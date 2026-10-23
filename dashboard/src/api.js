const KEY = "medicai_token";

export function getToken() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** Al volver de ClaveÚnica, ms-identidad deja el token en el fragmento de la URL (#token=...). */
export function takeTokenFromHash() {
  const m = location.hash.match(/token=([^&]+)/);
  if (!m) return false;
  setToken(decodeURIComponent(m[1]));
  history.replaceState(null, "", location.pathname + location.search);
  return true;
}

export function setToken(t) {
  try {
    if (t) localStorage.setItem(KEY, t);
    else localStorage.removeItem(KEY);
  } catch {
    /* almacenamiento no disponible: la sesión dura lo que la pestaña */
  }
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export async function api(path, { method = "GET", body, params } = {}) {
  const qs = params
    ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString()
    : "";
  const isForm = body instanceof FormData;
  const res = await fetch(`/api${path}${qs}`, {
    method,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });
  if (res.status === 401) {
    onUnauthorized();
    throw new Error("Sesión expirada");
  }
  if (!res.ok) throw new Error(await errorText(res));
  return res.headers.get("content-type")?.includes("json") ? res.json() : res.text();
}

/** Mensaje legible de un error de la API ({"detail": "..."} de FastAPI o texto plano). */
export async function errorText(res) {
  const raw = await res.text();
  try {
    const d = JSON.parse(raw).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => x.msg).join(" · ");
  } catch { /* no es JSON */ }
  return raw || res.statusText;
}

/** Lee una respuesta NDJSON línea a línea (progreso de la consulta multi-establecimiento). */
export async function stream(path, params, onLine) {
  const qs = "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString();
  const res = await fetch(`/api${path}${qs}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (res.status === 401) {
    onUnauthorized();
    throw new Error("Sesión expirada");
  }
  if (!res.ok) throw new Error(await errorText(res));
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (line) onLine(JSON.parse(line));
    }
  }
  if (buf.trim()) onLine(JSON.parse(buf));
}

export async function download(path, params, filename) {
  const qs = "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  const res = await fetch(`/api${path}${qs}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new Error("No se pudo exportar");
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

export const fmt = {
  int: (n) => (n == null ? "—" : new Intl.NumberFormat("es-CL").format(n)),
  pct: (r) => (r == null ? "—" : `${(r * 100).toLocaleString("es-CL", { maximumFractionDigits: 1 })} %`),
  ms: (n) => (n == null ? "—" : n >= 1000 ? `${(n / 1000).toLocaleString("es-CL", { maximumFractionDigits: 2 })} s` : `${Math.round(n)} ms`),
  dec: (n, d = 1) => (n == null ? "—" : n.toLocaleString("es-CL", { maximumFractionDigits: d, minimumFractionDigits: d })),
  // "2026-10-21" se interpreta como fecha local (sin desfase UTC)
  date: (s) => new Date(/^\d{4}-\d{2}-\d{2}$/.test(s) ? `${s}T12:00` : s).toLocaleDateString("es-CL", { day: "2-digit", month: "short" }),
  datetime: (s) =>
    new Date(s).toLocaleString("es-CL", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }),
};

export const SERVICE_LABEL = {
  agendamiento: "Agendamiento",
  recordatorios: "Recordatorios",
  orientacion: "Orientación",
  derivacion: "Derivación",
  medicamentos: "Medicamentos",
  orchestrator: "Orquestador",
  resultados: "Resultados",
  atencion: "Atención al usuario",
  historial: "Ficha clínica",
  identidad: "Identidad (ClaveÚnica)",
};
