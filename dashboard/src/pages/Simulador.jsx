import { useEffect, useRef, useState } from "react";
import { api, fmt } from "../api.js";

function newSession() {
  return (crypto.randomUUID?.() || String(Math.random()).slice(2)).slice(0, 12);
}

/** Formato de WhatsApp (*negrita*, _cursiva_) sin usar innerHTML. */
function WaText({ text }) {
  const parts = String(text).split(/(\*[^*\n]+\*|_[^_\n]+_)/g);
  return parts.map((p, i) =>
    /^\*[^*]+\*$/.test(p) ? <b key={i}>{p.slice(1, -1)}</b>
      : /^_[^_]+_$/.test(p) ? <i key={i}>{p.slice(1, -1)}</i>
        : p,
  );
}

function Bubble({ m, onPick, used }) {
  return (
    <div className={`bubble ${m.me ? "me" : "bot"}`}>
      <WaText text={m.text} />
      {m.footer && <div className="foot">{m.footer}</div>}
      {m.options?.length > 0 && (
        <div className="opts">
          {m.options.map((o) => (
            <button key={o.id} className="opt" disabled={used} onClick={() => onPick(o)}>
              {o.title}
              {o.description && <small>{o.description}</small>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Simulador() {
  const [session, setSession] = useState(newSession);
  const [msgs, setMsgs] = useState([]);
  const [log, setLog] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const chatRef = useRef(null);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs]);

  // Mensajes proactivos (recordatorios) que el scheduler envía a esta sesión.
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const r = await api(`/outbox/web:${session}`);
        if (r.messages.length) setMsgs((m) => [...m, ...r.messages.map((x) => ({ ...x, proactive: true }))]);
      } catch { /* sin conexión: se reintenta */ }
    }, 5000);
    return () => clearInterval(id);
  }, [session]);

  async function send(text, option) {
    if (busy || (!text?.trim() && !option)) return;
    setBusy(true);
    setMsgs((m) => [...m.map((x) => ({ ...x, used: x.used || !!x.options?.length })), { me: true, text: option ? option.title : text }]);
    setInput("");
    const t0 = performance.now();
    try {
      const r = await api("/chat", { method: "POST", body: { session_id: session, text: option ? "" : text, option_id: option?.id || null } });
      setMsgs((m) => [...m, ...r.messages]);
      setLog((l) => [{ input: option ? `[${option.id}]` : text, rtt: performance.now() - t0, ...r.meta }, ...l].slice(0, 30));
    } catch (e) {
      setMsgs((m) => [...m, { text: `⚠️ Error: ${e.message}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Simulador de conversación</h1>
          <p>Prueba los flujos sin WhatsApp. Las conversaciones quedan registradas con canal «Simulador».</p>
        </div>
        <button className="btn" onClick={() => { setSession(newSession()); setMsgs([]); setLog([]); }}>↺ Nueva sesión</button>
      </div>
      <div className="sim">
        <div className="phone">
          <div className="phone-head">
            <div className="avatar" aria-hidden="true">🩺</div>
            <div><b>MedicAI</b><div className="small" style={{ opacity: 0.8 }}>Asistente de tu CESFAM</div></div>
          </div>
          <div className="chat" ref={chatRef} aria-live="polite">
            {msgs.length === 0 && <div className="empty">Escribe «hola» para comenzar.</div>}
            {msgs.map((m, i) => <Bubble key={i} m={m} used={m.used || busy} onPick={(o) => send("", o)} />)}
          </div>
          <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
            <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Escribe un mensaje" aria-label="Mensaje" />
            <button className="btn primary" disabled={busy}>Enviar</button>
          </form>
        </div>

        <div className="card">
          <div className="card-head"><div><h2>Traza técnica</h2><p>Cómo se procesó cada mensaje (útil en pruebas de usabilidad y validación)</p></div></div>
          {log.length === 0 ? <div className="empty">Aún no hay mensajes.</div> : (
            <div className="table-wrap">
              <table className="meta-log">
                <thead><tr><th>Entrada</th><th>Intención</th><th>Motor</th><th className="r">Confianza</th><th>Servicio</th><th className="r">Asistente</th><th className="r">Ida y vuelta</th></tr></thead>
                <tbody>
                  {log.map((l) => (
                    <tr key={l.interaction_id}>
                      <td>{l.input.slice(0, 28)}</td>
                      <td>{l.nlu?.intent || (l.red_flag ? "alarma" : "—")}</td>
                      <td>{l.nlu?.source || (l.input.startsWith("[") ? "opción" : "—")}</td>
                      <td className="r">{l.nlu ? fmt.pct(l.nlu.confidence) : "—"}</td>
                      <td>{(l.services || []).join(" → ") || "orquestador"}</td>
                      <td className="r">{fmt.ms(l.latency_ms)}</td>
                      <td className="r">{fmt.ms(l.rtt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
