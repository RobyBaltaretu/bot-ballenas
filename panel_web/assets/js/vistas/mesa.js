// MESA (18/11/2026, idea de un vídeo de un panel de «equipo de agentes»): el bot visto como un equipo de ocho puestos,
// cada uno con su cifra, su barra y lo último que ha hecho en una frase; la respuesta a «¿por qué no entra nada?» con
// los motivos reales de las propuestas; y «cada número que cree el bot» con su valor actual frente al límite.
// Todo son datos del bot (panel_datos, feed y registro): esta vista no decide ni cambia nada.

import {alEvento, chispa, cifraViva} from "../anim.js";
import {obtener} from "../api.js";
import {h, reemplazar, seccion, vacio} from "../dom.js";
import {estado} from "../estado.js";
import {hace, hay, horaCorta, num, pct, usd} from "../formato.js";
import {ayuda} from "../info.js";

const TIPOS = ["senal_detectada", "decision_aprobada", "decision_rechazada", "orden_enviada", "orden_completada", "entrada", "salida",
  "cierre", "stop_movido", "proteccion", "alerta", "error", "ballena_fill", "ballena_cambio_inferido", "liquidacion_inferida"];
const CORTO = {senal_detectada: "señal", decision_aprobada: "aprobada", decision_rechazada: "descartada", orden_enviada: "orden enviada",
  orden_completada: "orden completada", entrada: "entrada", salida: "salida", cierre: "cerrada", stop_movido: "stop movido",
  proteccion: "protección", alerta: "alerta", error: "error", ballena_fill: "ballena", ballena_cambio_inferido: "ballena",
  liquidacion_inferida: "liquidación"};
const LADO = {L: "largo", S: "corto", compra: "compra", venta: "venta"};

function agenteDe(ev) {
  const t = ev.tipo;
  if (t === "senal_detectada") return "escaner";
  if (t === "decision_aprobada") return "cerebro";
  if (t === "decision_rechazada") return /cerebro/i.test(ev.detalle || "") ? "cerebro" : "riesgo";
  if (["orden_enviada", "orden_completada", "entrada", "salida", "cierre", "stop_movido"].includes(t)) return "ejecucion";
  if (["proteccion", "alerta", "error"].includes(t)) return "guardian";
  if (["ballena_fill", "ballena_cambio_inferido", "liquidacion_inferida"].includes(t)) return "ballenas";
  return null;
}

function frase(ev) {
  const lado = ev.lado ? `${LADO[ev.lado] || ev.lado} ` : "";
  const txt = (ev.detalle || CORTO[ev.tipo] || ev.tipo || "").replace(/\s+/g, " ");
  return `${ev.moneda ? `${ev.moneda} ` : ""}${lado}${ev.detalle ? "" : "· "}${txt}`.slice(0, 96);
}

const s = {raiz: null, zona: null, ultimos: {}, historia: {}, serie: {}, tSerie: 0, quitar: null, mesa: null, lab: null, vistoSeq: {}, pulsos: new Set(),
  tMesa: 0, tLab: 0, timer: null, ventana: "ultimo"};

async function cargarEventos() {
  try {
    const r = await obtener(`/api/feed?limite=120&tipo=${encodeURIComponent(TIPOS.join(","))}`);
    const evs = (r.eventos || []).slice().sort((a, b) => b.seq - a.seq);
    const nuevos = {};
    const historia = {};
    for (const ev of evs) {
      const a = agenteDe(ev);
      if (!a) continue;
      if (!nuevos[a]) nuevos[a] = ev;
      (historia[a] = historia[a] || []);
      if (historia[a].length < 5) historia[a].push(ev);
    }
    s.historia = historia;
    for (const [a, ev] of Object.entries(nuevos)) {
      if (s.vistoSeq[a] !== undefined && ev.seq !== s.vistoSeq[a]) s.pulsos.add(a);
      s.vistoSeq[a] = ev.seq;
    }
    s.ultimos = nuevos;
  } catch (e) { /* se conserva lo anterior */ }
}

