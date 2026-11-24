# 12 — Análisis forense de operaciones

Datos: 30 operaciones cerradas desde la puesta a cero (28/10 → 23/11), reconstruidas desde los eventos crudos del ledger
(`experimentos/forense_ledger.py`, resultado en `forense_ledger_resultado.json`), MAE/MFE con las velas de 1 h que el
propio bot archiva, y referencia de mercado = mismo lado en el universo equiponderado (20 monedas archivadas) en la
misma ventana.

## 1. Ranking de causas de pérdida por impacto económico (17 perdedoras, −19,61 $)

Una operación puede tener varias causas; las sumas se solapan.

| # | Causa | n | PnL | R | Tipo |
|---|---|---|---|---|---|
| 1 | **Largos en un mercado bajista** (BTC −26 %) | 12 | −12,26 $ | −10,9 | Evitable: 10 de ellos antes del filtro de régimen (13/11); los 2 posteriores (ZRO, PUMP, `retroceso_1h`) pasaron porque el régimen de 1 h (EMA200 de velas de 1 h) estaba alcista en un rebote |
| 2 | **Estrategias de 1 h negativas en el laboratorio** operadas igualmente (ruptura_1h, fuerza_1h, retroceso_1h) | 10 | −7,77 $ | −8,2 | Evitable: el laboratorio ya las daba por negativas |
| 3 | **Estrategia de 4 h negativa** (retroceso_4h) | 2 | −5,24 $ | −2,0 | Evitable (t −3,8 en el lab) |
| 4 | **Vía memoria** (sin modelo del cerebro, la memoria kNN decide) | 7 | −4,77 $ | −5,8 | Evitable: filtro sin validar |
| 5 | Stops con deslizamiento > 0,1 R (WLD −1,39 R; ZRO −1,07 R…) | 2 | −1,77 $ | −2,5 | Normal de ejecución (memecoins/altcoins finas) |
| 6 | Piramidación que deshizo el TP1 (SKY) | 1 | −0,47 $ | −0,38 | Evitable: regla mal diseñada (Q-05) |

**Lectura:** casi toda la pérdida es **evitable por proceso**, no «mala suerte»: se operaron estrategias y vías que el
propio laboratorio del bot ya daba por negativas o que nunca se validaron. Las pérdidas «normales» de una estrategia
válida (stops a −1 R con deslizamiento pequeño) son una parte menor.

## 2. Ganadoras: ¿buena decisión o azar?

| Moneda | Lado | Estrategia | PnL | R | Retorno del lado | Universo mismo lado | Exceso | Salida |
|---|---|---|---|---|---|---|---|---|
| ENA | corto | momentum_4h | +12,80 $ | +1,97 | +22,1 % | +11,4 % | +10,8 % | tiempo máximo 164 h |
| UNI | corto | momentum_4h | +9,88 $ | +1,52 | +17,0 % | +11,4 % | +5,7 % | tiempo máximo |
| ARB | corto | ruptura_4h | +4,79 $ | +1,46 | +13,5 % | +12,0 % | +1,6 % | tiempo máximo 120 h |
| kPEPE | corto | ruptura_4h | +4,46 $ | +1,35 | +14,5 % | +12,0 % | +2,5 % | tiempo máximo |
| XRP | corto | ruptura_4h | +3,90 $ | +1,73 | +11,1 % | +4,5 % | +6,6 % | tiempo máximo |
| AAVE | corto | momentum_4h | +3,24 $ | +1,06 | +9,6 % | +11,6 % | −2,0 % | tiempo máximo |

- 13 ganadoras (+49,45 $); 11 de ellas batieron al universo en su ventana. Pero en el total de 29 operaciones con
  referencia el exceso medio es +0,40 % (t 0,53) y solo 14 son positivas: las perdedoras quedaron por debajo del
  universo y compensan.
- **Más de la mitad del movimiento de las mejores era el del mercado** (ENA: 11,4 de 22,1 puntos).
- **Todas las ganadoras grandes salieron por tiempo máximo**, ninguna por objetivo: el beneficio viene de «estar corto
  durante la caída», no de la gestión de la salida. Con trailing a cada 15 s (T-05) varias habrían salido antes.

## 3. Errores recurrentes

| Error | Ejemplos | Corrección |
|---|---|---|
| Operar lo que el lab rechaza | ruptura_1h (5/5 perdedoras), retroceso_4h (2/2), fuerza_1h (2/2) | Solo operar estrategias con veredicto ≠ negativo; exploración separada |
| Filtros sin validar decidiendo | memoria 7/7 perdedoras | Eliminar |
| Concentración direccional | 4 cortos a la vez con correlaciones 0,82–0,96 | Límite de exposición neta y beta más estricto |
| Tamaños irrisorios por factores apilados | entradas de 10–40 $ de nocional (factor 0,17 × 0,5…) | Una sola regla de tamaño |
| Métrica de stop mal calculada | SKY `peor_que_trigger_pct = 0` con 2 % real | Q-06 |

## 4. Oportunidades descartadas (contrafactual con OHLC, solo información del momento)
- Lo descartado por el **régimen de BTC** habría perdido −0,40 R de media (n 33): el filtro acertó.
- Lo descartado por **«sin hueco / demasiado riesgo»** habría ganado +0,95 R (n 34): 25 eran cortos de momentum y
  ruptura en plena caída. No es una oportunidad perdida por un mal filtro, sino el límite de concentración haciendo su
  trabajo (más cortos = la misma apuesta).
- **Sombras de estrategias apagadas**: −0,07 R (n 344): estaban bien apagadas.

## 5. Patrones observados
1. El resultado del bot es una función casi lineal del movimiento de BTC en el periodo.
2. Las salidas por objetivo (TP final) prácticamente no ocurren; la salida que gana es la temporal.
3. Las operaciones de 1 h son peores que las de 4 h en todas las fuentes (costes relativos y ruido).
4. Los stops se ejecutan bien en monedas grandes (−1,02 a −1,05 R) y peor en altcoins finas (hasta −1,39 R).
5. Diferencia entre lo que el lab valida y lo que se opera: la causa principal de pérdidas evitables.
