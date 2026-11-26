# Bot de ballenas — guía para Claude Code

Bot de trading para **Hyperliquid** (futuros perpetuos de cripto), escrito en Python. Propietario: Roberto.
Toda la interfaz, la documentación y los mensajes del bot están **en español**: mantenlo así.
Lee `LEEME.md` para el detalle completo (es la documentación de referencia del proyecto).

## Reglas de seguridad (obligatorias, sin excepciones)

- **No envíes órdenes reales, no conectes una wallet para operar, no solicites ni muestres secretos** y no
  imprimas `.env`, claves privadas, tokens ni credenciales. Enmascara secretos en logs, informes y salidas.
- **No hagas llamadas que puedan modificar una cuenta de Hyperliquid.** Para pruebas de integración usa mocks o
  fixtures. Todo test de órdenes debe probar el adaptador simulado (`papel.py`).
- **No cambies el bot a modo real** ni lo inicies contra una cuenta real. No crees ni transfieras fondos a subcuentas.
- Ningún botón, endpoint ni comando puede saltarse los gates ni convertir shadow/simulado en real.
- Ningún resultado del laboratorio puede elevar límites ni activar real automáticamente. Pasar a real exige
  `promocion.py` + aprobación humana expresa de Roberto.
- **Binance y Bybit: solo datos públicos de lectura.** Nunca se opera allí.
- No ocultes cambios no implementados ni inventes resultados de rentabilidad o porcentajes de acierto.
- Si algo es irreversible o dudoso, pregunta antes.

## Estado actual (19/11/2026)

- **Modo SIMULADO** (dinero ficticio con precios reales). Cuenta simulada ≈ 230 USD (`saldo_simulado_usd: 232` ≈ 200 €).
- Riesgo por operación **3 %** (`riesgo.riesgo_por_operacion_pct`), riesgo abierto máx. **9 %**, 6 posiciones,
  apalancamiento máx. 5 y universo desde 3 M$ de volumen con memecoins (04/11/2026, a petición de Roberto). Es el
  riesgo bueno (confirmado por Roberto el 19/11/2026). **Piloto real = simulado** (Roberto, 19/11): en `config.json`
  `piloto_real` tiene 3 % / 9 % / 6 posiciones, `mercados: ["*"]` (todo el universo, `bot.mercado_en_piloto`),
  `apalancamiento_max: 5` (nuevo; por defecto 3) y `perdida_max_usd: 116` (50 % de 232, como `perdida_max_total_pct`).
  `/aplicarconfig` rechaza cambios de `piloto_real` (barrera: debe aplicarlos un arranque manual con `INICIAR.bat`).
  **Incidencia 19/11:** al reiniciar con el piloto devuelto un momento a sus valores antiguos, Claude lo restauró antes
  de que el lanzador releyera `config.json` (≈ 44 s después de aceptar el comando), así que el bot cargó el piloto nuevo
  a las 13:22 UTC sin arranque manual. Sin efecto en simulado; Roberto lo había pedido expresamente. Lección: no usar ese
  truco; para cambios de `piloto_real`, arranque manual. Lo que NO es igual en real
  ni debe serlo (reglas de seguridad): solo operan estrategias promovidas (`promocion.py` + Roberto), el cerebro solo
  decide con un modelo que supera, y la exploración (cerebro y amplia), la cartera de funding y las ballenas en
  `modo_senal: simulado` no existen en real.
- Sin datos externos frescos el cerebro no decide (`cerebro_vivo`): su ausencia inflaba la predicción en vivo.
- **Cerebro** (`cerebro_vivo.py`): único que decide qué propuestas se operan. Modelo actual del laboratorio con la
  validación endurecida: **4 h = no_supera** (falla t por días 2,8 < 3,6 y holdout ≈ 0); **1 h = sin modelo**.
  - `cerebro.exploracion_simulado: ["4h"]`: en simulado el cerebro de 4 h decide aunque no apruebe (marcado
    «exploración»). En real no tiene efecto.
- **Exploración amplia** (`exploracion_amplia`): en simulado, lo que el cerebro no opera se opera con riesgo 0,5 %
  y como máximo 4 abiertas (03/11/2026, para aprender más rápido; `riesgo.max_posiciones_abiertas` 6 y `max_mismo_lado` 4,
  que en real siguen limitados por `piloto_real`), sin ocupar los huecos del cerebro. Desde el 19/11 explora TODO,
  también lo que el laboratorio da por negativo (igual que la exploración del cerebro); `t_min_laboratorio` es un
  filtro opcional (vacío por defecto). Marcado `exploracion_amplia` en ledger/panel.
- **Modo defensa**: en simulado solo cuenta las operaciones posteriores a la última puesta a cero (`archivo_reinicios/`).
- **Probador en vivo** (`aprendizaje.Memoria.probador`): resultados por estrategia (operadas + sombra) y cerebro
  aceptadas vs rechazadas. Panel → Estrategias y tarjeta del cerebro en la portada.
- **Agenda propia** (`bot.agenda`): laboratorio domingos ≥ 04:00 y investigación lun–sáb ≥ 02:30 (hora local),
  con recuperación si se perdieron y nunca dos a la vez (bloqueos `*.lock`).
- Ninguna estrategia individual ha superado el laboratorio. Lo más sólido en investigación: **carry de funding
  realista** (~12 %/año en pruebas, ~7 % en holdout); desde el 19/11 corre en SIMULADO con dos patas (`carry/motor.py`).

## Cambios del 19/11/2026 tras el estudio (`ESTUDIO_BOT_2026-11-19.md`, pedidos por Roberto)

- **Funding con su hora** (`gestor.procesar_cierre`): cada evento `funding` lleva `ts_pago` (hora real del cobro;
  `ledger.iso_ms`); `ledger.operaciones()` la usa. Los eventos antiguos siguen con la hora del cierre.
- **Stop disparado sin llenar del todo** (`gestor._reduccion` y `_recuperar_stop`): si los fills del stop explican la
  reducción, o el precio ya está al otro lado del stop, el resto se cierra al momento (reduce-only) en vez de quedar sin
  protección y congelado. Evento `proteccion` `disparado_parcial` / `cruzado`.
- **Simulador MODELO 3** (`papel.py`): una orden límite en reposo se llena solo si hay contrapartida real a su precio en
  el libro o una operación real se imprimió PEOR (velas de 1 min posteriores a la orden). Antes bastaba con que el precio
  MEDIO la cruzara (con el diferencial abierto llenaba sin que nadie operase a ese precio). IOC y stops siguen con el libro
  AGREGADO (`nSigFigs` 3 y 2) si los 20 niveles visibles no bastan. Foto del libro cacheada con los mids.
- **Memoria por vecinos aplica** (`bot.procesar_candidatas`): también sobre lo que acepta el cerebro o la exploración
  amplia (factor 0,5–1; en contra: tamaño × `factor_exploracion` en simulado, veto en real). Así todos los parámetros
  de `aprendizaje` vuelven a tener efecto. Deshace el cambio del 13/11.
