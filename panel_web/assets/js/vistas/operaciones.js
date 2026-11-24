// OPERACIONES (rediseño 19/11/2026): tres pestañas en vez de una lista larga con filtros —
//   · «En vivo»: cada posición abierta como un carril (stop · entrada · objetivo) con el precio actual moviéndose entre ellos;
//   · «Historial»: las cerradas agrupadas por día, con una tira de pulso de resultados y una barra de R por operación;
//   · «Descartes»: lo que el bot propuso y no ejecutó, con su motivo.
// Datos: /api/operaciones (ledger) y la foto del bot (posiciones). Lo que el ledger no confirma se muestra como
// desconocido: nunca se deduce un cierre porque una orden desaparezca. Esta vista solo lee; ajustar stop/objetivo sigue
// en la ficha de cada operación (y lo valida el bot).

import {cifraViva} from "../anim.js";
import {SOLO_LECTURA, enviar, esperarResultado, obtener} from "../api.js";
import {chip, errorCarga, h, listaDef, pestanasVista, reemplazar, seccion, tabla, vacio} from "../dom.js";
import {bot, estado, preferencias} from "../estado.js";
import {conSigno, corto, duracion, fecha, hace, hay, iso, lado, num, pct, precio, resultado, usd} from "../formato.js";
import {graficoLinea} from "../grafico.js";
import {info} from "../info.js";

const ESTADOS = {senal: "señal", aprobada: "aprobada", rechazada: "rechazada", enviada: "orden enviada", abierta: "abierta",
  parcial: "parcial", completada: "completada", cerrando: "cerrando", cerrada: "cerrada", error: "error",
  desconocido: "desconocido", shadow: "shadow (sin órdenes)", shadow_cerrada: "shadow cerrada (modelado)"};
const CLASE_ESTADO = {cerrada: null, abierta: "info", rechazada: null, error: "mal", desconocido: "aviso", cerrando: "aviso"};

const filtros = {estado: "", moneda: "", lado: "", estrategia: "", origen: "", q: "", solo_ejecutadas: "1", pagina: 1};

function parametros(extra = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries({...filtros, ...extra})) if (v !== "" && v !== null && v !== undefined) p.set(k, v);
  return p;
}

function estadoOp(e) {
  return chip(ESTADOS[e] || e || "—", CLASE_ESTADO[e] ?? null);
}

// ---------------------------------------------------------------- el carril de una posición abierta
/** Escala de precios: stop, entrada, objetivos y precio actual sobre una misma línea. Todo son datos de la posición. */
export function carril(p) {
  const niveles = [["stop", p.sl], ["entrada", p.entrada], ["obj1", p.tp1], ["obj", p.tpf]].filter(([, v]) => hay(v)).map(([k, v]) => [k, Number(v)]);
  const mark = hay(p.precio_mark) ? Number(p.precio_mark) : null;
  const todos = [...niveles.map((n) => n[1]), ...(mark !== null ? [mark] : [])];
  if (todos.length < 2) return h("div", {clase: "carril vacio"}, h("span", {clase: "muy-tenue"}, "Sin precios suficientes para dibujar el recorrido."));
  const min = Math.min(...todos), max = Math.max(...todos);
  const pad = (max - min) * 0.08 || max * 0.01;
  const lo = min - pad, hi = max + pad;
  const pos = (v) => `${Math.max(0, Math.min(100, (v - lo) / (hi - lo) * 100)).toFixed(2)}%`;
  const entrada = hay(p.entrada) ? Number(p.entrada) : null;
  const aFavor = mark !== null && entrada !== null ? (p.lado === "S" ? mark < entrada : mark > entrada) : null;
  const tramo = mark !== null && entrada !== null
    ? h("span", {clase: ["tramo", aFavor ? "gana" : "pierde"], estilo: {left: pos(Math.min(mark, entrada)), width: `${Math.abs((mark - entrada) / (hi - lo) * 100).toFixed(2)}%`}}) : null;
  const marcas = niveles.map(([k, v]) => h("span", {clase: ["marca", `m-${k}`], estilo: {left: pos(v)}, title: `${{stop: "Stop", entrada: "Entrada", obj1: "Objetivo 1", obj: "Objetivo"}[k]} ${precio(v)}`},
    h("i", {}), h("em", {}, `${{stop: "stop", entrada: "entrada", obj1: "obj. 1", obj: "obj."}[k]} ${precio(v)}`)));
  const ahora = mark !== null ? h("span", {clase: ["marca", "m-ahora", aFavor === null ? null : aFavor ? "gana" : "pierde"], estilo: {left: pos(mark)}, title: `Ahora ${precio(mark)}`},
    h("i", {}), h("em", {}, `ahora ${precio(mark)}`)) : null;
  return h("div", {clase: "carril", role: "img", "aria-label": `Recorrido de ${p.moneda}: stop ${precio(p.sl)}, entrada ${precio(p.entrada)}, ahora ${precio(p.precio_mark)}`},
    h("div", {clase: "carril-pista"}, tramo, marcas, ahora));
}

// ---------------------------------------------------------------- pestaña «En vivo»
function tarjetaViva(p, k) {
  const explora = p.exploracion_amplia || p.explorando;
  const ganando = hay(p.pnl_no_realizado) ? p.pnl_no_realizado >= 0 : null;
  const dist = hay(p.distancia_stop_pct) ? p.distancia_stop_pct : null;
  const riesgoCerca = dist !== null && dist < 0.6;
  return h("a", {clase: ["viva", p.lado === "L" ? "largo" : "corto", ganando === null ? null : ganando ? "gana" : "pierde", riesgoCerca ? "cerca" : null],
    href: `#/operacion/${encodeURIComponent(p.trade_id)}`, estilo: {"--k": String(k)}, "aria-label": `${p.moneda} ${lado(p.lado)}: ver la operación`},
  h("div", {clase: "viva-cab"},
    h("span", {clase: ["avatar", p.lado === "L" ? "largo" : "corto"], "aria-hidden": "true"}, String(p.moneda || "?").slice(0, 4)),
    h("div", {clase: "viva-titulo"}, h("strong", {}, p.moneda), h("span", {clase: "tenue"}, `${lado(p.lado)} · ${num(p.tam, 4)}${p.cartera_funding ? " · cartera de funding" : explora ? " · exploración" : ""}`)),
    h("div", {clase: "viva-pnl"}, h("b", {}, resultado(p.pnl_no_realizado)), h("span", {clase: "tenue"}, "ahora mismo"))),
  carril(p),
  h("div", {clase: "viva-datos"},
    h("span", {}, h("i", {}, "cantidad"), `${num(p.tam, 4)} ${p.moneda || ""}`),
    h("span", {}, h("i", {}, "entrada"), precio(hay(p.entrada_cuenta) && p.ampliacion ? p.entrada_cuenta : p.entrada)),
    h("span", {}, h("i", {}, "importe"), usd(p.notional)),
    h("span", {}, h("i", {}, "apalanc."), hay(p.apalancamiento) ? `${num(p.apalancamiento, 0)}×` : "—"),
    h("span", {}, h("i", {}, "margen"), usd(p.margen)),
    h("span", {}, h("i", {}, "riesgo"), usd(p.riesgo_usd))),
  h("div", {clase: "viva-pie"},
    p.stop_verificado ? chip("stop confirmado", "ok") : chip("stop sin confirmar", "mal"),
    p.ampliacion ? chip(`ampliada +${num(p.ampliacion.tam, 4)}`, "info") : null,
    dist !== null ? h("span", {clase: riesgoCerca ? "aviso-txt" : "tenue"}, `a ${pct(dist, 1)} del stop`) : null,
    h("span", {clase: "tenue"}, p.estrategia || ""),
    (() => { const t = p.abierta_ts ? hace(iso(p.abierta_ts) ?? p.abierta_ts, estado.datos?.ahora) : ""; return t && !/sin dato/.test(t) ? h("span", {clase: "tenue"}, `abierta ${t}`) : null; })()));
}

function enVivo() {
  const b = bot();
  const pos = b.posiciones || [];
  const total = pos.every((p) => hay(p.pnl_no_realizado)) ? pos.reduce((a, p) => a + p.pnl_no_realizado, 0) : null;
  const cab = h("div", {clase: "encabezado"}, h("h2", {}, "Abiertas ahora ", info("stop_verificado", "stop verificado")),
    h("span", {clase: "tenue"}, pos.length ? h("span", {}, `${pos.length} · resultado abierto `, resultado(total)) : "ninguna"));
  if (!pos.length) {
    return h("section", {clase: "seccion"}, cab, h("div", {clase: "reposo"},
      h("div", {clase: "reposo-onda", "aria-hidden": "true"}, h("i", {}), h("i", {}), h("i", {})),
      h("p", {}, b.modo === "shadow" ? "Modo shadow: el bot no tiene posiciones, solo apunta lo que haría."
        : "El bot está vigilando. Cuando una estrategia entre, la verás aquí con su recorrido hasta el stop y el objetivo."),
      h("p", {clase: "muy-tenue"}, "Mientras tanto, mira el Historial o pregúntale a la Mesa por qué no entra nada.")));
  }
  return h("section", {clase: "seccion"}, cab,
    h("p", {clase: "muy-tenue"}, "Cada barra es el camino de la operación: el stop a un lado, el objetivo al otro y el punto es el precio de ahora. Toca una para ver su historia o ajustarla."),
    h("div", {clase: "vivas"}, pos.map(tarjetaViva)),
    (b.shadow_abiertas || []).length ? h("p", {clase: "muy-tenue"}, `${b.shadow_abiertas.length} intención(es) en sombra abiertas (sin órdenes): se ven en Estrategias.`) : null);
}

