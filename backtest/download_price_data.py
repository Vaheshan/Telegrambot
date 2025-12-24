"""
Download historical 1-minute OHLCV data from Binance Futures API
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from config_backtest import (
    BINANCE_FUTURES_BASE_URL,
    MAX_KLINES_PER_REQUEST,
    DATA_CACHE_DIR
)


class BinancePriceDataDownloader:
    def __init__(self):
        self.base_url = BINANCE_FUTURES_BASE_URL
        os.makedirs(DATA_CACHE_DIR, exist_ok=True)
    
    def get_klines(self, symbol, interval, start_time, end_time):
        """
        Fetch klines (candlestick data) from Binance Futures API
        
        Args:
            symbol (str): Trading pair (e.g., 'BTCUSDT')
            interval (str): Kline interval (e.g., '1m')
            start_time (int): Start timestamp in milliseconds
            end_time (int): End timestamp in milliseconds
        
        Returns:
            list: List of klines
        """
        endpoint = f"{self.base_url}/fapi/v1/klines"
        
        all_klines = []
        current_start = start_time
        
        while current_start < end_time:
            params = {
                'symbol': symbol,
                'interval': interval,
                'startTime': current_start,
                'endTime': end_time,
                'limit': MAX_KLINES_PER_REQUEST
            }
            
            try:
                response = requests.get(endpoint, params=params)
                response.raise_for_status()
                klines = response.json()
                
                if not klines:
                    break
                
                all_klines.extend(klines)
                
                # Update start time for next request
                current_start = klines[-1][0] + 1
                
                # Rate limiting
                time.sleep(0.1)
                
            except requests.exceptions.RequestException as e:
                # Skip error printing for now, will be handled by caller
                break
        
        return all_klines
    
    def klines_to_dataframe(self, klines):
        """
        Convert klines data to pandas DataFrame
        
        Args:
            klines (list): List of klines from Binance API
        
        Returns:
            pd.DataFrame: DataFrame with OHLCV data
        """
        if not klines:
            return pd.DataFrame()
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # Convert to appropriate data types
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        # Keep only relevant columns
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        return df
    
    def download_data_for_signal(self, symbol, signal_datetime, hours_after=12):
        """
        Download price data for a specific signal
        
        Args:
            symbol (str): Trading pair
            signal_datetime (datetime): Signal date and time
            hours_after (int): Number of hours of data to download after signal
        
        Returns:
            pd.DataFrame: Price data
        """
        # Add buffer before signal to ensure entry price is captured
        start_datetime = signal_datetime - timedelta(hours=1)
        end_datetime = signal_datetime + timedelta(hours=hours_after)
        
        start_ms = int(start_datetime.timestamp() * 1000)
        end_ms = int(end_datetime.timestamp() * 1000)
        
        klines = self.get_klines(symbol, '1m', start_ms, end_ms)
        df = self.klines_to_dataframe(klines)
        
        return df
    
    def save_cache(self, symbol, signal_datetime, df):
        """Save downloaded data to cache"""
        cache_filename = f"{symbol}_{signal_datetime.strftime('%Y%m%d_%H%M')}.csv"
        cache_path = os.path.join(DATA_CACHE_DIR, cache_filename)
        df.to_csv(cache_path, index=False)
    
    def load_cache(self, symbol, signal_datetime):
        """Load cached data if available - optimized for speed"""
        cache_filename = f"{symbol}_{signal_datetime.strftime('%Y%m%d_%H%M')}.csv"
        cache_path = os.path.join(DATA_CACHE_DIR, cache_filename)
        
        if os.path.exists(cache_path):
            # Use faster CSV reading with optimized dtypes
            df = pd.read_csv(
                cache_path,
                parse_dates=['timestamp'],
                dtype={
                    'open': 'float32',
                    'high': 'float32',
                    'low': 'float32',
                    'close': 'float32',
                    'volume': 'float32'
                }
            )
            return df
        
        return None
    
    def download_with_cache(self, symbol, signal_datetime, hours_after=12):
        """
        Download data with caching support
        
        Args:
            symbol (str): Trading pair
            signal_datetime (datetime): Signal date and time
            hours_after (int): Number of hours of data to download after signal
        
        Returns:
            pd.DataFrame: Price data
        """
        # Try to load from cache first
        cached_df = self.load_cache(symbol, signal_datetime)
        if cached_df is not None:
            return cached_df
        
        # Download if not cached
        df = self.download_data_for_signal(symbol, signal_datetime, hours_after)
        
        if not df.empty:
            self.save_cache(symbol, signal_datetime, df)
        
        return df


def main():
    """Test the downloader"""
    downloader = BinancePriceDataDownloader()
    
    # Test download for one signal
    test_symbol = "BTCUSDT"
    test_datetime = datetime(2025, 12, 18, 21, 30)
    
    df = downloader.download_with_cache(test_symbol, test_datetime, hours_after=12)
    
    if not df.empty:
        print(f"\nDownloaded {len(df)} candles")
        print(df.head())
        print(df.tail())
    else:
        print("No data downloaded")


if __name__ == "__main__":
    main()
