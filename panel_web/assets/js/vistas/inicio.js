// INICIO, como una app de bolsa: una cifra protagonista (el saldo, rotulado con su modo), su gráfico, lo que requiere
// atención y la lista de posiciones. Lo secundario (límites, cerebro, camino a real, controles) queda plegado al final.

import {cifraViva} from "../anim.js";
import {SOLO_LECTURA, enviar, esperarResultado, obtener} from "../api.js";
import {chip, escribiendo, h, pestanasVista, plegable, reemplazar, seccion, tabla, vacio} from "../dom.js";
import {estado} from "../estado.js";
import {conSigno, fecha, frescura, hace, hay, lado, num, pct, precio, resultado, usd} from "../formato.js";
import {graficoLinea} from "../grafico.js";
import {info, titulo} from "../info.js";
import {crearNucleo} from "../nucleo.js";
import {cerrarMesa, pestanaMesa} from "./mesa.js";

let raiz = null;
let nucleo = null;                 // núcleo 3D: se crea una vez por visita y se reutiliza en cada repintado
let accionEnCurso = null;          // mensaje del último comando enviado (lo confirma el bot)
let periodo = "1D";                // solo en memoria: no se guarda nada en el navegador

const RECIENTE_CONCILIACION = 300; // s: más vieja que esto -> la protección se muestra como «desconocida»
const PERIODOS = {"1D": [86400, "en 24 h"], "1S": [7 * 86400, "en 7 días"], Todo: [Infinity, null]};

function atenciones(d) {
  const b = d.bot || {};
  const out = [];
  if (!b.ts) out.push(["mal", "El bot no ha escrito datos", "¿Está apagado? Arranca el bot (INICIAR.bat) y vuelve a mirar."]);
  else if (!d.bot_vivo) out.push(["mal", "El bot no da señales", `Su última foto es de ${hace(b.ts, d.ahora)}. Puede estar parado o bloqueado.`]);
  if (b.ts && b.datos_frescos === false) out.push(["aviso", "Precios del mercado obsoletos", "Sin precios frescos el bot no abre operaciones."]);
  if (b.ts && b.conciliacion_ok === false) out.push(["mal", "La cuenta no cuadra con el registro del bot", "Mira la sección Observabilidad y las alertas."]);
  for (const [m, motivo] of Object.entries(b.sin_stop || {})) out.push(["mal", `${m}: stop NO confirmado`, motivo]);
  for (const [m, c] of Object.entries(b.congelados || {})) out.push(["aviso", `${m}: mercado congelado`, c.motivo]);
  for (const [m, motivo] of Object.entries(b.riesgo_liquidacion || {})) out.push(["mal", `${m}: riesgo de liquidación`, motivo]);
  for (const x of b.bloqueos || []) out.push(["aviso", "Entradas nuevas bloqueadas", x]);
  if ((b.externas || []).length) out.push(["aviso", `${b.externas.length} posición(es) externa(s)`, "El bot no las toca; cuentan como riesgo."]);
  const sinRiesgo = b.exposicion?.riesgo_desconocido || [];
  if (sinRiesgo.length) out.push(["mal", `Riesgo desconocido: ${sinRiesgo.join(", ")}`,
    "No se sabe cuánto arriesga esa posición (falta su stop o su riesgo). El bot no abre nada nuevo hasta saberlo."]);
  if ((b.posiciones_legado || []).length) out.push(["aviso", "Posiciones antiguas sin identificar", b.posiciones_legado.join(", ")]);
  if (b.cerebro?.error) out.push(["aviso", "Modelo del cerebro no disponible", b.cerebro.error]);
  const inc = d.sistema_resumen?.incidentes_activos;
  if (inc) out.push(["mal", `${inc} incidente(s) técnico(s) activo(s)`, h("a", {href: "#/sistema"}, "Ver en Observabilidad")]);
  return out;
}

