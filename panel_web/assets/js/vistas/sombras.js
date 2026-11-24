// SÓNAR DE SOMBRAS: lo que el bot vio pasar y dejó ir. Cada señal descartada se sigue «en papel» con precios reales
// (aprendizaje.json, tipo "sombra"); aquí se ven como ecos en un sónar: el ángulo es la estrategia que la propuso, la
// distancia al centro es su antigüedad, el color es cómo habría acabado y el tamaño, cuántas R. El barrido las va
// iluminando. Debajo: la balanza (lo que se ahorró frente a lo que dejó pasar), las que siguen en el agua, si cada
// motivo de descarte acierta y la estela de cada estrategia. Solo informa: nada de esto decide.
// Todo el SVG con createElementNS y atributos; colores por clases y posiciones por CSSOM (CSP estricta).

import {obtener} from "../api.js";
import {chip, errorCarga, h, reemplazar, vacio} from "../dom.js";
import {conSigno, duracion, hace, hay, lado, num} from "../formato.js";
import {svg} from "../grafico.js";

const QUIETO = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const DIA = 86400;
const BARRIDO_S = 6;
const PERIODOS = [[7, "7 días"], [30, "30 días"], [0, "Todo"]];
const RESULTADOS = [["todas", "Todas"], ["ganan", "Ganadoras"], ["pierden", "Perdedoras"], ["vivas", "En el agua"]];
const ESTADO = {activa: ["activa", "ok"], apagada: ["apagada", null], investigacion: ["en estudio", "info"],
  desconocido: ["sin dato", "aviso"]};
const LECTURA = {acierta: ["acierta", "ok"], falla: ["se equivoca", "mal"], neutro: ["no se nota", null], pocos: ["pocos casos", "aviso"]};
const SALIDA = {"stop-loss": "saltó el stop", "tiempo máximo": "se acabó el tiempo", "stop sin pérdidas": "stop en tablas",
  "stop dinámico": "stop dinámico", "objetivo final": "llegó al objetivo"};

let raiz = null, datos = null, periodo = 30, filtro = "todas", foco = null, elegido = null, cargado = 0;
let observador = null, sonarVivo = null;

const nombre = (clave) => String(clave || "?").replace(/_/g, " ");
// En pantallas estrechas los nombres van abreviados en el borde del sónar (la ficha da el nombre entero).
const ABREV = {cartera_funding: "cart", liquidaciones: "liq", ballenas: "ball", momentum: "mom", retroceso: "retr",
  reversion: "rev", ruptura: "rupt", funding: "fund", fuerza: "fuer"};
const abreviado = (clave) => {
  const m = String(clave || "?").match(/^(.*)_(\dh)$/);
  return m ? `${ABREV[m[1]] || m[1].slice(0, 4)}·${m[2]}` : nombre(clave);
};
const claseR = (r) => (!hay(r) ? "plano" : r > 0.05 ? "gana" : r < -0.05 ? "pierde" : "plano");
const etiquetaCat = (clave) => (datos.categorias || []).find((c) => c.clave === clave)?.etiqueta || clave;

function azar(texto) {                 // reparto estable dentro del sector (mismo punto, mismo sitio)
  let x = 2166136261;
  for (const ch of String(texto)) { x ^= ch.codePointAt(0); x = Math.imul(x, 16777619); }
  return (x >>> 0) / 4294967296;
}

