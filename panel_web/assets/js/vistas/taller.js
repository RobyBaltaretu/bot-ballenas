// TALLER (18/11/2026): revisión de todo el sistema en un vistazo, con luces de estado, órdenes de trabajo y arreglos
// seguros que se COMPRUEBAN después. Los datos salen de /api/taller (taller.py, solo lectura). Un arreglo es siempre un
// comando que el bot ya tenía y que no toca dinero, límites ni modo; el panel solo envía los de PERMITIDOS y el
// servidor los vuelve a filtrar (y solo desde este equipo). Lo que debe hacer una persona se explica paso a paso.

import {SOLO_LECTURA, enviar, esperarResultado, obtener} from "../api.js";
import {chip, errorCarga, h, reemplazar, seccion, vacio} from "../dom.js";
import {hace} from "../formato.js";
import {abrirDialogo, ayuda} from "../info.js";

const PERMITIDOS = ["/reanudar", "/aplicarconfig", "/laboratorio", "/investigacion"];
const NOMBRE_ESTADO = {ok: "En orden", aviso: "Revisar", mal: "Falla", desconocido: "Sin comprobar", pendiente: "Pendiente tuyo"};
const ICONO = {ok: "✓", aviso: "!", mal: "✕", desconocido: "?", pendiente: "○"};

const s = {datos: null, error: null, raiz: null, zona: null, libro: [], trabajando: new Set(), timer: null, previo: null, hechos: {}};

function led(estado, extra) {
  return h("span", {clase: ["led", `e-${estado}`, extra || null], role: "img", "aria-label": NOMBRE_ESTADO[estado] || estado}, ICONO[estado] || "");
}

function todos() {
  return (s.datos?.grupos || []).flatMap((g) => g.checks);
}

function anotar(texto, clase) {
  s.libro.unshift({ts: Date.now() / 1000, texto, clase: clase || null});
  s.libro.length = Math.min(s.libro.length, 30);
}

/** Cambios entre dos revisiones: se apuntan solos en el libro del taller. */
function comparar(antes, despues) {
  if (!antes) return;
  const viejo = Object.fromEntries(antes.map((c) => [c.id, c.estado]));
  for (const c of despues) {
    const e = viejo[c.id];
    if (e && e !== c.estado) {
      const mejor = ["ok", "pendiente"].includes(c.estado) && !["ok", "pendiente"].includes(e);
      anotar(`${c.titulo}: ${NOMBRE_ESTADO[e]} → ${NOMBRE_ESTADO[c.estado]}`, mejor ? "e-ok" : c.estado === "ok" ? null : "e-aviso");
    }
  }
}

async function revisar({silencioso = false} = {}) {
  if (!silencioso && s.zona) s.zona.classList.add("revisando");
  try {
    const d = await obtener("/api/taller");
    comparar(s.previo, d.grupos.flatMap((g) => g.checks));
    s.datos = d;
    s.previo = d.grupos.flatMap((g) => g.checks);
    s.error = null;
  } catch (e) {
    s.error = e.message;
  }
  s.zona?.classList.remove("revisando");
  pintar();
  return s.datos;
}

