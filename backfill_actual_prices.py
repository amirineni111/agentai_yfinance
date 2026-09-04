"""
Standalone Backfill: Actual Prices for ai_prediction_history
=============================================================
Fills actual_price, actual_change_pct, direction_correct, absolute_error,
squared_error, and percentage_error for all predictions where target_date
has elapsed but actual_price is still NULL.

Covers all three markets: NSE 500, NASDAQ 100, Forex.

RESOLVED 2026-09-03: the ~124,115 predictions stalled since Feb 27, 2026 are fully
backfilled. Root cause was arithmetic overflow 8115 on NUMERIC columns, fixed by
migrate_widen_error_columns.sql. Verified 0 rows with an elapsed target_date and
actual_price IS NULL, across all three markets. Do not carry this as an open issue.

Note on "unresolved" counts: ~11k NASDAQ / ~10k NSE rows normally have
actual_price IS NULL at any time. Those are 7-day predictions whose target_date
has not arrived yet — roughly 5 trading days x ticker count. Only rows with an
ELAPSED target_date indicate a problem.

daily_prediction_job.py runs this same logic as Step 1 every night (for all three
markets regardless of --market) and now exits non-zero if any market's UPDATE
fails — the silent per-market failure is what let the Feb stall run unnoticed.
This script remains the standalone recovery version, with verbose reporting and
a --dry-run option.

Usage:
    python backfill_actual_prices.py               # run for all markets
    python backfill_actual_prices.py --dry-run     # report counts only, no DB writes
    python backfill_actual_prices.py --market "NSE 500"
    python backfill_actual_prices.py --market "NSE 500" "NASDAQ 100"
"""

import pyodbc
import argparse
from datetime import datetime
import sys
import traceback

# Force unbuffered output for real-time logs
sys.stdout.reconfigure(line_buffering=True)


# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_db_connection():
    """Get SQL Server database connection (Windows auth)."""
    conn_str = (
        "DRIVER={SQL Server};"
        "SERVER=localhost\\MSSQLSERVER01;"
        "DATABASE=stockdata_db;"
        "Trusted_Connection=yes;"
    )
    conn = pyodbc.connect(conn_str, timeout=30)
    conn.timeout = 1800  # 30-minute query timeout for large backfills
    return conn


# =====================================================
# MARKET CONFIGURATION (must match daily_prediction_job.py)
# =====================================================

MARKETS = {
    'NSE 500':    {'table': 'nse_500_hist_data',    'symbol_col': 'ticker'},
    'NASDAQ 100': {'table': 'nasdaq_100_hist_data', 'symbol_col': 'ticker'},
    'Forex':      {'table': 'forex_hist_data',       'symbol_col': 'symbol'},
}


# =====================================================
# SHARED GRADING SQL
#
# daily_prediction_job.py imports these so the nightly Step-1 backfill and
# this standalone script can never grade the same row differently. Do not
# inline a copy -- the two drifted apart once already (the FLAT band).
# =====================================================

# FLAT is scored against the band that was in force when the prediction was
# made (stored per row by store_prediction). calibrate_flat_threshold()
# re-derives that band every run from each market's realized return
# distribution -- NASDAQ 0.0185, NSE 0.015, Forex 0.0080 as of 2026-09-03 --
# so a hardcoded constant here silently mismatches the training labels.
# The ISNULL fallback covers pre-migration rows only.
FLAT_BAND_SQL = """
                ISNULL(p.flat_band_pct,
                       CASE WHEN p.days_ahead >= 7 THEN 0.015 ELSE 0.008 END)
"""