// ---------------------------------------------------------------- pestaña «Historial» y «Descartes»
let raiz = null;
let vivaZona = null;
let ultimaCarga = null;

function control(etiqueta, campo, opciones, recargar) {
  const el = opciones
    ? h("select", {onChange: (e) => { filtros[campo] = e.target.value; filtros.pagina = 1; recargar(); }},
      h("option", {value: ""}, "todas"), opciones.map((o) => h("option", {value: o, selected: filtros[campo] === o || null}, ESTADOS[o] || o)))
    : h("input", {type: "search", valor: filtros[campo], placeholder: "texto…",
      onChange: (e) => { filtros[campo] = e.target.value.trim(); filtros.pagina = 1; recargar(); }});
  return h("label", {}, etiqueta, el);
}

function dia(ts, ahora) {
  const t = iso(ts) ?? (Number.isFinite(Number(ts)) ? Number(ts) : null);
  if (!t) return "Sin fecha";
  const d = new Date(t * 1000), n = new Date(ahora * 1000);
  const mismo = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  if (mismo(d, n)) return "Hoy";
  if (mismo(d, new Date((ahora - 86400) * 1000))) return "Ayer";
  return d.toLocaleDateString("es-ES", {weekday: "long", day: "numeric", month: "long"});
}

/** Tira de pulso: una barra por operación cerrada (la más reciente a la derecha). Verde gana, rojo pierde, altura = |R|. */
function pulso(filas) {
  const cerradas = filas.filter((f) => f.estado === "cerrada" && hay(f.r_neto)).slice(0, 24).reverse();
  if (cerradas.length < 2) return null;
  const maxR = Math.max(1, ...cerradas.map((f) => Math.abs(f.r_neto)));
  return h("div", {clase: "pulso-ops", role: "img", "aria-label": `Resultado en R de las últimas ${cerradas.length} operaciones cerradas`},
    cerradas.map((f, k) => h("a", {clase: ["barrita", f.r_neto >= 0 ? "gana" : "pierde"], href: `#/operacion/${encodeURIComponent(f.trade_id)}`,
      title: `${f.moneda} ${lado(f.lado)} · ${conSigno(f.r_neto, 2)} R`, estilo: {height: `${Math.max(14, Math.sqrt(Math.abs(f.r_neto) / maxR) * 100)}%`, "--k": String(k)}})));
}

/** Barra divergente de R: a la derecha ganó, a la izquierda perdió (tope ±3 R). */
function barraR(r) {
  if (!hay(r)) return h("span", {clase: "barra-r vacia"});
  const w = Math.min(100, Math.abs(r) / 3 * 100) / 2;
  return h("span", {clase: "barra-r", title: `${conSigno(r, 2)} R`}, h("span", {clase: r >= 0 ? "gana" : "pierde", estilo: {width: `${w}%`}}));
}

function filaHistorial(f) {
  const cerrada = f.estado === "cerrada";
  const gana = cerrada && hay(f.pnl_neto) ? f.pnl_neto >= 0 : null;
  return h("li", {clase: ["hist", gana === null ? "neutra" : gana ? "gana" : "pierde"]},
    h("a", {clase: "fila", href: `#/operacion/${encodeURIComponent(f.trade_id)}`, "aria-label": `${f.moneda || "—"} ${lado(f.lado)}: ver la operación`},
      h("span", {clase: ["avatar", f.lado === "L" ? "largo" : f.lado === "S" ? "corto" : null], "aria-hidden": "true"}, String(f.moneda || "?").slice(0, 4)),
      h("div", {clase: "centro"},
        h("div", {clase: "titulo"}, `${f.moneda || "—"} · ${lado(f.lado)}`),
        h("div", {clase: "sub"}, h("span", {}, f.estrategia || "—"), h("span", {}, fecha(f.abierta_ts)), estadoOp(f.estado),
          f.ampliada ? chip("ampliada", "info") : null),
        hay(f.tam) && hay(f.precio_medio_entrada) ? h("div", {clase: "sub muy-tenue"},
          `${num(f.tam, 4)} ${f.moneda || ""} a ${precio(f.precio_medio_entrada)}`
          + (hay(f.notional_entrada) ? ` · ${usd(f.notional_entrada)}` : "")
          + (hay(f.apalancamiento) ? ` · ${num(f.apalancamiento, 0)}×` : "")
          + (hay(f.precio_medio_salida) ? ` · salida ${precio(f.precio_medio_salida)}` : "")) : null),
      cerrada ? barraR(f.r_neto) : null,
      h("div", {clase: "derecha"},
        h("div", {clase: "titulo"}, cerrada ? resultado(f.pnl_neto)
          : h("span", {clase: "tenue"}, hay(f.r_modelado) ? `modelado ${num(f.r_modelado)} R` : "—")),
        h("div", {clase: "sub"}, cerrada && hay(f.r_neto) ? h("span", {}, `${conSigno(f.r_neto, 2)} R`) : null))));
}

/** Agrupa por día manteniendo el orden del servidor (más reciente primero). */
function porDias(filas) {
  const ahora = estado.datos?.ahora || Date.now() / 1000;
  const grupos = [];
  for (const f of filas) {
    const t = dia(f.abierta_ts, ahora);
    const g = grupos[grupos.length - 1];
    if (g && g.t === t) g.filas.push(f); else grupos.push({t, filas: [f]});
  }
  return grupos.map((g, k) => {
    const cer = g.filas.filter((f) => f.estado === "cerrada" && hay(f.pnl_neto));
    const neto = cer.length ? cer.reduce((a, f) => a + f.pnl_neto, 0) : null;
    return h("section", {clase: "dia", estilo: {"--k": String(k)}},
      h("header", {}, h("h3", {}, g.t), h("span", {clase: "tenue"}, `${g.filas.length} ${g.filas.length === 1 ? "operación" : "operaciones"}`,
        neto !== null ? [" · ", resultado(neto)] : null)),
      h("ul", {clase: "lista dia-lista"}, g.filas.map(filaHistorial)));
  });
}

function listaHistorial(modo) {
  const zona = h("div", {});
  const filtrosZona = h("div", {});
  const sobreEscribir = modo === "descartes" ? {estado: "rechazada", solo_ejecutadas: ""} : {};
  async function cargar() {
    reemplazar(zona, h("p", {clase: "cargando"}, "Cargando operaciones…"));
    let d;
    try {
      d = await obtener(`/api/operaciones?${parametros({por_pagina: modo === "descartes" ? 15 : 20, ...sobreEscribir})}`);
    } catch (e) {
      reemplazar(zona, errorCarga(`No se pudieron leer las operaciones: ${e.message}`));
      return;
    }
    ultimaCarga = d;
    const r = d.resumen || {};
    const csv = `/api/operaciones?${parametros({formato: "csv", pagina: "", ...sobreEscribir})}`;
    const cols = [
      {t: "Apertura", v: (f) => fecha(f.abierta_ts)}, {t: "Moneda", v: (f) => h("strong", {}, f.moneda || "—")}, {t: "Lado", v: (f) => lado(f.lado)},
      {t: "Estrategia", v: (f) => f.estrategia || "—"}, {t: "Estado", v: (f) => estadoOp(f.estado)},
      {t: "Resultado neto", v: (f) => f.estado === "cerrada" ? resultado(f.pnl_neto) : h("span", {clase: "tenue"}, hay(f.r_modelado) ? `modelado ${num(f.r_modelado)} R` : "—"), der: true},
      {t: "R neto", v: (f) => hay(f.r_neto) ? num(f.r_neto) : "—", der: true},
    ];
    if (preferencias.experto) cols.push({t: "Origen", v: (f) => f.origen || "—"}, {t: "Comisiones", v: (f) => usd(f.comisiones, 4), der: true},
      {t: "ID", v: (f) => h("span", {clase: "mono"}, corto(f.trade_id, 8))});
    const ganadoras = hay(r.ganadoras_pct) ? r.ganadoras_pct : null;
    reemplazar(zona,
      modo === "historial" ? h("div", {clase: "kpis-ops"},
        kpi("Cerradas", cifraViva("ops.cerradas", r.cerradas ?? 0, (n) => String(Math.round(n))), "con el filtro actual"),
        kpi("Resultado neto", resultado(r.pnl_neto), "tras comisiones y funding", info("pnl_neto", "resultado neto")),
        kpi("R neto medio", hay(r.r_neto_medio) ? conSigno(r.r_neto_medio, 3) : "—", "por operación", info("r", "R")),
        h("div", {clase: "kpi anillo-kpi"}, anilloGanadoras(ganadoras), h("div", {}, h("span", {clase: "etq"}, "Ganadoras"),
          h("span", {clase: "tenue"}, ganadoras === null ? "sin cerradas" : "de las cerradas")))) : null,
      modo === "historial" ? pulso(d.filas) : null,
      (d.problemas_ledger || []).length ? h("p", {clase: "aviso"}, `El registro tiene ${d.problemas_ledger.length} línea(s) que no se pudieron leer.`) : null,
      modo === "descartes" ? h("p", {clase: "muy-tenue"}, "Propuestas que el bot rechazó: el motivo de cada una está en su ficha. No son operaciones ejecutadas.") : null,
      preferencias.experto ? tabla(cols, d.filas, {alPulsar: (f) => { location.hash = `#/operacion/${encodeURIComponent(f.trade_id)}`; }, vacioTexto: "No hay operaciones con estos filtros."})
        : (d.filas || []).length ? h("div", {clase: "dias"}, porDias(d.filas)) : vacio(modo === "descartes" ? "No hay descartes con estos filtros." : "No hay operaciones con estos filtros."),
      h("div", {clase: "paginacion"},
        h("a", {clase: "boton", href: csv, download: ""}, "Exportar CSV"),
        h("button", {type: "button", disabled: d.pagina <= 1 || null, onClick: () => { filtros.pagina--; cargar(); }}, "← Anterior"),
        h("span", {clase: "tenue"}, `Página ${d.pagina} de ${d.paginas} · ${d.total} en total`),
        h("button", {type: "button", disabled: d.pagina >= d.paginas || null, onClick: () => { filtros.pagina++; cargar(); }}, "Siguiente →")));
    if (!filtrosZona.firstChild) pintarFiltros(filtrosZona, d.valores || {}, cargar, modo);
  }
  cargar();
  return h("div", {}, filtrosZona, zona);
}

