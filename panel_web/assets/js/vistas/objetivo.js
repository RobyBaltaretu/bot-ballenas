// OBJETIVO: la prueba de dos semanas (criterios fijados de antemano, calculados por código) y el informe del analista.
// El veredicto no lo decide ninguna IA. Lo que proponga el analista son textos: esta vista no permite aplicar nada.

import {obtener} from "../api.js";
import {chip, errorCarga, h, pestanasVista, reemplazar, seccion, vacio} from "../dom.js";
import {fecha, num, resultado} from "../formato.js";
import {ceto} from "../ceto.js";

const RESULTADOS = {
  pendiente: ["Aún sin resultado", null, "Falta el primer laboratorio de la prueba (domingo 08/11)."],
  adelante: ["Adelante", "ok", "Hay una estrategia validada y en vivo no la contradice."],
  cambiar_de_rumbo: ["Cambiar de rumbo", "aviso", "Ninguna estrategia de dirección vale, pero el carry de funding aguanta (provisional: faltan costes por medir)."],
  no_vale: ["No vale", "mal", "Nada ha superado los criterios: no se pone dinero real."],
};
const ESTADOS = {cumple: ["Cumple", "ok"], no_cumple: ["No cumple", "mal"], pendiente: ["Pendiente", null]};
const RECOMENDACION = {mantener: "ok", vigilar: "aviso", retirar: "mal"};
const FECHA = new Intl.DateTimeFormat("es-ES", {day: "2-digit", month: "2-digit"});

const HUMOR = {pendiente: "pendiente", adelante: "adelante", cambiar_de_rumbo: "rumbo", no_vale: "no_vale"};
const ECO = {cumple: "ok", no_cumple: "mal", pendiente: null};

/** Ceto da el veredicto. Solo pronuncia lo que calculó el código: criterios, alarmas y días que quedan. */
function cabecera(v, alarmasActivas) {
  const [titulo, clase, texto] = RESULTADOS[v.resultado];
  const cr = v.criterios || [];
  const cumplen = cr.filter((c) => c.estado === "cumple").length, fallan = cr.filter((c) => c.estado === "no_cumple").length;
  const pend = cr.length - cumplen - fallan;
  const nAl = (alarmasActivas || []).length;
  const frases = [
    v.terminada ? "Soy Ceto. La prueba ha terminado; este es mi veredicto final." : `Soy Ceto. Faltan ${num(v.dias_restantes, 0)} días de prueba; esto es lo que veo hoy.`,
    `${titulo}. ${texto}`,
    `Criterios: ${cumplen} cumplen, ${fallan} no cumplen y ${pend} pendientes de ${cr.length}.`,
    nAl ? `Tengo ${nAl} ${nAl === 1 ? "alarma activa" : "alarmas activas"} en el vigilante.` : "El vigilante no tiene alarmas activas.",
    "Ojo: hablo yo, pero el veredicto lo calcula el código con criterios fijados el 04/11. No soy una IA decidiendo.",
  ];
  const contactos = cr.map((c) => ({etq: c.texto, estado: ECO[c.estado] ?? null,
    dice: [c.texto, c.detalle, `Estado: ${ESTADOS[c.estado]?.[0] || c.estado}.`].filter(Boolean)}));
  return ceto({humor: HUMOR[v.resultado] || "pendiente", frases, contactos,
    cabecera: [h("div", {clase: "ceto-etq"}, v.terminada ? "Veredicto final" : `Si terminara hoy · quedan ${num(v.dias_restantes, 0)} días`),
      h("div", {clase: "ceto-veredicto"}, titulo), h("div", {}, chip(v.terminada ? "Final" : "Provisional", clase))]});
}

function criterios(v) {
  return seccion("Criterios", h("ul", {clase: "lista"}, v.criterios.map((c) => h("li", {}, h("div", {clase: "fila"},
    h("div", {clase: "centro"}, h("div", {clase: "titulo"}, c.texto), h("div", {clase: "sub"}, c.detalle)),
    h("div", {clase: "derecha"}, chip(...ESTADOS[c.estado])))))));
}

