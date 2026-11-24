"""RASGOS DEL CEREBRO: ¿lo que ve el cerebro en vivo se parece a lo que vio al entrenar? SOLO LECTURA.

Compara, por intervalo, los 8 rasgos que el cerebro calculó en cada decisión del ledger con la media y la desviación
con las que se estandarizó el modelo (`cerebro_modelo.json`). Un desplazamiento grande de la media (en desviaciones de
entrenamiento), una dispersión muy distinta o muchos valores fuera de ±3 desviaciones indican que el modelo recibe
entradas que no entrenó, y su predicción en vivo no es comparable con la del laboratorio.

Criterio fijado de antemano: una desviación se marca como «desplazada» si |media viva − media de entrenamiento| > 0,5
desviaciones de entrenamiento, o si la dispersión viva es < 0,5× o > 2× la de entrenamiento. Con menos de 30 decisiones
por intervalo el informe lo dice y no concluye."""

import argparse
import json
import math
import os

from estudios_ext.paridad import leer_ledger

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(AQUI, "registro", "estudio_rasgos_cerebro.json")
MIN_DECISIONES = 30
DESPLAZAMIENTO_MAX = 0.5


def _cuantil(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def informe(ledger, modelo):
    por_iv = {"1h": [], "4h": []}
    for e in leer_ledger(ledger):
        c = e.get("cerebro") if e.get("tipo") == "decision" else None
        if c and c.get("rasgos") and str(e.get("estrategia", "")).endswith(("_1h", "_4h")):
            por_iv[e["estrategia"][-2:]].append((e, c))
    res = {"estudio": "rasgos_cerebro_vivo_vs_entrenamiento", "criterio": f"|Δmedia| > {DESPLAZAMIENTO_MAX} desv. o dispersión fuera de 0,5×–2×",
           "intervalos": {}}
    for iv, filas in por_iv.items():
        m = ((modelo or {}).get("modelos") or {}).get(iv)
        if not m:
            res["intervalos"][iv] = {"motivo": "sin modelo"}
            continue
        out = {"decisiones": len(filas), "entrenamiento_n": m.get("n"), "estado_modelo": m.get("estado_laboratorio"),
               "rasgos": {}, "desplazados": []}
        for r in m["rasgos"]:
            xs = [float(c["rasgos"][r]) for _, c in filas if c["rasgos"].get(r) is not None]
            mu_t, sd_t = m["media"][r], m["desv"][r]
            if len(xs) < 2 or not sd_t:
                out["rasgos"][r] = {"n": len(xs)}
                continue
            mu_v = sum(xs) / len(xs)
            sd_v = math.sqrt(sum((x - mu_v) ** 2 for x in xs) / (len(xs) - 1))
            z = (mu_v - mu_t) / sd_t
            fuera = sum(1 for x in xs if abs((x - mu_t) / sd_t) > 3) / len(xs) * 100
            ratio = sd_v / sd_t
            out["rasgos"][r] = {"n": len(xs), "media_viva": round(mu_v, 5), "media_entrenamiento": round(mu_t, 5),
                                "desplazamiento_en_desv": round(z, 2), "dispersion_viva_sobre_entrenamiento": round(ratio, 2),
                                "fuera_de_3_desv_pct": round(fuera, 1)}
            if abs(z) > DESPLAZAMIENTO_MAX or ratio < 0.5 or ratio > 2:
                out["desplazados"].append(r)
        preds = [float(c["prediccion"]) for _, c in filas if c.get("prediccion") is not None]
        if preds:
            out["prediccion"] = {"media": round(sum(preds) / len(preds), 4), "p10": round(_cuantil(preds, 0.1), 4),
                                 "p50": round(_cuantil(preds, 0.5), 4), "p90": round(_cuantil(preds, 0.9), 4),
                                 "pct_sobre_umbral": round(100 * sum(1 for p in preds if p > m.get("umbral_r", 0.05)) / len(preds), 1)}
        out["con_datos_externos_ausentes"] = sum(1 for _, c in filas if c.get("faltan"))
        out["aprobadas_pct"] = round(100 * sum(1 for e, _ in filas if e.get("aprobada")) / len(filas), 1) if filas else None
        out["veredicto"] = ("sin muestra suficiente para concluir" if len(filas) < MIN_DECISIONES else
                            ("rasgos desplazados: " + ", ".join(out["desplazados"]) if out["desplazados"] else "sin desplazamientos relevantes"))
        res["intervalos"][iv] = out
    return res


def main():
    ap = argparse.ArgumentParser(description="Rasgos del cerebro en vivo frente al entrenamiento (solo lectura)")
    ap.add_argument("--salida", default=SALIDA)
    args = ap.parse_args()
    with open(os.path.join(AQUI, "cerebro_modelo.json"), encoding="utf-8") as fh:
        modelo = json.load(fh)
    res = informe(os.path.join(AQUI, "registro", "ledger.jsonl"), modelo)
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print("Guardado en", args.salida)


if __name__ == "__main__":
    main()