function kpi(etiqueta, valor, pie, ayuda) {
  return h("div", {clase: "kpi"}, h("span", {clase: "etq"}, etiqueta, ayuda ? [" ", ayuda] : null), h("b", {}, valor), pie ? h("span", {clase: "tenue"}, pie) : null);
}

function anilloGanadoras(p) {
  const NS = "http://www.w3.org/2000/svg";
  const sv = document.createElementNS(NS, "svg");
  sv.setAttribute("viewBox", "0 0 44 44");
  sv.setAttribute("class", "anillo mini-anillo");
  sv.setAttribute("aria-hidden", "true");
  const c = (cl, extra = {}) => {
    const e = document.createElementNS(NS, "circle");
    e.setAttribute("cx", "22"); e.setAttribute("cy", "22"); e.setAttribute("r", "17"); e.setAttribute("class", cl);
    for (const [k, v] of Object.entries(extra)) e.setAttribute(k, v);
    return e;
  };
  const largo = 2 * Math.PI * 17;
  sv.append(c("pista"), c("relleno", {"stroke-dasharray": `${((p ?? 0) / 100 * largo).toFixed(1)} ${largo.toFixed(1)}`, transform: "rotate(-90 22 22)"}));
  const t = document.createElementNS(NS, "text");
  t.setAttribute("x", "22"); t.setAttribute("y", "26"); t.setAttribute("text-anchor", "middle"); t.setAttribute("class", "anillo-num");
  t.textContent = p === null ? "—" : `${Math.round(p)}%`;
  sv.append(t);
  return sv;
}

function pintarFiltros(zona, valores, recargar, modo) {
  const solo = modo === "historial" ? h("label", {clase: "acciones"}, h("input", {type: "checkbox", marcado: filtros.solo_ejecutadas === "1",
    onChange: (e) => { filtros.solo_ejecutadas = e.target.checked ? "1" : ""; filtros.pagina = 1; recargar(); }}), "Ocultar señales y descartes") : null;
  const activos = ["estado", "moneda", "lado", "estrategia", "origen", "q"].filter((k) => filtros[k]).length;
  reemplazar(zona, h("details", {clase: "plegable", open: activos || null},
    h("summary", {}, activos ? `Filtros (${activos} activos)` : "Filtros"), h("div", {clase: "filtros cuerpo"},
      modo === "historial" ? control("Estado", "estado", Object.keys(ESTADOS), recargar) : null,
      control("Moneda", "moneda", valores.moneda || [], recargar), control("Lado", "lado", ["L", "S"], recargar),
      control("Estrategia", "estrategia", valores.estrategia || [], recargar),
      preferencias.experto ? control("Origen", "origen", valores.origen || [], recargar) : null,
      control("Buscar", "q", null, recargar), solo)));
}

export const vista = {
  async entrar(el) {
    raiz = el;
    const b = bot();
    const n = (b.posiciones || []).length;
    vivaZona = h("div", {});
    subtitulo = h("span", {});
    pintarSubtitulo();
    reemplazar(el, h("div", {clase: "titulo-vista"}, h("div", {}, h("h1", {}, "Operaciones"),
      h("p", {}, subtitulo, " Toca una para ver su historia. ", info("pnl_neto", "resultado neto")))),
    pestanasVista("operaciones", [
      ["vivo", n ? `En vivo (${n})` : "En vivo", () => { reemplazar(vivaZona, enVivo()); return vivaZona; }],
      ["historial", "Historial", () => listaHistorial("historial")],
      ["descartes", "Descartes", () => listaHistorial("descartes")],
      ["vias", "Por vía", () => pestanaVias()],
      ["ampliaciones", "Ampliaciones", () => pestanaAmpliaciones()],
      ["proceso", "Proceso", () => pestanaProceso()],
    ], "Operaciones"));
  },
  /** La foto del bot cambia cada 10 s: se repinta solo «En vivo» (sin tocar el historial ni los filtros). */
  actualizar() {
    pintarSubtitulo();
    if (vivaZona?.isConnected) reemplazar(vivaZona, enVivo());
  },
  salir() { raiz = null; vivaZona = null; subtitulo = null; },
};

let subtitulo = null;
function pintarSubtitulo() {
  if (!subtitulo) return;
  const n = (bot().posiciones || []).length;
  subtitulo.textContent = !estado.datos ? "Leyendo el estado del bot…" : n ? `${n} abierta${n > 1 ? "s" : ""} ahora.` : "Ninguna abierta ahora.";
}

// ---------------------------------------------------------------- detalle
const ESTADO_ORDEN = {
  enviada: ["Orden enviada (sin respuesta aún)", null], abierta: ["Orden aceptada (en el libro)", "ok"],
  parcial: ["Orden con fill parcial", "aviso"], completada: ["Orden completada (fill completo)", "ok"],
  cancelada: ["Orden cancelada (confirmado)", null], rechazada: ["Orden rechazada", "mal"],
  disparada: ["Trigger activado (orden hija a mercado)", "aviso"], desconocida: ["Estado de la orden DESCONOCIDO", "aviso"],
  no_confirmada: ["El exchange no conoce la orden", "aviso"], cancelacion_solicitada: ["Cancelación pedida (sin confirmar)", null],
};
const ROL = {entrada: "entrada", stop: "stop", stop_sobrante: "stop sobrante", tp1: "primer objetivo", tpf: "objetivo final",
  cierre: "cierre", tp: "objetivo", salida: "salida", huerfana: "orden huérfana"};

