// ESTRATEGIAS (18/11/2026, estilo terminal): lista con minigráfico y barra de evidencia, ficha de cada estrategia
// (acierto, R:R, esperanza, operaciones, caída, curva de capital, caída bajo el agua y robustez por meses) y pestañas
// para cerebro, régimen, cartera y probador. Sin «ganadora» ni «rentable»: los estados son los del laboratorio.

import {obtener} from "../api.js";
import {chip, errorCarga, h, listaDef, pestanasVista, reemplazar, seccion, tabla, vacio} from "../dom.js";
import {bot, preferencias} from "../estado.js";
import {conSigno, fecha, hay, iso, num} from "../formato.js";
import {graficoLinea, svg} from "../grafico.js";
import {ayuda, info, titulo} from "../info.js";
import {explicacion} from "./explicaciones.js";
import {pestanaCarry} from "./carry.js";

const ETAPA = {investigacion: "en investigación", laboratorio: "superó el laboratorio", shadow: "observación", paper: "simulado",
  apta_revision: "apta para revisión", real_habilitado: "REAL habilitado"};
const VEREDICTO = {supera: ["Supera", "ok"], exploratorio: ["Exploratorio", "aviso"], no_supera: ["No supera", null], no_evaluable: ["Sin datos", null]};

function veredicto(e) {
  const [t, c] = VEREDICTO[e] || [e || "sin evaluar", null];
  return chip(t, c);
}

function partes(clave) {
  const [nombre, iv] = String(clave).split(/_(?=\d+[hm]$)/);
  return [nombre.replaceAll("_", " "), iv || ""];
}

