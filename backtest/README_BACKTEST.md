# Telegram Signals Backtesting System

## Overview

This backtesting system analyzes historical Telegram trading signals to find optimal take-profit (TP) and stop-loss (SL) percentages.

## Files

### Configuration
- **config_backtest.py** - Main configuration file
  - Set your Binance API credentials here (optional, public data only)
  - Adjust default TP/SL percentages
  - Configure testing ranges and parameters

### Data Download
- **download_price_data.py** - Downloads 1-minute OHLCV data from Binance Futures
  - Uses public API (no authentication needed)
  - Implements caching to avoid re-downloading
  - Data stored in `price_data_cache/` directory

### Backtesting Engine
- **backtest_engine.py** - Core backtesting logic
  - Simulates trade execution
  - Checks entry fills
  - Tests TP/SL hits
  - Handles expired trades

### Main Runner
- **run_backtest.py** - Runs comprehensive backtest
  - Tests all TP/SL combinations
  - Tests multiple time windows (4h, 8h, 12h)
  - Generates detailed reports
  - Finds optimal parameters

## Setup Instructions

### 1. Install Required Packages

```bash
pip install pandas numpy requests tqdm
```

### 2. Configure Settings

Edit `config_backtest.py`:

```python
# Default TP/SL when not in CSV
DEFAULT_TP_PERCENT = 2.0  # Change as needed
DEFAULT_SL_PERCENT = 5.0  # Change as needed

# Testing ranges
TP_START = 0.10  # Start testing from 0.10%
TP_END = 5.0     # Test up to 5.0%
TP_STEP = 0.10   # Increment by 0.10%

SL_START = 0.10
SL_END = 5.0
SL_STEP = 0.10
```

### 3. Prepare Your Data

Ensure `telegram_signals.csv` is in the same directory with columns:
- symbol
- date
- time
- side
- entry
- stop_loss (optional)
- tp1, tp2, tp3, tp4 (optional)

### 4. Run the Backtest

```bash
python run_backtest.py
```

## How It Works

### 1. Data Download
- For each signal, downloads 1-minute price data from Binance Futures
- Downloads data from 1 hour before signal to 13 hours after
- Caches data locally to speed up subsequent runs

### 2. Entry Detection
- Checks if entry price was actually hit after signal
- For LONG: entry hit when price drops to entry level
- For SHORT: entry hit when price rises to entry level

### 3. Trade Simulation
- After entry, monitors price minute-by-minute
- Checks if TP or SL is hit first
- Respects time windows (4h, 8h, 12h)
- Force-closes at window end if neither TP/SL hit

### 4. Results Classification
- **Win**: TP hit before SL within time window
- **Loss**: SL hit before TP within time window
- **Expired**: Neither hit, force-closed at window end
- **No Entry**: Entry price never reached

### 5. Performance Metrics
- Win Rate: Percentage of winning trades
- Total PnL: Sum of all profits/losses
- Expectancy: Average expected profit per trade
- Profit Factor: Gross profit / Gross loss
- Expired Analysis: PnL impact of expired trades

## Output Files

All results saved in `backtest_results/` directory:

### Individual Window Results
- `backtest_results_4h.csv` - Results for 4-hour window
- `backtest_results_8h.csv` - Results for 8-hour window
- `backtest_results_12h.csv` - Results for 12-hour window

### Combined Results
- `backtest_results_all.csv` - All results combined

### Recommendations
- `optimal_parameters.csv` - Top 20 recommended TP/SL combinations

## Interpreting Results

### Key Columns in Results

- **tp_percent / sl_percent**: The tested TP/SL percentages
- **hours_window**: Time window tested (4, 8, or 12 hours)
- **total_trades**: Number of trades that entered
- **wins / losses / expired**: Count of each outcome
- **win_rate**: Percentage of wins
- **expectancy**: Average expected profit per trade (most important!)
- **total_pnl**: Total profit/loss in USDT
- **profit_factor**: Ratio of gross profit to gross loss
- **avg_expired_pnl**: Average PnL of expired trades

### What to Look For

1. **Positive Expectancy**: Most critical metric
2. **High Win Rate**: Generally 50%+ is good
3. **Low Expired Rate**: Too many expired trades indicate unrealistic parameters
4. **Positive Expired PnL**: If trades expire profitably, that's good
5. **High Profit Factor**: >1.5 is considered good

### Optimal Parameters

The system scores combinations based on:
- 40% Expectancy
- 30% Win Rate
- 20% Total PnL
- 10% Expired trades (negative impact)

Top-scored combinations are saved in `optimal_parameters.csv`.

## Example Usage

### Test with Custom Range

Edit `config_backtest.py`:
```python
TP_START = 1.0
TP_END = 3.0
TP_STEP = 0.25

SL_START = 2.0
SL_END = 6.0
SL_STEP = 0.5
```

This tests fewer combinations for faster results.

### Test Single Signal

```python
from backtest_engine import SignalBacktester
import pandas as pd

backtester = SignalBacktester()
signals = pd.read_csv('telegram_signals.csv')

# Test first signal
result = backtester.backtest_signal(
    signals.iloc[0],
    tp_percent=2.0,
    sl_percent=5.0,
    hours_window=4
)

print(result)
```

## Troubleshooting

### No data downloaded
- Check internet connection
- Verify symbol names match Binance (e.g., "BTCUSDT" not "BTC/USDT")
- Some older symbols may not have data

### Too slow
- Reduce testing range in `config_backtest.py`
- Data is cached after first download
- Run on smaller subset first

### Memory issues
- Process signals in batches
- Clear `price_data_cache/` directory periodically

## Notes

- Uses position size of 100 USDT with 20x leverage (configurable)
- All calculations use 1-minute candlestick data
- Conservative fill assumptions (checks high/low of candles)
- Public data only - no authentication needed for Binance API

## Next Steps

After finding optimal parameters:
1. Review `optimal_parameters.csv`
2. Choose combination that fits your risk tolerance
3. Update your trading bot with chosen TP/SL percentages
4. Consider running forward test before live trading
