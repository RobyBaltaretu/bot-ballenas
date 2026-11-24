// Acceso a la API del propio panel (mismo origen, sin CORS). El token del panel va SOLO en la cabecera de los
// POST: nunca en la URL, ni en localStorage, ni en registros.

const meta = (n) => document.querySelector(`meta[name="${n}"]`)?.content || "";
const TOKEN = meta("panel-token");
export const SOLO_LECTURA = meta("panel-solo-lectura") === "1";

export class ErrorApi extends Error {
  constructor(mensaje, estado) {
    super(mensaje);
    this.estado = estado;
  }
}

async function leer(r) {
  const tipo = r.headers.get("content-type") || "";
  return tipo.includes("application/json") ? r.json() : {error: (await r.text()).slice(0, 300)};
}

export async function obtener(ruta, {timeout = 15000} = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(ruta, {cache: "no-store", credentials: "same-origin", signal: ctl.signal});
    const d = await leer(r);
    if (!r.ok) throw new ErrorApi(d.error || `error ${r.status}`, r.status);
    return d;
  } catch (e) {
    if (e instanceof ErrorApi) throw e;
    throw new ErrorApi(e.name === "AbortError" ? "el panel no responde (tiempo agotado)" : "no se pudo contactar con el panel", 0);
  } finally {
    clearTimeout(t);
  }
}

export async function enviar(ruta, cuerpo) {
  let r;
  try {
    r = await fetch(ruta, {method: "POST", cache: "no-store", credentials: "same-origin",
      headers: {"Content-Type": "application/json", "X-Panel-Token": TOKEN}, body: JSON.stringify(cuerpo)});
  } catch (e) {
    return {ok: false, estado: 0, error: "no se pudo contactar con el panel"};
  }
  const d = await leer(r);
  return {...d, ok: r.ok && d.ok !== false, estado: r.status};
}

/** Espera la respuesta del bot a un comando (lo confirma el BOT, no el panel). */
export async function esperarResultado(id, {intentos = 30, cada = 2000} = {}) {
  for (let i = 0; i < intentos; i++) {
    await new Promise((ok) => setTimeout(ok, cada));
    try {
      const r = await obtener(`/api/resultado?id=${encodeURIComponent(id)}`);
      if (!r.pendiente) return r;
    } catch (e) { /* se reintenta */ }
  }
  return {pendiente: true, mensaje: "el bot aún no ha confirmado (¿está en marcha?)"};
}
