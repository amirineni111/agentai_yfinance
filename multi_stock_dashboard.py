import streamlit as st
import pyodbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import time

# ----------------------------
# DB CONNECTION (Reuse from your existing setup)
# ----------------------------
@st.cache_resource
def get_connection_pool():
    """Create a connection pool to manage database connections more efficiently"""
    connection_string = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost\\MSSQLSERVER01;'
        'DATABASE=stockdata_db;'
        'Trusted_Connection=yes;'
        'MARS_Connection=yes;'
        'Connection Timeout=30;'
        'Command Timeout=30;'
        'MultipleActiveResultSets=true;'
        'Pooling=true;'
    )
    return connection_string

def get_connection():
    """Create a new database connection with enhanced error handling"""
    try:
        connection_string = get_connection_pool()
        conn = pyodbc.connect(connection_string)
        conn.timeout = 30
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error(f"Database connection error: {str(e)}")
        return None

def execute_query_safe(query: str, params: list = None) -> pd.DataFrame:
    """Safe database query execution with proper error handling"""
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
                    time.sleep(1)
                    continue
            
            if retry_count >= max_retries:
                st.error(f"Database query failed after {max_retries} attempts: {error_msg}")
                return pd.DataFrame()
                
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    return pd.DataFrame()

# ----------------------------
# MULTI-STOCK DATA LOADING FUNCTIONS
# ----------------------------

@st.cache_data(ttl=300)  # Cache for 5 minutes for real-time feel
def load_all_tickers(index_name: str) -> pd.DataFrame:
    """Get all available tickers for an index"""
    table = 'nse_500_hist_data' if index_name == 'NSE 500' else 'nasdaq_100_hist_data'
    query = f"""
        SELECT DISTINCT ticker, company
        FROM dbo.{table}
        ORDER BY ticker
    """
    return execute_query_safe(query)

@st.cache_data(ttl=300)
def load_latest_prices(index_name: str, limit: int = None) -> pd.DataFrame:
    """Load latest price data for all stocks in an index"""
    table = 'nse_500_hist_data' if index_name == 'NSE 500' else 'nasdaq_100_hist_data'
    limit_clause = f"TOP {limit}" if limit else ""
    
    query = f"""
        WITH LatestPrices AS (
            SELECT 
                ticker,
                company,
                trading_date,
                CAST(close_price AS FLOAT) AS close_price,
                CAST(open_price AS FLOAT) AS open_price,
                CAST(high_price AS FLOAT) AS high_price,
                CAST(low_price AS FLOAT) AS low_price,
                CAST(volume AS FLOAT) AS volume,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
            FROM dbo.{table}
        )
        SELECT {limit_clause}
            ticker,
            company,
            trading_date,
            close_price,
            open_price,
            high_price,
            low_price,
            volume,
            ROUND(((close_price - open_price) / open_price) * 100, 2) as daily_change_pct
        FROM LatestPrices
        WHERE rn = 1
        ORDER BY ticker
    """
    df = execute_query_safe(query)
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df