// ---------------------------------------------------------------- balanza
function balanza() {
  const b = datos.balanza, t = datos.total, op = datos.operadas;
  const peso = b.ahorrado + b.dejado;
  const ang = peso ? Math.max(-13, Math.min(13, (b.dejado - b.ahorrado) / peso * 60)) : 0;   // + = se hunde lo dejado
  const L = 140, dy = L * Math.sin(ang * Math.PI / 180);

  const brazo = svg("g", {class: "bal-brazo"});
  brazo.append(svg("line", {x1: 60, y1: 40, x2: 340, y2: 40, class: "bal-viga"}),
    svg("circle", {cx: 60, cy: 40, r: 4, class: "bal-pomo"}), svg("circle", {cx: 340, cy: 40, r: 4, class: "bal-pomo"}));
  const plato = (x, clase, monedas) => {
    const pos = svg("g", {transform: `translate(${x} 40)`});
    const mueve = svg("g", {class: "bal-plato-mueve"});
    mueve.append(svg("line", {x1: 0, y1: 0, x2: -34, y2: 74, class: "bal-cuerda"}),
      svg("line", {x1: 0, y1: 0, x2: 34, y2: 74, class: "bal-cuerda"}));
    for (let i = 0; i < monedas; i++) {            // un montón de fichas: más alto cuanto más pesa
      const fila = Math.floor(i / 5), col = i % 5;
      mueve.append(svg("circle", {cx: -20 + col * 10 + (fila % 2) * 5, cy: 68 - fila * 7, r: 4.4, class: `bal-ficha ${clase}`}));
    }
    mueve.append(svg("path", {d: "M-44 74 Q0 104 44 74 Z", class: `bal-cuenco ${clase}`}));
    pos.append(mueve);
    return [pos, mueve];
  };
  const fichas = (v) => (peso ? Math.max(1, Math.round(v / peso * 24)) : 0);
  const [pIzq, mIzq] = plato(60, "pierde", fichas(b.ahorrado));
  const [pDer, mDer] = plato(340, "gana", fichas(b.dejado));
  const dibujo = svg("svg", {viewBox: "0 0 400 190", class: "bal-svg", role: "img",
    "aria-label": `Balanza: se ahorró ${num(b.ahorrado, 1)} R y dejó pasar ${num(b.dejado, 1)} R`});
  dibujo.append(svg("path", {d: "M168 182 L232 182 L216 170 L184 170 Z", class: "bal-base"}),
    svg("line", {x1: 200, y1: 40, x2: 200, y2: 172, class: "bal-poste"}), brazo, pIzq, pDer,
    svg("circle", {cx: 200, cy: 40, r: 6, class: "bal-eje"}));
  const inclinar = () => {
    brazo.style.transform = `rotate(${ang}deg)`;
    mIzq.style.transform = `translateY(${-dy}px)`;
    mDer.style.transform = `translateY(${dy}px)`;
  };
  if (QUIETO) inclinar(); else requestAnimationFrame(() => requestAnimationFrame(inclinar));

  let veredicto;
  if (!t.n) veredicto = "Aún no ha terminado ninguna sombra.";
  else if (t.n < 30 || !hay(t.t)) veredicto = "Con tan pocas sombras cerradas la balanza aún no dice nada.";
  else if (t.t >= 2) veredicto = "Pesa más lo que dejó pasar: en conjunto, descartar le está costando.";
  else if (t.t <= -2) veredicto = "Pesa más lo que se ahorró: en conjunto, descartar le está protegiendo.";
  else veredicto = "Empate técnico: lo que dejó pasar y lo que se ahorró se compensan.";

  return h("section", {clase: "bal"},
    h("div", {clase: "bal-dibujo"}, dibujo),
    h("div", {clase: "bal-platos"},
      h("div", {clase: "bal-lado pierde"}, h("div", {clase: "bal-etq"}, "Se ahorró"),
        h("div", {clase: "bal-cifra"}, conSigno(-b.ahorrado, 1, " R")),
        h("div", {clase: "tenue"}, `${b.n_pierden} sombras que habrían perdido`)),
      h("div", {clase: "bal-lado gana"}, h("div", {clase: "bal-etq"}, "Dejó pasar"),
        h("div", {clase: "bal-cifra"}, conSigno(b.dejado, 1, " R")),
        h("div", {clase: "tenue"}, `${b.n_ganan} sombras que habrían ganado`))),
    h("div", {clase: "bal-veredicto"},
      h("p", {clase: "bal-frase"}, veredicto),
      h("p", {clase: "tenue"}, t.n ? `Si las hubiera operado todas: ${conSigno(b.neto, 1, " R")} en ${t.n} `
        + `(${conSigno(t.r_medio, 2, " R")} de media, gana el ${num(t.ganan_pct, 0)} %${hay(t.t) ? `, t = ${num(t.t, 1)}` : ""}). `
        + (op.n ? `Las que sí operó: ${conSigno(op.r_medio, 2, " R")} de media en ${op.n}.` : "Aún no ha cerrado ninguna operada.") : "")));
}

// ---------------------------------------------------------------- sónar
function puntosVisibles() {
  const ahora = datos.ahora;
  const desdeP = periodo ? ahora - periodo * DIA : 0;
  const cerradas = (datos.puntos || []).filter((p) => p.ts >= desdeP).map((p) => ({...p, viva: false}));
  const vivas = (datos.abiertas || []).filter((a) => a.ts >= desdeP).map((a) => ({...a, r: a.r_ahora, viva: true}));
  return vivas.concat(cerradas);
}

