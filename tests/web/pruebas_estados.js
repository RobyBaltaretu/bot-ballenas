// Pruebas de ESTADOS del panel nuevo con fixtures SIMULADAS (ninguna es una operación real).
// Cómo ejecutarlas: abre el panel (http://127.0.0.1:8080/), abre la consola del navegador (F12) y pega este archivo.
// Devuelve {ok, fallos}. No hay Node en este equipo: por eso se ejecutan en el propio navegador.
(async () => {
  const ini = await import("/assets/js/vistas/inicio.js");
  const f = await import("/assets/js/formato.js");
  const fallos = [];
  const ok = (cond, texto) => { if (!cond) fallos.push(texto); };
  const ahora = 1_800_000_000;
  const base = {modo: "simulado", ts: ahora - 5, conciliacion_ok: true, conciliacion_ts: ahora - 20, datos_frescos: true, bloqueos: [],
    posiciones: [], sin_stop: {}, congelados: {}, riesgo_liquidacion: {}, externas: [], posiciones_legado: [], cerebro: {}};
  const d = (bot, extra = {}) => ({ahora, bot, bot_vivo: bot.ts ? ahora - bot.ts < 120 : false, sistema_resumen: {}, ...extra});
  const textos = (x) => ini.atenciones(x).map((a) => a[1]).join(" | ");

  ok(ini.atenciones(d(base)).length === 0, "estado sano: nada requiere atención");
  ok(/no ha escrito datos/.test(textos(d({}))), "bot apagado (sin datos)");
  ok(/no da señales/.test(textos(d({...base, ts: ahora - 900}))), "bot parado (datos viejos)");
  ok(/obsoletos/.test(textos(d({...base, datos_frescos: false}))), "precios obsoletos");
  ok(/stop NO confirmado/.test(textos(d({...base, sin_stop: {ETH: "no hay stop activo"}}))), "stop no confirmado");
  ok(/no cuadra/.test(textos(d({...base, conciliacion_ok: false}))), "conciliación fallida");
  ok(/bloqueadas/.test(textos(d({...base, bloqueos: ["pausa manual"]}))), "entradas bloqueadas");
  ok(/incidente/.test(textos(d(base, {sistema_resumen: {incidentes_activos: 2}}))), "incidentes activos");

  const b = {...base};
  const chipTxt = (p, bb) => ini.proteccion(p, bb, ahora).textContent;
  ok(/confirmado/.test(chipTxt({stop_verificado: true, stop_verificado_ts: ahora - 30}, b)), "protección confirmada");
  ok(/SIN CONFIRMAR/.test(chipTxt({stop_verificado: false}, b)), "protección sin confirmar");
  ok(/desconocido/.test(chipTxt({stop_verificado: true}, {...b, conciliacion_ts: ahora - 3600})), "sin conciliación reciente -> desconocido");
  ok(/desconocido/.test(chipTxt({stop_verificado: true}, {...b, conciliacion_ts: null})), "sin conciliación -> desconocido");

  ok(f.num(null) === "—" && f.usd(undefined) === "—" && f.pct(NaN) === "—", "ausente nunca es 0");
  ok(/desconocido/.test(f.resultado(null).textContent), "resultado ausente = desconocido");
  ok(f.resultado(-1.5).textContent.startsWith("▼"), "pérdida con flecha y signo (no solo color)");
  ok(f.frescura(ahora - 10, ahora).estado === "fresco", "fresco");
  ok(f.frescura(ahora - 300, ahora).estado === "retrasado", "retrasado");
  ok(f.frescura(ahora - 5000, ahora).estado === "obsoleto", "obsoleto");
  ok(f.frescura(null, ahora).estado === "desconocido", "frescura desconocida");

  // Render de Inicio con fixtures SIMULADAS (al final se recarga la página para volver a los datos reales).
  const {estado} = await import("/assets/js/estado.js");
  const div = document.createElement("div");
  const t = Date.now() / 1000;
  estado.error = null;
  estado.datos = {ahora: t, bot_vivo: true, sistema_resumen: {}, bot: {modo: "shadow", ts: t - 3, datos_frescos: true, conciliacion_ok: true,
    bloqueos: [], posiciones: [], shadow_abiertas: [{moneda: "ETH", lado: "L", estrategia: "ruptura_1h", ts: t - 600}], saldo: 58, limites: {}, exposicion: {}}};
  ini.vista.entrar(div);
  ok(/Modo SHADOW/.test(div.textContent) && /Saldo teórico/.test(div.textContent) && /Intenciones shadow/.test(div.textContent), "render shadow");
  estado.datos = {ahora: t, bot_vivo: true, sistema_resumen: {}, bot: {modo: "simulado", ts: t - 3, datos_frescos: true, conciliacion_ok: true,
    conciliacion_ts: t - 10, bloqueos: [], sin_stop: {SOL: "no hay stop activo"}, saldo: 232, limites: {}, exposicion: {},
    posiciones: [{trade_id: "fixture-1", moneda: "SOL", lado: "S", tam: 1, entrada: 200, precio_mark: 201, pnl_no_realizado: null, sl: 204, stop_verificado: false}]}};
  ini.vista.entrar(div);
  ok(/SOL: stop NO confirmado/.test(div.textContent) && /SIN CONFIRMAR/.test(div.textContent), "render stop sin confirmar");
  ok(/desconocido/.test(div.textContent) && /SIMULADO \(ficticio\)/.test(div.textContent), "render dato ausente y saldo ficticio");
  ok(/sin historial suficiente/.test(div.textContent) && !div.querySelector(".grafico svg"), "sin historial no se dibuja gráfico");
  estado.datos.cerradas = {"1D": {n: 4, pnl: -4.85, desconocidas: 1}};
  ini.vista.entrar(div);
  const desg = div.querySelector(".desglose")?.textContent || "";
  ok(/Cerradas en 24 h \(4\)/.test(desg) && /−4,85/.test(desg) && /1 sin resultado/.test(desg) && /Abiertas ahora \(1\)/.test(desg) && /desconocido/.test(desg), "desglose: cerradas y abiertas sin inventar datos");
  ini.vista.salir();

  // Gráfico de precio de una operación: niveles de entrada/stop y punto de entrada, dentro de la escala.
  const {graficoLinea} = await import("/assets/js/grafico.js");
  const cifra = document.createElement("div"), pie = document.createElement("div");
  const g = graficoLinea([[0, 100], [3600, 99], [7200, 98]], {cifra, linea: pie, valor: String, pie: () => [], etiqueta: "x",
    niveles: [{v: 100, clase: "entrada", texto: "Entrada 100"}, {v: 105, clase: "stop", texto: "Stop 105"}],
    marcas: [{t: 0, v: 100, clase: "entrada", texto: "Entrada"}]});
  const tops = [...g.querySelectorAll(".nivel-texto")].map((e) => parseFloat(e.style.top));
  ok(g.querySelectorAll("line.nivel").length === 2 && /Stop 105/.test(g.textContent) && g.querySelector(".marca-punto")
    && tops.every((y) => y >= 0 && y <= 100) && g.classList.contains("baja"), "gráfico de precio con niveles");
  setTimeout(() => location.reload(), 500);
  return {ok: fallos.length === 0, pruebas: 25, fallos};
})();
