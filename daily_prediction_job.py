"""
Daily AI Direction Prediction Job (v3 — Classification)
========================================================
Runs daily to:
1. Update actual prices for past predictions (backtest)
2. Generate new direction predictions (UP/DOWN) per market
3. Store predictions in ai_prediction_history
4. Active learning adjusts confidence based on historical accuracy

v3 Changes (Classification Rewrite):
- Switched from REGRESSION to CLASSIFICATION (predict direction, not price)
- LightGBM Classifier + Logistic Regression ensemble (diverse model types)
- Reduced features from 48 to 15 (eliminated redundant/correlated indicators)
- Per-MARKET training (pools all tickers) instead of per-ticker (massively faster)
- Both 3-day and 7-day horizons retained
- Magnitude estimated from recent median absolute returns

Differentiation from sibling repos (sqlserver_copilot / sqlserver_copilot_nse):
- Those repos: 5-day horizon, GradientBoosting+RF+ExtraTrees+LogReg VotingClassifier
- This repo: 3-day + 7-day horizons, LightGBM + LogReg, 15 trimmed features

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
import lightgbm as lgb

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
PREDICTION_DAYS = [3, 7]  # Both horizons: 3-day and 7-day
MAX_STOCKS_PER_MARKET = None  # Set to None to process all tickers
MIN_DATA_POINTS = 200  # Minimum historical data per ticker
MIN_MARKET_SAMPLES = 5000  # Minimum pooled samples for per-market training

# Confidence bounds
CONFIDENCE_MIN = 30
CONFIDENCE_MAX = 80

# =====================================================
# ACTIVE LEARNING CONFIGURATION
# =====================================================
USE_ACTIVE_LEARNING = True  # Learn from past prediction accuracy
MIN_PREDICTIONS_FOR_LEARNING = 10  # Minimum predictions needed to assess model performance
MIN_DIRECTION_ACCURACY = 0.45  # Skip models with < 45% direction accuracy
HISTORICAL_LOOKBACK_DAYS = 90  # Look back 90 days for performance analysis

# =====================================================
# WATCHLIST CONFIGURATION
# =====================================================
USE_WATCHLIST = False  # Set to True to use watchlist, False for all tickers

# Columns to exclude from ML features (raw values that don't generalize)
EXCLUDE_FROM_FEATURES = ['trading_date', 'close_price', 'high_price', 'low_price', 'volume', 'target', 'ticker']

# 15 SELECTED FEATURES (trimmed from 48+ to eliminate redundancy)
# Dropped: sma_5/10/50, ema_5/20/50, log_returns, macd, macd_signal,
#          momentum_5, bb_width, hl_range_ma, price_position, regime_sma20_slope, regime_adx
SELECTED_FEATURES = [
    'returns',                  # Direct price momentum
    'rsi',                      # Proven mean-reversion signal
    'macd_histogram',           # Trend momentum change
    'bb_position',              # Mean reversion + volatility
    'volume_ratio',             # Confirms moves
    'momentum_10',              # Medium-term trend
    'volatility_20',            # Risk regime
    'regime_vol_ratio',         # Volatility regime shift
    'regime_trend_consistency', # Trend strength
    'sma_20_ratio',             # Price vs medium-term trend
    'ema_10_ratio',             # Short-term trend
    'hl_range',                 # Intraday volatility
    'rsi_change',               # Momentum acceleration
    'regime_mean_reversion',    # Distance from equilibrium
    'trend_strength',           # Overall trend magnitude
]

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


def calculate_technical_indicators(df, rsi_df=None):
    """Calculate the 15 selected technical indicators for ML features.
    
    Trimmed from 48+ features to eliminate redundant/correlated indicators.
    All features are normalized (ratios, percentages) for cross-stock comparability.
    
    RSI is loaded from pre-computed Wilder's smoothing tables (matching TradingView).
    If rsi_df is None, falls back to inline SMA calculation.
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
    
    # 3. rsi_change — RSI momentum
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
    df['volume_ratio'] = df['volume'] / volume_sma_20.replace(0, 1)
    df['volume_ratio'] = df['volume_ratio'].fillna(1.0).clip(upper=10.0)
    
    # 7. momentum_10 — 10-period price momentum
    df['momentum_10'] = df['close_price'] / df['close_price'].shift(10) - 1
    
    # 8. volatility_20 — 20-period rolling std of returns
    df['volatility_20'] = df['returns'].rolling(window=20).std()
    
    # 9. sma_20_ratio — price vs 20-period SMA
    sma20 = df['close_price'].rolling(window=20).mean()
    df['sma_20_ratio'] = df['close_price'] / sma20
    
    # 10. ema_10_ratio — price vs 10-period EMA
    ema10 = df['close_price'].ewm(span=10, adjust=False).mean()
    df['ema_10_ratio'] = df['close_price'] / ema10
    
    # 11. hl_range — intraday volatility (normalized)
    df['hl_range'] = (df['high_price'] - df['low_price']) / df['close_price']
    
    # 12. trend_strength — ADX-like indicator (vectorized)
    close_series = df['close_price']
    rolling_std = close_series.rolling(14).std()
    abs_change = (close_series - close_series.shift(13)).abs()
    df['trend_strength'] = np.where(rolling_std > 0, abs_change / rolling_std, 0)
    
    # 13. regime_vol_ratio — short-term vol vs long-term vol
    vol_short = df['close_price'].pct_change().rolling(10).std()
    vol_long = df['close_price'].pct_change().rolling(60).std()
    df['regime_vol_ratio'] = np.where(vol_long > 0, vol_short / vol_long, 1.0)
    
    # 14. regime_mean_reversion — distance from 50-SMA in ATR units
    sma50 = df['close_price'].rolling(window=50).mean()
    atr_14 = df['hl_range'].rolling(window=14).mean() * df['close_price']
    df['regime_mean_reversion'] = np.where(atr_14 > 0, (df['close_price'] - sma50) / atr_14, 0)
    
    # 15. regime_trend_consistency — % of last 20 days moving in overall direction
    overall_dir = np.sign(df['close_price'].diff(20))
    daily_dirs = np.sign(df['close_price'].diff(1))
    consistent = (daily_dirs == overall_dir).astype(float)
    df['regime_trend_consistency'] = consistent.rolling(20).mean()
    
    return df.dropna()

