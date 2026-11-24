# 06 — Auditoría de Hyperliquid y del seguimiento de ballenas

## 1. Integración con Hyperliquid (contrastada con la documentación oficial)

| Aspecto | Código | Documentación oficial (consultada 24/11/2026) | Estado |
|---|---|---|---|
| Comisiones nivel 0 | perp 0,045 % / 0,015 %; contado 0,07 % (carry) | perp 0,045 / 0,015; contado 0,070 / 0,040 | ✔ |
| TP/SL | trigger de mercado por marca, límite ±10 % | disparo por precio de marca; tolerancia 10 % en TP/SL de mercado | ✔ |
| Funding | horario, base 0,00125 %/h | 1/8 de la tasa de 8 h cada hora; interés 0,01 %/8 h; tope 4 %/h | ✔ |
| Marca | stop simulado con `markPx` (caché 10 s) | mediana de oráculo+EMA, mediana del libro y perps externos | ✔ (la marca es más suave que las operaciones: bien usada) |
| Límite por IP | limitador propio (peso por tipo) | 1 200 de peso/min por IP | ✔ conservador |
| Límite por dirección | no contemplado explícitamente | 1 petición por 1 USDC negociado + 10 000 iniciales; limitado: 1 cada 10 s; cancelaciones con margen extra | ⚠ Con 232 $ y trailing frecuente, el colchón de 10 000 dura, pero no se vigila (`userRateLimit`) |
| Subcuentas | `vault_address = subcuenta`, comprobación con `userRole` | subcuentas como usuarios separados; agente de la maestra | ✔ |
| `expiresAfter` | 15 s por envío | admitido por el SDK | ✔ (probado solo con exchanges falsos) |
| `scheduleCancel` | no usado (cancelaría stops) | — | Decisión razonable |
| WebSocket usuarios | máximo 10 suscripciones de usuario | límite por IP | ✔ |

**Nunca se ha probado contra la API real de órdenes** (ni en testnet). La red `testnet` está soportada en el código
(`bot.py:2181`) y es el paso obligatorio antes de cualquier dinero (ver 15).

## 2. Cómo se eligen las ballenas (`seleccion.py:117-131`)

1. Ranking público (`stats-data.hyperliquid.xyz/Mainnet/leaderboard`).
2. Filtro: valor de cuenta ≥ **100 000 $** (config; el defecto del código es 500 000), PnL histórico ≥ 500 000 $, PnL del
   mes > 0, día no muy negativo, ROI mensual ≤ 100 %, rotación mensual ≤ 60× (descarta creadores de mercado).
3. **Orden por PnL del último mes** (`candidatas.sort(reverse=True)`), 60 candidatas.
4. Perfil con sus últimos fills: ≤ 300 órdenes/día, ≥ 30 % de volumen en las monedas del bot, activa en 7 días.
5. Las 15 primeras + las «predictivas» del laboratorio.

**Crítica:**
- Ordenar por PnL del mes premia la **suerte reciente** y el **apalancamiento** (sin drawdown, sin volatilidad, sin
  consistencia, sin persistencia). Los casos públicos de grandes cuentas de Hyperliquid liquidadas tras rachas
  ganadoras (p. ej. James Wynn, ~100 M$ en mayo de 2025, según The Block y Arkham) ilustran la rotación del ranking:
  quien encabeza el ranking un mes puede ser el mayor perdedor el siguiente.
- Sesgo de supervivencia: solo cuentas que siguen arriba; las que quebraron desaparecen del ranking.
- No se observan coberturas en otros mercados (CEX, opciones): una «compra» en Hyperliquid puede ser la pata de una
  operación neutral.
- **«Predictivas» del laboratorio** (`laboratorio.py:872`): n ≥ 8, media ≥ 0,05 R y **t ≥ 1,0**, sin corrección por las
  40 ballenas probadas. Por azar pasarían ~6 de 40; se marcaron 9 (t entre 1,09 y 4,86). Es selección dentro de muestra.

