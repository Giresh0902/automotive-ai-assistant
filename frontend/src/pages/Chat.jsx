import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api.js";

const SUGGESTIONS = [
  "List the key features of the Hyundai Alcazar",
  "Compare Hyundai Alcazar vs Creta",
  "What are the safety features of the Creta?",
  "Compare Creta SX vs SX(O) variants",
];

export default function Chat() {
  const [sid, setSid] = useState(localStorage.getItem("chat_sid"));
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef();

  useEffect(() => { if (sid) api.history(sid).then(setMsgs).catch(() => {}); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  async function send(text) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: q }]);
    try {
      const r = await api.chat(q, sid);
      if (!sid) { setSid(r.session_id); localStorage.setItem("chat_sid", r.session_id); }
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, sources: r.sources }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", content: `⚠️ ${e.message}`, sources: [] }]);
    }
    setBusy(false);
  }
  const newChat = () => { localStorage.removeItem("chat_sid"); setSid(null); setMsgs([]); };

  return (
    <section className="chat">
      <div className="thread">
        {!msgs.length && (
          <div className="empty">
            <p>Ask anything about the uploaded brochures.</p>
            <div className="chips">{SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}</div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
            {m.sources?.length > 0 && (
              <div className="sources">
                {m.sources.map((s) => (
                  <a key={s.tag} href={`${s.url}#page=${s.page}`} target="_blank" rel="noreferrer">
                    [{s.tag}] {s.vehicle || s.filename} · p.{s.page}
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="msg assistant typing">Thinking…</div>}
        <div ref={end} />
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about features, compare cars or variants…" />
        <button disabled={busy}>Send</button>
        <button type="button" className="ghost" onClick={newChat}>New chat</button>
      </form>
    </section>
  );
}