// ---------------------------------------------------------------- arreglar y comprobar
async function arreglar(chk) {
  const a = chk.arreglo;
  if (!a || !PERMITIDOS.includes(a.cmd) || s.trabajando.has(chk.id)) return;
  s.trabajando.add(chk.id);
  s.hechos[chk.id] = {paso: "Enviando la orden al bot…"};
  pintar();
  const fin = (texto, clase) => {
    s.trabajando.delete(chk.id);
    s.hechos[chk.id] = {fin: texto, clase, ts: Date.now()};
    anotar(`${a.etiqueta}: ${texto}`, clase);
    pintar();
    setTimeout(pintar, 25000);                       // la tarjeta resuelta se queda unos segundos y luego se retira
  };
  const r = await enviar("/api/comando", {cmd: a.cmd});
  if (!r.ok) return fin(`no se pudo (${r.error || "error"})`, "e-mal");
  s.hechos[chk.id] = {paso: "El bot la ha recibido; esperando su confirmación…"};
  pintar();
  const res = await esperarResultado(r.id, {intentos: 20, cada: 1500});
  if (res.pendiente) return fin("el bot no ha confirmado (¿está en marcha?)", "e-aviso");
  if (res.ok === false) return fin(`el bot la rechazó: ${res.mensaje || ""}`, "e-mal");
  s.hechos[chk.id] = {paso: "Hecho. Comprobando que funciona…"};
  pintar();
  // Un reinicio tarda unos segundos: se vuelve a revisar hasta que esa comprobación esté en orden (máx. 90 s).
  const reinicia = a.cmd === "/aplicarconfig";
  const espera = a.cmd === "/laboratorio" || a.cmd === "/investigacion" ? 3 : reinicia ? 14 : 2;
  await new Promise((ok) => setTimeout(ok, espera * 1000));
  for (let i = 0; i < (reinicia ? 12 : 3); i++) {
    await revisar({silencioso: true});
    const ahora = todos().find((x) => x.id === chk.id);
    if (ahora && ["ok", "pendiente"].includes(ahora.estado)) return fin("arreglado y comprobado ✓", "e-ok");
    if (ahora && (a.cmd === "/laboratorio" || a.cmd === "/investigacion") && /marcha/.test(ahora.resumen || "")) return fin("en marcha ✓", "e-ok");
    await new Promise((ok) => setTimeout(ok, 5000));
  }
  fin("hecho, pero la comprobación sigue sin quedar en orden: mira el detalle", "e-aviso");
}

function pedirConfirmacion(chk) {
  const a = chk.arreglo;
  abrirDialogo(a.etiqueta, h("p", {}, a.confirma), h("p", {clase: "muy-tenue"}, "Después se vuelve a revisar solo para comprobar que ha funcionado."),
    h("div", {clase: "acciones"}, h("button", {type: "button", clase: "primario", onClick: () => { document.getElementById("dialogo").close(); arreglar(chk); }}, "Sí, hazlo"),
      h("button", {type: "button", onClick: () => document.getElementById("dialogo").close()}, "Cancelar")));
}

// ---------------------------------------------------------------- piezas
function anillo(d) {
  const ok = (d.cuenta.ok || 0) + (d.cuenta.pendiente || 0);
  const frac = d.total ? ok / d.total : 0;
  const R = 44, C = 2 * Math.PI * R;
  const NS = "http://www.w3.org/2000/svg";
  const sv = document.createElementNS(NS, "svg");
  sv.setAttribute("viewBox", "0 0 100 100");
  sv.setAttribute("class", `anillo e-${d.estado}`);
  sv.setAttribute("aria-hidden", "true");
  for (const [clase, largo] of [["pista", C], ["relleno", C * frac]]) {
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", "50"); c.setAttribute("cy", "50"); c.setAttribute("r", String(R));
    c.setAttribute("class", clase);
    c.setAttribute("stroke-dasharray", `${largo} ${C}`);
    c.setAttribute("transform", "rotate(-90 50 50)");
    sv.append(c);
  }
  return h("div", {clase: "anillo-caja"}, sv, h("div", {clase: "anillo-texto"}, h("b", {}, String(ok)), h("span", {}, `de ${d.total}`)));
}

function cabecera(d) {
  const trabajos = d.trabajos.length;
  const titulo = d.estado === "ok" ? "Todo en orden" : d.estado === "mal" ? "Hay algo que falla" : "Hay cosas que revisar";
  const sub = trabajos ? `${trabajos} ${trabajos === 1 ? "orden de trabajo" : "órdenes de trabajo"} abierta${trabajos === 1 ? "" : "s"}`
    : "No hay nada que arreglar";
  return h("section", {clase: ["taller-cabecera", `e-${d.estado}`], "aria-live": "polite"},
    anillo(d),
    h("div", {clase: "taller-texto"},
      h("div", {clase: "etq"}, "Revisión del taller"),
      h("h2", {}, titulo),
      h("p", {clase: "tenue"}, `${sub} · ${d.pendientes.length ? `${d.pendientes.length} pendiente${d.pendientes.length === 1 ? "" : "s"} tuyo${d.pendientes.length === 1 ? "" : "s"} · ` : ""}revisado ${hace(d.ts)}`)),
    h("div", {clase: "taller-acciones"},
      h("button", {type: "button", clase: "primario", onClick: () => revisar(), disabled: s.zona?.classList.contains("revisando") || null}, "Revisar de nuevo")));
}

