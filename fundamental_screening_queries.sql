-- =====================================================
-- FUNDAMENTAL SCREENING QUERY EXAMPLES
-- Practical queries for value investing
-- =====================================================

-- ========== VALUE INVESTING STRATEGIES ==========

-- 1. Deep Value Stocks (Graham-style)
-- P/E < 15, P/B < 1.5, ROE > 15%, Debt/Equity < 1
SELECT TOP 20
    ticker,
    company_name,
    value_score,
    trailing_pe,
    price_to_book,
    return_on_equity,
    debt_to_equity,
    market_cap
FROM vw_value_stocks_screen
WHERE 
    trailing_pe < 15
    AND price_to_book < 1.5
    AND return_on_equity > 0.15
    AND debt_to_equity < 1
ORDER BY value_score DESC;

-- 2. Quality + Value Combo (Buffett-style)
-- High quality business at reasonable price
SELECT TOP 20
    f.ticker,
    f.company_name,
    f.total_score,
    f.overall_rating,
    f.value_score,
    f.quality_score,
    v.trailing_pe,
    q.return_on_equity,
    q.profit_margin,
    q.debt_to_equity
FROM vw_fundamental_scoring f
INNER JOIN vw_value_stocks_screen v ON f.ticker = v.ticker
INNER JOIN vw_quality_stocks_screen q ON f.ticker = q.ticker
WHERE 
    f.quality_score >= 70
    AND f.value_score >= 50
    AND q.debt_to_equity < 1.5
ORDER BY f.total_score DESC;

-- 3. Dividend Aristocrats
-- High dividend yield with sustainable payout
SELECT TOP 20
    ticker,
    company_name,
    dividend_score,
    dividend_yield * 100 as dividend_yield_pct,
    payout_ratio * 100 as payout_ratio_pct,
    free_cashflow / 10000000 as fcf_crores,
    return_on_equity * 100 as roe_pct,
    debt_to_equity
FROM vw_dividend_stocks_screen
WHERE 
    dividend_yield > 0.03
    AND payout_ratio < 0.70
    AND free_cashflow > 0
    AND debt_to_equity < 1.5
ORDER BY dividend_score DESC;

-- 4. Growth at Reasonable Price (GARP)
-- High growth + reasonable valuation
SELECT TOP 20
    ticker,
    company_name,
    growth_score,
    revenue_growth * 100 as rev_growth_pct,
    earnings_growth * 100 as earn_growth_pct,
    peg_ratio,
    forward_pe,
    return_on_equity * 100 as roe_pct
FROM vw_growth_stocks_screen
WHERE 
    revenue_growth > 0.15
    AND earnings_growth > 0.15
    AND peg_ratio < 1.5
    AND forward_pe < 25
ORDER BY growth_score DESC;

-- 5. High Quality Franchises
-- Best-in-class businesses regardless of price
SELECT TOP 20
    ticker,
    company_name,
    quality_score,
    quality_category,
    return_on_equity * 100 as roe_pct,
    profit_margin * 100 as margin_pct,
    debt_to_equity,
    current_ratio,
    free_cashflow / 10000000 as fcf_crores
FROM vw_quality_stocks_screen
WHERE 
    return_on_equity > 0.20
    AND profit_margin > 0.15
    AND debt_to_equity < 0.5
    AND free_cashflow > 0
ORDER BY quality_score DESC;

-- ========== COMBINED STRATEGIES ==========

-- 6. Triple A Stocks (Value + Quality + Growth)
-- Stocks scoring high on all dimensions
SELECT TOP 20
    f.ticker,
    f.company_name,
    f.total_score,
    f.overall_rating,
    f.value_score,
    f.quality_score,
    f.growth_score,
    f.dividend_score,
    v.trailing_pe,
    q.return_on_equity * 100 as roe_pct,
    g.revenue_growth * 100 as growth_pct
FROM vw_fundamental_scoring f
INNER JOIN vw_value_stocks_screen v ON f.ticker = v.ticker
INNER JOIN vw_quality_stocks_screen q ON f.ticker = q.ticker
INNER JOIN vw_growth_stocks_screen g ON f.ticker = g.ticker
WHERE 
    f.value_score >= 60
    AND f.quality_score >= 70
    AND f.growth_score >= 50
ORDER BY f.total_score DESC;

