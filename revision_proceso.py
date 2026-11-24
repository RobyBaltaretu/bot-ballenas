"""Nota de PROCESO de cada operación, separada de su resultado.

Idea tomada del «Trade Reviewer» de HyperGrok: una operación puede ganar con mal proceso (suerte) o perder con buen
proceso (el mercado, o una estrategia sin ventaja). Mezclar las dos cosas esconde los fallos de ejecución detrás de los
resultados. Aquí solo se mira CÓMO se hizo, con lo que el registro (ledger) ya guarda:

  - cuánto tardó en quedar puesto el stop tras la entrada y si se verificó en el exchange;
  - el deslizamiento de la entrada (frente al precio de la señal) y el del stop (frente a su precio de activación);
  - el riesgo real tras el fill frente al planificado, y la pérdida frente al riesgo;
  - el peso de comisiones y funding en R;
  - que los pasos fueron en orden (decisión aprobada antes del primer fill) e incidencias (errores, órdenes sin
    confirmar, contabilidad incompleta, precios estimados con el bot parado).

Lo calcula código, no una IA. Solo describe: NO decide nada ni lo lee ninguna ruta de decisión (archivo «sin efecto»
en promocion.py, no cambia la huella). Sirve además para calibrar la simulación de ejecución (pendiente 5).
"""
from datetime import datetime

VERSION = 1
# Penalización por comprobación (sobre 100). Un «fallo» es algo que no debería pasar; un «aviso», algo a vigilar.
PENALIZACION = {"fallo": 25, "aviso": 10, "info": 0}
NOTAS = ((90, "A"), (75, "B"), (50, "C"), (0, "D"))
# Umbrales (pb = puntos básicos, 1 pb = 0,01 %). Elegidos a priori, no ajustados a los resultados.
STOP_AVISO_S, STOP_FALLO_S = 60, 300
ENTRADA_AVISO_PB, ENTRADA_FALLO_PB = 25, 75
STOP_DESL_AVISO_PB, STOP_DESL_FALLO_PB = 20, 50
RIESGO_AVISO, RIESGO_FALLO = 1.10, 1.25
PERDIDA_AVISO_R, PERDIDA_FALLO_R = -1.15, -1.5
COSTES_AVISO_R = 0.15
CUADRANTES = {
    (True, True): "buen proceso y buen resultado",
    (True, False): "buen proceso, mal resultado (mercado o estrategia sin ventaja: no es un error de ejecución)",
    (False, True): "mal proceso, buen resultado (suerte: el fallo sigue ahí)",
    (False, False): "mal proceso y mal resultado",
}


def _ts(v):
    if v is None or isinstance(v, (int, float)):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _num(v):
    try:
        return None if v is None or isinstance(v, bool) else float(v)
    except (TypeError, ValueError):
        return None


def _tif(ev):
    t = ev.get("tipo_orden")
    return ((t or {}).get("limit") or {}).get("tif") if isinstance(t, dict) else None


