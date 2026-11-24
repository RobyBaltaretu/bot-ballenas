# 06 · Resultados y validación cuantitativa

**Metodología:** solo lectura de `registro/ledger.jsonl` (`Ledger.operaciones()`) y de `papel.json`, origen «simulado».
- Los scripts de análisis quedaron en el directorio temporal de la sesión (`metricas.py`, `cuadre*.py`, `tabla_ops.py`).
- Sharpe y Sortino se calculan sobre el PnL cerrado diario / 232 $, anualizado ×√365.

## Cuadre ledger ↔ cuenta [HECHO]

- Cuenta simulada: efectivo 261,24 − 232 = **+29,24 $** (closedPnl 29,72 − comisiones 0,48 + funding 0,00).
- Ledger, operaciones abiertas tras la puesta a cero (28/10 22:44 UTC): **+29,25 $**. Cuadra (0,01 $).
- La cifra de «+19,15 $» del estudio anterior mezclaba 8 operaciones anteriores a la puesta a cero (−10,1 $). La cifra
  buena es **+29,25 $ en 22 operaciones**.

## Métricas (22 operaciones cerradas con resultado, 29/10 → 19/11, 21 días)

| Métrica | Valor |
|---|---|
| Neto / bruto | +29,25 $ / +29,72 $ (+12,6 % sobre 232 $) |
| Comisiones / funding | 0,47 $ / −0,00 $ (costes = 1,6 % del bruto) |
| Ganadoras | 40,9 % · ganancia media +4,88 $ · pérdida media −1,13 $ |
| Factor de beneficio | 2,99 |
| R medio por operación | **+0,062 R (t 0,26)**: no distinguible de cero |
| Caída máxima (PnL cerrado) | −11,25 $ (−4,8 %) |
| Sharpe / Sortino anualizados | 4,85 / 17,4. **No significativos**: 21 días, 22 operaciones y dos operaciones dominantes |
| Duración mediana | 56 h |
| Largos | n 10 · −9,73 $ · 0 % ganadoras · −0,88 R |
| Cortos | n 12 · +38,98 $ · 75 % ganadoras · +0,85 R (t 3,34) |

Por estrategia: momentum_4h n 4, **+26,75 $**, +1,35 R · ruptura_4h n 9, +12,51 $, +0,42 R · ruptura_1h n 5, −3,34 $ ·
retroceso_4h n 2, −5,24 $ · fuerza_1h n 2, −1,43 $.

## Por qué gana y por qué pierde [HECHO + HIPÓTESIS]

1. **Concentración:** dos operaciones (ENA y UNI cortos, `momentum_4h`, 12/11, factor 1) dan +22,7 $, el **78 %** del
   beneficio. Sin ellas, el resultado es +6,6 $ en 20 operaciones.
2. **Paradoja del factor de beneficio frente a la R:** el factor de beneficio es 2,99, pero la R media es +0,06.
   - Las ganadoras grandes fueron las de tamaño completo (factor 1).
   - Las pérdidas fueron en su mayoría de tamaño reducido (exploración, factor 0,25–0,5).
   - El beneficio en dólares sale de **cómo se repartió el tamaño**, no de una ventaja por operación.
3. **Régimen:** todo lo que ganó fue corto en un mercado bajista. Todos los largos perdieron. **[HIPÓTESIS]** El
   resultado depende del régimen, no de las estrategias: el laboratorio da momentum_4h t −3,2 en 1179 operaciones.
4. **Muestra dependiente:** el probador en vivo de momentum_4h muestra 44 casos (91 % ganadoras, +1,44 R). Pero
   `momentum` rebalancea cada 42 velas de 4 h (7 días, `senales.py:325`), así que esos 44 casos caen en ~3–4 fechas
   del mismo tramo bajista. **El tamaño efectivo de la muestra es de unas 3–4 observaciones, no 44.**

## 6.1 Validación estadística (laboratorio)

