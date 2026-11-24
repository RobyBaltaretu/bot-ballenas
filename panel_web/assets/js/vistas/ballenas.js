// BALLENAS Y DATOS EXTERNOS: lo observado y lo inferido, con procedencia y frescura. Direcciones enmascaradas
// (vienen así del backend). Binance y Bybit son SOLO fuentes de lectura: el bot nunca opera allí.

import {chip, escribiendo, h, pestanasVista, reemplazar, seccion, tabla, vacio} from "../dom.js";
import {bot, estado, preferencias} from "../estado.js";
import {conSigno, frescura, hace, num, usd} from "../formato.js";
import {info} from "../info.js";

const ETIQUETA = {"observación": ["observación", "info"], "inferencia": ["inferencia", "aviso"], "validada fuera de muestra": ["validada fuera de muestra", "ok"]};

let raiz = null;

function pintar() {
  if (!raiz) return;
  const b = bot();
  const ahora = estado.datos?.ahora || Date.now() / 1000;
  const cob = b.cobertura_ballenas || {};
  const ctx = b.contexto_externo || {};
  const flujo = Object.entries(cob.flujo_1h_usd || {});
  const cols = [
    {t: "Cuenta", v: (x) => h("span", {clase: "mono"}, x.direccion || "—")},
    {t: "Tipo de dato", v: (x) => { const [t, c] = ETIQUETA[x.etiqueta] || [x.etiqueta || "—", null]; return chip(t, c); }},
    {t: "Frescura", v: (x) => { const f = frescura(x.actualizada_ts, ahora, {retraso: 600, obsoleto: 3600}); return chip(f.texto, f.clase); }},
    {t: "Tiempo real", v: (x) => x.tiempo_real ? "websocket" : "fotos periódicas"},
    {t: "Posiciones observadas", v: (x) => (x.abiertas || []).join(", ") || "ninguna"},
    {t: "Cambio 1 h (inferido)", v: (x) => (x.cambios_1h || []).map((c) => `${c.moneda} ${usd(c.neto_1h_usd, 0)}`).join(" · ") || "—"},
  ];
  if (preferencias.experto) cols.push({t: "Casos / R medio (inferencia)", v: (x) => x.casos ? `${x.casos} · ${num(x.r_medio, 2)} R` : "—", der: true},
    {t: "Vetada", v: (x) => x.vetada ? "sí" : "no"}, {t: "Regla de selección", v: (x) => x.regla || "—"});
  reemplazar(raiz,
    h("div", {clase: "titulo-vista"}, h("div", {}, h("h1", {}, "Ballenas"),
      h("p", {}, `${cob.elegidas ?? "—"} cuentas grandes seguidas · ${cob.frescas ?? "—"} con datos frescos `,
        info("ballena_etiqueta", "observación, inferencia o validada")))),
    pestanasVista("ballenas", [
    ["cuentas", "Cuentas seguidas", () => seccion(null, tabla(cols, b.ballenas || [], {vacioTexto: "El bot no sigue ninguna cuenta ahora mismo."}),
      h("p", {clase: "muy-tenue"}, `${cob.suscritas_tiempo_real ?? "—"} en tiempo real (máximo ${cob.limite_tiempo_real ?? "—"}) · ${cob.fills_ws_recibidos ?? 0} fills vistos`))],
    ["flujo", "Qué compran y venden", () => seccion(h("span", {}, "Flujo neto de la última hora ", chip("inferido", "aviso")),
      flujo.length ? tabla([{t: "Moneda", v: ([m]) => m}, {t: "Neto (USD, + = compran)", v: ([, v]) => h("span", {clase: "num"}, conSigno(v, 0, " $")), der: true}], flujo)
        : vacio("Sin cambios relevantes en la última hora."),
      h("p", {clase: "muy-tenue"}, "Deducido de fotos de sus posiciones, no de sus órdenes."))],
    ["externos", "Binance y Bybit", () => seccion("Datos externos (solo lectura)",
      h("p", {clase: "tenue"}, ctx.uso || "Datos públicos de mercado; nunca se opera allí."),
      tabla([{t: "Fuente", v: ([k]) => k}, {t: "Estado", v: ([, v]) => chip(v.estado || "desconocido", v.estado === "correcto" ? "ok" : "aviso")},
        {t: "Detalle", v: ([, v]) => v.detalle || "—"}, {t: "Leído", v: ([, v]) => hace(v.ts, ahora)}],
      Object.entries(ctx.fuentes || {}), {vacioTexto: ctx.activo === false ? "Desactivado en la configuración." : "Sin datos de fuentes externas."}),
      (ctx.no_coinciden || []).length ? h("p", {clase: "aviso"}, `Precio externo distinto del de Hyperliquid (se ignora): ${ctx.no_coinciden.join(", ")}`) : null)],
    ], "Secciones de ballenas"));
}

export const vista = {
  entrar(el) { raiz = el; pintar(); },
  actualizar() { if (!escribiendo(raiz)) pintar(); },
  salir() { raiz = null; },
};
