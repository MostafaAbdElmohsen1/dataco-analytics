@echo off
setlocal
title DataCo - Setup
cd /d "%~dp0"

echo.
echo   ========================================
echo    DataCo Ask the Data - Setup
echo   ========================================
echo.
echo   This does everything in one go:
echo     1. installs the openai library
echo     2. asks for your Gemini API key
echo     3. writes the .env file for you
echo     4. checks that everything works
echo.
echo   ----------------------------------------
echo.

echo   [1/4] Installing the openai library...
echo.
".venv\Scripts\python.exe" -m pip install --quiet --upgrade openai
if errorlevel 1 (
    echo.
    echo   [!!] pip install failed. Screenshot this and send it to Claude.
    echo.
    pause
    exit /b 1
)
echo   Done.
echo.

echo   ----------------------------------------
echo.
echo   [2/4] Your Gemini API key
echo.
echo   Get one at:  https://aistudio.google.com/apikey
echo   Click the copy icon next to a key, then RIGHT-CLICK
echo   in this window to paste it, and press Enter.
echo.
echo   Nothing you type here leaves your computer.
echo.

set "GKEY="
set /p "GKEY=API key: "

if "%GKEY%"=="" (
    echo.
    echo   [!!] You did not paste anything. Run SETUP.bat again.
    echo.
    pause
    exit /b 1
)

echo.
echo   [3/4] Writing .env ...
(
echo GEMINI_API_KEY=%GKEY%
echo GEMINI_MODEL=gemini-3.5-flash-lite
)>.env

if not exist ".env" (
    echo   [!!] Could not create .env. Screenshot this and send it to Claude.
    echo.
    pause
    exit /b 1
)
echo   Done. .env created.
echo.

echo   ----------------------------------------
echo.
echo   [4/4] Checking everything...
echo.
".venv\Scripts\python.exe" check_setup.py

echo.
pause
