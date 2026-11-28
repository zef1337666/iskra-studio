"""Workflow студии в API-формате ComfyUI.

Каждая функция принимает параметры (dict) и режим 'draft' | 'quality', возвращает граф.
Ускорения, заметно влияющие на качество, используются только в 'draft'.
"""
import math, random
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
def _finish(g, img, p, mode, seed):
    """Доводка в «Качестве»: SeedVR2 восстанавливает мелкие детали (кожа, волосы, ткань) без перерисовки композиции."""
    if mode == "quality" and p.get("finish_upscale"):
        return _seedvr2(g, img, float(p.get("finish_scale", 1.5)), seed)
    return img


class _M:  # модель после цепочки LoRA (совместима с .out)
    def __init__(self, out):
        self.out = out


def _klein_base(g, mode, loras=None, unet_name=None):
    unet = g.add("UNETLoader", "Модель Klein", unet_name=unet_name or KLEIN[mode], weight_dtype="default")
    clip = g.add("CLIPLoader", "Текстовый энкодер", clip_name=KLEIN_TE, type="flux3", device="default")
    vae = g.add("VAELoader", "VAE", vae_name=FLUX2_VAE)
    model, _ = _loras(g, unet.out, loras)  # LoRA пресета / обученного персонажа
    return _M(model), clip, vae


def klein_t2i(p, mode="quality"):
    g = Graph()
    seed, (w, h) = _seed(p), _size(p)
    unet, clip, vae = _klein_base(g, mode, p.get("loras"), p.get("unet"))
    pos = g.add("CLIPTextEncode", "Промпт", clip=clip.out, text=p["prompt"])
    neg = g.add("ConditioningZeroOut", "Пустой негатив", conditioning=pos.out)
    lat = g.add("EmptyFlux2LatentImage", "Размер", width=w, height=h, batch_size=int(p.get("batch", 1)))
    steps = int(p.get("steps") or (8 if mode == "draft" else 16))
    ks = g.add("KSampler", "Генерация", model=unet.out, positive=pos.out, negative=neg.out, latent_image=lat.out, seed=seed,
               steps=steps, cfg=float(p.get("cfg") or 1.0), sampler_name=p.get("sampler", "euler"), scheduler="simple", denoise=1.0)
    img = g.add("VAEDecode", "Декодирование", samples=ks.out, vae=vae.out).out
    img = _finish(g, img, p, mode, seed)
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
    unet, clip, vae = _klein_base(g, mode, p.get("loras"))
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
    unet, clip, vae = _klein_base(g, mode, p.get("loras"))
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
    cfg = float(p.get("cfg") or 1.0)  # Turbo-модели — CFG 1 (негатив не нужен); не-Turbo (Real Dream) — CFG > 1 с настоящим негативом
    neg = (g.add("CLIPTextEncode", "Негатив", clip=clip.out, text=p.get("negative") or "blurry, lowres, deformed, bad anatomy, extra fingers, watermark")
           if cfg > 1 else g.add("ConditioningZeroOut", "Пустой негатив", conditioning=pos.out))
    steps = int(p.get("steps") or 8)
    denoise = 1.0
    if p.get("img2img") and p.get("images"):
        # «по картинке»: исходник — основа (поза, композиция, внешность); сила влияния 0..1 -> denoise 0.9..0.25
        src = g.add("LoadImage", "Исходная картинка", image=p["images"][0])
        fit = g.add("ImageScale", "Под размер кадра", image=src[0], upscale_method="lanczos", width=w, height=h, crop="center")
        lat = g.add("VAEEncode", "Кодирование исходника", pixels=fit.out, vae=vae.out)
        denoise = max(0.25, min(0.9, 1.0 - 0.75 * float(p.get("ref_strength", 0.6))))
        steps = max(steps, round(steps / denoise))  # чтобы реальных шагов дорисовки было столько же, сколько при генерации с нуля
    else:
        lat = g.add("EmptyLatentImage", "Размер", width=w, height=h, batch_size=int(p.get("batch", 1)))
    # при частичной перерисовке er_sde даёт белые «крапинки» на коже (тест 2026-11-26) — для «по картинке» euler/simple
    sampler, scheduler = (("euler", "simple") if denoise < 1.0 else (p.get("sampler", "euler"), p.get("scheduler", "simple")))
    ks = g.add("KSampler", "Генерация", model=model, positive=pos.out, negative=neg.out, latent_image=lat.out, seed=seed,
               steps=steps, cfg=cfg, sampler_name=sampler, scheduler=scheduler, denoise=denoise)
    img = g.add("VAEDecode", "Декодирование", samples=ks.out, vae=vae.out).out
    img = _finish(g, img, p, mode, seed)
    if mode == "quality" and p.get("hires", False):
        img = _hires_pixels(g, img, model, pos.out, neg.out, vae.out, seed, float(p.get("hires_scale", 1.5)), float(p.get("hires_denoise", 0.3)), 4, 1.0, "euler", "simple")
    if mode == "quality" and p.get("face_fix", False):
        img = _face_detailer(g, img, model, clip.out, vae.out, pos.out, neg.out, seed, steps=6, denoise=0.3)
    _save(g, img, p, p.get("prefix_default", "studio/krea2"))
    return g.to_api()


