# 03 — Auditoría técnica

Severidad: **P0** crítica (pérdidas graves o invalida resultados) · **P1** alta · **P2** media · **P3** baja.
Evidencia: **[C]** demostrada en código · **[D]** demostrada con datos del repositorio · **[X]** experimento propio ·
**[H]** hipótesis.

## A. Lo que está bien hecho (verificado)

No es complaciente: estas piezas son mejores que las de la mayoría de bots minoristas y deben **conservarse**.

| Pieza | Por qué es correcta | Ref. |
|---|---|---|
| Idempotencia de órdenes | CLOID de 128 bits generado y registrado antes de enviar; respuesta ambigua → consulta, nunca reenvío; congelación del mercado si no se resuelve | ejecucion.py:280-320, 240-277 |
| Cancelación verificada | Un ACK no cuenta: se re-consulta el estado final | ejecucion.py:336-387 |
| Stop verificado y sustitución segura | Nuevo stop puesto y verificado antes de cancelar el viejo; adopción de stops existentes para no duplicar | gestor.py:746-845 |
| Entrada con verdad de cuenta | Lo ejecutado lo dicen la POSICIÓN y los FILLS; la IOC de reserva solo por lo que falta | gestor.py:1040-1086 |
| Propiedad y externas | Lo que no es del bot no se toca; divergencias congelan | gestor.py:116-171, 267-379 |
| Falla cerrado | Sin modelo, con modelo corrupto, sin datos externos, sin huella: no entra nada | cerebro_vivo.py, promocion.py |
| Arranque real | `userRole` exige subcuenta + API wallet de su maestra; el cliente firmante se crea el último | bot.py:160-184, 2199-2218 |
| Riesgo con escenarios | Tamaño = mínimo de tres presupuestos (base, severo, límite del stop); salto conjunto por lado | riesgo.py:121-180, 320-370 |
| Contabilidad | PnL desde fills y funding atribuido con reglas estrictas; nunca desde la variación del saldo | contabilidad.py |
| Reconstrucción | Mi reconstrucción independiente del ledger coincide al céntimo con la del bot | experimentos/forense_ledger.py |

## B. Hallazgos

### T-01 · Sesgo de muestreo de stops y objetivos en el simulador · P1 · [C][D]
- **Dónde:** `papel.py:400-428` (stops) frente a `papel.py:283-318` (límites/objetivos).
- **Problema:** el stop se dispara solo si la marca está al otro lado del trigger **en el instante** de `procesar()`
  (cada ~15 s, y nada durante los ~45–90 s de descarga de velas, T-02). El objetivo se llena si una vela de 1 min
  posterior a la orden se imprimió más allá de su precio, es decir, ve las mechas entre comprobaciones.
- **Causa raíz:** dos modelos de llenado distintos para órdenes reduce-only del mismo tipo de riesgo.
- **Consecuencia técnica:** una mecha que cruza el stop y vuelve no lo dispara en simulado; otra que cruza el objetivo
  sí lo llena. Cuando el precio sigue de largo, el stop se detecta tarde y llena peor (SKY 23/11: marca 1,7 % más allá
  del trigger al detectarlo, fill 2 % peor).
- **Consecuencia financiera:** el paper no reproduce el motor de disparo de Hyperliquid (marca evaluada de forma
  continua). Dirección neta del sesgo incierta; su varianza sí es mayor que la real.
- **Corrección:** evaluar stops con la misma regla que los objetivos (velas de 1 min de MARCA si se archivan, o de
  operaciones como aproximación conservadora: disparo si el extremo cruzó el trigger) y llenar al trigger + deslizamiento
  modelado; registrar ambos modelos en paralelo durante un mes.
- **Prueba:** fixture de velas con mecha que cruza stop y vuelve → debe cerrar; mecha que cruza objetivo → igual regla.

### T-02 · Bloqueo del hilo principal al cierre de vela · P2 · [C]
- **Dónde:** `motor.py:377` (`time.sleep(1.0)` por moneda e intervalo).
- **Problema:** con ~45 monedas y 2 intervalos, el ciclo queda 45–90 s sin gestionar posiciones ni llamar a
  `papel.procesar()`. El hueco < 180 s no activa `_recuperar_hueco`.
- **Consecuencia:** en simulado, stops y objetivos congelados ese tiempo cada hora; en real los stops están en el
  exchange (sin riesgo de pérdida), pero el trailing local y los cierres por tiempo se retrasan.
