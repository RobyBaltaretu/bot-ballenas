"""
Veredicto de la prueba de dos semanas (04/11/2026 a 18/11/2026): ¿el bot va adelante o no vale?

Los criterios se fijaron ANTES de ver los resultados y no los decide ninguna IA: es este código y nada más. Solo lee y
calcula: no cambia ningún límite, no toca el modo y no acerca nada a dinero real (eso sigue exigiendo promocion.py y la
aprobación expresa de Roberto).

  adelante           alguna estrategia supera el laboratorio (holdout incluido) y en vivo no va claramente peor
  cambiar_de_rumbo   ninguna estrategia de dirección lo supera, pero el carry de funding aguanta con costes
  no_vale            nada de lo anterior: no se pone dinero real

El objetivo de 20-50 € por semana se informa aparte: en dos semanas el saldo depende sobre todo de la suerte y de
estrategias que se operan para aprender, así que no decide el veredicto.
"""

from datetime import datetime, timezone
from math import sqrt

INICIO_TS = datetime(2026, 11, 4, tzinfo=timezone.utc).timestamp()
FIN_TS = datetime(2026, 11, 19, tzinfo=timezone.utc).timestamp()      # incluye todo el día 18
SEMANA = 7 * 86400
EUR_USD = 1.16                  # referencia del proyecto: 232 USD ≈ 200 €
OBJETIVO_EUR_SEMANA = (20, 50)
OBJETIVO_EUR_MES = (300, 400)
MIN_OPS_CONTRASTE = 10          # con menos operaciones en vivo no se puede contradecir al laboratorio
SIGMAS_PEOR = 2.0               # «claramente peor»: 2 desviaciones por debajo de lo previsto (1 R por operación)
CARRY_T_MIN = 3.0
CARRY_N_MIN = 30


def _ts(texto):
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _resumen_r(filas):
    rs = [f["r_neto"] for f in filas if f.get("r_neto") is not None]
    return {"n": len(rs), "r_medio": round(sum(rs) / len(rs), 3) if rs else None,
            "pnl_usd": round(sum(f.get("pnl_neto") or 0 for f in filas), 2)}


def en_vivo(cerradas):
    """Resultado en vivo por estrategia desde el inicio de la prueba."""
    claves = sorted({f.get("estrategia") or "?" for f in cerradas})
    return {k: _resumen_r([f for f in cerradas if (f.get("estrategia") or "?") == k]) for k in claves}


def _contraste(previsto, vivo):
    """¿Lo visto en vivo contradice al laboratorio? Devuelve True, False o None si aún no hay datos para decirlo."""
    if not vivo or vivo["n"] < MIN_OPS_CONTRASTE or previsto is None:
        return None
    return vivo["r_medio"] < previsto - SIGMAS_PEOR / sqrt(vivo["n"])


def _laboratorio(lab, vivo):
    """Estrategias que superan un laboratorio ejecutado durante la prueba (los anteriores no cuentan)."""
    generado = _ts(lab.get("generado"))
    vigente = generado is not None and generado >= INICIO_TS
    pasan = []
    for clave, r in (lab.get("resultados") or {}).items() if vigente else ():
        holdout = (r.get("holdout") or {}).get("r_medio")
        if r.get("estado_evaluacion") == "supera" and holdout is not None and holdout > 0:
            previsto = (r.get("fuera_de_muestra") or r.get("validacion") or {}).get("r_medio")
            pasan.append({"clave": clave, "r_previsto": previsto, "vivo": vivo.get(clave),
                          "contradice": _contraste(previsto, vivo.get(clave))})
    return vigente, pasan


def _carry(lab, vigente):
    r = ((lab.get("investigacion") or {}).get("carry_realista") or {}) if vigente else {}
    h = r.get("holdout") or {}
    rentab, t, n = h.get("rentab_anual_capital_pct"), h.get("t"), h.get("n")
    aguanta = rentab is not None and rentab > 0 and (t or 0) >= CARRY_T_MIN and (n or 0) >= CARRY_N_MIN
    return {"medido": bool(h), "aguanta": aguanta, "rentab_anual_pct": rentab, "t": t, "n": n,
            "n_contado_hyperliquid": (r.get("solo_monedas_con_contado_en_hyperliquid") or {}).get("n"),
            "aviso": "Modelado con el contado de Binance. Faltan costes y riesgos sin medir (préstamo, margen del corto, "
                     "desajuste entre patas), así que aun aguantando es provisional."}


def _semanas(cerradas, latente, ahora):
    out = []
    for i in range(2):
        desde = INICIO_TS + i * SEMANA
        hasta = desde + SEMANA if i == 0 else FIN_TS
        filas = [f for f in cerradas if desde <= f["cerrada_ts"] < hasta]
        conocidas = [f["pnl_neto"] for f in filas if f.get("pnl_neto") is not None]
        en_curso = desde <= ahora < hasta
        pnl = sum(conocidas)
        total = pnl + (latente or 0) if en_curso else pnl
        out.append({"semana": i + 1, "desde": desde, "hasta": hasta, "empezada": ahora >= desde, "en_curso": en_curso,
                    "n": len(filas), "desconocidas": len(filas) - len(conocidas), "cerradas_usd": round(pnl, 2),
                    "latente_usd": round(latente, 2) if en_curso and latente is not None else None,
                    "total_usd": round(total, 2), "total_eur": round(total / EUR_USD, 2),
                    "en_positivo": total > 0, "llega_al_objetivo": total / EUR_USD >= OBJETIVO_EUR_SEMANA[0]})
    return out


