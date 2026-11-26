# Auditoría de la cuenta agresiva (25/11/2026)

Pedida por Roberto: revisar con fuentes externas (documentación, estudios, repositorios) cómo mejorar la cuenta agresiva y
buscar fallos en el código que ya tenemos. **No se ha cambiado nada**: ni el código, ni la cuenta en marcha, ni el bot.
Todas las mediciones son con la misma historia que la primera prueba (Binance, velas de 15 min, 120 días, 20 monedas)
y con un script aparte que no escribe en el proyecto.

## Estado: arreglado el 25/11/2026 (pedido por Roberto)

Roberto pidió arreglar todos los fallos y que la agresiva fuera agresiva de verdad:

- **Fallos del simulador.** Arreglados F1 a F7 (detalle en la tabla de abajo y en `CLAUDE.md`).
- **Riesgo de la agresiva (F8).** Arriesga un **5 % fijo** hasta el stop, con un tope de margen del 30 % por operación
  y del 90 % en total.
- **Prueba con historia (F9, F10).** Universo elegido cada día, funding de Binance y simulación de ruina por días.
- **Pruebas.** 816 en total, todas en verde (52 de la cuenta agresiva). Motor reiniciado a las 21:50 hora local.
- **Señales abiertas.** Las tres que estaban abiertas (HYPE, ZEC, NEAR) conservan su tamaño antiguo. Su liquidación y
  su funding ya siguen las reglas nuevas.

**Nueva prueba con historia**:

- Periodo: del 28/07 al 25/11/2026.
- Universo: 20 monedas cada día, 51 distintas en total.
- Operaciones: 2 330.

| | Antes de los arreglos | Después |
|---|---|---|
| R medio de la gemela | −0,15 a −0,17 | **−0,17** (1 272 operaciones) |
| Riesgo medio de la agresiva | ~1,2 % | **3,4 %** (pide 5 %; el tope de margen lo recorta en monedas de 3–10× con stops cortos) |
| Resultado de la agresiva | −516 $ | **−1 038 $** |
| Quiebras | 2 (≈ 51 y 44 días) | **4** (32, 20, 19 y 28 días) |
| Liquidaciones | 0 | 0 |
| Simulación de ruina por días | — | **100 %**, mediana de 25 días hasta quebrar |

Cómo se lee:

- **Las señales siguen sin ventaja.** Con el universo elegido sin mirar el futuro salen algo peor que antes.
- **El riesgo más alto solo acelera la quiebra.** Es lo que se esperaba (variante C5).
- **La gemela se queda sin saldo a mitad de la prueba** (4,38 $ al final). Desde ahí muchas entradas suyas no llegan a
  10 $. Gracias al arreglo de F1, la agresiva abre igual: 1 058 señales solo con la agresiva.
- **Lo que no ha cambiado:** las reglas de entrada, el stop (fijo en la entrada tras el objetivo 1, como pidió Roberto)
  y los objetivos.

## En cinco líneas (diagnóstico antes de los arreglos)

1. **Las señales no tienen ventaja.** Sin comisiones ni deslizamiento dan **+0,008 R** por operación (t 0,5): un
   empate. Todo lo que se pierde (−0,14 R por operación) son costes. Elegir la dirección al azar da −0,18 R: nuestras
   reglas son solo un poco mejores que tirar una moneda.
2. **Hay un fallo que distorsiona la prueba**: si la gemela no puede abrir, tampoco abre la agresiva. En la historia
   eso bloqueó **1 032 entradas** de la agresiva, porque la gemela se quedó sin saldo (0,20 $ al final).
3. **La «agresiva» no es agresiva.** Arriesga de mediana un **1,2 %** de la cuenta por operación, menos que la gemela
   (2 %). La mayoría de las monedas no deja pasar de 3–10×.
4. **Lo único que mueve la aguja son los costes y el plazo.** Con velas de 1 h, el filtro de BTC y entrada con orden
   límite, la historia da +0,04 R (t 1,3) y 0 quiebras. Es la mejor de 15 variantes probadas mirando el resultado, así
   que **no es una prueba**: como mucho, una pista para probar en vivo aparte.
5. Las fuentes externas dicen lo mismo:
   - en Hyperliquid, el trader minorista pierde en conjunto;
   - las señales de los canales no tienen ningún estudio serio detrás;
   - el stop solo ayuda si hay tendencia;
   - a plazos cortos los costes se comen la ventaja.