function lineaEvento(ev) {
  const t = ev.tipo;
  const rol = ROL[ev.rol] || ev.rol;
  let titulo, clase = null, partes = [];
  if (t === "senal") { titulo = "Señal detectada"; partes = [ev.motivo, ev.precio ? `precio ${precio(ev.precio)}` : null]; }
  else if (t === "decision") {
    titulo = ev.aprobada ? "Decisión: APROBADA" : "Decisión: rechazada"; clase = ev.aprobada ? "ok" : null;
    partes = [(ev.motivos || []).join(" · ") || null, ev.cerebro?.prediccion != null ? `cerebro ${num(ev.cerebro.prediccion, 3)} R esperados` : null,
      ev.cerebro?.exploracion ? "exploración (simulado)" : null,
      ev.plan?.riesgo_usd != null ? `riesgo previsto ${usd(ev.plan.riesgo_usd)}` : null];
  } else if (t === "orden_enviada") { titulo = `Orden de ${rol} enviada`; partes = [`tamaño ${num(ev.sz, 4)}`, ev.px ? `límite ${precio(ev.px)}` : null, ev.trigger ? `trigger ${precio(ev.trigger)}` : null, ev.reduce_only ? "reduce-only" : null]; }
  else if (t === "orden_estado") { const [txt, c] = ESTADO_ORDEN[ev.estado] || [`Orden: ${ev.estado}`, null]; titulo = `${txt} · ${rol || ""}`; clase = c; partes = [ev.ejecutado != null ? `ejecutado ${num(ev.ejecutado, 4)}` : null, ev.detalle]; }
  else if (t === "fill") { titulo = `Fill de ${rol || "orden"}`; clase = "ok"; partes = [`${num(ev.sz, 4)} a ${precio(ev.px)}`, ev.comision != null ? `comisión ${usd(ev.comision, 4)}` : null, ev.estimado ? "ESTIMADO" : null, ev.atribucion ? `atribución: ${ev.atribucion}` : null]; }
  else if (t === "proteccion") { titulo = `Protección (${ev.clase || ""}): ${ev.accion || ""}`; clase = ["fallo", "ausente_o_incorrecto", "no_verificado", "incoherente"].includes(ev.accion) ? "mal" : ev.accion === "verificado" ? "ok" : null; partes = [ev.trigger ? `trigger ${precio(ev.trigger)}` : null, ev.px ? `precio ${precio(ev.px)}` : null, ev.motivo]; }
  else if (t === "trailing") { titulo = "Stop movido"; partes = [`${precio(ev.de)} → ${precio(ev.a)}`, ev.motivo]; }
  else if (t === "funding") { titulo = "Funding"; partes = [usd(ev.usd, 4)]; }
  else if (t === "riesgo_post_fill") { titulo = "Riesgo con lo ejecutado"; partes = [`plan ${usd(ev.plan_usd)} → real ${usd(ev.real_usd)}`]; }
  else if (t === "salida_solicitada") { titulo = "El bot pide cerrar"; partes = [ev.causa]; clase = "aviso"; }
  else if (t === "cierre") { titulo = "Posición cerrada"; clase = ev.pnl_neto == null ? "aviso" : ev.pnl_neto >= 0 ? "ok" : "mal"; partes = [ev.causa, ev.pnl_neto == null ? "resultado DESCONOCIDO" : `neto ${usd(ev.pnl_neto)}`, ev.datos_fills && ev.datos_fills !== "reales" ? `fills ${ev.datos_fills}` : null]; }
  else if (t === "alerta" || t === "error") { titulo = t === "error" ? "Error" : "Alerta"; clase = t === "error" || ev.severidad === "error" ? "mal" : "aviso"; partes = [ev.mensaje]; }
  else if (t === "shadow_intencion") { titulo = "Intención shadow (sin órdenes)"; partes = [ev.motivo]; }
  else if (t === "shadow_resultado") { titulo = "Resultado shadow MODELADO"; partes = [ev.r_modelado != null ? `${num(ev.r_modelado)} R` : null]; }
  else { titulo = t; partes = [ev.accion, ev.mensaje]; }
  const cuando = iso(ev.ts);
  const hx = ev.ts_exchange ? ` · exchange ${fecha(ev.ts_exchange / (ev.ts_exchange > 1e11 ? 1000 : 1))}` : "";
  return h("li", {clase}, h("div", {}, h("strong", {}, titulo)),
    partes.filter(Boolean).length ? h("div", {clase: "tenue"}, partes.filter(Boolean).join(" · ")) : null,
    h("div", {clase: "cuando"}, `${fecha(cuando)}${hx}`),
    preferencias.experto && (ev.cloid || ev.oid) ? h("div", {clase: "muy-tenue mono"}, `cloid ${corto(ev.cloid, 14)} · oid ${ev.oid ?? "—"}`) : null);
}

/** Pagos de funding seguidos -> una sola línea con el número de pagos y el total (el detalle sigue en «técnico»). */
function agruparFunding(eventos) {
  const out = [];
  for (const ev of eventos) {
    const prev = out[out.length - 1];
    if (ev.tipo === "funding" && prev?.tipo === "funding_grupo") {
      prev.n++;
      prev.usd += Number(ev.usd) || 0;
    } else if (ev.tipo === "funding") {
      out.push({tipo: "funding_grupo", ts: ev.ts, n: 1, usd: Number(ev.usd) || 0});
    } else out.push(ev);
  }
  return out.map((ev) => ev.tipo === "funding_grupo"
    ? h("li", {}, h("div", {}, h("strong", {}, `Funding atribuido: ${ev.n} pago${ev.n > 1 ? "s" : ""}`)),
      h("div", {clase: "tenue"}, `total ${usd(ev.usd, 4)} (positivo = cobrado)`), h("div", {clase: "cuando"}, `registrado ${fecha(iso(ev.ts))}`))
    : lineaEvento(ev));
}

// ---------------------------------------------------------------- gráfico de precio de la moneda
// Velas de 1 h / 4 h ya cerradas que el bot archiva (sin peticiones al exchange) más el último precio de marca.
const PERIODOS_PRECIO = {
  "Operación": null, "1D": ["1h", 86400, "en 24 h"], "1S": ["1h", 7 * 86400, "en 7 días"], "1M": ["4h", 30 * 86400, "en 30 días"],
};
const SEG_IV = {"1h": 3600, "4h": 14400};

function ventanaOperacion(op, ahora) {
  const t0 = iso(op.abierta_ts) ?? ahora;
  const t1 = iso(op.cerrada_ts) ?? ahora;
  const desde = t0 - Math.max(12 * 3600, (t1 - t0) * 0.3);
  return [t1 - desde > 12 * 86400 ? "4h" : "1h", desde, t1 + (op.cerrada_ts ? 6 * 3600 : 0)];
}

function puntosPrecio(d, hasta) {
  const seg = SEG_IV[d.iv];
  const puntos = d.velas.map(([t, , , , c]) => [Math.min(t + seg, hasta), c]);
  const m = d.marca;
  if (m && hay(m.px) && hay(m.ts) && m.ts <= hasta + 60 && (!puntos.length || m.ts > puntos[puntos.length - 1][0])) puntos.push([m.ts, Number(m.px)]);
  return puntos;
}

function piePrecio(v0, vi, t, texto) {
  const rel = v0 ? (vi - v0) / v0 * 100 : null;
  return [h("span", {clase: ["num", vi > v0 ? "sube" : vi < v0 ? "baja" : null]}, `${vi > v0 ? "▲ " : vi < v0 ? "▼ " : ""}${conSigno(rel, 2, " %")}`),
    h("span", {clase: "tenue"}, texto ?? fecha(t))];
}

function graficoPrecio(op) {
  let periodo = "Operación";
  const zona = h("div", {}, h("p", {clase: "cargando"}, "Cargando precio…"));
  const caja = h("section", {clase: "seccion portada", "aria-label": `Precio de ${op.moneda}`}, zona);

  async function pintar() {
    const ahora = Date.now() / 1000;
    const [iv, desde, hasta] = periodo === "Operación" ? ventanaOperacion(op, ahora)
      : [PERIODOS_PRECIO[periodo][0], ahora - PERIODOS_PRECIO[periodo][1], ahora];
    let d;
    try {
      d = await obtener(`/api/velas?${new URLSearchParams({moneda: op.moneda, iv, desde: Math.floor(desde), hasta: Math.ceil(hasta)})}`);
    } catch (e) {
      reemplazar(zona, errorCarga(`No se pudo leer el precio: ${e.message}`));
      return;
    }
    const abierta = !op.cerrada_ts;
    const puntos = puntosPrecio(d, abierta ? Infinity : hasta);
    const entrada = Number(op.precio_medio_entrada), salida = Number(op.precio_medio_salida);
    const ultimo = puntos.length ? puntos[puntos.length - 1] : null;
    const actual = abierta ? ultimo?.[1] : (hay(op.precio_medio_salida) ? salida : ultimo?.[1]);
    const cifra = h("div", {clase: "cifra"}, hay(actual) ? `${precio(actual)} $` : "—");
    // Frente a la entrada, en el sentido de la posición: en un corto, que el precio baje es a favor.
    let frente = null;
    if (hay(actual) && Number.isFinite(entrada) && entrada > 0) {
      const mov = (actual - entrada) / entrada * 100;
      const aFavor = op.lado === "S" ? mov < 0 : mov > 0;
      frente = `${conSigno(mov, 2, " %")} desde la entrada (${Math.abs(mov) < 0.005 ? "igual" : aFavor ? "a favor" : "en contra"} del ${lado(op.lado)})`;
    }
    const linea = h("div", {clase: "variacion", "aria-live": "off"},
      puntos.length >= 2 ? piePrecio(puntos[0][1], puntos[puntos.length - 1][1], null, periodo === "Operación" ? "desde poco antes de abrir" : PERIODOS_PRECIO[periodo][2])
        : h("span", {clase: "tenue"}, "—"));
    const niveles = [];
    if (Number.isFinite(entrada) && entrada > 0) niveles.push({v: entrada, clase: "entrada", texto: `Entrada ${precio(entrada)}`});
    if (abierta && hay(op.stop_actual)) niveles.push({v: Number(op.stop_actual), clase: "stop", texto: `Stop ${precio(op.stop_actual)}`});
    if (abierta) {
      const objs = objetivosVivos((bot().posiciones || []).find((p) => p.trade_id === op.trade_id));
      if (objs.length) objs.forEach((o) => niveles.push({v: o.v, clase: "objetivo", texto: `${o.nombre} ${precio(o.v)}`}));
      else if (hay(op.tp_inicial)) niveles.push({v: Number(op.tp_inicial), clase: "objetivo", texto: `Objetivo ${precio(op.tp_inicial)}`});
    }
    const marcas = [];
    if (Number.isFinite(entrada) && iso(op.abierta_ts)) marcas.push({t: iso(op.abierta_ts), v: entrada, clase: "entrada", texto: `Entrada ${precio(entrada)}`});
    if (!abierta && Number.isFinite(salida) && iso(op.cerrada_ts)) marcas.push({t: iso(op.cerrada_ts), v: salida, clase: "salida", texto: `Salida ${precio(salida)}`});
    const periodos = h("div", {clase: "periodos", role: "group", "aria-label": "Periodo del gráfico de precio"},
      Object.keys(PERIODOS_PRECIO).map((p) => h("button", {type: "button", "aria-pressed": String(p === periodo),
        onClick: () => { periodo = p; pintar(); }}, p)));
    const m = d.marca;
    reemplazar(zona,
      h("div", {clase: "etiqueta"}, `Precio de ${op.moneda}`),
      cifra, linea,
      puntos.length >= 2
        ? graficoLinea(puntos, {cifra, linea, valor: (v) => `${precio(v)} $`, pie: (v0, vi, t) => piePrecio(v0, vi, t),
          etiqueta: `Precio de ${op.moneda} de ${precio(puntos[0][1])} a ${precio(ultimo[1])}`, niveles, marcas})
        : h("div", {clase: "grafico-vacio"}, `Aún no hay velas archivadas de ${op.moneda} para este periodo (el bot las guarda al cerrar cada vela).`),
      periodos,
      frente ? h("p", {}, frente) : null,
      h("p", {clase: "muy-tenue"}, `Velas de ${d.iv} ya cerradas${abierta && m?.ts ? ` + precio de marca de ${fecha(m.ts)}` : ""}. `
        + "La línea es el cierre de cada vela: los máximos y mínimos dentro de ella no se ven."));
  }
  pintar();
  return caja;
}

