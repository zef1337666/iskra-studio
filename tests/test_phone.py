"""Проверка доступа с телефона: обращение по адресу в домашней сети (как с другого устройства)."""
import json, sys, time, urllib.request, urllib.error, urllib.parse, http.cookiejar
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\AI-Studio")
from studio.server import extras  # noqa
ip = extras.lan_ips()[0]
B = f"http://{ip}:7860"
res = []
ok = lambda c, m: print(("✓ " if c else "✗ ") + m) or res.append(bool(c))
for _ in range(30):
    try:
        urllib.request.urlopen("http://127.0.0.1:7860/api/status", timeout=2); break
    except Exception:
        time.sleep(1)
info = json.loads(urllib.request.urlopen("http://127.0.0.1:7860/api/phone/info").read())
ok(info["listening_lan"], f"сервер слушает домашнюю сеть: {info['urls']}")


class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


raw = urllib.request.build_opener(NoRedir)
try:
    raw.open(B + "/")
    ok(False, "без пароля пустило")
except urllib.error.HTTPError as e:
    ok(e.code in (302, 307) and "/login" in e.headers.get("Location", ""), "без входа → страница пароля")
try:
    urllib.request.urlopen(B + "/api/items")
    ok(False, "API без входа доступно")
except urllib.error.HTTPError as e:
    ok(e.code == 401, "API без входа → 401")
try:
    raw.open(B + "/api/login", data=urllib.parse.urlencode({"password": "wrong"}).encode())
except urllib.error.HTTPError as e:
    ok("err=1" in e.headers.get("Location", ""), "неверный пароль отклонён")
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
op.open(B + "/api/login", data=urllib.parse.urlencode({"password": "test-123456"}).encode())
st = json.loads(op.open(B + "/api/status").read())
ok("services" in st, "после входа API доступно")
ok(b"<div id=\"root\">" in op.open(B + "/").read(), "интерфейс открывается")
try:
    op.open(urllib.request.Request(B + "/api/settings", data=b'{"phone_access": false}', method="PUT", headers={"Content-Type": "application/json"}))
    ok(False, "настройки менялись с телефона")
except urllib.error.HTTPError as e:
    ok(e.code == 403, "менять настройки с телефона нельзя (403)")
print(f"\nИтог: {sum(res)}/{len(res)}")
