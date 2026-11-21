import React, { useEffect, useState } from "react";
import { Save, KeyRound, Shield, Bell, Palette, FolderOpen, RotateCcw, Smartphone } from "lucide-react";
import { useStore } from "../store";
import { api } from "../api";
import { Segmented, Tip } from "../components/ui";

const ACCENTS = ["#8b7cff", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#06b6d4"];

function Card({ icon: I, title, children }) {
  return <div className="panel rounded-2xl p-5 space-y-4"><div className="flex items-center gap-2 font-semibold"><I size={17} />{title}</div>{children}</div>;
}
function Row({ label, hint, children }) {
  return <div className="flex items-center gap-4 flex-wrap"><div className="flex-1 min-w-48"><div className="text-sm">{label}</div>{hint && <div className="text-xs dim">{hint}</div>}</div><div>{children}</div></div>;
}

function Telegram({ s, upd, reload }) {
  const toast = useStore((x) => x.toast);
  const [token, setToken] = useState("");
  const [open, setOpen] = useState(false);
  const act = async (fn, ok) => { try { const r = await fn(); toast(typeof ok === "function" ? ok(r) : ok); await reload(); } catch (e) { toast(e.message, "error"); } };
  return (
    <div className="space-y-3">
      <Row label="Telegram" hint={s.telegram_chat_id ? "бот подключён" : "сообщения о готовых задачах в Telegram (только текст, без картинок)"}>
        {s.telegram_chat_id ? <input type="checkbox" checked={s.telegram_enabled} onChange={(e) => upd({ telegram_enabled: e.target.checked })} className="w-5 h-5 accent-[var(--color-accent)]" />
          : <button className="btn-ghost" onClick={() => setOpen(!open)}>Подключить</button>}
      </Row>
      {(open || s.telegram_chat_id) && <div className="rounded-xl p-3 space-y-2 text-sm" style={{ background: "var(--panel-2)" }}>
        {!s.telegram_chat_id && <ol className="list-decimal pl-5 space-y-1 muted text-xs">
          <li>В Telegram откройте <b>@BotFather</b>, отправьте <code>/newbot</code>, придумайте имя — он пришлёт токен.</li>
          <li>Вставьте токен ниже и сохраните.</li><li>Откройте своего нового бота, нажмите «Start».</li><li>Нажмите «Найти мой чат».</li></ol>}
        <div className="flex gap-2 flex-wrap">
          <input type="password" className="field !w-64" placeholder="токен бота 1234567890:AAH…" value={token} onChange={(e) => setToken(e.target.value)} />
          <button className="btn-ghost" disabled={!token} onClick={() => act(() => api.post("/api/telegram/token", { token }), "Токен сохранён в .env").then(() => setToken(""))}>Сохранить</button>
          <button className="btn-ghost" onClick={() => act(() => api.post("/api/telegram/detect"), (r) => `Чат найден: ${r.name || r.chat_id}`)}>Найти мой чат</button>
          {s.telegram_chat_id && <button className="btn-ghost" onClick={() => act(() => api.post("/api/telegram/test"), "Тестовое сообщение отправлено")}>Проверить</button>}
        </div>
      </div>}
    </div>
  );
}

function Phone({ s, upd }) {
  const toast = useStore((x) => x.toast);
  const [info, setInfo] = useState(null);
  const [pw, setPw] = useState("");
  const canvas = React.useRef();
  const load = () => api.get("/api/phone/info").then(setInfo).catch(() => {});
  useEffect(() => { load(); }, [s.phone_access]);
  useEffect(() => {
    if (info?.urls?.[0] && canvas.current) import("qrcode").then((Q) => Q.toCanvas(canvas.current, info.urls[0], { width: 180, margin: 1, color: { dark: "#0b0c11", light: "#ffffff" } }));
  }, [info, s.phone_access]);
  const savePw = async () => { try { await api.post("/api/phone/password", { password: pw }); setPw(""); toast("Пароль для телефона сохранён"); load(); } catch (e) { toast(e.message, "error"); } };
  return (
    <Card icon={Smartphone} title="Доступ с телефона">
      <div className="text-xs muted">Студия откроется на телефоне в браузере, если он в той же домашней Wi-Fi. Можно создавать, смотреть галерею и скачивать. Вход по паролю, безопасный режим на телефоне свой.</div>
      <Row label="Пароль для входа" hint={info?.pass_set ? "задан" : "минимум 6 символов"}>
        <div className="flex gap-2"><input type="password" className="field !w-40" value={pw} onChange={(e) => setPw(e.target.value)} placeholder={info?.pass_set ? "новый пароль" : "пароль"} />
          <button className="btn-ghost" disabled={pw.length < 6} onClick={savePw}>Сохранить</button></div>
      </Row>
      <Row label="Разрешить доступ из домашней сети">
        <input type="checkbox" checked={!!s.phone_access} disabled={!info?.pass_set} onChange={(e) => upd({ phone_access: e.target.checked })} className="w-5 h-5 accent-[var(--color-accent)]" />
      </Row>
      {s.phone_access && info && (info.listening_lan ? <div className="flex gap-4 items-center flex-wrap">
        <canvas ref={canvas} className="rounded-xl" />
        <div className="text-sm space-y-1"><div>Наведите камеру телефона на QR-код или откройте:</div>{info.urls.map((u) => <div key={u} className="font-mono" style={{ color: "var(--color-accent-hi)" }}>{u}</div>)}
          <div className="text-xs dim">Если не открывается — при первом запуске Windows спросит разрешение для Python в сети: нажмите «Разрешить» (частные сети).</div></div>
      </div> : <div className="text-sm p-3 rounded-xl" style={{ background: "rgba(245,184,75,.12)", color: "#f5b84b" }}>Закройте и снова откройте «Искру» — студия начнёт принимать подключения из домашней сети.</div>)}
    </Card>
  );
}

export function applyAccent(c) {
  const r = document.documentElement.style;
  r.setProperty("--color-accent", c);
  r.setProperty("--color-accent-hi", `color-mix(in srgb, ${c} 75%, white)`);
  r.setProperty("--color-accent-lo", `color-mix(in srgb, ${c} 80%, black)`);
}

export default function Settings() {
  const { theme, setTheme, toast, status, safeMode } = useStore();
  const [s, setS] = useState(null);
  const [keys, setKeys] = useState({ HF_TOKEN: "", CIVITAI_API_KEY: "" });
  const [pin, setPin] = useState({ old: "", pin: "" });
  const [accent, setAccent] = useState(() => { try { return localStorage.getItem("iskra_accent") || ACCENTS[0]; } catch { return ACCENTS[0]; } });
  useEffect(() => { api.get("/api/settings").then(setS); }, []);
  const upd = async (patch) => { const r = await api.put("/api/settings", patch); setS(r); useStore.setState({ settings: r }); toast("Сохранено"); };
  const saveKey = async (name) => { await api.post("/api/settings/key", { name, value: keys[name] }); setKeys({ ...keys, [name]: "" }); toast("Ключ сохранён в .env"); };
  const savePin = async (clear) => {
    try { await api.post("/api/pin/set", { pin: clear ? "" : pin.pin, old: pin.old }); setPin({ old: "", pin: "" }); const ns = await api.get("/api/settings"); setS(ns); useStore.setState({ settings: ns }); toast(clear ? "PIN убран" : "PIN установлен"); }
    catch (e) { toast(e.message, "error"); }
  };
  if (!s) return <div className="p-8"><div className="h-64 rounded-2xl skeleton" /></div>;
  return (
    <div className="h-full overflow-y-auto p-5 md:p-8">
      <h1 className="text-2xl font-bold mb-6">Настройки</h1>
      <div className="grid xl:grid-cols-2 gap-4 max-w-6xl">
        <Card icon={Palette} title="Внешний вид">
          <Row label="Тема"><Segmented value={theme} onChange={setTheme} options={[{ value: "dark", label: "Тёмная" }, { value: "light", label: "Светлая" }]} /></Row>
          <Row label="Акцентный цвет"><div className="flex gap-2">{ACCENTS.map((c) => <button key={c} onClick={() => { setAccent(c); applyAccent(c); try { localStorage.setItem("iskra_accent", c); } catch {} }} className="w-7 h-7 rounded-full transition hover:scale-110" style={{ background: c, outline: accent === c ? "2px solid var(--text)" : "none", outlineOffset: 2 }} aria-label={c} />)}</div></Row>
          <Row label="Язык пояснений помощника" hint="«Что я добавил» под промптом"><Segmented value={s.explain_lang} onChange={(v) => upd({ explain_lang: v })} options={[{ value: "ru", label: "Русский" }, { value: "en", label: "English" }]} /></Row>
        </Card>
        <Card icon={Save} title="Генерация и сохранение">
          <Row label="Режим по умолчанию"><Segmented value={s.default_mode} onChange={(v) => { upd({ default_mode: v }); useStore.getState().setDraft({ mode: v }); }} options={[{ value: "draft", label: "Черновик" }, { value: "quality", label: "Качество" }]} /></Row>
          <Row label="Формат картинок" hint="WebP и JPG занимают в 3–5 раз меньше места"><Segmented value={s.save_format} onChange={(v) => upd({ save_format: v })} options={[{ value: "png", label: "PNG" }, { value: "webp", label: "WebP" }, { value: "jpg", label: "JPG" }]} /></Row>
          {s.save_format !== "png" && <Row label={`Качество ${s.jpg_quality}`}><input type="range" min="70" max="100" value={s.jpg_quality} onChange={(e) => setS({ ...s, jpg_quality: Number(e.target.value) })} onMouseUp={() => upd({ jpg_quality: s.jpg_quality })} /></Row>}
          <Row label="Сохранять параметры генерации в файл" hint="Workflow внутри PNG — можно открыть в ComfyUI"><input type="checkbox" checked={s.keep_metadata} onChange={(e) => upd({ keep_metadata: e.target.checked })} className="w-5 h-5 accent-[var(--color-accent)]" /></Row>
          <Row label="Папки" hint="Модели: F:\AI-Studio\models · Результаты: F:\AI-Studio\data\output (18+ — в подпапке nsfw)"><FolderOpen size={16} className="dim" /></Row>
        </Card>
        <Card icon={KeyRound} title="Ключи сервисов">
          {[["HF_TOKEN", "Hugging Face", "hf_…"], ["CIVITAI_API_KEY", "Civitai", "ключ API"]].map(([k, l, ph]) => <Row key={k} label={l} hint={status?.keys?.[k] ? "сохранён ••••••••" : "не задан"}>
            <div className="flex gap-2"><input type="password" className="field !w-56" placeholder={ph} value={keys[k]} onChange={(e) => setKeys({ ...keys, [k]: e.target.value })} />
              <button className="btn-ghost" disabled={!keys[k]} onClick={() => saveKey(k)}>Сохранить</button></div></Row>)}
          <div className="text-xs dim">Ключи хранятся только в файле .env на этом компьютере и никогда не показываются.</div>
        </Card>
        <Card icon={Shield} title="Приватность 18+">
          <Row label="Безопасный режим" hint="Скрывает весь 18+ контент и пресеты (клавиша S)"><input type="checkbox" checked={safeMode} onChange={() => useStore.getState().toggleSafe()} className="w-5 h-5 accent-[var(--color-accent)]" /></Row>
          <Row label={s.pin_set ? "PIN-код установлен" : "PIN-код на раздел 18+"} hint="Спрашивается при выключении безопасного режима">
            <div className="flex gap-2">{s.pin_set && <input type="password" inputMode="numeric" className="field !w-24" placeholder="старый" value={pin.old} onChange={(e) => setPin({ ...pin, old: e.target.value })} />}
              <input type="password" inputMode="numeric" className="field !w-24" placeholder="4–8 цифр" value={pin.pin} onChange={(e) => setPin({ ...pin, pin: e.target.value })} />
              <button className="btn-ghost" disabled={!pin.pin} onClick={() => savePin(false)}>{s.pin_set ? "Сменить" : "Задать"}</button>
              {s.pin_set && <button className="btn-ghost" onClick={() => savePin(true)}>Убрать</button>}</div></Row>
        </Card>
        <Card icon={Bell} title="Уведомления">
          <Row label="Уведомление Windows" hint="Когда очередь опустела или долгая задача готова"><input type="checkbox" checked={s.notify_windows} onChange={(e) => upd({ notify_windows: e.target.checked })} className="w-5 h-5 accent-[var(--color-accent)]" /></Row>
          <Telegram s={s} upd={upd} reload={async () => { const ns = await api.get("/api/settings"); setS(ns); }} />
        </Card>
        <Phone s={s} upd={upd} />
        <div className="xl:col-span-2"><button className="btn-ghost" onClick={async () => { if (confirm("Сбросить настройки к стандартным? PIN и ключи сохранятся.")) { setS(await api.post("/api/settings/reset")); toast("Настройки сброшены"); } }}><RotateCcw size={15} />Сбросить настройки</button></div>
      </div>
    </div>
  );
}
