-- =============================================================
-- MIGRATION: Persist the per-row FLAT band on ai_prediction_history
--
-- Why: calibrate_flat_threshold() in daily_prediction_job.py derives the
--      UP/FLAT/DOWN label band from each market's realized 7-day return
--      distribution and RE-DERIVES IT ON EVERY RUN (NASDAQ 0.0185, NSE
--      0.015, Forex 0.0080 as of 2026-09-03). Both graders, however,
--      hardcoded 0.015. A FLAT call trained against a 1.85% band but
--      graded against a 1.5% band is scored wrong for moves in between.
--
--      Measured impact of the mismatch on existing rows:
--          NASDAQ FLAT accuracy  37.8%  ->  44.5%  (regraded at 0.0185)
--          NSE    FLAT accuracy  31.9%  ->  38.3%  (regraded at 0.0185)
--
--      Storing the band on the row makes grading reproducible even as the
--      band drifts, and keeps historical rows graded against the band that
--      was actually in force when they were made.
--
-- Run in SSMS against stockdata_db BEFORE deploying the updated job.
-- Idempotent: safe to re-run.
-- =============================================================

USE stockdata_db;
GO

-- ---------------------------------------------------------------
-- Step 1: Add the column
-- ---------------------------------------------------------------

IF NOT EXISTS (SELECT 1 FROM sys.columns
               WHERE object_id = OBJECT_ID('dbo.ai_prediction_history')
                 AND name = 'flat_band_pct')
BEGIN
    ALTER TABLE dbo.ai_prediction_history
        ADD flat_band_pct FLOAT NULL;
    PRINT 'Step 1 complete: flat_band_pct added.';
END
ELSE
    PRINT 'Step 1 skipped: flat_band_pct already exists.';
GO

-- ---------------------------------------------------------------
-- Step 2: Backfill the band for existing 3-class rows
--
-- The 3-class era starts 2026-05-25 (first row with predicted_direction
-- NOT NULL). Rows before that are legacy binary predictions and are graded
-- by the predicted_change_pct branches, which never consult this column --
-- they stay NULL.
--
-- Values below are the current calibrated bands. They are the best
-- available estimate for historical rows: the band is a slow-moving
-- function of the market's return distribution, and it was NOT stored at
-- the time. Rows written after this migration carry their exact band.
-- ---------------------------------------------------------------

UPDATE dbo.ai_prediction_history
SET flat_band_pct = CASE market
        WHEN 'NASDAQ 100' THEN 0.0185
        WHEN 'NSE 500'    THEN 0.0185
        WHEN 'Forex'      THEN 0.0080
        ELSE 0.015
    END
WHERE predicted_direction IS NOT NULL
  AND flat_band_pct IS NULL
  AND days_ahead >= 7;

PRINT 'Step 2 complete: historical 3-class rows backfilled.';
GO

-- ---------------------------------------------------------------
-- Step 3: Re-grade already-resolved FLAT rows against the stored band.
--
-- actual_price is already persisted on these rows, so the band comparison
-- can be recomputed in place -- no price lookup and no window where rows
-- sit ungraded. (The backfill script only touches actual_price IS NULL,
-- so it would never revisit these rows.)
--
-- Only FLAT rows are affected: UP/DOWN grading compares actual vs current
-- price directly and never consults the band, so those rows are already
-- correct and are left untouched.
-- ---------------------------------------------------------------

UPDATE dbo.ai_prediction_history
SET direction_correct = CASE
        WHEN CAST(current_price AS FLOAT) = 0 THEN 0
        WHEN ABS(CAST(actual_price AS FLOAT) - CAST(current_price AS FLOAT))
             / CAST(current_price AS FLOAT) < ISNULL(flat_band_pct, 0.015) THEN 1
        ELSE 0
    END
WHERE predicted_direction = 'FLAT'
  AND actual_price IS NOT NULL;

PRINT 'Step 3 complete: resolved FLAT rows re-graded against stored band.';
GO

-- ---------------------------------------------------------------
-- Verify
-- ---------------------------------------------------------------
SELECT
    market,
    predicted_direction,
    COUNT(*)                                              AS n,
    COUNT(flat_band_pct)                                  AS with_band,
    MIN(flat_band_pct)                                    AS band,
    SUM(CASE WHEN direction_correct IS NULL THEN 1 ELSE 0 END) AS ungraded
FROM dbo.ai_prediction_history
WHERE predicted_direction IS NOT NULL
GROUP BY market, predicted_direction
ORDER BY market, predicted_direction;
GO
