# 07 — Auditoría del cerebro y del analista de inteligencia artificial

Hay **dos** «IA» distintas y conviene no mezclarlas:

| | Cerebro | Analista LLM |
|---|---|---|
| Qué es | Regresión ridge (8 rasgos + indicadores de falta + estrategia) | `openai/gpt-oss-120b` vía Groq (plan gratuito) |
| Archivos | `cerebro.py`, `cerebro_vivo.py`, `mercado_unificado.py` | `analista_ia.py` (proceso del panel) |
| ¿Decide? | **Sí**: único que aprueba candidatas (umbral +0,05 R) | **No**: informe, revisor, vigilante, escéptico; ideas para investigación |
| ¿Supera la validación? | No (`no_supera`) | No se valida (no hay criterio económico) |

## 1. Cerebro

**Funcionamiento verificado (código):** junta las candidatas de todas las estrategias del intervalo, estandariza 8 rasgos
(tendencia, impulso 6 velas, volatilidad relativa, funding 8 h, diferencia de funding HL−externo, flujo comprador
agresivo de Binance 1 y 6 velas, base HL−Binance), recorta a ±3σ, añade un indicador de «falta» por rasgo y un
efecto fijo por estrategia, y predice el R. Walk-forward con embargo; modelo final con todas las candidatas cerradas.
Falla cerrado ante modelo ausente, corrupto, de otra versión de rasgos o sin datos externos.

**Resultados (laboratorio 22/11):**

| Variante | OOS n | R medio | t | Holdout | Cartera con límites reales |
|---|---|---|---|---|---|
| Operar todas | 4 767 | −0,057 | −3,59 | +0,034 (1 251) | — |
| Cerebro con todo | 1 036 | +0,090 | 2,75 (listón 2,91; t días 1,32) | +0,072 (363) | **−1,65 %, caída 28,6 %** |
| Todas, solo historia HL | 2 263 | −0,069 | −2,93 | — | — |
| Cerebro solo HL | 757 | −0,045 | −1,20 | +0,100 (280) | **−25,4 %** |

**Lectura independiente:**
- La «mejora» del cerebro con todo (+0,15 R frente a operar todo) no aparece cuando se mira solo la historia propia de
  Hyperliquid (+0,02 R, nula): o la ventaja viene de los datos externos (que solo hay donde la historia es de Binance),
  o es un artefacto de la historia sustituida (riesgo D6 que la auditoría interna dejó abierto). No se puede distinguir
  sin un experimento dedicado.
- Incluso la variante buena **pierde dinero como cartera** con los límites reales: el R medio por candidata no se traduce
  en resultado cuando las candidatas aprobadas se concentran en el tiempo y en el mismo lado.
- El modelo predice un rango estrecho (pesos de 0,02–0,10 R por σ); la decisión la dominan los efectos fijos por
  estrategia (−0,19 R funding, +0,09 R momentum…). En la práctica es «qué estrategia» + un pequeño ajuste lineal.
- Problema de diseño: entrenar sobre candidatas de estrategias que **ya** son negativas y pedirle al modelo que encuentre
  el subconjunto positivo es la receta clásica de minería de datos. Con 1 098 variantes históricas probadas en el
  proyecto, un t de 2,75 es compatible con el azar.

**Decisión:** SUSTITUIR. Mientras no supere, el cerebro no debe aprobar operaciones ni en simulado (hoy lo hace por
`exploracion_simulado`). Para un filtro estadístico futuro: regresión logística o gradient boosting con validación
cruzada purgada y embargo, **una** hipótesis por rasgo prerregistrada, y siempre comparado con el modelo nulo «solo
estrategia + régimen».

## 2. Analista LLM

**Qué hace (verificado):**
- Informe diario con datos del bot (recortados a 8 000 tokens/min del plan gratuito), revisión de cada operación cerrada,
  explicación de alarmas que detecta el código, «escéptico» que da un argumento en contra de cada apertura, y hasta 2
  ideas semanales para `investigacion.py` (búsqueda congelada desde el 17/11).
- **Aislamiento correcto:** solo importa `json, os, re, sys, time, datetime, requests`; no toca órdenes, config ni
  promoción. Sus cifras se cruzan con los datos (`verificar_dato`). Temperatura 0,2, salida JSON, tope de 40 consultas/día.
