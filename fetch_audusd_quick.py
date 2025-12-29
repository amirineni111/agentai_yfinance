"""
Quick fetch AUDUSD data for 2025-12-22
"""
import yfinance as yf
import pandas as pd
from datetime import datetime

print("="*70)
print("FETCHING AUDUSD DATA FOR 2025-12-22")
print("="*70)

# Method 1: yfinance (quick, no API key needed)
print("\n📊 Attempting to fetch from yfinance...")
try:
    ticker = yf.Ticker("AUDUSD=X")
    df = ticker.history(period="5d")  # Get last 5 days to ensure we have 2025-12-22
    
    if not df.empty:
        df.reset_index(inplace=True)
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        
        print(f"\n✅ Successfully fetched {len(df)} days of data")
        print("\nAll available data:")
        print("-"*70)
        
        for _, row in df.iterrows():
            print(f"\nDate: {row['Date']}")
            print(f"  Open:  ${row['Open']:.5f}")
            print(f"  High:  ${row['High']:.5f}")
            print(f"  Low:   ${row['Low']:.5f}")
            print(f"  Close: ${row['Close']:.5f}")
            print(f"  Volume: {row['Volume']:,.0f}")
        
        # Check for specific date
        target_date = datetime(2025, 12, 22).date()
        target_row = df[df['Date'] == target_date]
        
        if not target_row.empty:
            print("\n" + "="*70)
            print(f"🎯 DATA FOR {target_date}:")
            print("="*70)
            row = target_row.iloc[0]
            print(f"\n  Currency Pair: AUDUSD")
            print(f"  Open Price:    ${row['Open']:.5f}")
            print(f"  High Price:    ${row['High']:.5f}")
            print(f"  Low Price:     ${row['Low']:.5f}")
            print(f"  Close Price:   ${row['Close']:.5f}")
            print(f"  Volume:        {row['Volume']:,.0f}")
            
            # Calculate daily change
            daily_change = row['Close'] - row['Open']
            daily_change_pct = (daily_change / row['Open']) * 100
            
            print(f"\n  Daily Change:  ${daily_change:+.5f} ({daily_change_pct:+.2f}%)")
            
            # Intraday range
            intraday_range = row['High'] - row['Low']
            range_pct = (intraday_range / row['Open']) * 100
            
            print(f"  Intraday Range: ${intraday_range:.5f} ({range_pct:.2f}%)")
            
        else:
            print(f"\n⚠️ Data for {target_date} not available yet")
            print(f"   Latest available date: {df['Date'].max()}")
            print(f"   Note: Market might be closed or data not yet updated")
    else:
        print("❌ No data returned from yfinance")
        
except Exception as e:
    print(f"❌ Error fetching data: {e}")

print("\n" + "="*70)
print("\n💡 NOTE:")
print("   - December 22, 2025 is a Sunday (market closed)")
print("   - Forex markets are typically closed on weekends")
print("   - Last trading day was likely Friday, December 19, 2025")
print("   - Next trading day will be Monday, December 22, 2025")
print("\n   If you need more accurate data, use Alpha Vantage or OANDA")
print("="*70)
