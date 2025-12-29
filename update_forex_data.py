"""
Update Forex Data in Database from Reliable Sources
====================================================
This script replaces yfinance forex data with more accurate data from Alpha Vantage
"""

import pyodbc
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# Database connection
CONN_STR = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=localhost\\MSSQLSERVER01;'
    'DATABASE=stockdata_db;'
    'Trusted_Connection=yes;'
)

# Alpha Vantage API Key (FREE - Sign up at https://www.alphavantage.co/support/#api-key)
ALPHA_VANTAGE_KEY = "AG63AW94QZN86YBX"

# Currency pairs to update
FOREX_PAIRS = [
    ('AUD', 'USD'),
    ('EUR', 'CHF'),
    ('EUR', 'JPY'),
    ('EUR', 'USD'),
    ('GBP', 'USD')
]


def fetch_forex_data(from_currency, to_currency, api_key, days_back=365):
    """
    Fetch forex data from Alpha Vantage
    
    Parameters:
    -----------
    from_currency : str
        Base currency (e.g., 'AUD', 'EUR')
    to_currency : str
        Quote currency (e.g., 'USD')
    api_key : str
        Your Alpha Vantage API key
    days_back : int
        Number of days of historical data to fetch (default: 365 for 1 year)
    """
    
    url = 'https://www.alphavantage.co/query'
    params = {
        'function': 'FX_DAILY',
        'from_symbol': from_currency,
        'to_symbol': to_currency,
        'apikey': api_key,
        'outputsize': 'full',  # Get full historical data (20+ years)
        'datatype': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        
        # Check for errors
        if 'Error Message' in data:
            print(f"❌ API Error: {data['Error Message']}")
            return pd.DataFrame()
        
        if 'Note' in data:
            print(f"⚠️  API Limit: {data['Note']}")
            return pd.DataFrame()
        
        if 'Time Series FX (Daily)' not in data:
            print(f"❌ No data returned for {from_currency}/{to_currency}")
            return pd.DataFrame()
        
        # Parse data
        time_series = data['Time Series FX (Daily)']
        
        records = []
        for date_str, values in time_series.items():
            records.append({
                'symbol': f"{from_currency}{to_currency}",
                'trading_date': date_str,
                'open_price': float(values['1. open']),
                'high_price': float(values['2. high']),
                'low_price': float(values['3. low']),
                'close_price': float(values['4. close']),
                'volume': 0  # Forex doesn't have volume
            })
        
        df = pd.DataFrame(records)
        df['trading_date'] = pd.to_datetime(df['trading_date'])
        df = df.sort_values('trading_date')
        
        # Filter to last N days
        cutoff_date = datetime.now() - timedelta(days=days_back)
        df_filtered = df[df['trading_date'] >= cutoff_date].copy()
        
        print(f"✅ Fetched {len(df)} total records for {from_currency}/{to_currency}")
        print(f"   Full date range: {df['trading_date'].min().date()} to {df['trading_date'].max().date()}")
        print(f"   Filtered to last {days_back} days: {len(df_filtered)} records")
        print(f"   Filtered range: {df_filtered['trading_date'].min().date()} to {df_filtered['trading_date'].max().date()}")
        
        return df_filtered
        
    except requests.exceptions.Timeout:
        print(f"❌ Request timeout for {from_currency}/{to_currency}")
        return pd.DataFrame()
    except Exception as e:
        print(f"❌ Error fetching {from_currency}/{to_currency}: {e}")
        return pd.DataFrame()


def update_database(df, conn_str):
    """Update forex_hist_data table with new data"""
    
    if df.empty:
        print("⚠️  No data to update")
        return
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        symbol = df['symbol'].iloc[0]
        
        # Count existing records
        cursor.execute("SELECT COUNT(*) FROM dbo.forex_hist_data WHERE symbol = ?", symbol)
        existing_count = cursor.fetchone()[0]
        
        print(f"\nUpdating {symbol}:")
        print(f"  - Existing records in DB: {existing_count}")
        print(f"  - New records to process: {len(df)}")
        
        # Use MERGE to upsert data
        updated = 0
        inserted = 0
        
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
            
            # Track if it was insert or update (simplified - actual tracking would need @@ROWCOUNT)
            if cursor.rowcount > 0:
                updated += 1
        
        conn.commit()
        
        # Get final count
        cursor.execute("SELECT COUNT(*) FROM dbo.forex_hist_data WHERE symbol = ?", symbol)
        final_count = cursor.fetchone()[0]
        
        print(f"  - Final records in DB: {final_count}")
        print(f"  - Records processed: {updated}")
        
        cursor.close()
        conn.close()
        
        print(f"✅ Database updated successfully for {symbol}\n")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}\n")


def main():
    """Main execution function"""
    
    print("=" * 70)
    print("FOREX DATA UPDATE UTILITY")
    print("Using Alpha Vantage API for accurate forex data")
    print("=" * 70)
    
    if ALPHA_VANTAGE_KEY == "YOUR_API_KEY_HERE":
        print("\n❌ ERROR: Please set your Alpha Vantage API key!")
        print("\n📝 Get your FREE API key here:")
        print("   https://www.alphavantage.co/support/#api-key")
        print("\nThen update the ALPHA_VANTAGE_KEY variable in this script.\n")
        return
    
    print(f"\n📅 Starting data update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔄 Updating {len(FOREX_PAIRS)} currency pairs\n")
    
    total_records = 0
    successful = 0
    failed = 0
    
    for i, (from_curr, to_curr) in enumerate(FOREX_PAIRS, 1):
        print(f"[{i}/{len(FOREX_PAIRS)}] Processing {from_curr}/{to_curr}...")
        
        # Fetch data
        df = fetch_forex_data(from_curr, to_curr, ALPHA_VANTAGE_KEY)
        
        if not df.empty:
            # Update database
            update_database(df, CONN_STR)
            total_records += len(df)
            successful += 1
        else:
            print(f"⚠️  Skipping {from_curr}/{to_curr} - no data retrieved\n")
            failed += 1
        
        # Rate limiting - Alpha Vantage allows 5 calls/minute on free tier
        if i < len(FOREX_PAIRS):
            print("⏳ Waiting 15 seconds (API rate limit)...")
            time.sleep(15)
    
    # Summary
    print("\n" + "=" * 70)
    print("UPDATE SUMMARY")
    print("=" * 70)
    print(f"✅ Successful updates: {successful}/{len(FOREX_PAIRS)}")
    print(f"❌ Failed updates: {failed}/{len(FOREX_PAIRS)}")
    print(f"📊 Total records processed: {total_records}")
    print(f"⏰ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    print("\n💡 NEXT STEPS:")
    print("   1. Restart your Streamlit app to see the updated data")
    print("   2. Clear the database cache using 'Reset Database Connections'")
    print("   3. Run this script daily to keep data fresh (set up as scheduled task)")
    print("\n📌 TIP: Consider upgrading to Alpha Vantage Premium for:")
    print("   - More API calls per day")
    print("   - Intraday data")
    print("   - Real-time data\n")


if __name__ == "__main__":
    main()