---

## 1. Fallos en el código

Ordenados por importancia. Lo «medido» viene de la historia con el código tal cual.

| # | Gravedad | Dónde | Qué pasa | Medido | Arreglo propuesto |
|---|---|---|---|---|---|
| F1 | **Alta** | `agresiva/cuenta.py:131-136` | `abrir()` calcula primero la gemela. Si la gemela no puede (saldo nulo, tamaño 0 o sin liquidez), devuelve error y la agresiva **tampoco abre**. La agresiva depende de la salud de la gemela. | 1 032 señales perdidas para la agresiva en 120 días (la gemela acabó con 0,20 $). En vivo no pasa hoy (gemela en 232 $), pero pasaría si la gemela quebrara. | Abrir cada pierna por su cuenta: si falla la gemela, abrir solo la agresiva, y al revés. Contar «solo_agresiva» igual que «solo_gemela». |
| F2 | Media | `logica.tamano_*`, `logica._cerrar_parte` | Hyperliquid rechaza órdenes de menos de **10 $** de valor. No está modelado. | 1 575 entradas de la gemela y 34 de la agresiva por debajo de 10 $. **3 554 de 7 189 cierres parciales** (20 % por objetivo) por debajo de 10 $. | No abrir por debajo de 10 $. Si un parcial no llega a 10 $, juntarlo con el siguiente o cerrar el resto. *(No he podido confirmar si una orden reduce-only que cierra la posición está exenta: hay que comprobarlo antes de dar por buena la regla.)* |
| F3 | Media | `logica._liquidar` | Al liquidarse se da por perdido **todo** el margen que queda. En Hyperliquid, una liquidación por el libro **deja al usuario el margen sobrante**. Solo el rescate (si el valor baja de 2/3 del mantenimiento) se queda el mantenimiento, que es la mitad del margen inicial al apalancamiento máximo. | 0 liquidaciones en la historia de 15 min y 2 casos con la liquidación antes que el stop. Con velas de 1 h (stops más anchos) hubo 5: allí sí cuenta. | Liquidación al precio de liquidación + comisión, devolviendo el resto. Mantener el «se pierde todo» solo si el precio salta más allá (caso de rescate). |
| F4 | Media | `logica.avanzar` y `motor._gestionar` | Stops, objetivos y liquidación se disparan con las velas de **operaciones** de 1 min. Hyperliquid dispara TP/SL y liquidaciones con el **precio de marca**: la mediana de oráculo + libro + precios de otros exchanges. Una mecha de una sola operación puede saltar un stop que en Hyperliquid no saltaría, y al revés. | Sin medir: la API pública no da velas de marca. | Guardar el `markPx` de cada pasada y usar la vela de 1 min solo como confirmación. Si no, dejarlo escrito como aproximación conocida (ya lo es en papel.py). |
| F5 | Baja | `logica.py:341` | Si una vela **abre ya por encima** del siguiente objetivo (hueco a favor), ese objetivo no se llena. Además, el stop no pasa a la entrada. Una orden límite en reposo se habría llenado a la apertura. Comprobado con un ejemplo: la vela abre en +1,6 % con objetivos en +0,75 y +1,5 %, luego cae, y la operación no cobra nada. | 0 casos en la historia de 15 min. En vivo es raro: sobre todo en el primer minuto tras la entrada. | Al abrir la vela, llenar a la apertura todos los objetivos que ya quedan atrás. |
| F6 | Baja | `logica.avanzar` | El 20 % de cada objetivo no se redondea a los decimales de la moneda (en vivo: `16.400000000000002` NEAR). El exchange no lo aceptaría así. | Cosmético en dinero. | `bajar(sz0 × reparto, sz_dec)` y el último objetivo cierra lo que quede. |
| F7 | Baja | `motor._funding` | El funding se cobra cada hora con la tasa del momento de `metaAndAssetCtxs`, no con la pagada (`fundingHistory`, como hace el carry). No resta del margen aislado, que en Hyperliquid mueve el precio de liquidación. La historia no lleva funding. | Pequeño en operaciones de horas. | Usar `fundingHistory` al pasar la hora y restarlo del margen de la pierna. |
| F8 | **Diseño** | `logica.tamano_agresiva` | Con margen fijo del 10 % y apalancamiento recortado al de cada moneda, el riesgo varía mucho entre operaciones por motivos que no tienen que ver con la señal (el tope de la moneda y la distancia al stop). | Riesgo por operación: p10 0,44 %, mediana 1,23 %, p90 1,91 %, máx. 6 %. Las tres abiertas de hoy, entre 1,8 y 2,6 %. | Si se quiere de verdad «agresiva», dimensionar por riesgo fijo y que el apalancamiento solo decida el margen. **Pero** con ventaja negativa, más riesgo = quiebra antes (ver C5). |
| F9 | Método | `historia.principal` | El universo se elige con el volumen y el apalancamiento máximo **de hoy** (HYPE, ZEC, PUMP, MON…). Hay sesgo de supervivencia: hace 120 días algunas no eran las más negociadas. | Sin medir. | Elegir el universo de cada día con el volumen en USDT de Binance de los días anteriores (ya está en la caché). |
| F10 | Método | `historia.monte_carlo` | Sortea operaciones independientes. No tiene en cuenta que suelen ir juntas (hoy HYPE, ZEC y NEAR son las tres largos de la misma regla) ni los frenos. | Subestima rachas. | Sortear días enteros en vez de operaciones sueltas. |

