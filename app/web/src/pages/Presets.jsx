import React, { useEffect, useState } from "react";
import { Plus, Copy, Trash2, FlaskConical, Download, Upload, Save, Loader2, Lock } from "lucide-react";
import { useStore } from "../store";
import { api } from "../api";
import { PresetCover } from "../components/PresetPicker";
import { Tip } from "../components/ui";

const WORKFLOWS = [["klein_t2i", "Фото: FLUX.3 Klein"], ["anima_t2i", "Аниме: Anima"], ["krea2_t2i", "Стили: Krea 2"], ["sdxl_t2i", "SDXL / Illustrious чекпоинт"],
  ["klein_edit", "Правка / персонаж: Klein"], ["zimage_control", "Поза: Z-Image + ControlNet"], ["h3_video", "Видео со звуком: MiniMax-H3"], ["wan22_video", "Видео: Wan 2.2"], ["image_to_3d", "3D: Pixal3D"]];
const ASSIST = [["photo", "Фото (естественный язык)"], ["art", "Иллюстрация"], ["photo18", "18+ фотостиль"], ["anime", "Аниме-теги"], ["anime18", "Аниме-теги 18+"], ["edit", "Команда правки"], ["video", "Видео"], ["video18", "Видео 18+"]];
const GROUPS = ["Фото", "Арт", "Редактирование", "Видео", "3D", "18+", "Мои"];
const TEST_PROMPT = { "Фото": "рыжая кошка на подоконнике, вечер, уют", "Арт": "маяк на скале во время шторма", "18+": "женщина 30 лет в студии, портрет", default: "уютная кофейня дождливым вечером" };

function Field({ label, children, hint }) {
  return <label className="block"><div className="flex items-center gap-1.5 mb-1"><span className="text-xs muted">{label}</span>{hint && <Tip text={hint}><span className="text-[10px] dim cursor-help">(?)</span></Tip>}</div>{children}</label>;
}

