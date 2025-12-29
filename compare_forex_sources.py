"""
Compare Forex Data Quality: yfinance vs Alpha Vantage
======================================================
This script helps you compare the data quality between different sources
"""

import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta

def fetch_yfinance(symbol, period='1mo'):
    """Fetch from yfinance (current method)"""
    try:
        ticker = yf.Ticker(f"{symbol}=X")
        df = ticker.history(period=period)
        df.reset_index(inplace=True)
        df.columns = [col.lower().replace(' ', '_') for col in df.columns]
        return df
    except Exception as e:
        print(f"Error with yfinance: {e}")
        return pd.DataFrame()

def fetch_alphavantage(from_curr, to_curr, api_key):
    """Fetch from Alpha Vantage"""
    url = 'https://www.alphavantage.co/query'
    params = {
        'function': 'FX_DAILY',
        'from_symbol': from_curr,
        'to_symbol': to_curr,
        'apikey': api_key,
        'outputsize': 'compact'
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'Time Series FX (Daily)' not in data:
            return pd.DataFrame()
        
        time_series = data['Time Series FX (Daily)']
        
        records = []
        for date_str, values in time_series.items():
            records.append({
                'date': date_str,
                'open': float(values['1. open']),
                'high': float(values['2. high']),
                'low': float(values['3. low']),
                'close': float(values['4. close'])
            })
        
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date')
        
    except Exception as e:
        print(f"Error with Alpha Vantage: {e}")
        return pd.DataFrame()

def compare_data(symbol, from_curr, to_curr, api_key):
    """Compare data from both sources"""
    
    print(f"\n{'='*70}")
    print(f"COMPARING: {from_curr}/{to_curr} ({symbol})")
    print(f"{'='*70}\n")
    
    # Fetch from both sources
    print("📊 Fetching from yfinance...")
    df_yf = fetch_yfinance(symbol)
    
    print("📊 Fetching from Alpha Vantage...")
    df_av = fetch_alphavantage(from_curr, to_curr, api_key)
    
    if df_yf.empty or df_av.empty:
        print("❌ Could not fetch data from one or both sources")
        return
    
    # Find common dates
    yf_dates = set(df_yf['date'].dt.date)
    av_dates = set(df_av['date'].dt.date)
    common_dates = yf_dates & av_dates
    
    print(f"\n📅 DATA COVERAGE:")
    print(f"   yfinance records: {len(df_yf)}")
    print(f"   Alpha Vantage records: {len(df_av)}")
    print(f"   Common dates: {len(common_dates)}")
    
    if len(common_dates) == 0:
        print("❌ No overlapping dates found!")
        return
    
    # Compare prices on common dates
    print(f"\n💰 PRICE COMPARISON (Last 5 common dates):")
    print(f"{'Date':<12} {'Source':<15} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Diff %':<10}")
    print("-" * 85)
    
    common_dates_sorted = sorted(common_dates, reverse=True)[:5]
    
    total_diff = 0
    count = 0
    
    for date in common_dates_sorted:
        yf_row = df_yf[df_yf['date'].dt.date == date].iloc[0]
        av_row = df_av[df_av['date'].dt.date == date].iloc[0]
        
        # Calculate difference
        close_diff = abs(yf_row['close'] - av_row['close']) / av_row['close'] * 100
        total_diff += close_diff
        count += 1
        
        print(f"{date} yfinance      {yf_row['open']:<10.5f} {yf_row['high']:<10.5f} {yf_row['low']:<10.5f} {yf_row['close']:<10.5f}")
        print(f"{'':12} Alpha Vantage {av_row['open']:<10.5f} {av_row['high']:<10.5f} {av_row['low']:<10.5f} {av_row['close']:<10.5f} {close_diff:>9.4f}%")
        print()
    
    avg_diff = total_diff / count if count > 0 else 0
    
    print(f"\n📊 ACCURACY ANALYSIS:")
    print(f"   Average price difference: {avg_diff:.4f}%")
    
    if avg_diff < 0.01:
        print("   ✅ Excellent match - both sources highly accurate")
    elif avg_diff < 0.1:
        print("   ✅ Good match - minor differences")
    elif avg_diff < 1.0:
        print("   ⚠️  Moderate differences - consider switching source")
    else:
        print("   ❌ Significant differences - SHOULD switch to Alpha Vantage")
    
    # Show latest prices from both
    print(f"\n📌 LATEST PRICES:")
    latest_yf = df_yf.iloc[-1]
    latest_av = df_av.iloc[-1]
    
    print(f"   yfinance: {latest_yf['close']:.5f} (Date: {latest_yf['date'].date()})")
    print(f"   Alpha Vantage: {latest_av['close']:.5f} (Date: {latest_av['date'].date()})")

if __name__ == "__main__":
    
    # Your Alpha Vantage API key
    API_KEY = "YOUR_API_KEY_HERE"
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("\n❌ Please set your Alpha Vantage API key!")
        print("Get it FREE at: https://www.alphavantage.co/support/#api-key\n")
        exit()
    
    print("=" * 70)
    print("FOREX DATA QUALITY COMPARISON")
    print("=" * 70)
    
    # Compare all your forex pairs
    pairs = [
        ('AUDUSD', 'AUD', 'USD'),
        ('EURCHF', 'EUR', 'CHF'),
        ('EURJPY', 'EUR', 'JPY'),
        ('EURUSD', 'EUR', 'USD'),
        ('GBPUSD', 'GBP', 'USD')
    ]
    
    for symbol, from_curr, to_curr in pairs:
        compare_data(symbol, from_curr, to_curr, API_KEY)
        print("\n" + "="*70)
    
    print("\n💡 RECOMMENDATION:")
    print("""
    If you see significant differences:
    1. Use update_forex_data.py to replace your data with Alpha Vantage
    2. Set up a daily scheduled task to keep data fresh
    3. Consider Alpha Vantage Premium for real-time data
    
    Alternative sources if Alpha Vantage doesn't work:
    - OANDA (most accurate for forex traders)
    - Twelve Data (good free tier)
    - Polygon.io (comprehensive data)
    """)
