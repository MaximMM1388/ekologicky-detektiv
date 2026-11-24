@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo Spustam Ekologickeho detektiva...
echo.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 server.py
) else (
    python server.py
)
echo.
echo Ak sa aplikacia nespustila, nainstaluj Python 3 z python.org.
pause
