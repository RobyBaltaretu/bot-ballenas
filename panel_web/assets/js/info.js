// Ayuda «ⓘ»: un botón real (clic, teclado, lector de pantalla) que abre un diálogo. No depende del hover.
// Textos: el glosario del backend (/api/glosario) más los de las métricas nuevas del panel.

import {obtener} from "./api.js";
import {$, h, reemplazar} from "./dom.js";

const LOCAL = {
  saldo_simulado: ["Saldo simulado", "Dinero FICTICIO de la cuenta simulada, valorado con precios reales. No es dinero real ni se puede retirar."],
  saldo_real: ["Valor de la cuenta (dinero real)", "Saldo de la subcuenta real más el resultado de las posiciones abiertas, limitado al capital del piloto."],
  saldo_shadow: ["Saldo teórico (shadow)", "En shadow el bot no tiene cuenta: este saldo es un valor teórico de configuración para calcular tamaños."],
  margen_libre: ["Margen libre", "Parte del saldo que no está bloqueada como margen de posiciones abiertas."],
  resultado_hoy: ["Resultado de hoy", "Variación del valor de la cuenta desde el inicio del día (hora UTC). Incluye lo no realizado."],
  pnl_abierto: ["Resultado abierto", "Suma del resultado no realizado de las posiciones del bot, según la cuenta. Si alguna posición no lo trae, se muestra como desconocido."],
  posiciones: ["Posiciones del bot", "Posiciones que el bot reconoce como suyas (con su registro y sus órdenes) frente al máximo permitido."],
  proteccion: ["Protección (stop)", "«Confirmado»: en la última conciliación el stop existía en el exchange con el tamaño, el lado y el precio correctos. «Desconocido»: no hay conciliación reciente o el bot no lo pudo verificar. Un stop no garantiza el precio de salida."],
  frescura: ["Frescura de los datos", "Cuándo escribió el bot su última foto. Retrasado: más de 2 minutos. Obsoleto: más de 10. Con datos viejos el bot no abre operaciones nuevas."],
  vivo: ["Actividad en vivo", "Los eventos llegan por push (SSE) con unos segundos de retraso; si no es posible, por sondeo. No es tiempo real garantizado."],
  inferido: ["Observado / inferido", "Observado: el dato existe tal cual (p. ej. un fill visto por websocket). Inferido: se deduce (p. ej. el cambio de posición entre dos fotos, o una posible liquidación). Lo inferido no es una señal de entrada confirmada."],
  laboratorio_estado: ["Veredicto del laboratorio", "supera: cumple todas las reglas, incluido un holdout no consultado. exploratorio: cumple, pero el holdout ya se había mirado. no supera: falla alguna regla. no evaluable: no hay datos suficientes. Superar es evidencia, no permiso para operar con dinero real."],
  exploracion: ["Exploración (solo simulado)", "Operaciones con riesgo muy reducido para acumular evidencia en vivo. No son evidencia de ventaja y en real no existen."],
};

let glosario = null;
async function cargar() {
  if (glosario) return glosario;
  try {
    const g = await obtener("/api/glosario");
    glosario = Object.fromEntries(Object.entries(g).map(([k, v]) => [k, [v.titulo, v.texto]]));
  } catch (e) {
    glosario = {};
  }
  return glosario;
}

export function abrirDialogo(titulo, ...cuerpo) {
  const d = $("dialogo");
  $("dialogo-titulo").textContent = titulo;
  reemplazar($("dialogo-cuerpo"), ...cuerpo);
  if (!d.open) d.showModal();
  return d;
}

export async function mostrarAyuda(clave) {
  const g = {...(await cargar()), ...LOCAL};
  const [titulo, texto] = g[clave] || ["Ayuda", "No hay explicación para este dato."];
  abrirDialogo(titulo, h("p", {}, texto));
}

/** Botón ⓘ con nombre accesible. */
export function info(clave, nombre) {
  return h("button", {type: "button", clase: "info-btn", "aria-label": `Qué significa ${nombre || clave}`,
    onClick: (e) => { e.stopPropagation(); mostrarAyuda(clave); }}, "i");
}

/** Botón ⓘ con su propia explicación (sin glosario): los textos largos van aquí, no en la pantalla. */
export function ayuda(titulo, ...cuerpo) {
  return h("button", {type: "button", clase: "info-btn", "aria-label": `Ayuda: ${titulo}`,
    onClick: (e) => { e.stopPropagation(); abrirDialogo(titulo, ...cuerpo.map((x) => typeof x === "string" ? h("p", {}, x) : x)); }}, "i");
}

/** Título de sección con su ayuda al lado. */
export function titulo(texto, tituloAyuda, ...cuerpoAyuda) {
  return h("span", {}, `${texto} `, cuerpoAyuda.length ? ayuda(tituloAyuda || texto, ...cuerpoAyuda) : null);
}

export function iniciarDialogo() {
  const d = $("dialogo");
  $("dialogo-cerrar").addEventListener("click", () => d.close());
  d.addEventListener("click", (e) => { if (e.target === d) d.close(); });
}
