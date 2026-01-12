@echo off
echo Starting Backend Server...
cd backend
uvicorn main:app --reload --port 8000
pause