function proteccion(p, b, ahora) {
  const conc = b.conciliacion_ts;
  if (!hay(conc) || ahora - conc > RECIENTE_CONCILIACION) return chip("Stop desconocido", "aviso", {titulo: "sin conciliación reciente"});
  if (!p.stop_verificado) return chip("Stop SIN CONFIRMAR", "mal");
  return chip("Stop confirmado", "ok", {titulo: p.stop_verificado_ts ? `verificado ${hace(p.stop_verificado_ts, ahora)}` : null});
}

/** Serie del saldo para el periodo: historial (cada 5 min) más la lectura actual si es más nueva. */
function serie(b, ahora, per) {
  const [ventana] = PERIODOS[per];
  const puntos = (b.historial_saldo || []).filter(([t, v]) => hay(t) && hay(v) && ahora - t <= ventana).map(([t, v]) => [t, Number(v)]);
  const tAct = b.saldo_ts || b.ts;
  if (hay(b.saldo) && hay(tAct) && (!puntos.length || tAct > puntos[puntos.length - 1][0])) puntos.push([tAct, Number(b.saldo)]);
  return puntos;
}

function variacion(desde, hasta, texto) {
  const dif = hasta - desde;
  const rel = desde ? dif / desde * 100 : null;
  return [resultado(dif), h("span", {clase: ["num", dif > 0 ? "sube" : dif < 0 ? "baja" : null]}, `(${conSigno(rel, 2, " %")})`),
    texto ? h("span", {clase: "tenue"}, texto) : null];
}

function grafico(puntos, cifra, linea) {
  const vs = puntos.map((p) => p[1]);
  return graficoLinea(puntos, {cifra, linea, valor: usd, pie: (v0, vi, t) => variacion(v0, vi, fecha(t)),
    etiqueta: `Evolución del saldo: de ${usd(vs[0])} a ${usd(vs[vs.length - 1])}`});
}

/** De dónde sale el saldo: lo ya cerrado en el periodo y lo que van las abiertas ahora (en Inicio solo se listan estas). */
function desglose(d, per) {
  const b = d.bot || {};
  const c = d.cerradas?.[per];
  if (b.modo === "shadow" || !c) return null;
  const pos = b.posiciones || [];
  const abiertas = pos.some((p) => !hay(p.pnl_no_realizado)) ? null : pos.reduce((s, p) => s + Number(p.pnl_no_realizado), 0);
  return h("div", {clase: "desglose"},
    h("span", {}, h("span", {clase: "tenue"}, `Cerradas ${PERIODOS[per][1] || "desde el inicio"} (${c.n}): `), resultado(c.pnl),
      c.desconocidas ? h("span", {clase: "tenue"}, ` · ${c.desconocidas} sin resultado`) : null),
    h("span", {}, h("span", {clase: "tenue"}, `Abiertas ahora (${pos.length}): `), resultado(abiertas)));
}

function portada(d) {
  const b = d.bot || {};
  const modo = b.modo;
  const etiquetaSaldo = modo === "real" ? "Valor de la cuenta (REAL)" : modo === "shadow" ? "Saldo teórico (shadow)" : "Saldo SIMULADO (ficticio)";
  const claveSaldo = modo === "real" ? "saldo_real" : modo === "shadow" ? "saldo_shadow" : "saldo_simulado";
  const ahora = estado.error ? Date.now() / 1000 : d.ahora;
  const puntos = serie(b, ahora, periodo);
  const [, textoPeriodo] = PERIODOS[periodo];
  const cifra = h("div", {clase: "cifra"}, usd(b.saldo));
  const linea = h("div", {clase: "variacion", "aria-live": "off"},
    puntos.length >= 2 ? variacion(puntos[0][1], puntos[puntos.length - 1][1], textoPeriodo || `desde ${fecha(puntos[0][0])}`)
      : h("span", {clase: "tenue"}, "Variación: — sin historial suficiente"));
  const f = frescura(b.saldo_ts, d.ahora, {retraso: 180, obsoleto: 900});
  const periodos = h("div", {clase: "periodos", role: "group", "aria-label": "Periodo del gráfico"},
    Object.keys(PERIODOS).map((p) => h("button", {type: "button", "aria-pressed": String(p === periodo),
      onClick: () => { periodo = p; pintar(); }}, p)));
  return h("section", {clase: "portada", "aria-label": "Saldo"},
    h("div", {clase: "etiqueta"}, etiquetaSaldo, info(claveSaldo, etiquetaSaldo)),
    cifra, linea, desglose(d, periodo),
    puntos.length >= 2 ? grafico(puntos, cifra, linea)
      : h("div", {clase: "grafico-vacio"}, "Aún no hay historial suficiente para dibujar el gráfico (se guarda una muestra cada 5 min)."),
    periodos,
    h("p", {clase: "muy-tenue"}, modo === "shadow" ? "Valor de configuración: en shadow no hay cuenta."
      : `${modo === "simulado" ? "Dinero ficticio con precios reales · " : ""}saldo leído ${f.texto}`));
}

