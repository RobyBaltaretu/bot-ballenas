# 01 — Inventario y cobertura

**Commit auditado:** `b8a9f8d` (rama `claude/audit-algo-trading-bot-nua1pw`), fecha de corte 24/11/2026.
**Estado de esta entrega:** auditoría **NO completada al 100 %** en revisión manual línea a línea (ver «Cobertura» y
`AUDIT_PROGRESS.md`). Las conclusiones financieras no dependen de los archivos pendientes (son panel, herramientas e
investigación clasificados por el propio bot como «sin efecto» en las decisiones), pero se dice explícitamente.

## 1. Estructura del repositorio

| Carpeta / grupo | Archivos | Contenido | Tratamiento |
|---|---|---|---|
| Raíz `*.py` | 59 | Código del bot, laboratorio, panel, IA | Auditado (niveles L/F/E) |
| `carry/` | 7 | Carry de funding de dos patas (proceso aparte) | `logica.py` L; resto E |
| `estudios_ext/` | 8 | Estudios externos (carry 2026, factor de funding, paridad, tendencia) | E |
| `tests/` | 69 (8 995 líneas) | `unittest` | Ejecutadas: **764 OK en 64,7 s** (Python 3.13, Linux) |
| `panel_web/` + `panel.html` | 32 (8 638 líneas JS/HTML/CSS) | Panel web | Muestreado (CSP, `dom.h`, comandos); no línea a línea |
| `despliegue/` | 30 | systemd, PowerShell, guías VPS | F (servicio, instalador, lanzador) |
| `herramientas/` | 18 `.bat` | Accesos directos de Windows | E |
| `copias/antes_auditoria_20261028/` | 43 | Copia del código anterior | **Excluido**: no se importa (verificado con grep) |
| Datos (`datos_mercado/` 206 MB, `datos_archivo/` 100 MB, `registro/` 38 MB, JSON de estado) | ~400 | Ledger, velas, OI, sombras | Usados como evidencia (no se auditan como código) |
| `datos_backtest/` (~738 MB) | — | Caché del laboratorio | **No está en el repositorio** (`.gitignore`): el laboratorio NO es reproducible desde el repo |

## 2. Configuración, entorno y dependencias

- `config.json`: `modo: simulado`, riesgo 3 % / 9 % / 6 posiciones / 5×, `panel.tunel_sin_clave: true`. Valores
  efectivos obtenidos con `bot.py --validar-config` en una copia (ver 05).
- `.env`: no existe en el repo; `.env.example` sin valores. Barrido de patrones de secretos (Groq `gsk_`, tokens de
  Telegram, claves privadas de 64 hex, AWS/R2): **ninguno** versionado. 2 544 direcciones `0x…` públicas de cuentas de
  Hyperliquid (ballenas y operaciones grandes) en datos: no son secretos.
- `.mcp.json` versionado con rutas locales (`C:/Users/…`) y etiquetas de cliente (no secretas).
- Dependencias directas: `hyperliquid-python-sdk 0.24.0` (última en PyPI, 04/06/2026), `python-dotenv 1.2.4`,
  `requests 2.34.2`. `pip-audit` sobre `requirements-bloqueado.txt` (servicio PyPI, 24/11/2026): **sin vulnerabilidades
  conocidas**.
- Sin base de datos: todo el estado en JSON/JSONL con escritura atómica (`*.tmp` + reemplazo).

## 3. Pruebas y comprobaciones ejecutadas (todas en una COPIA del repositorio)

| Comando | Resultado |
|---|---|
| `python -m unittest discover -s tests -t .` | 764 pruebas OK, 64,7 s. Varias intentan red real a `api.hyperliquid.xyz` (T-09) |
| `python bot.py --validar-config` | Válida; volcado de los 37 límites efectivos |
| `ruff check --select E9,F,B,…` | 3 avisos reales menores (import sin usar, variable sin usar); B023 y SHA1: falsos positivos revisados |
| `bandit -ll` | SHA1 para claves de caché (no seguridad), bind 0.0.0.0 en un mensaje: sin hallazgos reales |
| `pip-audit` | Sin vulnerabilidades conocidas |
| `experimentos/forense_ledger.py` | Reconstrucción independiente del ledger = cifras declaradas |
| `experimentos/sesgo_sombras.py` | Sesgo de las sombras +0,123 R/op |
| `experimentos/backtest_independiente.py` | 20 monedas Binance 2021–2026 |

