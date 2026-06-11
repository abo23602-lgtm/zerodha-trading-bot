#!/usr/bin/env python3
"""Zerodha Kite Automated Options Trading Bot - CALL & PUT - NIFTY & BANKNIFTY"""

import logging
import time
import sys
from datetime import datetime, timedelta
import pytz
from collections import deque
import numpy as np
import csv
import os

try:
    import config
except ImportError:
    print("ERROR: config.py not found!")
    sys.exit(1)

try:
    from kiteconnect import KiteConnect
except ImportError:
    print("ERROR: kiteconnect not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EMA:
    """Exponential Moving Average"""
    def __init__(self, period):
        self.period = period
        self.values = deque(maxlen=period * 2)
        self.ema = None
        self.multiplier = 2 / (period + 1)

    def add(self, value):
        self.values.append(value)
        if len(self.values) < self.period:
            return None
        if self.ema is None:
            self.ema = np.mean(list(self.values)[:self.period])
        else:
            self.ema = value * self.multiplier + self.ema * (1 - self.multiplier)
        return self.ema

    def get(self):
        return self.ema


class VolumeAnalyzer:
    """Volume Analysis"""
    def __init__(self, lookback=7):
        self.lookback = lookback
        self.volumes = deque(maxlen=lookback + 1)

    def add(self, volume):
        self.volumes.append(volume)

    def is_high(self, multiplier=1.2):
        if len(self.volumes) < self.lookback:
            return False
        past = list(self.volumes)[:-1]
        avg = np.mean(past)
        current = self.volumes[-1]
        return current > avg * multiplier


class AngleDetector:
    """Detects upward/downward angle movement"""
    @staticmethod
    def calculate(start_price, end_price, candles):
        if start_price == 0:
            return 0
        change = end_price - start_price
        angle_rad = np.arctan(change / (start_price * candles))
        return np.degrees(angle_rad)

    @staticmethod
    def is_upward(angle, threshold=30):
        """Check if angle is upward (positive and above threshold)"""
        return angle > threshold

    @staticmethod
    def is_downward(angle, threshold=30):
        """Check if angle is downward (negative and below -threshold)"""
        return angle < -threshold


class OptionsStrategyBot:
    """Bidirectional Options Trading Bot - CALL & PUT"""

    def __init__(self):
        self.kite = KiteConnect(api_key=config.API_KEY)
        
        self.ema9 = {symbol: EMA(9) for symbol in config.TRADING_SYMBOLS}
        self.ema15 = {symbol: EMA(15) for symbol in config.TRADING_SYMBOLS}
        self.volume_analyzer = {symbol: VolumeAnalyzer(7) for symbol in config.TRADING_SYMBOLS}
        self.candle_history = {symbol: deque(maxlen=20) for symbol in config.TRADING_SYMBOLS}
        
        self.active_trades = {}  # {symbol: trade_object}
        self.closed_trades = []
        self.timezone = pytz.timezone(config.TIMEZONE)
        self.instruments = None
        self.current_prices = {}
        
        logger.info("🟢🔴 Bidirectional Options Trading Bot (CALL & PUT) initialized")

    def get_access_token(self):
        """Get access token from Zerodha"""
        
        if hasattr(config, 'ACCESS_TOKEN') and config.ACCESS_TOKEN and config.ACCESS_TOKEN != "your_access_token_here":
            logger.info("✅ Using ACCESS_TOKEN from config.py")
            return config.ACCESS_TOKEN
        
        logger.warning("⚠️ No valid access token found.")
        logger.info("📌 Get your access token from: https://kite.zerodha.com")
        
        manual_token = input("\n📋 Enter your access token: ").strip()
        
        if manual_token and manual_token != "your_access_token_here":
            self._save_access_token(manual_token)
            return manual_token
        
        return None
    
    def _save_access_token(self, token):
        """Save access token to config file"""
        try:
            with open('config.py', 'r') as f:
                content = f.read()
            
            import re
            content = re.sub(
                r'ACCESS_TOKEN = "[^"]*"',
                f'ACCESS_TOKEN = "{token}"',
                content
            )
            
            with open('config.py', 'w') as f:
                f.write(content)
            
            logger.info("💾 Access token saved to config.py")
        except Exception as e:
            logger.warning(f"⚠️ Could not save token: {e}")

    def connect(self):
        """Connect to Kite API"""
        try:
            access_token = self.get_access_token()
            
            if not access_token:
                logger.error("❌ Failed to get access token")
                return False
            
            self.kite.set_access_token(access_token)
            
            profile = self.kite.profile()
            logger.info(f"✅ Connected to Kite. User: {profile['user_name']}")
            
            self.instruments = self.kite.instruments("NFO")
            logger.info(f"✅ Loaded {len(self.instruments)} NFO instruments")
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            return False

    def get_instrument_token(self, symbol):
        """Get instrument token for SPOT price"""
        if not self.instruments:
            return None
        
        for inst in self.instruments:
            if inst["tradingsymbol"] == symbol and inst["segment"] == "INDICES":
                return inst["instrument_token"]
        
        return None

    def get_option_token(self, symbol, strike, expiry_date, option_type):
        """Get instrument token for Option (CALL or PUT)"""
        if not self.instruments:
            return None
        
        option_symbol = f"{symbol}{expiry_date}{strike}{option_type}"
        
        for inst in self.instruments:
            if inst["tradingsymbol"] == option_symbol:
                return inst["instrument_token"]
        
        logger.warning(f"⚠️ Option not found: {option_symbol}")
        return None

    def get_nearest_strike(self, symbol, ltp):
        """Get nearest ATM strike"""
        if symbol == "NIFTY":
            interval = config.NIFTY_STRIKE_INTERVAL
        else:
            interval = config.BANKNIFTY_STRIKE_INTERVAL
        
        strike = round(ltp / interval) * interval
        strike = strike + (config.STRIKE_OFFSET * interval)
        
        return int(strike)

    def get_current_expiry_date(self):
        """Get current option expiry date"""
        today = datetime.now(self.timezone)
        
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0:
            days_until_thursday = 7
        
        expiry = today + timedelta(days=days_until_thursday)
        
        return expiry.strftime("%d%b").upper()

    def get_historical_data(self, symbol, days=1):
        """Fetch historical 3-min candles"""
        try:
            token = self.get_instrument_token(symbol)
            
            if not token:
                logger.warning(f"⚠️ Instrument token not found for: {symbol}")
                return None
            
            from_date = datetime.now() - timedelta(days=days)
            data = self.kite.historical_data(token, from_date, datetime.now(), "3minute")
            
            return data
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    def process_candle(self, symbol, candle):
        """Process a new candle"""
        close = candle["close"]
        volume = candle["volume"]
        
        self.current_prices[symbol] = close
        
        self.ema9[symbol].add(close)
        self.ema15[symbol].add(close)
        self.volume_analyzer[symbol].add(volume)
        self.candle_history[symbol].append(candle)

    def check_signals(self, symbol):
        """Check for CALL (bullish) or PUT (bearish) signals"""
        
        if len(self.candle_history[symbol]) < 7:
            return None, None
        
        ema9 = self.ema9[symbol].get()
        ema15 = self.ema15[symbol].get()
        
        if ema9 is None or ema15 is None:
            return None, None
        
        # Calculate angle
        candles = list(self.candle_history[symbol])
        start_price = candles[-7]["close"]
        end_price = candles[-1]["close"]
        angle = AngleDetector.calculate(start_price, end_price, 7)
        
        # Check volume
        if not self.volume_analyzer[symbol].is_high(config.VOLUME_MULTIPLIER):
            return None, None
        
        # Check market hours
        if not self.is_market_hours():
            return None, None
        
        # ============================================
        # CALL OPTION SIGNAL (BULLISH)
        # ============================================
        # Condition: 9 EMA > 15 EMA AND angle > 30° (UPWARD)
        if ema9 > ema15 and AngleDetector.is_upward(angle, config.ANGLE_THRESHOLD):
            logger.info(f"🟢 CALL SIGNAL (BULLISH): {symbol} | EMA9={ema9:.2f} > EMA15={ema15:.2f} | Angle={angle:.2f}° ⬆️")
            return "CE", {
                "ema9": ema9,
                "ema15": ema15,
                "angle": angle,
                "volume": candles[-1]["volume"],
                "direction": "BULLISH"
            }
        
        # ============================================
        # PUT OPTION SIGNAL (BEARISH)
        # ============================================
        # Condition: 9 EMA < 15 EMA AND angle < -30° (DOWNWARD)
        if ema9 < ema15 and AngleDetector.is_downward(angle, config.ANGLE_THRESHOLD):
            logger.info(f"🔴 PUT SIGNAL (BEARISH): {symbol} | EMA9={ema9:.2f} < EMA15={ema15:.2f} | Angle={angle:.2f}° ⬇️")
            return "PE", {
                "ema9": ema9,
                "ema15": ema15,
                "angle": angle,
                "volume": candles[-1]["volume"],
                "direction": "BEARISH"
            }
        
        return None, None

    def execute_option_trade(self, symbol, option_type, signal_data):
        """Execute CALL or PUT option trade"""
        try:
            if symbol in self.active_trades:
                logger.warning(f"⚠️ Already in trade for {symbol}")
                return False
            
            current_price = self.current_prices.get(symbol)
            if not current_price:
                logger.error(f"❌ No current price for {symbol}")
                return False
            
            strike = self.get_nearest_strike(symbol, current_price)
            expiry = self.get_current_expiry_date()
            
            # Get option token
            option_token = self.get_option_token(symbol, strike, expiry, option_type)
            if not option_token:
                logger.error(f"❌ Option token not found")
                return False
            
            # Get option premium
            quote = self.kite.quote(f"NFO:{symbol}{expiry}{strike}{option_type}")
            
            if not quote:
                logger.error(f"❌ No quote for option")
                return False
            
            quote_key = f"NFO:{symbol}{expiry}{strike}{option_type}"
            if quote_key not in quote:
                logger.error(f"❌ Quote key not found: {quote_key}")
                return False
            
            premium = quote[quote_key]["last_price"]
            
            lot_size = config.LOT_SIZES.get(symbol, 1)
            quantity = lot_size * config.LOTS_PER_TRADE
            
            total_capital = premium * quantity
            
            if total_capital > config.RISK_PER_TRADE:
                logger.warning(f"⚠️ Capital required (₹{total_capital:.0f}) exceeds risk limit (₹{config.RISK_PER_TRADE})")
                return False
            
            # Place BUY order
            order = self.kite.place_order(
                variety="regular",
                exchange="NFO",
                tradingsymbol=f"{symbol}{expiry}{strike}{option_type}",
                transaction_type="BUY",
                quantity=quantity,
                order_type="MARKET",
                product="MIS"
            )
            
            # Determine profit target and stop loss based on option type
            if option_type == "CE":
                profit_pct = config.CALL_OPTION_PROFIT_TARGET_PCT
                stop_loss_pct = config.CALL_OPTION_STOP_LOSS_PCT
            else:  # PE
                profit_pct = config.PUT_OPTION_PROFIT_TARGET_PCT
                stop_loss_pct = config.PUT_OPTION_STOP_LOSS_PCT
            
            profit_target_premium = premium * (1 + profit_pct / 100)
            stop_loss_premium = premium * (1 - stop_loss_pct / 100)
            
            option_name = "CALL 🟢" if option_type == "CE" else "PUT 🔴"
            direction = "BULLISH ⬆️" if option_type == "CE" else "BEARISH ⬇️"
            
            logger.info(f"✅ BUY {option_name} OPTION: {symbol} ({direction}) | Strike={strike} | Qty={quantity} | Premium=₹{premium:.2f} | Total=₹{total_capital:.0f}")
            logger.info(f"   Profit Target (₹{profit_target_premium:.2f}): +{profit_pct}% 📈")
            logger.info(f"   Stop Loss (₹{stop_loss_premium:.2f}): -{stop_loss_pct}% 📉")
            
            self.active_trades[symbol] = {
                "order_id": order,
                "entry_premium": premium,
                "quantity": quantity,
                "strike": strike,
                "expiry": expiry,
                "option_type": option_type,  # CE or PE
                "profit_target": profit_target_premium,
                "stop_loss": stop_loss_premium,
                "entry_time": datetime.now(self.timezone),
                "signal_data": signal_data,
                "tradingsymbol": f"{symbol}{expiry}{strike}{option_type}",
                "entry_price": current_price,
                "direction": signal_data.get("direction")
            }
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Error executing option trade for {symbol}: {e}")
            return False

    def check_exit_conditions(self):
        """Check if any option trades should exit"""
        to_exit = []
        
        for symbol, trade in list(self.active_trades.items()):
            try:
                quote = self.kite.quote(f"NFO:{trade['tradingsymbol']}")
                
                if f"NFO:{trade['tradingsymbol']}" not in quote:
                    continue
                
                current_premium = quote[f"NFO:{trade['tradingsymbol']}"]["last_price"]
                
                # Profit Target
                if current_premium >= trade["profit_target"]:
                    option_name = "CALL 🟢" if trade["option_type"] == "CE" else "PUT 🔴"
                    logger.info(f"✅ PROFIT TARGET HIT: {symbol} {option_name} @ ₹{current_premium:.2f}")
                    to_exit.append((symbol, current_premium, "PROFIT_TARGET"))
                
                # Stop Loss
                elif current_premium <= trade["stop_loss"]:
                    option_name = "CALL 🟢" if trade["option_type"] == "CE" else "PUT 🔴"
                    logger.info(f"❌ STOP LOSS HIT: {symbol} {option_name} @ ₹{current_premium:.2f}")
                    to_exit.append((symbol, current_premium, "STOP_LOSS"))
                
                # Expiry approaching
                days_to_expiry = self._days_until_expiry(trade["expiry"])
                if days_to_expiry <= config.DAYS_TO_EXPIRY_MIN:
                    logger.warning(f"⏰ Expiry approaching ({days_to_expiry} days): Exiting {symbol}")
                    to_exit.append((symbol, current_premium, "EXPIRY_APPROACH"))
                
                # EOD close
                elif self.should_close_at_eod():
                    logger.warning(f"⏰ EOD CLOSE TIME: Exiting {symbol}")
                    to_exit.append((symbol, current_premium, "EOD"))
            
            except Exception as e:
                logger.error(f"Error checking exit for {symbol}: {e}")
        
        return to_exit

    def _days_until_expiry(self, expiry_str):
        """Calculate days until option expiry"""
        try:
            today = datetime.now(self.timezone)
            day = int(expiry_str[:2])
            month_str = expiry_str[2:].upper()
            
            year = today.year
            month = datetime.strptime(month_str, "%b").month
            
            expiry_date = datetime(year, month, day, 15, 30, tzinfo=self.timezone)
            
            if expiry_date < today:
                year += 1
                expiry_date = datetime(year, month, day, 15, 30, tzinfo=self.timezone)
            
            days_diff = (expiry_date - today).days
            return max(0, days_diff)
        except:
            return 0

    def execute_sell_option(self, symbol, current_premium, reason):
        """Execute SELL to close option trade"""
        try:
            if symbol not in self.active_trades:
                return False
            
            trade = self.active_trades[symbol]
            
            # Place SELL order
            order = self.kite.place_order(
                variety="regular",
                exchange="NFO",
                tradingsymbol=trade["tradingsymbol"],
                transaction_type="SELL",
                quantity=trade["quantity"],
                order_type="MARKET",
                product="MIS"
            )
            
            # Calculate P&L
            premium_change = current_premium - trade["entry_premium"]
            pnl = premium_change * trade["quantity"]
            pnl_pct = ((premium_change) / trade["entry_premium"]) * 100
            
            option_name = "CALL 🟢" if trade["option_type"] == "CE" else "PUT 🔴"
            emoji = "✅" if pnl > 0 else "❌"
            logger.info(f"{emoji} SELL {option_name} OPTION: {symbol} | Exit Premium=₹{current_premium:.2f} | P&L=₹{pnl:.0f} ({pnl_pct:.2f}%) | Reason={reason}")
            
            # Log trade
            trade["exit_premium"] = current_premium
            trade["exit_time"] = datetime.now(self.timezone)
            trade["pnl"] = pnl
            trade["pnl_pct"] = pnl_pct
            trade["reason"] = reason
            
            self.closed_trades.append(trade)
            self.log_trade(symbol, trade)
            
            del self.active_trades[symbol]
            return True
        
        except Exception as e:
            logger.error(f"❌ Error executing sell for {symbol}: {e}")
            return False

    def is_market_hours(self):
        """Check if within market hours"""
        now = datetime.now(self.timezone)
        start_h, start_m = map(int, config.MARKET_START_TIME.split(":"))
        end_h, end_m = map(int, config.MARKET_END_TIME.split(":"))
        
        current_time = now.time()
        start_time = current_time.replace(hour=start_h, minute=start_m)
        end_time = current_time.replace(hour=end_h, minute=end_m)
        
        is_weekday = now.weekday() < 5
        is_trading_hours = start_time <= current_time < end_time
        
        return is_weekday and is_trading_hours

    def should_close_at_eod(self):
        """Check if should close at EOD"""
        now = datetime.now(self.timezone)
        close_h, close_m = map(int, config.MARKET_END_TIME.split(":"))
        
        current_time = now.time()
        close_time = current_time.replace(hour=close_h, minute=close_m)
        
        return current_time >= close_time

    def log_trade(self, symbol, trade):
        """Log closed trade to CSV"""
        try:
            file_exists = os.path.exists(config.TRADE_LOG_FILE)
            
            with open(config.TRADE_LOG_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                
                if not file_exists:
                    writer.writerow([
                        "Entry Time", "Symbol", "Type", "Direction", "Strike", "Expiry", "Entry Premium", "Qty",
                        "Profit Target", "Stop Loss", "Exit Time", "Exit Premium", "P&L", "P&L %", "Reason"
                    ])
                
                option_type_name = "CALL" if trade["option_type"] == "CE" else "PUT"
                direction = trade.get("direction", "N/A")
                
                writer.writerow([
                    trade["entry_time"].strftime("%Y-%m-%d %H:%M:%S"),
                    symbol,
                    option_type_name,
                    direction,
                    trade["strike"],
                    trade["expiry"],
                    f"{trade['entry_premium']:.2f}",
                    trade["quantity"],
                    f"{trade['profit_target']:.2f}",
                    f"{trade['stop_loss']:.2f}",
                    trade["exit_time"].strftime("%Y-%m-%d %H:%M:%S"),
                    f"{trade['exit_premium']:.2f}",
                    f"{trade['pnl']:.0f}",
                    f"{trade['pnl_pct']:.2f}",
                    trade["reason"]
                ])
            
            logger.info(f"📊 Trade logged to {config.TRADE_LOG_FILE}")
        
        except Exception as e:
            logger.error(f"Error logging trade: {e}")

    def get_summary(self):
        """Get trading summary"""
        if not self.closed_trades:
            return None
        
        total = len(self.closed_trades)
        wins = len([t for t in self.closed_trades if t["pnl"] > 0])
        losses = len([t for t in self.closed_trades if t["pnl"] < 0])
        calls = len([t for t in self.closed_trades if t["option_type"] == "CE"])
        puts = len([t for t in self.closed_trades if t["option_type"] == "PE"])
        total_pnl = sum(t["pnl"] for t in self.closed_trades)
        avg_pnl = total_pnl / total if total > 0 else 0
        
        return {
            "Total Trades": total,
            "CALL Trades": calls,
            "PUT Trades": puts,
            "Wins": wins,
            "Losses": losses,
            "Win Rate": f"{(wins/total*100):.1f}%" if total > 0 else "0%",
            "Total P&L": f"₹{total_pnl:.0f}",
            "Avg P&L per trade": f"₹{avg_pnl:.0f}"
        }

    def run(self):
        """Main trading loop"""
        logger.info("=" * 110)
        logger.info("🟢🔴 BIDIRECTIONAL OPTIONS TRADING BOT (CALL & PUT) - 1 WEEK TEST")
        logger.info("=" * 110)
        logger.info(f"📊 Trading Symbols: {config.TRADING_SYMBOLS}")
        logger.info(f"📈 NIFTY Lot Size: {config.LOT_SIZES['NIFTY']} units")
        logger.info(f"📈 BANKNIFTY Lot Size: {config.LOT_SIZES['BANKNIFTY']} units")
        logger.info(f"⏰ Candle Timeframe: {config.CANDLE_TIMEFRAME} minutes")
        logger.info(f"🕐 Market Hours: {config.MARKET_START_TIME} - {config.MARKET_END_TIME} IST")
        logger.info("")
        logger.info("🟢 CALL OPTION (BULLISH): When 9 EMA > 15 EMA AND Angle > +30° (UPWARD)")
        logger.info(f"   Profit Target: +{config.CALL_OPTION_PROFIT_TARGET_PCT}% | Stop Loss: -{config.CALL_OPTION_STOP_LOSS_PCT}%")
        logger.info("")
        logger.info("🔴 PUT OPTION (BEARISH): When 9 EMA < 15 EMA AND Angle < -30° (DOWNWARD)")
        logger.info(f"   Profit Target: +{config.PUT_OPTION_PROFIT_TARGET_PCT}% | Stop Loss: -{config.PUT_OPTION_STOP_LOSS_PCT}%")
        logger.info("")
        logger.info(f"💰 Risk Per Trade: ₹{config.RISK_PER_TRADE}")
        logger.info(f"⏰ Exit before {config.DAYS_TO_EXPIRY_MIN} days to expiry")
        logger.info("=" * 110)
        
        if not self.connect():
            return
        
        try:
            while True:
                if not self.is_market_hours():
                    logger.debug(f"⏰ Waiting for market hours... ({datetime.now(self.timezone).strftime('%H:%M:%S')})")
                    time.sleep(60)
                    continue
                
                for symbol in config.TRADING_SYMBOLS:
                    data = self.get_historical_data(symbol, days=1)
                    
                    if data:
                        for candle in data[-10:]:
                            self.process_candle(symbol, candle)
                        
                        # Check for CALL or PUT signals
                        option_type, signal_data = self.check_signals(symbol)
                        if option_type and signal_data:
                            self.execute_option_trade(symbol, option_type, signal_data)
                
                # Check exit conditions
                exits = self.check_exit_conditions()
                for symbol, premium, reason in exits:
                    self.execute_sell_option(symbol, premium, reason)
                
                # Print status
                status = f"🔄 Active={len(self.active_trades)} | Closed={len(self.closed_trades)} | Time={datetime.now(self.timezone).strftime('%H:%M:%S')}"
                logger.info(status)
                
                time.sleep(180)
        
        except KeyboardInterrupt:
            logger.info("\n" + "=" * 110)
            logger.info("⚠️ Bot stopped by user")
            logger.info("=" * 110)
            
            # Close all active trades
            for symbol in list(self.active_trades.keys()):
                try:
                    quote = self.kite.quote(f"NFO:{self.active_trades[symbol]['tradingsymbol']}")
                    if f"NFO:{self.active_trades[symbol]['tradingsymbol']}" in quote:
                        premium = quote[f"NFO:{self.active_trades[symbol]['tradingsymbol']}"]["last_price"]
                        self.execute_sell_option(symbol, premium, "USER_STOP")
                except Exception as e:
                    logger.error(f"Error closing {symbol}: {e}")
            
            # Print summary
            summary = self.get_summary()
            if summary:
                logger.info("=" * 110)
                logger.info("📊 TRADING SUMMARY (1-WEEK TEST):")
                for key, value in summary.items():
                    logger.info(f"  {key}: {value}")
                logger.info("=" * 110)
                
                if summary["Wins"] > 0 and float(summary["Total P&L"].replace("₹", "")) > 0:
                    logger.info("✅ BIDIRECTIONAL STRATEGY WORKING! Ready to scale up next week.")
                else:
                    logger.info("⚠️ Strategy needs adjustment. Test another week before scaling.")
            
            logger.info("Bot stopped gracefully")
        
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
            logger.error("Bot stopped due to error")


def main():
    """Entry point"""
    try:
        bot = OptionsStrategyBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
