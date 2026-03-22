-- ============================================================================
-- UPDATE RSI VIEWS: SMA → Wilder's Smoothed RSI (matches TradingView)
-- ============================================================================
-- Problem: Current views use simple 14-period window average (SMA), which 
--          diverges significantly from the industry-standard Wilder's smoothing.
-- Fix:     Use recursive CTE to compute Wilder's SMMA. Since views can't use
--          OPTION(MAXRECURSION 0), we use inline table-valued functions + views.
-- Affects: nasdaq_100_RSI_calculation, nse_500_RSI_calculation, forex_RSI_calculation
--          (downstream signal views remain unchanged - they just SELECT from these)
-- ============================================================================

-- ============================================================================
-- STEP 1: Create helper inline table-valued functions (recursive CTE lives here)
-- ============================================================================

-- Drop existing functions if they exist
IF OBJECT_ID('dbo.fn_nasdaq_100_RSI', 'IF') IS NOT NULL DROP FUNCTION dbo.fn_nasdaq_100_RSI;
IF OBJECT_ID('dbo.fn_nse_500_RSI', 'IF') IS NOT NULL DROP FUNCTION dbo.fn_nse_500_RSI;
IF OBJECT_ID('dbo.fn_forex_RSI', 'IF') IS NOT NULL DROP FUNCTION dbo.fn_forex_RSI;
GO

-- ============================================================================
-- NASDAQ 100 RSI Function
-- ============================================================================
CREATE FUNCTION dbo.fn_nasdaq_100_RSI()
RETURNS TABLE
AS
RETURN
(
    WITH PriceChanges AS (
        SELECT
            ticker,
            trading_date,
            CAST(close_price AS FLOAT) AS close_price,
            CAST(close_price AS FLOAT) - LAG(CAST(close_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) AS price_change,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date) AS rn
        FROM dbo.nasdaq_100_hist_data
    ),
    GainsLosses AS (
        SELECT
            ticker,
            trading_date,
            close_price,
            rn,
            CASE WHEN price_change > 0 THEN price_change ELSE 0 END AS gain,
            CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END AS loss
        FROM PriceChanges
        WHERE price_change IS NOT NULL  -- Skip first row per ticker (no LAG value)
    ),
    -- Initial SMA seed: average of first 14 gains/losses per ticker
    InitialAvg AS (
        SELECT
            ticker,
            AVG(gain) AS initial_avg_gain,
            AVG(loss) AS initial_avg_loss
        FROM GainsLosses
        WHERE rn BETWEEN 2 AND 15  -- rows 2-15 = first 14 price changes
        GROUP BY ticker
    ),
    -- Numbered rows for recursion (only rows after the seed period)
    Numbered AS (
        SELECT
            gl.ticker,
            gl.trading_date,
            gl.gain,
            gl.loss,
            gl.rn,
            ROW_NUMBER() OVER (PARTITION BY gl.ticker ORDER BY gl.trading_date) AS seq
        FROM GainsLosses gl
        WHERE gl.rn >= 2  -- All rows with valid price changes
    ),
    -- Recursive Wilder's smoothing
    WilderSmoothing AS (
        -- Base case: row at position 14 (seq=14) uses the SMA seed
        SELECT
            n.ticker,
            n.trading_date,
            n.gain,
            n.loss,
            n.seq,
            ia.initial_avg_gain AS avg_gain,
            ia.initial_avg_loss AS avg_loss
        FROM Numbered n
        INNER JOIN InitialAvg ia ON n.ticker = ia.ticker
        WHERE n.seq = 14

        UNION ALL

        -- Recursive case: Wilder's formula
        SELECT
            n.ticker,
            n.trading_date,
            n.gain,
            n.loss,
            n.seq,
            (ws.avg_gain * 13.0 + n.gain) / 14.0 AS avg_gain,
            (ws.avg_loss * 13.0 + n.loss) / 14.0 AS avg_loss
        FROM WilderSmoothing ws
        INNER JOIN Numbered n ON ws.ticker = n.ticker AND n.seq = ws.seq + 1
    )
    SELECT
        ticker,
        trading_date,
        CASE
            WHEN avg_loss = 0 THEN 100.0
            ELSE 100.0 - (100.0 / (1.0 + (avg_gain / NULLIF(avg_loss, 0))))
        END AS RSI
    FROM WilderSmoothing
);
GO

