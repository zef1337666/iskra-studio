"""Настройки, персонажи, коллекции, уведомления Windows, логи, экспорт zip."""
import hashlib, io, json, re, subprocess, time, zipfile
from ..config import DATA, OUTPUT
from . import db

SETTINGS_FILE = DATA / "settings.json"
DEFAULTS = {"default_mode": "quality", "save_format": "png", "jpg_quality": 92, "keep_metadata": True, "explain_lang": "ru",
            "notify_windows": True, "pin_hash": None, "onboarded": False, "night_mode": False,
            "phone_access": False, "phone_pass_hash": None, "telegram_enabled": False, "telegram_chat_id": None}
SECRET_KEYS = ("pin_hash", "phone_pass_hash")


def get_settings():
    s = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        try:
            s.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return s


def public_settings():
    s = get_settings()
    s["pin_set"] = bool(s.pop("pin_hash"))
    s["phone_pass_set"] = bool(s.pop("phone_pass_hash"))
    return s


def save_settings(patch):
    s = get_settings()
    for k, v in patch.items():
        if k in DEFAULTS and k not in SECRET_KEYS:
            s[k] = v
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return public_settings()


def reset_settings():
    pin = get_settings().get("pin_hash")
    SETTINGS_FILE.write_text(json.dumps({**DEFAULTS, "pin_hash": pin, "onboarded": True}, ensure_ascii=False), encoding="utf-8")
    return public_settings()


def _h(pin):
    return hashlib.sha256(("iskra:" + str(pin)).encode()).hexdigest()


def set_pin(pin, old=None):
    s = get_settings()
    if s.get("pin_hash") and _h(old or "") != s["pin_hash"]:
        raise ValueError("Старый PIN неверный.")
    if pin and not re.fullmatch(r"\d{4,8}", str(pin)):
        raise ValueError("PIN — от 4 до 8 цифр.")
    s["pin_hash"] = _h(pin) if pin else None
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def check_pin(pin):
    h = get_settings().get("pin_hash")
    return (not h) or _h(pin or "") == h


# ---------------------------------------------------------------- доступ с телефона
import hmac, secrets, socket  # noqa: E402

_SESSION_SECRET = secrets.token_hex(16)


def set_phone_password(pw):
    if len(pw or "") < 6:
        raise ValueError("Пароль — минимум 6 символов.")
    s = get_settings()
    s["phone_pass_hash"] = hashlib.sha256(("iskra-phone:" + pw).encode()).hexdigest()
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def phone_login(pw):
    h = get_settings().get("phone_pass_hash")
    if not h or not hmac.compare_digest(h, hashlib.sha256(("iskra-phone:" + (pw or "")).encode()).hexdigest()):
        return None
    return session_token()


def session_token():
    h = get_settings().get("phone_pass_hash") or ""
    return hmac.new(_SESSION_SECRET.encode(), h.encode(), "sha256").hexdigest()


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 80))  # без отправки пакетов: просто узнать свой адрес в сети
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith(("192.168.", "10.", "172.")):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


# ---------------------------------------------------------------- Telegram
def telegram_send(text, chat_id=None):
    from ..config import load_env
    import urllib.request, urllib.parse
    token = load_env().get("TELEGRAM_BOT_TOKEN")
    chat = chat_id or get_settings().get("telegram_chat_id")
    if not token or not chat:
        raise ValueError("Telegram не настроен: нужен токен бота и чат.")
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15)


def telegram_detect():
    """Находит чат: пользователь пишет боту /start, мы берём chat_id из последнего сообщения."""
    from ..config import load_env
    import urllib.request
    token = load_env().get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("Сначала сохраните токен бота.")
    d = json.loads(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15).read())
    chats = [u["message"]["chat"] for u in d.get("result", []) if u.get("message")]
    if not chats:
        raise ValueError("Бот пока не получил сообщений. Откройте бота в Telegram, нажмите «Start» и повторите.")
    chat = chats[-1]
    s = get_settings()
    s["telegram_chat_id"], s["telegram_enabled"] = chat["id"], True
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"chat_id": chat["id"], "name": chat.get("first_name") or chat.get("title")}


# ---------------------------------------------------------------- уведомления Windows (+ Telegram)
def notify(title, text):
    s = get_settings()
    if s.get("telegram_enabled") and s.get("telegram_chat_id"):
        import threading
        threading.Thread(target=lambda: _safe(telegram_send, f"{title}\n{text}"), daemon=True).start()
    if not s.get("notify_windows"):
        return
    t = title.replace("'", "").replace("\n", " ")
    b = text.replace("'", "").replace("\n", " ")
    ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
          "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
          f"$t = $x.GetElementsByTagName('text'); $t.Item(0).AppendChild($x.CreateTextNode('{t}')) > $null; $t.Item(1).AppendChild($x.CreateTextNode('{b}')) > $null;"
          "$n = [Windows.UI.Notifications.ToastNotification]::new($x);"
          "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($n)")
    subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps], creationflags=0x08000000)