DIRECTION_CORRECT_SQL = f"""
            CASE
                -- 3-class evaluation: predicted_direction IS NOT NULL (v4C and later)
                WHEN p.predicted_direction = 'UP'
                     AND CAST(h.close_price AS FLOAT) > CAST(p.current_price AS FLOAT) THEN 1
                WHEN p.predicted_direction = 'DOWN'
                     AND CAST(h.close_price AS FLOAT) < CAST(p.current_price AS FLOAT) THEN 1
                WHEN p.predicted_direction = 'FLAT'
                     AND ABS(CAST(h.close_price AS FLOAT) - CAST(p.current_price AS FLOAT))
                         / NULLIF(CAST(p.current_price AS FLOAT), 0)
                         < {FLAT_BAND_SQL} THEN 1
                -- Legacy binary evaluation: predicted_direction IS NULL (pre-2026-05-25)
                WHEN p.predicted_direction IS NULL
                     AND p.predicted_change_pct > 0.01
                     AND CAST(h.close_price AS FLOAT) > CAST(p.current_price AS FLOAT) THEN 1
                WHEN p.predicted_direction IS NULL
                     AND p.predicted_change_pct < -0.01
                     AND CAST(h.close_price AS FLOAT) < CAST(p.current_price AS FLOAT) THEN 1
                WHEN p.predicted_direction IS NULL
                     AND ABS(p.predicted_change_pct) <= 0.01
                     AND CAST(p.current_price AS FLOAT) != 0
                     AND ABS(CAST(h.close_price AS FLOAT) - CAST(p.current_price AS FLOAT))
                         / CAST(p.current_price AS FLOAT) < 0.005 THEN 1
                ELSE 0
            END
"""


def price_lookup_sql(table, symbol_col):
    """
    CROSS APPLY that resolves a prediction against the last close on or before
    its target_date.

    The lower bound (trading_date >= prediction_date) matters: without it a
    ticker whose data feed stalled -- delisted, halted, renamed -- resolves
    against whatever its last bar was, potentially one from before the
    prediction was even made, producing a confidently wrong outcome. With the
    bound, such a prediction simply stays unresolved, which is the honest
    answer and is visible in the pending counts.
    """
    return f"""
        CROSS APPLY (
            SELECT TOP 1 close_price
            FROM {table}
            WHERE {symbol_col} = p.ticker
              AND trading_date <= p.target_date
              AND trading_date >= p.prediction_date
              AND close_price IS NOT NULL
              AND CAST(close_price AS FLOAT) > 0
            ORDER BY trading_date DESC
        ) h
    """


# =====================================================
# LOGGING
# =====================================================

