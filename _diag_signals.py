import pyodbc
conn = pyodbc.connect('DRIVER={SQL Server};SERVER=localhost\\MSSQLSERVER01;DATABASE=stockdata_db;Trusted_Connection=yes;')
cursor = conn.cursor()

# Check latest forex hist data date
cursor.execute('SELECT MAX(trading_date) FROM forex_hist_data')
print('Latest forex_hist_data date:', cursor.fetchone()[0])

# Check forex signals captured around March 25-26
cursor.execute("""
SELECT market, signal_date, COUNT(*) as signal_count 
FROM signal_tracking_history 
WHERE market = 'Forex' AND signal_date >= '2026-03-20'
GROUP BY market, signal_date
ORDER BY signal_date DESC
""")
print('\nForex signals by date:')
for row in cursor.fetchall():
    print(f'  {row[0]} | {row[1]} | {row[2]} signals')

# Check ALL markets for March 24-26
cursor.execute("""
SELECT market, signal_date, COUNT(*) as signal_count 
FROM signal_tracking_history 
WHERE signal_date >= '2026-03-24'
GROUP BY market, signal_date
ORDER BY signal_date DESC, market
""")
print('\nAll markets signals by date (recent):')
for row in cursor.fetchall():
    print(f'  {row[0]} | {row[1]} | {row[2]} signals')

# Check what forex data exists for March 25-26
cursor.execute("""
SELECT trading_date, COUNT(DISTINCT symbol) as symbol_count
FROM forex_hist_data
WHERE trading_date >= '2026-03-24'
GROUP BY trading_date 
ORDER BY trading_date DESC
""")
print('\nForex hist data availability:')
for row in cursor.fetchall():
    print(f'  {row[0]} | {row[1]} symbols')

# Check crossover view for forex on March 25 and 26
for dt in ['2026-03-26', '2026-03-25']:
    cursor.execute(f"""
    SELECT COUNT(*) FROM vw_crossover_signals_Forex WHERE trading_date = '{dt}'
    """)
    cnt = cursor.fetchone()[0]
    print(f'\nvw_crossover_signals_Forex rows on {dt}: {cnt}')
    
    if cnt > 0:
        cursor.execute(f"""
        SELECT TOP 3 ticker, bullish_count, bearish_count 
        FROM vw_crossover_signals_Forex WHERE trading_date = '{dt}'
        """)
        for row in cursor.fetchall():
            print(f'  {row[0]} | bullish={row[1]} | bearish={row[2]}')

conn.close()
