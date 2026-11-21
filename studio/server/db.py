"""SQLite: история результатов, коллекции. Один файл data/studio.db."""
import json, sqlite3, threading, time
from ..config import DATA

DB_PATH = DATA / "studio.db"
_lock = threading.Lock()
_conn = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL,            -- относительно data/output
  thumb TEXT,                    -- относительно data/thumbs
  kind TEXT NOT NULL,            -- image | video | 3d
  preset TEXT, preset_name TEXT, model TEXT, mode TEXT,
  prompt TEXT, negative TEXT, user_text TEXT, seed INTEGER,
  width INTEGER, height INTEGER, params TEXT,
  nsfw INTEGER DEFAULT 0, favorite INTEGER DEFAULT 0, rating INTEGER DEFAULT 0,
  deleted INTEGER DEFAULT 0, parent_id INTEGER, job_sec REAL,
  created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS items_created ON items(created DESC);
CREATE TABLE IF NOT EXISTS collections (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, created REAL);
CREATE TABLE IF NOT EXISTS collection_items (collection_id INTEGER, item_id INTEGER, PRIMARY KEY(collection_id, item_id));
"""


def conn():
    global _conn
    if _conn is None:
        DATA.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
    return _conn


def _row(r):
    d = dict(r)
    d["params"] = json.loads(d["params"]) if d.get("params") else {}
    for k in ("nsfw", "favorite", "deleted"):
        d[k] = bool(d.get(k))
    return d


def add_item(**kw):
    kw.setdefault("created", time.time())
    if isinstance(kw.get("params"), dict):
        kw["params"] = json.dumps(kw["params"], ensure_ascii=False)
    cols = ",".join(kw)
    with _lock:
        cur = conn().execute(f"INSERT INTO items ({cols}) VALUES ({','.join('?' * len(kw))})", list(kw.values()))
        conn().commit()
        return get_item(cur.lastrowid)


def get_item(item_id):
    r = conn().execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return _row(r) if r else None


def list_items(before=None, limit=60, kind=None, preset=None, favorite=None, q=None, nsfw=True, deleted=False, min_rating=None, collection=None):
    where, args = ["deleted=?"], [1 if deleted else 0]
    if before:
        where.append("id<?"); args.append(int(before))
    if kind:
        where.append("kind=?"); args.append(kind)
    if preset:
        where.append("preset=?"); args.append(preset)
    if favorite:
        where.append("favorite=1")
    if min_rating:
        where.append("rating>=?"); args.append(int(min_rating))
    if not nsfw:
        where.append("nsfw=0")
    if q:
        where.append("(prompt LIKE ? OR user_text LIKE ?)"); args += [f"%{q}%", f"%{q}%"]
    if collection:
        where.append("id IN (SELECT item_id FROM collection_items WHERE collection_id=?)"); args.append(int(collection))
    rows = conn().execute(f"SELECT * FROM items WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?", args + [int(limit)]).fetchall()
    return [_row(r) for r in rows]


def update_item(item_id, **kw):
    allowed = {k: v for k, v in kw.items() if k in ("favorite", "rating", "deleted", "nsfw")}
    if not allowed:
        return get_item(item_id)
    with _lock:
        conn().execute(f"UPDATE items SET {','.join(f'{k}=?' for k in allowed)} WHERE id=?", [int(v) for v in allowed.values()] + [item_id])
        conn().commit()
    return get_item(item_id)


def stats():
    r = conn().execute("SELECT COUNT(*) n, SUM(kind='image') img, SUM(kind='video') vid, SUM(kind='3d') m3d FROM items WHERE deleted=0").fetchone()
    return dict(r)
