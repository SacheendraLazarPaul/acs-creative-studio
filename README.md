# ACS — AI Creative Studio

A local AI creative studio for image & video generation, model management, streaming chat, and character-driven scene production.

**Stack:** React + Vite · FastAPI · SQLite · Ollama (local LLM) · diffusers (local image/video)  
**No cloud APIs required** — everything runs on your machine.

---

## Features

### Chat
- Streaming chat with any Ollama model (dolphin-mistral, llama3, mistral, qwen, etc.)
- **Persistent memory** — the AI remembers facts and preferences across sessions, stored in `backend/data/memory.json`
- **Web search** — toggle the globe icon to include live results from 20+ sources (DuckDuckGo, YouTube, Wikipedia, GitHub, news, weather, and more)
- **Vision analysis** — attach an image for describe / pose / style / SD-prompt / character-sheet / translate tasks (requires a vision model like `moondream`)
- **Code blocks** — language label, Copy button, and Download button on every code snippet
- Pause / Resume / Stop streaming at any time
- Full session history with sidebar; sessions are auto-titled

### Image Generation

| Mode | Description |
|------|-------------|
| Text → Image | Generate from a prompt |
| Image → Image | Transform a reference image |
| Inpaint | Edit a masked region |
| Upscale | 2×/4×/6×/8× (Real-ESRGAN or PIL fallback) |

**Universal model loader** — detects architecture from the safetensors header:
- **Flux** — `FluxPipeline` / `FluxImg2ImgPipeline`, bfloat16, CPU offload
- **SD 3 / 3.5** — `StableDiffusion3Pipeline`
- **SDXL / Pony / Illustrious** — `StableDiffusionXLPipeline` family
- **SD 1.5** — `AutoPipelineForText2Image` with SD1.5 fallback
- **ComfyUI passthrough** — routes GGUF and advanced workflows to ComfyUI if running

Aspect ratio quick-pick: Square, Portrait, Landscape, Wide 16:9, Tall 9:16.  
Advanced panel: Strength, Frames, FPS, Seed.

### Video Generation
- **Wan 2.1 / 2.2** Text→Video and Image→Video — runs from local `.safetensors` files
- **LTX-Video** fallback if no Wan model is selected
- GGUF video models route to ComfyUI automatically

### Model Manager
- Scans all local model folders, ComfyUI directories, and any extra paths you configure
- Detects architecture, quantization, and variant from filename and safetensors header
- Categories: Checkpoints, LoRAs, VAE, Text Encoders, ControlNet, IP-Adapter, Upscalers, Video, Audio, TTS, 3D
- ComfyUI auto-discovery scans all drives

### Downloads
Pre-configured download catalogue with progress bars:
- SDXL Turbo · DreamShaper XL · Wan 2.1 T2V · LTX-Video · Moondream vision
- Real-ESRGAN upscaler · OpenPose ControlNet · IP-Adapter Face ID · LoRAs

### Gallery
- Thumbnail grid of all generated images and videos
- Metadata sidecar (`.json`) stored alongside each output — prompt, model, seed, steps, CFG, dimensions
- Delete individual outputs

### AI Advisor
Describe your creative goal → AI recommends the best installed model, generation mode, and settings.

### Prompt Enhancement
Sparkle button in Generate → AI rewrites your rough description into a detailed SD prompt with lighting, camera angle, quality tags, and a negative prompt.

### Studio AI (KK Bridge)
A separate FastAPI microservice (`kk/`, port 7862) that bridges the AI stack to CharaStudio:
- **Character brain** — personality archetypes, emotion engine, dynamic expression selection
- **Scene director** — Ollama-powered scene composition, camera selection, animation scripting
- **Story DB** — SQLite-backed character profiles, relationships, scenes, dialogue, and a knowledge base
- **Voice** — TTS via edge-tts with emotion-driven prosody (rate, pitch, volume)
- **Ren'Py export** — generates a playable visual novel project from the story database
- **BepInEx plugin** (`kk/bridge/KKAIBridge.cs`) — C# plugin that receives AI commands inside CharaStudio

