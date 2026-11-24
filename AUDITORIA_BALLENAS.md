# Auditoría del Bot Ballenas

Informe único e incremental. Fases 1, 2, 3 y 4 escritas el 13/11/2026. No se modificó código de decisión ni configuración.

**Veredicto corto:** hoy el bot no tiene ventaja demostrada y, tal como opera, lo esperable es que pierda despacio. La investigación externa (fase 4) cambia el rumbo propuesto en la fase 3: el carry de funding con dos patas está comprimido en 2025–26 y baja de prioridad, y lo que tiene mejor respaldo publicado es la tendencia lenta (velas diarias, sin objetivo, tamaño por volatilidad), que es justo lo contrario de cómo operan hoy las reglas del bot. La lista completa de errores y el plan están en la fase 4, apartados 4 y 5.

Leyenda de evidencia: **[V]** verificado en código o datos · **[H]** hipótesis · **[NC]** no comprobado.

---

## FASE 1 — Diagnóstico del sistema

### 1. Mapa funcional

| Etapa | Qué hace | Dónde |
|---|---|---|
| Datos | Velas cerradas de 1 h y 4 h, funding y precios de Hyperliquid (API pública). Contexto de Binance/Bybit solo lectura. Libro y horquilla por moneda. | `motor.py:157-260`, `contexto_externo.py`, `mercado.py` |
| Oportunidades | Seis reglas técnicas por intervalo (ruptura, retroceso, reversión, funding, fuerza relativa, momentum) proponen en cada cierre de vela. | `senales.py:137-213`, `motor.py:294` |
| Cerebro | Regresión ridge de 8 rasgos que predice el resultado en R. Entra si la predicción supera 0,05 R. | `cerebro_vivo.py:111-155`, `cerebro_modelo.json` |
| Decisión | Filtros de riesgo, después cerebro, después exploración amplia, después memoria de aprendizaje. | `bot.py:784-870` |
| Riesgo | Tamaño por distancia al stop con costes y funding adverso; límites agregados, beta, pérdida máxima, suelo de emergencia. | `riesgo.py:121`, `:262`, `:376`, `:397` |
| Ejecución | Cuenta simulada contra precios reales; una operación por moneda; stops verificados y conciliación. | `papel.py`, `gestor.py`, `ejecucion.py` |
| Validación | Laboratorio semanal (walk-forward, holdout sellado, t por días) e investigación diaria de ideas. | `laboratorio.py`, `validacion.py`, `investigacion.py` |
| Paso a real | Huella de código y modelo más aprobación humana. Bloqueado. | `promocion.py`, `cerebro_vivo.py:123` |

### 2. Cómo decide comprar, vender o abstenerse [V]

1. Una estrategia propone moneda, lado y stop (`motor.py:294`).
2. `evaluar()` aplica los filtros de riesgo, horquilla y costes (`bot.py:809`).
3. El cerebro predice. Si el modelo de ese intervalo no está aprobado, solo decide cuando el intervalo está en `exploracion_simulado` (hoy solo 4 h) (`cerebro_vivo.py:128-132`).
4. Si el cerebro dice no, la exploración amplia la abre igualmente con riesgo 0,5 % y hasta 4 a la vez (`bot.py:843-849`, `:1042-1053`).
5. Si el cerebro dice sí, la decisión pasa además por la memoria de aprendizaje (`bot.py:850-858`).

En simulado, por tanto, el bot casi nunca se abstiene: se abstiene solo por límites de riesgo o de cupo.

### 3. Hallazgos priorizados

| # | Nivel | Hallazgo | Evidencia |
|---|---|---|---|
| 1 | CRÍTICO | Ningún componente tiene ventaja demostrada. Los dos modelos del cerebro están en `no_supera` y ninguna estrategia individual pasa el laboratorio. | [V] `cerebro_modelo.json` (4 h y 1 h: `estado_laboratorio: no_supera`); informe del 12/11: 840 ideas, 0 supervivientes |
| 2 | CRÍTICO | El riesgo está al nivel de un sistema validado: 3 % por operación, 9 % abierto, apalancamiento 5, pérdida total tolerada 50 %. En simulado no cuesta dinero, pero estos valores no pueden llegar a real. | [V] `config.json` → `riesgo` |
| 3 | ALTO | El filtro del cerebro no discrimina en vivo: lo rechazado rindió más que lo aceptado (25 operaciones a +0,66 R frente a 19 a −0,00 R). Muestra pequeña. | [V] probador, informe 12/11; causa [NC] |
| 4 | ALTO | El resultado positivo reciente se explica por la caída del mercado y no por selección: las mismas operaciones todas en corto habrían dado +12,30 $ frente a +1,32 $ del bot. | [V] `veredicto.contra_mercado`, 15 operaciones |
| 5 | ALTO | La decisión del cerebro se sobrescribe. Cuando acepta, `val` se asigna en la línea 836 y la rama `elif not fallos` de la 850 lo reemplaza por el juicio de la memoria. La memoria puede reducir el tamaño a la mitad en simulado y vetar en real, lo que contradice «el cerebro es el único que decide». | [V] `bot.py:834-858`; efecto en resultados [NC] |
| 6 | ALTO | Los pesos del modelo son muy pequeños (máximo ≈ 0,085 R por desviación típica) frente a un umbral de 0,05 R. La entrada depende de diferencias mínimas de predicción, del tamaño del ruido. | [V] `cerebro_modelo.json` → `w`; que sea ruido es [H] |
| 7 | MEDIO | La protección «sin datos externos el cerebro no decide» se salta: esa abstención cuenta como rechazo del cerebro y la exploración amplia abre la operación. | [V] `cerebro_vivo.py:149-151` con `bot.py:838-849` |
| 8 | MEDIO | Las estrategias de 1 h pierden y solo operan por exploración amplia; consumen comisiones y cupo sin aportar evidencia a favor. | [V] informe 12/11; muestra pequeña |
| 9 | MEDIO | El nombre no describe el sistema: las señales operadas son técnicas. El papel real del flujo de ballenas en las decisiones no está comprobado. | [V] `senales.py`; `motor.py:404` y `ballenas.py` [NC] |
| 10 | BAJO | La agenda considera un trabajo «en marcha» durante 6 h y los bloqueos duran 12 h. El segundo proceso se niega a arrancar, así que no hay doble ejecución. | [V] `bot.py:1328`, `investigacion.py:703` |
| 11 | BAJO | Documentación desfasada: `CLAUDE.md` dice «1 h = sin modelo» y existe un modelo de 1 h. La carpeta `copias/` duplica código antiguo y ensucia las búsquedas. | [V] |

### 4. Lo que parece sólido [V]

- Barreras hacia real: modo, huella, aprobación humana y abstención del cerebro si el modelo no supera el laboratorio.
- El cerebro falla cerrado ante errores o modelo inválido (`cerebro_vivo.py:156`, `bot.py:818`).
- La validación es exigente: holdout sellado y listón que sube con cada idea probada.
- Contabilidad en `ledger.jsonl` con modelo y rasgos de cada decisión.

### 5. Módulos que requieren investigación en la fase 2

1. `gestor.py`: reglas de salida (stops móviles, tiempo máximo). Es lo no inspeccionado con más efecto sobre el resultado.
2. `aprendizaje.py` (`Memoria.valorar`): cuánto altera hoy las decisiones del cerebro (hallazgo 5).
3. `ledger.jsonl`: costes reales por operación frente al riesgo, y resultado por estrategia, intervalo y lado.
4. Rasgos del cerebro en vivo frente al laboratorio: si la distribución coincide (hallazgos 3 y 6).
5. `ballenas.py` y `motor.senales_ballenas`: si aportan algo o son peso muerto (hallazgo 9).

### 6. Límites de esta fase

