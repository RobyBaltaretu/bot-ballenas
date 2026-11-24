# 04 — Auditoría de estrategias

Fuentes de evidencia por estrategia (de más a menos fiable):
1. **Laboratorio del bot** (`estrategia_elegida.json`, `lab-20261122T030003Z`): walk-forward 5 tramos (12/2022–12/2025),
   holdout 12/2025–11/2026, parámetros elegidos solo con el pasado. Historia de Hyperliquid ampliada con Binance/Bybit.
2. **Backtest independiente** (`experimentos/backtest_independiente.py`): Binance USDT-M 4 h, 20 monedas grandes,
   2021-01 → 2026-10, parámetros FIJOS del laboratorio, funciones de señal y salida del propio bot, funding real.
   Sesgo de supervivencia a favor de las estrategias (solo monedas que existen hoy).
3. **Paper** (ledger, desde la puesta a cero del 28/10): muestras de 2–11 operaciones por estrategia.
4. **Sombras re-simuladas con OHLC** (`experimentos/sesgo_sombras.py`): la sombra original está sesgada (+0,12 R/op).

## Resumen

| Estrategia | Estado config | Lab OOS (n, R, t) | Holdout lab | Backtest indep. (n, R, t) | Paper | Sombra OHLC | Decisión |
|---|---|---|---|---|---|---|---|
| `ruptura_4h` | activa | 1652, +0,006, 0,21 | 669, −0,004 | 2644, +0,011, 0,53 · **con régimen 2179, +0,051, 2,22** | 11, +0,39 | 29, +0,04 | **REDISEÑAR** (solo a favor del régimen; pre-registrar) |
| `momentum_4h` v2 | activa | 1155, **−0,107, −3,35** | 366, +0,180 | 1442, +0,021, 0,63 (neg. 2023–26) | 4, +1,35 | 57, +1,08 (4 fechas) | **DESACTIVAR** |
| `fuerza_4h` v2 | activa | 196, +0,088, 0,59 | 56, +0,146 | 455, +0,062, 0,68 | 0 | 1 | **VALIDAR ANTES DE DECIDIR** (prerregistro en curso); sin ventaja hoy |
| `retroceso_4h` | apagada | 1511, −0,096, −3,84 | 110, −0,167 | — | 2, −1,02 | — | **ELIMINAR** |
| `reversion_4h` | apagada | 126, −0,096, −1,46 | 11, −0,618 | — | 0 | 7, −0,91 | **ELIMINAR** |
| `funding_4h` | apagada | 127, −0,134, −1,53 | 39, −0,107 | — | 0 | 9, −0,50 | **ELIMINAR** |
| `ruptura_1h` | apagada | (lab 1 h retirado) | — | — | 5, −0,71 | 177, **−0,48** | **ELIMINAR** |
| `retroceso_1h` | apagada | ~700, −0,09, t ≈ −2,4 (doc.) | −0,11 | — | 4, −0,35 | 27, −0,04 | **ELIMINAR** |
| `funding_1h` | apagada | −0,11 (doc.) | — | — | 0 | 87, +0,08 (n.s.) | **ELIMINAR** (la «pista» de sombra era sesgo) |
| `reversion_1h`, `fuerza_1h` | apagadas | — | — | — | 2, −1,10 | 10, −0,63 / 4, +0,14 | **ELIMINAR** |
| `ballenas_1h` | activa (simulado) | 128, +0,010, 0,13 | — | — | 2, +1,93 | 109, −0,05 | **ELIMINAR como señal** (ver 06) |
| `liquidaciones_1h` | solo investigación | 82, −0,012, −0,14 | — | — | 0 | 134, −0,07 | **ELIMINAR** (o reformular con datos reales de liquidación) |
| `cartera_funding_4h` | activa (simulado) | no evaluada en el lab | — | — | 2 abiertas | — | **VALIDAR ANTES DE DECIDIR** (no medida como se opera) |
| Carry 2 patas (`carry/`) | en marcha (simulado) | estudio: ~12 %/año pruebas, ~7 % holdout | — | — | 0 cierres | — | **MANTENER** como línea principal de investigación |

«doc.» = cifra de `CLAUDE.md` no recalculada (el laboratorio de 1 h se retiró el 17/11 y no está en el JSON actual).

## Fichas

### ruptura (Donchian a favor de EMA)
- **Hipótesis:** las rupturas de máximos/mínimos de N velas con volatilidad creciente continúan (momentum de corto plazo).
- **Fundamento económico:** débil pero documentado (trend following en cripto; Liu y Tsyvinski, RFS 2021, hallan
  momentum de serie temporal diario/semanal).
- **Reglas:** `senales.py:137-150`. Stop 1,5–2,5 ATR. Salida TP1 1,5 R (50 %), final 4 R, trailing 1,5 R, 30 velas.
- **Evidencia:** sin ventaja en conjunto (lab t 0,21; independiente t 0,53). **Interacción con el régimen de BTC**: en
  el backtest independiente las rupturas a favor del régimen dan +0,051 R (t 2,22) y las contrarias −0,177 R (t −3,9).
  Los cortos rinden más que los largos (+0,099 frente a −0,047). El objetivo final (4 R) casi nunca se alcanza
  (106 de 2 644).
