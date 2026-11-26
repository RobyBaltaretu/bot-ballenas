# Plan de desarrollo

Generado desde `experimentos/generar_plan_desarrollo.py` (no editar a mano). Parte de las propuestas de la auditoría
(`CAMBIOS_PROPUESTOS.md`) con la condición del propietario del 26/11/2026: **nada que impida o reduzca que el bot
opere**. Lo que lo haría está excluido al final, con su motivo; algunas propuestas se han transformado (aviso en
lugar de pausa, piramidación corregida en lugar de eliminada, límites solo para el modo real).

**48 tareas en 5 fases · 13 excluidas.**

## Fase 1: Corregir errores (no cambia la operativa)

| ID | Tarea | Prioridad | Esfuerzo | Acción de Roberto |
|---|---|---|---|---|
| CP-E06 | Piramidación: no recomprar lo recién cobrado en el TP1 | P1 | S | — |
| CP-M05 | Deslizamiento del stop medido solo con fills del stop | P2 | S | — |
| CP-M06 | Prompt del escéptico: significado de funding_contra | P2 | S | — |
| CP-M15 | Funding de las horas perdidas en simulado | P3 | S | — |
| CP-M16 | Una sola fuente del modelo de simulación | P3 | S | — |
| CP-M17 | Curva de valor completa | P3 | S | — |
| CP-M18 | Instalador del VPS con el entorno bloqueado | P3 | S | — |
| CP-M19 | Pruebas herméticas | P3 | S | — |
| CP-M23 | Registrar los fallos silenciosos de datos externos | P3 | S | — |
| CP-M24 | Higiene de codificación | P3 | S | — |
| CP-E13 | Borrado automático de datos_mercado/ | P1 | S | — |

### CP-E06 · Piramidación: no recomprar lo recién cobrado en el TP1

- **Dónde:** config.json → "piramide": {"activa": false}; bot.py:1245-1310; gestor.py:1260-1349
- **Ahora:** Activa en simulado; tras el TP1 vuelve a comprar el 50 % recién vendido.
- **Qué hacer:** Mantener la piramidación activa, pero que gestor.ampliable() devuelva motivo si la operación tenía objetivo parcial y ya lo cobró (tp1_hecho) hasta que el precio avance al menos 1 R más allá del TP1; y nunca en el mismo ciclo del cobro.
- **Por qué:** Q-05 · SKY op-20261123130132-ccb50a: +0,29 R → −0,38 R; 4 ampliaciones = +0,02 $ en total.
- **Riesgo:** Menos ampliaciones justo después del TP1 (las que deshacían la toma de beneficios). · **Huella:** sí (código)
- **Hecho cuando:** Prueba: TP1 cobrado y precio sin avanzar 1 R → no amplía; tras +1 R → amplía.
- **Depende de:** —

### CP-M05 · Deslizamiento del stop medido solo con fills del stop

- **Dónde:** gestor.py:1506-1510; riesgo.py:237-246
- **Ahora:** peor_que_trigger_pct usa el precio medio de TODAS las salidas.
- **Qué hacer:** Calcularlo con los fills de rol stop.
- **Por qué:** Q-06 · SKY: 0,0 % registrado, −2,0 % real.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Operación con TP1 + stop peor → peor_que_trigger_pct > 0.
- **Depende de:** —

### CP-M06 · Prompt del escéptico: significado de funding_contra

- **Dónde:** analista_ia.py:102
- **Ahora:** «funding_contra > 0 = el funding juega a favor del lado».
- **Qué hacer:** «funding_contra > 0 = el funding juega EN CONTRA del lado (lo paga)».
- **Por qué:** IA-01 · esceptico.jsonl (VVV, SKY).
- **Riesgo:** Ninguno. · **Huella:** no
- **Hecho cuando:** Prueba de texto del prompt.
- **Depende de:** —

### CP-M15 · Funding de las horas perdidas en simulado

- **Dónde:** papel.py:245-268
- **Ahora:** Solo una hora al volver de un parón.
- **Qué hacer:** Iterar por cada hora perdida con fundingHistory.
- **Por qué:** T-08.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Prueba con hueco de 3 h.
- **Depende de:** —

### CP-M16 · Una sola fuente del modelo de simulación

