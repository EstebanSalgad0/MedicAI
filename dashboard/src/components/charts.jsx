import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
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

/** Barras horizontales; `series` > 1 = barras agrupadas. Valor en la punta de la barra. */
export function HBars({ data, category, series, format = fmt.int, height }) {
  if (!data?.length) return <div className="empty">Sin datos en el período.</div>;
  const h = height || Math.max(120, data.length * (series.length > 1 ? 44 : 32) + 30);
  return (
    <>
      {series.length > 1 && <Legend box items={series.map((s) => ({ label: s.label, color: s.color }))} />}
      <ResponsiveContainer width="100%" height={h}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }} barGap={2}>
          <CartesianGrid stroke="var(--grid)" horizontal={false} />
          <XAxis type="number" {...axis} tickFormatter={format} allowDecimals={false} />
          <YAxis type="category" dataKey={category} {...axis} axisLine={false} width={120}
            tick={{ fill: "var(--ink-2)", fontSize: 13 }} />
          <Tooltip content={<TT format={format} />} cursor={{ fill: "var(--surface-2)" }} />
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color} barSize={series.length > 1 ? 12 : 16}
              radius={[0, 4, 4, 0]} isAnimationActive={false}
              label={{ position: "right", fill: "var(--ink-2)", fontSize: 12, formatter: format }} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}
