"""Fase 3 del carry: pata CORTA del perpetuo, SIMULADA. Dinero ficticio; no habla con ningún exchange ni firma nada.

Es una cuenta propia del carry (no toca papel.py ni el ledger del bot). Las órdenes comen niveles de un libro real leído de
la API pública; el margen del corto sale de `libre_usd` de la cartera y vuelve al cerrar con su resultado. El funding se
acredita con las tasas REALES de Hyperliquid (fundingHistory): un corto cobra cuando la tasa es positiva.

Implementa el adaptador que espera ejecucion.abrir_par / cerrar_par:
    abrir_corto(coin, notional_usd, precio_ref) -> {"px", "sz", "comision"}   (ErrorPata si falla)
    cerrar_corto(coin, sz)                      -> {"px", "sz", "comision", "pnl"}
    funding_cobrado(coin, desde_ts)             -> USD cobrados (con signo)
"""

import math

from carry.ejecucion import ErrorPata


def _bajar(x, decimales):
    f = 10 ** decimales
    return math.floor(x * f + 1e-9) / f


def _barrer(niveles, cantidad):
    """(px medio, px de referencia) al comer niveles [(px, sz)] hasta llenar; None si no hay profundidad."""
    faltan, coste, ref = cantidad, 0.0, niveles[0][0]
    for px, sz in niveles:
        t = min(faltan, sz)
        coste += t * px
        faltan -= t
        if faltan <= 1e-12:
            break
    if faltan > 1e-9:
        return None, ref
    return coste / cantidad, ref


class PerpCortoPapel:
    """cartera: el diccionario de estado de CarteraCarry (se muta aquí; guarda quien lo posee)."""

    def __init__(self, cartera, comision_pct=0.045, apalancamiento=2, max_deslizamiento_pct=0.5):
        self.c = cartera
        self.comision_pct = comision_pct
        self.apalancamiento = max(1, apalancamiento)
        self.max_desliz = max_deslizamiento_pct
        self.libro = None          # {"compras": [(px, sz)], "ventas": [...]} del perpetuo, lo fija el motor antes de operar
        self.sz_decimales = {}     # {coin: decimales del tamaño en el perpetuo}

    def _libro(self, lado):
        if not self.libro:
            raise ErrorPata("sin libro del perpetuo")
        niveles = self.libro["compras" if lado == "venta" else "ventas"]       # un corto VENDE contra las compras
        if not niveles:
            raise ErrorPata("libro del perpetuo vacío")
        return sorted(niveles, key=lambda n: n[0], reverse=(lado == "venta"))

    def abrir_corto(self, coin, notional_usd, precio_ref):
        if coin in self.c["perp"]:
            raise ErrorPata(f"ya hay un corto simulado de {coin}")
        qty = _bajar(notional_usd / precio_ref, self.sz_decimales.get(coin, 4))
        if qty <= 0:
            raise ErrorPata("cantidad nula tras redondear")
        px, ref = _barrer(self._libro("venta"), qty)
        if px is None:
            raise ErrorPata(f"no hay profundidad para vender {qty:g} {coin}")
        desliz = abs(px / ref - 1) * 100
        if desliz > self.max_desliz:
            raise ErrorPata(f"deslizamiento {desliz:.3f} % > {self.max_desliz} %")
        nocional = qty * px
        margen = nocional / self.apalancamiento
        comision = nocional * self.comision_pct / 100
        if self.c["libre_usd"] < margen + comision - 1e-9:
            raise ErrorPata(f"falta margen simulado: hacen falta {margen + comision:.2f} $ y hay {self.c['libre_usd']:.2f} $")
        self.c["libre_usd"] -= margen + comision
        self.c["perp"][coin] = {"sz": qty, "entrada": px, "margen_usd": margen, "apalancamiento": self.apalancamiento,
                                "funding_usd": 0.0, "comision_apertura": comision}
        return {"px": px, "sz": qty, "comision": comision}

    def cerrar_corto(self, coin, sz):
        pos = self.c["perp"].get(coin)
        if not pos:
            raise ErrorPata(f"no hay corto simulado de {coin}")
        px, ref = _barrer(self._libro("compra"), pos["sz"])
        if px is None:
            raise ErrorPata(f"no hay profundidad para recomprar {pos['sz']:g} {coin}")
        comision = pos["sz"] * px * self.comision_pct / 100
        pnl = (pos["entrada"] - px) * pos["sz"]
        self.c["libre_usd"] += pos["margen_usd"] + pnl - comision
        self.c.setdefault("_ultimo_cierre", {})[coin] = {"funding_usd": pos["funding_usd"]}
        del self.c["perp"][coin]
        return {"px": px, "sz": pos["sz"], "comision": comision, "pnl": pnl}

    def funding_cobrado(self, coin, desde_ts):
        """Funding acumulado de esa pata. Si ya se cerró, el motor lo guardó en la posición antes de cerrar."""
        pos = self.c["perp"].get(coin) or self.c.get("_ultimo_cierre", {}).get(coin)
        return float(pos["funding_usd"]) if pos else 0.0

    def acreditar_funding(self, coin, registros, marca):
        """registros: [{"time": ms, "fundingRate": "0.0000125"}]. Acredita lo posterior a lo ya cobrado y devuelve los USD."""
        pos = self.c["perp"].get(coin)
        if not pos:
            return 0.0
        desde = max(pos.get("funding_ms", 0), pos.get("abierta_ms", 0))
        total = 0.0
        for r in sorted(registros, key=lambda x: x["time"]):
            if r["time"] <= desde:
                continue
            total += pos["sz"] * marca * float(r["fundingRate"])      # corto: cobra con tasa positiva, paga con negativa
            pos["funding_ms"] = r["time"]
        pos["funding_usd"] += total
        self.c["libre_usd"] += total
        return total
