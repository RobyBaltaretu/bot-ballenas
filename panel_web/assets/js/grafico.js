// Gráfico de línea en SVG, sin librerías (saldo en Inicio y precio de la moneda en el detalle de una operación).
// Al pasar el dedo o el ratón, la cifra de encima muestra el valor de ese momento. Las etiquetas van en HTML (el SVG
// se estira con preserveAspectRatio="none" y el texto dentro se deformaría); las posiciones, por CSSOM (CSP estricta).

import {h, reemplazar} from "./dom.js";

const NS = "http://www.w3.org/2000/svg";

export function svg(etiqueta, atributos) {
  const el = document.createElementNS(NS, etiqueta);
  for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, String(v));
  return el;
}

/**
 * puntos: [[t (s), valor], ...] en orden. cifra/linea: nodos que se reescriben al recorrer el gráfico.
 * valor(v) -> texto de la cifra; pie(v0, vi, t) -> nodos de la línea de variación.
 * niveles: [{v, clase, texto}] líneas horizontales (entrada, stop, objetivo); entran siempre en la escala.
 * marcas: [{t, v, clase, texto}] puntos fijos (entrada, salida).
 */
export function graficoLinea(puntos, {cifra, linea, valor, pie, etiqueta, niveles = [], marcas = []}) {
  const W = 1000, H = 200;
  const ts = puntos.map((p) => p[0]), vs = puntos.map((p) => p[1]);
  const t0 = ts[0], t1 = ts[ts.length - 1] === t0 ? t0 + 1 : ts[ts.length - 1];
  const extra = [...niveles, ...marcas].map((n) => n.v).filter(Number.isFinite);
  let min = Math.min(...vs, ...extra), max = Math.max(...vs, ...extra);
  if (max - min < 1e-9) { const m = Math.max(Math.abs(max) * 0.002, 0.01); min -= m; max += m; }
  const pad = (max - min) * 0.12;
  min -= pad; max += pad;
  const x = (t) => (t - t0) / (t1 - t0) * W;
  const y = (v) => H - (v - min) / (max - min) * H;
  const d = puntos.map(([t, v], i) => `${i ? "L" : "M"}${x(t).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const dif = vs[vs.length - 1] - vs[0];
  const lienzo = svg("svg", {viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", role: "img", "aria-label": etiqueta});
  lienzo.append(svg("path", {d: `${d} L${W} ${H} L0 ${H} Z`, class: "area"}));
  if (!niveles.length) lienzo.append(svg("line", {x1: 0, x2: W, y1: y(vs[0]), y2: y(vs[0]), class: "base", "vector-effect": "non-scaling-stroke"}));
  for (const n of niveles) {
    lienzo.append(svg("line", {x1: 0, x2: W, y1: y(n.v), y2: y(n.v), class: `nivel ${n.clase || ""}`, "vector-effect": "non-scaling-stroke"}));
  }
  lienzo.append(svg("path", {d, class: "linea", "vector-effect": "non-scaling-stroke"}));
  const textos = niveles.map((n) => {
    const el = h("div", {clase: ["nivel-texto", n.clase]}, n.texto);
    el.style.top = `${y(n.v) / H * 100}%`;
    return el;
  });
  const fijos = marcas.filter((m) => m.t >= t0 && m.t <= t1).map((m) => {
    const el = h("div", {clase: ["marca-punto", m.clase], title: m.texto});
    el.style.left = `${x(m.t) / W * 100}%`;
    el.style.top = `${y(m.v) / H * 100}%`;
    return el;
  });
  const cursor = h("div", {clase: "cursor"});
  const punto = h("div", {clase: "punto"});
  const caja = h("div", {clase: ["grafico", dif > 0 ? "sube" : dif < 0 ? "baja" : null]}, lienzo, textos, fijos, cursor, punto);
  const original = [cifra.textContent, [...linea.childNodes]];

  function mover(e) {
    const r = caja.getBoundingClientRect();
    if (!r.width) return;
    const t = t0 + Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * (t1 - t0);
    let i = 0;
    for (let k = 1; k < ts.length; k++) if (Math.abs(ts[k] - t) < Math.abs(ts[i] - t)) i = k;
    const px = x(ts[i]) / W * 100, py = y(vs[i]) / H * 100;
    cursor.style.left = `${px}%`;
    punto.style.left = `${px}%`;
    punto.style.top = `${py}%`;
    caja.classList.add("activo");
    cifra.textContent = valor(vs[i]);
    reemplazar(linea, pie(vs[0], vs[i], ts[i]));
  }
  function soltar() {
    caja.classList.remove("activo");
    cifra.textContent = original[0];
    reemplazar(linea, original[1]);
  }
  caja.addEventListener("pointermove", mover);
  caja.addEventListener("pointerdown", mover);
  caja.addEventListener("pointerleave", soltar);
  caja.addEventListener("pointercancel", soltar);
  caja.addEventListener("pointerup", (e) => { if (e.pointerType !== "mouse") soltar(); });
  return caja;
}
