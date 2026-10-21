import { useEffect, useState } from "react";
import { api, download, fmt, SERVICE_LABEL } from "../api.js";
import Kpi from "../components/Kpi.jsx";
import { HBars, TimeLines } from "../components/charts.jsx";

const PERIODS = [7, 30, 90];
const CHANNELS = [
  { id: "", label: "Todos" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "web", label: "Simulador" },
];
const NLU_LABEL = { rasa: "Rasa NLU", llm: "LLM (respaldo)", rules: "Reglas (modo degradado)", fallback: "No entendido",
  safety: "Detector de alarmas", error: "Error del NLU" };
const NIVEL = [
  { key: "urgencia", label: "🔴 Urgencia" },
  { key: "prioritario", label: "🟠 Prioritario" },
  { key: "control", label: "🟡 Consulta CESFAM" },
  { key: "autocuidado", label: "🟢 Autocuidado" },
];
const DOC = { interconsulta: "Interconsulta", examenes: "Exámenes", receta: "Receta", urgente: "Derivación urgente", otro: "Otro" };

export default function Resumen() {
  const [days, setDays] = useState(30);
  const [center, setCenter] = useState("");
  const [channel, setChannel] = useState("");
  const [centers, setCenters] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api("/agendamiento/catalog").then((c) => setCenters(c.centers)).catch(() => {});
  }, []);

  useEffect(() => {
    const params = { days, center, channel };
    setLoading(true);
    Promise.all([
      api("/analytics/kpis", { params }),
      api("/analytics/timeseries", { params }),
      api("/analytics/services", { params }),
      api("/analytics/intents", { params }),
    ])
      .then(([k, ts, sv, it]) => { setData({ k, ts, sv, it }); setErr(""); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [days, center, channel]);

  const k = data?.k;
  const t = k?.targets || {};
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Indicadores de MedicAI</h1>
          <p>Desempeño del asistente frente a las metas comprometidas en la formulación.</p>
        </div>
        <div className="filters" role="group" aria-label="Filtros">
          <div className="seg" role="group" aria-label="Período">
            {PERIODS.map((d) => (
              <button key={d} aria-pressed={days === d} onClick={() => setDays(d)}>{d} días</button>
            ))}
          </div>
          <select value={center} onChange={(e) => setCenter(e.target.value)} aria-label="CESFAM">
            <option value="">Todos los CESFAM</option>
            {centers.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
          <div className="seg" role="group" aria-label="Canal">
            {CHANNELS.map((c) => (
              <button key={c.id} aria-pressed={channel === c.id} onClick={() => setChannel(c.id)}>{c.label}</button>
            ))}
          </div>
          <button className="btn" onClick={() => download("/analytics/export.csv", { days, center, channel }, "medicai_eventos.csv")}>
            ⬇ Exportar CSV
          </button>
        </div>
      </div>

      {channel !== "whatsapp" && (
        <div className="banner">
          ℹ️ Esta vista incluye conversaciones del <b>simulador</b> (pruebas internas). Para evidencia con pacientes reales
          filtra por <b>WhatsApp</b>.
        </div>
      )}
      {center && (
        <div className="banner">Filtrar por CESFAM solo aplica a eventos con centro (citas, farmacia); los indicadores de conversación quedan en cero.</div>
      )}
      {err && <div className="card error" role="alert">No se pudieron cargar los indicadores: {err}</div>}

      {k && (
        <div className={loading ? "loading" : ""}>
          <div className="grid kpis">
            <Kpi label="Usuarios únicos" value={fmt.int(k.unique_users)} detail={`${fmt.int(k.interactions)} interacciones`} />
            <Kpi label="Resolución autónoma" value={fmt.pct(k.autonomous_resolution_rate.value)}
              detail={`${fmt.int(k.autonomous_resolution_rate.num)} de ${fmt.int(k.autonomous_resolution_rate.den)} trámites iniciados`}
              target={t.autonomous_resolution_rate} />
            <Kpi label="Tiempo de respuesta (p95)" value={fmt.ms(k.latency_p95_ms)}
              detail={`Mediana ${fmt.ms(k.latency_p50_ms)} · extremo a extremo p95 ${fmt.ms(k.end_to_end_p95_ms)}`}
              target={t.latency_p95_ms} />
            <Kpi label="Satisfacción" value={k.satisfaction_avg.value == null ? "—" : `${fmt.dec(k.satisfaction_avg.value)} / 5`}
              detail={`${fmt.int(k.satisfaction_avg.n)} respuestas a la encuesta`} target={t.satisfaction_avg} />
            <Kpi label="Mensajes no entendidos" value={fmt.pct(k.fallback_rate.value)}
              detail={`${fmt.int(k.fallback_rate.num)} de ${fmt.int(k.fallback_rate.den)} mensajes de texto`} target={t.fallback_rate} />
            <Kpi label="Adherencia a tomas" value={fmt.pct(k.adherence_rate.value)}
              detail={`${fmt.int(k.doses.taken)} tomadas · ${fmt.int(k.doses.skipped)} omitidas · ${fmt.int(k.doses.expired)} sin respuesta`}
              target={t.adherence_rate} />
            <Kpi label="Inasistencia a citas" value={fmt.pct(k.no_show_rate.value)}
              detail={`${fmt.int(k.appointments_booked)} horas agendadas · ${fmt.int(k.attendance_confirmed)} confirmaron asistencia`} />
            <Kpi label="Alertas de urgencia" value={fmt.int(k.red_flags)}
              detail={`${fmt.int(k.human_handoff_offered)} derivaciones a atención humana`} />
          </div>

          <div className="grid two">
            <div className="card">
              <div className="card-head"><div><h2>Actividad diaria</h2><p>Interacciones y trámites resueltos por día</p></div></div>
              <TimeLines data={data.ts} series={[
                { key: "interactions", label: "Interacciones", color: "var(--series-1)" },
                { key: "flows_resolved", label: "Trámites resueltos", color: "var(--series-2)" },
              ]} />
            </div>
            <div className="card">
              <div className="card-head"><div><h2>Tiempo de respuesta p95 por día</h2><p>Procesamiento del asistente, sin contar la red de WhatsApp</p></div></div>
              <TimeLines data={data.ts} format={fmt.ms} target={{ value: 5000, label: "Meta 5 s" }}
                series={[{ key: "latency_p95_ms", label: "p95", color: "var(--series-1)" }]} />
            </div>
          </div>

          <div className="grid two">
            <div className="card">
              <div className="card-head"><div><h2>Uso por microservicio</h2><p>Trámites iniciados y resueltos sin intervención humana</p></div></div>
              <HBars data={data.sv.map((s) => ({ ...s, name: SERVICE_LABEL[s.service] || s.service }))} category="name"
                series={[
                  { key: "started", label: "Iniciados", color: "var(--series-1)" },
                  { key: "resolved", label: "Resueltos", color: "var(--series-2)" },
                ]} />
              {data.sv.length > 0 && (
                <div className="table-wrap" style={{ marginTop: 10 }}>
                  <table>
                    <thead><tr><th>Servicio</th><th className="r">Resolución</th><th className="r">Abandonos</th><th className="r">Turnos prom.</th><th className="r">Duración prom.</th></tr></thead>
                    <tbody>
                      {data.sv.map((s) => (
                        <tr key={s.service}>
                          <td>{SERVICE_LABEL[s.service] || s.service}</td>
                          <td className="r">{fmt.pct(s.resolution_rate)}</td>
                          <td className="r">{fmt.int(s.abandoned)}</td>
                          <td className="r">{fmt.dec(s.avg_turns)}</td>
                          <td className="r">{s.avg_duration_s == null ? "—" : `${fmt.dec(s.avg_duration_s, 0)} s`}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="card">
              <div className="card-head"><div><h2>¿Quién interpretó los mensajes?</h2><p>Capa del NLU híbrido que resolvió cada mensaje de texto</p></div></div>
              <HBars data={Object.entries(k.nlu_sources).map(([s, n]) => ({ name: NLU_LABEL[s] || "Sin registro", n }))}
                category="name" series={[{ key: "n", label: "Mensajes", color: "var(--series-1)" }]} />
              <h2 style={{ margin: "18px 0 8px" }}>Intenciones más frecuentes</h2>
              {data.it.length ? (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Intención</th><th className="r">Mensajes</th><th className="r">Confianza prom.</th></tr></thead>
                    <tbody>
                      {data.it.slice(0, 8).map((i) => (
                        <tr key={i.intent}><td>{i.intent}</td><td className="r">{fmt.int(i.total)}</td><td className="r">{fmt.pct(i.avg_confidence)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="empty">Sin mensajes de texto en el período.</div>}
            </div>
          </div>

          <div className="grid two">
            <div className="card">
              <div className="card-head"><div><h2>Orientación de síntomas</h2><p>Nivel de atención sugerido</p></div></div>
              <HBars data={NIVEL.map((n) => ({ name: n.label, n: k.triage[n.key] || 0 }))} category="name"
                series={[{ key: "n", label: "Orientaciones", color: "var(--series-1)" }]} />
            </div>
            <div className="card">
              <div className="card-head"><div><h2>Satisfacción usuaria</h2><p>Respuestas a la encuesta post-atención (1 a 5)</p></div></div>
              <HBars data={[[5, "Excelente"], [4, "Buena"], [3, "Regular"], [2, "Mala"], [1, "Muy mala"]].map(([r, l]) => ({ name: `${r} · ${l}`, n: k.satisfaction_avg.distribution[r] || 0 }))}
                category="name" series={[{ key: "n", label: "Respuestas", color: "var(--series-1)" }]} />
              <h2 style={{ margin: "18px 0 8px" }}>Guía de ruta por tipo de documento</h2>
              <HBars data={Object.entries(k.referrals).map(([d, n]) => ({ name: DOC[d] || d, n }))} category="name"
                series={[{ key: "n", label: "Consultas", color: "var(--series-1)" }]} />
            </div>
          </div>
        </div>
      )}
      {!k && loading && <div className="empty">Cargando indicadores…</div>}
    </>
  );
}
