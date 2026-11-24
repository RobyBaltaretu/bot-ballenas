# Prompt para Codex: auditoría independiente y evaluación de la auditoría de Claude

Instrucciones para la persona: entrega a Codex este repositorio en la rama `claude/audit-algo-trading-bot-nua1pw` (o
en la rama donde se haya fusionado la carpeta `auditoria_independiente/`) y pega como prompt **todo el texto que hay
entre las dos líneas `=====`**. Está escrito para que Codex no lea las conclusiones de Claude hasta haber terminado y
guardado su propio análisis.

=====

# Encargo

Eres un equipo de auditoría sénior (investigación cuantitativa, trading de derivados de cripto, microestructura,
ingeniería de software financiero, gestión de riesgos, ejecución de órdenes, IA aplicada a mercados, ciberseguridad y
fiabilidad). Vas a auditar de forma **independiente** un bot de trading de futuros perpetuos de Hyperliquid escrito en
Python, y después vas a **evaluar críticamente** la auditoría que hizo otro agente (Claude) sobre el mismo código.

Trabajas en dos fases y **el orden es obligatorio**:

- **Fase A — Auditoría propia, a ciegas.** No abras, leas, busques ni hagas `grep` dentro de
  `auditoria_independiente/` hasta haber terminado y guardado (commit) la fase A. Si lo abres por error, dilo en tu
  informe.
- **Fase B — Evaluación de la auditoría de Claude.** Solo después del commit de la fase A. Los documentos de la fase A
  no se editan en la fase B: cualquier corrección va en los documentos de la fase B.

Todo el trabajo y todos los informes en **español**, como el resto del proyecto. Tu objetivo no es coincidir con nadie
ni defender el código: es descubrir qué es verdad, qué aporta valor y qué no, con evidencia.

## Repositorio

- Código auditado: commit `b8a9f8d` («AUDIT_CONTEXT.md: contexto del bot para una auditoría externa»). Comprueba que
  desde ese commit solo ha cambiado la carpeta de la auditoría:
  `git diff --stat b8a9f8d -- . ':(exclude)auditoria_independiente'` debe salir vacío. Si no, audita el estado actual
  e indícalo.
- Documentación del propio proyecto (son **afirmaciones a verificar**, no hechos): `AUDIT_CONTEXT.md`, `LEEME.md`,
  `CLAUDE.md`, `audit/ballenas/` (auditoría interna del desarrollador), `INFORME_AUDITORIA_V12.md`,
  `ESTUDIO_BOT_2026-11-19.md`.
- Datos disponibles en el repo: `registro/ledger.jsonl` (verdad contable), `aprendizaje.json` (sombras),
  `estrategia_elegida.json` (último laboratorio), `cerebro_modelo.json`, `papel.json`, `estado.json`,
  `datos_archivo/velas/{1h,4h}/` (velas archivadas por el bot), `datos_mercado/` (interés abierto, flujo, contexto
  externo), `registro/analista/` (salidas de la IA).
- No está en el repo: `datos_backtest/` (caché de ~738 MB del laboratorio), `.env`, `bot.log`.

## Reglas de seguridad (obligatorias, sin excepciones)

1. **No envíes órdenes reales**, no conectes ninguna wallet, no pongas `"modo": "real"`, no rellenes
   `HL_API_WALLET_KEY`, `HL_DIRECCION_CUENTA` ni `BOT_REAL_CONFIRMADO`. No hagas ninguna llamada que pueda modificar una
   cuenta de Hyperliquid (el endpoint `/exchange` está prohibido; `/info` es de solo lectura y está permitido).
2. **No modifiques el código funcional ni `config.json`.** Esto es una auditoría. Si quieres ilustrar un arreglo,
   escríbelo como parche `.diff` dentro de tu carpeta de entrega, sin aplicarlo.
3. Trabaja sobre una **copia** del repositorio para ejecutar cualquier cosa (las pruebas y los experimentos escriben
   archivos). Nunca ejecutes `python laboratorio.py` completo en la carpeta original: gasta el holdout y reescribe
   `cerebro_modelo.json`. Nunca uses `promocion.py aprobar`. No arranques el bot en vivo.
4. No imprimas ni copies secretos; enmascáralos si aparecieran. Binance y Bybit: solo datos públicos de lectura.
5. No borres datos del repositorio.
6. No inventes cifras, fuentes ni resultados. Si algo no se puede verificar, márcalo como «no verificable» y explica
   por qué.

## Entorno sugerido

