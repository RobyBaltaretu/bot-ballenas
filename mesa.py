"""
MESA (18/11/2026, idea de un vídeo de un panel de «equipo de agentes»): responde a «¿por qué no entra nada?».

Toma las propuestas de las estrategias (operaciones del registro con su decisión) y cuenta, en lenguaje llano, qué
filtro las frenó en el último cierre de vela y en las últimas 24 h. Solo LEE datos ya registrados: no decide, no
cambia nada y no opera. Funciones puras (se prueban con filas de ejemplo).

Un motivo que no se reconoce se cuenta como «Otros motivos» (nunca se esconde ni se inventa).
"""

import re

# (patrón en minúsculas, etiqueta corta). Se prueba en este orden: el primero que encaja gana.
REGLAS = (
    (r"misma direcci", "Ya hay el máximo del mismo lado"),
    (r"máximo de posiciones abiertas|max.*posiciones abiertas", "Máximo de posiciones abiertas"),
    (r"riesgo abierto total", "Riesgo abierto al máximo"),
    (r"tamaño mínimo|minimo de orden|mínimo.*riesgo", "Orden mínima mayor que el riesgo permitido"),
    (r"stop .*fuera de l[ií]mites|stop .*demasiado", "Stop demasiado lejos o demasiado cerca"),
    (r"funding", "Funding en contra"),
    (r"volatilidad", "Volatilidad extrema"),
    (r"correlaci|correlad", "Muy correlacionada con otra abierta"),
    (r"exposici", "Exposición al máximo"),
    (r"liquidaci", "Liquidación demasiado cerca"),
    (r"horquilla|spread", "Horquilla demasiado ancha"),
    (r"impacto|libro de [oó]rdenes|profundidad", "Poca liquidez en el libro"),
    (r"coste|comisi", "Costes demasiado altos"),
    (r"avanz[oó] .* r desde la se", "El precio ya se había ido"),
    (r"enfriamiento", "Enfriamiento tras cerrar en esa moneda"),
    (r"cerebro", "El cerebro no ve ventaja"),
    (r"pausa|racha|bloque|p[eé]rdida (diaria|semanal)|ca[ií]da desde", "Pausa o límite de pérdida"),
    (r"datos|precio actual|obsolet|cuenta no es reciente", "Datos no frescos"),
    (r"tendencia de btc|r[eé]gimen", "En contra de la tendencia de BTC"),
    (r"solo investigaci|estrategia apagada", "Hipótesis solo de investigación"),
)
SOLO_INVESTIGACION = "Hipótesis solo de investigación"


def etiqueta(motivo):
    m = str(motivo or "").lower()
    for patron, nombre in REGLAS:
        if re.search(patron, m):
            return nombre
    return "Otros motivos"


def _resumen(filas):
    """Cuenta propuestas, entradas y motivos (cada propuesta cuenta una vez por motivo distinto)."""
    total, entran, rechazadas, motivos = 0, 0, 0, {}
    for f in filas:
        etqs = {etiqueta(x) for x in (f.get("motivos") or [])}
        if etqs == {SOLO_INVESTIGACION}:
            continue                                  # no son operables por diseño: no ensucian la respuesta
        total += 1
        if f.get("estado") == "rechazada":
            rechazadas += 1
            for e in etqs or {"Otros motivos"}:
                motivos[e] = motivos.get(e, 0) + 1
        elif f.get("estado") != "senal":
            entran += 1
    lista = sorted(({"motivo": k, "n": v} for k, v in motivos.items()), key=lambda x: (-x["n"], x["motivo"]))
    return {"propuestas": total, "entran": entran, "rechazadas": rechazadas, "sin_decision": total - entran - rechazadas,
            "motivos": lista}


def embudo(filas, ahora, cluster_seg=1800, ventana_seg=86400):
    """filas: [{ts, estado, motivos, estrategia, moneda, lado}]. Devuelve el último cierre con propuestas y las 24 h."""
    validas = [f for f in filas if f.get("ts")]
    if not validas:
        return {"ultimo": None, "dia": _resumen([])}
    tmax = max(f["ts"] for f in validas)
    ultimo = [f for f in validas if f["ts"] >= tmax - cluster_seg]
    dia = [f for f in validas if f["ts"] >= ahora - ventana_seg]
    r = _resumen(ultimo)
    r.update(ts=tmax, hace_seg=max(0, ahora - tmax),
             estrategias=sorted({f.get("estrategia") for f in ultimo if f.get("estrategia")}))
    return {"ultimo": r if r["propuestas"] else None, "dia": _resumen(dia),
            "solo_investigacion_24h": sum(1 for f in dia if {etiqueta(x) for x in (f.get("motivos") or [])} == {SOLO_INVESTIGACION})}
