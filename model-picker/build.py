"""Собирает data/part_*.json в data.js для страницы выбора (работает с file://)."""
import json, pathlib, sys

root = pathlib.Path(__file__).parent
order = ["part_photo.json", "part_tools.json", "part_video.json", "part_nsfw.json"]
cats, problems = [], []
for name in order:
    p = root / "data" / name
    if not p.exists():
        problems.append(f"нет файла {name}")
        continue
    try:
        part = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        problems.append(f"{name}: битый JSON ({e})")
        continue
    for c in part:
        items = c.get("items", [])
        recs = [i for i in items if i.get("recommended")]
        if len(recs) != 1:
            problems.append(f"{c.get('id')}: рекомендаций {len(recs)}")
        for i in items:
            if c.get("nsfw"):
                i["nsfw"] = True
            if not i.get("total_gb"):
                i["total_gb"] = round(sum(float(f.get("size_gb") or 0) for f in i.get("files", [])), 2)
        cats.append(c)
(root / "data.js").write_text("window.MODEL_DATA = " + json.dumps(cats, ensure_ascii=False) + ";\n", encoding="utf-8")
print(f"категорий: {len(cats)}, карточек: {sum(len(c['items']) for c in cats)}")
for x in problems:
    print("!", x)
