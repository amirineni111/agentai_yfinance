-- =============================================================
-- MIGRATION: vw_strategy2_unified_ml_predictions
--            - expose NASDAQ model_version (upstream now stamps it)
--            - expose is_actionable so consumers can re-filter
--            - establish a CREATE OR ALTER baseline
--
-- Why (baseline): the repo previously held only an ALTER VIEW for this object
--      (sql/2026-06-12_views_is_actionable_filter.sql). There was no CREATE
--      anywhere, so the authoritative definition existed ONLY inside the live
--      database and the view could not be rebuilt on a fresh instance. This
--      file is CREATE OR ALTER, so it is both the migration and the baseline.
--      Body below was scripted from stockdata_db via OBJECT_DEFINITION on
--      2026-09-04 and then modified; it is a faithful superset of what was live.
--
-- Why (model_version): the 2026-08/09 upstream S1 work added model_version to
--      dbo.ml_trading_predictions. The NASDAQ branch hardcoded
--      "NULL as model_version", so per-row model attribution was invisible
--      downstream even though NSE and Forex already carried it.
--
-- Why (is_actionable): the NASDAQ branch FILTERS on is_actionable but never
--      PROJECTS it, so a consumer of this view could not tell which definition
--      of "tradeable" it was looking at, nor re-filter.
--
-- VERIFIED COLUMN FACTS as of 2026-09-04 (do not "fix" these without checking):
--      ml_trading_predictions.model_version        EXISTS  -> now projected
--      ml_trading_predictions.model_name           DOES NOT EXIST -> stays NULL
--      ml_trading_predictions.is_actionable        EXISTS  -> now projected
--      ml_nse_trading_predictions.is_actionable    DOES NOT EXIST -> NULL
--      forex_ml_predictions.is_actionable          DOES NOT EXIST -> NULL
--      ml_nse_trading_predictions.conviction_score DOES NOT EXIST YET
--
-- DEFERRED: upstream reports conviction_score is created by an idempotent ALTER
--      on the next NSE 4:30 PM run. It is intentionally NOT referenced here --
--      adding it now would make this view fail to compile. Once the column
--      lands, add "conviction_score" to the NSE branch and "NULL as
--      conviction_score" to the NASDAQ and Forex branches.
--
-- NOT CHANGED: the Forex ml_signal_strength tiers (>= 0.8 High / >= 0.6 Medium).
--      An upstream review suspected the 0.8 tier was unreachable by
--      construction. It is not: signal_confidence ranges to 1.0 and 539 of 1642
--      rows are >= 0.8. The real Forex problem is model pooling, which is
--      handled in the dashboard accuracy panel, not here.
--
-- Run in SSMS against stockdata_db. Idempotent (CREATE OR ALTER).
-- Additive only: existing consumers keep working, two columns are added.
-- =============================================================

USE stockdata_db;
GO

CREATE OR ALTER VIEW dbo.vw_strategy2_unified_ml_predictions AS
-- NSE
SELECT 'NSE' as market, ticker, company, trading_date as prediction_date, predicted_signal,
    confidence as ml_confidence, confidence_percentage, signal_strength as ml_signal_strength,
    close_price, rsi, rsi_category, buy_probability, sell_probability,
    CASE WHEN predicted_signal='Buy' THEN 'LONG' WHEN predicted_signal='Sell' THEN 'SHORT' ELSE 'NEUTRAL' END as trade_direction,
    volume, hold_probability, model_name, model_version, sector, market_cap_category,
    medium_confidence, low_confidence,
    CAST(NULL AS BIT) as is_actionable,          -- no such column on the NSE table
    actual_return_1d, actual_return_5d, actual_return_10d, prediction_accuracy,
    direction_correct_1d, direction_correct_5d, updated_at
FROM dbo.ml_nse_trading_predictions
UNION ALL
-- NASDAQ (actionable signals only -- suppressed rows excluded)
SELECT 'NASDAQ' as market, ticker, company, trading_date as prediction_date, predicted_signal,
    confidence as ml_confidence, confidence_percentage, signal_strength as ml_signal_strength,
    close_price, RSI as rsi, rsi_category, buy_probability, sell_probability,
    CASE WHEN predicted_signal LIKE '%Buy%' THEN 'LONG' WHEN predicted_signal LIKE '%Sell%' THEN 'SHORT' ELSE 'NEUTRAL' END as trade_direction,
    NULL as volume, NULL as hold_probability,
    NULL as model_name,                          -- column does not exist on this table
    model_version,                               -- 2026-09-04: was NULL, now real
    NULL as sector, NULL as market_cap_category, NULL as medium_confidence, NULL as low_confidence,
    is_actionable,                               -- 2026-09-04: now projected, not just filtered
    actual_return_1d, actual_return_5d, actual_return_10d, prediction_accuracy,
    direction_correct_1d, direction_correct_5d, updated_at
FROM dbo.ml_trading_predictions
WHERE ISNULL(is_actionable, 1) = 1
UNION ALL
-- Forex
SELECT 'Forex' as market, currency_pair as ticker, currency_pair as company,
    CAST(date_time as date) as prediction_date, predicted_signal,
    CAST(signal_confidence AS FLOAT) as ml_confidence,
    CAST(signal_confidence AS FLOAT) * 100 as confidence_percentage,
    CASE WHEN signal_confidence >= 0.8 THEN 'High' WHEN signal_confidence >= 0.6 THEN 'Medium' ELSE 'Low' END as ml_signal_strength,
    CAST(close_price AS FLOAT) as close_price, NULL as rsi, NULL as rsi_category,
    CAST(prob_buy AS FLOAT) as buy_probability, CAST(prob_sell AS FLOAT) as sell_probability,
    CASE WHEN predicted_signal='BUY' THEN 'LONG' WHEN predicted_signal='SELL' THEN 'SHORT' ELSE 'NEUTRAL' END as trade_direction,
    CAST(volume AS BIGINT) as volume, CAST(prob_hold AS FLOAT) as hold_probability,
    model_name, model_version, NULL as sector, NULL as market_cap_category,
    CAST(NULL AS BIT) as medium_confidence, CAST(NULL AS BIT) as low_confidence,
    CAST(NULL AS BIT) as is_actionable,           -- no such column on the Forex table
    actual_return_1d, actual_return_5d, actual_return_10d, prediction_accuracy,
    direction_correct_1d, direction_correct_5d, updated_at
FROM dbo.forex_ml_predictions;
GO

-- ---------------------------------------------------------------
-- Verify: every market resolves, NASDAQ now carries model_version.
-- ---------------------------------------------------------------
SELECT market,
       COUNT(*)                     AS n_rows,
       COUNT(model_version)         AS with_model_version,
       COUNT(is_actionable)         AS with_is_actionable,
       COUNT(DISTINCT model_version) AS distinct_versions
FROM dbo.vw_strategy2_unified_ml_predictions
GROUP BY market
ORDER BY market;
GO
