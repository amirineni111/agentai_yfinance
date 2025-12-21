-- =====================================================
-- Fibonacci Retracement and Extension SQL View Definitions
-- =====================================================
-- This script creates Fibonacci indicator views for NSE 500, NASDAQ 100, and Forex
-- Using Fibonacci retracement and extension levels
-- =====================================================

USE stockdata_db;
GO

-- =====================================================
-- NSE 500 Fibonacci Indicator View
-- =====================================================
IF OBJECT_ID('dbo.nse_500_fibonacci', 'V') IS NOT NULL
    DROP VIEW dbo.nse_500_fibonacci;
GO

CREATE VIEW dbo.nse_500_fibonacci AS
WITH PriceData AS (
    SELECT 
        ticker,
        trading_date,
        CAST(close_price AS FLOAT) as close_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        -- 20-day swing high and low
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as swing_high_20,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as swing_low_20,
        -- 50-day swing high and low
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as swing_high_50,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as swing_low_50,
        -- 100-day swing high and low for longer trends
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 100 PRECEDING AND CURRENT ROW) as swing_high_100,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 100 PRECEDING AND CURRENT ROW) as swing_low_100
    FROM dbo.nse_500_hist_data
    WHERE close_price IS NOT NULL
),
FibCalculations AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        swing_high_20,
        swing_low_20,
        swing_high_50,
        swing_low_50,
        swing_high_100,
        swing_low_100,
        -- Calculate range for 20-day Fibonacci
        (swing_high_20 - swing_low_20) as range_20,
        -- Calculate range for 50-day Fibonacci
        (swing_high_50 - swing_low_50) as range_50,
        -- Calculate range for 100-day Fibonacci
        (swing_high_100 - swing_low_100) as range_100,
        
        -- 20-Day Fibonacci Retracement Levels (from swing low)
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.236) as fib_20d_level_236,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.382) as fib_20d_level_382,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.500) as fib_20d_level_500,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.618) as fib_20d_level_618,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.786) as fib_20d_level_786,
        
        -- 50-Day Fibonacci Retracement Levels
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.236) as fib_50d_level_236,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.382) as fib_50d_level_382,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.500) as fib_50d_level_500,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.618) as fib_50d_level_618,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.786) as fib_50d_level_786,
        
        -- 100-Day Fibonacci Retracement Levels
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.236) as fib_100d_level_236,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.382) as fib_100d_level_382,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.500) as fib_100d_level_500,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.618) as fib_100d_level_618,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.786) as fib_100d_level_786,
        
        -- Fibonacci Extension Levels (for targets)
        swing_high_20 + ((swing_high_20 - swing_low_20) * 0.272) as fib_20d_ext_1272,
        swing_high_20 + ((swing_high_20 - swing_low_20) * 0.618) as fib_20d_ext_1618,
        swing_high_20 + ((swing_high_20 - swing_low_20) * 1.000) as fib_20d_ext_2000,
        
        swing_high_50 + ((swing_high_50 - swing_low_50) * 0.272) as fib_50d_ext_1272,
        swing_high_50 + ((swing_high_50 - swing_low_50) * 0.618) as fib_50d_ext_1618,
        swing_high_50 + ((swing_high_50 - swing_low_50) * 1.000) as fib_50d_ext_2000
    FROM PriceData
)
SELECT 
    ticker,
    trading_date,
    close_price,
    
    -- 20-Day Swing Points
    ROUND(swing_high_20, 2) as swing_high_20d,
    ROUND(swing_low_20, 2) as swing_low_20d,
    
    -- 20-Day Fibonacci Levels
    ROUND(fib_20d_level_236, 2) as fib_20d_0236,
    ROUND(fib_20d_level_382, 2) as fib_20d_0382,
    ROUND(fib_20d_level_500, 2) as fib_20d_0500,
    ROUND(fib_20d_level_618, 2) as fib_20d_0618,
    ROUND(fib_20d_level_786, 2) as fib_20d_0786,
    
    -- 50-Day Swing Points
    ROUND(swing_high_50, 2) as swing_high_50d,
    ROUND(swing_low_50, 2) as swing_low_50d,
    
    -- 50-Day Fibonacci Levels
    ROUND(fib_50d_level_236, 2) as fib_50d_0236,
    ROUND(fib_50d_level_382, 2) as fib_50d_0382,
    ROUND(fib_50d_level_500, 2) as fib_50d_0500,
    ROUND(fib_50d_level_618, 2) as fib_50d_0618,
    ROUND(fib_50d_level_786, 2) as fib_50d_0786,
    
    -- 100-Day Fibonacci Levels
    ROUND(fib_100d_level_236, 2) as fib_100d_0236,
    ROUND(fib_100d_level_382, 2) as fib_100d_0382,
    ROUND(fib_100d_level_500, 2) as fib_100d_0500,
    ROUND(fib_100d_level_618, 2) as fib_100d_0618,
    ROUND(fib_100d_level_786, 2) as fib_100d_0786,
    
    -- Extension Levels (Targets)
    ROUND(fib_20d_ext_1272, 2) as fib_20d_ext_1272,
    ROUND(fib_20d_ext_1618, 2) as fib_20d_ext_1618,
    ROUND(fib_20d_ext_2000, 2) as fib_20d_ext_2000,
    
    -- Current Position relative to 50-day Fibonacci levels
    CASE 
        WHEN close_price <= fib_50d_level_236 THEN 'BELOW_FIB_236'
        WHEN close_price <= fib_50d_level_382 THEN 'AT_FIB_382'
        WHEN close_price <= fib_50d_level_500 THEN 'AT_FIB_500'
        WHEN close_price <= fib_50d_level_618 THEN 'AT_FIB_618'
        WHEN close_price <= fib_50d_level_786 THEN 'AT_FIB_786'
        ELSE 'ABOVE_FIB_786'
    END as fib_position,
    
    -- Trading Signal based on Fibonacci
    CASE 
        -- Strong buy at deep retracement
        WHEN close_price BETWEEN (fib_50d_level_618 * 0.98) AND (fib_50d_level_618 * 1.02) THEN 'STRONG_BUY_FIB_618'
        WHEN close_price BETWEEN (fib_50d_level_786 * 0.98) AND (fib_50d_level_786 * 1.02) THEN 'STRONG_BUY_FIB_786'
        -- Buy at golden ratio
        WHEN close_price BETWEEN (fib_50d_level_500 * 0.98) AND (fib_50d_level_500 * 1.02) THEN 'BUY_FIB_500'
        WHEN close_price BETWEEN (fib_50d_level_382 * 0.98) AND (fib_50d_level_382 * 1.02) THEN 'BUY_FIB_382'
        -- Sell at shallow retracement
        WHEN close_price BETWEEN (fib_50d_level_236 * 0.98) AND (fib_50d_level_236 * 1.02) THEN 'SELL_FIB_236'
        -- Hold in between levels
        ELSE 'NEUTRAL'
    END as fib_trade_signal,
    
    -- Distance to nearest Fibonacci level (%)
    ROUND(
        CASE 
            WHEN ABS(close_price - fib_50d_level_618) < ABS(close_price - fib_50d_level_500) 
                AND ABS(close_price - fib_50d_level_618) < ABS(close_price - fib_50d_level_382)
                AND ABS(close_price - fib_50d_level_618) < ABS(close_price - fib_50d_level_236)
            THEN ((close_price - fib_50d_level_618) / fib_50d_level_618 * 100)
            WHEN ABS(close_price - fib_50d_level_500) < ABS(close_price - fib_50d_level_382)
                AND ABS(close_price - fib_50d_level_500) < ABS(close_price - fib_50d_level_236)
            THEN ((close_price - fib_50d_level_500) / fib_50d_level_500 * 100)
            WHEN ABS(close_price - fib_50d_level_382) < ABS(close_price - fib_50d_level_236)
            THEN ((close_price - fib_50d_level_382) / fib_50d_level_382 * 100)
            ELSE ((close_price - fib_50d_level_236) / fib_50d_level_236 * 100)
        END, 
    2) as distance_to_nearest_fib_pct
