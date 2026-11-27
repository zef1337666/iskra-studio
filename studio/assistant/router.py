"""Кнопка «ИИ» и режим «Авто»: по описанию своими словами (и вложениям) выбирает пресет-модель, формат кадра и подходящие LoRA.
Промпт потом пишет обычный помощник по официальной инструкции выбранной модели."""
import json, struct
import yaml
from ..config import ROOT
from . import prompter

SKIP = {"inpaint", "outpaint"}  # нужна ручная подготовка в интерфейсе (маска, поля)
LORAS_DIR = ROOT / "models" / "loras"
CATALOG = ROOT / "config" / "loras.yaml"
BASE_BY_WORKFLOW = {"krea2_t2i": "krea2", "krea2_identity": "krea2", "klein_t2i": "klein", "klein_edit": "klein", "sdxl_t2i": "sdxl"}

SYSTEM = """You route a request from a user of a local AI image/video studio to the single best preset, and pick add-on LoRAs.
The user writes in Russian, in their own words, often vaguely. Read the preset descriptions and pick the one that best fits what they want to GET.
Rules:
- Wants a video, animation, motion, "оживи", "видео", "ролик" -> a video preset. If an image is attached and they want it to move -> the image-to-video preset.
- An image is attached and they want to change something in it (add, remove, replace, recolor, change background/time of day) -> the edit preset.
- An image of a person is attached and they want the same person in a new place, pose or outfit -> the character preset.
- Enlarge / sharpen / "увеличь", "качество", "резкость" of an attached image -> upscale; remove or delete the background ("убери фон") -> nobg;
  fix face or hands -> detail; 3D model -> to-3d. These are not edits.
- A painting, illustration or art style is named -> the matching art preset; anime/manga -> anime. Otherwise realistic photos -> the realistic photo preset.
- Pick an [18+] preset only when the request is explicitly sexual, nude or erotic.
- Never pick a preset marked [needs image] unless images are attached.
Aspect: vertical portraits, people full-height, phone/stories -> 2:3 or 9:16; landscapes, scenes, groups, cinematic -> 3:2 or 16:9; avatars, icons, products -> 1:1.
LoRAs: only for presets marked [loras: ...]; choose 0-2 from that list whose description matches the wanted look; [] if none fits or unsure.
reason_ru: 4-12 words in Russian, why this preset (and LoRA)."""


def _header_meta(path):
    try:
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            return json.loads(f.read(n)).get("__metadata__") or {}
    except Exception:
        return {}


def _norm_base(s):
    s = (s or "").lower().replace(" ", "")
    return "krea2" if "krea2" in s else "klein" if ("klein" in s or "flux.3" in s or "flux3" in s) else \
        "sdxl" if any(k in s for k in ("sdxl", "illustrious", "pony", "noobai")) else None


def lora_catalog():
    """Доступные для автоподбора LoRA: {file: {base, weight, trigger, label, when}}."""
    try:
        cfg = {x["file"]: x for x in yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or []}
    except Exception:
        cfg = {}
    out = {}
    for f in sorted(LORAS_DIR.glob("*.safetensors")):  # подпапка characters — LoRA персонажей, у них свои пресеты
        c = dict(cfg.get(f.name) or {})
        if c.get("skip"):
            continue
        if not c.get("base") or not c.get("when"):  # новая LoRA: берём что есть из .meta.json и заголовка файла
            meta = {}
            try:
                meta = json.loads(f.with_name(f.name + ".meta.json").read_text(encoding="utf-8"))
            except Exception:
                pass
            hm = _header_meta(f)
            c.setdefault("base", _norm_base(meta.get("base_model") or hm.get("ss_base_model_version")))
            c.setdefault("when", (meta.get("description") or meta.get("name") or f.stem).replace("\n", " ")[:160])
            if not c.get("trigger") and meta.get("trained_words"):
                c["trigger"] = meta["trained_words"][0]
        if c.get("base"):
            out[f.name] = {"base": c["base"], "weight": float(c.get("weight", 0.8)), "trigger": c.get("trigger"),
                           "label": c.get("label") or f.stem, "when": c["when"]}
    return out


