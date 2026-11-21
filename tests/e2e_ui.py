"""E2E-тест интерфейса (Playwright + системный Edge): создать картинку → она в галерее → апскейл работает.
Плюс скриншоты на 1920×1080, 2560×1440 и телефоне в data/screens/. Нужна запущенная студия (127.0.0.1:7860)."""
import json, sys, time, pathlib, urllib.request
from playwright.sync_api import sync_playwright, expect
sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:7860"
SHOTS = pathlib.Path(__file__).resolve().parents[1] / "data" / "screens"
SHOTS.mkdir(parents=True, exist_ok=True)
api = lambda p: json.loads(urllib.request.urlopen(B + p).read())
res = []
ok = lambda c, m: print(("✓ " if c else "✗ ") + m) or res.append(bool(c))


def wait_idle(timeout=240):
    t = time.time()
    while time.time() - t < timeout:
        if not api("/api/queue"):
            return True
        time.sleep(1.5)
    return False


with sync_playwright() as pw:
    br = pw.chromium.launch(channel="msedge", headless=True)
    ctx = br.new_context(viewport={"width": 1920, "height": 1080})
    ctx.add_init_script("localStorage.setItem('iskra_page', '\"create\"')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(B)
    if page.get_by_role("button", name="Пропустить").count():
        page.get_by_role("button", name="Пропустить").click()
    before = api("/api/items?limit=1")[0]["id"]
    # 1. создать картинку
    box = page.get_by_placeholder("Опишите, что хотите", exact=False)
    box.fill("маленький зелёный кактус в глиняном горшке на белом фоне")
    page.locator("button", has_text="Черновик").first.click()
    page.keyboard.press("Control+Enter")
    expect(page.get_by_role("button", name="Отменить").first).to_be_visible(timeout=60000)
    ok(True, "карточка задачи с прогрессом появилась в ленте")
    page.screenshot(path=str(SHOTS / "create_progress_1920.png"))
    ok(wait_idle(), "генерация завершилась")
    time.sleep(2)
    new = api("/api/items?limit=1")[0]
    ok(new["id"] > before and new["preset"] == "photo-real", f"результат #{new['id']} сохранён ({new['job_sec']} с)")
    page.screenshot(path=str(SHOTS / "create_result_1920.png"))
    # 2. галерея
    page.locator("aside").get_by_role("button", name="Галерея").click()
    tile = page.locator("main img").first
    expect(tile).to_be_visible(timeout=10000)
    ok(True, "результат виден в галерее")
    page.screenshot(path=str(SHOTS / "gallery_1920.png"))
    # 3. апскейл из просмотра
    tile.click()
    page.get_by_role("button", name="Апскейл", exact=True).click()
    time.sleep(2)
    ok(wait_idle(300), "апскейл завершился")
    up = api("/api/items?limit=1")[0]
    ok(up["preset"] == "upscale" and up["parent_id"] == new["id"] and up["width"] >= new["width"] * 2, f"апскейл: {new['width']}→{up['width']} px")
    page.keyboard.press("Escape")
    # 4. скриншоты разделов в разных разрешениях
    for w, h, tag in ((1920, 1080, "1920"), (2560, 1440, "2560")):
        page.set_viewport_size({"width": w, "height": h})
        for name, slug in (("Создать", "create"), ("Галерея", "gallery"), ("Модели", "models"), ("Система", "system"), ("Настройки", "settings")):
            page.locator("aside").get_by_role("button", name=name).click()
            time.sleep(1.2)
            page.screenshot(path=str(SHOTS / f"{slug}_{tag}.png"))
    mob = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    mob.add_init_script("localStorage.setItem('iskra_page', '\"create\"')")
    mp = mob.new_page()
    mp.goto(B); time.sleep(2)
    if mp.get_by_role("button", name="Пропустить").count():
        mp.get_by_role("button", name="Пропустить").click()
    mp.screenshot(path=str(SHOTS / "create_mobile.png"), full_page=True)
    mp.locator("aside").get_by_role("button", name="Галерея").click(); time.sleep(1.5)
    mp.screenshot(path=str(SHOTS / "gallery_mobile.png"))
    overflow = mp.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
    ok(not overflow, "телефон: нет горизонтальной прокрутки")
    ok(not errors, f"ошибок JavaScript: {len(errors)} {errors[:2]}")
    br.close()
print(f"\nИтог e2e: {sum(res)}/{len(res)} · скриншоты: {SHOTS}")
