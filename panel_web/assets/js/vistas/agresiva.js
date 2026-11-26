// CUENTA AGRESIVA (25/11/2026, pedida por Roberto): experimento APARTE de las ballenas. Señales propias de 15 min al estilo
// de los canales de señales (stop corto, cinco objetivos, apalancamiento alto) en una cuenta simulada propia, con una
// gemela de tamaño normal que recibe las mismas señales. Lo escribe el motor agresiva/motor.py (proceso aparte) en
// agresiva_estado.json; aquí solo se lee (/api/agresiva). No se mezcla con nada del bot: ni operaciones, ni ledger, ni
// estrategias. Dinero ficticio con precios reales; no existe camino a real.

import {obtener} from "../api.js";
import {chip, errorCarga, h, listaDef, pestanasVista, reemplazar, seccion, tabla, vacio} from "../dom.js";
import {conSigno, fecha, hay, num, precio, resultado, usd} from "../formato.js";
import {graficoLinea, graficoVelas} from "../grafico.js";
import {titulo} from "../info.js";

let raiz = null, datos = null, cargado = 0;
const intervalo = new Map();          // señal -> "1m" | "15m" (solo en memoria)
const SEG = {"1m": 60000, "15m": 900000};

const LADO = {1: ["Largo", "ok"], "-1": ["Corto", "mal"]};
const SALIDA = {stop: "stop", stop_entrada: "stop en la entrada", liquidacion: "LIQUIDADA", tiempo: "por tiempo", quiebra: "cierre por quiebra",
  reinicio: "cierre por reinicio", objetivo_1: "objetivo 1", objetivo_2: "objetivo 2", objetivo_3: "objetivo 3", objetivo_4: "objetivo 4",
  objetivo_5: "todos los objetivos"};
const ESTADO_CUENTA = {activa: ["Agresiva activa", "ok"], pausa: ["Agresiva en pausa", "aviso"], quebrada: ["Agresiva QUEBRADA", "mal"]};

const nombreRegla = (r) => datos?.nombres_reglas?.[r] || String(r || "?").replace(/_/g, " ");
const pct = (v, d = 1) => (hay(v) ? `${num(v, d)} %` : "—");
const fechaMs = (ms) => (hay(ms) ? fecha(ms / 1000) : "—");

function kpi(etq, valor, pie, clase) {
  return h("div", {clase: ["paso", clase]}, h("div", {clase: "etq"}, etq), h("div", {clase: "v"}, valor), h("div", {clase: "pie"}, pie || ""));
}

function salida(p) {
  if (!p) return "—";
  const t = SALIDA[p.salida] || p.salida || "abierta";
  return p.salida === "liquidacion" ? h("strong", {clase: "agr-liq-txt"}, t) : t;
}

// ---------------------------------------------------------------- cabecera
function cabecera(d) {
  const edad = Date.now() / 1000 - (d.ts || 0);
  const vivo = d.estado === "activo" && edad < 4 * (d.intervalo_s || 60);
  const motor = d.estado === "activo"
    ? (vivo ? chip("Motor en marcha", "ok") : chip(`Motor parado desde ${fecha(d.ts)}`, "aviso", {titulo: "Se arranca con INICIAR.bat o python -m agresiva.motor"}))
    : chip(`Motor ${d.estado}: ${d.motivo || ""}`, "aviso");
  const [txt, cls] = ESTADO_CUENTA[d.agresiva?.estado] || ["Agresiva: sin dato", "aviso"];
  return h("div", {clase: "agr-cabecera"},
    h("h1", {}, "Cuenta agresiva"),
    h("p", {clase: "agr-aviso"}, "Experimento aparte de las ballenas: señales propias de 15 min con apalancamiento alto. Dinero ficticio con precios reales de Hyperliquid. No puede pasar a real."),
    h("p", {}, motor, " ", chip(txt, cls, {titulo: d.agresiva?.motivo_pausa || ""}), " ",
      chip(`Etapa ${d.etapa?.n ?? 1}`, null, {titulo: "Cada vez que la cuenta quiebra y se reinicia empieza una etapa nueva"}),
      (d.reinicios || []).length ? chip(`${d.reinicios.length} reinicio${d.reinicios.length > 1 ? "s" : ""}`, "aviso") : null, " ",
      h("span", {clase: "muy-tenue"}, `última pasada ${fecha(d.ts)}`)));
}

