# Plan: carry de funding con dos patas (en simulado)

Objetivo: cobrar el funding de los perpetuos de Hyperliquid sin quedar expuesto al precio, con un **corto en el
perpetuo** y una **compra de la misma cantidad al contado** (spot). Solo se gana si el funding cobrado supera las
comisiones de las cuatro operaciones (abrir y cerrar cada pata) y lo que se pierda porque los dos precios se separen.

Todo en **SIMULADO**. Se aplican al 100 % las reglas de seguridad de `CLAUDE.md`: nada de órdenes reales,
transferencias, subcuentas ni secretos. Pasar a real seguiría exigiendo `promocion.py` y la aprobación de Roberto.

## Respeta la prueba de dos semanas (hasta el 18/11/2026)

El código de `promocion.ARCHIVOS_CODIGO` y la config que entra en la huella están **congelados** salvo fallos claros.
Por eso:

- Las **fases 0–2** se hacen en **archivos nuevos** (`carry.py`, `papel_spot.py`, pruebas) **sin conectarlos** al bucle
  del bot y con `carry.activa: false`. No cambian ninguna decisión y no tocan la evidencia de la prueba.
  Clasifica los archivos nuevos en `promocion` según la convención (hay una prueba que lo exige); si eso altera
  la huella, déjalo preparado y aplícalo después del 18/11.
- La **fase 3** (conectarlo al bot) empieza **después del 18/11** y solo si Roberto lo aprueba a la vista del
  veredicto de la prueba.

## Lo que ya existe y hay que reutilizar

- `laboratorio.carry_realista(...)`: el estudio que da ~12 %/año en pruebas y ~7 % en holdout. Solo funding
  positivo, 4 comisiones, riesgo de base (perpetuo HL frente a spot de Binance), rentabilidad sobre el capital
  de las dos patas. Hoy supone que hay spot en Hyperliquid para `SPOT_EN_HYPERLIQUID = ("BTC","ETH","SOL","HYPE")`:
  **es una suposición, hay que verificarla** (fase 0).
- `historia_externa.BinanceSpot`: velas spot para el estudio. `contexto_externo`: funding y base en vivo.
- `papel.py` (perpetuos simulados), `gestor.py` (protección/conciliación), `ledger.py` (registro contable).

## Fase 0 — Verificar el terreno (solo lectura, ~1 sesión)

1. Con la Info API pública (`spotMeta`, `spotMetaAndAssetCtxs`): qué monedas tienen **spot en Hyperliquid**, su nombre
   interno (p. ej. `UBTC`, `UETH`, índices `@N`), decimales, tamaño mínimo, comisiones spot y **liquidez** (libro).
   Guardarlo en `datos_mercado/spot_hl.json` y sustituir la lista fija `SPOT_EN_HYPERLIQUID` por esa lista verificada.
2. Comprobar si el precio de esos spots sigue de cerca al perpetuo (la base). Si un spot es poco líquido o se
   separa mucho, se excluye.
3. Repetir `carry_realista` **solo con esas monedas y con el spot de Hyperliquid** (no el de Binance) donde haya
   historia. Si con datos de Hyperliquid deja de salir positivo, se para aquí y se informa.

## Fase 1 — Lógica pura del carry: `carry.py` (sin órdenes)

- `oportunidades(funding_por_moneda, base, liquidez, cfg)`: monedas donde el funding esperado (media reciente
  ponderada, no el último valor) cubre con margen las 4 comisiones en el plazo de tenencia previsto.
- `tamano(capital, cfg)`: capital por posición de carry (las dos patas), con límites propios: % máximo de la cuenta
  en carry, máximo de posiciones, máximo por moneda.
- Reglas de salida: funding medio por debajo del umbral durante N horas, base que se abre más de X %, tiempo máximo,
  o deterioro de liquidez. **Sin stop de precio**: la cobertura es la otra pata.
- Riesgo de margen: el corto de perpetuo puede acercarse a liquidación si el precio sube mucho, aunque la pata spot
  gane lo mismo (están en cuentas separadas). Calcular la distancia a liquidación y cerrar o reducir antes.
- Todo con pruebas unitarias (`tests/test_carry.py`), con datos sintéticos y casos límite.

## Fase 2 — Simulación de las dos patas: `papel_spot.py`

- Cuenta spot simulada (saldo USDC + monedas), órdenes con libro spot real, comisiones spot, sin apalancamiento.
- Reparto del capital simulado entre la cuenta de perpetuos (`papel.json`) y la spot (`papel_spot.json`), como un
  «traspaso interno» **solo simulado** (en real, mover fondos entre spot y perpetuos es una acción de cuenta que
  queda fuera de este plan).
- **Atomicidad**: abrir la pata spot y la de perpetuo casi a la vez; si una falla o se llena a medias, deshacer o
  igualar la otra al momento. Si queda desequilibrio, congelar el carry de esa moneda y avisar (igual que
  `gestor` con las entradas inciertas).
- Ledger: eventos `carry_apertura`, `carry_funding`, `carry_cierre`, con el resultado separado en funding cobrado,
  comisiones, deslizamiento y base.
- Pruebas: apertura completa, fallo de una pata, llenado parcial, cierre, funding negativo, base que se dispara,
  reinicio del bot a mitad (todo con fixtures, nunca contra la API de órdenes).

## Fase 3 — Integración en el bot (después del 18/11 y con aprobación)

- `bot.py`: ciclo de carry separado de las estrategias (revisión horaria, que es cuando se paga el funding),
  con su propio presupuesto de capital que no compite con el cerebro.
- `config.json`: bloque `carry` (`activa`, `capital_max_pct`, `max_posiciones`, `funding_min_anual_pct`,
  `base_max_pct`, `horas_min`, `horas_max`).
- Panel: tarjeta «Carry de funding» en lenguaje claro: qué monedas, cuánto capital, funding cobrado, comisiones,
  resultado neto y «no apuesta a que suba o baje el precio».
- Promoción: nueva estrategia `carry` con sus propias etapas; mismos requisitos (evidencia en vivo + aprobación humana).

## Fase 4 — Evidencia y decisión

- Mínimo 4–6 semanas en simulado (el funding cambia por regímenes de mercado).
- Comparar lo simulado en vivo con lo que predijo el laboratorio para esas mismas semanas.
- Solo si el neto es positivo y estable, proponer a Roberto un piloto real con poco capital, con todos los pasos
  de `promocion.py`. Nada de esto se activa solo.

## Riesgos a vigilar (no desaparecen)

- El funding puede cambiar de signo de un día para otro.
- Las 4 comisiones se comen el beneficio si se entra y sale demasiado.
- Spot poco líquido en Hyperliquid: deslizamiento y base mayores que en Binance.
- Liquidación del corto de perpetuo en una subida fuerte (la pata spot no lo evita, está en otra cuenta).
- Riesgo de la plataforma: todo el capital en un mismo exchange.
