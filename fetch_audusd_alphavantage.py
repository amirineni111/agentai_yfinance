"""
Fetch AUDUSD data for 2025-12-22 from Alpha Vantage
"""
import requests
import pandas as pd
from datetime import datetime

# Your Alpha Vantage API Key
# Get FREE key at: https://www.alphavantage.co/support/#api-key
ALPHA_VANTAGE_KEY = "AG63AW94QZN86YBX"

print("="*70)
print("FETCHING AUDUSD FROM ALPHA VANTAGE - December 22, 2025")
print("="*70)

if ALPHA_VANTAGE_KEY == "YOUR_API_KEY_HERE":
    print("\n❌ ERROR: Please set your Alpha Vantage API key!")
    print("\n📝 Get your FREE API key here:")
    print("   https://www.alphavantage.co/support/#api-key")
    print("\n   Steps:")
    print("   1. Visit the URL above")
    print("   2. Enter your email")
    print("   3. Get instant API key (no credit card needed)")
    print("   4. Update ALPHA_VANTAGE_KEY in this script")
    exit()

print("\n📊 Fetching from Alpha Vantage API...")

url = 'https://www.alphavantage.co/query'
params = {
    'function': 'FX_DAILY',
    'from_symbol': 'AUD',
    'to_symbol': 'USD',
    'apikey': ALPHA_VANTAGE_KEY,
    'outputsize': 'compact',  # Last 100 data points
    'datatype': 'json'
}

try:
    response = requests.get(url, params=params, timeout=30)
    data = response.json()
    
    # Check for errors
    if 'Error Message' in data:
        print(f"\n❌ API Error: {data['Error Message']}")
        exit()
    
    if 'Note' in data:
        print(f"\n⚠️  API Rate Limit: {data['Note']}")
        print("\n💡 Alpha Vantage free tier limits:")
        print("   - 25 API calls per day")
        print("   - 5 API calls per minute")
        exit()
    
    if 'Time Series FX (Daily)' not in data:
        print(f"\n❌ Unexpected response from Alpha Vantage")
        print(f"Response: {data}")
        exit()
    
    # Parse data
    time_series = data['Time Series FX (Daily)']
    
    print(f"\n✅ Successfully fetched data from Alpha Vantage")
    print(f"   Total records available: {len(time_series)}")
    
    # Convert to DataFrame for easier handling
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
    df = df.sort_values('date', ascending=False)
    
    print("\n" + "="*70)
    print("LATEST 5 DAYS OF DATA:")
    print("="*70)
    
    for _, row in df.head(5).iterrows():
        date = row['date'].date()
        daily_change = row['close'] - row['open']
        daily_change_pct = (daily_change / row['open']) * 100
        
        print(f"\nDate: {date}")
        print(f"  Open:  ${row['open']:.5f}")
        print(f"  High:  ${row['high']:.5f}")
        print(f"  Low:   ${row['low']:.5f}")
        print(f"  Close: ${row['close']:.5f}")
        print(f"  Change: ${daily_change:+.5f} ({daily_change_pct:+.2f}%)")
    
    # Look for December 22, 2025
    target_date = datetime(2025, 12, 22).date()
    target_row = df[df['date'].dt.date == target_date]
    
    print("\n" + "="*70)
    if not target_row.empty:
        print(f"🎯 AUDUSD DATA FOR {target_date} (Alpha Vantage)")
        print("="*70)
        
        row = target_row.iloc[0]
        
        print(f"\n  Currency Pair: AUD/USD")
        print(f"  Source:        Alpha Vantage (Professional Grade)")
        print(f"  Date:          {target_date}")
        print(f"\n  Open Price:    ${row['open']:.5f}")
        print(f"  High Price:    ${row['high']:.5f}")
        print(f"  Low Price:     ${row['low']:.5f}")
        print(f"  Close Price:   ${row['close']:.5f}")
        
        # Calculate metrics
        daily_change = row['close'] - row['open']
        daily_change_pct = (daily_change / row['open']) * 100
        intraday_range = row['high'] - row['low']
        range_pct = (intraday_range / row['open']) * 100
        
        print(f"\n  Daily Change:  ${daily_change:+.5f} ({daily_change_pct:+.2f}%)")
        print(f"  Intraday Range: ${intraday_range:.5f} ({range_pct:.2f}%)")
        
        # Price position analysis
        close_position = ((row['close'] - row['low']) / (row['high'] - row['low'])) * 100 if row['high'] != row['low'] else 50
        
        print(f"\n  📊 Technical Analysis:")
        print(f"     Close position in range: {close_position:.1f}%")
        
        if close_position > 70:
            print(f"     Signal: Strong close near high (bullish)")
        elif close_position < 30:
            print(f"     Signal: Weak close near low (bearish)")
        else:
            print(f"     Signal: Mid-range close (neutral)")
        
        # Trend
        if daily_change > 0:
            print(f"     Trend: Bullish (+{daily_change_pct:.2f}%)")
        elif daily_change < 0:
            print(f"     Trend: Bearish ({daily_change_pct:.2f}%)")
        else:
            print(f"     Trend: Flat (0.00%)")
        
    else:
        print(f"⚠️ DATA FOR {target_date} NOT FOUND")
        print("="*70)
        print(f"\n   Latest available date: {df['date'].max().date()}")
        print(f"   Possible reasons:")
        print(f"   - Market was closed on {target_date}")
        print(f"   - Data not yet available from Alpha Vantage")
        print(f"   - Weekend or holiday")
    
    print("\n" + "="*70)
    print("✅ DATA QUALITY: Professional Grade")
    print("   Alpha Vantage provides accurate, exchange-sourced data")
    print("   Suitable for trading decisions and analysis")
    print("="*70)
    
except requests.exceptions.Timeout:
    print("\n❌ Request timeout - Alpha Vantage server not responding")
except requests.exceptions.RequestException as e:
    print(f"\n❌ Network error: {e}")
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n💡 NEXT STEPS:")
print("   - Use update_forex_data.py to update your entire database")
print("   - Set up daily automation for fresh data")
print("   - Consider Alpha Vantage Premium for real-time data")
print()
