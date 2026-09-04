"""
Daily AI Direction Prediction Job (v4 — Classification + Sector Training)
==========================================================================
Runs daily to:
1. Update actual prices for past predictions (backtest)
2. Generate new direction predictions (UP/DOWN) per sector per market
3. Store predictions in ai_prediction_history
4. Active learning adjusts confidence based on historical accuracy

v4 Accuracy Improvements (42-46% → target 52-58%):
- FIX 1: Per-SECTOR training instead of per-market pooling (+3-5%)
- FIX 2: LightGBM is_unbalance=True for UP/DOWN class imbalance (+2-4%)
- FIX 3: Market regime filter — skip SIDEWAYS tickers (+2-3%)
- FIX 4: New features: week52_position, rel_strength (+2-3%)
- FIX 5: Walk-forward windows 2 → 5 (better calibration)
- FIX 6: Removed correlated features, trimmed to 11 independent (+1-2%)
- FIX 7: Confidence recalibrated to actual walk-forward accuracy

v3 Changes (Classification Rewrite):
- Switched from REGRESSION to CLASSIFICATION (predict direction, not price)
- LightGBM Classifier + Logistic Regression ensemble (diverse model types)
- Per-MARKET training (pools all tickers) instead of per-ticker (massively faster)
- Both 3-day and 7-day horizons retained

Differentiation from sibling repos (sqlserver_copilot / sqlserver_copilot_nse):
- Those repos: 5-day horizon, GradientBoosting+RF+ExtraTrees+LogReg VotingClassifier
- This repo: 3-day + 7-day horizons, LightGBM + LogReg, 11 trimmed features, sector training

Schedule this to run daily via Windows Task Scheduler.
"""

import pandas as pd
import numpy as np
import pyodbc
from datetime import datetime, timedelta
import traceback
import sys
import argparse
import warnings
warnings.filterwarnings('ignore')

# Force unbuffered output so logs appear immediately in Task Scheduler
sys.stdout.reconfigure(line_buffering=True)

# Import ML libraries
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
import lightgbm as lgb

# Shared outcome-grading SQL. Single source of truth for both this job's
# nightly Step 1 and the standalone backfill_actual_prices.py recovery run.
from backfill_actual_prices import DIRECTION_CORRECT_SQL, price_lookup_sql

# Database connection
def get_db_connection():
    """Get SQL Server database connection"""
    conn_str = (
        "DRIVER={SQL Server};"
        "SERVER=localhost\\MSSQLSERVER01;"
        "DATABASE=stockdata_db;"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)

# Configuration
MARKETS = {
    'NSE 500': {'table': 'nse_500_hist_data', 'symbol_col': 'ticker', 'company_col': 'company', 'rsi_table': 'nse_500_rsi_data', 'rsi_col': 'ticker'},
    'NASDAQ 100': {'table': 'nasdaq_100_hist_data', 'symbol_col': 'ticker', 'company_col': 'company', 'rsi_table': 'nasdaq_100_rsi_data', 'rsi_col': 'ticker'},
    'Forex': {'table': 'forex_hist_data', 'symbol_col': 'symbol', 'company_col': 'symbol', 'rsi_table': 'forex_rsi_data', 'rsi_col': 'symbol'},
}

# S2-1: Dropped 1-day predictions (37% accuracy = worse than coin flip)
# S2-6: 7-day is primary horizon (only one historically above 50%)
# S2-7: Dropped 3-day predictions (42.1% accuracy, systematic DOWN bias —
#        when predicting DOWN, actual market goes UP +0.15% on average)
PREDICTION_DAYS = [7]  # 7-day only; 3-day disabled (see S2-7)
MAX_STOCKS_PER_MARKET = None  # Set to None to process all tickers
MIN_DATA_POINTS = 200  # Minimum historical data per ticker
MIN_MARKET_SAMPLES = 5000  # Minimum pooled samples for per-market training

# Confidence bounds.
# Phase 6: widened from [30,80] to a bare sanity range. Confidence is now the
# isotonic-calibrated P(correct) (see predict_for_ticker_v4), so the bounds
# should only catch degenerate fits -- not compress the distribution. The old
# tight clamp is why every market's confidence looked identical in [30,80] and
# why a genuinely strong signal could not distinguish itself.
CONFIDENCE_MIN = 5
CONFIDENCE_MAX = 95

# Phase 6: actionability threshold on calibrated confidence. A prediction is
# tradeable when the model's own calibrated hit rate clears this bar.
#
# PROVISIONAL. Measured out-of-fold on the NASDAQ Financial Services pool
# (40,240 rows) after the target fix:
#
#   directional (UP+DOWN) accuracy by calibrated-confidence quartile
#     Q1 conf 34.2% -> 33.8%      Q3 conf 39.9% -> 37.6%
#     Q2 conf 37.8% -> 36.8%      Q4 conf 49.3% -> 44.1%
#
# 45.0 is roughly the top-quartile boundary. Note this is a 3-class problem:
# a directional call competes against a ~26-37% base rate, not 50%, because
# FLAT absorbs ~37% of outcomes. Do NOT read these as coin-flip comparisons.
#
# Set the real value per market from the realized reliability curve once ~2
# weeks of calibrated predictions have resolved. Do not tune it by guessing --
# and re-check the volume it admits: 55.0 would have passed only 4.3% of
# directional calls.
ACTIONABLE_CONFIDENCE_MIN = 45.0

# Magnitude sanity bounds.
#
# predicted_change_pct is a volatility proxy (sign x robust vol), not a
# forecast, but it reaches consumers and must not be absurd. A 7-day move
# beyond +/-50% is not a realistic central estimate for any liquid name; values
# past this always traced back to corrupt price history rather than genuine
# volatility.
MAX_PREDICTED_MOVE_PCT = 50.0

# Any single n-day return above this in the recent window means the price
# series contains a discontinuity — almost always an unadjusted reverse split
# (observed: ALIT $0.56 -> $19.62 in 7 bars = +3,404%). 150% is far outside
# genuine 7-day equity moves but well inside split territory.
#
# This corrupts every price-derived feature, not just the magnitude, so such
# tickers are marked is_actionable=0 with suppression_reason='PRICE_ARTIFACT'.
SPLIT_ARTIFACT_RETURN = 1.5

# Fraction of tickers allowed to error before a run is treated as failed.
# One bad ticker should not sink a 2,300-ticker run; half of them erroring
# means something systemic (schema drift, bad data load) and must not report
# success to Task Scheduler.
MAX_ERROR_RATE = 0.25

# =====================================================
# ACTIVE LEARNING CONFIGURATION
# =====================================================
# Phase 6: DISABLED. adjust_confidence_with_history() multiplies the calibrated
# confidence by hardcoded 1.15/1.05/0.80 factors, which un-calibrates the
# isotonic output that model_confidence now depends on. Re-enable only with a
# replacement that preserves calibration (e.g. refit the isotonic map on
# per-ticker history rather than rescaling its output).
USE_ACTIVE_LEARNING = False  # Learn from past prediction accuracy
MIN_PREDICTIONS_FOR_LEARNING = 10  # Minimum predictions needed to assess model performance
MIN_DIRECTION_ACCURACY = 0.45  # Skip models with < 45% direction accuracy
HISTORICAL_LOOKBACK_DAYS = 90  # Look back 90 days for performance analysis

# =====================================================
# RETIRED MODEL REGISTRY (Phase 5)
# These models ran until Feb 12, 2026 when the LGB+LR Ensemble took over.
# Excluded from active learning history to prevent skewing current Ensemble.
# =====================================================
RETIRED_MODELS = {
    'Linear Regression':    {'retired_date': '2026-02-12', 'superseded_by': 'Ensemble (LGB+LR)'},
    'Gradient Boosting':    {'retired_date': '2026-02-12', 'superseded_by': 'Ensemble (LGB+LR)'},
    'Random Forest':        {'retired_date': '2026-02-12', 'superseded_by': 'Ensemble (LGB+LR)'},
    'ExtraTreesClassifier': {'retired_date': '2026-02-12', 'superseded_by': 'Ensemble (LGB+LR)'},
}

# =====================================================
# 3-CLASS CLASSIFICATION THRESHOLDS (Phase 4C)
# Returns within these thresholds are labelled FLAT (class=1).
# 7-day: 1.5% is roughly 1 ATR for large-caps over a week.
# 3-day: 0.8% threshold is tighter (less noise in shorter window).
# =====================================================
FLAT_THRESHOLD_7D = 0.015   # ±1.5% for 7-day horizon (default / NSE-preserving)
FLAT_THRESHOLD_3D = 0.008   # ±0.8% for 3-day horizon

# Phase 5: Per-market FLAT band. A single global band created a UP/DOWN class
# skew that made NASDAQ disagree with the sibling ml_trading_predictions model.
# The band is calibrated per market from the realized 7-day return distribution
# (see calibrate_flat_threshold). These are the fallbacks used until calibration
# runs; NSE keeps the historical 1.5% to preserve its already-good behavior.
FLAT_THRESHOLD_7D_BY_MARKET = {
    'NSE 500':    0.015,
    'NASDAQ 100': 0.015,
    'Forex':      0.010,
}

# =====================================================
# WATCHLIST CONFIGURATION
# =====================================================
USE_WATCHLIST = False  # Set to True to use watchlist, False for all tickers

# Columns to exclude from ML features (raw values that don't generalize)
EXCLUDE_FROM_FEATURES = ['trading_date', 'close_price', 'high_price', 'low_price', 'volume', 'target', 'ticker']

# =====================================================
# V4 FIX 6: 11 NON-CORRELATED FEATURES (trimmed from 15)
# Removed: sma_20_ratio (corr >0.85 with ema_10_ratio),
#          momentum_10 (corr >0.80 with returns),
#          regime_mean_reversion (corr with bb_position),
#          regime_trend_consistency (corr with trend_strength),
#          regime_vol_ratio (corr with volatility_20)
# Added:   week52_position (52-week range position — strong breakout signal)
#          rel_strength (stock return vs market index)
# =====================================================
SELECTED_FEATURES_V4 = [
    'returns',               # Direct price momentum
    'rsi',                   # Mean-reversion signal (Wilder's from RSI tables)
    'rsi_change',            # RSI momentum acceleration
    'macd_histogram',        # Trend momentum change
    'bb_position',           # Mean reversion + volatility band position
    'volume_ratio',          # Volume confirmation of moves
    'volatility_20',         # Risk/volatility regime
    'ema_10_ratio',          # Short-term trend (price vs EMA)
    'hl_range',              # Intraday volatility
    'week52_position',       # 52-week high/low position (strong breakout signal)
    'rel_strength',          # Return vs market index (relative momentum)
    'index_return_20d',      # 20-day cumulative index return (regime signal: +ve=bull, -ve=bear)
    'sector_momentum',       # Mean 20-day return of sector peers (cross-sectional momentum)
    'sector_sentiment',      # SENTIMENT: Composite score from SQL Server sentiment tables
    'sector_finbert',        # SENTIMENT: FinBERT financial NLP score
    'sentiment_momentum_3d', # SENTIMENT: 3-day sentiment trend
    'sentiment_vs_avg_30d',  # SENTIMENT: Sentiment vs 30-day baseline
]

