import React, { useEffect, useMemo, useRef, useState } from "react";
import { Sparkles, Wand2, Languages, Dices, Layers, ChevronDown, Lock, Unlock, Loader2, X, Zap, Gem, Plus, Trash2, Clock, Rocket } from "lucide-react";
import { useStore } from "../store";
import { api, thumbUrl } from "../api";
import PresetPicker from "../components/PresetPicker";
import RefDrop, { FocusChips } from "../components/RefDrop";
import Lightbox from "../components/Lightbox";
import { Tip, Segmented, fmtSec } from "../components/ui";

const ASPECTS = ["1:1", "4:5", "3:4", "2:3", "9:16", "16:9", "21:9"];
const CAMERA = [["static", "Статично"], ["push_in", "Наезд"], ["pull_out", "Отъезд"], ["pan", "Панорама"], ["orbit", "Облёт"]];
const EXAMPLES = [
  { t: "Кот-астронавт в открытом космосе, Земля на фоне", p: "photo-real" },
  { t: "Уютная кофейня дождливым вечером, тёплый свет ламп", p: "watercolor" },
  { t: "Аниме-девушка под дождём с прозрачным зонтом, неоновый город", p: "anime" },
];

function AspectIcon({ a, on, onClick }) {
  const [w, h] = a.split(":").map(Number);
  const k = 18 / Math.max(w, h);
  return (
    <Tip text={`Пропорции ${a}`}>
      <button onClick={onClick} className={`flex flex-col items-center gap-1 px-1.5 py-1.5 rounded-lg transition ${on ? "bg-[var(--color-accent)] text-white" : "muted hover:bg-[var(--panel-2)]"}`}>
        <span className="flex items-center justify-center w-5 h-5"><span className="rounded-[3px] border-2 border-current" style={{ width: w * k, height: h * k }} /></span>
        <span className="text-[10px] leading-none">{a}</span>
      </button>
    </Tip>
  );
}

