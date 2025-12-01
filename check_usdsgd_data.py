import pyodbc
import pandas as pd

conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost\\MSSQLSERVER01;DATABASE=stockdata_db;Trusted_Connection=yes;')

# Check data count for each symbol
symbols = ['AUDUSD', 'USDSGD', 'EURUSD']
for symbol in symbols:
    df = pd.read_sql(f'SELECT COUNT(*) as count FROM dbo.forex_hist_data WHERE symbol = ?', conn, params=[symbol])
    print(f'{symbol}: {df["count"].iloc[0]} records')
    
# Check date range for USDSGD
df = pd.read_sql('SELECT MIN(trading_date) as min_date, MAX(trading_date) as max_date FROM dbo.forex_hist_data WHERE symbol = ?', conn, params=['USDSGD'])
print(f'USDSGD date range: {df.iloc[0]["min_date"]} to {df.iloc[0]["max_date"]}')

# Check sample data for USDSGD
df = pd.read_sql('SELECT TOP 5 trading_date, close_price, volume FROM dbo.forex_hist_data WHERE symbol = ? ORDER BY trading_date', conn, params=['USDSGD'])
print(f'\nUSDSGD sample data:')
print(df)

conn.close()