```bash
cp -r <repo> /tmp/copia_bot && cd /tmp/copia_bot
python3 -m venv .venv && .venv/bin/pip install -r requirements-bloqueado.txt
.venv/bin/python -m unittest discover -s tests -t .      # Claude obtuvo 764 OK en ~65 s con Python 3.13
.venv/bin/python bot.py --validar-config                  # límites efectivos; no conecta ni opera
```
Red: puede que tu entorno no tenga salida a internet o que Binance/Bybit estén bloqueados por geografía. Documenta lo
que no puedas alcanzar. Fuentes públicas útiles: `https://api.hyperliquid.xyz/info` (POST de lectura),
`https://data.binance.vision` (archivo histórico público).

## Fase A — Tu auditoría independiente (sin leer `auditoria_independiente/`)

Alcance: el 100 % del código propio (raíz `*.py`, `carry/`, `estudios_ext/`, `despliegue/`, `panel_web/`, `tests/`),
configuración, datos y documentación. Excluye con justificación lo que no audites (p. ej. `copias/` si compruebas que
no se importa). Si no llegas al 100 % línea a línea, dilo con cifras y deja un registro para continuar.

Recorre, como mínimo, estas fases:
0. Inventario y matriz de cobertura (archivo, líneas, funciones, responsabilidad, nivel de revisión real, hallazgos).
1. Ingeniería inversa del flujo real: dato de mercado → señal → filtros → decisión (incluida la IA) → tamaño →
   orden → protección → gestión → cierre → resultado contable → aprendizaje. Divergencias documentación/código.
2. Auditoría técnica línea a línea: errores lógicos y matemáticos, estados inconsistentes, órdenes duplicadas,
   posiciones huérfanas, recuperación tras reinicios, concurrencia, unidades y tiempo, errores silenciosos. Para cada
   hallazgo: archivo y líneas, explicación, causa raíz, consecuencia técnica y financiera, escenario, evidencia,
   severidad (P0–P3), corrección y prueba.
3. Datos y conexiones: Hyperliquid (contrastado con su documentación oficial: límites, comisiones, TP/SL, funding,
   precio de marca), Binance/Bybit, calidad, frescura, precio de señal frente a precio ejecutable.
4. Estrategias, una a una (también las apagadas): hipótesis, reglas, validez, resultados del laboratorio, de paper y
   de sombras; clasificación (mantener / optimizar / simplificar / rediseñar / limitar / desactivar / eliminar).
5. Reglas y validaciones: inventario completo, propósito, qué bloquean, qué dejan pasar, redundancias; distingue
   filtros de estrategia de controles de seguridad; ablación con los datos disponibles.
6. Seguimiento de ballenas: selección, interpretación de movimientos (abrir/aumentar/reducir/cerrar), replicabilidad,
   rentabilidad.
7. Intradía: qué es viable con esta infraestructura, costes y latencia.
8. Cerebro (modelo estadístico que decide) y analista de IA (LLM): qué deciden, prompts, calidad, coste, valor
   incremental; qué decisiones deben ser deterministas, estadísticas o prohibidas para la IA.
9. Régimen de mercado y orquestación de estrategias.
10. Backtesting y validación: look-ahead, fugas, supervivencia, sobreajuste, pruebas múltiples, costes, intravela,
    holdout, reproducibilidad; diferencias laboratorio / simulado / real.
11. Métricas con intervalos de confianza y suficiencia de la muestra; benchmarks (BTC comprar y mantener, tendencia
    simple de BTC, mercado en el mismo lado, no operar).
12. Riesgo y protección del capital, con escenarios extremos razonados contra el código.
13. Ejecución de órdenes.
14. Seguridad, estabilidad y observabilidad.
15. Investigación externa con trazabilidad (fuente, URL, fecha, evidencia, limitaciones, aplicabilidad). No inventes
    referencias.
16. Nuevas oportunidades (problema, hipótesis, evidencia, coste, criterios de éxito y abandono).
17. Forense de operaciones del ledger: causas de pérdida por impacto económico, ganadoras por azar o por decisión,
    descartes contrafactuales.
18. Red team: qué supuestos tendrían que fallar para perder dinero; escenarios de mayor fragilidad.
19. Arquitectura objetivo (la más sencilla que cumpla).

**Experimentos propios obligatorios** (con tus propios scripts, guardados en tu carpeta, reproducibles):
- Reconstrucción independiente del ledger y métricas con IC (no uses `ledger.Ledger.operaciones()` como única fuente).
- Separación de habilidad y mercado: exceso de cada operación frente a una referencia de mercado razonable.
- Fiabilidad de las «sombras» (`aprendizaje.json`): ¿son comparables con una simulación con máximos/mínimos?
- Al menos un backtest independiente de las estrategias activas con una fuente de datos que no sea la del
  laboratorio del bot, con parámetros fijos.

