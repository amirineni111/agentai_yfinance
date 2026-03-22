"""
RSI Refresh Core — Incremental Wilder's Smoothing
==================================================
Shared logic for per-market RSI refresh scripts.

Incremental approach:
  1. For each ticker, read the last stored avg_gain/avg_loss/trading_date
  2. Read only NEW price rows after that date from the source table
  3. Continue Wilder's smoothing from the stored state
  4. INSERT only the new RSI rows (no truncate, no recompute)

For new tickers (no RSI data yet), full calculation from scratch.

Tables: nasdaq_100_rsi_data, nse_500_rsi_data, forex_rsi_data
Columns: ticker/symbol, trading_date, RSI, avg_gain, avg_loss
"""
import pyodbc
import pandas as pd
import numpy as np
import logging
from datetime import datetime

RSI_PERIOD = 14

CONN_STR = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=192.168.86.55\\MSSQLSERVER01;'
    'DATABASE=stockdata_db;'
    'UID=remote_user;PWD=YourStrongPassword123!;'
    'TrustServerCertificate=Yes;Connect Timeout=30'
)


def get_logger(market_name):
    """Create a logger with file + console output."""
    log = logging.getLogger(f'rsi_refresh_{market_name}')
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)

    fh = logging.FileHandler(
        f'rsi_refresh_{market_name}_{datetime.now().strftime("%Y%m%d")}.log'
    )
    fh.setFormatter(fmt)
    log.addHandler(fh)

    return log


def calculate_full_rsi(prices, dates, period=RSI_PERIOD):
    """Full Wilder's RSI from scratch for a single ticker.
    Returns list of tuples: (date, rsi, avg_gain, avg_loss)
    """
    if len(prices) < period + 1:
        return []

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    if avg_loss == 0:
        rsi_val = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_val = 100.0 - (100.0 / (1.0 + rs))

    results = [(dates[period], float(rsi_val), float(avg_gain), float(avg_loss))]

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + float(gains[i])) / period
        avg_loss = (avg_loss * (period - 1) + float(losses[i])) / period

        if avg_loss == 0:
            rsi_val = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100.0 - (100.0 / (1.0 + rs))

        results.append((dates[i + 1], float(rsi_val), float(avg_gain), float(avg_loss)))

    return results