function sectores(puntos) {
  const n = new Map();
  for (const p of puntos) n.set(p.e, (n.get(p.e) || 0) + 1);
  const orden = (datos.estrategias || []).map((e) => e.clave).filter((c) => n.has(c));
  for (const c of n.keys()) if (!orden.includes(c)) orden.push(c);
  const hueco = 1.5, minimo = 14;
  const disponible = 360 - hueco * orden.length;
  const pesos = orden.map((c) => Math.sqrt(n.get(c)) + 1);
  const suma = pesos.reduce((a, b) => a + b, 0);
  let anchos = pesos.map((p) => Math.max(minimo, p / suma * disponible));
  const sobra = anchos.reduce((a, b) => a + b, 0) - disponible;
  const grandes = anchos.reduce((a, w) => a + (w > minimo ? w - minimo : 0), 0);
  if (sobra > 0 && grandes > 0) anchos = anchos.map((w) => (w > minimo ? w - sobra * (w - minimo) / grandes : w));
  let a = 0;
  return orden.map((c, i) => {
    const s = {clave: c, n: n.get(c), desde: a + hueco / 2, hasta: a + hueco / 2 + anchos[i],
      estado: (datos.estrategias || []).find((e) => e.clave === c)?.estado || "desconocido"};
    a += anchos[i] + hueco;
    return s;
  });
}

function pasa(p) {
  if (foco && p.e !== foco) return false;
  if (filtro === "ganan") return !p.viva && p.r > 0.05;
  if (filtro === "pierden") return !p.viva && p.r < -0.05;
  if (filtro === "vivas") return p.viva;
  return true;
}

