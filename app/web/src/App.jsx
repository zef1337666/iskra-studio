import React, { useEffect, useState } from "react";
import { Sparkles, Images, SlidersHorizontal, Shield, ShieldOff, Sun, Moon, Cpu, Keyboard, HardDrive, UserRound, Activity, Settings as Cog } from "lucide-react";
import { useStore } from "./store";
import { api } from "./api";
import { Toasts, Tip, Modal } from "./components/ui";
import Create from "./pages/Create";
import Gallery from "./pages/Gallery";
import Presets from "./pages/Presets";
import Models from "./pages/Models";
import Characters from "./pages/Characters";
import System from "./pages/System";
import Settings, { applyAccent } from "./pages/Settings";
import Onboarding from "./components/Onboarding";

const NAV = [
  { id: "create", label: "Создать", icon: Sparkles },
  { id: "gallery", label: "Галерея", icon: Images },
  { id: "characters", label: "Персонажи", icon: UserRound },
  { id: "presets", label: "Пресеты", icon: SlidersHorizontal },
  { id: "models", label: "Модели", icon: HardDrive },
  { id: "system", label: "Система", icon: Activity, desk: true },
  { id: "settings", label: "Настройки", icon: Cog, desk: true },
];

function PinModal() {
  const { pinAsk, toggleSafe } = useStore();
  const [pin, setPin] = useState("");
  const [bad, setBad] = useState(false);
  const check = async () => { try { await api.post("/api/pin/check", { pin }); setPin(""); setBad(false); toggleSafe(true); } catch { setBad(true); } };
  return (
    <Modal open={pinAsk} onClose={() => useStore.setState({ pinAsk: false })} title="Введите PIN">
      <div className="px-6 pb-6 space-y-3">
        <div className="text-sm muted">Чтобы показать 18+ контент, введите PIN-код.</div>
        <input autoFocus type="password" inputMode="numeric" className="field !text-center !text-2xl tracking-[.5em]" value={pin} onChange={(e) => { setPin(e.target.value.replace(/\D/g, "")); setBad(false); }} onKeyDown={(e) => e.key === "Enter" && check()} />
        {bad && <div className="text-sm" style={{ color: "#ff6b6b" }}>Неверный PIN</div>}
        <button className="btn-primary w-full" onClick={check}>Открыть</button>
      </div>
    </Modal>
  );
}

const HOTKEYS = [["Ctrl + Enter", "Создать"], ["Ctrl + V", "Вставить картинку-референс"], ["Esc", "Отменить генерацию / закрыть"],
  ["← / →", "Листать в просмотре"], ["F", "В избранное"], ["U", "Апскейл"], ["S", "Безопасный режим"], ["/", "Поиск в галерее"], ["?", "Эта подсказка"]];

function StatusDots() {
  const status = useStore((s) => s.status);
  if (!status) return <div className="text-xs dim px-3">Подключение…</div>;
  const c = { running: "#3ecf8e", starting: "#f5b84b", crashed: "#ff6b6b", stopped: "#ff6b6b" };
  const ru = { running: "работает", starting: "запускается", crashed: "перезапуск", stopped: "остановлен" };
  const g = status.gpu;
  return (
    <div className="px-3 space-y-1.5 text-xs">
      {status.services.map((s) => (
        <div key={s.name}><Tip side="right" text={`${s.name}: ${ru[s.state] || s.state}${s.restarts ? `, перезапусков: ${s.restarts}` : ""}`}>
          <div className="flex items-center gap-2 muted"><span className="w-2 h-2 rounded-full" style={{ background: c[s.state] }} />{s.name === "ComfyUI" ? "Движок" : "Помощник"}</div>
        </Tip></div>
      ))}
      {g && <Tip side="right" className="flex" text={`Видеокарта: загрузка ${g.util}%, ${g.temp}°C`}>
        <div className="flex items-center gap-2 muted"><Cpu size={12} />{(g.vram_used / 1024).toFixed(1)} / {(g.vram_total / 1024).toFixed(0)} ГБ</div></Tip>}
    </div>
  );
}