- **Estrategias apagadas en sombra** (`motor.nuevas_senales`): se evalúan igual y sus señales van como
  `solo_investigacion` + `apagada` (nunca operan; probador y memoria siguen aprendiendo). Las de 1 h siguen apagadas.
- **Ballenas operan en simulado y vetan** (`config.json`): `ballenas.modo_senal: "simulado"`, `usar_como_veto: true`,
  `estrategias.ballenas_1h.activa: true`. Como el cerebro de 1 h no tiene modelo, entran por la exploración amplia.
  En real, nada sin promoción.
- **Código muerto fuera**: `estrategia.redondear_tamano`, `SimSalida.cerrar_ya`, `validacion.en_tramo` y `estres_costes`,
  `Memoria.registrar_cerrado`, `CuentaPapel.market_close`, constantes `PESO_TIPO`, `POR_RUTA`, `ESTADOS_OPERACION`,
  `NO_EJECUTADO`, `ESTADOS_CANCELADA`, `FASES` e imports sin usar. Se conserva a propósito `InfoConPapel.open_orders`
  (sin él, la consulta iría a la API real).
- **Listón de t por familias** (Roberto, 19/11): `validacion.RegistroVariantes` guarda la familia de cada variante
  (laboratorio: módulo × intervalo, `laboratorio.familias_laboratorio`; investigación: disparador × intervalo,
  `validacion.familia_idea`; cerebro: una; registros antiguos sin familia: una por origen). Bonferroni se aplica sobre
  `efectivas()` (27 familias) en vez de `total()` (1 098 variantes): con 60 operaciones el listón pasa de t ≥ 4,2 a
  t ≥ 3,02. Ampliar una rejilla no lo sube; un TIPO de idea nuevo sí. Se lanzó un laboratorio el 19/11 12:14 UTC para
  recalcular los veredictos con el listón nuevo.
- **Ampliar ganadoras / piramidar** (Roberto, 19/11; SOLO simulado, `config.piramide`, por defecto apagado y activo en
  `config.json`): `bot._ampliar_ganadoras` → `gestor.ampliable` / `gestor.ampliar`. Con el stop ya en la entrada o mejor
  (`en_breakeven`), UNA vez por operación se añade `fraccion` (0,5) del tamaño inicial con IOC (rol `ampliacion`, no
  reduce-only); la parte añadida arriesga como mucho `riesgo_max_frac_original` × `riesgo_plan_usd`, dentro del riesgo
  abierto máximo y del margen libre. Tras ampliar: stop del tamaño nuevo (verificado), objetivo final rehecho por
  `_reconciliar_tps`, `tramos_tam` para el funding, `tam_inicial` = todo lo que entró. Si los fills de la orden no explican
  lo que creció la cuenta, congela. Al cerrar (`gestor._separar_ampliacion`): 1 R = riesgo de la entrada ORIGINAL; el
  cierre lleva `ampliacion` {pnl_ampliacion, pnl_sin_ampliacion, r_sin_ampliacion…} (ESTIMADO: el funding de la parte
  añadida no se separa) y la memoria aprende con el resultado SIN ampliación. Ledger: fills `ampliacion` cuentan como
  entrada (`fills_ampliacion` aparte). Panel: Operaciones → pestaña «Ampliaciones» (`GET /api/ampliaciones`, con y sin).
- **Operaciones con más datos** (Roberto, 19/11): tarjetas en vivo con cantidad, entrada, importe, apalancamiento, margen
  y riesgo; historial con cantidad · precio · importe · apalancamiento · salida; ficha «La operación en números»
  (`operaciones.js`, `numerosOperacion`): señal, entrada, importe, apalancamiento y margen, riesgo, stop, objetivo, valor
  y liquidación si está abierta, salida, comisiones, funding, duración, quién decidió y ampliación.
- **Peticiones a Hyperliquid**: `papel._ctx` (metaAndAssetCtxs, peso 20) se cachea 10 s (antes 3 s); `limitador.por_tipo`
  acumula el peso por tipo de petición (`estado_sistema.json` → contadores → `peso_por_tipo`). Tras CADA arranque el bot
  vuelve a bajar 90 días de funding de ~37 monedas (`motor.preparar_funding`, ~8 000 de peso): durante ~10–15 min el
  limitador frena y el ciclo tarda 30–45 s; después vuelve a ~7 s. Es normal; no reiniciar en bucle.
- **Auditoría maestra** (19/11): informes en `audit/ballenas/` (README con matriz de problemas; veredicto PAPER TRADING).
  Arreglos aplicados el mismo día (pedidos por Roberto):
  - **R-01** `bot._ampliar_ganadoras` pasa los mismos controles que una entrada: `bloqueos_entrada` (pausa, límites de
    pérdida, datos, conciliación…), `comprobar_agregados` con la posición AMPLIADA frente a las demás, desplome conjunto y
    horquilla máxima. Si espera, el motivo queda en `op["ampliacion_esperando"]` / `bot.ampliacion_bloqueada`.
  - **R-05** Desplome conjunto: `riesgo.riesgo_salto` (pérdida si el stop salta y llena a su precio límite, tolerancia
    10 %) y `riesgo.comprobar_salto` (suma por LADO de todas las posiciones del bot, también exploración, + la nueva ≤
    `riesgo.riesgo_salto_max_pct`, 20 % por defecto; 0 = desactivado). Se aplica a entradas (`procesar_candidatas`) y
    ampliaciones (`bot._motivos_salto`).
  - **R-08** `gestor.cerrar_huerfanas_ledger` (al arrancar y cada 6 h, `bot._cerrar_huerfanas`): una operación que el
    ledger ve abierta, que el gestor ya no tiene, con > 10 min sin eventos y sin posición sin dueño en esa moneda, se
    cierra como `contabilidad: incompleta` (resultado desconocido). Primer caso: kPEPE 23/10 (`op-20261023120105-55b133`).
    El resumen del ledger ya no recalcula PnL con fills cuando el cierre dice `incompleta`.
- Todo esto cambia la huella. 723 pruebas.

## Cambios del 21/11/2026 (mejoras de la auditoría que no dependían de Roberto, pedidas por él)

- **`retroceso_1h` activa** (Roberto: «la de 1 h que iba ganando»; +0,22 R en 15 operaciones en sombra, nada
  concluyente). Como el cerebro de 1 h no tiene modelo, entra por la exploración amplia o la memoria.
  **Apagada otra vez el 23/11 (decisión de Roberto):** 4 operadas, todas el 23/11 por la exploración amplia
  (−1,39 R, −1,73 $). En el laboratorio, ~700 casos a −0,09 R (t ≈ −2,4; holdout −0,11). En sombra iba +0,48 R
  (27 casos) y se sigue midiendo allí: si pasa de 50 casos en positivo, merece un estudio aparte.
- **R-07 vía de decisión** (`ledger.via_decision`, `op["via"]`): cerebro / cerebro_exploracion / exploracion_amplia /
  cartera_funding / memoria. Panel → Operaciones → «Por vía» (`GET /api/vias`, `panel.resumen_vias`, desde la última
  puesta a cero), y «Quién decidió» en la ficha.
