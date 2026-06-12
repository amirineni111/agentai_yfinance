-- June 2026: ml_trading_predictions now stores ALL ~2,300 NASDAQ tickers daily.
-- Suppressed (non-tradeable) rows carry is_actionable = 0 and
-- signal_strength = 'Suppressed'; previously they were dropped before export.
-- These views must keep their original meaning (tradeable signals only), so the
-- NASDAQ branches filter ISNULL(is_actionable, 1) = 1 (NULL = pre-flag rows,
-- which had all passed the old drop-style filters).
-- Applied to stockdata_db on 2026-06-12.

ALTER VIEW dbo.vw_strategy2_unified_ml_predictions AS
-- NSE
SELECT 'NSE' as market, ticker, company, trading_date as prediction_date, predicted_signal,
    confidence as ml_confidence, confidence_percentage, signal_strength as ml_signal_strength,
    close_price, rsi, rsi_category, buy_probability, sell_probability,
    CASE WHEN predicted_signal='Buy' THEN 'LONG' WHEN predicted_signal='Sell' THEN 'SHORT' ELSE 'NEUTRAL' END as trade_direction,
    volume, hold_probability, model_name, model_version, sector, market_cap_category,
    medium_confidence, low_confidence,
    actual_return_1d, actual_return_5d, actual_return_10d, prediction_accuracy,
    direction_correct_1d, direction_correct_5d, updated_at
FROM dbo.ml_nse_trading_predictions
UNION ALL
-- NASDAQ (actionable signals only — suppressed rows excluded)
SELECT 'NASDAQ' as market, ticker, company, trading_date as prediction_date, predicted_signal,
    confidence as ml_confidence, confidence_percentage, signal_strength as ml_signal_strength,
    close_price, RSI as rsi, rsi_category, buy_probability, sell_probability,
    CASE WHEN predicted_signal LIKE '%Buy%' THEN 'LONG' WHEN predicted_signal LIKE '%Sell%' THEN 'SHORT' ELSE 'NEUTRAL' END as trade_direction,
    NULL as volume, NULL as hold_probability, NULL as model_name, NULL as model_version,
    NULL as sector, NULL as market_cap_category, NULL as medium_confidence, NULL as low_confidence,
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
    actual_return_1d, actual_return_5d, actual_return_10d, prediction_accuracy,
    direction_correct_1d, direction_correct_5d, updated_at
FROM dbo.forex_ml_predictions;
GO

ALTER VIEW vw_theme_ml_signal_score AS
WITH latest_pred AS (
    SELECT
        ticker,
        UPPER(predicted_signal)  AS predicted_signal,
        confidence,                             -- FLOAT 0.0-1.0 confirmed in live DB
        trading_date,
        ROW_NUMBER() OVER (
            PARTITION BY ticker
            ORDER BY trading_date DESC
        ) AS rn
    FROM ml_trading_predictions
    WHERE UPPER(predicted_signal) IN ('BUY', 'SELL', 'HOLD')
      AND ISNULL(is_actionable, 1) = 1
),
current_signals AS (
    SELECT ticker, predicted_signal, confidence
    FROM latest_pred
    WHERE rn = 1
)
SELECT
    m.theme,
    COUNT(DISTINCT m.ticker)                                                    AS ticker_count,
    ROUND(
        SUM(CASE WHEN cs.predicted_signal = 'BUY' THEN 1.0 ELSE 0 END)
        / NULLIF(COUNT(cs.ticker), 0) * 100
    , 2)                                                                        AS buy_signal_pct,
    ROUND(
        AVG(CASE WHEN cs.predicted_signal = 'BUY' THEN cs.confidence END) * 100
    , 2)                                                                        AS avg_buy_conf_pct,
    ROUND(
        ISNULL(
            SUM(CASE WHEN cs.predicted_signal = 'BUY' THEN 1.0 ELSE 0 END)
            / NULLIF(COUNT(cs.ticker), 0) * 60, 0)
        + ISNULL(
            AVG(CASE WHEN cs.predicted_signal = 'BUY' THEN cs.confidence END) * 40, 0)
    , 2)                                                                        AS ml_signal_score