export default function App() {
  const { page, setPage, safeMode, toggleSafe, theme, setTheme, loadPresets } = useStore();
  const [help, setHelp] = useState(false);
  const settings = useStore((s) => s.settings);
  useEffect(() => {
    loadPresets();
    try { const a = localStorage.getItem("iskra_accent"); if (a) applyAccent(a); } catch {}
    api.get("/api/settings").then((s) => useStore.setState({ settings: s })).catch(() => {});
    const poll = async () => { try { useStore.setState({ status: await api.get("/api/status") }); } catch {} };
    poll();
    const t = setInterval(poll, 4000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    const k = (e) => {
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "s" || e.key === "ы") toggleSafe();
      if (e.key === "?") setHelp(true);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  return (
    <div className="h-full flex flex-col md:flex-row">
      <aside className="glass md:w-60 shrink-0 md:h-full flex md:flex-col gap-1 p-2 md:p-3 order-2 md:order-1 border-t md:border-t-0 md:border-r z-10">
        <div className="hidden md:flex items-center gap-2.5 px-2 pt-1 pb-5">
          <img src="/logo.svg" className="w-9 h-9" alt="" />
          <div><div className="font-bold text-lg leading-none">Искра</div><div className="text-[11px] dim mt-1">локальная ИИ-студия</div></div>
        </div>
        {NAV.map((n) => (
          <button key={n.id} onClick={() => setPage(n.id)}
            className={`${n.desk ? "hidden md:flex" : "flex"} flex-1 md:flex-none flex-col md:flex-row items-center gap-1 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-[11px] md:text-sm font-medium transition ${page === n.id ? "text-white" : "muted hover:text-[var(--text)] hover:bg-[var(--panel-2)]"}`}
            style={page === n.id ? { background: "linear-gradient(135deg, var(--color-accent), var(--color-accent-lo))" } : {}}>
            <n.icon size={18} />{n.label}
          </button>
        ))}
        <div className="hidden md:block flex-1" />
        <div className="hidden md:block"><StatusDots /></div>
        <div className="hidden md:flex gap-1 pt-3 px-1">
          <Tip text={safeMode ? "Безопасный режим включён: 18+ скрыто (клавиша S)" : "18+ виден. Нажмите, чтобы скрыть (клавиша S)"}>
            <button className="btn-ghost !px-2.5" onClick={toggleSafe} style={safeMode ? {} : { color: "var(--color-pink)", borderColor: "var(--color-pink)" }}>
              {safeMode ? <Shield size={16} /> : <ShieldOff size={16} />}
            </button>
          </Tip>
          <Tip text="Светлая / тёмная тема"><button className="btn-ghost !px-2.5" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}</button></Tip>
          <Tip text="Горячие клавиши (?)"><button className="btn-ghost !px-2.5" onClick={() => setHelp(true)}><Keyboard size={16} /></button></Tip>
        </div>
      </aside>
      <main className="flex-1 min-h-0 overflow-hidden order-1 md:order-2">
        {page === "create" && <Create />}
        {page === "gallery" && <Gallery />}
        {page === "presets" && <Presets />}
        {page === "models" && <Models />}
        {page === "characters" && <Characters />}
        {page === "system" && <System />}
        {page === "settings" && <Settings />}
      </main>
      <Toasts />
      <PinModal />
      {settings && !settings.onboarded && <Onboarding onDone={async () => useStore.setState({ settings: await api.put("/api/settings", { onboarded: true }) })} />}
      <Modal open={help} onClose={() => setHelp(false)} title="Горячие клавиши">
        <div className="px-6 pb-6 grid gap-2">
          {HOTKEYS.map(([k, v]) => <div key={k} className="flex justify-between text-sm"><span className="muted">{v}</span><kbd className="px-2 py-0.5 rounded-md text-xs font-mono" style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}>{k}</kbd></div>)}
        </div>
      </Modal>
    </div>
  );
}