FROM FibCalculations;
GO

-- =====================================================
-- NASDAQ 100 Fibonacci Indicator View
-- =====================================================
IF OBJECT_ID('dbo.nasdaq_100_fibonacci', 'V') IS NOT NULL
    DROP VIEW dbo.nasdaq_100_fibonacci;
GO

CREATE VIEW dbo.nasdaq_100_fibonacci AS
WITH PriceData AS (
    SELECT 
        ticker,
        trading_date,
        CAST(close_price AS FLOAT) as close_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as swing_high_20,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as swing_low_20,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as swing_high_50,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as swing_low_50,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 100 PRECEDING AND CURRENT ROW) as swing_high_100,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 100 PRECEDING AND CURRENT ROW) as swing_low_100
    FROM dbo.nasdaq_100_hist_data
    WHERE close_price IS NOT NULL
),
FibCalculations AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        swing_high_20,
        swing_low_20,
        swing_high_50,
        swing_low_50,
        swing_high_100,
        swing_low_100,
        (swing_high_20 - swing_low_20) as range_20,
        (swing_high_50 - swing_low_50) as range_50,
        (swing_high_100 - swing_low_100) as range_100,
        
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.236) as fib_20d_level_236,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.382) as fib_20d_level_382,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.500) as fib_20d_level_500,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.618) as fib_20d_level_618,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.786) as fib_20d_level_786,
        
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.236) as fib_50d_level_236,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.382) as fib_50d_level_382,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.500) as fib_50d_level_500,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.618) as fib_50d_level_618,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.786) as fib_50d_level_786,
        
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.236) as fib_100d_level_236,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.382) as fib_100d_level_382,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.500) as fib_100d_level_500,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.618) as fib_100d_level_618,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.786) as fib_100d_level_786,
        
        swing_high_20 + ((swing_high_20 - swing_low_20) * 0.272) as fib_20d_ext_1272,
        swing_high_20 + ((swing_high_20 - swing_low_20) * 0.618) as fib_20d_ext_1618,
        swing_high_20 + ((swing_high_20 - swing_low_20) * 1.000) as fib_20d_ext_2000,
        
        swing_high_50 + ((swing_high_50 - swing_low_50) * 0.272) as fib_50d_ext_1272,
        swing_high_50 + ((swing_high_50 - swing_low_50) * 0.618) as fib_50d_ext_1618,
        swing_high_50 + ((swing_high_50 - swing_low_50) * 1.000) as fib_50d_ext_2000
    FROM PriceData
)
SELECT 
    ticker,
    trading_date,
    close_price,
    ROUND(swing_high_20, 2) as swing_high_20d,
    ROUND(swing_low_20, 2) as swing_low_20d,
    ROUND(fib_20d_level_236, 2) as fib_20d_0236,
    ROUND(fib_20d_level_382, 2) as fib_20d_0382,
    ROUND(fib_20d_level_500, 2) as fib_20d_0500,
    ROUND(fib_20d_level_618, 2) as fib_20d_0618,
    ROUND(fib_20d_level_786, 2) as fib_20d_0786,
    ROUND(swing_high_50, 2) as swing_high_50d,
    ROUND(swing_low_50, 2) as swing_low_50d,
    ROUND(fib_50d_level_236, 2) as fib_50d_0236,
    ROUND(fib_50d_level_382, 2) as fib_50d_0382,
    ROUND(fib_50d_level_500, 2) as fib_50d_0500,
    ROUND(fib_50d_level_618, 2) as fib_50d_0618,
    ROUND(fib_50d_level_786, 2) as fib_50d_0786,
    ROUND(fib_100d_level_236, 2) as fib_100d_0236,
    ROUND(fib_100d_level_382, 2) as fib_100d_0382,
    ROUND(fib_100d_level_500, 2) as fib_100d_0500,
    ROUND(fib_100d_level_618, 2) as fib_100d_0618,
    ROUND(fib_100d_level_786, 2) as fib_100d_0786,
    ROUND(fib_20d_ext_1272, 2) as fib_20d_ext_1272,
    ROUND(fib_20d_ext_1618, 2) as fib_20d_ext_1618,
    ROUND(fib_20d_ext_2000, 2) as fib_20d_ext_2000,
    CASE 
        WHEN close_price <= fib_50d_level_236 THEN 'BELOW_FIB_236'
        WHEN close_price <= fib_50d_level_382 THEN 'AT_FIB_382'
        WHEN close_price <= fib_50d_level_500 THEN 'AT_FIB_500'
        WHEN close_price <= fib_50d_level_618 THEN 'AT_FIB_618'
        WHEN close_price <= fib_50d_level_786 THEN 'AT_FIB_786'
        ELSE 'ABOVE_FIB_786'
    END as fib_position,
    CASE 
        WHEN close_price BETWEEN (fib_50d_level_618 * 0.98) AND (fib_50d_level_618 * 1.02) THEN 'STRONG_BUY_FIB_618'
        WHEN close_price BETWEEN (fib_50d_level_786 * 0.98) AND (fib_50d_level_786 * 1.02) THEN 'STRONG_BUY_FIB_786'
        WHEN close_price BETWEEN (fib_50d_level_500 * 0.98) AND (fib_50d_level_500 * 1.02) THEN 'BUY_FIB_500'
        WHEN close_price BETWEEN (fib_50d_level_382 * 0.98) AND (fib_50d_level_382 * 1.02) THEN 'BUY_FIB_382'
        WHEN close_price BETWEEN (fib_50d_level_236 * 0.98) AND (fib_50d_level_236 * 1.02) THEN 'SELL_FIB_236'
        ELSE 'NEUTRAL'
    END as fib_trade_signal,
    ROUND(
        CASE 
            WHEN ABS(close_price - fib_50d_level_618) < ABS(close_price - fib_50d_level_500) 
                AND ABS(close_price - fib_50d_level_618) < ABS(close_price - fib_50d_level_382)
                AND ABS(close_price - fib_50d_level_618) < ABS(close_price - fib_50d_level_236)
            THEN ((close_price - fib_50d_level_618) / fib_50d_level_618 * 100)
            WHEN ABS(close_price - fib_50d_level_500) < ABS(close_price - fib_50d_level_382)
                AND ABS(close_price - fib_50d_level_500) < ABS(close_price - fib_50d_level_236)
            THEN ((close_price - fib_50d_level_500) / fib_50d_level_500 * 100)
            WHEN ABS(close_price - fib_50d_level_382) < ABS(close_price - fib_50d_level_236)
            THEN ((close_price - fib_50d_level_382) / fib_50d_level_382 * 100)
            ELSE ((close_price - fib_50d_level_236) / fib_50d_level_236 * 100)
        END, 
    2) as distance_to_nearest_fib_pct
