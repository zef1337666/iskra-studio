"""Workflow студии в API-формате ComfyUI.

Каждая функция принимает параметры (dict) и режим 'draft' | 'quality', возвращает граф.
Ускорения, заметно влияющие на качество, используются только в 'draft'.
"""
import random
from .graph import Graph

KLEIN = {"draft": "flux3-image-klein-nvfp4.safetensors", "quality": "flux3-image-klein-int8-convrot.safetensors"}
KLEIN_TE = "qwen3vl_4b_int8_convrot.safetensors"
FLUX2_VAE = "flux2-vae.safetensors"


def _seed(p):
    s = p.get("seed")
    return int(s) if s not in (None, "", -1) else random.randint(0, 2**50)


def _size(p, default=(1024, 1024)):
    w, h = int(p.get("width", default[0])), int(p.get("height", default[1]))
    return w - w % 16, h - h % 16


def _save(g, img, p, prefix):
    return g.add("SaveImage", "Сохранить", images=img, filename_prefix=p.get("prefix", prefix))


def _face_detailer(g, img, model, clip, vae, pos, neg, seed, steps=8, denoise=0.35, cfg=1.0, sampler="euler", scheduler="simple"):
    det = g.add("UltralyticsDetectorProvider", "Детектор лиц", model_name="bbox/face_yolov8m.pt")
    fd = g.add("FaceDetailer", "Детейлер лица", image=img, model=model, clip=clip, vae=vae, positive=pos, negative=neg,
               bbox_detector=det[0], guide_size=768, guide_size_for=True, max_size=1024, seed=seed, steps=steps, cfg=cfg,
               sampler_name=sampler, scheduler=scheduler, denoise=denoise, feather=8, noise_mask=True, force_inpaint=True,
               bbox_threshold=0.5, bbox_dilation=12, bbox_crop_factor=3.0, sam_detection_hint="center-1",
               sam_dilation=0, sam_threshold=0.93, sam_bbox_expansion=0, sam_mask_hint_threshold=0.7,
               sam_mask_hint_use_negative="False", drop_size=40, wildcard="", cycle=1, inpaint_model=False,
               noise_mask_feather=20, tiled_encode=False, tiled_decode=False)
    return fd[0]


# ---------------------------------------------------------------- FLUX.3 Klein
def _klein_base(g, mode):
    unet = g.add("UNETLoader", "Модель Klein", unet_name=KLEIN[mode], weight_dtype="default")
    clip = g.add("CLIPLoader", "Текстовый энкодер", clip_name=KLEIN_TE, type="flux3", device="default")
    vae = g.add("VAELoader", "VAE", vae_name=FLUX2_VAE)
    return unet, clip, vae


def klein_t2i(p, mode="quality"):
    g = Graph()
    seed, (w, h) = _seed(p), _size(p)
    unet, clip, vae = _klein_base(g, mode)
    pos = g.add("CLIPTextEncode", "Промпт", clip=clip.out, text=p["prompt"])
    neg = g.add("ConditioningZeroOut", "Пустой негатив", conditioning=pos.out)
    lat = g.add("EmptyFlux2LatentImage", "Размер", width=w, height=h, batch_size=int(p.get("batch", 1)))
    steps = int(p.get("steps") or (8 if mode == "draft" else 16))
    ks = g.add("KSampler", "Генерация", model=unet.out, positive=pos.out, negative=neg.out, latent_image=lat.out, seed=seed,
               steps=steps, cfg=1.0, sampler_name=p.get("sampler", "euler"), scheduler="simple", denoise=1.0)
    img = g.add("VAEDecode", "Декодирование", samples=ks.out, vae=vae.out).out
    if mode == "quality" and p.get("hires", False):  # у дистиллята Klein второй проход портит кожу (тест 2026-11-20)
        # Hires в пикселях: латентный апскейл у Flux-VAE даёт пересвет и «пережаренную» текстуру
        up = g.add("ImageScaleBy", "Hires: увеличение", image=img, upscale_method="lanczos", scale_by=float(p.get("hires_scale", 1.5)))
        enc = g.add("VAEEncode", "Hires: кодирование", pixels=up.out, vae=vae.out)
        ks2 = g.add("KSampler", "Hires: дорисовка", model=unet.out, positive=pos.out, negative=neg.out, latent_image=enc.out,
                    seed=seed, steps=8, cfg=1.0, sampler_name="euler", scheduler="simple", denoise=float(p.get("hires_denoise", 0.3)))
        img = g.add("VAEDecode", "Hires: декодирование", samples=ks2.out, vae=vae.out).out
    if mode == "quality" and p.get("face_fix", False):
        img = _face_detailer(g, img, unet.out, clip.out, vae.out, pos.out, neg.out, seed, denoise=0.3)
    _save(g, img, p, "studio/klein")
    return g.to_api()


