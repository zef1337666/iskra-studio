"""Загрузчик выбранных моделей: докачка, повторы, проверка SHA256, раскладка по папкам.

Использование:
  python download_models.py --list          # показать, что будет скачано
  python download_models.py                 # скачать всё, что доступно
Ключи берутся из F:/AI-Studio/.env: HF_TOKEN, CIVITAI_API_KEY (никогда не печатаются).
Основа будущего менеджера загрузок (этап 4).
"""
import hashlib, json, os, pathlib, sys, time, urllib.request, urllib.error, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
STATUS = ROOT / "data" / "downloads.json"
# Официальные (gated) репозитории вместо неофициальных зеркал
URL_REWRITE = {"/ml-resources/flux-3-image-klein-comfy/": "/black-forest-labs/flux-3-image-klein-comfy/"}


def load_env():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    return env


def load_plan():
    raw = (ROOT / "model-picker" / "data.js").read_text(encoding="utf-8")
    data = json.loads(raw.split("=", 1)[1].strip().rstrip(";"))
    idx = {c["id"] + "/" + i["id"]: i for c in data for i in c["items"]}
    sel = [l.strip() for l in (ROOT / "config" / "selection.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    files, missing = {}, []
    for s in sel:
        it = idx.get(s)
        if not it:
            missing.append(s)
            continue
        for f in it.get("files", []):
            url = f.get("url") or ""
            for a, b in URL_REWRITE.items():
                url = url.replace(a, b)
            key = f["folder"] + "/" + f["filename"]
            files.setdefault(key, {**f, "url": url, "for": []})["for"].append(s)
    extra = ROOT / "config" / "extra_files.json"
    if extra.exists():
        for f in json.loads(extra.read_text(encoding="utf-8-sig")):
            files.setdefault(f["folder"] + "/" + f["filename"], {**f, "for": [f.get("for", "extra")]})
    return files, missing


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """При переходе на другой хост (CDN) не пересылаем ключ: иначе CDN отвечает 400."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlparse(newurl).netloc != urllib.parse.urlparse(req.full_url).netloc:
            new.headers.pop("Authorization", None)
            new.unredirected_hdrs.pop("Authorization", None)
        if new is not None and "/model-versions/" in newurl and "civitai.com" in newurl:
            raise urllib.error.HTTPError(newurl, 403, "civitai: файл недоступен для скачивания", headers, fp)
        return new


urllib.request.install_opener(urllib.request.build_opener(SafeRedirect))


def auth_request(url, env, start=0):
    headers = {"User-Agent": "ai-studio-downloader/1.0"}
    host = urllib.parse.urlparse(url).netloc
    if "huggingface.co" in host and env.get("HF_TOKEN"):
        headers["Authorization"] = "Bearer " + env["HF_TOKEN"]
    if "civitai.com" in host and env.get("CIVITAI_API_KEY"):
        headers["Authorization"] = "Bearer " + env["CIVITAI_API_KEY"]
    if start:
        headers["Range"] = f"bytes={start}-"
    return urllib.request.Request(url, headers=headers)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(f, env):
    dest = MODELS / f["folder"] / f["filename"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    want_sha = (f.get("sha256") or "").lower() or None
    if dest.exists():
        return "уже есть"
    for attempt in range(1, 7):
        start = part.stat().st_size if part.exists() else 0
        try:
            with urllib.request.urlopen(auth_request(f["url"], env, start), timeout=60) as r:
                if start and r.status != 206:
                    start = 0  # сервер не поддерживает докачку
                total = start + int(r.headers.get("Content-Length") or 0)
                mode = "ab" if start else "wb"
                done, t0, last = start, time.time(), 0
                with open(part, mode) as out:
                    while True:
                        chunk = r.read(4 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                        done += len(chunk)
                        if time.time() - last > 15:
                            last = time.time()
                            spd = (done - start) / max(1e-3, last - t0) / 1e6
                            pct = f"{done / total * 100:5.1f}%" if total else ""
                            print(f"    {pct} {done / 1e9:.2f} ГБ, {spd:.0f} МБ/с", flush=True)
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return "нужен вход/ключ (" + str(e.code) + ")"
            if e.code == 416:
                break
            err = f"HTTP {e.code}"
        except Exception as e:  # обрыв сети
            err = type(e).__name__
        print(f"    обрыв ({err}), повтор {attempt}/6…", flush=True)
        time.sleep(min(60, 5 * attempt))
    else:
        return "ошибка загрузки"
    if want_sha:
        got = sha256_of(part)
        if got != want_sha:
            part.rename(part.with_suffix(".bad"))
            return "хеш не совпал — файл отложен (.bad)"
    part.rename(dest)
    return "ok" + (" (хеш проверен)" if want_sha else "")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    env = load_env()
    files, missing = load_plan()
    for m in missing:
        print("! нет в каталоге:", m)
    total = sum(float(f.get("size_gb") or 0) for f in files.values())
    if "--list" in sys.argv:
        for k, f in files.items():
            print(f"{float(f.get('size_gb') or 0):7.2f}  {k}  <- {urllib.parse.urlparse(f['url']).netloc or f['url']}")
        print(f"Итого {len(files)} файлов, {total:.1f} ГБ")
        return
    status = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    for k, f in files.items():
        if only and not any(s in f["url"] for s in only):
            continue
        if f["url"].startswith("ollama:"):
            status[k] = "через Ollama (этап 5)"
            continue
        if "civitai.com" in f["url"] and not env.get("CIVITAI_API_KEY"):
            status[k] = "ждёт ключ Civitai"
            continue
        print(f"→ {k} ({f.get('size_gb')} ГБ)", flush=True)
        status[k] = download(f, env)
        print("   ", status[k], flush=True)
        STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nИТОГ:")
    for k, v in status.items():
        print(f"  {v:40s} {k}")


if __name__ == "__main__":
    main()
