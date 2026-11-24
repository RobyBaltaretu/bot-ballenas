# Registro de hallazgos (borrador de trabajo, se consolida en 03_auditoria_tecnica.md)

Formato: ID · archivo:línea · severidad (P0–P3) · evidencia · estado de verificación.

## Núcleo (bot.py, gestor.py, ejecucion.py, papel.py, riesgo.py, estrategia.py, senales.py, motor.py)

- T-01 papel.py:400-428 vs 283-318 · P1 · Asimetría de muestreo en simulado: los objetivos (límite reduce-only) se llenan
  con mechas de velas de 1 min entre comprobaciones (`_limite_llena`), pero los stops solo se disparan si la marca está al
  otro lado del trigger EN EL INSTANTE de `procesar()` (~15 s). Una mecha que cruza el stop y vuelve entre muestras no
  dispara el stop simulado; una que cruza el objetivo sí lo llena. Sesgo optimista del paper. Verificado por lectura.
- T-02 motor.py:377 · P2 · `time.sleep(1.0)` por moneda e intervalo en el hilo principal al cierre de vela: ~45–90 s sin
  que nadie llame a `papel.procesar()` (los stops/objetivos simulados quedan congelados ese tiempo; el hueco < 180 s no
  activa `_recuperar_hueco`). En real los stops están en el exchange: no aplica.
- T-03 bot.py:813-997 · P2 · `eq`/`libre` se calculan una vez por ciclo; varias aprobadas en el mismo ciclo se dimensionan
  con el mismo margen libre. `papel.order()` NO comprueba margen (papel.py:520-582), así que en simulado nunca hay
  rechazo por margen (en real: `perpMarginRejected`). Divergencia paper/real.
- T-04 bot.py:817, estrategia.py:115-117, aprendizaje (r_minimo_relajado −0,1) · P2 · Tras 24 h sin operar se relajan los
  filtros de la memoria (acepta R esperado −0,1). Antipatrón «operar por aburrimiento»; no tiene justificación estadística.
- T-05 estrategia.py:243-251 vs gestor.py:1215-1226 · P2 · Divergencia lab/vivo del stop dinámico: el laboratorio mueve
  el trailing una vez por vela (4 h) y lo aplica desde la vela siguiente; el bot lo mueve cada ~15 s con el mid. Con
  momentum v2 (trailing 1,5 R) el vivo sale antes en retrocesos intravela. Lo validado no es lo que se opera.
- T-06 estrategia.py:230 · P3 · El laboratorio da por lleno un objetivo al TOCARLO (`favorable >= tpf`); el simulado exige
  una operación impresa PEOR (papel.py:312-315). Lab algo optimista frente al paper.
- T-07 laboratorio.py:200 vs motor.py:309 · P3 · `funding_contra` en el lab = media de 8 h; en vivo = tasa instantánea
  prevista. Mismo nombre, distinta definición (rasgo de la memoria y filtro de entrada).
- T-08 papel.py:245-268 · P3 · Si el bot está parado varias horas, solo se cobra/paga UNA hora de funding al volver
  (salta a la hora actual). Funding de horas perdidas omitido.
- T-09 tests (test_panel_web, test_feed, test_config_panel, test_bot.LatidoExterno, test_panel_proxy) · P3 · Pruebas no
  herméticas: intentan red real a api.hyperliquid.xyz; pasan igual sin red (no detectan nada que dependa de ella).
- T-10 carry/motor.py, carry/terreno.py · P3 · BOM UTF-8 y fin de línea mixto CRLF/LF (terreno.py). Inofensivo para
  Python; síntoma de ediciones desde PowerShell. CLAUDE.md contiene restos literales "`n" (líneas de «Reloj de baja
  resolución» y «Hetzner»).

## Estrategia / configuración

- S-01 config.json → momentum_4h activa · P1 · El laboratorio del 22/11 da momentum_4h (v2) n=1155, −0,107 R, t −3,35
  fuera de muestra. Sigue ACTIVA por un resultado en sombra (+1,12 R en 59 casos, modelado). Selección por el resultado
  más favorable (cherry-picking). Pendiente: confirmar versión en estrategia_elegida.json.
- S-02 ruptura_4h (+0,006 R, t 0,21) y fuerza_4h (+0,088 R, t 0,59) activas sin ventaja medible.

## Cuantitativo (experimentos forense_ledger.py y sesgo_sombras.py)

- Q-01 · Reconstrucción independiente del ledger = cifras declaradas (30 ops desde la puesta a cero, +0,145 R, t 0,67,
  +29,84 $). IC95 bootstrap del R medio [−0,27; +0,56]. Sin las 2 mejores: +7,16 $. Mediana −0,05 R.
- Q-02 · BTC −26,5 % en el periodo (81 253 → 59 753). Exceso de cada operación frente al universo equiponderado en el
  mismo lado y ventana: +0,40 % de media (t 0,53; IC95 [−1,0; +1,9]); 14 de 29 positivas (prueba de signos p=0,64).
  No hay selección mejor que el azar: el beneficio es beta bajista.
- Q-03 · Cortos +0,834 R (17), largos −0,756 R (13). Vía «memoria» 7/7 perdedoras (−0,82 R).
- Q-04 · Las ganadoras salen por TIEMPO MÁXIMO (11 ops, casi todas positivas); el stop medio −1,07 R. Ninguna
  estrategia gana por su objetivo: los objetivos casi nunca se alcanzan.
