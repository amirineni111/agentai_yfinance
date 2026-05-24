-- =============================================================
-- MIGRATION: Add predicted_direction column to ai_prediction_history
-- Phase 4C: 3-class classification (UP / FLAT / DOWN)
-- Run ONCE before starting the updated daily_prediction_job.py
-- =============================================================

-- Safe check: only add if column does not already exist
IF NOT EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'dbo.ai_prediction_history')
      AND name = N'predicted_direction'
)
BEGIN
    ALTER TABLE dbo.ai_prediction_history
    ADD predicted_direction VARCHAR(10) NULL;

    PRINT 'Column predicted_direction added to ai_prediction_history.'
END
ELSE
BEGIN
    PRINT 'Column predicted_direction already exists — no change made.'
END
GO

-- Verify
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'ai_prediction_history'
  AND COLUMN_NAME = 'predicted_direction';
GO
