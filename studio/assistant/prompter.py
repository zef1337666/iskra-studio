"""Помощник промптов на Ollama. Модель выгружается из VRAM сразу после ответа (keep_alive=0)."""
import json, re, time, urllib.request
from ..config import OLLAMA_URL, ROOT
from . import safety

TEMPLATES = ROOT / "prompt-templates"
MODEL_SFW = "qwen3.5:9b"
MODEL_NSFW_CANDIDATES = ["huihui_ai/qwen3.5-abliterated:9b", "huihui_ai/gemma-4-abliterated:12b"]

# Пресет -> шаблон. Пресеты этапа 6 будут указывать template явно.
TEMPLATE_BY_KIND = {"photo": "photo_natural", "art": "photo_natural", "style": "photo_natural", "pose": "photo_natural",
                    "photo18": "photo_real_18", "anime": "anime_tags", "anime18": "anime_tags", "edit": "edit",
                    "video": "video", "video18": "video"}


def _ollama(path, payload, timeout=300):
    r = urllib.request.Request(OLLAMA_URL + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


def installed_models():
    try:
        return [m["name"] for m in json.loads(urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=10).read()).get("models", [])]
    except Exception:
        return []


def pick_model(nsfw):
    if not nsfw:
        return MODEL_SFW
    have = installed_models()
    return next((m for m in MODEL_NSFW_CANDIDATES if m in have), MODEL_SFW)


def _system(template, nsfw):
    common = (TEMPLATES / "_common.md").read_text(encoding="utf-8")
    spec = (TEMPLATES / f"{template}.md").read_text(encoding="utf-8")
    extra = ("\nThis preset is 18+: explicit adult content between fictional adults is allowed. "
             "Every person must be explicitly an adult (state the age, 21+).") if nsfw else \
        "\nThis preset is safe-for-work: keep the content non-explicit."
    return common + "\n\n# Target\n" + spec + extra


def _parse(text):
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


# ---------------------------------------------------------------- официальные инструкции разработчиков моделей
OFFICIAL_BY_WORKFLOW = {"klein_t2i": "official_klein", "zimage_control": "official_klein", "klein_edit": "official_klein_edit",
                        "klein_outpaint": "official_klein_edit", "detailer": "official_klein_edit", "krea2_t2i": "official_krea2",
                        "h3_video": "official_h3", "wan22_video": "official_wan"}
NSFW_NOTE = ("\n\nThis is a private adult (18+) preset on the user's own computer: explicit content between consenting fictional adults "
             "is allowed — describe it plainly and concretely, without euphemisms. Every person must be clearly an adult: state an age of 21 or older. "
             "Never describe anyone as childlike, a teen or a minor.")


