"""
ENHANCED VERSION of your existing streamlit app with Flight Status Dashboard added
This integrates the multi-stock flight status view with your existing single-stock analysis

Integration Instructions:
1. Add this code to your existing streamlitapp_20251123_v2.py
2. Or use this as a standalone enhanced version
"""

# Import all your existing functions and libraries
import streamlit as st
import pyodbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import time
import io
import base64

# Import your existing functions (copy from streamlitapp_20251123_v2.py)
# ... [All your existing DB connection and indicator functions] ...

# For brevity, I'll include just the essential connection functions
# Copy your complete functions from the original file

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

def execute_query_safe(query: str, params: list = None) -> pd.DataFrame:
    """Safe database query execution with proper error handling"""
    import pyodbc
    import time
    
    conn = None
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            connection_string = get_connection_pool()
            conn = pyodbc.connect(connection_string)
            conn.timeout = 30
            conn.autocommit = True
            
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
# FLIGHT STATUS DASHBOARD FUNCTIONS
# ----------------------------

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_flight_status_data(index_name: str, limit: int = None) -> pd.DataFrame:
    """
    Load comprehensive multi-stock data for flight status dashboard
    """
    
    # Map to your existing table and view names
    if index_name == 'NSE 500':
        base_table = 'nse_500_hist_data'
        rsi_view = 'nse_500_RSI_calculation' 
        macd_view = 'nse_500_macd'
        bb_view = 'nse_500_bollingerband'
        sma_view = 'nse_500_ema_sma_view'
        atr_view = 'nse_500_atr'
        rsi_signals = 'nse_500_rsi_signals'
        macd_signals = 'nse_500_macd_signals'
        bb_signals = 'nse_500_bb_signals' 
        sma_signals = 'nse_500_sma_signals'
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
    
    limit_clause = f"TOP {limit}" if limit else ""
    
    # Optimized single query for all stock data
    query = f"""
    WITH 
    LatestPrices AS (
        SELECT 
            ticker, company, trading_date,
            CAST(close_price AS FLOAT) AS close_price,
            CAST(open_price AS FLOAT) AS open_price,
            CAST(volume AS FLOAT) AS volume,
            ROUND(((CAST(close_price AS FLOAT) - CAST(open_price AS FLOAT)) / CAST(open_price AS FLOAT)) * 100, 2) as daily_change_pct,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
        FROM dbo.{base_table}
    ),
    LatestRSI AS (
        SELECT ticker, RSI,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
        FROM dbo.{rsi_view}
    ),
    LatestMACD AS (
        SELECT ticker, MACD, Signal_Line,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
        FROM dbo.{macd_view}
    ),
    LatestSMA AS (
        SELECT ticker, SMA_50, SMA_200,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
        FROM dbo.{sma_view}
    ),
    LatestSignals AS (
        SELECT DISTINCT
            p.ticker,
            (SELECT TOP 1 rsi_trade_signal FROM dbo.{rsi_signals} rs WHERE rs.ticker = p.ticker AND rs.rsi_trade_signal IS NOT NULL ORDER BY rs.trading_date DESC) as rsi_signal,
            (SELECT TOP 1 MACD_Signal FROM dbo.{macd_signals} ms WHERE ms.ticker = p.ticker AND ms.MACD_Signal IS NOT NULL ORDER BY ms.trading_date DESC) as macd_signal,
            (SELECT TOP 1 bb_trade_signal FROM dbo.{bb_signals} bs WHERE bs.ticker = p.ticker AND bs.bb_trade_signal IS NOT NULL ORDER BY bs.trading_date DESC) as bb_signal,
            (SELECT TOP 1 sma_trade_signal FROM dbo.{sma_signals} ss WHERE ss.ticker = p.ticker AND ss.sma_trade_signal IS NOT NULL ORDER BY ss.trading_date DESC) as sma_signal
        FROM (SELECT DISTINCT ticker FROM dbo.{base_table}) p
    )
    
    SELECT {limit_clause}
        p.ticker, p.company, p.trading_date as last_update,
        p.close_price, p.daily_change_pct, p.volume,
        r.RSI, m.MACD, m.Signal_Line, sma.SMA_50, sma.SMA_200,
        sig.rsi_signal, sig.macd_signal, sig.bb_signal, sig.sma_signal,
        
        -- Analysis fields
        CASE WHEN r.RSI > 70 THEN 'Overbought' WHEN r.RSI < 30 THEN 'Oversold' ELSE 'Neutral' END as rsi_status,
        CASE WHEN m.MACD > m.Signal_Line THEN 'Bullish' ELSE 'Bearish' END as macd_trend,
        CASE WHEN p.close_price > sma.SMA_200 THEN 'Uptrend' ELSE 'Downtrend' END as long_term_trend,
        
        -- Signal Score
        (
            CASE WHEN sig.rsi_signal IN ('BUY', 'Buy') THEN 1 WHEN sig.rsi_signal IN ('SELL', 'Sell') THEN -1 ELSE 0 END +
            CASE WHEN sig.macd_signal IN ('BUY', 'Buy') THEN 1 WHEN sig.macd_signal IN ('SELL', 'Sell') THEN -1 ELSE 0 END +
            CASE WHEN sig.bb_signal IN ('BUY', 'Buy') THEN 1 WHEN sig.bb_signal IN ('SELL', 'Sell') THEN -1 ELSE 0 END +
            CASE WHEN sig.sma_signal IN ('BUY', 'Buy') THEN 1 WHEN sig.sma_signal IN ('SELL', 'Sell') THEN -1 ELSE 0 END +
            CASE WHEN r.RSI < 30 THEN 1 WHEN r.RSI > 70 THEN -1 ELSE 0 END
        ) as signal_score
        
    FROM LatestPrices p
    LEFT JOIN LatestRSI r ON p.ticker = r.ticker AND r.rn = 1
    LEFT JOIN LatestMACD m ON p.ticker = m.ticker AND m.rn = 1
    LEFT JOIN LatestSMA sma ON p.ticker = sma.ticker AND sma.rn = 1
    LEFT JOIN LatestSignals sig ON p.ticker = sig.ticker
    WHERE p.rn = 1
    ORDER BY p.ticker
    """
    
    df = execute_query_safe(query)
    
    if not df.empty:
        df['last_update'] = pd.to_datetime(df['last_update'])
        
        # Add recommendations
        def get_recommendation(score):
            if pd.isna(score):
                return '🟡 Hold'
            elif score >= 3: return '🟢 Strong Buy'
            elif score >= 1: return '🟢 Buy'
            elif score <= -3: return '🔴 Strong Sell'
            elif score <= -1: return '🔴 Sell'
            else: return '🟡 Hold'
        
        df['recommendation'] = df['signal_score'].apply(get_recommendation)
    
    return df