def klein_edit(p, mode="quality"):
    """Редактирование по команде / персонаж: p['images'] — имена файлов во входной папке (1–3 референса)."""
    g = Graph()
    seed = _seed(p)
    unet, clip, vae = _klein_base(g, mode)
    pos = g.add("CLIPTextEncode", "Инструкция", clip=clip.out, text=p["prompt"])
    neg = g.add("ConditioningZeroOut", "Пустой негатив", conditioning=pos.out)
    refs = {}
    for i, name in enumerate(p["images"][:4]):
        refs[f"images.image{i}"] = g.add("LoadImage", f"Референс {i + 1}", image=name).out
    rml = g.add("ReferenceMultiLatent", "Референсы", positive=pos.out, negative=neg.out, vae=vae.out,
                resolution="resize", **{"resolution.megapixels": float(p.get("megapixels", 1.0))}, **refs)
    latent_in = rml[2]
    if p.get("width") and p.get("height"):
        w, h = _size(p)
        latent_in = g.add("EmptyFlux2LatentImage", "Размер", width=w, height=h, batch_size=1).out
    steps = int(p.get("steps") or (8 if mode == "draft" else 16))
    ks = g.add("KSampler", "Правка", model=unet.out, positive=rml[0], negative=rml[1], latent_image=latent_in, seed=seed,
               steps=steps, cfg=1.0, sampler_name="euler", scheduler="simple", denoise=1.0)
    img = g.add("VAEDecode", "Декодирование", samples=ks.out, vae=vae.out).out
    if p.get("mask"):  # инпейнтинг: меняем только область маски, остальное — пиксель в пиксель
        src = refs["images.image0"]
        m = g.add("LoadImageMask", "Маска", image=p["mask"], channel="alpha" if p.get("mask_alpha") else "red")
        grown = g.add("GrowMask", "Расширить маску", mask=m.out, expand=int(p.get("mask_grow", 12)), tapered_corners=True)
        blur = g.add("ImageScale", "Подогнать размер", image=img, upscale_method="lanczos", width=int(p["src_w"]), height=int(p["src_h"]), crop="disabled")
        img = g.add("ImageCompositeMasked", "Вклеить область", destination=src, source=blur.out, x=0, y=0, resize_source=False, mask=grown.out).out
    _save(g, img, p, "studio/edit")
    return g.to_api()


def klein_outpaint(p, mode="quality"):
    """Расширение кадра: поля left/top/right/bottom в пикселях."""
    g = Graph()
    seed = _seed(p)
    unet, clip, vae = _klein_base(g, mode)
    # Серые поля модель копирует как есть, поэтому даём исходник референсом и просим более широкий кадр на холсте целевого размера
    src = g.add("LoadImage", "Исходник", image=p["images"][0])
    sw, sh = int(p["src_w"]), int(p["src_h"])
    tw, th = sw + int(p.get("left", 0)) + int(p.get("right", 0)), sh + int(p.get("top", 0)) + int(p.get("bottom", 0))
    k = (float(p.get("megapixels", 1.3)) * 1024 * 1024 / (tw * th)) ** 0.5
    tw, th = int(tw * k) // 16 * 16, int(th * k) // 16 * 16
    sides = [s for s, key in (("left", "left"), ("right", "right"), ("top", "top"), ("bottom", "bottom")) if int(p.get(key, 0)) > 0]
    text = ("Show a wider view of <ref_image_0>: extend the scene beyond the original frame on the " + " and ".join(sides) +
            ", continuing the surroundings naturally. Keep every element of the original image identical, same lighting, style and perspective. "
            + (p.get("prompt") or ""))
    pos = g.add("CLIPTextEncode", "Инструкция", clip=clip.out, text=text)
    neg = g.add("ConditioningZeroOut", "Пустой негатив", conditioning=pos.out)
    rml = g.add("ReferenceMultiLatent", "Референс", positive=pos.out, negative=neg.out, vae=vae.out,
                resolution="resize", **{"resolution.megapixels": 1.0}, **{"images.image0": src[0]})
    lat = g.add("EmptyFlux2LatentImage", "Новый размер кадра", width=tw, height=th, batch_size=1)
    steps = 8 if mode == "draft" else 16
    ks = g.add("KSampler", "Дорисовка", model=unet.out, positive=rml[0], negative=rml[1], latent_image=lat.out, seed=seed,
               steps=steps, cfg=1.0, sampler_name="euler", scheduler="simple", denoise=1.0)
    img = g.add("VAEDecode", "Декодирование", samples=ks.out, vae=vae.out)
    _save(g, img.out, p, "studio/outpaint")
    return g.to_api()


