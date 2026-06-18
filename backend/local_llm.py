"""
Embedded local LLM engine (no Ollama required).

Runs GGUF chat models in-process via llama-cpp-python. Drop a .gguf chat model
into  models/llm/  (or any configured models dir) and enable it in Settings.

Optional — if llama-cpp-python isn't installed or no model is chosen, the
functions return a friendly message instead of crashing.
"""
from __future__ import annotations

import threading
from pathlib import Path

from config import MODELS_DIR, config

_LLM = None
_LLM_PATH = None
_LOCK = threading.Lock()


def available() -> bool:
    try:
        import llama_cpp  # noqa: F401
        return True
    except Exception:
        return False


def _llm_dirs() -> list[Path]:
    dirs = [MODELS_DIR / "llm"]
    custom = (config.get("custom_models_dir") or "").strip()
    if custom:
        dirs.append(Path(custom) / "llm")
    return dirs


def list_models() -> list[dict]:
    seen, out = set(), []
    for d in _llm_dirs():
        try:
            if not d.exists():
                continue
            for f in d.rglob("*.gguf"):
                key = str(f.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append({"name": f.name, "path": str(f),
                            "size_gb": round(f.stat().st_size / 1e9, 2)})
        except Exception:
            continue
    return sorted(out, key=lambda m: m["name"].lower())


def _resolve_model_path() -> str | None:
    p = (config.get("local_gguf_path") or "").strip()
    if p and Path(p).exists():
        return p
    models = list_models()
    return models[0]["path"] if models else None


def _get_llm(model_path: str):
    global _LLM, _LLM_PATH
    with _LOCK:
        if _LLM is not None and _LLM_PATH == model_path:
            return _LLM
        from llama_cpp import Llama
        _LLM = Llama(model_path=model_path, n_ctx=4096, n_gpu_layers=-1, verbose=False)
        _LLM_PATH = model_path
        return _LLM


def _build(messages: list, system: str | None) -> list:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs += messages
    return msgs


def chat(messages: list, system: str | None = None) -> str:
    if not available():
        return ("The built-in local engine isn't installed yet. Run install.bat (it adds "
                "llama-cpp-python), or use Ollama instead.")
    model_path = _resolve_model_path()
    if not model_path:
        return ("No local GGUF chat model found. Drop a .gguf into models/llm/ and pick it in "
                "Settings → AI Engine.")
    try:
        llm = _get_llm(model_path)
        out = llm.create_chat_completion(messages=_build(messages, system), temperature=0.7)
        return out["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Local engine error: {e}"


def stream(messages: list, system: str | None = None):
    if not available():
        yield ("The built-in local engine isn't installed yet. Run install.bat (it adds "
               "llama-cpp-python), or use Ollama instead.")
        return
    model_path = _resolve_model_path()
    if not model_path:
        yield ("No local GGUF chat model found. Drop a .gguf into models/llm/ and pick it in "
               "Settings → AI Engine.")
        return
    try:
        llm = _get_llm(model_path)
        for chunk in llm.create_chat_completion(messages=_build(messages, system),
                                                temperature=0.7, stream=True):
            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if delta:
                yield delta
    except Exception as e:
        yield f"Local engine error: {e}"
