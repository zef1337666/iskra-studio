"""Очередь задач: сборка workflow из пресета, отправка в ComfyUI, живой прогресс и превью, сохранение в историю."""
import asyncio, base64, json, random, shutil, time, uuid, urllib.request, urllib.error
import websockets
from PIL import Image
from ..config import COMFY_URL, DATA, INPUT, OUTPUT
from ..engine.workflows import REGISTRY
from ..models import registry as model_registry
from ..assistant import safety
from . import db, presets

THUMBS = DATA / "thumbs"
FREE_BEFORE = {"video_audio"}
CLIENT_ID = "iskra-" + uuid.uuid4().hex[:8]

ERRORS_RU = [
    ("out of memory", "Не хватило видеопамяти. Попробуйте режим «Черновик» или уменьшите разрешение."),
    ("allocation on device", "Не хватило видеопамяти. Попробуйте режим «Черновик» или уменьшите разрешение."),
    ("value_not_in_list", "Не найден файл модели. Проверьте раздел «Модели» — возможно, модель не установлена."),
    ("not found", "Не найден нужный файл (модель или картинка)."),
    ("connection", "Движок ComfyUI не отвечает. Студия перезапускает его — повторите через минуту."),
]


def human_error(text):
    t = (text or "").lower()
    for k, ru in ERRORS_RU:
        if k in t:
            return ru
    return "Что-то пошло не так при генерации. Подробности — в разделе «Система» → «Логи»."


def _post(path, data):
    r = urllib.request.Request(COMFY_URL + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=30).read() or b"{}")


class Job:
    def __init__(self, req, preset, mode, params, workflow, title):
        self.id = uuid.uuid4().hex[:10]
        self.req, self.preset, self.mode, self.params, self.workflow, self.title = req, preset, mode, params, workflow, title
        self.state = "queued"  # queued | running | done | error | cancelled
        self.progress, self.step, self.steps = 0.0, 0, 0
        self.node = ""
        self.prompt_id = None
        self.error = None
        self.items = []
        self.created, self.started, self.finished = time.time(), None, None
        self.eta = None
        self.paused = False

    def info(self):
        return {"id": self.id, "state": self.state, "progress": round(self.progress, 3), "step": self.step, "steps": self.steps,
                "node": self.node, "error": self.error, "items": self.items, "title": self.title, "preset": self.preset.get("id"),
                "preset_name": self.preset.get("name"), "mode": self.mode, "eta": self.eta, "paused": self.paused,
                "elapsed": round(time.time() - self.started, 1) if self.started and not self.finished else None,
                "kind": self.preset.get("media", "image")}


