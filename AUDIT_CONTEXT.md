# AUDIT_CONTEXT — Contexto para una auditoría externa independiente

**Fecha de corte:** 24/11/2026. Propietario: Roberto. Repositorio: `RobyBaltaretu/bot-ballenas`.

Este documento describe el estado **actual** del bot, tal y como está. No propone correcciones ni mejoras, y no
cambia nada del código ni de la configuración.

**De dónde salen las cifras:** del propio repositorio, a fecha de corte.
- Las del laboratorio, de `estrategia_elegida.json` (ejecución `lab-20261122T030003Z`, generada el 22/11/2026).
- Las de operativa simulada, del ledger (`registro/ledger.jsonl`), reconstruido con `ledger.Ledger.operaciones()`.
- El estado de la cuenta, de `panel_datos.json`.

Lo que no se ha podido verificar se marca como tal.

Documentos relacionados (en la raíz salvo que se indique): `LEEME.md` (referencia funcional), `CLAUDE.md` (bitácora
técnica de cambios por fecha), `audit/ballenas/` (auditoría interna del 19/11/2026, 11 documentos),
`INFORME_AUDITORIA_V12.md`, `ESTUDIO_BOT_2026-11-19.md`, `PLAN_CARRY.md`, `PANEL_REDISENO.md`, `PENDIENTE_ROBERTO.md`.

---

## 0. Resumen en diez líneas

1. Bot de trading de **futuros perpetuos de cripto en Hyperliquid**, escrito en Python 3 (probado con 3.12 y 3.14),
   con panel web local. Toda la interfaz y la documentación están en español.
2. **Funciona solo en modo SIMULADO**: dinero ficticio con precios, libro y funding reales. Nunca ha enviado una orden
   real. Ninguna estrategia está autorizada para real.
3. Varias **estrategias técnicas** proponen candidatas en cada cierre de vela de 1 h o 4 h. Un **«cerebro»** (regresión
   ridge de 8 rasgos) decide cuáles se operan, y después actúan los filtros y límites de riesgo.
4. Un **laboratorio** semanal valida las estrategias con walk-forward, holdout sellado y corrección por pruebas
   múltiples. **Ninguna estrategia ni el cerebro superan hoy esa validación** (todas `no_supera`).
5. En simulado se opera igualmente, por vías de «exploración», para acumular evidencia. En real esas vías no existen.
6. **Resultado simulado desde la última puesta a cero** (28/10/2026 22:44 UTC): 30 operaciones cerradas,
   **+29,84 $ netos**, R medio **+0,145** (t 0,67, no significativo). Valor de la cuenta: 264,25 $ frente a 232 $
   iniciales.
7. El beneficio se concentra en los **cortos**: 17 operaciones, +40,84 $. Los **largos** pierden: 13 operaciones,
   −11,00 $. Dos operaciones de `momentum_4h` aportan 22,7 $.
8. **Binance y Bybit se usan solo como fuente de datos públicos** de lectura, sin cuenta ni claves.
9. El paso a real exige `promocion.py`, una huella de código y configuración, y la aprobación humana expresa de Roberto.
   Ningún resultado automático puede activarlo.
10. Problemas abiertos más relevantes:
    - el panel está accesible por túnel sin contraseña;
    - no hay alertas externas (Telegram sin configurar);
    - no hay copias de seguridad en Windows;
    - el bot corre en un PC doméstico;
    - nunca se ha probado contra la API real de órdenes.

---

## 1. Contexto funcional

### 1.1 Qué hace

- **Universo.** Vigila hasta 40 monedas del perpetuo de Hyperliquid con al menos 3 M$ de volumen en 24 h, más una
  lista fija de inclusión obligatoria (BTC, ETH, DOGE, kPEPE, FARTCOIN, TRUMP, PUMP, WIF, kBONK). Incluye memecoins.
- **Propuestas.** En cada cierre de vela (1 h y 4 h), las estrategias activas generan **candidatas** (moneda, lado,
  stop, plan de salida y motivo).
- **Decisión.** Cada candidata pasa por:
  1. el cerebro, o en su defecto la memoria por vecinos o la exploración;
  2. los filtros de entrada (régimen de BTC, funding en contra, costes, horquilla);
  3. el dimensionado por riesgo y los límites agregados.
- **Operación aprobada.**
  - Se abre con una orden límite post-only (ALO) y, si no se llena, una IOC de reserva por lo que falte.
  - Se protege con un stop verificado y objetivos reduce-only.
  - Se gestiona (parcial, break-even, trailing, tiempo máximo) hasta su cierre.
- **Registro.** Todo queda en un **ledger** de eventos versionado (señal, decisión con motivos, orden con CLOID, fill,
  stop, movimientos, funding y cierre). El panel reconstruye cada operación solo desde ese registro.
- **Sombras.** Lo que se descarta se sigue en **sombra** (`aprendizaje.json`): cómo habría acabado. Sirve para medir
  si los filtros aciertan.
- **Tareas programadas propias** (`bot.agenda`), con bloqueos para que no se solapen:
  - laboratorio, los domingos desde las 04:00 hora local;
  - investigación de ideas nuevas, de lunes a sábado desde las 02:30.

### 1.2 Modos

| Modo | Qué hace | Estado |
|---|---|---|
| `simulado` (`paper`) | Cuenta ficticia (`papel.py`, `papel.json`) con 232 $ iniciales y datos reales | **Activo** |
| `shadow` | Solo observa; ni siquiera crea el cliente de órdenes | No se usa |
| `real` | Subcuenta dedicada, solo estrategias promovidas, límites del piloto | **Nunca activado** |

### 1.3 Procesos en marcha (Windows, PC doméstico)

Lanzados por `INICIAR.bat` → `despliegue/iniciar_windows.ps1`:

- **`bot.py`:** bucle principal (ciclo cada 15 s), con reinicio automático salvo en tres casos:
  - código de salida 3, el suelo de emergencia;
  - configuración inválida;
  - parada manual.
- **`panel.py`:** panel web en `127.0.0.1:8080`, y el analista de IA (`analista_ia.py`) en el mismo proceso.
- **`carry/motor.py`:** carry de funding de dos patas, como proceso aparte con su propia cuenta ficticia de 200 $.
- **Cloudflare Tunnel:** servicio de Windows que expone el panel (ver los problemas conocidos).

Está preparada una migración a un VPS de Hetzner (`despliegue/GUIA_HETZNER.md`, `instalar_vps.sh`, unidades systemd),
pero **no se ha ejecutado**. El bot nunca ha corrido en Linux.

---

## 2. Arquitectura técnica

### 2.1 Pila

- **Python.** Dependencias directas fijadas en `requirements.txt`: `hyperliquid-python-sdk==0.24.0`,
  `python-dotenv==1.2.4` y `requests==2.34.2`. El entorno completo está en `requirements-bloqueado.txt`.
- **Estado en archivos JSON / JSONL**, sin base de datos. Las escrituras son atómicas; el ledger y el feed rotan por
  tamaño.
- **Panel:** servidor HTTP propio en `panel.py` y frontend en `panel_web/`, con módulos JS nativos, sin compilación,
  CSP estricta, sin `innerHTML` ni estilos en línea. El panel clásico está en `/clasico` (`panel.html`).