@st.cache_data(ttl=300)
def load_latest_indicators_batch(index_name: str, limit: int = None) -> pd.DataFrame:
    """
    OPTION 1: Database-level aggregation (RECOMMENDED)
    Load all latest technical indicators in a single query for better performance
    """
    # Define view names based on index
    if index_name == 'NSE 500':
        price_table = 'nse_500_hist_data'
        rsi_view = 'nse_500_RSI_calculation'
        macd_view = 'nse_500_macd'
        bb_view = 'nse_500_bollingerband'
        sma_view = 'nse_500_ema_sma_view'
        atr_view = 'nse_500_atr'
        
        # Signal views
        bb_signals = 'nse_500_bb_signals'
        macd_signals = 'nse_500_macd_signals'
        rsi_signals = 'nse_500_rsi_signals'
        sma_signals = 'nse_500_sma_signals'
        atr_signals = 'nse_500_atr_spikes'
    else:
        price_table = 'nasdaq_100_hist_data'
        rsi_view = 'nasdaq_100_RSI_calculation'
        macd_view = 'nasdaq_100_macd'
        bb_view = 'nasdaq_100_bollingerband'
        sma_view = 'nasdaq_100_ema_sma_view'
        atr_view = 'nasdaq_100_atr'
        
        # Signal views
        bb_signals = 'nasdaq_100_bb_signals'
        macd_signals = 'nasdaq_100_macd_signals'
        rsi_signals = 'nasdaq_100_rsi_signals'
        sma_signals = 'nasdaq_100_sma_signals'
        atr_signals = 'nasdaq_100_atr_spikes'
    
    limit_clause = f"TOP {limit}" if limit else ""
    
    # Comprehensive query that joins all indicators and latest signals
    query = f"""
        WITH LatestData AS (
            -- Get latest price data
            SELECT 
                ticker,
                company,
                trading_date,
                CAST(close_price AS FLOAT) AS close_price,
                CAST(open_price AS FLOAT) AS open_price,
                ROUND(((close_price - open_price) / open_price) * 100, 2) as daily_change_pct,
                CAST(volume AS FLOAT) AS volume,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as price_rn
            FROM dbo.{price_table}
        ),
        LatestRSI AS (
            SELECT 
                ticker,
                RSI,
                trading_date,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rsi_rn
            FROM dbo.{rsi_view}
        ),
        LatestMACD AS (
            SELECT 
                ticker,
                MACD,
                Signal_Line,
                trading_date,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as macd_rn
            FROM dbo.{macd_view}
        ),
        LatestBB AS (
            SELECT 
                ticker,
                Upper_Band,
                Lower_Band,
                close_price as bb_close,
                trading_date,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as bb_rn
            FROM dbo.{bb_view}
        ),
        LatestSMA AS (
            SELECT 
                ticker,
                SMA_50,
                SMA_200,
                EMA_50,
                close_price as sma_close,
                trading_date,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as sma_rn
            FROM dbo.{sma_view}
        ),
        LatestATR AS (
            SELECT 
                ticker,
                ATR_14,
                trading_date,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as atr_rn
            FROM dbo.{atr_view}
        ),
        LatestSignals AS (
            -- Get latest signals from each signal view
            SELECT 
                p.ticker,
                -- Latest RSI signal
                (SELECT TOP 1 rsi_trade_signal 
                 FROM dbo.{rsi_signals} rs 
                 WHERE rs.ticker = p.ticker AND rs.rsi_trade_signal IS NOT NULL 
                 ORDER BY rs.trading_date DESC) as latest_rsi_signal,
                
                -- Latest MACD signal  
                (SELECT TOP 1 MACD_Signal 
                 FROM dbo.{macd_signals} ms 
                 WHERE ms.ticker = p.ticker AND ms.MACD_Signal IS NOT NULL 
                 ORDER BY ms.trading_date DESC) as latest_macd_signal,
                
                -- Latest BB signal
                (SELECT TOP 1 bb_trade_signal 
                 FROM dbo.{bb_signals} bs 
                 WHERE bs.ticker = p.ticker AND bs.bb_trade_signal IS NOT NULL 
                 ORDER BY bs.trading_date DESC) as latest_bb_signal,
                
                -- Latest SMA signal
                (SELECT TOP 1 sma_trade_signal 
                 FROM dbo.{sma_signals} ss 
                 WHERE ss.ticker = p.ticker AND ss.sma_trade_signal IS NOT NULL 
                 ORDER BY ss.trading_date DESC) as latest_sma_signal,
                
                -- Latest ATR signal
                (SELECT TOP 1 atr_volatility_signal 
                 FROM dbo.{atr_signals} ats 
                 WHERE ats.ticker = p.ticker AND ats.atr_volatility_signal IS NOT NULL 
                 ORDER BY ats.trading_date DESC) as latest_atr_signal
                 
            FROM (SELECT DISTINCT ticker FROM dbo.{price_table}) p
        )
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
            m.Signal_Line,
            bb.Upper_Band,
            bb.Lower_Band,
            sma.SMA_50,
            sma.SMA_200,
            sma.EMA_50,
            atr.ATR_14,
            
            -- Trading Signals
            sig.latest_rsi_signal,
            sig.latest_macd_signal, 
            sig.latest_bb_signal,
            sig.latest_sma_signal,
            sig.latest_atr_signal,
            
            -- Calculated Fields for Dashboard
            CASE 
                WHEN r.RSI > 70 THEN 'Overbought'
                WHEN r.RSI < 30 THEN 'Oversold' 
                ELSE 'Neutral'
            END as rsi_status,
            
            CASE 
                WHEN m.MACD > m.Signal_Line THEN 'Bullish'
                ELSE 'Bearish'
            END as macd_trend,
            
            CASE 
                WHEN p.close_price > sma.SMA_200 THEN 'Uptrend'
                ELSE 'Downtrend'
            END as long_term_trend,
            
            CASE 
                WHEN bb.Upper_Band IS NOT NULL AND bb.Lower_Band IS NOT NULL THEN
                    ROUND(((p.close_price - bb.Lower_Band) / (bb.Upper_Band - bb.Lower_Band)) * 100, 1)
                ELSE NULL
            END as bb_position,
            
            -- Signal Strength Score (0-5 scale)
            (
                CASE WHEN sig.latest_rsi_signal = 'BUY' THEN 1 WHEN sig.latest_rsi_signal = 'SELL' THEN -1 ELSE 0 END +
                CASE WHEN sig.latest_macd_signal = 'BUY' THEN 1 WHEN sig.latest_macd_signal = 'SELL' THEN -1 ELSE 0 END +
                CASE WHEN sig.latest_bb_signal = 'BUY' THEN 1 WHEN sig.latest_bb_signal = 'SELL' THEN -1 ELSE 0 END +
                CASE WHEN sig.latest_sma_signal = 'BUY' THEN 1 WHEN sig.latest_sma_signal = 'SELL' THEN -1 ELSE 0 END +
                CASE WHEN r.RSI < 30 THEN 1 WHEN r.RSI > 70 THEN -1 ELSE 0 END
            ) as signal_score
            
        FROM LatestData p
        LEFT JOIN LatestRSI r ON p.ticker = r.ticker AND r.rsi_rn = 1
        LEFT JOIN LatestMACD m ON p.ticker = m.ticker AND m.macd_rn = 1  
        LEFT JOIN LatestBB bb ON p.ticker = bb.ticker AND bb.bb_rn = 1
        LEFT JOIN LatestSMA sma ON p.ticker = sma.ticker AND sma.sma_rn = 1
        LEFT JOIN LatestATR atr ON p.ticker = atr.ticker AND atr.atr_rn = 1
        LEFT JOIN LatestSignals sig ON p.ticker = sig.ticker
        WHERE p.price_rn = 1
        ORDER BY p.ticker
    """
    
    df = execute_query_safe(query)
    if not df.empty:
        df['last_update'] = pd.to_datetime(df['last_update'])
        # Add overall recommendation based on signal score
        df['recommendation'] = df['signal_score'].apply(
            lambda x: '🟢 Strong Buy' if x >= 3 
                     else '🟢 Buy' if x >= 1 
                     else '🔴 Sell' if x <= -1
                     else '🔴 Strong Sell' if x <= -3
                     else '🟡 Hold'
        )
    return df

