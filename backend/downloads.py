"""
Download catalogue and download engine.
Edit DOWNLOADABLE_MODELS to add/remove models from the catalog.
"""
import threading, time, requests
from pathlib import Path
from config import config, state, save_config

# ── Catalogue ──────────────────────────────────────────────────────────────
DOWNLOADABLE_MODELS = [

    # ── CHECKPOINTS ────────────────────────────────────────────────────────
    {"id":"sd15","name":"Stable Diffusion 1.5","description":"The classic baseline. Fast, lightweight, huge community support.","size":"~4.3 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors","filename":"v1-5-pruned-emaonly.safetensors"}],"requires_hf_token":False},
    {"id":"sd15-inpainting","name":"SD 1.5 Inpainting","description":"Official SD 1.5 fine-tuned for inpainting tasks. Required for the Inpaint mode.","size":"~4.3 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/runwayml/stable-diffusion-inpainting/resolve/main/sd-v1-5-inpainting.ckpt","filename":"sd-v1-5-inpainting.ckpt"}],"requires_hf_token":False},
    {"id":"sdxl-base","name":"SDXL 1.0 Base","description":"Stable Diffusion XL — higher resolution, better composition, richer detail.","size":"~6.9 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors","filename":"sd_xl_base_1.0.safetensors"}],"requires_hf_token":False},
    {"id":"sdxl-turbo","name":"SDXL Turbo (1-step)","description":"Ultra-fast SDXL — high quality in just 1–4 steps.","size":"~6.9 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors","filename":"sd_xl_turbo_1.0_fp16.safetensors"}],"requires_hf_token":False},
    {"id":"dreamshaper-xl","name":"DreamShaper XL","description":"Most popular SDXL fine-tune. Beautiful photorealistic and artistic images.","size":"~6.7 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/Lykon/dreamshaper-xl-turbo/resolve/main/DreamShaperXL_Turbo_dpmppSDE.safetensors","filename":"DreamShaperXL_Turbo_dpmppSDE.safetensors"}],"requires_hf_token":False},
    {"id":"realistic-vision","name":"Realistic Vision v6 (SD15)","description":"Best-in-class photorealistic portrait and scene generation for SD 1.5.","size":"~2.1 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/SG161222/Realistic_Vision_V6.0_B1_noVAE/resolve/main/Realistic_Vision_V6.0_NV_B1.safetensors","filename":"Realistic_Vision_V6.0_NV_B1.safetensors"}],"requires_hf_token":False},
    {"id":"anything-v5","name":"Anything V5 (Anime SD15)","description":"Top anime/illustration model. Clean lines, rich colors, consistent style.","size":"~2.1 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/stablediffusionapi/anything-v5/resolve/main/AnythingV5Ink_ink.safetensors","filename":"AnythingV5Ink_ink.safetensors"}],"requires_hf_token":False},
    {"id":"counterfeit-v3","name":"Counterfeit V3 (Anime SD15)","description":"High quality anime illustration model. Excellent for character art.","size":"~2.0 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/gsdf/Counterfeit-V3.0/resolve/main/Counterfeit-V3.0_fp16.safetensors","filename":"Counterfeit-V3.0_fp16.safetensors"}],"requires_hf_token":False},
    {"id":"juggernaut-xl","name":"Juggernaut XL v9","description":"Extremely photorealistic SDXL model. Great for portraits, fashion, architecture.","size":"~6.8 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors","filename":"Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"}],"requires_hf_token":False},
    {"id":"pony-xl","name":"Pony Diffusion XL v6","description":"Best SDXL model for anime, cartoon, and illustration styles.","size":"~6.9 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/AingIndian/Pony-Diffusion-V6-XL/resolve/main/ponyDiffusionV6XL_v6StartWithThisOne.safetensors","filename":"ponyDiffusionV6XL_v6.safetensors"}],"requires_hf_token":False},
    {"id":"dreamshaper8","name":"DreamShaper 8 (SD1.5, pruned)","description":"Most popular all-rounder SD 1.5 model. ~2GB pruned FP16.","size":"~2.0 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/Lykon/DreamShaper/resolve/main/DreamShaper_8_pruned.safetensors","filename":"DreamShaper_8_pruned.safetensors"}],"requires_hf_token":False},
    {"id":"waifu-diffusion-v14","name":"Waifu Diffusion v1.4 (SD1.5 anime)","description":"Classic anime/illustration SD 1.5 model. ~2GB, fast.","size":"~2.0 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/hakurei/waifu-diffusion-v1-4/resolve/main/wd-1-4-anime_e2.ckpt","filename":"wd-1-4-anime_e2.ckpt"}],"requires_hf_token":False},
    {"id":"deliberate-v6","name":"Deliberate v6 (SD1.5, photorealism)","description":"Razor-sharp photorealism on SD 1.5. ~2GB pruned.","size":"~2.0 GB","category":"checkpoints","save_dir":"models/checkpoints","files":[{"url":"https://huggingface.co/XpucT/Deliberate/resolve/main/Deliberate_v6.safetensors","filename":"Deliberate_v6.safetensors"}],"requires_hf_token":False},

    # ── VAE ────────────────────────────────────────────────────────────────
    {"id":"vae-sd15","name":"VAE SD 1.5 (ft-mse)","description":"Best VAE for SD 1.5 — fixes washed-out colors, improves fine detail.","size":"~335 MB","category":"vae","save_dir":"models/vae","files":[{"url":"https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors","filename":"vae-ft-mse-840000-ema-pruned.safetensors"}],"requires_hf_token":False},
    {"id":"vae-sdxl","name":"VAE SDXL (fp16)","description":"Official SDXL VAE. Required for proper colors with SDXL models.","size":"~335 MB","category":"vae","save_dir":"models/vae","files":[{"url":"https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors","filename":"sdxl_vae.safetensors"}],"requires_hf_token":False},
    {"id":"vae-animevae","name":"Anime VAE (kl-f8)","description":"Specialized VAE for anime models. Richer saturation and cleaner lines.","size":"~335 MB","category":"vae","save_dir":"models/vae","files":[{"url":"https://huggingface.co/hakurei/waifu-diffusion-v1-4/resolve/main/vae/kl-f8-anime2.ckpt","filename":"kl-f8-anime2.ckpt"}],"requires_hf_token":False},

    # ── LORAS ──────────────────────────────────────────────────────────────
    {"id":"lora-add-detail","name":"LoRA: Add Detail (SD15)","description":"Adds fine skin texture, hair detail, and overall sharpness. Use at 0.5–1.0.","size":"~144 MB","category":"loras","save_dir":"models/loras","files":[{"url":"https://huggingface.co/philz1337x/detail-tweaker-lora/resolve/main/add_detail.safetensors","filename":"add_detail.safetensors"}],"requires_hf_token":False},
    {"id":"lora-film-grain","name":"LoRA: Film Grain (SD15)","description":"Adds cinematic film grain, analog look, and vintage photography aesthetic.","size":"~18 MB","category":"loras","save_dir":"models/loras","files":[{"url":"https://huggingface.co/CiroN2022/toy-face/resolve/main/toy_face_sdv15.safetensors","filename":"film_grain.safetensors"}],"requires_hf_token":False},
    {"id":"lora-epi-noise","name":"LoRA: Epi Noise Offset (SD15)","description":"Dramatically improves dark scenes and contrast.","size":"~73 KB","category":"loras","save_dir":"models/loras","files":[{"url":"https://huggingface.co/epinikion/epiNoiseoffset_v2/resolve/main/epinoiseoffset_v2.safetensors","filename":"epinoiseoffset_v2.safetensors"}],"requires_hf_token":False},
    {"id":"lora-xl-detail","name":"LoRA: SDXL Detail Enhancer","description":"Sharpness and fine-detail enhancer for SDXL models. Use at 0.3–0.7.","size":"~24 MB","category":"loras","save_dir":"models/loras","files":[{"url":"https://huggingface.co/KappaNeuro/studio-ghibli-style/resolve/main/Studio%20Ghibli%20Style.safetensors","filename":"sdxl_detail_enhancer.safetensors"}],"requires_hf_token":False},

    # ── CONTROLNET ─────────────────────────────────────────────────────────
    {"id":"controlnet-openpose","name":"ControlNet OpenPose (SD15)","description":"Precise body pose control using skeleton keypoints.","size":"~1.5 GB","category":"controlnet","save_dir":"models/controlnet","files":[{"url":"https://huggingface.co/lllyasviel/ControlNet/resolve/main/models/control_sd15_openpose.pth","filename":"control_sd15_openpose.pth"}],"requires_hf_token":False},
    {"id":"controlnet-canny","name":"ControlNet Canny (SD15)","description":"Edge-based structural control. Preserves lines and outlines from reference images.","size":"~1.5 GB","category":"controlnet","save_dir":"models/controlnet","files":[{"url":"https://huggingface.co/lllyasviel/ControlNet/resolve/main/models/control_sd15_canny.pth","filename":"control_sd15_canny.pth"}],"requires_hf_token":False},
    {"id":"controlnet-depth","name":"ControlNet Depth (SD15)","description":"3D depth-based layout control. Preserves scene composition.","size":"~1.5 GB","category":"controlnet","save_dir":"models/controlnet","files":[{"url":"https://huggingface.co/lllyasviel/ControlNet/resolve/main/models/control_sd15_depth.pth","filename":"control_sd15_depth.pth"}],"requires_hf_token":False},
    {"id":"controlnet-openpose-sdxl","name":"ControlNet OpenPose (SDXL)","description":"Body pose control for SDXL models.","size":"~2.4 GB","category":"controlnet","save_dir":"models/controlnet","files":[{"url":"https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors","filename":"controlnet-openpose-sdxl.safetensors"}],"requires_hf_token":False},
    {"id":"controlnet-canny-sdxl","name":"ControlNet Canny (SDXL)","description":"Edge/line control for SDXL. Maintains structural precision.","size":"~2.4 GB","category":"controlnet","save_dir":"models/controlnet","files":[{"url":"https://huggingface.co/xinsir/controlnet-canny-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors","filename":"controlnet-canny-sdxl.safetensors"}],"requires_hf_token":False},

    # ── IP-ADAPTER ─────────────────────────────────────────────────────────
    {"id":"ip-adapter-face","name":"IP-Adapter FaceID (SD15)","description":"Lock a specific face across generated images.","size":"~92 MB","category":"ipadapter","save_dir":"models/ipadapter/ip-adapter-face","files":[{"url":"https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid_sd15.bin","filename":"ip-adapter-faceid_sd15.bin"}],"requires_hf_token":False},
    {"id":"ip-adapter-plus","name":"IP-Adapter Plus (SD15)","description":"Style and character consistency from a reference image.","size":"~94 MB","category":"ipadapter","save_dir":"models/ipadapter/ip-adapter-plus","files":[{"url":"https://huggingface.co/h94/IP-Adapter/resolve/main/models/ip-adapter-plus_sd15.safetensors","filename":"ip-adapter-plus_sd15.safetensors"}],"requires_hf_token":False},
    {"id":"ip-adapter-sdxl","name":"IP-Adapter (SDXL)","description":"Reference-image style transfer for SDXL models.","size":"~800 MB","category":"ipadapter","save_dir":"models/ipadapter","files":[{"url":"https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter_sdxl.safetensors","filename":"ip-adapter_sdxl.safetensors"}],"requires_hf_token":False},
    {"id":"ip-adapter-faceid-sdxl","name":"IP-Adapter FaceID (SDXL)","description":"Face consistency for SDXL — high resolution face locking.","size":"~430 MB","category":"ipadapter","save_dir":"models/ipadapter","files":[{"url":"https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid_sdxl.bin","filename":"ip-adapter-faceid_sdxl.bin"}],"requires_hf_token":False},

    # ── UPSCALERS ──────────────────────────────────────────────────────────
    {"id":"upscale-4x-ultra","name":"4x UltraSharp Upscaler","description":"Best general upscaler. Adds realistic detail at 4x resolution.","size":"~67 MB","category":"upscale_models","save_dir":"models/upscale_models","files":[{"url":"https://huggingface.co/Kim2091/UltraSharp/resolve/main/4x-UltraSharp.pth","filename":"4x-UltraSharp.pth"}],"requires_hf_token":False},
    {"id":"upscale-4x-animeultra","name":"4x AnimeUltraV2 Upscaler","description":"Specialized 4x upscaler for anime/illustration.","size":"~67 MB","category":"upscale_models","save_dir":"models/upscale_models","files":[{"url":"https://huggingface.co/Akumetsu971/SD_Anime_Futuristic_Armor/resolve/main/4x_AnimeSharp.pth","filename":"4x_AnimeSharp.pth"}],"requires_hf_token":False},
    {"id":"upscale-realesrgan","name":"RealESRGAN x4+ (Photo)","description":"NVIDIA real-world photo upscaler. Handles noise, compression, and blur.","size":"~67 MB","category":"upscale_models","save_dir":"models/upscale_models","files":[{"url":"https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth","filename":"RealESRGAN_x4plus.pth"}],"requires_hf_token":False},

    # ── EMBEDDINGS ─────────────────────────────────────────────────────────
    {"id":"embedding-easyneg","name":"EasyNegative (SD15)","description":"Most popular negative embedding. Add 'easynegative' to negative prompt.","size":"~25 KB","category":"embeddings","save_dir":"models/embeddings","files":[{"url":"https://huggingface.co/datasets/gsdf/EasyNegative/resolve/main/EasyNegative.safetensors","filename":"EasyNegative.safetensors"}],"requires_hf_token":False},
    {"id":"embedding-badhandv4","name":"Bad Hands V4 (SD15)","description":"Fixes the classic AI hand problem. Add 'badhandv4' to negative prompt.","size":"~7 KB","category":"embeddings","save_dir":"models/embeddings","files":[{"url":"https://huggingface.co/yesyeahvh/bad-hands-5/resolve/main/bad-hands-5.pt","filename":"bad-hands-5.pt"}],"requires_hf_token":False},
    {"id":"embedding-ng-deepneg","name":"Deep Negative V1 (SD15)","description":"Reduces artifacts and anatomical errors. Use in negative prompt.","size":"~8 KB","category":"embeddings","save_dir":"models/embeddings","files":[{"url":"https://huggingface.co/datasets/Nerfgun3/bad_prompt/resolve/main/bad_prompt_version2.pt","filename":"deep_negative_v1.pt"}],"requires_hf_token":False},

    # ── VIDEO ──────────────────────────────────────────────────────────────
    {"id":"ltx-video","name":"LTX-Video (Text/Image to Video)","description":"Fast open-source video generation. Supports T2V and I2V.","size":"~4.4 GB","category":"video","save_dir":"models/video","files":[{"url":"https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.safetensors","filename":"ltx-video-2b-v0.9.safetensors"}],"requires_hf_token":False},

    # ── WAN 2.1 GGUF (HuggingFace, city96 repo) ───────────────────────────
    {"id":"wan21-t2v-1b-q4","name":"Wan 2.1 T2V 1.3B Q4_K_M (GGUF)","description":"Wan 2.1 Text-to-Video tiny model — ~800MB, runs in 6GB VRAM.","size":"~800 MB","category":"video","save_dir":"models/video","files":[{"url":"https://huggingface.co/city96/Wan2.1-T2V-1.3B-gguf/resolve/main/Wan2.1-T2V-1.3B-Q4_K_M.gguf","filename":"Wan2.1-T2V-1.3B-Q4_K_M.gguf"}],"requires_hf_token":False},
    {"id":"wan21-t2v-1b-q8","name":"Wan 2.1 T2V 1.3B Q8_0 (GGUF)","description":"Wan 2.1 T2V 1.3B Q8 — ~1.4GB, better quality than Q4.","size":"~1.4 GB","category":"video","save_dir":"models/video","files":[{"url":"https://huggingface.co/city96/Wan2.1-T2V-1.3B-gguf/resolve/main/Wan2.1-T2V-1.3B-Q8_0.gguf","filename":"Wan2.1-T2V-1.3B-Q8_0.gguf"}],"requires_hf_token":False},
    {"id":"wan21-t2v-14b-q3","name":"Wan 2.1 T2V 14B Q3_K_M (GGUF)","description":"Wan 2.1 T2V 14B — ~5.6GB with CPU offload for 6GB VRAM.","size":"~5.6 GB","category":"video","save_dir":"models/video","files":[{"url":"https://huggingface.co/city96/Wan2.1-T2V-14B-gguf/resolve/main/Wan2.1-T2V-14B-Q3_K_M.gguf","filename":"Wan2.1-T2V-14B-Q3_K_M.gguf"}],"requires_hf_token":False},
    {"id":"wan21-i2v-14b-480p-q3","name":"Wan 2.1 I2V 14B 480P Q3_K_M (GGUF)","description":"Wan 2.1 Image-to-Video 14B 480P — ~5.6GB. Animate any photo.","size":"~5.6 GB","category":"video","save_dir":"models/video","files":[{"url":"https://huggingface.co/city96/Wan2.1-I2V-14B-480P-gguf/resolve/main/Wan2.1-I2V-14B-480P-Q3_K_M.gguf","filename":"Wan2.1-I2V-14B-480P-Q3_K_M.gguf"}],"requires_hf_token":False},

    # ── WAN 2.2 GGUF (CivitAI community fine-tunes) ───────────────────────
    {"id":"wan22-smooth-t2v","name":"Smooth Mix Wan 2.2 T2V (GGUF)","description":"Community fine-tune of Wan 2.2 T2V — smoother, more cinematic.","size":"~5–9 GB","category":"video","save_dir":"models/video","files":[{"url":"https://civitai.com/api/download/models/2357542","filename":"smooth_mix_wan22_t2v.gguf"}],"requires_hf_token":False,"requires_civitai_token":True},
    {"id":"wan22-smooth-i2v","name":"Smooth Mix Wan 2.2 I2V v2.0 (GGUF)","description":"Community fine-tune of Wan 2.2 I2V v2.0 — smooth image-to-video.","size":"~5–9 GB","category":"video","save_dir":"models/video","files":[{"url":"https://civitai.com/api/download/models/2593810","filename":"smooth_mix_wan22_i2v_v2.gguf"}],"requires_hf_token":False,"requires_civitai_token":True},
    {"id":"wan22-remix-t2v","name":"Wan 2.2 Remix T2V v2.0 (GGUF)","description":"Remix T2V v2.0 — enhanced Wan 2.2 T2V with better prompt following.","size":"~5–9 GB","category":"video","save_dir":"models/video","files":[{"url":"https://civitai.com/api/download/models/2520055","filename":"wan22_remix_t2v_v2.gguf"}],"requires_hf_token":False,"requires_civitai_token":True},
    {"id":"wan22-remix-i2v","name":"Wan 2.2 Remix I2V v3.0 (GGUF)","description":"Remix I2V v3.0 — best community I2V fine-tune.","size":"~5–9 GB","category":"video","save_dir":"models/video","files":[{"url":"https://civitai.com/api/download/models/2780181","filename":"wan22_remix_i2v_v3.gguf"}],"requires_hf_token":False,"requires_civitai_token":True},
]


