"""
Hipótesis PRERREGISTRADAS (17/11/2026, pedido por Roberto): acelerar el veredicto sin hacer trampas.

Por qué: el laboratorio corrige su umbral de t por TODAS las variantes probadas desde siempre (más de mil), así que
pide t ≥ ~4. Es lo correcto cuando se elige la mejor de muchas a posteriori. Aquí se hace lo contrario: se fijan DE
ANTEMANO dos hipótesis concretas (definición cerrada, con fecha) y se juzgan SOLO con datos posteriores a esa fecha.
Como solo se juzgan dos, la corrección es por 2 (t ≥ ~2 en vez de ~4), y sigue siendo honesto porque nada se elige
mirando esos datos.

Reglas (fijas; cambiarlas invalida el preregistro):
  - Datos: solo operaciones ABIERTAS en o después de REGISTRO y ya CERRADAS al final de los datos (las que siguen
    abiertas no cuentan). Las genera la misma regla fija sobre velas nuevas en cada laboratorio.
  - Tamaño de muestra decidido de antemano (sin mirar resultados mientras tanto): las primeras MIN_OPS operaciones
    por fecha de cierre, ampliando solo hasta cubrir MIN_DIAS días distintos. Hasta llegar ahí la hipótesis está
    «acumulando» y su resultado NO se calcula ni se muestra (mirar a medias y parar cuando conviene inflaría los
    falsos positivos).
  - Se juzga UNA sola vez: media > 0, t por días ≥ umbral (Student, una cola, α = 5 % / número de hipótesis) y
    sigue > 0 con costes al doble. El veredicto queda guardado y es definitivo.
  - Si la definición cambia (huella distinta), la hipótesis queda «invalidada»: habría que registrar otra nueva.

Es SOLO informe: ningún resultado de aquí activa, autoriza ni cambia nada del bot. Pasar a real sigue exigiendo
promocion.py y la aprobación de Roberto.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

import validacion as vd

AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA_ESTADO = os.path.join(AQUI, "preregistro_estado.json")
REGISTRO = "2026-11-17T00:00:00Z"
REGISTRO_TS = int(datetime(2026, 11, 17, tzinfo=timezone.utc).timestamp())
ALFA = 0.05
MIN_OPS = 30
MIN_DIAS = 20

HIPOTESIS = {
    "fuerza_4h": {
        "tipo": "modulo", "modulo": "fuerza", "intervalo": "4h", "version": "2",
        "params": {"lookback": 42, "rebalanceo": 84, "top": 2, "sl_atr": 2.5},
        "unidad": "R",
        "descripcion": "Fuerza relativa en 4 h con los parámetros del laboratorio del 15/11/2026 (el módulo con mejor "
                       "media fuera de muestra: +0,297 R en el holdout, sin significación).",
    },
    "carry_realista": {
        "tipo": "carry_realista", "params": {"umbral_anual_pct": 20},
        "unidad": "% del tamaño de una pata",
        "descripcion": "Carry de funding cubierto (corto en el perpetuo de Hyperliquid + largo en contado) cuando el "
                       "funding medio de 24 h supera el 20 % anual; modelo del laboratorio con base y 4 comisiones.",
    },
}


def huella(definicion):
    return hashlib.sha256(json.dumps(definicion, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


# La ruta se resuelve al LLAMAR (no al definir la función): así, quien cambia RUTA_ESTADO (pruebas) no escribe en el
# archivo real. El 17/11/2026 una prueba de humo con datos inventados dejó un veredicto falso de fuerza_4h en el real.
def cargar_estado(ruta=None):
    return vd.leer_registro(ruta or RUTA_ESTADO, {"hipotesis": {}})


def guardar_estado(estado, ruta=None):
    vd.guardar_registro(ruta or RUTA_ESTADO, estado)


def muestra_fija(trades, fin_ts):
    """Muestra decidida de antemano: operaciones abiertas desde REGISTRO y cerradas antes de fin_ts, por fecha de
    cierre; las primeras MIN_OPS ampliadas hasta MIN_DIAS días distintos. None si aún no se llega."""
    validas = sorted((t for t in trades if t["t"] >= REGISTRO_TS and t.get("cierre_ts") and t["cierre_ts"] < fin_ts),
                     key=lambda t: (t["cierre_ts"], t["t"], t.get("moneda", "")))
    dias = set()
    for i, t in enumerate(validas):
        dias.add(int(t["t"] // 86400))
        if i + 1 >= MIN_OPS and len(dias) >= MIN_DIAS:
            return validas[:i + 1]
    return None


def progreso(trades, fin_ts):
    validas = [t for t in trades if t["t"] >= REGISTRO_TS and t.get("cierre_ts") and t["cierre_ts"] < fin_ts]
    return {"operaciones": len(validas), "dias": len({int(t["t"] // 86400) for t in validas}),
            "objetivo": {"operaciones": MIN_OPS, "dias": MIN_DIAS}}


def juzgar(muestra, estres_r):
    """Prueba única sobre la muestra fija. estres_r: resultados de la misma muestra con costes al doble."""
    rs = [t["r"] for t in muestra]
    por_dia = {}
    for t in muestra:
        por_dia[int(t["t"] // 86400)] = por_dia.get(int(t["t"] // 86400), 0.0) + t["r"]
    t_dias = vd.estadistico_t(list(por_dia.values()))
    req = vd.t_requerido(len(HIPOTESIS), alfa=ALFA, n_ops=len(por_dia))
    m, me = vd.media(rs), vd.media(estres_r) if estres_r else None
    comp = [{"regla": "media > 0", "cumple": m > 0, "valor": round(m, 4)},
            {"regla": f"t por días ≥ {req:.2f} (una cola, α 5 %/{len(HIPOTESIS)}, {len(por_dia)} días)",
             "cumple": t_dias >= req, "valor": round(t_dias, 2)},
            {"regla": "sigue > 0 con costes al doble", "cumple": bool(me is not None and me > 0),
             "valor": None if me is None else round(me, 4)}]
    return {"estado": "confirmada" if all(c["cumple"] for c in comp) else "rechazada", "n": len(rs),
            "dias": len(por_dia), "r_medio": round(m, 4), "t_dias": round(t_dias, 2), "t_requerido": round(req, 2),
            "comprobaciones": comp}


def evaluar(clave, trades, fin_ts, estres, estado, ahora=None):
    """Estado de una hipótesis. estres: función(muestra) -> lista de r con costes al doble.
    Modifica 'estado' (lo guarda quien llama). Un veredicto ya emitido no se recalcula nunca."""
    defn = HIPOTESIS[clave]
    h = huella(defn)
    reg = estado["hipotesis"].setdefault(clave, {"huella": h, "registrada": REGISTRO})
    base = {"clave": clave, "descripcion": defn["descripcion"], "unidad": defn["unidad"], "registrada": REGISTRO,
            "huella": h}
    if reg.get("huella") != h:
        return dict(base, estado="invalidada", motivo="la definición cambió después de registrarla: no se juzga; "
                                                      "habría que preregistrar una hipótesis nueva")
    if reg.get("veredicto"):
        return dict(base, definitivo=True, **reg["veredicto"])
    if trades is None:
        return dict(base, estado="no_evaluable", motivo="el laboratorio no generó operaciones para esta definición")
    muestra = muestra_fija(trades, fin_ts)
    if muestra is None:
        return dict(base, estado="acumulando", progreso=progreso(trades, fin_ts),
                    motivo="se juzga una sola vez al llegar a la muestra fijada; hasta entonces no se mira el resultado")
    ver = dict(juzgar(muestra, estres(muestra)),
               fecha=datetime.fromtimestamp(ahora or datetime.now(timezone.utc).timestamp(), timezone.utc)
               .isoformat(timespec="seconds"))
    reg["veredicto"] = ver
    return dict(base, definitivo=True, **ver)
