# PROGRESS — ИИ-студия

Спецификация: C:\Users\ZEF\Downloads\prompt_claude_code_comfyui.md
Папка проекта: F:\AI-Studio (NVMe WD_BLACK SN770 2TB). D: (223 ГБ SATA) отклонён — мало места.

## Решения
- 2026-11-20: всё ставим на F:. Подкачка 64 ГБ на F: (фикс.). LongPathsEnabled=1.
- Отложено в конец: обучение LoRA, Telegram-бот, доступ с телефона.
- Аккаунтов Civitai/HF нет — понадобятся на вехе 2.
- Пользователь просит максимум самостоятельности и экономию лимита.

## Этап 0 — диагностика ✅
| Пункт | Статус |
|---|---|
| Windows 11 Home | ✅ |
| RTX 5060 Ti 16 ГБ, драйвер 621.24 (CUDA 12.8+ ок) | ✅ |
| Ryzen 9 7900X, ОЗУ 32 ГБ | ✅ |
| Git, Node установлены глобально | ✅ |
| Python — только заглушка Store, ставим свой внутрь папки | ⏳ этап 1 |
| Ollama нет | ⏳ этап 5 |
| Подкачка 64 ГБ на F: | ✅ (нужна перезагрузка) |
| Длинные пути | ✅ |

## Вехи
- [x] Этап 0
- [x] Веха 1: ComfyUI + PyTorch + SageAttention + тест
- [x] Веха 2: выбор моделей (23 шт.; Big Love и One Obsession — 403 на Civitai)
- [x] Веха 3: workflow
- [x] Веха 4: менеджер моделей, помощник
- [ ] Веха 5: MVP приложения
- [ ] Веха 6: остальные разделы
- [ ] Веха 7: оптимизация и тесты
- [ ] Веха 8: документация

## Этап 1 — движок ✅ (2026-11-20)
- Способ: git + venv (не portable): свой Python 3.12.16 через uv в `tools/`, venv в `venv/`. Проще ставить SageAttention/triton и обновлять.
- ComfyUI v0.46.0+ (git, `ComfyUI/`), ComfyUI-Manager в custom_nodes.
- PyTorch 2.14.1+cu130, CUDA 13.0, карта видна (sm_120).
- Модели вынесены в `models/` (config/extra_model_paths.yaml), результаты в `data/output`.
- Запуск: `start_comfyui.bat` (127.0.0.1:8188).
- Тест API (`tools/test_api.py`, SD1.5 512px 25 шагов): 1-й прогон 20 c (загрузка), повторный 2.0 c.
- `_test_sd15.safetensors` — временная тестовая модель, удалить после выбора моделей.

### Ускорения
| Ускорение | Прирост | Качество | Статус |
|---|---|---|---|
| SageAttention 2.2 (triton-windows 3.9) | внимание ×6 (48→8 мс в тесте), на видео-моделях ~1.5–2× общий | минимальное | включено всегда |
| Async offload, dynamic VRAM, cudaMallocAsync, RAM-кэш | быстрее выгрузка/подгрузка | нет | по умолчанию в ComfyUI |
| --fast fp16_accumulation | +10–20% | минимальное/заметное | только «Черновик» |
| Ускоряющие LoRA (lightx2v, Hyper, DMD2 и т.п.) | 3–8× | заметное | только «Черновик» (этап 2–3) |

## Этап 2 — выбор моделей ✅
- 2026-11-20: исследование 4 агентами → `model-picker/data/part_*.json`, сборка `python model-picker/build.py` → `data.js`. Страница: `model-picker/index.html` (22 категории, 103 карточки).
- Ключевое на ноябрь 2026: фото — FLUX.3 Klein (gated BFL), Qwen-Image 2.1, Z-Image Turbo, Krea 2; аниме — Anima 2B / Illustrious; видео — Wan 2.2 (Apache, надёжно), MiniMax-H3 (тяжёлая), LTX-2.5 (gated); 3D — Pixal3D/TRELLIS.2 нативно в ComfyUI.
- Убрана карточка MMD Dance LoRA из 18+ (риск юного облика).
- ВНИМАНИЕ при загрузке: FLUX.3 Klein в данных ссылается на зеркало ml-resources — качать с официального репо BFL после принятия лицензии на HF. Civitai-файлы требуют API-ключ.
- Превью нет у служебных категорий (детекторы, LLM, апскейлеры) — это нормально.
- Ждём выбор пользователя.

