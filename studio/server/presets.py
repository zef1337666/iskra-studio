"""Пресеты студии: папка presets/*.yaml (можно править вручную)."""
import re, shutil, time
import yaml
from ..config import ROOT

PRESETS_DIR = ROOT / "presets"
COVERS_DIR = PRESETS_DIR / "covers"
ASPECTS = {"1:1": (1, 1), "4:5": (4, 5), "3:4": (3, 4), "2:3": (2, 3), "9:16": (9, 16), "16:9": (16, 9), "21:9": (21, 9), "3:2": (3, 2), "5:4": (5, 4)}
GROUP_ORDER = ["Фото", "Арт", "Редактирование", "Видео", "3D", "18+", "Мои"]


def _ratio(aspect):
    """Произвольное соотношение «Ш:В» (например, размер исходника «832:1216»)."""
    try:
        a, b = (float(v) for v in str(aspect).split(":"))
        return (a, b) if a > 0 and b > 0 and 0.2 < a / b < 5 else None
    except Exception:
        return None


def size_for(aspect, megapixels, step=16):
    a, b = ASPECTS.get(aspect) or _ratio(aspect) or (1, 1)
    px = megapixels * 1024 * 1024
    w = (px * a / b) ** 0.5
    h = w * b / a
    return int(round(w / step)) * step, int(round(h / step)) * step


def caps(p):
    """Что умеет пресет: t2i, img2img, edit, char, pose, t2v, img2v, 2img2v, v2v, img2-3d."""
    wf, req, media = p.get("workflow"), p.get("requires"), p.get("media", "image")
    if media == "3d" or wf == "image_to_3d":
        return ["img2-3d"]
    if req == "video":
        return ["v2v"]
    if media == "video":
        if req == "images2":
            return ["2img2v"]
        if req == "image":
            return ["img2v"]
        return ["t2v", "img2v"] if wf == "h3_video" else ["t2v"]  # MiniMax-H3 — и из текста, и из картинки (первый кадр)
    if req in ("image", "images2"):
        if wf == "krea2_identity" or "same person" in (p.get("prompt_prefix") or ""):
            return ["char"]
        return ["pose"] if wf == "zimage_control" else ["edit"]
    out = ["t2i"]
    if p.get("ref_workflow") or (p.get("params") or {}).get("img2img"):
        out.append("img2img")
    return out


def load_all():
    out = []
    for f in sorted(PRESETS_DIR.glob("*.yaml")):
        try:
            p = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception as e:
            p = {"id": f.stem, "name": f.stem, "error": f"Ошибка в файле: {e}"}
        p.setdefault("id", f.stem)
        p["_file"] = f.name
        p["_caps"] = caps(p)
        out.append(p)
    out.sort(key=lambda p: (GROUP_ORDER.index(p.get("group")) if p.get("group") in GROUP_ORDER else 99, p.get("order", 50), p.get("name", "")))
    return out


def get(pid):
    return next((p for p in load_all() if p["id"] == pid), None)


def _slug(name):
    s = re.sub(r"[^a-z0-9а-яё]+", "-", name.lower()).strip("-")
    return s or f"preset-{int(time.time())}"


def save(p):
    p = {k: v for k, v in p.items() if not k.startswith("_")}
    p["id"] = p.get("id") or _slug(p.get("name", "preset"))
    (PRESETS_DIR / f"{p['id']}.yaml").write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return get(p["id"])


def duplicate(pid):
    p = dict(get(pid))
    p["id"] = f"{pid}-copy-{int(time.time()) % 10000}"
    p["name"] = p.get("name", pid) + " (копия)"
    p["group"] = "Мои"
    return save(p)


def delete(pid):
    f = PRESETS_DIR / f"{pid}.yaml"
    if f.exists():
        trash = ROOT / "data" / "trash" / "presets"
        trash.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(trash / f.name))


def mode_params(p, mode):
    """Параметры workflow: общие params + переопределения режима."""
    return {**(p.get("params") or {}), **(p.get(mode) or {})}
