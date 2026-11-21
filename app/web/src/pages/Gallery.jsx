import React, { useEffect, useRef, useState, useCallback } from "react";
import { Search, Heart, Image as ImageIcon, Film, Box, CheckSquare, Trash2, X, Star, Images, Play } from "lucide-react";
import { useStore } from "../store";
import { api, thumbUrl, fileUrl } from "../api";
import Lightbox from "../components/Lightbox";
import { Empty, Tip } from "../components/ui";

const KINDS = [[null, "Всё", Images], ["image", "Фото", ImageIcon], ["video", "Видео", Film], ["3d", "3D", Box]];

function Tile({ it, onOpen, selecting, selected, onSelect }) {
  const [hover, setHover] = useState(false);
  const ratio = it.width && it.height ? it.height / it.width : 1;
  return (
    <div className="mb-3 break-inside-avoid relative group rounded-2xl overflow-hidden panel cursor-pointer animate-fade-in" style={{ outline: selected ? "3px solid var(--color-accent)" : "none" }}
      onClick={() => (selecting ? onSelect(it) : onOpen(it))} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      draggable onDragStart={(e) => e.dataTransfer.setData("application/x-iskra-item", JSON.stringify({ id: it.id }))}>
      <div style={{ aspectRatio: `1 / ${Math.min(Math.max(ratio, 0.5), 2)}` }} className="relative" >
        {it.kind === "video" && hover ? <video src={fileUrl(it)} autoPlay muted loop playsInline className="absolute inset-0 w-full h-full object-cover" />
          : it.thumb ? <img src={thumbUrl(it)} loading="lazy" className="absolute inset-0 w-full h-full object-cover transition duration-300 group-hover:scale-[1.03]" alt="" />
          : <div className="absolute inset-0 flex items-center justify-center" style={{ background: "linear-gradient(135deg,#06b6d4,#6366f1)" }}><Box size={36} className="text-white/80" /></div>}
        {it.kind === "video" && !hover && <div className="absolute top-2 left-2 w-7 h-7 rounded-full bg-black/50 text-white flex items-center justify-center"><Play size={13} fill="white" /></div>}
        {it.favorite && <Heart size={16} fill="#ff5fa2" color="#ff5fa2" className="absolute top-2.5 right-2.5 drop-shadow" />}
        {it.nsfw && <span className="absolute bottom-2 right-2 text-[10px] px-1.5 rounded bg-[var(--color-pink)] text-white">18+</span>}
        {selecting && <div className={`absolute top-2 left-2 w-6 h-6 rounded-md flex items-center justify-center ${selected ? "bg-[var(--color-accent)]" : "bg-black/40 border border-white/60"}`}>{selected && <CheckSquare size={14} color="white" />}</div>}
        <div className="absolute inset-x-0 bottom-0 p-2.5 text-[11px] text-white bg-gradient-to-t from-black/75 to-transparent opacity-0 group-hover:opacity-100 transition line-clamp-2">{it.user_text || it.prompt}</div>
      </div>
    </div>
  );
}