// Objetivos que tiene ahora una posición: si hay primer objetivo pendiente (salida parcial) y final, se listan los dos.
function objetivosVivos(p) {
  if (!p) return [];
  const r = [];
  if (hay(p.tp1)) r.push({nombre: p.tp1_hecho ? "Objetivo 1 (parcial, cumplido)" : "Objetivo 1 (parcial)", v: Number(p.tp1)});
  if (hay(p.tpf)) r.push({nombre: r.length ? "Objetivo 2 (final)" : "Objetivo", v: Number(p.tpf)});
  return r;
}

// ---------------------------------------------------------------- ajustar el stop y el objetivo de ESTA operación
// Cada operación abierta tiene los suyos. Solo simulado y solo desde este equipo; el bot lo vuelve a validar (el stop no
// puede quedar más lejos que el inicial ni al otro lado del precio; el objetivo, del lado de la ganancia) y lo confirma él.
function ajusteOperacion(op) {
  const viva = (lista) => (lista || []).find((p) => p.trade_id === op.trade_id);
  const p0 = viva(bot().posiciones);
  if (!p0) return null;                                  // cerrada, o el bot aún no ha escrito su foto
  const sinAjuste = SOLO_LECTURA || bot().modo !== "simulado" || null;
  const campo = (nombre, valor) => h("input", {type: "number", step: "any", min: "0", inputmode: "decimal", autocomplete: "off",
    "aria-label": nombre, placeholder: nombre, valor: hay(valor) ? valor : ""});
  const inStop = campo("Stop", p0.sl);
  const inTp = campo("Objetivo (TP)", p0.tpf);
  const resumen = h("div", {});
  const mensaje = h("p", {clase: "muy-tenue", "aria-live": "polite"});
  function pintarResumen(p) {
    reemplazar(resumen, listaDef([
      [`${lado(p.lado)} desde`, `${precio(p.entrada)} · ahora ${precio(p.precio_mark)}`],
      ["Stop actual", `${precio(p.sl)}  (el inicial era ${precio(p.sl_inicial)}: no puede quedar más lejos)`],
      ...objetivosVivos(p).map((o) => [o.nombre, precio(o.v)]),
      ...(objetivosVivos(p).length ? [] : [["Objetivo actual", "ninguno"]]),
    ]));
  }
  pintarResumen(p0);
  async function mandar(cuerpo, boton) {
    boton.disabled = true;
    mensaje.textContent = "Enviado al bot; esperando su confirmación…";
    const r = await enviar("/api/comando", cuerpo);
    if (!r.ok) {
      mensaje.textContent = `No se pudo: ${r.error || "error"}`;
    } else {
      const res = await esperarResultado(r.id);
      mensaje.textContent = res.pendiente ? res.mensaje : `${res.ok ? "Hecho" : "El bot respondió"}: ${res.mensaje || ""}`;
    }
    boton.disabled = false;
    try {
      const p = viva((await obtener("/api/datos")).bot?.posiciones);
      if (p) pintarResumen(p);
    } catch (e) { /* se queda lo anterior */ }
  }
  const pedir = (cmd, entrada) => (e) => {
    const texto = entrada ? entrada.value.trim() : "";
    if (entrada && !texto) { mensaje.textContent = "Escribe el precio."; return; }
    mandar({cmd, moneda: op.moneda, precio: texto ? Number(texto) : null}, e.currentTarget);
  };
  return seccion("Ajustar esta operación",
    h("p", {clase: "tenue"}, "Solo en simulado. Aplica a esta operación y a ninguna otra. El bot lo comprueba y confirma."),
    resumen,
    h("div", {clase: "acciones"}, inStop, h("button", {type: "button", disabled: sinAjuste, onClick: pedir("/stopmanual", inStop)}, "Mover stop")),
    h("div", {clase: "acciones"}, inTp, h("button", {type: "button", disabled: sinAjuste, onClick: pedir("/tpmanual", inTp)}, "Poner objetivo"),
      h("button", {type: "button", disabled: sinAjuste, onClick: pedir("/tpmanual", null)}, "Quitar objetivo")),
    bot().modo !== "simulado" ? h("p", {clase: "aviso"}, "Los ajustes manuales solo existen en modo simulado.") : null,
    SOLO_LECTURA ? h("p", {clase: "muy-tenue"}, "Panel en solo lectura desde fuera de este equipo.") : null,
    mensaje);
}

// ---------------------------------------------------------------- qué cabe esperar de esta operación
// Idea de la «Time Machine» de day-trader-skill, pero con lo que ya mide el laboratorio (años de velas, costes, fuera de
// muestra) en vez de 60 días remuestreados. Describe el pasado de la ESTRATEGIA; no predice esta operación.
const LECTURA = {
  a_favor: ["Inclina a favor", "ok", "El intervalo del R medio queda por encima de 0."],
  en_contra: ["Inclina en contra", "mal", "El intervalo del R medio queda por debajo de 0."],
  azar: ["Moneda al aire", "aviso", "El intervalo del R medio incluye el 0: el laboratorio no distingue esta estrategia del azar."],
  muestra_pequena: ["Muestra pequeña", "aviso", "Menos de 30 operaciones fuera de muestra: no se puede leer nada."],
  sin_datos: ["Sin datos", null, "El laboratorio no tiene operaciones fuera de muestra de esta estrategia."],
};
const NOMBRE_SALIDA = {stop: "Stop inicial", protegido: "Stop movido (sin pérdidas o dinámico)", objetivo: "Objetivo final",
  tiempo: "Tiempo máximo", otra: "Otra salida"};

function rango(ic, sufijo = "") {
  return ic && hay(ic.inferior) ? `${conSigno(ic.inferior, 2)}${sufijo} a ${conSigno(ic.superior, 2)}${sufijo}` : "—";
}

