-- =====================================================
-- AI PRICE PREDICTION HISTORY TABLE
-- Stores daily predictions and actual results for backtesting
-- =====================================================

USE stockdata_db;
GO

-- Drop existing table if it exists
IF OBJECT_ID('dbo.ai_prediction_history', 'U') IS NOT NULL
    DROP TABLE dbo.ai_prediction_history;
GO

-- Create prediction history table
CREATE TABLE dbo.ai_prediction_history (
    prediction_id INT IDENTITY(1,1) PRIMARY KEY,
    market VARCHAR(50) NOT NULL,                    -- NSE 500, NASDAQ 100, Forex
    ticker VARCHAR(50) NOT NULL,                    -- Stock/Forex ticker
    company_name VARCHAR(200),                      -- Company name
    prediction_date DATE NOT NULL,                  -- When prediction was made
    target_date DATE NOT NULL,                      -- Date being predicted
    days_ahead INT NOT NULL,                        -- 1, 3, 5, 7, 14, 30 days
    model_name VARCHAR(100) NOT NULL,               -- LSTM, XGBoost, Prophet, etc.
    
    -- Prediction values
    current_price DECIMAL(18, 5) NOT NULL,          -- Price when prediction was made
    predicted_price DECIMAL(18, 5) NOT NULL,        -- Predicted price
    predicted_change_pct DECIMAL(10, 4) NOT NULL,   -- Predicted % change
    
    -- Actual results (filled when target_date arrives)
    actual_price DECIMAL(18, 5) NULL,               -- Actual price on target_date
    actual_change_pct DECIMAL(10, 4) NULL,          -- Actual % change
    
    -- Accuracy metrics
    absolute_error DECIMAL(18, 5) NULL,             -- |predicted - actual|
    squared_error DECIMAL(18, 10) NULL,             -- (predicted - actual)^2
    percentage_error DECIMAL(10, 4) NULL,           -- Error as % of actual price
    direction_correct BIT NULL,                     -- Did we predict direction correctly?
    
    -- Metadata
    model_confidence DECIMAL(5, 2),                 -- Confidence level (0-100)
    created_at DATETIME DEFAULT GETDATE(),
    updated_at DATETIME DEFAULT GETDATE(),
    
    -- Constraints
    CONSTRAINT CHK_days_ahead CHECK (days_ahead IN (1, 3, 5, 7, 14, 30)),
    CONSTRAINT CHK_market CHECK (market IN ('NSE 500', 'NASDAQ 100', 'Forex'))
);
GO

-- Create indexes for performance
CREATE INDEX IDX_prediction_market_ticker ON dbo.ai_prediction_history(market, ticker);
CREATE INDEX IDX_prediction_target_date ON dbo.ai_prediction_history(target_date);
CREATE INDEX IDX_prediction_date ON dbo.ai_prediction_history(prediction_date);
CREATE INDEX IDX_model_performance ON dbo.ai_prediction_history(model_name, target_date) 
    WHERE actual_price IS NOT NULL;
GO

-- Create view for model performance summary
CREATE VIEW dbo.vw_model_performance_summary AS
SELECT 
    model_name,
    market,
    days_ahead,
    COUNT(*) as total_predictions,
    COUNT(actual_price) as completed_predictions,
    
    -- Accuracy metrics (only for completed predictions)
    AVG(CASE WHEN actual_price IS NOT NULL THEN absolute_error END) as avg_mae,
    SQRT(AVG(CASE WHEN actual_price IS NOT NULL THEN squared_error END)) as avg_rmse,
    AVG(CASE WHEN actual_price IS NOT NULL THEN percentage_error END) as avg_percentage_error,
    
    -- Directional accuracy
    SUM(CASE WHEN direction_correct = 1 THEN 1 ELSE 0 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN direction_correct IS NOT NULL THEN 1 END), 0) as directional_accuracy_pct,
    
    -- Date range
    MIN(prediction_date) as first_prediction,
    MAX(prediction_date) as last_prediction,
    MAX(target_date) as latest_target_date
FROM 
    dbo.ai_prediction_history
GROUP BY 
    model_name, market, days_ahead;
GO

-- Create view for recent predictions vs actuals
CREATE VIEW dbo.vw_recent_prediction_accuracy AS
SELECT TOP 1000
    prediction_id,
    market,
    ticker,
    company_name,
    prediction_date,
    target_date,
    days_ahead,
    model_name,
    current_price,
    predicted_price,
    predicted_change_pct,
    actual_price,
    actual_change_pct,
    absolute_error,
    percentage_error,
    direction_correct,
    CASE 
        WHEN direction_correct = 1 THEN '✓ Correct'
        WHEN direction_correct = 0 THEN '✗ Wrong'
        ELSE '⏳ Pending'
    END as direction_status,
    DATEDIFF(day, prediction_date, GETDATE()) as days_since_prediction
FROM 
    dbo.ai_prediction_history
WHERE 
    target_date >= DATEADD(day, -30, GETDATE())  -- Last 30 days
ORDER BY 
    target_date DESC, prediction_date DESC;
GO

PRINT '✅ Prediction history table and views created successfully!';
PRINT '📊 Ready to store daily predictions and track model accuracy.';
GO
