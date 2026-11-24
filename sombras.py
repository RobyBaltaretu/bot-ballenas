"""
Sombras: lo que el bot dejó pasar.

Resume para el panel (vista «Sónar de sombras») las señales que el bot DESCARTÓ y siguió en papel
(aprendizaje.json, tipo "sombra"): cuánto habrían ganado o perdido, por qué se descartaron, qué estrategia las propuso y
cómo van las que siguen abiertas.

Solo describe: no decide nada ni está en el camino de las decisiones del bot (módulo «sin efecto» en promocion.py).
OJO: el resultado de una sombra es MODELADO (SimSalida con un precio por ciclo, muestreo puntual), no una ejecución.
"""

import math
import re

# Por qué se descartó (primer motivo). Orden = prioridad de coincidencia.
CATEGORIAS = (
    ("investigacion", "Idea en estudio", "Estrategias que solo registran: hipótesis sin validar que nunca operan.",
     r"solo investigaci"),
    ("apagada", "Estrategia apagada", "Las has apagado tú: se siguen en sombra para ver si merecen volver.",
     r"estrategia apagada"),
    ("cerebro", "El cerebro dijo no", "El modelo no la eligió, no tiene modelo o el resultado esperado era bajo.",
     r"cerebro|el modelo de|sin modelo"),
    ("regimen", "Contra la marea de BTC", "Iba en contra de la tendencia de BTC (filtro de régimen).",
     r"r[ée]gimen de btc"),
    ("riesgo", "Sin hueco o demasiado riesgo", "Límites de la cuenta: tamaño mínimo, riesgo abierto, máximo de "
     "posiciones, correlación o ya había una posición en esa moneda.",
     r"tama[ñn]o m[íi]nimo|riesgo abierto|m[áa]ximo de posiciones|correlada|ya hay una posici|cartera de funding"),
    ("mercado", "Mercado poco fiable", "Volatilidad extrema, horquilla ancha, funding en contra o un stop fuera de "
     "límites.", r"volatilidad|horquilla|funding .* en contra|stop .* fuera de l"),
    ("pausa", "Bot en pausa", "Entradas bloqueadas: racha de pérdidas o datos obsoletos.", r"entradas bloqueadas"),
)
OTRO = ("otro", "Otros motivos", "Motivos poco frecuentes.")
_RE = [(c, re.compile(p, re.I)) for c, _, _, p in CATEGORIAS]
MIN_CASOS = 30           # por debajo, nada es concluyente
T_CLARO = 2.0
MAX_PUNTOS = 1500
MAX_CURVA = 80


def categoria(motivo):
    m = motivo or ""
    for clave, rx in _RE:
        if rx.search(m):
            return clave
    return OTRO[0]


def estadisticas(rs):
    rs = [float(x) for x in rs if x is not None]
    n = len(rs)
    if not n:
        return {"n": 0, "r_medio": None, "ganan_pct": None, "suma": 0.0, "t": None}
    media = sum(rs) / n
    t = None
    if n > 1:
        var = sum((x - media) ** 2 for x in rs) / (n - 1)
        t = round(media / math.sqrt(var / n), 2) if var > 0 else None
    return {"n": n, "r_medio": round(media, 3), "ganan_pct": round(sum(1 for x in rs if x > 0) / n * 100, 1),
            "suma": round(sum(rs), 2), "t": t}


def lectura_filtro(st):
    """¿El motivo de descarte acertó? Las sombras perdedoras = descartes acertados."""
    if st["n"] < MIN_CASOS or st["t"] is None:
        return "pocos", "Aún pocos casos: no se puede saber."
    if st["t"] <= -T_CLARO:
        return "acierta", "Acierta: lo que descarta pierde."
    if st["t"] >= T_CLARO:
        return "falla", "Se equivoca: lo que descarta gana."
    return "neutro", "No se nota: lo descartado queda cerca de cero."


def aviso_estrategia(estado, st):
    if st["n"] >= 50 and st["t"] is not None and st["t"] >= T_CLARO and estado != "activa":
        return "En sombra gana con claridad: merece un estudio aparte (el laboratorio manda)."
    if st["n"] >= MIN_CASOS and st["t"] is not None and st["t"] <= -T_CLARO and estado == "activa":
        return "En sombra pierde con claridad."
    return None


def _curva(regs):
    regs = sorted(regs, key=lambda r: r["cierre_ts"])
    acum, puntos = 0.0, []
    for r in regs:
        acum += r["resultado_r"]
        puntos.append([round(r["cierre_ts"]), round(acum, 2)])
    if len(puntos) > MAX_CURVA:                       # se reduce sin perder el último punto
        paso = len(puntos) / MAX_CURVA
        puntos = [puntos[int(i * paso)] for i in range(MAX_CURVA - 1)] + [puntos[-1]]
    return puntos