def _safe(fn, *a):
    try:
        fn(*a)
    except Exception:
        pass


# ---------------------------------------------------------------- персонажи и коллекции (таблицы в той же БД)
def _init():
    c = db.conn()
    c.executescript("""CREATE TABLE IF NOT EXISTS characters (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT,
                       refs TEXT, cover TEXT, created REAL);""")
    return c


def characters():
    rows = _init().execute("SELECT * FROM characters ORDER BY id DESC").fetchall()
    return [dict(r, refs=json.loads(r["refs"] or "[]")) for r in rows]


def save_character(ch):
    c = _init()
    refs = json.dumps(ch.get("refs") or [], ensure_ascii=False)
    if ch.get("id"):
        c.execute("UPDATE characters SET name=?, description=?, refs=?, cover=? WHERE id=?",
                  (ch["name"], ch.get("description", ""), refs, ch.get("cover"), ch["id"]))
    else:
        cur = c.execute("INSERT INTO characters (name, description, refs, cover, created) VALUES (?,?,?,?,?)",
                        (ch["name"], ch.get("description", ""), refs, ch.get("cover"), time.time()))
        ch["id"] = cur.lastrowid
    c.commit()
    return next(x for x in characters() if x["id"] == ch["id"])


def delete_character(cid):
    c = _init()
    c.execute("DELETE FROM characters WHERE id=?", (cid,))
    c.commit()


def collections():
    rows = db.conn().execute("""SELECT c.id, c.name, COUNT(ci.item_id) n, MAX(ci.item_id) last FROM collections c
                                LEFT JOIN collection_items ci ON ci.collection_id=c.id GROUP BY c.id ORDER BY c.name""").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        it = db.get_item(d["last"]) if d["last"] else None
        d["cover"] = it["thumb"] if it else None
        out.append(d)
    return out


def create_collection(name):
    c = db.conn()
    c.execute("INSERT OR IGNORE INTO collections (name, created) VALUES (?, ?)", (name.strip(), time.time()))
    c.commit()
    return next(x for x in collections() if x["name"] == name.strip())


def add_to_collection(cid, ids):
    c = db.conn()
    c.executemany("INSERT OR IGNORE INTO collection_items VALUES (?, ?)", [(cid, int(i)) for i in ids])
    c.commit()


def delete_collection(cid):
    c = db.conn()
    c.execute("DELETE FROM collection_items WHERE collection_id=?", (cid,))
    c.execute("DELETE FROM collections WHERE id=?", (cid,))
    c.commit()


def export_zip(ids):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for i in ids:
            it = db.get_item(int(i))
            if it and (OUTPUT / it["path"]).exists():
                z.write(OUTPUT / it["path"], f"{it['id']}_{(OUTPUT / it['path']).name}")
    buf.seek(0)
    return buf


# ---------------------------------------------------------------- логи человеческим языком
LOG_PATTERNS = [
    (r"out of memory|OutOfMemory|allocation on device", "Не хватило видеопамяти"),
    (r"Prompt executed in ([\d.]+) seconds", "Задача выполнена за {0} с"),
    (r"got prompt", "Получена новая задача"),
    (r"Traceback|Exception|Error", "Ошибка в движке (подробности в отчёте)"),
    (r"Starting server|To see the GUI go to", "Движок запущен"),
    (r"Loading .*?model|loaded completely|Requested to load (\w+)", "Загрузка модели {0}"),
]


def human_logs(name="comfy", n=80):
    f = DATA / ("comfy.log" if name == "comfy" else "ollama.log" if name == "ollama" else "server.log")
    if not f.exists():
        return []
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]
    out = []
    for ln in lines:
        for pat, ru in LOG_PATTERNS:
            m = re.search(pat, ln)
            if m:
                out.append({"text": ru.format(*[g or "" for g in m.groups()]) if m.groups() else ru, "raw": ln[-300:],
                            "level": "error" if "Ошибка" in ru or "видеопамяти" in ru else "info"})
                break
    return out[-n:]


def error_report():
    parts = [f"Отчёт «Искра» {time.strftime('%Y-%m-%d %H:%M')}"]
    for name in ("comfy", "server", "ollama"):
        f = DATA / ("comfy.log" if name == "comfy" else f"{name}.log")
        if f.exists():
            tail = f.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
            parts.append(f"\n===== {name} (последние строки) =====\n" + "\n".join(tail))
    txt = "\n".join(parts)
    return re.sub(r"(hf_[A-Za-z0-9]{10,}|Bearer [A-Za-z0-9._-]+|token=[A-Za-z0-9]+)", "***", txt)  # ключи не попадают в отчёт


def bench_table():
    f = DATA / "bench.jsonl"
    rows = {}
    if f.exists():
        for ln in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                rows[(r["workflow"], r["mode"])] = r
            except Exception:
                pass
    return [{"workflow": k[0], "mode": k[1], "sec": v["sec"], "vram_mb": v["peak_vram_mb"], "time": v["time"]} for k, v in sorted(rows.items())]
