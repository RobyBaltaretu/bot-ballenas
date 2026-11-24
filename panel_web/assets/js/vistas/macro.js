// PARTE DEL MAR: las citas macro de EE. UU. (decisiones de la Fed e IPC) como tormentas que se acercan por el horizonte.
// No es un calendario: el mar se encrespa cerca de cada cita, la lluvia marca la ventana en la que el estudio mira si
// conviene no abrir, y las estelas de las operaciones abiertas muestran si van a cruzar alguna. Debajo, la huella real
// que dejaron las últimas en BTC (velas que el bot ya archiva). Solo informa: el bot no usa este calendario para decidir.
// Todo el SVG se construye con createElementNS y atributos; los colores van por clases (CSP estricta, sin estilos en línea).

import {obtener} from "../api.js";
import {errorCarga, h, reemplazar, vacio} from "../dom.js";
import {bot} from "../estado.js";
import {conSigno, hay, num} from "../formato.js";
import {svg} from "../grafico.js";

const TIPO = {
  fomc: {corto: "Fed", nombre: "Decisión de tipos de la Fed (FOMC)", pico: 1, clase: "fomc",
    dice: "La Reserva Federal publica su decisión de tipos y después habla su presidente. Suele mover todo el mercado."},
  cpi: {corto: "IPC", nombre: "Inflación de EE. UU. (IPC)", pico: 0.7, clase: "cpi",
    dice: "Se publica el IPC de EE. UU. Una sorpresa en la inflación cambia lo que se espera de la Fed."},
};
const HORIZONTES = [[14, "2 semanas"], [35, "5 semanas"], [60, "2 meses"]];
const DIA = 86400;
const QUIETO = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const F_DIA = new Intl.DateTimeFormat("es-ES", {weekday: "short", day: "2-digit", month: "2-digit"});
const F_HORA = new Intl.DateTimeFormat("es-ES", {hour: "2-digit", minute: "2-digit"});
const F_ETQ = new Intl.DateTimeFormat("es-ES", {day: "numeric", month: "short"});

let raiz = null, datos = null, horizonte = 35, animacion = null, reloj = null, observador = null, escena = null;

const ahoraS = () => Date.now() / 1000;
const diaHora = (ts) => `${F_DIA.format(new Date(ts * 1000))} · ${F_HORA.format(new Date(ts * 1000))}`;

function cuenta(seg) {
  const s = Math.max(0, Math.floor(seg));
  const d = Math.floor(s / DIA), hh = Math.floor((s % DIA) / 3600), mm = Math.floor((s % 3600) / 60), ss = s % 60;
  return d ? `${d} d ${hh} h ${String(mm).padStart(2, "0")} min` : `${hh} h ${String(mm).padStart(2, "0")} min ${String(ss).padStart(2, "0")} s`;
}

/** Estado del mar ahora: tormenta (dentro de la ventana), mar de fondo (< 72 h) o calma. */
function estadoMar(ahora) {
  const {antes, despues} = datos.ventana_h;
  const prox = (datos.proximas || []).filter((e) => e.ts + despues * 3600 >= ahora);
  const dentro = prox.find((e) => ahora >= e.ts - antes * 3600);
  const siguiente = prox.find((e) => e.ts >= ahora) || null;
  if (dentro) return {clave: "tormenta", titulo: "Tormenta", evento: dentro,
    texto: ahora < dentro.ts ? `Estás dentro de la ventana de ${TIPO[dentro.tipo].corto}: faltan ${cuenta(dentro.ts - ahora)} para la cita.`
      : `${TIPO[dentro.tipo].corto} acaba de salir. La ventana se cierra en ${cuenta(dentro.ts + despues * 3600 - ahora)}.`};
  if (siguiente && siguiente.ts - ahora < 72 * 3600) return {clave: "fondo", titulo: "Mar de fondo", evento: siguiente,
    texto: `${TIPO[siguiente.tipo].nombre} en menos de 3 días. La ventana empieza ${antes} h antes.`};
  return {clave: "calma", titulo: "Calma", evento: siguiente,
    texto: siguiente ? `Nada a la vista en los próximos 3 días.` : "No hay citas cargadas en el calendario."};
}

