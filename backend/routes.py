"""
All FastAPI route handlers.
Import this router in app.py and include it: app.include_router(router).
"""
import json, re, sys, time, threading, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import config, state, chat_history, save_config, save_history, OLLAMA_URL, OUTPUT_DIR, MODELS_DIR
from models import scan_models, find_comfyui_automatically
import local_llm
from search import (
    combined_search, fetch_page_content,
    search_youtube, search_youtube_trending, search_news,
    search_civitai_models, search_wikipedia, search_arxiv,
    search_github, search_anime, get_crypto_prices, get_weather,
    get_exchange_rates, search_open_library, search_music,
    get_country_info, search_pypi, search_devto,
    search_reddit, search_twitter, search_instagram,
    search_huggingface,
)
from chat import (
    get_system_prompt, ollama_chat, ollama_vision, get_ollama_models, _save_turn,
)
from memory import (
    get_memory, add_fact, add_preference, clear_memory,
    delete_fact, delete_preference, get_ai_persona, save_ai_persona, detect_gender,
)
from downloads import DOWNLOADABLE_MODELS, _run_download
from generation import (
    GenRequest, generate, get_comfyui_url,
    _build_t2i_workflow, _comfyui_dispatch, smart_gen_request,
)

import requests as _requests

router = APIRouter()

# ── Identity guard (model-agnostic) ────────────────────────────────────────
_IDENTITY_Q = re.compile(
    r"(who\s+(are|made|created|built|develop(?:ed)?|trained)\s+you|"
    r"what('?s| is)?\s+your\s+name|what\s+(model|llm|ai|version)\s+are\s+you|"
    r"are\s+you\s+(qwen|gpt|chatgpt|llama|mistral|gemini|claude|dolphin)|"
    r"your\s+(creator|maker|developer)|what\s+are\s+you\s+based\s+on|which\s+(model|company))", re.I)

_SCRUB = [
    (re.compile(r"\bAlibaba\s+Cloud\b", re.I), "ACS Creative Studio"),
    (re.compile(r"\bAlibaba\b", re.I),         "ACS Creative Studio"),
    (re.compile(r"\bQwen\b", re.I),            None),
    (re.compile(r"\bTongyi(?:\s+Qianwen)?\b", re.I), None),
]

def _identity_question(message: str) -> bool:
    return bool(_IDENTITY_Q.search(message or ""))

def _identity_answer(name: str) -> str:
    return (f"I'm {name}, your assistant inside ACS Creative Studio. I run locally on your PC, "
            f"I have live web search for real-time info (weather, news, prices, and more), and I can help "
            f"with images, video, code, and writing. I don't represent any outside company. How can I help?")

def _scrub_identity(text: str, name: str) -> str:
    if not text:
        return text
    for pat, repl in _SCRUB:
        text = pat.sub(name if repl is None else repl, text)
    return text


# ── Image / video generation intent (chat-triggered) ───────────────────────
_VIDEO_INTENT = re.compile(r"\b(make|create|generate|render|produce)\b.{0,20}\b(video|clip|animation|gif)\b|"
                           r"\b(video|clip|animation)\b.{0,15}\b(of|for|about)\b", re.I)
_IMAGE_INTENT = re.compile(r"\b(make|create|generate|draw|paint|render|design|produce|give\s+me)\b.{0,24}"
                           r"\b(image|picture|pic|art|artwork|photo|drawing|illustration|wallpaper|logo|scene)\b|"
                           r"\b(draw|paint|generate|render)\s+(me\s+)?(a|an|the)\b", re.I)
# Short confirmations that should reuse the previous described scene.
_CONFIRM = re.compile(r"^\s*(ok(ay)?|yes|yep|sure|do it|go ahead|create it|make it|generate it|please)\b", re.I)

def _gen_intent(message: str):
    if _VIDEO_INTENT.search(message):
        return "video"
    if _IMAGE_INTENT.search(message):
        return "image"
    return None

# ── SFW prompt filter — blocks explicit image/video prompts at the source ───
_NSFW_TERMS = {
    "nude", "naked", "nudity", "nsfw", "porn", "porno", "xxx", "sex", "sexual",
    "erotic", "erotica", "hentai", "explicit", "topless", "bottomless", "lingerie",
    "underwear", "panties", "thong", "bikini", "cleavage", "breasts", "boobs", "tits",
    "nipple", "nipples", "areola", "pussy", "vagina", "penis", "cock", "dick", "genital",
    "genitalia", "cum", "cumshot", "blowjob", "anal", "orgasm", "masturbat", "fellatio",
    "sensual", "seductive", "provocative", "fetish", "bdsm", "bondage", "rule34",
    "onlyfans", "camgirl", "escort", "hooker", "slut", "milf", "creampie", "deepthroat",
}
_NSFW_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _NSFW_TERMS) + r")", re.I)

def _is_blocked_prompt(text: str) -> bool:
    return bool(_NSFW_RE.search(text or ""))

_BLOCK_MSG = ("I keep image and video generation strictly SFW, so I can't create that. "
              "Try a non-explicit prompt — landscapes, characters (clothed), art styles, objects, etc.")


