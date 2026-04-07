"""
ATR Refresh Core — Incremental Wilder's Smoothed ATR
=====================================================
Shared logic for per-market ATR refresh scripts.

Incremental approach:
  1. For each ticker, read the last stored ATR_14 state
  2. Read only NEW price rows after that date from the source table
  3. Continue Wilder's smoothing from the stored state
  4. INSERT only the new ATR rows (no truncate, no recompute)

For new tickers (no ATR data yet), full calculation from scratch.

True Range = MAX(High - Low, |High - PrevClose|, |Low - PrevClose|)
ATR_14 = Wilder's: first ATR = SMA(TR, 14), then ATR_t = (ATR_{t-1} * 13 + TR_t) / 14

Tables: nasdaq_100_atr_data, nse_500_atr_data, forex_atr_data
Columns: ticker/symbol, trading_date, close_price, high_price, low_price, true_range, ATR_14
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

ATR_PERIOD = 14


def _sanitize(val):
    """Convert NaN to None for SQL insertion."""
    if val is None:
        return None
    try:
        if np.isnan(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


def get_logger(market_name):
    log = logging.getLogger(f'atr_refresh_{market_name}')
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    fh = logging.FileHandler(
        os.path.join(_SCRIPT_DIR, f'atr_refresh_{market_name}_{datetime.now().strftime("%Y%m%d")}.log')
    )
    fh.setFormatter(fmt)
    log.addHandler(fh)
    return log


def compute_true_range(highs, lows, closes):
    """True Range = MAX(H-L, |H-prevC|, |L-prevC|)"""
    n = len(closes)
    tr = np.full(n, np.nan)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
    return tr


def compute_wilder_atr(tr, period=14):
    """Wilder's smoothed ATR: seed = SMA(TR, period), then ATR_t = (ATR_{t-1}*(period-1) + TR_t)/period"""
    n = len(tr)
    atr = np.full(n, np.nan)
    if n < period:
        return atr
    atr[period - 1] = float(np.mean(tr[:period]))
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def calculate_full_atr(highs, lows, closes, dates):
    """Full ATR from scratch for a single ticker.
    Returns list of tuples: (date, close, high, low, true_range, atr_14)
    """
    if len(closes) < ATR_PERIOD:
        return []

    tr = compute_true_range(highs, lows, closes)
    atr = compute_wilder_atr(tr, ATR_PERIOD)

    results = []
    for i in range(len(closes)):
        dt = dates[i]
        if isinstance(dt, np.datetime64):
            dt = pd.Timestamp(dt).to_pydatetime()

        results.append((
            dt,
            round(float(closes[i]), 6),
            round(float(highs[i]), 6),
            round(float(lows[i]), 6),
            round(float(tr[i]), 6) if not np.isnan(tr[i]) else None,
            round(float(atr[i]), 6) if not np.isnan(atr[i]) else None,
        ))
    return results


def continue_atr(prev_atr, prev_close, new_highs, new_lows, new_closes, new_dates):
    """Continue Wilder's ATR from a known state.
    new_closes[0] is the overlap close (last known), actual new data starts at [1].
    Returns list of tuples: (date, close, high, low, true_range, atr_14)
    """
    results = []
    atr = prev_atr
    prev_c = prev_close

    for i in range(1, len(new_closes)):
        c = float(new_closes[i])
        h = float(new_highs[i])
        l = float(new_lows[i])

        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))

        if atr is not None:
            atr = (atr * (ATR_PERIOD - 1) + tr) / ATR_PERIOD

        dt = new_dates[i]
        if isinstance(dt, np.datetime64):
            dt = pd.Timestamp(dt).to_pydatetime()

        results.append((
            dt,
            round(c, 6),
            round(h, 6),
            round(l, 6),
            round(tr, 6),
            round(atr, 6) if atr is not None else None,
        ))
        prev_c = c

    return results


