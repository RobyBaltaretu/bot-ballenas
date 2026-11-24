# Lo que depende de ti (21/11/2026)

Lo que podía hacer sin ti ya está hecho (ver el final). Esto solo lo puedes hacer o decidir tú. Va por orden de importancia.

## A. Migración a Hetzner (sigue `despliegue/GUIA_HETZNER.md`)

1. **Crear la cuenta y el servidor**: 4 vCPU x86, 8 GB de RAM, Ubuntu 24.04, en Alemania o Finlandia, con IPv4,
   **Backups** y un firewall que solo deje entrar por SSH (paso 0–2).
2. **Crear tu clave SSH** en el PC (paso 1). Es tuya y no la debe ver nadie.
3. **Parar el bot del PC y empaquetar**: `herramientas\parar-para-migrar.bat` y `herramientas\preparar-migracion.bat`.
4. **Instalar y escribir las claves en el servidor** cuando el instalador las pida (no se ven al escribir):
   - `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`: sin ellos no te llega ningún aviso fuera del panel.
   - `PANEL_PASSWORD`: **ponla**. Hoy el panel se ve por el túnel sin contraseña.
   - `HEALTHCHECK_URL`: crea el aviso en healthchecks.io (paso 6).
5. **Pasar las pruebas en el servidor antes de arrancar** (paso 5). Es la primera vez que el bot corre en Linux.
   Si no sale `OK`, no arranques y pásame el final.
6. **Mover el túnel de Cloudflare** al servidor y quitarlo del PC (paso 7).
7. Opcional: copia fuera de Hetzner en Cloudflare R2 (crear el cubo y el token).

Si prefieres no migrar todavía, lo mínimo en el PC: pon `PANEL_PASSWORD` y las dos claves de Telegram en el `.env`.

## B. Decisiones sobre cómo opera

1. **Exploración de estrategias negativas.** Hoy la exploración opera también lo que el laboratorio da por claramente
   negativo (`ruptura_1h` va −0,39 R en 144 casos; `retroceso_4h` 3 de 3 perdidas). Aprende más, pero cuesta dinero
   simulado y ensucia el resultado. ¿Las sigo explorando o pongo un listón mínimo?
   **En parte decidido (23/11):** apagadas `retroceso_1h`, `retroceso_4h`, `funding_4h` y `reversion_4h` (siguen en
   sombra). Todo lo que se descarta se ve en el panel → Más → «Sónar de sombras».
2. **Límites del primer real.** El piloto real está hoy igual que el simulado: puede perder hasta la mitad del
   capital (116 $), todos los mercados (memecoins incluidas) y apalancamiento hasta 5×. Te recomiendo, para empezar,
   bastante menos: pérdida máxima ~20 %, solo BTC/ETH/SOL/HYPE y 2–3×. Ninguna estrategia ha superado aún el
   laboratorio, así que hoy no hay nada promovible a real.
3. **`retroceso_1h`: decidido, apagada (23/11).** El laboratorio la da negativa (~700 casos, −0,09 R). Sigue en
   sombra (+0,48 R en 27 casos al apagarla); si pasa de 50 casos en positivo, se estudia aparte.

4. **Techos duros del dinero real (22/11): decidido.** Roberto prefiere mantener los nuestros (3 % por operación, 9 %
   abierto, 5×), no los de HyperGrok (2 % / 6 %). Quedan fijados así en `riesgo.TECHOS_REAL`.

## C. Más adelante

- **Calibrar el simulador con real**: unas pocas operaciones reales muy pequeñas para medir deslizamiento y llenados.
  Solo cuando haya algo validado y con tu aprobación expresa.
- **Auditoría de dependencias** (`pip-audit`): hay que instalar la herramienta. Puedo hacerlo en el servidor nuevo si me
  lo autorizas.

## Hecho hoy sin ti (para que lo sepas)

- **Resultado por vía de decisión**: Operaciones → «Por vía» (cerebro, cerebro en exploración, exploración amplia,
  cartera, memoria), cada una por estrategia. Hoy: cerebro en exploración +34,02 $ (15 cerradas, t 1,67);
  sin cerebro −4,77 $ (7); exploración amplia +3,52 $ (2). Nada es concluyente todavía.
- **Predicción del cerebro** en la ficha de cada operación.
- **Fallo arreglado**: una ampliación descartada borraba la decisión de entrada de la operación (caso ZEC del 19/11).
- **Arranque rápido**: el funding histórico se guarda en disco; el bot ya no se frena 10–15 min tras cada reinicio.
- **Stops con el bot parado**: si el bot se cae, al volver la cuenta simulada aplica los stops y objetivos que el
  precio tocó mientras tanto.
- **Dos fallos que dependían del reloj** (salieron al probar con la versión de Python del servidor): al rotar el
  registro se podían perder eventos, y la conciliación podía duplicar el objetivo final tras un ajuste manual.
- **Preparación de Hetzner**: guía, script para parar todo en el PC, instalador ajustado (sin el recordatorio de
  Oracle, exige Python 3.12+, reinicio automático a las 07:30 para no cortar el laboratorio).
- `bot.log` ya rotaba (5 MB × 3): la auditoría se equivocó en ese punto.
- 734 pruebas, todas bien con Python 3.12 y 3.14. Bot y panel reiniciados y sanos.
