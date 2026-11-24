"""ESTUDIO B — Factor de funding entre monedas (solo perpetuos). SOLO INVESTIGACIÓN. Reglas fijadas de antemano.

Pregunta única: ¿ganar dinero neto largo en el tercio de perpetuos con funding más BAJO y corto en el tercio con funding
más ALTO (señal: funding medio de Binance de los últimos 7 días), con rebalanceo semanal y neutral en dólares?

Reglas (no se ajusta ninguna):
  - Cada domingo al cierre (00:00 UTC del lunes) se ordenan las monedas del universo por funding medio de 7 días.
  - Universo: cada mes, las 30 monedas con más volumen medio de 30 días (≥ 2 M$/día), con ≥ 90 días de historia.
  - Largo en el tercio más bajo, corto en el más alto; pesos por volatilidad inversa de 30 días dentro de cada pata;
    cada pata suma 0,5 del capital (bruto total 1,0, neto 0). Se mantiene una semana.
  - Costes: 0,045 % taker + 0,02 % de deslizamiento por lado sobre lo operado. Funding de Binance: el largo paga la tasa,
    el corto la cobra.

Limitaciones: sesgo de supervivencia (monedas que siguen listadas); precios y funding de Binance, no de Hyperliquid; el
corto de Hyperliquid paga/cobra el funding de Hyperliquid, que difiere; las patas se mantienen a fracción constante.
"""

import argparse
import json
import os
import random
import time

from estudios_ext import datos as dt
from estudios_ext import metricas as mt
from estudios_ext import tendencia as td

N_UNIVERSO = 30
HISTORIA_MIN = 90
VENT_SENAL = 7
VENT_VOL = 30
PATA = 0.5
SALIDA = os.path.join(td.AQUI, "registro", "estudio_factor_funding.json")


def senal_funding(mundo, m, j, n=VENT_SENAL):
    """Funding medio diario de los n días hasta j (inclusive); None si faltan datos (menos de n-2 días)."""
    xs = [mundo.fund[m][k] for k in range(j - n + 1, j + 1) if k >= 0 and mundo.fund[m][k] is not None]
    return sum(xs) / len(xs) if len(xs) >= n - 2 else None


def construir_pesos(mundo, pert, vols, primero, modo="normal", semilla=1, retraso=0):
    """modo: «normal» (la regla), «invertida» (largo en funding alto: debe salir mal), «aleatoria» (señal al azar: debe
    salir ≈ 0 menos costes). `retraso`: días extra de antigüedad de la señal (debe cambiar poco si no hay mirada al futuro)."""
    W = {m: [0.0] * mundo.T for m in mundo.monedas}
    actual = {m: 0.0 for m in mundo.monedas}
    azar = random.Random(semilla)
    for j in range(mundo.T):
        if j >= primero and td.fecha(mundo.d0 + j).weekday() == 6:        # domingo: se decide al cierre
            cand = []
            for m in mundo.monedas:
                s = senal_funding(mundo, m, j - retraso) if pert[m][j] and mundo.valida[m][j] else None
                if s is not None and vols[m][j]:
                    cand.append((azar.random() if modo == "aleatoria" else (-s if modo == "invertida" else s), m))
            nuevos = {m: 0.0 for m in mundo.monedas}
            k = len(cand) // 3
            if k >= 1:
                cand.sort()
                for lado, grupo in ((1.0, cand[:k]), (-1.0, cand[-k:])):
                    inv = {m: 1.0 / max(vols[m][j], td.VOL_MINIMA) for _, m in grupo}
                    tot = sum(inv.values())
                    for m, v in inv.items():
                        nuevos[m] = lado * PATA * v / tot
            actual = nuevos
        for m in mundo.monedas:
            W[m][j] = actual[m]
    return W


def rendimientos(mundo, W, desde, coste_lado=td.COSTE_LADO):
    """Igual que el estudio A pero con largos Y cortos: el funding lo paga quien está largo y lo cobra quien está corto."""
    return td.rendimientos(mundo, W, desde, coste_lado, con_funding=True)


def contribuciones(mundo, W, desde):
    """Resultado total (suma de retornos diarios ponderados, sin costes) por moneda: quién aporta."""
    out = {}
    for m, Wm in W.items():
        out[m] = sum(Wm[j - 1] * mundo.ret[m][j] - Wm[j - 1] * (mundo.fund[m][j] or 0.0)
                     for j in range(max(desde, 2), mundo.T))
    return out


