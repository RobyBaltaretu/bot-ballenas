# Prompt para el desarrollador

Antes de pasárselo: fusiona la rama `claude/audit-algo-trading-bot-nua1pw` en `main` (o dile que trabaje desde esa rama)
para que tenga la carpeta `auditoria_independiente/`. Copia el texto entre las dos líneas `=====`.

=====

Vas a corregir errores y añadir mejoras al bot a partir de una auditoría independiente. Todo está en
`auditoria_independiente/`:
- `PLAN_DESARROLLO.md` (y `plan_desarrollo.json`): **las 48 tareas que tienes que hacer**, en 5 fases, cada una con
  dónde está, qué hay ahora, qué hacer, por qué, riesgo, si cambia la huella, criterio de «hecho» y dependencias.
- `03_auditoria_tecnica.md` e `INDICE_HALLAZGOS.md`: el detalle de cada hallazgo citado en las tareas.
- `experimentos/`: scripts que reproducen las mediciones (forense del ledger, sesgo de las sombras, backtest).

Regla principal del propietario: **el bot tiene que seguir operando**. Ninguna tarea puede impedir, pausar ni reducir
las entradas en simulado (no apagues estrategias, vías de exploración, ballenas ni la cartera de funding, no bajes el
riesgo ni endurezcas límites del simulado). Si al implementar algo ves que reduciría la operativa, no lo hagas así:
busca la forma que no la reduzca o déjalo sin hacer y explícalo. Las 13 propuestas de la sección «Excluidas» del plan
no se tocan.

Cómo trabajar:
1. Por fases y en orden (1 → 5). Dentro de cada fase, respeta las dependencias. Una rama por fase y un commit por
   tarea, con el ID en el mensaje (p. ej. `CP-M05: deslizamiento del stop con los fills del stop`).
2. Antes de cambiar nada, comprueba en el código que el problema sigue ahí tal como se describe (las líneas pueden
   haberse movido). Si no es así, no lo cambies y dilo.
3. Cada tarea con su prueba en `tests/` según su «Hecho cuando». La batería completa
   (`.venv\Scripts\python -m unittest discover -s tests -t .`) tiene que pasar al cerrar cada tarea.
4. Respeta `CLAUDE.md`: nada de modo real ni órdenes reales, no muestres secretos, todo `.py` nuevo clasificado en
   `promocion.ARCHIVOS_CODIGO` o en los «sin efecto», panel sin `innerHTML` ni estilos en línea, no borres datos.
5. Lo marcado «Acción de Roberto» (contraseña del panel, Telegram, Healthchecks, VPS, testnet) déjalo preparado y
   documentado paso a paso; los secretos los pone él. CP-M08 y CP-M09 solo afectan al modo real y se aplican con
   arranque manual (`INICIAR.bat`), nunca con `/aplicarconfig`.
6. Para aplicar cada fase en el bot en marcha usa el reinicio ordenado de siempre (`/aplicarconfig`). Casi todas las
   tareas cambian la huella de `promocion.py`: es esperado.
7. No hagas push a `main` ni fusiones: Roberto revisa cada fase antes de pasar a la siguiente.

Al terminar cada fase, entrega:
- tabla `ID → hecha / no hecha / hecha de otra forma`, con el commit y la prueba de cada una (y el motivo si no);
- resultado de la batería de pruebas;
- qué cambia en el comportamiento del bot, confirmando que sigue abriendo operaciones igual que antes;
- `CLAUDE.md` actualizado con los cambios de la fase.

Empieza por la fase 1.

=====
