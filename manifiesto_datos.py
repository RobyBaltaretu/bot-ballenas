"""Manifiesto de los datos con que trabajó el laboratorio: cobertura, huecos e historia que cambia.

Idea tomada del «research dataset manifest» de HyperGrok. El laboratorio ya guardaba un hash ligero de los datos
(validacion.hash_datos: primera/última vela y último cierre). Aquí, por cada moneda e intervalo:

  - velas, primera y última, y HUECOS (velas que faltan entre la primera y la última) con el mayor en horas;
  - cobertura del funding (horas con dato / horas esperadas);
  - un hash por mes del contenido de las velas. Comparado con el manifiesto anterior, un mes ya cerrado cuyo hash
    cambia significa que la historia se ha reescrito (otra fuente, una corrección del exchange, una caché rota):
    resultados de semanas distintas dejarían de ser comparables sin saberlo.

Solo describe e informa: no filtra ni cambia datos ni decide nada (archivo «sin efecto» en promocion.py).
"""
import hashlib
import json
import os
from datetime import datetime, timezone

VERSION = 1
MINUTOS = {"1h": 60, "4h": 240}
HUECO_AVISO = 0.01          # más de un 1 % de velas que faltan en una serie: se señala


def _mes(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m")


def serie(m):
    """Manifiesto de un mercado del laboratorio (laboratorio.Mercado)."""
    ctx, paso = m.ctx, MINUTOS[m.intervalo] * 60
    t = list(ctx.t)
    if not t:
        return {"velas": 0}
    faltan, mayor = 0, 0.0
    for a, b in zip(t, t[1:]):
        hueco = round((b - a) / paso) - 1
        if hueco > 0:
            faltan += hueco
            mayor = max(mayor, (b - a - paso) / 3600)
    meses = {}
    for i, ti in enumerate(t):
        meses.setdefault(_mes(ti), hashlib.sha256()).update(
            json.dumps([ti, ctx.o[i], ctx.h[i], ctx.l[i], ctx.c[i]]).encode())
    esperadas = round((t[-1] - t[0]) / paso) + 1
    out = {"velas": len(t), "inicio": t[0], "fin": t[-1], "faltan": faltan,
           "faltan_pct": round(100 * faltan / esperadas, 3) if esperadas else 0.0, "mayor_hueco_h": round(mayor, 1),
           "meses": {k: h.hexdigest()[:10] for k, h in meses.items()}}
    f = getattr(m, "funding", None)
    ft = [x for x in (getattr(f, "t", None) or []) if t[0] <= x <= t[-1]]
    if ft:
        horas = (min(t[-1], ft[-1]) - max(t[0], ft[0])) / 3600 + 1
        out["funding_cobertura_pct"] = round(100 * min(1.0, len(set(int(x // 3600) for x in ft)) / horas), 1) if horas > 0 else None
    else:
        out["funding_cobertura_pct"] = 0.0
    return out


def construir(mercados, anterior=None):
    """mercados: {"1h": [Mercado], "4h": [...]}. anterior: manifiesto previo (o None). Devuelve el manifiesto."""
    series = {}
    for iv, lista in mercados.items():
        for m in lista:
            series[f"{m.moneda}|{iv}"] = serie(m)
    cambiadas = []
    previas = (anterior or {}).get("series") or {}
    for clave, s in series.items():
        p = previas.get(clave)
        if not p or not s.get("meses"):
            continue
        ultimo = max(s["meses"])                      # el mes en curso puede crecer: no cuenta
        distintos = [mes for mes, h in (p.get("meses") or {}).items()
                     if mes < ultimo and mes in s["meses"] and s["meses"][mes] != h]
        if distintos:
            cambiadas.append({"serie": clave, "meses": sorted(distintos)})
    huecos = sorted(({"serie": k, "faltan": s["faltan"], "faltan_pct": s["faltan_pct"], "mayor_hueco_h": s["mayor_hueco_h"]}
                     for k, s in series.items() if s.get("faltan_pct", 0) > HUECO_AVISO * 100), key=lambda x: -x["faltan_pct"])
    sin_funding = sorted(k for k, s in series.items() if (s.get("funding_cobertura_pct") or 0) < 90)
    h = hashlib.sha256(json.dumps({k: s.get("meses") for k, s in sorted(series.items())}, sort_keys=True).encode())
    return {"version": VERSION, "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "hash": h.hexdigest()[:16], "series": series,
            "resumen": {"series": len(series), "con_huecos": huecos, "funding_incompleto": sin_funding,
                        "historia_cambiada": cambiadas, "comparado_con": (anterior or {}).get("hash")}}


def leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def guardar(ruta, manifiesto):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(manifiesto, fh, ensure_ascii=False)
    os.replace(ruta + ".tmp", ruta)


def texto(resumen):
    """Líneas para el registro del laboratorio."""
    r = resumen or {}
    lineas = [f"Datos: {r.get('series', 0)} series · {len(r.get('con_huecos') or [])} con huecos > {HUECO_AVISO * 100:.0f} % · "
              f"{len(r.get('funding_incompleto') or [])} con funding < 90 % · {len(r.get('historia_cambiada') or [])} con historia cambiada"]
    for x in (r.get("con_huecos") or [])[:5]:
        lineas.append(f"  hueco {x['serie']}: faltan {x['faltan']} velas ({x['faltan_pct']} %), el mayor de {x['mayor_hueco_h']} h")
    for x in (r.get("historia_cambiada") or [])[:5]:
        lineas.append(f"  HISTORIA CAMBIADA {x['serie']}: {', '.join(x['meses'][:6])}")
    return lineas