def informe(panel):
    mundo = td.Mundo(panel)
    pert, primero = mundo.universo_mensual(n=N_UNIVERSO, hist=HISTORIA_MIN)
    if primero is None:
        raise RuntimeError("ninguna moneda cumple las condiciones de universo")
    vols = {m: mundo.vol_anual(m, VENT_VOL) for m in mundo.monedas}
    W = construir_pesos(mundo, pert, vols, primero)
    bruto, neto_c, neto = rendimientos(mundo, W, primero)
    dias = [mundo.d0 + j for j in range(max(primero, 2), mundo.T)]
    res = {"estudio": "B_factor_funding", "generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "periodo": {"desde": td.fecha(dias[0]).isoformat(), "hasta": td.fecha(dias[-1]).isoformat(), "dias": len(dias)},
           "monedas_en_cache": len(mundo.monedas),
           "limitaciones": ["sesgo de supervivencia", "precios y funding de Binance", "patas a fracción constante"]}
    res["bruto_sin_costes_ni_funding"] = mt.resumen(bruto)
    desarrollo, holdout = td.dividir(neto)
    res["neto"], res["neto_desarrollo"], res["neto_holdout"] = mt.resumen(neto), mt.resumen(desarrollo), mt.resumen(holdout)
    res["por_anio"] = mt.por_anio(dias, neto, lambda d: td.fecha(d).year)
    exp = [sum(abs(W[m][j]) for m in W) for j in range(max(primero, 2), mundo.T)]
    res["bruto_medio"] = round(sum(exp) / len(exp), 3)
    res["sharpe_deflactado_prob"] = round(mt.sharpe_deflactado(neto, n_pruebas=td.N_ESTUDIOS), 3)
    # Robustez: sin las tres monedas que más aportan, y con costes dobles.
    contrib = contribuciones(mundo, W, primero)
    tres = [m for m, _ in sorted(contrib.items(), key=lambda x: -x[1])[:3]]
    res["tres_que_mas_aportan"] = tres
    panel_sin = {m: p for m, p in panel.items() if m not in tres}
    m2 = td.Mundo(panel_sin)
    p2, pr2 = m2.universo_mensual(n=N_UNIVERSO, hist=HISTORIA_MIN)
    v2 = {m: m2.vol_anual(m, VENT_VOL) for m in m2.monedas}
    W2 = construir_pesos(m2, p2, v2, pr2)
    neto2 = rendimientos(m2, W2, pr2)[2]
    res["sin_esas_tres"] = mt.resumen(neto2)
    res["coste_x2"] = mt.resumen(rendimientos(mundo, W, primero, td.COSTE_LADO * 2)[2])
    # Controles del método: la señal invertida debe salir mal, la aleatoria ≈ 0 y la retrasada parecida a la real.
    azar = [mt.sharpe(rendimientos(mundo, construir_pesos(mundo, pert, vols, primero, "aleatoria", s), primero)[2])
            for s in range(1, 21)]
    res["controles"] = {
        "senal_invertida": mt.resumen(rendimientos(mundo, construir_pesos(mundo, pert, vols, primero, "invertida"), primero)[2]),
        "senal_aleatoria_sharpe_medio_20": round(sum(azar) / len(azar), 3),
        "senal_aleatoria_sharpe_max_20": round(max(azar), 3),
        "senal_retrasada_7_dias": mt.resumen(rendimientos(mundo, construir_pesos(mundo, pert, vols, primero, retraso=7), primero)[2])}
    # Descomposición: de dónde sale el resultado (precio frente a funding).
    precio, fund = [], []
    for j in range(max(primero, 2), mundo.T):
        g = f = 0.0
        for m, Wm in W.items():
            w = Wm[j - 1]
            if w:
                g += w * mundo.ret[m][j]
                f -= w * (mundo.fund[m][j] if mundo.fund[m][j] is not None else td.FUNDING_DEFECTO_DIA)
        precio.append(g); fund.append(f)
    res["descomposicion"] = {"precio_sin_costes": mt.resumen(precio), "funding": mt.resumen(fund)}
    res["veredicto"] = veredicto(res)
    return res


def veredicto(res):
    crit = {"sharpe_neto_mayor_0_4": res["neto"]["sharpe"] > 0.4,
            "holdout_positivo": res["neto_holdout"]["sharpe"] > 0,
            "caida_max_menor_35pct": res["neto"]["caida_max_pct"] < 35,
            "sin_las_tres_mejores_sharpe_mayor_0": res["sin_esas_tres"]["sharpe"] > 0,
            # El método debe distinguir: con la señal invertida pierde y con una aleatoria no gana.
            "control_invertida_negativa": res["controles"]["senal_invertida"]["sharpe"] < 0,
            "control_aleatoria_por_debajo_de_la_real": res["controles"]["senal_aleatoria_sharpe_max_20"] < res["neto"]["sharpe"]}
    return {"criterios": crit, "supera": all(crit.values()),
            "lectura": ("Cumple todos los criterios fijados de antemano." if all(crit.values()) else
                        "No cumple: " + ", ".join(k for k, v in crit.items() if not v) + ".")}


def main():
    ap = argparse.ArgumentParser(description="Estudio B: factor de funding (solo investigación, sin red)")
    ap.add_argument("--salida", default=SALIDA)
    args = ap.parse_args()
    res = informe(dt.cargar_panel())
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("periodo", "neto", "neto_holdout", "sin_esas_tres", "tres_que_mas_aportan",
                                          "veredicto")}, ensure_ascii=False, indent=1))
    print("Guardado en", args.salida)


if __name__ == "__main__":
    main()