function fichaEsperable(op) {
  const caja = seccion("Qué cabe esperar (según el laboratorio)", h("p", {clase: "cargando"}, "Cargando…"));
  if (!op.estrategia) return null;
  (async () => {
    let d;
    try {
      d = await obtener(`/api/estrategia?clave=${encodeURIComponent(op.estrategia)}`);
    } catch (e) {
      caja.replaceChildren(h("h2", {}, "Qué cabe esperar (según el laboratorio)"),
        vacio(e.estado === 404 ? "El laboratorio no tiene datos de esta estrategia." : `No se pudo leer: ${e.message}`));
      return;
    }
    const lab = d.laboratorio || {};
    const p = lab.probabilidades;
    const oos = lab.fuera_de_muestra || lab.validacion || {};
    // Hasta el primer laboratorio con la ficha (22/11/2026) se usa lo que ya hay: n, % de ganadoras y R medio.
    const n = p?.n ?? oos.n;
    let lectura = p?.lectura;
    const icR = p?.r_ic || lab.veredicto?.ic_bootstrap;
    if (!lectura) lectura = !n ? "sin_datos" : n < 30 || !icR ? "muestra_pequena"
      : icR.inferior > 0 ? "a_favor" : icR.superior < 0 ? "en_contra" : "azar";
    const [texto, clase, explica] = LECTURA[lectura] || LECTURA.sin_datos;
    const vivo = [d.aprendizaje?.real, d.aprendizaje?.sombra].filter((x) => x && x.n);
    const nVivo = vivo.reduce((s, x) => s + x.n, 0);
    const mediaVivo = nVivo ? vivo.reduce((s, x) => s + x.media * x.n, 0) / nVivo : null;
    const hijos = [
      h("p", {}, chip(texto, clase), ` ${explica}`),
      listaDef([
        ["Operaciones fuera de muestra", hay(n) ? String(n) : null],
        ["Ganadoras", hay(p?.ganadoras_pct ?? oos.ganan_pct)
          ? `${num(p?.ganadoras_pct ?? oos.ganan_pct, 1)} %${p?.ganadoras_ic ? ` (95 %: ${num(p.ganadoras_ic.inferior, 1)}–${num(p.ganadoras_ic.superior, 1)} %)` : ""}` : null],
        ["R medio por operación", hay(p?.r_medio ?? oos.r_medio)
          ? `${conSigno(p?.r_medio ?? oos.r_medio, 3)} R (intervalo ${p?.r_ic ? "95" : "90"} %: ${rango(icR, " R")})` : null],
        ["En vivo (simulado y sombra)", nVivo ? `${nVivo} operaciones, ${conSigno(mediaVivo, 3)} R de media` : "aún sin operaciones cerradas"],
      ]),
    ];
    if (p?.salidas) {
      hijos.push(tabla([
        {t: "Cómo terminaron", v: (x) => NOMBRE_SALIDA[x[0]] || x[0]},
        {t: "Veces", v: (x) => `${x[1].n} (${num(x[1].pct, 1)} %)`, der: true},
        {t: "R medio", v: (x) => hay(x[1].r_medio) ? conSigno(x[1].r_medio, 2) : "—", der: true},
      ], Object.entries(p.salidas).filter(([, v]) => v.n)));
    } else {
      hijos.push(h("p", {clase: "muy-tenue"}, "El reparto por tipo de salida (stop, objetivo, tiempo) aparece tras el próximo laboratorio semanal."));
    }
    hijos.push(h("p", {clase: "muy-tenue"}, "Describe el pasado de la estrategia, con costes y sin elegir a posteriori. "
      + "No es una predicción de esta operación."));
    caja.replaceChildren(h("h2", {}, "Qué cabe esperar (según el laboratorio)"), ...hijos);
  })();
  return caja;
}

// ---------------------------------------------------------------- la operación en números
const apal = (v) => (hay(v) ? `${num(v, Number(v) % 1 ? 1 : 0)}×` : "—");

/** Un dato con su etiqueta (y nota opcional debajo). */
function dato(etiqueta, valor, nota) {
  return h("div", {clase: "op-dato"}, h("span", {clase: "etq"}, etiqueta), h("b", {}, valor), nota ? h("span", {clase: "muy-tenue"}, nota) : null);
}

/** Cantidad, precios, importe, apalancamiento, margen, riesgo, stop, objetivo, liquidación, costes y duración.
 *  Datos: registro (fills y plan aprobado) y, si sigue abierta, la foto de la cuenta. Lo que no hay sale «—». */
function numerosOperacion(op, p) {
  const plan = op.decision?.plan || {};
  const moneda = op.moneda || "";
  const tam = hay(p?.tam) ? p.tam : op.tam_entrada;
  const pe = Number(op.precio_medio_entrada);
  const importe = hay(op.precio_medio_entrada) && hay(op.tam_entrada) ? pe * Number(op.tam_entrada) : null;
  const ap = hay(p?.apalancamiento) ? p.apalancamiento : plan.apalancamiento;
  const margen = hay(p?.margen) ? p.margen : (hay(importe) && hay(ap) && ap > 0 ? importe / ap : null);
  const amp = op.ampliacion || p?.ampliacion || null;
  const fa = op.fills_ampliacion || [];
  const tamAmp = amp?.tam ?? (fa.length ? fa.reduce((a, f) => a + Number(f.sz || 0), 0) : null);
  const corta = op.lado === "S";
  const ahora = estado.datos?.ahora || Date.now() / 1000;
  const ini = iso(op.abierta_ts) ?? op.abierta_ts, fin = iso(op.cerrada_ts) ?? op.cerrada_ts;
  const decide = NOMBRE_VIA[op.via] || "—";
  const cer = op.decision?.cerebro || {};
  const prediccion = hay(cer.prediccion) ? `${conSigno(cer.prediccion, 2)} R esperados`
    : cer.abstencion ? "se abstuvo" : "sin predicción";
  const datos = [
    dato("Cantidad", hay(tam) ? `${num(tam, 4)} ${moneda}` : "—",
      hay(tamAmp) && tamAmp > 0 ? `${num(Number(op.tam_entrada || tam) - tamAmp, 4)} al abrir + ${num(tamAmp, 4)} ampliadas` : (corta ? "vendidas en corto" : "compradas")),
    dato("Precio de la señal", precio(op.precio_referencia), "cuando la estrategia avisó"),
    dato("Precio de entrada", precio(op.precio_medio_entrada),
      hay(op.deslizamiento_entrada_pct) ? `medio ejecutado · ${num(Math.abs(op.deslizamiento_entrada_pct), 3)} % ${op.deslizamiento_entrada_pct > 0 ? "peor" : "mejor"} que la señal` : "medio ejecutado"),
    dato(corta ? "Importe vendido" : "Importe comprado", usd(importe), "cantidad × precio de entrada"),
    dato("Apalancamiento", apal(ap), hay(margen) ? `margen ${usd(margen)}${hay(p?.margen) ? "" : " (estimado)"}` : null),
    dato("Riesgo al abrir", usd(op.riesgo_inicial_usd ?? plan.riesgo_usd), hay(plan.sl_pct) ? `stop a ${pct(plan.sl_pct, 2)} de la entrada` : "lo que se pierde si salta el stop"),
    dato("Stop", `${precio(op.stop_inicial)}${hay(op.stop_actual) && op.stop_actual !== op.stop_inicial ? ` → ${precio(op.stop_actual)}` : ""}`, "inicial → actual"),
    dato("Objetivo", precio(hay(p?.tpf) ? p.tpf : op.tp_inicial), hay(p?.tp1) ? `objetivo 1 en ${precio(p.tp1)}${p.tp1_hecho ? " (cobrado)" : ""}` : null),
  ];
  if (p) {
    datos.push(dato("Valor ahora", usd(p.notional), `precio ${precio(p.precio_mark)}`),
      dato("Resultado abierto", resultado(p.pnl_no_realizado)),
      dato("Liquidación", precio(p.liquidacion), p.liquidacion_estimada ? "estimada (simulado)" : "según el exchange"));
  } else {
    datos.push(dato("Precio de salida", precio(op.precio_medio_salida), op.causa_salida || null));
  }
  datos.push(dato("Comisiones", usd(op.comisiones, 4)), dato("Funding", usd(op.funding_total, 4), "positivo = cobrado"),
    dato("Duración", hay(ini) ? duracion((hay(fin) ? fin : ahora) - ini) : "—", fin ? "abierta → cerrada" : "abierta desde hace"),
    dato("Quién decidió", decide),
    dato("Predicción del cerebro", prediccion, cer.hash_modelo ? `modelo ${String(cer.hash_modelo).slice(0, 8)}` : null));
  if (amp) {
    datos.push(dato("Ampliación", `+${num(amp.tam, 4)} a ${precio(amp.precio)}`,
      hay(amp.pnl_ampliacion) ? `aportó ${conSigno(amp.pnl_ampliacion, 2, " $")} · sin ella ${conSigno(amp.pnl_sin_ampliacion, 2, " $")} (estimado)`
        : "con el stop ya en la entrada"));
  }
  return seccion("La operación en números", h("div", {clase: "op-numeros"}, datos));
}

// ---------------------------------------------------------------- resultado por vía de decisión
const NOMBRE_VIA = {
  cerebro: "cerebro (modelo aprobado)", cerebro_exploracion: "cerebro en exploración",
  exploracion_amplia: "exploración amplia (riesgo reducido)", cartera_funding: "cartera de funding",
  memoria: "sin cerebro (memoria)",
};

