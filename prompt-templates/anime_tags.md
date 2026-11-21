# Аниме — теги Danbooru (Anima, Illustrious / One Obsession)

Target model: anime model trained on Danbooru tags.
- prompt = comma-separated lowercase tags. Order: quality tags, rating, subject count (1girl / 1boy / solo), character features (hair, eyes, clothing), pose/action, background/setting, lighting, composition.
- Quality tags for Anima: "masterpiece, best quality, score_7, safe," (use "safe" unless the preset is 18+).
- Quality tags for Illustrious/One Obsession: "masterpiece, best quality, amazing quality, very aesthetic, absurdres, newest,".
- You may append one short natural-language sentence at the end for complex scenes.
- negative: "worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, bad anatomy, bad hands, extra digits, watermark, signature".
- In 18+ presets: characters are explicitly adults — always include "adult" and "mature" tags; never use tags implying minors (loli, shota, child, teen, school uniform with child body, etc.). If the request implies a minor, return {"error": "refused"}.