def train_market_model(market_df, days_ahead):
    """
    Train a CLASSIFICATION model on the entire market's pooled data.
    
    Uses LightGBM + Logistic Regression ensemble.
    Target: 1 = price goes UP in N days, 0 = price goes DOWN.
    
    Returns: (lgb_model, lr_model, scaler, wf_accuracy) or (None, None, None, None)
    """
    df = market_df.copy()
    
    # Classification target: 1 if price goes up in N days, 0 otherwise
    df['target'] = (df['close_price'].shift(-days_ahead) > df['close_price']).astype(int)
    df = df.dropna(subset=['target'])
    
    if len(df) < MIN_MARKET_SAMPLES:
        log_message(f"    Insufficient pooled data ({len(df)} < {MIN_MARKET_SAMPLES}), skipping", "WARNING")
        return None, None, None, None
    
    # Use only the selected 15 features
    feature_cols = [f for f in SELECTED_FEATURES if f in df.columns]
    if len(feature_cols) < 10:
        log_message(f"    Only {len(feature_cols)} features available, skipping", "WARNING")
        return None, None, None, None
    
    X_all = df[feature_cols].values
    y_all = df['target'].values
    
    # Time-weighted sample weights (exponential recency)
    n_samples = len(y_all)
    time_positions = np.arange(n_samples) / n_samples
    decay_rate = 1.2
    time_weights = np.exp(decay_rate * (time_positions - 1))
    time_weights = time_weights / time_weights.mean()
    
    # Walk-forward validation (2 expanding windows) for honest OOS accuracy
    n_windows = 2
    purge_gap = max(days_ahead + 3, 8)
    min_train = int(n_samples * 0.5)
    window_size = max(100, (n_samples - min_train) // (n_windows + 1))
    
    wf_direction_scores = []
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
        
        try:
            # LightGBM in walk-forward
            lgb_wf = lgb.LGBMClassifier(
                n_estimators=200, learning_rate=0.05, max_depth=6,
                num_leaves=31, min_child_samples=20, subsample=0.8,
                colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1,
                random_state=42, verbosity=-1, n_jobs=-1
            )
            lgb_wf.fit(wf_X_train_s, wf_y_train, sample_weight=wf_weights)
            lgb_acc = np.mean(lgb_wf.predict(wf_X_test_s) == wf_y_test)
            wf_direction_scores.append(lgb_acc)
        except Exception:
            pass
        
        try:
            # Logistic Regression in walk-forward
            lr_wf = LogisticRegression(C=0.1, max_iter=500, class_weight='balanced', random_state=42)
            lr_wf.fit(wf_X_train_s, wf_y_train, sample_weight=wf_weights)
            lr_acc = np.mean(lr_wf.predict(wf_X_test_s) == wf_y_test)
            wf_direction_scores.append(lr_acc)
        except Exception:
            pass
    
    wf_accuracy = np.mean(wf_direction_scores) * 100 if wf_direction_scores else 50.0
    
    # Train final models on 80% of data (time-ordered)
    train_end_final = int(n_samples * 0.8)
    X_train = X_all[:train_end_final]
    y_train = y_all[:train_end_final]
    weights_train = time_weights[:train_end_final]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    
    # LightGBM Classifier
    lgb_model = lgb.LGBMClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=6,
        num_leaves=31, min_child_samples=20, subsample=0.8,
        colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1,
        random_state=42, verbosity=-1, n_jobs=-1
    )
    lgb_model.fit(X_train_scaled, y_train, sample_weight=weights_train)
    
    # Logistic Regression (diverse second model)
    lr_model = LogisticRegression(C=0.1, max_iter=500, class_weight='balanced', random_state=42)
    lr_model.fit(X_train_scaled, y_train, sample_weight=weights_train)
    
    # Test set accuracy for confidence calibration
    X_test = X_all[train_end_final:]
    y_test = y_all[train_end_final:]
    X_test_scaled = scaler.transform(X_test)
    
    lgb_test_acc = np.mean(lgb_model.predict(X_test_scaled) == y_test) * 100
    lr_test_acc = np.mean(lr_model.predict(X_test_scaled) == y_test) * 100
    
    log_message(f"    {days_ahead}-day model trained on {len(X_train):,} samples | "
                f"WF acc: {wf_accuracy:.1f}% | Test acc: LGB={lgb_test_acc:.1f}%, LR={lr_test_acc:.1f}%")
    
    return lgb_model, lr_model, scaler, wf_accuracy


