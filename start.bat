@echo off
cd /d "C:\google ads ai agents 111"
call venv\Scripts\activate
uvicorn app:app --port 8000
