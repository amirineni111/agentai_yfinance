-- Update Fundamental Screening Views to Include Both NSE and NASDAQ Data
-- This fixes the issue where NASDAQ 100 filter returns no results

USE stockdata_db;
GO

-- Drop existing views
DROP VIEW IF EXISTS vw_fundamental_scoring;
DROP VIEW IF EXISTS vw_value_stocks_screen;
DROP VIEW IF EXISTS vw_quality_stocks_screen;
DROP VIEW IF EXISTS vw_growth_stocks_screen;
DROP VIEW IF EXISTS vw_dividend_stocks_screen;
DROP VIEW IF EXISTS vw_momentum_value_combo;
GO

-- 1. VALUE STOCKS SCREEN (COMBINED NSE + NASDAQ)
CREATE VIEW vw_value_stocks_screen AS
WITH latest_fundamentals AS (
    -- NSE Data
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    
    UNION ALL
    
    -- NASDAQ Data
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nasdaq_100_fundamentals
),
filtered AS (
    SELECT * FROM latest_fundamentals WHERE rn = 1
)
SELECT 
    ticker,
    company_name,
    -- Value Score Calculation (0-100)
    CAST(
        CASE WHEN trailing_pe < 15 THEN 20 ELSE 0 END +
        CASE WHEN price_to_book < 1.5 THEN 25 ELSE 0 END +
        CASE WHEN price_to_sales < 2 THEN 20 ELSE 0 END +
        CASE WHEN peg_ratio < 1 THEN 20 ELSE 0 END +
        CASE WHEN return_on_equity > 0.15 THEN 15 ELSE 0 END
    AS INT) as value_score,
    
    -- Classification
    CASE 
        WHEN trailing_pe < 10 AND price_to_book < 1 THEN 'Deep Value'
        WHEN trailing_pe < 15 AND price_to_book < 1.5 THEN 'Undervalued'
        WHEN trailing_pe < 25 THEN 'Fair Value'
        ELSE 'Overvalued'
    END as valuation_category,
    
    trailing_pe,
    forward_pe,
    price_to_book,
    price_to_sales,
    peg_ratio,
    return_on_equity,
    debt_to_equity,
    market_cap,
    fetch_date
FROM filtered;
GO

-- 2. QUALITY STOCKS SCREEN (COMBINED NSE + NASDAQ)
CREATE VIEW vw_quality_stocks_screen AS
WITH latest_fundamentals AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    UNION ALL
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nasdaq_100_fundamentals
),
filtered AS (
    SELECT * FROM latest_fundamentals WHERE rn = 1
)
SELECT 
    ticker,
    company_name,
    -- Quality Score (0-100)
    CAST(
        CASE WHEN return_on_equity > 0.20 THEN 25 ELSE 0 END +
        CASE WHEN return_on_assets > 0.10 THEN 15 ELSE 0 END +
        CASE WHEN profit_margin > 0.15 THEN 20 ELSE 0 END +
        CASE WHEN debt_to_equity < 0.5 THEN 20 ELSE 0 END +
        CASE WHEN current_ratio > 1.5 THEN 10 ELSE 0 END +
        CASE WHEN free_cashflow > 0 THEN 10 ELSE 0 END
    AS INT) as quality_score,
    
    CASE 
        WHEN return_on_equity > 0.25 AND debt_to_equity < 0.3 THEN 'Excellent'
        WHEN return_on_equity > 0.15 AND debt_to_equity < 0.7 THEN 'Good'
        WHEN return_on_equity > 0.10 THEN 'Average'
        ELSE 'Below Average'
    END as quality_category,
    
    return_on_equity,
    return_on_assets,
    profit_margin,
    operating_margin,
    debt_to_equity,
    current_ratio,
    free_cashflow,
    market_cap,
    fetch_date
FROM filtered;
GO