# ---------------------------------------------------------------- общие хелперы для LoRA и второго прохода
def _loras(g, model, loras, clip=None):
    """loras: [[имя, сила], ...]. Без clip — LoRA только на модель."""
    for name, w in loras or []:
        if clip is None:
            model = g.add("LoraLoaderModelOnly", f"LoRA {name}", model=model, lora_name=name, strength_model=float(w)).out
        else:
            ln = g.add("LoraLoader", f"LoRA {name}", model=model, clip=clip, lora_name=name, strength_model=float(w), strength_clip=float(w))
            model, clip = ln[0], ln[1]
    return model, clip


def _hires_pixels(g, img, model, pos, neg, vae, seed, scale, denoise, steps, cfg, sampler, scheduler):
    up = g.add("ImageScaleBy", "Hires: увеличение", image=img, upscale_method="lanczos", scale_by=scale)
    enc = g.add("VAEEncode", "Hires: кодирование", pixels=up.out, vae=vae)
    ks = g.add("KSampler", "Hires: дорисовка", model=model, positive=pos, negative=neg, latent_image=enc.out, seed=seed,
               steps=steps, cfg=cfg, sampler_name=sampler, scheduler=scheduler, denoise=denoise)
    return g.add("VAEDecode", "Hires: декодирование", samples=ks.out, vae=vae).out


# ---------------------------------------------------------------- Anima (аниме)
def anima_t2i(p, mode="quality"):
    g = Graph()
    seed, (w, h) = _seed(p), _size(p, (832, 1216))
    unet = g.add("UNETLoader", "Модель Anima", unet_name=p.get("model", "anima-turbo-v1.1.safetensors"), weight_dtype="default")
    clip = g.add("CLIPLoader", "Текстовый энкодер", clip_name="qwen_3_06b_base.safetensors", type="stable_diffusion", device="default")
    vae = g.add("VAELoader", "VAE", vae_name="qwen_image_vae.safetensors")
    model, _ = _loras(g, unet.out, p.get("loras"))
    pos = g.add("CLIPTextEncode", "Промпт", clip=clip.out, text=p["prompt"])
    neg = g.add("CLIPTextEncode", "Негатив", clip=clip.out, text=p.get("negative", "worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts"))
    lat = g.add("EmptyLatentImage", "Размер", width=w, height=h, batch_size=int(p.get("batch", 1)))
    steps = int(p.get("steps") or (8 if mode == "draft" else 12))
    cfg = float(p.get("cfg", 1.0))
    ks = g.add("KSampler", "Генерация", model=model, positive=pos.out, negative=neg.out, latent_image=lat.out, seed=seed,
               steps=steps, cfg=cfg, sampler_name="euler", scheduler="simple", denoise=1.0)
    img = g.add("VAEDecode", "Декодирование", samples=ks.out, vae=vae.out).out
    if mode == "quality" and p.get("hires", True):
        img = _hires_pixels(g, img, model, pos.out, neg.out, vae.out, seed, 1.5, float(p.get("hires_denoise", 0.35)), 8, cfg, "euler", "simple")
    _save(g, img, p, "studio/anima")
    return g.to_api()