/** Minigráfico de la curva de capital (R acumulado) para la lista. */
function mini(vals) {
  if (!vals || vals.length < 2) return h("span", {clase: "mini vacio-mini", title: "La curva aparece tras el laboratorio del 22/11"}, "—");
  const W = 100, H = 28, min = Math.min(...vals, 0), max = Math.max(...vals, 0), r = max - min || 1;
  const d = vals.map((v, i) => `${i ? "L" : "M"}${(i / (vals.length - 1) * W).toFixed(1)} ${(H - (v - min) / r * H).toFixed(1)}`).join(" ");
  const lienzo = svg("svg", {viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", "aria-hidden": "true", class: "mini"});
  lienzo.append(svg("path", {d, class: vals[vals.length - 1] >= 0 ? "sube" : "baja", "vector-effect": "non-scaling-stroke"}));
  return lienzo;
}

/** Barra «fuerza de la evidencia»: t fuera de muestra frente al listón (corrección por todas las variantes). */
function barraEvidencia(t, liston) {
  const uso = hay(t) && liston ? Math.max(0, Math.min(100, t / liston * 100)) : 0;
  return h("div", {clase: "evidencia", title: hay(t) ? `t ${num(t, 2)} de ${num(liston, 1)} necesarios` : "sin datos"},
    h("span", {estilo: {width: `${uso}%`}}));
}

const AYUDA_LISTA = ["Cada fila es una estrategia con el resultado del laboratorio fuera de muestra (datos que no usó para elegir sus parámetros).",
  "La barra es la fuerza de la evidencia: hasta dónde llega su estadístico t frente al listón necesario. Llena = pasaría esa prueba.",
  "El minigráfico es su curva de capital fuera de muestra (aparece tras el laboratorio del 22/11)."];

function lista(est, liston) {
  if (!est.length) return vacio("El bot no ha informado de estrategias (¿está en marcha?).");
  return h("ul", {clase: "lista lista-estrategias"}, est.map((e) => {
    const [nombre, iv] = partes(e.clave);
    return h("li", {}, h("a", {clase: "fila", href: `#/estrategia/${encodeURIComponent(e.clave)}`, "aria-label": `${e.clave}: ver ficha`},
      h("span", {clase: "avatar", "aria-hidden": "true"}, iv || "—"),
      h("div", {clase: "centro"},
        h("div", {clase: "titulo"}, nombre, e.activa ? null : h("span", {clase: "muy-tenue"}, " · apagada")),
        explicacion(e.clave) ? h("div", {clase: "sub resumen-estrategia"}, explicacion(e.clave).resumen) : null,
        h("div", {clase: "sub"}, barraEvidencia(e.lab?.oos_t, liston),
          h("span", {}, hay(e.lab?.oos_n) ? `${e.lab.oos_n} ops · ${conSigno(e.lab.oos_r, 3)} R` : "sin muestra"))),
      mini(e.lab?.mini),
      h("div", {clase: "derecha"}, veredicto(e.lab?.estado))));
  }));
}

function cerebro(b) {
  const c = b.cerebro || {};
  const filas = Object.entries(c.modelos || {});
  return seccion(titulo("Cerebro", "Qué es el cerebro", "Es el único que decide qué propuestas se operan.",
    "Si su modelo no supera el laboratorio, en real se abstiene. En simulado puede decidir «en exploración» para acumular evidencia."),
  filas.length ? tabla([
    {t: "Velas", v: ([iv]) => iv}, {t: "Veredicto", v: ([, m]) => veredicto(m.estado_laboratorio)},
    {t: "Entrenado con", v: ([, m]) => hay(m.n) ? `${m.n} casos` : "—", der: true},
    {t: "Hasta", v: ([, m]) => fecha(m.entrenado_hasta)},
  ], filas) : vacio(c.error || "Sin modelo del cerebro."));
}

function regimenBtc(b) {
  const r = b.regimen_btc || {};
  if (!r.activo) return seccion("Tendencia de BTC", vacio("Filtro apagado: se opera en los dos sentidos."));
  const [texto, clase, permite] = r.alcista === true ? ["Alcista", "ok", "solo entran largos"]
    : r.alcista === false ? ["Bajista", "aviso", "solo entran cortos"] : ["Aún sin calcular", null, "se calcula al cerrar la próxima vela de 4 h"];
  return seccion(titulo("Tendencia de BTC", "Filtro de tendencia de BTC",
    `Compara el cierre de BTC (velas de 4 h) con su media de ${r.media ?? 200} velas. Las estrategias solo entran a favor de esa tendencia.`,
    "La cartera de funding no pasa por este filtro: lleva largos y cortos a la vez."),
  h("p", {clase: "cifra-media"}, chip(texto, clase), " ", h("span", {clase: "tenue"}, permite)));
}

function carteraFunding(b) {
  const c = b.cartera_funding || {};
  if (!c.activa) return seccion("Cartera de funding", vacio("Módulo apagado."));
  const ahora = new Date();
  const dias = (8 - ahora.getUTCDay()) % 7 || 7;
  const proximo = new Date(Date.UTC(ahora.getUTCFullYear(), ahora.getUTCMonth(), ahora.getUTCDate() + dias));
  const abiertas = (b.posiciones || []).filter((p) => p.cartera_funding);
  const patas = [...(c.largos || []).map((x) => ({...x, lado: "largo"})), ...(c.cortos || []).map((x) => ({...x, lado: "corto"}))];
  return seccion(titulo("Cartera de funding", "Cartera de funding",
    "Cada lunes a las 00:00 UTC: largo en las monedas con el funding más bajo y corto en las de funding más alto.",
    "Abre las dos patas o ninguna, con los límites de riesgo de siempre. Dinero ficticio; no está validada como rentable."),
  listaDef([
    ["Próximo rebalanceo", fecha(proximo.getTime() / 1000)],
    ["Patas abiertas", String(abiertas.length)],
    ...(c.caben ? [["Cabían nuevas", `${c.caben.L} largas · ${c.caben.S} cortas`]] : []),
  ]),
  patas.length ? tabla([
    {t: "Moneda", v: (x) => h("strong", {}, x.moneda)}, {t: "Lado", v: (x) => x.lado},
    {t: "Funding 7 d (%/h)", v: (x) => num(x.funding, 4), der: true},
    {t: "Abierta", v: (x) => abiertas.some((p) => p.moneda === x.moneda) ? "sí" : "no"},
  ], patas) : vacio("Aún no ha habido ninguna selección semanal."));
}

function probador(b) {
  const p = b.probador || {};
  const filas = Object.entries(p.estrategias || {});
  const res = (x) => x && x.n ? `${x.n} · ${conSigno(x.r_medio, 2)} R` : "—";
  const c = p.cerebro || {};
  return seccion(titulo("Resultados en vivo", "Resultados en vivo (simulado)",
    "«Operadas»: las que el bot abrió en simulado. «Exploración»: abiertas con riesgo reducido para aprender. «Sombra»: propuestas que no se abrieron pero se siguen en papel.",
    "Dinero ficticio. Con menos de 30 operaciones por grupo nada es concluyente."),
  filas.length ? [tabla([{t: "Estrategia", v: ([k]) => k},
    {t: "Operadas", v: ([, v]) => res(v.operadas), der: true},
    {t: "Exploración", v: ([, v]) => res(v.exploracion), der: true},
    {t: "Sombra", v: ([, v]) => res(v.sombra), der: true}], filas),
  h("p", {clase: "muy-tenue"}, `Cerebro: aceptadas ${res(c.aceptadas)} · rechazadas ${res(c.rechazadas)} · desde ${fecha(p.desde)}`)]
    : vacio("Aún no hay resultados en vivo."));
}

function preregistro(pr) {
  const filas = Object.entries(pr || {});
  return seccion(titulo("Hipótesis prerregistradas", "Hipótesis prerregistradas",
    "Dos estrategias fijadas de antemano (17/11) que se juzgan solo con datos nuevos y una sola vez, al llegar a 30 operaciones en 20 días distintos.",
    "Así el listón baja a t ≥ ~2 sin hacer trampas. Hasta llegar, el resultado no se mira."),
  filas.length ? h("ul", {clase: "lista"}, filas.map(([k, p]) => h("li", {}, h("div", {clase: "fila"},
    h("div", {clase: "centro"}, h("div", {clase: "titulo"}, k.replaceAll("_", " ")),
      h("div", {clase: "sub"}, p.estado === "acumulando" ? `${p.progreso?.operaciones ?? 0} de 30 operaciones · ${p.progreso?.dias ?? 0} de 20 días` : (p.motivo || ""))),
    h("div", {clase: "derecha"}, chip(p.estado, p.estado === "confirmada" ? "ok" : p.estado === "rechazada" ? "mal" : null))))))
    : vacio("Aparecen tras el laboratorio del domingo 22/11."));
}

let raiz = null;
let firmaPintada = null;
let labCache = null;

async function pintar() {
  const b = bot();
  let errLab = null;
  try {
    labCache = await obtener("/api/laboratorio");
  } catch (e) { errLab = e.message; }
  const lab = labCache || {filas: []};
  if (!raiz) return;
  const porClave = Object.fromEntries((lab.filas || []).map((f) => [f.clave, f]));
  const est = (b.estrategias || []).map((e) => ({...e, lab: porClave[e.clave]}))
    .sort((a, c) => (c.activa - a.activa) || ((c.lab?.oos_r ?? -9) - (a.lab?.oos_r ?? -9)));
  const liston = b.investigacion?.t_requerido || 4;
  reemplazar(raiz,
    h("div", {clase: "titulo-vista"}, h("div", {}, h("h1", {}, "Estrategias"),
      h("p", {}, `Laboratorio del ${fecha(iso(lab.generado))} `, info("etapa", "etapas")))),
    pestanasVista("estrategias", [
      ["lista", "Estrategias", () => seccion(titulo("Qué dice el laboratorio", "Cómo leer esta lista", ...AYUDA_LISTA),
        errLab ? errorCarga(`No se pudo leer el laboratorio: ${errLab}`) : null, lista(est, liston))],
      ["vivo", "En vivo", () => [probador(b), preregistro(lab.preregistro)]],
      ["cerebro", "Cerebro y tendencia", () => [cerebro(b), regimenBtc(b)]],
      ["carry", "Carry (2 patas)", () => pestanaCarry()],
      ["cartera", "Cartera de funding", () => carteraFunding(b)],
    ], "Secciones de estrategias"));
}

// ---------------------------------------------------------------- ficha de una estrategia
function kpi(etq, valor, pie, ayudaTxt) {
  return h("div", {clase: "paso"}, h("div", {clase: "etq"}, etq, ayudaTxt ? [" ", ayuda(etq, ayudaTxt)] : null),
    h("div", {clase: "v"}, valor), h("div", {clase: "pie"}, pie || ""));
}

function bajoElAgua(puntos) {
  const W = 1000, H = 60;
  const ts = puntos.map((p) => p[0]), dd = puntos.map((p) => p[2]);
  const t0 = ts[0], t1 = ts[ts.length - 1] === t0 ? t0 + 1 : ts[ts.length - 1];
  const min = Math.min(...dd, -0.001);
  const d = puntos.map(([t, , v], i) => `${i ? "L" : "M"}${((t - t0) / (t1 - t0) * W).toFixed(1)} ${(v / min * H).toFixed(1)}`).join(" ");
  const lienzo = svg("svg", {viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", role: "img",
    "aria-label": `Caída desde el máximo; la peor, ${num(-min, 1)} R`});
  lienzo.append(svg("path", {d: `M0 0 ${d.slice(1)} L${W} 0 Z`, class: "agua"}));
  return h("div", {clase: "bajo-agua"}, lienzo);
}

function meses(m) {
  const filas = Object.entries(m || {}).sort();
  if (!filas.length) return null;
  const tope = Math.max(...filas.map(([, x]) => Math.abs(x.r)), 0.001);
  return h("div", {clase: "meses", role: "list"}, filas.map(([mes, x]) => h("div", {
    role: "listitem", clase: ["mes", x.r > 0 ? "sube" : x.r < 0 ? "baja" : null], title: `${mes}: ${conSigno(x.r, 2)} R en ${x.n} operaciones`,
    estilo: {opacity: String(0.35 + 0.65 * Math.abs(x.r) / tope)}}, mes.slice(2).replace("-", "/"))));
}

/** Tarjeta «Qué es»: qué hace, cómo funciona y qué persigue la estrategia, en tres líneas. */
function queEs(clave) {
  const x = explicacion(clave);
  if (!x) return null;
  const bloque = (n, etq, txt) => h("div", {clase: "explica-bloque", estilo: {"--k": String(n)}},
    h("div", {clase: "explica-etq"}, etq), h("p", {}, txt));
  return h("section", {clase: "explica", "aria-label": "Qué es esta estrategia"},
    h("p", {clase: "explica-resumen"}, x.resumen),
    h("div", {clase: "explica-rejilla"}, bloque(0, "Qué hace", x.hace), bloque(1, "Cómo funciona", x.como), bloque(2, "Qué persigue", x.persigue)));
}

export const detalle = {
  async entrar(el, clave) {
    reemplazar(el, h("p", {clase: "cargando"}, "Cargando estrategia…"));
    let d;
    try {
      d = await obtener(`/api/estrategia?clave=${encodeURIComponent(clave)}`);
    } catch (e) {
      reemplazar(el, h("p", {}, h("a", {href: "#/estrategias"}, "← Estrategias")), errorCarga(e.estado === 404 ? "Estrategia sin datos." : e.message));
      return;
    }
    const lab = d.laboratorio || {};
    const oos = lab.fuera_de_muestra || lab.validacion || {};
    const cur = lab.curva || {};
    const ver = lab.veredicto || {};
    const [nombre, iv] = partes(clave);
    // R:R medio de ganadoras frente a perdedoras; antes de tener la curva se deduce del factor de beneficio y el acierto.
    const p = (cur.acierto_pct ?? oos.ganan_pct) / 100;
    const rr = cur.rr ?? (hay(oos.factor_beneficio) && p > 0 && p < 1 ? oos.factor_beneficio * (1 - p) / p : null);
    const viv = (bot().probador?.estrategias || {})[clave] || {};
    const fallos = (ver.comprobaciones || []).filter((c) => !c.cumple);
    const cifra = h("div", {clase: "cifra cifra-media"}, hay(cur.r_total) ? `${conSigno(cur.r_total, 1)} R` : "—");
    const linea = h("div", {clase: "variacion"}, h("span", {clase: "tenue"}, "acumulado fuera de muestra"));
    reemplazar(el,
      h("p", {}, h("a", {href: "#/estrategias"}, "← Estrategias")),
      h("div", {clase: "titulo-vista"}, h("div", {},
        h("h1", {}, `${nombre} `, h("span", {clase: "tenue"}, iv)),
        h("p", {}, veredicto(lab.estado_evaluacion), " ", chip(ETAPA[d.estado?.etapa] || d.estado?.etapa || "—", null),
          " ", chip(d.estado?.activa === false ? "apagada" : "propone", d.estado?.activa === false ? null : "info")))),
      queEs(clave),
      h("section", {clase: "embudo kpis", "aria-label": "Métricas fuera de muestra"},
        kpi("Acierto", hay(cur.acierto_pct ?? oos.ganan_pct) ? `${num(cur.acierto_pct ?? oos.ganan_pct, 1)} %` : "—", "operaciones ganadoras",
          "Porcentaje de operaciones que acabaron en ganancia (con costes), fuera de muestra."),
        kpi("Riesgo : beneficio", hay(rr) ? `1 : ${num(rr, 2)}` : "—", "ganancia media / pérdida media",
          "Cuánto gana de media una ganadora frente a lo que pierde una perdedora. Con 1 : 2, una ganadora compensa dos perdedoras."),
        kpi("Esperanza", hay(cur.esperanza_r ?? oos.r_medio) ? `${conSigno(cur.esperanza_r ?? oos.r_medio, 3)} R` : "—", "por operación",
          "Resultado medio por operación en R (R = lo que se pierde si salta el stop). Positiva = gana de media."),
        kpi("Operaciones", num(cur.n ?? oos.n, 0), "fuera de muestra"),
        kpi("Caída máx.", hay(cur.caida_max_r ?? oos.caida_max_r) ? `${num(cur.caida_max_r ?? oos.caida_max_r, 1)} R` : "—", "peor racha",
          "La mayor caída desde un máximo de la curva, en R. Mide lo dura que fue la peor racha.")),
      seccion(titulo("Curva de capital", "Curva de capital", "R acumulado de las operaciones fuera de muestra, en orden de cierre.",
        "Debajo, la caída desde el máximo («bajo el agua»): cuánto se perdía en cada momento respecto al mejor punto anterior."),
      (cur.puntos || []).length >= 2 ? [cifra, linea, graficoLinea(cur.puntos.map((x) => [x[0], x[1]]), {cifra, linea,
        valor: (v) => `${conSigno(v, 1)} R`, pie: (v0, vi, t) => [h("span", {clase: "tenue"}, fecha(t))],
        etiqueta: `Curva de capital de ${clave}`}), bajoElAgua(cur.puntos)]
        : h("div", {clase: "grafico-vacio"}, "La curva aparece tras el laboratorio del domingo 22/11.")),
      seccion(titulo("Robustez por meses", "Robustez por meses", "Cada casilla es un mes: verde si ganó, rojo si perdió; más intenso cuanto mayor fue el resultado.",
        "Una estrategia robusta gana en la mayoría de meses, no solo en uno o dos."),
      cur.meses ? [h("p", {clase: "tenue"}, `${cur.meses_positivos} de ${cur.meses_total} meses en positivo`), meses(cur.meses)]
        : h("p", {clase: "vacio"}, "Aparece tras el laboratorio del domingo 22/11.")),
      seccion("En vivo (simulado)", listaDef([
        ["Operadas", viv.operadas?.n ? `${viv.operadas.n} · ${conSigno(viv.operadas.r_medio, 2)} R de media` : "ninguna"],
        ["En sombra", viv.sombra?.n ? `${viv.sombra.n} · ${conSigno(viv.sombra.r_medio, 2)} R de media` : "ninguna"],
      ])),
      fallos.length ? h("details", {clase: "plegable"}, h("summary", {}, `Por qué no supera (${fallos.length} ${fallos.length === 1 ? "regla" : "reglas"})`),
        h("div", {clase: "cuerpo"}, h("ul", {clase: "lista-simple"}, fallos.map((c) => h("li", {}, c.regla))))) : null,
      preferencias.experto ? h("details", {clase: "plegable"}, h("summary", {}, "Datos completos (técnico)"),
        h("div", {clase: "cuerpo"}, h("pre", {clase: "json"}, JSON.stringify(d, null, 1)))) : null);
  },
};

export const vista = {
  async entrar(el) { raiz = el; reemplazar(el, h("p", {clase: "cargando"}, "Cargando…")); await pintar(); },
  // Se repinta cuando llegan los datos del bot o cambian cartera o régimen (no en cada refresco).
  actualizar() {
    const b = bot() || {};
    const firma = JSON.stringify([Object.keys(b).length > 0, b.cartera_funding, b.regimen_btc]);
    if (raiz && firma !== firmaPintada) { firmaPintada = firma; pintar(); }
  },
  salir() { raiz = null; firmaPintada = null; },
};
