"""
"""
FLIGHT STATUS DASHBOARD for Stock Analysis
Displays all stocks in a single table with technical indicators and trading recommendations
Author: Assistant
Date: 2024

This dashboard provides a "flight status board" view of all stocks with their technical analysis.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# Import your existing database functions
# (You can copy the connection functions from your streamlitapp_20251123_v2.py)

# Database connection functions copied from main app
@st.cache_resource
def get_connection_pool():
    """Database connection pool with working configuration"""
    connection_string = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost\\MSSQLSERVER01;'
        'DATABASE=stockdata_db;'
        'Trusted_Connection=yes;'
        'MARS_Connection=yes;'  # Enable Multiple Active Result Sets
        'Connection Timeout=30;'
        'Command Timeout=30;'
        'MultipleActiveResultSets=true;'  # Additional MARS setting
        'Pooling=true;'  # Enable connection pooling
    )
    return connection_string

def get_connection():
    """Create a new database connection with enhanced error handling"""
    try:
        import pyodbc
        connection_string = get_connection_pool()
        conn = pyodbc.connect(connection_string)
        conn.timeout = 30
        conn.autocommit = True  # Prevent transaction locks
        return conn
    except Exception as e:
        st.error(f"Database connection error: {str(e)}")
        return None

def execute_query_safe(query: str, params: list = None) -> pd.DataFrame:
    """Your existing safe query execution"""
    import pyodbc
    import time
    
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
        rsi_view = 'nse_500_RSI_calculation' 
        macd_view = 'nse_500_macd'
        bb_view = 'nse_500_bollingerband'
        sma_view = 'nse_500_ema_sma_view'
        atr_view = 'nse_500_atr'
        
        # Signal views
        rsi_signals = 'nse_500_rsi_signals'
        macd_signals = 'nse_500_macd_signals'
        bb_signals = 'nse_500_bb_signals' 
        sma_signals = 'nse_500_sma_signals'
        atr_signals = 'nse_500_atr_spikes'
    else:  # NASDAQ 100
        base_table = 'nasdaq_100_hist_data'
        rsi_view = 'nasdaq_100_RSI_calculation'
        macd_view = 'nasdaq_100_macd'
        bb_view = 'nasdaq_100_bollingerband' 
        sma_view = 'nasdaq_100_ema_sma_view'
        atr_view = 'nasdaq_100_atr'
        
        rsi_signals = 'nasdaq_100_rsi_signals'
        macd_signals = 'nasdaq_100_macd_signals'
        bb_signals = 'nasdaq_100_bb_signals'
        sma_signals = 'nasdaq_100_sma_signals'
        atr_signals = 'nasdaq_100_atr_spikes'
    
    limit_clause = f"TOP {limit}" if limit else ""
    
    # Single comprehensive query - this is where the magic happens!
    query = f"""
    WITH 
    -- Get latest price data for each stock
    LatestPrices AS (
        SELECT 
            ticker,
            company,
            trading_date,
            CAST(close_price AS FLOAT) AS close_price,
            CAST(open_price AS FLOAT) AS open_price,
            CAST(high_price AS FLOAT) AS high_price,
            CAST(low_price AS FLOAT) AS low_price,
            CAST(volume AS FLOAT) AS volume,
            -- Calculate daily change
            ROUND(((CAST(close_price AS FLOAT) - CAST(open_price AS FLOAT)) / CAST(open_price AS FLOAT)) * 100, 2) as daily_change_pct,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
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
            ticker, 
            ATR_14,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
        FROM dbo.{atr_view}
    ),
    
    -- Latest trading signals (get most recent signal for each indicator)
    LatestSignals AS (
        SELECT DISTINCT
            p.ticker,
            
            -- RSI Signal (latest non-null)
            (SELECT TOP 1 rsi_trade_signal 
             FROM dbo.{rsi_signals} rs 
             WHERE rs.ticker = p.ticker AND rs.rsi_trade_signal IS NOT NULL
             ORDER BY rs.trading_date DESC) as rsi_signal,
             
            -- MACD Signal (latest non-null)  
            (SELECT TOP 1 MACD_Signal
             FROM dbo.{macd_signals} ms
             WHERE ms.ticker = p.ticker AND ms.MACD_Signal IS NOT NULL
             ORDER BY ms.trading_date DESC) as macd_signal,
             
            -- BB Signal (latest non-null)
            (SELECT TOP 1 bb_trade_signal
             FROM dbo.{bb_signals} bs  
             WHERE bs.ticker = p.ticker AND bs.bb_trade_signal IS NOT NULL
             ORDER BY bs.trading_date DESC) as bb_signal,
             
            -- SMA Signal (latest non-null)
            (SELECT TOP 1 sma_trade_signal
             FROM dbo.{sma_signals} ss
             WHERE ss.ticker = p.ticker AND ss.sma_trade_signal IS NOT NULL  
             ORDER BY ss.trading_date DESC) as sma_signal,
             
            -- ATR Signal (latest non-null)
            (SELECT TOP 1 atr_volatility_signal
             FROM dbo.{atr_signals} ats
             WHERE ats.ticker = p.ticker AND ats.atr_volatility_signal IS NOT NULL
             ORDER BY ats.trading_date DESC) as atr_signal
             
        FROM (SELECT DISTINCT ticker FROM dbo.{base_table}) p
    )
    
    -- Main query combining all data
    SELECT {limit_clause}
        p.ticker,
        p.company,
        p.trading_date as last_update,
        p.close_price,
        p.open_price,
        p.high_price,
        p.low_price,
        p.volume,
        p.daily_change_pct,
        
        -- Technical Indicators
        r.RSI,
        m.MACD,
        m.Signal_Line as MACD_Signal_Line,
        bb.Upper_Band as bb_upper,
        bb.Lower_Band as bb_lower,  
        sma.SMA_50,
        sma.SMA_200,
        sma.EMA_50,
        atr.ATR_14,
        
        -- Trading Signals
        sig.rsi_signal,
        sig.macd_signal,
        sig.bb_signal, 
        sig.sma_signal,
        sig.atr_signal,
        
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
        
        -- Bollinger Band Position (0-100%)
        CASE 
            WHEN bb.Upper_Band IS NOT NULL AND bb.Lower_Band IS NOT NULL AND bb.Upper_Band != bb.Lower_Band THEN
                ROUND(((p.close_price - bb.Lower_Band) / (bb.Upper_Band - bb.Lower_Band)) * 100, 1)
            ELSE 50.0
        END as bb_position_pct,
        
        -- Signal Strength Score (-5 to +5)
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
            
            -- RSI level contribution (independent of signal)
            CASE 
                WHEN r.RSI < 30 THEN 1  -- Oversold = potential buy
                WHEN r.RSI > 70 THEN -1 -- Overbought = potential sell
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
    LEFT JOIN LatestSignals sig ON p.ticker = sig.ticker
    WHERE p.rn = 1
    ORDER BY p.ticker
    """
    
    df = execute_query_safe(query)
    
    if not df.empty:
        # Convert date column
        df['last_update'] = pd.to_datetime(df['last_update'])
        
        # Add overall recommendation based on signal score
        def get_recommendation(score):
            if pd.isna(score):
                return '🟡 Hold'
            elif score >= 4:
                return '🟢 Strong Buy'
            elif score >= 2: 
                return '🟢 Buy'
            elif score >= 1:
                return '🟢 Weak Buy'
            elif score <= -4:
                return '🔴 Strong Sell'
            elif score <= -2:
                return '🔴 Sell'
            elif score <= -1:
                return '🔴 Weak Sell'
            else:
                return '🟡 Hold'
        
        df['recommendation'] = df['signal_score'].apply(get_recommendation)
        
        # Add risk level based on ATR
        if 'ATR_14' in df.columns:
            atr_median = df['ATR_14'].median()
            df['risk_level'] = df['ATR_14'].apply(
                lambda x: 'High' if pd.notna(x) and x > atr_median * 1.5 
                         else 'Low' if pd.notna(x) and x < atr_median * 0.7
                         else 'Medium'
            )
    
    return df

