"""Análisis forense INDEPENDIENTE del ledger (solo lectura). No importa nada del bot.

Uso: python3 forense_ledger.py <raiz_repo> <salida_json>
Reconstruye cada operación cerrada desde los eventos crudos (senal, decision, fill, cierre), calcula métricas con
intervalos de confianza por bootstrap y MAE/MFE con las velas de 1 h archivadas por el propio bot.
"""
import bisect
import json
import math
import os
import random
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timezone

RAIZ, SALIDA = sys.argv[1], sys.argv[2]
RESET = datetime(2026, 10, 28, 22, 44, 56, tzinfo=timezone.utc).timestamp()


def iso(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


eventos = [json.loads(l) for l in open(os.path.join(RAIZ, "registro", "ledger.jsonl"), encoding="utf-8")]
por_tid = defaultdict(list)
for e in eventos:
    if e.get("trade_id"):
        por_tid[e["trade_id"]].append(e)


def via(dec):
    p = (dec or {}).get("plan") or {}
    c = (dec or {}).get("cerebro") or {}
    if p.get("cartera_funding"):
        return "cartera_funding"
    if p.get("exploracion_amplia"):
        return "exploracion_amplia"
    if c.get("exploracion") and c.get("prediccion") is not None and (c.get("prediccion") or 0) > 0.05:
        return "cerebro_exploracion"
    if (dec or {}).get("aprendizaje", "").startswith("cerebro:") or (c.get("prediccion") or -9) > 0.05:
        return "cerebro"
    return "memoria"


ops = []
for tid, evs in por_tid.items():
    cierre = next((e for e in evs if e["tipo"] == "cierre"), None)
    if not cierre or cierre.get("sin_ejecucion"):
        continue
    sen = next((e for e in evs if e["tipo"] == "senal"), None)
    dec = next((e for e in evs if e["tipo"] == "decision" and e.get("aprobada")), None)
    fills = [e for e in evs if e["tipo"] == "fill"]
    ent = [f for f in fills if f.get("rol") in ("entrada", "ampliacion")]
    sal = [f for f in fills if f.get("rol") not in ("entrada", "ampliacion")]
    t_ent = min((f["ts_exchange"] / 1000 for f in ent if f.get("ts_exchange")), default=None)
    t_sal = iso(cierre["ts"])
    ops.append({
        "tid": tid, "moneda": cierre["moneda"], "lado": cierre["lado"], "estrategia": cierre.get("estrategia"),
        "causa": cierre.get("causa"), "pnl_neto": cierre.get("pnl_neto"), "pnl_bruto": cierre.get("pnl_bruto"),
        "r_neto": cierre.get("r_neto"), "r_bruto": cierre.get("r_bruto"), "comisiones": cierre.get("comisiones"),
        "funding": cierre.get("funding"), "riesgo": cierre.get("riesgo_inicial_usd"),
        "desl_ent_pct": cierre.get("deslizamiento_entrada_pct"), "px_ent": cierre.get("precio_medio_entrada"),
        "px_sal": cierre.get("precio_medio_salida"), "contabilidad": cierre.get("contabilidad"),
        "t_senal": iso(sen["ts"]) if sen else None, "px_senal": (sen or {}).get("precio"),
        "sl_pct": (sen or {}).get("sl_pct"), "t_ent": t_ent, "t_sal": t_sal,
        "via": via(dec), "factor": ((dec or {}).get("plan") or {}).get("factor"),
        "pred": ((dec or {}).get("cerebro") or {}).get("prediccion"),
        "btc_alcista": ((sen or {}).get("contexto") or {}).get("btc_alcista"),
        "maker_ent": [f.get("maker") for f in ent], "ampliacion": bool(cierre.get("ampliacion")),
        "n_fills": len(fills),
    })
ops.sort(key=lambda o: o["t_sal"])


def boot_ic(xs, reps=10000, nivel=0.95, semilla=7):
    if len(xs) < 3:
        return None
    rng = random.Random(semilla)
    medias = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    return [round(medias[int((1 - nivel) / 2 * reps)], 3), round(medias[int((1 + nivel) / 2 * reps) - 1], 3)]


def metr(grupo):
    rs = [o["r_neto"] for o in grupo if o["r_neto"] is not None]
    pnl = [o["pnl_neto"] for o in grupo if o["pnl_neto"] is not None]
    if not rs:
        return {"n": 0}
    g = [x for x in rs if x > 0]
    p = [x for x in rs if x <= 0]
    sd = st.stdev(rs) if len(rs) > 1 else 0
    eq, pico, dd = 0.0, 0.0, 0.0
    for x in pnl:
        eq += x
        pico = max(pico, eq)
        dd = max(dd, pico - eq)
    eqr, picor, ddr = 0.0, 0.0, 0.0
    for x in rs:
        eqr += x
        picor = max(picor, eqr)
        ddr = max(ddr, picor - eqr)
    orden = sorted(pnl, reverse=True)
    return {
        "n": len(rs), "r_medio": round(st.mean(rs), 3), "r_mediana": round(st.median(rs), 3),
        "t": round(st.mean(rs) / (sd / math.sqrt(len(rs))), 2) if sd else None, "ic95_r_medio_bootstrap": boot_ic(rs),
        "ganadoras_pct": round(len(g) / len(rs) * 100, 1), "ganancia_media_r": round(st.mean(g), 3) if g else None,
        "perdida_media_r": round(st.mean(p), 3) if p else None,
        "payoff": round(st.mean(g) / -st.mean(p), 2) if g and p and st.mean(p) < 0 else None,
        "profit_factor_r": round(sum(g) / -sum(p), 2) if p and sum(p) < 0 else None,
        "pnl_neto_usd": round(sum(pnl), 2), "caida_max_usd": round(dd, 2), "caida_max_r": round(ddr, 2),
        "top2_usd": round(sum(orden[:2]), 2), "pnl_sin_top2_usd": round(sum(orden[2:]), 2),
        "comisiones_usd": round(sum(o["comisiones"] or 0 for o in grupo), 2),
        "funding_usd": round(sum(o["funding"] or 0 for o in grupo), 2),
    }


def agrupar(lista, clave):
    g = defaultdict(list)
    for o in lista:
        g[clave(o)].append(o)
    return {k: metr(v) for k, v in sorted(g.items(), key=lambda kv: str(kv[0]))}


desde = [o for o in ops if o["t_sal"] >= RESET]
antes = [o for o in ops if o["t_sal"] < RESET]

# -------------------------------------------------------------- MAE / MFE con velas de 1 h archivadas por el bot
velas = {}


def cargar_velas(m):
    if m in velas:
        return velas[m]
    p = os.path.join(RAIZ, "datos_archivo", "velas", "1h", f"{m}.jsonl")
    vs = []
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            v = json.loads(l)
            vs.append((int(v["t"]) / 1000, float(v["h"]), float(v["l"]), float(v["c"]), float(v["o"])))
    vs.sort()
    velas[m] = vs
    return vs


for o in desde:
    vs = cargar_velas(o["moneda"])
    if not vs or not o["t_ent"] or not o["px_ent"] or not o["sl_pct"]:
        continue
    ts = [v[0] for v in vs]
    i0 = bisect.bisect_right(ts, o["t_ent"]) - 1
    i1 = bisect.bisect_right(ts, o["t_sal"])
    tramo = vs[max(0, i0):i1]
    if not tramo:
        continue
    s = 1 if o["lado"] == "L" else -1
    r_dist = o["px_ent"] * o["sl_pct"] / 100
    hi, lo = max(v[1] for v in tramo), min(v[2] for v in tramo)
    fav, adv = (hi, lo) if s == 1 else (lo, hi)
    o["mfe_r"] = round(s * (fav - o["px_ent"]) / r_dist, 2)
    o["mae_r"] = round(s * (adv - o["px_ent"]) / r_dist, 2)
    # Movimiento del activo de la señal a la entrada (coste de llegar tarde), en R
    if o["px_senal"]:
        o["persecucion_r"] = round(s * (o["px_ent"] - o["px_senal"]) / r_dist, 3)

# -------------------------------------------------------------- referencia de mercado: ¿cortos de todo ganaban igual?
def ret_moneda(m, t0, t1):
    vs = cargar_velas(m)
    if not vs:
        return None
    ts = [v[0] for v in vs]
    i0, i1 = bisect.bisect_right(ts, t0) - 1, bisect.bisect_right(ts, t1) - 1
    if i0 < 0 or i1 <= i0:
        return None
    return vs[i1][3] / vs[i0][3] - 1


monedas = sorted(f[:-6] for f in os.listdir(os.path.join(RAIZ, "datos_archivo", "velas", "1h")))
ref = []
for o in desde:
    if not o["t_ent"]:
        continue
    rets = [r for m in monedas if (r := ret_moneda(m, o["t_ent"], o["t_sal"])) is not None]
    btc = ret_moneda("BTC", o["t_ent"], o["t_sal"])
    propio = ret_moneda(o["moneda"], o["t_ent"], o["t_sal"])
    if rets and propio is not None:
        s = 1 if o["lado"] == "L" else -1
        ref.append({"tid": o["tid"], "moneda": o["moneda"], "lado": o["lado"], "estrategia": o["estrategia"],
                    "ret_lado_pct": round(s * propio * 100, 2), "ret_universo_mismo_lado_pct": round(s * st.mean(rets) * 100, 2),
                    "ret_btc_mismo_lado_pct": round(s * btc * 100, 2) if btc is not None else None,
                    "exceso_vs_universo_pct": round(s * (propio - st.mean(rets)) * 100, 2)})

# BTC en el periodo completo
btc_v = cargar_velas("BTC")
btc_periodo = None
if btc_v:
    ts = [v[0] for v in btc_v]
    i0 = bisect.bisect_right(ts, RESET) - 1
    btc_periodo = {"desde": btc_v[i0][3], "hasta": btc_v[-1][3], "cambio_pct": round((btc_v[-1][3] / btc_v[i0][3] - 1) * 100, 2),
                   "ultima_vela": datetime.fromtimestamp(btc_v[-1][0], timezone.utc).isoformat()}

res = {
    "n_operaciones_cerradas_con_fills": len(ops), "antes_reset": metr(antes), "desde_reset": metr(desde),
    "todas": metr(ops),
    "desde_reset_por_estrategia": agrupar(desde, lambda o: o["estrategia"]),
    "desde_reset_por_lado": agrupar(desde, lambda o: o["lado"]),
    "desde_reset_por_via": agrupar(desde, lambda o: o["via"]),
    "desde_reset_por_causa": agrupar(desde, lambda o: o["causa"]),
    "desde_reset_por_regimen_btc": agrupar(desde, lambda o: o["btc_alcista"]),
    "desde_reset_por_lado_y_estrategia": agrupar(desde, lambda o: f"{o['estrategia']}|{o['lado']}"),
    "deslizamiento_entrada_pct": {"media": round(st.mean([o["desl_ent_pct"] for o in desde if o["desl_ent_pct"] is not None]), 3),
                                  "mediana": round(st.median([o["desl_ent_pct"] for o in desde if o["desl_ent_pct"] is not None]), 3),
                                  "max": round(max(o["desl_ent_pct"] for o in desde if o["desl_ent_pct"] is not None), 3)},
    "persecucion_r": [o.get("persecucion_r") for o in desde if o.get("persecucion_r") is not None],
    "entradas_maker": sum(1 for o in desde for m in o["maker_ent"] if m), "entradas_taker": sum(1 for o in desde for m in o["maker_ent"] if m is False),
    "mae_mfe": [{k: o.get(k) for k in ("moneda", "lado", "estrategia", "causa", "r_neto", "mae_r", "mfe_r")} for o in desde],
    "referencia_mercado": ref,
    "btc_periodo": btc_periodo,
    "operaciones": desde,
}
json.dump(res, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: res[k] for k in ("n_operaciones_cerradas_con_fills", "antes_reset", "desde_reset", "todas")}, ensure_ascii=False, indent=1))
