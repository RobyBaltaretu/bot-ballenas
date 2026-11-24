// CARRY de funding (19/11/2026): pestaña de «Estrategias». Muestra lo que hace el motor simulado (carry/motor.py, proceso
// aparte): las dos patas de cada posición con el funding cobrado, el radar de funding por moneda frente al listón, y los
// cierres. Dinero ficticio con precios y funding reales. Sin «rentable»: con menos de 30 cierres nada es concluyente.

import {obtener} from "../api.js";
import {cifraViva} from "../anim.js";
import {chip, errorCarga, h, listaDef, reemplazar, seccion, tabla, vacio} from "../dom.js";
import {fecha, num, resultado} from "../formato.js";
import {titulo} from "../info.js";
import {explicacion} from "./explicaciones.js";

function kpi(etq, valor, pie) {
  return h("div", {clase: "paso"}, h("div", {clase: "etq"}, etq), h("div", {clase: "v"}, valor), h("div", {clase: "pie"}, pie || ""));
}

function queEs() {
  const x = explicacion("carry");
  return h("section", {clase: "explica", "aria-label": "Qué es el carry"}, h("p", {clase: "explica-resumen"}, x.resumen),
    h("div", {clase: "explica-rejilla"},
      [["Qué hace", x.hace], ["Cómo funciona", x.como], ["Qué persigue", x.persigue]].map(([e, t], k) =>
        h("div", {clase: "explica-bloque", estilo: {"--k": String(k)}}, h("div", {clase: "explica-etq"}, e), h("p", {}, t)))));
}

function pata(etq, linea, detalle, clase) {
  return h("div", {clase: ["carry-pata", clase]}, h("div", {clase: "carry-pata-etq"}, etq), h("div", {clase: "carry-pata-linea"}, linea),
    h("div", {clase: "carry-pata-det"}, detalle));
}

function posicion(p) {
  const neto = p.neto_estimado_usd;
  return h("article", {clase: ["carry-pos", p.congelada ? "congelada" : null]},
    h("header", {clase: "carry-pos-cab"}, h("strong", {}, p.coin), chip(`${num(p.horas, 1)} h abierta`),
      p.funding_anual_actual_pct != null ? chip(`funding ${num(p.funding_anual_actual_pct, 1)} %/año`, "info") : null,
      p.congelada ? chip("DESEQUILIBRIO: revisar", "mal") : null),
    h("div", {clase: "carry-patas"},
      pata("Corto en perpetuo", `${num(p.sz, 5)} ${p.coin}`, `entró a ${num(p.entrada_perp, 2)} $ · marca ${num(p.marca_perp, 2)} $`, "corto"),
      h("div", {clase: "carry-flujo", "aria-hidden": "true"}, [0, 1, 2, 3].map((k) => h("i", {estilo: {"--k": String(k)}})),
        h("span", {}, `+${num(p.funding_usd, 4)} $`)),
      pata("Largo al contado", `${num(p.sz, 5)} ${p.coin}`, `entró a ${num(p.entrada_spot, 2)} $ · ahora ${num(p.precio_spot, 2)} $`, "largo")),
    listaDef([
      ["Funding cobrado (real)", `${num(p.funding_usd, 4)} $`],
      ["Base (diferencia entre patas)", [resultado(p.base_usd, 4, " $"), p.base_pct != null ? ` · ${num(p.base_pct, 3)} %` : ""]],
      ["Comisiones de apertura", `${num(p.comisiones_usd, 4)} $`],
      ["Resultado estimado si cerrara ya", resultado(neto, 4, " $")],
      ["Margen hasta la liquidación del corto", p.distancia_liquidacion_pct != null ? `${num(p.distancia_liquidacion_pct, 1)} % de subida` : "—"],
      ["Capital usado", p.capital_usd ? `${num(p.capital_usd, 2)} $ (contado + margen)` : "—"],
    ]));
}

function radar(d) {
  const lis = d.radar || [];
  if (!lis.length) return vacio("Aún no hay lectura de funding.");
  const liston = d.criterios?.funding_min_anual_pct ?? 20;
  const tope = Math.max(liston * 2, ...lis.map((r) => r.funding_anual_pct), 10);
  return h("ul", {clase: "carry-radar"}, lis.map((r) => {
    const llega = r.funding_anual_pct >= liston;
    return h("li", {clase: llega ? "llega" : null},
      h("span", {clase: "radar-moneda"}, r.coin),
      h("div", {clase: "radar-barra", title: `${num(r.funding_anual_pct, 1)} %/año de funding; el listón es ${liston} %`},
        h("span", {clase: "radar-relleno", estilo: {width: `${Math.max(0, Math.min(100, r.funding_anual_pct / tope * 100))}%`}}),
        h("i", {clase: "radar-liston", estilo: {left: `${liston / tope * 100}%`}})),
      h("span", {clase: "radar-valor"}, cifraViva(`carry.${r.coin}`, r.funding_anual_pct, (n) => `${num(n, 1)} %`)),
      h("span", {clase: "radar-motivo"}, (d.descartadas || {})[r.coin] ? "" : llega ? "cumple" : ""));
  }));
}

