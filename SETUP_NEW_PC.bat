@echo off
setlocal
title DataCo - Setup on a new PC
cd /d "%~dp0"

echo.
echo   ============================================
echo    DataCo Analytics - first-time setup
echo   ============================================
echo.
echo   Run this once on a new computer, inside the
echo   project folder (the one with app.py in it).
echo.
echo   --------------------------------------------
echo.

rem ---------------------------------------------- 1
echo   [1/6] Looking for Python...
where python >nul 2>&1
if errorlevel 1 goto :nopython
for /f "delims=" %%v in ('python --version') do echo         Found %%v
echo.

rem ---------------------------------------------- 2
echo   [2/6] Creating the .venv environment...
if exist ".venv\Scripts\python.exe" goto :venvok
python -m venv .venv
if errorlevel 1 goto :venvfail
echo         Done.
goto :venvdone
:venvok
echo         Already exists - skipping.
:venvdone
echo.

rem ---------------------------------------------- 3
echo   [3/6] Installing packages ^(takes a few minutes^)...
echo.
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :pipfail
echo         Done.
echo.

rem ---------------------------------------------- 4
rem  NOTE: the key prompt is deliberately NOT inside a ( ) block.
rem  Inside parentheses cmd expands %GKEY% at parse time, i.e. BEFORE
rem  set /p runs, so the value always reads as empty. That bug made an
rem  earlier version of this script say "nothing pasted" and quit even
rem  when the key had been pasted correctly.
echo   --------------------------------------------
echo.
echo   [4/6] Your Gemini API key
echo.
if exist ".env" goto :haveenv

echo   Get one free at:  https://aistudio.google.com/apikey
echo   RIGHT-CLICK in this window to paste, then press Enter.
echo   Nothing you type here leaves your computer.
echo.
set "GKEY="
set /p "GKEY=API key: "
if not defined GKEY goto :nokey

> .env echo GEMINI_API_KEY=%GKEY%
>> .env echo GEMINI_MODEL=gemini-3.5-flash-lite
echo.
echo         .env created.
goto :envdone

:haveenv
echo         .env already exists - keeping the key you already have.
echo         (Delete .env and run this again to change it.)

:envdone
echo.

rem ---------------------------------------------- 5
echo   [5/6] Rebuilding dataco.db from the CSV files...
echo.
".venv\Scripts\python.exe" build_db.py
if errorlevel 1 goto :dbfail
echo.

rem ---------------------------------------------- 6
echo   --------------------------------------------
echo   [6/6] Final check...
echo.
".venv\Scripts\python.exe" check_setup.py

echo.
echo   ============================================
echo    If everything above says OK, you are done.
echo    Double-click START.bat to open the site.
echo   ============================================
echo.
pause
exit /b 0


rem ================= error exits =================
:nopython
echo.
echo   [!!] Python is not installed, or not on PATH.
echo.
echo        Install it from  https://www.python.org/downloads/
echo        IMPORTANT: tick "Add python.exe to PATH" on the first
echo        screen of the installer, then run this again.
echo.
pause
exit /b 1

:venvfail
echo.
echo   [!!] Could not create .venv. Screenshot this and send it to Claude.
echo.
pause
exit /b 1

:pipfail
echo.
echo   [!!] Package install failed. Screenshot this and send it to Claude.
echo.
pause
exit /b 1

:nokey
echo.
echo   [!!] Nothing was pasted. Run SETUP_NEW_PC.bat again and use
echo        RIGHT-CLICK to paste (Ctrl+V does not work in this window).
echo.
pause
exit /b 1

:dbfail
echo.
echo   [!!] build_db.py failed. Screenshot this and send it to Claude.
echo.
pause
exit /b 1
