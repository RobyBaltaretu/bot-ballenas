# 14 — Backlog maestro, matriz de decisiones y hoja de ruta

Prioridad: **P0** crítica · **P1** alta · **P2** media · **P3** baja. Esfuerzo: S (< 1 día) · M (1–3 días) · L (> 3 días).
Ninguna estimación de mejora económica es una promesa: donde no hay evidencia directa se indica «escenario».

## 1. Matriz maestra de decisiones

| ID | Componente | Estado actual | Problema | Evidencia | Impacto financiero | Riesgo | Decisión | Prio. | Esf. |
|---|---|---|---|---|---|---|---|---|---|
| M-01 | Política «qué se opera» | Se opera lo que el lab rechaza (momentum, exploración, memoria) | El lab no gobierna la operativa | 04, 12 (pérdidas evitables) | Alto: causa principal de pérdidas | Alto en real | REDISEÑAR: solo estrategias no negativas; exploración fuera | **P0** | S |
| M-02 | Medición de sombras | Muestreo puntual, entrada al mid, stop exacto | +0,123 R/op de sesgo | Q-07 | Decisiones basadas en datos falsos | Alto | REDISEÑAR con OHLC + costes | **P0** | M |
| M-03 | Referencia de mercado en toda evidencia | Solo en `veredicto.contra_mercado` | Beta confundida con habilidad | Q-02 | Alto | Alto | AÑADIR (lab y paper) | **P0** | M |
| M-04 | momentum_4h | Activa | OOS −0,107 R, t −3,35 | 04 | Negativo esperado | Alto | ELIMINAR de la operativa | **P0** | S |
| M-05 | Piramidación | Activa (simulado) | Deshace el TP1 | Q-05 | Negativo | Medio | ELIMINAR | P1 | S |
| M-06 | Memoria kNN | Decide/veta | 7/7 pérdidas; sin validar | A-01 | Negativo | Medio | ELIMINAR | P1 | S |
| M-07 | Relajación tras 24 h | Activa | Antipatrón | T-04 | Negativo | Medio | ELIMINAR | P1 | S |
| M-08 | Exploración amplia / del cerebro | Activas | Contaminan la evidencia | 05 | Indirecto | Medio | ELIMINAR (o cuenta separada) | P1 | S |
| M-09 | Cerebro ridge | Decide en simulado sin superar | t 2,75 < 2,91; solo HL sin mejora | C-01 | Nulo/negativo | Medio | SUSTITUIR (filtro solo si supera) | P1 | M |
| M-10 | Ballenas (señal, veto) | Activas | Sin señal; selección sesgada; no distingue abrir/cerrar | 06 | Nulo | Bajo | ELIMINAR del bot | P1 | S |
| M-11 | Simulador: stops por muestreo | Asimetría con objetivos | T-01 | 03 | Evidencia paper poco fiable | Medio | REDISEÑAR | P1 | M |
| M-12 | Trailing lab ≠ vivo | Divergencia | T-05 | 03 | Lo validado no es lo operado | Medio | OPTIMIZAR | P1 | M |
| M-13 | Panel por túnel sin contraseña | Activo | Lectura pública | SEG-01 | — | Alto (privacidad) | REDISEÑAR (contraseña + Access) | P1 | S |
| M-14 | Alertas externas | Sin configurar | Nadie se entera de una caída | 10 | Alto en real | Alto | AÑADIR | P1 | S |
| M-15 | VPS + copias | No ejecutado | PC doméstico, sin copias | 10 | Alto en real | Alto | AÑADIR | P1 | M |
| M-16 | Pruebas en testnet | Nunca | Código de órdenes no probado en real | 06 | Crítico antes de real | Crítico | AÑADIR | P1 (P0 antes de real) | M |
| M-17 | Límites del piloto real | = simulado (3 %/9 %/5×/−50 %) | Excesivos sin ventaja | 10 | Pérdida potencial grande | Alto | REDISEÑAR (1 %/3 %/2×/−20 %) | P1 | S |
| M-18 | Riesgo por operación simulado 3 % | Activo | Paper no representa un real prudente | 05 | Indirecto | Medio | OPTIMIZAR (1 %) | P2 | S |
| M-19 | Métrica `peor_que_trigger_pct` | Precio medio de salidas | Oculta deslizamiento | Q-06 | Calibración falsa | Bajo | OPTIMIZAR | P2 | S |
| M-20 | Escéptico / revisor LLM | Activos | Prompt invertido; constante | IA-01/02 | Nulo | Bajo | ELIMINAR (o corregir) | P2 | S |
| M-21 | Analista LLM (informe) | Activo | Repite cifras del código | IA-04 | Nulo | Bajo | SIMPLIFICAR (opcional) | P3 | S |
| M-22 | Borrado de datos_mercado a 120 días | Activo | Destruye la única historia de OI | W-03 | Bloquea investigación | Medio | ELIMINAR la limpieza | P1 | S |
| M-23 | Reproducibilidad del lab | Caché fuera del repo | No auditable | OPS-03 | — | Medio | AÑADIR archivo versionado | P2 | M |
| M-24 | DSR y PBO | No existen | Corrección de selección incompleta | 11 | — | Medio | AÑADIR | P2 | M |
| M-25 | Familias para Bonferroni en investigación | Disparador × intervalo | Subestima pruebas | 09 | Falsos positivos | Medio | OPTIMIZAR | P2 | S |
| M-26 | ruptura_4h + régimen | Opera sin régimen propio validado | Pista t 2,22 | B-02 | Posible prima pequeña | Medio | VALIDAR ANTES DE DECIDIR (prerregistro) | P1 | M |
| M-27 | Carry 2 patas | Simulado, 0 cierres | Umbral 20 %/año no se alcanza | 04 | Prima plausible ~7–12 %/año | Bajo-medio | MANTENER; validar con funding de HL | P1 | M |
| M-28 | Referencia «BTC > EMA200» | No existe como estrategia | Supera al sistema en Sharpe | 09 | Escenario: base sencilla | Bajo | AÑADIR como referencia (y quizá como estrategia) | P1 | S |
| M-29 | Cartera de funding | Activa sin validar | No es lo medido | 04 | Desconocido | Medio | VALIDAR ANTES DE DECIDIR | P2 | M |
| M-30 | Margen en el simulador | No se comprueba | T-03 | 03 | Divergencia | Bajo | AÑADIR | P2 | S |
| M-31 | Bloqueo del hilo al cierre de vela | 45–90 s | T-02 | 03 | Simulado poco fiel | Bajo | OPTIMIZAR | P2 | M |
| M-32 | `bot.py` monolítico | 2 389 líneas | Mantenibilidad | 03 | Indirecto | Medio | SIMPLIFICAR al quitar vías | P2 | M |
| M-33 | Panel decorativo (núcleo 3D, Ceto, Mesa, Sónar, Parte del mar) | 8 638 líneas JS | Complejidad sin valor de trading | 02 | Indirecto | Bajo | SIMPLIFICAR | P3 | M |
| M-34 | Pruebas no herméticas | Red real | T-09 | 03 | — | Bajo | OPTIMIZAR | P3 | S |
| M-35 | `MODELO_SIMULACION` | 2 ≠ 3 | T-11 | 03 | — | Bajo | OPTIMIZAR | P3 | S |
| M-36 | Instalador VPS sin lock | requirements.txt | OPS-01 | 03 | — | Bajo | OPTIMIZAR | P3 | S |
| M-37 | Curva de valor truncada | 3 000 puntos | T-13 | 03 | — | Bajo | OPTIMIZAR | P3 | S |
| M-38 | Núcleo de ejecución (gestor, ejecucion, riesgo, ledger, contabilidad) | Sólido | — | 03-A | Protege el capital | — | **MANTENER** | — | — |
| M-39 | Laboratorio y validación | Sólido | Ver M-23..M-25 | 09 | — | — | **MANTENER** (con mejoras) | — | — |
| M-40 | Promoción por huella + aprobación humana | Sólido | Evidencia paper poco exigente (T-12) | 03 | — | — | MANTENER + OPTIMIZAR | P2 | S |
| M-41 | Estrategias negativas (retroceso, reversión, funding, 1 h, liquidaciones) | Apagadas en sombra | Consumen recursos | 04 | — | — | ELIMINAR (cementerio) | P2 | S |