# ----------------------------
# DASHBOARD UI FUNCTIONS
# ----------------------------

def render_summary_dashboard(df: pd.DataFrame):
    """Render the summary metrics at the top"""
    if df.empty:
        return
    
    st.markdown("### 📊 Market Summary")
    
    # Calculate summary statistics
    total_stocks = len(df)
    bullish_stocks = len(df[df['signal_score'] > 0])
    bearish_stocks = len(df[df['signal_score'] < 0])
    neutral_stocks = total_stocks - bullish_stocks - bearish_stocks
    
    # Performance metrics
    avg_change = df['daily_change_pct'].mean() if 'daily_change_pct' in df.columns else 0
    avg_rsi = df['RSI'].mean() if 'RSI' in df.columns and not df['RSI'].isna().all() else 50
    
    # Market condition
    if avg_change > 1:
        market_mood = "🟢 Bullish"
    elif avg_change < -1:
        market_mood = "🔴 Bearish"
    else:
        market_mood = "🟡 Mixed"
    
    # Display metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("📈 Total Stocks", total_stocks)
    with col2:
        bullish_pct = (bullish_stocks/total_stocks*100) if total_stocks > 0 else 0
        st.metric("🟢 Bullish", bullish_stocks, f"{bullish_pct:.1f}%")
    with col3:
        bearish_pct = (bearish_stocks/total_stocks*100) if total_stocks > 0 else 0  
        st.metric("🔴 Bearish", bearish_stocks, f"{bearish_pct:.1f}%")
    with col4:
        st.metric("🟡 Neutral", neutral_stocks)
    with col5:
        st.metric("📊 Avg Daily %", f"{avg_change:.2f}%")
    with col6:
        st.metric("🎯 Market Mood", market_mood)

