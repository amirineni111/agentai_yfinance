"""
EMA/SMA Refresh Core — Incremental True Recursive EMA
======================================================
Shared logic for per-market EMA/SMA refresh scripts.

Incremental approach:
  1. For each ticker, read the last stored EMA_20/50/100/200 state
  2. Read only NEW price rows after that date from the source table
  3. Continue EMA smoothing from the stored state
  4. INSERT only the new rows (no truncate, no recompute)

For new tickers (no EMA data yet), full calculation from scratch.

Tables: nasdaq_100_ema_sma_data, nse_500_ema_sma_data, forex_ema_sma_data
Columns: ticker/symbol, trading_date, close_price, SMA_20, SMA_50, EMA_20, EMA_50, EMA_100, EMA_200
"""
import os
import pyodbc
import pandas as pd
import numpy as np
import logging
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONN_STR = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=localhost\\MSSQLSERVER01;'
    'DATABASE=stockdata_db;'
    'UID=remote_user;PWD=YourStrongPassword123!;'
    'TrustServerCertificate=Yes;Connect Timeout=30'
)

EMA_PERIODS = [20, 50, 100, 200]
SMA_PERIODS = [20, 50]

# EMA multipliers: k = 2/(period+1)
EMA_MULT = {p: 2.0 / (p + 1) for p in EMA_PERIODS}


