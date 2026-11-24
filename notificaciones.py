"""
Avisos y control del bot por Telegram.

Configuración (una vez):
  1. En Telegram, habla con @BotFather -> /newbot -> copia el token.
  2. Pon el token en .env:   TELEGRAM_TOKEN=123456:ABC...
  3. Escribe cualquier cosa a tu bot nuevo desde tu móvil.
  4. Ejecuta:  python notificaciones.py   -> te muestra tu chat_id.
  5. Ponlo en .env:          TELEGRAM_CHAT_ID=123456789

Comandos que entiende el bot (solo desde tu chat):
  /estado      saldo, posiciones abiertas y situación
  /pausa       deja de abrir operaciones (gestiona las abiertas)
  /reanudar    vuelve a abrir operaciones
  /cerrartodo  cierra todas las posiciones y se pausa
  /informe     resumen de lo aprendido
  /ayuda       esta lista
"""

import hashlib
import os
import queue
import re
import threading
import time
from datetime import datetime

import requests

API = "https://api.telegram.org/bot{token}/{metodo}"
# Severidades que NUNCA se silencian (aunque sea horario de silencio): un aviso o un error del bot (stop sin
# confirmar, liquidación cerca, bloqueo...) y la respuesta a un comando que acabas de mandar.
NUNCA_SILENCIAR = ("aviso", "error", "respuesta")


class ControlRuido:
    """Menos ruido en Telegram sin perder lo importante (17/11/2026, idea de daily_stock_analysis, corregida):
      - Duplicados: el MISMO texto no se repite dentro de 'dedup_min' minutos (salvo respuestas a comandos).
      - Horas de silencio 'HH:MM-HH:MM' (hora de 'zona'; admite cruzar medianoche; vacío = sin silencio): solo
        callan los avisos informativos. Avisos, errores y respuestas pasan SIEMPRE (el original silenciaba también
        lo crítico).
    Estado en memoria: un reinicio olvida los duplicados (como mucho, un aviso repetido)."""
    PATRON = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")

    def __init__(self, dedup_min=10, silencio="", zona=None):
        self.dedup_s = max(0, float(dedup_min or 0)) * 60
        self.zona = zona
        self.silencio = None
        m = self.PATRON.match((silencio or "").strip())
        if m:
            a, b = int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])
            self.silencio = (a, b) if a != b else None
        self.vistos = {}
        self.lock = threading.Lock()

    def _minuto_local(self, ahora):
        try:
            from zoneinfo import ZoneInfo
            d = datetime.fromtimestamp(ahora, ZoneInfo(self.zona)) if self.zona else datetime.fromtimestamp(ahora)
        except Exception:  # noqa: BLE001  (sin base de zonas horarias: hora local del equipo)
            d = datetime.fromtimestamp(ahora)
        return d.hour * 60 + d.minute

    def en_silencio(self, ahora=None):
        if not self.silencio:
            return False
        m, (a, b) = self._minuto_local(ahora or time.time()), self.silencio
        return a <= m < b if a < b else (m >= a or m < b)

    def permitir(self, texto, severidad="info", ahora=None):
        """True si el aviso debe enviarse (y lo apunta como enviado)."""
        ahora = ahora or time.time()
        if severidad == "respuesta":
            return True
        if severidad not in NUNCA_SILENCIAR and self.en_silencio(ahora):
            return False
        if self.dedup_s:
            clave = hashlib.sha256(texto.encode("utf-8", "replace")).hexdigest()
            with self.lock:
                for k in [k for k, t in self.vistos.items() if ahora - t >= self.dedup_s]:
                    del self.vistos[k]
                if clave in self.vistos:
                    return False
                self.vistos[clave] = ahora
        return True


class Telegram:
    def __init__(self, token, chat_id, log=None, ruido=None):
        self.token = (token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self.activo = bool(self.token and self.chat_id)
        self.log = log
        self.ruido = ruido or ControlRuido()
        self.offset = None
        self.ultimo_error = {}
        self.cola = queue.Queue()
        if self.activo:
            threading.Thread(target=self._enviar_en_fondo, daemon=True).start()

    def _llamar(self, metodo, **datos):
        r = requests.post(API.format(token=self.token, metodo=metodo), json=datos, timeout=15)
        return r.json()

    def _enviar_en_fondo(self):
        while True:
            texto = self.cola.get()
            for intento in range(3):
                try:
                    self._llamar("sendMessage", chat_id=self.chat_id, text=texto[:4000],
                                 disable_web_page_preview=True)
                    break
                except Exception as e:  # noqa: BLE001
                    if intento == 2 and self.log:
                        self.log.warning("Telegram: no se pudo enviar el aviso (%s)", e)
                    time.sleep(3)

    def enviar(self, texto, severidad="info"):
        """Envía sin bloquear el bot. Si Telegram falla, el bot sigue igual. severidad: info | aviso | error |
        respuesta (ver ControlRuido: solo 'info' puede callar en horas de silencio)."""
        if self.activo and self.ruido.permitir(texto, severidad):
            self.cola.put(texto)

    def error(self, clave, texto, cada_min=15):
        """Avisa de un error como mucho una vez cada 'cada_min' minutos por tipo."""
        ahora = time.time()
        if ahora - self.ultimo_error.get(clave, 0) >= cada_min * 60:
            self.ultimo_error[clave] = ahora
            self.enviar("⚠️ " + texto, "error")

    def comandos(self):
        """Devuelve los comandos nuevos recibidos desde TU chat (lista de strings)."""
        if not self.activo:
            return []
        try:
            datos = {"timeout": 0, "allowed_updates": ["message"]}
            if self.offset is not None:
                datos["offset"] = self.offset
            res = self._llamar("getUpdates", **datos)
        except Exception:  # noqa: BLE001
            return []
        cmds = []
        for u in res.get("result", []):
            self.offset = u["update_id"] + 1
            msg = u.get("message") or {}
            if str(msg.get("chat", {}).get("id")) != self.chat_id:
                continue  # ignora a cualquiera que no seas tú
            texto = (msg.get("text") or "").strip()
            if texto.startswith("/"):
                partes = texto.split()
                partes[0] = partes[0].split("@")[0].lower()      # el comando en minúsculas; los argumentos tal cual
                cmds.append(" ".join(partes[:4]))
        return cmds


def _mostrar_chat_id():
    from compat import consola_utf8
    consola_utf8()
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        print("Pon primero TELEGRAM_TOKEN en el archivo .env (te lo da @BotFather).")
        return
    res = requests.get(API.format(token=token, metodo="getUpdates"), timeout=15).json()
    if not res.get("ok"):
        print("Telegram rechaza el token:", res)
        return
    chats = {}
    for u in res.get("result", []):
        chat = (u.get("message") or {}).get("chat")
        if chat:
            chats[chat["id"]] = chat.get("first_name") or chat.get("title") or ""
    if not chats:
        print("No hay mensajes. Escribe algo a tu bot desde Telegram y vuelve a ejecutar esto.")
        return
    for cid, nombre in chats.items():
        print(f"chat_id: {cid}   ({nombre})")
    print("\nCopia el número en .env como TELEGRAM_CHAT_ID=...")


if __name__ == "__main__":
    _mostrar_chat_id()
