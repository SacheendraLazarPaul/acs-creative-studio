# ACS — Creative Studio

A **fully local, standalone AI creative studio**. Chat, generate images, and generate
short videos — all on your own PC. No cloud APIs, no accounts, no data leaving your machine.

> Built by **[Sacheendra Lazar Paul](https://github.com/SacheendraLazarPaul)** — full-stack + AI developer.

---

## Features

### 💬 Chat
- Runs **fully locally** — two free engine options, no API keys:
  - **Built-in engine** (`llama-cpp-python`) — drop a `.gguf` chat model in `backend/models/llm/`, no Ollama needed
  - **Ollama** — auto-started if installed
- Streaming responses, persistent sessions, and **cross-session memory** (remembers facts you tell it)
- Customisable assistant **persona** — name, voice (male/female), and personality
- **Live web search** (free sources) for current weather, news, prices, and more

### 🎨 Image generation
- Generate from chat ("create an image of…") **or** the dedicated Generate page
- **SD 1.5 + SDXL** checkpoints, VAE, **IP-Adapter**, CLIP-Vision, LoRA support
- Native-resolution selection per model, quality presets (Fast / Balanced / High)
- GGUF image models supported via `stable-diffusion.cpp`
- Live progress bar + ETA

### 🎬 Video generation
- **AnimateDiff** — animates an SD 1.5 checkpoint into short clips; runs on low-VRAM GPUs (6 GB)
- Live progress + ETA

### 🔒 Safe by default
- Always-on **SFW prompt filter** blocks explicit prompts across every generation path

### 🎨 UI
- Dark / light theme, clean responsive layout, model management

---

## Tech stack
**Backend:** FastAPI · PyTorch · diffusers · stable-diffusion.cpp · llama-cpp-python
**Frontend:** React · Vite
**Local LLM:** GGUF (built-in) or Ollama

---

## Setup

```bash
# 1. Install dependencies (Python 3.10+ and Node 18+)
install.bat            # installs backend/requirements.txt + builds the frontend

# 2. Add models (all optional, download what you want):
#    - Chat:  drop a .gguf chat model in  backend/models/llm/
#    - Image: drop a .safetensors checkpoint in  backend/models/checkpoints/
#    - Video: the AnimateDiff motion adapter auto-downloads on first use

# 3. Run
ACS.bat               # starts the app at http://localhost:7860
```

Models are **not** included in this repo (they're large and gitignored) — add your own SFW models.

---

## Notes
- Designed and tested on an **NVIDIA RTX 3050 (6 GB)** laptop GPU.
- Video generation is VRAM-heavy; expect short clips and one at a time on 6 GB cards.
- All generation is local; nothing is uploaded anywhere.
