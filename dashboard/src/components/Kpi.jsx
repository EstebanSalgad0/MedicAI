const STATUS_TXT = { ok: "Cumple meta", below: "Bajo la meta", none: "Sin datos suficientes" };

/** Tarjeta de indicador. La meta se muestra con ícono + texto, nunca solo con color. */
export default function Kpi({ label, value, detail, target }) {
  const st = target ? target.status || "none" : null;
  return (
    <div className="card">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {detail && <div className="small muted">{detail}</div>}
      {target && (
        <div className={`target status-${st}`} style={{ marginTop: 6 }}>
          <span className="dot" aria-hidden="true" />
          <span>{target.label} · {st === "ok" ? "✓ " : st === "below" ? "✕ " : ""}{STATUS_TXT[st]}</span>
        </div>
      )}
    </div>
  );
}
