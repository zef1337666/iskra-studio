"""ИИ учится на ваших оценках и исправлениях.

Удачно: ♥, 4–5 звёзд, продолжение работы с результатом (правка, оживление, персонаж из него).
Неудачно: 1–2 звезды, удаление. Исправления: «Вернуть» и ручная смена модели сразу после выбора ИИ.
Похожие прошлые случаи (по словам запроса) подсказываются ИИ при выборе модели, LoRA и формата — с каждым разом точнее под ваш вкус.
"""
import json, re, time
from ..config import DATA

FILE = DATA / "learning.json"


def _words(t):
    return {w[:5] for w in re.findall(r"[a-zа-яё0-9]{3,}", (t or "").lower())}


def _sim(a, b):
    A, B = _words(a), _words(b)
    return len(A & B) / (len(A | B) or 1)


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"corrections": []}


def record_correction(text, ai, wanted):
    if not text or not ai or not wanted or ai == wanted:
        return
    d = _load()
    d["corrections"] = (d.get("corrections", []) + [{"text": text[:300], "ai": ai, "wanted": wanted, "t": time.time()}])[-300:]
    FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def _feedback():
    from ..server import db
    c = db.conn()
    parents = {r[0] for r in c.execute("SELECT DISTINCT parent_id FROM items WHERE parent_id IS NOT NULL")}
    out = []
    for r in c.execute("SELECT id, preset, user_text, params, favorite, rating, deleted, width, height FROM items "
                       "WHERE user_text IS NOT NULL AND user_text != ''"):
        rating = r["rating"] or 0
        score = (2 if r["favorite"] else 0) + (1 if rating >= 4 else -2 if 1 <= rating <= 2 else 0) \
            + (1 if r["id"] in parents else 0) - (2 if r["deleted"] else 0)
        if score:
            out.append((score, dict(r)))
    return out


def context(text, k=5):
    """(блок текста для ИИ, сколько случаев учтено) — похожие удачные/неудачные генерации и исправления пользователя."""
    if not text:
        return "", 0
    lines = []
    fb = sorted(((s, _sim(text, r["user_text"]), r) for s, r in _feedback()), key=lambda x: -x[1])
    good = [x for x in fb if x[0] > 0 and x[1] >= 0.12][:k]
    bad = [x for x in fb if x[0] < 0 and x[1] >= 0.12][:3]
    for s, _, r in good:
        loras = [l[0] if isinstance(l, list) else l.get("name") for l in (json.loads(r["params"] or "{}").get("loras") or [])]
        lines.append(f"- liked: «{r['user_text'][:120]}» -> preset {r['preset']}" + (f", LoRAs {loras}" if loras else "")
                     + (f", {r['width']}x{r['height']}" if r.get("width") else ""))
    for s, _, r in bad:
        lines.append(f"- disliked: «{r['user_text'][:120]}» -> preset {r['preset']}")
    for sim, c in sorted(((_sim(text, c["text"]), c) for c in _load().get("corrections", [])), key=lambda x: -x[0])[:3]:
        if sim >= 0.15:
            lines.append(f"- the user corrected you: for «{c['text'][:120]}» use preset {c['wanted']}, not {c['ai']}")
    if not lines:
        return "", 0
    return ("\nThis user's past feedback on similar requests (it reflects their taste — follow it unless the request clearly differs):\n"
            + "\n".join(lines)), len(lines)


def stats():
    fb = _feedback()
    return {"liked": sum(1 for s, _ in fb if s > 0), "disliked": sum(1 for s, _ in fb if s < 0),
            "corrections": len(_load().get("corrections", []))}
