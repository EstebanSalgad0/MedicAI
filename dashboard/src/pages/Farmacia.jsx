import { useEffect, useState } from "react";
import { api, fmt } from "../api.js";
import Kpi from "../components/Kpi.jsx";

const STOCK = {
  available: { label: "Disponible", color: "var(--good)", icon: "✓" },
  low: { label: "Stock bajo", color: "var(--warning)", icon: "!" },
  none: { label: "Sin stock", color: "var(--critical)", icon: "✕" },
};

function StockRow({ item, onSave }) {
  const [qty, setQty] = useState(item.stock);
  const [min, setMin] = useState(item.min_stock);
  const [busy, setBusy] = useState(false);
  const dirty = Number(qty) !== item.stock || Number(min) !== item.min_stock;
  const st = STOCK[item.status];
  return (
    <tr>
      <td>{item.name}</td>
      <td>{item.center_nombre}</td>
      <td><span className="pill"><span className="dot" style={{ background: st.color }} />{st.icon} {st.label}</span></td>
      <td className="r"><input type="number" min="0" value={qty} onChange={(e) => setQty(e.target.value)} style={{ width: 90 }} aria-label={`Stock de ${item.name}`} /></td>
      <td className="r"><input type="number" min="0" value={min} onChange={(e) => setMin(e.target.value)} style={{ width: 80 }} aria-label={`Mínimo de ${item.name}`} /></td>
      <td>
        <button className="btn small primary" disabled={!dirty || busy}
          onClick={async () => { setBusy(true); await onSave({ center_id: item.center_id, name: item.name, stock: Number(qty), min_stock: Number(min) }); setBusy(false); }}>
          Guardar
        </button>
      </td>
    </tr>
  );
}

export default function Farmacia() {
  const [centers, setCenters] = useState([]);
  const [center, setCenter] = useState("");
  const [stock, setStock] = useState([]);
  const [pickups, setPickups] = useState([]);
  const [stats, setStats] = useState(null);
  const [notice, setNotice] = useState("");
  const [nuevo, setNuevo] = useState({ name: "", stock: "", center_id: "" });

  useEffect(() => {
    api("/agendamiento/catalog").then((c) => { setCenters(c.centers); setCenter((cur) => cur || c.centers[0]?.id || ""); }).catch(() => {});
  }, []);
  function load() {
    Promise.all([
      api("/medicamentos/stock", { params: { center_id: center } }),
      api("/medicamentos/pickups", { params: { center_id: center, status: "pending" } }),
      api("/medicamentos/stats"),
    ]).then(([s, p, st]) => { setStock(s); setPickups(p); setStats(st); });
  }
  useEffect(load, [center]);

  async function save(body) {
    const r = await api("/medicamentos/stock", { method: "PUT", body });
    setNotice(r.notified ? `Stock actualizado. Se avisó a ${r.notified} paciente(s) que esperaban este medicamento.` : "Stock actualizado.");
    load();
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Farmacia</h1>
          <p>Inventario que MedicAI informa a los pacientes y retiros programados.</p>
        </div>
        <div className="filters">
          <select value={center} onChange={(e) => setCenter(e.target.value)} aria-label="CESFAM">
            <option value="">Todos los CESFAM</option>
            {centers.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </div>
      </div>

      {stats && (
        <div className="grid kpis">
          <Kpi label="Retiros pendientes" value={fmt.int(stats.pickups.pending || 0)} />
          <Kpi label="Retiros cumplidos" value={fmt.pct(stats.pickup_rate)} detail={`${fmt.int(stats.pickups.done || 0)} retirados · ${fmt.int(stats.pickups.missed || 0)} no retirados`} />
          <Kpi label="Fármacos bajo el mínimo" value={fmt.int(stats.low_stock_items)} />
          <Kpi label="Pacientes esperando reposición" value={fmt.int(stats.pending_stock_alerts)} />
        </div>
      )}
      {notice && <div className="banner" role="status">{notice}</div>}

      <div className="grid" style={{ gap: 14 }}>
        <div className="card">
          <div className="card-head"><div><h2>Inventario</h2><p>Al reponer un fármaco sin stock, MedicAI avisa automáticamente a quienes lo pidieron.</p></div></div>
          <form className="filters" style={{ marginBottom: 10 }}
            onSubmit={async (e) => {
              e.preventDefault();
              await save({ center_id: nuevo.center_id || center, name: nuevo.name, stock: Number(nuevo.stock || 0) });
              setNuevo({ name: "", stock: "", center_id: "" });
            }}>
            <input type="text" placeholder="Nuevo medicamento" value={nuevo.name} onChange={(e) => setNuevo({ ...nuevo, name: e.target.value })} required />
            {!center && (
              <select value={nuevo.center_id} onChange={(e) => setNuevo({ ...nuevo, center_id: e.target.value })} required aria-label="CESFAM del medicamento">
                <option value="">CESFAM…</option>
                {centers.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            )}
            <input type="number" min="0" placeholder="Stock" value={nuevo.stock} onChange={(e) => setNuevo({ ...nuevo, stock: e.target.value })} style={{ width: 100 }} required />
            <button className="btn">Agregar</button>
          </form>
          {stock.length ? (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Medicamento</th><th>CESFAM</th><th>Estado</th><th className="r">Stock</th><th className="r">Mínimo</th><th /></tr></thead>
                <tbody>{stock.map((s) => <StockRow key={`${s.id}-${s.stock}-${s.min_stock}`} item={s} onSave={save} />)}</tbody>
              </table>
            </div>
          ) : <div className="empty">Sin inventario registrado.</div>}
        </div>

        <div className="card">
          <div className="card-head"><div><h2>Próximos retiros</h2><p>Programados por pacientes en el chat</p></div></div>
          {pickups.length ? (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Fecha</th><th>Medicamento</th><th>CESFAM</th><th className="r">Ciclo</th></tr></thead>
                <tbody>
                  {pickups.map((p) => (
                    <tr key={p.id}>
                      <td className="num">{new Date(p.due_date + "T12:00").toLocaleDateString("es-CL")}</td>
                      <td>{p.medication}</td><td>{p.center_nombre}</td>
                      <td className="r">{p.freq_days ? `cada ${p.freq_days} días` : "único"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="empty">No hay retiros pendientes.</div>}
        </div>
      </div>
    </>
  );
}
