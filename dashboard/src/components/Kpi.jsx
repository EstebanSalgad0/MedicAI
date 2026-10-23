import Info from "./Info.jsx";

/** Tarjeta de cifra simple: etiqueta, valor y un detalle opcional. */
export default function Kpi({ label, value, detail, info, icon }) {
  return (
    <div className="card tile">
      <div className="tile-top">
        {icon && <span className="tile-icon" aria-hidden="true">{icon}</span>}
        <span className="tile-label">{label}</span>
        {info && <Info>{info}</Info>}
      </div>
      <div className="tile-value">{value}</div>
      {detail && <div className="tile-detail">{detail}</div>}
    </div>
  );
}

const STATUS_TXT = { ok: "✓ Cumple la meta", below: "✕ Bajo la meta", none: "Sin datos suficientes" };

/**
 * Indicador con meta: valor, barra de avance con la meta marcada y estado.
 * El estado se comunica con ícono + texto, nunca solo con color.
 */
export function TargetCard({ label, desc, info, value, raw, target, scale, format, detail }) {
  const st = target?.status || "none";
  const [min, max] = scale;
  const pos = (v) => `${Math.max(0, Math.min(1, (v - min) / (max - min))) * 100}%`;
  const goal = target ? `Meta ${target.op === "<=" ? "≤" : "≥"} ${format(target.value)}` : null;
  return (
    <div className={`card target-card status-${st}`}>
      <div className="tile-top">
        <span className="tile-label">{label}</span>
        {info && <Info>{info}</Info>}
      </div>
      <div className="tile-value">{value}</div>
      {desc && <p className="tile-desc">{desc}</p>}
      <div className="bullet" aria-hidden="true">
        <div className="bullet-fill" style={{ width: raw == null ? 0 : pos(raw) }} />
        {target && <div className="bullet-target" style={{ left: pos(target.value) }} />}
      </div>
      <div className="target-foot">
        <span className={`status-pill ${st}`}>{STATUS_TXT[st]}</span>
        {goal && <span className="muted small">{goal}</span>}
      </div>
      {detail && <div className="tile-detail">{detail}</div>}
    </div>
  );
}
