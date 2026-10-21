import { useEffect, useState } from "react";
import { api, download, fmt, SERVICE_LABEL } from "../api.js";
import Kpi, { TargetCard } from "../components/Kpi.jsx";
import Info from "../components/Info.jsx";
import { HBars, InlineBar, MiniTrend, SegmentBar, TimeLines } from "../components/charts.jsx";

const PERIODS = [7, 30, 90];
const CHANNELS = [
  { id: "", label: "Todos" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "web", label: "Simulador" },
];
const NLU = [
  { key: "rasa", label: "Rasa NLU", hint: "modelo principal", color: "var(--series-1)" },
  { key: "llm", label: "LLM de respaldo", hint: "cuando Rasa duda", color: "var(--series-2)" },
  { key: "rules", label: "Reglas", hint: "modo degradado", color: "var(--series-3)" },
  { key: "safety", label: "Detector de alarmas", color: "var(--series-4)" },
  { key: "fallback", label: "No entendido", color: "var(--axis)" },
];
const NIVEL = [
  { key: "urgencia", label: "Urgencia", color: "var(--critical)" },
  { key: "prioritario", label: "Prioritario", color: "var(--serious)" },
  { key: "control", label: "Consulta en CESFAM", color: "var(--warning)" },
  { key: "autocuidado", label: "Autocuidado", color: "var(--good)" },
];
const DOC = { interconsulta: "Interconsulta", examenes: "Exámenes", receta: "Receta", urgente: "Derivación urgente", otro: "Otro" };
const INTENT = {
  agendar_cita: "Agendar hora", ver_citas: "Ver mis horas", cancelar_cita: "Cancelar hora",
  recordatorio_medicamento: "Crear recordatorio", ver_recordatorios: "Ver recordatorios",
  orientacion_sintomas: "Orientación de síntomas", guia_ruta: "Guía de ruta", farmacia: "Farmacia",
  ver_retiros: "Ver retiros", saludo: "Saludo", despedida: "Despedida", agradecer: "Agradecimiento",
  menu: "Menú", ayuda: "Ayuda", cancelar: "Cancelar", afirmar: "Sí", negar: "No", emergencia: "Emergencia",
  nlu_fallback: "No entendido",
};

function rangeLabel(days) {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - (days - 1));
  const f = (d) => d.toLocaleDateString("es-CL", { day: "numeric", month: "short" });
  return `${f(start)} – ${f(end)}`;
}

