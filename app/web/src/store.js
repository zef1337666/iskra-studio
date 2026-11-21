import { create } from "zustand";
import { api } from "./api";

const ls = {
  get: (k, d) => { try { const v = localStorage.getItem("iskra_" + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem("iskra_" + k, JSON.stringify(v)); } catch {} },
};

export const useStore = create((set, get) => ({
  page: ls.get("page", "create"),
  theme: ls.get("theme", "dark"),
  safeMode: ls.get("safeMode", true),
  presets: [],
  queue: [],
  jobs: {},          // id -> job info
  previews: {},      // id -> dataURL
  lastItems: [],     // результаты последней генерации
  toasts: [],
  status: null,
  draft: ls.get("draft", { preset: "photo-real", mode: "quality", aspect: "1:1", count: 1, text: "" }),
  galleryVersion: 0,
  refInject: null,   // картинка, переданная из галереи в «Создать»

  setPage: (page) => { ls.set("page", page); set({ page }); },
  setTheme: (theme) => { ls.set("theme", theme); document.documentElement.classList.toggle("dark", theme === "dark"); set({ theme }); },
  settings: null,
  pinAsk: false,
  toggleSafe: (force) => {
    const v = !get().safeMode;
    if (!v && get().settings?.pin_set && !force) { set({ pinAsk: true }); return; }
    ls.set("safeMode", v); set({ safeMode: v, pinAsk: false });
    get().toast(v ? "Безопасный режим включён: 18+ скрыто" : "Безопасный режим выключен", "info");
  },
  setDraft: (patch) => { const d = { ...get().draft, ...patch }; ls.set("draft", { ...d, text: d.text?.slice(0, 2000) }); set({ draft: d }); },
  toast: (text, kind = "ok") => {
    const id = Math.random().toString(36).slice(2);
    set({ toasts: [...get().toasts, { id, text, kind }] });
    setTimeout(() => set({ toasts: get().toasts.filter((t) => t.id !== id) }), kind === "error" ? 7000 : 3500);
  },
  loadPresets: async () => { try { set({ presets: await api.get("/api/presets") }); } catch (e) { get().toast(e.message, "error"); } },
  onWs: (m) => {
    if (m.type === "queue") set({ queue: m.queue });
    else if (m.type === "job") {
      const j = m.job, prev = get().jobs[j.id];
      set({ jobs: { ...get().jobs, [j.id]: j } });
      if (j.state === "done" && prev?.state !== "done") {
        set({ lastItems: [...j.items, ...get().lastItems].slice(0, 24), galleryVersion: get().galleryVersion + 1 });
      }
      if (j.state === "error" && prev?.state !== "error") get().toast(j.error, "error");
    } else if (m.type === "preview") set({ previews: { ...get().previews, [m.job]: m.image } });
  },
}));

export function connectWs() {
  let ws, timer;
  const open = () => {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    ws.onmessage = (e) => useStore.getState().onWs(JSON.parse(e.data));
    ws.onclose = () => { clearTimeout(timer); timer = setTimeout(open, 2000); };
  };
  open();
}
