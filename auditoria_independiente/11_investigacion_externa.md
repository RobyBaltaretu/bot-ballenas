# 11 — Investigación externa

Fecha de consulta de todas las fuentes: **24/11/2026** (búsqueda web desde el entorno de la auditoría). Se distingue:
**[O]** documentación oficial · **[A]** académica (revisada por pares o working paper institucional) · **[P]** preprint
· **[S]** secundaria / prensa · **[C]** comercial. No se citan fuentes que no se hayan consultado.

## 1. Hyperliquid (documentación oficial)

| Tema | Fuente | Evidencia | Aplicación al bot | Confianza |
|---|---|---|---|---|
| Límites de peticiones | [O] [Rate limits and user limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits) | 1 200 de peso/min por IP; por dirección 1 petición por 1 USDC negociado + 10 000 iniciales; limitado: 1 cada 10 s; lotes cuentan n por dirección | Vigilar `userRateLimit` en real (hoy no se hace) | Alta |
| Comisiones | [O] [Fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees) | Perp 0,045 % / 0,015 %; contado 0,070 % / 0,040 % en nivel 0; niveles por volumen de 14 días | Coinciden con `config.comisiones` y `carry/logica.py` | Alta |
| TP/SL | [O] [Take profit and stop loss orders](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/take-profit-and-stop-loss-orders-tp-sl); [O] [Order types](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/order-types) | Disparo por precio de marca; TP/SL de mercado con 10 % de tolerancia | Coincide con `gestor.poner_stop` y `papel.TOLERANCIA_MERCADO` | Alta |
| Funding | [O] [Funding](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding) | Tasa de 8 h pagada cada hora a 1/8; interés 0,01 %/8 h; tope 4 %/h | Coincide con `riesgo.funding_adverso_frac` (0,00125 %/h); el tope de 4 %/h justifica una salida por funding extremo | Alta |
| Precio de marca | [O] [Robust price indices](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/robust-price-indices) | Mediana de oráculo + EMA, mediana del libro y perps externos | La marca es más suave que las operaciones: el simulador debe usarla para stops (lo hace) | Media-alta (texto truncado en la búsqueda) |
| SDK | [O] PyPI `hyperliquid-python-sdk` | Última versión 0.24.0 (04/06/2026) | El bot está al día | Alta |

## 2. Investigación académica

