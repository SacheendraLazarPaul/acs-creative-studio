"""
Shared state, paths, config, and chat history.
All other modules import from here — no local imports in this file.
"""
import json, os
from pathlib import Path
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).resolve().parent
MODELS_DIR   = BASE_DIR / "models"
OUTPUT_DIR   = BASE_DIR / "outputs"
PLUGINS_DIR  = BASE_DIR / "plugins"
STATIC_DIR   = BASE_DIR / "static"
CONFIG_FILE  = BASE_DIR / "config.json"
HISTORY_FILE = BASE_DIR / "chat_history.json"
OLLAMA_URL   = "http://localhost:11434"

os.chdir(BASE_DIR)

for _d in [
    OUTPUT_DIR, PLUGINS_DIR,
    MODELS_DIR / "checkpoints", MODELS_DIR / "loras",
    MODELS_DIR / "vae",         MODELS_DIR / "controlnet",
    MODELS_DIR / "ipadapter",   MODELS_DIR / "upscale_models",
    MODELS_DIR / "video",       MODELS_DIR / "embeddings",
    MODELS_DIR / "hypernetworks", MODELS_DIR / "clip",
]:
    _d.mkdir(parents=True, exist_ok=True)


# ── Config ─────────────────────────────────────────────────────────────────
def load_config() -> dict:
    default = {
        "hf_token": "", "first_run_done": False,
        "downloaded_models": [], "default_checkpoint": "",
        "ollama_text_model":  "llama3",
        "ollama_vision_model": "moondream",
        "custom_models_dir": "",
        "comfyui_dir": "",          # optional external models folder to scan
        "extra_scan_dirs": [],
        "civitai_token": "",
        # Embedded local LLM engine (chat without Ollama)
        "use_local_engine": False,
        "local_gguf_path": "",
    }
    if CONFIG_FILE.exists():
        try:
            default.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return default

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

config = load_config()


# ── Chat history ───────────────────────────────────────────────────────────
def load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sessions": {}, "order": []}

def save_history(h: dict):
    HISTORY_FILE.write_text(json.dumps(h, indent=2), encoding="utf-8")

chat_history = load_history()


# ── Runtime state (mutable, shared across modules) ─────────────────────────
state: dict = {
    "preferences":      {},
    "gen_status":       "idle",
    "gen_progress":     0,
    "gen_log":          "",
    "download_status":  {},
    "download_threads": {},
}


# ── Live PC context (injected into every system prompt) ───────────────────
def get_live_context() -> str:
    now = datetime.now()
    cpu_pct = ram_info = gpu_info = "?"
    try:
        import psutil
        cpu_pct  = f"{psutil.cpu_percent():.0f}%"
        vm       = psutil.virtual_memory()
        ram_info = f"{vm.used/1e9:.1f}GB/{vm.total/1e9:.1f}GB"
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            name     = torch.cuda.get_device_name(0)
            free     = round(torch.cuda.mem_get_info(0)[0] / 1e9, 1)
            total    = round(torch.cuda.mem_get_info(0)[1] / 1e9, 1)
            gpu_info = f"{name} {free}GB free/{total}GB"
    except Exception:
        pass
    return (
        f"=== LIVE PC INFO ===\n"
        f"Date: {now.strftime('%A, %B %d, %Y')} | Time: {now.strftime('%I:%M %p')} IST\n"
        f"CPU: {cpu_pct} | RAM: {ram_info} | GPU: {gpu_info}\n"
        f"===================\n"
    )