- **Dónde:** promocion.py:196 (MODELO_SIMULACION = 2) y papel.py:41 (MODELO = 3)
- **Ahora:** Etiqueta de evidencia desactualizada.
- **Qué hacer:** MODELO_SIMULACION = papel.MODELO + prueba.
- **Por qué:** T-11.
- **Riesgo:** Ninguno. · **Huella:** sí
- **Hecho cuando:** Prueba de igualdad.
- **Depende de:** —

### CP-M17 · Curva de valor completa

- **Dónde:** bot.py:1762-1765 (del hist[:-3000])
- **Ahora:** Solo ~10 días.
- **Qué hacer:** Guardar un punto diario en un JSONL aparte, sin truncar.
- **Por qué:** T-13.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Curva diaria desde la puesta a cero.
- **Depende de:** —

### CP-M18 · Instalador del VPS con el entorno bloqueado

- **Dónde:** despliegue/instalar_vps.sh:137
- **Ahora:** pip install -r requirements.txt.
- **Qué hacer:** pip install -r requirements-bloqueado.txt.
- **Por qué:** OPS-01.
- **Riesgo:** Ninguno. · **Huella:** no
- **Hecho cuando:** pip freeze = bloqueado.
- **Depende de:** —

### CP-M19 · Pruebas herméticas

- **Dónde:** tests/test_panel_web.py, test_feed.py, test_config_panel.py, test_panel_proxy.py, test_bot.py (LatidoExterno)
- **Ahora:** Intentan red real a api.hyperliquid.xyz.
- **Qué hacer:** Info falso inyectado; fallar si se abre un socket.
- **Por qué:** T-09.
- **Riesgo:** Ninguno. · **Huella:** no
- **Hecho cuando:** Batería en verde sin red y sin intentos de conexión.
- **Depende de:** —

### CP-M23 · Registrar los fallos silenciosos de datos externos

- **Dónde:** contexto_externo.py:48, 69, 100 (except: pass)
- **Ahora:** Un fallo de funding externo no deja rastro y el cerebro se abstiene sin causa visible.
- **Qué hacer:** Registrar el error (nivel aviso) y marcar la fuente.
- **Por qué:** 03 (análisis estático).
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Fallo simulado → línea en el log y fuente marcada.
- **Depende de:** —

### CP-M24 · Higiene de codificación

