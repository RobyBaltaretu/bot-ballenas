"""ESTUDIO C — El carry de funding «realista» del laboratorio, medido por PERIODOS y solo con datos recientes. SOLO INVESTIGACIÓN.

Pregunta única: con las mismas reglas que `laboratorio.carry_realista` (corto en el perpetuo + largo en contado cuando el
funding anualizado supera el umbral; sale cuando baja de la mitad; 4 comisiones; riesgo de base incluido), ¿cuánto rindió
en 2025 y en 2026 sobre el capital de las dos patas, restando el tipo sin riesgo?

Es la medición que pedía la investigación externa: dos análisis independientes dicen que el carry de nivel está comprimido
y que su Sharpe alto es un artefacto de cobrar casi todos los días. Aquí no se calcula Sharpe: se mira la rentabilidad
neta por periodo, el peor momento de la base y cuánto se gana frente al efectivo.

Datos (solo cachés locales): funding horario de Hyperliquid (`datos_backtest/funding_<moneda>.json`), contado de Binance de
8 h y perpetuo de Binance de 4 h para la base (el laboratorio usa el perpetuo de Hyperliquid; aquí la base mide contado
frente a perpetuo del mismo exchange, que es lo que se hedgearía allí). Monedas: las verificadas con contado en
Hyperliquid (BTC, ETH, SOL, HYPE, ZEC).

Reglas fijadas de antemano: umbrales 10, 20 y 40 % anual (los del laboratorio; se informan los tres, sin elegir);
comisiones 2 × 0,045 % + 2 × 0,070 % (0,23 % ida y vuelta, como el laboratorio); tipo sin riesgo supuesto 4,0 % anual.
Criterio: rentabilidad anual neta sobre el capital reservado (dos patas, todas las monedas, también el tiempo sin
operar) en 2026 > tipo sin riesgo, con umbral 20 % y en al menos 2 de los 3 umbrales.
"""

import argparse
import datetime
import json
import os
import time

from estudios_ext import datos as dt
from senales import SerieFunding

AQUI = dt.AQUI
MONEDAS = ("BTC", "ETH", "SOL", "HYPE", "ZEC")
UMBRALES = (10, 20, 40)
COSTE_PCT = 2 * 0.045 + 2 * 0.070
TIPO_SIN_RIESGO_PCT = 4.0
SALIDA = os.path.join(AQUI, "registro", "estudio_carry_2026.json")
H8 = 8 * 3600


