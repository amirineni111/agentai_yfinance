"""
RSI Refresh — Forex (Incremental)
==================================
Schedule: Run after Forex market data ingestion completes.
Only computes RSI for new price data since the last run.

Source: forex_hist_data → Target: forex_rsi_data
"""
from rsi_refresh_core import refresh_market_rsi

if __name__ == '__main__':
    refresh_market_rsi(
        source_table='forex_hist_data',
        target_table='forex_rsi_data',
        id_col='symbol',
        market_label='forex',
    )
