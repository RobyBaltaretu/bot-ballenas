"""¿Cuánto se desvían las «sombras» (muestreo puntual cada ~15 s, entrada al mid, stop lleno a su precio exacto) de una
simulación OHLC conservadora con las velas de 1 h archivadas por el propio bot?

Uso (desde la COPIA del repositorio, para importar estrategia.py/senales.py sin tocar el original):
  python3 sesgo_sombras.py <raiz_copia> <salida_json>
Solo lectura de aprendizaje.json, config.json, estrategia_elegida.json y datos_archivo/velas/1h.
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
sys.path.insert(0, RAIZ)
from estrategia import SimSalida  # noqa: E402
from senales import MODULOS, barras_max  # noqa: E402

RESET = datetime(2026, 10, 28, 22, 44, 56, tzinfo=timezone.utc).timestamp()
cfg = json.load(open(os.path.join(RAIZ, "config.json"), encoding="utf-8"))
lab = json.load(open(os.path.join(RAIZ, "estrategia_elegida.json"), encoding="utf-8"))["resultados"]
SALIDA_BASE = {"parcial_activo": True, "tp1_r": 1.0, "parcial_pct": 50, "tp_final_r": 3.0, "trailing_r": 1.0,
               "breakeven_tras_r": 1.0, "mover_stop_min_r": 0.25}
SALIDA_BASE.update(cfg.get("salida", {}))
MIN = {"1h": 60, "4h": 240}
TAKER, MAKER = cfg["comisiones"]["taker_pct"] / 100, cfg["comisiones"]["maker_pct"] / 100
DESL = 0.0005   # 0,05 % en salidas a mercado (riesgo.deslizamiento_estimado_pct del bot)


def def_estrategia(clave):
    if clave == "ballenas_1h":
        return dict(SALIDA_BASE, **cfg["ballenas"]["salida"]), cfg["ballenas"]["barras_max"] * 60
    if clave == "liquidaciones_1h":
        lq = cfg["mercado"]["liquidaciones"]
        return dict(SALIDA_BASE, **lq["salida"]), lq["barras_max"] * 60
    if clave.startswith("cartera_funding"):
        return None
    mod, iv = clave.rsplit("_", 1)
    if mod not in MODULOS:
        return None
    r = lab.get(clave)
    params = dict(MODULOS[mod]["defecto"], **((r or {}).get("params") or {}))
    if r and str(r.get("version", "1")) == str(MODULOS[mod].get("version", "1")):
        salida = dict(SALIDA_BASE, **r["salida"])
        barras = r["barras_max"]
    else:
        salida = dict(SALIDA_BASE, **MODULOS[mod]["salida"])
        barras = barras_max(mod, params)
    return salida, min(barras * MIN[iv], 336 * 60)


velas = {}


def cargar(m):
    if m not in velas:
        p = os.path.join(RAIZ, "datos_archivo", "velas", "1h", f"{m}.jsonl")
        vs = []
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                v = json.loads(l)
                vs.append((int(v["t"]) / 1000, float(v["o"]), float(v["h"]), float(v["l"]), float(v["c"])))
        vs.sort()
        velas[m] = vs
    return velas[m]


regs = json.load(open(os.path.join(RAIZ, "aprendizaje.json"), encoding="utf-8"))["registros"]
sombras = [r for r in regs if r["tipo"] == "sombra" and r["resultado_r"] is not None and r["ts"] >= RESET]
filas = []
for r in sombras:
    d = def_estrategia(r.get("modulo") or "")
    vs = cargar(r["moneda"])
    if d is None or not vs:
        continue
    salida, dur_min = d
    ts = [v[0] for v in vs]
    i = bisect.bisect_right(ts, r["ts"])            # primera vela que EMPIEZA después de la señal
    fin = r["ts"] + dur_min * 60
    if i >= len(vs) or vs[-1][0] + 3600 < min(fin, r["cierre_ts"]):
        continue                                     # sin velas suficientes para cubrir la operación
    # Entrada: el mid de la sombra empeorado media horquilla típica (0,05 %) -> como una IOC
    s = 1 if r["lado"] == "L" else -1
    entrada = r["entrada"] * (1 + s * 0.0005)
    sim = SimSalida(r["lado"], entrada, r["sl_pct"], salida, fin, TAKER, TAKER, MAKER, desl_mercado=DESL)
    cerrada = False
    for v in vs[i:]:
        if sim.paso(v[2], v[3], v[4], v[0] + 3600, apertura=v[1]):
            cerrada = True
            break
    if not cerrada:
        continue
    filas.append({"moneda": r["moneda"], "lado": r["lado"], "estrategia": r["modulo"], "r_sombra": r["resultado_r"],
                  "r_ohlc": sim.resultado_r(), "motivo": (r.get("motivos_descarte") or ["?"])[0][:60],
                  "cierre_sombra": r["cierre"], "cierre_ohlc": sim.motivo})


def resumen(xs):
    if len(xs) < 2:
        return {"n": len(xs)}
    m, sd = st.mean(xs), st.stdev(xs)
    rng = random.Random(3)
    b = sorted(st.mean(rng.choice(xs) for _ in xs) for _ in range(4000))
    return {"n": len(xs), "media": round(m, 3), "t": round(m / (sd / math.sqrt(len(xs))), 2) if sd else None,
            "ic95": [round(b[100], 3), round(b[3899], 3)]}


dif = [f["r_sombra"] - f["r_ohlc"] for f in filas]
por = defaultdict(list)
for f in filas:
    por[f["estrategia"]].append(f)
out = {
    "sombras_cerradas_desde_reset": len(sombras), "resimuladas": len(filas),
    "r_sombra": resumen([f["r_sombra"] for f in filas]), "r_ohlc": resumen([f["r_ohlc"] for f in filas]),
    "diferencia_sombra_menos_ohlc": resumen(dif),
    "por_estrategia": {k: {"sombra": resumen([x["r_sombra"] for x in v]), "ohlc": resumen([x["r_ohlc"] for x in v])}
                       for k, v in sorted(por.items())},
    "cierres_distintos": sum(1 for f in filas if f["cierre_sombra"] != f["cierre_ohlc"]),
    "filas": filas,
}
json.dump(out, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "filas"}, ensure_ascii=False, indent=1))
