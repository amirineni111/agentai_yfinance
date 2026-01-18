-- =====================================================
-- PREDICTION WATCHLIST TABLE
-- Store tickers for daily prediction job
-- =====================================================

USE stockdata_db;
GO

-- Drop existing table if it exists
IF OBJECT_ID('dbo.prediction_watchlist', 'U') IS NOT NULL
    DROP TABLE dbo.prediction_watchlist;
GO

-- Create watchlist table
CREATE TABLE dbo.prediction_watchlist (
    watchlist_id INT IDENTITY(1,1) PRIMARY KEY,
    market VARCHAR(50) NOT NULL,
    ticker VARCHAR(50) NOT NULL,
    company_name VARCHAR(200),
    is_active BIT DEFAULT 1,
    priority INT DEFAULT 1,
    notes VARCHAR(500),
    added_date DATETIME DEFAULT GETDATE(),
    updated_date DATETIME DEFAULT GETDATE(),
    
    -- Constraints
    CONSTRAINT CHK_watchlist_market CHECK (market IN ('NSE 500', 'NASDAQ 100', 'Forex')),
    CONSTRAINT UQ_watchlist_market_ticker UNIQUE (market, ticker)
);
GO

-- Create index for performance
CREATE INDEX IDX_watchlist_market_active ON dbo.prediction_watchlist(market, is_active);
GO

-- Insert NSE 500 watchlist (Top 20 Indian stocks)
INSERT INTO dbo.prediction_watchlist (market, ticker, company_name, priority)
VALUES
    ('NSE 500', 'RELIANCE.NS', 'Reliance Industries', 1),
    ('NSE 500', 'TCS.NS', 'Tata Consultancy Services', 1),
    ('NSE 500', 'HDFCBANK.NS', 'HDFC Bank', 1),
    ('NSE 500', 'INFY.NS', 'Infosys', 1),
    ('NSE 500', 'HINDUNILVR.NS', 'Hindustan Unilever', 1),
    ('NSE 500', 'ICICIBANK.NS', 'ICICI Bank', 1),
    ('NSE 500', 'SBIN.NS', 'State Bank of India', 1),
    ('NSE 500', 'BHARTIARTL.NS', 'Bharti Airtel', 1),
    ('NSE 500', 'ITC.NS', 'ITC Limited', 1),
    ('NSE 500', 'KOTAKBANK.NS', 'Kotak Mahindra Bank', 1),
    ('NSE 500', 'LT.NS', 'Larsen & Toubro', 2),
    ('NSE 500', 'AXISBANK.NS', 'Axis Bank', 2),
    ('NSE 500', 'ASIANPAINT.NS', 'Asian Paints', 2),
    ('NSE 500', 'MARUTI.NS', 'Maruti Suzuki', 2),
    ('NSE 500', 'HCLTECH.NS', 'HCL Technologies', 2),
    ('NSE 500', 'WIPRO.NS', 'Wipro', 2),
    ('NSE 500', 'TITAN.NS', 'Titan Company', 2),
    ('NSE 500', 'SUNPHARMA.NS', 'Sun Pharma', 2),
    ('NSE 500', 'ULTRACEMCO.NS', 'UltraTech Cement', 2),
    ('NSE 500', 'NESTLEIND.NS', 'Nestle India', 2);

