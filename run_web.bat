@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python -m uvicorn web_app:app --reload
pause