- **Debilidades:** entra después del movimiento (señal al cierre, entrada en la siguiente vela); 62 % de perdedoras;
  extremadamente dependiente del régimen.
- **Recomendación:** REDISEÑAR como hipótesis prerregistrada única: «ruptura_4h solo a favor del régimen de BTC», con
  muestra y criterio fijados antes de mirar, y listón corregido por el número de hipótesis vivas. No operar mientras tanto
  fuera de simulado.

### momentum (serie temporal, 2–4 semanas, v2 con trailing 1,5 R)
- **Hipótesis:** las monedas que suben/bajan con claridad durante semanas siguen.
- **Evidencia en contra:** lab OOS −0,107 R (t −3,35, n 1 155) con los parámetros de cada tramo; veteranas −0,115;
  solo Hyperliquid −0,104; estrés combinado −0,25. Independiente: positiva en 2021–2022 y negativa los cuatro años
  siguientes. Parámetros inestables entre tramos (lookback 180/umbral 6 → 63/3).
- **Evidencia a favor (usada por el desarrollador):** holdout +0,18 R y 4 operaciones en paper +1,35 R y 59 sombras.
  Las 63 son **todas cortos** y salen de **4 fechas de rebalanceo** durante una caída de BTC del 26 %: n efectivo ≈ 4.
- **Diagnóstico:** funciona solo en tendencias fuertes y prolongadas (régimen), y pierde en el resto; el periodo
  reciente es exactamente su régimen favorable. Mantenerla activa por el holdout y las sombras es **selección por el
  resultado más favorable**.
- **Recomendación:** DESACTIVAR. Si se quiere estudiar, como filtro de régimen de cartera, no como generador de entradas.

### fuerza (fuerza relativa, top-k, rebalanceo)
- **Hipótesis:** momentum transversal (Liu, Tsyvinski y Wu, JF 2022: el factor momentum de cripto es uno de los tres
  factores comunes).
- **Evidencia:** lab +0,088 (t 0,59); independiente +0,062 (t 0,68). En la literatura el factor es de cartera
  (quintiles largos-cortos, semanal) y aquí se opera 1–2 monedas con stop de 2,5 ATR: no es la misma apuesta.
- **Recomendación:** VALIDAR ANTES DE DECIDIR. El prerregistro (30 ops / 20 días) es correcto; al ritmo actual (~5/mes)
  tardará unos 6 meses. Considerar la versión de cartera neutral (largo top / corto bottom) en lugar de 1–2 apuestas.

### retroceso, reversión, funding (4 h y 1 h)
- Negativas en todas las fuentes y con holdout negativo. **ELIMINAR** del código activo (pueden quedar en el
  cementerio de investigación con su resultado). Mantenerlas «en sombra» consume peticiones y alimenta la memoria con
  datos que no se usan para nada útil.

### ballenas_1h → ver 06. liquidaciones_1h
- Inferencia de cascadas por caída de OI y movimiento de precio, corroborada por flujo agresivo. Lab −0,012 R (n 82),
  sombra OHLC −0,07 R (n 134). El bot no tiene datos directos de liquidaciones: solo las infiere (qué fuente directa
  existe en Hyperliquid queda como investigación pendiente, no verificada en esta auditoría). ELIMINAR.

### cartera_funding_4h (simulado)
- Largo en las 2 monedas de funding medio más bajo y corto en las 2 de más alto, semanal. El propio módulo reconoce que
  **no es lo que se estudió** (otro funding, otro universo, 2 patas en lugar de terciles, con stop). Sin evidencia del
  laboratorio. Dos patas abiertas hoy. VALIDAR ANTES DE DECIDIR (pasarla por el laboratorio tal como se opera) o
  eliminar.

### Carry de dos patas (corto perp + largo contado en Hyperliquid)
- **Fundamento económico sólido:** cobra la prima de financiación (BIS WP 1087, Schmeling, Schrimpf y Todorov:
  «crypto carry», a veces > 40 %/año, muy variable, y un carry alto predice caídas). Neutral al precio.
- **Riesgos:** liquidación del corto en subidas (cuentas separadas), base, funding que cambia de signo, comisiones de
  4 patas (~0,31 %), contraparte (USDC, Hyperliquid). Capacidad: con 200 $ y 50 % desplegado a ~10 %/año ≈ 10 $/año.
- **Recomendación:** MANTENER como línea principal, con su propia contabilidad y sin mezclarla con el bot direccional.
  Validar con la historia de funding de Hyperliquid (disponible por API desde 2023) en lugar de Binance.

## Estrategias que parecen rentables pero no lo son
1. **momentum_4h** (paper +1,35 R, sombras +1,1 R): régimen bajista, 4 fechas, OOS negativo.
2. **ruptura_4h en paper** (+0,39 R en 11): sus cortos ganan en la caída; sin régimen, cero en lab e independiente.
3. **funding_1h y retroceso_1h en sombra**: el positivo desaparece al simular con OHLC (Q-07).
4. **El total del paper** (+29,84 $): explicado por la caída del mercado (Q-02).

## Ninguna estrategia tiene ventaja estadística demostrada.
