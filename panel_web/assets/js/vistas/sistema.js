// OBSERVABILIDAD: salud TÉCNICA del bot, separada del trading (sin saldo, PnL ni posiciones). «Responde» no es
// «sano»: se resalta lo viejo, lo ausente y lo desconocido.

import {SOLO_LECTURA, enviar, obtener} from "../api.js";
import {chip, errorCarga, escribiendo, h, pestanasVista, reemplazar, seccion, tabla} from "../dom.js";
import {preferencias} from "../estado.js";
import {duracion, fecha, frescura, hace, num} from "../formato.js";
import {info} from "../info.js";
import {cerrarTaller, pestanaTaller} from "./taller.js";

const CLASE = {correcto: "ok", degradado: "aviso", fallido: "mal", sin_datos: "aviso", desactualizado: "aviso", desactivado: null};
const filtro = {nivel: "WARNING", componente: "", traza: "", q: ""};
let raiz = null;
let temporizador = null;

function estadoComponente(c, ahora) {
  if (!c) return chip("desconocido", "aviso");
  const viejo = c.ts && ahora - c.ts > 600 && c.estado === "correcto";
  return chip(viejo ? "correcto pero sin actualizar" : (c.estado || "desconocido").replace("_", " "), viejo ? "aviso" : CLASE[c.estado] ?? "aviso");
}

async function pintar() {
  if (!raiz) return;
  const p = new URLSearchParams({limite: "40"});
  for (const [k, v] of Object.entries(filtro)) if (v) p.set(k, v);
  let d;
  try {
    d = await obtener(`/api/observabilidad?${p}`);
  } catch (e) {
    if (raiz) reemplazar(raiz.querySelector("#obs") || raiz, errorCarga(`No se pudo leer el estado del sistema: ${e.message}`));
    return;
  }
  if (!raiz) return;
  const s = d.sistema || {};
  const ahora = d.ahora;
  const lat = frescura(s.latido_ts, ahora, {retraso: 180, obsoleto: 600});
  const comps = Object.entries(s.componentes || {});
  const obligFall = [...(s.obligatorios_fallidos || []), ...(s.obligatorios_sin_datos || [])];
  const ct = s.contadores || {};
  const incs = d.incidentes || [];
  const abiertos = incs.filter((i) => i.estado !== "resuelto");
  const zona = raiz.querySelector("#obs");
  // Las tarjetas técnicas (estado global, latido, ciclo) van en «Componentes»; el Taller ya lo resume en lenguaje llano.
  const resumen = h("div", {clase: "rejilla"},
      h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "Estado global ", info("estado_componente", "estados")),
        h("div", {clase: "valor"}, chip(s.estado_global || "desconocido", CLASE[s.estado_global] ?? "aviso"))),
      h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "Último latido ", info("latido", "latido")), h("div", {clase: "valor"}, chip(lat.texto, lat.clase))),
      h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "Duración del ciclo ", info("ciclo_p95", "duración del ciclo")),
        h("div", {clase: "valor"}, `${num(s.ciclo_mediana_seg, 1)} s`), h("div", {clase: "pie"}, `p95 ${num(s.ciclo_p95_seg, 1)} s · ${s.ciclos_fallidos ?? 0} de ${s.ciclos ?? 0} fallidos`)),
      h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "Incidentes abiertos ", info("incidente", "incidente")), h("div", {clase: "valor"}, String(abiertos.length))));
  reemplazar(zona,
    obligFall.length ? h("p", {clase: "aviso mal"}, `Componentes obligatorios con problemas: ${obligFall.join(", ")}`) : null,
    pestanasVista("sistema", [
    ["taller", "Taller", () => pestanaTaller()],
    ["componentes", "Componentes", () => [resumen, seccion(null, tabla([
      {t: "Componente", v: ([k, c]) => h("span", {}, h("strong", {}, k), c.descripcion ? h("div", {clase: "muy-tenue"}, c.descripcion) : null)},
      {t: "Estado", v: ([, c]) => estadoComponente(c, ahora)},
      {t: "Detalle", v: ([, c]) => c.detalle || "—"},
      {t: "Actualizado", v: ([, c]) => hace(c.ts, ahora)},
    ], comps, {vacioTexto: "El bot no ha informado de sus componentes (¿está apagado?)."}))]],
    ["incidentes", `Incidentes · ${abiertos.length}`, () => seccion(null, tabla([
      {t: "Severidad", v: (i) => chip(i.severidad, i.severidad === "error" ? "mal" : "aviso")},
      {t: "Componente", v: (i) => i.componente},
      {t: "Mensaje", v: (i) => h("span", {}, i.mensaje, i.recomendacion ? h("div", {clase: "muy-tenue"}, i.recomendacion) : null)},
      {t: "Primera / última vez", v: (i) => `${fecha(i.primer_ts)} / ${hace(i.ultimo_ts, ahora)} (${i.repeticiones}×)`},
      {t: "Estado", v: (i) => i.estado === "activo" && !SOLO_LECTURA
        ? h("button", {type: "button", onClick: async (e) => { e.stopPropagation(); e.currentTarget.disabled = true; await enviar("/api/incidente", {id: i.id}); pintar(); }}, "Reconocer")
        : i.estado},
    ], incs.slice(0, 20), {vacioTexto: "Sin incidentes registrados."}))],
    ["registros", "Registros", () => seccion(h("span", {}, "Registros técnicos ", info("traza", "traza")), filtros(d), tabla([
      {t: "Hora (UTC)", v: (e) => h("span", {clase: "mono"}, (e.ts || "").replace("T", " ").replace("Z", ""))},
      {t: "Nivel", v: (e) => chip(e.nivel, e.nivel === "ERROR" || e.nivel === "CRITICAL" ? "mal" : e.nivel === "WARNING" ? "aviso" : null, {punto: false})},
      {t: "Componente", v: (e) => e.componente || "—"},
      {t: "Mensaje", v: (e) => h("span", {}, e.mensaje, e.traza && preferencias.experto ? h("button", {type: "button", clase: "muy-tenue",
        onClick: () => { filtro.traza = e.traza; pintar(); }}, ` traza ${e.traza}`) : null)},
    ], (d.logs || []).slice(0, 40), {vacioTexto: "No hay registros con estos filtros."}),
    h("p", {}, h("a", {clase: "boton", href: "/api/diagnostico", download: ""}, "Descargar diagnóstico (sin saldo ni secretos)")))],
    ["contadores", "Contadores", () => seccion(h("span", {}, "Contadores ", info("contadores", "contadores")), tabla([
      {t: "Contador", v: ([k]) => k.replaceAll("_", " ")}, {t: "Valor", v: ([, v]) => typeof v === "object" ? JSON.stringify(v) : String(v), der: true},
    ], Object.entries(ct), {vacioTexto: "Sin contadores."}),
    s.disco ? h("p", {clase: "muy-tenue"}, `Disco: ${typeof s.disco === "object" ? Object.entries(s.disco).map(([k, v]) => `${k} ${v}`).join(" · ") : s.disco}`) : null)],
    ], "Secciones del sistema"));
}