def load_latest_indicators_individual(index_name: str, tickers: list = None, limit: int = None) -> pd.DataFrame:
    """
    OPTION 2: Application-level aggregation 
    Load indicators individually (slower but more flexible)
    Use this if the database query is too complex or you need more control
    """
    if not tickers:
        ticker_df = load_all_tickers(index_name)
        if limit:
            ticker_df = ticker_df.head(limit)
        tickers = ticker_df['ticker'].tolist()
    
    all_data = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(tickers):
        try:
            status_text.text(f"Loading data for {ticker}... ({i+1}/{len(tickers)})")
            
            # Load latest price
            price_data = load_latest_price_individual(index_name, ticker)
            if price_data.empty:
                continue
                
            # Load latest indicators
            rsi_data = load_latest_rsi_individual(index_name, ticker)
            macd_data = load_latest_macd_individual(index_name, ticker)
            bb_data = load_latest_bb_individual(index_name, ticker)
            sma_data = load_latest_sma_individual(index_name, ticker)
            atr_data = load_latest_atr_individual(index_name, ticker)
            
            # Load latest signals
            signals = load_latest_signals_individual(index_name, ticker)
            
            # Combine into single row
            row_data = {
                'ticker': ticker,
                'company': price_data.get('company', ''),
                'last_update': price_data.get('trading_date'),
                'close_price': price_data.get('close_price'),
                'daily_change_pct': price_data.get('daily_change_pct'),
                'volume': price_data.get('volume'),
                
                # Technical indicators
                'RSI': rsi_data.get('RSI'),
                'MACD': macd_data.get('MACD'),
                'Signal_Line': macd_data.get('Signal_Line'),
                'SMA_50': sma_data.get('SMA_50'),
                'SMA_200': sma_data.get('SMA_200'),
                'ATR_14': atr_data.get('ATR_14'),
                
                # Signals
                'latest_rsi_signal': signals.get('rsi_signal'),
                'latest_macd_signal': signals.get('macd_signal'),
                'latest_bb_signal': signals.get('bb_signal'),
                'latest_sma_signal': signals.get('sma_signal'),
                
                # Calculated fields
                'rsi_status': 'Overbought' if (rsi_data.get('RSI', 50) > 70) else 'Oversold' if (rsi_data.get('RSI', 50) < 30) else 'Neutral',
                'macd_trend': 'Bullish' if (macd_data.get('MACD', 0) > macd_data.get('Signal_Line', 0)) else 'Bearish',
                'long_term_trend': 'Uptrend' if (price_data.get('close_price', 0) > sma_data.get('SMA_200', 0)) else 'Downtrend'
            }
            
            # Calculate signal score
            signal_score = 0
            if signals.get('rsi_signal') == 'BUY': signal_score += 1
            elif signals.get('rsi_signal') == 'SELL': signal_score -= 1
            if signals.get('macd_signal') == 'BUY': signal_score += 1
            elif signals.get('macd_signal') == 'SELL': signal_score -= 1
            # Add other signals...
            
            row_data['signal_score'] = signal_score
            row_data['recommendation'] = (
                '🟢 Strong Buy' if signal_score >= 3 else
                '🟢 Buy' if signal_score >= 1 else
                '🔴 Sell' if signal_score <= -1 else
                '🔴 Strong Sell' if signal_score <= -3 else
                '🟡 Hold'
            )
            
            all_data.append(row_data)
            
            progress_bar.progress((i + 1) / len(tickers))
            
        except Exception as e:
            st.warning(f"Failed to load data for {ticker}: {str(e)}")
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame(all_data)

