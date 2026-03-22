"""Incremental EMA/SMA refresh for NSE market."""
from ema_refresh_core import refresh_market_ema

if __name__ == '__main__':
    refresh_market_ema(
        source_table='nse_500_hist_data',
        target_table='nse_500_ema_sma_data',
        id_col='ticker',
        market_label='NSE'
    )
