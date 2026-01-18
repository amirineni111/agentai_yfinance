"""
FLIGHT STATUS DASHBOARD for Stock Analysis
Displays all stocks in a single table with technical indicators and trading recommendations
Author: Assistant
Date: November 2025

This dashboard provides a "flight status board" view of all stocks with their technical analysis.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import pyodbc
import time

# ----------------------------
# DB CONNECTION (Reuse from existing app)
# ----------------------------

@st.cache_resource
def get_connection_pool():
    """Reuse your existing connection pool"""
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
    """Your existing get_connection function"""
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
    """Your existing safe query execution"""
    conn = None
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = get_connection()
            if conn is None:
                return pd.DataFrame()
            
            if params:
                df = pd.read_sql(query, conn, params=params)
            else:
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                st.error(f"Database query failed: {str(e)}")
                return pd.DataFrame()
            time.sleep(1)
                
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    return pd.DataFrame()

# ----------------------------
# OPTIMIZED SINGLE-QUERY APPROACH  
# ----------------------------

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_flight_status_data(index_name: str, limit: int = None) -> pd.DataFrame:
    """
    OPTIMIZED: Single comprehensive query to get all stock data for flight status view
    This is the RECOMMENDED approach for your database architecture
    """
    
    # Map to your existing table and view names
    if index_name == 'NSE 500':
        base_table = 'nse_500_hist_data'
        ticker_column = 'ticker'
        company_column = 'company'
        rsi_view = 'nse_500_RSI_calculation'
        macd_view = 'nse_500_macd'
        bb_view = 'nse_500_bollingerband'
        sma_view = 'nse_500_ema_sma_view'
        atr_view = 'nse_500_atr'
        fibonacci_view = 'nse_500_fibonacci'
        stochastic_view = 'nse_500_stochastic'
        
        # Signal views
        rsi_signals = 'nse_500_rsi_signals'
        macd_signals = 'nse_500_macd_signals'
        bb_signals = 'nse_500_bb_signals' 
        sma_signals = 'nse_500_sma_signals'
        atr_signals = 'nse_500_atr_spikes'
        
    elif index_name == 'NASDAQ 100':
        base_table = 'nasdaq_100_hist_data'
        ticker_column = 'ticker'
        company_column = 'company'
        rsi_view = 'nasdaq_100_RSI_calculation'
        macd_view = 'nasdaq_100_macd'
        bb_view = 'nasdaq_100_bollingerband' 
        sma_view = 'nasdaq_100_ema_sma_view'
        atr_view = 'nasdaq_100_atr'
        fibonacci_view = 'nasdaq_100_fibonacci'
        stochastic_view = 'nasdaq_100_stochastic'
        
        rsi_signals = 'nasdaq_100_rsi_signals'
        macd_signals = 'nasdaq_100_macd_signals'
        bb_signals = 'nasdaq_100_bb_signals'
        sma_signals = 'nasdaq_100_sma_signals'
        atr_signals = 'nasdaq_100_atr_spikes'
        
    else:  # Forex
        base_table = 'forex_hist_data'
        ticker_column = 'symbol'  # Forex uses 'symbol' not 'ticker'
        company_column = 'symbol'  # Forex uses symbol for both
        rsi_view = 'forex_RSI_calculation'
        macd_view = 'forex_macd'
        bb_view = 'forex_bollingerband'
        sma_view = 'forex_ema_sma_view'
        atr_view = 'forex_atr'
        fibonacci_view = 'forex_fibonacci'
        stochastic_view = 'forex_stochastic'
        
        rsi_signals = 'forex_rsi_signals'
        macd_signals = 'forex_macd_signals'
        bb_signals = 'forex_bb_signals'
        sma_signals = 'forex_sma_signals'
        atr_signals = 'forex_atr_spikes'
    
    limit_clause = f"TOP {limit}" if limit else ""
    
    # Single comprehensive query - this is where the magic happens!
    query = f"""
    WITH 
    -- Get latest price data for each stock
    LatestPrices AS (
        SELECT 
            {ticker_column} as ticker,
            {company_column} as company,
            trading_date,
            CAST(close_price AS FLOAT) AS close_price,
            CAST(open_price AS FLOAT) AS open_price,
            CAST(high_price AS FLOAT) AS high_price,
            CAST(low_price AS FLOAT) AS low_price,
            CAST(volume AS FLOAT) AS volume,
            -- Calculate daily change
            ROUND(((CAST(close_price AS FLOAT) - CAST(open_price AS FLOAT)) / CAST(open_price AS FLOAT)) * 100, 2) as daily_change_pct,
            ROW_NUMBER() OVER (PARTITION BY {ticker_column} ORDER BY trading_date DESC) as rn
        FROM dbo.{base_table}
    ),
    
    -- Latest RSI values
    LatestRSI AS (
        SELECT 
            ticker,
            RSI,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
        FROM dbo.{rsi_view}
    ),
    
    -- Latest MACD values  
    LatestMACD AS (
        SELECT 
            ticker,
            MACD,
            Signal_Line,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
        FROM dbo.{macd_view}
    ),
    
    -- Latest Bollinger Bands
    LatestBB AS (
        SELECT 
            ticker,
            Upper_Band,
            Lower_Band,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
        FROM dbo.{bb_view}
    ),
    
    -- Latest Moving Averages
    LatestSMA AS (
        SELECT 
            ticker,
            SMA_50,
            SMA_200,
            EMA_50,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
        FROM dbo.{sma_view}
    ),
    
    -- Latest ATR
    LatestATR AS (
        SELECT 
            {ticker_column} as ticker, 
            ATR_14,
            ROW_NUMBER() OVER (PARTITION BY {ticker_column} ORDER BY trading_date DESC) as rn
        FROM dbo.{atr_view}
    ),
    
    -- Latest Fibonacci Levels
    LatestFibonacci AS (
        SELECT 
            {ticker_column} as ticker,
            fib_position,
            fib_trade_signal,
            distance_to_nearest_fib_pct,
            ROW_NUMBER() OVER (PARTITION BY {ticker_column} ORDER BY trading_date DESC) as rn
        FROM dbo.{fibonacci_view}
    ),
    
    -- Latest Stochastic Oscillator
    LatestStochastic AS (
        SELECT 
            {ticker_column} as ticker,
            stoch_14d_k,
            stoch_14d_d,
            stoch_status,
            stoch_crossover,
            stoch_trade_signal,
            ROW_NUMBER() OVER (PARTITION BY {ticker_column} ORDER BY trading_date DESC) as rn
        FROM dbo.{stochastic_view}
    ),
    
    -- Latest trading signals (get most recent signal for each indicator)
    LatestSignals AS (
        SELECT DISTINCT
            p.ticker,
            
            -- RSI Signal (latest non-null)
            (SELECT TOP 1 rsi_trade_signal 
             FROM dbo.{rsi_signals} rs 
             WHERE rs.{ticker_column} = p.ticker AND rs.rsi_trade_signal IS NOT NULL
             ORDER BY rs.trading_date DESC) as rsi_signal,
             
            -- MACD Signal (latest non-null)  
            (SELECT TOP 1 MACD_Signal
             FROM dbo.{macd_signals} ms
             WHERE ms.{ticker_column} = p.ticker AND ms.MACD_Signal IS NOT NULL
             ORDER BY ms.trading_date DESC) as macd_signal,
             
            -- BB Signal (latest non-null)
            (SELECT TOP 1 bb_trade_signal
             FROM dbo.{bb_signals} bs  
             WHERE bs.{ticker_column} = p.ticker AND bs.bb_trade_signal IS NOT NULL
             ORDER BY bs.trading_date DESC) as bb_signal,
             
            -- SMA Signal (latest non-null)
            (SELECT TOP 1 sma_trade_signal
             FROM dbo.{sma_signals} ss
             WHERE ss.{ticker_column} = p.ticker AND ss.sma_trade_signal IS NOT NULL  
             ORDER BY ss.trading_date DESC) as sma_signal,
             
            -- ATR Signal (latest non-null)
            (SELECT TOP 1 atr_volatility_signal
             FROM dbo.{atr_signals} ats
             WHERE ats.{ticker_column} = p.ticker AND ats.atr_volatility_signal IS NOT NULL
             ORDER BY ats.trading_date DESC) as atr_signal,
             
            -- MA/SMA Crossover Signal
            (SELECT TOP 1 
                CASE 
                    WHEN SMA_50 > SMA_200 AND LAG(SMA_50) OVER (ORDER BY trading_date) <= LAG(SMA_200) OVER (ORDER BY trading_date) THEN 'GOLDEN_CROSS_BUY'
                    WHEN SMA_50 < SMA_200 AND LAG(SMA_50) OVER (ORDER BY trading_date) >= LAG(SMA_200) OVER (ORDER BY trading_date) THEN 'DEATH_CROSS_SELL'
                    WHEN SMA_50 > SMA_200 THEN 'BULLISH_TREND'
                    WHEN SMA_50 < SMA_200 THEN 'BEARISH_TREND'
                    ELSE NULL
                END
             FROM dbo.{sma_view} sv
             WHERE sv.{ticker_column} = p.ticker
             ORDER BY sv.trading_date DESC) as ma_crossover_signal
             
        FROM (SELECT DISTINCT {ticker_column} as ticker FROM dbo.{base_table}) p
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
        sma.SMA_50,
        sma.SMA_200,
        atr.ATR_14,
        fib.fib_position,
        fib.distance_to_nearest_fib_pct,
        stoch.stoch_14d_k,
        stoch.stoch_14d_d,
        stoch.stoch_status,
        
        -- Trading Signals
        sig.rsi_signal,
        sig.macd_signal,
        sig.bb_signal, 
        sig.sma_signal,
        fib.fib_trade_signal,
        stoch.stoch_trade_signal,
        sig.ma_crossover_signal,
        
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
        
        -- Enhanced Signal Strength Score (-10 to +10) with all indicators
        (
            -- RSI contribution 
            CASE 
                WHEN sig.rsi_signal = 'BUY' OR sig.rsi_signal = 'Buy' THEN 1
                WHEN sig.rsi_signal = 'SELL' OR sig.rsi_signal = 'Sell' THEN -1 
                ELSE 0 
            END +
            
            -- MACD contribution
            CASE 
                WHEN sig.macd_signal = 'BUY' OR sig.macd_signal = 'Buy' THEN 1
                WHEN sig.macd_signal = 'SELL' OR sig.macd_signal = 'Sell' THEN -1
                ELSE 0 
            END +
            
            -- BB contribution
            CASE 
                WHEN sig.bb_signal = 'BUY' OR sig.bb_signal = 'Buy' THEN 1
                WHEN sig.bb_signal = 'SELL' OR sig.bb_signal = 'Sell' THEN -1
                ELSE 0 
            END +
            
            -- SMA contribution
            CASE 
                WHEN sig.sma_signal = 'BUY' OR sig.sma_signal = 'Buy' THEN 1
                WHEN sig.sma_signal = 'SELL' OR sig.sma_signal = 'Sell' THEN -1
                ELSE 0 
            END +
            
            -- Fibonacci contribution (weighted higher for strong signals)
            CASE 
                WHEN fib.fib_trade_signal LIKE '%STRONG_BUY%' THEN 2
                WHEN fib.fib_trade_signal LIKE '%BUY%' THEN 1
                WHEN fib.fib_trade_signal LIKE '%STRONG_SELL%' THEN -2
                WHEN fib.fib_trade_signal LIKE '%SELL%' THEN -1
                ELSE 0 
            END +
            
            -- Stochastic contribution
            CASE 
                WHEN stoch.stoch_trade_signal LIKE '%BUY%' THEN 1
                WHEN stoch.stoch_trade_signal LIKE '%SELL%' THEN -1
                ELSE 0 
            END +
            
            -- MA/SMA Crossover contribution (strong signal)
            CASE 
                WHEN sig.ma_crossover_signal = 'GOLDEN_CROSS_BUY' THEN 2
                WHEN sig.ma_crossover_signal = 'BULLISH_TREND' THEN 1
                WHEN sig.ma_crossover_signal = 'DEATH_CROSS_SELL' THEN -2
                WHEN sig.ma_crossover_signal = 'BEARISH_TREND' THEN -1
                ELSE 0 
            END +
            
            -- Overall trend contribution
            CASE 
                WHEN p.close_price > sma.SMA_200 THEN 1
                WHEN p.close_price < sma.SMA_200 THEN -1 
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
    LEFT JOIN LatestFibonacci fib ON p.ticker = fib.ticker AND fib.rn = 1
    LEFT JOIN LatestStochastic stoch ON p.ticker = stoch.ticker AND stoch.rn = 1
    LEFT JOIN LatestSignals sig ON p.ticker = sig.ticker
    WHERE p.rn = 1
    ORDER BY p.ticker
    """
    
    return execute_query_safe(query)

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------

def render_summary_metrics(df: pd.DataFrame):
    """Render the summary metrics at the top"""
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

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render filter controls and return filtered dataframe"""
    if df.empty:
        return df
    
    st.sidebar.subheader("🔍 Flight Status Filters")
    
    # Signal Type Filter (updated for new range)
    signal_types = ['All', 'Strong Buy (6-10)', 'Buy (1-5)', 'Hold (0)', 'Sell (-5 to -1)', 'Strong Sell (-10 to -6)']
    selected_signal = st.sidebar.selectbox("Signal Type", signal_types)
    
    # RSI Status Filter
    rsi_statuses = ['All'] + df['rsi_status'].dropna().unique().tolist()
    selected_rsi = st.sidebar.selectbox("RSI Status", rsi_statuses)
    
    # Trend Filter
    trends = ['All'] + df['long_term_trend'].dropna().unique().tolist()
    selected_trend = st.sidebar.selectbox("Long-term Trend", trends)
    
    # Market Cap Filter
    market_caps = ['All'] + df['market_cap_category'].dropna().unique().tolist()
    selected_cap = st.sidebar.selectbox("Market Cap", market_caps)
    
    # Apply filters
    filtered_df = df.copy()
    
    # Signal filter (updated for -10 to +10 range)
    if selected_signal != 'All':
        if selected_signal == 'Strong Buy (6-10)':
            filtered_df = filtered_df[filtered_df['signal_score'] >= 6]
        elif selected_signal == 'Buy (1-5)':
            filtered_df = filtered_df[(filtered_df['signal_score'] >= 1) & (filtered_df['signal_score'] <= 5)]
        elif selected_signal == 'Hold (0)':
            filtered_df = filtered_df[filtered_df['signal_score'] == 0]
        elif selected_signal == 'Sell (-5 to -1)':
            filtered_df = filtered_df[(filtered_df['signal_score'] <= -1) & (filtered_df['signal_score'] >= -5)]
        elif selected_signal == 'Strong Sell (-10 to -6)':
            filtered_df = filtered_df[filtered_df['signal_score'] <= -6]
    
    # Other filters
    if selected_rsi != 'All':
        filtered_df = filtered_df[filtered_df['rsi_status'] == selected_rsi]
    
    if selected_trend != 'All':
        filtered_df = filtered_df[filtered_df['long_term_trend'] == selected_trend]
    
    if selected_cap != 'All':
        filtered_df = filtered_df[filtered_df['market_cap_category'] == selected_cap]
    
    return filtered_df

def get_signal_color(score):
    """Get color for signal score (updated for -10 to +10 range)"""
    if score >= 6:
        return '#00ff00'  # Strong Green - Strong Buy
    elif score >= 1:
        return '#90ee90'  # Light Green - Buy
    elif score == 0:
        return '#ffff00'  # Yellow - Hold
    elif score >= -5:
        return '#ffa500'  # Orange - Sell
    else:
        return '#ff0000'  # Red - Strong Sell

def get_flight_status_emoji(score):
    """Get emoji for flight status (updated for -10 to +10 range)"""
    if score >= 6:
        return '✈️🟢'  # Ready for takeoff - Strong Buy
    elif score >= 1:
        return '🟢'     # Boarding - Buy
    elif score == 0:
        return '🟡'     # On schedule - Hold
    elif score >= -5:
        return '🟠'     # Delayed - Sell
    else:
        return '🔴'     # Cancelled - Strong Sell

# ----------------------------
# MAIN APP
# ----------------------------

def main():
    st.set_page_config(
        page_title="🛩️ Flight Status Dashboard", 
        layout="wide",
        initial_sidebar_state="expanded"
    )

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
        **Enhanced Signal Score**: -10 to +10 (now includes 7 indicators!)
        - **+6 to +10**: Strong Buy (Multiple strong bullish signals)
        - **+1 to +5**: Buy (Moderate bullish signals)
        - **0**: Hold/Neutral (No clear direction)
        - **-1 to -5**: Sell (Moderate bearish signals)
        - **-6 to -10**: Strong Sell (Multiple strong bearish signals)
        
        **Technical Indicators Included**:
        - **RSI**: Momentum indicator (30-70 normal range)
        - **MACD**: Trend direction and momentum
        - **Bollinger Bands**: Volatility and price extremes
        - **SMA/EMA**: Long-term trend vs 50/200-day averages
        - **Fibonacci Retracements**: Support/resistance levels (weighted 2x for strong signals)
        - **Stochastic Oscillator**: Overbought/oversold conditions
        - **MA Crossover**: Golden/Death cross signals (weighted 2x)
        
        **Data Sources**: Your SQL Server database views (real-time technical analysis)
        """)
    
    # Index Selection
    index_name = st.selectbox(
        "Select Index",
        ["NSE 500", "NASDAQ 100", "Forex"],
        help="Choose which market index to analyze"
    )
    
    # Load data
    with st.spinner(f"🛩️ Loading flight status for {index_name}..."):
        df = load_flight_status_data(index_name, limit=100)  # Limit for performance
    
    if df.empty:
        st.error("❌ No data available. Please check your database connection and table structure.")
        return
    
    # Summary metrics
    render_summary_metrics(df)
    
    st.markdown("---")
    
    # Apply filters
    filtered_df = apply_filters(df)
    
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
                help='Combined signal strength (-10 to +10) - includes RSI, MACD, BB, SMA, Fibonacci, Stochastic, MA Crossover',
                min_value=-10,
                max_value=10,
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
    if st.button("📥 Export to CSV"):
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="💾 Download CSV",
            data=csv,
            file_name=f"flight_status_{index_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
