import React, { useEffect, useState } from "react";
import { HardDrive, Star, Search, Download, Trash2, RefreshCw, Link2, Pause, Play, X, Loader2, Sparkles, Eye } from "lucide-react";
import { useStore } from "../store";
import { api } from "../api";
import { Segmented, Tip, Empty } from "../components/ui";

const COMPAT = { fits: ["Помещается в VRAM", "#3ecf8e"], offload: ["С выгрузкой в ОЗУ", "#f5b84b"], edge: ["На пределе", "#ff6b6b"] };
const FOLDER_RU = { diffusion_models: "Основные модели", checkpoints: "Чекпоинты", loras: "LoRA", vae: "VAE", text_encoders: "Текстовые энкодеры", upscale_models: "Апскейлеры",
  model_patches: "ControlNet", mmaudio: "Звук", clip_vision: "Зрение", "llm (Ollama)": "Помощники (LLM)", geometry_estimation: "3D: глубина", background_removal: "Удаление фона",
  ultralytics: "Детекторы", frame_interpolation: "Плавность" };
const COLORS = ["#8b7cff", "#3ecf8e", "#f5b84b", "#ff5fa2", "#38bdf8", "#f97316", "#a3e635", "#e879f9", "#94a3b8", "#14b8a6"];

function Preview({ urls, nsfw, flags }) {
  const safeMode = useStore((s) => s.safeMode);
  const [show, setShow] = useState(false);
  const url = urls?.[0];
  const blur = (nsfw || flags?.[0]) && !show;
  if (!url) return <div className="aspect-[4/3] flex items-center justify-center" style={{ background: "var(--panel-2)" }}><HardDrive size={28} className="dim" /></div>;
  return (
    <div className="aspect-[4/3] relative overflow-hidden" style={{ background: "var(--panel-2)" }} onClick={() => !safeMode && setShow(true)}>
      {/\.(mp4|webm)$/i.test(url) ? <video src={url} muted loop autoPlay playsInline className={`w-full h-full object-cover ${blur ? "nsfw-blur" : ""}`} />
        : <img src={url} referrerPolicy="no-referrer" loading="lazy" className={`w-full h-full object-cover ${blur ? "nsfw-blur" : ""}`} alt="" />}
      {blur && <div className="absolute inset-0 flex items-center justify-center text-white text-xs gap-1.5 bg-black/20"><Eye size={14} />{safeMode ? "18+ скрыто" : "18+ — нажмите, чтобы показать"}</div>}
    </div>
  );
}

function Downloads() {
  const [list, setList] = useState([]);
  useEffect(() => { const f = () => api.get("/api/models/downloads").then(setList).catch(() => {}); f(); const t = setInterval(f, 1500); return () => clearInterval(t); }, []);
  const active = list.filter((d) => d.state !== "done" || Date.now());
  if (!active.length) return null;
  const st = { queued: "в очереди", running: "качается", paused: "пауза", verifying: "проверка файла", done: "готово", error: "ошибка", cancelled: "отменено" };
  return (
    <div className="panel rounded-2xl p-4 mb-5 space-y-3">
      <div className="label">Загрузки</div>
      {active.map((d) => <div key={d.id}>
        <div className="flex items-center gap-2 text-sm"><span className="flex-1 truncate">{d.name || d.file}</span>
          <span className="text-xs muted">{st[d.state]}{d.state === "running" ? ` · ${d.speed_mb} МБ/с` : ""}</span>
          {d.state === "running" && <button className="btn-ghost !h-7 !px-2" onClick={() => api.post(`/api/models/downloads/${d.id}/pause`)}><Pause size={13} /></button>}
          {d.state === "paused" && <button className="btn-ghost !h-7 !px-2" onClick={() => api.post(`/api/models/downloads/${d.id}/resume`)}><Play size={13} /></button>}
          {["running", "paused", "queued"].includes(d.state) && <button className="btn-ghost !h-7 !px-2" onClick={() => api.post(`/api/models/downloads/${d.id}/cancel`)}><X size={13} /></button>}
        </div>
        <div className="h-1.5 rounded-full mt-1.5 overflow-hidden" style={{ background: "var(--panel-2)" }}><div className="h-full rounded-full" style={{ width: `${d.percent || 0}%`, background: d.state === "error" ? "#ff6b6b" : "var(--color-accent)" }} /></div>
        {d.error && <div className="text-xs mt-1" style={{ color: d.state === "error" ? "#ff6b6b" : "var(--dim)" }}>{d.error}</div>}
      </div>)}
    </div>
  );
}

