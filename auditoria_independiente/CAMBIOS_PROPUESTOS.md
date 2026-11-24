# Cambios propuestos por la auditoría

**Ninguno está aplicado.** El código funcional y `config.json` siguen como en el commit `b8a9f8d`. Este documento
y `propuestas.json` se generan desde `experimentos/generar_propuestas.py` (fuente única: no editar a mano).

- **huella**: si el cambio altera la huella de promoción (`promocion.py`); si es así reinicia la evidencia
  válida para real (hoy no hay ninguna que perder).
- **decide**: «propietario» = decisión de negocio de Roberto (límites, qué operar, secretos); «auditor» = corrección
  técnica sin decisión de negocio.
- Prioridad P0–P3 y esfuerzo S/M/L como en `14_backlog_y_hoja_de_ruta.md`.

## Resumen

| ID | Tipo | Título | Prioridad | Esfuerzo | Decide |
|---|---|---|---|---|---|
| CP-E01 | ELIMINAR | momentum_4h fuera de la operativa | P0 | S | propietario |
| CP-E02 | ELIMINAR | Exploración amplia | P1 | S | propietario |
| CP-E03 | ELIMINAR | Exploración del cerebro en simulado | P1 | S | propietario |
| CP-E04 | ELIMINAR | Memoria por vecinos como filtro de decisión | P1 | S | auditor |
| CP-E05 | ELIMINAR | Relajación de filtros tras 24 h sin operar | P1 | S | auditor |
| CP-E06 | ELIMINAR | Piramidación (ampliar ganadoras) | P1 | S | propietario |
| CP-E07 | ELIMINAR | Ballenas como señal y como veto | P1 | S | propietario |
| CP-E08 | ELIMINAR | Seguimiento de ballenas en el bot de producción | P2 | S | propietario |
| CP-E09 | ELIMINAR | Estrategia de liquidaciones inferidas | P2 | S | auditor |
| CP-E10 | ELIMINAR | Estrategias negativas evaluadas en sombra | P2 | S | auditor |
| CP-E11 | ELIMINAR | Escéptico y revisor de IA | P2 | S | propietario |
| CP-E12 | ELIMINAR | Factor «objetivo diario conseguido» | P3 | S | propietario |
| CP-E13 | ELIMINAR | Borrado automático de datos_mercado/ | P1 | S | auditor |
| CP-E14 | ELIMINAR | Panel por túnel sin contraseña | P1 | S | propietario |
| CP-E15 | ELIMINAR | Cartera de funding hasta validarla | P2 | S | propietario |
| CP-E16 | ELIMINAR | Vistas decorativas del panel (opcional) | P3 | M | propietario |
| CP-M01 | MODIFICAR | El laboratorio gobierna lo que se opera | P0 | S | auditor |
| CP-M02 | MODIFICAR | Sombras simuladas con OHLC y costes realistas | P0 | M | auditor |
| CP-M03 | MODIFICAR | Stops del simulador con la misma regla que los objetivos | P1 | M | auditor |
| CP-M04 | MODIFICAR | Trailing igual en laboratorio y en vivo | P1 | M | auditor |
| CP-M05 | MODIFICAR | Deslizamiento del stop medido solo con fills del stop | P2 | S | auditor |
| CP-M06 | MODIFICAR | Prompt del escéptico: significado de funding_contra | P2 | S | auditor |
| CP-M07 | MODIFICAR | Riesgo por operación en simulado | P2 | S | propietario |
| CP-M08 | MODIFICAR | Límites del piloto real | P1 | S | propietario |
| CP-M09 | MODIFICAR | Techos duros del real más bajos | P1 | S | propietario |
| CP-M10 | MODIFICAR | Suelo de emergencia | P1 | S | propietario |
| CP-M11 | MODIFICAR | Exposición neta y beta | P2 | S | propietario |
| CP-M12 | MODIFICAR | Descarga de velas fuera del hilo de gestión | P2 | M | auditor |
| CP-M13 | MODIFICAR | Margen en el simulador y libre actualizado por apertura | P2 | S | auditor |
| CP-M14 | MODIFICAR | Una sola definición de funding_contra | P3 | S | auditor |
| CP-M15 | MODIFICAR | Funding de las horas perdidas en simulado | P3 | S | auditor |
| CP-M16 | MODIFICAR | Una sola fuente del modelo de simulación | P3 | S | auditor |
| CP-M17 | MODIFICAR | Curva de valor completa | P3 | S | auditor |
| CP-M18 | MODIFICAR | Instalador del VPS con el entorno bloqueado | P3 | S | auditor |
| CP-M19 | MODIFICAR | Pruebas herméticas | P3 | S | auditor |
| CP-M20 | MODIFICAR | Familias de investigación más finas | P2 | S | auditor |
| CP-M21 | MODIFICAR | Requisitos de apta_revision más informativos | P2 | S | auditor |
| CP-M22 | MODIFICAR | Objetivos del laboratorio por cruce estricto | P3 | S | auditor |
| CP-M23 | MODIFICAR | Registrar los fallos silenciosos de datos externos | P3 | S | auditor |
| CP-M24 | MODIFICAR | Higiene de codificación | P3 | S | auditor |
| CP-A01 | AÑADIR | Referencia de mercado obligatoria | P0 | M | auditor |
| CP-A02 | AÑADIR | Muestra efectiva por fechas independientes | P1 | S | auditor |
| CP-A03 | AÑADIR | Deflated Sharpe Ratio y PBO | P2 | M | auditor |
| CP-A04 | AÑADIR | Referencia «BTC > EMA200» en el laboratorio | P1 | S | auditor |
| CP-A05 | AÑADIR | Hipótesis prerregistrada: ruptura_4h solo a favor del régimen | P1 | S | propietario |
| CP-A06 | AÑADIR | Estudio de carry con funding de Hyperliquid | P1 | M | auditor |
| CP-A07 | AÑADIR | Parada por desviación del laboratorio | P2 | S | auditor |
| CP-A08 | AÑADIR | Salida por funding extremo durante la operación | P2 | S | auditor |
| CP-A09 | AÑADIR | Vigilancia del límite por dirección | P2 | S | auditor |
| CP-A10 | AÑADIR | Campaña en testnet de Hyperliquid | P1 (P0 antes de real) | M | propietario |
| CP-A11 | AÑADIR | Alertas externas probadas | P1 | S | propietario |
| CP-A12 | AÑADIR | VPS y copias de seguridad | P1 | M | propietario |
| CP-A13 | AÑADIR | Datos del laboratorio versionados | P2 | M | auditor |
| CP-A14 | AÑADIR | Conciliación PnL de fills frente al valor de la cuenta (real) | P2 | S | auditor |
| CP-A15 | AÑADIR | Sentido de los fills de ballenas (si se retoma el estudio) | P3 | M | auditor |
| CP-A16 | AÑADIR | Contraseña del panel y Cloudflare Access | P1 | S | propietario |
| CP-V01 | VALIDAR | fuerza_4h: prerregistro y versión de cartera neutral | P2 | M | propietario |
| CP-V02 | VALIDAR | Cartera de funding tal como se opera | P2 | M | auditor |
| CP-V03 | VALIDAR | Cerebro con historia solo de Hyperliquid y por régimen | P2 | M | auditor |
| CP-V04 | VALIDAR | Salidas: TP1 + trailing frente a solo tiempo + stop | P2 | S | auditor |
| CP-V05 | VALIDAR | Ablación regla a regla en el laboratorio | P2 | M | auditor |