def _clean_gen_prompt(message: str, history: list) -> str:
    """Turn a chat request into an image/video prompt."""
    msg = message.strip()
    # Pure confirmation ("ok create it") → reuse the assistant's last description.
    if _CONFIRM.match(msg) and len(msg.split()) <= 4 and history:
        for h in reversed(history):
            if h.get("role") == "assistant" and len(h.get("content", "")) > 20:
                return h["content"].strip()[:600]
    # Otherwise strip the command words and keep the subject.
    cleaned = re.sub(r"\b(can you|could you|please|for me|make|create|generate|draw|paint|render|design|produce|"
                     r"give me|a|an|the|image|picture|pic|photo|video|clip|animation|of|me)\b", " ", msg, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned if len(cleaned) >= 3 else msg


# ── GPU info — detected once at startup, never again ───────────────────────
_gpu_info: dict = {"cuda": False, "gpu": "CPU only", "vram_gb": 0}

def _warmup_gpu():
    try:
        import torch
        c = torch.cuda.is_available()
        n = torch.cuda.get_device_name(0) if c else "CPU only"
        v = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1) if c else 0
        _gpu_info.update({"cuda": c, "gpu": n, "vram_gb": v})
    except Exception:
        pass

threading.Thread(target=_warmup_gpu, daemon=True).start()

# ── scan_models cache (30-second TTL) ──────────────────────────────────────
_scan_cache: dict = {"data": None, "ts": 0.0}

def _models_cached() -> dict:
    if _scan_cache["data"] and time.time() - _scan_cache["ts"] < 30:
        return _scan_cache["data"]
    _scan_cache["data"] = scan_models()
    _scan_cache["ts"]   = time.time()
    return _scan_cache["data"]


# ── Status ─────────────────────────────────────────────────────────────────
@router.get("/api/status")
def get_status():
    models_list = get_ollama_models()
    ollama_ok   = False
    try:
        _requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_ok = True
    except Exception:
        pass

    cuda_ok  = _gpu_info["cuda"]
    gpu_name = _gpu_info["gpu"]
    vram_gb  = _gpu_info["vram_gb"]

    text_model   = config.get("ollama_text_model",  "llama3")
    vision_model = config.get("ollama_vision_model", "moondream")
    _persona = get_ai_persona()
    now = datetime.now()
    return {
        "ollama": ollama_ok, "ollama_models": models_list,
        "text_model": text_model, "vision_model": vision_model,
        "text_pulled":   any(text_model.split(":")[0]   in m for m in models_list),
        "vision_pulled": any(vision_model.split(":")[0] in m for m in models_list),
        "cuda": cuda_ok, "gpu": gpu_name, "vram_gb": vram_gb,
        "date": now.strftime("%A, %B %d, %Y"),
        "time": now.strftime("%I:%M %p"),
        "gen_status":  state["gen_status"],
        "gen_progress": state["gen_progress"],
        "gen_log":     state["gen_log"],
        "hf_token_set": bool(config.get("hf_token", "")),
        "models_dir": str(MODELS_DIR),
        "custom_models_dir": config.get("custom_models_dir", ""),
        "use_local_engine": bool(config.get("use_local_engine", False)),
        "ai_name":   _persona.get("name", "Nova"),
        "ai_gender": _persona.get("gender", "female"),
    }


# ── AI persona + local engine ──────────────────────────────────────────────
class PersonaReq(BaseModel):
    name:        str = ""
    gender:      str = ""
    personality: Optional[str] = None

@router.get("/api/persona")
def get_persona():
    return get_ai_persona()

@router.post("/api/persona")
def set_persona(req: PersonaReq):
    p = get_ai_persona()
    if req.name.strip():
        p["name"] = req.name.strip()
    if req.gender in ("male", "female"):
        p["gender"] = req.gender
    elif req.name.strip():
        p["gender"] = detect_gender(req.name)
    if req.personality is not None:
        p["personality"] = req.personality.strip()
    save_ai_persona(p)
    return {"ok": True, "persona": p}

@router.get("/api/local-models")
def local_models():
    return {"available": local_llm.available(), "models": local_llm.list_models()}


# ── Models ─────────────────────────────────────────────────────────────────
@router.get("/api/models")
def get_models():
    return _models_cached()


@router.get("/api/ollama/models")
def get_ollama_models_list():
    return {"models": get_ollama_models()}


class PullRequest(BaseModel):
    model_name: str

@router.post("/api/ollama/pull")
def ollama_pull(req: PullRequest):
    def do_pull():
        try:
            _requests.post(f"{OLLAMA_URL}/api/pull",
                           json={"name": req.model_name, "stream": False}, timeout=600)
        except Exception:
            pass
    threading.Thread(target=do_pull, daemon=True).start()
    return {"ok": True, "message": f"Pulling {req.model_name}..."}


# ── Config ─────────────────────────────────────────────────────────────────
class ConfigUpdate(BaseModel):
    hf_token:            Optional[str]  = None
    first_run_done:      Optional[bool] = None
    default_checkpoint:  Optional[str]  = None
    ollama_text_model:   Optional[str]  = None
    ollama_vision_model: Optional[str]  = None
    custom_models_dir:   Optional[str]  = None
    comfyui_dir:         Optional[str]  = None
    extra_scan_dirs:     Optional[list] = None
    civitai_token:       Optional[str]  = None
    comfyui_url:         Optional[str]  = None
    use_local_engine:    Optional[bool] = None
    local_gguf_path:     Optional[str]  = None

@router.post("/api/config")
def update_config(req: ConfigUpdate):
    data = req.model_dump(exclude_none=True)
    config.update(data)
    save_config(config)
    return {"ok": True}

@router.get("/api/config")
def get_config():
    safe = dict(config)
    tok  = safe.get("hf_token", "")
    if tok:
        safe["hf_token"] = tok[:8] + "..." + tok[-4:]
    ctok = safe.get("civitai_token", "")
    if ctok:
        safe["civitai_token"] = ctok[:4] + "..." + ctok[-4:]
    return safe


