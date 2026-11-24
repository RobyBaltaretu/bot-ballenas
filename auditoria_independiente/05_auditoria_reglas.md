# 05 — Auditoría de reglas y validaciones

## 1. Método y límites

- **Ablación natural** con las 651 sombras cerradas desde la puesta a cero, re-simuladas con OHLC de 1 h y costes
  realistas (`experimentos/sesgo_sombras.py`): para cada regla de descarte se mide cómo habrían acabado las operaciones
  que bloqueó. Una regla de filtro «acierta» si lo bloqueado sale negativo.
- **Ablación histórica** del filtro de régimen con el backtest independiente (2021–2026).
- **Pendiente (no ejecutado):** ablación regla a regla dentro del laboratorio del bot (exige su caché de 738 MB y gasta
  holdout). Plan en 14.
- Se separan **filtros de estrategia** (deben ganarse su sitio con datos) de **controles de seguridad** (se mantienen
  aunque cuesten beneficio histórico).

## 2. Resultado de la ablación natural (sombras desde 28/10, OHLC con costes)

| Regla que descartó | n | Sombra original (R) | OHLC realista (R, t) | Lectura |
|---|---|---|---|---|
| Estrategia apagada / solo investigación | 344 | +0,075 | −0,069 (−1,3) | Bien apagadas |
| Cerebro se abstiene (sin modelo de 1 h) | 101 | −0,324 | −0,442 (−5,4) | Acierta (eran 1 h negativas) |
| Tamaño mínimo excede riesgo | 63 | +0,198 | +0,165 (1,1) | Neutra; control de seguridad |
| Sin hueco / demasiado riesgo / correlación | 34 | +1,088 | +0,946 (4,6) | Bloqueó cortos de momentum y ruptura en la caída: **es concentración direccional**; mantener |
| Contra el régimen de BTC | 33 | −0,065 | **−0,404 (−2,8)** | Acierta |
| Cerebro en exploración: descarte posterior | 21 | +0,348 | +0,405 (3,2) | Muestra pequeña; mismo efecto beta |
| Funding en contra | 14 | −0,248 | −0,262 (−1,0) | Acierta (n pequeño) |
| Volatilidad extrema (> 4 ATR) | 12 | −0,236 | −0,297 (−1,1) | Acierta (n pequeño) |
| Liquidez / horquilla / impacto | 6 | −0,548 | −0,683 (−3,2) | Acierta; control de ejecución |
| Entradas bloqueadas (globales) | 3 | −0,683 | −0,717 | — |
| Stop fuera de límites (> 12 %) | 20 | — | — (n=1 cada motivo) | Control de seguridad |

Advertencia: periodo de 4 semanas con un único régimen (bajista). Ninguna de estas cifras generaliza.

## 3. Inventario de reglas y matriz de decisión

Tipo: **S** = seguridad / control · **E** = filtro de estrategia · **G** = gestión de tamaño.