-- 3. GROWTH STOCKS SCREEN (COMBINED NSE + NASDAQ)
CREATE VIEW vw_growth_stocks_screen AS
WITH latest_fundamentals AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    UNION ALL
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nasdaq_100_fundamentals
),
filtered AS (
    SELECT * FROM latest_fundamentals WHERE rn = 1
)
SELECT 
    ticker,
    company_name,
    -- Growth Score (0-100)
    CAST(
        CASE WHEN revenue_growth > 0.25 THEN 30 WHEN revenue_growth > 0.15 THEN 20 ELSE 0 END +
        CASE WHEN earnings_growth > 0.25 THEN 30 WHEN earnings_growth > 0.15 THEN 20 ELSE 0 END +
        CASE WHEN peg_ratio < 1 THEN 20 WHEN peg_ratio < 1.5 THEN 10 ELSE 0 END +
        CASE WHEN return_on_equity > 0.15 THEN 20 ELSE 0 END
    AS INT) as growth_score,
    
    CASE 
        WHEN revenue_growth > 0.30 AND earnings_growth > 0.30 THEN 'High Growth'
        WHEN revenue_growth > 0.15 AND earnings_growth > 0.15 THEN 'Moderate Growth'
        WHEN revenue_growth > 0 THEN 'Low Growth'
        ELSE 'Declining'
    END as growth_category,
    
    revenue_growth,
    earnings_growth,
    forward_pe,
    peg_ratio,
    profit_margin,
    return_on_equity,
    total_revenue,
    market_cap,
    fetch_date
FROM filtered;
GO

-- 4. DIVIDEND STOCKS SCREEN (COMBINED NSE + NASDAQ)
CREATE VIEW vw_dividend_stocks_screen AS
WITH latest_fundamentals AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    UNION ALL
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nasdaq_100_fundamentals
),
filtered AS (
    SELECT * FROM latest_fundamentals WHERE rn = 1
)
SELECT 
    ticker,
    company_name,
    -- Dividend Score (0-100)
    CAST(
        CASE WHEN dividend_yield > 0.04 THEN 30 WHEN dividend_yield > 0.03 THEN 20 ELSE 0 END +
        CASE WHEN payout_ratio < 0.50 THEN 25 WHEN payout_ratio < 0.75 THEN 15 ELSE 0 END +
        CASE WHEN free_cashflow > 0 THEN 20 ELSE 0 END +
        CASE WHEN debt_to_equity < 1 THEN 15 WHEN debt_to_equity < 1.5 THEN 10 ELSE 0 END +
        CASE WHEN return_on_equity > 0.15 THEN 10 ELSE 0 END
    AS INT) as dividend_score,
    
    CASE 
        WHEN dividend_yield > 0.05 AND payout_ratio < 0.60 THEN 'Excellent Dividend'
        WHEN dividend_yield > 0.03 AND payout_ratio < 0.75 THEN 'Good Dividend'
        WHEN dividend_yield > 0.02 THEN 'Moderate'
        ELSE 'Weak'
    END as dividend_category,
    
    dividend_yield,
    dividend_rate,
    payout_ratio,
    free_cashflow,
    profit_margin,
    debt_to_equity,
    return_on_equity,
    market_cap,
    fetch_date
FROM filtered;
GO

-- 5. GARP STRATEGY (COMBINED NSE + NASDAQ)
CREATE VIEW vw_momentum_value_combo AS
WITH latest_fundamentals AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    UNION ALL
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nasdaq_100_fundamentals
),
filtered AS (
    SELECT * FROM latest_fundamentals WHERE rn = 1
),
latest_signals AS (
    SELECT 
        ticker,
        signal_strength as bullish_strength,
        0 as bearish_strength,
        CASE WHEN signal_strength >= 3 THEN 'Uptrend' ELSE 'Neutral' END as trend,
        signal_date as last_signal_date,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY signal_date DESC) as rn
    FROM signal_tracking_history
    WHERE signal_type = 'BUY'
)
SELECT 
    f.ticker,
    f.company_name,
    -- GARP Score (0-100): Value 40 + Growth 30 + Quality 20 + Momentum 10
    CAST(
        -- Value component (40 points)
        CASE WHEN f.trailing_pe < 15 THEN 15 WHEN f.trailing_pe < 20 THEN 10 ELSE 0 END +
        CASE WHEN f.price_to_book < 2 THEN 15 WHEN f.price_to_book < 3 THEN 8 ELSE 0 END +
        CASE WHEN f.peg_ratio < 1 THEN 10 WHEN f.peg_ratio < 1.5 THEN 5 ELSE 0 END +
        -- Growth component (30 points)
        CASE WHEN f.revenue_growth > 0.15 THEN 15 WHEN f.revenue_growth > 0.10 THEN 10 ELSE 0 END +
        CASE WHEN f.earnings_growth > 0.15 THEN 15 WHEN f.earnings_growth > 0.10 THEN 10 ELSE 0 END +
        -- Quality component (20 points)
        CASE WHEN f.return_on_equity > 0.15 THEN 10 ELSE 0 END +
        CASE WHEN f.debt_to_equity < 1 THEN 10 WHEN f.debt_to_equity < 1.5 THEN 5 ELSE 0 END +
        -- Momentum component (10 points)
        CASE WHEN s.bullish_strength >= 4 THEN 10 WHEN s.bullish_strength >= 3 THEN 7 WHEN s.bullish_strength >= 2 THEN 4 ELSE 0 END
    AS INT) as garp_score,
    
    CASE 
        WHEN f.peg_ratio < 1 AND f.return_on_equity > 0.15 AND s.bullish_strength >= 3 THEN 'Strong BUY'
        WHEN f.peg_ratio < 1.5 AND f.return_on_equity > 0.10 AND s.bullish_strength >= 2 THEN 'BUY'
        WHEN f.peg_ratio > 2 OR f.return_on_equity < 0.05 THEN 'SELL'
        ELSE 'HOLD'
    END as investment_signal,
    
    f.trailing_pe,
    f.price_to_book,
    f.peg_ratio,
    f.return_on_equity,
    f.revenue_growth,
    f.earnings_growth,
    f.debt_to_equity,
    ISNULL(s.bullish_strength, 0) as bullish_strength,
    ISNULL(s.bearish_strength, 0) as bearish_strength,
    ISNULL(s.trend, 'No Signal') as trend,
    s.last_signal_date,
    f.market_cap,
    f.fetch_date