# ── Chat session management ────────────────────────────────────────────────
@router.get("/api/chat/sessions")
def get_sessions():
    sessions = []
    for sid in chat_history.get("order", []):
        sess = chat_history["sessions"].get(sid)
        if sess:
            sessions.append({
                "id": sid, "title": sess.get("title", "Untitled"),
                "model": sess.get("model", "llama3"),
                "created": sess.get("created", ""), "updated": sess.get("updated", ""),
                "message_count": len(sess.get("messages", [])),
            })
    return {"sessions": sessions}

@router.get("/api/chat/sessions/{session_id}")
def get_session(session_id: str):
    sess = chat_history["sessions"].get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return sess

@router.post("/api/chat/sessions")
def create_session():
    sid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    chat_history["sessions"][sid] = {
        "id": sid, "title": "New Chat",
        "model": config.get("ollama_text_model", "llama3"),
        "created": now, "updated": now, "messages": [],
    }
    chat_history["order"].insert(0, sid)
    save_history(chat_history)
    return {"id": sid}

@router.delete("/api/chat/sessions/{session_id}")
def delete_session(session_id: str):
    chat_history["sessions"].pop(session_id, None)
    if session_id in chat_history.get("order", []):
        chat_history["order"].remove(session_id)
    save_history(chat_history)
    return {"ok": True}

@router.delete("/api/chat/sessions")
def clear_all_sessions():
    chat_history["sessions"] = {}
    chat_history["order"]    = []
    save_history(chat_history)
    return {"ok": True}


# ── Chat ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message:    str
    session_id: str  = ""
    history:    list = []
    with_search: bool = False
    model:      str  = ""


def _build_search_context(message: str) -> tuple[str, list]:
    pasted_urls  = re.findall(r'https?://[^\s\'"<>]+', message)
    url_contexts = []
    for pu in pasted_urls[:2]:
        pg = fetch_page_content(pu, max_chars=2000)
        if pg:
            url_contexts.append(f"[Content of {pu}]:\n{pg}")

    raw     = combined_search(message, safe=True)
    sources = []
    lines   = []
    if raw:
        sources = [{"source": r["source"], "title": r["title"][:80], "url": r["url"]}
                   for r in raw[:8] if r.get("url")]
        for r in raw[:8]:
            lines.append(f"- [{r['source']}] {r['title']}: {r['text'][:200]}")
        if not pasted_urls:
            top_web = next((r for r in raw
                            if r.get("url", "").startswith("http")
                            and r.get("source", "") in ("DDG", "SearXNG", "Google News", "GDELT")), None)
            if top_web and top_web.get("url"):
                pg = fetch_page_content(top_web["url"], max_chars=1500)
                if pg:
                    lines.append(f"\n[Full page: {top_web['url']}]:\n{pg}")

    search_ctx = "\n\nWeb results:\n" + "\n".join(lines) if lines else ""
    if url_contexts:
        search_ctx = "\n\n" + "\n\n".join(url_contexts) + search_ctx
    return search_ctx, sources


@router.post("/api/chat")
def chat(req: ChatRequest):
    model     = req.model or config.get("ollama_text_model", "llama3")
    msg_lower = req.message.lower()
    for kw in ["i like", "i prefer", "i want", "i love"]:
        if kw in msg_lower:
            state["preferences"]["last_preference"] = req.message[:120]
            break

    now      = datetime.now()
    _name    = get_ai_persona().get("name", "Nova")

    # Deterministic identity answer — never reveal the underlying model.
    if _identity_question(req.message):
        ans = _identity_answer(_name)
        _save_turn(req.session_id, req.message, ans, model, now)
        return {"response": ans, "searched": False}

    if req.with_search:
        search_ctx, _ = _build_search_context(req.message)
    else:
        search_ctx = ""
    date_inject    = f"[{now.strftime('%A, %B %d, %Y')} {now.strftime('%I:%M %p')} IST] "
    messages       = (req.history + [{"role": "user",
                                       "content": date_inject + req.message + search_ctx}])[-20:]
    system_prompt  = get_system_prompt(model)

    if config.get("use_local_engine"):
        response = local_llm.chat(messages, system=system_prompt)
    else:
        response = ollama_chat(messages, system=system_prompt, model=model)
    response = _scrub_identity(response, _name)

    _save_turn(req.session_id, req.message, response, model, now)
    return {"response": response, "searched": bool(search_ctx)}


