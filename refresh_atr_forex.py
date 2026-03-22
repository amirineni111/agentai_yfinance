"""Incremental ATR refresh for Forex market."""
from atr_refresh_core import refresh_market_atr

if __name__ == '__main__':
    refresh_market_atr(
        source_table='forex_hist_data',
        target_table='forex_atr_data',
        id_col='symbol',
        market_label='Forex'
    )
