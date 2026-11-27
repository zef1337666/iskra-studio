import React, { useEffect, useRef, useState } from "react";
import { Sparkles, Wand2, Languages, Dices, Layers, Loader2, X, Zap, Gem, Plus, Trash2, Lock, Unlock, SlidersHorizontal, Undo2,
  Maximize2, Heart, Download, Film, Box, Pencil, Copy, ImagePlus, ChevronDown } from "lucide-react";
import { useStore } from "../store";
import { api, thumbUrl, fileUrl } from "../api";
import PresetPicker from "../components/PresetPicker";
import { FOCUS } from "../components/RefDrop";
import Lightbox from "../components/Lightbox";
import { ACTIONS, toggleFav } from "../components/actions";
import { Tip, fmtSec } from "../components/ui";

const ASPECTS = ["1:1", "4:5", "3:4", "2:3", "9:16", "16:9", "21:9"];
const CAMERA = [["static camera", "Статично"], ["slow camera push-in", "Наезд"], ["slow camera pull-out", "Отъезд"], ["smooth camera pan", "Панорама"], ["smooth camera orbit around the subject", "Облёт"]];
const EXAMPLES = [
  { t: "Кот-астронавт в открытом космосе, Земля на фоне", p: "photo-real" },
  { t: "Уютная кофейня дождливым вечером", p: "watercolor" },
  { t: "Аниме-девушка под дождём с прозрачным зонтом, неоновый город", p: "anime" },
];
const GROUP_SHORT = { "Редактирование": "Правка" };
const ls = { get: (k, d) => { try { return JSON.parse(localStorage.getItem("iskra_" + k)) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem("iskra_" + k, JSON.stringify(v)); } catch {} } };