def log(message, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = message.encode('ascii', 'ignore').decode('ascii')
    print(f"[{ts}] [{level}] {message}", flush=True)


# =====================================================
# DIAGNOSTIC: count pending before / after
# =====================================================

def count_pending(cursor, today_str):
    """Return {market: pending_count} for all markets."""
    cursor.execute("""
        SELECT market, COUNT(*) as cnt
        FROM ai_prediction_history
        WHERE target_date <= ? AND actual_price IS NULL
        GROUP BY market
        ORDER BY market
    """, (today_str,))
    return {row[0]: row[1] for row in cursor.fetchall()}


def count_anomalous_resolved(cursor):
    """Return count of resolved predictions where direction_correct IS NULL (data quality check)."""
    cursor.execute("""
        SELECT COUNT(*) FROM ai_prediction_history
        WHERE actual_price IS NOT NULL AND direction_correct IS NULL
    """)
    return cursor.fetchone()[0]


# =====================================================
# CORE BACKFILL LOGIC
# =====================================================

def backfill_market(cursor, market, config, today_str, dry_run=False):
    """
    Fill actual_price + derived columns for one market using a single batch UPDATE.

    Resolves each prediction against the last close in
    [prediction_date, target_date] -- see price_lookup_sql(). This correctly
    handles weekends, public holidays, and early market closes, and leaves
    predictions on stalled tickers unresolved rather than grading them
    against a pre-prediction bar.

    Returns: number of rows updated (0 for dry-run).
    """
    table      = config['table']
    symbol_col = config['symbol_col']

    # Pre-check
    cursor.execute("""
        SELECT COUNT(*) FROM ai_prediction_history
        WHERE market = ? AND target_date <= ? AND actual_price IS NULL
    """, (market, today_str))
    pending = cursor.fetchone()[0]

    if pending == 0:
        log(f"  {market}: 0 pending — already up to date")
        return 0

    log(f"  {market}: {pending:,} predictions pending backfill")

    if dry_run:
        log(f"  {market}: [DRY RUN] would update {pending:,} rows (no commit)")
        return 0

    update_sql = f"""
        UPDATE p
        SET
            p.actual_price = CAST(h.close_price AS FLOAT),

            p.actual_change_pct = CASE
                WHEN CAST(p.current_price AS FLOAT) = 0 THEN NULL
                -- Cap at ±9999.99 to prevent overflow on NUMERIC columns
                WHEN ABS(((CAST(h.close_price AS FLOAT) - CAST(p.current_price AS FLOAT))
                          / CAST(p.current_price AS FLOAT)) * 100) > 9999.99 THEN NULL
                ELSE ROUND(((CAST(h.close_price AS FLOAT) - CAST(p.current_price AS FLOAT))
                             / CAST(p.current_price AS FLOAT)) * 100, 4)
            END,

            p.absolute_error = ABS(
                CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT)
            ),

            p.squared_error = CASE
                WHEN ABS(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT)) > 1000000
                    THEN 999999999999
                ELSE POWER(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT), 2)
            END,

            p.percentage_error = CASE
                WHEN CAST(h.close_price AS FLOAT) = 0 THEN NULL
                -- Cap at 9999.99 to prevent overflow on NUMERIC columns
                WHEN ABS(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT))
                     / CAST(h.close_price AS FLOAT) * 100 > 9999.99 THEN 9999.99
                ELSE ROUND(
                    ABS(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT))
                    / CAST(h.close_price AS FLOAT) * 100
                , 4)
            END,

            -- 3-class direction_correct (shared with daily_prediction_job.py)
            p.direction_correct = {DIRECTION_CORRECT_SQL},

            p.updated_at = GETDATE()

        FROM ai_prediction_history p
        {price_lookup_sql(table, symbol_col)}

        WHERE p.market = ?
          AND p.target_date <= ?
          AND p.actual_price IS NULL
    """

    cursor.execute(update_sql, (market, today_str))
    updated = cursor.rowcount
    log(f"  {market}: Updated {updated:,} predictions")
    return updated


# =====================================================
# ACCURACY SUMMARY (post-backfill diagnostic)
# =====================================================

def print_accuracy_summary(cursor, markets):
    """Print per-market direction accuracy and pending counts after backfill."""
    log("")
    log("=" * 70)
    log("POST-BACKFILL ACCURACY SUMMARY")
    log("=" * 70)

    for market in markets:
        cursor.execute("""
            SELECT
                COUNT(*)                                                    AS total,
                SUM(CASE WHEN actual_price IS NULL AND target_date <= GETDATE() THEN 1 ELSE 0 END) AS still_pending,
                SUM(CASE WHEN actual_price IS NOT NULL THEN 1 ELSE 0 END)   AS has_actual,
                SUM(CASE WHEN direction_correct = 1 THEN 1 ELSE 0 END)      AS correct,
                SUM(CASE WHEN direction_correct IS NOT NULL THEN 1 ELSE 0 END) AS evaluated,
                AVG(CASE WHEN actual_price IS NOT NULL THEN actual_change_pct ELSE NULL END) AS avg_actual_chg,
                AVG(CASE WHEN actual_price IS NOT NULL THEN predicted_change_pct ELSE NULL END) AS avg_pred_chg
            FROM ai_prediction_history
            WHERE market = ?
        """, (market,))
        row = cursor.fetchone()
        total, still_pending, has_actual, correct, evaluated, avg_actual, avg_pred = row

        log(f"\n  {market}:")
        log(f"    Total predictions    : {total:,}")
        log(f"    Has actual_price     : {has_actual:,}")
        log(f"    Still pending (bug?) : {still_pending:,}")
        if evaluated and evaluated > 0:
            acc = correct / evaluated * 100
            log(f"    Direction accuracy   : {correct:,}/{evaluated:,}  ({acc:.1f}%)")
        else:
            log(f"    Direction accuracy   : No evaluated predictions yet")
        if avg_actual is not None:
            log(f"    Avg actual change    : {avg_actual:.3f}%")
        if avg_pred is not None:
            log(f"    Avg predicted change : {avg_pred:.3f}%")

    # Check for 3-class breakdown if predicted_direction column exists
    try:
        cursor.execute("""
            SELECT predicted_direction, COUNT(*) as cnt
            FROM ai_prediction_history
            WHERE predicted_direction IS NOT NULL
            GROUP BY predicted_direction
            ORDER BY predicted_direction
        """)
        rows = cursor.fetchall()
        if rows:
            log("")
            log("  3-Class Direction Breakdown (new-style predictions):")
            for direction, cnt in rows:
                log(f"    {direction:<6}: {cnt:,}")
    except Exception:
        pass  # predicted_direction column doesn't exist yet — schema migration not run

    # DOWN prediction accuracy check — bias and sub-random detection
    try:
        cursor.execute("""
            SELECT
                days_ahead,
                predicted_direction,
                COUNT(*)                                                      AS total,
                SUM(CASE WHEN direction_correct = 1 THEN 1 ELSE 0 END)       AS correct,
                AVG(CAST(actual_change_pct AS FLOAT))                         AS avg_actual
            FROM ai_prediction_history
            WHERE direction_correct IS NOT NULL
              AND predicted_direction IS NOT NULL
            GROUP BY days_ahead, predicted_direction
            ORDER BY days_ahead, predicted_direction
        """)
        rows = cursor.fetchall()
        if rows:
            log("")
            log("  Accuracy by Horizon x Direction:")
            for days_ahead, direction, total, correct, avg_actual in rows:
                if total and total > 0:
                    acc = correct / total * 100
                    avg_str = f"{avg_actual:+.2f}%" if avg_actual is not None else "n/a"
                    line = f"    {days_ahead}d {direction:<5}: {correct:,}/{total:,} ({acc:.1f}%)  avg actual: {avg_str}"
                    alerts = []
                    if direction == 'DOWN' and avg_actual is not None and avg_actual > 0:
                        alerts.append("BIAS ALERT: DOWN predicted but market goes UP on avg")
                    if direction == 'DOWN' and acc < 45.0:
                        alerts.append("SUB-RANDOM: DOWN accuracy < 45%")
                    if alerts:
                        log(line, "WARNING")
                        for alert in alerts:
                            log(f"      *** {alert} ***", "WARNING")
                    else:
                        log(line)
    except Exception:
        pass  # predicted_direction or days_ahead column not available


# =====================================================
# MAIN
# =====================================================

def run_backfill(markets_filter=None, dry_run=False):
    today_str = datetime.now().date().isoformat()

    log("=" * 70)
    log("Standalone Backfill: ai_prediction_history → actual prices")
    log(f"Date: {today_str}")
    if dry_run:
        log("MODE: DRY RUN (no writes)")
    log("=" * 70)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Determine which markets to process
    if markets_filter:
        markets_to_process = {k: v for k, v in MARKETS.items() if k in markets_filter}
        unknown = [m for m in markets_filter if m not in MARKETS]
        if unknown:
            log(f"WARNING: Unknown markets: {unknown}. Valid: {list(MARKETS.keys())}", "WARNING")
    else:
        markets_to_process = MARKETS

    # Pre-run count
    log("\nPRE-BACKFILL: Pending counts per market")
    pre_counts = count_pending(cursor, today_str)
    total_pending = sum(pre_counts.values())
    if pre_counts:
        for mkt, cnt in sorted(pre_counts.items()):
            log(f"  {mkt}: {cnt:,} pending")
    else:
        log("  None — all predictions already have actual prices!")

    anomalous = count_anomalous_resolved(cursor)
    if anomalous:
        log(f"  WARNING: {anomalous:,} resolved predictions have direction_correct=NULL (possible schema issue)", "WARNING")

    log("")
    log("RUNNING BACKFILL:")

    total_updated = 0

    try:
        for market, config in markets_to_process.items():
            updated = backfill_market(cursor, market, config, today_str, dry_run=dry_run)
            total_updated += updated

        if not dry_run:
            conn.commit()
            log(f"\nCOMMITTED: {total_updated:,} rows updated across all markets")
        else:
            log(f"\nDRY RUN COMPLETE: Would update ~{total_pending:,} rows (no commit)")

    except Exception as e:
        log(f"ERROR during backfill: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        conn.rollback()
        raise
    finally:
        # Post-run summary
        if not dry_run:
            print_accuracy_summary(cursor, list(markets_to_process.keys()))

        conn.close()

    log("")
    log("=" * 70)
    log("Backfill complete.")
    log("Next step: verify with SQL:")
    log("  SELECT market, COUNT(*) FROM ai_prediction_history")
    log("  WHERE actual_price IS NULL AND target_date <= GETDATE()")
    log("  GROUP BY market")
    log("  -- Should return 0 rows for all markets.")
    log("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backfill actual prices into ai_prediction_history for elapsed predictions."
    )
    parser.add_argument(
        "--market", type=str, nargs="+",
        help='Market(s) to process. E.g.: --market "NSE 500" "NASDAQ 100". Default: all.',
        default=None
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report pending counts without writing to the database."
    )
    args = parser.parse_args()

    try:
        run_backfill(markets_filter=args.market, dry_run=args.dry_run)
    except Exception as e:
        log(f"CRITICAL ERROR: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        sys.exit(1)
