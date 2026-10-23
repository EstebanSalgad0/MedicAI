"""Páginas web mínimas del ingreso con ClaveÚnica (se abren desde WhatsApp o el dashboard)."""
from __future__ import annotations

from html import escape

CSS = """
:root{--page:#f3f5f8;--card:#fff;--ink:#0b0b0b;--muted:#5f5e59;--brand:#1c5cab;--line:#dcdbd5;--warn:#fff4d6}
@media (prefers-color-scheme:dark){:root{--page:#0d0d0d;--card:#1a1a19;--ink:#f0efec;--muted:#a3a198;
--brand:#5598e7;--line:#33332f;--warn:#3a2f12}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;display:grid;place-items:center;min-height:100vh;padding:16px}
main{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:28px;width:min(440px,100%)}
h1{font-size:21px;margin:0 0 6px}p{color:var(--muted);margin:8px 0}label{display:grid;gap:4px;margin:12px 0;font-size:14px}
input,select{font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink)}
button,.btn{display:block;width:100%;margin-top:14px;padding:11px;border:0;border-radius:10px;background:var(--brand);
color:#fff;font:inherit;font-weight:600;cursor:pointer;text-align:center;text-decoration:none}
.alt{background:none;border:1px solid var(--line);color:var(--ink);font-weight:500}
.warn{background:var(--warn);border-radius:10px;padding:10px 12px;font-size:14px;color:var(--ink)}
.check{display:flex;gap:10px;align-items:flex-start;font-size:14px}.check input{margin-top:4px}
small{color:var(--muted)}
"""


def page(title: str, body: str, status: int = 200) -> tuple[str, int]:
    html = (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>'
            f"<style>{CSS}</style></head><body><main>{body}</main></body></html>")
    return html, status


def mensaje(title: str, texto: str, status: int = 200) -> tuple[str, int]:
    return page(title, f"<h1>{escape(title)}</h1><p>{escape(texto)}</p>", status)


def demo(state: str, sugeridos: list[tuple[str, str, str]]) -> tuple[str, int]:
    """Simulador de la página de ClaveÚnica. `sugeridos`: (run, nombre, detalle)."""
    picks = "".join(
        f'<form method="post" action="/id/demo"><input type="hidden" name="state" value="{escape(state)}">'
        f'<input type="hidden" name="run" value="{escape(r)}"><input type="hidden" name="nombre" value="{escape(n)}">'
        f'<button class="alt" type="submit">{escape(n)}<br><small>{escape(d)}</small></button></form>'
        for r, n, d in sugeridos)
    return page("Simulador de ClaveÚnica", f"""
<h1>Simulador de ClaveÚnica</h1>
<p class="warn">Solo para pruebas y demostraciones (CLAVEUNICA_MODE=demo). En producción esta página
es la de ClaveÚnica del Estado y MedicAI nunca ve la clave.</p>
<form method="post" action="/id/demo">
  <input type="hidden" name="state" value="{escape(state)}">
  <label>RUN <input name="run" placeholder="12.345.678-5" required autocomplete="off"></label>
  <label>Nombre <input name="nombre" placeholder="Nombre y apellidos" required></label>
  <button type="submit">Ingresar</button>
</form>
{('<p>O usa una identidad de prueba:</p>' + picks) if picks else ''}""")


def cuidador(token: str, nombre: str, relaciones: list[tuple[str, str]], error: str = "") -> tuple[str, int]:
    opts = "".join(f'<option value="{k}">{escape(v)}</option>' for k, v in relaciones)
    err = f'<p class="warn">{escape(error)}</p>' if error else ""
    return page("Registrar persona a cargo", f"""
<h1>Modo cuidador</h1>
<p>Hola, {escape(nombre or 'cuidador/a')}. Verificamos tu identidad con ClaveÚnica.
Registra a la persona cuyos trámites vas a gestionar.</p>{err}
<form method="post" action="/id/cuidador">
  <input type="hidden" name="token" value="{escape(token)}">
  <label>Nombre completo de la persona <input name="nombre" required minlength="3" maxlength="120"></label>
  <label>RUN de la persona <input name="run" required placeholder="12.345.678-5" autocomplete="off"></label>
  <label>Relación <select name="relacion">{opts}</select></label>
  <label class="check"><input type="checkbox" name="declaro" value="si" required>
  <span>Declaro que esta persona me autorizó a gestionar sus horas, resultados y recordatorios.
  Puede revocar la autorización cuando quiera en Admisión.</span></label>
  <button type="submit">Registrar</button>
</form>
<p><small>Este formulario es seguro y está fuera del chat: MedicAI nunca pide RUN ni claves por WhatsApp.</small></p>""")
