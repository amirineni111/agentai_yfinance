# CLAUDE.md — streamlit-trading-dashboard (Visualization + Signal Tracking)

> **Project context file for AI assistants (Claude, Copilot, Cursor).**

---

## 1. SYSTEM OVERVIEW

This is the **visualization and signal tracking** layer — one of **7 interconnected repositories** that form an AI-powered stock trading analytics platform.

### Repository Map

| Layer | Repo | Purpose |
|-------|------|---------|
| Data Ingestion | `stockanalysis` | ETL: yfinance/Alpha Vantage → SQL Server |
| SQL Infrastructure | `sqlserver_mcp` | .NET 8 MCP Server (Microsoft MssqlMcp) — 7 tools (ListTables, DescribeTable, ReadData, CreateTable, DropTable, InsertData, UpdateData) via stdio transport for AI IDE ↔ SQL Server |
| **Dashboard** ⭐ | **`streamlit-trading-dashboard`** | **THIS REPO** — 40+ SQL views, signal tracking, AI predictions, 15-page Streamlit UI |
| ML: NASDAQ | `sqlserver_copilot` | Gradient Boosting → `ml_trading_predictions` (since June 2026: ALL ~2,300 tickers daily; suppressed rows have `is_actionable=0` / `signal_strength='Suppressed'` — filter `ISNULL(is_actionable,1)=1` for tradeable signals. Views `vw_strategy2_unified_ml_predictions`, `vw_theme_ml_signal_score`, `vw_theme_stock_signals` already apply this; see `sql/2026-06-12_views_is_actionable_filter.sql`) |
| ML: NSE | `sqlserver_copilot_nse` | 5-model ensemble → `ml_nse_trading_predictions` |
| ML: Forex | `sqlserver_copilot_forex` | XGBoost/LightGBM → `forex_ml_predictions` |
| Agentic AI | `stockdata_agenticai` | 7 CrewAI agents, daily briefing email |

---

## 2. THIS REPO: streamlit-trading-dashboard

### Purpose
Serves a **dual role**:
1. **SQL View Creation**: Creates and maintains 40+ SQL views for technical indicators, signals, and fundamental screening used by the entire ecosystem
2. **15-page Streamlit Dashboard**: Interactive visualization of all trading data, ML predictions, signals, and portfolio tracking
3. **Scheduled Jobs**: Daily AI direction predictions (7-day UP/FLAT/DOWN classifier, one run per market) and signal tracking (7 PM)

### Daily Schedule
```
Evening    AI direction predictions → ai_prediction_history (LGB+LogReg 'Ensemble', 7-day UP/FLAT/DOWN)
           run_predictions_{nasdaq,nse,forex}.bat → daily_prediction_job.py --market ...
07:00 PM   Signal tracking          → signal_tracking_history
On-demand  Dashboard server         → streamlit run streamlitapp_20251123_v2.py
```

### Key Files

> **File names below are verified against the working tree (2026-09-04).**
> `app.py`, `create_views.py`, `signal_tracker.py`, `create_signal_tracking.py`
> and `setup_scheduler.bat` were documented here for months and **none of them
> have ever existed**. There is no Python view-deployment layer at all.

```
streamlit-trading-dashboard/
├── streamlitapp_20251123_v2.py      # MAIN — 12,085-line monolithic Streamlit app
├── daily_prediction_job.py          # AI direction pipeline (LGB+LogReg, 7-day UP/FLAT/DOWN)
├── backfill_actual_prices.py        # Strategy 2 outcome backfill; owns the shared grading SQL
├── backfill_strategy1_outcomes.py   # Strategy 1 outcome backfill (NASDAQ/NSE/Forex ML tables)
├── daily_signal_tracking_job.py     # Signal tracking job (7 PM)
├── run_predictions_{nasdaq,nse,forex}.bat  # Per-market launchers
├── run_signal_tracking.bat          # Signal tracking launcher
├── setup_scheduled_task.ps1         # Task Scheduler setup — AI predictions
├── setup_signal_tracking_task.ps1   # Task Scheduler setup — signal tracking
├── sql/                             # Dated, idempotent migrations (run manually in SSMS)
├── *.sql (repo root)                # View DDL — standalone SSMS scripts, NOT run from Python
├── requirements.txt                 # Streamlit + pandas + plotly + pyodbc
├── .streamlit/
│   └── config.toml                  # Streamlit theme configuration
└── (no pages/ package — all 15 pages live in streamlitapp_20251123_v2.py)
    # 15 pages embedded in the main app:
    # 1. Dashboard Overview
    # 2. NASDAQ Analysis
    # 3. NSE Analysis
    # 4. Forex Analysis
    # 5. AI Predictions
    # 6. ML Trading Signals
    # 7. Technical Indicators
    # 8. Signal Tracker
    # 9. Strategy Combos (TIER 1/2)
    # 10. Cross-Strategy Analysis
    # 11. Fundamental Analysis
    # 12. Portfolio Tracker
    # 13. Trade Journal
    # 14. Risk Dashboard
    # 15. Settings / Admin
```

