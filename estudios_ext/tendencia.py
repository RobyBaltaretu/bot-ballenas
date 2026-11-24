"""ESTUDIO A — Tendencia lenta (conjunto de canales de Donchian). SOLO INVESTIGACIÓN. Reglas fijadas de antemano.

Pregunta única: ¿una cartera solo larga de canales de Donchian de 5 a 360 días, sin objetivo de beneficio, con stop móvil
en la mitad del canal y tamaño por volatilidad, gana dinero NETO de costes y de funding en las monedas líquidas de
Binance, mejor que mantener BTC con la misma volatilidad?

Reglas (no se ajusta ninguna):
  - Velas diarias UTC (6 de 4 h). La decisión se toma al cierre del día d y la posición rinde desde el día d+1.
  - Universo: cada mes, las 15 monedas con más volumen medio de 30 días (≥ 2 M$/día), con ≥ 365 días de historia.
  - 9 ventanas: 5, 10, 20, 30, 60, 90, 150, 250, 360 días. Cada una, por moneda: entra si cierra por encima del máximo de
    los n días anteriores; el stop es la mitad del canal (máx+mín de n días)/2, solo sube; sale si cierra por debajo.
    Sin objetivo y sin tiempo máximo. Si la moneda sale del universo, se cierra.
  - Tamaño de cada porción (moneda × ventana), FIJADO en la entrada: (25 % ÷ volatilidad anual de 90 días) ÷ 15 ÷ 9
    (volatilidad mínima 10 %). Exposición total máxima 2×.
  - Costes: 0,045 % taker + 0,02 % de deslizamiento por lado sobre lo operado. Funding de Binance cobrado/pagado cada día
    sobre lo largo (tasa por defecto 0,03 %/día si falta el dato).

Limitaciones que conoce el estudio: SESGO DE SUPERVIVENCIA (la caché solo tiene monedas que siguen listadas hoy); el
funding y los precios son de Binance, no de Hyperliquid; la fracción de cada porción se mantiene constante entre
entrada y salida (equivale a reequilibrar a diario sin coste).
"""

import argparse
import datetime
import json
import math
import os
import time
from statistics import NormalDist, median

from estudios_ext import datos as dt
from estudios_ext import metricas as mt

AQUI = dt.AQUI
VENTANAS = (5, 10, 20, 30, 60, 90, 150, 250, 360)
VOL_OBJETIVO = 0.25
VENT_VOL = 90
VOL_MINIMA = 0.10
TOPE_EXPOSICION = 2.0
N_MONEDAS = 15
HISTORIA_MIN = 365
VOL_MIN_USD = 2_000_000
COSTE_LADO = 0.00045 + 0.0002
FUNDING_DEFECTO_DIA = 0.0003
N_ESTUDIOS = 3                       # A, B y C: el listón de t se corrige por esto
T_MIN = NormalDist().inv_cdf(1 - 0.05 / N_ESTUDIOS)
FRACCION_HOLDOUT = 0.15
SALIDA = os.path.join(AQUI, "registro", "estudio_tendencia.json")
_EPOCA = datetime.date(1970, 1, 1).toordinal()


def fecha(dia):
    return datetime.date.fromordinal(dia + _EPOCA)


class Mundo:
    """Panel diario alineado: días consecutivos, huecos rellenados con el último cierre (retorno 0, sin volumen)."""

    def __init__(self, panel):
        self.d0, self.d1 = dt.rango_dias(panel)
        self.T = self.d1 - self.d0 + 1
        self.monedas = sorted(panel)
        self.c, self.h, self.l, self.usd, self.valida, self.fund = {}, {}, {}, {}, {}, {}
        for m in self.monedas:
            dias = panel[m]["dias"]
            c, h, l, u, v = [], [], [], [], []
            for j in range(self.T):
                x = dias.get(self.d0 + j)
                if x is not None:
                    c.append(x["c"]); h.append(x["h"]); l.append(x["l"]); u.append(x["usd"]); v.append(True)
                else:                      # hueco (o antes de cotizar): último cierre, sin volumen; 0 antes de cotizar
                    p = c[-1] if c else 0.0
                    c.append(p); h.append(p); l.append(p); u.append(0.0); v.append(False)
            self.c[m], self.h[m], self.l[m], self.usd[m], self.valida[m] = c, h, l, u, v
            self.fund[m] = [panel[m]["funding"].get(self.d0 + j) for j in range(self.T)]
        self.ret = {m: [0.0] + [(self.c[m][j] / self.c[m][j - 1] - 1) if self.c[m][j] and self.c[m][j - 1] else 0.0
                                for j in range(1, self.T)] for m in self.monedas}
        self.primero = {m: next((j for j, ok in enumerate(self.valida[m]) if ok), self.T) for m in self.monedas}

    def vol_anual(self, m, n=VENT_VOL):
        """Volatilidad anual de los n retornos diarios hasta cada día j (inclusive). None si no hay n retornos."""
        r, out = self.ret[m], [None] * self.T
        s1 = s2 = 0.0
        for j in range(self.T):
            s1 += r[j]; s2 += r[j] * r[j]
            if j >= n:
                s1 -= r[j - n]; s2 -= r[j - n] * r[j - n]
            if j >= n and j - n + 1 > self.primero[m]:
                var = max(0.0, (s2 - s1 * s1 / n) / (n - 1))
                out[j] = math.sqrt(var) * math.sqrt(mt.ANIO)
        return out

    def universo_mensual(self, n=N_MONEDAS, hist=HISTORIA_MIN, vol_min=VOL_MIN_USD):
        """{m: [bool por día]} y el primer día con universo. Se recalcula el primer día de cada mes con datos previos."""
        pert = {m: [False] * self.T for m in self.monedas}
        actual, mes_ant, primero = set(), None, None
        for j in range(self.T):
            f = fecha(self.d0 + j)
            if (f.year, f.month) != mes_ant:
                mes_ant = (f.year, f.month)
                cand = []
                for m in self.monedas:
                    if j - self.primero[m] < hist or j < 30:
                        continue
                    vols = self.usd[m][j - 30:j]
                    if median(vols) >= vol_min:
                        cand.append((sum(vols) / 30, m))
                actual = {m for _, m in sorted(cand, reverse=True)[:n]}
                if actual and primero is None:
                    primero = j
            for m in actual:
                pert[m][j] = True
        return pert, primero


