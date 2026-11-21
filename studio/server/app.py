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
    # промпт по-русски без помощника — переводим (модели лучше понимают английский)
    import re as _re
    if _re.search("[а-яё]", body.get("prompt") or "", _re.I):
        p = presets.get(body.get("preset")) or {}
        try:
            r = prompter.generate(body["prompt"], p.get("assistant", "photo"), "exact", nsfw=bool(p.get("nsfw")))
            if r.get("error") and p.get("nsfw"):
                err(r["error"])
            if r.get("prompt"):
                body["prompt"] = r["prompt"]
        except HTTPException:
            raise
        except Exception:
            pass
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
                              reference=ref, focus=body.get("focus", "all"), style_hint=body.get("style_hint"),
                              lang=extras.get_settings().get("explain_lang", "ru"))
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


# ---------------------------------------------------------------- настройки, PIN
from . import extras  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402


@app.get("/api/settings")
def get_settings():
    return extras.public_settings()


@app.put("/api/settings")
def put_settings(body: dict):
    return extras.save_settings(body)


@app.post("/api/settings/reset")
def reset_settings():
    return extras.reset_settings()


@app.post("/api/pin/set")
def pin_set(body: dict):
    try:
        extras.set_pin(body.get("pin"), body.get("old"))
    except ValueError as e:
        err(str(e))
    return {"ok": True}


@app.post("/api/pin/check")
def pin_check(body: dict):
    if not extras.check_pin(body.get("pin")):
        err("Неверный PIN")
    return {"ok": True}


# ---------------------------------------------------------------- персонажи
@app.get("/api/characters")
def chars():
    return extras.characters()


@app.post("/api/characters")
def char_save(body: dict):
    if not body.get("name"):
        err("Укажите имя персонажа")
    return extras.save_character(body)


@app.delete("/api/characters/{cid}")
def char_del(cid: int):
    extras.delete_character(cid)
    return {"ok": True}


# ---------------------------------------------------------------- коллекции и экспорт
@app.get("/api/collections")
def colls():
    return extras.collections()


@app.post("/api/collections")
def coll_create(body: dict):
    if not body.get("name", "").strip():
        err("Введите название коллекции")
    return extras.create_collection(body["name"])


@app.post("/api/collections/{cid}/add")
def coll_add(cid: int, body: dict):
    extras.add_to_collection(cid, body.get("ids", []))
    return {"ok": True}


@app.delete("/api/collections/{cid}")
def coll_del(cid: int):
    extras.delete_collection(cid)
    return {"ok": True}


@app.post("/api/export.zip")
def export_zip(body: dict):
    return StreamingResponse(extras.export_zip(body.get("ids", [])), media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename=iskra_{time.strftime('%Y%m%d_%H%M')}.zip"})


@app.post("/api/items/restore/{item_id}")
def restore(item_id: int):
    return db.update_item(item_id, deleted=0)


# ---------------------------------------------------------------- модели: каталог, установка, обновления
@app.get("/api/models/search")
def models_search(q: str = "", source: str = "civitai", kind: str = None, base: str = None, nsfw: int = 0, cursor: str = None):
    try:
        if source == "hf":
            return catalog.hf_search(q or "comfyui", 24)
        return catalog.civitai_search(q, kind or None, base or None, bool(nsfw), cursor=cursor)
    except Exception:
        err("Каталог не отвечает. Проверьте интернет и попробуйте ещё раз.")


@app.post("/api/models/resolve")
def models_resolve(body: dict):
    try:
        return catalog.resolve(body.get("link", ""))
    except ValueError as e:
        err(str(e))
    except Exception:
        err("Не удалось открыть ссылку. Проверьте её и интернет.")


@app.post("/api/models/install")
def models_install(body: dict):
    if body.get("card"):
        t = registry.install_civitai(body["card"])
    elif body.get("file"):
        t = registry.install_hf(body["file"], body.get("repo", ""), {"name": body["file"]["filename"]})
    else:
        err("Нечего устанавливать")
    return t.info()


@app.post("/api/models/downloads/{tid}/{action}")
def dl_action(tid: str, action: str):
    t = get_downloader().tasks.get(tid) or err("Загрузка не найдена", 404)
    {"pause": t.pause, "resume": t.resume, "cancel": t.cancel}.get(action, lambda: None)()
    get_downloader()._wake.set()
    return t.info()


@app.delete("/api/models/file/{rel:path}")
def model_delete(rel: str):
    try:
        return {"trash": registry.delete(rel)}
    except ValueError as e:
        err(str(e))


@app.get("/api/models/updates")
def model_updates():
    return registry.check_updates()


@app.get("/api/models/recommended")
def model_recommended():
    js = ROOT / "model-picker" / "data.js"
    import json as _j
    return _j.loads(js.read_text(encoding="utf-8").split("=", 1)[1].strip().rstrip(";")) if js.exists() else []


@app.get("/api/models/ollama")
def model_ollama():
    return prompter.installed_models()


@app.post("/api/models/preset-from")
def preset_from_model(body: dict):
    """Пресет из рекомендованных настроек автора (для LoRA и чекпоинтов, установленных из каталога)."""
    m = body.get("model", {})
    base = (m.get("base_model") or "").lower()
    fam = "sdxl" if any(x in base for x in ("sdxl", "pony", "illustrious", "noob")) else "krea2" if "krea" in base else "klein" if "flux.3" in base or "klein" in base else "anima" if "anima" in base else None
    wf = {"sdxl": "sdxl_t2i", "krea2": "krea2_t2i", "klein": "klein_t2i", "anima": "anima_t2i"}.get(fam)
    if not wf:
        err("Для этой базовой модели пока нет готового workflow. Создайте пресет вручную в разделе «Пресеты».")
    fname = m["file"].rsplit("/", 1)[-1]
    p = {"name": m.get("name", fname)[:40], "group": "Мои", "nsfw": bool(m.get("nsfw")), "media": "image", "workflow": wf,
         "assistant": "anime" if fam in ("sdxl", "anima") else "photo", "base_model": m.get("base_model"),
         "megapixels": {"draft": 1.0, "quality": 1.0}, "params": {}, "description": "Создан из настроек автора модели."}
    if m["file"].startswith("loras/"):
        p["params"]["loras"] = [[fname, 0.8]]
        if fam == "sdxl":
            p["params"]["model"] = "OneObsession 24.safetensors"
    elif fam == "sdxl":
        p["params"]["model"] = fname
    if m.get("trained_words"):
        p["prompt_prefix"] = ", ".join(m["trained_words"][:3]) + ", "
    return presets.save(p)


# ---------------------------------------------------------------- система: логи, отчёт, бенчмарк
@app.get("/api/system/logs/{name}")
def sys_logs(name: str):
    return extras.human_logs(name)


@app.get("/api/system/report")
def sys_report():
    return {"text": extras.error_report()}


@app.get("/api/system/bench")
def sys_bench():
    return extras.bench_table()


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
