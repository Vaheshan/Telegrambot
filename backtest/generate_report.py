"""
Generate detailed FreqTrade-style backtest report
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from tabulate import tabulate


def format_duration(minutes):
    """Format duration in minutes to HH:MM:SS"""
    if pd.isna(minutes) or minutes == 0:
        return "0:00:00"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}:{mins:02d}:00"


def generate_pair_summary(df):
    """Generate summary by trading pair"""
    completed = df[(df['status'] == 'completed') & (df['entry_hit'] == True)].copy()
    
    if len(completed) == 0:
        return None
    
    # Calculate duration in minutes
    completed['duration_minutes'] = completed.apply(
        lambda row: (row['exit_time'] - row['entry_time']).total_seconds() / 60 
        if pd.notna(row.get('exit_time')) and pd.notna(row.get('entry_time')) else 0,
        axis=1
    )
    
    pair_stats = []
    
    for symbol in sorted(completed['symbol'].unique()):
        pair_df = completed[completed['symbol'] == symbol]
        
        wins = len(pair_df[pair_df['result'] == 'win'])
        losses = len(pair_df[pair_df['result'] == 'loss'])
        expired = len(pair_df[pair_df['result'] == 'expired'])
        
        total_pnl = pair_df['pnl'].sum()
        avg_pnl_pct = pair_df['pnl_percent'].mean()
        avg_duration = pair_df['duration_minutes'].mean()
        win_pct = (wins / len(pair_df)) * 100
        
        pair_stats.append({
            'Pair': f"{symbol}:USDT",
            'Trades': len(pair_df),
            'Avg Profit %': round(avg_pnl_pct, 2),
            'Tot Profit USDT': round(total_pnl, 3),
            'Tot Profit %': round(total_pnl / 100, 2),  # Assuming 100 USDT position
            'Avg Duration': format_duration(avg_duration),
            'Win  Draw  Loss  Win%': f"{wins:4d}     0  {losses:4d}  {win_pct:5.1f}"
        })
    
    # Sort by total profit descending
    pair_stats_df = pd.DataFrame(pair_stats).sort_values('Tot Profit USDT', ascending=False)
    
    # Add total row
    total_wins = completed[completed['result'] == 'win'].shape[0]
    total_losses = completed[completed['result'] == 'loss'].shape[0]
    total_expired = completed[completed['result'] == 'expired'].shape[0]
    total_pnl = completed['pnl'].sum()
    avg_pnl_pct = completed['pnl_percent'].mean()
    avg_duration = completed['duration_minutes'].mean()
    win_pct = (total_wins / len(completed)) * 100
    
    total_row = pd.DataFrame([{
        'Pair': 'TOTAL',
        'Trades': len(completed),
        'Avg Profit %': round(avg_pnl_pct, 2),
        'Tot Profit USDT': round(total_pnl, 3),
        'Tot Profit %': round(total_pnl / 100, 2),
        'Avg Duration': format_duration(avg_duration),
        'Win  Draw  Loss  Win%': f"{total_wins:4d}     0  {total_losses:4d}  {win_pct:5.1f}"
    }])
    
    pair_stats_df = pd.concat([pair_stats_df, total_row], ignore_index=True)
    
    return pair_stats_df


def generate_datetime_summary(df):
    """Generate summary by signal datetime (entry tag)"""
    completed = df[(df['status'] == 'completed') & (df['entry_hit'] == True)].copy()
    
    if len(completed) == 0:
        return None
    
    # Add datetime tag
    completed['datetime_tag'] = pd.to_datetime(completed['signal_datetime']).dt.strftime('%Y%m%d%H%M')
    
    # Calculate duration in minutes
    completed['duration_minutes'] = completed.apply(
        lambda row: (row['exit_time'] - row['entry_time']).total_seconds() / 60 
        if pd.notna(row.get('exit_time')) and pd.notna(row.get('entry_time')) else 0,
        axis=1
    )
    
    datetime_stats = []
    
    for dt_tag in sorted(completed['datetime_tag'].unique()):
        dt_df = completed[completed['datetime_tag'] == dt_tag]
        
        wins = len(dt_df[dt_df['result'] == 'win'])
        losses = len(dt_df[dt_df['result'] == 'loss'])
        
        total_pnl = dt_df['pnl'].sum()
        avg_pnl_pct = dt_df['pnl_percent'].mean()
        avg_duration = dt_df['duration_minutes'].mean()
        win_pct = (wins / len(dt_df)) * 100
        
        datetime_stats.append({
            'Enter Tag': dt_tag,
            'Entries': len(dt_df),
            'Avg Profit %': round(avg_pnl_pct, 2),
            'Tot Profit USDT': round(total_pnl, 3),
            'Tot Profit %': round(total_pnl / 100, 2),
            'Avg Duration': format_duration(avg_duration),
            'Win  Draw  Loss  Win%': f"{wins:4d}     0  {losses:4d}  {win_pct:5.1f}"
        })
    
    # Sort by total profit descending
    datetime_stats_df = pd.DataFrame(datetime_stats).sort_values('Tot Profit USDT', ascending=False)
    
    # Add total
    total_wins = completed[completed['result'] == 'win'].shape[0]
    total_losses = completed[completed['result'] == 'loss'].shape[0]
    total_pnl = completed['pnl'].sum()
    avg_pnl_pct = completed['pnl_percent'].mean()
    avg_duration = completed['duration_minutes'].mean()
    win_pct = (total_wins / len(completed)) * 100
    
    total_row = pd.DataFrame([{
        'Enter Tag': 'TOTAL',
        'Entries': len(completed),
        'Avg Profit %': round(avg_pnl_pct, 2),
        'Tot Profit USDT': round(total_pnl, 3),
        'Tot Profit %': round(total_pnl / 100, 2),
        'Avg Duration': format_duration(avg_duration),
        'Win  Draw  Loss  Win%': f"{total_wins:4d}     0  {total_losses:4d}  {win_pct:5.1f}"
    }])
    
    datetime_stats_df = pd.concat([datetime_stats_df, total_row], ignore_index=True)
    
    return datetime_stats_df


def generate_exit_reason_summary(df):
    """Generate summary by exit reason"""
    completed = df[(df['status'] == 'completed') & (df['entry_hit'] == True)].copy()
    
    if len(completed) == 0:
        return None
    
    # Calculate duration in minutes
    completed['duration_minutes'] = completed.apply(
        lambda row: (row['exit_time'] - row['entry_time']).total_seconds() / 60 
        if pd.notna(row.get('exit_time')) and pd.notna(row.get('entry_time')) else 0,
        axis=1
    )
    
    # Map results to exit reasons
    completed['exit_reason'] = completed['result'].map({
        'win': 'roi',
        'loss': 'stop_loss',
        'expired': f"{completed['hours_window'].iloc[0]}h_timeout"
    })
    
    exit_stats = []
    
    for reason in ['roi', 'stop_loss', f"{completed['hours_window'].iloc[0]}h_timeout"]:
        reason_df = completed[completed['exit_reason'] == reason]
        
        if len(reason_df) == 0:
            continue
        
        wins = len(reason_df[reason_df['result'] == 'win'])
        losses = len(reason_df[reason_df['result'] == 'loss'])
        expired = len(reason_df[reason_df['result'] == 'expired'])
        
        total_pnl = reason_df['pnl'].sum()
        avg_pnl_pct = reason_df['pnl_percent'].mean()
        avg_duration = reason_df['duration_minutes'].mean()
        win_pct = (wins / len(reason_df)) * 100 if len(reason_df) > 0 else 0
        
        exit_stats.append({
            'Exit Reason': reason,
            'Exits': len(reason_df),
            'Avg Profit %': round(avg_pnl_pct, 2),
            'Tot Profit USDT': round(total_pnl, 3),
            'Tot Profit %': round(total_pnl / 100, 2),
            'Avg Duration': format_duration(avg_duration),
            'Win  Draw  Loss  Win%': f"{wins:4d}     0  {losses:4d}  {win_pct:5.1f}"
        })
    
    exit_stats_df = pd.DataFrame(exit_stats)
    
    # Add total
    total_wins = completed[completed['result'] == 'win'].shape[0]
    total_losses = completed[completed['result'] == 'loss'].shape[0]
    total_expired = completed[completed['result'] == 'expired'].shape[0]
    total_pnl = completed['pnl'].sum()
    avg_pnl_pct = completed['pnl_percent'].mean()
    avg_duration = completed['duration_minutes'].mean()
    win_pct = (total_wins / len(completed)) * 100
    
    total_row = pd.DataFrame([{
        'Exit Reason': 'TOTAL',
        'Exits': len(completed),
        'Avg Profit %': round(avg_pnl_pct, 2),
        'Tot Profit USDT': round(total_pnl, 3),
        'Tot Profit %': round(total_pnl / 100, 2),
        'Avg Duration': format_duration(avg_duration),
        'Win  Draw  Loss  Win%': f"{total_wins:4d}     0  {total_losses:4d}  {win_pct:5.1f}"
    }])
    
    exit_stats_df = pd.concat([exit_stats_df, total_row], ignore_index=True)
    
    return exit_stats_df


def generate_summary_metrics(df, initial_balance=1000):
    """Generate overall summary metrics"""
    completed = df[(df['status'] == 'completed') & (df['entry_hit'] == True)].copy()
    
    if len(completed) == 0:
        return None
    
    # Calculate duration in minutes
    completed['duration_minutes'] = completed.apply(
        lambda row: (row['exit_time'] - row['entry_time']).total_seconds() / 60 
        if pd.notna(row.get('exit_time')) and pd.notna(row.get('entry_time')) else 0,
        axis=1
    )
    
    # Calculate metrics
    total_trades = len(completed)
    wins = completed[completed['result'] == 'win']
    losses = completed[completed['result'] == 'loss']
    
    total_pnl = completed['pnl'].sum()
    final_balance = initial_balance + total_pnl
    total_profit_pct = (total_pnl / initial_balance) * 100
    
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    
    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
    
    profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else 0
    
    # Best/worst trades
    best_trade = completed.loc[completed['pnl'].idxmax()] if len(completed) > 0 else None
    worst_trade = completed.loc[completed['pnl'].idxmin()] if len(completed) > 0 else None
    
    # Duration stats
    avg_duration = completed['duration_minutes'].mean()
    avg_duration_winners = wins['duration_minutes'].mean() if len(wins) > 0 else 0
    avg_duration_losers = losses['duration_minutes'].mean() if len(losses) > 0 else 0
    
    # Long/Short breakdown
    longs = completed[completed['side'] == 'long']
    shorts = completed[completed['side'] == 'short']
    
    long_wins = longs[longs['result'] == 'win']
    long_losses = longs[longs['result'] == 'loss']
    long_expired = longs[longs['result'] == 'expired']
    
    short_wins = shorts[shorts['result'] == 'win']
    short_losses = shorts[shorts['result'] == 'loss']
    short_expired = shorts[shorts['result'] == 'expired']
    
    long_pnl = longs['pnl'].sum()
    short_pnl = shorts['pnl'].sum()
    
    long_win_rate = (len(long_wins) / len(longs) * 100) if len(longs) > 0 else 0
    short_win_rate = (len(short_wins) / len(shorts) * 100) if len(shorts) > 0 else 0
    
    # Get final balance from last trade
    final_balance = initial_balance + total_pnl
    if 'balance_after_trade' in completed.columns:
        final_balance = completed['balance_after_trade'].iloc[-1]
    
    metrics = {
        'Total Trades': total_trades,
        'Total Signals': len(df),
        'Entry Fill Rate %': round((total_trades / len(df)) * 100, 2),
        'Skipped (Insufficient Balance)': len(df[df['status'] == 'insufficient_balance']) if 'status' in df.columns else 0,
        'Starting Balance': f"{initial_balance} USDT",
        'Final Balance': f"{final_balance:.2f} USDT",
        'Absolute Profit': f"{total_pnl:.2f} USDT",
        'Total Profit %': f"{total_profit_pct:.2f}%",
        'Win Rate %': f"{win_rate:.2f}%",
        'Wins / Losses / Expired': f"{len(wins)} / {len(losses)} / {len(completed[completed['result'] == 'expired'])}",
        'Profit Factor': round(profit_factor, 2),
        'Avg Win': f"{avg_win:.2f} USDT",
        'Avg Loss': f"{avg_loss:.2f} USDT",
        'Avg Duration': format_duration(avg_duration),
        'Avg Duration Winners': format_duration(avg_duration_winners),
        'Avg Duration Losers': format_duration(avg_duration_losers),
        '': '',  # Separator
        'LONG TRADES': '─'*30,
        'Long Total': len(longs),
        'Long Wins / Losses / Expired': f"{len(long_wins)} / {len(long_losses)} / {len(long_expired)}",
        'Long Win Rate %': f"{long_win_rate:.2f}%",
        'Long Profit': f"{long_pnl:.2f} USDT",
        'Long Avg Win': f"{long_wins['pnl'].mean():.2f} USDT" if len(long_wins) > 0 else "0.00 USDT",
        'Long Avg Loss': f"{long_losses['pnl'].mean():.2f} USDT" if len(long_losses) > 0 else "0.00 USDT",
        ' ': '',  # Separator
        'SHORT TRADES': '─'*30,
        'Short Total': len(shorts),
        'Short Wins / Losses / Expired': f"{len(short_wins)} / {len(short_losses)} / {len(short_expired)}",
        'Short Win Rate %': f"{short_win_rate:.2f}%",
        'Short Profit': f"{short_pnl:.2f} USDT",
        'Short Avg Win': f"{short_wins['pnl'].mean():.2f} USDT" if len(short_wins) > 0 else "0.00 USDT",
        'Short Avg Loss': f"{short_losses['pnl'].mean():.2f} USDT" if len(short_losses) > 0 else "0.00 USDT",
        '  ': '',  # Separator
        'Best Trade': f"{best_trade['symbol']} {best_trade['pnl_percent']:.2f}%" if best_trade is not None else "N/A",
        'Worst Trade': f"{worst_trade['symbol']} {worst_trade['pnl_percent']:.2f}%" if worst_trade is not None else "N/A",
    }
    
    return metrics


def print_report(csv_file):
    """Generate and print complete report"""
    df = pd.read_csv(csv_file)
    
    # Convert datetime columns
    datetime_cols = ['signal_datetime', 'entry_time', 'exit_time']
    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    hours_window = df['hours_window'].iloc[0] if 'hours_window' in df.columns else 'Unknown'
    
    print("\n" + "="*100)
    print(f"BACKTESTING REPORT - {hours_window}h Window".center(100))
    print("="*100)
    
    # Pair Summary
    print("\n" + "PAIR PERFORMANCE".center(100))
    print("-"*100)
    pair_summary = generate_pair_summary(df)
    if pair_summary is not None:
        print(tabulate(pair_summary, headers='keys', tablefmt='simple', showindex=False))
    
    # Exit Reason Summary
    print("\n" + "EXIT REASON STATS".center(100))
    print("-"*100)
    exit_summary = generate_exit_reason_summary(df)
    if exit_summary is not None:
        print(tabulate(exit_summary, headers='keys', tablefmt='simple', showindex=False))
    
    # DateTime Summary (top 20 and bottom 10)
    print("\n" + "ENTER TAG STATS (Top 20 Best + Bottom 10 Worst)".center(100))
    print("-"*100)
    datetime_summary = generate_datetime_summary(df)
    if datetime_summary is not None:
        top_20 = datetime_summary.head(20)
        bottom_10 = datetime_summary[datetime_summary['Enter Tag'] != 'TOTAL'].tail(10)
        total = datetime_summary[datetime_summary['Enter Tag'] == 'TOTAL']
        display_df = pd.concat([top_20, bottom_10, total])
        print(tabulate(display_df, headers='keys', tablefmt='simple', showindex=False))
    
    # Summary Metrics
    print("\n" + "SUMMARY METRICS".center(100))
    print("-"*100)
    metrics = generate_summary_metrics(df)
    if metrics is not None:
        metrics_table = [[k, v] for k, v in metrics.items()]
        print(tabulate(metrics_table, tablefmt='simple', showindex=False))
    
    print("\n" + "="*100 + "\n")


def main():
    """Generate reports for all result files"""
    results_dir = "backtest_results"
    
    for hours in [4, 8, 12]:
        csv_file = os.path.join(results_dir, f"simple_backtest_{hours}h.csv")
        
        if os.path.exists(csv_file):
            print_report(csv_file)
        else:
            print(f"\nFile not found: {csv_file}")


if __name__ == "__main__":
    main()
