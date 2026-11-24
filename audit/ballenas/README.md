# Auditoría maestra de Ballenas (19/11/2026): resumen ejecutivo

**Veredicto: PAPER TRADING.**
- La mecánica es sólida y está verificada: órdenes, stops, conciliación y contabilidad cuadran con la cuenta.
- **No hay ventaja estadística demostrada:** 13/13 estrategias `no_supera`. Solo el cerebro de 4 h con datos externos es
  prometedor (OOS t 2,97, holdout +0,071 R), sin validar y con un posible sesgo de datos.
- El +12,6 % simulado (+29,25 $ en 22 operaciones) viene de cortos en un mercado bajista. Dos operaciones hacen el 78 %.
  La R media por operación es +0,06 (t 0,26).
- **No es candidato a real.**

Sin cambios de código ni configuración y sin órdenes durante la auditoría. Pruebas locales: 710/710 OK.

## Documentos

| Documento | Contenido |
|---|---|
| [00-inventario](00-inventario.md) | Repositorio, procesos, componentes |
| [01-arquitectura](01-arquitectura.md) | Flujo real de una operación, fallos, matriz de funcionalidades |
| [02-cerebro-estrategias](02-cerebro-estrategias.md) | Decisión, estrategias y su evidencia |
| [03-ejecucion-exchanges](03-ejecucion-exchanges.md) | Exchanges, ciclo de vida de una orden, 15 escenarios |
| [04-riesgo](04-riesgo.md) | Fórmulas, controles, defectos |
| [05-paper-trading](05-paper-trading.md) | Simulador, paridad, operación por operación |
| [06-resultados-cuantitativos](06-resultados-cuantitativos.md) | Métricas, validación, costes, clasificación |
| [07-seguridad-resiliencia](07-seguridad-resiliencia.md) | Secretos, exposición, copias, observabilidad |
| [08-pruebas](08-pruebas.md) | Lo ejecutado y lo pendiente |
| [09-roadmap](09-roadmap.md) | Tareas priorizadas (no implementadas) |
| [10-veredicto](10-veredicto.md) | Respuestas, puntuaciones, estado |

## Estado de las correcciones

| Tarea | Estado | Pruebas |
|---|---|---|
| R-01 (D1) | **Hecho, 19/11 tarde**: la ampliación pasa bloqueos, exposición, desplome conjunto y horquilla | `test_bot`: `test_ampliar_respeta_*` |
| R-05 (D5) | **Hecho, 19/11 tarde**: `riesgo.comprobar_salto` por lado, tope del 20 % del equity | `test_auditoria_arreglos.DesplomeConjunto`, `test_entrada_bloqueada_por_desplome_conjunto` |
| R-08 (D8) | **Hecho, 19/11 tarde**: `gestor.cerrar_huerfanas_ledger`; kPEPE se cierra al arrancar como resultado desconocido | `test_auditoria_arreglos.HuerfanasDelLedger` |
| R-07, R-10 | **Hecho, 21/11**: `ledger.via_decision`, panel Operaciones → «Por vía»; bloque del cerebro en la ficha | `test_mejoras_auditoria` |
| R-09 | **Hecho, 21/11**: caché `funding_vivo_cache.json` | `FundingEnDisco` |
| R-11 | **No era un fallo**: `bot.log` ya rotaba (5 MB × 3) | — |
| R-14 | **Hecho, 21/11**: `papel._recuperar_hueco` | `StopsConElBotParado` |
| Resto | Pendiente (ver 09); R-02/R-03/R-04/R-12/R-15 dependen de Roberto | — |

## Matriz de problemas

| ID | Clase | Gravedad | Problema | Evidencia | Tarea |
|---|---|---|---|---|---|
| D1 | DEFECTO | P0 (solo simulado) | La ampliación se salta pausa, límites de pérdida, datos viejos, conciliación y exposición | `bot.py:1233` | R-01 |
| D2 | DEFECTO | P1 | Panel expuesto a internet sin contraseña (lectura de saldo, posiciones, estrategias) | `cloudflared` activo, `panel.tunel_sin_clave`, `panel.py:842` | R-02 |
| D3 | DEFECTO operativo | P1 | Sin alertas fuera del panel (Telegram sin claves) | `.env` | R-03 |
| D4 | DEFECTO operativo | P1 | Sin copias de seguridad en Windows | `despliegue/` | R-04 |
| D5 | RIESGO | P1 | Salto correlacionado sin límite agregado (~26 % con 4 posiciones del mismo lado) | `riesgo.py:141-147`, `:283` | R-05 |
| D6 | HIPÓTESIS | P1 | La ventaja del cerebro de 4 h puede venir de la historia sustituida | `estrategia_elegida.json` (con todo frente a solo HL) | R-06 |
| D7 | RIESGO | P1 | Evidencia mezclada entre cinco vías de decisión | `bot.py:841-907` | R-07 |
| D8 | DEFECTO | P2 | Operación kPEPE del 23/10 sin cierre en el ledger | `op-20261023120105-55b133` | R-08 |
| D9 | DEFECTO operativo | P2 | Arranque: 10–15 min de ciclo lento (funding de 90 días) | `motor.py:230`, medido | R-09 |
| D10 | DEFECTO menor | P2 | Resumen del ledger sin el bloque del cerebro | `ledger.py:220` | R-10 |
| D11 | DEFECTO menor | P2 | `bot.log` sin rotación | 837 KB | R-11 |
| D12 | RIESGO | P2 | Se operan estrategias negativas en exploración | `bot._puede_explorar` | R-12 |
| D13 | NO VERIFICADO | P2 | Vulnerabilidades de dependencias | `requirements*.txt` | R-13 |
| D14 | RIESGO | P3 | En simulado, si el bot cae no corren los stops | `papel.procesar` | R-14 |
| D15 | RIESGO | P1 (antes de real) | `piloto_real` escrito con 50 % de pérdida máxima, todos los mercados y 5× | `config.json` | R-15 |
