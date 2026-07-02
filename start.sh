#!/usr/bin/env bash
# macOS/Linux equivalent of start.bat — double-click, or run: ./start.sh
set -e
cd "$(dirname "$0")"

command -v git >/dev/null || { echo "Install git first: git-scm.com"; exit 1; }
command -v python3 >/dev/null || { echo "Install Python 3 first: python.org"; exit 1; }

echo "Checking for updates..."
git pull https://github.com/vk86294140-cloud/promptpress resume-tailor-staging >/dev/null 2>&1 || true
git push origin main >/dev/null 2>&1 || true

if [ ! -f ".venv/bin/python" ]; then
    echo "First-time setup - installing, this takes about a minute..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -q -r requirements.txt openai python-dotenv
else
    source .venv/bin/activate
    pip install -q -r requirements.txt openai python-dotenv >/dev/null 2>&1
fi

if [ ! -f ".env" ]; then
    echo
    echo "============================================================"
    echo "  First run: no .env file yet."
    echo "  Opening a template - add at least ONE key (a free one is"
    echo "  fine: NVIDIA_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY),"
    echo "  then save and close the editor to continue."
    echo "============================================================"
    echo
    cp .env.example .env
    "${EDITOR:-nano}" .env
fi

( sleep 3; xdg-open http://localhost:8080 2>/dev/null || open http://localhost:8080 2>/dev/null || true ) &
echo
echo "Starting Resume Tailor at http://localhost:8080"
echo "Keep this window open while you use the app. Close it (or Ctrl+C) to stop."
echo
uvicorn app:app --port 8080
