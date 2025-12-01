"""
Quick test script to verify forex data accessibility
"""

import pyodbc
import pandas as pd

def test_forex_database_access():
    """Test forex database views and tables"""
    
    # Database connection parameters (adjust as needed)
    server = 'localhost\\MSSQLSERVER01'
    database = 'stockdata_db'
    
    try:
        # Establish connection
        conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'
        conn = pyodbc.connect(conn_str)
        print("✅ Database connection successful!")
        
        # Test forex views/tables
        forex_objects_to_test = [
            'forex_daily_summary',
            'forex_ml_predictions', 
            'forex_hist_data',
            'forex_RSI_calculation',
            'forex_macd',
            'forex_bollingerband'
        ]
        
        for obj_name in forex_objects_to_test:
            try:
                # Try to query each object
                query = f"SELECT TOP 5 * FROM dbo.{obj_name}"
                df = pd.read_sql(query, conn)
                
                print(f"\n📊 {obj_name}:")
                print(f"   - Rows: {len(df)}")
                print(f"   - Columns: {list(df.columns)}")
                
                if not df.empty:
                    # Look for currency/symbol columns
                    currency_cols = [col for col in df.columns 
                                   if any(keyword in col.lower() 
                                        for keyword in ['currency', 'pair', 'symbol'])]
                    if currency_cols:
                        print(f"   - Currency columns: {currency_cols}")
                        unique_values = df[currency_cols[0]].unique()[:5]  # First 5 unique values
                        print(f"   - Sample currency pairs: {list(unique_values)}")
                else:
                    print("   - No data found")
                    
            except Exception as e:
                print(f"❌ Error accessing {obj_name}: {str(e)}")
        
        conn.close()
        print("\n✅ Database connection closed successfully!")
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")

if __name__ == "__main__":
    test_forex_database_access()