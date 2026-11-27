"""Проверка улучшений качества через API студии: улучшатель BFL, доводка SeedVR2, 18+ на LUSTIFY, «по картинке»."""
import io, json, sys, time, urllib.request, urllib.error
from PIL import Image
sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:7860"
res = []
ok = lambda c, m: print(("✓ " if c else "✗ ") + m) or res.append(bool(c))


def call(m, p, b=None, t=600):
    r = urllib.request.Request(B + p, data=json.dumps(b).encode() if b is not None else None, method=m, headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(r, timeout=t).read())
    except urllib.error.HTTPError as e:
        return {"_err": e.code, "detail": json.loads(e.read() or b"{}").get("detail")}


def upload(path):
    buf = io.BytesIO(); Image.open(path).convert("RGB").save(buf, "JPEG", quality=92)
    bnd = "----q"
    body = f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"my.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode() + buf.getvalue() + f"\r\n--{bnd}--\r\n".encode()
    return json.loads(urllib.request.urlopen(urllib.request.Request(B + "/api/upload", data=body, headers={"Content-Type": f"multipart/form-data; boundary={bnd}"})).read())


def wait_new(since, timeout=600):
    t = time.time()
    while time.time() - t < timeout:
        if not call("GET", "/api/queue"):
            break
        time.sleep(2)
    return [i for i in call("GET", "/api/items?limit=10") if i["created"] >= since]


a = call("POST", "/api/assist", {"preset": "photo-real", "mode": "improve", "text": "пожилой рыбак чинит сети на причале на рассвете, туман", "aspect": "3:2"})
ok(a.get("_model") == "BFL upsampler" and len(a.get("prompt", "")) > 200, f"«Улучшить» через улучшатель BFL ({a.get('_sec')} с): {a.get('prompt', a)[:120]}…")
t0 = time.time()
call("POST", "/api/generate", {"preset": "photo-real", "mode": "quality", "prompt": a["prompt"], "user_text": "рыбак", "aspect": "3:2"})
new = wait_new(t0)
ok(new and new[0]["width"] >= 1800, f"«Реализм / Качество» с доводкой SeedVR2: {new[0]['width']}×{new[0]['height']} за {new[0]['job_sec']} с" if new else "нет результата")
t0 = time.time()
call("POST", "/api/generate", {"preset": "real18", "mode": "quality", "prompt": "Candid photo of a 24-year-old woman with curly red hair in a green summer dress laughing in a sunflower field at golden hour. Amateur phone photo.", "aspect": "2:3"})
new18 = wait_new(t0)
ok(new18 and new18[0]["preset"] == "real18", f"«Реализм 18+» (LUSTIFY + Vérité + SeedVR2): {new18[0]['width']}×{new18[0]['height']} за {new18[0]['job_sec']} с" if new18 else "нет результата")
if new18:
    t0 = time.time()
    r = call("POST", "/api/generate", {"preset": "real18", "mode": "draft", "source_item": new18[0]["id"], "ref_strength": 0.55,
                                       "prompt": "the same woman, now standing at a beach at sunset, wind in her hair. Amateur phone photo."})
    v = wait_new(t0)
    ok(isinstance(r, list) and v, f"18+ «по картинке» из галереи работает ({v[0]['job_sec'] if v else '?'} с)")
up = upload(r"F:\AI-Studio\data\input\test_cat.png")
r = call("POST", "/api/generate", {"preset": "real18", "mode": "draft", "images": [up["name"]], "attest_fictional": True, "prompt": "a woman"})
ok(r.get("_err") == 400, f"18+ «по картинке» с загруженным файлом отклонено: {str(r.get('detail'))[:80]}")
t0 = time.time()
r = call("POST", "/api/generate", {"preset": "watercolor", "mode": "draft", "images": [up["name"]], "ref_strength": 0.5, "prompt": "a ginger cat on a windowsill, soft watercolor"})
w = wait_new(t0)
ok(isinstance(r, list) and w and w[0]["preset"] == "watercolor", f"«Акварель» по загруженной фотографии ({w[0]['job_sec'] if w else '?'} с)")
print(f"\nИтог: {sum(res)}/{len(res)}")
print("ID для просмотра:", [x["id"] for x in (new or []) + (new18 or []) + (w or [])])