/** Planta: el recorrido del dato, de la fuente al almacén, con una luz por cada banco. */
function planta(d) {
  const peor = (g) => g.checks.reduce((p, c) => ({mal: 0, aviso: 1, desconocido: 2, pendiente: 3, ok: 4}[c.estado] < {mal: 0, aviso: 1, desconocido: 2, pendiente: 3, ok: 4}[p] ? c.estado : p), "ok");
  const orden = ["datos", "motor", "proteccion", "cerebro", "almacen"];
  const grupos = orden.map((id) => d.grupos.find((g) => g.id === id)).filter(Boolean);
  return h("nav", {clase: "planta", "aria-label": "Recorrido del dato por el taller"},
    grupos.map((g, k) => [h("a", {clase: ["estacion", `e-${peor(g)}`], href: `#banco-${g.id}`, onClick: (e) => {
      e.preventDefault();
      s.raiz?.querySelector(`#banco-${g.id}`)?.scrollIntoView({behavior: "smooth", block: "start"});
    }}, led(peor(g)), h("span", {}, g.titulo)), k < grupos.length - 1 ? h("span", {clase: "tubo", "aria-hidden": "true"}) : null]));
}

function orden(chk) {
  const hecho = s.hechos[chk.id];
  const ocupado = s.trabajando.has(chk.id);
  const a = chk.arreglo;
  return h("li", {clase: ["orden", `e-${chk.estado}`]},
    led(chk.estado),
    h("div", {clase: "orden-centro"},
      h("div", {clase: "titulo"}, chk.titulo, " ", ayuda(chk.titulo, chk.detalle)),
      h("div", {clase: "tenue"}, chk.resumen),
      chk.pasos.length ? h("ol", {clase: "pasos"}, chk.pasos.map((p) => h("li", {}, p))) : null,
      hecho?.paso ? h("div", {clase: "progreso", role: "status"}, h("span", {clase: "rueda", "aria-hidden": "true"}), hecho.paso) : null,
      hecho?.fin ? h("div", {clase: ["resultado-arreglo", hecho.clase], role: "status"}, hecho.fin) : null),
    a ? h("button", {type: "button", clase: "primario", disabled: SOLO_LECTURA || ocupado || null,
      title: SOLO_LECTURA ? "Los arreglos solo se piden desde este equipo" : null, onClick: () => pedirConfirmacion(chk)}, ocupado ? "Trabajando…" : a.etiqueta) : null);
}

function ordenes(d) {
  const lista = d.trabajos.map((id) => todos().find((c) => c.id === id)).filter(Boolean);
  // Lo que se acaba de arreglar se queda 25 s con su «arreglado y comprobado ✓» antes de desaparecer de la lista.
  const resueltas = Object.entries(s.hechos).filter(([id, x]) => x.fin && Date.now() - x.ts < 25000 && !d.trabajos.includes(id))
    .map(([id]) => todos().find((c) => c.id === id)).filter(Boolean);
  lista.push(...resueltas);
  return seccion(h("span", {}, "Órdenes de trabajo ", ayuda("Órdenes de trabajo",
    "Cada orden es algo que el taller ha encontrado fuera de su sitio, de lo más grave a lo menos.",
    "Si hay un botón, es un arreglo seguro que el bot ya sabe hacer: no toca dinero, límites ni el modo. Después de hacerlo, el taller revisa solo si ha funcionado.",
    "Lo que no tiene botón requiere que lo hagas tú (por ejemplo, poner una clave en .env): se explica paso a paso.")),
  lista.length ? h("ul", {clase: "ordenes"}, lista.map(orden))
    : h("div", {clase: "taller-vacio"}, h("span", {clase: "led e-ok grande"}, "✓"), h("div", {}, h("b", {}, "Nada que arreglar."), h("div", {clase: "tenue"}, "Todas las comprobaciones están en orden o pendientes de ti."))));
}

