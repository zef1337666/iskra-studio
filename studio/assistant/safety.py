"""Жёсткие ограничения 18+ (встроены в код, не зависят от модели-помощника).

- Ничего, связанного с несовершеннолетними: запрос блокируется до генерации.
- В 18+ промптах всегда явно указан взрослый возраст.
- Негатив 18+ всегда содержит теги против детского облика.
"""
import re

MINOR_PATTERNS = [
    r"\bloli\w*", r"\bshota\w*", r"\bchild\w*", r"\bkids?\b", r"\bteen\w*", r"\bunderage\b", r"\bminor\b", r"\bpreteen\b",
    r"\bschool ?girl\w*", r"\bschool ?boy\w*", r"\byoung girl\b", r"\blittle girl\b", r"\blittle boy\b", r"\bbaby\b", r"\btoddler\b",
    r"\b(1[0-7]|[1-9])[ -]?(years?[ -]old|yo|y/o)\b", r"\byoung[- ]looking\b", r"\bchildlike\b", r"\bjailbait\b", r"\bbarely legal\b",
    r"\bjunior high\b", r"\bmiddle school\b", r"\belementary\b", r"\bpetite child\b",
    r"\bмолоденьк\w*", r"\bюнн?ая на вид\b", r"\bвыглядит как реб\w*",
    r"ребён\w*", r"ребен\w*", r"\bдет(и|ей|ск\w*)", r"девочк\w*", r"мальчик\w*", r"школьни\w*", r"подрост\w*", r"несовершеннолет\w*",
    r"малолет\w*", r"\b(1[0-7]|[1-9])\s*(лет|года|год)\b", r"лоли\w*", r"тинейдж\w*", r"\bюн(ая|ый|ую|ой)\b",
]
_minor_re = re.compile("|".join(MINOR_PATTERNS), re.IGNORECASE)

# Явный возраст: число 21+ лет или «adult/mature». Слова woman/man сами по себе возрастом не считаются.
ADULT_RE = re.compile(r"\b(adult|mature)\b|\b(2[1-9]|[3-9]\d)[ -]?(years?[ -]old|yo)\b|\bin (her|his|their) (20|30|40|50|60)s\b", re.I)

NSFW_NEGATIVE = "child, minor, teen, underage, young-looking, childlike body, loli, shota, school uniform, flat chest child, baby face"

REFUSAL_RU = ("Этот запрос нельзя выполнить: в разделе 18+ разрешены только вымышленные взрослые персонажи. "
              "Ничего, что связано с несовершеннолетними, студия не генерирует.")


# Откровенный запрос в обычном (не 18+) пресете: в обычных пресетах нет проверки возраста на картинке и фильтра про несовершеннолетних,
# поэтому такие запросы отправляем в раздел 18+, где эти проверки работают
EXPLICIT_RE = re.compile(
    r"\b(naked|nude|nudes|nudity|topless|bottomless|undress\w*|unclothed|striptease|stripping|nsfw|porn\w*|sex|sexual|erotic\w*|nipples?|"
    r"genitals?|pussy|vagina|penis|cock|boobs?|tits|bare breasts?|no clothes|without clothes)\b|"
    r"\b(гол(ая|ой|ую|ые|ый|ого|ышом)|обнаж\w*|раздень\w*|разде(ть|вай|тая|тую|тые|тый)\w*|без одежды|порн\w*|секс\w*|эрот\w*|"
    r"сосок|соски|сиськ\w*|вагин\w*|наг(ая|ой|ую|ие|ишом)|топлес)\b", re.I)

EXPLICIT_RU = ("Откровенный контент делается только в разделе 18+: там работают проверки возраста. "
               "Выберите пресет из группы «18+» (или режим «Авто» при открытом разделе 18+).")


def is_explicit(text: str):
    return bool(text and EXPLICIT_RE.search(text))


def check_request(text: str, nsfw: bool):
    """Возвращает текст отказа или None. Для 18+ — строгая проверка, для обычных пресетов проверку делает модель."""
    if nsfw and text and _minor_re.search(text):
        return REFUSAL_RU
    return None


ADULT_NOUN_RE = re.compile(r"\b(woman|women|man|men|lady|ladies|guy|wife|husband|girlfriend|boyfriend|milf|1woman|1man)\b|\b(1[89]|[2-9]\d)[ -]?(years?[ -]old|yo)\b|\bin (her|his|their) (20|30|40|50)s\b|\badult\b", re.I)


def enforce_adult(prompt: str, negative: str, anime: bool = False):
    """18+: не пропускаем несовершеннолетних. Ничего лишнего не дописываем — приписки «mature»/«25+» портили результат
    (старили лица), поэтому только одно слово «adult», и только если в промпте нет ни взрослого существительного, ни возраста."""
    if _minor_re.search(prompt or ""):
        return None, None  # модель-помощник выдала недопустимое — не используем
    if not ADULT_NOUN_RE.search(prompt or ""):
        prompt = "adult, " + (prompt or "")
    neg = (negative + ", " if negative else "") + NSFW_NEGATIVE if anime else negative  # негатив нужен только моделям с CFG>1
    return prompt, neg