-- Insert NASDAQ 100 watchlist (Top 30 tech stocks)
INSERT INTO dbo.prediction_watchlist (market, ticker, company_name, priority)
VALUES
    ('NASDAQ 100', 'AAPL', 'Apple Inc.', 1),
    ('NASDAQ 100', 'MSFT', 'Microsoft Corporation', 1),
    ('NASDAQ 100', 'GOOGL', 'Alphabet Inc.', 1),
    ('NASDAQ 100', 'AMZN', 'Amazon.com Inc.', 1),
    ('NASDAQ 100', 'NVDA', 'NVIDIA Corporation', 1),
    ('NASDAQ 100', 'META', 'Meta Platforms Inc.', 1),
    ('NASDAQ 100', 'TSLA', 'Tesla Inc.', 1),
    ('NASDAQ 100', 'AVGO', 'Broadcom Inc.', 1),
    ('NASDAQ 100', 'COST', 'Costco Wholesale', 1),
    ('NASDAQ 100', 'NFLX', 'Netflix Inc.', 1),
    ('NASDAQ 100', 'ADBE', 'Adobe Inc.', 2),
    ('NASDAQ 100', 'PEP', 'PepsiCo Inc.', 2),
    ('NASDAQ 100', 'CSCO', 'Cisco Systems', 2),
    ('NASDAQ 100', 'AMD', 'Advanced Micro Devices', 2),
    ('NASDAQ 100', 'INTC', 'Intel Corporation', 2),
    ('NASDAQ 100', 'CMCSA', 'Comcast Corporation', 2),
    ('NASDAQ 100', 'TXN', 'Texas Instruments', 2),
    ('NASDAQ 100', 'QCOM', 'QUALCOMM Inc.', 2),
    ('NASDAQ 100', 'INTU', 'Intuit Inc.', 2),
    ('NASDAQ 100', 'AMAT', 'Applied Materials', 2),
    ('NASDAQ 100', 'HON', 'Honeywell International', 3),
    ('NASDAQ 100', 'AMGN', 'Amgen Inc.', 3),
    ('NASDAQ 100', 'SBUX', 'Starbucks Corporation', 3),
    ('NASDAQ 100', 'GILD', 'Gilead Sciences', 3),
    ('NASDAQ 100', 'ADP', 'Automatic Data Processing', 3),
    ('NASDAQ 100', 'BKNG', 'Booking Holdings', 3),
    ('NASDAQ 100', 'MDLZ', 'Mondelez International', 3),
    ('NASDAQ 100', 'ISRG', 'Intuitive Surgical', 3),
    ('NASDAQ 100', 'ADI', 'Analog Devices', 3),
    ('NASDAQ 100', 'VRTX', 'Vertex Pharmaceuticals', 3);

-- Insert Forex watchlist (Major currency pairs)
INSERT INTO dbo.prediction_watchlist (market, ticker, company_name, priority)
VALUES
    ('Forex', 'AUDUSD', 'Australian Dollar / US Dollar', 1),
    ('Forex', 'EURUSD', 'Euro / US Dollar', 1),
    ('Forex', 'GBPUSD', 'British Pound / US Dollar', 1),
    ('Forex', 'USDJPY', 'US Dollar / Japanese Yen', 1),
    ('Forex', 'USDCHF', 'US Dollar / Swiss Franc', 2),
    ('Forex', 'EURCHF', 'Euro / Swiss Franc', 2),
    ('Forex', 'EURJPY', 'Euro / Japanese Yen', 2),
    ('Forex', 'GBPJPY', 'British Pound / Japanese Yen', 2);

GO

-- Create view for active watchlist
CREATE VIEW dbo.vw_active_watchlist AS
SELECT 
    market,
    ticker,
    company_name,
    priority,
    notes,
    added_date
FROM dbo.prediction_watchlist
WHERE is_active = 1
ORDER BY market, priority, ticker;
GO

PRINT '✅ Watchlist table created successfully!';
PRINT '📊 Inserted:';
PRINT '   - NSE 500: 20 stocks';
PRINT '   - NASDAQ 100: 30 stocks';
PRINT '   - Forex: 8 pairs';
PRINT '';
PRINT '📝 To manage your watchlist:';
PRINT '   -- View active watchlist:';
PRINT '   SELECT * FROM vw_active_watchlist;';
PRINT '';
PRINT '   -- Add new ticker:';
PRINT '   INSERT INTO prediction_watchlist (market, ticker, company_name) VALUES (''NSE 500'', ''ADANIPORTS.NS'', ''Adani Ports'');';
PRINT '';
PRINT '   -- Disable ticker:';
PRINT '   UPDATE prediction_watchlist SET is_active = 0 WHERE ticker = ''TICKER'';';
PRINT '';
PRINT '   -- Delete ticker:';
PRINT '   DELETE FROM prediction_watchlist WHERE ticker = ''TICKER'';';
GO
