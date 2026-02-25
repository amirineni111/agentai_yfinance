"""
Daily AI Price Prediction Job (Strategy 2)
============================================
Runs daily to:
1. Update actual prices for past predictions (backtest)
2. Generate new predictions for all markets using ensemble averaging
3. Store predictions in ai_prediction_history
4. Active learning adjusts model selection & confidence

Improvements applied (S2-1 through S2-8):
- Dropped 1-day predictions (pure noise at 37-41% accuracy)
- Fixed confidence calibration (removed inflating 1.3x multiplier)
- Walk-forward validation (expanding window, not single 80/20 split)
- Time-weighted training (recent data weighted 3.3x more)
- Market regime detection features (ADX, vol ratio, mean reversion, etc.)
- 7-day horizon as primary (only horizon above 50% accuracy)
- Ensemble averaging across all models (not individual model predictions)
- Minimum 200 samples required (was 50)

Schedule this to run daily via Windows Task Scheduler.
"""

import pandas as pd
import numpy as np
import pyodbc
from datetime import datetime, timedelta
import traceback
import sys
import warnings
warnings.filterwarnings('ignore')

# Force unbuffered output so logs appear immediately in Task Scheduler
sys.stdout.reconfigure(line_buffering=True)

# Import ML libraries
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

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
    'NSE 500': {'table': 'nse_500_hist_data', 'symbol_col': 'ticker', 'company_col': 'company'},
    'NASDAQ 100': {'table': 'nasdaq_100_hist_data', 'symbol_col': 'ticker', 'company_col': 'company'},
    # Forex removed: regression-based price prediction doesn't work for FX pairs (35-41% accuracy).
    # Forex uses Strategy 1 ML classification only (sqlserver_copilot_forex pipeline).
}

# S2-1: Dropped 1-day predictions (37% accuracy = worse than coin flip)
# S2-6: 7-day is primary horizon (only one historically above 50%)
PREDICTION_DAYS = [3, 7]  # 3-day secondary, 7-day primary
MAX_STOCKS_PER_MARKET = None  # Set to None to process all tickers
# S2-8: Raised minimum from 100 to 200 for more reliable training
MIN_DATA_POINTS = 200  # Minimum historical data required

# S2-2: Removed CONFIDENCE_MULTIPLIER (was 1.3x, inflated confidence way above actual accuracy)
# Confidence now comes directly from walk-forward validation metrics

# Unified confidence bounds
CONFIDENCE_MIN = 30
CONFIDENCE_MAX = 80  # Lowered from 85 to be more honest

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

# Columns to exclude from ML features (raw values that don't generalize across stocks)
EXCLUDE_FROM_FEATURES = ['trading_date', 'close_price', 'high_price', 'low_price', 'volume', 'target']

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

def get_performance_from_cache(all_history, ticker, days_ahead):
    """Look up performance from the bulk-loaded cache. Returns dict or empty dict."""
    return all_history.get(ticker, {}).get(days_ahead, {})