function Section({ title, desc, aside, children }) {
  return (
    <section className="section">
      <div className="section-head">
        <div>
          <h2>{title}</h2>
          {desc && <p>{desc}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

function Card({ title, desc, info, children, className = "" }) {
  return (
    <div className={`card ${className}`}>
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          {desc && <p>{desc}</p>}
        </div>
        {info && <Info>{info}</Info>}
      </div>
      {children}
    </div>
  );
}

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
  const metas = Object.values(t).filter((x) => x.status);
  const cumplidas = metas.filter((x) => x.status === "ok").length;
  const resueltos = k?.autonomous_resolution_rate.num ?? 0;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Indicadores · {rangeLabel(days)}</p>
          <h1>¿Cómo está funcionando MedicAI?</h1>
          <p>Uso del asistente y avance frente a las metas comprometidas en la formulación del proyecto.</p>
        </div>
        <button className="btn" onClick={() => download("/analytics/export.csv", { days, center, channel }, "medicai_eventos.csv")}>
          ⬇ Exportar CSV
        </button>
      </header>

      <div className="toolbar" role="group" aria-label="Filtros">
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
        {channel !== "whatsapp" && (
          <span className="toolbar-note">ℹ️ Incluye pruebas del simulador. Para evidencia con pacientes reales, elige <b>WhatsApp</b>.</span>
        )}
      </div>
      {center && (
        <div className="banner">El filtro por CESFAM solo aplica a citas y farmacia; los indicadores de conversación quedan en cero.</div>
      )}
      {err && <div className="card error" role="alert">No se pudieron cargar los indicadores: {err}</div>}
      {!k && loading && <div className="empty">Cargando indicadores…</div>}

      {k && (
        <div className={loading ? "loading" : ""}>
          <Section title="Metas del proyecto"
            desc="Cada tarjeta muestra el valor del período, una barra con la meta marcada y si se cumple."
            aside={metas.length > 0 && (
              <span className={`status-pill ${cumplidas === metas.length ? "ok" : "below"}`}>
                {cumplidas} de {metas.length} metas cumplidas
              </span>
            )}>
            <div className="grid targets">
              <TargetCard label="Resolución autónoma" value={fmt.pct(k.autonomous_resolution_rate.value)}
                raw={k.autonomous_resolution_rate.value} target={t.autonomous_resolution_rate} scale={[0, 1]} format={fmt.pct}
                desc="Trámites que terminan con éxito sin ayuda de un funcionario."
                detail={`${fmt.int(k.autonomous_resolution_rate.num)} resueltos de ${fmt.int(k.autonomous_resolution_rate.den)} iniciados`}
                info="Trámites resueltos ÷ trámites iniciados. Un trámite se resuelve cuando termina con éxito: hora agendada, recordatorio creado, orientación entregada, retiro programado, etc. Incluye las respuestas de un toque a los avisos (por ejemplo «✅ Tomé el medicamento»)." />
              <TargetCard label="Tiempo de respuesta" value={fmt.ms(k.latency_p95_ms)}
                raw={k.latency_p95_ms} target={t.latency_p95_ms} format={fmt.ms}
                scale={[0, Math.max(10000, (k.latency_p95_ms || 0) * 1.2)]}
                desc="El 95 % de las respuestas tarda menos que esto."
                detail={`Mediana ${fmt.ms(k.latency_p50_ms)} · con red de WhatsApp ${fmt.ms(k.end_to_end_p95_ms)}`}
                info="Percentil 95 del tiempo que tarda el asistente en procesar un mensaje y generar la respuesta. No incluye la red de WhatsApp; ese valor aparece aparte como «con red de WhatsApp»." />
              <TargetCard label="Satisfacción"
                value={k.satisfaction_avg.value == null ? "—" : `${fmt.dec(k.satisfaction_avg.value)} / 5`}
                raw={k.satisfaction_avg.value} target={t.satisfaction_avg} scale={[1, 5]} format={(v) => fmt.dec(v)}
                desc="Nota promedio de la encuesta al terminar un trámite."
                detail={`${fmt.int(k.satisfaction_avg.n)} respuestas a la encuesta`}
                info="Promedio de las respuestas (1 = muy mala, 5 = excelente) a la encuesta que el asistente envía después de un trámite resuelto. Cada paciente la recibe como máximo una vez cada cierto tiempo." />
              <TargetCard label="Mensajes no entendidos" value={fmt.pct(k.fallback_rate.value)}
                raw={k.fallback_rate.value} target={t.fallback_rate} format={fmt.pct}
                scale={[0, Math.max(0.2, (k.fallback_rate.value || 0) * 1.25)]}
                desc="Mensajes escritos que el asistente no logró interpretar."
                detail={`${fmt.int(k.fallback_rate.num)} de ${fmt.int(k.fallback_rate.den)} mensajes de texto`}
                info="Mensajes de texto libre (no botones) en que el asistente respondió «no logré entenderte», divididos por el total de mensajes de texto. Aquí, más bajo es mejor." />
              <TargetCard label="Adherencia a tomas" value={fmt.pct(k.adherence_rate.value)}
                raw={k.adherence_rate.value} target={t.adherence_rate} scale={[0, 1]} format={fmt.pct}
                desc="Tomas de medicamento confirmadas tras el recordatorio."
                detail={`${fmt.int(k.doses.taken)} tomadas · ${fmt.int(k.doses.skipped)} omitidas · ${fmt.int(k.doses.expired)} sin respuesta`}
                info="Tomas confirmadas ÷ (confirmadas + omitidas + sin respuesta). Una toma queda «sin respuesta» si el paciente no contesta el recordatorio a tiempo." />
            </div>
          </Section>

          <Section title="Uso del asistente"
            desc="Una interacción es cada mensaje o botón que envía un paciente. Un trámite suele requerir varios mensajes, por eso siempre hay más interacciones que trámites.">
            <div className="grid stats">
              <Kpi icon="👥" label="Pacientes únicos" value={fmt.int(k.unique_users)}
                info="Personas distintas que escribieron al asistente en el período (se cuentan con un identificador seudonimizado, no con su teléfono)." />
              <Kpi icon="💬" label="Interacciones" value={fmt.int(k.interactions)}
                detail={k.unique_users ? `${fmt.dec(k.interactions / k.unique_users)} por paciente` : null}
                info="Cada mensaje escrito o botón presionado por un paciente." />
              <Kpi icon="✅" label="Trámites resueltos" value={fmt.int(resueltos)}
                detail={resueltos ? `${fmt.dec(k.interactions / resueltos)} interacciones por trámite` : null}
                info="Trámites que terminaron con éxito: hora agendada, recordatorio creado, orientación entregada, etc." />
              <Kpi icon="↩️" label="Trámites abandonados" value={fmt.int(k.flows_abandoned)}
                info="Trámites que el paciente empezó y dejó a medias (no respondió o cambió de tema)." />
            </div>
            <div className="grid three">
              <Card title="Pacientes por día">
                <MiniTrend data={data.ts} dataKey="unique_users" label="Pacientes" />
              </Card>
              <Card title="Interacciones por día">
                <MiniTrend data={data.ts} dataKey="interactions" label="Interacciones" />
              </Card>
              <Card title="Trámites resueltos por día">
                <MiniTrend data={data.ts} dataKey="flows_resolved" label="Trámites resueltos" />
              </Card>
            </div>
          </Section>

          <Section title="Trámites por servicio" desc="Cuántos trámites inicia cada microservicio y qué proporción termina resuelta.">
            <div className="card">
              {data.sv.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Servicio</th><th className="r">Iniciados</th><th className="r">Resueltos</th>
                        <th>Resolución</th><th className="r">Abandonados</th>
                        <th className="r">Mensajes por trámite</th><th className="r">Duración prom.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.sv.map((s) => (
                        <tr key={s.service}>
                          <td><b>{SERVICE_LABEL[s.service] || s.service}</b></td>
                          <td className="r">{fmt.int(s.started)}</td>
                          <td className="r">{fmt.int(s.resolved)}</td>
                          <td className="bar-cell">
                            <InlineBar value={s.resolution_rate}
                              tone={s.resolution_rate == null ? null : s.resolution_rate >= 0.85 ? "good" : "below"} />
                            <span className="num">{fmt.pct(s.resolution_rate)}</span>
                          </td>
                          <td className="r">{fmt.int(s.abandoned)}</td>
                          <td className="r">{fmt.dec(s.avg_turns)}</td>
                          <td className="r">{s.avg_duration_s == null ? "—" : `${fmt.dec(s.avg_duration_s, 0)} s`}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="empty">Sin trámites en el período.</div>}
              <p className="foot-note">La barra se marca en verde cuando el servicio alcanza la meta de 85 % de resolución.</p>
            </div>
          </Section>

          <Section title="Calidad del asistente" desc="Qué tan rápido responde y cómo interpreta lo que escriben los pacientes.">
            <div className="grid two">
              <Card title="Tiempo de respuesta por día" desc="Percentil 95 del procesamiento, sin la red de WhatsApp"
                info="Si la línea supera la meta de 5 s, ese día al menos 1 de cada 20 respuestas tardó más que la meta.">
                <TimeLines data={data.ts} format={fmt.ms} target={{ value: 5000, label: "Meta 5 s" }}
                  series={[{ key: "latency_p95_ms", label: "p95", color: "var(--series-1)" }]} />
              </Card>
              <Card title="¿Quién interpretó los mensajes?" desc="Capa del NLU que resolvió cada mensaje escrito"
                info="El asistente usa primero Rasa; si no está seguro consulta un LLM de respaldo, y si ambos fallan usa reglas simples. Las alarmas (por ejemplo «no puedo respirar») se detectan antes que todo lo demás.">
                <SegmentBar items={NLU.map((n) => ({ ...n, value: k.nlu_sources[n.key] || 0 }))} />
              </Card>
            </div>
            <Card title="Lo que más piden los pacientes" desc="Intenciones detectadas en mensajes escritos">
              {data.it.length ? (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Intención</th><th className="r">Mensajes</th><th>Confianza promedio</th></tr></thead>
                    <tbody>
                      {data.it.slice(0, 8).map((i) => (
                        <tr key={i.intent}>
                          <td>{INTENT[i.intent] || i.intent} <span className="muted small">{i.intent}</span></td>
                          <td className="r">{fmt.int(i.total)}</td>
                          <td className="bar-cell"><InlineBar value={i.avg_confidence} /><span className="num">{fmt.pct(i.avg_confidence)}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="empty">Sin mensajes de texto en el período.</div>}
            </Card>
          </Section>

          <Section title="Atención de pacientes" desc="Resultados clínicos y de gestión de los trámites.">
            <div className="grid stats">
              <Kpi icon="🗓️" label="Horas agendadas" value={fmt.int(k.appointments_booked)}
                detail={`${fmt.int(k.attendance_confirmed)} confirmaron asistencia`} />
              <Kpi icon="🚫" label="Inasistencia a citas" value={fmt.pct(k.no_show_rate.value)}
                detail={`${fmt.int(k.no_show_rate.num)} de ${fmt.int(k.no_show_rate.den)} con asistencia registrada`}
                info="Citas marcadas como «No asistió» ÷ citas con asistencia registrada por el CESFAM (asistió + no asistió)." />
              <Kpi icon="🚨" label="Alertas de urgencia" value={fmt.int(k.red_flags)}
                detail="Se indicó llamar al 131 o acudir a urgencia"
                info="Mensajes con señales de alarma (dificultad respiratoria, dolor de pecho, ideación suicida, etc.) y orientaciones clasificadas como urgencia." />
              <Kpi icon="🙋" label="Derivación a persona" value={fmt.int(k.human_handoff_offered)}
                detail="Tras 2 mensajes no entendidos seguidos"
                info="Veces en que el asistente ofreció contactar a un funcionario porque no logró entender al paciente." />
            </div>
            <div className="grid three">
              <Card title="Orientación de síntomas" desc="Nivel de atención sugerido">
                <SegmentBar items={NIVEL.map((n) => ({ ...n, value: k.triage[n.key] || 0 }))} />
              </Card>
              <Card title="Satisfacción" desc="Respuestas a la encuesta (1 a 5)">
                <HBars labelWidth={92}
                  data={[[5, "Excelente"], [4, "Buena"], [3, "Regular"], [2, "Mala"], [1, "Muy mala"]].map(([r, l]) => ({ name: `${r} · ${l}`, n: k.satisfaction_avg.distribution[r] || 0 }))}
                  category="name" series={[{ key: "n", label: "Respuestas", color: "var(--series-1)" }]} />
              </Card>
              <Card title="Guía de ruta" desc="Consultas por tipo de documento">
                <HBars labelWidth={120}
                  data={Object.entries(k.referrals).sort((a, b) => b[1] - a[1]).map(([d, n]) => ({ name: DOC[d] || d, n }))}
                  category="name" series={[{ key: "n", label: "Consultas", color: "var(--series-1)" }]} />
              </Card>
            </div>
          </Section>
        </div>
      )}
    </>
  );
}