function montarSonar(caja, ficha) {
  // Más ancho que alto: los nombres de las estrategias necesitan sitio a los lados del círculo.
  const ancho = Math.round(Math.min(760, Math.max(290, caja.clientWidth || 600)));
  const estrecho = ancho < 520;
  const alto = Math.round(Math.min(ancho, 600));
  const cx = ancho / 2, c = alto / 2;
  const R = Math.min(c - (estrecho ? 26 : 34), cx - (estrecho ? 50 : 112)), R0 = 14;
  const ahora = datos.ahora;
  const puntos = puntosVisibles();
  const secs = sectores(puntos);
  const edadMax = periodo ? periodo * DIA : Math.max(DIA, ahora - Math.min(...puntos.map((p) => p.ts), ahora - DIA));
  const radio = (ts) => R0 + (R - R0) * Math.sqrt(Math.min(1, Math.max(0, ahora - ts) / edadMax));
  const pt = (ang, r) => [cx + r * Math.sin(ang * Math.PI / 180), c - r * Math.cos(ang * Math.PI / 180)];
  const cuña = (a1, a2, r) => {
    const [x1, y1] = pt(a1, r), [x2, y2] = pt(a2, r);
    return `M${cx} ${c} L${x1.toFixed(1)} ${y1.toFixed(1)} A${r} ${r} 0 ${a2 - a1 > 180 ? 1 : 0} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} Z`;
  };

  const raizSvg = svg("svg", {viewBox: `0 0 ${ancho} ${alto}`, width: ancho, height: alto, class: "sonar-svg", role: "img",
    "aria-label": `Sónar con ${puntos.length} sombras de ${secs.length} estrategias`});
  const defs = svg("defs", {});
  const grad = svg("radialGradient", {id: "sonar-fondo", cx: "50%", cy: "50%", r: "50%"});
  grad.append(svg("stop", {offset: "0%", class: "sonar-f0"}), svg("stop", {offset: "100%", class: "sonar-f1"}));
  defs.append(grad);
  raizSvg.append(defs, svg("circle", {cx, cy: c, r: R + 4, fill: "url(#sonar-fondo)", class: "sonar-disco"}));

  // Sector enfocado: una cuña tenue detrás de los puntos.
  for (const s of secs) if (foco === s.clave) raizSvg.append(svg("path", {d: cuña(s.desde, s.hasta, R), class: "sonar-foco"}));

  // Anillos de antigüedad.
  const marcas = [[0.25, "6 h"], [1, "1 d"], [3, "3 d"], [7, "7 d"], [14, "14 d"], [30, "30 d"], [60, "60 d"], [90, "90 d"]]
    .filter(([d]) => d * DIA < edadMax * 0.97);
  let ultimoR = R0;
  for (const [d, txt] of marcas) {
    const r = radio(ahora - d * DIA);
    if (r - ultimoR < 16) continue;
    ultimoR = r;
    raizSvg.append(svg("circle", {cx, cy: c, r, class: "sonar-anillo"}));
    const etq = svg("text", {x: cx + 3, y: c - r - 3, class: "sonar-etq-anillo"});
    etq.textContent = txt;
    raizSvg.append(etq);
  }
  raizSvg.append(svg("circle", {cx, cy: c, r: R, class: "sonar-anillo borde"}));
  const etqFin = svg("text", {x: cx + 3, y: c - R - 3, class: "sonar-etq-anillo"});
  etqFin.textContent = periodo ? `${periodo} d` : `${Math.round(edadMax / DIA)} d`;
  raizSvg.append(etqFin);

  // Radios entre estrategias y sus nombres en el borde (clic: enfocar esa estrategia).
  const capaEtq = svg("g", {});
  for (const s of secs) {
    const [x1, y1] = pt(s.desde, R0), [x2, y2] = pt(s.desde, R);
    raizSvg.append(svg("line", {x1, y1, x2, y2, class: "sonar-radio"}));
    const medio = (s.desde + s.hasta) / 2;
    const [tx, ty] = pt(medio, R + (estrecho ? 9 : 13));
    const ancla = tx > cx + 6 ? "start" : tx < cx - 6 ? "end" : "middle";
    const etq = svg("text", {x: tx.toFixed(1), y: (ty + (ty > c ? 9 : 0)).toFixed(1), "text-anchor": ancla,
      class: `sonar-etq-est ${s.estado}${foco === s.clave ? " activo" : ""}`, tabindex: 0, role: "button",
      "aria-label": `${nombre(s.clave)}: ${s.n} sombras. Pulsa para enfocarla.`});
    etq.textContent = estrecho ? abreviado(s.clave) : `${nombre(s.clave)} · ${s.n}`;
    const enfocar = () => { foco = foco === s.clave ? null : s.clave; pintarSonar(); };
    etq.addEventListener("click", enfocar);
    etq.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); enfocar(); } });
    capaEtq.append(etq);
  }

  // El barrido: una cuña que se desvanece hacia atrás y gira; los ecos se encienden cuando pasa por encima.
  const haz = svg("g", {class: "sonar-giro"});
  haz.style.transformOrigin = `${cx}px ${c}px`;
  haz.style.animationDuration = `${BARRIDO_S}s`;
  for (let k = 0; k < 10; k++) {
    haz.append(svg("path", {d: cuña(-(k + 1) * 4, -k * 4, R), class: "sonar-haz", "fill-opacity": (0.24 * (1 - k / 10)).toFixed(3)}));
  }
  const [lx, ly] = pt(0, R);
  haz.append(svg("line", {x1: cx, y1: c, x2: lx, y2: ly, class: "sonar-haz-linea"}));
  if (!QUIETO) raizSvg.append(haz);

  // Ecos.
  const capa = svg("g", {class: "sonar-ecos"});
  const pos = [];
  const tam = estrecho ? 1.4 : 2;
  puntos.forEach((p, i) => {
    const s = secs.find((x) => x.clave === p.e);
    const pad = Math.min(2.5, (s.hasta - s.desde) * 0.12);
    const ang = s.desde + pad + azar(p.id) * (s.hasta - s.desde - 2 * pad);
    const [x, y] = pt(ang, radio(p.ts));
    pos[i] = [x, y];
    const r = tam + 1.5 * Math.sqrt(Math.min(Math.abs(p.r || 0), 4));
    const cl = ["sonar-eco", claseR(p.r), p.viva ? "en-agua" : "", pasa(p) ? "" : "atenuado"].filter(Boolean).join(" ");
    const eco = svg("circle", {cx: x.toFixed(1), cy: y.toFixed(1), r: r.toFixed(1), class: cl, "data-i": i});
    if (!QUIETO) eco.style.animationDelay = `${(ang / 360 * BARRIDO_S).toFixed(2)}s`;
    capa.append(eco);
    if (p.viva && pasa(p)) {
      const onda = svg("circle", {cx: x.toFixed(1), cy: y.toFixed(1), r: (r + 3).toFixed(1), class: "sonar-onda", "data-i": i});
      capa.append(onda);
    }
  });
  raizSvg.append(capa);
  const marca = svg("circle", {cx: -50, cy: -50, r: 9, class: "sonar-marca"});
  raizSvg.append(marca, svg("circle", {cx, cy: c, r: 5, class: "sonar-centro"}), capaEtq);
  const centro = svg("text", {x: cx, y: c + 18, "text-anchor": "middle", class: "sonar-etq-anillo"});
  centro.textContent = "ahora";
  raizSvg.append(centro);

  const elegir = (i) => {
    const p = puntos[i];
    if (!p) return;
    elegido = p.id;
    marca.setAttribute("cx", pos[i][0].toFixed(1));
    marca.setAttribute("cy", pos[i][1].toFixed(1));
    reemplazar(ficha, fichaSombra(p));
  };
  capa.addEventListener("pointerover", (e) => { const i = e.target.getAttribute?.("data-i"); if (i !== null && i !== undefined) elegir(Number(i)); });
  capa.addEventListener("click", (e) => { const i = e.target.getAttribute?.("data-i"); if (i !== null && i !== undefined) elegir(Number(i)); });

  reemplazar(caja, raizSvg);
  const inicial = puntos.findIndex((p) => p.id === elegido);
  const primero = inicial >= 0 ? inicial : puntos.findIndex((p) => pasa(p));
  if (primero >= 0) elegir(primero);
  else reemplazar(ficha, vacio("Nada que mostrar con este filtro."));
}

