"""Создаёт стартовый набор пресетов presets/*.yaml (существующие файлы не перезаписывает)."""
import pathlib, sys, yaml
sys.stdout.reconfigure(encoding="utf-8")
D = pathlib.Path(__file__).resolve().parents[1] / "presets"
D.mkdir(exist_ok=True)

PHOTO_CHIPS = [{"label": "Студийный свет", "hint": "professional studio lighting, softbox key light, clean backdrop"},
               {"label": "Дневной свет", "hint": "natural daylight, soft window light"},
               {"label": "Вечер, тёплый свет", "hint": "warm golden evening light, cozy ambience"},
               {"label": "Снято на телефон", "hint": "amateur smartphone photo, candid, slight noise, on-camera flash look"},
               {"label": "Плёнка", "hint": "35mm film photo, Kodak Portra colors, film grain"},
               {"label": "Глянец", "hint": "glossy magazine photoshoot, editorial fashion lighting, high-end retouch"}]
NEG18 = "cartoon, anime, 3d render, plastic skin, waxy skin, airbrushed, extra fingers, deformed hands, bad anatomy, distorted body"

P = [
    dict(id="photo-real", name="Реализм", group="Фото", order=1, media="image", workflow="klein_t2i", ref_workflow="klein_edit",
         assistant="photo", base_model="FLUX.3 Klein", megapixels={"draft": 1.0, "quality": 1.5}, eta={"draft": 6, "quality": 11},
         description="Фотореалистичные снимки: люди, животные, предметы, интерьеры.", chips=PHOTO_CHIPS),
    dict(id="anime", name="Аниме", group="Арт", order=1, media="image", workflow="anima_t2i", assistant="anime", base_model="Anima",
         megapixels={"draft": 1.0, "quality": 1.0}, eta={"draft": 7, "quality": 15}, description="Аниме и манга в современном стиле."),
    dict(id="illustration", name="Иллюстрация", group="Арт", order=2, media="image", workflow="krea2_t2i", assistant="art", base_model="Krea 2",
         megapixels={"draft": 1.0, "quality": 1.0}, eta={"draft": 8, "quality": 9}, description="Цифровая иллюстрация, концепт-арт, постеры."),
    dict(id="watercolor", name="Акварель", group="Арт", order=3, media="image", workflow="krea2_t2i", assistant="art", base_model="Krea 2",
         params={"loras": [["krea2_softwatercolor.safetensors", 1.0]]}, megapixels={"draft": 1.0, "quality": 1.0}, eta={"draft": 8, "quality": 9},
         prompt_suffix=", soft watercolor painting", description="Нежная акварель на бумаге."),
    dict(id="dark-brush", name="Тёмная кисть", group="Арт", order=4, media="image", workflow="krea2_t2i", assistant="art", base_model="Krea 2",
         params={"loras": [["krea2_darkbrush.safetensors", 1.0]]}, megapixels={"draft": 1.0, "quality": 1.0}, eta={"draft": 8, "quality": 9},
         description="Драматичная живопись тёмной кистью."),
    dict(id="retro-anime", name="Ретро-аниме", group="Арт", order=5, media="image", workflow="krea2_t2i", assistant="art", base_model="Krea 2",
         params={"loras": [["krea2_retroanime.safetensors", 1.0]]}, megapixels={"draft": 1.0, "quality": 1.0}, eta={"draft": 8, "quality": 9},
         description="Аниме 80–90-х, как кадр из старого фильма."),
    dict(id="edit", name="Редактировать командой", group="Редактирование", order=1, media="image", workflow="klein_edit", requires="image",
         assistant="edit", base_model="FLUX.3 Klein", eta={"draft": 10, "quality": 14},
         description="«Смени фон», «сделай ночь», «добавь очки» — загрузите картинку и напишите, что изменить."),
    dict(id="character", name="Персонаж", group="Редактирование", order=2, media="image", workflow="klein_edit", requires="image",
         assistant="edit", base_model="FLUX.3 Klein", megapixels={"draft": 1.0, "quality": 1.3}, eta={"draft": 11, "quality": 14},
         prompt_prefix="Photo of the same person from <ref_image_0>: ", description="Тот же персонаж в новой сцене (1–3 референса)."),
    dict(id="pose", name="Поза и композиция", group="Редактирование", order=3, media="image", workflow="zimage_control", requires="image",
         assistant="photo", base_model="Z-Image Turbo", eta={"draft": 25, "quality": 28}, params={"control": "pose"},
         description="Повторить позу или композицию с картинки-образца."),
    dict(id="inpaint", name="Перерисовать область", group="Редактирование", hidden=True, media="image", workflow="klein_edit", requires="image",
         assistant="edit", base_model="FLUX.3 Klein", eta={"draft": 10, "quality": 14}),
    dict(id="outpaint", name="Расширить кадр", group="Редактирование", hidden=True, media="image", workflow="klein_outpaint", requires="image",
         assistant="edit", base_model="FLUX.3 Klein", eta={"draft": 9, "quality": 16}),
    dict(id="upscale", name="Апскейл", group="Редактирование", hidden=True, media="image", workflow="upscale", requires="image",
         base_model="SeedVR2", eta={"draft": 10, "quality": 33}),
    dict(id="detail", name="Улучшить лицо и руки", group="Редактирование", hidden=True, media="image", workflow="detailer", requires="image",
         base_model="FLUX.3 Klein", eta={"draft": 8, "quality": 23}),
    dict(id="nobg", name="Удалить фон", group="Редактирование", hidden=True, media="image", workflow="remove_bg", requires="image",
         base_model="BiRefNet", eta={"draft": 2, "quality": 2}),
    dict(id="video", name="Видео со звуком", group="Видео", order=1, media="video", workflow="h3_video", assistant="video", base_model="MiniMax-H3",
         eta={"draft": 70, "quality": 230}, description="Из текста или картинки — видео 4–8 секунд со звуком."),
    dict(id="animate", name="Оживить картинку", group="Видео", order=2, media="video", workflow="wan22_video", requires="image", assistant="video",
         base_model="Wan 2.2", eta={"draft": 100, "quality": 285}, description="Оживление картинки моделью Wan 2.2 (без звука)."),
    dict(id="transition", name="Первый и последний кадр", group="Видео", order=3, media="video", workflow="h3_video", requires="images2",
         assistant="video", base_model="MiniMax-H3", eta={"draft": 70, "quality": 230}, description="Плавный переход между двумя картинками."),
    dict(id="video-enhance", name="Сделать плавнее", group="Видео", hidden=True, media="video", workflow="video_enhance", requires="video",
         base_model="RIFE + SeedVR2", eta={"draft": 3, "quality": 220}),
    dict(id="video-sound", name="Добавить звук", group="Видео", hidden=True, media="video", workflow="video_audio", requires="video",
         base_model="MMAudio", eta={"draft": 50, "quality": 100}),
    dict(id="to-3d", name="Картинка → 3D", group="3D", order=1, media="3d", workflow="image_to_3d", requires="image", base_model="Pixal3D",
         eta={"draft": 95, "quality": 115}, description="3D-модель с текстурой из картинки предмета. Фон удаляется сам."),
    dict(id="real18", name="Реализм 18+", group="18+", order=1, nsfw=True, media="image", workflow="krea2_t2i", assistant="photo18",
         base_model="Krea 2", params={"loras": [["RealisticSnapshotKrea2V2.safetensors", 0.8]]}, megapixels={"draft": 1.0, "quality": 1.3},
         eta={"draft": 9, "quality": 14}, negative=NEG18, chips=PHOTO_CHIPS,
         prompt_prefix="photorealistic, natural skin texture, detailed skin pores, ",
         description="Фотореализм для взрослых: естественная кожа и свет. Только вымышленные взрослые персонажи."),
    dict(id="real18-candid", name="Реализм 18+ (любительское)", group="18+", order=2, nsfw=True, media="image", workflow="krea2_t2i",
         assistant="photo18", base_model="Krea 2", params={"loras": [["Famegrid-Spice-Preview-V2.safetensors", 0.75]]},
         megapixels={"draft": 1.0, "quality": 1.3}, eta={"draft": 9, "quality": 14}, negative=NEG18, chips=PHOTO_CHIPS,
         prompt_prefix="famegrid, natural face, candid photo, ", description="Естественные «любительские» снимки взрослых персонажей."),
    dict(id="anime18", name="Аниме 18+", group="18+", order=3, nsfw=True, media="image", workflow="sdxl_t2i", assistant="anime18",
         base_model="Illustrious", params={"model": "OneObsession 24.safetensors", "cfg": 5.0}, megapixels={"draft": 1.0, "quality": 1.0},
         eta={"draft": 10, "quality": 30}, prompt_prefix="masterpiece, best quality, amazing quality, very aesthetic, absurdres, newest, ",
         description="Аниме для взрослых (One Obsession v24). Только взрослые персонажи."),
    dict(id="video18", name="Видео 18+ реализм", group="18+", order=4, nsfw=True, media="video", workflow="wan22_video", requires="image",
         assistant="video18", base_model="Wan 2.2", params={"set": "nsfw_real"}, eta={"draft": 110, "quality": 290},
         description="Оживление картинки с вымышленными взрослыми персонажами."),
    dict(id="video18-anime", name="Видео 18+ аниме", group="18+", order=5, nsfw=True, media="video", workflow="wan22_video", requires="image",
         assistant="video18", base_model="Wan 2.2", params={"set": "nsfw_anime"}, eta={"draft": 90, "quality": 120},
         prompt_prefix="smoothmixanime, anime style. ", description="Оживление аниме-картинки (SmoothMix)."),
]
n = 0
for p in P:
    f = D / f"{p['id']}.yaml"
    if not f.exists():
        f.write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False), encoding="utf-8")
        n += 1
print("создано пресетов:", n, "из", len(P))