- **R-10**: `op["decision"]` guarda también `cerebro` y `aprendizaje`; la ficha muestra la predicción del cerebro.
- **Fallo arreglado**: una decisión de AMPLIACIÓN descartada (`ampliacion: true`) sobrescribía la decisión de entrada
  (la operación perdía plan, apalancamiento y vía; caso ZEC `op-20261119225043-d76a8e`). Ahora va a
  `op["decisiones_ampliacion"]`.
- **R-09 arranque rápido** (`motor._cargar_funding_disco` / `_guardar_funding_disco`): el funding histórico se guarda
  en `funding_vivo_cache.json`; tras reiniciar solo se baja lo nuevo. Es caché: si falta o está rota, se descarga.
- **R-11**: `bot.log` YA rotaba (5 MB × 3, `observabilidad.configurar_logs`); la auditoría se equivocó.
- **R-14 stops con el bot parado** (`papel._recuperar_hueco`): si `procesar()` no corre en > 3 min
  (`papel.HUECO_MIN_S`), se repasan las velas reales de 1 min del hueco y se ejecutan en orden cronológico los stops y
  objetivos reduce-only que se habrían disparado (stop al disparo o a la apertura si hubo hueco, ESTIMADO). Queda en
  `papel.json` → `huecos_recuperados`. Las velas son de operaciones, no de marca (aproximación).
- **Reloj de baja resolución** (salió al probar con Python 3.12 en Windows): `ledger.destino_libre` (al rotar ledger o
  feed nunca se pisa un archivado con el mismo nombre; antes se perdían eventos) y `gestor._ultima_tp` (empate de hora
  -> gana el objetivo creado después; antes la conciliación duplicaba el objetivo final).
- **Hetzner** (Roberto, 21/11; sustituye a Oracle): `despliegue/GUIA_HETZNER.md`, `herramientas\parar-para-migrar.bat`
  (`despliegue/parar_windows.ps1`). `instalar_vps.sh`: recordatorio mensual solo en Oracle, exige Python ≥ 3.12, reinicio
  automático a las 07:30 (hora de Madrid; antes 04:00 chocaba con el laboratorio). Las pruebas pasan con 3.12 y 3.14;
  el bot aún no se ha ejecutado en Linux (la guía pide pasar las pruebas en el servidor antes de arrancar).
- 734 pruebas (`tests/test_mejoras_auditoria.py`).
- **Preregistro: veredicto falso anulado** (21/11): «fuerza_4h confirmada» (30 ops, +0,40 R, t 10,77) lo escribió el
  17/11 14:08 una prueba de humo de Claude con datos inventados: `cargar_estado`/`guardar_estado` fijaban la ruta al
  definirse y cambiar `pr.RUTA_ESTADO` no la redirigía. Arreglado (ruta al llamar + prueba). Quitado de
  `preregistro_estado.json` (queda `anulado`) y de `estrategia_elegida.json` → «acumulando»; el laboratorio del 22/11
  vuelve a contar. Copias de antes en el scratchpad de la sesión. 735 pruebas.

## Cambios del 22/11/2026 (ideas copiadas de HyperGrok, galleonlabs/hypergrok-trading-desk; pedidas por Roberto)

HyperGrok no trae estrategia: se copiaron solo controles y método. Su código se leyó sin ejecutarlo.
- **Nota de proceso** (`revision_proceso.py`, sin efecto): por operación, cómo se hizo y no cuánto ganó (stop puesto y
  verificado, deslizamiento de entrada y de stop en pb, riesgo real/plan, costes en R, orden de pasos, incidencias).
  Nota A–D y cuadrante proceso × resultado. Ficha de la operación y Operaciones → Proceso (`/api/proceso`), con
  calibración del deslizamiento por tipo de entrada (creadora/tomadora) para el pendiente 5.
- **Escéptico en sombra** (`analista_ia.revisar_aperturas`): la IA da el mejor argumento en contra de cada apertura con
  los datos de la entrada (≤ 4 h después, 2 por pasada, deja 12 consultas al día para lo demás). No decide nada; se mide
  en Objetivo → Escéptico (`registro/analista/esceptico.jsonl`; marcador frente a «decir siempre en contra»).
- **Calendario macro** (`calendario_macro.py` + `calendario_macro.json`, sin efecto): FOMC e IPC 2019–2026 copiados de
  federalreserve.gov y bls.gov; horas de Nueva York calculadas sin zoneinfo. Solo lo usan el escéptico y el estudio
  `python investigacion.py --estudio-macro` (hipótesis fija: no abrir de 12 h antes a 2 h después; resultado en
  `registro/estudio_macro.json`). Filtrar entradas exigiría pasarlo a ARCHIVOS_CODIGO y superar el laboratorio.
  **Resultado del 22/11: NO mejora** (7 de 20 pares, −0,006 R de media, p = 0,94; 158 citas). Las abiertas cerca de una
  cita dieron +0,10 R de media (2906), pero no era la hipótesis fijada: como mucho, una pista. No se activa nada.
  Vista **«Parte del mar»** (`#/macro`, `vistas/macro.js`, `/api/macro`): las citas como tormentas en un horizonte SVG
  animado (olas que crecen cerca de cada cita, lluvia = ventana 12 h/2 h, rayo = Fed), estado del mar con cuenta atrás,
  estelas de las operaciones abiertas que cruzarán una tormenta, boletín, huella real de las últimas citas en BTC (velas
  archivadas; oleaje frente a la mediana de 4 h) y el estudio. Respeta reduced-motion y la CSP (sin estilos en línea).
- **Caducidad de envíos reales** (`ordenes.caducidad_envio_seg`: 15): `Ejecutor.enviar` fija `expiresAfter` solo en ese
  envío (si el exchange lo admite; la cuenta simulada no). Si la respuesta es dudosa y la orden sigue sin constar pasada
  la caducidad, se da por rechazada sin congelar el mercado. Probado solo con exchanges falsos.
- **Manifiesto de datos del laboratorio** (`manifiesto_datos.py`, sin efecto): huecos de velas, cobertura de funding y hash
  por mes; avisa si un mes ya cerrado cambia entre ejecuciones (historia reescrita). `registro/manifiesto_datos.json` y
  bloque `manifiesto_datos` en `estrategia_elegida.json`.
- **Tramos de margen** (`riesgo.tramos_margen` / `dimensionar_con_tramos`): el apalancamiento máximo baja con el tamaño
  según `marginTables` de Hyperliquid. Con 230 $ no cambia nada.
- **Techos duros del real** (`riesgo.TECHOS_REAL`): config y panel no pueden pasarlos. Fijados en lo que ya regía
  (3 % / 9 % / 5× / 6 posiciones / pérdida diaria 10 %): no cambian nada hoy. Roberto decidió (22/11) mantenerlos.
- Cambia la huella de código (ejecucion, riesgo, bot, configuracion, laboratorio, promocion): la evidencia para
  promoción empieza de nuevo (hoy no había nada promovible). 756 pruebas.

## Cambios del 23/11/2026 (pedidos por Roberto)