# =====================================================
# V4 FIX 1: SECTOR MAPS FOR PER-SECTOR TRAINING
# =====================================================
SECTOR_MAP_NSE = {
    'IT':        ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTIM', 'MPHASIS',
                  'COFORGE', 'PERSISTENT', 'OFSS'],
    'BANKING':   ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN',
                  'BANKBARODA', 'CANBK', 'PNB', 'FEDERALBNK', 'IDFCFIRSTB'],
    'FINANCE':   ['HDFC', 'BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN', 'MUTHOOTFIN',
                  'SHRIRAMFIN', 'LICHSGFIN', 'M&MFIN', 'MANAPPURAM'],
    'OIL_GAS':   ['RELIANCE', 'ONGC', 'IOC', 'BPCL', 'GAIL', 'MGL', 'IGL',
                  'PETRONET', 'HINDPETRO', 'GSPL'],
    'AUTO':      ['MARUTI', 'M&M', 'TATAMOTORS', 'BAJAJ-AUTO', 'EICHERMOT',
                  'HEROMOTOCO', 'TVSMOTOR', 'ASHOKLEY', 'MOTHERSON', 'BALKRISIND'],
    'PHARMA':    ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'BIOCON',
                  'LUPIN', 'AUROPHARMA', 'TORNTPHARM', 'ALKEM', 'IPCALAB'],
    'FMCG':      ['HINDUNILVR', 'ITC', 'NESTLEIND', 'DABUR', 'MARICO',
                  'GODREJCP', 'COLPAL', 'EMAMILTD', 'TATACONSUM', 'VBL'],
    'METALS':    ['TATASTEEL', 'JSWSTEEL', 'HINDALCO', 'VEDL', 'NATIONALUM',
                  'SAIL', 'NMDC', 'COALINDIA', 'HINDZINC', 'APL'],
    'INFRA':     ['LT', 'ADANIENT', 'ADANIPORTS', 'ULTRACEMCO', 'ACC',
                  'AMBUJACEM', 'SIEMENS', 'ABB', 'HAVELLS', 'POWERGRID'],
    'OTHER_NSE': [],   # Catch-all for tickers not in above sectors
}

SECTOR_MAP_NASDAQ = {
    'TECH_MEGA':    ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'GOOG', 'META', 'AMZN'],
    'TECH_MID':     ['AMD', 'INTC', 'QCOM', 'TXN', 'AVGO', 'MU', 'AMAT',
                     'KLAC', 'LRCX', 'MRVL'],
    'SOFTWARE':     ['ADBE', 'CRM', 'ORCL', 'NOW', 'INTU', 'WDAY', 'SNOW',
                     'DDOG', 'ZS', 'CRWD', 'OKTA', 'TEAM'],
    'CONSUMER':     ['TSLA', 'NFLX', 'SBUX', 'COST', 'BKNG', 'ABNB',
                     'EBAY', 'ETSY', 'DASH', 'LYFT'],
    'BIOTECH':      ['AMGN', 'GILD', 'BIIB', 'REGN', 'VRTX', 'IDXX',
                     'DXCM', 'ILMN', 'SGEN', 'ALXN'],
    'OTHER_NASDAQ': [],   # Catch-all
}

# V4 FIX 3: Regime detection thresholds
REGIME_TREND_MIN_ADX = 20     # ADX above this = trending market
REGIME_LOOKBACK_DAYS = 50     # Days to assess current regime

# Minimum samples per sector for training (lower than per-market since sector is smaller)
MIN_SECTOR_SAMPLES = 1000

# =====================================================
# SENTIMENT: Map internal sector codes → sentiment table sector names
# Tables: nasdaq_sector_sentiment, nse_sector_sentiment
# =====================================================
SENTIMENT_SECTOR_MAP = {
    'NSE 500': {
        'IT':        'Information Technology',
        'BANKING':   'Financial Services',    # Banking rolled into Financial Services
        'FINANCE':   'Financial Services',
        'OIL_GAS':   'Oil & Gas',
        'AUTO':      'Automobile',
        'PHARMA':    'Healthcare',
        'FMCG':      'Fast Moving Consumer Goods',
        'METALS':    'Metals & Mining',
        'INFRA':     None,                    # No matching sentiment sector
        'OTHER_NSE': None,
    },
    'NASDAQ 100': {
        'TECH_MEGA':    'Technology',
        'TECH_MID':     'Technology',
        'SOFTWARE':     'Technology',
        'CONSUMER':     'Consumer Cyclical',
        'BIOTECH':      'Healthcare',
        'OTHER_NASDAQ': None,
    },
    'Forex': {},
}

def log_message(message, level="INFO"):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Remove emojis that cause encoding issues in Windows console
    message = message.encode('ascii', 'ignore').decode('ascii')
    print(f"[{timestamp}] [{level}] {message}", flush=True)

def get_watchlist_stocks(conn, market):
    """Get stocks from database watchlist table"""
    query = """
    SELECT ticker, company_name
    FROM prediction_watchlist
    WHERE market = ? AND is_active = 1
    ORDER BY priority, ticker
    """
    
    df = pd.read_sql(query, conn, params=[market])
    
    if len(df) == 0:
        log_message(f"No active tickers in watchlist for {market}, falling back to top volume", "WARNING")
        return get_top_volume_stocks(conn, market, MAX_STOCKS_PER_MARKET)
    
    log_message(f"Loaded {len(df)} stocks from watchlist table for {market}")
    return df

def bulk_load_performance_history(conn, market):
    """
    BULK preload all active learning history for an entire market in ONE query.
    Returns nested dict: {ticker: {days_ahead: {model_name: metrics}}}.
    
    This replaces 768+ individual queries (256 stocks x 3 timeframes) with 1 query.
    """
    lookback_date = (datetime.now() - timedelta(days=HISTORICAL_LOOKBACK_DAYS)).date()
    
    query = """
    SELECT 
        ticker,
        days_ahead,
        model_name,
        COUNT(*) as prediction_count,
        AVG(CAST(direction_correct AS FLOAT)) as direction_accuracy,
        AVG(ABS(percentage_error)) as avg_error_pct,
        AVG(model_confidence) as avg_confidence,
        STDEV(percentage_error) as error_volatility
    FROM ai_prediction_history
    WHERE market = ?
      AND prediction_date >= ?
      AND actual_price IS NOT NULL
      AND direction_correct IS NOT NULL
      AND model_name NOT IN (
          'Linear Regression', 'Gradient Boosting',
          'Random Forest', 'ExtraTreesClassifier'
      )
      AND ISNULL(is_actionable, 1) = 1
    GROUP BY ticker, days_ahead, model_name
    HAVING COUNT(*) >= ?
    """
    
    cursor = conn.cursor()
    cursor.execute(query, (market, str(lookback_date), MIN_PREDICTIONS_FOR_LEARNING))
    
    all_history = {}
    for row in cursor.fetchall():
        ticker, days_ahead, model_name, count, direction_acc, avg_error, avg_conf, error_vol = row
        
        if ticker not in all_history:
            all_history[ticker] = {}
        if days_ahead not in all_history[ticker]:
            all_history[ticker][days_ahead] = {}
        
        all_history[ticker][days_ahead][model_name] = {
            'count': count,
            'direction_accuracy': direction_acc if direction_acc else 0.5,
            'avg_error_pct': avg_error if avg_error else 10.0,
            'avg_confidence': avg_conf if avg_conf else 50.0,
            'error_volatility': error_vol if error_vol else 5.0
        }
    
    return all_history

def adjust_confidence_with_history(confidence, model_name, performance_history):
    """
    Adjust predicted confidence based on historical model performance.
    
    ACTIVE LEARNING: Models that historically perform well get confidence boost,
    poor performers get confidence penalty.
    """
    if model_name not in performance_history:
        return confidence  # No history, return original confidence
    
    perf = performance_history[model_name]
    direction_acc = perf['direction_accuracy']
    
    # Adjust confidence based on actual historical accuracy
    if direction_acc >= 0.60:
        adjustment = 1.15  # +15% for strong performers
    elif direction_acc >= 0.55:
        adjustment = 1.05  # +5% for good performers
    elif direction_acc <= 0.48:
        adjustment = 0.80  # -20% for weak performers
    else:
        adjustment = 1.0   # No change for average performers
    
    adjusted_confidence = confidence * adjustment
    
    # Also consider error volatility - consistent models get bonus
    error_vol = perf.get('error_volatility', 5.0)
    if error_vol < 3.0:  # Very consistent
        adjusted_confidence *= 1.05
    elif error_vol > 8.0:  # Very volatile
        adjusted_confidence *= 0.95
    
    # Keep within unified bounds
    adjusted_confidence = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, adjusted_confidence))
    
    return adjusted_confidence


def get_tickers_with_new_data(conn, market):
    """
    OPTIMIZATION #4: Skip tickers with no new trading data since last prediction.
    Returns set of tickers that have new data since their last prediction date.
    """
    config = MARKETS[market]
    query = f"""
    SELECT DISTINCT h.{config['symbol_col']} as ticker
    FROM {config['table']} h
    LEFT JOIN (
        SELECT ticker, MAX(prediction_date) as last_pred_date
        FROM ai_prediction_history
        WHERE market = ?
        GROUP BY ticker
    ) p ON h.{config['symbol_col']} = p.ticker
    WHERE p.last_pred_date IS NULL
       OR h.trading_date > p.last_pred_date
    """
    df = pd.read_sql(query, conn, params=[market])
    return set(df['ticker'].tolist())


def get_top_volume_stocks(conn, market, limit=50):
    """Get top stocks by trading volume for a market (or all tickers if limit is None)."""
    config = MARKETS[market]
    
    top_clause = f"TOP {limit}" if limit else ""
    query = f"""
    SELECT {top_clause}
        {config['symbol_col']} as ticker,
        {config['company_col']} as company_name,
        AVG(CAST(volume AS FLOAT)) as avg_volume
    FROM {config['table']}
    WHERE trading_date >= DATEADD(day, -30, GETDATE())
    GROUP BY {config['symbol_col']}, {config['company_col']}
    ORDER BY avg_volume DESC
    """
    
    df = pd.read_sql(query, conn)
    return df

def get_top_stocks(conn, market, limit=50):
    """Get stocks based on configuration (watchlist or top volume)"""
    if USE_WATCHLIST:
        return get_watchlist_stocks(conn, market)
    else:
        return get_top_volume_stocks(conn, market, limit)