function pestanaVias() {
  const zona = h("div", {}, h("p", {clase: "cargando"}, "Cargando resultado por vía…"));
  (async () => {
    let d;
    try { d = await obtener("/api/vias"); } catch (e) { reemplazar(zona, errorCarga(e.message)); return; }
    const t = d.total || {};
    const cols = [
      {t: "Vía / estrategia", v: (x) => x.sub ? h("span", {clase: "tenue"}, `· ${x.estrategia}`) : h("strong", {}, x.nombre)},
      {t: "Cerradas", v: (x) => String(x.n ?? 0) + (x.desconocidas ? ` (+${x.desconocidas} sin resultado)` : ""), der: true},
      {t: "Neto", v: (x) => resultado(x.pnl), der: true},
      {t: "R medio", v: (x) => hay(x.r_medio) ? conSigno(x.r_medio, 2) : "—", der: true},
      {t: "t", v: (x) => hay(x.t) ? num(x.t, 2) : "—", der: true},
      {t: "Ganan", v: (x) => hay(x.ganan_pct) ? `${num(x.ganan_pct, 0)} %` : "—", der: true},
    ];
    const filas = [];
    for (const v of d.vias || []) {
      filas.push(v);
      for (const e of v.estrategias || []) filas.push({...e, sub: true});
    }
    reemplazar(zona,
      h("div", {clase: "encabezado"}, h("h2", {}, "Resultado por vía de decisión")),
      h("p", {clase: "muy-tenue"},
        "Cada operación entra por un camino distinto: el cerebro con un modelo aprobado, el cerebro en exploración "
        + "(decide aunque su modelo aún no supere el laboratorio), la exploración amplia (lo que el cerebro NO quería, a "
        + "riesgo pequeño), la cartera de funding o, sin cerebro, la memoria. Son evidencias distintas: no se suman para "
        + `juzgar si algo funciona. ${d.desde ? `Desde la puesta a cero del ${fecha(d.desde)}. ` : ""}`
        + "Con menos de 30 cerradas por grupo nada es concluyente; t mide si el R medio se aleja de 0 (≥ 2 empieza a contar)."),
      h("div", {clase: "kpis-ops"},
        kpi("Cerradas", String(t.n ?? 0), t.desconocidas ? `${t.desconocidas} sin resultado conocido` : null),
        kpi("Neto total", resultado(t.pnl), hay(t.r_medio) ? `${conSigno(t.r_medio, 2)} R de media` : null),
        kpi("t del total", hay(t.t) ? num(t.t, 2) : "—", "todas las vías juntas")),
      seccion("Por vía y estrategia", tabla(cols, filas, {vacioTexto: "Aún no hay operaciones cerradas."})));
  })();
  return zona;
}

// ---------------------------------------------------------------- ampliar ganadoras (prueba en simulado)
function pestanaAmpliaciones() {
  const zona = h("div", {}, h("p", {clase: "cargando"}, "Cargando ampliaciones…"));
  (async () => {
    let d;
    try { d = await obtener("/api/ampliaciones"); } catch (e) { reemplazar(zona, errorCarga(e.message)); return; }
    const cfg = d.config || {};
    const explica = h("p", {clase: "muy-tenue"},
      `Prueba en simulado: cuando una operación ya tiene el stop en la entrada (la parte original ya no puede perder), el bot `
      + `le añade una vez el ${num((cfg.fraccion ?? 0.5) * 100, 0)} % de su tamaño inicial, arriesgando como mucho lo que arriesgó al abrir. `
      + `Al cerrar se calcula qué aportó esa parte. Con menos de 30 cerradas nada es concluyente.`);
    const diff = hay(d.pnl_con) && hay(d.pnl_sin) ? d.pnl_con - d.pnl_sin : null;
    reemplazar(zona,
      h("div", {clase: "encabezado"}, h("h2", {}, "Ampliar ganadoras"),
        d.activa ? chip("activa en simulado", "ok") : chip("apagada", null)),
      explica,
      h("div", {clase: "kpis-ops"},
        kpi("Ampliadas y cerradas", String(d.n ?? 0), `${d.ayudo ?? 0} en las que ayudó`),
        kpi("Resultado CON ampliar", resultado(d.pnl_con), hay(d.r_con_medio) ? `${conSigno(d.r_con_medio, 2)} R de media` : null),
        kpi("Resultado SIN ampliar", resultado(d.pnl_sin), hay(d.r_sin_medio) ? `${conSigno(d.r_sin_medio, 2)} R de media` : "estimado"),
        kpi("Diferencia", resultado(diff), diff === null ? "sin datos todavía" : diff >= 0 ? "ampliar va ganando" : "ampliar va perdiendo")),
      (d.abiertas || []).length ? seccion("Ampliadas y aún abiertas", tabla([
        {t: "Moneda", v: (x) => h("a", {href: `#/operacion/${encodeURIComponent(x.trade_id)}`}, h("strong", {}, x.moneda || "—"))},
        {t: "Lado", v: (x) => lado(x.lado)}, {t: "Estrategia", v: (x) => x.estrategia || "—"},
        {t: "Añadido", v: (x) => `+${num(x.tam, 4)} a ${precio(x.precio)}`, der: true},
        {t: "Riesgo añadido", v: (x) => usd(x.riesgo_usd), der: true},
      ], d.abiertas)) : null,
      seccion("Cerradas", tabla([
        {t: "Cierre", v: (x) => fecha(x.cerrada_ts)},
        {t: "Moneda", v: (x) => h("a", {href: `#/operacion/${encodeURIComponent(x.trade_id)}`}, h("strong", {}, x.moneda || "—"))},
        {t: "Estrategia", v: (x) => x.estrategia || "—"},
        {t: "Con ampliar", v: (x) => resultado(x.pnl_con), der: true},
        {t: "Sin ampliar", v: (x) => resultado(x.pnl_sin), der: true},
        {t: "Aportó", v: (x) => resultado(x.pnl_ampliacion), der: true},
        {t: "R con / sin", v: (x) => `${conSigno(x.r_con, 2)} / ${conSigno(x.r_sin, 2)}`, der: true},
      ], d.cerradas, {vacioTexto: "Aún no se ha cerrado ninguna operación ampliada."})));
  })();
  return zona;
}

// ---------------------------------------------------------------- nota de proceso (cómo se hizo, no cuánto ganó)
const NIVEL_PROCESO = {fallo: ["fallo", "mal"], aviso: ["a vigilar", "aviso"], info: ["bien", "ok"]};
const TIPO_NOTA = {A: "ok", B: "ok", C: "aviso", D: "mal"};

/** Ficha: nota de proceso de la operación (revision_proceso.py). Separada del resultado a propósito. */
function fichaProceso(pr) {
  if (!pr) return null;
  const m = pr.medidas || {};
  return seccion("Cómo se hizo (nota de proceso)",
    h("p", {}, chip(`nota ${pr.nota} · ${pr.puntos}/100`, TIPO_NOTA[pr.nota] || null),
      pr.provisional ? " provisional: sigue abierta" : (pr.cuadrante ? ` ${pr.cuadrante}` : "")),
    h("p", {clase: "muy-tenue"}, "Mide la ejecución, no si ganó: stop puesto y verificado, deslizamientos, riesgo real, costes e incidencias. "
      + "Una operación perdedora con buen proceso no es un error del bot."),
    h("div", {clase: "op-numeros"},
      dato("Sin stop tras entrar", hay(m.segundos_sin_stop) ? `${num(m.segundos_sin_stop, 1)} s` : "—"),
      dato("Deslizamiento de entrada", hay(m.deslizamiento_entrada_pb) ? `${num(m.deslizamiento_entrada_pb, 1)} pb` : "—", `entrada ${m.entrada || "—"} · positivo = peor`),
      dato("Deslizamiento del stop", hay(m.deslizamiento_stop_pb) ? `${num(m.deslizamiento_stop_pb, 1)} pb` : "—", "frente a su precio de activación"),
      dato("Riesgo real / plan", hay(m.riesgo_real_sobre_plan) ? `${num(m.riesgo_real_sobre_plan * 100, 0)} %` : "—"),
      dato("Costes en R", hay(m.costes_r) ? conSigno(m.costes_r, 3) : "—", "comisiones − funding")),
    h("ul", {clase: "atencion"}, (pr.comprobaciones || []).map((c) =>
      h("li", {}, chip((NIVEL_PROCESO[c.nivel] || [c.nivel])[0], (NIVEL_PROCESO[c.nivel] || [])[1] || null), " ", c.texto))));
}

/** Ficha: lo que opinó el escéptico al abrirse (no decide nada). */
function fichaEsceptico(e) {
  const ia = e?.ia;
  if (!ia || ia.estado !== "ok") return null;
  const tipo = {a_favor: "ok", en_contra: "mal"}[ia.veredicto] || null;
  return seccion("Qué dijo el escéptico al abrir",
    h("p", {}, chip(ia.veredicto.replace("_", " "), tipo), ia.confianza ? ` confianza ${ia.confianza} · ` : " ", ia.objecion || ""),
    h("p", {clase: "muy-tenue"}, "Opinión de una IA con los datos del momento de entrar. No decide nada: se mide en Objetivo → Escéptico."));
}