-- 7. Contrarian Plays (Undervalued + Recent Technical Signals)
-- Value stocks showing technical buy signals
SELECT TOP 20
    m.ticker,
    m.company_name,
    m.garp_score,
    m.investment_signal,
    m.trailing_pe,
    m.price_to_book,
    m.revenue_growth * 100 as growth_pct,
    m.bullish_strength,
    m.trend,
    m.last_signal_date
FROM vw_momentum_value_combo m
WHERE 
    m.trailing_pe < 20
    AND m.price_to_book < 2
    AND m.bullish_strength >= 3
    AND m.trend = 'Uptrend'
ORDER BY m.garp_score DESC;

-- 8. Turnaround Candidates
-- Improving fundamentals (compare latest vs historical)
WITH prev_quarter AS (
    SELECT 
        ticker,
        revenue_growth as prev_rev_growth,
        earnings_growth as prev_earn_growth,
        return_on_equity as prev_roe,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fetch_date DESC) as rn
    FROM nse_500_fundamentals
    WHERE fetch_date < (SELECT MAX(fetch_date) - 7 FROM nse_500_fundamentals)
)
SELECT TOP 20
    g.ticker,
    g.company_name,
    g.revenue_growth * 100 as current_rev_growth_pct,
    pq.prev_rev_growth * 100 as prev_rev_growth_pct,
    (g.revenue_growth - pq.prev_rev_growth) * 100 as improvement_pct,
    g.forward_pe,
    g.peg_ratio
FROM vw_growth_stocks_screen g
INNER JOIN prev_quarter pq ON g.ticker = pq.ticker AND pq.rn = 1
WHERE 
    g.revenue_growth > pq.prev_rev_growth
    AND g.forward_pe < 25
ORDER BY (g.revenue_growth - pq.prev_rev_growth) DESC;

-- ========== RISK ASSESSMENT ==========

-- 9. Safe Havens (Low debt + High quality)
-- Conservative investments for risk-averse investors
SELECT TOP 20
    q.ticker,
    q.company_name,
    q.quality_score,
    q.return_on_equity * 100 as roe_pct,
    q.profit_margin * 100 as margin_pct,
    q.debt_to_equity,
    q.current_ratio,
    q.quick_ratio,
    d.dividend_yield * 100 as div_yield_pct
FROM vw_quality_stocks_screen q
LEFT JOIN vw_dividend_stocks_screen d ON q.ticker = d.ticker
WHERE 
    q.debt_to_equity < 0.5
    AND q.current_ratio > 1.5
    AND q.return_on_equity > 0.15
ORDER BY q.quality_score DESC;

-- 10. Red Flags (Avoid these)
-- Stocks with concerning fundamentals
SELECT 
    ticker,
    company_name,
    trailing_pe,
    price_to_book,
    debt_to_equity,
    current_ratio,
    profit_margin * 100 as margin_pct,
    return_on_equity * 100 as roe_pct,
    CASE 
        WHEN debt_to_equity > 3 THEN 'High Debt Risk'
        WHEN current_ratio < 1 THEN 'Liquidity Crisis'
        WHEN profit_margin < 0 THEN 'Unprofitable'
        WHEN return_on_equity < 0.05 THEN 'Weak Returns'
        WHEN trailing_pe > 50 THEN 'Overvalued'
    END as red_flag
FROM vw_value_stocks_screen
WHERE 
    debt_to_equity > 3
    OR current_ratio < 1
    OR profit_margin < 0
    OR return_on_equity < 0.05
    OR trailing_pe > 50
ORDER BY debt_to_equity DESC;

-- ========== PORTFOLIO CONSTRUCTION ==========

-- 11. Balanced Portfolio Mix
-- Diversified allocation across strategies
(
    SELECT TOP 5 ticker, company_name, 'Deep Value' as strategy, value_score as score
    FROM vw_value_stocks_screen 
    WHERE valuation_category = 'Deep Value'
    ORDER BY value_score DESC
)
UNION ALL
(
    SELECT TOP 5 ticker, company_name, 'High Quality' as strategy, quality_score as score
    FROM vw_quality_stocks_screen 
    WHERE quality_category = 'Excellent'
    ORDER BY quality_score DESC
)
UNION ALL
(
    SELECT TOP 5 ticker, company_name, 'High Growth' as strategy, growth_score as score
    FROM vw_growth_stocks_screen 
    WHERE growth_category = 'High Growth'
    ORDER BY growth_score DESC
)
UNION ALL
(
    SELECT TOP 5 ticker, company_name, 'Dividend' as strategy, dividend_score as score
    FROM vw_dividend_stocks_screen 
    WHERE dividend_category = 'Excellent Dividend'
    ORDER BY dividend_score DESC
);

