@echo off
setlocal
cd /d %~dp0
title Resume Tailor

where git >nul 2>&1
if errorlevel 1 (
    echo Git is not installed or not on PATH. Install it from git-scm.com, then
    echo double-click this file again.
    pause
    exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not on PATH. Install it from python.org
    echo ^(check "Add python.exe to PATH" during install^), then double-click
    echo this file again.
    pause
    exit /b 1
)

echo Checking for updates...
git pull https://github.com/vk86294140-cloud/promptpress resume-tailor-staging >nul 2>&1
git push origin main >nul 2>&1

if not exist ".venv\Scripts\python.exe" (
    echo First-time setup - installing, this takes about a minute...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -q -r requirements.txt openai python-dotenv
) else (
    call .venv\Scripts\activate.bat
    pip install -q -r requirements.txt openai python-dotenv >nul 2>&1
)

if not exist ".env" (
    echo.
    echo ============================================================
    echo   First run: no .env file yet.
    echo   Notepad will open a template - add at least ONE key (a
    echo   free one is fine: NVIDIA_API_KEY, GROQ_API_KEY, or
    echo   GEMINI_API_KEY^), then Save and close Notepad to continue.
    echo ============================================================
    echo.
    copy .env.example .env >nul
    notepad .env
)

echo.
echo Keep this window open while you use the app. Close it (or Ctrl+C) to stop.
echo.
python run.py
pause
