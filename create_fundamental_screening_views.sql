-- =====================================================
-- Fundamental Analysis Screening Views for Value Investing
-- =====================================================
-- These views leverage fundamental data for stock screening

-- Drop existing views if they exist
IF OBJECT_ID('dbo.vw_value_stocks_screen', 'V') IS NOT NULL
    DROP VIEW dbo.vw_value_stocks_screen;
GO

IF OBJECT_ID('dbo.vw_quality_stocks_screen', 'V') IS NOT NULL
    DROP VIEW dbo.vw_quality_stocks_screen;
GO

IF OBJECT_ID('dbo.vw_growth_stocks_screen', 'V') IS NOT NULL
    DROP VIEW dbo.vw_growth_stocks_screen;
GO

IF OBJECT_ID('dbo.vw_dividend_stocks_screen', 'V') IS NOT NULL
    DROP VIEW dbo.vw_dividend_stocks_screen;
GO

IF OBJECT_ID('dbo.vw_momentum_value_combo', 'V') IS NOT NULL
    DROP VIEW dbo.vw_momentum_value_combo;
GO

IF OBJECT_ID('dbo.vw_fundamental_scoring', 'V') IS NOT NULL
    DROP VIEW dbo.vw_fundamental_scoring;
GO

-- =====================================================
-- 1. VALUE STOCKS SCREENER
-- Classic value investing metrics (Graham, Buffett style)
-- =====================================================
CREATE VIEW dbo.vw_value_stocks_screen AS
WITH latest_fundamentals AS (
    SELECT 
        ticker,
        company_name,
        fetch_date,
        trailing_pe,
        forward_pe,
        price_to_book,
        price_to_sales,
        peg_ratio,
        book_value,
        return_on_equity,
        debt_to_equity,
        current_ratio,
        market_cap,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    WHERE trailing_pe IS NOT NULL
)
SELECT 
    ticker,
    company_name,
    fetch_date,
    trailing_pe,
    forward_pe,
    price_to_book,
    price_to_sales,
    peg_ratio,
    book_value,
    return_on_equity,
    debt_to_equity,
    current_ratio,
    market_cap,
    
    -- Value Score (0-100, higher is better)
    CAST(
        (CASE WHEN trailing_pe < 15 THEN 20 WHEN trailing_pe < 25 THEN 10 ELSE 0 END) +
        (CASE WHEN price_to_book < 1.5 THEN 25 WHEN price_to_book < 3 THEN 15 ELSE 0 END) +
        (CASE WHEN price_to_sales < 2 THEN 20 WHEN price_to_sales < 4 THEN 10 ELSE 0 END) +
        (CASE WHEN peg_ratio < 1 THEN 20 WHEN peg_ratio < 2 THEN 10 ELSE 0 END) +
        (CASE WHEN return_on_equity > 0.15 THEN 15 WHEN return_on_equity > 0.10 THEN 8 ELSE 0 END)
    AS INT) as value_score,
    
    -- Classification
    CASE 
        WHEN trailing_pe < 15 AND price_to_book < 1.5 AND return_on_equity > 0.15 THEN 'Deep Value'
        WHEN trailing_pe < 20 AND price_to_book < 2 AND return_on_equity > 0.10 THEN 'Undervalued'
        WHEN trailing_pe < 25 AND price_to_book < 3 THEN 'Fair Value'
        ELSE 'Overvalued'
    END as valuation_category
    
FROM latest_fundamentals
WHERE rn = 1 AND market_cap > 1000000000; -- Market cap > 100 Cr
GO

