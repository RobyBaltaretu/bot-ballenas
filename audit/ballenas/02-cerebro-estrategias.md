# 02 · El cerebro y las estrategias

## 1.1 Cómo se decide de verdad (`bot.procesar_candidatas`, `bot.py:805-1046`)

Para cada candidata, en este orden:

1. **Filtros de calidad** (`evaluar`, `bot.py:629`): horquilla ≤ 0,15 %, costes ≤ 20 % del riesgo, funding en contra
   ≤ 0,005 %/h, vela de 1 h ≤ 4 ATR y veto de ballenas (≥ 150 k$ en contra).
2. **Memoria (medición):** `memoria.valorar(..., medir=True)` sobre todas las candidatas (`bot.py:826`).
3. **Cerebro:** `cerebro_vivo.decidir` (`cerebro_vivo.py:111`).
   - Modelo ridge sobre 8 rasgos + indicador de estrategia (`cerebro.py`); abre si la predicción > 0,05 R.
   - Sin modelo, sin velas o sin datos externos: **se abstiene**.
   - En simulado, 4 h decide en «exploración» aunque su modelo sea `no_supera` (`exploracion_simulado`).
4. **Régimen de BTC:** solo a favor de la EMA 200 de BTC (`bot.py:851`).
5. **Exploración amplia:** si el cerebro rechaza o se abstiene, se opera igual con 0,5 % de riesgo (`bot.py:877`,
   `_puede_explorar`). Desde el 19/11 sin filtro de t.
6. **Memoria (aplica):** factor 0,5–1, o ×0,5 si está en contra en simulado; veto en real (desde el 19/11).
7. **Real:** promoción vigente y mercado del piloto (`bot.py:908`).
8. **Bloqueos, posición en la moneda, enfriamiento → `factor_capital` → `dimensionar` → `comprobar_agregados`**
   (ver 04).

### Ejemplo reconstruido (datos reales del ledger, sin inventar)

**UNI corto, `momentum_4h`, 12/11 04:04 UTC:**
- Señal de momentum (baja con claridad en 21 días). El cerebro predijo +0,11 R en modo exploración y la dejó entrar.
- Factor 1,0. Entrada 6,235, salida por tiempo máximo (164 h) a 5,197.
- Resultado: +1,5 R, +9,88 $. Fuente: eventos `senal`, `decision` y `cierre` del ledger (tabla completa en 05).

**TRX largo, `ruptura_4h`, 30/10:**
- El cerebro predijo +0,81 R (la predicción más alta del periodo). Factor 0,5.
- Salió por stop: −0,99 R. Es un ejemplo de que la predicción no ordena bien el resultado; con n = 22, no es concluyente.

## 1.2 Estrategias implementadas (`senales.py`)

Todas usan **velas cerradas** y el stop es k × ATR. Hay prueba de lookahead (`tests/test_lookahead.py`, 7 pruebas en
verde hoy) que incluye un control que demuestra que una fuga se detecta. **[HECHO]**

| Estrategia | Qué intenta explotar | Condición (código) | Riesgos de diseño |
|---|---|---|---|
| `ruptura` (`senales.py:137`) | Continuación tras romper un rango | Cierre > máximo de n velas, > EMA con pendiente, ATR ≥ vol_min × ATR medio | Entra tras el movimiento (posible agotamiento); falsas rupturas en rango |
| `retroceso` (`:153`) | Retroceso a la media en tendencia | EMA rápida > lenta, toca la rápida, vela a favor, eficiencia ≥ er_min | Tendencias que se giran; filtro de eficiencia retrasado |
| `reversion` (`:165`) | Exceso que revierte en rango | RSI extremo, desvío > k ATR de la EMA 50, eficiencia baja, vela de giro | Atrapar cuchillos; pocas señales |
| `funding` (`:179`) | Posicionamiento extremo (funding en percentil alto) + giro | Funding medio ≥ percentil y cruce de EMA rápida | El funding extremo puede persistir; dos condiciones raras |
| `fuerza` v2 (`:193`) | Momentum transversal (ranking entre monedas) | Top-k más fuertes o débiles cada rebalanceo | Ranking con pocas monedas; costes de rotación |
| `momentum` v2 (`:213`) | Momentum de serie temporal (3–4 semanas) | Movimiento ≥ umbral ATR y eficiencia mínima, en cada rebalanceo | Giros de régimen; muy dependiente de la tendencia de fondo |
| `ballenas_1h` (`motor.py:413`) | Seguir el flujo neto de cuentas grandes | ≥ flujo_min y mayoritario en 60 min | Observación, no intención; el ranking se rehace cada 12 h |
| `liquidaciones_1h` | Rebote tras cascada inferida (OI y precio) | Caída de OI + movimiento ≥ 2 ATR | Inferida, no confirmada |
| Cartera de funding | Factor transversal de funding | Lunes: largo en el funding más bajo, corto en el más alto | Distinta de lo medido en el estudio |
| Carry (`carry/`) | Prima de funding (estructural) | Funding anual ≥ 20 % | Riesgo de base y de giro del funding; dos patas |

