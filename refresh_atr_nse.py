"""Incremental ATR refresh for NSE market."""
from atr_refresh_core import refresh_market_atr

if __name__ == '__main__':
    refresh_market_atr(
        source_table='nse_500_hist_data',
        target_table='nse_500_atr_data',
        id_col='ticker',
        market_label='NSE'
    )