function Installed() {
  const { toast, loadPresets, safeMode } = useStore();
  const [data, setData] = useState(null);
  const [upd, setUpd] = useState(null);
  const [filter, setFilter] = useState("");
  const load = () => api.get("/api/models/installed").then(setData).catch((e) => toast(e.message, "error"));
  useEffect(() => { load(); }, []);
  if (!data) return <div className="grid gap-2">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-14 rounded-xl skeleton" />)}</div>;
  const total = Object.values(data.space).reduce((a, b) => a + b, 0);
  const items = data.items.filter((m) => !(safeMode && m.nsfw) && (!filter || (m.name + m.file).toLowerCase().includes(filter.toLowerCase())));
  const del = async (m) => { if (!confirm(`Удалить «${m.name}» (${m.size_gb} ГБ)? Файл уйдёт в корзину data/trash/models — его можно вернуть.`)) return; try { await api.del(`/api/models/file/${m.file}`); toast("Модель перемещена в корзину"); load(); } catch (e) { toast(e.message, "error"); } };
  const mkPreset = async (m) => { try { const p = await api.post("/api/models/preset-from", { model: m }); await loadPresets(); toast(`Создан пресет «${p.name}» в группе «Мои»`); } catch (e) { toast(e.message, "error"); } };
  return (
    <div className="space-y-5">
      <div className="panel rounded-2xl p-5">
        <div className="flex items-baseline justify-between mb-3"><div className="font-semibold">Занято моделями: {total.toFixed(0)} ГБ</div>
          <Tip text="Проверить новые версии моделей, скачанных с Civitai"><button className="btn-ghost !h-8" onClick={async () => { setUpd("…"); setUpd(await api.get("/api/models/updates")); }}><RefreshCw size={14} />Проверить обновления</button></Tip></div>
        <div className="flex h-4 rounded-full overflow-hidden">{Object.entries(data.space).map(([k, v], i) => <div key={k} title={`${FOLDER_RU[k] || k}: ${v} ГБ`} className="h-full transition-all" style={{ width: `${(v / total) * 100}%`, minWidth: 3, background: COLORS[i % COLORS.length] }} />)}</div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs muted">{Object.entries(data.space).map(([k, v], i) => <span key={k} className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS[i % COLORS.length] }} />{FOLDER_RU[k] || k} · {v} ГБ</span>)}</div>
        {Array.isArray(upd) && <div className="mt-3 text-sm">{upd.length ? upd.map((u) => <div key={u.file}>Новая версия «{u.name}»: {u.new_version} — <a href={u.url} target="_blank" className="underline" style={{ color: "var(--color-accent-hi)" }}>открыть</a></div>) : "Все модели с Civitai — последних версий."}</div>}
        {upd === "…" && <div className="mt-3 text-sm muted flex items-center gap-2"><Loader2 size={14} className="animate-spin" />Проверяю…</div>}
      </div>
      <input className="field max-w-sm" placeholder="Фильтр по названию" value={filter} onChange={(e) => setFilter(e.target.value)} />
      <div className="panel rounded-2xl divide-y" style={{ borderColor: "var(--line)" }}>
        {items.map((m) => <div key={m.file} className="flex items-center gap-3 px-4 py-3" style={{ borderColor: "var(--line)" }}>
          <div className="min-w-0 flex-1"><div className="text-sm font-medium truncate flex items-center gap-2">{m.name}{m.nsfw && <span className="text-[10px] px-1.5 rounded bg-[var(--color-pink)] text-white">18+</span>}</div>
            <div className="text-xs dim truncate">{FOLDER_RU[m.folder.split("/")[0]] || m.folder} · {m.size_gb} ГБ · установлена {m.installed}{m.last_used ? ` · использовалась ${m.last_used}` : " · ещё не использовалась"}</div></div>
          {(m.folder === "loras" || m.folder === "checkpoints") && <Tip text="Создать пресет из рекомендованных настроек автора"><button className="btn-ghost !h-8 !px-2.5" onClick={() => mkPreset(m)}><Sparkles size={14} /></button></Tip>}
          {m.url && <Tip text="Страница модели"><a className="btn-ghost !h-8 !px-2.5" href={m.url} target="_blank"><Link2 size={14} /></a></Tip>}
          <Tip text="Удалить (в корзину)"><button className="btn-ghost !h-8 !px-2.5" onClick={() => del(m)}><Trash2 size={14} /></button></Tip>
        </div>)}
      </div>
    </div>
  );
}

