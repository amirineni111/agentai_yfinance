import pyodbc
conn = pyodbc.connect('DRIVER={SQL Server};SERVER=localhost\\MSSQLSERVER01;DATABASE=stockdata_db;Trusted_Connection=yes;')
c = conn.cursor()

# 1. How many forex tickers exist?
c.execute("SELECT COUNT(DISTINCT symbol) FROM forex_hist_data")
print(f'Forex distinct symbols: {c.fetchone()[0]}')

# 2. How many rows per symbol?
c.execute("""
SELECT symbol, COUNT(*) as rows, MIN(trading_date) as first, MAX(trading_date) as latest
FROM forex_hist_data
GROUP BY symbol ORDER BY rows DESC
""")
print('\nForex symbols data:')
for r in c.fetchall():
    print(f'  {r[0]} | {r[1]} rows | {r[2]} to {r[3]}')

# 3. Tickers with new data since last prediction
c.execute("""
SELECT DISTINCT h.symbol as ticker
FROM forex_hist_data h
LEFT JOIN (
    SELECT ticker, MAX(prediction_date) as last_pred_date
    FROM ai_prediction_history
    WHERE market = 'Forex'
    GROUP BY ticker
) p ON h.symbol = p.ticker
WHERE p.last_pred_date IS NULL
   OR h.trading_date > p.last_pred_date
""")
tickers = [r[0] for r in c.fetchall()]
print(f'\nForex tickers with new data since last prediction: {len(tickers)}')
for t in tickers:
    print(f'  {t}')

# 4. Last forex prediction per ticker 
c.execute("""
SELECT ticker, MAX(prediction_date) as last_pred
FROM ai_prediction_history
WHERE market = 'Forex'
GROUP BY ticker ORDER BY last_pred DESC
""")
print('\nLast Forex prediction per ticker:')
for r in c.fetchall():
    print(f'  {r[0]} | last prediction: {r[1]}')

# 5. Check RSI data availability for forex
c.execute("SELECT COUNT(*), COUNT(DISTINCT symbol), MAX(trading_date) FROM forex_rsi_data")
r = c.fetchone()
print(f'\nForex RSI data: {r[0]} rows, {r[1]} symbols, latest: {r[2]}')

conn.close()