## 1. Eliminar

### CP-E01 · momentum_4h fuera de la operativa

- **Dónde:** config.json → estrategias (añadir momentum_4h)
- **Ahora:** Activa por defecto (configuracion.estrategia_activa: no figura en config → activa).
- **Propuesta:** Añadir "momentum_4h": {"activa": false}. Sigue en el laboratorio como evidencia; no opera.
- **Evidencia:** S-01, B-01, Q-08 · 04, 09: lab OOS −0,107 R (t −3,35, n 1 155); independiente negativa 2023–2026; los 63 casos positivos recientes son cortos de 4 fechas de rebalanceo.
- **Riesgo del cambio:** Se pierden ganancias si la caída continúa (beta, no ventaja).
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P0 · **Esfuerzo:** S
- **Aceptación:** python bot.py --validar-config muestra momentum_4h inactiva; ninguna candidata de momentum_4h aprobada en el ledger tras el cambio.
- **Depende de:** —

### CP-E02 · Exploración amplia

- **Dónde:** config.json → exploracion_amplia; bot.py:898-904, 1312-1325
- **Ahora:** activa, 0,5 % de riesgo, hasta 4 abiertas; opera lo que el cerebro rechaza, también lo negativo.
- **Propuesta:** "exploracion_amplia": {"activa": false}. A medio plazo, borrar la vía del código o moverla a una cuenta simulada separada con ledger propio.
- **Evidencia:** 05 (#10), 12 · mezcla evidencia; las estrategias de 1 h perdieron 10/10.
- **Riesgo del cambio:** Menos operaciones simuladas (es lo deseado).
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Ninguna decisión con plan.exploracion_amplia = true tras el cambio.
- **Depende de:** —

### CP-E03 · Exploración del cerebro en simulado

- **Dónde:** config.json → "cerebro": {"exploracion_simulado": []} (defecto en configuracion.py:143 = ["4h"])
- **Ahora:** El cerebro de 4 h decide en simulado aunque su modelo sea no_supera (16 de 30 operaciones).
- **Propuesta:** Añadir "cerebro": {"exploracion_simulado": []}. Con un modelo no_supera, el cerebro se abstiene.
- **Evidencia:** C-01 · 07: t 2,75 < 2,91; solo Hyperliquid sin mejora; cartera −1,65 %.
- **Riesgo del cambio:** Con E02+E03 el bot no abrirá nada hasta que algo supere. Es el comportamiento correcto.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** cerebro_vivo devuelve abstención con estado no_supera en simulado.
- **Depende de:** —

### CP-E04 · Memoria por vecinos como filtro de decisión

- **Dónde:** bot.py:905-928; aprendizaje.py:215-256; config aprendizaje.activo / explorar_en_simulado
- **Ahora:** Multiplica el tamaño (0,5–1) o veta; hiperparámetros a mano; nunca validada.
- **Propuesta:** Quitar su efecto en la decisión (factor 1, sin veto). Puede seguir midiendo (medir=True) o borrarse.
- **Evidencia:** A-01 · vía memoria 7/7 perdedoras (−0,82 R).
- **Riesgo del cambio:** Ninguno conocido.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Prueba: con memoria en contra, el tamaño y la aprobación no cambian.
- **Depende de:** —

### CP-E05 · Relajación de filtros tras 24 h sin operar

- **Dónde:** bot.py:817; aprendizaje.py:249; estrategia.py:115-117; config gestion_capital.horas_sin_operar_para_relajar
- **Ahora:** Tras 24 h sin operar acepta R esperado ≥ −0,1 (con tamaño ×0,5).
- **Propuesta:** Borrar el parámetro relajado y r_minimo_relajado. No operar es válido.
- **Evidencia:** T-04 · antipatrón sin base estadística.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Prueba: 48 h sin operar y R esperado −0,05 → rechazo.
- **Depende de:** —

### CP-E06 · Piramidación (ampliar ganadoras)

- **Dónde:** config.json → "piramide": {"activa": false}; bot.py:1245-1310; gestor.py:1260-1349
- **Ahora:** Activa en simulado; tras el TP1 vuelve a comprar el 50 % recién vendido.
- **Propuesta:** "piramide": {"activa": false} (el defecto del código ya es false). Borrar el código o rediseñarlo (no permitirlo si hubo parcial; exigir +1 R adicional).
- **Evidencia:** Q-05 · SKY op-20261123130132-ccb50a: +0,29 R → −0,38 R; 4 ampliaciones = +0,02 $ en total.
- **Riesgo del cambio:** Ninguno conocido.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Ninguna orden con rol ampliacion tras el cambio.
- **Depende de:** —

### CP-E07 · Ballenas como señal y como veto

- **Dónde:** config.json → ballenas.modo_senal = "investigacion", ballenas.usar_como_veto = false, estrategias.ballenas_1h.activa = false; bot.py:679-682; motor.py:451-491
- **Ahora:** Señal operable en simulado y veto de 150 k$.
- **Propuesta:** Desactivar señal y veto. Conservar solo la grabación de datos de mercado.
- **Evidencia:** W-01, W-02 · 06: lab +0,01 R (n 128, ballenas elegidas dentro de muestra), −0,034 R con todas (n 852); sombras OHLC −0,05 R.
- **Riesgo del cambio:** Ninguno conocido.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Ninguna candidata ballenas_1h aprobada; ningún descarte por «veto de ballenas».
- **Depende de:** —

### CP-E08 · Seguimiento de ballenas en el bot de producción

- **Dónde:** bot.py:400-499 (selección, lectura de 15 cuentas por ciclo), 502-599 (websocket userFills); seleccion.py
- **Ahora:** Hilo de selección, 15 lecturas de cuenta por ciclo, suscripciones de usuario.
- **Propuesta:** ballenas.activo = false en producción; si se quiere estudiar, un proceso aparte que solo grabe (usando el campo dir de los fills: abrir/cerrar).
- **Evidencia:** 06 · sin señal; consume peticiones y complejidad.
- **Riesgo del cambio:** Se pierde la vista del panel.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Ciclo sin llamadas user_state a cuentas ajenas.
- **Depende de:** CP-E07

### CP-E09 · Estrategia de liquidaciones inferidas

- **Dónde:** config.json → mercado.liquidaciones.activo = false; mercado.py:senales_liquidaciones
- **Ahora:** Solo investigación; genera sombras.
- **Propuesta:** Desactivar.
- **Evidencia:** 04 · lab −0,012 R (n 82); sombras OHLC −0,07 R (n 134).
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (config) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Ninguna candidata liquidaciones_1h.
- **Depende de:** —

### CP-E10 · Estrategias negativas evaluadas en sombra

- **Dónde:** motor.py:352-354, 420 (las apagadas se evalúan como solo_investigacion)
- **Ahora:** retroceso, reversión, funding y todas las de 1 h siguen generando sombras.
- **Propuesta:** No evaluar las apagadas en vivo (su evidencia está en el laboratorio); dejarlas en el cementerio.
- **Evidencia:** 04, 05 · OHLC: apagadas −0,07 R (n 344).
- **Riesgo del cambio:** Menos datos de sombra (sesgados).
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Ninguna señal con apagada = true en el ledger.
- **Depende de:** —

### CP-E11 · Escéptico y revisor de IA

- **Dónde:** analista_ia.py:98-106 (escéptico), 461-553 (revisor/escéptico)
- **Ahora:** Escéptico vota en contra 6/6; prompt con funding_contra invertido.
- **Propuesta:** Desactivarlos. Si se conserva el escéptico, aplicar CP-M06.
- **Evidencia:** IA-01, IA-02 · 07.
- **Riesgo del cambio:** Ninguno (no deciden).
- **Huella:** no (sin efecto) · **Decide:** propietario · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Sin nuevas filas en esceptico.jsonl.
- **Depende de:** —

### CP-E12 · Factor «objetivo diario conseguido»

- **Dónde:** config.json → gestion_capital.objetivo_diario_pct = 0; estrategia.py:109-110
- **Ahora:** Tras +3 % en el día el tamaño se reduce a la mitad.
- **Propuesta:** objetivo_diario_pct: 0 (la condición se desactiva con 0).
- **Evidencia:** 05 (#29) · sin base estadística.
- **Riesgo del cambio:** Ninguno conocido.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** factor_capital no reduce tras +3 %.
- **Depende de:** —

### CP-E13 · Borrado automático de datos_mercado/

- **Dónde:** mercado.py:106-117 (_limpiar), config mercado.dias_guardar 120
- **Ahora:** Borra OI, flujo y operaciones grandes de más de 120 días.
- **Propuesta:** Eliminar la limpieza (o comprimir/archivar en vez de borrar). Hyperliquid no ofrece esta historia.
- **Evidencia:** W-03 · contradice CLAUDE.md («no borres datos_mercado»).
- **Riesgo del cambio:** Disco (~200 MB/mes).
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Ningún os.remove sobre datos_mercado/.
- **Depende de:** —

### CP-E14 · Panel por túnel sin contraseña

- **Dónde:** config.json → panel.tunel_sin_clave; panel.py:1352
- **Ahora:** true: lectura pública de saldo, posiciones y estrategias por el túnel.
- **Propuesta:** Poner PANEL_PASSWORD (lo hace el propietario), quitar la opción de config y del código.
- **Evidencia:** SEG-01 · 10.
- **Riesgo del cambio:** Ninguno.
- **Huella:** no (CONFIG_SIN_EFECTO) · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Petición con cabecera Cf-Connecting-Ip y sin credenciales → 401/403.
- **Depende de:** CP-A16

### CP-E15 · Cartera de funding hasta validarla

- **Dónde:** config.json → "cartera_funding": {"activa": false}
- **Ahora:** Activa en simulado sin pasar por el laboratorio; el propio módulo dice que no es lo medido.
- **Propuesta:** Desactivar hasta CP-V02.
- **Evidencia:** S-04 · 04.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Ninguna decisión con cartera_funding = true.
- **Depende de:** —

### CP-E16 · Vistas decorativas del panel (opcional)

- **Dónde:** panel_web/assets/js/nucleo.js, ceto.js, vistas/mesa.js, sombras.js, macro.js; taller.py, mesa.py
- **Ahora:** ~8 600 líneas de frontend; no afectan al trading.
- **Propuesta:** Opcional: separarlas del bot o congelarlas. No es prioritario.
- **Evidencia:** 02, 13 · complejidad sin valor de trading.
- **Riesgo del cambio:** Preferencia del propietario.
- **Huella:** no · **Decide:** propietario · **Prioridad:** P3 · **Esfuerzo:** M
- **Aceptación:** —
- **Depende de:** —


## 2. Modificar

### CP-M01 · El laboratorio gobierna lo que se opera

- **Dónde:** motor.py:_cargar_estrategias (91-136); bot.py:procesar_candidatas; nueva prueba
- **Ahora:** Se operan estrategias con t fuera de muestra negativo y vías que el lab rechaza.
- **Propuesta:** Regla dura: una estrategia con veredicto de laboratorio no_supera y R medio OOS < 0 no puede generar candidatas operables (ni en simulado), salvo en una cuenta de investigación separada.
- **Evidencia:** 12 · la mayor parte de las pérdidas evitables.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P0 · **Esfuerzo:** S
- **Aceptación:** Prueba que falla si una estrategia activa tiene r_medio OOS < 0 en estrategia_elegida.json.
- **Depende de:** —

### CP-M02 · Sombras simuladas con OHLC y costes realistas

- **Dónde:** aprendizaje.py:160-209 (abrir_sombra, actualizar_sombras)
- **Ahora:** Un precio cada ~15 s (alto = bajo = cierre), entrada al mid con comisión maker, stop lleno exacto.
- **Propuesta:** Avanzar con velas de 1 min (candleSnapshot) o de 1 h archivadas, política «peor», entrada al ask/bid + comisión tomadora, deslizamiento en stops.
- **Evidencia:** Q-07 · sesgo +0,123 R/op (t 7,7); +0,074 R solo por muestreo.
- **Riesgo del cambio:** Más peticiones (velas de 1 min).
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P0 · **Esfuerzo:** M
- **Aceptación:** Re-simular las 651 sombras con el nuevo método: diferencia con experimentos/sesgo_sombras.py < 0,02 R.
- **Depende de:** —

### CP-M03 · Stops del simulador con la misma regla que los objetivos

- **Dónde:** papel.py:400-428 frente a 283-318
- **Ahora:** Objetivos ven mechas de velas de 1 min; stops solo la marca en el instante de procesar().
- **Propuesta:** Disparo del stop si el extremo de las velas de 1 min desde la última comprobación cruzó el trigger (aproximación conservadora; mejor con marca si se archiva); fill al trigger + deslizamiento.
- **Evidencia:** T-01.
- **Riesgo del cambio:** Resultados simulados algo peores (más realistas).
- **Huella:** sí (código; subir MODELO) · **Decide:** auditor · **Prioridad:** P1 · **Esfuerzo:** M
- **Aceptación:** Fixture: mecha que cruza el stop y vuelve → cierra; mecha que cruza el objetivo → mismo trato.
- **Depende de:** CP-M16

### CP-M04 · Trailing igual en laboratorio y en vivo

- **Dónde:** gestor.py:1215-1226; estrategia.py:243-251
- **Ahora:** Lab: por vela de 4 h, aplicado desde la siguiente. Vivo: cada ~15 s con el mid.
- **Propuesta:** En vivo, recalcular el stop dinámico solo al cierre de la vela del intervalo de la estrategia (o simular sub-velas en el lab).
- **Evidencia:** T-05.
- **Riesgo del cambio:** Stops algo más lejos.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P1 · **Esfuerzo:** M
- **Aceptación:** Misma serie de precios en SimSalida y en Gestor (Info falso) → mismo stop final.
- **Depende de:** —

### CP-M05 · Deslizamiento del stop medido solo con fills del stop

- **Dónde:** gestor.py:1506-1510; riesgo.py:237-246
- **Ahora:** peor_que_trigger_pct usa el precio medio de TODAS las salidas.
- **Propuesta:** Calcularlo con los fills de rol stop.
- **Evidencia:** Q-06 · SKY: 0,0 % registrado, −2,0 % real.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Operación con TP1 + stop peor → peor_que_trigger_pct > 0.
- **Depende de:** —

### CP-M06 · Prompt del escéptico: significado de funding_contra

- **Dónde:** analista_ia.py:102
- **Ahora:** «funding_contra > 0 = el funding juega a favor del lado».
- **Propuesta:** «funding_contra > 0 = el funding juega EN CONTRA del lado (lo paga)».
- **Evidencia:** IA-01 · esceptico.jsonl (VVV, SKY).
- **Riesgo del cambio:** Ninguno.
- **Huella:** no · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Prueba de texto del prompt.
- **Depende de:** —

### CP-M07 · Riesgo por operación en simulado

- **Dónde:** config.json → riesgo.riesgo_por_operacion_pct 3 → 1; riesgo_abierto_max_pct 9 → 3
- **Ahora:** 3 % / 9 % (decisión del propietario del 04/11 y 19/11).
- **Propuesta:** 1 % / 3 %, para que el paper represente lo que se operaría en un primer real prudente.
- **Evidencia:** 05 (#21), 10 · sin ventaja, 10 pérdidas seguidas ≈ −26 %.
- **Riesgo del cambio:** Ninguno técnico; es decisión del propietario.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** --validar-config muestra 1 / 3.
- **Depende de:** —

### CP-M08 · Límites del piloto real

- **Dónde:** config.json → piloto_real
- **Ahora:** 3 % / 9 % / 6 posiciones / 5× / perdida_max_usd 116 (50 %) / mercados *.
- **Propuesta:** 1 % / 3 % / 3 posiciones / 2× / perdida_max_usd 46 (20 % de 232) / mercados [BTC, ETH, SOL].
- **Evidencia:** 10 · sin ventaja demostrada y sin pruebas en real.
- **Riesgo del cambio:** Ninguno; /aplicarconfig lo rechaza: exige arranque manual.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** limites_efectivos en modo real = propuesta.
- **Depende de:** —

### CP-M09 · Techos duros del real más bajos

- **Dónde:** riesgo.py:532-533 (TECHOS_REAL)
- **Ahora:** 3 % / 9 % / 5× / −10 % día / 6 posiciones.
- **Propuesta:** 1 % / 3 % / 2× / −3 % día / 3 posiciones (subir exige cambiar código y nueva aprobación).
- **Evidencia:** 10.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** tests/test_tramos_techos.py actualizado.
- **Depende de:** —

### CP-M10 · Suelo de emergencia

- **Dónde:** config.json → riesgo.perdida_max_total_pct 50 → 20 (al menos en real)
- **Ahora:** −50 % del capital inicial.
- **Propuesta:** −20 %.
- **Evidencia:** 05 (#34), 10.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** --validar-config.
- **Depende de:** —

### CP-M11 · Exposición neta y beta

- **Dónde:** config.json → riesgo.exposicion_neta_max_pct 150 → 100; exposicion_beta_btc_max_pct 200 → 100
- **Ahora:** Límites tan laxos que casi nunca actúan.
- **Propuesta:** 100 % y 100 %.
- **Evidencia:** 05 (#23), 02 §5.3 · concentración direccional en la caída.
- **Riesgo del cambio:** Menos cortos simultáneos.
- **Huella:** sí (config) · **Decide:** propietario · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** --validar-config.
- **Depende de:** —

### CP-M12 · Descarga de velas fuera del hilo de gestión

- **Dónde:** motor.py:377 (time.sleep(1.0) por moneda)
- **Ahora:** 45–90 s sin gestionar posiciones ni procesar la cuenta simulada en cada cierre de vela.
- **Propuesta:** Hilo de descarga con el limitador compartido; el bucle de gestión nunca duerme > 15 s.
- **Evidencia:** T-02.
- **Riesgo del cambio:** Concurrencia: proteger motor.contextos con un bloqueo.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** M
- **Aceptación:** Con 45 monedas y un Info falso lento, gestionar() se llama cada ≤ 15 s.
- **Depende de:** —

### CP-M13 · Margen en el simulador y libre actualizado por apertura

- **Dónde:** papel.py:520-582 (order); bot.py:1002-1058 (bucle de aprobadas)
- **Ahora:** La cuenta simulada nunca rechaza por margen; libre fijo durante el ciclo.
- **Propuesta:** Rechazo por margen como Hyperliquid; releer la cuenta tras cada apertura.
- **Evidencia:** T-03.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Dos candidatas que juntas superan el margen → la segunda se rechaza.
- **Depende de:** —

### CP-M14 · Una sola definición de funding_contra

- **Dónde:** laboratorio.py:200 (media 8 h) y motor.py:309 (tasa instantánea)
- **Ahora:** Mismo nombre, dos definiciones.
- **Propuesta:** Función compartida (como mercado_unificado.rasgos).
- **Evidencia:** T-07.
- **Riesgo del cambio:** Cambia el filtro de entrada.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** Prueba de igualdad lab/vivo.
- **Depende de:** —

### CP-M15 · Funding de las horas perdidas en simulado

- **Dónde:** papel.py:245-268
- **Ahora:** Solo una hora al volver de un parón.
- **Propuesta:** Iterar por cada hora perdida con fundingHistory.
- **Evidencia:** T-08.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** Prueba con hueco de 3 h.
- **Depende de:** —

### CP-M16 · Una sola fuente del modelo de simulación

- **Dónde:** promocion.py:196 (MODELO_SIMULACION = 2) y papel.py:41 (MODELO = 3)
- **Ahora:** Etiqueta de evidencia desactualizada.
- **Propuesta:** MODELO_SIMULACION = papel.MODELO + prueba.
- **Evidencia:** T-11.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** Prueba de igualdad.
- **Depende de:** —

### CP-M17 · Curva de valor completa

- **Dónde:** bot.py:1762-1765 (del hist[:-3000])
- **Ahora:** Solo ~10 días.
- **Propuesta:** Guardar un punto diario en un JSONL aparte, sin truncar.
- **Evidencia:** T-13.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** Curva diaria desde la puesta a cero.
- **Depende de:** —

### CP-M18 · Instalador del VPS con el entorno bloqueado

- **Dónde:** despliegue/instalar_vps.sh:137
- **Ahora:** pip install -r requirements.txt.
- **Propuesta:** pip install -r requirements-bloqueado.txt.
- **Evidencia:** OPS-01.
- **Riesgo del cambio:** Ninguno.
- **Huella:** no · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** pip freeze = bloqueado.
- **Depende de:** —

### CP-M19 · Pruebas herméticas

- **Dónde:** tests/test_panel_web.py, test_feed.py, test_config_panel.py, test_panel_proxy.py, test_bot.py (LatidoExterno)
- **Ahora:** Intentan red real a api.hyperliquid.xyz.
- **Propuesta:** Info falso inyectado; fallar si se abre un socket.
- **Evidencia:** T-09.
- **Riesgo del cambio:** Ninguno.
- **Huella:** no · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** Batería en verde sin red y sin intentos de conexión.
- **Depende de:** —

### CP-M20 · Familias de investigación más finas

- **Dónde:** validacion.py:665-671 (familia_idea)
- **Ahora:** Disparador × intervalo.
- **Propuesta:** Incluir filtro y tipo de salida, o estimar el número efectivo por correlación de resultados.
- **Evidencia:** 09 §1.
- **Riesgo del cambio:** Listón más exigente para investigación.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Prueba con ideas que difieren solo en filtro.
- **Depende de:** —

### CP-M21 · Requisitos de apta_revision más informativos

- **Dónde:** promocion.py:369-408
- **Ahora:** 30 operaciones con R medio > 0 y PnL > 0.
- **Propuesta:** Añadir: R medio paper dentro del IC del laboratorio, exceso de mercado ≥ 0 y n efectivo por fechas.
- **Evidencia:** T-12.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Pruebas de promoción actualizadas.
- **Depende de:** CP-A01, CP-A02

### CP-M22 · Objetivos del laboratorio por cruce estricto

- **Dónde:** estrategia.py:220-232
- **Ahora:** Lleno al tocar.
- **Propuesta:** Cruce estricto (o un tick más).
- **Evidencia:** T-06.
- **Riesgo del cambio:** Resultados del lab algo peores.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** Prueba de toque exacto.
- **Depende de:** —

### CP-M23 · Registrar los fallos silenciosos de datos externos

- **Dónde:** contexto_externo.py:48, 69, 100 (except: pass)
- **Ahora:** Un fallo de funding externo no deja rastro y el cerebro se abstiene sin causa visible.
- **Propuesta:** Registrar el error (nivel aviso) y marcar la fuente.
- **Evidencia:** 03 (análisis estático).
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** Fallo simulado → línea en el log y fuente marcada.
- **Depende de:** —

### CP-M24 · Higiene de codificación

- **Dónde:** carry/motor.py, carry/terreno.py (BOM, CRLF); CLAUDE.md (restos «`n»)
- **Ahora:** BOM y finales de línea mezclados.
- **Propuesta:** .editorconfig y prueba de codificación.
- **Evidencia:** T-10.
- **Riesgo del cambio:** Ninguno.
- **Huella:** no · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** S
- **Aceptación:** Prueba que rechaza BOM y CRLF en .py.
- **Depende de:** —


## 3. Añadir

### CP-A01 · Referencia de mercado obligatoria

- **Dónde:** validacion.py (nuevo), veredicto.py, informes; experimentos/forense_ledger.py como prototipo
- **Ahora:** Solo veredicto.contra_mercado (todo corto / todo largo) en el paper.
- **Propuesta:** Para cada operación (lab y paper): exceso frente al universo equiponderado en el mismo lado y ventana, y frente a BTC > EMA200; IC bootstrap; una evidencia sin exceso significativo no cuenta.
- **Evidencia:** Q-02 · exceso +0,40 % (t 0,53).
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P0 · **Esfuerzo:** M
- **Aceptación:** El informe del laboratorio muestra el exceso con IC.
- **Depende de:** —

### CP-A02 · Muestra efectiva por fechas independientes

- **Dónde:** validacion.py; promocion.py; preregistro.py
- **Ahora:** Se cuentan operaciones aunque salgan del mismo rebalanceo.
- **Propuesta:** n efectivo = fechas distintas (rebalanceo o día); exigir ≥ 30 para cualquier juicio.
- **Evidencia:** Q-08 · momentum: 63 casos de 4 fechas.
- **Riesgo del cambio:** Juicios más lentos.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Prueba con 60 ops de 4 fechas → n efectivo 4.
- **Depende de:** —

### CP-A03 · Deflated Sharpe Ratio y PBO

- **Dónde:** validacion.py; laboratorio.py (veredicto)
- **Ahora:** Bonferroni por familias.
- **Propuesta:** DSR con el número real de pruebas y PBO por CSCV; exigir DSR ≥ 0,95 para «supera».
- **Evidencia:** 11 (Bailey y López de Prado).
- **Riesgo del cambio:** Listón más exigente.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** M
- **Aceptación:** Pruebas con series sintéticas conocidas.
- **Depende de:** —

### CP-A04 · Referencia «BTC > EMA200» en el laboratorio

- **Dónde:** laboratorio.py (línea base)
- **Ahora:** Líneas base: azar y siempre largo.
- **Propuesta:** Añadir la regla de tendencia de BTC (largo/fuera) como línea base de cartera.
- **Evidencia:** B-04 · Sharpe 0,75 frente a 0,12–0,36.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Aparece en estrategia_elegida.json.
- **Depende de:** —

### CP-A05 · Hipótesis prerregistrada: ruptura_4h solo a favor del régimen

- **Dónde:** preregistro.py
- **Ahora:** Solo fuerza_4h y carry_realista.
- **Propuesta:** Definición fija (parámetros del 22/11, régimen EMA200 de BTC en 4 h), muestra fijada, juicio único.
- **Evidencia:** B-02 · +0,051 R, t 2,22 (no pasa el listón).
- **Riesgo del cambio:** Sube a 3 hipótesis (listón).
- **Huella:** no (preregistro sin efecto) · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Hipótesis escrita antes de mirar nuevos datos.
- **Depende de:** —

### CP-A06 · Estudio de carry con funding de Hyperliquid

- **Dónde:** estudios_ext/ o carry/ (estudio aparte)
- **Ahora:** Estudio con funding de Binance.
- **Propuesta:** fundingHistory de Hyperliquid 2023–2026, 4 patas de costes, holdout.
- **Evidencia:** 04, 11 (BIS WP 1087).
- **Riesgo del cambio:** Ninguno.
- **Huella:** no · **Decide:** auditor · **Prioridad:** P1 · **Esfuerzo:** M
- **Aceptación:** Informe con R anual neto e IC.
- **Depende de:** —

### CP-A07 · Parada por desviación del laboratorio

- **Dónde:** vigilancia.py:49-117
- **Ahora:** Solo reduce el tamaño ×0,5.
- **Propuesta:** Si el R medio de las últimas 30 operaciones queda bajo el límite inferior del IC del lab: pausa.
- **Evidencia:** 05 §6.
- **Riesgo del cambio:** Pausas por mala racha normal (calibrar).
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Prueba con serie degradada → pausa.
- **Depende de:** —

### CP-A08 · Salida por funding extremo durante la operación

- **Dónde:** gestor.py:gestionar (1204-1226)
- **Ahora:** Solo se mira el funding al entrar.
- **Propuesta:** Cerrar si el funding en contra supera un umbral (p. ej. 0,05 %/h) durante N horas.
- **Evidencia:** 10, 11 (tope de 4 %/h en Hyperliquid).
- **Riesgo del cambio:** Salidas adicionales.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Prueba con funding sintético.
- **Depende de:** —

### CP-A09 · Vigilancia del límite por dirección

- **Dónde:** ejecucion.py / bot.py (solo real)
- **Ahora:** No se consulta userRateLimit.
- **Propuesta:** Leer userRateLimit cada hora en real; bloquear entradas si el margen es bajo.
- **Evidencia:** 06, 11.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Prueba con respuesta falsa al límite.
- **Depende de:** —

### CP-A10 · Campaña en testnet de Hyperliquid

- **Dónde:** red: testnet (bot.py:2181); checklist nuevo en despliegue/
- **Ahora:** Código de órdenes nunca probado contra la API real.
- **Propuesta:** Ejecutar en testnet: ALO + IOC de reserva, stop, TP, sustitución de stop, cancelación ambigua, reinicio con posiciones, conciliación y cierre de emergencia.
- **Evidencia:** 06, 10.
- **Riesgo del cambio:** Ninguno (testnet).
- **Huella:** no · **Decide:** propietario · **Prioridad:** P1 (P0 antes de real) · **Esfuerzo:** M
- **Aceptación:** Checklist de 10 escenarios superada.
- **Depende de:** CP-A11

### CP-A11 · Alertas externas probadas

- **Dónde:** .env (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, HEALTHCHECK_URL: los pone el propietario)
- **Ahora:** Sin configurar.
- **Propuesta:** Configurar y hacer un simulacro de caída.
- **Evidencia:** 10.
- **Riesgo del cambio:** Ninguno.
- **Huella:** no · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** Aviso en < 10 min tras matar el proceso.
- **Depende de:** —

### CP-A12 · VPS y copias de seguridad

- **Dónde:** despliegue/GUIA_HETZNER.md, copia_seguridad.sh
- **Ahora:** PC doméstico, sin copias.
- **Propuesta:** Migrar al VPS, copias cifradas diarias del ledger y del estado.
- **Evidencia:** 10.
- **Riesgo del cambio:** Migración (seguir la guía; pruebas en Linux).
- **Huella:** no · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** M
- **Aceptación:** Restauración probada desde copia.
- **Depende de:** CP-M18

### CP-A13 · Datos del laboratorio versionados

- **Dónde:** laboratorio.py (hash_datos ya existe); almacenamiento externo
- **Ahora:** datos_backtest/ fuera del repositorio; no reproducible.
- **Propuesta:** Archivar los datos exactos de cada ejecución con su hash (R2/S3).
- **Evidencia:** OPS-03.
- **Riesgo del cambio:** Coste de almacenamiento.
- **Huella:** no · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** M
- **Aceptación:** Re-ejecución con el mismo hash reproduce el resultado.
- **Depende de:** —

### CP-A14 · Conciliación PnL de fills frente al valor de la cuenta (real)

- **Dónde:** bot.py / gestor.py
- **Ahora:** No existe.
- **Propuesta:** Si la suma de PnL atribuido difiere del cambio de accountValue (sin depósitos) más de X en 24 h: pausa.
- **Evidencia:** 05 §6.
- **Riesgo del cambio:** Falsos positivos por funding no atribuido (calibrar).
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Prueba con diferencia sintética.
- **Depende de:** —

### CP-A15 · Sentido de los fills de ballenas (si se retoma el estudio)

- **Dónde:** ballenas.py; bot.py:502-533
- **Ahora:** Flujo por diferencia de fotos; dir solo para el panel.
- **Propuesta:** Usar dir (Open/Close Long/Short) para separar aperturas de cierres.
- **Evidencia:** W-02.
- **Riesgo del cambio:** Ninguno.
- **Huella:** sí (código) · **Decide:** auditor · **Prioridad:** P3 · **Esfuerzo:** M
- **Aceptación:** Cubrir un corto no genera señal larga.
- **Depende de:** —

### CP-A16 · Contraseña del panel y Cloudflare Access

- **Dónde:** .env PANEL_PASSWORD (propietario); configuración de Cloudflare
- **Ahora:** Sin contraseña.
- **Propuesta:** PANEL_PASSWORD + política de Access.
- **Evidencia:** SEG-01.
- **Riesgo del cambio:** Ninguno.
- **Huella:** no · **Decide:** propietario · **Prioridad:** P1 · **Esfuerzo:** S
- **Aceptación:** 401 sin credenciales.
- **Depende de:** —


## 4. Validar antes de decidir

### CP-V01 · fuerza_4h: prerregistro y versión de cartera neutral

- **Dónde:** preregistro.py; senales.py:193-210
- **Ahora:** Prerregistro en curso (1/30).
- **Propuesta:** Mantener el prerregistro; estudiar además largo top / corto bottom semanal neutral.
- **Evidencia:** 04 · lab +0,088 (t 0,59); independiente +0,062 (t 0,68).
- **Riesgo del cambio:** —
- **Huella:** — · **Decide:** propietario · **Prioridad:** P2 · **Esfuerzo:** M
- **Aceptación:** Veredicto del prerregistro.
- **Depende de:** —

### CP-V02 · Cartera de funding tal como se opera

- **Dónde:** laboratorio.py; cartera_funding.py
- **Ahora:** No pasa por el laboratorio.
- **Propuesta:** Simularla en el lab con las mismas reglas (2 patas, stop, funding de HL).
- **Evidencia:** S-04.
- **Riesgo del cambio:** —
- **Huella:** — · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** M
- **Aceptación:** Veredicto del lab.
- **Depende de:** CP-E15

### CP-V03 · Cerebro con historia solo de Hyperliquid y por régimen

- **Dónde:** laboratorio.py:686-770 (evaluar_cerebro)
- **Ahora:** Mejora solo donde hay historia de Binance.
- **Propuesta:** Experimento dedicado (R-06 de la auditoría interna); si no supera, retirar el cerebro.
- **Evidencia:** C-01.
- **Riesgo del cambio:** —
- **Huella:** — · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** M
- **Aceptación:** Informe con ambas variantes y régimen.
- **Depende de:** —

### CP-V04 · Salidas: TP1 + trailing frente a solo tiempo + stop

- **Dónde:** laboratorio.py; senales.MODULOS[*].salida
- **Ahora:** Las ganancias salen por tiempo máximo.
- **Propuesta:** Comparar en el lab ambas gestiones con la misma entrada.
- **Evidencia:** Q-04, B-02 (objetivo final 4 %).
- **Riesgo del cambio:** Una variante más (listón).
- **Huella:** — · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** S
- **Aceptación:** Veredicto del lab.
- **Depende de:** —

### CP-V05 · Ablación regla a regla en el laboratorio

- **Dónde:** laboratorio.py
- **Ahora:** Solo ablación natural con sombras (05).
- **Propuesta:** Repetir la simulación quitando cada filtro de estrategia (régimen, funding, volatilidad, enfriamiento, persecución) con todo lo demás fijo.
- **Evidencia:** 05 §1.
- **Riesgo del cambio:** Gasta holdout si no se hace en copia.
- **Huella:** — · **Decide:** auditor · **Prioridad:** P2 · **Esfuerzo:** M
- **Aceptación:** Tabla de ablación con IC.
- **Depende de:** —

## Orden de aplicación recomendado

1. **Fase 0 (1 semana):** CP-M01, CP-E01, CP-E02, CP-E03, CP-E04, CP-E05, CP-E06, CP-E07, CP-E13, CP-E15, y nueva puesta a cero de la cuenta simulada.
2. **Fase 1 (2–3 semanas):** CP-M02, CP-A01, CP-A02, CP-M03, CP-M04, CP-M05, CP-A03, CP-A04, CP-M17.
3. **Fase 2 (1–3 meses):** CP-A05, CP-A06, CP-V01…CP-V05.
4. **Fase 3 (en paralelo):** CP-A16, CP-E14, CP-A11, CP-A12, CP-M18, CP-A10, CP-M08, CP-M09, CP-M10.
5. **Resto:** P2/P3 según capacidad.
