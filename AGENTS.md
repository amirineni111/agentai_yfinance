# AGENTS.md — streamlit-trading-dashboard

## Overview
This repo does NOT contain CrewAI agents. It is a **Streamlit dashboard** with 15 pages, **40+ SQL view creator**, and **scheduled signal tracking + AI prediction** jobs.

## Architecture

```
[SQL Server: stockdata_db]
        │
        ├─ create_views.py → Creates 40+ SQL views
        │   (Technical indicators, signals, strategies, fundamentals)
        │
        ├─ ai_predictions.py → Daily 6 PM
        │   (LR/GB/RF price predictions → ai_prediction_history)
        │
        ├─ signal_tracker.py → Daily 7 PM
        │   (Signal outcome tracking → signal_tracking_history)
        │
        └─ app.py → Streamlit dashboard (11,658 lines)
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
`app.py` is 11,658 lines — monolithic. Needs decomposition into Streamlit multipage pattern.
