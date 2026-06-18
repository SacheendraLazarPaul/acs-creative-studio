"""
ACS JARVIS — always-listening voice assistant.

Say "Hey Lisa" (or just "Lisa") followed by — or then speak — a command:
  "Hey Lisa, what time is it?"
  "Hey Lisa, open chrome"
  "Hey Lisa, generate an image of a sunset"
  "Hey Lisa, what's the weather in Mumbai?"
  ...anything else goes to the AI and she answers OUT LOUD.

Runs in the system tray. Replaces voice_launcher.py (which only opened the app).
"""
import os, re, sys, time, json, threading, subprocess, webbrowser, winsound
import urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path

import speech_recognition as sr
import pystray
from PIL import Image, ImageDraw

APP_DIR  = Path(__file__).parent
BACKEND  = APP_DIR / "backend" / "app.py"
APP_URL  = "http://localhost:7860"

# Wake words follow the AI's configured name (refreshed from the backend).
_AI_NAME   = "lisa"
WAKE_WORDS = ["hey lisa", "hi lisa", "lisa", "hey leesa", "elisa"]


def _refresh_wake_words():
    """Re-read the AI name from the backend; update wake words if renamed."""
    global _AI_NAME, WAKE_WORDS
    try:
        with urllib.request.urlopen(APP_URL + "/api/status", timeout=2) as r:
            name = json.loads(r.read()).get("ai_name", "Lisa").lower().strip()
        if name and name != _AI_NAME:
            _AI_NAME = name
            WAKE_WORDS = [f"hey {name}", f"hi {name}", name]
            print(f"[Jarvis] Wake word changed → '{name}'")
    except Exception:
        pass

_listener_on = True
_speaking    = threading.Event()
_recognizer  = sr.Recognizer()
_recognizer.energy_threshold         = 300
_recognizer.dynamic_energy_threshold = True
_recognizer.pause_threshold          = 0.7

_tts_lock = threading.Lock()


# ── Text-to-speech (offline, instant) ───────────────────────────────────────
def speak(text: str):
    """Speak text aloud with a female voice. Blocks until done."""
    text = re.sub(r"[*#`_\[\]()>|]", "", text)         # strip markdown
    text = re.sub(r"https?://\S+", "a link", text)      # don't read URLs
    text = text.strip()
    if not text:
        return
    if len(text) > 400:                                 # keep spoken replies short
        text = text[:400].rsplit(".", 1)[0] + "."
    with _tts_lock:
        _speaking.set()
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            gender = _get_ai_gender()
            for v in engine.getProperty("voices"):
                name = v.name.lower()
                if gender == "male" and any(m in name for m in ("david", "mark", "james", "male")):
                    engine.setProperty("voice", v.id); break
                if gender == "female" and any(f in name for f in ("zira", "susan", "hazel", "eva", "female")):
                    engine.setProperty("voice", v.id); break
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[Jarvis] TTS error: {e}")
        finally:
            _speaking.clear()


def _get_ai_gender() -> str:
    try:
        with urllib.request.urlopen(APP_URL + "/api/status", timeout=2) as r:
            return json.loads(r.read()).get("ai_gender", "female")
    except Exception:
        return "female"


def _beep(kind="ok"):
    try:
        if kind == "ok":
            winsound.Beep(880, 100); winsound.Beep(1100, 100)
        elif kind == "wake":
            winsound.Beep(1200, 120)
        elif kind == "err":
            winsound.Beep(300, 250)
    except Exception:
        pass


# ── Backend helpers ──────────────────────────────────────────────────────────
def _backend_running() -> bool:
    try:
        urllib.request.urlopen(APP_URL + "/api/status", timeout=1.5)
        return True
    except Exception:
        return False