No se ejecutó ninguna prueba ni se modificó código. No se leyeron `gestor.py`, `aprendizaje.py`, `papel.py` ni `laboratorio.py`. Las cifras de operaciones proceden del análisis del 12/11 y no se recalcularon.

---

## FASE 2 — Operaciones y cerebro

Fuentes: `registro/ledger.jsonl` (28 cierres, 23/10 a 12/11), `estrategia_elegida.json` (laboratorio del 08/11), `panel_datos.json` (probador). Con 28 operaciones nada de lo que sigue es concluyente por sí solo; lo que pesa es que coincide con el laboratorio, que tiene miles.

### 1. Resultado en vivo (simulado) [V]

| Grupo | n | Ganan | R medio | Neto $ | Factor de beneficio |
|---|---|---|---|---|---|
| **Total** | 28 | 21 % | −0,43 | −12,79 | 0,48 |
| 1 h | 15 | 7 % | −0,72 | −8,32 | 0,00 |
| 4 h | 13 | 38 % | −0,09 | −4,47 | 0,73 |
| Largos | 15 | 7 % | −0,78 | −12,18 | 0,00 |
| Cortos | 13 | 38 % | −0,03 | −0,61 | 0,95 |
| Salida por stop-loss | 15 | 0 % | −1,11 | −23,99 | — |
| Salida por tiempo máximo | 8 | 62 % | +0,59 | +11,30 | 17,5 |

Expectativa: −0,43 R por operación. Caída máxima: 21,34 $ (≈ 9 % de la cuenta). Comisiones: 0,52 $ en total; no son el problema.

Desde la puesta a cero del 03/11 (16 cierres con resultado):

| Vía de entrada | n | R total | R medio | Composición |
|---|---|---|---|---|
| Cerebro de 4 h (con predicción) | 9 | +2,85 | +0,32 | 7 cortos y 2 largos; los 2 largos perdieron |
| Exploración amplia (sin predicción) | 7 | −5,75 | −0,82 | 7 largos de 1 h; 0 ganadores |

### 2. Lo que dice el laboratorio, fuera de muestra y en holdout [V]

| Conjunto | n | R medio | FB | t | Holdout: R medio / t |
|---|---|---|---|---|---|
| Todas las propuestas de 4 h | 3497 | −0,035 | 0,93 | −1,73 | −0,013 / −0,38 |
| 4 h filtradas por el cerebro | 854 | +0,103 | 1,26 | 2,66 | +0,102 / 1,68 |
| Todas las propuestas de 1 h | 7292 | −0,068 | 0,86 | −5,36 | −0,144 / −6,76 |
| 1 h filtradas por el cerebro | 979 | −0,050 | 0,89 | −1,53 | −0,143 / −1,53 |

Por estrategia (t fuera de muestra / t en holdout):

- Claramente negativas: `ruptura_1h` (−3,89 / −6,68), `retroceso_4h` (−3,66 / −2,38), `retroceso_1h` (−3,15 / −3,51), `funding_1h` (−2,64 / −0,80), `reversion_1h` (−2,16), `reversion_4h` (−1,72 / −2,08), `funding_4h` (−1,05 / −2,28).
- En torno a cero: `ruptura_4h` (+0,28 / −0,08), `momentum_4h` (−0,38 / +0,89), `fuerza_4h` (+0,29 / +0,27), `fuerza_1h` (−0,79 / +0,41).
- Sin muestra suficiente: `ballenas_1h` (n = 33), `liquidaciones_1h` (n = 22). El módulo que da nombre al bot no tiene evidencia.
- El listón exigido es t ≈ 4,19 porque ya se han probado 1074 variantes. Ninguna se acerca.

Carry de funding (investigación, sin conectar): fuera de muestra n = 273, 81 % ganadoras, t 9,78, ≈ 12 % anual sobre el capital; holdout n = 85, t 8,87, ≈ 7 % anual. Solo con monedas que tienen contado en Hyperliquid: n = 51, t 4,0, ≈ 10 % anual. Usa contado de Binance como referencia y deja sin modelar margen, liquidación del corto, desajuste entre patas y base dentro de las 8 h.

### 3. Causas, separadas por tipo

| Tipo | Hallazgo | Nivel | Evidencia |
|---|---|---|---|
| Estrategia | El conjunto de reglas tiene expectativa negativa antes de filtrar. Operarlas sin filtro (exploración amplia) es pagar por confirmar lo que el laboratorio ya sabe. | CRÍTICO | [V] tabla anterior; en vivo 7 de 7 pérdidas o empates |
| Estrategia | Todo 1 h es negativo con miles de operaciones, con o sin cerebro. | CRÍTICO | [V] t −5,36 y −6,76 |
| Estrategia | Dependencia del lado y del régimen: en vivo ganó 1 de 15 largos durante una caída del mercado. El estudio del laboratorio muestra lo mismo en `fuerza_4h` (+0,54 R en alcista de volatilidad baja, −0,43 R en bajista de volatilidad baja). | ALTO | [V] datos; que un filtro de régimen lo arregle es [H] (estudio en marcha) |
| Decisión | El filtro del cerebro en 4 h es lo único que cambia el signo (de −0,035 a +0,10 R) y lo mantiene en holdout, pero sin significación. En vivo, sus 9 operaciones dan +0,32 R, casi todas cortos en un mercado bajista: no distingue acierto de viento a favor. | ALTO | [V] |
| Decisión | En vivo el cerebro acepta el 40 % de las propuestas de 4 h (90 decisiones desde el 05/11, predicción media 0,039). En el laboratorio aceptaba el 24 % (854 de 3497). La distribución de rasgos en vivo no coincide con la de entrenamiento, o el régimen actual es atípico. | ALTO | [V] cifras; causa [NC] |
| Decisión | Confirmado el hallazgo 5: tras aceptar el cerebro, la memoria (vecinos más cercanos sobre resultados pasados) vuelve a juzgar y fija el tamaño entre 0,5 y 1. Son dos modelos sin validar encadenados. | ALTO | [V] `bot.py:834-858`, `aprendizaje.py:219-257` |
| Riesgo | El riesgo real por operación no es el 3 % configurado (≈ 7 $): varía entre 0,28 $ y 4,29 $. Las pérdidas y las ganancias no pesan igual, así que el resultado en dólares no sigue al resultado en R. | MEDIO | [V] `riesgo_inicial_usd` del ledger; qué límite recorta cada una [NC] |
| Riesgo | 94 rechazos por «tamaño mínimo excede riesgo». Con 232 $ el bot solo puede operar parte del universo, y no es una parte elegida por calidad. | MEDIO | [V] recuento; efecto en el resultado [H] |
| Ejecución | Las salidas en vivo y en el laboratorio siguen la misma lógica. `momentum` y `fuerza` no tienen objetivo (tp a 98 R): salen por tiempo o por stop. Por eso todas las ganancias aparecen como «tiempo máximo». No es un fallo. | — | [V] `gestor.py:1050-1072`, `estrategia.py:206-259` |
| Ejecución | Las 32 entradas simuladas se ejecutaron como maker. En real una orden límite se llena más a menudo cuando el precio va en contra (selección adversa). El simulador exige que el precio atraviese la orden, lo que lo mitiga solo en parte. | MEDIO | [V] fills; magnitud [NC] |
| Ejecución | Los stops se ejecutan cerca del disparo (mediana ≈ 0,05 % peor), con un caso de 1,67 % (WLD, −1,39 R). Si el laboratorio supone el mismo deslizamiento está [NC]. | BAJO | [V] `peor_que_trigger_pct` |
| Datos | Las dos predicciones más altas del cerebro (0,81 y 0,69) acabaron en pérdida y son anteriores al arreglo de datos externos del 04/11. Coherente con que la falta de datos inflaba la predicción. | — | [V], n = 2 |
| Datos | El ledger no guarda `exploracion_amplia` en la decisión: hay que deducirla de que no haya predicción. | BAJO | [V] |

