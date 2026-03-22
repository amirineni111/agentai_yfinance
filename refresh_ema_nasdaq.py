"""Incremental EMA/SMA refresh for NASDAQ market."""
from ema_refresh_core import refresh_market_ema

if __name__ == '__main__':
    refresh_market_ema(
        source_table='nasdaq_100_hist_data',
        target_table='nasdaq_100_ema_sma_data',
        id_col='ticker',
        market_label='NASDAQ'
    )
