"""Чат с ИИ внутри студии: пользователь пишет своими словами, что ему нужно, ИИ отвечает по-русски и предлагает подходящие пресеты."""
import json
from . import learning, prompter, router, safety

SYSTEM = """Ты — дружелюбный помощник локальной ИИ-студии «Искра» (фото, видео, правка картинок, 3D). Пользователь может быть новичком.
Отвечай по-русски, коротко и по делу: 1–3 предложения в поле reply, без списков и без технических терминов.
Задача: понять, что человек хочет получить, и предложить 1–3 подходящих пресета из списка ниже (поле suggestions).
- Если запрос понятен — сразу предлагай пресеты. Для каждого: why — зачем он подходит (3–10 слов), idea — готовое описание
  картинки или видео, как если бы его вписали в генератор: по-русски, 1–2 предложения, конкретно (кто, как выглядит, что делает, где,
  стиль, свет), с деталями из разговора, а чего не хватает — придумай сам красиво. Без обращений к пользователю («опишите», «выберите»).
  Пример idea: «Аниме-портрет парня с серебристыми волосами в чёрной куртке на фоне неонового ночного города, мягкий розовый свет».
  Для оживления фото idea — движение: «Человек на фото медленно улыбается и смотрит в камеру, лёгкий ветер шевелит волосы».
- Пресет с пометкой [needs image] работает только с прикреплённой картинкой: если её нет — попроси прикрепить фото (кнопка «+» или перетащить).
- Если просьба неясна — задай один уточняющий вопрос (и можешь сразу предложить 1–2 варианта).
- Можно подсказать режим: «Черновик» — быстро, «Качество» — лучше, но дольше.
- Предлагай только пресеты из списка, по их id."""


def reply(messages, images, ref_kind, allow_nsfw, all_presets):
    user_text = " ".join(m["content"] for m in messages if m["role"] == "user")
    nsfw = allow_nsfw and not safety.check_request(user_text, True)  # о несовершеннолетних — только обычные пресеты и обычная модель
    cands = router.candidates(all_presets, images, ref_kind, nsfw)
    ids = {p["id"]: p for p in cands}
    lines = []
    for p in cands:
        tags = (" [needs image]" if p.get("requires") in ("image", "images2") else "") + (" [needs video]" if p.get("requires") == "video" else "")
        tags += " [18+]" if p.get("nsfw") else ""
        lines.append(f"- {p['id']}: «{p.get('name')}» ({p.get('group')}){tags} — {(p.get('description') or '').strip()}")
    system = SYSTEM + "\n\nПресеты:\n" + "\n".join(lines)
    system += f"\n\nСейчас прикреплено: {len(images)} {'видео' if ref_kind == 'video' else 'картинок'}." if images else "\n\nСейчас ничего не прикреплено."
    learned, _ = learning.context(user_text)  # похожие прошлые случаи: что понравилось и что пользователь исправлял
    system += learned
    if nsfw:
        system += ("\nРаздел 18+ открыт: откровенный контент с вымышленными взрослыми разрешён. Пресеты [18+] предлагай только на откровенные "
                   "просьбы. Ничего, связанного с несовершеннолетними.")
    schema = {"type": "object", "properties": {
        "reply": {"type": "string"},
        "suggestions": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
            "preset": {"type": "string", "enum": list(ids)}, "why": {"type": "string"}, "idea": {"type": "string"}},
            "required": ["preset", "why", "idea"]}}},
        "required": ["reply", "suggestions"]}
    payload = {"model": prompter.pick_model(nsfw), "stream": False, "think": False, "keep_alive": 0, "format": schema,
               "options": {"temperature": 0.4},
               "messages": [{"role": "system", "content": system}] + [{"role": m["role"], "content": m["content"]} for m in messages[-12:]]}
    out = json.loads(prompter._ollama("/api/chat", payload, timeout=180)["message"]["content"])
    sug = []
    for s in out.get("suggestions") or []:
        p = ids.get(s.get("preset"))
        if p and p["id"] not in {x["preset"] for x in sug}:
            sug.append({"preset": p["id"], "name": p.get("name"), "nsfw": bool(p.get("nsfw")), "requires": p.get("requires"),
                        "why": (s.get("why") or "").strip(), "idea": (s.get("idea") or "").strip()})
    return {"reply": (out.get("reply") or "").strip() or "Вот что могу предложить:", "suggestions": sug}