### 4. Lo que la muestra no permite afirmar

- Que el cerebro de 4 h funcione en vivo. Nueve operaciones a favor de la tendencia no prueban nada.
- Que los largos sean malos en general: solo hubo mercado bajista.
- La diferencia «rechazadas mejor que aceptadas» del probador (hallazgo 3): mezcla sombras de 1 h y 4 h y fechas anteriores al arreglo del 04/11.

---

## FASE 3 — Veredicto, optimización y hoja de ruta

### 1. Veredicto

1. **El bot no gana dinero y hoy no hay razón para esperar que lo haga.** En vivo: −0,43 R por operación. En el laboratorio: las reglas sin filtrar pierden en 4 h y pierden con claridad en 1 h.
2. **Hay dos líneas que merecen trabajo**, y son distintas:
   - *Cerebro de 4 h:* +0,10 R por operación, igual fuera de muestra y en holdout. Es la señal de que hay algo, pero con t 2,66 y 1,68 frente a un listón de ≈ 4 puede ser azar.
   - *Carry de funding:* estadísticamente sólido, de riesgo bajo y rentabilidad modesta (7–12 % anual antes de los costes sin modelar).
3. **La prueba de dos semanas no puede decidir sobre el cerebro.** Con una desviación de ≈ 1,2 R por operación, confirmar +0,10 R con t ≥ 2 exige unas 500 operaciones. El cerebro abre unas 25 al mes: son más de 18 meses. La validación tiene que venir del laboratorio; el simulado solo sirve para comprobar que la ejecución real se parece a la simulada.
4. **El tamaño de la cuenta limita el resultado en dinero.** Con 232 $, un 10 % anual son 23 $. Que «gane dinero» en sentido práctico depende del capital, y subir capital solo tiene sentido después de validar.

### 2. Tabla priorizada

Orden: impacto alto, riesgo bajo y esfuerzo bajo primero. «Tras 18/11» indica que toca código o configuración de la huella y necesita aprobación de Roberto.

| # | Problema | Causa | Solución | Archivos | Beneficio esperado (hipótesis) | Prueba de validación | Cuándo |
|---|---|---|---|---|---|---|---|
| 1 | Se operan reglas con expectativa negativa | La exploración amplia abre lo que el cerebro rechaza y todo lo de 1 h | Apagar la exploración amplia con ejecución. Dejar 1 h y lo rechazado solo en sombra, que ya da los mismos datos sin coste | `config.json` → `exploracion_amplia.activa` | Elimina la mayor fuente de pérdida medida (−5,75 R en 7 operaciones) | El probador sigue acumulando sombras; el resultado operado deja de incluirlas | Tras 18/11 |
| 2 | Estrategias sin posibilidad razonable | t ≤ −2 en el laboratorio con cientos o miles de operaciones | Retirar de la operativa `retroceso_4h`, `reversion_4h`, `funding_4h` y todo 1 h. Mantener `ruptura_4h`, `momentum_4h` y `fuerza_4h` como base del cerebro | `config.json` (estrategias activas), `motor.py:116-147` | Sube la expectativa del conjunto antes de filtrar y reduce el ruido que el cerebro tiene que separar | Reentrenar el cerebro solo con las tres y comparar t y holdout con el modelo actual, como una única variante registrada | Laboratorio: ya. Operativa: tras 18/11 |
| 3 | No se sabe si el simulado se parece al laboratorio | Nunca se ha comparado operación a operación | Prueba de paridad: pasar cada operación cerrada por `SimSalida` con las velas reales y comparar su R con el R del ledger | Script nuevo fuera de la huella (clasificar en `ARCHIVOS_SIN_EFECTO`) | Dice si las cifras del laboratorio son trasladables; detecta deslizamiento y selección adversa | Diferencia media menor de 0,10 R en al menos 30 operaciones | Ya |
| 4 | El cerebro acepta en vivo el 40 % y en el laboratorio el 24 % | Rasgos en vivo con distinta distribución, o régimen atípico | Comparar la distribución de los 8 rasgos en vivo (ledger) con la de entrenamiento. Si un rasgo se desvía, corregir su cálculo | Script de lectura; si hay fallo, `mercado_unificado.py`, `contexto_externo.py` | Evita decidir con un modelo alimentado con datos distintos de los que aprendió | Media y percentiles de cada rasgo en vivo dentro del rango del entrenamiento; tasa de aceptación en vivo cerca del 24 % | Diagnóstico: ya. Arreglo: tras 18/11 |
| 5 | El cerebro es demasiado débil para decidir con un umbral fijo | Regresión lineal única para seis reglas distintas; pesos máximos de 0,085 R; umbral 0,05 R fijado a mano | (a) Medir el resultado por deciles de predicción: si no crece de forma ordenada, el modelo no sirve. (b) Elegir el umbral dentro del walk-forward. (c) Añadir la regla y el lado como rasgos. Todo como una sola variante declarada de antemano | `cerebro.py`, `laboratorio.py` | Si la señal es real, concentrarla en los deciles altos sube el R medio y el t | Resultado creciente por decil fuera de muestra y en holdout; t de la variante por encima del listón | Laboratorio: ya. Uso en vivo: tras 18/11 |
| 6 | Dos modelos sin validar deciden en cadena | La memoria vuelve a juzgar lo que el cerebro aceptó | Con el cerebro activo, no llamar a la memoria; dejarla solo para medir | `bot.py:850-858` | Decisión única y auditable; tamaño constante | Prueba unitaria: con cerebro que acepta, factor = 1 y sin llamada a `valorar` | Tras 18/11 |
| 7 | Sin datos externos se abre igualmente | La abstención cuenta como rechazo y la exploración la abre | Distinguir «abstención» de «rechazo»: una abstención no se explora | `cerebro_vivo.py:149-151`, `bot.py:838-849` | Ninguna operación abierta con datos incompletos | Prueba unitaria con datos externos caducados | Tras 18/11 (desaparece si se aplica el punto 1) |
| 8 | Dependencia del lado y del régimen | Reglas de tendencia aplicadas igual en mercado alcista y bajista | Esperar al estudio de régimen de BTC. Si mejora, incorporarlo como rasgo del cerebro, no como regla nueva | `investigacion.py` (en marcha), después `mercado_unificado.py` | Evitar el lado contrario al mercado, que es donde se concentró la pérdida | Mejora del R medio en la mayoría de los pares del estudio, con prueba de signos | Estudio: en marcha |
| 9 | Riesgo desproporcionado para un sistema sin validar | 3 % por operación, 9 % abierto, pérdida total 50 % | Bajar a 1 % por operación, 3 % abierto y 20 % de pérdida total. Registrar qué límite recorta cada tamaño | `config.json` → `riesgo`, `riesgo.py` | Resultado en dólares proporcional al resultado en R; menos caída | `riesgo_inicial_usd` con dispersión baja entre operaciones | Tras 18/11 |
| 10 | El ledger no marca la exploración | El campo no se escribe en la decisión | Guardar `exploracion_amplia` y el límite que fijó el tamaño | `bot.py` (plan de la decisión) | Análisis posteriores sin deducciones | Campo presente en decisiones nuevas | Tras 18/11 |
| 11 | La única línea con significación no está conectada | Carry con las fases 0 a 2 hechas y sin integrar | Fase 3 del carry en simulado, solo con contado de Hyperliquid (BTC, ETH, SOL, HYPE, ZEC), midiendo base y desajuste entre patas | `carry/`, `promocion.py`, ledger, panel | 7–10 % anual bruto, con poca caída; menos después de los costes sin modelar | 30 días en simulado: funding cobrado menos costes mayor que cero, y comparado con tener el dinero parado | Tras 18/11 |

### 3. Qué mantener, modificar y descartar