FROM FibCalculations;
GO

-- =====================================================
-- Forex Fibonacci Indicator View (using 'symbol' column)
-- =====================================================
IF OBJECT_ID('dbo.forex_fibonacci', 'V') IS NOT NULL
    DROP VIEW dbo.forex_fibonacci;
GO

CREATE VIEW dbo.forex_fibonacci AS
WITH PriceData AS (
    SELECT 
        symbol as ticker,  -- Use symbol column for Forex
        trading_date,
        CAST(close_price AS FLOAT) as close_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as swing_high_20,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as swing_low_20,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as swing_high_50,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as swing_low_50,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 100 PRECEDING AND CURRENT ROW) as swing_high_100,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 100 PRECEDING AND CURRENT ROW) as swing_low_100
    FROM dbo.forex_hist_data
    WHERE close_price IS NOT NULL
),
FibCalculations AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        swing_high_20,
        swing_low_20,
        swing_high_50,
        swing_low_50,
        swing_high_100,
        swing_low_100,
        (swing_high_20 - swing_low_20) as range_20,
        (swing_high_50 - swing_low_50) as range_50,
        (swing_high_100 - swing_low_100) as range_100,
        
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.236) as fib_20d_level_236,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.382) as fib_20d_level_382,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.500) as fib_20d_level_500,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.618) as fib_20d_level_618,
        swing_low_20 + ((swing_high_20 - swing_low_20) * 0.786) as fib_20d_level_786,
        
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.236) as fib_50d_level_236,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.382) as fib_50d_level_382,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.500) as fib_50d_level_500,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.618) as fib_50d_level_618,
        swing_low_50 + ((swing_high_50 - swing_low_50) * 0.786) as fib_50d_level_786,
        
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.236) as fib_100d_level_236,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.382) as fib_100d_level_382,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.500) as fib_100d_level_500,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.618) as fib_100d_level_618,
        swing_low_100 + ((swing_high_100 - swing_low_100) * 0.786) as fib_100d_level_786,
        
        swing_high_20 + ((swing_high_20 - swing_low_20) * 0.272) as fib_20d_ext_1272,
        swing_high_20 + ((swing_high_20 - swing_low_20) * 0.618) as fib_20d_ext_1618,
        swing_high_20 + ((swing_high_20 - swing_low_20) * 1.000) as fib_20d_ext_2000,
        
        swing_high_50 + ((swing_high_50 - swing_low_50) * 0.272) as fib_50d_ext_1272,
        swing_high_50 + ((swing_high_50 - swing_low_50) * 0.618) as fib_50d_ext_1618,
        swing_high_50 + ((swing_high_50 - swing_low_50) * 1.000) as fib_50d_ext_2000
    FROM PriceData
)
SELECT 
    ticker,
    trading_date,
    close_price,
    ROUND(swing_high_20, 4) as swing_high_20d,
    ROUND(swing_low_20, 4) as swing_low_20d,
    ROUND(fib_20d_level_236, 4) as fib_20d_0236,
    ROUND(fib_20d_level_382, 4) as fib_20d_0382,
    ROUND(fib_20d_level_500, 4) as fib_20d_0500,
    ROUND(fib_20d_level_618, 4) as fib_20d_0618,
    ROUND(fib_20d_level_786, 4) as fib_20d_0786,
    ROUND(swing_high_50, 4) as swing_high_50d,
    ROUND(swing_low_50, 4) as swing_low_50d,
    ROUND(fib_50d_level_236, 4) as fib_50d_0236,
    ROUND(fib_50d_level_382, 4) as fib_50d_0382,
    ROUND(fib_50d_level_500, 4) as fib_50d_0500,
    ROUND(fib_50d_level_618, 4) as fib_50d_0618,
    ROUND(fib_50d_level_786, 4) as fib_50d_0786,
    ROUND(fib_100d_level_236, 4) as fib_100d_0236,
    ROUND(fib_100d_level_382, 4) as fib_100d_0382,
    ROUND(fib_100d_level_500, 4) as fib_100d_0500,
    ROUND(fib_100d_level_618, 4) as fib_100d_0618,
    ROUND(fib_100d_level_786, 4) as fib_100d_0786,
    ROUND(fib_20d_ext_1272, 4) as fib_20d_ext_1272,
    ROUND(fib_20d_ext_1618, 4) as fib_20d_ext_1618,
    ROUND(fib_20d_ext_2000, 4) as fib_20d_ext_2000,
    CASE 
        WHEN close_price <= fib_50d_level_236 THEN 'BELOW_FIB_236'
        WHEN close_price <= fib_50d_level_382 THEN 'AT_FIB_382'
        WHEN close_price <= fib_50d_level_500 THEN 'AT_FIB_500'
        WHEN close_price <= fib_50d_level_618 THEN 'AT_FIB_618'
        WHEN close_price <= fib_50d_level_786 THEN 'AT_FIB_786'
        ELSE 'ABOVE_FIB_786'
    END as fib_position,
    CASE 
        WHEN close_price BETWEEN (fib_50d_level_618 * 0.98) AND (fib_50d_level_618 * 1.02) THEN 'STRONG_BUY_FIB_618'
        WHEN close_price BETWEEN (fib_50d_level_786 * 0.98) AND (fib_50d_level_786 * 1.02) THEN 'STRONG_BUY_FIB_786'
        WHEN close_price BETWEEN (fib_50d_level_500 * 0.98) AND (fib_50d_level_500 * 1.02) THEN 'BUY_FIB_500'
        WHEN close_price BETWEEN (fib_50d_level_382 * 0.98) AND (fib_50d_level_382 * 1.02) THEN 'BUY_FIB_382'
        WHEN close_price BETWEEN (fib_50d_level_236 * 0.98) AND (fib_50d_level_236 * 1.02) THEN 'SELL_FIB_236'
        ELSE 'NEUTRAL'
    END as fib_trade_signal,
    ROUND(
        CASE 
            WHEN ABS(close_price - fib_50d_level_618) < ABS(close_price - fib_50d_level_500) 
                AND ABS(close_price - fib_50d_level_618) < ABS(close_price - fib_50d_level_382)
                AND ABS(close_price - fib_50d_level_618) < ABS(close_price - fib_50d_level_236)
            THEN ((close_price - fib_50d_level_618) / fib_50d_level_618 * 100)
            WHEN ABS(close_price - fib_50d_level_500) < ABS(close_price - fib_50d_level_382)
                AND ABS(close_price - fib_50d_level_500) < ABS(close_price - fib_50d_level_236)
            THEN ((close_price - fib_50d_level_500) / fib_50d_level_500 * 100)
            WHEN ABS(close_price - fib_50d_level_382) < ABS(close_price - fib_50d_level_236)
            THEN ((close_price - fib_50d_level_382) / fib_50d_level_382 * 100)
            ELSE ((close_price - fib_50d_level_236) / fib_50d_level_236 * 100)
        END, 
    2) as distance_to_nearest_fib_pct
