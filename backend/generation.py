"""
Image and video generation pipelines.
Supports: SD 1.5, SD 2.x, SDXL, SD3, Flux, Wan, LTX-Video, ComfyUI, Upscale.
Auto-detects model architecture from safetensors header — no config needed.
"""
import base64, json, struct, time, requests
from pathlib import Path
from typing import Optional, List, Any
from pydantic import BaseModel
from config import config, state, OUTPUT_DIR
from models import scan_models

_MAX_CACHED_PIPES = 2
_pipeline_cache: dict = {}


# ── Request model ──────────────────────────────────────────────────────────
class GenRequest(BaseModel):
    prompt:               str
    negative:             str   = "bad quality, blurry, deformed, ugly, watermark, low resolution"
    model:                str   = ""
    mode:                 str   = "t2i"
    width:                int   = 832
    height:               int   = 1216
    steps:                int   = 20
    cfg:                  float = 7.0
    strength:             float = 0.75
    seed:                 int   = -1
    loras:                List[Any] = []
    ref_image:            Optional[str] = None
    ref_video:            Optional[str] = None
    mask_image:           Optional[str] = None
    consistency_mode:     str   = "none"
    num_frames:           int   = 25
    fps:                  int   = 8
    video_model:          Optional[str] = None
    controlnet:           Optional[str] = None
    controlnet_image:     Optional[str] = None
    controlnet_strength:  float = 1.0
    upscale_factor:       int   = 4
    hires_fix:            bool  = False
    hires_scale:          float = 1.5
    hires_strength:       float = 0.5
    scheduler:            str   = ""
    vae_path:             str   = ""
    clip_skip:            int   = 1
    seamless:             bool  = False
    outpaint_px:          int   = 64


# ── Small helpers ──────────────────────────────────────────────────────────
def _b64_to_pil(b64_str: str):
    import io
    from PIL import Image
    if "," in b64_str:
        b64_str = b64_str.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(b64_str))).convert("RGB")


def _write_sidecar(stem: str, seed: int, req: GenRequest):
    try:
        meta = {
            "prompt": req.prompt, "negative": req.negative,
            "model": req.model or "", "mode": req.mode,
            "seed": seed, "steps": req.steps, "cfg": req.cfg,
            "width": req.width, "height": req.height,
            "timestamp": time.time(),
        }
        (OUTPUT_DIR / (stem + ".json")).write_text(json.dumps(meta), encoding="utf-8")
    except Exception:
        pass


def _save_image(img, seed: int, mode: str, req: GenRequest = None):
    import io
    ts    = int(time.time())
    fname = f"{mode}_{ts}_{seed}.png"
    stem  = f"{mode}_{ts}_{seed}"
    img.save(str(OUTPUT_DIR / fname))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    if req:
        _write_sidecar(stem, seed, req)
    state.update({"gen_status": "idle", "gen_progress": 100, "gen_log": "Done!"})
    return {"image": base64.b64encode(buf.getvalue()).decode(), "seed": seed, "filename": fname, "mode": mode}


