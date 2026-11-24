# Pasar el bot a Hetzner (24/7, sin depender del PC)

Al terminar tendrás:
- El bot, el panel y el carry funcionando día y noche en un servidor de Hetzner en Europa.
- El panel en tu dirección de Cloudflare, con contraseña.
- El laboratorio semanal y la investigación nocturna, automáticos (hora de Madrid).
- Avisos por Telegram, un aviso si el servidor se cae (Healthchecks) y copias de seguridad.

Tiempo: 1–2 horas la primera vez. **Las claves solo las escribes tú, en el servidor; nunca salen de él.**
El bot sigue en **SIMULADO**: la migración no cambia el modo, ni los límites, ni nada de real.

---

## 0. Qué servidor contratar

| Campo | Valor |
|---|---|
| Tipo | **Shared vCPU, x86 (Intel/AMD)**, **4 vCPU y 8 GB de RAM** (unos 80 GB de disco) |
| Ubicación | **Alemania** (Núremberg o Falkenstein) o **Finlandia** (Helsinki). Nada fuera de Europa |
| Imagen | **Ubuntu 24.04** (o una más nueva) |
| Red | **IPv4 pública** activada (además de IPv6) |
| Copias | **Backups** activado (copia diaria del disco entero, unos € más al mes) |

Por qué así:
- El bot usa ~150 MB, el panel ~160 MB y el carry poco. El que pide memoria es el **laboratorio de los domingos**
  (su servicio admite hasta 6 GB). Con 4 GB puede quedarse corto; con 8 GB va holgado.
- **x86 mejor que ARM**: todas las dependencias tienen paquetes listos y es el mismo tipo de procesador que tu PC.
- El bot está probado con **Python 3.12** (el de Ubuntu 24.04) y 3.14 (el de tu PC): las 734 pruebas pasan con los dos.
- Comprueba el precio actual en la web de Hetzner antes de contratar.

## 1. Cuenta y clave SSH (en tu PC)

1. Crea la cuenta en Hetzner (piden verificar identidad y un método de pago).
2. En tu PC abre **PowerShell** y crea una clave para entrar al servidor (sin contraseña de root, más seguro):
   ```
   ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\hetzner_bot"
   ```
   Te pide una frase de paso: pon una (o Enter para ninguna). Guarda la clave **fuera** de la carpeta del bot
   (así nunca acaba en un paquete): con ese comando ya queda en `C:\Users\rober\.ssh\`.
3. Copia la parte pública (la que se puede compartir):
   ```
   Get-Content "$env:USERPROFILE\.ssh\hetzner_bot.pub"
   ```

## 2. Crear el servidor (en la consola de Hetzner)

1. **Create Server** con los valores del paso 0.
2. En **SSH keys**, **Add SSH key** y pega la línea del paso 1.3.
3. En **Firewalls**, crea uno: **entrada solo TCP 22 (SSH)**; salida, todo. No abras el 8080: el panel se ve
   por el túnel de Cloudflare, nunca con un puerto abierto.
4. Nombre: `bot-ballenas`. **Create & Buy**. Copia la **IP pública (IPv4)**.

Prueba que entras (la primera vez escribe `yes`):
```
ssh -i "$env:USERPROFILE\.ssh\hetzner_bot" root@IP_DEL_SERVIDOR
```
Para salir: `exit`.

## 3. Parar el bot en el PC y empaquetar

Desde aquí el bot estará parado hasta el paso 7 (unos 30–60 min). En simulado no pasa nada: al arrancar en el
servidor, la cuenta simulada repasa las velas reales de 1 minuto del hueco y ejecuta los stops y objetivos que se
habrían tocado mientras tanto (en orden, marcados como estimados).

1. Doble clic en `herramientas\parar-para-migrar.bat`. Te pide cerrar la ventana del bot si sigue abierta, para el
   panel y el carry que queden sueltos y quita el arranque automático y las tareas programadas del PC.
   **Nunca deben funcionar dos bots a la vez.**
2. Doble clic en `herramientas\preparar-migracion.bat`. Crea `bot-migracion.tar.gz` en el Escritorio con el código,
   tu `config.json` y los datos (cuenta simulada, registro, memoria, mercado, archivo). **No incluye tu `.env`** ni
   `datos_backtest` (es una caché de ~530 MB que el laboratorio vuelve a bajar).
3. Súbelo (el `.bat` te muestra la ruta exacta del archivo):
   ```
   scp -i "$env:USERPROFILE\.ssh\hetzner_bot" "$env:USERPROFILE\Desktop\bot-migracion.tar.gz" root@IP_DEL_SERVIDOR:/root/
   ```

## 4. Instalar (en el servidor)

```
ssh -i "$env:USERPROFILE\.ssh\hetzner_bot" root@IP_DEL_SERVIDOR
tar -xzf bot-migracion.tar.gz
cd bot-ballenas
bash despliegue/instalar_vps.sh
```

El instalador:
- Instala Python, las actualizaciones de seguridad automáticas (si hace falta reiniciar, lo hace a las **07:30 hora de
  Madrid**, después del laboratorio de los domingos) y un cortafuegos interno que solo deja entrar por SSH.
- Crea el usuario `botballenas` sin privilegios y copia todo a `/opt/bot-ballenas`.
- Pone la hora de Madrid (la agenda del laboratorio y la investigación va en hora local).
- Te pregunta las claves (no se ven al escribir; se guardan en `/opt/bot-ballenas/.env`, que solo lee el bot):
  - **Token de Telegram** y **chat_id**.
  - **URL de Healthchecks** (si aún no la tienes, deja en blanco; paso 6).
  - **Contraseña del panel**: ponla. Con ella, el panel por el túnel pide contraseña aunque `config.json` tenga
    `tunel_sin_clave`.
- Deja preparados los servicios: bot, panel, carry, laboratorio, investigación y copia diaria. No arranca nada aún.

## 5. Probar el bot en el servidor antes de arrancarlo

Es la primera vez que el bot corre en Linux: antes de arrancar, pasa las pruebas allí.
```
cd /opt/bot-ballenas
sudo -u botballenas .venv/bin/python -m unittest discover -s tests -t . 2>&1 | tail -3
```
Debe terminar en `OK`. Si sale `FAILED`, **no arranques**: copia el final y pásamelo.

## 6. Avisos y copias

**Healthchecks** (aviso si el bot o el servidor se caen): cuenta gratis en healthchecks.io → **Add Check**
(Period 10 min, Grace 10 min) → integración con Telegram → copia la *Ping URL* y ponla en el servidor:
```
sudo nano /opt/bot-ballenas/.env        # HEALTHCHECK_URL=https://hc-ping.com/...   (Ctrl+O, Enter, Ctrl+X)
```

**Copias**: con **Backups** de Hetzner ya tienes una copia diaria del disco entero. Opcionalmente, una copia de los
datos del bot fuera de Hetzner (Cloudflare R2, gratis hasta 10 GB): crea el cubo `bot-ballenas-copias` y un token
de R2 con permiso solo sobre ese cubo, y en el servidor:
```
sudo bash /opt/bot-ballenas/despliegue/configurar_copias.sh
```

## 7. Panel por Cloudflare y arranque

1. En Cloudflare **Zero Trust → Networks → Tunnels**, abre el túnel que usa hoy tu PC → **Configure** → en
   *Install and run connectors* elige **Debian** y **64-bit (amd64)** y copia el comando (lleva un texto que empieza
   por `eyJ`). En el servidor:
   ```
   sudo bash /opt/bot-ballenas/despliegue/cloudflare_linux.sh
   ```
   La ruta pública debe seguir apuntando a `http://localhost:8080`.