/** Tubería de idea a dinero real: cada paso con su cifra y una barra (escala logarítmica) que se va estrechando. */
function embudo(b) {
  const inv = b.investigacion || {};
  const est = b.estrategias || [];
  const real = est.filter((e) => e.etapa === "real_habilitado").length;
  const pasos = [
    ["Ideas", inv.probadas_total, "probadas por la noche"],
    ["Variantes", inv.variantes_totales, "con el laboratorio"],
    ["Aspirantes", (inv.aspirantes || []).length, "seguidas en vivo"],
    ["Superan el lab", b.motor?.validadas ?? 0, "con evidencia"],
    ["En simulado", est.filter((e) => e.activa).length, "estrategias activas", "destacado"],
    ["En real", real, "solo con tu aprobación"],
  ];
  const max = Math.max(1, ...pasos.map((p) => Number(p[1]) || 0));
  const ancho = (v) => `${Math.max(3, Math.log10((Number(v) || 0) + 1) / Math.log10(max + 1) * 100)}%`;
  return h("section", {clase: "embudo", "aria-label": "Tubería: de idea a dinero real"},
    pasos.map(([etq, v, pie, clase]) => h("div", {clase: ["paso", clase]},
      h("div", {clase: "etq"}, etq),
      h("div", {clase: ["v", clase === "destacado" ? "vivo" : null]}, hay(v) && (v || etq !== "En real") ? cifraViva(`embudo.${etq}`, v, (n) => num(n, 0)) : "—"),
      h("div", {clase: "barra-paso"}, h("span", {estilo: {width: ancho(v)}})),
      h("div", {clase: "pie"}, pie))));
}

// ---------------------------------------------------------------- datos lentos de la portada (cada 5 min)
const lento = {lab: null, objetivo: null, ts: 0, cargando: false};
async function cargarLento() {
  if (lento.cargando || Date.now() - lento.ts < 300000) return;
  lento.cargando = true;
  const [lab, obj] = await Promise.allSettled([obtener("/api/laboratorio"), obtener("/api/objetivo")]);
  lento.lab = lab.status === "fulfilled" ? lab.value : lento.lab;
  lento.objetivo = obj.status === "fulfilled" ? obj.value : lento.objetivo;
  lento.ts = Date.now();
  lento.cargando = false;
  pintar();
}

