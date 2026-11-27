"""Запуск официального улучшателя промптов FLUX.3 в ComfyUI и получение текста (синхронно)."""
import json, time, urllib.request
from ..config import COMFY_URL, MODELS
from ..engine.workflows import klein_upsample, KLEIN_UPSAMPLER


def available():
    return (MODELS / "text_encoders" / KLEIN_UPSAMPLER).exists()


def _post(path, data):
    r = urllib.request.Request(COMFY_URL + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=30).read())


def run(text, aspect=None, images=None, seed=0, timeout=240):
    graph = klein_upsample({"prompt": text, "aspect": aspect, "images": images or [], "seed": seed})
    pid = _post("/prompt", {"prompt": graph, "client_id": "iskra-upsampler"})["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = json.loads(urllib.request.urlopen(f"{COMFY_URL}/history/{pid}", timeout=30).read()).get(pid)
        if h and h.get("status", {}).get("completed"):
            for out in h.get("outputs", {}).values():
                txt = out.get("text")
                if txt:
                    return {"prompt": (txt[0] if isinstance(txt, list) else txt).strip(), "_sec": round(time.time() - t0, 1), "_model": "BFL upsampler"}
            raise RuntimeError("улучшатель не вернул текст")
        if h and h.get("status", {}).get("status_str") == "error":
            raise RuntimeError("ошибка улучшателя")
        time.sleep(0.5)
    raise TimeoutError("улучшатель не ответил вовремя")
