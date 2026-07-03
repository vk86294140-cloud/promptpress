"""Robust launcher: start the server, open the browser only once it's actually
reachable. If an OUTDATED server from an old window still owns the port (the
"zombie server" failure mode), kill and replace it automatically.
Used by start.bat / start.sh; `python run.py` works anywhere.
"""

import json
import platform
import re
import socket
import subprocess
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

HOST, PORT = "127.0.0.1", 8080
URL = f"http://localhost:{PORT}"


def _local_version() -> str:
    src = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION = "([^"]+)"', src)
    return m.group(1) if m else "?"


def _listening() -> bool:
    try:
        socket.create_connection((HOST, PORT), timeout=0.5).close()
        return True
    except OSError:
        return False


def _running_server_version():
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/api/status", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8")).get("version")
    except Exception:
        return None


def _kill_port_owner() -> bool:
    """Terminate whatever process is listening on our port. True on success."""
    try:
        if platform.system() == "Windows":
            out = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                                 capture_output=True, text=True).stdout
            pids = {line.split()[-1] for line in out.splitlines()
                    if f":{PORT}" in line and "LISTENING" in line.upper()}
            for pid in pids:
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        else:
            for cmd in (["lsof", "-ti", f"tcp:{PORT}"], ["fuser", f"{PORT}/tcp"]):
                try:
                    out = subprocess.run(cmd, capture_output=True, text=True).stdout
                except FileNotFoundError:
                    continue
                for pid in re.findall(r"\d+", out):
                    subprocess.run(["kill", "-9", pid], capture_output=True)
                if out.strip():
                    break
        for _ in range(10):
            if not _listening():
                return True
            time.sleep(0.5)
        return False
    except Exception:
        return False


def _open_browser_when_ready():
    for _ in range(240):  # up to 2 minutes (first run installs can be slow)
        if _listening():
            webbrowser.open(URL)
            return
        time.sleep(0.5)


def main():
    local = _local_version()
    if _listening():
        running = _running_server_version()
        if running == local:
            print(f"Resume Tailor v{local} is already running — opening {URL}")
            webbrowser.open(URL)
            return
        print(f"An OUTDATED Resume Tailor server (build {running or 'unknown'}) from an "
              f"old window is still holding port {PORT} — replacing it with v{local}...")
        if not _kill_port_owner():
            print()
            print("Could not stop it automatically. Close every other Resume Tailor /")
            print("PowerShell window, or run:  taskkill /F /IM python.exe")
            print("...then double-click start.bat again.")
            return
        print("Old server stopped.")

    # Loud, unambiguous startup banner: tell the user exactly which provider
    # was detected, so silent demo mode is impossible to miss.
    import app as app_module  # triggers .env load + provider detection
    provider = app_module.llm.detect_provider()
    model = app_module.llm.active_model()
    print()
    print("=" * 62)
    if provider == "demo":
        print("  WARNING: NO API KEY FOUND — running in DEMO mode.")
        print("  Tailoring will return a FAKE sample resume (Jane Doe).")
        print("  Fix: open the .env file in this folder and set ONE key,")
        print("  e.g.  NVIDIA_API_KEY=nvapi-your-real-key")
        print("  (no spaces around =, no quotes), then close this window")
        print("  and double-click start.bat again.")
    else:
        print(f"  Provider: {provider}   Model: {model}")
        print("  API key loaded — real tailoring is ON.")
    print(f"  Build: v{local}")
    print("=" * 62)
    print()

    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    print(f"Starting Resume Tailor v{local} — your browser will open {URL} when it's ready...")

    import uvicorn
    uvicorn.run("app:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
