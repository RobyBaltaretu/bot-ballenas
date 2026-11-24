# 09 · Hoja de ruta (no implementado: pendiente de aprobación de Roberto)

| ID | Prio | Título | Problema · evidencia | Propuesta técnica | Módulos | Pruebas | Aceptación |
|---|---|---|---|---|---|---|---|
| R-01 | **P0** | La ampliación debe pasar los mismos controles que una entrada | D1: `bot._ampliar_ganadoras` (`bot.py:1233`) se salta `bloqueos_entrada` y `comprobar_agregados` | Llamar a `bloqueos_entrada(eq)` y a `comprobar_agregados` con el riesgo y el nocional añadidos antes de `gestor.ampliar`; además, horquilla e impacto del libro | `bot.py` | T-R1, T-R2 | No amplía con pausa, límites de pérdida, datos viejos ni exposición superada |
| R-02 | **P1** | Cerrar el panel expuesto | `cloudflared` + `tunel_sin_clave: true` sin `PANEL_PASSWORD` | Roberto pone `PANEL_PASSWORD` en `.env` y se quita `tunel_sin_clave` (o se para el túnel) | `.env`, `config.json` | T-S1 | Por el túnel: 401/403 sin clave |
| R-03 | **P1** | Alertas fuera del panel | Telegram sin claves: ninguna alerta llega | Roberto pone `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`; probar `/estado` | `.env` | Manual | Llega una alerta de prueba |
| R-04 | **P1** | Copias de seguridad en Windows | No hay copias; el ledger es la verdad contable | Tarea programada que copie `registro/`, `estado.json`, `papel.json`, `aprendizaje.json` y la config (o migrar a la VPS con `copia_seguridad.sh`) | `despliegue/` | Restauración de prueba | Copia diaria verificada |
| R-05 | **P1** | Límite agregado del escenario severo | Salto correlacionado de hasta ~26 % con 4 posiciones del mismo lado (04 §4.2) | Sumar el riesgo «límite» de todas las abiertas + la nueva ≤ X % del equity (p. ej. 20 %) en `comprobar_agregados` | `riesgo.py` | T-R3 | Ninguna combinación supera X % en el escenario límite |
| R-06 | **P1** | Validar el cerebro de 4 h sin sesgo de datos | «Con todo» > «solo HL» y la historia anterior a HL es sustituida | Laboratorio en curso + T-Q2 (solo periodo con HL) + T-Q3 (por régimen). Si pasa, **prerregistrar** antes de mirar más | `laboratorio.py`, `preregistro.py` | T-Q1, T-Q2, T-Q3 | Veredicto escrito antes de cambiar nada |
| R-07 | **P1** | Separar la evidencia de las vías de decisión | Cinco vías en simulado mezclan resultados (02, 05) | Etiqueta única `via` en el plan del ledger (`cerebro` / `cerebro_exploracion` / `exploracion_amplia` / `cartera` / `ballenas`) y métricas por vía en el panel | `bot.py`, `ledger.py`, `panel.py` | Unitaria | Cada operación tiene una sola vía y el panel las separa |
| R-08 | P2 | Cierre de operaciones huérfanas en el ledger | kPEPE 23/10 «completada» para siempre (03) | Si la conciliación no encuentra la posición y las órdenes del `trade_id` quedan huérfanas canceladas, registrar `cierre` con `contabilidad: incompleta` | `gestor.py` | T-D4 | Ninguna operación «abierta» sin posición tras N ciclos |
| R-09 | P2 | Arranque sin saturar el limitador | 10–15 min de ciclos lentos tras cada reinicio (03) | Guardar `funding_hist` en disco y bajar solo lo nuevo; o presupuesto propio para el hilo (p. ej. ≤ 30 % del límite) | `motor.py`, `datos.py` | T-D3 | Ciclo < 15 s desde el primer minuto |
| R-10 | P2 | Bloque `cerebro` en el resumen del ledger | `ledger.aplicar` lo descarta (`ledger.py:220`) | Copiar `cerebro`, `aprendizaje` y `tamano` al resumen de la operación | `ledger.py`, panel | Unitaria | La ficha muestra la predicción |
| R-11 | P2 | Rotar `bot.log` | 837 KB y creciendo | `RotatingFileHandler` como en el panel | `bot.py` (`configurar_logs`) | Manual | Rota al llegar a N MB |
| R-12 | P2 | Revisar la exploración de estrategias negativas | Se operan estrategias con t ≤ −2 (02) | Decisión de Roberto: volver a `t_min_laboratorio` o fijar un presupuesto de exploración mensual | `config.json` | — | Decisión documentada |
| R-13 | P2 | Auditoría de dependencias | `pip-audit` no disponible | Instalar la herramienta (con autorización) y revisar `requirements-bloqueado.txt` | — | T-S2 | Sin CVE críticos |
| R-14 | P3 | Simulador sin el bot | Si el bot cae, los stops simulados no corren | Aceptarlo y documentarlo, o un vigilante mínimo de stops en el proceso del carry o del panel | `papel.py` | — | Decisión documentada |
| R-15 | P3 | Revisar el piloto antes de real | `piloto_real` = simulado (50 % de pérdida máxima, todos los mercados, 5×) | Antes de la primera promoción, decidir por escrito los límites del primer real (recomendado: muy por debajo) | `config.json` | `test_capital_piloto` | Firmado por Roberto |

## Orden recomendado

1. **Riesgos críticos:** R-01, R-02.
2. **Integridad y operación:** R-03, R-04, R-08, R-09, R-11.
3. **Riesgo agregado:** R-05.
4. **Simulador fiable y evidencia separada:** R-07, R-10, R-14.
5. **Validación estadística:** R-06, y con su resultado R-12.
6. **Mejora de decisiones:** solo lo que salga validado de R-06 (cerebro 4 h) y del carry (30 cierres).
7. **Costes:** maker en salidas y staking de HYPE solo cuando haya una estrategia positiva (hoy no cambian el signo).
8. **Hacia real:** R-15 + calibración con capital mínimo (T-P2) + promoción con `promocion.py` y aprobación de Roberto.

## Comparación externa (fase 9, alcance limitado)

No se hizo búsqueda web nueva en esta auditoría. Se reutilizan las fuentes verificadas en `ESTUDIO_BOT_2026-11-19.md`
(comisiones de Hyperliquid, estudios de tendencia en cripto, diferencial de funding). Frente a Freqtrade, Nautilus o LEAN,
lo que le falta a Ballenas **no** es su arquitectura, que en conciliación y órdenes ambiguas es más estricta que la de la
mayoría de bots, sino:
- una estrategia con ventaja;
- operación robusta: copias, alertas y máquina siempre encendida.

No se recomienda migrar a otro framework: no resolvería ninguno de los defectos encontrados.
