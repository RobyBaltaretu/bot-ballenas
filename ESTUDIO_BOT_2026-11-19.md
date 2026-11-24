# Estudio completo del bot — 19/11/2026

Revisión de código, configuración, reglas, registros, operaciones simuladas, laboratorio e investigación externa.
No se ha cambiado nada del bot para hacer este estudio. Todo lo que se cita está medido sobre los archivos reales
(`bot.log`, ledger, `panel_datos.json`, laboratorio del 15/11, `config.json`) salvo donde se indica que es de internet.

---

## 0. Resumen en 10 líneas

1. **El código está sano**: 693 pruebas pasan, no hay nombres indefinidos ni `except:` desnudos, y el código muerto es poco.
2. **El problema no es el código, es la ventaja**: el laboratorio ha probado **840 ideas y 1 098 variantes** y ninguna supera.
   La mejor (`fuerza_4h`) da +0,117 R fuera de muestra con t = 0,77. El listón ya está en **t ≥ 4,2**.
3. **Lo ganado en simulado (+29 $, +12,6 %) se explica por el mercado bajista**: los cortos ganan (+0,37 R de media) y
   los largos pierden (−0,78 R, 7 % de aciertos). Lo dice también el analista IA (no es mejor que «todo corto»).
4. **Contradicción importante**: `CLAUDE.md` dice riesgo 2 % / abierto 4 % / exploración 0,25 % ×2, pero `config.json`
   (modificado el 13/11 14:14) tiene **3 % / 9 % / 0,5 % ×4**, 6 posiciones y pérdida máxima total del 50 %.
5. **El simulado no se parece al real previsto**: el piloto real usa 0,5 % de riesgo y 1 posición; el simulado, 3 % y 6.
   Las cifras del simulado no anticipan lo que haría el real.
6. **Tres caminos de «exploración» a la vez** (cerebro en exploración, exploración amplia y memoria) mezclan la evidencia.
   El cerebro en exploración abre `momentum_4h` aunque el laboratorio le da t = −3,2, algo que la exploración amplia prohíbe.
7. **Funcionalidades caras sin efecto en decisiones**: el seguimiento de ballenas (websocket de 15 cuentas), el aprendizaje
   por vecinos (memoria) y las estrategias de 1 h siguen corriendo pero no deciden nada.
8. **Fallos de red frecuentes** desde casa (≈ 700 avisos de conexión en el log): la VPS es una mejora real, no cosmética.
9. **Mejoras con más potencial**: ventajas estructurales (carry, diferencial de funding entre mercados, comisiones más bajas,
   tendencia diaria con objetivo de volatilidad) en vez de seguir buscando patrones de velas de 1 h / 4 h.
10. Prioridad recomendada: **(a)** decidir la configuración de riesgo y alinear docs, **(b)** simplificar la exploración,
    **(c)** VPS, **(d)** investigar tendencia diaria + carry/diferenciales, **(e)** recortar lo que no aporta.

---

## 1. Estado actual medido

| Dato | Valor |
|---|---|
| Modo | SIMULADO (mainnet, precios reales) |
| Saldo simulado | 261,25 $ (inicial 232 $) → **+29,25 $ (+12,6 %)** en ~4 semanas |
| Operaciones cerradas (simulado) | 32 desde el 23/10 (31 con R conocido) |
| R medio total | **−0,186 R** (t = −0,97), 32 % de ganadoras, pero +19,15 $ netos en el ledger |
| Por lado | Cortos: n=16, +0,374 R, 56 % ganan, +31,33 $ · Largos: n=15, **−0,783 R**, 7 % ganan, −12,18 $ |
| Por estrategia | `momentum_4h` 4 ops +1,35 R (+26,75 $) · `ruptura_4h` 10 ops +0,28 R · `ruptura_1h` 8 ops −0,79 R · `retroceso_4h` 3 ops −1,02 R · `fuerza_1h` 4 ops −1,07 R |
| Laboratorio (15/11) | 13 estrategias, **todas «no supera»**. Mejor: `fuerza_4h` +0,117 R (t 0,77; holdout +0,297 R n=53) |
| Investigación | 840 ideas al cementerio, 1 098 variantes, listón t ≥ 4,2 |
| Cerebro | Modelo 4 h «no_supera», decide en modo exploración en simulado |
| Régimen BTC | Bajista (bajo la media de 200 velas de 4 h) → solo cortos |
| Carry | En marcha desde hoy; ninguna moneda llega al 20 %/año (BTC 8,9 %, HYPE 10,2 %, ZEC 10,6 %) |
| Pruebas | 693, todas OK |

