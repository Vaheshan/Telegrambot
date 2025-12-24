"""
Configuration file for backtesting Telegram trading signals
"""

# Binance API Configuration
BINANCE_API_KEY = ""  # Fill this in
BINANCE_API_SECRET = ""  # Fill this in

# Default TP/SL percentages when not provided in CSV
DEFAULT_TP_PERCENT = 2.0  # 2%
DEFAULT_SL_PERCENT = 5.0  # 5%

# TP/SL Testing Range
TP_START = 0.10  # Start at 0.10%
TP_END = 5.0     # End at 5.0%
TP_STEP = 0.10   # Increment by 0.10%

SL_START = 0.10  # Start at 0.10%
SL_END = 5.0     # End at 5.0%
SL_STEP = 0.10   # Increment by 0.10%

# Time windows to evaluate (in hours)
TIME_WINDOWS = [12]  # Only 12h window

# Trading parameters
LEVERAGE = 1  # No leverage for spot-like trading
POSITION_SIZE_USDT = 50  # Position size in USDT per trade

# Data download settings
BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"
MAX_KLINES_PER_REQUEST = 1500  # Binance limit

# File paths
CSV_INPUT_FILE = "telegram_signals.csv"
DATA_CACHE_DIR = "price_data_cache"
RESULTS_OUTPUT_DIR = "backtest_results"

# Performance settings
MAX_WORKERS = 8  # Number of parallel workers for backtesting