- Q-05 · Piramidación: 4 ampliaciones, aportación neta +0,02 $. Caso SKY (op-20261123130132-ccb50a): la ampliación se
  ejecutó 7 s después de cobrar el TP1 (reabre la mitad recién cobrada) y convirtió +0,29 R en −0,38 R.
- Q-06 · gestor.py:1506 `analisis_salida_stop` usa el precio MEDIO de todas las salidas (TP1 + stop) para
  `peor_que_trigger_pct`: SKY registró 0,0 % cuando el stop llenó un 2 % peor que su trigger. Métrica que oculta
  el deslizamiento de los stops.
- Q-07 · Sombras: re-simuladas 651 con velas OHLC de 1 h → la sombra sobrestima +0,123 R/op (t 7,7; IC95 [0,09; 0,16]).
  Con los MISMOS supuestos de coste, solo el muestreo puntual infla +0,074 R/op (t 4,7). Conjunto: +0,056 R → −0,068 R.
  funding_1h +0,18 → +0,08 (n.s.); retroceso_1h +0,38 → −0,04; ballenas_1h +0,11 → −0,05.
- Q-08 · momentum_4h: 63 casos (59 sombras + 4 reales), TODOS cortos, de 4 fechas de rebalanceo (29/10, 5/11, 12/11,
  19/11). n efectivo ≈ 4. El «+1,12 R en 59» no es evidencia de ventaja; es la caída del mercado.
- Q-09 · «Sin hueco / demasiado riesgo» (+0,95 R OHLC, n 34) = 19 cortos de momentum + 6 de ruptura_4h bloqueados por
  «máximo 4 del mismo lado» durante la caída. El límite hizo su trabajo (concentración direccional).
- Q-10 · «Contra régimen de BTC»: sombra −0,07 R; OHLC −0,40 R (t −2,8, n 33). El filtro de régimen sí evitó pérdidas
  en este periodo (muestra corta, un solo régimen).

## IA

- IA-01 analista_ia.py:102 · P2 · El prompt del escéptico dice «funding_contra > 0 = el funding juega a favor», pero en
  el código (motor.py:309, bot.py:832) funding_contra > 0 = EN CONTRA. Evidencia: esceptico.jsonl (VVV corto con
  funding_contra −0,0045 → la IA dice que le perjudica; SKY igual).
- IA-02 · El escéptico ha votado «en_contra» 6 de 6: predictor constante, sin información medible.
- IA-03 · El analista no decide nada (verificado: no importa gestor/ejecucion ni escribe config). Coste: 1–40 consultas/día
  (Groq gratuito). Valor económico medido: ninguno.

## Ballenas / datos

- W-01 seleccion.py:117-131 · P1 · Selección por PnL del ÚLTIMO MES (sesgo de recencia/suerte), sin drawdown, sin
  persistencia, sin ajuste por riesgo; `valor_cuenta_min_usd` 100 000 en config (el defecto del código era 500 000).
- W-02 ballenas.py:136-151 · P1 · La señal suma cambios netos de posición: cubrir un corto cuenta como «compra» y
  reducir un largo como «venta». Movimientos defensivos/toma de beneficios se interpretan como entradas.
- W-03 mercado.py:_limpiar · P2 · Borra datos_mercado/ de más de 120 días: la única historia propia de OI/flujo
  (Hyperliquid no la ofrece). Contradice CLAUDE.md («no borres datos_mercado»). Impide validar liquidaciones a largo plazo.
- W-04 contexto_externo.py (docstring) · P3 · Dice «no cambia ninguna decisión del bot», pero alimenta 4 de los 8 rasgos
  del cerebro y su ausencia hace que el cerebro se abstenga.

## Backtest independiente (backtest_independiente.py; Binance USDT-M 4 h, 20 monedas, 2021-01 → 2026-10)

- B-01 momentum_4h (params lab 22/11): n 1442, +0,021 R, t 0,63, IC95 [−0,04; +0,09], t por días 0,28. Por año:
  2021 +0,42 · 2022 +0,14 · 2023 −0,07 · 2024 −0,06 · 2025 −0,06 · 2026 −0,02. Filtro de régimen: no ayuda (+0,01).
- B-02 ruptura_4h: n 2644, +0,011 R (t 0,53). CON filtro de régimen BTC del bot: n 2179, +0,051 R, t 2,22, IC95
  [+0,007; +0,095], t por días 1,20. Contra el régimen: −0,177 R (t −3,9). Cortos +0,099 R (t 3,2) vs largos −0,047.
  Única hipótesis con señal; NO pasa un listón corregido por pruebas múltiples (≈2,9) ni el de días.
- B-03 fuerza_4h: n 455, +0,062 R (t 0,68). Nada.
- B-04 Referencias (sin apalancamiento): BTC comprar y mantener CAGR 18 %, caída 77 %, Sharpe 0,58; BTC largo si cierre
  > EMA200 (4 h) y fuera si no: CAGR 23 %, caída 44 %, Sharpe 0,75. Carteras de las estrategias a 1 % de riesgo por
  operación sin tope de posiciones: Sharpe 0,12–0,36 y caídas enormes (muchas posiciones correlacionadas a la vez).
  Limitación: universo superviviente, fuente Binance, sin cola/latencia; aproximación R → % sin compuesto por posición.