def bulk_load_stock_data(conn, market, tickers):
    """
    BULK load historical data for ALL tickers in one market.
    Returns dict: {ticker: DataFrame}.
    
    Batches queries in chunks of 1500 to stay safely under SQL Server's 2100 parameter limit.
    """
    config = MARKETS[market]
    BATCH_SIZE = 1500  # SQL Server max parameters is 2100; keep ample margin
    
    log_message(f"  Bulk loading data for {len(tickers)} tickers...")
    load_start = datetime.now()
    
    frames = []
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        placeholders = ','.join(['?' for _ in batch])
        query = f"""
        SELECT {config['symbol_col']} as ticker, trading_date, close_price, volume, high_price, low_price
        FROM {config['table']}
        WHERE {config['symbol_col']} IN ({placeholders})
          AND trading_date >= DATEADD(day, -400, GETDATE())
        ORDER BY {config['symbol_col']}, trading_date ASC
        """
        frames.append(pd.read_sql(query, conn, params=batch))
    
    df_all = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    load_elapsed = (datetime.now() - load_start).total_seconds()
    log_message(f"  Loaded {len(df_all):,} rows in {load_elapsed:.1f}s")
    
    # Split into per-ticker DataFrames using groupby (O(n) vs O(n*m))
    split_start = datetime.now()
    stock_data = {}
    if not df_all.empty:
        df_all = df_all.sort_values(['ticker', 'trading_date'])
        for ticker, group in df_all.groupby('ticker'):
            df = group.drop(columns=['ticker']).reset_index(drop=True)
            if len(df) >= MIN_DATA_POINTS:
                if len(df) > 1000:
                    df = df.tail(1000).reset_index(drop=True)
                stock_data[ticker] = df
    
    split_elapsed = (datetime.now() - split_start).total_seconds()
    log_message(f"  Split into {len(stock_data)} ticker DataFrames in {split_elapsed:.1f}s")
    
    return stock_data

def bulk_load_rsi_data(conn, market, tickers):
    """Bulk load pre-computed Wilder's RSI from materialized tables.
    Returns dict: {ticker: DataFrame with [trading_date, RSI]}.
    """
    config = MARKETS[market]
    rsi_table = config['rsi_table']
    rsi_col = config['rsi_col']
    BATCH_SIZE = 1500  # SQL Server max parameters is 2100; keep ample margin
    
    log_message(f"  Bulk loading RSI for {len(tickers)} tickers...")
    rsi_start = datetime.now()
    
    frames = []
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        placeholders = ','.join(['?' for _ in batch])
        query = f"""
        SELECT {rsi_col} as ticker, trading_date, RSI
        FROM dbo.{rsi_table}
        WHERE {rsi_col} IN ({placeholders})
          AND trading_date >= DATEADD(day, -400, GETDATE())
        ORDER BY {rsi_col}, trading_date ASC
        """
        frames.append(pd.read_sql(query, conn, params=batch))
    
    df_all = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    rsi_elapsed = (datetime.now() - rsi_start).total_seconds()
    log_message(f"  RSI query returned {len(df_all):,} rows in {rsi_elapsed:.1f}s")
    
    # Use groupby instead of repeated boolean indexing (O(n) vs O(n*m))
    rsi_by_ticker = {}
    if not df_all.empty:
        for ticker, group in df_all.groupby('ticker'):
            rsi_by_ticker[ticker] = group[['trading_date', 'RSI']].copy()
    
    return rsi_by_ticker


