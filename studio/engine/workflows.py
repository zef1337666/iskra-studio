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


REGISTRY = {
    "klein_t2i": klein_t2i,
    "klein_edit": klein_edit,
    "klein_outpaint": klein_outpaint,
}
