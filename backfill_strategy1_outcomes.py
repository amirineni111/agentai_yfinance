"""
Strategy 1 - Outcome Tracking & Backfill
==========================================
Updates actual returns and prediction accuracy for all three Strategy 1 ML prediction tables:
1. ml_trading_predictions (NASDAQ 100)
2. ml_nse_trading_predictions (NSE 500)
3. forex_ml_predictions (Forex)

This script:
- Looks up actual closing prices 1, 5, and 10 trading days after each prediction
- Calculates actual returns
- Determines if the predicted direction was correct
- Updates prediction_accuracy (Correct/Incorrect/Pending)

Uses batch SQL updates for performance (handles ~34,000 predictions efficiently).

Schedule this alongside daily_prediction_job.py via Windows Task Scheduler.
"""

import pyodbc
from datetime import datetime
import traceback
import sys

# Force unbuffered output so logs appear immediately
sys.stdout.reconfigure(line_buffering=True)

# Database connection
def get_db_connection():
    """Get SQL Server database connection"""
    conn_str = (
        "DRIVER={SQL Server};"
        "SERVER=localhost\\MSSQLSERVER01;"
        "DATABASE=stockdata_db;"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)

def log_message(message, level="INFO"):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = message.encode('ascii', 'ignore').decode('ascii')
    print(f"[{timestamp}] [{level}] {message}", flush=True)


# =====================================================
# NASDAQ 100: ml_trading_predictions
# =====================================================

def backfill_nasdaq_predictions(conn):
    """
    Backfill actual returns for ml_trading_predictions (NASDAQ 100).
    Uses batch SQL with ROW_NUMBER to find Nth trading day after prediction.
    """
    log_message("=" * 60)
    log_message("NASDAQ 100: Backfilling ml_trading_predictions")
    log_message("=" * 60)
    
    cursor = conn.cursor()
    
    # Count pending
    cursor.execute("""
        SELECT COUNT(*) FROM ml_trading_predictions 
        WHERE actual_return_1d IS NULL AND trading_date <= DATEADD(day, -1, GETDATE())
    """)
    pending = cursor.fetchone()[0]
    log_message(f"Found {pending} NASDAQ predictions to backfill")
    
    if pending == 0:
        return
    
    # ---- 1-DAY RETURN ----
    log_message("  Updating 1-day returns...")
    cursor.execute("""
        UPDATE p
        SET 
            p.actual_return_1d = ((CAST(h.close_price AS FLOAT) - p.close_price) / p.close_price) * 100,
            p.direction_correct_1d = CASE 
                WHEN p.predicted_signal LIKE '%Buy%' AND CAST(h.close_price AS FLOAT) > p.close_price THEN 1
                WHEN p.predicted_signal LIKE '%Sell%' AND CAST(h.close_price AS FLOAT) < p.close_price THEN 1
                ELSE 0
            END,
            p.prediction_accuracy = CASE 
                WHEN p.predicted_signal LIKE '%Buy%' AND CAST(h.close_price AS FLOAT) > p.close_price THEN 'Correct'
                WHEN p.predicted_signal LIKE '%Sell%' AND CAST(h.close_price AS FLOAT) < p.close_price THEN 'Correct'
                ELSE 'Incorrect'
            END,
            p.updated_at = GETDATE()
        FROM ml_trading_predictions p
        INNER JOIN (
            SELECT ticker, trading_date, close_price,
                   LAG(trading_date) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_date
            FROM nasdaq_100_hist_data
        ) h ON h.ticker = p.ticker
        WHERE p.actual_return_1d IS NULL
          AND h.prev_date = p.trading_date
    """)
    updated_1d = cursor.rowcount
    conn.commit()
    log_message(f"  Updated {updated_1d} with 1-day returns")
    
    # ---- 5-DAY RETURN ----
    log_message("  Updating 5-day returns...")
    cursor.execute("""
        UPDATE p
        SET 
            p.actual_return_5d = ((CAST(future.close_price_5d AS FLOAT) - p.close_price) / p.close_price) * 100,
            p.direction_correct_5d = CASE 
                WHEN p.predicted_signal LIKE '%Buy%' AND CAST(future.close_price_5d AS FLOAT) > p.close_price THEN 1
                WHEN p.predicted_signal LIKE '%Sell%' AND CAST(future.close_price_5d AS FLOAT) < p.close_price THEN 1
                ELSE 0
            END,
            p.updated_at = GETDATE()
        FROM ml_trading_predictions p
        INNER JOIN (
            SELECT ticker, trading_date,
                   LEAD(close_price, 5) OVER (PARTITION BY ticker ORDER BY trading_date) as close_price_5d
            FROM nasdaq_100_hist_data
        ) future ON future.ticker = p.ticker AND future.trading_date = p.trading_date
        WHERE p.actual_return_5d IS NULL
          AND future.close_price_5d IS NOT NULL
    """)
    updated_5d = cursor.rowcount
    conn.commit()
    log_message(f"  Updated {updated_5d} with 5-day returns")
    
    # ---- 10-DAY RETURN ----
    log_message("  Updating 10-day returns...")
    cursor.execute("""
        UPDATE p
        SET 
            p.actual_return_10d = ((CAST(future.close_price_10d AS FLOAT) - p.close_price) / p.close_price) * 100,
            p.updated_at = GETDATE()
        FROM ml_trading_predictions p
        INNER JOIN (
            SELECT ticker, trading_date,
                   LEAD(close_price, 10) OVER (PARTITION BY ticker ORDER BY trading_date) as close_price_10d
            FROM nasdaq_100_hist_data
        ) future ON future.ticker = p.ticker AND future.trading_date = p.trading_date
        WHERE p.actual_return_10d IS NULL
          AND future.close_price_10d IS NOT NULL
    """)
    updated_10d = cursor.rowcount
    conn.commit()
    log_message(f"  Updated {updated_10d} with 10-day returns")
    
    log_message(f"NASDAQ 100 complete: 1d={updated_1d}, 5d={updated_5d}, 10d={updated_10d}")


