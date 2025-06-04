import os
from dotenv import load_dotenv
from typing import Union, Dict
import yfinance as yf
import datetime as dt
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD
from ta.volume import volume_weighted_average_price
import pandas as pd

# Load environment variables (not required for Ollama but good habit)
load_dotenv()

# ✅ Define tools
@tool
def get_stock_prices(ticker: str) -> Union[Dict, str]:
    """Fetches historical stock price data and technical indicators for a given ticker."""
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


@tool
def get_financial_metrics(ticker: str) -> Union[Dict, str]:
    """Fetches key financial ratios for a given ticker using Yahoo Finance."""
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

# ✅ Use Ollama's llama3 model
llm = ChatOllama(model="llama3")

# ✅ Set stock symbol here
ticker = "AAPL"

# ✅ Run tools
price_result = get_stock_prices.invoke({"ticker": ticker})
metrics_result = get_financial_metrics.invoke({"ticker": ticker})

# ✅ Build the full prompt
full_prompt = (
    f"You are a financial analyst.\n"
    f"Analyze stock data and financial metrics for {ticker}.\n\n"
    f"Stock Price Data and Indicators:\n{price_result}\n\n"
    f"Financial Metrics:\n{metrics_result}\n\n"
    f"Provide a summary of the company's current technical trend and financial health."
)

# ✅ Ask the model
response = llm.invoke(full_prompt)

# ✅ Print result
print("\n🔍 ANALYSIS SUMMARY:\n")
print(response.content)
