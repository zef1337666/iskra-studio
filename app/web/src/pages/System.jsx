import React, { useEffect, useRef, useState } from "react";
import { Cpu, Thermometer, MemoryStick, Zap, RotateCw, Eraser, Copy, ListOrdered, ChevronUp, ChevronDown, X, Pause, Play, Moon } from "lucide-react";
import { useStore } from "../store";
import { api } from "../api";
import { Tip, fmtSec } from "../components/ui";

function Spark({ data, color, max }) {
  const w = 220, h = 48;
  const pts = data.map((v, i) => `${(i / Math.max(1, data.length - 1)) * w},${h - (v / max) * h}`).join(" ");
  return <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="h-12"><polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" /></svg>;
}

function Stat({ icon: I, label, value, sub, data, color, max }) {
  return (
    <div className="panel rounded-2xl p-4">
      <div className="flex items-center gap-2 text-xs muted mb-1"><I size={14} />{label}</div>
      <div className="text-2xl font-semibold">{value}<span className="text-sm muted font-normal ml-1">{sub}</span></div>
      {data && <Spark data={data} color={color} max={max} />}
    </div>
  );
}

export function QueuePanel() {
  const { queue, jobs, toast } = useStore();
  const [paused, setPaused] = useState(false);
  const [settings, setSettings] = useState(null);
  useEffect(() => { api.get("/api/settings").then(setSettings); }, []);
  const night = async () => { const s = await api.put("/api/settings", { night_mode: !settings.night_mode }); setSettings(s); toast(s.night_mode ? "Ночной режим: студия пришлёт уведомление, когда очередь опустеет" : "Ночной режим выключен", "info"); };
  const list = queue.map((q) => jobs[q.id] || q);
  return (
    <div className="panel rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4 flex-wrap"><ListOrdered size={18} /><span className="font-semibold flex-1">Очередь · {list.length}</span>
        {settings && <Tip text="Накидайте задач и уходите — по окончании придёт уведомление Windows"><button className={`btn-ghost ${settings.night_mode ? "!text-white !bg-[var(--color-accent)]" : ""}`} onClick={night}><Moon size={15} />Ночной режим</button></Tip>}
        <button className="btn-ghost" onClick={async () => { const r = await api.post(`/api/queue/pause/${paused ? 0 : 1}`); setPaused(r.paused); }}>{paused ? <><Play size={15} />Продолжить</> : <><Pause size={15} />Пауза</>}</button>
      </div>
      {!list.length ? <div className="text-sm muted">Очередь пуста. Задачи из «Создать» появятся здесь.</div> :
        <div className="space-y-2">{list.map((j, i) => (
          <div key={j.id} className="flex items-center gap-3 p-2.5 rounded-xl" style={{ background: "var(--panel-2)" }}>
            <span className="w-6 text-center text-xs dim">{i + 1}</span>
            <div className="flex-1 min-w-0"><div className="text-sm truncate">{j.title || "Без названия"}</div>
              <div className="text-xs dim">{j.preset_name} · {j.mode === "draft" ? "черновик" : "качество"} · {j.state === "running" ? `идёт ${Math.round((j.progress || 0) * 100)}%${j.eta != null ? `, ≈${fmtSec(j.eta)}` : ""}` : `ожидает (~${fmtSec(j.eta)})`}</div></div>
            {j.state === "queued" && <><button className="btn-ghost !h-7 !px-2" onClick={() => api.post(`/api/jobs/${j.id}/move/-1`)} aria-label="Выше"><ChevronUp size={14} /></button>
              <button className="btn-ghost !h-7 !px-2" onClick={() => api.post(`/api/jobs/${j.id}/move/1`)} aria-label="Ниже"><ChevronDown size={14} /></button></>}
            <Tip text="Удалить из очереди"><button className="btn-ghost !h-7 !px-2" onClick={() => api.post(`/api/jobs/${j.id}/cancel`)}><X size={14} /></button></Tip>
          </div>))}</div>}
    </div>
  );
}