# ---------------------------------------------------------------- Krea 2 (стили, 18+ реализм на базе Krea 2)
def krea2_t2i(p, mode="quality"):
    g = Graph()
    seed, (w, h) = _seed(p), _size(p)
    unet = g.add("UNETLoader", "Модель Krea 2", unet_name=p.get("model", "krea2_turbo_nvfp4.safetensors"), weight_dtype="default")
    clip = g.add("CLIPLoader", "Текстовый энкодер", clip_name=p.get("te", KLEIN_TE), type="krea2", device="default")
    vae = g.add("VAELoader", "VAE", vae_name="qwen_image_vae.safetensors")
    model, _ = _loras(g, unet.out, p.get("loras"))
    pos = g.add("CLIPTextEncode", "Промпт", clip=clip.out, text=p["prompt"])
    neg = g.add("ConditioningZeroOut", "Пустой негатив", conditioning=pos.out)
    lat = g.add("EmptyLatentImage", "Размер", width=w, height=h, batch_size=int(p.get("batch", 1)))
    steps = int(p.get("steps") or 8)
    ks = g.add("KSampler", "Генерация", model=model, positive=pos.out, negative=neg.out, latent_image=lat.out, seed=seed,
               steps=steps, cfg=1.0, sampler_name=p.get("sampler", "euler"), scheduler=p.get("scheduler", "simple"), denoise=1.0)
    img = g.add("VAEDecode", "Декодирование", samples=ks.out, vae=vae.out).out
    if mode == "quality" and p.get("hires", False):
        img = _hires_pixels(g, img, model, pos.out, neg.out, vae.out, seed, float(p.get("hires_scale", 1.5)), float(p.get("hires_denoise", 0.3)), 4, 1.0, "euler", "simple")
    if mode == "quality" and p.get("face_fix", False):
        img = _face_detailer(g, img, model, clip.out, vae.out, pos.out, neg.out, seed, steps=6, denoise=0.3)
    _save(g, img, p, p.get("prefix_default", "studio/krea2"))
    return g.to_api()


# ---------------------------------------------------------------- SDXL / Illustrious чекпоинты
def sdxl_t2i(p, mode="quality"):
    g = Graph()
    seed, (w, h) = _seed(p), _size(p, (832, 1216))
    ck = g.add("CheckpointLoaderSimple", "Чекпоинт", ckpt_name=p["model"])
    clip = g.add("CLIPSetLastLayer", "Clip skip 2", clip=ck[1], stop_at_clip_layer=-2).out
    model, clip = _loras(g, ck[0], p.get("loras"), clip)
    pos = g.add("CLIPTextEncode", "Промпт", clip=clip, text=p["prompt"])
    neg = g.add("CLIPTextEncode", "Негатив", clip=clip, text=p.get("negative", "worst quality, low quality, bad anatomy, bad hands, extra digits, watermark, signature, blurry"))
    lat = g.add("EmptyLatentImage", "Размер", width=w, height=h, batch_size=int(p.get("batch", 1)))
    cfg = float(p.get("cfg", 5.0))
    steps = int(p.get("steps") or (18 if mode == "draft" else 28))
    ks = g.add("KSampler", "Генерация", model=model, positive=pos.out, negative=neg.out, latent_image=lat.out, seed=seed,
               steps=steps, cfg=cfg, sampler_name=p.get("sampler", "euler_ancestral"), scheduler="normal", denoise=1.0)
    img = g.add("VAEDecode", "Декодирование", samples=ks.out, vae=ck[2]).out
    if mode == "quality" and p.get("hires", True):
        img = _hires_pixels(g, img, model, pos.out, neg.out, ck[2], seed, 1.5, 0.4, 14, cfg, "euler_ancestral", "normal")
    if mode == "quality" and p.get("face_fix", True):
        img = _face_detailer(g, img, model, clip, ck[2], pos.out, neg.out, seed, steps=16, denoise=0.35, cfg=cfg, sampler="euler_ancestral", scheduler="normal")
    _save(g, img, p, "studio/sdxl")
    return g.to_api()


