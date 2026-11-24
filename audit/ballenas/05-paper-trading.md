# 05 · El simulador (paper trading)

## 5.1 Cómo funciona `papel.py` (MODELO 3, 19/11/2026)

| Aspecto | Modelo | Realismo |
|---|---|---|
| Precios | Mids, marca, oráculo, libro L2 y velas de 1 min **reales** de Hyperliquid | Alto |
| Frecuencia | Solo cuando el bot pregunta (`procesar()` en `user_state` y consultas): cada ciclo, unos 7–15 s (30–45 s al arrancar) | Medio. Entre consultas no se ve nada salvo por las velas de 1 min |
| Orden límite (ALO/GTC) | Se llena entera si hay contrapartida a su precio en el libro o un mínimo/máximo de vela de 1 min posterior la atraviesa | Medio-alto. No modela la cola ni el llenado parcial al tocar |
| IOC / mercado | Recorre los niveles reales (20 visibles + libro agregado `nSigFigs` 3/2) hasta el límite; el resto se cancela | Medio. El libro es una foto y no reacciona a la propia orden |
| Stops | Se activan por la **marca** (como Hyperliquid), con tolerancia del 10 % y taker | Alto |
| Comisiones | 0,015 % maker / 0,045 % taker (config) | Coincide con la tarifa base; no incluye descuentos por volumen ni por staking |
| Funding | Cada hora con la tasa real sobre el nocional al oráculo | Alto |
| Latencia | No se modela | Bajo |
| Liquidación | Estimada (fórmula de margen aislado) | Medio |
| Rechazos | Nocional < 10 $, ALO que cruzaría, reduce-only inválido, CLOID duplicado | Alto |

**[RIESGO]** Si el bot se para, el simulador se para: los stops simulados no se ejecutan. En real el stop vive en el
exchange. Con la máquina en casa y cortes de red frecuentes (ver 07), esto pasa a menudo.

**[HECHO]** Deslizamiento de entrada en las 22 operaciones posteriores a la puesta a cero: mediana +0,003 %, media −0,041 %
(negativo = mejor que la referencia). El MODELO 3 debería dejarlo algo más neutro. Aún no hay datos para comprobarlo.

## 5.2 Paridad con real

| Elemento | ¿Igual? | Diferencia |
|---|---|---|
| Señales, rasgos, cerebro | Sí | El mismo código (`motor`, `cerebro_vivo`) |
| Motor de riesgo y tamaño | Sí (fórmulas) | En real se aplican además los límites del piloto (`limites_efectivos`) |
| Máquina de estados de órdenes | Sí | Mismo `Ejecutor` y mismo `gestor`; `papel` imita el contrato del SDK |
| **Qué se opera** | **No** | Exploración del cerebro, exploración amplia, cartera de funding, ballenas en simulado y ampliación **solo existen en simulado**. En real, solo lo promovido (hoy, nada) |
| Comisiones | Casi | En real se leen de la cuenta |
| Liquidación | No | Estimada en simulado; real en real |
| Riesgo desconocido | No | `politica_riesgo_desconocido: bloquear` solo en real |

**Conclusión [HECHO]:** el simulado prueba bien la **mecánica** (órdenes, stops, conciliación, contabilidad). **No** es un
ensayo de lo que haría el bot en real: en real no operaría nada (no hay promociones), y en simulado opera sobre todo por
vías que en real no existen.

## 5.3 Operaciones tras la puesta a cero (28/10 22:44 UTC → 19/11)

Datos del ledger. «Cerebro» = predicción en R; «expl» = modelo sin aprobar en exploración; «—» = 1 h, el cerebro se
abstiene y entra por exploración amplia.

