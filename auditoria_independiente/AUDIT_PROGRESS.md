# AUDIT_PROGRESS — registro para reanudar la auditoría independiente

- **Inicio y entrega 1:** 24/11/2026. **Commit auditado:** `b8a9f8d1f99e8cc02b74ca54523e6dac2210d0f9`,
  rama `claude/audit-algo-trading-bot-nua1pw`.
- **Modo:** solo lectura del código funcional. Ninguna orden real. Pruebas y experimentos en una COPIA del repositorio
  (scratchpad de la sesión), nunca en la carpeta original.
- **Estado:** **ENTREGA 1 — NO COMPLETADA AL 100 %** en revisión manual línea a línea. Las conclusiones financieras
  (ausencia de ventaja, sesgos de medición, beta) están demostradas y no dependen de lo pendiente.

## Entorno

- Python 3.13.18 (Linux) en un venv aislado con `requirements-bloqueado.txt` (el bot declara probado 3.12 y 3.14).
- Sin `.env`; ninguna variable `HL_*`, `BOT_REAL_CONFIRMADO`, `GROQ_*`, `TELEGRAM_*` en el entorno (comprobado).
- `config.json → modo: "simulado"`.
- Red: entorno `bot-ballenas` (aprobado por el usuario) con hosts públicos de lectura:
  - `api.hyperliquid.xyz/info` → OK. `data.binance.vision` → OK.
  - `api.binance.com`, `fapi.binance.com` → 451; `api.bybit.com` → 403 (bloqueo geográfico) → no utilizables.
  - `api.massive.com` (servicio conectado) → «Unknown API Key».

## Cobertura (detalle por archivo en 01_inventario_y_cobertura.md)

| Nivel | Archivos | Líneas |
|---|---|---|
| L — línea a línea | 16 | 8 104 (36 %) |
| F — secciones críticas + estático | 9 | 6 367 (28 %) |
| E — solo estático + cabecera | 42 | 8 015 (36 %) |
| Pruebas (`tests/`, 8 995 líneas) | ejecutadas; no revisadas línea a línea | — |
| Panel web (8 638 líneas JS/HTML/CSS) | muestreado (CSP, comandos) | — |
| `copias/` | excluido (no se importa) | — |

## Pendiente para completar el 100 % (por orden de prioridad)

1. **Lectura línea a línea, nivel F → L:** `laboratorio.py` (restante: probar_ballenas, probar_mercado, carry_realista,
   main), `validacion.py` (veredicto, cartera_produccion, meseta, RegistroHoldout), `promocion.py` (huella, hash_codigo),
   `panel.py` (resto de endpoints GET), `mercado.py`, `contexto_externo.py`, `cartera_funding.py`, `analista_ia.py`
   (informe y vigilante), `ledger.py` (aplicar, rotación).
2. **Nivel E → L, con efecto en decisiones según el propio bot:** `historia_externa.py`, `datos.py`, `archivo.py`,
   `vigilancia.py`, `limitador.py`, `configuracion.py`.
3. **Nivel E → L, sin efecto:** `investigacion.py`, `veredicto.py`, `preregistro.py`, `feed.py`, `observabilidad.py`,
   `notificaciones.py`, `config_panel.py`, `taller.py`, `mesa.py`, `sombras.py`, `revision_proceso.py`, `informe.py`,
   `diagnostico.py`, `comprobar.py`, `instancia.py`, `compat.py`, `estudios.py`, `laboratorio_semanal.py`,
   `manifiesto_datos.py`, `calendario_macro.py`, `coinglass.py`, `estudios_ext/*`, `carry/` (salvo `logica.py`),
   `despliegue/avisos.py`.
4. Panel web JS (`panel_web/assets/js/**`), scripts de despliegue PowerShell y systemd restantes.
5. Revisión de las pruebas (qué cubren y qué no) con `coverage.py`.
6. **Experimentos pendientes:**
   - Ablación regla a regla dentro del laboratorio (requiere su caché o regenerarla; gasta holdout: usar copia).
   - Cerebro con historia solo de Hyperliquid y por régimen (R-06 de la auditoría interna).
   - DSR y PBO (CSCV) sobre las variantes registradas en `laboratorio_variantes.json`.
   - Carry con funding horario de Hyperliquid 2023–2026 (`fundingHistory`) en lugar de Binance.
   - Backtest de ruptura_4h + régimen con historia de Hyperliquid (5 000 velas por moneda).
   - Investigación externa no hecha: vectorbt, LEAN, FreqAI, CCXT, rastreadores de ballenas de Hyperliquid, fuente
     directa de liquidaciones en Hyperliquid.

## Cómo reanudar
1. Copiar el repositorio a un directorio temporal y crear un venv con `requirements-bloqueado.txt`.
2. Releer `experimentos/hallazgos_borrador.md` (registro centralizado de hallazgos) y `01_inventario_y_cobertura.md`.
3. Seguir la lista «Pendiente» en orden; añadir hallazgos al borrador y consolidarlos en 03 y 14.

## Registro de comandos y experimentos

| # | Comando | Resultado |
|---|---|---|
| 1 | `python3 experimentos/inventario.py .` | 67 archivos propios, 22 486 líneas, 1 088 funciones (sin copias ni pruebas) |
| 2 | `python -m unittest discover -s tests -t .` (en la copia) | 764 OK en 64,7 s; pruebas con red real (T-09) |
| 3 | `python bot.py --validar-config` (copia) | Límites efectivos (05) |
| 4 | `ruff check …`, `bandit -ll`, `pip-audit -r requirements-bloqueado.txt` | Sin hallazgos graves; sin vulnerabilidades conocidas |
| 5 | `python3 -I experimentos/forense_ledger.py . …` | Coincide con las cifras declaradas; exceso frente a mercado +0,40 % (t 0,53) |
| 6 | `python3 -I experimentos/sesgo_sombras.py <copia> …` | Sesgo +0,123 R/op (t 7,7); +0,074 solo por muestreo |
| 7 | Descarga de `data.binance.vision` (2 800 archivos, 4 h + funding, 20 símbolos, 2021-01 → 2026-10) | 0 fallos |
| 8 | `python3 -I experimentos/backtest_independiente.py <copia> <datos> …` | Ver 04 y 09 |
| 9 | Búsquedas web (documentación de Hyperliquid, literatura, prensa, proyectos) | Ver 11 |
| 10 | `generar_propuestas.py`, `generar_indice_hallazgos.py`, `generar_plantilla_evaluacion.py` | 61 propuestas, 50 hallazgos, plantilla |
| 11 | Re-ejecución de los 3 experimentos sobre la copia | Resultados idénticos a los guardados |

## Entrega 2 (24/11/2026): paquete para revisión externa
- `CAMBIOS_PROPUESTOS.md` + `propuestas.json` (61 propuestas, ninguna aplicada), `INDICE_HALLAZGOS.md` (50 IDs),
  `PUNTOS_DEBILES_DE_ESTA_AUDITORIA.md`, `PROMPT_CODEX.md`, `plantilla_evaluacion_propuestas.json`.
- Corrección: el documento 12 decía «20 monedas archivadas» para la referencia de mercado; son las 72 monedas con
  velas de 1 h archivadas (las cifras no cambian: el script ya usaba las 72).
- Definidos 6 IDs citados sin definición (IA-04, S-04, V-01..V-04) en `experimentos/hallazgos_borrador.md`.