function fichaSombra(p) {
  const fila = (k, ...v) => h("div", {clase: "sonar-fila"}, h("span", {clase: "tenue"}, k), h("span", {}, ...v));
  return h("div", {clase: ["sonar-ficha", claseR(p.r), p.viva ? "en-agua" : null]},
    h("div", {clase: "sonar-ficha-cab"},
      h("div", {}, h("div", {clase: "sonar-ficha-moneda"}, p.m || "—"),
        h("div", {clase: "tenue"}, `${lado(p.l)} · ${nombre(p.e)}`)),
      h("div", {clase: "sonar-ficha-r"}, hay(p.r) ? conSigno(p.r, 2, " R") : "—",
        h("div", {clase: "sonar-ficha-sub"}, p.viva ? "va así ahora" : "habría acabado"))),
    fila("Descartada por", etiquetaCat(p.cat)),
    h("p", {clase: "sonar-motivo"}, p.motivo || "—"),
    fila("Señal", hace(p.ts, datos.ahora)),
    p.viva ? fila("Le queda", hay(p.limite_ts) ? duracion(p.limite_ts - datos.ahora) : "—")
      : fila("Salida", `${SALIDA[p.c] || p.c || "—"} · tras ${duracion((p.fin || p.ts) - p.ts)}`),
    p.tid ? h("a", {clase: "sonar-enlace", href: `#/operacion/${encodeURIComponent(p.tid)}`}, "Ver la señal en el registro →") : null);
}

function segmentos(opciones, actual, al) {
  return h("div", {clase: "segmentos", role: "group"}, opciones.map(([v, txt]) =>
    h("button", {type: "button", clase: v === actual ? "activo" : null, "aria-pressed": String(v === actual),
      onClick: () => al(v)}, txt)));
}

function pintarSonar() {
  if (!sonarVivo) return;
  const {caja, ficha, controles} = sonarVivo;
  reemplazar(controles,
    segmentos(PERIODOS, periodo, (v) => { periodo = v; pintarSonar(); }),
    segmentos(RESULTADOS, filtro, (v) => { filtro = v; pintarSonar(); }),
    foco ? h("button", {type: "button", clase: "sonar-quitar", onClick: () => { foco = null; pintarSonar(); }}, `${nombre(foco)} ✕`) : null);
  montarSonar(caja, ficha);
}

