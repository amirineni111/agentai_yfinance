# AGENTS.md — streamlit-trading-dashboard

## Overview
This repo does NOT contain CrewAI agents. It is a **Streamlit dashboard** with 15 pages, **40+ SQL view creator**, and **scheduled signal tracking + AI prediction** jobs.

## Architecture

```
[SQL Server: stockdata_db]
        │
        ├─ *.sql (repo root + sql/) → 40+ SQL views, run manually in SSMS
        │   (Technical indicators, signals, strategies, fundamentals)
        │   NOTE: there is no create_views.py and never has been.
        │
        ├─ daily_prediction_job.py → Daily, one run per market
        │   (LightGBM+LogReg 'Ensemble', 7-day UP/FLAT/DOWN → ai_prediction_history)
        │
        ├─ daily_signal_tracking_job.py → Daily 7 PM
        │   (Signal outcome tracking → signal_tracking_history)
        │
        └─ streamlitapp_20251123_v2.py → Streamlit dashboard (12,085 lines)
            (15 pages: Overview, NASDAQ, NSE, Forex, AI Predictions,
             ML Signals, Tech Indicators, Signal Tracker, Strategy Combos,
             Cross-Strategy, Fundamentals, Portfolio, Trade Journal, Risk, Admin)
```

## SQL Views Created (40+)
This repo creates views consumed by the **entire ecosystem**:
- Per-market technical indicators (RSI, MACD, BB, SMA/EMA, ATR, Stochastic, Fibonacci, S/R, Patterns)
- Per-market signal views (RSI/MACD/BB/SMA signals, ATR spikes)
- Crossover aggregate views per market
- Strategy views: `vw_PowerBI_AI_Technical_Combos`, `vw_strategy2_trade_opportunities`
- Fundamental screening views (value, quality, growth, dividend, scoring)
- Performance summary views

## Downstream Impact
When views in this repo change, it affects:
- `stockdata_agenticai` — agents query these views
- All ML pipelines — some queries reference these views
- `sqlserver_mcp` — MCP server exposes these views

## Known Issue
`streamlitapp_20251123_v2.py` is 12,085 lines — monolithic. Needs decomposition into Streamlit multipage pattern.