/** Lo que necesita una decisión TUYA. Solo informa y lleva a la sección: el panel no aprueba nada. */
function decisiones(d) {
  const b = d.bot || {};
  const tarjetas = [];
  const t = (tipo, clase, que, texto, href) => tarjetas.push(h("a", {clase: ["decision", clase], href},
    h("div", {clase: "etq"}, tipo), h("div", {clase: "titulo"}, que), h("div", {clase: "tenue"}, texto)));
  for (const e of b.estrategias || []) {
    if (e.etapa === "apta_revision") t("Promoción", "aviso", `${e.clave}: apta para revisión`, "Cumple los requisitos. Pasar a real lo decides tú con promocion.py.", "#/estrategias");
  }
  for (const a of b.investigacion?.aspirantes || []) {
    if (a.estado === "lista_revision") t("Investigación", "aviso", "Idea lista para revisar", a.descripcion || "Aguantó en vivo.", "#/aprendizaje");
  }
  for (const [k, v] of Object.entries(b.vigilancia || {})) {
    if (v?.estado === "degradada") t("Vigilancia", "mal", `${k}: rinde peor de lo esperado`, "El bot ya le ha bajado el tamaño a la mitad.", "#/estrategias");
  }
  if ((b.bloqueos || []).includes("pausa manual")) t("Control", "aviso", "Entradas en pausa", "Pausaste las entradas nuevas. Reanúdalas en Control.", "#/inicio");
  for (const [k, p] of Object.entries(lento.lab?.preregistro || {})) {
    if (p?.estado === "confirmada" || p?.estado === "rechazada") {
      t("Preregistro", p.estado === "confirmada" ? "ok" : "mal", `${k}: ${p.estado}`, "Veredicto definitivo con datos nuevos. Decide si seguir con ella.", "#/estrategias");
    }
  }
  return seccion(titulo("Necesita tu decisión", "Necesita tu decisión",
    "Aquí aparece lo que solo tú puedes decidir: estrategias aptas para dinero real, ideas que han aguantado, avisos de la vigilancia o hipótesis con veredicto.",
    "El panel solo informa: ninguna tarjeta aprueba nada. El paso a real sigue siendo promocion.py más tu aprobación."),
  tarjetas.length ? h("div", {clase: "decisiones"}, tarjetas) : h("p", {clase: "vacio"}, "Nada pendiente. El bot sigue acumulando evidencia."));
}

/** Resumen del informe diario del analista (las cifras las calcula código; la IA solo las comenta). */
function informeDia() {
  const inf = lento.objetivo?.analista;
  const hall = (inf?.hallazgos || []).slice(0, 3);
  return seccion(titulo("Informe del día", "Informe del día",
    "Lo genera el analista una vez al día con los datos del bot. Las cifras las calcula el código; la IA solo las explica y nunca opera."),
  !lento.objetivo ? h("p", {clase: "cargando"}, "Cargando…")
    : hall.length ? [h("ul", {clase: "lista-simple"}, hall.map((x) => h("li", {}, typeof x === "string" ? x : x.texto))),
      h("p", {}, h("a", {href: "#/objetivo"}, `Ver el informe completo (${fecha(inf.ts)}) →`))]
      : h("p", {clase: "vacio"}, "Aún no hay informe de hoy."));
}

function bloqueAtencion(d, at) {
  const b = d.bot || {};
  if (!at.length) {
    return h("section", {clase: "seccion", "aria-label": "Estado"}, h("ul", {clase: "atencion"}, h("li", {clase: "ok"}, h("div", {},
      h("div", {clase: "que"}, "✓ Todo en orden"),
      h("div", {clase: "tenue"}, `Bot activo, datos frescos y ${b.operando ? "entradas permitidas" : "entradas en pausa"}.`)))));
  }
  return seccion("Requiere tu atención",
    h("ul", {clase: "atencion"}, at.map(([tipo, que, detalle]) =>
      h("li", {clase: tipo}, h("div", {}, h("div", {clase: "que"}, tipo === "mal" ? "⚠ " : "", que), h("div", {clase: "tenue"}, detalle))))));
}

