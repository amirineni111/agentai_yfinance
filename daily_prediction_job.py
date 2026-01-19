"""
Daily AI Price Prediction Job
==============================
Runs daily to:
1. Generate predictions for all markets and models
2. Store predictions in database
3. Update actual prices for past predictions
4. Calculate accuracy metrics

Schedule this to run daily via Windows Task Scheduler
"""

import pandas as pd
import numpy as np
import pyodbc
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import ML libraries
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except:
    LIGHTGBM_AVAILABLE = False

try:
    from tensorflow import keras
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.optimizers import Adam
    LSTM_AVAILABLE = True
except:
    LSTM_AVAILABLE = False

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except:
    PROPHET_AVAILABLE = False

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
    'Forex': {'table': 'forex_hist_data', 'symbol_col': 'symbol', 'company_col': 'symbol'}
}

PREDICTION_DAYS = [1, 3, 7]  # Predict 1, 3, and 7 days ahead
MAX_STOCKS_PER_MARKET = 50  # Not used when USE_WATCHLIST is True
MIN_DATA_POINTS = 100  # Minimum historical data required

# Confidence boost for direction-based trading (since direction accuracy is good)
CONFIDENCE_MULTIPLIER = 1.3  # Boost confidence by 30% for practical usability

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
USE_WATCHLIST = True  # Set to True to use watchlist, False for top volume stocks

def log_message(message, level="INFO"):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Remove emojis that cause encoding issues in Windows console
    message = message.encode('ascii', 'ignore').decode('ascii')
    print(f"[{timestamp}] [{level}] {message}")

def get_watchlist_stocks(market):
    """Get stocks from database watchlist table"""
    conn = get_db_connection()
    
    query = """
    SELECT ticker, company_name
    FROM prediction_watchlist
    WHERE market = ? AND is_active = 1
    ORDER BY priority, ticker
    """
    
    df = pd.read_sql(query, conn, params=[market])
    conn.close()
    
    if len(df) == 0:
        log_message(f"No active tickers in watchlist for {market}, falling back to top volume", "WARNING")
        return get_top_volume_stocks(market, MAX_STOCKS_PER_MARKET)
    
    log_message(f"Loaded {len(df)} stocks from watchlist table for {market}")
    return df

def get_model_performance_history(conn, market, ticker, days_ahead):
    """
    Get historical performance for all models for a specific stock and timeframe.
    Returns dict with model_name as key and performance metrics as value.
    
    This enables ACTIVE LEARNING - the system learns from past prediction accuracy.
    """
    lookback_date = (datetime.now() - timedelta(days=HISTORICAL_LOOKBACK_DAYS)).date()
    
    query = """
    SELECT 
        model_name,
        COUNT(*) as prediction_count,
        AVG(CAST(direction_correct AS FLOAT)) as direction_accuracy,
        AVG(ABS(percentage_error)) as avg_error_pct,
        AVG(model_confidence) as avg_confidence,
        STDEV(percentage_error) as error_volatility
    FROM ai_prediction_history
    WHERE market = ?
      AND ticker = ?
      AND days_ahead = ?
      AND prediction_date >= ?
      AND actual_price IS NOT NULL
      AND direction_correct IS NOT NULL
    GROUP BY model_name
    HAVING COUNT(*) >= ?
    """
    
    cursor = conn.cursor()
    cursor.execute(query, (market, ticker, days_ahead, str(lookback_date), MIN_PREDICTIONS_FOR_LEARNING))
    
    performance = {}
    for row in cursor.fetchall():
        model_name, count, direction_acc, avg_error, avg_conf, error_vol = row
        performance[model_name] = {
            'count': count,
            'direction_accuracy': direction_acc if direction_acc else 0.5,
            'avg_error_pct': avg_error if avg_error else 10.0,
            'avg_confidence': avg_conf if avg_conf else 50.0,
            'error_volatility': error_vol if error_vol else 5.0
        }
    
    return performance

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
    # If model historically gets 60% direction accuracy, boost confidence
    # If model historically gets 45% direction accuracy, reduce confidence
    
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
    
    # Keep within bounds
    adjusted_confidence = max(30, min(85, adjusted_confidence))
    
    return adjusted_confidence


