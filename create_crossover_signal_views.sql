-- =====================================================
-- Create Combined Crossover Signal Views
-- =====================================================
-- These views combine all indicator signals into one view per market

-- Drop existing views if they exist
IF OBJECT_ID('dbo.vw_crossover_signals_NSE_500', 'V') IS NOT NULL
    DROP VIEW dbo.vw_crossover_signals_NSE_500;
GO

IF OBJECT_ID('dbo.vw_crossover_signals_NASDAQ_100', 'V') IS NOT NULL
    DROP VIEW dbo.vw_crossover_signals_NASDAQ_100;
GO

IF OBJECT_ID('dbo.vw_crossover_signals_Forex', 'V') IS NOT NULL
    DROP VIEW dbo.vw_crossover_signals_Forex;
GO

-- =====================================================
-- NSE 500 Combined Crossover Signals (Enhanced with all indicators)
-- =====================================================
CREATE VIEW dbo.vw_crossover_signals_NSE_500 AS
SELECT 
    m.ticker,
    m.ticker as company_name,
    m.trading_date,
    bb.close_price,
    
    -- Individual signals (7 total indicators)
    COALESCE(bb.bb_trade_signal, 'No Signal') as bb_trade_signal,
    COALESCE(m.MACD_Signal, 'No Signal') as macd_signal,
    COALESCE(r.rsi_trade_signal, 'No Signal') as rsi_trade_signal,
    COALESCE(s.sma_trade_signal, 'No Signal') as sma_trade_signal,
    COALESCE(st.stoch_trade_signal, 'No Signal') as stoch_signal,
    COALESCE(f.fib_trade_signal, 'No Signal') as fib_signal,
    COALESCE(p.pattern_signal, 'No Signal') as pattern_signal,
    
    -- Count bullish signals (all 7 indicators)
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%buy%' THEN 1 ELSE 0 END) as bullish_count,
    
    -- Count bearish signals (all 7 indicators)
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%sell%' THEN 1 ELSE 0 END) as bearish_count
    
FROM dbo.nse_500_macd_signals m
LEFT JOIN dbo.nse_500_bb_signals bb ON m.ticker = bb.ticker AND m.trading_date = bb.trading_date
LEFT JOIN dbo.nse_500_rsi_signals r ON m.ticker = r.ticker AND m.trading_date = r.trading_date
LEFT JOIN dbo.nse_500_sma_signals s ON m.ticker = s.ticker AND m.trading_date = s.trading_date
LEFT JOIN dbo.nse_500_stochastic st ON m.ticker = st.ticker AND m.trading_date = st.trading_date
LEFT JOIN dbo.nse_500_fibonacci f ON m.ticker = f.ticker AND m.trading_date = f.trading_date
LEFT JOIN dbo.nse_500_patterns p ON m.ticker = p.ticker AND m.trading_date = p.trading_date
WHERE 
    -- Only include rows with at least 2 aligned signals
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%buy%' THEN 1 ELSE 0 END) >= 2
    OR
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%sell%' THEN 1 ELSE 0 END) >= 2;
GO

-- =====================================================
-- NASDAQ 100 Combined Crossover Signals (Enhanced with all indicators)
-- =====================================================
CREATE VIEW dbo.vw_crossover_signals_NASDAQ_100 AS
SELECT 
    m.ticker,
    m.ticker as company_name,
    m.trading_date,
    bb.close_price,
    
    -- Individual signals (7 total indicators)
    COALESCE(bb.bb_trade_signal, 'No Signal') as bb_trade_signal,
    COALESCE(m.MACD_Signal, 'No Signal') as macd_signal,
    COALESCE(r.rsi_trade_signal, 'No Signal') as rsi_trade_signal,
    COALESCE(s.sma_trade_signal, 'No Signal') as sma_trade_signal,
    COALESCE(st.stoch_trade_signal, 'No Signal') as stoch_signal,
    COALESCE(f.fib_trade_signal, 'No Signal') as fib_signal,
    COALESCE(p.pattern_signal, 'No Signal') as pattern_signal,
    
    -- Count bullish signals (all 7 indicators)
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%buy%' THEN 1 ELSE 0 END) as bullish_count,
    
    -- Count bearish signals (all 7 indicators)
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%sell%' THEN 1 ELSE 0 END) as bearish_count
    
