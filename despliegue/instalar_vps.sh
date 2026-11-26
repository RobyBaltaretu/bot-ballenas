#!/usr/bin/env bash
# Instala el bot como servicio en un servidor Linux (Oracle Cloud ARM, Hetzner...) con Ubuntu 24.04 o más nuevo (Python 3.12+).
#
# Uso (en el servidor, dentro de la carpeta del bot que has subido):
#     sudo bash despliegue/instalar_vps.sh
#
# Qué hace:
#   - Instala Python y lo necesario, activa las actualizaciones de seguridad automáticas (con reinicio, si hace falta,
#     a las 07:30 hora de Madrid) y un cortafuegos que solo deja entrar por SSH. El panel NO se abre a internet.
#   - Crea un usuario sin privilegios para el bot y copia el bot (con sus datos, si vienen en el paquete de
#     migración) a /opt/bot-ballenas. Nunca copia un .env: las claves se piden aquí y solo las ve este servidor.
#   - Deja el bot y el panel como servicios que arrancan solos al encender y se reinician si fallan, y programa:
#     copia diaria a Cloudflare R2 (si la configuras), laboratorio semanal y (solo en Oracle) un recordatorio mensual.
# Si /opt/bot-ballenas ya existe, no toca nada: para actualizar usa despliegue/actualizar_vps.sh.
set -euo pipefail

DESTINO="${DESTINO:-/opt/bot-ballenas}"
USUARIO="${USUARIO:-botballenas}"
PRUEBA="${PRUEBA:-0}"            # PRUEBA=1: solo copia y prepara (sin apt, systemd ni usuarios). Para tests.
ORIGEN="$(cd "$(dirname "$0")/.." && pwd)"
# Proveedor: se detecta Oracle por su metadato; en cualquier otro (Hetzner...) no hay recordatorio mensual.
if [ -z "${PROVEEDOR:-}" ]; then
  if grep -qi "oracle" /sys/class/dmi/id/chassis_asset_tag /sys/class/dmi/id/sys_vendor 2>/dev/null; then PROVEEDOR=oracle
  else PROVEEDOR=otro; fi
fi

paso() { echo; echo ">> $*"; }
# CP-M18 (auditoría 26/11, OPS-01): el servidor debe quedar con EXACTAMENTE el entorno probado
# (requirements-bloqueado.txt, dependencias indirectas incluidas), no con lo que resuelva pip ese día.
entorno_igual_al_bloqueado() {  # $1 = requirements-bloqueado.txt, $2 = pip del entorno
  local esperado actual
  esperado=$(tr -d '\r' < "$1" | grep -vE '^[[:space:]]*(#|$)' | tr 'A-Z_' 'a-z-' | sort)
  actual=$("$2" freeze 2>/dev/null | tr -d '\r' | tr 'A-Z_' 'a-z-' | sort)
  [ "$esperado" = "$actual" ]
}
sistema() { if [ "$PRUEBA" = "1" ]; then echo "   (prueba) $*"; else "$@"; fi; }

if [ "$PRUEBA" != "1" ] && [ "$(id -u)" -ne 0 ]; then
  echo "Ejecútalo con sudo:  sudo bash despliegue/instalar_vps.sh"; exit 1
fi
if [ -f "$DESTINO/bot.py" ]; then
  echo "Ya hay un bot instalado en $DESTINO. Para actualizarlo usa:  sudo bash despliegue/actualizar_vps.sh"; exit 1
fi

# ------------------------------------------------------------------ sistema
paso "Instalando Python y utilidades (unos minutos)..."
sistema apt-get update -qq
sistema env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pip python3-dev \
  build-essential unattended-upgrades ufw rsync rclone tar curl ca-certificates

paso "Actualizaciones de seguridad automáticas (reinicio, si hace falta, a las 07:30 hora de Madrid: después del laboratorio de los domingos)..."
if [ "$PRUEBA" != "1" ]; then
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
  cat > /etc/apt/apt.conf.d/52bot-ballenas <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "07:30";
EOF
fi

paso "Cortafuegos: solo SSH (el panel se ve por el túnel de Cloudflare, nunca con un puerto abierto)..."
sistema ufw allow OpenSSH
sistema ufw --force enable

