// ACTIVIDAD: feed persistente del bot (/api/feed) con push por SSE (/api/feed/stream). EventSource reconecta solo
// (retry 3000 y Last-Event-ID); aquí NO hay un segundo bucle de reconexión. Si SSE falla repetidamente, sondeo cada
// 5 s. Se deduplica por seq y el búfer se limita. Los datos llegan con unos segundos de retraso: no es tiempo real.

import {obtener} from "../api.js";
import {chip, h, listaDef, reemplazar, seccion, vacio} from "../dom.js";
import {preferencias} from "../estado.js";
import {fecha, hace, horaCorta, lado, num, precio} from "../formato.js";
import {abrirDialogo, info} from "../info.js";

const MAX_BUFER = 400;
const SONDEO_MS = 5000;
const BOT = new Set(["senal_detectada", "decision_aprobada", "decision_rechazada", "orden_enviada", "orden_abierta", "orden_parcial",
  "orden_completada", "orden_cancelada", "orden_rechazada", "orden_desconocida", "orden_no_confirmada", "orden_cancelacion_solicitada",
  "orden_disparada", "proteccion", "stop_movido", "entrada", "salida", "cierre", "intencion_shadow", "resultado_shadow", "alerta", "error"]);
const MERCADO = new Set(["ballena_fill", "ballena_cambio_inferido", "operacion_grande", "liquidacion_inferida"]);
const SISTEMA = new Set(["datos_obsoletos", "reconexion", "fuente_perdida", "fuente_recuperada"]);
const INFERIDOS = new Set(["ballena_cambio_inferido", "liquidacion_inferida"]);
const OBSERVADOS = new Set(["ballena_fill", "operacion_grande"]);

const s = {eventos: [], vistos: new Set(), ultimo: -1, conexion: "desconectado", es: null, sondeo: null, fallosSse: 0,
  pausado: false, pendientes: [], grupo: "bot", tipos: {}, botTs: null, raiz: null, lista: null, estadoEl: null, primeroDisponible: null,
  perdidos: false};

function ts(ev) {
  return ev.ts_exchange || ev.ts_recepcion || ev.ts_proceso || null;
}

function grupoDe(tipo) {
  return BOT.has(tipo) ? "bot" : MERCADO.has(tipo) ? "mercado" : SISTEMA.has(tipo) ? "sistema" : "otros";
}

function añadir(evs) {
  let nuevos = 0;
  for (const ev of evs) {
    if (typeof ev.seq !== "number" || s.vistos.has(ev.seq)) continue;           // deduplicación por seq
    s.vistos.add(ev.seq);
    s.ultimo = Math.max(s.ultimo, ev.seq);
    if (s.pausado) s.pendientes.push(ev); else s.eventos.unshift(ev);
    nuevos++;
  }
  if (s.eventos.length > MAX_BUFER) s.eventos.length = MAX_BUFER;
  if (s.vistos.size > MAX_BUFER * 4) s.vistos = new Set(s.eventos.map((e) => e.seq).concat(s.pendientes.map((e) => e.seq)));
  if (nuevos) pintarLista();
  pintarEstado();
}

function etiquetaOrigen(ev) {
  if (INFERIDOS.has(ev.tipo)) return chip("inferido", "aviso", {titulo: "deducido, no confirmado"});
  if (OBSERVADOS.has(ev.tipo)) return chip("observado", "info");
  if (ev.tipo === "resultado_shadow" || ev.tipo === "intencion_shadow") return chip("modelado", "aviso");
  return null;
}

// Nombre corto en la lista (la descripción completa del backend va en el detalle).
const CORTO = {senal_detectada: "señal", decision_aprobada: "decisión: aprobada", decision_rechazada: "decisión: rechazada",
  orden_enviada: "orden enviada", orden_abierta: "orden aceptada", orden_parcial: "fill parcial", orden_completada: "orden completada",
  orden_cancelada: "orden cancelada", orden_rechazada: "orden rechazada", orden_desconocida: "orden: estado desconocido",
  orden_no_confirmada: "orden no confirmada", orden_cancelacion_solicitada: "cancelación pedida", orden_disparada: "trigger activado",
  proteccion: "protección", stop_movido: "stop movido", entrada: "fill de entrada", salida: "fill de salida", cierre: "posición cerrada",
  intencion_shadow: "intención shadow", resultado_shadow: "resultado shadow", alerta: "alerta", error: "error",
  ballena_fill: "fill de ballena", ballena_cambio_inferido: "cambio de ballena", operacion_grande: "operación grande pública",
  liquidacion_inferida: "posible liquidación", datos_obsoletos: "datos obsoletos", reconexion: "reconexión",
  fuente_perdida: "fuente perdida", fuente_recuperada: "fuente recuperada"};
const LADO_FEED = {compra: "compra", venta: "venta", L: "largo", S: "corto"};

