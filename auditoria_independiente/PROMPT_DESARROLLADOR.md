# Entrega al desarrollador

## Antes de dárselo (lo hace Roberto)

1. **Esperar la evaluación de Codex** (`auditoria_codex/fase_b/evaluacion_propuestas.json`). Se aplica lo que ambos
   aceptan; lo que Codex rechace o cambie, se decide caso a caso.
2. **Fusionar la rama `claude/audit-algo-trading-bot-nua1pw` (y la de Codex) en `main`**, para que el desarrollador
   tenga los archivos en la carpeta donde trabaja.
3. **Decidir las propuestas que son decisión de negocio** (en `CAMBIOS_PROPUESTOS.md` llevan «Decide: propietario»).
   Marca cada una con SÍ / NO / MÁS ADELANTE en la tabla de abajo; el desarrollador no las tocará sin esa marca.

| ID | Decisión | SÍ / NO / MÁS ADELANTE |
|---|---|---|
| CP-E01 | Apagar momentum_4h | |
| CP-E02 | Quitar la exploración amplia | |
| CP-E03 | Quitar la exploración del cerebro en simulado | |
| CP-E06 | Quitar la piramidación | |
| CP-E07 | Quitar ballenas como señal y veto | |
| CP-E08 | Quitar el seguimiento de ballenas del bot | |
| CP-E11 | Quitar el escéptico y el revisor de IA | |
| CP-E12 | Quitar el factor «objetivo diario» | |
| CP-E14 | Quitar el túnel sin contraseña (tras poner PANEL_PASSWORD) | |
| CP-E15 | Apagar la cartera de funding | |
| CP-E16 | Simplificar las vistas decorativas del panel | |
| CP-M07 | Riesgo simulado 1 % / 3 % | |
| CP-M08 | Límites del piloto real 1 % / 3 % / 3 / 2× / −20 % / BTC-ETH-SOL | |
| CP-M09 | Techos duros del real más bajos | |
| CP-M10 | Suelo de emergencia −20 % | |
| CP-M11 | Exposición neta y beta ≤ 100 % | |
| CP-A05 | Prerregistrar ruptura_4h + régimen | |
| CP-A10 | Campaña en testnet | |
| CP-A11 / A16 | Alertas y contraseña del panel (los secretos los pone Roberto) | |
| CP-A12 | Migración al VPS | |
| CP-V01 | Seguir el prerregistro de fuerza_4h | |

## Prompt para el desarrollador (copiar desde la línea `=====`)

=====

Vas a aplicar las correcciones de dos auditorías externas del bot. Todo está en el repositorio:
- `auditoria_independiente/CAMBIOS_PROPUESTOS.md` y `propuestas.json`: 61 propuestas con ID `CP-…`, dónde, qué
  cambiar, evidencia, criterio de aceptación y dependencias.
- `auditoria_codex/fase_b/evaluacion_propuestas.json`: la evaluación de cada propuesta por Codex.
- `auditoria_independiente/PROMPT_DESARROLLADOR.md`: la tabla de decisiones de Roberto.

Qué aplicar:
1. Una propuesta se aplica solo si Codex la marca `ACEPTAR` o `ACEPTAR_CON_CAMBIOS` (en ese caso, con sus cambios) y,
   si es «Decide: propietario», Roberto la ha marcado SÍ. Las marcadas `RECHAZAR`, `NO_VERIFICABLE`, NO o MÁS
   ADELANTE no se tocan; lístalas al final con su motivo.
2. Antes de cambiar nada, comprueba en el código que el diagnóstico sigue siendo cierto (las líneas pueden haberse
   movido). Si no lo es, no lo apliques y dilo.

Cómo trabajar:
- Por fases, en el orden de `CAMBIOS_PROPUESTOS.md` («Orden de aplicación recomendado»): fase 0, luego 1, luego 2.
  Una rama y un commit por propuesta (mensaje con su ID), y una rama por fase. No pases a la siguiente fase sin que
  Roberto revise la anterior.
- Cada propuesta con su prueba, según su criterio de aceptación. La batería completa
  (`.venv\Scripts\python -m unittest discover -s tests -t .`) debe pasar al cerrar cada propuesta.
- Respeta `CLAUDE.md`: nada de modo real, ni órdenes reales, ni secretos; todo `.py` nuevo clasificado en
  `promocion.py`; panel sin `innerHTML` ni estilos en línea.
- Los cambios de `piloto_real` y de `TECHOS_REAL` solo se aplican con arranque manual (`INICIAR.bat`), nunca con
  `/aplicarconfig`.
- No borres código de estrategias ni datos: lo que se elimina de la operativa se desactiva y queda documentado en el
  cementerio de investigación.
- Casi todo cambia la huella de `promocion.py` y reinicia la evidencia: es esperado. Al terminar la fase 0, propón a
  Roberto una puesta a cero de la cuenta simulada (`reiniciar_simulado.json`) para empezar evidencia limpia.

Al terminar cada fase, entrega:
- tabla `ID → aplicada / no aplicada / modificada`, con el commit y la prueba de cada una;
- resultado de la batería de pruebas;
- qué cambió en el comportamiento del bot (qué deja de operar, qué límites cambian);
- actualización de `CLAUDE.md` con los cambios de la fase.

=====