**Lectura honesta**: con 31 operaciones nada es concluyente. La diferencia de R medio negativo y $ positivos viene de
que las ganadoras de `momentum_4h` se abrieron con más riesgo (≈ 6,6 $) que las perdedoras de 1 h (≈ 1 $). La mitad del
beneficio sale de 4 operaciones cortas de `momentum_4h` en una caída, y esa estrategia tiene t = −3,2 en el laboratorio.

---

## 2. Errores en el código

No he encontrado errores graves que hoy produzcan resultados incorrectos. Lo que hay:

### 2.1 Corregidos o históricos (para que conste)
- **Groq 413/400** (13–19/11): el analista no tenía IA. **Arreglado hoy** (recorte por presupuesto de tokens,
  `reasoning_effort: low`, reintento ante 429).
- **Doble entrada en kPEPE el 23/10**: `ruptura_4h` y `ruptura_1h` abrieron la misma moneda con 11 s de diferencia;
  terminó en −1,66 R (peor que el stop) y generó **230 errores** «CLOID desconocido» ese día. Ya existe la comprobación
  «ya hay una posición en esa moneda (este ciclo)» y las de 1 h están apagadas. No se ha repetido.

### 2.2 Menores (vale la pena arreglar)
| # | Dónde | Qué pasa | Efecto |
|---|---|---|---|
| E1 | ledger, campo `funding` de cada operación | Todos los pagos horarios llevan la **misma marca de tiempo** (la del cierre; p. ej. 164 entradas con `2026-11-19T00:04:20`) | Imposible ver cuándo se cobró/pagó cada hora; análisis de funding por hora engañoso |
| E2 | `papel.py` (stops) | Si el libro no cubre el stop dentro del 10 %, el resto de la orden se **cancela** y la posición queda sin stop hasta que el gestor lo repone en la siguiente conciliación | Riesgo breve sin protección en monedas poco líquidas (en real HL se comporta parecido; vigilar) |
| E3 | `papel.py` (entradas límite) | Una orden ALO se llena **entera** en cuanto el precio la atraviesa, sin cola ni llenado parcial | Ligeramente optimista; los deslizamientos de entrada salen **favorables** (−0,1 % a −0,4 %) en casi todas |
| E4 | `cerebro_vivo.py:20` `import os`, `investigacion.py:25` `import bisect` | Imports sin usar | Ninguno |
| E5 | `bot.log` | Mezcla 230 errores de un solo día con el resto; no rota | Ruido al buscar errores reales (787 KB, crece) |

---

## 3. Contradicciones y ambigüedades

| # | Contradicción | Detalle | Qué decidir |
|---|---|---|---|
| C1 | **Riesgo en docs ≠ config** | `CLAUDE.md`: 2 % por operación, 4 % abierto, exploración 0,25 % ×2. `config.json` (13/11): **3 %**, **9 %**, exploración **0,5 % ×4**, 6 posiciones, pérdida total máx. **50 %** | ¿Cuál es la configuración buena? Si es la de 3 %, actualizar `CLAUDE.md`; si no, volver a la anterior |
| C2 | **Simulado ≠ piloto real** | Piloto real: 0,5 % riesgo, 1,5 % abierto, 1 posición, BTC/ETH. Simulado: 3 %, 9 %, 6 posiciones, 34 monedas | El simulado no sirve para predecir el real. Propuesta: un segundo simulado «espejo del piloto» |
| C3 | **Dos varas de medir la exploración** | La exploración amplia excluye estrategias con t ≤ −2 en el laboratorio; el cerebro en exploración no. `momentum_4h` (t = −3,2) se ha operado con riesgo completo | Aplicar el mismo filtro a la exploración del cerebro, o documentar por qué no |
| C4 | **Tres mecanismos que deciden en simulado** | Cerebro (exploración), exploración amplia y memoria por vecinos (si el cerebro no decide) | La evidencia queda mezclada; el probador lo separa, pero cuesta interpretarlo |
| C5 | **`CLAUDE.md` desactualizado** | «Estado actual (27/10)», «hoy son 304 pruebas» (son 693), «código congelado hasta el 18/11» (ya pasó), pendiente 3 ya hecho | Refrescar la sección de estado |
| C6 | **`piloto_real.capital_max_usd`** | Config: 232 $; defecto en `configuracion.py`: 50 $ | Confirmar cuál quieres para el primer real |
| C7 | **Reglas que reducen tras ganar** | `objetivo_diario_pct: 3` → el tamaño se reduce a la mitad tras ganar un 3 % en el día | Sin evidencia de que ayude; es una regla «psicológica». Mantener solo si es deliberado |
| C8 | **«Relajar» tras 24 h sin operar** | `horas_sin_operar_para_relajar: 24` relaja filtros por inactividad | Es un sesgo de sobreoperar. Hoy solo afecta a la memoria (no decide), pero conviene quitarlo |
| C9 | **Dos módulos de funding** | `cartera_funding` (factor largo/corto por funding, activo en simulado) y el nuevo **carry** (dos patas) | Nombres parecidos, objetivos distintos; dejarlo claro en el panel o retirar uno |
| C10 | **Nombre del bot** | Se llama «de ballenas», pero las ballenas no deciden nada (`modo_senal: investigacion`, `usar_como_veto: false`; laboratorio `ballenas_1h` −0,12 R) | Decidir si se sigue invirtiendo en esa línea |

