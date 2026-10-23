import { useEffect, useState } from "react";
import { api, fmt } from "../api.js";
import Kpi, { TargetCard } from "../components/Kpi.jsx";
import { Card, Section } from "../components/Section.jsx";
import { HBars, MiniTrend, ThresholdBars, TimeLines } from "../components/charts.jsx";

const INTENT = {
  agendar_cita: "Agendar hora", ver_citas: "Ver mis horas", cancelar_cita: "Reprogramar o cancelar",
  orientacion_sintomas: "Síntomas", salud_mental: "Salud mental", resultados_examenes: "Resultados",
  tramites_fonasa: "FONASA", recordatorio_medicamento: "Recordatorios", farmacia: "Farmacia",
  guia_ruta: "Guía de ruta", hablar_persona: "Hablar con persona", modo_cuidador: "Modo cuidador",
  info_hospital: "Info del hospital", visitas: "Visitas", preparacion_examenes: "Preparación de exámenes",
  emergencia: "Emergencia", nlu_fallback: "No entendido", ver_recordatorios: "Mis recordatorios", ver_retiros: "Mis retiros",
  menu: "Menú", ayuda: "Ayuda", cancelar: "Cancelar",
};
const ALERTA = {
  critical: { icon: "🔴", label: "Crítica" },
  warning: { icon: "🟠", label: "Atención" },
  good: { icon: "🟢", label: "Positivo" },
  info: { icon: "🔵", label: "Info" },
};
const SUGERENCIAS = ["¿Cómo va el ausentismo?", "¿Cuántas camas UCI quedan?", "¿Cómo está urgencias?",
  "¿Cómo van las listas de espera?", "¿Y los pabellones?", "¿Cómo va el chatbot?"];
const minutes = (v) => (v == null ? "—" : `${Math.round(v)} min`);

/** Formato estilo WhatsApp (*negrita*) sin innerHTML. */
function Rich({ text }) {
  return String(text).split("\n").map((line, i) => (
    <p key={i} className="rich-line">
      {line.split(/(\*[^*]+\*)/g).map((p, j) => (/^\*[^*]+\*$/.test(p) ? <b key={j}>{p.slice(1, -1)}</b> : p))}
    </p>
  ));
}

