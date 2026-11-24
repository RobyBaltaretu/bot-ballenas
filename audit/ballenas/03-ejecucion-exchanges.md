# 03 · Exchanges y ejecución

## 2.1 Integraciones

| Exchange | Uso | Biblioteca | Canal | Escritura |
|---|---|---|---|---|
| Hyperliquid perpetuos | Datos y órdenes | `hyperliquid-python-sdk 0.24.0` (`Info`, `Exchange`) | REST `/info` + websocket (ballenas y operaciones) | Solo en real, con API wallet de subcuenta |
| Hyperliquid contado | Carry (simulado) | REST público `/info` (`carry/terreno.py`, lista `PERMITIDOS`) | REST | No (simulado) |
| Binance, Bybit | Rasgos e historia | `requests` a endpoints públicos (`contexto_externo.py`, `historia_externa.py`) | REST | Nunca |

- **Límites [HECHO]:** `limitador.py` aplica 900 de peso por minuto (límite de IP: 1200), con los pesos de la documentación
  de Hyperliquid (consultada el 28/10 según el código) y reintentos ante 429.
- **[DEFECTO operativo] Arranque lento:** tras cada arranque, `motor.preparar_funding` (`motor.py:230`) vuelve a bajar
  90 días de funding de unas 37 monedas, unos 8 000 de peso. Durante 10–15 min el limitador frena y el ciclo pasa de ~7 s a
  30–45 s. Medido hoy: 95 esperas en 2 min durante el arranque y 0 pasados 15 min.
- Las comisiones (0,015 % maker / 0,045 % taker) están en `config.json`. En real se leen de la cuenta
  (`comisiones.fuente: cuenta`, `bot.py:2145`). Las tarifas oficiales se verificaron en el estudio del 19/11 (documentación
  de Hyperliquid, «Fees»).

## 2.2 / 2.3 Consistencia y contado frente a derivados

- No hay multiexchange operativo: no hay normalización entre exchanges ni riesgo de exposición duplicada entre ellos.
  **[HECHO]**
- Lo que sí usa el contado (el carry) está **aislado**: proceso, cartera y registro propios (`carry/motor.py`). Una prueba
  impide que la raíz importe `carry` y otra prohíbe cadenas de órdenes reales dentro de `carry/`. Tampoco cruza reglas
  con el bot. **[HECHO]**
- **Perpetuos [HECHO]:**
  - margen aislado (`update_leverage(..., is_cross=False)`, `ejecucion.py:358`);
  - stops trigger de mercado reduce-only activados por la marca;
  - funding atribuido por intervalos y tamaño (`contabilidad.atribuir_funding`);
  - liquidación vigilada con el `liquidationPx` de la cuenta (`gestor.vigilar_liquidacion`).
- Unidades: el PnL y el riesgo van en USD(C) de forma coherente y el R es PnL / riesgo inicial. **[HECHO]**

## 3. Ciclo de vida de una orden

| Fase | Mecanismo | Evidencia |
|---|---|---|
| Antes de enviar | Ledger `orden_enviada` **antes** del envío; las órdenes de protección o cierre deben ser reduce-only (si no, `ValueError`) | `ejecucion.py:263-272` |
| Idempotencia | CLOID nuevo por orden; el exchange (y `papel`) rechaza CLOID repetidos; **nunca se reenvía** una ambigua | `ejecucion.py:267`, `papel._duplicado` |
| Respuesta ambigua | `resolver`: consulta con espera creciente; si no consta, `no_confirmada` y congela la moneda | `ejecucion.py:235-257` |
| Entrada | ALO → espera ≤ 20 s → **cancelación confirmada** (consulta tras el ACK) → IOC solo por lo que falte según **posición real + fills** | `gestor.py:962-1017`, `_ejecutado_confirmado` |
| Stop | Trigger reduce-only, verificado en la cuenta en **cada** ciclo; mover un stop = poner el nuevo, verificarlo y cancelar el viejo | `gestor.reemplazar_stop`, `asegurar_stop` |
| Parciales | Tramos de tamaño (hora del fill o «incierta») → funding y stop rehechos | `gestor._reduccion` |
| Cierre | IOC reduce-only con tres niveles de deslizamiento; se verifica en la cuenta | `gestor.cerrar` |
| Conciliación | Propias, externas, tamaño mayor o menor, lado distinto, órdenes externas y huérfanas | `gestor.conciliar` (`gestor.py:116`, `:267`) |