-- ============================================================================
-- NSE 500 RSI Function
-- ============================================================================
CREATE FUNCTION dbo.fn_nse_500_RSI()
RETURNS TABLE
AS
RETURN
(
    WITH PriceChanges AS (
        SELECT
            ticker,
            trading_date,
            CAST(close_price AS FLOAT) AS close_price,
            CAST(close_price AS FLOAT) - LAG(CAST(close_price AS FLOAT), 1) OVER (PARTITION BY ticker ORDER BY trading_date) AS price_change,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date) AS rn
        FROM dbo.nse_500_hist_data
    ),
    GainsLosses AS (
        SELECT
            ticker,
            trading_date,
            close_price,
            rn,
            CASE WHEN price_change > 0 THEN price_change ELSE 0 END AS gain,
            CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END AS loss
        FROM PriceChanges
        WHERE price_change IS NOT NULL
    ),
    InitialAvg AS (
        SELECT
            ticker,
            AVG(gain) AS initial_avg_gain,
            AVG(loss) AS initial_avg_loss
        FROM GainsLosses
        WHERE rn BETWEEN 2 AND 15
        GROUP BY ticker
    ),
    Numbered AS (
        SELECT
            gl.ticker,
            gl.trading_date,
            gl.gain,
            gl.loss,
            gl.rn,
            ROW_NUMBER() OVER (PARTITION BY gl.ticker ORDER BY gl.trading_date) AS seq
        FROM GainsLosses gl
        WHERE gl.rn >= 2
    ),
    WilderSmoothing AS (
        SELECT
            n.ticker,
            n.trading_date,
            n.gain,
            n.loss,
            n.seq,
            ia.initial_avg_gain AS avg_gain,
            ia.initial_avg_loss AS avg_loss
        FROM Numbered n
        INNER JOIN InitialAvg ia ON n.ticker = ia.ticker
        WHERE n.seq = 14

        UNION ALL

        SELECT
            n.ticker,
            n.trading_date,
            n.gain,
            n.loss,
            n.seq,
            (ws.avg_gain * 13.0 + n.gain) / 14.0 AS avg_gain,
            (ws.avg_loss * 13.0 + n.loss) / 14.0 AS avg_loss
        FROM WilderSmoothing ws
        INNER JOIN Numbered n ON ws.ticker = n.ticker AND n.seq = ws.seq + 1
    )
    SELECT
        ticker,
        trading_date,
        CASE
            WHEN avg_loss = 0 THEN 100.0
            ELSE 100.0 - (100.0 / (1.0 + (avg_gain / NULLIF(avg_loss, 0))))
        END AS RSI
    FROM WilderSmoothing
);
GO

-- ============================================================================
-- Forex RSI Function (uses 'symbol' instead of 'ticker')
-- ============================================================================
CREATE FUNCTION dbo.fn_forex_RSI()
RETURNS TABLE
AS
RETURN
(
    WITH PriceChanges AS (
        SELECT
            symbol,
            trading_date,
            CAST(close_price AS FLOAT) AS close_price,
            CAST(close_price AS FLOAT) - LAG(CAST(close_price AS FLOAT), 1) OVER (PARTITION BY symbol ORDER BY trading_date) AS price_change,
            ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trading_date) AS rn
        FROM dbo.forex_hist_data
    ),
    GainsLosses AS (
        SELECT
            symbol,
            trading_date,
            close_price,
            rn,
            CASE WHEN price_change > 0 THEN price_change ELSE 0 END AS gain,
            CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END AS loss
        FROM PriceChanges
        WHERE price_change IS NOT NULL
    ),
    InitialAvg AS (
        SELECT
            symbol,
            AVG(gain) AS initial_avg_gain,
            AVG(loss) AS initial_avg_loss
        FROM GainsLosses
        WHERE rn BETWEEN 2 AND 15
        GROUP BY symbol
    ),
    Numbered AS (
        SELECT
            gl.symbol,
            gl.trading_date,
            gl.gain,
            gl.loss,
            gl.rn,
            ROW_NUMBER() OVER (PARTITION BY gl.symbol ORDER BY gl.trading_date) AS seq
        FROM GainsLosses gl
        WHERE gl.rn >= 2
    ),
    WilderSmoothing AS (
        SELECT
            n.symbol,
            n.trading_date,
            n.gain,
            n.loss,
            n.seq,
            ia.initial_avg_gain AS avg_gain,
            ia.initial_avg_loss AS avg_loss
        FROM Numbered n
        INNER JOIN InitialAvg ia ON n.symbol = ia.symbol
        WHERE n.seq = 14

        UNION ALL

        SELECT
            n.symbol,
            n.trading_date,
            n.gain,
            n.loss,
            n.seq,
            (ws.avg_gain * 13.0 + n.gain) / 14.0 AS avg_gain,
            (ws.avg_loss * 13.0 + n.loss) / 14.0 AS avg_loss
        FROM WilderSmoothing ws
        INNER JOIN Numbered n ON ws.symbol = n.symbol AND n.seq = ws.seq + 1
    )
    SELECT
        symbol,
        trading_date,
        CASE
            WHEN avg_loss = 0 THEN 100.0
            ELSE 100.0 - (100.0 / (1.0 + (avg_gain / NULLIF(avg_loss, 0))))
        END AS RSI
    FROM WilderSmoothing
);
GO