function filaEvento(ev) {
  const t = ts(ev);
  const precioRef = ev.precio_ref?.valor != null ? `${precio(ev.precio_ref.valor)} (${ev.precio_ref.tipo || "?"})` : null;
  const origen = etiquetaOrigen(ev);
  const estadoRepetido = ["observado", "inferido", "modelado"].includes(ev.estado);
  return h("li", {tabIndex: 0, onClick: () => detalleEvento(ev), onKeydown: (e) => { if (e.key === "Enter") detalleEvento(ev); }},
    h("span", {clase: "hora", title: fecha(t)}, horaCorta(t)),
    h("span", {clase: "texto"}, h("strong", {}, ev.moneda ? `${ev.moneda} ` : ""), ev.lado ? `${LADO_FEED[ev.lado] || ev.lado} · ` : "",
      CORTO[ev.tipo] || s.tipos[ev.tipo] || ev.tipo,
      precioRef ? h("span", {clase: "muy-tenue"}, ` · ${precioRef}`) : null,
      ev.detalle && BOT.has(ev.tipo) ? h("div", {clase: "tenue"}, ev.detalle) : null),
    h("span", {clase: "extra acciones"}, origen, ev.estado && !estadoRepetido ? chip(ev.estado, null, {punto: false}) : null,
      h("span", {clase: "muy-tenue"}, hace(t))));
}

function detalleEvento(ev) {
  const t = ts(ev);
  abrirDialogo(s.tipos[ev.tipo] || ev.tipo,
    listaDef([
      ["Tipo", ev.tipo], ["Moneda", ev.moneda || "—"], ["Lado", lado(ev.lado)], ["Estrategia", ev.estrategia || "—"],
      ["Detalle", ev.detalle || "—"], ["Estado", ev.estado || "—"],
      ["Hora del exchange", ev.ts_exchange ? fecha(ev.ts_exchange) : "no la trae"], ["Recibido por el bot", fecha(ev.ts_recepcion)],
      ["Frescura del dato", ev.frescura_seg != null ? `${num(ev.frescura_seg, 1)} s` : "—"], ["Fuente", ev.fuente || "—"],
      ["Tamaño", ev.tam != null ? num(ev.tam, 4) : "—"], ["Riesgo", ev.riesgo_usd != null ? `${num(ev.riesgo_usd)} $` : "—"],
      ["Origen del dato", INFERIDOS.has(ev.tipo) ? "INFERIDO (no confirmado)" : OBSERVADOS.has(ev.tipo) ? "observado" : "registro del bot"],
      ev.trade_id ? ["Operación", h("a", {href: `#/operacion/${encodeURIComponent(ev.trade_id)}`}, "ver operación")] : null,
      ["Hace", hace(t)],
    ]),
    preferencias.experto ? h("pre", {clase: "json"}, JSON.stringify(ev, null, 1)) : null);
}

function pintarEstado() {
  if (!s.estadoEl) return;
  const textos = {vivo: ["En vivo", "ok"], reconectando: ["Reconectando…", "aviso"],
    sondeo: [`Sondeo cada ${SONDEO_MS / 1000} s`, "aviso"], desconectado: ["Desconectado", "mal"]};
  const [txt, c] = textos[s.conexion];
  reemplazar(s.estadoEl, chip(txt, c), info("vivo", "actividad en vivo"),
    s.botTs ? h("span", {clase: "muy-tenue"}, ` · foto del bot ${hace(s.botTs)}`) : null,
    s.perdidos ? chip("hubo eventos que ya no están disponibles (rotación del registro)", "aviso") : null,
    h("button", {type: "button", onClick: () => { s.pausado = !s.pausado; if (!s.pausado) reanudar(); pintarEstado(); }},
      s.pausado ? `Reanudar lectura${s.pendientes.length ? ` (${s.pendientes.length} nuevos)` : ""}` : "Pausar lectura"));
}

function reanudar() {
  s.eventos.unshift(...s.pendientes.reverse());
  s.pendientes = [];
  if (s.eventos.length > MAX_BUFER) s.eventos.length = MAX_BUFER;
  pintarLista();
}

// Sin scroll infinito (18/11/2026): se ven los 25 últimos y un botón para ver más, de 25 en 25.
const POR_TANDA = 25;
let mostrar = POR_TANDA;

function pintarLista() {
  if (!s.lista) return;
  const visibles = s.eventos.filter((e) => s.grupo === "todo" || grupoDe(e.tipo) === s.grupo);
  const resto = visibles.length - mostrar;
  reemplazar(s.lista, visibles.length ? [h("ul", {clase: "feed"}, visibles.slice(0, mostrar).map(filaEvento)),
    resto > 0 ? h("div", {clase: "paginacion"}, h("button", {type: "button", onClick: () => { mostrar += POR_TANDA; pintarLista(); }},
      `Ver ${Math.min(POR_TANDA, resto)} más`), h("span", {clase: "tenue"}, `${resto} más en memoria`)) : null]
    : vacio(s.conexion === "desconectado" && !s.eventos.length ? "Sin conexión con el feed."
      : "Nada reciente de este tipo. Lo nuevo aparecerá aquí."));
}