def load_latest_price_individual(index_name: str, ticker: str) -> dict:
    """Load latest price for a single ticker"""
    table = 'nse_500_hist_data' if index_name == 'NSE 500' else 'nasdaq_100_hist_data'
    query = f"""
        SELECT TOP 1 
            company,
            trading_date,
            CAST(close_price AS FLOAT) as close_price,
            CAST(open_price AS FLOAT) as open_price,
            CAST(volume AS FLOAT) as volume,
            ROUND(((close_price - open_price) / open_price) * 100, 2) as daily_change_pct
        FROM dbo.{table}
        WHERE ticker = ?
        ORDER BY trading_date DESC
    """
    df = execute_query_safe(query, params=[ticker])
    return df.iloc[0].to_dict() if not df.empty else {}

def load_latest_rsi_individual(index_name: str, ticker: str) -> dict:
    """Load latest RSI for a single ticker"""
    view = 'nse_500_RSI_calculation' if index_name == 'NSE 500' else 'nasdaq_100_RSI_calculation'
    query = f"""
        SELECT TOP 1 RSI
        FROM dbo.{view}
        WHERE ticker = ?
        ORDER BY trading_date DESC
    """
    df = execute_query_safe(query, params=[ticker])
    return df.iloc[0].to_dict() if not df.empty else {}

