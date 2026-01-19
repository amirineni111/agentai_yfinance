"""
Daily Double/Triple Strategy Signal Tracking Job
=================================================
Runs daily to:
1. Detect current Double/Triple strategy signals
2. Store signals in database
3. Update actual results for past signals (7, 14, 30 days)
4. Calculate win/loss accuracy

Schedule this to run daily via Windows Task Scheduler
"""

import pandas as pd
import numpy as np
import pyodbc
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

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

# Configuration
MARKETS = {
    'NSE 500': {'table': 'nse_500_hist_data', 'symbol_col': 'ticker'},
    'NASDAQ 100': {'table': 'nasdaq_100_hist_data', 'symbol_col': 'ticker'},
    'Forex': {'table': 'forex_hist_data', 'symbol_col': 'symbol'}
}

MIN_SIGNAL_STRENGTH = 2  # Minimum 2 indicators aligned
SIGNAL_TIMEFRAMES = [7, 14, 30]  # Check results after 7, 14, and 30 days

def log_message(message, level="INFO"):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = message.encode('ascii', 'ignore').decode('ascii')
    print(f"[{timestamp}] [{level}] {message}")

def get_latest_signals(market, signal_date):
    """Get Double/Triple strategy signals for a specific market and date"""
    conn = get_db_connection()
    
    # Query the crossover signals view
    query = f"""
    SELECT 
        ticker,
        company_name,
        close_price,
        bullish_count,
        bearish_count,
        bb_trade_signal,
        macd_signal,
        rsi_trade_signal,
        sma_trade_signal
    FROM vw_crossover_signals_{market.replace(' ', '_').replace(' ', '')}
    WHERE trading_date = ?
    """
    
    try:
        df = pd.read_sql(query, conn, params=[str(signal_date)])
        conn.close()
        return df
    except Exception as e:
        log_message(f"Error loading signals for {market}: {str(e)}", "ERROR")
        conn.close()
        return pd.DataFrame()

def determine_signal_type(bullish_count, bearish_count):
    """Determine signal type and strength"""
    if bullish_count >= MIN_SIGNAL_STRENGTH and bullish_count > bearish_count:
        return 'BULLISH', bullish_count
    elif bearish_count >= MIN_SIGNAL_STRENGTH and bearish_count > bullish_count:
        return 'BEARISH', bearish_count
    else:
        return None, 0

def store_signal(conn, market, ticker, company_name, signal_date, signal_type, 
                signal_strength, signal_price, macd_sig, rsi_sig, bb_sig, sma_sig):
    """Store signal in database"""
    
    cursor = conn.cursor()
    
    # Calculate target dates
    target_7d = signal_date + timedelta(days=7)
    target_14d = signal_date + timedelta(days=14)
    target_30d = signal_date + timedelta(days=30)
    
    query = """
    INSERT INTO signal_tracking_history 
    (market, ticker, company_name, signal_date, signal_type, signal_strength,
     signal_price, macd_signal, rsi_signal, bb_signal, sma_signal,
     target_date_7d, target_date_14d, target_date_30d, signal_status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEW')
    """
    
    cursor.execute(query, (
        market, ticker, company_name, str(signal_date), signal_type, signal_strength,
        float(signal_price), macd_sig, rsi_sig, bb_sig, sma_sig,
        str(target_7d), str(target_14d), str(target_30d)
    ))
    
    conn.commit()

def get_actual_price(market, ticker, target_date):
    """Get actual price on or after target date"""
    conn = get_db_connection()
    config = MARKETS[market]
    
    query = f"""
    SELECT TOP 1 close_price
    FROM {config['table']}
    WHERE {config['symbol_col']} = ? 
      AND trading_date >= ?
    ORDER BY trading_date ASC
    """
    
    cursor = conn.cursor()
    cursor.execute(query, (ticker, str(target_date)))
    result = cursor.fetchone()
    conn.close()
    
    return float(result[0]) if result else None