| # | Regla (valor) | Dónde | Tipo | ¿Cumple su propósito? | Evidencia | Decisión |
|---|---|---|---|---|---|---|
| 1 | Stop entre 0,25 % y 12 % | bot.py:643, riesgo.py:130 | S | Sí | 20 descartes > 12 % | MANTENER |
| 2 | Persecución ≤ 0,3 R desde la señal | bot.py:648-650 | E | Sí | persecución real −0,47…+0,36 R | MANTENER |
| 3 | Horquilla ≤ 0,15 % | bot.py:659 | S | Sí | descartes −0,68 R | MANTENER |
| 4 | Costes ≤ 20 % del riesgo | riesgo.py:100-110 | S/E | Sí | evita stops cortos caros | MANTENER |
| 5 | Funding en contra ≤ 0,005 %/h | bot.py:670 | E | Probable | 14 casos −0,26 R | MANTENER; unificar definición (T-07) |
| 6 | Vela > 4 ATR = volatilidad extrema | bot.py:672-677 | E | Probable | 12 casos −0,30 R | MANTENER (validar en lab) |
| 7 | Veto de ballenas ≥ 150 k$ en contra | bot.py:678-682 | E | **No demostrado** | lab ballenas +0,01 R | ELIMINAR (06) |
| 8 | Cerebro: predicción > 0,05 R | cerebro_vivo.py | E | **No** (no supera) | t 2,75 < 2,91; solo HL sin mejora | SUSTITUIR (07) |
| 9 | Exploración del cerebro en simulado | config `cerebro.exploracion_simulado` | — | Contamina la evidencia | 16/30 operaciones | ELIMINAR o separar contabilidad |
| 10 | Exploración amplia (0,5 %, 4 abiertas) | bot.py:898-904 | — | Contamina; opera lo negativo | 7 ops +0,57 R (ruido) | ELIMINAR o separar |
| 11 | Régimen de BTC (EMA200) | bot.py:872-878 | E | **Sí** en el periodo y en 2021–2026 para ruptura | −0,40 R bloqueado; ruptura +0,05 vs −0,18 | MANTENER; validar por estrategia |
| 12 | Memoria por vecinos (factor 0,5–1 / veto) | bot.py:905-928 | E | **No** | vía memoria 7/7 pérdidas | ELIMINAR |
| 13 | Relajación tras 24 h sin operar | bot.py:817, aprendizaje.py:249 | E | Contraproducente | — | ELIMINAR (T-04) |
| 14 | Promoción vigente para real | bot.py:929-934 | S | Sí | — | MANTENER |
| 15 | Bloqueos globales (pausa, datos > 120 s, degradado, conciliación, sin stop, liquidación, cuenta > 90 s, reloj > 10 s) | bot.py:602-632 | S | Sí | — | MANTENER |
| 16 | Pérdida diaria 6 % / semanal 12 % / caída 25 % | riesgo.py:495-513 | S | Sí | — | MANTENER (25 % es tarde para real) |
| 17 | 12 operaciones al día | riesgo.py:509 | S | Sí, pero se evalúa una vez por ciclo | — | MANTENER; recontar tras cada apertura |
| 18 | Pausa 120 min tras 4 pérdidas | gestor.py:1544-1550 | S/G | Neutro | cuenta también exploración de 10 $ | OPTIMIZAR (contar solo vías reales) |
| 19 | Enfriamiento 60 min por moneda | gestor.py:1522 | E | Sin evidencia | — | VALIDAR |
| 20 | Una operación por moneda | gestor.py:976-989 | S | Sí (Hyperliquid netea) | — | MANTENER |
| 21 | Riesgo 3 % por operación | config | G | **Excesivo** para una estrategia sin ventaja | — | REDISEÑAR: ≤ 0,5–1 % |
| 22 | Riesgo abierto 9 %, 6 posiciones, 4 del mismo lado | riesgo.py:373-411 | S | Sí | bloqueó concentración | MANTENER; bajar en real |
| 23 | Exposición mercado 100 % / bruta 250 % / neta 150 % / beta 200 % | riesgo.py | S | Demasiado laxos para no actuar casi nunca | — | OPTIMIZAR (neta ≤ 100 %, beta ≤ 100 %) |
| 24 | Correlación > 0,8 con una abierta | bot.py:690-704 | S | Sí (bloqueó 5 casos 0,82–0,96) | — | MANTENER |
| 25 | Salto conjunto ≤ 20 % por lado | riesgo.py:341-370 | S | Sí | — | MANTENER |
| 26 | Escenarios de tamaño (base / severo ×2 / límite 15 %) | riesgo.py:121-180 | S | Sí | — | MANTENER |
| 27 | Liquidación ≥ 1,5× distancia al stop; cierre si la liquidación llega antes | riesgo.py:166, gestor.py:381-426 | S | Sí | — | MANTENER |
| 28 | Profundidad ≥ 3× nocional, impacto ≤ 0,15 % | bot.py:960-976 | S | Sí | — | MANTENER |
| 29 | Factor de capital (caída 5/10/20 %, día −4 %, semana −8 %, objetivo +3 %, defensa) | estrategia.py:74-118 | G | Parcial | — | SIMPLIFICAR: quitar «objetivo diario» (reduce tras ganar sin base) |
| 30 | Vigilancia de degradación (×0,5) | vigilancia.py | G | Sí (solo reduce) | — | MANTENER |
| 31 | Duración máxima por estrategia / 336 h | gestor.py:1201-1212 | E | Sí; **es la salida que más gana** | Q-04 | MANTENER; estudiar salidas por tiempo |
| 32 | TP1 50 % a 1–1,5 R + sin pérdidas + trailing | gestor.py:1098-1226 | E | **No demostrado** | ruptura: objetivo final 4 % de las ops | VALIDAR en lab frente a «salida solo por tiempo + stop» |
| 33 | Piramidación | bot.py:1245-1310 | E | **No**; deshace el TP1 | Q-05 | ELIMINAR |
| 34 | Suelo de emergencia −50 % | riesgo.py:516-525 | S | Demasiado tarde | — | REDISEÑAR: −20 % en real |
| 35 | Techos duros del real (3 % / 9 % / 5× / 6 / −10 % día) | riesgo.py:532-533 | S | Existen, pero altos | — | REDISEÑAR: 1 % / 3 % / 2× / 3 / −3 % |

## 4. Reglas perjudiciales
- **#13 relajación tras inactividad**, **#33 piramidación**, **#12 memoria**, **#9-10 exploración** (para la calidad
  de la evidencia), **#21 riesgo 3 %** (para la supervivencia), **#29 objetivo diario** (reduce el tamaño tras ganar:
  convierte un sistema de esperanza cero en uno con menor recuperación tras rachas buenas sin motivo estadístico).

## 5. Reglas redundantes
- Correlación (#24) y exposición beta (#23) se solapan; «mismo lado» (#22) y salto conjunto (#25) también. No son
  contradictorias; conservar las más estrictas y simples (mismo lado + salto conjunto + correlación).
- Cerebro + memoria + vigilancia + factor de capital: cuatro capas que multiplican factores (0,17 × 0,5 × 0,5 × 0,75…)
  sin que ninguna esté validada: SIMPLIFICAR a una sola regla de tamaño (riesgo fijo × vigilancia).

## 6. Reglas nuevas propuestas
1. **Prueba de beta obligatoria**: cada resultado (lab, paper) se compara con «mismo lado en el universo equiponderado»
   en las mismas ventanas (como en Q-02). Si el exceso no es significativo, la evidencia no cuenta.
2. **Contabilidad separada por vía** que impida mezclar exploración con evidencia (ya existe `op["via"]`; hacerla
   obligatoria en promoción).
3. **Límite de evidencia por fecha**: en estrategias de rebalanceo, n efectivo = número de fechas de rebalanceo, no de
   operaciones.
4. **Stop de reconciliación en real**: si la diferencia entre el PnL de los fills y el `accountValue` supera X en 24 h,
   pausa (detecta errores de atribución).
5. **Kill switch por desviación**: si el R medio de las últimas 30 operaciones reales queda por debajo del límite
   inferior del IC del laboratorio, pausa automática (hoy vigilancia solo reduce).
