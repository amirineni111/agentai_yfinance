# Copilot Instructions — streamlit-trading-dashboard

## Project Context
This is the **visualization and signal tracking** layer of a 7-repo stock trading analytics platform. Creates 40+ SQL views, runs daily AI predictions and signal tracking, and serves a 15-page Streamlit dashboard.

## Key Architecture Rules
- Creates **40+ SQL views** consumed by the entire ecosystem (technical indicators, signals, strategies, fundamentals)
- **streamlitapp_20251123_v2.py** is 12,085 lines (monolithic — needs decomposition into pages/)
- Daily scheduled jobs: AI predictions (6 PM), signal tracking (7 PM)
- SQL credentials are **hardcoded** (known issue — should use .env)
- Connected to `stockdata_db` on `localhost\MSSQLSERVER01`

## Three Responsibilities
1. **View Creation**: standalone `.sql` scripts in the repo root and `sql/`, run manually in SSMS. There is no `create_views.py` and never has been.
2. **Scheduled Jobs**: `daily_prediction_job.py --market ...` (7-day UP/FLAT/DOWN direction classifier, LightGBM+LogReg, retrained every run) + daily_signal_tracking_job.py (7 PM)
3. **Dashboard**: `streamlit run streamlitapp_20251123_v2.py` → 15-page interactive UI

## Key SQL Views Created
- `vw_PowerBI_AI_Technical_Combos` — TIER 1/2 trade signals (used by agentic AI)
- `vw_strategy2_trade_opportunities` — Trade grades A-D (used by agentic AI)
- `{market}_RSI_calculation`, `{market}_macd`, `{market}_bollingerband`, etc.
- `vw_crossover_signals_*` — Aggregate crossover signals per market
- `vw_*_stocks_screen` — Fundamental screening views

## Tables Written
- `ai_prediction_history` — 7-day UP/FLAT/DOWN **direction** classifications from the
  LightGBM+LogReg 'Ensemble'. NOT price predictions: LR/GB/RF were retired 2026-02-12,
  and `predicted_price` is a volatility-scaled magnitude proxy, not a forecast.
  See CLAUDE.md section 4 — this line was wrong for months and misled a model review.
- `signal_tracking_history` — Signal outcomes at 7d/14d/30d
- `daily_signals_history` — Daily signal snapshots

## Sibling Repositories (same database)
- `stockdata_agenticai` — CrewAI agents (major consumer of views)
- `sqlserver_copilot` / `sqlserver_copilot_nse` / `sqlserver_copilot_forex` — ML pipelines
- `sqlserver_mcp` — .NET 8 MCP Server (Microsoft MssqlMcp) with 7 tools: ListTables, DescribeTable, ReadData, CreateTable, DropTable, InsertData, UpdateData. Stdio transport. Use to explore DB schemas and verify view definitions during development.
- `stockanalysis` — Data ingestion ETL

## MCP Server for Development
Configure in `.vscode/mcp.json` to query stockdata_db directly from your AI IDE:
```json
"MSSQL MCP": {
    "type": "stdio",
    "command": "C:\\Users\\sreea\\OneDrive\\Desktop\\sqlserver_mcp\\SQL-AI-samples\\MssqlMcp\\dotnet\\MssqlMcp\\bin\\Debug\\net8.0\\MssqlMcp.exe",
    "env": {
        "CONNECTION_STRING": "Server=localhost\\MSSQLSERVER01;Database=stockdata_db;Trusted_Connection=True;TrustServerCertificate=True"
    }
}
```
Useful for: verifying view definitions, checking AI prediction data, validating signal tracking output.
