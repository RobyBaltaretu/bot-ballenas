// Construcción del DOM SIN innerHTML: todo texto dinámico (monedas, motivos, errores del exchange, logs...) entra
// como textContent. Así ningún dato puede convertirse en HTML o script.

import {marcarEntrada} from "./anim.js";   // (anim.js importa h de aquí: ciclo inocuo, solo se usan dentro de funciones)

const EVENTO = /^on[A-Z]/;

export function h(etiqueta, atributos, ...hijos) {
  const el = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(atributos || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "clase") el.className = Array.isArray(v) ? v.filter(Boolean).join(" ") : v;
    else if (k === "texto") el.textContent = String(v);
    else if (EVENTO.test(k)) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "estilo") {                                         // CSSOM: permitido por la CSP
      for (const [p, val] of Object.entries(v)) { if (p.startsWith("--")) el.style.setProperty(p, val); else el.style[p] = val; }
    }
    else if (k === "valor") el.value = v;
    else if (k === "marcado") el.checked = !!v;
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  agregar(el, hijos);
  return el;
}

export function agregar(el, hijos) {
  for (const x of hijos.flat(Infinity)) {
    if (x === null || x === undefined || x === false) continue;
    el.append(x instanceof Node ? x : document.createTextNode(String(x)));
  }
  return el;
}

export function reemplazar(el, ...hijos) {
  el.replaceChildren();
  return agregar(el, hijos);
}

export const $ = (id) => document.getElementById(id);

/** ¿Está el usuario escribiendo o eligiendo algo dentro de 'raiz'? Entonces no se repinta (no se pierde lo escrito). */
export function escribiendo(raiz) {
  const a = document.activeElement;
  return !!(raiz && a && a !== raiz && raiz.contains(a) && ["INPUT", "SELECT", "TEXTAREA"].includes(a.tagName));
}

// Pestaña elegida por vista: solo en memoria (vuelve a la primera al recargar).
const PESTANA_ELEGIDA = new Map();

/** Pestañas de una vista: parten una página larga en pantallas cortas (18/11/2026, sin scroll infinito).
 *  opciones: [[id, título, () => contenido]]. Solo se construye la pestaña visible. Devuelve el elemento. */
export function pestanasVista(clave, opciones, etiqueta = "Secciones") {
  const ids = opciones.map((o) => o[0]);
  let actual = PESTANA_ELEGIDA.get(clave);
  if (!ids.includes(actual)) actual = ids[0];
  const cuerpo = h("div", {clase: "panel-pestana", role: "tabpanel"});
  const botones = opciones.map(([id, titulo]) => h("button", {type: "button", role: "tab", "aria-selected": String(id === actual),
    "aria-pressed": String(id === actual), onClick: () => elegir(id)}, titulo));
  const barra = h("div", {clase: "pestanas pestanas-vista", role: "tablist", "aria-label": etiqueta}, botones);
  function elegir(id) {
    actual = id;
    PESTANA_ELEGIDA.set(clave, id);
    botones.forEach((b, k) => { b.setAttribute("aria-selected", String(ids[k] === id)); b.setAttribute("aria-pressed", String(ids[k] === id)); });
    const fn = opciones.find((o) => o[0] === id)[2];
    reemplazar(cuerpo, fn());
    if (primera) primera = false; else marcarEntrada(cuerpo.closest("main") || cuerpo);   // al cambiar de pestaña, entra con animación
  }
  let primera = true;
  elegir(actual);
  return h("div", {clase: "vista-pestanas"}, barra, cuerpo);
}

/** Estado vacío explicado (nunca una tabla en blanco sin motivo). */
export function vacio(texto) {
  return h("p", {clase: "vacio"}, texto);
}

export function errorCarga(texto) {
  return h("p", {clase: "vacio error-carga", role: "alert"}, texto);
}

/** Tabla accesible. columnas: [{t: título, v: fila => nodo|texto, der: bool}]. En móvil cada celda lleva su etiqueta. */
export function tabla(columnas, filas, {alPulsar, titulo, vacioTexto} = {}) {
  if (!filas || !filas.length) return vacio(vacioTexto || "Sin datos.");
  const cuerpo = filas.map((f) => {
    const tr = h("tr", {clase: alPulsar ? "clicable" : null},
      columnas.map((c) => h("td", {clase: c.der ? "der" : null, "data-etiqueta": c.t}, c.v(f))));
    if (alPulsar) {
      tr.tabIndex = 0;
      tr.addEventListener("click", () => alPulsar(f));
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); alPulsar(f); } });
    }
    return tr;
  });
  return h("div", {clase: "tabla-envoltura"},
    h("table", {clase: "resp"},
      titulo ? h("caption", {}, titulo) : null,
      h("thead", {}, h("tr", {}, columnas.map((c) => h("th", {scope: "col", clase: c.der ? "der" : null}, c.t)))),
      h("tbody", {}, cuerpo)));
}

export function chip(texto, tipo, {punto = true, titulo} = {}) {
  return h("span", {clase: ["chip", tipo, punto ? null : "sin-punto"], title: titulo || null}, texto);
}

export function seccion(titulo, ...hijos) {
  return h("section", {clase: "seccion"}, titulo ? h("h2", {}, titulo) : null, ...hijos);
}

export function plegable(titulo, abierto, ...hijos) {
  return h("details", {clase: "plegable", open: abierto || null}, h("summary", {}, titulo), h("div", {clase: "cuerpo"}, ...hijos));
}

/** Valor de una ficha: un hueco en blanco se lee como «no hay» cuando quizá es «no se sabe». Se distingue:
 *  ausente (null/undefined/"") -> «— sin dato»; lista vacía -> «ninguno»; el resto, tal cual. */
function valorFicha(v) {
  if (v === null || v === undefined || v === "") return h("span", {clase: "tenue", title: "dato no disponible"}, "— sin dato");
  if (Array.isArray(v) && !v.length) return h("span", {clase: "tenue"}, "ninguno");
  return v;
}

export function listaDef(pares) {
  return h("dl", {clase: "lista-def"}, pares.filter(Boolean).map(([k, v]) => [h("dt", {}, k), h("dd", {}, valorFicha(v))]));
}
