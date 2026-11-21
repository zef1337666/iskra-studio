"""Пути и настройки студии. Секреты — только в .env (никогда не логируются)."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
DATA = ROOT / "data"
OUTPUT = DATA / "output"
INPUT = DATA / "input"
ENV_FILE = ROOT / ".env"
COMFY_URL = "http://127.0.0.1:8188"
OLLAMA_URL = "http://127.0.0.1:11434"
UA = "ai-studio/1.0"

# Тип модели (Civitai/HF) -> папка
TYPE_FOLDERS = {
    "checkpoint": "checkpoints", "diffusion_model": "diffusion_models", "lora": "loras", "locon": "loras", "dora": "loras",
    "vae": "vae", "text_encoder": "text_encoders", "controlnet": "controlnet", "upscaler": "upscale_models",
    "textualinversion": "embeddings", "embedding": "embeddings", "clip_vision": "clip_vision", "detection": "ultralytics/bbox",
    "motionmodule": "animatediff_models", "model_patch": "model_patches",
}
# Базовые модели, у которых «Checkpoint» на Civitai — это только диффузионная часть (без CLIP/VAE)
DIFFUSION_ONLY_BASES = ("flux", "krea", "qwen", "wan", "z-image", "zimage", "anima", "hunyuan", "minimax", "chroma", "ltx", "moss", "hidream")

# Семейства базовых моделей для проверки совместимости LoRA
BASE_FAMILIES = {
    "sdxl": ["sdxl", "pony", "illustrious", "noobai"],
    "sd15": ["sd 1.5", "sd1.5", "sd 1.4"],
    "flux1": ["flux.1", "flux1"],
    "flux2": ["flux.2", "flux2"],
    "flux3": ["flux.3", "flux3", "klein"],
    "krea2": ["krea 2", "krea2"],
    "qwen": ["qwen"],
    "zimage": ["z-image", "zimage"],
    "anima": ["anima"],
    "wan22": ["wan 2.2", "wan2.2", "wan video 2.2"],
    "wan21": ["wan 2.1", "wan2.1", "wan video 14b", "wan video"],
    "h3": ["minimax", "h3"],
}


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    return env


def save_env_key(key, value):
    """Обновляет один ключ в .env, остальное не трогает."""
    lines = ENV_FILE.read_text(encoding="utf-8-sig").splitlines() if ENV_FILE.exists() else []
    out, done = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == key:
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def family_of(base_model: str):
    b = (base_model or "").lower()
    for fam, keys in BASE_FAMILIES.items():
        if any(k in b for k in keys):
            return fam
    return None
