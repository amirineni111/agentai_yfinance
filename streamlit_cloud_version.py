"""
Enhanced Trading Dashboard - Cloud Version
Modified to work without SQL Server dependency using yfinance
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

# ----------------------------
# CONFIGURATION
# ----------------------------
st.set_page_config(
    page_title="AI Trading Dashboard - multizoneus.com",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# DATA FETCHING FUNCTIONS
# ----------------------------
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_stock_data(symbol, period="1y"):
    """Fetch stock data using yfinance"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        info = ticker.info
        
        if data.empty:
            return None, None
            
        # Prepare data with consistent column names
        data = data.reset_index()
        data.rename(columns={
            'Date': 'trading_date',
            'Open': 'open_price', 
            'High': 'high_price',
            'Low': 'low_price',
            'Close': 'close_price',
            'Volume': 'volume'
        }, inplace=True)
        
        return data, info
        
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None, None

@st.cache_data(ttl=300)
def get_market_symbols():
    """Get predefined list of popular symbols"""
    return {
        "US Stocks": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM", "JNJ", "V"],
        "Tech Stocks": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "CRM", "ADBE", "NFLX", "UBER"],
        "Crypto": ["BTC-USD", "ETH-USD", "BNB-USD", "ADA-USD", "SOL-USD"],
        "Indices": ["^GSPC", "^DJI", "^IXIC", "^RUT"],
        "Forex": ["EURUSD=X", "GBPUSD=X", "JPYUSD=X", "AUDUSD=X"]
    }

def calculate_technical_indicators(df):
    """Calculate technical indicators"""
    df = df.copy()
    
    # Moving averages
    df['sma_20'] = df['close_price'].rolling(20).mean()
    df['sma_50'] = df['close_price'].rolling(50).mean()
    df['ema_12'] = df['close_price'].ewm(span=12).mean()
    df['ema_26'] = df['close_price'].ewm(span=26).mean()
    
    # RSI
    delta = df['close_price'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    df['MACD'] = df['ema_12'] - df['ema_26']
    df['Signal_Line'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']
    
    # Bollinger Bands
    df['bb_middle'] = df['close_price'].rolling(20).mean()
    bb_std = df['close_price'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # Volume indicators
    df['volume_ma_20'] = df['volume'].rolling(20).mean()
    df['relative_volume'] = df['volume'] / df['volume_ma_20']
    
    return df

# ----------------------------
# MAIN APPLICATION
# ----------------------------

def main():
    # Header
    st.markdown('<h1 class="main-header">🤖 AI Trading Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">Powered by multizoneus.com</p>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("📊 Dashboard Controls")
    
    # Market and symbol selection
    markets = get_market_symbols()
    selected_market = st.sidebar.selectbox("Select Market:", list(markets.keys()))
    selected_symbol = st.sidebar.selectbox("Select Symbol:", markets[selected_market])
    
    # Time period selection
    time_period = st.sidebar.selectbox(
        "Time Period:",
        ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
        index=3
    )
    
    # Fetch data
    with st.spinner(f"Loading data for {selected_symbol}..."):
        stock_data, stock_info = fetch_stock_data(selected_symbol, time_period)
    
    if stock_data is None:
        st.error("Failed to load stock data. Please try a different symbol.")
        return
    
    # Calculate indicators
    stock_data = calculate_technical_indicators(stock_data)
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview", "📊 Technical Analysis", "🤖 AI Predictions", "📋 Data"])
    
    with tab1:
        show_overview_tab(stock_data, stock_info, selected_symbol)
    
    with tab2:
        show_technical_analysis_tab(stock_data, selected_symbol)
    
    with tab3:
        show_ai_predictions_tab(stock_data, selected_symbol)
    
    with tab4:
        show_data_tab(stock_data)

def show_overview_tab(data, info, symbol):
    """Show overview and key metrics"""
    st.subheader(f"📈 {symbol} Overview")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    current_price = data['close_price'].iloc[-1]
    previous_price = data['close_price'].iloc[-2] if len(data) > 1 else current_price
    change = current_price - previous_price
    change_pct = (change / previous_price) * 100
    
    with col1:
        st.metric("Current Price", f"${current_price:.2f}", f"{change:+.2f} ({change_pct:+.1f}%)")
    
    with col2:
        high_52w = data['high_price'].max()
        st.metric("52W High", f"${high_52w:.2f}")
    
    with col3:
        low_52w = data['low_price'].min()
        st.metric("52W Low", f"${low_52w:.2f}")
    
    with col4:
        avg_volume = data['volume'].mean()
        st.metric("Avg Volume", f"{avg_volume:,.0f}")
    
    # Price chart
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=data['trading_date'],
        open=data['open_price'],
        high=data['high_price'],
        low=data['low_price'],
        close=data['close_price'],
        name='Price'
    ))
    
    fig.add_trace(go.Scatter(
        x=data['trading_date'],
        y=data['sma_20'],
        mode='lines',
        name='SMA 20',
        line=dict(color='orange', width=1)
    ))
    
    fig.add_trace(go.Scatter(
        x=data['trading_date'],
        y=data['sma_50'],
        mode='lines',
        name='SMA 50',
        line=dict(color='blue', width=1)
    ))
    
    fig.update_layout(
        title=f'{symbol} Price Chart',
        yaxis_title='Price ($)',
        height=500,
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)

def show_technical_analysis_tab(data, symbol):
    """Show technical analysis charts"""
    st.subheader(f"📊 Technical Analysis - {symbol}")
    
    # Technical indicators
    col1, col2 = st.columns(2)
    
    with col1:
        # RSI Chart
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(
            x=data['trading_date'],
            y=data['RSI'],
            mode='lines',
            name='RSI',
            line=dict(color='purple')
        ))
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
        fig_rsi.update_layout(title='RSI (14)', yaxis_title='RSI', height=300)
        st.plotly_chart(fig_rsi, use_container_width=True)
    
    with col2:
        # Volume Chart
        fig_vol = go.Figure()
        fig_vol.add_trace(go.Bar(
            x=data['trading_date'],
            y=data['volume'],
            name='Volume',
            marker_color='lightblue'
        ))
        fig_vol.add_trace(go.Scatter(
            x=data['trading_date'],
            y=data['volume_ma_20'],
            mode='lines',
            name='Volume MA 20',
            line=dict(color='red', width=2)
        ))
        fig_vol.update_layout(title='Volume Analysis', yaxis_title='Volume', height=300)
        st.plotly_chart(fig_vol, use_container_width=True)
    
    # MACD Chart
    fig_macd = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.1, height=400)
    
    fig_macd.add_trace(go.Scatter(
        x=data['trading_date'], y=data['MACD'],
        mode='lines', name='MACD', line=dict(color='blue')
    ), row=1, col=1)
    
    fig_macd.add_trace(go.Scatter(
        x=data['trading_date'], y=data['Signal_Line'],
        mode='lines', name='Signal', line=dict(color='red')
    ), row=1, col=1)
    
    fig_macd.add_trace(go.Bar(
        x=data['trading_date'], y=data['MACD_Histogram'],
        name='Histogram', marker_color='gray'
    ), row=2, col=1)
    
    fig_macd.update_layout(title='MACD Analysis')
    st.plotly_chart(fig_macd, use_container_width=True)