def calculate_technical_indicators_v4(df, rsi_df=None, market_index_returns=None):
    """Calculate 11 non-correlated technical indicators for ML features (v4).

    v4 changes vs v3:
      + Added week52_position  — 52-week range position (powerful breakout signal)
      + Added rel_strength     — stock return vs market index (relative momentum)
      - Removed sma_20_ratio   — correlated >0.85 with ema_10_ratio
      - Removed momentum_10    — correlated >0.80 with returns
      - Removed regime_mean_reversion    — correlated with bb_position
      - Removed regime_trend_consistency — correlated with trend_strength
      - Removed regime_vol_ratio         — correlated with volatility_20

    RSI is loaded from pre-computed Wilder's smoothing tables (matching TradingView).
    If rsi_df is None, falls back to inline SMA calculation.
    market_index_returns: optional pd.Series indexed by trading_date for rel_strength.
    """
    df = df.copy()

    # Convert price columns to numeric
    df['close_price'] = pd.to_numeric(df['close_price'], errors='coerce')
    df['high_price'] = pd.to_numeric(df['high_price'], errors='coerce')
    df['low_price'] = pd.to_numeric(df['low_price'], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    df = df.dropna()

    # 1. returns — daily % change
    df['returns'] = df['close_price'].pct_change()

    # 2. RSI (14-period, Wilder's smoothing from pre-computed table)
    if rsi_df is not None and not rsi_df.empty:
        df = df.merge(rsi_df[['trading_date', 'RSI']], on='trading_date', how='left')
        df['rsi'] = df['RSI']
        df.drop(columns=['RSI'], inplace=True)
    else:
        # Fallback: inline SMA method (less accurate than Wilder's)
        delta = df['close_price'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

    # 3. rsi_change — RSI momentum acceleration
    df['rsi_change'] = df['rsi'].diff()

    # 4. MACD histogram (as % of price)
    ema12 = df['close_price'].ewm(span=12, adjust=False).mean()
    ema26 = df['close_price'].ewm(span=26, adjust=False).mean()
    macd_line = (ema12 - ema26) / df['close_price'] * 100
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = macd_line - macd_signal

    # 5. Bollinger Band position (0 = at lower band, 1 = at upper band)
    bb_middle = df['close_price'].rolling(window=20).mean()
    bb_std = df['close_price'].rolling(window=20).std()
    bb_upper = bb_middle + (bb_std * 2)
    bb_lower = bb_middle - (bb_std * 2)
    df['bb_position'] = (df['close_price'] - bb_lower) / (bb_upper - bb_lower + 1e-8)

    # 6. volume_ratio (current vol / 20-SMA, capped)
    volume_sma_20 = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = (df['volume'] / volume_sma_20.replace(0, 1)).fillna(1.0).clip(upper=10.0)

    # 7. volatility_20 — 20-period rolling std of returns
    df['volatility_20'] = df['returns'].rolling(window=20).std()

    # 8. ema_10_ratio — price vs 10-period EMA
    ema10 = df['close_price'].ewm(span=10, adjust=False).mean()
    df['ema_10_ratio'] = df['close_price'] / ema10

    # 9. hl_range — intraday volatility (normalized)
    df['hl_range'] = (df['high_price'] - df['low_price']) / df['close_price']

    # 10. week52_position — WHERE is price in its 52-week range? (FIX 4)
    #     0.0 = at 52-week low, 1.0 = at 52-week high
    #     52-week high breakouts have persistent momentum; lows mean-revert
    low_52w = df['close_price'].rolling(window=252, min_periods=100).min()
    high_52w = df['close_price'].rolling(window=252, min_periods=100).max()
    range_52w = (high_52w - low_52w).replace(0, np.nan)
    df['week52_position'] = (df['close_price'] - low_52w) / range_52w
    df['week52_position'] = df['week52_position'].fillna(0.5)  # neutral default

    # 11. rel_strength — stock return vs market index (FIX 4)
    #     Stocks outperforming their index tend to continue outperforming
    # 12. index_return_20d — 20-day cumulative index return (Phase 4A regime signal)
    #     Positive = bull regime; negative = bear regime. Helps model learn regime-conditional patterns.
    if market_index_returns is not None and not market_index_returns.empty:
        idx_df = pd.DataFrame({
            'trading_date': market_index_returns.index,
            'index_return': market_index_returns.values
        })
        df = df.merge(idx_df, on='trading_date', how='left')
        df['index_return'] = df['index_return'].fillna(0)
        df['rel_strength'] = df['returns'].rolling(20).mean() - \
                             df['index_return'].rolling(20).mean()
        # 20-day cumulative index return: sum of daily returns ≈ log-return over window
        df['index_return_20d'] = df['index_return'].rolling(20).sum()
        df.drop(columns=['index_return'], inplace=True)
    else:
        df['rel_strength']    = 0.0  # Neutral — no index data provided
        df['index_return_20d'] = 0.0  # Neutral — no index data

    return df.dropna()

def train_sector_model(sector_df, days_ahead, market=None):
    """
    FIX 2 + FIX 5: Train a classification model on ONE sector's pooled data.
    Replaces train_market_model().

    Phase 5: `market` selects the per-market FLAT band
    (FLAT_THRESHOLD_7D_BY_MARKET) so the UP/FLAT/DOWN labels match each market's
    realized volatility instead of a single global 1.5% band.

    Changes vs v3:
      FIX 2: LightGBM is_unbalance=True (handles UP/DOWN class imbalance)
      FIX 5: Walk-forward windows 2 → 5 (better OOS accuracy estimate)
      FIX 6: Uses SELECTED_FEATURES_V4 (11 features, no correlated duplicates)

    Phase 6: the walk-forward pass now scores the BLENDED ensemble rather than
    averaging the two models' separate accuracies, and fits an isotonic
    calibrator mapping winning-class probability -> P(correct) on the same
    out-of-fold predictions. That calibrator is what produces model_confidence,
    replacing the hand-tuned piecewise formula whose output turned out to carry
    no information about accuracy (48-50% correct at every confidence level).

    Returns:
        (lgb_model, lr_model, scaler, wf_accuracy, lgb_weight, lr_weight, calibrator)
        or a 7-tuple of None if insufficient data.
    """
    FAILED = (None,) * 7
    df = sector_df.copy()

    # 3-class classification target: 2=UP, 1=FLAT, 0=DOWN (Phase 4C)
    # Phase 5: per-market 7-day band (falls back to global default if unknown market).
    if days_ahead >= 7:
        flat_threshold = FLAT_THRESHOLD_7D_BY_MARKET.get(market, FLAT_THRESHOLD_7D)
    else:
        flat_threshold = FLAT_THRESHOLD_3D

    # CRITICAL (Phase 6): shift WITHIN each ticker.
    #
    # sector_df is pd.concat over every ticker in the sector, then sorted by
    # trading_date (pool_sector_data), so consecutive rows are DIFFERENT
    # companies on the same date. A bare .shift(-days_ahead) therefore produced
    # price(other_company) / price(this_company) - 1, which is not a return at
    # all. Measured on the NASDAQ Financial Services pool (99,312 rows):
    #
    #   - shift(-7) stayed within the same ticker on 1 row out of 99,312
    #   - median |target| was 84.5% (max 923,634%) vs 2.6% for a real 7-day return
    #   - FLAT collapsed to 0.9% of labels instead of ~39%
    #   - labels matched the correct ones only 30.2% of the time
    #   - label purity within a ticker was 74.6%, i.e. the "target" mostly
    #     encoded which ticker the row belonged to
    #
    # Because ticker identity is inferable from the features, walk-forward
    # accuracy looked healthy (~58%) while live predictions sat at ~49%. That
    # gap -- not a stale artifact -- is why this model appeared to be a
    # coin flip in production across all three markets.
    #
    # groupby('ticker') preserves each ticker's date ordering (sector_df is
    # date-sorted and the sort is stable), so this is the same-ticker
    # n-trading-days-ahead return.
    if 'ticker' in df.columns:
        future_ret = (df.groupby('ticker')['close_price'].shift(-days_ahead)
                      / df['close_price'].replace(0, np.nan) - 1)
    else:
        # Single-ticker frame (no pooling) — a plain shift is already correct.
        future_ret = df['close_price'].shift(-days_ahead) / df['close_price'].replace(0, np.nan) - 1

    df['target'] = np.where(future_ret > flat_threshold, 2,
                   np.where(future_ret < -flat_threshold, 0, 1))
    # np.where maps NaN to class 1, so an explicit notna filter is required --
    # otherwise the last `days_ahead` rows of every ticker (the highest
    # time-weighted ones) become fabricated FLAT labels.
    df = df[future_ret.notna()]
    df['target'] = df['target'].astype(int)

    # Guard against the target silently becoming a cross-ticker price ratio
    # again. A real n-day equity return has a median magnitude of a few percent;
    # the corrupted version measured 84.5%. Cheap to check, and it fails loudly
    # in the log rather than after months of ~chance live predictions.
    _mag = future_ret.dropna().abs().median()
    if _mag is not None and _mag > 0.25:
        log_message(
            f"    [{days_ahead}d] TARGET SANITY CHECK FAILED: median |target| = "
            f"{_mag*100:.1f}% (expected <25% for a {days_ahead}-day return). "
            f"The target is probably being computed across ticker boundaries — "
            f"check that the shift is grouped by 'ticker'.", "ERROR"
        )

    if len(df) < MIN_SECTOR_SAMPLES:
        log_message(f"    [{days_ahead}d] Insufficient sector data ({len(df)} < {MIN_SECTOR_SAMPLES}), skipping", "WARNING")
        return FAILED

    # FIX 6: Use only the 11 non-correlated features
    feature_cols = [f for f in SELECTED_FEATURES_V4 if f in df.columns]
    if len(feature_cols) < 7:
        log_message(f"    [{days_ahead}d] Only {len(feature_cols)} features available, skipping", "WARNING")
        return FAILED

    X_all = df[feature_cols].values
    y_all = df['target'].values

    # Time-weighted sample weights (exponential recency)
    n_samples = len(y_all)
    time_positions = np.arange(n_samples) / n_samples
    time_weights = np.exp(1.2 * (time_positions - 1))
    time_weights = time_weights / time_weights.mean()

    # FIX 5: Walk-forward with 5 windows (was 2)
    n_windows = 5
    purge_gap = max(days_ahead + 3, 8)
    min_train = int(n_samples * 0.50)
    window_size = max(80, (n_samples - min_train) // (n_windows + 1))

    lgb_wf_scores = []   # Per-model scores for dynamic weighting (Phase 3)
    lr_wf_scores  = []

    # Phase 6: retain the raw out-of-fold probabilities so the blended ensemble
    # can be scored and calibrated once the weights are known. Scoring the two
    # models separately (the old approach) measured neither of the things that
    # actually ships.
    oof_lgb_proba = []
    oof_lr_proba  = []
    oof_y         = []

    for w in range(n_windows):
        train_end = min_train + w * window_size
        test_start = train_end + purge_gap
        test_end = min(test_start + window_size, n_samples)

        if test_start >= n_samples or test_end <= test_start:
            continue

        wf_X_train = X_all[:train_end]
        wf_y_train = y_all[:train_end]
        wf_X_test = X_all[test_start:test_end]
        wf_y_test = y_all[test_start:test_end]
        wf_weights = time_weights[:train_end]

        scaler_wf = StandardScaler()
        wf_X_train_s = scaler_wf.fit_transform(wf_X_train)
        wf_X_test_s = scaler_wf.transform(wf_X_test)

        # FIX 2: LightGBM with class_weight='balanced' (3-class; is_unbalance only works for binary)
        try:
            lgb_wf = lgb.LGBMClassifier(
                n_estimators=200, learning_rate=0.05, max_depth=6,
                num_leaves=31, min_child_samples=20, subsample=0.8,
                colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1,
                class_weight='balanced',   # Phase 4C: replaces is_unbalance for 3-class
                random_state=42, verbosity=-1, n_jobs=-1
            )
            lgb_wf.fit(wf_X_train_s, wf_y_train, sample_weight=wf_weights)
            lgb_p = lgb_wf.predict_proba(wf_X_test_s)
            lgb_wf_scores.append(np.mean(np.argmax(lgb_p, axis=1) == wf_y_test))
        except Exception as e:
            log_message(f"    LGB WF error: {e}", "WARNING")
            lgb_p = None

        try:
            lr_wf = LogisticRegression(C=0.1, max_iter=500, class_weight='balanced', random_state=42)
            lr_wf.fit(wf_X_train_s, wf_y_train, sample_weight=wf_weights)
            lr_p = lr_wf.predict_proba(wf_X_test_s)
            lr_wf_scores.append(np.mean(np.argmax(lr_p, axis=1) == wf_y_test))
        except Exception as e:
            log_message(f"    LR WF error: {e}", "WARNING")
            lr_p = None

        # Only keep folds where both models produced probabilities — a blended
        # score built from one model on some folds and two on others is not a
        # measurement of anything.
        if lgb_p is not None and lr_p is not None and lgb_p.shape == lr_p.shape:
            oof_lgb_proba.append(lgb_p)
            oof_lr_proba.append(lr_p)
            oof_y.append(wf_y_test)

    # Compute dynamic ensemble weights from per-model walk-forward accuracy (Phase 3)
    # Each model's weight = its WF accuracy share, clamped to [0.30, 0.70].
    lgb_avg = np.mean(lgb_wf_scores) if lgb_wf_scores else 0.60
    lr_avg  = np.mean(lr_wf_scores)  if lr_wf_scores  else 0.40
    _total  = lgb_avg + lr_avg
    lgb_weight = max(0.30, min(0.70, lgb_avg / _total)) if _total > 0 else 0.60
    lr_weight  = 1.0 - lgb_weight

    # Phase 6: score and calibrate the BLEND that actually ships.
    calibrator = None
    if oof_y:
        blend_proba = (lgb_weight * np.vstack(oof_lgb_proba)
                       + lr_weight * np.vstack(oof_lr_proba))
        y_oof       = np.concatenate(oof_y)
        pred_class  = np.argmax(blend_proba, axis=1)
        win_proba   = blend_proba[np.arange(len(pred_class)), pred_class]
        was_correct = (pred_class == y_oof).astype(float)

        wf_accuracy = float(was_correct.mean() * 100)

        # Map winning-class probability -> P(correct). Isotonic is the right
        # choice here: monotone but free-form, so it can express "this model's
        # 0.45 means 52% correct" without assuming a parametric shape.
        # Needs both outcomes present, or the fit is a constant.
        if len(was_correct) >= 50 and 0 < was_correct.sum() < len(was_correct):
            try:
                calibrator = IsotonicRegression(
                    y_min=0.02, y_max=0.98, out_of_bounds='clip'
                ).fit(win_proba, was_correct)
            except Exception as e:
                log_message(f"    Calibrator fit failed: {e} — falling back to WF accuracy", "WARNING")
    else:
        wf_accuracy = float(np.mean(lgb_wf_scores + lr_wf_scores) * 100) if (lgb_wf_scores or lr_wf_scores) else 50.0

    # Train final models on 80% of data (time-ordered)
    train_end_final = int(n_samples * 0.80)
    X_train = X_all[:train_end_final]
    y_train = y_all[:train_end_final]
    weights_train = time_weights[:train_end_final]
    X_test = X_all[train_end_final:]
    y_test = y_all[train_end_final:]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # FIX 2: Final LightGBM with class_weight='balanced' (3-class)
    lgb_model = lgb.LGBMClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=6,
        num_leaves=31, min_child_samples=20, subsample=0.8,
        colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1,
        class_weight='balanced',   # Phase 4C: replaces is_unbalance for 3-class
        random_state=42, verbosity=-1, n_jobs=-1
    )
    lgb_model.fit(X_train_scaled, y_train, sample_weight=weights_train)

    lr_model = LogisticRegression(C=0.1, max_iter=500, class_weight='balanced', random_state=42)
    lr_model.fit(X_train_scaled, y_train, sample_weight=weights_train)

    lgb_test_acc = np.mean(lgb_model.predict(X_test_scaled) == y_test) * 100 if len(y_test) > 0 else 0
    lr_test_acc = np.mean(lr_model.predict(X_test_scaled) == y_test) * 100 if len(y_test) > 0 else 0

    log_message(f"    [{days_ahead}d] Trained on {len(X_train):,} samples | "
                f"WF acc (blended, 5-fold): {wf_accuracy:.1f}% | "
                f"Test: LGB={lgb_test_acc:.1f}%, LR={lr_test_acc:.1f}% | "
                f"Weights: LGB={lgb_weight:.2f}, LR={lr_weight:.2f} | "
                f"Calibrator: {'fitted' if calibrator is not None else 'NONE (fallback)'}")

    if calibrator is not None:
        log_reliability(calibrator, win_proba, was_correct, days_ahead)

    return lgb_model, lr_model, scaler, wf_accuracy, lgb_weight, lr_weight, calibrator


def log_reliability(calibrator, win_proba, was_correct, days_ahead, n_bins=5):
    """
    Log the calibrator's reliability on the out-of-fold data it was fitted to:
    predicted P(correct) vs realized, in equal-count bins.

    This is the immediate check on Phase 6 -- it does not require waiting for
    the 7-day horizon to resolve. A well-behaved calibrator shows realized
    accuracy tracking predicted confidence across bins. A flat line means the
    features carry no confidence signal and no amount of rescaling will help.
    """
    try:
        conf = calibrator.predict(win_proba)
        order = np.argsort(conf)
        parts = np.array_split(order, n_bins)
        cells = []
        for part in parts:
            if len(part) == 0:
                continue
            cells.append(f"{conf[part].mean()*100:.0f}%->{was_correct[part].mean()*100:.0f}%")
        log_message(f"    [{days_ahead}d] Reliability (pred->actual, n={len(win_proba):,}): "
                    + "  ".join(cells))
    except Exception as e:
        log_message(f"    Reliability check failed: {e}", "WARNING")


def predict_for_ticker_v4(ticker_df, lgb_model, lr_model, scaler, wf_accuracy, days_ahead,
                          lgb_weight=0.6, lr_weight=0.4, calibrator=None):
    """
    Generate a direction prediction for a single ticker.

    Changes vs v3:
      FIX 6: Uses SELECTED_FEATURES_V4 (11 + 2 regime features)
      Phase 3: Dynamic ensemble weights (lgb_weight, lr_weight) from WF per-model scoring.
      Phase 4C: 3-class output — 0=DOWN, 1=FLAT, 2=UP. Returns predicted_direction string.
      Phase 6: confidence is the isotonic-calibrated P(correct) from the
               walk-forward pass, so it means exactly one thing: the fraction
               of predictions at this score that come true. Verify it with the
               confidence-bucket query in docs, or the per-run reliability line.

    The previous formula (base anchored to WF accuracy + probability bonus +
    agreement bonus, clamped to [30,80]) was measurably uninformative: accuracy
    was 48-50% in every confidence bucket on both NASDAQ and NSE. Do not
    reintroduce hand-tuned additive bonuses here -- they destroy calibration.

    Regime check is done in the main loop before calling this function.

    Returns:
        (direction, predicted_change_pct, confidence, predicted_direction,
         price_series_suspect)
        or (None, None, None, None, False) if prediction not possible
    """
    feature_cols = [f for f in SELECTED_FEATURES_V4 if f in ticker_df.columns]
    if len(feature_cols) < 7:
        return None, None, None, None, False

    latest = ticker_df[feature_cols].iloc[-1:].values
    latest_scaled = scaler.transform(latest)

    # Ensemble: dynamic weights from walk-forward per-model accuracy (Phase 3)
    lgb_proba = lgb_model.predict_proba(latest_scaled)[0]   # shape: [n_classes]
    lr_proba  = lr_model.predict_proba(latest_scaled)[0]
    avg_proba = lgb_weight * lgb_proba + lr_weight * lr_proba

    # 3-class prediction (Phase 4C): 0=DOWN, 1=FLAT, 2=UP
    predicted_class = int(np.argmax(avg_proba))
    direction_prob  = float(avg_proba[predicted_class])
    direction_labels = {0: 'DOWN', 1: 'FLAT', 2: 'UP'}
    predicted_direction = direction_labels[predicted_class]

    # Binary direction for backward-compat fields (FLAT is treated conservatively as 0/DOWN)
    direction = 1 if predicted_class == 2 else 0

    # Magnitude: robust volatility of recent n-day returns.
    #
    # This is a volatility proxy, NOT a price forecast — the model outputs
    # direction only. But it is stored in predicted_price and surfaces to
    # consumers, so it has to be sane.
    #
    # Plain std() blew up on tickers with an unadjusted reverse split. A single
    # price discontinuity contaminates exactly `days_ahead` overlapping windows,
    # e.g. ALIT went $0.56 -> $19.62 in 7 bars (a 3,404% "return"), giving
    # std = 9.886 and a printed forecast of -988.6%. Observed Sep 2026: AMOD
    # +801%, ALIT -989%, AIFU +577%, AEHL +423%.
    #
    # Winsorizing does not fix this: 7 of 60 windows (11.7%) are contaminated,
    # so a 5-95pct clip barely moves the estimate (ALIT 988% -> 973%). MAD
    # tolerates up to 50% contamination and returns a sensible 16.7%.
    # 1.4826 rescales MAD to be consistent with std under normality.
    recent_returns = ticker_df['close_price'].pct_change(days_ahead).dropna().tail(60)
    if len(recent_returns) > 10:
        med = recent_returns.median()
        vol_estimate = 1.4826 * (recent_returns - med).abs().median()
        # MAD collapses to 0 for a flat/halted series — fall back rather than
        # emit a 0% move.
        if not np.isfinite(vol_estimate) or vol_estimate <= 0:
            vol_estimate = 0.03
    else:
        vol_estimate = 0.03

    # A split artifact means the PRICE SERIES is corrupt, which means the
    # features derived from it (returns, volatility_20, hl_range,
    # week52_position) are corrupt too — so the direction call is untrustworthy,
    # not just the magnitude. Flag it so the caller can suppress actionability.
    price_series_suspect = bool(
        len(recent_returns) > 10
        and (recent_returns.abs() > SPLIT_ARTIFACT_RETURN).any()
    )

    sign = 1.0 if predicted_class == 2 else (-1.0 if predicted_class == 0 else 0.0)
    predicted_change_pct = sign * vol_estimate * 100

    # Belt and braces: a hard cap so nothing absurd can reach the database even
    # if a new failure mode defeats the robust estimator.
    predicted_change_pct = float(np.clip(predicted_change_pct,
                                         -MAX_PREDICTED_MOVE_PCT,
                                          MAX_PREDICTED_MOVE_PCT))

    # Phase 6: confidence = calibrated P(this prediction is correct), as a
    # percentage. The isotonic map was fitted on out-of-fold walk-forward
    # predictions from this same sector model, so it is specific to this
    # sector, market, and horizon.
    if calibrator is not None:
        confidence = float(calibrator.predict([direction_prob])[0]) * 100.0
    else:
        # No calibrator (too few out-of-fold rows, or the fit failed): fall back
        # to the sector's blended walk-forward accuracy. Honest and uninformative
        # rather than confidently wrong.
        confidence = float(wf_accuracy)

    # Wide sanity bound only. The old [30,80] clamp was tight enough to be the
    # dominant effect on the output distribution and made every market's
    # confidence range look identical.
    confidence = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, confidence))

    return direction, predicted_change_pct, confidence, predicted_direction, price_series_suspect


