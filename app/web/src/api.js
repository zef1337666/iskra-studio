// Обёртка над API backend. Ошибки приходят по-русски в поле detail.
async function req(method, url, body) {
  const opt = { method, headers: {} };
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(url, opt); } catch { throw new Error("Студия не отвечает. Проверьте, что приложение запущено."); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Что-то пошло не так. Попробуйте ещё раз.");
  return data;
}
export const api = {
  get: (u) => req("GET", u),
  post: (u, b) => req("POST", u, b ?? {}),
  put: (u, b) => req("PUT", u, b),
  patch: (u, b) => req("PATCH", u, b),
  del: (u) => req("DELETE", u),
  upload: (file) => { const f = new FormData(); f.append("file", file); return req("POST", "/api/upload", f); },
};
export const fileUrl = (it) => `/files/output/${encodeURI(it.path)}`;
export const thumbUrl = (it) => (it.thumb ? `/files/thumbs/${it.thumb}` : null);
export const coverUrl = (p) => (p.cover ? `/files/covers/${p.cover}` : null);