export default function System() {
  const { status, toast } = useStore();
  const hist = useRef({ gpu: [], vram: [], ram: [], temp: [] });
  const [, force] = useState(0);
  const [logName, setLogName] = useState("comfy");
  const [logs, setLogs] = useState([]);
  const [bench, setBench] = useState([]);
  useEffect(() => {
    if (!status?.gpu) return;
    const h = hist.current, g = status.gpu;
    const push = (k, v) => { h[k] = [...h[k], v].slice(-60); };
    push("gpu", g.util); push("vram", g.vram_used / 1024); push("temp", g.temp); push("ram", status.ram.used); force((x) => x + 1);
  }, [status]);
  useEffect(() => { api.get(`/api/system/logs/${logName}`).then(setLogs).catch(() => {}); }, [logName, status?.stats?.n]);
  useEffect(() => { api.get("/api/system/bench").then(setBench); }, []);
  const g = status?.gpu, h = hist.current;
  const report = async () => { const r = await api.get("/api/system/report"); await navigator.clipboard.writeText(r.text); toast("Отчёт скопирован — вставьте его в чат с Claude"); };
  const ru = { running: "работает", starting: "запускается…", crashed: "упал, перезапускаю", stopped: "остановлен" };
  const wfRu = { klein_t2i: "Фото (Klein)", klein_edit: "Правка / персонаж", klein_outpaint: "Расширить кадр", detailer: "Детейлер", anima_t2i: "Аниме", krea2_t2i: "Стиль / 18+ Krea 2", sdxl_t2i: "SDXL", upscale: "Апскейл", remove_bg: "Удаление фона", wan22_video: "Видео Wan", h3_video: "Видео H3", video_enhance: "Улучшение видео", video_audio: "Звук", image_to_3d: "3D", zimage_control: "Поза" };
  return (
    <div className="h-full overflow-y-auto p-5 md:p-8 space-y-6">
      <h1 className="text-2xl font-bold">Система</h1>
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <Stat icon={Zap} label="Загрузка видеокарты" value={g ? g.util : "—"} sub="%" data={h.gpu} color="#8b7cff" max={100} />
        <Stat icon={Cpu} label="Видеопамять" value={g ? (g.vram_used / 1024).toFixed(1) : "—"} sub={g ? `из ${(g.vram_total / 1024).toFixed(0)} ГБ` : ""} data={h.vram} color="#3ecf8e" max={g ? g.vram_total / 1024 : 16} />
        <Stat icon={Thermometer} label="Температура GPU" value={g ? g.temp : "—"} sub="°C" data={h.temp} color="#f5b84b" max={100} />
        <Stat icon={MemoryStick} label="Оперативная память" value={status ? status.ram.used : "—"} sub={status ? `из ${status.ram.total} ГБ` : ""} data={h.ram} color="#38bdf8" max={status?.ram.total || 32} />
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="panel rounded-2xl p-5 space-y-3">
          <div className="font-semibold">Сервисы</div>
          {status?.services.map((s) => <div key={s.name} className="flex items-center gap-3">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: s.state === "running" ? "#3ecf8e" : s.state === "starting" ? "#f5b84b" : "#ff6b6b" }} />
            <div className="flex-1"><div className="text-sm">{s.name === "ComfyUI" ? "Движок генерации (ComfyUI)" : "Помощник промптов (Ollama)"}</div><div className="text-xs dim">{ru[s.state] || s.state}{s.restarts ? ` · перезапусков: ${s.restarts}` : ""}</div></div>
            <button className="btn-ghost !h-8" onClick={async () => { await api.post(`/api/services/${s.name === "ComfyUI" ? "comfy" : "ollama"}/restart`); toast(`${s.name} перезапускается`, "info"); }}><RotateCw size={14} />Перезапустить</button>
          </div>)}
          <div className="flex items-center gap-3"><span className="w-2.5 h-2.5 rounded-full bg-[#3ecf8e]" /><div className="flex-1 text-sm">Студия (backend)<div className="text-xs dim">работает</div></div></div>
          <div className="flex gap-2 pt-2"><Tip text="Выгрузить все модели из видеопамяти"><button className="btn-ghost" onClick={async () => { try { await api.post("/api/free"); toast("Видеопамять освобождена"); } catch (e) { toast(e.message, "error"); } }}><Eraser size={15} />Освободить видеопамять</button></Tip>
            <button className="btn-ghost" onClick={report}><Copy size={15} />Скопировать отчёт об ошибке</button></div>
        </div>
        <QueuePanel />
      </div>
      <div className="panel rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-3"><span className="font-semibold flex-1">Журнал</span>
          {[["comfy", "Движок"], ["server", "Студия"], ["ollama", "Помощник"]].map(([v, l]) => <button key={v} className={`chip !h-7 !text-xs ${logName === v ? "on" : ""}`} onClick={() => setLogName(v)}>{l}</button>)}</div>
        <div className="max-h-72 overflow-y-auto text-sm space-y-1 font-mono">{logs.length ? logs.slice().reverse().map((l, i) => <div key={i} title={l.raw} className="truncate" style={{ color: l.level === "error" ? "#ff6b6b" : "var(--muted)" }}>• {l.text}</div>) : <div className="dim">Пока пусто</div>}</div>
      </div>
      <div className="panel rounded-2xl p-5">
        <div className="font-semibold mb-3">Бенчмарк на этом компьютере</div>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs dim"><th className="py-1.5">Задача</th><th>Режим</th><th>Время</th><th>Пик VRAM</th><th>Замер</th></tr></thead>
          <tbody>{bench.map((b) => <tr key={b.workflow + b.mode} className="border-t" style={{ borderColor: "var(--line)" }}><td className="py-1.5">{wfRu[b.workflow] || b.workflow}</td><td>{b.mode === "draft" ? "Черновик" : "Качество"}</td><td>{fmtSec(b.sec)}</td><td>{(b.vram_mb / 1024).toFixed(1)} ГБ</td><td className="dim">{b.time}</td></tr>)}</tbody></table></div>
      </div>
    </div>
  );
}
