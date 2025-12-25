"""
Simple backtest - uses TP/SL from CSV, no optimization
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from backtest_engine import SignalBacktester
from config_backtest import (
    CSV_INPUT_FILE,
    RESULTS_OUTPUT_DIR,
    DEFAULT_TP_PERCENT,
    DEFAULT_SL_PERCENT,
    TIME_WINDOWS,
    MAX_CONCURRENT_POSITIONS
)


def backtest_single_signal_wrapper(args):
    """Wrapper for parallel processing"""
    idx, signal, hours_window = args
    backtester = SignalBacktester()
    
    symbol = signal['symbol']
    side = signal['side'].lower()
    entry_price = float(signal['entry'])
    
    # Check if CSV has TP/SL values
    has_tp = all(pd.notna(signal.get(f'tp{i}')) for i in range(1, 5))
    has_sl = pd.notna(signal.get('stop_loss'))
    
    if has_tp and has_sl:
        # Use CSV values - pass all 4 TP levels
        tp_prices = [float(signal[f'tp{i}']) for i in range(1, 5)]
        sl_price = float(signal['stop_loss'])
        
        # Calculate percentages from prices (for reporting purposes)
        if side == 'long':
            avg_tp = np.mean(tp_prices)
            tp_percent = ((avg_tp - entry_price) / entry_price) * 100
            sl_percent = ((entry_price - sl_price) / entry_price) * 100
        else:  # short
            avg_tp = np.mean(tp_prices)
            tp_percent = ((entry_price - avg_tp) / entry_price) * 100
            sl_percent = ((sl_price - entry_price) / entry_price) * 100
        
        # Run backtest with TP levels
        result = backtester.backtest_signal(signal, tp_percent, sl_percent, hours_window, tp_levels=tp_prices)
    else:
        # Use defaults
        tp_percent = DEFAULT_TP_PERCENT
        sl_percent = DEFAULT_SL_PERCENT
        
        # Run backtest without TP levels (single TP)
        result = backtester.backtest_signal(signal, tp_percent, sl_percent, hours_window)
    
    result['has_csv_tpsl'] = has_tp and has_sl
    result['signal_index'] = idx
    
    return result


def main():
    print("\n" + "="*60)
    print("SIMPLE BACKTEST - Using CSV TP/SL Values")
    print("="*60)
    
    # Load signals
    signals_df = pd.read_csv(CSV_INPUT_FILE)
    
    # Sort by datetime for chronological processing
    signals_df['datetime'] = pd.to_datetime(signals_df['date'] + ' ' + signals_df['time'])
    signals_df = signals_df.sort_values('datetime').reset_index(drop=True)
    
    print(f"\nLoaded {len(signals_df)} signals")
    print(f"Date range: {signals_df['date'].min()} to {signals_df['date'].max()}")
    print(f"Long signals: {len(signals_df[signals_df['side'] == 'long'])}")
    print(f"Short signals: {len(signals_df[signals_df['side'] == 'short'])}")
    
    # Count signals with TP/SL
    has_tpsl = signals_df.apply(
        lambda row: all(pd.notna(row.get(f'tp{i}')) for i in range(1, 5)) and pd.notna(row.get('stop_loss')),
        axis=1
    )
    print(f"\nSignals with TP/SL in CSV: {has_tpsl.sum()}")
    print(f"Signals using defaults ({DEFAULT_TP_PERCENT}% TP, {DEFAULT_SL_PERCENT}% SL): {len(signals_df) - has_tpsl.sum()}")
    
    os.makedirs(RESULTS_OUTPUT_DIR, exist_ok=True)
    
    # Test each time window
    for hours_window in TIME_WINDOWS:
        print(f"\n{'='*60}")
        print(f"Testing {hours_window}-hour window")
        print(f"{'='*60}")
        
        # Initialize balance tracking
        STARTING_BALANCE = 1000  # USDT
        current_balance = STARTING_BALANCE
        
        results = []
        signal_updates = 0
        last_signal_time = {}  # Track last signal time per symbol for update detection
        
        # Track open positions for concurrent position limit
        open_positions = {}  # {symbol: {'entry_time': datetime, 'signal_index': idx}}
        
        # Process signals sequentially in chronological order for proper balance tracking
        for idx, signal in tqdm(signals_df.iterrows(), total=len(signals_df), desc=f"Backtesting {hours_window}h", ncols=100):
            symbol = signal['symbol']
            signal_time = signal['datetime']
            
            # Check for signal update (new signal for same symbol within time window)
            if symbol in last_signal_time:
                time_diff = (signal_time - last_signal_time[symbol]).total_seconds() / 3600  # hours
                if time_diff <= hours_window:
                    signal_updates += 1
            
            last_signal_time[symbol] = signal_time
            
            # Check if we've reached max concurrent positions limit
            if len(open_positions) >= MAX_CONCURRENT_POSITIONS:
                # Check if any open positions have closed by this time
                # (positions close when their trade completes)
                # We'll mark positions as closed after processing results
                results.append({
                    'status': 'max_positions_reached',
                    'symbol': signal['symbol'],
                    'side': signal['side'],
                    'signal_index': idx,
                    'open_positions_count': len(open_positions)
                })
                continue
            
            # Check if we have enough balance to trade
            if current_balance < 50:  # POSITION_SIZE_USDT = 50
                # Not enough balance, record as skipped
                results.append({
                    'status': 'insufficient_balance',
                    'symbol': signal['symbol'],
                    'side': signal['side'],
                    'signal_index': idx,
                    'balance_at_signal': current_balance
                })
                continue
            
            # Backtest this signal
            try:
                result = backtest_single_signal_wrapper((idx, signal, hours_window))
                
                # Update balance based on result
                if result.get('status') == 'completed' and result.get('entry_hit'):
                    # Add to open positions when entry is hit
                    entry_time = result.get('entry_time')
                    if entry_time:
                        open_positions[symbol] = {'entry_time': entry_time, 'signal_index': idx}
                    
                    # Calculate when position closes
                    exit_time = result.get('exit_time')
                    
                    # Remove from open positions when trade exits
                    if exit_time and symbol in open_positions:
                        del open_positions[symbol]
                    
                    pnl = result.get('pnl', 0)
                    current_balance += pnl
                    result['balance_after_trade'] = current_balance
                
                results.append(result)
            except Exception as e:
                results.append({
                    'status': 'error',
                    'symbol': signal['symbol'],
                    'error': str(e),
                    'signal_index': idx
                })
        
        # Create results DataFrame
        results_df = pd.DataFrame(results)
        
        # Filter completed trades
        completed = results_df[
            (results_df['status'] == 'completed') & 
            (results_df['entry_hit'] == True)
        ]
        
        if len(completed) == 0:
            print(f"\nNo completed trades for {hours_window}h window!")
            continue
        
        # Calculate statistics
        wins = completed[completed['result'] == 'win']
        losses = completed[completed['result'] == 'loss']
        expired = completed[completed['result'] == 'expired']
        
        # Long/Short breakdowns
        long_trades = completed[completed['side'] == 'long']
        short_trades = completed[completed['side'] == 'short']
        
        long_wins = long_trades[long_trades['result'] == 'win']
        long_losses = long_trades[long_trades['result'] == 'loss']
        long_expired = long_trades[long_trades['result'] == 'expired']
        
        short_wins = short_trades[short_trades['result'] == 'win']
        short_losses = short_trades[short_trades['result'] == 'loss']
        short_expired = short_trades[short_trades['result'] == 'expired']
        
        total_pnl = completed['pnl'].sum()
        avg_pnl = completed['pnl'].mean()
        win_rate = len(wins) / len(completed) * 100
        
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        
        # Calculate Expectancy: (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        win_rate_decimal = len(wins) / len(completed) if len(completed) > 0 else 0
        loss_rate_decimal = len(losses) / len(completed) if len(completed) > 0 else 0
        expectancy = (win_rate_decimal * avg_win) - (loss_rate_decimal * abs(avg_loss))
        
        profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else 0
        
        # Statistics by source (CSV vs defaults)
        csv_trades = completed[completed['has_csv_tpsl'] == True]
        default_trades = completed[completed['has_csv_tpsl'] == False]
        
        # Count insufficient balance cases
        insufficient_balance_count = len(results_df[results_df['status'] == 'insufficient_balance'])
        
        # Count max positions reached cases
        max_positions_count = len(results_df[results_df['status'] == 'max_positions_reached'])
        
        print(f"\n{'='*60}")
        print(f"RESULTS - {hours_window}-hour window")
        print(f"{'='*60}")
        print(f"\nStarting Balance: ${STARTING_BALANCE:.2f}")
        print(f"Final Balance: ${current_balance:.2f}")
        print(f"Total PnL: ${total_pnl:.2f}")
        print(f"Return: {(total_pnl / STARTING_BALANCE * 100):.2f}%")
        
        print(f"\nTotal signals: {len(signals_df)}")
        print(f"Signal updates detected: {signal_updates} (within {hours_window}h window)")
        print(f"Entries filled: {len(completed)} ({len(completed)/len(signals_df)*100:.1f}%)")
        if insufficient_balance_count > 0:
            print(f"Skipped (insufficient balance): {insufficient_balance_count}")
        if max_positions_count > 0:
            print(f"Skipped (max {MAX_CONCURRENT_POSITIONS} positions reached): {max_positions_count}")
        
        print(f"\nOVERALL STATS:")
        print(f"Wins: {len(wins)} ({len(wins)/len(completed)*100:.1f}%)")
        print(f"Losses: {len(losses)} ({len(losses)/len(completed)*100:.1f}%)")
        print(f"Expired: {len(expired)} ({len(expired)/len(completed)*100:.1f}%)")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Average Win: ${avg_win:.2f}")
        print(f"Average Loss: ${avg_loss:.2f}")
        print(f"Expectancy: ${expectancy:.2f} per trade")
        print(f"Profit Factor: {profit_factor:.2f}")
        
        print(f"\nLONG TRADES ({len(long_trades)} total):")
        print(f"Wins: {len(long_wins)} | Losses: {len(long_losses)} | Expired: {len(long_expired)}")
        long_wr = len(long_wins)/len(long_trades)*100 if len(long_trades) > 0 else 0
        long_pnl = long_trades['pnl'].sum()
        long_avg_win = long_wins['pnl'].mean() if len(long_wins) > 0 else 0
        long_avg_loss = long_losses['pnl'].mean() if len(long_losses) > 0 else 0
        long_expectancy = (len(long_wins)/len(long_trades)*long_avg_win) - (len(long_losses)/len(long_trades)*abs(long_avg_loss)) if len(long_trades) > 0 else 0
        print(f"Win Rate: {long_wr:.1f}% | PnL: ${long_pnl:.2f}")
        print(f"Expectancy: ${long_expectancy:.2f} per trade")
        
        print(f"\nSHORT TRADES ({len(short_trades)} total):")
        print(f"Wins: {len(short_wins)} | Losses: {len(short_losses)} | Expired: {len(short_expired)}")
        short_wr = len(short_wins)/len(short_trades)*100 if len(short_trades) > 0 else 0
        short_pnl = short_trades['pnl'].sum()
        short_avg_win = short_wins['pnl'].mean() if len(short_wins) > 0 else 0
        short_avg_loss = short_losses['pnl'].mean() if len(short_losses) > 0 else 0
        short_expectancy = (len(short_wins)/len(short_trades)*short_avg_win) - (len(short_losses)/len(short_trades)*abs(short_avg_loss)) if len(short_trades) > 0 else 0
        print(f"Win Rate: {short_wr:.1f}% | PnL: ${short_pnl:.2f}")
        print(f"Expectancy: ${short_expectancy:.2f} per trade")
        
        if len(csv_trades) > 0:
            csv_win_rate = len(csv_trades[csv_trades['result'] == 'win']) / len(csv_trades) * 100
            csv_pnl = csv_trades['pnl'].sum()
            print(f"\nCSV TP/SL trades: {len(csv_trades)} | Win Rate: {csv_win_rate:.1f}% | PnL: ${csv_pnl:.2f}")
        
        if len(default_trades) > 0:
            default_win_rate = len(default_trades[default_trades['result'] == 'win']) / len(default_trades) * 100
            default_pnl = default_trades['pnl'].sum()
            print(f"Default TP/SL trades: {len(default_trades)} | Win Rate: {default_win_rate:.1f}% | PnL: ${default_pnl:.2f}")
        
        # Save results
        output_file = os.path.join(RESULTS_OUTPUT_DIR, f"simple_backtest_{hours_window}h.csv")
        results_df.to_csv(output_file, index=False)
        print(f"\nDetailed results saved to: {output_file}")
    
    print("\n" + "="*60)
    print("BACKTEST COMPLETED!")
    print(f"Results saved in '{RESULTS_OUTPUT_DIR}' directory")
    print("="*60)


if __name__ == "__main__":
    main()
