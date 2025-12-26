"""
Backtesting engine for Telegram trading signals
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from download_price_data import BinancePriceDataDownloader
from config_backtest import (
    DEFAULT_TP_PERCENT,
    DEFAULT_SL_PERCENT,
    TIME_WINDOWS,
    POSITION_SIZE_USDT,
    LEVERAGE,
    USE_BETTER_MARKET_PRICE,
    SIGNAL_TIMEZONE_OFFSET_MINUTES
)


class SignalBacktester:
    def __init__(self):
        self.downloader = BinancePriceDataDownloader()
    
    def calculate_tp_sl_from_csv(self, row, side):
        """
        Extract TP and SL levels from CSV row
        
        Args:
            row: DataFrame row containing signal data
            side (str): 'long' or 'short'
        
        Returns:
            dict: TP levels and SL price
        """
        entry = float(row['entry'])
        
        # Extract TP levels if they exist
        tp_levels = []
        for i in range(1, 5):
            tp_col = f'tp{i}'
            if tp_col in row.index and pd.notna(row[tp_col]):
                tp_levels.append(float(row[tp_col]))
        
        # Extract SL if exists
        sl_price = None
        if 'stop_loss' in row.index and pd.notna(row['stop_loss']):
            sl_price = float(row['stop_loss'])
        
        return {
            'entry': entry,
            'tp_levels': tp_levels,
            'sl_price': sl_price,
            'has_tp': len(tp_levels) > 0,
            'has_sl': sl_price is not None
        }
    
    def calculate_default_tp_sl(self, entry_price, side, tp_percent, sl_percent):
        """
        Calculate TP and SL prices based on percentages
        
        Args:
            entry_price (float): Entry price
            side (str): 'long' or 'short'
            tp_percent (float): Take profit percentage
            sl_percent (float): Stop loss percentage
        
        Returns:
            tuple: (tp_price, sl_price)
        """
        if side.lower() == 'long':
            tp_price = entry_price * (1 + tp_percent / 100)
            sl_price = entry_price * (1 - sl_percent / 100)
        else:  # short
            tp_price = entry_price * (1 - tp_percent / 100)
            sl_price = entry_price * (1 + sl_percent / 100)
        
        return tp_price, sl_price
    
    def get_market_price_at_signal(self, price_data, signal_datetime):
        """
        Get the current market price at signal time
        
        Args:
            price_data (pd.DataFrame): 1-minute OHLCV data
            signal_datetime (datetime): Signal timestamp
        
        Returns:
            float or None: Current market price (close price of the candle at or before signal time)
        """
        # Find the candle at or before signal time
        at_or_before = price_data[price_data['timestamp'] <= signal_datetime]
        
        if at_or_before.empty:
            # If no data before signal, try to get first candle after
            after = price_data[price_data['timestamp'] >= signal_datetime]
            if not after.empty:
                return float(after.iloc[0]['close'])
            return None
        
        # Return close price of the most recent candle before or at signal time
        return float(at_or_before.iloc[-1]['close'])
    
    def select_better_entry_price(self, signal_entry_price, market_price, side):
        """
        Select the better entry price between signal price and market price
        
        Args:
            signal_entry_price (float): Entry price from signal
            market_price (float): Current market price
            side (str): 'long' or 'short'
        
        Returns:
            tuple: (selected_entry_price, used_market_price)
        """
        if market_price is None:
            return signal_entry_price, False
        
        if side.lower() == 'long':
            # For long: market price is better if it's lower (better buy price)
            if market_price < signal_entry_price:
                return market_price, True
        else:  # short
            # For short: market price is better if it's higher (better sell price)
            if market_price > signal_entry_price:
                return market_price, True
        
        return signal_entry_price, False
    
    def check_entry_hit(self, price_data, signal_datetime, entry_price, side):
        """
        Check if entry price was hit and when
        
        Args:
            price_data (pd.DataFrame): 1-minute OHLCV data
            signal_datetime (datetime): Signal timestamp
            entry_price (float): Entry price
            side (str): 'long' or 'short'
        
        Returns:
            dict: Entry information
        """
        # Filter data after signal time
        after_signal = price_data[price_data['timestamp'] >= signal_datetime].copy()
        
        if after_signal.empty:
            return {'hit': False, 'entry_time': None, 'entry_index': None}
        
        # Check if price crossed entry level
        for idx, row in after_signal.iterrows():
            if side.lower() == 'long':
                # For long, entry is hit when price goes down to entry or below
                if row['low'] <= entry_price:
                    return {
                        'hit': True,
                        'entry_time': row['timestamp'],
                        'entry_index': idx,
                        'minutes_to_entry': (row['timestamp'] - signal_datetime).total_seconds() / 60
                    }
            else:  # short
                # For short, entry is hit when price goes up to entry or above
                if row['high'] >= entry_price:
                    return {
                        'hit': True,
                        'entry_time': row['timestamp'],
                        'entry_index': idx,
                        'minutes_to_entry': (row['timestamp'] - signal_datetime).total_seconds() / 60
                    }
        
        return {'hit': False, 'entry_time': None, 'entry_index': None}
    
    def simulate_trade(self, price_data, entry_info, entry_price, tp_price, sl_price, side, hours_limit, tp_levels=None):
        """
        Simulate a trade after entry is filled with partial TP taking and trailing SL
        
        Strategy:
        - TP1: Close 50%, move SL to entry (breakeven)
        - TP2: Close 50% of remaining (25% total), move SL to TP1
        - TP3: Close 50% of remaining (12.5% total), move SL to TP2
        - TP4: Close all remaining (12.5% total), move SL to TP3
        
        Args:
            price_data (pd.DataFrame): 1-minute OHLCV data
            entry_info (dict): Entry information
            entry_price (float): Entry price
            tp_price (float): Take profit price (used if tp_levels is None)
            sl_price (float): Initial stop loss price
            side (str): 'long' or 'short'
            hours_limit (int): Time limit in hours
            tp_levels (list): Optional list of [tp1, tp2, tp3, tp4] prices
        
        Returns:
            dict: Trade result
        """
        if not entry_info['hit']:
            return {
                'result': 'no_entry',
                'pnl': 0,
                'pnl_percent': 0,
                'exit_time': None,
                'bars_in_trade': 0
            }
        
        # Get data after entry
        entry_idx = entry_info['entry_index']
        after_entry = price_data.loc[entry_idx:].copy()
        
        # Calculate time limit
        time_limit = entry_info['entry_time'] + timedelta(hours=hours_limit)
        
        # Initialize position tracking
        remaining_position = 1.0  # 100% of position
        total_pnl = 0
        current_sl = sl_price
        
        # Setup TP strategy
        if tp_levels and len(tp_levels) == 4:
            # Multiple TP levels with partial closes
            tp_targets = [
                {'price': tp_levels[0], 'close_pct': 0.50, 'new_sl': entry_price},  # TP1: close 50%, SL to entry
                {'price': tp_levels[1], 'close_pct': 0.50, 'new_sl': tp_levels[0]},  # TP2: close 50% remaining, SL to TP1
                {'price': tp_levels[2], 'close_pct': 0.50, 'new_sl': tp_levels[1]},  # TP3: close 50% remaining, SL to TP2
                {'price': tp_levels[3], 'close_pct': 1.00, 'new_sl': tp_levels[2]},  # TP4: close all, SL to TP3
            ]
            current_tp_index = 0
        else:
            # Single TP level - close all at once
            tp_targets = [{'price': tp_price, 'close_pct': 1.00, 'new_sl': None}]
            current_tp_index = 0
        
        # Track trade
        for idx, row in after_entry.iloc[1:].iterrows():  # Skip entry candle itself
            # Check if time expired
            if row['timestamp'] > time_limit:
                # Force close remaining position at current price
                exit_price = row['close']
                if side.lower() == 'long':
                    pnl_percent = ((exit_price - entry_price) / entry_price) * 100 * remaining_position
                else:
                    pnl_percent = ((entry_price - exit_price) / entry_price) * 100 * remaining_position
                
                pnl = pnl_percent * POSITION_SIZE_USDT * LEVERAGE / 100
                total_pnl += pnl
                
                return {
                    'result': 'expired',
                    'pnl': total_pnl,
                    'pnl_percent': (total_pnl / POSITION_SIZE_USDT) * 100,
                    'exit_time': row['timestamp'],
                    'exit_price': exit_price,
                    'bars_in_trade': len(after_entry.loc[entry_idx:idx])
                }
            
            # Check stop loss first (trailing SL)
            sl_hit = False
            if side.lower() == 'long':
                if row['low'] <= current_sl:
                    sl_hit = True
            else:  # short
                if row['high'] >= current_sl:
                    sl_hit = True
            
            if sl_hit:
                # Hit stop loss - close remaining position
                if abs(current_sl - entry_price) < 0.0001:  # Breakeven stop
                    pnl = 0
                else:
                    if side.lower() == 'long':
                        pnl_percent = ((current_sl - entry_price) / entry_price) * 100 * remaining_position
                    else:
                        pnl_percent = ((entry_price - current_sl) / entry_price) * 100 * remaining_position
                    pnl = pnl_percent * POSITION_SIZE_USDT * LEVERAGE / 100
                
                total_pnl += pnl
                
                return {
                    'result': 'loss' if total_pnl < 0 else 'win',
                    'pnl': total_pnl,
                    'pnl_percent': (total_pnl / POSITION_SIZE_USDT) * 100,
                    'exit_time': row['timestamp'],
                    'exit_price': current_sl,
                    'bars_in_trade': len(after_entry.loc[entry_idx:idx])
                }
            
            # Check take profit levels
            if current_tp_index < len(tp_targets) and remaining_position > 0:
                tp_target = tp_targets[current_tp_index]
                tp_hit = False
                
                if side.lower() == 'long':
                    if row['high'] >= tp_target['price']:
                        tp_hit = True
                else:  # short
                    if row['low'] <= tp_target['price']:
                        tp_hit = True
                
                if tp_hit:
                    # Hit TP - close specified percentage
                    close_amount = remaining_position * tp_target['close_pct']
                    
                    # Calculate PnL for this partial close
                    if side.lower() == 'long':
                        pnl_percent = ((tp_target['price'] - entry_price) / entry_price) * 100 * close_amount
                    else:
                        pnl_percent = ((entry_price - tp_target['price']) / entry_price) * 100 * close_amount
                    
                    pnl = pnl_percent * POSITION_SIZE_USDT * LEVERAGE / 100
                    total_pnl += pnl
                    
                    # Update remaining position
                    remaining_position -= close_amount
                    
                    # Update stop loss if specified
                    if tp_target['new_sl'] is not None:
                        current_sl = tp_target['new_sl']
                    
                    # Move to next TP level
                    current_tp_index += 1
                    
                    # If all position closed, exit
                    if remaining_position < 0.01:  # Essentially zero
                        return {
                            'result': 'win',
                            'pnl': total_pnl,
                            'pnl_percent': (total_pnl / POSITION_SIZE_USDT) * 100,
                            'exit_time': row['timestamp'],
                            'exit_price': tp_target['price'],
                            'bars_in_trade': len(after_entry.loc[entry_idx:idx])
                        }
        
        # If we reach here, neither TP nor SL was hit within time limit
        # Force close at last available price
        last_row = after_entry.iloc[-1]
        exit_price = last_row['close']
        
        if side.lower() == 'long':
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100 * remaining_position
        else:
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100 * remaining_position
        
        pnl = pnl_percent * POSITION_SIZE_USDT * LEVERAGE / 100
        total_pnl += pnl
        
        return {
            'result': 'expired',
            'pnl': total_pnl,
            'pnl_percent': (total_pnl / POSITION_SIZE_USDT) * 100,
            'exit_time': last_row['timestamp'],
            'exit_price': exit_price,
            'bars_in_trade': len(after_entry)
        }
    
    def backtest_signal(self, signal_row, tp_percent, sl_percent, hours_window, tp_levels=None):
        """
        Backtest a single signal with specific TP/SL percentages
        
        Args:
            signal_row: DataFrame row with signal data
            tp_percent (float): Take profit percentage to test (used if tp_levels is None)
            sl_percent (float): Stop loss percentage to test
            hours_window (int): Time window in hours
            tp_levels (list): Optional list of [tp1, tp2, tp3, tp4] prices from CSV
        
        Returns:
            dict: Backtest result
        """
        symbol = signal_row['symbol']
        side = signal_row['side'].lower()
        
        # Parse signal datetime
        signal_date = pd.to_datetime(signal_row['date'])
        signal_time = pd.to_datetime(signal_row['time'], format='%H:%M').time()
        signal_datetime = datetime.combine(signal_date.date(), signal_time)
        # Convert from SL time (UTC+5:30) to Binance/UTC time
        signal_datetime = signal_datetime - timedelta(minutes=SIGNAL_TIMEZONE_OFFSET_MINUTES)
        
        # Download price data
        try:
            price_data = self.downloader.download_with_cache(
                symbol, 
                signal_datetime, 
                hours_after=max(TIME_WINDOWS) + 1
            )
            
            if price_data.empty:
                return {
                    'status': 'no_data',
                    'symbol': symbol,
                    'signal_datetime': signal_datetime
                }
        except Exception as e:
            return {
                'status': 'error',
                'symbol': symbol,
                'error': str(e)
            }
        
        # Get entry price from signal
        signal_entry_price = float(signal_row['entry'])
        
        # Optionally use better market price if enabled
        market_price = None
        entry_price_decrease_percent = None
        if USE_BETTER_MARKET_PRICE:
            market_price = self.get_market_price_at_signal(price_data, signal_datetime)
            entry_price, used_market_price = self.select_better_entry_price(
                signal_entry_price, market_price, side
            )
            
            # Calculate percentage decrease if entry price changed and market price is lower
            if used_market_price and market_price is not None and market_price < signal_entry_price:
                entry_price_decrease_percent = ((signal_entry_price - market_price) / signal_entry_price) * 100
        else:
            entry_price = signal_entry_price
            used_market_price = False
        
        # Calculate TP and SL based on selected entry price
        tp_price, sl_price = self.calculate_default_tp_sl(entry_price, side, tp_percent, sl_percent)
        
        # Check if entry was hit
        # If we used market price, entry is immediately filled at signal time
        if used_market_price:
            # Find the index of the candle at signal time
            signal_candle = price_data[price_data['timestamp'] <= signal_datetime]
            if not signal_candle.empty:
                entry_idx = signal_candle.index[-1]
                entry_info = {
                    'hit': True,
                    'entry_time': signal_datetime,
                    'entry_index': entry_idx,
                    'minutes_to_entry': 0
                }
            else:
                # Fallback: use first available candle
                first_candle = price_data.iloc[0]
                entry_info = {
                    'hit': True,
                    'entry_time': first_candle['timestamp'],
                    'entry_index': price_data.index[0],
                    'minutes_to_entry': 0
                }
        else:
            entry_info = self.check_entry_hit(price_data, signal_datetime, entry_price, side)
        
        # Simulate trade
        trade_result = self.simulate_trade(
            price_data, 
            entry_info, 
            entry_price, 
            tp_price, 
            sl_price, 
            side, 
            hours_window,
            tp_levels=tp_levels  # Pass TP levels if available
        )
        
        # Combine results
        result = {
            'status': 'completed',
            'symbol': symbol,
            'side': side,
            'signal_datetime': signal_datetime,
            'signal_entry_price': signal_entry_price,
            'entry_price': entry_price,
            'used_market_price': used_market_price if USE_BETTER_MARKET_PRICE else False,
            'entry_price_decrease_percent': entry_price_decrease_percent,
            'tp_percent': tp_percent,
            'sl_percent': sl_percent,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'hours_window': hours_window,
            'entry_hit': entry_info['hit'],
            **trade_result
        }
        
        return result


def main():
    """Test the backtesting engine"""
    backtester = SignalBacktester()
    
    # Load one signal for testing
    signals_df = pd.read_csv('telegram_signals.csv')
    test_signal = signals_df.iloc[0]
    
    print(f"Testing signal: {test_signal['symbol']} - {test_signal['side']}")
    
    # Test with default TP/SL
    result = backtester.backtest_signal(test_signal, DEFAULT_TP_PERCENT, DEFAULT_SL_PERCENT, 4)
    
    print("\nBacktest Result:")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