-- ============================================================================
-- STEP 2: Recreate views to use the functions (preserves same view names)
-- ============================================================================

-- Drop and recreate NASDAQ 100 RSI view
IF OBJECT_ID('dbo.nasdaq_100_rsi_signals', 'V') IS NOT NULL DROP VIEW dbo.nasdaq_100_rsi_signals;
IF OBJECT_ID('dbo.nasdaq_100_RSI_calculation', 'V') IS NOT NULL DROP VIEW dbo.nasdaq_100_RSI_calculation;
GO

CREATE VIEW [dbo].[nasdaq_100_RSI_calculation] AS
    SELECT ticker, trading_date, RSI
    FROM dbo.fn_nasdaq_100_RSI() WITH (NOEXPAND)
    OPTION (MAXRECURSION 0);  -- Allow unlimited recursion
GO

-- Drop and recreate NSE 500 RSI view
IF OBJECT_ID('dbo.nse_500_rsi_signals', 'V') IS NOT NULL DROP VIEW dbo.nse_500_rsi_signals;
IF OBJECT_ID('dbo.nse_500_RSI_calculation', 'V') IS NOT NULL DROP VIEW dbo.nse_500_RSI_calculation;
GO

CREATE VIEW [dbo].[nse_500_RSI_calculation] AS
    SELECT ticker, trading_date, RSI
    FROM dbo.fn_nse_500_RSI() WITH (NOEXPAND)
    OPTION (MAXRECURSION 0);
GO

-- Drop and recreate Forex RSI view
IF OBJECT_ID('dbo.forex_rsi_signals', 'V') IS NOT NULL DROP VIEW dbo.forex_rsi_signals;
IF OBJECT_ID('dbo.forex_RSI_calculation', 'V') IS NOT NULL DROP VIEW dbo.forex_RSI_calculation;
GO

CREATE VIEW [dbo].[forex_RSI_calculation] AS
    SELECT symbol, trading_date, RSI
    FROM dbo.fn_forex_RSI() WITH (NOEXPAND)
    OPTION (MAXRECURSION 0);
GO

-- ============================================================================
-- STEP 3: Recreate signal views (same logic, just depend on updated RSI views)
-- ============================================================================

CREATE VIEW dbo.nasdaq_100_rsi_signals AS
SELECT *,
  CASE
    WHEN RSI < 30 THEN 'Oversold (Buy)'
    WHEN RSI > 70 THEN 'Overbought (Sell)'
    ELSE NULL
  END AS rsi_trade_signal
FROM [dbo].[nasdaq_100_RSI_calculation]
WHERE RSI IS NOT NULL;
GO

CREATE VIEW dbo.nse_500_rsi_signals AS
SELECT *,
  CASE
    WHEN RSI < 30 THEN 'Oversold (Buy)'
    WHEN RSI > 70 THEN 'Overbought (Sell)'
    ELSE NULL
  END AS rsi_trade_signal
FROM dbo.nse_500_RSI_calculation
WHERE RSI IS NOT NULL;
GO

CREATE VIEW dbo.forex_rsi_signals AS
SELECT *,
  CASE
    WHEN RSI < 30 THEN 'Oversold (Buy)'
    WHEN RSI > 70 THEN 'Overbought (Sell)'
    ELSE NULL
  END AS rsi_trade_signal
FROM dbo.forex_RSI_calculation
WHERE RSI IS NOT NULL;
GO
