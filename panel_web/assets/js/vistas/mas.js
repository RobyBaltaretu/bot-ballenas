// MÁS: las secciones secundarias (investigación y sistema), el modo experto y la vuelta al panel clásico.

import {h, reemplazar} from "../dom.js";
import {aplicarTema, estado, preferencias} from "../estado.js";

const NS = "http://www.w3.org/2000/svg";

// Iconos de trazo simples (atributos de presentación SVG: la CSP no los considera estilos en línea).
const ICONOS = {
  ballenas: "M3 15c2.5-5 7.5-7 12.5-5.5 2.2.7 3.8 2 5.5 1.3-.8 3.4-4 5.2-7.4 5.2H9l-3.2 2.5.8-3.5z",
  aprendizaje: "M12 3 2 8l10 5 10-5-10-5zM6 10.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-5.5",
  sistema: "M3 12h4l2-5 4 10 2-5h6M3 5h18M3 19h18",
  configuracion: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4",
  clasico: "M4 4h16v16H4zM4 9h16M9 9v11",
  experto: "M8 9l-4 3 4 3M16 9l4 3-4 3M13 6l-2 12",
  objetivo: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  tema: "M12 3a9 9 0 1 0 9 9 7 7 0 0 1-9-9z",
  macro: "M7 15a4 4 0 0 1 .5-8 5 5 0 0 1 9.5 1.5A3.5 3.5 0 0 1 17 15M12 12l-2 4h3l-2 4",
  sombras: "M12 21a9 9 0 1 1 9-9M12 17a5 5 0 1 1 5-5M12 12l7-7",
};

function icono(nombre) {
  const svg = document.createElementNS(NS, "svg");
  for (const [k, v] of Object.entries({viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "2",
    "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true"})) svg.setAttribute(k, v);
  const p = document.createElementNS(NS, "path");
  p.setAttribute("d", ICONOS[nombre]);
  svg.append(p);
  return h("span", {clase: "icono"}, svg);
}

function enlace(href, nombre, titulo, sub) {
  return h("li", {}, h("a", {clase: "fila", href}, icono(nombre),
    h("div", {clase: "centro"}, h("div", {clase: "titulo"}, titulo), h("div", {clase: "sub"}, sub)), h("span", {clase: "flecha", "aria-hidden": "true"})));
}

function pintar(raiz) {
  const inc = estado.datos?.sistema_resumen?.incidentes_activos;
  const exp = h("input", {type: "checkbox", id: "modo-experto", marcado: preferencias.experto, "aria-describedby": "experto-ayuda",
    onChange: (e) => { preferencias.experto = e.currentTarget.checked; document.body.classList.toggle("experto", e.currentTarget.checked); }});
  const claro = h("input", {type: "checkbox", id: "tema-claro", marcado: preferencias.tema === "claro", "aria-describedby": "tema-ayuda",
    onChange: (e) => { preferencias.tema = e.currentTarget.checked ? "claro" : "terminal"; aplicarTema(preferencias.tema); }});
  reemplazar(raiz,
    h("div", {clase: "titulo-vista"}, h("h1", {}, "Más")),
    h("section", {clase: "seccion"}, h("h2", {}, "Prueba de dos semanas"),
      h("ul", {clase: "lista menu-mas"},
        enlace("#/objetivo", "objetivo", "Objetivo y analista", "Veredicto, objetivo semanal e informe diario"))),
    h("section", {clase: "seccion"}, h("h2", {}, "Investigación"),
      h("ul", {clase: "lista menu-mas"},
        enlace("#/ballenas", "ballenas", "Ballenas y datos externos", "Cuentas seguidas, flujo inferido y fuentes"),
        enlace("#/aprendizaje", "aprendizaje", "Aprendizaje e investigación", "Qué filtra el bot y las ideas en estudio"),
        enlace("#/macro", "macro", "Parte del mar", "Citas de la Fed y del IPC como tormentas en el horizonte"),
        enlace("#/sombras", "sombras", "Sónar de sombras", "Lo que el bot descartó y cómo habría acabado"))),
    h("section", {clase: "seccion"}, h("h2", {}, "Sistema"),
      h("ul", {clase: "lista menu-mas"},
        enlace("#/sistema", "sistema", "Observabilidad", inc ? `${inc} incidente(s) activo(s)` : "Salud del bot, registros e incidentes"),
        enlace("#/configuracion", "configuracion", "Configuración", "Ajustes del bot con vista previa"))),
    h("section", {clase: "seccion"}, h("h2", {}, "Preferencias"),
      h("ul", {clase: "lista menu-mas"},
        h("li", {}, h("div", {clase: "fila"}, icono("experto"),
          h("div", {clase: "centro"}, h("label", {clase: "titulo", for: "modo-experto"}, "Modo experto"),
            h("div", {clase: "sub", id: "experto-ayuda"}, "Más columnas, filtros, trazas e identificadores. No cambia ningún permiso.")),
          h("span", {clase: "interruptor"}, exp, h("span", {"aria-hidden": "true"})))),
        h("li", {}, h("div", {clase: "fila"}, icono("tema"),
          h("div", {clase: "centro"}, h("label", {clase: "titulo", for: "tema-claro"}, "Tema claro"),
            h("div", {clase: "sub", id: "tema-ayuda"}, "Por defecto, tema oscuro tipo terminal. Solo cambia el aspecto en este navegador.")),
          h("span", {clase: "interruptor"}, claro, h("span", {"aria-hidden": "true"})))),
        h("li", {}, h("a", {clase: "fila", href: "/clasico"}, icono("clasico"),
          h("div", {clase: "centro"}, h("div", {clase: "titulo"}, "Panel clásico"), h("div", {clase: "sub"}, "La versión anterior, por si la necesitas")),
          h("span", {clase: "flecha", "aria-hidden": "true"}))))));
}

export const vista = {
  entrar(el) { pintar(el); },
};