- Выбор пользователя: `config/selection.txt`. Загрузчик: `tools/download_models.py` (докачка, SHA256, ключи из .env, CDN-редирект без ключа).
- Ollama портативно в `tools/ollama`, модели в `models/llm`: qwen3.5:9b (умеет vision), joycaption Q8_0.
- Ноды: Impact-Pack/Subpack, controlnet_aux, GGUF, MMAudio, VideoHelperSuite, KJNodes. SeedVR2/RIFE/BiRefNet/3D — нативные.

## Этап 3 — workflow ✅ (2026-11-20)
Код: `studio/engine/workflows.py` (конструктор API-графов, REGISTRY), `studio/engine/ui2api.py` (конвертер UI→API для официальных шаблонов).
Экспорт: `workflows/api/*.draft|quality.json`, `workflows/ui/*.json` (официальные шаблоны для ручной работы). Замеры: `tools/bench.py` → `data/bench.jsonl`.

### Важные находки
- Klein: sampler er_sde из шаблона «пережаривает» кожу → euler. Второй проход (hires/FaceDetailer) на дистилляте Klein портит текстуру → в «Качестве» int8 + 1–1.5 Мп без второго прохода.
- Детейлер = правка Klein с инструкцией ретушёра (FaceDetailer не подходит для дистиллятов).
- Outpaint: серые поля Klein копирует → исходник как референс + холст целевого размера.
- MiniMax-H3 GGUF (unsloth) — только для stable-diffusion.cpp, в ComfyUI не грузится. GGUF удалён; скачан нативный pruned_w6a8 (16 ГБ) — работает (подкачка пик ~11 ГБ).
- MMAudio: кадры нужно пересэмплировать в 25 к/с (VHS_LoadVideo force_rate) — иначе звук короче. Работает медленно (3.7 с/шаг, VRAM 16 ГБ) — разобрать на вехе 7.
- SmoothMix Wan: при 4 шагах размытие, нужно ≥8.
- ControlNet: докачана Z-Image Turbo int8 + Qwen3-4B fp8 + ae (по решению пользователя). Поза — сила 0.8; глубина/контуры — 0.6 до 75% шагов (иначе «пластик»).
- Big Love KreaLife3 и One Obsession (nsfwLevel XXX): Civitai 403 даже после включения уровней — вероятно, ограничение аккаунта/региона. Неофициальные зеркала НЕ используем. 18+ реализм работает на Krea 2 Turbo + Realistic Snapshot/FameGrid.

### Бенчмарк (RTX 5060 Ti 16 ГБ; время с прогретой моделью, если не указано; пик VRAM по nvidia-smi)
| Workflow | Черновик | Качество | Пик VRAM |
|---|---|---|---|
| Текст → фото (Klein) 1 Мп | 5 с | 8 с (1.5 Мп: 10 с) | 12.5–13.3 ГБ |
| Аниме (Anima) | 7 с | 14 с (с hires) | 11.6–13.0 |
| Стиль (Krea 2 + LoRA) | 22 с* | 23 с* | 15.2 (на пределе) |
| Правка командой (Klein) | 10 с | 14 с | 13.7–14.1 |
| Инпейнтинг (Klein + маска) | — | 14 с | 14.1 |
| Аутпейнтинг | 9 с | 16 с | 11.4–14.3 |
| Персонаж (Klein, референс) | 11 с | 13 с | 11.6–12.1 |
| Детейлер (Klein-ретушь) | 8 с | 23 с | 11.3–12.1 |
| Апскейл SeedVR2 | 10 с (2x) | 33 с (4x) | 13.1–13.5 |
| Удаление фона BiRefNet | 1.4 с | 1.4 с | <1 (модель мала) |
| Картинка → видео Wan 2.2, 5 с | 100 с (832×480, 4 шага) | 284 с (1024×576, 8 шагов) | 13.0–13.9 |
| Первый+последний кадр Wan | 99 с | ≈280 с | 15.6 |
| Улучшение видео | 3 с (RIFE x2) | 222 с (+SeedVR2 x2) | 1–12.5 |
| Звук MMAudio, 5 с | 51 с | ≈100 с | 16.0 (!) |
| Поза (Z-Image + ControlNet) | ≈25 с | 28 с | 15.4–15.8 (на пределе) |
| Видео со звуком MiniMax-H3, 4 с | 70 с (640×640, turbo 6 шагов) | 226 с (1056×576, 20 шагов) | 15.6–15.7 |
| Картинка → 3D Pixal3D (GLB) | 93 с | 115 с | 12.6–12.9 |
| 18+ фото Krea 2 + Realistic Snapshot | — | 22 с* | 15.0 |
| 18+ видео Wan NSFW Q6, 4 с | 137 с* | — | 14.9 |
| 18+ аниме-видео SmoothMix, 3 с (8 шагов) | 86 с | — | 14.7 |
\* с загрузкой модели. Ни одной ошибки нехватки памяти.

