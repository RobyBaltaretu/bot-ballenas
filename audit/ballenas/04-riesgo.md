# 04 · Gestión de riesgo

Límites efectivos hoy (`python bot.py --validar-config`):

| Grupo | Límites |
|---|---|
| Por operación y apertura | 3 % por operación · 9 % de riesgo abierto · 6 posiciones · 4 por lado · 12 operaciones al día · apalancamiento ≤ 5 · margen ≤ 35 % por operación |
| Exposición | por mercado ≤ 100 % · bruta ≤ 250 % · neta ≤ 150 % · beta-BTC ≤ 200 % · correlación ≤ 0,8 |
| Pérdidas y pausas | pérdida diaria 6 % · semanal 12 % · caída desde el máximo 25 % · suelo total 50 % · pausa de 120 min tras 4 pérdidas seguidas |
| Stop, liquidez y datos | stop 0,25–12 % · horquilla ≤ 0,15 % · impacto ≤ 0,15 % · costes ≤ 20 % del riesgo · datos ≤ 120 s · cuenta ≤ 90 s |

## 4.1 Riesgo por operación: fórmula verificada (`riesgo.dimensionar`, `riesgo.py:121`)

- **Escenarios de stop** (`escenarios_stop`, `riesgo.py:55`), en pérdida por USD de nocional:
  - **base** = stop + costes + funding previsto;
  - **severo** = stop + deslizamiento severo (1 %) + costes fijos;
  - **límite** = stop + tolerancia de la orden hija (10 %) + costes fijos.
- **Presupuestos:** base = equity × 3 % × factor · severo = 2 × base · límite = equity × 15 % × factor.
- **Tamaño:** nocional = mínimo de (presupuesto / pérdida por USD) en los tres escenarios. Después se recorta por margen
  máximo × apalancamiento tope y por saldo libre × 0,95 × apalancamiento tope. El tamaño se redondea hacia abajo a
  `szDecimals`.
- **Apalancamiento:** el menor que cabe en el margen máximo (`riesgo.py:162`). Antes de aceptar comprueba que la
  liquidación quede a ≥ 1,5 × la distancia del stop (`riesgo.py:166`).

**Ejemplo calculado** (equity 261 $, factor 1, stop 8 %):
- base ≈ 7,83 $ / (0,08 + ~0,2 % de costes) ≈ 95 $ de nocional;
- severo ≈ 15,7 / 0,091 ≈ 172 $ y límite ≈ 39 / 0,18 ≈ 217 $, así que manda el escenario base;
- margen máximo = 91 $, por tanto apalancamiento 2× (95 > 91). Coherente con lo observado: en vivo, todas las operaciones a 1×,
  porque el factor ≤ 1 y los stops anchos dan nocionales de 10–74 $.

Las fórmulas, las unidades y el redondeo son correctos: el redondeo va hacia abajo y la orden mínima se comprueba contra
el riesgo en los tres escenarios. **[HECHO]** Hay pruebas: `test_riesgo` (18), `test_riesgo_stop` (10),
`test_simulacion_riesgo` (15) y `test_riesgo_desconocido` (7).

## 4.2 Riesgo agregado (`comprobar_agregados`, `riesgo.py:283`)

- Antes de enviar se comprueban: número de posiciones, máximo por lado, **riesgo abierto total**, exposición por mercado,
  bruta y neta, beta-BTC, y riesgo **desconocido** (bloquea). Las posiciones externas cuentan como exposición. **[HECHO]**
- **[RIESGO] Salto correlacionado:** el 9 % de riesgo abierto es el escenario **base**. El escenario «límite» (la orden hija
  del stop llena al 10 % de tolerancia) se acota **por operación** (15 %), pero **no en conjunto**.
  - Ejemplo: con 4 posiciones del mismo lado de ~95 $, un desplome que salte todos los stops a su límite costaría
    ≈ 4 × 95 × 0,18 ≈ 68 $, un **26 % de la cuenta**.
  - Es improbable, pero en cripto ya han ocurrido cascadas así. Falta un límite agregado del escenario severo o del límite.
- Pérdidas consecutivas: pausa tras 4. Modo defensa con R medio < −0,25 en 8 operaciones. Reducción en caídas del 5, 10
  y 20 %. **[HECHO]**

## 4.3 Derivados y liquidación

- **[HECHO]** Margen aislado. Liquidación real (`liquidationPx`) vigilada en cada ciclo (`gestor.vigilar_liquidacion`):
  si llega antes que el stop, cierra; si está cerca, bloquea entradas. Margen de mantenimiento > 50 % del equity: bloquea.
- Funding previsto incluido en el tamaño (`funding_adverso_frac`, con estrés ×2).
- **[RIESGO] Liquidez:** el stop de mercado de Hyperliquid admite un 10 % de deslizamiento. En monedas finas, un salto mayor
  deja la orden hija sin llenar (`riesgo.SIN_TOPE` lo reconoce). Desde el 19/11 el gestor cierra el resto si el stop se
  disparó a medias o el precio está al otro lado. El universo incluye memecoins (volumen ≥ 3 M$).

## 4.4 Sistema de protección

| Control | Implementación | Evidencia | Fallo posible | Gravedad |
|---|---|---|---|---|
| Kill switch / cierre total | `/cerrartodo`, `emergencia()` con el suelo | `bot.py:1435-1452` | Necesita el panel en local o Telegram (sin claves) | Media |
| Pausa manual | `pausa_manual` → bloqueo | `bot.py:598` | — | — |
| Circuit breaker de pérdidas | Diaria, semanal, caída, racha, suelo 50 % | `riesgo.bloqueos_duros`, `suelo_emergencia` | — | — |
| Datos viejos | Bloqueo | `bot.py:600` | — | — |
| Desincronización | Conciliación fallida o divergencia → bloquea o congela | `bot.py:604`, `gestor.conciliar` | — | — |
| Órdenes duplicadas | CLOID, reserva por moneda, bloqueo de instancia | `ejecucion.py:267`, `gestor.py:932`, `instancia.py` | — | — |
| Límite de órdenes | `max_operaciones_dia` 12 | `bloqueos_duros` | No limita órdenes por minuto (no hace falta con la frecuencia actual) | Baja |
| Reconciliación tras reinicio | `conciliacion_inicial`; en real se niega a arrancar con cosas sin atribuir | `bot.py:183`, `:1922` | — | — |
| Fail-safe del cerebro | Modelo roto o ausente → no decide | `cerebro.Modelo.desde_dict`, `bot.py:830` | — | — |
| **Ampliación de ganadoras** | Solo riesgo abierto y margen | `bot.py:1233` | **[DEFECTO D1]** Se salta la pausa manual, los límites de pérdida, los datos viejos, la conciliación y la exposición por mercado, bruta y beta | **Alta** (solo simulado) |

## Configuración para real pendiente de aplicar

`piloto_real` está escrito igual al simulado (19/11, por decisión de Roberto) y se aplicaría con el próximo arranque manual:
3 %, 9 %, 6 posiciones, **todos los mercados** (`"*"`), apalancamiento ≤ 5 y pérdida máxima de **116 $ (50 %)**.

**[RIESGO]** Si algún día se activa real con estos límites, una sola mala racha puede llevarse la mitad del capital, y las
memecoins tienen peor liquidez para los stops. Hoy no hay ninguna estrategia promovida, así que real no podría operar nada.
