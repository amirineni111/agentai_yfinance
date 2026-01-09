# 📑 Multi-Tab Usage Guide

## How to Open Different Pages in Multiple Browser Tabs

Your Streamlit dashboard now supports opening multiple pages in separate browser tabs!

### ✅ Method 1: Use the Sidebar Quick Links (Recommended)

1. Look in the **sidebar** for **"🔗 Open in New Tab"** section
2. **Right-click** on any link (e.g., "📝 Stock Notes & Journal")
3. Select **"Open link in new tab"**
4. The page will open independently in a new tab!

### ✅ Method 2: Manual URL Navigation

You can directly type or bookmark these URLs:

#### **Stock Notes & Journal**
```
http://localhost:8501/?page=Stock_Notes_Journal
```

#### **Technical Analysis**
```
http://localhost:8501/?page=Technical_Analysis
```

#### **AI Price Predictions**
```
http://localhost:8501/?page=AI_Price_Predictions
```

#### **My Portfolio Tracker**
```
http://localhost:8501/?page=My_Portfolio_Tracker
```

#### **AI Trading Signals Scanner**
```
http://localhost:8501/?page=AI_Trading_Signals_Scanner
```

#### **Flight Status Dashboard**
```
http://localhost:8501/?page=Flight_Status_Dashboard
```

#### **Data in Table Format**
```
http://localhost:8501/?page=Data_Table_format
```

### ✅ Method 3: Duplicate Current Tab

1. With the Streamlit app open, press **Ctrl+Shift+T** (or **Cmd+Shift+T** on Mac)
2. Or right-click the tab and select **"Duplicate"**
3. Use the navigation in each tab independently

## 🎯 Use Cases

### **Scenario 1: Compare Two Stocks**
- **Tab 1**: Technical Analysis for AAPL (NASDAQ)
- **Tab 2**: Technical Analysis for RELIANCE (NSE)
- Switch between tabs to compare charts

### **Scenario 2: Analysis + Notes**
- **Tab 1**: Technical Analysis for a stock
- **Tab 2**: Stock Notes & Journal
- Add notes while keeping the analysis visible

### **Scenario 3: Multi-Market Monitoring**
- **Tab 1**: AI Trading Signals (NASDAQ 100)
- **Tab 2**: AI Trading Signals (NSE 500)
- **Tab 3**: Forex ML Predictions
- Monitor all markets simultaneously

### **Scenario 4: Portfolio + Analysis**
- **Tab 1**: My Portfolio Tracker
- **Tab 2**: Technical Analysis for a holding
- **Tab 3**: Stock Notes for the holding
- Complete workflow in separate tabs

## ⚠️ Important Notes

1. **Session State**: Some filters/selections may be shared across tabs (stored in session)
2. **Database**: All tabs connect to the same database - changes are reflected everywhere
3. **Performance**: Having many tabs open may slow down the browser
4. **Recommended**: Keep 2-4 tabs open at a time for best performance

## 💡 Pro Tips

1. **Bookmark Frequently Used Pages**: Save URLs with `?page=` parameter
2. **Pin Important Tabs**: Right-click tab → "Pin tab" to keep it always visible
3. **Use Multiple Windows**: Drag tabs to create separate windows for multi-monitor setups
4. **Keyboard Shortcuts**:
   - `Ctrl+1` through `Ctrl+9`: Switch between first 9 tabs
   - `Ctrl+Tab`: Next tab
   - `Ctrl+Shift+Tab`: Previous tab
   - `Ctrl+W`: Close current tab

## 🔧 For Remote Access

If accessing from another machine on your network, replace `localhost` with the server IP:

```
http://192.168.87.27:8501/?page=Stock_Notes_Journal
```

## 📝 Example Workflow

**Morning Routine:**

1. Open **Home page** - Select stocks to watch
2. Right-click **"Technical Analysis"** link → Open in new tab
3. Right-click **"Stock Notes & Journal"** link → Open in new tab
4. Right-click **"AI Trading Signals"** link → Open in new tab

Now you have:
- **Tab 1**: Filter and select stocks
- **Tab 2**: Detailed technical charts
- **Tab 3**: Trading journal for notes
- **Tab 4**: AI signals scanner for all markets

Switch between tabs as needed throughout the day!

---

**Enjoy your multi-tab trading dashboard!** 🚀
