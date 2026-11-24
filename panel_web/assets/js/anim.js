// Utilidades de animación (18/11/2026). Todo respeta «reducir movimiento» del sistema: con él activo, las cifras
// saltan directamente a su valor y no se lanza ningún bucle. Sin librerías; solo requestAnimationFrame y CSSOM.

import {h} from "./dom.js";

const mq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
export const reducido = () => !!mq?.matches;

const previos = new Map();        // clave -> último valor mostrado (para animar desde ahí al siguiente)
const suave = (t) => 1 - Math.pow(1 - t, 3);

/**
 * Cifra que «cuenta» hacia su valor: la primera vez desde 0, después desde el valor anterior de esa clave.
 * El DOM se reconstruye en cada refresco, por eso el valor previo se guarda aparte (por clave).
 * formato(n) -> texto. Devuelve un <span> que se anima solo mientras esté en pantalla.
 */
export function cifraViva(clave, valor, formato = (n) => String(Math.round(n)), duracion = 700) {
  const el = h("span", {clase: "cifra-viva"});
  const destino = Number(valor);
  if (!Number.isFinite(destino)) {
    el.textContent = formato(valor);
    return el;
  }
  const desde = previos.has(clave) ? previos.get(clave) : 0;
  previos.set(clave, destino);
  if (reducido() || desde === destino || document.hidden) {
    el.textContent = formato(destino);
    return el;
  }
  el.textContent = formato(desde);
  const t0 = performance.now();
  const paso = (t) => {
    if (!el.isConnected && t - t0 > 60) { el.textContent = formato(destino); return; }
    const k = Math.min(1, (t - t0) / duracion);
    el.textContent = formato(desde + (destino - desde) * suave(k));
    if (k < 1) requestAnimationFrame(paso);
  };
  requestAnimationFrame(paso);
  return el;
}

/** Quita la clase de «entrada» tras un rato: las animaciones de entrada solo suenan al abrir una vista, no en cada refresco. */
export function marcarEntrada(main, ms = 1600) {
  main.classList.add("anim-entrada");
  clearTimeout(main._tEntrada);
  main._tEntrada = setTimeout(() => main.classList.remove("anim-entrada"), ms);
}

/** Bus de eventos del bot: marco.js los emite al llegar novedades; el núcleo 3D y la Mesa reaccionan. */
export function emitirEvento(ev) {
  document.dispatchEvent(new CustomEvent("panel:evento", {detail: ev}));
}

export function alEvento(fn) {
  const f = (e) => fn(e.detail);
  document.addEventListener("panel:evento", f);
  return () => document.removeEventListener("panel:evento", f);
}

/** Minigráfico de una serie corta (sin ejes): línea y un punto final que respira. Devuelve un nodo SVG. */
export function chispa(valores, {ancho = 120, alto = 30} = {}) {
  const NS = "http://www.w3.org/2000/svg";
  const sv = document.createElementNS(NS, "svg");
  sv.setAttribute("viewBox", `0 0 ${ancho} ${alto}`);
  sv.setAttribute("preserveAspectRatio", "none");
  sv.setAttribute("class", "chispa");
  sv.setAttribute("aria-hidden", "true");
  if (!valores || valores.length < 2) return sv;
  const min = Math.min(...valores), max = Math.max(...valores), r = max - min || 1;
  const pts = valores.map((v, i) => [i / (valores.length - 1) * ancho, alto - 3 - (v - min) / r * (alto - 6)]);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = document.createElementNS(NS, "path");
  area.setAttribute("d", `${d} L${ancho} ${alto} L0 ${alto} Z`);
  area.setAttribute("class", "chispa-area");
  const linea = document.createElementNS(NS, "path");
  linea.setAttribute("d", d);
  linea.setAttribute("class", "chispa-linea");
  linea.setAttribute("vector-effect", "non-scaling-stroke");
  const [ux, uy] = pts[pts.length - 1];
  const punto = document.createElementNS(NS, "circle");
  punto.setAttribute("cx", ux.toFixed(1));
  punto.setAttribute("cy", uy.toFixed(1));
  punto.setAttribute("r", "2.4");
  punto.setAttribute("class", "chispa-punto");
  sv.append(area, linea, punto);
  return sv;
}
