"""
One-time migration: Add avg_gain and avg_loss columns to RSI tables.
These columns store the Wilder's smoothing state so daily incremental
refreshes can continue from where they left off.
"""
import pyodbc
import pandas as pd
import numpy as np

CONN_STR = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=localhost\\MSSQLSERVER01;'
    'DATABASE=stockdata_db;'
    'UID=remote_user;PWD=YourStrongPassword123!;'
    'TrustServerCertificate=Yes;Connect Timeout=30'
)

TABLES = ['nasdaq_100_rsi_data', 'nse_500_rsi_data', 'forex_rsi_data']

conn = pyodbc.connect(CONN_STR)
conn.autocommit = True
c = conn.cursor()

# Step 1: Add columns
for tbl in TABLES:
    for col in ['avg_gain', 'avg_loss']:
        try:
            c.execute(f"ALTER TABLE dbo.{tbl} ADD {col} FLOAT NULL")
            print(f"Added {col} to {tbl}")
        except Exception as e:
            if 'already' in str(e).lower() or 'column names' in str(e).lower():
                print(f"Column {col} already exists in {tbl}")
            else:
                raise

# Step 2: Backfill avg_gain/avg_loss from existing price data
MARKETS = [
    ('nasdaq_100_hist_data', 'nasdaq_100_rsi_data', 'ticker'),
    ('nse_500_hist_data',    'nse_500_rsi_data',    'ticker'),
    ('forex_hist_data',      'forex_rsi_data',      'symbol'),
]

for source, target, id_col in MARKETS:
    print(f"\nBackfilling {target}...")

    # Read all price data
    df = pd.read_sql(
        f"SELECT {id_col}, trading_date, close_price "
        f"FROM dbo.{source} ORDER BY {id_col}, trading_date", conn)

    updates = []
    for ticker, group in df.groupby(id_col):
        group = group.sort_values('trading_date').reset_index(drop=True)
        prices = group['close_price'].astype(float).values
        dates = group['trading_date'].values

        if len(prices) < 15:
            continue

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = float(np.mean(gains[:14]))
        avg_loss = float(np.mean(losses[:14]))
        updates.append((float(avg_gain), float(avg_loss), str(ticker), dates[14]))

        for i in range(14, len(gains)):
            avg_gain = (avg_gain * 13 + float(gains[i])) / 14
            avg_loss = (avg_loss * 13 + float(losses[i])) / 14
            if isinstance(dates[i + 1], np.datetime64):
                dt = pd.Timestamp(dates[i + 1]).to_pydatetime()
            else:
                dt = dates[i + 1]
            updates.append((float(avg_gain), float(avg_loss), str(ticker), dt))

    # Bulk update
    c.fast_executemany = True
    update_sql = f"UPDATE dbo.{target} SET avg_gain=?, avg_loss=? WHERE {id_col}=? AND trading_date=?"
    batch_size = 5000
    total = len(updates)
    for i in range(0, total, batch_size):
        batch = updates[i:i + batch_size]
        c.executemany(update_sql, batch)
        print(f"  Updated {min(i + batch_size, total)}/{total}")

    print(f"  Done: {total} rows updated in {target}")

conn.close()
print("\nMigration complete.")
