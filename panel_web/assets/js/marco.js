// Armazón del panel (18/11/2026, tema «terminal»): reloj UTC, contadores de la cabecera, cinta de eventos en vivo,
// insignias del menú lateral y altura de la cabecera para que el menú lateral quede pegado debajo.
// Todo con textContent / dom.h (nunca innerHTML) y sin estilos en línea salvo propiedades CSSOM.

import {cifraViva, emitirEvento} from "./anim.js";
import {obtener} from "./api.js";
import {$, h, reemplazar} from "./dom.js";
import {estado} from "./estado.js";
import {hace, hay, num, pct} from "./formato.js";

const pad = (n) => String(n).padStart(2, "0");

function reloj() {
  const el = $("reloj");
  if (!el) return;
  const pintar = () => {
    const d = new Date();
    reemplazar(el, `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`, h("small", {}, "UTC"));
  };
  pintar();
  setInterval(pintar, 1000);
}

function contador(etiqueta, valor, opcional) {
  return h("div", {clase: ["contador", opcional ? "opcional" : null]}, h("span", {clase: "etq"}, etiqueta), h("span", {clase: "v"}, valor));
}

/** Cabecera y menú lateral con los datos del bot. Se llama en cada sondeo de /api/datos. */
export function pintarMarco() {
  const d = estado.datos;
  const b = d?.bot || {};
  const inv = b.investigacion || {};
  const pos = b.posiciones || [];
  const maxPos = b.efectiva?.riesgo?.max_posiciones_abiertas;
  const ra = b.limites?.riesgo_abierto?.valor_pct;
  const cont = $("contadores");
  if (cont) {
    reemplazar(cont, d ? [
      contador("Variantes", hay(inv.variantes_totales) ? cifraViva("cab.variantes", inv.variantes_totales, (n) => num(n, 0)) : "—", true),
      contador("Listón t", num(inv.t_requerido, 1), true),
      contador("Abiertas", `${pos.length}${maxPos ? `/${maxPos}` : ""}`),
      contador("Riesgo", hay(ra) ? cifraViva("cab.riesgo", ra, (n) => pct(n, 1)) : pct(ra, 1)),
    ] : []);
  }
  const insOp = $("ins-operaciones");
  if (insOp) insOp.textContent = pos.length ? String(pos.length) : "";
  const insSis = $("ins-sistema");
  if (insSis) insSis.textContent = d?.sistema_resumen?.incidentes_activos ? String(d.sistema_resumen.incidentes_activos) : "";
  const insEst = $("ins-estrategias");
  if (insEst) insEst.textContent = (inv.aspirantes || []).length ? String(inv.aspirantes.length) : "";
  const pie = $("pie-lateral");
  if (pie) {
    reemplazar(pie, !d ? "conectando…" : [
      h("div", {}, d.bot_vivo ? h("b", {}, "● bot en marcha") : "○ bot sin señales"),
      h("div", {}, `foto ${hace(b.ts, d.ahora)}`),
      h("div", {}, `modo ${b.modo || "—"} · ${b.red || "—"}`),
    ]);
  }
}

// ---------------------------------------------------------------- cinta de eventos
const NOMBRES = {senal_detectada: "señal", decision_aprobada: "aprobada", decision_rechazada: "descartada", orden_enviada: "orden",
  orden_completada: "fill", entrada: "entrada", salida: "salida", cierre: "cierre", stop_movido: "stop movido", proteccion: "protección",
  intencion_shadow: "sombra", resultado_shadow: "sombra", alerta: "alerta", error: "error", ballena_fill: "ballena",
  ballena_cambio_inferido: "ballena", operacion_grande: "grande", liquidacion_inferida: "liquidación", datos_obsoletos: "datos",
  reconexion: "reconexión", fuente_perdida: "fuente", fuente_recuperada: "fuente"};
const TONO = {decision_aprobada: "ok", entrada: "ok", fuente_recuperada: "ok", error: "mal", alerta: "mal", fuente_perdida: "mal",
  decision_rechazada: null};

const DEL_BOT = ["senal_detectada", "decision_aprobada", "decision_rechazada", "orden_enviada", "orden_completada", "entrada",
  "salida", "cierre", "stop_movido", "proteccion", "alerta", "error", "intencion_shadow", "resultado_shadow"].join(",");

