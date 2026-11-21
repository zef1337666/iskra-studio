import React, { useEffect, useState } from "react";
import { X, ChevronLeft, ChevronRight, Heart, Copy, FolderOpen, Download, Star, Info } from "lucide-react";
import { fileUrl, api } from "../api";
import { useStore } from "../store";
import { ACTIONS, toggleFav } from "./actions";
import { Tip } from "./ui";
import MaskEditor from "./MaskEditor";

export function Media({ it, className = "", controls, autoPlay }) {
  if (it.kind === "video") return <video src={fileUrl(it)} className={className} controls={controls} autoPlay={autoPlay} loop playsInline />;
  if (it.kind === "3d") return <model-viewer src={fileUrl(it)} camera-controls auto-rotate class={className} style={{ width: "100%", height: "100%" }} />;
  return <img src={fileUrl(it)} className={className} alt="" />;
}

function Compare({ before, after }) {
  const [x, setX] = useState(50);
  const ref = React.useRef();
  const drag = (e) => { const r = ref.current.getBoundingClientRect(); setX(Math.min(100, Math.max(0, ((e.clientX - r.left) / r.width) * 100))); };
  return (
    <div ref={ref} className="relative max-w-full max-h-full select-none cursor-ew-resize" onMouseMove={(e) => e.buttons === 1 && drag(e)} onMouseDown={drag} onClick={(e) => e.stopPropagation()}>
      <img src={fileUrl(after)} className="max-w-full max-h-[calc(100vh-170px)] block rounded-lg" alt="" draggable={false} />
      <img src={fileUrl(before)} className="absolute inset-0 w-full h-full object-fill rounded-lg" style={{ clipPath: `inset(0 ${100 - x}% 0 0)` }} alt="" draggable={false} />
      <div className="absolute top-0 bottom-0 w-0.5 bg-white shadow" style={{ left: `${x}%` }}><div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-9 h-9 rounded-full bg-white text-black flex items-center justify-center text-xs font-bold">⇔</div></div>
      <span className="absolute top-3 left-3 text-xs bg-black/60 text-white px-2 py-1 rounded">До</span><span className="absolute top-3 right-3 text-xs bg-black/60 text-white px-2 py-1 rounded">После</span>
    </div>
  );
}

