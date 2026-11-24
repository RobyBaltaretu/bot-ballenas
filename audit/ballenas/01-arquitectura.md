# 01 · Arquitectura y flujo real

## Arranque (`bot.main`, `bot.py:2197`)

1. Carga la configuración y la valida. Con error, sale y no reintenta.
2. Toma un **bloqueo de instancia** por carpeta y cuenta (`instancia.BloqueoInstancia`): dos bots no pueden operar la misma
   cuenta. **[HECHO]**
3. `crear_cliente` (`bot.py:2113`):
   - **Shadow:** no se crea cliente de órdenes (`EjecutorShadow` bloquea cualquier envío).
   - **Simulado:** `CuentaPapel` sobre la API pública real. No necesita claves y no puede firmar.
   - **Real:** antes de crear el `Exchange` firmante comprueba:
     - que la cuenta sea **subcuenta** (`verificar_subcuenta`, `bot.py:156`);
     - que la clave sea una **API wallet** de su cuenta maestra;
     - que la cuenta no tenga nada que el bot no pueda atribuirse (`verificar_propiedad_inicial`);
     - que exista al menos una estrategia con promoción `real_habilitado` vigente (`bot.py:2267`). Si falta algo, **no
       arranca**. **[HECHO]**
4. Conciliación inicial y arranque del bucle `ejecutar`, con vigilante de cuelgue (`comprobar_cuelgue`): si un ciclo pasa
   de 20 min, el proceso sale y el lanzador lo reinicia.

## Un ciclo (`Bot.ciclo`, `bot.py:701`, cada 15 s más su duración)

`atender_comandos` → `actualizar_ballenas` → `leer_precios` → `gestor.conciliar` → suelo de emergencia → `leer_ballenas` y
websocket → `gestor.gestionar` (tiempo máximo, sin pérdidas, trailing) → `_ampliar_ganadoras` → shadow y sombras de la
memoria → `motor.nuevas_senales` (solo al cierre de vela) → cartera de funding, ballenas y liquidaciones → `agenda` →
**si hay candidatas:** relee precios y cuenta y llama a `procesar_candidatas` (`bot.py:805`).

## De la señal al PnL

| Paso | Dónde | Qué pasa |
|---|---|---|
| Datos | `motor.contexto`, `mercado.foto`, `papel._ctx` | Velas REST cerradas, mids, marca, OI y funding |
| Señal | `senales.detectar` vía `motor.nuevas_senales` (`motor.py:317`) | Solo al cierre de vela; también las estrategias apagadas, que van a sombra |
| Registro | `ledger.registrar("senal")` (`bot.py:818`) | Con contexto, rasgos y régimen |
| Filtros | `bot.evaluar` (`bot.py:629`) | Datos frescos, horquilla, costes frente a stop, funding en contra, volatilidad extrema, veto de ballenas |
| Decisión | `cerebro.decidir`, exploración, memoria (`bot.py:841-907`) | Ver 02 |
| Régimen | `filtros_entrada.regimen_btc` (`bot.py:851`) | Solo a favor de la tendencia de BTC (EMA 200) |
| Bloqueos | `bloqueos_entrada` (`bot.py:596`) + `comprobar_agregados` + `dimensionar` | Ver 04 |
| Orden | `gestor.abrir` (`gestor.py:928`) | Reserva por moneda → apalancamiento → ALO → espera → cancelación confirmada → IOC por lo que falte |
| Protección | `asegurar_stop`, `poner_tp` | Stop trigger reduce-only verificado; objetivos GTC reduce-only |
| Seguimiento | `gestor.conciliar` cada ciclo | Cuenta frente a registro: reducciones, stops ausentes o incorrectos, huérfanas, liquidación |
| Cierre | `cerrar` / stop / objetivo → `procesar_cierre` | Fills reales, funding atribuido, R, causa → ledger `cierre` |
| Persistencia | `estado.json`, `papel.json`, `ledger.jsonl` (fsync), `aprendizaje.json` | Escritura atómica (`compat.reemplazar`) |

Asíncrono: websocket de ballenas y de mercado, hilo de funding histórico (`motor.preparar_funding`), vigilante de cuelgue,
analista IA (en el panel), motor del carry (otro proceso) y laboratorio e investigación (procesos lanzados con bloqueos
`*.lock`).

## Qué pasa cuando algo falla

| Fallo | Comportamiento | Evidencia |
|---|---|---|
| No se puede leer la cuenta | `conciliacion_ok=False` → bloquea entradas | `bot.py:604`, `gestor.leer` |
| Precios viejos | Bloquea entradas | `bloqueos_entrada` `datos_frescos` |
| Errores repetidos del exchange | Ejecución degradada → bloquea entradas | `ejecucion._fallo` (`ejecucion.py:180`) |
| Respuesta ambigua de una orden | Consulta sin reenviar; si no se aclara, congela la moneda | `ejecucion.resolver` (`ejecucion.py:235`) |
| Excepción en el ciclo | Se registra y se reintenta en el siguiente; las posiciones conservan su stop | `bot.py:1912` |
| Ciclo colgado | Sale con código para que el lanzador reinicie | `comprobar_cuelgue` |
| Reinicio | Conciliación inicial; propiedad por ledger y CLOID | `conciliacion_inicial` |

## Matriz de funcionalidades

| Funcionalidad | Estado | Nota |
|---|---|---|
| Perpetuos de Hyperliquid (simulado) | IMPLEMENTADO | En uso |
| Perpetuos de Hyperliquid (real) | IMPLEMENTADO, NO VERIFICADO | Nunca ejecutado contra el exchange real; sin promociones |
| Contado de Hyperliquid | PARCIAL | Solo en `carry/`, simulado |
| Binance/Bybit | IMPLEMENTADO (solo lectura) | Rasgos e historia; nunca órdenes |
| Cerebro 4 h | IMPLEMENTADO | Decide en simulado en modo «exploración» (modelo `no_supera`) |
| Cerebro 1 h | PARCIAL | Hay modelo (`no_supera`) pero no decide; lo de 1 h va a exploración amplia |
| Exploración amplia | IMPLEMENTADO | Solo simulado; 0,5 % de riesgo, 4 como máximo |
| Memoria por vecinos | IMPLEMENTADO | Desde el 19/11 también reduce tamaño o veta sobre lo que acepta el cerebro |
| Ballenas (señal y veto) | IMPLEMENTADO | Señal en simulado desde el 19/11; veto activo |
| Liquidaciones inferidas | PARCIAL | Solo investigación (no opera) |
| Cartera de funding | IMPLEMENTADO | Solo simulado |
| Carry de dos patas | IMPLEMENTADO | Proceso aparte, simulado; 0 posiciones (funding < 20 %/año) |
| Ampliar ganadoras | IMPLEMENTADO | Solo simulado, desde el 19/11; tiene un defecto (ver 04, D1) |
| Telegram | NO IMPLEMENTADO en la práctica | Faltan las claves |
| Copias de seguridad | NO IMPLEMENTADO en Windows | Scripts solo para la VPS (`despliegue/copia_seguridad.sh`) |
| Promoción a real | IMPLEMENTADO | Ninguna estrategia promovida |

**Decisión de arquitectura que hay que tener presente [HECHO]:** el simulado ejecuta varias vías de decisión que en real
**no existen**: exploración del cerebro, exploración amplia, cartera de funding, ballenas en `modo_senal: simulado` y
ampliación. En real solo operarían las estrategias promovidas, y hoy no hay ninguna. Por tanto, el resultado del simulado
**no** describe lo que haría el bot en real.
