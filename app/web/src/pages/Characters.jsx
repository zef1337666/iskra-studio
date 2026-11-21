import React, { useEffect, useState } from "react";
import { UserRound, Plus, Trash2, Sparkles, Save, Info } from "lucide-react";
import { useStore } from "../store";
import { api } from "../api";
import RefDrop from "../components/RefDrop";
import { Empty, Modal } from "../components/ui";

export default function Characters() {
  const { toast, setDraft, setPage } = useStore();
  const [list, setList] = useState(null);
  const [edit, setEdit] = useState(null);
  const load = () => api.get("/api/characters").then(setList).catch((e) => toast(e.message, "error"));
  useEffect(() => { load(); }, []);
  const save = async () => {
    try { await api.post("/api/characters", { ...edit, cover: edit.cover || null }); toast("Персонаж сохранён"); setEdit(null); load(); } catch (e) { toast(e.message, "error"); }
  };
  const use = (c) => { useStore.setState({ refInject: { refs: c.refs, character: c } }); setDraft({ preset: "character", text: "" }); setPage("create"); };
  return (
    <div className="h-full overflow-y-auto p-5 md:p-8">
      <div className="flex items-center justify-between mb-2"><h1 className="text-2xl font-bold">Персонажи</h1>
        <button className="btn-primary" onClick={() => setEdit({ name: "", description: "", refs: [] })}><Plus size={15} />Новый персонаж</button></div>
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
