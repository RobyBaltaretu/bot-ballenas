# 02 — Arquitectura y funcionamiento real

Reconstruido desde el código (no desde la documentación). Referencias `archivo:línea` del commit `b8a9f8d`.

## 1. Procesos

```
INICIAR.bat → despliegue/iniciar_windows.ps1 (bucle: reinicia salvo código 0 o 3; código 4 = reinicio ordenado)
 ├─ bot.py            bucle principal, ciclo de 15 s (segundos_entre_ciclos)
 │    └─ hilos: selección de ballenas, funding histórico, websocket (SDK), latido externo, vigía de cuelgue (20 min)
 ├─ panel.py          HTTP propio en 127.0.0.1:8080 + analista_ia.py (Groq) en el mismo proceso
 ├─ carry/motor.py    carry de dos patas, cuenta ficticia propia (200 $), cada 10 min
 └─ cloudflared       túnel al panel (servicio de Windows; panel.tunel_sin_clave = true)
laboratorio_semanal.py / investigacion.py: procesos aparte lanzados por bot.agenda (domingo 04:00 / lun–sáb 02:30)
```

## 2. Flujo de un dato hasta el resultado económico

```
Hyperliquid /info (REST, SDK)  ──►  motor.contexto(): velas CERRADAS 1h/4h (300) → senales.Contexto (EMA, ATR, ER, RSI)
Binance/Bybit (público)        ──►  contexto_externo (cada 5 min) → rasgos externos del cerebro
WS trades / userFills          ──►  mercado.py (OI, flujo grande) · feed del panel (no deciden)
clearinghouseState ballenas    ──►  ballenas.FlujoBallenas.foto(): Δ de posición entre fotos (≈15 s)
                │
                ▼  al cierre de vela (+20 s), motor.nuevas_senales (1 s de pausa por moneda e intervalo)
   CANDIDATA {moneda, lado, sl_pct = k·ATR, salida, duración, rasgos}
                │
bot.procesar_candidatas (bot.py:812-1058)
  1  ledger «senal»
  2  evaluar(): stop en [0,25 %, 12 %], persecución ≤ 0,3 R, horquilla ≤ 0,15 %, costes ≤ 20 % del riesgo,
     funding en contra ≤ 0,005 %/h, vela ≤ 4 ATR, veto de ballenas (≥ 150 k$ en contra)
  3  memoria.valorar(medir=True)  (todas)
  4  cerebro.decidir(): ridge 8 rasgos → predicción R; > 0,05 R abre. Sin datos externos: se abstiene
  5  apagada/solo_investigacion → descartada (sombra)
  6  régimen BTC (cierre vs EMA200 de su intervalo): solo a favor; desconocido → no
  7  vías: cerebro | cerebro_exploracion (simulado, 4 h) | exploracion_amplia (simulado, 0,5 %) | memoria | cartera_funding
  8  memoria por vecinos: factor 0,5–1, o veto (real) / ×0,5 (simulado)
  9  real: promoción vigente + mercado en piloto
 10  bloqueos globales (pausa, datos viejos, degradado, conciliación, sin stop, liquidación, límites de pérdida)
 11  factor de capital (caída, defensa, día/semana, objetivo, «relajado» tras 24 h) × vigilancia
 12  riesgo.dimensionar_con_tramos(): 3 escenarios (base / severo / límite) → el menor; apalancamiento mínimo que cabe
 13  libro: profundidad ≥ 3× nocional, impacto ≤ 0,15 %, redimensiona con 2×impacto
 14  ordenar por (factor, predicción, fuerza); equilibrar cartera de funding
 15  agregados: posiciones, mismo lado, riesgo abierto 9 %, exposición mercado/bruta/neta/beta, salto conjunto 20 %,
     correlación > 0,8, una por moneda
                │
gestor.abrir (gestor.py:970)  registro ANTES de enviar → ALO al mejor precio, 20 s (consulta cada 2 s) → cancelar
  y CONFIRMAR → lo que falta según POSICIÓN REAL y FILLS → IOC (mid ± 0,5 %, si no se escapó > 0,5 %)
  → stop trigger de mercado reduce-only (marca, límite ±10 %), VERIFICADO → TP1 (50 %) + TP final (límite GTC RO)
                │
cada ciclo: gestor.conciliar (cuenta vs registro; congela ante divergencia), gestionar (tiempo máximo, sin pérdidas,
  trailing con el mid cada 15 s), _ampliar_ganadoras (simulado), cerrar_huerfanas_ledger (6 h)
                │
cierre: procesar_cierre → fills (closedPnl, fee) + funding atribuido → R = PnL / (|entrada − stop| × tamaño)
  → ledger «cierre» → memoria.cerrar_real → promociones.registrar_evidencia («paper»)
```

