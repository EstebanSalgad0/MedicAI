import { useEffect, useState } from "react";
import { api, fmt } from "../api.js";
import Kpi from "../components/Kpi.jsx";

const STATUS = {
  confirmed: { label: "Agendada", color: "var(--series-1)" },
  attended: { label: "Asistió", color: "var(--good)" },
  no_show: { label: "No asistió", color: "var(--critical)" },
  cancelled: { label: "Cancelada", color: "var(--axis)" },
};
const REPLY = { yes: "✅ Confirmó", reschedule: "🔁 Reagendó", cancel: "❌ Avisó que no va" };

function today(offset = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toLocaleDateString("en-CA");
}

const CUPO = {
  ocupada: ["●", "Ocupada"], atendida: ["✓", "Atendida"], inasistencia: ["✕", "No asistió"],
  ofrecida: ["⚡", "Ofrecida a lista de espera"], libre: ["", "Libre"], pasada: ["·", "Pasó sin uso"],
};
const PRIORIDADES = [[0, "Orden de llegada"], [1, "GES"], [2, "Prioridad clínica"]];

/** Vista centralizada: todos los box y profesionales del centro, actualizada cada 30 s. */
function Ocupacion({ centers }) {
  const [center, setCenter] = useState("");
  const [fecha, setFecha] = useState(today());
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { if (!center && centers.length) setCenter(centers[0].id); }, [centers]);
  useEffect(() => {
    if (!center) return undefined;
    const load = () => api("/agendamiento/ocupacion", { params: { center_id: center, fecha } })
      .then((d) => { setData(d); setErr(""); }).catch((e) => setErr(e.message));
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [center, fecha]);
  return (
    <div className="card section">
      <div className="card-head">
        <div>
          <h3>Ocupación por box y profesional</h3>
          <p>Disponibilidad del día en tiempo real (se actualiza cada 30 s). {data && `Actualizado ${data.actualizado.slice(11, 16)}.`}</p>
        </div>
        <div className="row">
          <select value={center} onChange={(e) => setCenter(e.target.value)} aria-label="Establecimiento">
            {centers.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} aria-label="Fecha" />
        </div>
      </div>
      {err && <div className="error small">{err}</div>}
      {data && !data.habil && <div className="empty">Día no hábil: sin agenda.</div>}
      {data && data.habil && (
        <>
          <div className="legend">
            {Object.entries(CUPO).map(([k, [ico, txt]]) => <span key={k}><i className={`box cupo-${k}`} />{ico} {txt}</span>)}
            <span className="muted">Ocupación: <b>{fmt.pct(data.resumen.ocupacion)}</b> · {data.resumen.libres} cupos libres</span>
          </div>
          <div className="table-wrap">
            <table className="ocupacion">
              <thead><tr><th>Profesional · box</th>{data.horarios.map((h) => <th key={h} className="r">{h}</th>)}<th className="r">Uso</th></tr></thead>
              <tbody>
                {data.filas.map((f) => (
                  <tr key={f.prestacion}>
                    <td><b>{f.profesional}</b><div className="small muted">{f.box} · {f.prestacion_nombre}</div></td>
                    {f.slots.map((s) => (
                      <td key={s.hora} className={`cupo cupo-${s.estado}`}
                        title={`${s.hora} · ${CUPO[s.estado][1]}${s.paciente ? ` · ${s.paciente}` : ""}${s.codigo ? ` (${s.codigo})` : ""}`}>
                        {CUPO[s.estado][0]}
                      </td>
                    ))}
                    <td className="r small">{fmt.pct(f.ocupacion)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default function Agenda() {
  const [centers, setCenters] = useState([]);
  const [center, setCenter] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState(today(-7));
  const [to, setTo] = useState(today(14));
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [waitlist, setWaitlist] = useState([]);
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => { api("/agendamiento/catalog").then((c) => setCenters(c.centers)).catch(() => {}); }, []);

  function load() {
    setLoading(true);
    Promise.all([
      api("/agendamiento/appointments", { params: { center_id: center, status, date_from: from, date_to: to } }),
      api("/agendamiento/stats", { params: { center_id: center } }),
      api("/agendamiento/waitlist"),
      api("/agendamiento/gap-offers", { params: { limit: 15 } }),
    ])
      .then(([r, s, w, g]) => { setRows(r); setStats(s); setWaitlist(w); setOffers(g); setErr(""); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }
  useEffect(load, [center, status, from, to]);

  async function mark(id, st) {
    await api(`/agendamiento/appointments/${id}`, { method: "PATCH", body: { status: st } });
    load();
  }

  async function setPriority(w, priority) {
    let motivo = null;
    if (priority === 2) {
      motivo = window.prompt("Motivo clínico de la prioridad (queda registrado con su nombre):", w.priority_reason || "");
      if (!motivo?.trim()) return;
    }
    try {
      await api(`/agendamiento/waitlist/${w.id}`, { method: "PATCH", body: { priority, motivo } });
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  const past = (r) => new Date(r.slot_at) < new Date();
  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Módulo 3 · Agenda centralizada</p>
          <h1>Horas reservadas por MedicAI</h1>
          <p>Horas que los pacientes agendaron por el chat. Registra si asistieron para medir la inasistencia.</p>
        </div>
      </header>

      <div className="toolbar" role="group" aria-label="Filtros">
        <select value={center} onChange={(e) => setCenter(e.target.value)} aria-label="CESFAM">
          <option value="">Todos los establecimientos</option>
          {centers.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Estado">
          <option value="">Todos los estados</option>
          {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <label className="small muted">Desde <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label className="small muted">Hasta <input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        <span className="toolbar-note">{rows.length} horas en el rango</span>
      </div>

      {stats && (
        <div className="grid stats section">
          <Kpi icon="🗓️" label="Horas vigentes" value={fmt.int(stats.by_status.confirmed || 0)}
            info="Horas agendadas que aún no ocurren o que no tienen asistencia registrada." />
          <Kpi icon="✅" label="Asistencias registradas" value={fmt.int(stats.by_status.attended || 0)} />
          <Kpi icon="🚫" label="Inasistencias registradas" value={fmt.int(stats.by_status.no_show || 0)} />
          <Kpi icon="📉" label="Tasa de inasistencia" value={fmt.pct(stats.no_show_rate)}
            detail="Sobre horas con asistencia registrada"
            info="No asistió ÷ (asistió + no asistió). Solo cuenta horas en que el CESFAM registró la asistencia." />
        </div>
      )}
      {err && <div className="card error" role="alert">{err}</div>}

      <Ocupacion centers={centers} />

      <div className={`card section ${loading ? "loading" : ""}`}>
        <div className="card-head">
          <div>
            <h3>Listado de horas</h3>
            <p>Los botones de asistencia se activan cuando la hora ya pasó.</p>
          </div>
        </div>
        {rows.length === 0 ? (
          <div className="empty">{loading ? "Cargando…" : "No hay horas con estos filtros."}</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Fecha y hora</th><th>Código</th><th>Paciente</th><th>Atención</th><th>CESFAM</th><th>Recordatorio</th><th>Estado</th><th>Registrar</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="num">{fmt.datetime(r.slot_at)}</td>
                    <td className="num small">{r.code}</td>
                    <td>{r.patient_name || <span className="muted">Sin nombre</span>}{r.channel === "web" && <span className="tag">simulador</span>}{r.ges && <span className="tag" title={`Mencionó ${r.ges}`}>GES</span>}</td>
                    <td>{r.prestacion_nombre}</td>
                    <td>{r.center_nombre}</td>
                    <td className="small">{REPLY[r.attendance_reply] || <span className="muted">—</span>}</td>
                    <td><span className="pill"><span className="dot" style={{ background: STATUS[r.status]?.color }} />{STATUS[r.status]?.label || r.status}</span></td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {r.status !== "cancelled" && (
                        <>
                          <button className="btn small" disabled={!past(r) || r.status === "attended"} onClick={() => mark(r.id, "attended")}>Asistió</button>{" "}
                          <button className="btn small" disabled={!past(r) || r.status === "no_show"} onClick={() => mark(r.id, "no_show")}>No asistió</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    
      <div className="card section">
        <div className="card-head">
          <div>
            <h3>Lista de espera y fill-the-gap</h3>
            <p>Cuando alguien cancela, la hora se ofrece de inmediato al primero compatible. La prioridad clínica prevalece sobre el orden de llegada: prioridad clínica → GES → antigüedad.</p>
          </div>
        </div>
        {waitlist.length === 0 ? <div className="empty">Nadie en lista de espera.</div> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Desde</th><th>Paciente</th><th>Atención</th><th>Centro</th><th>Busca</th><th>Prioridad</th><th className="r">Ofertas</th></tr></thead>
              <tbody>
                {waitlist.map((w) => (
                  <tr key={w.id}>
                    <td className="num">{fmt.datetime(w.created_at)}</td>
                    <td>{w.patient_name || <span className="muted">Sin nombre</span>}</td>
                    <td>{w.prestacion_nombre}</td>
                    <td>{w.center_nombre}</td>
                    <td className="small">{w.earlier ? "Una hora antes de la que tiene" : "Una hora"}</td>
                    <td>
                      <select value={w.priority} onChange={(e) => setPriority(w, Number(e.target.value))} aria-label="Prioridad">
                        {PRIORIDADES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                      {w.priority_reason && <div className="small muted" title={w.priority_by}>{w.priority_reason}</div>}
                    </td>
                    <td className="r">{w.offers}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card section">
        <div className="card-head">
          <div>
            <h3>Reasignaciones recientes</h3>
            <p>Cada cupo liberado y ofrecido, con el criterio aplicado para elegir al paciente.</p>
          </div>
        </div>
        {offers.length === 0 ? <div className="empty">Aún no hay reasignaciones.</div> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Ofrecida</th><th>Cupo</th><th>Atención</th><th>Paciente</th><th>Resultado</th><th>Criterio aplicado</th></tr></thead>
              <tbody>
                {offers.map((o) => (
                  <tr key={o.id}>
                    <td className="num">{fmt.datetime(o.offered_at)}</td>
                    <td className="num">{fmt.datetime(o.slot_at)}</td>
                    <td>{o.prestacion_nombre}<div className="small muted">{o.center_nombre}</div></td>
                    <td>{o.patient_name || <span className="muted">Sin nombre</span>}</td>
                    <td className="small">{{ offered: "⏳ Esperando respuesta", accepted: "✅ Tomada", declined: "No la quiso", expired: "⌛ Venció", taken: "Ya tomada" }[o.status] || o.status}</td>
                    <td className="small">{o.criterio || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