- **Mantener:** el laboratorio y su listón, el holdout sellado, las barreras hacia real, el ledger, la lógica de salidas (coincide con el laboratorio).
- **Modificar:** el cerebro (puntos 2, 4 y 5), el encadenado con la memoria (6), el riesgo (9).
- **Descartar de la operativa:** exploración amplia con ejecución, todo 1 h, `retroceso_4h`, `reversion_4h`, `funding_4h`. Siguen en sombra.
- **No hacer:** modelos más complejos, más rasgos al azar o más variantes. Cada variante sube el listón de todas (ya va por 1074).

### 4. Criterios para decir que funciona

Fijados antes de mirar los resultados, y todos necesarios:

1. **Laboratorio:** una variante declarada de antemano supera el t exigido fuera de muestra y en holdout, con factor de beneficio ≥ 1,15, y no es negativa en ninguno de los dos lados ni en más del 40 % de los trimestres.
2. **Paridad:** el R del simulado difiere del R del laboratorio en menos de 0,10 R de media sobre 30 operaciones o más.
3. **Simulado:** al menos 100 operaciones del cerebro (operadas y sombra), con R medio positivo y por encima de la referencia «todas en el lado del mercado».
4. **Real:** solo entonces, piloto mínimo mediante `promocion.py` y con aprobación expresa de Roberto.

Si el punto 1 no se cumple tras los cambios 2 y 5, la conclusión honrada es que las reglas direccionales no dan ventaja y el proyecto debe centrarse en el carry.

### 5. Límites de esta auditoría

- No se ejecutó el laboratorio ni ninguna prueba costosa. Las cifras son las ya guardadas.
- Sin comprobar: el deslizamiento y la comisión de entrada que supone el laboratorio, qué límite recorta cada tamaño, el papel de `ballenas.py` en vivo, y la causa de la diferencia de aceptación del cerebro.
- El estudio de régimen de BTC sigue en marcha y no tiene resultado.

---

## FASE 4 — Investigación externa, lista completa y plan

Qué se hizo: búsqueda de artículos académicos, informes de mesas de trading y repositorios de GitHub sobre qué gana dinero en perpetuos de cripto y cómo operan los bots conocidos; después se contrastó con el código del bot. No se descargó ni ejecutó código ajeno, no se lanzó el laboratorio y no se cambió código ni configuración.

Advertencia sobre las cifras externas: son las que publican sus autores. Ninguna se ha reproducido aquí y varias vienen de blogs o de vendedores. Sirven para orientar qué probar, no como promesa de resultado.

### 1. Qué dice la evidencia externa

| Línea | Qué se publica | Calidad de la fuente | Encaje con el bot |
|---|---|---|---|
| **Tendencia lenta** (seguir la subida de cada moneda durante semanas o meses) | Conjunto de canales de Donchian de 5 a 360 días, solo largos, stop móvil en la mitad del canal, sin objetivo, tamaño por volatilidad objetivo del 25 % anual, 20 monedas líquidas. 2015–2025: ≈ 18 % anual neto con coste del 0,10 % (Zarattini, Pagani y Barbon). Una réplica no oficial solo con BTC da Sharpe 1,12 y caída máxima del 18,5 %. | Artículo de trabajo con universo sin sesgo de supervivencia. Diseño fuera de muestra sin verificar. | Es lo contrario de lo que hace el bot (ver apartado 3). Datos disponibles: sí (6 años en 4 h). |
| Tendencia por intervalo | Con coste de 4 pb: 1 h Sharpe 1,54 con 847 operaciones al mes; 4 h 2,08; 6 h 2,41; diario 1,63. Sin stop móvil cae a 1,68. Por régimen: alcista +68 %, lateral +19 %, bajista −4 % (*AdaptiveTrend*, arXiv 2602.11708). | Preprint sin revisar, con reoptimización mensual (riesgo de mirar al futuro). Las cifras absolutas no son fiables; el orden entre intervalos sí es coherente con el resto. | Coincide con el laboratorio del bot: todo 1 h negativo y la tendencia pierde en bajista. |
| Momentum en cripto | El de serie temporal (cada moneda contra su propio pasado) es fuerte; el transversal (ranking entre monedas) es débil. La ganancia viene de la pata larga y de las monedas grandes y líquidas (Han, Kang y Ryu; Fieberg y otros, JFQA; Cakici y otros, 2024). | Académica, revisada en parte. | `fuerza` es transversal con una sola moneda por lado; el universo incluye memecoins desde 3 M$. |
| **Carry con dos patas** (perpetuo corto y contado largo) | «El carry de nivel ha muerto»: +5,6 % anual en 2023–2026, decreciente hasta negativo en 2026 y por debajo del tipo sin riesgo. El Sharpe de 8,5 es un artefacto: un cobro casi constante parece seguro hasta el día del salto de base o de la liquidación en cascada (octubre de 2025). La diferencia de funding Hyperliquid–Binance pasó del 7,6 % en 2023 a ≈ 1 % anual en 2025–26. | Dos análisis independientes con datos (bryanvine; Delphic Alpha) y un informe sectorial (1Token). | El «t 8–10» del laboratorio del bot tiene el mismo artefacto. Hay que volver a medirlo solo con 2026. |
| **Factor de funding transversal** (solo perpetuos: largo en las de funding bajo, corto en las de funding alto) | Señal: funding medio de Binance en 7 días; tercios; pesos por volatilidad inversa; rebalanceo diario o semanal. Fuera de muestra 2025–26: Sharpe 1,13 (Delphic Alpha). Otro análisis más estricto: Sharpe 0,39 fuera de muestra, caída máxima del 35 %, probabilidad de sobreajuste 0,81. Rebalancear cada 8 h lo convierte en pérdida. En Hyperliquid la señal propia no funciona desde 2024; la de Binance sí (RobotWealth). | Tres fuentes independientes que coinciden en el signo y discrepan en el tamaño. | El bot ya lee el funding de Binance y opera perpetuos en Hyperliquid. Falta un módulo de cartera. |
| Aprendizaje automático direccional, sentimiento diario, arbitraje estadístico | Clasificados como «muertos» tras costes en la serie de bryanvine. Una idea propuesta por un modelo de lenguaje tuvo t 3,22 dentro de la ventana y 0,48 fuera. | Un autor, método cuidado. | Refuerza «no hacer modelos más complejos». |
| Copiar ballenas; reversión tras liquidaciones | Sin evidencia independiente de que sea rentable. | Solo blogs de vendedores. | Coincide con el bot: `ballenas_1h` y `liquidaciones_1h` sin muestra. |
| Expectativa realista | Las ventajas que sobreviven (tendencia, factor de funding) quedan en Sharpe neto ≈ 0,4–0,5 según el análisis más estricto, y hasta ≈ 1 según los más favorables. | — | Con 232 $ es poco dinero en cualquier caso. |

Datos oficiales de Hyperliquid que afectan al diseño [V en su documentación]: comisión de perpetuos 0,045 % taker y 0,015 % maker (igual que en el bot); contado 0,070 % y 0,040 %; el funding se paga cada hora; el componente de interés es 0,01 % cada 8 h, es decir ≈ 11,6 % anual que **los largos pagan a los cortos** cuando la prima es cero. Valor mínimo por orden: 10 $ (fuentes secundarias).

### 2. Cómo operan los bots de código abierto

