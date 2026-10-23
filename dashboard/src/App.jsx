import { useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler, takeTokenFromHash } from "./api.js";
import Resumen from "./pages/Resumen.jsx";
import Agenda from "./pages/Agenda.jsx";
import Farmacia from "./pages/Farmacia.jsx";
import Simulador from "./pages/Simulador.jsx";
import Satisfaccion from "./pages/Satisfaccion.jsx";
import Hospital from "./pages/Hospital.jsx";
import Contacto from "./pages/Contacto.jsx";
import FichaClinica from "./pages/FichaClinica.jsx";
import Derivaciones from "./pages/Derivaciones.jsx";

const ICONS = {
  ficha: "M9 3h6l1 2h3v16H5V5h3zM9 12h6M12 9v6",
  derivaciones: "M4 7h11l-3-3M20 17H9l3 3M15 7a5 5 0 0 1 0 10",
  hospital: "M3 21h18M5 21V8l7-5 7 5v13M10 21v-5h4v5M12 8v5M9.5 10.5h5",
  contacto: "M3 13h5l2 3h4l2-3h5M5.5 5h13L21 13v6H3v-6z",
  resumen: "M4 19V10M10 19V5M16 19v-6M22 19H2",
  satisfaccion: "m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9Z",
  agenda: "M7 3v3M17 3v3M3 9h18M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z",
  farmacia: "m10.5 20.5-7-7a4.95 4.95 0 0 1 7-7l7 7a4.95 4.95 0 0 1-7 7ZM7 10l7 7",
  simulador: "M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z",
};
// group: 1 = Dashboard clínico · 2 = Chatbot de pacientes · 3 = Agendas y derivaciones · g = gestión
const PAGES = [
  { id: "ficha", label: "Ficha clínica", el: FichaClinica, group: "1", can: (u) => u.clinico },
  { id: "agenda", label: "Agenda", el: Agenda, group: "3", can: () => true },
  { id: "derivaciones", label: "Derivaciones", el: Derivaciones, group: "3", can: () => true },
  { id: "hospital", label: "Hospital", el: Hospital, group: "g", can: () => true },
  { id: "resumen", label: "Indicadores", el: Resumen, group: "g", can: () => true },
  { id: "satisfaccion", label: "Satisfacción", el: Satisfaccion, group: "g", can: () => true },
  { id: "farmacia", label: "Farmacia", el: Farmacia, group: "2", can: () => true },
  { id: "contacto", label: "Contacto", el: Contacto, group: "2", can: () => true },
  { id: "simulador", label: "Simulador", el: Simulador, group: "2", can: () => true },
];
const GROUPS = [
  ["1", "Dashboard clínico"],
  ["3", "Agendas y derivaciones"],
  ["2", "Chatbot de pacientes"],
  ["g", "Gestión"],
];

function Icon({ d }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
  );
}

function Login({ onLogin }) {
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [local, setLocal] = useState(false);
  const [modo, setModo] = useState(null);
  useEffect(() => {
    fetch("/id/config").then((r) => r.json()).then((c) => setModo(c.modo)).catch(() => {});
  }, []);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r = await api("/auth/login", { method: "POST", body: { username: user, password: pass } });
      setToken(r.token);
      onLogin();
    } catch {
      setErr("Usuario o contraseña incorrectos.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login">
      <div className="card login-card">
        <div className="logo" style={{ padding: "0 0 8px" }}>
          <Mark />
          <div>
            <b>MedicAI</b>
            <span>Red asistencial · Maule</span>
          </div>
        </div>
        <a className="btn primary cu-btn" href="/id/login?next=/">Ingresar con ClaveÚnica</a>
        <p className="muted small" style={{ margin: 0 }}>
          Profesionales de salud y funcionarios. El acceso a fichas clínicas requiere ClaveÚnica y queda auditado.
          {modo === "demo" && <><br /><b>Modo demostración:</b> ClaveÚnica está simulada.</>}
        </p>
        {!local ? (
          <button type="button" className="btn" onClick={() => setLocal(true)}>Cuenta de administración</button>
        ) : (
          <form onSubmit={submit} className="login-form">
            <p className="muted small" style={{ margin: 0 }}>Solo indicadores, agendas y configuración. No da acceso a fichas.</p>
            <label>
              Usuario
              <input type="text" autoComplete="username" value={user} onChange={(e) => setUser(e.target.value)} required />
            </label>
            <label>
              Contraseña
              <input type="password" autoComplete="current-password" value={pass} onChange={(e) => setPass(e.target.value)} required />
            </label>
            {err && <div className="error small" role="alert">{err}</div>}
            <button className="btn" disabled={busy}>{busy ? "Ingresando…" : "Ingresar"}</button>
          </form>
        )}
      </div>
    </div>
  );
}

function Mark() {
  return (
    <div className="logo-mark" aria-hidden="true">
      <svg width="18" height="18" viewBox="0 0 32 32"><path d="M12 5h8v7h7v8h-7v7h-8v-7H5v-8h7z" fill="white" /></svg>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(() => location.hash.slice(1) || "");

  function loadUser() {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api("/analytics/auth/verify")
      .then((u) => setUser(u))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    takeTokenFromHash();
    setUnauthorizedHandler(() => {
      setToken(null);
      setUser(null);
    });
    loadUser();
    const onHash = () => setPage(location.hash.slice(1));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (loading) return <div className="login"><div className="muted">Cargando…</div></div>;
  if (!user) return <Login onLogin={loadUser} />;
  const pages = PAGES.filter((p) => p.can(user));
  const current = pages.find((p) => p.id === page) || pages.find((p) => p.id === (user.clinico ? "ficha" : "resumen")) || pages[0];
  const Page = current.el;

  return (
    <div className="shell">
      <nav className="side" aria-label="Secciones">
        <div className="logo">
          <Mark />
          <div>
            <b>MedicAI</b>
            <span>Red asistencial · Maule</span>
          </div>
        </div>
        {GROUPS.map(([g, label]) => {
          const items = pages.filter((p) => p.group === g);
          if (!items.length) return null;
          return (
            <div key={g} className="nav-group">
              <div className="nav-label">{label}</div>
              {items.map((p) => (
                <a key={p.id} href={`#${p.id}`} className="nav" aria-current={current.id === p.id ? "page" : undefined}>
                  <Icon d={ICONS[p.id]} />
                  {p.label}
                </a>
              ))}
            </div>
          );
        })}
        <div className="side-foot">
          <span className="avatar-sm" aria-hidden="true">{String(user.nombre || user.user).slice(0, 1)}</span>
          <div className="who">
            <b title={user.nombre}>{user.nombre || user.user}</b>
            <span className="muted">{user.rol_nombre}{user.metodo === "claveunica" ? " · ClaveÚnica" : ""}</span>
            <button onClick={() => { setToken(null); setUser(null); }}>Cerrar sesión</button>
          </div>
        </div>
      </nav>
      <main className="main">
        <Page user={user} />
      </main>
    </div>
  );
}