export default function Lightbox({ items, index, onClose, onIndex }) {
  const it = items[index];
  const [cur, setCur] = useState(it);
  const [zoom, setZoom] = useState(false);
  const [meta, setMeta] = useState(false);
  const [parent, setParent] = useState(null);
  const [compare, setCompare] = useState(false);
  const [mask, setMask] = useState(false);
  const [collMenu, setCollMenu] = useState(null);
  const toast = useStore((s) => s.toast);
  useEffect(() => {
    setCur(it); setZoom(false); setCompare(false); setParent(null);
    if (it?.parent_id) api.get(`/api/items/${it.parent_id}`).then((p) => p.kind === "image" && setParent(p)).catch(() => {});
  }, [it?.id]);
  const saveChar = async () => {
    const name = prompt("Имя персонажа (вымышленного):");
    if (!name) return;
    try { const ref = await api.post(`/api/items/${cur.id}/to-input`); await api.post("/api/characters", { name, description: cur.user_text || "", refs: [ref], cover: cur.thumb }); toast(`Персонаж «${name}» сохранён — выберите его в «Создать»`); }
    catch (e) { toast(e.message, "error"); }
  };
  const openColl = async () => setCollMenu(await api.get("/api/collections"));
  const addColl = async (c) => {
    try {
      const col = c || (await api.post("/api/collections", { name: window.prompt("Название новой коллекции:") || "" }));
      await api.post(`/api/collections/${col.id}/add`, { ids: [cur.id] }); toast(`Добавлено в «${col.name}»`); setCollMenu(null);
    } catch (e) { toast(e.message, "error"); }
  };
  useEffect(() => {
    const k = (e) => {
      if (["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" && index < items.length - 1) onIndex(index + 1);
      if (e.key === "ArrowLeft" && index > 0) onIndex(index - 1);
      if (e.key === "f" || e.key === "а") fav();
      if ((e.key === "u" || e.key === "г") && cur.kind === "image") ACTIONS.find((a) => a.id === "upscale").run(cur);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  });
  if (!cur) return null;
  const fav = async () => setCur(await toggleFav(cur));
  const rate = async (n) => setCur(await api.patch(`/api/items/${cur.id}`, { rating: n === cur.rating ? 0 : n }));
  const copy = async () => {
    try {
      const b = await (await fetch(fileUrl(cur))).blob();
      const png = b.type === "image/png" ? b : await new Promise((res) => { const img = new Image(); img.onload = () => { const c = document.createElement("canvas"); c.width = img.width; c.height = img.height; c.getContext("2d").drawImage(img, 0, 0); c.toBlob(res, "image/png"); }; img.src = URL.createObjectURL(b); });
      await navigator.clipboard.write([new ClipboardItem({ "image/png": png })]);
      toast("Картинка скопирована в буфер обмена");
    } catch { toast("Не получилось скопировать — попробуйте «Скачать»", "error"); }
  };
  return (
    <div className="fixed inset-0 z-[90] bg-black/90 flex flex-col animate-fade-in">
      <div className="flex items-center gap-2 p-3 text-white/80">
        <div className="text-sm truncate flex-1 px-2">{cur.preset_name} · {cur.width}×{cur.height} · seed {cur.seed}</div>
        <Tip text="В избранное (F)" side="bottom"><button className="btn !text-white hover:bg-white/10" onClick={fav}><Heart size={18} fill={cur.favorite ? "#ff5fa2" : "none"} color={cur.favorite ? "#ff5fa2" : "currentColor"} /></button></Tip>
        <div className="flex">{[1, 2, 3, 4, 5].map((n) => <button key={n} onClick={() => rate(n)} className="p-1" aria-label={`Оценка ${n}`}><Star size={16} fill={n <= (cur.rating || 0) ? "#f5b84b" : "none"} color={n <= (cur.rating || 0) ? "#f5b84b" : "currentColor"} /></button>)}</div>
        {cur.kind === "image" && <Tip text="Копировать в буфер" side="bottom"><button className="btn !text-white hover:bg-white/10" onClick={copy}><Copy size={18} /></button></Tip>}
        <Tip text="Открыть в папке" side="bottom"><button className="btn !text-white hover:bg-white/10" onClick={() => api.post(`/api/items/${cur.id}/open-folder`)}><FolderOpen size={18} /></button></Tip>
        <Tip text="Скачать" side="bottom"><a className="btn !text-white hover:bg-white/10" href={fileUrl(cur)} download><Download size={18} /></a></Tip>
        <Tip text="Промпт и параметры" side="bottom"><button className={`btn !text-white hover:bg-white/10 ${meta ? "bg-white/15" : ""}`} onClick={() => setMeta(!meta)}><Info size={18} /></button></Tip>
        <button className="btn !text-white hover:bg-white/10" onClick={onClose} aria-label="Закрыть (Esc)"><X size={20} /></button>
      </div>
      <div className="flex-1 min-h-0 flex relative">
        <div className={`flex-1 min-w-0 flex items-center justify-center p-4 ${zoom ? "overflow-auto" : ""}`} onClick={() => cur.kind === "image" && setZoom(!zoom)}>
          {compare && parent ? <Compare before={parent} after={cur} /> : <Media it={cur} controls autoPlay className={zoom ? "max-w-none cursor-zoom-out" : "max-w-full max-h-full object-contain cursor-zoom-in rounded-lg"} />}
        </div>
        {collMenu && <div className="absolute bottom-3 left-1/2 -translate-x-1/2 panel rounded-2xl p-2 w-64 shadow-2xl z-10 animate-pop" onClick={(e) => e.stopPropagation()}>
          <div className="text-xs dim px-2 py-1">Добавить в коллекцию</div>
          {collMenu.map((c) => <button key={c.id} className="w-full text-left px-2 py-1.5 rounded-lg text-sm hover:bg-[var(--panel-2)]" onClick={() => addColl(c)}>{c.name} <span className="dim text-xs">· {c.n}</span></button>)}
          <button className="w-full text-left px-2 py-1.5 rounded-lg text-sm hover:bg-[var(--panel-2)]" style={{ color: "var(--color-accent-hi)" }} onClick={() => addColl(null)}>+ Новая коллекция</button>
          <button className="w-full text-left px-2 py-1 text-xs dim" onClick={() => setCollMenu(null)}>Закрыть</button>
        </div>}
        {meta && <div className="w-80 shrink-0 bg-black/60 text-white/85 text-sm p-4 overflow-auto space-y-3">
          <div><div className="text-white/50 text-xs mb-1">Ваш текст</div>{cur.user_text || "—"}</div>
          <div><div className="text-white/50 text-xs mb-1">Промпт</div><div className="text-xs leading-relaxed">{cur.prompt}</div></div>
          {cur.negative && <div><div className="text-white/50 text-xs mb-1">Негатив</div><div className="text-xs">{cur.negative}</div></div>}
          <div className="text-xs text-white/60">Модель: {cur.model} · режим: {cur.mode === "draft" ? "Черновик" : "Качество"} · {cur.job_sec} с</div>
        </div>}
        {index > 0 && <button className="absolute left-3 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center" onClick={() => onIndex(index - 1)} aria-label="Назад"><ChevronLeft /></button>}
        {index < items.length - 1 && <button className="absolute right-3 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center" style={meta ? { right: "21rem" } : {}} onClick={() => onIndex(index + 1)} aria-label="Вперёд"><ChevronRight /></button>}
      </div>
      <div className="flex gap-2 p-3 overflow-x-auto justify-center flex-wrap">
        {parent && <Tip text="Слайдер «до / после»"><button className={`btn !h-8 !text-xs text-white ${compare ? "bg-[var(--color-accent)]" : "bg-white/10 hover:bg-white/20"}`} onClick={() => setCompare(!compare)}>Сравнить</button></Tip>}
        {cur.kind === "image" && <Tip text="Закрасьте область и опишите, что там нарисовать"><button className="btn !h-8 !text-xs text-white/90 bg-white/10 hover:bg-white/20" onClick={() => setMask(true)}>Перерисовать область</button></Tip>}
        {cur.kind === "image" && !cur.nsfw && <Tip text="Сохранить вымышленного персонажа для повторного использования"><button className="btn !h-8 !text-xs text-white/90 bg-white/10 hover:bg-white/20" onClick={saveChar}>Сохранить персонажа</button></Tip>}
        <button className="btn !h-8 !text-xs text-white/90 bg-white/10 hover:bg-white/20" onClick={openColl}>В коллекцию</button>
        {ACTIONS.filter((a) => a.kinds.includes(cur.kind)).map((a) => (
          <Tip key={a.id} text={a.hint}><button className="btn !h-8 text-white/90 bg-white/10 hover:bg-white/20 !text-xs whitespace-nowrap" onClick={() => { a.run(cur); if (["edit", "animate", "as-ref", "edit-prompt"].includes(a.id)) onClose(); }}>{a.label}</button></Tip>
        ))}
      </div>
      {mask && <MaskEditor item={cur} onClose={() => setMask(false)} />}
    </div>
  );
}
