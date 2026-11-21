"""Backend студии «Искра»: FastAPI + WebSocket. Запуск: python -m studio.server.app"""
import asyncio, os, shutil, sys, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from ..config import ROOT, DATA, OUTPUT, INPUT, save_env_key, load_env
from ..assistant import prompter, vision
from ..models import catalog, registry
from ..models.downloader import get_downloader
from . import db, presets, services
from .jobs import JobManager, THUMBS, save_upload, item_to_input

WEB = ROOT / "app" / "web" / "dist"
JM: JobManager = None


@asynccontextmanager
async def lifespan(app):
    global JM
    for d in (OUTPUT, INPUT, THUMBS):
        d.mkdir(parents=True, exist_ok=True)
    db.conn()
    if os.environ.get("ISKRA_NO_SERVICES") != "1":
        services.start_all()
    JM = JobManager()
    asyncio.get_event_loop().create_task(JM.run())
    yield
    if os.environ.get("ISKRA_KEEP_SERVICES") != "1":
        for s in services.SERVICES.values():
            s.stop()


app = FastAPI(title="Искра", lifespan=lifespan)


def err(msg, code=400):
    raise HTTPException(code, detail=msg)


# ---------------------------------------------------------------- статус и система
@app.get("/api/status")
def status():
    return {"services": [s.info() for s in services.SERVICES.values()], "gpu": services.gpu_stats(), "ram": services.ram_stats(),
            "queue": JM.queue_info() if JM else [], "stats": db.stats(), "keys": {k: bool(v) for k, v in load_env().items() if k in ("HF_TOKEN", "CIVITAI_API_KEY")}}


@app.post("/api/services/{name}/restart")
def restart_service(name: str):
    s = services.SERVICES.get(name) or err("Нет такого сервиса", 404)
    s.restart()
    return s.info()


@app.post("/api/free")
def free():
    try:
        services.free_vram()
        return {"ok": True}
    except Exception:
        err("Движок не отвечает — освобождать нечего.")


# ---------------------------------------------------------------- пресеты
@app.get("/api/presets")
def list_presets():
    return presets.load_all()


@app.put("/api/presets/{pid}")
def save_preset(pid: str, body: dict):
    body["id"] = pid
    return presets.save(body)


@app.post("/api/presets")
def create_preset(body: dict):
    body.setdefault("group", "Мои")
    return presets.save(body)


@app.post("/api/presets/{pid}/duplicate")
def dup_preset(pid: str):
    return presets.duplicate(pid)


@app.delete("/api/presets/{pid}")
def del_preset(pid: str):
    presets.delete(pid)
    return {"ok": True}


@app.post("/api/presets/{pid}/cover/{item_id}")
def set_cover(pid: str, item_id: int):
    it = db.get_item(item_id) or err("Нет такого результата", 404)
    presets.COVERS_DIR.mkdir(parents=True, exist_ok=True)
    src = THUMBS / it["thumb"]
    shutil.copy(src, presets.COVERS_DIR / f"{pid}.webp")
    p = presets.get(pid)
    p["cover"] = f"{pid}.webp"
    return presets.save(p)


# ---------------------------------------------------------------- генерация и очередь
@app.post("/api/generate")
def generate(body: dict):
    if body.get("source_item"):
        it = db.get_item(int(body["source_item"])) or err("Исходный результат не найден", 404)
        key = "videos" if it["kind"] == "video" else "images"
        body[key] = [item_to_input(it)] + list(body.get(key) or [])
        body.setdefault("parent_id", it["id"])
        if it.get("width"):
            body.setdefault("src_w", it["width"]); body.setdefault("src_h", it["height"])
    try:
        jobs = JM.build(body)
    except ValueError as e:
        err(str(e))
    return JM.add(jobs)


@app.get("/api/queue")
def queue():
    return JM.queue_info()


@app.post("/api/jobs/{jid}/cancel")
def cancel(jid: str):
    JM.cancel(jid)
    return {"ok": True}


@app.post("/api/jobs/{jid}/move/{delta}")
def move(jid: str, delta: int):
    JM.move(jid, delta)
    return {"ok": True}


@app.post("/api/queue/pause/{on}")
def pause_queue(on: int):
    JM.queue_paused = bool(on)
    return {"paused": JM.queue_paused}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 300 * 2**20:
        err("Файл слишком большой (больше 300 МБ).")
    try:
        name = save_upload(data, file.filename or "image.png")
    except ValueError as e:
        err(str(e))
    try:
        from PIL import Image
        w, h = Image.open(INPUT / name).size
    except Exception:
        w = h = None
    return {"name": name, "url": f"/files/input/{name}", "width": w, "height": h}


