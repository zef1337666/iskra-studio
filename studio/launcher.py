"""Запуск «Искры» как настоящего приложения: backend в фоне + отдельное окно (WebView2)."""
import os, sys, threading, time, urllib.request, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
URL = "http://127.0.0.1:7860"


def alive():
    try:
        urllib.request.urlopen(URL + "/api/status", timeout=2)
        return True
    except Exception:
        return False


def run_server():
    import uvicorn
    from studio.server.app import app, bind_host
    uvicorn.run(app, host=bind_host(), port=7860, log_level="warning")


def main():
    import webview
    webview.settings["ALLOW_DOWNLOADS"] = True
    owner = False
    if not alive():
        owner = True
        threading.Thread(target=run_server, daemon=True).start()
        for _ in range(120):
            if alive():
                break
            time.sleep(0.5)
    win = webview.create_window("Искра", URL, width=1560, height=980, min_size=(1000, 680), background_color="#0b0c11", text_select=True)

    def on_closed():
        if owner:  # останавливаем движки, которые запустило это окно
            from studio.server import services
            for s in services.SERVICES.values():
                s.stop()
    win.events.closed += on_closed
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(ROOT / "data" / "webview"), icon=str(ROOT / "app" / "iskra.ico"))
    os._exit(0)


if __name__ == "__main__":
    main()