function Section({ title, open, setOpen, children, badge }) {
  return (
    <div className="rounded-2xl" style={{ border: "1px solid var(--line)" }}>
      <button className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium" onClick={() => setOpen(!open)}>
        <span className="flex items-center gap-2">{title}{badge}</span><ChevronDown size={16} className={`dim transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="px-4 pb-4 space-y-3 animate-fade-in">{children}</div>}
    </div>
  );
}

function JobCard({ job }) {
  const preview = useStore((s) => s.previews[job.id]);
  const pct = Math.round((job.progress || 0) * 100);
  return (
    <div className="rounded-2xl overflow-hidden panel animate-pop relative">
      <div className="aspect-square relative flex items-center justify-center" style={{ background: "var(--panel-2)" }}>
        {preview ? <img src={preview} className="w-full h-full object-cover" alt="" /> : <div className="absolute inset-0 skeleton" />}
        <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/70 to-transparent text-white">
          <div className="flex justify-between text-xs mb-1.5">
            <span>{job.state === "queued" ? "В очереди" : job.node === "Перезапуск движка…" ? job.node : job.steps ? `Шаг ${job.step} из ${job.steps}` : "Загрузка модели…"}</span>
            <span>{job.state === "running" && job.eta != null ? `≈ ${fmtSec(job.eta)}` : ""}</span>
          </div>
          <div className="h-1.5 rounded-full bg-white/20 overflow-hidden"><div className="h-full rounded-full transition-all duration-500" style={{ width: `${job.state === "queued" ? 0 : Math.max(pct, 3)}%`, background: "var(--color-accent)" }} /></div>
        </div>
        <Tip text="Отменить (Esc)" className="absolute top-2 right-2"><button onClick={() => api.post(`/api/jobs/${job.id}/cancel`)} className="w-8 h-8 rounded-full bg-black/50 hover:bg-black/70 text-white flex items-center justify-center" aria-label="Отменить"><X size={15} /></button></Tip>
      </div>
      <div className="px-3 py-2 text-xs muted truncate">{job.preset_name} · {job.title}</div>
    </div>
  );
}

export default function Create() {
  const { presets, draft, setDraft, queue, jobs, lastItems, toast, refInject, safeMode } = useStore();
  const p = presets.find((x) => x.id === draft.preset) || presets.find((x) => !x.hidden);
  const [refs, setRefs] = useState([]);
  const [focus, setFocus] = useState("all");
  const [strength, setStrength] = useState(0.7);
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState("");
  const [explain, setExplain] = useState("");
  const [variants, setVariants] = useState(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showFine, setShowFine] = useState(false);
  const [seed, setSeed] = useState("");
  const [seedLock, setSeedLock] = useState(false);
  const [steps, setSteps] = useState("");
  const [cfg, setCfg] = useState("");
  const [loras, setLoras] = useState([]);
  const [chip, setChip] = useState(null);
  const [seconds, setSeconds] = useState(5);
  const [camera, setCamera] = useState(null);
  const [smooth, setSmooth] = useState(false);
  const [busy, setBusy] = useState(null);
  const [lb, setLb] = useState(null);
  const [character, setCharacter] = useState(null);
  const [attest, setAttest] = useState(false);
  const [chars, setChars] = useState([]);
  const ta = useRef();
  useEffect(() => { api.get("/api/characters").then(setChars).catch(() => {}); }, []);
  const pickChar = (c) => { setCharacter(c); if (c) { setRefs(c.refs); setDraft({ preset: "character" }); } else setRefs([]); };

  useEffect(() => {
    if (!refInject) return;
    if (refInject.refs) setRefs(refInject.refs);
    if (refInject.character) setCharacter(refInject.character);
    if (refInject.prompt !== undefined) { setPrompt(refInject.prompt); setNegative(refInject.negative || ""); setShowPrompt(true); }
    if (refInject.seed) { setSeed(String(refInject.seed)); }
    useStore.setState({ refInject: null });
    ta.current?.focus();
  }, [refInject]);
  useEffect(() => { if (p?.nsfw && safeMode) setDraft({ preset: "photo-real" }); }, [safeMode]);
  useEffect(() => { setChip(null); }, [draft.preset]);

  const media = p?.media || "image";
  const maxRefs = p?.requires === "images2" ? 2 : p?.id === "character" ? 3 : 1;
  const needsRef = ["image", "images2", "video"].includes(p?.requires);
  const active = queue.map((q) => jobs[q.id] || q);
  const eta = p?.eta?.[draft.mode];

  const assist = async (mode) => {
    if (!draft.text.trim() && mode !== "surprise" && !refs.length) { toast("Сначала опишите идею в поле выше", "info"); ta.current?.focus(); return; }
    setBusy(mode); setVariants(null);
    try {
      const r = await api.post("/api/assist", { text: draft.text, preset: p.id, mode, reference: refs[0]?.name, focus, style_hint: chip?.hint,
        aspect: draft.aspect, images: refs.map((x) => x.name).filter(Boolean), seconds, camera });
      if (mode === "variants") { setVariants(r.variants); }
      else { setPrompt(r.prompt); setNegative(r.negative || ""); setExplain(r.explanation_ru || ""); setShowPrompt(true); }
    } catch (e) { toast(e.message, "error"); }
    setBusy(null);
  };

  const body = (overPrompt) => ({
    preset: p.id, mode: draft.mode, aspect: draft.aspect, count: draft.count, user_text: draft.text, character: character?.id, attest_fictional: attest,
    prompt: (overPrompt ?? prompt) || (draft.text + (chip ? `, ${chip.hint}` : "") + (character?.description ? `. ${character.description}` : "")), negative,
    images: refs.map((r) => r.name).filter(Boolean), focus, ref_strength: strength,
    seed: seed ? Number(seed) : undefined, seed_lock: seedLock, steps: steps ? Number(steps) : undefined, cfg: cfg ? Number(cfg) : undefined,
    loras: loras.filter((l) => l.name), ...(media === "video" ? { seconds, camera, smooth } : {}),
    ...(p.requires === "video" ? { videos: refs.map((r) => r.name), images: [] } : {}),
  });

  const create = async (overPrompt, over) => {
    if (!p) return;
    if (over) { // кнопки-примеры: не ждём обновления состояния
      setBusy("create");
      try { await api.post("/api/generate", { ...body(""), preset: over.preset, user_text: over.text, prompt: over.text, images: [], aspect: draft.aspect }); } catch (e) { toast(e.message, "error"); }
      setBusy(null);
      return;
    }
    if (needsRef && refs.length < (p.requires === "images2" ? 2 : 1)) { toast(p.requires === "images2" ? "Добавьте две картинки: первый и последний кадр" : "Для этого пресета нужна картинка — добавьте её в зону референса", "info"); return; }
    if (!draft.text.trim() && !prompt.trim() && !overPrompt && !["to-3d"].includes(p.id)) { toast("Опишите, что хотите получить", "info"); ta.current?.focus(); return; }
    setBusy("create");
    try { await api.post("/api/generate", body(overPrompt)); } catch (e) { toast(e.message, "error"); }
    setBusy(null);
  };

  useEffect(() => {
    const k = (e) => {
      if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); create(); }
      if (e.key === "Escape" && !lb) { const run = queue.find((q) => q.state === "running"); if (run) api.post(`/api/jobs/${run.id}/cancel`); }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  });

  if (!p) return <div className="p-8"><div className="h-12 w-80 rounded-xl skeleton" /></div>;
  const results = lastItems.filter((it) => !(safeMode && it.nsfw));
  return (
    <div className="h-full overflow-y-auto lg:overflow-hidden flex flex-col lg:flex-row">
      {/* ---------- панель управления */}
      <section className="lg:w-[440px] xl:w-[480px] shrink-0 flex flex-col lg:min-h-0 lg:border-r" style={{ borderColor: "var(--line)" }}>
        <div className="lg:flex-1 lg:overflow-y-auto p-4 md:p-5 space-y-4">
          <PresetPicker value={p.id} onChange={(id) => setDraft({ preset: id })} />
          <div className="rounded-2xl p-1 transition focus-within:shadow-[0_0_0_3px_rgba(139,124,255,.18)]" style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}>
            <textarea ref={ta} value={draft.text} onChange={(e) => setDraft({ text: e.target.value })} rows={4}
              placeholder={p.requires === "image" && p.workflow === "klein_edit" ? "Что изменить? Например: «сделай ночь и добавь неоновые вывески»" : media === "video" ? "Что происходит в видео? Например: «кот зевает, потом смотрит в окно»" : "Опишите, что хотите. Например: «рыжая кошка на подоконнике, вечер, уют»"}
              className="w-full bg-transparent resize-none outline-none px-3 py-2.5 text-[15px] leading-relaxed" style={{ color: "var(--text)" }} />
            <div className="flex gap-1 px-1.5 pb-1.5 flex-wrap">
              {[["improve", "Улучшить", Wand2, "Помощник расширит идею: свет, камера, детали"], ["exact", "Точно как написал", Languages, "Только перевести на английский, ничего не добавлять"],
                ["surprise", "Удиви меня", Dices, "Случайная красивая идея в стиле пресета"], ["variants", "5 вариантов", Layers, "Пять разных трактовок идеи"]].map(([m, l, I, t]) => (
                <Tip key={m} text={t}><button className="btn !h-8 !px-2.5 !text-xs muted hover:text-[var(--text)] hover:bg-[var(--panel-solid)]" onClick={() => assist(m)} disabled={!!busy}>
                  {busy === m ? <Loader2 size={14} className="animate-spin" /> : <I size={14} />}{l}</button></Tip>
              ))}
            </div>
          </div>
          {p.chips && <div><div className="label mb-2">Фотостиль</div><div className="flex gap-1.5 flex-wrap">
            {p.chips.map((c) => <button key={c.label} className={`chip !h-7 !text-xs ${chip?.label === c.label ? "on" : ""}`} onClick={() => setChip(chip?.label === c.label ? null : c)}>{c.label}</button>)}</div></div>}
          {variants && <div className="space-y-2 animate-fade-in">
            <div className="flex items-center justify-between"><span className="label">5 вариантов — выберите или создайте все</span>
              <button className="btn-ghost !h-7 !text-xs" onClick={async () => { for (const v of variants) await create(v.prompt); setVariants(null); }}><Rocket size={13} />Создать все</button></div>
            {variants.map((v, i) => <button key={i} onClick={() => { setPrompt(v.prompt); setNegative(v.negative || ""); setExplain(v.explanation_ru); setVariants(null); setShowPrompt(true); }}
              className="w-full text-left text-xs p-3 rounded-xl hover:bg-[var(--panel-2)] transition muted leading-relaxed" style={{ border: "1px solid var(--line)" }}>{v.prompt}</button>)}
          </div>}
          {!p.nsfw && media === "image" && chars.length > 0 && <div className="flex items-center gap-2">
            <span className="label shrink-0">Персонаж</span>
            <select className="field !py-1.5" value={character?.id || ""} onChange={(e) => pickChar(chars.find((c) => c.id === Number(e.target.value)) || null)}>
              <option value="">— без персонажа —</option>{chars.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>}
          <RefDrop refs={refs} setRefs={setRefs} max={maxRefs} accept={p.requires === "video" ? "video" : "image"}
            label={p.requires === "images2" ? "Первый и последний кадр" : p.id === "character" ? "Референсы персонажа (1–3)" : needsRef ? "Исходная картинка" : "Картинка-референс (необязательно)"} />
          {p.nsfw && refs.some((r) => r.name?.startsWith("up_")) && !useStore.getState().settings?.uploads_attested && <div className="rounded-xl p-3 text-xs space-y-2 animate-fade-in" style={{ background: "rgba(255,95,162,.08)", border: "1px solid rgba(255,95,162,.3)" }}>
            {refs.filter((r) => r.name?.startsWith("up_")).every((r) => r.ai)
              ? <div style={{ color: "#3ecf8e" }}>В файле найдена метка «создано ИИ» — картинку можно использовать.</div>
              : <label className="flex gap-2 items-start cursor-pointer"><input type="checkbox" checked={attest} onChange={async (e) => { setAttest(e.target.checked); if (e.target.checked) useStore.setState({ settings: await api.put("/api/settings", { uploads_attested: true }) }); }} className="mt-0.5 accent-[var(--color-pink)]" />
                  <span>Подтверждаю: на картинке <b>вымышленный взрослый персонаж, созданный ИИ</b>, а не фото реального человека. Отмечается один раз — больше спрашивать не буду.</span></label>}
          </div>}
          {refs.length > 0 && !needsRef && <div className="space-y-2.5 animate-fade-in">
            <div className="label">Что взять с картинки</div>
            <FocusChips value={focus} onChange={setFocus} />
            {p.ref_workflow && <div className="flex items-center gap-3 text-xs muted"><span className="w-28 shrink-0">Сила влияния</span>
              <input type="range" min="0" max="1" step="0.05" value={strength} onChange={(e) => setStrength(Number(e.target.value))} className="flex-1" />
              <Tip text="Меньше 50% — берём только описание картинки; больше — сама картинка идёт в модель"><span className="w-9 text-right">{Math.round(strength * 100)}%</span></Tip></div>}
          </div>}
          {media === "video" && <div className="space-y-3">
            <div className="flex items-center gap-3 text-sm"><span className="label w-28">Длительность</span><input type="range" min="3" max="8" step="1" value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} className="flex-1" /><span className="w-10 text-right">{seconds} с</span></div>
            <div><div className="label mb-2">Камера</div><div className="flex gap-1.5 flex-wrap">{CAMERA.map(([v, l]) => <button key={v} className={`chip !h-7 !text-xs ${camera === v ? "on" : ""}`} onClick={() => setCamera(camera === v ? null : v)}>{l}</button>)}</div></div>
            {p.workflow === "wan22_video" && <label className="flex items-center gap-2 text-sm muted cursor-pointer"><input type="checkbox" checked={smooth} onChange={(e) => setSmooth(e.target.checked)} className="accent-[var(--color-accent)]" />Сделать плавнее (удвоить кадры)</label>}
          </div>}
          <Section title="Промпт" open={showPrompt} setOpen={setShowPrompt} badge={prompt && <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)]" />}>
            {explain && <div className="text-xs leading-relaxed p-3 rounded-xl" style={{ background: "rgba(139,124,255,.1)", color: "var(--muted)" }}><b style={{ color: "var(--color-accent-hi)" }}>Что я добавил: </b>{explain}</div>}
            <textarea className="field text-xs leading-relaxed" rows={5} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Здесь появится промпт от помощника. Можно написать свой (на английском)." />
            <textarea className="field text-xs" rows={2} value={negative} onChange={(e) => setNegative(e.target.value)} placeholder="Негатив: чего не должно быть (для моделей, которые его поддерживают)" />
            {prompt && <button className="text-xs dim hover:text-[var(--text)]" onClick={() => { setPrompt(""); setNegative(""); setExplain(""); }}>Очистить промпт — использовать мой текст</button>}
          </Section>
          <Section title="Тонкие настройки" open={showFine} setOpen={setShowFine}>
            <div className="flex items-center gap-2">
              <span className="text-sm muted w-20">Seed</span>
              <input className="field !py-1.5" value={seed} onChange={(e) => setSeed(e.target.value.replace(/\D/g, ""))} placeholder="случайный" />
              <Tip text={seedLock ? "Seed закреплён: каждый раз тот же результат" : "Закрепить seed"}><button className="btn-ghost !px-2.5" onClick={() => setSeedLock(!seedLock)}>{seedLock ? <Lock size={15} /> : <Unlock size={15} />}</button></Tip>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-sm muted">Шаги<input className="field !py-1.5 mt-1" value={steps} onChange={(e) => setSteps(e.target.value.replace(/\D/g, ""))} placeholder="авто" /></label>
              <label className="text-sm muted">CFG<input className="field !py-1.5 mt-1" value={cfg} onChange={(e) => setCfg(e.target.value.replace(/[^\d.]/g, ""))} placeholder="авто" /></label>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between"><span className="text-sm muted">LoRA</span><button className="btn-ghost !h-7 !text-xs" onClick={() => setLoras([...loras, { name: "", weight: 0.8 }])}><Plus size={13} />Добавить</button></div>
              {loras.map((l, i) => <div key={i} className="flex gap-2 items-center">
                <input className="field !py-1.5 flex-1" value={l.name} placeholder="имя файла LoRA" onChange={(e) => setLoras(loras.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
                <input className="field !py-1.5 !w-16" value={l.weight} onChange={(e) => setLoras(loras.map((x, j) => j === i ? { ...x, weight: e.target.value } : x))} />
                <button className="btn-ghost !px-2" onClick={() => setLoras(loras.filter((_, j) => j !== i))} aria-label="Убрать"><Trash2 size={14} /></button></div>)}
              <div className="text-[11px] dim">LoRA пресета подключаются сами. Выбор из списка установленных — в разделе «Модели».</div>
            </div>
          </Section>
        </div>
        {/* ---------- нижняя панель */}
        <div className="p-4 md:p-5 space-y-3 border-t glass" style={{ borderColor: "var(--line)" }}>
          <Segmented value={draft.mode} onChange={(mode) => setDraft({ mode })} options={[
            { value: "draft", label: "Черновик", icon: <Zap size={14} />, sub: p.eta ? `~${fmtSec(p.eta.draft)}` : "", tip: "Максимально быстро — чтобы подобрать идею" },
            { value: "quality", label: "Качество", icon: <Gem size={14} />, sub: p.eta ? `~${fmtSec(p.eta.quality)}` : "", tip: "Лучший результат, дольше" }]} />
          {(media === "image" || media === "video") && p.workflow !== "klein_edit" && !["upscale", "nobg", "detail"].includes(p.id) && (
            <div className="flex items-center gap-1 justify-between">
              <div className="flex gap-0.5 flex-wrap">{ASPECTS.map((a) => <AspectIcon key={a} a={a} on={draft.aspect === a} onClick={() => setDraft({ aspect: a })} />)}</div>
              {media === "image" && <Tip text="Сколько вариантов сделать"><div className="flex rounded-lg overflow-hidden shrink-0" style={{ border: "1px solid var(--line)" }}>
                {[1, 2, 3, 4].map((n) => <button key={n} onClick={() => setDraft({ count: n })} className={`w-7 h-7 text-xs ${draft.count === n ? "bg-[var(--color-accent)] text-white" : "muted hover:bg-[var(--panel-2)]"}`}>{n}</button>)}</div></Tip>}
            </div>)}
          <button className="btn-primary w-full !h-12 !text-base !rounded-2xl" onClick={() => create()} disabled={busy === "create"}>
            {busy === "create" ? <Loader2 className="animate-spin" size={18} /> : <Sparkles size={18} />}Создать<span className="text-xs opacity-70 font-normal ml-1">Ctrl+Enter</span>
          </button>
        </div>
      </section>
      {/* ---------- результаты */}
      <section className="lg:flex-1 lg:min-h-0 lg:overflow-y-auto p-4 md:p-6 min-h-[50vh]">
        {active.length === 0 && results.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center animate-fade-in">
            <img src="/logo.svg" className="w-16 h-16 mb-5 opacity-90" alt="" />
            <h1 className="text-2xl font-bold mb-2">Здесь пока пусто — создайте первую картинку</h1>
            <p className="muted mb-6 max-w-md">Опишите идею слева своими словами или попробуйте пример в один клик.</p>
            <div className="flex gap-2 flex-wrap justify-center">
              {EXAMPLES.map((e) => <button key={e.t} className="chip !h-10 !px-4" onClick={() => { setDraft({ text: e.t, preset: e.p }); create(null, { text: e.t, preset: e.p }); }}><Sparkles size={14} />{e.t.split(",")[0].split(" в ")[0]}</button>)}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {active.length > 0 && <div>
              <div className="flex items-center gap-2 mb-3"><Clock size={15} className="dim" /><span className="label">В работе · {active.length}</span></div>
              <div className="grid grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3">{active.map((j) => <JobCard key={j.id} job={j} />)}</div>
            </div>}
            {results.length > 0 && <div>
              <div className="label mb-3">Последние результаты</div>
              <div className="grid grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3">
                {results.map((it, i) => (
                  <button key={it.id} onClick={() => setLb(i)} draggable onDragStart={(e) => e.dataTransfer.setData("application/x-iskra-item", JSON.stringify({ id: it.id }))}
                    className="group relative rounded-2xl overflow-hidden panel animate-pop text-left" style={{ animationDelay: `${i * 40}ms` }}>
                    {it.kind === "video" ? <video src={`/files/output/${encodeURI(it.path)}`} poster={thumbUrl(it)} muted loop playsInline className="w-full aspect-square object-cover" onMouseEnter={(e) => e.target.play()} onMouseLeave={(e) => e.target.pause()} />
                      : <img src={thumbUrl(it) || `/files/output/${encodeURI(it.path)}`} className="w-full aspect-square object-cover transition group-hover:scale-[1.03]" alt="" />}
                    <div className="absolute inset-x-0 bottom-0 p-2.5 text-xs text-white bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition truncate">{it.preset_name} · {it.job_sec} с</div>
                  </button>))}
              </div>
            </div>}
          </div>
        )}
      </section>
      {lb !== null && <Lightbox items={results} index={lb} onIndex={setLb} onClose={() => setLb(null)} />}
    </div>
  );
}
