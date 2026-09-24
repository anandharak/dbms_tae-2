@echo off
echo ==============================================================================
echo Launching Futures ^& Options Trading, Volatility ^& Settlement DBMS System
echo ==============================================================================
cd /d "%~dp0"
python -m streamlit run app.py --server.port 8501 --server.headless false
pause
