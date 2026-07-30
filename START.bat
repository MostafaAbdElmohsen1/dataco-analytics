@echo off
title DataCo Analytics
cd /d "%~dp0"

echo.
echo   ========================================
echo    DataCo Supply Chain Analytics
echo   ========================================
echo.
echo   Starting the server...
echo   Your browser will open in a few seconds.
echo.
echo   To stop the site: close this window,
echo   or press Ctrl + C
echo.

rem  Open the browser after a short delay, in the background.
rem  If you set up the hosts file, change the address below to:
rem      http://dataco.local:8050
start /b "" cmd /c "timeout /t 5 >nul && start """" http://127.0.0.1:8050"

rem  Start the app. This window stays open while the site is running.
".venv\Scripts\python.exe" app.py

echo.
echo   The server has stopped.
pause