function kpis(d) {
  const a = d.agresiva || {}, g = d.gemela || {}, t = d.resumen?.total || {};
  const ab = (d.abiertas || []).length;
  return h("section", {clase: "embudo kpis agr-kpis", "aria-label": "Resumen de la cuenta agresiva"},
    kpi("Cuenta agresiva", usd(a.equity_usd), [resultado(a.rendimiento_usd, 2, " $"), ` (${conSigno(a.rendimiento_pct, 1, " %")}) desde ${usd(a.inicial_usd, 0)}`],
      a.estado === "quebrada" ? "agr-mal" : null),
    kpi("Gemela (tamaño normal)", usd(g.equity_usd), [resultado(g.rendimiento_usd, 2, " $"), ` (${conSigno(g.rendimiento_pct, 1, " %")}) · mismas señales`]),
    kpi("Abiertas", `${ab} / ${d.criterios?.max_abiertas ?? 3}`, `margen agresivo en uso ${usd(a.margen_usado_usd)}`),
    kpi("Cerradas", num(t.gemela?.n || 0, 0), t.gemela?.n ? `acierto ${pct(t.gemela.acierto_pct)} · R medio ${num(t.gemela.r_media, 2)}` : "sin cierres todavía"),
    kpi("Peor caída", pct(a.caida_max_pct), `gemela ${pct(g.caida_max_pct)} · quiebra por debajo de ${usd(a.quiebra_usd)}`, a.caida_max_pct >= 30 ? "agr-mal" : null));
}

// ---------------------------------------------------------------- resumen
function curva(d, indice, etiqueta) {
  const puntos = (d.curva || []).map((p) => [p[0], p[indice]]).filter((p) => hay(p[1]));
  if (puntos.length < 2) return vacio("La curva aparece cuando haya al menos dos lecturas (una cada 15 min).");
  const cifra = h("div", {clase: "cifra"}, usd(puntos[puntos.length - 1][1]));
  const linea = h("div", {clase: "variacion"}, "");
  return h("div", {clase: "agr-curva"}, h("div", {clase: "agr-curva-etq"}, etiqueta), cifra, linea,
    graficoLinea(puntos, {cifra, linea, valor: usd, pie: (v0, vi, t) => [resultado(vi - v0, 2, " $"), ` · ${fecha(t)}`],
      etiqueta: `${etiqueta}: de ${usd(puntos[0][1])} a ${usd(puntos[puntos.length - 1][1])}`}));
}

function frenos(d) {
  const a = d.agresiva || {}, c = d.criterios || {};
  const ini = a.inicial_usd || 0, eq = a.equity_usd || 0;
  const barra = (texto, valor, limite, clase) => {
    const p = limite ? Math.max(0, Math.min(100, valor / limite * 100)) : 0;
    return h("div", {clase: "agr-freno"}, h("div", {clase: "agr-freno-etq"}, texto),
      h("div", {clase: "agr-freno-barra"}, h("span", {clase: ["agr-freno-relleno", clase], estilo: {width: `${p}%`}})),
      h("div", {clase: "agr-freno-v"}, `${num(valor, 1)} % de ${num(limite, 0)} %`));
  };
  const perdidaEtapa = ini ? Math.max(0, (1 - eq / ini) * 100) : 0;
  const perdidaDia = a.equity_dia_usd ? Math.max(0, (1 - eq / a.equity_dia_usd) * 100) : 0;
  return seccion(titulo("Frenos", "Frenos de la cuenta agresiva",
    `Pausa de ${c.pausa_freno_h ?? 24} h si pierde el ${c.freno_caida_pct ?? 50} % desde el inicio de la etapa (una vez por etapa).`,
    `Sin entradas hasta las 00:00 UTC si pierde el ${c.freno_diario_pct ?? 15} % en el día.`,
    `Quebrada si baja del ${c.quiebra_pct ?? 10} % del saldo inicial: se cierra todo y se para. Volver a empezar solo a mano, y cada reinicio queda contado.`,
    "Una pausa solo impide entradas nuevas: lo abierto sigue con sus stops y objetivos. La gemela no tiene frenos: sigue midiendo las señales."),
  barra("Pérdida de la etapa (pausa)", perdidaEtapa, c.freno_caida_pct || 50, perdidaEtapa >= (c.freno_caida_pct || 50) * 0.7 ? "mal" : null),
  barra("Pérdida de hoy (freno diario)", perdidaDia, c.freno_diario_pct || 15, perdidaDia >= (c.freno_diario_pct || 15) * 0.7 ? "mal" : null),
  barra("Camino a la quiebra", perdidaEtapa, 100 - (c.quiebra_pct || 10), perdidaEtapa >= 60 ? "mal" : null),
  a.estado === "quebrada" ? h("p", {clase: "agr-quebrada"}, "La cuenta agresiva ha quebrado. Para empezar otra etapa hay que pedirlo (python -m agresiva.motor --reiniciar). El historial se conserva.") : null,
  a.estado === "pausa" ? h("p", {clase: "agr-pausa"}, `${a.motivo_pausa} · hasta ${fecha(a.pausa_hasta)}`) : null);
}