| Tema | Fuente | Evidencia | Limitaciones | Aplicabilidad | Experimento necesario |
|---|---|---|---|---|---|
| Momentum de serie temporal en cripto | [A] Liu, Tsyvinski, «Risks and Returns of Cryptocurrency», *Review of Financial Studies* 34(6), 2021 ([NBER w24877](https://nber.org/papers/w24877)) | Momentum de serie temporal significativo a frecuencia diaria/semanal en BTC, ETH, XRP | Muestra hasta ~2018; pocas monedas | Base teórica de `ruptura`/`momentum`; mi backtest muestra que el efecto se debilita desde 2023 | Replicar con datos de 2023–2026 en Hyperliquid |
| Factores comunes | [A] Liu, Tsyvinski, Wu, «Common Risk Factors in Cryptocurrency», *Journal of Finance* 77(2), 2022 ([RePEc](https://econpapers.repec.org/RePEc:bla:jfinan:v:77:y:2022:i:2:p:1133-1177)) | Mercado, tamaño y momentum explican el corte transversal | Carteras amplias de quintiles; costes no de minorista | `fuerza` es una versión degradada (1–2 monedas) | Cartera largo-corto semanal con 20–40 monedas |
| Carry de cripto | [A] Schmeling, Schrimpf, Todorov, «Crypto carry», BIS WP 1087 (2023, rev. 2025) ([BIS](https://www.bis.org/publ/work1087.htm)) | Carry a veces > 40 %/año, muy variable; carry alto predice caídas | Mide futuros/perp en CEX | Fundamento del carry de `carry/`; sugiere reducir exposición direccional larga cuando el carry es extremo | Validar con funding horario de Hyperliquid |
| Funding de perpetuos | [P] He, Manela, Ross, von Wachter, «Fundamentals of Perpetual Futures» ([arXiv 2212.06888](https://arxiv.org/abs/2212.06888)) | El funding ≈ diferencia media futuro-contado | Preprint | Coherente con el diseño del carry | — |
| Pruebas múltiples | [A] Harvey, Liu, «Backtesting» ([Duke](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)); [A] Bailey, López de Prado, «The Deflated Sharpe Ratio» ([SSRN 2460551](https://papers.ssrn.com/abstract=2460551)); [A] Bailey et al., «Probability of Backtest Overfitting» ([eScholarship](https://escholarship.org/content/qt4w1110bb/qt4w1110bb.pdf)) | Un t de 3 deja de ser significativo con muchas pruebas; DSR y PBO corrigen selección | — | Apoya el listón alto; el cambio a 27 familias necesita justificación cuantitativa (correlación entre variantes) | Implementar DSR y PBO (CSCV) en `validacion.py` |
| Tendencia en cripto | [P] Rozario et al., «A Decade of Evidence of Trend Following Investing in Cryptocurrencies» ([arXiv 2009.12155](https://arxiv.org/abs/2009.12155)); [P] Mroziewicz, Ślepaczuk ([arXiv 2602.10785](https://arxiv.org/abs/2602.10785), 2026, doble fuera de muestra) | Tendencia con medias móviles; en el estudio de doble OOS rinde como comprar y mantener con menor caída | Preprints; evidencia mixta | La referencia «BTC > EMA200» debe ser obligatoria | Ya medida en 09 |
| Microestructura | [P] Estudios de order book en Binance Futures (arXiv 2506.05764; 2602.00776); [C] informe práctico «Crypto Orderflow Alpha» (Substack, 02/2026) | El desequilibrio de órdenes predice a segundos; pierde ~la mitad del valor en 5 s (informe no revisado) | Infraestructura de baja latencia | **No aplicable** al bot | — |
| Copy trading | [P] Preprint 2025 sobre selección de líderes ([arXiv 2507.01817](https://arxiv.org/abs/2507.01817)); [A] CHI 2024 sobre copy trading de cripto ([Kawai et al.](https://www.andrew.cmu.edu/user/nicolasc/publications/Kawai-CHI24.pdf)) | Los seguidores eligen por popularidad, mal correlacionada con rendimiento; incentivos de los líderes a parecer rentables | No hay estudio de persistencia de ballenas en Hyperliquid | Coherente con la ausencia de señal medida | Estudio de persistencia con histórico propio |

## 3. Casos públicos y prensa

| Caso | Fuente | Lectura |
|---|---|---|
| Grandes cuentas de Hyperliquid liquidadas tras rachas ganadoras (James Wynn, ~100 M$, mayo 2025; 0xa523, −40 M$ en un mes) | [S] [The Block](https://www.theblock.co/news/ecosystems/2025-05-30-hyperliquid-trader-james-wynn-hit-with-over-100-million-loss-as-leveraged-bitcoin-trade-unravels), [S] [Cointelegraph](https://cointelegraph.com/news/whale-ousts-james-wynn-as-hyperliquid-s-biggest-loser-after-40m-blowup) | El ranking por PnL reciente rota y premia el apalancamiento: argumento contra `seleccion.py` |
| Alpha Arena (Nof1): 6 LLM operando perps en Hyperliquid con 10 000 $ | [S] [Decrypt](https://decrypt.co/345006/ai-crypto-trading-showdown-deepseek-grok-winning-gemini-implodes), [S] [SCMP](https://www.scmp.com/tech/tech-trends/article/3329784/deepseek-outperforms-ai-rivals-real-money-real-market-crypto-showdown), [S] [Forklog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/amp) | 4 de 6 en pérdidas; costes por sobre-operar. No es un experimento controlado |

## 4. Proyectos de código abierto

| Proyecto | Fuente | Relación con Hyperliquid | Aprovechable | Limitaciones |
|---|---|---|---|---|
| Hummingbot | [O] [hummingbot.org/exchanges/hyperliquid](https://hummingbot.org/exchanges/hyperliquid) | Conector oficial de perpetuos (testnet incluido) | Referencia de cómo manejar órdenes y reconexiones | Orientado a market making; no aporta estrategia |
| NautilusTrader | [O] [nautilustrader.io/docs/latest/integrations/hyperliquid](https://nautilustrader.io/docs/latest/integrations/hyperliquid/) | Adaptador oficial (Rust + Python), datos y ejecución | Motor de backtest por eventos con el **mismo código** que en vivo: resolvería T-05/T-06 | Curva de aprendizaje; migración costosa |
| Freqtrade | [S] guías de terceros: vía CCXT | Sin verificar en la documentación oficial | Hyperopt/FreqAI como referencia de validación | No verificado aquí |
| vectorbt, LEAN, FreqAI, CCXT, rastreadores de ballenas | — | **No investigados en esta sesión** | — | Pendiente (AUDIT_PROGRESS) |

## 5. Conclusiones
1. Las integraciones con Hyperliquid son **coherentes con la documentación oficial**; falta solo vigilar el límite por
   dirección y probar en testnet.
2. La literatura respalda **carry** y **momentum/tendencia** en cripto como fuentes plausibles de prima; no respalda
   copiar ballenas ni usar un LLM como decisor. El bot ya tiene las piezas para las dos primeras; las dos últimas sobran.
3. Microestructura y scalping requieren una infraestructura que el proyecto no tiene ni necesita.
4. El rigor estadístico del laboratorio está alineado con la literatura de sobreajuste; faltan DSR y PBO.