def _save_video(frames, seed: int, fps: int, mode: str, req: GenRequest = None):
    import numpy as np, imageio
    ts    = int(time.time())
    fname = f"{mode}_{ts}_{seed}.mp4"
    stem  = f"{mode}_{ts}_{seed}"
    fpath = str(OUTPUT_DIR / fname)
    frames_u8 = []
    for f in frames:
        arr = np.array(f)
        frames_u8.append((arr * 255).astype("uint8") if arr.max() <= 1.0 else arr.astype("uint8"))
    imageio.mimsave(fpath, frames_u8, fps=fps)
    with open(fpath, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    if req:
        _write_sidecar(stem, seed, req)
    state.update({"gen_status": "idle", "gen_progress": 100, "gen_log": "Video ready!"})
    return {"video": b64, "seed": seed, "filename": fname, "mode": mode}


def _step_cb(total: int):
    def cb(pipe, step_index, timestep, callback_kwargs):
        pct = 20 + int((step_index + 1) / total * 78)
        state.update({"gen_progress": pct, "gen_log": f"Step {step_index + 1}/{total} — {pct}%"})
        return callback_kwargs
    return cb


# ── Pipeline cache (max 2 entries) ────────────────────────────────────────
def _cache_put(key: str, pipe):
    if len(_pipeline_cache) >= _MAX_CACHED_PIPES:
        oldest = next(iter(_pipeline_cache))
        del _pipeline_cache[oldest]
    _pipeline_cache[key] = pipe


# ── Architecture detection ─────────────────────────────────────────────────
def _detect_arch(model_path: str) -> str:
    """Inspect safetensors header (no GPU, no full load) to detect architecture."""
    p = Path(model_path)
    if not p.exists():
        return "unknown"
    if p.suffix == ".gguf":
        return "gguf"
    name = p.name.lower()
    if p.suffix == ".safetensors":
        try:
            with open(p, "rb") as f:
                hlen = struct.unpack("<Q", f.read(8))[0]
                header = json.loads(f.read(min(hlen, 3 * 1024 * 1024)))
            keys = set(header.keys()) - {"__metadata__"}
            meta = header.get("__metadata__", {})
            # Flux: uses double_blocks (Flux transformer architecture)
            if any("double_blocks" in k for k in keys):
                return "flux"
            # SD3 / SD3.5: uses joint_blocks or joint transformer
            if any("joint_blocks" in k or "context_embedder" in k for k in keys):
                return "sd3"
            # SDXL: add_embedding + mid_block (time conditioning)
            if any("add_embedding" in k for k in keys):
                return "sdxl"
            # Auraflow
            if any("single_transformer_blocks" in k for k in keys):
                return "auraflow"
            # SD1.5 / SD2: input_blocks / output_blocks
            if any("input_blocks" in k for k in keys):
                return "sd15"
        except Exception:
            pass
    # Name-based fallback
    if any(x in name for x in ["flux1", "flux_1", "flux-1", "-flux.", "_flux."]):
        return "flux"
    if any(x in name for x in ["sd3", "sd_3", "sd-3", "stable_diffusion_3"]):
        return "sd3"
    if any(x in name for x in ["sdxl", "_xl_", "-xl_", "xl_base", "xl_refiner",
                                 "pony", "illustrious", "animagine_xl", "waifu_diffusion_xl"]):
        return "sdxl"
    if p.stat().st_size > 5.5e9:  # >5.5GB → almost certainly SDXL
        return "sdxl"
    return "sd15"


# ── Universal pipeline loader ──────────────────────────────────────────────
def _load_universal_pipe(mode: str, model_path: str, device, dtype,
                         loras=None, controlnet_path: str = None):
    """Load any image model by auto-detecting architecture from file header."""
    import torch
    if not (model_path and Path(model_path).exists()):
        model_path = _auto_find_checkpoint()
    if not model_path:
        return "No checkpoint found — download a model from the Models tab first."

    arch = _detect_arch(model_path)
    cache_key = f"{mode}:{model_path}:{arch}:{controlnet_path or ''}"
    if cache_key in _pipeline_cache:
        return _pipeline_cache[cache_key]

    state["gen_log"] = f"Loading {arch.upper()} model…"

    try:
        if arch == "flux":
            from diffusers import FluxPipeline, FluxImg2ImgPipeline
            cls = FluxImg2ImgPipeline if mode == "i2i" else FluxPipeline
            pipe = cls.from_single_file(model_path, torch_dtype=torch.bfloat16)
            pipe.enable_model_cpu_offload()

        elif arch == "sd3":
            from diffusers import (StableDiffusion3Pipeline,
                                   StableDiffusion3Img2ImgPipeline)
            cls = StableDiffusion3Img2ImgPipeline if mode == "i2i" else StableDiffusion3Pipeline
            pipe = cls.from_single_file(model_path, torch_dtype=dtype)
            pipe.enable_model_cpu_offload()

        elif arch == "sdxl":
            from diffusers import (StableDiffusionXLPipeline,
                                   StableDiffusionXLImg2ImgPipeline,
                                   StableDiffusionXLInpaintPipeline,
                                   StableDiffusionXLControlNetPipeline,
                                   ControlNetModel)
            if controlnet_path and Path(controlnet_path).exists():
                cn = ControlNetModel.from_single_file(controlnet_path, torch_dtype=dtype)
                pipe = StableDiffusionXLControlNetPipeline.from_single_file(
                    model_path, controlnet=cn, torch_dtype=dtype)
            else:
                cls_map = {"t2i": StableDiffusionXLPipeline,
                           "i2i": StableDiffusionXLImg2ImgPipeline,
                           "inpaint": StableDiffusionXLInpaintPipeline}
                pipe = cls_map.get(mode, StableDiffusionXLPipeline).from_single_file(
                    model_path, torch_dtype=dtype)
            pipe.enable_model_cpu_offload()

        else:  # sd15, unknown — use AutoPipeline then fall back to explicit SD1.5
            try:
                from diffusers import (AutoPipelineForText2Image,
                                       AutoPipelineForImage2Image,
                                       AutoPipelineForInpainting)
                auto = {"t2i": AutoPipelineForText2Image,
                        "i2i": AutoPipelineForImage2Image,
                        "inpaint": AutoPipelineForInpainting}
                if controlnet_path and Path(controlnet_path).exists():
                    from diffusers import (StableDiffusionControlNetPipeline,
                                           StableDiffusionControlNetImg2ImgPipeline,
                                           ControlNetModel)
                    cn  = ControlNetModel.from_single_file(controlnet_path, torch_dtype=dtype)
                    cls = (StableDiffusionControlNetImg2ImgPipeline if mode == "i2i"
                           else StableDiffusionControlNetPipeline)
                    pipe = cls.from_single_file(model_path, controlnet=cn,
                                                torch_dtype=dtype, safety_checker=None)
                else:
                    pipe = auto.get(mode, AutoPipelineForText2Image).from_single_file(
                        model_path, torch_dtype=dtype, safety_checker=None)
            except Exception:
                from diffusers import (StableDiffusionPipeline,
                                       StableDiffusionImg2ImgPipeline,
                                       StableDiffusionInpaintPipeline)
                cls = {"t2i": StableDiffusionPipeline,
                       "i2i": StableDiffusionImg2ImgPipeline,
                       "inpaint": StableDiffusionInpaintPipeline}.get(mode, StableDiffusionPipeline)
                pipe = cls.from_single_file(model_path, torch_dtype=dtype, safety_checker=None)
            pipe = pipe.to(device)

    except Exception as e:
        return f"Failed to load model ({arch}): {e}"

    # Optimizations
    for opt in ("enable_attention_slicing", "enable_vae_tiling"):
        try: getattr(pipe, opt)()
        except Exception: pass
    try: pipe.enable_xformers_memory_efficient_attention()
    except Exception: pass

    # LoRAs
    if loras:
        for lora in loras:
            lp = lora.get("path", "")
            if Path(lp).exists():
                try:
                    pipe.load_lora_weights(lp)
                    if "scale" in lora:
                        pipe.fuse_lora(lora_scale=float(lora["scale"]))
                except Exception:
                    pass

    _cache_put(cache_key, (pipe, arch))
    return pipe, arch


# ── Model finders ──────────────────────────────────────────────────────────
def _find_wan_components():
    m   = scan_models()
    te  = next((x["path"] for x in m.get("text_encoders", [])
                if "wan" in x["name"].lower() or "umt5" in x["name"].lower()), None)
    vae = next((x["path"] for x in m.get("vae", [])
                if "wan" in x["name"].lower()), None)
    clp = next((x["path"] for x in m.get("clip_vision", [])
                if "wan" in x["name"].lower() or "clip" in x["name"].lower()), None)
    return te, vae, clp


def _auto_find_checkpoint() -> str:
    m   = scan_models()
    cps = m.get("checkpoints", [])
    return cps[0]["path"] if cps else ""


# Native resolutions per architecture — generating far above these on SD1.5
# causes the "doubled/repeated" artifact, so we match the model's sweet spot.
_NATIVE_RES = {"sd15": (512, 768), "sd2": (768, 768), "sdxl": (1024, 1024),
               "flux": (1024, 1024), "sd3": (1024, 1024), "auraflow": (1024, 1024)}

def smart_gen_request(prompt: str, mode: str = "t2i") -> "GenRequest":
    """Build a quality-tuned request for chat-driven generation: correct
    resolution for the model, a VAE if available, hi-res fix for SD1.5."""
    model = _auto_find_checkpoint() or ""
    arch  = _detect_arch(model) if model else "sd15"
    if mode in ("t2v", "i2v"):
        return GenRequest(prompt=prompt, mode="t2v", width=512, height=320,
                          steps=25, num_frames=25, fps=8)
    w, h = _NATIVE_RES.get(arch, (512, 768))
    vae = ""
    try:
        vaes = scan_models().get("vae", [])
        if arch in ("sd15", "sd2") and vaes:
            vae = vaes[0]["path"]
    except Exception:
        pass
    return GenRequest(
        prompt=prompt, model=model, mode="t2i",
        width=w, height=h, steps=26, cfg=6.5,
        hires_fix=False,  # native-res already fixes the SD1.5 "doubling"; hi-res is too slow on low VRAM
        vae_path=vae,
        negative="lowres, bad anatomy, bad hands, text, error, missing fingers, "
                 "extra digit, fewer digits, cropped, worst quality, low quality, "
                 "jpeg artifacts, signature, watermark, blurry, duplicate, deformed",
    )


def _detect_video_model_type(model_path: str) -> str:
    if not model_path:
        return "ltx"
    p    = Path(model_path)
    name = p.name.lower()
    if p.suffix == ".gguf":
        return "wan_gguf"
    if any(k in name for k in ("wan", "smooth_mix", "t2v", "i2v")):
        return "wan_safetensors"
    if "ltx" in name:
        return "ltx"
    return "unknown"


# ── SD pipeline loader ─────────────────────────────────────────────────────
def _load_sd_pipe(mode: str, model_path: str, device, dtype, loras=None, controlnet_path: str = None):
    from diffusers import (
        StableDiffusionPipeline, StableDiffusionImg2ImgPipeline,
        StableDiffusionInpaintPipeline,
        StableDiffusionControlNetPipeline, StableDiffusionControlNetImg2ImgPipeline,
        ControlNetModel,
    )
    if not (model_path and Path(model_path).exists()):
        model_path = _auto_find_checkpoint()

    cache_key = f"{mode}:{model_path}:{controlnet_path or ''}"
    if cache_key in _pipeline_cache:
        return _pipeline_cache[cache_key]

    if controlnet_path and Path(controlnet_path).exists():
        cn_model = ControlNetModel.from_single_file(controlnet_path, torch_dtype=dtype)
        cn_cls   = (StableDiffusionControlNetImg2ImgPipeline if mode == "i2i"
                    else StableDiffusionControlNetPipeline)
        if model_path and Path(model_path).exists():
            pipe = cn_cls.from_single_file(model_path, controlnet=cn_model,
                                           torch_dtype=dtype, safety_checker=None)
        else:
            pipe = cn_cls.from_pretrained("runwayml/stable-diffusion-v1-5",
                                          controlnet=cn_model, torch_dtype=dtype, safety_checker=None)
    else:
        cls_map = {
            "t2i":    StableDiffusionPipeline,
            "i2i":    StableDiffusionImg2ImgPipeline,
            "inpaint": StableDiffusionInpaintPipeline,
        }
        cls = cls_map.get(mode, StableDiffusionPipeline)
        if model_path and Path(model_path).exists():
            pipe = cls.from_single_file(model_path, torch_dtype=dtype, safety_checker=None)
        else:
            return "No checkpoint found. Download DreamShaper 8 or any SD model from the Models tab first."

    pipe = pipe.to(device)
    pipe.enable_attention_slicing()
    try:
        pipe.enable_xformers_memory_efficient_attention()
    except Exception:
        pass
    if loras:
        for lora in loras:
            lp = lora.get("path", "")
            if Path(lp).exists():
                try:
                    pipe.load_lora_weights(lp)
                    if "scale" in lora:
                        pipe.fuse_lora(lora_scale=float(lora["scale"]))
                except Exception:
                    pass

    _cache_put(cache_key, pipe)
    return pipe


def _apply_consistency(pipe, req: GenRequest, device, dtype):
    """Load IP-adapter weights onto pipe and return the image to inject, or None."""
    if req.consistency_mode == "none" or not req.ref_image:
        return None
    try:
        if "face" in req.consistency_mode:
            ipad_dir = Path("models/ipadapter/ip-adapter-face")
            wname    = "ip-adapter-faceid_sd15.bin"
            scale    = 0.8
        else:
            ipad_dir = Path("models/ipadapter/ip-adapter-plus")
            wname    = "ip-adapter-plus_sd15.safetensors"
            scale    = 0.6
        if not (ipad_dir / wname).exists():
            return None
        pipe.load_ip_adapter(str(ipad_dir), subfolder="", weight_name=wname)
        pipe.set_ip_adapter_scale(scale)
        return _b64_to_pil(req.ref_image)
    except Exception:
        return None


# ── Wan pipeline loader ────────────────────────────────────────────────────
def _load_wan_pipe(mode: str, model_path: str, device, dtype):
    cache_key = f"wan:{mode}:{model_path}"
    if cache_key in _pipeline_cache:
        return _pipeline_cache[cache_key]

    from diffusers import WanPipeline, WanImageToVideoPipeline
    from diffusers.models import WanTransformer3DModel, AutoencoderKLWan

    _, vae_path, _ = _find_wan_components()
    base_id = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"

    state["gen_log"] = "Loading Wan transformer…"
    transformer = WanTransformer3DModel.from_single_file(model_path, torch_dtype=dtype)

    state["gen_log"] = "Loading VAE…"
    if vae_path and Path(vae_path).exists():
        vae = AutoencoderKLWan.from_single_file(vae_path, torch_dtype=dtype)
    else:
        vae = AutoencoderKLWan.from_pretrained(base_id, subfolder="vae", torch_dtype=dtype)

    state["gen_log"] = "Assembling Wan pipeline…"
    PipeClass = WanImageToVideoPipeline if mode == "i2v" else WanPipeline
    pipe = PipeClass.from_pretrained(
        base_id, transformer=transformer, vae=vae,
        torch_dtype=dtype, low_cpu_mem_usage=True,
    )
    pipe.enable_model_cpu_offload()
    _cache_put(cache_key, pipe)
    return pipe


# ── ComfyUI helpers ────────────────────────────────────────────────────────
def get_comfyui_url() -> str:
    return config.get("comfyui_url", "http://localhost:8188").rstrip("/")


def _build_t2i_workflow(prompt, negative, model_name, width, height, steps, cfg, seed):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model_name}},
        "2": {"class_type": "CLIPTextEncode",   "inputs": {"text": prompt,   "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",   "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": ["4", 0], "seed": seed, "steps": steps,
            "cfg": cfg, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
        }},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "ACS"}},
    }