### Settings
- Ollama text + vision model selector (pull models directly from UI)
- HuggingFace and CivitAI token storage
- Custom models directory, ComfyUI directory, extra scan paths
- Memory panel — view, add, and delete facts the AI remembers

---

## Setup

### 1. Chat (required for AI features)

Install [Ollama](https://ollama.com), then pull models:

```
ollama pull dolphin-mistral
ollama pull moondream
```

Or use **Settings → Pull model** in the UI.

### 2. Image / Video generation

Install PyTorch + diffusers once (several GB):

```
INSTALL_AI.bat  →  choose 1 for NVIDIA GPU (RTX)  or  2 for CPU
```

Then `START.bat` as usual.

### 3. Real-ESRGAN upscaling (optional)

```
pip install realesrgan basicsr
```

Falls back to PIL LANCZOS if not installed.

### 4. Config

Copy `backend/config.example.json` → `backend/config.json` and fill in your tokens:

```json
{
  "hf_token": "YOUR_HUGGINGFACE_TOKEN",
  "civitai_token": "YOUR_CIVITAI_TOKEN"
}
```

---

## Quick Start

```
START.bat        →  open http://localhost:7860
DEV.bat          →  hot-reload dev (frontend :5173, backend :7860)
REBUILD.bat      →  compile UI into backend/static after frontend changes
```

---

## Project Layout

```
ACS/
  backend/
    app.py            FastAPI entrypoint
    routes.py         all API routes
    generation.py     universal image/video/upscale pipeline
    models.py         model scanner + architecture detection
    chat.py           Ollama streaming + auto-summarize
    memory.py         persistent AI memory
    search.py         20+ search integrations
    downloads.py      download catalogue + resumable downloader
    kk_routes.py      thin proxy → KK Bridge (port 7862)
    config.py         paths, config, shared state
    config.example.json  template — copy to config.json
  frontend/
    src/
      pages/          ChatPage, GeneratePage, DownloadsPage, OtherPages
      components/     Sidebar, Topbar, Toasts, FileBrowser
      api.js          typed fetch wrappers
      store/          Zustand global state
  kk/
    server.py         KK Bridge — FastAPI on port 7862
    api/
      brain.py        character emotion engine + personality archetypes
      story.py        SQLite story DB (characters, scenes, dialogue)
      voice.py        edge-tts voice director
      pose.py         pose estimation + preset library
      nlp.py          NLP tagging, sentiment, scene parsing
      world.py        world state, NPC spawning, ambient dialogue
      extra.py        QA, render queue, semantic search, multi-agent, Ren'Py export
    bridge/
      KKAIBridge.cs   BepInEx C# plugin for CharaStudio
  kkbridge/
    KKAIBridge.cs     C# plugin source (standalone build)
    KKAIBridge.csproj
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Blank page at :7860 | Run `REBUILD.bat` to recompile the UI |
| "Ollama is not running" | Start Ollama, then `ollama pull dolphin-mistral` |
| Generation error — missing model | Open Downloads tab, pick a checkpoint |
| CUDA out of memory | Lower resolution or steps; Flux/SD3 offload automatically |
| Wan video model not found | Place `.safetensors` in `backend/models/video/` and rescan |
| KK Bridge offline | `cd kk && python server.py` (or `.\run.ps1`) |

---

## Roadmap

Features planned for future versions:

- **Blender plugin** — AI-assisted 3D model generation, rigging, and timeline animation via a Python addon
- **DaVinci Resolve plugin** — AI color grading suggestions and automated video editing
- **Unity plugin** — AI asset generation and scene composition inside the Unity Editor
- **ComfyUI workflow builder** — visual node editor integration for custom pipeline creation
- **Multi-GPU support** — pipeline sharding across multiple GPUs for large models
- **Real-time collaboration** — shared generation sessions over LAN

---
