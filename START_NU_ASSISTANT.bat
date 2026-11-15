@echo off
title NIIT University - GenAI Knowledge Assistant (Capstone Project II - Team-20)
echo ===============================================================================
echo   NIIT UNIVERSITY - GENERATIVE AI-BASED UNIVERSITY KNOWLEDGE ASSISTANT
echo   Capstone Project II - Team-20 (Supervised by Prof. Manish Hurkat)
echo   Team: Bharadwaj (BT23GCS244), Jithendar (BT23GCS425),
echo         Sai Deep (BT23GCS246), Vijay Vardhan Reddy (BT23GCS245)
echo ===============================================================================
echo.
cd /d "%~dp0backend"
echo [1/3] Verifying database schema (8 tables) and seeding NIIT University docs...
python -m app.seed
echo [2/3] Running automated SRS/SDD Requirement Verification Tests...
python -m unittest discover -s tests -p "test_*.py"
echo [3/3] Launching FastAPI + React Web Application on http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
