"""
MACD Refresh — Forex (Incremental)
====================================
Schedule: Run after Forex market data ingestion completes.

Source: forex_hist_data -> Target: forex_macd_data
"""
from macd_refresh_core import refresh_market_macd

if __name__ == '__main__':
    refresh_market_macd(
        source_table='forex_hist_data',
        target_table='forex_macd_data',
        id_col='symbol',
        market_label='forex',
    )