async function cargarLento() {
  const ahora = Date.now();
  if (ahora - s.tMesa > 60000) {
    s.tMesa = ahora;
    try { s.mesa = await obtener("/api/mesa"); } catch (e) { /* idem */ }
  }
  if (ahora - s.tLab > 300000) {
    s.tLab = ahora;
    try { s.lab = await obtener("/api/laboratorio"); } catch (e) { /* idem */ }
  }
}

// ---------------------------------------------------------------- el equipo
/** Guarda una muestra de la cifra de cada puesto (máx. 30, una cada ≥ 8 s) para dibujar su minigráfico. */
function muestrear(lista) {
  const t = Date.now();
  if (t - s.tSerie < 8000) return;
  s.tSerie = t;
  for (const c of lista) {
    if (!hay(c.valor)) continue;
    const v = (s.serie[c.id] = s.serie[c.id] || []);
    v.push(Number(c.valor));
    if (v.length > 30) v.shift();
  }
}

function tarjetas() {
  const b = estado.datos?.bot || {};
  const ahora = estado.datos?.ahora || Date.now() / 1000;
  const r = b.efectiva?.riesgo || {};
  const pos = b.posiciones || [];
  const ra = b.limites?.riesgo_abierto || {};
  const cer = b.cerebro?.contadores || {};
  const cob = b.cobertura_ballenas || {};
  const inv = b.investigacion || {};
  const ult = s.mesa?.ultimo;
  const stopsOk = pos.filter((p) => p.stop_verificado).length;
  const cerca = pos.filter((p) => hay(p.distancia_stop_pct)).sort((x, y) => x.distancia_stop_pct - y.distancia_stop_pct)[0];
  const labTs = s.lab?.generado ? Date.parse(s.lab.generado) / 1000 : null;
  const uso = (v, max) => (hay(v) && max ? Math.max(0, Math.min(100, v / max * 100)) : null);
  const tono = (p) => (p === null ? null : p >= 95 ? "mal" : p >= 75 ? "aviso" : "ok");
  return [
    {id: "escaner", nombre: "Escáner", rol: "busca qué se mueve", acento: "azul",
      valor: ult ? ult.propuestas : 0, fmt: (n) => String(Math.round(n)),
      numero: ult ? String(ult.propuestas) : "0", unidad: ult?.propuestas === 1 ? "propuesta" : "propuestas",
      pie: ult ? `último cierre ${hace(ult.ts, ahora)}` : "sin propuestas recientes", barra: null, tono: null},
    {id: "cerebro", nombre: "Cerebro", rol: "decide qué entra", acento: "violeta",
      valor: cer.entra ?? 0, fmt: (n) => String(Math.round(n)),
      numero: String(cer.entra ?? 0), unidad: cer.entra === 1 ? "entra" : "entran",
      pie: `${cer.no_entra ?? 0} no entran · ${cer.abstiene ?? 0} se abstiene`, barra: null, tono: null},
    {id: "riesgo", nombre: "Riesgo", rol: "lo que no se negocia", acento: "ambar",
      valor: hay(ra.valor_pct) ? ra.valor_pct : null, fmt: (n) => pct(n, 1),
      numero: hay(ra.valor_pct) ? pct(ra.valor_pct, 1) : "—", unidad: `de ${hay(ra.limite_pct) ? pct(ra.limite_pct, 0) : "—"}`,
      pie: (b.bloqueos || []).length ? b.bloqueos.join(" · ").slice(0, 60) : "sin bloqueos", barra: uso(ra.valor_pct, ra.limite_pct),
      tono: (b.bloqueos || []).length ? "aviso" : tono(uso(ra.valor_pct, ra.limite_pct))},
    {id: "tamano", nombre: "Tamaño", rol: "cuánto arriesga", acento: "rosa",
      valor: hay(b.exposicion?.riesgo_abierto_usd) ? b.exposicion.riesgo_abierto_usd : null,
      numero: hay(r.riesgo_por_operacion_pct) ? pct(r.riesgo_por_operacion_pct, 1) : "—", unidad: "por operación",
      pie: `lo abierto arriesga ${usd(b.exposicion?.riesgo_abierto_usd)}`, barra: null, tono: null},
    {id: "ejecucion", nombre: "Ejecución", rol: "pone las órdenes", acento: "verde",
      valor: pos.length ? stopsOk / pos.length * 100 : null,
      numero: pos.length ? `${stopsOk}/${pos.length}` : "—", unidad: "stops confirmados",
      pie: b.conciliacion_ok === false ? "la cuenta NO cuadra" : "la cuenta cuadra con el registro",
      barra: pos.length ? stopsOk / pos.length * 100 : null, tono: b.conciliacion_ok === false ? "mal" : pos.length && stopsOk < pos.length ? "aviso" : "ok"},
    {id: "guardian", nombre: "Guardián", rol: "vigila lo abierto", acento: "naranja",
      valor: cerca ? cerca.distancia_stop_pct : null,
      numero: `${pos.length}${r.max_posiciones_abiertas ? `/${r.max_posiciones_abiertas}` : ""}`, unidad: "abiertas",
      pie: cerca ? `${cerca.moneda} a ${pct(cerca.distancia_stop_pct, 1)} de su stop` : "ninguna posición abierta",
      barra: uso(pos.length, r.max_posiciones_abiertas), tono: null},
    {id: "ballenas", nombre: "Ballenas", rol: "sigue a los grandes", acento: "cian",
      valor: hay(cob.frescas) ? cob.frescas : null,
      numero: hay(cob.frescas) ? `${cob.frescas}/${cob.elegidas ?? "?"}` : "—", unidad: "con datos frescos",
      pie: `${cob.suscritas_tiempo_real ?? 0} en tiempo real`, barra: uso(cob.frescas, cob.elegidas), tono: null},
    {id: "laboratorio", nombre: "Laboratorio", rol: "prueba y aprende", acento: "lima",
      valor: hay(inv.variantes_totales) ? inv.variantes_totales : null, fmt: (n) => num(n, 0),
      numero: hay(inv.variantes_totales) ? num(inv.variantes_totales, 0) : "—", unidad: "variantes probadas",
      pie: labTs ? `último resultado hace ${hace(labTs, ahora).replace("hace ", "")} · listón t ${num(inv.t_requerido, 1)}` : `listón t ${num(inv.t_requerido, 1)}`,
      barra: null, tono: null},
  ];
}

