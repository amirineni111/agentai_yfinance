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
| ML: NASDAQ | `sqlserver_copilot` | Gradient Boosting → `ml_trading_predictions` |
| ML: NSE | `sqlserver_copilot_nse` | 5-model ensemble → `ml_nse_trading_predictions` |
| ML: Forex | `sqlserver_copilot_forex` | XGBoost/LightGBM → `forex_ml_predictions` |
| Agentic AI | `stockdata_agenticai` | 7 CrewAI agents, daily briefing email |

---

## 2. THIS REPO: streamlit-trading-dashboard

### Purpose
Serves a **dual role**:
1. **SQL View Creation**: Creates and maintains 40+ SQL views for technical indicators, signals, and fundamental screening used by the entire ecosystem
2. **15-page Streamlit Dashboard**: Interactive visualization of all trading data, ML predictions, signals, and portfolio tracking
3. **Scheduled Jobs**: Daily AI price predictions (6 PM) and signal tracking (7 PM)

### Daily Schedule
```
06:00 PM  AI price predictions      → ai_prediction_history (LR/GB/RF models)
07:00 PM  Signal tracking           → signal_tracking_history
On-demand  Dashboard server         → streamlit run app.py
```

### Key Files

```
streamlit-trading-dashboard/
├── app.py                           # MAIN — 11,658-line monolithic Streamlit app
├── create_views.py                  # Creates 40+ SQL views (run once / on schema change)
├── create_signal_tracking.py        # Creates signal_tracking_history table
├── ai_predictions.py                # AI price prediction pipeline (LR/GB/RF)
├── signal_tracker.py                # Signal tracking job
├── setup_scheduler.bat              # Task Scheduler setup for daily jobs
├── requirements.txt                 # Streamlit + pandas + plotly + pyodbc
├── .streamlit/
│   └── config.toml                  # Streamlit theme configuration
└── pages/ (or all in app.py)
    # 15 pages embedded in app.py:
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

### `ai_predictions.py` — Runs daily at 6:00 PM
Trains 3 lightweight price prediction models on each stock in the prediction watchlist:

| Model | Algorithm | Purpose |
|-------|-----------|---------|
| LR | Linear Regression | Baseline price prediction |
| GB | Gradient Boosting Regressor | Non-linear prediction |
| RF | Random Forest Regressor | Ensemble prediction |

### Output Table: `ai_prediction_history`
| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR | Stock symbol |
| prediction_date | DATE | When prediction was made |
| model_name | VARCHAR | 'LR', 'GB', or 'RF' |
| predicted_price | FLOAT | Model's next-day price |
| actual_price | FLOAT | Actual price (filled next day) |
| direction_correct | BIT | Was direction right? |
| absolute_error | FLOAT | |predicted - actual| |
| percentage_error | FLOAT | Error as % of actual |

---

## 5. SIGNAL TRACKING

### `signal_tracker.py` — Runs daily at 7:00 PM
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
- **Monolithic app.py**: 11,658 lines in a single file — needs decomposition into pages/
- **SQL credentials in code**: Connection strings with username/password hardcoded (should use .env)
- **No tests**: No automated test suite

### Improvements Needed
- Break `app.py` into separate page modules (Streamlit multipage app pattern)
- Move SQL credentials to .env
- Add caching for expensive SQL queries (`@st.cache_data`)
- Add error handling for database connection failures
- Create separate `create_views.sql` script (currently Python-based)

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
