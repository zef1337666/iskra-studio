"""Замер точности переноса персонажа: варианты workflow -> сходство лица с исходником (ArcFace, 0..1).

Запуск при работающем ComfyUI: venv\\Scripts\\python.exe tests\\bench_identity.py <исходник> [варианты через запятую]
Исходник — ИИ-картинка (генерация студии). Результаты — в data/output/_bench.

Итоги 2026-11-27 (2 исходника × 2 сцены × 2 seed): Vérité 0.6 снижает сходство (0.28→0.34 и 0.46→0.47 без неё); identity 1.3 и 0.8 хуже 1.0;
базовая Krea 2 ≈ LUSTIFY; доводка SeedVR2 не мешает (0.36). Не помогли на встроенных нодах: лицо крупным планом вторым референсом,
референс 2 Мп, «зрение» Qwen-VL 768/1024 px.
"""
import json, shutil, sys, time, urllib.request, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")
from studio.engine import workflows
from studio.assistant import face
from studio.config import INPUT, OUTPUT

C = "http://127.0.0.1:8188"
PREFIX = "Take only the person from image 1 (face, hair, skin, body) and place them in a completely new photo: "
PROMPTS = ["the person is sitting in a cozy cafe by the window, wearing a black knit sweater, holding a cup of coffee, three-quarter view, natural daylight. Amateur phone photo.",
           "the person is walking down a city street at night with neon signs, wearing a denim jacket, full body shot. Amateur phone photo."]
BASE = {"model": "lustify-v10-krea-turbo-int8_convrot.safetensors", "loras": [["Verite_realism.safetensors", 0.6]], "width": 1056, "height": 1584}
VARIANTS = {
    "base": {"loras": []},
    "verite": {},
    "id13": {"loras": [], "identity_strength": 1.3},
    "id08": {"loras": [], "identity_strength": 0.8},
    "krea2base": {"loras": [], "model": "krea2_turbo_nvfp4.safetensors"},
    "finish": {"loras": [], "finish_upscale": True, "finish_scale": 1.5},
}


def run(graph):
    r = json.loads(urllib.request.urlopen(urllib.request.Request(C + "/prompt", data=json.dumps({"prompt": graph}).encode(),
                                                                 headers={"Content-Type": "application/json"})).read())
    pid = r["prompt_id"]
    while True:
        h = json.loads(urllib.request.urlopen(f"{C}/history/{pid}").read())
        if pid in h and h[pid].get("status", {}).get("completed") is not None:
            st = h[pid]["status"]
            if st.get("status_str") == "error":
                raise RuntimeError(json.dumps(st)[:600])
            for o in h[pid]["outputs"].values():
                for im in o.get("images", []):
                    if im.get("type") == "output":
                        return OUTPUT / im["subfolder"] / im["filename"]
        time.sleep(1)


def main():
    src = pathlib.Path(sys.argv[1])
    names = sys.argv[2].split(",") if len(sys.argv) > 2 else list(VARIANTS)
    seeds = [11, 22]
    name = f"test_bench_{src.stem}{src.suffix}"
    shutil.copy(src, INPUT / name)
    res = {}
    for v in names:
        sims, t0 = [], time.time()
        for pi, pr in enumerate(PROMPTS):
            for s in seeds:
                p = {**BASE, **VARIANTS[v], "images": [name], "prompt": PREFIX + pr, "seed": s, "prefix": f"_bench/{src.stem}_{v}_p{pi}_s{s}"}
                out = run(workflows.krea2_identity(p, "quality"))
                sims.append(face.similarity(src, out))
        ok = [x for x in sims if x is not None]
        res[v] = (sum(ok) / len(ok) if ok else 0, min(ok) if ok else 0, (time.time() - t0) / len(sims))
        print(f"{v:14s} сходство ср. {res[v][0]:.3f}  мин. {res[v][1]:.3f}  {res[v][2]:.0f} с/карт.  {['%.2f' % x if x is not None else '—' for x in sims]}", flush=True)


if __name__ == "__main__":
    main()
