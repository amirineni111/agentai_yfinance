import streamlit as st
import pyodbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import io
from io import BytesIO
import base64

# Configure Streamlit page settings first
st.set_page_config(
    page_title="📈 Advanced Trading Dashboard", 
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://docs.streamlit.io/library/api-reference',
        'Report a bug': None,
        'About': "Advanced Trading Dashboard with Interactive Charts"
    }
)

# ----------------------------
# DB CONNECTION
# ----------------------------
@st.cache_resource
def get_connection_pool():
    """Create a connection pool to manage database connections more efficiently"""
    # SQL Server Authentication for remote access
    # Works from any machine on the same network
    connection_string = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost\\MSSQLSERVER01;'  # Use 192.168.87.27\\MSSQLSERVER01 for remote access
        'DATABASE=stockdata_db;'
        'UID=remote_user;'  # SQL Server authentication
        'PWD=YourStrongPassword123!;'  # SQL Server password
        'MARS_Connection=yes;'  # Enable Multiple Active Result Sets
        'Connection Timeout=900;'  # 15 minutes for large queries
        'Command Timeout=900;'  # 15 minutes for large queries
        'MultipleActiveResultSets=true;'  # Additional MARS setting
        'Pooling=true;'  # Enable connection pooling
    )
    return connection_string

def reset_database_connections():
    """Reset all database connections by clearing the cache"""
    try:
        get_connection_pool.clear()
        st.cache_data.clear()
        st.success("Database connections reset successfully!")
    except Exception as e:
        st.error(f"Error resetting connections: {str(e)}")

def get_connection():
    """Create a new database connection with enhanced error handling"""
    try:
        connection_string = get_connection_pool()
        conn = pyodbc.connect(connection_string)
        conn.timeout = 900  # 15 minutes for large queries
        conn.autocommit = True  # Prevent transaction locks
        return conn
    except Exception as e:
        st.error(f"Database connection error: {str(e)}")
        return None

def execute_query_safe(query: str, params: list = None) -> pd.DataFrame:
    """
    Safe database query execution with proper error handling and connection management
    """
    conn = None
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = get_connection()
            if conn is None:
                st.error("Failed to establish database connection")
                return pd.DataFrame()
            
            if params:
                df = pd.read_sql(query, conn, params=params)
            else:
                df = pd.read_sql(query, conn)
            
            return df
            
        except Exception as e:
            retry_count += 1
            error_msg = str(e)
            
            if "Connection is busy with results for another command" in error_msg:
                st.warning(f"Database busy, retrying... (attempt {retry_count}/{max_retries})")
                if retry_count < max_retries:
                    import time
                    time.sleep(1)  # Wait 1 second before retry
                    continue
            
            if retry_count >= max_retries:
                st.error(f"Database query failed after {max_retries} attempts: {error_msg}")
                return pd.DataFrame()
                
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass  # Ignore close errors
    
    return pd.DataFrame()

def execute_query(query: str, params: list = None) -> pd.DataFrame:
    """
    Centralized function to execute database queries with proper connection handling
    """
    conn = None
    try:
        conn = get_connection()
        if params:
            df = pd.read_sql(query, conn, params=params)
        else:
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"Database query error: {str(e)}")
        return pd.DataFrame()
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass  # Ignore close errors

# ----------------------------
# BASIC LOADERS
# ----------------------------
@st.cache_data
def get_tickers(index_name: str) -> pd.DataFrame:
    if index_name == 'NSE 500':
        q = """SELECT DISTINCT ticker 
            FROM dbo.nse_500_hist_data 
            WHERE ticker IS NOT NULL
            ORDER BY ticker"""
    elif index_name == 'Forex':
        q = """SELECT DISTINCT symbol as ticker 
            FROM dbo.forex_hist_data 
            WHERE symbol IS NOT NULL
            ORDER BY symbol"""
    else:
        q = """SELECT DISTINCT ticker 
            FROM dbo.nasdaq_100_hist_data 
            WHERE ticker IS NOT NULL
            ORDER BY ticker"""
    return execute_query_safe(q)
@st.cache_data
def load_price_data(index_name: str, ticker: str) -> pd.DataFrame:
    if index_name == 'NSE 500':
        table = 'nse_500_hist_data'
        ticker_col = 'ticker'
    elif index_name == 'Forex':
        table = 'forex_hist_data'
        ticker_col = 'symbol'
    else:
        table = 'nasdaq_100_hist_data'
        ticker_col = 'ticker'
        
    q = f"""
        SELECT trading_date,
               CAST(open_price AS FLOAT) AS open_price,
               CAST(high_price AS FLOAT) AS high_price,
               CAST(low_price AS FLOAT) AS low_price,
               CAST(close_price AS FLOAT) AS close_price,
               CAST(volume AS FLOAT) AS volume
        FROM dbo.{table}
        WHERE {ticker_col} = ?
        ORDER BY trading_date
    """
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_rsi(index_name: str, ticker: str) -> pd.DataFrame:
    if index_name == 'NSE 500':
        view = 'nse_500_RSI_calculation'
        ticker_col = 'ticker'
    elif index_name == 'Forex':
        view = 'forex_RSI_calculation'
        ticker_col = 'symbol'
    else:
        view = 'nasdaq_100_RSI_calculation'
        ticker_col = 'ticker'
        
    q = f"""SELECT trading_date, RSI
            FROM dbo.{view}
            WHERE {ticker_col} = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_bbands(index_name: str, ticker: str) -> pd.DataFrame:
    if index_name == 'NSE 500':
        view = 'nse_500_bollingerband'
        ticker_col = 'ticker'
    elif index_name == 'Forex':
        view = 'forex_bollingerband'
        ticker_col = 'symbol'
    else:
        view = 'nasdaq_100_bollingerband'
        ticker_col = 'ticker'
        
    q = f"""SELECT trading_date, close_price, Upper_Band, Lower_Band
            FROM dbo.{view}
            WHERE {ticker_col} = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_macd(index_name: str, ticker: str) -> pd.DataFrame:
    if index_name == 'NSE 500':
        view = 'nse_500_macd'
        ticker_col = 'ticker'
    elif index_name == 'Forex':
        view = 'forex_macd'
        ticker_col = 'symbol'
    else:
        view = 'nasdaq_100_macd'
        ticker_col = 'ticker'
        
    q = f"""SELECT trading_date, MACD, Signal_Line
            FROM dbo.{view}
            WHERE {ticker_col} = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_ema_sma(index_name: str, ticker: str) -> pd.DataFrame:
    if index_name == 'NSE 500':
        view = 'nse_500_ema_sma_view'
        ticker_col = 'ticker'
    elif index_name == 'Forex':
        view = 'forex_ema_sma_view'
        ticker_col = 'symbol'
    else:
        view = 'nasdaq_100_ema_sma_view'
        ticker_col = 'ticker'
        
    q = f"""SELECT trading_date, close_price,
                   SMA_50, SMA_100, SMA_200,
                   EMA_50, EMA_100, EMA_200
            FROM dbo.{view}
            WHERE {ticker_col} = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_atr(index_name: str, ticker: str) -> pd.DataFrame:
    if index_name == 'NSE 500':
        view = 'nse_500_atr'
        ticker_col = 'ticker'
    elif index_name == 'Forex':
        view = 'forex_atr'
        ticker_col = 'symbol'
    else:
        view = 'nasdaq_100_atr'
        ticker_col = 'ticker'
        
    q = f"""SELECT trading_date, ATR_14
            FROM dbo.{view}
            WHERE {ticker_col} = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_fibonacci(index_name: str, ticker: str) -> pd.DataFrame:
    """Load Fibonacci retracement and extension levels"""
    if index_name == 'NSE 500':
        view = 'nse_500_fibonacci'
    elif index_name == 'Forex':
        view = 'forex_fibonacci'
    else:
        view = 'nasdaq_100_fibonacci'
        
    q = f"""SELECT trading_date, close_price,
                   fib_20d_0236, fib_20d_0382, fib_20d_0500, fib_20d_0618, fib_20d_0786,
                   fib_50d_0236, fib_50d_0382, fib_50d_0500, fib_50d_0618, fib_50d_0786,
                   fib_20d_ext_1272, fib_20d_ext_1618, fib_20d_ext_2000,
                   fib_trade_signal, fib_position
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_stochastic(index_name: str, ticker: str) -> pd.DataFrame:
    """Load Stochastic oscillator indicators"""
    if index_name == 'NSE 500':
        view = 'nse_500_stochastic'
    elif index_name == 'Forex':
        view = 'forex_stochastic'
    else:
        view = 'nasdaq_100_stochastic'
        
    q = f"""SELECT trading_date, close_price,
                   stoch_5d_k, stoch_5d_d,
                   stoch_14d_k, stoch_14d_d,
                   stoch_21d_k, stoch_21d_d,
                   stoch_crossover, stoch_status, stoch_trade_signal
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_support_resistance(index_name: str, ticker: str) -> pd.DataFrame:
    """Load Support & Resistance levels"""
    if index_name == 'NSE 500':
        view = 'nse_500_support_resistance'
    elif index_name == 'Forex':
        view = 'forex_support_resistance'
    else:
        view = 'nasdaq_100_support_resistance'
        
    q = f"""SELECT trading_date, close_price,
                   pivot_point, r1, r2, r3,
                   s1, s2, s3,
                   swing_high_20d, swing_low_20d,
                   sr_trade_signal, pivot_status
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_candlestick_patterns(index_name: str, ticker: str) -> pd.DataFrame:
    """Load Candlestick pattern detection"""
    if index_name == 'NSE 500':
        view = 'nse_500_patterns'
    elif index_name == 'Forex':
        view = 'forex_patterns'
    else:
        view = 'nasdaq_100_patterns'
        
    q = f"""SELECT trading_date, close_price,
                   doji, hammer, shooting_star,
                   bullish_engulfing, bearish_engulfing,
                   morning_star, evening_star,
                   cup_and_handle, inverse_cup_handle,
                   double_top, double_bottom,
                   head_and_shoulders, inverse_head_shoulders,
                   patterns_detected, pattern_signal
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df

# ----------------------------
# TREND ANALYSIS FUNCTIONS
# ----------------------------
@st.cache_data
def get_latest_macd_date() -> pd.Timestamp:
    """Get the latest date with MACD data available"""
    try:
        conn = get_connection()
        
        # Check both NSE and NASDAQ MACD data
        nse_latest = pd.read_sql("""
            SELECT MAX(trading_date) as latest_date
            FROM dbo.nse_500_macd
        """, conn)
        
        nasdaq_latest = pd.read_sql("""
            SELECT MAX(trading_date) as latest_date
            FROM dbo.nasdaq_100_macd
        """, conn)
        
        conn.close()
        
        # Return the later of the two dates
        nse_date = nse_latest.iloc[0]['latest_date'] if not nse_latest.empty else None
        nasdaq_date = nasdaq_latest.iloc[0]['latest_date'] if not nasdaq_latest.empty else None
        
        if nse_date and nasdaq_date:
            return max(nse_date, nasdaq_date)
        elif nse_date:
            return nse_date
        elif nasdaq_date:
            return nasdaq_date
        else:
            return None
            
    except Exception as e:
        st.error(f"Error checking MACD data availability: {e}")
        return None

@st.cache_data
def get_trend_analysis_data_range(markets: list, date_range: list) -> pd.DataFrame:
    """Get trend analysis data for multiple markets and dates"""
    all_results = []
    
    for market in markets:
        for analysis_date in date_range:
            try:
                market_data = get_trend_analysis_data(market, analysis_date)
                if not market_data.empty:
                    market_data['market'] = market
                    market_data['analysis_date'] = analysis_date
                    all_results.append(market_data)
            except Exception as e:
                # Skip dates with no data
                continue
    
    if all_results:
        combined_df = pd.concat(all_results, ignore_index=True)
        return combined_df
    else:
        return pd.DataFrame()

@st.cache_data
def get_trend_analysis_data(market: str, analysis_date: str) -> pd.DataFrame:
    """Get comprehensive trend analysis data with historical tracking for a specific date and market"""
    if market == 'NSE 500':
        price_table = 'nse_500_hist_data'
        rsi_table = 'nse_500_RSI_calculation'
        macd_table = 'nse_500_macd'
        sma_table = 'nse_500_ema_sma_view'
        ticker_col = 'ticker'
    else:  # NASDAQ 100
        price_table = 'nasdaq_100_hist_data'
        rsi_table = 'nasdaq_100_RSI_calculation'
        macd_table = 'nasdaq_100_macd'
        sma_table = 'nasdaq_100_ema_sma_view'
        ticker_col = 'ticker'
    
    # Get previous trading day and week back dates
    query = f"""
    WITH date_context AS (
        SELECT DISTINCT trading_date
        FROM dbo.{price_table}
        WHERE trading_date <= ?
        ORDER BY trading_date DESC
        OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY
    ),
    prev_day AS (
        SELECT trading_date as prev_day_date
        FROM date_context
        ORDER BY trading_date DESC
        OFFSET 1 ROWS FETCH NEXT 1 ROWS ONLY
    ),
    prev_week AS (
        SELECT trading_date as prev_week_date
        FROM date_context
        ORDER BY trading_date DESC
        OFFSET 5 ROWS FETCH NEXT 1 ROWS ONLY
    ),
    current_data AS (
        SELECT 
            p.{ticker_col},
            p.trading_date as trading_date_current,
            CAST(p.close_price AS FLOAT) as close_price,
            CAST(r.RSI AS FLOAT) as RSI,
            CAST(m.MACD AS FLOAT) as MACD,
            CAST(m.Signal_Line AS FLOAT) as Signal_Line,
            CAST(s.SMA_50 AS FLOAT) as SMA_50,
            CASE WHEN CAST(r.RSI AS FLOAT) <= 30 
                      AND CAST(m.MACD AS FLOAT) > CAST(m.Signal_Line AS FLOAT) 
                 THEN 1 ELSE 0 END as double_strategy,
            CASE WHEN CAST(r.RSI AS FLOAT) <= 30 
                      AND CAST(m.MACD AS FLOAT) > CAST(m.Signal_Line AS FLOAT)
                      AND CAST(p.close_price AS FLOAT) > CAST(s.SMA_50 AS FLOAT)
                 THEN 1 ELSE 0 END as triple_strategy
        FROM dbo.{price_table} p
        LEFT JOIN dbo.{rsi_table} r ON p.{ticker_col} = r.{ticker_col} AND p.trading_date = r.trading_date
        LEFT JOIN dbo.{macd_table} m ON p.{ticker_col} = m.{ticker_col} AND p.trading_date = m.trading_date  
        LEFT JOIN dbo.{sma_table} s ON p.{ticker_col} = s.{ticker_col} AND p.trading_date = s.trading_date
        WHERE p.trading_date = ?
            AND r.RSI IS NOT NULL 
            AND m.MACD IS NOT NULL 
            AND m.Signal_Line IS NOT NULL
            AND s.SMA_50 IS NOT NULL
    ),
    prev_day_data AS (
        SELECT 
            p.{ticker_col},
            CASE WHEN CAST(r.RSI AS FLOAT) <= 30 
                      AND CAST(m.MACD AS FLOAT) > CAST(m.Signal_Line AS FLOAT) 
                 THEN 1 ELSE 0 END as prev_day_double,
            CASE WHEN CAST(r.RSI AS FLOAT) <= 30 
                      AND CAST(m.MACD AS FLOAT) > CAST(m.Signal_Line AS FLOAT)
                      AND CAST(p.close_price AS FLOAT) > CAST(s.SMA_50 AS FLOAT)
                 THEN 1 ELSE 0 END as prev_day_triple
        FROM dbo.{price_table} p
        LEFT JOIN dbo.{rsi_table} r ON p.{ticker_col} = r.{ticker_col} AND p.trading_date = r.trading_date
        LEFT JOIN dbo.{macd_table} m ON p.{ticker_col} = m.{ticker_col} AND p.trading_date = m.trading_date  
        LEFT JOIN dbo.{sma_table} s ON p.{ticker_col} = s.{ticker_col} AND p.trading_date = s.trading_date
        CROSS JOIN prev_day
        WHERE p.trading_date = prev_day.prev_day_date
    ),
    prev_week_data AS (
        SELECT 
            p.{ticker_col},
            CASE WHEN CAST(r.RSI AS FLOAT) <= 30 
                      AND CAST(m.MACD AS FLOAT) > CAST(m.Signal_Line AS FLOAT) 
                 THEN 1 ELSE 0 END as prev_week_double,
            CASE WHEN CAST(r.RSI AS FLOAT) <= 30 
                      AND CAST(m.MACD AS FLOAT) > CAST(m.Signal_Line AS FLOAT)
                      AND CAST(p.close_price AS FLOAT) > CAST(s.SMA_50 AS FLOAT)
                 THEN 1 ELSE 0 END as prev_week_triple
        FROM dbo.{price_table} p
        LEFT JOIN dbo.{rsi_table} r ON p.{ticker_col} = r.{ticker_col} AND p.trading_date = r.trading_date
        LEFT JOIN dbo.{macd_table} m ON p.{ticker_col} = m.{ticker_col} AND p.trading_date = m.trading_date  
        LEFT JOIN dbo.{sma_table} s ON p.{ticker_col} = s.{ticker_col} AND p.trading_date = s.trading_date
        CROSS JOIN prev_week
        WHERE p.trading_date = prev_week.prev_week_date
    )
    SELECT 
        c.*,
        ISNULL(pd.prev_day_double, 0) as prev_day_double,
        ISNULL(pd.prev_day_triple, 0) as prev_day_triple,
        ISNULL(pw.prev_week_double, 0) as prev_week_double,
        ISNULL(pw.prev_week_triple, 0) as prev_week_triple
    FROM current_data c
    LEFT JOIN prev_day_data pd ON c.{ticker_col} = pd.{ticker_col}
    LEFT JOIN prev_week_data pw ON c.{ticker_col} = pw.{ticker_col}
    WHERE c.double_strategy = 1 OR c.triple_strategy = 1
    ORDER BY c.triple_strategy DESC, c.double_strategy DESC, c.{ticker_col}
    """
    
    return execute_query_safe(query, params=[analysis_date, analysis_date])

@st.cache_data
def get_historical_comparison(ticker: str, market: str, current_date: str, previous_date: str, week_back_date: str) -> dict:
    """Get historical comparison data for a specific ticker across different dates"""
    if market == 'NSE 500':
        price_table = 'nse_500_hist_data'
        rsi_table = 'nse_500_RSI_calculation'
        macd_table = 'nse_500_macd'
        sma_table = 'nse_500_ema_sma_view'
        ticker_col = 'ticker'
    else:  # NASDAQ 100
        price_table = 'nasdaq_100_hist_data'
        rsi_table = 'nasdaq_100_RSI_calculation'
        macd_table = 'nasdaq_100_macd'
        sma_table = 'nasdaq_100_ema_sma_view'
        ticker_col = 'ticker'
    
    # Query for all three dates
    query = f"""
    SELECT 
        p.trading_date,
        CAST(p.close_price AS FLOAT) as close_price,
        CAST(r.RSI AS FLOAT) as RSI,
        CAST(m.MACD AS FLOAT) as MACD,
        CAST(m.Signal_Line AS FLOAT) as Signal_Line,
        CAST(s.SMA_50 AS FLOAT) as SMA_50,
        CASE WHEN CAST(r.RSI AS FLOAT) <= 30 
                  AND CAST(m.MACD AS FLOAT) > CAST(m.Signal_Line AS FLOAT) 
             THEN 1 ELSE 0 END as double_strategy,
        CASE WHEN CAST(r.RSI AS FLOAT) <= 30 
                  AND CAST(m.MACD AS FLOAT) > CAST(m.Signal_Line AS FLOAT)
                  AND CAST(p.close_price AS FLOAT) > CAST(s.SMA_50 AS FLOAT)
             THEN 1 ELSE 0 END as triple_strategy
    FROM dbo.{price_table} p
    LEFT JOIN dbo.{rsi_table} r ON p.{ticker_col} = r.{ticker_col} AND p.trading_date = r.trading_date
    LEFT JOIN dbo.{macd_table} m ON p.{ticker_col} = m.{ticker_col} AND p.trading_date = m.trading_date  
    LEFT JOIN dbo.{sma_table} s ON p.{ticker_col} = s.{ticker_col} AND p.trading_date = s.trading_date
    WHERE p.{ticker_col} = ? AND p.trading_date IN (?, ?, ?)
    ORDER BY p.trading_date DESC
    """
    
    df = execute_query_safe(query, params=[ticker, current_date, previous_date, week_back_date])
    
    # Organize data by date
    result = {
        'current': None,
        'previous': None,
        'week_back': None
    }
    
    for _, row in df.iterrows():
        date_str = row['trading_date'].strftime('%Y-%m-%d') if pd.notna(row['trading_date']) else None
        if date_str == current_date:
            result['current'] = row.to_dict()
        elif date_str == previous_date:
            result['previous'] = row.to_dict()
        elif date_str == week_back_date:
            result['week_back'] = row.to_dict()
    
    return result

def get_available_trading_dates(market: str, target_date: str, days_back: int = 10) -> list:
    """Get list of available trading dates around target date"""
    if market == 'NSE 500':
        table = 'nse_500_hist_data'
    else:
        table = 'nasdaq_100_hist_data'
    
    query = f"""
    SELECT DISTINCT trading_date
    FROM dbo.{table}
    WHERE trading_date <= ? AND trading_date >= DATEADD(day, -{days_back}, ?)
    ORDER BY trading_date DESC
    """
    
    df = execute_query_safe(query, params=[target_date, target_date])
    return [date.strftime('%Y-%m-%d') for date in df['trading_date']] if not df.empty else []

# ----------------------------
# RECOMMENDATION TRACKING FUNCTIONS
# ----------------------------
@st.cache_data
def load_recommendations() -> pd.DataFrame:
    """Load all recommendation tracking data from master tables"""
    # Load NSE recommendations
    nse_query = """
        SELECT ticker, company_name, monitor_startdate, monitor_enddate, 
               comments, process_flag, 'NSE 500' as market
        FROM dbo.NSE_500 
        WHERE monitor_startdate IS NOT NULL
    """
    nse_df = execute_query_safe(nse_query)
    
    # Load NASDAQ recommendations
    nasdaq_query = """
        SELECT ticker, company_name, monitor_startdate, monitor_enddate, 
               comments, process_flag, 'NASDAQ 100' as market
        FROM dbo.NASDAQ_top100 
        WHERE monitor_startdate IS NOT NULL
    """
    nasdaq_df = execute_query_safe(nasdaq_query)
    
    # Combine both datasets
    if not nse_df.empty and not nasdaq_df.empty:
        combined_df = pd.concat([nse_df, nasdaq_df], ignore_index=True)
    elif not nse_df.empty:
        combined_df = nse_df.copy()
    elif not nasdaq_df.empty:
        combined_df = nasdaq_df.copy()
    else:
        combined_df = pd.DataFrame()
    
    if not combined_df.empty:
        # Convert date columns
        combined_df['monitor_startdate'] = pd.to_datetime(combined_df['monitor_startdate'])
        combined_df['monitor_enddate'] = pd.to_datetime(combined_df['monitor_enddate'])
        
        # Sort by monitor start date
        combined_df = combined_df.sort_values('monitor_startdate', ascending=False)
    
    return combined_df

def get_price_for_date(ticker: str, target_date: pd.Timestamp, market: str) -> tuple:
    """Get price for a specific date, or next available date if not found"""
    if market == 'NSE 500':
        table = 'nse_500_hist_data'
        ticker_col = 'ticker'
    else:  # NASDAQ 100
        table = 'nasdaq_100_hist_data'
        ticker_col = 'ticker'
    
    # First try to get exact date
    exact_query = f"""
        SELECT TOP 1 trading_date, CAST(close_price AS FLOAT) as close_price
        FROM dbo.{table}
        WHERE {ticker_col} = ? AND trading_date = ?
    """
    
    exact_df = execute_query_safe(exact_query, params=[ticker, target_date.strftime('%Y-%m-%d')])
    
    if not exact_df.empty:
        return exact_df.iloc[0]['trading_date'], float(exact_df.iloc[0]['close_price'])
    
    # If exact date not found, get next available date
    next_query = f"""
        SELECT TOP 1 trading_date, CAST(close_price AS FLOAT) as close_price
        FROM dbo.{table}
        WHERE {ticker_col} = ? AND trading_date >= ?
        ORDER BY trading_date ASC
    """
    
    next_df = execute_query_safe(next_query, params=[ticker, target_date.strftime('%Y-%m-%d')])
    
    if not next_df.empty:
        return next_df.iloc[0]['trading_date'], float(next_df.iloc[0]['close_price'])
    
    return None, None

def get_current_price(ticker: str, market: str) -> tuple:
    """Get the most recent available price for a ticker"""
    if market == 'NSE 500':
        table = 'nse_500_hist_data'
        ticker_col = 'ticker'
    else:  # NASDAQ 100
        table = 'nasdaq_100_hist_data'
        ticker_col = 'ticker'
    
    query = f"""
        SELECT TOP 1 trading_date, CAST(close_price AS FLOAT) as close_price
        FROM dbo.{table}
        WHERE {ticker_col} = ?
        ORDER BY trading_date DESC
    """
    
    df = execute_query_safe(query, params=[ticker])
    
    if not df.empty:
        return df.iloc[0]['trading_date'], float(df.iloc[0]['close_price'])
    
    return None, None

# ----------------------------
# VOLUME-BASED INDICATOR CALCULATIONS
# ----------------------------

def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Volume Weighted Average Price (VWAP)"""
    if df.empty or 'volume' not in df.columns:
        return df
    
    df = df.copy()
    
    # Calculate typical price (HLC/3)
    df['typical_price'] = (df['high_price'] + df['low_price'] + df['close_price']) / 3
    
    # Calculate volume * typical price
    df['volume_price'] = df['typical_price'] * df['volume']
    
    # Calculate cumulative values
    df['cum_volume_price'] = df['volume_price'].cumsum()
    df['cum_volume'] = df['volume'].cumsum()
    
    # Calculate VWAP - handle zero volume case
    df['vwap'] = df['cum_volume_price'] / df['cum_volume'].replace(0, np.nan)
    
    # If all volume is zero, use typical price as VWAP fallback
    if df['cum_volume'].sum() == 0:
        df['vwap'] = df['typical_price']
    
    # Calculate VWAP bands (standard deviations)
    df['vwap_upper_1'] = df['vwap'] * 1.01  # 1% band
    df['vwap_lower_1'] = df['vwap'] * 0.99
    df['vwap_upper_2'] = df['vwap'] * 1.02  # 2% band
    df['vwap_lower_2'] = df['vwap'] * 0.98
    
    return df

def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate On-Balance Volume (OBV)"""
    if df.empty or 'volume' not in df.columns:
        return df
    
    df = df.copy()
    df = df.sort_values('trading_date').reset_index(drop=True)
    
    # Calculate price change
    df['price_change'] = df['close_price'].diff()
    
    # Calculate OBV using vectorized operations for better performance
    df['obv_raw'] = 0.0
    
    for i in range(1, len(df)):
        if df.loc[i, 'price_change'] > 0:
            df.loc[i, 'obv_raw'] = df.loc[i-1, 'obv_raw'] + df.loc[i, 'volume']
        elif df.loc[i, 'price_change'] < 0:
            df.loc[i, 'obv_raw'] = df.loc[i-1, 'obv_raw'] - df.loc[i, 'volume']
        else:
            df.loc[i, 'obv_raw'] = df.loc[i-1, 'obv_raw']
    
    # Calculate OBV moving averages
    df['obv_ma_10'] = df['obv_raw'].rolling(window=10).mean()
    df['obv_ma_20'] = df['obv_raw'].rolling(window=20).mean()
    
    return df

def calculate_mfi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate Money Flow Index (MFI) - Volume-weighted RSI"""
    if df.empty or 'volume' not in df.columns:
        return df
    
    df = df.copy()
    df = df.sort_values('trading_date').reset_index(drop=True)
    
    # Calculate typical price
    df['typical_price'] = (df['high_price'] + df['low_price'] + df['close_price']) / 3
    
    # Calculate raw money flow
    df['raw_money_flow'] = df['typical_price'] * df['volume']
    
    # Calculate positive and negative money flow using vectorized operations
    df['price_change'] = df['typical_price'].diff()
    
    # Initialize columns
    df['positive_mf'] = 0.0
    df['negative_mf'] = 0.0
    
    # Use numpy where for better performance
    import numpy as np
    df['positive_mf'] = np.where(df['price_change'] > 0, df['raw_money_flow'], 0)
    df['negative_mf'] = np.where(df['price_change'] < 0, df['raw_money_flow'], 0)
    
    # Calculate rolling sums
    df['positive_mf_sum'] = df['positive_mf'].rolling(window=period).sum()
    df['negative_mf_sum'] = df['negative_mf'].rolling(window=period).sum()
    
    # Calculate money ratio with division by zero protection
    df['money_ratio'] = df['positive_mf_sum'] / (df['negative_mf_sum'] + 1e-10)  # Add small epsilon to avoid division by zero
    
    # Calculate MFI
    df['mfi'] = 100 - (100 / (1 + df['money_ratio']))
    
    # Handle any remaining NaN values
    df['mfi'] = df['mfi'].fillna(50)  # Default to neutral 50 if calculation fails
    
    return df

def calculate_ad_line(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Accumulation/Distribution Line"""
    if df.empty or 'volume' not in df.columns:
        return df
    
    df = df.copy()
    
    # Calculate Money Flow Multiplier
    df['clv'] = ((df['close_price'] - df['low_price']) - (df['high_price'] - df['close_price'])) / (df['high_price'] - df['low_price'])
    
    # Handle division by zero (when high == low)
    df['clv'] = df['clv'].fillna(0)
    
    # Calculate Money Flow Volume
    df['mf_volume'] = df['clv'] * df['volume']
    
    # Calculate A/D Line (cumulative)
    df['ad_line'] = df['mf_volume'].cumsum()
    
    # Calculate A/D Line moving average
    df['ad_line_ma'] = df['ad_line'].rolling(window=20).mean()
    
    return df

def calculate_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all volume-based indicators"""
    if df.empty:
        return df
    
    # Calculate volume moving averages
    df['volume_ma_10'] = df['volume'].rolling(window=10).mean()
    df['volume_ma_20'] = df['volume'].rolling(window=20).mean()
    df['volume_ma_50'] = df['volume'].rolling(window=50).mean()
    
    # Calculate volume rate of change
    df['volume_roc'] = df['volume'].pct_change(periods=10) * 100
    
    # Calculate relative volume - handle zero volume case
    df['relative_volume'] = df['volume'] / df['volume_ma_20'].replace(0, np.nan)
    
    # If all volume is zero, set relative volume to 1 (neutral)
    if df['volume_ma_20'].sum() == 0:
        df['relative_volume'] = 1.0
    
    # Calculate all volume indicators
    df = calculate_vwap(df)
    df = calculate_obv(df)
    df = calculate_mfi(df)
    df = calculate_ad_line(df)
    
    return df

# ----------------------------
# SIGNAL VIEW LOADERS
# ----------------------------
@st.cache_data
def load_signal_view(index_name: str, view_type: str, ticker: str) -> pd.DataFrame:
    """view_type in {'BB', 'MACD', 'RSI', 'SMA', 'ATR'}."""
    if index_name == 'NSE 500':
        view_map = {
            'BB': 'nse_500_bb_signals',
            'MACD': 'nse_500_macd_signals',
            'RSI': 'nse_500_rsi_signals',
            'SMA': 'nse_500_sma_signals',
            'ATR': 'nse_500_atr_spikes',
        }
        ticker_col = 'ticker'
    elif index_name == 'Forex':
        view_map = {
            'BB': 'forex_bb_signals',
            'MACD': 'forex_macd_signals',
            'RSI': 'forex_rsi_signals',
            'SMA': 'forex_sma_signals',
            'ATR': 'forex_atr_spikes',
        }
        ticker_col = 'symbol'
    else:
        view_map = {
            'BB': 'nasdaq_100_bb_signals',
            'MACD': 'nasdaq_100_macd_signals',
            'RSI': 'nasdaq_100_rsi_signals',
            'SMA': 'nasdaq_100_sma_signals',
            'ATR': 'nasdaq_100_atr_spikes',
        }
        ticker_col = 'ticker'

    view_name = view_map[view_type]
    q = f"""SELECT *
            FROM dbo.{view_name}
            WHERE {ticker_col} = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df

# ----------------------------
# FILTER BY DATE
# ----------------------------
def filter_by_date(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    if df is None or df.empty or 'trading_date' not in df.columns:
        return df
    mask = (
        df['trading_date'] >= pd.to_datetime(start_date)
    ) & (
        df['trading_date'] <= pd.to_datetime(end_date)
    )
    return df.loc[mask]

# ----------------------------
# TRADING EDUCATION HELPERS
# ----------------------------
def show_trading_guide():
    st.markdown("---")
    st.header("📚 Trading Education & Strategy Guide")
    
    with st.expander("🎯 How to Combine Indicators for Better Trading Decisions"):
        st.markdown("""
        ### 🔄 Multi-Indicator Confirmation Strategy
        
        **Never rely on a single indicator!** Professional traders use multiple confirmations:
        
        #### 📊 **Trend + Momentum + Volume Strategy**
        1. **Trend Direction** (SMA/EMA): Determines the overall market direction
        2. **Momentum** (RSI + MACD): Confirms strength of the move
        3. **Volatility** (Bollinger Bands + ATR): Helps with position sizing and stop-loss
        
        #### 🎯 **Entry Signal Combinations**
        
        **🟢 BULLISH ENTRY:**
        - Price above SMA 50 & SMA 200 (uptrend)
        - RSI between 30-70 (not overbought)
        - MACD line crosses above Signal line
        - Price bounces off Bollinger Band lower band
        - ATR showing normal volatility (not spiking)
        
        **🔴 BEARISH ENTRY:**
        - Price below SMA 50 & SMA 200 (downtrend)
        - RSI between 30-70 (not oversold)
        - MACD line crosses below Signal line
        - Price rejected at Bollinger Band upper band
        - High ATR suggests strong momentum down
        
        #### ⚠️ **Risk Management Rules**
        - **Stop Loss**: Use ATR to set stops (2-3x ATR from entry)
        - **Position Size**: Reduce size when ATR is high (high volatility)
        - **Profit Taking**: Take partial profits at Bollinger Band extremes
        """)
    
    with st.expander("⚡ Quick Trading Cheat Sheet"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 🟢 BUY Signals
            - **Trend**: Price > SMA 200
            - **RSI**: 30-50 (oversold recovery)
            - **MACD**: Bullish crossover
            - **Bollinger**: Price near lower band
            - **ATR**: Stable or decreasing
            """)
        
        with col2:
            st.markdown("""
            ### 🔴 SELL Signals
            - **Trend**: Price < SMA 200
            - **RSI**: 50-70 (overbought)
            - **MACD**: Bearish crossover
            - **Bollinger**: Price near upper band
            - **ATR**: Spiking (exit before volatility)
            """)

def show_indicator_education():
    st.markdown("---")
    st.header("🧠 Technical Indicator Deep Dive")
    
    with st.expander("📈 Understanding Each Indicator"):
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Bollinger Bands", "RSI", "MACD", "Moving Averages", "ATR"])
        
        with tab1:
            st.markdown("""
            ### 📊 Bollinger Bands (BB)
            
            **What it shows:** Price volatility and potential reversal points
            
            **Components:**
            - **Middle Band**: 20-period Simple Moving Average
            - **Upper Band**: Middle Band + (2 × Standard Deviation)
            - **Lower Band**: Middle Band - (2 × Standard Deviation)
            
            **How to Trade:**
            - **Bollinger Squeeze**: When bands contract → Breakout coming
            - **Band Walk**: Price riding upper/lower band → Strong trend
            - **Mean Reversion**: Price touches bands → Potential reversal
            
            **⚠️ Warning Signs:**
            - Don't trade against strong trends even at band extremes
            - Wait for confirmation from other indicators
            """)
        
        with tab2:
            st.markdown("""
            ### 📊 RSI (Relative Strength Index)
            
            **What it shows:** Momentum and overbought/oversold conditions
            
            **Reading RSI:**
            - **Above 70**: Overbought → Potential sell signal
            - **Below 30**: Oversold → Potential buy signal
            - **50 Level**: Momentum direction (above = bullish, below = bearish)
            
            **Advanced RSI Strategies:**
            - **Divergence**: Price makes new high/low but RSI doesn't → Reversal signal
            - **RSI Breakouts**: RSI breaking 50 → Momentum confirmation
            - **Hidden Divergence**: Trend continuation signal
            
            **Best Practices:**
            - In strong trends, RSI can stay "overbought" or "oversold" for long periods
            - Use 30/70 levels as alerts, not absolute signals
            """)
        
        with tab3:
            st.markdown("""
            ### 📊 MACD (Moving Average Convergence Divergence)
            
            **What it shows:** Trend changes and momentum shifts
            
            **Components:**
            - **MACD Line**: 12 EMA - 26 EMA
            - **Signal Line**: 9 EMA of MACD Line
            - **Histogram**: MACD - Signal Line
            
            **Key Signals:**
            - **Golden Cross**: MACD crosses above Signal → Bullish
            - **Death Cross**: MACD crosses below Signal → Bearish
            - **Zero Line**: Above = uptrend, Below = downtrend
            
            **Pro Tips:**
            - MACD works best in trending markets
            - Histogram shows momentum acceleration/deceleration
            - Look for divergences with price
            """)
        
        with tab4:
            st.markdown("""
            ### 📊 Moving Averages (SMA/EMA)
            
            **What they show:** Trend direction and support/resistance levels
            
            **Types:**
            - **SMA (Simple)**: Average of X periods
            - **EMA (Exponential)**: More weight to recent prices
            
            **Key Levels:**
            - **SMA/EMA 50**: Short-term trend
            - **SMA/EMA 100**: Medium-term trend  
            - **SMA/EMA 200**: Long-term trend (most important)
            
            **Trading Strategies:**
            - **Golden Cross**: 50 MA above 200 MA → Bull market
            - **Death Cross**: 50 MA below 200 MA → Bear market
            - **Dynamic Support/Resistance**: Price bounces off MAs
            
            **Rule of Thumb:**
            - Trade in direction of 200 MA for higher success rate
            """)
        
        with tab5:
            st.markdown("""
            ### 📊 ATR (Average True Range)
            
            **What it shows:** Market volatility and price movement range
            
            **How to Use:**
            - **Position Sizing**: Reduce position when ATR is high
            - **Stop Losses**: Set stops at 2-3x ATR from entry
            - **Volatility Filter**: Avoid trading when ATR spikes unexpectedly
            
            **ATR Applications:**
            - **Risk Management**: Higher ATR = wider stops needed
            - **Profit Targets**: Use ATR multiples for realistic targets
            - **Market Regime**: High ATR = volatile market, Low ATR = calm market
            
            **Key Insight:**
            ATR doesn't predict direction, only how much price might move!
            """)

# ----------------------------
# ENHANCED PLOTTING HELPERS WITH BETTER INTERACTIVITY
# ----------------------------

def create_downloadable_report(selected_ticker, index_option, price_df, rsi_df, bb_df, macd_df, ema_sma_df, atr_df):
    """Create a downloadable data report in CSV format"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Combine all data into a comprehensive report
    report_data = []
    
    # Price data summary
    if not price_df.empty:
        latest_price = price_df['close_price'].iloc[-1] if len(price_df) > 0 else 0
        price_change = (latest_price - price_df['close_price'].iloc[0]) if len(price_df) > 1 else 0
        price_change_pct = (price_change / price_df['close_price'].iloc[0] * 100) if len(price_df) > 1 and price_df['close_price'].iloc[0] != 0 else 0
        
        report_data.append({
            'Metric': 'Current Price',
            'Value': f"${latest_price:.2f}",
            'Description': 'Latest closing price'
        })
        report_data.append({
            'Metric': 'Price Change',
            'Value': f"{price_change_pct:.1f}%",
            'Description': 'Price change over selected period'
        })
        report_data.append({
            'Metric': 'Data Points',
            'Value': len(price_df),
            'Description': 'Number of trading days analyzed'
        })
    
    # RSI summary
    if not rsi_df.empty and 'RSI' in rsi_df.columns:
        current_rsi = rsi_df['RSI'].iloc[-1] if len(rsi_df) > 0 else 0
        rsi_status = "Overbought (>70)" if current_rsi > 70 else "Oversold (<30)" if current_rsi < 30 else "Neutral (30-70)"
        report_data.append({
            'Metric': 'Current RSI',
            'Value': f"{current_rsi:.1f}",
            'Description': f'RSI Status: {rsi_status}'
        })
    
    # MACD summary
    if not macd_df.empty and 'MACD' in macd_df.columns:
        current_macd = macd_df['MACD'].iloc[-1] if len(macd_df) > 0 else 0
        current_signal = macd_df['Signal_Line'].iloc[-1] if 'Signal_Line' in macd_df.columns and len(macd_df) > 0 else 0
        macd_status = "Bullish" if current_macd > current_signal else "Bearish"
        report_data.append({
            'Metric': 'MACD Signal',
            'Value': f"{current_macd:.3f}",
            'Description': f'MACD vs Signal: {macd_status}'
        })
    
    # Create DataFrame for the report
    report_df = pd.DataFrame(report_data)
    
    # Convert to CSV
    csv_buffer = io.StringIO()
    report_df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()
    
    return csv_data, timestamp

def create_enhanced_plotly_config():
    """Create enhanced plotly configuration for better interactivity"""
    return {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToAdd': [
            'drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect', 'eraseshape'
        ],
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'chart',
            'height': 500,
            'width': 1200,
            'scale': 1
        },
        'scrollZoom': True,
        'doubleClick': 'reset+autosize'
    }

def enhance_chart_layout(fig, title, height=600):
    """Enhance chart layout for better interactivity"""
    fig.update_layout(
        title={
            'text': title,
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16, 'color': '#2E4057'}
        },
        height=height,
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.8)"
        ),
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)',
            showspikes=True,
            spikesnap='cursor',
            spikemode='across',
            spikethickness=1,
            rangeslider=dict(visible=True, thickness=0.05),
            type='date'
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)',
            showspikes=True,
            spikesnap='cursor',
            spikemode='across',
            spikethickness=1
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=10, r=10, t=40, b=40)
    )
    
    # Add crossfilter cursor
    fig.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>" +
                     "Date: %{x}<br>" +
                     "Value: %{y:.2f}<br>" +
                     "<extra></extra>"
    )
    
    return fig

def plot_indicator_section(price_df, rsi_df, macd_df, bb_df, ema_sma_df, atr_df, ticker, index_name,
                          fibonacci_df=None, stochastic_df=None, support_resistance_df=None, candlestick_patterns_df=None):
    st.subheader(f"📈 Interactive Price & Indicator Charts for {ticker} ({index_name})")
    
    # Add chart controls
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        chart_height = st.selectbox("Chart Height", [500, 600, 700, 800], index=1, key="chart_height")
    with col2:
        show_volume = st.checkbox("Show Volume (if available)", value=False, key="show_volume")
    with col3:
        time_range = st.selectbox("Default Time Range", 
                                 ["1M", "3M", "6M", "1Y", "2Y", "All"], 
                                 index=3, key="time_range")

    # 1. Enhanced Bollinger Bands
    if bb_df is not None and not bb_df.empty:
        st.markdown("### 🎯 Interactive Bollinger Bands Analysis")
        
        with st.expander("📚 What Bollinger Bands Tell You", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                **Current Analysis:**
                - **Upper Band**: Potential overbought zone
                - **Lower Band**: Potential oversold zone  
                - **Middle Line (SMA 20)**: Dynamic support/resistance
                - **Band Width**: Narrow = breakout coming, Wide = high volatility
                """)
            with col2:
                st.markdown("""
                **Trading Signals:**
                - Price at upper band + RSI > 70 = Strong sell signal
                - Price at lower band + RSI < 30 = Strong buy signal
                - Band squeeze often precedes major moves
                - Bollinger Band walk indicates strong trends
                """)
        
        # Create enhanced Bollinger Bands chart
        fig_bb = go.Figure()
        
        # Add price line
        fig_bb.add_trace(go.Scatter(
            x=bb_df['trading_date'], 
            y=bb_df['close_price'],
            mode='lines',
            name='Close Price',
            line=dict(color='#1f77b4', width=2),
            hovertemplate="<b>Close Price</b><br>Date: %{x}<br>Price: $%{y:.2f}<extra></extra>"
        ))
        
        # Add Bollinger Bands with fill
        fig_bb.add_trace(go.Scatter(
            x=bb_df['trading_date'],
            y=bb_df['Upper_Band'],
            mode='lines',
            name='Upper Band',
            line=dict(color='red', width=1, dash='dot'),
            hovertemplate="<b>Upper Band</b><br>Date: %{x}<br>Value: $%{y:.2f}<extra></extra>"
        ))
        
        fig_bb.add_trace(go.Scatter(
            x=bb_df['trading_date'],
            y=bb_df['Lower_Band'],
            mode='lines',
            name='Lower Band',
            line=dict(color='green', width=1, dash='dot'),
            fill='tonexty',
            fillcolor='rgba(128,128,128,0.1)',
            hovertemplate="<b>Lower Band</b><br>Date: %{x}<br>Value: $%{y:.2f}<extra></extra>"        ))
        
        fig_bb = enhance_chart_layout(fig_bb, "Interactive Bollinger Bands - Click and Drag to Zoom", chart_height)
        st.plotly_chart(fig_bb, width="stretch", config=create_enhanced_plotly_config())

    # 2. Enhanced RSI with additional features
    if rsi_df is not None and not rsi_df.empty:
        st.markdown("### ⚡ Interactive RSI Momentum Analysis")
        
        # Calculate current RSI level and statistics
        current_rsi = rsi_df['RSI'].iloc[-1] if not rsi_df.empty else None
        rsi_mean = rsi_df['RSI'].mean() if not rsi_df.empty else None
        
        if current_rsi and rsi_mean:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if current_rsi > 70:
                    st.metric("Current RSI", f"{current_rsi:.1f}", "🔴 OVERBOUGHT", delta_color="inverse")
                elif current_rsi < 30:
                    st.metric("Current RSI", f"{current_rsi:.1f}", "🟢 OVERSOLD", delta_color="normal")
                else:
                    st.metric("Current RSI", f"{current_rsi:.1f}", "🟡 NEUTRAL", delta_color="off")
            
            with col2:
                st.metric("Average RSI", f"{rsi_mean:.1f}")
            with col3:
                rsi_volatility = rsi_df['RSI'].std()
                st.metric("RSI Volatility", f"{rsi_volatility:.1f}")
            with col4:
                overbought_pct = (rsi_df['RSI'] > 70).sum() / len(rsi_df) * 100
                st.metric("Overbought %", f"{overbought_pct:.1f}%")
        
        with st.expander("📚 Advanced RSI Trading Guide", expanded=False):
            tab1, tab2 = st.tabs(["Basic Signals", "Advanced Strategies"])
            with tab1:
                st.markdown("""
                **RSI Trading Zones:**
                - **🔴 Above 70**: Overbought - Look for sell signals, avoid new longs
                - **🟡 30-70**: Normal range - Trade with trend direction
                - **🟢 Below 30**: Oversold - Look for buy signals, avoid new shorts
                - **⚖️ Around 50**: Momentum line - Above = bullish, Below = bearish
                """)
            with tab2:
                st.markdown("""
                **Professional RSI Techniques:**
                - **Divergence Trading**: Price makes new high/low but RSI doesn't
                - **RSI Breakouts**: RSI breaking above/below 50 confirms momentum
                - **Failure Swings**: RSI fails to reach previous extreme levels
                - **Multiple Timeframe**: Use higher timeframe RSI for trend filter
                """)
        
        # Create enhanced RSI chart
        fig_rsi = go.Figure()
        
        fig_rsi.add_trace(go.Scatter(
            x=rsi_df['trading_date'],
            y=rsi_df['RSI'],
            mode='lines',
            name='RSI',
            line=dict(color='purple', width=2),
            hovertemplate="<b>RSI</b><br>Date: %{x}<br>RSI: %{y:.2f}<extra></extra>"
        ))
        
        # Add RSI zones with different colors
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", 
                         annotation_text="Overbought (70)", annotation_position="right")
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", 
                         annotation_text="Oversold (30)", annotation_position="right")
        fig_rsi.add_hline(y=50, line_dash="dot", line_color="gray", 
                         annotation_text="Momentum Line (50)", annotation_position="right")
          # Add colored background zones
        fig_rsi.add_hrect(y0=70, y1=100, fillcolor="red", opacity=0.1, line_width=0)
        fig_rsi.add_hrect(y0=0, y1=30, fillcolor="green", opacity=0.1, line_width=0)
        
        fig_rsi = enhance_chart_layout(fig_rsi, "Interactive RSI - Momentum & Overbought/Oversold Zones", chart_height)
        fig_rsi.update_yaxes(range=[0, 100])
        
        st.plotly_chart(fig_rsi, width="stretch", config=create_enhanced_plotly_config())

    # 3. Enhanced MACD with histogram
    if macd_df is not None and not macd_df.empty:
        st.markdown("### 🚀 Interactive MACD Trend Analysis")
        
        # Calculate current MACD status
        current_macd = macd_df['MACD'].iloc[-1] if not macd_df.empty else None
        current_signal = macd_df['Signal_Line'].iloc[-1] if not macd_df.empty else None
        
        if current_macd and current_signal:
            col1, col2, col3 = st.columns(3)
            with col1:
                if current_macd > current_signal:
                    st.metric("MACD Status", "🟢 BULLISH", "Above Signal Line")
                else:
                    st.metric("MACD Status", "🔴 BEARISH", "Below Signal Line")
            
            with col2:
                histogram = current_macd - current_signal
                st.metric("MACD Histogram", f"{histogram:.4f}")
            
            with col3:
                if current_macd > 0:
                    st.metric("Zero Line", "🟢 ABOVE", "Bullish Territory")
                else:
                    st.metric("Zero Line", "🔴 BELOW", "Bearish Territory")
        
        with st.expander("📚 MACD Trading Masterclass", expanded=False):
            st.markdown("""
            **Signal Types & Interpretation:**
            
            **🟢 Bullish Signals:**
            - MACD line crosses above Signal line (Golden crossover)
            - MACD crosses above zero line (Trend confirmation)
            - Positive histogram growing (Accelerating momentum)
            
            **🔴 Bearish Signals:**
            - MACD line crosses below Signal line (Death crossover)  
            - MACD crosses below zero line (Trend reversal)
            - Negative histogram growing (Accelerating decline)
            
            **🎯 Best Practices:**
            - Use in trending markets for best results
            - Combine with price action for confirmation
            - Watch for divergences with price movements
            - Histogram shows momentum acceleration/deceleration
            """)
        
        # Create MACD with histogram subplot
        fig_macd = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                vertical_spacing=0.03, row_heights=[0.7, 0.3],
                                subplot_titles=('MACD Lines', 'MACD Histogram'))
        
        # MACD and Signal lines
        fig_macd.add_trace(go.Scatter(
            x=macd_df['trading_date'], y=macd_df['MACD'],
            mode='lines', name='MACD',
            line=dict(color='blue', width=2),
            hovertemplate="<b>MACD</b><br>Date: %{x}<br>Value: %{y:.4f}<extra></extra>"
        ), row=1, col=1)
        
        fig_macd.add_trace(go.Scatter(
            x=macd_df['trading_date'], y=macd_df['Signal_Line'],
            mode='lines', name='Signal Line',
            line=dict(color='red', width=2),
            hovertemplate="<b>Signal Line</b><br>Date: %{x}<br>Value: %{y:.4f}<extra></extra>"
        ), row=1, col=1)
        
        # MACD Histogram
        macd_histogram = macd_df['MACD'] - macd_df['Signal_Line']
        colors = ['green' if x >= 0 else 'red' for x in macd_histogram]
        
        fig_macd.add_trace(go.Bar(
            x=macd_df['trading_date'], y=macd_histogram,
            name='Histogram', marker_color=colors,
            hovertemplate="<b>Histogram</b><br>Date: %{x}<br>Value: %{y:.4f}<extra></extra>"
        ), row=2, col=1)
          # Add zero lines
        fig_macd.add_hline(y=0, line_dash="dash", line_color="black", row=1, col=1)
        fig_macd.add_hline(y=0, line_dash="dash", line_color="black", row=2, col=1)
        
        fig_macd.update_layout(
            title="Interactive MACD - Trend Direction & Momentum",
            height=chart_height,
            hovermode='x unified',
            showlegend=True
        )
        
        fig_macd.update_xaxes(showgrid=True, rangeslider=dict(visible=True), row=2, col=1)
        
        st.plotly_chart(fig_macd, width="stretch", config=create_enhanced_plotly_config())

    # 4. Enhanced Moving Averages with trend analysis
    if ema_sma_df is not None and not ema_sma_df.empty:
        st.markdown("### 📊 Interactive Moving Average Trend Analysis")
        
        # Analyze current trend
        current_price = ema_sma_df['close_price'].iloc[-1] if not ema_sma_df.empty else None
        sma_200 = ema_sma_df['SMA_200'].iloc[-1] if 'SMA_200' in ema_sma_df.columns and not ema_sma_df.empty else None
        sma_50 = ema_sma_df['SMA_50'].iloc[-1] if 'SMA_50' in ema_sma_df.columns and not ema_sma_df.empty else None
        
        if current_price and sma_200 and sma_50:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if current_price > sma_200:
                    st.metric("Long-term Trend", "🟢 BULLISH", "Above 200 SMA")
                else:
                    st.metric("Long-term Trend", "🔴 BEARISH", "Below 200 SMA")
            
            with col2:
                if sma_50 > sma_200:
                    st.metric("MA Cross", "🟢 GOLDEN", "50 > 200 SMA")
                else:
                    st.metric("MA Cross", "🔴 DEATH", "50 < 200 SMA")
            
            with col3:
                distance_200 = ((current_price - sma_200) / sma_200) * 100
                st.metric("Distance from 200 SMA", f"{distance_200:.1f}%")
            
            with col4:
                if current_price > sma_50:
                    st.metric("Short-term", "🟢 ABOVE 50", "Bullish bias")
                else:
                    st.metric("Short-term", "🔴 BELOW 50", "Bearish bias")
          # MA selection
        ma_options = st.multiselect(
            "Select Moving Averages to Display:",
            ["SMA_50", "SMA_100", "SMA_200", "EMA_50", "EMA_100", "EMA_200"],
            default=["SMA_50", "SMA_200", "EMA_50"],
            key="ma_selection"
        )
        
        # Add close price to selection
        if "close_price" not in ma_options:
            ma_options.insert(0, "close_price")
        
        with st.expander("📚 Moving Average Trading Encyclopedia", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                **Moving Average Hierarchy:**
                - **200 SMA**: Long-term trend (most important)
                - **100 SMA**: Medium-term trend
                - **50 SMA**: Short-term trend
                - **20 EMA**: Very short-term momentum
                
                **Golden Rules:**
                - Trade in direction of 200 SMA for 80% higher success rate
                - Price above all MAs = Strong bull trend
                - Price below all MAs = Strong bear trend
                """)
            with col2:
                st.markdown("""
                **Support & Resistance:**
                - MAs act as dynamic support in uptrends
                - MAs act as dynamic resistance in downtrends
                - Bounce off MAs = Trend continuation
                - Break through MAs = Potential reversal
                
                **Cross Signals:**
                - Golden Cross: 50 MA > 200 MA → Major bull signal
                - Death Cross: 50 MA < 200 MA → Major bear signal
                """)
        
        # Create enhanced MA chart
        fig_ma = go.Figure()
        
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
        
        for i, col in enumerate(ma_options):
            if col in ema_sma_df.columns:
                line_style = dict(width=3 if col == 'close_price' else 2)
                if 'SMA' in col:
                    line_style['dash'] = 'solid'
                elif 'EMA' in col:
                    line_style['dash'] = 'dot'
                
                fig_ma.add_trace(go.Scatter(
                    x=ema_sma_df['trading_date'],
                    y=ema_sma_df[col],
                    mode='lines',
                    name=col.replace('_', ' '),
                    line=dict(color=colors[i % len(colors)], **line_style),                    hovertemplate=f"<b>{col}</b><br>Date: %{{x}}<br>Value: $%{{y:.2f}}<extra></extra>"
                ))
        
        fig_ma = enhance_chart_layout(fig_ma, "Interactive Moving Averages - Trend Direction & Support/Resistance", chart_height)
        st.plotly_chart(fig_ma, width="stretch", config=create_enhanced_plotly_config())

    # 5. Enhanced ATR with volatility analysis
    if atr_df is not None and not atr_df.empty:
        st.markdown("### 💥 Interactive ATR Volatility Analysis")
        
        # Analyze current volatility
        current_atr = atr_df['ATR_14'].iloc[-1] if not atr_df.empty else None
        avg_atr = atr_df['ATR_14'].mean() if not atr_df.empty else None
        atr_std = atr_df['ATR_14'].std() if not atr_df.empty else None
        
        if current_atr and avg_atr and atr_std:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if current_atr > avg_atr * 1.5:
                    st.metric("Volatility", "🔥 HIGH", f"{current_atr:.2f}")
                elif current_atr < avg_atr * 0.7:
                    st.metric("Volatility", "😴 LOW", f"{current_atr:.2f}")
                else:
                    st.metric("Volatility", "📊 NORMAL", f"{current_atr:.2f}")
            
            with col2:
                st.metric("Average ATR", f"{avg_atr:.2f}")
            
            with col3:
                st.metric("ATR Volatility", f"{atr_std:.2f}")
            
            with col4:
                atr_percentile = ((atr_df['ATR_14'] < current_atr).sum() / len(atr_df)) * 100
                st.metric("ATR Percentile", f"{atr_percentile:.0f}th")
        
        with st.expander("📚 ATR Risk Management Academy", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                **Position Sizing Formula:**
                - **High ATR (>{avg_atr*1.5:.2f})**: Reduce position by 50%
                - **Normal ATR ({avg_atr*0.7:.2f}-{avg_atr*1.5:.2f})**: Standard size
                - **Low ATR (<{avg_atr*0.7:.2f})**: Can increase position by 25%
                
                **Stop Loss Guidelines:**
                - Conservative: 2x ATR from entry
                - Moderate: 1.5x ATR from entry  
                - Aggressive: 1x ATR from entry
                """)
            with col2:
                st.markdown(f"""
                **Profit Target Framework:**
                - Target 1: 2x ATR (1:1 Risk/Reward)
                - Target 2: 3x ATR (1:1.5 Risk/Reward)
                - Target 3: 5x ATR (1:2.5 Risk/Reward)
                
                **Market Regime:**
                - High ATR = Trending/Volatile market
                - Low ATR = Range-bound/Calm market
                - ATR spikes = Major news/events
                """)
        
        # Create enhanced ATR chart with volatility bands
        fig_atr = go.Figure()
        
        fig_atr.add_trace(go.Scatter(
            x=atr_df['trading_date'],
            y=atr_df['ATR_14'],
            mode='lines',
            name='ATR 14',
            line=dict(color='orange', width=2),
            fill='tozeroy',
            fillcolor='rgba(255,165,0,0.1)',
            hovertemplate="<b>ATR 14</b><br>Date: %{x}<br>ATR: %{y:.4f}<extra></extra>"
        ))
          # Add volatility reference lines
        if avg_atr:
            fig_atr.add_hline(y=avg_atr, line_dash="dash", line_color="blue", 
                             annotation_text=f"Average ATR: {avg_atr:.2f}", annotation_position="right")
            fig_atr.add_hline(y=avg_atr*1.5, line_dash="dash", line_color="red", 
                             annotation_text=f"High Volatility: {avg_atr*1.5:.2f}", annotation_position="right")
            fig_atr.add_hline(y=avg_atr*0.7, line_dash="dash", line_color="green", 
                             annotation_text=f"Low Volatility: {avg_atr*0.7:.2f}", annotation_position="right")
        
        fig_atr = enhance_chart_layout(fig_atr, "Interactive ATR - Volatility Measurement for Risk Management", chart_height)
        st.plotly_chart(fig_atr, width="stretch", config=create_enhanced_plotly_config())

    # 6. Volume-Based Indicators Section
    if 'volume' in price_df.columns and not price_df['volume'].isna().all():
        st.markdown("### 📊 Interactive Volume-Based Indicators")
        
        # Calculate volume indicators
        volume_df = calculate_volume_indicators(price_df.copy())
        
        # Volume indicator selection
        volume_indicators = st.multiselect(
            "Select Volume Indicators to Display:",
            ["Volume Analysis", "VWAP", "OBV", "MFI", "A/D Line"],
            default=["Volume Analysis", "VWAP", "OBV"],
            key="volume_indicators"
        )
        
        # 6.1 Volume Analysis
        if "Volume Analysis" in volume_indicators:
            st.markdown("#### 📈 Volume Analysis & Relative Volume")
            
            # Volume statistics
            current_volume = volume_df['volume'].iloc[-1] if not volume_df.empty else None
            avg_volume_20 = volume_df['volume_ma_20'].iloc[-1] if not volume_df.empty else None
            
            if current_volume and avg_volume_20:
                relative_vol = current_volume / avg_volume_20
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if relative_vol > 2.0:
                        st.metric("Volume Alert", "🔥 UNUSUAL", f"{relative_vol:.1f}x average")
                    elif relative_vol > 1.5:
                        st.metric("Volume Alert", "📈 HIGH", f"{relative_vol:.1f}x average")
                    else:
                        st.metric("Volume Alert", "📊 NORMAL", f"{relative_vol:.1f}x average")
                
                with col2:
                    st.metric("Current Volume", f"{current_volume:,.0f}")
                
                with col3:
                    st.metric("20-day Avg Volume", f"{avg_volume_20:,.0f}")
                
                with col4:
                    volume_trend = "📈 INCREASING" if volume_df['volume'].tail(5).mean() > volume_df['volume_ma_20'].iloc[-1] else "📉 DECREASING"
                    st.metric("Volume Trend", volume_trend)
            
            with st.expander("📚 Volume Analysis Guide", expanded=False):
                st.markdown("""
                **Volume Interpretation:**
                - **High Volume + Price Rise** = Strong buying interest (bullish)
                - **High Volume + Price Fall** = Strong selling pressure (bearish)
                - **Low Volume + Price Move** = Weak move, likely to reverse
                - **Volume Spikes** = Often mark important price levels
                
                **Relative Volume:**
                - **> 2x Average**: Unusual activity - investigate news/events
                - **1.5-2x Average**: Above normal - confirms price moves
                - **< 0.5x Average**: Low interest - be cautious of breakouts
                """)
            
            # Create volume chart
            fig_vol = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                   vertical_spacing=0.03, row_heights=[0.7, 0.3],
                                   subplot_titles=('Price with Volume MAs', 'Volume Bars'))
            
            # Price and volume moving averages
            fig_vol.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['close_price'],
                mode='lines', name='Close Price',
                line=dict(color='blue', width=2),
                hovertemplate="<b>Close</b><br>Date: %{x}<br>Price: $%{y:.2f}<extra></extra>"
            ), row=1, col=1)
            
            # Volume bars with color coding
            colors = []
            for i in range(len(volume_df)):
                if i == 0:
                    colors.append('gray')
                elif volume_df['close_price'].iloc[i] > volume_df['close_price'].iloc[i-1]:
                    colors.append('green')
                else:
                    colors.append('red')
            
            fig_vol.add_trace(go.Bar(
                x=volume_df['trading_date'], y=volume_df['volume'],
                name='Volume', marker_color=colors,
                hovertemplate="<b>Volume</b><br>Date: %{x}<br>Volume: %{y:,.0f}<extra></extra>"
            ), row=2, col=1)
            
            # Add volume moving averages to volume chart
            fig_vol.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['volume_ma_20'],
                mode='lines', name='Vol MA 20',
                line=dict(color='orange', width=2),
                hovertemplate="<b>Vol MA 20</b><br>Date: %{x}<br>Volume: %{y:,.0f}<extra></extra>"
            ), row=2, col=1)
            
            fig_vol.update_layout(
                title="Volume Analysis - Price Movement vs Volume Activity",
                height=chart_height,
                hovermode='x unified',
                showlegend=True
            )
            
            fig_vol.update_xaxes(showgrid=True, rangeslider=dict(visible=True), row=2, col=1)
            st.plotly_chart(fig_vol, width="stretch", config=create_enhanced_plotly_config())
        
        # 6.2 VWAP Analysis
        if "VWAP" in volume_indicators:
            st.markdown("#### 🎯 VWAP (Volume Weighted Average Price)")
            
            # VWAP statistics
            current_price = volume_df['close_price'].iloc[-1] if not volume_df.empty else None
            current_vwap = volume_df['vwap'].iloc[-1] if not volume_df.empty else None
            
            if current_price and current_vwap:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if current_price > current_vwap:
                        distance = ((current_price - current_vwap) / current_vwap) * 100
                        st.metric("VWAP Position", "🟢 ABOVE", f"+{distance:.1f}%")
                    else:
                        distance = ((current_vwap - current_price) / current_vwap) * 100
                        st.metric("VWAP Position", "🔴 BELOW", f"-{distance:.1f}%")
                
                with col2:
                    st.metric("Current VWAP", f"${current_vwap:.2f}")
                
                with col3:
                    # Check if price is within VWAP bands
                    vwap_upper_1 = volume_df['vwap_upper_1'].iloc[-1]
                    vwap_lower_1 = volume_df['vwap_lower_1'].iloc[-1]
                    
                    if current_price > vwap_upper_1:
                        st.metric("VWAP Band", "🔥 ABOVE +1%", "Strong buyers")
                    elif current_price < vwap_lower_1:
                        st.metric("VWAP Band", "❄️ BELOW -1%", "Strong sellers")
                    else:
                        st.metric("VWAP Band", "⚖️ WITHIN 1%", "Fair value")
                
                with col4:
                    # VWAP trend
                    vwap_slope = volume_df['vwap'].diff().tail(5).mean()
                    if vwap_slope > 0:
                        st.metric("VWAP Trend", "📈 RISING", "Bullish bias")
                    else:
                        st.metric("VWAP Trend", "📉 FALLING", "Bearish bias")
            
            with st.expander("📚 VWAP Trading Strategy", expanded=False):
                st.markdown("""
                **VWAP as Support/Resistance:**
                - **Above VWAP**: Bullish bias - VWAP acts as support
                - **Below VWAP**: Bearish bias - VWAP acts as resistance
                - **Price at VWAP**: Fair value - watch for direction
                
                **VWAP Band Trading:**
                - **Outside +2% Band**: Extreme deviation - expect mean reversion
                - **Outside +1% Band**: Strong move - trend continuation likely
                - **Within Bands**: Normal trading range
                
                **Institutional Use:**
                - Large institutions use VWAP as execution benchmark
                - Heavy volume near VWAP = institutional interest
                """)
            
            # Create VWAP chart
            fig_vwap = go.Figure()
            
            # Price
            fig_vwap.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['close_price'],
                mode='lines', name='Close Price',
                line=dict(color='blue', width=3),
                hovertemplate="<b>Close</b><br>Date: %{x}<br>Price: $%{y:.2f}<extra></extra>"
            ))
            
            # VWAP
            fig_vwap.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['vwap'],
                mode='lines', name='VWAP',
                line=dict(color='purple', width=2),
                hovertemplate="<b>VWAP</b><br>Date: %{x}<br>VWAP: $%{y:.2f}<extra></extra>"
            ))
            
            # VWAP Bands
            fig_vwap.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['vwap_upper_2'],
                mode='lines', name='VWAP +2%',
                line=dict(color='red', width=1, dash='dash'),
                hovertemplate="<b>VWAP +2%</b><br>Date: %{x}<br>Value: $%{y:.2f}<extra></extra>"
            ))
            
            fig_vwap.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['vwap_upper_1'],
                mode='lines', name='VWAP +1%',
                line=dict(color='orange', width=1, dash='dot'),
                hovertemplate="<b>VWAP +1%</b><br>Date: %{x}<br>Value: $%{y:.2f}<extra></extra>"
            ))
            
            fig_vwap.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['vwap_lower_1'],
                mode='lines', name='VWAP -1%',
                line=dict(color='orange', width=1, dash='dot'),
                fill='tonexty', fillcolor='rgba(128,0,128,0.1)',
                hovertemplate="<b>VWAP -1%</b><br>Date: %{x}<br>Value: $%{y:.2f}<extra></extra>"
            ))
            
            fig_vwap.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['vwap_lower_2'],
                mode='lines', name='VWAP -2%',
                line=dict(color='red', width=1, dash='dash'),
                hovertemplate="<b>VWAP -2%</b><br>Date: %{x}<br>Value: $%{y:.2f}<extra></extra>"
            ))
            
            fig_vwap = enhance_chart_layout(fig_vwap, "VWAP Analysis - Volume Weighted Average Price with Deviation Bands", chart_height)
            st.plotly_chart(fig_vwap, width="stretch", config=create_enhanced_plotly_config())
        
        # 6.3 On-Balance Volume (OBV)
        if "OBV" in volume_indicators:
            st.markdown("#### ⚖️ On-Balance Volume (OBV)")
            
            # OBV statistics
            current_obv = volume_df['obv_raw'].iloc[-1] if not volume_df.empty else None
            obv_ma_10 = volume_df['obv_ma_10'].iloc[-1] if not volume_df.empty else None
            obv_ma_20 = volume_df['obv_ma_20'].iloc[-1] if not volume_df.empty else None
            
            if current_obv and obv_ma_10 and obv_ma_20:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if current_obv > obv_ma_20:
                        st.metric("OBV Trend", "🟢 BULLISH", "Above MA 20")
                    else:
                        st.metric("OBV Trend", "🔴 BEARISH", "Below MA 20")
                
                with col2:
                    st.metric("Current OBV", f"{current_obv:,.0f}")
                
                with col3:
                    if obv_ma_10 > obv_ma_20:
                        st.metric("OBV MAs", "📈 RISING", "MA 10 > MA 20")
                    else:
                        st.metric("OBV MAs", "📉 FALLING", "MA 10 < MA 20")
                
                with col4:
                    # OBV momentum
                    obv_change = volume_df['obv_raw'].pct_change(periods=5).iloc[-1] * 100
                    if obv_change > 5:
                        st.metric("OBV Momentum", "🚀 STRONG+", f"+{obv_change:.1f}%")
                    elif obv_change < -5:
                        st.metric("OBV Momentum", "💥 STRONG-", f"{obv_change:.1f}%")
                    else:
                        st.metric("OBV Momentum", "😐 WEAK", f"{obv_change:.1f}%")
            
            with st.expander("📚 OBV Analysis Guide", expanded=False):
                st.markdown("""
                **OBV Interpretation:**
                - **OBV Rising + Price Rising**: Confirmed uptrend
                - **OBV Falling + Price Falling**: Confirmed downtrend
                - **OBV Divergence**: OBV direction differs from price (warning signal)
                
                **Trading Signals:**
                - **OBV Above MA 20**: Bullish volume momentum
                - **OBV Below MA 20**: Bearish volume momentum
                - **OBV Breakout**: OBV breaks resistance/support before price
                
                **Smart Money Tracking:**
                - OBV often leads price movements
                - Use OBV to confirm trend strength
                - Watch for OBV divergences at key levels
                """)
            
            # Create OBV chart
            fig_obv = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                   vertical_spacing=0.03, row_heights=[0.6, 0.4],
                                   subplot_titles=('Price Chart', 'On-Balance Volume'))
            
            # Price
            fig_obv.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['close_price'],
                mode='lines', name='Close Price',
                line=dict(color='blue', width=2),
                hovertemplate="<b>Price</b><br>Date: %{x}<br>Price: $%{y:.2f}<extra></extra>"
            ), row=1, col=1)
            
            # OBV
            fig_obv.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['obv_raw'],
                mode='lines', name='OBV',
                line=dict(color='green', width=2),
                fill='tozeroy', fillcolor='rgba(0,128,0,0.1)',
                hovertemplate="<b>OBV</b><br>Date: %{x}<br>OBV: %{y:,.0f}<extra></extra>"
            ), row=2, col=1)
            
            # OBV moving averages
            fig_obv.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['obv_ma_10'],
                mode='lines', name='OBV MA 10',
                line=dict(color='orange', width=1),
                hovertemplate="<b>OBV MA 10</b><br>Date: %{x}<br>Value: %{y:,.0f}<extra></extra>"
            ), row=2, col=1)
            
            fig_obv.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['obv_ma_20'],
                mode='lines', name='OBV MA 20',
                line=dict(color='red', width=1),
                hovertemplate="<b>OBV MA 20</b><br>Date: %{x}<br>Value: %{y:,.0f}<extra></extra>"
            ), row=2, col=1)
            
            fig_obv.update_layout(
                title="On-Balance Volume - Smart Money Flow Analysis",
                height=chart_height,
                hovermode='x unified',
                showlegend=True
            )
            
            fig_obv.update_xaxes(showgrid=True, rangeslider=dict(visible=True), row=2, col=1)
            st.plotly_chart(fig_obv, width="stretch", config=create_enhanced_plotly_config())
        
        # 6.4 Money Flow Index (MFI)
        if "MFI" in volume_indicators:
            st.markdown("#### 💰 Money Flow Index (MFI) - Volume-Weighted RSI")
            
            # MFI statistics
            current_mfi = volume_df['mfi'].iloc[-1] if not volume_df.empty else None
            
            if current_mfi:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if current_mfi > 80:
                        st.metric("MFI Signal", "🔴 OVERBOUGHT", f"{current_mfi:.1f}")
                    elif current_mfi < 20:
                        st.metric("MFI Signal", "🟢 OVERSOLD", f"{current_mfi:.1f}")
                    else:
                        st.metric("MFI Signal", "🟡 NEUTRAL", f"{current_mfi:.1f}")
                
                with col2:
                    mfi_mean = volume_df['mfi'].mean()
                    st.metric("Average MFI", f"{mfi_mean:.1f}")
                
                with col3:
                    # MFI momentum
                    mfi_change = volume_df['mfi'].diff().tail(3).mean()
                    if mfi_change > 2:
                        st.metric("MFI Momentum", "📈 RISING", f"+{mfi_change:.1f}")
                    elif mfi_change < -2:
                        st.metric("MFI Momentum", "📉 FALLING", f"{mfi_change:.1f}")
                    else:
                        st.metric("MFI Momentum", "➡️ FLAT", f"{mfi_change:.1f}")
                
                with col4:
                    # Extreme readings percentage
                    extreme_readings = ((volume_df['mfi'] > 80) | (volume_df['mfi'] < 20)).sum()
                    extreme_pct = (extreme_readings / len(volume_df)) * 100
                    st.metric("Extreme Readings", f"{extreme_pct:.1f}%")
            
            with st.expander("📚 MFI Trading Strategy", expanded=False):
                st.markdown("""
                **MFI vs RSI:**
                - MFI includes volume data (more reliable)
                - RSI only uses price data
                - MFI gives fewer but higher quality signals
                
                **Trading Levels:**
                - **> 80**: Overbought - look for selling opportunities
                - **< 20**: Oversold - look for buying opportunities
                - **50**: Momentum line - above = bullish, below = bearish
                
                **Advanced Techniques:**
                - **Divergence**: MFI and price move in opposite directions
                - **Failure Swings**: MFI fails to reach previous extreme
                - **Volume Confirmation**: High MFI readings need volume confirmation
                """)
            
            # Create MFI chart
            fig_mfi = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                   vertical_spacing=0.03, row_heights=[0.6, 0.4],
                                   subplot_titles=('Price Chart', 'Money Flow Index'))
            
            # Price
            fig_mfi.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['close_price'],
                mode='lines', name='Close Price',
                line=dict(color='blue', width=2),
                hovertemplate="<b>Price</b><br>Date: %{x}<br>Price: $%{y:.2f}<extra></extra>"
            ), row=1, col=1)
            
            # MFI
            fig_mfi.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['mfi'],
                mode='lines', name='MFI',
                line=dict(color='purple', width=2),
                hovertemplate="<b>MFI</b><br>Date: %{x}<br>MFI: %{y:.1f}<extra></extra>"
            ), row=2, col=1)
            
            # Add MFI zones
            fig_mfi.add_hline(y=80, line_dash="dash", line_color="red", 
                             annotation_text="Overbought (80)", annotation_position="right", row=2, col=1)
            fig_mfi.add_hline(y=20, line_dash="dash", line_color="green", 
                             annotation_text="Oversold (20)", annotation_position="right", row=2, col=1)
            fig_mfi.add_hline(y=50, line_dash="dot", line_color="gray", 
                             annotation_text="Momentum Line (50)", annotation_position="right", row=2, col=1)
            
            # Add colored background zones
            fig_mfi.add_hrect(y0=80, y1=100, fillcolor="red", opacity=0.1, line_width=0, row=2, col=1)
            fig_mfi.add_hrect(y0=0, y1=20, fillcolor="green", opacity=0.1, line_width=0, row=2, col=1)
            
            fig_mfi.update_layout(
                title="Money Flow Index - Volume-Weighted Momentum Oscillator",
                height=chart_height,
                hovermode='x unified',
                showlegend=True
            )
            
            fig_mfi.update_yaxes(range=[0, 100], row=2, col=1)
            fig_mfi.update_xaxes(showgrid=True, rangeslider=dict(visible=True), row=2, col=1)
            st.plotly_chart(fig_mfi, width="stretch", config=create_enhanced_plotly_config())
        
        # 6.5 Accumulation/Distribution Line
        if "A/D Line" in volume_indicators:
            st.markdown("#### 📈 Accumulation/Distribution Line")
            
            # A/D Line statistics
            current_ad = volume_df['ad_line'].iloc[-1] if not volume_df.empty else None
            ad_ma_20 = volume_df['ad_ma_20'].iloc[-1] if not volume_df.empty else None
            
            if current_ad and ad_ma_20:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if current_ad > ad_ma_20:
                        st.metric("A/D Trend", "🟢 ACCUMULATION", "Above MA 20")
                    else:
                        st.metric("A/D Trend", "🔴 DISTRIBUTION", "Below MA 20")
                
                with col2:
                    st.metric("Current A/D", f"{current_ad:,.0f}")
                
                with col3:
                    # A/D momentum
                    ad_change = volume_df['ad_line'].pct_change(periods=10).iloc[-1] * 100
                    if ad_change > 10:
                        st.metric("A/D Momentum", "🚀 STRONG+", f"+{ad_change:.1f}%")
                    elif ad_change < -10:
                        st.metric("A/D Momentum", "💥 STRONG-", f"{ad_change:.1f}%")
                    else:
                        st.metric("A/D Momentum", "😐 WEAK", f"{ad_change:.1f}%")
                
                with col4:
                    # A/D Line direction
                    ad_slope = volume_df['ad_line'].diff().tail(5).mean()
                    if ad_slope > 0:
                        st.metric("A/D Direction", "📈 RISING", "Smart money buying")
                    else:
                        st.metric("A/D Direction", "📉 FALLING", "Smart money selling")
            
            with st.expander("📚 A/D Line Analysis", expanded=False):
                st.markdown("""
                **What A/D Line Shows:**
                - **Rising A/D**: Accumulation phase - smart money buying
                - **Falling A/D**: Distribution phase - smart money selling
                - **A/D Divergence**: A/D direction differs from price (key signal)
                
                **Trading Applications:**
                - **Trend Confirmation**: A/D should confirm price trends
                - **Early Warning**: A/D often changes direction before price
                - **Volume Quality**: Shows if volume is accumulative or distributive
                
                **Key Patterns:**
                - **A/D New High + Price New High**: Strong bull trend
                - **A/D Flat + Price Rising**: Weak rally, likely to fail
                - **A/D Rising + Price Falling**: Hidden strength, potential reversal
                """)
            
            # Create A/D Line chart
            fig_ad = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                  vertical_spacing=0.03, row_heights=[0.6, 0.4],
                                  subplot_titles=('Price Chart', 'Accumulation/Distribution Line'))
            
            # Price
            fig_ad.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['close_price'],
                mode='lines', name='Close Price',
                line=dict(color='blue', width=2),
                hovertemplate="<b>Price</b><br>Date: %{x}<br>Price: $%{y:.2f}<extra></extra>"
            ), row=1, col=1)
            
            # A/D Line
            fig_ad.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['ad_line'],
                mode='lines', name='A/D Line',
                line=dict(color='darkgreen', width=2),
                fill='tozeroy', fillcolor='rgba(0,100,0,0.1)',
                hovertemplate="<b>A/D Line</b><br>Date: %{x}<br>A/D: %{y:,.0f}<extra></extra>"
            ), row=2, col=1)
            
            # A/D moving average
            fig_ad.add_trace(go.Scatter(
                x=volume_df['trading_date'], y=volume_df['ad_ma_20'],
                mode='lines', name='A/D MA 20',
                line=dict(color='orange', width=1),
                hovertemplate="<b>A/D MA 20</b><br>Date: %{x}<br>Value: %{y:,.0f}<extra></extra>"
            ), row=2, col=1)
            
            fig_ad.update_layout(
                title="Accumulation/Distribution Line - Smart Money Flow Tracking",
                height=chart_height,
                hovermode='x unified',
                showlegend=True
            )
            
            fig_ad.update_xaxes(showgrid=True, rangeslider=dict(visible=True), row=2, col=1)
            st.plotly_chart(fig_ad, width="stretch", config=create_enhanced_plotly_config())
    else:
        st.info("📊 Volume data not available for volume-based indicators.")
    
    # ----------------------------
    # NEW ADVANCED INDICATORS
    # ----------------------------
    
    # 7. Fibonacci Retracement & Extension Levels
    if fibonacci_df is not None and not fibonacci_df.empty:
        st.markdown("---")
        st.markdown("### 📐 Fibonacci Retracement & Extension Levels")
        
        with st.expander("📚 Understanding Fibonacci Levels", expanded=False):
            st.markdown("""
            **Key Fibonacci Levels:**
            - **23.6%**: Minor support/resistance
            - **38.2%**: Moderate pullback level
            - **50.0%**: Psychological level (not Fibonacci, but widely watched)
            - **61.8%**: The Golden Ratio - strongest Fibonacci level
            - **78.6%**: Deep retracement before reversal
            
            **Extension Levels (Profit Targets):**
            - **127.2%**: First profit target
            - **161.8%**: Major profit target (Golden extension)
            - **200.0%**: Extreme profit target
            
            **Trading Strategy:**
            - Look for bounces at Fibonacci support levels
            - Set profit targets at extension levels
            - Combine with other indicators for confirmation
            """)
        
        # Display current Fibonacci signals
        if 'fib_trade_signal' in fibonacci_df.columns:
            latest_signal = fibonacci_df['fib_trade_signal'].iloc[-1] if not fibonacci_df.empty else "NO_SIGNAL"
            latest_position = fibonacci_df['fib_position'].iloc[-1] if 'fib_position' in fibonacci_df.columns else "N/A"
            
            col1, col2 = st.columns(2)
            with col1:
                signal_emoji = "🟢" if "BUY" in str(latest_signal) else "🔴" if "SELL" in str(latest_signal) else "🟡"
                st.metric("Current Fibonacci Signal", f"{signal_emoji} {latest_signal}")
            with col2:
                st.metric("Price Position", latest_position)
        
        # Fibonacci chart
        fig_fib = go.Figure()
        fig_fib.add_trace(go.Scatter(
            x=fibonacci_df['trading_date'], y=fibonacci_df['close_price'],
            mode='lines', name='Close Price',
            line=dict(color='blue', width=2)
        ))
        
        # Add key Fibonacci levels
        if 'fib_20d_0618' in fibonacci_df.columns:
            fig_fib.add_trace(go.Scatter(
                x=fibonacci_df['trading_date'], y=fibonacci_df['fib_20d_0618'],
                mode='lines', name='Fib 61.8% (20d)',
                line=dict(color='gold', width=1, dash='dash')
            ))
        if 'fib_20d_0500' in fibonacci_df.columns:
            fig_fib.add_trace(go.Scatter(
                x=fibonacci_df['trading_date'], y=fibonacci_df['fib_20d_0500'],
                mode='lines', name='Fib 50% (20d)',
                line=dict(color='orange', width=1, dash='dot')
            ))
        
        fig_fib.update_layout(
            title=f"Fibonacci Levels for {ticker}",
            xaxis_title="Date",
            yaxis_title="Price",
            height=500,
            hovermode='x unified'
        )
        st.plotly_chart(fig_fib, use_container_width=True, config=create_enhanced_plotly_config())
    
    # 8. Stochastic Oscillator
    if stochastic_df is not None and not stochastic_df.empty:
        st.markdown("---")
        st.markdown("### 🎢 Stochastic Oscillator - Momentum Indicator")
        
        with st.expander("📚 Stochastic Oscillator Guide", expanded=False):
            st.markdown("""
            **Stochastic Basics:**
            - **%K Line**: Fast line (like MACD)
            - **%D Line**: Slow line (3-period moving average of %K)
            - **Range**: 0-100
            
            **Overbought/Oversold:**
            - **Above 80**: Overbought zone → potential sell
            - **Below 20**: Oversold zone → potential buy
            - **50-80**: Bullish momentum
            - **20-50**: Bearish momentum
            
            **Trading Signals:**
            - **Bullish Cross**: %K crosses above %D in oversold zone
            - **Bearish Cross**: %K crosses below %D in overbought zone
            - **Divergence**: Price makes new high/low but Stochastic doesn't
            """)
        
        # Display current Stochastic status
        if 'stoch_14d_k' in stochastic_df.columns:
            latest_k = stochastic_df['stoch_14d_k'].iloc[-1]
            latest_d = stochastic_df['stoch_14d_d'].iloc[-1]
            latest_status = stochastic_df['stoch_status'].iloc[-1] if 'stoch_status' in stochastic_df.columns else "N/A"
            latest_signal = stochastic_df['stoch_trade_signal'].iloc[-1] if 'stoch_trade_signal' in stochastic_df.columns else "NO_SIGNAL"
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("%K (14d)", f"{latest_k:.1f}")
            with col2:
                st.metric("%D (14d)", f"{latest_d:.1f}")
            with col3:
                status_emoji = "🔴" if "OVERBOUGHT" in latest_status else "🟢" if "OVERSOLD" in latest_status else "🟡"
                st.metric("Status", f"{status_emoji} {latest_status}")
            with col4:
                signal_emoji = "🟢" if "BUY" in latest_signal else "🔴" if "SELL" in latest_signal else "🟡"
                st.metric("Signal", f"{signal_emoji} {latest_signal.replace('_', ' ')}")
        
        # Stochastic chart
        fig_stoch = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                  vertical_spacing=0.03, row_heights=[0.6, 0.4])
        
        # Price chart
        fig_stoch.add_trace(go.Scatter(
            x=stochastic_df['trading_date'], y=stochastic_df['close_price'],
            mode='lines', name='Close Price',
            line=dict(color='blue', width=2)
        ), row=1, col=1)
        
        # Stochastic %K and %D
        fig_stoch.add_trace(go.Scatter(
            x=stochastic_df['trading_date'], y=stochastic_df['stoch_14d_k'],
            mode='lines', name='%K (14)',
            line=dict(color='blue', width=2)
        ), row=2, col=1)
        
        fig_stoch.add_trace(go.Scatter(
            x=stochastic_df['trading_date'], y=stochastic_df['stoch_14d_d'],
            mode='lines', name='%D (14)',
            line=dict(color='red', width=2)
        ), row=2, col=1)
        
        # Add overbought/oversold lines
        fig_stoch.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="Overbought", row=2, col=1)
        fig_stoch.add_hline(y=20, line_dash="dash", line_color="green", annotation_text="Oversold", row=2, col=1)
        fig_stoch.add_hline(y=50, line_dash="dot", line_color="gray", row=2, col=1)
        
        fig_stoch.update_layout(
            title=f"Stochastic Oscillator for {ticker}",
            height=600,
            hovermode='x unified'
        )
        fig_stoch.update_yaxes(range=[0, 100], row=2, col=1)
        fig_stoch.update_xaxes(rangeslider=dict(visible=True), row=2, col=1)
        st.plotly_chart(fig_stoch, use_container_width=True, config=create_enhanced_plotly_config())
    
    # 9. Support & Resistance Levels
    if support_resistance_df is not None and not support_resistance_df.empty:
        st.markdown("---")
        st.markdown("### 🎯 Support & Resistance Levels - Key Price Zones")
        
        with st.expander("📚 Support & Resistance Trading Guide", expanded=False):
            st.markdown("""
            **Support & Resistance Basics:**
            - **Pivot Point**: Central reference level calculated from previous period
            - **Resistance (R1, R2, R3)**: Price levels where selling pressure expected
            - **Support (S1, S2, S3)**: Price levels where buying pressure expected
            
            **Trading Strategies:**
            - **Buy near support**: Enter long positions when price approaches S1/S2
            - **Sell near resistance**: Take profits or short when price reaches R1/R2
            - **Breakout trading**: Strong moves above R3 or below S3 signal trends
            - **Range trading**: Trade between support and resistance in sideways markets
            
            **Price Zones:**
            - **BULLISH_ZONE**: Price above pivot point
            - **BEARISH_ZONE**: Price below pivot point
            - **NEAR_SUPPORT_BUY**: Price approaching support level
            - **NEAR_RESISTANCE_SELL**: Price approaching resistance level
            """)
        
        # Display current S/R levels
        if 'sr_trade_signal' in support_resistance_df.columns:
            latest_signal = support_resistance_df['sr_trade_signal'].iloc[-1]
            latest_zone = support_resistance_df['pivot_status'].iloc[-1] if 'pivot_status' in support_resistance_df.columns else "N/A"
            current_price = support_resistance_df['close_price'].iloc[-1]
            pivot = support_resistance_df['pivot_point'].iloc[-1] if 'pivot_point' in support_resistance_df.columns else 0
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Current Price", f"${current_price:.2f}")
            with col2:
                st.metric("Pivot Point", f"${pivot:.2f}")
            with col3:
                zone_emoji = "🟢" if "ABOVE" in latest_zone else "🔴" if "BELOW" in latest_zone else "🟡"
                st.metric("Price Zone", f"{zone_emoji} {latest_zone}")
            with col4:
                signal_emoji = "🟢" if "BUY" in latest_signal else "🔴" if "SELL" in latest_signal else "🟡"
                st.metric("Trading Signal", f"{signal_emoji} {latest_signal.replace('_', ' ')}")
        
        # S/R chart with levels
        fig_sr = go.Figure()
        fig_sr.add_trace(go.Scatter(
            x=support_resistance_df['trading_date'],
            y=support_resistance_df['close_price'],
            mode='lines', name='Close Price',
            line=dict(color='blue', width=2)
        ))
        
        # Add S/R levels
        if 'r3' in support_resistance_df.columns:
            fig_sr.add_trace(go.Scatter(
                x=support_resistance_df['trading_date'], y=support_resistance_df['r3'],
                mode='lines', name='R3', line=dict(color='darkred', width=1, dash='dash')
            ))
        if 'r2' in support_resistance_df.columns:
            fig_sr.add_trace(go.Scatter(
                x=support_resistance_df['trading_date'], y=support_resistance_df['r2'],
                mode='lines', name='R2', line=dict(color='red', width=1, dash='dash')
            ))
        if 'r1' in support_resistance_df.columns:
            fig_sr.add_trace(go.Scatter(
                x=support_resistance_df['trading_date'], y=support_resistance_df['r1'],
                mode='lines', name='R1', line=dict(color='orange', width=1, dash='dash')
            ))
        if 'pivot_point' in support_resistance_df.columns:
            fig_sr.add_trace(go.Scatter(
                x=support_resistance_df['trading_date'], y=support_resistance_df['pivot_point'],
                mode='lines', name='Pivot', line=dict(color='purple', width=2)
            ))
        if 's1' in support_resistance_df.columns:
            fig_sr.add_trace(go.Scatter(
                x=support_resistance_df['trading_date'], y=support_resistance_df['s1'],
                mode='lines', name='S1', line=dict(color='lightgreen', width=1, dash='dash')
            ))
        if 's2' in support_resistance_df.columns:
            fig_sr.add_trace(go.Scatter(
                x=support_resistance_df['trading_date'], y=support_resistance_df['s2'],
                mode='lines', name='S2', line=dict(color='green', width=1, dash='dash')
            ))
        if 's3' in support_resistance_df.columns:
            fig_sr.add_trace(go.Scatter(
                x=support_resistance_df['trading_date'], y=support_resistance_df['s3'],
                mode='lines', name='S3', line=dict(color='darkgreen', width=1, dash='dash')
            ))
        
        fig_sr.update_layout(
            title=f"Support & Resistance Levels for {ticker}",
            xaxis_title="Date",
            yaxis_title="Price",
            height=600,
            hovermode='x unified'
        )
        fig_sr.update_xaxes(rangeslider=dict(visible=True))
        st.plotly_chart(fig_sr, use_container_width=True, config=create_enhanced_plotly_config())
    
    # 10. Candlestick Pattern Detection
    if candlestick_patterns_df is not None and not candlestick_patterns_df.empty:
        st.markdown("---")
        st.markdown("### 🕯️ Candlestick Pattern Recognition")
        
        with st.expander("📚 Candlestick Patterns Encyclopedia", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                **Bullish Patterns:**
                - **Hammer**: Reversal signal at bottom
                - **Bullish Engulfing**: Strong reversal
                - **Morning Star**: 3-candle reversal pattern
                - **Inverse Head & Shoulders**: Major reversal
                - **Cup and Handle**: Continuation pattern
                - **Double Bottom**: Support confirmation
                """)
            with col2:
                st.markdown("""
                **Bearish Patterns:**
                - **Shooting Star**: Reversal at top
                - **Bearish Engulfing**: Strong reversal down
                - **Evening Star**: 3-candle bearish reversal
                - **Head & Shoulders**: Major reversal
                - **Inverse Cup Handle**: Bearish continuation
                - **Double Top**: Resistance confirmation
                """)
        
        # Display recent patterns
        if 'patterns_detected' in candlestick_patterns_df.columns:
            patterns_last_30 = candlestick_patterns_df.tail(30)
            patterns_found = patterns_last_30[patterns_last_30['patterns_detected'].notna()]
            
            if not patterns_found.empty:
                st.markdown("#### 🔍 Recent Patterns Detected (Last 30 Days)")
                
                # Show pattern summary
                latest_pattern = patterns_found.iloc[-1]
                latest_signal = latest_pattern['pattern_signal'] if 'pattern_signal' in latest_pattern else "NO_PATTERN"
                
                col1, col2 = st.columns(2)
                with col1:
                    signal_emoji = "🟢" if "BUY" in latest_signal else "🔴" if "SELL" in latest_signal else "🟡"
                    st.metric("Latest Pattern Signal", f"{signal_emoji} {latest_signal}")
                with col2:
                    st.metric("Patterns in Last 30 Days", len(patterns_found))
                
                # Display patterns table
                display_df = patterns_found[['trading_date', 'close_price', 'patterns_detected', 'pattern_signal']].copy()
                display_df['trading_date'] = display_df['trading_date'].dt.strftime('%Y-%m-%d')
                st.dataframe(
                    display_df.sort_values('trading_date', ascending=False),
                    use_container_width=True,
                    column_config={
                        'trading_date': 'Date',
                        'close_price': st.column_config.NumberColumn('Close Price', format="$%.2f"),
                        'patterns_detected': 'Pattern(s)',
                        'pattern_signal': 'Signal'
                    }
                )
            else:
                st.info("No candlestick patterns detected in the last 30 days.")


def plot_signal_view(view_type: str, df: pd.DataFrame, label: str):
    if df is None or df.empty:
        st.info(f"No {label} signals available for this selection.")
        return

    # Map to correct columns based on your metadata
    if view_type == "BB":
        value_col = "close_price"
        signal_col = "bb_trade_signal"
        title = f"🎯 Interactive Bollinger Band Trade Signals"
        y_label = "Close Price"
        description = """
        **What to look for:**
        - 🟢 **BUY**: Price touches lower band + other indicators confirm oversold
        - 🔴 **SELL**: Price touches upper band + other indicators confirm overbought
        - ⚡ **Squeeze**: Bands getting narrow → Big move coming soon
        """
        color_map = {'BUY': 'green', 'Buy': 'green', 'buy': 'green',
                    'SELL': 'red', 'Sell': 'red', 'sell': 'red'}
    elif view_type == "MACD":
        value_col = "MACD"
        signal_col = "MACD_Signal"
        title = f"🚀 Interactive MACD Trade Signals"
        y_label = "MACD"
        description = """
        **Trading Signals:**
        - 🟢 **BUY**: MACD line crosses above Signal line (Golden crossover)
        - 🔴 **SELL**: MACD line crosses below Signal line (Death crossover)
        - ⚡ **Trend**: MACD above zero = Bullish, below zero = Bearish
        """
        color_map = {'BUY': 'green', 'Buy': 'green', 'buy': 'green',
                    'SELL': 'red', 'Sell': 'red', 'sell': 'red'}
    elif view_type == "RSI":
        value_col = "RSI"
        signal_col = "rsi_trade_signal"
        title = f"⚡ Interactive RSI Trade Signals"
        y_label = "RSI"
        description = """
        **Momentum Signals:**
        - 🟢 **BUY**: RSI below 30 (oversold) + starts moving up
        - 🔴 **SELL**: RSI above 70 (overbought) + starts moving down
        - 🎯 **Best**: Combine with trend direction for higher success rate
        """
        color_map = {'BUY': 'green', 'Buy': 'green', 'buy': 'green',
                    'SELL': 'red', 'Sell': 'red', 'sell': 'red'}
    elif view_type == "SMA":
        value_col = "close_price"
        signal_col = "sma_trade_signal"
        title = f"📊 Interactive Moving Average Trade Signals"
        y_label = "Close Price"
        description = """
        **Trend Following:**
        - 🟢 **BUY**: Price crosses above key moving averages
        - 🔴 **SELL**: Price crosses below key moving averages
        - 🏆 **Golden Rule**: Trade in direction of 200 SMA for best results
        """
        color_map = {'BUY': 'green', 'Buy': 'green', 'buy': 'green',
                    'SELL': 'red', 'Sell': 'red', 'sell': 'red'}
    elif view_type == "ATR":
        value_col = "ATR_14"
        signal_col = "atr_volatility_signal"
        title = f"💥 Interactive ATR Volatility Signals"
        y_label = "ATR 14"
        description = """
        **Volatility Alerts:**
        - 🔥 **High ATR**: Reduce position size, use wider stops
        - 😴 **Low ATR**: Potential breakout coming, prepare for big moves
        - ⚖️ **Risk Management**: Use ATR multiples for stop losses
        """
        color_map = {'HIGH': 'red', 'High': 'red', 'high': 'red',
                    'LOW': 'green', 'Low': 'green', 'low': 'green',
                    'NORMAL': 'blue', 'Normal': 'blue', 'normal': 'blue'}
    else:
        st.warning(f"Unknown view type: {view_type}")
        return

    # Validate columns
    if value_col not in df.columns or signal_col not in df.columns:
        st.warning(f"Expected columns '{value_col}' or '{signal_col}' not found in data.")
        st.dataframe(df)
        return

    df = df.copy()
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    st.markdown(f"### {title}")
    
    # Create expandable description and controls
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(description)
    
    with col2:
        # Chart controls
        chart_type = st.selectbox(
            "Chart Type:",
            ["Scatter", "Line + Signals", "Candlestick"],
            key=f"{view_type}_chart_type"
        )
        
        show_all_data = st.checkbox(
            "Show All Data Points",
            value=False,
            key=f"{view_type}_show_all"
        )
    
    # Enhanced signal summary with statistics    if signal_col in df.columns:
        signal_counts = df[signal_col].value_counts()
        if not signal_counts.empty:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_signals = len(df[df[signal_col].notna()])
                st.metric("Total Signals", total_signals)
            with col2:
                buy_signals = signal_counts.get('BUY', signal_counts.get('Buy', signal_counts.get('buy', 0)))
                if total_signals > 0:
                    buy_pct = (buy_signals / total_signals) * 100
                    st.metric("Buy Signals", buy_signals, f"{buy_pct:.1f}%")
                else:
                    st.metric("Buy Signals", buy_signals)
            with col3:
                sell_signals = signal_counts.get('SELL', signal_counts.get('Sell', signal_counts.get('sell', 0)))
                if total_signals > 0:
                    sell_pct = (sell_signals / total_signals) * 100
                    st.metric("Sell Signals", sell_signals, f"{sell_pct:.1f}%")
                else:
                    st.metric("Sell Signals", sell_signals)
            with col4:
                if buy_signals > 0 and sell_signals > 0:
                    signal_ratio = buy_signals / sell_signals
                    st.metric("Buy/Sell Ratio", f"{signal_ratio:.2f}")
                else:
                    st.metric("Buy/Sell Ratio", "N/A")

    # Filter data with signals for analysis (used later in performance section)
    signal_df = df[df[signal_col].notna()]

    # Create enhanced interactive chart
    fig = go.Figure()
    
    if chart_type == "Scatter":
        # Enhanced scatter plot with better interactivity
        for signal_type in df[signal_col].unique():
            if pd.notna(signal_type):
                signal_data = df[df[signal_col] == signal_type]
                
                fig.add_trace(go.Scatter(
                    x=signal_data['trading_date'],
                    y=signal_data[value_col],
                    mode='markers',
                    name=f"{signal_type} Signal",
                    marker=dict(
                        size=12,
                        color=color_map.get(signal_type, 'gray'),
                        line=dict(width=2, color='white'),
                        symbol='circle'
                    ),
                    hovertemplate=f"<b>{signal_type} Signal</b><br>" +
                                 "Date: %{x}<br>" +
                                 f"{y_label}: %{{y:.2f}}<br>" +
                                 "<extra></extra>"
                ))
        
        # Add background line if requested
        if show_all_data:
            fig.add_trace(go.Scatter(
                x=df['trading_date'],
                y=df[value_col],
                mode='lines',
                name=y_label,
                line=dict(color='lightgray', width=1),
                hovertemplate=f"<b>{y_label}</b><br>" +
                             "Date: %{x}<br>" +
                             f"Value: %{{y:.2f}}<br>" +
                             "<extra></extra>",
                showlegend=True
            ))
    
    elif chart_type == "Line + Signals":
        # Line chart with signal markers
        fig.add_trace(go.Scatter(
            x=df['trading_date'],
            y=df[value_col],
            mode='lines',
            name=y_label,
            line=dict(color='blue', width=2),
            hovertemplate=f"<b>{y_label}</b><br>" +
                         "Date: %{x}<br>" +
                         f"Value: %{{y:.2f}}<br>" +
                         "<extra></extra>"        ))
        
        # Add signal markers on top
        if not signal_df.empty:
            for signal_type in signal_df[signal_col].unique():
                if pd.notna(signal_type):
                    signal_data = signal_df[signal_df[signal_col] == signal_type]
                    
                    fig.add_trace(go.Scatter(
                        x=signal_data['trading_date'],
                        y=signal_data[value_col],
                        mode='markers',
                        name=f"{signal_type}",
                        marker=dict(
                            size=15,
                            color=color_map.get(signal_type, 'gray'),
                            line=dict(width=2, color='white'),
                            symbol='star' if 'BUY' in str(signal_type).upper() else 'x'
                        ),
                        hovertemplate=f"<b>{signal_type} Signal</b><br>" +
                                     "Date: %{x}<br>" +
                                     f"{y_label}: %{{y:.2f}}<br>" +
                                     "<extra></extra>"
                    ))
    
    # Enhance chart layout with better interactivity
    fig.update_layout(
        title={
            'text': f"{title} - {label}",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16, 'color': '#2E4057'}
        },
        height=600,
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.8)"
        ),
        xaxis=dict(
            title="Date",
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)',
            showspikes=True,
            spikesnap='cursor',
            spikemode='across',
            spikethickness=1,
            rangeslider=dict(visible=True, thickness=0.05),
            type='date'
        ),
        yaxis=dict(
            title=y_label,
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)',
            showspikes=True,
            spikesnap='cursor',
            spikemode='across',
            spikethickness=1
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=10, r=10, t=60, b=40)
    )
    
    # Add range selector buttons
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True),
            type="date"
        )
    )
    
    # Enhanced plotly config for better interactivity
    config = {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToAdd': [
            'drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect', 'eraseshape'
        ],
        'modeBarButtonsToRemove': ['lasso2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f'{view_type}_signals_chart',
            'height': 600,
            'width': 1200,
            'scale': 1
        },
        'scrollZoom': True,
        'doubleClick': 'reset+autosize'
    }
    
    st.plotly_chart(fig, width="stretch", config=config)
    
    # Add signal analysis summary
    with st.expander("📈 Signal Performance Analysis", expanded=False):
        if not signal_df.empty and len(signal_df) > 1:
            col1, col2 = st.columns(2)
            
            with col1:
                # Time-based analysis
                signal_df_sorted = signal_df.sort_values('trading_date')
                if len(signal_df_sorted) >= 2:
                    last_signal = signal_df_sorted.iloc[-1][signal_col]
                    prev_signal = signal_df_sorted.iloc[-2][signal_col]
                    
                    st.markdown("**Recent Signal Pattern:**")
                    st.write(f"Previous: {prev_signal}")
                    st.write(f"Latest: {last_signal}")
                    
                    # Calculate days since last signal
                    days_since = (df['trading_date'].max() - signal_df_sorted.iloc[-1]['trading_date']).days
                    st.write(f"Days since last signal: {days_since}")
            
            with col2:
                # Signal frequency analysis
                st.markdown("**Signal Frequency:**")
                total_days = (df['trading_date'].max() - df['trading_date'].min()).days
                if total_days > 0:
                    signals_per_month = (total_signals / total_days) * 30
                    st.write(f"Average signals per month: {signals_per_month:.1f}")
                
                # Most common signal
                most_common = signal_counts.index[0] if not signal_counts.empty else "None"
                st.write(f"Most frequent signal: {most_common}")
        else:
            st.info("Insufficient signal data for performance analysis.")

# ----------------------------
# FLIGHT STATUS DASHBOARD FUNCTIONS
# ----------------------------

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_flight_status_data(index_name: str, limit: int = None) -> pd.DataFrame:
    """
    SIMPLIFIED: Flight status data using only core tables that exist
    Fixed to work with your actual database structure
    """
    
    # Map to your existing table and view names
    if index_name == 'NSE 500':
        base_table = 'nse_500_hist_data'
        rsi_view = 'nse_500_RSI_calculation'
        macd_view = 'nse_500_macd'
        bb_view = 'nse_500_bollingerband'
        sma_view = 'nse_500_ema_sma_view'
        atr_view = 'nse_500_atr'
        ticker_col = 'ticker'
    elif index_name == 'Forex':
        base_table = 'forex_hist_data'
        rsi_view = 'forex_RSI_calculation'
        macd_view = 'forex_macd'
        bb_view = 'forex_bollingerband'
        sma_view = 'forex_ema_sma_view'
        atr_view = 'forex_atr'
        ticker_col = 'symbol'
    else:  # NASDAQ 100
        base_table = 'nasdaq_100_hist_data'
        rsi_view = 'nasdaq_100_RSI_calculation'
        macd_view = 'nasdaq_100_macd'
        bb_view = 'nasdaq_100_bollingerband' 
        sma_view = 'nasdaq_100_ema_sma_view'
        atr_view = 'nasdaq_100_atr'
        ticker_col = 'ticker'
    
    limit_clause = f"TOP {limit}" if limit else ""  # No default limit - load all stocks
    
    # Simplified query using only existing indicator views (no signal tables)
    query = f"""
    WITH 
    -- Get latest price data for each stock
    LatestPrices AS (
        SELECT 
            {ticker_col} as ticker,
            company,
            trading_date,
            CAST(close_price AS FLOAT) AS close_price,
            CAST(open_price AS FLOAT) AS open_price,
            CAST(high_price AS FLOAT) AS high_price,
            CAST(low_price AS FLOAT) AS low_price,
            CAST(volume AS FLOAT) AS volume,
            -- Calculate daily change
            ROUND(((CAST(close_price AS FLOAT) - CAST(open_price AS FLOAT)) / CAST(open_price AS FLOAT)) * 100, 2) as daily_change_pct,
            ROW_NUMBER() OVER (PARTITION BY {ticker_col} ORDER BY trading_date DESC) as rn
        FROM dbo.{base_table}
    ),
    
    -- Latest RSI values
    LatestRSI AS (
        SELECT 
            {ticker_col} as ticker,
            RSI,
            ROW_NUMBER() OVER (PARTITION BY {ticker_col} ORDER BY trading_date DESC) as rn
        FROM dbo.{rsi_view}
    ),
    
    -- Latest MACD values  
    LatestMACD AS (
        SELECT 
            {ticker_col} as ticker,
            MACD,
            Signal_Line,
            ROW_NUMBER() OVER (PARTITION BY {ticker_col} ORDER BY trading_date DESC) as rn
        FROM dbo.{macd_view}
    ),
    
    -- Latest Bollinger Bands
    LatestBB AS (
        SELECT 
            {ticker_col} as ticker,
            Upper_Band,
            Lower_Band,
            ROW_NUMBER() OVER (PARTITION BY {ticker_col} ORDER BY trading_date DESC) as rn
        FROM dbo.{bb_view}
    ),
    
    -- Latest Moving Averages
    LatestSMA AS (
        SELECT 
            {ticker_col} as ticker,
            SMA_50,
            SMA_200,
            EMA_50,
            ROW_NUMBER() OVER (PARTITION BY {ticker_col} ORDER BY trading_date DESC) as rn
        FROM dbo.{sma_view}
    ),
    
    -- Latest ATR
    LatestATR AS (
        SELECT 
            {ticker_col} as ticker, 
            ATR_14,
            ROW_NUMBER() OVER (PARTITION BY {ticker_col} ORDER BY trading_date DESC) as rn
        FROM dbo.{atr_view}
    )
    
    -- Main query combining all data
    SELECT {limit_clause}
        p.ticker,
        p.company,
        p.trading_date as last_update,
        p.close_price,
        p.daily_change_pct,
        p.volume,
        
        -- Technical Indicators
        r.RSI,
        m.MACD,
        m.Signal_Line as MACD_Signal_Line,
        bb.Upper_Band,
        bb.Lower_Band,
        sma.SMA_50,
        sma.SMA_200,
        sma.EMA_50,
        atr.ATR_14,
        
        -- Calculated Trading Signals (derived from indicators)
        CASE 
            WHEN r.RSI < 30 THEN 'Buy'
            WHEN r.RSI > 70 THEN 'Sell'
            ELSE 'Hold'
        END as rsi_signal,
        
        CASE 
            WHEN m.MACD > m.Signal_Line THEN 'Buy'
            WHEN m.MACD < m.Signal_Line THEN 'Sell'
            ELSE 'Hold'
        END as macd_signal,
        
        CASE 
            WHEN p.close_price < bb.Lower_Band THEN 'Buy'
            WHEN p.close_price > bb.Upper_Band THEN 'Sell'
            ELSE 'Hold'
        END as bb_signal,
        
        CASE 
            WHEN sma.SMA_50 > sma.SMA_200 THEN 'Buy'
            WHEN sma.SMA_50 < sma.SMA_200 THEN 'Sell'
            ELSE 'Hold'
        END as sma_signal,
        
        -- Calculated Analysis Fields
        CASE 
            WHEN r.RSI > 70 THEN 'Overbought'
            WHEN r.RSI < 30 THEN 'Oversold'
            ELSE 'Neutral'
        END as rsi_status,
        
        CASE 
            WHEN m.MACD > m.Signal_Line THEN 'Bullish'
            WHEN m.MACD < m.Signal_Line THEN 'Bearish'
            ELSE 'Neutral'
        END as macd_trend,
        
        CASE 
            WHEN p.close_price > sma.SMA_200 THEN 'Uptrend'
            WHEN p.close_price < sma.SMA_200 THEN 'Downtrend' 
            ELSE 'Sideways'
        END as long_term_trend,
        
        -- Signal Strength Score (-4 to +4) based on indicators
        (
            -- RSI contribution 
            CASE 
                WHEN r.RSI < 30 THEN 1
                WHEN r.RSI > 70 THEN -1 
                ELSE 0 
            END +
            
            -- MACD contribution
            CASE 
                WHEN m.MACD > m.Signal_Line THEN 1
                WHEN m.MACD < m.Signal_Line THEN -1
                ELSE 0 
            END +
            
            -- BB contribution
            CASE 
                WHEN p.close_price < bb.Lower_Band THEN 1
                WHEN p.close_price > bb.Upper_Band THEN -1
                ELSE 0 
            END +
            
            -- SMA contribution (Golden/Death Cross)
            CASE 
                WHEN sma.SMA_50 > sma.SMA_200 THEN 1
                WHEN sma.SMA_50 < sma.SMA_200 THEN -1
                ELSE 0 
            END
        ) as signal_score,
        
        -- Market Cap Category (based on volume as proxy)
        CASE 
            WHEN p.volume > 1000000 THEN 'Large Cap'
            WHEN p.volume > 100000 THEN 'Mid Cap'
            ELSE 'Small Cap'
        END as market_cap_category
        
    FROM LatestPrices p
    LEFT JOIN LatestRSI r ON p.ticker = r.ticker AND r.rn = 1
    LEFT JOIN LatestMACD m ON p.ticker = m.ticker AND m.rn = 1
    LEFT JOIN LatestBB bb ON p.ticker = bb.ticker AND bb.rn = 1
    LEFT JOIN LatestSMA sma ON p.ticker = sma.ticker AND sma.rn = 1
    LEFT JOIN LatestATR atr ON p.ticker = atr.ticker AND atr.rn = 1
    WHERE p.rn = 1
    ORDER BY p.ticker
    """
    
    return execute_query_safe(query)

def render_flight_status_summary_metrics(df: pd.DataFrame):
    """Render the summary metrics at the top of flight status dashboard"""
    if df.empty:
        return
        
    total_stocks = len(df)
    buy_signals = len(df[df['signal_score'] > 0])
    sell_signals = len(df[df['signal_score'] < 0])
    hold_signals = len(df[df['signal_score'] == 0])
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("🛩️ Total Stocks", f"{total_stocks:,}")
    
    with col2:
        st.metric("🟢 Buy Signals", f"{buy_signals}", f"{buy_signals/total_stocks:.1%}")
    
    with col3:
        st.metric("🔴 Sell Signals", f"{sell_signals}", f"{sell_signals/total_stocks:.1%}")
    
    with col4:
        st.metric("🟡 Hold/Neutral", f"{hold_signals}", f"{hold_signals/total_stocks:.1%}")
    
    with col5:
        avg_score = df['signal_score'].mean()
        st.metric("📊 Avg Signal Score", f"{avg_score:.1f}", 
                 "🟢 Bullish" if avg_score > 0 else "🔴 Bearish" if avg_score < 0 else "🟡 Neutral")

def apply_flight_status_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render filter controls and return filtered dataframe for flight status"""
    if df.empty:
        return df
    
    st.sidebar.subheader("🔍 Flight Status Filters")
    
    # Search Filter - NEW!
    search_term = st.sidebar.text_input(
        "🔎 Search Stock",
        "",
        placeholder="Enter ticker or company name...",
        key="flight_search_filter",
        help="Search by ticker symbol or company name"
    )
    
    # Signal Type Filter
    signal_types = ['All', 'Strong Buy (4-5)', 'Buy (1-3)', 'Hold (0)', 'Sell (-3 to -1)', 'Strong Sell (-5 to -4)']
    selected_signal = st.sidebar.selectbox("Signal Type", signal_types, key="flight_signal_filter")
    
    # RSI Status Filter
    rsi_statuses = ['All'] + df['rsi_status'].dropna().unique().tolist()
    selected_rsi = st.sidebar.selectbox("RSI Status", rsi_statuses, key="flight_rsi_filter")
    
    # Trend Filter
    trends = ['All'] + df['long_term_trend'].dropna().unique().tolist()
    selected_trend = st.sidebar.selectbox("Long-term Trend", trends, key="flight_trend_filter")
    
    # Market Cap Filter
    market_caps = ['All'] + df['market_cap_category'].dropna().unique().tolist()
    selected_cap = st.sidebar.selectbox("Market Cap", market_caps, key="flight_cap_filter")
    
    # Apply filters
    filtered_df = df.copy()
    
    # Search filter - apply first
    if search_term:
        search_lower = search_term.lower()
        filtered_df = filtered_df[
            filtered_df['ticker'].str.lower().str.contains(search_lower, na=False) |
            filtered_df['company'].str.lower().str.contains(search_lower, na=False)
        ]
    
    # Signal filter
    if selected_signal != 'All':
        if selected_signal == 'Strong Buy (4-5)':
            filtered_df = filtered_df[filtered_df['signal_score'] >= 4]
        elif selected_signal == 'Buy (1-3)':
            filtered_df = filtered_df[(filtered_df['signal_score'] >= 1) & (filtered_df['signal_score'] <= 3)]
        elif selected_signal == 'Hold (0)':
            filtered_df = filtered_df[filtered_df['signal_score'] == 0]
        elif selected_signal == 'Sell (-3 to -1)':
            filtered_df = filtered_df[(filtered_df['signal_score'] <= -1) & (filtered_df['signal_score'] >= -3)]
        elif selected_signal == 'Strong Sell (-5 to -4)':
            filtered_df = filtered_df[filtered_df['signal_score'] <= -4]
    
    # Other filters
    if selected_rsi != 'All':
        filtered_df = filtered_df[filtered_df['rsi_status'] == selected_rsi]
    
    if selected_trend != 'All':
        filtered_df = filtered_df[filtered_df['long_term_trend'] == selected_trend]
    
    if selected_cap != 'All':
        filtered_df = filtered_df[filtered_df['market_cap_category'] == selected_cap]
    
    return filtered_df

def get_flight_status_emoji(score):
    """Get emoji for flight status"""
    if score >= 4:
        return '✈️🟢'  # Ready for takeoff
    elif score >= 1:
        return '🟢'     # Boarding
    elif score == 0:
        return '🟡'     # On schedule
    elif score >= -3:
        return '🟠'     # Delayed
    else:
        return '🔴'     # Cancelled

# ----------------------------
# MAIN APP
# ----------------------------
st.set_page_config(
    page_title="📈 Advanced Trading Dashboard", 
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://docs.streamlit.io/library/api-reference',
        'Report a bug': None,
        'About': "Advanced Trading Dashboard with Interactive Charts"
    }
)
st.title("📊 Advanced Stock Trading Dashboard with AI Analysis")

# ----------------------------
# SIDEBAR - DATABASE CONNECTION MANAGEMENT
# ----------------------------
st.sidebar.header("🔧 Database Management")
if st.sidebar.button("🔄 Reset Database Connections", help="Click if you're experiencing database connection issues"):
    reset_database_connections()

# ----------------------------
# PAGE NAVIGATION
# ----------------------------
st.sidebar.header("📊 Dashboard Controls")

# Page Navigation
st.sidebar.markdown("### 🧭 Page Navigation")
page = st.sidebar.radio(
    "Select Page:",
    ["🏠 Home & Filters", "📋 Data in Table format", "📈 Technical Analysis", "🤖 AI Price Predictions", "🛩️ Flight Status Dashboard", "📊 NASDAQ ML Predictions", "📈 NSE ML Predictions", "💱 Forex ML Predictions", "📊 Reco Tracking and Current Status", "📈 Today Trend Recommendations", "🤖 AI Trading Signals Scanner", "📊 Master Data Editor", "💼 My Portfolio Tracker", "👨‍👩‍👧‍👦 For Family"],
    index=0,
    key="main_page_selector"
)

st.sidebar.markdown("---")

# Store page selection in session state for use in page functions
st.session_state.selected_page = page

# ----------------------------
# PAGE FUNCTIONS
# ----------------------------

def show_home_page():
    """Home page with market/stock selection and filters"""
    
    # Welcome section
    st.markdown("""
    # 🏠 Welcome to Your Advanced Trading Dashboard
    
    ### 📊 Central Control Hub
    Select your market, stock, and preferences below. These settings will apply to all pages of the dashboard.
    
    ---
    """)

    # Check if we have session data to display
    if 'selected_ticker' not in st.session_state:
        st.session_state.selected_ticker = None
    if 'index_option' not in st.session_state:
        st.session_state.index_option = "NSE 500"

    # Market and ticker selection
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📈 Market Selection")
        index_option = st.radio("Select Index", ["NSE 500", "NASDAQ 100", "Forex"], key="home_index")
        
        # Store in session state
        st.session_state.index_option = index_option
        
    # Clear session state when market selection changes
    if 'prev_market' not in st.session_state:
        st.session_state.prev_market = index_option
    elif st.session_state.prev_market != index_option:
        # Market changed, clear related session states
        if 'selected_ticker' in st.session_state:
            del st.session_state.selected_ticker
        if 'date_range' in st.session_state:
            del st.session_state.date_range
        if 'price_df' in st.session_state:
            del st.session_state.price_df
        st.session_state.prev_market = index_option
        
    with col2:
        st.markdown("### 🔍 Stock Selection")
        
        # Load ticker data
        try:
            ticker_df = get_tickers(index_option)
        except Exception as e:
            st.error(f"Error loading tickers: {str(e)}")
            return
            
        if ticker_df.empty:
            st.error("❌ No tickers available for this market.")
            return
        
        # Show helpful info for Forex market
        if index_option == "Forex":
            st.info(f"💱 **Available Forex symbols:** {', '.join(sorted(ticker_df['ticker'].tolist()))}")
            st.caption("Note: Only symbols listed above have complete historical data for AI analysis.")
            
        # Dynamic placeholder based on market selection
        if index_option == "NSE 500":
            placeholder_text = "e.g., RELIANCE, TCS, INFY"
        elif index_option == "Forex":
            placeholder_text = "e.g., EUR/USD, GBP/JPY, USD/CAD"
        else:  # NASDAQ 100
            placeholder_text = "e.g., AAPL, MSFT, TSLA"
            
        search_ticker = st.text_input("🔎 Search Ticker:", placeholder=placeholder_text, key="home_search").upper()

        if search_ticker:
            ticker_df = ticker_df[ticker_df["ticker"].str.contains(search_ticker, case=False, na=False)]
            if ticker_df.empty:
                st.error("❌ No tickers found for this search.")
                return
            else:
                st.success(f"✅ Found {len(ticker_df)} ticker(s)")

        selected_ticker = st.selectbox("📊 Choose Ticker:", ticker_df["ticker"].tolist(), key="home_ticker")
        
        # Store in session state
        st.session_state.selected_ticker = selected_ticker
        
        # Clear date range session state when ticker changes
        if 'prev_ticker' not in st.session_state:
            st.session_state.prev_ticker = selected_ticker
        elif st.session_state.prev_ticker != selected_ticker:
            # Ticker changed, clear date range session state
            if 'date_range' in st.session_state:
                del st.session_state.date_range
            if 'price_df' in st.session_state:
                del st.session_state.price_df
            st.session_state.prev_ticker = selected_ticker
        
    if selected_ticker:
        st.success(f"📈 Selected: **{selected_ticker}** from **{index_option}**")
        
        # Load price data to get date range
        with st.spinner("Loading data for date range..."):
            try:
                price_df = load_price_data(index_option, selected_ticker)
            except Exception as e:
                st.error(f"Error loading price data: {str(e)}")
                return
            
        if price_df is None or price_df.empty:
            st.error("❌ No price data available for this ticker.")
            return
            
        # Store price data in session state
        st.session_state.price_df = price_df
        
        # Date range selection
        st.markdown("### 📅 Date Range Selection")
        
        date_min = price_df["trading_date"].min()
        date_max = price_df["trading_date"].max()
        
        # Quick date range buttons
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("📅 Last 1M", key="home_1m_filter"):
                start_date_quick = date_max - pd.DateOffset(months=1)
                st.session_state.date_range = [start_date_quick, date_max]
        with col2:
            if st.button("📅 Last 3M", key="home_3m_filter"):
                start_date_quick = date_max - pd.DateOffset(months=3)
                st.session_state.date_range = [start_date_quick, date_max]
        with col3:
            if st.button("📅 Last 6M", key="home_6m_filter"):
                start_date_quick = date_max - pd.DateOffset(months=6)
                st.session_state.date_range = [start_date_quick, date_max]
        with col4:
            if st.button("📅 Last 1Y", key="home_1y_filter"):
                start_date_quick = date_max - pd.DateOffset(years=1)
                st.session_state.date_range = [start_date_quick, date_max]

        # Initialize session state for date range
        if 'date_range' not in st.session_state:
            st.session_state.date_range = [date_min, date_max]

        start_date, end_date = st.date_input(
            "📅 Custom Date Range:",
            value=st.session_state.date_range,
            min_value=date_min,
            max_value=date_max,
            key="home_date_range"
        )
        
        # Update session state with selected dates
        st.session_state.date_range = [start_date, end_date]
        
        # Chart preferences
        st.markdown("### ⚙️ Chart & Display Preferences")
        
        col1, col2 = st.columns(2)
        
        with col1:
            default_chart_height = st.selectbox(
                "📏 Default Chart Height:", 
                [500, 600, 700, 800], 
                index=1,
                key="home_chart_height"
            )
            
            chart_theme = st.selectbox(
                "🎨 Chart Theme:",
                ["Default", "Dark", "Plotly White"],
                index=0,
                key="home_theme"
            )
            
        with col2:
            show_gridlines = st.checkbox("📋 Show Gridlines", value=True, key="home_gridlines")
            enable_crossfilter = st.checkbox("🎯 Enable Crossfilter", value=True, key="home_crossfilter")
            show_education = st.checkbox("📚 Show Educational Content", value=True, key="home_education")
            
        # Store preferences in session state
        st.session_state.chart_preferences = {
            'height': default_chart_height,
            'theme': chart_theme,
            'gridlines': show_gridlines,
            'crossfilter': enable_crossfilter,
            'education': show_education
        }
        
        # Data summary
        st.markdown("### 📊 Current Selection Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            data_points = len(price_df)
            st.metric("📈 Total Data Points", data_points)
            
        with col2:
            date_range_days = (date_max - date_min).days
            st.metric("📅 Date Range (Days)", date_range_days)
            
        with col3:
            if data_points > 0:
                current_price = price_df['close_price'].iloc[-1]
                st.metric("💰 Current Price", f"${current_price:.2f}")
                
        with col4:
            if data_points > 1:
                price_change = current_price - price_df['close_price'].iloc[0]
                price_change_pct = (price_change / price_df['close_price'].iloc[0] * 100)
                st.metric("📈 Period Change", f"{price_change_pct:.1f}%")
        
        # Navigation suggestions
        st.markdown("---")
        st.markdown("### 🧭 Ready to Analyze?")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **📈 Technical Analysis Page**
            - Interactive charts with professional indicators
            - RSI, MACD, Bollinger Bands, and more
            - Trading signals and educational content
            - Risk management tools
            """)
            
        with col2:
            st.markdown("""
            **🤖 AI Price Predictions Page**
            - Machine learning price forecasting
            - Multiple ML models (Random Forest, Linear Regression)
            - Feature importance analysis
            - Risk assessment and trading recommendations
            """)
            
        st.info("💡 **Tip:** Use the navigation in the sidebar to switch between pages. Your selections will be remembered!")
    else:
        st.info("👆 Please select a market and stock to get started!")


def show_data_table_page():
    """Data in Table format page with historical data from NSE, NASDAQ, and Forex"""
    st.markdown("""
    # 📋 Data in Table format
    
    ### 📊 Historical Market Data in Tabular View
    
    View and analyze historical market data from NSE 500, NASDAQ 100, and Forex markets in a comprehensive table format.
    
    ---
    """)
    
    # Market selection
    col1, col2, col3 = st.columns(3)
    
    with col1:
        market_selection = st.selectbox(
            "🏪 Select Market:",
            ["NSE 500", "NASDAQ 100", "Forex"],
            key="table_market_selection"
        )
    
    with col2:
        date_range_option = st.selectbox(
            "📅 Date Range:",
            ["Last 30 Days", "Last 90 Days", "Last 6 Months", "Last 1 Year", "Custom Range"],
            key="table_date_range"
        )
    
    with col3:
        max_records = st.selectbox(
            "📊 Max Records:",
            [100, 500, 1000, 2000, 5000],
            index=2,
            key="table_max_records"
        )
    
    # Date range selection
    if date_range_option == "Custom Range":
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input(
                "Start Date:",
                value=(pd.Timestamp.now() - pd.Timedelta(days=30)).date(),
                key="table_start_date"
            )
        with col_end:
            end_date = st.date_input(
                "End Date:",
                value=pd.Timestamp.now().date(),
                key="table_end_date"
            )
    else:
        # Calculate date range based on selection
        end_date = pd.Timestamp.now().date()
        if date_range_option == "Last 30 Days":
            start_date = (pd.Timestamp.now() - pd.Timedelta(days=30)).date()
        elif date_range_option == "Last 90 Days":
            start_date = (pd.Timestamp.now() - pd.Timedelta(days=90)).date()
        elif date_range_option == "Last 6 Months":
            start_date = (pd.Timestamp.now() - pd.Timedelta(days=180)).date()
        else:  # Last 1 Year
            start_date = (pd.Timestamp.now() - pd.Timedelta(days=365)).date()
    
    # Additional filters
    st.markdown("### 🔍 Additional Filters")
    
    # Symbol/Ticker filter for NSE and NASDAQ
    if market_selection in ["NSE 500", "NASDAQ 100"]:
        symbol_filter = st.text_input(
            "🔍 Filter by Symbol/Ticker (optional):",
            placeholder="e.g., AAPL, RELIANCE.NS",
            key="table_symbol_filter"
        )
    else:  # Forex
        symbol_filter = st.text_input(
            "🔍 Filter by Currency Pair (optional):",
            placeholder="e.g., EURUSD, GBPUSD",
            key="table_forex_filter"
        )
    
    # Show/hide columns
    with st.expander("⚙️ Column Selection", expanded=False):
        st.markdown("Select which columns to display:")
        
        if market_selection in ["NSE 500", "NASDAQ 100"]:
            default_cols = ["ticker", "trading_date", "open_price", "high_price", "low_price", "close_price", "volume"]
            available_cols = default_cols + ["data_source", "last_updated", "created_at"]
        else:  # Forex
            default_cols = ["symbol", "trading_date", "open_price", "high_price", "low_price", "close_price"]
            available_cols = default_cols + ["data_source", "last_updated", "created_at"]
        
        selected_columns = st.multiselect(
            "Columns to display:",
            available_cols,
            default=default_cols,
            key="table_selected_columns"
        )
    
    # Load and display data
    if st.button("📊 Load Data", type="primary"):
        with st.spinner(f"Loading {market_selection} historical data..."):
            try:
                # Determine table name and columns based on market
                if market_selection == "NSE 500":
                    table_name = "nse_500_hist_data"
                    symbol_col = "ticker"
                elif market_selection == "NASDAQ 100":
                    table_name = "nasdaq_100_hist_data"
                    symbol_col = "ticker"
                else:  # Forex
                    table_name = "forex_hist_data"
                    symbol_col = "symbol"
                
                # Build query
                base_query = f"""
                SELECT TOP {max_records} {', '.join(selected_columns)}
                FROM dbo.{table_name}
                WHERE trading_date >= ? AND trading_date <= ?
                """
                
                params = [start_date, end_date]
                
                # Add symbol filter if provided
                if symbol_filter.strip():
                    if market_selection == "Forex":
                        base_query += f" AND {symbol_col} LIKE ?"
                        params.append(f"%{symbol_filter.strip()}%")
                    else:
                        base_query += f" AND {symbol_col} LIKE ?"
                        params.append(f"%{symbol_filter.strip().upper()}%")
                
                base_query += " ORDER BY trading_date DESC, " + symbol_col
                
                # Execute query
                df = execute_query_safe(base_query, params)
                
                if not df.empty:
                    # Clean and convert data types
                    try:
                        # Ensure trading_date is datetime
                        df['trading_date'] = pd.to_datetime(df['trading_date'])
                        
                        # Convert price columns to numeric, coercing errors to NaN
                        price_columns = ['open_price', 'high_price', 'low_price', 'close_price']
                        for col in price_columns:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce')
                        
                        # Convert volume to numeric if it exists
                        if 'volume' in df.columns:
                            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
                        
                    except Exception as e:
                        st.warning(f"Data type conversion warning: {e}. Proceeding with original data types.")
                    
                    # Display summary
                    st.success(f"📊 Loaded {len(df):,} records from {market_selection}")
                    
                    # Summary metrics with error handling
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        unique_symbols = df[symbol_col].nunique()
                        st.metric("🔢 Unique Symbols", unique_symbols)
                    
                    with col2:
                        try:
                            date_range_days = (df['trading_date'].max() - df['trading_date'].min()).days
                            st.metric("📅 Date Range", f"{date_range_days} days")
                        except:
                            st.metric("📅 Date Range", "N/A")
                    
                    with col3:
                        try:
                            min_date = df['trading_date'].min().strftime('%Y-%m-%d')
                            st.metric("📅 From Date", min_date)
                        except:
                            st.metric("📅 From Date", "N/A")
                    
                    with col4:
                        try:
                            max_date = df['trading_date'].max().strftime('%Y-%m-%d')
                            st.metric("📅 To Date", max_date)
                        except:
                            st.metric("📅 To Date", "N/A")
                    
                    st.markdown("---")
                    
                    # Display data table with improved formatting
                    st.markdown("### 📋 Historical Data Table")
                    
                    # Format the dataframe for better display
                    display_df = df.copy()
                    
                    try:
                        # Format date columns safely
                        if 'trading_date' in display_df.columns:
                            display_df['trading_date'] = pd.to_datetime(display_df['trading_date']).dt.strftime('%Y-%m-%d')
                        
                        # Format price columns safely
                        for col in price_columns:
                            if col in display_df.columns:
                                try:
                                    # Only round if the column is numeric
                                    display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(4)
                                except:
                                    # Keep original values if conversion fails
                                    pass
                        
                        # Format volume column safely
                        if 'volume' in display_df.columns:
                            try:
                                # Convert to numeric and format with commas
                                volume_numeric = pd.to_numeric(display_df['volume'], errors='coerce')
                                display_df['volume'] = volume_numeric.apply(lambda x: f"{x:,.0f}" if pd.notnull(x) and not pd.isna(x) else "N/A")
                            except:
                                # Keep original values if formatting fails
                                pass
                        
                    except Exception as e:
                        st.warning(f"Data formatting warning: {e}. Displaying with original formatting.")
                    
                    # Create column configuration for better display
                    column_config = {}
                    
                    try:
                        if 'trading_date' in display_df.columns:
                            column_config['trading_date'] = st.column_config.TextColumn('📅 Date')
                        if symbol_col in display_df.columns:
                            column_config[symbol_col] = st.column_config.TextColumn('🏷️ Symbol')
                        
                        # Only add number columns for successfully converted price data
                        for col in price_columns:
                            if col in display_df.columns:
                                try:
                                    # Check if the column is numeric after conversion
                                    if pd.api.types.is_numeric_dtype(display_df[col]):
                                        column_config[col] = st.column_config.NumberColumn(
                                            col.replace('_', ' ').title(),
                                            format="%.4f"
                                        )
                                    else:
                                        column_config[col] = st.column_config.TextColumn(col.replace('_', ' ').title())
                                except:
                                    column_config[col] = st.column_config.TextColumn(col.replace('_', ' ').title())
                        
                        if 'volume' in display_df.columns:
                            column_config['volume'] = st.column_config.TextColumn('📊 Volume')
                    
                    except Exception as e:
                        st.warning(f"Column configuration warning: {e}. Using default formatting.")
                        column_config = {}
                    
                    # Display the dataframe with error handling
                    try:
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            column_config=column_config,
                            hide_index=True
                        )
                    except Exception as e:
                        st.error(f"Error displaying table: {e}")
                        st.write("Raw data preview:")
                        st.write(display_df.head())
                    
                    # Download options
                    st.markdown("### 📥 Download Data")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        csv_data = df.to_csv(index=False)
                        st.download_button(
                            label="📄 Download as CSV",
                            data=csv_data,
                            file_name=f"{market_selection.lower().replace(' ', '_')}_data_{start_date}_{end_date}.csv",
                            mime="text/csv"
                        )
                    
                    with col2:
                        excel_buffer = BytesIO()
                        df.to_excel(excel_buffer, index=False, sheet_name='Historical Data')
                        excel_data = excel_buffer.getvalue()
                        
                        st.download_button(
                            label="📊 Download as Excel",
                            data=excel_data,
                            file_name=f"{market_selection.lower().replace(' ', '_')}_data_{start_date}_{end_date}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    
                else:
                    st.warning("No data found for the selected criteria. Try adjusting your filters.")
                
            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
                st.error("Please check your database connection and table structure.")
    
    # Information section
    with st.expander("ℹ️ About Data Sources", expanded=False):
        st.markdown(f"""
        **Current Selection: {market_selection}**
        
        **📊 NSE 500:**
        - Source Table: `dbo.nse_500_hist_data`
        - Contains: Indian stock market data for NSE 500 companies
        - Fields: ticker, trading_date, OHLC prices, volume
        
        **📈 NASDAQ 100:**
        - Source Table: `dbo.nasdaq_100_hist_data`
        - Contains: US stock market data for NASDAQ 100 companies
        - Fields: ticker, trading_date, OHLC prices, volume
        
        **💱 Forex:**
        - Source Table: `dbo.forex_hist_data`
        - Contains: Foreign exchange currency pair data
        - Fields: symbol, trading_date, OHLC prices
        
        **🔧 Features:**
        - Real-time data filtering and sorting
        - Customizable date ranges and record limits
        - Symbol/ticker specific filtering
        - Export to CSV and Excel formats
        - Responsive table display with professional formatting
        """)


def show_technical_analysis_page():
    """Show the main technical analysis dashboard"""
    
    # Add custom CSS for better interactivity and scrolling
    st.markdown("""
<style>
    /* Improve scrolling and layout */
    .main > div {
        max-width: 100%;
        padding-top: 1rem;
    }
    
    /* Make expanders more interactive */
    .streamlit-expanderHeader {
        background-color: #f0f2f6;
        border-radius: 5px;
    }
    
    /* Improve plotly chart container */
    .js-plotly-plot .plotly .modebar {
        background-color: rgba(255,255,255,0.7) !important;
    }
    
    /* Better spacing for metrics */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    
    /* Improve sidebar */
    .css-1d391kg {
        padding-top: 1rem;
    }
    
    /* Better button styling */
    .stButton > button {
        width: 100%;
        border-radius: 5px;
        background-color: #007ACC;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
    }
    
    /* Responsive tables */
    .dataframe {
        width: 100% !important;
    }
    
    /* Fix plotly toolbar positioning */
    .modebar {
        padding-top: 20px !important;
    }
</style>
""", unsafe_allow_html=True)    # Check if we have data from home page
    if 'selected_ticker' not in st.session_state or st.session_state.selected_ticker is None:
        st.warning("🏠 **Please select a market and stock from the Home page first!**")
        st.info("👈 Use the Home & Filters page in the sidebar to select your market, stock, and date range.")
        return
    
    # Get data from session state
    selected_ticker = st.session_state.selected_ticker
    index_option = st.session_state.index_option
    
    # Introduction section
    st.markdown(f"""
### 📈 Technical Analysis Dashboard for {selected_ticker}

**Market:** {index_option} | **Stock:** {selected_ticker}

This comprehensive technical analysis combines **professional indicators**, **trading education**, and **signal analysis** to help you make informed trading decisions.

---
""")

    # Load all base indicator data
    with st.spinner("Loading technical indicator data..."):
        price_df = load_price_data(index_option, selected_ticker)
        rsi_df = load_rsi(index_option, selected_ticker)
        bb_df = load_bbands(index_option, selected_ticker)
        macd_df = load_macd(index_option, selected_ticker)
        ema_sma_df = load_ema_sma(index_option, selected_ticker)
        atr_df = load_atr(index_option, selected_ticker)
        
        # Load new advanced indicators
        fibonacci_df = load_fibonacci(index_option, selected_ticker)
        stochastic_df = load_stochastic(index_option, selected_ticker)
        support_resistance_df = load_support_resistance(index_option, selected_ticker)
        candlestick_patterns_df = load_candlestick_patterns(index_option, selected_ticker)

    if price_df is None or price_df.empty:
        st.error("❌ No price data available for this ticker.")
        return

    # Get date range from session state
    if 'date_range' in st.session_state:
        start_date, end_date = st.session_state.date_range
    else:
        # Fallback to full range
        start_date = price_df["trading_date"].min()
        end_date = price_df["trading_date"].max()
    
    # Get chart preferences from session state
    chart_preferences = st.session_state.get('chart_preferences', {
        'height': 600,
        'theme': 'Default',
        'gridlines': True,
        'crossfilter': True,
        'education': True
    })

    # Sidebar controls for this page only
    st.sidebar.markdown("### 👁️ Technical Analysis Controls")
    show_education = st.sidebar.checkbox("📚 Show Educational Content", value=chart_preferences.get('education', True))
    show_indicators = st.sidebar.checkbox("📈 Show Indicator Charts", value=True)
    show_signals = st.sidebar.checkbox("🎯 Show Trading Signals", value=True)
    show_ai_analysis = st.sidebar.checkbox("🤖 Show AI Decision Matrix", value=True)
    
    st.sidebar.markdown("---")
    
    # Export options
    st.sidebar.markdown("### 💾 Export Current Analysis")
    
    # Generate downloadable reports
    csv_data, timestamp = create_downloadable_report(selected_ticker, index_option, price_df, rsi_df, bb_df, macd_df, ema_sma_df, atr_df)
    
    # CSV Download Button
    csv_filename = f"{selected_ticker}_{index_option.replace(' ', '_')}_technical_analysis_{timestamp}.csv"
    st.sidebar.download_button(
        label="📊 Download Technical Analysis (CSV)",
        data=csv_data,
        file_name=csv_filename,
        mime="text/csv",
        help="Download technical analysis data in CSV format"
    )    # Apply date filter to all indicator data
    price_df = filter_by_date(price_df, start_date, end_date)
    rsi_df = filter_by_date(rsi_df, start_date, end_date)
    bb_df = filter_by_date(bb_df, start_date, end_date)
    macd_df = filter_by_date(macd_df, start_date, end_date)
    ema_sma_df = filter_by_date(ema_sma_df, start_date, end_date)
    atr_df = filter_by_date(atr_df, start_date, end_date)

    st.markdown(
        f"### 📌 Analyzing: **{selected_ticker}** in **{index_option}** "
        f"from **{start_date}** to **{end_date}**"
    )

    # Load signal data (needed for all sections)
    bb_signals_df = load_signal_view(index_option, "BB", selected_ticker)
    macd_signals_df = load_signal_view(index_option, "MACD", selected_ticker)
    rsi_signals_df = load_signal_view(index_option, "RSI", selected_ticker)
    sma_signals_df = load_signal_view(index_option, "SMA", selected_ticker)
    atr_spikes_df = load_signal_view(index_option, "ATR", selected_ticker)

    # Apply same date filter to signal data
    bb_signals_df = filter_by_date(bb_signals_df, start_date, end_date)
    macd_signals_df = filter_by_date(macd_signals_df, start_date, end_date)
    rsi_signals_df = filter_by_date(rsi_signals_df, start_date, end_date)
    sma_signals_df = filter_by_date(sma_signals_df, start_date, end_date)
    atr_spikes_df = filter_by_date(atr_spikes_df, start_date, end_date)

    # ----------------------------
    # Section 1: Trading Education
    # ----------------------------
    if show_education:
        show_trading_guide()
        show_indicator_education()

    # ----------------------------
    # Section 2: Indicator Charts  
    # ----------------------------
    if show_indicators:
        st.markdown("---")
        with st.container():
            plot_indicator_section(
                price_df, rsi_df, macd_df, bb_df, ema_sma_df, atr_df,
                selected_ticker, index_option,
                fibonacci_df, stochastic_df, support_resistance_df, candlestick_patterns_df
            )

    # ----------------------------
    # Section 3: Trading Signal Views
    # ----------------------------
    if show_signals:
        st.markdown("---")
        st.header("🎯 Live Trading Signal Analysis")

        st.markdown(
            "📊 **Real-time signals from your SQL views** - These charts show entry/exit points based on your trading algorithms. "
            "Combine multiple signals for higher probability trades!"
        )

        # Add a summary dashboard for current signals
        st.markdown("### 📈 Current Market Summary")
        col1, col2, col3, col4 = st.columns(4)

        # Show latest signal from each indicator
        with col1:
            if not bb_signals_df.empty and 'bb_trade_signal' in bb_signals_df.columns:
                latest_bb = bb_signals_df['bb_trade_signal'].iloc[-1] if bb_signals_df['bb_trade_signal'].notna().any() else "No Signal"
                st.metric("Bollinger Bands", latest_bb, help="Latest BB signal")

        with col2:
            if not macd_signals_df.empty and 'MACD_Signal' in macd_signals_df.columns:
                latest_macd = macd_signals_df['MACD_Signal'].iloc[-1] if macd_signals_df['MACD_Signal'].notna().any() else "No Signal"
                st.metric("MACD", latest_macd, help="Latest MACD signal")

        with col3:
            if not rsi_signals_df.empty and 'rsi_trade_signal' in rsi_signals_df.columns:
                latest_rsi = rsi_signals_df['rsi_trade_signal'].iloc[-1] if rsi_signals_df['rsi_trade_signal'].notna().any() else "No Signal"
                st.metric("RSI", latest_rsi, help="Latest RSI signal")

        with col4:
            if not sma_signals_df.empty and 'sma_trade_signal' in sma_signals_df.columns:
                latest_sma = sma_signals_df['sma_trade_signal'].iloc[-1] if sma_signals_df['sma_trade_signal'].notna().any() else "No Signal"
                st.metric("Moving Average", latest_sma, help="Latest SMA signal")

        # Plot each signal view
        plot_signal_view("BB", bb_signals_df, f"{index_option} - {selected_ticker}")
        plot_signal_view("MACD", macd_signals_df, f"{index_option} - {selected_ticker}")
        plot_signal_view("RSI", rsi_signals_df, f"{index_option} - {selected_ticker}")
        plot_signal_view("SMA", sma_signals_df, f"{index_option} - {selected_ticker}")
        plot_signal_view("ATR", atr_spikes_df, f"{index_option} - {selected_ticker}")# ----------------------------
    # Section 4: Trading Decision Matrix
    # ----------------------------
    if show_ai_analysis:
        st.markdown("---")
        st.header("🧠 AI Trading Decision Matrix")
        
        # Add explanation of signal types
        with st.expander("ℹ️ Understanding Different Signal Types - READ THIS FIRST!", expanded=False):
            st.markdown("""
            ### 🎯 **Why Do Signals Sometimes Differ?**
            
            You might notice that the **Interactive Charts** show different signals than the **AI Trading Decision Matrix**. 
            This is **INTENTIONAL** and here's why:
            
            ---
            
            ### 📊 **Two Types of Analysis:**
            
            #### 1️⃣ **Interactive Chart Signals (Visual Analysis)**
            - **What it shows**: Current position of indicators
            - **MACD Example**: If MACD line is above Signal line → Shows "BULLISH"
            - **Moving Average Example**: If SMA 50 > SMA 200 → Shows "Golden Cross"
            - **Use Case**: Understand current market state and trend direction
            
            #### 2️⃣ **AI Trading Decision Matrix (Action Signals)**
            - **What it shows**: Actual trading signals (Buy/Sell/Hold)
            - **MACD Example**: Only triggers "BUY" when MACD **crosses above** Signal line (not just being above)
            - **Moving Average Example**: Triggers "BUY" when price **crosses above** moving averages
            - **Use Case**: Get specific entry/exit timing for trades
            
            ---
            
            ### 🔍 **Real Example - AUDUSD MACD:**
            
            | Indicator View | Shows | What It Means |
            |---------------|-------|---------------|
            | **Interactive MACD Chart** | MACD line above Signal line | Current state: "BULLISH position" |
            | **AI Trading Decision** | SELL or HOLD | No recent crossover = No new entry signal |
            
            **Why the difference?**
            - MACD might have crossed above the signal line **days ago** (chart shows bullish)
            - But no **recent crossover** means no new trade signal today (AI shows hold/sell)
            - The trend is bullish, but you missed the entry point!
            
            ---
            
            ### 📈 **How to Read Both Together:**
            
            #### ✅ **Best Trading Scenario:**
            1. **Chart shows**: MACD crossing above signal line (bullish crossover)
            2. **AI Decision shows**: BUY signal
            3. **SMA shows**: Golden Cross (50 > 200)
            4. **Action**: Strong buy signal with multiple confirmations!
            
            #### ⚠️ **Caution Scenario:**
            1. **Chart shows**: MACD above signal line (bullish)
            2. **AI Decision shows**: SELL or HOLD
            3. **Why**: Trend might be bullish, but momentum is weakening or already extended
            4. **Action**: Wait for pullback or new crossover signal
            
            #### 🔴 **Conflicting Signals:**
            1. **Chart shows**: Golden Cross (long-term bullish)
            2. **AI Decision shows**: BEARISH BIAS
            3. **Why**: Short-term momentum indicators (RSI, MACD) showing weakness
            4. **Action**: Long-term uptrend but short-term correction likely
            
            ---
            
            ### 🎓 **Key Takeaways:**
            
            | Signal Type | Best For | Time Frame |
            |------------|----------|------------|
            | **Interactive Charts** | Trend identification | Long-term view |
            | **AI Trading Decision** | Entry/Exit timing | Short-term action |
            | **Both Combined** | Complete picture | Best strategy! |
            
            ---
            
            ### 💡 **Pro Trading Tips:**
            
            1. **Use Charts for Context**:
               - Is the overall trend up or down?
               - Are we at support/resistance levels?
               
            2. **Use AI Signals for Timing**:
               - When should I enter?
               - When should I exit?
               
            3. **Wait for Alignment**:
               - Best trades happen when both chart trends AND AI signals agree
               - If they conflict, wait for clarity or reduce position size
               
            4. **Risk Management Always**:
               - Even with perfect signals, use stop losses
               - Position size based on volatility (ATR)
               - Never risk more than 1-2% per trade
            
            ---
            
            **Remember**: The market doesn't care about your position. Always use multiple confirmations and proper risk management! 🛡️
            """)

        # Create a comprehensive trading decision analysis
        def analyze_trading_signals(bb_df, macd_df, rsi_df, sma_df, atr_df,
                                    fibonacci_df=None, stochastic_df=None, 
                                    support_resistance_df=None, candlestick_patterns_df=None):
            decisions = []
            
            # Get latest values for analysis
            latest_data = {}
            
            # Bollinger Bands analysis
            if not bb_df.empty and 'bb_trade_signal' in bb_df.columns:
                latest_bb_signal = bb_df['bb_trade_signal'].iloc[-1] if bb_df['bb_trade_signal'].notna().any() else None
                latest_data['bb_signal'] = latest_bb_signal
            
            # MACD analysis
            if not macd_df.empty and 'MACD_Signal' in macd_df.columns:
                latest_macd_signal = macd_df['MACD_Signal'].iloc[-1] if macd_df['MACD_Signal'].notna().any() else None
                latest_data['macd_signal'] = latest_macd_signal
            
            # RSI analysis
            if not rsi_df.empty and 'rsi_trade_signal' in rsi_df.columns:
                latest_rsi_signal = rsi_df['rsi_trade_signal'].iloc[-1] if rsi_df['rsi_trade_signal'].notna().any() else None
                latest_data['rsi_signal'] = latest_rsi_signal
            
            # SMA analysis
            if not sma_df.empty and 'sma_trade_signal' in sma_df.columns:
                latest_sma_signal = sma_df['sma_trade_signal'].iloc[-1] if sma_df['sma_trade_signal'].notna().any() else None
                latest_data['sma_signal'] = latest_sma_signal
            
            # Fibonacci analysis
            if fibonacci_df is not None and not fibonacci_df.empty and 'fib_trade_signal' in fibonacci_df.columns:
                latest_fib_signal = fibonacci_df['fib_trade_signal'].iloc[-1] if fibonacci_df['fib_trade_signal'].notna().any() else None
                latest_data['fib_signal'] = latest_fib_signal
                if 'fib_position' in fibonacci_df.columns:
                    latest_data['fib_position'] = fibonacci_df['fib_position'].iloc[-1]
            
            # Stochastic analysis
            if stochastic_df is not None and not stochastic_df.empty and 'stoch_trade_signal' in stochastic_df.columns:
                latest_stoch_signal = stochastic_df['stoch_trade_signal'].iloc[-1] if stochastic_df['stoch_trade_signal'].notna().any() else None
                latest_data['stoch_signal'] = latest_stoch_signal
                if 'stoch_status' in stochastic_df.columns:
                    latest_data['stoch_status'] = stochastic_df['stoch_status'].iloc[-1]
            
            # Support/Resistance analysis
            if support_resistance_df is not None and not support_resistance_df.empty and 'sr_trade_signal' in support_resistance_df.columns:
                latest_sr_signal = support_resistance_df['sr_trade_signal'].iloc[-1] if support_resistance_df['sr_trade_signal'].notna().any() else None
                latest_data['sr_signal'] = latest_sr_signal
                if 'pivot_status' in support_resistance_df.columns:
                    latest_data['pivot_status'] = support_resistance_df['pivot_status'].iloc[-1]
            
            # Candlestick Pattern analysis
            if candlestick_patterns_df is not None and not candlestick_patterns_df.empty and 'pattern_signal' in candlestick_patterns_df.columns:
                latest_pattern_signal = candlestick_patterns_df['pattern_signal'].iloc[-1] if candlestick_patterns_df['pattern_signal'].notna().any() else None
                latest_data['pattern_signal'] = latest_pattern_signal
                if 'patterns_detected' in candlestick_patterns_df.columns:
                    latest_data['patterns_detected'] = candlestick_patterns_df['patterns_detected'].iloc[-1]
            
            return latest_data

        # Analyze current signals with all indicators
        signal_analysis = analyze_trading_signals(bb_signals_df, macd_signals_df, rsi_signals_df, sma_signals_df, atr_spikes_df,
                                                  fibonacci_df, stochastic_df, support_resistance_df, candlestick_patterns_df)
        
        # Add comparison table to show difference between chart view and trading signals
        st.markdown("### 📊 Signal Comparison: Chart View vs Trading Action")
        
        comparison_data = []
        
        # MACD Comparison
        macd_chart_status = "N/A"
        if not macd_signals_df.empty and 'MACD' in macd_signals_df.columns and 'Signal_Line' in macd_signals_df.columns:
            latest_macd_val = macd_signals_df['MACD'].iloc[-1]
            latest_signal_val = macd_signals_df['Signal_Line'].iloc[-1]
            if pd.notna(latest_macd_val) and pd.notna(latest_signal_val):
                macd_chart_status = "🟢 BULLISH (MACD > Signal)" if latest_macd_val > latest_signal_val else "🔴 BEARISH (MACD < Signal)"
        
        macd_action_signal = signal_analysis.get('macd_signal', 'N/A')
        comparison_data.append({
            'Indicator': 'MACD',
            'Chart View (Trend)': macd_chart_status,
            'Trading Signal (Action)': f"{'🟢' if 'buy' in str(macd_action_signal).lower() else '🔴' if 'sell' in str(macd_action_signal).lower() else '🟡'} {macd_action_signal}",
            'Meaning': 'Chart shows current position, Signal shows recent crossover action'
        })
        
        # SMA Comparison
        sma_chart_status = "N/A"
        if not sma_signals_df.empty and 'SMA_50' in sma_signals_df.columns and 'SMA_200' in sma_signals_df.columns:
            latest_sma50 = sma_signals_df['SMA_50'].iloc[-1]
            latest_sma200 = sma_signals_df['SMA_200'].iloc[-1]
            if pd.notna(latest_sma50) and pd.notna(latest_sma200):
                sma_chart_status = "🟢 Golden Cross (50>200)" if latest_sma50 > latest_sma200 else "🔴 Death Cross (50<200)"
        
        sma_action_signal = signal_analysis.get('sma_signal', 'N/A')
        comparison_data.append({
            'Indicator': 'Moving Average',
            'Chart View (Trend)': sma_chart_status,
            'Trading Signal (Action)': f"{'🟢' if 'buy' in str(sma_action_signal).lower() else '🔴' if 'sell' in str(sma_action_signal).lower() else '🟡'} {sma_action_signal}",
            'Meaning': 'Chart shows long-term trend, Signal shows price crossover timing'
        })
        
        # RSI Comparison
        rsi_chart_status = "N/A"
        if not rsi_signals_df.empty and 'RSI' in rsi_signals_df.columns:
            latest_rsi = rsi_signals_df['RSI'].iloc[-1]
            if pd.notna(latest_rsi):
                if latest_rsi > 70:
                    rsi_chart_status = "🔴 Overbought (>70)"
                elif latest_rsi < 30:
                    rsi_chart_status = "🟢 Oversold (<30)"
                else:
                    rsi_chart_status = "🟡 Neutral (30-70)"
        
        rsi_action_signal = signal_analysis.get('rsi_signal', 'N/A')
        comparison_data.append({
            'Indicator': 'RSI',
            'Chart View (Trend)': rsi_chart_status,
            'Trading Signal (Action)': f"{'🟢' if 'buy' in str(rsi_action_signal).lower() else '🔴' if 'sell' in str(rsi_action_signal).lower() else '🟡'} {rsi_action_signal}",
            'Meaning': 'Chart shows overbought/oversold zones, Signal shows momentum shifts'
        })
        
        # Bollinger Bands Comparison
        bb_chart_status = "N/A"
        if not bb_signals_df.empty and 'close_price' in bb_signals_df.columns and 'Upper_Band' in bb_signals_df.columns and 'Lower_Band' in bb_signals_df.columns:
            latest_price = bb_signals_df['close_price'].iloc[-1]
            latest_upper = bb_signals_df['Upper_Band'].iloc[-1]
            latest_lower = bb_signals_df['Lower_Band'].iloc[-1]
            if pd.notna(latest_price) and pd.notna(latest_upper) and pd.notna(latest_lower):
                if latest_price > latest_upper:
                    bb_chart_status = "🔴 Above Upper Band"
                elif latest_price < latest_lower:
                    bb_chart_status = "🟢 Below Lower Band"
                else:
                    bb_chart_status = "🟡 Within Bands"
        
        bb_action_signal = signal_analysis.get('bb_signal', 'N/A')
        comparison_data.append({
            'Indicator': 'Bollinger Bands',
            'Chart View (Trend)': bb_chart_status,
            'Trading Signal (Action)': f"{'🟢' if 'buy' in str(bb_action_signal).lower() else '🔴' if 'sell' in str(bb_action_signal).lower() else '🟡'} {bb_action_signal}",
            'Meaning': 'Chart shows price position, Signal shows band bounce opportunities'
        })
        
        # Fibonacci Comparison
        fib_chart_status = "N/A"
        if not fibonacci_df.empty and 'fib_position' in fibonacci_df.columns:
            fib_position = fibonacci_df['fib_position'].iloc[-1]
            if pd.notna(fib_position):
                fib_chart_status = f"📊 {fib_position}"
        
        fib_action_signal = signal_analysis.get('fib_signal', 'N/A')
        comparison_data.append({
            'Indicator': 'Fibonacci',
            'Chart View (Trend)': fib_chart_status,
            'Trading Signal (Action)': f"{'🟢' if 'buy' in str(fib_action_signal).lower() else '🔴' if 'sell' in str(fib_action_signal).lower() else '🟡'} {fib_action_signal}",
            'Meaning': 'Chart shows price at key retracement levels, Signal shows reversal zones'
        })
        
        # Stochastic Comparison
        stoch_chart_status = "N/A"
        if not stochastic_df.empty and 'stoch_status' in stochastic_df.columns:
            stoch_status = stochastic_df['stoch_status'].iloc[-1]
            if pd.notna(stoch_status):
                if 'Overbought' in str(stoch_status):
                    stoch_chart_status = "🔴 Overbought"
                elif 'Oversold' in str(stoch_status):
                    stoch_chart_status = "🟢 Oversold"
                else:
                    stoch_chart_status = "🟡 Neutral"
        
        stoch_action_signal = signal_analysis.get('stoch_signal', 'N/A')
        comparison_data.append({
            'Indicator': 'Stochastic',
            'Chart View (Trend)': stoch_chart_status,
            'Trading Signal (Action)': f"{'🟢' if 'buy' in str(stoch_action_signal).lower() else '🔴' if 'sell' in str(stoch_action_signal).lower() else '🟡'} {stoch_action_signal}",
            'Meaning': 'Chart shows momentum zones, Signal shows %K/%D crossovers'
        })
        
        # Support/Resistance Comparison
        sr_chart_status = "N/A"
        if not support_resistance_df.empty and 'pivot_status' in support_resistance_df.columns:
            pivot_status = support_resistance_df['pivot_status'].iloc[-1]
            if pd.notna(pivot_status):
                sr_chart_status = f"📍 {pivot_status}"
        
        sr_action_signal = signal_analysis.get('sr_signal', 'N/A')
        comparison_data.append({
            'Indicator': 'Support/Resistance',
            'Chart View (Trend)': sr_chart_status,
            'Trading Signal (Action)': f"{'🟢' if 'buy' in str(sr_action_signal).lower() else '🔴' if 'sell' in str(sr_action_signal).lower() else '🟡'} {sr_action_signal}",
            'Meaning': 'Chart shows price at key levels, Signal shows bounce/breakout opportunities'
        })
        
        # Candlestick Pattern Comparison
        pattern_chart_status = "N/A"
        if not candlestick_patterns_df.empty and 'patterns_detected' in candlestick_patterns_df.columns:
            patterns = candlestick_patterns_df['patterns_detected'].iloc[-1]
            if pd.notna(patterns) and str(patterns) != 'None':
                pattern_chart_status = f"🕯️ {patterns}"
        
        pattern_action_signal = signal_analysis.get('pattern_signal', 'N/A')
        comparison_data.append({
            'Indicator': 'Candlestick Patterns',
            'Chart View (Trend)': pattern_chart_status,
            'Trading Signal (Action)': f"{'🟢' if 'buy' in str(pattern_action_signal).lower() or 'bullish' in str(pattern_action_signal).lower() else '🔴' if 'sell' in str(pattern_action_signal).lower() or 'bearish' in str(pattern_action_signal).lower() else '🟡'} {pattern_action_signal}",
            'Meaning': 'Chart shows pattern formation, Signal shows pattern interpretation'
        })
        
        # Display comparison table
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        
        st.info("💡 **Key Insight**: Chart View = Where we are, Trading Signal = What action to take")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 📊 Signal Consensus")
            
            buy_signals = 0
            sell_signals = 0
            neutral_signals = 0
            
            # Categorize signals by type
            bullish_indicators = []
            bearish_indicators = []
            neutral_indicators = []
            
            # Map indicator keys to display names
            indicator_names = {
                'bb_signal': 'Bollinger Bands',
                'macd_signal': 'MACD',
                'rsi_signal': 'RSI',
                'sma_signal': 'SMA Crossover',
                'fib_signal': 'Fibonacci',
                'stoch_signal': 'Stochastic',
                'sr_signal': 'Support/Resistance',
                'pattern_signal': 'Candlestick Patterns'
            }
            
            for indicator, signal in signal_analysis.items():
                indicator_display = indicator_names.get(indicator, indicator.replace('_', ' ').title())
                
                if signal and isinstance(signal, str):
                    signal_lower = signal.lower()
                    if 'buy' in signal_lower or 'bullish' in signal_lower:
                        buy_signals += 1
                        bullish_indicators.append(f"✓ {indicator_display}: {signal}")
                    elif 'sell' in signal_lower or 'bearish' in signal_lower:
                        sell_signals += 1
                        bearish_indicators.append(f"✓ {indicator_display}: {signal}")
                    else:
                        neutral_signals += 1
                        neutral_indicators.append(f"• {indicator_display}: {signal}")
            
            total_signals = buy_signals + sell_signals + neutral_signals
            
            if total_signals > 0:
                buy_pct = (buy_signals / total_signals) * 100
                sell_pct = (sell_signals / total_signals) * 100
                
                st.metric("🟢 Bullish Signals", f"{buy_signals}/{total_signals}", f"{buy_pct:.1f}%")
                st.metric("🔴 Bearish Signals", f"{sell_signals}/{total_signals}", f"{sell_pct:.1f}%")
                st.metric("🟡 Neutral Signals", f"{neutral_signals}/{total_signals}")
                
                # Show detailed breakdown
                st.markdown("---")
                st.markdown("#### 📋 Signal Details")
                
                if bullish_indicators:
                    st.markdown("**🟢 Bullish Indicators:**")
                    for indicator in bullish_indicators:
                        st.markdown(f"- {indicator}")
                
                if bearish_indicators:
                    st.markdown("**🔴 Bearish Indicators:**")
                    for indicator in bearish_indicators:
                        st.markdown(f"- {indicator}")
                
                if neutral_indicators:
                    st.markdown("**🟡 Neutral Indicators:**")
                    for indicator in neutral_indicators:
                        st.markdown(f"- {indicator}")

        with col2:
            st.markdown("### 🎯 Trading Recommendation")
            
            # Enhanced thresholds for 9 indicators (up from 4)
            if buy_signals > sell_signals and buy_signals >= 3:
                recommendation = "🟢 **STRONG BULLISH BIAS** - Consider Long Positions"
                confidence = "Very High" if buy_signals >= 5 else "High" if buy_signals >= 4 else "Medium"
                action = "Look for buying opportunities on dips with multiple confirmations"
            elif sell_signals > buy_signals and sell_signals >= 3:
                recommendation = "🔴 **STRONG BEARISH BIAS** - Consider Short Positions"
                confidence = "Very High" if sell_signals >= 5 else "High" if sell_signals >= 4 else "Medium"
                action = "Look for selling opportunities on rallies with multiple confirmations"
            elif buy_signals > sell_signals:
                recommendation = "🟢 **MILD BULLISH BIAS** - Cautiously Bullish"
                confidence = "Medium"
                action = "Wait for additional confirmation before entering long positions"
            elif sell_signals > buy_signals:
                recommendation = "🔴 **MILD BEARISH BIAS** - Cautiously Bearish"
                confidence = "Medium"
                action = "Wait for additional confirmation before entering short positions"
            else:
                recommendation = "🟡 **MIXED SIGNALS** - Stay Neutral"
                confidence = "Low"
                action = "Wait for clearer signals before entering any positions"
            
            st.markdown(recommendation)
            st.markdown(f"**Confidence Level:** {confidence}")
            st.markdown(f"**Suggested Action:** {action}")
            
            # Add signal strength bar
            st.markdown("---")
            st.markdown("#### Signal Strength Distribution")
            signal_strength_data = {
                'Type': ['Bullish', 'Bearish', 'Neutral'],
                'Count': [buy_signals, sell_signals, neutral_signals]
            }
            import plotly.express as px
            fig_strength = px.bar(signal_strength_data, x='Type', y='Count', 
                                 color='Type',
                                 color_discrete_map={'Bullish': 'green', 'Bearish': 'red', 'Neutral': 'gray'},
                                 title=f'Signal Distribution ({total_signals} total indicators)')
            fig_strength.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig_strength, use_container_width=True)

        # Add risk management reminder
        st.markdown("### ⚠️ Risk Management Checklist")
        risk_checklist = st.columns(3)

        with risk_checklist[0]:
            st.markdown("""
            **📏 Position Sizing:**
            - [ ] Check ATR for volatility
            - [ ] Risk only 1-2% per trade
            - [ ] Reduce size in high volatility
            """)

        with risk_checklist[1]:
            st.markdown("""
            **🛑 Stop Loss:**
            - [ ] Set stop at 2x ATR
            - [ ] Never risk more than planned
            - [ ] Move stops to break-even when possible
            """)

        with risk_checklist[2]:
            st.markdown("""
            **🎯 Profit Taking:**
            - [ ] Take partial profits at 1:1 R/R
            - [ ] Scale out at resistance levels
            - [ ] Let winners run with trailing stops
            """)

        st.markdown("---")
        st.markdown("### 💡 Remember: No single indicator is perfect. Always use multiple confirmations and proper risk management!")

        # Add disclaimer
        st.markdown("""
        ---
        **⚠️ Disclaimer:** This analysis is for educational purposes only. Always do your own research and consider consulting with a financial advisor before making investment decisions. Past performance does not guarantee future results.
        """)


def show_ml_prediction_page():
    """Show the ML-based price prediction page with enhanced models"""
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error, classification_report, confusion_matrix
    from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
    import warnings
    warnings.filterwarnings('ignore')
    
    # Advanced ML models availability check
    ADVANCED_MODELS_AVAILABLE = {}
    
    try:
        import xgboost as xgb
        ADVANCED_MODELS_AVAILABLE['XGBoost'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['XGBoost'] = False
    
    try:
        import lightgbm as lgb
        ADVANCED_MODELS_AVAILABLE['LightGBM'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['LightGBM'] = False
    
    try:
        from prophet import Prophet
        ADVANCED_MODELS_AVAILABLE['Prophet'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['Prophet'] = False
    
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.optimizers import Adam
        ADVANCED_MODELS_AVAILABLE['LSTM'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['LSTM'] = False
    
    try:
        from statsmodels.tsa.arima.model import ARIMA
        ADVANCED_MODELS_AVAILABLE['ARIMA'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['ARIMA'] = False
    
    # Advanced ML models availability check
    ADVANCED_MODELS_AVAILABLE = {}
    
    try:
        import xgboost as xgb
        ADVANCED_MODELS_AVAILABLE['XGBoost'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['XGBoost'] = False
    
    try:
        import lightgbm as lgb
        ADVANCED_MODELS_AVAILABLE['LightGBM'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['LightGBM'] = False
    
    try:
        from prophet import Prophet
        ADVANCED_MODELS_AVAILABLE['Prophet'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['Prophet'] = False
    
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.optimizers import Adam
        ADVANCED_MODELS_AVAILABLE['LSTM'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['LSTM'] = False
    
    try:
        from statsmodels.tsa.arima.model import ARIMA
        ADVANCED_MODELS_AVAILABLE['ARIMA'] = True
    except ImportError:
        ADVANCED_MODELS_AVAILABLE['ARIMA'] = False
    
    # Check if we have data from home page
    if 'selected_ticker' not in st.session_state or st.session_state.selected_ticker is None:
        st.warning("🏠 **Please select a market and stock from the Home page first!**")
        st.info("👈 Use the Home & Filters page in the sidebar to select your market, stock, and date range.")
        return
    
    # Get data from session state
    selected_ticker = st.session_state.selected_ticker
    index_option = st.session_state.index_option
    
    st.markdown(f"""
    # 🤖 AI Price Prediction & Forecasting
    
    ### Advanced machine learning models to predict future price movements for smart trading decisions
    
    **Market:** {index_option} | **Stock:** {selected_ticker}
    
    ---
    """)
    
    # Display available advanced models
    st.sidebar.markdown("### 🔬 Advanced Models Status")
    for model, available in ADVANCED_MODELS_AVAILABLE.items():
        status = "✅" if available else "❌"
        st.sidebar.text(f"{status} {model}")
    
    if not any(ADVANCED_MODELS_AVAILABLE.values()):
        st.sidebar.warning("Install advanced packages: pip install xgboost lightgbm prophet tensorflow statsmodels")
    
    # Load and prepare data for ML
    with st.spinner("Loading data for ML analysis..."):
        price_df = load_price_data(index_option, selected_ticker)
        
        if price_df is None or price_df.empty:
            st.error(f"❌ No price data available for **{selected_ticker}** in **{index_option}** market.")
            if index_option == "Forex":
                available_symbols = ["AUDUSD", "EURCHF", "EURJPY", "EURUSD", "GBPUSD"]
                st.info(f"📊 **Available Forex symbols:** {', '.join(available_symbols)}")
                st.info("💡 **Tip:** Go back to Home page and select one of the available symbols.")
            return
        
        # Calculate volume indicators for features
        ml_df = calculate_volume_indicators(price_df.copy())
        
        # Load additional indicators
        rsi_df = load_rsi(index_option, selected_ticker)
        macd_df = load_macd(index_option, selected_ticker)
        atr_df = load_atr(index_option, selected_ticker)
        
        # Load new advanced indicators for ML features
        fibonacci_df = load_fibonacci(index_option, selected_ticker)
        stochastic_df = load_stochastic(index_option, selected_ticker)
        support_resistance_df = load_support_resistance(index_option, selected_ticker)
        candlestick_patterns_df = load_candlestick_patterns(index_option, selected_ticker)
        
        # Merge all indicators
        if not rsi_df.empty:
            ml_df = ml_df.merge(rsi_df[['trading_date', 'RSI']], on='trading_date', how='left')
        if not macd_df.empty:
            ml_df = ml_df.merge(macd_df[['trading_date', 'MACD', 'Signal_Line']], on='trading_date', how='left')
        if not atr_df.empty:
            ml_df = ml_df.merge(atr_df[['trading_date', 'ATR_14']], on='trading_date', how='left')
        
        # Merge new advanced indicators
        if not fibonacci_df.empty:
            # Add key Fibonacci levels as features
            fib_cols = ['trading_date', 'fib_20d_0382', 'fib_20d_0500', 'fib_20d_0618', 'fib_50d_0618']
            ml_df = ml_df.merge(fibonacci_df[fib_cols], on='trading_date', how='left')
        
        if not stochastic_df.empty:
            # Add Stochastic %K and %D for 14-day period
            stoch_cols = ['trading_date', 'stoch_14d_k', 'stoch_14d_d']
            ml_df = ml_df.merge(stochastic_df[stoch_cols], on='trading_date', how='left')
        
        if not support_resistance_df.empty:
            # Add pivot points and key S/R levels
            sr_cols = ['trading_date', 'pivot_point', 'r1', 's1']
            ml_df = ml_df.merge(support_resistance_df[sr_cols], on='trading_date', how='left')
        
        if not candlestick_patterns_df.empty:
            # Add pattern signals as categorical features
            # Create binary flags for key patterns
            patterns_to_add = candlestick_patterns_df[['trading_date']].copy()
            patterns_to_add['has_bullish_pattern'] = (
                candlestick_patterns_df['bullish_engulfing'].notna() | 
                candlestick_patterns_df['morning_star'].notna() |
                candlestick_patterns_df['hammer'].notna() |
                candlestick_patterns_df['inverse_head_shoulders'].notna()
            ).astype(int)
            patterns_to_add['has_bearish_pattern'] = (
                candlestick_patterns_df['bearish_engulfing'].notna() |
                candlestick_patterns_df['evening_star'].notna() |
                candlestick_patterns_df['shooting_star'].notna() |
                candlestick_patterns_df['head_and_shoulders'].notna()
            ).astype(int)
            ml_df = ml_df.merge(patterns_to_add, on='trading_date', how='left')
            # Fill NaN with 0 for pattern flags
            ml_df['has_bullish_pattern'] = ml_df['has_bullish_pattern'].fillna(0)
            ml_df['has_bearish_pattern'] = ml_df['has_bearish_pattern'].fillna(0)
            ml_df = ml_df.merge(atr_df[['trading_date', 'ATR_14']], on='trading_date', how='left')
      # ML Configuration
    st.markdown("## ⚙️ Enhanced ML Model Configuration")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        prediction_days = st.selectbox("Prediction Horizon", [1, 3, 5, 7, 14, 30], index=2, key="pred_days")
    
    with col2:
        # Build model list based on availability
        base_models = ["Random Forest", "Linear Regression", "Gradient Boosting"]
        available_models = base_models.copy()
        
        if ADVANCED_MODELS_AVAILABLE.get('XGBoost', False):
            available_models.append("XGBoost")
        if ADVANCED_MODELS_AVAILABLE.get('LightGBM', False):
            available_models.append("LightGBM")
        if ADVANCED_MODELS_AVAILABLE.get('LSTM', False):
            available_models.append("LSTM Neural Network")
        if ADVANCED_MODELS_AVAILABLE.get('Prophet', False):
            available_models.append("Prophet (Time Series)")
        
        available_models.extend(["Ensemble (All Available)", "Classification (Buy/Sell/Hold)"])
        
        model_type = st.selectbox("ML Model", available_models, index=0, key="model_type")
    
    with col3:
        feature_set = st.selectbox("Feature Set", ["Technical Only", "Volume + Technical", "All Features"], index=2, key="features")
    
    with col4:
        # Advanced options
        use_time_series_cv = st.checkbox("Time Series CV", value=True, help="Use time series cross-validation")
        optimize_hyperparams = st.checkbox("Hyperparameter Optimization", value=False, help="Optimize model parameters (slower)")
    
    # Show feature engineering options
    with st.expander("🔧 Advanced Feature Engineering Options", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Additional Technical Features:**")
            add_lagged_features = st.checkbox("Lagged Price Features", value=True, help="Add previous N-day prices")
            add_volatility_regime = st.checkbox("Volatility Regime Classification", value=True, help="High/Medium/Low volatility periods")
            add_trend_strength = st.checkbox("Trend Strength Indicator", value=True, help="Measure of trend strength")
        
        with col2:
            st.markdown("**Market Features:**")
            add_market_cap_features = st.checkbox("Market Cap Relative Features", value=False, help="Relative to market performance")
            add_sector_features = st.checkbox("Sector Momentum", value=False, help="Sector-based features")
            add_seasonality = st.checkbox("Seasonal Features", value=True, help="Day of week, month effects")
      # Enhanced feature preparation with advanced options
    def prepare_ml_features(df, feature_set):
        """Prepare comprehensive feature matrix for ML models with advanced engineering"""
        df = df.copy()
        
        # Sort by date
        df = df.sort_values('trading_date').reset_index(drop=True)
        
        # Basic technical features
        df['price_change'] = df['close_price'].pct_change()
        df['price_sma_5'] = df['close_price'].rolling(5).mean()
        df['price_sma_10'] = df['close_price'].rolling(10).mean() 
        df['price_sma_20'] = df['close_price'].rolling(20).mean()
        df['volatility_5'] = df['close_price'].rolling(5).std()
        df['volatility_20'] = df['close_price'].rolling(20).std()
        
        # Price position relative to moving averages
        df['price_vs_sma5'] = df['close_price'] / df['price_sma_5'] - 1
        df['price_vs_sma20'] = df['close_price'] / df['price_sma_20'] - 1
        
        # Price momentum features
        df['momentum_3'] = df['close_price'] / df['close_price'].shift(3) - 1
        df['momentum_7'] = df['close_price'] / df['close_price'].shift(7) - 1
        
        # Advanced feature engineering based on user selections
        if 'add_lagged_features' in locals() and add_lagged_features:
            # Add lagged price features
            for lag in [1, 2, 3, 5, 10]:
                df[f'price_lag_{lag}'] = df['close_price'].shift(lag)
                df[f'return_lag_{lag}'] = df['close_price'].pct_change(lag)
        
        if 'add_volatility_regime' in locals() and add_volatility_regime:
            # Volatility regime classification
            vol_20 = df['close_price'].rolling(20).std()
            vol_percentiles = vol_20.quantile([0.33, 0.67])
            df['volatility_regime'] = 0  # Low
            df.loc[vol_20 > vol_percentiles.iloc[0], 'volatility_regime'] = 1  # Medium
            df.loc[vol_20 > vol_percentiles.iloc[1], 'volatility_regime'] = 2  # High
        
        if 'add_trend_strength' in locals() and add_trend_strength:
            # Trend strength indicator
            df['trend_strength'] = abs(df['close_price'].rolling(10).apply(
                lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == 10 else 0, raw=False
            ))
        
        if 'add_seasonality' in locals() and add_seasonality:
            # Add seasonal features
            df['day_of_week'] = df['trading_date'].dt.dayofweek
            df['month'] = df['trading_date'].dt.month
            df['quarter'] = df['trading_date'].dt.quarter
        
        # Calculate additional technical indicators
        # Bollinger Band position
        if 'close_price' in df.columns:
            bb_period = 20
            bb_std = 2
            df['bb_middle'] = df['close_price'].rolling(bb_period).mean()
            df['bb_std'] = df['close_price'].rolling(bb_period).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * df['bb_std'])
            df['bb_lower'] = df['bb_middle'] - (bb_std * df['bb_std'])
            df['bb_position'] = (df['close_price'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # Rate of change features
        df['roc_5'] = df['close_price'].pct_change(5)
        df['roc_10'] = df['close_price'].pct_change(10)
        df['roc_20'] = df['close_price'].pct_change(20)
        
        # Select features based on feature_set
        base_features = [
            'close_price', 'price_change', 'volatility_5', 'volatility_20', 
            'price_vs_sma5', 'price_vs_sma20', 'momentum_3', 'momentum_7',
            'bb_position', 'bb_width', 'roc_5', 'roc_10', 'roc_20'
        ]
        
        # Add advanced features if selected
        if 'add_lagged_features' in locals() and add_lagged_features:
            base_features.extend([f'price_lag_{lag}' for lag in [1, 2, 3, 5, 10]])
            base_features.extend([f'return_lag_{lag}' for lag in [1, 2, 3, 5, 10]])
        
        if 'add_volatility_regime' in locals() and add_volatility_regime:
            base_features.append('volatility_regime')
        
        if 'add_trend_strength' in locals() and add_trend_strength:
            base_features.append('trend_strength')
        
        if 'add_seasonality' in locals() and add_seasonality:
            base_features.extend(['day_of_week', 'month', 'quarter'])
        
        if feature_set in ["Volume + Technical", "All Features"]:
            volume_features = ['volume', 'volume_ma_20', 'relative_volume', 'vwap', 'obv_raw', 'mfi']
            base_features.extend([f for f in volume_features if f in df.columns])
        
        if feature_set == "All Features":
            extra_features = ['RSI', 'MACD', 'Signal_Line', 'ATR_14']
            base_features.extend([f for f in extra_features if f in df.columns])
            
            # Add new advanced indicator features
            advanced_indicator_features = [
                # Fibonacci levels
                'fib_20d_0382', 'fib_20d_0500', 'fib_20d_0618', 'fib_50d_0618',
                # Stochastic oscillator
                'stoch_14d_k', 'stoch_14d_d',
                # Support & Resistance
                'pivot_point', 'r1', 's1',
                # Candlestick patterns
                'has_bullish_pattern', 'has_bearish_pattern'
            ]
            base_features.extend([f for f in advanced_indicator_features if f in df.columns])
        
        # Create feature matrix
        available_features = [f for f in base_features if f in df.columns]
        feature_df = df[['trading_date'] + available_features].copy()
        
        # Forward fill missing values
        feature_df = feature_df.fillna(method='ffill').fillna(method='bfill')
        
        # Remove any remaining infinite values that might result from zero volume calculations
        feature_df = feature_df.replace([np.inf, -np.inf], np.nan)
        
        # Drop rows with any remaining NaN values after processing
        initial_rows = len(feature_df)
        feature_df = feature_df.dropna()
        
        if len(feature_df) < initial_rows:
            st.info(f"ℹ️ Removed {initial_rows - len(feature_df)} rows with invalid values (typically from zero volume calculations)")
        
        return feature_df, available_features
    
    # Prepare data
    try:
        feature_df, feature_names = prepare_ml_features(ml_df, feature_set)
        
        if len(feature_df) < 50:
            st.error("Insufficient data for ML training. Need at least 50 data points.")
            return
        
        st.success(f"✅ Prepared {len(feature_df)} data points with {len(feature_names)} features")
        
    except Exception as e:
        st.error(f"Error preparing features: {str(e)}")
        return
    
    # Create target variable (future price change)
    def create_target(df, days_ahead):
        """Create target variable for prediction"""
        df = df.copy()
        df['target'] = df['close_price'].shift(-days_ahead) / df['close_price'] - 1
        return df.dropna()
    
    target_df = create_target(feature_df, prediction_days)
    
    # Validate we have sufficient data after target creation
    if len(target_df) < 50:
        st.error(f"❌ Insufficient data for ML training after target creation. Need at least 50 data points, but only have {len(target_df)} points.")
        if index_option == "Forex":
            available_symbols = ["AUDUSD", "EURCHF", "EURJPY", "EURUSD", "GBPUSD"]
            st.info(f"📊 **Available Forex symbols:** {', '.join(available_symbols)}")
            st.info("💡 **Tip:** Go back to Home page and select one of the available symbols.")
        return
    
    # Split data for training and testing
    train_size = int(len(target_df) * 0.8)
    train_df = target_df.iloc[:train_size]
    test_df = target_df.iloc[train_size:]
    
    # Prepare X and y
    X_train = train_df[feature_names].values
    y_train = train_df['target'].values
    X_test = test_df[feature_names].values 
    y_test = test_df['target'].values
    
    # Additional validation before scaling
    if len(X_train) == 0 or len(X_test) == 0:
        st.error(f"❌ No training or test data available. Training samples: {len(X_train)}, Test samples: {len(X_test)}")
        if index_option == "Forex":
            available_symbols = ["AUDUSD", "EURCHF", "EURJPY", "EURUSD", "GBPUSD"]
            st.info(f"📊 **Available Forex symbols:** {', '.join(available_symbols)}")
            st.info("💡 **Tip:** Go back to Home page and select one of the available symbols.")
        return
    
    # Enhanced model training with advanced algorithms
    st.markdown("## 🧠 Advanced Model Training & Predictions")
    
    # Create different scalers for different model types
    standard_scaler = StandardScaler()
    minmax_scaler = MinMaxScaler()
    
    X_train_standard = standard_scaler.fit_transform(X_train)
    X_test_standard = standard_scaler.transform(X_test)
    X_train_minmax = minmax_scaler.fit_transform(X_train)
    X_test_minmax = minmax_scaler.transform(X_test)
    
    # Model training with progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    models = {}
    predictions = {}
    model_info = {}
    
    def train_model_with_progress(model_name, model_func, progress_value):
        """Train a model with progress updates"""
        status_text.text(f"Training {model_name}...")
        progress_bar.progress(progress_value)
        try:
            model, pred, info = model_func()
            models[model_name] = model
            predictions[model_name] = pred
            model_info[model_name] = info
            return True
        except Exception as e:
            st.warning(f"Failed to train {model_name}: {str(e)}")
            return False
    
    total_models = 0
    completed_models = 0
    
    # Count total models to train
    if model_type in ["Random Forest", "Ensemble (All Available)"]:
        total_models += 1
    if model_type in ["Linear Regression", "Ensemble (All Available)"]:
        total_models += 1
    if model_type in ["Gradient Boosting", "Ensemble (All Available)"]:
        total_models += 1
    if model_type in ["XGBoost", "Ensemble (All Available)"] and ADVANCED_MODELS_AVAILABLE.get('XGBoost', False):
        total_models += 1
    if model_type in ["LightGBM", "Ensemble (All Available)"] and ADVANCED_MODELS_AVAILABLE.get('LightGBM', False):
        total_models += 1
    if model_type in ["LSTM Neural Network", "Ensemble (All Available)"] and ADVANCED_MODELS_AVAILABLE.get('LSTM', False):
        total_models += 1
    if model_type in ["Prophet (Time Series)", "Ensemble (All Available)"] and ADVANCED_MODELS_AVAILABLE.get('Prophet', False):
        total_models += 1
    if model_type == "Classification (Buy/Sell/Hold)":
        total_models += 2  # We'll train multiple classification models
    
    if total_models == 0:
        total_models = 1  # Prevent division by zero
    
    # Random Forest
    if model_type in ["Random Forest", "Ensemble (All Available)"]:
        def train_rf():
            if optimize_hyperparams:
                rf_param_grid = {
                    'n_estimators': [50, 100, 200],
                    'max_depth': [5, 10, 15, None],
                    'min_samples_split': [2, 5, 10],
                    'min_samples_leaf': [1, 2, 4]
                }
                rf_model = RandomForestRegressor(random_state=42)
                rf_grid = GridSearchCV(rf_model, rf_param_grid, cv=3, scoring='neg_mean_squared_error', n_jobs=-1)
                rf_grid.fit(X_train_standard, y_train)
                model = rf_grid.best_estimator_
                info = {"best_params": rf_grid.best_params_, "cv_score": rf_grid.best_score_}
            else:
                model = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10, n_jobs=-1)
                model.fit(X_train_standard, y_train)
                info = {"n_estimators": 100, "max_depth": 10}
            
            pred = model.predict(X_test_standard)
            return model, pred, info
        
        if train_model_with_progress("Random Forest", train_rf, (completed_models + 1) / total_models):
            completed_models += 1
    
    # Linear Regression
    if model_type in ["Linear Regression", "Ensemble (All Available)"]:
        def train_lr():
            model = LinearRegression()
            model.fit(X_train_standard, y_train)
            pred = model.predict(X_test_standard)
            info = {"intercept": model.intercept_, "n_features": len(model.coef_)}
            return model, pred, info
        
        if train_model_with_progress("Linear Regression", train_lr, (completed_models + 1) / total_models):
            completed_models += 1
    
    # Gradient Boosting
    if model_type in ["Gradient Boosting", "Ensemble (All Available)"]:
        def train_gb():
            if optimize_hyperparams:
                gb_param_grid = {
                    'n_estimators': [50, 100, 200],
                    'learning_rate': [0.05, 0.1, 0.2],
                    'max_depth': [3, 5, 7]
                }
                gb_model = GradientBoostingRegressor(random_state=42)
                gb_grid = GridSearchCV(gb_model, gb_param_grid, cv=3, scoring='neg_mean_squared_error', n_jobs=-1)
                gb_grid.fit(X_train_standard, y_train)
                model = gb_grid.best_estimator_
                info = {"best_params": gb_grid.best_params_, "cv_score": gb_grid.best_score_}
            else:
                model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
                model.fit(X_train_standard, y_train)
                info = {"n_estimators": 100, "learning_rate": 0.1, "max_depth": 5}
            
            pred = model.predict(X_test_standard)
            return model, pred, info
        
        if train_model_with_progress("Gradient Boosting", train_gb, (completed_models + 1) / total_models):
            completed_models += 1
    
    # XGBoost
    if model_type in ["XGBoost", "Ensemble (All Available)"] and ADVANCED_MODELS_AVAILABLE.get('XGBoost', False):
        def train_xgb():
            import xgboost as xgb
            if optimize_hyperparams:
                xgb_param_grid = {
                    'n_estimators': [50, 100, 200],
                    'learning_rate': [0.05, 0.1, 0.2],
                    'max_depth': [3, 5, 7],
                    'subsample': [0.8, 0.9, 1.0]
                }
                xgb_model = xgb.XGBRegressor(random_state=42, eval_metric='rmse')
                xgb_grid = GridSearchCV(xgb_model, xgb_param_grid, cv=3, scoring='neg_mean_squared_error', n_jobs=-1)
                xgb_grid.fit(X_train_standard, y_train)
                model = xgb_grid.best_estimator_
                info = {"best_params": xgb_grid.best_params_, "cv_score": xgb_grid.best_score_}
            else:
                model = xgb.XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42, eval_metric='rmse')
                model.fit(X_train_standard, y_train)
                info = {"n_estimators": 100, "learning_rate": 0.1, "max_depth": 5}
            
            pred = model.predict(X_test_standard)
            return model, pred, info
        
        if train_model_with_progress("XGBoost", train_xgb, (completed_models + 1) / total_models):
            completed_models += 1
    
    # LightGBM
    if model_type in ["LightGBM", "Ensemble (All Available)"] and ADVANCED_MODELS_AVAILABLE.get('LightGBM', False):
        def train_lgb():
            import lightgbm as lgb
            if optimize_hyperparams:
                lgb_param_grid = {
                    'n_estimators': [50, 100, 200],
                    'learning_rate': [0.05, 0.1, 0.2],
                    'max_depth': [3, 5, 7, -1],
                    'num_leaves': [31, 50, 100]
                }
                lgb_model = lgb.LGBMRegressor(random_state=42, verbose=-1)
                lgb_grid = GridSearchCV(lgb_model, lgb_param_grid, cv=3, scoring='neg_mean_squared_error', n_jobs=-1)
                lgb_grid.fit(X_train_standard, y_train)
                model = lgb_grid.best_estimator_
                info = {"best_params": lgb_grid.best_params_, "cv_score": lgb_grid.best_score_}
            else:
                model = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42, verbose=-1)
                model.fit(X_train_standard, y_train)
                info = {"n_estimators": 100, "learning_rate": 0.1, "max_depth": 5}
            
            pred = model.predict(X_test_standard)
            return model, pred, info
        
        if train_model_with_progress("LightGBM", train_lgb, (completed_models + 1) / total_models):
            completed_models += 1
    
    # LSTM Neural Network
    if model_type in ["LSTM Neural Network", "Ensemble (All Available)"] and ADVANCED_MODELS_AVAILABLE.get('LSTM', False):
        def train_lstm():
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout
            from tensorflow.keras.optimizers import Adam
            import tensorflow as tf
            
            # Suppress TensorFlow warnings
            tf.get_logger().setLevel('ERROR')
            
            # Prepare data for LSTM (reshape for sequence)
            sequence_length = min(10, len(X_train_minmax) // 4)  # Use 10 time steps or quarter of data
            
            def create_sequences(X, y, seq_length):
                X_seq, y_seq = [], []
                for i in range(seq_length, len(X)):
                    X_seq.append(X[i-seq_length:i])
                    y_seq.append(y[i])
                return np.array(X_seq), np.array(y_seq)
            
            X_train_seq, y_train_seq = create_sequences(X_train_minmax, y_train, sequence_length)
            X_test_seq, y_test_seq = create_sequences(X_test_minmax, y_test, sequence_length)
            
            # Build LSTM model
            model = Sequential([
                LSTM(50, return_sequences=True, input_shape=(sequence_length, X_train_minmax.shape[1])),
                Dropout(0.2),
                LSTM(50, return_sequences=False),
                Dropout(0.2),
                Dense(25),
                Dense(1)
            ])
            
            model.compile(optimizer=Adam(learning_rate=0.001), loss='mse')
            
            # Train with minimal epochs for demo
            model.fit(X_train_seq, y_train_seq, epochs=20, batch_size=32, verbose=0, validation_split=0.2)
            
            # Make predictions
            pred_seq = model.predict(X_test_seq, verbose=0)
            
            # Pad predictions to match original test set length
            pred = np.full(len(y_test), np.nan)
            pred[sequence_length:] = pred_seq.flatten()
            pred[:sequence_length] = pred_seq[0]  # Fill initial values with first prediction
            
            info = {"sequence_length": sequence_length, "epochs": 20, "architecture": "LSTM-50-50-25-1"}
            return model, pred, info
        
        if train_model_with_progress("LSTM Neural Network", train_lstm, (completed_models + 1) / total_models):
            completed_models += 1
    
    # Prophet Time Series Model
    if model_type in ["Prophet (Time Series)", "Ensemble (All Available)"] and ADVANCED_MODELS_AVAILABLE.get('Prophet', False):
        def train_prophet():
            from prophet import Prophet
            
            # Prepare Prophet data format
            prophet_df = pd.DataFrame({
                'ds': target_df['trading_date'],
                'y': target_df['target']
            })
            
            train_prophet_df = prophet_df.iloc[:train_size]
            test_prophet_df = prophet_df.iloc[train_size:]
            
            # Create and train Prophet model
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=0.05
            )
              # Add additional regressors if available
            if 'volatility_20' in feature_df.columns:
                model.add_regressor('volatility_20')
                train_prophet_df['volatility_20'] = target_df['volatility_20'].iloc[:train_size]
                test_prophet_df['volatility_20'] = target_df['volatility_20'].iloc[train_size:]
            
            model.fit(train_prophet_df)
            
            # Make predictions
            forecast = model.predict(test_prophet_df)
            pred = forecast['yhat'].values
            
            info = {
                "seasonality": "yearly+weekly",
                "changepoint_prior_scale": 0.05,
                "n_changepoints": len(model.changepoints)
            }
            
            return model, pred, info
        
        if train_model_with_progress("Prophet (Time Series)", train_prophet, (completed_models + 1) / total_models):
            completed_models += 1
    
    # Classification Models (Buy/Sell/Hold)
    if model_type == "Classification (Buy/Sell/Hold)":
        # Create classification labels: BUY (>2%), SELL (<-2%), HOLD (between)
        y_train_class = np.where(y_train > 0.02, 1, np.where(y_train < -0.02, -1, 0))  # 1=BUY, -1=SELL, 0=HOLD
        y_test_class = np.where(y_test > 0.02, 1, np.where(y_test < -0.02, -1, 0))
        
        # Random Forest Classifier
        def train_rf_class():
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10, n_jobs=-1)
            model.fit(X_train_standard, y_train_class)
            pred_class = model.predict(X_test_standard)
            
            # Convert predictions back to return estimates
            pred = np.where(pred_class == 1, 0.03, np.where(pred_class == -1, -0.03, 0.0))
            
            info = {
                "n_estimators": 100,
                "max_depth": 10,
                "classification_report": classification_report(y_test_class, pred_class, zero_division=0)
            }
            return model, pred, info
        
        if train_model_with_progress("RF Classifier", train_rf_class, (completed_models + 1) / total_models):
            completed_models += 1
        
        # Gradient Boosting Classifier
        def train_gb_class():
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
            model.fit(X_train_standard, y_train_class)
            pred_class = model.predict(X_test_standard)
            
            # Convert predictions back to return estimates
            pred = np.where(pred_class == 1, 0.03, np.where(pred_class == -1, -0.03, 0.0))
            
            info = {
                "n_estimators": 100,
                "learning_rate": 0.1,
                "max_depth": 5,
                "classification_report": classification_report(y_test_class, pred_class, zero_division=0)
            }
            return model, pred, info
        
        if train_model_with_progress("GB Classifier", train_gb_class, (completed_models + 1) / total_models):
            completed_models += 1
    
    # Complete progress
    progress_bar.progress(1.0)
    status_text.text("Training complete!")
    
    # Model performance comparison
    if predictions:
        st.markdown("## 📊 Model Performance Analysis")
        
        # Calculate performance metrics for each model
        metrics_df = []
        for name, pred in predictions.items():
            if pred is not None and len(pred) == len(y_test):
                mae = mean_absolute_error(y_test, pred)
                rmse = np.sqrt(mean_squared_error(y_test, pred))
                
                metrics_df.append({
                    'Model': name,
                    'MAE': mae,
                    'RMSE': rmse,
                    'Score': -rmse  # Negative RMSE for ranking (higher is better)
                })
        
        if metrics_df:
            metrics_df = pd.DataFrame(metrics_df)
            metrics_df = metrics_df.sort_values('Score', ascending=False)
            
            # Display metrics
            st.dataframe(metrics_df, use_container_width=True)
            
            # Best model
            best_model = metrics_df.iloc[0]['Model']
            st.success(f"🏆 Best performing model: **{best_model}**")
        
        else:
            st.warning("No valid predictions to compare.")
    else:
        st.warning("No models available for analysis.")
    
    # Future Prediction
    st.markdown("### 🔮 Future Price Forecast")
      # Get the most recent data point for prediction
    latest_features = feature_df[feature_names].iloc[-1:].values
    latest_features_scaled = standard_scaler.transform(latest_features)
    
    # Make predictions with all models
    future_predictions = {}
    for name, model in models.items():
        pred = model.predict(latest_features_scaled)[0]
        future_predictions[name] = pred
    
    if model_type == "Ensemble" and len(models) > 1:
        ensemble_pred = np.mean(list(future_predictions.values()))
        future_predictions['Ensemble'] = ensemble_pred
    
    # Display predictions
    col1, col2, col3 = st.columns(3)
    
    current_price = feature_df['close_price'].iloc[-1]
    
    with col1:
        st.markdown("#### 📊 Current Price")
        # Use 5 decimal places for Forex, 2 for stocks
        price_format = f"${current_price:.5f}" if index_option == "Forex" else f"${current_price:.2f}"
        st.metric("Current Price", price_format)
        
    with col2:
        st.markdown("#### 🎯 Predicted Change")
        if model_type == "Ensemble" and 'Ensemble' in future_predictions:
            pred_change = future_predictions['Ensemble']
        elif len(future_predictions) > 0:
            pred_change = list(future_predictions.values())[0]
        else:
            # Handle case where no predictions are available
            pred_change = 0.0
            st.warning("No predictions available. Please train a model first.")
        
        direction = "📈" if pred_change > 0 else "📉"
        st.metric(f"{prediction_days}-day Return", f"{direction} {pred_change*100:.2f}%")
        
    with col3:
        st.markdown("#### 💰 Target Price")
        target_price = current_price * (1 + pred_change)
        price_diff = target_price - current_price
        # Use 5 decimal places for Forex, 2 for stocks
        target_format = f"${target_price:.5f}" if index_option == "Forex" else f"${target_price:.2f}"
        # Format difference - remove $ sign to let Streamlit handle the color based on +/- value
        if index_option == "Forex":
            diff_format = f"{price_diff:+.5f}"
        else:
            diff_format = f"{price_diff:+.2f}"
        st.metric("Target Price", target_format, diff_format)
    
    # Prediction confidence and risk assessment
    st.markdown("### ⚠️ Risk Assessment & Confidence")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Model Confidence")
        
        # Calculate prediction variance as confidence indicator
        if len(future_predictions) > 1:
            pred_values = list(future_predictions.values())
            pred_std = np.std(pred_values)
            confidence = max(0, 100 - pred_std * 1000)  # Rough confidence calculation
        else:
            confidence = 75  # Default confidence for single model
        
        confidence_color = "🟢" if confidence > 70 else "🟡" if confidence > 50 else "🔴"
        st.metric("Confidence Level", f"{confidence_color} {confidence:.0f}%")
        
        # Model agreement
        if len(future_predictions) > 1:
            agreements = sum(1 for p1 in future_predictions.values() 
                           for p2 in future_predictions.values() 
                           if np.sign(p1) == np.sign(p2) and p1 != p2)
            total_pairs = len(future_predictions) * (len(future_predictions) - 1)
            agreement_pct = (agreements / total_pairs * 100) if total_pairs > 0 else 0
            st.metric("Model Agreement", f"{agreement_pct:.0f}%")
    
    with col2:
        st.markdown("#### ⚠️ Risk Factors")
        
        # Risk assessment based on volatility and market conditions
        recent_volatility = feature_df['volatility_20'].iloc[-1]
        avg_volatility = feature_df['volatility_20'].mean()
        
        risk_factors = []
        
        if recent_volatility > avg_volatility * 1.5:
            risk_factors.append("🔴 High current volatility")
        
        if abs(pred_change) > 0.05:  # 5% predicted change
            risk_factors.append("🟡 Large predicted movement")
            
        if confidence < 60:
            risk_factors.append("🔴 Low model confidence")
            
        if len(risk_factors) == 0:
            risk_factors.append("🟢 Normal risk conditions")
            
        for risk in risk_factors:
            st.markdown(f"- {risk}")
    
    # Trading recommendations
    st.markdown("### 💡 AI Trading Recommendations")
    
    recommendation_strength = abs(pred_change)
    
    if recommendation_strength < 0.01:  # Less than 1%
        recommendation = "🟡 **HOLD** - Minimal predicted movement"
        strategy = "Wait for clearer signals or consider range trading strategies"
    elif pred_change > 0.03:  # More than 3% bullish
        recommendation = "🟢 **STRONG BUY** - Significant upside predicted"
        strategy = "Consider entering long position with proper risk management"
    elif pred_change > 0.01:  # 1-3% bullish
        recommendation = "🟢 **BUY** - Moderate upside predicted"
        strategy = "Consider small long position, watch for confirmation"
    elif pred_change < -0.03:  # More than 3% bearish
        recommendation = "🔴 **STRONG SELL** - Significant downside predicted"
        strategy = "Consider short position or exit long positions"
    elif pred_change < -0.01:  # 1-3% bearish  
        recommendation = "🔴 **SELL** - Moderate downside predicted"
        strategy = "Reduce long exposure, consider defensive positioning"
    else:
        recommendation = "🟡 **NEUTRAL** - Mixed signals"
        strategy = "Wait for clearer directional signals"
    
        st.markdown(recommendation)
    st.markdown(f"**Strategy:** {strategy}")
    
    # Disclaimer for ML predictions
    st.markdown("---")
    st.markdown("""
    **⚠️ AI Prediction Disclaimer:** 
    - Machine learning predictions are based on historical patterns and may not reflect future market conditions
    - Models can fail during unusual market events, news, or regime changes
    - Always combine ML predictions with fundamental analysis and current market conditions
    - Use proper risk management and never invest more than you can afford to lose
    - These predictions are for educational purposes only and not financial advice
    """)


def show_flight_status_page():
    """Show the Flight Status Dashboard page"""
    
    # Header
    st.title("🛩️ Stock Flight Status Dashboard")
    
    # Description
    st.markdown("""
    **Real-time stock analysis across your entire portfolio - Just like tracking flights at the airport!**
    
    Each stock shows its current "departure status":
    - 🟢 **Buy Signals**: Ready for takeoff (good entry opportunities)
    - 🔴 **Sell Signals**: Delayed/cancelled (consider exit strategies)
    - 🟡 **Hold**: On schedule (maintain current positions)
    """)
    
    with st.expander("ℹ️ How to Read the Dashboard", expanded=False):
        st.markdown("""
        **Signal Score**: -5 to +5
        - **+4,+5**: Strong Buy
        - **+1 to +3**: Buy
        - **0**: Hold/Neutral
        - **-1 to -3**: Sell
        - **-4,-5**: Strong Sell
        
        **Technical Indicators**:
        - **RSI**: Momentum (30-70 normal)
        - **MACD**: Trend direction
        - **SMA**: Long-term trend vs 200-day
        
        **Data Sources**: Your SQL Server database views
        """)
    
    # Index and Ticker Selection
    col1, col2 = st.columns([1, 2])
    
    with col1:
        index_name = st.selectbox(
            "Select Index",
            ["NSE 500", "NASDAQ 100", "Forex"],
            help="Choose which market index to analyze"
        )
    
    # Load data first to get available tickers
    with st.spinner(f"🛩️ Loading flight status for {index_name}..."):
        df = load_flight_status_data(index_name, limit=None)  # Load all stocks
    
    # Ticker filter - only show after data is loaded
    with col2:
        if not df.empty:
            # Get unique tickers from loaded data
            available_tickers = ['All'] + sorted(df['ticker'].unique().tolist())
            selected_ticker = st.selectbox(
                "Select Ticker/Symbol",
                available_tickers,
                index=0,
                help="Filter by specific ticker symbol (default: All)"
            )
        else:
            selected_ticker = 'All'
    
    if df.empty:
        st.error("❌ No data available. Please check your database connection and table structure.")
        return
    
    # Apply ticker filter if a specific ticker is selected
    if selected_ticker != 'All':
        df = df[df['ticker'] == selected_ticker]
        if df.empty:
            st.warning(f"⚠️ No data found for ticker: {selected_ticker}")
            return
    
    # Summary metrics
    render_flight_status_summary_metrics(df)
    
    st.markdown("---")
    
    # Apply filters
    filtered_df = apply_flight_status_filters(df)
    
    if filtered_df.empty:
        st.warning("⚠️ No stocks match your current filters. Try adjusting the filter criteria.")
        return
    
    # Main flight status table
    st.subheader(f"🛩️ Flight Status Board ({len(filtered_df)} stocks)")
    
    # Prepare display data
    display_df = filtered_df.copy()
    display_df['Status'] = display_df['signal_score'].apply(get_flight_status_emoji)
    display_df['Signal Score'] = display_df['signal_score']
    display_df['RSI'] = display_df['RSI'].round(1)
    display_df['Change %'] = display_df['daily_change_pct'].round(2)
    display_df['Price'] = display_df['close_price'].round(2)
    
    # Select columns for display
    columns_to_show = [
        'Status', 'ticker', 'company', 'Signal Score', 'Price', 'Change %',
        'RSI', 'rsi_status', 'macd_trend', 'long_term_trend', 'last_update'
    ]
    
    # Display the table
    st.dataframe(
        display_df[columns_to_show],
        use_container_width=True,
        height=600,
        column_config={
            'Status': st.column_config.TextColumn(
                '✈️ Status',
                help='Flight departure status'
            ),
            'ticker': st.column_config.TextColumn(
                '🏷️ Symbol',
                help='Stock ticker symbol'
            ),
            'company': st.column_config.TextColumn(
                '🏢 Company',
                help='Company name'
            ),
            'Signal Score': st.column_config.NumberColumn(
                '📊 Score',
                help='Combined signal strength (-5 to +5)',
                min_value=-5,
                max_value=5,
                format='%d'
            ),
            'Price': st.column_config.NumberColumn(
                '💰 Price',
                help='Latest close price',
                format='$%.2f'
            ),
            'Change %': st.column_config.NumberColumn(
                '📈 Change %',
                help='Daily change percentage',
                format='%.2f%%'
            ),
            'RSI': st.column_config.NumberColumn(
                '📊 RSI',
                help='Relative Strength Index',
                format='%.1f'
            ),
            'last_update': st.column_config.DatetimeColumn(
                '📅 Updated',
                help='Last update timestamp'
            )
        }
    )
    
    # Export functionality
    if st.button("📥 Export to CSV", key="flight_export_csv"):
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="💾 Download CSV",
            data=csv,
            file_name=f"flight_status_{index_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key="flight_download_csv"
        )


def show_nasdaq_ml_predictions_page():
    """Show NASDAQ ML Predictions page with separate filters"""
    st.title("📊 NASDAQ ML Predictions Dashboard")
    
    st.markdown("""
    ### 🤖 Advanced Machine Learning Predictions for NASDAQ Stocks
    
    This page provides ML-powered insights using dedicated prediction models trained on NASDAQ data.
    
    ---
    """)
    
    # Separate filters for this page
    st.sidebar.header("📊 NASDAQ ML Filters")
    
    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        date_type = st.selectbox(
            "📅 Date Selection Type:",
            ["Date Range", "Single Date"],
            key="nasdaq_ml_date_type"
        )
    
    if date_type == "Single Date":
        selected_date = st.date_input(
            "📅 Select Date:",
            value=datetime.now().date(),
            key="nasdaq_ml_single_date"
        )
        start_date = end_date = selected_date
    else:
        with col2:
            date_range = st.date_input(
                "📅 Select Date Range:",
                value=[datetime.now().date() - pd.Timedelta(days=30), datetime.now().date()],
                key="nasdaq_ml_date_range"
            )
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = date_range[0]
    
    # Ticker filter
    ticker_input = st.text_input(
        "🔍 Ticker Symbol (optional):",
        placeholder="e.g., AAPL, MSFT, TSLA",
        help="Enter ticker symbol for specific stock analysis. Uses partial matching.",
        key="nasdaq_ml_ticker"
    ).upper().strip()
    
    # Load data button
    if st.button("📊 Load NASDAQ ML Data", key="load_nasdaq_ml"):
        with st.spinner("Loading NASDAQ ML prediction data..."):
            # Show filter information
            if ticker_input:
                st.info(f"🔍 Filtering data for ticker: **{ticker_input}**")
            else:
                st.info("📊 Loading all available NASDAQ data...")
            
            try:
                # Query ml_prediction_summary (this is a summary table, no ticker filtering)
                summary_query = "SELECT * FROM dbo.ml_prediction_summary ORDER BY 1 DESC"
                # Note: ml_prediction_summary doesn't have ticker column - it's an aggregate summary
                
                summary_df = execute_query_safe(summary_query)
                
                # Display column information for debugging
                if not summary_df.empty:
                    st.info(f"Available columns in ml_prediction_summary: {', '.join(summary_df.columns.tolist())}")
                
                # Query ml_technical_indicators
                indicators_query = "SELECT * FROM dbo.ml_technical_indicators ORDER BY 1 DESC"
                
                indicators_df = execute_query_safe(indicators_query)
                
                # Apply ticker filtering after loading data if filter is provided
                if not indicators_df.empty and ticker_input:
                    # Find the ticker column (check various possible names)
                    ticker_col = None
                    for col in indicators_df.columns:
                        if any(keyword in col.lower() for keyword in ['ticker', 'symbol', 'stock']):
                            ticker_col = col
                            break
                    
                    if ticker_col:
                        # Apply filter using pandas
                        indicators_df = indicators_df[indicators_df[ticker_col].str.contains(ticker_input, case=False, na=False)]
                        st.success(f"✅ Filtered {ticker_col} column for: {ticker_input}")
                    else:
                        st.warning("⚠️ Could not find ticker column for filtering")
                
                # Display column information for debugging
                if not indicators_df.empty:
                    st.info(f"Available columns in ml_technical_indicators: {', '.join(indicators_df.columns.tolist())}")
                
                # Query ml_trading_predictions
                predictions_query = "SELECT * FROM dbo.ml_trading_predictions ORDER BY 1 DESC"
                
                predictions_df = execute_query_safe(predictions_query)
                
                # Apply ticker filtering after loading data if filter is provided
                if not predictions_df.empty and ticker_input:
                    # Find the ticker column (check various possible names)
                    ticker_col = None
                    for col in predictions_df.columns:
                        if any(keyword in col.lower() for keyword in ['ticker', 'symbol', 'stock']):
                            ticker_col = col
                            break
                    
                    if ticker_col:
                        # Apply filter using pandas
                        predictions_df = predictions_df[predictions_df[ticker_col].str.contains(ticker_input, case=False, na=False)]
                        st.success(f"✅ Filtered {ticker_col} column for: {ticker_input}")
                    else:
                        st.warning("⚠️ Could not find ticker column for filtering")
                
                # Display column information for debugging
                if not predictions_df.empty:
                    st.info(f"Available columns in ml_trading_predictions: {', '.join(predictions_df.columns.tolist())}")
                
                # Display results
                if not summary_df.empty:
                    st.markdown("### 📊 ML Prediction Summary")
                    
                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Predictions", len(summary_df))
                    with col2:
                        unique_tickers = summary_df['ticker'].nunique() if 'ticker' in summary_df.columns else 0
                        st.metric("Unique Tickers", unique_tickers)
                    with col3:
                        if 'confidence_score' in summary_df.columns:
                            avg_confidence = summary_df['confidence_score'].mean()
                            st.metric("Avg Confidence", f"{avg_confidence:.2f}%")
                    with col4:
                        if 'predicted_direction' in summary_df.columns:
                            bullish_count = len(summary_df[summary_df['predicted_direction'].str.contains('UP|BUY|BULL', case=False, na=False)])
                            st.metric("Bullish Signals", bullish_count)
                    
                    # Display summary table with enhanced formatting
                    st.dataframe(
                        summary_df,
                        use_container_width=True,
                        column_config={
                            'run_date': st.column_config.DateColumn('📅 Run Date'),
                            'total_predictions': st.column_config.NumberColumn('🔢 Total Predictions'),
                            'avg_confidence': st.column_config.NumberColumn('🎯 Avg Confidence %', format='%.1f%%'),
                            'buy_signals': st.column_config.NumberColumn('📈 Buy Signals'),
                            'sell_signals': st.column_config.NumberColumn('📉 Sell Signals')
                        }
                    )
                    
                    # Export functionality
                    csv_summary = summary_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Summary (CSV)",
                        data=csv_summary,
                        file_name=f"nasdaq_ml_summary_{start_date}_{end_date}.csv",
                        mime="text/csv",
                        key="download_nasdaq_summary"
                    )
                else:
                    st.warning("No prediction summary data found for the selected criteria.")
                
                # Technical Indicators Section
                if not indicators_df.empty:
                    st.markdown("### 📈 Technical Indicators Analysis")
                    
                    # Indicators metrics - Traditional Indicators
                    st.markdown("#### 📊 Traditional Indicators")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if 'rsi' in indicators_df.columns:
                            avg_rsi = indicators_df['rsi'].mean()
                            st.metric("Avg RSI", f"{avg_rsi:.1f}")
                    with col2:
                        if 'macd_trend' in indicators_df.columns:
                            bullish_macd = len(indicators_df[indicators_df['macd_trend'].str.contains('UP|BULL', case=False, na=False)])
                            st.metric("Bullish MACD Trend", bullish_macd)
                    with col3:
                        if 'trend_direction' in indicators_df.columns:
                            uptrend = len(indicators_df[indicators_df['trend_direction'].str.contains('UP|BULL', case=False, na=False)])
                            st.metric("Uptrend Stocks", uptrend)
                    with col4:
                        if 'volume_sma_ratio' in indicators_df.columns:
                            high_volume = len(indicators_df[indicators_df['volume_sma_ratio'] > 1.5])
                            st.metric("High Volume", high_volume)
                    
                    # Advanced Indicators metrics
                    st.markdown("#### 🎯 Advanced Indicators")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if 'fib_trade_signal' in indicators_df.columns:
                            fib_buy = len(indicators_df[indicators_df['fib_trade_signal'].str.contains('BUY', case=False, na=False)])
                            st.metric("📊 Fibonacci Buy Signals", fib_buy)
                        else:
                            st.info("Fibonacci data not available")
                    with col2:
                        if 'stoch_trade_signal' in indicators_df.columns:
                            stoch_buy = len(indicators_df[indicators_df['stoch_trade_signal'].str.contains('BUY', case=False, na=False)])
                            st.metric("📈 Stochastic Buy Signals", stoch_buy)
                        else:
                            st.info("Stochastic data not available")
                    with col3:
                        if 'sr_trade_signal' in indicators_df.columns:
                            sr_buy = len(indicators_df[indicators_df['sr_trade_signal'].str.contains('BUY', case=False, na=False)])
                            st.metric("📍 S/R Buy Signals", sr_buy)
                        else:
                            st.info("S/R data not available")
                    with col4:
                        if 'pattern_signal' in indicators_df.columns:
                            pattern_bullish = len(indicators_df[indicators_df['pattern_signal'].str.contains('BULLISH', case=False, na=False)])
                            st.metric("🕯️ Bullish Patterns", pattern_bullish)
                        else:
                            st.info("Pattern data not available")
                    
                    st.dataframe(indicators_df, use_container_width=True)
                    
                    # Export indicators
                    csv_indicators = indicators_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Indicators (CSV)",
                        data=csv_indicators,
                        file_name=f"nasdaq_ml_indicators_{start_date}_{end_date}.csv",
                        mime="text/csv",
                        key="download_nasdaq_indicators"
                    )
                else:
                    st.info("No technical indicators data found for the selected criteria.")
                
                # Trading Predictions Section
                if not predictions_df.empty:
                    st.markdown("### 🎯 Trading Predictions")
                    
                    # Predictions metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Predictions", len(predictions_df))
                    with col2:
                        if 'recommendation' in predictions_df.columns:
                            buy_recommendations = len(predictions_df[predictions_df['recommendation'].str.contains('BUY', case=False, na=False)])
                            st.metric("Buy Recommendations", buy_recommendations)
                    with col3:
                        if 'risk_level' in predictions_df.columns:
                            high_risk = len(predictions_df[predictions_df['risk_level'].str.contains('HIGH', case=False, na=False)])
                            st.metric("High Risk", high_risk)
                    with col4:
                        if 'expected_return' in predictions_df.columns:
                            avg_return = predictions_df['expected_return'].mean()
                            st.metric("Avg Expected Return", f"{avg_return:.2f}%")
                    
                    st.dataframe(
                        predictions_df,
                        use_container_width=True,
                        column_config={
                            'prediction_date': st.column_config.DateColumn('📅 Date'),
                            'ticker': st.column_config.TextColumn('🏢 Ticker'),
                            'recommendation': st.column_config.TextColumn('💡 Recommendation'),
                            'expected_return': st.column_config.NumberColumn('📈 Expected Return %', format='%.2f%%'),
                            'risk_level': st.column_config.TextColumn('⚠️ Risk Level')
                        }
                    )
                    
                    # Export predictions
                    csv_predictions = predictions_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Predictions (CSV)",
                        data=csv_predictions,
                        file_name=f"nasdaq_ml_predictions_{start_date}_{end_date}.csv",
                        mime="text/csv",
                        key="download_nasdaq_predictions"
                    )
                else:
                    st.info("No trading predictions data found for the selected criteria.")
                
            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
    
    # Information section
    with st.expander("ℹ️ About NASDAQ ML Predictions", expanded=False):
        st.markdown("""
        **Data Sources:**
        - `dbo.ml_prediction_summary`: High-level ML prediction results
        - `dbo.ml_technical_indicators`: Technical analysis with ML enhancements
        - `dbo.ml_trading_predictions`: Specific trading recommendations
        
        **Features:**
        - Date range or single date filtering
        - Ticker-specific analysis
        - Comprehensive ML metrics
        - Downloadable reports in CSV format
        - Real-time confidence scoring
        """)


def show_nse_ml_predictions_page():
    """Show NSE ML Predictions page with separate filters"""
    st.title("📈 NSE ML Predictions Dashboard")
    
    st.markdown("""
    ### 🤖 Advanced Machine Learning Predictions for NSE Stocks
    
    This page provides ML-powered insights using dedicated prediction models trained on NSE 500 data.
    
    ---
    """)
    
    # Separate filters for this page
    st.sidebar.header("📈 NSE ML Filters")
    
    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        date_type = st.selectbox(
            "📅 Date Selection Type:",
            ["Date Range", "Single Date"],
            key="nse_ml_date_type"
        )
    
    if date_type == "Single Date":
        selected_date = st.date_input(
            "📅 Select Date:",
            value=datetime.now().date(),
            key="nse_ml_single_date"
        )
        start_date = end_date = selected_date
    else:
        with col2:
            date_range = st.date_input(
                "📅 Select Date Range:",
                value=[datetime.now().date() - pd.Timedelta(days=30), datetime.now().date()],
                key="nse_ml_date_range"
            )
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = date_range[0]
    
    # Ticker filter
    ticker_input = st.text_input(
        "🔍 Ticker Symbol (optional):",
        placeholder="e.g., RELIANCE, TCS, INFY",
        help="Enter ticker symbol for specific stock analysis. Uses partial matching.",
        key="nse_ml_ticker"
    ).upper().strip()
    
    # Load data button
    if st.button("📈 Load NSE ML Data", key="load_nse_ml"):
        with st.spinner("Loading NSE ML prediction data..."):
            # Show filter information
            if ticker_input:
                st.info(f"🔍 Filtering data for ticker: **{ticker_input}**")
            else:
                st.info("📈 Loading all available NSE data...")
            
            try:
                # Query ml_nse_predict_summary (this is a summary table, no ticker filtering)
                summary_query = "SELECT * FROM dbo.ml_nse_predict_summary ORDER BY 1 DESC"
                # Note: ml_nse_predict_summary doesn't have ticker column - it's an aggregate summary
                
                summary_df = execute_query_safe(summary_query)
                
                # Display column information for debugging
                if not summary_df.empty:
                    st.info(f"Available columns in ml_nse_predict_summary: {', '.join(summary_df.columns.tolist())}")
                
                # Query ml_nse_technical_indicators
                indicators_query = "SELECT * FROM dbo.ml_nse_technical_indicators ORDER BY 1 DESC"
                
                indicators_df = execute_query_safe(indicators_query)
                
                # Apply ticker filtering after loading data if filter is provided
                if not indicators_df.empty and ticker_input:
                    # Find the ticker column (check various possible names)
                    ticker_col = None
                    for col in indicators_df.columns:
                        if any(keyword in col.lower() for keyword in ['ticker', 'symbol', 'stock']):
                            ticker_col = col
                            break
                    
                    if ticker_col:
                        # Apply filter using pandas
                        indicators_df = indicators_df[indicators_df[ticker_col].str.contains(ticker_input, case=False, na=False)]
                        st.success(f"✅ Filtered {ticker_col} column for: {ticker_input}")
                    else:
                        st.warning("⚠️ Could not find ticker column for filtering")
                
                # Display column information for debugging
                if not indicators_df.empty:
                    st.info(f"Available columns in ml_nse_technical_indicators: {', '.join(indicators_df.columns.tolist())}")
                
                # Query ml_nse_trading_predictions
                predictions_query = "SELECT * FROM dbo.ml_nse_trading_predictions ORDER BY 1 DESC"
                
                predictions_df = execute_query_safe(predictions_query)
                
                # Apply ticker filtering after loading data if filter is provided
                if not predictions_df.empty and ticker_input:
                    # Find the ticker column (check various possible names)
                    ticker_col = None
                    for col in predictions_df.columns:
                        if any(keyword in col.lower() for keyword in ['ticker', 'symbol', 'stock']):
                            ticker_col = col
                            break
                    
                    if ticker_col:
                        # Apply filter using pandas
                        predictions_df = predictions_df[predictions_df[ticker_col].str.contains(ticker_input, case=False, na=False)]
                        st.success(f"✅ Filtered {ticker_col} column for: {ticker_input}")
                    else:
                        st.warning("⚠️ Could not find ticker column for filtering")
                
                # Display column information for debugging
                if not predictions_df.empty:
                    st.info(f"Available columns in ml_nse_trading_predictions: {', '.join(predictions_df.columns.tolist())}")
                
                # Display results
                if not summary_df.empty:
                    st.markdown("### 📊 NSE ML Prediction Summary")
                    
                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Predictions", len(summary_df))
                    with col2:
                        unique_tickers = summary_df['ticker'].nunique() if 'ticker' in summary_df.columns else 0
                        st.metric("Unique Tickers", unique_tickers)
                    with col3:
                        if 'confidence_score' in summary_df.columns:
                            avg_confidence = summary_df['confidence_score'].mean()
                            st.metric("Avg Confidence", f"{avg_confidence:.2f}%")
                    with col4:
                        if 'predicted_direction' in summary_df.columns:
                            bullish_count = len(summary_df[summary_df['predicted_direction'].str.contains('UP|BUY|BULL', case=False, na=False)])
                            st.metric("Bullish Signals", bullish_count)
                    
                    # Display summary table with enhanced formatting
                    st.dataframe(
                        summary_df,
                        use_container_width=True,
                        column_config={
                            'analysis_date': st.column_config.DateColumn('📅 Analysis Date'),
                            'total_predictions': st.column_config.NumberColumn('🔢 Total Predictions'),
                            'avg_confidence': st.column_config.NumberColumn('🎯 Avg Confidence %', format='%.1f%%'),
                            'total_buy_signals': st.column_config.NumberColumn('📈 Buy Signals'),
                            'total_sell_signals': st.column_config.NumberColumn('📉 Sell Signals')
                        }
                    )
                    
                    # Export functionality
                    csv_summary = summary_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Summary (CSV)",
                        data=csv_summary,
                        file_name=f"nse_ml_summary_{start_date}_{end_date}.csv",
                        mime="text/csv",
                        key="download_nse_summary"
                    )
                else:
                    st.warning("No prediction summary data found for the selected criteria.")
                
                # Technical Indicators Section
                if not indicators_df.empty:
                    st.markdown("### 📈 NSE Technical Indicators Analysis")
                    
                    # Indicators metrics - Traditional Indicators
                    st.markdown("#### 📊 Traditional Indicators")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if 'rsi' in indicators_df.columns:
                            avg_rsi = indicators_df['rsi'].mean()
                            st.metric("Avg RSI", f"{avg_rsi:.1f}")
                    with col2:
                        if 'macd_trend' in indicators_df.columns:
                            bullish_macd = len(indicators_df[indicators_df['macd_trend'].str.contains('UP|BULL', case=False, na=False)])
                            st.metric("Bullish MACD Trend", bullish_macd)
                    with col3:
                        if 'trend_direction' in indicators_df.columns:
                            uptrend = len(indicators_df[indicators_df['trend_direction'].str.contains('UP|BULL', case=False, na=False)])
                            st.metric("Uptrend Stocks", uptrend)
                    with col4:
                        if 'volume_sma_ratio' in indicators_df.columns:
                            high_volume = len(indicators_df[indicators_df['volume_sma_ratio'] > 1.5])
                            st.metric("High Volume", high_volume)
                        elif 'volume_trend' in indicators_df.columns:
                            high_volume = len(indicators_df[indicators_df['volume_trend'].str.contains('HIGH', case=False, na=False)])
                            st.metric("High Volume", high_volume)
                    
                    # Advanced Indicators metrics
                    st.markdown("#### 🎯 Advanced Indicators")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if 'fib_trade_signal' in indicators_df.columns:
                            fib_buy = len(indicators_df[indicators_df['fib_trade_signal'].str.contains('BUY', case=False, na=False)])
                            st.metric("📊 Fibonacci Buy Signals", fib_buy)
                        else:
                            st.info("Fibonacci data not available")
                    with col2:
                        if 'stoch_trade_signal' in indicators_df.columns:
                            stoch_buy = len(indicators_df[indicators_df['stoch_trade_signal'].str.contains('BUY', case=False, na=False)])
                            st.metric("📈 Stochastic Buy Signals", stoch_buy)
                        else:
                            st.info("Stochastic data not available")
                    with col3:
                        if 'sr_trade_signal' in indicators_df.columns:
                            sr_buy = len(indicators_df[indicators_df['sr_trade_signal'].str.contains('BUY', case=False, na=False)])
                            st.metric("📍 S/R Buy Signals", sr_buy)
                        else:
                            st.info("S/R data not available")
                    with col4:
                        if 'pattern_signal' in indicators_df.columns:
                            pattern_bullish = len(indicators_df[indicators_df['pattern_signal'].str.contains('BULLISH', case=False, na=False)])
                            st.metric("🕯️ Bullish Patterns", pattern_bullish)
                        else:
                            st.info("Pattern data not available")
                    
                    st.dataframe(indicators_df, use_container_width=True)
                    
                    # Export indicators
                    csv_indicators = indicators_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Indicators (CSV)",
                        data=csv_indicators,
                        file_name=f"nse_ml_indicators_{start_date}_{end_date}.csv",
                        mime="text/csv",
                        key="download_nse_indicators"
                    )
                else:
                    st.info("No technical indicators data found for the selected criteria.")
                
                # Trading Predictions Section
                if not predictions_df.empty:
                    st.markdown("### 🎯 NSE Trading Predictions")
                    
                    # Predictions metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Predictions", len(predictions_df))
                    with col2:
                        if 'recommendation' in predictions_df.columns:
                            buy_recommendations = len(predictions_df[predictions_df['recommendation'].str.contains('BUY', case=False, na=False)])
                            st.metric("Buy Recommendations", buy_recommendations)
                    with col3:
                        if 'risk_level' in predictions_df.columns:
                            high_risk = len(predictions_df[predictions_df['risk_level'].str.contains('HIGH', case=False, na=False)])
                            st.metric("High Risk", high_risk)
                    with col4:
                        if 'expected_return' in predictions_df.columns:
                            avg_return = predictions_df['expected_return'].mean()
                            st.metric("Avg Expected Return", f"{avg_return:.2f}%")
                    
                    st.dataframe(
                        predictions_df,
                        use_container_width=True,
                        column_config={
                            'prediction_date': st.column_config.DateColumn('📅 Date'),
                            'ticker': st.column_config.TextColumn('🏢 Ticker'),
                            'recommendation': st.column_config.TextColumn('💡 Recommendation'),
                            'expected_return': st.column_config.NumberColumn('📈 Expected Return %', format='%.2f%%'),
                            'risk_level': st.column_config.TextColumn('⚠️ Risk Level')
                        }
                    )
                    
                    # Export predictions
                    csv_predictions = predictions_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Predictions (CSV)",
                        data=csv_predictions,
                        file_name=f"nse_ml_predictions_{start_date}_{end_date}.csv",
                        mime="text/csv",
                        key="download_nse_predictions"
                    )
                else:
                    st.info("No trading predictions data found for the selected criteria.")
                
            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
    
    # Information section
    with st.expander("ℹ️ About NSE ML Predictions", expanded=False):
        st.markdown("""
        **Data Sources:**
        - `dbo.ml_nse_predict_summary`: High-level ML prediction results
        - `dbo.ml_nse_technical_indicators`: Technical analysis with ML enhancements
        - `dbo.ml_nse_trading_predictions`: Specific trading recommendations
        
        **Features:**
        - Date range or single date filtering
        - Ticker-specific analysis
        - NSE 500 focused predictions
        - Downloadable reports in CSV format
        - Indian market specific insights
        """)


def show_today_trend_recommendations_page():
    """Show Today Trend Recommendations page with RSI/MACD/SMA strategy analysis"""
    st.markdown("""
    # 📈 Today Trend Recommendations
    
    ### Advanced Technical Analysis: Double & Triple Strategy Detection
    
    Identify high-potential trading opportunities using sophisticated technical indicators:
    - **Double Strategy**: RSI ≤ 30 + MACD > Signal Line
    - **Triple Strategy**: Double Strategy + Current Price > SMA 50
    
    ---
    """)
    
    # Get the latest available MACD date for smart defaults
    latest_macd_date = get_latest_macd_date()
    if latest_macd_date:
        latest_date = latest_macd_date.date() if hasattr(latest_macd_date, 'date') else latest_macd_date
        st.info(f"📊 Latest MACD data available: {latest_date}")
    else:
        latest_date = pd.Timestamp.now().date()
        st.warning("⚠️ Could not determine latest MACD date, using today as default")
    
    # Date selection controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        date_range_option = st.selectbox(
            "📅 Date Selection:",
            ["Single Date", "Date Range (Last 7 Days)", "Date Range (Last 14 Days)", "Custom Range"],
            key="date_range_option",
            help="Choose how to select analysis dates"
        )
    
    # Date inputs based on selection
    if date_range_option == "Single Date":
        analysis_date = st.date_input(
            "📅 Analysis Date:",
            value=latest_date,
            key="trend_analysis_date",
            help="Select single date to analyze (defaulted to latest available MACD data)"
        )
        date_range = [analysis_date.strftime('%Y-%m-%d')]
    elif date_range_option == "Date Range (Last 7 Days)":
        end_date = latest_date
        start_date = (pd.Timestamp(latest_date) - pd.Timedelta(days=6)).date()  # 7 days total including end date
        st.info(f"📅 Analyzing last 7 days: {start_date} to {end_date} (based on latest MACD data)")
        # Generate date range for last 7 days
        date_range = [(start_date + pd.Timedelta(days=i)).strftime('%Y-%m-%d') 
                     for i in range((end_date - start_date).days + 1)]
    elif date_range_option == "Date Range (Last 14 Days)":
        end_date = latest_date
        start_date = (pd.Timestamp(latest_date) - pd.Timedelta(days=13)).date()  # 14 days total including end date
        st.info(f"📅 Analyzing last 14 days: {start_date} to {end_date} (based on latest MACD data)")
        # Generate date range for last 14 days
        date_range = [(start_date + pd.Timedelta(days=i)).strftime('%Y-%m-%d') 
                     for i in range((end_date - start_date).days + 1)]
    else:  # Custom Range
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input(
                "Start Date:",
                value=(pd.Timestamp(latest_date) - pd.Timedelta(days=6)).date(),
                key="custom_start_date"
            )
        with col_end:
            end_date = st.date_input(
                "End Date:",
                value=latest_date,
                key="custom_end_date",
                help="Defaulted to latest available MACD data"
            )
        
        if start_date <= end_date:
            date_range = [(start_date + pd.Timedelta(days=i)).strftime('%Y-%m-%d') 
                         for i in range((end_date - start_date).days + 1)]
        else:
            st.error("Start date must be before end date")
            return
    
    with col2:
        market_selection = st.selectbox(
            "🏪 Market:",
            ["All Markets", "NSE 500", "NASDAQ 100"],
            key="trend_market_selection"
        )
    
    with col3:
        strategy_filter = st.selectbox(
            "📊 Strategy Filter:",
            ["All Strategies", "Triple Strategy Only", "Double Strategy Only"],
            key="strategy_filter"
        )
    
    # Determine markets to analyze
    if market_selection == "All Markets":
        markets_to_analyze = ["NSE 500", "NASDAQ 100"]
    else:
        markets_to_analyze = [market_selection]
    
    # Display analysis information
    if len(date_range) == 1:
        st.info(f"""
        📊 **Analysis Configuration:**
        - **Markets**: {', '.join(markets_to_analyze)}
        - **Date**: {date_range[0]}
        """)
    else:
        st.info(f"""
        📊 **Analysis Configuration:**
        - **Markets**: {', '.join(markets_to_analyze)}
        - **Date Range**: {date_range[0]} to {date_range[-1]} ({len(date_range)} days)
        """)
    
    # Check MACD data availability (should rarely trigger now with smart defaults)
    with st.spinner("Validating data availability..."):
        latest_macd_date_check = get_latest_macd_date()
        if latest_macd_date_check:
            latest_date_str = latest_macd_date_check.strftime('%Y-%m-%d')
            latest_macd_date_only = latest_macd_date_check.date() if hasattr(latest_macd_date_check, 'date') else latest_macd_date_check
            if any(pd.Timestamp(date).date() > latest_macd_date_only for date in date_range):
                st.warning(f"""
                📊 **Data Availability Notice**
                
                **Latest MACD Data:** {latest_date_str}  
                **Selected Date Range:** {date_range[0]} to {date_range[-1]}
                
                Some selected dates are beyond the latest MACD data. You can:
                """)
                
                # Offer to filter dates to available range
                valid_dates = [date for date in date_range if pd.Timestamp(date).date() <= latest_macd_date_only]
                if valid_dates:
                    if st.button(f"🔄 Analyze Available Dates Only ({len(valid_dates)} days)"):
                        date_range = valid_dates
                        st.rerun()
                else:
                    st.info("💡 Please select earlier dates with available MACD data.")
                    st.stop()

    # Load trend analysis data
    with st.spinner(f"Analyzing trends across {len(markets_to_analyze)} market(s) and {len(date_range)} date(s)..."):
        if len(date_range) == 1 and len(markets_to_analyze) == 1:
            # Single market, single date - use original function
            trend_df = get_trend_analysis_data(markets_to_analyze[0], date_range[0])
            if not trend_df.empty:
                trend_df['market'] = markets_to_analyze[0]
                trend_df['analysis_date'] = date_range[0]
        else:
            # Multiple markets or dates - use range function
            trend_df = get_trend_analysis_data_range(markets_to_analyze, date_range)
    
    if trend_df.empty:
        st.warning(f"📈 No trend recommendations found for the selected criteria")
        st.info("""
        💡 **Possible reasons:**
        - No stocks meeting the strategy criteria in the selected period
        - Weekend or holiday periods (no trading data)
        - Missing technical indicator data
        
        **Try:**
        - Expanding the date range
        - Checking different market combinations
        - Using a longer historical period
        """)
        return
    
    if trend_df.empty:
        st.warning(f"📈 No trend recommendations found for {analysis_date_str} in {market_selection}")
        st.info("""
        💡 **Possible reasons:**
        - No stocks meeting the strategy criteria on this date
        - Weekend or holiday (no trading data)
        - Missing technical indicator data
        
        Try selecting a different trading day.
        """)
        return
    
    # Apply strategy filter
    if strategy_filter == "Triple Strategy Only":
        filtered_df = trend_df[trend_df['triple_strategy'] == 1]
    elif strategy_filter == "Double Strategy Only":
        filtered_df = trend_df[trend_df['double_strategy'] == 1]
    else:
        filtered_df = trend_df.copy()
    
    if filtered_df.empty:
        st.warning(f"No stocks found matching {strategy_filter} criteria")
        return
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_opportunities = len(filtered_df)
        st.metric("📊 Total Opportunities", total_opportunities)
    
    with col2:
        triple_count = len(filtered_df[filtered_df['triple_strategy'] == 1])
        st.metric("🎯 Triple Strategy", triple_count)
    
    with col3:
        double_count = len(filtered_df[filtered_df['double_strategy'] == 1])
        st.metric("⚡ Double Strategy", double_count)
    
    with col4:
        if 'market' in filtered_df.columns:
            unique_dates = len(filtered_df['analysis_date'].unique()) if 'analysis_date' in filtered_df.columns else 1
            unique_markets = len(filtered_df['market'].unique())
            st.metric("📅 Dates × Markets", f"{unique_dates} × {unique_markets}")
        else:
            avg_rsi = filtered_df['RSI'].mean() if not filtered_df.empty else 0
            st.metric("📉 Avg RSI", f"{avg_rsi:.1f}")
    
    # Enhanced analysis with date/market information
    st.markdown("### 📊 Detailed Trend Analysis Results")
    
    # Add explanation
    st.info("""
    🔍 **Historical Tracking**: See when strategies changed!
    - 🆕 **NEW** = Strategy appeared today (wasn't there yesterday)
    - ⏫ **UPGRADE** = Moved from Double to Triple strategy
    - ✅ **ACTIVE** = Strategy continuing from previous periods
    - 🔄 **FLIP** = Strategy status changed from last week
    """)
    
    # Create enhanced display dataframe
    display_results = []
    
    for _, row in filtered_df.iterrows():
        # Determine strategy change status
        current_strategy = '🎯 Triple' if row['triple_strategy'] == 1 else '⚡ Double'
        prev_day_had_double = row.get('prev_day_double', 0) == 1
        prev_day_had_triple = row.get('prev_day_triple', 0) == 1
        prev_week_had_double = row.get('prev_week_double', 0) == 1
        prev_week_had_triple = row.get('prev_week_triple', 0) == 1
        
        # Determine status
        if row['triple_strategy'] == 1:
            if not prev_day_had_triple:
                if prev_day_had_double:
                    status = '⏫ UPGRADED'
                else:
                    status = '🆕 NEW TRIPLE'
            elif not prev_week_had_triple:
                status = '🔄 FLIPPED'
            else:
                status = '✅ ACTIVE'
        else:  # double strategy
            if not prev_day_had_double:
                status = '🆕 NEW DOUBLE'
            elif not prev_week_had_double:
                status = '🔄 FLIPPED'
            else:
                status = '✅ ACTIVE'
        
        # Previous day strategy
        if prev_day_had_triple:
            prev_day_strategy = '🎯 Triple'
        elif prev_day_had_double:
            prev_day_strategy = '⚡ Double'
        else:
            prev_day_strategy = '❌ None'
            
        # Previous week strategy
        if prev_week_had_triple:
            prev_week_strategy = '🎯 Triple'
        elif prev_week_had_double:
            prev_week_strategy = '⚡ Double'
        else:
            prev_week_strategy = '❌ None'
        
        result = {
            'Date': row.get('analysis_date', 'N/A'),
            'Market': row.get('market', market_selection),
            'Ticker': row['ticker'],
            'Status': status,
            'Current Strategy': current_strategy,
            'Prev Day': prev_day_strategy,
            'Prev Week': prev_week_strategy,
            'Price': f"${row['close_price']:.2f}",
            'RSI': f"{row['RSI']:.1f}",
            'MACD': f"{row['MACD']:.3f}",
            'Signal Line': f"{row['Signal_Line']:.3f}",
            'SMA 50': f"${row['SMA_50']:.2f}",
            'MACD Signal': '🟢 Bullish' if row['MACD'] > row['Signal_Line'] else '🔴 Bearish',
            'Price vs SMA': '✅ Above' if row['close_price'] > row['SMA_50'] else '❌ Below'
        }
        display_results.append(result)
    
    if display_results:
        results_df = pd.DataFrame(display_results)
        
        # Sort by status priority and then by strategy
        status_priority = {'🆕 NEW TRIPLE': 0, '🆕 NEW DOUBLE': 1, '⏫ UPGRADED': 2, '🔄 FLIPPED': 3, '✅ ACTIVE': 4}
        results_df['sort_priority'] = results_df['Status'].map(status_priority)
        results_df = results_df.sort_values(['sort_priority', 'Current Strategy'], ascending=[True, False])
        results_df = results_df.drop('sort_priority', axis=1)
        
        st.dataframe(
            results_df,
            use_container_width=True,
            height=600
        )
        
        # Download functionality
        csv_data = results_df.to_csv(index=False)
        filename_suffix = "_".join(markets_to_analyze).replace(" ", "_")
        if len(date_range) == 1:
            filename = f"trend_recommendations_{filename_suffix}_{date_range[0]}.csv"
        else:
            filename = f"trend_recommendations_{filename_suffix}_{date_range[0]}_to_{date_range[-1]}.csv"
            
        st.download_button(
            label="📥 Download Trend Analysis (CSV)",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            key="download_trend_analysis"
        )
    
    # Visualization section
    st.markdown("### 📊 Analysis Visualizations")
    
    if not filtered_df.empty:
        # Create visualization columns
        viz_col1, viz_col2 = st.columns(2)
        
        with viz_col1:
            # Strategy distribution chart
            strategy_counts = {
                'Triple Strategy': len(filtered_df[filtered_df['triple_strategy'] == 1]),
                'Double Strategy Only': len(filtered_df[(filtered_df['double_strategy'] == 1) & (filtered_df['triple_strategy'] == 0)])
            }
            
            fig_pie = px.pie(
                values=list(strategy_counts.values()),
                names=list(strategy_counts.keys()),
                title='Strategy Distribution',
                color_discrete_map={'Triple Strategy': '#2E8B57', 'Double Strategy Only': '#FF6347'}
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with viz_col2:
            # Market distribution if multiple markets
            if 'market' in filtered_df.columns and len(markets_to_analyze) > 1:
                market_counts = filtered_df['market'].value_counts()
                fig_market = px.bar(
                    x=market_counts.index,
                    y=market_counts.values,
                    title='Opportunities by Market',
                    labels={'x': 'Market', 'y': 'Number of Opportunities'}
                )
                fig_market.update_layout(height=400)
                st.plotly_chart(fig_market, use_container_width=True)
            else:
                # RSI distribution
                fig_rsi = px.histogram(
                    filtered_df,
                    x='RSI',
                    nbins=15,
                    title='RSI Distribution',
                    labels={'RSI': 'RSI Value', 'count': 'Number of Stocks'}
                )
                fig_rsi.add_vline(x=30, line_dash="dash", line_color="red", 
                                 annotation_text="RSI 30 Threshold")
                fig_rsi.update_layout(height=400)
                st.plotly_chart(fig_rsi, use_container_width=True)
        
        # Time series if multiple dates
        if 'analysis_date' in filtered_df.columns and len(date_range) > 1:
            st.markdown("#### 📅 Opportunities Over Time")
            
            # Count opportunities by date
            daily_counts = filtered_df.groupby('analysis_date').agg({
                'ticker': 'count',
                'triple_strategy': 'sum',
                'double_strategy': 'sum'
            }).rename(columns={
                'ticker': 'Total Opportunities',
                'triple_strategy': 'Triple Strategy',
                'double_strategy': 'Double Strategy'
            })
            
            fig_timeline = px.line(
                daily_counts.reset_index(),
                x='analysis_date',
                y='Total Opportunities',
                title='Daily Trend Opportunities',
                markers=True
            )
            fig_timeline.update_layout(height=400)
            st.plotly_chart(fig_timeline, use_container_width=True)
    
    else:
        st.info("No data available for visualization.")


def get_ai_trading_signals_data(market: str, analysis_date: str) -> pd.DataFrame:
    """Get AI trading signals (crossover-based) for a specific date and market"""
    if market == 'NSE 500':
        bb_view = 'nse_500_bb_signals'
        macd_view = 'nse_500_macd_signals'
        rsi_view = 'nse_500_rsi_signals'
        sma_view = 'nse_500_sma_signals'
        price_table = 'nse_500_hist_data'
        ticker_col = 'ticker'
    elif market == 'NASDAQ 100':
        bb_view = 'nasdaq_100_bb_signals'
        macd_view = 'nasdaq_100_macd_signals'
        rsi_view = 'nasdaq_100_rsi_signals'
        sma_view = 'nasdaq_100_sma_signals'
        price_table = 'nasdaq_100_hist_data'
        ticker_col = 'ticker'
    else:  # Forex
        bb_view = 'forex_bb_signals'
        macd_view = 'forex_macd_signals'
        rsi_view = 'forex_rsi_signals'
        sma_view = 'forex_sma_signals'
        price_table = 'forex_hist_data'
        ticker_col = 'symbol'
    
    query = f"""
    WITH date_context AS (
        SELECT DISTINCT trading_date
        FROM dbo.{macd_view}
        WHERE trading_date <= ?
        ORDER BY trading_date DESC
        OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY
    ),
    prev_day AS (
        SELECT trading_date as prev_day_date
        FROM date_context
        ORDER BY trading_date DESC
        OFFSET 1 ROWS FETCH NEXT 1 ROWS ONLY
    ),
    prev_week AS (
        SELECT trading_date as prev_week_date
        FROM date_context
        ORDER BY trading_date DESC
        OFFSET 5 ROWS FETCH NEXT 1 ROWS ONLY
    ),
    current_signals AS (
        SELECT 
            m.{ticker_col},
            m.trading_date,
            p.close_price,
            bb.bb_trade_signal,
            m.MACD_Signal as macd_signal,
            r.rsi_trade_signal,
            s.sma_trade_signal,
            -- Count bullish signals
            (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
             CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%buy%' THEN 1 ELSE 0 END +
             CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
             CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END) as bullish_count,
            -- Count bearish signals
            (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
             CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%sell%' THEN 1 ELSE 0 END +
             CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
             CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END) as bearish_count
        FROM dbo.{macd_view} m
        LEFT JOIN dbo.{price_table} p ON m.{ticker_col} = p.{ticker_col} AND m.trading_date = p.trading_date
        LEFT JOIN dbo.{bb_view} bb ON m.{ticker_col} = bb.{ticker_col} AND m.trading_date = bb.trading_date
        LEFT JOIN dbo.{rsi_view} r ON m.{ticker_col} = r.{ticker_col} AND m.trading_date = r.trading_date
        LEFT JOIN dbo.{sma_view} s ON m.{ticker_col} = s.{ticker_col} AND m.trading_date = s.trading_date
        WHERE m.trading_date = ?
    ),
    prev_day_signals AS (
        SELECT 
            m.{ticker_col},
            (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
             CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%buy%' THEN 1 ELSE 0 END +
             CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
             CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END) as prev_day_bullish,
            (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
             CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%sell%' THEN 1 ELSE 0 END +
             CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
             CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END) as prev_day_bearish
        FROM dbo.{macd_view} m
        LEFT JOIN dbo.{bb_view} bb ON m.{ticker_col} = bb.{ticker_col} AND m.trading_date = bb.trading_date
        LEFT JOIN dbo.{rsi_view} r ON m.{ticker_col} = r.{ticker_col} AND m.trading_date = r.trading_date
        LEFT JOIN dbo.{sma_view} s ON m.{ticker_col} = s.{ticker_col} AND m.trading_date = s.trading_date
        CROSS JOIN prev_day
        WHERE m.trading_date = prev_day.prev_day_date
    ),
    prev_week_signals AS (
        SELECT 
            m.{ticker_col},
            (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
             CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%buy%' THEN 1 ELSE 0 END +
             CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
             CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END) as prev_week_bullish,
            (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
             CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%sell%' THEN 1 ELSE 0 END +
             CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
             CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END) as prev_week_bearish
        FROM dbo.{macd_view} m
        LEFT JOIN dbo.{bb_view} bb ON m.{ticker_col} = bb.{ticker_col} AND m.trading_date = bb.trading_date
        LEFT JOIN dbo.{rsi_view} r ON m.{ticker_col} = r.{ticker_col} AND m.trading_date = r.trading_date
        LEFT JOIN dbo.{sma_view} s ON m.{ticker_col} = s.{ticker_col} AND m.trading_date = s.trading_date
        CROSS JOIN prev_week
        WHERE m.trading_date = prev_week.prev_week_date
    )
    SELECT 
        c.*,
        ISNULL(pd.prev_day_bullish, 0) as prev_day_bullish,
        ISNULL(pd.prev_day_bearish, 0) as prev_day_bearish,
        ISNULL(pw.prev_week_bullish, 0) as prev_week_bullish,
        ISNULL(pw.prev_week_bearish, 0) as prev_week_bearish
    FROM current_signals c
    LEFT JOIN prev_day_signals pd ON c.{ticker_col} = pd.{ticker_col}
    LEFT JOIN prev_week_signals pw ON c.{ticker_col} = pw.{ticker_col}
    WHERE c.bullish_count >= 2 OR c.bearish_count >= 2
    ORDER BY c.bullish_count DESC, c.bearish_count DESC, c.{ticker_col}
    """
    
    return execute_query_safe(query, params=[analysis_date, analysis_date])


def show_ai_trading_signals_scanner():
    """Show AI Trading Signals Scanner page with crossover-based signal detection"""
    st.markdown("""
    # 🤖 AI Trading Signals Scanner
    
    ### AI-Powered Crossover Signal Detection
    
    Find actionable trading opportunities using AI crossover signals from:
    - **MACD**: Crossover events (not just position)
    - **RSI**: Momentum shift signals
    - **Bollinger Bands**: Band touch/bounce signals
    - **Moving Averages**: Price crossover signals
    
    **Key Difference from Trend Recommendations:**
    - ✅ **AI Signals** = Based on recent crossovers (timing-focused)
    - 📊 **Trend Recommendations** = Based on current indicator positions (condition-focused)
    
    ---
    """)
    
    # Get the latest available MACD date
    latest_macd_date = get_latest_macd_date()
    if latest_macd_date:
        latest_date = latest_macd_date.date() if hasattr(latest_macd_date, 'date') else latest_macd_date
        st.info(f"📊 Latest AI signal data available: {latest_date}")
    else:
        latest_date = pd.Timestamp.now().date()
        st.warning("⚠️ Could not determine latest signal date, using today as default")
    
    # Controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        analysis_date = st.date_input(
            "📅 Analysis Date:",
            value=latest_date,
            key="ai_signal_date",
            help="Select date to analyze AI trading signals"
        )
    
    with col2:
        market_selection = st.selectbox(
            "🏪 Market:",
            ["NSE 500", "NASDAQ 100", "Forex"],
            key="ai_signal_market"
        )
    
    with col3:
        signal_filter = st.selectbox(
            "📊 Signal Filter:",
            ["All Signals", "Strong Bullish (3-4 signals)", "Strong Bearish (3-4 signals)", "Moderate Bullish (2 signals)", "Moderate Bearish (2 signals)"],
            key="ai_signal_filter"
        )
    
    analysis_date_str = analysis_date.strftime('%Y-%m-%d')
    
    # Load AI signal data
    with st.spinner(f"Analyzing AI trading signals for {analysis_date_str}..."):
        signals_df = get_ai_trading_signals_data(market_selection, analysis_date_str)
    
    if signals_df.empty:
        st.warning(f"📈 No AI trading signals found for {analysis_date_str} in {market_selection}")
        st.info("""
        💡 **Possible reasons:**
        - No fresh crossover signals on this date
        - Weekend or holiday (no trading data)
        - Missing signal view data
        
        **Try:**
        - Select a different trading day
        - Check the Technical Analysis page for individual signals
        """)
        return
    
    # Apply signal filter
    if signal_filter == "Strong Bullish (3-4 signals)":
        filtered_df = signals_df[signals_df['bullish_count'] >= 3]
    elif signal_filter == "Strong Bearish (3-4 signals)":
        filtered_df = signals_df[signals_df['bearish_count'] >= 3]
    elif signal_filter == "Moderate Bullish (2 signals)":
        filtered_df = signals_df[signals_df['bullish_count'] == 2]
    elif signal_filter == "Moderate Bearish (2 signals)":
        filtered_df = signals_df[signals_df['bearish_count'] == 2]
    else:
        filtered_df = signals_df.copy()
    
    if filtered_df.empty:
        st.warning(f"No signals found matching {signal_filter} criteria")
        return
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_signals = len(filtered_df)
        st.metric("📊 Total Signals", total_signals)
    
    with col2:
        strong_bullish = len(filtered_df[filtered_df['bullish_count'] >= 3])
        st.metric("🟢 Strong Bullish", strong_bullish)
    
    with col3:
        strong_bearish = len(filtered_df[filtered_df['bearish_count'] >= 3])
        st.metric("🔴 Strong Bearish", strong_bearish)
    
    with col4:
        moderate_signals = len(filtered_df[(filtered_df['bullish_count'] == 2) | (filtered_df['bearish_count'] == 2)])
        st.metric("🟡 Moderate Signals", moderate_signals)
    
    # Detailed results
    st.markdown("### 📊 AI Trading Signal Details")
    
    st.info("""
    🔍 **Signal Strength Tracking**:
    - 🆕 **NEW** = Signal appeared today (wasn't there yesterday)
    - ⏫ **STRONGER** = More indicators aligned than yesterday
    - ⏬ **WEAKER** = Fewer indicators aligned than yesterday
    - ✅ **ACTIVE** = Signal continuing with same strength
    - 🔄 **FLIP** = Signal direction changed from last week
    """)
    
    # Create enhanced display dataframe
    display_results = []
    
    for _, row in filtered_df.iterrows():
        ticker_col = 'ticker' if market_selection != 'Forex' else 'symbol'
        
        # Determine signal strength and status
        current_bullish = row['bullish_count']
        current_bearish = row['bearish_count']
        prev_day_bullish = row.get('prev_day_bullish', 0)
        prev_day_bearish = row.get('prev_day_bearish', 0)
        prev_week_bullish = row.get('prev_week_bullish', 0)
        prev_week_bearish = row.get('prev_week_bearish', 0)
        
        # Determine primary signal
        if current_bullish > current_bearish:
            signal_type = f"🟢 BULLISH ({current_bullish}/4)"
            strength = "💪 Strong" if current_bullish >= 3 else "⚡ Moderate"
        elif current_bearish > current_bullish:
            signal_type = f"🔴 BEARISH ({current_bearish}/4)"
            strength = "💪 Strong" if current_bearish >= 3 else "⚡ Moderate"
        else:
            signal_type = f"🟡 MIXED ({current_bullish}-{current_bearish})"
            strength = "⚖️ Neutral"
        
        # Determine status change
        if current_bullish >= 2 and prev_day_bullish < 2:
            status = "🆕 NEW BULLISH"
        elif current_bearish >= 2 and prev_day_bearish < 2:
            status = "🆕 NEW BEARISH"
        elif current_bullish > prev_day_bullish and prev_day_bullish >= 2:
            status = "⏫ STRONGER"
        elif current_bullish < prev_day_bullish and current_bullish >= 2:
            status = "⏬ WEAKER"
        elif current_bearish > prev_day_bearish and prev_day_bearish >= 2:
            status = "⏫ STRONGER"
        elif current_bearish < prev_day_bearish and current_bearish >= 2:
            status = "⏬ WEAKER"
        elif (current_bullish >= 2 and prev_week_bearish >= 2) or (current_bearish >= 2 and prev_week_bullish >= 2):
            status = "🔄 FLIPPED"
        else:
            status = "✅ ACTIVE"
        
        # Previous day signal
        if prev_day_bullish >= 3:
            prev_day_signal = f"🟢 Strong ({prev_day_bullish}/4)"
        elif prev_day_bullish == 2:
            prev_day_signal = f"🟢 Moderate ({prev_day_bullish}/4)"
        elif prev_day_bearish >= 3:
            prev_day_signal = f"🔴 Strong ({prev_day_bearish}/4)"
        elif prev_day_bearish == 2:
            prev_day_signal = f"🔴 Moderate ({prev_day_bearish}/4)"
        else:
            prev_day_signal = "❌ None"
        
        # Previous week signal
        if prev_week_bullish >= 3:
            prev_week_signal = f"🟢 Strong ({prev_week_bullish}/4)"
        elif prev_week_bullish == 2:
            prev_week_signal = f"🟢 Moderate ({prev_week_bullish}/4)"
        elif prev_week_bearish >= 3:
            prev_week_signal = f"🔴 Strong ({prev_week_bearish}/4)"
        elif prev_week_bearish == 2:
            prev_week_signal = f"🔴 Moderate ({prev_week_bearish}/4)"
        else:
            prev_week_signal = "❌ None"
        
        # Get price value safely
        price_val = row.get('close_price')
        if pd.notna(price_val) and price_val is not None:
            try:
                price_display = f"${float(price_val):.2f}"
            except (ValueError, TypeError):
                price_display = 'N/A'
        else:
            price_display = 'N/A'
        
        result = {
            'Ticker': row[ticker_col],
            'Status': status,
            'Signal': signal_type,
            'Strength': strength,
            'Prev Day': prev_day_signal,
            'Prev Week': prev_week_signal,
            'Price': price_display,
            'BB Signal': str(row.get('bb_trade_signal', 'N/A')),
            'MACD Signal': str(row.get('macd_signal', 'N/A')),
            'RSI Signal': str(row.get('rsi_trade_signal', 'N/A')),
            'SMA Signal': str(row.get('sma_trade_signal', 'N/A'))
        }
        display_results.append(result)
    
    if display_results:
        results_df = pd.DataFrame(display_results)
        
        # Sort by status priority
        status_priority = {
            '🆕 NEW BULLISH': 0, '🆕 NEW BEARISH': 1, '⏫ STRONGER': 2, 
            '🔄 FLIPPED': 3, '✅ ACTIVE': 4, '⏬ WEAKER': 5
        }
        results_df['sort_priority'] = results_df['Status'].map(status_priority)
        results_df = results_df.sort_values('sort_priority')
        results_df = results_df.drop('sort_priority', axis=1)
        
        st.dataframe(
            results_df,
            use_container_width=True,
            height=600
        )
        
        # Download functionality
        csv_data = results_df.to_csv(index=False)
        filename = f"ai_trading_signals_{market_selection.replace(' ', '_')}_{analysis_date_str}.csv"
        
        st.download_button(
            label="📥 Download AI Signals (CSV)",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            key="download_ai_signals"
        )
    
    # Visualization
    st.markdown("### 📊 Signal Strength Distribution")
    
    if not filtered_df.empty:
        viz_col1, viz_col2 = st.columns(2)
        
        with viz_col1:
            # Bullish vs Bearish distribution
            signal_dist = {
                'Strong Bullish (3-4)': len(filtered_df[filtered_df['bullish_count'] >= 3]),
                'Moderate Bullish (2)': len(filtered_df[filtered_df['bullish_count'] == 2]),
                'Moderate Bearish (2)': len(filtered_df[filtered_df['bearish_count'] == 2]),
                'Strong Bearish (3-4)': len(filtered_df[filtered_df['bearish_count'] >= 3])
            }
            
            fig_dist = px.bar(
                x=list(signal_dist.keys()),
                y=list(signal_dist.values()),
                title='Signal Strength Distribution',
                labels={'x': 'Signal Type', 'y': 'Count'},
                color=list(signal_dist.keys()),
                color_discrete_map={
                    'Strong Bullish (3-4)': '#00A86B',
                    'Moderate Bullish (2)': '#90EE90',
                    'Moderate Bearish (2)': '#FFB6C1',
                    'Strong Bearish (3-4)': '#DC143C'
                }
            )
            fig_dist.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig_dist, use_container_width=True)
        
        with viz_col2:
            # Signal count distribution
            bullish_counts = filtered_df['bullish_count'].value_counts().sort_index()
            bearish_counts = filtered_df['bearish_count'].value_counts().sort_index()
            
            fig_counts = go.Figure()
            fig_counts.add_trace(go.Bar(
                x=bullish_counts.index,
                y=bullish_counts.values,
                name='Bullish Signals',
                marker_color='green'
            ))
            fig_counts.add_trace(go.Bar(
                x=bearish_counts.index,
                y=bearish_counts.values,
                name='Bearish Signals',
                marker_color='red'
            ))
            fig_counts.update_layout(
                title='Number of Aligned Indicators',
                xaxis_title='Signal Count',
                yaxis_title='Number of Stocks',
                barmode='group',
                height=400
            )
            st.plotly_chart(fig_counts, use_container_width=True)


def show_reco_tracking_page():
    """Show Recommendation Tracking and Current Status page"""
    st.markdown("""
    # 📊 Recommendation Tracking and Current Status
    
    ### Monitor performance of tracked recommendations from NSE 500 and NASDAQ 100
    
    Track the performance of your monitored stocks from recommendation start date to current status.
    
    ---
    """)
    
    # Load recommendation data
    with st.spinner("Loading recommendation tracking data..."):
        reco_df = load_recommendations()
    
    if reco_df.empty:
        st.warning("📋 No active recommendations found in the master tables.")
        st.info("""
        💡 **To add recommendations:**
        - Add entries to `dbo.NSE_500` or `dbo.NASDAQ_top100` tables
        - Include `monitor_startdate` and optionally `monitor_enddate`
        - Set appropriate `comments` and `process_flag` values
        """)
        return
    
    st.success(f"✅ Found {len(reco_df)} active recommendations")
    
    # Filter controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        market_filter = st.selectbox(
            "🏪 Filter by Market:",
            ["All"] + list(reco_df['market'].unique()),
            key="reco_market_filter"
        )
    
    with col2:
        status_filter = st.selectbox(
            "📊 Filter by Status:",
            ["All", "Active", "Ended"],
            key="reco_status_filter"
        )
    
    with col3:
        sort_by = st.selectbox(
            "🔄 Sort by:",
            ["Monitor Start Date", "Company Name", "Performance %"],
            key="reco_sort_by"
        )
    
    # Apply filters
    filtered_df = reco_df.copy()
    
    if market_filter != "All":
        filtered_df = filtered_df[filtered_df['market'] == market_filter]
    
    if status_filter != "All":
        current_date = pd.Timestamp.now()
        if status_filter == "Active":
            filtered_df = filtered_df[
                (filtered_df['monitor_enddate'].isna()) | 
                (filtered_df['monitor_enddate'] >= current_date)
            ]
        else:  # Ended
            filtered_df = filtered_df[
                (filtered_df['monitor_enddate'].notna()) & 
                (filtered_df['monitor_enddate'] < current_date)
            ]
    
    if filtered_df.empty:
        st.warning("No recommendations match the selected filters.")
        return
    
    # Get price data for each recommendation
    st.markdown("### 📈 Performance Analysis")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    
    for idx, row in filtered_df.iterrows():
        progress = (idx + 1) / len(filtered_df)
        progress_bar.progress(progress)
        status_text.text(f"Processing {row['ticker']} ({idx + 1}/{len(filtered_df)})...")
        
        # Get start price
        start_date, start_price = get_price_for_date(
            row['ticker'], row['monitor_startdate'], row['market']
        )
        
        # Get current price
        current_date, current_price = get_current_price(row['ticker'], row['market'])
        
        # Calculate performance
        if start_price is not None and current_price is not None:
            performance_pct = ((current_price - start_price) / start_price) * 100
            performance_abs = current_price - start_price
        else:
            performance_pct = None
            performance_abs = None
        
        # Status determination
        current_timestamp = pd.Timestamp.now()
        if pd.isna(row['monitor_enddate']) or row['monitor_enddate'] >= current_timestamp:
            status = "🟢 Active"
        else:
            status = "🔴 Ended"
        
        results.append({
            'Ticker': row['ticker'],
            'Company': row['company_name'],
            'Market': row['market'],
            'Status': status,
            'Monitor Start': row['monitor_startdate'].strftime('%Y-%m-%d'),
            'Monitor End': row['monitor_enddate'].strftime('%Y-%m-%d') if pd.notna(row['monitor_enddate']) else 'Ongoing',
            'Start Date (Actual)': start_date.strftime('%Y-%m-%d') if start_date else 'N/A',
            'Start Price': f"${start_price:.2f}" if start_price else 'N/A',
            'Current Date': current_date.strftime('%Y-%m-%d') if current_date else 'N/A',
            'Current Price': f"${current_price:.2f}" if current_price else 'N/A',
            'Performance (%)': f"{performance_pct:.2f}%" if performance_pct is not None else 'N/A',
            'Performance ($)': f"${performance_abs:.2f}" if performance_abs is not None else 'N/A',
            'Comments': row['comments'] or 'None',
            '_performance_num': performance_pct  # For sorting
        })
    
    progress_bar.empty()
    status_text.empty()
    
    # Convert to DataFrame for display
    results_df = pd.DataFrame(results)
    
    # Apply sorting
    if sort_by == "Monitor Start Date":
        results_df = results_df.sort_values('Monitor Start', ascending=False)
    elif sort_by == "Company Name":
        results_df = results_df.sort_values('Company')
    elif sort_by == "Performance %":
        results_df = results_df.sort_values('_performance_num', ascending=False, na_position='last')
    
    # Display summary statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_recos = len(results_df)
        st.metric("📊 Total Recommendations", total_recos)
    
    with col2:
        active_recos = len([r for r in results if "🟢" in r['Status']])
        st.metric("🟢 Active", active_recos)
    
    with col3:
        valid_performances = [r['_performance_num'] for r in results if r['_performance_num'] is not None]
        avg_performance = sum(valid_performances) / len(valid_performances) if valid_performances else 0
        st.metric("📈 Avg Performance", f"{avg_performance:.2f}%")
    
    with col4:
        positive_count = len([p for p in valid_performances if p > 0])
        win_rate = (positive_count / len(valid_performances) * 100) if valid_performances else 0
        st.metric("🎯 Win Rate", f"{win_rate:.1f}%")
    
    # Display the results table
    st.markdown("### 📋 Detailed Tracking Results")
    
    # Remove the sorting column for display
    display_df = results_df.drop('_performance_num', axis=1)
    
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600
    )
    
    # Download button
    csv_data = display_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Tracking Report (CSV)",
        data=csv_data,
        file_name=f"recommendation_tracking_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="download_reco_tracking"
    )
    
    # Performance visualization
    st.markdown("### 📊 Performance Visualization")
    
    if valid_performances:
        # Create performance chart
        chart_data = []
        for result in results:
            if result['_performance_num'] is not None:
                chart_data.append({
                    'Ticker': result['Ticker'],
                    'Performance (%)': result['_performance_num'],
                    'Market': result['Market'],
                    'Status': result['Status']
                })
        
        if chart_data:
            chart_df = pd.DataFrame(chart_data)
            
            fig = px.bar(
                chart_df,
                x='Ticker',
                y='Performance (%)',
                color='Market',
                title='📈 Recommendation Performance by Ticker',
                hover_data=['Status'],
                color_discrete_map={'NSE 500': '#1f77b4', 'NASDAQ 100': '#ff7f0e'}
            )
            
            # Add horizontal line at 0%
            fig.add_hline(y=0, line_dash="dash", line_color="red", 
                         annotation_text="Break-even line")
            
            fig.update_layout(
                height=500,
                xaxis_title="Ticker",
                yaxis_title="Performance (%)",
                xaxis={'tickangle': 45}
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info("No performance data available for visualization.")


def show_forex_ml_predictions_page():
    """Show Forex ML Predictions page with separate filters"""
    st.title("💱 Forex ML Predictions Dashboard")
    
    st.markdown("""
    ### 🌍 Advanced Machine Learning Predictions for Forex Markets
    
    This page provides ML-powered insights using dedicated prediction models trained on Forex data.
    
    ---
    """)
    
    # Separate filters for this page
    st.sidebar.header("💱 Forex ML Filters")
    
    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        date_type = st.selectbox(
            "📅 Date Selection Type:",
            ["Date Range", "Single Date"],
            key="forex_ml_date_type"
        )
    
    if date_type == "Single Date":
        selected_date = st.date_input(
            "📅 Select Date:",
            value=datetime.now().date(),
            key="forex_ml_single_date"
        )
        start_date = end_date = selected_date
    else:
        with col2:
            date_range = st.date_input(
                "📅 Select Date Range:",
                value=[datetime.now().date() - pd.Timedelta(days=30), datetime.now().date()],
                key="forex_ml_date_range"
            )
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = date_range[0]
    
    # Currency pair filter
    currency_pair_input = st.text_input(
        "💰 Currency Pair (optional):",
        placeholder="e.g., EUR/USD, GBP/USD, USD/JPY, EUR, USD",
        help="Enter full pair (EUR/USD) or partial match (EUR, USD). Uses LIKE search.",
        key="forex_ml_currency_pair"
    ).upper().strip()
    
    # Load data button
    if st.button("💱 Load Forex ML Data", key="load_forex_ml"):
        with st.spinner("Loading Forex ML prediction data..."):
            # Show filter information
            if currency_pair_input:
                st.info(f"🔍 Filtering data for currency pair: **{currency_pair_input}**")
            else:
                st.info("📊 Loading all available forex data...")
            
            try:
                # Query forex_daily_summary
                summary_query = "SELECT * FROM dbo.forex_daily_summary ORDER BY 1 DESC"
                
                summary_df = execute_query_safe(summary_query)
                
                # Apply currency pair filtering after loading data if filter is provided
                if not summary_df.empty and currency_pair_input:
                    # Find the currency pair column (check various possible names)
                    currency_col = None
                    for col in summary_df.columns:
                        if any(keyword in col.lower() for keyword in ['currency', 'pair', 'symbol']):
                            currency_col = col
                            break
                    
                    if currency_col:
                        # Apply filter using pandas
                        summary_df = summary_df[summary_df[currency_col].str.contains(currency_pair_input, case=False, na=False)]
                        st.success(f"✅ Filtered {currency_col} column for: {currency_pair_input}")
                    else:
                        st.warning("⚠️ Could not find currency pair column for filtering")
                
                # Display column information for debugging
                if not summary_df.empty:
                    st.info(f"Available columns in forex_daily_summary: {', '.join(summary_df.columns.tolist())}")
                
                # Query forex_ml_predictions
                predictions_query = "SELECT * FROM dbo.forex_ml_predictions ORDER BY 1 DESC"
                
                predictions_df = execute_query_safe(predictions_query)
                
                # Apply currency pair filtering after loading data if filter is provided
                if not predictions_df.empty and currency_pair_input:
                    # Find the currency pair column (check various possible names)
                    currency_col = None
                    for col in predictions_df.columns:
                        if any(keyword in col.lower() for keyword in ['currency', 'pair', 'symbol']):
                            currency_col = col
                            break
                    
                    if currency_col:
                        # Apply filter using pandas
                        predictions_df = predictions_df[predictions_df[currency_col].str.contains(currency_pair_input, case=False, na=False)]
                        st.success(f"✅ Filtered {currency_col} column for: {currency_pair_input}")
                    else:
                        st.warning("⚠️ Could not find currency pair column for filtering")
                
                # Display column information for debugging
                if not predictions_df.empty:
                    st.info(f"Available columns in forex_ml_predictions: {', '.join(predictions_df.columns.tolist())}")
                
                # Query forex_model_performance
                performance_query = "SELECT * FROM dbo.forex_model_performance ORDER BY 1 DESC"
                
                performance_df = execute_query_safe(performance_query)
                
                # Apply currency pair filtering after loading data if filter is provided
                if not performance_df.empty and currency_pair_input:
                    # Find the currency pair column (check various possible names)
                    currency_col = None
                    for col in performance_df.columns:
                        if any(keyword in col.lower() for keyword in ['currency', 'pair', 'symbol']):
                            currency_col = col
                            break
                    
                    if currency_col:
                        # Apply filter using pandas
                        performance_df = performance_df[performance_df[currency_col].str.contains(currency_pair_input, case=False, na=False)]
                        st.success(f"✅ Filtered {currency_col} column for: {currency_pair_input}")
                    else:
                        st.warning("⚠️ Could not find currency pair column for filtering")
                
                # Display column information for debugging
                if not performance_df.empty:
                    st.info(f"Available columns in forex_model_performance: {', '.join(performance_df.columns.tolist())}")
                # Display results
                if not summary_df.empty:
                    st.markdown("### 📊 Forex Daily Summary")
                    
                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Records", len(summary_df))
                    with col2:
                        unique_pairs = summary_df['currency_pair'].nunique() if 'currency_pair' in summary_df.columns else 0
                        st.metric("Currency Pairs", unique_pairs)
                    with col3:
                        if 'daily_return' in summary_df.columns:
                            avg_return = summary_df['daily_return'].mean()
                            st.metric("Avg Daily Return", f"{avg_return:.4f}%")
                    with col4:
                        if 'volatility' in summary_df.columns:
                            avg_volatility = summary_df['volatility'].mean()
                            st.metric("Avg Volatility", f"{avg_volatility:.4f}")
                    
                    # Display summary table with enhanced formatting
                    # Create dynamic column config based on available columns
                    column_config = {}
                    if any(col in summary_df.columns for col in ['trading_date', 'date', 'Date', 'TradeDate']):
                        date_col = next((col for col in ['trading_date', 'date', 'Date', 'TradeDate'] if col in summary_df.columns), None)
                        if date_col:
                            column_config[date_col] = st.column_config.DateColumn('📅 Date')
                    
                    if 'currency_pair' in summary_df.columns:
                        column_config['currency_pair'] = st.column_config.TextColumn('💱 Currency Pair')
                    elif 'CurrencyPair' in summary_df.columns:
                        column_config['CurrencyPair'] = st.column_config.TextColumn('💱 Currency Pair')
                    
                    st.dataframe(
                        summary_df,
                        use_container_width=True,
                        column_config=column_config
                    )
                    
                    # Export summary
                    csv_summary = summary_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Summary (CSV)",
                        data=csv_summary,
                        file_name=f"forex_daily_summary_{start_date}_{end_date}.csv",
                        mime="text/csv",
                        key="download_forex_summary"
                    )
                else:
                    st.warning("No forex daily summary data found for the selected criteria.")
                
                # ML Predictions Section
                if not predictions_df.empty:
                    st.markdown("### 🤖 Forex ML Predictions")
                    
                    # Predictions metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Predictions", len(predictions_df))
                    with col2:
                        if 'prediction_direction' in predictions_df.columns:
                            bullish_predictions = len(predictions_df[predictions_df['prediction_direction'].str.contains('UP|BUY|BULL', case=False, na=False)])
                            st.metric("Bullish Predictions", bullish_predictions)
                    with col3:
                        if 'confidence_score' in predictions_df.columns:
                            avg_confidence = predictions_df['confidence_score'].mean()
                            st.metric("Avg Confidence", f"{avg_confidence:.2f}%")
                    with col4:
                        if 'predicted_return' in predictions_df.columns:
                            avg_predicted_return = predictions_df['predicted_return'].mean()
                            st.metric("Avg Predicted Return", f"{avg_predicted_return:.4f}%")
                    
                    # Create dynamic column config for predictions
                    pred_column_config = {}
                    if any(col in predictions_df.columns for col in ['prediction_date', 'date', 'Date', 'PredictionDate']):
                        date_col = next((col for col in ['prediction_date', 'date', 'Date', 'PredictionDate'] if col in predictions_df.columns), None)
                        if date_col:
                            pred_column_config[date_col] = st.column_config.DateColumn('📅 Date')
                    
                    if 'currency_pair' in predictions_df.columns:
                        pred_column_config['currency_pair'] = st.column_config.TextColumn('💱 Currency Pair')
                    elif 'CurrencyPair' in predictions_df.columns:
                        pred_column_config['CurrencyPair'] = st.column_config.TextColumn('💱 Currency Pair')
                    
                    st.dataframe(
                        predictions_df,
                        use_container_width=True,
                        column_config=pred_column_config
                    )
                    
                    # Export predictions
                    csv_predictions = predictions_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Predictions (CSV)",
                        data=csv_predictions,
                        file_name=f"forex_ml_predictions_{start_date}_{end_date}.csv",
                        mime="text/csv",
                        key="download_forex_predictions"
                    )
                else:
                    st.info("No forex ML predictions data found for the selected criteria.")
                
                # Model Performance Section
                if not performance_df.empty:
                    st.markdown("### 📈 Model Performance Analysis")
                    
                    # Performance metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if 'accuracy_score' in performance_df.columns:
                            avg_accuracy = performance_df['accuracy_score'].mean()
                            st.metric("Avg Accuracy", f"{avg_accuracy:.2f}%")
                    with col2:
                        if 'precision_score' in performance_df.columns:
                            avg_precision = performance_df['precision_score'].mean()
                            st.metric("Avg Precision", f"{avg_precision:.2f}%")
                    with col3:
                        if 'recall_score' in performance_df.columns:
                            avg_recall = performance_df['recall_score'].mean()
                            st.metric("Avg Recall", f"{avg_recall:.2f}%")
                    with col4:
                        if 'f1_score' in performance_df.columns:
                            avg_f1 = performance_df['f1_score'].mean()
                            st.metric("Avg F1 Score", f"{avg_f1:.2f}%")
                    
                    # Create dynamic column config for performance
                    perf_column_config = {}
                    if any(col in performance_df.columns for col in ['evaluation_date', 'date', 'Date', 'EvaluationDate']):
                        date_col = next((col for col in ['evaluation_date', 'date', 'Date', 'EvaluationDate'] if col in performance_df.columns), None)
                        if date_col:
                            perf_column_config[date_col] = st.column_config.DateColumn('📅 Date')
                    
                    if 'currency_pair' in performance_df.columns:
                        perf_column_config['currency_pair'] = st.column_config.TextColumn('💱 Currency Pair')
                    elif 'CurrencyPair' in performance_df.columns:
                        perf_column_config['CurrencyPair'] = st.column_config.TextColumn('💱 Currency Pair')
                    
                    st.dataframe(
                        performance_df,
                        use_container_width=True,
                        column_config=perf_column_config
                    )
                    
                    # Export performance
                    csv_performance = performance_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Performance (CSV)",
                        data=csv_performance,
                        file_name=f"forex_model_performance_{start_date}_{end_date}.csv",
                        mime="text/csv",
                        key="download_forex_performance"
                    )
                else:
                    st.info("No forex model performance data found for the selected criteria.")
                
            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
    
    # Information section
    with st.expander("ℹ️ About Forex ML Predictions", expanded=False):
        st.markdown("""
        **Data Sources:**
        - `dbo.forex_daily_summary`: Daily market summary and statistics
        - `dbo.forex_ml_predictions`: ML-powered forex predictions and signals
        - `dbo.forex_model_performance`: Model accuracy and performance metrics
        
        **Features:**
        - Date range or single date filtering
        - Currency pair-specific analysis
        - Comprehensive ML performance metrics
        - Downloadable reports in CSV format
        - Real-time forex market insights
        """)

def show_master_data_editor():
    """Master Data Editor - View and edit NSE 500, NASDAQ 100, and Forex master data"""
    st.markdown("""
    # 📊 Master Data Editor
    
    ### View and edit master data for NSE 500 and NASDAQ 100 stocks
    
    Edit ticker information, recommendation dates, and tracking parameters directly.
    
    ---
    """)
    
    # Market selector
    market = st.selectbox("Select Market to Edit", 
                          ["NSE 500", "NASDAQ 100"], 
                          key="master_data_market")
    
    # Fetch master data based on market
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if market == "NSE 500":
            table_name = "dbo.nse_500"
        else:
            table_name = "dbo.NASDAQ_top100"
        
        query = f"SELECT * FROM {table_name} ORDER BY ticker"
        
        with st.spinner(f"Loading {market} master data..."):
            df = pd.read_sql(query, conn)
        
        conn.close()
        
        if df.empty:
            st.warning(f"No data found in {table_name}")
            return
        
        st.success(f"✅ Loaded {len(df)} records from {market}")
        
        # Display editable dataframe
        st.markdown("### Edit Master Data")
        st.info("💡 Make changes directly in the table below. Click 'Save Changes' to update the database.")
        
        # Use st.data_editor for inline editing
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",  # Allow adding/deleting rows
            key=f"master_data_editor_{market}"
        )
        
        # Save button
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if st.button("💾 Save Changes", type="primary"):
                conn = None
                try:
                    # Create connection with manual transaction control
                    connection_string = get_connection_pool()
                    conn = pyodbc.connect(connection_string)
                    conn.autocommit = False  # Disable autocommit to use transactions
                    cursor = conn.cursor()
                    
                    # Delete all and reinsert (within transaction)
                    cursor.execute(f"DELETE FROM {table_name}")
                    
                    # Insert edited data with proper date handling
                    for _, row in edited_df.iterrows():
                        # Convert datetime columns to proper date format
                        row_values = []
                        for col in edited_df.columns:
                            value = row[col]
                            # Handle datetime/date conversion
                            if pd.api.types.is_datetime64_any_dtype(edited_df[col]) and pd.notna(value):
                                # Convert to date only (remove time component)
                                if hasattr(value, 'date'):
                                    row_values.append(value.date())
                                else:
                                    row_values.append(value)
                            elif pd.isna(value):
                                row_values.append(None)
                            else:
                                row_values.append(value)
                        
                        columns = ', '.join(edited_df.columns)
                        placeholders = ', '.join(['?'] * len(edited_df.columns))
                        insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                        cursor.execute(insert_query, tuple(row_values))
                    
                    # Commit transaction only if everything succeeds
                    conn.commit()
                    conn.close()
                    
                    st.success(f"✅ Successfully saved {len(edited_df)} records to {table_name}!")
                    st.balloons()
                    st.rerun()  # Refresh to show updated data
                except Exception as e:
                    # Rollback transaction on error to prevent data loss
                    if conn:
                        try:
                            conn.rollback()
                            conn.close()
                            st.error(f"❌ Error saving data: {e}")
                            st.warning("⚠️ Changes were rolled back. Your original data is safe.")
                        except:
                            st.error(f"❌ Error saving data: {e}")
                    else:
                        st.error(f"❌ Error saving data: {e}")
        
        with col2:
            if st.button("🔄 Refresh Data"):
                st.rerun()
        
        # Show statistics
        st.markdown("### Data Statistics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records", len(edited_df))
        with col2:
            if 'monitor_startdate' in edited_df.columns:
                monitored = edited_df['monitor_startdate'].notna().sum()
                st.metric("Monitored Tickers", monitored)
        with col3:
            if 'ticker' in edited_df.columns:
                st.metric("Unique Tickers", edited_df['ticker'].nunique())
        
    except Exception as e:
        st.error(f"❌ Error loading master data: {e}")
        st.info("Please check your database connection and table structure.")

def show_portfolio_tracker():
    """Portfolio Tracker - Track personal buy/sell transactions"""
    st.markdown("""
    # 💼 My Portfolio Tracker
    
    ### Track your personal stock portfolio with buy/sell transactions
    
    Monitor your holdings, calculate P&L, and track performance across markets.
    
    ---
    """)
    
    # Create portfolio table if not exists
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create portfolio table if not exists
        create_table_query = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='portfolio_tracker' AND xtype='U')
        CREATE TABLE dbo.portfolio_tracker (
            id INT IDENTITY(1,1) PRIMARY KEY,
            ticker VARCHAR(50) NOT NULL,
            market VARCHAR(20) NOT NULL,
            buy_date DATE,
            buy_price FLOAT,
            buy_qty INT,
            sell_date DATE,
            sell_price FLOAT,
            sell_qty INT,
            status VARCHAR(20) DEFAULT 'HOLDING',
            notes VARCHAR(500)
        )
        """
        cursor.execute(create_table_query)
        conn.commit()
        
        # Fetch portfolio data
        query = """
        SELECT 
            id,
            ticker,
            market,
            buy_date,
            buy_price,
            buy_qty,
            sell_date,
            sell_price,
            sell_qty,
            status,
            notes
        FROM dbo.portfolio_tracker
        ORDER BY buy_date DESC
        """
        
        portfolio_df = pd.read_sql(query, conn)
        
        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Current Holdings", "➕ Add Transaction", "📜 Transaction History"])
        
        with tab1:
            st.markdown("### Current Holdings")
            
            if portfolio_df.empty:
                st.info("📋 No transactions recorded yet. Add your first transaction in the 'Add Transaction' tab.")
            else:
                # Filter for active holdings
                holdings = portfolio_df[portfolio_df['status'] == 'HOLDING'].copy()
                
                if holdings.empty:
                    st.info("📋 No active holdings. All positions are closed.")
                else:
                    # Get current prices for holdings
                    st.markdown(f"**Total Holdings:** {len(holdings)} positions")
                    
                    # Calculate metrics for each holding
                    for _, holding in holdings.iterrows():
                        with st.expander(f"📈 {holding['ticker']} ({holding['market']})"):
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Buy Price", f"${holding['buy_price']:.2f}")
                            with col2:
                                st.metric("Quantity", f"{holding['buy_qty']}")
                            with col3:
                                investment = holding['buy_price'] * holding['buy_qty']
                                st.metric("Investment", f"${investment:.2f}")
                            with col4:
                                st.metric("Buy Date", holding['buy_date'].strftime('%Y-%m-%d') if pd.notna(holding['buy_date']) else "N/A")
                            
                            if holding['notes']:
                                st.info(f"📝 Notes: {holding['notes']}")
        
        with tab2:
            st.markdown("### Add New Transaction")
            
            with st.form("add_transaction_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    ticker = st.text_input("Ticker Symbol*", placeholder="e.g., AAPL, RELIANCE")
                    market = st.selectbox("Market*", ["NSE", "NASDAQ", "Forex"])
                    buy_date = st.date_input("Buy Date*")
                    buy_price = st.number_input("Buy Price*", min_value=0.01, step=0.01)
                    buy_qty = st.number_input("Quantity*", min_value=1, step=1, value=1)
                
                with col2:
                    transaction_type = st.radio("Transaction Type", ["Buy Only", "Buy & Sell"])
                    
                    if transaction_type == "Buy & Sell":
                        sell_date = st.date_input("Sell Date")
                        sell_price = st.number_input("Sell Price", min_value=0.01, step=0.01)
                        sell_qty = st.number_input("Sell Quantity", min_value=1, step=1, value=buy_qty)
                        status = "SOLD"
                    else:
                        sell_date = None
                        sell_price = None
                        sell_qty = None
                        status = "HOLDING"
                    
                    notes = st.text_area("Notes (Optional)", placeholder="Add any notes about this transaction")
                
                submitted = st.form_submit_button("💾 Add Transaction", type="primary")
                
                if submitted:
                    if not ticker or not market or not buy_date or not buy_price or not buy_qty:
                        st.error("❌ Please fill all required fields marked with *")
                    else:
                        try:
                            insert_query = """
                            INSERT INTO dbo.portfolio_tracker 
                            (ticker, market, buy_date, buy_price, buy_qty, sell_date, sell_price, sell_qty, status, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """
                            cursor.execute(insert_query, 
                                         (ticker.upper(), market, buy_date, buy_price, buy_qty, 
                                          sell_date, sell_price, sell_qty, status, notes))
                            conn.commit()
                            
                            # Store success message in session state
                            st.session_state.portfolio_success = f"✅ Successfully added {status} transaction for {ticker.upper()}!"
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error adding transaction: {e}")
            
            # Display success message if it exists
            if 'portfolio_success' in st.session_state:
                st.success(st.session_state.portfolio_success)
                st.balloons()
                # Clear the message after displaying
                del st.session_state.portfolio_success
        
        with tab3:
            st.markdown("### Transaction History")
            
            if portfolio_df.empty:
                st.info("📋 No transaction history yet.")
            else:
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                
                total_transactions = len(portfolio_df)
                active_holdings = len(portfolio_df[portfolio_df['status'] == 'HOLDING'])
                closed_positions = len(portfolio_df[portfolio_df['status'] == 'SOLD'])
                
                with col1:
                    st.metric("Total Transactions", total_transactions)
                with col2:
                    st.metric("Active Holdings", active_holdings)
                with col3:
                    st.metric("Closed Positions", closed_positions)
                with col4:
                    total_investment = (portfolio_df['buy_price'] * portfolio_df['buy_qty']).sum()
                    st.metric("Total Investment", f"${total_investment:.2f}")
                
                # Display editable transaction history
                st.markdown("---")
                st.markdown("#### Edit Transactions")
                
                # Clear instructions
                with st.expander("💡 How to Edit/Delete Transactions", expanded=False):
                    st.markdown("""
                    **Editing Transactions:**
                    1. Click on any cell in the table below to edit its value
                    2. Click the **Save Changes** button to update the database
                    
                    **Deleting Transactions:**
                    1. Hover over the row number (leftmost column)
                    2. Click the **trash can icon (🗑️)** that appears
                    3. The row will be marked for deletion
                    4. Click **Save Changes** to permanently delete from database
                    
                    **Adding New Transactions:**
                    - Use the "Add Transaction" tab for better data validation
                    - Or click the **+** icon at the bottom of the table to add a row manually
                    
                    ⚠️ **Important**: Changes are not saved until you click the "Save Changes" button!
                    """)
                
                # Make dataframe editable
                edited_portfolio_df = st.data_editor(
                    portfolio_df,
                    use_container_width=True,
                    num_rows="dynamic",  # Allow adding/deleting rows
                    column_config={
                        "id": st.column_config.NumberColumn("ID", width="small", disabled=True),
                        "ticker": st.column_config.TextColumn("Ticker", width="medium"),
                        "market": st.column_config.SelectboxColumn("Market", width="small", options=["NSE", "NASDAQ", "Forex"]),
                        "buy_date": st.column_config.DateColumn("Buy Date"),
                        "buy_price": st.column_config.NumberColumn("Buy Price", format="$%.2f"),
                        "buy_qty": st.column_config.NumberColumn("Buy Qty"),
                        "sell_date": st.column_config.DateColumn("Sell Date"),
                        "sell_price": st.column_config.NumberColumn("Sell Price", format="$%.2f"),
                        "sell_qty": st.column_config.NumberColumn("Sell Qty"),
                        "status": st.column_config.SelectboxColumn("Status", width="small", options=["HOLDING", "SOLD"]),
                        "notes": st.column_config.TextColumn("Notes", width="large")
                    },
                    key="portfolio_editor"
                )
                
                # Show changes detected
                if len(edited_portfolio_df) != len(portfolio_df):
                    rows_added = max(0, len(edited_portfolio_df) - len(portfolio_df))
                    rows_deleted = max(0, len(portfolio_df) - len(edited_portfolio_df))
                    
                    if rows_deleted > 0:
                        st.warning(f"⚠️ {rows_deleted} row(s) will be deleted. Click 'Save Changes' to confirm.")
                    if rows_added > 0:
                        st.info(f"ℹ️ {rows_added} new row(s) added. Click 'Save Changes' to save.")
                
                # Bulk delete option
                st.markdown("---")
                st.markdown("#### 🗑️ Bulk Delete Transactions")
                
                with st.expander("Delete Multiple Transactions", expanded=False):
                    st.warning("⚠️ This will permanently delete selected transactions from the database!")
                    
                    # Filter options for bulk delete
                    delete_col1, delete_col2 = st.columns(2)
                    
                    with delete_col1:
                        delete_by = st.radio(
                            "Delete by:",
                            ["Select by Ticker", "Select by Status", "Select by Date Range"],
                            key="delete_by_option"
                        )
                    
                    with delete_col2:
                        if delete_by == "Select by Ticker":
                            tickers_to_delete = st.multiselect(
                                "Select Tickers to Delete",
                                options=sorted(portfolio_df['ticker'].unique().tolist()),
                                key="tickers_to_delete"
                            )
                            if tickers_to_delete and st.button("🗑️ Delete Selected Tickers", type="secondary"):
                                try:
                                    ids_to_delete = portfolio_df[portfolio_df['ticker'].isin(tickers_to_delete)]['id'].tolist()
                                    if ids_to_delete:
                                        placeholders = ','.join(['?' for _ in ids_to_delete])
                                        delete_query = f"DELETE FROM dbo.portfolio_tracker WHERE id IN ({placeholders})"
                                        cursor.execute(delete_query, ids_to_delete)
                                        conn.commit()
                                        st.session_state.portfolio_success = f"✅ Deleted {len(ids_to_delete)} transaction(s) for tickers: {', '.join(tickers_to_delete)}"
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error deleting transactions: {e}")
                        
                        elif delete_by == "Select by Status":
                            status_to_delete = st.selectbox(
                                "Select Status to Delete",
                                options=["HOLDING", "SOLD"],
                                key="status_to_delete"
                            )
                            matching_count = len(portfolio_df[portfolio_df['status'] == status_to_delete])
                            st.info(f"This will delete {matching_count} transaction(s) with status '{status_to_delete}'")
                            
                            if st.button(f"🗑️ Delete All {status_to_delete} Transactions", type="secondary"):
                                try:
                                    ids_to_delete = portfolio_df[portfolio_df['status'] == status_to_delete]['id'].tolist()
                                    if ids_to_delete:
                                        placeholders = ','.join(['?' for _ in ids_to_delete])
                                        delete_query = f"DELETE FROM dbo.portfolio_tracker WHERE id IN ({placeholders})"
                                        cursor.execute(delete_query, ids_to_delete)
                                        conn.commit()
                                        st.session_state.portfolio_success = f"✅ Deleted {len(ids_to_delete)} {status_to_delete} transaction(s)"
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error deleting transactions: {e}")
                        
                        elif delete_by == "Select by Date Range":
                            date_col1, date_col2 = st.columns(2)
                            with date_col1:
                                start_date = st.date_input("From Date", key="delete_start_date")
                            with date_col2:
                                end_date = st.date_input("To Date", key="delete_end_date")
                            
                            matching_count = len(portfolio_df[
                                (portfolio_df['buy_date'] >= pd.Timestamp(start_date)) & 
                                (portfolio_df['buy_date'] <= pd.Timestamp(end_date))
                            ])
                            st.info(f"This will delete {matching_count} transaction(s) between {start_date} and {end_date}")
                            
                            if st.button("🗑️ Delete Transactions in Date Range", type="secondary"):
                                try:
                                    ids_to_delete = portfolio_df[
                                        (portfolio_df['buy_date'] >= pd.Timestamp(start_date)) & 
                                        (portfolio_df['buy_date'] <= pd.Timestamp(end_date))
                                    ]['id'].tolist()
                                    
                                    if ids_to_delete:
                                        placeholders = ','.join(['?' for _ in ids_to_delete])
                                        delete_query = f"DELETE FROM dbo.portfolio_tracker WHERE id IN ({placeholders})"
                                        cursor.execute(delete_query, ids_to_delete)
                                        conn.commit()
                                        st.session_state.portfolio_success = f"✅ Deleted {len(ids_to_delete)} transaction(s) from date range"
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error deleting transactions: {e}")
                
                # Save and Download buttons
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 1, 4])
                with col1:
                    if st.button("💾 Save Changes", type="primary", key="save_portfolio"):
                        try:
                            # Create connection with manual transaction control
                            connection_string = get_connection_pool()
                            conn_update = pyodbc.connect(connection_string)
                            conn_update.autocommit = False
                            cursor_update = conn_update.cursor()
                            
                            # Delete all and reinsert (simple approach)
                            cursor_update.execute("DELETE FROM dbo.portfolio_tracker")
                            
                            # Insert edited data with proper date handling
                            for _, row in edited_portfolio_df.iterrows():
                                # Handle date conversions
                                buy_date_val = row['buy_date'].date() if pd.notna(row['buy_date']) and hasattr(row['buy_date'], 'date') else row['buy_date'] if pd.notna(row['buy_date']) else None
                                sell_date_val = row['sell_date'].date() if pd.notna(row['sell_date']) and hasattr(row['sell_date'], 'date') else row['sell_date'] if pd.notna(row['sell_date']) else None
                                
                                insert_query = """
                                INSERT INTO dbo.portfolio_tracker 
                                (ticker, market, buy_date, buy_price, buy_qty, sell_date, sell_price, sell_qty, status, notes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """
                                cursor_update.execute(insert_query, 
                                    (row['ticker'], row['market'], buy_date_val, 
                                     row['buy_price'] if pd.notna(row['buy_price']) else None, 
                                     row['buy_qty'] if pd.notna(row['buy_qty']) else None,
                                     sell_date_val, 
                                     row['sell_price'] if pd.notna(row['sell_price']) else None, 
                                     row['sell_qty'] if pd.notna(row['sell_qty']) else None,
                                     row['status'], 
                                     row['notes'] if pd.notna(row['notes']) else None))
                            
                            conn_update.commit()
                            conn_update.close()
                            
                            st.session_state.portfolio_success = f"✅ Successfully updated {len(edited_portfolio_df)} portfolio transactions!"
                            st.rerun()
                        except Exception as e:
                            if conn_update:
                                try:
                                    conn_update.rollback()
                                    conn_update.close()
                                except:
                                    pass
                            st.error(f"❌ Error saving changes: {e}")
                            st.warning("⚠️ Changes were rolled back. Your data is safe.")
                
                with col2:
                    if st.button("🔄 Refresh Data"):
                        st.rerun()
                
                with col3:
                    # Download option
                    st.download_button(
                        label="📥 Download Portfolio History (CSV)",
                        data=edited_portfolio_df.to_csv(index=False),
                        file_name=f"portfolio_history_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
        
        conn.close()
        
    except Exception as e:
        st.error(f"❌ Error loading portfolio tracker: {e}")
        st.info("Please check your database connection.")


def show_family_assets_page():
    """For Family - Track family assets and liabilities"""
    st.markdown("""
    # 👨‍👩‍👧‍👦 For Family - Assets & Liabilities Tracker
    
    ### Keep track of all family assets and liabilities in one place
    
    Document important financial information for your family's future planning.
    
    ---
    """)
    
    # Create family assets table if not exists
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create family_assets table if not exists
        create_table_query = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='family_assets' AND xtype='U')
        CREATE TABLE dbo.family_assets (
            id INT IDENTITY(1,1) PRIMARY KEY,
            asset_type VARCHAR(50) NOT NULL,
            item_name VARCHAR(200) NOT NULL,
            category VARCHAR(100),
            location_place VARCHAR(500),
            purchase_date DATE,
            purchase_value FLOAT,
            sold_date DATE,
            sold_value FLOAT,
            current_status VARCHAR(50) DEFAULT 'ACTIVE',
            notes VARCHAR(1000),
            created_date DATETIME DEFAULT GETDATE()
        )
        """
        cursor.execute(create_table_query)
        conn.commit()
        
        # Fetch family assets data
        query = """
        SELECT 
            id,
            asset_type,
            item_name,
            category,
            location_place,
            purchase_date,
            purchase_value,
            sold_date,
            sold_value,
            current_status,
            notes,
            created_date
        FROM dbo.family_assets
        ORDER BY created_date DESC
        """
        
        assets_df = pd.read_sql(query, conn)
        
        # Tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "➕ Add Asset/Liability", "📋 All Records", "📈 Summary"])
        
        with tab1:
            st.markdown("### Family Assets & Liabilities Overview")
            
            if assets_df.empty:
                st.info("📋 No records yet. Add your first asset or liability in the 'Add Asset/Liability' tab.")
            else:
                # Split into assets and liabilities
                assets_only = assets_df[assets_df['asset_type'] == 'ASSET'].copy()
                liabilities_only = assets_df[assets_df['asset_type'] == 'LIABILITY'].copy()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 💰 Assets")
                    if assets_only.empty:
                        st.info("No assets recorded yet.")
                    else:
                        active_assets = assets_only[assets_only['current_status'] == 'ACTIVE']
                        total_asset_value = active_assets['purchase_value'].sum() if not active_assets.empty else 0
                        st.metric("Total Active Assets", len(active_assets))
                        st.metric("Total Value", f"${total_asset_value:,.2f}")
                        
                        st.markdown("**Recent Assets:**")
                        for _, asset in assets_only.head(5).iterrows():
                            status_emoji = "✅" if asset['current_status'] == 'ACTIVE' else "📦"
                            st.markdown(f"- {status_emoji} **{asset['item_name']}** ({asset['category']}) - ${asset['purchase_value']:,.2f}")
                
                with col2:
                    st.markdown("#### 📉 Liabilities")
                    if liabilities_only.empty:
                        st.info("No liabilities recorded yet.")
                    else:
                        active_liabilities = liabilities_only[liabilities_only['current_status'] == 'ACTIVE']
                        total_liability_value = active_liabilities['purchase_value'].sum() if not active_liabilities.empty else 0
                        st.metric("Total Active Liabilities", len(active_liabilities))
                        st.metric("Total Amount", f"${total_liability_value:,.2f}")
                        
                        st.markdown("**Recent Liabilities:**")
                        for _, liability in liabilities_only.head(5).iterrows():
                            status_emoji = "⚠️" if liability['current_status'] == 'ACTIVE' else "✅"
                            st.markdown(f"- {status_emoji} **{liability['item_name']}** ({liability['category']}) - ${liability['purchase_value']:,.2f}")
                
                # Net Worth
                st.markdown("---")
                if not assets_only.empty or not liabilities_only.empty:
                    active_assets = assets_df[assets_df['asset_type'] == 'ASSET'][assets_df['current_status'] == 'ACTIVE']
                    active_liabilities = assets_df[assets_df['asset_type'] == 'LIABILITY'][assets_df['current_status'] == 'ACTIVE']
                    
                    total_assets = active_assets['purchase_value'].sum() if not active_assets.empty else 0
                    total_liabilities = active_liabilities['purchase_value'].sum() if not active_liabilities.empty else 0
                    net_worth = total_assets - total_liabilities
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Assets", f"${total_assets:,.2f}")
                    with col2:
                        st.metric("Total Liabilities", f"${total_liabilities:,.2f}")
                    with col3:
                        st.metric("Net Worth", f"${net_worth:,.2f}", delta=None if net_worth >= 0 else "Negative")
        
        with tab2:
            st.markdown("### Add New Asset or Liability")
            
            with st.form("add_family_asset_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    asset_type = st.selectbox(
                        "Type*",
                        ["ASSET", "LIABILITY"],
                        help="Select whether this is an asset or liability"
                    )
                    
                    item_name = st.text_input(
                        "Item Name*",
                        placeholder="e.g., House, Car, Credit Card, Property"
                    )
                    
                    category = st.selectbox(
                        "Category*",
                        ["Real Estate", "Vehicle", "Investment", "Jewelry", "Electronics", 
                         "Furniture", "Loan", "Credit Card", "Mortgage", "Personal Loan", "Other"],
                        help="Select the category that best fits this item"
                    )
                    
                    location_place = st.text_area(
                        "Location/Place",
                        placeholder="e.g., 123 Main St, New York, NY or Bank Name, Account Number"
                    )
                    
                    purchase_date = st.date_input(
                        "Purchase/Start Date*",
                        help="Date when acquired or loan started"
                    )
                    
                    purchase_value = st.number_input(
                        "Purchase/Original Value*",
                        min_value=0.0,
                        step=100.0,
                        help="Original value or loan amount"
                    )
                
                with col2:
                    current_status = st.selectbox(
                        "Current Status*",
                        ["ACTIVE", "SOLD", "PAID_OFF", "INACTIVE"],
                        help="Current status of this item"
                    )
                    
                    # Sold/Paid off details
                    if current_status in ["SOLD", "PAID_OFF"]:
                        sold_date = st.date_input(
                            "Sold/Paid Off Date",
                            help="Date when sold or paid off"
                        )
                        sold_value = st.number_input(
                            "Sold/Final Value",
                            min_value=0.0,
                            step=100.0,
                            help="Final sale value or remaining balance"
                        )
                    else:
                        sold_date = None
                        sold_value = None
                    
                    notes = st.text_area(
                        "Notes",
                        placeholder="Additional information, documents location, insurance details, etc.",
                        height=200
                    )
                
                submitted = st.form_submit_button("💾 Add Record", type="primary")
                
                if submitted:
                    if not item_name or not category or not purchase_date or purchase_value <= 0:
                        st.error("❌ Please fill all required fields marked with *")
                    else:
                        try:
                            insert_query = """
                            INSERT INTO dbo.family_assets 
                            (asset_type, item_name, category, location_place, purchase_date, 
                             purchase_value, sold_date, sold_value, current_status, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """
                            cursor.execute(insert_query, 
                                         (asset_type, item_name, category, location_place, purchase_date,
                                          purchase_value, sold_date, sold_value, current_status, notes))
                            conn.commit()
                            
                            st.session_state.family_success = f"✅ Successfully added {asset_type.lower()}: {item_name}!"
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error adding record: {e}")
            
            # Display success message if it exists
            if 'family_success' in st.session_state:
                st.success(st.session_state.family_success)
                st.balloons()
                del st.session_state.family_success
        
        with tab3:
            st.markdown("### All Assets & Liabilities Records")
            
            if assets_df.empty:
                st.info("📋 No records yet.")
            else:
                # Filter options
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    filter_type = st.selectbox("Filter by Type", ["All", "ASSET", "LIABILITY"])
                with col2:
                    filter_status = st.selectbox("Filter by Status", ["All", "ACTIVE", "SOLD", "PAID_OFF", "INACTIVE"])
                with col3:
                    filter_category = st.selectbox(
                        "Filter by Category",
                        ["All"] + sorted(assets_df['category'].dropna().unique().tolist())
                    )
                
                # Apply filters
                filtered_df = assets_df.copy()
                if filter_type != "All":
                    filtered_df = filtered_df[filtered_df['asset_type'] == filter_type]
                if filter_status != "All":
                    filtered_df = filtered_df[filtered_df['current_status'] == filter_status]
                if filter_category != "All":
                    filtered_df = filtered_df[filtered_df['category'] == filter_category]
                
                st.markdown(f"**Showing {len(filtered_df)} of {len(assets_df)} records**")
                
                # Editable dataframe
                st.markdown("---")
                st.markdown("#### Edit Records")
                
                with st.expander("💡 How to Edit/Delete Records", expanded=False):
                    st.markdown("""
                    **Editing:**
                    1. Click on any cell to edit its value
                    2. Click 'Save Changes' to update database
                    
                    **Deleting:**
                    1. Hover over row number (leftmost column)
                    2. Click trash icon (🗑️)
                    3. Click 'Save Changes' to confirm deletion
                    """)
                
                edited_df = st.data_editor(
                    filtered_df,
                    use_container_width=True,
                    num_rows="dynamic",
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                        "asset_type": st.column_config.SelectboxColumn("Type", options=["ASSET", "LIABILITY"], width="small"),
                        "item_name": st.column_config.TextColumn("Item Name", width="medium"),
                        "category": st.column_config.TextColumn("Category", width="medium"),
                        "location_place": st.column_config.TextColumn("Location/Place", width="large"),
                        "purchase_date": st.column_config.DateColumn("Purchase Date"),
                        "purchase_value": st.column_config.NumberColumn("Purchase Value", format="$%.2f"),
                        "sold_date": st.column_config.DateColumn("Sold Date"),
                        "sold_value": st.column_config.NumberColumn("Sold Value", format="$%.2f"),
                        "current_status": st.column_config.SelectboxColumn(
                            "Status",
                            options=["ACTIVE", "SOLD", "PAID_OFF", "INACTIVE"],
                            width="small"
                        ),
                        "notes": st.column_config.TextColumn("Notes", width="large"),
                        "created_date": st.column_config.DatetimeColumn("Created", disabled=True)
                    },
                    key="family_assets_editor"
                )
                
                # Show changes detected
                if len(edited_df) != len(filtered_df):
                    rows_added = max(0, len(edited_df) - len(filtered_df))
                    rows_deleted = max(0, len(filtered_df) - len(edited_df))
                    
                    if rows_deleted > 0:
                        st.warning(f"⚠️ {rows_deleted} row(s) will be deleted. Click 'Save Changes' to confirm.")
                    if rows_added > 0:
                        st.info(f"ℹ️ {rows_added} new row(s) added. Click 'Save Changes' to save.")
                
                # Bulk delete option
                st.markdown("---")
                st.markdown("#### 🗑️ Bulk Delete Records")
                
                with st.expander("Delete Multiple Records", expanded=False):
                    st.warning("⚠️ This will permanently delete selected records from the database!")
                    
                    # Filter options for bulk delete
                    delete_col1, delete_col2 = st.columns(2)
                    
                    with delete_col1:
                        delete_by = st.radio(
                            "Delete by:",
                            ["Select by ID", "Select by Item", "Select by Type", "Select by Status", "Select by Category"],
                            key="family_delete_by_option"
                        )
                    
                    with delete_col2:
                        if delete_by == "Select by ID":
                            # Show available IDs with item names for reference
                            st.markdown("**Available IDs:**")
                            id_reference = assets_df[['id', 'item_name', 'asset_type', 'category']].copy()
                            st.dataframe(
                                id_reference,
                                use_container_width=True,
                                height=200,
                                column_config={
                                    "id": "ID",
                                    "item_name": "Item Name",
                                    "asset_type": "Type",
                                    "category": "Category"
                                }
                            )
                            
                            ids_to_delete_input = st.text_input(
                                "Enter IDs to Delete (comma-separated)",
                                placeholder="e.g., 1, 5, 12",
                                key="family_ids_to_delete",
                                help="Enter one or more ID numbers separated by commas"
                            )
                            
                            if ids_to_delete_input and st.button("🗑️ Delete Selected IDs", type="secondary", key="delete_ids_btn"):
                                try:
                                    # Parse comma-separated IDs
                                    ids_to_delete = [int(id.strip()) for id in ids_to_delete_input.split(',') if id.strip().isdigit()]
                                    
                                    if not ids_to_delete:
                                        st.error("❌ Please enter valid ID numbers")
                                    else:
                                        # Verify IDs exist in database
                                        valid_ids = assets_df[assets_df['id'].isin(ids_to_delete)]['id'].tolist()
                                        invalid_ids = [id for id in ids_to_delete if id not in valid_ids]
                                        
                                        if invalid_ids:
                                            st.warning(f"⚠️ IDs not found: {', '.join(map(str, invalid_ids))}")
                                        
                                        if valid_ids:
                                            # Get item names for confirmation message
                                            deleted_items = assets_df[assets_df['id'].isin(valid_ids)]['item_name'].tolist()
                                            
                                            placeholders = ','.join(['?' for _ in valid_ids])
                                            delete_query = f"DELETE FROM dbo.family_assets WHERE id IN ({placeholders})"
                                            cursor.execute(delete_query, valid_ids)
                                            conn.commit()
                                            st.session_state.family_success = f"✅ Deleted {len(valid_ids)} record(s) (IDs: {', '.join(map(str, valid_ids))}): {', '.join(deleted_items)}"
                                            st.rerun()
                                except ValueError:
                                    st.error("❌ Please enter valid numeric IDs separated by commas")
                                except Exception as e:
                                    st.error(f"❌ Error deleting records: {e}")
                        
                        elif delete_by == "Select by Item":
                            items_to_delete = st.multiselect(
                                "Select Items to Delete",
                                options=sorted(assets_df['item_name'].unique().tolist()),
                                key="family_items_to_delete"
                            )
                            if items_to_delete and st.button("🗑️ Delete Selected Items", type="secondary", key="delete_items_btn"):
                                try:
                                    ids_to_delete = assets_df[assets_df['item_name'].isin(items_to_delete)]['id'].tolist()
                                    if ids_to_delete:
                                        placeholders = ','.join(['?' for _ in ids_to_delete])
                                        delete_query = f"DELETE FROM dbo.family_assets WHERE id IN ({placeholders})"
                                        cursor.execute(delete_query, ids_to_delete)
                                        conn.commit()
                                        st.session_state.family_success = f"✅ Deleted {len(ids_to_delete)} record(s): {', '.join(items_to_delete)}"
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error deleting records: {e}")
                        
                        elif delete_by == "Select by Type":
                            type_to_delete = st.selectbox(
                                "Select Type to Delete",
                                options=["ASSET", "LIABILITY"],
                                key="family_type_to_delete"
                            )
                            matching_count = len(assets_df[assets_df['asset_type'] == type_to_delete])
                            st.info(f"This will delete {matching_count} record(s) of type '{type_to_delete}'")
                            
                            if st.button(f"🗑️ Delete All {type_to_delete}s", type="secondary", key="delete_type_btn"):
                                try:
                                    ids_to_delete = assets_df[assets_df['asset_type'] == type_to_delete]['id'].tolist()
                                    if ids_to_delete:
                                        placeholders = ','.join(['?' for _ in ids_to_delete])
                                        delete_query = f"DELETE FROM dbo.family_assets WHERE id IN ({placeholders})"
                                        cursor.execute(delete_query, ids_to_delete)
                                        conn.commit()
                                        st.session_state.family_success = f"✅ Deleted {len(ids_to_delete)} {type_to_delete} record(s)"
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error deleting records: {e}")
                        
                        elif delete_by == "Select by Status":
                            status_to_delete = st.selectbox(
                                "Select Status to Delete",
                                options=["ACTIVE", "SOLD", "PAID_OFF", "INACTIVE"],
                                key="family_status_to_delete"
                            )
                            matching_count = len(assets_df[assets_df['current_status'] == status_to_delete])
                            st.info(f"This will delete {matching_count} record(s) with status '{status_to_delete}'")
                            
                            if st.button(f"🗑️ Delete All {status_to_delete} Records", type="secondary", key="delete_status_btn"):
                                try:
                                    ids_to_delete = assets_df[assets_df['current_status'] == status_to_delete]['id'].tolist()
                                    if ids_to_delete:
                                        placeholders = ','.join(['?' for _ in ids_to_delete])
                                        delete_query = f"DELETE FROM dbo.family_assets WHERE id IN ({placeholders})"
                                        cursor.execute(delete_query, ids_to_delete)
                                        conn.commit()
                                        st.session_state.family_success = f"✅ Deleted {len(ids_to_delete)} {status_to_delete} record(s)"
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error deleting records: {e}")
                        
                        elif delete_by == "Select by Category":
                            category_to_delete = st.selectbox(
                                "Select Category to Delete",
                                options=sorted(assets_df['category'].dropna().unique().tolist()),
                                key="family_category_to_delete"
                            )
                            matching_count = len(assets_df[assets_df['category'] == category_to_delete])
                            st.info(f"This will delete {matching_count} record(s) in category '{category_to_delete}'")
                            
                            if st.button(f"🗑️ Delete All '{category_to_delete}' Records", type="secondary", key="delete_category_btn"):
                                try:
                                    ids_to_delete = assets_df[assets_df['category'] == category_to_delete]['id'].tolist()
                                    if ids_to_delete:
                                        placeholders = ','.join(['?' for _ in ids_to_delete])
                                        delete_query = f"DELETE FROM dbo.family_assets WHERE id IN ({placeholders})"
                                        cursor.execute(delete_query, ids_to_delete)
                                        conn.commit()
                                        st.session_state.family_success = f"✅ Deleted {len(ids_to_delete)} record(s) from category '{category_to_delete}'"
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error deleting records: {e}")
                
                # Save and export buttons
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 1, 4])
                
                with col1:
                    if st.button("💾 Save Changes", type="primary", key="save_family_assets"):
                        try:
                            connection_string = get_connection_pool()
                            conn_update = pyodbc.connect(connection_string)
                            conn_update.autocommit = False
                            cursor_update = conn_update.cursor()
                            
                            cursor_update.execute("DELETE FROM dbo.family_assets")
                            
                            for _, row in edited_df.iterrows():
                                purchase_date_val = row['purchase_date'].date() if pd.notna(row['purchase_date']) and hasattr(row['purchase_date'], 'date') else row['purchase_date'] if pd.notna(row['purchase_date']) else None
                                sold_date_val = row['sold_date'].date() if pd.notna(row['sold_date']) and hasattr(row['sold_date'], 'date') else row['sold_date'] if pd.notna(row['sold_date']) else None
                                
                                insert_query = """
                                INSERT INTO dbo.family_assets 
                                (asset_type, item_name, category, location_place, purchase_date, 
                                 purchase_value, sold_date, sold_value, current_status, notes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """
                                cursor_update.execute(insert_query,
                                    (row['asset_type'], row['item_name'], row['category'],
                                     row['location_place'] if pd.notna(row['location_place']) else None,
                                     purchase_date_val,
                                     row['purchase_value'] if pd.notna(row['purchase_value']) else None,
                                     sold_date_val,
                                     row['sold_value'] if pd.notna(row['sold_value']) else None,
                                     row['current_status'],
                                     row['notes'] if pd.notna(row['notes']) else None))
                            
                            conn_update.commit()
                            conn_update.close()
                            
                            st.session_state.family_success = f"✅ Successfully updated {len(edited_df)} records!"
                            st.rerun()
                        except Exception as e:
                            if conn_update:
                                try:
                                    conn_update.rollback()
                                    conn_update.close()
                                except:
                                    pass
                            st.error(f"❌ Error saving changes: {e}")
                
                with col2:
                    if st.button("🔄 Refresh"):
                        st.rerun()
                
                with col3:
                    st.download_button(
                        label="📥 Download CSV",
                        data=filtered_df.to_csv(index=False),
                        file_name=f"family_assets_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
        
        with tab4:
            st.markdown("### Summary & Analytics")
            
            if assets_df.empty:
                st.info("📋 No data available for summary.")
            else:
                # Category breakdown
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### Assets by Category")
                    assets_only = assets_df[assets_df['asset_type'] == 'ASSET']
                    if not assets_only.empty:
                        category_summary = assets_only.groupby('category')['purchase_value'].agg(['sum', 'count']).reset_index()
                        category_summary.columns = ['Category', 'Total Value', 'Count']
                        category_summary = category_summary.sort_values('Total Value', ascending=False)
                        
                        st.dataframe(
                            category_summary,
                            use_container_width=True,
                            column_config={
                                "Total Value": st.column_config.NumberColumn("Total Value", format="$%.2f")
                            }
                        )
                    else:
                        st.info("No assets to summarize.")
                
                with col2:
                    st.markdown("#### Liabilities by Category")
                    liabilities_only = assets_df[assets_df['asset_type'] == 'LIABILITY']
                    if not liabilities_only.empty:
                        category_summary = liabilities_only.groupby('category')['purchase_value'].agg(['sum', 'count']).reset_index()
                        category_summary.columns = ['Category', 'Total Value', 'Count']
                        category_summary = category_summary.sort_values('Total Value', ascending=False)
                        
                        st.dataframe(
                            category_summary,
                            use_container_width=True,
                            column_config={
                                "Total Value": st.column_config.NumberColumn("Total Value", format="$%.2f")
                            }
                        )
                    else:
                        st.info("No liabilities to summarize.")
                
                # Status breakdown
                st.markdown("---")
                st.markdown("#### Status Breakdown")
                
                status_df = assets_df.groupby(['asset_type', 'current_status'])['purchase_value'].agg(['sum', 'count']).reset_index()
                status_df.columns = ['Type', 'Status', 'Total Value', 'Count']
                
                st.dataframe(
                    status_df,
                    use_container_width=True,
                    column_config={
                        "Total Value": st.column_config.NumberColumn("Total Value", format="$%.2f")
                    }
                )
        
        conn.close()
        
    except Exception as e:
        st.error(f"❌ Error loading family assets tracker: {e}")
        st.info("Please check your database connection.")


# Main application routing
if page == "🏠 Home & Filters":
    show_home_page()
elif page == "📋 Data in Table format":
    show_data_table_page()
elif page == "📈 Technical Analysis":
    show_technical_analysis_page()
elif page == "🤖 AI Price Predictions":
    show_ml_prediction_page()
elif page == "🛩️ Flight Status Dashboard":
    show_flight_status_page()
elif page == "📊 NASDAQ ML Predictions":
    show_nasdaq_ml_predictions_page()
elif page == "📈 NSE ML Predictions":
    show_nse_ml_predictions_page()
elif page == "💱 Forex ML Predictions":
    show_forex_ml_predictions_page()
elif page == "📊 Reco Tracking and Current Status":
    show_reco_tracking_page()
elif page == "📈 Today Trend Recommendations":
    show_today_trend_recommendations_page()
elif page == "📊 Master Data Editor":
    show_master_data_editor()
elif page == "💼 My Portfolio Tracker":
    show_portfolio_tracker()
elif page == "👨‍👩‍👧‍👦 For Family":
    show_family_assets_page()
elif page == "🤖 AI Trading Signals Scanner":
    show_ai_trading_signals_scanner()