| Herramienta | Cómo opera | Qué se aprovecha | Qué no |
|---|---|---|---|
| Freqtrade | Marco de estrategias con backtest, optimizador, modo simulado y modelos adaptativos (FreqAI). No publica resultados. | Sus comprobaciones automáticas de mirada al futuro (`lookahead-analysis`) y de fórmulas recursivas (`recursive-analysis`). | Cambiar de marco: el bot ya tiene lo equivalente. |
| Passivbot | Creador de mercado «a contracorriente» con martingala: entra pequeño y dobla cuando el precio va en contra; optimizador evolutivo sin separación entre entrenamiento y validación. | Nada. | Todo: añadir a perdedores con apalancamiento gana a menudo y pierde la cuenta de golpe. |
| Hummingbot v2 | Creación de mercado con horquillas fijas, rejillas y arbitraje de funding entre plataformas. | Nada con esta cuenta. | Sin evidencia de rentabilidad en cuentas pequeñas; exige operar en varias plataformas. |
| SILVR | Implementación del conjunto de Donchian: 15 monedas, 9 ventanas, entrada en la apertura siguiente, stop en la mitad del canal que solo sube, sin objetivo, tope de riesgo del 0,5 % por porción, salta órdenes por debajo del mínimo, interruptor de caída del 30 %, cada ejecución cuenta como una mirada a los datos. | El diseño completo como plantilla del estudio de tendencia. | No publica resultados. |
| DELTA_NEUTRAL_HYPERLIQUID_PERP_SPOT | Carry con dos patas en Hyperliquid: ordena por funding medio de 7 días («el de una hora es ruido»), exige volumen ≥ 75 M$ y funding ≥ 5 % anual, mantiene 7 días como mínimo, solo cambia si la mejora en 8 días supera las comisiones de 4 patas. | Las reglas de permanencia y cambio, si algún día se retoma el carry. | Admite que no tiene protección de distancia a liquidación. |
| Carry-Desk | Calcula el neto con el coste real del libro; calibrado con 63.000 órdenes: los costes en altcoins salen entre 0,1 y 3 veces lo estimado. | La idea de medir el coste contra el libro archivado. | — |

### 3. Contraste con el código del bot

| Aspecto | El bot hoy | Lo que respalda la evidencia | Evidencia |
|---|---|---|---|
| Horizonte de `ruptura` | Máximo de 20 o 40 velas (3 a 7 días en 4 h; 20 a 40 horas en 1 h) y cierre forzoso a las 30 velas (5 días) | Canales de 5 a 360 días y posición abierta mientras dure la tendencia | [V] `senales.py:144`, `:274-277` |
| Salidas de `ruptura` | Cobro parcial a 1,5 R, objetivo final 4 R, stop móvil a 1,5 R | Sin objetivo; solo stop móvil | [V] `senales.py:276` |
| `momentum` | Mira 10 a 30 días, cierra a los 7 días, sin objetivo, largos y cortos | Parecido en idea; horizonte corto y sin conjunto de ventanas | [V] `senales.py:318-328` |
| `fuerza` | Ranking entre monedas, **una** moneda por lado, cada 7–14 días | El momentum transversal es el débil; cuando se usa, tercios con pesos por volatilidad | [V] `senales.py:306-315` |
| `funding` | A contracorriente: largo cuando el funding es muy negativo y el precio gira | En Hyperliquid, funding muy negativo anticipa más caídas | [V] `senales.py:179-190`; laboratorio −0,136 R y −0,418 R en holdout |
| Tamaño | Riesgo fijo por operación según la distancia al stop | Volatilidad objetivo de la cartera repartida entre monedas | [V] `riesgo.py:121` |
| Universo | 40 monedas desde 3 M$ de volumen, con memecoins forzadas | 15–20 monedas grandes y líquidas | [V] `config.json` → `universo` |
| Cerebro | Filtro sobre reglas con expectativa ≈ 0 o negativa | Un filtro de este tipo depende de la calidad de la regla de partida | [V] estructura; [H] que no pueda rescatarlas |
| Laboratorio | Evalúa operaciones sueltas (`cartera()`: 2 posiciones, 1 %) | Las líneas con respaldo son carteras con rebalanceo | [V] `laboratorio.py:754-770` |
| Validación | Walk-forward, embargo, holdout sellado, t ajustado por variantes, línea base de entrada aleatoria | Lo mismo más probabilidad de sobreajuste (PBO) y Sharpe deflactado | [V] `validacion.py:279`; PBO ausente |

Puntos que quedaban sin comprobar y ahora están resueltos:

- **Coste de entrada del laboratorio** [V]: supone entrada a mercado (taker) con deslizamiento mínimo del 0,02 % que crece con la volatilidad (`laboratorio.py:81`, `:204-206`). El simulado llena las entradas como maker. El laboratorio es por tanto más prudente que el simulado, y es una fuente conocida de diferencia entre ambos.
- **Qué límite fija el tamaño** [V]: en 70 de 71 planes del ledger lo fija el presupuesto de riesgo base (`limitado_por: base`). La dispersión del riesgo real (0,28 a 4,29 $) viene de mezclar exploración al 0,5 % con cerebro al 3 % y del factor de la memoria, no de otros topes.
- **Historia disponible** [V]: 6 años en 4 h y 4 en 1 h con Binance y Bybit (`configuracion.py:162-163`). Alcanza para ventanas de hasta 360 días.

Siguen sin comprobar: la causa de la diferencia de aceptación del cerebro (40 % en vivo, 24 % en laboratorio) y el papel de `ballenas.py` en vivo. El estudio de régimen de BTC sigue ejecutándose (relanzado a las 08:33 del 13/11, 240 minutos).

### 4. Lista completa de errores y puntos de mejora

Reúne las fases 1 a 3 y lo nuevo de la investigación (marcado **N**). «Tras 18/11» significa que toca la huella y necesita la aprobación de Roberto.

**A. Estrategia**

| # | Nivel | Error o mejora | Qué hacer | Cuándo |
|---|---|---|---|---|
| 1 | CRÍTICO | Ningún componente tiene ventaja demostrada: los dos cerebros en `no_supera`, ninguna regla pasa el laboratorio [V] | Sustituir las reglas de partida (puntos 4 a 6), no afinar el filtro | Estudios: ya |
| 2 | CRÍTICO | Se operan reglas con expectativa negativa mediante la exploración amplia: −5,75 R en 7 operaciones, 0 ganadoras [V] | Apagar la ejecución de la exploración; dejarla en sombra | Tras 18/11 |
| 3 | CRÍTICO | Todo 1 h pierde (t −5,36; holdout −6,76) [V]. La evidencia externa coincide: a más frecuencia, más coste y menos ventaja **N** | Retirar 1 h de la operativa | Tras 18/11 |
| 4 | ALTO | **N** Las reglas de tendencia miran y mantienen demasiado poco: 3–7 días y cierre a los 5 [V]. Lo publicado usa 5–360 días [H que alargar mejore] | Estudio A (apartado 5) | Ya |
| 5 | ALTO | **N** Las salidas recortan las ganancias grandes: parcial a 1–1,5 R, punto de equilibrio a 1 R, objetivo 3–4 R, tiempo máximo [V]. En tendencia, unas pocas operaciones muy largas dan casi todo el resultado [H]. Las dos reglas del bot sin objetivo son las menos malas en holdout [V] | Estudio A: solo stop móvil | Ya |
| 6 | ALTO | **N** Tamaño por operación en lugar de volatilidad objetivo de cartera [V] | Estudio A | Ya |
| 7 | ALTO | Dependencia del lado y del régimen: 1 de 15 largos ganó en la caída; `fuerza_4h` +0,54 R en alcista y −0,43 R en bajista [V] | Esperar al estudio de régimen; si ayuda, como rasgo y no como regla | En marcha |
| 8 | ALTO | **N** El carry con dos patas, tratado como la línea más sólida, está comprimido en 2025–26 y su t alto es un artefacto de cobro constante [H para los datos del bot] | Volver a medirlo solo con 2026, neto del tipo sin riesgo y con el peor salto de base. Aplazar la fase 3 del carry hasta verlo | Medición: ya |
| 9 | MEDIO | **N** `funding` opera a contracorriente y la evidencia en Hyperliquid va en el otro sentido; el laboratorio lo confirma [V] | Retirarla junto con `retroceso_4h` y `reversion_4h` | Tras 18/11 |
| 10 | MEDIO | **N** `fuerza` concentra en una moneda por lado y usa el tipo de momentum más débil [V]/[H] | No ampliar su rejilla; mantenerla solo en sombra hasta el estudio A | Tras 18/11 |
| 11 | MEDIO | **N** Universo de 40 monedas con memecoins desde 3 M$: lo contrario de donde se publica que la tendencia sobrevive [H] | Para lo que se opere: 15–20 monedas grandes. Las demás, en sombra | Tras 18/11 |
| 12 | MEDIO | **N** Cortos tratados igual que largos. Lo publicado da la ganancia a la pata larga y exige más a los cortos. En vivo los cortos fueron mejor, pero en un mes bajista [H] | El estudio A se declara solo largos; los cortos, pregunta aparte y posterior | Ya |
| 13 | MEDIO | Las señales de ballenas y de liquidaciones no tienen evidencia propia (n 33 y 22) ni externa [V] | Fuera de la operativa; el nombre del bot es cosmético | Tras 18/11 |
| 14 | — | **N** Candidato nuevo: factor de funding transversal con señal de Binance | Estudio B | Tras el A |

