"""
ACS Desktop — native window app (no browser).
Starts the backend silently if needed, then opens the UI in its own window
like a real desktop application.

Run:  pythonw desktop.py   (or double-click ACS Desktop shortcut)
"""
import sys, time, subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
URL  = "http://localhost:7860"


def _backend_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(URL + "/api/status", timeout=2)
        return True
    except Exception:
        return False


def _start_backend():
    if _backend_running():
        return
    subprocess.Popen(
        [sys.executable, str(BASE / "backend" / "app.py")],
        cwd=str(BASE / "backend"),
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        if _backend_running():
            return
        time.sleep(0.5)


def main():
    _start_backend()
    try:
        import webview
    except ImportError:
        # pywebview not installed — fall back to browser so the app still opens
        import webbrowser
        webbrowser.open(URL)
        print("pywebview not installed — opened in browser instead.")
        print("Install with:  pip install pywebview")
        return
    webview.create_window(
        "ACS — AI Creative Studio", URL,
        width=1440, height=900, min_size=(1024, 700),
        background_color="#0d0d1a",
    )
    webview.start()


if __name__ == "__main__":
    main()