**Parámetros:** son rejillas pequeñas (16–32 combinaciones por módulo) y hay control de **meseta** (`validacion.meseta`).
No veo sobreajuste por parámetros. El problema es la falta de ventaja, no el ajuste. **[HECHO]**

**Diseño frente a implementación:**
- `momentum` y `fuerza` dicen «mantener hasta el siguiente rebalanceo», pero el bot permite una sola operación por moneda
  y sale por `barras_max`. En vivo, la duración la fija el tiempo máximo (164 h), no el rebalanceo. Es coherente con el
  laboratorio (`SimSalida` usa la misma salida). **[HECHO]**

## Evidencia por estrategia (laboratorio del 15/11, fuera de muestra)

Datos de `estrategia_elegida.json`.

| Estrategia | n OOS | R medio | t | Holdout (n, R) | Vivo (operadas + sombra) | Clasificación |
|---|---|---|---|---|---|---|
| fuerza_4h | 180 | +0,117 | 0,77 | 53, +0,297 | 1 sombra | Prometedora, insuficientemente validada (prerregistrada) |
| ruptura_4h | 1543 | −0,003 | −0,13 | 602, −0,008 | 9 operadas tras la puesta a cero: +0,42 R | Sin evidencia de ventaja |
| momentum_4h | 1179 | −0,103 | −3,2 | 551, +0,002 | 44 casos, +1,44 R, 91 % (ver 06: muestra dependiente) | Sin evidencia de ventaja; el vivo es efecto de régimen |
| retroceso_4h | 472 | −0,105 | −2,42 | 135, −0,158 | 3 operadas, −1,02 R | Sin evidencia (negativa) |
| reversion_4h | 125 | −0,065 | −0,98 | 50, −0,261 | — | Sin evidencia |
| funding_4h | 161 | −0,129 | −1,69 | 159, −0,205 | 3 sombra, −0,59 | Sin evidencia (negativa) |
| ruptura_1h · retroceso_1h · funding_1h · fuerza_1h · reversion_1h | 105–6410 | −0,05 a −0,22 | −1,7 a −3,8 | negativos | Sombra mixta | Sin evidencia (negativas) |
| ballenas_1h | 123 | −0,12 | −1,53 | — | 122 sombra, +0,067 R | Sin evidencia |
| liquidaciones_1h | 68 | +0,09 | 0,88 | — | 118 sombra, +0,07 R | No evaluable (muestra pequeña, sin holdout) |
| **Cerebro 4 h con todo** | 748 | **+0,117** | **2,97** | 338, **+0,071** | En uso (exploración) | **Prometedora, insuficientemente validada** |
| Cerebro 4 h solo Hyperliquid | 623 | −0,059 | −1,45 | 185, −0,061 | — | Sin evidencia |
| Cerebro 1 h con todo | 1509 | −0,02 | −0,75 | 206, −0,291 | No decide | Sin evidencia |
| Carry realista | estudio | ~12 %/año (prueba) · ~7 % (holdout) | — | — | 0 operaciones | Fundamentado (estructural), sin validación en vivo |

