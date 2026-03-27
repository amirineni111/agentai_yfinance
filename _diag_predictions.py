import pyodbc
conn = pyodbc.connect('DRIVER={SQL Server};SERVER=localhost\\MSSQLSERVER01;DATABASE=stockdata_db;Trusted_Connection=yes;')
c = conn.cursor()

# Check forex predictions in ai_prediction_history
c.execute("""
SELECT market, prediction_date, COUNT(*) as cnt
FROM ai_prediction_history
WHERE market = 'Forex' AND prediction_date >= '2026-03-20'
GROUP BY market, prediction_date
ORDER BY prediction_date DESC
""")
print('Forex predictions by date:')
rows = c.fetchall()
if rows:
    for r in rows: print(f'  {r[0]} | {r[1]} | {r[2]} predictions')
else:
    print('  NO FOREX PREDICTIONS FOUND')

# All markets
c.execute("SELECT market, COUNT(*) FROM ai_prediction_history GROUP BY market")
print('\nAll markets in ai_prediction_history:')
for r in c.fetchall(): print(f'  {r[0]} | {r[1]} total predictions')

# Latest prediction per market
c.execute("""
SELECT market, MAX(prediction_date) as latest
FROM ai_prediction_history GROUP BY market
""")
print('\nLatest prediction date per market:')
for r in c.fetchall(): print(f'  {r[0]} | {r[1]}')

conn.close()