function seccionSonar() {
  const caja = h("div", {clase: "sonar-caja"});
  const ficha = h("div", {clase: "sonar-lado"});
  const controles = h("div", {clase: "sonar-controles"});
  sonarVivo = {caja, ficha, controles};
  return h("section", {clase: "seccion"},
    h("h2", {}, "El sónar"),
    controles,
    h("div", {clase: "sonar-rejilla"}, caja, ficha),
    h("div", {clase: "sonar-leyenda"},
      h("span", {}, h("i", {clase: "ley gana"}), "habría ganado"), h("span", {}, h("i", {clase: "ley pierde"}), "habría perdido"),
      h("span", {}, h("i", {clase: "ley plano"}), "quedó en tablas"), h("span", {}, h("i", {clase: "ley en-agua"}), "sigue en el agua"),
      h("span", {clase: "tenue"}, "Cuanto más lejos del centro, más antigua; cuanto más grande, más R. Pulsa un nombre para enfocar esa estrategia.")));
}

// ---------------------------------------------------------------- en el agua
function carril(a) {
  const valores = [a.r_stop, a.r_tp1, a.r_tpf, a.r_mejor, a.r_ahora, 0, -1].filter(hay);
  const lo = Math.min(...valores) - 0.15, hi = Math.max(...valores) + 0.15;
  const x = (v) => `${((v - lo) / (hi - lo) * 100).toFixed(2)}%`;
  const marcaNivel = (v, txt, clase) => (hay(v) ? h("div", {clase: ["carril-nivel", clase], estilo: {left: x(v)}},
    h("span", {}, txt)) : null);
  const ahoraR = a.r_ahora;
  return h("div", {clase: "agua-carril"},
    h("div", {clase: "carril-agua"},
      h("div", {clase: "carril-zona pierde", estilo: {left: "0%", width: x(0)}}),
      h("div", {clase: "carril-zona gana", estilo: {left: x(0), right: "0"}}),
      marcaNivel(a.r_stop, a.en_breakeven ? "stop (protegido)" : "stop", "stop"),
      marcaNivel(0, "entrada", "entrada"),
      marcaNivel(a.r_tp1, a.tp1_hecho ? "✓ parcial" : "parcial", a.tp1_hecho ? "hecho" : "tp"),
      marcaNivel(a.r_tpf, "objetivo", "tp"),
      hay(a.r_mejor) ? h("div", {clase: "carril-mejor", estilo: {left: x(a.r_mejor)}, title: `Lo mejor que llegó: ${conSigno(a.r_mejor, 2, " R")}`}) : null,
      hay(ahoraR) ? h("div", {clase: ["carril-pez", claseR(ahoraR)], estilo: {left: x(ahoraR)}},
        h("span", {}, conSigno(ahoraR, 2, " R"))) : null));
}

function seccionAgua() {
  const vivas = datos.abiertas || [];
  const ahora = datos.ahora;
  return h("section", {clase: "seccion"},
    h("h2", {}, "En el agua ahora", h("span", {clase: "tenue cuenta-titulo"}, ` · ${vivas.length}`)),
    vivas.length ? h("ul", {clase: "agua-lista"}, vivas.map((a) => {
      const total = hay(a.limite_ts) ? a.limite_ts - a.ts : null;
      const pasado = total ? Math.max(0, Math.min(1, (ahora - a.ts) / total)) : null;
      return h("li", {clase: "agua-fila"},
        h("div", {clase: "agua-cab"},
          h("div", {}, h("span", {clase: "agua-moneda"}, a.m), " ", chip(lado(a.l), a.l === "L" ? "ok" : "mal", {punto: false}),
            h("div", {clase: "tenue agua-sub"}, `${nombre(a.e)} · ${etiquetaCat(a.cat)}`)),
          h("div", {clase: ["agua-r", claseR(a.r_ahora)]}, hay(a.r_ahora) ? conSigno(a.r_ahora, 2, " R") : "—")),
        carril(a),
        h("div", {clase: "agua-pie"},
          pasado !== null ? h("div", {clase: "agua-reloj", title: "Tiempo consumido de su duración máxima"},
            h("div", {clase: "agua-reloj-lleno", estilo: {width: `${(pasado * 100).toFixed(1)}%`}})) : null,
          h("span", {clase: "muy-tenue"}, (hay(a.limite_ts) ? `le quedan ${duracion(a.limite_ts - ahora)} · ` : "")
            + (hay(a.px_ts) ? `precio: último cierre de 1 h, ${hace(a.px_ts, ahora)}` : "sin precio archivado aún"))));
    })) : vacio("Ahora mismo no hay ninguna sombra abierta."),
    vivas.length ? h("p", {clase: "muy-tenue"}, "La barra va del stop al objetivo final; la marca hueca es lo mejor que llegó a ir. "
      + "La R de ahora es aproximada (último cierre de 1 h, sin comisiones); la definitiva la da la simulación al cerrar.") : null);
}

