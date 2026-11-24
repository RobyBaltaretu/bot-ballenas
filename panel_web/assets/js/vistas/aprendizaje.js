// APRENDIZAJE E INVESTIGACIÓN: lo que el bot aprende de sus señales (operadas y en papel) y el departamento de
// investigación. Nada de esto son resultados de dinero real: se dice en cada bloque.

import {chip, escribiendo, h, pestanasVista, reemplazar, seccion, tabla, vacio} from "../dom.js";
import {bot, estado, preferencias} from "../estado.js";
import {fecha, num} from "../formato.js";
import {info} from "../info.js";

const TIPO = {real: "operadas por el bot", sombra: "descartadas, seguidas en papel", shadow: "intenciones shadow (modelado)", backtest: "laboratorio (histórico)"};

let raiz = null;

// El backend da media 0 cuando no hay casos: aquí se muestra «—» (sin datos), no un 0 inventado.
const media = (x) => (x && x.n ? `${num(x.media, 3)} R` : "—");

function pintar() {
  if (!raiz) return;
  const a = estado.datos?.aprendizaje || {};
  const b = bot();
  const inv = b.investigacion || {};
  const ev = a.evaluacion_filtro || {};
  const simulado = b.modo !== "real";
  reemplazar(raiz,
    h("div", {clase: "titulo-vista"}, h("div", {}, h("h1", {}, "Aprendizaje"),
      h("p", {}, "Qué tal salen las señales y qué ideas se están probando."))),
    pestanasVista("aprendizaje", [
    ["filtro", "¿Acierta el bot al filtrar?", () => [
    seccion(h("span", {}, "¿Sirve el filtro de aprendizaje? ", info("filtro_aprendizaje", "evaluación del filtro")),
      h("p", {}, chip(ev.veredicto === "sin_datos" ? "sin datos suficientes" : ev.veredicto || "—", ev.veredicto === "aporta" ? "ok" : "aviso"), " ", ev.texto || ""),
      tabla([{t: "Grupo", v: ([k]) => k}, {t: "Señales cerradas", v: ([, v]) => String(v?.n ?? "—"), der: true},
        {t: "R medio", v: ([, v]) => (v?.n ? `${num(v.r_medio, 3)} R` : "—"), der: true}],
      [["aceptadas", ev.aceptadas], ["rechazadas", ev.rechazadas]])),
    seccion("Resultados por tipo de seguimiento",
      simulado ? h("p", {clase: "aviso info"}, "En simulado, «operadas por el bot» son operaciones con dinero ficticio.") : null,
      tabla([{t: "Tipo", v: ([k]) => TIPO[k] || k}, {t: "Casos", v: ([, v]) => String(v.n), der: true},
        {t: "Ganadoras", v: ([, v]) => (v.n ? `${v.ganan} %` : "—"), der: true}, {t: "R medio", v: ([, v]) => media(v), der: true}],
      Object.entries(a.por_tipo || {}))),
    preferencias.experto ? seccion("Motivos de descarte (resultado en papel de lo descartado)",
      tabla([{t: "Motivo", v: ([k]) => k}, {t: "Casos", v: ([, v]) => String(v.n), der: true}, {t: "R medio", v: ([, v]) => media(v), der: true}],
        Object.entries(a.por_filtro || {}).sort((x, y) => y[1].n - x[1].n))) : null]],
    ["investigacion", "Ideas nuevas", () => [
    seccion(h("span", {}, "Departamento de investigación ", info("investigacion", "investigación")),
      h("p", {}, `${inv.probadas_total ?? "—"} ideas probadas · ${inv.en_cementerio ?? "—"} descartadas · t exigida ahora ${num(inv.t_requerido, 2)} (sube con el total probado: ${inv.variantes_totales ?? "—"} variantes).`),
      inv.ultimo_informe ? h("p", {clase: "tenue"}, `Última sesión ${inv.ultimo_informe.fecha}: ${inv.ultimo_informe.probadas_hoy} ideas en ${num(inv.ultimo_informe.minutos, 0)} min.`) : null,
      (inv.aspirantes || []).length ? tabla([{t: "Aspirante", v: (x) => x.nombre || x.id || "—"}, {t: "Estado", v: (x) => x.estado || "—"}], inv.aspirantes)
        : vacio("Ninguna idea está en observación ahora mismo (ninguna ha superado el examen)."),
      (inv.en_revision || []).length ? h("p", {clase: "aviso"}, `${inv.en_revision.length} idea(s) pendientes de TU revisión. Nada se activa sola.`) : null)]],
    ["descartes", "Descartes recientes", () => seccion(null, tabla([
      {t: "Fecha", v: (r) => fecha(r.ts)}, {t: "Moneda", v: (r) => r.moneda}, {t: "Estrategia", v: (r) => r.modulo || "—"},
      {t: "Motivo", v: (r) => (r.motivos_descarte || []).join(" · ") || "—"},
      {t: "Resultado (papel)", v: (r) => (r.resultado_r == null ? "abierta" : `${num(r.resultado_r)} R`), der: true}],
    (a.descartes || []).slice(0, 20), {vacioTexto: "Sin descartes recientes."}))],
    ], "Secciones de aprendizaje"));
}

export const vista = {
  entrar(el) { raiz = el; pintar(); },
  actualizar() { if (!escribiendo(raiz)) pintar(); },
  salir() { raiz = null; },
};
