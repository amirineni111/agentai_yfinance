# 🤖 AI Price Prediction Backtesting Setup Guide

## Overview

This backtesting system automatically:
- ✅ Generates daily predictions for all markets (NSE, NASDAQ, Forex)
- ✅ Stores predictions with timestamps
- ✅ Compares predictions vs actual prices
- ✅ Tracks model accuracy over time
- ✅ Shows which models perform best

---

## 📋 Setup Steps

### Step 1: Create Database Table

Run the SQL script to create the prediction history table:

```powershell
# In PowerShell or SQL Server Management Studio
sqlcmd -S localhost\MSSQLSERVER01 -d stockdata_db -i create_prediction_history_table.sql
```

Or manually execute `create_prediction_history_table.sql` in SSMS.

**What this creates:**
- `ai_prediction_history` table - stores all predictions
- `vw_model_performance_summary` view - model accuracy metrics
- `vw_recent_prediction_accuracy` view - recent predictions vs actuals

---

### Step 2: Test the Daily Prediction Job

Run the prediction job manually to test it:

```powershell
python daily_prediction_job.py
```

**What it does:**
1. Updates actual prices for past predictions (where target_date has arrived)
2. Generates new predictions for top 50 stocks in each market
3. Uses 3 models: XGBoost, Random Forest, Gradient Boosting
4. Predicts for 1, 3, and 7 days ahead
5. Stores predictions in database

**Expected output:**
```
[2026-01-17 18:00:00] [INFO] Starting Daily AI Price Prediction Job
[2026-01-17 18:00:05] [INFO] Step 1: Updating actual prices for past predictions...
[2026-01-17 18:00:06] [INFO] Updated 42 predictions with actual prices
[2026-01-17 18:00:08] [INFO] Step 2: Processing NSE 500...
[2026-01-17 18:00:10] [INFO]   Found 50 stocks to analyze
...
[2026-01-17 18:15:23] [INFO] Daily Prediction Job Completed Successfully!
[2026-01-17 18:15:23] [INFO] Total Predictions Generated: 450
```

---

### Step 3: Setup Daily Automation (Windows Task Scheduler)

**Option A: Automatic Setup (Recommended)**

Run the PowerShell setup script:

```powershell
# Right-click PowerShell and "Run as Administrator"
cd C:\Users\sreea\OneDrive\Desktop\streamlit-trading-dashboard
.\setup_scheduled_task.ps1
```

This will:
- Create a scheduled task named "AI_Price_Prediction_Daily"
- Schedule it to run daily at 6:00 PM
- Configure it to run even if computer is on battery
- Set execution timeout to 2 hours

**Option B: Manual Setup**

1. Open Task Scheduler (`Win + R` → type `taskschd.msc`)
2. Click "Create Basic Task"
3. Name: `AI_Price_Prediction_Daily`
4. Trigger: Daily at 6:00 PM
5. Action: Start a program
6. Program: Browse to `run_daily_predictions.bat`
7. Finish and test by right-clicking → Run

---

### Step 4: View Backtesting Results in Dashboard

1. **Start your Streamlit dashboard:**
   ```powershell
   streamlit run streamlitapp_20251123_v2.py
   ```

2. **Navigate to:**
   - Select a market and stock from Home page
   - Go to "AI Price Predictions" page
   - Check the box "🔍 Show Prediction Accuracy Analysis"

3. **What you'll see:**
   - **Model Performance Summary** - MAE, RMSE, directional accuracy by model
   - **Recent Predictions vs Actuals** - Your predictions compared to actual prices
   - **Accuracy Statistics** - How well models performed for selected stock
   - **Error Timeline Chart** - Prediction accuracy trends over time

---

## 📊 Understanding the Metrics

### Accuracy Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| **MAE** (Mean Absolute Error) | Average difference between predicted and actual price | Lower is better (< 2% for stocks) |
| **RMSE** (Root Mean Squared Error) | Penalizes large errors more heavily | Lower is better (< 3% for stocks) |
| **Direction Accuracy** | % of times model predicted correct up/down direction | Higher is better (> 60% is good) |
| **Error %** | Error as percentage of actual price | Lower is better (< 5% is acceptable) |

### Model Comparison

After a few weeks of data collection, you'll see which models perform best:

**Example Results:**
```
7-Day Predictions:
1. XGBoost      - MAE: 1.2%, RMSE: 1.8%, Direction: 67%  ✅ Best
2. Random Forest - MAE: 1.5%, RMSE: 2.1%, Direction: 62%
3. Gradient Boost - MAE: 1.7%, RMSE: 2.3%, Direction: 58%
```