**Lo que está bien** (comprobado):
- **Recorrido dentro de la vela.** Solo 54 de 33 049 velas (0,16 %) tocan a la vez stop y objetivo: el supuesto
  o→l→h→c apenas cambia nada.
- **Sin lookahead.** La señal se calcula al cierre de la vela y se entra a la apertura de la siguiente.
- **Indicadores en vivo frente a historia.** En vivo se calculan con 130–200 velas y en la historia con todas. El peso
  que queda del arranque de la media de 50 es ≈ 0,5 %: despreciable.
- **Fórmula del precio de liquidación.** Es la de la documentación de Hyperliquid.
- **Aislamiento y seguridad.** Solo lectura de la API pública con lista blanca, y parada si el bot no está en
  simulado.

## 2. Qué dice la historia: la señal por separado

Para medir la señal sin que la ruina de la gemela bloquee operaciones, en estas pruebas la gemela tiene **tamaño fijo**
(2 % de 232 $). R = resultado ÷ riesgo inicial; t = media ÷ error estándar.

| Variante | Operaciones | R medio | t | Acierto | 1.ª mitad / 2.ª | Agresiva | Quiebras |
|---|---|---|---|---|---|---|---|
| Base (como en vivo) | 2 776 | **−0,139** | −8,3 | 46,6 % | −0,17 / −0,11 | −414 $ | 2 |
| Sin costes (comisión y deslizamiento 0) | 2 753 | **+0,008** | 0,5 | 66,5 % | 0,00 / +0,02 | +111 $ | 0 |
| Dirección al revés | 2 594 | −0,164 | −9,5 | 43,9 % | | −537 $ | 2 |
| Dirección al azar (3 sorteos) | ~2 750 | −0,187 / −0,181 / −0,164 | | ~44 % | | −568 a −674 $ | 2–3 |
| Un solo objetivo a 2 R | 1 803 | −0,144 | −4,3 | 32,2 % | | −371 $ | 1 |
| Un solo objetivo a 1 R | 3 372 | −0,169 | −9,5 | 46,4 % | | −714 $ | 3 |
| Entrada con orden límite (aprox.) | 2 729 | −0,080 | −4,8 | 65,3 % | | −281 $ | 1 |
| Solo a favor de BTC (media de 200 h) | 2 372 | −0,110 | −6,1 | 48,3 % | | −345 $ | 1 |
| Mismas reglas con velas de **1 h** | 1 044 | −0,063 | −2,3 | 60,0 % | −0,10 / −0,03 | −180 $ | 0 |
| 1 h sin costes | 1 045 | +0,051 | 1,9 | 68,8 % | | +150 $ | 0 |
| 1 h + filtro BTC | 910 | +0,007 | 0,2 | 62,7 % | +0,02 / −0,01 | −99 $ | 0 |
| 1 h + filtro BTC + entrada límite | 933 | **+0,038** | 1,3 | 68,8 % | +0,07 / +0,01 | +12 $ | 0 |
| Agresiva con riesgo fijo 2 % | — | (misma señal) | | | | −610 $ | 2 (40 y 29 días) |
| Agresiva con riesgo fijo 5 % | — | (misma señal) | | | | −991 $ | **4** (~22 días cada una) |

Cómo se lee:

