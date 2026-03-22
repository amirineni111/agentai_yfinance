"""
Daily RSI Refresh — All Markets (Incremental)
==============================================
Refreshes RSI for all 3 markets in sequence using incremental Wilder's smoothing.
Only new price data since the last run is processed — no truncate/reload.

For per-market scheduling, use the individual scripts instead:
  - refresh_rsi_nasdaq.py
  - refresh_rsi_nse.py
  - refresh_rsi_forex.py

Tables updated:
  - nasdaq_100_rsi_data  (from nasdaq_100_hist_data)
  - nse_500_rsi_data     (from nse_500_hist_data)
  - forex_rsi_data       (from forex_hist_data)
"""
import logging
from datetime import datetime
from rsi_refresh_core import refresh_market_rsi

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'rsi_refresh_all_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
log = logging.getLogger(__name__)

MARKETS = [
    {'source': 'nasdaq_100_hist_data', 'target': 'nasdaq_100_rsi_data', 'id_col': 'ticker', 'label': 'nasdaq'},
    {'source': 'nse_500_hist_data',    'target': 'nse_500_rsi_data',    'id_col': 'ticker', 'label': 'nse'},
    {'source': 'forex_hist_data',      'target': 'forex_rsi_data',      'id_col': 'symbol', 'label': 'forex'},
]


def refresh_all():
    """Incremental RSI refresh for all markets."""
    total_inserted = 0
    for market in MARKETS:
        rows = refresh_market_rsi(
            source_table=market['source'],
            target_table=market['target'],
            id_col=market['id_col'],
            market_label=market['label'],
        )
        total_inserted += rows
    log.info(f"All markets done — {total_inserted} total new rows inserted")


if __name__ == '__main__':
    log.info("=" * 60)
    log.info("Starting RSI refresh — all markets (incremental)")
    log.info("=" * 60)
    refresh_all()
