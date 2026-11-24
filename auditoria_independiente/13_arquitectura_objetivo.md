# 13 — Arquitectura objetivo

**Principio:** no reescribir. Conservar el núcleo de ejecución y riesgo (lo mejor del proyecto), **quitar** las capas de
decisión sin evidencia y **separar** producción de investigación. La arquitectura más sencilla capaz de operar una o dos
estrategias validadas con seguridad.

## 1. Diagrama propuesto

```
                         ┌──────────────────────────── INVESTIGACIÓN (fuera de producción) ─────────────────────────┐
datos públicos ─► archivo│ velas, funding, OI, fills de ballenas (sin borrado; copia en R2 con hash por ejecución)  │
 (HL, Binance)           │ laboratorio WF + holdout + DSR/PBO + referencia BTC/beta  ─►  informe + veredicto         │
                         │ prerregistro de hipótesis (una variante por hipótesis)                                    │
                         └──────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                                │ solo estrategias «supera» + aprobación humana
                                                                ▼
┌──────────────────────────── PRODUCCIÓN (bot direccional) ──────────────────────────────────────────────┐
│ motor de señales (senales.py) ─► 1–2 estrategias validadas, parámetros fijos                            │
│   └─ filtro de régimen (EMA200 BTC) SI está en la definición validada                                   │
│ riesgo.py: riesgo fijo por operación (0,5–1 %) × vigilancia; límites agregados; salto conjunto          │
│ gestor.py + ejecucion.py: SIN CAMBIOS de fondo (CLOID, stops verificados, conciliación, congelación)    │
│ papel.py: stops y objetivos con la MISMA regla de llenado; margen simulado                              │
│ ledger.py: verdad contable; curva de valor diaria completa                                              │
│ alertas externas (Telegram + Healthchecks) obligatorias; VPS                                            │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────── PRODUCCIÓN (carry, proceso aparte) ─────────┐
│ carry/: corto perp + largo contado HL; su propio ledger y límites        │
└──────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────── PANEL (solo lectura remota, con contraseña) ┐
│ estado, posiciones, riesgo, ledger, veredictos del laboratorio           │
└──────────────────────────────────────────────────────────────────────────┘
```

## 2. Motores

| Motor | Hoy | Objetivo | Cambio |
|---|---|---|---|
| Datos | Velas por petición, OI grabado y borrado a 120 días, externos en vivo | Archivo sin borrado + copia versionada; externos solo si una estrategia validada los usa | Quitar `_limpiar`; R2 |
| Señales | 9 módulos × 2 intervalos + ballenas + liquidaciones + aspirantes | 1–2 módulos validados; el resto en el cementerio de investigación | Simplificar |
| Clasificación de mercado | EMA200 de BTC por intervalo | EMA200 de BTC en 4 h (una sola definición) | Simplificar |
| Ballenas | Selección por PnL mensual, señal y veto | Fuera de producción; datos para un estudio futuro | Eliminar del bot |
| IA | Cerebro (decide) + LLM (informa) | Sin cerebro hasta que un filtro supere; LLM opcional solo para redactar | Eliminar / sustituir |
| Asignación de capital | Factores apilados (capital, defensa, objetivo diario, memoria, exploración, vigilancia) | Riesgo fijo × vigilancia (solo reduce) | Simplificar |
| Riesgo | Muy completo | Igual, con límites del piloto reducidos y techos duros más bajos | Mantener |
| Ejecución | Robusta | Igual + vigilancia de `userRateLimit` + salida por funding extremo | Mantener |
| Backtesting | Laboratorio WF sólido; divergencias con el vivo | Mismo código de salida en lab y vivo (trailing al cierre de vela) o motor por eventos (NautilusTrader) a largo plazo | Optimizar |
| Monitorización | Panel muy rico; sin alertas externas | Panel más pequeño + alertas externas + curva diaria | Simplificar + añadir |
| Experimentación | Exploración amplia y del cerebro dentro del bot | Fuera del bot de producción (o en una cuenta simulada separada con su propio ledger) | Separar |
| Evaluación continua | Vigilancia (bootstrap), promoción por huella | + comparación con el IC del lab y con la referencia de mercado | Optimizar |

## 3. Qué se elimina del flujo de decisión (y por qué)

| Componente | Motivo |
|---|---|
| Cerebro en exploración (`exploracion_simulado`) | No supera; contamina la evidencia |
| Exploración amplia | Opera lo que el lab da por negativo; evidencia mezclada |
| Memoria por vecinos | 7/7 pérdidas; hiperparámetros a mano |
| Relajación tras 24 h | Antipatrón |
| Piramidación | Deshace el TP1; sin valor |
| Ballenas (señal, veto, rasgo) | Sin señal en ninguna fuente |
| Liquidaciones inferidas | Sin señal; sin datos |
| Cartera de funding | No es lo que se estudió; validar primero |
| Estrategias negativas «en sombra» | Consumen peticiones y no informan nada nuevo |
| Factor «objetivo diario» | Sin base estadística |

## 4. Qué se conserva intacto
`gestor.py`, `ejecucion.py`, `riesgo.py`, `ledger.py`, `contabilidad.py`, `instancia.py`, `promocion.py` (huella y
aprobación humana), `validacion.py`, el núcleo de `laboratorio.py`, `senales.py`, `estrategia.SimSalida` (corrigiendo
T-05/T-06) y `carry/`.

## 5. Diferencia con la arquitectura actual
- De **5 vías de decisión** a **1** (estrategia validada → riesgo → ejecución).
- De **9+ estrategias activas o en sombra** a **1–2** en producción.
- De **4 multiplicadores de tamaño** a **1** (vigilancia).
- Investigación y producción en procesos y contabilidades separadas.
- Panel reducido a lo operativo (las vistas decorativas —núcleo 3D, Ceto, «Parte del mar», Mesa, Sónar— pueden quedarse
  como proyecto aparte, pero no deben condicionar el mantenimiento del bot).

## 6. Justificación
Cada capa añadida sin evidencia (1) introduce sesgos de medición, (2) cambia la huella y reinicia la evidencia, y (3)
multiplica los caminos que hay que probar en real. El núcleo de ejecución ya es sólido: el límite del proyecto no es la
ingeniería, es la **ausencia de una ventaja**. La arquitectura debe facilitar encontrarla (laboratorio honesto) y
operarla con seguridad (núcleo actual), no esconder su ausencia bajo capas de decisión.