@router.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    model     = req.model or config.get("ollama_text_model", "llama3")
    msg_lower = req.message.lower()
    for kw in ["i like", "i prefer", "i want", "i love"]:
        if kw in msg_lower:
            state["preferences"]["last_preference"] = req.message[:120]
            break

    now           = datetime.now()
    date_inject   = f"[{now.strftime('%A, %B %d, %Y')} {now.strftime('%I:%M %p')} IST] "
    system_prompt = get_system_prompt(model)

    def generate_stream():
        # ── Image / video generation intent — actually run the pipeline ──────
        _kind = _gen_intent(req.message)
        if _kind:
            _name = get_ai_persona().get("name", "Nova")
            prompt = _clean_gen_prompt(req.message, req.history)
            # SFW guard — refuse explicit generation prompts.
            if _is_blocked_prompt(req.message) or _is_blocked_prompt(prompt):
                yield f"data: {json.dumps({'type':'delta','content':_BLOCK_MSG})}\n\n"
                _save_turn(req.session_id, req.message, _BLOCK_MSG, model, now)
                yield f"data: {json.dumps({'type':'done'})}\n\n"
                return
            mode = "t2v" if _kind == "video" else "t2i"
            yield f"data: {json.dumps({'type':'gen_start','kind':_kind,'prompt':prompt})}\n\n"

            result_holder: dict = {}
            def _run():
                try:
                    result_holder["result"] = generate(smart_gen_request(prompt, mode))
                except Exception as e:
                    result_holder["error"] = str(e)
                finally:
                    result_holder["finished"] = True

            t = threading.Thread(target=_run, daemon=True); t.start()
            t0 = time.time()
            last_pct = -1
            while not result_holder.get("finished"):
                time.sleep(0.5)
                pct = int(state.get("gen_progress", 0) or 0)
                elapsed = time.time() - t0
                eta = int(elapsed / pct * (100 - pct)) if pct > 3 else 0
                if pct != last_pct:
                    last_pct = pct
                    yield f"data: {json.dumps({'type':'gen_progress','pct':pct,'log':state.get('gen_log',''),'eta':eta,'elapsed':int(elapsed)})}\n\n"
            if result_holder.get("error"):
                msg = f"Sorry, I couldn't generate that {_kind}: {result_holder['error']}"
                yield f"data: {json.dumps({'type':'delta','content':msg})}\n\n"
                _save_turn(req.session_id, req.message, msg, model, now)
                yield f"data: {json.dumps({'type':'done'})}\n\n"
                return
            res = result_holder.get("result", {})
            fname = res.get("filename", "")
            url = f"/outputs/{fname}" if fname else ""
            yield f"data: {json.dumps({'type':'gen_done','kind':_kind,'url':url,'prompt':prompt})}\n\n"
            saved = (f"Here's the {_kind} I generated:\n\n"
                     + (f"![{prompt[:60]}]({url})" if _kind == "image" else f"[▶ Watch video]({url})")
                     + f"\n\n*Prompt: {prompt[:200]}*")
            _save_turn(req.session_id, req.message, saved, model, now)
            yield f"data: {json.dumps({'type':'done'})}\n\n"
            return

        # Search runs inside the generator so the SSE connection opens immediately
        # and the client sees typing dots instead of a blank screen during search.
        if req.with_search:
            yield f"data: {json.dumps({'type':'searching'})}\n\n"
            search_ctx, search_sources = _build_search_context(req.message)
        else:
            search_ctx, search_sources = "", []

        yield f"data: {json.dumps({'type':'meta','searched':bool(search_sources),'sources':search_sources})}\n\n"

        _name = get_ai_persona().get("name", "Nova")

        # Deterministic identity answer — applies to every engine.
        if _identity_question(req.message):
            ans = _identity_answer(_name)
            yield f"data: {json.dumps({'type':'delta','content':ans})}\n\n"
            _save_turn(req.session_id, req.message, ans, model, now)
            yield f"data: {json.dumps({'type':'done'})}\n\n"
            return

        messages_payload = (req.history + [{"role": "user",
                                             "content": date_inject + req.message + search_ctx}])[-20:]
        full, _hold = "", ""

        # Embedded local engine (no Ollama) — stream tokens from llama-cpp-python.
        if config.get("use_local_engine"):
            for delta in local_llm.stream(messages_payload, system=system_prompt):
                full += delta; _hold += delta
                if len(_hold) > 20:
                    emit, _hold = _hold[:-20], _hold[-20:]
                    emit = _scrub_identity(emit, _name)
                    if emit:
                        yield f"data: {json.dumps({'type':'delta','content':emit})}\n\n"
            if _hold:
                emit = _scrub_identity(_hold, _name)
                if emit:
                    yield f"data: {json.dumps({'type':'delta','content':emit})}\n\n"
            if full:
                _save_turn(req.session_id, req.message, _scrub_identity(full, _name), model, now)
            yield f"data: {json.dumps({'type':'done'})}\n\n"
            return

        try:
            # Prepend identity priming + system as a message (Ollama /api/chat
            # ignores a top-level "system" field).
            primed = messages_payload
            if not any(m.get("role") == "assistant" for m in primed):
                primed = [
                    {"role": "user",      "content": "What is your name and who made you?"},
                    {"role": "assistant", "content": f"I'm {_name}, the assistant built into ACS Creative Studio. I don't represent any outside company or model."},
                ] + primed
            chat_messages = [{"role": "system", "content": system_prompt}] + primed
            payload = {"model": model, "messages": chat_messages, "stream": True}
            with _requests.post(f"{OLLAMA_URL}/api/chat",
                                json=payload, stream=True, timeout=120) as resp:
                if resp.status_code != 200:
                    yield f"data: {json.dumps({'type':'error','message':f'Ollama error {resp.status_code}'})}\n\n"
                    return
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("error"):
                            yield f"data: {json.dumps({'type':'error','message':data['error']})}\n\n"
                            return
                        if data.get("done"):
                            break
                        delta = data.get("message", {}).get("content", "")
                        if delta:
                            full += delta; _hold += delta
                            if len(_hold) > 20:
                                emit, _hold = _hold[:-20], _hold[-20:]
                                emit = _scrub_identity(emit, _name)
                                if emit:
                                    yield f"data: {json.dumps({'type':'delta','content':emit})}\n\n"
                    except Exception:
                        continue
            if _hold:
                emit = _scrub_identity(_hold, _name)
                if emit:
                    yield f"data: {json.dumps({'type':'delta','content':emit})}\n\n"
        except _requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'type':'error','message':'Ollama is not running. Start it from the Start Menu.'})}\n\n"
            return
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
            return

        if full:
            _save_turn(req.session_id, req.message, _scrub_identity(full, _name), model, now)
        yield f"data: {json.dumps({'type':'done'})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Image analysis ─────────────────────────────────────────────────────────
class ImageAnalysisRequest(BaseModel):
    image: str
    task:  str = "describe"

ANALYSIS_PROMPTS = {
    "describe":  "Describe this image in full detail: subjects, poses, expressions, clothing, background, lighting, mood, art style.",
    "pose":      "Describe every body pose: limb angles, hand positions, facial expression, body orientation.",
    "style":     "Analyze the art style: technique, medium, color palette, line work, shading, influences.",
    "prompt":    "Write a Stable Diffusion prompt to recreate this image exactly.",
    "character": "Extract a complete character sheet: face features, hair, eyes, clothing, accessories, body. Format as a reusable SD prompt.",
    "translate": "Translate any text in this image to English. Also describe what the image shows.",
}

