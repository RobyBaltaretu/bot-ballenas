#!/usr/bin/env bash
# Actualiza SOLO el código del bot en el servidor. Conserva .env, config.json y todos los datos
# (estado, cuenta simulada, memoria, registro, datos de mercado y archivo).
# Uso (en el servidor, dentro de la carpeta con la versión NUEVA):   sudo bash despliegue/actualizar_vps.sh
set -euo pipefail
ORIGEN="$(cd "$(dirname "$0")/.." && pwd)"
# CP-M18 (auditoría 26/11, OPS-01): el servidor debe quedar con EXACTAMENTE el entorno probado
# (requirements-bloqueado.txt, dependencias indirectas incluidas), no con lo que resuelva pip ese día.
entorno_igual_al_bloqueado() {  # $1 = requirements-bloqueado.txt, $2 = pip del entorno
  local esperado actual
  esperado=$(tr -d '\r' < "$1" | grep -vE '^[[:space:]]*(#|$)' | tr 'A-Z_' 'a-z-' | sort)
  actual=$("$2" freeze 2>/dev/null | tr -d '\r' | tr 'A-Z_' 'a-z-' | sort)
  [ "$esperado" = "$actual" ]
}
DESTINO="${DESTINO:-/opt/bot-ballenas}"
USUARIO="${USUARIO:-botballenas}"
PRUEBA="${PRUEBA:-0}"
sistema() { if [ "$PRUEBA" = "1" ]; then echo "   (prueba) $*"; else "$@"; fi; }

[ -f "$DESTINO/bot.py" ] || { echo "No hay bot instalado en $DESTINO: usa despliegue/instalar_vps.sh"; exit 1; }
if [ "$PRUEBA" != "1" ] && [ "$(id -u)" -ne 0 ]; then echo "Ejecútalo con sudo."; exit 1; fi

echo ">> Parando el bot (apagado ordenado: conserva los stops)..."
sistema systemctl stop bot-ballenas bot-ballenas-panel bot-ballenas-carry bot-ballenas-agresiva || true

echo ">> Copiando solo el código..."
rsync -a --prune-empty-dirs \
  --exclude '.venv/' --exclude '__pycache__/' --exclude 'datos_*/' --exclude 'registro/' --exclude 'logs/' \
  --include '*/' --include '*.py' --include '*.html' --include '*.md' --include '*.txt' --include '*.sh' \
  --include '*.js' --include '*.css' --include '*.svg' \
  --include '*.service' --include '*.timer' --include '*.bat' --include '*.ps1' --include '.env.example' \
  --exclude '*' "$ORIGEN"/ "$DESTINO"/

echo ">> Dependencias..."
if [ "$PRUEBA" != "1" ]; then
  "$DESTINO/.venv/bin/pip" install -q -r "$DESTINO/requirements-bloqueado.txt"
  # Al actualizar no se para nada por esto (el bot tiene que seguir operando): se avisa para revisarlo.
  if ! entorno_igual_al_bloqueado "$DESTINO/requirements-bloqueado.txt" "$DESTINO/.venv/bin/pip"; then
    echo "   AVISO: el entorno del servidor no coincide con requirements-bloqueado.txt (pip freeze distinto)."
    echo "   Hay paquetes de más o con otra versión. Revísalo con: $DESTINO/.venv/bin/pip freeze"
  fi
fi
if [ "$PRUEBA" != "1" ]; then chown -R "$USUARIO:$USUARIO" "$DESTINO"; fi

echo ">> Comprobando (y si hace falta migrando, con copia de seguridad) la configuración..."
if [ "$PRUEBA" = "1" ]; then
  (cd "$DESTINO" && .venv/bin/python bot.py --validar-config)
else
  (cd "$DESTINO" && sudo -u "$USUARIO" .venv/bin/python bot.py --validar-config) || {
    echo "La configuración no es válida. El bot NO se ha arrancado. Corrige config.json y ejecuta:"
    echo "  sudo systemctl start bot-ballenas bot-ballenas-panel bot-ballenas-carry bot-ballenas-agresiva"; exit 1; }
fi

if [ "$PRUEBA" != "1" ]; then
  for u in "$DESTINO"/despliegue/bot-ballenas*.service "$DESTINO"/despliegue/bot-ballenas*.timer; do
    cp "$u" /etc/systemd/system/
  done
  systemctl daemon-reload
  systemctl enable bot-ballenas bot-ballenas-panel bot-ballenas-carry bot-ballenas-agresiva >/dev/null
  systemctl enable --now bot-ballenas-investigacion.timer bot-ballenas-laboratorio.timer bot-ballenas-recordatorio.timer bot-ballenas-copia.timer >/dev/null
fi
sistema systemctl start bot-ballenas bot-ballenas-panel bot-ballenas-carry bot-ballenas-agresiva
echo "Actualizado y en marcha. Ver lo que hace: journalctl -u bot-ballenas -f"
if [ "$PRUEBA" != "1" ]; then sleep 20; (cd "$DESTINO" && sudo -u "$USUARIO" .venv/bin/python comprobar.py) || true; fi