class JobManager:
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []
        self.listeners: set = set()
        self.current: Job | None = None
        self._wake = asyncio.Event()
        self.queue_paused = False

    # ---------- рассылка в интерфейс
    async def broadcast(self, msg):
        dead = []
        for ws in list(self.listeners):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.listeners.discard(ws)

    def push(self, msg):
        """Безопасно из любого потока (синхронные обработчики FastAPI работают в пуле потоков)."""
        loop = getattr(self, "loop", None)
        if loop is None:
            return
        try:
            if asyncio.get_running_loop() is loop:
                loop.create_task(self.broadcast(msg))
                return
        except RuntimeError:
            pass
        asyncio.run_coroutine_threadsafe(self.broadcast(msg), loop)

    # ---------- сборка задач из запроса интерфейса
    def build(self, req):
        p = presets.get(req["preset"])
        if not p:
            raise ValueError("Пресет не найден.")
        mode = req.get("mode") or "quality"
        if p.get("nsfw"):
            ref = safety.check_request((req.get("user_text") or "") + " " + (req.get("prompt") or ""), True)
            if ref:
                raise ValueError(ref)
        count = max(1, min(4, int(req.get("count", 1))))
        base_seed = req.get("seed")
        if base_seed in (None, "", -1) or not req.get("seed_lock"):
            base_seed = random.randint(0, 2**40)
        jobs = []
        for i in range(count):
            params = presets.mode_params(p, mode)
            wf_name = p["workflow"]
            images = list(req.get("images") or [])
            # слабое влияние референса — только описание в промпте; сильное — картинка идёт в модель правки
            if images and p.get("ref_workflow") and float(req.get("ref_strength", 0.7)) >= 0.5:
                wf_name = p["ref_workflow"]
            elif images and p.get("ref_workflow"):
                images = []
            prompt = (req.get("prompt") or req.get("user_text") or "").strip()
            if wf_name == p.get("ref_workflow") and "<ref_image" not in prompt:
                focus = {"style": "in the visual style of", "composition": "with the same composition and pose as",
                         "character": "featuring the same character as", "colors": "with the same colors and lighting as"}.get(req.get("focus"), "based on")
                prompt = f"A new image {focus} <ref_image_0>: {prompt}"
            if p.get("nsfw") and (req.get("character") or images and p.get("ref_workflow")):
                raise ValueError("В 18+ пресетах нельзя использовать персонажей и фото-референсы людей — только вымышленные персонажи из текста.")
            if p.get("nsfw"):
                from ..assistant import provenance
                for n in images:
                    if not str(n).startswith("up_"):
                        continue
                    inf = provenance.info(n)
                    # загруженная картинка в 18+: нужна метка «создано ИИ» или явное подтверждение пользователя
                    if not inf.get("ai") and not req.get("attest_fictional"):
                        raise ValueError("Для 18+ подтвердите, что на загруженной картинке вымышленный взрослый персонаж, созданный ИИ, "
                                         "а не фото реального человека (галочка под картинкой).")
                    if inf.get("age") is None or inf["age"] < 20:
                        raise ValueError("Возраст на картинке не прошёл проверку — такую картинку нельзя использовать в 18+.")
            if p.get("prompt_template"):
                prompt = p["prompt_template"].replace("{prompt}", prompt)
            if p.get("prompt_prefix"):
                prompt = p["prompt_prefix"] + prompt
            if p.get("prompt_suffix"):
                prompt = prompt + p["prompt_suffix"]
            negative = req.get("negative") or p.get("negative") or ""
            if p.get("nsfw"):
                prompt, negative = safety.enforce_adult(prompt, negative, anime="anime" in (p.get("assistant") or ""))
                if prompt is None:
                    raise ValueError(safety.REFUSAL_RU)
            params.update(prompt=prompt, negative=negative, seed=int(base_seed) + i)
            if images:
                params["images"] = images
            if req.get("videos"):
                params["videos"] = req["videos"]
            mp = (p.get("megapixels") or {}).get(mode)
            if mp and req.get("aspect") and p.get("media", "image") == "image" and wf_name not in ("upscale", "remove_bg", "detailer"):
                params["width"], params["height"] = presets.size_for(req["aspect"], mp)
            if p.get("media") == "video" and req.get("aspect"):
                a, b = presets.ASPECTS.get(req["aspect"], (16, 9))
                params["aspect"] = a / b
                params["portrait"] = b > a
            for k in ("steps", "cfg", "seconds", "camera", "smooth", "control", "strength", "target", "scale", "left", "right",
                      "top", "bottom", "src_w", "src_h", "mask", "fps", "duration", "multiplier", "set", "width", "height"):
                if req.get(k) not in (None, ""):
                    params[k] = req[k]
            if req.get("loras"):
                params["loras"] = [[l["name"], float(l.get("weight", 1.0))] if isinstance(l, dict) else [l[0], float(l[1])]
                                   for l in req["loras"] if (l.get("name") if isinstance(l, dict) else l)]
            prefix_root = "nsfw" if p.get("nsfw") else "studio"
            params["prefix"] = f"{prefix_root}/{time.strftime('%Y-%m')}/{p['id']}"
            title = (req.get("user_text") or prompt)[:80]
            job = Job(req, p, mode, params, wf_name, title)
            job.eta = (p.get("eta") or {}).get(mode)
            jobs.append(job)
        return jobs

    def add(self, jobs):
        for j in jobs:
            self.jobs[j.id] = j
            self.order.append(j.id)
        self._wake.set()
        self.push({"type": "queue", "queue": self.queue_info()})
        return [j.info() for j in jobs]

    def queue_info(self):
        return [self.jobs[i].info() for i in self.order if i in self.jobs and self.jobs[i].state in ("queued", "running")]

    def cancel(self, jid):
        j = self.jobs.get(jid)
        if not j:
            return
        if j.state == "running":
            try:
                _post("/interrupt", {})
            except Exception:
                pass
        if j.state in ("queued", "running"):
            j.state = "cancelled"
            j.finished = time.time()
        self.push({"type": "job", "job": j.info()})
        self.push({"type": "queue", "queue": self.queue_info()})

    def move(self, jid, delta):
        if jid in self.order:
            i = self.order.index(jid)
            k = max(0, min(len(self.order) - 1, i + delta))
            self.order.insert(k, self.order.pop(i))
            self.push({"type": "queue", "queue": self.queue_info()})

    # ---------- основной цикл
    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.loop.create_task(self._ws_loop())
        while True:
            job = None if self.queue_paused else next((self.jobs[i] for i in self.order if self.jobs[i].state == "queued" and not self.jobs[i].paused), None)
            if not job:
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), 2)
                except asyncio.TimeoutError:
                    pass
                continue
            await self._execute(job)

    async def _execute(self, job: Job, retry=True):
        self.current = job
        job.state, job.started = "running", time.time()
        self.push({"type": "job", "job": job.info()})
        try:
            graph = REGISTRY[job.workflow](dict(job.params), job.mode)
            job._done_evt = asyncio.Event()
            if job.workflow in FREE_BEFORE:
                # сторонние ноды (MMAudio) не умеют выгружать чужие модели — освобождаем VRAM заранее
                try:
                    await asyncio.get_event_loop().run_in_executor(None, _post, "/free", {"unload_models": True, "free_memory": True})
                except Exception:
                    pass
            res = await asyncio.get_event_loop().run_in_executor(None, _post, "/prompt", {"prompt": graph, "client_id": CLIENT_ID})
            job.prompt_id = res["prompt_id"]
            await job._done_evt.wait()
            if job.state == "cancelled":
                return
            if getattr(job, "_lost", False):
                raise ConnectionError("движок упал во время задачи")
            if job.error:
                raise RuntimeError(job.error)
            await asyncio.get_event_loop().run_in_executor(None, self._collect, job, graph)
            job.state = "done"
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            job.state, job.error = "error", human_error(body)
        except (urllib.error.URLError, ConnectionError) as e:
            if retry:  # ComfyUI упал — ждём перезапуска и повторяем один раз
                job._lost = False
                job.node = "Перезапуск движка…"
                self.push({"type": "job", "job": job.info()})
                for _ in range(90):
                    await asyncio.sleep(2)
                    try:
                        urllib.request.urlopen(COMFY_URL + "/system_stats", timeout=2)
                        break
                    except Exception:
                        pass
                return await self._execute(job, retry=False)
            job.state, job.error = "error", human_error("connection")
        except Exception as e:
            job.state, job.error = "error", human_error(str(e))
            job._raw_error = str(e)
        finally:
            job.finished = time.time()
            self.current = None
            self.push({"type": "job", "job": job.info()})
            self.push({"type": "queue", "queue": self.queue_info()})
            self._maybe_notify(job)

    def _maybe_notify(self, job):
        """Уведомление Windows, когда очередь опустела (ночной режим) или долгая задача завершилась."""
        from . import extras
        if self.queue_info():
            return
        s = extras.get_settings()
        batch = [j for j in self.jobs.values() if j.finished and j.finished > time.time() - 12 * 3600 and not getattr(j, "_notified", False)]
        long_job = job.finished - (job.started or job.finished) > 60
        if s.get("night_mode") or long_job:
            ok = sum(1 for j in batch if j.state == "done")
            bad = sum(1 for j in batch if j.state == "error")
            extras.notify("Искра: всё готово", f"Готово задач: {ok}" + (f", с ошибкой: {bad}" if bad else ""))
            for j in batch:
                j._notified = True

    def _collect(self, job: Job, graph):
        h = json.loads(urllib.request.urlopen(f"{COMFY_URL}/history/{job.prompt_id}", timeout=30).read())[job.prompt_id]
        model_registry.mark_used([n["inputs"].get(k) for n in graph.values() for k in ("unet_name", "ckpt_name", "lora_name") if n["inputs"].get(k)])
        for out in h.get("outputs", {}).values():
            for key in ("images", "gifs", "videos", "3d", "video"):
                for f in out.get(key, []) or []:
                    if not isinstance(f, dict) or "filename" not in f or f.get("type", "output") != "output":
                        continue
                    rel = (f.get("subfolder") + "/" if f.get("subfolder") else "") + f["filename"]
                    src = OUTPUT / rel
                    if not src.exists():
                        continue
                    if src.suffix.lower() == ".png":
                        src, rel = convert_image(src, rel)
                    kind ="video" if src.suffix.lower() in (".mp4", ".webm", ".mov") else "3d" if src.suffix.lower() in (".glb", ".gltf", ".obj") else "image"
                    w = hgt = None
                    thumb = None
                    try:
                        thumb, w, hgt = make_thumb(src, kind)
                    except Exception:
                        pass
                    p = job.params
                    item = db.add_item(path=rel, thumb=thumb, kind=kind, preset=job.preset["id"], preset_name=job.preset.get("name"),
                                       model=job.preset.get("base_model"), mode=job.mode, prompt=p.get("prompt"), negative=p.get("negative"),
                                       user_text=job.req.get("user_text"), seed=p.get("seed"), width=w, height=hgt,
                                       params={k: v for k, v in p.items() if k not in ("prompt", "negative")} | {"workflow": job.workflow},
                                       nsfw=1 if job.preset.get("nsfw") else 0, parent_id=job.req.get("parent_id"),
                                       job_sec=round(time.time() - job.started, 1))
                    job.items.append(item)

    # ---------- события ComfyUI
    async def _ws_loop(self):
        url = COMFY_URL.replace("http", "ws") + f"/ws?clientId={CLIENT_ID}"
        while True:
            try:
                async with websockets.connect(url, max_size=64 * 2**20) as ws:
                    async for msg in ws:
                        await self._on_comfy(msg)
            except Exception:
                pass
            # связь с движком оборвалась: текущая задача не завершится сама — помечаем для повтора
            j = self.current
            if j and j.prompt_id and hasattr(j, "_done_evt") and not j._done_evt.is_set():
                j._lost = True
                j._done_evt.set()
            await asyncio.sleep(3)

    async def _on_comfy(self, msg):
        job = self.current
        if isinstance(msg, (bytes, bytearray)):
            if job and len(msg) > 8:  # бинарное превью: 4 байта тип события + 4 байта формат + картинка
                fmt = int.from_bytes(msg[4:8], "big")
                mime = "image/png" if fmt == 2 else "image/jpeg"
                await self.broadcast({"type": "preview", "job": job.id, "image": f"data:{mime};base64," + base64.b64encode(msg[8:]).decode()})
            return
        m = json.loads(msg)
        t, d = m.get("type"), m.get("data", {})
        if not job or (d.get("prompt_id") and d.get("prompt_id") != job.prompt_id):
            return
        if t == "progress":
            job.step, job.steps = d.get("value", 0), d.get("max", 0)
            job.progress = job.step / job.steps if job.steps else 0
            if job.started and job.progress > 0.05:
                el = time.time() - job.started
                job.eta = round(el / job.progress - el)
            await self.broadcast({"type": "job", "job": job.info()})
        elif t == "executing":
            node = d.get("node")
            if node is None and d.get("prompt_id") == job.prompt_id:
                job._done_evt.set()
            else:
                job.node = node or ""
        elif t == "execution_success":
            job._done_evt.set()
        elif t == "execution_error":
            job.error = human_error(d.get("exception_message", ""))
            job._raw_error = d.get("exception_message")
            job._done_evt.set()
        elif t == "execution_interrupted":
            job.state = "cancelled"
            job._done_evt.set()