def refresh_market_atr(source_table, target_table, id_col, market_label):
    """Incremental ATR refresh for one market."""
    log = get_logger(market_label)
    log.info(f"{'=' * 50}")
    log.info(f"ATR refresh: {market_label} ({source_table} -> {target_table})")
    log.info(f"{'=' * 50}")

    conn = pyodbc.connect(CONN_STR)
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.fast_executemany = True

    # 1. Get last ATR state per ticker
    log.info("Reading last ATR state per ticker...")
    last_state_df = pd.read_sql(f"""
        SELECT r.{id_col}, r.trading_date, r.close_price, r.ATR_14
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
            'atr': _sanitize(row['ATR_14']),
            'close': _sanitize(row['close_price']),
        }
    log.info(f"  {len(last_state)} tickers have existing ATR data")

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

            if state['atr'] is None:
                # Missing state — full recalc
                prices_df = pd.read_sql(
                    f"SELECT trading_date, CAST(close_price AS FLOAT) as close_price, "
                    f"CAST(high_price AS FLOAT) as high_price, CAST(low_price AS FLOAT) as low_price "
                    f"FROM dbo.{source_table} WHERE {id_col}=? "
                    f"AND close_price IS NOT NULL AND high_price IS NOT NULL AND low_price IS NOT NULL "
                    f"ORDER BY trading_date",
                    conn, params=[ticker])
                if len(prices_df) < ATR_PERIOD:
                    continue
                results = calculate_full_atr(
                    prices_df['high_price'].values,
                    prices_df['low_price'].values,
                    prices_df['close_price'].values,
                    prices_df['trading_date'].values
                )
                cursor.execute(f"DELETE FROM dbo.{target_table} WHERE {id_col}=?", ticker)
                for dt, cl, h, l, tr, atr in results:
                    insert_rows.append((str(ticker), dt, cl, h, l, tr, atr))
                updated += 1
                continue

            # Get new prices after last_date (include last for overlap)
            prices_df = pd.read_sql(
                f"SELECT trading_date, CAST(close_price AS FLOAT) as close_price, "
                f"CAST(high_price AS FLOAT) as high_price, CAST(low_price AS FLOAT) as low_price "
                f"FROM dbo.{source_table} WHERE {id_col}=? AND trading_date >= ? "
                f"AND close_price IS NOT NULL AND high_price IS NOT NULL AND low_price IS NOT NULL "
                f"ORDER BY trading_date",
                conn, params=[ticker, last_date])

            if len(prices_df) <= 1:
                skipped += 1
                continue

            results = continue_atr(
                state['atr'],
                state['close'],
                prices_df['high_price'].values,
                prices_df['low_price'].values,
                prices_df['close_price'].values,
                prices_df['trading_date'].values
            )

            for dt, cl, h, l, tr, atr in results:
                insert_rows.append((str(ticker), dt, cl, h, l, tr, atr))
            updated += 1

        log.info(f"  Updated {updated}, skipped {skipped} (no new data)")

    # 4. Handle NEW tickers — full calculation
    if new_tickers:
        log.info(f"Processing {len(new_tickers)} new tickers (full calc)...")
        for ticker in new_tickers:
            prices_df = pd.read_sql(
                f"SELECT trading_date, CAST(close_price AS FLOAT) as close_price, "
                f"CAST(high_price AS FLOAT) as high_price, CAST(low_price AS FLOAT) as low_price "
                f"FROM dbo.{source_table} WHERE {id_col}=? "
                f"AND close_price IS NOT NULL AND high_price IS NOT NULL AND low_price IS NOT NULL "
                f"ORDER BY trading_date",
                conn, params=[ticker])
            if len(prices_df) < ATR_PERIOD:
                continue
            results = calculate_full_atr(
                prices_df['high_price'].values,
                prices_df['low_price'].values,
                prices_df['close_price'].values,
                prices_df['trading_date'].values
            )
            for dt, cl, h, l, tr, atr in results:
                insert_rows.append((str(ticker), dt, cl, h, l, tr, atr))
        log.info(f"  Processed {len(new_tickers)} new tickers")

    # 5. Bulk insert all new rows
    if insert_rows:
        log.info(f"Inserting {len(insert_rows)} rows into {target_table}...")
        clean_rows = [
            (t, dt, _sanitize(cl), _sanitize(h), _sanitize(l), _sanitize(tr), _sanitize(atr))
            for t, dt, cl, h, l, tr, atr in insert_rows
        ]
        batch_size = 5000
        for i in range(0, len(clean_rows), batch_size):
            batch = clean_rows[i:i + batch_size]
            cursor.executemany(f"""
                INSERT INTO dbo.{target_table}
                ({id_col}, trading_date, close_price, high_price, low_price, true_range, ATR_14)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, batch)
        log.info(f"  Inserted {len(insert_rows)} rows")
    else:
        log.info("No new rows to insert — all data up to date")

    conn.close()
    log.info(f"[OK] ATR refresh complete for {market_label}")
    return len(insert_rows)
