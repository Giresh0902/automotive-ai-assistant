import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [brand, setBrand] = useState("Hyundai");
  const [model, setModel] = useState("");
  const [file, setFile] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("admin_token") || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef();

  const load = () => api.listDocs().then(setDocs).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  useEffect(() => {  // poll while anything is processing
    if (!docs.some((d) => d.status === "processing")) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [docs]);

  const saveToken = (v) => { setToken(v); localStorage.setItem("admin_token", v); };

  async function submit(e) {
    e.preventDefault(); setErr("");
    if (!file) return setErr("Choose a PDF first");
    setBusy(true);
    try { await api.upload(file, brand, model); setFile(null); fileRef.current.value = ""; await load(); }
    catch (e) { setErr(e.message); }
    setBusy(false);
  }
  const act = (fn) => async (id) => { setErr(""); try { await fn(id); await load(); } catch (e) { setErr(e.message); } };
  const del = act(async (id) => { if (confirm("Delete this brochure and its indexed data?")) await api.remove(id); });
  const redo = act(api.reprocess);

  return (
    <section>
      <h2>Brochure management</h2>
      <form className="card upload" onSubmit={submit}>
        <input placeholder="Brand" value={brand} onChange={(e) => setBrand(e.target.value)} required />
        <input placeholder="Model (e.g. Creta)" value={model} onChange={(e) => setModel(e.target.value)} required />
        <input ref={fileRef} type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0])} />
        <input type="password" placeholder="Admin token" value={token} onChange={(e) => saveToken(e.target.value)} />
        <button disabled={busy}>{busy ? "Uploading…" : "Upload brochure"}</button>
      </form>
      {err && <p className="error">{err}</p>}
      <table>
        <thead><tr><th>Vehicle</th><th>File</th><th>Pages</th><th>Status</th><th>Uploaded</th><th>Actions</th></tr></thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              <td>{d.vehicles ? `${d.vehicles.brand} ${d.vehicles.model}` : "—"}</td>
              <td>{d.filename}</td>
              <td>{d.page_count ?? "—"}</td>
              <td><span className={`pill ${d.status}`} title={d.error || ""}>{d.status}</span></td>
              <td>{new Date(d.uploaded_at).toLocaleString()}</td>
              <td className="actions">
                <a href={d.url} target="_blank" rel="noreferrer">View</a>
                <button onClick={() => redo(d.id)}>Reprocess</button>
                <button className="danger" onClick={() => del(d.id)}>Delete</button>
              </td>
            </tr>
          ))}
          {!docs.length && <tr><td colSpan="6" className="muted">No brochures yet. Upload one above.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}