| Apertura | Moneda | Lado | Estrategia | Factor | Entrada → salida | Causa | R neto | Neto $ | Cerebro |
|---|---|---|---|---|---|---|---|---|---|
| 29/10 04:01 | SOL | S | momentum_4h | 0,25 | 99,53 → 95,47 | tiempo (164 h) | +0,83 | +0,82 | 0,37 expl |
| 29/10 16:01 | HYPE | L | ruptura_4h | 0,5 | 94,41 → 88,11 | stop | −1,00 | −2,17 | 0,06 expl |
| 30/10 00:02 | TRX | L | ruptura_4h | 0,5 | 0,3545 → 0,3452 | stop | −0,99 | −1,90 | 0,81 expl |
| 30/10 04:02 | CRV | S | ruptura_4h | 0,5 | 0,2765 → 0,2546 | tiempo (120 h) | +0,68 | +1,49 | 0,34 expl |
| 31/10 08:01 | TRX | S | ruptura_4h | 0,25 | 0,3221 → 0,3219 | sin pérdidas | −0,03 | −0,03 | 0,69 expl |
| 03/11 16:01 | LIT | L | retroceso_4h | 0,25 | 3,422 → 3,124 | stop | −1,00 | −0,90 | 0,10 expl |
| 03/11 20:01 | XMR | L | ruptura_1h | 0,25 | 631,1 → 630,8 | sin pérdidas | −0,07 | −0,07 | — |
| 03/11 22:00 | PUMP | L | ruptura_1h | 0,25 | 0,004398 → 0,004197 | stop | −1,00 | −1,10 | — |
| 04/11 04:10 | ENA | S | retroceso_4h | 1 | 0,1714 → 0,1843 | stop | −1,00 | −4,34 | 0,09 expl |
| 04/11 08:01 | WLD | L | ruptura_1h | 0,25 | 0,3929 → 0,3694 | stop | −1,40 | −1,46 | — |
| 04/11 08:02 | UNI | L | ruptura_1h | 0,25 | 7,483 → 7,487 | sin pérdidas | −0,02 | −0,02 | — |
| 04/11 11:01 | ZEC | L | ruptura_1h | 0,25 | 1312 → 1244 | stop | −1,10 | −0,70 | — |
| 05/11 01:02 | PAXG | L | fuerza_1h | 0,08 | 4085 → 4027 | stop | −1,10 | −0,31 | — |
| 05/11 04:04 | AAVE | S | momentum_4h | 0,5 | 132,2 → 120,6 | tiempo (164 h) | +1,10 | +3,24 | 0,11 expl |
| 05/11 16:04 | FARTCOIN | S | ruptura_4h | 0,5 | 0,1124 → 0,1145 | tiempo (120 h) | −0,19 | −0,58 | 0,28 expl |
| 05/11 16:04 | AERO | S | ruptura_4h | 0,5 | 0,5906 → 0,5463 | tiempo (120 h) | +0,81 | +2,53 | 0,18 expl |
| 06/11 08:02 | XRP | S | ruptura_4h | 0,38 | 1,187 → 1,072 | tiempo (120 h) | +1,70 | +3,90 | 0,20 expl |
| 12/11 00:03 | kPEPE | S | ruptura_4h | 0,5 | 0,004538 → 0,003815 | tiempo (120 h) | +1,40 | +4,46 | 0,25 expl |
| 12/11 00:03 | ARB | S | ruptura_4h | 0,5 | 0,1523 → 0,1304 | tiempo (120 h) | +1,50 | +4,79 | 0,06 expl |
| 12/11 01:02 | ETHFI | L | fuerza_1h | 0,17 | 0,6366 → 0,6082 | stop | −1,10 | −1,12 | — |
| 12/11 04:04 | ENA | S | momentum_4h | 1 | 0,144 → 0,1119 | tiempo (164 h) | +2,00 | +12,80 | 0,09 expl |
| 12/11 04:04 | UNI | S | momentum_4h | 1 | 6,235 → 5,197 | tiempo (164 h) | +1,50 | +9,88 | 0,11 expl |

Además: CASHCAT (`fuerza_1h`, 12/11) se cerró como «entrada sin ejecutar» (0 $). Abiertas a la fecha de esta auditoría:
PAXG y BNB (cortos, exploración amplia).

## Clasificación de las pérdidas (con los datos disponibles)

- **Estratégicas [HECHO, causa probable]:** los **10 largos perdieron o quedaron a cero**. Siete fueron stops, en un mercado
  bajista según el régimen de BTC. Desde el 13/11 el filtro de régimen bloquea los largos contra la tendencia de BTC; no
  hay largos posteriores con los que medirlo.
- **De ejecución:** no se identificó ninguna. Los stops llenaron cerca del trigger (R de −0,99 a −1,10; el −1,40 de WLD
  incluye deslizamiento y comisiones).
- **De riesgo:** la mayor pérdida fue ENA (`retroceso_4h`, factor 1: −4,34 $ = −1 R). El tamaño fue correcto; la señal no
  funcionó.
- **De simulación:** no se puede afirmar ninguna. El MODELO 3 corrige un optimismo del modelo anterior en entradas límite
  (ver 06).
