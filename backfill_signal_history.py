"""
One-Time Historical Signal Backfill Script
===========================================
Backfills signal_tracking_history with last 70 days of historical data
prior to Jan 19, 2026.

This script:
1. Retrieves historical signals from crossover views for each day
2. Stores signals in signal_tracking_history
3. Calculates actual 7d, 14d, 30d results since dates have passed
4. Updates win/loss results automatically
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

MIN_SIGNAL_STRENGTH = 2
START_DATE = datetime(2026, 1, 19).date()
BACKFILL_DAYS = 70

def log_message(message, level="INFO"):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = message.encode('ascii', 'ignore').decode('ascii')
    print(f"[{timestamp}] [{level}] {message}")

def get_historical_signals(market, signal_date):
    """Get Double/Triple strategy signals for a specific market and date"""
    conn = get_db_connection()
    
    # Determine the view name based on market
    view_name_map = {
        'NSE 500': 'vw_crossover_signals_NSE_500',
        'NASDAQ 100': 'vw_crossover_signals_NASDAQ_100',
        'Forex': 'vw_crossover_signals_Forex'
    }
    
    view_name = view_name_map.get(market)
    if not view_name:
        log_message(f"Unknown market: {market}", "ERROR")
        conn.close()
        return pd.DataFrame()
    
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
        sma_trade_signal,
        stoch_signal,
        fib_signal,
        pattern_signal
    FROM {view_name}
    WHERE trading_date = ?
    """
    
    try:
        df = pd.read_sql(query, conn, params=[str(signal_date)])
        conn.close()
        return df
    except Exception as e:
        log_message(f"Error loading signals for {market} on {signal_date}: {str(e)}", "ERROR")
        conn.close()
        return pd.DataFrame()

def determine_signal_type(bullish_count, bearish_count):
    """Determine signal type and strength"""
    if bullish_count >= MIN_SIGNAL_STRENGTH and bullish_count > bearish_count:
        return 'BULLISH', int(bullish_count)
    elif bearish_count >= MIN_SIGNAL_STRENGTH and bearish_count > bullish_count:
        return 'BEARISH', int(bearish_count)
    else:
        return None, 0

def get_actual_price(market, ticker, target_date):
    """Get actual price on or after target date"""
    conn = get_db_connection()
    config = MARKETS[market]
    
    query = f"""
    SELECT TOP 1 close_price, trading_date
    FROM {config['table']}
    WHERE {config['symbol_col']} = ? 
      AND trading_date >= ?
    ORDER BY trading_date ASC
    """
    
    cursor = conn.cursor()
    try:
        cursor.execute(query, (ticker, str(target_date)))
        result = cursor.fetchone()
        conn.close()
        if result:
            return float(result[0]), result[1]
        return None, None
    except Exception as e:
        log_message(f"Error getting price for {ticker} on {target_date}: {str(e)}", "ERROR")
        conn.close()
        return None, None

def calculate_result(signal_type, price_change_pct):
    """Determine if signal was WIN, LOSS, or NEUTRAL"""
    if price_change_pct is None:
        return 'PENDING'
    
    # For BULLISH signals, positive change is WIN
    # For BEARISH signals, negative change is WIN
    if signal_type == 'BULLISH':
        if price_change_pct >= 2.0:  # 2% threshold for win
            return 'WIN'
        elif price_change_pct <= -2.0:
            return 'LOSS'
        else:
            return 'NEUTRAL'
    else:  # BEARISH
        if price_change_pct <= -2.0:  # -2% threshold for win (price went down)
            return 'WIN'
        elif price_change_pct >= 2.0:
            return 'LOSS'
        else:
            return 'NEUTRAL'

def store_historical_signal(conn, market, ticker, company_name, signal_date, 
                            signal_type, signal_strength, signal_price, 
                            macd_sig, rsi_sig, bb_sig, sma_sig, stoch_sig, 
                            fib_sig, pattern_sig):
    """Store historical signal with calculated results"""
    
    cursor = conn.cursor()
    
    # Calculate target dates
    target_7d = signal_date + timedelta(days=7)
    target_14d = signal_date + timedelta(days=14)
    target_30d = signal_date + timedelta(days=30)
    
    # Get actual prices for target dates
    actual_price_7d, actual_date_7d = get_actual_price(market, ticker, target_7d)
    actual_price_14d, actual_date_14d = get_actual_price(market, ticker, target_14d)
    actual_price_30d, actual_date_30d = get_actual_price(market, ticker, target_30d)
    
    # Calculate price changes
    actual_change_7d = ((actual_price_7d - signal_price) / signal_price * 100) if actual_price_7d else None
    actual_change_14d = ((actual_price_14d - signal_price) / signal_price * 100) if actual_price_14d else None
    actual_change_30d = ((actual_price_30d - signal_price) / signal_price * 100) if actual_price_30d else None
    
    # Determine results
    result_7d = calculate_result(signal_type, actual_change_7d)
    result_14d = calculate_result(signal_type, actual_change_14d)
    result_30d = calculate_result(signal_type, actual_change_30d)
    
    query = """
    INSERT INTO signal_tracking_history 
    (market, ticker, company_name, signal_date, signal_type, signal_strength,
     signal_price, macd_signal, rsi_signal, bb_signal, sma_signal,
     stoch_signal, fib_signal, pattern_signal,
     target_date_7d, actual_price_7d, actual_change_7d, result_7d,
     target_date_14d, actual_price_14d, actual_change_14d, result_14d,
     target_date_30d, actual_price_30d, actual_change_30d, result_30d,
     signal_status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'HISTORICAL')
    """
    
    try:
        cursor.execute(query, (
            market, ticker, company_name, str(signal_date), signal_type, signal_strength,
            float(signal_price), macd_sig, rsi_sig, bb_sig, sma_sig,
            stoch_sig, fib_sig, pattern_sig,
            str(target_7d), actual_price_7d, actual_change_7d, result_7d,
            str(target_14d), actual_price_14d, actual_change_14d, result_14d,
            str(target_30d), actual_price_30d, actual_change_30d, result_30d
        ))
        conn.commit()
        return True
    except Exception as e:
        log_message(f"Error storing signal for {ticker} on {signal_date}: {str(e)}", "ERROR")
        return False

