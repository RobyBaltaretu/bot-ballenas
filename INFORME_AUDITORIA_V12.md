# Informe de la auditoría (28/10/2026)

Trabajo hecho sobre el código de `bot-ballenas-v6/bot-ballenas` (la versión «v12» del encargo; no hay repositorio
git, así que la copia del estado anterior está en `copias/antes_auditoria_20261028/`). El modo sigue siendo
**simulado**: no se ha enviado ninguna orden, no se ha conectado ninguna cuenta, no se ha tocado `.env` ni se ha
desplegado nada. **Ningún resultado de este trabajo es una cifra de rentabilidad ni de acierto.**

Pruebas: `.venv\Scripts\python -m unittest discover -s tests -t .` → **395 pruebas, todas OK** (antes, 304).
`python bot.py --validar-config` → configuración válida, modo simulado.

> El bot en marcha (pid del `bot.lock.info`) sigue con el código ANTERIOR hasta que se reinicie
> (`/aplicarconfig`). No lo he reiniciado.

## 1. Matriz requisito → cambio → prueba → resultado

| Req. | Qué se ha hecho | Archivo / función | Prueba | Resultado |
|---|---|---|---|---|
| A-01.1-2 | La huella incluye `contexto_externo.py` (pasa a código que decide) y su configuración (sale de `CONFIG_SIN_EFECTO`) | `promocion.ARCHIVOS_CODIGO`, `CONFIG_SIN_EFECTO` | `test_integridad_modelo.test_cambiar_regla_de_contexto_externo_invalida` | OK |
| A-01.2 | Identidad reproducible del modelo: sha256 del modelo canónico + versión de rasgos + versión del documento; `VERSION_HUELLA = 3` | `cerebro_vivo.identidad_modelo`, `mercado_unificado.VERSION_RASGOS`, `promocion.huella(modelo=)`, `modelo_decisivo` | `test_identidad_es_la_misma_para_bot_cli_y_laboratorio` | OK |
| A-01.2 | El laboratorio guarda la procedencia del modelo (rasgos, hash de datos, hash de código, modelo de simulación) y registra la evidencia con la MISMA identidad | `laboratorio` (escritura de `cerebro_modelo.json`, `registrar_evidencias`) | (cubierta por la de identidad) | OK |
| A-01.4 | En vivo la huella usa el modelo CARGADO; sin modelo válido → huella `None` → nada autorizado; incidente «cerebro/modelo» | `bot._huella`, `bot.procesar_candidatas`, `bot.estrategias_promovidas` | `test_cambiar_un_coeficiente_impide_operar_en_real_hasta_nueva_aprobacion` (**aceptación**) | OK |
| A-01.4 | Recarga por CONTENIDO (no por fecha); archivo ausente, JSON roto, NaN/Inf, rasgos o versión de rasgos desconocidos → sin modelo | `CerebroVivo.recargar` | `test_archivo_ausente…`, `test_json_corrupto…`, `test_pesos_nan_o_inf…`, `test_version_de_rasgos…`, `test_modelo_que_desaparece…` | OK |
| A-01.5 | Cada decisión guarda `hash_modelo` y `version_rasgos` en el ledger | `bot.procesar_candidatas` (`decision.cerebro`) | `test_bot` (ruta de decisión) | OK |
| A-01.6 | Migración: aprobaciones sin identidad del modelo → `investigacion` + `pendiente_revision`, copia `.v1.bak` | `promocion.Registro._migrar` | `test_migracion_pasa_aprobaciones_viejas…` | OK (hoy no había ninguna aprobación) |
| A-01.7 | Huella truncada o mal formada → no autoriza; registro de promociones corrupto → falla cerrado y conserva el original | `huella_bien_formada`, `Registro.corrupto` | `test_huella_truncada_bloquea`, `test_registro_corrupto_falla_cerrado…` | OK |
| Gemini «no_supera» | En REAL solo decide un modelo «supera», lo diga la config o no; en simulado se carga etiquetado como exploración | `CerebroVivo.decidir` | `test_en_real_un_modelo_no_supera_nunca_decide`, `test_cuatro_estados_en_simulado_y_real` | OK |
| A-02.1-3 | Tamaño con tres presupuestos: base (stop + costes + funding), **severo** (salto / sin liquidez) y **límite de la orden hija** (tolerancia del stop). Desglose por partes y escenarios; nota de que nada es un máximo garantizado | `riesgo.escenarios_stop`, `riesgo.dimensionar`, `SIN_TOPE` | `test_riesgo_stop.test_respeta_los_tres_presupuestos_largo_y_corto` (comprobación matemática independiente, largo y corto) | OK |
| A-02.3 | Supuestos explícitos, validados y en la huella: `riesgo.stop_deslizamiento_severo_pct` (1 %), `riesgo.riesgo_severo_max_multiplo` (2×), `riesgo.perdida_limite_stop_max_pct` (15 %), `ordenes.tolerancia_stop_pct` (10 %, rango 1–10) | `configuracion.DEFECTOS/validar` | `test_tolerancia_fuera_de_rango_no_valida` | OK |
| A-02.1 | El stop deja de usar un 0,9/1,1 fijo: usa la tolerancia configurada (la misma del dimensionado) | `gestor.poner_stop` | `test_limite_del_stop_usa_la_tolerancia_configurada_reduce_only` | OK |
| A-02.4 | Riesgo tras el fill frente al plan (evento `riesgo_post_fill`); al cerrar, pérdida/riesgo inicial y fill peor que el trigger (alerta) | `riesgo.comparar_con_plan`, `analisis_salida_stop`, `gestor._despues_de_entrada`, `procesar_cierre` | `test_comparacion_con_plan_y_cola_del_stop` | OK |
| A-02.4 | Si la tolerancia supera el presupuesto, no se abre | `dimensionar` | `test_tolerancia_que_excede_el_presupuesto_no_abre` | OK |
| A-02.5 | Unidades `_pct` vs fracción; mínimo de 10 USD y redondeo; funding en todos los escenarios | `riesgo` | `test_unidades…`, `test_minimo_de_10_usd…`, `test_funding_previsto…` | OK |
| Gemini motor | La vela solo se marca procesada tras leer contexto válido con esa vela; fallo / `None` / vela atrasada se reintentan mientras sea reciente; contadores visibles (`reintentos`, `perdidas_tras_reintentos`, `duracion_lectura_s`). `sleep(1)` sin cambiar | `motor.nuevas_senales` | `test_motor_velas` (4 casos) | OK |
| Gemini gestor 1 | TP1 y TP final se ponen y registran por separado | `gestor._despues_de_entrada` | `test_tp1_fallido_no_impide_el_objetivo_final` | OK |
| Gemini gestor 2 | Conciliación de objetivos: tamaños coherentes con la posición, reposición del final solo con estado final confirmado y tras releer la cuenta; estado incierto → no se reenvía | `gestor._reconciliar_tps` | `test_objetivo_final_que_desaparece_se_repone…`, `test_objetivo_con_estado_incierto_no_se_repone…` | OK |
| Gemini gestor 3 | Reducción explicada por FILLS de los objetivos aunque el estado de la orden vaya atrasado; si no hay atribución única → `contabilidad_incompleta`, congelado, estado `unknown` | `gestor._reduccion` | `test_parcial_con_estado_de_orden_atrasado…`, `test_reduccion_sin_atribucion_unica…` | OK |
| Gemini gestor 4 | Trailing con estado explícito (`trailing_activo`); sin parcial solo con `salida.trailing_sin_parcial` (por defecto `false` = comportamiento de siempre). Mismo criterio en `SimSalida` | `gestor.trailing_activo`, `estrategia.SimSalida.paso` | `test_trailing_sin_parcial…` (3 pruebas) | OK |
| Gemini gestor 5 | Al cerrar se buscan TODOS los fills que faltan (también tras un TP1), deduplicados; con actividad externa en la moneda → resultado desconocido (sin PnL), congelado de tipo «contabilidad» (no se levanta solo) | `gestor.procesar_cierre` | `test_tp1_y_despues_stop_con_otro_oid…`, `test_actividad_externa_concurrente…` | OK |
| Gemini gestor 6 | Tramos de tamaño con hora del FILL del exchange; si es incierta, el funding de la ventana dudosa queda sin asignar | `gestor.intervalos_funding` | `test_cambio_de_tamano_con_hora_incierta…` | OK |
| Gemini gestor 7 | Antes de mover el stop, lado del trigger validado contra mid y mark; si se rechaza, se comprueba que el anterior sigue vivo (si no: sin stop + congelado) | `gestor._trigger_invalido`, `_proteccion_anterior_viva` | `test_trigger_al_otro_lado_del_precio…` | OK |
| Gemini SimSalida | Política intrabar declarada: base «peor orden plausible», «favorable» solo para sensibilidad; contador `ambiguas`; compatible con simulaciones ya guardadas | `estrategia.SimSalida` | `test_simsalida_intrabar` (9 casos) | OK |
| Gemini sombras | Las sombras declaran `muestreo = "puntual"` (no equivalen al simulador OHLC) | `aprendizaje.actualizar_sombras` | (documental) | Hecho |
| Gemini limitador | Pesos según la documentación vigente (consultada hoy): base + peso extra por elementos (`userFills`… /20, `candleSnapshot` /60); cada reintento sigue contando; `datos.Api` comparte el limitador del bot; otro proceso con el bot en marcha usa solo lo que queda de 1200 | `limitador.peso/peso_extra/cargar`, `datos.Api`, `bot.crear_cliente` | `test_limitador` (5 casos) | OK |
| Gemini panel | Sin `PANEL_PASSWORD`, solo este equipo SIN cabeceras de túnel/proxy; con ellas → 403. Freno a la fuerza bruta (10 fallos/5 min → 429) | `panel._autorizado` | `test_panel_proxy` (4 casos) | OK |
| Revisión puntual | `ordenes.espera_limite_seg` del panel alineado con la validación (máx. 60 s) | `config_panel.py` | `test_config_panel` | OK |
| A-03 | Cartera: cierres por orden de cierre, orden determinista, bloqueos por pérdida diaria/semanal y caída, abiertas al final CENSURADAS, candidatas/aceptadas/rechazadas por regla, R total, días invertidos y lista de **lo que no modela** | `validacion.cartera_produccion` | `test_validacion_cartera.Cartera` (3 casos) | OK |
| A-03.5 | El veredicto de las estrategias exige la cartera con límites (antes solo el cerebro) | `validacion.veredicto(cartera=)`, `laboratorio` | `test_pasa_por_operaciones_pero_falla_por_cartera` | OK |
| A-04.3 / A-12 | Comparación EMPAREJADA por día con cada línea base, mismo periodo, bootstrap por bloques de días contiguos; sin días suficientes → `no_evaluable` | `validacion.diferencia_emparejada` | `test_media_bruta_positiva_pero_emparejada_no_supera`, `test_sin_dias_comunes…` | OK |
| A-04.9 | Registros de variantes y holdout: si están dañados se usa la copia `.bak`; si tampoco, error (nunca empiezan vacíos); escritura atómica y durable | `validacion.leer_registro/guardar_registro` | `RegistrosFallanCerrado` (3 casos) | OK |
| A-07 | El carry queda etiquetado `hipotesis_cross_venue`, con supuestos, lo no modelado y comparadores pendientes | `laboratorio.carry_realista` | (documental en el resultado) | Hecho |
| A-11 | Un cambio de capital solo desplaza referencias y queda registrado (anterior/nuevo/tipo, `limites_modificados: false`); en real el capital usado nunca pasa de `capital_max_usd`; ~200 € no activan nada | `riesgo.rebasar_capital`, `bot.equity` | `test_capital_piloto` (5 casos) | OK |
| CoinGlass | Conector de SOLO lectura, desactivado por defecto y sin clave → `sin_clave`; estados explícitos; procedencia; la clave nunca sale; ningún módulo que decide lo importa | `coinglass.py` (nuevo), `.env.example` | `test_coinglass` (6 casos) | OK (sin verificar contra la API real: no hay clave) |
| A-10.1 | `python diagnostico.py`: huellas, identidad del modelo, integridad de archivos (sha256, JSON válido), lo que falta, lo desconocido, todo redactado; nunca lee `.env` | `diagnostico.py` (nuevo) | `test_diagnostico` | OK |

