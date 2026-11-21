import React, { useEffect, useState } from "react";
import { UserRound, Plus, Trash2, Sparkles, Save, Info, GraduationCap, X } from "lucide-react";
import { useStore } from "../store";
import { api } from "../api";
import RefDrop from "../components/RefDrop";
import { Empty, Modal } from "../components/ui";

function TrainPanel({ open, setOpen, preset }) {
  const { toast, loadPresets } = useStore();
  const [name, setName] = useState(preset?.name || "");
  const [refs, setRefs] = useState(preset?.refs || []);
  const [steps, setSteps] = useState(1000);
  const [st, setSt] = useState(null);
  useEffect(() => { if (preset) { setName(preset.name); setRefs(preset.refs || []); } }, [preset]);
  useEffect(() => {
    const f = () => api.get("/api/train/status").then((s) => { setSt(s); if (s.train?.state === "done" && s.phase === "finished") loadPresets(); }).catch(() => {});
    f(); const t = setInterval(f, 3000); return () => clearInterval(t);
  }, []);
  const running = st && ["captions", "stopping_engine", "training"].includes(st.phase);
  const start = async () => {
    try { const r = await api.post("/api/train/start", { name, images: refs.map((r) => r.name), steps, character_id: preset?.id }); toast(`Обучение «${r.name}» запущено (слово-триггер ${r.trigger})`, "info"); setOpen(false); }
    catch (e) { toast(e.message, "error"); }
  };
  const tr = st?.train;
  const phaseRu = { captions: `Подписываю картинки: ${st?.captioned}/${st?.total}`, stopping_engine: "Освобождаю видеокарту…",
    training: tr?.state === "training" ? `Обучение: шаг ${tr.step} из ${tr.steps}` : "Загружаю модель и готовлю данные…" };
  return (
    <>
      {(running || (st?.phase === "finished" && tr)) && <div className="panel rounded-2xl p-4 mb-6 animate-fade-in">
        <div className="flex items-center gap-3 mb-2"><GraduationCap size={18} /><div className="font-semibold flex-1">LoRA «{st.name}»</div>
          {running && <button className="btn-ghost !h-8" onClick={() => api.post("/api/train/cancel")}><X size={14} />Остановить</button>}</div>
        {running ? <>
          <div className="text-sm muted mb-2">{phaseRu[st.phase]}{tr?.eta ? ` · осталось ≈ ${Math.round(tr.eta / 60)} мин` : ""}</div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--panel-2)" }}><div className="h-full rounded-full transition-all" style={{ width: `${st.phase === "captions" ? (st.captioned / st.total) * 10 : tr?.steps ? 10 + (tr.step / tr.steps) * 90 : 10}%`, background: "var(--color-accent)" }} /></div>
          <div className="text-xs dim mt-2">Пока идёт обучение, генерация недоступна — видеокарта занята. Можно закрыть этот раздел, прогресс сохранится.</div>
        </> : tr.state === "done" ? <div className="text-sm" style={{ color: "#3ecf8e" }}>Готово! Создан пресет «Персонаж: {st.name}» в группе «Мои». Пишите сцену — персонаж будет узнаваем.</div>
          : <div className="text-sm" style={{ color: "#ff6b6b" }}>{st.error || tr.error || "Обучение остановлено."}</div>}
      </div>}
      <Modal open={open} onClose={() => setOpen(false)} title="Обучить LoRA персонажа">
        <div className="px-6 pb-6 space-y-4">
          <div className="text-sm muted">Своя LoRA делает персонажа узнаваемым точнее, чем референсы. Нужно 15–30 картинок одного вымышленного персонажа (или вас): разные ракурсы, свет, одежда и фон. Подписи студия сделает сама.</div>
          <label className="block"><span className="text-xs muted">Имя персонажа</span><input className="field mt-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Например: mira" /></label>
          <RefDrop refs={refs} setRefs={setRefs} max={30} label={`Картинки персонажа (${refs.length}/30, минимум 8)`} />
          <div className="flex items-center gap-3 text-sm"><span className="muted w-24">Шагов</span><input type="range" min="400" max="2000" step="100" value={steps} onChange={(e) => setSteps(Number(e.target.value))} className="flex-1" /><span className="w-40 text-right">{steps} · ≈ {Math.round((steps * 2.6) / 60 + 3)} мин</span></div>
          <div className="text-xs dim">Во время обучения (обычно 30–60 минут) генерация недоступна: видеокарта занята целиком. Когда закончится, придёт уведомление. Только вымышленные персонажи или вы сами.</div>
          <button className="btn-primary w-full" onClick={start} disabled={running || refs.length < 8 || !name}><GraduationCap size={15} />Начать обучение</button>
        </div>
      </Modal>
    </>
  );
}

