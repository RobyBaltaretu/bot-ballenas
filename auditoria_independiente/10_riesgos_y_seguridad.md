# 10 — Riesgos y seguridad

## 1. Escenarios extremos (comportamiento verificado en el código)

| Escenario | Qué hace el bot | Riesgo residual | Severidad |
|---|---|---|---|
| Caída repentina que salta los stops | Stops en el exchange por marca, límite ±10 %; tamaño acotado por el escenario «límite» (≤ 15 % del valor por operación) y salto conjunto ≤ 20 % por lado | Un hueco > 10 % deja la orden hija sin llenar: **pérdida sin tope** hasta que el bot cierre con IOC (5 % de tolerancia) | Alta con 5× y 6 posiciones |
| Liquidaciones en cascada | Liquidación ≥ 1,5× la distancia al stop; vigilancia del `liquidationPx` real y cierre si queda antes que el stop | Con margen aislado y ≤ 5× la liquidación está lejos; correcto | Media |
| Horquilla dispara / libro vacío | Entradas bloqueadas (horquilla, profundidad, impacto); cierres con IOC escalonados (0,5 %, 2 %, 5 %) | Si nada llena, mantiene el stop y reintenta cada ciclo | Media |
| Desconexión del exchange / API caída | Lecturas fallidas → conciliación pendiente → entradas bloqueadas; 5 errores → «degradado» | Stops en el exchange siguen vivos en real. En simulado, nadie los procesa (recuperación estimada > 3 min) | Baja (real) / media (simulado) |
| Caída del proveedor de IA | Sin efecto en decisiones | Ninguno | — |
| Caída de Binance/Bybit | El cerebro se abstiene: **no entra nada** | Riesgo de no operar, no de perder | Baja |
| Orden parcial | Se protege el tamaño real; IOC solo por lo que falte según posición y fills | Correcto | — |
| Ejecutada sin confirmación | Estado «desconocida/no_confirmada» → mercado congelado; nunca reenvía | Correcto | — |
| Reinicio con posiciones | Registro antes de enviar; conciliación al arrancar; adopción de stops existentes; huérfanas cerradas en el ledger | Correcto | — |
| Datos obsoletos | Precios > 120 s o cuenta > 90 s → entradas bloqueadas | Correcto | — |
| Movimientos adversos simultáneos | Límites de lado (4), correlación, beta, salto conjunto | Si todas las del mismo lado saltan a la vez: escenario base acotado al 9 % (riesgo abierto) y escenario de salto al 20 % del valor de la cuenta | Alta |
| Funding extraordinario (hasta 4 %/h en Hyperliquid) | El funding previsto ×2 entra en el tamaño; filtro de funding en contra en la entrada | No hay salida por funding durante la operación (solo el carry la tiene) | Media en memecoins |
| Fallo de conciliación | Mercado congelado, alerta, sin entradas | Correcto | — |
| Bot parado (PC doméstico) | En real los stops siguen; en simulado R-14 estima con velas de 1 min | **Sin alertas externas** (Telegram y Healthchecks sin configurar): nadie se entera | Alta operativa |
| Otra instancia sobre la misma cuenta | Bloqueo por carpeta y por cuenta; aviso ante CLOID desconocidos | Correcto | — |

**¿Puede perder el control de sus posiciones?** En el diseño actual, solo en dos casos razonables: (1) hueco mayor que
la tolerancia del stop con el proceso caído (la orden hija no llena y nadie reintenta el cierre) y (2) el PC apagado sin
alertas durante un movimiento fuerte. Ambos se mitigan con VPS, alertas externas y un apalancamiento menor.

## 2. Riesgos financieros

| Riesgo | Situación | Recomendación |
|---|---|---|
| Esperanza matemática | **No demostrada** para ninguna estrategia direccional | No operar real |
| Riesgo por operación 3 % | Muy alto para un sistema sin ventaja: 10 pérdidas seguidas ≈ −26 % | 0,5–1 % hasta tener evidencia |
| Piloto real = simulado (3 % / 9 % / 6 / 5× / −50 %) | Decidido por el propietario el 19/11 | 1 % / 3 % / 3 posiciones / 2× / −20 %; solo BTC/ETH/SOL al principio |
| Suelo de emergencia −50 % | Llega tarde | −20 % y parada manual obligatoria |
| Memecoins en el universo | Horquillas, huecos y funding extremo | Excluir en real |
| Concentración direccional | Régimen + 4 del mismo lado = apuesta única al beta | Límite de exposición neta ≤ 100 % del valor y beta ≤ 100 % |
| Contraparte | Hyperliquid (L1 propia), USDC | Capital pequeño, retiradas periódicas |

## 3. Riesgos técnicos y operativos
- PC doméstico con suspensión, cortes de luz y red; migración a Hetzner preparada pero **no ejecutada**.
- Sin copias de seguridad en Windows; el ledger es la verdad contable y solo existe en ese disco (y ahora en GitHub).
- El código de órdenes **nunca se ha probado** contra la API real (ni testnet).
- Dependencia de Binance/Bybit para decidir (C-03).
- Monolito `bot.py`; cualquier cambio reinicia la evidencia (incentivo a no corregir).

## 4. Ciberseguridad

| Área | Estado | Hallazgo |
|---|---|---|
| Secretos | `.env` fuera del repo; enmascarado en logs (`observabilidad.ocultar_secretos`); prueba `test_secretos.py`; barrido propio sin hallazgos | ✔ |
| Claves de operación | Diseño con API wallet (no puede retirar) en subcuenta; verificación `userRole` | ✔ |
| Panel | Solo 127.0.0.1; token por página, mismo origen, límite de frecuencia y tamaño; CSP estricta; `dom.h` sin `innerHTML` | ✔ |
| Panel por túnel | **Sin contraseña** (`tunel_sin_clave`): lectura pública de saldo, posiciones y estrategias | **SEG-01, P1** |
| Repositorio público | Contiene ledger, estado, datos y rutas locales; ningún secreto | Riesgo de privacidad y de ingeniería social (se conoce la operativa y el tamaño de la cuenta) |
| Dependencias | `pip-audit`: sin vulnerabilidades conocidas (24/11/2026); VPS instala versiones no fijadas | OPS-01 |
| Inyección en el LLM | Datos propios; la IA no actúa | Bajo |
| Integridad de configuración | Validación completa, lista blanca en el panel, copias, `piloto_real` no aplicable desde el panel | ✔ (con la incidencia del 19/11 documentada) |
| Procesos externos | `subprocess.Popen` solo con rutas internas y argumentos fijos | ✔ |

## 5. Plan de mitigación (resumen; detalle en 14)
1. P1: `PANEL_PASSWORD` + Cloudflare Access; eliminar `tunel_sin_clave` del código.
2. P1: Telegram + Healthchecks configurados **antes** de cualquier cosa real; probar que avisan.
3. P1: VPS con `requirements-bloqueado.txt`, copias cifradas del ledger y del estado.
4. P1: campaña en **testnet** de Hyperliquid de todas las rutas de órdenes (entrada ALO, IOC de reserva, stop, TP,
   sustitución de stop, cancelaciones ambiguas, reinicio con posiciones).
5. P1: límites del piloto real reducidos (sección 2) y exclusión de memecoins.
6. P2: salida por funding extremo durante la operación; vigilancia de `userRateLimit`.
