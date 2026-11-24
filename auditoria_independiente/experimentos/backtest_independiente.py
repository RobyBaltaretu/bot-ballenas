"""Backtest INDEPENDIENTE de las estrategias activas con historia pública de Binance (USDT-M, 4 h, 2021-01 a 2026-10).

No es el laboratorio del bot: otra fuente (Binance, no Hyperliquid), otro universo (20 monedas grandes que existen hoy:
sesgo de supervivencia A FAVOR de las estrategias), parámetros FIJOS (los que eligió el laboratorio del 22/11, sin
optimizar aquí). Usa las funciones de señal (senales.py) y de salida (estrategia.SimSalida) del propio bot, importadas
desde una COPIA del repositorio, para medir exactamente la lógica que se opera.

Uso: python3 -I backtest_independiente.py <raiz_copia> <carpeta_datos_binance> <salida_json>
"""
import bisect
import csv
import io
import json
import math
import os
import random
import statistics as st
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

RAIZ, DATOS, SALIDA = sys.argv[1:4]
sys.path.insert(0, RAIZ)
from estrategia import SimSalida  # noqa: E402
from senales import Contexto, m_momentum, m_ruptura, m_fuerza, rangos_fuerza  # noqa: E402

TAKER, MAKER = 0.00045, 0.00015
BASE = {"parcial_activo": True, "tp1_r": 1.0, "parcial_pct": 50, "tp_final_r": 3.0, "trailing_r": 1.0,
        "breakeven_tras_r": 1.0, "mover_stop_min_r": 0.25}
ESTRATEGIAS = {
    "momentum_4h": {"f": m_momentum, "p": {"lookback": 180, "rebalanceo": 42, "umbral_atr": 3.0, "eficiencia_min": 0.1,
                                          "sl_atr": 3.0},
                    "salida": dict(BASE, parcial_activo=False, tp1_r=98, tp_final_r=99, trailing_r=1.5,
                                   breakeven_tras_r=1.5, trailing_sin_parcial=True, sin_objetivo=True), "barras": 41},
    "ruptura_4h": {"f": m_ruptura, "p": {"n": 20, "ema": 100, "vol_min": 1.1, "sl_atr": 2.5},
                   "salida": dict(BASE, tp1_r=1.5, tp_final_r=4.0, trailing_r=1.5), "barras": 30},
    "fuerza_4h": {"f": m_fuerza, "p": {"lookback": 42, "rebalanceo": 84, "top": 2, "sl_atr": 2.5},
                  "salida": dict(BASE, parcial_activo=False, tp1_r=98, tp_final_r=99, trailing_r=99, breakeven_tras_r=99,
                                 sin_objetivo=True), "barras": 83},
}


def leer_zip(ruta):
    with zipfile.ZipFile(ruta) as z:
        texto = z.read(z.namelist()[0]).decode()
    filas = list(csv.reader(io.StringIO(texto)))
    return [f for f in filas if f and f[0].isdigit()]


def cargar(moneda):
    vel, fun = {}, []
    for n in sorted(os.listdir(os.path.join(DATOS, "k"))):
        if n.startswith(moneda + "USDT-4h-"):
            for f in leer_zip(os.path.join(DATOS, "k", n)):
                vel[int(f[0])] = {"t": int(f[0]), "o": f[1], "h": f[2], "l": f[3], "c": f[4], "v": f[5]}
    for n in sorted(os.listdir(os.path.join(DATOS, "f"))):
        if n.startswith(moneda + "USDT-fundingRate-"):
            for f in leer_zip(os.path.join(DATOS, "f", n)):
                try:
                    fun.append((int(f[0]) / 1000, float(f[2])))
                except (ValueError, IndexError):
                    pass
    fun.sort()
    return [vel[k] for k in sorted(vel)], fun


MONEDAS = sorted({n.split("USDT")[0] for n in os.listdir(os.path.join(DATOS, "k"))})
datos = {m: cargar(m) for m in MONEDAS}
ctxs = {m: Contexto(v) for m, (v, _) in datos.items() if len(v) > 400}
btc = ctxs["BTC"]
btc_e200 = btc.ema(200)


