@echo off
rem Iskra studio launcher (app window). ComfyUI and Ollama start automatically.
start "" "%~dp0venv\Scripts\pythonw.exe" -m studio.launcher
