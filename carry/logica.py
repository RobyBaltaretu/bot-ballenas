"""Fase 1 del carry: la lógica pura. Sin red, sin órdenes, sin estado; todo son funciones de datos.

Se cobra el funding de un perpetuo CORTO cubierto con la misma cantidad COMPRADA al contado, de modo que el precio
no importa. Solo se gana si el funding cobrado supera las cuatro operaciones (abrir y cerrar cada pata) y lo que se
separe la base entre los dos precios. Las tasas de funding entran como % por hora (positivo = los largos pagan a los
cortos, es decir, lo que nos interesa).

No hay stop de precio: la cobertura es la otra pata. El riesgo real es de margen (el corto en perpetuo puede acercarse
a la liquidación en una subida fuerte aunque el contado gane lo mismo, porque están en cuentas separadas), de base y de
que el funding cambie de signo.
"""

import math

CFG_DEFECTO = {
    "comision_perp_pct": 0.045,        # taker nivel 0
    "comision_spot_pct": 0.07,         # taker nivel 0 del contado
    "deslizamiento_pct": 0.02,         # por operación, sobre el nocional
    "funding_min_anual_pct": 20.0,     # funding esperado mínimo para entrar (el del laboratorio)
    "horas_amortizacion_max": 72,      # las 4 comisiones deben recuperarse en este plazo
    "positivas_min_pct": 70.0,         # % de las últimas 48 h con funding positivo
    "semivida_funding_h": 24,          # peso de lo reciente en el funding esperado
    "base_max_pct": 0.5,               # |base| máxima para entrar
    "base_salida_pct": 1.0,            # base que obliga a salir
    "funding_salida_anual_pct": 5.0,   # funding medio por debajo de esto durante `horas_funding_bajo` horas = salir
    "horas_funding_bajo": 12,
    "horas_max": 24 * 14,
    "capital_max_pct": 50.0,           # % de la cuenta que puede estar en carry (las dos patas)
    "max_posiciones": 3,
    "max_por_moneda_pct": 20.0,        # % de la cuenta en una moneda
    "apalancamiento_perp": 2,          # del corto; el contado va sin apalancar
    "apalancamiento_max_moneda": 20,   # para estimar el margen de mantenimiento
    "liquidacion_salida_pct": 15.0,    # salir si el precio está a menos de esto % de la liquidación del corto
    "notional_min_usd": 10.0,          # mínimo por pata
}
HORAS_ANIO = 24 * 365


def cfg(**cambios):
    return dict(CFG_DEFECTO, **cambios)


def coste_ida_vuelta_pct(c=None):
    """% del nocional que cuestan las cuatro operaciones (perp abrir y cerrar, contado comprar y vender)."""
    c = c or CFG_DEFECTO
    return round(2 * (c["comision_perp_pct"] + c["comision_spot_pct"]) + 4 * c["deslizamiento_pct"], 4)


def funding_esperado(historial_h, c=None):
    """Funding esperado de una moneda a partir de sus tasas horarias recientes (la más antigua primero).
    Media ponderada (lo reciente pesa más), no el último valor. None si no hay datos suficientes (< 24 horas)."""
    c = c or CFG_DEFECTO
    xs = [float(x) for x in historial_h if x is not None and math.isfinite(float(x))]
    if len(xs) < 24:
        return None
    n = len(xs)
    pesos = [0.5 ** ((n - 1 - i) / c["semivida_funding_h"]) for i in range(n)]
    h_pct = sum(p * x for p, x in zip(pesos, xs)) / sum(pesos)
    ultimas = xs[-48:]
    return {"h_pct": h_pct, "anual_pct": h_pct * HORAS_ANIO,
            "positivas_pct": 100 * sum(1 for x in ultimas if x > 0) / len(ultimas), "horas_datos": n}


def horas_amortizacion(funding_h_pct, c=None):
    """Horas que tarda el funding en pagar las cuatro operaciones. inf si el funding no es positivo."""
    if not funding_h_pct or funding_h_pct <= 0:
        return math.inf
    return coste_ida_vuelta_pct(c) / funding_h_pct