def estados_ventana(mundo, m, n, elegible, vol):
    """Peso unitario por día (0 si fuera) de la porción (m, n): máquina de estados Donchian con stop en la mitad."""
    h, l, c = mundo.h[m], mundo.l[m], mundo.c[m]
    alto, bajo = dt.maximos_moviles(h, n), dt.minimos_moviles(l, n)
    wu, dentro, stop, w = [0.0] * mundo.T, False, 0.0, 0.0
    for j in range(mundo.T):
        if alto[j] is None or vol[j] is None or not elegible[j] or not mundo.valida[m][j]:
            dentro = False
            continue
        mid = (alto[j] + bajo[j]) / 2
        if dentro:
            stop = max(stop, mid)
            if c[j] < stop:
                dentro = False
        elif c[j] > alto[j]:
            dentro, stop = True, mid
            w = VOL_OBJETIVO / max(vol[j], VOL_MINIMA)
        if dentro:
            wu[j] = w
    return wu


def pesos(mundo, unidades, ventanas, n_monedas=N_MONEDAS):
    """{m: [peso por día]} de la cartera con ese subconjunto de ventanas, con el tope de exposición total."""
    W = {m: [0.0] * mundo.T for m in unidades}
    k = 1.0 / (n_monedas * len(ventanas))
    for m, por_n in unidades.items():
        for n in ventanas:
            wu = por_n[n]
            Wm = W[m]
            for j in range(mundo.T):
                if wu[j]:
                    Wm[j] += wu[j] * k
    for j in range(mundo.T):
        tot = sum(W[m][j] for m in W)
        if tot > TOPE_EXPOSICION:
            f = TOPE_EXPOSICION / tot
            for m in W:
                W[m][j] *= f
    return W


def rendimientos(mundo, W, desde, coste_lado=COSTE_LADO, con_funding=True):
    """Retornos diarios (bruto, neto de costes, neto de costes y funding) desde el día `desde`. El peso del día j-1 rinde el día j."""
    bruto, neto_c, neto = [], [], []
    for j in range(max(desde, 2), mundo.T):
        g = rot = fun = 0.0
        for m, Wm in W.items():
            w = Wm[j - 1]
            if w:
                g += w * mundo.ret[m][j]
                f = mundo.fund[m][j]
                fun += w * (FUNDING_DEFECTO_DIA if f is None else f)
            rot += abs(w - Wm[j - 2])
        c = rot * coste_lado
        bruto.append(g); neto_c.append(g - c); neto.append(g - c - (fun if con_funding else 0.0))
    return bruto, neto_c, neto


def ejecutar(panel, ventanas=VENTANAS):
    mundo = Mundo(panel)
    pert, primero = mundo.universo_mensual()
    if primero is None:
        raise RuntimeError("ninguna moneda cumple las condiciones de universo")
    vols = {m: mundo.vol_anual(m) for m in mundo.monedas}
    unidades = {m: {n: estados_ventana(mundo, m, n, pert[m], vols[m]) for n in ventanas} for m in mundo.monedas}
    return mundo, unidades, primero


def dividir(xs, fraccion=FRACCION_HOLDOUT):
    k = int(len(xs) * (1 - fraccion))
    return xs[:k], xs[k:]