def contra_mercado(cerradas):
    """¿El resultado es del bot o del mercado? Compara con las MISMAS operaciones (mismas monedas, entradas y salidas)
    hechas todas cortas o todas largas, con las mismas comisiones. Si todo corto habría ganado igual o más, lo ganado se
    explica por la caída del mercado y no por elegir bien. Solo informa: no entra en los criterios de la prueba."""
    filas = [f for f in cerradas if f.get("pnl_bruto") is not None and f.get("lado") in ("L", "S")]
    if not filas:
        return {"n": 0, "lectura": "Aún no hay operaciones cerradas con resultado conocido para comparar."}
    movimiento = sum((1 if f["lado"] == "L" else -1) * f["pnl_bruto"] for f in filas)     # lo que ganaría un largo en todas
    comisiones = sum(f.get("comisiones") or 0 for f in filas)
    bruto = sum(f["pnl_bruto"] for f in filas)
    bot, corto, largo = bruto - comisiones, -movimiento - comisiones, movimiento - comisiones
    cortos = sum(f["lado"] == "S" for f in filas)
    if bot <= corto:
        lectura = (f"Las mismas {len(filas)} operaciones, todas cortas, habrían dado {corto:+.2f} $ frente a {bot:+.2f} $ del bot: "
                   "el resultado se explica por la caída del mercado, no por elegir bien la dirección.")
    else:
        lectura = (f"Las mismas {len(filas)} operaciones, todas cortas, habrían dado {corto:+.2f} $ frente a {bot:+.2f} $ del bot: "
                   f"elegir la dirección sumó {bot - corto:+.2f} $ (con tan pocas operaciones aún puede ser azar).")
    return {"n": len(filas), "bot_usd": round(bot, 2), "todo_corto_usd": round(corto, 2), "todo_largo_usd": round(largo, 2),
            "cortos": cortos, "largos": len(filas) - cortos, "mejor_que_todo_corto": bot > corto,
            "nota": "Sin funding en ninguna de las tres cifras (comisiones iguales).", "lectura": lectura}


def _capital_necesario(rentab_anual_pct):
    """Capital que haría falta para 300-400 €/mes con esa rentabilidad anual: lo que hay que tener para ese objetivo."""
    if not rentab_anual_pct or rentab_anual_pct <= 0:
        return None
    return [round(m * 12 / (rentab_anual_pct / 100)) for m in OBJETIVO_EUR_MES]


def evaluar(lab, cerradas, latente=None, saldo=None, ahora=None):
    """lab: estrategia_elegida.json. cerradas: [{estrategia, cerrada_ts, pnl_neto, r_neto}] de la cuenta simulada."""
    ahora = ahora if ahora is not None else datetime.now(timezone.utc).timestamp()
    cerradas = [f for f in cerradas if f.get("cerrada_ts") and INICIO_TS <= f["cerrada_ts"] < FIN_TS]
    vivo = en_vivo(cerradas)
    vigente, pasan = _laboratorio(lab, vivo)
    carry = _carry(lab, vigente)
    confirmadas = [p for p in pasan if p["contradice"] is not True]
    if confirmadas:
        resultado = "adelante"
    elif carry["aguanta"]:
        resultado = "cambiar_de_rumbo"
    else:
        resultado = "no_vale"
    terminada = ahora >= FIN_TS
    if not vigente and not terminada:
        resultado = "pendiente"          # sin ningún laboratorio de la prueba, aún no se puede decir nada
    criterios = [
        {"clave": "laboratorio", "texto": "Alguna estrategia supera un laboratorio de estas dos semanas, holdout incluido",
         "estado": "cumple" if pasan else ("no_cumple" if vigente else "pendiente"),
         "detalle": ", ".join(p["clave"] for p in pasan) if pasan else
                    ("Ninguna en el último laboratorio." if vigente else "Aún no hay laboratorio de estas semanas.")},
        {"clave": "vivo", "texto": "En vivo no va claramente peor de lo que predice el laboratorio",
         "estado": "pendiente" if not pasan or all(p["contradice"] is None for p in pasan) else
                   ("cumple" if confirmadas else "no_cumple"),
         "detalle": f"Se contrasta a partir de {MIN_OPS_CONTRASTE} operaciones de la estrategia que supere el laboratorio."},
        {"clave": "carry", "texto": "El carry de funding aguanta con costes (alternativa si no hay estrategia)",
         "estado": "cumple" if carry["aguanta"] else ("no_cumple" if vigente else "pendiente"),
         "detalle": carry["aviso"] if carry["medido"] else "Aún no hay laboratorio de estas semanas."},
    ]
    return {"inicio": INICIO_TS, "fin": FIN_TS, "terminada": terminada, "resultado": resultado,
            "provisional": not terminada, "dias_restantes": max(0, round((FIN_TS - ahora) / 86400, 1)),
            "lab_generado": lab.get("generado"), "lab_vigente": vigente, "criterios": criterios, "estrategias_superan": pasan,
            "carry": carry, "en_vivo": vivo, "contra_mercado": contra_mercado(cerradas),
            "semanas": _semanas(cerradas, latente, ahora),
            "objetivo": {"eur_semana": OBJETIVO_EUR_SEMANA, "eur_mes": OBJETIVO_EUR_MES,
                         "pct_semana_sobre_saldo": [round(e * EUR_USD / saldo * 100, 1) for e in OBJETIVO_EUR_SEMANA] if saldo else None,
                         "capital_eur_con_carry": _capital_necesario(carry["rentab_anual_pct"])}}
