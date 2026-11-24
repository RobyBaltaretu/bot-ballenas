# 07 · Seguridad, resiliencia y observabilidad

## Seguridad

| Punto | Estado | Evidencia | Clase |
|---|---|---|---|
| Secretos | En `.env`, nunca en `config.json`. Hoy solo `GROQ_API_KEY` tiene valor; no hay claves de trading | Revisión de nombres de variables (sin leer valores) | HECHO |
| Secretos en salidas | Pruebas de que la API de datos, el CSV, el detalle, el diagnóstico y los logs no los contienen | `tests/test_secretos.py` (3) | HECHO |
| Permisos para real | Solo API wallet (agente) de una **subcuenta**; se verifica rol y maestra antes de firmar | `bot.verificar_subcuenta` (`bot.py:156`) | HECHO |
| Separación paper/real | Simulado sin cliente firmante; shadow con `EjecutorShadow` que bloquea; real con cinco barreras (subcuenta, agente, propiedad, promoción, piloto) | `bot.crear_cliente`, `bot.py:2267` | HECHO |
| Cambios peligrosos desde el panel | `/aplicarconfig` no aplica cambios de `modo`, `red`, `real` ni `piloto_real` | `bot.aplicar_config_nueva` (`bot.py:1660`) | HECHO |
| **Panel expuesto a internet** | `cloudflared` en marcha y `panel.tunel_sin_clave: true` sin `PANEL_PASSWORD`: **cualquiera con la URL del túnel ve saldo, posiciones, estrategias y registros** (solo lectura; los comandos remotos están bloqueados) | `panel.py:834-844`, `:1210`; proceso `cloudflared` | **DEFECTO** (P1) |
| CSP | Estricta; DOM sin `innerHTML` | `panel.py:879`, `dom.js` | HECHO |
| Dependencias | 3 directas, fijadas. No se pudo pasar `pip-audit` (no está instalado y la auditoría no instala nada) | `requirements.txt` | NO VERIFICADO |
| Analista IA | Lee datos y escribe informes; sin acceso a órdenes ni configuración | `analista_ia.py:141` | HECHO |

## Resiliencia

| Punto | Estado | Evidencia |
|---|---|---|
| Reinicio automático | El lanzador rearranca (código 4); vigilante de ciclo colgado (20 min) | `iniciar_windows.ps1`, `bot.comprobar_cuelgue` |
| Una sola instancia | Bloqueo del sistema operativo por cuenta | `instancia.BloqueoInstancia` |
| Escrituras | Ledger con `fsync` y solo añadir; JSON con escritura atómica; línea corrupta se salta y se cuenta (0 hoy) | `ledger.py:91-99`, `compat.reemplazar` |
| **Copias de seguridad** | **No hay en Windows.** `copia_seguridad.sh` y el timer de systemd son solo para la VPS, que no existe | `despliegue/` (grep sin coincidencias en `iniciar_windows.ps1`) |
| Punto único de fallo | Un PC doméstico: red (≈700 avisos de conexión en `bot.log`), luz y disco. En simulado, si el bot cae, **los stops simulados no se ejecutan** | Estudio del 19/11, `papel.procesar` |
| Arranque | 10–15 min de ciclo lento por la descarga del funding (ver 03) | Medido hoy |
| Datos externos | Sin Binance/Bybit frescos, el cerebro se abstiene (falla cerrado) | `cerebro_vivo.py:149` |

## Observabilidad

- **Trazabilidad [HECHO]:**
  - `trade_id` común a señal, decisión, órdenes (CLOID/oid), fills, protección, funding (con hora real desde el 19/11) y
    cierre. Se puede reconstruir cada operación (ver 05).
  - Huecos:
    - resumen sin el bloque `cerebro` (ver 02);
    - la operación kPEPE del 23/10 sin cierre (ver 03).
- **Salud:** `estado_sistema.json` con componentes, ciclos, esperas del limitador y, desde el 19/11, peso por tipo de
  petición. Más el panel (Taller, Mesa, Sistema), `logs/bot.jsonl`, el feed de eventos y el latido externo opcional
  (`HEALTHCHECK_URL` vacío).
- **Alertas:** Telegram sin configurar, así que **hoy no llega ninguna alerta fuera del panel**. **[DEFECTO operativo]**
- **[DEFECTO menor]** `bot.log` no rota (837 KB y creciendo). `logs/panel_acceso.log` sí rota.