- **Estrategias apagadas** (`config.json → estrategias`, siguen en sombra): `retroceso_1h`, `retroceso_4h`,
  `funding_4h` y `reversion_4h`. Las tres de 4 h son negativas en todos los laboratorios y también en vivo:
  - `retroceso_4h`: −0,10 R en 1511 casos, t −3,8, holdout −0,17; 3 de 3 perdidas en vivo.
  - `funding_4h`: −0,13 R, holdout −0,11; −0,41 R en 10 en sombra.
  - `reversion_4h`: −0,10 R, holdout −0,62 (11 casos); −0,88 R en 7 en sombra.

  Siguen activas `momentum_4h` (en sombra +1,12 R en 59), `ruptura_4h`, `fuerza_4h`, `ballenas_1h` y la cartera de
  funding. El cerebro de 4 h ya no recibe las apagadas: solo las ve en sombra.
- **Vista «Sónar de sombras»** (`#/sombras`, `vistas/sombras.js`, `GET /api/sombras` → `panel.resumen_sombras` →
  `sombras.py`, «sin efecto»; 6 pruebas en `tests/test_sombras.py`). Lee las sombras de `aprendizaje.json` desde
  la última puesta a cero. La vista tiene cinco partes:
  - **Balanza:** lo que se ahorró (R de las sombras perdedoras) frente a lo que dejó pasar (R de las ganadoras).
  - **Sónar:** ángulo = estrategia, distancia al centro = antigüedad, color = resultado, tamaño = |R|. El barrido las
    ilumina; filtros 7 d / 30 d / todo y ganadoras / perdedoras / abiertas; pulsar un nombre enfoca esa estrategia.
  - **«En el agua ahora»:** las abiertas en un carril que va del stop al objetivo, con su R al último cierre de 1 h
    archivado.
  - **«¿Acertó al descartar?»:** R medio por motivo de descarte, con su lectura (≥ 30 casos y |t| ≥ 2).
  - **Estelas:** R acumulada por estrategia, con un aviso si una apagada gana con claridad (≥ 50 casos y t ≥ 2).

  Los resultados de las sombras son modelados (muestreo puntual). Solo informa.
- **Lo que mostró al estrenarse (650 sombras desde el 28/10):** el conjunto da +0,07 R (t 1,7), un empate.
  - «El cerebro dijo no» acierta: −0,20 R, t −2,5.
  - «Sin hueco o demasiado riesgo» descarta operaciones que luego ganan (+0,48 R, t 3,6). Son límites de riesgo: no
    se tocan por esto.
  - `funding_1h` (apagada) gana en sombra: +0,23 R en 81, t 2,3. En el laboratorio sale −0,11 R, así que, como mucho,
    merece un estudio.
- CSS del panel: ojo con los nombres de clase genéricos. `.viva`, `.carril`, `.motivos` y `.motivo-barra` ya existían;
  la vista usa `en-agua`, `agua-carril`, `descartes` y `desc-*`. 764 pruebas.

## Cambios del 13/11/2026 (pedidos por Roberto, por encima de la congelación)

- **Estrategias de 1 h retiradas** (`config.json` → `estrategias.*_1h.activa: false`). Solo proponen las de 4 h.
- **Filtro de régimen de BTC** (`filtros_entrada.regimen_btc`, activo): solo se entra a favor de la tendencia de BTC
  (cierre frente a su media exponencial de 200 velas, `senales.btc_alcista_en`). Si no se sabe el régimen, no entra.
  La exploración amplia no se lo salta. Reduce el número de operaciones.
- **Cerebro con rasgos recortados a ±3** (`cerebro.RECORTE_Z`, antes ±5). El modelo vigente se entrenó con ±5 y se
  evalúa con ±3 hasta que el laboratorio lo regenere.
- **Cartera del factor de funding** (`cartera_funding.py` + `bot._candidatas_cartera_funding`, SOLO simulado): los
  lunes 00:00 UTC (ventana de 12 h), largo en las 2 monedas de funding medio de 7 días más bajo y corto en las 2 de
  más alto, 1 % de riesgo por pata, las dos patas o ninguna, dentro de los límites de siempre. No pasa por el cerebro,
  va marcada `cartera_funding` y «explorando»; solo toca sus propias posiciones. No es lo mismo que lo medido en el
  estudio B (ver el docstring del módulo) y no está validada como rentable.
- Cada uno de estos cambios reinicia la evidencia en vivo y cambia la huella.

## Cambio del 14/11/2026 (pedido por Roberto)

- **Momentum v2 protege ganancias** (`senales.MODULOS["momentum"]`, versión 2): sigue sin objetivo, pero al avanzar 1,5 R
  el stop sube a sin pérdidas y desde ahí persigue al precio a 1,5 R (`breakeven_tras_r`/`trailing_r` 1,5,
  `trailing_sin_parcial`). Antes (v1) el stop no se movía. Valores de criterio, no optimizados: el laboratorio del
  domingo 15/11 los mide con la misma regla. Sin evidencia en vivo de que mejoren el resultado.
- `motor._cargar_estrategias`: un veredicto del laboratorio hecho con otra **versión** del módulo ya no impone su salida
  (la salida de v1 estaba guardada en `estrategia_elegida.json` y anulaba la v2). Solo afecta hoy a momentum.
- Solo aplica a operaciones **nuevas**: cada posición guarda su propia `salida` al abrirse. La UNI abierta (v1) conserva
  stop 6,9109 y salida a tiempo máximo (19/11 00:04 UTC). Posiciones y saldo no se tocaron. 580 pruebas.
- **Ajuste manual desde el panel** (pedido por Roberto, SOLO simulado): dentro de CADA operación abierta (portada →
  tocar la posición → «Ajustar esta operación», `operaciones.js`); no hay control general. La portada muestra el
  objetivo de cada posición junto a su stop.
  Comandos `/stopmanual` y `/tpmanual` (`panel.COMANDOS`, `bot.ajuste_manual`, `gestor.ajustar_manual`). Reglas: solo
  desde el panel (nunca Telegram), solo posiciones del propio bot, el stop no puede quedar más lejos que el inicial ni
  al otro lado del precio, el objetivo debe estar del lado de la ganancia; todo se valida antes de cancelar nada. El
  panel solo admite estos comandos en local. Quedan en `op["ajustes_manuales"]`. Añadir/quitar monedas ya existía:
  Configuración → Monedas («Incluir siempre» / «Excluir»), con previsualización y reinicio ordenado.
- 14/11 20:46 UTC: stops de ENA y UNI (momentum) movidos a mano con la regla v2: ENA 0,16023 → 0,14239 y UNI
  6,9109 → 5,8867 (breakeven a 1,5 R y trailing 1,5 R tras el mejor precio). Solo cambiaron `sl` y `en_breakeven`.
  604 pruebas.
- `comandos_panel.json` debe escribirse **sin BOM** (con BOM el bot lo ignora).

## Cambio del 17/11/2026 (pedido por Roberto): acelerar el veredicto sin hacer trampas

- **Búsqueda congelada** (`laboratorio.busqueda_congelada: true`): la investigación nocturna ya no prueba ideas nuevas
  (cada una subía el listón de t para todas: 1.098 variantes → t ≥ ~4). Sigue juzgando las aspirantes en vivo. El
  laboratorio avisa si una ejecución añade variantes (cambiar una rejilla o la versión de un módulo las añade).
