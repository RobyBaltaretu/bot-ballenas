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

/**
 * Gráfico de VELAS en SVG (cuenta agresiva, 25/11/2026): cuerpo y mecha de cada vela, niveles horizontales con su etiqueta
 * a la derecha (separadas para que no se pisen), una línea vertical en la entrada y puntos en los eventos (objetivos,
 * stop...). Al pasar el dedo o el ratón, «leyenda» muestra apertura, máximo, mínimo y cierre de esa vela.
 * velas: [[t (ms), o, h, l, c], ...]. seg: duración de cada vela en ms. niveles: [{v, clase, texto, fuera}] (los que
 * quedan muy lejos del precio se dejan fuera de la escala y se avisan en «fuera»). marcas: [{t (ms), v, clase, texto}].
 * entrada_t: ms de la entrada (línea vertical). formato(v) -> texto de un precio.
 */
export function graficoVelas(velas, {seg, niveles = [], marcas = [], entrada_t = null, leyenda, formato = String, etiqueta}) {
  const W = 1000, H = 260;
  const lo = Math.min(...velas.map((v) => v[3])), hi = Math.max(...velas.map((v) => v[2]));
  const rango = Math.max(hi - lo, Math.abs(hi) * 1e-4);
  const dentro = niveles.filter((n) => Number.isFinite(n.v) && n.v >= lo - rango * 1.2 && n.v <= hi + rango * 1.2);
  const fuera = niveles.filter((n) => Number.isFinite(n.v) && !dentro.includes(n));
  let min = Math.min(lo, ...dentro.map((n) => n.v)), max = Math.max(hi, ...dentro.map((n) => n.v));
  const pad = (max - min) * 0.06 || Math.abs(max) * 0.001;
  min -= pad; max += pad;
  const t0 = velas[0][0], t1 = velas[velas.length - 1][0] + seg;
  const x = (t) => (t - t0) / (t1 - t0) * W;
  const y = (v) => H - (v - min) / (max - min) * H;
  const ancho = Math.max(1, (seg / (t1 - t0)) * W * 0.7);
  const lienzo = svg("svg", {viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", role: "img", "aria-label": etiqueta || "Velas"});
  for (const n of dentro) {
    lienzo.append(svg("line", {x1: 0, x2: W, y1: y(n.v), y2: y(n.v), class: `nivel ${n.clase || ""}`, "vector-effect": "non-scaling-stroke"}));
  }
  if (Number.isFinite(entrada_t) && entrada_t >= t0 && entrada_t <= t1) {
    lienzo.append(svg("line", {x1: x(entrada_t), x2: x(entrada_t), y1: 0, y2: H, class: "vela-entrada", "vector-effect": "non-scaling-stroke"}));
  }
  for (const [t, o, hh, l, c] of velas) {
    const cx = x(t + seg / 2), clase = c >= o ? "vela-sube" : "vela-baja";
    lienzo.append(svg("line", {x1: cx, x2: cx, y1: y(hh), y2: y(l), class: `mecha ${clase}`, "vector-effect": "non-scaling-stroke"}));
    const y1 = y(Math.max(o, c)), y2 = y(Math.min(o, c));
    lienzo.append(svg("rect", {x: cx - ancho / 2, y: y1, width: ancho, height: Math.max(y2 - y1, 0.8), class: `cuerpo ${clase}`}));
  }
  // Etiquetas de los niveles: ordenadas por altura y separadas al menos 6 % del alto para que no se monten.
  const etq = dentro.map((n) => ({n, p: y(n.v) / H * 100})).sort((a, b) => a.p - b.p);
  for (let k = 1; k < etq.length; k++) etq[k].p = Math.max(etq[k].p, etq[k - 1].p + 6);
  const textos = etq.map(({n, p}) => {
    const el = h("div", {clase: ["nivel-texto", n.clase]}, n.texto);
    el.style.top = `${Math.min(p, 100)}%`;
    return el;
  });
  const fijos = marcas.filter((m) => m.t >= t0 && m.t <= t1 && Number.isFinite(m.v)).map((m) => {
    const el = h("div", {clase: ["marca-punto", m.clase], title: m.texto});
    el.style.left = `${x(m.t) / W * 100}%`;
    el.style.top = `${y(m.v) / H * 100}%`;
    return el;
  });
  const cursor = h("div", {clase: "cursor"});
  const caja = h("div", {clase: "grafico grafico-velas"}, lienzo, textos, fijos, cursor);
  const original = leyenda ? [...leyenda.childNodes] : null;
  function mover(e) {
    const r = caja.getBoundingClientRect();
    if (!r.width) return;
    const t = t0 + Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * (t1 - t0);
    const i = Math.min(velas.length - 1, Math.max(0, velas.findIndex((v) => v[0] + seg > t)));
    const [tv, o, hh, l, c] = velas[i < 0 ? velas.length - 1 : i];
    cursor.style.left = `${x(tv + seg / 2) / W * 100}%`;
    caja.classList.add("activo");
    if (leyenda) {
      const hora = new Date(tv).toLocaleString("es-ES", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"});
      reemplazar(leyenda, h("span", {clase: "tenue"}, `${hora} · `), `A ${formato(o)} · Máx ${formato(hh)} · Mín ${formato(l)} · `,
        h("strong", {clase: c >= o ? "sube" : "baja"}, `C ${formato(c)}`));
    }
  }
  function soltar() {
    caja.classList.remove("activo");
    if (leyenda) reemplazar(leyenda, ...original);
  }
  caja.addEventListener("pointermove", mover);
  caja.addEventListener("pointerdown", mover);
  caja.addEventListener("pointerleave", soltar);
  caja.addEventListener("pointercancel", soltar);
  caja.addEventListener("pointerup", (e) => { if (e.pointerType !== "mouse") soltar(); });
  return {caja, fuera};
}