def get_top_volume_stocks(market, limit=50):
    """Get top stocks by trading volume for a market"""
    conn = get_db_connection()
    config = MARKETS[market]
    
    query = f"""
    SELECT TOP {limit}
        {config['symbol_col']} as ticker,
        {config['company_col']} as company_name,
        AVG(CAST(volume AS FLOAT)) as avg_volume
    FROM {config['table']}
    WHERE trading_date >= DATEADD(day, -30, GETDATE())
    GROUP BY {config['symbol_col']}, {config['company_col']}
    ORDER BY avg_volume DESC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_top_stocks(market, limit=50):
    """Get stocks based on configuration (watchlist or top volume)"""
    if USE_WATCHLIST:
        return get_watchlist_stocks(market)
    else:
        return get_top_volume_stocks(market, limit)

def load_stock_data(market, ticker):
    """Load historical data for a stock"""
    conn = get_db_connection()
    config = MARKETS[market]
    
    query = f"""
    SELECT TOP 1000
        trading_date,
        close_price,
        volume,
        high_price,
        low_price
    FROM {config['table']}
    WHERE {config['symbol_col']} = ?
    ORDER BY trading_date DESC
    """
    
    df = pd.read_sql(query, conn, params=[ticker])
    conn.close()
    
    if len(df) < MIN_DATA_POINTS:
        return None
    
    # Reverse to chronological order
    df = df.sort_values('trading_date').reset_index(drop=True)
    return df

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
    
    # Moving averages
    for period in [5, 10, 20, 50]:
        df[f'sma_{period}'] = df['close_price'].rolling(window=period).mean()
        df[f'ema_{period}'] = df['close_price'].ewm(span=period, adjust=False).mean()
    
    # Volatility
    df['volatility_20'] = df['returns'].rolling(window=20).std()
    
    # RSI
    delta = df['close_price'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['close_price'].ewm(span=12, adjust=False).mean()
    ema26 = df['close_price'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # Bollinger Bands
    df['bb_middle'] = df['close_price'].rolling(window=20).mean()
    bb_std = df['close_price'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # Volume features (handle forex with zero volume)
    df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
    # For forex pairs where volume is always 0, set volume_ratio to 1
    df['volume_ratio'] = df['volume'] / df['volume_sma_20'].replace(0, 1)
    df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
    
    # Price momentum
    df['momentum_5'] = df['close_price'] / df['close_price'].shift(5) - 1
    df['momentum_10'] = df['close_price'] / df['close_price'].shift(10) - 1
    
    # Additional advanced features for better predictions
    # High-Low Range (volatility indicator)
    df['hl_range'] = (df['high_price'] - df['low_price']) / df['close_price']
    df['hl_range_ma'] = df['hl_range'].rolling(window=10).mean()
    
    # Price position within range
    df['price_position'] = (df['close_price'] - df['low_price']) / (df['high_price'] - df['low_price'] + 1e-8)
    
    # Bollinger Band position
    df['bb_position'] = (df['close_price'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-8)
    
    # RSI momentum
    df['rsi_change'] = df['rsi'].diff()
    
    # MACD histogram
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # Trend strength (ADX-like indicator)
    df['trend_strength'] = df['close_price'].rolling(window=14).apply(
        lambda x: abs(x.iloc[-1] - x.iloc[0]) / x.std() if x.std() > 0 else 0, raw=False
    )
    
    return df.dropna()

def train_and_predict(df, days_ahead, model_name='XGBoost'):
    """Train model and make prediction"""
    # Prepare features
    feature_cols = [col for col in df.columns if col not in ['trading_date', 'close_price', 'target']]
    
    # Create target (future return)
    df_model = df.copy()
    df_model['target'] = df_model['close_price'].shift(-days_ahead) / df_model['close_price'] - 1
    df_model = df_model.dropna()
    
    if len(df_model) < 50:
        return None, None
    
    # Train/test split (80% train, 20% validation)
    train_size = int(len(df_model) * 0.8)
    train_df = df_model.iloc[:train_size]
    test_df = df_model.iloc[train_size:]
    
    X_train = train_df[feature_cols].values
    y_train = train_df['target'].values
    X_test = test_df[feature_cols].values
    y_test = test_df['target'].values
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Get latest data for prediction
    latest_features = df[feature_cols].iloc[-1:].values
    latest_features_scaled = scaler.transform(latest_features)
    
    # Train model with improved hyperparameters
    try:
        if model_name == 'XGBoost' and XGBOOST_AVAILABLE:
            model = xgb.XGBRegressor(
                n_estimators=150, 
                learning_rate=0.05, 
                max_depth=6, 
                min_child_weight=3,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42, 
                verbosity=0
            )
        elif model_name == 'LightGBM' and LIGHTGBM_AVAILABLE:
            model = lgb.LGBMRegressor(
                n_estimators=150, 
                learning_rate=0.05, 
                max_depth=6, 
                num_leaves=31,
                subsample=0.8,
                random_state=42, 
                verbose=-1
            )
        elif model_name == 'Random Forest':
            model = RandomForestRegressor(
                n_estimators=100, 
                max_depth=10, 
                min_samples_split=5,
                min_samples_leaf=2,
                max_features='sqrt',
                random_state=42, 
                n_jobs=1
            )
        elif model_name == 'Gradient Boosting':
            model = GradientBoostingRegressor(
                n_estimators=100, 
                learning_rate=0.05, 
                max_depth=6,
                min_samples_split=5,
                subsample=0.8,
                random_state=42
            )
        else:
            model = LinearRegression()
        
        model.fit(X_train_scaled, y_train)
        predicted_change = model.predict(latest_features_scaled)[0]
        
        # Calculate confidence based on validation performance (IMPROVED)
        if len(X_test) > 0:
            y_pred_test = model.predict(X_test_scaled)
            
            # 1. Direction Accuracy (most important for trading)
            direction_actual = np.sign(y_test)
            direction_pred = np.sign(y_pred_test)
            direction_accuracy = np.mean(direction_actual == direction_pred) * 100
            
            # 2. Magnitude Accuracy (how close are predictions)
            mae = np.mean(np.abs(y_test - y_pred_test))
            mean_abs_return = np.mean(np.abs(y_test))
            magnitude_accuracy = max(0, (1 - mae / (mean_abs_return + 1e-8)) * 100)
            
            # 3. R² Score (variance explained)
            ss_res = np.sum((y_test - y_pred_test) ** 2)
            ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
            r2_score = max(0, 1 - ss_res / (ss_tot + 1e-8))
            r2_confidence = r2_score * 100
            
            # 4. Consistency Score (predictions not too volatile)
            pred_std = np.std(y_pred_test)
            actual_std = np.std(y_test)
            consistency = max(0, 100 - abs(pred_std - actual_std) / (actual_std + 1e-8) * 100)
            
            # IMPROVED FORMULA: Emphasize direction accuracy (most useful for trading)
            # 50% direction + 20% magnitude + 15% R² + 15% consistency
            confidence = (
                0.50 * direction_accuracy + 
                0.20 * magnitude_accuracy + 
                0.15 * r2_confidence + 
                0.15 * consistency
            )
            
            # Adjust confidence based on test set size (more data = more reliable)
            if len(X_test) < 50:
                confidence *= 0.8  # Reduce confidence if test set too small
            elif len(X_test) > 150:
                confidence *= 1.15  # Boost confidence with large test set
            
            # Apply confidence multiplier for practical usability
            # (Direction accuracy is often 55-60% which is valuable for trading)
            confidence *= CONFIDENCE_MULTIPLIER
            
            # More realistic bounds: 35-80%
            confidence = max(35, min(80, confidence))
        else:
            confidence = 50.0  # Default if no test data
        
        return predicted_change, confidence
        
    except Exception as e:
        log_message(f"Model training error for {model_name}: {str(e)}", "ERROR")
        return None, None

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
                    f"      {model_name}: Confidence adjusted {base_confidence:.1f}% → {adjusted_confidence:.1f}% "
                    f"(historical accuracy: {performance_history.get(model_name, {}).get('direction_accuracy', 0.5):.1%})",
                    "INFO"
                )
            
            return predicted_change, adjusted_confidence
        else:
            return predicted_change, base_confidence
            
    except Exception as e:
        log_message(f"Model training error for {model_name}: {str(e)}", "ERROR")
        return None, None

def store_prediction(conn, market, ticker, company_name, days_ahead, model_name, 
                    current_price, predicted_change, confidence):
    """Store prediction in database"""
    prediction_date = datetime.now().date()
    target_date = prediction_date + timedelta(days=days_ahead)
    predicted_price = current_price * (1 + predicted_change)
    
    cursor = conn.cursor()
    
    query = """
    INSERT INTO ai_prediction_history 
    (market, ticker, company_name, prediction_date, target_date, days_ahead, model_name,
     current_price, predicted_price, predicted_change_pct, model_confidence)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    # Convert dates to strings for pyodbc compatibility
    cursor.execute(query, (
        market, ticker, company_name, str(prediction_date), str(target_date), days_ahead, model_name,
        float(current_price), float(predicted_price), float(predicted_change * 100), float(confidence)
    ))
    
    conn.commit()