## 2. Cambios por archivo

- `promocion.py`: huella v3 (modelo + rasgos), `modelo_decisivo`, `identidades_archivo`, `huella_bien_formada`, registro con migración v1→v2, falla cerrado si está corrupto, escritura con `fsync`. CLI usa la identidad del modelo.
- `cerebro_vivo.py`: `identidad_modelo`, recarga por contenido, rechazo de NaN/Inf y versión de rasgos desconocida, «supera» obligatorio en real, `hash_modelo` en cada decisión.
- `mercado_unificado.py`: `VERSION_RASGOS = 1`.
- `bot.py`: huella con el modelo cargado, incidente si no hay modelo, `hash_modelo` en el ledger, marcas al gestor, limitador compartido, aviso de registro de promociones corrupto o migrado.
- `riesgo.py`: `escenarios_stop`, tres presupuestos en `dimensionar`, `comparar_con_plan`, `analisis_salida_stop`, registro auditable de cambios de capital.
- `gestor.py`: TP por separado, `_reconciliar_tps`, reducción por fills, tramos con hora del fill, `intervalos_funding`, `trailing_activo`, cierre con todos los fills y «contabilidad incompleta», validación del trigger, tolerancia configurable del stop, riesgo tras el fill.
- `estrategia.py`: política intrabar y `ambiguas`; trailing sin parcial opcional.
- `motor.py`: marcado de vela procesada tras datos válidos.
- `limitador.py` / `datos.py`: pesos documentados, peso extra, presupuesto compartido.
- `validacion.py`: cartera ampliada, diferencia emparejada, registros que fallan cerrado.
- `laboratorio.py`: procedencia del modelo, evidencia con identidad del modelo, cartera en el veredicto de las estrategias, etiquetas del carry.
- `panel.py`: autenticación tras túnel/proxy, freno a la fuerza bruta. `config_panel.py`: rango de espera.
- `configuracion.py`: claves nuevas `riesgo.stop_deslizamiento_severo_pct`, `riesgo.riesgo_severo_max_multiplo`, `riesgo.perdida_limite_stop_max_pct`, `ordenes.tolerancia_stop_pct`, `salida.trailing_sin_parcial` (todas con valor por defecto; `config.json` no necesita cambios).
- `ledger.py`: tipo de evento `riesgo_post_fill`. `aprendizaje.py`: `muestreo = "puntual"`.
- Nuevos: `coinglass.py`, `diagnostico.py` (clasificados «sin efecto» en `promocion.py`), 12 archivos de prueba.