- **Corrección:** descargar velas en un hilo con el limitador compartido, o un único `candleSnapshot` incremental por
  moneda; nunca dormir en el hilo de gestión.
- **Prueba:** simular 45 monedas con un `Info` falso lento y verificar que `gestionar()` se llama cada ≤ 15 s.

### T-03 · Margen no simulado y libre desactualizado dentro del ciclo · P2 · [C]
- **Dónde:** `papel.py:520-582` (sin comprobación de margen), `bot.py:813` (`eq, libre` una vez por ciclo).
- **Problema:** varias aprobadas del mismo ciclo se dimensionan con el mismo margen libre; el simulador nunca rechaza
  por margen (`perpMarginRejected` en real).
- **Consecuencia:** en real podrían rechazarse entradas que en simulado se abren → divergencia paper/real.
- **Corrección:** releer la cuenta tras cada apertura y validar margen en `papel.order()` con la fórmula de
  Hyperliquid.
- **Prueba:** dos candidatas que juntas superan el margen → la segunda se rechaza en ambos modos.

### T-04 · Relajación de filtros tras 24 h sin operar · P2 · [C]
- **Dónde:** `bot.py:817`, `aprendizaje.py:249` (`r_minimo_relajado −0,1`), `estrategia.py:115-117`.
- **Problema:** si el bot no opera en 24 h, la memoria acepta operaciones con R esperado de hasta −0,1.
- **Causa raíz:** objetivo implícito de «no quedarse parado».
- **Consecuencia financiera:** entra en operaciones que su propio filtro considera de esperanza negativa precisamente
  cuando el mercado no ofrece señales. Sin justificación estadística.
- **Corrección:** eliminar la relajación. No operar es una decisión válida.
- **Prueba:** con 48 h sin operar, `valorar()` con R esperado −0,05 debe rechazar.

### T-05 · El trailing del laboratorio no es el del bot · P2 · [C]
- **Dónde:** `estrategia.py:243-251` frente a `gestor.py:1215-1226`.
- **Problema:** el lab mueve el stop dinámico con el extremo de la vela (4 h) y lo aplica desde la vela siguiente; el
  bot lo mueve cada 15 s con el mid.
- **Consecuencia:** con momentum v2 (trailing 1,5 R) el vivo sale antes en retrocesos intravela. Lo validado no es lo
  operado; además la salida por tiempo domina las ganancias (Q-04), así que el trailing cambia el reparto de resultados.
- **Corrección:** o el bot aplica el trailing solo al cierre de vela (como el lab), o el lab lo simula con velas de
  1 h/15 min dentro de cada vela de 4 h.
- **Prueba:** misma serie de precios en `SimSalida` y en `Gestor` con `Info` falso → mismo stop final.

### T-06 · El laboratorio llena objetivos al tocarlos · P3 · [C]
- **Dónde:** `estrategia.py:220-232` (`favorable >= tp`); el simulado exige operación impresa peor (`papel.py:312-315`).
- **Consecuencia:** lab ligeramente optimista en objetivos. **Corrección:** exigir cruce estricto o un tick más.

### T-07 · `funding_contra` con dos definiciones · P3 · [C]
- **Dónde:** `laboratorio.py:200` (media de 8 h) frente a `motor.py:309` (tasa instantánea prevista).
- **Consecuencia:** el rasgo de la memoria y el filtro de entrada no miden lo mismo que se aprendió. **Corrección:**
  una sola función compartida (como `mercado_unificado.rasgos`).

### T-08 · Funding perdido si el bot está parado varias horas (simulado) · P3 · [C]
- **Dónde:** `papel.py:245-268`. Solo se paga una hora al volver. **Corrección:** iterar por cada hora perdida con
  `fundingHistory`.

### T-09 · Pruebas no herméticas · P3 · [X]
- **Dónde:** `tests/test_panel_web.py`, `test_feed.py`, `test_config_panel.py`, `test_panel_proxy.py`,
  `test_bot.LatidoExterno`. Intentan `POST api.hyperliquid.xyz/info` y pasan igual sin red.
- **Corrección:** inyectar un `Info` falso; marcar como fallo cualquier socket abierto durante las pruebas.