# =====================================================
# NSE 500: ml_nse_trading_predictions
# =====================================================

def backfill_nse_predictions(conn):
    """
    Backfill actual returns for ml_nse_trading_predictions (NSE 500).
    Uses batch SQL with ROW_NUMBER to find Nth trading day after prediction.
    """
    log_message("=" * 60)
    log_message("NSE 500: Backfilling ml_nse_trading_predictions")
    log_message("=" * 60)
    
    cursor = conn.cursor()
    
    # Count pending
    cursor.execute("""
        SELECT COUNT(*) FROM ml_nse_trading_predictions 
        WHERE actual_return_1d IS NULL AND trading_date <= DATEADD(day, -1, GETDATE())
    """)
    pending = cursor.fetchone()[0]
    log_message(f"Found {pending} NSE predictions to backfill")
    
    if pending == 0:
        return
    
    # ---- 1-DAY RETURN ----
    log_message("  Updating 1-day returns...")
    cursor.execute("""
        UPDATE p
        SET 
            p.actual_return_1d = ((CAST(h.close_price AS FLOAT) - p.close_price) / p.close_price) * 100,
            p.direction_correct_1d = CASE 
                WHEN p.predicted_signal = 'Buy' AND CAST(h.close_price AS FLOAT) > p.close_price THEN 1
                WHEN p.predicted_signal = 'Sell' AND CAST(h.close_price AS FLOAT) < p.close_price THEN 1
                ELSE 0
            END,
            p.prediction_accuracy = CASE 
                WHEN p.predicted_signal = 'Buy' AND CAST(h.close_price AS FLOAT) > p.close_price THEN 'Correct'
                WHEN p.predicted_signal = 'Sell' AND CAST(h.close_price AS FLOAT) < p.close_price THEN 'Correct'
                ELSE 'Incorrect'
            END,
            p.updated_at = GETDATE()
        FROM ml_nse_trading_predictions p
        INNER JOIN (
            SELECT ticker, trading_date, close_price,
                   LAG(trading_date) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_date
            FROM nse_500_hist_data
        ) h ON h.ticker = p.ticker
        WHERE p.actual_return_1d IS NULL
          AND h.prev_date = p.trading_date
    """)
    updated_1d = cursor.rowcount
    conn.commit()
    log_message(f"  Updated {updated_1d} with 1-day returns")
    
    # ---- 5-DAY RETURN ----
    log_message("  Updating 5-day returns...")
    cursor.execute("""
        UPDATE p
        SET 
            p.actual_return_5d = ((CAST(future.close_price_5d AS FLOAT) - p.close_price) / p.close_price) * 100,
            p.direction_correct_5d = CASE 
                WHEN p.predicted_signal = 'Buy' AND CAST(future.close_price_5d AS FLOAT) > p.close_price THEN 1
                WHEN p.predicted_signal = 'Sell' AND CAST(future.close_price_5d AS FLOAT) < p.close_price THEN 1
                ELSE 0
            END,
            p.updated_at = GETDATE()
        FROM ml_nse_trading_predictions p
        INNER JOIN (
            SELECT ticker, trading_date,
                   LEAD(close_price, 5) OVER (PARTITION BY ticker ORDER BY trading_date) as close_price_5d
            FROM nse_500_hist_data
        ) future ON future.ticker = p.ticker AND future.trading_date = p.trading_date
        WHERE p.actual_return_5d IS NULL
          AND future.close_price_5d IS NOT NULL
    """)
    updated_5d = cursor.rowcount
    conn.commit()
    log_message(f"  Updated {updated_5d} with 5-day returns")
    
    # ---- 10-DAY RETURN ----
    log_message("  Updating 10-day returns...")
    cursor.execute("""
        UPDATE p
        SET 
            p.actual_return_10d = ((CAST(future.close_price_10d AS FLOAT) - p.close_price) / p.close_price) * 100,
            p.updated_at = GETDATE()
        FROM ml_nse_trading_predictions p
        INNER JOIN (
            SELECT ticker, trading_date,
                   LEAD(close_price, 10) OVER (PARTITION BY ticker ORDER BY trading_date) as close_price_10d
            FROM nse_500_hist_data
        ) future ON future.ticker = p.ticker AND future.trading_date = p.trading_date
        WHERE p.actual_return_10d IS NULL
          AND future.close_price_10d IS NOT NULL
    """)
    updated_10d = cursor.rowcount
    conn.commit()
    log_message(f"  Updated {updated_10d} with 10-day returns")
    
    log_message(f"NSE 500 complete: 1d={updated_1d}, 5d={updated_5d}, 10d={updated_10d}")


