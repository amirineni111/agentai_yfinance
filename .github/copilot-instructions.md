# Copilot Instructions — streamlit-trading-dashboard

## Project Context
This is the **visualization and signal tracking** layer of a 7-repo stock trading analytics platform. Creates 40+ SQL views, runs daily AI predictions and signal tracking, and serves a 15-page Streamlit dashboard.

## Key Architecture Rules
- Creates **40+ SQL views** consumed by the entire ecosystem (technical indicators, signals, strategies, fundamentals)
- **app.py** is 11,658 lines (monolithic — needs decomposition into pages/)
- Daily scheduled jobs: AI predictions (6 PM), signal tracking (7 PM)
- SQL credentials are **hardcoded** (known issue — should use .env)
- Connected to `stockdata_db` on `localhost\MSSQLSERVER01`

## Three Responsibilities
1. **View Creation**: `create_views.py` creates 40+ views (run once/on schema change)
2. **Scheduled Jobs**: `daily_prediction_job.py --market ...` (7-day UP/FLAT/DOWN direction classifier, LightGBM+LogReg, retrained every run) + signal_tracker.py (7 PM)
3. **Dashboard**: `streamlit run app.py` → 15-page interactive UI

## Key SQL Views Created
- `vw_PowerBI_AI_Technical_Combos` — TIER 1/2 trade signals (used by agentic AI)
- `vw_strategy2_trade_opportunities` — Trade grades A-D (used by agentic AI)
- `{market}_RSI_calculation`, `{market}_macd`, `{market}_bollingerband`, etc.
- `vw_crossover_signals_*` — Aggregate crossover signals per market
- `vw_*_stocks_screen` — Fundamental screening views

## Tables Written
- `ai_prediction_history` — LR/GB/RF price predictions
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