// ---------------------------------------------------------------- ¿acertó al descartar?
function seccionMotivos() {
  const lista = (datos.por_motivo || []).filter((m) => m.n);
  const maxAbs = Math.max(0.1, ...lista.map((m) => Math.abs(m.r_medio || 0)));
  const fallan = lista.filter((m) => m.lectura === "falla");
  const aciertan = lista.filter((m) => m.lectura === "acierta");
  return h("section", {clase: "seccion"},
    h("h2", {}, "¿Acertó al descartar?"),
    h("p", {clase: "muy-tenue"}, "Cada motivo de descarte, juzgado por lo que hicieron después sus sombras. "
      + "Si lo descartado perdía, el motivo acertó; si ganaba, dejó pasar dinero."),
    h("div", {clase: "desc-eje muy-tenue"}, h("span", {}, "← lo descartado perdía"), h("span", {}, "lo descartado ganaba →")),
    h("ul", {clase: "descartes"}, lista.map((m) => {
      const ancho = `${(Math.abs(m.r_medio || 0) / maxAbs * 50).toFixed(2)}%`;
      const neg = (m.r_medio || 0) < 0;
      const [txt, clase] = LECTURA[m.lectura] || ["", null];
      return h("li", {clase: ["desc", m.lectura]},
        h("div", {clase: "desc-texto"}, h("div", {clase: "titulo"}, m.etiqueta),
          h("div", {clase: "muy-tenue"}, `${m.n} casos · gana el ${num(m.ganan_pct, 0)} %${hay(m.t) ? ` · t = ${num(m.t, 1)}` : ""}`)),
        h("div", {clase: "desc-barra", title: m.explica},
          h("div", {clase: "desc-cero"}),
          h("div", {clase: ["desc-relleno", neg ? "pierde" : "gana"], estilo: neg ? {right: "50%", width: ancho} : {left: "50%", width: ancho}}),
          h("span", {clase: ["desc-valor", neg ? "izq" : "der"], estilo: neg ? {right: `calc(50% + ${ancho} + 6px)`} : {left: `calc(50% + ${ancho} + 6px)`}},
            conSigno(m.r_medio, 2, " R"))),
        chip(txt, clase, {titulo: m.texto}));
    })),
    fallan.length || aciertan.length ? h("div", {clase: "desc-lectura"},
      aciertan.map((m) => h("p", {}, h("b", {}, m.etiqueta), `: acierta. Lo que descarta da ${conSigno(m.r_medio, 2, " R")} de media en ${m.n} casos.`)),
      fallan.map((m) => h("p", {}, h("b", {}, m.etiqueta), `: lo que descarta habría ganado ${conSigno(m.r_medio, 2, " R")} de media en ${m.n} casos.`
        + (m.clave === "riesgo" ? " Ojo: es un límite de riesgo; protege la cuenta, no elige operaciones, así que esto no basta para quitarlo." : "")
        + (m.clave === "apagada" ? " Son estrategias que has apagado: mira sus estelas abajo." : "")))) : null);
}

// ---------------------------------------------------------------- estelas por estrategia
function estela(curva) {
  const ancho = 200, alto = 54;
  const s = svg("svg", {viewBox: `0 0 ${ancho} ${alto}`, preserveAspectRatio: "none", class: "estela-svg", "aria-hidden": "true"});
  if (!curva || curva.length < 2) return s;
  const vs = curva.map((p) => p[1]).concat([0]);
  const lo = Math.min(...vs), hi = Math.max(...vs), rango = hi - lo || 1;
  const t0 = curva[0][0], t1 = curva[curva.length - 1][0] || t0 + 1;
  const px = (t) => ((t - t0) / (t1 - t0 || 1)) * ancho, py = (v) => alto - 3 - ((v - lo) / rango) * (alto - 6);
  const d = curva.map((p, i) => `${i ? "L" : "M"}${px(p[0]).toFixed(1)} ${py(p[1]).toFixed(1)}`).join(" ");
  const fin = curva[curva.length - 1][1];
  s.append(svg("line", {x1: 0, x2: ancho, y1: py(0), y2: py(0), class: "estela-cero"}),
    svg("path", {d: `${d} L${ancho} ${py(0).toFixed(1)} L0 ${py(0).toFixed(1)} Z`, class: `estela-area ${fin >= 0 ? "gana" : "pierde"}`}),
    svg("path", {d, class: `estela-linea ${fin >= 0 ? "gana" : "pierde"}`}));
  return s;
}

