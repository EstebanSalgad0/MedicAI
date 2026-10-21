const KEY = "medicai_token";

export function getToken() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
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
  const res = await fetch(`/api${path}${qs}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    onUnauthorized();
    throw new Error("Sesión expirada");
  }
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.headers.get("content-type")?.includes("json") ? res.json() : res.text();
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
};
