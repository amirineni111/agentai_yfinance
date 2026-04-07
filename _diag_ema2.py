"""Check for NaN values in EMA insert data."""
import pyodbc, pandas as pd, numpy as np, sys
from datetime import datetime

OUT = r'C:\Users\sreea\OneDrive\Desktop\streamlit-trading-dashboard\_ema_diag.txt'
sys.stdout = open(OUT, 'w')

CONN_STR = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=localhost\\MSSQLSERVER01;'
    'DATABASE=stockdata_db;'
    'UID=remote_user;PWD=YourStrongPassword123!;'
    'TrustServerCertificate=Yes'
)
conn = pyodbc.connect(CONN_STR)
cursor = conn.cursor()

# Check column types
cursor.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME='nse_500_ema_sma_data' 
    ORDER BY ORDINAL_POSITION
""")
print("=== nse_500_ema_sma_data columns ===")
for row in cursor.fetchall():
    print(f"  {row[0]:20s} {row[1]:15s} nullable={row[2]}")

# Check for any existing NaN/NULL in EMA_200
cursor.execute("""
    SELECT COUNT(*) as total, 
           SUM(CASE WHEN EMA_200 IS NULL THEN 1 ELSE 0 END) as null_200,
           SUM(CASE WHEN EMA_100 IS NULL THEN 1 ELSE 0 END) as null_100
    FROM nse_500_ema_sma_data
""")
row = cursor.fetchone()
print(f"\nExisting data: total={row[0]}, NULL EMA_200={row[1]}, NULL EMA_100={row[2]}")

# Simulate what the incremental code produces - check one ticker with few rows
cursor.execute("""
    SELECT TOP 5 ticker, COUNT(*) as cnt
    FROM nse_500_hist_data 
    GROUP BY ticker 
    HAVING COUNT(*) < 200
    ORDER BY cnt ASC
""")
print("\nTickers with < 200 rows:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} rows")

# Test: what does Python's round(np.float64('nan'), 4) produce?
try:
    val = round(np.float64('nan'), 4)
    print(f"\nround(NaN, 4) = {val}, type={type(val)}, is None? {val is None}, isnan? {np.isnan(val)}")
except Exception as e:
    print(f"\nround(NaN, 4) raises: {e}")

conn.close()
sys.stdout.close()