/** Pestaña: resumen de la nota de proceso de las cerradas (total y últimos 7 días). */
function pestanaProceso() {
  const zona = h("div", {}, h("p", {clase: "cargando"}, "Cargando nota de proceso…"));
  (async () => {
    let d;
    try { d = await obtener("/api/proceso"); } catch (e) { reemplazar(zona, errorCarga(e.message)); return; }
    const bloque = (titulo, r) => {
      const pn = r.por_nota || {};
      const cal = r.calibracion_entrada || {};
      return [seccion(titulo,
        h("div", {clase: "kpis-ops"},
          kpi("Revisadas", String(r.n ?? 0), `A ${pn.A ?? 0} · B ${pn.B ?? 0} · C ${pn.C ?? 0} · D ${pn.D ?? 0}`),
          kpi("Deslizamiento de entrada", hay(r.deslizamiento_entrada_pb_medio) ? `${num(r.deslizamiento_entrada_pb_medio, 1)} pb` : "—",
            ["creadora", "tomadora"].filter((k) => cal[k]).map((k) => `${k} ${num(cal[k].deslizamiento_medio_pb, 1)} pb (${cal[k].n})`).join(" · ") || "positivo = peor"),
          kpi("Deslizamiento del stop", hay(r.deslizamiento_stop_pb_medio) ? `${num(r.deslizamiento_stop_pb_medio, 1)} pb` : "—", "media en salidas por stop"),
          kpi("Costes", hay(r.costes_r_medio) ? `${conSigno(r.costes_r_medio, 3)} R` : "—", hay(r.segundos_sin_stop_mediana) ? `stop puesto en ${num(r.segundos_sin_stop_mediana, 1)} s (mediana)` : null)),
        Object.keys(r.cuadrantes || {}).length ? listaDef(Object.entries(r.cuadrantes).map(([k, v]) => [k, String(v)])) : null,
        Object.keys(r.problemas || {}).length ? listaDef(Object.entries(r.problemas).map(([k, v]) => [k.replaceAll("_", " "), `${v} vez/veces`])) : null)];
    };
    const peores = (d.total || {}).peores || [];
    reemplazar(zona,
      h("div", {clase: "encabezado"}, h("h2", {}, "Nota de proceso")),
      h("p", {clase: "muy-tenue"}, "Puntúa CÓMO se hizo cada operación, no si ganó (idea del revisor de HyperGrok). "
        + "Lo calcula código con el registro: stop puesto y verificado, deslizamientos, riesgo real frente al plan, costes e incidencias. "
        + "Sirve para encontrar fallos de ejecución y para calibrar la simulación. No decide nada. "
        + (d.desde ? `Desde la puesta a cero del ${fecha(d.desde)}. ` : "") + ((d.total || {}).nota_aviso || "")),
      bloque("Últimos 7 días", d.semana || {}), bloque("Total", d.total || {}),
      seccion("Las de peor proceso", tabla([
        {t: "Moneda", v: (x) => h("a", {href: `#/operacion/${encodeURIComponent(x.trade_id)}`}, h("strong", {}, x.moneda || "—"))},
        {t: "Estrategia", v: (x) => x.estrategia || "—"},
        {t: "Nota", v: (x) => chip(`${x.nota} · ${x.puntos}`, TIPO_NOTA[x.nota] || null)},
        {t: "Resultado", v: (x) => resultado(x.pnl_neto), der: true},
        {t: "Qué falló", v: (x) => (x.problemas || []).join(" · ")},
      ], peores, {vacioTexto: "Ninguna operación con fallos de proceso."})));
  })();
  return zona;
}

export const detalle = {
  async entrar(el, id) {
    reemplazar(el, h("p", {clase: "cargando"}, "Cargando operación…"));
    let op;
    try {
      op = await obtener(`/api/operacion?id=${encodeURIComponent(id)}`);
    } catch (e) {
      reemplazar(el, h("p", {}, h("a", {href: "#/operaciones"}, "← Operaciones")), errorCarga(e.estado === 404 ? "Operación no encontrada." : e.message));
      return;
    }
    const cerrada = op.estado === "cerrada";
    const avisos = [];
    if (cerrada && op.pnl_neto == null) avisos.push("Resultado DESCONOCIDO: el registro no permite atribuir con certeza todos los fills.");
    if (op.comisiones_estimadas) avisos.push("Parte de las comisiones son estimadas, no leídas del exchange.");
    if (op.eventos_repetidos) avisos.push(`${op.eventos_repetidos} evento(s) repetido(s) en el registro (contados una sola vez).`);
    if (op.estado === "desconocido") avisos.push("Estado DESCONOCIDO: la conciliación aún no lo ha resuelto.");
    const ordenes = Object.values(op.ordenes || {});
    reemplazar(el,
      h("p", {}, h("a", {href: "#/operaciones"}, "← Operaciones")),
      h("div", {clase: "titulo-vista"}, h("div", {}, h("h1", {}, `${op.moneda || "—"} · ${lado(op.lado)}`),
        h("p", {}, estadoOp(op.estado), ` ${op.estrategia || ""} · origen ${op.origen || "—"}`))),
      avisos.map((a) => h("p", {clase: "aviso"}, a)),
      h("div", {clase: "rejilla"},
        h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "Resultado neto ", info("pnl_neto", "resultado neto")), h("div", {clase: "valor"}, cerrada ? resultado(op.pnl_neto) : h("span", {clase: "tenue"}, "sigue abierta"))),
        h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "R neto ", info("r", "R")), h("div", {clase: "valor"}, hay(op.r_neto) ? num(op.r_neto) : "—")),
        h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "Comisiones"), h("div", {clase: "valor"}, usd(op.comisiones, 4))),
        h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "Funding ", info("funding", "funding")), h("div", {clase: "valor"}, usd(op.funding_total, 4)))),
      (() => {                                                // si sigue abierta: su recorrido, igual que en «En vivo»
        const p = (bot().posiciones || []).find((x) => x.trade_id === op.trade_id);
        return [p ? h("section", {clase: "seccion"}, h("div", {clase: "viva-detalle"}, carril(p))) : null,
          numerosOperacion(op, p || null), fichaProceso(op.proceso), fichaEsceptico(op.esceptico)];
      })(),
      pestanasVista("operacion", [
        ["precio", cerrada ? "Precio" : "Precio y ajuste", () => [
          op.moneda && (hay(op.precio_medio_entrada) || op.abierta_ts) ? graficoPrecio(op) : vacio("Sin datos de precio."),
          !cerrada ? ajusteOperacion(op) : null]],
        ["esperar", "Qué cabe esperar", () => fichaEsperable(op) || vacio("Operación sin estrategia.")],
        ["detalle", "Datos", () => [seccion("Datos de la operación", listaDef([
        ["Motivo de la señal", op.motivo || "—"],
        ["Decisión", op.decision ? (op.decision.aprobada ? "aprobada" : `rechazada: ${(op.decision.motivos || []).join(" · ")}`) : "—"],
        ["Entrada media", precio(op.precio_medio_entrada)], ["Salida media", precio(op.precio_medio_salida)],
        ["Stop inicial / actual", `${precio(op.stop_inicial)} / ${precio(op.stop_actual)}`],
        ["Riesgo inicial", usd(op.riesgo_inicial_usd)], ["Deslizamiento de entrada", hay(op.deslizamiento_entrada_pct) ? `${num(op.deslizamiento_entrada_pct, 3)} %` : "—"],
        ["Causa de salida", op.causa_salida || "—"], ["Apertura", fecha(iso(op.abierta_ts) ?? op.abierta_ts)], ["Cierre", fecha(iso(op.cerrada_ts) ?? op.cerrada_ts)],
        ["Identificador", h("span", {clase: "mono"}, op.trade_id)],
      ])),
        (op.alertas || []).length ? seccion("Alertas de esta operación", h("ul", {clase: "atencion"}, op.alertas.map((a) => h("li", {clase: "aviso"}, a.mensaje || JSON.stringify(a))))) : null]],
        ["historia", "Historia y órdenes", () => [
      seccion("Qué ha pasado, en orden", (op.eventos || []).length ? h("ol", {clase: "cronologia"}, agruparFunding(op.eventos)) : vacio("Sin eventos.")),
      seccion("Órdenes", tabla([
        {t: "Rol", v: (o) => ROL[o.rol] || o.rol || "—"},
        {t: "Estado", v: (o) => (ESTADO_ORDEN[o.estado] || [o.estado || "—"])[0]},
        {t: "Tamaño", v: (o) => h("span", {clase: "mono"}, num(o.sz, 4)), der: true},
        {t: "Precio / trigger", v: (o) => h("span", {clase: "mono"}, `${precio(o.px)}${o.trigger ? ` / ${precio(o.trigger)}` : ""}`), der: true},
        {t: "cloid / oid", v: (o) => h("span", {clase: "mono"}, `${corto(o.cloid, 10)} / ${o.oid ?? "—"}`)},
      ], ordenes, {vacioTexto: "Sin órdenes (señal o descarte)."}))]],
      ], "Secciones de la operación"),
      preferencias.experto ? h("details", {clase: "plegable"}, h("summary", {}, "Datos completos (técnico)"),
        h("div", {clase: "cuerpo"}, h("pre", {clase: "json"}, JSON.stringify(op, null, 1)))) : null);
  },
};