- **Unas 22 350 líneas** en los `.py` de la raíz y **764 pruebas** `unittest` en `tests/`.

### 2.2 Módulos

| Capa | Archivos | Función |
|---|---|---|
| Orquestación | `bot.py` (2 388 líneas) | Bucle, arranque seguro, `procesar_candidatas`, bloqueos de entrada, agenda, comandos del panel, `panel_datos.json` |
| Señales | `motor.py`, `senales.py`, `estrategia.py` | Indicadores, módulos de estrategia, salida y gestión de capital |
| Decisión | `cerebro.py`, `cerebro_vivo.py`, `mercado_unificado.py`, `aprendizaje.py` | Modelo ridge, decisión en vivo, rasgos comunes entre laboratorio y vivo, memoria por vecinos |
| Riesgo | `riesgo.py` | Tamaño, apalancamiento, liquidación, límites agregados, techos de real, desplome conjunto |
| Ejecución | `gestor.py` (1 554 líneas), `ejecucion.py`, `limitador.py` | Propiedad, conciliación, máquina de estados de órdenes, CLOID, stops verificados, huérfanas, límite de peticiones |
| Simulación | `papel.py` | Cuenta ficticia: libro real, MODELO 3 de llenado, funding real, recuperación de stops con el bot parado |
| Contabilidad | `ledger.py`, `contabilidad.py` | Ledger de eventos y PnL bruto/neto, comisiones y funding |
| Validación | `laboratorio.py` (1 765), `validacion.py`, `historia_externa.py`, `datos.py`, `laboratorio_semanal.py`, `manifiesto_datos.py`, `preregistro.py` | Walk-forward, holdout, pruebas múltiples, estrés, historia de Binance/Bybit, prerregistro |
| Investigación | `investigacion.py`, `vigilancia.py`, `estudios.py`, `estudios_ext/` | Ideas nuevas, aspirantes, cementerio, vigilancia de degradación, estudios |
| Promoción | `promocion.py`, `veredicto.py` | Etapas, huella y aprobaciones; veredicto de la prueba de dos semanas |
| Datos de mercado | `mercado.py`, `archivo.py`, `contexto_externo.py`, `ballenas.py`, `seleccion.py`, `coinglass.py`, `calendario_macro.py` | Grabación de interés abierto, funding, operaciones grandes, libro y ballenas; Binance/Bybit en vivo |
| Panel y operación | `panel.py`, `config_panel.py`, `taller.py`, `mesa.py`, `sombras.py`, `revision_proceso.py`, `observabilidad.py`, `notificaciones.py`, `feed.py`, `informe.py`, `diagnostico.py`, `comprobar.py`, `instancia.py`, `compat.py` | Panel, editor de configuración, salud, Telegram, feed, bloqueo de instancia |
| Configuración | `configuracion.py`, `config.json` | Valores por defecto (`DEFECTOS`), migración y validación |
| Carry | `carry/` (`motor`, `logica`, `ejecucion`, `papel_perp`, `papel_spot`, `terreno`) | Carry de dos patas en simulado, aislado del resto: no importa nada de la raíz |
| IA (solo lectura) | `analista_ia.py` | Informe diario, revisor y escéptico con Groq (`openai/gpt-oss-120b`), tope de 40 consultas al día |

**Clasificación de código para la huella:** `promocion.ARCHIVOS_CODIGO` agrupa el código que afecta a las decisiones;
los archivos «sin efecto» van aparte. Una prueba exige que todo `.py` nuevo esté clasificado. El paquete `carry/` queda
fuera de la huella a propósito.

### 2.3 Flujo de una candidata (`bot.procesar_candidatas`)

1. **Señal.** Se calculan los rasgos (funding en contra, mercado y régimen de BTC) y se registra la `senal` en el
   ledger.
2. **Evaluación** (`self.evaluar`): plan, tamaño, horquilla y fallos de filtros.
3. **Memoria por vecinos** (`aprendizaje.Memoria.valorar`): juzga **todas** las señales, para poder medir el filtro.
4. **Cerebro** (`cerebro_vivo`). Si falta el modelo, está corrupto o hay un error interno, **no entra nada** (falla
   cerrado).
5. **Vías de decisión** (`ledger.via_decision`):
   - `cerebro`: el modelo supera el laboratorio; **hoy no hay ninguno así**.
   - `cerebro_exploracion`: solo en simulado, para el intervalo de 4 h.
   - `exploracion_amplia`: solo en simulado; 0,5 % de riesgo, como máximo 4 abiertas.
   - `cartera_funding`: solo en simulado.
   - `memoria`.
6. **Bloqueos y límites:**
   - bloqueos globales (`bloqueos_entrada`, `bloqueos_duros`);
   - límites agregados (`comprobar_agregados`);
   - desplome conjunto (`comprobar_salto`);
   - régimen de BTC.
7. **Apertura** (`gestor.abrir`): una operación por moneda, reservada antes de enviar nada. Después, el stop se
   verifica y la operación se concilia en cada ciclo.

---

## 3. Estrategias implementadas

Los módulos están en `senales.MODULOS`. Cada uno se combina con un intervalo (`modulo_intervalo`). Los parámetros por
defecto se citan tal y como están; el laboratorio elige los suyos por tramo dentro de una rejilla.

| Módulo (versión) | Idea | Parámetros por defecto | Salida por defecto |
|---|---|---|---|
| `ruptura` (v1) | Ruptura del máximo o mínimo de N velas a favor de la EMA | n 20, EMA 50, vol_min 1,0, stop 2 ATR | TP1 1,5 R, final 4 R, trailing 1,5 R, 30 velas |
| `retroceso` (v1) | Retroceso a la media en tendencia (EMA 20/50, eficiencia ≥ 0,3) | stop 1,5 ATR | 1 R / 3 R / 1 R, 24 velas |
| `reversion` (v1) | RSI extremo con poca eficiencia y desvío ≥ 2 ATR | RSI 14 < 25, stop 1,5 ATR | 0,8 / 1,8 / 0,8 R, 10 velas |
| `funding` (v1) | Funding extremo (percentil 95 en 8 h) | stop 1,8 ATR | 1 / 3 / 1,2 R, 18 velas |
| `fuerza` (v2) | Fuerza relativa: la moneda más fuerte o débil, con rebalanceo | lookback 42, rebalanceo 84, top 1, stop 3 ATR | Sin objetivo, 83 velas |
| `momentum` (v2, solo 4 h) | Movimiento de 2–4 semanas ≥ 4 ATR con eficiencia ≥ 0,1 | lookback 126, rebalanceo 42, stop 4 ATR | Sin objetivo; break-even y trailing a 1,5 R; 41 velas |
| `ballenas_1h` | Flujo de cuentas grandes seguidas (≥ 50 k$ de aumento, ≥ 100 k$ de flujo) | stop 1,5 ATR, 8 velas | 1 / 2,5 / 1 R |
| `liquidaciones_1h` | Posible cascada de liquidaciones (caída del interés abierto ≥ 3 %, movimiento ≥ 2 ATR) | stop 1,5 ATR, 6 velas | 1 / 2 / 0,8 R |
| `cartera_funding_4h` | Los lunes a las 00:00 UTC: largo en las 2 monedas de funding de 7 días más bajo y corto en las 2 de más alto | 1 % de riesgo por pata, las dos patas o ninguna | — |
| Carry (`carry/`) | Corto en el perpetuo y largo en contado de Hyperliquid cuando el funding supera el 20 %/año | Proceso aparte, 200 $ ficticios | Por `logica.evaluar_salida` |

