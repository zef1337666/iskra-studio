"""Тест движка: генерирует картинку через API ComfyUI и замеряет время."""
import json, time, urllib.request, sys

URL = "http://127.0.0.1:8188"

def req(path, data=None):
    r = urllib.request.Request(URL + path, data=json.dumps(data).encode() if data else None,
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r).read())

for _ in range(120):
    try:
        req("/system_stats"); break
    except Exception:
        time.sleep(1)
else:
    sys.exit("ComfyUI не запустился")

wf = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "_test_sd15.safetensors"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "a red cat sitting on a windowsill, warm evening light, cozy, photo"}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "blurry, lowres"}},
    "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
                                               "seed": 42, "steps": 25, "cfg": 7, "sampler_name": "euler", "scheduler": "normal", "denoise": 1}},
    "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
    "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "test/engine"}},
}
for run in (1, 2):
    wf["5"]["inputs"]["seed"] = 42 + run
    t = time.time()
    pid = req("/prompt", {"prompt": wf})["prompt_id"]
    while True:
        h = req(f"/history/{pid}")
        if pid in h and h[pid].get("status", {}).get("completed"):
            break
        if pid in h and h[pid].get("status", {}).get("status_str") == "error":
            sys.exit(json.dumps(h[pid]["status"], ensure_ascii=False)[:2000])
        time.sleep(0.2)
    img = h[pid]["outputs"]["7"]["images"][0]
    print(f"прогон {run}: {time.time() - t:.1f} c -> {img['subfolder']}/{img['filename']}")
print(req("/system_stats")["devices"][0]["name"])