def _comfyui_dispatch(workflow: dict, comfy_url: str, seed: int) -> dict:
    """Send workflow to ComfyUI, poll for result, and return image dict."""
    try:
        r         = requests.post(f"{comfy_url}/prompt", json={"prompt": workflow}, timeout=15)
        prompt_id = r.json().get("prompt_id")
        if not prompt_id:
            return {"error": f"ComfyUI rejected workflow: {r.text[:300]}"}
    except Exception as e:
        return {"error": f"Cannot reach ComfyUI at {comfy_url}. Is it running? ({e})"}

    for _ in range(120):
        time.sleep(1)
        try:
            hist = requests.get(f"{comfy_url}/history/{prompt_id}", timeout=5).json()
            if prompt_id in hist:
                for node_out in hist[prompt_id].get("outputs", {}).values():
                    for img_info in node_out.get("images", []):
                        img_r = requests.get(f"{comfy_url}/view", params={
                            "filename": img_info["filename"],
                            "subfolder": img_info.get("subfolder", ""),
                            "type": img_info.get("type", "output"),
                        }, timeout=15)
                        fname = f"comfyui_{int(time.time())}_{seed}.png"
                        (OUTPUT_DIR / fname).write_bytes(img_r.content)
                        b64 = base64.b64encode(img_r.content).decode()
                        return {"image": b64, "seed": seed, "filename": fname, "mode": "comfyui_t2i"}
        except Exception:
            continue
    return {"error": "ComfyUI generation timed out after 120s."}


