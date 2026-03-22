"""
MACD Refresh — NSE (Incremental)
=================================
Schedule: Run after NSE market data ingestion completes.

Source: nse_500_hist_data -> Target: nse_500_macd_data
"""
from macd_refresh_core import refresh_market_macd

if __name__ == '__main__':
    refresh_market_macd(
        source_table='nse_500_hist_data',
        target_table='nse_500_macd_data',
        id_col='ticker',
        market_label='nse',
    )