# =====================================================
# FOREX: forex_ml_predictions
# =====================================================

def backfill_forex_predictions(conn):
    """
    Backfill actual returns for forex_ml_predictions (Forex).
    Uses forex_hist_data (symbol column, close_price is DECIMAL).
    """
    log_message("=" * 60)
    log_message("FOREX: Backfilling forex_ml_predictions")
    log_message("=" * 60)
    
    cursor = conn.cursor()
    
    # Count pending
    cursor.execute("""
        SELECT COUNT(*) FROM forex_ml_predictions 
        WHERE actual_return_1d IS NULL 
          AND CAST(prediction_date AS date) <= DATEADD(day, -1, GETDATE())
          AND close_price IS NOT NULL AND close_price > 0
    """)
    pending = cursor.fetchone()[0]
    log_message(f"Found {pending} Forex predictions to backfill")
    
    if pending == 0:
        return
    
    # ---- 1-DAY RETURN ----
    log_message("  Updating 1-day returns...")
    cursor.execute("""
        UPDATE p
        SET 
            p.actual_return_1d = ((CAST(h.close_price AS FLOAT) - CAST(p.close_price AS FLOAT)) / CAST(p.close_price AS FLOAT)) * 100,
            p.direction_correct_1d = CASE 
                WHEN p.predicted_signal = 'BUY' AND CAST(h.close_price AS FLOAT) > CAST(p.close_price AS FLOAT) THEN 1
                WHEN p.predicted_signal = 'SELL' AND CAST(h.close_price AS FLOAT) < CAST(p.close_price AS FLOAT) THEN 1
                WHEN p.predicted_signal = 'HOLD' AND ABS(CAST(h.close_price AS FLOAT) - CAST(p.close_price AS FLOAT)) / CAST(p.close_price AS FLOAT) < 0.01 THEN 1
                ELSE 0
            END,
            p.prediction_accuracy = CASE 
                WHEN p.predicted_signal = 'BUY' AND CAST(h.close_price AS FLOAT) > CAST(p.close_price AS FLOAT) THEN 'Correct'
                WHEN p.predicted_signal = 'SELL' AND CAST(h.close_price AS FLOAT) < CAST(p.close_price AS FLOAT) THEN 'Correct'
                WHEN p.predicted_signal = 'HOLD' AND ABS(CAST(h.close_price AS FLOAT) - CAST(p.close_price AS FLOAT)) / CAST(p.close_price AS FLOAT) < 0.01 THEN 'Correct'
                ELSE 'Incorrect'
            END,
            p.updated_at = GETDATE()
        FROM forex_ml_predictions p
        INNER JOIN (
            SELECT symbol, trading_date, close_price,
                   LAG(trading_date) OVER (PARTITION BY symbol ORDER BY trading_date) as prev_date
            FROM forex_hist_data
        ) h ON h.symbol = p.currency_pair
        WHERE p.actual_return_1d IS NULL
          AND p.close_price IS NOT NULL AND p.close_price > 0
          AND h.prev_date = CAST(p.prediction_date AS date)
    """)
    updated_1d = cursor.rowcount
    conn.commit()
    log_message(f"  Updated {updated_1d} with 1-day returns")
    
    # ---- 5-DAY RETURN ----
    log_message("  Updating 5-day returns...")
    cursor.execute("""
        UPDATE p
        SET 
            p.actual_return_5d = ((CAST(future.close_price_5d AS FLOAT) - CAST(p.close_price AS FLOAT)) / CAST(p.close_price AS FLOAT)) * 100,
            p.direction_correct_5d = CASE 
                WHEN p.predicted_signal = 'BUY' AND CAST(future.close_price_5d AS FLOAT) > CAST(p.close_price AS FLOAT) THEN 1
                WHEN p.predicted_signal = 'SELL' AND CAST(future.close_price_5d AS FLOAT) < CAST(p.close_price AS FLOAT) THEN 1
                WHEN p.predicted_signal = 'HOLD' AND ABS(CAST(future.close_price_5d AS FLOAT) - CAST(p.close_price AS FLOAT)) / CAST(p.close_price AS FLOAT) < 0.01 THEN 1
                ELSE 0
            END,
            p.updated_at = GETDATE()
        FROM forex_ml_predictions p
        INNER JOIN (
            SELECT symbol, trading_date,
                   LEAD(close_price, 5) OVER (PARTITION BY symbol ORDER BY trading_date) as close_price_5d
            FROM forex_hist_data
        ) future ON future.symbol = p.currency_pair AND future.trading_date = CAST(p.prediction_date AS date)
        WHERE p.actual_return_5d IS NULL
          AND p.close_price IS NOT NULL AND p.close_price > 0
          AND future.close_price_5d IS NOT NULL
    """)
    updated_5d = cursor.rowcount
    conn.commit()
    log_message(f"  Updated {updated_5d} with 5-day returns")
    
    # ---- 10-DAY RETURN ----
    log_message("  Updating 10-day returns...")
    cursor.execute("""
        UPDATE p
        SET 
            p.actual_return_10d = ((CAST(future.close_price_10d AS FLOAT) - CAST(p.close_price AS FLOAT)) / CAST(p.close_price AS FLOAT)) * 100,
            p.updated_at = GETDATE()
        FROM forex_ml_predictions p
        INNER JOIN (
            SELECT symbol, trading_date,
                   LEAD(close_price, 10) OVER (PARTITION BY symbol ORDER BY trading_date) as close_price_10d
            FROM forex_hist_data
        ) future ON future.symbol = p.currency_pair AND future.trading_date = CAST(p.prediction_date AS date)
        WHERE p.actual_return_10d IS NULL
          AND p.close_price IS NOT NULL AND p.close_price > 0
          AND future.close_price_10d IS NOT NULL
    """)
    updated_10d = cursor.rowcount
    conn.commit()
    log_message(f"  Updated {updated_10d} with 10-day returns")
    
    log_message(f"FOREX complete: 1d={updated_1d}, 5d={updated_5d}, 10d={updated_10d}")


