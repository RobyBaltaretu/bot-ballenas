"""Fase 3 del carry: el motor SIMULADO que lo une todo. Dinero ficticio con precios, libros y funding REALES (solo lectura
de la API pública de Hyperliquid). No envía órdenes, no firma, no usa claves ni cuenta: no existe código de orden real en este
paquete (una prueba lo exige) y se niega a funcionar si config.json no está en modo simulado.

Corre como proceso propio (`python -m carry.motor`), aparte del bot y del panel, y no toca papel.py, el ledger, el riesgo ni
las estrategias: la huella de código y de configuración del bot no cambia. Cada pasada (por defecto cada 10 min):
  1. acredita el funding real cobrado por los cortos abiertos,
  2. mira si alguna posición debe cerrarse (carry.logica.evaluar_salida) y la cierra (primero el corto, luego el contado),
  3. busca la mejor oportunidad (carry.logica.oportunidades), la dimensiona (tamano) y abre las dos patas (abrir_par),
  4. escribe carry_estado.json (lo lee el panel) y registro/carry.jsonl (lo que ha hecho y por qué).

Ajustes opcionales en carry_config.json (no existe por defecto): cualquier clave de logica.CFG_DEFECTO y además
cuenta_simulada_usd (por defecto 200), intervalo_s (600) y activo (true).
Con menos de 30 operaciones cerradas nada de lo que muestre es concluyente.
"""

import calendar
import json
import os
import sys
import time

import requests

from carry import logica, terreno
from carry.ejecucion import RegistroCarry, abrir_par, cerrar_par
from carry.papel_perp import PerpCortoPapel
from carry.papel_spot import PapelSpot
from compat import reemplazar

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUENTA_DEFECTO_USD = 200.0
INTERVALO_DEFECTO_S = 600
HORAS_HISTORIA = 80
TTL_FUNDING_S = 55 * 60
TTL_TERRENO_S = 24 * 3600
MAX_CERRADAS = 200


def libro_simple(l2):
    """l2Book de Hyperliquid -> {"compras": [(px, sz)], "ventas": [(px, sz)]} (vacío si la respuesta no vale)."""
    try:
        compras, ventas = l2["levels"]
        return {"compras": [(float(x["px"]), float(x["sz"])) for x in compras],
                "ventas": [(float(x["px"]), float(x["sz"])) for x in ventas]}
    except (KeyError, TypeError, ValueError):
        return {"compras": [], "ventas": []}


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