def regimen(t):
    j = bisect.bisect_right(btc.t, t) - 1
    return None if j < 200 else btc.c[j] > btc_e200[j]


def funding_r(moneda, t0, t1, lado, sl_pct):
    fun = datos[moneda][1]
    ts = [x[0] for x in fun]
    i, j = bisect.bisect_right(ts, t0), bisect.bisect_right(ts, t1)
    tot = sum(x[1] for x in fun[i:j])          # fracción del nocional (positivo = los largos pagan)
    s = 1 if lado == "L" else -1
    return -s * tot * 100 / sl_pct


def simular(nombre, moneda, ctx, extra_por_i=None):
    e = ESTRATEGIAS[nombre]
    ops, ocupado = [], -1
    for i in range(205, len(ctx) - 1):
        if i <= ocupado:
            continue
        extra = extra_por_i.get(i) if extra_por_i is not None else None
        if extra_por_i is not None and extra is None:
            continue
        s = e["f"](ctx, i, e["p"], extra)
        if not s or not 0.25 <= s["sl_pct"] <= 12:
            continue
        j = i + 1
        sg = 1 if s["lado"] == "L" else -1
        desl = 0.0002 + 0.05 * (ctx.atr[i] / ctx.c[i])          # igual que laboratorio.deslizamiento_vela
        entrada = ctx.o[j] * (1 + sg * desl)
        limite = ctx.t[j] + e["barras"] * 4 * 3600
        sim = SimSalida(s["lado"], entrada, s["sl_pct"], e["salida"], limite, TAKER, TAKER, MAKER, desl_mercado=desl)
        k = j
        while k < len(ctx) and not sim.paso(ctx.h[k], ctx.l[k], ctx.c[k], ctx.t[k] + 4 * 3600, apertura=ctx.o[k]):
            k += 1
        if not sim.cerrada:
            break
        fr = funding_r(moneda, ctx.t[j], sim.cierre_ts, s["lado"], s["sl_pct"])
        ops.append({"m": moneda, "t": ctx.t[j], "lado": s["lado"], "r": sim.resultado_r() + fr, "r_sin_funding": sim.resultado_r(),
                    "salida": sim.motivo, "regimen": regimen(ctx.t[i]), "anio": datetime.fromtimestamp(ctx.t[j], timezone.utc).year,
                    "cierre": sim.cierre_ts})
        ocupado = k
    return ops


resultados = {}
for nombre in ESTRATEGIAS:
    ops = []
    if nombre == "fuerza_4h":
        tabla = rangos_fuerza(list(ctxs.items()), ESTRATEGIAS[nombre]["p"]["lookback"])
        for m, ctx in ctxs.items():
            ops += simular(nombre, m, ctx, tabla.get(m, {}))
    else:
        for m, ctx in ctxs.items():
            ops += simular(nombre, m, ctx)
    resultados[nombre] = sorted(ops, key=lambda o: o["t"])


def est(rs):
    if len(rs) < 2:
        return {"n": len(rs)}
    m, sd = st.mean(rs), st.stdev(rs)
    rng = random.Random(11)
    b = sorted(st.mean(rng.choice(rs) for _ in rs) for _ in range(3000))
    return {"n": len(rs), "r_medio": round(m, 3), "t": round(m / (sd / math.sqrt(len(rs))), 2),
            "ic95": [round(b[75], 3), round(b[2924], 3)], "gan_pct": round(sum(1 for x in rs if x > 0) / len(rs) * 100, 1)}