-- =====================================================
-- 2. QUALITY STOCKS SCREENER
-- Focus on profitability, efficiency, and financial health
-- =====================================================
CREATE VIEW dbo.vw_quality_stocks_screen AS
WITH latest_fundamentals AS (
    SELECT 
        ticker,
        company_name,
        fetch_date,
        return_on_equity,
        return_on_assets,
        profit_margin,
        operating_margin,
        gross_margin,
        debt_to_equity,
        current_ratio,
        quick_ratio,
        free_cashflow,
        operating_cashflow,
        market_cap,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    WHERE return_on_equity IS NOT NULL
)
SELECT 
    ticker,
    company_name,
    fetch_date,
    return_on_equity,
    return_on_assets,
    profit_margin,
    operating_margin,
    gross_margin,
    debt_to_equity,
    current_ratio,
    quick_ratio,
    free_cashflow,
    operating_cashflow,
    market_cap,
    
    -- Quality Score (0-100, higher is better)
    CAST(
        (CASE WHEN return_on_equity > 0.20 THEN 25 WHEN return_on_equity > 0.15 THEN 15 WHEN return_on_equity > 0.10 THEN 10 ELSE 0 END) +
        (CASE WHEN return_on_assets > 0.10 THEN 15 WHEN return_on_assets > 0.05 THEN 10 ELSE 0 END) +
        (CASE WHEN profit_margin > 0.15 THEN 20 WHEN profit_margin > 0.10 THEN 12 WHEN profit_margin > 0.05 THEN 6 ELSE 0 END) +
        (CASE WHEN debt_to_equity < 0.5 THEN 20 WHEN debt_to_equity < 1 THEN 12 WHEN debt_to_equity < 2 THEN 6 ELSE 0 END) +
        (CASE WHEN current_ratio > 1.5 THEN 10 WHEN current_ratio > 1.0 THEN 6 ELSE 0 END) +
        (CASE WHEN free_cashflow > 0 THEN 10 ELSE 0 END)
    AS INT) as quality_score,
    
    -- Classification
    CASE 
        WHEN return_on_equity > 0.20 AND debt_to_equity < 0.5 AND profit_margin > 0.15 THEN 'Excellent'
        WHEN return_on_equity > 0.15 AND debt_to_equity < 1 AND profit_margin > 0.10 THEN 'Good'
        WHEN return_on_equity > 0.10 AND debt_to_equity < 2 THEN 'Average'
        ELSE 'Weak'
    END as quality_category
    
FROM latest_fundamentals
WHERE rn = 1 AND market_cap > 1000000000;
GO

-- =====================================================
-- 3. GROWTH STOCKS SCREENER
-- Focus on revenue and earnings growth
-- =====================================================
CREATE VIEW dbo.vw_growth_stocks_screen AS
WITH latest_fundamentals AS (
    SELECT 
        ticker,
        company_name,
        fetch_date,
        revenue_growth,
        earnings_growth,
        forward_pe,
        peg_ratio,
        profit_margin,
        operating_margin,
        return_on_equity,
        market_cap,
        total_revenue,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    WHERE revenue_growth IS NOT NULL OR earnings_growth IS NOT NULL
)
SELECT 
    ticker,
    company_name,
    fetch_date,
    revenue_growth,
    earnings_growth,
    forward_pe,
    peg_ratio,
    profit_margin,
    operating_margin,
    return_on_equity,
    market_cap,
    total_revenue,
    
    -- Growth Score (0-100, higher is better)
    CAST(
        (CASE WHEN revenue_growth > 0.25 THEN 30 WHEN revenue_growth > 0.15 THEN 20 WHEN revenue_growth > 0.10 THEN 10 ELSE 0 END) +
        (CASE WHEN earnings_growth > 0.25 THEN 30 WHEN earnings_growth > 0.15 THEN 20 WHEN earnings_growth > 0.10 THEN 10 ELSE 0 END) +
        (CASE WHEN peg_ratio < 1 THEN 20 WHEN peg_ratio < 1.5 THEN 12 WHEN peg_ratio < 2 THEN 6 ELSE 0 END) +
        (CASE WHEN return_on_equity > 0.15 THEN 20 WHEN return_on_equity > 0.10 THEN 12 ELSE 0 END)
    AS INT) as growth_score,
    
    -- Classification
    CASE 
        WHEN revenue_growth > 0.25 AND earnings_growth > 0.25 AND peg_ratio < 1.5 THEN 'High Growth'
        WHEN revenue_growth > 0.15 AND earnings_growth > 0.15 THEN 'Moderate Growth'
        WHEN revenue_growth > 0.05 OR earnings_growth > 0.05 THEN 'Slow Growth'
        ELSE 'Stagnant/Declining'
    END as growth_category
    
FROM latest_fundamentals
WHERE rn = 1 AND market_cap > 1000000000;
GO