paso "Límite de tamaño de los registros del sistema..."
if [ "$PRUEBA" != "1" ]; then
  mkdir -p /etc/systemd/journald.conf.d
  printf '[Journal]\nSystemMaxUse=300M\n' > /etc/systemd/journald.conf.d/bot-ballenas.conf
  systemctl restart systemd-journald || true
fi

# Memoria de intercambio: el laboratorio tiene picos de memoria; con 2 GB de RAM conviene tener 2 GB de swap.
if [ "$PRUEBA" != "1" ] && [ "$(swapon --show --noheadings | wc -l)" -eq 0 ]; then
  ram_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
  if [ "$ram_mb" -lt 4096 ]; then
    paso "Creando 2 GB de memoria de intercambio (swap)..."
    fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  fi
fi

paso "Usuario sin privilegios '$USUARIO'..."
if [ "$PRUEBA" != "1" ]; then
  id -u "$USUARIO" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$USUARIO"
fi

# ------------------------------------------------------------------ bot y datos
paso "Copiando el bot a $DESTINO (con los datos del paquete de migración, si los trae; nunca .env)..."
mkdir -p "$DESTINO"
rsync -a --exclude '.env' --exclude '.venv' --exclude '__pycache__' --exclude '.ruff_cache' --exclude 'datos_backtest' \
      --exclude '*.lock' --exclude '*.tmp' "$ORIGEN"/ "$DESTINO"/
if [ -f "$ORIGEN/.env" ]; then
  echo "   AVISO: en la carpeta subida hay un .env. No se ha copiado: las claves se configuran ahora."
fi

paso "Claves y avisos (.env). Deja en blanco lo que no uses y pulsa Enter."
python3 - "$DESTINO" <<'PYEOF'
import getpass, os, re, sys
destino = sys.argv[1]
ruta = os.path.join(destino, ".env")
base = open(os.path.join(destino, ".env.example"), encoding="utf-8").read()
interactivo = sys.stdin.isatty() or os.path.exists("/dev/tty")
try:
    tty = open("/dev/tty", "r+") if interactivo else None
except OSError:
    tty = None

def preguntar(texto, secreto=False):
    if tty is None:
        return ""
    tty.write(texto); tty.flush()
    if secreto:
        return getpass.getpass("", stream=tty).strip()
    return tty.readline().strip()

valores = {
    "TELEGRAM_TOKEN": preguntar("  Token del bot de Telegram (no se muestra al escribir): ", True),
    "TELEGRAM_CHAT_ID": preguntar("  Tu chat_id de Telegram: "),
    "HEALTHCHECK_URL": preguntar("  URL de ping de Healthchecks.io (https://hc-ping.com/...): ", True),
    "PANEL_PASSWORD": preguntar("  Contraseña del panel (RECOMENDADA: sin ella, con tunel_sin_clave en config.json, el panel se ve por el túnel sin clave): ", True),
}
for k, v in valores.items():
    if "\n" in v or "\r" in v:
        sys.exit(f"Valor no válido para {k}")
    base = re.sub(rf"(?m)^{k}=.*$", lambda m: f"{k}={v}", base)
fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as fh:
    fh.write(base)
print("   .env creado (solo lo puede leer el usuario del bot).")
PYEOF

# El bot está probado con Python 3.12 (Ubuntu 24.04) y 3.14 (el del PC). Con uno más antiguo no se instala.
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
  echo "Este sistema trae Python $(python3 -V 2>&1 | cut -d' ' -f2) y el bot necesita 3.12 o más nuevo."
  echo "Crea el servidor con Ubuntu 24.04 (o más nuevo) y vuelve a empezar."; exit 1
fi
paso "Entorno de Python y dependencias (en ARM puede tardar unos minutos)..."
if [ "$PRUEBA" = "1" ]; then
  python3 -m venv --system-site-packages "$DESTINO/.venv"      # pruebas: sin descargar dependencias
else
  python3 -m venv "$DESTINO/.venv"
  "$DESTINO/.venv/bin/pip" install -q --upgrade pip
  "$DESTINO/.venv/bin/pip" install -q -r "$DESTINO/requirements-bloqueado.txt"
  if ! entorno_igual_al_bloqueado "$DESTINO/requirements-bloqueado.txt" "$DESTINO/.venv/bin/pip"; then
    echo "   ERROR: las dependencias instaladas no coinciden con requirements-bloqueado.txt (pip freeze distinto)."
    echo "   No sigo: el bot solo se arranca con el entorno probado. Revisa la salida de pip y vuelve a lanzarlo."
    exit 1
  fi
