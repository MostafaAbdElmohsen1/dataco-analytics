@echo off
title Push to GitHub
cd /d "%~dp0"

echo.
echo   ========================================
echo    Pushing changes to GitHub
echo   ========================================
echo.

git add .

rem  Use the message you type, or a default one.
set /p MSG="  Commit message (press Enter for 'update'): "
if "%MSG%"=="" set MSG=update

git commit -m "%MSG%"
git push

echo.
echo   ----------------------------------------
echo    Done. Now update the live site:
echo.
echo    1) Open a Bash console on PythonAnywhere
echo    2) Paste this one line:
echo.
echo       cd ~/dataco-analytics ^&^& git pull ^&^& touch /var/www/mostafaabdelmohsen1_pythonanywhere_com_wsgi.py
echo.
echo   ----------------------------------------
echo.
pause
