@echo off
echo 🎯 RECOMMENDED APPROACH - Use Integrated Flight Status Dashboard
echo ================================================================
echo.
echo ✅ Your Flight Status Dashboard is ALREADY INTEGRATED in your main app!
echo.
echo 🚀 To use it:
echo 1. Run: streamlit run streamlitapp_20251123_v2.py
echo 2. Open: http://localhost:8501
echo 3. In sidebar, select: "🛩️ Flight Status Dashboard"
echo.
echo 📋 The integrated version has:
echo - All your database connections working
echo - Proper error handling  
echo - Navigation between pages
echo - All features integrated
echo.
pause
echo.
echo 🚀 Starting your main app with integrated Flight Status Dashboard...
cd /d "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"
streamlit run streamlitapp_20251123_v2.py --server.port=8501