function comparativa(d) {
  const t = d.resumen?.total || {}, a = t.agresiva || {}, g = t.gemela || {};
  if (!g.n) return seccion("Agresiva frente a gemela", vacio("Sin operaciones cerradas todavía. Con menos de 30 por regla nada es concluyente; lo serio empieza hacia las 100."));
  const fila = (k, va, vg) => h("tr", {}, h("th", {scope: "row"}, k), h("td", {clase: "der"}, va), h("td", {clase: "der"}, vg));
  return seccion(titulo("Agresiva frente a gemela", "Por qué hay una gemela",
    `Cada señal se opera dos veces con la misma entrada, stop y objetivos: en la cuenta agresiva (riesgo del ${d.criterios?.riesgo_pct ?? 5} % hasta el stop y apalancamiento alto) y en la gemela (riesgo normal del bot, ${d.criterios?.gemela_riesgo_pct ?? 2} % hasta el stop). Cada una se abre aunque la otra no pueda.`,
    "Si la gemela gana y la agresiva pierde, lo que hunde es el apalancamiento (liquidaciones, comisiones). Si las dos pierden, las señales no valen."),
  h("div", {clase: "tabla-envoltura"}, h("table", {clase: "resp agr-comp"},
    h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", {clase: "der"}, "Agresiva"), h("th", {clase: "der"}, "Gemela"))),
    h("tbody", {},
      fila("Operaciones", num(a.n || 0, 0), num(g.n, 0)),
      fila("Resultado", resultado(a.pnl_usd, 2, " $"), resultado(g.pnl_usd, 2, " $")),
      fila("Riesgo medio por operación (% de la cuenta)", pct(a.riesgo_pct_media, 2), pct(g.riesgo_pct_media, 2)),
      fila("Media por operación (% de la cuenta)", conSigno(a.pct_cuenta_media, 2, " %"), conSigno(g.pct_cuenta_media, 2, " %")),
      fila("R medio", num(a.r_media, 3), num(g.r_media, 3)),
      fila("Acierto", pct(a.acierto_pct), pct(g.acierto_pct)),
      fila("Llegan al objetivo 1", num(a.con_objetivo_1 || 0, 0), num(g.con_objetivo_1 || 0, 0)),
      fila("Stops / stops en la entrada", `${a.stops || 0} / ${a.stops_en_entrada || 0}`, `${g.stops || 0} / ${g.stops_en_entrada || 0}`),
      fila("Liquidaciones", h("strong", {clase: a.liquidaciones ? "agr-liq-txt" : null}, num(a.liquidaciones || 0, 0)), num(g.liquidaciones || 0, 0)),
      fila("Comisiones", usd(a.comisiones_usd), usd(g.comisiones_usd)),
      fila("Funding", resultado(a.funding_usd, 2, " $"), resultado(g.funding_usd, 2, " $"))))),
  (g.n || 0) < 30 ? h("p", {clase: "muy-tenue"}, `Solo ${g.n} cerradas: nada de esto es concluyente todavía.`) : null);
}

// ---------------------------------------------------------------- abiertas
function escalera(s, p) {
  const niveles = [["liq", p.liq, "Liquidación"], ["stop", p.stop, p.toc ? "Stop (en la entrada)" : "Stop"], ["entrada", p.entrada, "Entrada"],
    ...p.objetivos.map((o, k) => [k < p.toc ? "obj tocado" : "obj", o, `Objetivo ${k + 1}`])].filter((n) => hay(n[1]));
  const marca = s.marca;
  const vs = niveles.map((n) => n[1]).concat(hay(marca) ? [marca] : []);
  let min = Math.min(...vs), max = Math.max(...vs);
  if (max - min < 1e-12) { max += 1; min -= 1; }
  const x = (v) => ((v - min) / (max - min)) * 100;
  return h("div", {clase: "agr-escalera", role: "img", "aria-label": `Niveles de ${s.coin}: ${niveles.map((n) => `${n[2]} ${precio(n[1])}`).join(", ")}`},
    h("div", {clase: "agr-pista"}),
    niveles.map(([cls, v, txt]) => h("div", {clase: ["agr-nivel", cls], estilo: {left: `${x(v)}%`}, title: `${txt}: ${precio(v)}`},
      h("span", {clase: "agr-nivel-etq"}, cls.startsWith("obj") ? txt.replace("Objetivo ", "O") : txt))),
    hay(marca) ? h("div", {clase: "agr-marca", estilo: {left: `${x(marca)}%`}, title: `Precio ahora: ${precio(marca)}`}, h("span", {}, precio(marca))) : null);
}