- **Costes.** Cuestan ≈ 0,15 R por operación. Con un stop de ~1,3 %, ida y vuelta pagan 0,045 % + 0,045 % de comisión
  y ~0,1 % de deslizamiento: ≈ 0,19 % del importe, unos 0,15 R. En 15 min el movimiento que se busca es pequeño y los
  costes pesan mucho.
- **Señales.** Solo ganan unos 0,04 R a una dirección al azar: no hay ventaja que proteger con stops ni con
  apalancamiento.
- **Salidas.** Pasar de cinco objetivos a uno solo no arregla nada: a 2 R queda igual y a 1 R, peor.
- **Entrada con límite.** Reduce la pérdida a la mitad, pero la cifra es optimista: supone que la orden límite siempre
  se llena. En la realidad, las que no se llenan suelen ser justo las que se van a favor.
- **Velas de 1 h.** Es el cambio con más efecto: menos operaciones y menos costes por R.
- **Más riesgo** (C2, C5) con ventaja negativa solo acelera la quiebra.
- **Ojo con la mejor fila.** He probado 15 variantes y la mejor, elegida mirando el resultado, tiene t 1,3. Según
  Bailey y López de Prado, el máximo de muchas pruebas sale alto por azar. Esa fila es una pista, no una prueba.

## 3. Qué dicen las fuentes externas