FROM dbo.nasdaq_100_macd_signals m
LEFT JOIN dbo.nasdaq_100_bb_signals bb ON m.ticker = bb.ticker AND m.trading_date = bb.trading_date
LEFT JOIN dbo.nasdaq_100_rsi_signals r ON m.ticker = r.ticker AND m.trading_date = r.trading_date
LEFT JOIN dbo.nasdaq_100_sma_signals s ON m.ticker = s.ticker AND m.trading_date = s.trading_date
LEFT JOIN dbo.nasdaq_100_stochastic st ON m.ticker = st.ticker AND m.trading_date = st.trading_date
LEFT JOIN dbo.nasdaq_100_fibonacci f ON m.ticker = f.ticker AND m.trading_date = f.trading_date
LEFT JOIN dbo.nasdaq_100_patterns p ON m.ticker = p.ticker AND m.trading_date = p.trading_date
WHERE 
    -- Only include rows with at least 2 aligned signals
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%buy%' THEN 1 ELSE 0 END) >= 2
    OR
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%sell%' THEN 1 ELSE 0 END) >= 2;
GO

-- =====================================================
-- Forex Combined Crossover Signals (Enhanced with all indicators)
-- Note: Forex uses 'symbol' instead of 'ticker'
-- =====================================================
CREATE VIEW dbo.vw_crossover_signals_Forex AS
SELECT 
    m.symbol as ticker,
    m.symbol as company_name,
    m.trading_date,
    bb.close_price,
    
    -- Individual signals (7 total indicators)
    COALESCE(bb.bb_trade_signal, 'No Signal') as bb_trade_signal,
    COALESCE(m.MACD_Signal, 'No Signal') as macd_signal,
    COALESCE(r.rsi_trade_signal, 'No Signal') as rsi_trade_signal,
    COALESCE(s.sma_trade_signal, 'No Signal') as sma_trade_signal,
    COALESCE(st.stoch_trade_signal, 'No Signal') as stoch_signal,
    COALESCE(f.fib_trade_signal, 'No Signal') as fib_signal,
    COALESCE(p.pattern_signal, 'No Signal') as pattern_signal,
    
    -- Count bullish signals (all 7 indicators)
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%buy%' THEN 1 ELSE 0 END) as bullish_count,
    
    -- Count bearish signals (all 7 indicators)
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%sell%' THEN 1 ELSE 0 END) as bearish_count
    
FROM dbo.forex_macd_signals m
LEFT JOIN dbo.forex_bb_signals bb ON m.symbol = bb.symbol AND m.trading_date = bb.trading_date
LEFT JOIN dbo.forex_rsi_signals r ON m.symbol = r.symbol AND m.trading_date = r.trading_date
LEFT JOIN dbo.forex_sma_signals s ON m.symbol = s.symbol AND m.trading_date = s.trading_date
LEFT JOIN dbo.forex_stochastic st ON m.symbol = st.ticker AND m.trading_date = st.trading_date
LEFT JOIN dbo.forex_fibonacci f ON m.symbol = f.ticker AND m.trading_date = f.trading_date
LEFT JOIN dbo.forex_patterns p ON m.symbol = p.ticker AND m.trading_date = p.trading_date
WHERE 
    -- Only include rows with at least 2 aligned signals
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%buy%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%buy%' THEN 1 ELSE 0 END) >= 2
    OR
    (CASE WHEN bb.bb_trade_signal IS NOT NULL AND LOWER(bb.bb_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN m.MACD_Signal IS NOT NULL AND LOWER(m.MACD_Signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN r.rsi_trade_signal IS NOT NULL AND LOWER(r.rsi_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN s.sma_trade_signal IS NOT NULL AND LOWER(s.sma_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN st.stoch_trade_signal IS NOT NULL AND LOWER(st.stoch_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN f.fib_trade_signal IS NOT NULL AND LOWER(f.fib_trade_signal) LIKE '%sell%' THEN 1 ELSE 0 END +
     CASE WHEN p.pattern_signal IS NOT NULL AND LOWER(p.pattern_signal) LIKE '%sell%' THEN 1 ELSE 0 END) >= 2;
GO

PRINT 'Combined crossover signal views created successfully!';
PRINT 'Views created: vw_crossover_signals_NSE_500, vw_crossover_signals_NASDAQ_100, vw_crossover_signals_Forex';
PRINT '';
PRINT 'These views combine 7 indicators: BB, MACD, RSI, SMA, Stochastic, Fibonacci, and Chart Patterns';
PRINT 'Only stocks with 2+ aligned BUY or SELL signals are included.';
PRINT 'Signal strength can now range from 2 to 7 based on indicator alignment.';

