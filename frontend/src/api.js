const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN || "";

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, opts);

  if (!res.ok) {
    let msg = res.statusText;

    try {
      msg = (await res.json()).detail || msg;
    } catch {}

    throw new Error(msg);
  }

  return res.json();
}

const adminHeaders = () => ({
  "x-admin-token": ADMIN_TOKEN
});

export const api = {
  listDocs: () => req("/api/documents"),

  upload: (file, brand, model) => {
    const fd = new FormData();

    fd.append("file", file);
    fd.append("brand", brand);
    fd.append("model", model);

    return req("/api/documents", {
      method: "POST",
      body: fd,
      headers: adminHeaders()
    });
  },

  reprocess: (id) =>
    req(`/api/documents/${id}/reprocess`, {
      method: "POST",
      headers: adminHeaders()
    }),

  remove: (id) =>
    req(`/api/documents/${id}`, {
      method: "DELETE",
      headers: adminHeaders()
    }),

  chat: (message, session_id) =>
    req("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ message, session_id })
    }),

  history: (sid) => req(`/api/chat/${sid}`)
};