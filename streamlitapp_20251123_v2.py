import streamlit as st
import pyodbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import io
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
    connection_string = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost\\MSSQLSERVER01;'
        'DATABASE=stockdata_db;'
        'Trusted_Connection=yes;'
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
    table = 'nse_500_hist_data' if index_name == 'NSE 500' else 'nasdaq_100_hist_data'
    q = f"""SELECT DISTINCT ticker
            FROM dbo.{table}
            WHERE ticker IS NOT NULL
            ORDER BY ticker"""
    return execute_query_safe(q)


@st.cache_data
def load_price_data(index_name: str, ticker: str) -> pd.DataFrame:
    table = 'nse_500_hist_data' if index_name == 'NSE 500' else 'nasdaq_100_hist_data'
    q = f"""
        SELECT trading_date,
               CAST(open_price AS FLOAT) AS open_price,
               CAST(high_price AS FLOAT) AS high_price,
               CAST(low_price AS FLOAT) AS low_price,
               CAST(close_price AS FLOAT) AS close_price,
               CAST(volume AS FLOAT) AS volume
        FROM dbo.{table}
        WHERE ticker = ?
        ORDER BY trading_date
    """
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_rsi(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_RSI_calculation' if index_name == 'NSE 500' else 'nasdaq_100_RSI_calculation'
    q = f"""SELECT trading_date, RSI
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_bbands(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_bollingerband' if index_name == 'NSE 500' else 'nasdaq_100_bollingerband'
    q = f"""SELECT trading_date, close_price, Upper_Band, Lower_Band
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_macd(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_macd' if index_name == 'NSE 500' else 'nasdaq_100_macd'
    q = f"""SELECT trading_date, MACD, Signal_Line
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_ema_sma(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_ema_sma_view' if index_name == 'NSE 500' else 'nasdaq_100_ema_sma_view'
    q = f"""SELECT trading_date, close_price,
                   SMA_50, SMA_100, SMA_200,
                   EMA_50, EMA_100, EMA_200
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


@st.cache_data
def load_atr(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_atr' if index_name == 'NSE 500' else 'nasdaq_100_atr'
    q = f"""SELECT trading_date, ATR_14
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = execute_query_safe(q, params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df

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
    
    # Calculate VWAP
    df['vwap'] = df['cum_volume_price'] / df['cum_volume']
    
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
    
    # Calculate relative volume
    df['relative_volume'] = df['volume'] / df['volume_ma_20']
    
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
    else:
        view_map = {
            'BB': 'nasdaq_100_bb_signals',
            'MACD': 'nasdaq_100_macd_signals',
            'RSI': 'nasdaq_100_rsi_signals',
            'SMA': 'nasdaq_100_sma_signals',
            'ATR': 'nasdaq_100_atr_spikes',
        }

    view_name = view_map[view_type]
    q = f"""SELECT *
            FROM dbo.{view_name}
            WHERE ticker = ?
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

def plot_indicator_section(price_df, rsi_df, macd_df, bb_df, ema_sma_df, atr_df, ticker, index_name):
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
    else:  # NASDAQ 100
        base_table = 'nasdaq_100_hist_data'
        rsi_view = 'nasdaq_100_RSI_calculation'
        macd_view = 'nasdaq_100_macd'
        bb_view = 'nasdaq_100_bollingerband' 
        sma_view = 'nasdaq_100_ema_sma_view'
        atr_view = 'nasdaq_100_atr'
    
    limit_clause = f"TOP {limit}" if limit else ""  # No default limit - load all stocks
    
    # Simplified query using only existing indicator views (no signal tables)
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
st.title("📊 Advanced Stock Trading Dashboard with AI Analysis")

# ----------------------------
# SIDEBAR - DATABASE CONNECTION MANAGEMENT  
# ----------------------------
st.sidebar.header("🔧 Database Management")
if st.sidebar.button("🔄 Reset Database Connections", key="reset_db_sidebar", help="Click if you're experiencing database connection issues"):
    reset_database_connections()

# ----------------------------
# PAGE NAVIGATION
# ----------------------------
st.sidebar.header("📊 Dashboard Controls")

# Page Navigation
st.sidebar.markdown("### 🧭 Page Navigation")
page = st.sidebar.radio(
    "Select Page:",
    ["🏠 Home & Filters", "📈 Technical Analysis", "🤖 AI Price Predictions", "🛩️ Flight Status Dashboard", "📊 NASDAQ ML Predictions", "📈 NSE ML Predictions", "💱 Forex ML Predictions"],
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
        index_option = st.radio("Select Index", ["NSE 500", "NASDAQ 100"], key="home_index")
        
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
            
        search_ticker = st.text_input("🔎 Search Ticker:", placeholder="e.g., AAPL, RELIANCE", key="home_search").upper()

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

        # Create a comprehensive trading decision analysis
        def analyze_trading_signals(bb_df, macd_df, rsi_df, sma_df, atr_df):
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
            
            return latest_data

        # Analyze current signals
        signal_analysis = analyze_trading_signals(bb_signals_df, macd_signals_df, rsi_signals_df, sma_signals_df, atr_spikes_df)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 📊 Signal Consensus")
            
            buy_signals = 0
            sell_signals = 0
            neutral_signals = 0
            
            for indicator, signal in signal_analysis.items():
                if signal and isinstance(signal, str):
                    signal_lower = signal.lower()
                    if 'buy' in signal_lower or 'bullish' in signal_lower:
                        buy_signals += 1
                    elif 'sell' in signal_lower or 'bearish' in signal_lower:
                        sell_signals += 1
                    else:
                        neutral_signals += 1
            
            total_signals = buy_signals + sell_signals + neutral_signals
            
            if total_signals > 0:
                buy_pct = (buy_signals / total_signals) * 100
                sell_pct = (sell_signals / total_signals) * 100
                
                st.metric("🟢 Bullish Signals", f"{buy_signals}/{total_signals}", f"{buy_pct:.1f}%")
                st.metric("🔴 Bearish Signals", f"{sell_signals}/{total_signals}", f"{sell_pct:.1f}%")
                st.metric("🟡 Neutral Signals", f"{neutral_signals}/{total_signals}")

        with col2:
            st.markdown("### 🎯 Trading Recommendation")
            
            if buy_signals > sell_signals and buy_signals >= 2:
                recommendation = "🟢 **BULLISH BIAS** - Consider Long Positions"
                confidence = "High" if buy_signals >= 3 else "Medium"
                action = "Look for buying opportunities on dips"
            elif sell_signals > buy_signals and sell_signals >= 2:
                recommendation = "🔴 **BEARISH BIAS** - Consider Short Positions"
                confidence = "High" if sell_signals >= 3 else "Medium"
                action = "Look for selling opportunities on rallies"
            else:
                recommendation = "🟡 **MIXED SIGNALS** - Stay Cautious"
                confidence = "Low"
                action = "Wait for clearer signals before entering positions"
            
            st.markdown(recommendation)
            st.markdown(f"**Confidence Level:** {confidence}")
            st.markdown(f"**Suggested Action:** {action}")

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
            st.error("No price data available for this stock.")
            return
        
        # Calculate volume indicators for features
        ml_df = calculate_volume_indicators(price_df.copy())
        
        # Load additional indicators
        rsi_df = load_rsi(index_option, selected_ticker)
        macd_df = load_macd(index_option, selected_ticker)
        atr_df = load_atr(index_option, selected_ticker)
        
        # Merge all indicators
        if not rsi_df.empty:
            ml_df = ml_df.merge(rsi_df[['trading_date', 'RSI']], on='trading_date', how='left')
        if not macd_df.empty:
            ml_df = ml_df.merge(macd_df[['trading_date', 'MACD', 'Signal_Line']], on='trading_date', how='left')
        if not atr_df.empty:
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
        
        # Create feature matrix
        available_features = [f for f in base_features if f in df.columns]
        feature_df = df[['trading_date'] + available_features].copy()
        
        # Forward fill missing values
        feature_df = feature_df.fillna(method='ffill').fillna(method='bfill')
        
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
    
    # Split data for training and testing
    train_size = int(len(target_df) * 0.8)
    train_df = target_df.iloc[:train_size]
    test_df = target_df.iloc[train_size:]
    
    # Prepare X and y
    X_train = train_df[feature_names].values
    y_train = train_df['target'].values
    X_test = test_df[feature_names].values 
    y_test = test_df['target'].values
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
        st.metric("Current Price", f"${current_price:.2f}")
        
    with col2:
        st.markdown("#### 🎯 Predicted Change")
        if model_type == "Ensemble" and 'Ensemble' in future_predictions:
            pred_change = future_predictions['Ensemble']
        else:
            pred_change = list(future_predictions.values())[0]
        
        direction = "📈" if pred_change > 0 else "📉"
        st.metric(f"{prediction_days}-day Return", f"{direction} {pred_change*100:.2f}%")
        
    with col3:
        st.markdown("#### 💰 Target Price")
        target_price = current_price * (1 + pred_change)
        price_diff = target_price - current_price
        st.metric("Target Price", f"${target_price:.2f}", f"${price_diff:+.2f}")
    
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
    
    # Index Selection
    index_name = st.selectbox(
        "Select Index",
        ["NSE 500", "NASDAQ 100"],
        help="Choose which market index to analyze"
    )
    
    # Load data - load ALL stocks (no limit)
    with st.spinner(f"🛩️ Loading flight status for {index_name}..."):
        df = load_flight_status_data(index_name, limit=None)  # Load all stocks
    
    if df.empty:
        st.error("❌ No data available. Please check your database connection and table structure.")
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
        key="nasdaq_ml_ticker"
    ).upper()
    
    # Load data button
    if st.button("📊 Load NASDAQ ML Data", key="load_nasdaq_ml"):
        with st.spinner("Loading NASDAQ ML prediction data..."):
            try:
                # Query ml_prediction_summary (this is a summary table, no ticker filtering)
                summary_query = f"""
                SELECT TOP 1000 *
                FROM dbo.ml_prediction_summary
                WHERE run_date BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY run_date DESC
                """
                # Note: ml_prediction_summary doesn't have ticker column - it's an aggregate summary
                
                summary_df = execute_query_safe(summary_query)
                
                # Query ml_technical_indicators
                indicators_query = f"""
                SELECT TOP 1000 *
                FROM dbo.ml_technical_indicators
                WHERE trading_date BETWEEN '{start_date}' AND '{end_date}'
                """
                if ticker_input:
                    indicators_query += f" AND ticker = '{ticker_input}'"
                indicators_query += " ORDER BY trading_date DESC, ticker"
                
                indicators_df = execute_query_safe(indicators_query)
                
                # Query ml_trading_predictions
                predictions_query = f"""
                SELECT TOP 1000 *
                FROM dbo.ml_trading_predictions
                WHERE trading_date BETWEEN '{start_date}' AND '{end_date}'
                """
                if ticker_input:
                    predictions_query += f" AND ticker = '{ticker_input}'"
                predictions_query += " ORDER BY trading_date DESC, ticker"
                
                predictions_df = execute_query_safe(predictions_query)
                
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
                    
                    # Indicators metrics
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
        key="nse_ml_ticker"
    ).upper()
    
    # Load data button
    if st.button("📈 Load NSE ML Data", key="load_nse_ml"):
        with st.spinner("Loading NSE ML prediction data..."):
            try:
                # Query ml_nse_predict_summary (this is a summary table, no ticker filtering)
                summary_query = f"""
                SELECT TOP 1000 *
                FROM dbo.ml_nse_predict_summary
                WHERE analysis_date BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY analysis_date DESC
                """
                # Note: ml_nse_predict_summary doesn't have ticker column - it's an aggregate summary
                
                summary_df = execute_query_safe(summary_query)
                
                # Query ml_nse_technical_indicators
                indicators_query = f"""
                SELECT TOP 1000 *
                FROM dbo.ml_nse_technical_indicators
                WHERE trading_date BETWEEN '{start_date}' AND '{end_date}'
                """
                if ticker_input:
                    indicators_query += f" AND ticker = '{ticker_input}'"
                indicators_query += " ORDER BY trading_date DESC, ticker"
                
                indicators_df = execute_query_safe(indicators_query)
                
                # Query ml_nse_trading_predictions
                predictions_query = f"""
                SELECT TOP 1000 *
                FROM dbo.ml_nse_trading_predictions
                WHERE trading_date BETWEEN '{start_date}' AND '{end_date}'
                """
                if ticker_input:
                    predictions_query += f" AND ticker = '{ticker_input}'"
                predictions_query += " ORDER BY trading_date DESC, ticker"
                
                predictions_df = execute_query_safe(predictions_query)
                
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
                    
                    # Indicators metrics
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
                    with col4:
                        if 'volume_trend' in indicators_df.columns:
                            high_volume = len(indicators_df[indicators_df['volume_trend'].str.contains('HIGH', case=False, na=False)])
                            st.metric("High Volume", high_volume)
                    
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


# Main application routing
if page == "🏠 Home & Filters":
    show_home_page()
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