**Entregables de la fase A** en `auditoria_codex/fase_a/` (mismos nombres que se pidieron a Claude, para poder
compararlos): `00_resumen_ejecutivo.md`, `01_inventario_y_cobertura.md`, `02_arquitectura_y_funcionamiento.md`,
`03_auditoria_tecnica.md`, `04_auditoria_estrategias.md`, `05_auditoria_reglas.md`, `06_hyperliquid_y_ballenas.md`,
`07_inteligencia_artificial.md`, `08_investigacion_intradia.md`, `09_validacion_cuantitativa.md`,
`10_riesgos_y_seguridad.md`, `11_investigacion_externa.md`, `12_forense_operaciones.md`,
`13_arquitectura_objetivo.md`, `14_backlog_y_hoja_de_ruta.md` (con matriz maestra: ID, componente, estado, problema,
evidencia, impacto financiero, riesgo, decisión MANTENER/OPTIMIZAR/SIMPLIFICAR/REDISEÑAR/SUSTITUIR/ELIMINAR/AÑADIR/
VALIDAR ANTES DE DECIDIR, prioridad, esfuerzo), `15_veredicto_final.md` (puntuaciones 0–100 o N/E por área,
GO/NO-GO para investigación, backtesting, paper, real limitado, real significativo y real apalancado), y
`AUDIT_PROGRESS.md`. En `15` responde a estas 20 preguntas, una a una:

1. ¿Es actualmente un buen bot de trading? 2. ¿Hay evidencia suficiente de que puede ganar dinero? 3. ¿Qué provoca sus
pérdidas? 4. ¿Qué estrategias tienen mayor potencial demostrado? 5. ¿Cuáles eliminarías inmediatamente? 6. ¿Qué reglas
cambiarías? 7. ¿Cuáles eliminarías? 8. ¿Cuáles añadirías? 9. ¿Qué valor aporta la IA? 10. ¿Qué valor aporta el
seguimiento de ballenas? 11. ¿Qué estrategias intradía llevarías a la fase experimental? 12. ¿Qué está
sobredimensionado? 13. ¿Qué necesita rediseño? 14. ¿Principales obstáculos para la rentabilidad sostenible? 15. ¿Qué
falta para confiar en el bot? 16. ¿Qué harías con tu propio capital? 17. ¿Qué mejoras desarrollarías primero? 18. ¿En
qué condiciones detendrías toda la operativa? 19. ¿Qué resultados deben alcanzarse antes de dinero real? 20. ¿Hoja de
ruta más eficiente?

Clasifica cada conclusión por evidencia: demostrada en código y pruebas · respaldada estadísticamente · respaldada
por fuentes externas · hipótesis · no verificable.

**Cierre de la fase A:** commit que solo añada `auditoria_codex/fase_a/` con el mensaje
`Codex fase A: auditoría independiente` y anota su hash en `auditoria_codex/fase_a/AUDIT_PROGRESS.md`. A partir de
aquí no se modifica nada de `fase_a/`.

## Fase B — Evaluación de la auditoría de Claude

Ahora sí, lee entera `auditoria_independiente/`: documentos 00–15, `CAMBIOS_PROPUESTOS.md`, `propuestas.json`
(61 propuestas con ID `CP-…`), `INDICE_HALLAZGOS.md` (50 hallazgos con ID), `PUNTOS_DEBILES_DE_ESTA_AUDITORIA.md`
(empieza por aquí: es la lista de supuestos y dudas del propio Claude) y `experimentos/`.

### B1. Reproducción de los experimentos de Claude
En tu copia del repositorio:
```bash
python3 -I auditoria_independiente/experimentos/forense_ledger.py <copia> /tmp/forense.json
python3 -I auditoria_independiente/experimentos/sesgo_sombras.py <copia> /tmp/sombras.json   # importa estrategia.py y senales.py de <copia>
bash auditoria_independiente/experimentos/descargar_binance.sh /tmp/datos_binance              # solo si hay red
python3 -I auditoria_independiente/experimentos/backtest_independiente.py <copia> /tmp/datos_binance /tmp/backtest.json
```
Compara con `forense_ledger_resultado.json`, `sesgo_sombras_resultado.json` y `backtest_independiente_resultado.json`.
Además de reproducir, **audita los scripts**: errores, supuestos discutibles, si miden lo que dicen medir. Si un
supuesto cambia la conclusión, demuéstralo con una variante.