def load_latest_macd_individual(index_name: str, ticker: str) -> dict:
    """Load latest MACD for a single ticker"""
    view = 'nse_500_macd' if index_name == 'NSE 500' else 'nasdaq_100_macd'
    query = f"""
        SELECT TOP 1 MACD, Signal_Line
        FROM dbo.{view}
        WHERE ticker = ?
        ORDER BY trading_date DESC
    """
    df = execute_query_safe(query, params=[ticker])
    return df.iloc[0].to_dict() if not df.empty else {}

def load_latest_bb_individual(index_name: str, ticker: str) -> dict:
    """Load latest Bollinger Bands for a single ticker"""
    view = 'nse_500_bollingerband' if index_name == 'NSE 500' else 'nasdaq_100_bollingerband'
    query = f"""
        SELECT TOP 1 Upper_Band, Lower_Band, close_price
        FROM dbo.{view}
        WHERE ticker = ?
        ORDER BY trading_date DESC
    """
    df = execute_query_safe(query, params=[ticker])
    return df.iloc[0].to_dict() if not df.empty else {}

def load_latest_sma_individual(index_name: str, ticker: str) -> dict:
    """Load latest SMAs for a single ticker"""
    view = 'nse_500_ema_sma_view' if index_name == 'NSE 500' else 'nasdaq_100_ema_sma_view'
    query = f"""
        SELECT TOP 1 SMA_50, SMA_200, EMA_50
        FROM dbo.{view}
        WHERE ticker = ?
        ORDER BY trading_date DESC
    """
    df = execute_query_safe(query, params=[ticker])
    return df.iloc[0].to_dict() if not df.empty else {}

def load_latest_atr_individual(index_name: str, ticker: str) -> dict:
    """Load latest ATR for a single ticker"""
    view = 'nse_500_atr' if index_name == 'NSE 500' else 'nasdaq_100_atr'
    query = f"""
        SELECT TOP 1 ATR_14
        FROM dbo.{view}
        WHERE ticker = ?
        ORDER BY trading_date DESC
    """
    df = execute_query_safe(query, params=[ticker])
    return df.iloc[0].to_dict() if not df.empty else {}

def load_latest_signals_individual(index_name: str, ticker: str) -> dict:
    """Load latest signals for a single ticker"""
    if index_name == 'NSE 500':
        views = {
            'rsi': 'nse_500_rsi_signals',
            'macd': 'nse_500_macd_signals', 
            'bb': 'nse_500_bb_signals',
            'sma': 'nse_500_sma_signals'
        }
    else:
        views = {
            'rsi': 'nasdaq_100_rsi_signals',
            'macd': 'nasdaq_100_macd_signals',
            'bb': 'nasdaq_100_bb_signals', 
            'sma': 'nasdaq_100_sma_signals'
        }
    
    signals = {}
    for signal_type, view_name in views.items():
        try:
            query = f"""
                SELECT TOP 1 
                    CASE 
                        WHEN '{signal_type}' = 'rsi' THEN rsi_trade_signal
                        WHEN '{signal_type}' = 'macd' THEN MACD_Signal
                        WHEN '{signal_type}' = 'bb' THEN bb_trade_signal
                        WHEN '{signal_type}' = 'sma' THEN sma_trade_signal
                    END as signal
                FROM dbo.{view_name}
                WHERE ticker = ? 
                ORDER BY trading_date DESC
            """
            df = execute_query_safe(query, params=[ticker])
            if not df.empty:
                signals[f'{signal_type}_signal'] = df.iloc[0]['signal']
        except:
            signals[f'{signal_type}_signal'] = None
    
    return signals

