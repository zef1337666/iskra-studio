"""Конвертирует шаблон и отправляет в ComfyUI на валидацию (без запуска: проверка /prompt)."""
import json, sys, pathlib, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio.engine.ui2api import convert, fetch_object_info  # noqa
T = ROOT / "venv/Lib/site-packages/comfyui_workflow_templates_json/templates"
info = fetch_object_info()
wf = json.loads((T / sys.argv[1]).read_text(encoding="utf-8"))
api = convert(wf, info)
out = ROOT / "workflows" / "api" / sys.argv[1]
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(api, ensure_ascii=False, indent=1), encoding="utf-8")
print("нод:", len(api), "->", out)
for nid, n in api.items():
    if n["class_type"] not in info:
        print("  нет ноды:", n["class_type"])
