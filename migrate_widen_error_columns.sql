-- =============================================================
-- MIGRATION: Widen error/change columns to FLOAT
-- Fixes: Arithmetic overflow error 8115 in backfill_actual_prices.py
-- Root cause: NUMERIC(p,s) columns overflow when predicted vs actual
--             prices are far apart (e.g. stale INR predictions).
-- Run in SSMS against stockdata_db BEFORE re-running the backfill.
-- =============================================================

USE stockdata_db;
GO

-- ---------------------------------------------------------------
-- Step 1: Drop indexes that block the ALTER COLUMN statements
-- ---------------------------------------------------------------

-- Drop covering/composite indexes on absolute_error
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ai_pred_accuracy_cover'
           AND object_id = OBJECT_ID('dbo.ai_prediction_history'))
    DROP INDEX IX_ai_pred_accuracy_cover ON dbo.ai_prediction_history;

IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ai_pred_market_accuracy'
           AND object_id = OBJECT_ID('dbo.ai_prediction_history'))
    DROP INDEX IX_ai_pred_market_accuracy ON dbo.ai_prediction_history;

-- Drop any other indexes that may reference the affected columns
-- (Run the query below first to check for others if needed)
--
-- SELECT i.name, c.name AS column_name
-- FROM sys.index_columns ic
-- JOIN sys.indexes      i ON i.object_id = ic.object_id AND i.index_id = ic.index_id
-- JOIN sys.columns      c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
-- WHERE ic.object_id = OBJECT_ID('dbo.ai_prediction_history')
--   AND c.name IN ('absolute_error','squared_error','percentage_error','actual_change_pct');

PRINT 'Step 1 complete: blocking indexes dropped.'
GO

-- ---------------------------------------------------------------
-- Step 2: Widen columns to FLOAT (no precision limit)
-- ---------------------------------------------------------------

ALTER TABLE dbo.ai_prediction_history
    ALTER COLUMN actual_change_pct  FLOAT NULL;

ALTER TABLE dbo.ai_prediction_history
    ALTER COLUMN absolute_error     FLOAT NULL;

ALTER TABLE dbo.ai_prediction_history
    ALTER COLUMN squared_error      FLOAT NULL;

ALTER TABLE dbo.ai_prediction_history
    ALTER COLUMN percentage_error   FLOAT NULL;

PRINT 'Step 2 complete: columns widened to FLOAT.'
GO

-- ---------------------------------------------------------------
-- Step 3: Recreate the indexes (same structure, now on FLOAT cols)
-- ---------------------------------------------------------------

-- Covering index used by accuracy dashboard queries
CREATE NONCLUSTERED INDEX IX_ai_pred_accuracy_cover
    ON dbo.ai_prediction_history (market, ticker, days_ahead, model_name)
    INCLUDE (absolute_error, percentage_error, direction_correct, model_confidence, prediction_date);

-- Market + accuracy composite (used by bulk_load_performance_history)
CREATE NONCLUSTERED INDEX IX_ai_pred_market_accuracy
    ON dbo.ai_prediction_history (market, prediction_date)
    INCLUDE (ticker, days_ahead, model_name, direction_correct, percentage_error, absolute_error);

PRINT 'Step 3 complete: indexes recreated.'
GO

-- ---------------------------------------------------------------
-- Verify
-- ---------------------------------------------------------------
SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME   = 'ai_prediction_history'
  AND COLUMN_NAME IN ('actual_change_pct','absolute_error','squared_error','percentage_error')
ORDER BY COLUMN_NAME;
GO