function equipo() {
  const lista = tarjetas();
  muestrear(lista);
  return h("div", {clase: "equipo"}, lista.map((c, k) => {
    const pulso = s.pulsos.has(c.id);
    const hist = s.historia[c.id] || [];
    const serie = s.serie[c.id] || [];
    const cifra = c.fmt && hay(c.valor) ? cifraViva(`mesa.${c.id}`, c.valor, c.fmt) : c.numero;
    return h("article", {clase: ["agente", `acento-${c.acento}`, pulso ? "pulso" : null], id: `agente-${c.id}`, estilo: {"--k": String(k)}},
      h("header", {}, h("span", {clase: "punto-agente", "aria-hidden": "true"}), h("div", {},
        h("h3", {}, c.nombre), h("p", {clase: "rol"}, c.rol)),
      c.tono ? h("span", {clase: ["etiqueta-tono", `e-${c.tono}`]}, c.tono === "ok" ? "bien" : c.tono === "aviso" ? "ojo" : "falla") : null),
      h("div", {clase: "agente-medida"},
        h("div", {clase: "agente-cifra"}, h("b", {}, cifra), h("span", {}, c.unidad)),
        serie.length > 2 ? h("div", {clase: "agente-chispa", title: "últimas muestras de esta cifra"}, chispa(serie, {ancho: 120, alto: 36})) : null),
      c.barra !== null ? h("div", {clase: ["barra-agente", c.tono ? `e-${c.tono}` : null]}, h("span", {estilo: {width: `${c.barra}%`}})) : h("div", {clase: "barra-agente vacia"}),
      h("p", {clase: "pie-agente"}, c.pie),
      h("div", {clase: "bitacora"}, h("span", {clase: "bitacora-titulo"}, "Bitácora"),
        hist.length ? h("ol", {}, hist.map((ev, i) => h("li", {clase: i === 0 ? "nuevo" : null, title: frase(ev)},
          h("span", {clase: "hora"}, horaCorta(ev.ts_recepcion || ev.ts_exchange)), h("span", {clase: "txt"}, frase(ev)))))
          : h("p", {clase: "muy-tenue"}, "Sin novedades recientes.")));
  }));
}

