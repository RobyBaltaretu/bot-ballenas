"""Fase 2 del carry: abrir y cerrar las DOS patas con atomicidad razonable. Todo simulado y con adaptadores.

Orden de apertura: primero el contado (si falla, no hay nada abierto) y después el corto del perpetuo. Si el corto falla,
se deshace el contado; si el deshacer también falla, queda DESEQUILIBRIO y el carry de esa moneda se congela y avisa.
Si el corto se llena a medias, el contado se iguala a lo que realmente se llenó (el perpetuo manda: es la exposición).
Cierre: primero el corto (quita el riesgo de margen) y después se vende el contado.

Adaptador del perpetuo (lo que la fase 3 conectará a papel.py/gestor.py; aquí solo hay uno de prueba):
    perp.abrir_corto(coin, notional_usd, precio_ref) -> {"px", "sz", "comision"}      (lanza ErrorPata si falla)
    perp.cerrar_corto(coin, sz)                      -> {"px", "sz", "comision", "pnl"}
    perp.funding_cobrado(coin, desde_ts)             -> USD cobrados (con signo)
Nada de esto envía órdenes reales ni se conecta a una cuenta.
"""

import json
import os
import time

from carry.papel_spot import ErrorSpot

TOLERANCIA_PATAS = 0.02          # diferencia máxima entre las dos cantidades antes de igualar


class ErrorPata(RuntimeError):
    pass


class RegistroCarry:
    """Eventos del carry en registro/carry.jsonl (aparte del ledger: la fase 3 los lleva allí, con su tipo propio)."""

    def __init__(self, ruta):
        self.ruta = ruta

    def anotar(self, tipo, **datos):
        os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
        with open(self.ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(datos, tipo=tipo, ts=time.time()), ensure_ascii=False) + "\n")

    def leer(self):
        try:
            with open(self.ruta, encoding="utf-8") as fh:
                return [json.loads(x) for x in fh if x.strip()]
        except OSError:
            return []


def abrir_par(coin, notional_usd, perp, spot, libro_spot, precio_ref, c, registro, sz_decimales=4, ahora=None):
    """Devuelve {"estado": "abierto"|"deshecho"|"desequilibrio", ...}. Nunca deja una pata sola sin decirlo."""
    ahora = ahora or time.time()
    cantidad = notional_usd / precio_ref
    try:
        f_spot = spot.ejecutar(coin, "compra", cantidad, libro_spot, c["comision_spot_pct"], sz_decimales)
    except ErrorSpot as e:
        registro.anotar("carry_alerta", coin=coin, mensaje=f"no se abre: falló el contado ({e})")
        return {"estado": "deshecho", "motivo": f"contado: {e}", "patas_abiertas": 0}
    try:
        f_perp = perp.abrir_corto(coin, notional_usd, precio_ref)
    except ErrorPata as e:
        try:                                                    # deshacer el contado
            v = spot.ejecutar(coin, "venta", f_spot["sz"], libro_spot, c["comision_spot_pct"], sz_decimales, max_deslizamiento_pct=5.0)
            registro.anotar("carry_alerta", coin=coin, mensaje=f"no se abre: falló el corto ({e}); contado deshecho",
                            perdida_deshacer_usd=round(f_spot["usd"] + f_spot["comision"] - (v["usd"] - v["comision"]), 4))
            return {"estado": "deshecho", "motivo": f"corto: {e}", "patas_abiertas": 0}
        except ErrorSpot as e2:
            registro.anotar("carry_alerta", coin=coin, grave=True,
                            mensaje=f"DESEQUILIBRIO: falló el corto ({e}) y no pude deshacer el contado ({e2}). Carry de {coin} congelado.")
            return {"estado": "desequilibrio", "motivo": f"corto: {e}; deshacer: {e2}", "patas_abiertas": 1, "congelar": coin}
    sz_perp = f_perp["sz"]
    if abs(f_spot["sz"] - sz_perp) / max(sz_perp, 1e-12) > TOLERANCIA_PATAS:
        try:                                                    # el perpetuo manda: se iguala el contado a lo llenado
            if f_spot["sz"] > sz_perp:
                spot.ejecutar(coin, "venta", f_spot["sz"] - sz_perp, libro_spot, c["comision_spot_pct"], sz_decimales, max_deslizamiento_pct=5.0)
            else:
                spot.ejecutar(coin, "compra", sz_perp - f_spot["sz"], libro_spot, c["comision_spot_pct"], sz_decimales, max_deslizamiento_pct=5.0)
        except ErrorSpot as e:
            registro.anotar("carry_alerta", coin=coin, grave=True, mensaje=f"DESEQUILIBRIO: patas de distinto tamaño y no pude igualarlas ({e}).")
            return {"estado": "desequilibrio", "motivo": f"igualar: {e}", "patas_abiertas": 2, "congelar": coin}
    pos = {"coin": coin, "abierta_ts": ahora, "entrada_perp": f_perp["px"], "entrada_spot": f_spot["px"], "sz": sz_perp,
           "notional_usd": notional_usd, "comisiones_apertura": f_perp["comision"] + f_spot["comision"],
           "deslizamiento_apertura_usd": abs(f_spot["px"] - f_spot["px_ref"]) * f_spot["sz"]}
    registro.anotar("carry_apertura", **pos)
    return {"estado": "abierto", "posicion": pos}


def cerrar_par(pos, perp, spot, libro_spot, c, registro, motivo, sz_decimales=4, ahora=None):
    """Cierra primero el corto y luego vende el contado. Si el contado no se vende queda DESEQUILIBRIO (largo sin cubrir)."""
    ahora = ahora or time.time()
    coin = pos["coin"]
    try:
        f_perp = perp.cerrar_corto(coin, pos["sz"])
    except ErrorPata as e:
        registro.anotar("carry_alerta", coin=coin, mensaje=f"no pude cerrar el corto ({e}); sigo con las dos patas abiertas")
        return {"estado": "abierto", "motivo": f"corto: {e}"}
    try:
        f_spot = spot.ejecutar(coin, "venta", pos["sz"], libro_spot, c["comision_spot_pct"], sz_decimales, max_deslizamiento_pct=5.0)
    except ErrorSpot as e:
        registro.anotar("carry_alerta", coin=coin, grave=True,
                        mensaje=f"DESEQUILIBRIO: cerré el corto pero no pude vender el contado ({e}): queda largo sin cobertura.")
        return {"estado": "desequilibrio", "motivo": f"contado: {e}", "congelar": coin}
    funding = perp.funding_cobrado(coin, pos["abierta_ts"])
    pnl_spot = (f_spot["px"] - pos["entrada_spot"]) * pos["sz"]
    pnl_perp = f_perp.get("pnl", (pos["entrada_perp"] - f_perp["px"]) * pos["sz"])
    comisiones = pos["comisiones_apertura"] + f_perp["comision"] + f_spot["comision"]
    resultado = {"coin": coin, "motivo": motivo, "horas": round((ahora - pos["abierta_ts"]) / 3600, 2), "funding_cobrado_usd": round(funding, 4),
                 "comisiones_usd": round(comisiones, 4), "base_usd": round(pnl_spot + pnl_perp, 4),
                 "pnl_neto_usd": round(funding + pnl_spot + pnl_perp - comisiones, 4)}
    registro.anotar("carry_cierre", **resultado)
    return {"estado": "cerrado", "resultado": resultado}
