import { useEffect, useState } from "react";
import { api, fmt } from "../api.js";
import Kpi from "../components/Kpi.jsx";

const STATUS = {
  open: { label: "Pendiente", color: "var(--warning)" },
  answered: { label: "Respondida", color: "var(--series-1)" },
  closed: { label: "Cerrada", color: "var(--axis)" },
};

export default function Contacto() {
  const [data, setData] = useState({ items: [], counts: {} });
  const [status, setStatus] = useState("open");
  const [sel, setSel] = useState(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  function load(keep) {
    api("/atencion/tickets", { params: { status } })
      .then((r) => {
        setData(r);
        setSel((cur) => (keep && cur ? r.items.find((t) => t.id === cur.id) || null : r.items[0] || null));
        setErr("");
      })
      .catch((e) => setErr(e.message));
  }
  useEffect(() => load(false), [status]);

  async function send() {
    setBusy(true);
    try {
      const t = await api(`/atencion/tickets/${sel.id}/reply`, { method: "POST", body: { text: reply } });
      setSel(t);
      setReply("");
      load(true);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function close() {
    await api(`/atencion/tickets/${sel.id}`, { method: "PATCH", body: { status: "closed" } });
    load(false);
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Contacto</p>
          <h1>Solicitudes para hablar con una persona</h1>
          <p>Cada solicitud llega con el resumen de la conversación: el paciente no tiene que repetir todo.
            Tu respuesta le llega por el mismo WhatsApp.</p>
        </div>
      </header>

      <div className="grid stats">
        <Kpi icon="📥" label="Pendientes" value={fmt.int(data.counts.open || 0)} />
        <Kpi icon="💬" label="Respondidas" value={fmt.int(data.counts.answered || 0)} />
        <Kpi icon="✔️" label="Cerradas" value={fmt.int(data.counts.closed || 0)} />
      </div>

      <div className="toolbar section" role="group" aria-label="Filtro">
        <div className="seg">
          {Object.entries(STATUS).map(([k, v]) => (
            <button key={k} aria-pressed={status === k} onClick={() => setStatus(k)}>{v.label}</button>
          ))}
        </div>
      </div>
      {err && <div className="card error" role="alert">{err}</div>}

      <div className="grid inbox section">
        <div className="card inbox-list">
          {data.items.length === 0 && <div className="empty">No hay solicitudes en este estado.</div>}
          {data.items.map((t) => (
            <button key={t.id} className={`inbox-item ${sel?.id === t.id ? "active" : ""}`} onClick={() => setSel(t)}>
              <div className="inbox-top">
                <b>{t.name || "Paciente"}</b>
                <span className="muted small">{t.folio}</span>
              </div>
              <div className="small"><span className="tag">{t.topic_nombre}</span>{t.channel === "web" && <span className="tag">simulador</span>}
                {!t.in_hours && <span className="tag">fuera de horario</span>}</div>
              <div className="muted small inbox-sum">{t.summary}</div>
              <div className="muted small">{fmt.datetime(t.created_at)}</div>
            </button>
          ))}
        </div>

        {sel && (
          <div className="card">
            <div className="card-head">
              <div>
                <h3>{sel.folio} · {sel.topic_nombre}</h3>
                <p>{sel.name || "Paciente"}{sel.acting_for ? ` · gestiona a ${sel.acting_for}` : ""} · {fmt.datetime(sel.created_at)}</p>
              </div>
              <span className="pill"><span className="dot" style={{ background: STATUS[sel.status]?.color }} />{STATUS[sel.status]?.label}</span>
            </div>
            <div className="ticket-summary"><b>Lo que necesita:</b> {sel.summary}</div>
            <h3 style={{ margin: "16px 0 8px" }}>Conversación previa</h3>
            <div className="transcript">
              {sel.transcript.length === 0 && <div className="muted small">Sin conversación previa.</div>}
              {sel.transcript.map((line, i) => {
                const bot = line.startsWith("MedicAI:");
                return <div key={i} className={`tline ${bot ? "bot" : "me"}`}>{line.replace(/^(MedicAI|Paciente): /, "")}</div>;
              })}
            </div>
            {sel.replies.length > 0 && (
              <>
                <h3 style={{ margin: "16px 0 8px" }}>Respuestas enviadas</h3>
                {sel.replies.map((r, i) => <div key={i} className="tline agent"><b>{r.agent}</b> · {r.at.replace("T", " ")}<br />{r.text}</div>)}
              </>
            )}
            {sel.status !== "closed" && (
              <form className="reply" onSubmit={(e) => { e.preventDefault(); send(); }}>
                <textarea rows={3} value={reply} onChange={(e) => setReply(e.target.value)}
                  placeholder="Escribe la respuesta para el paciente…" aria-label="Respuesta" />
                <div className="filters">
                  <button className="btn primary" disabled={busy || !reply.trim()}>{busy ? "Enviando…" : "Enviar por WhatsApp"}</button>
                  <button type="button" className="btn" onClick={close}>Cerrar solicitud</button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>
    </>
  );
}