def informe(panel, ventanas=VENTANAS):
    mundo, unidades, primero = ejecutar(panel, ventanas)
    desde = primero
    W = pesos(mundo, unidades, ventanas)
    bruto, neto_c, neto = rendimientos(mundo, W, desde)
    dias = [mundo.d0 + j for j in range(max(desde, 2), mundo.T)]
    # Referencias: BTC y BTC escalado a la volatilidad de la estrategia.
    btc = mundo.ret.get("BTC", [])[max(desde, 2):]
    res = {"estudio": "A_tendencia_lenta", "generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "periodo": {"desde": fecha(dias[0]).isoformat(), "hasta": fecha(dias[-1]).isoformat(), "dias": len(dias)},
           "monedas_en_cache": len(mundo.monedas), "ventanas": list(ventanas),
           "limitaciones": ["sesgo de supervivencia: solo monedas que siguen listadas hoy", "precios y funding de Binance",
                            "fracción de cada porción constante entre entrada y salida"]}
    ok, ho = dividir(neto)
    res["bruto"], res["neto_costes"], res["neto_costes_y_funding"] = (mt.resumen(bruto), mt.resumen(neto_c), mt.resumen(neto))
    res["neto_desarrollo"], res["neto_holdout"] = mt.resumen(ok), mt.resumen(ho)
    res["por_anio"] = mt.por_anio(dias, neto, lambda d: fecha(d).year)
    exposicion = [sum(W[m][j] for m in W) for j in range(max(desde, 2), mundo.T)]
    res["exposicion_media"] = round(sum(exposicion) / len(exposicion), 3)
    res["exposicion_maxima"] = round(max(exposicion), 3)
    res["dias_en_efectivo_pct"] = round(sum(1 for e in exposicion if e < 1e-9) / len(exposicion) * 100, 1)
    if btc:
        r_btc = mt.resumen(btc)
        vol_e = res["neto_costes_y_funding"]["volatilidad_anual_pct"]
        btc_e = mt.escalar_a_volatilidad(btc, vol_e, r_btc["volatilidad_anual_pct"])
        dif = [a - b for a, b in zip(neto, btc_e)]
        res["btc_mantener"] = r_btc
        res["btc_misma_volatilidad"] = mt.resumen(btc_e)
        res["estrategia_menos_btc_misma_vol"] = {"t_dias": round(mt.t_dias(dif), 2),
                                                 "media_diaria_pct": round(mt.media_desv(dif)[0] * 100, 4)}
    # Cada ventana sola (para PBO y para ver si alguna ayuda más que el conjunto).
    sueltas = {}
    for n in ventanas:
        Wn = pesos(mundo, unidades, (n,))
        sueltas[n] = rendimientos(mundo, Wn, desde)[2]
    res["ventanas_sueltas"] = {str(n): mt.resumen(v) for n, v in sueltas.items()}
    res["pbo_ventanas"] = mt.pbo_cscv({str(n): v for n, v in sueltas.items()})
    res["sharpe_deflactado_prob"] = round(mt.sharpe_deflactado(neto, n_pruebas=N_ESTUDIOS), 3)
    # Sin funding y con costes más altos (robustez).
    res["robustez"] = {"coste_x2": mt.resumen(rendimientos(mundo, W, desde, coste_lado=COSTE_LADO * 2)[2]),
                       "sin_funding": res["neto_costes"]}
    res["veredicto"] = veredicto(res)
    return res


def veredicto(res):
    anios = [a for a, r in res["por_anio"].items() if r["dias"] >= 180]
    neg = [a for a in anios if res["por_anio"][a]["cagr_pct"] < 0]
    pbo = (res.get("pbo_ventanas") or {}).get("pbo")
    btc = res.get("btc_misma_volatilidad") or {}
    crit = {
        "sharpe_neto_mayor_0_5": res["neto_costes_y_funding"]["sharpe"] > 0.5,
        "holdout_positivo": res["neto_holdout"]["sharpe"] > 0,
        f"t_dias_mayor_{T_MIN:.2f}": res["neto_costes_y_funding"]["t_dias"] >= T_MIN,
        "mejor_que_btc_misma_volatilidad": bool(btc) and res["neto_costes_y_funding"]["sharpe"] > btc["sharpe"]
        and res["estrategia_menos_btc_misma_vol"]["t_dias"] > 0,
        "pbo_menor_0_5": pbo is not None and pbo < 0.5,
        "anios_negativos_hasta_40pct": bool(anios) and len(neg) / len(anios) <= 0.4}
    return {"criterios": crit, "supera": all(crit.values()), "anios_negativos": neg,
            "lectura": ("Cumple todos los criterios fijados de antemano." if all(crit.values()) else
                        "No cumple: " + ", ".join(k for k, v in crit.items() if not v) + ".")}


def main():
    ap = argparse.ArgumentParser(description="Estudio A: tendencia lenta (solo investigación, sin red)")
    ap.add_argument("--salida", default=SALIDA)
    args = ap.parse_args()
    panel = dt.cargar_panel()
    res = informe(panel)
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("periodo", "neto_costes_y_funding", "neto_holdout", "btc_misma_volatilidad",
                                          "pbo_ventanas", "veredicto")}, ensure_ascii=False, indent=1))
    print("Guardado en", args.salida)


if __name__ == "__main__":
    main()
