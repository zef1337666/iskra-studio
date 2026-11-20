"""Компактный разбор UI-шаблона ComfyUI: ноды, виджеты, связи (включая сабграфы)."""
import json, sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
T = pathlib.Path(r"F:\AI-Studio\venv\Lib\site-packages\comfyui_workflow_templates_json\templates")


def dump(g, title):
    nodes = {n["id"]: n for n in g.get("nodes", [])}
    print(f"== {title}")
    for n in g.get("nodes", []):
        if n.get("mode") in (2, 4):  # muted / bypassed
            continue
        wv = n.get("widgets_values")
        if isinstance(wv, dict):
            wv = {k: v for k, v in wv.items() if k != "videopreview"}
        s = json.dumps(wv, ensure_ascii=False)
        if len(s) > 220:
            s = s[:220] + "…"
        print(f"  #{n['id']} {n['type']} {s}")
    for l in g.get("links", []):
        if isinstance(l, dict):
            a, sa, b, ib = l["origin_id"], l["origin_slot"], l["target_id"], l["target_slot"]
        else:
            _, a, sa, b, ib, _t = l[:6]
        na, nb = nodes.get(a), nodes.get(b)
        ta = na["type"] if na else str(a)
        tb = nb["type"] if nb else str(b)
        iname = nb["inputs"][ib]["name"] if nb and ib < len(nb.get("inputs", [])) else ib
        print(f"    {a}:{ta}[{sa}] -> {b}:{tb}.{iname}")


for name in sys.argv[1:]:
    wf = json.loads((T / name).read_text(encoding="utf-8"))
    dump(wf, name)
    for sg in (wf.get("definitions") or {}).get("subgraphs", []):
        dump(sg, "subgraph " + sg.get("name", sg.get("id")))
