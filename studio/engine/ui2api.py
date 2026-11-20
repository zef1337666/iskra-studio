"""Конвертер UI-workflow ComfyUI (формат шаблонов/сохранённых графов) в API-формат.

Поддерживает: обычные ноды, виджеты (по объявлению input.widget или по object_info),
служебные значения control_after_generate, bypass (mode 4) — сквозная передача,
muted (mode 2) — исключение, Reroute, сабграфы (разворачиваются), dotted-входы V3.
"""
import json, urllib.request

UI_ONLY = {"Note", "MarkdownNote", "Reroute", "PrimitiveNode", "Label (rgthree)"}
DROP_OUTPUT_NODES = {"PreviewImage", "PreviewAny", "MaskPreview", "Preview3DAdvanced", "Preview3D", "PreviewAudio", "ImageCompare"}
CONTROL_VALUES = {"fixed", "randomize", "increment", "decrement"}


def fetch_object_info(url="http://127.0.0.1:8188"):
    return json.loads(urllib.request.urlopen(url + "/object_info").read())


def _widget_names(info, ctype):
    """Порядок виджетов по object_info (для нод без input.widget в UI)."""
    n = info.get(ctype)
    if not n:
        return []
    names = []
    for sect in ("required", "optional"):
        for k, v in (n["input"].get(sect) or {}).items():
            t = v[0]
            if isinstance(t, list) or t in ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COLOR") or str(t).startswith("COMFY_DYNAMICCOMBO"):
                names.append(k)
    return names


def _fix_invalid(inputs, spec):
    """Шаблон и ноды разных версий: невалидные значения виджетов заменяем значениями по умолчанию."""
    if not spec:
        return
    for sect in ("required", "optional"):
        for k, v in (spec["input"].get(sect) or {}).items():
            if k not in inputs or isinstance(inputs[k], list) and len(inputs[k]) == 2 and isinstance(inputs[k][0], str):
                continue
            t, cfg = v[0], (v[1] if len(v) > 1 and isinstance(v[1], dict) else {})
            val, ok = inputs[k], True
            if isinstance(t, list):
                ok = val in t
            elif t == "COMBO":
                ok = val in (cfg.get("options") or [val])
            elif t == "INT":
                ok = isinstance(val, int) and not isinstance(val, bool)
            elif t == "FLOAT":
                ok = isinstance(val, (int, float)) and not isinstance(val, bool)
            elif t == "BOOLEAN":
                ok = isinstance(val, bool)
            elif t == "STRING":
                ok = isinstance(val, str)
            if ok and t in ("INT", "FLOAT"):
                ok = cfg.get("min", -1e30) <= val <= cfg.get("max", 1e30)
            if not ok:
                if "default" in cfg:
                    inputs[k] = cfg["default"]
                elif isinstance(t, list) and t:
                    inputs[k] = t[0]


def _flatten_subgraphs(wf):
    """Разворачивает сабграфы в плоский граф (ноды с id 'sg:inner')."""
    defs = {sg["id"]: sg for sg in (wf.get("definitions") or {}).get("subgraphs", [])}
    nodes = {str(n["id"]): n for n in wf.get("nodes", [])}
    links = {}
    for l in wf.get("links", []):
        lid, a, sa, b, ib = (l["id"], l["origin_id"], l["origin_slot"], l["target_id"], l["target_slot"]) if isinstance(l, dict) else l[:5]
        links[lid] = [str(a), sa, str(b), ib]
    if not defs:
        return nodes, links
    # повторяем, пока остаются экземпляры сабграфов
    changed = True
    while changed:
        changed = False
        for nid, node in list(nodes.items()):
            sg = defs.get(node["type"])
            if not sg:
                continue
            changed = True
            pref = nid + ":"
            inner = {pref + str(n["id"]): dict(n, id=pref + str(n["id"])) for n in sg["nodes"]}
            # входы сабграфа: внешняя связь -> внутренние цели
            in_map = {}  # slot -> (origin, oslot)
            for lid, (a, sa, b, ib) in list(links.items()):
                if b == nid:
                    in_map[ib] = (a, sa)
                    del links[lid]
            out_targets = {}  # slot -> [(b, ib)]
            for lid, (a, sa, b, ib) in list(links.items()):
                if a == nid:
                    out_targets.setdefault(sa, []).append((b, ib))
                    del links[lid]
            # виджеты экземпляра сабграфа -> значения его входов
            widget_inputs = {}
            vals = list(node.get("widgets_values") or [])
            proxy = [i for i in node.get("inputs", []) if i.get("widget")]
            for i, inp in enumerate(proxy):
                if i < len(vals):
                    widget_inputs[inp.get("name")] = vals[i]
            sg_inputs = sg.get("inputs", [])
            for l in sg.get("links", []):
                lid, a, sa, b, ib = (l["id"], l["origin_id"], l["origin_slot"], l["target_id"], l["target_slot"]) if isinstance(l, dict) else l[:5]
                a, b = str(a), str(b)
                key = f"{pref}{lid}"
                if a == "-10":  # вход сабграфа
                    if sa in in_map:
                        links[key] = [in_map[sa][0], in_map[sa][1], pref + b, ib]
                    else:
                        name = sg_inputs[sa]["name"] if sa < len(sg_inputs) else None
                        if name in widget_inputs:
                            tgt = inner[pref + b]
                            tin = tgt["inputs"][ib]
                            tgt.setdefault("_const", {})[tin.get("widget", {}).get("name", tin["name"])] = widget_inputs[name]
                elif b == "-20":  # выход сабграфа
                    for (tb, tib) in out_targets.get(ib, []):
                        links[f"{key}>{tb}:{tib}"] = [pref + a, sa, tb, tib]
                else:
                    links[key] = [pref + a, sa, pref + b, ib]
            del nodes[nid]
            nodes.update(inner)
    return nodes, links