def get_sector_for_ticker(ticker, market):
    """
    FIX 1: Return the sector name for a given ticker and market.
    Falls back to OTHER_<market> catch-all if ticker not in any sector.
    """
    if market == 'NSE 500':
        sector_map = SECTOR_MAP_NSE
    elif market == 'NASDAQ 100':
        sector_map = SECTOR_MAP_NASDAQ
    else:
        return 'FOREX'  # Forex has no sectors — treat all as one group

    for sector, tickers in sector_map.items():
        if ticker in tickers:
            return sector

    return f'OTHER_{market.split()[0]}'


def build_sector_groups(ticker_list, market):
    """
    FIX 1: Group tickers by sector.
    Returns {sector_name: [ticker1, ticker2, ...]}
    """
    groups = {}
    for ticker in ticker_list:
        sector = get_sector_for_ticker(ticker, market)
        if sector not in groups:
            groups[sector] = []
        groups[sector].append(ticker)

    for sector, tickers in sorted(groups.items()):
        log_message(f"    Sector {sector}: {len(tickers)} tickers")

    return groups


def refresh_sector_map_from_db(conn, market):
    """
    Phase 5 (primary NASDAQ fix): replace the hardcoded SECTOR_MAP_NASDAQ with a
    data-driven ticker -> GICS sector map read from dbo.nasdaq_top100.

    Why: the NASDAQ universe (nasdaq_100_hist_data) is ~2,368 tickers, but the
    hardcoded map named only ~49 of them, so ~2,300 tickers were dumped into the
    single OTHER_NASDAQ catch-all and trained as one model across unrelated
    industries. That noise is why NASDAQ predictions stopped agreeing with the
    sibling ml_trading_predictions model while NSE (well-sectored) kept agreeing.

    nasdaq_top100.sector uses the SAME 11 GICS names as nasdaq_sector_sentiment,
    so the sentiment map becomes an identity mapping (no translation table needed).

    Mutates the module globals SECTOR_MAP_NASDAQ and SENTIMENT_SECTOR_MAP['NASDAQ 100'].
    Only acts for 'NASDAQ 100'; NSE/Forex keep their existing hardcoded maps so their
    (already-good) behavior and sentiment wiring are untouched.
    Falls back silently to the hardcoded map on any error.
    """
    if market != 'NASDAQ 100':
        return

    global SECTOR_MAP_NASDAQ
    try:
        df = pd.read_sql(
            "SELECT ticker, sector FROM dbo.nasdaq_top100 WHERE sector IS NOT NULL",
            conn,
        )
        if df.empty:
            log_message("  Sector map: nasdaq_top100 returned no rows — keeping hardcoded map", "WARNING")
            return

        new_map = {}
        for sector, grp in df.groupby('sector'):
            new_map[sector] = sorted(grp['ticker'].dropna().unique().tolist())
        new_map['OTHER_NASDAQ'] = []   # catch-all for NULL-sector / unlisted tickers

        SECTOR_MAP_NASDAQ.clear()
        SECTOR_MAP_NASDAQ.update(new_map)

        # GICS sector names match the sentiment table names exactly -> identity map.
        SENTIMENT_SECTOR_MAP['NASDAQ 100'] = {s: (None if s == 'OTHER_NASDAQ' else s)
                                              for s in new_map.keys()}

        named = sum(len(v) for k, v in new_map.items() if k != 'OTHER_NASDAQ')
        log_message(f"  Sector map (DB): {len(new_map)-1} GICS sectors covering {named} NASDAQ tickers "
                    f"(was ~49 hardcoded; catch-all now only NULL-sector names)")
    except Exception as e:
        log_message(f"  Sector map: DB load failed ({e}) — keeping hardcoded map", "WARNING")


def calibrate_flat_threshold(market, all_stock_data, days_ahead=7):
    """
    Phase 5: derive the 7-day FLAT band for a market from its realized return
    distribution (~0.5x the median absolute n-day return), so UP/FLAT/DOWN labels
    are balanced to the market's own volatility instead of a fixed global 1.5%.

    Mutates FLAT_THRESHOLD_7D_BY_MARKET[market]. Clamped to [0.8%, 4%] for safety.
    No-op for horizons < 7 (3-day is disabled) and on insufficient data.
    """
    if days_ahead < 7 or not all_stock_data:
        return
    try:
        abs_rets = []
        for df in all_stock_data.values():
            if 'close_price' in df and len(df) > days_ahead + 30:
                r = df['close_price'].astype(float).pct_change(days_ahead).abs().dropna()
                if len(r):
                    abs_rets.append(r.median())
        if not abs_rets:
            return
        band = float(np.median(abs_rets)) * 0.5
        band = max(0.008, min(0.04, band))
        prev = FLAT_THRESHOLD_7D_BY_MARKET.get(market)
        FLAT_THRESHOLD_7D_BY_MARKET[market] = round(band, 4)
        log_message(f"  FLAT band calibrated for {market}: {band:.4f} (was {prev})")
    except Exception as e:
        log_message(f"  FLAT band calibration failed ({market}): {e} — keeping default", "WARNING")


def classify_market_regime(df):
    """
    FIX 3: Classify the current price regime for a single ticker's DataFrame.

    Returns:
        'BULL_TREND'   — Strong uptrend; momentum strategies work well
        'BEAR_TREND'   — Strong downtrend; momentum strategies work well
        'SIDEWAYS'     — Choppy/ranging; momentum signals unreliable — suppress
        'INSUFFICIENT' — Not enough data

    Used to gate predictions: SIDEWAYS and INSUFFICIENT tickers are still
    predicted and stored, but flagged is_actionable=0 with this regime as
    the suppression_reason.
    """
    if len(df) < REGIME_LOOKBACK_DAYS + 50:
        return 'INSUFFICIENT'

    close = df['close_price'].astype(float)
    high = df['high_price'].astype(float)
    low = df['low_price'].astype(float)

    sma_50 = close.rolling(50).mean().iloc[-1]
    sma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
    price = close.iloc[-1]

    # ADX (trend strength)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    dm_pos = (high.diff()).clip(lower=0)
    dm_neg = (-low.diff()).clip(lower=0)

    period = 14
    atr14 = tr.rolling(period).mean()
    di_pos = 100 * (dm_pos.rolling(period).mean() / atr14.replace(0, np.nan))
    di_neg = 100 * (dm_neg.rolling(period).mean() / atr14.replace(0, np.nan))
    dx = 100 * ((di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan))
    adx = dx.rolling(period).mean().iloc[-1]

    # Trend consistency: % of last 20 days in same direction
    recent = close.tail(REGIME_LOOKBACK_DAYS)
    overall_direction = 1 if recent.iloc[-1] > recent.iloc[0] else -1
    daily_directions = np.sign(close.diff().tail(20))
    consistency = (daily_directions == overall_direction).mean()

    is_trending = (not np.isnan(adx)) and (adx > REGIME_TREND_MIN_ADX) and (consistency > 0.55)

    if is_trending:
        if sma_200 is not None and not np.isnan(sma_200):
            if price > sma_50 > sma_200:
                return 'BULL_TREND'
            elif price < sma_50 < sma_200:
                return 'BEAR_TREND'
        if price > sma_50:
            return 'BULL_TREND'
        else:
            return 'BEAR_TREND'
    else:
        return 'SIDEWAYS'