# ── Download engine ────────────────────────────────────────────────────────
def _download_file_with_progress(url: str, dest_path: Path, model_id: str,
                                  file_index: int, total_files: int,
                                  hf_token: str, stop_evt, pause_evt):
    headers = {"User-Agent": "AI-Creative-Studio/3.0"}
    if "civitai.com" in url:
        ctok = config.get("civitai_token", "") or ""
        if ctok:
            headers["Authorization"] = f"Bearer {ctok}"
    elif hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path   = dest_path.with_suffix(dest_path.suffix + ".part")
    resume_pos = tmp_path.stat().st_size if tmp_path.exists() else 0
    if resume_pos > 0:
        headers["Range"] = f"bytes={resume_pos}-"

    try:
        resp  = requests.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True)
        total = int(resp.headers.get("Content-Length", 0)) + resume_pos
        state["download_status"][model_id].update({
            "total_bytes": total, "filename": dest_path.name,
            "file_index": file_index, "total_files": total_files,
        })
        downloaded    = resume_pos
        speed_samples = []
        t_start       = time.time()
        last_bytes    = downloaded

        with open(tmp_path, "ab" if resume_pos > 0 else "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if stop_evt.is_set():
                    raise InterruptedError("cancelled")
                while pause_evt.is_set():
                    state["download_status"][model_id]["status"] = "paused"
                    time.sleep(0.5)
                    if stop_evt.is_set():
                        raise InterruptedError("cancelled")
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    now     = time.time()
                    elapsed = now - t_start
                    if elapsed >= 1.0:
                        speed = (downloaded - last_bytes) / elapsed
                        speed_samples.append(speed)
                        if len(speed_samples) > 5:
                            speed_samples.pop(0)
                        avg_speed = sum(speed_samples) / len(speed_samples)
                        remaining = (total - downloaded) / avg_speed if avg_speed > 0 else 0
                        progress  = int(downloaded / total * 100) if total > 0 else 0
                        state["download_status"][model_id].update({
                            "status": "downloading", "downloaded_bytes": downloaded,
                            "speed_bps": int(avg_speed), "eta_sec": int(remaining), "progress": progress,
                        })
                        t_start    = now
                        last_bytes = downloaded

        tmp_path.rename(dest_path)
        state["download_status"][model_id].update({"downloaded_bytes": downloaded, "progress": 100})

    except InterruptedError:
        raise
    except Exception as e:
        raise RuntimeError(f"Download failed: {e}")


def _run_download(model_id: str):
    model = next((m for m in DOWNLOADABLE_MODELS if m["id"] == model_id), None)
    if not model:
        return
    ctrl      = state["download_threads"].get(model_id, {})
    stop_evt  = ctrl.get("stop_event",  threading.Event())
    pause_evt = ctrl.get("pause_event", threading.Event())
    hf_token  = config.get("hf_token", "") or ""
    try:
        state["download_status"][model_id] = {
            "status": "downloading", "progress": 0, "downloaded_bytes": 0,
            "total_bytes": 0, "speed_bps": 0, "eta_sec": 0,
            "filename": "", "file_index": 0, "total_files": len(model["files"]), "error": "",
        }
        save_dir = Path(model["save_dir"])
        for i, file_info in enumerate(model["files"]):
            if stop_evt.is_set():
                break
            dest = save_dir / file_info["filename"]
            if dest.exists():
                continue
            _download_file_with_progress(
                file_info["url"], dest, model_id, i + 1, len(model["files"]),
                hf_token, stop_evt, pause_evt,
            )
        if not stop_evt.is_set():
            dl = config.get("downloaded_models", [])
            if model_id not in dl:
                dl.append(model_id)
            config["downloaded_models"] = dl
            save_config(config)
            state["download_status"][model_id]["status"] = "done"

    except InterruptedError:
        state["download_status"][model_id]["status"] = "cancelled"
    except Exception as e:
        state["download_status"][model_id].update({"status": "error", "error": str(e)})
    finally:
        state["download_threads"].pop(model_id, None)
