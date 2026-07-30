@echo off
title Move new files into the project
cd /d "%~dp0"

rem  Looks in .\files first, then in Downloads, and takes whichever
rem  copy is newest. Handles names like "db (1).py" too.
set "SRC1=%~dp0files"
set "SRC2=%USERPROFILE%\Downloads"

echo.
echo   ========================================
echo    Moving new files into place
echo   ========================================
echo.
echo   Looking in:
echo     %SRC1%
echo     %SRC2%
echo.

if not exist "assets" mkdir "assets"
if not exist "pages"  mkdir "pages"

call :one "theme*.py"            "theme.py"
call :one "db*.py"               "db.py"
call :one "geo*.py"              "geo.py"
call :one "app_new*.py"          "app.py"
call :one "wsgi*.py"             "wsgi.py"
call :one "build_db*.py"         "build_db.py"
call :one "style*.css"           "assets\style.css"
call :one "globe*.js"            "assets\globe.js"
call :one "pages_home*.py"       "pages\home.py"
call :one "pages_executive*.py"  "pages\executive.py"
call :one "pages_network*.py"    "pages\network.py"
call :one "pages_map*.py"        "pages\map.py"
call :one "pages_risk*.py"       "pages\risk.py"
call :one "pages_trends*.py"     "pages\trends.py"
call :one "pages_quality*.py"    "pages\quality.py"

echo.
echo   Clearing python caches...
if exist "__pycache__"       rmdir /s /q "__pycache__"
if exist "pages\__pycache__" rmdir /s /q "pages\__pycache__"

echo.
echo   ----------------------------------------
echo    Done. Now run START.bat
echo   ----------------------------------------
echo.
pause
exit /b


:one
rem  %~1 = filename pattern, %~2 = destination inside the project
set "BEST="
set "BESTDIR="

for %%D in ("%SRC1%" "%SRC2%") do (
    if exist "%%~D" (
        for /f "delims=" %%F in ('dir /b /a-d /o-d "%%~D\%~1" 2^>nul') do (
            if not defined BEST (
                set "BEST=%%F"
                set "BESTDIR=%%~D"
            )
        )
    )
)

if not defined BEST (
    echo     skip    %~2
    exit /b
)

copy /y "%BESTDIR%\%BEST%" "%~2" >nul
if errorlevel 1 (
    echo     FAIL    %~2
) else (
    echo     ok      %~2
)
exit /b