-- =====================================================
-- 4. DIVIDEND STOCKS SCREENER
-- Focus on dividend yield and sustainability
-- =====================================================
CREATE VIEW dbo.vw_dividend_stocks_screen AS
WITH latest_fundamentals AS (
    SELECT 
        ticker,
        company_name,
        fetch_date,
        dividend_rate,
        dividend_yield,
        payout_ratio,
        free_cashflow,
        profit_margin,
        debt_to_equity,
        return_on_equity,
        market_cap,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    WHERE dividend_yield IS NOT NULL AND dividend_yield > 0
)
SELECT 
    ticker,
    company_name,
    fetch_date,
    dividend_rate,
    dividend_yield,
    payout_ratio,
    free_cashflow,
    profit_margin,
    debt_to_equity,
    return_on_equity,
    market_cap,
    
    -- Dividend Score (0-100, higher is better)
    CAST(
        (CASE WHEN dividend_yield > 0.04 THEN 30 WHEN dividend_yield > 0.03 THEN 20 WHEN dividend_yield > 0.02 THEN 10 ELSE 0 END) +
        (CASE WHEN payout_ratio < 0.50 THEN 25 WHEN payout_ratio < 0.70 THEN 15 WHEN payout_ratio < 0.80 THEN 8 ELSE 0 END) +
        (CASE WHEN free_cashflow > 0 THEN 20 ELSE 0 END) +
        (CASE WHEN debt_to_equity < 1 THEN 15 WHEN debt_to_equity < 2 THEN 8 ELSE 0 END) +
        (CASE WHEN return_on_equity > 0.15 THEN 10 WHEN return_on_equity > 0.10 THEN 6 ELSE 0 END)
    AS INT) as dividend_score,
    
    -- Classification
    CASE 
        WHEN dividend_yield > 0.04 AND payout_ratio < 0.60 AND free_cashflow > 0 THEN 'Excellent Dividend'
        WHEN dividend_yield > 0.03 AND payout_ratio < 0.75 THEN 'Good Dividend'
        WHEN dividend_yield > 0.02 THEN 'Moderate Dividend'
        ELSE 'Low Dividend'
    END as dividend_category
    
FROM latest_fundamentals
WHERE rn = 1 AND market_cap > 1000000000;
GO

-- =====================================================
-- 5. MOMENTUM + VALUE COMBO (GARP Strategy)
-- Combines technical signals with fundamental value
-- =====================================================
CREATE VIEW dbo.vw_momentum_value_combo AS
WITH latest_fundamentals AS (
    SELECT 
        ticker,
        company_name,
        fetch_date,
        trailing_pe,
        price_to_book,
        peg_ratio,
        return_on_equity,
        revenue_growth,
        earnings_growth,
        debt_to_equity,
        market_cap,
        fifty_two_week_high,
        fifty_two_week_low,
        fifty_day_avg,
        two_hundred_day_avg,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
),
recent_signals AS (
    SELECT 
        ticker,
        MAX(signal_date) as last_signal_date,
        MAX(CASE WHEN signal_type = 'BULLISH' THEN signal_strength ELSE 0 END) as bullish_strength,
        MAX(CASE WHEN signal_type = 'BEARISH' THEN signal_strength ELSE 0 END) as bearish_strength
    FROM signal_tracking_history
    WHERE signal_date >= DATEADD(day, -30, GETDATE())
    GROUP BY ticker
)
SELECT 
    f.ticker,
    f.company_name,
    f.fetch_date,
    f.trailing_pe,
    f.price_to_book,
    f.peg_ratio,
    f.return_on_equity,
    f.revenue_growth,
    f.earnings_growth,
    f.debt_to_equity,
    f.market_cap,
    
    -- Technical indicators
    s.last_signal_date,
    s.bullish_strength,
    s.bearish_strength,
    
    -- Price momentum
    CASE 
        WHEN f.fifty_day_avg > f.two_hundred_day_avg THEN 'Uptrend'
        WHEN f.fifty_day_avg < f.two_hundred_day_avg THEN 'Downtrend'
        ELSE 'Neutral'
    END as trend,
    
    -- Combined GARP Score (Growth at Reasonable Price)
    CAST(
        -- Value component (40 points)
        (CASE WHEN f.trailing_pe < 15 THEN 15 WHEN f.trailing_pe < 20 THEN 10 WHEN f.trailing_pe < 25 THEN 5 ELSE 0 END) +
        (CASE WHEN f.price_to_book < 2 THEN 15 WHEN f.price_to_book < 3 THEN 8 ELSE 0 END) +
        (CASE WHEN f.peg_ratio < 1 THEN 10 WHEN f.peg_ratio < 1.5 THEN 6 ELSE 0 END) +
        
        -- Growth component (30 points)
        (CASE WHEN f.revenue_growth > 0.15 THEN 15 WHEN f.revenue_growth > 0.10 THEN 10 ELSE 0 END) +
        (CASE WHEN f.earnings_growth > 0.15 THEN 15 WHEN f.earnings_growth > 0.10 THEN 10 ELSE 0 END) +
        
        -- Quality component (20 points)
        (CASE WHEN f.return_on_equity > 0.15 THEN 15 WHEN f.return_on_equity > 0.10 THEN 8 ELSE 0 END) +
        (CASE WHEN f.debt_to_equity < 1 THEN 5 ELSE 0 END) +
        
        -- Momentum component (10 points)
        (CASE WHEN s.bullish_strength >= 4 THEN 10 WHEN s.bullish_strength >= 3 THEN 6 WHEN s.bullish_strength >= 2 THEN 3 ELSE 0 END)
    AS INT) as garp_score,
    
    -- Investment Category
    CASE 
        WHEN f.trailing_pe < 15 AND f.peg_ratio < 1 AND f.revenue_growth > 0.15 AND s.bullish_strength >= 3 THEN 'BUY - Strong GARP'
        WHEN f.trailing_pe < 20 AND f.peg_ratio < 1.5 AND f.revenue_growth > 0.10 AND s.bullish_strength >= 2 THEN 'BUY - Good GARP'
        WHEN f.trailing_pe < 25 AND f.revenue_growth > 0.05 THEN 'HOLD - Moderate'
        WHEN s.bearish_strength >= 3 THEN 'SELL - Technical Weakness'
        ELSE 'WATCH'
    END as investment_signal
    