function pendientes(d) {
  const lista = d.pendientes.map((id) => todos().find((c) => c.id === id)).filter(Boolean);
  if (!lista.length) return null;
  return seccion(h("span", {}, "Pendiente de ti ", ayuda("Pendiente de ti", "No son fallos: son cosas opcionales o que solo puedes hacer tú, como configurar Telegram o la contraseña del panel.")),
    h("ul", {clase: "ordenes"}, lista.map(orden)));
}

function banco(g) {
  const peor = g.checks.some((c) => c.estado === "mal") ? "mal" : g.checks.some((c) => c.estado === "aviso") ? "aviso"
    : g.checks.some((c) => c.estado === "desconocido") ? "desconocido" : "ok";
  const ok = g.checks.filter((c) => ["ok", "pendiente"].includes(c.estado)).length;
  return h("section", {id: `banco-${g.id}`, clase: ["banco", `e-${peor}`]},
    h("header", {}, led(peor), h("div", {}, h("h3", {}, g.titulo), h("p", {clase: "muy-tenue"}, g.texto)), h("span", {clase: "etq"}, `${ok}/${g.checks.length}`)),
    h("ul", {}, g.checks.map((c) => h("li", {clase: `e-${c.estado}`, title: c.resumen}, led(c.estado, "pequeno"),
      h("div", {clase: "fila-check"}, h("span", {clase: "nombre"}, c.titulo, " ", ayuda(c.titulo, c.detalle)), h("span", {clase: "resumen"}, c.resumen))))));
}

function libro() {
  return seccion(h("span", {}, "Libro del taller ", ayuda("Libro del taller", "Lo que ha pasado en esta sesión: arreglos hechos y comprobaciones que han cambiado de estado. Se borra al recargar la página.")),
    s.libro.length ? h("ul", {clase: "libro"}, s.libro.map((x) => h("li", {clase: x.clase || null},
      h("span", {clase: "hora mono"}, new Date(x.ts * 1000).toTimeString().slice(0, 8)), h("span", {}, x.texto))))
      : vacio("Aún no ha pasado nada en esta sesión."),
    h("p", {}, h("a", {clase: "boton", href: "/api/diagnostico", download: ""}, "Descargar diagnóstico (sin saldo ni secretos)")));
}

function pintar() {
  if (!s.zona) return;
  const d = s.datos;
  if (!d) {
    reemplazar(s.zona, s.error ? errorCarga(`No se pudo hacer la revisión: ${s.error}`) : h("p", {clase: "cargando"}, "Revisando el taller…"));
    return;
  }
  reemplazar(s.zona,
    s.error ? h("p", {clase: "aviso mal"}, `No se pudo actualizar (${s.error}): lo de abajo es de la última revisión.`) : null,
    cabecera(d), planta(d), ordenes(d), pendientes(d),
    seccion(h("span", {}, "Bancos de pruebas ", ayuda("Bancos de pruebas", "Todas las comprobaciones, agrupadas. Cada luz es una: verde en orden, ámbar a revisar, roja falla, gris sin comprobar, hueca pendiente de ti.")),
      h("div", {clase: "bancos"}, d.grupos.map(banco))),
    libro());
}

/** Contenido de la pestaña «Taller». Se revisa al abrir y cada 30 s mientras esté a la vista. */
export function pestanaTaller() {
  if (s.zona) return s.zona;                    // la vista Sistema se repinta cada 15 s: el taller conserva su estado
  const zona = h("div", {clase: "taller"});
  s.zona = zona;
  s.raiz = zona;
  pintar();
  revisar();
  clearInterval(s.timer);
  s.timer = setInterval(() => { if (!document.hidden) revisar({silencioso: true}); }, 30000);
  return zona;
}

/** Al salir de la vista Sistema: se paran las revisiones periódicas (el libro se conserva hasta recargar). */
export function cerrarTaller() {
  clearInterval(s.timer);
  s.timer = null;
  s.zona = s.raiz = null;
}