# ----------------------------
# DASHBOARD UI FUNCTIONS
# ----------------------------

def create_summary_metrics(df: pd.DataFrame):
    """Create summary metrics for the dashboard"""
    if df.empty:
        return
        
    total_stocks = len(df)
    bullish_stocks = len(df[df['signal_score'] > 0])
    bearish_stocks = len(df[df['signal_score'] < 0])
    neutral_stocks = total_stocks - bullish_stocks - bearish_stocks
    
    # Calculate percentages
    bullish_pct = (bullish_stocks / total_stocks * 100) if total_stocks > 0 else 0
    bearish_pct = (bearish_stocks / total_stocks * 100) if total_stocks > 0 else 0
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📊 Total Stocks", total_stocks)
    with col2:
        st.metric("🟢 Bullish", bullish_stocks, f"{bullish_pct:.1f}%")
    with col3:
        st.metric("🔴 Bearish", bearish_stocks, f"{bearish_pct:.1f}%")
    with col4:
        st.metric("🟡 Neutral", neutral_stocks)
    with col5:
        avg_rsi = df['RSI'].mean() if 'RSI' in df.columns and not df['RSI'].isna().all() else 0
        st.metric("📈 Avg RSI", f"{avg_rsi:.1f}")

def create_flight_status_table(df: pd.DataFrame):
    """Create the main flight-status style table"""
    if df.empty:
        st.warning("No data available for the selected criteria.")
        return
    
    st.markdown("### 🛩️ Flight Status Dashboard - All Stocks")
    
    # Add filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        signal_filter = st.selectbox(
            "Filter by Signal",
            ["All", "🟢 Buy Signals", "🔴 Sell Signals", "🟡 Hold"],
            key="signal_filter"
        )
    
    with col2:
        rsi_filter = st.selectbox(
            "Filter by RSI Status", 
            ["All", "Overbought", "Oversold", "Neutral"],
            key="rsi_filter"
        )
    
    with col3:
        trend_filter = st.selectbox(
            "Filter by Trend",
            ["All", "Uptrend", "Downtrend"], 
            key="trend_filter"
        )
    
    # Apply filters
    filtered_df = df.copy()
    
    if signal_filter != "All":
        if signal_filter == "🟢 Buy Signals":
            filtered_df = filtered_df[filtered_df['signal_score'] > 0]
        elif signal_filter == "🔴 Sell Signals":
            filtered_df = filtered_df[filtered_df['signal_score'] < 0]
        else:  # Hold
            filtered_df = filtered_df[filtered_df['signal_score'] == 0]
    
    if rsi_filter != "All":
        filtered_df = filtered_df[filtered_df['rsi_status'] == rsi_filter]
    
    if trend_filter != "All":
        filtered_df = filtered_df[filtered_df['long_term_trend'] == trend_filter]
    
    st.markdown(f"**Showing {len(filtered_df)} of {len(df)} stocks**")
    
    # Create the main table with custom formatting
    if not filtered_df.empty:
        # Select and rename columns for display
        display_df = filtered_df[[
            'ticker', 'company', 'close_price', 'daily_change_pct', 
            'RSI', 'rsi_status', 'macd_trend', 'long_term_trend',
            'latest_rsi_signal', 'latest_macd_signal', 'latest_bb_signal',
            'signal_score', 'recommendation', 'last_update'
        ]].copy()
        
        # Round numeric columns
        numeric_cols = ['close_price', 'daily_change_pct', 'RSI', 'signal_score']
        for col in numeric_cols:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(2)
        
        # Rename columns for better display
        display_df.columns = [
            'Ticker', 'Company', 'Price', 'Daily %', 
            'RSI', 'RSI Status', 'MACD Trend', 'Long Trend',
            'RSI Signal', 'MACD Signal', 'BB Signal', 
            'Score', 'Recommendation', 'Last Update'
        ]
        
        # Display with color coding
        def highlight_signals(row):
            styles = [''] * len(row)
            
            # Color code daily change
            if 'Daily %' in row.index:
                if row['Daily %'] > 0:
                    styles[row.index.get_loc('Daily %')] = 'color: green; font-weight: bold'
                elif row['Daily %'] < 0:
                    styles[row.index.get_loc('Daily %')] = 'color: red; font-weight: bold'
            
            # Color code RSI status
            if 'RSI Status' in row.index:
                if row['RSI Status'] == 'Overbought':
                    styles[row.index.get_loc('RSI Status')] = 'background-color: #ffebee; color: red'
                elif row['RSI Status'] == 'Oversold':
                    styles[row.index.get_loc('RSI Status')] = 'background-color: #e8f5e8; color: green'
            
            # Color code recommendation
            if 'Recommendation' in row.index:
                if 'Buy' in str(row['Recommendation']):
                    styles[row.index.get_loc('Recommendation')] = 'background-color: #e8f5e8; color: green; font-weight: bold'
                elif 'Sell' in str(row['Recommendation']):
                    styles[row.index.get_loc('Recommendation')] = 'background-color: #ffebee; color: red; font-weight: bold'
            
            return styles
        
        # Display the styled dataframe
        styled_df = display_df.style.apply(highlight_signals, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        # Add download button
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📊 Download Results as CSV",
            data=csv,
            file_name=f"flight_status_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

def create_visualizations(df: pd.DataFrame):
    """Create visualization charts for the dashboard"""
    if df.empty:
        return
    
    st.markdown("### 📊 Market Overview Charts")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Signal distribution pie chart
        signal_counts = df['recommendation'].value_counts()
        fig_pie = px.pie(
            values=signal_counts.values,
            names=signal_counts.index,
            title="📊 Signal Distribution",
            color_discrete_map={
                '🟢 Strong Buy': '#1f77b4',
                '🟢 Buy': '#2ca02c', 
                '🟡 Hold': '#ffbb33',
                '🔴 Sell': '#ff7f0e',
                '🔴 Strong Sell': '#d62728'
            }
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # RSI distribution histogram
        if 'RSI' in df.columns and not df['RSI'].isna().all():
            fig_hist = px.histogram(
                df,
                x='RSI',
                nbins=20,
                title="📈 RSI Distribution",
                labels={'RSI': 'RSI Value', 'count': 'Number of Stocks'}
            )
            fig_hist.add_vline(x=30, line_dash="dash", line_color="green", annotation_text="Oversold")
            fig_hist.add_vline(x=70, line_dash="dash", line_color="red", annotation_text="Overbought")
            st.plotly_chart(fig_hist, use_container_width=True)
    
    # Scatter plot of Price vs RSI colored by recommendation
    if 'RSI' in df.columns and 'close_price' in df.columns:
        fig_scatter = px.scatter(
            df,
            x='RSI',
            y='close_price',
            color='recommendation',
            hover_data=['ticker', 'company', 'daily_change_pct'],
            title="💹 Price vs RSI Analysis",
            labels={'close_price': 'Current Price', 'RSI': 'RSI Value'}
        )
        fig_scatter.add_vline(x=30, line_dash="dash", line_color="green", annotation_text="Oversold")
        fig_scatter.add_vline(x=70, line_dash="dash", line_color="red", annotation_text="Overbought")
        st.plotly_chart(fig_scatter, use_container_width=True)

def create_top_movers_section(df: pd.DataFrame):
    """Create top movers section"""
    if df.empty or 'daily_change_pct' not in df.columns:
        return
    
    st.markdown("### 🚀 Top Movers")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📈 Top Gainers")
        top_gainers = df.nlargest(10, 'daily_change_pct')[['ticker', 'company', 'daily_change_pct', 'recommendation']]
        top_gainers.columns = ['Ticker', 'Company', 'Change %', 'Signal']
        st.dataframe(top_gainers, use_container_width=True)
    
    with col2:
        st.markdown("#### 📉 Top Losers") 
        top_losers = df.nsmallest(10, 'daily_change_pct')[['ticker', 'company', 'daily_change_pct', 'recommendation']]
        top_losers.columns = ['Ticker', 'Company', 'Change %', 'Signal']
        st.dataframe(top_losers, use_container_width=True)

# ----------------------------
# MAIN DASHBOARD APP
# ----------------------------

def main():
    st.set_page_config(
        page_title="🛩️ Flight Status Stock Dashboard",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🛩️ Multi-Stock Flight Status Dashboard")
    st.markdown("**Real-time technical analysis across all stocks - Just like a flight status board!**")
    
    # Sidebar controls
    st.sidebar.header("🎛️ Dashboard Controls")
    
    # Index selection
    index_option = st.sidebar.selectbox(
        "📊 Select Market Index",
        ["NSE 500", "NASDAQ 100"]
    )
    
    # Data loading method selection
    loading_method = st.sidebar.selectbox(
        "⚙️ Data Loading Method",
        [
            "Database Batch Query (Recommended)",
            "Individual Stock Queries (Flexible)"
        ]
    )
    
    # Limit number of stocks for testing
    enable_limit = st.sidebar.checkbox("🔢 Limit number of stocks (for testing)")
    stock_limit = None
    if enable_limit:
        stock_limit = st.sidebar.slider("Number of stocks", 5, 50, 20)
    
    # Auto-refresh option
    auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (every 5 minutes)")
    if auto_refresh:
        st.sidebar.info("Dashboard will refresh automatically every 5 minutes")
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Data Now"):
        st.cache_data.clear()
        st.experimental_rerun()
    
    # Load data based on selected method
    with st.spinner("Loading market data..."):
        if "Database Batch" in loading_method:
            # RECOMMENDED: Use database-level aggregation
            df = load_latest_indicators_batch(index_option, limit=stock_limit)
        else:
            # Use application-level aggregation 
            df = load_latest_indicators_individual(index_option, limit=stock_limit)
    
    if df.empty:
        st.error("❌ No data available. Please check your database connection and ensure data is up to date.")
        return
    
    # Display last update time
    if 'last_update' in df.columns and not df['last_update'].isna().all():
        latest_update = df['last_update'].max()
        st.info(f"📅 Data last updated: {latest_update}")
    
    # Main dashboard sections
    create_summary_metrics(df)
    
    st.markdown("---")
    
    # Main table
    create_flight_status_table(df)
    
    st.markdown("---")
    
    # Visualizations
    create_visualizations(df)
    
    st.markdown("---")
    
    # Top movers
    create_top_movers_section(df)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    ### 📋 How to Read This Dashboard
    
    **Flight Status Approach:** Just like airport departures, each stock shows its current "status":
    - 🟢 **Buy Signals**: Like flights ready for departure - good entry opportunities
    - 🔴 **Sell Signals**: Like delayed flights - consider exiting positions  
    - 🟡 **Hold/Neutral**: Like flights on time - maintain current positions
    
    **Signal Score**: Combines multiple technical indicators (-5 to +5 scale)
    - **+3 to +5**: Strong Buy (multiple bullish signals)
    - **+1 to +2**: Buy (some bullish signals) 
    - **0**: Hold/Neutral (mixed signals)
    - **-1 to -2**: Sell (some bearish signals)
    - **-3 to -5**: Strong Sell (multiple bearish signals)
    
    **Technical Indicators Used:**
    - **RSI**: Momentum (Overbought >70, Oversold <30)
    - **MACD**: Trend direction and momentum
    - **SMA/EMA**: Long-term trend (Price vs 200 SMA)
    - **Bollinger Bands**: Volatility and mean reversion
    - **ATR**: Risk and position sizing
    """)
    
    # Auto-refresh implementation
    if auto_refresh:
        time.sleep(300)  # Wait 5 minutes
        st.experimental_rerun()

if __name__ == "__main__":
    main()