def show_ai_predictions_tab(data, symbol):
    """Show AI predictions and recommendations"""
    st.subheader(f"🤖 AI Predictions - {symbol}")
    
    # Simple ML prediction (you can integrate your advanced models here)
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    
    # Prepare features
    features = ['RSI', 'MACD', 'relative_volume', 'close_price']
    feature_data = data[features].dropna()
    
    if len(feature_data) < 50:
        st.warning("Insufficient data for AI predictions")
        return
    
    # Create target (next day return)
    feature_data['target'] = feature_data['close_price'].shift(-1) / feature_data['close_price'] - 1
    feature_data = feature_data.dropna()
    
    # Split data
    train_size = int(len(feature_data) * 0.8)
    train_data = feature_data.iloc[:train_size]
    test_data = feature_data.iloc[train_size:]
    
    # Train model
    X_train = train_data[features].values
    y_train = train_data['target'].values
    X_test = test_data[features].values
    y_test = test_data['target'].values
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    # Make predictions
    predictions = model.predict(X_test_scaled)
    
    # Current prediction
    latest_features = feature_data[features].iloc[-1:].values
    latest_scaled = scaler.transform(latest_features)
    next_return = model.predict(latest_scaled)[0]
    
    # Display prediction
    col1, col2, col3 = st.columns(3)
    
    current_price = data['close_price'].iloc[-1]
    predicted_price = current_price * (1 + next_return)
    
    with col1:
        st.metric("Current Price", f"${current_price:.2f}")
    
    with col2:
        direction = "📈" if next_return > 0 else "📉"
        st.metric("Predicted Change", f"{direction} {next_return*100:.2f}%")
    
    with col3:
        st.metric("Target Price", f"${predicted_price:.2f}")
    
    # Recommendation
    if abs(next_return) < 0.01:
        recommendation = "🟡 HOLD"
        color = "orange"
    elif next_return > 0.02:
        recommendation = "🟢 STRONG BUY"
        color = "green"
    elif next_return > 0:
        recommendation = "🟢 BUY"
        color = "green"
    elif next_return < -0.02:
        recommendation = "🔴 STRONG SELL"
        color = "red"
    else:
        recommendation = "🔴 SELL"
        color = "red"
    
    st.markdown(f'<div style="text-align: center; font-size: 2em; color: {color}; font-weight: bold; margin: 2rem 0;">{recommendation}</div>', 
                unsafe_allow_html=True)
    
    # Prediction vs actual chart
    test_dates = test_data.index
    
    fig_pred = go.Figure()
    fig_pred.add_trace(go.Scatter(
        x=test_dates, y=y_test * 100,
        mode='lines', name='Actual Returns (%)',
        line=dict(color='blue')
    ))
    fig_pred.add_trace(go.Scatter(
        x=test_dates, y=predictions * 100,
        mode='lines', name='Predicted Returns (%)',
        line=dict(color='red', dash='dash')
    ))
    
    fig_pred.update_layout(
        title='AI Model Performance',
        yaxis_title='Returns (%)',
        height=400
    )
    st.plotly_chart(fig_pred, use_container_width=True)

def show_data_tab(data):
    """Show raw data"""
    st.subheader("📋 Raw Data")
    st.dataframe(data.tail(100), use_container_width=True)
    
    # Download option
    csv = data.to_csv(index=False)
    st.download_button(
        label="Download Data as CSV",
        data=csv,
        file_name=f"stock_data_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

if __name__ == "__main__":
    main()