---

## 3. SQL VIEWS CREATED (40+)

This repo creates views consumed by the **entire ecosystem** including the agentic AI agents.

### Technical Indicator Views (per market: NASDAQ, NSE, Forex)
| View Pattern | Indicators |
|-------------|------------|
| `{market}_RSI_calculation` | RSI (14-period) |
| `{market}_macd` | MACD line, signal, histogram |
| `{market}_bollingerband` | BB upper/lower/width/position |
| `{market}_ema_sma_view` | SMA/EMA multiple periods |
| `{market}_atr` | Average True Range |
| `{market}_stochastic` | Stochastic %K/%D |
| `{market}_fibonacci` | Fibonacci retracement levels |
| `{market}_support_resistance` | Support/resistance zones |
| `{market}_patterns` | Candlestick pattern recognition |

### Signal Views (per market)
| View Pattern | Purpose |
|-------------|---------|
| `{market}_rsi_signals` | RSI overbought/oversold signals |
| `{market}_macd_signals` | MACD crossover signals |
| `{market}_bb_signals` | Bollinger Band breakout signals |
| `{market}_sma_signals` | SMA crossover signals |
| `{market}_atr_spikes` | ATR volatility spike detection |

### Crossover Aggregate Views
| View | Purpose |
|------|---------|
| `vw_crossover_signals_NASDAQ_100` | All crossover signals for NASDAQ |
| `vw_crossover_signals_NSE_500` | All crossover signals for NSE |
| `vw_crossover_signals_Forex` | All crossover signals for Forex |

### Strategy Views
| View | Purpose |
|------|---------|
| `vw_PowerBI_AI_Technical_Combos` | TIER 1/2 trade signals (AI + 6 tech indicators) |
| `vw_strategy2_trade_opportunities` | Trade grades A-D (ML classifier + RSI alignment) |

### Fundamental Screening Views
| View | Purpose |
|------|---------|
| `vw_value_stocks_screen` | Value investing criteria |
| `vw_quality_stocks_screen` | Quality metrics screening |
| `vw_growth_stocks_screen` | Growth stock screening |
| `vw_dividend_stocks_screen` | Dividend yield screening |
| `vw_fundamental_scoring` | Composite fundamental score |

### Performance Views
| View | Purpose |
|------|---------|
| `vw_signal_performance_summary` | Signal win/loss rates by type |
| `vw_model_performance_summary` | ML model accuracy over time |
| `vw_recent_prediction_accuracy` | Recent prediction accuracy |

---

## 4. AI PREDICTION PIPELINE

> **This section was wrong until 2026-09-03.** It described an `ai_predictions.py`
> producing LR/GB/RF next-day *price* forecasts. No such file has ever existed in
> this repo, and the pipeline has been a direction classifier since March 2026. An
> external model review trusted this section and concluded the live model was a
> frozen heuristic. Keep this section accurate — it is load-bearing.

### `daily_prediction_job.py` — Runs daily, one invocation per market

| Launcher | Command |
|---|---|
| `run_predictions_nasdaq.bat` | `daily_prediction_job.py --market "NASDAQ 100"` |
| `run_predictions_nse.bat` | `daily_prediction_job.py --market "NSE 500"` |
| `run_predictions_forex.bat` | `daily_prediction_job.py --market "Forex"` |

**It is a direction classifier, not a price model.** Predicts one of three
classes over a **7-day** horizon: `UP` / `FLAT` / `DOWN`.