def predict_for_ticker(ticker_df, lgb_model, lr_model, scaler, wf_accuracy, days_ahead):
    """
    Generate direction prediction for a single ticker using trained market model.
    
    Returns: (direction, predicted_change_pct, confidence) or (None, None, None)
    """
    feature_cols = [f for f in SELECTED_FEATURES if f in ticker_df.columns]
    if len(feature_cols) < 10:
        return None, None, None
    
    latest = ticker_df[feature_cols].iloc[-1:].values
    latest_scaled = scaler.transform(latest)
    
    # Ensemble: average probabilities from both models
    lgb_proba = lgb_model.predict_proba(latest_scaled)[0]  # [P(down), P(up)]
    lr_proba = lr_model.predict_proba(latest_scaled)[0]
    
    # Average probabilities (LightGBM gets 60% weight, LogReg 40%)
    avg_proba = 0.6 * lgb_proba + 0.4 * lr_proba
    direction = 1 if avg_proba[1] > 0.5 else 0  # 1=UP, 0=DOWN
    direction_prob = avg_proba[1] if direction == 1 else avg_proba[0]
    
    # Estimate magnitude from recent median absolute returns
    recent_returns = ticker_df['close_price'].pct_change(days_ahead).dropna().tail(60)
    if len(recent_returns) > 10:
        median_abs_return = recent_returns.abs().median()
    else:
        median_abs_return = 0.02  # Default 2%
    
    # predicted_change_pct: direction * estimated magnitude
    sign = 1.0 if direction == 1 else -1.0
    predicted_change_pct = sign * median_abs_return * 100  # As percentage
    
    # Confidence: blend of walk-forward accuracy + model probability + model agreement
    lgb_dir = 1 if lgb_proba[1] > 0.5 else 0
    lr_dir = 1 if lr_proba[1] > 0.5 else 0
    agreement = 100.0 if lgb_dir == lr_dir else 50.0
    
    confidence = (
        0.50 * wf_accuracy +           # Walk-forward accuracy (honest OOS)
        0.30 * (direction_prob * 100) + # Model probability
        0.20 * agreement                # Model agreement
    )
    confidence = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, confidence))
    
    return direction, predicted_change_pct, confidence


