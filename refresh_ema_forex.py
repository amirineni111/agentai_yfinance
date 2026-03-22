"""Incremental EMA/SMA refresh for Forex market."""
from ema_refresh_core import refresh_market_ema

if __name__ == '__main__':
    refresh_market_ema(
        source_table='forex_hist_data',
        target_table='forex_ema_sma_data',
        id_col='symbol',
        market_label='Forex'
    )