def _start_backend():
    if _backend_running():
        return True
    subprocess.Popen(
        [sys.executable, str(BACKEND)], cwd=str(BACKEND.parent),
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        time.sleep(0.5)
        if _backend_running():
            return True
    return False


def ask_lisa(message: str) -> str:
    """Send a message to the ACS chat API and return the reply text."""
    if not _backend_running():
        if not _start_backend():
            return "Sorry, I couldn't start the backend."
    try:
        body = json.dumps({"message": message, "session_id": "jarvis-voice"}).encode()
        req = urllib.request.Request(
            APP_URL + "/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read()).get("response", "")
    except Exception as e:
        print(f"[Jarvis] chat error: {e}")
        return "Sorry, something went wrong talking to the AI."


# ── Built-in commands (instant, no AI round-trip) ───────────────────────────
_APP_ALIASES = {
    "chrome":     r"chrome.exe",
    "browser":    r"chrome.exe",
    "edge":       r"msedge.exe",
    "notepad":    r"notepad.exe",
    "calculator": r"calc.exe",
    "explorer":   r"explorer.exe",
    "files":      r"explorer.exe",
    "paint":      r"mspaint.exe",
    "settings":   r"ms-settings:",
    "spotify":    r"spotify.exe",
    "discord":    r"discord.exe",
    "steam":      r"steam.exe",
    "vs code":    r"code",
    "vscode":     r"code",
    "code":       r"code",
}


def _open_app(name: str) -> str:
    name = name.strip().lower()
    target = _APP_ALIASES.get(name)
    if target:
        try:
            if target.endswith(":"):
                os.startfile(target)
            else:
                subprocess.Popen(target, shell=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Opening {name}."
        except Exception:
            pass
    # Fallback: let Windows resolve it via start
    try:
        subprocess.Popen(f'start "" "{name}"', shell=True,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return f"Trying to open {name}."
    except Exception:
        return f"I couldn't open {name}."


def handle_command(text: str) -> str:
    """Handle built-ins locally; everything else goes to the AI."""
    t = text.lower().strip()

    # open the studio itself
    if any(p in t for p in ("open acs", "open studio", "launch studio", "open the app", "open yourself")):
        _start_backend()
        webbrowser.open(APP_URL)
        return "Opening the studio."

    # open <app>
    m = re.match(r"(?:open|launch|start)\s+(.+)", t)
    if m and len(m.group(1)) < 30:
        return _open_app(m.group(1))

    # time / date
    if re.search(r"\b(time|what time)\b", t) and len(t) < 30:
        return "It's " + datetime.now().strftime("%I:%M %p")
    if re.search(r"\b(date|day) (is it|today)\b", t) or t in ("what's the date", "what is the date"):
        return "Today is " + datetime.now().strftime("%A, %B %d")

    # search the web in browser
    m = re.match(r"(?:search|google|look up)\s+(?:for\s+)?(.+)", t)
    if m:
        q = m.group(1)
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(q))
        return f"Searching for {q}."

    # generate image → open the app on Generate page
    if re.search(r"\b(generate|create|make|draw)\b.*\b(image|picture|photo|art)\b", t):
        _start_backend()
        webbrowser.open(APP_URL + "/generate")
        # also let the AI craft the prompt
        reply = ask_lisa(text)
        return reply or "Opening the image generator."

    # shutdown / sleep guard — confirm via voice is unreliable, so refuse politely
    if re.search(r"\b(shut\s?down|restart|reboot|sleep)\b.*\b(pc|computer|laptop|system)\b", t):
        return "I don't do shutdowns by voice — too risky. You can do it from the Start menu."

    # everything else → AI chat, spoken aloud
    return ask_lisa(text)


# ── Listening loop ───────────────────────────────────────────────────────────
def _listen_once(mic, timeout=6, phrase_limit=10) -> str:
    with mic as source:
        audio = _recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
    return _recognizer.recognize_google(audio).lower()


def _strip_wake(text: str) -> str:
    """Remove the wake word from the start, return remaining command (may be '')."""
    for w in sorted(WAKE_WORDS, key=len, reverse=True):
        if w in text:
            after = text.split(w, 1)[1].strip(" ,.?!")
            return after
    return ""


def _listen_loop(icon):
    try:
        mic = sr.Microphone()
    except Exception as e:
        print(f"[Jarvis] No microphone: {e}")
        return

    with mic as source:
        _recognizer.adjust_for_ambient_noise(source, duration=1)
    _refresh_wake_words()
    print(f"[Jarvis] Listening… say 'Hey {_AI_NAME.title()}'")

    _loops = 0
    while _listener_on:
        if _speaking.is_set():        # don't listen to ourselves talk
            time.sleep(0.3)
            continue
        _loops += 1
        if _loops % 10 == 0:          # pick up renames every ~10 listen cycles
            _refresh_wake_words()
        try:
            heard = _listen_once(mic, timeout=5, phrase_limit=8)
            print(f"[Jarvis] Heard: {heard}")
            if not any(w in heard for w in WAKE_WORDS):
                continue

            command = _strip_wake(heard)
            if not command:
                # Wake word alone — beep and listen for the actual command
                _beep("wake")
                try:
                    command = _listen_once(mic, timeout=6, phrase_limit=12)
                    print(f"[Jarvis] Command: {command}")
                except Exception:
                    speak("Yes? I'm listening — say that again.")
                    continue

            icon.title = f"{_AI_NAME.title()}: working on '{command[:40]}'"
            reply = handle_command(command)
            print(f"[Jarvis] Reply: {reply[:120]}")
            speak(reply)
            icon.title = f"ACS Jarvis — say 'Hey {_AI_NAME.title()}'"

        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            print(f"[Jarvis] STT error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"[Jarvis] Error: {e}")
            time.sleep(2)


# ── Tray ─────────────────────────────────────────────────────────────────────
def _make_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, 63, 63], fill=(45, 31, 94))
    d.ellipse([14, 14, 49, 49], outline=(167, 139, 250), width=3)
    d.ellipse([26, 26, 37, 37], fill=(167, 139, 250))
    return img


def _build_tray():
    def on_open(icon, item):
        _start_backend()
        webbrowser.open(APP_URL)

    def on_quit(icon, item):
        global _listener_on
        _listener_on = False
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open ACS", on_open, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Jarvis", on_quit),
    )
    return pystray.Icon("ACS Jarvis", _make_icon(),
                        "ACS Jarvis — say 'Hey Lisa'", menu)


def main():
    icon = _build_tray()
    threading.Thread(target=_listen_loop, args=(icon,), daemon=True).start()
    _beep("ok")
    print("[Jarvis] Ready. Say 'Hey Lisa' + your command.")
    icon.run()


if __name__ == "__main__":
    main()
