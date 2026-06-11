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

LOT_SIZES = {
    "NIFTY": 50,
    "BANKNIFTY": 20
}

LOTS_PER_TRADE = 1
CANDLE_TIMEFRAME = 3

# ============================================
# STRATEGY PARAMETERS
# ============================================
EMA_FAST = 9
EMA_SLOW = 15
ANGLE_THRESHOLD = 30
VOLUME_LOOKBACK = 7
VOLUME_MULTIPLIER = 1.2

# ============================================
# RISK MANAGEMENT
# ============================================
RISK_REWARD_RATIO = 3

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
LOG_FILE = "logs/trading_bot.log"
TRADE_LOG_FILE = "logs/trades.csv"

# ============================================
# GENERAL SETTINGS
# ============================================
CONNECTION_TIMEOUT = 30
RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5
TRADE_DAYS = [0, 1, 2, 3, 4]  # Monday to Friday
MAX_ACTIVE_TRADES = 2
PAPER_TRADING = False
