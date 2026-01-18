-- =====================================================
-- INDEXED VIEWS FOR FLIGHT STATUS DASHBOARD PERFORMANCE
-- =====================================================
-- These indexed views (SQL Server's materialized views) will significantly improve query performance
-- by pre-computing and storing the results with a clustered index

-- IMPORTANT: Before running, ensure your database recovery model allows indexed views
-- Run this first if needed: ALTER DATABASE stockdata_db SET RECOVERY FULL;

USE stockdata_db;
GO

-- =====================================================
-- NSE 500 FLIGHT STATUS INDEXED VIEW
-- =====================================================

-- Drop existing view if it exists
IF OBJECT_ID('dbo.vw_nse_500_flight_status_indexed', 'V') IS NOT NULL
    DROP VIEW dbo.vw_nse_500_flight_status_indexed;
GO

-- Create the view with SCHEMABINDING (required for indexed views)
CREATE VIEW dbo.vw_nse_500_flight_status_indexed
WITH SCHEMABINDING
AS
WITH LatestPrices AS (
    SELECT 
        ticker,
        company,
        trading_date,
        CAST(close_price AS FLOAT) AS close_price,
        CAST(open_price AS FLOAT) AS open_price,
        CAST(volume AS FLOAT) AS volume,
        ROUND(((CAST(close_price AS FLOAT) - CAST(open_price AS FLOAT)) / CAST(open_price AS FLOAT)) * 100, 2) as daily_change_pct,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nse_500_hist_data
),
LatestRSI AS (
    SELECT 
        ticker,
        RSI,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nse_500_RSI_calculation
),
LatestMACD AS (
    SELECT 
        ticker,
        MACD,
        Signal_Line,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nse_500_macd
),
LatestSMA AS (
    SELECT 
        ticker,
        SMA_50,
        SMA_200,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nse_500_ema_sma_view
),
LatestFib AS (
    SELECT 
        ticker,
        fib_trade_signal,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nse_500_fibonacci
),
LatestStoch AS (
    SELECT 
        ticker,
        stoch_trade_signal,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nse_500_stochastic
)
SELECT 
    p.ticker,
    p.company,
    p.trading_date as last_update,
    p.close_price,
    p.daily_change_pct,
    p.volume,
    r.RSI,
    m.MACD,
    sma.SMA_50,
    sma.SMA_200,
    -- Signal score
    (
        CASE WHEN r.RSI < 30 THEN 1 WHEN r.RSI > 70 THEN -1 ELSE 0 END +
        CASE WHEN m.MACD > m.Signal_Line THEN 1 WHEN m.MACD < m.Signal_Line THEN -1 ELSE 0 END +
        CASE WHEN sma.SMA_50 > sma.SMA_200 THEN 1 WHEN sma.SMA_50 < sma.SMA_200 THEN -1 ELSE 0 END +
        CASE WHEN fib.fib_trade_signal LIKE '%STRONG_BUY%' THEN 2 WHEN fib.fib_trade_signal LIKE '%BUY%' THEN 1 
             WHEN fib.fib_trade_signal LIKE '%STRONG_SELL%' THEN -2 WHEN fib.fib_trade_signal LIKE '%SELL%' THEN -1 ELSE 0 END +
        CASE WHEN stoch.stoch_trade_signal LIKE '%BUY%' THEN 1 WHEN stoch.stoch_trade_signal LIKE '%SELL%' THEN -1 ELSE 0 END +
        CASE WHEN sma.SMA_50 > sma.SMA_200 AND p.close_price > sma.SMA_50 THEN 2 
             WHEN sma.SMA_50 > sma.SMA_200 THEN 1 
             WHEN sma.SMA_50 < sma.SMA_200 AND p.close_price < sma.SMA_50 THEN -2 
             WHEN sma.SMA_50 < sma.SMA_200 THEN -1 ELSE 0 END
    ) as signal_score,
    -- Analysis fields
    CASE WHEN r.RSI > 70 THEN 'Overbought' WHEN r.RSI < 30 THEN 'Oversold' ELSE 'Neutral' END as rsi_status,
    CASE WHEN m.MACD > m.Signal_Line THEN 'Bullish' WHEN m.MACD < m.Signal_Line THEN 'Bearish' ELSE 'Neutral' END as macd_trend,
    CASE WHEN p.close_price > sma.SMA_200 THEN 'Uptrend' WHEN p.close_price < sma.SMA_200 THEN 'Downtrend' ELSE 'Sideways' END as long_term_trend
FROM LatestPrices p
LEFT JOIN LatestRSI r ON p.ticker = r.ticker AND r.rn = 1
LEFT JOIN LatestMACD m ON p.ticker = m.ticker AND m.rn = 1
LEFT JOIN LatestSMA sma ON p.ticker = sma.ticker AND sma.rn = 1
LEFT JOIN LatestFib fib ON p.ticker = fib.ticker AND fib.rn = 1
LEFT JOIN LatestStoch stoch ON p.ticker = stoch.ticker AND stoch.rn = 1
WHERE p.rn = 1;
GO

-- Create unique clustered index (this materializes the view)
CREATE UNIQUE CLUSTERED INDEX IX_FlightStatus_NSE_Ticker 
    ON dbo.vw_nse_500_flight_status_indexed(ticker);
GO

-- Optional: Create additional non-clustered indexes for better filter performance
CREATE NONCLUSTERED INDEX IX_FlightStatus_NSE_SignalScore 
    ON dbo.vw_nse_500_flight_status_indexed(signal_score) 
    INCLUDE (ticker, company, close_price);
GO

PRINT 'NSE 500 Indexed View Created Successfully!';
GO

-- =====================================================
-- NASDAQ 100 FLIGHT STATUS INDEXED VIEW
-- =====================================================

IF OBJECT_ID('dbo.vw_nasdaq_100_flight_status_indexed', 'V') IS NOT NULL
    DROP VIEW dbo.vw_nasdaq_100_flight_status_indexed;
GO

CREATE VIEW dbo.vw_nasdaq_100_flight_status_indexed
WITH SCHEMABINDING
AS
WITH LatestPrices AS (
    SELECT 
        ticker,
        company,
        trading_date,
        CAST(close_price AS FLOAT) AS close_price,
        CAST(open_price AS FLOAT) AS open_price,
        CAST(volume AS FLOAT) AS volume,
        ROUND(((CAST(close_price AS FLOAT) - CAST(open_price AS FLOAT)) / CAST(open_price AS FLOAT)) * 100, 2) as daily_change_pct,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nasdaq_100_hist_data
),
LatestRSI AS (
    SELECT 
        ticker,
        RSI,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nasdaq_100_RSI_calculation
),
LatestMACD AS (
    SELECT 
        ticker,
        MACD,
        Signal_Line,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nasdaq_100_macd
),
LatestSMA AS (
    SELECT 
        ticker,
        SMA_50,
        SMA_200,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nasdaq_100_ema_sma_view
),
LatestFib AS (
    SELECT 
        ticker,
        fib_trade_signal,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nasdaq_100_fibonacci
),
LatestStoch AS (
    SELECT 
        ticker,
        stoch_trade_signal,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.nasdaq_100_stochastic
)
SELECT 
    p.ticker,
    p.company,
    p.trading_date as last_update,
    p.close_price,
    p.daily_change_pct,
    p.volume,
    r.RSI,
    m.MACD,
    sma.SMA_50,
    sma.SMA_200,
    (
        CASE WHEN r.RSI < 30 THEN 1 WHEN r.RSI > 70 THEN -1 ELSE 0 END +
        CASE WHEN m.MACD > m.Signal_Line THEN 1 WHEN m.MACD < m.Signal_Line THEN -1 ELSE 0 END +
        CASE WHEN sma.SMA_50 > sma.SMA_200 THEN 1 WHEN sma.SMA_50 < sma.SMA_200 THEN -1 ELSE 0 END +
        CASE WHEN fib.fib_trade_signal LIKE '%STRONG_BUY%' THEN 2 WHEN fib.fib_trade_signal LIKE '%BUY%' THEN 1 
             WHEN fib.fib_trade_signal LIKE '%STRONG_SELL%' THEN -2 WHEN fib.fib_trade_signal LIKE '%SELL%' THEN -1 ELSE 0 END +
        CASE WHEN stoch.stoch_trade_signal LIKE '%BUY%' THEN 1 WHEN stoch.stoch_trade_signal LIKE '%SELL%' THEN -1 ELSE 0 END +
        CASE WHEN sma.SMA_50 > sma.SMA_200 AND p.close_price > sma.SMA_50 THEN 2 
             WHEN sma.SMA_50 > sma.SMA_200 THEN 1 
             WHEN sma.SMA_50 < sma.SMA_200 AND p.close_price < sma.SMA_50 THEN -2 
             WHEN sma.SMA_50 < sma.SMA_200 THEN -1 ELSE 0 END
    ) as signal_score,
    CASE WHEN r.RSI > 70 THEN 'Overbought' WHEN r.RSI < 30 THEN 'Oversold' ELSE 'Neutral' END as rsi_status,
    CASE WHEN m.MACD > m.Signal_Line THEN 'Bullish' WHEN m.MACD < m.Signal_Line THEN 'Bearish' ELSE 'Neutral' END as macd_trend,
    CASE WHEN p.close_price > sma.SMA_200 THEN 'Uptrend' WHEN p.close_price < sma.SMA_200 THEN 'Downtrend' ELSE 'Sideways' END as long_term_trend
FROM LatestPrices p
LEFT JOIN LatestRSI r ON p.ticker = r.ticker AND r.rn = 1
LEFT JOIN LatestMACD m ON p.ticker = m.ticker AND m.rn = 1
LEFT JOIN LatestSMA sma ON p.ticker = sma.ticker AND sma.rn = 1
LEFT JOIN LatestFib fib ON p.ticker = fib.ticker AND fib.rn = 1
LEFT JOIN LatestStoch stoch ON p.ticker = stoch.ticker AND stoch.rn = 1
WHERE p.rn = 1;
GO

CREATE UNIQUE CLUSTERED INDEX IX_FlightStatus_NASDAQ_Ticker 
    ON dbo.vw_nasdaq_100_flight_status_indexed(ticker);
GO

CREATE NONCLUSTERED INDEX IX_FlightStatus_NASDAQ_SignalScore 
    ON dbo.vw_nasdaq_100_flight_status_indexed(signal_score) 
    INCLUDE (ticker, company, close_price);
GO

PRINT 'NASDAQ 100 Indexed View Created Successfully!';
GO

-- =====================================================
-- FOREX FLIGHT STATUS INDEXED VIEW
-- =====================================================

IF OBJECT_ID('dbo.vw_forex_flight_status_indexed', 'V') IS NOT NULL
    DROP VIEW dbo.vw_forex_flight_status_indexed;
GO

CREATE VIEW dbo.vw_forex_flight_status_indexed
WITH SCHEMABINDING
AS
WITH LatestPrices AS (
    SELECT 
        symbol,
        trading_date,
        CAST(close_price AS FLOAT) AS close_price,
        CAST(open_price AS FLOAT) AS open_price,
        CAST(volume AS FLOAT) AS volume,
        ROUND(((CAST(close_price AS FLOAT) - CAST(open_price AS FLOAT)) / CAST(open_price AS FLOAT)) * 100, 2) as daily_change_pct,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trading_date DESC) as rn
    FROM dbo.forex_hist_data
),
LatestRSI AS (
    SELECT 
        symbol,
        RSI,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trading_date DESC) as rn
    FROM dbo.forex_RSI_calculation
),
LatestMACD AS (
    SELECT 
        symbol,
        MACD,
        Signal_Line,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trading_date DESC) as rn
    FROM dbo.forex_macd
),
LatestSMA AS (
    SELECT 
        symbol,
        SMA_50,
        SMA_200,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trading_date DESC) as rn
    FROM dbo.forex_ema_sma_view
),
LatestFib AS (
    SELECT 
        ticker,
        fib_trade_signal,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.forex_fibonacci
),
LatestStoch AS (
    SELECT 
        ticker,
        stoch_trade_signal,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) as rn
    FROM dbo.forex_stochastic
)
SELECT 
    p.symbol as ticker,
    p.symbol as company,
    p.trading_date as last_update,
    p.close_price,
    p.daily_change_pct,
    p.volume,
    r.RSI,
    m.MACD,
    sma.SMA_50,
    sma.SMA_200,
    (
        CASE WHEN r.RSI < 30 THEN 1 WHEN r.RSI > 70 THEN -1 ELSE 0 END +
        CASE WHEN m.MACD > m.Signal_Line THEN 1 WHEN m.MACD < m.Signal_Line THEN -1 ELSE 0 END +
        CASE WHEN sma.SMA_50 > sma.SMA_200 THEN 1 WHEN sma.SMA_50 < sma.SMA_200 THEN -1 ELSE 0 END +
        CASE WHEN fib.fib_trade_signal LIKE '%STRONG_BUY%' THEN 2 WHEN fib.fib_trade_signal LIKE '%BUY%' THEN 1 
             WHEN fib.fib_trade_signal LIKE '%STRONG_SELL%' THEN -2 WHEN fib.fib_trade_signal LIKE '%SELL%' THEN -1 ELSE 0 END +
        CASE WHEN stoch.stoch_trade_signal LIKE '%BUY%' THEN 1 WHEN stoch.stoch_trade_signal LIKE '%SELL%' THEN -1 ELSE 0 END +
        CASE WHEN sma.SMA_50 > sma.SMA_200 AND p.close_price > sma.SMA_50 THEN 2 
             WHEN sma.SMA_50 > sma.SMA_200 THEN 1 
             WHEN sma.SMA_50 < sma.SMA_200 AND p.close_price < sma.SMA_50 THEN -2 
             WHEN sma.SMA_50 < sma.SMA_200 THEN -1 ELSE 0 END
    ) as signal_score,
    CASE WHEN r.RSI > 70 THEN 'Overbought' WHEN r.RSI < 30 THEN 'Oversold' ELSE 'Neutral' END as rsi_status,
    CASE WHEN m.MACD > m.Signal_Line THEN 'Bullish' WHEN m.MACD < m.Signal_Line THEN 'Bearish' ELSE 'Neutral' END as macd_trend,
    CASE WHEN p.close_price > sma.SMA_200 THEN 'Uptrend' WHEN p.close_price < sma.SMA_200 THEN 'Downtrend' ELSE 'Sideways' END as long_term_trend
