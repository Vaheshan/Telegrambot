"""
Configuration file for backtesting Telegram trading signals
"""

# Binance API Configuration
BINANCE_API_KEY = ""  # Fill this in
BINANCE_API_SECRET = ""  # Fill this in

# Default TP/SL percentages when not provided in CSV
DEFAULT_TP_PERCENT = 2.5  # 2%
DEFAULT_SL_PERCENT = 5  # 5%

# TP/SL Testing Range
TP_START = 0.10  # Start at 0.10%
TP_END = 5.0     # End at 5.0%
TP_STEP = 0.10   # Increment by 0.10%

SL_START = 0.10  # Start at 0.10%
SL_END = 5.0     # End at 5.0%
SL_STEP = 0.10   # Increment by 0.10%

# Time windows to evaluate (in hours)
TIME_WINDOWS = [12]  # Only 12h window

# Signal timezone offset
# Signals are timestamped in Sri Lanka time (UTC+5:30); Binance data is UTC.
# Convert signal timestamps to UTC by subtracting this offset.
SIGNAL_TIMEZONE_OFFSET_MINUTES = 330

# Trading parameters
LEVERAGE = 20  # Leverage for futures trading (1x = no leverage)
POSITION_SIZE_USDT = 50  # Position size in USDT per trade
MAX_CONCURRENT_POSITIONS = 10  # Maximum number of positions open at once

# Entry price selection
USE_BETTER_MARKET_PRICE = True  # If True, use current market price if it's better than signal entry price
# For long: market price is better if lower than signal entry
# For short: market price is better if higher than signal entry

# Data download settings
BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"
MAX_KLINES_PER_REQUEST = 1500  # Binance limit

# File paths
CSV_INPUT_FILE = "telegram_signals.csv"
DATA_CACHE_DIR = "price_data_cache"
RESULTS_OUTPUT_DIR = "backtest_results"

# Performance settings
MAX_WORKERS = 8  # Number of parallel workers for backtesting