**B. Cerebro y decisión**

| # | Nivel | Error o mejora | Qué hacer | Cuándo |
|---|---|---|---|---|
| 15 | ALTO | En vivo lo rechazado rindió más que lo aceptado (muestra pequeña) [V] | Medir por deciles de predicción en el laboratorio | Ya |
| 16 | ALTO | Acepta el 40 % en vivo y el 24 % en el laboratorio [V]; causa [NC] | Comparar la distribución de los 8 rasgos en vivo y en entrenamiento | Ya (solo lectura) |
| 17 | ALTO | Pesos máximos de 0,085 R frente a un umbral de 0,05 R fijado a mano [V] | Umbral elegido dentro del walk-forward; regla y lado como rasgos; una sola variante | Laboratorio: ya |
| 18 | ALTO | **N** El cerebro filtra reglas sin ventaja; un filtro así rescata poco [H] | Prioridad a los estudios A y B. El cerebro, como capa opcional solo si sus deciles salen ordenados | — |
| 19 | ALTO | La memoria vuelve a juzgar lo que el cerebro aceptó: dos modelos sin validar en cadena [V] `bot.py:834-858` | Con cerebro activo, la memoria solo mide | Tras 18/11 |
| 20 | MEDIO | Sin datos externos el cerebro se abstiene, pero la exploración abre la operación [V] | Distinguir abstención de rechazo | Tras 18/11 |
| 21 | ALTO | El resultado reciente lo explica la caída del mercado, no la selección: +12,30 $ todo en corto frente a +1,32 $ del bot [V] | Mantener «¿Bot o mercado?» como referencia obligatoria | Ya existe |

**C. Riesgo y capital**

| # | Nivel | Error o mejora | Qué hacer | Cuándo |
|---|---|---|---|---|
| 22 | CRÍTICO | Riesgo de sistema validado en uno sin validar: 3 % por operación, 9 % abierto, apalancamiento 5, pérdida tolerada 50 % [V] | 1 %, 3 % y 20 %; apalancamiento 2 | Tras 18/11 |
| 23 | MEDIO | El riesgo real por operación varía de 0,28 a 4,29 $; ahora se sabe por qué (exploración y memoria) [V] | Se corrige con los puntos 2 y 19 | Tras 18/11 |
| 24 | MEDIO | 94 rechazos por tamaño mínimo [V]. **N** Con 10 $ de mínimo por orden y 232 $, una cartera de 20 monedas no cabe: caben de 3 a 5 [V por cálculo] | Decisión de Roberto: probar las carteras en simulado con un saldo ficticio mayor (por ejemplo 2.000 $) o limitarlas a 5 monedas | Tras 18/11 |
| 25 | MEDIO | **N** Un largo en perpetuo paga de base ≈ 11,6 % anual de funding cuando la prima es cero. Una tendencia solo largos carga con ello [V en la documentación] | El estudio A debe incluir el funding real. Alternativa a medir: contado de Hyperliquid en BTC, ETH, SOL, HYPE y ZEC | Ya |
| 26 | — | Con 232 $, un 10 % anual son 23 $ [V] | Subir capital solo después de validar, y es decisión de Roberto | — |

**D. Ejecución y simulación**

| # | Nivel | Error o mejora | Qué hacer | Cuándo |
|---|---|---|---|---|
| 27 | ALTO | Nunca se ha comparado el simulado con el laboratorio operación a operación [V] | Prueba de paridad con `SimSalida` y el ledger | Ya (script fuera de la huella) |
| 28 | MEDIO | Entradas simuladas como maker y laboratorio como taker [V]; en real hay selección adversa de magnitud [NC] | La paridad lo mide; en real, calibrar con el piloto | Ya |
| 29 | BAJO | Stops ≈ 0,05 % peor que el disparo, con un caso del 1,67 % [V] | Vigilar en la paridad | Ya |
| 30 | BAJO | El ledger no marca `exploracion_amplia` en la decisión [V] | Guardar el campo | Tras 18/11 |

**E. Validación e investigación**

| # | Nivel | Error o mejora | Qué hacer | Cuándo |
|---|---|---|---|---|
| 31 | ALTO | La prueba de dos semanas no puede decidir sobre el cerebro: confirmar +0,10 R exige unas 500 operaciones [V por cálculo] | Tomarla como prueba de funcionamiento, no de rentabilidad | — |
| 32 | MEDIO | **N** El laboratorio no puede evaluar carteras con rebalanceo y volatilidad objetivo [V] | Evaluador por días: rendimiento diario de la cartera, t por días, caída máxima | Ya (archivo nuevo sin efecto) |
| 33 | MEDIO | **N** Falta medir el sobreajuste por selección: PBO y Sharpe deflactado [V] | Añadirlos al informe de cada estudio | Ya en estudios nuevos; en `validacion.py` (dentro de la huella), tras 18/11 |
| 34 | MEDIO | **N** No hay prueba automática de mirada al futuro en los rasgos | Prueba unitaria: cada rasgo calculado con la historia cortada en *t* debe coincidir con el calculado con la historia completa | Ya (solo pruebas) |
| 35 | MEDIO | 1074 variantes probadas: cada idea nueva sube el listón de todas [V] | Tres preguntas declaradas de antemano como máximo (apartado 5); ninguna rejilla | Ya |
| 36 | BAJO | Agenda: «en marcha» 6 h y bloqueos de 12 h [V] | Ajustar a la duración real | Tras 18/11 |
| 37 | BAJO | `CLAUDE.md` desfasado («1 h = sin modelo»); `copias/` ensucia las búsquedas [V] | Actualizar; mover `copias/` fuera | Cuando se quiera |

**F. Operación y seguridad**

| # | Nivel | Error o mejora | Qué hacer | Quién |
|---|---|---|---|---|
| 38 | MEDIO | Panel por túnel sin contraseña (`panel.tunel_sin_clave`) [V] | Poner `PANEL_PASSWORD` en `.env` y quitar la opción | Roberto |
| 39 | MEDIO | Clave de Groq pendiente de rotar | Rotarla | Roberto |
| 40 | BAJO | Sin avisos de Telegram ni vigilancia externa; el bot corre en un PC doméstico | Telegram y migración al VPS | Roberto |

**G. Qué no añadir** (lo descarta la investigación)

- Martingala, rejillas o promediar a la baja (Passivbot).
- Creación de mercado (Hummingbot): no hay evidencia con cuentas pequeñas.
- Modelos más complejos, aprendizaje por refuerzo o señales generadas por modelos de lenguaje.
- Copiar ballenas y operar liquidaciones.
- Más rasgos o más variantes sin pregunta previa.

### 5. La solución propuesta

No existe una solución que garantice ganancias, y ninguna fuente seria la ofrece. Lo que sí hay es una dirección con respaldo y una forma de comprobarla sin engañarse. La propuesta es dejar de buscar muchas señales rápidas con un filtro encima y pasar a **una o dos carteras lentas, sencillas y documentadas**, cada una validada como una única pregunta declarada de antemano.

