"""Экспорт workflow: API-формат (из конструктора, с примерами параметров) и UI-формат (официальные шаблоны для ручной работы)."""
import json, pathlib, shutil, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio.engine.workflows import REGISTRY  # noqa

SAMPLES = {
    "klein_t2i": {"prompt": "A ginger cat on a windowsill at golden hour", "seed": 42},
    "klein_edit": {"prompt": "Make it a rainy night", "images": ["input.png"], "seed": 1},
    "klein_outpaint": {"images": ["input.png"], "src_w": 1024, "src_h": 1024, "left": 256, "right": 256, "seed": 1},
    "detailer": {"images": ["input.png"], "seed": 1},
    "anima_t2i": {"prompt": "masterpiece, best quality, score_7, safe, 1girl, rain, umbrella", "seed": 1},
    "krea2_t2i": {"prompt": "A cozy coffee shop, watercolor", "loras": [["krea2_softwatercolor.safetensors", 1.0]], "seed": 1},
    "sdxl_t2i": {"model": "One obsession_V25 Retro.safetensors", "prompt": "masterpiece, best quality, 1woman, adult", "seed": 1},
    "upscale": {"images": ["input.png"], "seed": 1},
    "remove_bg": {"images": ["input.png"]},
    "wan22_video": {"images": ["first.png"], "prompt": "The cat turns its head", "seconds": 5, "seed": 1},
    "h3_video": {"images": ["first.png"], "prompt": "The cat yawns", "seconds": 4, "seed": 1},
    "video_enhance": {"videos": ["input.mp4"], "fps": 16, "seed": 1},
    "video_audio": {"videos": ["input.mp4"], "prompt": "cat purring", "duration": 5, "fps": 16, "seed": 1},
    "image_to_3d": {"images": ["input.png"], "seed": 1},
    "zimage_control": {"images": ["pose.png"], "control": "pose", "prompt": "A man in a denim jacket", "seed": 1},
}
api_dir = ROOT / "workflows" / "api"
api_dir.mkdir(parents=True, exist_ok=True)
for name, fn in REGISTRY.items():
    for mode in ("draft", "quality"):
        try:
            g = fn(dict(SAMPLES.get(name, {})), mode)
            (api_dir / f"{name}.{mode}.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            print("!", name, mode, e)
T = ROOT / "venv/Lib/site-packages/comfyui_workflow_templates_json/templates"
ui_dir = ROOT / "workflows" / "ui"
ui_dir.mkdir(parents=True, exist_ok=True)
for t in ["image_flux3_klein_distilled_t2i", "image_flux3_klein_distilled_image_edit", "image_anima_base_v1", "image_krea2_turbo_t2i",
          "utility_seedvr2_3b_int8_upscale_image", "utility_birefnet_remove_background", "video_wan2_2_14B_i2v", "video_wan2_2_14B_flf2v",
          "utility_video_frame_interpolation", "utility_seedvr2_3b_int8_upscale_video", "3d_pixal3d_trellis2_image_to_model",
          "image_z_image_turbo_fun_union_controlnet", "video_minimax_h3_i2v", "video_minimax_h3_t2v"]:
    if (T / f"{t}.json").exists():
        shutil.copy(T / f"{t}.json", ui_dir / f"{t}.json")
print("API:", len(list(api_dir.glob("*.json"))), "UI:", len(list(ui_dir.glob("*.json"))))