## 4. Limitaciones de acceso y entorno

- Red: `api.hyperliquid.xyz` y `data.binance.vision` accesibles (entorno nuevo aprobado). `api.binance.com`,
  `fapi.binance.com` (451) y `api.bybit.com` (403) **bloqueados por geografía del servidor**: no se pudo reproducir la
  historia «ampliada» del laboratorio ni el contexto externo en vivo.
- No se ejecutó el bot en vivo (ni siquiera en simulado) para no crear una segunda instancia ni gastar el holdout.
- No se ejecutó el laboratorio completo (gasta holdout y reescribe `cerebro_modelo.json`); su caché no está en el repo.
- Sin acceso al PC de producción ni a `bot.log` (excluido del repo).

## 5. Cobertura por archivo

Niveles: **L** = leído línea a línea completo · **F** = secciones críticas leídas + análisis estático · **E** = solo
análisis estático (ruff/bandit) y lectura de su cabecera. «Pruebas»: la batería completa se ejecutó; no se midió
cobertura por línea (no hay `coverage` en el entorno del proyecto).

| Nivel | Archivos | Líneas | % de líneas |
|---|---|---|---|
| L | 16 | 8 104 | 36 % |
| F | 9 | 6 367 | 28 % |
| E | 42 | 8 015 | 36 % |
| **Total código propio Python** | **67** | **22 486** | 100 % inventariado |