function filaPosicion(p, b, ahora) {
  const explora = p.exploracion_amplia || p.explorando;
  return h("li", {}, h("a", {clase: "fila", href: `#/operacion/${encodeURIComponent(p.trade_id)}`,
    "aria-label": `${p.moneda}, ${lado(p.lado)}: ver la operación`},
    h("span", {clase: ["avatar", p.lado === "L" ? "largo" : p.lado === "S" ? "corto" : null], "aria-hidden": "true"}, String(p.moneda || "?").slice(0, 4)),
    h("div", {clase: "centro"},
      h("div", {clase: "titulo"}, p.moneda),
      h("div", {clase: "sub"}, h("span", {}, `${lado(p.lado)} ${num(p.tam, 4)}`),
        h("span", {title: p.precio_mark_ts ? `entrada → precio de marca (${hace(p.precio_mark_ts, ahora)})` : "entrada → precio de marca (sin hora)"},
          `${precio(p.entrada)} → ${precio(p.precio_mark)}`),
        p.cartera_funding ? h("span", {}, "cartera de funding") : explora ? h("span", {}, "exploración") : null)),
    h("div", {clase: "derecha"},
      h("div", {clase: "titulo"}, resultado(p.pnl_no_realizado)),
      h("div", {clase: "sub"}, h("span", {}, `stop ${precio(p.sl)}${hay(p.tp1) ? ` · obj. 1 ${precio(p.tp1)}${p.tp1_hecho ? " ✓" : ""}` : ""}${hay(p.tpf) ? ` · obj. ${hay(p.tp1) ? "2 " : ""}${precio(p.tpf)}` : ""}`), proteccion(p, b, ahora)))));
}

function posiciones(d) {
  const b = d.bot || {};
  const pos = b.posiciones || [];
  const maxPos = b.efectiva?.riesgo?.max_posiciones_abiertas;
  const cuerpo = [h("div", {clase: "encabezado"}, h("h2", {}, "Posiciones ", info("stop_verificado", "stop verificado")),
    h("span", {clase: "tenue"}, `${pos.length}${hay(maxPos) ? ` de ${maxPos}` : ""}`))];
  if (pos.length && b.modo === "simulado") cuerpo.push(h("p", {clase: "muy-tenue"}, "Toca una posición para ajustar su stop u objetivo."));
  cuerpo.push(pos.length ? h("ul", {clase: "lista"}, pos.map((p) => filaPosicion(p, b, d.ahora)))
    : vacio(b.modo === "shadow" ? "Modo shadow: el bot no tiene posiciones (solo apunta lo que haría)." : "No hay posiciones abiertas."));
  if ((b.shadow_abiertas || []).length) {
    cuerpo.push(h("h3", {}, "Intenciones shadow abiertas (sin órdenes, resultados modelados)"),
      h("ul", {clase: "lista"}, b.shadow_abiertas.map((x) => h("li", {}, h("div", {clase: "fila"},
        h("span", {clase: ["avatar", x.lado === "L" ? "largo" : "corto"], "aria-hidden": "true"}, String(x.moneda || "?").slice(0, 4)),
        h("div", {clase: "centro"}, h("div", {clase: "titulo"}, x.moneda), h("div", {clase: "sub"}, `${lado(x.lado)} · ${x.estrategia || "—"}`)),
        h("div", {clase: "derecha"}, h("div", {clase: "sub"}, hace(x.ts, d.ahora))))))));
  }
  return h("section", {clase: "seccion"}, cuerpo);
}

function tarjeta(etiqueta, clave, valor, pie) {
  return h("div", {clase: "tarjeta"},
    h("div", {clase: "etiqueta"}, etiqueta, clave ? info(clave, etiqueta) : null),
    h("div", {clase: "valor"}, valor), pie ? h("div", {clase: "pie"}, pie) : null);
}

function resumen(d) {
  const b = d.bot || {};
  const pos = b.posiciones || [];
  const abiertos = pos.map((p) => p.pnl_no_realizado);
  const pnlAbierto = !pos.length ? 0 : abiertos.every(hay) ? abiertos.reduce((a, x) => a + x, 0) : null;
  const dia = b.limites?.dia || {};
  const hoyUsd = hay(b.saldo) && hay(b.saldo_inicio_dia) ? b.saldo - b.saldo_inicio_dia : null;
  const ra = b.limites?.riesgo_abierto || {};
  return seccion("Resumen", h("div", {clase: "resumen"},
    tarjeta("Hoy (UTC)", "resultado_hoy", resultado(hoyUsd), hay(dia.valor_pct) ? `${pct(dia.valor_pct)} · límite ${pct(dia.limite_pct, 0)}` : null),
    tarjeta("Resultado abierto", "pnl_abierto", pos.length ? resultado(pnlAbierto) : h("span", {clase: "tenue"}, "sin posiciones"), null),
    b.modo === "shadow" ? null : tarjeta("Margen libre", "margen_libre", usd(b.libre), null),
    tarjeta("Riesgo abierto", "riesgo_abierto", pct(ra.valor_pct), hay(ra.limite_pct) ? `máximo ${pct(ra.limite_pct, 1)}` : null),
    tarjeta("Operaciones hoy", null, `${b.limites?.operaciones_hoy?.valor ?? "—"}`, hay(b.limites?.operaciones_hoy?.limite) ? `de ${b.limites.operaciones_hoy.limite}` : null),
    tarjeta("Entradas", null, b.ts ? (b.operando ? "Permitidas" : "En pausa") : "—", (b.bloqueos || []).length ? `${b.bloqueos.length} bloqueo(s)` : null)));
}