---

## 🔧 Configuration Options

### Adjust Stock Limits

Edit `daily_prediction_job.py`:

```python
MAX_STOCKS_PER_MARKET = 50  # Change to 100 for more stocks
PREDICTION_DAYS = [1, 3, 7]  # Add 14, 30 for longer horizons
```

### Change Schedule Time

Edit `setup_scheduled_task.ps1`:

```powershell
$taskTime = "18:00"  # Change to "20:00" for 8 PM
```

### Add More Models

Edit `daily_prediction_job.py`:

```python
models = ['XGBoost', 'Random Forest', 'Gradient Boosting', 'LightGBM']
```

---

## 📝 Monitoring & Logs

### Check Job Logs

```powershell
# View last 20 lines of log
Get-Content prediction_job.log -Tail 20
```

### Check Database Records

```sql
-- See latest predictions
SELECT TOP 10 * 
FROM ai_prediction_history 
ORDER BY prediction_date DESC;

-- Check model performance
SELECT * FROM vw_model_performance_summary;

-- See pending vs completed
SELECT 
    CASE WHEN actual_price IS NULL THEN 'Pending' ELSE 'Completed' END as status,
    COUNT(*) as count
FROM ai_prediction_history
GROUP BY CASE WHEN actual_price IS NULL THEN 'Pending' ELSE 'Completed' END;
```

### Task Scheduler Status

```powershell
# Check if task is running
Get-ScheduledTask -TaskName "AI_Price_Prediction_Daily"

# View task history
Get-ScheduledTaskInfo -TaskName "AI_Price_Prediction_Daily"

# Run task manually
Start-ScheduledTask -TaskName "AI_Price_Prediction_Daily"
```

---

## 🎯 Expected Timeline

| Day | What Happens |
|-----|--------------|
| **Day 1** | Setup complete, first predictions generated (all pending) |
| **Day 2** | 1-day predictions from Day 1 get actual prices, new predictions generated |
| **Day 4** | 3-day predictions from Day 1 complete, start seeing accuracy metrics |
| **Day 8** | 7-day predictions from Day 1 complete, full backtesting data available |
| **Week 2+** | Trends emerge showing which models perform best |

---

## ⚠️ Troubleshooting

### "Table does not exist" error
```powershell
# Re-run the SQL script
sqlcmd -S localhost\MSSQLSERVER01 -d stockdata_db -i create_prediction_history_table.sql
```

### Task doesn't run
- Check Task Scheduler → "AI_Price_Prediction_Daily" → Last Run Result
- Ensure computer is on at 6 PM
- Check `prediction_job.log` for errors
- Run batch file manually to test: `.\run_daily_predictions.bat`

### No predictions showing in dashboard
- Wait for predictions to be generated (run job manually)
- Verify data in database: `SELECT COUNT(*) FROM ai_prediction_history`
- Check if selected stock has predictions in that market

### Python package errors
```powershell
# Install required packages
pip install xgboost lightgbm scikit-learn pandas numpy pyodbc
```

---

## 📈 Best Practices

1. **Let it run for at least 2 weeks** before making decisions based on accuracy
2. **Monitor the log file** weekly to ensure job is running
3. **Review model performance** monthly to see if patterns emerge
4. **Adjust stock limits** if job takes too long (reduce MAX_STOCKS_PER_MARKET)
5. **Keep historical data** - don't delete old predictions, they show long-term accuracy

---

## 🚀 Next Steps

After setup is complete:

1. **Day 1-7:** Let system collect data
2. **Week 2:** Review initial accuracy metrics
3. **Week 3:** Compare model performance across different stocks
4. **Week 4:** Identify best-performing models for each market
5. **Month 2+:** Use historical accuracy to weight model predictions

---

## 📞 Support

If you encounter issues:

1. Check `prediction_job.log` for error messages
2. Verify database connection works
3. Ensure all Python packages are installed
4. Run job manually to see real-time errors
5. Check SQL Server is running

---

## 🎉 Success Indicators

You'll know it's working when:

✅ Task runs daily without errors (check Task Scheduler)  
✅ Log file shows successful completions  
✅ Database has growing number of predictions  
✅ Dashboard shows prediction accuracy data  
✅ Completed predictions show actual vs predicted prices  
✅ Model performance metrics update daily  

**Congratulations! Your AI Prediction Backtesting system is now operational! 🎊**