-- 12. Market Cap Segmentation
-- Small, Mid, and Large cap opportunities
SELECT 
    CASE 
        WHEN market_cap < 50000000000 THEN 'Small Cap'
        WHEN market_cap < 200000000000 THEN 'Mid Cap'
        ELSE 'Large Cap'
    END as market_cap_category,
    COUNT(*) as stock_count,
    AVG(total_score) as avg_score,
    AVG(value_score) as avg_value,
    AVG(quality_score) as avg_quality,
    AVG(growth_score) as avg_growth
FROM vw_fundamental_scoring
WHERE overall_rating IN ('A+ Exceptional', 'A Strong Buy')
GROUP BY 
    CASE 
        WHEN market_cap < 50000000000 THEN 'Small Cap'
        WHEN market_cap < 200000000000 THEN 'Mid Cap'
        ELSE 'Large Cap'
    END
ORDER BY avg_score DESC;

-- ========== WEEKLY MONITORING ==========

-- 13. Track Fundamental Changes
-- Compare week-over-week changes (for weekly job)
WITH current_week AS (
    SELECT ticker, trailing_pe, price_to_book, return_on_equity, debt_to_equity
    FROM nse_500_fundamentals
    WHERE fetch_date = (SELECT MAX(fetch_date) FROM nse_500_fundamentals)
),
prev_week AS (
    SELECT ticker, trailing_pe, price_to_book, return_on_equity, debt_to_equity
    FROM nse_500_fundamentals
    WHERE fetch_date = (SELECT MAX(fetch_date) - 7 FROM nse_500_fundamentals)
)
SELECT TOP 30
    c.ticker,
    c.trailing_pe as current_pe,
    p.trailing_pe as prev_pe,
    ((c.trailing_pe - p.trailing_pe) / NULLIF(p.trailing_pe, 0)) * 100 as pe_change_pct,
    c.price_to_book as current_pb,
    p.price_to_book as prev_pb,
    ((c.price_to_book - p.price_to_book) / NULLIF(p.price_to_book, 0)) * 100 as pb_change_pct
FROM current_week c
INNER JOIN prev_week p ON c.ticker = p.ticker
WHERE 
    ABS((c.trailing_pe - p.trailing_pe) / NULLIF(p.trailing_pe, 0)) > 0.10
    OR ABS((c.price_to_book - p.price_to_book) / NULLIF(p.price_to_book, 0)) > 0.10
ORDER BY ABS((c.trailing_pe - p.trailing_pe) / NULLIF(p.trailing_pe, 0)) DESC;

-- ========== EXPORT FOR POWER BI ==========

-- 14. Full Dataset for Power BI Dashboard
-- All metrics in one view for external analysis
SELECT 
    f.ticker,
    f.company_name,
    f.fetch_date,
    f.market_cap / 10000000 as market_cap_crores,
    
    -- Scores
    f.value_score,
    f.quality_score,
    f.growth_score,
    f.dividend_score,
    f.total_score,
    f.overall_rating,
    
    -- Valuation
    f.trailing_pe,
    f.price_to_book,
    v.price_to_sales,
    v.peg_ratio,
    
    -- Profitability
    q.return_on_equity * 100 as roe_pct,
    q.return_on_assets * 100 as roa_pct,
    q.profit_margin * 100 as profit_margin_pct,
    q.operating_margin * 100 as operating_margin_pct,
    
    -- Growth
    g.revenue_growth * 100 as revenue_growth_pct,
    g.earnings_growth * 100 as earnings_growth_pct,
    
    -- Financial Health
    q.debt_to_equity,
    q.current_ratio,
    q.quick_ratio,
    q.free_cashflow / 10000000 as fcf_crores,
    
    -- Dividends
    d.dividend_yield * 100 as dividend_yield_pct,
    d.payout_ratio * 100 as payout_ratio_pct,
    
    -- Categories
    f.valuation_category,
    q.quality_category,
    g.growth_category,
    d.dividend_category
    
FROM vw_fundamental_scoring f
LEFT JOIN vw_value_stocks_screen v ON f.ticker = v.ticker
LEFT JOIN vw_quality_stocks_screen q ON f.ticker = q.ticker
LEFT JOIN vw_growth_stocks_screen g ON f.ticker = g.ticker
LEFT JOIN vw_dividend_stocks_screen d ON f.ticker = d.ticker
ORDER BY f.total_score DESC;