def dias(ops):
    """t por DÍAS (las operaciones del mismo día están correlacionadas: se suman por día)."""
    d = defaultdict(float)
    for o in ops:
        d[int(o["t"] // 86400)] += o["r"]
    xs = list(d.values())
    return {"dias": len(xs), "t_dias": round(st.mean(xs) / (st.stdev(xs) / math.sqrt(len(xs))), 2) if len(xs) > 2 and st.stdev(xs) else None}


informe = {"monedas": MONEDAS, "periodo": [datetime.fromtimestamp(btc.t[0], timezone.utc).isoformat(),
                                          datetime.fromtimestamp(btc.t[-1], timezone.utc).isoformat()], "estrategias": {}}
for nombre, ops in resultados.items():
    rs = [o["r"] for o in ops]
    a_favor = [o for o in ops if o["regimen"] is not None and (o["lado"] == "L") == o["regimen"]]
    informe["estrategias"][nombre] = {
        "todas": dict(est(rs), **dias(ops)),
        "sin_funding": est([o["r_sin_funding"] for o in ops]),
        "por_anio": {a: est([o["r"] for o in ops if o["anio"] == a]) for a in sorted({o["anio"] for o in ops})},
        "por_lado": {l: est([o["r"] for o in ops if o["lado"] == l]) for l in ("L", "S")},
        "por_regimen_btc": {str(g): est([o["r"] for o in ops if o["regimen"] == g]) for g in (True, False)},
        "con_filtro_regimen_del_bot": dict(est([o["r"] for o in a_favor]), **dias(a_favor)),
        "contra_regimen": est([o["r"] for o in ops if o["regimen"] is not None and (o["lado"] == "L") != o["regimen"]]),
        "por_salida": {k: est([o["r"] for o in ops if o["salida"] == k]) for k in sorted({o["salida"] for o in ops})},
    }

# ------------------------------------------------------------------ benchmarks diarios con BTC (sin apalancamiento)
dia_c = {}
for t, c in zip(btc.t, btc.c):
    dia_c[int(t // 86400)] = c
dias_ord = sorted(dia_c)
ret_btc = [dia_c[b] / dia_c[a] - 1 for a, b in zip(dias_ord, dias_ord[1:])]
pos_tend = []
for a in dias_ord[:-1]:
    r = regimen(a * 86400 + 86399)
    pos_tend.append(1.0 if r else 0.0)
ret_tend = [p * r - (0.0009 if k and pos_tend[k] != pos_tend[k - 1] else 0.0) for k, (p, r) in enumerate(zip(pos_tend, ret_btc))]
ret_tend_ls = [(1.0 if p else -1.0) * r - (0.0018 if k and pos_tend[k] != pos_tend[k - 1] else 0.0)
               for k, (p, r) in enumerate(zip(pos_tend, ret_btc))]


def curva(rets):
    eq, pico, dd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= 1 + r
        pico = max(pico, eq)
        dd = max(dd, 1 - eq / pico)
    anios = len(rets) / 365
    sharpe = st.mean(rets) / st.stdev(rets) * math.sqrt(365) if st.stdev(rets) else None
    return {"multiplo": round(eq, 2), "cagr_pct": round((eq ** (1 / anios) - 1) * 100, 1), "caida_max_pct": round(dd * 100, 1),
            "sharpe": round(sharpe, 2) if sharpe else None}


informe["benchmarks"] = {"btc_comprar_y_mantener": curva(ret_btc), "btc_tendencia_ema200_4h_largo_o_fuera": curva(ret_tend),
                         "btc_tendencia_largo_corto": curva(ret_tend_ls)}


# Cartera aproximada de las estrategias: 1 % de riesgo por operación, sin límite de posiciones (aproximación R -> %)
def cartera_r(ops, riesgo=0.01):
    d = defaultdict(float)
    for o in ops:
        d[int(o["cierre"] // 86400)] += o["r"] * riesgo
    rets = [d.get(k, 0.0) for k in dias_ord[1:]]
    return curva(rets)


informe["carteras_1pct_riesgo"] = {n: cartera_r(o) for n, o in resultados.items()}
informe["carteras_1pct_riesgo"]["tres_juntas"] = cartera_r([o for v in resultados.values() for o in v])
informe["carteras_1pct_riesgo"]["tres_juntas_con_filtro_regimen"] = cartera_r(
    [o for v in resultados.values() for o in v if o["regimen"] is not None and (o["lado"] == "L") == o["regimen"]])
json.dump(informe, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(informe, ensure_ascii=False, indent=1)[:9000])