FROM filtered f
LEFT JOIN latest_signals s ON f.ticker = s.ticker AND s.rn = 1;
GO

-- 6. MASTER FUNDAMENTAL SCORING (COMBINED NSE + NASDAQ)
CREATE VIEW vw_fundamental_scoring AS
WITH latest_fundamentals AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    UNION ALL
    SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nasdaq_100_fundamentals
),
filtered AS (
    SELECT * FROM latest_fundamentals WHERE rn = 1
)
SELECT 
    ticker,
    company_name,
    
    -- Individual Scores
    CAST(
        CASE WHEN trailing_pe < 15 THEN 20 ELSE 0 END +
        CASE WHEN price_to_book < 1.5 THEN 25 ELSE 0 END +
        CASE WHEN price_to_sales < 2 THEN 20 ELSE 0 END +
        CASE WHEN peg_ratio < 1 THEN 20 ELSE 0 END +
        CASE WHEN return_on_equity > 0.15 THEN 15 ELSE 0 END
    AS INT) as value_score,
    
    CAST(
        CASE WHEN return_on_equity > 0.20 THEN 25 ELSE 0 END +
        CASE WHEN return_on_assets > 0.10 THEN 15 ELSE 0 END +
        CASE WHEN profit_margin > 0.15 THEN 20 ELSE 0 END +
        CASE WHEN debt_to_equity < 0.5 THEN 20 ELSE 0 END +
        CASE WHEN current_ratio > 1.5 THEN 10 ELSE 0 END +
        CASE WHEN free_cashflow > 0 THEN 10 ELSE 0 END
    AS INT) as quality_score,
    
    CAST(
        CASE WHEN revenue_growth > 0.25 THEN 30 WHEN revenue_growth > 0.15 THEN 20 ELSE 0 END +
        CASE WHEN earnings_growth > 0.25 THEN 30 WHEN earnings_growth > 0.15 THEN 20 ELSE 0 END +
        CASE WHEN peg_ratio < 1 THEN 20 WHEN peg_ratio < 1.5 THEN 10 ELSE 0 END +
        CASE WHEN return_on_equity > 0.15 THEN 20 ELSE 0 END
    AS INT) as growth_score,
    
    CAST(
        CASE WHEN dividend_yield > 0.04 THEN 30 WHEN dividend_yield > 0.03 THEN 20 ELSE 0 END +
        CASE WHEN payout_ratio < 0.50 THEN 25 WHEN payout_ratio < 0.75 THEN 15 ELSE 0 END +
        CASE WHEN free_cashflow > 0 THEN 20 ELSE 0 END +
        CASE WHEN debt_to_equity < 1 THEN 15 WHEN debt_to_equity < 1.5 THEN 10 ELSE 0 END +
        CASE WHEN return_on_equity > 0.15 THEN 10 ELSE 0 END
    AS INT) as dividend_score,
    
    -- Total Score (0-400)
    CAST(
        -- Value (100)
        CASE WHEN trailing_pe < 15 THEN 20 ELSE 0 END +
        CASE WHEN price_to_book < 1.5 THEN 25 ELSE 0 END +
        CASE WHEN price_to_sales < 2 THEN 20 ELSE 0 END +
        CASE WHEN peg_ratio < 1 THEN 20 ELSE 0 END +
        CASE WHEN return_on_equity > 0.15 THEN 15 ELSE 0 END +
        -- Quality (100)
        CASE WHEN return_on_equity > 0.20 THEN 25 ELSE 0 END +
        CASE WHEN return_on_assets > 0.10 THEN 15 ELSE 0 END +
        CASE WHEN profit_margin > 0.15 THEN 20 ELSE 0 END +
        CASE WHEN debt_to_equity < 0.5 THEN 20 ELSE 0 END +
        CASE WHEN current_ratio > 1.5 THEN 10 ELSE 0 END +
        CASE WHEN free_cashflow > 0 THEN 10 ELSE 0 END +
        -- Growth (100)
        CASE WHEN revenue_growth > 0.25 THEN 30 WHEN revenue_growth > 0.15 THEN 20 ELSE 0 END +
        CASE WHEN earnings_growth > 0.25 THEN 30 WHEN earnings_growth > 0.15 THEN 20 ELSE 0 END +
        CASE WHEN peg_ratio < 1 THEN 20 WHEN peg_ratio < 1.5 THEN 10 ELSE 0 END +
        CASE WHEN return_on_equity > 0.15 THEN 20 ELSE 0 END +
        -- Dividend (100)
        CASE WHEN dividend_yield > 0.04 THEN 30 WHEN dividend_yield > 0.03 THEN 20 ELSE 0 END +
        CASE WHEN payout_ratio < 0.50 THEN 25 WHEN payout_ratio < 0.75 THEN 15 ELSE 0 END +
        CASE WHEN free_cashflow > 0 THEN 20 ELSE 0 END +
        CASE WHEN debt_to_equity < 1 THEN 15 WHEN debt_to_equity < 1.5 THEN 10 ELSE 0 END +
        CASE WHEN return_on_equity > 0.15 THEN 10 ELSE 0 END
    AS INT) as total_score,
    
    -- Overall Rating
    CASE 
        WHEN (
            CASE WHEN trailing_pe < 15 THEN 20 ELSE 0 END +
            CASE WHEN price_to_book < 1.5 THEN 25 ELSE 0 END +
            CASE WHEN price_to_sales < 2 THEN 20 ELSE 0 END +
            CASE WHEN peg_ratio < 1 THEN 20 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 15 ELSE 0 END +
            CASE WHEN return_on_equity > 0.20 THEN 25 ELSE 0 END +
            CASE WHEN return_on_assets > 0.10 THEN 15 ELSE 0 END +
            CASE WHEN profit_margin > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN debt_to_equity < 0.5 THEN 20 ELSE 0 END +
            CASE WHEN current_ratio > 1.5 THEN 10 ELSE 0 END +
            CASE WHEN free_cashflow > 0 THEN 10 ELSE 0 END +
            CASE WHEN revenue_growth > 0.25 THEN 30 WHEN revenue_growth > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN earnings_growth > 0.25 THEN 30 WHEN earnings_growth > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN peg_ratio < 1 THEN 20 WHEN peg_ratio < 1.5 THEN 10 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN dividend_yield > 0.04 THEN 30 WHEN dividend_yield > 0.03 THEN 20 ELSE 0 END +
            CASE WHEN payout_ratio < 0.50 THEN 25 WHEN payout_ratio < 0.75 THEN 15 ELSE 0 END +
            CASE WHEN free_cashflow > 0 THEN 20 ELSE 0 END +
            CASE WHEN debt_to_equity < 1 THEN 15 WHEN debt_to_equity < 1.5 THEN 10 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 10 ELSE 0 END
        ) >= 300 THEN 'A+'
        WHEN (
            CASE WHEN trailing_pe < 15 THEN 20 ELSE 0 END +
            CASE WHEN price_to_book < 1.5 THEN 25 ELSE 0 END +
            CASE WHEN price_to_sales < 2 THEN 20 ELSE 0 END +
            CASE WHEN peg_ratio < 1 THEN 20 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 15 ELSE 0 END +
            CASE WHEN return_on_equity > 0.20 THEN 25 ELSE 0 END +
            CASE WHEN return_on_assets > 0.10 THEN 15 ELSE 0 END +
            CASE WHEN profit_margin > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN debt_to_equity < 0.5 THEN 20 ELSE 0 END +
            CASE WHEN current_ratio > 1.5 THEN 10 ELSE 0 END +
            CASE WHEN free_cashflow > 0 THEN 10 ELSE 0 END +
            CASE WHEN revenue_growth > 0.25 THEN 30 WHEN revenue_growth > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN earnings_growth > 0.25 THEN 30 WHEN earnings_growth > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN peg_ratio < 1 THEN 20 WHEN peg_ratio < 1.5 THEN 10 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN dividend_yield > 0.04 THEN 30 WHEN dividend_yield > 0.03 THEN 20 ELSE 0 END +
            CASE WHEN payout_ratio < 0.50 THEN 25 WHEN payout_ratio < 0.75 THEN 15 ELSE 0 END +
            CASE WHEN free_cashflow > 0 THEN 20 ELSE 0 END +
            CASE WHEN debt_to_equity < 1 THEN 15 WHEN debt_to_equity < 1.5 THEN 10 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 10 ELSE 0 END
        ) >= 250 THEN 'A'
        WHEN (
            CASE WHEN trailing_pe < 15 THEN 20 ELSE 0 END +
            CASE WHEN price_to_book < 1.5 THEN 25 ELSE 0 END +
            CASE WHEN price_to_sales < 2 THEN 20 ELSE 0 END +
            CASE WHEN peg_ratio < 1 THEN 20 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 15 ELSE 0 END +
            CASE WHEN return_on_equity > 0.20 THEN 25 ELSE 0 END +
            CASE WHEN return_on_assets > 0.10 THEN 15 ELSE 0 END +
            CASE WHEN profit_margin > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN debt_to_equity < 0.5 THEN 20 ELSE 0 END +
            CASE WHEN current_ratio > 1.5 THEN 10 ELSE 0 END +
            CASE WHEN free_cashflow > 0 THEN 10 ELSE 0 END +
            CASE WHEN revenue_growth > 0.25 THEN 30 WHEN revenue_growth > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN earnings_growth > 0.25 THEN 30 WHEN earnings_growth > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN peg_ratio < 1 THEN 20 WHEN peg_ratio < 1.5 THEN 10 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN dividend_yield > 0.04 THEN 30 WHEN dividend_yield > 0.03 THEN 20 ELSE 0 END +
            CASE WHEN payout_ratio < 0.50 THEN 25 WHEN payout_ratio < 0.75 THEN 15 ELSE 0 END +
            CASE WHEN free_cashflow > 0 THEN 20 ELSE 0 END +
            CASE WHEN debt_to_equity < 1 THEN 15 WHEN debt_to_equity < 1.5 THEN 10 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 10 ELSE 0 END
        ) >= 200 THEN 'B'
        WHEN (
            CASE WHEN trailing_pe < 15 THEN 20 ELSE 0 END +
            CASE WHEN price_to_book < 1.5 THEN 25 ELSE 0 END +
            CASE WHEN price_to_sales < 2 THEN 20 ELSE 0 END +
            CASE WHEN peg_ratio < 1 THEN 20 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 15 ELSE 0 END +
            CASE WHEN return_on_equity > 0.20 THEN 25 ELSE 0 END +
            CASE WHEN return_on_assets > 0.10 THEN 15 ELSE 0 END +
            CASE WHEN profit_margin > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN debt_to_equity < 0.5 THEN 20 ELSE 0 END +
            CASE WHEN current_ratio > 1.5 THEN 10 ELSE 0 END +
            CASE WHEN free_cashflow > 0 THEN 10 ELSE 0 END +
            CASE WHEN revenue_growth > 0.25 THEN 30 WHEN revenue_growth > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN earnings_growth > 0.25 THEN 30 WHEN earnings_growth > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN peg_ratio < 1 THEN 20 WHEN peg_ratio < 1.5 THEN 10 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 20 ELSE 0 END +
            CASE WHEN dividend_yield > 0.04 THEN 30 WHEN dividend_yield > 0.03 THEN 20 ELSE 0 END +
            CASE WHEN payout_ratio < 0.50 THEN 25 WHEN payout_ratio < 0.75 THEN 15 ELSE 0 END +
            CASE WHEN free_cashflow > 0 THEN 20 ELSE 0 END +
            CASE WHEN debt_to_equity < 1 THEN 15 WHEN debt_to_equity < 1.5 THEN 10 ELSE 0 END +
            CASE WHEN return_on_equity > 0.15 THEN 10 ELSE 0 END
        ) >= 150 THEN 'C'
        ELSE 'D'
    END as overall_rating,
    
    -- Key Metrics
    trailing_pe,
    price_to_book,
    return_on_equity,
    revenue_growth,
    dividend_yield,
    market_cap,
    fetch_date
FROM filtered;
GO

PRINT 'All fundamental screening views updated successfully to include both NSE and NASDAQ data!';
