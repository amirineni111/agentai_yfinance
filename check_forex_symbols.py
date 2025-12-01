import pyodbc
import pandas as pd

conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost\\MSSQLSERVER01;DATABASE=stockdata_db;Trusted_Connection=yes;')
df = pd.read_sql('SELECT DISTINCT symbol FROM dbo.forex_hist_data ORDER BY symbol', conn)
print('Available Forex symbols:')
print(df['symbol'].tolist())
print('\nChecking if USDSGD exists:')
usdsgd_exists = 'USDSGD' in df['symbol'].values
print(f'USDSGD exists: {usdsgd_exists}')
conn.close()