# ---------------------------------------------------------------- Перенос персонажа на Krea 2 (Identity Edit V2, встроенные ноды)
def krea2_identity(p, mode="quality"):
    """Персонаж с референса (1 картинка) в новой сцене/позе/одежде. Механизм — как в официальном шаблоне Krea 2 Style Reference:
    TextEncodeQwenImageEditPlus (референс через Qwen3-VL + латент) -> FluxKontextMultiReferenceLatentMethod, плюс LoRA Identity Edit V2."""
    g = Graph()
    seed, (w, h) = _seed(p), _size(p)
    unet = g.add("UNETLoader", "Модель Krea 2", unet_name=p.get("model", "lustify-v10-krea-turbo-int8_convrot.safetensors"), weight_dtype="default")
    clip = g.add("CLIPLoader", "Текстовый энкодер", clip_name=p.get("te", KLEIN_TE), type="krea2", device="default")
    vae = g.add("VAELoader", "VAE", vae_name="qwen_image_vae.safetensors")
    loras = [["krea2_identity_edit_v2.safetensors", float(p.get("identity_strength", 1.0))]] + list(p.get("loras") or [])
    model, _ = _loras(g, unet.out, loras)
    model = g.add("ModelSamplingFlux", "Сдвиг", model=model, max_shift=1.15, base_shift=0.5, width=w, height=h).out
    refs = {f"image{i + 1}": g.add("LoadImage", f"Персонаж {i + 1}", image=n)[0] for i, n in enumerate(p["images"][:2])}
    # Проверено замером сходства лиц (ArcFace, 2026-11-27): крупный план лица вторым референсом, референс крупнее 1 Мп и «зрение»
    # Qwen-VL на 768/1024 px на встроенных нодах сходство не повышают; LoRA реализма (Vérité) — понижает, поэтому в пресете её нет.
    cond = g.add("TextEncodeQwenImageEditPlus", "Промпт + персонаж", clip=clip.out, prompt=p["prompt"], vae=vae.out, **refs).out
    pos = g.add("FluxKontextMultiReferenceLatentMethod", "Референс", conditioning=cond, reference_latents_method="index_timestep_zero")
    neg = g.add("ConditioningZeroOut", "Пустой негатив", conditioning=pos.out)
    guider = g.add("CFGGuider", "Гайдер", model=model, positive=pos.out, negative=neg.out, cfg=1.0)
    steps = int(p.get("steps") or (8 if mode == "draft" else 10))
    sch = g.add("BasicScheduler", "Шаги", model=model, scheduler="simple", steps=steps, denoise=1.0)
    smp = g.add("KSamplerSelect", "Сэмплер", sampler_name="euler")
    noise = g.add("RandomNoise", "Шум", noise_seed=seed)
    lat = g.add("EmptyLatentImage", "Размер", width=w, height=h, batch_size=1)
    out = g.add("SamplerCustomAdvanced", "Генерация", noise=noise.out, guider=guider.out, sampler=smp.out, sigmas=sch.out, latent_image=lat.out)
    img = g.add("VAEDecode", "Декодирование", samples=out[0], vae=vae.out).out
    img = _finish(g, img, p, mode, seed)
    _save(g, img, p, "studio/identity")
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
    seconds = min(float(p.get("seconds", 5)), MAX_VIDEO_SEC)
    two = len(p["images"]) > 1  # первый + последний кадр — одним куском
    n = 1 if two else max(1, math.ceil(seconds / WAN_SEG_SEC - 1e-6))  # длиннее 5 с — продолжение по последнему кадру
    frames = int(round(seconds / n * 16)) // 4 * 4 + 1
    clip = g.add("CLIPLoader", "UMT5", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default")
    vae = g.add("VAELoader", "VAE Wan", vae_name="wan_2.1_vae.safetensors")
    text = p["prompt"] + (", " + CAMERA_RU[p["camera"]] if p.get("camera") in CAMERA_RU else "")
    pos = g.add("CLIPTextEncode", "Промпт", clip=clip.out, text=text)
    neg = g.add("CLIPTextEncode", "Негатив", clip=clip.out, text=p.get("negative", WAN_NEG))
    start = g.add("LoadImage", "Первый кадр", image=p["images"][0]).out
    hi = _wan_model(g, s["high"], s["loras_high"])
    lo = _wan_model(g, s["low"], s["loras_low"])
    steps = int(p.get("steps") or s.get("steps", {}).get(mode) or (4 if mode == "draft" else 8))
    half = steps // 2
    frames_img = None
    for k in range(n):
        part = f"Часть {k + 1}: " if n > 1 else ""
        if two:
            end = g.add("LoadImage", "Последний кадр", image=p["images"][1]).out
            cond = g.add("WanFirstLastFrameToVideo", "Первый + последний кадр", positive=pos.out, negative=neg.out, vae=vae.out,
                         width=w, height=h, length=frames, batch_size=1, start_image=start, end_image=end)
        else:
            cond = g.add("WanImageToVideo", part + "картинка → видео", positive=pos.out, negative=neg.out, vae=vae.out,
                         width=w, height=h, length=frames, batch_size=1, start_image=start)
        k1 = g.add("KSamplerAdvanced", part + "этап 1 (high)", model=hi, add_noise="enable", noise_seed=seed + k, steps=steps, cfg=1.0, sampler_name="euler",
                   scheduler="simple", positive=cond[0], negative=cond[1], latent_image=cond[2], start_at_step=0, end_at_step=half,
                   return_with_leftover_noise="enable")
        k2 = g.add("KSamplerAdvanced", part + "этап 2 (low)", model=lo, add_noise="disable", noise_seed=seed + k, steps=steps, cfg=1.0, sampler_name="euler",
                   scheduler="simple", positive=cond[0], negative=cond[1], latent_image=k1.out, start_at_step=half, end_at_step=10000,
                   return_with_leftover_noise="disable")
        dec = g.add("VAEDecode", part + "декодирование", samples=k2.out, vae=vae.out).out
        frames_img = dec if frames_img is None else _append_frames(g, frames_img, dec, frames, part)
        start = g.add("ImageFromBatch", part + "последний кадр", image=dec, batch_index=-1, length=1).out
    fps = 16
    if p.get("smooth"):
        frames_img = _interpolate(g, frames_img, 2)
        fps = 32
    vid = g.add("CreateVideo", "Сборка видео", images=frames_img, fps=float(fps))
    g.add("SaveVideo", "Сохранить видео", video=vid.out, filename_prefix=p.get("prefix", "studio/video"), format="auto", codec="auto")
    return g.to_api()


MAX_VIDEO_SEC = 30
WAN_SEG_SEC = 5.0   # Wan 2.2 лучше всего держит ~5 с (81 кадр) за один проход
H3_SEG_SEC = 8.0    # MiniMax-H3 — до 8 с за проход


def _append_frames(g, frames, new, length, part):
    """Склейка кусков: первый кадр нового куска совпадает с последним предыдущего — его убираем."""
    tail = g.add("ImageFromBatch", part + "без повтора кадра", image=new, batch_index=1, length=max(1, length - 1)).out
    return g.add("ImageBatch", part + "склейка", image1=frames, image2=tail).out


def _interpolate(g, frames, mult):
    m = g.add("FrameInterpolationModelLoader", "RIFE", model_name="rife_v4.26.safetensors")
    return g.add("FrameInterpolate", "Плавность (RIFE)", interp_model=m.out, images=frames, multiplier=int(mult)).out


# ---------------------------------------------------------------- Видео: MiniMax-H3 (со звуком)
def h3_video(p, mode="quality"):
    """Текст → видео (без картинок), картинка → видео (1), первый+последний кадр (2). 24 к/с, звук генерируется сам."""
    g = Graph()
    seed = _seed(p)
    unet = g.add("UNETLoader", "MiniMax-H3", unet_name=p.get("model", "minimax_h3_fl2va_pruned_w6a8.safetensors"), weight_dtype="default").out
    if mode == "draft" or p.get("turbo"):
        unet, _ = _loras(g, unet, [["minimax_h3_turbo_8step_v1.2.safetensors", 1.0]])
    clip = g.add("CLIPLoader", "Текстовый энкодер", clip_name="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", type="minimax", device="default")
    vvae = g.add("VAELoader", "VAE видео", vae_name="minimax_h3_video_vae_fp16.safetensors")
    avae = g.add("VAELoader", "VAE звука", vae_name="minimax_h3_audio_vae_fp32.safetensors")
    mp = 0.4 if mode == "draft" else 0.6
    ar = float(p.get("aspect", 16 / 9))
    w = int((mp * 1024 * 1024 * ar) ** 0.5) // 32 * 32
    h = int(w / ar) // 32 * 32
    seconds = min(float(p.get("seconds", 5)), MAX_VIDEO_SEC)
    imgs = p.get("images") or []
    n = 1 if len(imgs) > 1 else max(1, math.ceil(seconds / H3_SEG_SEC - 1e-6))  # длиннее 8 с — продолжение по последнему кадру
    x = max(5, round(seconds / n * 24))
    lo = x - (x - 5) % 17  # H3 принимает длину вида 17k+5 кадров — берём ближайшую, а не всегда большую
    length = lo if lo >= 5 and x - lo <= 8 else lo + 17
    text = p["prompt"] + (", " + CAMERA_RU[p["camera"]] if p.get("camera") in CAMERA_RU else "")
    first = g.add("LoadImage", "Первый кадр", image=imgs[0]).out if imgs else None
    steps = int(p.get("steps") or (6 if mode == "draft" else 20))
    sch = g.add("BasicScheduler", "Шаги", model=unet, scheduler="simple", steps=steps, denoise=1.0)
    smp = g.add("KSamplerSelect", "Сэмплер", sampler_name="res_multistep")
    frames = audio = None
    for k in range(n):
        part = f"Часть {k + 1}: " if n > 1 else ""
        extra = {"first_frame": first} if first is not None else {}
        if len(imgs) > 1:
            extra["last_frame"] = g.add("LoadImage", "Последний кадр", image=imgs[1]).out
        cond = g.add("MiniMaxH3ImageToVideo", part + "подготовка", clip=clip.out, vae=vvae.out, prompt=text, width=w, height=h, length=length, **extra)
        noise = g.add("RandomNoise", part + "шум", noise_seed=seed + k)
        guider = g.add("BasicGuider", part + "гайдер", model=unet, conditioning=cond[0])
        out = g.add("SamplerCustomAdvanced", part + "генерация", noise=noise.out, guider=guider.out, sampler=smp.out, sigmas=sch.out, latent_image=cond[1])
        fr = g.add("VAEDecode", part + "кадры", samples=out[0], vae=vvae.out).out
        au = g.add("VAEDecodeAudio", part + "звук", samples=out[0], vae=avae.out).out
        frames = fr if frames is None else _append_frames(g, frames, fr, length, part)
        audio = au if audio is None else g.add("AudioConcat", part + "склейка звука", audio1=audio, audio2=au, direction="after").out
        first = g.add("ImageFromBatch", part + "последний кадр", image=fr, batch_index=-1, length=1).out
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


# ---------------------------------------------------------------- Поза и композиция: Z-Image Turbo + Fun ControlNet Union 2.1
def _zimage(g):
    unet = g.add("UNETLoader", "Z-Image Turbo", unet_name="z_image_turbo_int8_convrot.safetensors", weight_dtype="default")
    clip = g.add("CLIPLoader", "Qwen3 4B", clip_name="qwen_3_4b_fp8_mixed.safetensors", type="lumina2", device="default")
    vae = g.add("VAELoader", "VAE", vae_name="ae.safetensors")
    return unet, clip, vae


def zimage_control(p, mode="quality"):
    """control: pose (скелет DWPose) | depth (глубина) | canny (контуры) | raw (картинка уже является позой/скетчем)."""
    g = Graph()
    seed = _seed(p)
    unet, clip, vae = _zimage(g)
    src = g.add("LoadImage", "Референс позы/композиции", image=p["images"][0])
    img = g.add("ImageScaleToMaxDimension", "Размер", image=src[0], upscale_method="lanczos", largest_size=1024 if mode == "draft" else 1344).out
    kind = p.get("control", "pose")
    if kind == "pose":
        img = g.add("DWPreprocessor", "Скелет позы", image=img, detect_hand="enable", detect_body="enable", detect_face="enable", resolution=1024,
                    bbox_detector="yolox_l.onnx", pose_estimator="dw-ll_ucoco_384_bs5.torchscript.pt", scale_stick_for_xinsr_cn="disable")[0]
    elif kind == "depth":
        img = g.add("DepthAnythingV2Preprocessor", "Карта глубины", image=img, ckpt_name="depth_anything_v2_vitl.pth", resolution=1024).out
    elif kind == "canny":
        img = g.add("Canny", "Контуры", image=img, low_threshold=0.1, high_threshold=0.32).out
    patch = g.add("ModelPatchLoader", "ControlNet Union", name="Z-Image-Turbo-Fun-Controlnet-Union-2.1-2602-8steps.safetensors")
    model = g.add("QwenImageDiffsynthControlnet", "Применить ControlNet", model=unet.out, model_patch=patch.out, vae=vae.out, image=img,
                  # depth/canny при 0.8 до конца дают «пластик» (тест) — слабее и отпускаем на последних шагах
                  strength=float(p.get("strength", {"pose": 0.8, "raw": 0.75}.get(kind, 0.6))), start_percent=0.0,
                  end_percent=float(p.get("end", 1.0 if kind == "pose" else 0.75))).out
    model = g.add("ModelSamplingAuraFlow", "Сдвиг", model=model, shift=3.0).out
    pos = g.add("CLIPTextEncode", "Промпт", clip=clip.out, text=p["prompt"])
    neg = g.add("ConditioningZeroOut", "Пустой негатив", conditioning=pos.out)
    size = g.add("GetImageSize", "Размер кадра", image=img)
    lat = g.add("EmptySD3LatentImage", "Латент", width=size[0], height=size[1], batch_size=1)
    ks = g.add("KSampler", "Генерация", model=model, positive=pos.out, negative=neg.out, latent_image=lat.out, seed=seed, steps=8, cfg=1.0,
               sampler_name="res_multistep", scheduler="simple", denoise=1.0)
    out = g.add("VAEDecode", "Декодирование", samples=ks.out, vae=vae.out)
    _save(g, out.out, p, "studio/pose")
    return g.to_api()


# ---------------------------------------------------------------- Обучение LoRA персонажа (нативные ноды ComfyUI)
def train_lora(p, mode="quality"):
    """p: folder (подпапка data/input с картинками + .txt подписями), name, steps, rank, lr.
    База — Z-Image Turbo (Klein в ComfyUI пока не обучается: ошибки dtype/autograd внутри модели, тест 2026-11-20)."""
    g = Graph()
    unet, clip, vae = _zimage(g) if p.get("base", "zimage") == "zimage" else _klein_base(g, "quality")
    ds = g.add("LoadImageTextDataSetFromFolder", "Датасет", folder=p["folder"])
    rs = g.add("ResizeImagesByShorterEdge", "Размер 768", images=ds[0], shorter_edge=int(p.get("resolution", 768)))
    td = g.add("MakeTrainingDataset", "Латенты и подписи", images=rs.out, vae=vae.out, clip=clip.out, texts=ds[1])
    steps = int(p.get("steps") or (300 if mode == "draft" else 800))
    tr = g.add("TrainLoraNode", "Обучение", model=unet.out, latents=td[0], positive=td[1], batch_size=1, grad_accumulation_steps=1,
               steps=steps, learning_rate=float(p.get("lr", 0.0002)), rank=int(p.get("rank", 16)), optimizer="AdamW", loss_function="MSE",
               seed=_seed(p) % 2**31, training_dtype=p.get("training_dtype", "bf16"), lora_dtype="bf16", quantized_backward=True, algorithm="LoRA",
               gradient_checkpointing=True, checkpoint_depth=1, offloading=bool(p.get("offloading", True)), existing_lora="[None]", bucket_mode=True, bypass_mode=False)
    g.add("SaveLoRA", "Сохранить LoRA", lora=tr[0], prefix=f"loras/characters/{p['name']}", steps=tr[2])
    return g.to_api()


# ---------------------------------------------------------------- Официальный улучшатель промптов FLUX.3 (Qwen3.5 9B, дообучен BFL)
KLEIN_UPSAMPLER = "qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors"


def klein_upsample(p, mode="quality"):
    """Текст (+картинки для правки) -> промпт для Klein по официальной схеме шаблонов BFL. Результат — в выводе PreviewAny."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2] / "prompt-templates"
    edit = bool(p.get("images"))
    system = (root / ("official_klein_edit.md" if edit else "official_klein.md")).read_text(encoding="utf-8")
    g = Graph()
    clip = g.add("CLIPLoader", "Улучшатель BFL", clip_name=KLEIN_UPSAMPLER, type="flux3", device="default")
    text = (f"TARGET CANVAS: {p['aspect']}\n" if p.get("aspect") and not edit else "") + p["prompt"]
    extra = {}
    if edit:
        imgs = [g.add("LoadImage", f"Картинка {i + 1}", image=n).out for i, n in enumerate(p["images"][:3])]
        batch = g.add("BatchImagesNode", "Картинки", **{f"images.image{i}": im for i, im in enumerate(imgs)})
        extra["image"] = batch.out
    tg = g.add("TextGenerate", "Улучшить промпт", clip=clip.out, prompt=text, max_length=3584, sampling_mode="on",
               **{"sampling_mode.temperature": 1.0, "sampling_mode.top_k": 1, "sampling_mode.top_p": 0.95, "sampling_mode.min_p": 0.0,
                  "sampling_mode.repetition_penalty": 1.05, "sampling_mode.seed": int(p.get("seed") or 0), "sampling_mode.presence_penalty": 1.5},
               thinking=False, use_default_template=True, mtp="off", system_prompt=system, **extra)
    g.add("PreviewAny", "Промпт", source=tg[0])
    return g.to_api()


REGISTRY = {
    "krea2_identity": krea2_identity,
    "klein_upsample": klein_upsample,
    "train_lora": train_lora,
    "zimage_control": zimage_control,
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
