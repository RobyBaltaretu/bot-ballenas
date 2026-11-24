"""Fase 2 del carry: cuenta de CONTADO SIMULADA. Dinero ficticio; no habla con ningún exchange ni firma nada.

Las órdenes se ejecutan contra un libro (el real, leído de la API pública, o uno de prueba) y comen niveles hasta llenar:
si no hay profundidad suficiente o el deslizamiento pasa del máximo, se rechaza entera (como una orden IOC que no se llena).
Estado en papel_spot.json (escritura atómica), aparte de papel.json.
"""

import json
import math
import os
import time

from compat import reemplazar

AQUI =os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA = os.path.join(AQUI, "papel_spot.json")


class ErrorSpot(RuntimeError):
    pass


def _bajar(x, decimales):
    f = 10 ** decimales
    return math.floor(x * f + 1e-9) / f


class PapelSpot:
    def __init__(self, ruta=RUTA, usdc=0.0):
        self.ruta = ruta
        self.d = {"version": 1, "usdc": float(usdc), "monedas": {}, "fills": [], "traspasos": [], "n_fill": 0}
        try:
            with open(ruta, encoding="utf-8") as fh:
                self.d = json.load(fh)
        except (OSError, ValueError):
            pass

    # ------------------------------------------------------------ persistencia
    def guardar(self):
        tmp = self.ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.d, fh, ensure_ascii=False, indent=1)
        reemplazar(tmp, self.ruta)       # con reintentos: en Windows falla si otro programa tiene el archivo abierto

    # ------------------------------------------------------------ dinero
    def traspasar(self, usd, motivo="traspaso simulado con la cuenta de perpetuos"):
        """Mueve USDC SIMULADOS entre la cuenta de perpetuos y esta (positivo = entra). Solo simulado: en real mover fondos
        entre spot y perpetuos es una acción de cuenta que queda fuera de este plan."""
        if usd < 0 and self.d["usdc"] + usd < -1e-9:
            raise ErrorSpot(f"no hay {abs(usd):.2f} USDC simulados para devolver (hay {self.d['usdc']:.2f})")
        self.d["usdc"] += usd
        self.d["traspasos"].append({"ts": time.time(), "usd": usd, "motivo": motivo})
        del self.d["traspasos"][:-200]
        self.guardar()

    def cantidad(self, coin):
        return self.d["monedas"].get(coin, 0.0)

    def valor(self, precios):
        return self.d["usdc"] + sum(q * precios.get(c, 0.0) for c, q in self.d["monedas"].items())

    # ------------------------------------------------------------ órdenes
    def ejecutar(self, coin, lado, cantidad, libro, comision_pct, sz_decimales=4, max_deslizamiento_pct=0.5):
        """Orden de mercado contra el libro. lado 'compra'|'venta'. libro = {"compras": [(px, sz)...], "ventas": [...]}.
        Devuelve el fill {px, sz, usd, comision}. Lanza ErrorSpot si no se llena entera."""
        if lado not in ("compra", "venta"):
            raise ErrorSpot(f"lado desconocido: {lado}")
        qty = _bajar(cantidad, sz_decimales)
        if qty <= 0:
            raise ErrorSpot("cantidad nula tras redondear a los decimales de la moneda")
        niveles = sorted(libro["ventas"] if lado == "compra" else libro["compras"], key=lambda n: n[0], reverse=(lado == "venta"))
        if not niveles:
            raise ErrorSpot("libro vacío")
        faltan, coste, ref = qty, 0.0, niveles[0][0]
        for px, sz in niveles:
            t = min(faltan, sz)
            coste += t * px
            faltan -= t
            if faltan <= 1e-12:
                break
        if faltan > 1e-9:
            raise ErrorSpot(f"no hay profundidad: faltan {faltan:g} de {qty:g} {coin}")
        px_medio = coste / qty
        desliz = abs(px_medio / ref - 1) * 100
        if desliz > max_deslizamiento_pct:
            raise ErrorSpot(f"deslizamiento {desliz:.3f} % > {max_deslizamiento_pct} %")
        comision = coste * comision_pct / 100
        if lado == "compra":
            if self.d["usdc"] < coste + comision - 1e-9:
                raise ErrorSpot(f"falta saldo: hacen falta {coste + comision:.2f} USDC y hay {self.d['usdc']:.2f}")
            self.d["usdc"] -= coste + comision
            self.d["monedas"][coin] = self.cantidad(coin) + qty
        else:
            if self.cantidad(coin) < qty - 1e-9:
                raise ErrorSpot(f"no hay {qty:g} {coin} para vender (hay {self.cantidad(coin):g})")
            self.d["usdc"] += coste - comision
            resto = self.cantidad(coin) - qty
            if resto > 1e-12:
                self.d["monedas"][coin] = resto
            else:
                self.d["monedas"].pop(coin, None)
        self.d["n_fill"] += 1
        fill = {"id": f"spot-{self.d['n_fill']}", "ts": time.time(), "coin": coin, "lado": lado, "sz": qty,
                "px": px_medio, "px_ref": ref, "deslizamiento_pct": round(desliz, 5), "usd": coste, "comision": comision}
        self.d["fills"].append(fill)
        del self.d["fills"][:-500]
        self.guardar()
        return fill