function avisosRecientes(d) {
  const al = (d.bot?.alertas || []).slice(0, 5);
  return h("section", {clase: "seccion"},
    h("div", {clase: "encabezado"}, h("h2", {}, "Avisos recientes"), h("a", {href: "#/actividad"}, "Ver actividad")),
    al.length ? h("ul", {clase: "lista"}, al.map((a) => h("li", {}, h("div", {clase: "fila"},
      h("div", {clase: "centro"}, h("div", {}, a.mensaje), h("div", {clase: "sub"}, `${fecha(a.ts)} · ${hace(a.ts, d.ahora)}`)),
      chip(a.severidad === "error" ? "error" : "aviso", a.severidad === "error" ? "mal" : "aviso")))))
      : vacio("Sin avisos recientes."));
}

function limites(b) {
  const l = b.limites || {};
  const fila = (nombre, valor, limite, texto) => {
    const uso = hay(valor) && hay(limite) && limite !== 0 ? Math.min(100, Math.max(0, valor / limite * 100)) : 0;
    return h("div", {clase: "limite"},
      h("div", {clase: "acciones"}, h("span", {}, nombre), h("span", {clase: "muy-tenue"}, texto)),
      h("div", {clase: "barra", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(Math.round(uso)), "aria-label": nombre},
        h("div", {clase: ["relleno", uso >= 90 ? "mal" : uso >= 60 ? "aviso" : null], estilo: {width: `${uso}%`}})));
  };
  return plegable("Límites de pérdida y de actividad", false,
    fila("Pérdida del día", l.dia?.valor_pct < 0 ? l.dia.valor_pct : 0, l.dia?.limite_pct, `${pct(l.dia?.valor_pct)} de ${pct(l.dia?.limite_pct, 0)}`),
    fila("Pérdida de la semana", l.semana?.valor_pct < 0 ? l.semana.valor_pct : 0, l.semana?.limite_pct, `${pct(l.semana?.valor_pct)} de ${pct(l.semana?.limite_pct, 0)}`),
    fila("Caída desde el máximo", l.caida?.valor_pct, l.caida?.limite_pct, `${pct(l.caida?.valor_pct)} de ${pct(l.caida?.limite_pct, 0)}`),
    fila("Operaciones hoy", l.operaciones_hoy?.valor, l.operaciones_hoy?.limite, `${l.operaciones_hoy?.valor ?? "—"} de ${l.operaciones_hoy?.limite ?? "—"}`),
    h("p", {clase: "muy-tenue"}, "Al llegar a un límite no se abre nada nuevo. ", info("limite_diario", "límites")));
}