En SIMULADO, `papel.CuentaPapel` sustituye al exchange con el MISMO contrato del SDK: órdenes contra el libro real
(foto de 20 niveles + libro agregado), ALO llenada solo si hay contrapartida o una operación impresa peor (velas de
1 min), stops disparados por la marca leída en cada `procesar()`, funding horario con la tasa real, liquidación estimada.

## 3. Capas y acoplamiento

| Capa | Módulos | Observaciones |
|---|---|---|
| Orquestación | `bot.py` (2 389 l.) | Monolito: decisión, agenda, comandos, panel_datos, ballenas, websocket. `procesar_candidatas` ≈ 245 líneas con 5 vías de decisión entrelazadas |
| Señales | `senales.py`, `motor.py` | Limpio; funciones puras de señal reutilizadas en lab y vivo |
| Decisión | `cerebro*.py`, `aprendizaje.py`, `mercado_unificado.py` | Tres filtros apilados (cerebro, memoria, factor de capital) sin validación conjunta |
| Riesgo | `riesgo.py` | Bien estructurado y compartido con el lab |
| Ejecución | `gestor.py`, `ejecucion.py` | Lo mejor del sistema: idempotencia por CLOID, verificación, congelación ante duda |
| Simulación | `papel.py` | Cuidadoso pero con sesgos de muestreo (T-01) |
| Validación | `laboratorio.py`, `validacion.py` | Metodología correcta en lo esencial; resultados todos negativos |
| Presentación | `panel.py` + `panel_web/` (8 638 l.), `taller.py`, `mesa.py`, `sombras.py`, `ceto.js`, `nucleo.js` | Sobredimensionado frente al valor del sistema |

## 4. Divergencias documentación ↔ código

| Documentación | Código real | Ref. |
|---|---|---|
| `papel.py` cabecera: «MODELO = 2»; «entra en la huella vía promocion.MODELO_SIMULACION» | `papel.MODELO = 3`, pero `promocion.MODELO_SIMULACION = 2` | papel.py:14,41; promocion.py:196 |
| `contexto_externo.py`: «no cambia ninguna decisión del bot» | Alimenta 4 de los 8 rasgos del cerebro; sin ellos el cerebro se abstiene | cerebro_vivo.py:148-150 |
| CLAUDE.md: «no borres datos_mercado/» | `Mercado._limpiar` borra `datos_mercado/` de más de 120 días | mercado.py:_limpiar |
| Prompt del escéptico: «funding_contra > 0 = a favor» | `funding_contra > 0` = en contra (filtro de entrada) | analista_ia.py:102; bot.py:670 |
| AUDIT_CONTEXT: «las de exploración amplia no ocupan los huecos del cerebro» | Correcto, pero entonces el riesgo abierto total puede superar el 9 % (9 % + 4×0,5 %) en simulado | bot.py:1005 |
| Laboratorio: «lo que se prueba es lo que se opera» | Trailing por vela (lab) vs cada 15 s (vivo); TP por toque (lab) vs por operación impresa (simulado) | estrategia.py:230,243; gestor.py:1222 |
| Sombras citadas como evidencia («momentum +1,12 R») | Muestreo puntual sin deslizamiento: +0,12 R/op de sesgo medido | aprendizaje.py:160-200 |

## 5. Interacciones que producen resultados incorrectos (aunque cada pieza sea correcta aislada)

1. **TP1 parcial + «sin pérdidas» + piramidación** (gestor.py:1219-1221 + bot.py:1245-1310): al cobrar el TP1 el stop
   pasa a la entrada; eso hace la operación «ampliable» y en el ciclo siguiente se vuelve a comprar el 50 % recién
   vendido, a peor precio y con comisión taker. Caso real SKY 23/11: +0,29 R → −0,38 R.
2. **Exploración + memoria + factor de capital**: tres reductores multiplicativos de tamaño (0,167 × 0,5 × 0,5…) hacen
   que muchas operaciones simuladas sean de 10–40 $ de nocional: el ruido de ejecución y el mínimo de 10 $ dominan y la
   evidencia «paper» no representa el tamaño que se operaría en real.
3. **Régimen de BTC + límite «4 del mismo lado»**: en un mercado bajista el filtro deja pasar solo cortos y el límite
   bloquea el quinto: la cartera queda forzada a ser «corto beta» con 4 posiciones muy correlacionadas (correlaciones
   0,82–0,96 registradas en los descartes).
4. **Sombra única por moneda y lado** (aprendizaje.py:156-171, `hay_sombra_abierta`): la primera estrategia que se descarta ocupa la sombra; las
   demás de esa moneda/lado no se siguen → la evidencia por estrategia depende del orden de evaluación.