**Compatibilidad**: `promociones.json` se migra al cargarse (copia `.v1.bak`); como no había aprobaciones, no cambia
ninguna etapa. Las simulaciones de sombra ya guardadas siguen funcionando. Con la configuración actual (2 % por
operación) los tres presupuestos casi nunca reducen el tamaño: manda antes el margen máximo; donde más se notan es
con stops muy cortos.

## 3. Lo que NO está hecho (o solo en parte) y por qué

- **A-03 (completo)**: la cartera NO es un motor compartido con el bot. No valora a mercado cada día y no aplica exposición por moneda, bruta, neta ni beta, correlación, margen, impacto, tamaño por precio y stop real ni gestión de capital. Ahora lo declara (`limites_no_modelados`), pero sigue siendo una aproximación.
- **A-04**: falta el registro append-only de cada consulta adaptativa, el periodo confirmatorio que se reinicia, el bootstrap multi-activo de cartera diaria, DSR/PBO, el sesgo de supervivencia con universo histórico (no hay datos de monedas retiradas) y la revisión de los escenarios de costes (doble conteo, funding adverso).
- **A-05**: no hay fixtures congelados de paridad laboratorio/vivo más allá de la prueba que ya existía. Tampoco se ha corregido el supuesto de 8 h del primer intervalo en `historia_externa.funding_horario`, ni las cohortes HL-only / externo / solape, ni `kPEPE`, ni el comportamiento con Binance caído o con las fuentes reordenadas.
- **A-06**: no hay replay L2, ni capturador de libro y trades, ni modelo de cola o latencia. El TP maker histórico sigue contándose lleno al tocarse. Tampoco hay paridad de costes en `simular_flujo` / `probar_mercado`.
- **A-07**: solo etiquetas. No se simulan dos patas con fills ni márgenes, ni hay comparadores.
- **A-08**: sin cambios en `ledger.py`: rotación, huecos, secuencia y el `id_fill` de respaldo que puede colisionar. Tampoco hay lease o heartbeat entre equipos. `estado.json` y `papel.json` no se han revisado.
- **A-09**: sin auditoría de `innerHTML` en `panel.html` (197 KB). La CSP sigue con `unsafe-inline`. No hay rotación de contraseña.
- **A-10.2-5**: sin SBOM ni pip-audit (no he instalado nada), sin pruebas de disco lleno ni permisos, sin OpenTelemetry/Prometheus.
- **P2** (contexto de mercado al arrancar, OBI/micro-price, ballenas OOS): no tocado.
- **Gemini, revisión puntual**: `interpretar_respuesta` / `papel.order` con fill parcial que queda abierto. He comprobado que la apertura toma el tamaño real de la CUENTA y de los fills (`_despues_de_entrada`), así que no se pierde. No he añadido una prueba específica de «parcial + cancelación».
- **CoinGlass**: rutas y cabecera según la documentación pública; el formato de respuesta y la cobertura por plan están SIN verificar (no hay clave). Lo mismo para la matriz de fuentes de Binance y Bybit: sin trabajo nuevo.
- **WebSocket de Hyperliquid, NautilusTrader, Hypothesis stateful, contrato de endpoints para un futuro frontend, lista de requisitos de despliegue**: no hechos.

