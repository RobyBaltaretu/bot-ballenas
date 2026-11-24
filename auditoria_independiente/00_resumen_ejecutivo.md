# 00 — Resumen ejecutivo

**Auditoría independiente del bot de Hyperliquid** · commit `b8a9f8d` · 24/11/2026 · modo solo lectura, sin órdenes
reales, pruebas y experimentos en una copia del repositorio.

## Veredicto
**El bot no tiene una ventaja estadística demostrada y no está preparado para operar dinero real.** Su infraestructura
de ejecución y riesgo es de buena calidad; sus estrategias, su «cerebro», su analista de IA y su seguimiento de ballenas
no aportan valor medible. El beneficio simulado (+29,84 $ en 30 operaciones) se explica por la caída de BTC (−26,5 %)
durante el periodo, no por la selección de operaciones.

## Estado real
- **Modo simulado** con 232 $ ficticios, precios y libro reales de Hyperliquid. Nunca ha enviado una orden real ni se ha
  probado en testnet.
- **764 pruebas en verde.** Reconstruí el ledger de forma independiente y coincide al céntimo.
- **Ninguna estrategia ni el cerebro superan el laboratorio**; aun así se operan en simulado (momentum_4h, con t fuera de
  muestra −3,35, sigue activa; vías de «exploración» operan lo que el laboratorio da por negativo).

## Principales fortalezas (conservar)
1. Ejecución robusta: CLOID antes de enviar, nunca reenvía ante la duda, cancelación y stop **verificados**, congelación
   del mercado ante cualquier incoherencia, conciliación con la cuenta en cada ciclo.
2. Riesgo serio: tamaño por tres escenarios de pérdida, salto conjunto por lado, riesgo desconocido nunca cuenta como 0.
3. Laboratorio honesto: walk-forward purgado, holdout de un uso, estrés de costes, prueba de lookahead.
4. Contabilidad desde fills y funding, nunca desde el saldo; ledger reconstruible.
5. Barreras al dinero real: huella de código y configuración, aprobación humana, subcuenta y API wallet verificadas.

## Principales debilidades
1. **El laboratorio no gobierna lo que se opera**: la mayoría de las pérdidas evitables vienen de estrategias y vías que
   el propio laboratorio rechaza (12).
2. **Evidencia sesgada**: las «sombras» sobrestiman +0,123 R por operación (t 7,7); los «+1,12 R de momentum en 59
   casos» son 4 fechas de cortos durante una caída (n efectivo ≈ 4).
3. **Beta confundida con habilidad**: exceso frente al universo en el mismo lado +0,40 % por operación (t 0,53;
   14 de 29 positivas).
4. **Capas de decisión sin validar**: cerebro que no supera, memoria kNN (7/7 pérdidas), relajación por inactividad,
   piramidación que deshace su propio objetivo parcial.
5. **IA sin valor**: el LLM no decide nada útil, su «escéptico» vota siempre en contra y su prompt invierte el
   significado del funding.
6. **Ballenas sin señal**: elegidas por PnL del último mes; la señal no distingue abrir de cerrar; +0,01 R en el lab.
7. **Operación frágil para real**: PC doméstico, sin alertas externas, sin copias, panel público sin contraseña, límites
   del piloto real iguales a los del simulado (3 %/9 %/5×/−50 %).

## Riesgos críticos
- Pasar a real con las estrategias actuales: esperanza matemática nula o negativa con 3 % de riesgo y 5×.
- Código de órdenes no probado contra la API real.
- Caída del PC sin aviso durante un movimiento fuerte.

## Rentabilidad
- **Demostrada:** ninguna.
- **No demostrada:** paper +0,145 R (IC95 [−0,27; +0,56]); cerebro +0,090 R en el lab (no supera); holdout de momentum
  +0,18 R (régimen).
- **Backtest independiente** (Binance, 20 monedas, 2021–2026): momentum +0,02 R (negativa cada año desde 2023), ruptura
  +0,01 R (**+0,05 R, t 2,22 solo a favor del régimen de BTC**: la única pista), fuerza +0,06 R (t 0,68). Una regla de
  una línea —BTC largo si está por encima de su EMA200, fuera si no— tuvo mejor Sharpe (0,75) que todo el sistema.

## Madurez
Infraestructura: **alta** para un proyecto individual. Estrategia: **inexistente**. Operación: **prototipo doméstico**.

## Decisión
| Investigación | Backtesting | Paper | Real limitado | Real significativo | Real apalancado |
|---|---|---|---|---|---|
| GO | GO | GO condicionado (tras limpiar vías) | **NO-GO** | **NO-GO** | **NO-GO** |

## Qué hacer ahora (en orden)
1. Que solo opere lo que el laboratorio no rechaza; quitar exploración, memoria, relajación, piramidación y ballenas.
2. Medir bien: sombras con OHLC, referencia de mercado en todo informe, Deflated Sharpe.
3. Prerregistrar dos hipótesis: ruptura_4h + régimen y carry con funding de Hyperliquid.
4. VPS, alertas, copias, contraseña del panel, testnet.
5. Si nada supera: no operar dinero real.

Índice de documentos en `README.md`.
