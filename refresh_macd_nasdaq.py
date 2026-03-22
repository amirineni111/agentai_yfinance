"""
MACD Refresh — NASDAQ (Incremental)
====================================
Schedule: Run after NASDAQ market data ingestion completes.

Source: nasdaq_100_hist_data -> Target: nasdaq_100_macd_data
"""
from macd_refresh_core import refresh_market_macd

if __name__ == '__main__':
    refresh_market_macd(
        source_table='nasdaq_100_hist_data',
        target_table='nasdaq_100_macd_data',
        id_col='ticker',
        market_label='nasdaq',
    )
