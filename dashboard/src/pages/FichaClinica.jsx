import { useEffect, useRef, useState } from "react";
import { api, fmt, stream } from "../api.js";

const MOTIVOS = [
  ["atencion", "Atención en curso"],
  ["interconsulta", "Interconsulta / derivación"],
  ["continuidad", "Continuidad de la atención"],
  ["urgencia", "Urgencia (acceso excepcional)"],
];
const ESTADO_FUENTE = {
  pendiente: ["⏳", "Consultando…"],
  ok: ["✓", "Con registros"],
  sin_registros: ["—", "Sin registros del paciente"],
  error: ["✕", "Error"],
  tiempo_agotado: ["⌛", "Sin respuesta"],
};
const EXAMEN = { alto: ["▲", "Alto", "ex-alto"], bajo: ["▼", "Bajo", "ex-bajo"], normal: ["", "En rango", ""],
  sin_rango: ["", "Sin rango de referencia", ""], sin_valor: ["", "Informe", ""] };

function Cita({ c, otras = [] }) {
  return (
    <span className="cita">
      {c}
      {otras.length > 0 && <> · también en {otras.length} registro(s) más</>}
    </span>
  );
}

function Lista({ items, vacio, render, max = 6 }) {
  const [all, setAll] = useState(false);
  if (!items.length) return <p className="faltante">{vacio}</p>;
  const shown = all ? items : items.slice(0, max);
  return (
    <>
      <ul className="clin-list">{shown.map(render)}</ul>
      {items.length > max && (
        <button className="btn small" onClick={() => setAll(!all)}>{all ? "Ver menos" : `Ver ${items.length - max} más`}</button>
      )}
    </>
  );
}

function Fuentes({ fuentes }) {
  return (
    <div className="fuentes" aria-live="polite">
      {fuentes.map((f) => {
        const [ico, txt] = ESTADO_FUENTE[f.estado] || ["?", f.estado];
        return (
          <span key={f.id} className={`fuente f-${f.estado}`} title={f.error || txt}>
            <b>{ico}</b> {f.nombre || f.id}
            <small>{txt}{f.estado !== "pendiente" && f.ms != null ? ` · ${fmt.ms(f.ms)}` : ""}</small>
          </span>
        );
      })}
    </div>
  );
}