def convert_image(src, rel):
    """Формат сохранения из настроек (PNG/WebP/JPG) и удаление метаданных workflow, если выключено."""
    from . import extras
    s = extras.get_settings()
    fmt = s.get("save_format", "png")
    if fmt == "png" and s.get("keep_metadata", True):
        return src, rel
    im = Image.open(src)
    if fmt == "png":
        im.save(src)  # пересохранение без текстовых блоков workflow
        return src, rel
    dst = src.with_suffix(".webp" if fmt == "webp" else ".jpg")
    if im.mode in ("RGBA", "LA") and fmt == "jpg":
        im = im.convert("RGB")
    im.save(dst, quality=int(s.get("jpg_quality", 92)))
    src.unlink()
    return dst, rel.rsplit(".", 1)[0] + dst.suffix


def make_thumb(src, kind):
    THUMBS.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex[:16] + ".webp"
    if kind == "image":
        im = Image.open(src)
    elif kind == "video":
        import av
        c = av.open(str(src))
        im = next(c.decode(video=0)).to_image()
        c.close()
    else:
        return None, None, None
    w, h = im.size
    im = im.convert("RGB")
    im.thumbnail((640, 640))
    im.save(THUMBS / name, quality=82)
    return name, w, h


def save_upload(data: bytes, filename: str):
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "png").lower()
    if ext not in ("png", "jpg", "jpeg", "webp", "mp4", "webm", "mov", "bmp"):
        raise ValueError("Этот формат файла не поддерживается.")
    name = f"up_{uuid.uuid4().hex[:12]}.{ext}"
    (INPUT / name).write_bytes(data)
    return name


def item_to_input(item):
    """Копирует результат из галереи во входную папку ComfyUI (для «Апскейл», «Оживить» и т.п.)."""
    src = OUTPUT / item["path"]
    name = f"it_{item['id']}_{src.name}"
    dst = INPUT / name
    if not dst.exists():
        shutil.copy(src, dst)
    return name