// Gráfico de velas en vivo de una señal abierta: velas de 1 min (6 h) o de 15 min (30 h) que lee el motor de Hyperliquid,
// incluida la que se está formando, con liquidación, stop, entrada, objetivos y precio de ahora, y los eventos marcados.
function graficoSenal(s) {
  const ref = s.agresiva || s.gemela;
  const zona = h("div", {});
  const caja = h("div", {clase: "agr-grafico"}, zona);
  function pintarGrafico() {
    const iv = intervalo.get(s.id) || "1m";
    const velas = (s.velas?.[iv] || []).filter((v) => v.every(Number.isFinite));
    const leyenda = h("div", {clase: "agr-grafico-leyenda", "aria-live": "off"},
      velas.length ? `Velas de ${iv === "1m" ? "1 min" : "15 min"} · la última se está formando · pasa el dedo para ver cada vela` : "");
    const botones = h("div", {clase: "periodos", role: "group", "aria-label": `Velas de ${s.coin}`},
      [["1m", "1 min"], ["15m", "15 min"]].map(([k, t]) => h("button", {type: "button", "aria-pressed": String(k === iv),
        onClick: () => { intervalo.set(s.id, k); pintarGrafico(); }}, t)));
    if (velas.length < 2 || !ref) {
      reemplazar(zona, h("div", {clase: "agr-grafico-cab"}, h("strong", {}, `Velas de ${s.coin}`), botones),
        h("div", {clase: "grafico-vacio"}, "El motor aún no ha leído las velas de esta señal (llegan en la siguiente pasada, cada minuto)."));
      return;
    }
    const niveles = [];
    if (s.agresiva && hay(s.agresiva.liq)) niveles.push({v: s.agresiva.liq, clase: "liq", texto: `Liquidación ${precio(s.agresiva.liq)}`});
    niveles.push({v: ref.stop, clase: "stop", texto: `${ref.toc ? "Stop (en la entrada)" : "Stop"} ${precio(ref.stop)}`});
    niveles.push({v: ref.entrada, clase: "entrada", texto: `Entrada ${precio(ref.entrada)}`});
    ref.objetivos.forEach((o, k) => niveles.push({v: o, clase: k < ref.toc ? "objetivo tocado" : "objetivo", texto: `O${k + 1} ${precio(o)}`}));
    if (hay(s.marca)) niveles.push({v: s.marca, clase: "ahora", texto: `Ahora ${precio(s.marca)}`});
    const vistos = new Set();
    const marcas = [{t: s.abierta_ms, v: ref.entrada, clase: "entrada", texto: `Entrada ${precio(ref.entrada)}`}];
    for (const e of s.eventos || []) {
      const clave = `${e.tipo}-${e.t}`;
      if (vistos.has(clave)) continue;
      vistos.add(clave);
      marcas.push({t: e.t + SEG["1m"] / 2, v: e.px, clase: e.tipo.startsWith("objetivo") ? "objetivo" : "stop",
        texto: `${SALIDA[e.tipo] || e.tipo} · ${precio(e.px)} (${e.pierna})`});
    }
    const {caja: g, fuera} = graficoVelas(velas, {seg: SEG[iv], niveles, marcas, entrada_t: s.abierta_ms, leyenda, formato: precio,
      etiqueta: `Velas de ${s.coin} con sus niveles`});
    reemplazar(zona, h("div", {clase: "agr-grafico-cab"}, h("strong", {}, `Velas de ${s.coin}`), botones), leyenda, g,
      fuera.length ? h("p", {clase: "muy-tenue"}, `Fuera del gráfico por lejanos: ${fuera.map((n) => n.texto).join(" · ")}`) : null);
  }
  pintarGrafico();
  return caja;
}

function pierna(nombre, p, extra) {
  if (!p) return h("div", {clase: "agr-pierna vacia"}, h("div", {clase: "agr-pierna-etq"}, nombre), h("p", {clase: "tenue"}, extra || "no se abrió"));
  return h("div", {clase: ["agr-pierna", p.liq_antes_que_stop ? "peligro" : null]},
    h("div", {clase: "agr-pierna-etq"}, nombre, " ", chip(`${p.apal}×`, p.apal >= 10 ? "mal" : "info", {punto: false})),
    h("div", {clase: "agr-pierna-v"}, resultado(p.neto_usd, 2, " $"), h("span", {clase: "tenue"}, hay(p.r_actual) ? ` · ${num(p.r_actual, 2)} R` : "")),
    listaDef([
      ["Entrada", precio(p.entrada)], ["Tamaño", `${num(p.sz, 6)} de ${num(p.sz0, 6)}`],
      ["Riesgo hasta el stop", hay(p.riesgo_pct) ? [`${pct(p.riesgo_pct, 2)} de la cuenta`, p.recortada ? h("span", {clase: "tenue"}, " · recortado: el margen no cabía") : ""] : "—"],
      ["Margen aislado", `${usd(p.margen_usd)} (al abrir ${usd(p.margen0)})`],
      ["Stop", `${precio(p.stop)} · a ${pct(p.dist_stop_pct, 2)}`],
      ["Liquidación", hay(p.liq) ? [`${precio(p.liq)} · a ${pct(p.dist_liq_pct, 2)}`, p.liq_antes_que_stop ? h("strong", {clase: "agr-liq-txt"}, " · ANTES que el stop") : ""] : "—"],
      ["Objetivos tocados", `${p.toc} de ${p.objetivos.length}`],
      ["Ya realizado", resultado(p.pnl_realizado_usd, 3, " $")], ["Sin realizar", resultado(p.upnl_usd, 3, " $")],
      ["Funding (en el margen)", resultado(p.funding_usd, 4, " $")],
    ]));
}

