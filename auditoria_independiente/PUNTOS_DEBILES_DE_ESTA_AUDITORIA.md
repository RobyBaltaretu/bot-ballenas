# Puntos débiles de esta auditoría (para quien la revise)

Lista honesta de dónde puedo estar equivocado, qué supuestos hice y qué no comprobé. Un revisor debería empezar por
aquí.

## 1. Cobertura
- Solo el 36 % del código Python está leído línea a línea; el 28 % por secciones críticas y el 36 % solo con análisis
  estático (01). Los módulos «sin efecto» (según `promocion.ARCHIVOS_SIN_EFECTO`) no se leyeron a fondo: si alguno sí
  afecta a decisiones o a seguridad, se me ha escapado.
- No se revisaron las 69 pruebas ni el frontend (`panel_web/`) línea a línea.

## 2. Supuestos de los experimentos que pueden sesgar mis cifras
| Experimento | Supuesto | Cómo podría estar mal |
|---|---|---|
| `sesgo_sombras.py` | Salida y duración de cada sombra reconstruidas desde `estrategia_elegida.json` (4 h) o `senales.MODULOS` (1 h), no desde el plan exacto guardado (las sombras cerradas tienen `sim = null`) | Si la salida real de una sombra difería, parte del «sesgo» sería diferencia de reglas y no de muestreo |
| `sesgo_sombras.py` | Simulación desde la primera vela de 1 h que empieza después de la señal | Ignora el tramo entre la señal y la siguiente hora en punto |
| `sesgo_sombras.py` | Costes «realistas»: +0,05 % de entrada, comisión tomadora, 0,05 % en salidas a mercado | Es un supuesto; el desglose «mismos costes» (+0,074 R) es la cifra menos dependiente de él |
| `forense_ledger.py` | La vía de cada operación la clasifica mi función `via()` (heurística sobre el plan y el cerebro) | Coincide con las cifras por vía del propio bot, pero no es la función `ledger.via_decision` |
| `forense_ledger.py` | Referencia de mercado = media equiponderada de las 72 monedas con velas de 1 h archivadas que tienen datos en cada ventana | Otro universo (p. ej. ponderado por volumen) daría otra cifra; el sentido (beta) probablemente se mantiene |
| `forense_ledger.py` | MAE/MFE con velas de 1 h de operaciones, no de marca | Aproximado |
| `backtest_independiente.py` | Binance, 20 monedas grandes que existen hoy (supervivencia), sin cola ni latencia, funding de Binance | No es Hyperliquid; el sesgo de supervivencia favorece a las estrategias, así que el resultado negativo es, si acaso, optimista |
| `backtest_independiente.py` | Carteras «1 % por operación sin tope de posiciones», aproximación R → % | Las cifras de CAGR/caída de las carteras de estrategias son orientativas; las comparaciones por operación (R, t) no dependen de esto |
| `backtest_independiente.py` | Régimen = BTC frente a su EMA200 de 4 h en la vela de la señal | El bot usa la EMA200 del intervalo de cada estrategia (igual para 4 h) |

## 3. Afirmaciones que conviene verificar primero
1. **T-01** (stops simulados): afirmo una asimetría; **no** demuestro la dirección neta del sesgo.
2. **Q-07** (sombras +0,123 R/op): depende de los supuestos de la tabla anterior.
3. **Q-08** (momentum, n efectivo ≈ 4): cuento fechas de apertura agrupadas por hora; comprobar con los `trade_id`.
4. **C-01** (el cerebro solo mejora con historia de Binance): es una lectura de las cifras del laboratorio, no un
   experimento propio.
5. **IA-01**: el prompt invierte el significado; comprobar que los rasgos que recibe el escéptico son los del ledger
   (`funding_contra = s × funding`) y no otros.
6. **Q-05** (piramidación tras el TP1): un único caso documentado (SKY); revisar las otras 3 ampliaciones.
7. Las cifras de las estrategias de 1 h citadas desde `CLAUDE.md` (p. ej. retroceso_1h ~700 casos, t −2,4) **no** las
   recalculé: el JSON actual del laboratorio ya no contiene el intervalo de 1 h.
8. Las puntuaciones de 15 son juicio experto con criterios explícitos, no una medida.

## 4. Lo que no pude hacer
- Ejecutar el laboratorio completo (gasta holdout y reescribe `cerebro_modelo.json`; su caché no está en el repo).
- Acceder a `api.binance.com`, `fapi.binance.com` y `api.bybit.com` (bloqueo geográfico): no reproduje la historia
  ampliada ni el contexto externo.
- Probar nada contra la API real de órdenes (por diseño).
- Leer `bot.log` o el PC de producción.