**Estado en `config.json` (24/11/2026):**

- **Proponen y pueden operar en simulado:** `ruptura_4h`, `fuerza_4h`, `momentum_4h`, `ballenas_1h`
  (`modo_senal: simulado`, también como veto) y `cartera_funding`.
- **Apagadas, pero siguen en sombra:**
  - todas las de 1 h salvo ballenas (desde el 13/11): `ruptura_1h`, `retroceso_1h`, `reversion_1h`, `funding_1h` y
    `fuerza_1h`;
  - `retroceso_4h`, `funding_4h` y `reversion_4h` (desde el 23/11).

  Las apagadas generan candidatas marcadas `solo_investigacion` + `apagada`: nunca operan, ni siquiera por exploración.
- **Solo investigación:** `liquidaciones_1h`.
- **Etapa de promoción** (`python promocion.py estado`): **las 13 claves están en `investigacion`**. Ninguna está en
  `apta_revision` ni en `real_habilitado`.

**Explicación para el usuario:** cada módulo tiene su texto en `panel_web/assets/js/vistas/explicaciones.js`.

---

## 4. Reglas y validaciones existentes

### 4.1 Riesgo y tamaño (`config.json → riesgo`, `riesgo.py`)

**Valores en vigor (simulado):**

| Parámetro | Valor |
|---|---|
| Riesgo por operación | 3 % |
| Riesgo abierto máximo | 9 % |
| Posiciones abiertas | máximo 6 (4 del mismo lado) |
| Operaciones al día | máximo 12 |
| Apalancamiento máximo | 5× |
| Margen por operación | máximo 35 % |
| Stop | entre 0,25 % y 12 % |
| Horquilla máxima | 0,15 % |
| Correlación máxima | 0,8 |
| Duración máxima global | 336 h |
| Pausa por pérdidas | 120 min tras 4 pérdidas seguidas |
| Suelo de emergencia | −50 % (`perdida_max_total_pct`): cierra solo las posiciones del bot y se apaga con código 3 |

**Cómo se calcula el tamaño:**
- Se parte del riesgo: distancia al stop más comisiones de entrada y salida, media horquilla, deslizamiento estimado,
  margen de estrés y el funding previsto (el mayor entre el actual y el básico, ×2). El tamaño se redondea hacia abajo.
- Si la orden mínima (10 $) excede el riesgo permitido, la candidata se descarta.
- El tamaño se recalcula con el impacto de recorrer el libro real. Se descarta si el libro no cubre el tamaño o si el
  impacto supera `impacto_max_pct`.
- Se usa el menor apalancamiento que cabe, y la liquidación estimada debe quedar bastante más lejos que el stop.
- Después de entrar, manda el `liquidationPx` real, que se lee en cada ciclo.
- Los tramos de margen (`riesgo.tramos_margen`) bajan el apalancamiento según las `marginTables` de Hyperliquid. Con
  230 $ no tienen efecto.

**Límites agregados y de exposición:**
- **Riesgo desconocido nunca cuenta como 0** (`riesgo.riesgo_posicion`): si no se puede estimar, bloquea entradas.
- **Desplome conjunto** (`riesgo.comprobar_salto`): suma por lado de la pérdida si saltan los stops, con un 10 % de
  tolerancia, tope del 20 % del valor de la cuenta.
- **Exposición a BTC ponderada por beta**; una beta desconocida se toma como 1,5.
- **Filtro de costes:** descarta si los costes superan el 20 % del riesgo.

**Gestión de capital** (`gestion_capital`), que solo reduce el tamaño:
- en caída: −5 % → ×0,75, −10 % → ×0,5, −20 % → ×0,3;
- tras una pérdida diaria del 4 %: ×0,4; tras una pérdida semanal del 8 %: ×0,5; al llegar al objetivo diario del 3 %:
  ×0,5;
- **modo defensa:** las últimas 8 operaciones con R medio < −0,25 → ×0,5. Solo cuenta lo posterior a la última
  puesta a cero.

**Techos duros del real** (`riesgo.TECHOS_REAL`), que ni la config ni el panel pueden superar: 3 % / 9 % / 5× / 6
posiciones / pérdida diaria del 10 %.

**`piloto_real` en `config.json`:** 232 $ de capital, 3 % / 9 % / 6 posiciones / 5×, todos los mercados (`"*"`) y
pérdida máxima de 116 $ (50 %).
- Tiene **los mismos valores que el simulado**, por decisión de Roberto del 19/11. La auditoría interna lo marcó como
  agresivo para un primer real (D15).
- Está pendiente de decisión (ver la sección 10).

### 4.2 Bloqueos de entrada (`bot.bloqueos_entrada`)

Bloquean entradas cualquiera de estos motivos:
- pausa manual;
- datos de precios obsoletos;
- ejecución degradada;
- conciliación pendiente;
- posiciones sin stop verificado;
- riesgo de liquidación o margen;
- lectura de la cuenta antigua;
- posiciones de una versión anterior (en real);
- reloj desfasado;
- bloqueos duros de pérdida (día, semana, caída y racha);
- en real, la pérdida del piloto ≥ `perdida_max_usd`.

La ampliación de ganadoras (`piramide`, solo en simulado) pasa los mismos controles desde el 19/11 (R-01).

### 4.3 Filtros de entrada

- **Régimen de BTC** (`filtros_entrada.regimen_btc`, activo): solo se entra a favor de la tendencia de BTC (cierre
  frente a su EMA de 200 velas). Si no se conoce el régimen, no se entra. La exploración no se lo salta.
  - **A fecha de corte el régimen es bajista**, así que solo se aceptan cortos.
- **Funding en contra:** máximo 0,005 %.
- **Veto de ballenas:** 150 k$ en contra.

### 4.4 Ejecución y propiedad (`gestor.py`, `ejecucion.py`)

- **Órdenes:**
  - cada orden lleva un **CLOID** generado antes del envío;
  - ante una respuesta dudosa se consulta el estado y **nunca se reenvía**;
  - si el estado no se puede saber, el mercado se congela;
  - una cancelación solo se da por buena tras volver a consultar.
- **Entrada:**
  - es ALO, con una espera de 20 s;
  - la IOC de reserva solo se envía con el estado final de la ALO confirmado, y solo por lo que falte según la posición
    real y los fills.
- **Stops:**
  - siempre reduce-only, y se bloquea cualquier orden de salida que no lo sea;
  - antes de reponer uno se adopta el que ya exista, y los duplicados se cancelan;
  - para mover un stop, primero se pone y verifica el nuevo y después se cancela el viejo.