function abierta(s) {
  const [ladoTxt, ladoCls] = LADO[String(s.lado)] || ["?", null];
  const ref = s.agresiva || s.gemela;
  return h("article", {clase: "agr-pos"},
    h("header", {clase: "agr-pos-cab"}, h("strong", {}, s.coin), chip(ladoTxt, ladoCls, {punto: false}), chip(nombreRegla(s.regla), "info", {punto: false}),
      chip(`${num(s.horas, 1)} h`, null), chip(`stop ${pct(s.stop_pct, 2)}`, null, {titulo: "Distancia del stop al abrir"}),
      chip(`máx. ${s.apal_max_mercado}× en esta moneda`, null)),
    graficoSenal(s),
    ref ? escalera(s, ref) : null,
    h("div", {clase: "agr-piernas"}, pierna("Agresiva", s.agresiva, s.sin_agresiva), pierna("Gemela", s.gemela, s.sin_gemela)));
}

function abiertas(d) {
  const lis = d.abiertas || [];
  return seccion(titulo("Señales abiertas", "Cómo leer una señal abierta",
    "La línea muestra los niveles de la señal: liquidación (rojo), stop, entrada, el precio de ahora (marcador) y los cinco objetivos.",
    "En cada objetivo se cierra un 20 % (redondeado a lo que admite la moneda; si no llega a 10 $ se junta con el siguiente); al tocar el primero el stop pasa a la entrada.",
    "Si la liquidación queda antes que el stop, se avisa: llegar ahí cierra todo a mercado y se pierde casi todo el margen (Hyperliquid devuelve lo que sobre; si el precio salta, nada).",
    "Stop y liquidación se miran como en Hyperliquid, con el precio de marca: tienen que tocarlos la vela de Hyperliquid y la de Binance del mismo minuto. Una mecha solo de Hyperliquid no los salta."),
  lis.length ? lis.map(abierta) : vacio(`Ninguna abierta. Se miran ${(d.universo || []).length || "las"} monedas con más volumen al cerrar cada vela de 15 min.`));
}

// ---------------------------------------------------------------- cerradas
function cerradas(d) {
  return seccion(titulo("Cerradas", "Operaciones cerradas", "Cada fila es una señal: su resultado en la cuenta agresiva y en la gemela.",
    "«% cuenta» es lo que ganó o perdió la agresiva respecto a lo que valía la cuenta al abrir. R es el resultado dividido por lo que se arriesgaba hasta el stop."),
  tabla([
    {t: "Moneda", v: (x) => h("strong", {}, x.coin)},
    {t: "Lado", v: (x) => (LADO[String(x.lado)] || ["?"])[0]},
    {t: "Regla", v: (x) => nombreRegla(x.regla)},
    {t: "Abierta", v: (x) => fechaMs(x.abierta_ms)},
    {t: "Salida agresiva", v: (x) => (x.agresiva ? salida(x.agresiva) : h("span", {clase: "tenue", title: x.sin_agresiva || ""}, "no se abrió"))},
    {t: "Apal.", v: (x) => (x.agresiva ? `${x.agresiva.apal}×` : "—"), der: true},
    {t: "Agresiva", v: (x) => (x.agresiva ? resultado(x.agresiva.pnl_usd, 2, " $") : "—"), der: true},
    {t: "% cuenta", v: (x) => (x.agresiva ? conSigno(x.agresiva.pct_cuenta, 2, " %") : "—"), der: true},
    {t: "Riesgo", v: (x) => (x.agresiva && hay(x.agresiva.riesgo_pct) ? pct(x.agresiva.riesgo_pct, 1) : "—"), der: true},
    {t: "Gemela R", v: (x) => (x.gemela ? conSigno(x.gemela.r, 2) : h("span", {clase: "tenue", title: x.sin_gemela || ""}, "—")), der: true},
    {t: "Objetivos", v: (x) => (x.gemela ? `${x.gemela.objetivos_tocados}/5` : "—"), der: true},
    {t: "Etapa", v: (x) => num(x.etapa, 0), der: true},
  ], d.cerradas || [], {vacioTexto: "Aún no se ha cerrado ninguna señal."}));
}