def nota(op):
    """{nota, puntos, proceso_bueno, cuadrante, comprobaciones:[{clave, nivel, texto, valor}], medidas:{...}}.
    op: operación reconstruida por ledger.operaciones(). None si no llegó a abrirse (señal o descarte)."""
    eventos = sorted(op.get("eventos") or [], key=lambda e: _ts(e.get("ts")) or 0)
    fills_ent = [e for e in eventos if e.get("tipo") == "fill" and e.get("rol") == "entrada"]
    if not fills_ent:
        return None
    comp, medidas = [], {}

    def marca(clave, nivel, texto, valor=None):
        comp.append({"clave": clave, "nivel": nivel, "texto": texto, "valor": valor})

    t_fill = _ts(fills_ent[0]["ts"])
    cerrada = op.get("estado") == "cerrada"

    # 1. Orden de los pasos: el primer fill de entrada tiene que venir DESPUÉS de una decisión aprobada.
    dec = [e for e in eventos if e.get("tipo") == "decision" and not e.get("ampliacion")]
    if not dec or not dec[0].get("aprobada") or (_ts(dec[0]["ts"]) or 0) > (t_fill or 0):
        marca("orden_pasos", "fallo", "Entró sin una decisión aprobada registrada antes del fill.")
    else:
        marca("orden_pasos", "info", "Señal → decisión aprobada → orden → fill, en orden.")

    # 2. Stop: cuánto tardó en estar puesto y si se verificó.
    stops = [e for e in eventos if e.get("tipo") == "proteccion" and e.get("clase") == "stop"
             and e.get("accion") in ("colocado", "verificado")]
    if not stops:
        marca("stop_puesto", "fallo", "No hay ningún stop registrado para esta operación.")
    else:
        espera = max(0.0, (_ts(stops[0]["ts"]) or t_fill) - t_fill)
        medidas["segundos_sin_stop"] = round(espera, 1)
        nivel = "fallo" if espera > STOP_FALLO_S else "aviso" if espera > STOP_AVISO_S else "info"
        marca("stop_puesto", nivel, f"Stop puesto {espera:.0f} s después de la entrada.", round(espera, 1))
        if not any(e.get("accion") == "verificado" for e in stops):
            marca("stop_verificado", "aviso", "El stop se colocó pero no consta verificado en el exchange.")

    # 3. Deslizamiento de entrada (positivo = peor que la señal) y tipo de entrada.
    d = _num(op.get("deslizamiento_entrada_pct"))
    if d is not None:
        pb = round(d * 100, 1)
        medidas["deslizamiento_entrada_pb"] = pb
        nivel = "fallo" if pb > ENTRADA_FALLO_PB else "aviso" if pb > ENTRADA_AVISO_PB else "info"
        marca("deslizamiento_entrada", nivel, f"Entrada {abs(pb):.1f} pb {'peor' if pb > 0 else 'mejor'} que el precio de la señal.", pb)
    envios = [e for e in eventos if e.get("tipo") == "orden_enviada" and e.get("rol") == "entrada"]
    cloid_fill = fills_ent[0].get("cloid")
    envio_fill = next((e for e in envios if e.get("cloid") and e.get("cloid") == cloid_fill), None)
    tif = _tif(envio_fill) if envio_fill else None
    medidas["entrada"] = {"Alo": "creadora", "Gtc": "creadora", "Ioc": "tomadora"}.get(tif, "desconocida")
    if tif == "Ioc" and len(envios) > 1:
        marca("entrada_reserva", "info", "La orden pasiva no se llenó: entró con la orden de reserva (tomadora).")

    # 4. Riesgo real tras el fill frente al planificado.
    post = next((e for e in eventos if e.get("tipo") == "riesgo_post_fill"), None)
    ratio = _num((post or {}).get("ratio"))
    if ratio is not None:
        medidas["riesgo_real_sobre_plan"] = round(ratio, 3)
        nivel = "fallo" if ratio > RIESGO_FALLO else "aviso" if ratio > RIESGO_AVISO else "info"
        marca("riesgo_real", nivel, f"Riesgo real {ratio * 100:.0f} % del planificado.", round(ratio, 3))

    # 5. Costes en R.
    riesgo = _num(op.get("riesgo_inicial_usd"))
    if riesgo and riesgo > 0:
        costes = (_num(op.get("comisiones")) or 0.0) - (_num(op.get("funding_total")) or 0.0)
        cr = round(costes / riesgo, 3)
        medidas["costes_r"] = cr
        marca("costes", "aviso" if cr > COSTES_AVISO_R else "info",
              f"Comisiones y funding: {cr:+.3f} R ({'se comen' if cr > 0 else 'suman'} {abs(cr) * 100:.0f} % del riesgo).", cr)

    # 6. Salida: deslizamiento del stop y pérdida frente al riesgo.
    cierre = next((e for e in reversed(eventos) if e.get("tipo") == "cierre"), None)
    if cierre is not None:
        if str(cierre.get("causa") or "").startswith("stop"):
            peor = _num(cierre.get("peor_que_trigger_pct"))
            if peor is not None:
                pb = round(peor * 100, 1)
                medidas["deslizamiento_stop_pb"] = pb
                nivel = "fallo" if pb > STOP_DESL_FALLO_PB else "aviso" if pb > STOP_DESL_AVISO_PB else "info"
                marca("deslizamiento_stop", nivel, f"El stop se ejecutó {pb:.1f} pb peor que su precio de activación.", pb)
        sin_conf = cierre.get("ordenes_sin_confirmar")
        if sin_conf:
            marca("ordenes_sin_confirmar", "aviso", f"Al cerrar quedaban órdenes sin confirmar: {sin_conf}.")
    r = _num(op.get("r_neto"))
    if r is not None and r < PERDIDA_AVISO_R:
        marca("perdida_vs_riesgo", "fallo" if r < PERDIDA_FALLO_R else "aviso",
              f"Perdió {r:.2f} R: más de lo que arriesgaba el stop.", round(r, 3))

    # 7. Incidencias.
    errores = [a for a in op.get("alertas") or [] if a.get("severidad") == "error"]
    if errores:
        marca("errores", "fallo", f"{len(errores)} error(es) durante la operación.", len(errores))
    desconocidas = sum(1 for e in eventos if e.get("tipo") == "orden_estado" and e.get("estado") == "desconocido")
    if desconocidas:
        marca("estado_desconocido", "aviso", f"{desconocidas} orden(es) pasaron por estado desconocido.", desconocidas)
    if op.get("contabilidad") == "incompleta":
        marca("contabilidad", "fallo", "Contabilidad incompleta: no se pudieron atribuir todos los fills.")
    if any(e.get("tipo") == "fill" and e.get("estimado") for e in eventos):
        marca("estimado", "info", "Parte de los precios son estimados (stop u objetivo tocado con el bot parado).")
    if op.get("eventos_repetidos"):
        marca("repetidos", "info", f"{op['eventos_repetidos']} evento(s) repetido(s), contados una vez.")

    puntos = max(0, 100 - sum(PENALIZACION[c["nivel"]] for c in comp))
    letra = next(n for umbral, n in NOTAS if puntos >= umbral)
    bueno = letra in ("A", "B")
    pnl = _num(op.get("pnl_neto"))
    cuadrante = CUADRANTES[(bueno, pnl > 0)] if cerrada and pnl is not None else None
    return {"version": VERSION, "nota": letra, "puntos": puntos, "proceso_bueno": bueno, "provisional": not cerrada,
            "cuadrante": cuadrante, "comprobaciones": comp, "medidas": medidas}


