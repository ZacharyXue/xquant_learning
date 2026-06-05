@echo off
chcp 65001 >nul
echo ========================================
echo   xtquant Real Trade - Test Trade 520990.SH
echo ========================================
echo.
echo [1] Checking xtquant import...
F:\Codes\xtquant_learning\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,r'D:\国金证券QMT交易端\bin.x64\Lib\site-packages'); from xtquant.xttrader import XtQuantTrader; from xtquant.xttype import StockAccount; print('   OK - xtquant importable')" 2>&1
if %errorlevel% neq 0 (
    echo   FAILED - xtquant not importable
    pause
    exit /b 1
)
echo.
echo [2] Starting trade...
echo.
F:\Codes\xtquant_learning\.venv\Scripts\python.exe F:\Codes\xtquant_learning\scripts\run_real.py --strategy test_trade 2>&1
echo.
echo [3] Trade script ended.
echo.
echo ========================================
echo   Check result: python scripts/show_trades.py --today
echo ========================================
pause
