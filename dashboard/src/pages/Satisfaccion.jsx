import { useEffect, useState } from "react";
import { api, fmt, SERVICE_LABEL } from "../api.js";
import Kpi, { TargetCard } from "../components/Kpi.jsx";
import { Card, Section } from "../components/Section.jsx";
import { HBars, InlineBar, TimeLines } from "../components/charts.jsx";

const PERIODS = [7, 30, 90];
const CHANNELS = [
  { id: "", label: "Todos" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "web", label: "Simulador" },
];
const RATING = { 5: "😀 Excelente", 4: "🙂 Buena", 3: "😐 Regular", 2: "🙁 Mala", 1: "😞 Muy mala" };
const LABEL = { ...SERVICE_LABEL, sin_dato: "Sin dato" };

function Stars({ n }) {
  return (
    <span className="stars" aria-label={`${n} de 5`}>
      {"★".repeat(n)}<span className="off">{"★".repeat(5 - n)}</span>
    </span>
  );
}

export default function Satisfaccion() {
  const [days, setDays] = useState(30);
  const [center, setCenter] = useState("");
  const [channel, setChannel] = useState("");
  const [centers, setCenters] = useState([]);
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api("/agendamiento/catalog").then((c) => setCenters(c.centers)).catch(() => {});
  }, []);
  useEffect(() => {
    setLoading(true);
    api("/analytics/satisfaction", { params: { days, center, channel, limit: 50 } })
      .then((r) => { setD(r); setErr(""); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [days, center, channel]);

  const centerName = (id) => centers.find((c) => c.id === id)?.nombre || id;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Satisfacción</p>
          <h1>¿Qué opinan los pacientes?</h1>
          <p>Respuestas a la encuesta que MedicAI envía al terminar un trámite: «¿Cómo evaluarías la atención que te di?».</p>
        </div>
      </header>

      <div className="toolbar" role="group" aria-label="Filtros">
        <div className="seg" role="group" aria-label="Período">
          {PERIODS.map((p) => <button key={p} aria-pressed={days === p} onClick={() => setDays(p)}>{p} días</button>)}
        </div>
        <select value={center} onChange={(e) => setCenter(e.target.value)} aria-label="CESFAM">
          <option value="">Todos los establecimientos</option>
          {centers.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <div className="seg" role="group" aria-label="Canal">
          {CHANNELS.map((c) => <button key={c.id} aria-pressed={channel === c.id} onClick={() => setChannel(c.id)}>{c.label}</button>)}
        </div>
        {center && <span className="toolbar-note">Por CESFAM solo se ven las evaluaciones de agendamiento y farmacia.</span>}
      </div>
      {err && <div className="card error" role="alert">No se pudieron cargar las respuestas: {err}</div>}
      {!d && loading && <div className="empty">Cargando…</div>}

      {d && (
        <div className={loading ? "loading" : ""}>
          <Section title="Resumen" desc="Nota de 1 (muy mala) a 5 (excelente).">
            <div className="grid stats">
              <TargetCard label="Nota promedio" value={d.avg == null ? "—" : `${fmt.dec(d.avg)} / 5`}
                raw={d.avg} target={d.target} scale={[1, 5]} format={(v) => fmt.dec(v)}
                desc="Promedio de todas las respuestas del período."
                info="Suma de las notas ÷ número de respuestas. La meta del proyecto es 4,5 o más." />
              <Kpi icon="🗳️" label="Respuestas" value={fmt.int(d.n)}
                detail={d.response_rate == null ? null : `${fmt.pct(d.response_rate)} de ${fmt.int(d.sent)} encuestas enviadas`}
                info="Cada paciente recibe la encuesta como máximo una vez cada 24 horas, después de un trámite resuelto." />
              <Kpi icon="😀" label="Satisfechos" value={fmt.pct(d.satisfied_rate)}
                detail="Evaluaron Buena o Excelente (4–5)" />
              <Kpi icon="😞" label="Insatisfechos" value={fmt.pct(d.dissatisfied_rate)}
                detail="Evaluaron Mala o Muy mala (1–2)"
                info="Conviene revisar estos casos: el listado de abajo muestra qué trámite evaluaron." />
            </div>
            <div className="grid two">
              <Card title="Reparto de notas" desc="Cuántos pacientes eligieron cada opción">
                <HBars labelWidth={110} category="name"
                  data={[5, 4, 3, 2, 1].map((r) => ({ name: RATING[r], n: d.distribution[r] || 0 }))}
                  series={[{ key: "n", label: "Respuestas", color: "var(--series-1)" }]} />
              </Card>
              <Card title="Nota promedio por día" desc="Los días con pocas respuestas varían más"
                info="Pasa el mouse sobre la línea para ver el promedio de cada día.">
                <TimeLines data={d.by_day} format={(v) => fmt.dec(v)} domain={[1, 5]} target={{ value: 4.5, label: "Meta 4,5" }}
                  series={[{ key: "avg", label: "Promedio", color: "var(--series-1)" }]} />
              </Card>
            </div>
          </Section>

          <Section title="Por trámite evaluado" desc="Qué servicio estaba usando el paciente cuando respondió la encuesta.">
            <div className="card">
              {d.by_service.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>Trámite</th><th className="r">Respuestas</th><th>Nota promedio</th>
                        <th className="r">Satisfechos</th><th className="r">Insatisfechos</th></tr>
                    </thead>
                    <tbody>
                      {d.by_service.map((s) => (
                        <tr key={s.service}>
                          <td><b>{LABEL[s.service] || s.service}</b></td>
                          <td className="r">{fmt.int(s.n)}</td>
                          <td className="bar-cell">
                            <InlineBar value={s.avg == null ? 0 : (s.avg - 1) / 4} tone={s.avg >= 4.5 ? "good" : "below"} />
                            <span className="num">{s.avg == null ? "—" : fmt.dec(s.avg)}</span>
                          </td>
                          <td className="r">{fmt.pct(s.satisfied_rate)}</td>
                          <td className="r">{fmt.pct(s.dissatisfied_rate)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="empty">Sin respuestas en el período.</div>}
              <p className="foot-note">La barra se marca en verde cuando el promedio alcanza la meta de 4,5.</p>
            </div>
          </Section>

          <Section title="Últimas respuestas" desc="Las 50 evaluaciones más recientes. El paciente aparece con un código seudónimo, sin su teléfono.">
            <div className="card">
              {d.recent.length ? (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Fecha</th><th>Calificación</th><th>Trámite</th><th>CESFAM</th><th>Canal</th><th>Paciente</th></tr></thead>
                    <tbody>
                      {d.recent.map((r, i) => (
                        <tr key={`${r.ts}-${i}`}>
                          <td className="num">{fmt.datetime(r.ts)}</td>
                          <td><Stars n={r.rating} /> <span className="small">{RATING[r.rating]}</span></td>
                          <td>{LABEL[r.service || "sin_dato"] || r.service}</td>
                          <td>{r.center ? centerName(r.center) : <span className="muted">—</span>}</td>
                          <td>{r.channel === "web" ? <span className="tag">simulador</span> : "WhatsApp"}</td>
                          <td className="muted small num">{r.user || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="empty">Sin respuestas en el período.</div>}
            </div>
          </Section>
        </div>
      )}
    </>
  );
}