function cerebro(b) {
  const c = b.cerebro || {};
  const modelos = Object.entries(c.modelos || {});
  return plegable("Cerebro: quién decide qué se opera", false,
    c.error ? h("p", {clase: "aviso"}, c.error) : null,
    modelos.length ? tabla([
      {t: "Velas", v: ([iv]) => iv},
      {t: "Veredicto del laboratorio", v: ([, m]) => chip(m.estado_laboratorio || "sin veredicto", m.estado_laboratorio === "supera" ? "ok" : "aviso")},
      {t: "Decide en este modo", v: ([iv, m]) => m.estado_laboratorio === "supera" ? "sí"
        : (c.exploracion || []).includes(iv) ? "solo exploración (simulado)" : "no (se abstiene)"},
      {t: "Entrenado hasta", v: ([, m]) => fecha(m.entrenado_hasta)},
      {t: "Identidad", v: ([iv]) => h("span", {clase: "mono"}, (c.identidades || {})[iv] || "—")},
    ], modelos) : vacio("Sin modelo del cerebro: no entra ninguna operación decidida por él."),
    h("p", {clase: "muy-tenue"}, `Desde el arranque: ${c.contadores?.entra ?? 0} entra · ${c.contadores?.no_entra ?? 0} no entra · ${c.contadores?.abstiene ?? 0} se abstiene. `,
      info("laboratorio_estado", "veredicto")));
}

function caminoReal(b) {
  const est = b.estrategias || [];
  const real = est.filter((e) => e.etapa === "real_habilitado").length;
  return plegable("Camino a dinero real", false,
    h("p", {}, real ? `${real} estrategia(s) aprobadas para real. ` : "Ninguna estrategia aprobada para real. ", info("etapa", "etapa de promoción")),
    h("p", {}, h("a", {href: "#/estrategias"}, "Ver estrategias y requisitos →")));
}

function acciones(b) {
  const pausado = (b.bloqueos || []).includes("pausa manual");
  const mensaje = h("p", {clase: "muy-tenue", "aria-live": "polite"}, accionEnCurso || "");
  const decir = (t) => { mensaje.textContent = t; };
  async function mandar(cuerpo, boton) {
    boton.disabled = true;
    accionEnCurso = "Enviado al bot; esperando su confirmación…";
    decir(accionEnCurso);
    const r = await enviar("/api/comando", cuerpo);
    if (!r.ok) {
      accionEnCurso = `No se pudo: ${r.error || "error"}`;
    } else {
      const res = await esperarResultado(r.id);
      accionEnCurso = res.pendiente ? res.mensaje : `${res.ok ? "Hecho" : "El bot respondió"}: ${res.mensaje || ""}`;
    }
    decir(accionEnCurso);
    boton.disabled = false;
  }
  const pausa = h("button", {type: "button", disabled: SOLO_LECTURA || pausado || null, onClick: (e) => mandar({cmd: "/pausa"}, e.currentTarget)}, "Pausar entradas nuevas");
  const reanudar = h("button", {type: "button", disabled: SOLO_LECTURA || !pausado || null, onClick: (e) => mandar({cmd: "/reanudar"}, e.currentTarget)}, "Reanudar entradas");

  const pos = (b.posiciones || []).map((p) => p.moneda).sort();

  const marcas =pos.map((m) => h("label", {clase: "acciones"}, h("input", {type: "checkbox", value: m}), m));
  const confirmacion = h("input", {type: "text", autocomplete: "off", "aria-label": "Escribe CERRAR-BOT para confirmar", placeholder: "CERRAR-BOT"});
  const cerrar = h("button", {type: "button", clase: "peligro-btn",
    disabled: SOLO_LECTURA || b.modo === "shadow" || !pos.length || null,
    onClick: (e) => {
      const alcance = marcas.map((l) => l.querySelector("input")).filter((i) => i.checked).map((i) => i.value).sort();
      if (alcance.length !== pos.length) { mensaje.textContent = "Marca TODAS las posiciones del bot: el cierre de emergencia afecta a todas."; return; }
      if (confirmacion.value.trim() !== "CERRAR-BOT") { mensaje.textContent = "Escribe exactamente CERRAR-BOT para confirmar."; return; }
      mandar({cmd: "/cerrarbot", confirmacion: "CERRAR-BOT", alcance}, e.currentTarget);
    }}, "Cerrar todas las posiciones del bot");
  return [
    plegable(pausado ? "Controles · entradas en PAUSA" : "Controles del bot", false,
      h("p", {clase: "tenue"}, pausado ? "En pausa: no abre nada nuevo; las abiertas siguen protegidas."
        : "Activo: abre operaciones si se cumplen las reglas."),
      h("div", {clase: "acciones"}, pausa, reanudar),
      SOLO_LECTURA ? h("p", {clase: "muy-tenue"}, "Panel en solo lectura desde fuera de este equipo.") : null, mensaje),
    h("details", {clase: "plegable peligro"}, h("summary", {}, "Emergencia: cerrar posiciones"),
      h("div", {clase: "cuerpo"},
        h("p", {}, "Cierra todas las posiciones del bot ahora. Solo para emergencias."),
        b.modo === "shadow" ? h("p", {clase: "aviso"}, "Modo shadow: no hay posiciones ni órdenes.") : null,
        pos.length ? h("fieldset", {}, h("legend", {}, "Alcance (marca todas)"), marcas) : vacio("No hay posiciones del bot abiertas."),
        h("div", {clase: "acciones"}, confirmacion, cerrar))),
  ];
}

