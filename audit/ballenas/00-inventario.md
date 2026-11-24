# 00 · Inventario (auditoría del 19/11/2026)

Leyenda usada en toda la auditoría: **[HECHO]** verificado con código, datos o ejecución · **[DEFECTO]** fallo confirmado ·
**[RIESGO]** riesgo potencial · **[HIPÓTESIS]** a validar · **[NO VERIFICADO]**.

Durante la auditoría no se cambió código ni configuración. No se envió ninguna orden. Solo se hicieron lecturas, scripts de
análisis de solo lectura (en el directorio temporal) y la batería de pruebas local (`papel.py` y mocks).

## Repositorio

- **Lenguaje:** Python 3.14. **Panel:** JavaScript nativo (ES modules) en `panel_web/`, sin compilación. No es un repositorio
  git, así que no hay historial de cambios auditable; la trazabilidad depende de `CLAUDE.md` y del ledger. **[HECHO]**
- **Dependencias fijadas** (`requirements.txt`): `hyperliquid-python-sdk==0.24.0`, `python-dotenv==1.2.4`,
  `requests==2.34.2`. Hay entorno completo en `requirements-bloqueado.txt`. **[HECHO]**
- **Tamaño:** unas 15 000 líneas de Python en la raíz, más el paquete `carry/` (unas 850).
  - Módulos mayores: `bot.py` 2206 · `laboratorio.py` 1607 · `gestor.py` 1445 · `panel.py` 1111.
- **Pruebas:** 59 archivos y 710 pruebas. Hoy se ejecutaron todas: OK en 101 s. **[HECHO]**

## Procesos en marcha (verificado el 19/11)

| Proceso | Entrypoint | Función |
|---|---|---|
| Bot | `bot.py` (lanzador `INICIAR.bat` / `despliegue/iniciar_windows.ps1`) | Bucle principal: datos, señales, decisiones, órdenes simuladas y gestión |
| Panel | `panel.py` (127.0.0.1:8080) | Panel web; hilo del analista IA (Groq) |
| Carry | `python -m carry.motor` | Carry de funding de dos patas, simulado y aparte del bot |
| Laboratorio | `laboratorio.py` (lanzado por la agenda o `/laboratorio`) | Walk-forward, holdout y veredictos. En marcha desde las 12:14 UTC |
| Túnel | `cloudflared` | Expone el panel a internet (ver 07) |

## Componentes por dominio

| Dominio | Archivos |
|---|---|
| Datos de mercado | `bot.leer_precios`, `motor.contexto` (velas REST), `mercado.py` (websocket de operaciones y OI), `contexto_externo.py` (Binance/Bybit, solo lectura), `datos.py` (API con caché), `limitador.py` |
| Señales | `senales.py` (6 módulos técnicos), `motor.py` (cierre de vela, ranking, aspirantes), `ballenas.py` (flujo de grandes cuentas), `mercado.senales_liquidaciones` |
| Decisión | `cerebro.py` (ridge), `cerebro_vivo.py`, `mercado_unificado.py` (rasgos), `aprendizaje.py` (memoria por vecinos), `bot.procesar_candidatas` |
| Riesgo | `riesgo.py`, `estrategia.factor_capital` (gestión de capital), `vigilancia.py` (degradación por estrategia) |
| Ejecución | `ejecucion.py` (envío, consulta, cancelación confirmada), `gestor.py` (ciclo de vida, conciliación, stops) |
| Simulación | `papel.py` (cuenta ficticia con libro, marca y funding reales), `carry/papel_*.py` |
| Contabilidad | `ledger.py` (JSONL de solo añadir), `contabilidad.py` |
| Validación | `laboratorio.py`, `validacion.py`, `investigacion.py`, `preregistro.py`, `promocion.py` (pase a real) |
| Observabilidad | `observabilidad.py` (`estado_sistema.json`), `feed.py`, `taller.py`, `mesa.py`, panel |
| IA | `analista_ia.py`: informes en texto; no decide ni escribe configuración (ver 02 §1.3) |

## Exchanges y mercados

- **Hyperliquid:** único exchange con ejecución (perpetuos), vía SDK oficial (`Info` / `Exchange`). **[HECHO]**
- **Contado de Hyperliquid:** solo en `carry/`, y solo simulado. **[HECHO]**
- **Binance y Bybit:** solo datos públicos de lectura (rasgos del cerebro e historia del laboratorio). No hay código de órdenes
  para ellos. **[HECHO]**
- No hay CCXT ni ninguna capa multi-exchange. Los apartados de «multiexchange» del encargo no aplican; ver 03.

## Configuración y modo

- `config.json`: `modo: simulado`, cuenta ficticia de 232 $.
- Riesgo: 3 % por operación, 9 % abierto, 6 posiciones.
- `piloto_real` escrito igual al simulado. **No está aplicado**: necesita un arranque manual (ver 04).
- `.env`: se comprobaron solo los nombres de las variables. `HL_API_WALLET_KEY`, `HL_DIRECCION_CUENTA`, `TELEGRAM_*` y
  `PANEL_PASSWORD` están vacías; solo `GROQ_API_KEY` tiene valor. No hay credenciales de trading. **[HECHO]**

## Datos y registros

- **Contabilidad y estado:** `registro/ledger.jsonl` (verdad contable), `estado.json`, `papel.json`, `aprendizaje.json`.
- **Laboratorio y cerebro:** `estrategia_elegida.json` (veredictos del 15/11), `cerebro_modelo.json`.
- **Logs:** `bot.log` (837 KB, sin rotación), `logs/bot.jsonl`, `logs/panel_acceso.log*` (con rotación).
- **Datos de mercado:** `datos_mercado/`, `datos_archivo/`, `datos_backtest/` (caché).
