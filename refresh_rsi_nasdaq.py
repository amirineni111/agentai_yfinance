"""
RSI Refresh — NASDAQ 100 (Incremental)
=======================================
Schedule: Run after NASDAQ market data ingestion completes.
Only computes RSI for new price data since the last run.

Source: nasdaq_100_hist_data → Target: nasdaq_100_rsi_data
"""
from rsi_refresh_core import refresh_market_rsi

if __name__ == '__main__':
    refresh_market_rsi(
        source_table='nasdaq_100_hist_data',
        target_table='nasdaq_100_rsi_data',
        id_col='ticker',
        market_label='nasdaq',
    )