- **Hipótesis prerregistradas** (`preregistro.py`, solo informe): `fuerza_4h` con los parámetros del 15/11 y
  `carry_realista` con umbral 20 %. Solo cuentan operaciones abiertas desde el 17/11/2026 y ya cerradas; muestra
  fijada de antemano (30 operaciones y 20 días distintos) y juicio UNA vez (media > 0, t por días ≥ ~2 al corregir
  por 2 hipótesis, > 0 con costes al doble). Hasta llegar, «acumulando» sin mostrar resultado. El veredicto queda en
  `preregistro_estado.json` y es definitivo; si cambia la definición, «invalidada». No activa ni autoriza nada.
  Ritmo esperado: fuerza ~5 operaciones/mes (unos 6 meses), carry ~11/mes (unos 3 meses).
- **Laboratorio solo con estrategias de 4 h** (`laboratorio.intervalos_estrategias: ["4h"]`): la simulación de 1 h
  (~50 min) desaparece. Las velas de 1 h se siguen descargando para ballenas, libro y mercado grabado. El cerebro de
  1 h ya no se regenera.
- **Meseta de parámetros** (`validacion.meseta`): los parámetros elegidos no pueden ser un pico aislado; si ningún
  vecino de la rejilla rinde parecido fuera de muestra, el módulo no supera (`resultados.<clave>.meseta`).
- **Prueba de lookahead** (`tests/test_lookahead.py`): señales de todos los módulos con toda su rejilla, rasgos del
  aprendizaje y del cerebro, ranking de fuerza y régimen de BTC calculados con historia completa y cortada: no hay
  fugas. Incluye un control que demuestra que la prueba caza una fuga deliberada.
- Panel: el CSV neutraliza textos que Excel abriría como fórmula (`panel.celda_csv`); las fichas distinguen
  «— sin dato» de «ninguno» (`dom.listaDef`); el título de la pestaña lleva las operaciones abiertas «(4) …».
- **Avisos de Telegram** (`notificaciones.ControlRuido`, config `avisos`): no repite el mismo texto en 10 min y admite
  horas de silencio (vacías por defecto) que solo callan lo informativo; avisos, errores y respuestas pasan siempre.
- Cambia la huella (bot.py, laboratorio.py, validacion.py, configuracion.py) un día antes del fin de la prueba de dos
  semanas: decidido por Roberto. 639 pruebas.

## Cambio del 18/11/2026 (tras analizar day-trader-skill; Roberto eligió A y C)

