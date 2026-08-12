@echo off
title DataCo - Agent Test
cd /d "%~dp0"

echo.
echo   ========================================
echo    Ask the Data - Agent Test
echo   ========================================
echo.
echo   This runs 4 messy, real-world questions
echo   against the agent and saves the result to:
echo.
echo       test_results.txt
echo.
echo   It takes about 2 minutes (it waits 20s
echo   between questions to respect the free
echo   Groq rate limit). Please do not close
echo   this window while it runs.
echo.
echo   ----------------------------------------
echo.

rem  Run the test. Change 4 to 2 for a lighter run,
rem  or to "all" to run every question.
".venv\Scripts\python.exe" test_agent_live.py 4

echo.
echo   ========================================
echo    Done. Open test_results.txt in this
echo    folder and send it to Claude.
echo   ========================================
echo.
pause
