"""Motor en vivo de la cuenta agresiva SIMULADA. Dinero ficticio con precios, libros, velas y funding REALES (solo lectura
de la API pública de Hyperliquid). No envía órdenes, no firma, no usa claves ni cuenta: no existe código de orden real en
este paquete (una prueba lo exige) y se niega a operar si config.json no está en modo simulado.

Corre como proceso propio (`python -m agresiva.motor`), aparte del bot, del panel y del carry. Cada pasada (por defecto
cada 60 s):
  1. lee precios de marca, apalancamiento máximo, tramos de margen, funding y volumen de todas las monedas;
  2. cobra o paga el funding REAL de cada hora (fundingHistory), dentro del margen aislado de cada pierna;
  3. pasa las velas de 1 min ya cerradas por cada señal abierta (stops, objetivos, liquidación, cierre por tiempo). Stop
     y liquidación se miran con una vela tipo precio de marca: la de Hyperliquid y la de Binance del mismo minuto (solo
     lectura pública) tienen que tocar el nivel las dos (logica.vela_disparo);
  4. aplica los frenos (pausa por caída, freno diario, quiebra);
  5. al cerrar cada vela de 15 min mira las monedas del universo (las de más volumen) y abre las señales nuevas
     comiendo niveles del libro real;
  6. escribe agresiva_estado.json (lo lee el panel), papel_agresiva.json (la cuenta) y registro/agresiva.jsonl.

Ajustes opcionales en agresiva_config.json (no existe por defecto): cualquier clave de logica.CFG_DEFECTO y además
intervalo_s (60), pausa_peticion_s (3) y activo (true).
Reiniciar la cuenta tras una quiebra (solo a mano): `python -m agresiva.motor --reiniciar` deja la petición y el motor la
aplica en su siguiente pasada.
"""

import json
import os
import sys
import time

import requests

from agresiva import logica
from agresiva.cuenta import Cuenta, estado_nuevo, migrar_estado
from compat import reemplazar

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL_INFO = "https://api.hyperliquid.xyz/info"
PERMITIDOS = ("metaAndAssetCtxs", "candleSnapshot", "l2Book", "fundingHistory")    # solo consultas públicas de lectura
URL_BINANCE = "https://fapi.binance.com/fapi/v1/klines"                # velas públicas de Binance (solo lectura, sin claves)
INTERVALO_DEFECTO_S = 60
PAUSA_PETICION_S = 3.0
TTL_UNIVERSO_S = 6 * 3600
VELAS_INICIALES = 130
MAX_VELAS = 200
MIN_MS = 60_000
GRAFICO_1M = 360                 # velas de 1 min que se guardan para el gráfico de cada señal abierta (6 h)
GRAFICO_15M = 120                # y de 15 min (30 h)
ANTES_MS = 60 * MIN_MS           # el gráfico empieza una hora antes de la entrada
HORA_MS = 3_600_000
FUNDING_REINTENTO_S = 300        # si el pago de la hora aún no aparece en fundingHistory, se vuelve a mirar a los 5 min
MAX_REF = 400                    # velas de 1 min de Binance que se guardan por señal (referencia para el disparo)


class ErrorApi(Exception):
    pass


class ErrorLimite(ErrorApi):
    pass


def _info(carga, post):
    """Única puerta de salida a la red: solo /info y solo consultas de la lista blanca."""
    if carga.get("type") not in PERMITIDOS:
        raise ErrorApi(f"consulta no permitida: {carga.get('type')}")
    r = post(URL_INFO, json=carga, timeout=30)
    if r.status_code == 429:
        raise ErrorLimite("HTTP 429: demasiadas consultas")
    if r.status_code != 200:
        raise ErrorApi(f"HTTP {r.status_code} en {carga.get('type')}")
    return r.json()


def simbolo_binance(coin):
    """Símbolo del perpetuo de Binance para una moneda de Hyperliquid (kPEPE → 1000PEPEUSDT)."""
    base = coin.split(":")[-1]
    if base.startswith("k") and len(base) > 1 and base[1:].isupper():
        return "1000" + base[1:] + "USDT"
    return base.upper() + "USDT"


class SimboloDesconocido(ErrorApi):
    pass