def update_actual_prices(conn):
    """Update actual prices for past predictions where target_date has arrived"""
    today = datetime.now().date()
    
    cursor = conn.cursor()
    
    # Get predictions where target_date <= today and actual_price is NULL
    query = """
    SELECT prediction_id, market, ticker, target_date, predicted_price, predicted_change_pct
    FROM ai_prediction_history
    WHERE target_date <= ? AND actual_price IS NULL
    """
    
    # Convert date to string for pyodbc compatibility
    cursor.execute(query, (str(today),))
    pending_predictions = cursor.fetchall()
    
    log_message(f"Found {len(pending_predictions)} predictions to update")
    
    updated = 0
    for pred in pending_predictions:
        pred_id, market, ticker, target_date, predicted_price, predicted_change_pct = pred
        
        # Get actual price on target_date
        config = MARKETS[market]
        price_query = f"""
        SELECT TOP 1 close_price
        FROM {config['table']}
        WHERE {config['symbol_col']} = ? 
          AND trading_date <= ?
        ORDER BY trading_date DESC
        """
        
        # Convert target_date to string for pyodbc compatibility
        cursor.execute(price_query, (ticker, str(target_date)))
        result = cursor.fetchone()
        
        if result:
            actual_price = float(result[0])  # Convert to float
            
            # Get the original price to calculate actual change
            original_query = """
            SELECT current_price FROM ai_prediction_history WHERE prediction_id = ?
            """
            cursor.execute(original_query, (pred_id,))
            current_price = float(cursor.fetchone()[0])  # Convert to float
            
            # Convert predicted values to float as well
            predicted_price = float(predicted_price)
            predicted_change_pct = float(predicted_change_pct)
            
            actual_change_pct = ((actual_price - current_price) / current_price) * 100
            absolute_error = abs(predicted_price - actual_price)
            squared_error = (predicted_price - actual_price) ** 2
            percentage_error = (absolute_error / actual_price) * 100
            
            # Check if direction was correct
            direction_correct = (predicted_change_pct > 0 and actual_change_pct > 0) or \
                              (predicted_change_pct < 0 and actual_change_pct < 0) or \
                              (predicted_change_pct == 0 and actual_change_pct == 0)
            
            # Update the record
            update_query = """
            UPDATE ai_prediction_history
            SET actual_price = ?,
                actual_change_pct = ?,
                absolute_error = ?,
                squared_error = ?,
                percentage_error = ?,
                direction_correct = ?,
                updated_at = GETDATE()
            WHERE prediction_id = ?
            """
            
            cursor.execute(update_query, (
                actual_price, actual_change_pct, absolute_error, squared_error,
                percentage_error, direction_correct, pred_id
            ))
            
            updated += 1
    
    conn.commit()
    log_message(f"Updated {updated} predictions with actual prices")

