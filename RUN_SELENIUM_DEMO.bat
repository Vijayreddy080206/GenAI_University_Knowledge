@echo off
setlocal
cd /d "%~dp0"
title NIIT University Knowledge Assistant - Automated Selenium Faculty Demo

echo ======================================================================
echo NIIT University Generative AI Knowledge Assistant
echo Real Visible Chrome Automation - Faculty Live Demo
echo ======================================================================
echo.
echo [1/3] Setting execution mode: HEADLESS=false (Visible Chrome with Pacing)...
set HEADLESS=false
set APP_URL=https://localhost

echo.
echo [2/3] Executing Selenium End-to-End User Journeys...
pytest tests/selenium/test_e2e_ui.py -v --html=reports/selenium_report.html --self-contained-html

echo.
echo [3/3] Opening Visual Execution Report & Captured Screenshots...
if exist "reports\selenium_report.html" (
    start "" "reports\selenium_report.html"
) else (
    echo Report not generated. Please check pytest console output above.
)

echo.
echo Demo finished. Press any key to exit.
pause >nul