function semanas(v) {
  const o = v.objetivo;
  const pct = o.pct_semana_sobre_saldo;
  return seccion("Objetivo semanal", h("ul", {clase: "lista"}, v.semanas.map((s) => h("li", {}, h("div", {clase: "fila"},
    h("div", {clase: "centro"}, h("div", {clase: "titulo"}, `Semana ${s.semana} · ${FECHA.format(new Date(s.desde * 1000))}`),
      h("div", {clase: "sub"}, !s.empezada ? "Aún no ha empezado"
        : `${s.n} cerradas${s.en_curso && s.latente_usd !== null ? " + abiertas" : ""}${s.desconocidas ? ` · ${s.desconocidas} sin resultado` : ""}`)),
    h("div", {clase: "derecha"}, s.empezada ? h("div", {clase: "titulo"}, resultado(s.total_eur, 2, " €")) : null,
      s.empezada ? h("div", {clase: "sub"}, chip(s.llega_al_objetivo ? "En objetivo" : s.en_positivo ? "En positivo" : "En negativo",
        s.llega_al_objetivo ? "ok" : s.en_positivo ? null : "mal")) : null))))),
  h("p", {clase: "muy-tenue"}, `Objetivo: ${o.eur_semana[0]}–${o.eur_semana[1]} € por semana`,
    pct ? ` (${num(pct[0], 0)}–${num(pct[1], 0)} % semanal). ` : ". ",
    "Solo informa: en dos semanas pesa mucho la suerte."));
}

function contraMercado(v) {
  const c = v.contra_mercado;
  if (!c || !c.n) return seccion("¿Bot o mercado?", h("p", {clase: "tenue"}, c?.lectura || "Aún no hay datos para comparar."));
  const fila = (texto, valor, clase) => h("li", {}, h("div", {clase: "fila"}, h("div", {clase: "centro"}, h("div", {clase: "titulo"}, texto)),
    h("div", {clase: "derecha"}, h("div", {clase: "titulo"}, resultado(valor, 2, " $")), clase ? chip(clase[0], clase[1]) : null)));
  return seccion("¿Bot o mercado?", h("p", {}, c.lectura),
    h("ul", {clase: "lista"}, fila(`El bot (${c.cortos} cortos, ${c.largos} largos)`, c.bot_usd),
      fila("Las mismas operaciones, todas cortas", c.todo_corto_usd, c.mejor_que_todo_corto ? null : ["Igual o mejor que el bot", "aviso"]),
      fila("Las mismas operaciones, todas largas", c.todo_largo_usd)),
    h("p", {clase: "muy-tenue"}, `${c.nota} Solo informa: no cambia el veredicto.`));
}

const VERIFICACION = {verificado: ["Dato comprobado", "ok"], contradicho: ["No cuadra con los datos", "mal"], no_verificado: ["Sin comprobar", null]};

function hallazgo(x) {
  if (typeof x === "string") return h("li", {}, x);      // informes antiguos
  const [texto, clase] = VERIFICACION[x.verificacion] || VERIFICACION.no_verificado;
  return h("li", {}, `${x.texto} `, chip(texto, clase));
}

function alarmas(lista) {
  if (!(lista || []).length) return seccion("Vigilante", h("p", {clase: "tenue"}, "Sin alarmas activas."));
  return seccion("Vigilante", h("ul", {clase: "atencion"}, lista.map((a) => h("li", {clase: a.gravedad === "grave" ? "mal" : "aviso"}, h("div", {},
    h("div", {clase: "que"}, a.texto), h("div", {clase: "cuando"}, `desde ${fecha(a.primer_ts)}`),
    a.ia?.explicacion ? h("div", {clase: "tenue"}, `IA: ${a.ia.explicacion}`) : null)))));
}

function revisiones(lista) {
  if (!(lista || []).length) return seccion("Revisor de operaciones", vacio("Aún no hay operaciones revisadas de la prueba."));
  return seccion("Revisor de operaciones", h("ul", {clase: "lista"}, lista.map((r) => {
    const fijas = r.comprobaciones?.anomalias || [];
    const ia = r.ia || {};
    return h("li", {}, h("a", {clase: "fila", href: `#/operacion/${encodeURIComponent(r.trade_id)}`},
      h("div", {clase: "centro"}, h("div", {clase: "titulo"}, `${r.moneda || "—"} · ${r.estrategia || "—"}`),
        h("div", {clase: "sub"}, ia.estado === "ok" ? `${ia.causa_probable}: ${ia.explicacion}` : "Sin revisión de la IA"),
        fijas.map((t) => h("div", {clase: "sub"}, chip(t, "aviso")))),
      h("div", {clase: "derecha"}, h("div", {clase: "titulo"}, resultado(r.pnl_neto)))));
  })));
}

