"""
Main script to run comprehensive backtest on all signals
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from backtest_engine import SignalBacktester
from config_backtest import (
    CSV_INPUT_FILE,
    RESULTS_OUTPUT_DIR,
    TP_START, TP_END, TP_STEP,
    SL_START, SL_END, SL_STEP,
    TIME_WINDOWS
)


class ComprehensiveBacktest:
    def __init__(self):
        self.backtester = SignalBacktester()
        os.makedirs(RESULTS_OUTPUT_DIR, exist_ok=True)
    
    def load_signals(self):
        """Load signals from CSV"""
        df = pd.read_csv(CSV_INPUT_FILE)
        print(f"Loaded {len(df)} signals")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"Long signals: {len(df[df['side'] == 'long'])}")
        print(f"Short signals: {len(df[df['side'] == 'short'])}")
        return df
    
    def generate_tp_sl_combinations(self):
        """Generate all TP/SL percentage combinations to test"""
        tp_values = np.arange(TP_START, TP_END + TP_STEP, TP_STEP)
        sl_values = np.arange(SL_START, SL_END + SL_STEP, SL_STEP)
        
        combinations = []
        for tp in tp_values:
            for sl in sl_values:
                combinations.append((round(tp, 2), round(sl, 2)))
        
        print(f"\nGenerated {len(combinations)} TP/SL combinations")
        print(f"TP range: {TP_START}% to {TP_END}% (step {TP_STEP}%)")
        print(f"SL range: {SL_START}% to {SL_END}% (step {SL_STEP}%)")
        
        return combinations
    
    def backtest_single_signal(self, args):
        """Helper function for parallel processing"""
        signal, tp_percent, sl_percent, hours_window = args
        backtester = SignalBacktester()
        return backtester.backtest_signal(signal, tp_percent, sl_percent, hours_window)
    
    def run_single_combination(self, signals_df, tp_percent, sl_percent, hours_window):
        """
        Run backtest for all signals with a specific TP/SL combination (parallelized)
        
        Args:
            signals_df (pd.DataFrame): All signals
            tp_percent (float): Take profit percentage
            sl_percent (float): Stop loss percentage
            hours_window (int): Time window in hours
        
        Returns:
            dict: Aggregated results
        """
        results = []
        
        # Prepare arguments for parallel processing
        args_list = [
            (signal, tp_percent, sl_percent, hours_window) 
            for idx, signal in signals_df.iterrows()
        ]
        
        # Use ThreadPoolExecutor for I/O-bound operations (reading cached files)
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self.backtest_single_signal, args) for args in args_list]
            
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # Skip failed signals
                    pass
        
        # Aggregate statistics
        completed_trades = [r for r in results if r.get('status') == 'completed' and r.get('entry_hit')]
        
        if not completed_trades:
            return {
                'tp_percent': tp_percent,
                'sl_percent': sl_percent,
                'hours_window': hours_window,
                'total_signals': len(signals_df),
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'expired': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'expectancy': 0
            }
        
        wins = [r for r in completed_trades if r['result'] == 'win']
        losses = [r for r in completed_trades if r['result'] == 'loss']
        expired = [r for r in completed_trades if r['result'] == 'expired']
        
        total_pnl = sum(r['pnl'] for r in completed_trades)
        avg_pnl = total_pnl / len(completed_trades) if completed_trades else 0
        
        win_rate = len(wins) / len(completed_trades) * 100 if completed_trades else 0
        
        # Calculate expectancy
        avg_win = np.mean([r['pnl'] for r in wins]) if wins else 0
        avg_loss = np.mean([r['pnl'] for r in losses]) if losses else 0
        win_prob = len(wins) / len(completed_trades) if completed_trades else 0
        loss_prob = len(losses) / len(completed_trades) if completed_trades else 0
        expectancy = (win_prob * avg_win) + (loss_prob * avg_loss)
        
        # Expired trades analysis
        expired_pnl = sum(r['pnl'] for r in expired)
        avg_expired_pnl = expired_pnl / len(expired) if expired else 0
        
        return {
            'tp_percent': tp_percent,
            'sl_percent': sl_percent,
            'hours_window': hours_window,
            'total_signals': len(signals_df),
            'total_trades': len(completed_trades),
            'entry_hit_rate': len(completed_trades) / len(signals_df) * 100,
            'wins': len(wins),
            'losses': len(losses),
            'expired': len(expired),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'expectancy': expectancy,
            'expired_pnl': expired_pnl,
            'avg_expired_pnl': avg_expired_pnl,
            'profit_factor': abs(sum(r['pnl'] for r in wins) / sum(r['pnl'] for r in losses)) if losses and sum(r['pnl'] for r in losses) != 0 else 0
        }
    
    def run_full_backtest(self):
        """Run backtest for all combinations"""
        print("\n" + "="*60)
        print("STARTING COMPREHENSIVE BACKTEST")
        print("="*60)
        
        # Load signals
        signals_df = self.load_signals()
        
        # Generate combinations
        combinations = self.generate_tp_sl_combinations()
        
        # Run backtest for each time window
        all_results = []
        
        for hours_window in TIME_WINDOWS:
            print(f"\n{'='*60}")
            print(f"Testing {hours_window}-hour window")
            print(f"{'='*60}")
            
            window_results = []
            
            # Progress bar for combinations
            pbar = tqdm(combinations, desc=f"{hours_window}h window", ncols=100)
            for tp_percent, sl_percent in pbar:
                pbar.set_postfix({'TP': f'{tp_percent}%', 'SL': f'{sl_percent}%'})
                result = self.run_single_combination(signals_df, tp_percent, sl_percent, hours_window)
                window_results.append(result)
                all_results.append(result)
            
            # Save results for this window
            window_df = pd.DataFrame(window_results)
            window_filename = f"backtest_results_{hours_window}h.csv"
            window_path = os.path.join(RESULTS_OUTPUT_DIR, window_filename)
            window_df.to_csv(window_path, index=False)
            print(f"\nSaved results to {window_path}")
            
            # Show top 10 by expectancy
            top_10 = window_df.nlargest(10, 'expectancy')
            print(f"\nTop 10 combinations by expectancy ({hours_window}h window):")
            print(top_10[['tp_percent', 'sl_percent', 'wins', 'losses', 'expired', 'win_rate', 'expectancy', 'total_pnl']].to_string(index=False))
        
        # Save all results
        all_results_df = pd.DataFrame(all_results)
        all_results_path = os.path.join(RESULTS_OUTPUT_DIR, "backtest_results_all.csv")
        all_results_df.to_csv(all_results_path, index=False)
        print(f"\n{'='*60}")
        print(f"All results saved to {all_results_path}")
        print(f"{'='*60}")
        
        return all_results_df
    
    def find_optimal_parameters(self, results_df):
        """
        Find optimal TP/SL parameters based on multiple criteria
        
        Args:
            results_df (pd.DataFrame): All backtest results
        
        Returns:
            pd.DataFrame: Top recommendations
        """
        print("\n" + "="*60)
        print("FINDING OPTIMAL PARAMETERS")
        print("="*60)
        
        # Filter for combinations with reasonable metrics
        filtered = results_df[
            (results_df['total_trades'] >= 10) &  # At least 10 trades
            (results_df['win_rate'] >= 40) &  # At least 40% win rate
            (results_df['expectancy'] > 0)  # Positive expectancy
        ].copy()
        
        if filtered.empty:
            print("No combinations met the filtering criteria!")
            return results_df.nlargest(10, 'expectancy')
        
        # Score combinations
        # Higher expectancy, higher win rate, fewer expired trades, higher total PnL
        filtered['score'] = (
            filtered['expectancy'] * 0.4 +
            filtered['win_rate'] * 0.3 +
            filtered['total_pnl'] * 0.2 -
            (filtered['expired'] / filtered['total_trades'] * 100) * 0.1
        )
        
        # Get top 20
        top_20 = filtered.nlargest(20, 'score')
        
        print("\nTop 20 optimal parameter combinations:")
        print(top_20[[
            'tp_percent', 'sl_percent', 'hours_window', 
            'wins', 'losses', 'expired', 'win_rate', 
            'expectancy', 'total_pnl', 'profit_factor', 'score'
        ]].to_string(index=False))
        
        # Save recommendations
        recommendations_path = os.path.join(RESULTS_OUTPUT_DIR, "optimal_parameters.csv")
        top_20.to_csv(recommendations_path, index=False)
        print(f"\nOptimal parameters saved to {recommendations_path}")
        
        return top_20


def main():
    """Run the comprehensive backtest"""
    backtest = ComprehensiveBacktest()
    
    # Run full backtest
    results_df = backtest.run_full_backtest()
    
    # Find optimal parameters
    optimal = backtest.find_optimal_parameters(results_df)
    
    print("\n" + "="*60)
    print("BACKTEST COMPLETED SUCCESSFULLY!")
    print("="*60)
    print(f"\nResults saved in '{RESULTS_OUTPUT_DIR}' directory")
    print("\nReview the following files:")
    print(f"  - backtest_results_4h.csv (4-hour window results)")
    print(f"  - backtest_results_8h.csv (8-hour window results)")
    print(f"  - backtest_results_12h.csv (12-hour window results)")
    print(f"  - backtest_results_all.csv (all results combined)")
    print(f"  - optimal_parameters.csv (top 20 recommended combinations)")


if __name__ == "__main__":
    main()
