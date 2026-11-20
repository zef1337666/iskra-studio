# Бриф для исследования моделей (общий для всех агентов)

Сегодня 2026-11-20. Ищем ЛУЧШИЕ НА СЕГОДНЯ локальные модели для ComfyUI. Ничего не выбирай по памяти: модели устаревают за месяцы. Проверяй актуальное состояние в интернете (Hugging Face, Civitai, GitHub, Reddit r/StableDiffusion и r/comfyui, официальные блоги, ComfyUI blog/docs/templates). Для каждого факта запоминай дату источника.

## Железо пользователя
- RTX 5060 Ti 16 ГБ VRAM (Blackwell, sm_120: поддерживает fp8 и nvfp4), PyTorch 2.14 + CUDA 13, SageAttention 2.2 установлен.
- 32 ГБ ОЗУ (докупать не будет) + подкачка 64 ГБ на NVMe.
- Ryzen 9 7900X. Под модели ~700 ГБ на NVMe.
- Значит: полные bf16 модели >16 ГБ — только с выгрузкой в ОЗУ; предпочтительно fp8 / nvfp4 / GGUF Q8/Q6/Q5. Укажи конкретный вариант файла, который подходит.

## Инструменты
- У тебя есть Bash/curl и веб-поиск/веб-загрузка. Публичные API без ключа:
  - Civitai: `https://civitai.com/api/v1/models?query=...&types=Checkpoint&sort=Most%20Downloaded&period=Month&nsfw=true&limit=20`, `https://civitai.com/api/v1/models/<id>` — даёт stats (downloadCount, thumbsUpCount), modelVersions[].files[] (sizeKB, hashes.SHA256, downloadUrl), images[] (url, nsfwLevel), baseModel, publishedAt, allowCommercialUse/license.
  - Hugging Face: `https://huggingface.co/api/models/<repo>?blobs=true` (siblings с size, lfs.sha256), `https://huggingface.co/api/models?search=...&sort=downloads`.
- Используй curl с `-s` и `| head -c` / jq-подобную обработку через python `-I -c`, чтобы не тащить огромные ответы целиком. Не скачивай сами модели!

## Что вернуть
Запиши ОДИН файл JSON (UTF-8) по указанному тебе пути. Формат — массив категорий:

```json
[
  {
    "id": "photo_real",
    "tab": "Фото: реализм",
    "group": "Фото",            // Фото | Редактирование | Помощники | Видео | 3D | 18+
    "nsfw": false,
    "note": "1–2 предложения: что это за категория и как выбирать (по-русски)",
    "items": [
      {
        "id": "flux2-dev-fp8",
        "name": "Название модели",
        "variant": "какой именно файл/квантизация для 16 ГБ (напр. fp8_e4m3fn, GGUF Q8_0, nvfp4)",
        "purpose": "для чего (по-русски, 1 предложение)",
        "pros": ["...", "..."],
        "cons": ["...", "..."],
        "files": [
          {"filename": "x.safetensors", "url": "прямая ссылка на скачивание", "folder": "diffusion_models", "size_gb": 12.3, "sha256": "если известен, иначе null"}
        ],
        "total_gb": 20.1,                     // сумма всех файлов, включая text encoder/VAE если нужны
        "shared_files_note": "напр. 'text encoder общий с Flux.2 Klein' или null",
        "speed_draft": "≈8 с / 1024px (оценка)",
        "speed_quality": "≈40 с / 1024px (оценка)",
        "quality": 9,                         // 1–10, твоя оценка относительно конкурентов сегодня
        "popularity": "1.2M загрузок HF, 45k 👍 Civitai",
        "release": "2026-03",
        "license": "Apache-2.0 / FLUX non-commercial / CreativeML OpenRAIL++ ...",
        "source_url": "страница модели",
        "source_date": "дата источника, на который опираешься",
        "compat": "fits | offload | edge",    // помещается в VRAM | работает с выгрузкой в ОЗУ | на пределе
        "previews": ["2–4 прямых URL картинок-примеров (Civitai image url или HF), предпочтительно от пользователей"],
        "nsfw": false,
        "recommended": false,
        "recommend_reason": "только у рекомендованного: почему именно эта",
        "author_settings": {"sampler": "...", "scheduler": "...", "steps": 20, "cfg": 3.5, "resolution": "1024x1024", "notes": "триггеры, VAE, clip skip и т.п."},
        "custom_nodes": ["если нужны нестандартные ноды ComfyUI — названия репозиториев GitHub"]
      }
    ]
  }
]
```

Правила:
- В каждой категории 3–5 кандидатов, ровно один `"recommended": true`.
- Все тексты для пользователя по-русски, коротко, без жаргона.
- Ссылки на файлы должны быть реальными (проверь, что репо/версия существует: HEAD-запрос или API). Для Civitai используй `downloadUrl` из API.
- Если компонент общий для нескольких моделей (text encoder, VAE), включай его в `files` каждой модели, но отмечай в `shared_files_note`.
- Не трать лимит: не больше ~40 веб-запросов на категорию группы, ответы API обрезай.
- В конце ответь коротко (≤10 строк): путь к файлу, сколько категорий/карточек, что не удалось проверить.
