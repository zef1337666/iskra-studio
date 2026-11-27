"""Проверка загруженных картинок для 18+: метка «создано ИИ» в файле и оценка возраста.

Метки ищем в сырых байтах файла: C2PA / Content Credentials, IPTC DigitalSourceType «trainedAlgorithmicMedia»,
подписи генераторов в EXIF/XMP/PNG-тексте. Метку можно удалить, поэтому без неё нужна явная галочка пользователя.
"""
import json, re, pathlib
from ..config import DATA

# Только «сильные» признаки ИИ: голый C2PA есть и у снимков с камеры (Pixel и др.), поэтому сам по себе не считается.
MARKERS = [
    (rb"trainedAlgorithmicMedia|compositeSynthetic|algorithmicMedia", "метка IPTC «создано ИИ»"),
    (rb"Made with Google AI|Google AI|SynthID|Imagen|Gemini", "Google AI"),
    (rb"OpenAI|DALL[-\xb7 ]?E|ChatGPT|gpt-image", "OpenAI"),
    (rb"Midjourney", "Midjourney"),
    (rb"Adobe Firefly|Firefly", "Adobe Firefly"),
    (rb"\"class_type\"|ComfyUI", "ComfyUI"),
    (rb"Stable Diffusion|Steps: \d+, Sampler", "Stable Diffusion"),
    (rb"Leonardo\.Ai|Ideogram|FLUX|Black Forest Labs|Krea", "ИИ-генератор"),
    (rb"Grok|xAI|Meta AI|Imagined with AI|Microsoft Designer|Bing Image Creator|Image Creator from Microsoft", "ИИ-генератор"),
    (rb"NovelAI|invokeai|Fooocus|sui_image_params|Civitai|SeaArt|Tensor\.Art|NightCafe|Playground AI", "ИИ-генератор"),
    (rb"Seedream|Dreamina|Jimeng|Doubao|Kling AI|Hailuo|Recraft|Tongyi|Wanxiang|Hunyuan|Qwen-Image", "ИИ-генератор"),
]
# Любые метаданные (EXIF, XMP, IPTC, C2PA, PNG-текст). Их отсутствие — признак пересылки через мессенджер/скриншота.
META = rb"Exif\x00\x00|http://ns\.adobe\.com/xap|jumb|c2pa|Photoshop 3\.0|tEXt|iTXt|zTXt|eXIf"
REG = DATA / "uploads.json"


def detect(path):
    data = pathlib.Path(path).read_bytes()[:4 * 2**20]  # метаданные лежат в начале/конце; 4 МБ хватает почти всегда
    tail = pathlib.Path(path).read_bytes()[-2**20:]
    for pat, label in MARKERS:
        if re.search(pat, data, re.I) or re.search(pat, tail, re.I):
            return label
    return None


def bare(path):
    """True — в файле нет никаких метаданных (метку «создано ИИ» стёрли при пересылке/скриншоте)."""
    b = pathlib.Path(path).read_bytes()
    return not (re.search(META, b[:4 * 2**20]) or re.search(META, b[-2**20:]))


def _reg():
    try:
        return json.loads(REG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def remember(name, info):
    r = _reg()
    r[name] = info
    REG.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")


def info(name):
    return _reg().get(name, {})


# Диапазон надёжнее одного числа: вопрос «самый молодой — одно число» давал JoyCaption заниженные 18 для женщины ~30 лет.
AGE_PROMPT = ("Estimate the apparent age range in years of the youngest-looking person in this image. "
              "Answer only like '25-30'. If there are no people, answer '0-0'.")


def youngest_age(path):
    """Оценка возраста самого молодого на вид человека (описатель без цензуры). None — если не удалось."""
    from . import vision
    import base64, urllib.request
    from ..config import OLLAMA_URL
    img = base64.b64encode(pathlib.Path(path).read_bytes()).decode()
    ages = []
    for model in (vision.MODEL_UNCENSORED, vision.MODEL_DEFAULT):
        try:
            payload = {"model": model, "stream": False, "keep_alive": 0, "think": False, "options": {"temperature": 0},
                       "messages": [{"role": "user", "content": AGE_PROMPT, "images": [img]}]}
            r = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            txt = json.loads(urllib.request.urlopen(r, timeout=180).read())["message"]["content"]
            m = re.search(r"\d{1,3}", txt)
            if m:
                ages.append(int(m.group(0)))
        except Exception:
            continue
    return min(ages) if ages else None  # берём самую осторожную оценку из двух моделей
