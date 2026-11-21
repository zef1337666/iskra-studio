"""Проверка менеджера моделей (сеть нужна). Запуск: venv\\Scripts\\python.exe tests\\test_models_manager.py"""
import sys, time, pathlib
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from studio.models import catalog, registry  # noqa
from studio.models.downloader import Task, get_downloader  # noqa

ok = lambda c, m: print(("✓ " if c else "✗ ") + m) or bool(c)
res = []

s = catalog.civitai_search("watercolor", kind="lora", limit=5)
res.append(ok(len(s["items"]) > 0 and s["items"][0]["file"], f"поиск Civitai: {len(s['items'])} шт., первая: {s['items'][0]['name'] if s['items'] else '-'}"))
h = catalog.hf_search("4x-UltraSharp", limit=3)
res.append(ok(len(h["items"]) > 0, f"поиск HF: {[i['repo'] for i in h['items']]}"))
r = catalog.resolve("https://civitai.com/models/2268008")
res.append(ok(r["card"]["kind"] == "lora" and r["card"]["file"]["folder"] == "loras", f"ссылка Civitai -> {r['card']['name']} / {r['card']['base_model']} / {r['card']['file']['folder']}"))
r2 = catalog.resolve("https://huggingface.co/Comfy-Org/z_image_turbo/blob/main/split_files/vae/ae.safetensors")
res.append(ok(r2["file"]["folder"] == "vae" and r2["file"]["sha256"], f"ссылка HF -> {r2['file']['folder']}/{r2['file']['filename']}"))
inst = registry.installed()
res.append(ok(len(inst) > 20, f"установлено моделей: {len(inst)}; место: {registry.space_by_category()}"))
res.append(ok(registry.check_lora_compat("Illustrious", "Krea 2") is not None and registry.check_lora_compat("Krea 2", "Krea 2") is None,
              "проверка совместимости LoRA"))

# загрузка с паузой и продолжением (быстрый апскейлер ~67 МБ — пригодится как «быстрый 4x»)
dl = get_downloader()
f = catalog.resolve("https://huggingface.co/Kim2091/UltraSharp/resolve/main/4x-UltraSharp.pth")["file"]
f["folder"] = "upscale_models"
t = registry.install_hf(f, "Kim2091/UltraSharp", {"name": "4x-UltraSharp (быстрый апскейл)", "kind": "upscaler"})
while t.state in ("queued",) or (t.state == "running" and t.done < 5_000_000):
    time.sleep(0.2)
t.pause()
time.sleep(1.5)
paused_at = t.done
res.append(ok(t.state == "paused" or t.state == "done", f"пауза: {t.state} на {paused_at / 1e6:.1f} МБ"))
t.resume()
while t.state not in ("done", "error"):
    time.sleep(0.5)
res.append(ok(t.state == "done" and t.dest.exists() and registry.meta_path(t.dest).exists(), f"продолжение и завершение: {t.state}, {t.error or 'хеш ок'}"))
print(f"\nИтог: {sum(res)}/{len(res)}")