**Hyperliquid (documentación oficial)**
- **Comisiones.** Tomadora 0,045 % y creadora 0,015 % en el nivel base. Descuento por tener HYPE en staking del 5 al
  40 %. Las rebajas para creadores exigen una cuota de volumen inalcanzable con 232 $.
  [fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
- **Disparo.** TP/SL y liquidaciones se disparan con el **precio de marca**. Los TP/SL a mercado tienen una tolerancia
  de deslizamiento del 10 %.
  [TP/SL](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/take-profit-and-stop-loss-orders-tp-sl) ·
  [marca](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/robust-price-indices)
- **Liquidación.** Si es por el libro, el usuario conserva el margen sobrante. El rescate se activa por debajo de 2/3
  del mantenimiento y entonces no se devuelve el mantenimiento. Por encima de 100 000 $ la liquidación es parcial (20 %
  cada vez, con 30 s de espera).
  [liquidaciones](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations) ·
  [margen](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margining)
- **Mínimo de 10 $ por orden.** Viene de documentación de terceros y del mensaje de error que devuelve la API.
  [Chainstack](https://docs.chainstack.com/reference/hyperliquid-exchange-place-order.md)

**Quién gana y quién pierde en Hyperliquid**
- Un estudio de AFT 2026 clasifica las carteras de Hyperliquid. Los que operan a mano desde la web (casi todos
  minoristas) pierden en conjunto unos 1 110 M$ después de comisiones. Además, son el 96 % del volumen liquidado.
  [AFT 2026](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.AFT.2026.36)

**Canales de señales**
- No he encontrado ningún estudio revisado que mida el resultado de las señales apalancadas de Telegram. Lo que circula
  son rankings de los propios vendedores, con aciertos del «95 %» sin verificar. Solo hay una tesis que propone cómo
  evaluarlos.
  [NCIRL](https://norma.ncirl.ie/8791/1/mohiburrehman.pdf)

**Plazo y costes**
- Con costes realistas, el momentum en cripto aguanta mejor a varias horas o días que en intradía.
  [Han, Kang y Ryu](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf) ·
  [AdaptiveTrend, 6 h](https://arxiv.org/abs/2602.11708)
- Dentro del día, BTC tiende a darse la vuelta a 1–4 h.
  [De Nicola](https://ledger.pitt.edu/ojs/ledger/article/view/213) ·
  [Shen y Urquhart](https://centaur.reading.ac.uk/100181)
- Hay un efecto curioso en el cambio de cada vela de 15 min.
  [turn-of-the-candle](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10015199/)
- Encaja con lo medido: 1 h sale mejor que 15 min.

**Stops y salidas**
- Kaminski y Lo: si los precios se mueven al azar, un stop **siempre** reduce el rendimiento esperado. Solo suma si hay
  tendencia (momentum). Con nuestra ventaja bruta ≈ 0, los stops solo cuestan.
  [MIT](https://dspace.mit.edu/handle/1721.1/114876)
- Repartir la salida en varios objetivos suaviza la curva, pero en sistemas de tendencia suele bajar la esperanza. La
  recomendación es medirlo con tus propias operaciones. Lo hemos medido: no mejora.
  [ejemplo](https://enlightenedstocktrading.com/trend-following-profit-targets-do-they-work) ·
  [LuxAlgo](https://www.luxalgo.com/library/concept/scaling-out/)

**Sobreajuste**
- Probabilidad de sobreajuste y Sharpe deflactado: con muchas variantes, el mejor resultado sale inflado.
  [PBO](https://papers.ssrn.com/abstract=2326253) · [DSR](https://papers.ssrn.com/abstract=2460551)

**Repositorios (leídos solo como referencia; no se ha ejecutado código suyo)**
- **freqtrade**:
  - Sus «protecciones» se parecen a nuestros frenos: StoplossGuard (pausa tras N stops en una ventana), MaxDrawdown y
    CooldownPeriod (no volver a entrar en la misma moneda nada más salir).
  - Sus análisis de lookahead y de dependencia del arranque de indicadores son las mismas comprobaciones que hemos
    hecho a mano.
  - [protecciones](https://codeclimate.com/github/freqtrade/freqtrade/docs/includes/protections.md/source) ·
    [lookahead](https://codeclimate.com/github/freqtrade/freqtrade/docs/lookahead-analysis.md/source) ·
    [recursive](https://codeclimate.com/github/freqtrade/freqtrade/docs/recursive-analysis.md/source)
- **Bots para Hyperliquid**:
  - `keitaj/hyperliquid-bot`: ruptura con ATR y volumen.
  - `hogatata/bot_hyperliquid`: stop que persigue al precio a varios ATR del máximo («chandelier exit»).
  - Ninguno publica resultados auditados: solo sirven como ideas.
  - [keitaj](https://gh.hhj520.top/keitaj/hyperliquid-bot) · [hogatata](https://gh.r-mj.com/hogatata/bot_hyperliquid)

## 4. Propuestas, por orden

Todo en SIMULADO, sin tocar el bot de ballenas ni su huella.

1. **Arreglar F1, F2, F5 y F6.** Son fallos del simulador, no cambios de reglas. Hacen que lo que se mida se parezca
   más a Hyperliquid. Sobre todo F1: sin él, la prueba con historia de la agresiva no es fiable a partir de la ruina de
   la gemela.
2. **Arreglar F3 (liquidación como en Hyperliquid).** No cambia nada a 15 min, pero sí en cuanto los stops sean más
   anchos.
3. **Rehacer la historia con universo por fecha (F9).** Con F1 arreglado, volver a medir la base. Así sabremos cuánto
   de la cifra actual se debe al fallo y al sesgo.
4. **Si se quiere seguir buscando, una «variante B» en vivo y en paralelo:** velas de 1 h + filtro de BTC + entrada
   con orden límite que solo se llena si el precio la cruza (como el MODELO 3 de `papel.py`). Criterios fijados antes de
   empezar: por ejemplo, 100 operaciones cerradas, R medio > 0 con t ≥ 2 y positivo con los costes al doble. Hasta
   entonces, nada de subir riesgo.
5. **Decidir qué significa «agresiva» (F8).** Hoy arriesga menos que la gemela. Si se quiere probar de verdad el
   apalancamiento alto, dimensionar por riesgo fijo y no por margen fijo. Pero la historia lo deja claro: con ventaja
   negativa, al 5 % de riesgo quiebra cuatro veces en 120 días (~22 días cada vez).
6. **Opcional: un freno tipo StoplossGuard** (por ejemplo, 4 stops en 6 horas → 6 horas sin entradas) y espera por
   moneda tras un stop. No crea ventaja; solo abarata las malas rachas.

**No recomiendo:**
- subir el apalancamiento o el riesgo;
- acortar objetivos (a 1 R sale peor);
- copiar las señales de los canales;
- añadir más reglas de 15 min sin antes resolver los costes.

**Pendiente a propósito:** el stop escalonado (subir el stop al objetivo anterior). Roberto pidió dejarlo como está;
no se ha probado.

## Cómo repetirlo

Los scripts están fuera del proyecto, en el scratchpad de la sesión:

- `auditoria_agr.py`: diagnóstico y variantes B/C.
- `auditoria_comb.py`: combinaciones con 1 h.

Usan la caché `datos_backtest/agresiva_15m/` y una sola lectura pública de `metaAndAssetCtxs`. Ninguno escribe en el
proyecto ni toca la cuenta en marcha.