function seccionEstelas() {
  const lista = datos.estrategias || [];
  return h("section", {clase: "seccion"},
    h("h2", {}, "La estela de cada estrategia"),
    h("p", {clase: "muy-tenue"}, "R acumulada de sus sombras ya cerradas, de la primera a la última. Pulsa una para verla en el sónar."),
    lista.length ? h("div", {clase: "estelas"}, lista.map((e) => {
      const [txt, clase] = ESTADO[e.estado] || ESTADO.desconocido;
      return h("button", {type: "button", clase: ["estela", e.aviso ? "con-aviso" : null, foco === e.clave ? "activa" : null],
        onClick: () => { foco = e.clave; filtro = "todas"; pintarSonar(); sonarVivo?.caja.scrollIntoView({behavior: QUIETO ? "auto" : "smooth", block: "center"}); }},
        h("div", {clase: "estela-cab"}, h("span", {clase: "estela-nombre"}, nombre(e.clave)), chip(txt, clase)),
        estela(e.curva),
        h("div", {clase: "estela-cifras"},
          h("span", {clase: ["estela-r", claseR(e.r_medio)]}, hay(e.r_medio) ? conSigno(e.r_medio, 2, " R") : "—"),
          h("span", {clase: "muy-tenue"}, `${e.n} cerradas${e.abiertas ? ` · ${e.abiertas} en el agua` : ""}`
            + (hay(e.ganan_pct) ? ` · gana el ${num(e.ganan_pct, 0)} %` : "") + (hay(e.t) ? ` · t ${num(e.t, 1)}` : ""))),
        e.aviso ? h("div", {clase: "estela-aviso"}, e.aviso) : null);
    })) : vacio("Aún no hay sombras."));
}

// ---------------------------------------------------------------- vista
function pintar() {
  const desde = datos.desde ? new Date(datos.desde * 1000).toLocaleDateString("es-ES") : null;
  reemplazar(raiz,
    h("div", {clase: "titulo-vista"}, h("div", {},
      h("h1", {}, "Sónar de sombras"),
      h("p", {}, "Lo que el bot vio pasar y dejó ir: cada señal descartada, seguida en papel con precios reales."))),
    balanza(),
    seccionSonar(),
    seccionAgua(),
    seccionMotivos(),
    seccionEstelas(),
    h("p", {clase: "muy-tenue"}, `${datos.nota} Desde ${desde ? `la última puesta a cero (${desde})` : "el principio"}. `
      + "Solo informa: nada de esta vista decide ni activa estrategias; para operar, una estrategia tiene que superar el laboratorio."
      + (datos.recortados ? ` Se dibujan las ${datos.puntos.length} más recientes.` : "")));
  pintarSonar();
  observador?.disconnect();
  if (window.ResizeObserver && sonarVivo) {
    let ancho = sonarVivo.caja.clientWidth;
    observador = new ResizeObserver(() => {
      const a = sonarVivo?.caja.clientWidth || 0;
      if (Math.abs(a - ancho) > 30) { ancho = a; montarSonar(sonarVivo.caja, sonarVivo.ficha); }
    });
    observador.observe(sonarVivo.caja);
  }
}

async function cargar() {
  datos = await obtener("/api/sombras");
  cargado = Date.now();
}

export const vista = {
  async entrar(el) {
    raiz = el;
    reemplazar(el, h("p", {clase: "cargando"}, "Escuchando el sónar…"));
    try {
      await cargar();
    } catch (e) {
      reemplazar(el, errorCarga(`No se pudieron leer las sombras: ${e.message}`));
      return;
    }
    if (datos.error) { reemplazar(el, errorCarga(datos.error)); return; }
    pintar();
  },
  async actualizar() {                       // el sondeo general llega cada pocos segundos: aquí basta cada 2 min
    if (!raiz || Date.now() - cargado < 120000) return;
    try { await cargar(); } catch { return; }
    if (raiz) pintar();
  },
  salir() {
    raiz = null; sonarVivo = null;
    observador?.disconnect();
  },
};
