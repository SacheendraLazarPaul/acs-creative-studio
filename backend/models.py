"""
Model scanning — detects local model files, classifies by category/arch/version.
Edit this file to add new folder mappings or architecture detection rules.
"""
import re, platform
from pathlib import Path
from config import MODELS_DIR, config

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".bin", ".gguf", ".pth", ".onnx"}

# ── Arch / quant / variant detection ──────────────────────────────────────
def _detect_model_meta(name: str, full_path: str) -> dict:
    n = name.lower()
    p = full_path.lower().replace("\\", "/")

    # Architecture — header-peek for safetensors, name-based for others
    arch = ""
    if name.endswith(".safetensors"):
        try:
            import struct, json
            with open(full_path, "rb") as f:
                hlen = struct.unpack("<Q", f.read(8))[0]
                keys = set(json.loads(f.read(min(hlen, 2 * 1024 * 1024))).keys()) - {"__metadata__"}
            if any("double_blocks" in k for k in keys):
                arch = "Flux"
            elif any("joint_blocks" in k or "context_embedder" in k for k in keys):
                arch = "SD 3"
            elif any("add_embedding" in k for k in keys):
                arch = "SDXL"
            elif any("input_blocks" in k for k in keys):
                arch = "SD 1.5"
        except Exception:
            pass

    if not arch:
        if any(x in n for x in ["wan21", "wan_21", "wan2.1"]) or ("umt5" in n and "wan" in n):
            arch = "Wan 2.1"
        elif any(x in n for x in ["wan22", "wan_22", "smooth_mix_wan22", "wan2.2"]):
            arch = "Wan 2.2"
        elif "wan" in n and any(x in n for x in ["t2v", "i2v", "1.3b", "14b"]):
            arch = "Wan 2.1"
        elif "ltx" in n:
            arch = "LTX Video"
        elif any(x in n for x in ["flux1", "flux_1", "flux-1"]):
            arch = "Flux"
        elif any(x in n for x in ["sd3", "sd_3", "sd-3"]) and "stable_diffusion" in n:
            arch = "SD 3"
        elif any(x in n for x in ["pony", "illustrious", "animagine_xl"]):
            arch = "Pony XL" if "pony" in n else "Illustrious XL"
        elif any(x in n for x in ["sdxl", "_xl_", "-xl_", "_xl.", "-xl."]) or "/sdxl/" in p:
            arch = "SDXL"
        elif any(x in n for x in ["sd15", "sd1.5", "_sd15", "-sd15", "dreamshaper", "revanimated"]):
            arch = "SD 1.5"
        elif any(x in n for x in ["musicgen", "audiocraft"]):
            arch = "MusicGen"
        elif any(x in n for x in ["bark", "tts", "voicecraft", "xtts"]):
            arch = "TTS"
        elif any(x in n for x in ["esrgan", "realesrgan", "swinir", "hat_"]):
            arch = "Upscaler"

    # Quantization / precision
    quant = ""
    if n.endswith(".gguf") or ".gguf" in n:
        m = re.search(r'(q\d+_k_[msl]|q\d+km|q\d+ks|q\d+k|q\d+_\d+|q\d+)', n, re.IGNORECASE)
        quant = m.group(1).upper().replace("_", " ") if m else "GGUF"
    elif "fp8"  in n: quant = "FP8"
    elif "fp32" in n: quant = "FP32"
    elif "fp16" in n: quant = "FP16"

    # Variant
    variant = ""
    if   any(x in n for x in ["t2v", "t2i2v", "text2vid"]): variant = "Text→Video"
    elif any(x in n for x in ["i2v", "img2vid"]):            variant = "Image→Video"
    elif "faceid"  in n:                                     variant = "Face ID"
    elif "openpose" in n or "pose" in n:                     variant = "OpenPose"
    elif "canny"   in n:                                     variant = "Canny"
    elif "depth"   in n:                                     variant = "Depth"
    elif "kijai"   in n:                                     variant = "Kijai"
    elif "remix"   in n:                                     variant = "Remix"
    elif "plus"    in n and "ipadapter" in p:                variant = "Plus"

    return {"arch": arch, "quant": quant, "variant": variant}


