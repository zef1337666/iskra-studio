import React, { useState } from "react";
import { ChevronDown, Lock, Image as ImageIcon, Film, Box, Wand2, Palette, Flame, Star } from "lucide-react";
import { useStore } from "../store";
import { coverUrl } from "../api";
import { Modal } from "./ui";

const GROUP_ICON = { "Фото": ImageIcon, "Арт": Palette, "Редактирование": Wand2, "Видео": Film, "3D": Box, "18+": Flame, "Мои": Star };
const GRAD = { "Фото": "#3b82f6,#8b7cff", "Арт": "#f59e0b,#ef4444", "Редактирование": "#10b981,#3b82f6", "Видео": "#8b5cf6,#ec4899", "3D": "#06b6d4,#6366f1", "18+": "#ff5fa2,#8b1d4f", "Мои": "#64748b,#8b7cff" };

export function PresetCover({ p, className = "", blur }) {
  const I = GROUP_ICON[p.group] || Star;
  const url = coverUrl(p);
  return (
    <div className={`relative overflow-hidden ${className}`} style={{ background: `linear-gradient(135deg, ${GRAD[p.group] || GRAD["Мои"]})` }}>
      {url ? <img src={url} className={`w-full h-full object-cover ${blur ? "nsfw-blur" : ""}`} alt="" loading="lazy" />
        : <div className="w-full h-full flex items-center justify-center"><I size={30} className="text-white/80" /></div>}
    </div>
  );
}

export default function PresetPicker({ value, onChange, compact }) {
  const { presets, safeMode } = useStore();
  const [open, setOpen] = useState(false);
  const visible = presets.filter((p) => !p.hidden && !(safeMode && p.nsfw));
  const groups = [...new Set(visible.map((p) => p.group))];
  const [tab, setTab] = useState(null);
  const cur = presets.find((p) => p.id === value);
  const g = tab && groups.includes(tab) ? tab : cur?.group && groups.includes(cur.group) ? cur.group : groups[0];
  return (
    <>
      {compact ? <button onClick={() => setOpen(true)} className="chip !h-8 shrink-0"><ChevronDown size={14} />Все пресеты</button> :
      <button onClick={() => setOpen(true)} className="w-full flex items-center gap-3 p-2 rounded-2xl transition hover:bg-[var(--panel-2)]" style={{ border: "1px solid var(--line)" }}>
        {cur ? <PresetCover p={cur} className="w-12 h-12 rounded-xl shrink-0" blur={cur.nsfw && safeMode} /> : <div className="w-12 h-12 rounded-xl skeleton" />}
        <div className="text-left min-w-0 flex-1">
          <div className="text-xs dim">Пресет</div>
          <div className="font-semibold truncate flex items-center gap-1.5">{cur?.name || "Выберите пресет"}{cur?.nsfw && <span className="text-[10px] px-1.5 rounded bg-[var(--color-pink)] text-white">18+</span>}</div>
          <div className="text-xs muted truncate">{cur?.base_model}</div>
        </div>
        <ChevronDown size={18} className="dim" />
      </button>}
      <Modal open={open} onClose={() => setOpen(false)} wide title="Выберите пресет">
        <div className="px-6 flex gap-2 flex-wrap pb-4">
          {groups.map((x) => { const I = GROUP_ICON[x] || Star; return (
            <button key={x} className={`chip ${x === g ? "on" : ""}`} onClick={() => setTab(x)} style={x === "18+" && x === g ? { background: "var(--color-pink)", borderColor: "var(--color-pink)" } : {}}><I size={14} />{x}</button>); })}
          {safeMode && <span className="chip !cursor-default opacity-70"><Lock size={13} />18+ скрыто</span>}
        </div>
        <div className="px-6 pb-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {visible.filter((p) => p.group === g).map((p, i) => (
            <button key={p.id} onClick={() => { onChange(p.id); setOpen(false); }} style={{ animationDelay: `${i * 30}ms`, border: `1px solid ${p.id === value ? "var(--color-accent)" : "var(--line)"}` }}
              className="text-left rounded-2xl overflow-hidden transition hover:-translate-y-0.5 hover:shadow-xl animate-fade-in">
              <PresetCover p={p} className="aspect-[4/3]" />
              <div className="p-3">
                <div className="font-semibold text-sm">{p.name}</div>
                <div className="text-xs muted line-clamp-2 mt-0.5 min-h-8">{p.description}</div>
                <div className="text-[11px] dim mt-1.5">{p.base_model} · ~{p.eta?.quality ?? "?"} с</div>
              </div>
            </button>
          ))}
        </div>
      </Modal>
    </>
  );
}