FROM nasdaq_theme_mapping m
LEFT JOIN current_signals cs ON m.ticker = cs.ticker
WHERE m.is_active = 1
GROUP BY m.theme;
GO

ALTER VIEW vw_theme_stock_signals AS
WITH latest_pred AS (
    SELECT ticker, company, UPPER(predicted_signal) AS predicted_signal,
           confidence, confidence_percentage, buy_probability, sell_probability,
           signal_strength, RSI, rsi_category, close_price, trading_date,
           ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date DESC) AS rn
    FROM ml_trading_predictions
    WHERE UPPER(predicted_signal) IN ('BUY', 'SELL', 'HOLD')
      AND ISNULL(is_actionable, 1) = 1
),
current_pred AS (SELECT * FROM latest_pred WHERE rn = 1),
latest_scores AS (
    SELECT * FROM nasdaq_theme_heat_scores
    WHERE score_date = (SELECT MAX(score_date) FROM nasdaq_theme_heat_scores)
),
latest_rotation AS (
    SELECT * FROM nasdaq_theme_rotation_log
    WHERE log_date = (SELECT MAX(log_date) FROM nasdaq_theme_rotation_log)
)
SELECT
    p.ticker, p.company,
    n.sector, n.industry, n.sub_industry,
    m.theme, m.market_cap_tier, m.beta_bucket, m.is_primary_theme,
    ths.heat_label,
    ROUND(ths.composite_heat_score, 1)   AS theme_heat_score,
    ROUND(ths.ml_signal_score, 1)        AS theme_ml_score,
    ROUND(ths.buy_signal_pct, 1)         AS theme_buy_pct,
    ROUND(ths.avg_1w_return_pct, 2)      AS theme_1w_return,
    rl.rotation_signal,
    ROUND(rl.score_change, 1)            AS theme_wk_change,
    rl.label_changed,
    p.predicted_signal,
    p.signal_strength,
    ROUND(p.confidence * 100, 1)         AS confidence_pct,
    ROUND(p.buy_probability * 100, 1)    AS buy_prob_pct,
    ROUND(p.sell_probability * 100, 1)   AS sell_prob_pct,
    p.RSI, p.rsi_category,
    ROUND(p.close_price, 2)              AS close_price,
    p.trading_date,
    -- ASCII-safe conviction text (no unicode stars)
    CASE
        WHEN ths.heat_label = 'Hot'
             AND p.predicted_signal = 'BUY'
             AND rl.rotation_signal IN ('Accelerating','Improving') THEN 'FULL+ (hot + accelerating)'
        WHEN ths.heat_label = 'Hot'      AND p.predicted_signal = 'BUY'  THEN 'FULL size'
        WHEN ths.heat_label = 'Rising'   AND p.predicted_signal = 'BUY'  THEN 'STANDARD'
        WHEN ths.heat_label = 'Emerging' AND p.predicted_signal = 'BUY'  THEN 'HALF size'
        WHEN ths.heat_label IN ('Steady','Caution')
                                         AND p.predicted_signal = 'BUY'  THEN 'WATCH only'
        WHEN p.predicted_signal = 'SELL'
             AND rl.rotation_signal = 'Exiting'                          THEN 'EXIT - theme cooling'
        WHEN p.predicted_signal = 'SELL'                                 THEN 'EXIT signal'
        ELSE                                                                   'HOLD'
    END AS conviction_action
FROM current_pred p
JOIN nasdaq_top100 n        ON p.ticker = n.ticker
JOIN nasdaq_theme_mapping m ON p.ticker = m.ticker AND m.is_active = 1
LEFT JOIN latest_scores ths ON m.theme = ths.theme
LEFT JOIN latest_rotation rl ON m.theme = rl.theme
WHERE p.predicted_signal IN ('BUY', 'SELL');
GO
