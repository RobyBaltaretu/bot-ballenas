# 09 — Validación cuantitativa y rentabilidad

Todas las cifras son **observadas** salvo que se indique «proyección». Fuente de cada una entre corchetes.

## 1. Auditoría del sistema de backtesting (laboratorio)

| Riesgo | Situación en el código | Valoración |
|---|---|---|
| Look-ahead | Señales solo con velas cerradas; entrada en la apertura de la vela siguiente; `tests/test_lookahead.py` con control positivo | ✔ Bien |
| Fugas entre tramos | Purga + embargo de 24 velas; la operación debe abrir y cerrar dentro del tramo | ✔ Bien |
| Selección de parámetros | Por tramo, solo con el pasado (`laboratorio.py:401-415`) | ✔ Bien |
| Holdout | De un solo uso, sellado con < 10 operaciones frescas | ✔ Bien; hoy 0 frescas en todas |
| Pruebas múltiples | Bonferroni sobre 27 familias (desde 19/11; antes 1 098 variantes) | ⚠ Razonable para el lab (cada familia es un procedimiento WF); **laxo para investigación**, donde ideas con distintos filtros/salidas se agrupan en la misma familia |
| Supervivencia | Universo de monedas que existen hoy; «universo en el tiempo» por volumen; aviso propio | ⚠ Mitigado, no resuelto |
| Historia sustituida | 6 años de Binance/Bybit pegados a Hyperliquid | ⚠ Diferencias de funding, base y microestructura; el cerebro solo mejora donde hay historia externa (07) |
| Costes | Comisión tomadora, deslizamiento 0,02 % + 5 % del ATR, funding real, estrés ×2/×3 | ✔ Prudente |
| Intravela | Stop primero si se tocan stop y objetivo en la misma vela | ✔ Conservador |
| Objetivos | Lleno al tocar | ⚠ Algo optimista (T-06) |
| Trailing | Por vela, distinto del vivo | ⚠ T-05 |
| Ejecución parcial / cola | No modelada (entrada a mercado) | Aceptable para 4 h |
| Reproducibilidad | Caché fuera del repo | ⚠ OPS-03 |
| Deflated Sharpe / PBO | No implementados | Recomendado (14) |

**Veredicto del laboratorio:** metodológicamente es de lo mejor del proyecto y sus resultados son coherentes con mi
backtest independiente. Su conclusión —ninguna estrategia supera— es **correcta**. El problema no es el laboratorio,
sino que **sus conclusiones no gobiernan lo que se opera** (momentum activo con t −3,35; exploración de todo).

## 2. Resultados de paper (desde la puesta a cero, 28/10 → 23/11) [forense_ledger.py]

| Métrica | Valor | IC / comentario |
|---|---|---|
| Operaciones cerradas con R | 30 | + 1 huérfana sin R (kPEPE) |
| PnL bruto / comisiones / funding / neto | +30,52 $ / 0,68 $ / 0,00 $ / **+29,84 $** | comisiones 2 % del bruto |
| R neto medio | **+0,145** | IC95 bootstrap **[−0,27; +0,56]**; t 0,67 |
| Mediana | −0,05 R | la mitad de las operaciones pierde |
| Ganadoras | 43 % | ganancia media +1,38 R; pérdida media −0,80 R; payoff 1,73 |
| Profit factor (en R) | 1,32 | |
| Caída máxima | 11,25 $ (7,45 R) | |
| Sin las 2 mejores | +7,16 $ | concentración extrema |
| Racha perdedora máxima | 5 | |
| Cortos / largos | +0,834 R (17) / −0,756 R (13) | |
| Exceso frente al universo en el mismo lado | **+0,40 %** por operación (t 0,53; IC95 [−1,0; +1,9]) | 14/29 positivas, p = 0,64 |
| BTC en el periodo | −26,5 % (81 253 → 59 753) | |
| Deslizamiento de entrada | media 0,03 %, máx. 1,02 % | 20 entradas creadoras, 15 tomadoras |

**Curva de valor** (`estado.json → historial_saldo`, recortada a 3 000 puntos: solo 13/11 → 24/11, hallazgo T-13):
+12,7 % en 10,9 días frente a BTC −13,4 % en la misma ventana; caída máxima 4,2 %; VaR 95 % diario 2,2 %. Cualquier
Sharpe anualizado sobre 11 días (sale 5,6) **no tiene significado** y no se usa.

## 3. Degradación entre fuentes

| Fuente | R medio | Comentario |
|---|---|---|
| Lab OOS, todas las candidatas 4 h | −0,057 | base honesta |
| Lab OOS, cerebro con todo | +0,090 | no supera |
| Paper (mezcla de vías, régimen bajista) | +0,145 | beta |
| Sombras originales | +0,056 | sesgadas +0,12 |
| Sombras re-simuladas OHLC | −0,068 | coherente con el lab |

## 4. Benchmarks [backtest_independiente.py, Binance 2021–2026, sin apalancamiento]

| Referencia | CAGR | Caída máx. | Sharpe |
|---|---|---|---|
| BTC comprar y mantener | 18,1 % | 76,7 % | 0,58 |
| **BTC largo si cierre > EMA200 (4 h), fuera si no** | **23,3 %** | **43,7 %** | **0,75** |
| BTC largo/corto según EMA200 | 6,5 % | 57,1 % | 0,39 |
| Estrategias del bot (1 % por operación, sin tope de posiciones; aproximación) | −4,4 % a +5,0 % | 34–90 % | 0,12–0,36 |
| Permanecer fuera | 0 % | 0 % | — |

Una regla de una línea sobre BTC supera a todo el sistema en rentabilidad ajustada al riesgo en el periodo histórico
probado (con la salvedad de que BTC es, por construcción, un superviviente).

## 5. Suficiencia de la muestra (proyección)

Con la desviación típica observada (1,19 R por operación):

| Ventaja real | n para t = 2 | n para t = 3 | Tiempo al ritmo actual (~1,15 ops/día) |
|---|---|---|---|
| +0,05 R | 2 266 | 5 099 | 5–12 años |
| +0,10 R | 567 | 1 275 | 1,4–3 años |
| +0,20 R | 142 | 319 | 4–9 meses |

**El paper trading no puede, por sí solo, demostrar una ventaja realista en un plazo útil.** La validación tiene que
venir del laboratorio (miles de operaciones históricas) y el paper solo debe **confirmar que no hay degradación**.

## 6. Nivel de confianza
- **Rentabilidad demostrada:** ninguna.
- **Resultados de paper:** fiables como contabilidad (reconstruidos al céntimo), **no** como evidencia de ventaja.
- **Resultados del laboratorio:** fiables como evidencia negativa; los positivos aislados (holdout de momentum,
  cerebro) no lo son.
