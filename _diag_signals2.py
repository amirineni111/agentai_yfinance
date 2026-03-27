import pyodbc
conn = pyodbc.connect('DRIVER={SQL Server};SERVER=localhost\\MSSQLSERVER01;DATABASE=stockdata_db;Trusted_Connection=yes;')
cursor = conn.cursor()

# Check when each market's latest data was inserted
for table, label in [('nasdaq_100_hist_data', 'NASDAQ'), ('nse_500_hist_data', 'NSE'), ('forex_hist_data', 'Forex')]:
    cursor.execute(f"SELECT MAX(trading_date) FROM {table}")
    print(f'{label} latest date: {cursor.fetchone()[0]}')

# Check forex data ingestion pattern (last 7 days)
cursor.execute("""
SELECT trading_date, COUNT(DISTINCT symbol) as symbols
FROM forex_hist_data
WHERE trading_date >= '2026-03-20'
GROUP BY trading_date ORDER BY trading_date
""")
print('\nForex data by date (last 7 days):')
for row in cursor.fetchall():
    print(f'  {row[0]} | {row[1]} symbols')

# Same for NASDAQ
cursor.execute("""
SELECT trading_date, COUNT(DISTINCT ticker) as symbols
FROM nasdaq_100_hist_data
WHERE trading_date >= '2026-03-20'
GROUP BY trading_date ORDER BY trading_date
""")
print('\nNASDAQ data by date (last 7 days):')
for row in cursor.fetchall():
    print(f'  {row[0]} | {row[1]} symbols')

conn.close()