def _media(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def _mediana(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return round(xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2, 3)


def resumen(ops, desde=0.0, hasta=None):
    """Resumen de las operaciones CERRADAS entre desde y hasta (epoch). ops: iterable de operaciones del ledger."""
    filas = []
    for op in ops:
        t = _ts(op.get("cerrada_ts"))
        if op.get("estado") != "cerrada" or t is None or t < desde or (hasta is not None and t >= hasta):
            continue
        n = nota(op)
        if n:
            filas.append((op, n))
    por_nota = {k: 0 for _, k in NOTAS}
    cuadrantes, fallos = {}, {}
    for op, n in filas:
        por_nota[n["nota"]] += 1
        if n["cuadrante"]:
            cuadrantes[n["cuadrante"]] = cuadrantes.get(n["cuadrante"], 0) + 1
        for c in n["comprobaciones"]:
            if c["nivel"] != "info":
                fallos[c["clave"]] = fallos.get(c["clave"], 0) + 1
    med = [n["medidas"] for _, n in filas]
    calibracion = {}
    for tipo in ("creadora", "tomadora"):
        xs = [m.get("deslizamiento_entrada_pb") for m in med if m.get("entrada") == tipo]
        xs = [x for x in xs if x is not None]
        if xs:
            calibracion[tipo] = {"n": len(xs), "deslizamiento_medio_pb": _media(xs)}
    return {
        "n": len(filas), "por_nota": por_nota, "cuadrantes": cuadrantes,
        "problemas": dict(sorted(fallos.items(), key=lambda kv: -kv[1])),
        "deslizamiento_entrada_pb_medio": _media([m.get("deslizamiento_entrada_pb") for m in med]),
        "deslizamiento_stop_pb_medio": _media([m.get("deslizamiento_stop_pb") for m in med]),
        "segundos_sin_stop_mediana": _mediana([m.get("segundos_sin_stop") for m in med]),
        "costes_r_medio": _media([m.get("costes_r") for m in med]),
        "calibracion_entrada": calibracion,
        "peores": [{"trade_id": op["trade_id"], "moneda": op.get("moneda"), "estrategia": op.get("estrategia"),
                    "nota": n["nota"], "puntos": n["puntos"], "pnl_neto": op.get("pnl_neto"),
                    "problemas": [c["texto"] for c in n["comprobaciones"] if c["nivel"] != "info"]}
                   for op, n in sorted(filas, key=lambda x: x[1]["puntos"])[:10] if n["puntos"] < 100],
        "nota_aviso": "Con menos de 30 operaciones nada es concluyente. En simulado, el deslizamiento es el modelado.",
    }
