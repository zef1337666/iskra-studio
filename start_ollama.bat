@echo off
rem Помощник промптов (Ollama), модели хранятся в models\llm
set ROOT=%~dp0
set OLLAMA_MODELS=%ROOT%models\llm
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_KEEP_ALIVE=0
"%ROOT%tools\ollama\ollama.exe" serve