function marcador(m, uso, maximo) {
  if (!m) return null;
  const d = m.datos_citados || {};
  return seccion("Marcador de la IA",
    h("p", {}, m.puntuadas ? `Recomendaciones: acierta ${m.aciertos} de ${m.puntuadas}. Diciendo siempre «retirar» acertaría ${m.siempre_retirar}.`
      : `Aún no hay recomendaciones puntuables: cada una necesita ${m.min_ops} operaciones posteriores (${m.pendientes} pendientes).`),
    h("p", {}, `Datos citados: ${d.verificado || 0} comprobados, ${d.contradicho || 0} no cuadran y ${d.no_verificado || 0} sin comprobar.`),
    h("p", {}, `Operaciones revisadas: ${m.revisiones}, ${m.revisiones_con_anomalias} con anomalías detectadas por código.`),
    h("p", {clase: "muy-tenue"}, `Consumo de hoy: ${uso?.consultas ?? 0} de ${maximo} consultas, ${uso?.unidades ?? 0} tokens.`));
}

const VEREDICTO_ESC = {a_favor: ["a favor", "ok"], neutral: ["neutral", null], en_contra: ["en contra", "mal"]};

/** Escéptico en sombra: la IA da el mejor argumento en contra de cada apertura. Nunca decide; aquí se mide si acierta. */
function esceptico(e) {
  if (!e) return null;
  const pv = e.por_veredicto || {};
  const fila = (v) => {
    const x = pv[v] || {};
    return h("li", {}, h("div", {clase: "fila"}, h("div", {clase: "centro"}, h("div", {clase: "titulo"}, `Dijo «${VEREDICTO_ESC[v][0]}»`),
      h("div", {clase: "sub"}, x.n ? `${x.n} cerradas · ganan ${num(x.ganan_pct, 0)} %` : "aún ninguna cerrada")),
      h("div", {clase: "derecha"}, h("div", {clase: "titulo"}, x.r_medio == null ? "—" : `${num(x.r_medio, 2)} R`))));
  };
  return [seccion("Escéptico en sombra",
    h("p", {}, "Cuando el bot abre una operación, la IA da el mejor argumento en contra con los datos de ese momento (idea del analista "
      + "de investigación de HyperGrok). No decide nada: se guarda y, al cerrarse, se mide. Si lo que dice «en contra» pierde más "
      + "que lo que dice «a favor», sus objeciones tienen información; si no, son ruido."),
    h("ul", {clase: "lista"}, ["a_favor", "neutral", "en_contra"].map(fila)),
    h("p", {}, e.aciertos_pct == null ? `Juzgadas: ${e.juzgadas ?? 0}. Aún ninguna cerrada con veredicto a favor o en contra.`
      : `Acierta el ${num(e.aciertos_pct, 0)} % (a favor y ganó, o en contra y perdió). Diciendo siempre «en contra» acertaría el ${num(e.siempre_en_contra_pct, 0)} %.`),
    h("p", {clase: "muy-tenue"}, e.concluyente ? "Ya hay 30 o más en cada lado: empieza a ser comparable."
      : "Hacen falta al menos 30 cerradas «a favor» y 30 «en contra» para comparar. Gasta como mucho 2 consultas por pasada y deja 12 al día para lo demás.")),
  seccion("Últimas opiniones", (e.recientes || []).length ? h("ul", {clase: "lista"}, e.recientes.map((r) => {
    const ia = r.ia || {};
    return h("li", {}, h("a", {clase: "fila", href: `#/operacion/${encodeURIComponent(r.trade_id)}`},
      h("div", {clase: "centro"}, h("div", {clase: "titulo"}, `${r.moneda || "—"} · ${r.estrategia || "—"}`),
        h("div", {clase: "sub"}, ia.estado === "ok" ? ia.objecion : ia.estado === "limite" ? "Sin consulta: tope diario" : `Sin opinión (${ia.estado || "—"})`)),
      h("div", {clase: "derecha"}, ia.estado === "ok" ? chip(VEREDICTO_ESC[ia.veredicto][0], VEREDICTO_ESC[ia.veredicto][1]) : null)));
  })) : vacio("Aún no ha opinado: juzga las operaciones que se abran a partir de ahora (como mucho 4 h después de abrirse)."))];
}

