"""Проверка API вехи 6: статус GPU, перерисовка области по маске, коллекции, zip, персонажи, настройки/PIN, защита 18+."""
import json, sys, time, urllib.request, urllib.error, io, pathlib
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:7860"


def call(method, path, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(B + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(r, timeout=120).read()
        return resp if raw else json.loads(resp)
    except urllib.error.HTTPError as e:
        return {"_err": e.code, "detail": json.loads(e.read() or b"{}").get("detail")}


def upload(img, name):
    buf = io.BytesIO(); img.save(buf, "PNG")
    bnd = "----iskra"
    body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{bnd}--\r\n".encode()
    r = urllib.request.Request(B + "/api/upload", data=body, headers={"Content-Type": f"multipart/form-data; boundary={bnd}"})
    return json.loads(urllib.request.urlopen(r).read())


ok = lambda c, m: print(("✓ " if c else "✗ ") + m) or bool(c)
res = []
for _ in range(30):
    try:
        st = call("GET", "/api/status"); break
    except Exception:
        time.sleep(1)
res.append(ok(st.get("gpu") and st["gpu"]["vram_total"] > 0, f"статус GPU: {st.get('gpu')}"))
src = call("GET", "/api/items?limit=50&kind=image")
src = next(i for i in src if i["preset"] == "photo-real")
w, h = src["width"], src["height"]
m = Image.new("RGB", (w, h), "black"); ImageDraw.Draw(m).ellipse((w * .3, h * .15, w * .7, h * .45), fill="white")
mask = upload(m, "mask.png")["name"]
jobs = call("POST", "/api/generate", {"preset": "inpaint", "mode": "draft", "source_item": src["id"], "mask": mask, "prompt": "круглые солнечные очки", "user_text": "круглые солнечные очки"})
res.append(ok(isinstance(jobs, list), f"перерисовка области поставлена: {jobs if not isinstance(jobs, list) else jobs[0]['id']}"))
for _ in range(90):
    q = call("GET", "/api/queue")
    if not q:
        break
    time.sleep(2)
new = call("GET", "/api/items?limit=1")[0]
res.append(ok(new["preset"] == "inpaint" and new["parent_id"] == src["id"], f"результат перерисовки #{new['id']} (родитель #{new['parent_id']}), промпт: {new['prompt'][:90]}"))
c = call("POST", "/api/collections", {"name": "Тест"})
call("POST", f"/api/collections/{c['id']}/add", {"ids": [src["id"], new["id"]]})
res.append(ok(len(call("GET", f"/api/items?collection={c['id']}")) == 2, "коллекция: 2 элемента"))
z = call("POST", "/api/export.zip", {"ids": [src["id"], new["id"]]}, raw=True)
res.append(ok(isinstance(z, bytes) and z[:2] == b"PK", f"zip: {len(z) // 1024} КБ"))
call("DELETE", f"/api/collections/{c['id']}")
ref = call("POST", f"/api/items/{src['id']}/to-input")
ch = call("POST", "/api/characters", {"name": "Тест-кот", "description": "рыжий кот", "refs": [ref]})
res.append(ok(ch.get("id") and call("GET", "/api/characters"), "персонаж сохранён"))
r18 = call("POST", "/api/generate", {"preset": "real18", "mode": "draft", "character": ch["id"], "prompt": "portrait", "images": [ref["name"]]})
res.append(ok(r18.get("_err") == 400, f"18+ с персонажем запрещено: {r18.get('detail', '')[:70]}"))
up = upload(Image.new("RGB", (64, 64), "gray"), "photo.png")["name"]
r18b = call("POST", "/api/generate", {"preset": "video18", "mode": "draft", "images": [up], "prompt": "smiles"})
res.append(ok(r18b.get("_err") == 400, f"18+ видео из загруженного фото запрещено: {r18b.get('detail', '')[:70]}"))
call("DELETE", f"/api/characters/{ch['id']}")
call("POST", "/api/pin/set", {"pin": "1234"})
res.append(ok(call("POST", "/api/pin/check", {"pin": "0000"}).get("_err") == 400 and call("POST", "/api/pin/check", {"pin": "1234"}).get("ok"), "PIN проверяется"))
call("POST", "/api/pin/set", {"pin": "", "old": "1234"})
print(f"\nИтог: {sum(res)}/{len(res)}")