// ---------------------------------------------------------------- карточка задачи в работе
function JobCard({ job, pos }) {
  const preview = useStore((s) => s.previews[job.id]);
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const pct = Math.round((job.progress || 0) * 100);
  const start = useRef(null);
  useEffect(() => { if (job.state === "running" && job.elapsed != null) start.current = Date.now() - job.elapsed * 1000; }, [job.elapsed, job.state]);
  const el = job.state === "running" && start.current ? (now - start.current) / 1000 : null;
  const stage = job.state === "queued" ? `В очереди${pos ? ` · ${pos}-я` : ""} · ≈ ${fmtSec(job.eta)}`
    : job.node === "Перезапуск движка…" ? "Движок перезапускается, повторю задачу…"
    : job.steps && pct >= 100 ? "Сохраняю результат…"
    : job.steps ? `Шаг ${job.step} из ${job.steps}`
    : (el || 0) < 3 ? "Запускаю…" : "Загружаю модель в видеокарту…";
  return (
    <div className="rounded-2xl overflow-hidden panel animate-pop relative">
      <div className="aspect-square relative" style={{ background: "var(--panel-2)" }}>
        {preview ? <img src={preview} className="w-full h-full object-cover" alt="" /> : <div className="absolute inset-0 skeleton" />}
        <div className="absolute inset-x-0 bottom-0 p-4 bg-gradient-to-t from-black/80 via-black/40 to-transparent text-white">
          <div className="text-sm font-medium mb-1">{stage}</div>
          <div className="flex justify-between text-xs opacity-80 mb-2"><span>{job.preset_name}</span>
            <span>{job.state === "running" ? `${el != null ? fmtSec(el) : ""}${job.eta != null && job.steps ? ` · осталось ≈ ${fmtSec(job.eta)}` : ""}` : ""}</span></div>
          <div className="h-1.5 rounded-full bg-white/20 overflow-hidden"><div className="h-full rounded-full transition-all duration-500" style={{ width: `${job.state === "queued" ? 0 : job.steps ? Math.max(pct, 4) : 4}%`, background: "var(--color-accent)" }} /></div>
        </div>
        <Tip text="Отменить (Esc)" className="absolute top-3 right-3"><button onClick={() => api.post(`/api/jobs/${job.id}/cancel`)} className="w-9 h-9 rounded-full bg-black/50 hover:bg-black/70 text-white flex items-center justify-center" aria-label="Отменить"><X size={16} /></button></Tip>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- карточка результата с действиями прямо на картинке
function ResultCard({ it, onOpen, onEdit, onAnimate }) {
  const [fav, setFav] = useState(it.favorite);
  const act = (id) => (e) => { e.stopPropagation(); ACTIONS.find((a) => a.id === id).run(it); };
  const Btn = ({ icon: I, label, onClick }) => <Tip text={label}><button onClick={onClick} className="w-9 h-9 rounded-xl bg-black/55 hover:bg-black/80 text-white flex items-center justify-center backdrop-blur" aria-label={label}><I size={16} /></button></Tip>;
  const ratio = it.width && it.height ? `${it.width} / ${it.height}` : "1 / 1";
  return (
    <div className="group relative rounded-2xl overflow-hidden panel animate-fade-in cursor-zoom-in" style={{ aspectRatio: ratio }} onClick={onOpen}
      draggable onDragStart={(e) => e.dataTransfer.setData("application/x-iskra-item", JSON.stringify({ id: it.id }))}>
      {it.kind === "video" ? <video src={fileUrl(it)} poster={thumbUrl(it)} muted loop playsInline className="w-full h-full object-cover" onMouseEnter={(e) => e.target.play()} onMouseLeave={(e) => e.target.pause()} />
        : it.kind === "3d" ? <model-viewer src={fileUrl(it)} auto-rotate camera-controls style={{ width: "100%", height: "100%" }} />
        : <img src={fileUrl(it)} loading="lazy" className="w-full h-full object-cover" alt="" />}
      <div className="absolute inset-0 pointer-events-none opacity-0 group-hover:opacity-100 transition bg-gradient-to-t from-black/60 via-transparent to-black/30" />
      <div className="absolute top-3 right-3 flex gap-1.5 opacity-0 group-hover:opacity-100 transition">
        <Btn icon={Heart} label="В избранное" onClick={async (e) => { e.stopPropagation(); const r = await toggleFav({ ...it, favorite: fav }); setFav(r.favorite); }} />
        <Btn icon={Download} label="Скачать" onClick={(e) => { e.stopPropagation(); const a = document.createElement("a"); a.href = fileUrl(it); a.download = ""; a.click(); }} />
      </div>
      {fav && <Heart size={18} fill="#ff5fa2" color="#ff5fa2" className="absolute top-3 left-3 drop-shadow" />}
      <div className="absolute inset-x-3 bottom-3 flex gap-1.5 flex-wrap opacity-0 group-hover:opacity-100 transition">
        {it.kind === "image" && <>
          <Btn icon={Copy} label="Ещё варианты" onClick={act("more")} />
          <Btn icon={Maximize2} label="Апскейл ×4" onClick={act("upscale")} />
          <Btn icon={Pencil} label="Редактировать командой" onClick={(e) => { e.stopPropagation(); onEdit(it); }} />
          <Btn icon={Film} label="Оживить (видео)" onClick={(e) => { e.stopPropagation(); onAnimate(it); }} />
          <Btn icon={Box} label="Сделать 3D" onClick={act("to3d")} />
        </>}
        {it.kind === "video" && <><Btn icon={Copy} label="Ещё варианты" onClick={act("more")} /><Btn icon={Sparkles} label="Сделать плавнее" onClick={act("smooth")} /></>}
        <span className="flex-1" />
        <span className="self-end text-[11px] text-white/85 bg-black/45 rounded-lg px-2 py-1">{it.preset_name} · {fmtSec(it.job_sec)}</span>
      </div>
    </div>
  );
}

export default function Create() {
  const { presets, draft, setDraft, queue, jobs, lastItems, toast, refInject, safeMode, galleryVersion, settings } = useStore();
  const p = presets.find((x) => x.id === draft.preset) || presets.find((x) => !x.hidden);
  const [refs, setRefs] = useState([]);
  const [focus, setFocus] = useState("all");
  const [strength, setStrength] = useState(0.7);
  const [original, setOriginal] = useState(null); // текст до «Улучшить»
  const [negative, setNegative] = useState("");
  const [variants, setVariants] = useState(null);
  const [panel, setPanel] = useState(false);
  const [menu, setMenu] = useState(false);
  const [seed, setSeed] = useState(""); const [seedLock, setSeedLock] = useState(false);
  const [steps, setSteps] = useState(""); const [cfg, setCfg] = useState("");
  const [loras, setLoras] = useState([]);
  const [chip, setChip] = useState(null);
  const [seconds, setSeconds] = useState(5);
  const [camera, setCamera] = useState(null);
  const [smooth, setSmooth] = useState(false);
  const [busy, setBusy] = useState(null);
  const [lb, setLb] = useState(null);
  const [character, setCharacter] = useState(null);
  const [chars, setChars] = useState([]);
  const [attest, setAttest] = useState(false);
  const [history, setHistory] = useState([]);
  const [recent, setRecent] = useState(() => ls.get("recentPresets", ["photo-real", "anime", "watercolor", "edit", "video"]));
  const ta = useRef(); const fileIn = useRef();

  useEffect(() => { api.get("/api/characters").then(setChars).catch(() => {}); }, []);
  useEffect(() => { api.get(`/api/items?limit=30&nsfw=${safeMode ? 0 : 1}`).then(setHistory).catch(() => {}); }, [galleryVersion, safeMode]);
  useEffect(() => {
    if (!refInject) return;
    if (refInject.refs) setRefs(refInject.refs);
    if (refInject.character) setCharacter(refInject.character);
    if (refInject.prompt !== undefined) { setDraft({ text: refInject.prompt }); setNegative(refInject.negative || ""); }
    if (refInject.seed) setSeed(String(refInject.seed));
    useStore.setState({ refInject: null });
    ta.current?.focus();
  }, [refInject]);
  useEffect(() => { if (p?.nsfw && safeMode) setDraft({ preset: "photo-real" }); }, [safeMode]);
  useEffect(() => { setChip(null); }, [draft.preset]);
  useEffect(() => { const el = ta.current; if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 220) + "px"; } }, [draft.text]);

  const pick = (id) => { setDraft({ preset: id }); const r = [id, ...recent.filter((x) => x !== id)].slice(0, 8); setRecent(r); ls.set("recentPresets", r); };
  const visible = presets.filter((x) => !x.hidden && !(safeMode && x.nsfw));
  const groups = [...new Set(visible.map((x) => x.group))];
  const [groupSel, setGroup] = useState(null);
  const curGroup = groupSel && groups.includes(groupSel) ? groupSel : (p?.group && groups.includes(p.group) ? p.group : groups[0]);
  const media = p?.media || "image";
  const maxRefs = p?.requires === "images2" ? 2 : p?.id === "character" ? 3 : 1;
  const needsRef = ["image", "images2", "video"].includes(p?.requires);
  const active = queue.map((q) => jobs[q.id] || q);
  const lastIds = new Set(lastItems.map((x) => x.id));
  const feed = [...lastItems, ...history.filter((x) => !lastIds.has(x.id))].filter((it) => !(safeMode && it.nsfw));
  const showAspect = (media === "image" || media === "video") && p?.workflow !== "klein_edit";

  const upload = async (files) => {
    const list = [...files].slice(0, maxRefs - refs.length);
    if (!list.length) return;
    setBusy("upload");
    try { const up = []; for (const f of list) up.push(await api.upload(f)); setRefs([...refs, ...up].slice(0, maxRefs)); } catch (e) { toast(e.message, "error"); }
    setBusy(null);
  };
  useEffect(() => {
    const onPaste = (e) => { const files = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith("image/")); if (files.length) { e.preventDefault(); upload(files); } };
    window.addEventListener("paste", onPaste); return () => window.removeEventListener("paste", onPaste);
  });
  const onDrop = async (e) => {
    e.preventDefault();
    const gal = e.dataTransfer.getData("application/x-iskra-item");
    if (gal) { try { const r = await api.post(`/api/items/${JSON.parse(gal).id}/to-input`); setRefs([...refs, r].slice(0, maxRefs)); } catch (er) { toast(er.message, "error"); } return; }
    upload(e.dataTransfer.files);
  };

  const assist = async (mode) => {
    setMenu(false);
    if (!draft.text.trim() && mode !== "surprise") { toast("Сначала напишите идею", "info"); ta.current?.focus(); return; }
    setBusy(mode); setVariants(null);
    try {
      const r = await api.post("/api/assist", { text: draft.text, preset: p.id, mode, reference: refs[0]?.name, focus, style_hint: chip?.hint,
        aspect: draft.aspect, images: refs.map((x) => x.name).filter(Boolean), seconds, camera });
      if (mode === "variants") setVariants(r.variants);
      else { setOriginal(draft.text); setDraft({ text: r.prompt }); if (r.negative) setNegative(r.negative); }
    } catch (e) { toast(e.message, "error"); }
    setBusy(null);
  };

  const body = (text) => ({
    preset: p.id, mode: draft.mode, aspect: draft.aspect, count: draft.count, user_text: original || text, character: character?.id, attest_fictional: attest,
    prompt: text + (chip ? `, ${chip.hint}` : "") + (character?.description ? `. ${character.description}` : ""), negative,
    images: refs.map((r) => r.name).filter(Boolean), focus, ref_strength: strength,
    seed: seed ? Number(seed) : undefined, seed_lock: seedLock, steps: steps ? Number(steps) : undefined, cfg: cfg ? Number(cfg) : undefined,
    loras: loras.filter((l) => l.name), ...(media === "video" ? { seconds, camera, smooth } : {}),
    ...(p.requires === "video" ? { videos: refs.map((r) => r.name), images: [] } : {}),
  });
  const create = async (textOver, presetOver) => {
    const text = (textOver ?? draft.text).trim();
    const preset = presetOver ? presets.find((x) => x.id === presetOver) : p;
    if (!preset) return;
    if (!presetOver && needsRef && refs.length < (p.requires === "images2" ? 2 : 1)) { toast(p.requires === "images2" ? "Добавьте две картинки: первый и последний кадр (кнопка +)" : "Для этого пресета нужна картинка — нажмите + или перетащите её сюда", "info"); return; }
    if (!text && preset.id !== "to-3d") { toast("Опишите, что хотите получить", "info"); ta.current?.focus(); return; }
    setBusy("create");
    try { await api.post("/api/generate", presetOver ? { ...body(text), preset: presetOver, images: [], user_text: text, prompt: text } : body(text)); setOriginal(null); }
    catch (e) { toast(e.message, "error"); }
    setBusy(null);
  };
  useEffect(() => {
    const k = (e) => {
      if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); create(); }
      if (e.key === "Escape" && lb === null) { const run = queue.find((q) => q.state === "running"); if (run) api.post(`/api/jobs/${run.id}/cancel`); setMenu(false); setPanel(false); }
    };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  });

  const toCreateWith = async (it, preset) => { try { const r = await api.post(`/api/items/${it.id}/to-input`); setRefs([r]); pick(preset); setDraft({ text: "" }); ta.current?.focus(); } catch (e) { toast(e.message, "error"); } };

  if (!p) return <div className="p-8"><div className="h-12 w-80 rounded-xl skeleton" /></div>;
  return (
    <div className="h-full flex flex-col" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
      {/* ---------- лента */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 pt-6 pb-4">
        {active.length === 0 && feed.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center animate-fade-in">
            <img src="/logo.svg" className="w-16 h-16 mb-5" alt="" />
            <h1 className="text-2xl font-bold mb-2">Здесь пока пусто — создайте первую картинку</h1>
            <p className="muted mb-6 max-w-md">Напишите идею внизу своими словами или нажмите на пример.</p>
            <div className="flex gap-2 flex-wrap justify-center">{EXAMPLES.map((e) => <button key={e.t} className="chip !h-10 !px-4" onClick={() => { setDraft({ text: e.t }); pick(e.p); create(e.t, e.p); }}><Sparkles size={14} />{e.t}</button>)}</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4 items-start max-w-[2200px] mx-auto">
            {active.map((j, i) => <JobCard key={j.id} job={j} pos={j.state === "queued" ? i + 1 : null} />)}
            {feed.map((it, i) => <ResultCard key={it.id} it={it} onOpen={() => setLb(i)} onEdit={(x) => toCreateWith(x, "edit")} onAnimate={(x) => toCreateWith(x, x.nsfw ? "video18" : "video")} />)}
          </div>
        )}
      </div>

      {/* ---------- строка ввода */}
      <div className="px-3 md:px-8 pb-3 md:pb-5 pt-2">
        <div className="max-w-6xl mx-auto">
          {variants && <div className="glass rounded-2xl p-3 mb-2 space-y-1.5 animate-pop max-h-72 overflow-y-auto">
            <div className="flex justify-between items-center px-1"><span className="label">5 вариантов — выберите</span>
              <div className="flex gap-1"><button className="btn-ghost !h-7 !text-xs" onClick={async () => { for (const v of variants) await create(v.prompt); setVariants(null); }}>Создать все</button>
                <button className="btn-ghost !h-7 !px-2" onClick={() => setVariants(null)}><X size={13} /></button></div></div>
            {variants.map((v, i) => <button key={i} onClick={() => { setOriginal(draft.text); setDraft({ text: v.prompt }); setVariants(null); }} className="w-full text-left text-xs p-2.5 rounded-xl hover:bg-[var(--panel-2)] muted leading-relaxed line-clamp-3">{v.prompt}</button>)}
          </div>}
          {panel && <div className="glass rounded-2xl p-4 mb-2 space-y-3.5 animate-pop max-h-[50vh] overflow-y-auto text-sm">
            {p.chips && <div><div className="label mb-1.5">Фотостиль</div><div className="flex gap-1.5 flex-wrap">{p.chips.map((c) => <button key={c.label} className={`chip !h-7 !text-xs ${chip?.label === c.label ? "on" : ""}`} onClick={() => setChip(chip?.label === c.label ? null : c)}>{c.label}</button>)}</div></div>}
            {refs.length > 0 && !needsRef && <div><div className="label mb-1.5">Что взять с картинки</div><div className="flex gap-1.5 flex-wrap">{FOCUS.map((f) => <button key={f.id} className={`chip !h-7 !text-xs ${focus === f.id ? "on" : ""}`} onClick={() => setFocus(f.id)}>{f.label}</button>)}</div>
              {false && <div className="flex items-center gap-3 mt-2 muted"><span className="w-28">Сила влияния</span><input type="range" min="0" max="1" step="0.05" value={strength} onChange={(e) => setStrength(Number(e.target.value))} className="flex-1" /><span className="w-10 text-right">{Math.round(strength * 100)}%</span></div>}</div>}
            {media === "video" && <div className="space-y-2">
              <div className="flex items-center gap-3"><span className="label w-28">Длительность</span><input type="range" min="3" max="8" value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} className="flex-1" /><span className="w-10 text-right">{seconds} с</span></div>
              <div className="flex gap-1.5 flex-wrap"><span className="label self-center w-28">Камера</span>{CAMERA.map(([v, l]) => <button key={v} className={`chip !h-7 !text-xs ${camera === v ? "on" : ""}`} onClick={() => setCamera(camera === v ? null : v)}>{l}</button>)}</div>
              {p.workflow === "wan22_video" && <label className="flex items-center gap-2 muted cursor-pointer"><input type="checkbox" checked={smooth} onChange={(e) => setSmooth(e.target.checked)} />Сделать плавнее (удвоить кадры)</label>}
            </div>}
            {(!p.nsfw || p.workflow === "krea2_identity") && media === "image" && chars.length > 0 && <div className="flex items-center gap-2"><span className="label w-28">Персонаж</span>
              <select className="field !py-1.5" value={character?.id || ""} onChange={(e) => { const c = chars.find((x) => x.id === Number(e.target.value)) || null; setCharacter(c); if (c) { setRefs(c.refs); if (!p.nsfw) pick("character"); } else setRefs([]); }}>
                <option value="">— без персонажа —</option>{chars.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>}
            <textarea className="field !text-xs" rows={2} value={negative} onChange={(e) => setNegative(e.target.value)} placeholder="Негатив: чего не должно быть (для моделей, которые его понимают)" />
            <div className="grid grid-cols-3 gap-2">
              <div className="flex gap-1"><input className="field !py-1.5" value={seed} onChange={(e) => setSeed(e.target.value.replace(/\D/g, ""))} placeholder="seed" />
                <Tip text={seedLock ? "Seed закреплён" : "Закрепить seed"}><button className="btn-ghost !px-2" onClick={() => setSeedLock(!seedLock)}>{seedLock ? <Lock size={14} /> : <Unlock size={14} />}</button></Tip></div>
              <input className="field !py-1.5" value={steps} onChange={(e) => setSteps(e.target.value.replace(/\D/g, ""))} placeholder="шаги (авто)" />
              <input className="field !py-1.5" value={cfg} onChange={(e) => setCfg(e.target.value.replace(/[^\d.]/g, ""))} placeholder="CFG (авто)" />
            </div>
            <div className="space-y-1.5">
              {loras.map((l, i) => <div key={i} className="flex gap-2"><input className="field !py-1.5 flex-1" value={l.name} placeholder="файл LoRA" onChange={(e) => setLoras(loras.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
                <input className="field !py-1.5 !w-16" value={l.weight} onChange={(e) => setLoras(loras.map((x, j) => j === i ? { ...x, weight: e.target.value } : x))} />
                <button className="btn-ghost !px-2" onClick={() => setLoras(loras.filter((_, j) => j !== i))}><Trash2 size={14} /></button></div>)}
              <button className="btn-ghost !h-7 !text-xs" onClick={() => setLoras([...loras, { name: "", weight: 0.8 }])}><Plus size={13} />LoRA</button>
            </div>
          </div>}

          <div className="glass rounded-3xl p-2 shadow-2xl">
            {/* пресеты: вкладки групп + пресеты выбранной группы — всё всегда видно */}
            <div className="flex items-center gap-1 px-1 pt-1 flex-wrap">
              {groups.map((g) => <button key={g} onClick={() => { setGroup(g); if (p.group !== g) { const inG = visible.filter((x) => x.group === g); const last = recent.map((id) => inG.find((x) => x.id === id)).find(Boolean); if (last || inG[0]) pick((last || inG[0]).id); } }} className={`h-7 px-2.5 rounded-lg text-xs font-medium transition ${g === curGroup ? "text-[var(--text)] bg-[var(--panel-2)]" : "dim hover:text-[var(--text)]"}`}
                style={g === "18+" && g === curGroup ? { color: "var(--color-pink)" } : {}}>{GROUP_SHORT[g] || g}</button>)}
            </div>
            <div className="flex gap-1.5 flex-wrap px-1 pt-1.5 pb-2">
              {visible.filter((x) => x.group === curGroup).map((x) => <Tip key={x.id} text={x.description}><button onClick={() => pick(x.id)} className={`chip !h-8 ${x.id === p.id ? "on" : ""}`}
                style={x.nsfw && x.id === p.id ? { background: "var(--color-pink)", borderColor: "var(--color-pink)" } : {}}>{x.name}</button></Tip>)}
            </div>
            {/* референсы */}
            {refs.length > 0 && <div className="flex gap-2 px-2 pb-2">{refs.map((r, i) => (
              <div key={i} className="relative w-14 h-14 rounded-xl overflow-hidden" style={{ border: "1px solid var(--line)" }}>
                {p.requires === "video" ? <video src={r.url} className="w-full h-full object-cover" muted /> : <img src={r.url} className="w-full h-full object-cover" alt="" />}
                {r.ai && <span className="absolute bottom-0.5 left-0.5 text-[9px] px-1 rounded bg-black/70 text-white">ИИ</span>}
                <button onClick={() => setRefs(refs.filter((_, j) => j !== i))} className="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-black/60 text-white flex items-center justify-center" aria-label="Убрать"><X size={11} /></button>
              </div>))}
              {!needsRef && (p.ref_workflow || p.params?.img2img) && <div className="flex items-center gap-2 text-xs muted self-center min-w-56">
                <Tip text="Насколько результат держится за картинку: меньше — свободнее, больше — ближе к исходнику"><span>Похожесть</span></Tip>
                <input type="range" min="0.1" max="0.95" step="0.05" value={strength} onChange={(e) => setStrength(Number(e.target.value))} className="flex-1" />
                <span className="w-9 text-right">{Math.round(strength * 100)}%</span></div>}
              {p.nsfw && (p.workflow === "krea2_identity" || p.params?.img2img) && refs.some((r) => r.name?.startsWith("up_") && !r.ai) &&
                <span className="text-xs self-center max-w-md" style={{ color: "var(--color-pink)" }}>
                  {refs.some((r) => r.bare) ? "В файле нет метаданных (переслан через мессенджер или это скриншот) — метка ИИ стёрта. Скачайте оригинал кнопкой «Скачать» в сервисе." : "Нет метки «создано ИИ» — для переноса не подойдёт. Возьмите оригинал из сервиса или генерацию из галереи."}</span>}
              {p.nsfw && !(p.workflow === "krea2_identity" || p.params?.img2img) && refs.some((r) => r.name?.startsWith("up_") && !r.ai) && !settings?.uploads_attested &&
                <label className="flex gap-2 items-start text-xs cursor-pointer max-w-md self-center"><input type="checkbox" checked={attest} onChange={async (e) => { setAttest(e.target.checked); if (e.target.checked) useStore.setState({ settings: await api.put("/api/settings", { uploads_attested: true }) }); }} className="mt-0.5" />
                  <span>Подтверждаю: на картинке вымышленный взрослый персонаж, созданный ИИ (спрошу один раз)</span></label>}
            </div>}
            {/* ввод */}
            <div className="flex flex-wrap sm:flex-nowrap items-end gap-2 px-1">
              <Tip text={needsRef ? "Добавить исходную картинку (или Ctrl+V / перетащить)" : "Картинка-референс (или Ctrl+V / перетащить)"}>
                <button className="w-10 h-10 shrink-0 rounded-xl flex items-center justify-center muted hover:text-[var(--text)] hover:bg-[var(--panel-2)]" onClick={() => fileIn.current.click()} aria-label="Добавить картинку">
                  {busy === "upload" ? <Loader2 size={18} className="animate-spin" /> : <ImagePlus size={19} />}</button></Tip>
              <textarea ref={ta} value={draft.text} rows={1} onChange={(e) => setDraft({ text: e.target.value })}
                placeholder={p.workflow === "klein_edit" ? "Что изменить? «сделай ночь», «добавь очки»…" : media === "video" ? "Что происходит в видео?" : "Опишите, что хотите увидеть…"}
                className="order-first sm:order-none basis-full sm:basis-auto flex-1 bg-transparent resize-none outline-none py-2.5 px-1 sm:px-0 text-[15px] leading-relaxed max-h-56" style={{ color: "var(--text)" }} />
              {original !== null && <Tip text="Вернуть мой текст"><button className="w-10 h-10 shrink-0 rounded-xl flex items-center justify-center muted hover:bg-[var(--panel-2)]" onClick={() => { setDraft({ text: original }); setOriginal(null); }}><Undo2 size={17} /></button></Tip>}
              <div className="relative shrink-0 flex h-10 rounded-xl" style={{ border: "1px solid var(--line)" }}>
                <Tip text="Улучшить промпт по официальным рекомендациям модели"><button className="h-full px-3 rounded-l-xl flex items-center gap-1.5 text-sm muted hover:text-[var(--text)] hover:bg-[var(--panel-2)]" onClick={() => assist("improve")} disabled={!!busy && busy !== "upload"}>
                  {["improve", "exact", "surprise", "variants"].includes(busy) ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}<span className="hidden sm:inline">Улучшить</span></button></Tip>
                <Tip text="Другие режимы: точно как написал, удиви меня, 5 вариантов"><button className="h-full px-2 rounded-r-xl muted hover:text-[var(--text)] hover:bg-[var(--panel-2)]" style={{ borderLeft: "1px solid var(--line)" }} onClick={() => setMenu(!menu)} aria-label="Другие режимы"><ChevronDown size={15} /></button></Tip>
                {menu && <div className="absolute bottom-12 right-0 panel rounded-2xl p-1.5 w-56 shadow-2xl animate-pop z-20">
                  {[["exact", "Точно как написал", Languages], ["surprise", "Удиви меня", Dices], ["variants", "5 вариантов", Layers]].map(([m, l, I]) =>
                    <button key={m} className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm hover:bg-[var(--panel-2)]" onClick={() => assist(m)}><I size={15} />{l}</button>)}
                </div>}
              </div>
              <Tip text="Настройки: фотостиль, видео, seed, LoRA…"><button className={`w-10 h-10 shrink-0 rounded-xl flex items-center justify-center hover:bg-[var(--panel-2)] ${panel ? "text-[var(--color-accent-hi)]" : "muted"}`} onClick={() => setPanel(!panel)} aria-label="Настройки"><SlidersHorizontal size={17} /></button></Tip>
              <button className="btn-primary !h-10 !rounded-xl !px-5 shrink-0 ml-auto sm:ml-0" onClick={() => create()} disabled={busy === "create"}>{busy === "create" ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}<span className="hidden sm:inline">Создать</span></button>
            </div>
            {/* режим, пропорции, количество */}
            <div className="flex items-center gap-2 px-2 pt-2 pb-1 text-xs flex-wrap">
              <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid var(--line)" }}>
                {[["draft", "Черновик", Zap], ["quality", "Качество", Gem]].map(([m, l, I]) => <button key={m} onClick={() => setDraft({ mode: m })} className={`h-7 px-2.5 flex items-center gap-1 ${draft.mode === m ? "bg-[var(--color-accent)] text-white" : "muted hover:bg-[var(--panel-2)]"}`}><I size={12} />{l}{p.eta?.[m] ? <span className="opacity-70">~{fmtSec(p.eta[m])}</span> : null}</button>)}
              </div>
              {showAspect && <select className="field !w-auto !py-1 !text-xs" value={draft.aspect} onChange={(e) => setDraft({ aspect: e.target.value })}>{ASPECTS.map((a) => <option key={a}>{a}</option>)}</select>}
              {media === "image" && <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid var(--line)" }}>{[1, 2, 3, 4].map((n) => <button key={n} onClick={() => setDraft({ count: n })} className={`w-7 h-7 ${draft.count === n ? "bg-[var(--color-accent)] text-white" : "muted hover:bg-[var(--panel-2)]"}`}>{n}</button>)}</div>}
              {media === "video" && <span className="muted">{seconds} с{camera ? ` · ${CAMERA.find((c) => c[0] === camera)?.[1]}` : ""}</span>}
              <span className="flex-1" />
              <span className="dim hidden md:inline">{p.base_model} · Ctrl+Enter</span>
            </div>
          </div>
        </div>
      </div>
      <input ref={fileIn} type="file" hidden multiple={maxRefs > 1} accept={p.requires === "video" ? "video/*" : "image/*"} onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
      {lb !== null && <Lightbox items={feed} index={lb} onIndex={setLb} onClose={() => setLb(null)} />}
    </div>
  );
}
