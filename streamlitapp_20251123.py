import streamlit as st
import pyodbc
import pandas as pd
import plotly.express as px

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
# PLOTTING HELPERS
# ----------------------------
def plot_indicator_section(price_df, rsi_df, macd_df, bb_df, ema_sma_df, atr_df, ticker, index_name):
    st.subheader(f"📈 Price & Indicator Charts for {ticker} ({index_name})")

    # 1. Price + Bollinger Bands
    if bb_df is not None and not bb_df.empty:
        st.markdown("**Bollinger Bands** highlight volatility and potential reversal zones.")
        fig_bb = px.line(
            bb_df,
            x="trading_date",
            y=["close_price", "Upper_Band", "Lower_Band"],
            title="Close Price with Bollinger Bands",
        )
        fig_bb.update_layout(legend_title_text="Series")
        st.plotly_chart(fig_bb, width="stretch")

    # 2. RSI
    if rsi_df is not None and not rsi_df.empty:
        st.markdown("**RSI (Relative Strength Index)** shows overbought (>70) and oversold (<30) zones.")
        fig_rsi = px.line(
            rsi_df,
            x="trading_date",
            y="RSI",
            title="RSI Indicator",
        )
        fig_rsi.add_hrect(y0=70, y1=70, line_width=1, line_dash="dash", line_color="red")
        fig_rsi.add_hrect(y0=30, y1=30, line_width=1, line_dash="dash", line_color="green")
        st.plotly_chart(fig_rsi, width="stretch")

    # 3. MACD
    if macd_df is not None and not macd_df.empty:
        st.markdown("**MACD** crossovers (MACD vs Signal) highlight momentum shifts.")
        fig_macd = px.line(
            macd_df,
            x="trading_date",
            y=["MACD", "Signal_Line"],
            title="MACD & Signal Line",
        )
        st.plotly_chart(fig_macd, width="stretch")

    # 4. SMA / EMA
    if ema_sma_df is not None and not ema_sma_df.empty:
        st.markdown("**SMA/EMA** trend direction: price above long-term MAs = bullish bias.")
        fig_ma = px.line(
            ema_sma_df,
            x="trading_date",
            y=["close_price", "SMA_50", "SMA_100", "SMA_200", "EMA_50", "EMA_100", "EMA_200"],
            title="Close Price with SMA & EMA",
        )
        st.plotly_chart(fig_ma, width="stretch")

    # 5. ATR
    if atr_df is not None and not atr_df.empty:
        st.markdown("**ATR (Average True Range)** captures volatility — higher ATR means wider stops are needed.")
        fig_atr = px.line(
            atr_df,
            x="trading_date",
            y="ATR_14",
            title="ATR 14",
        )
        st.plotly_chart(fig_atr, width="stretch")


def plot_signal_view(view_type: str, df: pd.DataFrame, label: str):
    if df is None or df.empty:
        st.info(f"No {label} signals available for this selection.")
        return

    # Map to correct columns based on your metadata
    if view_type == "BB":
        value_col = "close_price"
        signal_col = "bb_trade_signal"
        title = f"Bollinger Band Trade Signals - {label}"
        y_label = "Close Price"
    elif view_type == "MACD":
        value_col = "MACD"
        signal_col = "MACD_Signal"
        title = f"MACD Trade Signals - {label}"
        y_label = "MACD"
    elif view_type == "RSI":
        value_col = "RSI"
        signal_col = "rsi_trade_signal"
        title = f"RSI Trade Signals - {label}"
        y_label = "RSI"
    elif view_type == "SMA":
        value_col = "close_price"
        signal_col = "sma_trade_signal"
        title = f"SMA / EMA Trade Signals - {label}"
        y_label = "Close Price"
    elif view_type == "ATR":
        value_col = "ATR_14"
        signal_col = "atr_volatility_signal"
        title = f"ATR Volatility Spikes - {label}"
        y_label = "ATR 14"
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
    st.caption(f"Y-axis: {y_label}. Marker color = trade signal from `{signal_col}` column.")

    fig = px.scatter(
        df,
        x="trading_date",
        y=value_col,
        color=signal_col,          # <-- THIS now matches your actual column names
        hover_data=df.columns,
    )
    fig.update_traces(marker=dict(size=9, line=dict(width=1, color="DarkSlateGrey")))
    fig.update_layout(legend_title_text="Signal")
    st.plotly_chart(fig, width="stretch")

# ----------------------------
# MAIN APP
# ----------------------------
st.set_page_config(page_title="📈 Unified Stock Dashboard", layout="wide")
st.title("📊 Unified NSE 500 & NASDAQ 100 Dashboard")

# Sidebar controls
st.sidebar.header("Controls")

index_option = st.sidebar.radio("Select Index", ["NSE 500", "NASDAQ 100"])

ticker_df = get_tickers(index_option)
search_ticker = st.sidebar.text_input("Search Ticker:").upper()

if search_ticker:
    ticker_df = ticker_df[ticker_df["ticker"].str.contains(search_ticker, case=False, na=False)]

if ticker_df.empty:
    st.error("No tickers found for this filter.")
    st.stop()

selected_ticker = st.sidebar.selectbox("Choose Ticker", ticker_df["ticker"].tolist())

# Load all base indicator data
price_df = load_price_data(index_option, selected_ticker)
rsi_df = load_rsi(index_option, selected_ticker)
bb_df = load_bbands(index_option, selected_ticker)
macd_df = load_macd(index_option, selected_ticker)
ema_sma_df = load_ema_sma(index_option, selected_ticker)
atr_df = load_atr(index_option, selected_ticker)

if price_df is None or price_df.empty:
    st.error("No price data available for this ticker.")
    st.stop()

# Date range selector based on price_df
date_min = price_df["trading_date"].min()
date_max = price_df["trading_date"].max()

start_date, end_date = st.sidebar.date_input(
    "Select Date Range",
    [date_min, date_max],
    min_value=date_min,
    max_value=date_max,
)

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
# Section 1: Indicator Charts
# ----------------------------
with st.container():
    plot_indicator_section(
        price_df, rsi_df, macd_df, bb_df, ema_sma_df, atr_df,
        selected_ticker, index_option,
    )

# ----------------------------
# Section 2: Trading Signal Views
# ----------------------------
st.markdown("---")
st.header("🎯 Trading Signal Views")

st.markdown(
    "Use these charts to spot potential **entry/exit points** based on your SQL signal logic: "
    "Bollinger Band breakouts, MACD crossovers, RSI overbought/oversold, "
    "SMA/EMA trend shifts, and ATR volatility spikes."
)

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

# Plot each
plot_signal_view("BB", bb_signals_df, f"{index_option} - {selected_ticker} - Bollinger Band Signals")
plot_signal_view("MACD", macd_signals_df, f"{index_option} - {selected_ticker} - MACD Signals")
plot_signal_view("RSI", rsi_signals_df, f"{index_option} - {selected_ticker} - RSI Signals")
plot_signal_view("SMA", sma_signals_df, f"{index_option} - {selected_ticker} - SMA/EMA Signals")
plot_signal_view("ATR", atr_spikes_df, f"{index_option} - {selected_ticker} - ATR Volatility Spikes")