| Archivo | Líneas | Funciones | Responsabilidad | Revisión | Hallazgos | Pruebas |
|---|---|---|---|---|---|---|
| `analista_ia.py` | 739 | 42 | prompts, escéptico, aislamiento | F | IA-01..IA-03 | ejecutadas (764 OK) |
| `aprendizaje.py` | 338 | 21 | Memoria kNN, sombras, probador | L | A-01,Q-07 | ejecutadas (764 OK) |
| `archivo.py` | 207 | 13 | Archivo propio de datos de mercado (para que el laboratorio tenga más  | E | — | ejecutadas (764 OK) |
| `ballenas.py` | 133 | 10 | Flujo de ballenas | L | W-02 | ejecutadas (764 OK) |
| `bot.py` | 2389 | 94 | Orquestación, decisión de entradas, comandos | L | T-03,T-04,S-01 | ejecutadas (764 OK) |
| `calendario_macro.py` | 104 | 8 | Calendario de citas macro de EE. UU. que mueven las cripto: decisiones | E | — | ejecutadas (764 OK) |
| `carry/__init__.py` | 13 | 0 | Carry de funding con dos patas (perpetuo corto + contado largo), PREPA | E | — | ejecutadas (764 OK) |
| `carry/ejecucion.py` | 109 | 5 | Fase 2 del carry: abrir y cerrar las DOS patas con atomicidad razonabl | E | — | ejecutadas (764 OK) |
| `carry/logica.py` | 147 | 8 | Lógica pura del carry | L | — | ejecutadas (764 OK) |
| `carry/motor.py` | 340 | 20 | Fase 3 del carry: el motor SIMULADO que lo une todo. Dinero ficticio c | E | — | ejecutadas (764 OK) |
| `carry/papel_perp.py` | 112 | 8 | Fase 3 del carry: pata CORTA del perpetuo, SIMULADA. Dinero ficticio;  | E | — | ejecutadas (764 OK) |
| `carry/papel_spot.py` | 109 | 7 | Fase 2 del carry: cuenta de CONTADO SIMULADA. Dinero ficticio; no habl | E | — | ejecutadas (764 OK) |
| `carry/terreno.py` | 158 | 8 | Fase 0 del carry: verificar el terreno. SOLO LECTURA de la API pública | E | — | ejecutadas (764 OK) |
| `cartera_funding.py` | 122 | 8 | cartera semanal de funding | F | S-04 | ejecutadas (764 OK) |
| `cerebro.py` | 144 | 10 | Ridge, walk-forward del cerebro | L | C-01..C-03 | ejecutadas (764 OK) |
| `cerebro_vivo.py` | 177 | 10 | Decisión en vivo, falla cerrado | L | — | ejecutadas (764 OK) |
| `coinglass.py` | 135 | 6 | CoinGlass API v4: fuente OPCIONAL de SOLO LECTURA para investigación y | E | — | ejecutadas (764 OK) |
| `compat.py` | 71 | 4 | Detalles para que el bot funcione igual en Windows, macOS y Linux. | E | — | ejecutadas (764 OK) |
| `comprobar.py` | 186 | 9 | Comprobaciones de despliegue (Windows y Linux). No conecta con Hyperli | E | — | ejecutadas (764 OK) |
| `config_panel.py` | 431 | 15 | Editar la configuración desde el panel, con seguridad. | E | — | ejecutadas (764 OK) |
| `configuracion.py` | 619 | 15 | Configuración del bot: una sola fuente de verdad por parámetro, migrac | E | — | ejecutadas (764 OK) |
| `contabilidad.py` | 87 | 4 | PnL, comisiones, funding | L | — | ejecutadas (764 OK) |
| `contexto_externo.py` | 305 | 17 | Binance/Bybit en vivo | F | W-04 | ejecutadas (764 OK) |
| `datos.py` | 181 | 10 | Descarga de datos públicos de Hyperliquid con caché en disco y respeto | E | — | ejecutadas (764 OK) |
| `despliegue/avisos.py` | 33 | 1 | Envía un aviso por Telegram con la configuración del bot (.env). Lo us | E | — | ejecutadas (764 OK) |
| `diagnostico.py` | 113 | 3 | Exporta un DIAGNÓSTICO redactado del bot (para revisar o compartir sin | E | — | ejecutadas (764 OK) |
| `ejecucion.py` | 481 | 35 | CLOID, estados de orden, cancelación verificada | L | — | ejecutadas (764 OK) |
| `estrategia.py` | 267 | 18 | SimSalida, factor de capital, correlación | L | T-04,T-05,T-06 | ejecutadas (764 OK) |
| `estudios.py` | 120 | 7 | Estudios comparativos del laboratorio (solo informe: no cambian nada n | E | — | ejecutadas (764 OK) |
| `estudios_ext/__init__.py` | 8 | 0 | Estudios externos del bot (13/11/2026). SOLO INVESTIGACIÓN: leen caché | E | — | ejecutadas (764 OK) |
| `estudios_ext/carry2026.py` | 158 | 9 | ESTUDIO C — El carry de funding «realista» del laboratorio, medido por | E | — | ejecutadas (764 OK) |
| `estudios_ext/datos.py` | 104 | 11 | Lectura de las cachés locales de Binance (velas de 4 h, funding de 8 h | E | — | ejecutadas (764 OK) |
| `estudios_ext/factor_funding.py` | 167 | 7 | ESTUDIO B — Factor de funding entre monedas (solo perpetuos). SOLO INV | E | — | ejecutadas (764 OK) |
| `estudios_ext/metricas.py` | 140 | 12 | Métricas de una cartera diaria (solo estadística, sin datos de mercado | E | — | ejecutadas (764 OK) |
| `estudios_ext/paridad.py` | 192 | 10 | PARIDAD simulado ↔ laboratorio. SOLO LECTURA del ledger y de las velas | E | — | ejecutadas (764 OK) |
| `estudios_ext/rasgos.py` | 90 | 3 | RASGOS DEL CEREBRO: ¿lo que ve el cerebro en vivo se parece a lo que v | E | — | ejecutadas (764 OK) |
| `estudios_ext/tendencia.py` | 269 | 12 | ESTUDIO A — Tendencia lenta (conjunto de canales de Donchian). SOLO IN | E | — | ejecutadas (764 OK) |
| `feed.py` | 387 | 16 | Feed de «Señales en vivo»: flujo PERSISTENTE (append-only) de eventos  | E | — | ejecutadas (764 OK) |
| `gestor.py` | 1555 | 51 | Propiedad, stops verificados, conciliación, cierre, piramidación | L | Q-05,Q-06 | ejecutadas (764 OK) |
| `historia_externa.py` | 390 | 25 | Historia ampliada para el laboratorio con DATOS PÚBLICOS de Binance y  | E | — | ejecutadas (764 OK) |
| `informe.py` | 123 | 4 | Informe de lo que ha aprendido el bot.   Uso:  python informe.py | E | — | ejecutadas (764 OK) |
| `instancia.py` | 113 | 9 | Una sola instancia del bot por carpeta y por cuenta. | E | — | ejecutadas (764 OK) |
| `investigacion.py` | 807 | 28 | Departamento de investigación: busca estrategias nuevas por su cuenta, | E | — | ejecutadas (764 OK) |
| `laboratorio.py` | 1766 | 60 | walk_forward, simular, evaluar_cerebro, preparar_datos | F | V-01..V-04 | ejecutadas (764 OK) |
| `laboratorio_semanal.py` | 129 | 4 | Laboratorio semanal: pasa el laboratorio, lo compara con la ejecución  | E | — | ejecutadas (764 OK) |
| `ledger.py` | 403 | 18 | registro de eventos (verificado por reconstrucción independiente) | F | — | ejecutadas (764 OK) |
| `limitador.py` | 102 | 8 | Límite de peticiones a Hyperliquid: 1200 de "peso" por minuto y por IP | E | — | ejecutadas (764 OK) |
| `manifiesto_datos.py` | 110 | 6 | Manifiesto de los datos con que trabajó el laboratorio: cobertura, hue | E | — | ejecutadas (764 OK) |
| `mercado.py` | 303 | 17 | OI, operaciones grandes, liquidaciones, limpieza | F | W-03 | ejecutadas (764 OK) |
| `mercado_unificado.py` | 88 | 5 | Rasgos comunes lab/vivo | L | — | ejecutadas (764 OK) |
| `mesa.py` | 79 | 3 | MESA (18/11/2026, idea de un vídeo de un panel de «equipo de agentes») | E | — | ejecutadas (764 OK) |
| `motor.py` | 504 | 20 | Señales en vivo, universo, funding | L | T-02,T-07 | ejecutadas (764 OK) |
| `notificaciones.py` | 184 | 11 | Avisos y control del bot por Telegram. | E | — | ejecutadas (764 OK) |
| `observabilidad.py` | 279 | 15 | Observabilidad del SISTEMA (no del trading): salud de cada componente, | E | — | ejecutadas (764 OK) |
| `panel.py` | 1388 | 71 | autenticación, POST, túnel | F | SEG-01 | ejecutadas (764 OK) |
| `papel.py` | 652 | 45 | Cuenta simulada (MODELO 3) | L | T-01,T-03,T-08,T-11 | ejecutadas (764 OK) |
| `preregistro.py` | 133 | 7 | Hipótesis PRERREGISTRADAS (17/11/2026, pedido por Roberto): acelerar e | E | — | ejecutadas (764 OK) |
| `promocion.py` | 551 | 26 | requisitos apta_revision, aprobar, huella | F | T-12 | ejecutadas (764 OK) |
| `revision_proceso.py` | 220 | 8 | Nota de PROCESO de cada operación, separada de su resultado. | E | — | ejecutadas (764 OK) |
| `riesgo.py` | 550 | 34 | Tamaño, límites agregados, salto conjunto, techos real | L | — | ejecutadas (764 OK) |
| `seleccion.py` | 174 | 4 | Selección de ballenas y universo | L | W-01 | ejecutadas (764 OK) |
| `senales.py` | 418 | 29 | Módulos de señal e indicadores | L | — | ejecutadas (764 OK) |
| `sombras.py` | 176 | 8 | Sombras: lo que el bot dejó pasar. | E | — | ejecutadas (764 OK) |
| `taller.py` | 329 | 11 | TALLER (18/11/2026): revisión completa del sistema en un solo paso, en | E | — | ejecutadas (764 OK) |
| `validacion.py` | 790 | 52 | particiones, t, Bonferroni, bootstrap | F | V-02 | ejecutadas (764 OK) |
| `veredicto.py` | 168 | 10 | Veredicto de la prueba de dos semanas (04/11/2026 a 18/11/2026): ¿el b | E | — | ejecutadas (764 OK) |
| `vigilancia.py` | 117 | 3 | Vigilancia de degradación: ¿alguna estrategia en uso está rindiendo cl | E | — | ejecutadas (764 OK) |