/** Un evento nuevo del bot llega por el bus: se añade a la bitácora de su puesto y la tarjeta se ilumina al instante. */
function alLlegar(ev) {
  const a = agenteDe(ev);
  if (!a || !s.zona?.isConnected) return;
  const lista = (s.historia[a] = s.historia[a] || []);
  if (!lista.some((x) => x.seq === ev.seq)) lista.unshift(ev);
  s.historia[a] = lista.slice(0, 5);
  s.ultimos[a] = lista[0];
  s.vistoSeq[a] = Math.max(s.vistoSeq[a] || 0, ev.seq);
  pintar();
  const tarjeta = s.zona.querySelector(`#agente-${a}`);
  if (tarjeta) {
    tarjeta.classList.add("pulso");
    setTimeout(() => tarjeta.classList.remove("pulso"), 1800);
  }
}

// ---------------------------------------------------------------- ¿por qué no entra nada?
function porQue() {
  const m = s.mesa;
  const ayudaTxt = ayuda("¿Por qué no entra nada?",
    "Cada estrategia propone entradas al cerrar una vela de 4 h. Aquí se cuenta qué filtro frenó cada propuesta.",
    "Una propuesta puede frenarla más de un filtro, por eso las barras pueden sumar más que el total.",
    "Las hipótesis que son solo de investigación no se cuentan: no pueden operar por diseño.");
  const cabecera = h("div", {clase: "encabezado"}, h("h2", {}, "¿Por qué no entra nada? ", ayudaTxt),
    h("div", {clase: "pestanas", role: "group", "aria-label": "Periodo"},
      [["ultimo", "Último cierre"], ["dia", "24 h"]].map(([k, t]) => h("button", {type: "button", "aria-pressed": String(s.ventana === k),
        onClick: () => { s.ventana = k; pintar(); }}, t))));
  if (!m) return h("section", {clase: "seccion"}, cabecera, h("p", {clase: "cargando"}, "Contando…"));
  const d = s.ventana === "ultimo" ? m.ultimo : m.dia;
  if (!d || !d.propuestas) {
    return h("section", {clase: "seccion"}, cabecera, vacio(s.ventana === "ultimo"
      ? "Ninguna estrategia ha propuesto nada en el último cierre."
      : "Ninguna propuesta en las últimas 24 h."));
  }
  const max = Math.max(d.propuestas, ...d.motivos.map((x) => x.n));
  const titulo = s.ventana === "ultimo" ? `Cierre de las ${horaCorta(d.ts).slice(0, 5)} (${hace(d.ts, m.ahora)}): ` : "Últimas 24 h: ";
  return h("section", {clase: "seccion"}, cabecera,
    h("div", {clase: "resumen-embudo"},
      h("span", {}, titulo), h("b", {}, `${d.propuestas} ${d.propuestas === 1 ? "propuesta" : "propuestas"}`),
      h("span", {clase: "flecha-texto", "aria-hidden": "true"}, "→"), h("b", {clase: d.entran ? "sube" : null}, `${d.entran} ${d.entran === 1 ? "entra" : "entran"}`),
      d.sin_decision ? h("span", {clase: "tenue"}, ` · ${d.sin_decision} sin decisión`) : null),
    d.motivos.length ? h("ul", {clase: "motivos"}, d.motivos.map((x) => h("li", {},
      h("span", {clase: "motivo-nombre"}, x.motivo),
      h("span", {clase: "motivo-barra"}, h("span", {estilo: {width: `${x.n / max * 100}%`}})),
      h("b", {}, String(x.n)))))
      : h("p", {clase: "tenue"}, "Todas las propuestas entraron."),
    m.solo_investigacion_24h ? h("p", {clase: "muy-tenue"}, `${m.solo_investigacion_24h} propuestas de hipótesis solo de investigación (24 h) no se cuentan.`) : null);
}

