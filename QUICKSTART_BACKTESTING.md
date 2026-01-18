# 🚀 Quick Start - AI Prediction Backtesting

## ⚡ 3-Step Setup (5 Minutes)

### Step 1: Create Database Table (1 min)
```powershell
cd C:\Users\sreea\OneDrive\Desktop\streamlit-trading-dashboard
sqlcmd -S localhost\MSSQLSERVER01 -d stockdata_db -i create_prediction_history_table.sql
```
✅ Creates `ai_prediction_history` table and views

---

### Step 2: Run First Prediction Job (10-15 min)
```powershell
python daily_prediction_job.py
```
✅ Generates initial predictions for top 50 stocks in each market  
✅ Uses XGBoost, Random Forest, and Gradient Boosting  
✅ Predicts for 1, 3, and 7 days ahead

**Expected Output:**
```
[2026-01-17 18:00:00] [INFO] Starting Daily AI Price Prediction Job
...
[2026-01-17 18:15:23] [INFO] Total Predictions Generated: 450
```

---

### Step 3: Setup Daily Automation (2 min)
```powershell
# Run as Administrator
powershell -ExecutionPolicy Bypass -File setup_scheduled_task.ps1
```
✅ Creates scheduled task "AI_Price_Prediction_Daily"  
✅ Runs daily at 6:00 PM automatically

---

## 📊 View Results

### In Dashboard:
```powershell
streamlit run streamlitapp_20251123_v2.py
```

1. **Home Page** → Select market & stock
2. **AI Price Predictions** page
3. Check box: **"🔍 Show Prediction Accuracy Analysis"**

You'll see:
- ✅ Model performance summary (MAE, RMSE, accuracy)
- ✅ Recent predictions vs actual prices
- ✅ Accuracy statistics per stock
- ✅ Timeline chart showing prediction trends

---

## 📅 Timeline

| Day | What to Expect |
|-----|----------------|
| **Today** | Initial predictions generated (all pending) |
| **Day 2** | 1-day predictions show actuals, accuracy metrics start |
| **Day 4** | 3-day predictions complete |
| **Day 8** | 7-day predictions complete, full backtesting available |
| **Week 2+** | Clear trends showing best models |

---

## ✅ Verification Checklist

After setup, verify:

```powershell
# 1. Check database table exists
sqlcmd -S localhost\MSSQLSERVER01 -d stockdata_db -Q "SELECT COUNT(*) as prediction_count FROM ai_prediction_history"

# 2. Check scheduled task
Get-ScheduledTask -TaskName "AI_Price_Prediction_Daily"

# 3. View log file
Get-Content prediction_job.log -Tail 10

# 4. Test manual run
.\run_daily_predictions.bat
```

---

## 🎯 What Gets Predicted?

- **Markets:** NSE 500, NASDAQ 100, Forex
- **Stocks:** Top 50 by volume in each market
- **Models:** XGBoost, Random Forest, Gradient Boosting
- **Timeframes:** 1-day, 3-day, 7-day predictions
- **Daily Total:** ~450 predictions (50 stocks × 3 markets × 3 timeframes)

---

## 📈 Accuracy Metrics

For each prediction, you'll see:

| Metric | What It Means | Good Value |
|--------|---------------|------------|
| **MAE** | Average price error | < 2% |
| **RMSE** | Penalized large errors | < 3% |
| **Direction** | % correct up/down | > 60% |
| **Error %** | Error as % of price | < 5% |

---

## 🔧 Troubleshooting

**Problem:** "Table does not exist"  
**Solution:** Re-run Step 1 SQL script

**Problem:** Task doesn't run  
**Solution:** Check Task Scheduler, ensure PC is on at 6 PM

**Problem:** No data in dashboard  
**Solution:** Wait 24 hours for first actuals, or select a different stock

**Problem:** Python errors  
**Solution:** `pip install xgboost scikit-learn pandas numpy pyodbc`

---

## 📖 Full Documentation

For detailed information:
- **Setup Guide:** [BACKTESTING_SETUP_GUIDE.md](BACKTESTING_SETUP_GUIDE.md)
- **Implementation:** [BACKTESTING_IMPLEMENTATION.md](BACKTESTING_IMPLEMENTATION.md)

---

## 🎉 That's It!

Your backtesting system is now:
✅ Generating predictions daily  
✅ Tracking accuracy automatically  
✅ Comparing models performance  
✅ Available in your dashboard  

**Next:** Let it run for a week, then review accuracy metrics! 📊