## 2. Funcionalidades a eliminar
1. Exploración amplia y exploración del cerebro en el bot de producción (M-08).
2. Memoria por vecinos como filtro (M-06).
3. Relajación de filtros por inactividad (M-07).
4. Piramidación (M-05).
5. Señal, veto y rasgo de ballenas (M-10) — conservar solo la grabación de datos.
6. Liquidaciones inferidas como estrategia (M-41).
7. Estrategias negativas en sombra (retroceso, reversión, funding, todas las de 1 h) (M-41).
8. Escéptico y revisor LLM (M-20).
9. Factor «objetivo diario conseguido» (05 #29).
10. Borrado automático de `datos_mercado/` (M-22).
11. `panel.tunel_sin_clave` (M-13).

## 3. Las 10 mejoras de mayor impacto

| # | Mejora | Por qué | Criterio de aceptación |
|---|---|---|---|
| 1 | **El laboratorio gobierna lo que se opera** (M-01, M-04) | Es la causa principal de pérdidas evitables | Una prueba que falle si una estrategia con t OOS < 0 está activa |
| 2 | **Medición honesta** de sombras y paper (M-02, M-11, M-19) | Las decisiones se toman con datos sesgados | Sombras con OHLC; diferencia media sombra−OHLC < 0,02 R en una prueba de regresión |
| 3 | **Referencia de mercado obligatoria** (M-03, M-28) | Separar habilidad de beta | Cada informe muestra exceso frente a universo y a BTC>EMA200 con IC |
| 4 | **Simplificar la decisión** a 1 vía (M-05..M-10) | Menos sesgos y menos rutas que probar | `procesar_candidatas` < 100 líneas; una sola fuente de tamaño |
| 5 | **Prerregistrar ruptura_4h + régimen** (M-26) | Única pista direccional | Documento de hipótesis antes de mirar; juicio único |
| 6 | **Carry con funding de Hyperliquid** (M-27) | Prima con fundamento | Estudio con funding HL 2023–2026, neto de 4 patas, con holdout |
| 7 | **Operación segura**: VPS, alertas, copias, contraseña (M-13..M-15) | Requisito de cualquier real | Simulacro de caída: aviso en < 10 min |
| 8 | **Testnet** de todas las rutas de órdenes (M-16) | Nunca probado en real | Checklist de 10 escenarios superada en testnet |
| 9 | **Límites del piloto reducidos** (M-17) | Supervivencia | `piloto_real`: 1 %/3 %/3 posiciones/2×/−20 %; techos duros en el código |
| 10 | **DSR/PBO + datos versionados** (M-23, M-24) | Credibilidad de cualquier «supera» | DSR > 0,95 exigido para «supera»; datos de cada ejecución archivados con hash |

## 4. Hoja de ruta

| Fase | Duración orientativa | Contenido | Puerta de salida |
|---|---|---|---|
| **0. Detener el ruido** | 1 semana | M-01, M-04..M-10, M-20, M-22, M-13. Sin cambios en el núcleo | El bot opera solo lo no negativo (o nada) en simulado; evidencia limpia desde una nueva puesta a cero |
| **1. Medir bien** | 2–3 semanas | M-02, M-03, M-11, M-12, M-19, M-24, M-28, M-37 | Informe semanal con exceso frente al mercado e IC; sombras OHLC |
| **2. Hipótesis** | 1–3 meses (en paralelo con 1) | M-26 (ruptura+régimen), M-27 (carry HL), M-29 (cartera de funding tal como se opera) | Una o ninguna «supera» con DSR; si ninguna, **parar y no operar real** |
| **3. Operación segura** | 2–4 semanas | M-14, M-15, M-16, M-36, M-34 | Testnet superado; VPS con alertas probadas |
| **4. Paper de confirmación** | ≥ 30 operaciones y ≥ 20 fechas | Solo la estrategia validada, con los límites del piloto | R medio dentro del IC del lab y exceso de mercado ≥ 0 |
| **5. Real mínimo** | ≥ 3 meses | 100–200 $, 1 % de riesgo, 2×, BTC/ETH/SOL | Deslizamiento real ≤ 1,5× el simulado; sin incidentes de propiedad |

**Dependencias:** 0 → 1 → 2 → 4 → 5; 3 en paralelo, pero obligatoria antes de 5.