- **A. Riesgo desconocido nunca cuenta como 0** (`riesgo.riesgo_posicion`): si una posición no tiene `riesgo_usd` se
  estima como tamaño × |entrada − stop|; si tampoco se puede, `comprobar_agregados` bloquea entradas nuevas, la cartera
  de funding no abre patas y la portada avisa («Riesgo desconocido: …»). `exposicion()` devuelve `riesgo_desconocido`.
  Antes se sumaba `riesgo_usd or 0` (mismo defecto que la issue #55 del repo). Hoy no cambia nada: ENA y UNI lo tienen.
- **C. Ficha «Qué cabe esperar»** en el detalle de cada operación (`operaciones.js`, `fichaEsperable`): lectura de la
  estrategia fuera de muestra (a favor / en contra / moneda al aire según el IC del R medio), % de ganadoras, R medio
  e IC, y resultados en vivo. El laboratorio guarda `resultados.<clave>.probabilidades` (`validacion.probabilidades`:
  reparto por tipo de salida, IC de Wilson y bootstrap al 95 %); hasta el laboratorio del 22/11 se usa lo que ya hay
  (IC al 90 % del veredicto) y el reparto de salidas no aparece. Describe el pasado; no predice la operación.
- Descartado por Roberto de momento: **B** (freno si el precio ya se movió en contra desde la señal).
- 650 pruebas.

## Panel «terminal», fase 1 (18/11/2026, pedido por Roberto, inspirado en un vídeo de TikTok)

- Tema oscuro tipo terminal por defecto (`app.css`, tokens en `:root`); tema claro con `html[data-tema="claro"]`
  (Más → Tema claro; `localStorage` «panel.tema», solo comodidad visual).
- Cabecera: marca, estado, contadores (variantes, listón t, abiertas, riesgo) y reloj UTC; **cinta de eventos** en
  vivo bajo la cabecera (`/api/feed`, cada 30 s, se para al pasar el ratón). `marco.js` lo gestiona.
- Escritorio (> 860 px): **menú lateral agrupado** (Resumen · Dinero · Cerebro · Sistema) con insignias; móvil: barra
  inferior de siempre.
- Portada ancha: **embudo** de idea a real (tira deslizable en móvil) y **núcleo 3D** (`nucleo.js`): esfera de
  partículas en canvas propio, halo, órbitas y hilos con pulsos de las fuentes de datos a lo que sale del cerebro.
  Las cifras son reales; la esfera es decoración. ~30 fps, menos partículas en móvil, se para fuera de pantalla, con
  la pestaña oculta y con «reducir movimiento». Sin librerías externas (CSP estricta).
- Fases 2 y 3 (18/11): portada en pestañas (Resumen · Cuenta · Control); en Resumen la tubería de idea a real,
  el núcleo, «Necesita tu decisión» (tarjetas que solo informan y enlazan; nunca aprueban) e «Informe del día».
  Estrategias: lista con minigráfico y barra de evidencia (t frente al listón) y ficha propia `#/estrategia/<clave>`
  con acierto, R:R, esperanza, operaciones, caída máxima, curva de capital, caída «bajo el agua» y robustez por meses.
  El laboratorio guarda `resultados.<clave>.curva` (`validacion.curva_estrategia`, solo informe) y `/api/laboratorio`
  da `mini` y `preregistro`: la curva y los meses aparecen tras el laboratorio del 22/11.
- Sin páginas infinitas: pestañas por vista (`dom.pestanasVista`, barra pegada arriba) en Inicio, Estrategias,
  operación, Objetivo, Sistema, Aprendizaje y Ballenas; Actividad muestra 25 eventos con «Ver más»; Operaciones 15
  por página. Textos cortos en pantalla y explicaciones en diálogos ⓘ (`info.ayuda`, `info.titulo`).
- **Taller** (18/11, antes «Sistema»; `taller.py` + `vistas/taller.js`, `GET /api/taller`): revisión completa en lenguaje
  llano con 22 comprobaciones en 5 bancos (Motor, Datos, Protección, Cerebro, Almacén), anillo de salud, «planta» con una
  luz por banco, órdenes de trabajo por gravedad y libro de la sesión. Estados: ok / aviso / mal / pendiente (cosas tuyas,
  p. ej. Telegram) / desconocido (nunca cuenta como ok). Se revisa al abrir y cada 30 s.
  Arreglos con botón (SOLO estos, desde este equipo; `panel.COMANDOS_TALLER`): `/reanudar`, `/aplicarconfig` (reinicio
  ordenado), `/laboratorio`, `/investigacion`. Tras cada arreglo el taller VUELVE A REVISAR y dice «arreglado y comprobado
  ✓» o «sigue sin quedar en orden». Lo que debe hacer una persona (poner TELEGRAM_TOKEN o PANEL_PASSWORD en .env, abrir
  INICIAR.bat) se explica paso a paso; de `.env` solo se lee si una variable tiene valor, nunca el valor. No cambia
  configuración, límites, modo ni promoción.
- Configuración con ayudas plegadas «¿Qué es?» y barra de cambios fija; Costes: consumo de la IA del analista en el Taller.
- **Mesa** (18/11, portada → pestaña «Mesa»; idea de un vídeo de un «equipo de agentes»; `mesa.py` + `vistas/mesa.js`,
  `GET /api/mesa`): (1) «El equipo»: 8 puestos (Escáner, Cerebro, Riesgo, Tamaño, Ejecución, Guardián, Ballenas,
  Laboratorio) con cifra viva, barra de uso y lo último que hizo cada uno según el feed (la tarjeta se ilumina con cada
  novedad; se refresca cada 12 s); (2) «¿Por qué no entra nada?»: motivos reales de las propuestas del último cierre y
  de las 24 h, agrupados en lenguaje llano (las hipótesis solo de investigación no cuentan); (3) «Cada número que cree el
  bot»: límites vigentes con su valor actual (✓ / ! a partir del 80 % / ✕). Solo lee datos ya registrados; no decide nada.
  El vídeo era promocional (memecoins con enlace de afiliado): no se tomó nada de su operativa, solo ideas de presentación.
- **Animación y vida del panel** (18/11, solo presentación; `js/anim.js`, `nucleo.js`, `marco.js`, `app.css`): el núcleo 3D
  tiene núcleo interior que late, tres anillos giroscópicos con satélites, constelación, polvo con paralaje, tinte por salud
  (rojo/ámbar/verde), entrada animada, interacción (sigue al cursor, se arrastra con inercia, un toque lanza una onda) y
  **reacciona a eventos reales**: `marco.js` sondea el feed cada 12 s y emite cada evento nuevo (máx. 4, no el histórico) por
  el bus `panel:evento`; el núcleo lanza ondas/pulsos de color por tipo y la Mesa añade el evento a la bitácora del puesto.
  Mesa: tarjetas en 2 columnas (1 en móvil) con cifra grande que cuenta (`cifraViva`), minigráfico de las últimas 30 muestras
  y bitácora de 5 eventos. Resto: cifras que cuentan (cabecera, tubería), entrada escalonada al abrir vista o pestaña
  (`.anim-entrada` en `main`, ~1,6 s), micro-interacciones. ~30 fps, pausa fuera de pantalla, y todo se apaga con
  `prefers-reduced-motion`. `dom.h` acepta variables CSS en `estilo`. Sin cambios en bot, riesgo ni órdenes.
- **Operaciones rediseñada** (19/11, `vistas/operaciones.js`, solo presentación): tres pestañas. «En vivo»: cada posición
  abierta es un carril (stop · entrada · objetivos) con el precio de ahora moviéndose entre ellos, resultado abierto, stop
  confirmado/sin confirmar y aviso si está a < 0,6 % del stop (se repinta cada sondeo vía `actualizar`). «Historial»:
  KPIs (cerradas, neto, R medio, anillo de ganadoras), tira de pulso con las últimas 24 cerradas y operaciones agrupadas
  por día con barra de R (±3 R); en modo experto sigue la tabla. «Descartes»: propuestas rechazadas. La ficha de una
  operación abierta muestra el mismo carril. Los ajustes de stop/objetivo siguen solo en la ficha (los valida el bot).
- 682 pruebas.

## Prueba de dos semanas (04/11/2026 a 18/11/2026)

- **Veredicto** (`veredicto.py`, panel → Más → Objetivo y analista): adelante / cambiar de rumbo / no vale, con criterios
  fijados de antemano y calculados por código. No lo decide ninguna IA y no los cambies a mitad de prueba.
- **Código congelado hasta el 18/11** (ya terminó): en los archivos de `promocion.ARCHIVOS_CODIGO` y en la config que entra en la huella,
  solo fallos claros. Cada cambio reinicia la evidencia de las estrategias. Ideas al azar de investigación en pausa
  (`investigacion.PAUSA_ALEATORIAS_HASTA`): cada una sube el listón de todas.
- **Analista** (`analista_ia.py`): corre en el proceso del panel. Informe diario, revisor de cada operación cerrada,
  vigilante (las alarmas las detecta código; la IA solo las explica) y marcador de aciertos. Sin `GROQ_API_KEY` en `.env`
  sigue lo que no es IA. Modelo `openai/gpt-oss-120b` (tope de 40 consultas al día). Solo lectura: sus ideas pasan por
  `investigacion.py` y sus correcciones son texto. Nunca le des acceso a órdenes, configuración o promoción.
  **Groq (19/11)**: del 13 al 19/11 el informe fallaba con 413 porque petición + `max_tokens` superaba el límite de
  8000 tokens/minuto del plan gratuito (pedía 9485). Ahora `ajustar_a_presupuesto` recorta datos antiguos hasta caber
  (y lo dice en `nota_recorte`), `reasoning_effort: low` evita que el razonamiento corte el JSON (400), y un 429 espera
  `retry-after` y reintenta una vez. El error guardado incluye el código de Groq (nunca el cuerpo).

## Cuenta agresiva: experimento aparte, SIMULADO y en marcha (25/11/2026)

- Pedida por Roberto: señales PROPIAS de 15 min al estilo de los canales de señales (stop corto, cinco objetivos,
  apalancamiento alto) para ver con números si ese estilo es viable. Paquete `agresiva/`, proceso aparte
  `python -m agresiva.motor` (lo arranca `despliegue/iniciar_windows.ps1`; en VPS, `bot-ballenas-agresiva.service`).
- **No toca el bot**: cuenta propia `papel_agresiva.json`, registro `registro/agresiva.jsonl`, estado `agresiva_estado.json`,
  ajustes opcionales `agresiva_config.json` (claves de `agresiva.logica.CFG_DEFECTO` + `intervalo_s`, `pausa_peticion_s`,
  `activo`). Ningún .py de la raíz lo importa (prueba), sin código de órdenes (prueba), solo `/info` público con lista
  blanca y se para si `config.json` no está en simulado. No está en `promocion.py` a propósito: la huella no cambia.
- Panel: sección propia «Agresiva» (barra de arriba y lateral → «Experimento aparte»), `/api/agresiva` solo lectura,
  vista `panel_web/assets/js/vistas/agresiva.js`. Cada señal abierta lleva su gráfico de velas en vivo (1 min de las últimas 6 h o 15 min
  de 30 h, con la vela en formación) con liquidación, stop, entrada, objetivos, precio de ahora y eventos: las velas las
  lee el motor en cada pasada (`MotorAgresiva._graficos`, una consulta por moneda que sirve también para mover stops) y
  van en `agresiva_estado.json`; el panel las pinta con `grafico.graficoVelas` y se refresca cada 15 s. No se mezcla con operaciones, estrategias ni ledger de las ballenas.
- Reglas fijadas con Roberto: 232 $ ficticios; reglas `ruptura_15m`, `retroceso_15m`, `giro_15m`; stop 1,5×ATR entre
  0,8 % y 3 %; objetivos 0,5/1/1,5/2/3 R con 20 % cada uno y stop a la entrada tras el primero; cierre a 48 h; máx. 3
  abiertas; 20× recortado al máximo de la moneda y sus tramos (hasta el 25/11 con margen aislado fijo del 10 %; desde la
  auditoría, riesgo fijo del 5 %, ver abajo); si la liquidación llega antes que el stop, se liquida. **Gemela** con las mismas señales a riesgo 2 % y
  ≤ 5× para separar señal de apalancamiento. Frenos: pausa 24 h al perder 50 % (una vez por etapa), sin entradas el resto
  del día UTC al perder 15 % en el día, quiebra < 10 % del inicial (cierra y para). Reinicio solo a mano:
  `python -m agresiva.motor --reiniciar` (deja `agresiva_reinicio.json`; cada etapa queda contada).
- Universo: las 25 monedas de más volumen (≥ 20 M$/día), refrescado cada 6 h. Peticiones de 15 min espaciadas 3 s para
  no comer el límite de la API que comparte con el bot.
- **Auditoría y arreglos del 25/11/2026** (`audit/agresiva/README.md`, pedidos por Roberto: «arregla todos los errores y
  haz la cuenta agresiva»). Cuenta versión 2 (`cuenta.migrar_estado` anota el cambio en `cambios_reglas` y en el registro;
  las señales ya abiertas conservan su tamaño):
  - **F8 riesgo fijo**: `riesgo_pct` 5 % hasta el stop (con comisiones); el apalancamiento solo decide el margen
    (`margen_max_pct` 30 % por operación, `margen_total_max_pct` 90 %); si no cabe, arriesga menos (`recortada`). Antes,
    margen fijo del 10 % → mediana 1,2 % de riesgo, menos que la gemela.
  - **F1** cada pierna se abre aunque la otra no pueda (`sin_gemela`, contador `solo_agresiva`). En la historia vieja la
    gemela arruinada bloqueó 1 032 entradas de la agresiva.
  - **F2/F6** `min_orden_usd` 10 $ en entradas; `logica.tamanos_objetivos`: parciales redondeados a `szDecimals` y, si no
    llegan a 10 $, juntados con el siguiente (no confirmado si Hyperliquid exime las reduce-only).
  - **F3** liquidación por el libro conserva el margen sobrante; hueco por debajo de 2/3 del mantenimiento = rescate (todo).
  - **F4** stop y liquidación con `logica.vela_disparo`: el extremo en contra es el menos extremo de la vela de 1 min de
    Hyperliquid y la de Binance (`motor.velas_binance_1m`, GET público). Sin perpetuo en Binance → solo Hyperliquid
    (`sin_binance`). La historia sigue con la vela de Binance.
  - **F5** objetivos que una vela ya abre más allá se llenan a su precio (orden límite en reposo).
  - **F7** funding de `fundingHistory` (lista blanca) cada hora, dentro del margen aislado (`margen_extra`), mueve la
    liquidación. Se aplica antes de pasar las velas.
  - **F9/F10 historia**: universo diario = las `--monedas` de más volumen de Binance de los 7 días ANTERIORES entre todas
    las de Hyperliquid (también retiradas) y Binance (`historia.universo_por_dia`, cachés `datos_backtest/agresiva_1d/` y
    `agresiva_funding/`), funding de Binance y Monte Carlo por días (`rendimientos_diarios`).
  - La prueba de aislamiento prohíbe ahora `hyperliquid.xyz/exchange`, `"/exchange"` y rutas de órdenes de Binance (la URL
    pública `exchangeInfo` de Binance es lectura).
  - Historia rehecha tras los arreglos (28/07–25/11/2026, 20 monedas al día, 51 distintas): 2 330 operaciones,
    gemela −0,17 R, agresiva −1 038 $ con riesgo medio 3,4 % y 4 quiebras (32, 20, 19 y 28 días), 0 liquidaciones; ruina
    por días 100 % (mediana 25 días). 816 pruebas (52 de la agresiva).
- `python -m agresiva.historia`: misma lógica sobre 120 días de velas de 15 min de Binance (caché en
  `datos_backtest/agresiva_15m/`) + Monte Carlo → `agresiva_historia.json` (lo muestra el panel). Primera pasada (25/11):
  2805 operaciones, gemela −0,17 R de media y 44,6 % de acierto (negativa en las tres reglas), agresiva −569 $ con
  2 quiebras (≈ 47 y 45 días por etapa) y 0 liquidaciones; las comisiones son ~45 % de la pérdida. Con los máximos de
  Hyperliquid (la mayoría 3–10×) la agresiva arriesga ~1–2 % por operación, poco más que la gemela.

## Carry de funding: fase 3 hecha, SIMULADO y en marcha (19/11/2026)

- **Motor propio** `carry/motor.py` (`python -m carry.motor`): proceso aparte del bot y del panel (lo arranca
  `despliegue/iniciar_windows.ps1`; en VPS, `bot-ballenas-carry.service`). Cada 10 min: acredita el funding real
  (`fundingHistory`), cierra si `logica.evaluar_salida` lo pide, abre la mejor oportunidad con `abrir_par` (libros reales
  de la API pública) y escribe `carry_estado.json` (lo lee el panel: Estrategias → «Carry (2 patas)», `/api/carry`),
  `papel_carry.json` (cartera) y `papel_spot.json` (contado). Registro en `registro/carry.jsonl`. Cuenta ficticia propia
  (200 $, `carry_config.json` opcional: `cuenta_simulada_usd`, `intervalo_s`, `activo` y claves de `logica.CFG_DEFECTO`).
- **No toca el bot**: no usa `papel.py`, ledger ni riesgo, y no hay ninguna importación desde la raíz (prueba). La huella de
  código/config no cambia, así que no reinicia la evidencia de las estrategias. Se niega a correr si `config.json` no tiene
  `modo: simulado`. `papel_perp.py` simula el corto con libro real, comisión 0,045 % y funding real.
- Hoy (19/11) ninguna moneda llega al listón de 20 %/año (BTC 8,9, ETH 5,2, HYPE 10,2, SOL 0,4, ZEC 10,6): el motor espera;
  no se baja el listón (es el del laboratorio y el de la hipótesis prerregistrada). Pendiente: dejar que acumule cierres.
- Paquete `carry/` (no en la raíz, para no tocar la huella): `terreno.py` (fase 0, solo lectura de la API pública),
  `logica.py` (fase 1, funciones puras), `papel_spot.py` y `ejecucion.py` (fase 2, contado simulado y las dos patas con
  deshacer/igualar). Sin órdenes reales ni cuentas.
- Fase 0: contado verificado en Hyperliquid con base < 0,1 % y horquilla < 0,01 %: BTC, ETH, SOL, HYPE y ZEC
  (`datos_mercado/spot_hl.json`, se regenera con `python -m carry.terreno`). En `spotMetaAndAssetCtxs` los pares y sus
  contextos NO van en el mismo orden: emparejar por nombre.
- Fase 3: hecha como proceso aparte (ver arriba). No se clasificó en `promocion.py` ni se llevó al ledger a propósito: así no
  cambia la huella. Si algún día entra en la decisión del bot o en real, habrá que hacerlo con aprobación expresa de Roberto.
- `investigacion.py --estudio-regimen`: ¿ayuda operar a favor de la tendencia de BTC? Estudio con una pregunta fijada de
  antemano; no cuenta como variante. Resultado en `registro/estudio_regimen_btc.json`.
- El veredicto muestra «¿Bot o mercado?» (`veredicto.contra_mercado`): las mismas operaciones todas cortas o todas largas.
  El analista: «retirar» solo con t ≤ −2 o 5+ operaciones negativas en vivo; ideas solo los lunes.

## Arquitectura (archivos clave)

| Archivo | Qué hace |
|---|---|
| `bot.py` | Bucle principal, procesar candidatas, comandos del panel, agenda, panel_datos |
| `motor.py` / `senales.py` / `estrategia.py` | Estrategias (proponen en cada cierre de vela 1 h / 4 h), gestión de capital |
| `cerebro.py` / `cerebro_vivo.py` / `mercado_unificado.py` | Modelo ridge, decisión en vivo, rasgos comunes lab/vivo |
| `riesgo.py` | Tamaño (incluye funding previsto), límites, suelo de emergencia, rebase de capital |
| `gestor.py` / `ejecucion.py` | Una operación por moneda, stops verificados, conciliación, órdenes huérfanas |
| `papel.py` | Cuenta simulada (`papel.json`), registra `ajustes_capital` |
| `laboratorio.py` / `validacion.py` / `historia_externa.py` | Walk-forward, holdout sellado, t por días, cartera, historia Binance/Bybit |
| `investigacion.py` | Ideas nuevas con el rigor del laboratorio |
| `contexto_externo.py` | Datos públicos de Binance/Bybit en vivo (solo velas cerradas) |
| `promocion.py` | Etapas y requisitos para real (huella de código y config) |
| `panel.py` / `panel.html` | Panel web local (127.0.0.1:8080): portada sencilla + modo experto |
| `despliegue/` | Scripts de VPS (Oracle Madrid), systemd, copias a R2 |

## Convenciones

- **Todo .py nuevo** debe clasificarse en `promocion.ARCHIVOS_CODIGO` (afecta a decisiones) o en los «sin efecto»;
  hay una prueba que lo exige. Claves de config sin efecto en decisiones → `promocion.CONFIG_SIN_EFECTO`.
- La huella de aprobación (v3) incluye la identidad del modelo del cerebro (`cerebro_vivo.identidad_modelo`) y
  `contexto_externo`: cambiar un coeficiente o una regla externa invalida cualquier aprobación. Si cambias la
  definición de un rasgo, sube `mercado_unificado.VERSION_RASGOS`. Detalle de la auditoría: `INFORME_AUDITORIA_V12.md`.
- Defaults de configuración en `configuracion.DEFECTOS` (se fusionan con `config.json`). Valida con
  `python bot.py --validar-config`.
- Las pruebas usan `tests/comunes.config()`, que desactiva la agenda y la exploración amplia: actívalas en la
  prueba que las necesite.
- Panel nuevo en `panel_web/` (módulos JS nativos, sin compilar ni Node; detalle en `PANEL_REDISENO.md`): construye el
  DOM con `dom.h()` (textContent, nunca innerHTML) y sin scripts/estilos en línea (CSP estricta). El clásico
  (`panel.html`, en `/clasico`): no uses `onclick` con datos; usa `data-accion`/`data-arg` y `ACCIONES_PERMITIDAS`.
- Dependencias fijadas en `requirements.txt` (y `requirements-bloqueado.txt` con el entorno completo).

## Cómo trabajar

- **Pruebas** (deben pasar todas antes de dar algo por terminado; hoy son 734):
  `.venv\Scripts\python -m unittest discover -s tests -t .`
- **Reiniciar el bot** para aplicar código o config: escribir `comandos_panel.json` con
  `[{"cmd": "/aplicarconfig", "id": "<algo>"}]` (o el panel). El bot sale con código 4 y el lanzador lo rearranca.
  Resultado en `comandos_resultado.json`. Arranque manual: `INICIAR.bat`.
- **Laboratorio / investigación a mano**: comandos `/laboratorio` y `/investigacion` (mismo archivo). El laboratorio
  tarda ~1,5 h (menos desde el 17/11: ya no simula estrategias de 1 h); su registro (`registro/laboratorio_semanal_*.log`) se escribe al terminar.
- **Registros**: `bot.log` (horas en UTC), `registro/ledger.jsonl` (verdad contable), `panel_datos.json`,
  `estrategia_elegida.json` (veredictos), `cerebro_modelo.json` (modelo vigente).
- No borres datos (`datos_backtest/` es caché de 534 MB y se regenera; `datos_mercado/` y `datos_archivo/` no).

- **Explicación de estrategias (19/11)**: `panel_web/assets/js/vistas/explicaciones.js` guarda qué hace / cómo funciona /
  qué persigue cada módulo; se ve en la ficha (tarjeta «Qué es») y como resumen en la lista. Al añadir un módulo nuevo, añade su texto allí.
- **Ceto, la ballena-robot (19/11)**: `panel_web/assets/js/ceto.js` (SVG + burbuja que escribe) da el veredicto en
  «Objetivo y analista» (pestañas Veredicto y Analista). Solo pronuncia lo que calculó el código; no decide nada.

## Pendientes

- Arbitraje de funding: Roberto decidió (19/11) seguir solo dentro de Hyperliquid (el carry). Nada con Binance.

0. **Panel por túnel sin contraseña (temporal)**: `panel.tunel_sin_clave: true` en `config.json` (solo lectura).
   Cuando Roberto ponga `PANEL_PASSWORD` en `.env`, quitar esa opción.
1. **Telegram**: falta que Roberto ponga `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID` en `.env` (él mismo; no los pidas).
2. **Migración a VPS** (Hetzner desde el 21/11; guía `despliegue/GUIA_HETZNER.md`): scripts en `despliegue/` (`instalar_vps.sh`, servicios con
   `.path` para laboratorio/investigación, zona horaria Europe/Madrid). Falta crear la máquina.
3. ~~Carry de funding con dos patas~~ hecho en simulado (19/11). Falta que acumule cierres (hoy el funding no llega a
   20 %/año) y, mucho más adelante, decidir si pasa por `promocion.py`. **Plan detallado por fases en `PLAN_CARRY.md`** (fases 0–2 en archivos nuevos sin
   conectar, compatibles con la congelación hasta el 18/11; la integración, después y con aprobación de Roberto).
4. **Cerebro de 1 h**: ya no se regenera (laboratorio solo con 4 h desde el 17/11). Para recuperarlo, añadir "1h" a
   `laboratorio.intervalos_estrategias`.
5. Calibrar la simulación de ejecución con datos reales (pendiente de operar en real con poco capital).
6. Ir revisando el probador en vivo: con < 30 operaciones cerradas por grupo, nada es concluyente.