def update_signal_results(conn):
    """Update actual results for signals that have reached their target dates"""
    today = datetime.now().date()
    
    cursor = conn.cursor()
    
    # Get pending signals
    query = """
    SELECT signal_id, market, ticker, signal_date, signal_type, signal_price,
           target_date_7d, result_7d,
           target_date_14d, result_14d,
           target_date_30d, result_30d
    FROM signal_tracking_history
    WHERE result_7d IS NULL OR result_14d IS NULL OR result_30d IS NULL
    """
    
    cursor.execute(query)
    pending_signals = cursor.fetchall()
    
    log_message(f"Found {len(pending_signals)} signals to update")
    
    updated_count = 0
    
    for signal in pending_signals:
        (signal_id, market, ticker, signal_date, signal_type, signal_price,
         target_7d, result_7d, target_14d, result_14d, target_30d, result_30d) = signal
        
        signal_date = signal_date.date() if hasattr(signal_date, 'date') else signal_date
        target_7d = target_7d.date() if hasattr(target_7d, 'date') else target_7d
        target_14d = target_14d.date() if hasattr(target_14d, 'date') else target_14d
        target_30d = target_30d.date() if hasattr(target_30d, 'date') else target_30d
        
        signal_price = float(signal_price)
        
        # Update 7-day result
        if result_7d is None and target_7d <= today:
            actual_price_7d = get_actual_price(market, ticker, target_7d)
            if actual_price_7d:
                change_pct = ((actual_price_7d - signal_price) / signal_price) * 100
                
                # Determine win/loss based on signal type
                if signal_type == 'BULLISH':
                    result = 'WIN' if change_pct > 0 else 'LOSS' if change_pct < 0 else 'NEUTRAL'
                else:  # BEARISH
                    result = 'WIN' if change_pct < 0 else 'LOSS' if change_pct > 0 else 'NEUTRAL'
                
                cursor.execute("""
                    UPDATE signal_tracking_history
                    SET actual_price_7d = ?,
                        actual_change_7d = ?,
                        result_7d = ?,
                        updated_at = GETDATE()
                    WHERE signal_id = ?
                """, (actual_price_7d, change_pct, result, signal_id))
                updated_count += 1
        
        # Update 14-day result
        if result_14d is None and target_14d <= today:
            actual_price_14d = get_actual_price(market, ticker, target_14d)
            if actual_price_14d:
                change_pct = ((actual_price_14d - signal_price) / signal_price) * 100
                
                if signal_type == 'BULLISH':
                    result = 'WIN' if change_pct > 0 else 'LOSS' if change_pct < 0 else 'NEUTRAL'
                else:
                    result = 'WIN' if change_pct < 0 else 'LOSS' if change_pct > 0 else 'NEUTRAL'
                
                cursor.execute("""
                    UPDATE signal_tracking_history
                    SET actual_price_14d = ?,
                        actual_change_14d = ?,
                        result_14d = ?,
                        updated_at = GETDATE()
                    WHERE signal_id = ?
                """, (actual_price_14d, change_pct, result, signal_id))
                updated_count += 1
        
        # Update 30-day result
        if result_30d is None and target_30d <= today:
            actual_price_30d = get_actual_price(market, ticker, target_30d)
            if actual_price_30d:
                change_pct = ((actual_price_30d - signal_price) / signal_price) * 100
                
                if signal_type == 'BULLISH':
                    result = 'WIN' if change_pct > 0 else 'LOSS' if change_pct < 0 else 'NEUTRAL'
                else:
                    result = 'WIN' if change_pct < 0 else 'LOSS' if change_pct > 0 else 'NEUTRAL'
                
                cursor.execute("""
                    UPDATE signal_tracking_history
                    SET actual_price_30d = ?,
                        actual_change_30d = ?,
                        result_30d = ?,
                        updated_at = GETDATE()
                    WHERE signal_id = ?
                """, (actual_price_30d, change_pct, result, signal_id))
                updated_count += 1
    
    conn.commit()
    log_message(f"Updated {updated_count} signal results")

def run_daily_signal_tracking():
    """Main function to run daily signal tracking"""
    log_message("=" * 80)
    log_message("Starting Daily Double/Triple Strategy Signal Tracking Job")
    log_message("=" * 80)
    
    conn = get_db_connection()
    signal_date = datetime.now().date()
    
    # Step 1: Update past signal results
    log_message("Step 1: Updating results for past signals...")
    update_signal_results(conn)
    
    # Step 2: Detect and store today's signals
    log_message(f"\nStep 2: Detecting signals for {signal_date}...")
    
    total_signals = 0
    
    for market in MARKETS.keys():
        log_message(f"\nProcessing {market}...")
        
        signals_df = get_latest_signals(market, signal_date)
        
        if signals_df.empty:
            log_message(f"  No signals found for {market}", "WARNING")
            continue
        
        market_signals = 0
        
        for _, row in signals_df.iterrows():
            signal_type, strength = determine_signal_type(
                row.get('bullish_count', 0),
                row.get('bearish_count', 0)
            )
            
            if signal_type:
                store_signal(
                    conn, market, row['ticker'], row.get('company_name', ''),
                    signal_date, signal_type, strength, row['close_price'],
                    row.get('macd_signal', 'N/A'),
                    row.get('rsi_trade_signal', 'N/A'),
                    row.get('bb_trade_signal', 'N/A'),
                    row.get('sma_trade_signal', 'N/A')
                )
                market_signals += 1
                total_signals += 1
        
        log_message(f"  Found {market_signals} signals in {market}")
    
    conn.close()
    
    log_message("=" * 80)
    log_message(f"Signal Tracking Job Completed Successfully!")
    log_message(f"Total Signals Detected Today: {total_signals}")
    log_message("=" * 80)

if __name__ == "__main__":
    try:
        run_daily_signal_tracking()
    except Exception as e:
        log_message(f"CRITICAL ERROR: {str(e)}", "ERROR")
        import traceback
        log_message(traceback.format_exc(), "ERROR")
        exit(1)