| Aspect | Detail |
|---|---|
| Models | LightGBM (`LGBMClassifier`) + `LogisticRegression`, blended by walk-forward accuracy share (weights clamped to `[0.30, 0.70]`) |
| Training | **Retrained from scratch every run**, per sector, per market. Nothing is pickled — there is no persisted artifact. NASDAQ trains 12 GICS sector models; NSE and Forex train one pooled model each. |
| `model_name` | `'Ensemble'` — the LGB+LR blend. LR/GB/RF were retired 2026-02-12 (`RETIRED_MODELS`). |
| Features | 17, in `SELECTED_FEATURES_V4` (price/RSI/MACD/BB/volume/volatility/52w/relative strength/sector momentum + 4 sentiment features) |
| Validation | 5-window walk-forward with a purge gap; the **blended** ensemble is scored, not the two models separately |
| FLAT band | Recalibrated **every run** per market to `0.5 x median(|7-day return|)`, clamped `[0.8%, 4%]`. Stored per row in `flat_band_pct`. |
| Confidence | Isotonic calibration of winning-class probability → P(correct), fitted on out-of-fold walk-forward predictions. Bounds `[5, 95]` are a sanity guard only. |
| Actionability | `is_actionable=1` requires: clean price series, a non-FLAT call, an expected move at least as large as the market's calibrated FLAT band, and `model_confidence >= ACTIONABLE_CONFIDENCE_MIN`. Market regime is recorded in `suppression_reason` but no longer gates. |

**Exit codes.** The job exits non-zero when the outcome backfill fails, when a
run stores zero predictions despite errors, or when more than `MAX_ERROR_RATE`
of tickers error. All three previously reported `LastResult=0` to Task
Scheduler while doing nothing useful — on 2026-09-03 the Forex run errored on
14/14 tickers against a missing column, exited 0, and left the market a day
stale with nothing flagging it.

**`predicted_price` is not a forecast.** The model outputs direction only;
magnitude is filled in as `sign(class) x robust_vol(recent n-day returns)`. So
`absolute_error` / `squared_error` / `percentage_error` measure the stock's
volatility, **not** model skill. Judge the model on directional accuracy and
per-class lift.

Volatility uses a MAD estimator, not `std`, and is capped at
`MAX_PREDICTED_MOVE_PCT`. Plain `std` blew up on tickers with an unadjusted
reverse split — a single discontinuity contaminates `days_ahead` overlapping
windows, producing printed moves like ALIT −989% and AMOD +801%. Winsorizing
does not help (11.7% of windows contaminated); MAD does. Tickers with any
recent |n-day return| > `SPLIT_ARTIFACT_RETURN` are marked
`is_actionable=0 / suppression_reason='PRICE_ARTIFACT'`, because a corrupt
price series also corrupts every price-derived feature — so the *direction*
call is untrustworthy too, not just the magnitude.

### Output Table: `ai_prediction_history`
| Column | Type | Description |
|--------|------|-------------|
| market | VARCHAR | 'NASDAQ 100', 'NSE 500', 'Forex' |
| ticker | VARCHAR | Stock/pair symbol |
| prediction_date | DATE | When prediction was made |
| target_date | DATE | `prediction_date + days_ahead` (calendar days) |
| days_ahead | INT | 7 (1-day and 3-day horizons are disabled — both were sub-random) |
| model_name | VARCHAR | `'Ensemble'` since 2026-02-12 |
| predicted_direction | VARCHAR | `'UP'` / `'FLAT'` / `'DOWN'`. **NULL on legacy rows** (before 2026-05-25) — those are binary and graded differently. |
| predicted_price | FLOAT | Volatility-scaled magnitude proxy — *not* a price forecast |
| model_confidence | DECIMAL(5,2) | Calibrated P(correct) as a percentage |
| flat_band_pct | FLOAT | The FLAT band in force when this row was written; the grader scores FLAT against **this**, not a constant |
| is_actionable | BIT | 1 = tradeable signal. Consumers filter `ISNULL(is_actionable,1)=1` |
| suppression_reason | VARCHAR | `'PRICE_ARTIFACT'` / `'FLAT'` / `'IMMATERIAL'` / `'LOW_CONFIDENCE'`, optionally suffixed `/SIDEWAYS` or `/INSUFFICIENT`. Evaluated in that order — the first that applies wins. |
| actual_price | FLOAT | Last close in `[prediction_date, target_date]`, filled by the backfill |
| direction_correct | BIT | Graded per class; FLAT uses `flat_band_pct` |
| absolute_error, squared_error, percentage_error | FLOAT | Magnitude-proxy error — see caveat above |

### Measuring accuracy correctly

A single blended accuracy number over this table is **not interpretable**:

- The three classes have different base rates. FLAT's band is `0.5x` the median
  absolute move, so FLAT is correct roughly 30% of the time by construction,
  while UP/DOWN sit near 50%. Averaging drags the headline toward ~49%.