export default function Characters() {
  const { toast, setDraft, setPage } = useStore();
  const [list, setList] = useState(null);
  const [edit, setEdit] = useState(null);
  const [train, setTrain] = useState(false);
  const [trainFor, setTrainFor] = useState(null);
  const load =() => api.get("/api/characters").then(setList).catch((e) => toast(e.message, "error"));
  useEffect(() => { load(); }, []);
  const save = async () => {
    try { await api.post("/api/characters", { ...edit, cover: edit.cover || null }); toast("Персонаж сохранён"); setEdit(null); load(); } catch (e) { toast(e.message, "error"); }
  };
  const use = (c) => { useStore.setState({ refInject: { refs: c.refs, character: c } }); setDraft({ preset: "character", text: "" }); setPage("create"); };
  return (
    <div className="h-full overflow-y-auto p-5 md:p-8">
      <div className="flex items-center justify-between mb-2"><h1 className="text-2xl font-bold">Персонажи</h1>
        <div className="flex gap-2"><button className="btn-ghost" onClick={() => { setTrainFor(null); setTrain(true); }}><GraduationCap size={15} />Обучить LoRA</button>
          <button className="btn-primary" onClick={() => setEdit({ name: "", description: "", refs: [] })}><Plus size={15} />Новый персонаж</button></div></div>
      <TrainPanel open={train} setOpen={setTrain} preset={trainFor} />
      <div className="flex gap-2 items-start text-sm muted mb-6 max-w-3xl"><Info size={16} className="shrink-0 mt-0.5" />
        Сохраните вымышленного персонажа (или себя) по 1–3 картинкам — и он будет узнаваем в новых сценах. В 18+ пресетах персонажи и фото людей не используются.</div>
      {list === null ? <div className="grid grid-cols-2 md:grid-cols-4 gap-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-64 rounded-2xl skeleton" />)}</div>
        : list.length === 0 ? <Empty icon={UserRound} title="Создайте первого персонажа" text="Загрузите 1–3 картинки персонажа или нажмите «Сохранить персонажа» при просмотре любой картинки."
            action={<button className="btn-primary" onClick={() => setEdit({ name: "", description: "", refs: [] })}><Plus size={15} />Новый персонаж</button>} />
        : <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">{list.map((c) => (
          <div key={c.id} className="panel rounded-2xl overflow-hidden animate-fade-in group">
            <div className="aspect-square relative" style={{ background: "var(--panel-2)" }}>
              {c.refs[0] && <img src={c.refs[0].url} className="w-full h-full object-cover" alt="" />}
              {c.refs.length > 1 && <span className="absolute bottom-2 right-2 text-[11px] px-1.5 rounded bg-black/60 text-white">{c.refs.length} фото</span>}
            </div>
            <div className="p-3"><div className="font-semibold">{c.name}</div><div className="text-xs muted line-clamp-2 min-h-8">{c.description || "Без описания"}</div>
              <div className="flex gap-2 mt-2"><button className="btn-primary flex-1 !h-8 !text-xs" onClick={() => use(c)}><Sparkles size={13} />Создать с ним</button>
                <button className="btn-ghost !h-8 !px-2.5" onClick={() => setEdit(c)}><Save size={13} /></button>
                <button className="btn-ghost !h-8 !px-2.5" onClick={async () => { if (confirm(`Удалить персонажа «${c.name}»?`)) { await api.del(`/api/characters/${c.id}`); load(); } }}><Trash2 size={13} /></button></div></div>
          </div>))}</div>}
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? "Персонаж" : "Новый персонаж"}>
        {edit && <div className="px-6 pb-6 space-y-4">
          <label className="block"><span className="text-xs muted">Имя</span><input className="field mt-1" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} placeholder="Например: Капитан Мира" /></label>
          <RefDrop refs={edit.refs} setRefs={(refs) => setEdit({ ...edit, refs })} max={3} label="Референсы (1–3 картинки)" />
          <label className="block"><span className="text-xs muted">Описание внешности</span><textarea className="field mt-1" rows={3} value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} placeholder="Короткие тёмные волосы, шрам над бровью, кожаная куртка…" /></label>
          <div className="text-xs dim">Только вымышленные персонажи или вы сами. Не используйте фото других реальных людей без их согласия.</div>
          <button className="btn-primary w-full" onClick={save} disabled={!edit.name || !edit.refs.length}><Save size={15} />Сохранить</button>
        </div>}
      </Modal>
    </div>
  );
}