---

## 4. Funcionalidades sin uso (o sin efecto en decisiones)

| Funcionalidad | Estado real | Coste | Recomendación |
|---|---|---|---|
| **Seguimiento de ballenas** (websocket 15 cuentas, selección cada 12 h) | Solo observa; ni señal ni veto | Conexiones, llamadas API, complejidad (`ballenas.py`, `seleccion.py`, panel) | Apagar el websocket o dejarlo solo en investigación semanal |
| **Memoria por vecinos** (`aprendizaje`: `r_minimo_para_entrar`, `factor_exploracion`, `relajado`…) | Con el cerebro decidiendo, solo **mide** | 10+ parámetros en la config que no hacen nada | Dejar solo la parte de medición/probador y quitar los parámetros muertos |
| **Estrategias de 1 h** | Todas apagadas, pero `motor.intervalos` sigue incluyendo `1h` | Velas y cálculo cada hora | Quitar `1h` de `motor.intervalos` mientras no haya cerebro de 1 h |
| **Liquidaciones (`liquidaciones_1h`)** | Hipótesis; +0,09 R, t 0,88, sin holdout | Poco | Mantener como investigación |
| **Código sin referencias** | `estrategia.redondear_tamano`, `SimSalida.cerrar_ya`, `validacion.en_tramo`, `validacion.estres_costes`, `Memoria.registrar_cerrado`, `CuentaPapel.market_close`, `InfoConPapel.open_orders`, constantes `PESO_TIPO`, `POR_RUTA`, `ESTADOS_OPERACION`, `NO_EJECUTADO`, `ESTADOS_CANCELADA`, `FASES` | Ninguno | Borrar o usar (`estres_costes` parece útil para el laboratorio) |
| **Carpeta `copias/antes_auditoria_20261028`** | Copia antigua del código | Confunde búsquedas | Mover fuera del proyecto (o a las copias de R2) |

---

## 5. Puntos de mejora

Ordenados por **impacto esperado / esfuerzo**, con lo que dice la evidencia (internet y laboratorio).

### 5.1 Bases (antes de buscar más rentabilidad)
1. **Decidir la configuración de riesgo (C1) y alinear `CLAUDE.md`**. 3 % de riesgo con 6 posiciones y 50 % de pérdida
   máxima es agresivo para un sistema **sin ventaja demostrada**. Con un R medio de −0,19, un 3 % por operación
   lleva a rachas de −20 % o −30 % con facilidad.
2. **Simulado espejo del piloto real (C2)**: una segunda cuenta simulada con exactamente la config del piloto
   (0,5 %, 1 posición, BTC/ETH). Es lo único que dice algo sobre el futuro real.
3. **Una sola exploración (C3/C4)**: la del cerebro con el mismo filtro de t del laboratorio; la memoria solo mide.
4. **VPS (pendiente 2)**: en el log hay ~500 fallos al pedir velas, 144 al leer la cuenta y 39 al leer el universo,
   todos por conexión. En real, un fallo al leer la cuenta en mal momento es un riesgo.
5. **Telegram (pendiente 1)**: sin él, las alarmas solo se ven en el panel.

### 5.2 Rentabilidad: dónde puede haber ventaja de verdad
El laboratorio es muy claro: **los patrones técnicos de 1 h y 4 h no tienen ventaja con estos costes**. Seguir
generando ideas al azar sube el listón (t ≥ 4,2) y hace casi imposible aprobar nada. Lo prometedor es **estructural**:

| Idea | Por qué puede funcionar | Evidencia | Encaje con las reglas | Esfuerzo |
|---|---|---|---|---|
| **A. Carry perp–contado en Hyperliquid** (ya en marcha) | Cobra el funding sin apostar dirección | Lab: ~12 %/año en pruebas, ~7 % en holdout | Total (solo HL, simulado) | Hecho |
| **B. Tendencia diaria/semanal con objetivo de volatilidad** (BTC/ETH y 10–20 líquidas, horizonte 20–120 días, salida por cruce, tamaño por volatilidad) | El efecto «time-series momentum» está documentado en muchos activos; en cripto hay estudios 2024–2026 que lo encuentran, sobre todo en largo/plano | Literatura (ver fuentes); **nuestro lab** solo probó momentum a 10 días en 4 h | Total | Medio: 1–2 semanas, nuevo módulo y lab diario |
| **C. Diferencial de funding entre mercados** (p. ej. HL vs Binance: corto donde se paga más, largo donde menos) | Según un informe de BitMEX, el BTC de HL pagó de media un 7,17 %/año más que Binance (2023–2026) | Informe de exchange, no académico | **No**: las reglas prohíben operar en Binance/Bybit. Requiere que **Roberto cambie la regla** | Alto |
| **D. Bajar costes de verdad** | Cada 0,01 % cuenta con objetivos de 1–2 R | Tarifas de HL: 0,045 % taker / 0,015 % maker; descuento por HYPE en *staking* del 5 % (>10) al 40 %; reembolsos maker por volumen | Total | Bajo (salidas maker en objetivos, descuentos) |
| **E. Comparar contra el HLP** (bóveda de liquidez de HL) | Es la «alternativa pasiva» dentro de la misma plataforma | Fuentes no oficiales: 17–22 %/año histórico, con episodios de pérdida (JELLYJELLY, marzo 2025) | Solo como **referencia** en el panel (depositar es una acción de cuenta: no) | Bajo |
| **F. Cascadas de liquidación** | Reversión tras limpiezas forzadas | Lab: +0,09 R, t 0,88 (sin holdout) | Total | Ya en investigación |
| **G. Funding a plazo fijo (Pendle Boros)** | Fija el funding y quita la incertidumbre del carry | Documentación de Pendle | **No** (otra plataforma) | Alto |

**Recomendación**: **A + B + D**. B es la apuesta nueva con mejor relación evidencia/esfuerzo: pocas operaciones
(costes bajos), horizonte donde la literatura sí encuentra efecto, y se puede validar con el laboratorio actual
añadiendo velas diarias. Prerregistrarla antes de mirar datos (como `fuerza_4h` y `carry_realista`).

### 5.3 Metodología del laboratorio
1. **Parar la generación aleatoria de ideas** (ya en pausa): cada idea sube el listón para todas.
2. **Sharpe deflactado** (Bailey y López de Prado) como métrica oficial junto a la t corregida: mide lo mismo y es estándar.
3. **Prueba secuencial (SPRT) para lo que corre en vivo**: decide antes de 30 operaciones si algo es claramente malo,
   sin inflar falsos positivos.
4. **Separar «por qué gana»**: el analista ya compara con «todo corto». Añadir esa comparación al laboratorio
   (beta frente a BTC) evitaría aprobar estrategias que solo replican el mercado.

### 5.4 Ejecución y simulación
1. **Salidas maker** en los objetivos (TP con ALO) en vez de IOC: ahorro de 0,03 % por salida.
2. **Llenado parcial y cola** en `papel.py` (E3): hará el simulado algo más pesimista y más creíble.
3. **Calibrar con real** (pendiente 5): sigue siendo lo único que valida el simulador.

### 5.5 Plataforma
- **Seguir en Hyperliquid**: comisiones bajas, API completa, contado para el carry y transparencia (posiciones públicas).
- **Lighter** anuncia 0 % de comisión en cuentas estándar a cambio de ~200–300 ms más de latencia. Para estrategias
  de 4 h o diarias esa latencia no importa y ahorraría ~0,06–0,09 % por operación. **Pero** las reglas solo permiten HL;
  sería un cambio de plataforma que solo tú puedes decidir. Fuentes no oficiales: verificar antes.