def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render filter controls and return filtered dataframe"""
    st.markdown("### 🔍 Filters")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        signal_filter = st.selectbox(
            "Signal Type",
            ["All"] + sorted(df['recommendation'].dropna().unique().tolist()),
            key="signal_filter"
        )
    
    with col2:
        rsi_filter = st.selectbox(
            "RSI Status", 
            ["All"] + sorted(df['rsi_status'].dropna().unique().tolist()),
            key="rsi_filter"
        )
    
    with col3:
        trend_filter = st.selectbox(
            "Long Term Trend",
            ["All"] + sorted(df['long_term_trend'].dropna().unique().tolist()),
            key="trend_filter"
        )
    
    with col4:
        if 'market_cap_category' in df.columns:
            cap_filter = st.selectbox(
                "Market Cap",
                ["All"] + sorted(df['market_cap_category'].dropna().unique().tolist()),
                key="cap_filter"
            )
        else:
            cap_filter = "All"
    
    # Apply filters
    filtered_df = df.copy()
    
    if signal_filter != "All":
        filtered_df = filtered_df[filtered_df['recommendation'] == signal_filter]
    
    if rsi_filter != "All":
        filtered_df = filtered_df[filtered_df['rsi_status'] == rsi_filter]
    
    if trend_filter != "All":
        filtered_df = filtered_df[filtered_df['long_term_trend'] == trend_filter]
    
    if cap_filter != "All" and 'market_cap_category' in df.columns:
        filtered_df = filtered_df[filtered_df['market_cap_category'] == cap_filter]
    
    # Additional numeric filters
    with st.expander("📊 Advanced Filters"):
        col_a, col_b = st.columns(2)
        
        with col_a:
            if 'RSI' in df.columns:
                rsi_range = st.slider(
                    "RSI Range",
                    float(df['RSI'].min()) if not df['RSI'].isna().all() else 0.0,
                    float(df['RSI'].max()) if not df['RSI'].isna().all() else 100.0,
                    (0.0, 100.0),
                    key="rsi_range"
                )
                filtered_df = filtered_df[
                    (filtered_df['RSI'] >= rsi_range[0]) & 
                    (filtered_df['RSI'] <= rsi_range[1])
                ]
        
        with col_b:
            if 'daily_change_pct' in df.columns:
                change_range = st.slider(
                    "Daily Change % Range", 
                    float(df['daily_change_pct'].min()) if not df['daily_change_pct'].isna().all() else -10.0,
                    float(df['daily_change_pct'].max()) if not df['daily_change_pct'].isna().all() else 10.0,
                    (-10.0, 10.0),
                    key="change_range"
                )
                filtered_df = filtered_df[
                    (filtered_df['daily_change_pct'] >= change_range[0]) & 
                    (filtered_df['daily_change_pct'] <= change_range[1])
                ]
    
    return filtered_df

def render_flight_status_table(df: pd.DataFrame):
    """Render the main flight status table"""
    if df.empty:
        st.warning("No stocks match the selected filters.")
        return
    
    st.markdown(f"### 🛩️ Flight Status Board - {len(df)} Stocks")
    
    # Prepare display dataframe
    display_columns = [
        'ticker', 'company', 'close_price', 'daily_change_pct',
        'RSI', 'rsi_status', 'macd_trend', 'long_term_trend',
        'signal_score', 'recommendation'
    ]
    
    # Add optional columns if they exist
    optional_columns = ['bb_position_pct', 'ATR_14', 'risk_level', 'market_cap_category', 'last_update']
    for col in optional_columns:
        if col in df.columns:
            display_columns.append(col)
    
    # Filter to existing columns
    display_columns = [col for col in display_columns if col in df.columns]
    display_df = df[display_columns].copy()
    
    # Round numeric columns
    numeric_columns = ['close_price', 'daily_change_pct', 'RSI', 'signal_score', 'bb_position_pct', 'ATR_14']
    for col in numeric_columns:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(2)
    
    # Rename columns for better display
    column_names = {
        'ticker': 'Ticker',
        'company': 'Company',
        'close_price': 'Price ($)',
        'daily_change_pct': 'Change %',
        'RSI': 'RSI',
        'rsi_status': 'RSI Status',
        'macd_trend': 'MACD',
        'long_term_trend': 'Trend',
        'signal_score': 'Score',
        'recommendation': 'Signal',
        'bb_position_pct': 'BB %',
        'ATR_14': 'ATR',
        'risk_level': 'Risk',
        'market_cap_category': 'Cap',
        'last_update': 'Updated'
    }
    display_df.rename(columns=column_names, inplace=True)
    
    # Color coding function
    def color_row(row):
        styles = [''] * len(row)
        
        # Color daily change
        if 'Change %' in row.index and pd.notna(row['Change %']):
            if row['Change %'] > 0:
                styles[row.index.get_loc('Change %')] = 'color: green; font-weight: bold'
            elif row['Change %'] < 0:
                styles[row.index.get_loc('Change %')] = 'color: red; font-weight: bold'
        
        # Color RSI status
        if 'RSI Status' in row.index:
            if row['RSI Status'] == 'Overbought':
                styles[row.index.get_loc('RSI Status')] = 'background-color: #ffcccb'
            elif row['RSI Status'] == 'Oversold':
                styles[row.index.get_loc('RSI Status')] = 'background-color: #90EE90'
        
        # Color signals
        if 'Signal' in row.index and pd.notna(row['Signal']):
            if 'Buy' in str(row['Signal']):
                styles[row.index.get_loc('Signal')] = 'background-color: #90EE90; color: green; font-weight: bold'
            elif 'Sell' in str(row['Signal']):
                styles[row.index.get_loc('Signal')] = 'background-color: #ffcccb; color: red; font-weight: bold'
            else:  # Hold
                styles[row.index.get_loc('Signal')] = 'background-color: #FFFFE0'
        
        # Color score
        if 'Score' in row.index and pd.notna(row['Score']):
            score = row['Score'] 
            if score > 0:
                styles[row.index.get_loc('Score')] = 'color: green; font-weight: bold'
            elif score < 0:
                styles[row.index.get_loc('Score')] = 'color: red; font-weight: bold'
        
        return styles
    
    # Display styled table
    styled_df = display_df.style.apply(color_row, axis=1)
    
    # Show table with pagination option
    if len(display_df) > 50:
        show_all = st.checkbox("Show all stocks (may be slow for large datasets)")
        if not show_all:
            styled_df = styled_df.head(50)
            st.info(f"Showing first 50 of {len(display_df)} stocks. Check 'Show all' to see more.")
    
    st.dataframe(styled_df, use_container_width=True, height=600)
    
    # Download option
    csv = df.to_csv(index=False)
    st.download_button(
        label="📊 Download Full Results (CSV)",
        data=csv,
        file_name=f"flight_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        help="Download the complete dataset with all technical indicators"
    )

def render_analytics_section(df: pd.DataFrame):
    """Render analytics charts and insights"""
    if df.empty:
        return
    
    st.markdown("### 📊 Market Analytics")
    
    tab1, tab2, tab3 = st.tabs(["📈 Distribution", "🎯 Correlations", "🏆 Top Performers"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Signal distribution
            if 'recommendation' in df.columns:
                signal_counts = df['recommendation'].value_counts()
                fig_pie = px.pie(
                    values=signal_counts.values,
                    names=signal_counts.index,
                    title="Trading Signal Distribution",
                    color_discrete_map={
                        '🟢 Strong Buy': '#2e8b57',
                        '🟢 Buy': '#32cd32', 
                        '🟢 Weak Buy': '#90ee90',
                        '🟡 Hold': '#ffd700',
                        '🔴 Weak Sell': '#ffa07a',
                        '🔴 Sell': '#ff6347',
                        '🔴 Strong Sell': '#dc143c'
                    }
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # RSI distribution
            if 'RSI' in df.columns and not df['RSI'].isna().all():
                fig_hist = px.histogram(
                    df,
                    x='RSI',
                    nbins=30,
                    title="RSI Distribution Across All Stocks",
                    labels={'RSI': 'RSI Level', 'count': 'Number of Stocks'}
                )
                fig_hist.add_vline(x=30, line_dash="dash", line_color="green", annotation_text="Oversold")
                fig_hist.add_vline(x=70, line_dash="dash", line_color="red", annotation_text="Overbought")
                st.plotly_chart(fig_hist, use_container_width=True)
    
    with tab2:
        # Scatter plots
        if all(col in df.columns for col in ['RSI', 'close_price', 'daily_change_pct']):
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_scatter1 = px.scatter(
                    df,
                    x='RSI',
                    y='daily_change_pct',
                    color='recommendation',
                    hover_data=['ticker'],
                    title="Daily Performance vs RSI",
                    labels={'daily_change_pct': 'Daily Change %', 'RSI': 'RSI Level'}
                )
                fig_scatter1.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_scatter1.add_vline(x=30, line_dash="dash", line_color="green")
                fig_scatter1.add_vline(x=70, line_dash="dash", line_color="red")
                st.plotly_chart(fig_scatter1, use_container_width=True)
            
            with col2:
                if 'signal_score' in df.columns:
                    fig_scatter2 = px.scatter(
                        df,
                        x='signal_score', 
                        y='daily_change_pct',
                        color='rsi_status',
                        hover_data=['ticker'],
                        title="Signal Score vs Performance",
                        labels={'signal_score': 'Signal Score', 'daily_change_pct': 'Daily Change %'}
                    )
                    fig_scatter2.add_hline(y=0, line_dash="dash", line_color="gray")
                    fig_scatter2.add_vline(x=0, line_dash="dash", line_color="gray")
                    st.plotly_chart(fig_scatter2, use_container_width=True)
    
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🚀 Top Gainers Today")
            if 'daily_change_pct' in df.columns:
                top_gainers = df.nlargest(10, 'daily_change_pct')[
                    ['ticker', 'company', 'daily_change_pct', 'recommendation', 'RSI']
                ].round(2)
                st.dataframe(top_gainers, use_container_width=True)
        
        with col2:
            st.markdown("#### 📉 Top Losers Today") 
            if 'daily_change_pct' in df.columns:
                top_losers = df.nsmallest(10, 'daily_change_pct')[
                    ['ticker', 'company', 'daily_change_pct', 'recommendation', 'RSI']
                ].round(2)
                st.dataframe(top_losers, use_container_width=True)
        
        # Strong signals
        st.markdown("#### ⚡ Strongest Signals")
        col_a, col_b = st.columns(2)
        
        with col_a:
            if 'signal_score' in df.columns:
                strongest_buy = df[df['signal_score'] > 0].nlargest(10, 'signal_score')[
                    ['ticker', 'signal_score', 'recommendation', 'RSI', 'daily_change_pct']
                ].round(2)
                st.markdown("**🟢 Strongest Buy Signals**")
                st.dataframe(strongest_buy, use_container_width=True)
        
        with col_b:
            if 'signal_score' in df.columns:
                strongest_sell = df[df['signal_score'] < 0].nsmallest(10, 'signal_score')[
                    ['ticker', 'signal_score', 'recommendation', 'RSI', 'daily_change_pct']
                ].round(2)
                st.markdown("**🔴 Strongest Sell Signals**")
                st.dataframe(strongest_sell, use_container_width=True)

# ----------------------------
# MAIN APP
# ----------------------------

def main():
    st.set_page_config(
        page_title="🛩️ Flight Status Stock Dashboard",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Header
    st.title("🛩️ Flight Status Stock Dashboard")
    st.markdown("""
    **Real-time stock analysis across your entire portfolio - Just like tracking flights at the airport!**
    
    Each stock shows its current "departure status":
    - 🟢 **Buy Signals**: Ready for takeoff (good entry opportunities)
    - 🔴 **Sell Signals**: Delayed/cancelled (consider exit strategies)  
    - 🟡 **Hold**: On schedule (maintain current positions)
    """)
    
    # Sidebar
    with st.sidebar:
        st.header("🎛️ Dashboard Settings")
        
        # Market selection
        index_option = st.selectbox(
            "📊 Select Market",
            ["NSE 500", "NASDAQ 100"],
            help="Choose which stock index to analyze"
        )
        
        # Performance settings
        st.subheader("⚙️ Performance")
        enable_limit = st.checkbox("Limit stocks (for testing)", value=False)
        stock_limit = None
        if enable_limit:
            stock_limit = st.slider("Max stocks to load", 10, 100, 50)
        
        # Auto-refresh
        auto_refresh = st.checkbox("🔄 Auto-refresh (5 min)", value=False)
        
        # Manual refresh
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.experimental_rerun()
        
        st.markdown("---")
        
        # Info
        st.markdown("""
        ### 📖 Quick Guide
        
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
        - **BB%**: Position in Bollinger Bands
        
        **Data Sources**: Your SQL Server database views
        """)
    
    # Main content
    try:
        # Load data
        with st.spinner(f"Loading {index_option} flight status data..."):
            df = load_flight_status_data(index_option, limit=stock_limit)
        
        if df.empty:
            st.error("❌ No data available. Please check your database connection.")
            return
        
        # Show data freshness
        if 'last_update' in df.columns and not df['last_update'].isna().all():
            latest_update = df['last_update'].max()
            time_diff = datetime.now() - latest_update
            st.info(f"📅 Data last updated: {latest_update.strftime('%Y-%m-%d %H:%M')} "
                   f"({time_diff.days} days, {time_diff.seconds//3600} hours ago)")
        
        # Render dashboard sections
        render_summary_dashboard(df)
        
        st.markdown("---")
        
        # Filters
        filtered_df = render_filters(df)
        
        st.markdown("---")
        
        # Main table
        render_flight_status_table(filtered_df)
        
        st.markdown("---")
        
        # Analytics
        render_analytics_section(filtered_df)
        
    except Exception as e:
        st.error(f"❌ Error loading dashboard: {str(e)}")
        st.info("Please ensure your database is running and accessible.")
    
    # Auto-refresh logic
    if auto_refresh:
        import time
        time.sleep(300)  # 5 minutes
        st.experimental_rerun()

if __name__ == "__main__":
    main()