def velas_binance_1m(simbolo, desde_ms, hasta_ms, get, paginas=4):
    """Velas de 1 min de Binance (futuros, públicas) de desde_ms a hasta_ms. Única puerta a Binance: solo GET a klines."""
    out, t = [], int(desde_ms)
    for _ in range(paginas):
        if t >= hasta_ms:
            break
        r = get(URL_BINANCE, params={"symbol": simbolo, "interval": "1m", "startTime": t, "endTime": int(hasta_ms), "limit": 1500},
                timeout=30)
        if r.status_code == 400:
            raise SimboloDesconocido(f"Binance no tiene {simbolo}")
        if r.status_code in (418, 429):
            raise ErrorLimite(f"Binance HTTP {r.status_code}")
        if r.status_code != 200:
            raise ErrorApi(f"Binance HTTP {r.status_code}")
        lote = r.json() or []
        if not lote:
            break
        out += [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4])} for k in lote]
        nuevo = int(lote[-1][0]) + MIN_MS
        if nuevo <= t:
            break
        t = nuevo
    return out


def velas_api(lista):
    return [{"t": int(x["t"]), "o": float(x["o"]), "h": float(x["h"]), "l": float(x["l"]), "c": float(x["c"]),
             "v": float(x.get("v", 0) or 0)} for x in sorted(lista or [], key=lambda x: x["t"])]


def tramos_margen(meta):
    """{moneda: [(desde_usd, apal_max)]} con los tramos de margen de Hyperliquid (igual que riesgo.tramos_margen)."""
    tablas = {}
    for fila in (meta or {}).get("marginTables") or []:
        try:
            tid, tabla = fila
            tablas[tid] = sorted((float(x["lowerBound"]), int(x["maxLeverage"])) for x in tabla.get("marginTiers") or [])
        except (TypeError, ValueError, KeyError):
            continue
    return {a["name"]: tablas[a["marginTableId"]] for a in (meta or {}).get("universe") or []
            if a.get("marginTableId") in tablas and tablas[a["marginTableId"]]}


def barrer(niveles, sz):
    """Precio medio al comer niveles [(px, sz)] hasta llenar sz; None si no hay profundidad."""
    faltan, coste = sz, 0.0
    for px, cant in niveles:
        t = min(faltan, cant)
        coste += t * px
        faltan -= t
        if faltan <= 1e-12:
            return coste / sz
    return None


def _escribir_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    reemplazar(tmp, ruta)


def _leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return defecto