def pool_market_data(all_stock_data, rsi_by_ticker=None):
    """
    Pool all tickers' data into a single market-level DataFrame for per-market training.
    Each ticker's features are computed independently, then concatenated.
    """
    if rsi_by_ticker is None:
        rsi_by_ticker = {}
    all_frames = []
    ticker_latest = {}  # {ticker: DataFrame} — last row per ticker for prediction
    
    for ticker, df_raw in all_stock_data.items():
        df = calculate_technical_indicators(df_raw, rsi_df=rsi_by_ticker.get(ticker))
        if len(df) < MIN_DATA_POINTS:
            continue
        
        # Save only the latest rows needed for prediction (not full copy)
        ticker_latest[ticker] = df
        
        # Add ticker column (excluded from features but used for grouping)
        df['ticker'] = ticker
        all_frames.append(df)
    
    if not all_frames:
        return pd.DataFrame(), ticker_latest
    
    market_df = pd.concat(all_frames, ignore_index=True)
    # Sort by trading_date for proper time-series walk-forward
    market_df = market_df.sort_values('trading_date').reset_index(drop=True)
    
    return market_df, ticker_latest

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
                    current_price, predicted_change, confidence, existing_predictions=None):
    """
    Store prediction in database. 
    Skips if a prediction already exists for this market/ticker/date/days_ahead/model.
    Uses pre-loaded existing_predictions set for O(1) duplicate check instead of per-row SQL.
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
     current_price, predicted_price, predicted_change_pct, model_confidence)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    cursor.execute(query, (
        market, ticker, company_name, str(prediction_date), str(target_date), days_ahead, model_name,
        float(current_price), float(predicted_price), float(predicted_change * 100), float(confidence)
    ))
    
    return True  # Inserted

def update_actual_prices(conn):
    """
    Update actual prices for past predictions where target_date has arrived.
    Uses batch SQL for performance instead of row-by-row.
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
        return
    
    total_updated = 0
    
    # Include Forex for updating historical predictions (even though we no longer generate new ones)
    all_markets_for_update = dict(MARKETS)
    all_markets_for_update['Forex'] = {'table': 'forex_hist_data', 'symbol_col': 'symbol', 'company_col': 'symbol'}
    
    # Batch update for each market (uses JOIN for performance)
    for market, config in all_markets_for_update.items():
        table = config['table']
        symbol_col = config['symbol_col']
        
        # Update actual prices using batch SQL with JOIN
        # Uses trading_date <= target_date to find the closest available price
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
            p.direction_correct = CASE 
                WHEN p.predicted_change_pct > 0.01 AND CAST(h.close_price AS FLOAT) > CAST(p.current_price AS FLOAT) THEN 1
                WHEN p.predicted_change_pct < -0.01 AND CAST(h.close_price AS FLOAT) < CAST(p.current_price AS FLOAT) THEN 1
                WHEN ABS(p.predicted_change_pct) <= 0.01 AND CAST(p.current_price AS FLOAT) != 0 AND ABS(CAST(h.close_price AS FLOAT) - CAST(p.current_price AS FLOAT)) / CAST(p.current_price AS FLOAT) < 0.005 THEN 1
                ELSE 0
            END,
            p.updated_at = GETDATE()
        FROM ai_prediction_history p
        CROSS APPLY (
            SELECT TOP 1 close_price
            FROM {table}
            WHERE {symbol_col} = p.ticker 
              AND trading_date <= p.target_date
              AND close_price IS NOT NULL AND CAST(close_price AS FLOAT) > 0
            ORDER BY trading_date DESC
        ) h
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
            log_message(f"  {market}: Error updating actual prices: {str(e)}", "ERROR")
    
    conn.commit()
    log_message(f"Total updated: {total_updated} predictions with actual prices")

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
    log_message("Starting Daily AI Direction Prediction Job (v3 - Classification)")
    log_message(f"Markets: {', '.join(markets_to_process.keys())}")
    log_message(f"Models: LightGBM + Logistic Regression (per-market training)")
    log_message(f"Features: {len(SELECTED_FEATURES)} selected indicators")
    log_message(f"Horizons: {PREDICTION_DAYS}")
    if USE_ACTIVE_LEARNING:
        log_message("ACTIVE LEARNING ENABLED")
    log_message("=" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Step 1: Update actual prices for past predictions
    log_message("Step 1: Updating actual prices for past predictions...")
    update_actual_prices(conn)
    
    total_predictions = 0
    total_skipped_dup = 0
    total_skipped_data = 0
    total_skipped_unchanged = 0
    errors = 0
    
    # Step 2: Per-market training and prediction
    for market in markets_to_process.keys():
        log_message(f"\nStep 2: Processing {market}...")
        market_start = datetime.now()
        
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
        
        # Bulk preload active learning history
        all_performance_history = {}
        if USE_ACTIVE_LEARNING:
            all_performance_history = bulk_load_performance_history(conn, market)
            log_message(f"  Loaded active learning history for {len(all_performance_history)} tickers")
        
        # Bulk load pre-computed Wilder's RSI
        rsi_by_ticker = bulk_load_rsi_data(conn, market, ticker_list)
        log_message(f"  Loaded Wilder's RSI for {len(rsi_by_ticker)} tickers")
        
        # Pool all tickers into market-level DataFrame
        log_message(f"  Computing features and pooling market data...")
        pool_start = datetime.now()
        market_df, ticker_latest = pool_market_data(all_stock_data, rsi_by_ticker=rsi_by_ticker)
        pool_elapsed = (datetime.now() - pool_start).total_seconds()
        log_message(f"  Pooled {len(market_df):,} rows from {len(ticker_latest)} tickers in {pool_elapsed:.1f}s")
        
        if len(market_df) < MIN_MARKET_SAMPLES:
            log_message(f"  {market} skipped: insufficient pooled data ({len(market_df)} < {MIN_MARKET_SAMPLES})")
            continue
        
        # Train and predict for each horizon
        market_predictions = 0
        
        # Preload today's existing predictions for this market (1 query instead of ~4500)
        existing_predictions = load_existing_predictions(cursor, market)
        if existing_predictions:
            log_message(f"  Found {len(existing_predictions)} existing predictions for today (will skip duplicates)")
        
        for days_ahead in PREDICTION_DAYS:
            log_message(f"  Training {days_ahead}-day model for {market}...")
            train_start = datetime.now()
            
            lgb_model, lr_model, scaler, wf_accuracy = train_market_model(market_df, days_ahead)
            train_elapsed = (datetime.now() - train_start).total_seconds()
            
            if lgb_model is None:
                log_message(f"  {days_ahead}-day model training failed, skipping", "WARNING")
                continue
            
            log_message(f"  Model trained in {train_elapsed:.1f}s, predicting for {len(ticker_latest)} tickers...")
            
            # Predict for each ticker
            for ticker, ticker_df in ticker_latest.items():
                try:
                    direction, predicted_change_pct, confidence = predict_for_ticker(
                        ticker_df, lgb_model, lr_model, scaler, wf_accuracy, days_ahead
                    )
                    
                    if direction is None:
                        continue
                    
                    # Active learning: adjust confidence
                    if USE_ACTIVE_LEARNING:
                        perf_hist = all_performance_history.get(ticker, {}).get(days_ahead, {})
                        if perf_hist:
                            confidence = adjust_confidence_with_history(
                                confidence, 'Ensemble', perf_hist
                            )
                    
                    current_price = float(ticker_df['close_price'].iloc[-1])
                    company_name = ticker_company.get(ticker, ticker)
                    
                    inserted = store_prediction(
                        cursor, market, ticker, company_name, days_ahead, 'Ensemble',
                        current_price, predicted_change_pct / 100.0, confidence,
                        existing_predictions=existing_predictions
                    )
                    if inserted:
                        total_predictions += 1
                        market_predictions += 1
                    else:
                        total_skipped_dup += 1
                        
                except Exception as e:
                    errors += 1
                    log_message(f"    Error predicting {ticker}: {str(e)}", "ERROR")
        
        # Free memory
        del all_stock_data, market_df, ticker_latest
        
        conn.commit()
        market_elapsed = (datetime.now() - market_start).total_seconds()
        log_message(f"  {market} complete: {market_predictions} predictions in {market_elapsed:.1f}s")
    
    conn.close()
    
    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    log_message("")
    log_message("=" * 80)
    log_message(f"Daily Direction Prediction Job (v3) Completed!")
    log_message(f"  Total Predictions Generated: {total_predictions}")
    log_message(f"  Duplicates Skipped:          {total_skipped_dup}")
    log_message(f"  Stocks Skipped (no data):    {total_skipped_data}")
    log_message(f"  Stocks Skipped (unchanged):  {total_skipped_unchanged}")
    log_message(f"  Errors:                      {errors}")
    log_message(f"  Model: LightGBM + LogReg (per-market classification)")
    log_message(f"  Features: {len(SELECTED_FEATURES)}")
    log_message(f"  Total Time:                  {elapsed:.1f}s ({elapsed/60:.1f} min)")
    log_message("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily AI Direction Prediction Job (v3 - Classification)")
    parser.add_argument(
        '--market', type=str, nargs='+',
        help='Market(s) to process. E.g.: --market "NSE 500" or --market "NASDAQ 100". Default: all.',
        default=None
    )
    args = parser.parse_args()
    
    try:
        run_daily_predictions(markets_filter=args.market)
    except Exception as e:
        log_message(f"CRITICAL ERROR: {str(e)}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        exit(1)