# ---------------------------------------------------------------- Апскейл SeedVR2 (нативные ноды ComfyUI)
def _seedvr2(g, img, scale, seed, alpha=None):
    vae = g.add("VAELoader", "VAE SeedVR2", vae_name="seedvr2_ema_vae_fp16.safetensors")
    unet = g.add("UNETLoader", "SeedVR2 7B", unet_name="seedvr2_7b_sharp_fp8_e4m3fn.safetensors", weight_dtype="default")
    src = g.add("JoinImageWithAlpha", "Альфа", image=img, alpha=alpha).out if alpha is not None else img
    rs = g.add("ResizeImageMaskNode", "Целевой размер", input=src, resize_type="scale by multiplier",
               **{"resize_type.multiplier": float(scale)}, scale_method="lanczos")
    pre = g.add("SeedVR2Preprocess", "Подготовка", resized_images=rs.out)
    enc = g.add("VAEEncodeTiled", "Кодирование (тайлы)", pixels=pre.out, vae=vae.out, tile_size=512, overlap=128, temporal_size=4096, temporal_overlap=8)
    cond = g.add("SeedVR2Conditioning", "Условие", model=unet.out, vae_conditioning=enc.out)
    ks = g.add("KSampler", "Восстановление", model=unet.out, positive=cond[0], negative=cond[1], latent_image=enc.out, seed=seed,
               steps=1, cfg=1.0, sampler_name="euler", scheduler="simple", denoise=1.0)
    dec = g.add("VAEDecodeTiled", "Декодирование (тайлы)", samples=ks.out, vae=vae.out, tile_size=512, overlap=128, temporal_size=4096, temporal_overlap=8)
    return g.add("SeedVR2PostProcessing", "Цветокоррекция", images=dec.out, original_resized_images=rs.out, color_correction_method="lab").out


def upscale(p, mode="quality"):
    """Черновик: 2x, Качество: 4x (по умолчанию). Входная картинка ограничивается ~1 Мп, чтобы не выйти за VRAM."""
    g = Graph()
    src = g.add("LoadImage", "Исходник", image=p["images"][0])
    scale = float(p.get("scale") or (2 if mode == "draft" else 4))
    img = src[0]
    if p.get("limit_input", True):
        img = g.add("ImageScaleToTotalPixels", "Ограничить вход", image=img, upscale_method="lanczos",
                    megapixels=float(p.get("max_input_mp", 1.0)), resolution_steps=1).out
    out = _seedvr2(g, img, scale, _seed(p))
    _save(g, out, p, "studio/upscale")
    return g.to_api()


# ---------------------------------------------------------------- Удаление фона BiRefNet
def remove_bg(p, mode="quality"):
    g = Graph()
    src = g.add("LoadImage", "Исходник", image=p["images"][0])
    m = g.add("LoadBackgroundRemovalModel", "BiRefNet", bg_removal_name="birefnet.safetensors")
    mask = g.add("RemoveBackground", "Маска фона", bg_removal_model=m.out, image=src[0])
    inv = g.add("InvertMask", "Инверсия", mask=mask.out)
    out = g.add("JoinImageWithAlpha", "PNG с прозрачностью", image=src[0], alpha=inv.out)
    _save(g, out.out, p, "studio/nobg")
    return g.to_api()


# ---------------------------------------------------------------- Видео: Wan 2.2 14B (high → low)
WAN_NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
           "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")
WAN_SETS = {
    # базовая Wan 2.2 + lightx2v (ускоряющая LoRA)
    "base": {"high": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "low": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
             "loras_high": [["wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors", 1.0]],
             "loras_low": [["wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", 1.0]]},
    # 18+: ускорение уже встроено в модели
    "nsfw_real": {"high": "Wan2_2-I2V-A14B-NSFW_fast_move-HIGH_Q6K(lightning_edition)V2.gguf",
                  "low": "Wan2_2-I2V-A14B-NSFW_fast_move-LOW_Q6K(lightning_edition)V2.gguf", "loras_high": [], "loras_low": []},
    # SmoothMix при 4 шагах даёт размытие (тест 2026-11-20) — минимум 8
    "nsfw_anime": {"high": "SmoothMix_I2V_High_v2.safetensors", "low": "SmoothMix_I2V_Low_v2.safetensors", "loras_high": [], "loras_low": [],
                   "steps": {"draft": 8, "quality": 10}},
}
CAMERA_RU = {"static": "static camera, locked-off shot", "push_in": "slow camera push-in (dolly in)", "pull_out": "slow camera pull-out (dolly out)",
             "pan": "smooth horizontal camera pan", "orbit": "smooth camera orbit around the subject"}


def _wan_model(g, name, loras):
    if name.endswith(".gguf"):
        m = g.add("UnetLoaderGGUF", "Модель (GGUF)", unet_name=name).out
    else:
        m = g.add("UNETLoader", "Модель", unet_name=name, weight_dtype="default").out
    m, _ = _loras(g, m, loras)
    return g.add("ModelSamplingSD3", "Сдвиг", model=m, shift=5.0 if loras is not None else 8.0).out


