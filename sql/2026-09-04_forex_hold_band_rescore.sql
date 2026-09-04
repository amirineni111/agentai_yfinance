-- =============================================================
-- MIGRATION: Rescore historical Forex HOLD predictions against a
--            realistic FX band (1.00% -> 0.25%)
--
-- Why: backfill_strategy1_outcomes.py graded a Forex HOLD as Correct when the
--      move stayed inside a hardcoded 0.01 (1.0%) band, at three sites
--      (direction_correct_1d, prediction_accuracy, direction_correct_5d).
--      1% is an enormous 1-day FX move -- wider even than the 0.0080 band that
--      calibrate_flat_threshold() derives for Forex over a *7-day* horizon
--      (see sql/2026-09-03_add_flat_band.sql:60). The result is that HOLD was
--      graded correct almost unconditionally.
--
--      Measured on live rows before this migration:
--          signal   scored   accuracy
--          BUY         424      56.8%
--          HOLD        422      93.4%   <-- the band, not the model
--          SELL        616      46.8%
--          blended    1462      63.1%
--          excl HOLD  1040      50.9%
--
--      Worst offender: model_version '5.2_binary_rates+gated' scored 328 HOLD
--      rows at 97.6%.
--
--      Expected after this migration: HOLD ~63.7% (269/422), blended ~54.6%.
--      BUY and SELL accuracy must be COMPLETELY UNCHANGED -- only the HOLD arm
--      of the CASE moved. That is the correctness check for this script.
--
-- Pair with: backfill_strategy1_outcomes.py FOREX_HOLD_BAND = 0.0025.
--      Run BOTH in the same change window. Running only one leaves the table
--      carrying two different HOLD definitions spliced at the cutover date,
--      which makes any trailing-window accuracy metric meaningless.
--
--      A plain re-run of the backfill regrades NOTHING: every pass is gated on
--      "actual_return_Nd IS NULL", so already-scored rows are skipped. This
--      in-place UPDATE is the only way to reach them -- the same reason
--      sql/2026-09-03_add_flat_band.sql needed its Step 3.
--
-- UNITS -- read before editing:
--      The Python band (0.0025) is a *fraction*, compared against raw prices:
--          ABS(h.close_price - p.close_price) / p.close_price < 0.0025
--      The column actual_return_1d is stored as a *percentage* (already x100).
--      So the equivalent band HERE is 0.25, not 0.0025. Do not "fix" this.
--
-- Run in SSMS against stockdata_db.
-- Idempotent: recomputed from stored returns, safe to re-run.
-- =============================================================

USE stockdata_db;
GO

-- ---------------------------------------------------------------
-- Step 1: BEFORE snapshot
-- ---------------------------------------------------------------
PRINT '=== BEFORE ===';

SELECT
    predicted_signal,
    COUNT(*)                                                   AS scored_1d,
    SUM(CASE WHEN direction_correct_1d = 1 THEN 1 ELSE 0 END)  AS correct_1d,
    CAST(ROUND(AVG(CAST(direction_correct_1d AS FLOAT)) * 100, 1) AS DECIMAL(5,1)) AS acc_1d_pct
FROM dbo.forex_ml_predictions
WHERE direction_correct_1d IS NOT NULL
  AND actual_return_1d IS NOT NULL
GROUP BY predicted_signal
ORDER BY predicted_signal;
GO

-- ---------------------------------------------------------------
-- Step 2: Rescore the 1-day HOLD grade + prediction_accuracy
--
-- Scoped to predicted_signal = 'HOLD' so the BUY/SELL arms are provably
-- untouched. prediction_accuracy is a 1-day metric (only the 1d pass in
-- backfill_strategy1_outcomes.py ever writes it), so it is rescored here.
-- ---------------------------------------------------------------
UPDATE dbo.forex_ml_predictions
SET direction_correct_1d = CASE WHEN ABS(actual_return_1d) < 0.25 THEN 1 ELSE 0 END,
    prediction_accuracy  = CASE WHEN ABS(actual_return_1d) < 0.25 THEN 'Correct' ELSE 'Incorrect' END,
    updated_at           = GETDATE()
WHERE predicted_signal = 'HOLD'
  AND actual_return_1d IS NOT NULL;

PRINT 'Step 2 complete: 1-day HOLD rows rescored at 0.25%.';
GO

-- ---------------------------------------------------------------
-- Step 3: Rescore the 5-day HOLD grade
--
-- NOTE: the 5-day pass reuses the same band as the 1-day pass in the Python
-- source. That is arguably wrong -- a 5-day horizon should carry a wider band
-- -- but widening it is a modelling decision, not a bug fix, so this migration
-- reproduces the code's behaviour rather than inventing a second band.
-- ---------------------------------------------------------------
UPDATE dbo.forex_ml_predictions
SET direction_correct_5d = CASE WHEN ABS(actual_return_5d) < 0.25 THEN 1 ELSE 0 END,
    updated_at           = GETDATE()
WHERE predicted_signal = 'HOLD'
  AND actual_return_5d IS NOT NULL;

PRINT 'Step 3 complete: 5-day HOLD rows rescored at 0.25%.';
GO

-- ---------------------------------------------------------------
-- Verify
--
-- PASS criteria:
--   1. BUY and SELL acc_1d_pct are IDENTICAL to the Step 1 output.
--   2. HOLD acc_1d_pct has dropped (expected ~93.4% -> ~63.7%).
-- ---------------------------------------------------------------
PRINT '=== AFTER ===';

SELECT
    predicted_signal,
    COUNT(*)                                                   AS scored_1d,
    SUM(CASE WHEN direction_correct_1d = 1 THEN 1 ELSE 0 END)  AS correct_1d,
    CAST(ROUND(AVG(CAST(direction_correct_1d AS FLOAT)) * 100, 1) AS DECIMAL(5,1)) AS acc_1d_pct
FROM dbo.forex_ml_predictions
WHERE direction_correct_1d IS NOT NULL
  AND actual_return_1d IS NOT NULL
GROUP BY predicted_signal
ORDER BY predicted_signal;

-- Blended vs ex-HOLD, and the same split by model_version -- the cluster
-- models (forex_cluster_*) and the v1.0/v3.0 eras are leaky and should be
-- excluded from any headline accuracy figure. See W4 in the dashboard.
SELECT
    model_name,
    model_version,
    COUNT(*)                                                       AS scored_1d,
    CAST(ROUND(AVG(CAST(direction_correct_1d AS FLOAT)) * 100, 1) AS DECIMAL(5,1)) AS acc_1d_pct,
    CAST(ROUND(AVG(CASE WHEN predicted_signal <> 'HOLD'
                        THEN CAST(direction_correct_1d AS FLOAT) END) * 100, 1) AS DECIMAL(5,1)) AS acc_excl_hold_pct
FROM dbo.forex_ml_predictions
WHERE direction_correct_1d IS NOT NULL
  AND actual_return_1d IS NOT NULL
GROUP BY model_name, model_version
ORDER BY model_name, model_version;
GO