// ---------------------------------------------------------------- horizonte
function escenaHorizonte(contenedor) {
  const ancho = Math.max(320, Math.round(contenedor.clientWidth || 800));
  const alto = ancho < 560 ? 270 : 300;
  const agua = alto * 0.6;
  const margen = 46;
  const ahora = ahoraS();
  const t1 = ahora + horizonte * DIA;
  const x = (t) => margen + (t - ahora) / (t1 - ahora) * (ancho - margen - 14);
  const {antes, despues} = datos.ventana_h;
  const eventos = (datos.proximas || []).filter((e) => e.ts + despues * 3600 >= ahora && e.ts - antes * 3600 <= t1);
  const raizSvg = svg("svg", {viewBox: `0 0 ${ancho} ${alto}`, width: ancho, height: alto, class: "mar-svg", role: "img",
    "aria-label": `Horizonte de ${horizonte} días con ${eventos.length} citas macro`});
  const defs = svg("defs", {});
  const cielo = svg("linearGradient", {id: "mar-cielo", x1: 0, y1: 0, x2: 0, y2: 1});
  cielo.append(svg("stop", {offset: "0", class: "cielo-a"}), svg("stop", {offset: "1", class: "cielo-b"}));
  const hondo = svg("linearGradient", {id: "mar-hondo", x1: 0, y1: 0, x2: 0, y2: 1});
  hondo.append(svg("stop", {offset: "0", class: "hondo-a"}), svg("stop", {offset: "1", class: "hondo-b"}));
  defs.append(cielo, hondo);
  raizSvg.append(defs, svg("rect", {x: 0, y: 0, width: ancho, height: agua + 4, fill: "url(#mar-cielo)"}));

  // Estrellas fijas (semilla fija: siempre las mismas) y franjas de días.
  let semilla = 7;
  const azar = () => ((semilla = (semilla * 9301 + 49297) % 233280) / 233280);
  for (let i = 0; i < Math.round(ancho / 22); i++) {
    raizSvg.append(svg("circle", {cx: azar() * ancho, cy: azar() * agua * 0.55, r: azar() < 0.15 ? 1.3 : 0.7, class: "mar-estrella"}));
  }
  const capaEtq = svg("g", {});
  const paso = horizonte <= 14 ? 1 : horizonte <= 35 ? 7 : 14;
  const d0 = new Date(ahora * 1000); d0.setHours(0, 0, 0, 0);
  for (let t = d0.getTime() / 1000 + DIA; t < t1; t += DIA) {
    const finde = [0, 6].includes(new Date(t * 1000).getDay());
    raizSvg.append(svg("line", {x1: x(t), x2: x(t), y1: agua - 6, y2: agua + 4, class: finde ? "mar-dia finde" : "mar-dia"}));
    const nDia = Math.round((t - d0.getTime() / 1000) / DIA);
    if (nDia % paso === 0) {
      const et = svg("text", {x: x(t), y: alto - 10, class: "mar-etq-dia", "text-anchor": "middle"});
      et.textContent = F_ETQ.format(new Date(t * 1000));
      capaEtq.append(et);
    }
  }

  // Tormentas: ventana de lluvia (de «antes» a «después»), nube y, en la Fed, rayo.
  const capaLluvia = svg("g", {class: "mar-lluvia"});
  const capaNubes = svg("g", {});
  const colocadas = [];
  for (const e of eventos) {
    const tp = TIPO[e.tipo];
    const nivel = colocadas.filter((xc) => Math.abs(xc - x(e.ts)) < 110).length;
    colocadas.push(x(e.ts));
    const xa = Math.max(margen, x(e.ts - antes * 3600)), xb = Math.min(ancho - 4, x(e.ts + despues * 3600)), xe = x(e.ts);
    const nubeY = 56 + nivel * 46;
    capaLluvia.append(svg("rect", {x: xa, y: nubeY + 10, width: Math.max(2, xb - xa), height: agua - nubeY - 10, class: `mar-ventana ${tp.clase}`}));
    for (let lx = xa + 3; lx < xb; lx += 7) {
      capaLluvia.append(svg("line", {x1: lx, x2: lx - 4, y1: nubeY + 16, y2: agua - 4, class: `mar-gota ${tp.clase}`}));
    }
    const nube = svg("g", {class: `mar-nube ${tp.clase}`, tabindex: "0", "aria-label": `${tp.nombre}: ${diaHora(e.ts)}`});
    const r = 13 * (0.75 + tp.pico * 0.35);
    for (const [dx, dy, k] of [[-1.3, 0.35, 0.8], [-0.4, -0.25, 1.1], [0.6, 0, 0.95], [1.4, 0.4, 0.7]]) {
      nube.append(svg("circle", {cx: xe + dx * r, cy: nubeY + dy * r, r: r * k}));
    }
    nube.append(svg("rect", {x: xe - 2 * r, y: nubeY + 0.3 * r, width: 4 * r, height: 0.75 * r, rx: 0.37 * r}));
    if (e.tipo === "fomc") {
      const yb = nubeY + r;
      raizSvg.append(svg("polyline", {points: `${xe + 3},${yb} ${xe - 7},${yb + 26} ${xe + 2},${yb + 26} ${xe - 6},${agua - 8}`, class: "mar-rayo"}));
    }
    const etq = svg("text", {x: nivel ? xe + 2 * r + 6 : xe, y: nivel ? nubeY + 4 : nubeY - r - 8, class: `mar-etq ${tp.clase}`,
      "text-anchor": nivel ? "start" : "middle"});
    etq.textContent = `${tp.corto} · ${F_ETQ.format(new Date(e.ts * 1000))}`;
    const titulo = svg("title", {});
    titulo.textContent = `${tp.nombre}\n${diaHora(e.ts)} (tu hora)\nVentana: de ${antes} h antes a ${despues} h después`;
    nube.append(titulo);
    capaNubes.append(nube, etq);
  }
  raizSvg.append(capaLluvia, capaNubes);

  // Mar: tres capas cuya altura de ola crece cerca de cada cita.
  const picos = eventos.map((e) => ({x: x(e.ts), k: TIPO[e.tipo].pico}));
  const sigma = Math.max(22, (ancho - margen) / horizonte * 1.4);
  const amp = (px) => 2.2 + picos.reduce((a, p) => a + p.k * 26 * Math.exp(-(((px - p.x) / sigma) ** 2)), 0);
  const capas = [[0, 0.035, 1, "c1"], [10, 0.05, 0.7, "c2"], [20, 0.028, 0.45, "c3"]].map(([dy, f, k, c]) => {
    const p = svg("path", c === "c3" ? {class: `mar-ola ${c}`, fill: "url(#mar-hondo)"} : {class: `mar-ola ${c}`});
    raizSvg.append(p);
    return {p, dy, f, k};
  });

  // Estelas de las operaciones abiertas: de ahora a su fin previsto, bajo el agua, como un sonar.
  const capaEstelas = svg("g", {class: "mar-estelas"});
  raizSvg.append(capaEstelas);

  // La ballena (el bot) en el punto «ahora».
  const ballena = svg("g", {class: "mar-ballena"});
  ballena.append(svg("path", {d: "M3 15c2.5-5 7.5-7 12.5-5.5 2.2.7 3.8 2 5.5 1.3-.8 3.4-4 5.2-7.4 5.2H9l-3.2 2.5.8-3.5z"}));
  const hoy = svg("text", {x: margen, y: alto - 10, class: "mar-etq-dia hoy", "text-anchor": "middle"});
  hoy.textContent = "hoy";
  capaEtq.append(hoy);
  raizSvg.append(svg("line", {x1: margen, x2: margen, y1: 20, y2: alto - 26, class: "mar-ahora"}), ballena, capaEtq);

  function pintarOlas(fase) {
    for (const c of capas) {
      let d = "";
      for (let px = 0; px <= ancho; px += 4) {
        const y = agua + c.dy + Math.sin(px * c.f + fase * (1 + c.dy / 25)) * amp(px) * c.k
          + Math.sin(px * c.f * 2.3 - fase * 0.7) * amp(px) * 0.25 * c.k;
        d += (px ? " L" : "M") + px + " " + y.toFixed(1);
      }
      c.p.setAttribute("d", `${d} L${ancho} ${alto} L0 ${alto} Z`);
    }
    const yb = agua + Math.sin(margen * 0.035 + fase) * amp(margen) - 20;
    ballena.setAttribute("transform", `translate(${margen - 24} ${(yb - 8).toFixed(1)}) scale(2)`);
  }

  function pintarEstelas() {
    capaEstelas.replaceChildren();
    const pos = bot().posiciones || [];
    const ahora2 = ahoraS();
    pos.slice(0, 6).forEach((p, i) => {
      const ini = Number(p.abierta_ts) || ahora2;
      const fin = p.limite_ts ? Number(p.limite_ts) : ini + (Number(p.duracion_estrategia_min) || 0) * 60;
      const y = agua + 40 + i * 19;
      if (y > alto - 30) return;
      const xb = Math.min(ancho - 6, x(Math.max(fin, ahora2 + 3600)));
      const cruza = eventos.find((e) => e.ts - antes * 3600 < fin && e.ts + despues * 3600 > ahora2);
      capaEstelas.append(svg("line", {x1: margen + 6, x2: xb, y1: y, y2: y, class: cruza ? "mar-estela cruza" : "mar-estela"}),
        svg("circle", {cx: xb, cy: y, r: 2.5, class: cruza ? "mar-estela-fin cruza" : "mar-estela-fin"}));
      const t = svg("text", {x: margen + 10, y: y - 3, class: "mar-etq-estela"});
      t.textContent = `${p.moneda} ${p.lado === "S" ? "corto" : "largo"}${cruza ? ` · cruzará ${TIPO[cruza.tipo].corto}` : ""}`;
      capaEstelas.append(t);
    });
  }

  pintarOlas(0);
  pintarEstelas();
  return {raizSvg, pintarOlas, pintarEstelas};
}