// ---------------------------------------------------------------- por regla
function filaRegla(nombre, r) {
  const a = r.agresiva || {}, g = r.gemela || {};
  return {nombre, n: g.n || 0, g, a};
}

function porRegla(d) {
  const filas = Object.values(d.resumen?.por_regla || {}).map((r) => filaRegla(r.nombre, r));
  return seccion(titulo("Por regla de entrada", "Cada regla, por separado",
    "Ruptura con volumen: cierre por encima del máximo (o debajo del mínimo) de las 20 velas previas con volumen alto y la media de 50 a favor.",
    "Retroceso a la media: en tendencia, la vela baja hasta la media de 20 y cierra por encima (al revés en cortos).",
    "Giro tras exceso: RSI por debajo de 25 (o encima de 75) y vuelta, con el precio aún lejos de la media de 50.",
    "Con menos de 30 cerradas por regla no es concluyente; lo serio empieza hacia las 100."),
  tabla([
    {t: "Regla", v: (x) => h("strong", {}, x.nombre)},
    {t: "Cerradas", v: (x) => num(x.n, 0), der: true},
    {t: "Acierto", v: (x) => (x.n ? pct(x.g.acierto_pct) : "—"), der: true},
    {t: "R medio (gemela)", v: (x) => (x.n ? conSigno(x.g.r_media, 3) : "—"), der: true},
    {t: "Gemela $", v: (x) => (x.n ? resultado(x.g.pnl_usd, 2, " $") : "—"), der: true},
    {t: "Agresiva $", v: (x) => (x.a.n ? resultado(x.a.pnl_usd, 2, " $") : "—"), der: true},
    {t: "Liquidaciones", v: (x) => num(x.a.liquidaciones || 0, 0), der: true},
    {t: "Veredicto", v: (x) => (x.n < 30 ? chip("pocos casos", "aviso") : x.g.r_media > 0 ? chip("positiva", "ok") : chip("negativa", "mal"))},
  ], filas, {vacioTexto: "Sin reglas activas."}));
}

// ---------------------------------------------------------------- historia (prueba atrás)
function mc(m, etq) {
  if (!m) return h("p", {clase: "tenue"}, `${etq}: sin operaciones suficientes.`);
  return h("div", {clase: "agr-mc"}, h("h3", {}, etq), listaDef([
    ["Probabilidad de quebrar", h("strong", {clase: m.prob_quiebra_pct >= 20 ? "agr-liq-txt" : null}, pct(m.prob_quiebra_pct, 1))],
    [`${m.unidad === "días" ? "Días" : "Operaciones"} hasta quebrar (mediana)`, (() => {
      const v = m.mediana_pasos_hasta_quiebra ?? m.mediana_operaciones_hasta_quiebra;
      return hay(v) ? num(v, 0) : "no quiebra";
    })()],
    ["Probabilidad de acabar perdiendo", pct(m.prob_acabar_perdiendo_pct, 1)],
    ["Final típico (mediana)", `${num(m.final_mediana_x, 2)} × la cuenta`],
    ["Final malo / bueno (10 % / 90 %)", `${num(m.final_p10_x, 2)} × / ${num(m.final_p90_x, 2)} ×`],
    ["Peor caída típica", pct(m.caida_max_mediana_pct, 1)],
  ]), h("p", {clase: "muy-tenue"}, m.unidad === "días"
    ? `${num(m.corridas, 0)} secuencias de ${m.pasos_por_corrida} días sorteados de los reales de la prueba (cada día con todas sus operaciones: así se respeta que suelen ir juntas).`
    : `${num(m.corridas, 0)} secuencias de ${m.operaciones_por_corrida} operaciones sorteadas de las reales de la prueba.`));
}