class Registro:
    def __init__(self, ruta):
        self.ruta = ruta

    def anotar(self, tipo, **datos):
        os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
        fila = dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tipo": tipo}, **datos)
        with open(self.ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")


class MotorAgresiva:
    def __init__(self, raiz=AQUI, post=requests.post, reloj=time.time, esperar=time.sleep, get=requests.get):
        self.raiz, self.post, self.reloj, self.esperar, self.get = raiz, post, reloj, esperar, get
        self.ruta_cuenta = os.path.join(raiz, "papel_agresiva.json")
        self.ruta_estado = os.path.join(raiz, "agresiva_estado.json")
        self.ruta_reinicio = os.path.join(raiz, "agresiva_reinicio.json")
        self.registro = Registro(os.path.join(raiz, "registro", "agresiva.jsonl"))
        self.recargar_config()
        d = _leer_json(self.ruta_cuenta, None)
        if not d:
            d = estado_nuevo(self.reloj(), float(self.c["cuenta_inicial_usd"]))
            self.registro.anotar("inicio", saldo_usd=self.c["cuenta_inicial_usd"])
        for cambio in migrar_estado(d, self.reloj()):
            self.registro.anotar("cambio_reglas", version=cambio["version"], texto=cambio["texto"])
        self.cuenta = Cuenta(d, self.c)
        self.sin_binance = set()           # monedas sin perpetuo en Binance: stop y liquidación solo con Hyperliquid
        self.mercado = {}
        self.universo, self.universo_ts = [], 0.0
        self.velas15 = {}
        self.graf = {}                     # coin -> {"id", "1m": [velas], "15m": [velas], "b15": bloque}
        self.ultimas_senales, self.descartadas, self.alertas = [], [], []

    # ------------------------------------------------------------ configuración y seguridad
    def recargar_config(self):
        propia = _leer_json(os.path.join(self.raiz, "agresiva_config.json"), {}) or {}
        self.extra = {"intervalo_s": int(propia.pop("intervalo_s", INTERVALO_DEFECTO_S)),
                      "pausa_peticion_s": float(propia.pop("pausa_peticion_s", PAUSA_PETICION_S)),
                      "activo": bool(propia.pop("activo", True))}
        self.c = logica.cfg(**propia)
        if hasattr(self, "cuenta"):
            self.cuenta.c = self.c

    def modo_permitido(self):
        """Solo con el bot en modo simulado. Cualquier otra cosa (real, shadow, ilegible) = parado."""
        return (_leer_json(os.path.join(self.raiz, "config.json"), {}) or {}).get("modo") == "simulado"

    def _alerta(self, mensaje, **extra):
        self.registro.anotar("alerta", mensaje=mensaje, **extra)
        self.alertas = (self.alertas + [{"ts": self.reloj(), "mensaje": mensaje}])[-10:]

    # ------------------------------------------------------------ mercado
    def _leer_mercado(self, ahora):
        meta, ctxs = _info({"type": "metaAndAssetCtxs"}, self.post)
        tramos = tramos_margen(meta)
        mercado = {}
        for a, x in zip(meta.get("universe") or [], ctxs or []):
            if a.get("isDelisted") or not x.get("markPx"):
                continue
            try:
                mercado[a["name"]] = {"sz_dec": int(a.get("szDecimals", 0)), "apal_max": int(a.get("maxLeverage", 1)),
                                      "tramos": tramos.get(a["name"], []), "marca": float(x["markPx"]),
                                      "funding": float(x.get("funding") or 0), "vol": float(x.get("dayNtlVlm") or 0)}
            except (TypeError, ValueError):
                continue
        self.mercado = mercado
        if not self.universo or ahora - self.universo_ts > TTL_UNIVERSO_S:
            buenas = [k for k, v in mercado.items() if v["vol"] >= self.c["volumen_min_usd"]]
            self.universo = sorted(buenas, key=lambda k: -mercado[k]["vol"])[: int(self.c["universo_n"])]
            self.universo_ts = ahora
        return {k: v["marca"] for k, v in mercado.items()}

    # ------------------------------------------------------------ gestión de lo abierto
    def _graficos(self, ahora, solo_nuevas=False):
        """Velas de 1 min (incluida la que se está formando) y de 15 min de cada señal abierta. Sirven para el gráfico del
        panel y, las de 1 min ya cerradas, para mover stops y objetivos (_gestionar): una sola consulta por moneda."""
        fin = int(ahora * 1000)
        vivos = {}
        for coin, s in self.cuenta.d["abiertas"].items():
            g = self.graf.get(coin)
            if g and g["id"] == s["id"] and solo_nuevas:
                vivos[coin] = g
                continue
            if not g or g["id"] != s["id"]:
                g = {"id": s["id"], "1m": [], "15m": [], "b15": None}
            desde = g["1m"][-1]["t"] if g["1m"] else                 min(s["abierta_ms"] - ANTES_MS, (s["ultimo_min_ms"] // MIN_MS) * MIN_MS + MIN_MS)
            try:
                nuevas = velas_api(_info({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1m", "startTime": int(desde),
                                                                           "endTime": fin}}, self.post))
                juntas = {v["t"]: v for v in g["1m"]}
                juntas.update({v["t"]: v for v in nuevas if v["t"] <= fin})
                g["1m"] = [juntas[t] for t in sorted(juntas)]
                bloque = fin // logica.QUINCE_MIN_MS
                if g["b15"] != bloque:
                    d15 = g["15m"][-1]["t"] if g["15m"] else s["abierta_ms"] - 24 * logica.QUINCE_MIN_MS
                    n15 = velas_api(_info({"type": "candleSnapshot", "req": {"coin": coin, "interval": "15m",
                                                                            "startTime": int(d15), "endTime": fin}}, self.post))
                    j15 = {v["t"]: v for v in g["15m"]}
                    j15.update({v["t"]: v for v in n15})
                    g["15m"] = [j15[t] for t in sorted(j15)][-GRAFICO_15M:]
                    g["b15"] = bloque
            except ErrorApi as e:
                self._alerta(f"no pude leer las velas de {coin} ({e})", coin=coin)
            self._referencia(coin, s, g, fin)
            vivos[coin] = g
        self.graf = vivos

    def _referencia(self, coin, s, g, fin):
        """Velas de 1 min de Binance del mismo tramo: con ellas el disparo de stop y liquidación se parece al precio de
        marca de Hyperliquid (que mezcla su libro con otros exchanges). Sin ellas, se usa solo la vela de Hyperliquid."""
        if coin in self.sin_binance:
            return
        ref = g.setdefault("ref", {})
        desde = max(ref) + MIN_MS if ref else (s["ultimo_min_ms"] // MIN_MS) * MIN_MS
        try:
            for v in velas_binance_1m(simbolo_binance(coin), desde, fin, self.get):
                if v["t"] + MIN_MS <= fin:
                    ref[v["t"]] = v
        except SimboloDesconocido:
            self.sin_binance.add(coin)
            self._alerta(f"{coin} no cotiza en Binance: su stop y su liquidación se miran solo con Hyperliquid", coin=coin)
        except (ErrorApi, ValueError, TypeError, KeyError, IndexError, requests.RequestException) as e:
            self._alerta(f"no pude leer las velas de Binance de {coin} ({e}): esta pasada, solo Hyperliquid", coin=coin)
        for t in sorted(ref)[:-MAX_REF]:
            del ref[t]

    def _gestionar(self, ahora):
        fin = int(ahora * 1000)
        for coin, s in list(self.cuenta.d["abiertas"].items()):
            desde = (s["ultimo_min_ms"] // MIN_MS) * MIN_MS + MIN_MS
            g = self.graf.get(coin)
            if not g or g["id"] != s["id"]:
                continue
            velas = [v for v in g["1m"] if v["t"] >= desde and v["t"] + MIN_MS <= fin]
            g["1m"] = g["1m"][-GRAFICO_1M:]
            ref = g.get("ref") or {}
            for v in velas:
                if v["t"] < desde or v["t"] + MIN_MS > fin:
                    continue
                for ev in self.cuenta.avanzar(coin, v, logica.vela_disparo(v, ref.get(v["t"]), s["lado"])):
                    self.registro.anotar(ev["tipo"], coin=coin, id=s["id"], **{k: x for k, x in ev.items() if k != "tipo"})
                if coin not in self.cuenta.d["abiertas"]:
                    cerrada = self.cuenta.d["cerradas"][-1]
                    self.registro.anotar("senal_cerrada", **cerrada)
                    break

    def _funding(self, ahora):
        """Funding pagado de verdad: cada hora, los pagos de fundingHistory posteriores a la entrada (y a lo ya cobrado) se
        aplican con el precio de cierre del minuto anterior a la hora. Si el pago aún no aparece, se reintenta a los 5 min.
        Va antes de pasar las velas: una señal que se cierra justo después de la hora paga esa hora."""
        fin = int(ahora * 1000)
        hora_ms = fin // HORA_MS * HORA_MS
        for coin, s in list(self.cuenta.d["abiertas"].items()):
            hecho = s.get("funding_ms")
            if hecho is None:                    # abierta antes del 25/11: el motor anterior ya cobró hasta la hora pasada
                previa = self.cuenta.d.get("funding_h")
                hecho = s["funding_ms"] = previa * HORA_MS if previa else s["abierta_ms"]
            if hora_ms <= hecho:
                continue
            if s.get("funding_consulta_h") == hora_ms and ahora - s.get("funding_consulta", 0) < FUNDING_REINTENTO_S:
                continue
            s["funding_consulta"], s["funding_consulta_h"] = ahora, hora_ms
            try:
                filas = _info({"type": "fundingHistory", "coin": coin, "startTime": int(hecho) + 1, "endTime": fin}, self.post)
            except ErrorApi as e:
                self._alerta(f"no pude leer el funding de {coin} ({e})", coin=coin)
                continue
            velas = {v["t"]: v for v in (self.graf.get(coin) or {}).get("1m", [])}
            m = self.mercado.get(coin) or {}
            for fila in sorted(filas or [], key=lambda x: int(x["time"])):
                t = int(fila["time"])
                if t <= hecho or t <= s["abierta_ms"] or t > fin:
                    continue
                minuto = velas.get((t // MIN_MS - 1) * MIN_MS)
                precio = minuto["c"] if minuto else m.get("marca")
                if not precio:
                    continue
                tasa = float(fila["fundingRate"])
                pagos = self.cuenta.funding(coin, precio, tasa)
                s["funding_ms"] = hecho = t
                self.registro.anotar("funding", coin=coin, id=s["id"], t=t, tasa=tasa, precio=precio,
                                     **{f"pago_{k}": round(v, 6) for k, v in pagos.items()})

    # ------------------------------------------------------------ señales nuevas
    def _velas15(self, coin, bloque, fin_ms):
        previas = self.velas15.get(coin) or []
        inicio = previas[-1]["t"] if previas and previas[-1]["t"] >= (bloque - 6) * logica.QUINCE_MIN_MS else \
            (bloque - VELAS_INICIALES) * logica.QUINCE_MIN_MS
        if not previas or inicio != previas[-1]["t"]:
            previas = []
        nuevas = velas_api(_info({"type": "candleSnapshot", "req": {"coin": coin, "interval": "15m", "startTime": inicio,
                                                                   "endTime": fin_ms}}, self.post))
        juntas = {v["t"]: v for v in previas}
        juntas.update({v["t"]: v for v in nuevas})
        velas = [juntas[t] for t in sorted(juntas) if t + logica.QUINCE_MIN_MS <= fin_ms][-MAX_VELAS:]
        self.velas15[coin] = velas
        return velas

    def _llenador(self, coin):
        libro = {}

        def llenar(compra, sz):
            if not libro:
                l2 = _info({"type": "l2Book", "coin": coin}, self.post)
                compras, ventas = l2["levels"]
                libro["compras"] = [(float(x["px"]), float(x["sz"])) for x in compras]
                libro["ventas"] = [(float(x["px"]), float(x["sz"])) for x in ventas]
            return barrer(libro["ventas"] if compra else libro["compras"], sz)
        return llenar

    def _senales(self, ahora, marcas):
        fin = int(ahora * 1000)
        bloque = fin // logica.QUINCE_MIN_MS
        if self.cuenta.d.get("ultimo_bloque") == bloque:
            return
        self.cuenta.d["ultimo_bloque"] = bloque
        for coin in self.universo:
            if coin in self.cuenta.d["abiertas"] or coin not in self.mercado:
                continue
            try:
                velas = self._velas15(coin, bloque, fin)
            except ErrorLimite as e:
                self._alerta(f"Hyperliquid limita las consultas ({e}): se salta el resto de este cuarto de hora")
                self.esperar(30)
                return
            except ErrorApi as e:
                self._alerta(f"no pude leer las velas de 15 min de {coin} ({e})", coin=coin)
                continue
            finally:
                self.esperar(self.extra["pausa_peticion_s"])
            if not velas or velas[-1]["t"] != (bloque - 1) * logica.QUINCE_MIN_MS:
                continue
            det = logica.detectar(velas, self.c)
            if not det:
                continue
            self.cuenta.d["contadores"]["senales"] += 1
            info = {"coin": coin, "regla": det["regla"], "lado": det["lado"], "precio": det["precio"], "t": det["t"]}
            self.ultimas_senales = (self.ultimas_senales + [info])[-20:]
            try:
                r = self.cuenta.abrir(coin, det, self.mercado[coin], marcas, self._llenador(coin), ahora)
            except (ErrorApi, KeyError, ValueError, TypeError) as e:
                r = {"error": f"no pude leer el libro ({e})"}
            if "error" in r:
                self.descartadas = (self.descartadas + [dict(info, motivo=r["error"])])[-20:]
                self.registro.anotar("senal_descartada", **dict(info, motivo=r["error"]))
                continue
            self.registro.anotar("senal_abierta", id=r["id"], coin=coin, regla=r["regla"], lado=r["lado"],
                                 precio_senal=r["precio_senal"], stop_pct=r["stop_pct"], sin_agresiva=r["sin_agresiva"],
                                 sin_gemela=r.get("sin_gemela"), agresiva=_resumen_pierna(r.get("agresiva")),
                                 gemela=_resumen_pierna(r.get("gemela")))

    # ------------------------------------------------------------ una pasada
    def pasada(self):
        t0 = time.time()
        ahora = self.reloj()
        self.recargar_config()
        if not self.extra["activo"]:
            return self._estado(ahora, "apagado", "agresiva_config.json tiene activo=false", {})
        if not self.modo_permitido():
            return self._estado(ahora, "parado", "el bot no está en modo simulado: la cuenta agresiva solo funciona con dinero ficticio", {})
        marcas = self._leer_mercado(ahora)
        if os.path.exists(self.ruta_reinicio):
            antes, cierres = self.cuenta.reiniciar(marcas, ahora)
            self.registro.anotar("reinicio", **dict(antes, cierres=cierres))
            try:
                os.remove(self.ruta_reinicio)
            except OSError:
                pass
        self._graficos(ahora)
        self._funding(ahora)
        self._gestionar(ahora)
        for ev in self.cuenta.frenos(ahora, marcas):
            self.registro.anotar(ev.pop("tipo"), **ev)
        self._senales(self.reloj(), marcas)
        self._graficos(self.reloj(), solo_nuevas=True)
        for ev in self.cuenta.frenos(self.reloj(), marcas):
            self.registro.anotar(ev.pop("tipo"), **ev)
        self.cuenta.anotar_curva(ahora, marcas)
        self._guardar()
        return self._estado(ahora, "activo", None, marcas, duracion=time.time() - t0)

    def _guardar(self):
        _escribir_json(self.ruta_cuenta, self.cuenta.d)

    # ------------------------------------------------------------ estado para el panel
    def _estado(self, ahora, estado, motivo, marcas, duracion=None):
        out = resumen_panel(self.cuenta, marcas, self.c, ahora)
        compacta = lambda vs: [[v["t"], v["o"], v["h"], v["l"], v["c"]] for v in vs]
        for fila in out["abiertas"]:
            g = self.graf.get(fila["coin"])
            fila["velas"] = {"1m": compacta(g["1m"][-GRAFICO_1M:]), "15m": compacta(g["15m"])} if g and g["id"] == fila["id"] else None
        out.update({"ts": ahora, "estado": estado, "motivo": motivo, "simulado": True, "intervalo_s": self.extra["intervalo_s"],
                    "duracion_pasada_s": None if duracion is None else round(duracion, 1), "universo": self.universo,
                    "ultimas_senales": self.ultimas_senales[::-1], "descartadas": self.descartadas[::-1],
                    "alertas": self.alertas[::-1], "reinicio_pedido": os.path.exists(self.ruta_reinicio),
                    "sin_binance": sorted(self.sin_binance),
                    "historia": _leer_json(os.path.join(self.raiz, "agresiva_historia.json"), None)})
        _escribir_json(self.ruta_estado, out)
        return out


def _resumen_pierna(p):
    if not p:
        return None
    return {"entrada": p["entrada"], "sz": p["sz0"], "apal": p["apal"], "margen_usd": round(p["margen0"], 4), "liq": p["liq"],
            "stop": p["stop0"], "objetivos": p["objetivos"], "tamanos": p.get("tamanos"), "recortada": bool(p.get("recortada")),
            "riesgo_pct": round(logica.riesgo_inicial(p) / p["equity_entrada"] * 100, 3) if p.get("equity_entrada") else None}


def _stats(filas, cual):
    ps = [f[cual] for f in filas if f.get(cual)]
    if not ps:
        return {"n": 0}
    rs = [p["r"] for p in ps]
    out = {"n": len(ps), "pnl_usd": round(sum(p["pnl_usd"] for p in ps), 4), "r_media": round(sum(rs) / len(rs), 4),
           "r_total": round(sum(rs), 4), "ganadoras": sum(1 for r in rs if r > 0),
           "acierto_pct": round(sum(1 for r in rs if r > 0) / len(rs) * 100, 1),
           "con_objetivo_1": sum(1 for p in ps if p["objetivos_tocados"] >= 1),
           "todos_objetivos": sum(1 for p in ps if p["salida"] == f"objetivo_{len(logica.CFG_DEFECTO['objetivos_r'])}"),
           "stops": sum(1 for p in ps if p["salida"] == "stop"), "stops_en_entrada": sum(1 for p in ps if p["salida"] == "stop_entrada"),
           "liquidaciones": sum(1 for p in ps if p["salida"] == "liquidacion"),
           "por_tiempo": sum(1 for p in ps if p["salida"] == "tiempo"),
           "comisiones_usd": round(sum(p["comisiones_usd"] for p in ps), 4), "funding_usd": round(sum(p["funding_usd"] for p in ps), 4)}
    pct = [p["pct_cuenta"] for p in ps if p.get("pct_cuenta") is not None]
    if pct:
        out["pct_cuenta_media"] = round(sum(pct) / len(pct), 3)
    riesgo = [p["riesgo_pct"] for p in ps if p.get("riesgo_pct") is not None]
    if riesgo:
        out["riesgo_pct_media"] = round(sum(riesgo) / len(riesgo), 3)
    return out


def resumen_panel(cuenta, marcas, c, ahora):
    d = cuenta.d
    a, g = d["agresiva"], d["gemela"]
    eqa, eqg = cuenta.equity_agresiva(marcas), cuenta.equity_gemela(marcas)
    inicial = d["etapa"]["inicial_usd"]
    abiertas = []
    for coin, s in d["abiertas"].items():
        marca = marcas.get(coin)
        fila = {"id": s["id"], "coin": coin, "regla": s["regla"], "nombre_regla": logica.NOMBRES.get(s["regla"], s["regla"]),
                "lado": s["lado"], "abierta_ms": s["abierta_ms"], "horas": round((ahora * 1000 - s["abierta_ms"]) / 3_600_000, 2),
                "precio_senal": s["precio_senal"], "stop_pct": s["stop_pct"], "apal_max_mercado": s["apal_max_mercado"],
                "marca": marca, "sin_agresiva": s.get("sin_agresiva"), "sin_gemela": s.get("sin_gemela"),
                "eventos": s.get("eventos") or []}
        for cual in ("agresiva", "gemela"):
            p = s.get(cual)
            if not p:
                fila[cual] = None
                continue
            m = marca or p["entrada"]
            upnl = p["lado"] * (m - p["entrada"]) * p["sz"]
            fila[cual] = {"entrada": p["entrada"], "sz": p["sz"], "sz0": p["sz0"], "apal": p["apal"], "margen0": round(p["margen0"], 4),
                          "margen_usd": round(logica.margen_restante(p), 4), "liq": p["liq"], "stop": p["stop"], "stop0": p["stop0"],
                          "objetivos": p["objetivos"], "toc": p["toc"], "upnl_usd": round(upnl, 4),
                          "pnl_realizado_usd": round(p["pnl_usd"], 4), "neto_usd": round(p["pnl_usd"] + upnl, 4),
                          "r_actual": round((p["pnl_usd"] + upnl) / logica.riesgo_inicial(p), 3) if logica.riesgo_inicial(p) else None,
                          "dist_stop_pct": round(abs(m - p["stop"]) / m * 100, 3) if m else None,
                          "dist_liq_pct": round(abs(m - p["liq"]) / m * 100, 3) if (m and p["liq"]) else None,
                          "liq_antes_que_stop": bool(p["liq"] and p["lado"] * (p["liq"] - p["stop"]) > 0),
                          "riesgo_pct": round(logica.riesgo_inicial(p) / p["equity_entrada"] * 100, 3) if p.get("equity_entrada") else None,
                          "recortada": bool(p.get("recortada")), "funding_usd": round(p.get("funding_usd", 0.0), 4),
                          "salida": p["salida"]}
        abiertas.append(fila)
    cer = d["cerradas"]
    por_regla = {}
    for regla in sorted({f["regla"] for f in cer} | set(c["reglas"])):
        filas = [f for f in cer if f["regla"] == regla]
        por_regla[regla] = {"nombre": logica.NOMBRES.get(regla, regla), "agresiva": _stats(filas, "agresiva"), "gemela": _stats(filas, "gemela")}
    etapa_actual = [f for f in cer if f.get("etapa") == d["etapa"]["n"]]
    curva = d["curva"]
    paso = max(1, len(curva) // 600)
    return {
        "etapa": d["etapa"], "reinicios": d["reinicios"], "contadores": d["contadores"],
        "agresiva": {"equity_usd": round(eqa, 2), "inicial_usd": round(inicial, 2), "libre_usd": round(a["libre_usd"], 2),
                     "margen_usado_usd": round(cuenta.margen_agresivo(), 2), "rendimiento_usd": round(eqa - inicial, 2),
                     "rendimiento_pct": round((eqa / inicial - 1) * 100, 2) if inicial else None, "estado": a["estado"],
                     "motivo_pausa": a["motivo_pausa"], "pausa_hasta": a["pausa_hasta"] or None, "pico_usd": round(a["pico_usd"], 2),
                     "caida_max_pct": round(a["caida_max_pct"], 2), "quiebra_usd": round(inicial * c["quiebra_pct"] / 100, 2),
                     "freno50_usado": a["freno50_usado"], "equity_dia_usd": a["equity_dia"] and round(a["equity_dia"], 2)},
        "gemela": {"equity_usd": round(eqg, 2), "inicial_usd": round(g["inicial_usd"], 2), "libre_usd": round(g["libre_usd"], 2),
                   "rendimiento_usd": round(eqg - g["inicial_usd"], 2),
                   "rendimiento_pct": round((eqg / g["inicial_usd"] - 1) * 100, 2) if g["inicial_usd"] else None,
                   "pico_usd": round(g["pico_usd"], 2), "caida_max_pct": round(g["caida_max_pct"], 2)},
        "abiertas": abiertas, "cerradas": cer[-100:][::-1],
        "resumen": {"total": {"agresiva": _stats(cer, "agresiva"), "gemela": _stats(cer, "gemela")},
                    "etapa": {"agresiva": _stats(etapa_actual, "agresiva")}, "por_regla": por_regla},
        "curva": curva[::paso] + ([curva[-1]] if curva and (len(curva) - 1) % paso else []),
        "criterios": {k: c[k] for k in ("riesgo_pct", "apalancamiento", "margen_max_pct", "max_abiertas", "margen_total_max_pct",
                                         "min_orden_usd", "freno_caida_pct", "pausa_freno_h", "freno_diario_pct", "quiebra_pct",
                                         "gemela_riesgo_pct", "gemela_apal_max", "comision_taker_pct", "comision_maker_pct",
                                         "desliz_pct", "stop_atr", "stop_min_pct", "stop_max_pct", "objetivos_r", "reparto_objetivos",
                                         "horas_max", "reglas", "universo_n", "volumen_min_usd", "cuenta_inicial_usd")},
        "cambios_reglas": d.get("cambios_reglas") or [],
        "nombres_reglas": logica.NOMBRES,
    }


def bucle(raiz=AQUI):
    from instancia import InstanciaDuplicada, _Bloqueo
    bloqueo = _Bloqueo(os.path.join(raiz, "agresiva.lock"))
    try:
        bloqueo.tomar()
    except InstanciaDuplicada:
        print("Ya hay un motor de la cuenta agresiva en marcha.")
        return 1
    motor = MotorAgresiva(raiz)
    print("Cuenta AGRESIVA SIMULADA en marcha (dinero ficticio, solo lectura de la API pública). Ctrl+C para parar.")
    while True:
        try:
            r = motor.pasada()
            print(time.strftime("%H:%M:%S"), r["estado"], f"· {len(r['abiertas'])} abiertas · agresiva {r['agresiva']['equity_usd']} $"
                  f" · gemela {r['gemela']['equity_usd']} $", flush=True)
        except KeyboardInterrupt:
            return 0
        except Exception as e:                                   # un fallo de red o de datos no debe parar el motor
            motor._alerta(f"fallo en la pasada: {type(e).__name__}: {e}")
            print("fallo en la pasada:", type(e).__name__, e, flush=True)
        try:
            espera = motor.extra["intervalo_s"] - (time.time() % motor.extra["intervalo_s"]) + 2   # justo tras cada minuto
            time.sleep(max(5, espera))
        except KeyboardInterrupt:
            return 0


def pedir_reinicio(raiz=AQUI):
    _escribir_json(os.path.join(raiz, "agresiva_reinicio.json"), {"pedido": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print("Reinicio pedido: el motor de la cuenta agresiva lo aplicará en su próxima pasada (cierra lo agresivo abierto y "
          "vuelve al saldo inicial; el historial y la gemela se conservan).")
    return 0


if __name__ == "__main__":
    sys.exit(pedir_reinicio() if "--reiniciar" in sys.argv[1:] else bucle())