def _file_entry(f: Path) -> dict:
    sz   = f.stat().st_size
    meta = _detect_model_meta(f.name, str(f))
    return {
        "name":     f.name,
        "path":     str(f),
        "size_gb":  round(sz / 1e9, 2),
        "size_mb":  round(sz / 1e6, 1),
        "modified": f.stat().st_mtime,
        "arch":     meta["arch"],
        "quant":    meta["quant"],
        "variant":  meta["variant"],
    }


def _is_usable_model(f: Path) -> bool:
    """Reject incomplete downloads (.part) and empty/corrupt files (< 1 KB)."""
    if f.suffix.lower() == ".part" or f.name.endswith(".part"):
        return False
    try:
        return f.stat().st_size >= 1024
    except Exception:
        return False


# ── Directory scanners ─────────────────────────────────────────────────────
def scan_dir_flat(directory: Path) -> list:
    if not directory.exists():
        return []
    items = []
    try:
        for f in sorted(directory.iterdir()):
            if f.is_file() and f.suffix.lower() in MODEL_EXTENSIONS and _is_usable_model(f):
                try:
                    items.append(_file_entry(f))
                except Exception:
                    pass
    except PermissionError:
        pass
    return items


def scan_dir_recursive(directory: Path, max_depth: int = 3) -> dict:
    groups: dict = {}
    if not directory.exists():
        return groups

    def _walk(d: Path, depth: int):
        if depth > max_depth:
            return
        try:
            files = []
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix.lower() in MODEL_EXTENSIONS and _is_usable_model(f):
                    try:
                        files.append(_file_entry(f))
                    except Exception:
                        pass
                elif f.is_dir():
                    _walk(f, depth + 1)
            if files:
                label = d.name if d != directory else "root"
                groups.setdefault(label, []).extend(files)
        except PermissionError:
            pass

    _walk(directory, 0)
    return groups


# ── ComfyUI auto-discovery ─────────────────────────────────────────────────
def find_comfyui_automatically() -> list:
    candidates = []
    if platform.system() == "Windows":
        import string, ctypes
        drives = []
        try:
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drives.append(f"{letter}:\\")
                bitmask >>= 1
        except Exception:
            drives = ["C:\\", "D:\\", "E:\\"]
    else:
        drives = ["/"]

    folder_names  = ["ComfyUI", "comfyui", "Comfyui", "ComfyUI_windows_portable", "ComfyUI-portable", "comfy"]
    parent_dirs   = ["", "AI", "ai", "stable-diffusion", "StableDiffusion", "SD", "Apps", "tools", "Programs", "software"]

    for drive in drives:
        for parent in parent_dirs:
            for name in folder_names:
                path = Path(drive) / parent / name if parent else Path(drive) / name
                if path.exists() and (path / "models").exists():
                    candidates.append(str(path))
    try:
        home = Path.home()
        for name in folder_names:
            for p in [home / name, home / "Desktop" / name]:
                if p.exists() and (p / "models").exists():
                    candidates.append(str(p))
    except Exception:
        pass
    return list(dict.fromkeys(candidates))


def get_all_scan_bases() -> list:
    bases = [MODELS_DIR]
    seen  = {str(MODELS_DIR)}

    comfyui = config.get("comfyui_dir", "").strip()
    if comfyui:
        for candidate in [Path(comfyui) / "models", Path(comfyui)]:
            if candidate.exists() and str(candidate) not in seen:
                bases.append(candidate)
                seen.add(str(candidate))
                break

    custom = config.get("custom_models_dir", "").strip()
    if custom and Path(custom).exists() and custom not in seen:
        bases.append(Path(custom))
        seen.add(custom)

    for d in config.get("extra_scan_dirs", []):
        d = str(d).strip()
        if d and Path(d).exists() and d not in seen:
            bases.append(Path(d))
            seen.add(d)
    return bases