function historia(d) {
  const x = d.historia;
  if (!x) return seccion("Prueba con historia", vacio("Aún no se ha pasado. Se lanza con: python -m agresiva.historia"));
  const t = x.total || {}, a = t.agresiva || {}, g = t.gemela || {};
  const filas = Object.values(x.por_regla || {}).map((r) => filaRegla(r.nombre, r));
  return [
    seccion(titulo("Prueba con historia", "Qué es esta prueba",
      `Las mismas reglas y la misma cuenta sobre ${x.dias} días de velas de 15 min de Binance (${x.desde} a ${x.hasta}). ${x.universo_diario ? `Cada día se operan las ${x.universo_diario} monedas de más volumen de los 7 días anteriores (${x.monedas.length} distintas en total).` : `${x.monedas.length} monedas.`}`,
      `Limitaciones: ${x.limitaciones.join("; ")}.`),
    h("section", {clase: "embudo kpis"},
      kpi("Operaciones", num(x.operaciones, 0), `${num(x.senales, 0)} señales · ${num(x.sin_hueco, 0)} sin hueco`),
      kpi("Gemela", resultado(g.pnl_usd, 2, " $"), `R medio ${num(g.r_media, 3)} · acierto ${pct(g.acierto_pct)}`),
      kpi("Agresiva", resultado(a.pnl_usd, 2, " $"), `riesgo medio ${pct(a.riesgo_pct_media, 1)} · ${num(a.liquidaciones || 0, 0)} liquidaciones · ${num(a.stops || 0, 0)} stops`, a.pnl_usd < 0 ? "agr-mal" : null),
      kpi("Quiebras", num(x.quiebras, 0), x.quiebras ? `etapas de ${(x.dias_por_etapa_quebrada || []).map((v) => num(v, 1)).join(", ")} días` : "no quebró", x.quiebras ? "agr-mal" : null)),
    h("p", {clase: "muy-tenue"}, `Generada ${x.generado} · fuente: ${x.fuente}`)),
    seccion("Por regla (historia)", tabla([
      {t: "Regla", v: (r) => h("strong", {}, r.nombre)}, {t: "Cerradas", v: (r) => num(r.n, 0), der: true},
      {t: "Acierto", v: (r) => pct(r.g.acierto_pct), der: true}, {t: "R medio", v: (r) => conSigno(r.g.r_media, 3), der: true},
      {t: "Gemela $", v: (r) => resultado(r.g.pnl_usd, 2, " $"), der: true}, {t: "Agresiva $", v: (r) => resultado(r.a.pnl_usd, 2, " $"), der: true},
      {t: "Liquidaciones", v: (r) => num(r.a.liquidaciones || 0, 0), der: true},
    ], filas)),
    seccion(titulo("Simulación de ruina", "Qué es la simulación de ruina",
      "Se sortean al azar, con reposición, los días reales de la prueba (lo que ganó o perdió la cuenta cada día, en %) y se encadenan miles de veces.",
      "Da una idea de lo probable que es quebrar si el futuro se parece a la prueba. No es una promesa: si el mercado cambia, cambia todo."),
    h("div", {clase: "agr-mcs"}, mc(x.monte_carlo?.agresiva, "Cuenta agresiva"), mc(x.monte_carlo?.gemela, "Gemela (tamaño normal)"))),
  ];
}

// ---------------------------------------------------------------- reglas del juego
function juego(d) {
  const c = d.criterios || {};
  return [
    seccion("Reglas del juego", listaDef([
      ["Cuenta", `${usd(c.cuenta_inicial_usd, 0)} ficticios, aparte de todo lo demás`],
      ["Velas", "15 min (las de 5 min se comen en comisiones)"],
      ["Monedas", `las ${c.universo_n} de más volumen en Hyperliquid (mínimo ${num(c.volumen_min_usd / 1e6, 0)} M$ al día): ${(d.universo || []).join(", ") || "—"}`],
      ["Agresiva", `riesgo fijo del ${c.riesgo_pct} % de la cuenta hasta el stop (con comisiones). El apalancamiento (${c.apalancamiento}×, recortado al máximo de cada moneda y a sus tramos) solo decide el margen aislado: como mucho ${c.margen_max_pct} % por operación y ${c.margen_total_max_pct} % en total; si no cabe, se arriesga menos. Máx. ${c.max_abiertas} abiertas.`],
      ["Órdenes", `mínimo ${usd(c.min_orden_usd, 0)} por orden, como en Hyperliquid; cantidades redondeadas a lo que admite cada moneda`],
      ["Reglas de entrada", (c.reglas || []).map(nombreRegla).join(" · ")],
      ["Stop", `${c.stop_atr} × ATR(14), entre ${c.stop_min_pct} % y ${c.stop_max_pct} %`],
      ["Objetivos", `${(c.objetivos_r || []).join(" / ")} veces la distancia del stop; 20 % en cada uno; stop a la entrada tras el primero`],
      ["Cierre por tiempo", `${c.horas_max} h`],
      ["Liquidación", "si llega antes que el stop, se cierra todo contra el libro y se conserva el margen que sobre (como en Hyperliquid); si el precio salta por debajo de 2/3 del mantenimiento, rescate: se pierde todo el margen"],
      ["Disparo", "stop y liquidación con precio de marca aproximado: los tienen que tocar la vela de 1 min de Hyperliquid y la de Binance del mismo minuto"],
      ["Gemela", `misma señal con riesgo del ${c.gemela_riesgo_pct} % hasta el stop, hasta ${c.gemela_apal_max}×`],
      ["Costes", `comisión ${c.comision_taker_pct} % a mercado y ${c.comision_maker_pct} % en objetivos; deslizamiento ${c.desliz_pct} % en stops; funding real pagado cada hora (dentro del margen aislado: mueve la liquidación)`],
      ["Frenos", `pausa ${c.pausa_freno_h} h al perder ${c.freno_caida_pct} %; sin entradas el resto del día al perder ${c.freno_diario_pct} % en el día; quiebra por debajo del ${c.quiebra_pct} %`],
      ["Real", "imposible: no hay código de órdenes y el motor se para si el bot no está en simulado"],
    ])),
    (d.cambios_reglas || []).length ? seccion("Cambios de reglas", h("ul", {clase: "lista-simple"},
      d.cambios_reglas.map((x) => h("li", {}, h("strong", {}, fecha(x.ts)), ` · ${x.texto}`)))) : null,
    seccion("Últimas señales", tabla([
      {t: "Cuándo", v: (x) => fechaMs(x.t + 900000)}, {t: "Moneda", v: (x) => h("strong", {}, x.coin)},
      {t: "Lado", v: (x) => (LADO[String(x.lado)] || ["?"])[0]}, {t: "Regla", v: (x) => nombreRegla(x.regla)},
      {t: "Precio", v: (x) => precio(x.precio), der: true},
    ], d.ultimas_senales || [], {vacioTexto: "Sin señales desde que arrancó el motor."}),
    (d.descartadas || []).length ? h("details", {clase: "plegable"}, h("summary", {}, "Señales que no se abrieron"),
      h("div", {clase: "cuerpo"}, h("ul", {clase: "lista-simple"}, d.descartadas.map((x) => h("li", {}, `${x.coin} · ${nombreRegla(x.regla)}: ${x.motivo}`))))) : null),
    (d.reinicios || []).length ? seccion("Etapas anteriores", tabla([
      {t: "Etapa", v: (x) => num(x.etapa, 0)}, {t: "Desde", v: (x) => fecha(x.inicio)}, {t: "Hasta", v: (x) => fecha(x.fin)},
      {t: "Días", v: (x) => num((x.fin - x.inicio) / 86400, 1), der: true}, {t: "Final", v: (x) => usd(x.final_usd), der: true},
      {t: "Cómo acabó", v: (x) => x.estado_final}, {t: "Peor caída", v: (x) => pct(x.caida_max_pct), der: true},
    ], d.reinicios)) : null,
    (d.alertas || []).length ? seccion("Avisos del motor", h("ul", {clase: "lista-simple"}, d.alertas.map((x) => h("li", {}, `${fecha(x.ts)} · ${x.mensaje}`)))) : null,
  ];
}

