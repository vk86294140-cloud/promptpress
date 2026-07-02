"""Robust launcher: start the server, open the browser only once it's actually
reachable. Used by start.bat / start.sh; `python run.py` works anywhere.
"""

import socket
import threading
import time
import webbrowser

HOST, PORT = "127.0.0.1", 8080
URL = f"http://localhost:{PORT}"


def _listening() -> bool:
    try:
        socket.create_connection((HOST, PORT), timeout=0.5).close()
        return True
    except OSError:
        return False


def _open_browser_when_ready():
    for _ in range(240):  # up to 2 minutes (first run installs can be slow)
        if _listening():
            webbrowser.open(URL)
            return
        time.sleep(0.5)


def main():
    if _listening():
        print(f"Resume Tailor is already running — opening {URL}")
        print("(Close the other Resume Tailor window first if you meant to restart it.)")
        webbrowser.open(URL)
        return

    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    print(f"Starting Resume Tailor — your browser will open {URL} when it's ready...")

    import uvicorn
    uvicorn.run("app:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
