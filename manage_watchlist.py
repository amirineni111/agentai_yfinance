"""
WATCHLIST MANAGEMENT UTILITY
Simple script to view and manage prediction watchlist
"""

import pyodbc
import pandas as pd

def get_db_connection():
    """Create database connection"""
    conn_str = (
        "DRIVER={SQL Server};"
        "SERVER=localhost\\MSSQLSERVER01;"
        "DATABASE=stockdata_db;"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)

def view_watchlist():
    """Display current watchlist"""
    conn = get_db_connection()
    query = """
    SELECT 
        market,
        ticker,
        company_name,
        priority,
        CASE WHEN is_active = 1 THEN 'Active' ELSE 'Inactive' END as status
    FROM prediction_watchlist
    ORDER BY market, priority, ticker
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    print("\n" + "="*80)
    print("CURRENT WATCHLIST")
    print("="*80)
    
    for market in ['NSE 500', 'NASDAQ 100', 'Forex']:
        market_df = df[df['market'] == market]
        print(f"\n📊 {market}: {len(market_df)} tickers")
        print(market_df.to_string(index=False))
    
    print(f"\n📈 Total: {len(df)} tickers")
    print("="*80 + "\n")

def add_ticker(market, ticker, company_name, priority=1):
    """Add new ticker to watchlist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO prediction_watchlist (market, ticker, company_name, priority)
            VALUES (?, ?, ?, ?)
        """, market, ticker, company_name, priority)
        conn.commit()
        print(f"✅ Added: {ticker} ({company_name}) to {market}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cursor.close()
        conn.close()

def remove_ticker(ticker):
    """Remove ticker from watchlist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM prediction_watchlist WHERE ticker = ?", ticker)
        rows = cursor.rowcount
        conn.commit()
        if rows > 0:
            print(f"✅ Removed: {ticker}")
        else:
            print(f"⚠️  Ticker not found: {ticker}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cursor.close()
        conn.close()

def toggle_ticker(ticker, active=True):
    """Enable/disable ticker"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE prediction_watchlist 
            SET is_active = ?, updated_date = GETDATE()
            WHERE ticker = ?
        """, 1 if active else 0, ticker)
        rows = cursor.rowcount
        conn.commit()
        if rows > 0:
            status = "enabled" if active else "disabled"
            print(f"✅ {ticker} {status}")
        else:
            print(f"⚠️  Ticker not found: {ticker}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cursor.close()
        conn.close()

def get_summary():
    """Display watchlist summary"""
    conn = get_db_connection()
    query = """
    SELECT 
        market,
        COUNT(*) as total,
        SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active
    FROM prediction_watchlist
    GROUP BY market
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    print("\n" + "="*50)
    print("WATCHLIST SUMMARY")
    print("="*50)
    print(df.to_string(index=False))
    print(f"\nTotal Active: {df['active'].sum()}")
    print("="*50 + "\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("\n📋 Watchlist Management Commands:")
        print("  python manage_watchlist.py view")
        print("  python manage_watchlist.py summary")
        print("  python manage_watchlist.py add 'NSE 500' 'ADANIPORTS.NS' 'Adani Ports' 1")
        print("  python manage_watchlist.py remove 'TICKER'")
        print("  python manage_watchlist.py enable 'TICKER'")
        print("  python manage_watchlist.py disable 'TICKER'")
        print()
        get_summary()
    else:
        command = sys.argv[1].lower()
        
        if command == 'view':
            view_watchlist()
        elif command == 'summary':
            get_summary()
        elif command == 'add' and len(sys.argv) >= 5:
            market = sys.argv[2]
            ticker = sys.argv[3]
            company = sys.argv[4]
            priority = int(sys.argv[5]) if len(sys.argv) > 5 else 1
            add_ticker(market, ticker, company, priority)
        elif command == 'remove' and len(sys.argv) >= 3:
            remove_ticker(sys.argv[2])
        elif command == 'enable' and len(sys.argv) >= 3:
            toggle_ticker(sys.argv[2], True)
        elif command == 'disable' and len(sys.argv) >= 3:
            toggle_ticker(sys.argv[2], False)
        else:
            print("❌ Invalid command or missing arguments")
