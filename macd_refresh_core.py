"""
MACD Refresh Core — Incremental True EMA
=========================================
Shared logic for per-market MACD refresh scripts.

Incremental approach:
  1. For each ticker, read the last stored EMA_12, EMA_26, Signal_Line state
  2. Read only NEW price rows after that date from the source table
  3. Continue EMA smoothing from the stored state
  4. INSERT only the new MACD rows (no truncate, no recompute)

For new tickers (no MACD data yet), full calculation from scratch.

Tables: nasdaq_100_macd_data, nse_500_macd_data, forex_macd_data
Columns: ticker/symbol, trading_date, EMA_12, EMA_26, MACD, Signal_Line, Histogram
"""
import pyodbc
import pandas as pd
import numpy as np
import logging
from datetime import datetime

CONN_STR = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=192.168.86.55\\MSSQLSERVER01;'
    'DATABASE=stockdata_db;'
    'UID=remote_user;PWD=YourStrongPassword123!;'
    'TrustServerCertificate=Yes;Connect Timeout=30'
)

EMA12_MULT = 2.0 / 13  # 0.153846
EMA26_MULT = 2.0 / 27  # 0.074074
SIG9_MULT  = 2.0 / 10  # 0.200000


def get_logger(market_name):
    log = logging.getLogger(f'macd_refresh_{market_name}')
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    fh = logging.FileHandler(
        f'macd_refresh_{market_name}_{datetime.now().strftime("%Y%m%d")}.log'
    )
    fh.setFormatter(fmt)
    log.addHandler(fh)
    return log


def calc_ema(prices, period):
    """Standard EMA: SMA seed + exponential smoothing."""
    n = len(prices)
    ema = np.full(n, np.nan)
    if n < period:
        return ema
    mult = 2.0 / (period + 1)
    ema[period - 1] = float(np.mean(prices[:period]))
    for i in range(period, n):
        ema[i] = float(prices[i]) * mult + ema[i - 1] * (1 - mult)
    return ema


def calculate_full_macd(prices, dates):
    """Full MACD from scratch for a single ticker.
    Returns list of tuples: (date, ema12, ema26, macd, signal, histogram)
    """
    if len(prices) < 26:
        return []

    ema12 = calc_ema(prices, 12)
    ema26 = calc_ema(prices, 26)
    macd_line = ema12 - ema26

    # Signal = 9-period EMA of MACD, starting from index 25
    valid_macd = macd_line[25:]
    signal_raw = calc_ema(valid_macd, 9)
    signal_line = np.full(len(prices), np.nan)
    signal_line[25:] = signal_raw
    histogram = macd_line - signal_line

    results = []
    for i in range(25, len(prices)):
        if np.isnan(ema12[i]) or np.isnan(ema26[i]):
            continue
        dt = dates[i]
        if isinstance(dt, np.datetime64):
            dt = pd.Timestamp(dt).to_pydatetime()
        sig = float(signal_line[i]) if not np.isnan(signal_line[i]) else None
        hist = float(histogram[i]) if not np.isnan(histogram[i]) else None
        results.append((dt, float(ema12[i]), float(ema26[i]),
                        float(macd_line[i]), sig, hist))
    return results


def continue_macd(prev_ema12, prev_ema26, prev_signal, new_prices, new_dates):
    """Continue EMA smoothing from a known state.
    new_prices[0] must be the last known close (for continuity), actual new data starts at [1].
    Returns list of tuples: (date, ema12, ema26, macd, signal, histogram)
    """
    results = []
    ema12 = prev_ema12
    ema26 = prev_ema26
    signal = prev_signal

    for i in range(1, len(new_prices)):
        price = float(new_prices[i])
        ema12 = price * EMA12_MULT + ema12 * (1 - EMA12_MULT)
        ema26 = price * EMA26_MULT + ema26 * (1 - EMA26_MULT)
        macd = ema12 - ema26

        if signal is not None:
            signal = macd * SIG9_MULT + signal * (1 - SIG9_MULT)
            hist = macd - signal
        else:
            signal = None
            hist = None

        dt = new_dates[i]
        if isinstance(dt, np.datetime64):
            dt = pd.Timestamp(dt).to_pydatetime()

        results.append((dt, float(ema12), float(ema26), float(macd),
                        float(signal) if signal is not None else None,
                        float(hist) if hist is not None else None))
    return results


