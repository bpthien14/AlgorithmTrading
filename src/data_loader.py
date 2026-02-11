import os
import pandas as pd
import numpy as np
import requests
from io import StringIO


def load_data(filepath: str) -> pd.DataFrame:
    """
    Load M1 data from CSV.
    Expected columns: 'timestamp', 'open', 'high', 'low', 'close', 'volume'
    """
    try:
        df = pd.read_csv(filepath)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

def resample_to_m15(df_m1: pd.DataFrame) -> pd.DataFrame:
    """
    Resample M1 data to M15 data.
    """
    ohlc_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    # Resample to 15 minute intervals
    df_m15 = df_m1.resample('15min').agg(ohlc_dict)
    
    # Drop rows with NaN values (incomplete intervals)
    df_m15.dropna(inplace=True)
    
    return df_m15

def align_mtf_data(df_m1: pd.DataFrame, df_m15: pd.DataFrame) -> pd.DataFrame:
    """
    Align M15 data to M1 index using forward fill.
    This simulates request.security(..., lookahead=barmerge.lookahead_on).
    
    CRITICAL: In a real simulation, we must ensure that at time T (M1), 
    we only see M15 data that was available at or before T.
    
    Pine Script `request.security` behaves differently depending on context.
    For this strategy, we assume we want the 'current developing' M15 bar 
    or the 'last closed' M15 bar. 
    
    The strategy uses `is_new_m15_candle_close` logic, implying it acts ON THE CLOSE
    of the M15 bar.
    """
    # Reindex M15 to match M1, filling forward
    # shift(1) is often needed to correctly simulate "data available at open of next bar"
    # But Pine Script `latest` data is often available realtime.
    # We will simply merge on time index and ffill.
    
    df_m15_aligned = df_m15.reindex(df_m1.index, method='ffill')
    
    # Rename columns to avoid collision
    df_m15_aligned = df_m15_aligned.add_suffix('_m15')
    
    # Combine
    combined = pd.concat([df_m1, df_m15_aligned], axis=1)
    return combined

def generate_dummy_data(days=5) -> pd.DataFrame:
    """Generate synthetic M1 data for testing coverage."""
    rng = pd.date_range(start="2024-01-01", periods=1440*days, freq="1min")
    
    # Random walk
    price = 1000 + np.cumsum(np.random.randn(len(rng)) * 2)
    
    data = {
        'timestamp': rng,
        'open': price,
        'high': price + np.random.rand(len(rng)),
        'low': price - np.random.rand(len(rng)),
        'close': price + np.random.randn(len(rng)) * 0.5,
        'volume': np.abs(np.random.randn(len(rng)) * 1000)
    }
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


def load_oanda_xauusd_240(filepath: str) -> pd.DataFrame:
    """
    Load dữ liệu XAUUSD khung 240 phút (H4) từ file CSV OANDA.

    File mẫu: 'OANDA_XAUUSD, 240.csv'
    Cột: time (epoch seconds), open, high, low, close, Volume
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error loading OANDA CSV: {e}")
        return pd.DataFrame()

    if "time" not in df.columns:
        print("CSV missing 'time' column.")
        return pd.DataFrame()

    # Convert epoch seconds -> datetime
    df["timestamp"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("timestamp", inplace=True)

    # Chuẩn hoá tên cột cho thống nhất
    rename_map = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "Volume": "volume",
    }
    df = df.rename(columns=rename_map)

    # Giữ đúng thứ tự cột kỳ vọng
    df = df[["open", "high", "low", "close", "volume"]]

    return df


def load_oanda_xauusd_m1(filepath: str) -> pd.DataFrame:
    """
    Load dữ liệu XAUUSD khung 1 phút (M1) từ file CSV OANDA.

    File mẫu: 'OANDA_XAUUSD, 1.csv'
    Cột: time (epoch seconds), open, high, low, close, Volume
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error loading OANDA M1 CSV: {e}")
        return pd.DataFrame()

    if "time" not in df.columns:
        print("CSV missing 'time' column.")
        return pd.DataFrame()

    # Convert epoch seconds -> datetime
    df["timestamp"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("timestamp", inplace=True)
    # Chuẩn hoá timezone: dùng tz-naive (UTC) để đồng nhất với pipeline/backtest hiện tại
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)

    # Chuẩn hoá tên cột
    rename_map = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "Volume": "volume",
    }
    df = df.rename(columns=rename_map)

    df = df[["open", "high", "low", "close", "volume"]]

    return df