function Card({ c, onInstall, busy }) {
  const cp = COMPAT[c.compat] || COMPAT.offload;
  return (
    <div className="panel rounded-2xl overflow-hidden flex flex-col animate-fade-in">
      <Preview urls={c.previews} nsfw={c.nsfw} flags={c.previews_nsfw} />
      <div className="p-3 flex-1 flex flex-col gap-1.5">
        <div className="font-semibold text-sm leading-tight line-clamp-2">{c.name}</div>
        <div className="text-xs muted truncate">{c.version} · {c.base_model} · {c.kind}</div>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          <span className="px-1.5 rounded" style={{ background: "var(--panel-2)", color: cp[1] }}>{cp[0]}</span>
          {c.nsfw && <span className="px-1.5 rounded bg-[var(--color-pink)] text-white">18+</span>}
        </div>
        <div className="text-[11px] dim">⬇ {(c.downloads || 0).toLocaleString("ru")} · 👍 {(c.likes || 0).toLocaleString("ru")} · {c.size_gb} ГБ</div>
        <div className="text-[11px] dim">{c.license}</div>
        <div className="flex-1" />
        <div className="flex gap-2 mt-1">
          <button className="btn-primary flex-1 !h-8 !text-xs" onClick={() => onInstall(c)} disabled={busy || !c.file}>{busy ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}Установить</button>
          <a className="btn-ghost !h-8 !px-2.5" href={c.url} target="_blank" aria-label="Страница"><Link2 size={13} /></a>
        </div>
      </div>
    </div>
  );
}

function Catalog() {
  const { toast, safeMode } = useStore();
  const [q, setQ] = useState(""); const [kind, setKind] = useState(""); const [base, setBase] = useState(""); const [fits, setFits] = useState(false);
  const [res, setRes] = useState(null); const [loading, setLoading] = useState(false); const [link, setLink] = useState(""); const [busy, setBusy] = useState(null);
  const search = async () => {
    setLoading(true);
    try { setRes(await api.get(`/api/models/search?${new URLSearchParams({ q, kind, base, nsfw: safeMode ? 0 : 1 })}`)); } catch (e) { toast(e.message, "error"); }
    setLoading(false);
  };
  useEffect(() => { search(); }, [kind, base, safeMode]);
  const install = async (c) => {
    setBusy(c.version_id);
    try { await api.post("/api/models/install", { card: c }); toast(`«${c.name}» добавлена в загрузки. После установки можно создать пресет в «Установленных».`); } catch (e) { toast(e.message, "error"); }
    setBusy(null);
  };
  const byLink = async () => {
    try {
      const r = await api.post("/api/models/resolve", { link });
      if (r.card) await install(r.card);
      else if (r.file) { await api.post("/api/models/install", { file: r.file, repo: r.repo }); toast("Файл добавлен в загрузки"); }
      else if (r.files) toast(`В репозитории ${r.files.length} файлов — вставьте ссылку на конкретный файл`, "info");
      setLink("");
    } catch (e) { toast(e.message, "error"); }
  };
  const items = (res?.items || []).filter((c) => !(safeMode && c.nsfw) && (!fits || c.compat === "fits"));
  return (
    <div className="space-y-4">
      <div className="flex gap-2"><input className="field" placeholder="Вставьте ссылку Civitai / Hugging Face или номер версии" value={link} onChange={(e) => setLink(e.target.value)} onKeyDown={(e) => e.key === "Enter" && byLink()} />
        <button className="btn-ghost" onClick={byLink} disabled={!link}><Link2 size={15} />Установить по ссылке</button></div>
      <div className="flex gap-2 flex-wrap items-center">
        <div className="relative flex-1 min-w-52"><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 dim" /><input className="field !pl-9" placeholder="Поиск на Civitai" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} /></div>
        <select className="field !w-auto" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">Все типы</option><option value="checkpoint">Модели</option><option value="lora">LoRA</option><option value="vae">VAE</option><option value="upscaler">Апскейлеры</option><option value="controlnet">ControlNet</option></select>
        <select className="field !w-auto" value={base} onChange={(e) => setBase(e.target.value)}><option value="">Любая база</option>{["Krea 2", "Flux.3", "Illustrious", "Anima", "Z-Image", "Wan Video 2.2 I2V-A14B", "SDXL 1.0", "Qwen"].map((b) => <option key={b}>{b}</option>)}</select>
        <label className="chip"><input type="checkbox" checked={fits} onChange={(e) => setFits(e.target.checked)} className="accent-[var(--color-accent)]" />Помещается в мою видеокарту</label>
        <button className="btn-primary" onClick={search}>{loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}Найти</button>
      </div>
      {loading && !res ? <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">{Array.from({ length: 10 }).map((_, i) => <div key={i} className="h-72 rounded-2xl skeleton" />)}</div>
        : items.length ? <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">{items.map((c) => <Card key={c.version_id} c={c} onInstall={install} busy={busy === c.version_id} />)}</div>
        : <Empty icon={Search} title="Ничего не нашлось" text="Попробуйте другой запрос или уберите фильтры." />}
    </div>
  );
}