function itemCinta(ev) {
  const t = ev.ts_recepcion || ev.ts_exchange;
  const d = t ? new Date(t * 1000) : null;
  return h("span", {clase: "item"},
    h("span", {clase: "hora"}, d ? `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}` : "--:--"),
    h("span", {clase: ["tipo", TONO[ev.tipo] || null]}, NOMBRES[ev.tipo] || ev.tipo || "evento"),
    ev.moneda ? h("b", {}, `${ev.moneda} `) : null,
    ev.detalle ? String(ev.detalle).slice(0, 110) : "");
}

async function cinta() {
  const rodillo = $("rodillo");
  if (!rodillo) return;
  let firma = "";
  let ultimoSeq = null;                                // para emitir al bus solo lo NUEVO (no el histórico al abrir)
  async function cargar() {
    if (document.hidden && firma) return;              // la primera carga se hace siempre
    try {
      // Primero lo que hace el bot; si hay poco, se completa con lo último del mercado (sin repetir textos).
      const [delBot, todo] = await Promise.all([obtener(`/api/feed?limite=20&tipo=${encodeURIComponent(DEL_BOT)}`), obtener("/api/feed?limite=25")]);
      const vistos = new Set();
      const evs = [...(delBot.eventos || []), ...(todo.eventos || [])].sort((a, b) => b.seq - a.seq)
        .filter((e) => { const k = `${e.tipo}|${e.moneda}|${e.detalle}`; if (vistos.has(k)) return false; vistos.add(k); return true; })
        .slice(0, 25);
      const nueva = evs.map((e) => e.seq).join(",");
      // Novedades para el bus de eventos (núcleo 3D, Mesa): solo las posteriores a la última vista, y a lo sumo 4.
      const maxSeq = evs.length ? Math.max(...evs.map((e) => e.seq)) : null;
      if (ultimoSeq !== null && maxSeq !== null) {
        evs.filter((e) => e.seq > ultimoSeq).sort((a, b) => a.seq - b.seq).slice(-4).forEach((e, k) => setTimeout(() => emitirEvento(e), k * 500));
      }
      if (maxSeq !== null) ultimoSeq = Math.max(ultimoSeq ?? 0, maxSeq);
      if (nueva === firma) return;                     // sin novedades: no se reinicia la animación
      firma = nueva;
      // Dos copias seguidas y desplazamiento de media cinta: el bucle no tiene salto. La copia no se lee dos veces.
      const items = evs.length ? evs.map(itemCinta) : [h("span", {clase: "item"}, "Sin eventos recientes")];
      const copia = h("span", {clase: "copia", "aria-hidden": "true"}, evs.length ? evs.map(itemCinta) : "Sin eventos recientes");
      reemplazar(rodillo, h("span", {clase: "copia"}, items), copia);
      // Velocidad constante (~45 px/s): la duración crece con el largo de la cinta.
      rodillo.style.setProperty("--duracion-cinta", `${Math.max(30, Math.round(rodillo.scrollWidth / 2 / 45))}s`);
    } catch (e) {
      reemplazar(rodillo, h("span", {clase: "item"}, `Feed no disponible (${e.message})`));
      firma = "";
    }
  }
  await cargar();
  setInterval(cargar, 12000);
}

// ---------------------------------------------------------------- menú lateral pegado bajo la cabecera
function altoCabecera() {
  const cab = $("cabecera");
  if (!cab) return;
  const poner = () => document.documentElement.style.setProperty("--alto-cabecera", `${cab.offsetHeight}px`);
  poner();
  if (window.ResizeObserver) new ResizeObserver(poner).observe(cab);
  else window.addEventListener("resize", poner);
}

export function iniciarMarco() {
  reloj();
  cinta();
  altoCabecera();
}

/** Marca la sección actual en el menú lateral (la ficha de una operación cuelga de «Operaciones»). */
export function marcarLateral(nombre) {
  const actual = {operacion: "operaciones", estrategia: "estrategias"}[nombre] || nombre;
  for (const a of document.querySelectorAll(".lateral a[data-vista]")) {
    if (a.dataset.vista === actual) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
}
