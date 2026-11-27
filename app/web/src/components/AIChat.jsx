import React, { useEffect, useRef, useState } from "react";
import { MessageCircle, Send, X, Trash2, Loader2, Sparkles, MousePointerClick } from "lucide-react";
import { api } from "../api";

// Чат с ИИ: пользователь пишет, что ему нужно, ИИ отвечает и предлагает пресеты карточками («Выбрать» / «Создать»)
const EXAMPLES = ["Хочу оживить своё фото", "Сделать крутую аватарку", "Убрать фон с фото товара", "Пейзаж для обоев на рабочий стол"];
const ls = { get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* приватный режим */ } } };

export default function AIChat({ onClose, refs, allowNsfw, onPick, onCreate, busyCreate }) {
  const [msgs, setMsgs] = useState(() => ls.get("aiChat", []));
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const end = useRef(); const input = useRef();
  useEffect(() => { ls.set("aiChat", msgs.slice(-40)); end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);
  useEffect(() => { input.current?.focus(); }, []);

  const send = async (t) => {
    const content = (t ?? text).trim();
    if (!content || busy) return;
    const next = [...msgs, { role: "user", content }];
    setMsgs(next); setText(""); setBusy(true); setError(null);
    try {
      const imgs = refs.map((r) => r.name).filter(Boolean);
      // ИИ видит прошлые предложения как текст — чтобы понимал «давай второй вариант»
      const history = next.map((m) => ({ role: m.role, content: m.role === "assistant" && m.suggestions?.length ? `${m.content}\n(Предложено: ${m.suggestions.map((s, i) => `${i + 1}) ${s.name}: ${s.idea}`).join("; ")})` : m.content }));
      const r = await api.post("/api/chat", { messages: history, images: imgs, ref_kind: imgs.some((n) => /\.(mp4|webm|mov)$/i.test(n)) ? "video" : "image", allow_nsfw: allowNsfw });
      setMsgs([...next, { role: "assistant", content: r.reply, suggestions: r.suggestions }]);
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  return (
    <div className="fixed z-50 right-3 bottom-3 top-3 w-[min(420px,calc(100vw-1.5rem))] panel rounded-2xl shadow-2xl flex flex-col animate-pop">
      <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: "1px solid var(--line)" }}>
        <MessageCircle size={17} style={{ color: "var(--color-accent-hi)" }} />
        <div className="font-semibold">Чат с ИИ</div>
        <span className="dim text-xs">подскажет, какой пресет выбрать</span>
        <div className="ml-auto flex gap-1">
          {msgs.length > 0 && <button className="btn-ghost !px-2 !h-8" title="Очистить чат" onClick={() => { setMsgs([]); setError(null); }}><Trash2 size={15} /></button>}
          <button className="btn-ghost !px-2 !h-8" title="Закрыть" onClick={onClose}><X size={16} /></button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-sm">
        {msgs.length === 0 && <div className="text-center pt-6">
          <Sparkles size={28} className="mx-auto mb-3" style={{ color: "var(--color-accent-hi)" }} />
          <p className="mb-1 font-medium">Расскажите своими словами, что хотите сделать</p>
          <p className="muted text-xs mb-4">Фото, видео, правку картинки, аватарку… Я предложу подходящие пресеты и сразу опишу задачу. Если нужно — прикрепите картинку кнопкой «+» внизу.</p>
          <div className="flex flex-wrap gap-1.5 justify-center">{EXAMPLES.map((e) => <button key={e} className="chip !h-8 !text-xs" onClick={() => send(e)}>{e}</button>)}</div>
        </div>}
        {msgs.map((m, i) => m.role === "user"
          ? <div key={i} className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-br-md px-3 py-2 text-white" style={{ background: "var(--color-accent)" }}>{m.content}</div></div>
          : <div key={i} className="space-y-2">
            <div className="max-w-[92%] rounded-2xl rounded-bl-md px-3 py-2" style={{ background: "var(--panel-2)" }}>{m.content}</div>
            {m.suggestions?.map((s) => <div key={s.preset} className="rounded-xl p-3 space-y-1.5" style={{ border: `1px solid ${s.nsfw ? "var(--color-pink)" : "var(--line)"}` }}>
              <div className="flex items-baseline gap-2"><span className="font-semibold" style={s.nsfw ? { color: "var(--color-pink)" } : {}}>{s.name}</span><span className="dim text-xs">{s.why}</span></div>
              <div className="text-xs muted leading-relaxed">{s.idea}</div>
              {s.requires && !refs.length && <div className="text-xs" style={{ color: "var(--color-pink)" }}>Нужна картинка — добавьте её кнопкой «+» внизу</div>}
              <div className="flex gap-1.5 pt-0.5">
                <button className="btn-ghost !h-7 !text-xs" onClick={() => onPick(s.preset, s.idea)}><MousePointerClick size={13} />Выбрать</button>
                <button className="btn-primary !h-7 !text-xs !px-3" disabled={busyCreate} onClick={() => onCreate(s.preset, s.idea)}>{busyCreate ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}Создать</button>
              </div>
            </div>)}
          </div>)}
        {busy && <div className="flex items-center gap-2 muted text-xs"><Loader2 size={14} className="animate-spin" />ИИ думает…</div>}
        {error && <div className="text-xs" style={{ color: "var(--color-pink)" }}>{error}</div>}
        <div ref={end} />
      </div>

      <div className="p-3 flex gap-2 items-end" style={{ borderTop: "1px solid var(--line)" }}>
        <textarea ref={input} rows={1} value={text} onChange={(e) => setText(e.target.value)} placeholder="Напишите, что нужно…"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          className="field flex-1 resize-none !py-2 max-h-32" />
        <button className="btn-primary !h-10 !w-10 !px-0 justify-center shrink-0" onClick={() => send()} disabled={busy || !text.trim()} aria-label="Отправить"><Send size={16} /></button>
      </div>
    </div>
  );
}
