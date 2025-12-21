-- =====================================================
-- Support and Resistance SQL View Definitions
-- =====================================================
-- This script creates Support and Resistance views for NSE 500, NASDAQ 100, and Forex
-- Using multiple methods: Pivot Points, Swing Highs/Lows, and Dynamic S/R levels
-- =====================================================

USE stockdata_db;
GO

-- =====================================================
-- NSE 500 Support and Resistance View
-- =====================================================
IF OBJECT_ID('dbo.nse_500_support_resistance', 'V') IS NOT NULL
    DROP VIEW dbo.nse_500_support_resistance;
GO

CREATE VIEW dbo.nse_500_support_resistance AS
WITH PriceData AS (
    SELECT 
        ticker,
        trading_date,
        CAST(open_price AS FLOAT) as open_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        CAST(close_price AS FLOAT) as close_price,
        volume,
        -- Calculate previous day values for pivot points
        LAG(CAST(high_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_high,
        LAG(CAST(low_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_low,
        LAG(CAST(close_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_close,
        -- 20-day high and low for swing points
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as high_20d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as low_20d,
        -- 50-day high and low for major S/R levels
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as high_50d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as low_50d,
        -- Moving averages as dynamic S/R
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as sma_20,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma_50,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) as sma_200
    FROM dbo.nse_500_hist_data
    WHERE close_price IS NOT NULL
),
PivotPoints AS (
    SELECT 
        ticker,
        trading_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        prev_high,
        prev_low,
        prev_close,
        high_20d,
        low_20d,
        high_50d,
        low_50d,
        sma_20,
        sma_50,
        sma_200,
        -- Classic Pivot Point Calculation
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN (prev_high + prev_low + prev_close) / 3.0 
        END as pivot_point,
        -- Resistance Levels (R1, R2, R3)
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN (2.0 * (prev_high + prev_low + prev_close) / 3.0) - prev_low 
        END as resistance_1,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN ((prev_high + prev_low + prev_close) / 3.0) + (prev_high - prev_low) 
        END as resistance_2,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN prev_high + 2.0 * ((prev_high + prev_low + prev_close) / 3.0 - prev_low) 
        END as resistance_3,
        -- Support Levels (S1, S2, S3)
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN (2.0 * (prev_high + prev_low + prev_close) / 3.0) - prev_high 
        END as support_1,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN ((prev_high + prev_low + prev_close) / 3.0) - (prev_high - prev_low) 
        END as support_2,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN prev_low - 2.0 * (prev_high - (prev_high + prev_low + prev_close) / 3.0) 
        END as support_3
    FROM PriceData
)
SELECT 
    ticker,
    trading_date,
    close_price,
    -- Pivot Point Levels
    ROUND(pivot_point, 2) as pivot_point,
    ROUND(resistance_1, 2) as r1,
    ROUND(resistance_2, 2) as r2,
    ROUND(resistance_3, 2) as r3,
    ROUND(support_1, 2) as s1,
    ROUND(support_2, 2) as s2,
    ROUND(support_3, 2) as s3,
    -- Swing High/Low Levels
    ROUND(high_20d, 2) as swing_high_20d,
    ROUND(low_20d, 2) as swing_low_20d,
    ROUND(high_50d, 2) as swing_high_50d,
    ROUND(low_50d, 2) as swing_low_50d,
    -- Moving Average S/R Levels
    ROUND(sma_20, 2) as ma_20,
    ROUND(sma_50, 2) as ma_50,
    ROUND(sma_200, 2) as ma_200,
    -- Support/Resistance Status
    CASE 
        WHEN close_price > pivot_point THEN 'ABOVE_PIVOT'
        WHEN close_price < pivot_point THEN 'BELOW_PIVOT'
        ELSE 'AT_PIVOT'
    END as pivot_status,
    -- Nearest Support Level
    CASE 
        WHEN close_price >= support_1 THEN 'S1'
        WHEN close_price >= support_2 THEN 'S2'
        WHEN close_price >= support_3 THEN 'S3'
        ELSE 'BELOW_S3'
    END as nearest_support,
    -- Nearest Resistance Level
    CASE 
        WHEN close_price <= resistance_1 THEN 'R1'
        WHEN close_price <= resistance_2 THEN 'R2'
        WHEN close_price <= resistance_3 THEN 'R3'
        ELSE 'ABOVE_R3'
    END as nearest_resistance,
    -- Distance to Key Levels (%)
    ROUND(((close_price - support_1) / support_1 * 100), 2) as distance_to_s1_pct,
    ROUND(((resistance_1 - close_price) / close_price * 100), 2) as distance_to_r1_pct,
    -- Trading Signal based on S/R
    CASE 
        WHEN close_price <= support_1 * 1.01 THEN 'NEAR_SUPPORT_BUY'
        WHEN close_price >= resistance_1 * 0.99 THEN 'NEAR_RESISTANCE_SELL'
        WHEN close_price > pivot_point AND close_price < resistance_1 THEN 'BULLISH_ZONE'
        WHEN close_price < pivot_point AND close_price > support_1 THEN 'BEARISH_ZONE'
        ELSE 'NEUTRAL'
    END as sr_trade_signal
FROM PivotPoints;
GO

-- =====================================================
-- NASDAQ 100 Support and Resistance View
-- =====================================================
IF OBJECT_ID('dbo.nasdaq_100_support_resistance', 'V') IS NOT NULL
    DROP VIEW dbo.nasdaq_100_support_resistance;
GO

CREATE VIEW dbo.nasdaq_100_support_resistance AS
WITH PriceData AS (
    SELECT 
        ticker,
        trading_date,
        CAST(open_price AS FLOAT) as open_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        CAST(close_price AS FLOAT) as close_price,
        volume,
        LAG(CAST(high_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_high,
        LAG(CAST(low_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_low,
        LAG(CAST(close_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_close,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as high_20d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as low_20d,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as high_50d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as low_50d,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as sma_20,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma_50,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) as sma_200
    FROM dbo.nasdaq100_historical_prices
    WHERE close_price IS NOT NULL
),
PivotPoints AS (
    SELECT 
        ticker,
        trading_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        prev_high,
        prev_low,
        prev_close,
        high_20d,
        low_20d,
        high_50d,
        low_50d,
        sma_20,
        sma_50,
        sma_200,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN (prev_high + prev_low + prev_close) / 3.0 
        END as pivot_point,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN (2.0 * (prev_high + prev_low + prev_close) / 3.0) - prev_low 
        END as resistance_1,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN ((prev_high + prev_low + prev_close) / 3.0) + (prev_high - prev_low) 
        END as resistance_2,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN prev_high + 2.0 * ((prev_high + prev_low + prev_close) / 3.0 - prev_low) 
        END as resistance_3,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN (2.0 * (prev_high + prev_low + prev_close) / 3.0) - prev_high 
        END as support_1,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN ((prev_high + prev_low + prev_close) / 3.0) - (prev_high - prev_low) 
        END as support_2,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN prev_low - 2.0 * (prev_high - (prev_high + prev_low + prev_close) / 3.0) 
        END as support_3
    FROM PriceData
)
SELECT 
    ticker,
    trading_date,
    close_price,
    ROUND(pivot_point, 2) as pivot_point,
    ROUND(resistance_1, 2) as r1,
    ROUND(resistance_2, 2) as r2,
    ROUND(resistance_3, 2) as r3,
    ROUND(support_1, 2) as s1,
    ROUND(support_2, 2) as s2,
    ROUND(support_3, 2) as s3,
    ROUND(high_20d, 2) as swing_high_20d,
    ROUND(low_20d, 2) as swing_low_20d,
    ROUND(high_50d, 2) as swing_high_50d,
    ROUND(low_50d, 2) as swing_low_50d,
    ROUND(sma_20, 2) as ma_20,
    ROUND(sma_50, 2) as ma_50,
    ROUND(sma_200, 2) as ma_200,
    CASE 
        WHEN close_price > pivot_point THEN 'ABOVE_PIVOT'
        WHEN close_price < pivot_point THEN 'BELOW_PIVOT'
        ELSE 'AT_PIVOT'
    END as pivot_status,
    CASE 
        WHEN close_price >= support_1 THEN 'S1'
        WHEN close_price >= support_2 THEN 'S2'
        WHEN close_price >= support_3 THEN 'S3'
        ELSE 'BELOW_S3'
    END as nearest_support,
    CASE 
        WHEN close_price <= resistance_1 THEN 'R1'
        WHEN close_price <= resistance_2 THEN 'R2'
        WHEN close_price <= resistance_3 THEN 'R3'
        ELSE 'ABOVE_R3'
    END as nearest_resistance,
    ROUND(((close_price - support_1) / support_1 * 100), 2) as distance_to_s1_pct,
    ROUND(((resistance_1 - close_price) / close_price * 100), 2) as distance_to_r1_pct,
    CASE 
        WHEN close_price <= support_1 * 1.01 THEN 'NEAR_SUPPORT_BUY'
        WHEN close_price >= resistance_1 * 0.99 THEN 'NEAR_RESISTANCE_SELL'
        WHEN close_price > pivot_point AND close_price < resistance_1 THEN 'BULLISH_ZONE'
        WHEN close_price < pivot_point AND close_price > support_1 THEN 'BEARISH_ZONE'
        ELSE 'NEUTRAL'
    END as sr_trade_signal
FROM PivotPoints;
GO

-- =====================================================
-- Forex Support and Resistance View
-- =====================================================
IF OBJECT_ID('dbo.forex_support_resistance', 'V') IS NOT NULL
    DROP VIEW dbo.forex_support_resistance;
GO

CREATE VIEW dbo.forex_support_resistance AS
WITH PriceData AS (
    SELECT 
        ticker,
        trading_date,
        CAST(open_price AS FLOAT) as open_price,
        CAST(high_price AS FLOAT) as high_price,
        CAST(low_price AS FLOAT) as low_price,
        CAST(close_price AS FLOAT) as close_price,
        volume,
        LAG(CAST(high_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_high,
        LAG(CAST(low_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_low,
        LAG(CAST(close_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_close,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as high_20d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as low_20d,
        MAX(CAST(high_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as high_50d,
        MIN(CAST(low_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 50 PRECEDING AND CURRENT ROW) as low_50d,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as sma_20,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma_50,
        AVG(CAST(close_price AS FLOAT)) OVER (PARTITION BY ticker ORDER BY trading_date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) as sma_200
    FROM dbo.forex_historical_prices
    WHERE close_price IS NOT NULL
),
PivotPoints AS (
    SELECT 
        ticker,
        trading_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        prev_high,
        prev_low,
        prev_close,
        high_20d,
        low_20d,
        high_50d,
        low_50d,
        sma_20,
        sma_50,
        sma_200,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN (prev_high + prev_low + prev_close) / 3.0 
        END as pivot_point,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN (2.0 * (prev_high + prev_low + prev_close) / 3.0) - prev_low 
        END as resistance_1,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN ((prev_high + prev_low + prev_close) / 3.0) + (prev_high - prev_low) 
        END as resistance_2,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN prev_high + 2.0 * ((prev_high + prev_low + prev_close) / 3.0 - prev_low) 
        END as resistance_3,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN (2.0 * (prev_high + prev_low + prev_close) / 3.0) - prev_high 
        END as support_1,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN ((prev_high + prev_low + prev_close) / 3.0) - (prev_high - prev_low) 
        END as support_2,
        CASE 
            WHEN prev_high IS NOT NULL AND prev_low IS NOT NULL AND prev_close IS NOT NULL 
            THEN prev_low - 2.0 * (prev_high - (prev_high + prev_low + prev_close) / 3.0) 
        END as support_3
    FROM PriceData
)
SELECT 
    ticker,
    trading_date,
    close_price,
    ROUND(pivot_point, 4) as pivot_point,
    ROUND(resistance_1, 4) as r1,
    ROUND(resistance_2, 4) as r2,
    ROUND(resistance_3, 4) as r3,
    ROUND(support_1, 4) as s1,
    ROUND(support_2, 4) as s2,
    ROUND(support_3, 4) as s3,
    ROUND(high_20d, 4) as swing_high_20d,
    ROUND(low_20d, 4) as swing_low_20d,
    ROUND(high_50d, 4) as swing_high_50d,
    ROUND(low_50d, 4) as swing_low_50d,
    ROUND(sma_20, 4) as ma_20,
    ROUND(sma_50, 4) as ma_50,
    ROUND(sma_200, 4) as ma_200,
    CASE 
        WHEN close_price > pivot_point THEN 'ABOVE_PIVOT'
        WHEN close_price < pivot_point THEN 'BELOW_PIVOT'
        ELSE 'AT_PIVOT'
    END as pivot_status,
    CASE 
        WHEN close_price >= support_1 THEN 'S1'
        WHEN close_price >= support_2 THEN 'S2'
        WHEN close_price >= support_3 THEN 'S3'
        ELSE 'BELOW_S3'
    END as nearest_support,
    CASE 
        WHEN close_price <= resistance_1 THEN 'R1'
        WHEN close_price <= resistance_2 THEN 'R2'
        WHEN close_price <= resistance_3 THEN 'R3'
        ELSE 'ABOVE_R3'
    END as nearest_resistance,
    ROUND(((close_price - support_1) / support_1 * 100), 2) as distance_to_s1_pct,
    ROUND(((resistance_1 - close_price) / close_price * 100), 2) as distance_to_r1_pct,
    CASE 
        WHEN close_price <= support_1 * 1.01 THEN 'NEAR_SUPPORT_BUY'
        WHEN close_price >= resistance_1 * 0.99 THEN 'NEAR_RESISTANCE_SELL'
        WHEN close_price > pivot_point AND close_price < resistance_1 THEN 'BULLISH_ZONE'
        WHEN close_price < pivot_point AND close_price > support_1 THEN 'BEARISH_ZONE'
        ELSE 'NEUTRAL'
    END as sr_trade_signal
FROM PivotPoints;
GO

-- =====================================================
-- Grant SELECT permissions (adjust as needed)
-- =====================================================
GRANT SELECT ON dbo.nse_500_support_resistance TO PUBLIC;
GRANT SELECT ON dbo.nasdaq_100_support_resistance TO PUBLIC;
GRANT SELECT ON dbo.forex_support_resistance TO PUBLIC;
GO

-- =====================================================
-- Test queries to verify the views
-- =====================================================

-- Test NSE 500 Support/Resistance
SELECT TOP 10 
    ticker, 
    trading_date, 
    close_price,
    pivot_point,
    r1, s1,
    pivot_status,
    sr_trade_signal
FROM dbo.nse_500_support_resistance
ORDER BY trading_date DESC, ticker;

-- Test NASDAQ 100 Support/Resistance
SELECT TOP 10 
    ticker, 
    trading_date, 
    close_price,
    pivot_point,
    r1, s1,
    pivot_status,
    sr_trade_signal
FROM dbo.nasdaq_100_support_resistance
ORDER BY trading_date DESC, ticker;

-- Test Forex Support/Resistance
SELECT TOP 10 
    ticker, 
    trading_date, 
    close_price,
    pivot_point,
    r1, s1,
    pivot_status,
    sr_trade_signal
FROM dbo.forex_support_resistance
ORDER BY trading_date DESC, ticker;

PRINT 'Support and Resistance views created successfully!';
GO
