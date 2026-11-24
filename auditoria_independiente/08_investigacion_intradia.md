# 08 — Investigación de estrategias intradía

## 1. Restricciones que deciden la viabilidad

| Restricción | Valor real | Consecuencia |
|---|---|---|
| Coste de ida y vuelta tomador | 0,09 % comisión + horquilla 0,02–0,10 % + deslizamiento ≈ **0,12–0,20 %** | Con objetivos < 0,6 % el coste se come > 25 % del recorrido |
| Coste con entrada creadora (ALO) | 0,06 % + selección adversa (se llena cuando el precio va en contra) | Ahorro real menor de lo que parece |
| Latencia | Python, REST + websocket del SDK, ciclo 15 s, PC doméstico (VPS previsto) | Imposible competir en segundos (señales de libro pierden la mitad de su valor en ~5 s según un informe práctico de 2026; no revisado por pares) |
| Capital | 232 $ | Tamaño mínimo 10 $: muchas operaciones a 1–2 % de riesgo no caben; el impacto no importa |
| Límites por dirección en Hyperliquid | 1 petición por USDC negociado (+10 000) | Estrategias de muchas órdenes/cancelaciones agotarían el colchón |
| Datos | Velas, libro de 20 niveles, operaciones por websocket, funding, OI cada minuto (grabado por el bot desde 22/10) | Sin historia larga de libro ni de OI; sin historia de liquidaciones |

**Conclusión previa:** scalping, market making, arbitraje de latencia y señales de libro de orden de segundos
**no son viables** y no se recomiendan. El horizonte realista es **1 h – varios días**.

## 2. Fichas (ordenadas por prioridad)

| # | Estrategia | Hipótesis / fundamento | Evidencia | Datos | Horizonte | Coste/latencia | Viabilidad | Riesgo de sobreajuste | Prioridad |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Carry delta-neutral** (corto perp + largo contado HL) | Prima de financiación persistente por demanda apalancada de largos (BIS WP 1087) | Fuerte en la literatura; estudio propio ~12 %/año pruebas, ~7 % holdout | funding horario HL (API desde 2023), contado HL | días–semanas | 4 patas ≈ 0,31 %; latencia irrelevante | **Alta** (ya implementado en simulado) | Bajo (pocas reglas) | **P1** |
| 2 | **Ruptura 4 h solo a favor del régimen BTC** | Momentum de serie temporal condicionado a tendencia del mercado | Backtest independiente +0,051 R, t 2,22 (no pasa listón corregido) | velas 4 h | días | bajo frente a stops de 2,5 ATR | Alta (es código existente) | Medio (una pista entre muchas) | **P1** (prerregistrar) |
| 3 | **Tendencia de BTC/ETH (EMA o canal) como estrategia base** | Trend following en cripto (Rozario et al. 2020; Detzel et al. 2018; evidencia mixta) | Backtest propio: largo/fuera BTC Sharpe 0,75 frente a 0,58 comprar y mantener (2021–2026) | velas diarias/4 h | semanas | muy bajo | Alta | Bajo-medio | **P1 como referencia obligatoria** |
| 4 | **Momentum transversal de cartera** (largo top / corto bottom semanal, neutral) | Factor momentum de cripto (Liu, Tsyvinski y Wu, JF 2022) | Académica; `fuerza_4h` es una versión degradada (1–2 monedas) | velas diarias, 20–40 monedas | semana | rotación semanal; costes moderados | Media | Medio | P2 |
| 5 | **Factor de funding transversal** (largo funding bajo / corto alto) | Exceso de apalancamiento de un lado se corrige; carry relativo | Estudio B propio (no replicado aquí); `cartera_funding` no es lo medido | funding de todas las monedas | semana | moderado | Media | Medio-alto | P2 (medir tal como se opera) |
| 6 | **Reversión tras movimientos extremos con caída de OI** (liquidaciones) | Cascadas forzadas sobrepasan el precio justo | Lab −0,01 R; sombras −0,07 R | OI por minuto (solo desde 22/10), operaciones grandes | horas | moderado | Baja hoy (sin historia) | Alto | P3 (esperar 6–12 meses de datos sin borrarlos) |
| 7 | **Lead-lag BTC → altcoins** | Las alts reaccionan con retraso a BTC | Literatura de microestructura: el retraso es de segundos–minutos | velas de 1 min, operaciones | minutos | latencia crítica | **No viable** | Alto | Descartar |
| 8 | **Pairs / stat-arb** (p. ej. ETH/BTC, SOL/ETH) | Cointegración temporal | Débil y cambiante en cripto | velas 1 h | días | dos patas de costes | Media-baja | Alto | P3 |
| 9 | **VWAP / anchored VWAP reversión** | Reversión intradía a precio medio | Mayormente divulgación comercial, poca evidencia en cripto | operaciones | horas | costes altos frente a recorrido | Baja | Alto | Descartar por ahora |
| 10 | **Order-flow imbalance / CVD** | Desequilibrio de órdenes predice retornos a muy corto plazo | Académica para segundos (Binance Futures, 2025–2026) | libro y operaciones en tiempo real | segundos | latencia crítica | **No viable** | Alto | Descartar |
| 11 | **Sesiones / fin de semana / calendario macro** | Liquidez y volatilidad estacionales | Estudio macro propio: no mejora (p = 0,94) | velas + calendario | horas | — | Baja | Alto (muchas variantes) | Descartar como señal; usar solo como filtro de riesgo si se valida |

## 3. Plan de validación común (para cualquier ficha que se investigue)
1. Hipótesis escrita **antes** de mirar datos (como `preregistro.py`): regla, universo, parámetros, muestra mínima y
   criterio de éxito. Una sola variante.
2. Datos: historia de Hyperliquid cuando exista; Binance como validación cruzada, nunca sustituyendo.
3. Walk-forward purgado + holdout de un solo uso; t por días; bootstrap por bloques; **Deflated Sharpe Ratio** con el
   número real de pruebas del proyecto.
4. Referencia obligatoria: tendencia de BTC (ficha 3) y «mismo lado del universo» (Q-02). Si no las supera ajustando por
   exposición, se descarta.
5. Estrés: costes ×2, deslizamiento ×3, stops con hueco, funding ×3 (ya implementado en `validacion.escenarios_estres`).
6. Paper con la misma ejecución durante ≥ 30 operaciones y ≥ 20 fechas independientes, comparado con el IC del lab.

## 4. Criterios de abandono
- t por días < 1 en el walk-forward, o holdout fresco con R medio < 0, o no supera la referencia de tendencia de BTC.
- En paper, R medio por debajo del límite inferior del IC del laboratorio tras 30 operaciones.