function Ask() {
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState(null);
  const [busy, setBusy] = useState(false);
  async function send(question) {
    if (!question.trim()) return;
    setBusy(true);
    try {
      setAnswer({ question, ...(await api("/analytics/ask", { method: "POST", body: { question } })) });
    } catch (e) {
      setAnswer({ question, answer: `No pude responder: ${e.message}` });
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Pregúntale al sistema" desc="Analítica conversacional: escribe una pregunta sobre la operación del hospital"
      info="Responde con el número clave, el contexto y una sugerencia operativa. Usa solo datos agregados: nunca muestra pacientes identificables.">
      <form className="ask" onSubmit={(e) => { e.preventDefault(); send(q); }}>
        <input type="text" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ej: ¿cómo va el ausentismo este mes?"
          aria-label="Pregunta" />
        <button className="btn primary" disabled={busy || !q.trim()}>{busy ? "Consultando…" : "Preguntar"}</button>
      </form>
      <div className="chips">
        {SUGERENCIAS.map((s) => <button key={s} className="chip" onClick={() => { setQ(s); send(s); }}>{s}</button>)}
      </div>
      {answer && (
        <div className="answer" aria-live="polite">
          <div className="muted small">{answer.question}</div>
          <Rich text={answer.answer} />
        </div>
      )}
    </Card>
  );
}

export default function Hospital() {
  const [h, setH] = useState(null);
  const [bot, setBot] = useState(null);
  const [err, setErr] = useState("");

  function load() {
    Promise.all([api("/analytics/hospital"), api("/analytics/chatbot/panel", { params: { days: 14 } })])
      .then(([hh, bb]) => { setH(hh); setBot(bb); setErr(""); })
      .catch((e) => setErr(e.message));
  }
  useEffect(() => {
    load();
    const id = setInterval(load, 60000); // tablero en vivo
    return () => clearInterval(id);
  }, []);

  const u = h?.urgencias;
  const today = h?.agenda?.today;
  const daily = h?.agenda?.daily || [];
  const recuperadas = daily.reduce((a, d) => a + (d.gap_filled || 0), 0);
  const espera = u ? { value: u.meta_min, op: "<=", status: u.espera_media_min <= u.meta_min ? "ok" : "below" } : null;
  const autores = bot?.auto_resolution?.value;
  const autoTarget = { value: 0.8, op: ">=", status: autores == null ? null : autores >= 0.8 ? "ok" : "below" };

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Gestión hospitalaria · en vivo</p>
          <h1>Hospital Regional de Talca</h1>
          <p>Operación del hospital, agenda y chatbot en un solo tablero. Se actualiza cada minuto.</p>
        </div>
        {h && <span className="muted small">Actualizado {new Date(h.generado).toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" })}</span>}
      </header>
      <div className="banner">
        🧪 <b>Prototipo:</b> camas, urgencias, pabellones y listas de espera son <b>datos simulados</b> (en producción vienen del
        HIS vía HL7 FHIR). La agenda, el ausentismo, el fill-the-gap y el chatbot son <b>datos reales</b> del sistema.
      </div>
      {err && <div className="card error" role="alert">No se pudo cargar el tablero: {err}</div>}
      {!h && !err && <div className="empty">Cargando tablero…</div>}

      {h && (
        <>
          <Section title="Ahora">
            <div className="grid stats">
              <Kpi icon="🛏️" label="Ocupación de camas" value={fmt.pct(h.ocupacion_global)}
                detail={`${fmt.int(h.camas.reduce((a, c) => a + c.ocupadas, 0))} de ${fmt.int(h.camas_total)} camas`} />
              <Kpi icon="🫀" label="Camas UCI disponibles" value={fmt.int(h.uci_disponibles)} detail={`UCI al ${fmt.pct(h.uci_pct)}`} />
              <Kpi icon="🚑" label="En espera en urgencia" value={fmt.int(u.en_espera)} detail={`${u.boarding} esperando cama`} />
              <TargetCard label="Espera media en urgencia" value={minutes(u.espera_media_min)} raw={u.espera_media_min}
                target={espera} format={minutes} scale={[0, Math.max(60, u.espera_media_min * 1.3)]}
                desc="Tiempo promedio desde la llegada hasta la atención." />
              <Kpi icon="📉" label="Ausentismo de hoy" value={fmt.pct(today?.no_show_rate)}
                detail={today ? `${fmt.int(today.no_show)} no asistieron` : "Sin datos de agenda"}
                info="Inasistencias ÷ citas con asistencia registrada hoy (hospital y CESFAM)." />
              <Kpi icon="✅" label="Citas atendidas hoy" value={fmt.int(today?.attended)}
                detail={today ? `de ${fmt.int(today.scheduled)} agendadas` : ""} />
              <TargetCard label="Auto-resolución del chatbot" value={fmt.pct(autores)} raw={autores} target={autoTarget}
                scale={[0, 1]} format={fmt.pct} desc="Trámites resueltos sin intervención humana (14 días)." />
            </div>
          </Section>

          <Section title="Alertas" desc="Reglas automáticas sobre la operación y la agenda.">
            {h.alertas.length ? (
              <div className="grid alerts">
                {h.alertas.map((a, i) => (
                  <div key={i} className={`card alert alert-${a.level}`}>
                    <div className="alert-head"><span aria-hidden="true">{ALERTA[a.level]?.icon}</span>
                      <span className="alert-tag">{ALERTA[a.level]?.label}</span><b>{a.title}</b></div>
                    <p>{a.detail}</p>
                  </div>
                ))}
              </div>
            ) : <div className="card empty">Sin alertas activas. ✅</div>}
          </Section>

          <Section title="Pregunta en lenguaje natural">
            <Ask />
          </Section>

          <Section title="Camas y urgencias">
            <div className="grid two">
              <Card title="Ocupación por servicio" desc="Umbrales en 80 % y 90 %">
                <ThresholdBars rows={h.camas.map((c) => ({ label: c.servicio, value: c.pct, detail: `${c.ocupadas}/${c.total}` }))} />
              </Card>
              <Card title="Llegadas a urgencia por hora" desc={`Hoy frente al promedio · peak habitual ${u.pico_hora}`}>
                <TimeLines data={u.llegadas} xKey="hora" xFormat={(x) => x}
                  series={[{ key: "hoy", label: "Hoy", color: "var(--series-1)" },
                    { key: "promedio", label: "Promedio 7 días", color: "var(--series-2)" }]} />
              </Card>
            </div>
          </Section>

          <Section title="Agenda, ausentismo y fill-the-gap" desc="Datos reales de la agenda del hospital y los CESFAM.">
            <div className="grid two">
              <Card title="Ausentismo últimos 14 días" desc="Inasistencias sobre citas con asistencia registrada">
                {daily.some((d) => d.no_show_rate != null) ? (
                  <TimeLines data={daily} format={fmt.pct} target={{ value: 0.1, label: "Meta 10 %" }}
                    series={[{ key: "no_show_rate", label: "Ausentismo", color: "var(--series-1)" }]} />
                ) : (
                  <div className="empty">Aún no hay asistencia registrada. Se llena cuando los equipos marcan
                    «Asistió / No asistió» en la Agenda.</div>
                )}
              </Card>
              <Card title="Horas recuperadas por fill-the-gap" desc={`${fmt.int(recuperadas)} en 14 días · cupos liberados que tomó la lista de espera`}
                info="Cuando un paciente cancela, el sistema ofrece el cupo al siguiente de la lista de espera (GES primero, luego antigüedad).">
                <MiniTrend data={daily} dataKey="gap_filled" label="Horas recuperadas" height={200} />
              </Card>
            </div>
          </Section>

          {bot && (
            <Section title="Chatbot" desc="Uso del asistente en los últimos 14 días.">
              <div className="grid stats">
                <Kpi icon="🏠" label="Consultas desviadas a APS" value={fmt.int(bot.desvio_aps_total)}
                  detail="Orientaciones a CESFAM o autocuidado"
                  info="Personas que consultaron por síntomas y el triaje les indicó atenderse en su CESFAM o en casa, en vez de ir a urgencia." />
                <Kpi icon="📋" label="Resultados avisados en < 5 min" value={fmt.pct(bot.results_within_5_min)}
                  detail={`${fmt.int(bot.results_notified)} avisos enviados`} />
                <Kpi icon="💬" label="Derivaciones a una persona" value={fmt.int(bot.handoffs)} detail="Ver bandeja en Contacto" />
                <Kpi icon="👪" label="Sesiones en modo cuidador" value={fmt.int(bot.caregiver_sessions)} />
              </div>
              <div className="grid two">
                <Card title="Temas del chatbot" desc="Intenciones de los mensajes escritos (% del total)">
                  <HBars labelWidth={150} format={(v) => `${Math.round(v)} %`} category="name"
                    data={bot.temas.map((t) => ({ name: INTENT[t.intent] || t.intent, n: Math.round(t.pct * 1000) / 10 }))}
                    series={[{ key: "n", label: "Mensajes", color: "var(--series-1)" }]} />
                </Card>
                <Card title="Desvío de baja complejidad a APS por día">
                  <MiniTrend data={bot.desvio_aps} dataKey="n" label="Consultas desviadas" height={200} />
                </Card>
              </div>
            </Section>
          )}

          <Section title="Pabellones y listas de espera">
            <div className="grid stats">
              <Kpi icon="🔪" label="Utilización de pabellones" value={fmt.pct(h.pabellones.utilizacion)}
                detail={`${h.pabellones.cirugias_programadas} cirugías programadas hoy`} />
              <Kpi icon="⛔" label="Suspensiones hoy" value={fmt.int(h.pabellones.suspensiones)}
                detail={`Puntualidad 1.ª hora ${fmt.pct(h.pabellones.puntualidad_primera_hora)}`} />
              <Kpi icon="⏳" label="Pacientes en lista de espera" value={fmt.int(h.listas_espera.pacientes)}
                detail={`Mediana ${h.listas_espera.mediana_dias} días`} />
              <Kpi icon="🛡️" label="Cumplimiento GES" value={fmt.pct(h.listas_espera.cumplimiento_ges)} />
            </div>
            <Card title="Espera mediana por especialidad" desc="Días desde la interconsulta">
              <HBars labelWidth={110} category="name"
                data={[...h.listas_espera.por_especialidad].sort((a, b) => b.mediana_dias - a.mediana_dias)
                  .map((e) => ({ name: e.especialidad, n: e.mediana_dias }))}
                series={[{ key: "n", label: "Días", color: "var(--series-1)" }]} />
            </Card>
          </Section>
        </>
      )}
    </>
  );
}
