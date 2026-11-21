"""Фоновые движки: ComfyUI и Ollama. Студия сама запускает, следит и перезапускает их."""
import os, subprocess, threading, time, urllib.request, json
from ..config import ROOT, DATA, COMFY_URL, OLLAMA_URL

CREATE_NO_WINDOW = 0x08000000
PY = ROOT / "venv" / "Scripts" / "python.exe"


def _alive(url):
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except Exception:
        return False


class Service:
    def __init__(self, name, health_url, cmd, env=None, log="service.log"):
        self.name, self.health_url, self.cmd, self.env, self.log = name, health_url, cmd, env or {}, DATA / log
        self.proc = None
        self.restarts = 0
        self.state = "stopped"  # stopped | starting | running | crashed
        self.started_at = None
        self.want = True

    def start(self):
        if _alive(self.health_url):  # уже запущен (например, вручную)
            self.state = "running"
            return
        env = {**os.environ, **self.env, "PYTHONUTF8": "1"}
        fh = open(self.log, "a", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen(self.cmd, cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
        self.state, self.started_at = "starting", time.time()

    def stop(self):
        self.want = False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except Exception:
                self.proc.kill()
        self.state = "stopped"

    def restart(self):
        self.stop()
        self.want = True
        self.restarts += 1
        self.start()

    def check(self):
        ok = _alive(self.health_url)
        if ok:
            self.state = "running"
        elif self.want:
            if self.proc and self.proc.poll() is not None:
                self.state = "crashed"
                self.restarts += 1
                self.start()
            elif self.state == "starting" and time.time() - (self.started_at or 0) > 180:
                self.restart()
            elif not self.proc and self.state != "starting":
                self.start()
        return self.state

    def info(self):
        return {"name": self.name, "state": self.state, "restarts": self.restarts}


def comfy_cmd(extra=None):
    return [str(PY), str(ROOT / "ComfyUI" / "main.py"), "--listen", "127.0.0.1", "--port", "8188", "--use-sage-attention",
            "--preview-method", "auto", "--extra-model-paths-config", str(ROOT / "config" / "extra_model_paths.yaml"),
            "--output-directory", str(DATA / "output"), "--input-directory", str(DATA / "input"), "--temp-directory", str(DATA),
            "--disable-auto-launch"] + (extra or [])


COMFY = Service("ComfyUI", COMFY_URL + "/system_stats", comfy_cmd(), log="comfy.log")
OLLAMA = Service("Ollama", OLLAMA_URL + "/api/tags", [str(ROOT / "tools" / "ollama" / "ollama.exe"), "serve"],
                 env={"OLLAMA_MODELS": str(ROOT / "models" / "llm"), "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_KEEP_ALIVE": "0"}, log="ollama.log")
SERVICES = {"comfy": COMFY, "ollama": OLLAMA}


def start_all():
    for s in SERVICES.values():
        s.start()

    def watch():
        while True:
            for s in SERVICES.values():
                try:
                    s.check()
                except Exception:
                    pass
            time.sleep(5)
    threading.Thread(target=watch, daemon=True).start()


def gpu_stats():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total,power.draw",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW).stdout
        vals = [x.strip() for x in out.strip().splitlines()[0].split(",")]
        num = lambda v: float(v) if v.replace(".", "", 1).isdigit() else None  # «[N/A]» на некоторых драйверах
        u, t, mu, mt, p = (num(v) for v in vals)
        return {"util": int(u or 0), "temp": int(t or 0), "vram_used": int(mu or 0), "vram_total": int(mt or 16384), "power": p}
    except Exception:
        return None


def ram_stats():
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return {"used": round((m.ullTotalPhys - m.ullAvailPhys) / 1e9, 1), "total": round(m.ullTotalPhys / 1e9, 1)}


def free_vram():
    req = urllib.request.Request(COMFY_URL + "/free", data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)