def _r(sim, px):
    try:
        return sim["s"] * (float(px) - sim["entrada"]) / sim["r_dist"]
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def abierta(r, px=None, px_ts=None):
    """Sombra todavía abierta: niveles en R (stop actual, objetivos, mejor alcanzado) y R aproximada al último precio."""
    sim = r.get("sim") or {}
    motivo = (r.get("motivos_descarte") or [""])[0]
    rr = lambda p: (round(_r(sim, p), 2) if _r(sim, p) is not None else None)     # noqa: E731
    r_px = _r(sim, px) if px is not None else None
    r_ahora = None
    if r_px is not None:          # lo ya cobrado en el parcial + lo que queda, al último precio (sin comisiones)
        r_ahora = round(float(sim.get("realizado_r") or 0) + float(sim.get("restante", 1)) * r_px, 2)
    return {"id": r.get("id"), "e": r.get("modulo") or "?", "m": r.get("moneda"), "l": r.get("lado"), "ts": r.get("ts"),
            "limite_ts": sim.get("limite_ts"), "cat": categoria(motivo), "motivo": motivo[:160], "tid": r.get("trade_id"),
            "px": px, "px_ts": px_ts, "r_ahora": r_ahora, "r_mejor": rr(sim.get("mejor")), "r_stop": rr(sim.get("sl")),
            "r_tp1": rr(sim.get("tp1")), "r_tpf": rr(sim.get("tpf")), "tp1_hecho": bool(sim.get("tp1_hecho")),
            "en_breakeven": bool(sim.get("en_breakeven")), "realizado_r": sim.get("realizado_r")}


def resumen(registros, ahora, desde=0.0, origen="simulado", estado_estrategia=None, precios=None):
    """
    registros: los de aprendizaje.json. estado_estrategia(clave) -> "activa" | "apagada" | "investigacion".
    precios: {moneda: (precio, ts)} último precio conocido (para las abiertas). Solo lectura.
    """
    estado_estrategia = estado_estrategia or (lambda clave: "activa")
    precios = precios or {}
    propios = [r for r in registros if (r.get("origen") or origen) == origen and (r.get("ts") or 0) >= (desde or 0)]
    sombras = [r for r in propios if r.get("tipo") == "sombra"]
    cerradas = [r for r in sombras if r.get("resultado_r") is not None and r.get("cierre_ts")]
    abiertas = [r for r in sombras if r.get("resultado_r") is None]
    reales = [r["resultado_r"] for r in propios if r.get("tipo") == "real" and r.get("resultado_r") is not None]
    rs = [r["resultado_r"] for r in cerradas]

    puntos = sorted(({"id": r.get("id"), "e": r.get("modulo") or "?", "m": r.get("moneda"), "l": r.get("lado"),
                      "ts": round(r["ts"]), "fin": round(r["cierre_ts"]), "r": r["resultado_r"], "c": r.get("cierre"),
                      "cat": categoria((r.get("motivos_descarte") or [""])[0]),
                      "motivo": ((r.get("motivos_descarte") or [""])[0])[:160], "tid": r.get("trade_id")}
                     for r in cerradas), key=lambda p: p["ts"], reverse=True)[:MAX_PUNTOS]

    por_cat = {}
    for r in cerradas:
        por_cat.setdefault(categoria((r.get("motivos_descarte") or [""])[0]), []).append(r["resultado_r"])
    textos = {c: (e, x) for c, e, x, _ in CATEGORIAS}
    textos[OTRO[0]] = OTRO[1:]
    por_motivo = []
    for clave, lista in por_cat.items():
        st = estadisticas(lista)
        lect, texto = lectura_filtro(st)
        por_motivo.append(dict(st, clave=clave, etiqueta=textos[clave][0], explica=textos[clave][1], lectura=lect,
                               texto=texto))
    por_motivo.sort(key=lambda x: -x["n"])

    por_est = {}
    for r in sombras:
        por_est.setdefault(r.get("modulo") or "?", []).append(r)
    estrategias = []
    for clave, lista in por_est.items():
        cer = [r for r in lista if r.get("resultado_r") is not None and r.get("cierre_ts")]
        st = estadisticas([r["resultado_r"] for r in cer])
        est = estado_estrategia(clave)
        estrategias.append(dict(st, clave=clave, estado=est, abiertas=len(lista) - len(cer), curva=_curva(cer),
                                aviso=aviso_estrategia(est, st)))
    estrategias.sort(key=lambda x: (-x["n"], x["clave"]))

    neg = [x for x in rs if x < 0]
    pos = [x for x in rs if x > 0]
    return {
        "ahora": ahora, "desde": desde or None, "origen": origen,
        "total": estadisticas(rs), "operadas": estadisticas(reales),
        "balanza": {"ahorrado": round(-sum(neg), 2), "dejado": round(sum(pos), 2), "neto": round(sum(rs), 2),
                    "n_pierden": len(neg), "n_ganan": len(pos)},
        "puntos": puntos, "recortados": max(0, len(cerradas) - MAX_PUNTOS),
        "abiertas": sorted((abierta(r, *(precios.get(r.get("moneda")) or (None, None))) for r in abiertas),
                           key=lambda a: -(a["ts"] or 0)),
        "por_motivo": por_motivo,
        "estrategias": estrategias,
        "categorias": [{"clave": c, "etiqueta": e} for c, e, _, _ in CATEGORIAS] + [{"clave": OTRO[0], "etiqueta": OTRO[1]}],
        "nota": "Resultados MODELADOS en papel (precio real muestreado una vez por ciclo), no ejecuciones.",
    }
