import { useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api.js";
import Resumen from "./pages/Resumen.jsx";
import Agenda from "./pages/Agenda.jsx";
import Farmacia from "./pages/Farmacia.jsx";
import Simulador from "./pages/Simulador.jsx";
import Satisfaccion from "./pages/Satisfaccion.jsx";
import Hospital from "./pages/Hospital.jsx";
import Contacto from "./pages/Contacto.jsx";

const ICONS = {
  hospital: "M3 21h18M5 21V8l7-5 7 5v13M10 21v-5h4v5M12 8v5M9.5 10.5h5",
  contacto: "M3 13h5l2 3h4l2-3h5M5.5 5h13L21 13v6H3v-6z",
  resumen: "M4 19V10M10 19V5M16 19v-6M22 19H2",
  satisfaccion: "m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9Z",
  agenda: "M7 3v3M17 3v3M3 9h18M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z",
  farmacia: "m10.5 20.5-7-7a4.95 4.95 0 0 1 7-7l7 7a4.95 4.95 0 0 1-7 7ZM7 10l7 7",
  simulador: "M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z",
};
const PAGES = [
  { id: "hospital", label: "Hospital", el: Hospital },
  { id: "resumen", label: "Indicadores", el: Resumen },
  { id: "satisfaccion", label: "Satisfacción", el: Satisfaccion },
  { id: "agenda", label: "Agenda", el: Agenda },
  { id: "farmacia", label: "Farmacia", el: Farmacia },
  { id: "contacto", label: "Contacto", el: Contacto },
  { id: "simulador", label: "Simulador", el: Simulador },
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
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r = await api("/auth/login", { method: "POST", body: { username: user, password: pass } });
      setToken(r.token);
      onLogin(r.user);
    } catch {
      setErr("Usuario o contraseña incorrectos.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login">
      <form className="card" onSubmit={submit}>
        <div className="logo" style={{ padding: "0 0 8px" }}>
          <Mark />
          <div>
            <b>MedicAI</b>
            <span>Panel para equipos de APS</span>
          </div>
        </div>
        <label>
          Usuario
          <input type="text" autoComplete="username" value={user} onChange={(e) => setUser(e.target.value)} required />
        </label>
        <label>
          Contraseña
          <input type="password" autoComplete="current-password" value={pass} onChange={(e) => setPass(e.target.value)} required />
        </label>
        {err && <div className="error small" role="alert">{err}</div>}
        <button className="btn primary" disabled={busy}>{busy ? "Ingresando…" : "Ingresar"}</button>
      </form>
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
  const [user, setUser] = useState(getToken() ? "…" : null);
  const [page, setPage] = useState(() => location.hash.slice(1) || "resumen");

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null);
      setUser(null);
    });
    if (getToken()) api("/analytics/auth/verify").then((r) => setUser(r.user)).catch(() => {});
    const onHash = () => setPage(location.hash.slice(1) || "resumen");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (!user) return <Login onLogin={setUser} />;
  const Page = (PAGES.find((p) => p.id === page) || PAGES[0]).el;

  return (
    <div className="shell">
      <nav className="side" aria-label="Secciones">
        <div className="logo">
          <Mark />
          <div>
            <b>MedicAI</b>
            <span>Panel APS · Maule</span>
          </div>
        </div>
        <div className="nav-label">Panel</div>
        {PAGES.map((p) => (
          <a key={p.id} href={`#${p.id}`} className="nav" aria-current={page === p.id ? "page" : undefined}>
            <Icon d={ICONS[p.id]} />
            {p.label}
          </a>
        ))}
        <div className="side-foot">
          <span className="avatar-sm" aria-hidden="true">{String(user).slice(0, 1)}</span>
          <div className="who">
            <b>{user}</b>
            <button onClick={() => { setToken(null); setUser(null); }}>Cerrar sesión</button>
          </div>
        </div>
      </nav>
      <main className="main">
        <Page />
      </main>
    </div>
  );
}
