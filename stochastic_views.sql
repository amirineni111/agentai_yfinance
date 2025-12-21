-- =====================================================
-- Stochastic Oscillator SQL View Definitions
-- =====================================================
-- This script creates Stochastic Oscillator views for NSE 500, NASDAQ 100, and Forex
-- Using %K and %D lines with multiple timeframes (5-day, 14-day, 21-day)
-- =====================================================

USE stockdata_db;
GO

-- =====================================================
-- NSE 500 Stochastic Oscillator View
-- =====================================================
IF OBJECT_ID('dbo.nse_500_stochastic', 'V') IS NOT NULL
    DROP VIEW dbo.nse_500_stochastic;
GO

CREATE VIEW dbo.nse_500_stochastic AS
WITH PriceData AS (
    SELECT 
        ticker,
        trading_date,
        CAST(close_price AS FLOAT) as close_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        -- 5-day high and low
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) as high_5d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) as low_5d,
        -- 14-day high and low (standard period)
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as high_14d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as low_14d,
        -- 21-day high and low
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as high_21d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as low_21d
    FROM dbo.nse_500_hist_data
    WHERE close_price IS NOT NULL
),
StochasticK AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        high_5d,
        low_5d,
        high_14d,
        low_14d,
        high_21d,
        low_21d,
        -- Calculate %K for different periods
        -- 5-day %K
        CASE 
            WHEN (high_5d - low_5d) > 0 
            THEN ((close_price - low_5d) / (high_5d - low_5d)) * 100.0
            ELSE 50.0
        END as stoch_k_5d,
        -- 14-day %K (standard)
        CASE 
            WHEN (high_14d - low_14d) > 0 
            THEN ((close_price - low_14d) / (high_14d - low_14d)) * 100.0
            ELSE 50.0
        END as stoch_k_14d,
        -- 21-day %K
        CASE 
            WHEN (high_21d - low_21d) > 0 
            THEN ((close_price - low_21d) / (high_21d - low_21d)) * 100.0
            ELSE 50.0
        END as stoch_k_21d
    FROM PriceData
),
StochasticD AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        stoch_k_5d,
        stoch_k_14d,
        stoch_k_21d,
        -- Calculate %D (3-period SMA of %K)
        AVG(stoch_k_5d) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as stoch_d_5d,
        AVG(stoch_k_14d) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as stoch_d_14d,
        AVG(stoch_k_21d) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as stoch_d_21d
    FROM StochasticK
),
StochasticLags AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        stoch_k_5d,
        stoch_k_14d,
        stoch_k_21d,
        stoch_d_5d,
        stoch_d_14d,
        stoch_d_21d,
        -- Previous %K and %D values for crossover detection
        LAG(stoch_k_14d, 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_k_14d,
        LAG(stoch_d_14d, 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_d_14d
    FROM StochasticD
)
SELECT 
    ticker,
    trading_date,
    close_price,
    
    -- 5-Day Stochastic
    ROUND(stoch_k_5d, 2) as stoch_5d_k,
    ROUND(stoch_d_5d, 2) as stoch_5d_d,
    
    -- 14-Day Stochastic (Standard)
    ROUND(stoch_k_14d, 2) as stoch_14d_k,
    ROUND(stoch_d_14d, 2) as stoch_14d_d,
    
    -- 21-Day Stochastic
    ROUND(stoch_k_21d, 2) as stoch_21d_k,
    ROUND(stoch_d_21d, 2) as stoch_21d_d,
    
    -- Overbought/Oversold Status (14-day standard)
    CASE 
        WHEN stoch_k_14d >= 80 THEN 'OVERBOUGHT'
        WHEN stoch_k_14d <= 20 THEN 'OVERSOLD'
        WHEN stoch_k_14d > 50 THEN 'BULLISH'
        WHEN stoch_k_14d < 50 THEN 'BEARISH'
        ELSE 'NEUTRAL'
    END as stoch_status,
    
    -- Crossover Detection (14-day)
    CASE 
        -- Bullish crossover: %K crosses above %D
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d <= prev_d_14d 
            AND stoch_k_14d > stoch_d_14d 
        THEN 'BULLISH_CROSS'
        -- Bearish crossover: %K crosses below %D
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d >= prev_d_14d 
            AND stoch_k_14d < stoch_d_14d 
        THEN 'BEARISH_CROSS'
        -- %K above %D (bullish)
        WHEN stoch_k_14d > stoch_d_14d 
        THEN 'K_ABOVE_D'
        -- %K below %D (bearish)
        WHEN stoch_k_14d < stoch_d_14d 
        THEN 'K_BELOW_D'
        ELSE 'NEUTRAL'
    END as stoch_crossover,
    
    -- Trading Signal based on Stochastic
    CASE 
        -- Strong buy: Oversold with bullish crossover
        WHEN stoch_k_14d <= 20 
            AND prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d <= prev_d_14d 
            AND stoch_k_14d > stoch_d_14d 
        THEN 'STRONG_BUY_OVERSOLD_CROSS'
        -- Buy: Oversold
        WHEN stoch_k_14d <= 20 THEN 'BUY_OVERSOLD'
        -- Bullish crossover
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d <= prev_d_14d 
            AND stoch_k_14d > stoch_d_14d 
            AND stoch_k_14d < 80
        THEN 'BUY_BULLISH_CROSS'
        -- Strong sell: Overbought with bearish crossover
        WHEN stoch_k_14d >= 80 
            AND prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d >= prev_d_14d 
            AND stoch_k_14d < stoch_d_14d 
        THEN 'STRONG_SELL_OVERBOUGHT_CROSS'
        -- Sell: Overbought
        WHEN stoch_k_14d >= 80 THEN 'SELL_OVERBOUGHT'
        -- Bearish crossover
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d >= prev_d_14d 
            AND stoch_k_14d < stoch_d_14d 
            AND stoch_k_14d > 20
        THEN 'SELL_BEARISH_CROSS'
        -- Hold
        ELSE 'NEUTRAL'
    END as stoch_trade_signal,
    
    -- Distance from extreme zones
    CASE 
        WHEN stoch_k_14d >= 80 THEN ROUND(stoch_k_14d - 80, 2)
        WHEN stoch_k_14d <= 20 THEN ROUND(20 - stoch_k_14d, 2)
        ELSE 0
    END as extreme_zone_distance,
    
    -- Momentum strength (difference between %K and %D)
    ROUND(stoch_k_14d - stoch_d_14d, 2) as momentum_strength
FROM StochasticLags;
GO

-- =====================================================
-- NASDAQ 100 Stochastic Oscillator View
-- =====================================================
IF OBJECT_ID('dbo.nasdaq_100_stochastic', 'V') IS NOT NULL
    DROP VIEW dbo.nasdaq_100_stochastic;
GO

CREATE VIEW dbo.nasdaq_100_stochastic AS
WITH PriceData AS (
    SELECT 
        ticker,
        trading_date,
        CAST(close_price AS FLOAT) as close_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) as high_5d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) as low_5d,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as high_14d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as low_14d,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as high_21d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as low_21d
    FROM dbo.nasdaq_100_hist_data
    WHERE close_price IS NOT NULL
),
StochasticK AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        high_5d,
        low_5d,
        high_14d,
        low_14d,
        high_21d,
        low_21d,
        CASE 
            WHEN (high_5d - low_5d) > 0 
            THEN ((close_price - low_5d) / (high_5d - low_5d)) * 100.0
            ELSE 50.0
        END as stoch_k_5d,
        CASE 
            WHEN (high_14d - low_14d) > 0 
            THEN ((close_price - low_14d) / (high_14d - low_14d)) * 100.0
            ELSE 50.0
        END as stoch_k_14d,
        CASE 
            WHEN (high_21d - low_21d) > 0 
            THEN ((close_price - low_21d) / (high_21d - low_21d)) * 100.0
            ELSE 50.0
        END as stoch_k_21d
    FROM PriceData
),
StochasticD AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        stoch_k_5d,
        stoch_k_14d,
        stoch_k_21d,
        AVG(stoch_k_5d) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as stoch_d_5d,
        AVG(stoch_k_14d) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as stoch_d_14d,
        AVG(stoch_k_21d) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as stoch_d_21d
    FROM StochasticK
),
StochasticLags AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        stoch_k_5d,
        stoch_k_14d,
        stoch_k_21d,
        stoch_d_5d,
        stoch_d_14d,
        stoch_d_21d,
        LAG(stoch_k_14d, 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_k_14d,
        LAG(stoch_d_14d, 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_d_14d
    FROM StochasticD
)
SELECT 
    ticker,
    trading_date,
    close_price,
    ROUND(stoch_k_5d, 2) as stoch_5d_k,
    ROUND(stoch_d_5d, 2) as stoch_5d_d,
    ROUND(stoch_k_14d, 2) as stoch_14d_k,
    ROUND(stoch_d_14d, 2) as stoch_14d_d,
    ROUND(stoch_k_21d, 2) as stoch_21d_k,
    ROUND(stoch_d_21d, 2) as stoch_21d_d,
    CASE 
        WHEN stoch_k_14d >= 80 THEN 'OVERBOUGHT'
        WHEN stoch_k_14d <= 20 THEN 'OVERSOLD'
        WHEN stoch_k_14d > 50 THEN 'BULLISH'
        WHEN stoch_k_14d < 50 THEN 'BEARISH'
        ELSE 'NEUTRAL'
    END as stoch_status,
    CASE 
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d <= prev_d_14d 
            AND stoch_k_14d > stoch_d_14d 
        THEN 'BULLISH_CROSS'
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d >= prev_d_14d 
            AND stoch_k_14d < stoch_d_14d 
        THEN 'BEARISH_CROSS'
        WHEN stoch_k_14d > stoch_d_14d 
        THEN 'K_ABOVE_D'
        WHEN stoch_k_14d < stoch_d_14d 
        THEN 'K_BELOW_D'
        ELSE 'NEUTRAL'
    END as stoch_crossover,
    CASE 
        WHEN stoch_k_14d <= 20 
            AND prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d <= prev_d_14d 
            AND stoch_k_14d > stoch_d_14d 
        THEN 'STRONG_BUY_OVERSOLD_CROSS'
        WHEN stoch_k_14d <= 20 THEN 'BUY_OVERSOLD'
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d <= prev_d_14d 
            AND stoch_k_14d > stoch_d_14d 
            AND stoch_k_14d < 80
        THEN 'BUY_BULLISH_CROSS'
        WHEN stoch_k_14d >= 80 
            AND prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d >= prev_d_14d 
            AND stoch_k_14d < stoch_d_14d 
        THEN 'STRONG_SELL_OVERBOUGHT_CROSS'
        WHEN stoch_k_14d >= 80 THEN 'SELL_OVERBOUGHT'
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d >= prev_d_14d 
            AND stoch_k_14d < stoch_d_14d 
            AND stoch_k_14d > 20
        THEN 'SELL_BEARISH_CROSS'
        ELSE 'NEUTRAL'
    END as stoch_trade_signal,
    CASE 
        WHEN stoch_k_14d >= 80 THEN ROUND(stoch_k_14d - 80, 2)
        WHEN stoch_k_14d <= 20 THEN ROUND(20 - stoch_k_14d, 2)
        ELSE 0
    END as extreme_zone_distance,
    ROUND(stoch_k_14d - stoch_d_14d, 2) as momentum_strength
FROM StochasticLags;
GO

-- =====================================================
-- Forex Stochastic Oscillator View (using 'symbol' column)
-- =====================================================
IF OBJECT_ID('dbo.forex_stochastic', 'V') IS NOT NULL
    DROP VIEW dbo.forex_stochastic;
GO

CREATE VIEW dbo.forex_stochastic AS
WITH PriceData AS (
    SELECT 
        symbol as ticker,  -- Use symbol column for Forex
        trading_date,
        CAST(close_price AS FLOAT) as close_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) as high_5d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) as low_5d,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as high_14d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as low_14d,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as high_21d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY symbol ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as low_21d
    FROM dbo.forex_hist_data
    WHERE close_price IS NOT NULL
),
StochasticK AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        high_5d,
        low_5d,
        high_14d,
        low_14d,
        high_21d,
        low_21d,
        CASE 
            WHEN (high_5d - low_5d) > 0 
            THEN ((close_price - low_5d) / (high_5d - low_5d)) * 100.0
            ELSE 50.0
        END as stoch_k_5d,
        CASE 
            WHEN (high_14d - low_14d) > 0 
            THEN ((close_price - low_14d) / (high_14d - low_14d)) * 100.0
            ELSE 50.0
        END as stoch_k_14d,
        CASE 
            WHEN (high_21d - low_21d) > 0 
            THEN ((close_price - low_21d) / (high_21d - low_21d)) * 100.0
            ELSE 50.0
        END as stoch_k_21d
    FROM PriceData
),
StochasticD AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        stoch_k_5d,
        stoch_k_14d,
        stoch_k_21d,
        AVG(stoch_k_5d) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as stoch_d_5d,
        AVG(stoch_k_14d) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as stoch_d_14d,
        AVG(stoch_k_21d) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as stoch_d_21d
    FROM StochasticK
),
StochasticLags AS (
    SELECT 
        ticker,
        trading_date,
        close_price,
        high_price,
        low_price,
        stoch_k_5d,
        stoch_k_14d,
        stoch_k_21d,
        stoch_d_5d,
        stoch_d_14d,
        stoch_d_21d,
        LAG(stoch_k_14d, 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_k_14d,
        LAG(stoch_d_14d, 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_d_14d
    FROM StochasticD
)
SELECT 
    ticker,
    trading_date,
    close_price,
    ROUND(stoch_k_5d, 2) as stoch_5d_k,
    ROUND(stoch_d_5d, 2) as stoch_5d_d,
    ROUND(stoch_k_14d, 2) as stoch_14d_k,
    ROUND(stoch_d_14d, 2) as stoch_14d_d,
    ROUND(stoch_k_21d, 2) as stoch_21d_k,
    ROUND(stoch_d_21d, 2) as stoch_21d_d,
    CASE 
        WHEN stoch_k_14d >= 80 THEN 'OVERBOUGHT'
        WHEN stoch_k_14d <= 20 THEN 'OVERSOLD'
        WHEN stoch_k_14d > 50 THEN 'BULLISH'
        WHEN stoch_k_14d < 50 THEN 'BEARISH'
        ELSE 'NEUTRAL'
    END as stoch_status,
    CASE 
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d <= prev_d_14d 
            AND stoch_k_14d > stoch_d_14d 
        THEN 'BULLISH_CROSS'
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d >= prev_d_14d 
            AND stoch_k_14d < stoch_d_14d 
        THEN 'BEARISH_CROSS'
        WHEN stoch_k_14d > stoch_d_14d 
        THEN 'K_ABOVE_D'
        WHEN stoch_k_14d < stoch_d_14d 
        THEN 'K_BELOW_D'
        ELSE 'NEUTRAL'
    END as stoch_crossover,
    CASE 
        WHEN stoch_k_14d <= 20 
            AND prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d <= prev_d_14d 
            AND stoch_k_14d > stoch_d_14d 
        THEN 'STRONG_BUY_OVERSOLD_CROSS'
        WHEN stoch_k_14d <= 20 THEN 'BUY_OVERSOLD'
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d <= prev_d_14d 
            AND stoch_k_14d > stoch_d_14d 
            AND stoch_k_14d < 80
        THEN 'BUY_BULLISH_CROSS'
        WHEN stoch_k_14d >= 80 
            AND prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d >= prev_d_14d 
            AND stoch_k_14d < stoch_d_14d 
        THEN 'STRONG_SELL_OVERBOUGHT_CROSS'
        WHEN stoch_k_14d >= 80 THEN 'SELL_OVERBOUGHT'
        WHEN prev_k_14d IS NOT NULL AND prev_d_14d IS NOT NULL
            AND prev_k_14d >= prev_d_14d 
            AND stoch_k_14d < stoch_d_14d 
            AND stoch_k_14d > 20
        THEN 'SELL_BEARISH_CROSS'
        ELSE 'NEUTRAL'
    END as stoch_trade_signal,
    CASE 
        WHEN stoch_k_14d >= 80 THEN ROUND(stoch_k_14d - 80, 2)
        WHEN stoch_k_14d <= 20 THEN ROUND(20 - stoch_k_14d, 2)
        ELSE 0
    END as extreme_zone_distance,
    ROUND(stoch_k_14d - stoch_d_14d, 2) as momentum_strength
FROM StochasticLags;
GO

-- =====================================================
-- Grant SELECT permissions
-- =====================================================
GRANT SELECT ON dbo.nse_500_stochastic TO PUBLIC;
GRANT SELECT ON dbo.nasdaq_100_stochastic TO PUBLIC;
GRANT SELECT ON dbo.forex_stochastic TO PUBLIC;
GO

-- =====================================================
-- Test queries to verify the Stochastic views
-- =====================================================

-- Test NSE 500 Stochastic
SELECT TOP 10 
    ticker, 
    trading_date, 
    close_price,
    stoch_14d_k,
    stoch_14d_d,
    stoch_status,
    stoch_crossover,
    stoch_trade_signal,
    momentum_strength
FROM dbo.nse_500_stochastic
ORDER BY trading_date DESC, ticker;

-- Test NASDAQ 100 Stochastic
SELECT TOP 10 
    ticker, 
    trading_date, 
    close_price,
    stoch_14d_k,
    stoch_14d_d,
    stoch_status,
    stoch_crossover,
    stoch_trade_signal,
    momentum_strength
FROM dbo.nasdaq_100_stochastic
ORDER BY trading_date DESC, ticker;

-- Test Forex Stochastic
SELECT TOP 10 
    ticker, 
    trading_date, 
    close_price,
    stoch_14d_k,
    stoch_14d_d,
    stoch_status,
    stoch_crossover,
    stoch_trade_signal,
    momentum_strength
FROM dbo.forex_stochastic
ORDER BY trading_date DESC, ticker;

PRINT 'Stochastic Oscillator views created successfully!';
GO
