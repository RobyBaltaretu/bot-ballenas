# 15 — Veredicto final

## 1. Puntuaciones (0–100)

Criterio general: 100 = nivel profesional demostrado con evidencia; 50 = correcto pero con carencias relevantes;
< 30 = no cumple su función. **N/E** = no evaluable con los datos disponibles. La nota global **no** es una media: un
área crítica en rojo bloquea.

| Área | Nota | Justificación (evidencia) |
|---|---|---|
| Arquitectura | 55 | Núcleo de ejecución/riesgo bien separado y compartido con el lab; capa de decisión con 5 vías entrelazadas y `bot.py` monolítico (02, 13) |
| Calidad del código | 70 | Legible, documentado, 764 pruebas en verde, defensivo; monolito, 17 `except: pass`, pruebas con red (03) |
| Calidad de datos | 50 | Solo velas cerradas y validación cruzada de fuentes; historia sustituida, borrado de OI, dependencia de Binance/Bybit, lab no reproducible (03, 09) |
| Integración con exchanges | 60 | Coherente con la documentación oficial; **nunca probada contra la API real ni testnet** (06) |
| Estrategias | 10 | Ninguna con ventaja; las activas son nulas o negativas fuera de muestra (04) |
| Validaciones (reglas) | 50 | Controles de seguridad buenos; filtros de decisión sin validar y alguno contraproducente (05) |
| Trading intradía | 10 | Todas las de 1 h negativas; infraestructura y costes no lo permiten (08) |
| Seguimiento de ballenas | 5 | Sin señal en ninguna fuente; selección y lectura de movimientos defectuosas (06) |
| Inteligencia artificial | 10 | Cerebro no supera; LLM sin valor medible y con un prompt que invierte un rasgo (07) |
| Gestión del riesgo | 70 | Muy completa (escenarios, salto conjunto, riesgo desconocido ≠ 0); límites demasiado altos para real (10) |
| Ejecución | 65 | Diseño ejemplar (CLOID, verificación, congelación); sin verificación en real; simulador con sesgos (03) |
| Backtesting | 65 | Walk-forward purgado, holdout de un uso, estrés, lookahead probado; divergencias lab/vivo, sin DSR/PBO, no reproducible (09) |
| Evidencia estadística | 10 | Evidencia sólida de **ausencia** de ventaja; ninguna evidencia positiva (09) |
| Rentabilidad demostrada | 0 | +29,84 $ explicados por la caída del mercado; IC del R medio incluye 0 (09, 12) |
| Seguridad | 55 | Secretos bien gestionados; panel público sin contraseña; repo público con la operativa (10) |
| Estabilidad | 40 | Buen manejo de reinicios y cuelgues; PC doméstico, sin alertas externas, sin copias (10) |
| Escalabilidad | 40 | JSON y un proceso Python; suficiente para 232 $, no para más (02) |
| Observabilidad | 65 | Ledger excelente y reconstruible; sin alertas, curva truncada, métrica de stop errónea (03) |
| Preparación para dinero real | **5** | Sin ventaja, sin testnet, sin alertas, límites agresivos (15.3) |

**Nota global: NO APTO para dinero real.** Apto como plataforma de investigación y simulación con correcciones.

## 2. Decisión por entorno

| Entorno | Decisión | Condición |
|---|---|---|
| Investigación | **GO** | Con las correcciones de medición (M-02, M-03, M-24) |
| Backtesting | **GO** | El laboratorio es fiable como evidencia negativa; añadir DSR/PBO y referencias |
| Paper trading | **GO condicionado** | Solo tras la fase 0 (sin exploración, sin memoria, sin momentum); los resultados actuales no valen como evidencia |
| Real con capital limitado | **NO-GO** | Ver criterios 15.3 |
| Real con capital significativo | **NO-GO** | Además: ≥ 6 meses de real mínimo sin incidentes y ventaja confirmada |
| Real con apalancamiento > 2× | **NO-GO** | No hay ventaja que apalancar |

## 3. Criterios medibles para pasar a real con capital limitado (todos obligatorios)
1. Una estrategia con veredicto **«supera»**: t OOS y t por días ≥ listón corregido, **Deflated Sharpe ≥ 0,95**,
   holdout fresco ≥ 30 operaciones con R > 0, positiva en estrés combinado.
2. **Exceso frente a la referencia de mercado** (mismo lado del universo y BTC > EMA200) con IC 95 % > 0.
3. **n efectivo** ≥ 30 fechas independientes (no operaciones correlacionadas del mismo rebalanceo).
4. **Testnet**: entradas ALO + IOC de reserva, stop, TP, sustitución de stop, cancelación ambigua, reinicio con
   posiciones y conciliación, todos superados.
5. VPS con alertas (Telegram + Healthchecks) probadas en un simulacro; copias del ledger.
6. Paper de confirmación ≥ 30 operaciones con R medio dentro del IC del laboratorio.
7. `piloto_real` ≤ 1 % / 3 % / 3 posiciones / 2× / pérdida máxima 20 %; solo BTC, ETH, SOL; panel con contraseña.
8. Aprobación expresa del propietario con `promocion.py`.

## 4. Condiciones de bloqueo / parada total (en cualquier entorno real)
- Caída > 10 % del capital del piloto, o pérdida diaria > 3 %.
- R medio de las últimas 30 operaciones por debajo del límite inferior del IC del laboratorio.
- Cualquier incidente de propiedad o conciliación no explicado (mercado congelado > 1 h).
- Deslizamiento medio de stops > 2× el modelado.
- Caída de alertas o del VPS sin aviso en 10 min.
- Cambio de código o configuración que afecte a la huella sin nueva validación.