# ── GGUF image generation via stable-diffusion.cpp ────────────────────────
def _generate_sdcpp(req: GenRequest, seed: int) -> dict:
    try:
        from stable_diffusion_cpp import StableDiffusion
    except ImportError:
        return {"error": "stable-diffusion-cpp-python not installed. Run: pip install stable-diffusion-cpp-python"}

    from PIL import Image as PILImage
    import numpy as np

    state.update({"gen_log": "Loading GGUF model…", "gen_progress": 8})
    try:
        sd = StableDiffusion(model_path=req.model, wtype="default", verbose=False)
    except Exception as e:
        return {"error": f"Failed to load GGUF model: {e}"}

    state.update({"gen_log": "Generating (GGUF)…", "gen_progress": 25})
    try:
        if req.mode == "t2i":
            imgs = sd.txt_to_img(
                prompt=req.prompt, negative_prompt=req.negative,
                width=req.width, height=req.height,
                sample_steps=req.steps, cfg_scale=req.cfg, seed=seed,
            )
        elif req.mode in ("i2i", "inpaint") and req.ref_image:
            ref = _b64_to_pil(req.ref_image).resize((req.width, req.height))
            mask_arr = None
            if req.mode == "inpaint" and req.mask_image:
                mask_arr = np.array(_b64_to_pil(req.mask_image).resize((req.width, req.height)).convert("L"))
            imgs = sd.img_to_img(
                image=ref, mask=mask_arr,
                prompt=req.prompt, negative_prompt=req.negative,
                width=req.width, height=req.height,
                sample_steps=req.steps, cfg_scale=req.cfg,
                strength=req.strength, seed=seed,
            )
        else:
            return {"error": f"Mode '{req.mode}' not supported for GGUF models"}
    except Exception as e:
        return {"error": f"GGUF generation error: {e}"}

    img = imgs[0] if isinstance(imgs, (list, tuple)) else imgs
    if not isinstance(img, PILImage.Image):
        img = PILImage.fromarray(np.array(img).astype("uint8"))

    # optional hires fix
    if req.hires_fix and req.mode == "t2i":
        state.update({"gen_log": "Hires fix (GGUF i2i)…", "gen_progress": 75})
        hw = int(req.width * req.hires_scale)
        hh = int(req.height * req.hires_scale)
        upscaled = img.resize((hw, hh), PILImage.LANCZOS)
        try:
            hi = sd.img_to_img(
                image=upscaled, prompt=req.prompt, negative_prompt=req.negative,
                width=hw, height=hh, sample_steps=max(req.steps // 2, 8),
                cfg_scale=req.cfg, strength=req.hires_strength, seed=seed,
            )
            img = hi[0] if isinstance(hi, (list, tuple)) else hi
            if not isinstance(img, PILImage.Image):
                img = PILImage.fromarray(np.array(img).astype("uint8"))
        except Exception:
            img = upscaled  # fallback: just the upscaled version

    return _save_image(img, seed, req.mode, req)


# ── Wildcard expansion ──────────────────────────────────────────────────────
import re as _re
def _expand_wildcards(text: str) -> str:
    import random
    def _pick(m):
        opts = [o.strip() for o in m.group(1).split("|")]
        return random.choice(opts) if opts else ""
    return _re.sub(r'\{([^}]+)\}', _pick, text)


# ── Scheduler / VAE / seamless helpers ────────────────────────────────────
def _apply_scheduler(pipe, name: str):
    if not name or not hasattr(pipe, "scheduler"):
        return
    try:
        import diffusers
        karras = name.endswith("_karras")
        base   = name.replace("_karras", "")
        cls_map = {
            "euler_a":  "EulerAncestralDiscreteScheduler",
            "euler":    "EulerDiscreteScheduler",
            "dpm++_2m": "DPMSolverMultistepScheduler",
            "dpm++_sde":"DPMSolverSinglestepScheduler",
            "ddim":     "DDIMScheduler",
            "pndm":     "PNDMScheduler",
            "lms":      "LMSDiscreteScheduler",
            "heun":     "HeunDiscreteScheduler",
            "unipc":    "UniPCMultistepScheduler",
            "lcm":      "LCMScheduler",
            "deis":     "DEISMultistepScheduler",
            "kdpm2_a":  "KDPM2AncestralDiscreteScheduler",
            "kdpm2":    "KDPM2DiscreteScheduler",
        }
        cls_name = cls_map.get(base)
        if not cls_name:
            return
        cls = getattr(diffusers, cls_name)
        cfg = dict(pipe.scheduler.config)
        if karras:
            cfg["use_karras_sigmas"] = True
        pipe.scheduler = cls.from_config(cfg)
    except Exception:
        pass


def _apply_vae(pipe, vae_path: str, dtype):
    if not vae_path or not Path(vae_path).exists():
        return
    try:
        from diffusers import AutoencoderKL
        vae = AutoencoderKL.from_single_file(vae_path, torch_dtype=dtype)
        device = next(pipe.parameters()).device if hasattr(pipe, "parameters") else "cpu"
        pipe.vae = vae.to(device)
    except Exception:
        pass


def _enable_seamless(pipe):
    import torch
    for attr in ("unet", "vae", "transformer"):
        module = getattr(pipe, attr, None)
        if module is None:
            continue
        for m in module.modules():
            if isinstance(m, (torch.nn.Conv2d, torch.nn.ConvTranspose2d)):
                m.padding_mode = "circular"


def _outpaint_prep(ref_b64: str, px: int):
    """Pad image edges by px pixels and return (padded_b64, mask_b64)."""
    import io, base64
    from PIL import Image, ImageFilter
    img = _b64_to_pil(ref_b64)
    w, h = img.size
    nw, nh = w + px * 2, h + px * 2

    # Reflect-pad edges
    canvas = Image.new("RGB", (nw, nh))
    canvas.paste(img, (px, px))
    canvas.paste(img.crop((0, 0, w, min(px, h))).transpose(Image.FLIP_TOP_BOTTOM), (px, 0))
    canvas.paste(img.crop((0, max(0, h - px), w, h)).transpose(Image.FLIP_TOP_BOTTOM), (px, px + h))
    canvas.paste(img.crop((0, 0, min(px, w), h)).transpose(Image.FLIP_LEFT_RIGHT), (0, px))
    canvas.paste(img.crop((max(0, w - px), 0, w, h)).transpose(Image.FLIP_LEFT_RIGHT), (px + w, px))

    # Mask: white = repaint (padded border), black = keep (original centre)
    mask = Image.new("L", (nw, nh), 255)
    feather = max(4, px // 4)
    inner_w, inner_h = max(1, w - feather * 2), max(1, h - feather * 2)
    mask.paste(Image.new("L", (inner_w, inner_h), 0), (px + feather, px + feather))
    mask = mask.filter(ImageFilter.GaussianBlur(feather))

    def enc(im):
        buf = io.BytesIO(); im.save(buf, "PNG"); return base64.b64encode(buf.getvalue()).decode()

    return enc(canvas), enc(mask), nw, nh


# ── Main generate() ────────────────────────────────────────────────────────
def generate(req: GenRequest) -> dict:
    req = req.model_copy(update={
        "prompt":   _expand_wildcards(req.prompt),
        "negative": _expand_wildcards(req.negative),
    })
    state.update({"gen_status": "generating", "gen_progress": 0,
                  "gen_log": f"Starting {req.mode.upper()}..."})
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype  = torch.float16 if device == "cuda" else torch.float32
        seed   = req.seed if req.seed >= 0 else int(time.time()) % (2 ** 31)
        gen    = torch.Generator(device=device).manual_seed(seed)

        effective_model = req.model or ""
        if req.mode in ("t2v", "i2v", "t2i2v") and req.video_model:
            effective_model = req.video_model

        # Route GGUF image models to stable-diffusion.cpp
        if req.mode in ("t2i", "i2i", "inpaint") and effective_model.endswith(".gguf"):
            return _generate_sdcpp(req.model_copy(update={"model": effective_model}), seed)

        if req.mode in ("t2i", "i2i", "inpaint"):
            cn_path = req.controlnet if req.controlnet and Path(req.controlnet).exists() else None
            state.update({"gen_log": "Loading model…", "gen_progress": 5})
            result = _load_universal_pipe(req.mode, effective_model, device, dtype,
                                          req.loras, cn_path)
            if isinstance(result, str):
                return {"error": result}
            pipe, arch = result
            _apply_vae(pipe, req.vae_path, dtype)
            _apply_scheduler(pipe, req.scheduler)
            if req.seamless:
                _enable_seamless(pipe)
            ip_img = _apply_consistency(pipe, req, device, dtype)
            state.update({"gen_log": f"Generating ({arch.upper()})…", "gen_progress": 20})

            kw = dict(num_inference_steps=req.steps, generator=gen,
                      callback_on_step_end=_step_cb(req.steps))
            if ip_img is not None:
                kw["ip_adapter_image"] = ip_img
            if req.clip_skip > 1 and arch not in ("flux", "sd3"):
                kw["clip_skip"] = req.clip_skip

            if arch == "flux":
                kw.update(prompt=req.prompt, width=req.width, height=req.height,
                          num_inference_steps=max(req.steps, 4), guidance_scale=req.cfg)
                if req.mode == "i2i" and req.ref_image:
                    kw["image"] = _b64_to_pil(req.ref_image).resize((req.width, req.height))
                    kw["strength"] = req.strength
                kw.pop("callback_on_step_end", None)
            elif arch == "sd3":
                kw.update(prompt=req.prompt, negative_prompt=req.negative,
                          width=req.width, height=req.height, guidance_scale=req.cfg)
                if req.mode == "i2i" and req.ref_image:
                    kw["image"] = _b64_to_pil(req.ref_image).resize((req.width, req.height))
                    kw["strength"] = req.strength
                kw.pop("callback_on_step_end", None)
            elif req.mode == "inpaint":
                if not req.ref_image or not req.mask_image:
                    return {"error": "ref_image and mask_image required for inpaint"}
                ref  = _b64_to_pil(req.ref_image).resize((req.width, req.height))
                mask = _b64_to_pil(req.mask_image).resize((req.width, req.height)).convert("L")
                kw.update(prompt=req.prompt, negative_prompt=req.negative,
                          image=ref, mask_image=mask, guidance_scale=req.cfg)
            elif req.mode == "i2i":
                if not req.ref_image:
                    return {"error": "ref_image required for i2i"}
                ref = _b64_to_pil(req.ref_image).resize((req.width, req.height))
                kw.update(prompt=req.prompt, negative_prompt=req.negative,
                          image=ref, strength=req.strength, guidance_scale=req.cfg)
                if cn_path and req.controlnet_image:
                    kw["control_image"] = _b64_to_pil(req.controlnet_image).resize((req.width, req.height))
                    kw["controlnet_conditioning_scale"] = float(req.controlnet_strength)
            else:  # t2i
                kw.update(prompt=req.prompt, negative_prompt=req.negative,
                          width=req.width, height=req.height, guidance_scale=req.cfg)
                if cn_path and req.controlnet_image:
                    kw["image"] = _b64_to_pil(req.controlnet_image).resize((req.width, req.height))
                    kw["controlnet_conditioning_scale"] = float(req.controlnet_strength)

            out = pipe(**kw)
            img = out.images[0]

            # Hires fix: upscale then i2i at lower strength
            if req.hires_fix and req.mode == "t2i" and arch not in ("flux", "sd3"):
                state.update({"gen_log": "Hires fix…", "gen_progress": 75})
                hw = int(req.width * req.hires_scale)
                hh = int(req.height * req.hires_scale)
                from diffusers import StableDiffusionImg2ImgPipeline, StableDiffusionXLImg2ImgPipeline
                RefClass = StableDiffusionXLImg2ImgPipeline if arch == "sdxl" else StableDiffusionImg2ImgPipeline
                try:
                    hi_pipe = RefClass.from_pipe(pipe)
                    hi_pipe.to(device)
                    hi_out = hi_pipe(
                        prompt=req.prompt, negative_prompt=req.negative,
                        image=img.resize((hw, hh)), strength=req.hires_strength,
                        num_inference_steps=max(req.steps // 2, 8),
                        guidance_scale=req.cfg, generator=gen,
                    )
                    img = hi_out.images[0]
                except Exception:
                    from PIL import Image as PILImage
                    img = img.resize((hw, hh), PILImage.LANCZOS)

            return _save_image(img, seed, req.mode, req)

        elif req.mode == "outpaint":
            if not req.ref_image:
                return {"error": "ref_image required for outpaint"}
            state.update({"gen_log": "Preparing canvas…", "gen_progress": 5})
            px = max(16, min(req.outpaint_px, 512))
            padded_b64, mask_b64, ow, oh = _outpaint_prep(req.ref_image, px)
            cn_path = req.controlnet if req.controlnet and Path(req.controlnet).exists() else None
            result2 = _load_universal_pipe("inpaint", effective_model, device, dtype, req.loras, cn_path)
            if isinstance(result2, str):
                return {"error": result2}
            pipe2, arch2 = result2
            _apply_vae(pipe2, req.vae_path, dtype)
            _apply_scheduler(pipe2, req.scheduler)
            if req.seamless:
                _enable_seamless(pipe2)
            state.update({"gen_log": "Outpainting…", "gen_progress": 20})
            ref2  = _b64_to_pil(padded_b64).resize((ow, oh))
            mask2 = _b64_to_pil(mask_b64).resize((ow, oh)).convert("L")
            kw2   = dict(prompt=req.prompt, negative_prompt=req.negative,
                         image=ref2, mask_image=mask2, guidance_scale=req.cfg,
                         num_inference_steps=req.steps, generator=gen,
                         callback_on_step_end=_step_cb(req.steps))
            if req.clip_skip > 1 and arch2 not in ("flux", "sd3"):
                kw2["clip_skip"] = req.clip_skip
            out2 = pipe2(**kw2)
            return _save_image(out2.images[0], seed, "outpaint", req)

        elif req.mode == "upscale":
            if not req.ref_image:
                return {"error": "ref_image required for upscale"}
            state.update({"gen_log": "Upscaling…", "gen_progress": 10})
            src = _b64_to_pil(req.ref_image)
            factor = max(2, min(8, req.upscale_factor))

            # Try Real-ESRGAN first (best quality)
            upscaler_path = next(
                (x["path"] for x in scan_models().get("upscalers", [])
                 if Path(x["path"]).exists()),
                None
            )
            try:
                from basicsr.archs.rrdbnet_arch import RRDBNet
                from realesrgan import RealESRGANer
                import numpy as np
                model_id  = 0 if "x2" in (upscaler_path or "") else 1
                net       = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                                    num_block=23, num_grow_ch=32, scale=4)
                upsampler = RealESRGANer(scale=4, model_path=upscaler_path,
                                         model=net, tile=512, tile_pad=32,
                                         pre_pad=0, half=(device == "cuda"))
                out_arr, _ = upsampler.enhance(np.array(src), outscale=factor)
                from PIL import Image as PILImage
                result_img = PILImage.fromarray(out_arr)
                state.update({"gen_log": "Upscale done!", "gen_progress": 100})
                return _save_image(result_img, seed, "upscale", req)
            except ImportError:
                pass
            except Exception as e:
                state["gen_log"] = f"ESRGAN failed ({e}), using high-quality resize…"

            # Fallback: PIL LANCZOS (no dependencies, always works)
            new_w = src.width  * factor
            new_h = src.height * factor
            from PIL import Image as PILImage
            result_img = src.resize((new_w, new_h), PILImage.LANCZOS)
            state.update({"gen_log": "Upscale done (LANCZOS)!", "gen_progress": 100})
            return _save_image(result_img, seed, "upscale", req)

        elif req.mode in ("t2v", "i2v", "t2i2v"):
            vtype = _detect_video_model_type(effective_model)

            if vtype == "wan_gguf":
                return {"error": (
                    "GGUF video models aren't supported by the built-in engine. "
                    "Use a .safetensors Wan or LTX video model instead."
                )}

            elif vtype in ("wan_safetensors", "unknown") and effective_model and Path(effective_model).exists():
                try:
                    pipe = _load_wan_pipe(req.mode, effective_model, device, dtype)
                    state.update({"gen_log": "Generating video…", "gen_progress": 30})
                    if req.mode == "i2v" and req.ref_image:
                        ref = _b64_to_pil(req.ref_image).resize((req.width, req.height))
                        out = pipe(
                            prompt=req.prompt, negative_prompt=req.negative,
                            image=ref, num_frames=req.num_frames,
                            guidance_scale=req.cfg, generator=gen,
                        )
                    else:
                        out = pipe(
                            prompt=req.prompt, negative_prompt=req.negative,
                            num_frames=req.num_frames, width=req.width, height=req.height,
                            guidance_scale=req.cfg, generator=gen,
                        )
                    return _save_video(out.frames[0], seed, req.fps, req.mode, req)
                except Exception as e:
                    return {"error": f"Wan generation failed: {e}"}

            else:
                state["gen_log"] = "Loading LTX-Video..."
                try:
                    from diffusers import LTXPipeline, LTXImageToVideoPipeline
                    if req.mode in ("i2v", "t2i2v") and req.ref_image:
                        pipe = LTXImageToVideoPipeline.from_pretrained(
                            "Lightricks/LTX-Video", torch_dtype=dtype).to(device)
                        ref  = _b64_to_pil(req.ref_image).resize((req.width, req.height))
                        state.update({"gen_log": "Animating...", "gen_progress": 30})
                        out  = pipe(prompt=req.prompt, negative_prompt=req.negative, image=ref,
                                    num_frames=req.num_frames, guidance_scale=req.cfg, generator=gen)
                    else:
                        pipe = LTXPipeline.from_pretrained(
                            "Lightricks/LTX-Video", torch_dtype=dtype).to(device)
                        state.update({"gen_log": "Generating video...", "gen_progress": 30})
                        out  = pipe(prompt=req.prompt, negative_prompt=req.negative,
                                    num_frames=req.num_frames, width=req.width, height=req.height,
                                    guidance_scale=req.cfg, generator=gen)
                    return _save_video(out.frames[0], seed, req.fps, req.mode, req)
                except Exception as e:
                    return {"error": f"LTX-Video error: {e}. Download it from Downloads tab first."}

        else:
            return {"error": f"Unknown mode: {req.mode}"}

    except Exception as e:
        state.update({"gen_status": "error", "gen_log": f"Error: {e}"})
        return {"error": str(e)}
    finally:
        if state["gen_status"] != "idle":
            state.update({"gen_status": "idle", "gen_progress": 100})