function Perfil({ p }) {
  const r = p.resumen;
  const [todos, setTodos] = useState(false);
  const examenes = todos ? p.examenes : p.examenes.slice(0, 10);
  return (
    <>
      <div className="card section">
        <div className="card-head">
          <div>
            <h3>1 · Resumen instantáneo</h3>
            <p>Condiciones activas, medicamentos vigentes, alergias y alertas. Cada dato con su fuente.</p>
          </div>
          {r.alertas_altas > 0 && <span className="status-pill below">⚠ {r.alertas_altas} alerta(s) alta(s)</span>}
        </div>
        <div className="grid three">
          <div>
            <h4 className="clin-h">Condiciones activas</h4>
            <Lista items={r.condiciones_activas} vacio="No se encontró registro de condiciones activas en las fuentes disponibles."
              render={(c) => <li key={c.id}><b>{c.texto}</b><Cita c={c.cita} otras={c.otras_citas} /></li>} />
          </div>
          <div>
            <h4 className="clin-h">Medicamentos vigentes</h4>
            <Lista items={r.medicamentos_vigentes} vacio="No se encontró registro de medicamentos vigentes en las fuentes disponibles."
              render={(m) => <li key={m.id}><b>{m.texto}</b>{m.dosis && <span className="small"> — {m.dosis}</span>}<Cita c={m.cita} /></li>} />
          </div>
          <div>
            <h4 className="clin-h">Alergias</h4>
            <Lista items={r.alergias} vacio="No se encontró registro de alergias en las fuentes disponibles."
              render={(a) => <li key={a.id} className="alergia"><b>⚠ {a.texto}</b>{a.reaccion && <span className="small"> — {a.reaccion}</span>}<Cita c={a.cita} otras={a.otras_citas} /></li>} />
          </div>
        </div>
        {r.faltantes.length > 0 && (
          <div className="banner" role="note">{r.faltantes.map((f, i) => <div key={i}>ℹ️ {f}</div>)}</div>
        )}
      </div>

      <div className="card section">
        <div className="card-head">
          <div>
            <h3>3 · Alertas clínicas</h3>
            <p>Controles pendientes, posibles interacciones y signos de riesgo. Son sugerencias para evaluar.</p>
          </div>
        </div>
        {p.alertas.length === 0 ? <p className="muted">No se generaron alertas con las reglas configuradas.</p> : (
          <ul className="alertas">
            {p.alertas.map((a, i) => (
              <li key={i} className={`alerta nivel-${a.nivel}`}>
                <span className="alerta-nivel">{a.nivel === "alta" ? "⚠ Alta" : "● Media"}</span>
                <div>
                  <b>{a.texto}</b> <span className="tag">{a.codigo}</span>
                  <div className="small">{a.sugerencia}</div>
                  {a.citas.map((c, j) => <Cita key={j} c={c} />)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card section">
        <div className="card-head">
          <div>
            <h3>2 · Línea de tiempo de exámenes</h3>
            <p>Más reciente primero. Fuera de rango se marca con ▲/▼ y texto, no solo con color.</p>
          </div>
        </div>
        {p.examenes.length === 0 ? <p className="faltante">No se encontraron resultados de exámenes en las fuentes disponibles.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Fecha</th><th>Examen</th><th className="r">Resultado</th><th>Referencia</th><th>Estado</th><th>Fuente</th></tr></thead>
              <tbody>
                {examenes.map((e) => {
                  const [ico, txt, cls] = EXAMEN[e.estado] || ["", e.estado, ""];
                  return (
                    <tr key={e.id} className={cls}>
                      <td className="num">{fmt.date(e.fecha)}</td>
                      <td>{e.nombre}<span className="tag">{e.area}</span></td>
                      <td className="r">{e.valor != null ? <b>{ico} {fmt.dec(e.valor, e.valor % 1 ? 1 : 0)} {e.unidad}</b> : <span className="small">{e.informe}</span>}</td>
                      <td className="small">{e.rango ? `${e.rango} ${e.unidad || ""}` : "—"}</td>
                      <td className="small">{txt}</td>
                      <td><Cita c={e.cita} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {p.examenes.length > 10 && <button className="btn small" onClick={() => setTodos(!todos)}>{todos ? "Ver menos" : `Ver los ${p.examenes.length}`}</button>}
      </div>

      <details className="card section">
        <summary><b>Antecedentes, controles y atenciones previas</b> <span className="muted small">(detalle a solicitud)</span></summary>
        <div className="grid three" style={{ marginTop: 12 }}>
          <div>
            <h4 className="clin-h">Antecedentes</h4>
            <Lista items={p.antecedentes} vacio="No se encontraron antecedentes en las fuentes disponibles."
              render={(a) => <li key={a.id}>{a.texto}<Cita c={a.cita} /></li>} />
          </div>
          <div>
            <h4 className="clin-h">Controles</h4>
            <Lista items={p.controles} vacio="No se encontraron controles programados."
              render={(c) => <li key={c.id}>{c.texto} · {c.estado}{c.programado && ` (${fmt.date(c.programado)})`}<Cita c={c.cita} /></li>} />
          </div>
          <div>
            <h4 className="clin-h">Atenciones</h4>
            <Lista items={p.atenciones} vacio="No se encontraron atenciones registradas."
              render={(c) => <li key={c.id}><b>{c.texto}</b>{c.resumen && <div className="small">{c.resumen}</div>}<Cita c={c.cita} /></li>} />
          </div>
        </div>
      </details>
    </>
  );
}

function Apoyo({ run, ests, motivo }) {
  const [cuadro, setCuadro] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function pedir(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      setRes(await api(`/historial/pacientes/${run}/apoyo`, { method: "POST", body: { cuadro, establecimientos: ests, motivo } }));
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="card section">
      <div className="card-head">
        <div>
          <h3>4 · Apoyo diagnóstico</h3>
          <p>Describa el cuadro clínico. Las hipótesis y exámenes sugeridos son para su validación; no son diagnósticos.</p>
        </div>
      </div>
      <form onSubmit={pedir} className="stack">
        <textarea rows={3} value={cuadro} onChange={(e) => setCuadro(e.target.value)} required minLength={3}
          placeholder="Ej.: consulta por edema de extremidades inferiores y disnea de esfuerzo de 2 semanas" aria-label="Cuadro clínico" />
        <div><button className="btn primary" disabled={busy}>{busy ? "Analizando…" : "Sugerir hipótesis y exámenes"}</button></div>
      </form>
      {err && <div className="error small" role="alert">{err}</div>}
      {res && (
        <div className="stack" style={{ marginTop: 12 }}>
          {res.sin_resultados && <p className="faltante">{res.sin_resultados}</p>}
          {res.hipotesis.map((h, i) => (
            <div key={i} className={`hipotesis ${h.urgente ? "urgente" : ""}`}>
              <b>{h.urgente && "🚨 "}{h.hipotesis}</b> <span className="tag">{h.codigo} · {h.origen}</span>
              <ul className="clin-list">
                {h.fundamentos.map((f, j) => <li key={j}>{f.texto}<Cita c={f.cita} /></li>)}
              </ul>
              <div className="small"><b>Sugerido evaluar:</b> {h.examenes_sugeridos.join(" · ")}</div>
              <div className="small muted">{h.nota}</div>
            </div>
          ))}
          <p className="foot-note">{res.aviso}</p>
        </div>
      )}
    </div>
  );
}

function Dictado({ run, user, config }) {
  const [texto, setTexto] = useState("");
  const [borrador, setBorrador] = useState(null);
  const [ficha, setFicha] = useState(null);
  const [est, setEst] = useState(user.establecimientos?.[0] || "");
  const [rec, setRec] = useState(null);
  const [msg, setMsg] = useState("");
  const chunks = useRef([]);

  async function grabar() {
    if (rec) {
      rec.stop();
      return;
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      const r = new MediaRecorder(media);
      chunks.current = [];
      r.ondataavailable = (e) => chunks.current.push(e.data);
      r.onstop = async () => {
        media.getTracks().forEach((t) => t.stop());
        setRec(null);
        const fd = new FormData();
        fd.append("audio", new Blob(chunks.current, { type: "audio/webm" }), "dictado.webm");
        setMsg("Transcribiendo con el servicio local…");
        try {
          const out = await api("/historial/fichas/transcribir", { method: "POST", body: fd });
          setTexto((t) => `${t} ${out.texto}`.trim());
          setMsg("");
        } catch (x) {
          setMsg(x.message);
        }
      };
      r.start();
      setRec(r);
    } catch {
      setMsg("No se pudo acceder al micrófono.");
    }
  }

  async function estructurar() {
    setMsg("");
    setFicha(null);
    setBorrador(await api("/historial/fichas/estructurar", { method: "POST", body: { texto } }));
  }
  const editar = (id, v) => setBorrador((b) => ({ ...b, secciones: b.secciones.map((s) => (s.id === id ? { ...s, texto: v } : s)) }));
  async function guardar() {
    const body = { paciente_run: run, establecimiento_id: est, transcripcion: texto, origen: borrador.origen,
      secciones: borrador.secciones.map((s) => ({ id: s.id, texto: s.texto })) };
    try {
      setFicha(ficha ? await api(`/historial/fichas/${ficha.id}`, { method: "PUT", body })
        : await api("/historial/fichas", { method: "POST", body }));
      setMsg("Borrador guardado.");
    } catch (x) {
      setMsg(x.message);
    }
  }
  async function firmar() {
    try {
      setFicha(await api(`/historial/fichas/${ficha.id}/firmar`, { method: "POST" }));
      setMsg("Ficha firmada. Ya no puede modificarse.");
    } catch (x) {
      setMsg(x.message);
    }
  }
  const firmada = ficha?.estado === "firmada";
  return (
    <div className="card section">
      <div className="card-head">
        <div>
          <h3>5 · Ficha por dictado</h3>
          <p>Dicte o pegue la consulta. MedicAI la ordena en secciones sin agregar contenido; usted revisa, corrige y firma.</p>
        </div>
      </div>
      <div className="stack">
        <textarea rows={5} value={texto} onChange={(e) => setTexto(e.target.value)} aria-label="Transcripción"
          placeholder="Ej.: Paciente consulta por cefalea de 3 días. Al examen: presión arterial 160/95. Diagnóstico: … Indicaciones: …" />
        <div className="row">
          <button className="btn" onClick={grabar} disabled={!config?.transcripcion_local}
            title={config?.transcripcion_local ? "" : "Requiere un servicio de transcripción local (ASR_URL)"}>
            {rec ? "⏹ Detener" : "🎙 Dictar"}
          </button>
          <button className="btn primary" onClick={estructurar} disabled={!texto.trim()}>Estructurar ficha</button>
          {!config?.transcripcion_local && <span className="muted small">Dictado por voz desactivado: falta transcripción local.</span>}
        </div>
        {msg && <div className="banner" role="status">{msg}</div>}
      </div>
      {borrador && (
        <div className="stack" style={{ marginTop: 14 }}>
          <div className="banner">{borrador.aviso} <span className="tag">{borrador.origen}</span></div>
          {borrador.secciones.map((s) => (
            <label key={s.id} className="ficha-sec">
              <b>{s.titulo}</b>
              <textarea rows={3} value={s.texto} disabled={firmada} placeholder={s.faltante || ""}
                onChange={(e) => editar(s.id, e.target.value)} />
              {!s.texto && <span className="faltante small">{s.faltante || "Sección vacía."}</span>}
            </label>
          ))}
          <div className="row">
            <select value={est} onChange={(e) => setEst(e.target.value)} disabled={!!ficha} aria-label="Establecimiento">
              {(user.establecimientos || []).map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
            <button className="btn" onClick={guardar} disabled={firmada || !est}>{ficha ? "Guardar cambios" : "Guardar borrador"}</button>
            <button className="btn primary" onClick={firmar} disabled={!ficha || firmada}>Firmar ficha</button>
            {ficha && <span className="pill">{firmada ? `✓ Firmada por ${ficha.profesional}` : "Borrador"}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

export default function FichaClinica({ user }) {
  const [ests, setEsts] = useState([]);
  const [sel, setSel] = useState([]);
  const [run, setRun] = useState("");
  const [motivo, setMotivo] = useState("atencion");
  const [fuentes, setFuentes] = useState([]);
  const [perfil, setPerfil] = useState(null);
  const [consultado, setConsultado] = useState("");
  const [ms, setMs] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState(null);

  useEffect(() => {
    api("/historial/establecimientos").then((e) => { setEsts(e); setSel(e.map((x) => x.id)); }).catch((x) => setErr(x.message));
    api("/historial/config").then(setConfig).catch(() => {});
  }, []);

  const toggle = (id) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  async function consultar(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    setPerfil(null);
    const nombres = Object.fromEntries(ests.map((x) => [x.id, x.nombre]));
    setFuentes(sel.map((id) => ({ id, nombre: nombres[id], estado: "pendiente" })));
    try {
      await stream(`/historial/pacientes/${encodeURIComponent(run)}/perfil/stream`, { establecimientos: sel.join(","), motivo }, (ev) => {
        if (ev.evento === "fuente") setFuentes((f) => f.map((x) => (x.id === ev.id ? ev : x)));
        if (ev.evento === "perfil") {
          setPerfil(ev.perfil);
          setMs(ev.generado_ms);
          setConsultado(run);
        }
      });
    } catch (x) {
      setErr(x.message);
      setFuentes([]);
    } finally {
      setBusy(false);
    }
  }

  const pac = perfil?.paciente;
  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Módulo 1 · Dashboard clínico</p>
          <h1>Ficha clínica de la red</h1>
          <p>Perfil sintético previo a la consulta desde uno o varios establecimientos. Apoya, no decide: toda salida clínica requiere su validación.</p>
        </div>
      </header>

      <form className="card ficha-busqueda" onSubmit={consultar}>
        <div className="row">
          <label className="small">RUN del paciente
            <input type="text" value={run} onChange={(e) => setRun(e.target.value)} placeholder="12.345.678-5" required autoComplete="off" />
          </label>
          <label className="small">Motivo del acceso
            <select value={motivo} onChange={(e) => setMotivo(e.target.value)}>
              {MOTIVOS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <button className="btn primary" disabled={busy || !sel.length}>{busy ? "Consultando…" : "Consultar"}</button>
        </div>
        <fieldset className="ests">
          <legend className="small muted">Bases a consultar (en paralelo)</legend>
          {ests.map((x) => (
            <label key={x.id} className="chk">
              <input type="checkbox" checked={sel.includes(x.id)} onChange={() => toggle(x.id)} />
              {x.nombre}{x.propio && <span className="tag">su establecimiento</span>}
            </label>
          ))}
        </fieldset>
        <p className="muted small" style={{ margin: 0 }}>
          El acceso se registra en la auditoría (Ley 20.584). Solo verá pacientes con relación asistencial en sus establecimientos,
          salvo urgencia.
        </p>
      </form>

      {fuentes.length > 0 && <Fuentes fuentes={fuentes} />}
      {err && <div className="card error section" role="alert">{err}</div>}

      {perfil && (
        <>
          <div className="card section paciente-head">
            <div>
              <h2>{pac.nombre || "Paciente sin nombre registrado"}</h2>
              <p className="muted">
                RUN {pac.run_mask}{pac.edad != null && ` · ${pac.edad} años`}{pac.sexo && ` · ${pac.sexo === "F" ? "Femenino" : "Masculino"}`}
                {pac.inscripcion && ` · Inscrito en ${pac.inscripcion}`}
              </p>
            </div>
            <span className="muted small">Generado en {fmt.ms(ms)}</span>
          </div>
          <div className="banner" role="note">ℹ️ {perfil.aviso}</div>
          {perfil.sin_registros ? (
            <div className="card section"><p className="faltante">No se encontraron registros del paciente en las fuentes consultadas.</p></div>
          ) : (
            <>
              <Perfil p={perfil} />
              <Apoyo run={consultado} ests={sel} motivo={motivo} />
            </>
          )}
          <Dictado run={consultado} user={user} config={config} />
        </>
      )}
    </>
  );
}