function filtros(d) {
  const nivel = h("select", {onChange: (e) => { filtro.nivel = e.target.value; pintar(); }},
    ["DEBUG", "INFO", "WARNING", "ERROR"].map((n) => h("option", {value: n, selected: filtro.nivel === n || null}, n)));
  const comp = h("select", {onChange: (e) => { filtro.componente = e.target.value; pintar(); }}, h("option", {value: ""}, "todos"),
    (d.componentes_log || []).map((c) => h("option", {value: c, selected: filtro.componente === c || null}, c)));
  const q = h("input", {type: "search", valor: filtro.q, placeholder: "texto…", onChange: (e) => { filtro.q = e.target.value.trim(); pintar(); }});
  return h("div", {clase: "filtros"}, h("label", {}, "Nivel mínimo", nivel), h("label", {}, "Componente", comp), h("label", {}, "Buscar", q),
    filtro.traza ? h("button", {type: "button", onClick: () => { filtro.traza = ""; pintar(); }}, `Quitar traza ${filtro.traza}`) : null);
}

export const vista = {
  async entrar(el) {
    raiz = el;
    reemplazar(el, h("div", {clase: "titulo-vista"}, h("div", {}, h("h1", {}, "Taller"),
      h("p", {}, "Revisa que todo esté en orden y arregla lo que falle."))),
    h("div", {id: "obs"}, h("p", {clase: "cargando"}, "Cargando…")));
    await pintar();
    temporizador = setInterval(() => { if (!document.hidden && !escribiendo(raiz)) pintar(); }, 15000);
  },
  salir() { raiz = null; clearInterval(temporizador); cerrarTaller(); },
};