def convert(wf, info):
    nodes, links = _flatten_subgraphs(wf)
    by_target = {(b, ib): (a, sa) for (a, sa, b, ib) in links.values()}

    def resolve(a, sa):
        """Проходит сквозь Reroute и bypass-ноды до реального источника."""
        for _ in range(50):
            n = nodes.get(a)
            if n is None:
                return None
            if n["type"] == "Reroute" or (n["type"] in DROP_OUTPUT_NODES and (a, 0) in by_target):
                src = by_target.get((a, 0))
                if not src:
                    return None
                a, sa = src
                continue
            if n.get("mode") == 4:
                otype = (n.get("outputs") or [{}])[sa].get("type")
                cand = [i for i, inp in enumerate(n.get("inputs", [])) if inp.get("type") == otype and (a, i) in by_target]
                if not cand:
                    return None
                a, sa = by_target[(a, cand[0])]
                continue
            if n.get("mode") == 2:
                return None
            return [a, sa]
        return None

    api = {}
    for nid, n in nodes.items():
        ct = n["type"]
        if ct in UI_ONLY or n.get("mode") in (2, 4) or ct in DROP_OUTPUT_NODES:
            continue
        inputs = {}
        vals = n.get("widgets_values")
        if isinstance(vals, dict):  # VHS и т.п. хранят словарём
            inputs.update({k: v for k, v in vals.items() if k != "videopreview"})
        else:
            vals = list(vals or [])
            wnames = [i["widget"]["name"] for i in n.get("inputs", []) if i.get("widget")]
            ncontrol = sum(1 for v in vals if isinstance(v, str) and v in CONTROL_VALUES)
            if len(wnames) < len(vals) - ncontrol:
                wnames = _widget_names(info, ct) or wnames
            vi = 0
            for name in wnames:
                if vi >= len(vals):
                    break
                inputs[name] = vals[vi]
                vi += 1
                if vi < len(vals) and isinstance(vals[vi], str) and vals[vi] in CONTROL_VALUES and name in ("seed", "noise_seed", "value", "seed_value"):
                    vi += 1
                elif vi < len(vals) and isinstance(vals[vi], str) and vals[vi] in CONTROL_VALUES and isinstance(inputs[name], int):
                    vi += 1
            # dynamic combo (V3): оставшиеся значения — вложенные параметры
            dyn = info.get(ct, {})
            for sect in ("required", "optional"):
                for k, v in (dyn.get("input", {}).get(sect) or {}).items():
                    if str(v[0]).startswith("COMFY_DYNAMICCOMBO") and k in inputs:
                        opts = (v[1] or {}).get("options", []) if len(v) > 1 and isinstance(v[1], dict) else []
                        for o in opts:
                            if o.get("key") == inputs[k]:
                                for sub in o.get("inputs", {}).get("required", {}):
                                    if vi < len(vals):
                                        inputs[f"{k}.{sub}"] = vals[vi]
                                        vi += 1
        inputs.update(n.get("_const", {}))
        _fix_invalid(inputs, info.get(ct))
        for i, inp in enumerate(n.get("inputs", [])):
            src = by_target.get((nid, i))
            if src:
                r = resolve(*src)
                if r:
                    inputs[inp["name"]] = r
                    if inp.get("widget"):
                        inputs[inp["widget"]["name"]] = r
        api[nid] = {"class_type": ct, "inputs": inputs, "_meta": {"title": n.get("title") or ct}}
    # удалить ссылки на исключённые ноды
    for node in api.values():
        for k, v in list(node["inputs"].items()):
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] not in api:
                del node["inputs"][k]
    return api