- **Propiedad y conciliación:**
  - una posición es del bot solo si tiene su `trade_id`, sus CLOID y coincide con la cuenta; las demás son
    **externas**, cuentan como riesgo y nunca se tocan;
  - si la cuenta no cuadra con el registro, ese mercado se congela;
  - una sola operación por moneda.
- **Instancia y caducidad:**
  - bloqueo de una sola instancia por carpeta y por cuenta (`instancia.py`);
  - los envíos reales caducan a los 15 s (`expiresAfter`; probado solo con exchanges falsos).
- **Sin `scheduleCancel`** (dead man's switch), a propósito: cancelaría también los stops.
- **Operaciones huérfanas en el ledger** (R-08): una operación abierta en el ledger pero desconocida para el gestor se
  cierra como `contabilidad: incompleta`, con resultado desconocido. Hay un caso: kPEPE del 23/10.

### 4.5 Validación del laboratorio (`laboratorio.py`, `validacion.py`)

- **Walk-forward** de 5 tramos, holdout del 15 % y embargo de 24 velas. Una operación solo cuenta si abre y cierra
  dentro de su partición.
- **Holdout de un solo uso y acumulativo** (`laboratorio_holdout.json`): con menos de 10 operaciones frescas queda
  **sellado** (no se mira), y el resultado como mucho es «exploratorio».
- **Pruebas múltiples:**
  - t de Student de una cola al 5 %/k;
  - desde el 19/11, k = familias efectivas (27) en lugar de variantes totales (1 098);
  - listón actual: t ≈ 2,91 con unas 1 000 operaciones y 3,02 con 60;
  - también se exige **t por días** (resultado sumado por día).
- **Otras pruebas:**
  - bootstrap por bloques;
  - líneas base comparables (azar y «siempre largo»);
  - estrés (costes ×2, deslizamiento ×3, stops 0,15 R peor, funding ×3);
  - **meseta** de parámetros;
  - monedas veteranas;
  - cartera con los límites reales.
- **Prueba de lookahead** (`tests/test_lookahead.py`), con un control que demuestra que caza una fuga deliberada.
- **Historia ampliada** con Binance/Bybit: 6 años en 4 h. Se valida contra Hyperliquid y se informa aparte el tramo
  solo de Hyperliquid.
- **Búsqueda congelada** desde el 17/11 (`laboratorio.busqueda_congelada`): la investigación no prueba ideas nuevas.
- **Laboratorio solo con 4 h** desde el 17/11 (`laboratorio.intervalos_estrategias: ["4h"]`).
- **Requisitos para «supera»:** ≥ 30 operaciones fuera de muestra, media > 0, t y t por días por encima del listón,
  límite inferior del intervalo de confianza > 0, holdout fresco positivo, mejor que las líneas base, positiva en
  estrés y en las veteranas.
- **Hipótesis prerregistradas** (`preregistro.py`, solo informe): `fuerza_4h` y `carry_realista`, con 30 operaciones
  y 20 días fijados de antemano, y un único juicio.

### 4.6 Promoción a real (`promocion.py`)

- **Etapas:** `investigacion` → `laboratorio` → `shadow` → `paper` → `apta_revision` → `real_habilitado`.
  - Las dos últimas solo se dan por línea de comandos con confirmación literal (`--por "Roberto"`).
  - Ningún botón del panel ni comando de Telegram puede aprobar.
- **Huella determinista:** código de decisión, configuración efectiva, identidad del modelo del cerebro, contexto
  externo y versiones de esquema. Cualquier cambio invalida las aprobaciones; si la huella no se puede calcular, nada
  queda autorizado.
- **Requisitos de `apta_revision`:**
  - laboratorio superado hace ≤ 30 días;
  - ≥ 30 operaciones válidas y ≥ 14 días de observación;
  - última evidencia hace ≤ 7 días;
  - R neto medio > 0 y neto acumulado > 0;
  - caída ≤ 10 R y costes ≤ 0,35 R por operación.
- **Arranque en real** (nunca hecho). Exige:
  - una subcuenta dedicada y una API wallet (que puede operar, no retirar);
  - `BOT_REAL_CONFIRMADO=SI`;
  - `real.habilitado` con la misma subcuenta;
  - al menos una estrategia en `real_habilitado`.

  Al arrancar comprueba con `userRole` que la cuenta es una subcuenta y que la wallet pertenece a su cuenta maestra. Si
  falla, no arranca (falla cerrado).
- **`/aplicarconfig`** rechaza cambios de `piloto_real`: solo los aplica un arranque manual.

### 4.7 Panel

- **Acceso.** Por defecto solo escucha en `127.0.0.1`. Desde fuera es de solo lectura (salvo
  `panel.comandos_remotos`) y exige `PANEL_PASSWORD`, **excepto** con `panel.tunel_sin_clave: true`, que hoy está
  activo (sección 9).
- **Acciones:** token interno, mismo origen, tamaño máximo y límite de frecuencia.
- **Lo que el panel no puede cambiar:** el modo, la red, el piloto real, las comisiones, el laboratorio ni la seguridad.
- **Editor de configuración:** lista blanca, validación completa, copia en `config_copias/` y registro en
  `registro/cambios_config.jsonl`.
- **Ajuste manual de stop y objetivo** (`/stopmanual`, `/tpmanual`): solo en local y solo en simulado. El stop no puede
  quedar más lejos que el inicial.

### 4.8 Pruebas

764 pruebas en verde a fecha de corte (`.venv\Scripts\python -m unittest discover -s tests -t .`, unos 100 s).
- Usan `papel.py` y exchanges falsos: no hacen ninguna llamada que modifique una cuenta.
- `tests/comunes.config()` desactiva la agenda y la exploración amplia.
- Hay pruebas específicas de:
  - lookahead;
  - secretos (`test_secretos.py`);
  - clasificación de archivos para la huella;
  - aislamiento del carry;
  - arreglos de la auditoría (`test_auditoria_arreglos.py`, `test_mejoras_auditoria.py`).

---

## 5. El cerebro

**Qué es** (`cerebro.py`, `cerebro_vivo.py`, `mercado_unificado.py`):
- Una **regresión lineal con penalización (ridge)** que junta las candidatas de todas las estrategias del intervalo y
  predice su resultado en R.
- Se opera si la predicción supera **+0,05 R**, un umbral fijo que no se optimiza.

**Rasgos.** Son ocho, calculados con la misma función en laboratorio y en vivo, solo con velas cerradas (también las
de Binance/Bybit) y recortados a ±3 desviaciones (`cerebro.RECORTE_Z`):

| Rasgo | Peso del modelo vigente (R por desviación típica) |
|---|---|
| `tendencia` | −0,0435 |
| `impulso6` | +0,058 |
| `volatilidad` | +0,0445 |
| `funding8h` | +0,1053 |
| `dif_funding8h` (Hyperliquid frente a Binance/Bybit) | −0,0025 |
| `flujo1` (flujo comprador agresivo externo, 1 vela) | +0,0224 |
| `flujo6` | +0,0527 |
| `base_pct` (diferencia de precio con el exterior) | −0,0029 |

**Modelo vigente:** `cerebro_modelo.json`, versión `cerebro-lab-20261122T030003Z`, huella `fc49dfbad399dfd9`.
- Intervalo de 4 h, variante `cerebro_con_todo`, entrenado con 6 018 candidatas de 6 módulos de 4 h.
- **Estado de laboratorio: `no_supera`.**
- **No hay modelo de 1 h:** el laboratorio de 1 h se retiró el 17/11.

**Garantías:**
- sin modelo, con un modelo corrupto o de otra versión de rasgos → no entra nadie, y se indica en el panel;
- datos externos viejos → esos rasgos quedan «sin dato», y sin datos externos frescos no decide;
- error interno → no entra.
- La protección (filtros, límites y stops) se aplica después del cerebro.

**En simulado** (`cerebro.exploracion_simulado: ["4h"]`) el cerebro de 4 h decide aunque no supere, como
«exploración». En real esa opción no tiene efecto: solo decidiría un modelo `supera`.

**Resultados de laboratorio del 22/11/2026** (fuera de muestra / holdout):

| Variante | Fuera de muestra | Holdout | Veredicto |
|---|---|---|---|
| Operar todas las candidatas | n 4 767, −0,057 R, t −3,59 | n 1 251, +0,034 R | — (línea de comparación) |
| `cerebro_con_todo` | n 1 036, **+0,090 R, t 2,75** (listón 2,91), t por días 1,32 (listón 2,92), IC al 90 % [−0,004; +0,193] | n 363, +0,072 R, t 1,23 | **no_supera** |
| `cerebro_solo_hyperliquid` | n 757, −0,045 R, t −1,20 | n 280, +0,100 R | **no_supera** |

**Cartera con los límites reales:**
- `cerebro_con_todo`: −1,65 %, caída del 28,6 %.
- `cerebro_solo_hyperliquid`: −25,4 %.

**Riesgo de sesgo abierto (D6 de la auditoría interna):** la ventaja de «con todo» frente a «solo Hyperliquid» podría
deberse a la historia sustituida por Binance/Bybit. No está resuelto.

**Otros componentes de decisión:**
- **Memoria por vecinos** (`aprendizaje.py`): 20 vecinos, ≥ 8 casos y R mínimo de 0,05. Ajusta el tamaño entre ×0,5
  y ×1 y, en real, veta.
- **Vigilancia** (`vigilancia.py`): reduce el tamaño a ×0,5 si una estrategia en uso se degrada; nunca lo aumenta.
- **IA (Groq):** solo informa y es solo lectura. Analista, revisor, vigilante explicativo y «escéptico en sombra». No
  tiene acceso a órdenes, configuración ni promoción.

---

## 6. Integraciones con exchanges

### 6.1 Hyperliquid (único exchange donde se opera)

**Cliente y lectura:**
- SDK oficial `hyperliquid-python-sdk 0.24.0` y peticiones directas a `https://api.hyperliquid.xyz/info`.
- Peticiones de lectura usadas:
  - `metaAndAssetCtxs` (en caché 10 s en `papel._ctx`);
  - `candleSnapshot`, `l2Book` (también agregado con `nSigFigs`), `fundingHistory`, `trades`;
  - `userFills`, `userFillsByTime`;
  - `spotMetaAndAssetCtxs` (el carry, emparejando por nombre), `perpDexs`;
  - `userRole` (`bot.py`, solo al arrancar en real).
- Los pesos de cada tipo de petición están en el comentario de cabecera de `limitador.py`.
- WebSocket para el seguimiento de ballenas en tiempo real (máximo 15).

**Peticiones de escritura** (`order`, `cancel`, `expiresAfter`):
- Existen en `ejecucion.py`, pero **en simulado van a `papel.py`**, que emula el exchange.
- `InfoConPapel.open_orders` se conserva a propósito: sin él, la consulta iría a la API real.
- En shadow ni siquiera se crea el cliente de órdenes.

**Límite de peticiones** (`limitador.py`): peso acumulado por tipo en `estado_sistema.json → contadores → peso_por_tipo`.
- El funding de 90 días se guarda en `funding_vivo_cache.json` (R-09), para no volver a descargarlo en cada arranque.

**Comisiones en simulado:** 0,015 % maker / 0,045 % taker (nivel 0). En real se leerían de la cuenta.

### 6.2 Cómo simula la cuenta ficticia (`papel.py`, MODELO 3)

- **IOC y stops:** se ejecutan contra una foto del libro real de 20 niveles, o del libro agregado si no basta. El stop
  salta con la **marca**.
- **Órdenes límite en reposo:** se llenan solo si hay contrapartida real a su precio o una operación real se imprimió
  peor (en velas de 1 min posteriores a la orden).
- **Funding:** horario, con la tasa real.
- **Liquidación:** estimada.
- **Hueco del bot parado** (`papel._recuperar_hueco`, más de 3 min sin procesar): se repasan las velas de 1 min y se
  ejecutan los stops y objetivos que se habrían disparado. Es una estimación.
- **Lo que no modela:**
  - la latencia ni la posición en la cola;
  - la reacción del libro a la propia orden;
  - el precio de marca entre muestreos (se comprueba cada pocos segundos, no en cada tick).

### 6.3 Binance y Bybit (solo datos públicos de lectura)

- Endpoints públicos `api.binance.com`, `fapi.binance.com` y `api.bybit.com`, sin cuenta, sin claves y sin enviar
  nunca nada.
- **Laboratorio:** historia de velas y funding (`historia_externa.py`), con caché en `datos_backtest/externo/`.
- **En vivo** (`contexto_externo.py`, cada 5 min): precio frente a Hyperliquid, funding y su diferencia, interés
  abierto, flujo comprador y cuota de volumen.
  - Se archiva en `datos_mercado/externo_*.jsonl`.
  - Alimenta los rasgos del cerebro.
  - Si fallan, el cerebro se abstiene.

### 6.4 Otros servicios

| Servicio | Uso | Estado |
|---|---|---|
| CoinGlass (`coinglass.py`) | Opcional, con `COINGLASS_API_KEY` | Sin clave |
| Groq | IA de solo lectura (`GROQ_API_KEY`) | Configurado |
| Telegram | Avisos (`notificaciones.py`) | **Sin `TELEGRAM_TOKEN` ni `TELEGRAM_CHAT_ID`** |
| Healthchecks.io | Aviso externo de caída (`HEALTHCHECK_URL`) | Sin configurar |
| Cloudflare Tunnel | Exposición del panel | Activo en el PC según la auditoría del 19/11; no reverificado hoy |
| Cloudflare R2 | Copias de seguridad (scripts en `despliegue/`) | Solo para el VPS; no configurado |

---

## 7. Decisiones técnicas y financieras, y su justificación

| Fecha | Decisión | Justificación declarada |
|---|---|---|
| Base | Solo simulado/shadow hasta que algo supere el laboratorio y lo apruebe Roberto | Ninguna estrategia tiene ventaja demostrada |
| Base | Sin `scheduleCancel` | Cancelaría también los stops justo cuando el bot no responde |
| Base | Laboratorio con entrada a mercado en la vela siguiente | Es más prudente que el ALO real |
| Base | El funding previsto entra en el tamaño | Evitar que el funding en contra rompa el riesgo planificado |
| 28/10 | Puesta a cero de la cuenta simulada (232 $) | Empezar la evidencia con la versión rediseñada; queda archivado en `archivo_reinicios/` |
| 03/11 | Exploración amplia al 0,5 %, como máximo 4 abiertas | Aprender más deprisa en simulado |
| 04/11 | 3 % de riesgo por operación, 9 % abierto, 6 posiciones, 5×, universo desde 3 M$ con memecoins | Petición de Roberto; confirmado el 19/11 |
| 13/11 | Estrategias de 1 h apagadas; filtro de régimen de BTC; rasgos recortados a ±3; cartera de funding en simulado | Las de 1 h eran negativas; los largos perdían en un mercado bajista |
| 14/11 | Momentum v2: break-even y trailing a 1,5 R | Proteger ganancias; valores de criterio, sin optimizar |
| 17/11 | Búsqueda congelada, prerregistro, laboratorio solo con 4 h, meseta y prueba de lookahead | Cada idea nueva subía el listón de todas (1 098 variantes) |
| 18/11 | El riesgo desconocido nunca cuenta como 0 | Defecto equivalente a una issue conocida de otro proyecto |
| 19/11 | Listón de t por familias (27) en lugar de variantes (1 098); simulador MODELO 3; ballenas operan en simulado y vetan; piramidación en simulado; `piloto_real` = simulado | Decisiones de Roberto tras el estudio `ESTUDIO_BOT_2026-11-19.md`. El cambio del listón **lo hace menos exigente** (de t ≥ 4,2 a t ≥ 3,02 con 60 operaciones) |
| 19/11 | Arreglos R-01, R-05 y R-08 de la auditoría | Ampliación sin controles, salto agregado sin tope y operación kPEPE huérfana |
| 19/11 | Carry solo dentro de Hyperliquid (nada con Binance) | Decisión de Roberto |
| 21/11 | R-07, R-09, R-10 y R-14; migración prevista a Hetzner (en lugar de Oracle) | Mejoras de la auditoría; máquina siempre encendida |
| 22/11 | Ideas tomadas de HyperGrok (solo controles: nota de proceso, escéptico, calendario macro, caducidad de envíos, manifiesto de datos, tramos de margen, techos duros) | El código externo se leyó sin ejecutarlo; el estudio macro **no mejora** (p = 0,94) y no se activa |
| 22/11 | Techos del real en 3 % / 9 % / 5× / 6 / 10 % diario | Roberto prefiere mantener estos y no los de HyperGrok (2 % / 6 %) |
| 23/11 | Apagadas `retroceso_1h`, `retroceso_4h`, `funding_4h` y `reversion_4h` (siguen en sombra) | Negativas en el laboratorio y en vivo (ver 8.1) |

**Consecuencia para la evidencia:** cada cambio de código o configuración que decide cambia la huella y **reinicia la
evidencia válida para promoción**.

---

## 8. Resultados históricos y de paper trading

**Ninguna cifra de esta sección indica rentabilidad demostrada.** Las muestras en vivo son pequeñas (< 30 por grupo
salvo en el total).

### 8.1 Laboratorio (ejecución `lab-20261122T030003Z`, 22/11/2026)

**Criterio:** walk-forward de 5 pliegues, holdout del 15 %, embargo de 24 velas, 27 familias efectivas y 1 098
variantes totales. **Elegidos: ninguno.**

| Estrategia | Fuera de muestra | Holdout | Veredicto |
|---|---|---|---|
| `ruptura_4h` | n 1 652, +0,006 R, t 0,21 | n 669, −0,004 R | no_supera |
| `retroceso_4h` | n 1 511, −0,096 R, t −3,84 | n 110, −0,167 R | no_supera |
| `reversion_4h` | n 126, −0,096 R, t −1,46 | n 11, −0,618 R | no_supera |
| `funding_4h` | n 127, −0,134 R, t −1,53 | n 39, −0,107 R | no_supera |
| `fuerza_4h` | n 196, +0,088 R, t 0,59 | n 56, +0,146 R | no_supera (la «más prometedor» según el informe) |
| `momentum_4h` | n 1 155, −0,107 R, t −3,35 | n 366, +0,180 R | no_supera |
| `ballenas_1h` / `liquidaciones_1h` | Sin evaluación completa | — | no_supera |

- **Holdout fresco** (`n_holdout_fresco`): 0 en todas, porque el holdout está sellado.
- **Cerebro:** ver la sección 5.
- **Prerregistro:**
  - `fuerza_4h`: «acumulando», 1 operación de 30.
  - `carry_realista`: «acumulando», 0 de 30.
- **Fuentes:**
  - histórico de ejecuciones en `registro/laboratorio_ejecuciones.jsonl` y `registro/laboratorio_semanal.jsonl`;
  - registros en `registro/laboratorio_semanal_*.log`.
- **Avisos del propio laboratorio:**
  - sesgo de supervivencia, porque solo usa monedas que existen hoy;
  - dentro de una vela, si tocó stop y objetivo, se cuenta el stop.

**Investigación (estudios):**
- carry de funding realista: ~12 %/año en pruebas y ~7 % en holdout (fuera de este laboratorio);
- estudio macro: no mejora;
- resultados en `registro/estudio_*.json`.

### 8.2 Paper trading (ledger, cuenta simulada)

**Ledger completo:**
- 1 710 `trade_id`: 1 665 señales `rechazada`, 42 `cerrada` y 3 abiertas (`completada`).
- 0 líneas corruptas; todas con origen `simulado`.
- De las 40 cerradas con fills, una tiene `contabilidad: incompleta` (kPEPE) y queda sin R.

| Periodo | n con R | R neto medio | t | Ganadoras | PnL neto | Comisiones | Funding |
|---|---|---|---|---|---|---|---|
| Todo (23/10 → 23/11) | 39 | −0,071 | −0,39 | 36 % | +19,74 $ | 0,82 $ | +0,02 $ |
| Antes de la puesta a cero (28/10 22:44 UTC) | 9 | −0,793 | −4,07 | 11 % | −10,10 $ | 0,14 $ | +0,02 $ |
| **Desde la puesta a cero** | **30** | **+0,145** | **0,67** | **43 %** | **+29,84 $** | 0,68 $ | 0,00 $ |

**Desde la puesta a cero, por estrategia:**

| Estrategia | n | R medio | PnL neto |
|---|---|---|---|
| `ruptura_4h` | 11 | +0,391 | +11,32 $ |
| `ruptura_1h` | 5 | −0,712 | −3,34 $ |
| `momentum_4h` | 4 | +1,347 | +26,75 $ |
| `retroceso_1h` | 4 | −0,347 | −1,73 $ |
| `retroceso_4h` | 2 | −1,021 | −5,24 $ |
| `fuerza_1h` | 2 | −1,098 | −1,43 $ |
| `ballenas_1h` | 2 | +1,926 | +3,52 $ |

**Desde la puesta a cero, por vía:**

| Vía | n | R medio | PnL neto |
|---|---|---|---|
| `cerebro_exploracion` | 16 | +0,382 (t 1,36) | +32,08 $ |
| `memoria` | 7 | −0,822 | −4,77 $ |
| `exploracion_amplia` | 7 | +0,571 | +2,52 $ |
| `cerebro` (modelo que supera) | 0 | — | — |

**Desde la puesta a cero, por lado:**

| Lado | n | R medio | Ganadoras | PnL neto |
|---|---|---|---|---|
| Cortos | 17 | +0,834 (t 3,35) | 71 % | +40,84 $ |
| Largos | 13 | −0,756 (t −4,01) | 8 % | −11,00 $ |

- **Concentración:** las mejores son ENA momentum (+12,80 $), UNI momentum (+9,88 $) y ARB ruptura (+4,79 $). La
  peor, ENA retroceso_4h (−4,34 $).
- **Causas de salida:**

  | Causa | Operaciones |
  |---|---|
  | Stop-loss | 12 |
  | Tiempo máximo | 11 |
  | Stop sin pérdidas | 4 |
  | Objetivo o stop dinámico | 3 |
- **Cuenta a fecha de corte** (`panel_datos.json`):
  - valor 264,25 $, libre 218,25 $, inicial 232 $, máximo 270,08 $;
  - riesgo abierto 1,37 %, exposición bruta 16,8 % y neta −8,6 %.
- **Abiertas** (datos de `panel_datos.json`):

  | Moneda | Lado | Origen | Vía | Desde | No realizado |
  |---|---|---|---|---|---|
  | BNB | corto | `fuerza_4h` | exploración amplia | 19/11 | +1,63 $ |
  | VVV | corto | cartera de funding | `cartera_funding` | 23/11 | +0,32 $ |
  | kBONK | largo | cartera de funding | `cartera_funding` | 23/11 | +0,47 $ |
- **Carry de dos patas** (`carry_estado.json`): 0 cierres. La cuenta sigue en 200 $ porque ninguna moneda llega al
  listón del 20 %/año.

**Lectura de la auditoría interna (19/11), aún válida:**
- el beneficio viene de cortos en un mercado bajista y del reparto del tamaño, no de una ventaja medible en R;
- las vías de simulado (exploración y cartera) no existirían en real.

### 8.3 Sombras (descartes seguidos, `aprendizaje.json`)

Lectura del 23/11 en el panel → «Sónar de sombras», con 650 sombras cerradas desde la puesta a cero. Los resultados de
las sombras son **modelados**, por muestreo puntual.

| Grupo | Resultado | Lectura |
|---|---|---|
| Conjunto | +0,07 R, t 1,7 | Empate |
| «El cerebro dijo no» | −0,20 R, t −2,5 | El filtro acierta al descartar |
| «Sin hueco o demasiado riesgo» | +0,48 R, t 3,6 | Descarta operaciones que luego ganan; son límites de riesgo y no se tocan |
| `funding_1h` (apagada) | +0,23 R en 81, t 2,3 | Contradice al laboratorio (−0,11 R) |
| `momentum_4h` | +1,12 R en 59 | — |

---

## 9. Problemas conocidos

Los identificadores entre paréntesis son los de `audit/ballenas/README.md`.

### 9.1 Seguridad y operación

- **Panel por túnel sin contraseña** (D2). `panel.tunel_sin_clave: true` en `config.json`, y `PANEL_PASSWORD` sin
  valor en `.env`. Por el túnel de Cloudflare se ven, en solo lectura, saldo, posiciones y estrategias.
- **Sin alertas externas** (D3): Telegram sin claves y `HEALTHCHECK_URL` sin valor.
- **Sin copias de seguridad en Windows** (D4). Hay scripts de R2, pero solo para el VPS.
- **PC doméstico:**
  - las caídas de luz o de red y las suspensiones paran el bot;
  - con el bot parado no corren los stops simulados, que se recuperan después de forma estimada (R-14).
- **Dependencias sin auditar** (D13): `pip-audit` no instalado.
- **Repositorio público** desde el 24/11:
  - incluye ledger, estado, aprendizaje, datos de mercado, documentación con el nombre del propietario y rutas locales;
  - `.env`, `.venv`, `datos_backtest/` y los logs están excluidos por `.gitignore`;
  - se revisaron los secretos antes de subir y no se encontró ninguno.
- **Repositorio git vacío en `C:\Users\rober`** (la carpeta de usuario entera), sin commits ni remoto, ajeno al
  proyecto. Sin efecto, salvo que alguien hiciera `git add` allí.

### 9.2 Validación y estrategia

- **Ninguna ventaja demostrada:** todas las estrategias y el cerebro dan `no_supera`.
- **Sesgo posible del cerebro con la historia sustituida** (D6, R-06 sin resolver).
- **Sesgo de supervivencia** en el laboratorio: solo usa monedas que existen hoy.
- **Listón de t relajado el 19/11** (de variantes a familias). La decisión está documentada, pero reduce la exigencia.
- **Contradicción entre sombra y laboratorio** en `funding_1h` y `momentum_4h`.
- **En simulado se opera con modelos y estrategias que no superan**, por las vías de exploración (D12, en parte
  mitigado el 23/11).
- **Evidencia mezclada por vías** (D7): mitigado con `op["via"]` y el panel «Por vía».
- **Incidente del 17/11:** una prueba de humo escribió un veredicto falso de preregistro («fuerza_4h confirmada»). Se
  anuló el 21/11 y se arregló la ruta.

### 9.3 Ejecución y simulación

- **El código de órdenes no está probado contra la API real** de Hyperliquid, solo con exchanges falsos.
- **El simulador no modela latencia, cola ni impacto propio**, y la liquidación es estimada.
- **Calibración pendiente:** la nota de proceso calibra el deslizamiento por tipo de entrada, pero no hay datos reales
  con los que compararlo.
- **Incidencia del 19/11:** el piloto se recargó sin arranque manual tras un `/aplicarconfig`. Sin efecto en simulado;
  documentada en `CLAUDE.md`.

### 9.4 Código

- `bot.py` (2 388 líneas) y `gestor.py` (1 554) son monolíticos. `procesar_candidatas` tiene unas 240 líneas.
- El estado está repartido en decenas de JSON sin esquema de base de datos.

---

## 10. Funcionalidades pendientes

**Decisiones del propietario** (`PENDIENTE_ROBERTO.md`):

1. **Límites del primer real** (B2). La recomendación interna era una pérdida máxima de ~20 %, solo BTC/ETH/SOL/HYPE y
   2–3×. **Sin decidir.**
2. **`PANEL_PASSWORD`, `TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID` y `HEALTHCHECK_URL`:** debe ponerlos Roberto.
3. **Migración a Hetzner:** crear la máquina, pasar las pruebas en Linux y mover el túnel.
4. **Exploración de estrategias negativas** (B1): en parte decidido el 23/11 con las cuatro estrategias apagadas.

**Técnicas:**

5. Que el carry de dos patas acumule cierres. Más adelante, decidir si pasa por `promocion.py` (hoy está fuera de la
   huella y del ledger).
6. Las muestras prerregistradas (`fuerza_4h`, `carry_realista`): 30 operaciones y 20 días cada una.
7. Validar el cerebro sin historia sustituida (R-06) y por régimen.
8. **Cerebro de 1 h:** no se regenera. Haría falta volver a añadir «1h» a `laboratorio.intervalos_estrategias`.
9. Calibrar la simulación con unas pocas operaciones reales muy pequeñas. Solo con algo validado y con aprobación
   expresa.
10. Auditoría de dependencias (`pip-audit`).
11. El resto de tareas de `audit/ballenas/09-roadmap.md` no implementadas (R-02, R-03, R-04, R-06, R-12, R-13, R-15).

---

## 11. Localización de logs, históricos y datos

No hay base de datos relacional: todo el estado vive en archivos.

| Ruta | Contenido | En el repo |
|---|---|---|
| `registro/ledger.jsonl` (+ rotados) | **Verdad contable**: eventos versionados por `trade_id` | Sí |
| `registro/feed.jsonl` (+ `feed-*.jsonl`) | Feed «Señales en vivo» | Sí |
| `registro/laboratorio_ejecuciones.jsonl` | Reproducibilidad de cada laboratorio (semilla, huellas, universo, resultados) | Sí |
| `registro/laboratorio_semanal*.{jsonl,log}` | Laboratorio programado | Sí |
| `registro/investigacion_informe.{md,json}`, `registro/estudio_*.json` | Investigación y estudios | Sí |
| `registro/cambios_config.jsonl` | Cambios de configuración desde el panel | Hoy no existe: se crea con el primer cambio guardado desde el panel |
| `registro/carry.jsonl` | Registro de eventos del carry | Hoy no existe: el carry aún no ha abierto ni cerrado nada |
| `registro/analista/` | Salidas del analista de IA y del escéptico | Sí |
| `bot.log` (rota 5 MB × 3, horas en UTC) y `logs/bot.jsonl` (log estructurado, rota 10 MB × 5) | Log técnico; ambos ocultan secretos (`observabilidad.configurar_logs`) | **No** (`.gitignore`) |
| `papel.json` | Cuenta simulada (posiciones, órdenes, fills, funding, `ajustes_capital`, `huecos_recuperados`) | Sí |
| `estado.json`, `estado-simulado-*.json` | Estado del bot y archivos de cambio de modo y reinicios | Sí |
| `panel_datos.json` | Foto del estado para el panel | Sí |
| `estado_sistema.json`, `incidentes.json` | Salud, contadores y peso de peticiones; incidentes | Sí |
| `aprendizaje.json`, `aprendizaje_lab.json` | Memoria por vecinos, sombras y probador en vivo | Sí |
| `estrategia_elegida.json` | Veredictos del último laboratorio | Sí |
| `cerebro_modelo.json` | Modelo vigente del cerebro | Sí |
| `laboratorio_holdout.json`, `laboratorio_variantes.json` | Holdout ya consultado; registro de variantes y familias | Sí |
| `promociones.json`, `preregistro_estado.json` | Evidencia y etapas de promoción; prerregistro | Sí |
| `investigacion.json` | Aspirantes y cementerio | Sí |
| `carry_estado.json`, `papel_carry.json`, `papel_spot.json` | Estado y cuentas del carry | Sí |
| `datos_mercado/` (~205 MB) | Interés abierto, funding, operaciones grandes, contexto externo (`externo_*.jsonl`) y contado de HL | Sí |
| `datos_archivo/` (~99 MB) | Archivo propio de velas y libro de órdenes | Sí |
| `datos_backtest/` (~738 MB) | Caché regenerable del laboratorio (incluye `externo/`) | **No** |
| `funding_vivo_cache.json` | Caché del funding de 90 días | Sí |
| `archivo_reinicios/` | Puestas a cero de la cuenta simulada | Sí |
| `copias/` | Copia del código previa a la auditoría del 28/10 | Sí |
| `config_copias/` | Copias de `config.json` que guarda el editor del panel (las 30 últimas) | Hoy no existe: se crea con el primer cambio guardado desde el panel |
| `audit/ballenas/` | Auditoría interna del 19/11 | Sí |
| `.env` | Secretos (hoy solo `GROQ_API_KEY` tiene valor) | **No** (usar `.env.example`) |

---

## 12. Cómo ejecutar el bot y sus pruebas de forma segura

### 12.1 Reglas que el auditor debe respetar

- **No** poner `"modo": "real"`, no rellenar `HL_API_WALLET_KEY`, `HL_DIRECCION_CUENTA` ni `BOT_REAL_CONFIRMADO` y no
  conectar ninguna wallet.
- **No** usar `promocion.py aprobar`: queda registrado y altera la evidencia.
- **No** arrancar a la vez dos instancias sobre la misma cuenta o carpeta. Para experimentar, trabajar sobre una
  **copia** del repositorio, nunca sobre la carpeta en producción.
- Binance y Bybit: solo lectura pública, como ya hace el código.

### 12.2 Entorno

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-bloqueado.txt
cp .env.example .env
```

En Windows, `INICIAR.bat` hace todo esto y crea un acceso directo. En `.env` deben quedar vacías las variables de
real; las demás son opcionales.

### 12.3 Pruebas (sin red de órdenes ni claves)

```bash
.venv/Scripts/python -m unittest discover -s tests -t .
```

Resultado esperado a fecha de corte: `Ran 764 tests` / `OK`, en unos 100 s. Las pruebas usan `papel.py` y exchanges
falsos.

### 12.4 Comprobaciones sin operar

```bash
.venv/Scripts/python bot.py --validar-config
```

Valida la config y muestra los valores efectivos y su origen; no conecta ni opera.

```bash
.venv/Scripts/python promocion.py estado
```

Muestra la etapa de cada estrategia y la identidad del modelo. Es de solo lectura.

```bash
.venv/Scripts/python promocion.py requisitos momentum_4h
```

Muestra qué le falta a una estrategia para `apta_revision`.

```bash
.venv/Scripts/python informe.py
```

Resumen de lo aprendido.

### 12.5 Ejecutar en simulado

- Arranque con `INICIAR.bat` (Windows) o `.venv/Scripts/python bot.py` con `"modo": "simulado"`. Panel en
  `http://127.0.0.1:8080`.
- Hace peticiones **de lectura** a la API pública de Hyperliquid, Binance y Bybit; las órdenes van a `papel.json`.
- Para empezar de cero en una copia: con el bot parado, borrar `papel.json`, `estado.json` y `panel_datos.json`.
- **Reinicio ordenado:** escribir `comandos_panel.json` **sin BOM** con `[{"cmd": "/aplicarconfig", "id": "x"}]`. El
  bot sale con código 4 y el lanzador lo rearranca. El resultado queda en `comandos_resultado.json`.

### 12.6 Laboratorio e investigación

```bash
.venv/Scripts/python laboratorio.py --rapido
```

Versión de prueba con menos monedas y parámetros.

```bash
.venv/Scripts/python laboratorio.py
```

Laboratorio completo, de ~1,5 h o más. Escribe `estrategia_elegida.json` y `cerebro_modelo.json`, y gasta holdout.
**En la carpeta en producción cambia el modelo que usa el bot: ejecutarlo solo en una copia.**

```bash
.venv/Scripts/python investigacion.py
```

Investigación de ideas nuevas. Hoy la búsqueda está congelada.

### 12.7 Shadow

`"modo": "shadow"` no crea el cliente de órdenes: es el modo más restrictivo para observar con datos reales.
