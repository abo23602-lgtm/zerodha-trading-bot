#!/usr/bin/env python3
"""Zerodha Kite Automated Trading Bot - NIFTY & BANKNIFTY"""

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

    def get_stats(self):
        if len(self.volumes) < 2:
            return None
        vols = list(self.volumes)
        return {
            "current": vols[-1],
            "average": np.mean(vols[:-1]),
            "min": np.min(vols),
            "max": np.max(vols)
        }


class AngleDetector:
    """Detects 30 degree upward movement"""
    @staticmethod
    def calculate(start_price, end_price, candles):
        if start_price == 0:
            return 0
        change = end_price - start_price
        angle_rad = np.arctan(change / (start_price * candles))
        return np.degrees(angle_rad)


class TradingBot:
    """Main Trading Bot"""

    def __init__(self):
        self.kite = KiteConnect(api_key=config.API_KEY)
        self.kite.set_access_token(config.ACCESS_TOKEN)
        
        self.ema9 = {symbol: EMA(9) for symbol in config.TRADING_SYMBOLS}
        self.ema15 = {symbol: EMA(15) for symbol in config.TRADING_SYMBOLS}
        self.volume_analyzer = {symbol: VolumeAnalyzer(7) for symbol in config.TRADING_SYMBOLS}
        self.candle_history = {symbol: deque(maxlen=20) for symbol in config.TRADING_SYMBOLS}
        
        self.active_trades = {}
        self.closed_trades = []
        self.timezone = pytz.timezone(config.TIMEZONE)
        self.instruments = None
        
        logger.info("Bot initialized")

    def connect(self):
        """Connect to Kite API"""
        try:
            profile = self.kite.profile()
            logger.info(f"✅ Connected to Kite. User: {profile['user_name']}")
            
            # Get all instruments
            self.instruments = self.kite.instruments("NFO")
            logger.info(f"✅ Loaded {len(self.instruments)} NFO instruments")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            return False

    def get_instrument_token(self, symbol):
        """Get instrument token for symbol"""
        if not self.instruments:
            return None
        
        for inst in self.instruments:
            if inst["tradingsymbol"].startswith(symbol) and inst["tradingsymbol"].endswith("FUT"):
                return inst["instrument_token"]
        
        return None

    def get_historical_data(self, symbol, days=1):
        """Fetch historical 3-min candles"""
        try:
            token = self.get_instrument_token(symbol)
            
            if not token:
                logger.warning(f"⚠️ Instrument token not found for: {symbol}")
                return None
            
            # Fetch historical data
            from_date = datetime.now() - timedelta(days=days)
            data = self.kite.historical_data(token, from_date, datetime.now(), "3minute")
            
            return data
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    def process_candle(self, symbol, candle):
        """Process a new candle"""
        close = candle["close"]
        high = candle["high"]
        low = candle["low"]
        volume = candle["volume"]
        
        # Add to indicators
        self.ema9[symbol].add(close)
        self.ema15[symbol].add(close)
        self.volume_analyzer[symbol].add(volume)
        self.candle_history[symbol].append(candle)

    def check_buy_signal(self, symbol):
        """Check if buy signal is triggered"""
        
        # Need min 7 candles
        if len(self.candle_history[symbol]) < 7:
            return False, None
        
        # Condition 1: 9 EMA > 15 EMA
        ema9 = self.ema9[symbol].get()
        ema15 = self.ema15[symbol].get()
        
        if ema9 is None or ema15 is None or ema9 <= ema15:
            return False, None
        
        # Condition 2: 30° upward angle in last 7 candles
        candles = list(self.candle_history[symbol])
        start_price = candles[-7]["close"]
        end_price = candles[-1]["close"]
        angle = AngleDetector.calculate(start_price, end_price, 7)
        
        if angle < config.ANGLE_THRESHOLD:
            return False, None
        
        # Condition 3: High volume
        if not self.volume_analyzer[symbol].is_high(config.VOLUME_MULTIPLIER):
            return False, None
        
        # Condition 4: Within market hours (not after 3:20 PM)
        if not self.is_market_hours():
            logger.debug(f"⏰ Outside market hours")
            return False, None
        
        logger.info(f"🟢 BUY SIGNAL: {symbol} | EMA9={ema9:.2f} > EMA15={ema15:.2f} | Angle={angle:.2f}°")
        
        return True, {
            "ema9": ema9,
            "ema15": ema15,
            "angle": angle,
            "volume": self.candle_history[symbol][-1]["volume"]
        }

    def execute_buy(self, symbol, signal_data):
        """Execute buy trade"""
        try:
            if symbol in self.active_trades:
                logger.warning(f"⚠️ Already in trade for {symbol}")
                return False
            
            token = self.get_instrument_token(symbol)
            if not token:
                logger.error(f"❌ No token for {symbol}")
                return False
            
            # Get current price using quote
            quote = self.kite.quote(f"NFO:{self._get_tradingsymbol(symbol)}")
            if not quote:
                logger.error(f"❌ No quote for {symbol}")
                return False
            
            quote_key = f"NFO:{self._get_tradingsymbol(symbol)}"
            if quote_key not in quote:
                logger.error(f"❌ Quote key not found: {quote_key}")
                return False
            
            current_price = quote[quote_key]["last_price"]
            
            # Calculate lot size
            lot_size = config.LOT_SIZES.get(symbol, 1)
            quantity = lot_size * config.LOTS_PER_TRADE
            
            # Get 2nd last candle low as stop loss
            candles = list(self.candle_history[symbol])
            stop_loss = candles[-2]["low"] if len(candles) >= 2 else current_price * 0.98
            
            # Calculate take profit (1:3 ratio)
            sl_distance = current_price - stop_loss
            take_profit = current_price + (sl_distance * config.RISK_REWARD_RATIO)
            
            # Place order with SL and TP
            order = self.kite.place_order(
                variety="regular",
                exchange="NFO",
                tradingsymbol=self._get_tradingsymbol(symbol),
                transaction_type="BUY",
                quantity=quantity,
                order_type="MARKET",
                product="MIS"
            )
            
            logger.info(f"✅ BUY ORDER PLACED: {symbol} | Qty={quantity} | Price={current_price:.2f} | SL={stop_loss:.2f} | TP={take_profit:.2f}")
            
            self.active_trades[symbol] = {
                "order_id": order,
                "entry_price": current_price,
                "quantity": quantity,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "entry_time": datetime.now(self.timezone),
                "signal_data": signal_data
            }
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Error executing buy for {symbol}: {e}")
            return False

    def check_exit_conditions(self):
        """Check if any trades should exit"""
        to_exit = []
        
        for symbol, trade in list(self.active_trades.items()):
            try:
                ts = self._get_tradingsymbol(symbol)
                quote = self.kite.quote(f"NFO:{ts}")
                
                if f"NFO:{ts}" not in quote:
                    continue
                
                current_price = quote[f"NFO:{ts}"]["last_price"]
                
                # Check TP
                if current_price >= trade["take_profit"]:
                    logger.info(f"✅ TAKE PROFIT HIT: {symbol} @ {current_price:.2f}")
                    to_exit.append((symbol, current_price, "TAKE_PROFIT"))
                
                # Check SL
                elif current_price <= trade["stop_loss"]:
                    logger.info(f"❌ STOP LOSS HIT: {symbol} @ {current_price:.2f}")
                    to_exit.append((symbol, current_price, "STOP_LOSS"))
                
                # Check market close time
                elif self.should_close_at_eod():
                    logger.warning(f"⏰ EOD CLOSE TIME: Exiting {symbol}")
                    to_exit.append((symbol, current_price, "EOD"))
            
            except Exception as e:
                logger.error(f"Error checking exit for {symbol}: {e}")
        
        return to_exit

    def execute_sell(self, symbol, price, reason):
        """Execute sell to exit trade"""
        try:
            if symbol not in self.active_trades:
                return False
            
            trade = self.active_trades[symbol]
            
            # Place sell order
            order = self.kite.place_order(
                variety="regular",
                exchange="NFO",
                tradingsymbol=self._get_tradingsymbol(symbol),
                transaction_type="SELL",
                quantity=trade["quantity"],
                order_type="MARKET",
                product="MIS"
            )
            
            # Calculate P&L
            pnl = (price - trade["entry_price"]) * trade["quantity"]
            pnl_pct = ((price - trade["entry_price"]) / trade["entry_price"]) * 100
            
            emoji = "✅" if pnl > 0 else "❌"
            logger.info(f"{emoji} SELL ORDER: {symbol} | Price={price:.2f} | P&L=₹{pnl:.2f} ({pnl_pct:.2f}%) | Reason={reason}")
            
            # Log trade
            trade["exit_price"] = price
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
        """Check if should close at EOD (3:20 PM)"""
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
                        "Entry Time", "Symbol", "Entry Price", "Quantity",
                        "SL", "TP", "Exit Time", "Exit Price", "P&L", "P&L %", "Reason"
                    ])
                
                writer.writerow([
                    trade["entry_time"].strftime("%Y-%m-%d %H:%M:%S"),
                    symbol,
                    f"{trade['entry_price']:.2f}",
                    trade["quantity"],
                    f"{trade['stop_loss']:.2f}",
                    f"{trade['take_profit']:.2f}",
                    trade["exit_time"].strftime("%Y-%m-%d %H:%M:%S"),
                    f"{trade['exit_price']:.2f}",
                    f"{trade['pnl']:.2f}",
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
        total_pnl = sum(t["pnl"] for t in self.closed_trades)
        
        return {
            "Total Trades": total,
            "Wins": wins,
            "Losses": losses,
            "Win Rate": f"{(wins/total*100):.1f}%" if total > 0 else "0%",
            "Total P&L": f"₹{total_pnl:.2f}"
        }

    def _get_tradingsymbol(self, symbol):
        """Get trading symbol with current expiry (example: NIFTY24JANFUT)"""
        # This is a simplified version - you may need to fetch current expiry
        # For now, using a fixed pattern. Update as needed.
        if symbol == "NIFTY":
            return "NIFTY24JANFUT"  # Update month/year as needed
        elif symbol == "BANKNIFTY":
            return "BANKNIFTY24JANFUT"  # Update month/year as needed
        else:
            return f"{symbol}24JANFUT"

    def run(self):
        """Main trading loop"""
        logger.info("=" * 70)
        logger.info("🤖 Zerodha Kite Automated Trading Bot Started")
        logger.info("=" * 70)
        logger.info(f"Trading Symbols: {config.TRADING_SYMBOLS}")
        logger.info(f"Candle Timeframe: {config.CANDLE_TIMEFRAME} minutes")
        logger.info(f"Market Hours: {config.MARKET_START_TIME} - {config.MARKET_END_TIME} IST")
        logger.info(f"EOD Close Time: {config.MARKET_END_TIME} IST (NO TRADES AFTER THIS)")
        logger.info("=" * 70)
        
        if not self.connect():
            return
        
        try:
            while True:
                # Check market hours
                if not self.is_market_hours():
                    logger.debug(f"⏰ Waiting for market hours... ({datetime.now(self.timezone).strftime('%H:%M:%S')})")
                    time.sleep(60)
                    continue
                
                # Fetch and process candles
                for symbol in config.TRADING_SYMBOLS:
                    data = self.get_historical_data(symbol, days=1)
                    
                    if data:
                        for candle in data[-10:]:  # Last 10 candles
                            self.process_candle(symbol, candle)
                        
                        # Check buy signal
                        signal, signal_data = self.check_buy_signal(symbol)
                        if signal:
                            self.execute_buy(symbol, signal_data)
                
                # Check exit conditions
                exits = self.check_exit_conditions()
                for symbol, price, reason in exits:
                    self.execute_sell(symbol, price, reason)
                
                # Print status
                status = f"🔄 Status: Active={len(self.active_trades)} | Closed={len(self.closed_trades)} | Time={datetime.now(self.timezone).strftime('%H:%M:%S')}"
                logger.info(status)
                
                # Wait before next check (3 minutes = candle timeframe)
                time.sleep(180)
        
        except KeyboardInterrupt:
            logger.info("\n" + "=" * 70)
            logger.info("⚠️ Bot stopped by user")
            logger.info("=" * 70)
            
            # Close all active trades
            for symbol in list(self.active_trades.keys()):
                try:
                    ts = self._get_tradingsymbol(symbol)
                    quote = self.kite.quote(f"NFO:{ts}")
                    if f"NFO:{ts}" in quote:
                        price = quote[f"NFO:{ts}"]["last_price"]
                        self.execute_sell(symbol, price, "USER_STOP")
                except Exception as e:
                    logger.error(f"Error closing {symbol}: {e}")
            
            # Print summary
            summary = self.get_summary()
            if summary:
                logger.info("=" * 70)
                logger.info("📊 Trading Summary:")
                for key, value in summary.items():
                    logger.info(f"  {key}: {value}")
                logger.info("=" * 70)
            
            logger.info("Bot stopped gracefully")
        
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
            logger.error("Bot stopped due to error")


def main():
    """Entry point"""
    try:
        bot = TradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