# ── Folder name → category mapping (ComfyUI-compatible) ───────────────────
FOLDER_MAP = {
    "checkpoints": "checkpoints", "checkpoint": "checkpoints",
    "unet": "checkpoints",        "diffusion_models": "checkpoints",
    "loras": "loras",             "lora": "loras",
    "vae": "vae",                 "vae_approx": "vae",
    "text_encoders": "text_encoders", "text_encoder": "text_encoders",
    "clip": "text_encoders",      "clips": "text_encoders", "t5": "text_encoders",
    "controlnet": "controlnet",   "control_net": "controlnet",
    "upscale_models": "upscalers","upscalers": "upscalers",
    "upscaler": "upscalers",      "esrgan": "upscalers",    "swinir": "upscalers",
    "video_models": "video",      "video": "video",      "wan": "video",
    "ipadapter": "ipadapter",     "ip_adapter": "ipadapter", "ip-adapter": "ipadapter",
    "embeddings": "embeddings",   "textual_inversion": "embeddings",
    "hypernetworks": "hypernetworks",
    "clip_vision": "clip_vision", "style_models": "style_models",
    "gligen": "gligen",           "photomaker": "ipadapter", "instantid": "ipadapter",
    "audio": "audio",             "music": "audio",       "musicgen": "audio",
    "tts": "tts",                 "speech": "tts",        "voice": "tts",
    "3d": "3d_models",            "triposr": "3d_models",
}

TASK_LABELS = {
    "checkpoints":   "Image Generation",
    "loras":         "Style / Fine-tune",
    "vae":           "Color Encoder",
    "text_encoders": "Text Encoder",
    "controlnet":    "Structure Control",
    "ipadapter":     "Face / Style Ref",
    "clip_vision":   "Vision Encoder",
    "video":         "Video Generation",
    "embeddings":    "Prompt Helper",
    "upscalers":     "Upscale",
    "hypernetworks": "Hypernetwork",
    "style_models":  "Style",
    "gligen":        "Spatial Control",
    "audio":         "Audio / Music",
    "tts":           "Text to Speech",
    "3d_models":     "3D Generation",
}


# ── Main scan ──────────────────────────────────────────────────────────────
def scan_models() -> dict:
    result: dict = {
        "checkpoints": [], "loras": {}, "vae": [], "text_encoders": [],
        "controlnet": [], "upscalers": [], "ipadapter": [], "video": [],
        "embeddings": [], "hypernetworks": [], "clip_vision": [],
        "style_models": [], "gligen": [], "audio": [], "tts": [],
        "3d_models": [], "other": [],
    }
    seen_paths: set = set()

    def add(key: str, entry: dict, group: str = None):
        path = entry["path"]
        if path in seen_paths:
            return
        seen_paths.add(path)
        if key == "loras":
            result["loras"].setdefault(group or "root", []).append(entry)
        elif key in result and isinstance(result[key], list):
            result[key].append(entry)
        else:
            result.setdefault(key, [])
            if isinstance(result[key], list):
                result[key].append(entry)

    for base in get_all_scan_bases():
        if not base.exists():
            continue
        try:
            subdirs = [d for d in base.iterdir() if d.is_dir()]
        except PermissionError:
            continue

        for subdir in subdirs:
            folder_name = subdir.name.lower().replace("-", "_").replace(" ", "_")
            key = FOLDER_MAP.get(folder_name)

            if key == "loras":
                for grp, items in scan_dir_recursive(subdir).items():
                    for item in items:
                        add("loras", item, grp)
            elif key:
                for f in scan_dir_flat(subdir):
                    add(key, f)
                try:
                    for sub2 in subdir.iterdir():
                        if sub2.is_dir():
                            for f in scan_dir_flat(sub2):
                                add(key, f)
                except Exception:
                    pass
            else:
                for f in scan_dir_flat(subdir):
                    add("other", f)

        # Root-level files in base dir
        for f in scan_dir_flat(base):
            nl = f["name"].lower()
            if   any(x in nl for x in ["lora", "lyco", "loha"]):            add("loras", f, "root")
            elif any(x in nl for x in ["vae", "ae.safetensors"]):           add("vae", f)
            elif any(x in nl for x in ["clip", "t5", "llama"]):             add("text_encoders", f)
            elif any(x in nl for x in ["unet", "diffusion_model"]):         add("checkpoints", f)
            else:                                                            add("checkpoints", f)

    if not result.get("other"):
        result.pop("other", None)

    # Attach task label to every entry
    for cat, label in TASK_LABELS.items():
        entries = result.get(cat, [])
        if isinstance(entries, list):
            for e in entries:
                e["task"] = label
        elif isinstance(entries, dict):
            for grp in entries.values():
                for e in grp:
                    e["task"] = label

    result["_summary"] = {
        k: len(v) if isinstance(v, list) else sum(len(x) for x in v.values())
        for k, v in result.items() if not k.startswith("_")
    }
    return result