function montarHorizonte(caja) {
  if (animacion) cancelAnimationFrame(animacion);
  escena = escenaHorizonte(caja);
  reemplazar(caja, escena.raizSvg);
  if (QUIETO) return;
  const t0 = performance.now();
  const paso = (t) => {
    if (!escena) return;
    escena.pintarOlas((t - t0) / 1400);
    animacion = requestAnimationFrame(paso);
  };
  animacion = requestAnimationFrame(paso);
}

// ---------------------------------------------------------------- huella de las olas pasadas
function miniOla(p, normal) {
  const o = p.ola;
  const tp = TIPO[p.tipo];
  const W = 240, H = 92;
  const serie = o.serie;
  const ys = serie.map((s) => s[1]);
  const lim = Math.max(0.6, ...ys.map(Math.abs)) * 1.15;
  const sx = (hh) => 6 + (hh + 12) / 24 * (W - 12);
  const sy = (v) => H / 2 - v / lim * (H / 2 - 8);
  const {antes, despues} = datos.ventana_h;
  const g = svg("svg", {viewBox: `0 0 ${W} ${H}`, class: "ola-mini", role: "img",
    "aria-label": `BTC alrededor de ${tp.nombre} del ${p.fecha}: ${conSigno(o.mov_4h_pct, 1)} % en 4 h`});
  g.append(svg("rect", {x: sx(-antes), y: 0, width: sx(despues) - sx(-antes), height: H, class: `ola-ventana ${tp.clase}`}),
    svg("line", {x1: 0, x2: W, y1: sy(0), y2: sy(0), class: "ola-cero"}),
    svg("line", {x1: sx(0), x2: sx(0), y1: 4, y2: H - 4, class: `ola-cita ${tp.clase}`}));
  const d = serie.map((s, i) => `${i ? "L" : "M"}${sx(s[0]).toFixed(1)} ${sy(s[1]).toFixed(1)}`).join(" ");
  g.append(svg("path", {d, class: o.mov_4h_pct >= 0 ? "ola-linea sube" : "ola-linea baja"}));
  const veces = hay(normal) && normal > 0 ? o.rango_4h_pct / normal : null;
  return h("div", {clase: ["ola-tarjeta", tp.clase]},
    h("div", {clase: "ola-cab"}, h("span", {clase: ["ola-tipo", tp.clase]}, tp.corto), h("span", {clase: "tenue"}, F_DIA.format(new Date(p.ts * 1000)))),
    g,
    h("div", {clase: "ola-pie"}, h("b", {}, `${conSigno(o.mov_4h_pct, 1)} %`), " en 4 h · oleaje ",
      h("b", {}, `${num(o.rango_4h_pct, 1)} %`), veces ? h("span", {clase: veces >= 1.5 ? "ola-veces alto" : "ola-veces"}, ` (${num(veces, 1)}× lo normal)`) : null));
}