def _sanitize(val):
    """Convert NaN/numpy NaN to None for SQL insertion."""
    if val is None:
        return None
    try:
        if np.isnan(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


def get_logger(market_name):
    log = logging.getLogger(f'ema_refresh_{market_name}')
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    _logs_dir = os.path.join(_SCRIPT_DIR, 'logs')
    os.makedirs(_logs_dir, exist_ok=True)
    fh = logging.FileHandler(
        os.path.join(_logs_dir, f'ema_refresh_{market_name}_latest.log'), mode='w'
    )
    fh.setFormatter(fmt)
    log.addHandler(fh)
    return log


def compute_ema_full(prices, period):
    """True recursive EMA seeded with SMA of first 'period' values."""
    n = len(prices)
    ema = np.full(n, np.nan)
    if n < period:
        return ema
    ema[period - 1] = float(np.mean(prices[:period]))
    k = EMA_MULT[period]
    for i in range(period, n):
        ema[i] = float(prices[i]) * k + ema[i - 1] * (1 - k)
    return ema


def compute_sma_full(prices, period):
    """Simple moving average."""
    n = len(prices)
    sma = np.full(n, np.nan)
    if n < period:
        return sma
    cumsum = np.cumsum(prices.astype(float))
    sma[period - 1:] = (cumsum[period - 1:] - np.concatenate([[0], cumsum[:n - period]])) / period
    return sma


def calculate_full_ema(prices, dates):
    """Full EMA/SMA from scratch for a single ticker.
    Returns list of tuples: (date, close, sma20, sma50, ema20, ema50, ema100, ema200)
    """
    if len(prices) < 20:
        return []

    emas = {p: compute_ema_full(prices, p) for p in EMA_PERIODS}
    smas = {p: compute_sma_full(prices, p) for p in SMA_PERIODS}

    results = []
    for i in range(len(prices)):
        dt = dates[i]
        if isinstance(dt, np.datetime64):
            dt = pd.Timestamp(dt).to_pydatetime()

        def val(arr, idx):
            v = arr[idx]
            return round(float(v), 4) if not np.isnan(v) else None

        results.append((
            dt,
            round(float(prices[i]), 4),
            val(smas[20], i),
            val(smas[50], i),
            val(emas[20], i),
            val(emas[50], i),
            val(emas[100], i),
            val(emas[200], i),
        ))
    return results


def continue_ema(prev_emas, new_prices, new_dates, all_recent_prices):
    """Continue EMA smoothing from a known state.
    prev_emas: dict {20: val, 50: val, 100: val, 200: val}
    new_prices: array where [0] is the overlap price (last known), actual new data starts at [1]
    all_recent_prices: all recent prices needed for SMA window calculations
    Returns list of tuples: (date, close, sma20, sma50, ema20, ema50, ema100, ema200)
    """
    results = []
    emas = dict(prev_emas)

    for i in range(1, len(new_prices)):
        price = float(new_prices[i])

        # Update EMAs
        for p in EMA_PERIODS:
            if emas[p] is not None:
                emas[p] = price * EMA_MULT[p] + emas[p] * (1 - EMA_MULT[p])

        # Calculate SMAs from recent price window
        # all_recent_prices grows as we add new prices
        sma_20 = None
        sma_50 = None
        recent_idx = len(all_recent_prices) - len(new_prices) + i + 1
        if recent_idx >= 20:
            sma_20 = round(float(np.mean(all_recent_prices[recent_idx - 20:recent_idx])), 4)
        if recent_idx >= 50:
            sma_50 = round(float(np.mean(all_recent_prices[recent_idx - 50:recent_idx])), 4)

        dt = new_dates[i]
        if isinstance(dt, np.datetime64):
            dt = pd.Timestamp(dt).to_pydatetime()

        results.append((
            dt,
            round(price, 4),
            sma_20,
            sma_50,
            round(emas[20], 4) if emas[20] is not None else None,
            round(emas[50], 4) if emas[50] is not None else None,
            round(emas[100], 4) if emas[100] is not None else None,
            round(emas[200], 4) if emas[200] is not None else None,
        ))

    return results


def refresh_market_ema(source_table, target_table, id_col, market_label):
    """Incremental EMA/SMA refresh for one market."""
    log = get_logger(market_label)
    log.info(f"{'=' * 50}")
    log.info(f"EMA/SMA refresh: {market_label} ({source_table} -> {target_table})")
    log.info(f"{'=' * 50}")

    conn = pyodbc.connect(CONN_STR)
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.fast_executemany = True

    # 1. Get last EMA state per ticker
    log.info("Reading last EMA state per ticker...")
    last_state_df = pd.read_sql(f"""
        SELECT r.{id_col}, r.trading_date, r.EMA_20, r.EMA_50, r.EMA_100, r.EMA_200
        FROM dbo.{target_table} r
        INNER JOIN (
            SELECT {id_col}, MAX(trading_date) AS max_date
            FROM dbo.{target_table}
            GROUP BY {id_col}
        ) latest ON r.{id_col} = latest.{id_col} AND r.trading_date = latest.max_date
    """, conn)

    last_state = {}
    for _, row in last_state_df.iterrows():
        last_state[row[id_col]] = {
            'last_date': row['trading_date'],
            'emas': {
                20: row['EMA_20'],
                50: row['EMA_50'],
                100: row['EMA_100'],
                200: row['EMA_200'],
            }
        }
    log.info(f"  {len(last_state)} tickers have existing EMA data")

    # 2. Get all tickers from source
    all_tickers = pd.read_sql(
        f"SELECT DISTINCT {id_col} FROM dbo.{source_table}", conn
    )[id_col].tolist()
    log.info(f"  {len(all_tickers)} tickers in source table")

    new_tickers = [t for t in all_tickers if t not in last_state]
    existing_tickers = [t for t in all_tickers if t in last_state]
    log.info(f"  {len(new_tickers)} new, {len(existing_tickers)} existing")

    insert_rows = []

    # 3. Handle EXISTING tickers — incremental
    if existing_tickers:
        log.info("Processing existing tickers (incremental)...")
        updated = 0
        skipped = 0

        for ticker in existing_tickers:
            state = last_state[ticker]
            last_date = state['last_date']

            any_none = any(v is None for v in state['emas'].values())

            if any_none:
                # Missing state — full recalc
                prices_df = pd.read_sql(
                    f"SELECT trading_date, CAST(close_price AS FLOAT) as close_price "
                    f"FROM dbo.{source_table} WHERE {id_col}=? ORDER BY trading_date",
                    conn, params=[ticker])
                if len(prices_df) < 20:
                    continue
                prices = prices_df['close_price'].values
                dates = prices_df['trading_date'].values
                results = calculate_full_ema(prices, dates)
                cursor.execute(f"DELETE FROM dbo.{target_table} WHERE {id_col}=?", ticker)
                for dt, cl, s20, s50, e20, e50, e100, e200 in results:
                    insert_rows.append((str(ticker), dt, cl, s20, s50, e20, e50, e100, e200))
                updated += 1
                continue

            # Get new prices after last_date (include last for overlap)
            prices_df = pd.read_sql(
                f"SELECT trading_date, CAST(close_price AS FLOAT) as close_price "
                f"FROM dbo.{source_table} WHERE {id_col}=? AND trading_date >= ? "
                f"ORDER BY trading_date",
                conn, params=[ticker, last_date])

            if len(prices_df) <= 1:
                skipped += 1
                continue

            # Also get recent prices for SMA calculation (need 50 before last_date)
            recent_df = pd.read_sql(
                f"SELECT trading_date, CAST(close_price AS FLOAT) as close_price "
                f"FROM dbo.{source_table} WHERE {id_col}=? AND trading_date <= ? "
                f"ORDER BY trading_date",
                conn, params=[ticker, last_date])
            # Combine recent + new for SMA window
            all_recent = np.concatenate([
                recent_df['close_price'].values,
                prices_df['close_price'].values[1:]  # skip overlap
            ])

            new_prices = prices_df['close_price'].values
            new_dates = prices_df['trading_date'].values
            results = continue_ema(state['emas'], new_prices, new_dates, all_recent)

            for dt, cl, s20, s50, e20, e50, e100, e200 in results:
                insert_rows.append((str(ticker), dt, cl, s20, s50, e20, e50, e100, e200))
            updated += 1

        log.info(f"  Updated {updated}, skipped {skipped} (no new data)")

    # 4. Handle NEW tickers — full calculation
    if new_tickers:
        log.info(f"Processing {len(new_tickers)} new tickers (full calc)...")
        for ticker in new_tickers:
            prices_df = pd.read_sql(
                f"SELECT trading_date, CAST(close_price AS FLOAT) as close_price "
                f"FROM dbo.{source_table} WHERE {id_col}=? ORDER BY trading_date",
                conn, params=[ticker])
            if len(prices_df) < 20:
                continue
            prices = prices_df['close_price'].values
            dates = prices_df['trading_date'].values
            results = calculate_full_ema(prices, dates)
            for dt, cl, s20, s50, e20, e50, e100, e200 in results:
                insert_rows.append((str(ticker), dt, cl, s20, s50, e20, e50, e100, e200))
        log.info(f"  Processed {len(new_tickers)} new tickers")

    # 5. Bulk insert all new rows
    if insert_rows:
        log.info(f"Inserting {len(insert_rows)} rows into {target_table}...")
        # Sanitize NaN -> None for SQL Server compatibility
        clean_rows = [
            (t, dt, _sanitize(cl), _sanitize(s20), _sanitize(s50),
             _sanitize(e20), _sanitize(e50), _sanitize(e100), _sanitize(e200))
            for t, dt, cl, s20, s50, e20, e50, e100, e200 in insert_rows
        ]
        batch_size = 5000
        for i in range(0, len(clean_rows), batch_size):
            batch = clean_rows[i:i + batch_size]
            cursor.executemany(f"""
                INSERT INTO dbo.{target_table}
                ({id_col}, trading_date, close_price, SMA_20, SMA_50,
                 EMA_20, EMA_50, EMA_100, EMA_200)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
        log.info(f"  Inserted {len(insert_rows)} rows")
    else:
        log.info("No new rows to insert — all data up to date")

    conn.close()
    log.info(f"[OK] EMA/SMA refresh complete for {market_label}")
    return len(insert_rows)