def wan22_video(p, mode="quality"):
    """Картинка → видео (start), или первый+последний кадр (start+end). Длительность в секундах при 16 к/с."""
    g = Graph()
    seed = _seed(p)
    s = WAN_SETS[p.get("set", "base")]
    w, h = (832, 480) if mode == "draft" else (1024, 576)
    if p.get("portrait"):
        w, h = h, w
    if p.get("width"):
        w, h = _size(p)
    frames = int(round(float(p.get("seconds", 5)) * 16)) // 4 * 4 + 1
    clip = g.add("CLIPLoader", "UMT5", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default")
    vae = g.add("VAELoader", "VAE Wan", vae_name="wan_2.1_vae.safetensors")
    text = p["prompt"] + (", " + CAMERA_RU[p["camera"]] if p.get("camera") in CAMERA_RU else "")
    pos = g.add("CLIPTextEncode", "Промпт", clip=clip.out, text=text)
    neg = g.add("CLIPTextEncode", "Негатив", clip=clip.out, text=p.get("negative", WAN_NEG))
    start = g.add("LoadImage", "Первый кадр", image=p["images"][0]).out
    if len(p["images"]) > 1:
        end = g.add("LoadImage", "Последний кадр", image=p["images"][1]).out
        cond = g.add("WanFirstLastFrameToVideo", "Первый + последний кадр", positive=pos.out, negative=neg.out, vae=vae.out,
                     width=w, height=h, length=frames, batch_size=1, start_image=start, end_image=end)
    else:
        cond = g.add("WanImageToVideo", "Картинка → видео", positive=pos.out, negative=neg.out, vae=vae.out,
                     width=w, height=h, length=frames, batch_size=1, start_image=start)
    hi = _wan_model(g, s["high"], s["loras_high"])
    lo = _wan_model(g, s["low"], s["loras_low"])
    steps = int(p.get("steps") or s.get("steps", {}).get(mode) or (4 if mode == "draft" else 8))
    half = steps // 2
    k1 = g.add("KSamplerAdvanced", "Этап 1 (high)", model=hi, add_noise="enable", noise_seed=seed, steps=steps, cfg=1.0, sampler_name="euler",
               scheduler="simple", positive=cond[0], negative=cond[1], latent_image=cond[2], start_at_step=0, end_at_step=half,
               return_with_leftover_noise="enable")
    k2 = g.add("KSamplerAdvanced", "Этап 2 (low)", model=lo, add_noise="disable", noise_seed=seed, steps=steps, cfg=1.0, sampler_name="euler",
               scheduler="simple", positive=cond[0], negative=cond[1], latent_image=k1.out, start_at_step=half, end_at_step=10000,
               return_with_leftover_noise="disable")
    frames_img = g.add("VAEDecode", "Декодирование", samples=k2.out, vae=vae.out).out
    fps = 16
    if p.get("smooth"):
        frames_img = _interpolate(g, frames_img, 2)
        fps = 32
    vid = g.add("CreateVideo", "Сборка видео", images=frames_img, fps=float(fps))
    g.add("SaveVideo", "Сохранить видео", video=vid.out, filename_prefix=p.get("prefix", "studio/video"), format="auto", codec="auto")
    return g.to_api()


def _interpolate(g, frames, mult):
    m = g.add("FrameInterpolationModelLoader", "RIFE", model_name="rife_v4.26.safetensors")
    return g.add("FrameInterpolate", "Плавность (RIFE)", interp_model=m.out, images=frames, multiplier=int(mult)).out


# ---------------------------------------------------------------- Видео: MiniMax-H3 (со звуком)
def h3_video(p, mode="quality"):
    """Текст → видео (без картинок), картинка → видео (1), первый+последний кадр (2). 24 к/с, звук генерируется сам."""
    g = Graph()
    seed = _seed(p)
    unet = g.add("UnetLoaderGGUF", "MiniMax-H3 (GGUF)", unet_name="minimax_h3_fl2va_pruned-Q4_K.gguf").out
    if mode == "draft" or p.get("turbo"):
        unet, _ = _loras(g, unet, [["minimax_h3_turbo_8step_v1.2.safetensors", 1.0]])
    clip = g.add("CLIPLoader", "Текстовый энкодер", clip_name="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", type="minimax", device="default")
    vvae = g.add("VAELoader", "VAE видео", vae_name="minimax_h3_video_vae_fp16.safetensors")
    avae = g.add("VAELoader", "VAE звука", vae_name="minimax_h3_audio_vae_fp32.safetensors")
    mp = 0.4 if mode == "draft" else 0.6
    ar = float(p.get("aspect", 16 / 9))
    w = int((mp * 1024 * 1024 * ar) ** 0.5) // 32 * 32
    h = int(w / ar) // 32 * 32
    x = max(5, round(float(p.get("seconds", 5)) * 24))
    length = x + (5 - x % 17) % 17
    text = p["prompt"] + (", " + CAMERA_RU[p["camera"]] if p.get("camera") in CAMERA_RU else "")
    extra = {}
    imgs = p.get("images") or []
    if imgs:
        extra["first_frame"] = g.add("LoadImage", "Первый кадр", image=imgs[0]).out
    if len(imgs) > 1:
        extra["last_frame"] = g.add("LoadImage", "Последний кадр", image=imgs[1]).out
    cond = g.add("MiniMaxH3ImageToVideo", "Подготовка", clip=clip.out, vae=vvae.out, prompt=text, width=w, height=h, length=length, **extra)
    steps = int(p.get("steps") or (6 if mode == "draft" else 20))
    sch = g.add("BasicScheduler", "Шаги", model=unet, scheduler="simple", steps=steps, denoise=1.0)
    smp = g.add("KSamplerSelect", "Сэмплер", sampler_name="res_multistep")
    noise = g.add("RandomNoise", "Шум", noise_seed=seed)
    guider = g.add("BasicGuider", "Гайдер", model=unet, conditioning=cond[0])
    out = g.add("SamplerCustomAdvanced", "Генерация", noise=noise.out, guider=guider.out, sampler=smp.out, sigmas=sch.out, latent_image=cond[1])
    frames = g.add("VAEDecode", "Кадры", samples=out[0], vae=vvae.out).out
    audio = g.add("VAEDecodeAudio", "Звук", samples=out[0], vae=avae.out).out
    vid = g.add("CreateVideo", "Сборка видео", images=frames, fps=24.0, audio=audio)
    g.add("SaveVideo", "Сохранить видео", video=vid.out, filename_prefix=p.get("prefix", "studio/h3"), format="auto", codec="auto")
    return g.to_api()


# ---------------------------------------------------------------- Улучшение видео и звук
def _load_video(g, name):
    v = g.add("LoadVideo", "Видео", file=name)
    return v.out, g.add("GetVideoComponents", "Кадры и звук", video=v.out)


def video_enhance(p, mode="quality"):
    """Черновик: плавность x2 (RIFE). Качество: плавность + апскейл SeedVR2 x2."""
    g = Graph()
    _, comp = _load_video(g, p["videos"][0])
    frames = comp[0]
    if mode == "quality" and p.get("upscale", True):
        frames = _seedvr2(g, frames, float(p.get("scale", 2)), _seed(p))
    mult = int(p.get("multiplier", 2))
    if mult > 1:
        frames = _interpolate(g, frames, mult)
    fps = float(p.get("fps", 16)) * mult
    vid = g.add("CreateVideo", "Сборка", images=frames, fps=fps, audio=comp[1])
    g.add("SaveVideo", "Сохранить видео", video=vid.out, filename_prefix=p.get("prefix", "studio/enhanced"), format="auto", codec="auto")
    return g.to_api()


def video_audio(p, mode="quality"):
    """Звук к видео (MMAudio): описание звука + негатив; длительность = длительности ролика (передаёт backend)."""
    g = Graph()
    _, comp = _load_video(g, p["videos"][0])
    mm = g.add("MMAudioModelLoader", "MMAudio", mmaudio_model="mmaudio_large_44k_v2_fp16.safetensors", base_precision="fp16")
    fu = g.add("MMAudioFeatureUtilsLoader", "Утилиты MMAudio", vae_model="mmaudio_vae_44k_fp16.safetensors",
               synchformer_model="mmaudio_synchformer_fp16.safetensors", clip_model="apple_DFN5B-CLIP-ViT-H-14-384_fp16.safetensors",
               mode="44k", precision="fp16")
    au = g.add("MMAudioSampler", "Генерация звука", mmaudio_model=mm.out, feature_utils=fu.out, duration=float(p.get("duration", 5)),
               steps=12 if mode == "draft" else 25, cfg=4.5, seed=_seed(p), prompt=p.get("prompt", ""),
               negative_prompt=p.get("negative", "voices, talking, music"), mask_away_clip=False, force_offload=True,
               # MMAudio берёт кадры «как есть» и считает их 25 к/с — пересэмплируем, иначе звук короче и не в синхроне
               images=g.add("VHS_LoadVideo", "Кадры 25 к/с для MMAudio", video=p["videos"][0], force_rate=25.0, custom_width=0,
                            custom_height=0, frame_load_cap=0, skip_first_frames=0, select_every_nth=1, format="AnimateDiff")[0])
    vid = g.add("CreateVideo", "Сборка", images=comp[0], fps=float(p.get("fps", 16)), audio=au.out)
    g.add("SaveVideo", "Сохранить видео", video=vid.out, filename_prefix=p.get("prefix", "studio/sound"), format="auto", codec="auto")
    return g.to_api()


# ---------------------------------------------------------------- 3D: Pixal3D (официальный шаблон, сконвертирован ui2api)
def image_to_3d(p, mode="quality"):
    """Картинка → 3D-модель с текстурой (GLB). Фон удаляется автоматически (BiRefNet внутри шаблона)."""
    import json, pathlib, copy
    path = pathlib.Path(__file__).resolve().parents[2] / "workflows" / "api" / "3d_pixal3d_trellis2_image_to_model.json"
    api = copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))
    seed = _seed(p)
    api["122"]["inputs"]["image"] = p["images"][0]
    api.pop("40", None)  # TRELLIS.2 не установлен — всегда ветка Pixal3D
    api["318"]["inputs"]["on_true"] = ["319", 0]
    api["322"]["inputs"].update(filename_prefix=p.get("prefix", "studio/3d"), viewport_state="", width=1024, height=1024)
    for i, nid in enumerate(("3", "18", "23", "12")):
        api[nid]["inputs"]["seed"] = seed + i
    if mode == "draft":
        for nid in ("3", "18", "23", "12"):
            api[nid]["inputs"]["steps"] = max(6, api[nid]["inputs"]["steps"] // 2)
        api["288"]["inputs"]["value"] = 2048
        api["186"]["inputs"]["target_face_count" if "target_face_count" in api["186"]["inputs"] else next(iter(api["186"]["inputs"]))] = 300000
    return api


DETAIL_PROMPTS = {
    "face_hands": "Retouch <ref_image_0> like a professional photo retoucher: fix the face and hands. Remove blotches, color stains, noise, "
                  "smeared or painted-looking textures and any distortions; make the skin look like a natural high-quality photograph with fine pores; "
                  "clear symmetric eyes; correct hand anatomy with five fingers. Keep the same person, identity, expression, pose, framing and background.",
    "eyes": "Refine the eyes in <ref_image_0>: sharp, clear, symmetric, natural catchlights. Keep everything else exactly unchanged.",
}


def detailer(p, mode="quality"):
    """Детейлер: правка Klein с фиксированной инструкцией (в тестах дистиллят Klein плохо переносит частичную перерисовку FaceDetailer)."""
    q = dict(p)
    q["prompt"] = DETAIL_PROMPTS.get(p.get("target", "face_hands")) + (" " + p["prompt"] if p.get("prompt") else "")
    q.setdefault("prefix", "studio/detail")
    q.setdefault("megapixels", 1.5 if mode == "quality" else 1.0)
    return klein_edit(q, mode)


REGISTRY = {
    "detailer": detailer,
    "image_to_3d": image_to_3d,
    "video_enhance": video_enhance,
    "video_audio": video_audio,
    "wan22_video": wan22_video,
    "h3_video": h3_video,
    "upscale": upscale,
    "remove_bg": remove_bg,
    "anima_t2i": anima_t2i,
    "krea2_t2i": krea2_t2i,
    "sdxl_t2i": sdxl_t2i,
    "klein_t2i": klein_t2i,
    "klein_edit": klein_edit,
    "klein_outpaint": klein_outpaint,
}
