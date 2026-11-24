# Auditoría independiente 360° — bot de Hyperliquid (24/11/2026)

Auditoría externa e independiente del repositorio `RobyBaltaretu/bot-ballenas`, commit `b8a9f8d`. No modifica el código
funcional ni la configuración. No se ejecutó ninguna orden real. Las afirmaciones de `AUDIT_CONTEXT.md` y de
`audit/ballenas/` se trataron como hipótesis y se contrastaron con el código, los datos y fuentes externas.

| Documento | Contenido |
|---|---|
| [00 — Resumen ejecutivo](00_resumen_ejecutivo.md) | Estado real, fortalezas, debilidades, decisión |
| [01 — Inventario y cobertura](01_inventario_y_cobertura.md) | Archivos, líneas, funciones, nivel de revisión, pruebas, exclusiones, limitaciones |
| [02 — Arquitectura y funcionamiento](02_arquitectura_y_funcionamiento.md) | Flujo real dato → resultado, divergencias documentación/código |
| [03 — Auditoría técnica](03_auditoria_tecnica.md) | Hallazgos con archivo:línea, causa, consecuencia, corrección y prueba |
| [04 — Estrategias](04_auditoria_estrategias.md) | Lab, backtest independiente, paper y sombras por estrategia |
| [05 — Reglas](05_auditoria_reglas.md) | Inventario de 35 reglas, ablación natural, decisión |
| [06 — Hyperliquid y ballenas](06_hyperliquid_y_ballenas.md) | Integración frente a la doc. oficial; selección, interpretación y replicabilidad |
| [07 — Inteligencia artificial](07_inteligencia_artificial.md) | Cerebro (ridge) y analista LLM |
| [08 — Intradía](08_investigacion_intradia.md) | Fichas de estrategias y viabilidad |
| [09 — Validación cuantitativa](09_validacion_cuantitativa.md) | Backtesting, métricas, benchmarks, tamaño de muestra |
| [10 — Riesgos y seguridad](10_riesgos_y_seguridad.md) | Escenarios extremos, ciberseguridad, mitigación |
| [11 — Investigación externa](11_investigacion_externa.md) | Fuentes con trazabilidad |
| [12 — Forense de operaciones](12_forense_operaciones.md) | Causas de pérdida, ganadoras, descartes |
| [13 — Arquitectura objetivo](13_arquitectura_objetivo.md) | Diseño propuesto y diferencias |
| [14 — Backlog y hoja de ruta](14_backlog_y_hoja_de_ruta.md) | Matriz maestra de decisiones, eliminaciones, top 10, fases |
| [15 — Veredicto final](15_veredicto_final.md) | Puntuaciones, GO/NO-GO, criterios, 20 respuestas |
| [AUDIT_PROGRESS](AUDIT_PROGRESS.md) | Estado, pendientes y cómo reanudar |

## Para aplicar cambios y para una revisión externa

| Archivo | Contenido |
|---|---|
| [CAMBIOS_PROPUESTOS.md](CAMBIOS_PROPUESTOS.md) | Las 61 propuestas: 16 eliminar, 24 modificar, 16 añadir, 5 validar. Dónde, qué hay, qué cambiar, evidencia, riesgo, huella, quién decide, prioridad, aceptación, dependencias y orden de aplicación. **Ninguna está aplicada** |
| [propuestas.json](propuestas.json) | Las mismas propuestas en formato de máquina (fuente única: `experimentos/generar_propuestas.py`) |
| [INDICE_HALLAZGOS.md](INDICE_HALLAZGOS.md) | Los 50 hallazgos con su ID, severidad y dónde se definen |
| [PUNTOS_DEBILES_DE_ESTA_AUDITORIA.md](PUNTOS_DEBILES_DE_ESTA_AUDITORIA.md) | Supuestos, dudas y límites de esta auditoría: por dónde empezar a revisarla |
| [PROMPT_CODEX.md](PROMPT_CODEX.md) | Prompt para que Codex haga su propia auditoría a ciegas y después evalúe esta |
| [plantilla_evaluacion_propuestas.json](plantilla_evaluacion_propuestas.json) | Plantilla que el revisor rellena: 61 propuestas, 50 hallazgos, 3 experimentos |

## Experimentos reproducibles (`experimentos/`)

| Script | Qué hace | Resultado |
|---|---|---|
| `inventario.py` | Inventario AST de todo el Python | `inventario_ast.tsv` |
| `forense_ledger.py` | Reconstrucción independiente del ledger, IC bootstrap, MAE/MFE, referencia de mercado | `forense_ledger_resultado.json` |
| `sesgo_sombras.py` | Re-simulación OHLC de las sombras con la `SimSalida` del bot | `sesgo_sombras_resultado.json` |
| `backtest_independiente.py` | Backtest de momentum/ruptura/fuerza con Binance 2021–2026 y benchmarks | `backtest_independiente_resultado.json` |
| `salida_pruebas_20261124.txt` | Salida de la batería de pruebas (764 OK) | — |
| `descargar_binance.sh` | Descarga los datos públicos que usa el backtest | ≈ 2 800 archivos, 23 MB |
| `generar_propuestas.py` | Genera `CAMBIOS_PROPUESTOS.md` y `propuestas.json` | — |
| `generar_indice_hallazgos.py` | Genera `INDICE_HALLAZGOS.md` (falla si se cita un ID sin definir) | — |
| `generar_plantilla_evaluacion.py` | Genera `plantilla_evaluacion_propuestas.json` | — |

Reproducción comprobada el 24/11/2026: los tres experimentos dan resultados idénticos a los JSON guardados.

Reproducción: crear una COPIA del repositorio (los scripts que importan `estrategia.py`/`senales.py` deben apuntar a la
copia), un venv con `requirements-bloqueado.txt`, y para el backtest descargar de `data.binance.vision` las velas de 4 h y
el funding mensual de los 20 símbolos listados en el script (≈ 23 MB). Ejecutar con `python3 -I`.