// ---------------------------------------------------------------- cada número que cree el bot
function fila(nombre, actual, limite, uso, texto) {
  const st = uso === null ? null : uso >= 100 ? "mal" : uso >= 80 ? "aviso" : "ok";
  return h("tr", {clase: st ? `e-${st}` : null},
    h("td", {clase: "nombre-umbral"}, nombre),
    h("td", {clase: "der mono"}, actual),
    h("td", {clase: "der mono tenue"}, limite),
    h("td", {clase: "barra-umbral"}, uso === null ? null : h("span", {clase: ["barra-agente", `e-${st}`]}, h("span", {estilo: {width: `${Math.min(100, uso)}%`}}))),
    h("td", {clase: "estado-umbral", title: texto || ""}, st === "mal" ? "✕" : st === "aviso" ? "!" : st === "ok" ? "✓" : "·"));
}

function numeros() {
  const b = estado.datos?.bot || {};
  const r = b.efectiva?.riesgo || {};
  const l = b.limites || {};
  const pos = b.posiciones || [];
  const largos = pos.filter((p) => p.lado === "L").length, cortos = pos.length - largos;
  const e = b.exposicion || {};
  const u = (v, m) => (hay(v) && m ? Math.abs(v) / m * 100 : null);
  const filas = [
    fila("Riesgo por operación", hay(r.riesgo_por_operacion_pct) ? pct(r.riesgo_por_operacion_pct, 1) : "—", "fijo", null),
    fila("Riesgo abierto", pct(l.riesgo_abierto?.valor_pct, 1), `máx ${pct(r.riesgo_abierto_max_pct, 0)}`, u(l.riesgo_abierto?.valor_pct, r.riesgo_abierto_max_pct)),
    fila("Posiciones abiertas", String(pos.length), `máx ${r.max_posiciones_abiertas ?? "—"}`, u(pos.length, r.max_posiciones_abiertas)),
    fila("Largos del mismo lado", String(largos), `máx ${r.max_mismo_lado ?? "—"}`, u(largos, r.max_mismo_lado)),
    fila("Cortos del mismo lado", String(cortos), `máx ${r.max_mismo_lado ?? "—"}`, u(cortos, r.max_mismo_lado)),
    fila("Operaciones hoy", String(l.operaciones_hoy?.valor ?? "—"), `máx ${l.operaciones_hoy?.limite ?? "—"}`, u(l.operaciones_hoy?.valor, l.operaciones_hoy?.limite)),
    fila("Pérdida del día", pct(l.dia?.valor_pct, 1), `corte ${pct(l.dia?.limite_pct, 0)}`, l.dia?.valor_pct < 0 ? u(l.dia.valor_pct, l.dia.limite_pct) : 0),
    fila("Pérdida de la semana", pct(l.semana?.valor_pct, 1), `corte ${pct(l.semana?.limite_pct, 0)}`, l.semana?.valor_pct < 0 ? u(l.semana.valor_pct, l.semana.limite_pct) : 0),
    fila("Caída desde el máximo", pct(l.caida?.valor_pct, 1), `corte ${pct(l.caida?.limite_pct, 0)}`, l.caida?.valor_pct < 0 ? u(l.caida.valor_pct, l.caida.limite_pct) : 0),
    fila("Exposición bruta", pct(e.bruta_pct, 0), `máx ${pct(r.exposicion_bruta_max_pct, 0)}`, u(e.bruta_pct, r.exposicion_bruta_max_pct)),
    fila("Exposición neta", pct(e.neta_pct, 0), `máx ±${pct(r.exposicion_neta_max_pct, 0)}`, u(e.neta_pct, r.exposicion_neta_max_pct)),
    fila("Exposición a BTC (con beta)", pct(b.exposicion_beta?.pct, 0), `máx ±${pct(r.exposicion_beta_btc_max_pct, 0)}`, u(b.exposicion_beta?.pct, r.exposicion_beta_btc_max_pct)),
    fila("Apalancamiento", "—", `máx ${r.apalancamiento_max ?? "—"}×`, null),
    fila("Distancia del stop", "—", `${pct(r.sl_min_pct, 2)} – ${pct(r.sl_max_pct, 0)}`, null),
    fila("Horquilla máxima", "—", pct(r.spread_max_pct, 2), null),
    fila("Correlación máxima", "—", num(r.correlacion_max, 2), null),
    fila("Liquidación al menos", "—", `${num(r.distancia_liquidacion_min_multiplo_stop, 1)}× el stop`, null),
    fila("Pausa tras pérdidas seguidas", "—", `${r.pausa_tras_perdidas_seguidas ?? "—"} seguidas → ${r.minutos_pausa_tras_racha ?? "—"} min`, null),
  ];
  return seccion(h("span", {}, "Cada número que cree el bot ", ayuda("Cada número que cree el bot",
    "Los límites con los que el bot decide, junto a su valor de ahora. ✓ dentro, ! cerca del límite (80 % o más), ✕ en el límite.",
    "Son los de la configuración vigente. Para cambiarlos usa Configuración: el panel nunca los sube por su cuenta.")),
  h("div", {clase: "tabla-envoltura"}, h("table", {clase: "umbrales"},
    h("thead", {}, h("tr", {}, h("th", {}, "Qué"), h("th", {clase: "der"}, "Ahora"), h("th", {clase: "der"}, "Límite"), h("th", {}, ""), h("th", {}, ""))),
    h("tbody", {}, filas))));
}