def oportunidades(funding_hist, base_pct, terreno, c=None, abiertas=()):
    """Monedas donde entrar. funding_hist: {coin: [tasas horarias %]}. base_pct: {coin: %}. terreno: {coin: datos de
    carry.terreno} con las monedas de contado aptas. Devuelve [{coin, ...}] de mejor a peor funding esperado, y los
    motivos de las descartadas en 'descartadas'."""
    c = c or CFG_DEFECTO
    ok, descartadas = [], {}
    for coin in sorted(terreno):
        if coin in abiertas:
            descartadas[coin] = "ya hay carry abierto"
            continue
        f = funding_esperado(funding_hist.get(coin) or [], c)
        if f is None:
            descartadas[coin] = "pocos datos de funding"
            continue
        b = base_pct.get(coin)
        h = horas_amortizacion(f["h_pct"], c)
        if f["anual_pct"] < c["funding_min_anual_pct"]:
            descartadas[coin] = f"funding {f['anual_pct']:.1f} %/año < {c['funding_min_anual_pct']} %"
        elif f["positivas_pct"] < c["positivas_min_pct"]:
            descartadas[coin] = f"funding positivo solo el {f['positivas_pct']:.0f} % de las últimas horas"
        elif h > c["horas_amortizacion_max"]:
            descartadas[coin] = f"las comisiones tardan {h:.0f} h en recuperarse (máx. {c['horas_amortizacion_max']})"
        elif b is None or abs(b) > c["base_max_pct"]:
            descartadas[coin] = f"base {b} % fuera de ±{c['base_max_pct']} %"
        else:
            ok.append({"coin": coin, "funding_anual_pct": round(f["anual_pct"], 2), "funding_h_pct": f["h_pct"],
                       "positivas_pct": round(f["positivas_pct"], 1), "horas_amortizacion": round(h, 1), "base_pct": b})
    return {"entrar": sorted(ok, key=lambda x: -x["funding_anual_pct"]), "descartadas": descartadas}


def tamano(cuenta_usd, posiciones, coin, c=None):
    """Cuánto poner en una posición nueva. cuenta_usd = capital total simulado (perpetuos + contado). posiciones =
    [{coin, capital_usd}] ya abiertas. Devuelve {ok, notional_usd, margen_perp_usd, capital_usd, motivo}."""
    c = c or CFG_DEFECTO
    lev = max(1, c["apalancamiento_perp"])
    en_uso = sum(p["capital_usd"] for p in posiciones)
    if len(posiciones) >= c["max_posiciones"]:
        return {"ok": False, "motivo": f"máximo de {c['max_posiciones']} posiciones de carry"}
    libre = cuenta_usd * c["capital_max_pct"] / 100 - en_uso
    tope_moneda = cuenta_usd * c["max_por_moneda_pct"] / 100 - sum(p["capital_usd"] for p in posiciones if p["coin"] == coin)
    capital = min(libre, tope_moneda)
    # Capital de la posición = contado (N) + margen del corto (N / lev)  ->  N = capital / (1 + 1/lev)
    notional = capital / (1 + 1 / lev)
    if capital <= 0 or notional < c["notional_min_usd"]:
        return {"ok": False, "motivo": f"capital disponible {max(capital, 0):.2f} $ da menos de {c['notional_min_usd']} $ por pata"}
    return {"ok": True, "notional_usd": round(notional, 2), "margen_perp_usd": round(notional / lev, 2),
            "capital_usd": round(notional * (1 + 1 / lev), 2), "apalancamiento": lev}


def distancia_liquidacion_pct(apalancamiento, c=None):
    """% que puede SUBIR el precio desde la entrada hasta la liquidación de un corto aislado (estimación: 1/lev menos el
    margen de mantenimiento, que es 1/(2·apalancamiento máximo de la moneda))."""
    c = c or CFG_DEFECTO
    return round(100 / max(1, apalancamiento) - 100 / (2 * c["apalancamiento_max_moneda"]), 2)


def evaluar_salida(pos, mercado, c=None, ahora=0):
    """¿Hay que cerrar el carry? pos: {coin, abierta_ts, entrada_perp, apalancamiento}. mercado: {funding_hist,
    base_pct, precio_perp, horquilla_spot_pct}. Devuelve (salir, motivo). Sin stop de precio."""
    c = c or CFG_DEFECTO
    liq = pos["entrada_perp"] * (1 + distancia_liquidacion_pct(pos["apalancamiento"], c) / 100)
    precio = mercado.get("precio_perp")
    if precio and (liq - precio) / precio * 100 < c["liquidacion_salida_pct"]:
        return True, f"el precio está a {(liq - precio) / precio * 100:.1f} % de la liquidación del corto"
    b = mercado.get("base_pct")
    if b is not None and abs(b) > c["base_salida_pct"]:
        return True, f"la base se abrió a {b:+.2f} % (máx. {c['base_salida_pct']} %)"
    recientes = [x for x in (mercado.get("funding_hist") or [])[-c["horas_funding_bajo"]:] if x is not None]
    if len(recientes) >= c["horas_funding_bajo"] and sum(recientes) / len(recientes) * HORAS_ANIO < c["funding_salida_anual_pct"]:
        return True, f"funding medio de {sum(recientes) / len(recientes) * HORAS_ANIO:.1f} %/año durante {len(recientes)} h"
    if ahora and (ahora - pos["abierta_ts"]) / 3600 > c["horas_max"]:
        return True, f"tiempo máximo de {c['horas_max']} h"
    spread = mercado.get("horquilla_spot_pct")
    if spread is not None and spread > 3 * 0.05:
        return True, f"la liquidez del contado empeoró (horquilla {spread:.3f} %)"
    return False, None
