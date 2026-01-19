-- =====================================================
-- Double/Triple Strategy Signal Tracking System
-- =====================================================
-- This table tracks daily crossover signals and their accuracy

-- Drop existing table if exists
IF OBJECT_ID('dbo.signal_tracking_history', 'U') IS NOT NULL
    DROP TABLE dbo.signal_tracking_history;
GO

-- Create signal tracking table
CREATE TABLE dbo.signal_tracking_history (
    signal_id INT IDENTITY(1,1) PRIMARY KEY,
    
    -- Signal Information
    market VARCHAR(50) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    company_name VARCHAR(255),
    signal_date DATE NOT NULL,
    
    -- Signal Details
    signal_type VARCHAR(20) NOT NULL, -- 'BULLISH' or 'BEARISH'
    signal_strength INT NOT NULL, -- 2, 3, or 4 (number of aligned indicators)
    signal_status VARCHAR(20), -- 'NEW', 'STRONGER', 'WEAKER', 'ACTIVE', 'FLIPPED'
    
    -- Individual Signals (VARCHAR(100) to accommodate long signal descriptions)
    macd_signal VARCHAR(100),
    rsi_signal VARCHAR(100),
    bb_signal VARCHAR(100),
    sma_signal VARCHAR(100),
    
    -- Price at Signal Time
    signal_price DECIMAL(18, 4) NOT NULL,
    
    -- 7-Day Results
    target_date_7d DATE,
    actual_price_7d DECIMAL(18, 4),
    actual_change_7d DECIMAL(10, 4),
    result_7d VARCHAR(20), -- 'WIN', 'LOSS', 'NEUTRAL', 'PENDING'
    
    -- 14-Day Results  
    target_date_14d DATE,
    actual_price_14d DECIMAL(18, 4),
    actual_change_14d DECIMAL(10, 4),
    result_14d VARCHAR(20),
    
    -- 30-Day Results
    target_date_30d DATE,
    actual_price_30d DECIMAL(18, 4),
    actual_change_30d DECIMAL(10, 4),
    result_30d VARCHAR(20),
    
    -- Metadata
    created_at DATETIME DEFAULT GETDATE(),
    updated_at DATETIME DEFAULT GETDATE(),
    
    -- Indexes for performance
    INDEX IX_signal_tracking_market_ticker (market, ticker),
    INDEX IX_signal_tracking_date (signal_date),
    INDEX IX_signal_tracking_targets (target_date_7d, target_date_14d, target_date_30d)
);
GO

-- Create summary view for quick analytics
CREATE VIEW dbo.vw_signal_performance_summary AS
SELECT 
    market,
    signal_type,
    signal_strength,
    
    -- 7-Day Performance
    COUNT(CASE WHEN result_7d IS NOT NULL THEN 1 END) as completed_7d,
    COUNT(CASE WHEN result_7d = 'WIN' THEN 1 END) as wins_7d,
    COUNT(CASE WHEN result_7d = 'LOSS' THEN 1 END) as losses_7d,
    CAST(COUNT(CASE WHEN result_7d = 'WIN' THEN 1 END) AS FLOAT) / 
        NULLIF(COUNT(CASE WHEN result_7d IS NOT NULL THEN 1 END), 0) * 100 as win_rate_7d,
    AVG(CASE WHEN result_7d IS NOT NULL THEN actual_change_7d END) as avg_return_7d,
    
    -- 14-Day Performance
    COUNT(CASE WHEN result_14d IS NOT NULL THEN 1 END) as completed_14d,
    COUNT(CASE WHEN result_14d = 'WIN' THEN 1 END) as wins_14d,
    COUNT(CASE WHEN result_14d = 'LOSS' THEN 1 END) as losses_14d,
    CAST(COUNT(CASE WHEN result_14d = 'WIN' THEN 1 END) AS FLOAT) / 
        NULLIF(COUNT(CASE WHEN result_14d IS NOT NULL THEN 1 END), 0) * 100 as win_rate_14d,
    AVG(CASE WHEN result_14d IS NOT NULL THEN actual_change_14d END) as avg_return_14d,
    
    -- 30-Day Performance
    COUNT(CASE WHEN result_30d IS NOT NULL THEN 1 END) as completed_30d,
    COUNT(CASE WHEN result_30d = 'WIN' THEN 1 END) as wins_30d,
    COUNT(CASE WHEN result_30d = 'LOSS' THEN 1 END) as losses_30d,
    CAST(COUNT(CASE WHEN result_30d = 'WIN' THEN 1 END) AS FLOAT) / 
        NULLIF(COUNT(CASE WHEN result_30d IS NOT NULL THEN 1 END), 0) * 100 as win_rate_30d,
    AVG(CASE WHEN result_30d IS NOT NULL THEN actual_change_30d END) as avg_return_30d,
    
    COUNT(*) as total_signals
FROM dbo.signal_tracking_history
GROUP BY market, signal_type, signal_strength;
GO

-- Create view for pending signals
CREATE VIEW dbo.vw_pending_signal_updates AS
SELECT 
    signal_id,
    market,
    ticker,
    signal_date,
    signal_type,
    signal_strength,
    signal_price,
    
    -- 7-day pending
    CASE WHEN result_7d IS NULL AND target_date_7d <= CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END as needs_7d_update,
    target_date_7d,
    
    -- 14-day pending
    CASE WHEN result_14d IS NULL AND target_date_14d <= CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END as needs_14d_update,
    target_date_14d,
    
    -- 30-day pending
    CASE WHEN result_30d IS NULL AND target_date_30d <= CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END as needs_30d_update,
    target_date_30d
FROM dbo.signal_tracking_history
WHERE result_7d IS NULL OR result_14d IS NULL OR result_30d IS NULL;
GO

PRINT 'Signal tracking tables and views created successfully!';
PRINT 'Tables: signal_tracking_history';
PRINT 'Views: vw_signal_performance_summary, vw_pending_signal_updates';