function Editor({ preset, onSaved }) {
  const [p, setP] = useState(preset);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(null);
  const { toast, jobs, loadPresets } = useStore();
  useEffect(() => setP(preset), [preset.id]);
  useEffect(() => {
    if (!testing) return;
    const j = jobs[testing];
    if (j?.state === "done" && j.items[0]) {
      api.post(`/api/presets/${p.id}/cover/${j.items[0].id}`).then(() => { toast("Обложка пресета обновлена"); loadPresets(); setTesting(null); });
    } else if (j?.state === "error") setTesting(null);
  }, [jobs, testing]);
  const set = (k, v) => setP({ ...p, [k]: v });
  const setParam = (k, v) => setP({ ...p, params: { ...(p.params || {}), [k]: v === "" ? undefined : v } });
  const setMode = (m, k, v) => setP({ ...p, [m]: { ...(p[m] || {}), [k]: v === "" ? undefined : Number(v) } });
  const loras = p.params?.loras || [];
  const save = async () => {
    setSaving(true);
    try { await api.put(`/api/presets/${p.id}`, p); toast("Пресет сохранён"); await loadPresets(); onSaved?.(p.id); } catch (e) { toast(e.message, "error"); }
    setSaving(false);
  };
  const test = async () => {
    await api.put(`/api/presets/${p.id}`, p);
    try {
      const r = await api.post("/api/generate", { preset: p.id, mode: "draft", user_text: TEST_PROMPT[p.group] || TEST_PROMPT.default, aspect: "1:1", count: 1 });
      setTesting(r[0].id); toast("Тест запущен — результат станет обложкой", "info");
    } catch (e) { toast(e.message, "error"); }
  };
  const exportFile = () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(p, null, 2)], { type: "application/json" })); a.download = `${p.id}.preset.json`; a.click(); };
  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center gap-4">
        <PresetCover p={p} className="w-20 h-20 rounded-2xl shrink-0" />
        <div className="flex-1 min-w-0"><input className="field !text-lg !font-semibold" value={p.name || ""} onChange={(e) => set("name", e.target.value)} /><div className="text-xs dim mt-1">файл presets/{p.id}.yaml</div></div>
      </div>
      <div className="flex gap-2 flex-wrap">
        <button className="btn-primary" onClick={save} disabled={saving}>{saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}Сохранить</button>
        <Tip text="Сгенерировать пример и сделать его обложкой"><button className="btn-ghost" onClick={test} disabled={!!testing}>{testing ? <Loader2 size={15} className="animate-spin" /> : <FlaskConical size={15} />}Тест</button></Tip>
        <button className="btn-ghost" onClick={async () => { const r = await api.post(`/api/presets/${p.id}/duplicate`); await loadPresets(); onSaved?.(r.id); toast("Создана копия"); }}><Copy size={15} />Дублировать</button>
        <button className="btn-ghost" onClick={exportFile}><Download size={15} />Экспорт</button>
        <button className="btn-ghost" style={{ color: "#ff6b6b" }} onClick={async () => { if (!confirm(`Удалить пресет «${p.name}»? Файл уйдёт в корзину data/trash/presets.`)) return; await api.del(`/api/presets/${p.id}`); await loadPresets(); onSaved?.(null); toast("Пресет удалён"); }}><Trash2 size={15} />Удалить</button>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <Field label="Группа"><select className="field" value={p.group} onChange={(e) => set("group", e.target.value)}>{GROUPS.map((g) => <option key={g}>{g}</option>)}</select></Field>
        <Field label="Workflow (что делает пресет)"><select className="field" value={p.workflow} onChange={(e) => set("workflow", e.target.value)}>{WORKFLOWS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}{!WORKFLOWS.find((w) => w[0] === p.workflow) && <option value={p.workflow}>{p.workflow}</option>}</select></Field>
        <Field label="Шаблон помощника" hint="Как помощник пишет промпт: теги для аниме, описание фото, движение для видео"><select className="field" value={p.assistant || "photo"} onChange={(e) => set("assistant", e.target.value)}>{ASSIST.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
        <Field label="Базовая модель (подпись)"><input className="field" value={p.base_model || ""} onChange={(e) => set("base_model", e.target.value)} /></Field>
        {p.workflow === "sdxl_t2i" && <Field label="Файл чекпоинта"><input className="field" value={p.params?.model || ""} onChange={(e) => setParam("model", e.target.value)} /></Field>}
      </div>
      <Field label="Описание"><textarea className="field" rows={2} value={p.description || ""} onChange={(e) => set("description", e.target.value)} /></Field>
      <div>
        <div className="flex items-center justify-between mb-2"><span className="text-xs muted">LoRA с весами</span><button className="btn-ghost !h-7 !text-xs" onClick={() => setParam("loras", [...loras, ["", 0.8]])}><Plus size={13} />LoRA</button></div>
        {loras.map((l, i) => <div key={i} className="flex gap-2 mb-2 items-center">
          <input className="field flex-1" value={l[0]} placeholder="файл.safetensors" onChange={(e) => setParam("loras", loras.map((x, j) => j === i ? [e.target.value, x[1]] : x))} />
          <input type="range" min="0" max="1.5" step="0.05" value={l[1]} onChange={(e) => setParam("loras", loras.map((x, j) => j === i ? [x[0], Number(e.target.value)] : x))} className="w-28" />
          <span className="w-10 text-xs text-right">{Number(l[1]).toFixed(2)}</span>
          <button className="btn-ghost !px-2" onClick={() => setParam("loras", loras.filter((_, j) => j !== i))}><Trash2 size={14} /></button></div>)}
      </div>
      <div className="grid grid-cols-2 gap-4">
        {["draft", "quality"].map((m) => <div key={m} className="rounded-2xl p-4 space-y-3" style={{ border: "1px solid var(--line)" }}>
          <div className="font-medium text-sm">{m === "draft" ? "Черновик" : "Качество"}</div>
          <Field label="Шаги (пусто = авто)"><input className="field" value={p[m]?.steps ?? ""} onChange={(e) => setMode(m, "steps", e.target.value.replace(/\D/g, ""))} /></Field>
          <Field label="Мегапиксели кадра" hint="1.0 ≈ 1024×1024"><input className="field" value={p.megapixels?.[m] ?? ""} onChange={(e) => set("megapixels", { ...(p.megapixels || {}), [m]: e.target.value === "" ? undefined : Number(e.target.value) })} /></Field>
          <Field label="Ожидаемое время, с"><input className="field" value={p.eta?.[m] ?? ""} onChange={(e) => set("eta", { ...(p.eta || {}), [m]: Number(e.target.value) || undefined })} /></Field>
        </div>)}
      </div>
      <Field label="Служебный текст в начале промпта" hint="Добавляется к каждому промпту: теги качества, триггер-слова LoRA"><input className="field" value={p.prompt_prefix || ""} onChange={(e) => set("prompt_prefix", e.target.value)} /></Field>
      <Field label="Служебный текст в конце промпта"><input className="field" value={p.prompt_suffix || ""} onChange={(e) => set("prompt_suffix", e.target.value)} /></Field>
      <Field label="Негатив по умолчанию"><textarea className="field" rows={2} value={p.negative || ""} onChange={(e) => set("negative", e.target.value)} /></Field>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!p.nsfw} onChange={(e) => set("nsfw", e.target.checked)} className="accent-[var(--color-pink)]" />Пресет 18+ (скрывается безопасным режимом, включает защиту возраста)</label>
    </div>
  );
}