**Lectura del cerebro de 4 h [HIPÓTESIS]:**
- La versión con datos de Binance/Bybit es positiva fuera de muestra y en el holdout; la versión solo con Hyperliquid es
  negativa. O los rasgos externos aportan información, o el resultado sale de cómo se reconstruye la historia antes de que
  cada moneda cotizara en Hyperliquid (precios de Binance como sustituto, limitación declarada por el propio laboratorio).
- Pesos (`cerebro_modelo.json`): `funding8h` +0,096, `impulso6` +0,059, `volatilidad` +0,052, `flujo6` +0,048. Indicadores
  por estrategia: `fuerza_4h` +0,106, `funding_4h` −0,177. Son coeficientes pequeños (R por desviación típica). Cualquier
  ventaja, si existe, es modesta.

## 1.3 Inteligencia operativa

| Capacidad | ¿Existe? | Evidencia |
|---|---|---|
| Reconocer tendencia | Sí: EMA, eficiencia, régimen de BTC (EMA 200) | `senales.py`, `bot.py:851` |
| Consolidación frente a movimiento direccional | Parcial: eficiencia (`er`) en retroceso, reversión y momentum | `senales.eficiencia_serie` |
| Volatilidad | Sí: ATR relativo, filtro de vela extrema, rasgo `volatilidad` | `bot.py:659`, `mercado_unificado.py:71` |
| Liquidez insuficiente | Sí: horquilla, impacto en el libro, volumen mínimo del universo | `bot.evaluar`, `riesgo.impacto_pct` |
| Movimientos anómalos | Parcial: vela > 4 ATR bloquea; liquidaciones inferidas solo informan | `bot.py:663` |
| Entradas contradictorias | Sí: una operación por moneda; correlación ≤ 0,8; máximo por lado | `gestor.abrir:932`, `bot.correlada` |
| Pararse cuando desaparece la ventaja | Parcial: `vigilancia` reduce o retira el permiso de real por estrategia; modo defensa | `vigilancia.py`, `estrategia.factor_capital` |

**IA / LLM:** `analista_ia.py` (Groq) solo escribe informes en `registro/analista/` (`analista_ia.py:141`). No toca órdenes,
configuración ni promoción (grep sin coincidencias). Sus ideas pasan por `investigacion.py` con el rigor del laboratorio.
Que **no** decida es lo correcto: no hay ninguna razón para meter un LLM en la decisión. **[HECHO]**

## 1.4 Pregunta central

**Ballenas no opera con una ventaja estadística demostrada [HECHO].**
- Las 13 estrategias individuales dan `no_supera`, la mayoría con R medio negativo fuera de muestra.
- Lo único con resultado positivo fuera de muestra y en el holdout es el **cerebro de 4 h con datos externos**
  (t 2,97, holdout +0,071 R). Está en el límite del listón nuevo (t ≥ 3,02 con 60 operaciones), sin confirmar y con un
  posible sesgo de datos.
- El laboratorio que recalcula con el listón nuevo seguía en marcha al cerrar esta auditoría.

El sistema de validación es serio: walk-forward con purga y embargo, holdout sellado acumulativo, corrección por pruebas
múltiples, meseta, lookahead y prerregistro. El problema es de **fondo** (no hay ventaja), no de método.

## Problemas de decisión detectados

- **[RIESGO] Demasiadas capas de decisión sin validar en cadena:** cerebro en exploración, exploración amplia, memoria,
  ballenas y ampliación. La evidencia en vivo queda mezclada y no se puede atribuir el resultado a una regla concreta.
- **[DEFECTO menor] Información de la decisión en el ledger:** `ledger.aplicar` (`ledger.py:220`) guarda en el resumen de
  la operación solo `aprobada`, `motivos` y `plan`. El bloque `cerebro` (predicción, modelo) solo está en el evento crudo.
  Se puede reconstruir, pero el panel y el CSV no lo muestran.
- **[HIPÓTESIS] Cambio de regla a mitad de partido:** la exploración ya no filtra estrategias con t ≤ −2. Se vuelven a operar
  estrategias claramente negativas en el laboratorio (p. ej. `momentum_4h`, t −3,2). Es una decisión de Roberto para medir
  en vivo, pero cuesta dinero simulado y su señal informativa es baja.