function Recommended() {
  const { safeMode } = useStore();
  const [cats, setCats] = useState(null);
  useEffect(() => { api.get("/api/models/recommended").then(setCats); }, []);
  if (!cats) return <div className="h-40 rounded-2xl skeleton" />;
  return (
    <div className="space-y-6">
      <div className="text-sm muted">Подборка, собранная при настройке студии (ноябрь 2026). Установленное отмечено. Полная страница выбора: <code>model-picker/index.html</code>.</div>
      {cats.filter((c) => !(safeMode && c.nsfw)).map((c) => <div key={c.id}>
        <div className="font-semibold mb-1">{c.tab}</div><div className="text-xs muted mb-3 max-w-3xl">{c.note}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">{c.items.map((i) => (
          <div key={i.id} className="panel rounded-2xl overflow-hidden" style={i.recommended ? { borderColor: "var(--color-accent)" } : {}}>
            <Preview urls={i.previews} nsfw={c.nsfw} />
            <div className="p-3"><div className="text-sm font-semibold leading-tight">{i.name}</div><div className="text-[11px] dim mt-1">{i.variant}</div>
              <div className="text-[11px] mt-1.5" style={{ color: (COMPAT[i.compat] || COMPAT.offload)[1] }}>{(COMPAT[i.compat] || COMPAT.offload)[0]} · {i.total_gb} ГБ · {i.quality}/10</div>
              {i.recommended && <div className="text-[11px] mt-1.5" style={{ color: "var(--color-accent-hi)" }}>★ Рекомендация</div>}</div>
          </div>))}</div>
      </div>)}
    </div>
  );
}

export default function Models() {
  const [tab, setTab] = useState("installed");
  return (
    <div className="h-full overflow-y-auto p-5 md:p-8">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5"><h1 className="text-2xl font-bold">Модели</h1>
        <div className="w-full sm:w-auto sm:min-w-[420px]"><Segmented value={tab} onChange={setTab} options={[{ value: "installed", label: "Установленные", icon: <HardDrive size={14} /> }, { value: "rec", label: "Рекомендовано", icon: <Star size={14} /> }, { value: "catalog", label: "Каталог", icon: <Search size={14} /> }]} /></div></div>
      <Downloads />
      {tab === "installed" && <Installed />}{tab === "rec" && <Recommended />}{tab === "catalog" && <Catalog />}
    </div>
  );
}
