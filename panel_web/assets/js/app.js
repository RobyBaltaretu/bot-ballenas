// Aplicación del panel: navegación por hash, franja de estado común y modo sencillo/experto.
// Sin dependencias externas ni paso de compilación: módulos JavaScript nativos servidos por panel.py.

import {marcarEntrada} from "./anim.js";
import {SOLO_LECTURA} from "./api.js";
import {$, chip, errorCarga, h, reemplazar} from "./dom.js";
import {aplicarTema, estado, iniciarSondeo, preferencias, suscribir} from "./estado.js";
import {frescura} from "./formato.js";
import {iniciarDialogo} from "./info.js";
import {iniciarMarco, marcarLateral, pintarMarco} from "./marco.js";

const VISTAS = {
  inicio: () => import("./vistas/inicio.js"),
  operaciones: () => import("./vistas/operaciones.js"),
  operacion: () => import("./vistas/operaciones.js"),
  actividad: () => import("./vistas/actividad.js"),
  estrategias: () => import("./vistas/estrategias.js"),
  estrategia: () => import("./vistas/estrategias.js"),
  ballenas: () => import("./vistas/ballenas.js"),
  aprendizaje: () => import("./vistas/aprendizaje.js"),
  sistema: () => import("./vistas/sistema.js"),
  configuracion: () => import("./vistas/configuracion.js"),
  mas: () => import("./vistas/mas.js"),
  objetivo: () => import("./vistas/objetivo.js"),
  macro: () => import("./vistas/macro.js"),
  sombras: () => import("./vistas/sombras.js"),
};

let vistaActual = null;
let tituloBase = "Panel · Bot de ballenas";

// Título de la pestaña con las operaciones abiertas delante, «(4) Inicio · …», para verlo sin abrir el panel.
function ponerTitulo() {
  const n = (estado.datos?.bot?.posiciones || []).length;
  document.title = n ? `(${n}) ${tituloBase}` : tituloBase;
}

// Pestaña que se marca para cada vista (las secundarias viven dentro de «Más»).
const PESTANA = {operacion: "operaciones", estrategia: "estrategias", ballenas: "mas", aprendizaje: "mas", sistema: "mas", configuracion: "mas", objetivo: "mas", macro: "mas", sombras: "mas"};
const ESTRECHAS = new Set(["mas", "objetivo"]);   // columna centrada, como una app móvil
const ANCHAS = new Set(["inicio"]);               // portada tipo terminal: núcleo 3D y embudo a lo ancho

const MODOS = {simulado: ["Simulado", "info", "Dinero ficticio con precios reales"], shadow: ["Shadow", "aviso", "Sin órdenes: resultados modelados"],
  real: ["REAL", "mal", "Dinero real"]};

// Franja compacta: modo y si el bot está vivo; lo que falla se añade como una píldora más. El detalle va en Inicio.
function pintarFranja() {
  const el = $("franja");
  const d = estado.datos;
  if (!d) {
    reemplazar(el, estado.error ? chip("Sin conexión", "mal", {titulo: estado.error}) : chip("Conectando…", null));
    return;
  }
  const b = d.bot || {};
  const [textoModo, claseModo, explicacion] = MODOS[b.modo] || [`Modo ${b.modo || "desconocido"}`, "aviso", ""];
  const partes = [chip(textoModo, `${claseModo} modo`, {punto: false, titulo: explicacion})];
  if (estado.error) {
    // Sin respuesta del panel: no se sabe si el bot sigue activo ni si puede abrir. Se dice solo lo que se sabe.
    const f = frescura(b.ts, Date.now() / 1000);
    partes.push(chip("Sin conexión", "mal", {titulo: `${estado.error} · últimos datos del bot ${f.texto}`}),
      chip("Estado: desconocido", "aviso", {titulo: "Estado actual del bot: desconocido"}));
  } else {
    const f = frescura(b.ts, d.ahora);
    partes.push(!b.ts ? chip("Bot sin datos", "mal", {titulo: "¿Apagado?"})
      : d.bot_vivo ? chip(f.clase === "ok" ? "En vivo" : "Retrasado", f.clase, {titulo: `Bot activo · datos ${f.texto}`})
        : chip("Sin señales", "mal", {titulo: `Bot sin señales · ${f.texto}`}));
    const bloq = b.ts ? b.bloqueos || [] : [];
    if (bloq.length) partes.push(chip("Entradas bloqueadas", "aviso", {titulo: bloq.join(" · ")}));
    const inc = d.sistema_resumen?.incidentes_activos;
    if (inc) partes.push(h("a", {href: "#/sistema"}, chip(`${inc} incidente${inc > 1 ? "s" : ""}`, "mal")));
  }
  if (SOLO_LECTURA) partes.push(chip("Solo lectura", null, {titulo: "Panel abierto desde fuera de este equipo: sin comandos"}));
  reemplazar(el, ...partes);
}

function ruta() {
  const [, nombre = "inicio", ...resto] = (location.hash || "#/inicio").split("/");
  return {nombre: VISTAS[nombre] ? nombre : "inicio", arg: decodeURIComponent(resto.join("/") || "")};
}

async function navegar() {
  const {nombre, arg} = ruta();
  const nav = PESTANA[nombre] || nombre;
  for (const a of document.querySelectorAll(".navegacion a[data-vista]")) {
    if (a.dataset.vista === nav) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  marcarLateral(nombre);
  if (vistaActual?.salir) vistaActual.salir();
  const main = $("contenido");
  main.classList.toggle("estrecho", ESTRECHAS.has(nombre));
  main.classList.toggle("ancho", ANCHAS.has(nombre));
  reemplazar(main, h("p", {clase: "cargando"}, "Cargando…"));
  try {
    const modulo = await VISTAS[nombre]();
    vistaActual = nombre === "operacion" || nombre === "estrategia" ? modulo.detalle : modulo.vista;
    await vistaActual.entrar(main, arg);
    tituloBase = `${main.querySelector("h1")?.textContent || "Panel"} · Bot de ballenas`;
    ponerTitulo();
    main.focus({preventScroll: true});
    window.scrollTo(0, 0);
    marcarEntrada(main);
  } catch (e) {
    console.error(e);
    reemplazar(main, errorCarga(`No se pudo mostrar esta sección: ${e.message}`));
  }
}

function iniciar() {
  aplicarTema(preferencias.tema);
  iniciarDialogo();
  iniciarMarco();
  document.body.classList.toggle("experto", preferencias.experto);   // el interruptor está en «Más»
  suscribir(() => {
    pintarFranja();
    pintarMarco();
    ponerTitulo();
    vistaActual?.actualizar?.(estado);
  });
  window.addEventListener("hashchange", navegar);
  iniciarSondeo();
  navegar();
}

iniciar();