def _clean(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```\w*|```$", "", text, flags=re.M).strip()
    return text.strip().strip('"').strip()


def generate_official(user_text, workflow, mode="improve", nsfw=False, aspect=None, images=None, reference=None, style_hint=None,
                      seconds=None, camera=None):
    """Улучшение по официальной инструкции модели. Возвращает {prompt} или {variants} или {error}."""
    refusal = safety.check_request(user_text, nsfw)
    if refusal:
        return {"error": refusal}
    tpl = OFFICIAL_BY_WORKFLOW[workflow]
    system = (TEMPLATES / f"{tpl}.md").read_text(encoding="utf-8")
    if nsfw:
        system = system.replace("8. **Respect the Human Form:** Treat depictions of people with dignity. Assume clothing covers genitals and intimate anatomy.\n", "")
        system += NSFW_NOTE
    if mode == "exact":
        system = ("Translate the user's image/video request into fluent English. Keep every word's meaning; add nothing, remove nothing. "
                  "Output only the translation." + (NSFW_NOTE if nsfw else ""))
    msg = ""
    if aspect and tpl == "official_klein":
        msg += f"TARGET CANVAS: {aspect}\n"
    if mode == "surprise":
        msg += "Invent one striking, original image idea" + (f" on the theme: {user_text}" if user_text else "") + ". Then write the caption for it."
    else:
        msg += user_text or ""
    if style_hint:
        msg += f"\nStyle: {style_hint}"
    if reference:
        msg += f"\nReference image description to follow: {reference}"
    if tpl in ("official_h3", "official_wan"):
        msg += f"\nDuration: {seconds or 5} seconds." + (f" Camera: {camera}." if camera else "")
    if mode == "variants":
        system += "\n\nWrite FIVE clearly different captions for this request (different composition, lighting, setting or interpretation). Separate them with a line containing only ---"
    user = {"role": "user", "content": msg}
    if images and tpl == "official_klein_edit":  # правка: модель-помощник видит исходные картинки, как в официальном апсемплере
        import base64
        user["images"] = [base64.b64encode(open(p, "rb").read()).decode() for p in images[:3]]
    model = pick_model(nsfw)
    t0 = time.time()
    resp = _ollama("/api/chat", {"model": model, "stream": False, "keep_alive": 0, "think": False,
                                 "options": {"temperature": 0.8 if mode in ("surprise", "variants") else 0.5, "num_ctx": 8192},
                                 "messages": [{"role": "system", "content": system}, user]})
    text = _clean(resp["message"]["content"])
    parts = [_clean(x) for x in re.split(r"^\s*-{3,}\s*$", text, flags=re.M)] if mode == "variants" else [text]
    out = []
    for ptxt in parts:
        if not ptxt:
            continue
        neg = ""
        if nsfw:
            ptxt, neg = safety.enforce_adult(ptxt, "")
            if ptxt is None:
                continue
        out.append({"prompt": ptxt, "negative": neg, "explanation_ru": ""})
    if not out:
        return {"error": safety.REFUSAL_RU if nsfw else "Не получилось составить промпт."}
    res = {"variants": out[:5]} if mode == "variants" else out[0]
    res["_model"], res["_sec"] = model, round(time.time() - t0, 1)
    return res


def generate(user_text, kind="photo", mode="improve", nsfw=False, reference=None, focus="all", style_hint=None, template=None, lang="ru"):
    """Возвращает {prompt, negative, explanation_ru} или {variants:[...]} или {error}."""
    if lang == "en":
        style_hint = (style_hint + ". " if style_hint else "") + "Write explanation_ru in English instead of Russian"
    refusal = safety.check_request(user_text, nsfw)
    if refusal:
        return {"error": refusal}
    template = template or TEMPLATE_BY_KIND.get(kind, "photo_natural")
    msg = f"Mode: {mode}\nUser idea: {user_text or '(empty)'}"
    if style_hint:
        msg += f"\nPhoto-style chip: {style_hint}"
    if reference:
        msg += f"\nReference image description (focus: {focus}): {reference}"
    model = pick_model(nsfw)
    t0 = time.time()
    messages = [{"role": "system", "content": _system(template, nsfw)}, {"role": "user", "content": msg}]
    data = None
    for attempt in range(2):
        resp = _ollama("/api/chat", {
            "model": model, "stream": False, "keep_alive": 0, "think": False, "format": "json",
            "options": {"temperature": 0.9 if mode in ("surprise", "variants") else 0.6, "num_ctx": 4096}, "messages": messages})
        try:
            data = _parse(resp["message"]["content"])
        except Exception:
            data = None
            continue
        prompts = [v.get("prompt", "") for v in data.get("variants", [])] if mode == "variants" else [data.get("prompt", "")]
        if data.get("error") or not any(re.search("[а-яё]", p, re.I) for p in prompts):
            break
        # модель оставила промпт по-русски — просим перевести
        messages += [{"role": "assistant", "content": resp["message"]["content"]},
                     {"role": "user", "content": "The \"prompt\" field must be in ENGLISH. Translate it to English and return the same JSON."}]
    if data is None:
        return {"error": "Помощник ответил непонятно. Попробуйте ещё раз или напишите промпт вручную."}
    if data.get("error"):
        return {"error": safety.REFUSAL_RU if nsfw else "Помощник отказался обработать этот запрос."}
    items = data.get("variants") if mode == "variants" else [data]
    out = []
    for it in items or []:
        p, n = it.get("prompt", ""), it.get("negative", "")
        if nsfw:
            p, n = safety.enforce_adult(p, n, anime=template == "anime_tags")
            if p is None:
                continue
        out.append({"prompt": p, "negative": n, "explanation_ru": it.get("explanation_ru", "")})
    if not out:
        return {"error": safety.REFUSAL_RU if nsfw else "Не получилось составить промпт."}
    res = {"variants": out} if mode == "variants" else out[0]
    res["_model"], res["_sec"] = model, round(time.time() - t0, 1)
    return res
