"""Запуск workflow студии с замером времени и пиковой VRAM.
python bench.py <workflow> <draft|quality> '<json params>' [повторов]
"""
import json, subprocess, sys, threading, time, urllib.request, pathlib
sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio.engine.workflows import REGISTRY  # noqa

URL = "http://127.0.0.1:8188"


def req(path, data=None):
    r = urllib.request.Request(URL + path, data=json.dumps(data).encode() if data is not None else None,
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r).read())


def vram_used():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True)
    return int(out.stdout.strip().splitlines()[0])


def run(name, mode, params):
    wf = REGISTRY[name](params, mode)
    peak, stop = [0], threading.Event()

    def poll():
        while not stop.is_set():
            peak[0] = max(peak[0], vram_used())
            time.sleep(0.5)
    th = threading.Thread(target=poll, daemon=True)
    th.start()
    t = time.time()
    try:
        pid = req("/prompt", {"prompt": wf})["prompt_id"]
    except urllib.error.HTTPError as e:
        stop.set()
        print("ОШИБКА ГРАФА:", e.read().decode("utf-8", "replace")[:1500])
        return None
    while True:
        h = req(f"/history/{pid}")
        st = h.get(pid, {}).get("status", {})
        if st.get("completed") or st.get("status_str") == "error":
            break
        time.sleep(0.3)
    stop.set()
    dt = time.time() - t
    if st.get("status_str") == "error":
        msgs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
        err = msgs[0][1] if msgs else st
        print("ОШИБКА:", json.dumps({k: err.get(k) for k in ("node_type", "exception_message")} if isinstance(err, dict) else err, ensure_ascii=False)[:1500])
        return None
    files = [f"{i.get('subfolder')}/{i['filename']}" for o in h[pid]["outputs"].values() for k in ("images", "gifs", "videos", "audio", "3d") for i in o.get(k, []) if isinstance(i, dict) and "filename" in i]
    rec = {"workflow": name, "mode": mode, "sec": round(dt, 1), "peak_vram_mb": peak[0], "files": files, "time": time.strftime("%Y-%m-%d %H:%M")}
    with open(ROOT / "data" / "bench.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"{name} [{mode}] {dt:.1f} c, пик VRAM {peak[0]} МБ -> {files}")
    return rec


if __name__ == "__main__":
    name, mode = sys.argv[1], sys.argv[2]
    a = sys.argv[3] if len(sys.argv) > 3 else "{}"
    params = json.loads(pathlib.Path(a[1:]).read_text(encoding="utf-8-sig") if a.startswith("@") else a)
    for _ in range(int(sys.argv[4]) if len(sys.argv) > 4 else 1):
        run(name, mode, params)