## Escenarios críticos

| # | Escenario | Qué hace Ballenas | Consecuencia | Prueba |
|---|---|---|---|---|
| 1 | Orden aceptada, respuesta perdida | Excepción → «desconocida» → consulta por CLOID | No duplica | `test_ordenes_seguras` (existe) |
| 2 | Reintento de orden ya aceptada | No reenvía (sin reintentos ciegos); el CLOID evita el duplicado | — | Existe |
| 3 | El precio se mueve antes de ejecutar | ALO o IOC con límite; `persecucion_max_pct` 0,5 % frena la reserva a mercado | Puede no entrar | `test_gestor` |
| 4 | Ejecución parcial | Al primer parcial cancela el resto y protege lo ejecutado | Tamaño menor que el plan | Existe |
| 5 | Stop rechazado | `politica_sin_stop: reponer_y_alertar`, bloquea entradas; si el precio ya cruzó, cierra (arreglo del 19/11) | — | `test_arreglos_estudio` |
| 6 | Conexión perdida con posición abierta | En real el stop está en el exchange. En simulado `papel` solo procesa cuando el bot pregunta: **sin bot no hay stops simulados** | Solo afecta a la fidelidad del simulado | Pendiente |
| 7 | Reinicio a mitad de operación | El estado y el ledger se escriben antes de enviar; conciliación al arrancar | — | `test_bot` (reinicio) |
| 8 | Websocket desincronizado | Reconexión; solo afecta a ballenas y mercado grabado; las ballenas «no frescas» desactivan su señal y su veto | — | `test_mercado_ws` (2) |
| 9 | Datos viejos | Bloqueo de entradas (`datos_max_antiguedad_seg` 120) | — | Existe |
| 10 | Dos estrategias en el mismo activo y ciclo | Reserva por moneda y una sola entra (el 23/10 no existía y dio la doble entrada en kPEPE) | — | `test_dos_estrategias_misma_moneda...` |
| 11 | Cambian las reglas de tamaño | `meta` en cada universo; `szDecimals` en cada redondeo | — | Parcial |
| 12 | Fill no registrado | Se busca por moneda y tiempo; si hay actividad externa, «contabilidad incompleta» y congela | Resultado `None`, nunca inventado | Existe |
| 13 | Cierre reduce-only rechazado | Mantiene el stop, alerta y reintenta en el ciclo siguiente | — | Existe |
| 14 | Cancelación frente a ejecución | Se re-consulta tras cancelar; manda la posición real | — | Existe |
| 15 | Cambia el margen entre validar y enviar | `dimensionar` usa el saldo libre × 0,95; el exchange rechazaría | Rechazo claro | Parcial |

**¿Puede quedar una posición abierta sin que Ballenas lo sepa? [HECHO]** En la cuenta, no: la conciliación de cada ciclo
detecta cualquier posición u orden y la clasifica como externa o divergente. **En el ledger, sí:**
- **[DEFECTO]** La operación `op-20261023120105-55b133` (kPEPE, `ruptura_4h`, 23/10) figura «completada» con 2952 de
  entrada y **sin evento de cierre**. Fue la doble entrada del 23/10: sus órdenes se cancelaron como huérfanas y nadie cerró
  el registro. Esa «abierta fantasma» sigue en el historial. No altera el saldo: el ledger cuadra con la cuenta desde la
  puesta a cero, +29,25 frente a +29,24 (ver 06).

## Defecto del 19/11 (código nuevo)

- **[DEFECTO] D1:** `bot._ampliar_ganadoras` (`bot.py:1233`) amplía posiciones **sin pasar** por `bloqueos_entrada` (pausa
  manual, pérdida diaria o semanal, datos viejos, conciliación) ni por `comprobar_agregados` (exposición por mercado,
  bruta, neta y beta). Sí comprueba el riesgo abierto y el margen. Solo afecta al simulado. Detalle en 04.
