"""
Forex Data Fetching from Multiple Reliable Sources
===================================================
This module provides functions to fetch accurate forex data from various sources
to replace yfinance for better data quality.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# ============================================================================
# 1. ALPHA VANTAGE (Recommended for Free Tier)
# ============================================================================
# Sign up: https://www.alphavantage.co/support/#api-key
# Free: 25 API calls/day, 5 calls/minute

def fetch_forex_alphavantage(from_currency, to_currency, api_key, output_size='compact'):
    """
    Fetch forex data from Alpha Vantage
    
    Parameters:
    -----------
    from_currency : str
        Base currency (e.g., 'EUR', 'GBP')
    to_currency : str
        Quote currency (e.g., 'USD')
    api_key : str
        Your Alpha Vantage API key
    output_size : str
        'compact' (100 data points) or 'full' (20+ years)
    
    Returns:
    --------
    pd.DataFrame with columns: trading_date, open, high, low, close
    """
    
    url = f'https://www.alphavantage.co/query'
    params = {
        'function': 'FX_DAILY',
        'from_symbol': from_currency,
        'to_symbol': to_currency,
        'apikey': api_key,
        'outputsize': output_size,
        'datatype': 'json'
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'Time Series FX (Daily)' not in data:
            print(f"Error: {data.get('Note', data.get('Error Message', 'Unknown error'))}")
            return pd.DataFrame()
        
        # Parse the data
        time_series = data['Time Series FX (Daily)']
        
        df = pd.DataFrame.from_dict(time_series, orient='index')
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # Rename columns
        df = df.rename(columns={
            '1. open': 'open_price',
            '2. high': 'high_price',
            '3. low': 'low_price',
            '4. close': 'close_price'
        })
        
        # Convert to float
        for col in df.columns:
            df[col] = df[col].astype(float)
        
        # Add symbol and reset index
        df['symbol'] = f"{from_currency}{to_currency}"
        df.reset_index(inplace=True)
        df.rename(columns={'index': 'trading_date'}, inplace=True)
        
        # Add volume placeholder (forex doesn't have volume)
        df['volume'] = 0
        
        print(f"✅ Fetched {len(df)} records for {from_currency}/{to_currency} from Alpha Vantage")
        return df
        
    except Exception as e:
        print(f"❌ Error fetching from Alpha Vantage: {e}")
        return pd.DataFrame()


# ============================================================================
# 2. TWELVE DATA
# ============================================================================
# Sign up: https://twelvedata.com/
# Free: 800 API calls/day

def fetch_forex_twelvedata(symbol, api_key, interval='1day', start_date=None, end_date=None):
    """
    Fetch forex data from Twelve Data
    
    Parameters:
    -----------
    symbol : str
        Currency pair (e.g., 'EUR/USD', 'GBP/USD')
    api_key : str
        Your Twelve Data API key
    interval : str
        Time interval (1min, 5min, 15min, 30min, 45min, 1h, 2h, 4h, 1day, 1week, 1month)
    start_date : str
        Start date in 'YYYY-MM-DD' format
    end_date : str
        End date in 'YYYY-MM-DD' format
    
    Returns:
    --------
    pd.DataFrame with forex data
    """
    
    url = 'https://api.twelvedata.com/time_series'
    
    params = {
        'symbol': symbol,
        'interval': interval,
        'apikey': api_key,
        'format': 'JSON',
        'outputsize': 5000  # Maximum
    }
    
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'values' not in data:
            print(f"Error: {data.get('message', 'Unknown error')}")
            return pd.DataFrame()
        
        df = pd.DataFrame(data['values'])
        
        # Rename and convert columns
        df = df.rename(columns={
            'datetime': 'trading_date',
            'open': 'open_price',
            'high': 'high_price',
            'low': 'low_price',
            'close': 'close_price'
        })
        
        df['trading_date'] = pd.to_datetime(df['trading_date'])
        
        # Convert to float
        for col in ['open_price', 'high_price', 'low_price', 'close_price']:
            df[col] = df[col].astype(float)
        
        # Add symbol and volume
        df['symbol'] = symbol.replace('/', '')
        df['volume'] = 0
        
        df = df.sort_values('trading_date').reset_index(drop=True)
        
        print(f"✅ Fetched {len(df)} records for {symbol} from Twelve Data")
        return df
        
    except Exception as e:
        print(f"❌ Error fetching from Twelve Data: {e}")
        return pd.DataFrame()


# ============================================================================
# 3. OANDA API (Demo Account - Most Accurate for Forex)
# ============================================================================
# Sign up: https://www.oanda.com/
# Best for professional-grade forex data

def fetch_forex_oanda(instrument, api_key, account_id, start_date=None, end_date=None, granularity='D'):
    """
    Fetch forex data from OANDA
    
    Parameters:
    -----------
    instrument : str
        Currency pair in OANDA format (e.g., 'EUR_USD', 'GBP_USD')
    api_key : str
        Your OANDA API key
    account_id : str
        Your OANDA account ID
    granularity : str
        Candle granularity (S5, S10, M1, M5, H1, D, W, M)
    
    Returns:
    --------
    pd.DataFrame with forex data
    """
    
    # OANDA uses practice or live endpoint
    base_url = "https://api-fxpractice.oanda.com"  # For demo account
    # base_url = "https://api-fxtrade.oanda.com"  # For live account
    
    url = f"{base_url}/v3/instruments/{instrument}/candles"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    params = {
        'granularity': granularity,
        'count': 5000  # Maximum
    }
    
    if start_date:
        params['from'] = start_date
    if end_date:
        params['to'] = end_date
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        if 'candles' not in data:
            print(f"Error: {data.get('errorMessage', 'Unknown error')}")
            return pd.DataFrame()
        
        # Parse candles
        records = []
        for candle in data['candles']:
            if candle['complete']:  # Only use complete candles
                records.append({
                    'trading_date': candle['time'][:10],  # Extract date
                    'open_price': float(candle['mid']['o']),
                    'high_price': float(candle['mid']['h']),
                    'low_price': float(candle['mid']['l']),
                    'close_price': float(candle['mid']['c']),
                    'volume': candle.get('volume', 0)
                })
        
        df = pd.DataFrame(records)
        df['trading_date'] = pd.to_datetime(df['trading_date'])
        df['symbol'] = instrument.replace('_', '')
        
        df = df.sort_values('trading_date').reset_index(drop=True)
        
        print(f"✅ Fetched {len(df)} records for {instrument} from OANDA")
        return df
        
    except Exception as e:
        print(f"❌ Error fetching from OANDA: {e}")
        return pd.DataFrame()


# ============================================================================
# 4. POLYGON.IO
# ============================================================================
# Sign up: https://polygon.io/
# Free tier available for forex

def fetch_forex_polygon(ticker, api_key, start_date, end_date, timespan='day'):
    """
    Fetch forex data from Polygon.io
    
    Parameters:
    -----------
    ticker : str
        Currency pair (e.g., 'C:EURUSD', 'C:GBPUSD')
    api_key : str
        Your Polygon.io API key
    start_date : str
        Start date in 'YYYY-MM-DD' format
    end_date : str
        End date in 'YYYY-MM-DD' format
    timespan : str
        'minute', 'hour', 'day', 'week', 'month', 'quarter', 'year'
    
    Returns:
    --------
    pd.DataFrame with forex data
    """
    
    url = f'https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/{timespan}/{start_date}/{end_date}'
    
    params = {
        'adjusted': 'true',
        'sort': 'asc',
        'limit': 50000,
        'apiKey': api_key
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['status'] != 'OK' or 'results' not in data:
            print(f"Error: {data.get('error', 'Unknown error')}")
            return pd.DataFrame()
        
        df = pd.DataFrame(data['results'])
        
        # Rename columns
        df = df.rename(columns={
            't': 'timestamp',
            'o': 'open_price',
            'h': 'high_price',
            'l': 'low_price',
            'c': 'close_price',
            'v': 'volume'
        })
        
        # Convert timestamp to date
        df['trading_date'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Add symbol
        df['symbol'] = ticker.replace('C:', '')
        
        # Select and order columns
        df = df[['trading_date', 'symbol', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']]
        df = df.sort_values('trading_date').reset_index(drop=True)
        
        print(f"✅ Fetched {len(df)} records for {ticker} from Polygon.io")
        return df
        
    except Exception as e:
        print(f"❌ Error fetching from Polygon.io: {e}")
        return pd.DataFrame()


# ============================================================================
# UTILITY FUNCTION: Save to SQL Server
# ============================================================================

def save_forex_to_database(df, conn_str):
    """
    Save forex data to SQL Server database
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with forex data
    conn_str : str
        SQL Server connection string
    """
    import pyodbc
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Insert data
        for _, row in df.iterrows():
            cursor.execute("""
                MERGE INTO dbo.forex_hist_data AS target
                USING (SELECT ? AS symbol, ? AS trading_date, ? AS open_price, 
                              ? AS high_price, ? AS low_price, ? AS close_price, ? AS volume) AS source
                ON (target.symbol = source.symbol AND target.trading_date = source.trading_date)
                WHEN MATCHED THEN
                    UPDATE SET open_price = source.open_price, 
                               high_price = source.high_price,
                               low_price = source.low_price,
                               close_price = source.close_price,
                               volume = source.volume
                WHEN NOT MATCHED THEN
                    INSERT (symbol, trading_date, open_price, high_price, low_price, close_price, volume)
                    VALUES (source.symbol, source.trading_date, source.open_price, 
                            source.high_price, source.low_price, source.close_price, source.volume);
            """, row['symbol'], row['trading_date'], row['open_price'], 
                 row['high_price'], row['low_price'], row['close_price'], row['volume'])
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Saved {len(df)} records to database")
        
    except Exception as e:
        print(f"❌ Error saving to database: {e}")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    
    print("=" * 70)
    print("FOREX DATA FETCHING EXAMPLES")
    print("=" * 70)
    
    # Example 1: Alpha Vantage (Best for getting started)
    print("\n1. ALPHA VANTAGE Example:")
    print("-" * 70)
    ALPHA_VANTAGE_KEY = "YOUR_API_KEY_HERE"  # Get from https://www.alphavantage.co/support/#api-key
    
    df_alpha = fetch_forex_alphavantage('EUR', 'USD', ALPHA_VANTAGE_KEY, output_size='compact')
    if not df_alpha.empty:
        print(df_alpha.head())
        print(f"\nDate range: {df_alpha['trading_date'].min()} to {df_alpha['trading_date'].max()}")
    
    # Example 2: Twelve Data
    print("\n\n2. TWELVE DATA Example:")
    print("-" * 70)
    TWELVE_DATA_KEY = "YOUR_API_KEY_HERE"  # Get from https://twelvedata.com/
    
    df_twelve = fetch_forex_twelvedata('EUR/USD', TWELVE_DATA_KEY, interval='1day')
    if not df_twelve.empty:
        print(df_twelve.head())
    
    # Example 3: OANDA (Most accurate for forex)
    print("\n\n3. OANDA Example:")
    print("-" * 70)
    OANDA_API_KEY = "YOUR_API_KEY_HERE"  # Get from https://www.oanda.com/
    OANDA_ACCOUNT_ID = "YOUR_ACCOUNT_ID"
    
    df_oanda = fetch_forex_oanda('EUR_USD', OANDA_API_KEY, OANDA_ACCOUNT_ID, granularity='D')
    if not df_oanda.empty:
        print(df_oanda.head())
    
    # Example 4: Polygon.io
    print("\n\n4. POLYGON.IO Example:")
    print("-" * 70)
    POLYGON_KEY = "YOUR_API_KEY_HERE"  # Get from https://polygon.io/
    
    start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    end = datetime.now().strftime('%Y-%m-%d')
    
    df_polygon = fetch_forex_polygon('C:EURUSD', POLYGON_KEY, start, end)
    if not df_polygon.empty:
        print(df_polygon.head())
    
    # Save to database example
    print("\n\n5. SAVING TO DATABASE:")
    print("-" * 70)
    conn_string = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost\\MSSQLSERVER01;'
        'DATABASE=stockdata_db;'
        'Trusted_Connection=yes;'
    )
    
    # Uncomment to save
    # if not df_alpha.empty:
    #     save_forex_to_database(df_alpha, conn_string)
    
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS:")
    print("=" * 70)
    print("""
    For FREE accurate forex data:
    1. Alpha Vantage - Best for daily updates (25 calls/day free)
    2. Twelve Data - Good for higher frequency (800 calls/day free)
    3. OANDA Demo - Most accurate, professional-grade data
    
    For PAID professional use:
    1. OANDA Professional Account
    2. Interactive Brokers API
    3. Polygon.io paid tier
    
    RECOMMENDED WORKFLOW:
    - Use Alpha Vantage for daily historical data updates
    - Use OANDA demo for testing and validation
    - Consider Twelve Data for intraday data
    """)