FROM latest_fundamentals f
LEFT JOIN recent_signals s ON f.ticker = s.ticker
WHERE f.rn = 1 AND f.market_cap > 1000000000;
GO

-- =====================================================
-- 6. COMPREHENSIVE FUNDAMENTAL SCORING
-- Master view combining all metrics
-- =====================================================
CREATE VIEW dbo.vw_fundamental_scoring AS
SELECT 
    v.ticker,
    v.company_name,
    v.fetch_date,
    v.market_cap,
    
    -- Value Metrics
    v.value_score,
    v.valuation_category,
    v.trailing_pe,
    v.price_to_book,
    
    -- Quality Metrics
    q.quality_score,
    q.quality_category,
    q.return_on_equity,
    q.debt_to_equity,
    q.profit_margin,
    
    -- Growth Metrics
    g.growth_score,
    g.growth_category,
    g.revenue_growth,
    g.earnings_growth,
    
    -- Dividend Metrics
    d.dividend_score,
    d.dividend_category,
    d.dividend_yield,
    
    -- Combined Total Score (0-400)
    (v.value_score + q.quality_score + g.growth_score + ISNULL(d.dividend_score, 0)) as total_score,
    
    -- Overall Rating
    CASE 
        WHEN (v.value_score + q.quality_score + g.growth_score + ISNULL(d.dividend_score, 0)) >= 300 THEN 'A+ Exceptional'
        WHEN (v.value_score + q.quality_score + g.growth_score + ISNULL(d.dividend_score, 0)) >= 250 THEN 'A Strong Buy'
        WHEN (v.value_score + q.quality_score + g.growth_score + ISNULL(d.dividend_score, 0)) >= 200 THEN 'B Buy'
        WHEN (v.value_score + q.quality_score + g.growth_score + ISNULL(d.dividend_score, 0)) >= 150 THEN 'C Hold'
        ELSE 'D Avoid'
    END as overall_rating
    
FROM vw_value_stocks_screen v
LEFT JOIN vw_quality_stocks_screen q ON v.ticker = q.ticker
LEFT JOIN vw_growth_stocks_screen g ON v.ticker = g.ticker
LEFT JOIN vw_dividend_stocks_screen d ON v.ticker = d.ticker;
GO

PRINT '================================================================';
PRINT 'Fundamental Screening Views Created Successfully!';
PRINT '================================================================';
PRINT '';
PRINT 'Created 6 Views:';
PRINT '  1. vw_value_stocks_screen - Classic value investing metrics';
PRINT '  2. vw_quality_stocks_screen - Profitability & financial health';
PRINT '  3. vw_growth_stocks_screen - Revenue & earnings growth';
PRINT '  4. vw_dividend_stocks_screen - Dividend yield & sustainability';
PRINT '  5. vw_momentum_value_combo - Technical + Fundamental (GARP)';
PRINT '  6. vw_fundamental_scoring - Master scoring view';
PRINT '';
PRINT 'Usage Examples:';
PRINT '  -- Top 10 value stocks:';
PRINT '  SELECT TOP 10 * FROM vw_value_stocks_screen ORDER BY value_score DESC';
PRINT '';
PRINT '  -- High quality + undervalued:';
PRINT '  SELECT * FROM vw_fundamental_scoring WHERE quality_score > 70 AND value_score > 60';
PRINT '';
PRINT '  -- GARP stocks with technical confirmation:';
PRINT '  SELECT * FROM vw_momentum_value_combo WHERE investment_signal LIKE ''BUY%'' ORDER BY garp_score DESC';