def backfill_historical_data():
    """Main function to backfill historical signals"""
    
    log_message("="*80)
    log_message("HISTORICAL SIGNAL BACKFILL - STARTING")
    log_message("="*80)
    
    # Calculate date range (70 days before Jan 19, 2026)
    end_date = START_DATE - timedelta(days=1)  # Jan 18, 2026
    start_date = end_date - timedelta(days=BACKFILL_DAYS - 1)  # ~Nov 10, 2025
    
    log_message(f"Backfilling from {start_date} to {end_date} ({BACKFILL_DAYS} days)")
    log_message(f"Markets: {', '.join(MARKETS.keys())}")
    log_message(f"Minimum signal strength: {MIN_SIGNAL_STRENGTH}")
    
    conn = get_db_connection()
    
    total_signals = 0
    total_days = 0
    
    # Process each day
    current_date = start_date
    while current_date <= end_date:
        log_message(f"\nProcessing {current_date}...")
        day_signals = 0
        
        # Process each market
        for market in MARKETS.keys():
            # Get signals for this market and date
            df = get_historical_signals(market, current_date)
            
            if df.empty:
                log_message(f"  {market}: No data available", "WARNING")
                continue
            
            market_signals = 0
            
            # Process each ticker
            for idx, row in df.iterrows():
                signal_type, signal_strength = determine_signal_type(
                    row['bullish_count'], 
                    row['bearish_count']
                )
                
                if signal_type is None:
                    continue  # Skip weak signals
                
                # Store the signal with results
                success = store_historical_signal(
                    conn,
                    market=market,
                    ticker=row['ticker'],
                    company_name=row.get('company_name', ''),
                    signal_date=current_date,
                    signal_type=signal_type,
                    signal_strength=signal_strength,
                    signal_price=row['close_price'],
                    macd_sig=str(row.get('macd_signal', ''))[:100],
                    rsi_sig=str(row.get('rsi_trade_signal', ''))[:100],
                    bb_sig=str(row.get('bb_trade_signal', ''))[:100],
                    sma_sig=str(row.get('sma_trade_signal', ''))[:100],
                    stoch_sig=str(row.get('stoch_signal', ''))[:100],
                    fib_sig=str(row.get('fib_signal', ''))[:100],
                    pattern_sig=str(row.get('pattern_signal', ''))[:100]
                )
                
                if success:
                    market_signals += 1
                    day_signals += 1
            
            if market_signals > 0:
                log_message(f"  {market}: {market_signals} signals stored")
        
        total_signals += day_signals
        total_days += 1
        
        if day_signals == 0:
            log_message(f"  Total: No signals found for {current_date}", "WARNING")
        
        # Move to next day
        current_date += timedelta(days=1)
    
    conn.close()
    
    # Summary
    log_message("\n" + "="*80)
    log_message("BACKFILL COMPLETE")
    log_message("="*80)
    log_message(f"Days processed: {total_days}")
    log_message(f"Total signals stored: {total_signals}")
    log_message(f"Average signals per day: {total_signals/total_days:.1f}")
    
    # Show some statistics
    log_message("\nVerifying stored data...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            market,
            COUNT(*) as total,
            SUM(CASE WHEN result_7d = 'WIN' THEN 1 ELSE 0 END) as wins_7d,
            SUM(CASE WHEN result_7d = 'LOSS' THEN 1 ELSE 0 END) as losses_7d,
            CAST(SUM(CASE WHEN result_7d = 'WIN' THEN 1 ELSE 0 END) AS FLOAT) * 100 / 
                NULLIF(COUNT(*), 0) as win_rate_7d
        FROM signal_tracking_history
        WHERE signal_status = 'HISTORICAL'
        GROUP BY market
        ORDER BY market
    """)
    
    log_message("\nHistorical Signal Statistics (7-day results):")
    log_message(f"{'Market':<15} {'Total':<10} {'Wins':<10} {'Losses':<10} {'Win Rate':<10}")
    log_message("-"*60)
    
    for row in cursor.fetchall():
        market, total, wins, losses, win_rate = row
        win_rate_str = f"{win_rate:.1f}%" if win_rate else "N/A"
        log_message(f"{market:<15} {total:<10} {wins:<10} {losses:<10} {win_rate_str:<10}")
    
    conn.close()
    log_message("\nBackfill process completed successfully!")

if __name__ == "__main__":
    try:
        backfill_historical_data()
    except Exception as e:
        log_message(f"FATAL ERROR: {str(e)}", "ERROR")
        import traceback
        traceback.print_exc()