## 5. Riesgos pendientes y nivel de evidencia
- Riesgos pendientes: lectura línea a línea del 64 % del código no incluida en esta entrega (archivos «sin efecto» en su
  mayoría; ver AUDIT_PROGRESS); comportamiento real contra Hyperliquid no verificado; sesgo de la historia sustituida
  del cerebro sin resolver.
- Evidencia de las conclusiones principales: **demostrada** en código y datos (ausencia de ventaja, sesgo de sombras,
  beta, fallos Q-05/Q-06/IA-01), **respaldada estadísticamente** (backtest independiente, lab), **respaldada por fuentes
  externas** (documentación de Hyperliquid, literatura de carry/momentum/sobreajuste).

## 6. Respuestas directas

1. **¿Es actualmente un buen bot de trading?** No. Es una buena **infraestructura** de ejecución y validación sin una
   estrategia rentable. Como bot de trading (que gane dinero), no.
2. **¿Hay evidencia suficiente de que pueda ganar dinero?** No. Ninguna estrategia supera; el paper está dentro del azar
   (IC del R medio [−0,27; +0,56]) y su beneficio es la caída de BTC.
3. **¿Qué provoca sus pérdidas?** Operar lo que su propio laboratorio rechaza (estrategias de 1 h, retroceso, memoria,
   exploración) y largos contra la tendencia antes del filtro de régimen. Las pérdidas «normales» son menores.
4. **¿Qué estrategias tienen mayor potencial demostrado?** Ninguna demostrada. Potencial a investigar: carry de dos
   patas (fundamento económico) y ruptura_4h solo a favor del régimen de BTC (t 2,22 en mi backtest, insuficiente).
5. **¿Cuáles eliminaría inmediatamente?** momentum_4h de la operativa; retroceso, reversión, funding y todas las de 1 h;
   ballenas_1h; liquidaciones_1h.
6. **¿Qué reglas cambiaría?** Riesgo por operación (3 % → 1 %), límites del piloto, suelo de emergencia (−50 % → −20 %),
   exposición neta y beta más estrictas, trailing al cierre de vela, métrica de stop.
7. **¿Qué reglas eliminaría?** Relajación tras 24 h, memoria kNN, piramidación, exploración en el bot, veto de ballenas,
   factor de objetivo diario.
8. **¿Qué reglas añadiría?** Referencia de mercado obligatoria, n efectivo por fechas, kill switch por desviación del IC
   del laboratorio, salida por funding extremo, vigilancia de `userRateLimit`.
9. **¿Qué valor aporta la IA?** El LLM, ninguno medible (y un error de interpretación inducido por su prompt). El cerebro
   no supera la validación y su mejora desaparece con datos solo de Hyperliquid.
10. **¿Qué valor aporta el seguimiento de ballenas?** Ninguno: +0,01 R con las ballenas elegidas a dedo dentro de muestra,
    −0,03 R con todas; la señal no distingue abrir de cerrar.
11. **¿Qué estrategias intradía incorporaría a la fase experimental?** Ninguna de segundos/minutos. En 4 h–semanas:
    ruptura+régimen (prerregistrada), momentum transversal de cartera neutral y factor de funding medido tal como se
    opera; y el carry como línea principal.
12. **¿Qué partes están sobredimensionadas?** Panel (núcleo 3D, Ceto, Mesa, Sónar, Parte del mar, Taller), analista LLM,
    cinco vías de decisión, memoria kNN, ballenas, piramidación, cartera de funding.
13. **¿Qué necesita rediseño?** La política «qué se opera», la medición de sombras y del simulador, la capa de decisión
    (a una sola vía) y los límites del piloto.
14. **Principales obstáculos para la rentabilidad sostenible:** no existe una ventaja; los costes y la latencia descartan
    el intradía; la evidencia se ensucia con exploración y sombras sesgadas; la muestra de paper crece demasiado despacio
    (≈ 1 275 operaciones para detectar +0,1 R con t = 3).
15. **¿Qué falta para confiar en el bot?** Una estrategia que supere con DSR, confirmada sin degradación en paper, y la
    ejecución probada en testnet con operación 24/7 vigilada.
16. **¿Qué haría con mi propio capital?** No pondría dinero en las estrategias direccionales actuales. Si quisiera
    exposición a cripto, la regla «BTC por encima de su EMA200, si no fuera» con riesgo pequeño es más sencilla y, en la
    historia probada, mejor. Usaría este código solo para investigar el carry y la ruptura con régimen.
17. **¿Qué desarrollaría primero?** Fase 0 y 1 de la hoja de ruta: que el laboratorio gobierne lo que se opera y medir bien
    (sombras OHLC, referencia de mercado, DSR).
18. **¿Cuándo detendría toda la operativa?** Ahora, para lo direccional en real (nunca empezó: bien). En simulado,
    detener las vías de exploración y momentum ya. En real futuro, con los criterios de 15.4.
19. **¿Qué resultados antes de dinero real?** Los 8 criterios de 15.3.
20. **¿Hoja de ruta más eficiente?** Detener el ruido (1 semana) → medir bien (2–3 semanas) → 2–3 hipótesis
    prerregistradas (1–3 meses) → testnet y VPS → paper de confirmación → real mínimo. Si en la fase de hipótesis nada
    supera, la decisión correcta es **no operar dinero real** y dejar el bot como herramienta de investigación.
