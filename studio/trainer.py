"""Обучение LoRA персонажа через ai-toolkit (отдельное окружение tools/ai-toolkit/venv).

База — FLUX.3 Klein Base (int8 convrot, файлы в формате ComfyUI из models/), LoRA подходит к пресету «Персонаж» (Klein).
На время обучения движок ComfyUI нужно остановить: видеокарта нужна целиком.
"""
import os, pathlib, re, shutil, subprocess, threading, time
import yaml
from .config import ROOT, MODELS, DATA, load_env

TK = ROOT / "tools" / "ai-toolkit"
PY = TK / "venv" / "Scripts" / "python.exe"
JOBS = DATA / "training"


def make_config(name, dataset_dir, steps=1200, rank=16, lr=1e-4, resolution=(512, 768)):
    out = JOBS / name
    out.mkdir(parents=True, exist_ok=True)
    cfg = {"job": "extension", "config": {"name": name, "process": [{
        "type": "sd_trainer", "training_folder": str(out), "device": "cuda:0",
        "network": {"type": "lora", "linear": rank, "linear_alpha": rank},
        "save": {"dtype": "float16", "save_every": max(100, steps // 4), "max_step_saves_to_keep": 2},
        "datasets": [{"folder_path": str(dataset_dir), "caption_ext": "txt", "caption_dropout_rate": 0.05, "cache_latents_to_disk": True,
                      "resolution": list(resolution)}],
        "train": {"batch_size": 1, "cache_text_embeddings": True, "steps": steps, "gradient_accumulation": 1, "train_unet": True,
                  "train_text_encoder": False, "gradient_checkpointing": True, "noise_scheduler": "flowmatch", "optimizer": "adamw8bit",
                  "lr": lr, "dtype": "bf16", "disable_sampling": True, "skip_first_sample": True},
        "model": {"name_or_path": "black-forest-labs/flux-3-image-klein-comfy", "arch": "flux3", "quantize": True, "qtype": "convrot8",
                  "quantize_te": True, "qtype_te": "qfloat8", "low_vram": True},
    }]}, "meta": {"name": name, "version": "1.0"}}
    p = out / "config.yaml"
    p.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


class Training:
    def __init__(self, name, dataset_dir, steps, trigger, on_done=None):
        self.name, self.dataset_dir, self.steps, self.trigger, self.on_done = name, dataset_dir, steps, trigger, on_done
        self.state, self.step, self.error, self.eta, self.lora = "starting", 0, None, None, None
        self.started = time.time()
        self.proc = None
        self.log = []

    def info(self):
        return {"name": self.name, "state": self.state, "step": self.step, "steps": self.steps, "eta": self.eta, "error": self.error,
                "lora": self.lora, "elapsed": round(time.time() - self.started), "log": self.log[-6:]}

    def start(self):
        cfg = make_config(self.name, self.dataset_dir, self.steps)
        env = {**os.environ, "MODELS_PATH": str(MODELS), "HF_HOME": str(TK / "hf"), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
               "HF_TOKEN": load_env().get("HF_TOKEN", ""), "DISABLE_TELEMETRY": "YES"}
        self.proc = subprocess.Popen([str(PY), str(TK / "run.py"), str(cfg)], cwd=str(TK), env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=0x08000000)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        pat = re.compile(r"(\d+)/(\d+) \[[\d:]+<([\d:]+)")
        with open(JOBS / self.name / "train.log", "w", encoding="utf-8") as logf:
            for line in self.proc.stdout:
                logf.write(line)
                for part in line.replace("\r", "\n").split("\n"):
                    m = pat.search(part)
                    if m and int(m.group(2)) == self.steps:
                        self.state, self.step = "training", int(m.group(1))
                        t = [int(x) for x in m.group(3).split(":")]
                        self.eta = sum(v * 60 ** i for i, v in enumerate(reversed(t)))
                    elif part.strip():
                        self.log.append(part.strip()[:200])
                        if "out of memory" in part.lower():
                            self.error = "Не хватило видеопамяти. Уменьшите разрешение или закройте другие программы."
                        if self.state == "starting" and ("caching" in part.lower() or "loading" in part.lower()):
                            self.state = "preparing"
        rc = self.proc.wait()
        files = sorted((JOBS / self.name).rglob("*.safetensors"), key=lambda f: f.stat().st_mtime)
        if rc == 0 and files:
            dst = MODELS / "loras" / "characters" / f"{self.name}.safetensors"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(files[-1], dst)
            self.lora, self.state = f"characters/{self.name}.safetensors", "done"
            if self.on_done:
                self.on_done(self)
        elif self.state != "cancelled":
            self.state = "error"
            self.error = self.error or "Обучение остановилось с ошибкой. Подробности: data/training/" + self.name + "/train.log"

    def cancel(self):
        if self.proc and self.proc.poll() is None:
            self.state = "cancelled"
            self.proc.terminate()