// ---------------------------------------------------------------- montaje
function pintar() {
  if (!raiz) return;
  const d = datos;
  if (!d || !d.ts) {
    reemplazar(raiz, h("h1", {}, "Cuenta agresiva"), vacio("El motor de la cuenta agresiva aún no ha escrito nada. Arranca con INICIAR.bat o con: python -m agresiva.motor"));
    return;
  }
  reemplazar(raiz, h("div", {clase: "agresiva"}, cabecera(d), kpis(d),
    pestanasVista("agresiva", [
      ["resumen", "Resumen", () => [seccion("Evolución", h("div", {clase: "agr-curvas"}, curva(d, 1, "Cuenta agresiva"), curva(d, 2, "Gemela"))), frenos(d), comparativa(d)]],
      ["abiertas", `Abiertas (${(d.abiertas || []).length})`, () => abiertas(d)],
      ["cerradas", "Cerradas", () => cerradas(d)],
      ["reglas", "Por regla", () => porRegla(d)],
      ["historia", "Prueba con historia", () => historia(d)],
      ["juego", "Reglas del juego", () => juego(d)],
    ], "Secciones de la cuenta agresiva"),
    h("p", {clase: "muy-tenue"}, "Dinero ficticio con precios reales. Con menos de 30 cierres por regla nada es concluyente. Este experimento no decide nada del bot de ballenas ni puede pasar a real.")));
}

async function cargar() {
  datos = await obtener("/api/agresiva");
  cargado = Date.now();
}

export const vista = {
  async entrar(el) {
    raiz = el;
    reemplazar(el, h("p", {clase: "cargando"}, "Cargando la cuenta agresiva…"));
    try {
      await cargar();
    } catch (e) {
      reemplazar(el, errorCarga(`No se pudo leer la cuenta agresiva: ${e.message}`));
      return;
    }
    pintar();
  },
  async actualizar() {        // el sondeo general llega cada pocos segundos: aquí cada 15 s con señales abiertas, si no cada 30 s
    if (!raiz || Date.now() - cargado < ((datos?.abiertas || []).length ? 15000 : 30000)) return;
    try { await cargar(); } catch { return; }
    const activo = document.activeElement;
    if (raiz && !(activo && raiz.contains(activo) && activo.tagName === "SUMMARY")) pintar();
  },
  salir() { raiz = null; },
};
