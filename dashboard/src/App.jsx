import { useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api.js";
import Resumen from "./pages/Resumen.jsx";
import Agenda from "./pages/Agenda.jsx";
import Farmacia from "./pages/Farmacia.jsx";
import Simulador from "./pages/Simulador.jsx";

const PAGES = [
  { id: "resumen", label: "Indicadores", icon: "📊", el: Resumen },
  { id: "agenda", label: "Agenda", icon: "🗓️", el: Agenda },
  { id: "farmacia", label: "Farmacia", icon: "💊", el: Farmacia },
  { id: "simulador", label: "Simulador", icon: "💬", el: Simulador },
];

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
        <div className="logo" style={{ padding: 0 }}>
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
        {PAGES.map((p) => (
          <a key={p.id} href={`#${p.id}`} className="nav" aria-current={page === p.id ? "page" : undefined}>
            <span aria-hidden="true">{p.icon}</span>
            {p.label}
          </a>
        ))}
        <div className="side-foot">
          <span>Sesión: {user}</span>
          <button className="btn small" onClick={() => { setToken(null); setUser(null); }}>Cerrar sesión</button>
        </div>
      </nav>
      <main className="main">
        <Page />
      </main>
    </div>
  );
}