- Coste monetario: 0 (plan gratuito). Coste real: complejidad, mantenimiento (ajustes por errores 413/400/429 del 19/11),
  y la clave de Groq en `.env`.

**Problemas encontrados:**
1. **IA-01 · Prompt con el significado invertido** (`analista_ia.py:102`): «funding_contra > 0 = el funding juega a
   favor», cuando en el bot `funding_contra > 0` es funding EN CONTRA (filtro `bot.py:670`). Evidencia en
   `registro/analista/esceptico.jsonl`: VVV corto con `funding_contra −0,0045` (funding a favor del corto) → la IA
   responde «el funding actúa en contra del lado corto»; SKY, igual.
2. **IA-02 · Escéptico constante:** 6 de 6 veredictos «en_contra». Un predictor constante no tiene información.
3. **IA-03 · Recomendaciones inestables:** `ruptura_4h` recibió «vigilar» 3 veces, «retirar» 2 y «mantener» 2 en 23
   recomendaciones, sin cambios de evidencia que lo justifiquen.
4. **IA-04 · Sin valor incremental medible:** el informe del 24/11 dice «el rendimiento se explica por la caída del
   mercado», que es exactamente la cifra que calcula `veredicto.contra_mercado` de forma determinista. Sus hallazgos
   quedan como «no_verificado».
5. **Riesgo de inyección:** bajo (los datos son propios; nombres de monedas y direcciones podrían contener texto, pero la
   IA no puede actuar). El prompt ya pide ignorar instrucciones de los datos.

**Comparativa pedida (A–H):**

| Variante | Evidencia disponible | Conclusión |
|---|---|---|
| A. Bot sin IA (operar todas las candidatas) | Lab: −0,057 R | Pierde |
| B. Bot con la IA actual (cerebro) | Lab: +0,090 R, no supera; cartera −1,65 % | No demostrado |
| C. IA como filtro contextual (LLM) | No medido; escéptico constante | Sin valor |
| D. IA como clasificador de régimen | No implementado; el régimen EMA200 simple funciona en ruptura (05) | Un clasificador sencillo basta |
| E. IA como selector de estrategias | No implementado | Sin estrategias con ventaja no hay nada que seleccionar |
| F. IA como supervisor de riesgo | El vigilante LLM solo explica alarmas del código | Los controles deterministas ya cubren esto |
| G. ML especializado en lugar de LLM | El cerebro ES ML lineal | Correcto en principio; mal planteado (minería sobre estrategias negativas) |
| H. Híbrida | — | No justificada hoy |

Evidencia externa: en la competición pública Alpha Arena (Nof1, octubre de 2025) seis LLM con 10 000 $ cada uno operaron
perpetuos en Hyperliquid; 4 de 6 terminaron en pérdidas y Nof1 atribuyó buena parte del resultado a costes por
sobre-operar (Decrypt, SCMP, Forklog). No es un estudio controlado, pero coincide con lo observado aquí: el LLM no aporta
una ventaja de trading por sí mismo.

## 3. Qué decisiones deben ser de cada tipo

| Decisión | Tipo recomendado |
|---|---|
| Órdenes, stops, tamaño, límites, kill switch, conciliación | **Determinista** (ya lo es; mantener) |
| Señales de estrategia | Determinista, validada estadísticamente |
| Régimen de mercado | Estadístico simple (EMA/volatilidad), validado |
| Filtro de candidatas | Estadístico/ML solo si supera; si no, ninguno |
| Explicación, informe, resumen para el propietario | LLM opcional, sin datos que interpretar mal (pasarle conclusiones ya calculadas) |
| Cualquier cosa que toque dinero, riesgo o configuración | **Prohibido para la IA** |

## 4. Recomendación
- **Cerebro:** desactivar la exploración en simulado; mantener el código de validación; rehacer el planteamiento (07.1).
- **LLM:** corregir el prompt (IA-01) o, mejor, **eliminar el escéptico y el revisor** y dejar como mucho un resumen
  semanal que solo redacte cifras ya calculadas. Ahorra complejidad y una dependencia externa.
