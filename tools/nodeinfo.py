"""Печатает входы/выходы нод ComfyUI: python nodeinfo.py NodeA NodeB ..."""
import json, sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
for _ in range(90):
    try:
        info = json.loads(urllib.request.urlopen("http://127.0.0.1:8188/object_info").read())
        break
    except Exception:
        time.sleep(1)
for name in sys.argv[1:]:
    if name.startswith("~"):
        print("search", name, [k for k in info if name[1:].lower() in k.lower()])
        continue
    n = info.get(name)
    if not n:
        print("НЕТ", name)
        continue
    ins = {}
    for sect in ("required", "optional"):
        for k, v in (n["input"].get(sect) or {}).items():
            t = v[0]
            if isinstance(t, list):
                t = "[" + ",".join(map(str, t[:8])) + ("…" if len(t) > 8 else "") + "]"
            ins[k + ("?" if sect == "optional" else "")] = t if not (len(v) > 1 and isinstance(v[1], dict) and "default" in v[1]) else f"{t}={v[1]['default']}"
    print(name, "IN:", json.dumps(ins, ensure_ascii=False)[:700], "OUT:", n.get("output"))
