@echo off
title DataCo - Setup Check
cd /d "%~dp0"

".venv\Scripts\python.exe" check_setup.py

echo.
pause
