// Быстрые действия с результатом. run(item) запускает задачу; goto — переход в «Создать» с подстановкой.
import { api } from "../api";
import { useStore } from "../store";

const S = () => useStore.getState();

async function gen(body) {
  // без всплывающих «добавлено в очередь»: карточка задачи сама появляется в ленте
  try { await api.post("/api/generate", body); if (S().page !== "create") S().toast("Задача в очереди — прогресс на экране «Создать»", "info"); }
  catch (e) { S().toast(e.message, "error"); }
}

function toCreate(item, preset, extra = {}) {
  api.post(`/api/items/${item.id}/to-input`).then((ref) => {
    useStore.setState({ refInject: { refs: [ref], ...extra } });
    S().setDraft({ preset, ...(extra.text !== undefined ? { text: extra.text } : {}) });
    S().setPage("create");
  }).catch((e) => S().toast(e.message, "error"));
}

export const ACTIONS = [
  { id: "more", label: "Ещё варианты", kinds: ["image", "video"], hint: "Тот же промпт, новые случайные варианты",
    run: (it) => gen({ preset: it.preset, mode: it.mode, prompt: it.prompt, negative: it.negative, user_text: it.user_text, count: 2,
      width: it.params?.width, height: it.params?.height, loras: it.params?.loras, images: it.params?.images }, "Делаю ещё 2 варианта") },
  { id: "repeat", label: "Повторить", kinds: ["image", "video"], hint: "Ещё раз с тем же seed — тот же результат, если ничего не менять",
    run: (it) => gen({ preset: it.preset, mode: it.mode, prompt: it.prompt, negative: it.negative, user_text: it.user_text, seed: it.seed, seed_lock: true,
      width: it.params?.width, height: it.params?.height, loras: it.params?.loras, images: it.params?.images }) },
  { id: "edit-prompt", label: "Изменить промпт", kinds: ["image", "video"], hint: "Открыть промпт этого результата в «Создать»",
    run: (it) => { S().setDraft({ preset: it.preset, text: it.user_text || it.prompt }); useStore.setState({ refInject: { prompt: it.prompt, negative: it.negative, seed: it.seed } }); S().setPage("create"); } },
  { id: "upscale", label: "Апскейл", key: "u", kinds: ["image"], hint: "Увеличить в 4 раза с восстановлением деталей (SeedVR2)",
    run: (it) => gen({ preset: "upscale", mode: "quality", source_item: it.id }, "Апскейл добавлен в очередь") },
  { id: "detail", label: "Улучшить лицо и руки", kinds: ["image"], hint: "Ретушь лица и рук без изменения композиции",
    run: (it) => gen({ preset: "detail", mode: "quality", source_item: it.id }) },
  { id: "nobg", label: "Удалить фон", kinds: ["image"], hint: "PNG с прозрачным фоном", run: (it) => gen({ preset: "nobg", mode: "quality", source_item: it.id }) },
  { id: "edit", label: "Редактировать командой", kinds: ["image"], hint: "Напишите, что изменить: «сделай ночь», «добавь очки»…", run: (it) => toCreate(it, "edit", { text: "" }) },
  { id: "outpaint", label: "Расширить кадр", kinds: ["image"], hint: "Сделать кадр шире: дорисовать по бокам",
    run: (it) => gen({ preset: "outpaint", mode: "quality", source_item: it.id, left: Math.round((it.width || 1024) / 4), right: Math.round((it.width || 1024) / 4) }) },
  { id: "animate", label: "Оживить", kinds: ["image"], hint: "Сделать видео из этой картинки", run: (it) => toCreate(it, it.nsfw ? "video18" : "video", { text: "" }) },
  { id: "to3d", label: "Сделать 3D", kinds: ["image"], hint: "3D-модель с текстурой (GLB)", run: (it) => gen({ preset: "to-3d", mode: "quality", source_item: it.id }, "3D-модель в очереди (~2 мин)") },
  { id: "as-ref", label: "Как референс", kinds: ["image"], hint: "Использовать как картинку-референс в «Создать»", run: (it) => toCreate(it, S().draft.preset) },
  { id: "smooth", label: "Сделать плавнее", kinds: ["video"], hint: "Удвоить частоту кадров (RIFE)", run: (it) => gen({ preset: "video-enhance", mode: "draft", source_item: it.id, fps: it.params?.fps || (it.preset === "video" || it.preset === "transition" ? 24 : 16) }) },
  { id: "sound", label: "Добавить звук", kinds: ["video"], hint: "Сгенерировать звук под видео (MMAudio)",
    run: (it) => gen({ preset: "video-sound", mode: "quality", source_item: it.id, prompt: it.prompt?.slice(0, 300), fps: 16, duration: it.params?.seconds || 5 }) },
];

export async function toggleFav(it) {
  const r = await api.patch(`/api/items/${it.id}`, { favorite: !it.favorite });
  useStore.setState({ galleryVersion: S().galleryVersion + 1 });
  return r;
}
