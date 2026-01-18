# WATCHLIST MANAGEMENT GUIDE

## 📊 Database Watchlist System

Your prediction watchlist is now stored in the `prediction_watchlist` table, making it easy to manage without editing Python code.

---

## ✅ Quick Start

### View Your Current Watchlist
```powershell
python manage_watchlist.py summary
```

### View Full Details
```powershell
python manage_watchlist.py view
```

---

## 🔧 Managing Tickers

### Add a New Ticker
```powershell
# Syntax: python manage_watchlist.py add 'MARKET' 'TICKER' 'COMPANY_NAME' PRIORITY
python manage_watchlist.py add 'NSE 500' 'ADANIPORTS.NS' 'Adani Ports' 1
python manage_watchlist.py add 'NASDAQ 100' 'CRM' 'Salesforce' 1
python manage_watchlist.py add 'Forex' 'USDCAD' 'US Dollar / Canadian Dollar' 2
```

**Markets:** `NSE 500`, `NASDAQ 100`, `Forex`  
**Priority:** 1 = High, 2 = Medium, 3 = Low (affects processing order)

### Remove a Ticker
```powershell
python manage_watchlist.py remove 'TICKER'
python manage_watchlist.py remove 'ADANIPORTS.NS'
```

### Temporarily Disable a Ticker
```powershell
python manage_watchlist.py disable 'TICKER'
python manage_watchlist.py disable 'AAPL'
```

### Re-enable a Ticker
```powershell
python manage_watchlist.py enable 'TICKER'
python manage_watchlist.py enable 'AAPL'
```

---

## 💾 Direct SQL Management

### View Active Watchlist
```sql
SELECT market, ticker, company_name, priority 
FROM vw_active_watchlist;
```

### Add Multiple Tickers
```sql
INSERT INTO prediction_watchlist (market, ticker, company_name, priority)
VALUES 
    ('NSE 500', 'ADANIPORTS.NS', 'Adani Ports', 1),
    ('NSE 500', 'BAJFINANCE.NS', 'Bajaj Finance', 1),
    ('NSE 500', 'ONGC.NS', 'Oil & Natural Gas Corp', 2);
```

### Bulk Update Priority
```sql
UPDATE prediction_watchlist 
SET priority = 2 
WHERE ticker IN ('WIPRO.NS', 'HCLTECH.NS');
```

### Disable All Forex Pairs
```sql
UPDATE prediction_watchlist 
SET is_active = 0 
WHERE market = 'Forex';
```

### Export to CSV
```powershell
sqlcmd -S localhost\MSSQLSERVER01 -d stockdata_db -Q "SELECT * FROM vw_active_watchlist" -o watchlist.csv -s"," -W
```

---

## 🚀 Running Predictions

### Manual Run
```powershell
python daily_prediction_job.py
```

### Check Results
```powershell
sqlcmd -S localhost\MSSQLSERVER01 -d stockdata_db -Q "SELECT market, COUNT(*) as count FROM ai_prediction_history WHERE prediction_date = CAST(GETDATE() AS DATE) GROUP BY market"
```

---

## 📈 Current Watchlist (Default)

### NSE 500 (20 stocks)
RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, HINDUNILVR.NS, ICICIBANK.NS, SBIN.NS, BHARTIARTL.NS, ITC.NS, KOTAKBANK.NS, LT.NS, AXISBANK.NS, ASIANPAINT.NS, MARUTI.NS, HCLTECH.NS, WIPRO.NS, TITAN.NS, SUNPHARMA.NS, ULTRACEMCO.NS, NESTLEIND.NS

### NASDAQ 100 (30 stocks)
AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, AVGO, COST, NFLX, ADBE, PEP, CSCO, AMD, INTC, CMCSA, TXN, QCOM, INTU, AMAT, HON, AMGN, SBUX, GILD, ADP, BKNG, MDLZ, ISRG, ADI, VRTX

### Forex (8 pairs)
AUDUSD, EURUSD, GBPUSD, USDJPY, EURCHF, EURJPY, NZDUSD, USDHKD

**Total: 58 active tickers**

---

## ⚙️ Configuration

### Toggle Watchlist Mode
Edit [daily_prediction_job.py](daily_prediction_job.py#L76):
```python
USE_WATCHLIST = True   # Use database watchlist
USE_WATCHLIST = False  # Use top 50 by volume (fallback)
```

### Database Table Structure
```sql
prediction_watchlist:
  - watchlist_id (PK)
  - market (NSE 500 / NASDAQ 100 / Forex)
  - ticker
  - company_name
  - is_active (1=Yes, 0=No)
  - priority (1=High, 2=Medium, 3=Low)
  - notes (optional)
  - added_date, updated_date
```

---

## 🎯 Best Practices

1. **Start Small:** Test with 5-10 tickers before scaling up
2. **Use Priorities:** Set priority=1 for most important stocks
3. **Monitor Data:** Check for "Insufficient data" warnings
4. **Regular Review:** Update watchlist based on market conditions
5. **Backup:** Export watchlist before major changes

---

## 🔍 Troubleshooting

### No Predictions Generated?
```sql
-- Check active tickers
SELECT market, COUNT(*) FROM prediction_watchlist WHERE is_active = 1 GROUP BY market;
```

### Ticker Not in Database?
Some tickers may lack historical data. Check:
```sql
SELECT COUNT(*) FROM nse_500_hist_data WHERE ticker = 'YOURticker.NS';
```

### Re-import Default Watchlist
```powershell
sqlcmd -S localhost\MSSQLSERVER01 -d stockdata_db -i create_watchlist_table.sql
```

---

## 📞 Support

- View logs: `prediction_job.log`
- Check errors: `python daily_prediction_job.py 2>&1 | Select-String "ERROR"`
- Database: `localhost\MSSQLSERVER01\stockdata_db`

---

*Last Updated: 2026-01-17*