- The table spans three eras: retired LR/GB/RF rows, legacy binary rows
  (`predicted_direction IS NULL`), and current 3-class rows. On NASDAQ the
  legacy rows outnumber the current ones.

Always scope to `prediction_date >= '2026-05-25' AND predicted_direction IS NOT NULL`,
filter `ISNULL(is_actionable,1)=1`, and report **balanced accuracy** plus
**per-class lift over base rate**.

### Outcome backfill

`update_actual_prices()` runs as Step 1 of every job invocation and covers **all
three markets regardless of `--market`** — whichever launcher runs first does the
work. `backfill_actual_prices.py` is the standalone recovery version; both import
the same `DIRECTION_CORRECT_SQL` so they cannot grade a row differently.

Predictions resolve against the last close in `[prediction_date, target_date]`.
The lower bound matters: without it a ticker with a stalled feed resolves against
a pre-prediction bar. Rows on stalled tickers stay unresolved by design.

**Normal pending backlog is ~5 trading days x ticker count** (~11k NASDAQ, ~10k NSE)
— those are 7-day predictions whose `target_date` has not arrived. Only rows with
an *elapsed* `target_date` and `actual_price IS NULL` indicate a problem; the job
logs those as `STILL unresolved past target_date` and exits non-zero.

---

## 5. SIGNAL TRACKING

### `daily_signal_tracking_job.py` — Runs daily at 7:00 PM
Tracks outcomes of trading signals at 7-day, 14-day, and 30-day horizons.

### Output Table: `signal_tracking_history`
| Column | Type | Description |
|--------|------|-------------|
| market | VARCHAR | 'NASDAQ_100', 'NSE_500', 'Forex' |
| ticker | VARCHAR | Stock/pair symbol |
| signal_date | DATE | Date signal was generated |
| signal_type | VARCHAR | 'BULLISH'/'BEARISH' |
| signal_strength | VARCHAR | 'Strong'/'Moderate'/'Weak' |
| result_7d | VARCHAR | 'Win'/'Loss'/'Pending' |
| result_14d | VARCHAR | Same |
| result_30d | VARCHAR | Same |
| actual_change_7d | FLOAT | Actual price change at 7d |

---

## 6. DATABASE CONTEXT

### Connection
- **Server**: `192.168.87.27\MSSQLSERVER01` (Machine A LAN IP)
- **Database**: `stockdata_db`
- **Auth**: SQL Auth (`remote_user` via .env — credentials in code for legacy pages is a known security issue)

### Tables This Repo READS
All market data + ML prediction tables from the ecosystem.

### Tables This Repo WRITES
| Table | Purpose |
|-------|---------|
| `ai_prediction_history` | AI price predictions (LR/GB/RF) |
| `signal_tracking_history` | Signal outcome tracking |
| `daily_signals_history` | Daily signal snapshots |

### Views This Repo CREATES
40+ views (see Section 3 above) consumed by all other repos.

---

## 7. KNOWN ISSUES

### Critical
- **Monolithic main app**: `streamlitapp_20251123_v2.py` is 12,085 lines in a single file — needs decomposition into pages/
- **SQL credentials in code**: Connection strings with username/password hardcoded (should use .env)
- **No tests**: No automated test suite

### Improvements Needed
- Break `streamlitapp_20251123_v2.py` into separate page modules (Streamlit multipage app pattern)
- Move SQL credentials to .env
- Add caching for expensive SQL queries (`@st.cache_data`)
- Add error handling for database connection failures
- Consolidate the root-level view DDL scripts into `sql/` with dated, idempotent migrations

---

## 8. MCP SERVER FOR DEVELOPMENT

The `sqlserver_mcp` repo provides an MCP server for AI IDEs to query `stockdata_db` directly during development.

### VS Code Configuration
```json
"MSSQL MCP": {
    "type": "stdio",
    "command": "C:\\Users\\sreea\\OneDrive\\Desktop\\sqlserver_mcp\\SQL-AI-samples\\MssqlMcp\\dotnet\\MssqlMcp\\bin\\Debug\\net8.0\\MssqlMcp.exe",
    "env": {
        "CONNECTION_STRING": "Server=192.168.87.27\\MSSQLSERVER01;Database=stockdata_db;User Id=remote_user;Password=YourStrongPassword123!;TrustServerCertificate=True"
    }
}
```

### 7 MCP Tools: ListTables, DescribeTable, ReadData, CreateTable, DropTable, InsertData, UpdateData

Useful for: verifying view definitions, checking `ai_prediction_history` data, exploring `signal_tracking_history` output, validating indicator calculations.