def fetch_dukascopy_xauusd(start_date: str, end_date: str, timeframe: str = "m1") -> pd.DataFrame:
    """
    Fetch XAUUSD historical data from Dukascopy (FREE, institutional-grade data).
    
    Args:
        start_date: Start date in format 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'
        end_date: End date in format 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'
        timeframe: 'm1', 'm5', 'm15', 'm30', 'h1', 'h4', 'd1' (default: 'm1')
    
    Returns:
        DataFrame with DatetimeIndex (timestamp) and columns: open, high, low, close, volume
    
    Data Range: XAUUSD available from May 2003 to present (22+ years)
    Quality: Swiss bank institutional data, widely considered the gold standard for forex/commodities
    """
    print(f"Fetching XAUUSD {timeframe.upper()} data from Dukascopy ({start_date} -> {end_date})...")
    
    # Dukascopy API endpoint
    # Format: https://datafeed.dukascopy.com/datafeed/{instrument}/{year}/{month}/{day}/{hour}h_ticks.bi5
    # For aggregated bars, we use their CSV export or community tools
    
    base_url = "https://www.dukascopy.com/datafeed/xauusd"
    
    try:
        # Parse dates
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        # For simplicity, we'll use a direct CSV download approach
        # Dukascopy allows direct CSV download for historical data via their web interface
        # Alternative: Use dukascopy-node (Node.js) or Python wrapper
        
        # Method 1: Direct API call (simplified - real implementation would parse binary .bi5 files)
        # Method 2: Use pre-downloaded CSV from Dukascopy web interface
        # Method 3: Use Python wrapper library
        
        print("  Note: Download data via Dukascopy web interface or use 'dukascopy-node' CLI:")
        print(f"  npx dukascopy-node -i xauusd -from {start.strftime('%Y-%m-%d')} -to {end.strftime('%Y-%m-%d')} -t {timeframe} -f csv")
        print("  Then place the CSV file in the project directory.")
        
        # For now, return empty to indicate manual download needed
        # In production, integrate with dukascopy Python library or subprocess call to Node.js
        return pd.DataFrame()
        
    except Exception as e:
        print(f"Error fetching Dukascopy data: {e}")
        return pd.DataFrame()


def load_dukascopy_csv(filepath: str) -> pd.DataFrame:
    """
    Load Dukascopy CSV file (downloaded via dukascopy-node or web interface).
    
    Expected CSV format:
    timestamp,open,high,low,close,volume
    2024-01-01 00:00:00,2050.12,2051.45,2049.88,2050.99,1234
    
    Args:
        filepath: Path to Dukascopy CSV file
    
    Returns:
        DataFrame with DatetimeIndex and columns: open, high, low, close, volume
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error loading Dukascopy CSV: {e}")
        return pd.DataFrame()
    
    # Check for timestamp column (may be 'time', 'timestamp', or 'datetime')
    time_col = None
    for col in ['timestamp', 'time', 'datetime', 'date']:
        if col in df.columns:
            time_col = col
            break
    
    if time_col is None:
        print(f"CSV missing time column. Found columns: {list(df.columns)}")
        return pd.DataFrame()
    
    # Convert Unix timestamp (milliseconds) to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Ensure tz-naive UTC
    if getattr(df.index, 'tz', None) is not None:
        df.index = df.index.tz_convert('UTC').tz_localize(None)
    
    # Standardize column names
    rename_map = {
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume',
    }
    df = df.rename(columns=rename_map)
    
    # Select required columns
    required = ['open', 'high', 'low', 'close']
    if 'volume' not in df.columns:
        df['volume'] = 0  # Dukascopy may not have volume for all instruments
    
    df = df[['open', 'high', 'low', 'close', 'volume']]
    
    # Sort by timestamp to ensure chronological order
    df = df.sort_index()
    
    return df
