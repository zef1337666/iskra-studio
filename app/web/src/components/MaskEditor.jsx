import React, { useEffect, useRef, useState } from "react";
import { Brush, Eraser, Undo2, X, Sparkles, Loader2, Trash2 } from "lucide-react";
import { api, fileUrl } from "../api";
import { useStore } from "../store";
import { Tip } from "./ui";

// Редактор маски для «Перерисовать область»: кисть, ластик, размер, отмена. Маска = белое по чёрному, в размер оригинала.
export default function MaskEditor({ item, onClose }) {
  const img = useRef(), cv = useRef(), wrap = useRef();
  const [tool, setTool] = useState("brush");
  const [size, setSize] = useState(60);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [hist, setHist] = useState([]);
  const [cursor, setCursor] = useState(null);
  const drawing = useRef(false), last = useRef(null);
  const toast = useStore((s) => s.toast);

  const fit = () => {
    const i = img.current, c = cv.current;
    if (!i?.naturalWidth) return;
    c.width = i.naturalWidth; c.height = i.naturalHeight;
  };
  const pos = (e) => {
    const r = cv.current.getBoundingClientRect();
    return { x: (e.clientX - r.left) * (cv.current.width / r.width), y: (e.clientY - r.top) * (cv.current.height / r.height), k: cv.current.width / r.width };
  };
  const stroke = (a, b) => {
    const ctx = cv.current.getContext("2d");
    ctx.globalCompositeOperation = tool === "brush" ? "source-over" : "destination-out";
    ctx.strokeStyle = "rgba(139,124,255,1)"; ctx.lineWidth = size * a.k; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  };
  const down = (e) => {
    setHist([...hist.slice(-20), cv.current.getContext("2d").getImageData(0, 0, cv.current.width, cv.current.height)]);
    drawing.current = true; last.current = pos(e); stroke(last.current, last.current);
  };
  const move = (e) => {
    const r = wrap.current.getBoundingClientRect();
    setCursor({ x: e.clientX - r.left, y: e.clientY - r.top });
    if (!drawing.current) return;
    const p = pos(e); stroke(last.current, p); last.current = p;
  };
  const undo = () => { const h = [...hist]; const s = h.pop(); if (s) cv.current.getContext("2d").putImageData(s, 0, 0); setHist(h); };
  const clear = () => { setHist([...hist, cv.current.getContext("2d").getImageData(0, 0, cv.current.width, cv.current.height)]); cv.current.getContext("2d").clearRect(0, 0, cv.current.width, cv.current.height); };
  useEffect(() => {
    const k = (e) => { if (e.ctrlKey && e.key === "z") undo(); if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  });

  const submit = async () => {
    if (!text.trim()) { toast("Напишите, что нарисовать в выделенной области", "info"); return; }
    const c = cv.current, ctx = c.getContext("2d");
    const data = ctx.getImageData(0, 0, c.width, c.height).data;
    let any = false;
    for (let i = 3; i < data.length; i += 4 * 97) if (data[i] > 0) { any = true; break; }
    if (!any) { toast("Закрасьте кистью область, которую нужно перерисовать", "info"); return; }
    setBusy(true);
    const m = document.createElement("canvas"); m.width = c.width; m.height = c.height;
    const mx = m.getContext("2d"); mx.fillStyle = "#000"; mx.fillRect(0, 0, m.width, m.height);
    mx.globalCompositeOperation = "source-over"; mx.filter = "brightness(0) invert(1)"; mx.drawImage(c, 0, 0);
    const blob = await new Promise((r) => m.toBlob(r, "image/png"));
    try {
      const up = await api.upload(new File([blob], "mask.png", { type: "image/png" }));
      await api.post("/api/generate", { preset: "inpaint", mode: "quality", source_item: item.id, mask: up.name, prompt: text, user_text: text });
      toast("Перерисовка добавлена в очередь", "info"); onClose();
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-[95] bg-black/95 flex flex-col animate-fade-in">
      <div className="flex items-center gap-2 p-3 text-white flex-wrap">
        <div className="font-semibold px-2">Перерисовать область</div>
        <div className="flex gap-1 bg-white/10 rounded-xl p-1">
          <Tip text="Кисть" side="bottom"><button onClick={() => setTool("brush")} className={`btn !h-8 ${tool === "brush" ? "bg-[var(--color-accent)]" : ""}`}><Brush size={16} /></button></Tip>
          <Tip text="Ластик" side="bottom"><button onClick={() => setTool("eraser")} className={`btn !h-8 ${tool === "eraser" ? "bg-[var(--color-accent)]" : ""}`}><Eraser size={16} /></button></Tip>
        </div>
        <span className="text-xs text-white/60 ml-2">Размер</span>
        <input type="range" min="8" max="240" value={size} onChange={(e) => setSize(Number(e.target.value))} className="w-32" />
        <Tip text="Отменить (Ctrl+Z)" side="bottom"><button className="btn !h-8 hover:bg-white/10" onClick={undo}><Undo2 size={16} /></button></Tip>
        <Tip text="Стереть всё" side="bottom"><button className="btn !h-8 hover:bg-white/10" onClick={clear}><Trash2 size={16} /></button></Tip>
        <div className="flex-1" />
        <button className="btn !h-8 hover:bg-white/10" onClick={onClose} aria-label="Закрыть"><X size={18} /></button>
      </div>
      <div className="flex-1 min-h-0 flex items-center justify-center p-4">
        <div ref={wrap} className="relative max-w-full max-h-full" style={{ cursor: "none" }} onMouseLeave={() => { setCursor(null); drawing.current = false; }}>
          <img ref={img} src={fileUrl(item)} onLoad={fit} className="max-w-full max-h-[calc(100vh-190px)] block select-none rounded-lg" draggable={false} alt="" />
          <canvas ref={cv} className="absolute inset-0 w-full h-full opacity-55" onMouseDown={down} onMouseMove={move} onMouseUp={() => (drawing.current = false)} />
          {cursor && <div className="pointer-events-none absolute rounded-full border-2 border-white" style={{ width: size, height: size, left: cursor.x - size / 2, top: cursor.y - size / 2 }} />}
        </div>
      </div>
      <div className="p-3 flex gap-2 max-w-3xl w-full mx-auto">
        <input className="field !bg-white/10 !text-white !border-white/20 flex-1" autoFocus value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Что нарисовать в закрашенной области? Например: «солнечные очки», «букет цветов»" />
        <button className="btn-primary" onClick={submit} disabled={busy}>{busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}Перерисовать</button>
      </div>
    </div>
  );
}
