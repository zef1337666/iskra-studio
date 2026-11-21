"""Стресс-тест: 20 задач разных типов подряд через API студии, без перезапуска. Контроль ошибок, VRAM/ОЗУ до и после."""
import json, sys, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:7860"


def call(m, p, b=None):
    r = urllib.request.Request(B + p, data=json.dumps(b).encode() if b is not None else None, method=m, headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(r, timeout=180).read())
    except urllib.error.HTTPError as e:
        return {"_err": e.code, "detail": e.read().decode("utf-8", "replace")[:200]}


src = next(i for i in call("GET", "/api/items?limit=60&kind=image") if i["preset"] == "photo-real")
S = lambda **k: {"mode": "draft", "aspect": "1:1", "count": 1, **k}
TASKS = [
    S(preset="photo-real", prompt="A lighthouse on a cliff during a storm, dramatic waves"),
    S(preset="anime", prompt="masterpiece, best quality, score_7, safe, 1girl, solo, knight armor, castle, sunset"),
    S(preset="watercolor", prompt="A fox sleeping in autumn leaves"),
    S(preset="photo-real", prompt="Macro photo of a dewdrop on a green leaf", mode="quality"),
    S(preset="upscale", source_item=src["id"]),
    S(preset="nobg", source_item=src["id"]),
    S(preset="edit", source_item=src["id"], prompt="Make it snowy winter outside the window"),
    S(preset="dark-brush", prompt="An old wizard reading a glowing book"),
    S(preset="retro-anime", prompt="A girl riding a motorcycle through a neon city at night"),
    S(preset="photo-real", prompt="A cozy cabin interior with fireplace, warm light", aspect="16:9"),
    S(preset="detail", source_item=src["id"]),
    S(preset="outpaint", source_item=src["id"], left=256, right=256),
    S(preset="anime", prompt="masterpiece, best quality, score_7, safe, 1boy, solo, samurai, cherry blossoms", mode="quality"),
    S(preset="illustration", prompt="Poster of a futuristic train station"),
    S(preset="pose", source_item=src["id"], prompt="A small dog sitting on a windowsill"),
    S(preset="photo-real", prompt="Portrait of an elderly woman knitting, soft window light", aspect="3:4"),
    S(preset="to-3d", source_item=src["id"]),
    S(preset="photo-real", prompt="A red sports car on a mountain road", aspect="21:9"),
    S(preset="video", prompt="Waves gently rolling onto a sandy beach at sunset, soft ocean sounds", seconds=4),
    S(preset="watercolor", prompt="A small village by a river in spring", mode="quality"),
]
st0 = call("GET", "/api/status")
t0 = time.time()
ids = []
for t in TASKS:
    r = call("POST", "/api/generate", t)
    if isinstance(r, list):
        ids.append((t["preset"], r[0]["id"]))
    else:
        print("✗ не поставилась:", t["preset"], r)
print(f"поставлено {len(ids)} задач")
peak_vram, peak_ram = 0, 0
while True:
    q = call("GET", "/api/queue")
    st = call("GET", "/api/status")
    if st.get("gpu"):
        peak_vram = max(peak_vram, st["gpu"]["vram_used"])
    peak_ram = max(peak_ram, st["ram"]["used"])
    if not q:
        break
    time.sleep(3)
dt = time.time() - t0
items = call("GET", "/api/items?limit=40")
new = [i for i in items if i["created"] >= t0]
st1 = call("GET", "/api/status")
by = {}
for i in new:
    by[i["preset"]] = by.get(i["preset"], 0) + 1
print(f"\nготово результатов: {len(new)} из {len(TASKS)} за {dt / 60:.1f} мин")
print("по пресетам:", by)
print(f"VRAM: до {st0['gpu']['vram_used']} МБ, пик {peak_vram} МБ, после {st1['gpu']['vram_used']} МБ")
print(f"ОЗУ: до {st0['ram']['used']} ГБ, пик {peak_ram} ГБ, после {st1['ram']['used']} ГБ")
print("перезапуски движков:", [(s["name"], s["restarts"]) for s in st1["services"]])
missing = [p for p, _ in ids if p not in by]
print("без результата:", missing or "нет")