| Práctica | Estado | Evidencia |
|---|---|---|
| Walk-forward con purga y embargo | Sí | `validacion.en_tramo_purgado`, `cerebro.walk_forward` |
| Holdout sellado y acumulativo | Sí | `validacion.sellar_holdout`, `RegistroHoldout` |
| Pruebas múltiples | Sí: Bonferroni por **familias** desde el 19/11 (27 familias; t ≥ 3,02 con 60 operaciones; antes 1098 variantes, t ≥ 4,2) | `validacion.RegistroVariantes.efectivas` |
| t por días (dependencia intradía) | Sí | `validacion.veredicto` |
| Bootstrap por bloques | Sí | `validacion.bootstrap_bloques` |
| Meseta de parámetros | Sí | `validacion.meseta` |
| Estrés de costes | Sí (costes ×2, deslizamiento ×3, huecos en stops) | `validacion.escenarios_estres` |
| Línea base aleatoria | Sí | `validacion.linea_base_aleatoria` |
| Lookahead | Sí, con control positivo | `tests/test_lookahead.py` |
| Prerregistro | Sí (`fuerza_4h`, carry) | `preregistro.py` |
| Sesgo de supervivencia | **No resuelto**: universo con las monedas que existen hoy (declarado en `ejecucion.limitaciones`) | `laboratorio.py` |
| Historia antes de cotizar en Hyperliquid | Se sustituye por Binance/Bybit: **posible sesgo** a favor del cerebro «con todo» | Ídem |

**[RIESGO] Bajar el listón:** el cambio a familias es metodológicamente defendible: las variantes de una rejilla están
correlacionadas y Bonferroni sobre 1098 era demasiado estricto. Pero baja la barrera **después** de ver resultados (el
cerebro de 4 h tenía t 2,97). Para que no sea «data snooping», el holdout y la hipótesis deben seguir sellados y
prerregistrados (ver 09).

## 6.2 Costes

- **En vivo:** comisiones de 0,47 $ sobre 29,72 $ brutos (1,6 %). Entrar con ALO (maker) y tamaños pequeños hacen que los
  costes **no** sean el problema. **[HECHO]**
- **Laboratorio:** costes conservadores (taker en la salida, deslizamiento según ATR, `laboratorio.deslizamiento_vela`).
  Las estrategias son negativas **antes** del estrés de costes. Bajar comisiones (staking de HYPE, maker en las salidas)
  no convierte en positiva ninguna estrategia actual. **[HECHO]**
- **Punto de equilibrio:** con stops de 4–12 %, el coste de ida y vuelta (~0,1–0,2 %) supone 0,01–0,05 R por operación. Una
  estrategia necesita una R bruta > +0,05 para cubrirlo. Ninguna de las 13 la tiene fuera de muestra (la mejor,
  fuerza_4h, +0,117 con t 0,77).

## 6.3 Clasificación de estrategias

| Puesto | Estrategia | Evidencia | Recomendación |
|---|---|---|---|
| 1 | Carry de funding (dos patas) | Estructural; ~7 %/año en el holdout del estudio; 0 operaciones en vivo | Mantener en simulado hasta 30 cierres |
| 2 | Cerebro 4 h (con datos externos) | OOS +0,117 R (t 2,97), holdout +0,071 (n 338) | Validar con el laboratorio en curso y luego prerregistrar |
| 3 | fuerza_4h | OOS +0,117 (t 0,77), holdout +0,297 (n 53) | Prerregistrada: esperar a su muestra |
| — | ruptura_4h, momentum_4h, liquidaciones, ballenas | ~0 o negativas; el vivo depende del régimen | Solo sombra o exploración pequeña |
| — | retroceso, reversión, funding (4 h), todas las de 1 h | Negativas fuera de muestra | Sombra (ya están apagadas) |

**[HIPÓTESIS a validar fuera de muestra]:** quitar las estrategias negativas de la exploración (volver al filtro de t)
reduciría pérdidas simuladas sin perder información útil.
