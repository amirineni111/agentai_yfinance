from typing import Union, Dict
import pandas as pd
from langchain_core.tools import tool
import yfinance as yf
import datetime as dt
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD
from ta.volume import volume_weighted_average_price

@tool
def get_stock_prices(ticker: str) -> Union[Dict, str]:
    """Fetches historical stock price data and technical indicators for a given ticker."""
    try:
        # Download 18 months of weekly stock data
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

        # Compute RSI
        rsi_series = RSIIndicator(df['Close'], window=14).rsi().iloc[-12:]
        indicators["RSI"] = rsi_series.round(2).dropna().to_dict()

        # Compute Stochastic Oscillator
        sto_series = StochasticOscillator(
            df['High'], df['Low'], df['Close'], window=14
        ).stoch().iloc[-12:]
        indicators["Stochastic_Oscillator"] = sto_series.round(2).dropna().to_dict()

        # Compute MACD and Signal
        macd = MACD(df['Close'])
        indicators["MACD"] = macd.macd().iloc[-12:].round(2).dropna().to_dict()
        indicators["MACD_Signal"] = macd.macd_signal().iloc[-12:].round(2).dropna().to_dict()

        # Compute VWAP
        vwap_series = volume_weighted_average_price(
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            volume=df['Volume']
        ).iloc[-12:]
        indicators["VWAP"] = vwap_series.round(2).dropna().to_dict()

        return {
            'stock_price': df.to_dict(orient='records'),
            'indicators': indicators
        }

    except Exception as e:
        return f"Error fetching price data: {str(e)}"
