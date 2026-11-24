"""
Límite de peticiones a Hyperliquid: 1200 de "peso" por minuto y por IP. Si se supera, responde 429
y la petición falla. Esto envuelve la función post de Info para que todas las consultas del bot
(velas, libro, posiciones, ballenas...) respeten un presupuesto común, esperando lo justo si hace
falta, y reintentando con calma si aun así llega un 429.
"""

import threading
import time
from collections import deque

LIMITE_IP = 1200                  # Hyperliquid: peso REST agregado por minuto y por IP (todos los procesos juntos)
PRESUPUESTO_MINUTO = 900          # por debajo de 1200 para dejar margen al websocket y a otros programas
COMPARTIDO = None                 # el limitador del proceso del bot (lo fija bot.crear_cliente); datos.Api lo usa

# Pesos según la documentación de Hyperliquid («Rate limits and user limits», consultada el 28/10/2026):
#   2: l2Book, allMids, clearinghouseState, orderStatus, spotClearinghouseState, exchangeStatus · 60: userRole ·
#   20: el resto. Además, peso EXTRA según lo que devuelve la respuesta (ver PESO_POR_ELEMENTOS).
PESOS = {"l2Book": 2, "allMids": 2, "clearinghouseState": 2, "orderStatus": 2, "spotClearinghouseState": 2,
         "exchangeStatus": 2, "userRole": 60}
# +1 de peso por cada N elementos devueltos.
POR_20 = ("recentTrades", "historicalOrders", "userFills", "userFillsByTime", "fundingHistory", "userFunding",
          "nonUserFundingUpdates", "twapHistory", "userTwapSliceFills", "userTwapSliceFillsByTime",
          "delegatorHistory", "delegatorRewards", "validatorStats")
PESO_POR_ELEMENTOS = dict({t: 20 for t in POR_20}, candleSnapshot=60)


def peso(cuerpo):
    """Peso BASE (antes de conocer la respuesta)."""
    tipo = cuerpo.get("type") if isinstance(cuerpo, dict) else None
    return PESOS.get(tipo, 20)


def peso_extra(cuerpo, respuesta):
    """Peso adicional por elementos devueltos (0 si el tipo no lo tiene o la respuesta no es una lista)."""
    tipo = cuerpo.get("type") if isinstance(cuerpo, dict) else None
    n = PESO_POR_ELEMENTOS.get(tipo)
    if not n or not isinstance(respuesta, list):
        return 0
    return len(respuesta) // n


class Limitador:
    def __init__(self, presupuesto=PRESUPUESTO_MINUTO, log=None):
        self.presupuesto, self.log = presupuesto, log
        self.historial = deque()
        self.bloqueo = threading.Lock()
        self.esperas = 0
        self.reintentos_429 = 0
        self.por_tipo = {}               # peso acumulado por tipo de petición (diagnóstico: qué gasta el presupuesto)

    def reservar(self, p):
        while True:
            with self.bloqueo:
                ahora = time.time()
                while self.historial and ahora - self.historial[0][0] >= 60:
                    self.historial.popleft()
                usado = sum(x[1] for x in self.historial)
                if usado + p <= self.presupuesto:
                    self.historial.append((ahora, p))
                    return
                espera = 60 - (ahora - self.historial[0][0]) + 0.05
            self.esperas += 1
            time.sleep(min(max(espera, 0.1), 5))

    def cargar(self, p):
        """Anota peso ya consumido (el extra por elementos devueltos) sin esperar: frena las siguientes."""
        if p > 0:
            with self.bloqueo:
                self.historial.append((time.time(), p))

    def usado(self):
        with self.bloqueo:
            ahora = time.time()
            return sum(p for t, p in self.historial if ahora - t < 60)

    def envolver(self, info):
        """Sustituye info.post por una versión que respeta el presupuesto y reintenta los 429."""
        original = info.post

        def post(ruta, cuerpo=None, *a, **k):
            self.reservar(peso(cuerpo or {}))
            tipo = (cuerpo or {}).get("type", "?") if isinstance(cuerpo, dict) else "?"
            self.por_tipo[tipo] = self.por_tipo.get(tipo, 0) + peso(cuerpo or {})
            for intento in range(4):
                try:
                    r = original(ruta, cuerpo, *a, **k)
                    extra = peso_extra(cuerpo or {}, r)
                    self.por_tipo[tipo] = self.por_tipo.get(tipo, 0) + extra
                    self.cargar(extra)
                    return r
                except Exception as e:
                    if "429" not in str(e)[:20] or intento == 3:
                        raise
                    self.reintentos_429 += 1
                    if self.log:
                        self.log.warning("Hyperliquid pide calma (429): espero %d s y reintento.", 5 * (intento + 1))
                    time.sleep(5 * (intento + 1))
                    self.reservar(peso(cuerpo or {}))
        info.post = post
        return info