- **Dónde:** carry/motor.py, carry/terreno.py (BOM, CRLF); CLAUDE.md (restos «`n»)
- **Ahora:** BOM y finales de línea mezclados.
- **Qué hacer:** .editorconfig y prueba de codificación.
- **Por qué:** T-10.
- **Riesgo:** Ninguno. · **Huella:** no
- **Hecho cuando:** Prueba que rechaza BOM y CRLF en .py.
- **Depende de:** —

### CP-E13 · Borrado automático de datos_mercado/

- **Dónde:** mercado.py:106-117 (_limpiar), config mercado.dias_guardar 120
- **Ahora:** Borra OI, flujo y operaciones grandes de más de 120 días.
- **Qué hacer:** Eliminar la limpieza (o comprimir/archivar en vez de borrar). Hyperliquid no ofrece esta historia.
- **Por qué:** W-03 · contradice CLAUDE.md («no borres datos_mercado»).
- **Riesgo:** Disco (~200 MB/mes). · **Huella:** sí (código)
- **Hecho cuando:** Ningún os.remove sobre datos_mercado/.
- **Depende de:** —

## Fase 2: Simulación y medición fieles

| ID | Tarea | Prioridad | Esfuerzo | Acción de Roberto |
|---|---|---|---|---|
| CP-M02 | Sombras simuladas con OHLC y costes realistas | P0 | M | — |
| CP-M03 | Stops del simulador con la misma regla que los objetivos | P1 | M | — |
| CP-M04 | Trailing igual en laboratorio y en vivo | P1 | M | — |
| CP-M12 | Descarga de velas fuera del hilo de gestión | P2 | M | — |
| CP-M13 | Margen en el simulador y libre actualizado por apertura | P2 | S | — |
| CP-M14 | Una sola definición de funding_contra | P3 | S | — |
| CP-M22 | Objetivos del laboratorio por cruce estricto | P3 | S | — |
| CP-A01 | Referencia de mercado obligatoria | P0 | M | — |
| CP-A02 | Muestra efectiva por fechas independientes | P1 | S | — |
| CP-A04 | Referencia «BTC > EMA200» en el laboratorio | P1 | S | — |
| CP-A03 | Deflated Sharpe Ratio y PBO | P2 | M | — |
| CP-M20 | Familias de investigación más finas | P2 | S | — |
| CP-M21 | Requisitos de apta_revision más informativos | P2 | S | — |

### CP-M02 · Sombras simuladas con OHLC y costes realistas

- **Dónde:** aprendizaje.py:160-209 (abrir_sombra, actualizar_sombras)
- **Ahora:** Un precio cada ~15 s (alto = bajo = cierre), entrada al mid con comisión maker, stop lleno exacto.
- **Qué hacer:** Avanzar con velas de 1 min (candleSnapshot) o de 1 h archivadas, política «peor», entrada al ask/bid + comisión tomadora, deslizamiento en stops.
- **Por qué:** Q-07 · sesgo +0,123 R/op (t 7,7); +0,074 R solo por muestreo.
- **Riesgo:** Más peticiones (velas de 1 min). · **Huella:** sí (código)
- **Hecho cuando:** Re-simular las 651 sombras con el nuevo método: diferencia con experimentos/sesgo_sombras.py < 0,02 R.
- **Depende de:** —

### CP-M03 · Stops del simulador con la misma regla que los objetivos

- **Dónde:** papel.py:400-428 frente a 283-318
- **Ahora:** Objetivos ven mechas de velas de 1 min; stops solo la marca en el instante de procesar().
- **Qué hacer:** Disparo del stop si el extremo de las velas de 1 min desde la última comprobación cruzó el trigger (aproximación conservadora; mejor con marca si se archiva); fill al trigger + deslizamiento.
- **Por qué:** T-01.
- **Riesgo:** Resultados simulados algo peores (más realistas). · **Huella:** sí (código; subir MODELO)
- **Hecho cuando:** Fixture: mecha que cruza el stop y vuelve → cierra; mecha que cruza el objetivo → mismo trato.
- **Depende de:** CP-M16

### CP-M04 · Trailing igual en laboratorio y en vivo

- **Dónde:** gestor.py:1215-1226; estrategia.py:243-251
- **Ahora:** Lab: por vela de 4 h, aplicado desde la siguiente. Vivo: cada ~15 s con el mid.
- **Qué hacer:** En vivo, recalcular el stop dinámico solo al cierre de la vela del intervalo de la estrategia (o simular sub-velas en el lab).
- **Por qué:** T-05.
- **Riesgo:** Stops algo más lejos. · **Huella:** sí (código)
- **Hecho cuando:** Misma serie de precios en SimSalida y en Gestor (Info falso) → mismo stop final.
- **Depende de:** —

### CP-M12 · Descarga de velas fuera del hilo de gestión

- **Dónde:** motor.py:377 (time.sleep(1.0) por moneda)
- **Ahora:** 45–90 s sin gestionar posiciones ni procesar la cuenta simulada en cada cierre de vela.
- **Qué hacer:** Hilo de descarga con el limitador compartido; el bucle de gestión nunca duerme > 15 s.
- **Por qué:** T-02.
- **Riesgo:** Concurrencia: proteger motor.contextos con un bloqueo. · **Huella:** sí (código)
- **Hecho cuando:** Con 45 monedas y un Info falso lento, gestionar() se llama cada ≤ 15 s.
- **Depende de:** —

### CP-M13 · Margen en el simulador y libre actualizado por apertura

- **Dónde:** papel.py:520-582 (order); bot.py:1002-1058 (bucle de aprobadas)
- **Ahora:** La cuenta simulada nunca rechaza por margen; libre fijo durante el ciclo.
- **Qué hacer:** Rechazo por margen en papel.order() como en Hyperliquid y releer la cuenta tras cada apertura. Solo rechaza lo que en real sería imposible; si el margen libre no alcanza, redimensionar al margen disponible en vez de descartar.
- **Por qué:** T-03.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Dos candidatas que juntas superan el margen → la segunda se rechaza.
- **Depende de:** —

### CP-M14 · Una sola definición de funding_contra

- **Dónde:** laboratorio.py:200 (media 8 h) y motor.py:309 (tasa instantánea)
- **Ahora:** Mismo nombre, dos definiciones.
- **Qué hacer:** Función compartida (como mercado_unificado.rasgos).
- **Por qué:** T-07.
- **Riesgo:** Cambia el filtro de entrada. · **Huella:** sí (código)
- **Hecho cuando:** Prueba de igualdad lab/vivo.
- **Depende de:** —

### CP-M22 · Objetivos del laboratorio por cruce estricto

- **Dónde:** estrategia.py:220-232
- **Ahora:** Lleno al tocar.
- **Qué hacer:** Cruce estricto (o un tick más).
- **Por qué:** T-06.
- **Riesgo:** Resultados del lab algo peores. · **Huella:** sí (código)
- **Hecho cuando:** Prueba de toque exacto.
- **Depende de:** —

### CP-A01 · Referencia de mercado obligatoria

- **Dónde:** validacion.py (nuevo), veredicto.py, informes; experimentos/forense_ledger.py como prototipo
- **Ahora:** Solo veredicto.contra_mercado (todo corto / todo largo) en el paper.
- **Qué hacer:** Para cada operación (lab y paper): exceso frente al universo equiponderado en el mismo lado y ventana, y frente a BTC > EMA200; IC bootstrap; una evidencia sin exceso significativo no cuenta.
- **Por qué:** Q-02 · exceso +0,40 % (t 0,53).
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** El informe del laboratorio muestra el exceso con IC.
- **Depende de:** —

### CP-A02 · Muestra efectiva por fechas independientes

- **Dónde:** validacion.py; promocion.py; preregistro.py
- **Ahora:** Se cuentan operaciones aunque salgan del mismo rebalanceo.
- **Qué hacer:** n efectivo = fechas distintas (rebalanceo o día); exigir ≥ 30 para cualquier juicio.
- **Por qué:** Q-08 · momentum: 63 casos de 4 fechas.
- **Riesgo:** Juicios más lentos. · **Huella:** sí (código)
- **Hecho cuando:** Prueba con 60 ops de 4 fechas → n efectivo 4.
- **Depende de:** —

### CP-A04 · Referencia «BTC > EMA200» en el laboratorio

- **Dónde:** laboratorio.py (línea base)
- **Ahora:** Líneas base: azar y siempre largo.
- **Qué hacer:** Añadir la regla de tendencia de BTC (largo/fuera) como línea base de cartera.
- **Por qué:** B-04 · Sharpe 0,75 frente a 0,12–0,36.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Aparece en estrategia_elegida.json.
- **Depende de:** —

### CP-A03 · Deflated Sharpe Ratio y PBO

- **Dónde:** validacion.py; laboratorio.py (veredicto)
- **Ahora:** Bonferroni por familias.
- **Qué hacer:** DSR con el número real de pruebas y PBO por CSCV; exigir DSR ≥ 0,95 para «supera».
- **Por qué:** 11 (Bailey y López de Prado).
- **Riesgo:** Listón más exigente. · **Huella:** sí (código)
- **Hecho cuando:** Pruebas con series sintéticas conocidas.
- **Depende de:** —

### CP-M20 · Familias de investigación más finas

- **Dónde:** validacion.py:665-671 (familia_idea)
- **Ahora:** Disparador × intervalo.
- **Qué hacer:** Incluir filtro y tipo de salida, o estimar el número efectivo por correlación de resultados.
- **Por qué:** 09 §1.
- **Riesgo:** Listón más exigente para investigación. · **Huella:** sí (código)
- **Hecho cuando:** Prueba con ideas que difieren solo en filtro.
- **Depende de:** —

### CP-M21 · Requisitos de apta_revision más informativos

- **Dónde:** promocion.py:369-408
- **Ahora:** 30 operaciones con R medio > 0 y PnL > 0.
- **Qué hacer:** Añadir: R medio paper dentro del IC del laboratorio, exceso de mercado ≥ 0 y n efectivo por fechas.
- **Por qué:** T-12.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Pruebas de promoción actualizadas.
- **Depende de:** CP-A01, CP-A02

## Fase 3: Mejoras de la operativa (sin bloquear entradas)

| ID | Tarea | Prioridad | Esfuerzo | Acción de Roberto |
|---|---|---|---|---|
| CP-E04 | Memoria por vecinos como filtro de decisión | P1 | S | — |
| CP-E05 | Relajación de filtros tras 24 h sin operar | P1 | S | — |
| CP-E12 | Factor «objetivo diario conseguido» | P3 | S | — |
| CP-A08 | Salida por funding extremo durante la operación | P2 | S | — |
| CP-A15 | Sentido de los fills de ballenas (si se retoma el estudio) | P3 | M | — |
| CP-A07 | Aviso por desviación del laboratorio (sin pausa) | P2 | S | — |
| CP-A14 | Conciliación PnL de fills frente al valor de la cuenta (aviso) | P2 | S | — |
| CP-E09 | Estrategia de liquidaciones inferidas | P2 | S | — |

### CP-E04 · Memoria por vecinos como filtro de decisión

- **Dónde:** bot.py:905-928; aprendizaje.py:215-256; config aprendizaje.activo / explorar_en_simulado
- **Ahora:** Multiplica el tamaño (0,5–1) o veta; hiperparámetros a mano; nunca validada.
- **Qué hacer:** Quitar su efecto en la decisión (factor 1, sin veto). Puede seguir midiendo (medir=True) o borrarse.
- **Por qué:** A-01 · vía memoria 7/7 perdedoras (−0,82 R).
- **Riesgo:** Ninguno conocido. · **Huella:** sí (código)
- **Hecho cuando:** Prueba: con memoria en contra, el tamaño y la aprobación no cambian.
- **Depende de:** —

### CP-E05 · Relajación de filtros tras 24 h sin operar

- **Dónde:** bot.py:817; aprendizaje.py:249; estrategia.py:115-117; config gestion_capital.horas_sin_operar_para_relajar
- **Ahora:** Tras 24 h sin operar acepta R esperado ≥ −0,1 (con tamaño ×0,5).
- **Qué hacer:** Borrar el parámetro relajado y r_minimo_relajado. No operar es válido.
- **Por qué:** T-04 · antipatrón sin base estadística.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Prueba: 48 h sin operar y R esperado −0,05 → rechazo.
- **Depende de:** —

### CP-E12 · Factor «objetivo diario conseguido»

- **Dónde:** config.json → gestion_capital.objetivo_diario_pct = 0; estrategia.py:109-110
- **Ahora:** Tras +3 % en el día el tamaño se reduce a la mitad.
- **Qué hacer:** objetivo_diario_pct: 0 (la condición se desactiva con 0).
- **Por qué:** 05 (#29) · sin base estadística.
- **Riesgo:** Ninguno conocido. · **Huella:** sí (config)
- **Hecho cuando:** factor_capital no reduce tras +3 %.
- **Depende de:** —

### CP-A08 · Salida por funding extremo durante la operación

- **Dónde:** gestor.py:gestionar (1204-1226)
- **Ahora:** Solo se mira el funding al entrar.
- **Qué hacer:** Cerrar si el funding en contra supera un umbral (p. ej. 0,05 %/h) durante N horas.
- **Por qué:** 10, 11 (tope de 4 %/h en Hyperliquid).
- **Riesgo:** Salidas adicionales. · **Huella:** sí (código)
- **Hecho cuando:** Prueba con funding sintético.
- **Depende de:** —

### CP-A15 · Sentido de los fills de ballenas (si se retoma el estudio)

- **Dónde:** ballenas.py; bot.py:502-533
- **Ahora:** Flujo por diferencia de fotos; dir solo para el panel.
- **Qué hacer:** Usar dir (Open/Close Long/Short) para separar aperturas de cierres.
- **Por qué:** W-02.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Cubrir un corto no genera señal larga.
- **Depende de:** —

### CP-A07 · Aviso por desviación del laboratorio (sin pausa)

- **Dónde:** vigilancia.py:49-117
- **Ahora:** Solo reduce el tamaño ×0,5.
- **Qué hacer:** Si el R medio de las últimas 30 operaciones de una estrategia queda bajo el límite inferior del IC del laboratorio: incidente y aviso en el panel/Telegram. No pausa ni reduce.
- **Por qué:** 05 §6.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Prueba con serie degradada → incidente, sin bloqueo de entradas.
- **Depende de:** —

### CP-A14 · Conciliación PnL de fills frente al valor de la cuenta (aviso)

- **Dónde:** bot.py / gestor.py
- **Ahora:** No existe.
- **Qué hacer:** Si la suma de PnL atribuido difiere del cambio de accountValue (sin depósitos) más de X en 24 h: incidente y aviso. Sin pausa.
- **Por qué:** 05 §6.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Prueba con diferencia sintética → incidente.
- **Depende de:** —

### CP-E09 · Estrategia de liquidaciones inferidas

- **Dónde:** config.json → mercado.liquidaciones.activo = false; mercado.py:senales_liquidaciones
- **Ahora:** Solo investigación; genera sombras.
- **Qué hacer:** Desactivar.
- **Por qué:** 04 · lab −0,012 R (n 82); sombras OHLC −0,07 R (n 134).
- **Riesgo:** Ninguno. · **Huella:** sí (config)
- **Hecho cuando:** Ninguna candidata liquidaciones_1h.
- **Depende de:** —

## Fase 4: Operación segura y preparación del real (parte la hace Roberto)

| ID | Tarea | Prioridad | Esfuerzo | Acción de Roberto |
|---|---|---|---|---|
| CP-A16 | Contraseña del panel y Cloudflare Access | P1 | S | poner PANEL_PASSWORD en .env y la política de Cloudflare Access |
| CP-E14 | Panel por túnel sin contraseña | P1 | S | hacerlo después de CP-A16 |
| CP-A11 | Alertas externas probadas | P1 | S | poner TELEGRAM_TOKEN, TELEGRAM_CHAT_ID y HEALTHCHECK_URL |
| CP-A12 | VPS y copias de seguridad | P1 | M | crear la máquina del VPS |
| CP-A10 | Campaña en testnet de Hyperliquid | P1 (P0 antes de real) | M | crear la cuenta/API wallet de testnet |
| CP-A09 | Vigilancia del límite por dirección | P2 | S | — |
| CP-M08 | Límites del piloto real | P1 | S | arranque manual con INICIAR.bat |
| CP-M09 | Techos duros del real más bajos | P1 | S | arranque manual con INICIAR.bat |
| CP-A13 | Datos del laboratorio versionados | P2 | M | — |

### CP-A16 · Contraseña del panel y Cloudflare Access

- **Dónde:** .env PANEL_PASSWORD (propietario); configuración de Cloudflare
- **Ahora:** Sin contraseña.
- **Qué hacer:** PANEL_PASSWORD + política de Access.
- **Por qué:** SEG-01.
- **Riesgo:** Ninguno. · **Huella:** no
- **Hecho cuando:** 401 sin credenciales.
- **Depende de:** —

### CP-E14 · Panel por túnel sin contraseña

- **Dónde:** config.json → panel.tunel_sin_clave; panel.py:1352
- **Ahora:** true: lectura pública de saldo, posiciones y estrategias por el túnel.
- **Qué hacer:** Poner PANEL_PASSWORD (lo hace el propietario), quitar la opción de config y del código.
- **Por qué:** SEG-01 · 10.
- **Riesgo:** Ninguno. · **Huella:** no (CONFIG_SIN_EFECTO)
- **Hecho cuando:** Petición con cabecera Cf-Connecting-Ip y sin credenciales → 401/403.
- **Depende de:** CP-A16

### CP-A11 · Alertas externas probadas

- **Dónde:** .env (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, HEALTHCHECK_URL: los pone el propietario)
- **Ahora:** Sin configurar.
- **Qué hacer:** Configurar y hacer un simulacro de caída.
- **Por qué:** 10.
- **Riesgo:** Ninguno. · **Huella:** no
- **Hecho cuando:** Aviso en < 10 min tras matar el proceso.
- **Depende de:** —

### CP-A12 · VPS y copias de seguridad

- **Dónde:** despliegue/GUIA_HETZNER.md, copia_seguridad.sh
- **Ahora:** PC doméstico, sin copias.
- **Qué hacer:** Migrar al VPS, copias cifradas diarias del ledger y del estado.
- **Por qué:** 10.
- **Riesgo:** Migración (seguir la guía; pruebas en Linux). · **Huella:** no
- **Hecho cuando:** Restauración probada desde copia.
- **Depende de:** CP-M18

### CP-A10 · Campaña en testnet de Hyperliquid

- **Dónde:** red: testnet (bot.py:2181); checklist nuevo en despliegue/
- **Ahora:** Código de órdenes nunca probado contra la API real.
- **Qué hacer:** Ejecutar en testnet: ALO + IOC de reserva, stop, TP, sustitución de stop, cancelación ambigua, reinicio con posiciones, conciliación y cierre de emergencia.
- **Por qué:** 06, 10.
- **Riesgo:** Ninguno (testnet). · **Huella:** no
- **Hecho cuando:** Checklist de 10 escenarios superada.
- **Depende de:** CP-A11

### CP-A09 · Vigilancia del límite por dirección

- **Dónde:** ejecucion.py / bot.py (solo real)
- **Ahora:** No se consulta userRateLimit.
- **Qué hacer:** Solo en modo real: leer userRateLimit cada hora y avisar cuando quede poco margen; no afecta al simulado.
- **Por qué:** 06, 11.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** Prueba con respuesta falsa al límite.
- **Depende de:** —

### CP-M08 · Límites del piloto real

- **Dónde:** config.json → piloto_real
- **Ahora:** 3 % / 9 % / 6 posiciones / 5× / perdida_max_usd 116 (50 %) / mercados *.
- **Qué hacer:** Solo afecta a modo real (hoy no activo): 1 % / 3 % / 3 posiciones / 2× / perdida_max_usd 46 / mercados [BTC, ETH, SOL]. El simulado sigue igual.
- **Por qué:** 10 · sin ventaja demostrada y sin pruebas en real.
- **Riesgo:** Ninguno; /aplicarconfig lo rechaza: exige arranque manual. · **Huella:** sí (config)
- **Hecho cuando:** limites_efectivos en modo real = propuesta.
- **Depende de:** —

### CP-M09 · Techos duros del real más bajos

- **Dónde:** riesgo.py:532-533 (TECHOS_REAL)
- **Ahora:** 3 % / 9 % / 5× / −10 % día / 6 posiciones.
- **Qué hacer:** Solo modo real: TECHOS_REAL 1 % / 3 % / 2× / −3 % día / 3 posiciones. El simulado no cambia.
- **Por qué:** 10.
- **Riesgo:** Ninguno. · **Huella:** sí (código)
- **Hecho cuando:** tests/test_tramos_techos.py actualizado.
- **Depende de:** —

### CP-A13 · Datos del laboratorio versionados

- **Dónde:** laboratorio.py (hash_datos ya existe); almacenamiento externo
- **Ahora:** datos_backtest/ fuera del repositorio; no reproducible.
- **Qué hacer:** Archivar los datos exactos de cada ejecución con su hash (R2/S3).
- **Por qué:** OPS-03.
- **Riesgo:** Coste de almacenamiento. · **Huella:** no
- **Hecho cuando:** Re-ejecución con el mismo hash reproduce el resultado.
- **Depende de:** —

## Fase 5: Investigación (no toca la operativa)

| ID | Tarea | Prioridad | Esfuerzo | Acción de Roberto |
|---|---|---|---|---|
| CP-A05 | Hipótesis prerregistrada: ruptura_4h solo a favor del régimen | P1 | S | — |
| CP-A06 | Estudio de carry con funding de Hyperliquid | P1 | M | — |
| CP-V01 | fuerza_4h: prerregistro y versión de cartera neutral | P2 | M | — |
| CP-V02 | Cartera de funding tal como se opera | P2 | M | — |
| CP-V03 | Cerebro con historia solo de Hyperliquid y por régimen | P2 | M | — |
| CP-V04 | Salidas: TP1 + trailing frente a solo tiempo + stop | P2 | S | — |
| CP-V05 | Ablación regla a regla en el laboratorio | P2 | M | — |

### CP-A05 · Hipótesis prerregistrada: ruptura_4h solo a favor del régimen

- **Dónde:** preregistro.py
- **Ahora:** Solo fuerza_4h y carry_realista.
- **Qué hacer:** Definición fija (parámetros del 22/11, régimen EMA200 de BTC en 4 h), muestra fijada, juicio único.
- **Por qué:** B-02 · +0,051 R, t 2,22 (no pasa el listón).
- **Riesgo:** Sube a 3 hipótesis (listón). · **Huella:** no (preregistro sin efecto)
- **Hecho cuando:** Hipótesis escrita antes de mirar nuevos datos.
- **Depende de:** —

### CP-A06 · Estudio de carry con funding de Hyperliquid

- **Dónde:** estudios_ext/ o carry/ (estudio aparte)
- **Ahora:** Estudio con funding de Binance.
- **Qué hacer:** fundingHistory de Hyperliquid 2023–2026, 4 patas de costes, holdout.
- **Por qué:** 04, 11 (BIS WP 1087).
- **Riesgo:** Ninguno. · **Huella:** no
- **Hecho cuando:** Informe con R anual neto e IC.
- **Depende de:** —

### CP-V01 · fuerza_4h: prerregistro y versión de cartera neutral

- **Dónde:** preregistro.py; senales.py:193-210
- **Ahora:** Prerregistro en curso (1/30).
- **Qué hacer:** Mantener el prerregistro; estudiar además largo top / corto bottom semanal neutral.
- **Por qué:** 04 · lab +0,088 (t 0,59); independiente +0,062 (t 0,68).
- **Riesgo:** — · **Huella:** —
- **Hecho cuando:** Veredicto del prerregistro.
- **Depende de:** —

### CP-V02 · Cartera de funding tal como se opera

- **Dónde:** laboratorio.py; cartera_funding.py
- **Ahora:** No pasa por el laboratorio.
- **Qué hacer:** Simularla en el lab con las mismas reglas (2 patas, stop, funding de HL).
- **Por qué:** S-04.
- **Riesgo:** — · **Huella:** —
- **Hecho cuando:** Veredicto del lab.
- **Depende de:** —

### CP-V03 · Cerebro con historia solo de Hyperliquid y por régimen

- **Dónde:** laboratorio.py:686-770 (evaluar_cerebro)
- **Ahora:** Mejora solo donde hay historia de Binance.
- **Qué hacer:** Experimento dedicado (R-06 de la auditoría interna); si no supera, retirar el cerebro.
- **Por qué:** C-01.
- **Riesgo:** — · **Huella:** —
- **Hecho cuando:** Informe con ambas variantes y régimen.
- **Depende de:** —

### CP-V04 · Salidas: TP1 + trailing frente a solo tiempo + stop

- **Dónde:** laboratorio.py; senales.MODULOS[*].salida
- **Ahora:** Las ganancias salen por tiempo máximo.
- **Qué hacer:** Comparar en el lab ambas gestiones con la misma entrada.
- **Por qué:** Q-04, B-02 (objetivo final 4 %).
- **Riesgo:** Una variante más (listón). · **Huella:** —
- **Hecho cuando:** Veredicto del lab.
- **Depende de:** —

### CP-V05 · Ablación regla a regla en el laboratorio

- **Dónde:** laboratorio.py
- **Ahora:** Solo ablación natural con sombras (05).
- **Qué hacer:** Repetir la simulación quitando cada filtro de estrategia (régimen, funding, volatilidad, enfriamiento, persecución) con todo lo demás fijo.
- **Por qué:** 05 §1.
- **Riesgo:** Gasta holdout si no se hace en copia. · **Huella:** —
- **Hecho cuando:** Tabla de ablación con IC.
- **Depende de:** —

## Excluidas (impedirían o reducirían la operativa)

| ID | Propuesta | Motivo |
|---|---|---|
| CP-E01 | momentum_4h fuera de la operativa | apagaría momentum_4h (deja de operar una estrategia) |
| CP-E02 | Exploración amplia | quitaría la exploración amplia (deja de operar esa vía) |
| CP-E03 | Exploración del cerebro en simulado | con el modelo actual el cerebro dejaría de aprobar operaciones |
| CP-E07 | Ballenas como señal y como veto | ballenas_1h dejaría de operar (se mejora su señal con CP-A15 en su lugar) |
| CP-E08 | Seguimiento de ballenas en el bot de producción | quitaría las ballenas del bot |
| CP-E10 | Estrategias negativas evaluadas en sombra | las sombras de las estrategias apagadas alimentan el aprendizaje; se mantienen |
| CP-E11 | Escéptico y revisor de IA | se corrige el prompt (CP-M06) en lugar de quitarlo |
| CP-E15 | Cartera de funding hasta validarla | la cartera de funding dejaría de operar |
| CP-E16 | Vistas decorativas del panel (opcional) | no afecta al trading; queda a gusto del propietario |
| CP-M01 | El laboratorio gobierna lo que se opera | impediría operar estrategias que el laboratorio no aprueba (hoy, todas) |
| CP-M07 | Riesgo por operación en simulado | reduciría el tamaño de las operaciones (3 % confirmado por el propietario) |
| CP-M10 | Suelo de emergencia | un suelo de −20 % también apagaría el simulado; el tope del real ya lo cubre CP-M08 (perdida_max_usd) |
| CP-M11 | Exposición neta y beta | límites de exposición más estrictos bloquearían entradas |