@router.post("/api/analyze-image")
def analyze_image(req: ImageAnalysisRequest):
    return {
        "analysis": ollama_vision(req.image, ANALYSIS_PROMPTS.get(req.task, ANALYSIS_PROMPTS["describe"])),
        "task": req.task,
    }


# ── ComfyUI ────────────────────────────────────────────────────────────────
@router.get("/api/comfyui/status")
def comfyui_status_ep():
    url = get_comfyui_url()
    try:
        r = _requests.get(f"{url}/system_stats", timeout=4)
        d = r.json()
        return {"connected": True, "url": url,
                "version": d.get("system", {}).get("comfyui_version", "?")}
    except Exception:
        return {"connected": False, "url": url, "version": None}


class ComfyUIGenRequest(BaseModel):
    prompt:   str
    negative: str   = "bad quality, blurry"
    model:    str   = ""
    width:    int   = 832
    height:   int   = 1216
    steps:    int   = 20
    cfg:      float = 7.0
    seed:     int   = -1

@router.post("/api/comfyui/generate")
def comfyui_generate(req: ComfyUIGenRequest):
    if _is_blocked_prompt(req.prompt):
        return {"error": _BLOCK_MSG}
    url        = get_comfyui_url()
    seed       = req.seed if req.seed >= 0 else int(time.time()) % (2 ** 31)
    model_name = Path(req.model).name if req.model else ""
    if not model_name:
        return {"error": "Select a checkpoint model before using ComfyUI generation."}
    workflow = _build_t2i_workflow(req.prompt, req.negative, model_name,
                                   req.width, req.height, req.steps, req.cfg, seed)
    return _comfyui_dispatch(workflow, url, seed)


# ── Generation ─────────────────────────────────────────────────────────────
@router.post("/api/generate")
def generate_ep(req: GenRequest):
    # SFW guard — block explicit prompts at the generation layer.
    if _is_blocked_prompt(req.prompt):
        return {"error": _BLOCK_MSG}
    return generate(req)


# ── Prompt tools ───────────────────────────────────────────────────────────
class PromptRequest(BaseModel):
    prompt: str
    style:  str = "anime"
    mode:   str = "t2i"