**Tres preguntas, fijadas antes de mirar ningún resultado** (sin rejillas; cada una cuenta como una variante):

| Estudio | Regla exacta | Se da por buena si |
|---|---|---|
| **A. Tendencia lenta** | Velas diarias (cierre de 00:00 UTC, a partir de las de 4 h). 15 monedas más líquidas en cada fecha, con al menos un año de historia. Nueve ventanas de Donchian: 5, 10, 20, 30, 60, 90, 150, 250 y 360 días. Cada ventana: largo cuando el cierre supera el máximo; salida cuando el cierre cae bajo la mitad del canal, que solo sube. Sin objetivo y sin tiempo máximo. Solo largos. Peso por moneda = (25 % ÷ volatilidad anual de 90 días) ÷ 15, repartido entre las nueve ventanas; exposición total máxima 2×. Costes: taker 0,045 %, deslizamiento del laboratorio y funding real | Sharpe neto fuera de muestra > 0,5 y positivo en holdout; t por días por encima del listón; mejor que mantener BTC con la misma volatilidad; PBO < 0,5; no negativa en más del 40 % de los años |
| **B. Factor de funding** | Cada lunes: funding medio de Binance de los últimos 7 días en las monedas con perpetuo en Binance y en Hyperliquid. Largo en el tercio más bajo y corto en el más alto, pesos por volatilidad inversa de 30 días, neutral en dólares. Mismos costes | Sharpe neto fuera de muestra > 0,4 y positivo en holdout; caída máxima < 35 %; no depende de tres monedas (repetir sin las tres que más aportan) |
| **C. Carry en 2026** | El `carry_realista` actual, sin tocar, medido solo con datos de 2026 y restando el tipo sin riesgo; añadir el peor salto de base dentro de cada tramo | Rentabilidad neta por encima del tipo sin riesgo en 2026. Si no, el carry se archiva |

**Orden de trabajo:**

1. *Ahora, fuera de la huella y sin tocar la prueba:* prueba de paridad (27), comparación de rasgos del cerebro (16), evaluador de carteras por días (32), estudio C (el más barato, reutiliza código), estudio A, estudio B. Comprobado en `promocion.py:50-64`: `laboratorio.py` y `validacion.py` están dentro de la huella y no se tocan; `investigacion.py` y `estudios.py` están fuera, así que los estudios van ahí o en archivos nuevos clasificados como «sin efecto», que solo importan funciones del laboratorio sin modificarlas. Cada estudio necesita la autorización de Roberto porque usa horas de cálculo.
2. *Tras el 18/11, con aprobación:* apagar la exploración con ejecución (2), retirar 1 h y las reglas negativas (3, 9, 13), quitar la memoria de la cadena (19), bajar el riesgo (22), reducir el universo operado (11).
3. *Si el estudio A pasa:* motor de cartera nuevo en simulado, que sustituye a `ruptura`, `momentum` y `fuerza`. Tres meses en simulado para comprobar paridad con el estudio, no para medir rentabilidad.
4. *Si el estudio B pasa:* segunda cartera, independiente de la primera.
5. *Si ninguno pasa:* la conclusión es que con estos datos y este capital no hay ventaja demostrable, y lo sensato es no pasar a real.
6. *Paso a real:* solo con `promocion.py` y la aprobación expresa de Roberto, como hasta ahora.

**Qué esperar si sale bien.** Las fuentes más estrictas dejan estas ventajas en un Sharpe neto de 0,4 a 0,5 y las más favorables cerca de 1, con caídas del 20 al 35 % en los años malos (el factor de funding perdió en 2022 y 2023; la tendencia pierde en los mercados bajistas). Con 232 $ eso son unas decenas de dólares al año en el mejor caso. El valor del trabajo está en saber si hay ventaja antes de arriesgar más capital.

### 6. Límites de esta fase

- Ninguna cifra externa se ha reproducido. El PDF de *Catching Crypto Trends* no se pudo leer entero: las reglas vienen de un resumen de terceros y faltan sus tablas de costes y de caída máxima. El artículo de Delphic Alpha es de pago y solo se leyó la parte abierta.
- No se encontró ningún estudio riguroso que compare objetivos fijos con stops móviles en cripto. El punto 5 de la lista es una hipótesis que el estudio A pone a prueba.
- Las condiciones de margen de cartera de Hyperliquid varían según la fuente; no afectan a esta cuenta por tamaño.
- Los umbrales de «se da por buena» del apartado 5 son nuevos y solo valen para los estudios nuevos. No cambian los criterios del veredicto de la prueba de dos semanas.

### 7. Fuentes