## 3. Cómo se interpretan los movimientos (`ballenas.py`)

- El flujo se **infiere** por diferencia entre dos fotos de `clearinghouseState` (≈ cada 15 s por ballena).
- `senal()` (`ballenas.py:136-151`) suma el cambio neto en USD por ballena: **no distingue abrir de cerrar**.
  Cubrir un corto cuenta como «comprar» y reducir un largo como «vender». Una ballena que recoge beneficios de un corto
  tras una caída genera una señal LARGA en el peor momento.
- Liquidaciones, transferencias entre subcuentas y reequilibrios de cobertura aparecen como flujo.
- Hyperliquid ya ofrece el sentido explícito en los fills (`dir`: «Open Long», «Close Short», …): el bot lo recibe por
  websocket (`bot.py:527`) y solo lo usa para el panel, no para la señal.

## 4. Replicabilidad (latencia y coste)

| Paso | Retraso |
|---|---|
| Foto de posiciones | hasta ~15 s por ballena (más con el limitador) |
| Acumular ≥ 100 k$ en la ventana | hasta 60 min |
| Señal → orden | siguiente ciclo (≤ 15 s) + ALO 20 s + IOC |
| Tamaño | la ballena opera 100 k$–M$; el bot 10–300 $: impacto distinto, horizonte distinto (8 h de tope en el bot) |

Para cuando el bot entra, la ballena ya movió el precio (si su flujo es informativo) o está deshaciendo (si es
inventario). No hay ventaja de información tras ese retraso a menos que el efecto dure horas; los datos dicen que no.

## 5. Resultados

| Fuente | n | R medio | t | Nota |
|---|---|---|---|---|
| Laboratorio, todas las ballenas | 852 | −0,034 | −1,18 | |
| Laboratorio, solo «predictivas» (elegidas dentro de muestra) | 128 | +0,010 | 0,13 | aun con la selección a favor, cero |
| Sombras re-simuladas OHLC (desde 28/10) | 109 | −0,047 | −0,56 | la sombra original daba +0,108 |
| Paper | 2 | +1,93 | — | HYPE y ZEC cortos en plena caída: anécdota |
| Veto de ballenas | — | — | — | sin medición propia; hereda la falta de señal |

## 6. Alternativas evaluadas (cualitativamente; ninguna validada)

| Enfoque | Viabilidad | Opinión |
|---|---|---|
| Copia directa | Baja | Latencia, tamaño y horizonte distintos; sin ventaja medida |
| Copia selectiva (ranking ajustado por riesgo, persistencia ≥ 90 días) | Media | Necesita histórico de PnL por cuenta (no lo hay salvo grabándolo) |
| Consenso ponderado (neto del top-N independiente) | Media | Hipótesis razonable de **posicionamiento extremo** (contrario), no de copia |
| Ballenas como contexto (rasgo) | Media | Solo tras validarse como rasgo con la misma rigurosidad del laboratorio |
| Contrarian | Sin evidencia | No investigar sin una hipótesis previa |
| Vaults de Hyperliquid | Fuera del alcance (es otra decisión de inversión) | — |

## 7. Decisión

- **ELIMINAR** `ballenas_1h` como señal y como veto (no tiene ventaja en ninguna fuente; añade 15 consultas de cuenta
  por ciclo, websocket y un hilo de selección).
- **CONSERVAR** la grabación de datos (OI, operaciones grandes, flujo) y **desactivar el borrado a 120 días** para poder
  estudiar en 6–12 meses una hipótesis prerregistrada de posicionamiento agregado, usando `dir` de los fills (abrir vs
  cerrar) y un ranking por PnL ajustado a riesgo de 90 días.
- Si el propietario quiere conservar la vista de ballenas en el panel por interés informativo, que sea solo visual y sin
  efecto en decisiones.