## 4. Matriz de fuentes (estado actual)

| Fuente | Endpoint / campo | Unidad | Frecuencia | Límite / coste | Antigüedad aceptable | Fallback | Uso permitido | Pruebas |
|---|---|---|---|---|---|---|---|---|
| Hyperliquid REST | info (velas, libro, mids, cuenta, fills, funding) | según endpoint | ciclo del bot | 1200 peso/min/IP (900 bot + resto) | `riesgo.datos_max_antiguedad_seg` | no se entra | decide (en simulado) | `test_limitador`, `test_motor_velas` |
| Binance / Bybit públicos | velas cerradas, funding (`contexto_externo.py`) | precio, %/h | 5 min | gratis, público | `cerebro.max_antiguedad_externos_min` | rasgo = None | rasgos del cerebro (ahora en la huella) | `test_contexto_externo`, `test_cerebro_vivo` |
| CoinGlass v4 | OI agregado, funding, liquidaciones, taker, whale-alert/position HL | USD / fracción | bajo demanda | de pago, cabeceras `API-KEY-*-LIMIT` | `max_antiguedad_seg` 3600 | estado explícito, datos None | **research_only** (desactivado) | `test_coinglass` |

## 5. Lo que sigue bloqueando el modo real

1. Ningún modelo del cerebro «supera» el laboratorio (4 h y 1 h = `no_supera`). En real el cerebro se abstiene siempre.
2. No hay ninguna estrategia en `apta_revision` ni en `real_habilitado`. Cualquier aprobación necesita `promocion.py` y la confirmación literal de Roberto, ligada a la identidad exacta del modelo.
3. Los supuestos del stop severo (1 %) y de la tolerancia (10 %) no están calibrados con fills reales. **La pérdida no tiene tope garantizado** si el precio salta más allá del límite de la orden hija.
4. Siguen pendientes las partes de A-03, A-04, A-05, A-06 y A-08 de la sección 3. Mientras falten, los resultados del laboratorio son aproximaciones.
