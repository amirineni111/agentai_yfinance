from typing import Union, Dict
import yfinance as yf
from langchain_core.tools import tool  # Use this if you're using langgraph/langchain-core

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
