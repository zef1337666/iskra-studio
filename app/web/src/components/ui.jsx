import React, { useEffect } from "react";
import { X, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { useStore } from "../store";

export function Tip({ text, children, side = "top", className = "" }) {
  if (!text) return children;
  const pos = side === "bottom" ? "top-full mt-2" : side === "right" ? "left-full ml-2 top-1/2 -translate-y-1/2" : "bottom-full mb-2";
  return (
    <span className={`relative group/tip inline-flex ${className}`}>
      {children}
      <span className={`pointer-events-none absolute ${pos} ${side === "right" ? "" : "left-1/2 -translate-x-1/2"} z-50 w-max max-w-64 rounded-lg px-2.5 py-1.5 text-xs leading-snug opacity-0 transition group-hover/tip:opacity-100 group-hover/tip:delay-300 panel shadow-xl`}
        style={{ color: "var(--text)" }}>{text}</span>
    </span>
  );
}

export function Toasts() {
  const toasts = useStore((s) => s.toasts);
  const icon = { ok: CheckCircle2, error: AlertTriangle, info: Info };
  const color = { ok: "#3ecf8e", error: "#ff6b6b", info: "#8b7cff" };
  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 w-[min(380px,calc(100vw-32px))]">
      {toasts.map((t) => { const I = icon[t.kind] || Info; return (
        <div key={t.id} className="glass rounded-2xl px-4 py-3 shadow-2xl flex gap-3 items-start animate-pop">
          <I size={18} style={{ color: color[t.kind] }} className="shrink-0 mt-0.5" />
          <div className="text-sm leading-snug">{t.text}</div>
        </div>); })}
    </div>
  );
}

export function Modal({ open, onClose, children, wide, title }) {
  useEffect(() => {
    if (!open) return;
    const k = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[80] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in" onMouseDown={onClose}>
      <div className={`panel rounded-3xl shadow-2xl w-full ${wide ? "max-w-5xl" : "max-w-lg"} max-h-[90vh] overflow-auto animate-pop`} onMouseDown={(e) => e.stopPropagation()}>
        {title && <div className="flex items-center justify-between px-6 pt-5 pb-2"><h2 className="text-lg font-semibold">{title}</h2>
          <button className="btn-ghost !h-8 !px-2" onClick={onClose} aria-label="Закрыть"><X size={16} /></button></div>}
        {children}
      </div>
    </div>
  );
}

export function Segmented({ value, onChange, options }) {
  return (
    <div className="flex p-1 rounded-xl gap-1" style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}>
      {options.map((o) => (
        <Tip key={o.value} text={o.tip} className="flex-1">
          <button onClick={() => onChange(o.value)}
            className={`w-full h-9 px-3 rounded-lg text-sm font-medium transition flex items-center justify-center gap-1.5 ${value === o.value ? "text-white shadow" : "muted hover:text-[var(--text)]"}`}
            style={value === o.value ? { background: "var(--color-accent)" } : {}}>
            {o.icon}{o.label}{o.sub && <span className="text-[11px] opacity-75 font-normal">{o.sub}</span>}
          </button>
        </Tip>
      ))}
    </div>
  );
}

export function Empty({ icon: I, title, text, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6 animate-fade-in">
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4" style={{ background: "var(--panel-2)" }}><I size={28} className="dim" /></div>
      <div className="text-lg font-semibold mb-1">{title}</div>
      <div className="muted text-sm max-w-sm mb-5">{text}</div>
      {action}
    </div>
  );
}

export const fmtSec = (s) => (s == null ? "" : s < 60 ? `${Math.round(s)} с` : `${Math.floor(s / 60)} мин ${Math.round(s % 60)} с`);
