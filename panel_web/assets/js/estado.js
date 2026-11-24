// Estado compartido: /api/datos se sondea cada 10 s (y al volver a la pestaña). Las vistas se suscriben.

import {obtener} from "./api.js";

const suscriptores = new Set();
export const estado = {datos: null, error: null, ultimoOk: null, cargando: true};
let temporizador = null;

export function suscribir(fn) {
  suscriptores.add(fn);
  return () => suscriptores.delete(fn);
}

function avisar() {
  for (const fn of suscriptores) {
    try { fn(estado); } catch (e) { console.error(e); }
  }
}

export async function refrescar() {
  try {
    estado.datos = await obtener("/api/datos");
    estado.error = null;
    estado.ultimoOk = Date.now() / 1000;
  } catch (e) {
    estado.error = e.message;           // se conservan los últimos datos, marcados como viejos
  }
  estado.cargando = false;
  avisar();
}

export function iniciarSondeo(cada = 10000) {
  if (temporizador) return;
  refrescar();
  temporizador = setInterval(() => { if (!document.hidden) refrescar(); }, cada);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refrescar(); });
}

export const bot = () => estado.datos?.bot || {};

// Preferencia del visitante (modo experto): solo una comodidad local, nunca datos privados ni el token.
export const preferencias = {
  get experto() {
    try { return localStorage.getItem("panel.experto") === "1"; } catch (e) { return false; }
  },
  set experto(v) {
    try { localStorage.setItem("panel.experto", v ? "1" : "0"); } catch (e) { /* sin almacenamiento: no pasa nada */ }
  },
  // Tema: «terminal» (oscuro, por defecto) o «claro». Solo una comodidad visual local.
  get tema() {
    try { return localStorage.getItem("panel.tema") === "claro" ? "claro" : "terminal"; } catch (e) { return "terminal"; }
  },
  set tema(v) {
    try { localStorage.setItem("panel.tema", v === "claro" ? "claro" : "terminal"); } catch (e) { /* sin almacenamiento */ }
  },
};

export function aplicarTema(tema) {
  if (tema === "claro") document.documentElement.dataset.tema = "claro";
  else delete document.documentElement.dataset.tema;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", tema === "claro" ? "#ffffff" : "#06080a");
}