function pintar() {
  const d = estado.datos;
  if (!raiz) return;
  if (!d) {
    reemplazar(raiz, h("h1", {clase: "solo-lector"}, "Inicio"),
      estado.error ? h("p", {clase: "aviso mal"}, `No hay conexión con el panel: ${estado.error}`) : h("p", {clase: "cargando"}, "Cargando…"));
    return;
  }
  const b = d.bot || {};
  const at = atenciones(d);
  if (estado.error) {
    at.unshift(["mal", "Sin conexión con el panel: lo de abajo son los ÚLTIMOS datos recibidos",
      `Recibidos ${hace(estado.ultimoOk)}. El estado actual del bot es desconocido. (${estado.error})`]);
  }
  // Lo grave se ve siempre, en cualquier pestaña; el resto de avisos vive en «Cuenta».
  const graves = at.filter(([tipo]) => tipo === "mal");
  reemplazar(raiz,
    h("h1", {clase: "solo-lector"}, "Inicio"),
    b.modo === "shadow" ? h("p", {clase: "aviso"}, "Modo SHADOW: el bot no envía órdenes; los resultados son modelados.") : null,
    b.modo === "real" ? h("p", {clase: "aviso mal"}, "Modo REAL: dinero real.") : null,
    graves.length ? bloqueAtencion(d, graves) : null,
    pestanasVista("inicio", [
      ["resumen", "Resumen", () => [embudo(b), nucleo ? nucleo.el : null, h("div", {clase: "dos-columnas"}, decisiones(d), informeDia())]],
      ["mesa", "Mesa", () => pestanaMesa()],
      ["cuenta", `Cuenta (${(b.posiciones || []).length})`, () => [portada(d), graves.length ? null : bloqueAtencion(d, at), posiciones(d), resumen(d)]],
      ["control", "Control", () => [avisosRecientes(d),
        h("div", {clase: "grupo-plegables"}, limites(b), cerebro(b), caminoReal(b), acciones(b))]],
    ], "Secciones de inicio"),
    h("p", {clase: "muy-tenue"}, `Datos del bot de ${b.ts ? hace(b.ts, estado.error ? Date.now() / 1000 : d.ahora) : "—"} `,
      info("frescura", "frescura de los datos")));
  nucleo?.actualizar(d);
  cargarLento();
}

export {atenciones, proteccion};         // funciones puras: se prueban con fixtures (tests/web/pruebas_estados.js)

export const vista = {
  entrar(el) { raiz = el; nucleo = crearNucleo(); pintar(); },
  actualizar() {
    // No se repinta mientras se escribe, con la emergencia abierta o mientras se recorre el gráfico.
    if (escribiendo(raiz)) return;
    if (raiz?.querySelector("details.peligro[open], .grafico.activo")) return;
    const abiertos = [...(raiz?.querySelectorAll("details[open] > summary") || [])].map((s) => s.textContent);
    pintar();
    for (const s of raiz.querySelectorAll("details > summary")) if (abiertos.includes(s.textContent)) s.parentElement.open = true;
  },
  salir() { raiz = null; nucleo = null; cerrarMesa(); },
};