export default function Gallery() {
  const { safeMode, galleryVersion, presets, toast } = useStore();
  const [items, setItems] = useState(null);
  const [kind, setKind] = useState(null);
  const [fav, setFav] = useState(false);
  const [preset, setPreset] = useState("");
  const [rating, setRating] = useState(0);
  const [q, setQ] = useState("");
  const [qDeb, setQDeb] = useState("");
  const [more, setMore] = useState(true);
  const [lb, setLb] = useState(null);
  const [selecting, setSelecting] = useState(false);
  const [sel, setSel] = useState(new Set());
  const [coll, setColl] = useState("");
  const [colls, setColls] = useState([]);
  const [trash, setTrash] = useState(false);
  useEffect(() => { api.get("/api/collections").then(setColls).catch(() => {}); }, [galleryVersion]);
  const sentinel = useRef();
  const search = useRef();
  const loading = useRef(false);

  useEffect(() => { const t = setTimeout(() => setQDeb(q), 300); return () => clearTimeout(t); }, [q]);
  const params = useCallback((before) => {
    const u = new URLSearchParams({ limit: 60, nsfw: safeMode ? 0 : 1 });
    if (before) u.set("before", before);
    if (kind) u.set("kind", kind);
    if (fav) u.set("favorite", 1);
    if (preset) u.set("preset", preset);
    if (rating) u.set("rating", rating);
    if (qDeb) u.set("q", qDeb);
    if (coll) u.set("collection", coll);
    if (trash) u.set("trash", 1);
    return u.toString();
  }, [safeMode, kind, fav, preset, rating, qDeb, coll, trash]);
  const load = useCallback(async (reset) => {
    if (loading.current) return;
    loading.current = true;
    try {
      const before = reset ? null : items?.[items.length - 1]?.id;
      const page = await api.get(`/api/items?${params(before)}`);
      setItems(reset ? page : [...(items || []), ...page]);
      setMore(page.length === 60);
    } catch (e) { toast(e.message, "error"); }
    loading.current = false;
  }, [items, params]);
  useEffect(() => { load(true); }, [params, galleryVersion]);
  useEffect(() => {
    const ob = new IntersectionObserver((e) => { if (e[0].isIntersecting && more && items?.length) load(false); }, { rootMargin: "800px" });
    if (sentinel.current) ob.observe(sentinel.current);
    return () => ob.disconnect();
  }, [load, more, items]);
  useEffect(() => {
    const k = (e) => { if (e.key === "/" && document.activeElement?.tagName !== "INPUT") { e.preventDefault(); search.current?.focus(); } };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  const toggleSel = (it) => { const s = new Set(sel); s.has(it.id) ? s.delete(it.id) : s.add(it.id); setSel(s); };
  const bulk = async (patch, msg) => {
    for (const id of sel) await api.patch(`/api/items/${id}`, patch);
    toast(msg); setSel(new Set()); setSelecting(false); load(true);
  };
  const usedPresets = presets.filter((p) => !(safeMode && p.nsfw));
  const toColl = async () => {
    const name = window.prompt(`Название коллекции (существующие: ${colls.map((c) => c.name).join(", ") || "нет"}):`);
    if (!name) return;
    try {
      const c = colls.find((x) => x.name === name.trim()) || (await api.post("/api/collections", { name }));
      await api.post(`/api/collections/${c.id}/add`, { ids: [...sel] });
      toast(`Добавлено в «${c.name}»: ${sel.size}`); setSel(new Set()); setSelecting(false); useStore.setState({ galleryVersion: galleryVersion + 1 });
    } catch (e) { toast(e.message, "error"); }
  };
  const zip = async () => {
    const r = await fetch("/api/export.zip", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids: [...sel] }) });
    const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = `iskra_${sel.size}.zip`; a.click();
    toast("Архив готов");
  };
  return (
    <div className="h-full flex flex-col">
      <div className="p-4 md:px-6 flex flex-wrap gap-2 items-center border-b glass" style={{ borderColor: "var(--line)" }}>
        <div className="relative flex-1 min-w-52 max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 dim" />
          <input ref={search} className="field !pl-9" placeholder="Поиск по промпту  ( / )" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {KINDS.map(([k, l, I]) => <button key={l} className={`chip ${kind === k ? "on" : ""}`} onClick={() => setKind(k)}><I size={14} />{l}</button>)}
        <button className={`chip ${fav ? "on" : ""}`} onClick={() => setFav(!fav)}><Heart size={14} />Избранное</button>
        <Tip text="Минимальная оценка"><div className="flex items-center px-1">{[1, 2, 3, 4, 5].map((n) => <button key={n} onClick={() => setRating(rating === n ? 0 : n)} className="p-0.5" aria-label={`от ${n} звёзд`}><Star size={15} fill={n <= rating ? "#f5b84b" : "none"} color={n <= rating ? "#f5b84b" : "var(--dim)"} /></button>)}</div></Tip>
        <select className="field !w-auto !py-1.5" value={preset} onChange={(e) => setPreset(e.target.value)}>
          <option value="">Все пресеты</option>{usedPresets.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {colls.length > 0 && <select className="field !w-auto !py-1.5" value={coll} onChange={(e) => setColl(e.target.value)}>
          <option value="">Все коллекции</option>{colls.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.n})</option>)}</select>}
        <button className={`chip ${trash ? "on" : ""}`} onClick={() => setTrash(!trash)}><Trash2 size={14} />Корзина</button>
        <div className="flex-1" />
        {selecting ? <>
          <span className="text-sm muted">Выбрано: {sel.size}</span>
          {trash ? <button className="btn-ghost" disabled={!sel.size} onClick={() => bulk({ deleted: 0 }, "Восстановлено")}>Восстановить</button> : <>
            <button className="btn-ghost" disabled={!sel.size} onClick={() => bulk({ favorite: 1 }, "Добавлено в избранное")}><Heart size={15} />В избранное</button>
            <button className="btn-ghost" disabled={!sel.size} onClick={toColl}>В коллекцию</button>
            <button className="btn-ghost" disabled={!sel.size} onClick={zip}>Скачать zip</button>
            <button className="btn-ghost" disabled={!sel.size} onClick={() => bulk({ deleted: 1 }, "Перемещено в корзину (можно восстановить)")} style={{ color: "#ff6b6b" }}><Trash2 size={15} />В корзину</button></>}
          <button className="btn-ghost !px-2.5" onClick={() => { setSelecting(false); setSel(new Set()); }} aria-label="Отмена"><X size={15} /></button>
        </> : <button className="btn-ghost" onClick={() => setSelecting(true)}><CheckSquare size={15} />Выбрать</button>}
      </div>
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        {items === null ? <div className="columns-2 md:columns-3 xl:columns-4 2xl:columns-5 gap-3">{Array.from({ length: 12 }).map((_, i) => <div key={i} className="mb-3 rounded-2xl skeleton" style={{ height: 160 + (i % 4) * 60 }} />)}</div>
          : items.length === 0 ? <Empty icon={Images} title={q || kind || fav ? "Ничего не нашлось" : "Здесь пока пусто"} text={q || kind || fav ? "Попробуйте изменить фильтры или поиск." : "Всё, что вы создадите, появится здесь."}
              action={!(q || kind || fav) && <button className="btn-primary" onClick={() => useStore.getState().setPage("create")}>Создать первую картинку</button>} />
          : <div className="columns-2 md:columns-3 xl:columns-4 2xl:columns-5 gap-3">
              {items.map((it, i) => <Tile key={it.id} it={it} onOpen={() => setLb(i)} selecting={selecting} selected={sel.has(it.id)} onSelect={toggleSel} />)}
            </div>}
        <div ref={sentinel} className="h-10" />
      </div>
      {lb !== null && items && <Lightbox items={items} index={lb} onIndex={setLb} onClose={() => { setLb(null); }} />}
    </div>
  );
}