def load_sentiment_data(conn, market):
    """
    Load sector-level sentiment from SQL Server sentiment tables.

    Sources:
        NASDAQ 100 → dbo.nasdaq_sector_sentiment
        NSE 500    → dbo.nse_sector_sentiment
        Forex      → None (no sentiment table)

    Returns:
        dict keyed by internal sector code (e.g. 'IT', 'TECH_MEGA').
        Each value is a DataFrame with columns:
            [trading_date, sector_sentiment, sector_finbert,
             sentiment_momentum_3d, sentiment_vs_avg_30d]
        Returns {} on failure or unsupported market.
    """
    table_map = {
        'NASDAQ 100': 'nasdaq_sector_sentiment',
        'NSE 500':    'nse_sector_sentiment',
    }
    table = table_map.get(market)
    if not table:
        return {}

    sector_name_map = SENTIMENT_SECTOR_MAP.get(market, {})

    try:
        query = f"""
            SELECT trading_date, sector,
                   sentiment_score, finbert_score,
                   sentiment_momentum_3d, sentiment_vs_avg_30d
            FROM dbo.[{table}]
            WHERE trading_date >= DATEADD(day, -400, GETDATE())
            ORDER BY trading_date ASC
        """
        df_all = pd.read_sql(query, conn)
        if df_all.empty:
            return {}

        df_all['trading_date'] = pd.to_datetime(df_all['trading_date'])
        df_all = df_all.rename(columns={
            'sentiment_score':      'sector_sentiment',
            'finbert_score':        'sector_finbert',
        })

        # Invert the sector name map so we can look up by sentiment table name
        # Multiple internal codes can map to the same sentiment sector name (e.g. TECH_MEGA/TECH_MID/SOFTWARE → Technology)
        result = {}
        for internal_code, sentiment_name in sector_name_map.items():
            if sentiment_name is None:
                continue
            sector_rows = df_all[df_all['sector'] == sentiment_name].copy()
            if sector_rows.empty:
                continue
            result[internal_code] = sector_rows[
                ['trading_date', 'sector_sentiment', 'sector_finbert',
                 'sentiment_momentum_3d', 'sentiment_vs_avg_30d']
            ].reset_index(drop=True)

        return result

    except Exception as e:
        log_message(f"  Sentiment load failed ({market}): {e} — defaulting to 0", "WARNING")
        return {}


def pool_sector_data(sector_tickers, all_stock_data, rsi_by_ticker=None,
                    market_index_returns=None, sector_sentiment_df=None):
    """
    FIX 1: Pool only the tickers belonging to ONE sector (replaces pool_market_data).

    Sentiment integration: if sector_sentiment_df is provided (a DataFrame with
    [trading_date, sector_sentiment, sector_finbert, sentiment_momentum_3d,
    sentiment_vs_avg_30d]), it is merged by trading_date into each ticker's
    feature set. Missing dates are forward-filled then filled with 0.

    Returns:
        (sector_df, ticker_latest)
          sector_df    : Pooled DataFrame for model training
          ticker_latest: {ticker: DataFrame} for per-ticker prediction
    """
    if rsi_by_ticker is None:
        rsi_by_ticker = {}

    # Prepare sentiment lookup (indexed by date) if available
    sent_df = None
    if sector_sentiment_df is not None and not sector_sentiment_df.empty:
        sent_df = sector_sentiment_df.copy()
        sent_df['trading_date'] = pd.to_datetime(sent_df['trading_date'])
        sent_df = sent_df.sort_values('trading_date').drop_duplicates('trading_date')

    all_frames = []
    ticker_latest = {}

    for ticker in sector_tickers:
        df_raw = all_stock_data.get(ticker)
        if df_raw is None:
            continue

        df = calculate_technical_indicators_v4(
            df_raw,
            rsi_df=rsi_by_ticker.get(ticker),
            market_index_returns=market_index_returns
        )

        if len(df) < 100:
            continue

        # Merge sector sentiment by trading_date
        if sent_df is not None:
            df['trading_date'] = pd.to_datetime(df['trading_date'])
            df = df.merge(
                sent_df[['trading_date', 'sector_sentiment', 'sector_finbert',
                          'sentiment_momentum_3d', 'sentiment_vs_avg_30d']],
                on='trading_date', how='left'
            )
            # Forward-fill (use last known sentiment on days with no update)
            for col in ['sector_sentiment', 'sector_finbert',
                        'sentiment_momentum_3d', 'sentiment_vs_avg_30d']:
                df[col] = df[col].ffill().fillna(0.0)
        else:
            df['sector_sentiment']      = 0.0
            df['sector_finbert']        = 0.0
            df['sentiment_momentum_3d'] = 0.0
            df['sentiment_vs_avg_30d']  = 0.0

        if len(df) < 100:
            continue

        ticker_latest[ticker] = df

        df_copy = df.copy()
        df_copy['ticker'] = ticker
        all_frames.append(df_copy)

    if not all_frames:
        return pd.DataFrame(), ticker_latest

    sector_df = pd.concat(all_frames, ignore_index=True)
    sector_df = sector_df.sort_values('trading_date').reset_index(drop=True)

    # Phase 4A: sector_momentum — mean 20-day return across all sector tickers per date
    # Computed cross-sectionally after pooling so all peers are available.
    sector_df['__close_prev20__'] = sector_df.groupby('ticker')['close_price'].shift(20)
    sector_df['__ret_20d__'] = (
        (sector_df['close_price'] - sector_df['__close_prev20__'])
        / sector_df['__close_prev20__'].replace(0, np.nan)
    )
    sector_momentum_df = (
        sector_df.groupby('trading_date')['__ret_20d__'].mean()
        .rename('sector_momentum')
        .reset_index()
    )
    sector_df = sector_df.merge(sector_momentum_df, on='trading_date', how='left')
    sector_df['sector_momentum'] = sector_df['sector_momentum'].ffill().fillna(0.0)
    sector_df.drop(columns=['__close_prev20__', '__ret_20d__'], inplace=True)

    # Also add sector_momentum into per-ticker prediction DataFrames
    for ticker in list(ticker_latest.keys()):
        df = ticker_latest[ticker]
        df = df.merge(sector_momentum_df, on='trading_date', how='left')
        df['sector_momentum'] = df['sector_momentum'].ffill().fillna(0.0)
        ticker_latest[ticker] = df

    return sector_df, ticker_latest

def load_existing_predictions(cursor, market):
    """
    BULK preload today's existing predictions for a market in ONE query.
    Returns a set of (ticker, days_ahead, model_name) tuples for fast duplicate checking.
    Replaces ~2250 individual SELECT COUNT(*) queries per market.
    """
    prediction_date = datetime.now().date()
    cursor.execute("""
        SELECT ticker, days_ahead, model_name
        FROM ai_prediction_history
        WHERE market = ? AND prediction_date = ?
    """, (market, str(prediction_date)))
    return {(row[0], row[1], row[2]) for row in cursor.fetchall()}


