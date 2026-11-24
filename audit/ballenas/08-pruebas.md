# 08 · Plan de pruebas

**Ejecutado hoy (19/11/2026):**
- Batería completa `python -m unittest discover -s tests -t .`: **710 pruebas, OK, 101 s**.
- `tests.test_lookahead`: 7 pruebas OK, con control positivo.
- Todo es local, sobre `papel.py` y mocks, sin red de escritura.

Las pruebas «pendiente» están **diseñadas, no ejecutadas**: no cuentan como PASS.

## Cobertura existente (resumen por archivos de prueba)

| Área | Archivos (n.º de pruebas) |
|---|---|
| Unitarias | riesgo (18 + 10 + 7), contabilidad/ledger (10), simsalida (9), momentum (8), cerebro (6 + 11 + 14), probabilidades (7) |
| Ejecución | ordenes_seguras (15), ejecucion (10), gestor (21 + 12), simulacion_riesgo (15), arreglos_estudio (10) |
| Laboratorio | laboratorio_validez (13), holdout (7), meseta (7), validacion_promocion (26), lookahead (7), preregistro (12) |
| Sistema y panel | bot (36), panel (13 + 19 + 5 + 5), configuracion (18), secretos (3), limitador (5) |

## Pruebas propuestas

| ID | Tipo | Riesgo cubierto | Entrada / fixture | Resultado esperado | Prioridad | Estado |
|---|---|---|---|---|---|---|
| T-A1 | Unitaria | Fórmula de tamaño en los tres escenarios | Tabla equity/stop/costes → nocional esperado | Igual a la fórmula de 04 ±1e-9 | P2 | Existente (`test_riesgo*`), PASS hoy |
| T-A2 | Unitaria | R con ampliación medida sobre el riesgo original | Op con ampliación cerrada en el stop | `riesgo_inicial_usd` = riesgo original; con + sin = total | P1 | Existente (`test_arreglos_estudio`), PASS hoy |
| **T-R1** | Riesgo | **D1: la ampliación respeta los bloqueos** | Bot simulado con `pausa_manual` o pérdida diaria superada y una op en sin pérdidas | `ampliar` **no** se llama | **P0** | Pendiente (hoy fallaría) |
| **T-R2** | Riesgo | **D1: la ampliación respeta la exposición** | Exposición por mercado al 100 % | No amplía | **P0** | Pendiente (hoy fallaría) |
| T-R3 | Riesgo | Salto correlacionado | 4 posiciones del mismo lado; todos los stops llenan al límite del 10 % | Pérdida conjunta ≤ límite agregado definido | P1 | Pendiente (no existe el límite) |
| T-R4 | Riesgo | Suelo de emergencia | Equity que cae al 50 % | Cierra todo y bloquea | P1 | Existente (`test_riesgo`) |
| T-D1 | Fallo | Respuesta perdida | `order` lanza un timeout, pero la orden existe | Ni duplicado ni reenvío; estado por CLOID | P1 | Existente (`test_ordenes_seguras`) |
| T-D2 | Fallo | Websocket caído mucho rato | Sin mensajes de ballenas durante 10 min | Ballenas «no frescas»: sin señal ni veto; el resto sigue | P2 | Parcial (`test_mercado_ws`, 2) |
| T-D3 | Fallo | Arranque con el limitador saturado | Descarga de funding simulada con un presupuesto pequeño | Los ciclos no superan X s; las protecciones se procesan | P2 | Pendiente |
| T-D4 | Fallo | Operación sin cierre en el ledger | Ledger con entrada y órdenes huérfanas sin cierre | La conciliación cierra o marca la operación (no queda «completada» para siempre) | P2 | Pendiente (hoy fallaría: caso kPEPE) |
| T-I1 | Integración | Paridad del SDK | `papel` frente a respuestas grabadas de Hyperliquid (sin firmar) para order, cancel y estado | Mismo parseo (`interpretar_respuesta`, `normalizar_consulta`) | P1 | Parcial |
| T-I2 | Integración | Tamaños y ticks cambiantes | `meta` con otro `szDecimals` | Redondeo correcto; nada menor que el mínimo | P2 | Parcial |
| T-Q1 | Cuantitativa | Cerebro 4 h fuera de muestra con el listón nuevo | Laboratorio en curso | Veredicto con t por días y holdout | P0 para decidir | En curso |
| T-Q2 | Cuantitativa | Cerebro «con todo» frente a «solo HL» solo en el periodo con Hyperliquid | Recalcular quitando la historia sustituida | Si la ventaja desaparece, es un sesgo de datos | **P1** | Pendiente |
| T-Q3 | Cuantitativa | Dependencia del régimen | Resultados por régimen de BTC (alcista/bajista) | La ventaja existe en ambos o se documenta | P1 | Pendiente |
| T-P1 | Paridad | Lo que haría real | Reproducir las decisiones de simulado con `modo: real` simulado (sin cliente) | Lista de qué habría entrado en real (hoy: nada) | P1 | Pendiente |
| T-P2 | Paridad | Calibración de ejecución | Primeras operaciones reales pequeñas frente al simulado | Diferencia de deslizamiento y llenado medida | P1 | Bloqueada (requiere real y autorización de Roberto) |
| T-S1 | Seguridad | Panel remoto | Petición con cabecera de túnel y sin clave | 403 cuando se quite `tunel_sin_clave` | P1 | Existente (`test_panel_proxy`); la config actual lo permite |
| T-S2 | Seguridad | Dependencias | `pip-audit` sobre `requirements-bloqueado.txt` | Sin CVE críticos | P2 | Bloqueada (requiere instalar la herramienta) |