### 5.6 Nuevas funcionalidades que aportan valor
1. **Curva de capital frente a referencias** en el panel (BTC, «todo corto», HLP): saber si el bot aporta algo.
2. **Informe semanal automático** por Telegram con lo que el laboratorio y el probador dicen (sin cifras inventadas).
3. **Simulado espejo del piloto** (5.1.2) con su propia tarjeta en la portada.
4. **Interruptor de régimen visible** (ya existe el filtro de BTC): mostrar cuánto se ha dejado de operar por él.

---

## 6. Plan propuesto (por orden)

| # | Qué | Quién decide | Esfuerzo |
|---|---|---|---|
| 1 | Elegir la config de riesgo (C1) y actualizar `CLAUDE.md` (C5) | **Roberto** | 10 min |
| 2 | Filtro de t del lab también para la exploración del cerebro (C3) | Roberto aprueba; cambia la huella | 1 h |
| 3 | Quitar `1h` del motor, parámetros muertos de la memoria y código sin uso (§4) | Roberto aprueba | 2–3 h |
| 4 | Arreglos E1 (marcas de tiempo del funding) y E4 | — | 1 h |
| 5 | VPS + Telegram | Roberto (crear máquina y claves) | 1 tarde |
| 6 | **Tendencia diaria con objetivo de volatilidad**: prerregistro + lab + simulado | Roberto aprueba el prerregistro | 1–2 semanas |
| 7 | Simulado espejo del piloto real | — | 1 día |
| 8 | Salidas maker y llenado parcial en el simulador | Cambia la huella | 1–2 días |
| 9 | (Opcional) Decidir sobre ballenas, Binance (diferencial de funding) y Lighter | **Roberto** | — |

Nada de esto activa el modo real. Pasar a real sigue exigiendo `promocion.py` y tu aprobación expresa.

---

## Fuentes de internet

- Comisiones de Hyperliquid: [documentación oficial](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees), [Dwellir](https://www.dwellir.com/blog/hyperliquid-fees-explained), [Datawallet](https://www.datawallet.com/crypto/hyperliquid-fees-explained), [CoinPerps: HL vs Binance](https://www.coinperps.com/learn/hyperliquid-vs-binance-fees)
- Diferencial de funding HL–Binance: [BitMEX, informe Q3 2025](https://www.bitmex.com/blog/2025q3-derivatives-report), [resumen MEXC](https://www.mexc.com/news/1204852), [OneKey: guía arbitraje](https://onekey.so/blog/ecosystem/hyperliquid-binance-funding-arbitrage-20260429/), [Pendle Boros](https://docs.pendle.finance/boros-academy/advanced-strategies/fixed-return-funding-arbitrage)
- Tendencia/momentum en cripto: [Zarattini, Pagani y Barbon, «Catching Crypto Trends»](https://abarbon.com/papers/catching-crypto-trends), [Nguyen 2026 (arXiv, preprint)](https://arxiv.org/html/2602.11708v1), [CXO Advisory](https://www.cxoadvisory.com/?p=46798), [Grayscale](https://research.grayscale.com/reports/the-trend-is-your-friend-managing-bitcoins-volatility-with-momentum-signals), [Coinbase 2022 (evidencia en contra)](https://www.coinbase.com/institutional/research-insights/research/monthly-outlook/trend-following-in-uncertain-times-september-2022), [estudio TS vs transversal](https://www.journals.vu.lt/BATP/lt/article/download/44540/42590/138419)
- HLP: [CoinGecko](https://www.coingecko.com/learn/hyperliquid-hlp-vault-analysis), [DL News, incidente](https://www.dlnews.com/articles/defi/hyperliquid-denies-hack-after-investors-suffer-hlp-loss/?hl=en-GB), [Chaos Labs](https://chaoslabs.xyz/posts/yield-as-a-risk-signal-part-ii), [tradingstrategy.ai](https://tradingstrategy.ai/vaults/hyperliquidity-provider-hlp)
- Lighter: [Datawallet](https://www.datawallet.com/crypto/lighter-explained), [comparativa HL vs Lighter](https://hyperliquidguide.pages.dev/compare/hyperliquid-vs-lighter), [DeFiLlama](https://defillama.com/rwa/perps/venue/lighter)

Aviso: muchas fuentes de internet son guías de terceros o *preprints*; las cifras de rentabilidad de internet son
retrospectivas y ninguna garantiza resultados. Las cifras propias del bot salen de 31 operaciones: no son concluyentes.