class MotorCarry:
    def __init__(self, raiz=AQUI, post=requests.post, reloj=time.time, esperar=time.sleep):
        self.raiz = raiz
        self.post = post
        self.reloj = reloj
        self.esperar = esperar
        self.ruta_cartera = os.path.join(raiz, "papel_carry.json")
        self.ruta_estado = os.path.join(raiz, "carry_estado.json")
        self.registro = RegistroCarry(os.path.join(raiz, "registro", "carry.jsonl"))
        self.spot = PapelSpot(os.path.join(raiz, "papel_spot.json"))
        self._cache_funding = {}          # coin -> (ts, registros)
        self._ultimas_oportunidades = {"entrar": [], "descartadas": {}}
        self.recargar_config()
        self.cartera = _leer_json(self.ruta_cartera, None) or {
            "version": 1, "creado": self.reloj(), "cuenta_inicial_usd": self.extra["cuenta_simulada_usd"],
            "libre_usd": self.extra["cuenta_simulada_usd"], "perp": {}, "posiciones": {}, "cerradas": [], "congeladas": {}}
        self.perp = PerpCortoPapel(self.cartera, self.c["comision_perp_pct"], self.c["apalancamiento_perp"])

    # ------------------------------------------------------------ configuración y seguridad
    def recargar_config(self):
        propia = _leer_json(os.path.join(self.raiz, "carry_config.json"), {}) or {}
        self.extra = {"cuenta_simulada_usd": float(propia.pop("cuenta_simulada_usd", CUENTA_DEFECTO_USD)),
                      "intervalo_s": int(propia.pop("intervalo_s", INTERVALO_DEFECTO_S)),
                      "activo": bool(propia.pop("activo", True))}
        self.c = logica.cfg(**{k: v for k, v in propia.items() if k in logica.CFG_DEFECTO})

    def modo_permitido(self):
        """Solo con el bot en modo simulado. Cualquier otra cosa (real, shadow, ilegible) = parado."""
        return (_leer_json(os.path.join(self.raiz, "config.json"), {}) or {}).get("modo") == "simulado"

    # ------------------------------------------------------------ lectura pública
    def _info(self, carga):
        return terreno._info(carga, self.post)

    def _terreno(self, ahora):
        ruta = terreno.RUTA_SALIDA if self.raiz == AQUI else os.path.join(self.raiz, "datos_mercado", "spot_hl.json")
        datos = _leer_json(ruta, {})
        viejo = not datos.get("aptas") or ahora - _epoch(datos.get("generado")) > TTL_TERRENO_S
        if viejo:
            try:
                datos = terreno.generar(self.post, ahora)
                terreno.guardar(datos, ruta)
            except Exception as e:                      # sin red o API caída: se sigue con lo que haya
                self.registro.anotar("carry_alerta", mensaje=f"no pude actualizar el contado verificado ({type(e).__name__}: {e})")
        return datos.get("aptas") or {}

    def _contexto_perp(self):
        meta, ctxs = self._info({"type": "metaAndAssetCtxs"})
        marcas, dec = {}, {}
        for m, c in zip(meta["universe"], ctxs):
            marcas[m["name"]] = float(c["markPx"])
            dec[m["name"]] = int(m.get("szDecimals", 4))
        return marcas, dec

    def _registros_funding(self, coin, ahora):
        previo = self._cache_funding.get(coin)
        if previo and ahora - previo[0] < TTL_FUNDING_S:
            return previo[1]
        reg = self._info({"type": "fundingHistory", "coin": coin, "startTime": int((ahora - HORAS_HISTORIA * 3600) * 1000)})
        self._cache_funding[coin] = (ahora, reg)
        self.esperar(0.2)
        return reg

    def _libros(self, coin, par):
        sp = self._info({"type": "l2Book", "coin": par})
        pp = self._info({"type": "l2Book", "coin": coin})
        return sp, pp

    # ------------------------------------------------------------ dinero
    def _recoger_contado(self):
        """Lo que haya quedado como USDC en la cuenta de contado vuelve a la cartera."""
        sobra = self.spot.d["usdc"]
        if sobra > 1e-9:
            self.spot.traspasar(-sobra, "devuelto a la cartera del carry")
            self.cartera["libre_usd"] += sobra

    def _equity(self, marcas, mids):
        total = self.cartera["libre_usd"] + self.spot.d["usdc"]
        for coin, p in self.cartera["perp"].items():
            marca = marcas.get(coin, p["entrada"])
            total += p["margen_usd"] + (p["entrada"] - marca) * p["sz"]
        for coin, q in self.spot.d["monedas"].items():
            total += q * mids.get(coin, 0.0)
        return total

    def _guardar(self):
        for k in [k for k in self.cartera if k.startswith("_")]:
            del self.cartera[k]
        del self.cartera["cerradas"][:-MAX_CERRADAS]
        _escribir_json(self.ruta_cartera, self.cartera)

    # ------------------------------------------------------------ una pasada
    def pasada(self):
        ahora = self.reloj()
        self.recargar_config()
        if not self.extra["activo"]:
            return self._estado(ahora, "apagado", "carry_config.json tiene activo=false")
        if not self.modo_permitido():
            return self._estado(ahora, "parado", "el bot no está en modo simulado: el carry solo funciona con dinero ficticio")
        aptas = self._terreno(ahora)
        if not aptas:
            return self._estado(ahora, "sin_datos", "no hay monedas de contado verificadas (python -m carry.terreno)")
        marcas, dec = self._contexto_perp()
        self.perp.sz_decimales = dec
        self.perp.comision_pct, self.perp.apalancamiento = self.c["comision_perp_pct"], max(1, self.c["apalancamiento_perp"])
        self._recoger_contado()

        hist, bases, mids = {}, {}, {}
        for coin, t in sorted(aptas.items()):
            reg = self._registros_funding(coin, ahora)
            hist[coin] = [float(r["fundingRate"]) * 100 for r in sorted(reg, key=lambda x: x["time"])]
            mids[coin] = t["mid"]
            if coin in marcas:
                bases[coin] = (t["mid"] / marcas[coin] - 1) * 100
        for coin in list(self.cartera["perp"]):                           # funding real cobrado
            if coin in marcas:
                cobro = self.perp.acreditar_funding(coin, self._cache_funding.get(coin, (0, []))[1], marcas[coin])
                if abs(cobro) > 0:
                    self.cartera["posiciones"][coin]["funding_usd"] = self.cartera["perp"][coin]["funding_usd"]
        cierres = self._salidas(ahora, aptas, hist, bases, marcas)
        apertura = self._entradas(ahora, aptas, hist, bases, marcas, mids)
        self._recoger_contado()
        self._guardar()
        return self._estado(ahora, "activo", None, aptas=aptas, hist=hist, bases=bases, marcas=marcas, mids=mids,
                            cierres=cierres, apertura=apertura)

    def _salidas(self, ahora, aptas, hist, bases, marcas):
        hechos = []
        for coin, pos in list(self.cartera["posiciones"].items()):
            if coin in self.cartera["congeladas"] or coin not in aptas:
                continue
            t = aptas[coin]
            try:
                l_spot, l_perp = self._libros(coin, t["par"])
            except Exception as e:
                self.registro.anotar("carry_alerta", coin=coin, mensaje=f"no pude leer los libros para evaluar la salida ({e})")
                continue
            horq = terreno.resumen_libro(l_spot, t["mid"])[0]
            salir, motivo = logica.evaluar_salida(
                pos, {"funding_hist": hist.get(coin), "base_pct": bases.get(coin), "precio_perp": marcas.get(coin),
                      "horquilla_spot_pct": horq}, self.c, ahora)
            if not salir:
                continue
            self.perp.libro = libro_simple(l_perp)
            r = cerrar_par(pos, self.perp, self.spot, libro_simple(l_spot), self.c, self.registro, motivo,
                           t.get("sz_decimals", 4), ahora)
            self._recoger_contado()
            if r["estado"] == "cerrado":
                self.cartera["cerradas"].append(dict(r["resultado"], ts=ahora, capital_usd=pos.get("capital_usd")))
                del self.cartera["posiciones"][coin]
                hechos.append(r["resultado"])
            elif r["estado"] == "desequilibrio":
                self.cartera["congeladas"][coin] = r["motivo"]
        return hechos

    def _entradas(self, ahora, aptas, hist, bases, marcas, mids):
        ops = logica.oportunidades(hist, bases, aptas, self.c, abiertas=tuple(self.cartera["posiciones"]) + tuple(self.cartera["congeladas"]))
        self._ultimas_oportunidades = ops
        if not ops["entrar"]:
            return None
        cuenta = self._equity(marcas, mids)
        abiertas = [{"coin": k, "capital_usd": v.get("capital_usd", 0)} for k, v in self.cartera["posiciones"].items()]
        for op in ops["entrar"]:
            coin, t = op["coin"], aptas[op["coin"]]
            tam = logica.tamano(cuenta, abiertas, coin, self.c)
            if not tam["ok"]:
                self._ultimo_motivo_tamano = tam["motivo"]
                continue
            nec = tam["notional_usd"] * 1.01
            if self.cartera["libre_usd"] < nec + tam["margen_perp_usd"] * 1.02:
                continue
            try:
                l_spot, l_perp = self._libros(coin, t["par"])
            except Exception as e:
                self.registro.anotar("carry_alerta", coin=coin, mensaje=f"no pude leer los libros para abrir ({e})")
                continue
            self.cartera["libre_usd"] -= nec
            self.spot.traspasar(nec, "dinero simulado para comprar el contado del carry")
            self.perp.libro = libro_simple(l_perp)
            r = abrir_par(coin, tam["notional_usd"], self.perp, self.spot, libro_simple(l_spot), t["mid"], self.c, self.registro,
                          t.get("sz_decimals", 4), ahora)
            self._recoger_contado()
            if r["estado"] == "abierto":
                pos = dict(r["posicion"], apalancamiento=tam["apalancamiento"], capital_usd=tam["capital_usd"],
                           funding_anual_entrada_pct=op["funding_anual_pct"], base_entrada_pct=op["base_pct"], funding_usd=0.0,
                           abierta_ms=int(ahora * 1000))
                self.cartera["posiciones"][coin] = pos
                self.cartera["perp"][coin]["abierta_ms"] = int(ahora * 1000)
                return {"coin": coin, "notional_usd": tam["notional_usd"]}
            if r["estado"] == "desequilibrio":
                self.cartera["congeladas"][coin] = r["motivo"]
                return {"coin": coin, "error": r["motivo"]}
        return None

    # ------------------------------------------------------------ estado para el panel
    def _estado(self, ahora, estado, motivo, aptas=None, hist=None, bases=None, marcas=None, mids=None, cierres=None, apertura=None):
        marcas, mids, bases = marcas or {}, mids or {}, bases or {}
        posiciones = []
        for coin, p in self.cartera["posiciones"].items():
            marca, mid = marcas.get(coin, p["entrada_perp"]), mids.get(coin, p["entrada_spot"])
            base_usd = (p["entrada_perp"] - marca) * p["sz"] + (mid - p["entrada_spot"]) * p["sz"]
            recientes = (hist or {}).get(coin, [])[-12:]
            posiciones.append({
                "coin": coin, "abierta_ts": p["abierta_ts"], "horas": round((ahora - p["abierta_ts"]) / 3600, 1), "sz": p["sz"],
                "notional_usd": p["notional_usd"], "capital_usd": p.get("capital_usd"), "entrada_perp": p["entrada_perp"],
                "entrada_spot": p["entrada_spot"], "marca_perp": marca, "precio_spot": mid, "base_pct": bases.get(coin),
                "funding_usd": round(p.get("funding_usd", 0.0), 4), "comisiones_usd": round(p["comisiones_apertura"], 4),
                "base_usd": round(base_usd, 4), "congelada": self.cartera["congeladas"].get(coin),
                "funding_anual_actual_pct": round(sum(recientes) / len(recientes) * logica.HORAS_ANIO, 2) if recientes else None,
                "neto_estimado_usd": round(p.get("funding_usd", 0.0) + base_usd - p["comisiones_apertura"], 4),
                "distancia_liquidacion_pct": round((p["entrada_perp"] * (1 + logica.distancia_liquidacion_pct(p["apalancamiento"], self.c) / 100) - marca) / marca * 100, 1)})
        ops = getattr(self, "_ultimas_oportunidades", {"entrar": [], "descartadas": {}})
        radar = []
        for coin in sorted(hist or {}):
            f = logica.funding_esperado(hist[coin], self.c)
            if f:
                radar.append({"coin": coin, "funding_anual_pct": round(f["anual_pct"], 2), "positivas_pct": round(f["positivas_pct"], 1),
                              "base_pct": None if bases.get(coin) is None else round(bases[coin], 4),
                              "horas_amortizacion": None if f["h_pct"] <= 0 else round(logica.horas_amortizacion(f["h_pct"], self.c), 1)})
        cer = self.cartera["cerradas"]
        equity = self._equity(marcas, mids)
        out = {"ts": ahora, "estado": estado, "motivo": motivo, "simulado": True, "intervalo_s": self.extra["intervalo_s"],
               "cuenta": {"inicial_usd": round(self.cartera["cuenta_inicial_usd"], 2), "equity_usd": round(equity, 2),
                          "libre_usd": round(self.cartera["libre_usd"], 2),
                          "rendimiento_usd": round(equity - self.cartera["cuenta_inicial_usd"], 2)},
               "posiciones": posiciones, "radar": radar, "oportunidades": ops["entrar"], "descartadas": ops["descartadas"],
               "congeladas": self.cartera["congeladas"], "cerradas": cer[-20:],
               "resumen": {"n_cerradas": len(cer), "pnl_neto_usd": round(sum(x["pnl_neto_usd"] for x in cer), 4),
                           "funding_cobrado_usd": round(sum(x["funding_cobrado_usd"] for x in cer) + sum(x["funding_usd"] for x in posiciones), 4),
                           "comisiones_usd": round(sum(x["comisiones_usd"] for x in cer), 4)},
               "criterios": {k: self.c[k] for k in ("funding_min_anual_pct", "horas_amortizacion_max", "positivas_min_pct", "base_max_pct",
                                                    "capital_max_pct", "max_posiciones", "apalancamiento_perp", "horas_max")},
               "coste_ida_vuelta_pct": logica.coste_ida_vuelta_pct(self.c),
               "monedas_verificadas": sorted(aptas) if aptas else [],
               "ultima_apertura": apertura, "ultimos_cierres": cierres or []}
        _escribir_json(self.ruta_estado, out)
        return out