function conectarSse() {
  if (!window.EventSource || s.fallosSse >= 3) return activarSondeo();
  cerrarSse();
  const es = new EventSource(`/api/feed/stream?desde=${Math.max(0, s.ultimo)}`);
  s.es = es;
  s.conexion = "reconectando";
  es.onopen = () => { s.conexion = "vivo"; s.fallosSse = 0; pintarEstado(); };
  es.addEventListener("evento", (m) => { try { añadir([JSON.parse(m.data)]); } catch (e) { /* línea ilegible: se ignora */ } });
  es.addEventListener("estado", (m) => { try { s.botTs = JSON.parse(m.data).bot_ts; pintarEstado(); } catch (e) { /* */ } });
  es.onerror = () => {
    // EventSource reintenta por sí mismo (CONNECTING). Si queda CERRADO o falla una y otra vez -> sondeo.
    s.fallosSse++;
    if (es.readyState === EventSource.CLOSED || s.fallosSse >= 3) { cerrarSse(); activarSondeo(); }
    else s.conexion = "reconectando";
    pintarEstado();
  };
}

function cerrarSse() {
  if (s.es) { s.es.close(); s.es = null; }
}

async function sondear() {
  try {
    const d = await obtener(`/api/feed?desde=${s.ultimo}&limite=500`);
    s.botTs = d.bot_ts;
    s.perdidos = s.perdidos || d.perdidos;
    s.conexion = s.es ? s.conexion : "sondeo";
    añadir(d.eventos || []);
    // El servidor responde otra vez: pasado un minuto en sondeo se intenta volver al push (una sola conexión).
    if (!s.es && window.EventSource && Date.now() - (s.sondeoDesde || 0) > 60000) {
      clearInterval(s.sondeo);
      s.sondeo = null;
      s.fallosSse = 0;
      conectarSse();
    }
  } catch (e) {
    s.conexion = "desconectado";
    pintarEstado();
  }
}

function activarSondeo() {
  if (s.sondeo) return;
  s.conexion = "sondeo";
  s.sondeoDesde = Date.now();
  s.sondeo = setInterval(sondear, SONDEO_MS);
  pintarEstado();
}

async function cargaInicial() {
  try {
    s.tipos = await obtener("/api/feed/tipos");
  } catch (e) { s.tipos = {}; }
  try {
    // Dos lecturas: lo último de todo y lo último DEL BOT (que si no queda enterrado bajo la actividad del mercado).
    const [todo, delBot] = await Promise.all([obtener("/api/feed?limite=150"),
      obtener(`/api/feed?limite=150&tipo=${encodeURIComponent([...BOT].join(","))}`)]);
    s.botTs = todo.bot_ts;
    s.primeroDisponible = todo.primer_seq_disponible;
    añadir([...(todo.eventos || []), ...(delBot.eventos || [])].sort((a, b) => a.seq - b.seq));
    s.ultimo = Math.max(s.ultimo, todo.ultimo_seq ?? -1);
    s.eventos.sort((a, b) => b.seq - a.seq);
    pintarLista();
    return true;
  } catch (e) {
    s.conexion = "desconectado";
    pintarEstado();
    return false;
  }
}

export const vista = {
  async entrar(el) {
    s.raiz = el;
    s.estadoEl = h("div", {clase: "acciones", "aria-live": "polite"});
    s.lista = h("div", {});
    const botones = [["bot", "Actividad del bot"], ["mercado", "Ballenas y mercado"], ["sistema", "Fuentes de datos"], ["todo", "Todo"]];
    const pestanas = h("div", {clase: "pestanas", role: "group", "aria-label": "Qué actividad mostrar"},
      botones.map(([k, t]) => h("button", {type: "button", "aria-pressed": String(s.grupo === k), onClick: (e) => {
        s.grupo = k;
        mostrar = POR_TANDA;
        for (const b of pestanas.children) b.setAttribute("aria-pressed", String(b === e.currentTarget));
        pintarLista();
      }}, t)));
    mostrar = POR_TANDA;
    reemplazar(el, h("div", {clase: "titulo-vista"}, h("div", {}, h("h1", {}, "Actividad"),
      h("p", {}, "Lo último que ha hecho el bot y lo que pasa en el mercado. ", info("inferido", "observado o inferido")))),
    seccion(null, s.estadoEl, pestanas, s.lista));
    pintarEstado();
    pintarLista();
    if (s.ultimo < 0) await cargaInicial();
    if (s.raiz === el) conectarSse();
  },
  salir() {
    cerrarSse();
    if (s.sondeo) { clearInterval(s.sondeo); s.sondeo = null; }
    s.conexion = "desconectado";
    s.raiz = s.lista = s.estadoEl = null;
  },
};