### B2. Evaluación de cada propuesta (las 61, sin saltarte ninguna)
Para cada `CP-…` comprueba en el código y los datos (no en el texto de Claude) que el diagnóstico es correcto, que
las referencias `archivo:línea` existen y dicen eso, que el cambio propuesto arreglaría el problema sin romper otra
cosa, y si su prioridad es adecuada. Ten en cuenta los efectos secundarios propios de este proyecto: casi cualquier
cambio en código con efecto o en la configuración altera la **huella** de `promocion.py` y reinicia la evidencia
válida para real; algunas propuestas son decisiones de negocio del propietario y no correcciones técnicas.

Veredictos posibles: `ACEPTAR` · `ACEPTAR_CON_CAMBIOS` · `RECHAZAR` · `NO_VERIFICABLE`.

### B3. Evaluación de cada hallazgo (los 50 del índice)
Veredictos: `CONFIRMADO` · `PARCIAL` · `REFUTADO` · `NO_VERIFICABLE`, con tu severidad (P0–P3) y la evidencia.

### B4. Omisiones y errores de Claude
Lo que tu fase A encontró y Claude no; lo que Claude afirma sin evidencia suficiente; cifras que no se reproducen;
puntuaciones o veredictos que consideres mal calibrados.

### B5. Comparativa y recomendación conjunta
Coincidencias, discrepancias (con quién tiene razón y por qué, con evidencia), y una lista final priorizada de
cambios que recomendarías aplicar, indicando para cada uno si viene de tu fase A, de Claude o de ambos.

### Entregables de la fase B (en `auditoria_codex/fase_b/`)
1. `evaluacion_propuestas.json` — parte de `auditoria_independiente/plantilla_evaluacion_propuestas.json` (ya trae las
   61 propuestas y los 50 hallazgos) y rellena todos los campos con este esquema:
```json
{
  "evaluador": "codex",
  "commit_fase_a": "<hash>",
  "propuestas": [
    {"id": "CP-E01", "veredicto": "ACEPTAR|ACEPTAR_CON_CAMBIOS|RECHAZAR|NO_VERIFICABLE",
     "diagnostico_correcto": "si|parcial|no|no_verificable",
     "referencias_correctas": "si|parcial|no",
     "evidencia": "archivo:línea, comando y cifra que lo sostienen o lo refutan",
     "prioridad_claude": "P0", "prioridad_codex": "P0|P1|P2|P3|no_aplicar",
     "efectos_secundarios": "texto (incluye huella y riesgo de regresión)",
     "cambios_sugeridos": "texto o vacío", "alternativa_mejor": "texto o vacío",
     "coincide_con_fase_a": "si|no|no_tratado_en_fase_a", "confianza": "alta|media|baja"}
  ],
  "hallazgos": [
    {"id": "T-01", "veredicto": "CONFIRMADO|PARCIAL|REFUTADO|NO_VERIFICABLE", "severidad_codex": "P0|P1|P2|P3",
     "evidencia": "texto", "coincide_con_fase_a": "si|no|no_tratado_en_fase_a"}
  ],
  "reproduccion_experimentos": [
    {"script": "forense_ledger.py", "reproduce": "si|parcial|no", "diferencias": "texto",
     "problemas_del_script": "texto"}
  ],
  "omisiones_de_claude": [
    {"titulo": "texto", "severidad": "P0|P1|P2|P3", "evidencia": "texto", "propuesta": "texto"}
  ],
  "veredicto_global": {"coincide_en_no_go_real": "si|no", "comentario": "texto"}
}
```
2. `EVALUACION_AUDITORIA_CLAUDE.md` — explicación legible de B1–B4, con una tabla resumen por propuesta.
3. `COMPARATIVA_Y_RECOMENDACION.md` — B5, incluidas tus puntuaciones frente a las de Claude por área y la decisión
   GO/NO-GO de cada uno por entorno.

**Cierre de la fase B:** commit que solo añada `auditoria_codex/fase_b/` con el mensaje
`Codex fase B: evaluación de la auditoría de Claude`. No hagas push a `main` ni fusiones ramas.

## Criterios de calidad
- Cada afirmación relevante con evidencia verificable (archivo:línea, comando, dato). Sin evidencia, márcalo.
- No aceptes una propuesta porque esté bien redactada ni la rechaces sin demostrar por qué.
- Sé especialmente crítico con los resultados demasiado buenos y con las muestras pequeñas o correlacionadas.
- Distingue un fallo de código, una decisión de diseño discutible y una decisión de negocio del propietario.
- Si te quedas sin contexto, guarda el estado en `AUDIT_PROGRESS.md` de la fase en curso para poder continuar, y no
  declares terminada una fase con trabajo pendiente sin decirlo.

=====
