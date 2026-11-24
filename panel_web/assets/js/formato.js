// Formatos en español. Regla: un dato ausente se muestra como «—» con su motivo, NUNCA como 0.

import {h} from "./dom.js";

const N = (d) => new Intl.NumberFormat("es-ES", {minimumFractionDigits: d, maximumFractionDigits: d});
const ES = new Intl.DateTimeFormat("es-ES", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit"});
const ES_CORTA = new Intl.DateTimeFormat("es-ES", {hour: "2-digit", minute: "2-digit", second: "2-digit"});

export const hay = (v) => v !== null && v !== undefined && !(typeof v === "number" && !Number.isFinite(v));

export function num(v, dec = 2) {
  return hay(v) ? N(dec).format(Number(v)) : "—";
}

export function precio(v) {
  if (!hay(v)) return "—";
  const x = Math.abs(Number(v));
  return N(x >= 1000 ? 1 : x >= 1 ? 2 : x >= 0.01 ? 4 : 6).format(Number(v));
}

export function usd(v, dec = 2) {
  return hay(v) ? `${N(dec).format(Number(v))} $` : "—";
}

export function pct(v, dec = 2) {
  return hay(v) ? `${N(dec).format(Number(v))} %` : "—";
}

export function conSigno(v, dec = 2, sufijo = "") {
  if (!hay(v)) return "—";
  const s = Number(v) > 0 ? "+" : Number(v) < 0 ? "−" : "";
  return `${s}${N(dec).format(Math.abs(Number(v)))}${sufijo}`;
}

/** Número con color Y signo/texto (el color nunca es la única señal). */
export function resultado(v, dec = 2, sufijo = " $") {
  if (!hay(v)) return h("span", {clase: "tenue", title: "dato no disponible"}, "— desconocido");
  const clase = Number(v) > 0 ? "sube" : Number(v) < 0 ? "baja" : null;
  const flecha = Number(v) > 0 ? "▲ " : Number(v) < 0 ? "▼ " : "";
  return h("span", {clase: ["num", clase]}, flecha + conSigno(v, dec, sufijo));
}

export function fecha(ts) {
  return hay(ts) && ts > 0 ? ES.format(new Date(ts * 1000)) : "—";
}

export function horaCorta(ts) {
  return hay(ts) && ts > 0 ? ES_CORTA.format(new Date(ts * 1000)) : "—";
}

export function iso(v) {
  if (!v) return null;
  const t = Date.parse(v);
  return Number.isNaN(t) ? null : t / 1000;
}

export function duracion(seg) {
  if (!hay(seg)) return "—";
  seg = Math.max(0, seg);
  if (seg < 60) return `${Math.round(seg)} s`;
  if (seg < 3600) return `${Math.round(seg / 60)} min`;
  if (seg < 86400 * 2) return `${N(1).format(seg / 3600)} h`;
  return `${N(1).format(seg / 86400)} d`;
}

export function hace(ts, ahora = Date.now() / 1000) {
  return hay(ts) && ts > 0 ? `hace ${duracion(ahora - ts)}` : "sin dato";
}

/** Frescura de un dato: {estado: fresco|retrasado|obsoleto|desconocido, texto}. Umbrales en segundos. */
export function frescura(ts, ahora = Date.now() / 1000, {retraso = 120, obsoleto = 600} = {}) {
  if (!hay(ts) || ts <= 0) return {estado: "desconocido", texto: "sin dato", clase: "aviso"};
  const edad = ahora - ts;
  if (edad <= retraso) return {estado: "fresco", texto: hace(ts, ahora), clase: "ok"};
  if (edad <= obsoleto) return {estado: "retrasado", texto: `retrasado (${hace(ts, ahora)})`, clase: "aviso"};
  return {estado: "obsoleto", texto: `obsoleto (${hace(ts, ahora)})`, clase: "mal"};
}

export const LADO = {L: "largo", S: "corto"};
export function lado(l) {
  return LADO[l] || (l ? String(l) : "—");
}

export function corto(id, n = 10) {
  if (!id) return "—";
  const s = String(id);
  return s.length > n + 2 ? `${s.slice(0, n)}…` : s;
}
