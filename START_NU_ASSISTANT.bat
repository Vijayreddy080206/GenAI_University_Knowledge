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
echo [1/3] Initializing 8-Table SQLite Schema & Knowledge Base Document Vectors...
python -c "from app.seed import seed_all; seed_all(); print('Database & Vector Store initialized successfully.')"
echo.
echo [2/3] Executing Automated Requirement Verification Suite (18 Tests)...
python -m unittest discover -s tests -p "test_*.py" -v
echo.
echo [3/3] Launching FastAPI Web Application with Real Google OAuth & RAG Engine...
echo       Accessible at: http://127.0.0.1:8000
echo.
start "" "http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
