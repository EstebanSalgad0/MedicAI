import { Fragment, useEffect, useState } from "react";
import { api, fmt } from "../api.js";
import Kpi from "../components/Kpi.jsx";

const ESTADOS = {
  enviada: { label: "Enviada", icon: "📨", color: "var(--series-1)" },
  agendada: { label: "Agendada", icon: "📅", color: "var(--series-4)" },
  atendida: { label: "Atendida", icon: "✅", color: "var(--good)" },
  caducada: { label: "Caducada", icon: "⌛", color: "var(--critical)" },
};
const PRIORIDAD = { normal: "Normal", preferente: "Preferente", urgente: "Urgente" };
const VACIA = { paciente_run: "", paciente_nombre: "", origen_id: "", destino_id: "", especialidad: "", prioridad: "normal",
  ges: false, motivo: "" };

function Nueva({ user, destinos, onDone }) {
  const [f, setF] = useState({ ...VACIA, origen_id: user.establecimientos?.[0] || "" });
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const origenes = user.rol === "admin" ? destinos.intra : destinos.intra.filter((d) => user.establecimientos?.includes(d.id));
  async function enviar(e) {
    e.preventDefault();
    setErr("");
    try {
      await api("/derivacion/derivaciones", { method: "POST", body: f });
      setF({ ...VACIA, origen_id: f.origen_id });
      onDone();
    } catch (x) {
      setErr(x.message);
    }
  }
  return (
    <form className="card section stack" onSubmit={enviar}>
      <div className="card-head"><div><h3>Nueva derivación</h3><p>Queda registrada con fecha, origen, destino y usted como responsable.</p></div></div>
      <div className="row">
        <label className="small">RUN del paciente<input type="text" value={f.paciente_run} onChange={set("paciente_run")} required placeholder="12.345.678-5" /></label>
        <label className="small">Nombre<input type="text" value={f.paciente_nombre} onChange={set("paciente_nombre")} /></label>
        <label className="small">Especialidad<input type="text" value={f.especialidad} onChange={set("especialidad")} required placeholder="Cardiología" /></label>
      </div>
      <div className="row">
        <label className="small">Origen
          <select value={f.origen_id} onChange={set("origen_id")} required>
            <option value="">Elegir…</option>
            {origenes.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
          </select>
        </label>
        <label className="small">Destino
          <select value={f.destino_id} onChange={set("destino_id")} required>
            <option value="">Elegir…</option>
            <optgroup label="Intra red">{destinos.intra.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}</optgroup>
            <optgroup label="Extra red">{destinos.extra.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}</optgroup>
          </select>
        </label>
        <label className="small">Prioridad
          <select value={f.prioridad} onChange={set("prioridad")}>
            {Object.entries(PRIORIDAD).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="chk"><input type="checkbox" checked={f.ges} onChange={set("ges")} /> GES</label>
      </div>
      <label className="small">Motivo de la derivación<textarea rows={2} value={f.motivo} onChange={set("motivo")} required minLength={3} /></label>
      {err && <div className="error small" role="alert">{err}</div>}
      <div><button className="btn primary">Enviar derivación</button></div>
    </form>
  );
}

function Acciones({ d, onDone }) {
  const [fecha, setFecha] = useState("");
  const [nota, setNota] = useState("");
  const [err, setErr] = useState("");
  async function cambiar(estado) {
    setErr("");
    try {
      await api(`/derivacion/derivaciones/${d.id}`, { method: "PATCH", body: { estado, nota: nota || null, fecha_cita: fecha || null } });
      onDone();
    } catch (x) {
      setErr(x.message);
    }
  }
  if (d.estado === "atendida" || d.estado === "caducada") return <span className="muted small">Estado final</span>;
  return (
    <div className="stack">
      <div className="row">
        <label className="small">Fecha de la cita<input type="datetime-local" value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
        <label className="small">Nota<input type="text" value={nota} onChange={(e) => setNota(e.target.value)} maxLength={500} /></label>
      </div>
      <div className="row">
        <button className="btn small" disabled={!fecha} onClick={() => cambiar("agendada")}>📅 {d.estado === "agendada" ? "Reagendar" : "Agendar"}</button>
        {d.estado === "agendada" && <button className="btn small" onClick={() => cambiar("atendida")}>✅ Registrar atención</button>}
        <button className="btn small" onClick={() => cambiar("caducada")}>⌛ Caducar</button>
      </div>
      {err && <div className="error small" role="alert">{err}</div>}
    </div>
  );
}

export default function Derivaciones({ user }) {
  const [data, setData] = useState({ items: [], counts: {} });
  const [destinos, setDestinos] = useState({ intra: [], extra: [] });
  const [estado, setEstado] = useState("");
  const [abierta, setAbierta] = useState(null);
  const [err, setErr] = useState("");

  function load() {
    api("/derivacion/derivaciones", { params: { estado } }).then((d) => { setData(d); setErr(""); }).catch((x) => setErr(x.message));
  }
  useEffect(load, [estado]);
  useEffect(() => { api("/derivacion/destinos").then(setDestinos).catch(() => {}); }, []);
  const c = data.counts;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Módulo 3 · Derivaciones</p>
          <h1>Derivaciones con seguimiento</h1>
          <p>Intra y extra red, con trazabilidad hasta la atención de destino. Si el paciente vinculó su WhatsApp con ClaveÚnica, se le avisa al agendarse.</p>
        </div>
      </header>
      <div className="grid stats">
        {Object.entries(ESTADOS).map(([k, v]) => <Kpi key={k} icon={v.icon} label={v.label} value={fmt.int(c[k] || 0)} />)}
      </div>
      {user.clinico || user.rol === "admin" ? <Nueva user={user} destinos={destinos} onDone={load} /> : null}
      {err && <div className="card error section" role="alert">{err}</div>}
      <div className="card section">
        <div className="card-head">
          <div><h3>Listado</h3><p>Toque una fila para ver el historial y cambiar el estado.</p></div>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} aria-label="Estado">
            <option value="">Todos los estados</option>
            {Object.entries(ESTADOS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </div>
        {data.items.length === 0 ? <div className="empty">No hay derivaciones con este filtro.</div> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Folio</th><th>Emitida</th><th>Paciente</th><th>Origen → destino</th><th>Especialidad</th><th>Prioridad</th><th>Estado</th><th>Responsable</th></tr></thead>
              <tbody>
                {data.items.map((d) => (
                  <Fragment key={d.id}>
                    <tr className="clickable" onClick={() => setAbierta(abierta === d.id ? null : d.id)} aria-expanded={abierta === d.id}>
                      <td className="num small">{d.folio}</td>
                      <td className="num">{fmt.date(d.created_at)}</td>
                      <td>{d.paciente_nombre || <span className="muted">Sin nombre</span>}<div className="small muted">{d.paciente_run_mask}</div></td>
                      <td className="small">{d.origen} → {d.destino}<span className="tag">{d.red === "intra" ? "intra red" : "extra red"}</span></td>
                      <td>{d.especialidad}{d.ges && <span className="tag">GES</span>}</td>
                      <td className="small">{PRIORIDAD[d.prioridad]}</td>
                      <td><span className="pill"><span className="dot" style={{ background: ESTADOS[d.estado]?.color }} />{ESTADOS[d.estado]?.icon} {ESTADOS[d.estado]?.label}</span>
                        {d.estado === "agendada" && d.fecha_cita && <div className="small muted">{fmt.datetime(d.fecha_cita)}</div>}</td>
                      <td className="small">{d.responsable}</td>
                    </tr>
                    {abierta === d.id && (
                      <tr>
                        <td colSpan={8}>
                          <div className="grid two">
                            <div>
                              <b className="small">Motivo</b>
                              <p className="small" style={{ marginTop: 4 }}>{d.motivo}</p>
                              <b className="small">Historial</b>
                              <ol className="timeline">
                                {d.eventos.map((e, i) => (
                                  <li key={i}><b>{ESTADOS[e.estado]?.label}</b> · {fmt.datetime(e.at)} · {e.responsable}{e.nota && <div className="small muted">{e.nota}</div>}</li>
                                ))}
                              </ol>
                            </div>
                            <Acciones d={d} onDone={load} />
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