2. Arranca todo:
   ```
   sudo systemctl start bot-ballenas bot-ballenas-panel bot-ballenas-carry
   journalctl -u bot-ballenas -f          # Ctrl+C para dejar de mirar (el bot sigue)
   ```
   Te llegará «🤖 Bot en marcha» por Telegram.
3. Comprueba el despliegue:
   ```
   cd /opt/bot-ballenas && sudo -u botballenas .venv/bin/python comprobar.py
   ```
4. En tu PC, doble clic en `herramientas\desconectar-cloudflare.bat` (si no, Cloudflare repartiría las visitas entre
   el PC y el servidor). Abre tu dirección del panel: debe pedir la contraseña y mostrar el saldo de siempre.
5. Cuando todo funcione: en `config.json` del servidor, `"tunel_sin_clave": false` (o borra la línea) y
   `sudo systemctl restart bot-ballenas-panel`.

## 8. La primera semana

- El domingo, comprueba que el laboratorio terminó: `journalctl -u bot-ballenas-laboratorio -n 30`.
- La primera vez tarda más (vuelve a bajar `datos_backtest`).
- Mira la memoria del servidor en la consola de Hetzner (Graphs) durante el laboratorio.

## Uso diario

| Para… | Comando (en el servidor) |
|---|---|
| Ver lo que hace | `journalctl -u bot-ballenas -f` |
| Parar / arrancar / reiniciar | `sudo systemctl stop/start/restart bot-ballenas` |
| Tareas programadas | `systemctl list-timers 'bot-ballenas*'` |
| Comprobar el despliegue | `cd /opt/bot-ballenas && sudo -u botballenas .venv/bin/python comprobar.py` |
| Panel sin Cloudflare (desde tu PC) | `ssh -i "$env:USERPROFILE\.ssh\hetzner_bot" -L 8080:localhost:8080 root@IP` y abre http://localhost:8080 |

**Actualizar el código:** en el PC, `herramientas\preparar-actualizacion.bat` (solo código: sin `.env`, sin
`config.json`, sin datos), súbelo con `scp` como en el paso 3 y en el servidor:
`tar -xzf bot-actualizacion.tar.gz && cd bot-ballenas && sudo bash despliegue/actualizar_vps.sh`.
**Nunca subas la carpeta del PC entera** (llevaría tu `.env`).

**Volver al PC** (si algún día hiciera falta): `sudo systemctl stop bot-ballenas bot-ballenas-panel bot-ballenas-carry`
en el servidor, trae los datos con `scp` y abre `INICIAR.bat`. Nunca los dos a la vez.

## Seguridad

- Al servidor solo se entra con tu clave SSH. No la compartas ni la pongas en la carpeta del bot.
- El firewall de Hetzner y el del servidor solo dejan pasar SSH. El panel escucha en `127.0.0.1` y se ve por el túnel
  cifrado de Cloudflare, con contraseña.
- `.env` solo lo puede leer el usuario del bot y nunca va en paquetes ni copias.
- En simulado no hacen falta claves de Hyperliquid. Pasar a real exige `promocion.py` y tu aprobación expresa.
