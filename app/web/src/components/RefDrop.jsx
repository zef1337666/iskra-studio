import React, { useEffect, useRef, useState } from "react";
import { ImagePlus, X, Loader2, Film } from "lucide-react";
import { api } from "../api";
import { useStore } from "../store";
import { Tip } from "./ui";

export const FOCUS = [
  { id: "all", label: "Всё", tip: "Повторить картинку максимально близко" },
  { id: "style", label: "Стиль", tip: "Взять только стиль: технику, цвета, настроение" },
  { id: "composition", label: "Композиция и поза", tip: "Взять расположение и позу" },
  { id: "character", label: "Персонаж", tip: "Взять внешность персонажа" },
  { id: "colors", label: "Цвета и свет", tip: "Взять только палитру и освещение" },
];

// Список референсов (1–3). Поддерживает перетаскивание файла, перетаскивание из галереи и Ctrl+V.
export default function RefDrop({ refs, setRefs, max = 1, accept = "image", label = "Картинка-референс" }) {
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const input = useRef();
  const toast = useStore((s) => s.toast);
  const add = async (files) => {
    const list = [...files].slice(0, max - refs.length);
    if (!list.length) return;
    setBusy(true);
    try {
      const up = [];
      for (const f of list) up.push(await api.upload(f));
      setRefs([...refs, ...up].slice(0, max));
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  useEffect(() => {
    const onPaste = (e) => {
      const files = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith("image/"));
      if (files.length && refs.length < max) { e.preventDefault(); add(files); }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  });
  const onDrop = async (e) => {
    e.preventDefault(); setOver(false);
    const gal = e.dataTransfer.getData("application/x-iskra-item");
    if (gal) {
      const it = JSON.parse(gal);
      try { const r = await api.post(`/api/items/${it.id}/to-input`); setRefs([...refs, r].slice(0, max)); } catch (er) { toast(er.message, "error"); }
      return;
    }
    add(e.dataTransfer.files);
  };
  return (
    <div>
      <div className="flex items-center justify-between mb-2"><span className="label">{label}</span><span className="text-[11px] dim">{max > 1 ? `до ${max} · ` : ""}перетащите или Ctrl+V</span></div>
      <div className="flex gap-2 flex-wrap">
        {refs.map((r, i) => (
          <div key={i} className="relative w-20 h-20 rounded-xl overflow-hidden animate-pop" style={{ border: "1px solid var(--line)" }}>
            {accept === "video" ? <video src={r.url} className="w-full h-full object-cover" muted /> : <img src={r.url} className="w-full h-full object-cover" alt="" />}
            <button onClick={() => setRefs(refs.filter((_, j) => j !== i))} className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80" aria-label="Убрать"><X size={13} /></button>
          </div>
        ))}
        {refs.length < max && (
          <button onClick={() => input.current.click()} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}
            className={`h-20 rounded-xl flex items-center justify-center gap-2 text-sm transition ${refs.length ? "w-20" : "flex-1 min-w-40"}`}
            style={{ border: `1.5px dashed ${over ? "var(--color-accent)" : "var(--line)"}`, background: over ? "rgba(139,124,255,.08)" : "transparent", color: "var(--muted)" }}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : accept === "video" ? <Film size={18} /> : <ImagePlus size={18} />}
            {!refs.length && !busy && <span>{accept === "video" ? "Добавить видео" : "Добавить картинку"}</span>}
          </button>
        )}
      </div>
      <input ref={input} type="file" hidden multiple={max > 1} accept={accept === "video" ? "video/*" : "image/*"} onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
    </div>
  );
}

export function FocusChips({ value, onChange }) {
  return (
    <div className="flex gap-1.5 flex-wrap">
      {FOCUS.map((f) => <Tip key={f.id} text={f.tip}><button className={`chip !h-7 !text-xs ${value === f.id ? "on" : ""}`} onClick={() => onChange(f.id)}>{f.label}</button></Tip>)}
    </div>
  );
}