def store_prediction(cursor, market, ticker, company_name, days_ahead, model_name,
                    current_price, predicted_change, confidence, existing_predictions=None,
                    predicted_direction=None, is_actionable=1, suppression_reason=None,
                    flat_band_pct=None):
    """
    Store prediction in database.
    Skips if a prediction already exists for this market/ticker/date/days_ahead/model.
    Uses pre-loaded existing_predictions set for O(1) duplicate check instead of per-row SQL.
    Phase 4C: Writes predicted_direction (UP/FLAT/DOWN) when provided.
    Suppressed predictions carry is_actionable=0 and a suppression_reason;
    consumers filter ISNULL(is_actionable,1)=1.

    flat_band_pct records the UP/FLAT/DOWN label band this prediction was made
    under. calibrate_flat_threshold() re-derives that band every run, so the
    grader must read it off the row rather than assume a constant -- otherwise
    a FLAT call trained at 1.85% gets graded at 1.5%.
    """
    prediction_date = datetime.now().date()
    target_date = prediction_date + timedelta(days=days_ahead)
    predicted_price = current_price * (1 + predicted_change)
    
    # Fast in-memory duplicate check using pre-loaded set
    if existing_predictions is not None:
        if (ticker, days_ahead, model_name) in existing_predictions:
            return False  # Duplicate, skip
    else:
        # Fallback: individual SQL check (shouldn't happen in normal flow)
        dup_check = """
        SELECT COUNT(*) FROM ai_prediction_history 
        WHERE market = ? AND ticker = ? AND prediction_date = ? AND days_ahead = ? AND model_name = ?
        """
        cursor.execute(dup_check, (market, ticker, str(prediction_date), days_ahead, model_name))
        if cursor.fetchone()[0] > 0:
            return False
    
    query = """
    INSERT INTO ai_prediction_history
    (market, ticker, company_name, prediction_date, target_date, days_ahead, model_name,
     current_price, predicted_price, predicted_change_pct, model_confidence, predicted_direction,
     is_actionable, suppression_reason, flat_band_pct)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    cursor.execute(query, (
        market, ticker, company_name, str(prediction_date), str(target_date), days_ahead, model_name,
        float(current_price), float(predicted_price), float(predicted_change * 100), float(confidence),
        predicted_direction,   # None / 'UP' / 'FLAT' / 'DOWN'
        int(is_actionable), suppression_reason,  # 0 + 'FLAT'/'LOW_CONFIDENCE'/regime when suppressed
        float(flat_band_pct) if flat_band_pct is not None else None
    ))
    
    return True  # Inserted

def update_actual_prices(conn):
    """
    Update actual prices for past predictions where target_date has arrived.
    Uses batch SQL for performance instead of row-by-row.

    Grading SQL is imported from backfill_actual_prices so the nightly pass
    and the standalone recovery script can never disagree about whether a
    prediction was right.

    Returns True if every market's UPDATE succeeded, False otherwise. A
    per-market failure used to be swallowed by a bare log line, which is how
    the Feb 2026 overflow stall ran unnoticed for months.
    """
    today = datetime.now().date()
    cursor = conn.cursor()

    # Count pending first
    cursor.execute("""
        SELECT COUNT(*) FROM ai_prediction_history
        WHERE target_date <= ? AND actual_price IS NULL
    """, (str(today),))
    pending_count = cursor.fetchone()[0]
    log_message(f"Found {pending_count} predictions to update with actual prices")

    if pending_count == 0:
        return True

    total_updated = 0
    failed_markets = []

    # Include Forex for updating historical predictions (even though we no longer generate new ones)
    all_markets_for_update = dict(MARKETS)
    all_markets_for_update['Forex'] = {'table': 'forex_hist_data', 'symbol_col': 'symbol', 'company_col': 'symbol'}
    
    # Batch update for each market (uses JOIN for performance)
    for market, config in all_markets_for_update.items():
        table = config['table']
        symbol_col = config['symbol_col']
        
        # Update actual prices using batch SQL with JOIN.
        # Grading CASE and price lookup are imported from backfill_actual_prices
        # so both graders stay identical (they drifted apart once on the FLAT band).
        # Guards: NULLIF prevents division by zero; capped squared_error avoids numeric overflow
        update_sql = f"""
        UPDATE p
        SET
            p.actual_price = CAST(h.close_price AS FLOAT),
            p.actual_change_pct = CASE WHEN CAST(p.current_price AS FLOAT) = 0 THEN NULL
                ELSE ((CAST(h.close_price AS FLOAT) - CAST(p.current_price AS FLOAT)) / CAST(p.current_price AS FLOAT)) * 100 END,
            p.absolute_error = ABS(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT)),
            p.squared_error = CASE
                WHEN ABS(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT)) > 1000000 THEN 999999999999
                ELSE POWER(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT), 2) END,
            p.percentage_error = CASE WHEN CAST(h.close_price AS FLOAT) = 0 THEN NULL
                ELSE ABS(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT)) / CAST(h.close_price AS FLOAT) * 100 END,
            p.direction_correct = {DIRECTION_CORRECT_SQL},
            p.updated_at = GETDATE()
        FROM ai_prediction_history p
        {price_lookup_sql(table, symbol_col)}
        WHERE p.market = ?
          AND p.target_date <= ?
          AND p.actual_price IS NULL
        """

        try:
            cursor.execute(update_sql, (market, str(today)))
            updated = cursor.rowcount
            total_updated += updated
            if updated > 0:
                log_message(f"  {market}: Updated {updated} predictions with actual prices")
        except Exception as e:
            failed_markets.append(market)
            log_message(f"  {market}: Error updating actual prices: {str(e)}", "ERROR")

    conn.commit()
    log_message(f"Total updated: {total_updated} predictions with actual prices")

    # Anything still pending with an elapsed target_date is a real problem:
    # either a market's UPDATE failed, or the price history has a hole.
    cursor.execute("""
        SELECT market, COUNT(*) FROM ai_prediction_history
        WHERE target_date <= ? AND actual_price IS NULL
        GROUP BY market
    """, (str(today),))
    still_pending = {row[0]: row[1] for row in cursor.fetchall()}
    if still_pending:
        for mkt, cnt in sorted(still_pending.items()):
            log_message(f"  {mkt}: {cnt} predictions STILL unresolved past target_date", "WARNING")

    if failed_markets:
        log_message(f"BACKFILL FAILED for: {', '.join(failed_markets)}", "ERROR")
        return False

    return True

def run_daily_predictions(markets_filter=None):
    """
    Main function: per-MARKET classification training + per-ticker prediction.
    
    Flow per market:
    1. Load all tickers' data (bulk query)
    2. Compute features per ticker, pool into market DataFrame
    3. Train ONE LightGBM + ONE LogReg model on pooled data (per horizon)
    4. Predict direction for each ticker using trained model
    5. Store predictions
    """
    start_time = datetime.now()
    
    if markets_filter:
        markets_to_process = {k: v for k, v in MARKETS.items() if k in markets_filter}
        if not markets_to_process:
            log_message(f"ERROR: No valid markets in filter {markets_filter}. Available: {list(MARKETS.keys())}", "ERROR")
            exit(1)
    else:
        markets_to_process = MARKETS
    
    log_message("=" * 80)
    log_message("Starting Daily AI Direction Prediction Job (v4 - Classification + Sector Training)")
    log_message(f"Markets: {', '.join(markets_to_process.keys())}")
    log_message(f"Models: LightGBM + Logistic Regression (per-sector training)")
    log_message(f"Features: {len(SELECTED_FEATURES_V4)} selected indicators")
    log_message(f"Horizons: {PREDICTION_DAYS}")
    if USE_ACTIVE_LEARNING:
        log_message("ACTIVE LEARNING ENABLED")
    log_message("=" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Step 1: Update actual prices for past predictions
    log_message("Step 1: Updating actual prices for past predictions...")
    backfill_ok = update_actual_prices(conn)

    total_predictions = 0
    total_suppressed = 0
    total_no_direction = 0
    total_skipped_dup = 0
    total_skipped_data = 0
    total_skipped_unchanged = 0
    errors = 0
    
    # Step 2: Per-sector training and prediction
    for market in markets_to_process.keys():
        log_message(f"\nStep 2: Processing {market}...")
        market_start = datetime.now()

        # Phase 5: replace hardcoded NASDAQ sector map with data-driven GICS sectors
        # from nasdaq_top100 (no-op for NSE/Forex). Must run before build_sector_groups
        # and load_sentiment_data, which read the (now refreshed) module globals.
        refresh_sector_map_from_db(conn, market)

        # Get stocks
        stocks = get_top_stocks(conn, market, MAX_STOCKS_PER_MARKET)
        log_message(f"  Found {len(stocks)} stocks to analyze")

        # Skip tickers with no new data
        tickers_with_updates = get_tickers_with_new_data(conn, market)
        original_count = len(stocks)
        stocks = stocks[stocks['ticker'].isin(tickers_with_updates)]
        skipped_unchanged = original_count - len(stocks)
        total_skipped_unchanged += skipped_unchanged
        if skipped_unchanged > 0:
            log_message(f"  Skipped {skipped_unchanged} tickers with no new data")
        log_message(f"  {len(stocks)} tickers to process")

        if len(stocks) == 0:
            log_message(f"  {market} complete: No tickers need predictions")
            continue

        # Build ticker → company_name lookup
        ticker_company = dict(zip(stocks['ticker'], stocks['company_name']))

        # Bulk load all stock data
        ticker_list = stocks['ticker'].tolist()
        all_stock_data = bulk_load_stock_data(conn, market, ticker_list)
        tickers_with_data = len(all_stock_data)
        total_skipped_data += len(ticker_list) - tickers_with_data
        log_message(f"  {tickers_with_data} tickers have sufficient data (>= {MIN_DATA_POINTS} rows)")

        # Phase 5: calibrate the per-market FLAT band from realized 7-day volatility
        for _days in PREDICTION_DAYS:
            calibrate_flat_threshold(market, all_stock_data, _days)

        # Bulk preload active learning history
        all_performance_history = {}
        if USE_ACTIVE_LEARNING:
            all_performance_history = bulk_load_performance_history(conn, market)
            log_message(f"  Loaded active learning history for {len(all_performance_history)} tickers")

        # Bulk load pre-computed Wilder's RSI
        rsi_by_ticker = bulk_load_rsi_data(conn, market, ticker_list)
        log_message(f"  Loaded Wilder's RSI for {len(rsi_by_ticker)} tickers")

        # Load market index returns for rel_strength feature (safe fallback to None)
        index_returns = load_index_returns(conn, market)

        # Load sector sentiment from SQL Server sentiment tables
        all_sentiment = load_sentiment_data(conn, market)
        log_message(f"  Loaded sentiment for {len(all_sentiment)} sectors from DB")

        # Preload today's existing predictions (1 query instead of ~4500)
        existing_predictions = load_existing_predictions(cursor, market)
        if existing_predictions:
            log_message(f"  Found {len(existing_predictions)} existing predictions for today (will skip duplicates)")

        # FIX 1: Group tickers by sector and train per-sector models
        sector_groups = build_sector_groups(ticker_list, market)
        log_message(f"  Grouped into {len(sector_groups)} sectors")

        market_predictions = 0
        market_suppressed = 0

        def train_predict_pool(pool_label, sector_df, ticker_latest):
            """Train the per-sector ensemble and emit predictions for one pool.
            Shared by the per-sector loop and the small-sector fallback so both
            paths stay identical. Returns the number of predictions stored."""
            nonlocal total_predictions, market_predictions, market_suppressed, \
                total_suppressed, total_no_direction, total_skipped_dup, errors
            stored = 0
            for days_ahead in PREDICTION_DAYS:
                log_message(f"    Training {days_ahead}-day model for {pool_label}...")

                # Phase 6: train_sector_model returns 7 values (adds the isotonic calibrator)
                (lgb_model, lr_model, scaler, wf_accuracy,
                 lgb_weight, lr_weight, calibrator) = train_sector_model(sector_df, days_ahead, market)

                if lgb_model is None:
                    log_message(f"    {days_ahead}-day model training failed, skipping", "WARNING")
                    continue

                log_message(f"    [{days_ahead}d] Weights: LGB={lgb_weight:.2f}, LR={lr_weight:.2f} | "
                            f"Predicting for {len(ticker_latest)} tickers...")

                # The band these labels were trained under — stored per row so
                # the grader scores FLAT against the same threshold.
                band = (FLAT_THRESHOLD_7D_BY_MARKET.get(market, FLAT_THRESHOLD_7D)
                        if days_ahead >= 7 else FLAT_THRESHOLD_3D)

                for ticker, ticker_df in ticker_latest.items():
                    # Every ticker still gets a daily row; the regime is recorded
                    # as metadata but no longer decides actionability (see below).
                    regime = classify_market_regime(ticker_df)

                    try:
                        # Phase 3+4C+6: unpack 5 values; pass dynamic weights + calibrator
                        (direction, predicted_change_pct, confidence,
                         predicted_direction, price_suspect) = predict_for_ticker_v4(
                            ticker_df, lgb_model, lr_model, scaler, wf_accuracy, days_ahead,
                            lgb_weight=lgb_weight, lr_weight=lr_weight, calibrator=calibrator
                        )

                        if direction is None:
                            total_no_direction += 1
                            continue

                        # Active learning: adjust confidence.
                        # Phase 6: disabled by default (USE_ACTIVE_LEARNING=False).
                        # Its hardcoded 1.15/1.05/0.80 multipliers destroy the
                        # isotonic calibration this pipeline now depends on.
                        if USE_ACTIVE_LEARNING:
                            perf_hist = all_performance_history.get(ticker, {}).get(days_ahead, {})
                            if perf_hist:
                                confidence = adjust_confidence_with_history(
                                    confidence, 'Ensemble', perf_hist
                                )

                        # Phase 6: actionability is now gated on calibrated
                        # confidence, not on classify_market_regime(). The regime
                        # gate was measured to have no discriminating power:
                        # NASDAQ actionable 48.8% vs suppressed 49.0%, NSE 48.8%
                        # vs 48.1% -- it suppressed ~60% of NSE rows for nothing.
                        # FLAT is kept out of the signal feed because "expect no
                        # move" is not a buy/sell instruction -- NOT because it
                        # is weak. Post-target-fix it is in fact the model's
                        # strongest class (+16.3pp lift overall, +51.1pp in the
                        # top confidence quartile, 88.5% accurate there). If a
                        # volatility or options strategy is ever added, read
                        # high-confidence FLAT rows from is_actionable=0 /
                        # suppression_reason='FLAT' rather than discarding them.
                        # PRICE_ARTIFACT is checked FIRST: a corrupt price series
                        # invalidates the features the direction call is built
                        # from, so a confident-looking prediction on such a
                        # ticker is the most dangerous kind. Previously these
                        # leaked through as actionable (58 rows since Aug 1,
                        # including AMIX +518% and BANL +361% surfacing as
                        # legitimate picks).
                        # IMMATERIAL: the instrument's own expected move is
                        # smaller than what this market treats as "no move".
                        # `band` is the calibrated FLAT threshold — 0.5x the
                        # median absolute n-day move — so it is already this
                        # market's definition of materiality. A directional call
                        # below it is noise dressed as a signal: USDHKD is
                        # pegged and predicted -0.051% on Sep 2, sixteen times
                        # under the 0.8% Forex band, yet shipped as actionable.
                        immaterial = abs(predicted_change_pct) < band * 100

                        if price_suspect:
                            suppressed, reason = True, 'PRICE_ARTIFACT'
                        elif predicted_direction == 'FLAT':
                            suppressed, reason = True, 'FLAT'
                        elif immaterial:
                            suppressed, reason = True, 'IMMATERIAL'
                        elif confidence < ACTIONABLE_CONFIDENCE_MIN:
                            suppressed, reason = True, 'LOW_CONFIDENCE'
                        else:
                            suppressed, reason = False, None

                        # Regime rides along as an audit trail so B3 can measure
                        # whether it ever had signal -- it no longer gates.
                        if suppressed and regime in ('SIDEWAYS', 'INSUFFICIENT'):
                            reason = f"{reason}/{regime}"

                        current_price = float(ticker_df['close_price'].iloc[-1])
                        company_name = ticker_company.get(ticker, ticker)

                        inserted = store_prediction(
                            cursor, market, ticker, company_name, days_ahead, 'Ensemble',
                            current_price, predicted_change_pct / 100.0, confidence,
                            existing_predictions=existing_predictions,
                            predicted_direction=predicted_direction,   # Phase 4C
                            is_actionable=0 if suppressed else 1,
                            suppression_reason=reason,
                            flat_band_pct=band
                        )
                        if inserted:
                            total_predictions += 1
                            market_predictions += 1
                            stored += 1
                            if suppressed:
                                total_suppressed += 1
                                market_suppressed += 1
                        else:
                            total_skipped_dup += 1

                    except Exception as e:
                        errors += 1
                        log_message(f"      Error predicting {ticker}: {str(e)}", "ERROR")
            return stored

        # Phase 5: tickers from any sector too small to train on their own are
        # accumulated and trained together as one fallback pool, so no ticker is
        # silently dropped (replaces the old per-sector `continue` skip).
        fallback_tickers = []

        for sector_name, sector_tickers in sector_groups.items():
            log_message(f"  Sector: {sector_name} ({len(sector_tickers)} tickers)")

            # FIX 1: Pool only sector tickers (with sentiment)
            pool_start = datetime.now()
            sector_df, ticker_latest = pool_sector_data(
                sector_tickers, all_stock_data, rsi_by_ticker, index_returns,
                sector_sentiment_df=all_sentiment.get(sector_name)
            )
            pool_elapsed = (datetime.now() - pool_start).total_seconds()
            log_message(f"    Pooled {len(sector_df):,} rows from {len(ticker_latest)} tickers in {pool_elapsed:.1f}s")

            if len(sector_df) < MIN_SECTOR_SAMPLES:
                log_message(f"    {sector_name} below {MIN_SECTOR_SAMPLES} samples "
                            f"({len(sector_df)}) — deferring {len(sector_tickers)} tickers to fallback pool")
                fallback_tickers.extend(sector_tickers)
                continue

            train_predict_pool(sector_name, sector_df, ticker_latest)

        # Phase 5: train the combined fallback pool once (mixed sectors, no sector
        # sentiment). Only runs if at least one sector was too thin to train alone.
        if fallback_tickers:
            log_message(f"  Fallback pool: {len(fallback_tickers)} tickers from under-sized sectors")
            fb_df, fb_latest = pool_sector_data(
                fallback_tickers, all_stock_data, rsi_by_ticker, index_returns,
                sector_sentiment_df=None
            )
            if len(fb_df) >= MIN_SECTOR_SAMPLES:
                train_predict_pool('FALLBACK_POOL', fb_df, fb_latest)
            else:
                log_message(f"    Fallback pool still below {MIN_SECTOR_SAMPLES} "
                            f"({len(fb_df)}) — skipping", "WARNING")

        # Free memory
        del all_stock_data

        conn.commit()
        market_elapsed = (datetime.now() - market_start).total_seconds()
        log_message(f"  {market} complete: {market_predictions} predictions "
                    f"({market_predictions - market_suppressed} actionable + "
                    f"{market_suppressed} suppressed) in {market_elapsed:.1f}s")

    # Phase 5 diagnostic: report NASDAQ agreement with the sibling ML model
    if (not markets_to_process) or ('NASDAQ 100' in markets_to_process):
        report_sibling_agreement(conn)

    conn.close()
    
    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    log_message("")
    log_message("=" * 80)
    log_message(f"Daily Direction Prediction Job (v4) Completed!")
    log_message(f"  Total Predictions Generated: {total_predictions}")
    log_message(f"    Actionable:                {total_predictions - total_suppressed}")
    log_message(f"    Suppressed (FLAT/low-conf):{total_suppressed}")
    log_message(f"  Skipped (no direction):      {total_no_direction}")
    log_message(f"  Duplicates Skipped:          {total_skipped_dup}")
    log_message(f"  Stocks Skipped (no data):    {total_skipped_data}")
    log_message(f"  Stocks Skipped (unchanged):  {total_skipped_unchanged}")
    log_message(f"  Errors:                      {errors}")
    log_message(f"  Model: LightGBM + LogReg (per-sector classification + isotonic confidence)")
    log_message(f"  Features: {len(SELECTED_FEATURES_V4)}")
    log_message(f"  Outcome backfill:            {'OK' if backfill_ok else 'FAILED'}")
    log_message(f"  Total Time:                  {elapsed:.1f}s ({elapsed/60:.1f} min)")

    # A run that errored on every ticker previously still printed "Completed!"
    # and exited 0. On 2026-09-03 the Forex job failed all 14 tickers on a
    # missing column and Task Scheduler recorded LastResult=0 — the market sat
    # a day stale with nothing flagging it. Per-ticker errors are tolerated
    # (one bad ticker should not sink the run); a wholesale failure is not.
    attempted = total_predictions + errors
    run_ok = True
    if errors > 0 and total_predictions == 0:
        log_message(f"RUN FAILED: {errors} errors, 0 predictions stored", "ERROR")
        run_ok = False
    elif attempted > 0 and errors > attempted * MAX_ERROR_RATE:
        log_message(f"RUN DEGRADED: {errors}/{attempted} tickers errored "
                    f"(>{MAX_ERROR_RATE:.0%} threshold)", "ERROR")
        run_ok = False

    log_message(f"  Run status:                  {'OK' if run_ok else 'FAILED'}")
    log_message("=" * 80)

    return backfill_ok and run_ok

def load_index_returns(conn, market):
    """
    Load market index daily returns from SQL Server for the rel_strength feature.

    Requires a table: market_index_data (index_name, trading_date, close_price)
    Suggested index symbols:
        NSE 500    → 'NIFTY50'
        NASDAQ 100 → 'NDX'
        Forex      → 'DXY'

    Returns a pd.Series indexed by trading_date, or None if table/data not available.
    rel_strength defaults to 0.0 (neutral) when None is returned — safe fallback.
    """
    index_map = {
        'NSE 500':    'NIFTY50',
        'NASDAQ 100': 'NDX',
        'Forex':      'DXY',
    }

    index_name = index_map.get(market)
    if not index_name:
        return None

    try:
        query = """
            SELECT trading_date, close_price
            FROM market_index_data
            WHERE index_name = ?
              AND trading_date >= DATEADD(day, -400, GETDATE())
            ORDER BY trading_date ASC
        """
        df = pd.read_sql(query, conn, params=[index_name])
        if df.empty:
            return None
        df['trading_date'] = pd.to_datetime(df['trading_date'])
        df = df.set_index('trading_date')
        return df['close_price'].pct_change().dropna()
    except Exception:
        # Table doesn't exist yet — safe fallback, rel_strength defaults to 0
        return None


def run_correlation_check(all_stock_data, rsi_by_ticker=None, sample_n=5):
    """
    Diagnostic utility: verify the v4 features are non-correlated.
    Run once manually — NOT part of the daily pipeline.

    Usage:
        conn = get_db_connection()
        all_stock_data = bulk_load_stock_data(conn, 'NASDAQ 100', tickers[:50])
        rsi_by_ticker  = bulk_load_rsi_data(conn, 'NASDAQ 100', tickers[:50])
        run_correlation_check(all_stock_data, rsi_by_ticker)
    """
    frames = []
    for ticker, df_raw in list(all_stock_data.items())[:sample_n]:
        df = calculate_technical_indicators_v4(df_raw, rsi_by_ticker.get(ticker) if rsi_by_ticker else None)
        feature_cols = [f for f in SELECTED_FEATURES_V4 if f in df.columns]
        frames.append(df[feature_cols].tail(100))

    if not frames:
        print("No data for correlation check")
        return

    combined = pd.concat(frames, ignore_index=True)
    corr = combined.corr()

    print("\n=== Feature Correlation Matrix ===")
    print(corr.round(2).to_string())

    print("\n=== High Correlation Pairs (>0.60) ===")
    found = False
    for i in range(len(corr)):
        for j in range(i + 1, len(corr)):
            val = abs(corr.iloc[i, j])
            if val > 0.60:
                print(f"  {corr.columns[i]:25s} <-> {corr.columns[j]:25s}  {val:.2f}")
                found = True
    if not found:
        print("  None found -- features look good.")


def report_sibling_agreement(conn):
    """
    Phase 5 diagnostic (read-only): measure how often this repo's NASDAQ direction
    predictions agree with the sibling ml_trading_predictions model on the latest
    common trading date. This makes the "NASDAQ doesn't tally" symptom measurable
    and guards against regressions after the sector-map fix.

    Sibling 'predicted_signal' is Buy/Sell-flavored (no FLAT), so only our
    directional UP/DOWN rows are compared (FLAT/NULL excluded). Logs the agreement
    rate; never writes anything.
    """
    try:
        query = """
            WITH ours AS (
                SELECT ticker, predicted_direction,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY prediction_date DESC) rn
                FROM ai_prediction_history
                WHERE market = 'NASDAQ 100' AND predicted_direction IN ('UP','DOWN')
            ),
            sib AS (
                SELECT ticker, predicted_signal,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) rn
                FROM ml_trading_predictions
            )
            SELECT o.predicted_direction, s.predicted_signal
            FROM ours o JOIN sib s ON o.ticker = s.ticker
            WHERE o.rn = 1 AND s.rn = 1
        """
        df = pd.read_sql(query, conn)
        if df.empty:
            log_message("  Sibling agreement: no overlapping NASDAQ tickers to compare")
            return

        def sib_dir(sig):
            s = (sig or '').lower()
            if 'buy' in s:
                return 'UP'
            if 'sell' in s:
                return 'DOWN'
            return None

        df['sib_dir'] = df['predicted_signal'].map(sib_dir)
        df = df.dropna(subset=['sib_dir'])
        if df.empty:
            log_message("  Sibling agreement: no directional sibling signals to compare")
            return

        agree = (df['predicted_direction'] == df['sib_dir']).mean() * 100
        log_message(f"  NASDAQ sibling agreement: {agree:.1f}% over {len(df)} overlapping tickers "
                    f"(vs ml_trading_predictions)")
    except Exception as e:
        log_message(f"  Sibling agreement check failed: {e}", "WARNING")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily AI Direction Prediction Job (v3 - Classification)")
    parser.add_argument(
        '--market', type=str, nargs='+',
        help='Market(s) to process. E.g.: --market "NSE 500" or --market "NASDAQ 100". Default: all.',
        default=None
    )
    args = parser.parse_args()
    
    try:
        ok = run_daily_predictions(markets_filter=args.market)
        # Non-zero exit so Task Scheduler surfaces a failed run or a failed
        # outcome backfill. Both used to report LastResult=0 while doing
        # nothing — see the 2026-09-03 Forex run (14/14 tickers errored,
        # 0 predictions, exit 0, market a day stale with no alert).
        if ok is False:
            exit(2)
    except Exception as e:
        log_message(f"CRITICAL ERROR: {str(e)}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        exit(1)
