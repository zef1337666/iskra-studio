"""Кнопка «ИИ»: правильно ли выбирается пресет по описанию своими словами (нужен запущенный Ollama)."""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")
from studio.assistant import router
from studio.server import presets

CASES = [  # (текст, вложения, допустимые пресеты)
    ("красивый закат над горами, туман в долине", [], {"photo-real"}),
    ("аниме девушка с мечом под дождём", [], {"anime", "retro-anime"}),
    ("нарисуй акварелью домик у озера", [], {"watercolor"}),
    ("видео как кот бежит по траве", [], {"video"}),
    ("сделай на этой фотке ночь", ["up_x.jpg"], {"edit"}),
    ("этот же человек на пляже в летнем платье", ["up_x.jpg"], {"character"}),
    ("оживи эту картинку, пусть волосы развеваются", ["up_x.jpg"], {"animate"}),
    ("увеличь качество и резкость", ["up_x.jpg"], {"upscale", "detail"}),
    ("убери фон", ["up_x.jpg"], {"nobg"}),
]
CASES18 = [  # раздел 18+ открыт: обычные просьбы не должны уходить в 18+, откровенные — должны (и с подходящей LoRA)
    ("красивый закат над горами", [], {"photo-real"}),
    ("эротическое фото обнажённой женщины 25 лет в спальне, мягкий свет", [], {"real18", "real18-fp", "real18-rd", "real18-candid"}),
    ("откровенное селфи 27-летней блогерши в стиле инстаграм", [], {"real18", "real18-fp", "real18-rd", "real18-candid"}),
]
ok, n = 0, 0
allp = presets.load_all()
for cases, nsfw in ((CASES, False), (CASES18, True)):
    for text, imgs, good in cases:
        t = time.time()
        c = router.choose(text, router.candidates(allp, imgs, "image", nsfw), len(imgs), nsfw)
        hit = c["preset"] in good
        ok += hit; n += 1
        print(("✓" if hit else "✗"), f"{'[18+] ' if nsfw else ''}{text!r} -> {c['preset']} {c['aspect']} LoRA {c['loras']} ({time.time() - t:.1f} с) — {c['reason']}")
print(f"Итог: {ok}/{n}")
