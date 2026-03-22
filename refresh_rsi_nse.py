"""
RSI Refresh — NSE 500 (Incremental)
====================================
Schedule: Run after NSE market data ingestion completes.
Only computes RSI for new price data since the last run.

Source: nse_500_hist_data → Target: nse_500_rsi_data
"""
from rsi_refresh_core import refresh_market_rsi

if __name__ == '__main__':
    refresh_market_rsi(
        source_table='nse_500_hist_data',
        target_table='nse_500_rsi_data',
        id_col='ticker',
        market_label='nse',
    )