def select_best_models(performance_history, available_models):
    """
    Select which models to use based on historical performance.
    
    ACTIVE LEARNING: Skip poorly performing models, prioritize successful ones.
    """
    if not performance_history:
        # No history - use all models
        return available_models
    
    selected_models = []
    
    for model in available_models:
        if model in performance_history:
            perf = performance_history[model]
            direction_acc = perf['direction_accuracy']
            
            # Skip models with poor direction accuracy
            if direction_acc < MIN_DIRECTION_ACCURACY:
                log_message(f"    Skipping {model} (direction accuracy: {direction_acc:.1%} < {MIN_DIRECTION_ACCURACY:.1%})", "INFO")
                continue
        
        selected_models.append(model)
    
    # If all models were filtered out, use the best one from history
    if not selected_models and performance_history:
        best_model = max(performance_history.items(), 
                        key=lambda x: x[1]['direction_accuracy'])
        selected_models = [best_model[0]]
        log_message(f"    All models below threshold, using best: {best_model[0]} ({best_model[1]['direction_accuracy']:.1%})", "INFO")
    
    # If still no models, use all available
    if not selected_models:
        selected_models = available_models
    
    return selected_models

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
    BULK load historical data for ALL tickers in one market with ONE query.
    Returns dict: {ticker: DataFrame}.
    
    This replaces 256+ individual queries with 1 query.
    """
    config = MARKETS[market]
    
    # Build parameterized IN clause
    placeholders = ','.join(['?' for _ in tickers])
    query = f"""
    SELECT {config['symbol_col']} as ticker, trading_date, close_price, volume, high_price, low_price
    FROM {config['table']}
    WHERE {config['symbol_col']} IN ({placeholders})
      AND trading_date >= DATEADD(day, -1100, GETDATE())
    ORDER BY {config['symbol_col']}, trading_date ASC
    """
    
    log_message(f"  Bulk loading data for {len(tickers)} tickers...")
    load_start = datetime.now()
    df_all = pd.read_sql(query, conn, params=tickers)
    load_elapsed = (datetime.now() - load_start).total_seconds()
    log_message(f"  Loaded {len(df_all):,} rows in {load_elapsed:.1f}s")
    
    # Split into per-ticker DataFrames
    stock_data = {}
    for ticker in tickers:
        df = df_all[df_all['ticker'] == ticker].copy()
        df = df.drop(columns=['ticker'])
        df = df.sort_values('trading_date').reset_index(drop=True)
        
        if len(df) >= MIN_DATA_POINTS:
            # Keep only the most recent 1000 rows (same as original)
            if len(df) > 1000:
                df = df.tail(1000).reset_index(drop=True)
            stock_data[ticker] = df
    
    return stock_data

def calculate_technical_indicators(df):
    """Calculate technical indicators for ML features"""
    df = df.copy()
    
    # Convert price columns to numeric (they're stored as strings in database)
    df['close_price'] = pd.to_numeric(df['close_price'], errors='coerce')
    df['high_price'] = pd.to_numeric(df['high_price'], errors='coerce')
    df['low_price'] = pd.to_numeric(df['low_price'], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    
    # Drop any rows with NaN values after conversion
    df = df.dropna()
    
    # Price-based features
    df['returns'] = df['close_price'].pct_change()
    df['log_returns'] = np.log(df['close_price'] / df['close_price'].shift(1))
    
    # Moving averages (as ratios to close price for cross-stock comparability)
    for period in [5, 10, 20, 50]:
        df[f'sma_{period}'] = df['close_price'].rolling(window=period).mean()
        df[f'sma_{period}_ratio'] = df['close_price'] / df[f'sma_{period}']
        df[f'ema_{period}'] = df['close_price'].ewm(span=period, adjust=False).mean()
        df[f'ema_{period}_ratio'] = df['close_price'] / df[f'ema_{period}']
        # Drop raw SMA/EMA (keep only ratios which are scale-independent)
        df.drop(columns=[f'sma_{period}', f'ema_{period}'], inplace=True)
    
    # Volatility
    df['volatility_20'] = df['returns'].rolling(window=20).std()
    
    # RSI
    delta = df['close_price'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD (as percentage of price for cross-stock comparability)
    ema12 = df['close_price'].ewm(span=12, adjust=False).mean()
    ema26 = df['close_price'].ewm(span=26, adjust=False).mean()
    df['macd'] = (ema12 - ema26) / df['close_price'] * 100
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # Bollinger Bands (as positions, not absolute values)
    bb_middle = df['close_price'].rolling(window=20).mean()
    bb_std = df['close_price'].rolling(window=20).std()
    bb_upper = bb_middle + (bb_std * 2)
    bb_lower = bb_middle - (bb_std * 2)
    
    # Volume features (handle forex with zero volume)
    volume_sma_20 = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / volume_sma_20.replace(0, 1)
    df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
    # Cap extreme volume ratios
    df['volume_ratio'] = df['volume_ratio'].clip(upper=10.0)
    
    # Price momentum
    df['momentum_5'] = df['close_price'] / df['close_price'].shift(5) - 1
    df['momentum_10'] = df['close_price'] / df['close_price'].shift(10) - 1
    
    # High-Low Range (volatility indicator)
    df['hl_range'] = (df['high_price'] - df['low_price']) / df['close_price']
    df['hl_range_ma'] = df['hl_range'].rolling(window=10).mean()
    
    # Price position within range
    df['price_position'] = (df['close_price'] - df['low_price']) / (df['high_price'] - df['low_price'] + 1e-8)
    
    # Bollinger Band position (0 = at lower band, 1 = at upper band)
    df['bb_position'] = (df['close_price'] - bb_lower) / (bb_upper - bb_lower + 1e-8)
    
    # BB width (normalized volatility measure)
    df['bb_width'] = (bb_upper - bb_lower) / bb_middle
    
    # RSI momentum
    df['rsi_change'] = df['rsi'].diff()
    
    # MACD histogram
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # Trend strength (ADX-like indicator) -- optimized with raw=True
    close_values = df['close_price'].values
    trend_strength = np.full(len(close_values), np.nan)
    for i in range(13, len(close_values)):
        window = close_values[i-13:i+1]
        std = np.std(window)
        if std > 0:
            trend_strength[i] = abs(window[-1] - window[0]) / std
        else:
            trend_strength[i] = 0
    df['trend_strength'] = trend_strength
    
    # ================================================================
    # S2-5: Market Regime Detection (same 5 features as Strategy 1)
    # Helps model recognize trending vs mean-reverting environments
    # ================================================================
    
    # Regime: SMA trend direction (5-day slope of 20-SMA)
    sma20 = df['close_price'].rolling(window=20).mean()
    df['regime_sma20_slope'] = sma20.pct_change(5) * 100
    
    # Regime: ADX-like trend strength (simplified directional movement)
    up_move = df['high_price'].diff()
    down_move = -df['low_price'].diff()
    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    pos_dm_smooth = pd.Series(pos_dm, index=df.index).rolling(14).mean()
    neg_dm_smooth = pd.Series(neg_dm, index=df.index).rolling(14).mean()
    dm_sum = pos_dm_smooth + neg_dm_smooth
    dx = np.where(dm_sum > 0, np.abs(pos_dm_smooth - neg_dm_smooth) / dm_sum * 100, 0)
    df['regime_adx'] = pd.Series(dx, index=df.index).rolling(14).mean()
    
    # Regime: Volatility regime (short-term vol vs long-term vol)
    vol_short = df['close_price'].pct_change().rolling(10).std()
    vol_long = df['close_price'].pct_change().rolling(60).std()
    df['regime_vol_ratio'] = np.where(vol_long > 0, vol_short / vol_long, 1.0)
    
    # Regime: Mean reversion (distance from 50-SMA in ATR units)
    sma50 = df['close_price'].rolling(window=50).mean()
    atr_14 = df['hl_range'].rolling(window=14).mean() * df['close_price']  # Approximate ATR
    df['regime_mean_reversion'] = np.where(
        atr_14 > 0,
        (df['close_price'] - sma50) / atr_14,
        0
    )
    
    # Regime: Trend consistency (% of last 20 days moving in overall direction)
    overall_dir = np.sign(df['close_price'].diff(20))
    daily_dirs = np.sign(df['close_price'].diff(1))
    consistent = (daily_dirs == overall_dir).astype(float)
    df['regime_trend_consistency'] = consistent.rolling(20).mean()
    
    return df.dropna()

def _create_model(model_name):
    """Create a fresh model instance by name."""
    if model_name == 'XGBoost' and XGBOOST_AVAILABLE:
        return xgb.XGBRegressor(
            n_estimators=150, learning_rate=0.05, max_depth=6,
            min_child_weight=3, subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbosity=0
        )
    elif model_name == 'Random Forest':
        return RandomForestRegressor(
            n_estimators=100, max_depth=10, min_samples_split=5,
            min_samples_leaf=2, max_features='sqrt', random_state=42, n_jobs=-1
        )
    elif model_name == 'Gradient Boosting':
        return GradientBoostingRegressor(
            n_estimators=100, learning_rate=0.05, max_depth=6,
            min_samples_split=5, subsample=0.8, random_state=42
        )
    else:
        return LinearRegression()


def train_and_predict_ensemble(df, days_ahead, model_names):
    """
    S2-7: Ensemble prediction averaging across all models.
    S2-3: Walk-forward validation (expanding window) for honest confidence.
    S2-4: Time-weighted training (recent data weighted more).
    S2-2: Calibrated confidence (no artificial multiplier).
    
    Returns: (predicted_change, confidence) or (None, None)
    """
    feature_cols = [col for col in df.columns if col not in EXCLUDE_FROM_FEATURES]
    
    # Create target (future return)
    df_model = df.copy()
    df_model['target'] = df_model['close_price'].shift(-days_ahead) / df_model['close_price'] - 1
    df_model = df_model.dropna()
    
    # S2-8: Require minimum 200 samples for reliable training
    if len(df_model) < 200:
        return None, None
    
    X_all = df_model[feature_cols].values
    y_all = df_model['target'].values
    
    # S2-4: Time-weighted sample weights (exponential recency)
    n_samples = len(y_all)
    time_positions = np.arange(n_samples) / n_samples  # 0 to ~1
    decay_rate = 1.2
    time_weights = np.exp(decay_rate * (time_positions - 1))  # ~0.3 to 1.0
    time_weights = time_weights / time_weights.mean()  # Normalize to mean=1
    
    # S2-3: Walk-forward validation (3 expanding windows with purge gap)
    # Instead of a single 80/20 split, test across multiple time periods
    n_windows = 3
    purge_gap = max(days_ahead, 5)  # Gap >= prediction horizon to prevent leakage
    min_train = int(n_samples * 0.4)
    window_size = max(30, (n_samples - min_train) // (n_windows + 1))
    
    all_wf_direction_scores = []
    
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
        wf_X_train_scaled = scaler_wf.fit_transform(wf_X_train)
        wf_X_test_scaled = scaler_wf.transform(wf_X_test)
        
        # Test each model in the walk-forward window
        for model_name in model_names:
            try:
                model = _create_model(model_name)
                try:
                    model.fit(wf_X_train_scaled, wf_y_train, sample_weight=wf_weights)
                except TypeError:
                    model.fit(wf_X_train_scaled, wf_y_train)
                
                wf_preds = model.predict(wf_X_test_scaled)
                direction_acc = np.mean(np.sign(wf_y_test) == np.sign(wf_preds))
                all_wf_direction_scores.append(direction_acc)
            except Exception:
                pass
    
    # S2-2: Confidence from walk-forward direction accuracy (honest, no multiplier)
    if all_wf_direction_scores:
        wf_direction_accuracy = np.mean(all_wf_direction_scores) * 100
    else:
        wf_direction_accuracy = 50.0
    
    # Now train final models on ALL data and ensemble-average predictions
    # Use 80/20 split for the final training (with time weights)
    train_end_final = int(n_samples * 0.8)
    X_train_final = X_all[:train_end_final]
    y_train_final = y_all[:train_end_final]
    X_test_final = X_all[train_end_final:]
    y_test_final = y_all[train_end_final:]
    weights_final = time_weights[:train_end_final]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_final)
    X_test_scaled = scaler.transform(X_test_final)
    
    # Get latest data for prediction
    latest_features = df[feature_cols].iloc[-1:].values
    latest_features_scaled = scaler.transform(latest_features)
    
    # S2-7: Ensemble -- train all models, average their predictions
    ensemble_predictions = []
    ensemble_test_preds = []
    
    for model_name in model_names:
        try:
            model = _create_model(model_name)
            try:
                model.fit(X_train_scaled, y_train_final, sample_weight=weights_final)
            except TypeError:
                model.fit(X_train_scaled, y_train_final)
            
            pred = model.predict(latest_features_scaled)[0]
            ensemble_predictions.append(pred)
            
            # Also get test predictions for confidence calculation
            test_pred = model.predict(X_test_scaled)
            ensemble_test_preds.append(test_pred)
        except Exception as e:
            log_message(f"    Model {model_name} failed: {str(e)}", "WARNING")
    
    if not ensemble_predictions:
        return None, None
    
    # Ensemble average prediction
    predicted_change = np.mean(ensemble_predictions)
    
    # Calculate final confidence from multiple signals
    if ensemble_test_preds and len(y_test_final) > 0:
        # Average test predictions across ensemble
        avg_test_preds = np.mean(ensemble_test_preds, axis=0)
        
        # 1. Test set direction accuracy (30% weight)
        test_direction_acc = np.mean(np.sign(y_test_final) == np.sign(avg_test_preds)) * 100
        
        # 2. Walk-forward direction accuracy (50% weight -- most honest measure)
        # Already calculated above as wf_direction_accuracy
        
        # 3. Ensemble agreement (20% weight -- models agree = more confident)
        pred_signs = [np.sign(p) for p in ensemble_predictions]
        agreement = np.mean([s == pred_signs[0] for s in pred_signs]) * 100
        
        # S2-2: Calibrated confidence formula (no artificial multiplier)
        confidence = (
            0.50 * wf_direction_accuracy +  # Walk-forward (honest OOS metric)
            0.30 * test_direction_acc +       # Test set accuracy
            0.20 * agreement                  # Ensemble agreement
        )
        
        # Bounds (no multiplier, no inflating)
        confidence = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, confidence))
    else:
        confidence = CONFIDENCE_MIN
    
    return predicted_change, confidence


def train_and_predict(df, days_ahead, model_name='XGBoost'):
    """Legacy single-model interface (used by train_and_predict_with_feedback).
    Now delegates to ensemble internally but returns result for the specified model name.
    """
    # Use ensemble but return result tagged with the given model_name
    model_names = [model_name]
    return train_and_predict_ensemble(df, days_ahead, model_names)

def train_and_predict_with_feedback(df, days_ahead, model_name, performance_history):
    """
    Enhanced prediction function with ACTIVE LEARNING.
    Uses historical performance to adjust confidence scores.
    """
    try:
        # Train model normally
        predicted_change, base_confidence = train_and_predict(df, days_ahead, model_name)
        
        if predicted_change is None or base_confidence is None:
            return None, None
        
        # ACTIVE LEARNING: Adjust confidence based on historical model performance
        if USE_ACTIVE_LEARNING and performance_history:
            adjusted_confidence = adjust_confidence_with_history(
                base_confidence, model_name, performance_history
            )
            
            # Log adjustment if significant
            if abs(adjusted_confidence - base_confidence) > 3:
                log_message(
                    f"      {model_name}: Confidence adjusted {base_confidence:.1f}% -> {adjusted_confidence:.1f}% "
                    f"(historical accuracy: {performance_history.get(model_name, {}).get('direction_accuracy', 0.5):.1%})",
                    "INFO"
                )
            
            return predicted_change, adjusted_confidence
        else:
            return predicted_change, base_confidence
            
    except Exception as e:
        log_message(f"Model training error for {model_name}: {str(e)}", "ERROR")
        return None, None

def store_prediction(cursor, market, ticker, company_name, days_ahead, model_name, 
                    current_price, predicted_change, confidence):
    """
    Store prediction in database. 
    Skips if a prediction already exists for this market/ticker/date/days_ahead/model.
    Uses the cursor passed from the main function (no separate commit -- batched).
    """
    prediction_date = datetime.now().date()
    target_date = prediction_date + timedelta(days=days_ahead)
    predicted_price = current_price * (1 + predicted_change)
    
    # Check for duplicate before inserting
    dup_check = """
    SELECT COUNT(*) FROM ai_prediction_history 
    WHERE market = ? AND ticker = ? AND prediction_date = ? AND days_ahead = ? AND model_name = ?
    """
    cursor.execute(dup_check, (market, ticker, str(prediction_date), days_ahead, model_name))
    if cursor.fetchone()[0] > 0:
        return False  # Duplicate, skip
    
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
        update_sql = f"""
        UPDATE p
        SET 
            p.actual_price = CAST(h.close_price AS FLOAT),
            p.actual_change_pct = ((CAST(h.close_price AS FLOAT) - CAST(p.current_price AS FLOAT)) / CAST(p.current_price AS FLOAT)) * 100,
            p.absolute_error = ABS(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT)),
            p.squared_error = POWER(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT), 2),
            p.percentage_error = ABS(CAST(p.predicted_price AS FLOAT) - CAST(h.close_price AS FLOAT)) / CAST(h.close_price AS FLOAT) * 100,
            p.direction_correct = CASE 
                WHEN p.predicted_change_pct > 0.01 AND CAST(h.close_price AS FLOAT) > CAST(p.current_price AS FLOAT) THEN 1
                WHEN p.predicted_change_pct < -0.01 AND CAST(h.close_price AS FLOAT) < CAST(p.current_price AS FLOAT) THEN 1
                WHEN ABS(p.predicted_change_pct) <= 0.01 AND ABS(CAST(h.close_price AS FLOAT) - CAST(p.current_price AS FLOAT)) / CAST(p.current_price AS FLOAT) < 0.005 THEN 1
                ELSE 0
            END,
            p.updated_at = GETDATE()
        FROM ai_prediction_history p
        CROSS APPLY (
            SELECT TOP 1 close_price
            FROM {table}
            WHERE {symbol_col} = p.ticker 
              AND trading_date <= p.target_date
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

def run_daily_predictions():
    """Main function to run daily predictions with ACTIVE LEARNING"""
    start_time = datetime.now()
    
    log_message("=" * 80)
    log_message("Starting Daily AI Price Prediction Job (Strategy 2)")
    if USE_ACTIVE_LEARNING:
        log_message("ACTIVE LEARNING ENABLED - Using historical performance feedback")
    log_message("=" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Step 1: Update actual prices for past predictions (backtest)
    log_message("Step 1: Updating actual prices for past predictions...")
    update_actual_prices(conn)
    
    # Models to use
    all_models = ['XGBoost', 'Random Forest', 'Gradient Boosting']
    if not XGBOOST_AVAILABLE:
        all_models = ['Random Forest', 'Gradient Boosting', 'Linear Regression']
    log_message(f"Models available: {', '.join(all_models)}")
    
    total_predictions = 0
    total_skipped_dup = 0
    total_skipped_data = 0
    models_skipped = 0
    errors = 0
    
    # Step 2: Generate predictions for each market
    for market in MARKETS.keys():
        log_message(f"\nStep 2: Processing {market}...")
        market_start = datetime.now()
        
        # Get stocks (reuse connection)
        stocks = get_top_stocks(conn, market, MAX_STOCKS_PER_MARKET)
        log_message(f"  Found {len(stocks)} stocks to analyze")
        
        # OPTIMIZATION: Bulk preload ALL stock data in one query (instead of 256 individual queries)
        ticker_list = stocks['ticker'].tolist()
        all_stock_data = bulk_load_stock_data(conn, market, ticker_list)
        log_message(f"  {len(all_stock_data)} tickers have sufficient data (>= {MIN_DATA_POINTS} rows)")
        
        # OPTIMIZATION: Bulk preload ALL active learning history in one query (instead of 768 individual queries)
        all_performance_history = {}
        if USE_ACTIVE_LEARNING:
            perf_start = datetime.now()
            all_performance_history = bulk_load_performance_history(conn, market)
            perf_elapsed = (datetime.now() - perf_start).total_seconds()
            tickers_with_history = len(all_performance_history)
            log_message(f"  Loaded active learning history for {tickers_with_history} tickers in {perf_elapsed:.1f}s")
        
        market_predictions = 0
        
        for idx, row in stocks.iterrows():
            ticker = row['ticker']
            company_name = row['company_name']
            
            # Get data from bulk-loaded cache (no SQL query needed)
            if ticker not in all_stock_data:
                total_skipped_data += 1
                continue
            
            df_raw = all_stock_data[ticker]
            
            log_message(f"  Processing {ticker} ({company_name})...")
            
            # Calculate indicators
            df = calculate_technical_indicators(df_raw)
            if len(df) < MIN_DATA_POINTS:
                log_message(f"    Skipping {ticker}: Insufficient data after indicators ({len(df)} < {MIN_DATA_POINTS})", "WARNING")
                total_skipped_data += 1
                continue
            
            current_price = df['close_price'].iloc[-1]
            
            # Make predictions for each timeframe using ENSEMBLE
            for days_ahead in PREDICTION_DAYS:
                
                # ACTIVE LEARNING: Get from preloaded cache (no SQL query needed)
                performance_history = {}
                if USE_ACTIVE_LEARNING:
                    performance_history = get_performance_from_cache(
                        all_performance_history, ticker, days_ahead
                    )
                    
                    if performance_history:
                        log_message(f"    [{days_ahead}-day] Historical data: {len(performance_history)} models tracked", "INFO")
                
                # ACTIVE LEARNING: Select best models based on historical performance
                if USE_ACTIVE_LEARNING and performance_history:
                    selected_models = select_best_models(performance_history, all_models)
                    if len(selected_models) < len(all_models):
                        models_skipped += (len(all_models) - len(selected_models))
                        log_message(f"    [{days_ahead}-day] Using {len(selected_models)}/{len(all_models)} models (skipped underperformers)", "INFO")
                else:
                    selected_models = all_models
                
                # S2-7: Generate ENSEMBLE prediction (average of all selected models)
                try:
                    predicted_change, confidence = train_and_predict_ensemble(
                        df, days_ahead, selected_models
                    )
                    
                    if predicted_change is not None:
                        # Apply active learning confidence adjustment
                        if USE_ACTIVE_LEARNING and performance_history:
                            # Use best-performing model's history for adjustment
                            best_hist_model = max(
                                performance_history.items(),
                                key=lambda x: x[1]['direction_accuracy'],
                                default=(None, None)
                            )
                            if best_hist_model[0]:
                                confidence = adjust_confidence_with_history(
                                    confidence, best_hist_model[0], performance_history
                                )
                        
                        # Store as "Ensemble" model name
                        inserted = store_prediction(
                            cursor, market, ticker, company_name, days_ahead, 'Ensemble',
                            current_price, predicted_change, confidence
                        )
                        if inserted:
                            total_predictions += 1
                            market_predictions += 1
                        else:
                            total_skipped_dup += 1
                except Exception as e:
                    errors += 1
                    log_message(f"    Error predicting {ticker}/Ensemble/{days_ahead}d: {str(e)}", "ERROR")
            
            if (idx + 1) % 10 == 0:
                log_message(f"  Processed {idx + 1}/{len(stocks)} stocks...")
        
        # Free memory for this market's bulk data
        del all_stock_data
        del all_performance_history
        
        # Commit after each market (batch commit)
        conn.commit()
        market_elapsed = (datetime.now() - market_start).total_seconds()
        log_message(f"  {market} complete: {market_predictions} predictions in {market_elapsed:.1f}s")
    
    conn.close()
    
    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    log_message("")
    log_message("=" * 80)
    log_message(f"Daily Prediction Job Completed Successfully!")
    log_message(f"  Total Predictions Generated: {total_predictions}")
    log_message(f"  Duplicates Skipped:          {total_skipped_dup}")
    log_message(f"  Stocks Skipped (no data):    {total_skipped_data}")
    log_message(f"  Errors:                      {errors}")
    if USE_ACTIVE_LEARNING:
        log_message(f"  Models Skipped (underperf):  {models_skipped}")
    log_message(f"  Total Time:                  {elapsed:.1f}s ({elapsed/60:.1f} min)")
    log_message("=" * 80)

if __name__ == "__main__":
    try:
        run_daily_predictions()
    except Exception as e:
        log_message(f"CRITICAL ERROR: {str(e)}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        exit(1)