/** Ceto lee el informe del analista: resumen de la IA (o los hallazgos por código) y una lectura por estrategia. */
function cetoAnalista(inf) {
  const ia = inf.ia || {};
  const ok = ia.estado === "ok";
  const frases = ok
    ? [`Informe del ${fecha(inf.ts)}.`, ia.resumen || "Sin resumen.", "Esto es el análisis de una IA: no es evidencia. Los datos que cita se comprueban aparte."]
    : [`Informe del ${fecha(inf.ts)}.`, ...(inf.hallazgos || []).slice(0, 2), ia.estado === "sin_clave" ? "No tengo IA conectada (falta GROQ_API_KEY): solo leo hallazgos calculados por código." : "Hoy no pude consultar a la IA."];
  const contactos = (ia.estrategias || []).map((e) => ({etq: `${e.clave}: ${e.recomendacion}`, estado: RECOMENDACION[e.recomendacion] || null,
    dice: [`${e.clave}: ${e.recomendacion}.`, e.motivo, "Es una recomendación en texto: no cambia nada del bot."].filter(Boolean)}));
  return ceto({humor: ok ? "analiza" : "pendiente", frases, contactos, compacto: true,
    cabecera: [h("div", {clase: "ceto-etq"}, "Analista"), h("div", {clase: "ceto-veredicto"}, ok ? "Informe de hoy" : "Informe básico")]});
}

function analista(inf) {
  if (!inf) return seccion("Analista", vacio("Aún no hay informe. Se genera una vez al día."));
  const ia = inf.ia || {};
  const estadoIa = {ok: `Con IA (${ia.modelo})`, sin_clave: "Sin IA: falta GROQ_API_KEY en .env", error: `Error de IA: ${ia.error || "desconocido"}`}[ia.estado] || "—";
  return seccion("Analista",
    h("p", {}, chip(estadoIa, ia.estado === "ok" ? "ok" : ia.estado === "error" ? "aviso" : null), ` ${fecha(inf.ts)}`),
    h("ul", {clase: "lista-simple"}, (inf.hallazgos || []).map((t) => h("li", {}, t))),
    ia.estado === "ok" ? [
      h("h3", {}, "Análisis de la IA (no es evidencia)"), h("p", {}, ia.resumen),
      h("ul", {clase: "lista-simple"}, (ia.hallazgos || []).map(hallazgo)),
      (ia.estrategias || []).length ? h("ul", {clase: "lista"}, ia.estrategias.map((e) => h("li", {}, h("div", {clase: "fila"},
        h("div", {clase: "centro"}, h("div", {clase: "titulo"}, e.clave), h("div", {clase: "sub"}, e.motivo)),
        h("div", {clase: "derecha"}, chip(e.recomendacion, RECOMENDACION[e.recomendacion])))))) : null,
      (ia.correcciones || []).length ? [h("h3", {}, "Correcciones propuestas (sin aplicar)"),
        h("ul", {clase: "lista-simple"}, ia.correcciones.map((t) => h("li", {}, t)))] : null,
      (ia.ideas || []).length ? h("p", {clase: "muy-tenue"}, `${ia.ideas.length} idea(s) enviadas a investigación: pasan el mismo examen que las demás.`) : null,
    ] : null);
}

export const vista = {
  async entrar(el) {
    reemplazar(el, h("p", {clase: "cargando"}, "Cargando…"));
    let d;
    try {
      d = await obtener("/api/objetivo");
    } catch (e) {
      reemplazar(el, errorCarga(`No se pudo leer el objetivo: ${e.message}`));
      return;
    }
    reemplazar(el, h("div", {clase: "titulo-vista"}, h("h1", {}, "Objetivo y analista")),
      pestanasVista("objetivo", [
        ["veredicto", "Veredicto", () => [cabecera(d.veredicto, d.alarmas_activas), criterios(d.veredicto)]],
        ["semanas", "Semanas", () => [semanas(d.veredicto), contraMercado(d.veredicto)]],
        ["analista", "Analista", () => [d.analista ? cetoAnalista(d.analista) : null, alarmas(d.alarmas_activas), analista(d.analista), marcador(d.marcador, d.consumo, d.max_consultas_dia)]],
        ["revisiones", "Operaciones revisadas", () => revisiones(d.revisiones)],
        ["esceptico", "Escéptico", () => esceptico(d.esceptico)],
      ], "Secciones del objetivo"));
  },
};
