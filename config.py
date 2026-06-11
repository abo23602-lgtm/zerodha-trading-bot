# ============================================
# ZERODHA KITE API CREDENTIALS
# ============================================
API_KEY = "your_api_key_here"
API_SECRET = "your_api_secret_here"
ACCESS_TOKEN = "your_access_token_here"  # GET FROM ZERODHA DASHBOARD

# ============================================
# TRADING CONFIGURATION
# ============================================
TRADING_SYMBOLS = ["NIFTY", "BANKNIFTY"]

# CURRENT LOT SIZES (Updated 2024)
LOT_SIZES = {
    "NIFTY": 65,           # Updated: 65 units per lot
    "BANKNIFTY": 30        # Updated: 30 units per lot
}

LOTS_PER_TRADE = 1
CANDLE_TIMEFRAME = 3

# ============================================
# OPTION TYPE SETTINGS (CALL & PUT)
# ============================================
CALL_OPTION_TYPE = "CE"  # Call European
PUT_OPTION_TYPE = "PE"   # Put European
STRIKE_OFFSET = 0        # 0 = ATM (At The Money)

# Strike interval (depends on index)
NIFTY_STRIKE_INTERVAL = 50      # NIFTY strikes: 23000, 23050, etc
BANKNIFTY_STRIKE_INTERVAL = 100 # BANKNIFTY strikes: 47000, 47100, etc

# ============================================
# STRATEGY PARAMETERS
# ============================================
EMA_FAST = 9
EMA_SLOW = 15
ANGLE_THRESHOLD = 30  # Both upward and downward

VOLUME_LOOKBACK = 7
VOLUME_MULTIPLIER = 1.2

# ============================================
# OPTION RISK MANAGEMENT
# ============================================
RISK_REWARD_RATIO = 3

# Time decay management
DAYS_TO_EXPIRY_MIN = 3  # Don't trade if expiry < 3 days
DAYS_TO_EXPIRY_MAX = 10 # Don't trade if expiry > 10 days

# CALL OPTION: Buy when 9 EMA > 15 EMA (BULLISH + 30° UP angle)
CALL_OPTION_PROFIT_TARGET_PCT = 50  # Exit at 50% profit
CALL_OPTION_STOP_LOSS_PCT = 30      # Exit at 30% loss

# PUT OPTION: Buy when 9 EMA < 15 EMA (BEARISH + 30° DOWN angle)
PUT_OPTION_PROFIT_TARGET_PCT = 50   # Exit at 50% profit
PUT_OPTION_STOP_LOSS_PCT = 30       # Exit at 30% loss

# ============================================
# MARKET HOURS (IST)
# ============================================
MARKET_START_TIME = "09:15"
MARKET_END_TIME = "15:20"  # NO TRADES AFTER THIS ⚠️
MARKET_CLOSE_TIME = "15:30"
TIMEZONE = "Asia/Kolkata"

# ============================================
# TELEGRAM NOTIFICATIONS
# ============================================
ENABLE_TELEGRAM = False
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"

# ============================================
# LOGGING
# ============================================
LOG_LEVEL = "INFO"
LOG_FILE = "logs/trading_bot_options.log"
TRADE_LOG_FILE = "logs/option_trades.csv"

# ============================================
# GENERAL SETTINGS
# ============================================
CONNECTION_TIMEOUT = 30
RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5
TRADE_DAYS = [0, 1, 2, 3, 4]  # Monday to Friday
MAX_ACTIVE_TRADES = 2
PAPER_TRADING = False

# ============================================
# CAPITAL MANAGEMENT
# ============================================
INITIAL_CAPITAL = 200000  # ₹2,00,000 for 1-week test
RISK_PER_TRADE = 30000   # Max ₹30,000 per trade (15% of capital)
