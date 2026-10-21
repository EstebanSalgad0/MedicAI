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

export default function Agenda() {
  const [centers, setCenters] = useState([]);
  const [center, setCenter] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState(today(-7));
  const [to, setTo] = useState(today(14));
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => { api("/agendamiento/catalog").then((c) => setCenters(c.centers)).catch(() => {}); }, []);

  function load() {
    setLoading(true);
    Promise.all([
      api("/agendamiento/appointments", { params: { center_id: center, status, date_from: from, date_to: to } }),
      api("/agendamiento/stats"),
    ])
      .then(([r, s]) => { setRows(r); setStats(s); setErr(""); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }
  useEffect(load, [center, status, from, to]);

  async function mark(id, st) {
    await api(`/agendamiento/appointments/${id}`, { method: "PATCH", body: { status: st } });
    load();
  }

  const past = (r) => new Date(r.slot_at) < new Date();
  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Agenda</p>
          <h1>Horas reservadas por MedicAI</h1>
          <p>Horas que los pacientes agendaron por el chat. Registra si asistieron para medir la inasistencia.</p>
        </div>
      </header>

      <div className="toolbar" role="group" aria-label="Filtros">
        <select value={center} onChange={(e) => setCenter(e.target.value)} aria-label="CESFAM">
          <option value="">Todos los CESFAM</option>
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
                <tr><th>Fecha y hora</th><th>Paciente</th><th>Atención</th><th>CESFAM</th><th>Recordatorio</th><th>Estado</th><th>Registrar</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="num">{fmt.datetime(r.slot_at)}</td>
                    <td>{r.patient_name || <span className="muted">Sin nombre</span>}{r.channel === "web" && <span className="tag">simulador</span>}</td>
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
    </>
  );
}