def show_flight_status_page():
    """Main flight status dashboard page"""
    
    st.title("🛩️ Multi-Stock Flight Status Dashboard")
    st.markdown("""
    **Track all your stocks like flights at the airport!**
    
    🟢 **Buy Signals**: Ready for takeoff (good entry opportunities)  
    🔴 **Sell Signals**: Delayed flights (consider exit strategies)  
    🟡 **Hold**: On schedule (maintain positions)
    """)
    
    # Check if we have market selection in session state
    if 'index_option' not in st.session_state:
        st.warning("👈 Please select a market from the Home & Filters page first.")
        return
    
    index_option = st.session_state.index_option
    
    # Controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        enable_limit = st.checkbox("🔢 Limit stocks (for testing)", value=False)
        stock_limit = None
        if enable_limit:
            stock_limit = st.slider("Max stocks", 10, 100, 50)
    
    with col2:
        auto_refresh = st.checkbox("🔄 Auto-refresh (5 min)")
    
    with col3:
        if st.button("🔄 Refresh Now"):
            st.cache_data.clear()
            st.experimental_rerun()
    
    # Load data
    with st.spinner(f"Loading {index_option} flight status data..."):
        df = load_flight_status_data(index_option, limit=stock_limit)
    
    if df.empty:
        st.error("❌ No data available. Check your database connection.")
        return
    
    # Show data freshness
    if 'last_update' in df.columns and not df['last_update'].isna().all():
        latest_update = df['last_update'].max()
        st.info(f"📅 Data last updated: {latest_update}")
    
    # Summary metrics
    st.markdown("### 📊 Market Summary")
    
    total_stocks = len(df)
    bullish_stocks = len(df[df['signal_score'] > 0])
    bearish_stocks = len(df[df['signal_score'] < 0])
    neutral_stocks = total_stocks - bullish_stocks - bearish_stocks
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
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
        avg_rsi = df['RSI'].mean() if not df['RSI'].isna().all() else 50
        st.metric("📊 Avg RSI", f"{avg_rsi:.1f}")
    
    # Filters
    st.markdown("### 🔍 Flight Status Filters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        signal_filter = st.selectbox("Signal Type", ["All"] + sorted(df['recommendation'].dropna().unique().tolist()))
    with col2:
        rsi_filter = st.selectbox("RSI Status", ["All"] + sorted(df['rsi_status'].dropna().unique().tolist()))
    with col3:
        trend_filter = st.selectbox("Trend", ["All"] + sorted(df['long_term_trend'].dropna().unique().tolist()))
    
    # Apply filters
    filtered_df = df.copy()
    
    if signal_filter != "All":
        filtered_df = filtered_df[filtered_df['recommendation'] == signal_filter]
    if rsi_filter != "All":
        filtered_df = filtered_df[filtered_df['rsi_status'] == rsi_filter]
    if trend_filter != "All":
        filtered_df = filtered_df[filtered_df['long_term_trend'] == trend_filter]
    
    st.markdown(f"**Showing {len(filtered_df)} of {len(df)} stocks**")
    
    # Main flight status table
    if not filtered_df.empty:
        st.markdown("### 🛩️ Flight Status Board")
        
        # Prepare display
        display_df = filtered_df[[
            'ticker', 'company', 'close_price', 'daily_change_pct', 
            'RSI', 'rsi_status', 'macd_trend', 'long_term_trend',
            'signal_score', 'recommendation'
        ]].copy()
        
        # Round numeric columns
        for col in ['close_price', 'daily_change_pct', 'RSI', 'signal_score']:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(2)
        
        # Rename for display
        display_df.columns = [
            'Ticker', 'Company', 'Price', 'Daily %', 
            'RSI', 'RSI Status', 'MACD', 'Trend',
            'Score', 'Signal'
        ]
        
        # Show with color coding
        def highlight_row(row):
            styles = [''] * len(row)
            
            # Color daily change
            if 'Daily %' in row.index and pd.notna(row['Daily %']):
                if row['Daily %'] > 0:
                    styles[row.index.get_loc('Daily %')] = 'color: green; font-weight: bold'
                elif row['Daily %'] < 0:
                    styles[row.index.get_loc('Daily %')] = 'color: red; font-weight: bold'
            
            # Color RSI status  
            if 'RSI Status' in row.index:
                if row['RSI Status'] == 'Overbought':
                    styles[row.index.get_loc('RSI Status')] = 'background-color: #ffcccb'
                elif row['RSI Status'] == 'Oversold':
                    styles[row.index.get_loc('RSI Status')] = 'background-color: #90EE90'
            
            # Color signals
            if 'Signal' in row.index and pd.notna(row['Signal']):
                if 'Buy' in str(row['Signal']):
                    styles[row.index.get_loc('Signal')] = 'background-color: #90EE90; font-weight: bold'
                elif 'Sell' in str(row['Signal']):
                    styles[row.index.get_loc('Signal')] = 'background-color: #ffcccb; font-weight: bold'
            
            return styles
        
        styled_df = display_df.style.apply(highlight_row, axis=1)
        st.dataframe(styled_df, use_container_width=True, height=600)
        
        # Download button
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            "📊 Download Results (CSV)",
            data=csv,
            file_name=f"flight_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    # Quick analytics
    st.markdown("### 📊 Quick Analytics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Signal pie chart
        signal_counts = filtered_df['recommendation'].value_counts()
        fig_pie = px.pie(
            values=signal_counts.values,
            names=signal_counts.index,
            title="Signal Distribution"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Top movers
        st.markdown("#### 🚀 Top Movers")
        if 'daily_change_pct' in filtered_df.columns:
            top_gainers = filtered_df.nlargest(5, 'daily_change_pct')[['ticker', 'daily_change_pct', 'recommendation']]
            top_losers = filtered_df.nsmallest(5, 'daily_change_pct')[['ticker', 'daily_change_pct', 'recommendation']]
            
            st.markdown("**📈 Top Gainers**")
            st.dataframe(top_gainers, use_container_width=True)
            
            st.markdown("**📉 Top Losers**")
            st.dataframe(top_losers, use_container_width=True)
    
    # Auto-refresh
    if auto_refresh:
        time.sleep(300)  # 5 minutes
        st.experimental_rerun()

# ----------------------------
# ENHANCED MAIN APP WITH NAVIGATION
# ----------------------------

def show_home_page():
    """Enhanced home page with market selection"""
    st.title("📊 Enhanced Stock Analysis Dashboard")
    st.markdown("""
    ### Welcome to your comprehensive stock analysis platform!
    
    **New Feature: 🛩️ Flight Status Dashboard** - Track all stocks at once!
    
    Choose your market and explore:
    """)
    
    # Market selection
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Select Market Index")
        index_option = st.radio(
            "Choose your market:",
            ["NSE 500", "NASDAQ 100"],
            key="index_selection"
        )
        
        # Store in session state for other pages
        st.session_state.index_option = index_option
        
        # Date range selection
        st.markdown("#### 📅 Date Range")
        end_date = st.date_input("End Date", value=datetime.now().date())
        start_date = st.date_input("Start Date", value=datetime.now().date() - timedelta(days=365))
        
        # Store in session state
        st.session_state.date_range = (start_date, end_date)
        
    with col2:
        st.markdown("#### 🎛️ Chart Preferences")
        chart_height = st.slider("Chart Height", 400, 800, 600)
        chart_theme = st.selectbox("Theme", ["Default", "Dark", "Light"])
        show_gridlines = st.checkbox("Show Gridlines", True)
        enable_crossfilter = st.checkbox("Enable Crossfilter", True)
        
        # Store preferences
        st.session_state.chart_preferences = {
            'height': chart_height,
            'theme': chart_theme,
            'gridlines': show_gridlines,
            'crossfilter': enable_crossfilter
        }
    
    st.markdown("---")
    
    # Quick stats
    with st.spinner("Loading market overview..."):
        try:
            df = load_flight_status_data(index_option, limit=20)
            if not df.empty:
                st.markdown("### 📊 Market Snapshot")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    avg_change = df['daily_change_pct'].mean()
                    st.metric("📈 Avg Daily Change", f"{avg_change:.2f}%")
                
                with col2:
                    bullish_count = len(df[df['signal_score'] > 0])
                    st.metric("🟢 Bullish Signals", bullish_count)
                
                with col3:
                    avg_rsi = df['RSI'].mean() if not df['RSI'].isna().all() else 50
                    st.metric("📊 Average RSI", f"{avg_rsi:.1f}")
                
                with col4:
                    active_stocks = len(df)
                    st.metric("📋 Active Stocks", active_stocks)
                
        except Exception as e:
            st.info("Market data will load when you select a page.")
    
    # Navigation guide
    st.markdown("""
    ### 🧭 Navigation Guide
    
    **📊 Single Stock Analysis**: Deep dive into individual stock technical analysis  
    **🛩️ Flight Status Dashboard**: NEW! See all stocks in one table with signals  
    **🧠 ML Predictions**: AI-powered price forecasting (if available)
    
    👈 **Use the sidebar to navigate between pages**
    """)

def main():
    """Enhanced main app with navigation"""
    
    st.set_page_config(
        page_title="📊 Enhanced Stock Dashboard", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Sidebar navigation
    with st.sidebar:
        st.title("📊 Navigation")
        
        page = st.radio(
            "Choose Page:",
            [
                "🏠 Home & Filters",
                "📈 Single Stock Analysis", 
                "🛩️ Flight Status Dashboard",
                "🧠 ML Predictions"
            ]
        )
        
        st.markdown("---")
        
        # Quick actions
        st.markdown("### ⚡ Quick Actions")
        if st.button("🔄 Refresh All Data"):
            st.cache_data.clear()
            st.success("Cache cleared!")
        
        if st.button("🗃️ Reset Connections"):
            # Call your existing reset function if available
            st.info("Connections reset!")
        
        st.markdown("---")
        st.markdown("""
        ### 💡 Tips
        - **Flight Status**: Best for screening multiple stocks
        - **Single Stock**: Best for detailed analysis
        - **Use filters** to focus on specific signals
        - **Download data** for offline analysis
        """)
    
    # Route to appropriate page
    if page == "🏠 Home & Filters":
        show_home_page()
    elif page == "📈 Single Stock Analysis":
        # Call your existing technical analysis page
        # show_technical_analysis_page()  # Your existing function
        st.info("This would show your existing single-stock technical analysis page.")
        st.markdown("**Add your existing `show_technical_analysis_page()` function here.**")
    elif page == "🛩️ Flight Status Dashboard":
        show_flight_status_page()
    elif page == "🧠 ML Predictions":
        # Call your existing ML prediction page if available
        # show_ml_prediction_page()  # Your existing function
        st.info("This would show your ML prediction page if available.")
        st.markdown("**Add your existing `show_ml_prediction_page()` function here.**")

if __name__ == "__main__":
    main()
