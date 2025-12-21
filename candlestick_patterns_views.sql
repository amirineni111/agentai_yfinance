-- =====================================================
-- Candlestick Pattern Detection SQL View Definitions
-- =====================================================
-- This script creates pattern detection views for NSE 500, NASDAQ 100, and Forex
-- Includes: Cup and Handle, Head and Shoulders, Double Top/Bottom, and more
-- =====================================================

USE stockdata_db;
GO

-- =====================================================
-- NSE 500 Candlestick Patterns View
-- =====================================================
IF OBJECT_ID('dbo.nse_500_patterns', 'V') IS NOT NULL
    DROP VIEW dbo.nse_500_patterns;
GO

CREATE VIEW dbo.nse_500_patterns AS
WITH PriceData AS (
    SELECT 
        ticker,
        trading_date,
        CAST(open_price AS FLOAT) as open_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        CAST(close_price AS FLOAT) as close_price,
        volume,
        -- Rolling window calculations for pattern detection
        -- 20-day highs and lows
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as high_20d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as low_20d,
        -- 50-day highs and lows for cup patterns
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as high_50d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as low_50d,
        -- Moving averages
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as sma_20,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma_50,
        -- Previous candles for pattern recognition
        LAG(CAST(open_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_open,
        LAG(CAST(high_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_high,
        LAG(CAST(low_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_low,
        LAG(CAST(close_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_close,
        LAG(CAST(close_price AS FLOAT), 2) OVER (PARTITION BY ticker ORDER BY trading_date) as prev2_close,
        LAG(CAST(high_price AS FLOAT), 2) OVER (PARTITION BY ticker ORDER BY trading_date) as prev2_high,
        LAG(CAST(low_price AS FLOAT), 2) OVER (PARTITION BY ticker ORDER BY trading_date) as prev2_low
    FROM dbo.nse_500_hist_data
    WHERE close_price IS NOT NULL
),
PatternCalculations AS (
    SELECT 
        ticker,
        trading_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        sma_20,
        sma_50,
        high_20d,
        low_20d,
        high_50d,
        low_50d,
        
        -- Candlestick body and shadow sizes
        ABS(close_price - open_price) as body_size,
        (high_price - CASE WHEN close_price > open_price THEN close_price ELSE open_price END) as upper_shadow,
        (CASE WHEN close_price < open_price THEN close_price ELSE open_price END - low_price) as lower_shadow,
        
        -- **SINGLE CANDLE PATTERNS**
        
        -- Doji (Open ≈ Close, indecision)
        CASE 
            WHEN ABS(close_price - open_price) <= (high_price - low_price) * 0.1 
            THEN 1 ELSE 0 
        END as is_doji,
        
        -- Hammer (Bullish reversal: small body at top, long lower shadow)
        CASE 
            WHEN (CASE WHEN close_price < open_price THEN close_price ELSE open_price END - low_price) > 2 * ABS(close_price - open_price)
                AND (high_price - CASE WHEN close_price > open_price THEN close_price ELSE open_price END) < ABS(close_price - open_price)
                AND close_price < sma_20
            THEN 1 ELSE 0 
        END as is_hammer,
        
        -- Shooting Star (Bearish reversal: small body at bottom, long upper shadow)
        CASE 
            WHEN (high_price - CASE WHEN close_price > open_price THEN close_price ELSE open_price END) > 2 * ABS(close_price - open_price)
                AND (CASE WHEN close_price < open_price THEN close_price ELSE open_price END - low_price) < ABS(close_price - open_price)
                AND close_price > sma_20
            THEN 1 ELSE 0 
        END as is_shooting_star,
        
        -- **MULTI-CANDLE PATTERNS**
        
        -- Bullish Engulfing (Current green candle engulfs previous red candle)
        CASE 
            WHEN prev_close IS NOT NULL AND prev_open IS NOT NULL
                AND prev_close < prev_open  -- Previous was bearish
                AND close_price > open_price  -- Current is bullish
                AND close_price > prev_open
                AND open_price < prev_close
            THEN 1 ELSE 0 
        END as is_bullish_engulfing,
        
        -- Bearish Engulfing (Current red candle engulfs previous green candle)
        CASE 
            WHEN prev_close IS NOT NULL AND prev_open IS NOT NULL
                AND prev_close > prev_open  -- Previous was bullish
                AND close_price < open_price  -- Current is bearish
                AND close_price < prev_open
                AND open_price > prev_close
            THEN 1 ELSE 0 
        END as is_bearish_engulfing,
        
        -- Morning Star (3-candle bullish reversal: down, doji/small, up)
        CASE 
            WHEN prev2_close IS NOT NULL AND prev_close IS NOT NULL
                AND prev2_close < prev_open  -- First candle bearish
                AND ABS(prev_close - prev_open) < (prev2_close - prev_open) * 0.3  -- Middle candle small
                AND close_price > open_price  -- Third candle bullish
                AND close_price > (prev2_close + prev_open) / 2  -- Closes above midpoint of first
            THEN 1 ELSE 0 
        END as is_morning_star,
        
        -- Evening Star (3-candle bearish reversal: up, doji/small, down)
        CASE 
            WHEN prev2_close IS NOT NULL AND prev_close IS NOT NULL
                AND prev2_close > prev_open  -- First candle bullish
                AND ABS(prev_close - prev_open) < (prev2_close - prev_open) * 0.3  -- Middle candle small
                AND close_price < open_price  -- Third candle bearish
                AND close_price < (prev2_close + prev_open) / 2  -- Closes below midpoint of first
            THEN 1 ELSE 0 
        END as is_evening_star,
        
        -- **CHART PATTERNS**
        
        -- Cup and Handle (50-day pattern: U-shape recovery + consolidation)
        CASE 
            WHEN close_price >= high_50d * 0.95  -- Near 50-day high
                AND close_price > low_50d * 1.15  -- Significantly above 50-day low
                AND low_50d > high_50d * 0.80  -- Cup depth reasonable (not crash)
                AND close_price > sma_50  -- Above 50-day MA
            THEN 1 ELSE 0 
        END as is_cup_and_handle,
        
        -- Inverse Cup and Handle (Bearish)
        CASE 
            WHEN close_price <= low_50d * 1.05  -- Near 50-day low
                AND close_price < high_50d * 0.85  -- Significantly below 50-day high
                AND high_50d < low_50d * 1.20  -- Inverted cup depth reasonable
                AND close_price < sma_50  -- Below 50-day MA
            THEN 1 ELSE 0 
        END as is_inverse_cup_handle,
        
        -- Double Top (Resistance at 20-day high, failed breakout)
        CASE 
            WHEN close_price >= high_20d * 0.98  -- Near 20-day high
                AND prev_high IS NOT NULL 
                AND prev_high >= high_20d * 0.98  -- Previous attempt also near high
                AND close_price < high_20d  -- Failed to break through
            THEN 1 ELSE 0 
        END as is_double_top,
        
        -- Double Bottom (Support at 20-day low, bounce)
        CASE 
            WHEN close_price <= low_20d * 1.02  -- Near 20-day low
                AND prev_low IS NOT NULL 
                AND prev_low <= low_20d * 1.02  -- Previous attempt also near low
                AND close_price > low_20d  -- Bounced from low
                AND close_price > open_price  -- Bullish candle
            THEN 1 ELSE 0 
        END as is_double_bottom,
        
        -- Head and Shoulders (3 peaks: shoulder, head, shoulder)
        CASE 
            WHEN prev2_high IS NOT NULL AND prev_high IS NOT NULL
                AND prev_high > prev2_high * 1.03  -- Head higher than first shoulder
                AND prev_high > high_price * 1.03  -- Head higher than second shoulder
                AND ABS(prev2_high - high_price) / prev2_high < 0.05  -- Shoulders at similar level
                AND close_price < sma_20  -- Breaking down
            THEN 1 ELSE 0 
        END as is_head_and_shoulders,
        
        -- Inverse Head and Shoulders (Bullish reversal)
        CASE 
            WHEN prev2_low IS NOT NULL AND prev_low IS NOT NULL
                AND prev_low < prev2_low * 0.97  -- Head lower than first shoulder
                AND prev_low < low_price * 0.97  -- Head lower than second shoulder
                AND ABS(prev2_low - low_price) / prev2_low < 0.05  -- Shoulders at similar level
                AND close_price > sma_20  -- Breaking up
            THEN 1 ELSE 0 
        END as is_inverse_head_shoulders
        
    FROM PriceData
)
SELECT 
    ticker,
    trading_date,
    close_price,
    ROUND(sma_20, 2) as ma_20,
    ROUND(sma_50, 2) as ma_50,
    
    -- Single Candle Patterns
    CASE WHEN is_doji = 1 THEN 'DOJI' ELSE NULL END as doji,
    CASE WHEN is_hammer = 1 THEN 'HAMMER' ELSE NULL END as hammer,
    CASE WHEN is_shooting_star = 1 THEN 'SHOOTING_STAR' ELSE NULL END as shooting_star,
    
    -- Multi-Candle Patterns
    CASE WHEN is_bullish_engulfing = 1 THEN 'BULLISH_ENGULFING' ELSE NULL END as bullish_engulfing,
    CASE WHEN is_bearish_engulfing = 1 THEN 'BEARISH_ENGULFING' ELSE NULL END as bearish_engulfing,
    CASE WHEN is_morning_star = 1 THEN 'MORNING_STAR' ELSE NULL END as morning_star,
    CASE WHEN is_evening_star = 1 THEN 'EVENING_STAR' ELSE NULL END as evening_star,
    
    -- Chart Patterns
    CASE WHEN is_cup_and_handle = 1 THEN 'CUP_AND_HANDLE' ELSE NULL END as cup_and_handle,
    CASE WHEN is_inverse_cup_handle = 1 THEN 'INVERSE_CUP_HANDLE' ELSE NULL END as inverse_cup_handle,
    CASE WHEN is_double_top = 1 THEN 'DOUBLE_TOP' ELSE NULL END as double_top,
    CASE WHEN is_double_bottom = 1 THEN 'DOUBLE_BOTTOM' ELSE NULL END as double_bottom,
    CASE WHEN is_head_and_shoulders = 1 THEN 'HEAD_AND_SHOULDERS' ELSE NULL END as head_and_shoulders,
    CASE WHEN is_inverse_head_shoulders = 1 THEN 'INVERSE_HEAD_SHOULDERS' ELSE NULL END as inverse_head_shoulders,
    
    -- Pattern Summary (all detected patterns)
    CONCAT_WS(', ',
        CASE WHEN is_doji = 1 THEN 'DOJI' END,
        CASE WHEN is_hammer = 1 THEN 'HAMMER' END,
        CASE WHEN is_shooting_star = 1 THEN 'SHOOTING_STAR' END,
        CASE WHEN is_bullish_engulfing = 1 THEN 'BULLISH_ENGULFING' END,
        CASE WHEN is_bearish_engulfing = 1 THEN 'BEARISH_ENGULFING' END,
        CASE WHEN is_morning_star = 1 THEN 'MORNING_STAR' END,
        CASE WHEN is_evening_star = 1 THEN 'EVENING_STAR' END,
        CASE WHEN is_cup_and_handle = 1 THEN 'CUP_AND_HANDLE' END,
        CASE WHEN is_inverse_cup_handle = 1 THEN 'INVERSE_CUP_HANDLE' END,
        CASE WHEN is_double_top = 1 THEN 'DOUBLE_TOP' END,
        CASE WHEN is_double_bottom = 1 THEN 'DOUBLE_BOTTOM' END,
        CASE WHEN is_head_and_shoulders = 1 THEN 'HEAD_AND_SHOULDERS' END,
        CASE WHEN is_inverse_head_shoulders = 1 THEN 'INVERSE_HEAD_SHOULDERS' END
    ) as patterns_detected,
    
    -- Trading Signal based on patterns
    CASE 
        -- Strong Bullish Signals
        WHEN is_morning_star = 1 OR is_inverse_head_shoulders = 1 OR is_cup_and_handle = 1 
        THEN 'STRONG_BUY'
        WHEN is_bullish_engulfing = 1 OR is_hammer = 1 OR is_double_bottom = 1 
        THEN 'BUY'
        -- Strong Bearish Signals
        WHEN is_evening_star = 1 OR is_head_and_shoulders = 1 OR is_inverse_cup_handle = 1 
        THEN 'STRONG_SELL'
        WHEN is_bearish_engulfing = 1 OR is_shooting_star = 1 OR is_double_top = 1 
        THEN 'SELL'
        -- Neutral/Indecision
        WHEN is_doji = 1 THEN 'NEUTRAL_WAIT'
        ELSE 'NO_PATTERN'
    END as pattern_signal
    
FROM PatternCalculations
WHERE is_doji = 1 OR is_hammer = 1 OR is_shooting_star = 1 
    OR is_bullish_engulfing = 1 OR is_bearish_engulfing = 1
    OR is_morning_star = 1 OR is_evening_star = 1
    OR is_cup_and_handle = 1 OR is_inverse_cup_handle = 1
    OR is_double_top = 1 OR is_double_bottom = 1
    OR is_head_and_shoulders = 1 OR is_inverse_head_shoulders = 1;
GO
-- =====================================================

-- NASDAQ 100 Candlestick Patterns View
-- =====================================================
IF OBJECT_ID('dbo.nasdaq_100_patterns', 'V') IS NOT NULL
    DROP VIEW dbo.nasdaq_100_patterns;
GO

CREATE VIEW dbo.nasdaq_100_patterns AS
WITH PriceData AS (
    SELECT 
        ticker,
        trading_date,
        CAST(open_price AS FLOAT) as open_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        CAST(close_price AS FLOAT) as close_price,
        volume,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as high_20d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as low_20d,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as high_50d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as low_50d,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as sma_20,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma_50,
        LAG(CAST(open_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_open,
        LAG(CAST(high_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_high,
        LAG(CAST(low_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_low,
        LAG(CAST(close_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_close,
        LAG(CAST(close_price AS FLOAT), 2) OVER (PARTITION BY ticker ORDER BY trading_date) as prev2_close,
        LAG(CAST(high_price AS FLOAT), 2) OVER (PARTITION BY ticker ORDER BY trading_date) as prev2_high,
        LAG(CAST(low_price AS FLOAT), 2) OVER (PARTITION BY ticker ORDER BY trading_date) as prev2_low,
        LAG(CAST(open_price AS FLOAT), 2) OVER (PARTITION BY ticker ORDER BY trading_date) as prev2_open
    FROM dbo.nasdaq_100_hist_data
    WHERE close_price IS NOT NULL
),
PatternCalculations AS (
    SELECT 
        ticker,
        trading_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        sma_20,
        sma_50,
        high_20d,
        low_20d,
        high_50d,
        low_50d,
        ABS(close_price - open_price) as body_size,
        (high_price - CASE WHEN close_price > open_price THEN close_price ELSE open_price END) as upper_shadow,
        (CASE WHEN close_price < open_price THEN close_price ELSE open_price END - low_price) as lower_shadow,
        
        CASE WHEN ABS(close_price - open_price) <= (high_price - low_price) * 0.1 THEN 1 ELSE 0 END as is_doji,
        CASE WHEN (CASE WHEN close_price < open_price THEN close_price ELSE open_price END - low_price) > 2 * ABS(close_price - open_price)
                AND (high_price - CASE WHEN close_price > open_price THEN close_price ELSE open_price END) < ABS(close_price - open_price)
                AND close_price < sma_20
            THEN 1 ELSE 0 END as is_hammer,
        CASE WHEN (high_price - CASE WHEN close_price > open_price THEN close_price ELSE open_price END) > 2 * ABS(close_price - open_price)
                AND (CASE WHEN close_price < open_price THEN close_price ELSE open_price END - low_price) < ABS(close_price - open_price)
                AND close_price > sma_20
            THEN 1 ELSE 0 END as is_shooting_star,
        CASE WHEN prev_close IS NOT NULL AND prev_open IS NOT NULL AND prev_close < prev_open AND close_price > open_price 
                AND close_price > prev_open AND open_price < prev_close
            THEN 1 ELSE 0 END as is_bullish_engulfing,
        CASE WHEN prev_close IS NOT NULL AND prev_open IS NOT NULL AND prev_close > prev_open AND close_price < open_price 
                AND close_price < prev_open AND open_price > prev_close
            THEN 1 ELSE 0 END as is_bearish_engulfing,
        CASE WHEN prev2_close IS NOT NULL AND prev_close IS NOT NULL AND prev2_close < prev_open 
                AND ABS(prev_close - prev_open) < (prev2_close - prev_open) * 0.3 
                AND close_price > open_price AND close_price > (prev2_close + prev_open) / 2
            THEN 1 ELSE 0 END as is_morning_star,
        CASE WHEN prev2_close IS NOT NULL AND prev_close IS NOT NULL AND prev2_close > prev_open 
                AND ABS(prev_close - prev_open) < (prev2_close - prev_open) * 0.3 
                AND close_price < open_price AND close_price < (prev2_close + prev_open) / 2
            THEN 1 ELSE 0 END as is_evening_star,
        CASE WHEN close_price >= high_50d * 0.95 AND close_price > low_50d * 1.15 
                AND low_50d > high_50d * 0.80 AND close_price > sma_50
            THEN 1 ELSE 0 END as is_cup_and_handle,
        CASE WHEN close_price <= low_50d * 1.05 AND close_price < high_50d * 0.85 
                AND high_50d < low_50d * 1.20 AND close_price < sma_50
            THEN 1 ELSE 0 END as is_inverse_cup_handle,
        CASE WHEN close_price >= high_20d * 0.98 AND prev_high IS NOT NULL AND prev_high >= high_20d * 0.98 AND close_price < high_20d
            THEN 1 ELSE 0 END as is_double_top,
        CASE WHEN close_price <= low_20d * 1.02 AND prev_low IS NOT NULL AND prev_low <= low_20d * 1.02 
                AND close_price > low_20d AND close_price > open_price
            THEN 1 ELSE 0 END as is_double_bottom,
        CASE WHEN prev2_high IS NOT NULL AND prev_high IS NOT NULL AND prev_high > prev2_high * 1.03 
                AND prev_high > high_price * 1.03 AND ABS(prev2_high - high_price) / prev2_high < 0.05 AND close_price < sma_20
            THEN 1 ELSE 0 END as is_head_and_shoulders,
        CASE WHEN prev2_low IS NOT NULL AND prev_low IS NOT NULL AND prev_low < prev2_low * 0.97 
                AND prev_low < low_price * 0.97 AND ABS(prev2_low - low_price) / prev2_low < 0.05 AND close_price > sma_20
            THEN 1 ELSE 0 END as is_inverse_head_shoulders
    FROM PriceData
)
SELECT 
    ticker,
    trading_date,
    close_price,
    ROUND(sma_20, 2) as ma_20,
    ROUND(sma_50, 2) as ma_50,
    CASE WHEN is_doji = 1 THEN 'DOJI' ELSE NULL END as doji,
    CASE WHEN is_hammer = 1 THEN 'HAMMER' ELSE NULL END as hammer,
    CASE WHEN is_shooting_star = 1 THEN 'SHOOTING_STAR' ELSE NULL END as shooting_star,
    CASE WHEN is_bullish_engulfing = 1 THEN 'BULLISH_ENGULFING' ELSE NULL END as bullish_engulfing,
    CASE WHEN is_bearish_engulfing = 1 THEN 'BEARISH_ENGULFING' ELSE NULL END as bearish_engulfing,
    CASE WHEN is_morning_star = 1 THEN 'MORNING_STAR' ELSE NULL END as morning_star,
    CASE WHEN is_evening_star = 1 THEN 'EVENING_STAR' ELSE NULL END as evening_star,
    CASE WHEN is_cup_and_handle = 1 THEN 'CUP_AND_HANDLE' ELSE NULL END as cup_and_handle,
    CASE WHEN is_inverse_cup_handle = 1 THEN 'INVERSE_CUP_HANDLE' ELSE NULL END as inverse_cup_handle,
    CASE WHEN is_double_top = 1 THEN 'DOUBLE_TOP' ELSE NULL END as double_top,
    CASE WHEN is_double_bottom = 1 THEN 'DOUBLE_BOTTOM' ELSE NULL END as double_bottom,
    CASE WHEN is_head_and_shoulders = 1 THEN 'HEAD_AND_SHOULDERS' ELSE NULL END as head_and_shoulders,
    CASE WHEN is_inverse_head_shoulders = 1 THEN 'INVERSE_HEAD_SHOULDERS' ELSE NULL END as inverse_head_shoulders,
    CONCAT_WS(', ',
        CASE WHEN is_doji = 1 THEN 'DOJI' END,
        CASE WHEN is_hammer = 1 THEN 'HAMMER' END,
        CASE WHEN is_shooting_star = 1 THEN 'SHOOTING_STAR' END,
        CASE WHEN is_bullish_engulfing = 1 THEN 'BULLISH_ENGULFING' END,
        CASE WHEN is_bearish_engulfing = 1 THEN 'BEARISH_ENGULFING' END,
        CASE WHEN is_morning_star = 1 THEN 'MORNING_STAR' END,
        CASE WHEN is_evening_star = 1 THEN 'EVENING_STAR' END,
        CASE WHEN is_cup_and_handle = 1 THEN 'CUP_AND_HANDLE' END,
        CASE WHEN is_inverse_cup_handle = 1 THEN 'INVERSE_CUP_HANDLE' END,
        CASE WHEN is_double_top = 1 THEN 'DOUBLE_TOP' END,
        CASE WHEN is_double_bottom = 1 THEN 'DOUBLE_BOTTOM' END,
        CASE WHEN is_head_and_shoulders = 1 THEN 'HEAD_AND_SHOULDERS' END,
        CASE WHEN is_inverse_head_shoulders = 1 THEN 'INVERSE_HEAD_SHOULDERS' END
    ) as patterns_detected,
    CASE 
        WHEN is_morning_star = 1 OR is_inverse_head_shoulders = 1 OR is_cup_and_handle = 1 THEN 'STRONG_BUY'
        WHEN is_bullish_engulfing = 1 OR is_hammer = 1 OR is_double_bottom = 1 THEN 'BUY'
        WHEN is_evening_star = 1 OR is_head_and_shoulders = 1 OR is_inverse_cup_handle = 1 THEN 'STRONG_SELL'
        WHEN is_bearish_engulfing = 1 OR is_shooting_star = 1 OR is_double_top = 1 THEN 'SELL'
        WHEN is_doji = 1 THEN 'NEUTRAL_WAIT'
        ELSE 'NO_PATTERN'
    END as pattern_signal
FROM PatternCalculations
WHERE is_doji = 1 OR is_hammer = 1 OR is_shooting_star = 1 
    OR is_bullish_engulfing = 1 OR is_bearish_engulfing = 1
    OR is_morning_star = 1 OR is_evening_star = 1
    OR is_cup_and_handle = 1 OR is_inverse_cup_handle = 1
    OR is_double_top = 1 OR is_double_bottom = 1
    OR is_head_and_shoulders = 1 OR is_inverse_head_shoulders = 1;
GO

-- =====================================================
-- Forex Candlestick Patterns View (using 'symbol' column)
-- =====================================================
IF OBJECT_ID('dbo.forex_patterns', 'V') IS NOT NULL
    DROP VIEW dbo.forex_patterns;
GO

CREATE VIEW dbo.forex_patterns AS
WITH PriceData AS (
    SELECT 
        symbol as ticker,
        trading_date,
        CAST(open_price AS FLOAT) as open_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        CAST(close_price AS FLOAT) as close_price,
        volume,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as high_20d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as low_20d,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as high_50d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as low_50d,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as sma_20,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma_50,
        LAG(CAST(open_price AS FLOAT), 1) OVER (PARTITION BY symbol ORDER BY trading_date) as prev_open,
        LAG(CAST(high_price AS FLOAT), 1) OVER (PARTITION BY symbol ORDER BY trading_date) as prev_high,
        LAG(CAST(low_price AS FLOAT), 1) OVER (PARTITION BY symbol ORDER BY trading_date) as prev_low,
        LAG(CAST(close_price AS FLOAT), 1) OVER (PARTITION BY symbol ORDER BY trading_date) as prev_close,
        LAG(CAST(close_price AS FLOAT), 2) OVER (PARTITION BY symbol ORDER BY trading_date) as prev2_close,
        LAG(CAST(high_price AS FLOAT), 2) OVER (PARTITION BY symbol ORDER BY trading_date) as prev2_high,
        LAG(CAST(low_price AS FLOAT), 2) OVER (PARTITION BY symbol ORDER BY trading_date) as prev2_low,
        LAG(CAST(open_price AS FLOAT), 2) OVER (PARTITION BY symbol ORDER BY trading_date) as prev2_open
    FROM dbo.forex_hist_data
    WHERE close_price IS NOT NULL
),
PatternCalculations AS (
    SELECT 
        ticker,
        trading_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        sma_20,
        sma_50,
        high_20d,
        low_20d,
        high_50d,
        low_50d,
        ABS(close_price - open_price) as body_size,
        (high_price - CASE WHEN close_price > open_price THEN close_price ELSE open_price END) as upper_shadow,
        (CASE WHEN close_price < open_price THEN close_price ELSE open_price END - low_price) as lower_shadow,
        
        CASE WHEN ABS(close_price - open_price) <= (high_price - low_price) * 0.1 THEN 1 ELSE 0 END as is_doji,
        CASE WHEN (CASE WHEN close_price < open_price THEN close_price ELSE open_price END - low_price) > 2 * ABS(close_price - open_price)
                AND (high_price - CASE WHEN close_price > open_price THEN close_price ELSE open_price END) < ABS(close_price - open_price)
                AND close_price < sma_20
            THEN 1 ELSE 0 END as is_hammer,
        CASE WHEN (high_price - CASE WHEN close_price > open_price THEN close_price ELSE open_price END) > 2 * ABS(close_price - open_price)
                AND (CASE WHEN close_price < open_price THEN close_price ELSE open_price END - low_price) < ABS(close_price - open_price)
                AND close_price > sma_20
            THEN 1 ELSE 0 END as is_shooting_star,
        CASE WHEN prev_close IS NOT NULL AND prev_open IS NOT NULL AND prev_close < prev_open AND close_price > open_price 
                AND close_price > prev_open AND open_price < prev_close
            THEN 1 ELSE 0 END as is_bullish_engulfing,
        CASE WHEN prev_close IS NOT NULL AND prev_open IS NOT NULL AND prev_close > prev_open AND close_price < open_price 
                AND close_price < prev_open AND open_price > prev_close
            THEN 1 ELSE 0 END as is_bearish_engulfing,
        CASE WHEN prev2_close IS NOT NULL AND prev_close IS NOT NULL AND prev2_close < prev_open 
                AND ABS(prev_close - prev_open) < (prev2_close - prev_open) * 0.3 
                AND close_price > open_price AND close_price > (prev2_close + prev_open) / 2
            THEN 1 ELSE 0 END as is_morning_star,
        CASE WHEN prev2_close IS NOT NULL AND prev_close IS NOT NULL AND prev2_close > prev_open 
                AND ABS(prev_close - prev_open) < (prev2_close - prev_open) * 0.3 
                AND close_price < open_price AND close_price < (prev2_close + prev_open) / 2
            THEN 1 ELSE 0 END as is_evening_star,
        CASE WHEN close_price >= high_50d * 0.95 AND close_price > low_50d * 1.15 
                AND low_50d > high_50d * 0.80 AND close_price > sma_50
            THEN 1 ELSE 0 END as is_cup_and_handle,
        CASE WHEN close_price <= low_50d * 1.05 AND close_price < high_50d * 0.85 
                AND high_50d < low_50d * 1.20 AND close_price < sma_50
            THEN 1 ELSE 0 END as is_inverse_cup_handle,
        CASE WHEN close_price >= high_20d * 0.98 AND prev_high IS NOT NULL AND prev_high >= high_20d * 0.98 AND close_price < high_20d
            THEN 1 ELSE 0 END as is_double_top,
        CASE WHEN close_price <= low_20d * 1.02 AND prev_low IS NOT NULL AND prev_low <= low_20d * 1.02 
                AND close_price > low_20d AND close_price > open_price
            THEN 1 ELSE 0 END as is_double_bottom,
        CASE WHEN prev2_high IS NOT NULL AND prev_high IS NOT NULL AND prev_high > prev2_high * 1.03 
                AND prev_high > high_price * 1.03 AND ABS(prev2_high - high_price) / prev2_high < 0.05 AND close_price < sma_20
            THEN 1 ELSE 0 END as is_head_and_shoulders,
        CASE WHEN prev2_low IS NOT NULL AND prev_low IS NOT NULL AND prev_low < prev2_low * 0.97 
                AND prev_low < low_price * 0.97 AND ABS(prev2_low - low_price) / prev2_low < 0.05 AND close_price > sma_20
            THEN 1 ELSE 0 END as is_inverse_head_shoulders
    FROM PriceData
)
SELECT 
    ticker,
    trading_date,
    close_price,
    ROUND(sma_20, 4) as ma_20,
    ROUND(sma_50, 4) as ma_50,
    CASE WHEN is_doji = 1 THEN 'DOJI' ELSE NULL END as doji,
    CASE WHEN is_hammer = 1 THEN 'HAMMER' ELSE NULL END as hammer,
    CASE WHEN is_shooting_star = 1 THEN 'SHOOTING_STAR' ELSE NULL END as shooting_star,
    CASE WHEN is_bullish_engulfing = 1 THEN 'BULLISH_ENGULFING' ELSE NULL END as bullish_engulfing,
    CASE WHEN is_bearish_engulfing = 1 THEN 'BEARISH_ENGULFING' ELSE NULL END as bearish_engulfing,
    CASE WHEN is_morning_star = 1 THEN 'MORNING_STAR' ELSE NULL END as morning_star,
    CASE WHEN is_evening_star = 1 THEN 'EVENING_STAR' ELSE NULL END as evening_star,
    CASE WHEN is_cup_and_handle = 1 THEN 'CUP_AND_HANDLE' ELSE NULL END as cup_and_handle,
    CASE WHEN is_inverse_cup_handle = 1 THEN 'INVERSE_CUP_HANDLE' ELSE NULL END as inverse_cup_handle,
    CASE WHEN is_double_top = 1 THEN 'DOUBLE_TOP' ELSE NULL END as double_top,
    CASE WHEN is_double_bottom = 1 THEN 'DOUBLE_BOTTOM' ELSE NULL END as double_bottom,
    CASE WHEN is_head_and_shoulders = 1 THEN 'HEAD_AND_SHOULDERS' ELSE NULL END as head_and_shoulders,
    CASE WHEN is_inverse_head_shoulders = 1 THEN 'INVERSE_HEAD_SHOULDERS' ELSE NULL END as inverse_head_shoulders,
    CONCAT_WS(', ',
        CASE WHEN is_doji = 1 THEN 'DOJI' END,
        CASE WHEN is_hammer = 1 THEN 'HAMMER' END,
        CASE WHEN is_shooting_star = 1 THEN 'SHOOTING_STAR' END,
        CASE WHEN is_bullish_engulfing = 1 THEN 'BULLISH_ENGULFING' END,
        CASE WHEN is_bearish_engulfing = 1 THEN 'BEARISH_ENGULFING' END,
        CASE WHEN is_morning_star = 1 THEN 'MORNING_STAR' END,
        CASE WHEN is_evening_star = 1 THEN 'EVENING_STAR' END,
        CASE WHEN is_cup_and_handle = 1 THEN 'CUP_AND_HANDLE' END,
        CASE WHEN is_inverse_cup_handle = 1 THEN 'INVERSE_CUP_HANDLE' END,
        CASE WHEN is_double_top = 1 THEN 'DOUBLE_TOP' END,
        CASE WHEN is_double_bottom = 1 THEN 'DOUBLE_BOTTOM' END,
        CASE WHEN is_head_and_shoulders = 1 THEN 'HEAD_AND_SHOULDERS' END,
        CASE WHEN is_inverse_head_shoulders = 1 THEN 'INVERSE_HEAD_SHOULDERS' END
    ) as patterns_detected,
    CASE 
        WHEN is_morning_star = 1 OR is_inverse_head_shoulders = 1 OR is_cup_and_handle = 1 THEN 'STRONG_BUY'
        WHEN is_bullish_engulfing = 1 OR is_hammer = 1 OR is_double_bottom = 1 THEN 'BUY'
        WHEN is_evening_star = 1 OR is_head_and_shoulders = 1 OR is_inverse_cup_handle = 1 THEN 'STRONG_SELL'
        WHEN is_bearish_engulfing = 1 OR is_shooting_star = 1 OR is_double_top = 1 THEN 'SELL'
        WHEN is_doji = 1 THEN 'NEUTRAL_WAIT'
        ELSE 'NO_PATTERN'
    END as pattern_signal
FROM PatternCalculations
WHERE is_doji = 1 OR is_hammer = 1 OR is_shooting_star = 1 
    OR is_bullish_engulfing = 1 OR is_bearish_engulfing = 1
    OR is_morning_star = 1 OR is_evening_star = 1
    OR is_cup_and_handle = 1 OR is_inverse_cup_handle = 1
    OR is_double_top = 1 OR is_double_bottom = 1
    OR is_head_and_shoulders = 1 OR is_inverse_head_shoulders = 1;
GO

-- =====================================================
-- Grant SELECT permissions
-- =====================================================
GRANT SELECT ON dbo.nse_500_patterns TO PUBLIC;
GRANT SELECT ON dbo.nasdaq_100_patterns TO PUBLIC;
GRANT SELECT ON dbo.forex_patterns TO PUBLIC;
GO

-- =====================================================
-- Test queries to verify the Pattern views
-- =====================================================

-- Test NSE 500 Patterns
SELECT TOP 20
    ticker, 
    trading_date, 
    close_price,
    patterns_detected,
    pattern_signal
FROM dbo.nse_500_patterns
WHERE patterns_detected IS NOT NULL AND patterns_detected != ''
ORDER BY trading_date DESC, ticker;

-- Test NASDAQ 100 Patterns
SELECT TOP 20
    ticker, 
    trading_date, 
    close_price,
    patterns_detected,
    pattern_signal
FROM dbo.nasdaq_100_patterns
WHERE patterns_detected IS NOT NULL AND patterns_detected != ''
ORDER BY trading_date DESC, ticker;

-- Test Forex Patterns
SELECT TOP 20
    ticker, 
    trading_date, 
    close_price,
    patterns_detected,
    pattern_signal
FROM dbo.forex_patterns
WHERE patterns_detected IS NOT NULL AND patterns_detected != ''
ORDER BY trading_date DESC, ticker;

-- Pattern frequency analysis
SELECT 
    'NSE 500' as market,
    SUM(CASE WHEN cup_and_handle IS NOT NULL THEN 1 ELSE 0 END) as cup_handle_count,
    SUM(CASE WHEN head_and_shoulders IS NOT NULL THEN 1 ELSE 0 END) as head_shoulders_count,
    SUM(CASE WHEN double_top IS NOT NULL THEN 1 ELSE 0 END) as double_top_count,
    SUM(CASE WHEN double_bottom IS NOT NULL THEN 1 ELSE 0 END) as double_bottom_count
FROM dbo.nse_500_patterns;

PRINT 'Candlestick Pattern views created successfully!';
GO
