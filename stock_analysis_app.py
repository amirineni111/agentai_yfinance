import streamlit as st
from typing import Union, Dict
import yfinance as yf
import datetime as dt
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD
from ta.volume import volume_weighted_average_price
import pandas as pd

# LLM model
llm = ChatOllama(model="llama3")

# Tools

def get_stock_prices(ticker: str) -> Union[Dict, str]:
    try:
        data = yf.download(
            ticker,
            start=dt.datetime.now() - dt.timedelta(weeks=72),
            end=dt.datetime.now(),
            interval='1wk'
        )
        if data.empty:
            return f"No data found for ticker '{ticker}'."

        df = data.copy()
        df.reset_index(inplace=True)
        df['Date'] = df['Date'].astype(str)

        indicators = {}

        rsi_series = RSIIndicator(df['Close'], window=14).rsi().iloc[-12:]
        indicators["RSI"] = rsi_series.round(2).dropna().to_dict()

        sto_series = StochasticOscillator(
            df['High'], df['Low'], df['Close'], window=14
        ).stoch().iloc[-12:]
        indicators["Stochastic_Oscillator"] = sto_series.round(2).dropna().to_dict()

        macd = MACD(df['Close'])
        indicators["MACD"] = macd.macd().iloc[-12:].round(2).dropna().to_dict()
        indicators["MACD_Signal"] = macd.macd_signal().iloc[-12:].round(2).dropna().to_dict()

        vwap_series = volume_weighted_average_price(
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            volume=df['Volume']
        ).iloc[-12:]
        indicators["VWAP"] = vwap_series.round(2).dropna().to_dict()

        return {
            'stock_price': df.tail(5).to_dict(orient='records'),
            'indicators': indicators
        }

    except Exception as e:
        return f"Error fetching price data: {str(e)}"


def get_financial_metrics(ticker: str) -> Union[Dict, str]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or "forwardPE" not in info:
            return f"No financial data available for '{ticker}'."

        return {
            'pe_ratio': info.get('forwardPE'),
            'price_to_book': info.get('priceToBook'),
            'debt_to_equity': info.get('debtToEquity'),
            'profit_margins': info.get('profitMargins')
        }

    except Exception as e:
        return f"Error fetching ratios: {str(e)}"


# --- Streamlit UI ---
st.set_page_config(page_title="Llama3 Stock Analyzer", layout="wide")
st.title("📊 Llama3 Stock Analyzer (Offline, Local LLM)")

ticker = st.text_input("Enter stock ticker symbol:", value="AAPL")

if st.button("Analyze Stock"):
    with st.spinner("Fetching data and analyzing..."):
        stock_data = get_stock_prices(ticker)
        metrics = get_financial_metrics(ticker)

        prompt = (
            f"You are a financial analyst.\n"
            f"Analyze stock data and financial metrics for {ticker}.\n\n"
            f"Stock Price Data and Indicators:\n{stock_data}\n\n"
            f"Financial Metrics:\n{metrics}\n\n"
            f"Provide a technical summary and financial health analysis."
        )

        response = llm.invoke(prompt)

        st.subheader("🔍 LLM Analysis Summary")
        st.markdown(response.content)

        with st.expander("📈 Raw Price Data"):
            st.json(stock_data)

        with st.expander("💰 Raw Financial Metrics"):
            st.json(metrics)
