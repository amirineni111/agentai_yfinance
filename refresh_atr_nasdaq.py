"""Incremental ATR refresh for NASDAQ market."""
from atr_refresh_core import refresh_market_atr

if __name__ == '__main__':
    refresh_market_atr(
        source_table='nasdaq_100_hist_data',
        target_table='nasdaq_100_atr_data',
        id_col='ticker',
        market_label='NASDAQ'
    )