### Какая модель за что отвечает (для пресетов этапа 6)
- Фото/правка/инпейнт/аутпейнт/персонаж/детейлер: FLUX.3 Klein (черновик nvfp4, качество int8).
- Аниме: Anima Turbo. Стили: Krea 2 + LoRA. Поза: Z-Image + ControlNet.
- Видео (текст/картинка/первый+последний кадр, со звуком): MiniMax-H3 (черновик turbo-LoRA). Wan 2.2 — запасной и для 18+ (NSFW Q6, SmoothMix).
- Звук к готовому видео: MMAudio. Плавность: RIFE. Апскейл: SeedVR2. Фон: BiRefNet. 3D: Pixal3D.

- 2026-11-20: Big Love исключён по решению пользователя (Civitai не отдаёт ни одну версию). 18+ реализм = Krea 2 Turbo + Realistic Snapshot / FameGrid. One Obsession: v25 закрыта, v24 скачивается — ждёт решения.

## Этапы 4–5 — менеджер моделей и помощник ✅ (2026-11-20)
- One Obsession v24 скачан (v25 закрыта Civitai) — `checkpoints/OneObsession 24.safetensors`.
- `studio/config.py` — пути, .env (save_env_key), семейства базовых моделей.
- `studio/models/downloader.py` — очередь, прогресс/скорость, пауза/продолжение (.part), отмена, 7 повторов, SHA256, ошибки по-русски.
- `studio/models/catalog.py` — поиск Civitai (с query нельзя period!) и HF, разбор ссылок Civitai/HF/ID версии, автоопределение папки (Checkpoint Flux/Krea/Qwen/Wan… → diffusion_models), оценка совместимости с 16 ГБ.
- `studio/models/registry.py` — установленные (+метаданные *.meta.json и из страницы выбора), место по категориям, последнее использование, совместимость LoRA, проверка обновлений Civitai, удаление в корзину `data/trash/models`.
- Тест: `tests/test_models_manager.py` — 8/8. Попутно установлен 4x-UltraSharp (быстрый апскейл, 67 МБ).
- `studio/assistant/prompter.py` + `prompt-templates/*.md` (общие правила, фото, 18+ фото, аниме-теги, правка, видео). Режимы improve/exact/surprise/variants. keep_alive=0 — VRAM освобождается (проверено). Повтор, если промпт не на английском.
- `studio/assistant/safety.py` — блок запросов про несовершеннолетних в 18+ (RU/EN), явный возраст 21+ или adult, защитный негатив 18+.
- `studio/assistant/vision.py` — описатель: Qwen3.5 (vision) / JoyCaption для 18+, фокусы all/style/composition/character/colors.
- Скорость помощника: холодный старт ~60 с (первая загрузка с диска), далее 4–12 с; описатель ~14 с.
- Модель без цензуры для 18+ не выбрана — сейчас 18+ использует qwen3.5:9b (может отказывать). Кандидат: huihui_ai/qwen3.5-abliterated:9b (6.6 ГБ).