function pintar() {
  if (!s.zona) return;
  reemplazar(s.zona, h("section", {clase: "seccion"},
    h("div", {clase: "encabezado"}, h("h2", {}, "El equipo ", ayuda("El equipo",
      "El bot visto como ocho puestos de trabajo. Cada tarjeta muestra una cifra viva, una barra de uso y, abajo, lo último que ha hecho ese puesto.",
      "La tarjeta se ilumina un instante cuando llega una novedad nueva. Todo son datos del bot: aquí no se decide nada.")),
    h("span", {clase: "muy-tenue"}, "se actualiza solo")), equipo()),
  porQue(), numeros());
  s.pulsos.clear();
}

async function refrescar() {
  await Promise.all([cargarEventos(), cargarLento()]);
  const huboPulso = s.pulsos.size > 0;
  pintar();
  if (huboPulso) setTimeout(() => s.zona && s.zona.querySelectorAll(".agente.pulso").forEach((x) => x.classList.remove("pulso")), 1800);
}

/** Contenido de la pestaña «Mesa» (se refresca cada 12 s mientras se ve). */
export function pestanaMesa() {
  if (s.zona) return s.zona;
  s.zona = h("div", {clase: "mesa"});
  s.vistoSeq = {};
  pintar();
  refrescar();
  clearInterval(s.timer);
  s.timer = setInterval(() => { if (!document.hidden && s.zona?.isConnected) refrescar(); }, 12000);
  if (s.quitar) s.quitar();
  s.quitar = alEvento(alLlegar);
  return s.zona;
}

export function cerrarMesa() {
  clearInterval(s.timer);
  s.timer = null;
  if (s.quitar) s.quitar();
  s.quitar = null;
  s.zona = null;
}

/** El estado del bot cambia cada 10 s: se repintan las cifras sin volver a pedir nada al servidor. */
export function actualizarMesa() {
  if (s.zona?.isConnected) pintar();
}
