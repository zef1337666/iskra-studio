@echo off
rem Запуск движка ComfyUI (обычно его запускает приложение-студия само)
set ROOT=%~dp0
set PYTHONUTF8=1
"%ROOT%venv\Scripts\python.exe" "%ROOT%ComfyUI\main.py" --listen 127.0.0.1 --port 8188 --use-sage-attention --preview-method auto --extra-model-paths-config "%ROOT%config\extra_model_paths.yaml" --output-directory "%ROOT%data\output" --input-directory "%ROOT%data\input" --temp-directory "%ROOT%data" --disable-auto-launch %*