### T-10 · Codificación inconsistente · P3 · [C]
- BOM UTF-8 en `carry/motor.py` y `carry/terreno.py`; CRLF mezclado en `terreno.py`; restos literales «`n» de PowerShell
  en `CLAUDE.md`. **Corrección:** `.editorconfig` + comprobación en las pruebas.

### T-11 · Etiqueta del modelo de simulación desactualizada · P3 · [C]
- **Dónde:** `papel.py:14,41` (`MODELO = 3`), `promocion.py:196` (`MODELO_SIMULACION = 2`).
- **Consecuencia:** la evidencia «paper» posterior al 19/11 queda etiquetada como modelo 2. La huella cambia igualmente
  (papel.py está en `ARCHIVOS_CODIGO`), así que no hay riesgo de autorización; sí de trazabilidad.
- **Corrección:** `MODELO_SIMULACION = papel.MODELO` (una sola fuente) y una prueba que lo exija.

### T-13 · La curva de valor se trunca a ~10 días · P3 · [C][D]
- **Dónde:** `bot.py:1762-1765` (`del hist[:-3000]` con un punto cada 5 min).
- **Consecuencia:** imposible calcular caída, Sharpe o comparaciones de cartera sobre todo el periodo de paper desde el
  propio estado (hoy solo cubre 13/11 → 24/11). **Corrección:** guardar la curva diaria completa en un JSONL aparte.

### T-12 · Evidencia «paper» para promoción sin significación · P2 · [C]
- **Dónde:** `promocion.py:369-408`. Para `apta_revision` bastan 30 operaciones con R medio > 0 y PnL > 0 (además del
  laboratorio «supera»).
- **Consecuencia:** con una estrategia de esperanza cero, 30 operaciones dan R medio > 0 alrededor del 50 % de las
  veces. La barrera real es el laboratorio; el paper casi no añade información.
- **Corrección:** exigir que el IC del R medio paper no contradiga al del laboratorio (prueba de degradación) y medir
  frente a la referencia de mercado (Q-02).

### Q-05 · Piramidación que deshace el objetivo parcial · P1 · [C][D]
- **Dónde:** `bot.py:1245-1310`, `gestor.py:1219-1221, 1260-1349`.
- **Problema:** cobrar el TP1 pone el stop en la entrada (`en_breakeven`) → la operación pasa a «ampliable» → en el
  siguiente ciclo se recompra el 50 % del tamaño inicial con IOC (taker), justo lo que se acaba de vender con límite.
- **Evidencia:** SKY `op-20261123130132-ccb50a`: TP1 a las 13:40:29, ampliación a las 13:40:36 a 0,03757 (peor que el
  TP1 0,037436), stop en sin pérdidas saltado a las 13:56 con fill 2 % peor: **+0,29 R → −0,38 R**. Las 4 ampliaciones
  suman +0,02 $.
- **Consecuencia financiera:** paga horquilla y comisión taker para anular su propia toma de beneficios; aumenta el
  riesgo en el peor momento (tras un movimiento a favor, cuando el retroceso es más probable en estrategias de 1 h).
- **Corrección:** desactivar `piramide` (no tiene evidencia) o exigir avance adicional ≥ 1 R desde el TP1 y no permitirlo
  si hubo parcial.
- **Prueba:** operación con parcial cobrado → `ampliable()` debe devolver motivo.

### Q-06 · Métrica de deslizamiento de stop calculada con el precio medio de todas las salidas · P2 · [C][D]
- **Dónde:** `gestor.py:1506` → `riesgo.py:237-246`.
- **Problema:** `peor_que_trigger_pct` usa `precio_medio_salida` (TP1 + stop). Con un TP1 previo, el promedio queda
  «mejor que el trigger» aunque el stop llenara mucho peor.
- **Evidencia:** SKY: stop lleno a 0,040015 con trigger 0,039238 (−2,0 %); registrado `peor_que_trigger_pct: 0,0`.
- **Consecuencia:** la calibración del deslizamiento de stops (pendiente n.º 5 del proyecto) se haría con datos falsos.
- **Corrección:** calcular con los fills de rol `stop` únicamente.

### A-01 · Memoria por vecinos sin validación · P2 · [C][D]
- **Dónde:** `aprendizaje.py:32-50` (escalas), `215-256` (`valorar`).
- **Problema:** escalas, penalizaciones, 20 vecinos, distancia 3, vida media 21 días y umbrales elegidos a mano; mezcla
  casos reales, sombras sesgadas (Q-07) y casos de laboratorio. Nunca se ha validado fuera de muestra.
- **Evidencia:** vía «memoria» 7/7 operaciones perdedoras (−0,82 R) desde la puesta a cero.
- **Corrección:** eliminarla como filtro de decisión o validarla en el laboratorio como cualquier estrategia.

### C-01 · El cerebro no supera y su mejora depende de la historia sustituida · P1 · [D]
- **Dónde:** `cerebro.py`, `estrategia_elegida.json → cerebro.4h`.
- **Evidencia:** «con todo» +0,090 R (t 2,75; listón 2,91; t por días 1,32); «solo Hyperliquid» −0,045 R frente a
  −0,069 R de «todas» en el mismo subperiodo (mejora +0,02 R, nula); cartera con límites reales −1,65 % (caída 28,6 %).
- **Consecuencia:** se opera en simulado con un modelo que no supera (`exploracion_simulado: ["4h"]`); 16 de las 30
  operaciones vienen de esa vía.
- **Corrección:** ver 07.

### C-02 · Regularización nominal · P3 · [C]
- `LAMBDA = 10` con ~6 000 filas (diagonal de X'X ≈ 6 000) es prácticamente OLS. No es un fallo, pero el comentario
  «para no sobreajustar» no describe lo que hace.

### C-03 · Rasgos externos dependen de Binance/Bybit accesibles · P2 · [C][X]
- Sin datos externos el cerebro se abstiene. Desde el servidor de esta auditoría Binance responde 451 («no disponible
  por motivos legales») y Bybit 403: en un VPS en una jurisdicción bloqueada el bot no operaría nada. Hetzner (UE) hoy sí accede, pero es una dependencia operativa de
  terceros sin cuenta ni SLA.

### W-01..W-04, IA-01..IA-03, S-01..S-04
Detallados en 06, 07 y 04 respectivamente.

### SEG-01 · Panel por túnel sin contraseña · P1 · [C]
- **Dónde:** `config.json → panel.tunel_sin_clave: true`, `panel.py:968-999`.
- **Verificado:** la escritura remota está bloqueada (`puede_mandar` exige equipo local o contraseña; también
  `/api/incidente`). La lectura es pública para quien conozca la URL: saldo, posiciones, estrategias, ballenas seguidas.
- **Consecuencia:** fuga de información operativa; con el repositorio público desde el 24/11, cualquiera puede
  correlacionar el panel con el código. Con dinero real sería inaceptable.
- **Corrección:** `PANEL_PASSWORD` + Cloudflare Access, y retirar `tunel_sin_clave` del código.

### OPS-01 · El instalador del VPS no fija las dependencias indirectas · P3 · [C]
- **Dónde:** `despliegue/instalar_vps.sh:137` instala `requirements.txt` (3 paquetes), no `requirements-bloqueado.txt`.
- **Consecuencia:** el servidor puede resolver versiones distintas de `eth_account`, `pydantic`, etc. a las probadas.
- **Corrección:** instalar el archivo bloqueado y pasar las pruebas antes de arrancar (la guía ya lo pide para las
  pruebas).

### OPS-02 · Borrado automático de datos propios · P2 · [C]
- **Dónde:** `mercado.py:106-117` (`_limpiar`, 120 días). Ver W-03.

### OPS-03 · Laboratorio no reproducible desde el repositorio · P2 · [C]
- `datos_backtest/` (738 MB) está en `.gitignore`; Binance/Bybit pueden dejar de servir la historia o revisarla. El
  `manifiesto_datos.py` detecta cambios pero no conserva los datos.
- **Corrección:** archivar en R2/S3 los datos exactos de cada ejecución (hash ya calculado) o publicar el paquete.

### Análisis estático
- `ruff`: `bot.py:75` import sin usar (`dimensionar`), `feed.py:35` (`timezone`), `validacion.py:330` variable sin usar.
  17 `try/except/pass` silenciosos (S110), la mayoría en caminos de telemetría; los de `contexto_externo.py:48,69,100`
  ocultan fallos de lectura de funding externo (que después hacen abstenerse al cerebro sin causa visible).
- `bandit`: sin hallazgos reales (SHA1 como clave de caché).
- Complejidad: `bot.py` 2 389 líneas y 94 funciones; `procesar_candidatas` ~245 líneas. Mantenibilidad baja; cada
  cambio reinicia la evidencia (huella), lo que **desincentiva corregir** y favorece añadir capas laterales.
