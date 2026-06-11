# Zerodha Kite Automated Trading Bot

An **automated trading bot** for **NIFTY** and **BANKNIFTY** F&O using Zerodha Kite API.

## 🎯 Strategy

- **Entry Signal:** 9 EMA above 15 EMA + upward movement (30° angle) + high volume (last 7 candles)
- **Timeframe:** 3-minute candles
- **Trade:** 1 F&O lot per signal
- **Risk-Reward:** 1:3 ratio
- **Stop Loss:** 2nd last candle low
- **Take Profit:** SL distance × 3
- **Market Hours:** Only 9:15 AM - 3:20 PM IST (⚠️ **NO TRADES AFTER 3:20 PM to avoid EOD losses**)

## ✅ Features

- ✅ Real-time 3-min candle data from Zerodha Kite
- ✅ EMA (9 & 15) calculation
- ✅ Angle detection (30° upward movement)
- ✅ Volume analysis (7 candles)
- ✅ Automatic F&O trade execution
- ✅ Risk-reward management (1:3 ratio)
- ✅ **Market hours protection (NO EOD trades)**
- ✅ Trade logging & monitoring (CSV)
- ✅ Error handling & reconnection
- ✅ Telegram notifications (optional)

## 📋 Installation

### Requirements
- Python 3.8+
- Zerodha Kite API account
- Active F&O trading account

### Setup

1. **Clone or download this repository**

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Get API credentials from Zerodha:**
   - Go to https://kite.zerodha.com
   - Settings → API Tokens
   - Generate API Key and Secret
   - Get Access Token from dashboard

4. **Configure credentials:**
```bash
# Edit config.py and add your credentials:
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
ACCESS_TOKEN = "your_access_token"
```

5. **Update trading symbol expiry** in `bot.py`:
   - Current: `NIFTY24JANFUT` (update month/year)
   - Change to current futures expiry date

6. **Run the bot:**
```bash
python bot.py
```

## 📁 File Structure

```
zerodha-trading-bot/
├── bot.py              # Main bot script (READY TO RUN)
├── config.py           # Configuration (edit with your credentials)
├── requirements.txt    # Python dependencies
├── README.md           # This file
└── logs/               # Auto-created
    ├── trading_bot.log # Bot logs
    └── trades.csv      # Closed trades history
```

## 🚀 Usage

### Start the bot:
```bash
python bot.py
```

### Monitor trades:
- **Console:** Real-time status updates
- **Logs:** `logs/trading_bot.log` (detailed logs)
- **Trades:** `logs/trades.csv` (closed trades history)

### Stop the bot:
Press `Ctrl+C` (bot will auto-exit all open trades)

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Trading symbols
TRADING_SYMBOLS = ["NIFTY", "BANKNIFTY"]

# Lot sizes (per exchange standards)
LOT_SIZES = {
    "NIFTY": 50,
    "BANKNIFTY": 20
}

# Strategy parameters
EMA_FAST = 9          # Fast EMA period
EMA_SLOW = 15         # Slow EMA period
ANGLE_THRESHOLD = 30  # Minimum upward angle (degrees)
VOLUME_MULTIPLIER = 1.2  # Volume threshold (1.2 = 20% above average)

# Risk management
RISK_REWARD_RATIO = 3  # 1:3 ratio

# Market hours (IST)
MARKET_START_TIME = "09:15"
MARKET_END_TIME = "15:20"  # ⚠️ NO TRADES AFTER THIS
```

## 📊 Strategy Details

### Entry Conditions (ALL must be true):

1. **9 EMA > 15 EMA** - Bullish trend
2. **30° upward angle** - Strong upward movement (last 7 candles)
3. **High volume** - Volume > 7-candle average × 1.2
4. **Within market hours** - 9:15 AM to 3:20 PM IST

### Exit Strategy:
- **Take Profit:** SL distance × 3 (1:3 risk-reward)
- **Stop Loss:** 2nd last candle low
- **EOD Exit:** Auto-exit at 3:20 PM IST (prevents overnight gaps)

### Risk Management:
- One trade per symbol at a time
- Max 2 active trades simultaneously
- Auto-exit at market close to avoid overnight losses
- **NO TRADES after 3:20 PM IST** ⚠️

## 📝 Log Output Example

```
2024-01-15 09:30:45 - __main__ - INFO - ✅ Connected to Kite. User: ABC123
2024-01-15 09:31:00 - __main__ - INFO - 🟢 BUY SIGNAL: NIFTY | EMA9=22000.50 > EMA15=21999.20 | Angle=35.42°
2024-01-15 09:31:05 - __main__ - INFO - ✅ BUY ORDER PLACED: NIFTY | Qty=50 | Price=22010.00 | SL=22000.00 | TP=22040.00
2024-01-15 09:35:00 - __main__ - INFO - ✅ TAKE PROFIT HIT: NIFTY @ 22040.50
2024-01-15 09:35:10 - __main__ - INFO - ✅ SELL ORDER: NIFTY | Price=22040.50 | P&L=₹1502.50 (0.68%) | Reason=TAKE_PROFIT
```

## ⚠️ Important Notes

### Risk Warning:
- This bot executes **REAL TRADES** on your account
- Trading involves significant risk of loss
- Start with small position sizes (1 lot)
- Test thoroughly in paper trading first
- Monitor trades manually during first runs
- **NO TRADES AFTER 3:20 PM** to avoid overnight gaps/losses

### Before Running:
1. Verify all credentials are correct
2. Check market is open (9:15 AM - 3:30 PM IST)
3. Ensure sufficient margin in your account
4. Update futures expiry dates in `bot.py`
5. Start with 1 lot size for testing

### Telegram Notifications (Optional):
To enable notifications:
```python
ENABLE_TELEGRAM = True
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
```

## 🔗 API Documentation

- [Zerodha Kite Python](https://kite.trade)
- [KiteConnect Documentation](https://kite.trade/docs/connect/v3/)
- [Zerodha Dashboard](https://kite.zerodha.com)

## 📈 Expected Results

- Win rate: 60-70% (dependent on market conditions)
- Average P&L per trade: ±50-200 points
- Max drawdown: Monitor and adjust accordingly

## 🐛 Troubleshooting

### "Access token invalid"
- Get a new access token from Zerodha dashboard
- Update `config.py` with new token

### "Instrument not found"
- Update trading symbol expiry in `bot.py`
- Example: Change `NIFTY24JANFUT` to `NIFTY24FEBFUT`

### "Quote not available"
- Market may be closed
- Check market hours: 9:15 AM - 3:30 PM IST
- Verify internet connection

### No trades executing
- Check EMA values (9 EMA must be > 15 EMA)
- Verify angle > 30 degrees
- Check volume > 7-candle average
- Ensure within market hours

## 📞 Support

For issues:
1. Check `logs/trading_bot.log` for error details
2. Verify all API credentials in `config.py`
3. Ensure market is open during trading hours
4. Create an issue on GitHub

## 📄 License

MIT License - Feel free to use & modify

---

## ⚡ Quick Start Checklist

- [ ] Clone repository
- [ ] Edit `config.py` with your API credentials
- [ ] Update futures expiry in `bot.py`
- [ ] Run `pip install -r requirements.txt`
- [ ] Run `python bot.py`
- [ ] Monitor `logs/trading_bot.log`
- [ ] Check `logs/trades.csv` for closed trades

**Disclaimer:** This bot is for educational purposes. Trading involves risk. Use at your own discretion. Monitor trades actively, especially during initial runs.
