"""Описатель картинок (Ollama: Qwen3.5 с vision или JoyCaption). Выгружается из VRAM после ответа."""
import base64, json, time, urllib.request
from ..config import OLLAMA_URL

MODEL_DEFAULT = "qwen3.5:9b"
MODEL_UNCENSORED = "aha2025/llama-joycaption-beta-one-hf-llava:Q8_0"

FOCUS = {
    "all": "Describe this image in detail so it can be recreated as closely as possible: subject, appearance, clothing, pose, setting, composition, camera angle, lighting, colors, style/medium.",
    "style": "Describe ONLY the visual style of this image: medium (photo, painting, 3D, anime...), rendering technique, color grading, texture, lighting style, mood. Do not describe the subject or objects.",
    "composition": "Describe ONLY the composition and pose: framing, camera angle and distance, placement of subjects, body pose and gesture, perspective. Do not describe colors or style.",
    "character": "Describe ONLY the main character's appearance: approximate adult age, face, hair, body type, clothing and accessories. Do not describe the background.",
    "colors": "Describe ONLY the colors and lighting: color palette, dominant and accent colors, light sources, direction, softness, time of day, contrast.",
}


def describe(image_path, focus="all", nsfw=False):
    model = MODEL_UNCENSORED if nsfw else MODEL_DEFAULT
    img = base64.b64encode(open(image_path, "rb").read()).decode()
    payload = {"model": model, "stream": False, "keep_alive": 0, "think": False, "options": {"temperature": 0.3, "num_ctx": 4096},
               "messages": [{"role": "user", "content": FOCUS.get(focus, FOCUS["all"]) + " Answer in English, one compact paragraph, no preamble.",
                             "images": [img]}]}
    t0 = time.time()
    r = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(r, timeout=300).read())
    return {"text": resp["message"]["content"].strip(), "_model": model, "_sec": round(time.time() - t0, 1)}
