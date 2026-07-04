-- =============================================================
-- MIGRATION: Add is_actionable + suppression_reason columns to
-- ai_prediction_history
-- Regime-suppressed predictions (SIDEWAYS / INSUFFICIENT) are now
-- stored with is_actionable = 0 instead of being silently skipped.
-- Legacy rows keep NULL and are treated as actionable via
-- ISNULL(is_actionable, 1) = 1 (same convention as the NASDAQ
-- ml_trading_predictions ecosystem).
-- Run ONCE before starting the updated daily_prediction_job.py
-- =============================================================

-- Safe check: only add if column does not already exist
IF NOT EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.ai_prediction_history')
      AND name = N'is_actionable'
)
BEGIN
    ALTER TABLE dbo.ai_prediction_history
    ADD is_actionable BIT NULL;

    PRINT 'Column is_actionable added to ai_prediction_history.'
END
ELSE
BEGIN
    PRINT 'Column is_actionable already exists — no change made.'
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.ai_prediction_history')
      AND name = N'suppression_reason'
)
BEGIN
    ALTER TABLE dbo.ai_prediction_history
    ADD suppression_reason VARCHAR(20) NULL;

    PRINT 'Column suppression_reason added to ai_prediction_history.'
END
ELSE
BEGIN
    PRINT 'Column suppression_reason already exists — no change made.'
END
GO

-- Verify
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'ai_prediction_history'
  AND COLUMN_NAME IN ('is_actionable', 'suppression_reason');
GO