FROM LatestPrices p
LEFT JOIN LatestRSI r ON p.symbol = r.symbol AND r.rn = 1
LEFT JOIN LatestMACD m ON p.symbol = m.symbol AND m.rn = 1
LEFT JOIN LatestSMA sma ON p.symbol = sma.symbol AND sma.rn = 1
LEFT JOIN LatestFib fib ON p.symbol = fib.ticker AND fib.rn = 1
LEFT JOIN LatestStoch stoch ON p.symbol = stoch.ticker AND stoch.rn = 1
WHERE p.rn = 1;
GO

CREATE UNIQUE CLUSTERED INDEX IX_FlightStatus_Forex_Ticker 
    ON dbo.vw_forex_flight_status_indexed(ticker);
GO

CREATE NONCLUSTERED INDEX IX_FlightStatus_Forex_SignalScore 
    ON dbo.vw_forex_flight_status_indexed(signal_score) 
    INCLUDE (ticker, close_price);
GO

PRINT 'Forex Indexed View Created Successfully!';
GO

-- =====================================================
-- MAINTENANCE: Refresh indexed views (run periodically)
-- =====================================================
-- Note: Indexed views auto-update when base tables change, 
-- but you can manually refresh with:
-- sp_refreshview 'dbo.vw_nse_500_flight_status_indexed'
-- sp_refreshview 'dbo.vw_nasdaq_100_flight_status_indexed'
-- sp_refreshview 'dbo.vw_forex_flight_status_indexed'

PRINT '';
PRINT '========================================';
PRINT 'ALL INDEXED VIEWS CREATED SUCCESSFULLY!';
PRINT '========================================';
PRINT 'These materialized views will significantly improve Flight Status Dashboard performance.';
PRINT 'The views will automatically update when underlying data changes.';
PRINT '';
PRINT 'Next step: Update your Streamlit app to query these views instead of the complex CTEs.';