fi

if [ ! -f "$DESTINO/config.json" ]; then
  echo "   AVISO: no hay config.json en el paquete. Copia el de tu PC antes de arrancar (ver la guía)."
fi
if [ "$PRUEBA" != "1" ]; then
  chown -R "$USUARIO:$USUARIO" "$DESTINO"
  chmod 600 "$DESTINO/.env"
fi

paso "Comprobando la configuración (no conecta ni opera)..."
if [ -f "$DESTINO/config.json" ]; then
  if [ "$PRUEBA" = "1" ]; then
    (cd "$DESTINO" && .venv/bin/python bot.py --validar-config) || { echo "La configuración no es válida: corrígela antes de arrancar."; exit 1; }
  else
    (cd "$DESTINO" && sudo -u "$USUARIO" .venv/bin/python bot.py --validar-config) || { echo "La configuración no es válida: corrígela antes de arrancar."; exit 1; }
  fi
fi

# ------------------------------------------------------------------ servicios y tareas programadas
paso "Servicios: bot, panel, copia diaria, investigación nocturna, laboratorio semanal y recordatorio mensual..."
# Hora de España: la agenda del bot (laboratorio domingos 04:00, investigación 02:30) y los informes van en hora local.
if [ "$PRUEBA" != "1" ]; then timedatectl set-timezone Europe/Madrid || true; fi
# Carpeta de solicitudes: el bot deja aquí un archivo y systemd lanza el laboratorio/investigación en su servicio.
mkdir -p "$DESTINO/solicitudes"
[ "$PRUEBA" = "1" ] || chown "$USUARIO" "$DESTINO/solicitudes"
if [ "$PRUEBA" != "1" ]; then
  for u in bot-ballenas.service bot-ballenas-panel.service bot-ballenas-carry.service bot-ballenas-agresiva.service \
           bot-ballenas-copia.service bot-ballenas-copia.timer \
           bot-ballenas-laboratorio.service bot-ballenas-laboratorio.timer \
           bot-ballenas-investigacion.service bot-ballenas-investigacion.timer \
           bot-ballenas-laboratorio.path bot-ballenas-investigacion.path; do
    cp "$DESTINO/despliegue/$u" "/etc/systemd/system/$u"
  done
  # El recordatorio mensual solo tiene sentido en Oracle (suspende cuentas gratuitas sin actividad). En Hetzner u
  # otro proveedor de pago no se instala.
  if [ "$PROVEEDOR" = "oracle" ]; then
    cp "$DESTINO/despliegue/bot-ballenas-recordatorio.service" "$DESTINO/despliegue/bot-ballenas-recordatorio.timer" /etc/systemd/system/
  fi
  systemctl daemon-reload
  systemctl enable bot-ballenas bot-ballenas-panel bot-ballenas-carry bot-ballenas-agresiva >/dev/null
  systemctl enable --now bot-ballenas-investigacion.timer bot-ballenas-laboratorio.timer bot-ballenas-copia.timer >/dev/null
  systemctl enable --now bot-ballenas-laboratorio.path bot-ballenas-investigacion.path >/dev/null
  if [ "$PROVEEDOR" = "oracle" ]; then systemctl enable --now bot-ballenas-recordatorio.timer >/dev/null; fi
fi

echo
echo "================================================================"
echo " Instalación terminada."
echo "  1) Copias diarias a Cloudflare R2:   sudo bash $DESTINO/despliegue/configurar_copias.sh"
echo "  2) Panel por Cloudflare Tunnel:      sudo bash $DESTINO/despliegue/cloudflare_linux.sh"
echo "  3) Arrancar el bot y el panel:       sudo systemctl start bot-ballenas bot-ballenas-panel bot-ballenas-carry bot-ballenas-agresiva"
echo "  4) Ver lo que hace:                  journalctl -u bot-ballenas -f      (Ctrl+C para salir)"
echo "  5) Comprobar el despliegue:          cd $DESTINO && sudo -u $USUARIO .venv/bin/python comprobar.py"
echo " IMPORTANTE: antes de arrancarlo aquí, para el bot de tu PC. Nunca deben funcionar los dos a la vez."
echo "================================================================"