@router.post("/api/enhance-prompt")
def enhance_prompt(req: PromptRequest):
    mode_hint = {"t2i": "static image", "i2i": "image transformation",
                 "t2v": "text-to-video", "i2v": "image-to-video"}.get(req.mode, "image")
    now    = datetime.now().strftime("%A, %B %d, %Y")
    system = (
        f"You are an expert Stable Diffusion prompt engineer. Today: {now}. "
        f"Task: take the user's rough prompt and DIRECTLY rewrite it as a highly detailed, vivid SD prompt for a {mode_hint}. "
        "Rules: NEVER ask questions. NEVER refuse. NEVER add explanations. Just enhance it. "
        "Add: lighting style, camera angle, art style, quality tags, color palette, details. "
        "Output ONLY valid JSON with exactly these keys: "
        "\"positive\" (the enhanced prompt string), "
        "\"negative\" (negative prompt string), "
        "\"tips\" (array of exactly 3 short improvement tips). "
        "No markdown, no explanation, just the JSON."
    )
    resp = ollama_chat([{"role": "user", "content": f"Enhance this prompt: {req.prompt}"}], system=system)
    try:
        m = re.search(r'\{.*\}', resp, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {"positive": resp.strip(),
            "negative": "bad quality, blurry, deformed, ugly, watermark", "tips": []}


class SuggestRequest(BaseModel):
    theme: str
    count: int = 5
    mode:  str = "t2i"

@router.post("/api/suggest-prompts")
def suggest_prompts(req: SuggestRequest):
    now  = datetime.now().strftime("%A, %B %d, %Y")
    resp = ollama_chat(
        [{"role": "user", "content": f"Generate {req.count} creative {req.mode.upper()} prompts for: '{req.theme}'. SFW only. Return as JSON array of strings only."}],
        system=f"Creative prompt engineer. Today: {now}.",
    )
    try:
        m = re.search(r'\[.*\]', resp, re.DOTALL)
        if m:
            return {"prompts": json.loads(m.group())}
    except Exception:
        pass
    return {"prompts": [l.strip().strip('-"') for l in resp.split('\n') if l.strip()][:req.count]}


# ── AI Advisor ─────────────────────────────────────────────────────────────
class AdvisorRequest(BaseModel):
    goal: str
    mode: str = ""

@router.post("/api/advisor")
def advisor(req: AdvisorRequest):
    models_data     = _models_cached()
    installed_lines = []
    for cat, items in models_data.items():
        if cat.startswith("_"):
            continue
        flat = items if isinstance(items, list) else [f for g in items.values() for f in g]
        if flat:
            names = ", ".join(f["name"] for f in flat[:5])
            installed_lines.append(f"{cat}: {names}")
    installed_ctx = "\n".join(installed_lines) or "No models installed yet."
    system = (
        "You are an expert AI art model advisor for Stable Diffusion, Wan video, and FLUX models. "
        "Given the user's creative goal and their installed models, recommend exactly what to use. "
        "Reply ONLY as valid JSON with these keys: "
        "recommendation (string, 2-3 sentences), "
        "suggested_model (string, exact filename if known), "
        "suggested_mode (one of: t2i, i2i, t2v, i2v, inpaint), "
        "settings (object with optional: steps, cfg, width, height, negative). "
        "If the ideal model is NOT installed, name it and tell them to download it from the Downloads tab."
    )
    msg  = f"My goal: {req.goal}\nPreferred mode: {req.mode or 'not specified'}\n\nInstalled models:\n{installed_ctx}"
    resp = ollama_chat([{"role": "user", "content": msg}], system=system)
    try:
        m = re.search(r'\{.*\}', resp, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {"recommendation": resp, "suggested_model": "", "suggested_mode": req.mode or "t2i", "settings": {}}


# ── Downloads ──────────────────────────────────────────────────────────────
@router.get("/api/downloads")
def get_downloads():
    downloaded = config.get("downloaded_models", [])
    result     = []
    for m in DOWNLOADABLE_MODELS:
        entry      = {k: v for k, v in m.items() if k != "files"}
        save_dir   = Path(m["save_dir"])
        files_present = all((save_dir / fi["filename"]).exists() for fi in m.get("files", []))
        if files_present and m["id"] not in downloaded:
            downloaded.append(m["id"])
            config["downloaded_models"] = downloaded
            save_config(config)
        entry["downloaded"]   = files_present or m["id"] in downloaded
        entry["status"]       = state["download_status"].get(m["id"], {})
        entry["has_partial"]  = any(save_dir.glob("*.part")) if save_dir.exists() else False
        result.append(entry)
    return {"models": result}


class DownloadRequest(BaseModel):
    model_id: str

@router.post("/api/download/start")
def start_download(req: DownloadRequest):
    model = next((m for m in DOWNLOADABLE_MODELS if m["id"] == req.model_id), None)
    if not model:
        raise HTTPException(404, "Model not found")
    if req.model_id in config.get("downloaded_models", []):
        return {"ok": True, "message": "Already downloaded"}
    if req.model_id in state["download_threads"]:
        return {"ok": False, "message": "Already downloading"}
    stop_evt  = threading.Event()
    pause_evt = threading.Event()
    t = threading.Thread(target=_run_download, args=(req.model_id,), daemon=True)
    state["download_threads"][req.model_id] = {"thread": t, "stop_event": stop_evt, "pause_event": pause_evt}
    t.start()
    return {"ok": True, "message": f"Download started: {model['name']}"}

@router.post("/api/download/pause")
def pause_download(req: DownloadRequest):
    ctrl = state["download_threads"].get(req.model_id)
    if ctrl:
        ctrl["pause_event"].set()
        state["download_status"][req.model_id]["status"] = "paused"
        return {"ok": True}
    return {"ok": False}

@router.post("/api/download/resume")
def resume_download(req: DownloadRequest):
    ctrl = state["download_threads"].get(req.model_id)
    if ctrl:
        ctrl["pause_event"].clear()
        return {"ok": True}
    return start_download(req)

@router.post("/api/download/cancel")
def cancel_download(req: DownloadRequest):
    ctrl = state["download_threads"].get(req.model_id)
    if ctrl:
        ctrl["stop_event"].set()
        ctrl["pause_event"].clear()
        return {"ok": True}
    state["download_status"].pop(req.model_id, None)
    return {"ok": True}


class DeleteModelRequest(BaseModel):
    model_id:   Optional[str] = None
    model_path: Optional[str] = None

@router.post("/api/model/delete")
def delete_model(req: DeleteModelRequest):
    from config import MODELS_DIR
    deleted = []
    if req.model_path:
        p = Path(req.model_path)
        if p.exists() and str(p).startswith(str(MODELS_DIR)):
            p.unlink()
            deleted.append(str(p))
    if req.model_id:
        model = next((m for m in DOWNLOADABLE_MODELS if m["id"] == req.model_id), None)
        if model:
            for fi in model.get("files", []):
                p = Path(model["save_dir"]) / fi["filename"]
                if p.exists():
                    p.unlink()
                    deleted.append(str(p))
            for f in Path(model["save_dir"]).glob("*.part"):
                f.unlink()
        dl = config.get("downloaded_models", [])
        if req.model_id in dl:
            dl.remove(req.model_id)
            config["downloaded_models"] = dl
            save_config(config)
        state["download_status"].pop(req.model_id, None)
    return {"ok": True, "deleted": deleted}


# ── Outputs ────────────────────────────────────────────────────────────────
@router.get("/api/outputs")
def list_outputs():
    files = []
    for f in sorted(OUTPUT_DIR.glob("*"), reverse=True)[:50]:
        if f.suffix in (".png", ".jpg", ".mp4", ".gif", ".webp"):
            meta_file = OUTPUT_DIR / (f.stem + ".json")
            meta = {}
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            files.append({
                "name": f.name, "url": f"/outputs/{f.name}",
                "size_mb": round(f.stat().st_size / 1e6, 2),
                "time": f.stat().st_mtime,
                "type": "video" if f.suffix == ".mp4" else "image",
                "meta": meta,
            })
    return {"files": files}

@router.delete("/api/outputs/{filename}")
def delete_output(filename: str):
    safe    = Path(filename).name
    deleted = []
    for target in [OUTPUT_DIR / safe, OUTPUT_DIR / (Path(safe).stem + ".json")]:
        if target.exists():
            target.unlink()
            deleted.append(target.name)
    return {"ok": True, "deleted": deleted}


# ── Face restoration ──────────────────────────────────────────────────────
class FaceRestoreRequest(BaseModel):
    image: str  # base64

@router.post("/api/face-restore")
def face_restore(req: FaceRestoreRequest):
    import io, base64
    from PIL import Image as PILImage, ImageFilter

    data = req.image.split(",")[-1]
    img_bytes = base64.b64decode(data)
    img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")

    # Try GFPGAN first
    try:
        import numpy as np
        from gfpgan import GFPGANer
        restorer = GFPGANer(
            model_path=None, upscale=1, arch="clean", channel_multiplier=2,
        )
        _, _, restored = restorer.enhance(np.array(img), has_aligned=False, only_center_face=False, paste_back=True)
        img = PILImage.fromarray(restored)
    except Exception:
        # Fallback: unsharp mask sharpening (always available)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))

    buf = io.BytesIO(); img.save(buf, format="PNG")
    return {"image": base64.b64encode(buf.getvalue()).decode()}


# ── CLIP Interrogator (Ollama vision) ─────────────────────────────────────
class InterrogateRequest(BaseModel):
    image: str  # base64

@router.post("/api/interrogate")
def interrogate_image(req: InterrogateRequest):
    vision_model = config.get("ollama_vision_model", "") or config.get("chat_model", "")
    if not vision_model:
        return {"error": "No vision model configured. Set one in Settings."}
    try:
        from chat import ollama_vision
        prompt_text = ollama_vision(
            req.image,
            "Describe this image as a Stable Diffusion prompt. "
            "Output ONLY the prompt — comma-separated tags and descriptors, no sentences, no explanation. "
            "Include: subject, style, lighting, colors, quality tags. Keep under 120 words.",
        )
        if not prompt_text or prompt_text.startswith("Ollama"):
            return {"error": "Vision model did not return a result. Make sure it supports images."}
        return {"prompt": prompt_text.strip()}
    except Exception as e:
        return {"error": str(e)}


# ── Background removal ────────────────────────────────────────────────────
class RemoveBgRequest(BaseModel):
    image: str  # base64 PNG/JPEG

@router.post("/api/remove-bg")
def remove_bg(req: RemoveBgRequest):
    try:
        from rembg import remove
        from PIL import Image as PILImage
        import io, base64
        data = req.image.split(",")[-1]
        img_bytes = base64.b64decode(data)
        img_in = PILImage.open(io.BytesIO(img_bytes)).convert("RGBA")
        img_out = remove(img_in)
        buf = io.BytesIO()
        img_out.save(buf, format="PNG")
        result_b64 = base64.b64encode(buf.getvalue()).decode()
        return {"image": result_b64}
    except ImportError:
        return {"error": "rembg not installed. Run: pip install rembg"}
    except Exception as e:
        return {"error": f"Background removal failed: {e}"}


# ── Scan / ComfyUI discovery ───────────────────────────────────────────────
@router.get("/api/find-comfyui")
def find_comfyui():
    found = find_comfyui_automatically()
    return {"found": found, "count": len(found)}

@router.post("/api/scan")
def force_rescan():
    return scan_models()


# ── Search endpoints ───────────────────────────────────────────────────────
@router.get("/api/search/youtube")
def youtube_search_ep(q: str, safe: bool = True):
    return {"results": search_youtube(q, safe)}

@router.get("/api/search/youtube/trending")
def youtube_trending_ep():
    return {"results": search_youtube_trending()}

@router.get("/api/search/news")
def news_search_ep(q: str, safe: bool = True):
    return {"results": search_news(q, safe)}

@router.get("/api/search/civitai")
def civitai_search_ep(q: str):
    return {"results": search_civitai_models(q)}


# ── CivitAI browser (rich model cards + 1-click download) ─────────────────
@router.get("/api/civitai/browse")
def civitai_browse(q: str = "", type: str = "", page: int = 1):
    try:
        headers = {"User-Agent": "AI-Creative-Studio/3.0"}
        token = config.get("civitai_token", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # SFW only — never request NSFW models.
        params = {"limit": 20, "page": page, "sort": "Most Downloaded", "nsfw": "false"}
        if q.strip():
            params["query"] = q.strip()
        if type:
            params["types"] = type

        r = _requests.get("https://civitai.com/api/v1/models",
                          params=params, headers=headers, timeout=12)
        if r.status_code != 200:
            return {"error": f"CivitAI returned HTTP {r.status_code}", "models": [], "total": 0}

        data = r.json()
        models = []
        for m in data.get("items", []):
            versions = m.get("modelVersions", [])
            if not versions:
                continue
            latest = versions[0]

            # pick a safe preview image
            images = latest.get("images", [])
            safe_imgs = [i for i in images if not i.get("nsfw") and i.get("url")]
            preview = (safe_imgs or [i for i in images if i.get("url")] or [{}])[0].get("url", "")

            # primary file info
            files = latest.get("files", [])
            primary = next((f for f in files if f.get("primary")), files[0] if files else {})
            size_mb = round(primary.get("sizeKB", 0) / 1024, 1)
            filename = primary.get("name", f"model_{latest.get('id','')}.safetensors")

            # model type → save dir
            mtype = m.get("type", "Checkpoint")
            type_dir = {
                "Checkpoint": "models/checkpoints",
                "LORA": "models/loras/civitai",
                "LoCon": "models/loras/civitai",
                "TextualInversion": "models/embeddings",
                "VAE": "models/vae",
                "Upscaler": "models/upscalers",
            }.get(mtype, "models/checkpoints")

            models.append({
                "id":           m.get("id"),
                "name":         m.get("name", ""),
                "type":         mtype,
                "nsfw":         m.get("nsfw", False),
                "tags":         m.get("tags", [])[:6],
                "creator":      (m.get("creator") or {}).get("username", ""),
                "stats":        m.get("stats", {}),
                "preview":      preview,
                "version_id":   latest.get("id"),
                "version_name": latest.get("name", ""),
                "download_url": latest.get("downloadUrl", ""),
                "filename":     filename,
                "size_mb":      size_mb,
                "save_dir":     type_dir,
                "all_versions": [
                    {"id": v.get("id"), "name": v.get("name", ""),
                     "download_url": v.get("downloadUrl", ""),
                     "files": v.get("files", [])}
                    for v in versions[:5]
                ],
            })

        return {"models": models, "total": data.get("metadata", {}).get("totalItems", 0)}
    except Exception as e:
        return {"error": str(e), "models": [], "total": 0}


class CivitaiDownloadBody(BaseModel):
    version_id:   int
    name:         str
    filename:     str
    download_url: str
    type:         str   = "Checkpoint"
    size_mb:      float = 0
    save_dir:     str   = "models/checkpoints"

@router.post("/api/civitai/download")
def civitai_download_ep(body: CivitaiDownloadBody):
    from downloads import DOWNLOADABLE_MODELS, _run_download
    model_id = f"civitai_{body.version_id}"

    # avoid duplicate entries
    if not any(m["id"] == model_id for m in DOWNLOADABLE_MODELS):
        DOWNLOADABLE_MODELS.append({
            "id":          model_id,
            "name":        body.name,
            "description": f"CivitAI model ({body.type})",
            "size":        f"~{body.size_mb:.0f} MB",
            "category":    "loras" if body.type in ("LORA","LoCon") else "checkpoints",
            "save_dir":    body.save_dir,
            "files": [{"url": body.download_url, "filename": body.filename}],
            "requires_hf_token":     False,
            "requires_civitai_token": True,
        })

    threading.Thread(target=_run_download, args=(model_id,), daemon=True).start()
    return {"ok": True, "model_id": model_id}

@router.get("/api/search/wikipedia")
def wikipedia_ep(q: str):
    return {"results": search_wikipedia(q)}

@router.get("/api/search/arxiv")
def arxiv_ep(q: str):
    return {"results": search_arxiv(q)}

@router.get("/api/search/github")
def github_ep(q: str):
    return {"results": search_github(q)}

@router.get("/api/search/anime")
def anime_ep(q: str):
    return {"results": search_anime(q)}

@router.get("/api/search/crypto")
def crypto_ep(q: str):
    return {"results": get_crypto_prices(q)}

@router.get("/api/search/weather")
def weather_ep(q: str):
    return {"results": get_weather(q)}

@router.get("/api/search/exchange")
def exchange_ep(q: str):
    return {"results": get_exchange_rates(q)}

@router.get("/api/search/books")
def books_ep(q: str):
    return {"results": search_open_library(q)}

@router.get("/api/search/music")
def music_ep(q: str):
    return {"results": search_music(q)}

@router.get("/api/search/country")
def country_ep(q: str):
    return {"results": get_country_info(q)}

@router.get("/api/search/pypi")
def pypi_ep(q: str):
    return {"results": search_pypi(q)}

@router.get("/api/search/devto")
def devto_ep(q: str):
    return {"results": search_devto(q)}

@router.get("/api/search/reddit")
def reddit_ep(q: str, sr: str = ""):
    return {"results": search_reddit(q, sr)}

@router.get("/api/search/twitter")
def twitter_ep(q: str):
    return {"results": search_twitter(q)}

@router.get("/api/search/instagram")
def instagram_ep(q: str):
    return {"results": search_instagram(q)}

@router.get("/api/search/huggingface")
def huggingface_ep(q: str):
    return {"results": search_huggingface(q)}

@router.get("/api/browse/page")
def browse_page_ep(url: str, max_chars: int = 2000):
    content = fetch_page_content(url, max_chars)
    return {"url": url, "content": content, "length": len(content)}


# ── File browser ───────────────────────────────────────────────────────────
@router.get("/api/browse")
def browse_files(path: str = "", exts: str = ".safetensors,.ckpt,.pt,.bin,.pth,.gguf"):
    import platform
    ext_list = [e.strip().lower() for e in exts.split(",") if e.strip()]
    if not path:
        if platform.system() == "Windows":
            import string, ctypes
            drives  = []
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drives.append({"name": f"{letter}:\\", "path": f"{letter}:\\", "type": "drive"})
                bitmask >>= 1
            return {"items": drives, "current": "", "parent": None}
        return {"items": [{"name": "/", "path": "/", "type": "drive"}], "current": "", "parent": None}

    p = Path(path)
    if not p.exists():
        raise HTTPException(404, f"Path not found: {path}")
    items = []
    try:
        for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            try:
                if item.is_dir() and not item.name.startswith("."):
                    items.append({"name": item.name, "path": str(item), "type": "dir"})
                elif item.is_file() and item.suffix.lower() in ext_list:
                    items.append({"name": item.name, "path": str(item), "type": "file",
                                  "size_mb": round(item.stat().st_size / 1e6, 1)})
            except PermissionError:
                pass
    except PermissionError:
        raise HTTPException(403, "Permission denied")
    parent = str(p.parent) if p.parent != p else None
    return {"items": items, "current": str(p), "parent": parent}


# ── Memory ─────────────────────────────────────────────────────────────────
@router.get("/api/memory")
def get_memory_ep():
    return get_memory()

@router.post("/api/memory/fact")
def add_fact_ep(body: dict):
    fact = (body.get("fact") or "").strip()
    if fact:
        add_fact(fact)
    return {"ok": True}

@router.post("/api/memory/preference")
def add_pref_ep(body: dict):
    pref = (body.get("preference") or "").strip()
    if pref:
        add_preference(pref)
    return {"ok": True}

@router.delete("/api/memory/fact/{index}")
def del_fact_ep(index: int):
    delete_fact(index)
    return {"ok": True}

@router.delete("/api/memory/preference/{index}")
def del_pref_ep(index: int):
    delete_preference(index)
    return {"ok": True}

@router.post("/api/memory/clear")
def clear_memory_ep():
    clear_memory()
    return {"ok": True}