def preset_loras(p, catalog):
    """Какие LoRA из каталога можно добавить к пресету: та же базовая модель, и у пресета нет своей стилевой LoRA."""
    base = BASE_BY_WORKFLOW.get(p.get("workflow"))
    own = [l[0] for l in (p.get("params") or {}).get("loras") or []]
    # к рисованным стилям фото-LoRA не добавляем; к переносу персонажа — тоже: любая LoRA реализма снижает сходство лица
    # (замер ArcFace 2026-11-27: Vérité 0.6 — сходство 0.28 против 0.34 без неё)
    if not base or p.get("workflow") == "krea2_identity" or p.get("group") in ("Арт", "Аниме") or any(o not in catalog for o in own):
        return []
    return [f for f, c in catalog.items() if c["base"] == base]


def choose(text, cands, n_images=0, nsfw=False, ref_kind=None):
    """{preset, aspect, reason, loras:[file]} — cands: пресеты, подходящие по вложениям."""
    from ..server.presets import ASPECTS
    if not cands:
        raise ValueError("Не нашлось подходящей модели для этих вложений.")
    cat = lora_catalog()
    lines, used = [], set()
    for p in cands:
        tags = (" [needs image]" if p.get("requires") in ("image", "images2") else "") + (" [needs video]" if p.get("requires") == "video" else "")
        tags += " [video output]" if p.get("media") == "video" else (" [3D output]" if p.get("media") == "3d" else "")
        tags += " [18+]" if p.get("nsfw") else ""
        pl = preset_loras(p, cat)
        if pl:
            tags += f" [loras: {', '.join(pl)}]"
            used.update(pl)
        lines.append(f"- {p['id']}: {p.get('name')} / group {p.get('group')}{tags} — {(p.get('description') or '').strip()}")
    lora_txt = ("\nLoRA descriptions:\n" + "\n".join(f"- {f}: {cat[f]['when']}" for f in sorted(used))) if used else ""
    att = f"{n_images} {'video' if ref_kind == 'video' else 'image'}(s) attached" if n_images else "no attachments"
    schema = {"type": "object", "properties": {
        "preset": {"type": "string", "enum": [p["id"] for p in cands]},
        "aspect": {"type": "string", "enum": list(ASPECTS)},
        "loras": {"type": "array", "items": {"type": "string", "enum": sorted(used) or ["none"]}, "maxItems": 2},
        "reason_ru": {"type": "string"}}, "required": ["preset", "aspect", "loras", "reason_ru"]}
    payload = {"model": prompter.pick_model(nsfw), "stream": False, "think": False, "keep_alive": 0, "format": schema,
               "options": {"temperature": 0}, "messages": [
                   {"role": "system", "content": SYSTEM},
                   {"role": "user", "content": f"Request: {text}\nAttachments: {att}\nPresets:\n" + "\n".join(lines) + lora_txt}]}
    out = json.loads(prompter._ollama("/api/chat", payload, timeout=120)["message"]["content"])
    ids = {p["id"]: p for p in cands}
    pid = out.get("preset") if out.get("preset") in ids else cands[0]["id"]
    ok = set(preset_loras(ids[pid], cat))
    loras = [f for f in dict.fromkeys(out.get("loras") or []) if f in ok]
    return {"preset": pid, "aspect": out.get("aspect") if out.get("aspect") in ASPECTS else "2:3",
            "reason": (out.get("reason_ru") or "").strip(), "loras": loras}


def lora_params(p, files):
    """LoRA для запроса генерации (заменяют LoRA пресета) + слова-триггеры для промпта."""
    cat = lora_catalog()
    ok = set(preset_loras(p, cat))
    files = [f for f in files if f in ok]
    return ([{"name": f, "weight": cat[f]["weight"], "label": cat[f]["label"]} for f in files],
            [cat[f]["trigger"] for f in files if cat[f].get("trigger")])


def candidates(all_presets, images, ref_kind, allow_nsfw):
    out = []
    for p in all_presets:
        req = p.get("requires")
        if p.get("error") or p["id"] in SKIP or (p.get("nsfw") and not allow_nsfw):
            continue
        if p.get("hidden") and not (images and req):  # скрытые «инструменты» (апскейл, фон, лицо) — только для прикреплённой картинки
            continue
        if not images and req:
            continue
        if images and ref_kind == "video" and req != "video":
            continue
        if images and ref_kind != "video" and req == "video":
            continue
        if req == "images2" and len(images) < 2:
            continue
        out.append(p)
    return out