// ---------------------------------------------------------------- vista
function pintar() {
  const ahora = ahoraS();
  const mar = estadoMar(ahora);
  const sig = mar.evento;
  const cuentaAtras = h("span", {clase: "mar-cuenta", "aria-live": "off"}, sig ? cuenta(sig.ts - ahora) : "—");
  const caja = h("div", {clase: "mar-horizonte"});
  const selector = h("div", {clase: "mar-horizontes", role: "group", "aria-label": "Distancia del horizonte"},
    HORIZONTES.map(([d, t]) => h("button", {type: "button", clase: d === horizonte ? "activo" : null, "aria-pressed": d === horizonte ? "true" : "false",
      onClick: () => { horizonte = d; pintar(); }}, t)));
  const {antes, despues} = datos.ventana_h;
  const prox = (datos.proximas || []).filter((e) => e.ts + despues * 3600 >= ahora);
  const pasadas = (datos.pasadas || []).filter((p) => p.ola).reverse();
  const sinOla = (datos.pasadas || []).length - pasadas.length;
  const est = datos.estudio;
  const vivo = datos.en_vivo || {};

  reemplazar(raiz,
    h("div", {clase: "titulo-vista"}, h("div", {}, h("h1", {}, "Parte del mar"),
      h("p", {}, "Las citas macro de EE. UU. que mueven las cripto, como tormentas que se acercan por el horizonte."))),
    h("section", {clase: ["mar-parte", mar.clave]},
      h("div", {clase: "mar-estado"},
        h("div", {clase: "mar-etq-estado"}, "Estado del mar"),
        h("div", {clase: "mar-titulo-estado"}, mar.titulo),
        h("p", {}, mar.texto)),
      sig ? h("div", {clase: "mar-proxima"},
        h("div", {clase: "mar-etq-estado"}, "Próxima tormenta"),
        h("div", {clase: ["mar-prox-nombre", TIPO[sig.tipo].clase]}, TIPO[sig.tipo].nombre),
        h("div", {}, diaHora(sig.ts), h("span", {clase: "tenue"}, " (tu hora)")),
        h("div", {}, "Faltan ", cuentaAtras)) : null),
    h("section", {clase: "seccion"}, h("div", {clase: "mar-cab-horizonte"}, h("h2", {}, "El horizonte"), selector),
      caja,
      h("p", {clase: "muy-tenue"}, `La lluvia marca la ventana que mira el estudio: de ${antes} h antes a ${despues} h después de cada cita. `
        + "El mar se encrespa al acercarse y el rayo es una decisión de la Fed. Bajo el agua, las estelas de tus operaciones abiertas hasta su "
        + "fin previsto; en ámbar, las que van a cruzar una tormenta. Pasa el ratón por una nube para ver la hora exacta.")),
    h("section", {clase: "seccion"}, h("h2", {}, "Boletín"),
      prox.length ? h("ol", {clase: "mar-boletin"}, prox.slice(0, 6).map((e) => {
        const tp = TIPO[e.tipo];
        return h("li", {clase: tp.clase},
          h("span", {clase: ["mar-bol-icono", tp.clase], "aria-hidden": "true"}),
          h("div", {}, h("div", {clase: "titulo"}, tp.nombre),
            h("div", {clase: "sub"}, `${diaHora(e.ts)} · ventana de ${F_HORA.format(new Date((e.ts - antes * 3600) * 1000))} a ${F_HORA.format(new Date((e.ts + despues * 3600) * 1000))}`),
            h("div", {clase: "sub tenue"}, tp.dice)),
          h("div", {clase: "mar-bol-falta"}, e.ts > ahora ? `en ${cuenta(e.ts - ahora).split(" ").slice(0, 4).join(" ")}` : "ahora"));
      })) : vacio("No hay citas cargadas para las próximas semanas.")),
    h("section", {clase: "seccion"}, h("h2", {}, "La huella de las últimas tormentas"),
      h("p", {clase: "muy-tenue"}, `BTC de 12 h antes a 12 h después de cada cita, frente al cierre justo antes. «Oleaje» = recorrido entre máximo y mínimo en las 4 h siguientes; `
        + (hay(datos.oleaje_normal_4h_pct) ? `en 4 h cualesquiera, lo normal es ${num(datos.oleaje_normal_4h_pct, 1)} % (mediana).` : "")),
      pasadas.length ? h("div", {clase: "olas-rejilla"}, pasadas.map((p) => miniOla(p, datos.oleaje_normal_4h_pct)))
        : vacio("Aún no hay velas archivadas de BTC alrededor de ninguna cita."),
      sinOla ? h("p", {clase: "muy-tenue"}, `${sinOla} cita(s) anteriores sin dibujar: el archivo de velas de 1 h del bot aún no llega tan atrás (${datos.velas_btc} velas).`) : null,
      pasadas.length < 8 ? h("p", {clase: "muy-tenue"}, "Con tan pocas tormentas esto es una foto, no una regla.") : null),
    h("section", {clase: "seccion"}, h("h2", {}, "¿Conviene apartarse de las tormentas?"),
      h("div", {clase: "mar-veredicto"},
        h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "Estudio con la historia (fuera de muestra)"),
          est ? [h("p", {}, est.lectura || "—"),
            h("p", {clase: "muy-tenue"}, `${est.pares ?? 0} pares disparador × intervalo · mejora en ${est.mejora_en ?? 0}`
              + (hay(est.r_medio_cerca) ? ` · las abiertas cerca de una cita: ${conSigno(est.r_medio_cerca, 3)} R de media (${est.n_cerca})` : "")
              + ` · ${est.citas ?? "—"} citas · ${(est.fecha || "").slice(0, 10)}`)]
            : h("p", {}, "En marcha o aún sin hacer. Hipótesis fijada antes de mirar: no abrir de 12 h antes a 2 h después mejora el R medio.")),
        h("div", {clase: "tarjeta"}, h("div", {clase: "etiqueta"}, "Lo que llevan tus operaciones"),
          h("p", {}, `Abiertas cerca de una cita: ${vivo.cerca?.n ?? 0}${hay(vivo.cerca?.r_medio) ? ` (${conSigno(vivo.cerca.r_medio, 2)} R de media)` : ""}. `
            + `Lejos: ${vivo.lejos?.n ?? 0}${hay(vivo.lejos?.r_medio) ? ` (${conSigno(vivo.lejos.r_medio, 2)} R)` : ""}.`),
          h("p", {clase: "muy-tenue"}, "Con menos de 30 en cada grupo no dice nada."))),
      h("p", {clase: "muy-tenue"}, "Solo informa: el bot NO usa este calendario para decidir. Para que filtrara entradas tendría que superar antes el laboratorio. "
        + `Fechas oficiales: ${datos.fuente}.`)));

  montarHorizonte(caja);
  observador?.disconnect();
  if (window.ResizeObserver) {
    let ancho = caja.clientWidth;
    observador = new ResizeObserver(() => { if (Math.abs(caja.clientWidth - ancho) > 30) { ancho = caja.clientWidth; montarHorizonte(caja); } });
    observador.observe(caja);
  }
  clearInterval(reloj);
  reloj = setInterval(() => {
    if (!raiz || !sig) return;
    const falta = sig.ts - ahoraS();
    cuentaAtras.textContent = cuenta(falta);
    if (falta < -datos.ventana_h.despues * 3600) pintar();     // pasó la tormenta: se redibuja todo
  }, 1000);
}

export const vista = {
  async entrar(el) {
    raiz = el;
    reemplazar(el, h("p", {clase: "cargando"}, "Leyendo el parte…"));
    try {
      datos = await obtener("/api/macro");
    } catch (e) {
      reemplazar(el, errorCarga(`No se pudo leer el calendario: ${e.message}`));
      return;
    }
    if (datos.error) { reemplazar(el, errorCarga(datos.error)); return; }
    pintar();
  },
  actualizar() { escena?.pintarEstelas(); },
  salir() {
    raiz = null; escena = null;
    if (animacion) cancelAnimationFrame(animacion);
    clearInterval(reloj);
    observador?.disconnect();
  },
};