export default function Presets() {
  const { presets, safeMode, toast, loadPresets } = useStore();
  const [sel, setSel] = useState(null);
  const list = presets.filter((p) => !(safeMode && p.nsfw));
  const cur = list.find((p) => p.id === sel) || list[0];
  const create = async () => { const r = await api.post("/api/presets", { name: "Мой пресет", group: "Мои", workflow: "klein_t2i", assistant: "photo", base_model: "FLUX.3 Klein", media: "image", megapixels: { draft: 1, quality: 1.5 } }); await loadPresets(); setSel(r.id); };
  const importFile = (e) => {
    const f = e.target.files[0]; if (!f) return;
    f.text().then(async (t) => { try { const p = JSON.parse(t); delete p.cover; const r = await api.post("/api/presets", p); await loadPresets(); setSel(r.id); toast("Пресет импортирован"); } catch { toast("Не удалось прочитать файл пресета", "error"); } });
  };
  const groups = [...new Set(list.map((p) => p.group))];
  return (
    <div className="h-full flex flex-col md:flex-row">
      <div className="md:w-80 shrink-0 overflow-y-auto p-4 border-r space-y-4" style={{ borderColor: "var(--line)" }}>
        <div className="flex gap-2"><button className="btn-primary flex-1" onClick={create}><Plus size={15} />Новый</button>
          <label className="btn-ghost cursor-pointer"><Upload size={15} />Импорт<input type="file" accept=".json" hidden onChange={importFile} /></label></div>
        {safeMode && <div className="text-xs dim flex items-center gap-1.5"><Lock size={12} />18+ пресеты скрыты безопасным режимом</div>}
        {groups.map((g) => <div key={g}>
          <div className="label mb-2">{g}</div>
          {list.filter((p) => p.group === g).map((p) => (
            <button key={p.id} onClick={() => setSel(p.id)} className={`w-full flex items-center gap-3 p-2 rounded-xl text-left transition ${cur?.id === p.id ? "bg-[var(--panel-2)]" : "hover:bg-[var(--panel-2)]"}`}>
              <PresetCover p={p} className="w-10 h-10 rounded-lg shrink-0" />
              <div className="min-w-0"><div className="text-sm font-medium truncate">{p.name}</div><div className="text-[11px] dim truncate">{p.hidden ? "быстрое действие · " : ""}{p.base_model}</div></div>
            </button>))}
        </div>)}
      </div>
      <div className="flex-1 overflow-y-auto p-5 md:p-8 max-w-4xl">{cur ? <Editor key={cur.id} preset={cur} onSaved={setSel} /> : null}</div>
    </div>
  );
}