def run_daily_predictions():
    """Main function to run daily predictions with ACTIVE LEARNING"""
    log_message("=" * 80)
    log_message("Starting Daily AI Price Prediction Job")
    if USE_ACTIVE_LEARNING:
        log_message("ACTIVE LEARNING ENABLED - Using historical performance feedback")
    log_message("=" * 80)
    
    conn = get_db_connection()
    
    # First, update actual prices for past predictions
    log_message("Step 1: Updating actual prices for past predictions...")
    update_actual_prices(conn)
    
    # Models to use
    all_models = ['XGBoost', 'Random Forest', 'Gradient Boosting']
    if not XGBOOST_AVAILABLE:
        all_models = ['Random Forest', 'Gradient Boosting', 'Linear Regression']
    
    total_predictions = 0
    models_skipped = 0
    models_adjusted = 0
    
    # Generate predictions for each market
    for market in MARKETS.keys():
        log_message(f"\nStep 2: Processing {market}...")
        
        # Get top stocks
        stocks = get_top_stocks(market, MAX_STOCKS_PER_MARKET)
        log_message(f"  Found {len(stocks)} stocks to analyze")
        
        for idx, row in stocks.iterrows():
            ticker = row['ticker']
            company_name = row['company_name']
            
            log_message(f"  Processing {ticker} ({company_name})...")
            
            # Load data
            df = load_stock_data(market, ticker)
            if df is None:
                log_message(f"    Skipping {ticker}: Insufficient data (< {MIN_DATA_POINTS} records)", "WARNING")
                continue
            
            # Calculate indicators
            df = calculate_technical_indicators(df)
            if len(df) < MIN_DATA_POINTS:
                log_message(f"    Skipping {ticker}: Insufficient data after indicators ({len(df)} < {MIN_DATA_POINTS})", "WARNING")
                continue
            
            current_price = df['close_price'].iloc[-1]
            
            # Make predictions for each timeframe
            for days_ahead in PREDICTION_DAYS:
                
                # ACTIVE LEARNING: Get historical performance for this stock/timeframe
                performance_history = {}
                if USE_ACTIVE_LEARNING:
                    performance_history = get_model_performance_history(
                        conn, market, ticker, days_ahead
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
                
                # Generate predictions with each selected model
                for model_name in selected_models:
                    
                    # ACTIVE LEARNING: Use feedback-enhanced prediction
                    if USE_ACTIVE_LEARNING:
                        predicted_change, confidence = train_and_predict_with_feedback(
                            df, days_ahead, model_name, performance_history
                        )
                    else:
                        predicted_change, confidence = train_and_predict(
                            df, days_ahead, model_name
                        )
                    
                    if predicted_change is not None:
                        store_prediction(
                            conn, market, ticker, company_name, days_ahead, model_name,
                            current_price, predicted_change, confidence
                        )
                        total_predictions += 1
            
            if (idx + 1) % 10 == 0:
                log_message(f"  Processed {idx + 1}/{len(stocks)} stocks...")
    
    conn.close()
    
    log_message("=" * 80)
    log_message(f"Daily Prediction Job Completed Successfully!")
    log_message(f"Total Predictions Generated: {total_predictions}")
    if USE_ACTIVE_LEARNING:
        log_message(f"Active Learning Stats: {models_skipped} poor-performing model runs skipped")
    log_message("=" * 80)

if __name__ == "__main__":
    try:
        run_daily_predictions()
    except Exception as e:
        log_message(f"CRITICAL ERROR: {str(e)}", "ERROR")
        import traceback
        log_message(traceback.format_exc(), "ERROR")
        exit(1)