# ---------------------------------------------------------------- помощник и описатель
@app.post("/api/assist")
def assist(body: dict):
    p = presets.get(body.get("preset")) or {}
    ref = None
    if body.get("reference"):
        try:
            ref = vision.describe(str(INPUT / body["reference"]), body.get("focus", "all"), nsfw=bool(p.get("nsfw")))["text"]
        except Exception:
            err("Описатель картинок не отвечает. Проверьте статус Ollama в разделе «Система».")
    try:
        r = prompter.generate(body.get("text", ""), p.get("assistant", "photo"), body.get("mode", "improve"), nsfw=bool(p.get("nsfw")),
                              reference=ref, focus=body.get("focus", "all"), style_hint=body.get("style_hint"))
    except Exception:
        err("Помощник промптов не отвечает. Проверьте статус Ollama в разделе «Система».")
    if r.get("error"):
        err(r["error"])
    return r


@app.post("/api/describe")
def describe(body: dict):
    p = presets.get(body.get("preset")) or {}
    return vision.describe(str(INPUT / body["file"]), body.get("focus", "all"), nsfw=bool(p.get("nsfw")))


# ---------------------------------------------------------------- галерея
@app.get("/api/items")
def items(before: int = None, limit: int = 60, kind: str = None, preset: str = None, favorite: int = 0, q: str = None, nsfw: int = 1,
          rating: int = None, collection: int = None, trash: int = 0):
    return db.list_items(before, limit, kind, preset, favorite, q, bool(nsfw), bool(trash), rating, collection)


@app.get("/api/items/{item_id}")
def item(item_id: int):
    return db.get_item(item_id) or err("Не найдено", 404)


@app.patch("/api/items/{item_id}")
def patch_item(item_id: int, body: dict):
    return db.update_item(item_id, **body)


@app.post("/api/items/{item_id}/to-input")
def to_input(item_id: int):
    it = db.get_item(item_id) or err("Не найдено", 404)
    name = item_to_input(it)
    return {"name": name, "url": f"/files/input/{name}", "width": it.get("width"), "height": it.get("height")}


@app.post("/api/items/{item_id}/open-folder")
def open_folder(item_id: int):
    it = db.get_item(item_id) or err("Не найдено", 404)
    import subprocess
    subprocess.Popen(["explorer", "/select,", str(OUTPUT / it["path"])])
    return {"ok": True}


# ---------------------------------------------------------------- модели (часть раздела «Модели»; полная версия — веха 6)
@app.get("/api/models/installed")
def models_installed():
    return {"items": registry.installed(), "space": registry.space_by_category()}


@app.get("/api/models/downloads")
def downloads():
    return get_downloader().list()


@app.post("/api/settings/key")
def set_key(body: dict):
    if body.get("name") not in ("HF_TOKEN", "CIVITAI_API_KEY"):
        err("Неизвестный ключ")
    save_env_key(body["name"], body.get("value", "").strip())
    return {"ok": True}


# ---------------------------------------------------------------- WebSocket для интерфейса
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    JM.listeners.add(websocket)
    await websocket.send_json({"type": "queue", "queue": JM.queue_info()})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        JM.listeners.discard(websocket)


# ---------------------------------------------------------------- файлы
def _safe(base, rel):
    p = (base / rel).resolve()
    if base.resolve() not in p.parents and p != base.resolve():
        err("Нет доступа", 403)
    if not p.exists():
        err("Файл не найден", 404)
    return p


@app.get("/files/output/{rel:path}")
def f_output(rel: str):
    return FileResponse(_safe(OUTPUT, rel))


@app.get("/files/thumbs/{rel:path}")
def f_thumb(rel: str):
    return FileResponse(_safe(THUMBS, rel), headers={"Cache-Control": "max-age=31536000"})


@app.get("/files/input/{rel:path}")
def f_input(rel: str):
    return FileResponse(_safe(INPUT, rel))


@app.get("/files/covers/{rel:path}")
def f_cover(rel: str):
    return FileResponse(_safe(presets.COVERS_DIR, rel))


if WEB.exists():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")


def main():
    import uvicorn
    uvicorn.run(app, host=os.environ.get("ISKRA_HOST", "127.0.0.1"), port=int(os.environ.get("ISKRA_PORT", 7860)), log_level="warning")


if __name__ == "__main__":
    main()