def refresh_market_macd(source_table, target_table, id_col, market_label):
    """Incremental MACD refresh for one market."""
    log = get_logger(market_label)
    log.info(f"{'=' * 50}")
    log.info(f"MACD refresh: {market_label} ({source_table} -> {target_table})")
    log.info(f"{'=' * 50}")

    conn = pyodbc.connect(CONN_STR)
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.fast_executemany = True

    # 1. Get last MACD state per ticker
    log.info("Reading last MACD state per ticker...")
    last_state_df = pd.read_sql(f"""
        SELECT r.{id_col}, r.trading_date, r.EMA_12, r.EMA_26, r.Signal_Line
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
            'ema12': row['EMA_12'],
            'ema26': row['EMA_26'],
            'signal': row['Signal_Line'],
        }
    log.info(f"  {len(last_state)} tickers have existing MACD data")

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

            if state['ema12'] is None or state['ema26'] is None:
                # Missing state — full recalc for this ticker
                prices_df = pd.read_sql(
                    f"SELECT trading_date, close_price FROM dbo.{source_table} "
                    f"WHERE {id_col}=? ORDER BY trading_date", conn, params=[ticker])
                if len(prices_df) < 26:
                    continue
                prices = prices_df['close_price'].astype(float).values
                dates = prices_df['trading_date'].values
                results = calculate_full_macd(prices, dates)
                cursor.execute(f"DELETE FROM dbo.{target_table} WHERE {id_col}=?", ticker)
                for dt, e12, e26, m, s, h in results:
                    insert_rows.append((str(ticker), dt, e12, e26, m, s, h))
                updated += 1
                continue

            # Read prices from last MACD date onward
            prices_df = pd.read_sql(
                f"SELECT trading_date, close_price FROM dbo.{source_table} "
                f"WHERE {id_col}=? AND trading_date >= ? ORDER BY trading_date",
                conn, params=[ticker, last_date])

            if len(prices_df) <= 1:
                skipped += 1
                continue

            prices = prices_df['close_price'].astype(float).values
            dates = prices_df['trading_date'].values
            new_rows = continue_macd(state['ema12'], state['ema26'], state['signal'],
                                     prices, dates)

            for dt, e12, e26, m, s, h in new_rows:
                insert_rows.append((str(ticker), dt, e12, e26, m, s, h))

            if new_rows:
                updated += 1

        log.info(f"  Updated: {updated}, No new data: {skipped}")

    # 4. Handle NEW tickers — full calculation
    if new_tickers:
        log.info(f"Processing {len(new_tickers)} new tickers (full)...")
        for ticker in new_tickers:
            prices_df = pd.read_sql(
                f"SELECT trading_date, close_price FROM dbo.{source_table} "
                f"WHERE {id_col}=? ORDER BY trading_date", conn, params=[ticker])
            if len(prices_df) < 26:
                continue
            prices = prices_df['close_price'].astype(float).values
            dates = prices_df['trading_date'].values
            results = calculate_full_macd(prices, dates)
            for dt, e12, e26, m, s, h in results:
                insert_rows.append((str(ticker), dt, e12, e26, m, s, h))
        log.info(f"  Calculated MACD for {len(new_tickers)} new tickers")

    # 5. Bulk insert
    if insert_rows:
        log.info(f"Inserting {len(insert_rows)} rows...")
        insert_sql = (
            f"INSERT INTO dbo.{target_table} "
            f"({id_col}, trading_date, EMA_12, EMA_26, MACD, Signal_Line, Histogram) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?)")
        batch_size = 10000
        for i in range(0, len(insert_rows), batch_size):
            batch = insert_rows[i:i + batch_size]
            cursor.executemany(insert_sql, batch)
        log.info(f"  Inserted {len(insert_rows)} rows into {target_table}")
    else:
        log.info("No new rows to insert — MACD is up to date")

    # 6. Verify
    cursor.execute(f"SELECT COUNT(*) FROM dbo.{target_table}")
    total = cursor.fetchone()[0]
    log.info(f"Total rows in {target_table}: {total}")

    conn.close()
    log.info("Done")
    return len(insert_rows)