def _epoch(txt):
    try:
        return float(calendar.timegm(time.strptime(txt, "%Y-%m-%dT%H:%M:%SZ")))
    except (TypeError, ValueError):
        return 0.0


def bucle(raiz=AQUI):
    from instancia import InstanciaDuplicada, _Bloqueo
    bloqueo = _Bloqueo(os.path.join(raiz, "carry.lock"))
    try:
        bloqueo.tomar()
    except InstanciaDuplicada:
        print("Ya hay un motor de carry en marcha.")
        return 1
    motor = MotorCarry(raiz)
    print("Carry SIMULADO en marcha (dinero ficticio, solo lectura de la API pública). Ctrl+C para parar.")
    while True:
        try:
            r = motor.pasada()
            print(time.strftime("%H:%M:%S"), r["estado"], f"· {len(r['posiciones'])} abiertas · equity {r['cuenta']['equity_usd']} $", flush=True)
        except KeyboardInterrupt:
            return 0
        except Exception as e:                                   # un fallo de red o de datos no debe parar el motor
            motor.registro.anotar("carry_alerta", mensaje=f"fallo en la pasada: {type(e).__name__}: {e}")
            print("fallo en la pasada:", type(e).__name__, e, flush=True)
        try:
            time.sleep(motor.extra["intervalo_s"])
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(bucle())

