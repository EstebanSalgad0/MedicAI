import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fmt } from "../api.js";

const axis = { stroke: "var(--axis)", tick: { fill: "var(--muted)", fontSize: 12 }, tickLine: false };

function TT({ active, payload, label, format = fmt.int, labelFormat = (l) => l }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tt">
      <div className="muted small" style={{ marginBottom: 4 }}>{labelFormat(label)}</div>
      {payload.map((p) => (
        <div className="tt-row" key={p.dataKey}>
          <span className="tt-key" style={{ background: p.color || p.payload?.fill }} />
          <b>{format(p.value)}</b>
          <span className="muted">{p.name}</span>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items, box }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span key={i.label}><i className={box ? "box" : ""} style={{ background: i.color }} />{i.label}</span>
      ))}
    </div>
  );
}

/** Serie temporal: una o más líneas sobre el mismo eje (nunca doble eje). */
export function TimeLines({ data, series, format = fmt.int, target, height = 220 }) {
  if (!data?.length) return <div className="empty">Sin datos en el período.</div>;
  return (
    <>
      {series.length > 1 && <Legend items={series.map((s) => ({ label: s.label, color: s.color }))} />}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="date" {...axis} tickFormatter={fmt.date} minTickGap={24} />
          <YAxis {...axis} axisLine={false} width={format === fmt.ms ? 64 : 48} tickFormatter={format} allowDecimals={false} />
          {target && (
            <ReferenceLine y={target.value} stroke="var(--critical)" strokeWidth={1}
              label={{ value: target.label, position: "insideTopRight", fill: "var(--ink-2)", fontSize: 12 }} />
          )}
          <Tooltip content={<TT format={format} labelFormat={fmt.date} />} cursor={{ stroke: "var(--axis)" }} />
          {series.map((s) => (
            <Line key={s.key} dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={2} dot={false}
              activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }} connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </>
  );
}

/** Tendencia compacta de una sola serie (el título de la tarjeta la nombra; no lleva leyenda). */
export function MiniTrend({ data, dataKey, label, format = fmt.int, color = "var(--series-1)", height = 150 }) {
  if (!data?.length) return <div className="empty">Sin datos en el período.</div>;
  const id = `fill-${dataKey}`;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" style={{ stopColor: color, stopOpacity: 0.2 }} />
            <stop offset="100%" style={{ stopColor: color, stopOpacity: 0 }} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="date" {...axis} tickFormatter={fmt.date} minTickGap={36} />
        <YAxis {...axis} axisLine={false} width={40} tickFormatter={format} allowDecimals={false} tickCount={4} />
        <Tooltip content={<TT format={format} labelFormat={fmt.date} />} cursor={{ stroke: "var(--axis)" }} />
        <Area type="monotone" dataKey={dataKey} name={label} stroke={color} strokeWidth={2} fill={`url(#${id})`}
          dot={false} activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Barras horizontales; `series` > 1 = barras agrupadas. Valor en la punta de la barra. */
export function HBars({ data, category, series, format = fmt.int, height, labelWidth = 130 }) {
  if (!data?.length) return <div className="empty">Sin datos en el período.</div>;
  const h = height || Math.max(110, data.length * (series.length > 1 ? 44 : 34) + 24);
  return (
    <>
      {series.length > 1 && <Legend box items={series.map((s) => ({ label: s.label, color: s.color }))} />}
      <ResponsiveContainer width="100%" height={h}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 44, bottom: 0, left: 0 }} barGap={2}>
          <CartesianGrid stroke="var(--grid)" horizontal={false} />
          <XAxis type="number" {...axis} tickFormatter={format} allowDecimals={false} />
          <YAxis type="category" dataKey={category} {...axis} axisLine={false} width={labelWidth}
            tick={{ fill: "var(--ink-2)", fontSize: 13 }} />
          <Tooltip content={<TT format={format} />} cursor={{ fill: "var(--surface-2)" }} />
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color} barSize={series.length > 1 ? 12 : 14}
              radius={[0, 4, 4, 0]} isAnimationActive={false}
              label={{ position: "right", fill: "var(--ink-2)", fontSize: 12, formatter: format }} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

/** Reparto de un total en partes (≤ 6): barra 100 % + lista con cantidad y porcentaje. */
export function SegmentBar({ items, format = fmt.int }) {
  const total = items.reduce((s, i) => s + (i.value || 0), 0);
  if (!total) return <div className="empty">Sin datos en el período.</div>;
  return (
    <div>
      <div className="seg-bar" role="img" aria-label={items.map((i) => `${i.label}: ${format(i.value)}`).join(", ")}>
        {items.filter((i) => i.value > 0).map((i) => (
          <span key={i.label} style={{ flexGrow: i.value, background: i.color }}
            title={`${i.label}: ${format(i.value)} (${fmt.pct(i.value / total)})`} />
        ))}
      </div>
      <ul className="seg-legend">
        {items.map((i) => (
          <li key={i.label}>
            <i style={{ background: i.color }} aria-hidden="true" />
            <span className="seg-name">{i.label}{i.hint && <span className="muted small"> · {i.hint}</span>}</span>
            <b className="num">{format(i.value || 0)}</b>
            <span className="muted num seg-pct">{fmt.pct((i.value || 0) / total)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Barra dentro de una celda de tabla (proporción 0–1). */
export function InlineBar({ value, tone }) {
  return (
    <span className="ibar" aria-hidden="true">
      <span className={tone ? `tone-${tone}` : ""} style={{ width: `${Math.max(0, Math.min(1, value || 0)) * 100}%` }} />
    </span>
  );
}
