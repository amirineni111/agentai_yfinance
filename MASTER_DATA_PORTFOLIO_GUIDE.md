# Master Data Editor & Portfolio Tracker - User Guide

## 📊 Master Data Editor

### Overview
Edit and manage master data for NSE 500, NASDAQ 100, and Forex markets directly from the dashboard.

### Features
- **Multi-Market Support**: Switch between NSE 500, NASDAQ 100, and Forex markets
- **Inline Editing**: Edit records directly in the table
- **Add/Delete Rows**: Dynamic row management
- **Bulk Save**: Save all changes with one click
- **Data Statistics**: View record counts and monitoring status

### How to Use

#### 1. Access the Editor
- Navigate to **"📊 Master Data Editor"** from the sidebar
- Select the market you want to edit (NSE 500 / NASDAQ 100 / Forex)

#### 2. Edit Data
- Click on any cell to edit values
- Add new rows using the "+" button
- Delete rows using the "-" button
- Modify ticker symbols, recommendation dates, and tracking parameters

#### 3. Save Changes
- Click **"💾 Save Changes"** to update the database
- All changes are saved in a single transaction
- Use **"🔄 Refresh Data"** to reload from database

#### 4. View Statistics
- **Total Records**: Number of tickers in the table
- **Monitored Tickers**: Count of tickers with active monitoring
- **Unique Tickers**: Distinct ticker symbols

### Important Notes
- ⚠️ Saving replaces the entire table (backup recommended)
- Changes take effect immediately
- Ensure ticker symbols are correct before saving
- Monitor dates must be in valid date format

---

## 💼 My Portfolio Tracker

### Overview
Track your personal stock portfolio with buy/sell transactions across NSE, NASDAQ, and Forex markets.

### Features
- **Current Holdings**: View active positions with investment details
- **Transaction Management**: Add buy/sell transactions
- **Transaction History**: Complete audit trail
- **P&L Tracking**: Automatic profit/loss calculations
- **CSV Export**: Download portfolio history

### How to Use

#### 1. View Current Holdings (Tab 1)
- See all active holdings (status = HOLDING)
- View investment amount per position
- Track buy dates and quantities
- Read notes for each holding

**Metrics Displayed:**
- Buy Price
- Quantity
- Total Investment
- Buy Date

#### 2. Add New Transaction (Tab 2)

**For Buy-Only Transaction:**
1. Enter ticker symbol (e.g., AAPL, RELIANCE)
2. Select market (NSE / NASDAQ / Forex)
3. Set buy date, price, and quantity
4. Select "Buy Only" transaction type
5. Add optional notes
6. Click **"💾 Add Transaction"**

**For Buy & Sell Transaction:**
1. Follow steps 1-3 above
2. Select "Buy & Sell" transaction type
3. Enter sell date, price, and quantity
4. Add optional notes
5. Click **"💾 Add Transaction"**

**Required Fields:**
- Ticker Symbol*
- Market*
- Buy Date*
- Buy Price*
- Quantity*

#### 3. View Transaction History (Tab 3)

**Summary Metrics:**
- Total Transactions
- Active Holdings
- Closed Positions
- Total Investment

**Transaction Table:**
- ID, Ticker, Market
- Buy/Sell dates and prices
- Quantities and status
- Notes

**Export Options:**
- Download complete history as CSV
- Filename format: `portfolio_history_YYYYMMDD.csv`

### Database Structure

The portfolio tracker automatically creates the following table:

```sql
CREATE TABLE dbo.portfolio_tracker (
    id INT IDENTITY(1,1) PRIMARY KEY,
    ticker VARCHAR(50) NOT NULL,
    market VARCHAR(20) NOT NULL,
    buy_date DATE,
    buy_price FLOAT,
    buy_qty INT,
    sell_date DATE,
    sell_price FLOAT,
    sell_qty INT,
    status VARCHAR(20) DEFAULT 'HOLDING',
    notes VARCHAR(500)
)
```

### Transaction Status

- **HOLDING**: Active position (buy only, not yet sold)
- **SOLD**: Closed position (both buy and sell recorded)

### Tips & Best Practices

#### Master Data Editor
- ✅ Review changes before clicking "Save Changes"
- ✅ Keep ticker symbols consistent (use uppercase)
- ✅ Set monitoring dates only for actively tracked stocks
- ✅ Refresh data periodically to see latest updates

#### Portfolio Tracker
- ✅ Use consistent ticker symbols across markets
- ✅ Add notes to remember your investment thesis
- ✅ Record sell transactions to close positions
- ✅ Export history regularly for backup
- ✅ Monitor active holdings vs closed positions

### Example Workflows

#### Adding a New Stock to Monitor
1. Go to **Master Data Editor**
2. Select appropriate market
3. Add new row with ticker symbol
4. Set `monitor_startdate` to today
5. Save changes
6. Stock now appears in recommendation tracking

#### Recording a Complete Trade
1. Go to **Portfolio Tracker** → Add Transaction tab
2. Select "Buy & Sell" transaction type
3. Enter buy details (date, price, qty)
4. Enter sell details (date, price, qty)
5. Add notes (e.g., "Profit booking after 20% gain")
6. Submit → Status automatically set to SOLD

#### Tracking Open Positions
1. Go to **Portfolio Tracker** → Current Holdings tab
2. View all HOLDING positions
3. Check buy price and investment amount
4. Review notes for investment strategy
5. When ready to sell, add sell transaction

### Troubleshooting

**Master Data Editor:**
- If save fails, check database connection
- Ensure all required columns have values
- Verify date formats (YYYY-MM-DD)
- Check for duplicate ticker symbols

**Portfolio Tracker:**
- If table doesn't exist, it will be created automatically
- Ensure all required fields are filled (marked with *)
- Buy date should be before sell date
- Quantities must be positive integers

### Future Enhancements

**Planned Features:**
- 🔜 Current price integration from master data
- 🔜 Real-time P&L calculation
- 🔜 Portfolio performance charts
- 🔜 Sector-wise breakdown
- 🔜 Dividend tracking
- 🔜 Tax calculation support

---

## Navigation

**Access these features from the main dashboard sidebar:**
- 📊 Master Data Editor (13th page)
- 💼 My Portfolio Tracker (14th page)

**Related Pages:**
- 📊 Reco Tracking and Current Status (view monitoring performance)
- 📈 Today Trend Recommendations (see current signals)
- 🤖 AI Trading Signals Scanner (crossover-based signals)

---

## Technical Details

### Database Tables
- `dbo.NSE_500` - NSE 500 master data
- `dbo.NASDAQ_top100` - NASDAQ 100 master data
- `dbo.forex` - Forex pairs master data
- `dbo.portfolio_tracker` - Personal portfolio transactions

### Connection Requirements
- SQL Server with ODBC Driver 17
- Database credentials configured in session state
- TrustServerCertificate enabled

### Dependencies
- streamlit
- pandas
- pyodbc

---

**Version:** 1.0  
**Last Updated:** 2024-01-23  
**Dashboard File:** streamlitapp_20251123_v2.py
