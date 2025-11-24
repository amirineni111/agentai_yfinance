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

# ----------------------------
# DB CONNECTION
# ----------------------------
@st.cache_resource
def get_connection():
    return pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost\\MSSQLSERVER01;'
        'DATABASE=stockdata_db;'
        'Trusted_Connection=yes;'
    )

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
    return pd.read_sql(q, get_connection())


def load_price_data(index_name: str, ticker: str) -> pd.DataFrame:
    table = 'nse_500_hist_data' if index_name == 'NSE 500' else 'nasdaq_100_hist_data'
    q = f"""
        SELECT trading_date,
               CAST(close_price AS FLOAT) AS close_price
        FROM dbo.{table}
        WHERE ticker = ?
        ORDER BY trading_date
    """
    df = pd.read_sql(q, get_connection(), params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


def load_rsi(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_RSI_calculation' if index_name == 'NSE 500' else 'nasdaq_100_RSI_calculation'
    q = f"""SELECT trading_date, RSI
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = pd.read_sql(q, get_connection(), params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


def load_bbands(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_bollingerband' if index_name == 'NSE 500' else 'nasdaq_100_bollingerband'
    q = f"""SELECT trading_date, close_price, Upper_Band, Lower_Band
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = pd.read_sql(q, get_connection(), params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


def load_macd(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_macd' if index_name == 'NSE 500' else 'nasdaq_100_macd'
    q = f"""SELECT trading_date, MACD, Signal_Line
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = pd.read_sql(q, get_connection(), params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


def load_ema_sma(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_ema_sma_view' if index_name == 'NSE 500' else 'nasdaq_100_ema_sma_view'
    q = f"""SELECT trading_date, close_price,
                   SMA_50, SMA_100, SMA_200,
                   EMA_50, EMA_100, EMA_200
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = pd.read_sql(q, get_connection(), params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df


def load_atr(index_name: str, ticker: str) -> pd.DataFrame:
    view = 'nse_500_atr' if index_name == 'NSE 500' else 'nasdaq_100_atr'
    q = f"""SELECT trading_date, ATR_14
            FROM dbo.{view}
            WHERE ticker = ?
            ORDER BY trading_date"""
    df = pd.read_sql(q, get_connection(), params=[ticker])
    if not df.empty:
        df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df

# ----------------------------
# SIGNAL VIEW LOADERS
# ----------------------------
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

    df = pd.read_sql(q, get_connection(), params=[ticker])
    if not df.empty and 'trading_date' in df.columns:
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
""", unsafe_allow_html=True)

# Introduction section
st.markdown("""
### 🚀 Welcome to Your Professional Trading Dashboard!

This comprehensive platform combines **technical analysis**, **trading education**, and **AI-powered insights** to help you make informed trading decisions.

**What you'll find here:**
- 📈 **Real-time Technical Charts** with professional indicators
- 🧠 **Educational Content** to understand each indicator
- 🎯 **Trading Signals** from your custom SQL algorithms  
- 🤖 **AI Decision Matrix** that analyzes multiple indicators
- ⚡ **Risk Management Tools** for professional trading

**Navigation Guide:**
1. **Trading Education** - Learn how indicators work and combine them
2. **Technical Charts** - Analyze price action and indicators
3. **Signal Analysis** - Review your automated trading signals
4. **AI Recommendations** - Get data-driven trading suggestions

---
""")

# Sidebar controls
st.sidebar.header("📊 Dashboard Controls")

# Add quick navigation
st.sidebar.markdown("### 🧭 Quick Navigation")
if st.sidebar.button("🔝 Go to Top"):
    st.sidebar.write("Scroll to top of page")

st.sidebar.markdown("---")

# Market selection
st.sidebar.markdown("### 📈 Market Selection")
index_option = st.sidebar.radio("Select Index", ["NSE 500", "NASDAQ 100"])

# Clear session state when market selection changes
if 'prev_market' not in st.session_state:
    st.session_state.prev_market = index_option
elif st.session_state.prev_market != index_option:
    # Market changed, clear date range session state
    if 'date_range' in st.session_state:
        del st.session_state.date_range
    st.session_state.prev_market = index_option

# Ticker selection with enhanced search
st.sidebar.markdown("### 🔍 Stock Selection")
ticker_df = get_tickers(index_option)
search_ticker = st.sidebar.text_input("🔎 Search Ticker:", placeholder="e.g., AAPL, RELIANCE").upper()

if search_ticker:
    ticker_df = ticker_df[ticker_df["ticker"].str.contains(search_ticker, case=False, na=False)]
    if ticker_df.empty:
        st.sidebar.error("❌ No tickers found for this search.")
        st.error("No tickers found for this filter.")
        st.stop()
    else:
        st.sidebar.success(f"✅ Found {len(ticker_df)} ticker(s)")

if ticker_df.empty:
    st.error("No tickers found for this filter.")
    st.stop()

selected_ticker = st.sidebar.selectbox("📊 Choose Ticker:", ticker_df["ticker"].tolist())

# Display ticker info
if selected_ticker:
    st.sidebar.info(f"📈 Analyzing: **{selected_ticker}** from **{index_option}**")

st.sidebar.markdown("---")

# Chart preferences
st.sidebar.markdown("### ⚙️ Chart Preferences")
default_chart_height = st.sidebar.selectbox(
    "📏 Default Chart Height:", 
    [500, 600, 700, 800], 
    index=1,
    key="sidebar_chart_height"
)

chart_theme = st.sidebar.selectbox(
    "🎨 Chart Theme:",
    ["Default", "Dark", "Plotly White"],
    index=0
)

show_gridlines = st.sidebar.checkbox("📋 Show Gridlines", value=True)
enable_crossfilter = st.sidebar.checkbox("🎯 Enable Crossfilter", value=True)

st.sidebar.markdown("---")

# Load all base indicator data
st.sidebar.markdown("### 📊 Loading Data...")
with st.spinner("Loading indicator data..."):
    price_df = load_price_data(index_option, selected_ticker)
    rsi_df = load_rsi(index_option, selected_ticker)
    bb_df = load_bbands(index_option, selected_ticker)
    macd_df = load_macd(index_option, selected_ticker)
    ema_sma_df = load_ema_sma(index_option, selected_ticker)
    atr_df = load_atr(index_option, selected_ticker)

if price_df is None or price_df.empty:
    st.sidebar.error("❌ No price data available")
    st.error("No price data available for this ticker.")
    st.stop()
else:
    st.sidebar.success("✅ Data loaded successfully!")

# Date range selector based on price_df
st.sidebar.markdown("### 📅 Date Range")
date_min = price_df["trading_date"].min()
date_max = price_df["trading_date"].max()

# Quick date range buttons
col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("📅 Last 3M", key="3m"):
        start_date_quick = date_max - pd.DateOffset(months=3)
        st.session_state.date_range = [start_date_quick, date_max]
with col2:
    if st.button("📅 Last 1Y", key="1y"):
        start_date_quick = date_max - pd.DateOffset(years=1)
        st.session_state.date_range = [start_date_quick, date_max]

# Initialize session state for date range
if 'date_range' not in st.session_state:
    st.session_state.date_range = [date_min, date_max]

start_date, end_date = st.sidebar.date_input(
    "📅 Select Date Range:",
    value=st.session_state.date_range,
    min_value=date_min,
    max_value=date_max,
)

st.sidebar.markdown("---")

# Data summary
st.sidebar.markdown("### 📊 Data Summary")
data_points = len(price_df)
date_range_days = (date_max - date_min).days

st.sidebar.metric("📈 Total Data Points", data_points)
st.sidebar.metric("📅 Date Range (Days)", date_range_days)

if data_points > 0:
    current_price = price_df['close_price'].iloc[-1]
    price_change = current_price - price_df['close_price'].iloc[0] if len(price_df) > 1 else 0
    price_change_pct = (price_change / price_df['close_price'].iloc[0] * 100) if len(price_df) > 1 and price_df['close_price'].iloc[0] != 0 else 0
    
    st.sidebar.metric(
        "💰 Current Price", 
        f"${current_price:.2f}",
        delta=f"{price_change_pct:.1f}%"
    )

st.sidebar.markdown("---")

# Section visibility controls
st.sidebar.markdown("### 👁️ Section Visibility")
show_education = st.sidebar.checkbox("📚 Show Education", value=True)
show_indicators = st.sidebar.checkbox("📈 Show Indicators", value=True)
show_signals = st.sidebar.checkbox("🎯 Show Signals", value=True)
show_ai_analysis = st.sidebar.checkbox("🤖 Show AI Analysis", value=True)

st.sidebar.markdown("---")

# Export options
st.sidebar.markdown("### 💾 Export Options")

# Generate downloadable reports
csv_data, timestamp = create_downloadable_report(selected_ticker, index_option, price_df, rsi_df, bb_df, macd_df, ema_sma_df, atr_df)

# PDF Export Button (HTML print option)
if st.sidebar.button("📊 Export Current View as PDF"):
    st.sidebar.markdown("""
    **📋 PDF Export Instructions:**
    1. Press `Ctrl+P` (Windows) or `Cmd+P` (Mac)
    2. Select "Save as PDF" as destination
    3. Choose "More Settings" → "Options" → "Headers and Footers" (uncheck)
    4. Click "Save"
    
    *This will save the current dashboard view as a PDF file.*
    """)
    st.sidebar.success("📄 PDF export ready! Follow the instructions above.")

# CSV Download Button
csv_filename = f"{selected_ticker}_{index_option.replace(' ', '_')}_analysis_{timestamp}.csv"
st.sidebar.download_button(
    label="📈 Download Analysis Report (CSV)",
    data=csv_data,
    file_name=csv_filename,
    mime="text/csv",
    help="Download comprehensive analysis data in CSV format"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### ℹ️ About")
st.sidebar.info("""
🚀 **Advanced Trading Dashboard v2.0**

Built with Streamlit + SQL Server
- Real-time technical analysis
- AI-powered insights
- Professional risk management

📧 Contact: [Your Email]
""")

# Older Streamlit may return list-like
if isinstance(start_date, (list, tuple)):
    start_date, end_date = start_date

# Apply date filter to all indicator data
price_df = filter_by_date(price_df, start_date, end_date)
rsi_df = filter_by_date(rsi_df, start_date, end_date)
bb_df = filter_by_date(bb_df, start_date, end_date)
macd_df = filter_by_date(macd_df, start_date, end_date)
ema_sma_df = filter_by_date(ema_sma_df, start_date, end_date)
atr_df = filter_by_date(atr_df, start_date, end_date)

st.markdown(
    f"### 📌 Selected: **{selected_ticker}** in **{index_option}** "
    f"from **{start_date}** to **{end_date}**"
)

# ----------------------------
# Section 1: Trading Education
# ----------------------------
show_trading_guide()
show_indicator_education()

# ----------------------------
# Section 2: Indicator Charts
# ----------------------------
st.markdown("---")
with st.container():
    plot_indicator_section(
        price_df, rsi_df, macd_df, bb_df, ema_sma_df, atr_df,
        selected_ticker, index_option,
    )

# ----------------------------
# Section 3: Trading Signal Views
# ----------------------------
st.markdown("---")
st.header("🎯 Live Trading Signal Analysis")

st.markdown(
    "📊 **Real-time signals from your SQL views** - These charts show entry/exit points based on your trading algorithms. "
    "Combine multiple signals for higher probability trades!"
)

# Add a summary dashboard for current signals
st.markdown("### 📈 Current Market Summary")
col1, col2, col3, col4 = st.columns(4)

# Load each signal view
bb_signals_df = load_signal_view(index_option, "BB", selected_ticker)
macd_signals_df = load_signal_view(index_option, "MACD", selected_ticker)
rsi_signals_df = load_signal_view(index_option, "RSI", selected_ticker)
sma_signals_df = load_signal_view(index_option, "SMA", selected_ticker)
atr_spikes_df = load_signal_view(index_option, "ATR", selected_ticker)

# Apply same date filter
bb_signals_df = filter_by_date(bb_signals_df, start_date, end_date)
macd_signals_df = filter_by_date(macd_signals_df, start_date, end_date)
rsi_signals_df = filter_by_date(rsi_signals_df, start_date, end_date)
sma_signals_df = filter_by_date(sma_signals_df, start_date, end_date)
atr_spikes_df = filter_by_date(atr_spikes_df, start_date, end_date)

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
plot_signal_view("ATR", atr_spikes_df, f"{index_option} - {selected_ticker}")

# ----------------------------
# Section 4: Trading Decision Matrix
# ----------------------------
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