def _json(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def cargar(moneda, carpeta=AQUI):
    """(SerieFunding HL, {t_cierre_s: cierre perpetuo 4h}, {t_cierre_s: cierre contado 8h}) o None si faltan datos."""
    fr = _json(os.path.join(carpeta, "datos_backtest", f"funding_{moneda}.json"))
    perp = _json(os.path.join(carpeta, "datos_backtest", "externo", f"binance_{moneda}USDT_4h_v2.json"))
    spot = _json(os.path.join(carpeta, "datos_backtest", "externo", f"binance_spot_{moneda}USDT_8h_v2.json"))
    if not fr or not perp or len(spot) < 50:
        return None
    pc = {int(v["t"]) // 1000 + 4 * 3600: float(v["c"]) for v in perp}
    sc = {int(v["t"]) // 1000 + H8: float(v["c"]) for v in spot}
    return SerieFunding(fr), pc, sc


def operaciones(moneda, datos, umbral, coste=COSTE_PCT):
    """Mismo bucle que `laboratorio.carry_realista`, para una moneda y un umbral. r en % del tamaño de UNA pata."""
    fs, pc, sc = datos
    trades = []
    t = max(fs.t[0] + 24 * 3600, min(sc) + H8)
    t = t - t % H8 + H8
    fin = min(fs.t[-1], max(sc))
    abierta, peor = None, 0.0
    while t <= fin:
        media = fs.media(t, 24)
        anual = media * 24 * 365 if media is not None else None
        p, s = pc.get(t), sc.get(t)
        b = (p / s - 1) if p and s else None                 # base: perpetuo frente a contado
        if abierta is None and anual is not None and anual >= umbral and b is not None:
            abierta, peor = (t, b), 0.0
        elif abierta is not None:
            if b is not None:
                peor = min(peor, (abierta[1] - b) * 100)
            if (anual is None or anual < umbral / 2) and b is not None:
                cobrado = fs.suma(abierta[0], t)
                r = cobrado + (abierta[1] - b) * 100 - coste
                trades.append({"t": abierta[0], "cierre_ts": t, "moneda": moneda, "r": round(r, 4),
                               "funding_pct": round(cobrado, 4), "base_pct": round((abierta[1] - b) * 100, 4),
                               "peor_base_pct": round(peor, 4), "dias": round((t - abierta[0]) / 86400, 1)})
                abierta = None
        t += H8
    return trades


def _ts(anio, mes=1, dia=1):
    return datetime.datetime(anio, mes, dia, tzinfo=datetime.timezone.utc).timestamp()


def periodo(trades, desde, hasta, n_monedas):
    """Resumen de las operaciones CERRADAS dentro de [desde, hasta). Rentabilidad sobre el capital reservado: dos patas
    por cada moneda del estudio durante TODO el periodo, haya o no operación abierta."""
    ts = [x for x in trades if desde <= x["cierre_ts"] < hasta]
    anios = (hasta - desde) / (365 * 86400)
    out = {"n": len(ts), "dias_en_operacion": round(sum(x["dias"] for x in ts), 1)}
    if not ts:
        out.update(rentab_neta_capital_reservado_pct=0.0)
        return out
    r_total = sum(x["r"] for x in ts)
    out.update(funding_medio_pct=round(sum(x["funding_pct"] for x in ts) / len(ts), 4),
               base_media_pct=round(sum(x["base_pct"] for x in ts) / len(ts), 4),
               peor_base_pct=round(min(x["peor_base_pct"] for x in ts), 3),
               ganadoras_pct=round(sum(1 for x in ts if x["r"] > 0) / len(ts) * 100, 1),
               r_total_pct_de_una_pata=round(r_total, 3),
               rentab_en_operacion_pct=round(r_total / 2 / max(1.0, out["dias_en_operacion"]) * 365, 2),
               rentab_neta_capital_reservado_pct=round(r_total / (2 * n_monedas) / anios, 3))
    return out


def informe(carpeta=AQUI, ahora=None, monedas=MONEDAS):
    ahora = ahora or time.time()
    datos = {m: cargar(m, carpeta) for m in monedas}
    usadas = [m for m, d in datos.items() if d]
    res = {"estudio": "C_carry_por_periodos", "generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ahora)),
           "monedas_usadas": usadas, "monedas_sin_datos": [m for m in monedas if m not in usadas],
           "coste_ida_vuelta_pct": COSTE_PCT, "tipo_sin_riesgo_pct": TIPO_SIN_RIESGO_PCT, "umbrales": {}}
    marcos = {"2024_2s": (_ts(2024, 7), _ts(2025, 1)), "2025": (_ts(2025), _ts(2026)), "2026_hasta_hoy": (_ts(2026), ahora)}
    for u in UMBRALES:
        trades = [x for m in usadas for x in operaciones(m, datos[m], u)]
        res["umbrales"][str(u)] = {k: periodo(trades, a, b, len(usadas)) for k, (a, b) in marcos.items()}
        res["umbrales"][str(u)]["por_moneda_2026"] = {m: periodo([x for x in trades if x["moneda"] == m], *marcos["2026_hasta_hoy"], 1)
                                                      for m in usadas}
    res["veredicto"] = veredicto(res)
    return res


def veredicto(res):
    def neta(u):
        return res["umbrales"][str(u)]["2026_hasta_hoy"].get("rentab_neta_capital_reservado_pct", 0.0)
    supera = [u for u in UMBRALES if neta(u) > res["tipo_sin_riesgo_pct"]]
    ok = neta(20) > res["tipo_sin_riesgo_pct"] and len(supera) >= 2
    return {"criterio": "rentabilidad neta 2026 sobre capital reservado > tipo sin riesgo con umbral 20 % y en ≥ 2 de 3 umbrales",
            "umbrales_que_superan": supera, "supera": ok,
            "rentab_2026_por_umbral": {str(u): neta(u) for u in UMBRALES},
            "lectura": ("El carry de 2026 supera al efectivo." if ok else
                        "El carry de 2026 NO supera al efectivo con estos criterios: se archiva hasta que cambie.")}


def main():
    ap = argparse.ArgumentParser(description="Estudio C: carry por periodos (solo investigación, sin red)")
    ap.add_argument("--salida", default=SALIDA)
    args = ap.parse_args()
    res = informe()
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({"monedas": res["monedas_usadas"], "veredicto": res["veredicto"],
                      "umbral_20": {k: v for k, v in res["umbrales"]["20"].items() if k != "por_moneda_2026"}},
                     ensure_ascii=False, indent=1))
    print("Guardado en", args.salida)


if __name__ == "__main__":
    main()