# =====================================================
# SUMMARY REPORT
# =====================================================

def print_accuracy_summary(conn):
    """Print accuracy summary across all three Strategy 1 tables after backfill."""
    log_message("")
    log_message("=" * 60)
    log_message("STRATEGY 1 - ACCURACY SUMMARY")
    log_message("=" * 60)
    
    cursor = conn.cursor()
    
    tables = [
        ("NASDAQ 100", "ml_trading_predictions"),
        ("NSE 500", "ml_nse_trading_predictions"),
        ("FOREX", "forex_ml_predictions"),
    ]
    
    for label, table in tables:
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN actual_return_1d IS NOT NULL THEN 1 ELSE 0 END) as has_1d,
                SUM(CASE WHEN direction_correct_1d = 1 THEN 1 ELSE 0 END) as correct_1d,
                SUM(CASE WHEN direction_correct_1d IS NOT NULL THEN 1 ELSE 0 END) as evaluated_1d,
                SUM(CASE WHEN direction_correct_5d = 1 THEN 1 ELSE 0 END) as correct_5d,
                SUM(CASE WHEN direction_correct_5d IS NOT NULL THEN 1 ELSE 0 END) as evaluated_5d,
                SUM(CASE WHEN actual_return_10d IS NOT NULL THEN 1 ELSE 0 END) as has_10d,
                AVG(actual_return_1d) as avg_return_1d,
                AVG(actual_return_5d) as avg_return_5d
            FROM {table}
        """)
        row = cursor.fetchone()
        
        log_message(f"\n  {label} ({table}):")
        log_message(f"    Total predictions: {row[0]}")
        
        if row[3] and row[3] > 0:
            acc_1d = row[2] / row[3] * 100
            log_message(f"    1-day direction:  {row[2]}/{row[3]} correct ({acc_1d:.1f}%)")
        else:
            log_message(f"    1-day direction:  No evaluated predictions yet")
        
        if row[5] and row[5] > 0:
            acc_5d = row[4] / row[5] * 100
            log_message(f"    5-day direction:  {row[4]}/{row[5]} correct ({acc_5d:.1f}%)")
        else:
            log_message(f"    5-day direction:  No evaluated predictions yet")
        
        if row[6]:
            log_message(f"    10-day data:      {row[6]} predictions with returns")
        
        if row[7] is not None:
            log_message(f"    Avg 1d return:    {row[7]:.3f}%")
        if row[8] is not None:
            log_message(f"    Avg 5d return:    {row[8]:.3f}%")
        
        # Pending count
        still_pending = row[0] - (row[3] if row[3] else 0)
        if still_pending > 0:
            log_message(f"    Still pending:    {still_pending} (too recent or no price data)")


# =====================================================
# MAIN
# =====================================================

def run_strategy1_backfill():
    """Main function to backfill all Strategy 1 prediction outcomes."""
    log_message("=" * 80)
    log_message("Starting Strategy 1 Outcome Tracking & Backfill")
    log_message("Covers: ml_trading_predictions, ml_nse_trading_predictions, forex_ml_predictions")
    log_message("=" * 80)
    
    conn = get_db_connection()
    
    try:
        backfill_nasdaq_predictions(conn)
        backfill_nse_predictions(conn)
        backfill_forex_predictions(conn)
        print_accuracy_summary(conn)
        
    except Exception as e:
        log_message(f"Error during backfill: {str(e)}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        raise
    finally:
        conn.close()
    
    log_message("")
    log_message("=" * 80)
    log_message("Strategy 1 Backfill Completed Successfully!")
    log_message("=" * 80)


if __name__ == "__main__":
    try:
        run_strategy1_backfill()
    except Exception as e:
        log_message(f"CRITICAL ERROR: {str(e)}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        exit(1)