function cuerpo(d) {
  if (!d || !d.ts) {
    return [queEs(), vacio("El motor del carry aún no ha escrito nada. Arranca con INICIAR.bat o con: python -m carry.motor")];
  }
  const edad = Date.now() / 1000 - d.ts;
  const vivo = d.estado === "activo" && edad < 3 * (d.intervalo_s || 600);
  const cuenta = d.cuenta || {}, res = d.resumen || {};
  const estado = d.estado === "activo"
    ? (vivo ? chip("Motor en marcha", "ok") : chip(`Motor parado desde ${fecha(d.ts)}`, "aviso", {titulo: "Se arranca con INICIAR.bat o python -m carry.motor"}))
    : chip(`${d.estado}: ${d.motivo || ""}`, "aviso");
  return [
    queEs(),
    h("p", {}, estado, " ", chip("Dinero ficticio · precios y funding reales", null), " ", h("span", {clase: "muy-tenue"}, `última pasada ${fecha(d.ts)}`)),
    h("section", {clase: "embudo kpis", "aria-label": "Resumen del carry"},
      kpi("Cuenta simulada", `${num(cuenta.equity_usd, 2)} $`, [resultado(cuenta.rendimiento_usd, 2, " $"), ` desde ${num(cuenta.inicial_usd, 0)} $`]),
      kpi("Funding cobrado", `${num(res.funding_cobrado_usd, 3)} $`, "real, de las tasas de Hyperliquid"),
      kpi("Posiciones", `${(d.posiciones || []).length} / ${d.criterios?.max_posiciones ?? "—"}`, "dos patas cada una"),
      kpi("Cerradas", num(res.n_cerradas, 0), res.n_cerradas ? [resultado(res.pnl_neto_usd, 3, " $"), " netos"] : "sin cierres todavía")),
    seccion(titulo("Posiciones abiertas", "Posiciones abiertas",
      "Cada posición son dos patas: un corto en el perpetuo que cobra el funding y la misma cantidad comprada al contado que cubre el precio.",
      "No hay stop de precio: la cobertura es la otra pata. Sale por funding hundido, base abierta, liquidez peor, riesgo de liquidación o tiempo."),
    (d.posiciones || []).length ? (d.posiciones || []).map(posicion)
      : vacio(`Ninguna abierta: espera a que el funding supere ${d.criterios?.funding_min_anual_pct ?? 20} %/año y compense las comisiones.`)),
    seccion(titulo("Radar de funding", "Radar de funding",
      "Funding medio reciente de cada moneda con contado verificado, en % anual (lo que cobraría un corto). La marca es el listón de entrada.",
      `Además debe ser positivo la mayor parte del tiempo, amortizar las comisiones (${num(d.coste_ida_vuelta_pct, 2)} % ida y vuelta) y tener poca base.`),
    radar(d),
    Object.keys(d.descartadas || {}).length ? h("details", {clase: "plegable"}, h("summary", {}, "Por qué no entra cada moneda"),
      h("div", {clase: "cuerpo"}, h("ul", {clase: "lista-simple"}, Object.entries(d.descartadas).map(([c, m]) => h("li", {}, `${c}: ${m}`))))) : null),
    seccion("Cierres", tabla([
      {t: "Moneda", v: (x) => h("strong", {}, x.coin)}, {t: "Cuándo", v: (x) => fecha(x.ts)},
      {t: "Horas", v: (x) => num(x.horas, 1), der: true}, {t: "Funding", v: (x) => `${num(x.funding_cobrado_usd, 4)} $`, der: true},
      {t: "Comisiones", v: (x) => `${num(x.comisiones_usd, 4)} $`, der: true}, {t: "Base", v: (x) => resultado(x.base_usd, 4, " $"), der: true},
      {t: "Neto", v: (x) => resultado(x.pnl_neto_usd, 4, " $"), der: true}, {t: "Motivo", v: (x) => x.motivo},
    ], [...(d.cerradas || [])].reverse(), {vacioTexto: "Aún no se ha cerrado ningún carry."})),
    h("p", {clase: "muy-tenue"}, "Con menos de 30 cierres nada de esto es concluyente. No activa nada en real: pasar a real exige promoción y aprobación expresa."),
  ];
}

/** Contenedor que carga /api/carry y se repinta cada 30 s mientras esté en pantalla. */
export function pestanaCarry() {
  const raiz = h("div", {clase: "carry"}, h("p", {clase: "cargando"}, "Cargando carry…"));
  const cargar = async () => {
    try {
      reemplazar(raiz, ...[].concat(cuerpo(await obtener("/api/carry"))));
    } catch (e) {
      reemplazar(raiz, errorCarga(`No se pudo leer el carry: ${e.message}`));
    }
  };
  cargar();
  const t = setInterval(() => { if (!raiz.isConnected) clearInterval(t); else cargar(); }, 30000);
  return raiz;
}