Tendencia: [Catching Crypto Trends (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907) · [resumen de CXO Advisory](https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/) · [AdaptiveTrend (arXiv)](https://arxiv.org/html/2602.11708v1) · [Han, Kang y Ryu](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf) · [Fieberg y otros (JFQA)](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/trend-factor-for-the-cross-section-of-cryptocurrency-returns/4C1509ACBA33D5DCAF0AC24379148178) · [Cakici y otros](https://open.icm.edu.pl/items/7566337e-2e7e-40e7-86da-413d57c313b0)

Funding y carry: [bryanvine, serie](https://bryanvine.github.io/alpha-research/) · [bryanvine, artículo 2](https://bryanvine.github.io/alpha-research/paper2.html) · [Delphic Alpha](https://delphicalpha.substack.com/p/strategy-crypto-funding-carry-makes) · [RobotWealth](https://edgealchemy.robotwealth.com/p/hyperliquid-carry-looks-trendy) · [1Token](https://blog.1token.tech/crypto-strategy-returns-in-2026-and-the-next-opportunity-set/)

Hyperliquid: [comisiones](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees) · [funding](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding) · [orden mínima (secundaria)](https://www.buildix.trade/blog/hyperliquid-minimum-order-size-all-pairs-leverage-limits-2026)

Repositorios: [SILVR](https://github.com/ceezey/SILVR) · [DELTA_NEUTRAL_HYPERLIQUID_PERP_SPOT](https://github.com/djienne/DELTA_NEUTRAL_HYPERLIQUID_PERP_SPOT) · [Carry-Desk](https://github.com/grzresearch/Carry-Desk-Funding-Arbitrage-Hyperliquid-Lighter) · [Passivbot](https://github.com/enarjord/passivbot) · [Freqtrade](https://github.com/freqtrade/freqtrade) · [Hummingbot](https://github.com/hummingbot/hummingbot)

Validación: [Sharpe deflactado](https://papers.ssrn.com/abstract=2460551) · [probabilidad de sobreajuste](https://papers.ssrn.com/abstract=2326253) · [meta-etiquetado](https://hudsonthames.org/meta-labeling-a-toy-example/)

---

## FASE 5 — Implementación y resultados (13/11/2026)

Restricciones de Roberto: no tocar operaciones ni saldos, y mantener los límites de operaciones y riesgo como hoy. Por eso NO se aplicó: apagar la exploración amplia, retirar estrategias de 1 h o negativas, bajar el riesgo ni reducir el universo.

**Estudios nuevos** (paquete `estudios_ext/`, fuera de la huella, sin red; informes en `registro/estudio_*.json`):
- **A, tendencia lenta (Donchian 5–360 d, solo largos)** [V]: 2021-11 a 2026-11, Sharpe neto 0,51, t por días 1,15, holdout negativo (−0,46), PBO 0,54, 2022/2025/2026 negativos. No cumple los criterios. Ojo: sesgo de supervivencia y exposición media solo del 7 %.
- **B, factor de funding (terciles, semanal)** [V]: Sharpe neto 1,21, t 2,91, holdout 1,92, caída máx. 21 %, todos los años positivos; invertida −1,6, aleatoria ≈ −0,3, retrasada 7 d 0,96. Cumple los criterios, pero con sesgo de supervivencia, datos de Binance y sin validar en vivo [H]. Es el candidato a un módulo de cartera.
- **C, carry por periodos** [V]: rentabilidad sobre capital reservado 3,9 % (2.º sem. 2024), 0,45 % (2025), 0,15 % (2026) frente a 4 % del efectivo. Se archiva.
- **Paridad** [V]: 27 operaciones; diferencia media de salida +0,055 R, 70 % misma causa. Sin muestra para concluir (<30). Los stops de 1 h salen peor en vivo (−1,66 y −1,39 R frente a −1,02 R).
- **Rasgos del cerebro** [V]: funding8h con 3 valores extremos (hasta 94 desviaciones) que el modelo recorta a ±5 y aun así predice +0,8 R. Hallazgo para una variante del laboratorio (recortar a ±3), no aplicado.

**Cambios de código** (560 pruebas OK): la memoria ya no vuelve a juzgar lo que el cerebro aceptó (`bot.py`); el ledger guarda `exploracion_amplia`/`explorando` y `abstencion`; el probador separa abstenciones de rechazos; bloqueos de agenda unificados a 12 h.
Reinicio pedido con `/aplicarconfig` (id `ajustes-20261113`); no se confirmó que se haya aplicado.

**Actualización 13/11 (13:45).**
- Reinicio aplicado (el primer intento no se leyó: PowerShell escribió el JSON con BOM y el bot lo ignora; reenviado sin BOM, id `ajustes-20261113b`). El bot nuevo arrancó sin errores con el cerebro `cerebro-lab-20261108T030001Z`; las 4 posiciones (kPEPE, ARB, ENA, UNI) y el efectivo no cambiaron.
- **Estudio de régimen de BTC terminado** [V]: operar a favor de la tendencia de BTC mejora el R medio en 19 de 20 pares (+0,044 R de diferencia media, p de signos ≈ 0). En 4 h pasa de +0,010 a +0,052 R (24.570 → 14.809 operaciones) y en 1 h de −0,033 a +0,013 R. Salida sin objetivo, stop 2 ATR. Es una pista, no una estrategia: cualquier combinación elegida debe pasar el examen normal de la investigación, y cuenta como variante.


**Actualización 13/11 (19:35): las tres mejoras, en la operativa simulada, y 1 h retirada.**
- **Estrategias de 1 h retiradas** [V]: `ruptura_1h`, `retroceso_1h`, `reversion_1h`, `funding_1h` y `fuerza_1h` con `activa: false`. Siguen observándose (sin operar) las hipótesis de solo investigación.
- **Filtro de régimen de BTC** [V en pruebas]: `filtros_entrada.regimen_btc` activo (media de 200 velas). En contra del régimen no entra; régimen desconocido tampoco (falla cerrado); la exploración amplia no se lo salta. Reduce operaciones: es el efecto buscado, no un límite nuevo de riesgo.
- **Cerebro con recorte ±3** [V en pruebas]: `cerebro.RECORTE_Z = 3.0`. El modelo vigente (`cerebro-lab-20261108T030001Z`) se entrenó con ±5: hasta el laboratorio del domingo 15/11 se evalúa con un recorte distinto al de su entrenamiento.
- **Cartera del factor de funding** [V en pruebas; sin operación real todavía]: módulo `cartera_funding.py`, solo simulado. Primer rebalanceo: lunes 16/11 00:00 UTC. 2 patas por lado como mucho, 1 % de riesgo por pata, stop de 3 volatilidades diarias, las dos patas o ninguna, sin pasar por el cerebro. Usa los límites de siempre (6 posiciones, 4 del mismo lado, 9 % de riesgo abierto): con los 4 cortos de hoy abiertos y ≈ 8,6 % de riesgo usado NO cabría ninguna pata; solo abrirá si para el lunes se han liberado huecos.
- **Diferencias con el estudio B, sin ocultar**: funding de Hyperliquid (no Binance), universo por volumen de 24 h, 2 patas por lado en vez de un tercio del universo, con stops. Lo que opera no es lo que se midió; nada de esto está validado como rentable.
- **Límites conocidos**: los filtros de ejecución del segundo paso (correlación, agregados) aún podrían dejar una pata sin pareja; una pata mantenida varias semanas se cierra al llegar al tope global de 336 h; todos estos cambios reinician la evidencia en vivo y cambian la huella de aprobación.
- **Comprobación de no afectar** [V]: foto de `papel.json` y `estado.json` antes y después del reinicio (18:30 UTC, id `cartera-regimen-193005`): efectivo 229,268 $, las 4 posiciones (kPEPE, ARB, ENA, UNI), tamaños, entradas, stops, duraciones, identificadores y las 8 órdenes, idénticos. Único cambio: aparece la clave `cartera_funding` en el estado.
- Pruebas: 576 OK (16 nuevas en `tests/test_cartera_regimen.py`). `--validar-config` OK.
- Pendiente: guardar en el brain (esta sesión solo tiene herramientas de lectura del brain); mostrar la cartera en el panel web (los datos ya van en `panel_datos.json`, falta la vista).

**Actualización 13/11 (19:50):** el panel web ya muestra el régimen de BTC y la cartera de funding (página Estrategias) y marca las posiciones de la cartera en la portada. Reinicio 18:40 UTC sin cambios en posiciones ni saldo.

**Actualización 14/11 (20:40):** momentum pasa a v2 (breakeven y trailing a 1,5 R, sin objetivo) por petición de Roberto; solo operaciones nuevas, la UNI abierta conserva su salida v1. Reinicio 18:34 UTC sin cambios en posiciones ni saldo. Valores de criterio, sin evidencia de mejora; el laboratorio del 15/11 los mide.

**Actualización 14/11 (20:50):** panel con ajuste manual de stop/objetivo (solo simulado, solo local) y stops de ENA y UNI movidos a mano según la regla de momentum v2 (ENA 0,16023→0,14239; UNI 6,9109→5,8867). Posiciones y saldo sin otros cambios. El panel y el bot se reiniciaron. Un ajuste inválido de objetivo cancelaba antes el existente: corregido (valida antes de cancelar).

**Actualización 17/11:** revisión de 10 repositorios externos (Kronos, TradingAgents, day-trader-skill, last30days-skill, tick-stock-panel, Vibe-Trading, trader-skill, freqtrade, daily_stock_analysis, QuantDinger) y sus frontends. Casi todo lo útil ya existía en el bot (estrés de costes, Bonferroni, purga/embargo, vigilancia de degradación, pausa tras racha, enfriamiento, caída máxima, distancia a liquidación). Implementado a petición de Roberto: búsqueda congelada; hipótesis prerregistradas `fuerza_4h` y `carry_realista` (preregistro.py, solo informe, juicio único tras 30 operaciones y 20 días posteriores al 17/11); laboratorio solo con estrategias de 4 h; meseta de parámetros en el veredicto; prueba de lookahead (sin fugas encontradas); CSV sin fórmulas, fichas «sin dato»/«ninguno» y título con operaciones abiertas en el panel; control de ruido en Telegram. 639 pruebas OK. Límites de riesgo y operaciones sin cambios.

**Actualización 18/11:** análisis completo de Jakeschincariol/day-trader-skill (11 skills, 47 issues, 20 PR): sin ventaja medida (PR #53: −0,125 R en 15.415 operaciones de ruptura del rango de apertura). Implantado por elección de Roberto: (A) un riesgo desconocido ya no cuenta como 0 (riesgo.riesgo_posicion; bloquea entradas y avisa en el panel) y (C) ficha «Qué cabe esperar» por operación con datos fuera de muestra del laboratorio (validacion.probabilidades). 650 pruebas OK. Reinicio 10:55 UTC sin cambios en posiciones ni saldo. La propuesta B (freno por movimiento en contra) queda aparcada.