def continue_rsi(prev_avg_gain, prev_avg_loss, new_prices, new_dates, period=RSI_PERIOD):
    """Continue Wilder's smoothing from a known state.
    Returns list of tuples: (date, rsi, avg_gain, avg_loss) for each new price.
    """
    results = []
    avg_gain = prev_avg_gain
    avg_loss = prev_avg_loss

    for i in range(len(new_prices)):
        if i == 0:
            # First new price — compute delta from implicit previous close
            # The caller must include the last known close as new_prices[0]
            # and the actual new prices start at index 1
            continue

        delta = new_prices[i] - new_prices[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi_val = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100.0 - (100.0 / (1.0 + rs))

        results.append((new_dates[i], float(rsi_val), float(avg_gain), float(avg_loss)))

    return results


def refresh_market_rsi(source_table, target_table, id_col, market_label):
    """
    Incremental RSI refresh for one market.

    - Existing tickers: continue from last stored state, insert only new rows
    - New tickers: full calculation from scratch
    """
    log = get_logger(market_label)
    log.info(f"{'=' * 50}")
    log.info(f"RSI refresh: {market_label} ({source_table} → {target_table})")
    log.info(f"{'=' * 50}")

    conn = pyodbc.connect(CONN_STR)
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.fast_executemany = True

    # 1. Get last RSI state per ticker
    log.info("Reading last RSI state per ticker...")
    last_state_df = pd.read_sql(f"""
        SELECT r.{id_col}, r.trading_date, r.avg_gain, r.avg_loss
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
            'avg_gain': row['avg_gain'],
            'avg_loss': row['avg_loss'],
        }
    log.info(f"  {len(last_state)} tickers have existing RSI data")

    # 2. Get all tickers from source
    all_tickers = pd.read_sql(
        f"SELECT DISTINCT {id_col} FROM dbo.{source_table}", conn
    )[id_col].tolist()
    log.info(f"  {len(all_tickers)} tickers in source table")

    new_tickers = [t for t in all_tickers if t not in last_state]
    existing_tickers = [t for t in all_tickers if t in last_state]
    log.info(f"  {len(new_tickers)} new tickers, {len(existing_tickers)} existing")

    insert_rows = []  # (id, date, rsi, avg_gain, avg_loss)

    # 3. Handle EXISTING tickers — incremental
    if existing_tickers:
        log.info("Processing existing tickers (incremental)...")
        updated_count = 0
        skipped_count = 0

        for ticker in existing_tickers:
            state = last_state[ticker]
            last_date = state['last_date']

            if state['avg_gain'] is None or state['avg_loss'] is None:
                # Missing state — need to do a full recalc for this ticker
                # Read all prices for this ticker only
                prices_df = pd.read_sql(
                    f"SELECT trading_date, close_price FROM dbo.{source_table} "
                    f"WHERE {id_col}=? ORDER BY trading_date",
                    conn, params=[ticker]
                )
                if len(prices_df) < RSI_PERIOD + 1:
                    continue
                prices = prices_df['close_price'].astype(float).values
                dates = prices_df['trading_date'].values
                results = calculate_full_rsi(prices, dates)
                # Delete existing rows for this ticker and re-insert
                cursor.execute(f"DELETE FROM dbo.{target_table} WHERE {id_col}=?", ticker)
                for dt, rsi, ag, al in results:
                    if isinstance(dt, np.datetime64):
                        dt = pd.Timestamp(dt).to_pydatetime()
                    insert_rows.append((str(ticker), dt, rsi, ag, al))
                updated_count += 1
                continue

            # Read prices from last RSI date onward (need last close for delta)
            prices_df = pd.read_sql(
                f"SELECT trading_date, close_price FROM dbo.{source_table} "
                f"WHERE {id_col}=? AND trading_date >= ? ORDER BY trading_date",
                conn, params=[ticker, last_date]
            )

            if len(prices_df) <= 1:
                skipped_count += 1
                continue  # No new data

            prices = prices_df['close_price'].astype(float).values
            dates = prices_df['trading_date'].values

            # Continue from stored state
            new_rows = continue_rsi(state['avg_gain'], state['avg_loss'], prices, dates)

            for dt, rsi, ag, al in new_rows:
                if isinstance(dt, np.datetime64):
                    dt = pd.Timestamp(dt).to_pydatetime()
                insert_rows.append((str(ticker), dt, rsi, ag, al))

            if new_rows:
                updated_count += 1

        log.info(f"  Updated: {updated_count}, No new data: {skipped_count}")

    # 4. Handle NEW tickers — full calculation
    if new_tickers:
        log.info(f"Processing {len(new_tickers)} new tickers (full calculation)...")
        for ticker in new_tickers:
            prices_df = pd.read_sql(
                f"SELECT trading_date, close_price FROM dbo.{source_table} "
                f"WHERE {id_col}=? ORDER BY trading_date",
                conn, params=[ticker]
            )
            if len(prices_df) < RSI_PERIOD + 1:
                continue

            prices = prices_df['close_price'].astype(float).values
            dates = prices_df['trading_date'].values
            results = calculate_full_rsi(prices, dates)

            for dt, rsi, ag, al in results:
                if isinstance(dt, np.datetime64):
                    dt = pd.Timestamp(dt).to_pydatetime()
                insert_rows.append((str(ticker), dt, rsi, ag, al))

        log.info(f"  Calculated RSI for {len(new_tickers)} new tickers")

    # 5. Bulk insert
    if insert_rows:
        log.info(f"Inserting {len(insert_rows)} rows...")
        insert_sql = (
            f"INSERT INTO dbo.{target_table} ({id_col}, trading_date, RSI, avg_gain, avg_loss) "
            f"VALUES (?, ?, ?, ?, ?)"
        )
        batch_size = 5000
        for i in range(0, len(insert_rows), batch_size):
            batch = insert_rows[i:i + batch_size]
            cursor.executemany(insert_sql, batch)
        log.info(f"  Inserted {len(insert_rows)} rows into {target_table}")
    else:
        log.info("No new rows to insert — RSI is up to date")

    # 6. Verify
    cursor.execute(f"SELECT COUNT(*) FROM dbo.{target_table}")
    total = cursor.fetchone()[0]
    log.info(f"Total rows in {target_table}: {total}")

    conn.close()
    log.info("Done")
    return len(insert_rows)