FROM FibCalculations;
GO

-- =====================================================
-- Grant SELECT permissions
-- =====================================================
GRANT SELECT ON dbo.nse_500_fibonacci TO PUBLIC;
GRANT SELECT ON dbo.nasdaq_100_fibonacci TO PUBLIC;
GRANT SELECT ON dbo.forex_fibonacci TO PUBLIC;
GO

-- =====================================================
-- Test queries to verify the Fibonacci views
-- =====================================================

-- Test NSE 500 Fibonacci
SELECT TOP 10 
    ticker, 
    trading_date, 
    close_price,
    swing_high_50d,
    swing_low_50d,
    fib_50d_0618,
    fib_50d_0500,
    fib_50d_0382,
    fib_position,
    fib_trade_signal
FROM dbo.nse_500_fibonacci
ORDER BY trading_date DESC, ticker;

-- Test NASDAQ 100 Fibonacci
SELECT TOP 10 
    ticker, 
    trading_date, 
    close_price,
    swing_high_50d,
    swing_low_50d,
    fib_50d_0618,
    fib_50d_0500,
    fib_50d_0382,
    fib_position,
    fib_trade_signal
FROM dbo.nasdaq_100_fibonacci
ORDER BY trading_date DESC, ticker;

-- Test Forex Fibonacci
SELECT TOP 10 
    ticker, 
    trading_date, 
    close_price,
    swing_high_50d,
    swing_low_50d,
    fib_50d_0618,
    fib_50d_0500,
    fib_50d_0382,
    fib_position,
    fib_trade_signal
FROM dbo.forex_fibonacci
ORDER BY trading_date DESC, ticker;

PRINT 'Fibonacci views created successfully!';
GO
