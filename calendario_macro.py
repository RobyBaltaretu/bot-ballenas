"""Calendario de citas macro de EE. UU. que mueven las cripto: decisiones de la Reserva Federal (FOMC) y el IPC (CPI).

Idea tomada del «Research Analyst» de HyperGrok (calendario de catalizadores). Las fechas están en
calendario_macro.json, copiadas de las fuentes oficiales (federalreserve.gov y bls.gov) el 22/11/2026; nada se
inventa ni se descarga en vivo. Horas oficiales: FOMC a las 14:00 de Nueva York (comunicado), IPC a las 08:30.

Hoy SOLO lo usa la investigación (estudio «¿perder menos sin abrir cerca de una cita macro?»). Ninguna ruta de
decisión lo lee: archivo «sin efecto» en promocion.py. Si algún día filtra entradas, pasa a ARCHIVOS_CODIGO (cambia la
huella) y solo tras superar el laboratorio.
"""
import json
import os
from datetime import datetime, timedelta, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(AQUI, "calendario_macro.json")
HORA_NY = {"fomc": (14, 0), "cpi": (8, 30)}
# Ventana «cerca de una cita» (horas antes, horas después): la misma que fija investigacion.ESTUDIO_MACRO_VENTANA.
VENTANA_H = (12, 2)


def _domingo(anio, mes, n):
    """n-ésimo domingo del mes (1 = primero)."""
    d = datetime(anio, mes, 1)
    return d + timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))


def desfase_ny(dia):
    """Horas de Nueva York respecto a UTC ese día: −4 en horario de verano (2.º domingo de marzo a 1.er domingo de
    noviembre, regla vigente desde 2007), −5 el resto. Sin zoneinfo: en Windows no siempre hay base de zonas."""
    ini, fin = _domingo(dia.year, 3, 2), _domingo(dia.year, 11, 1)
    return -4 if ini.date() <= dia.date() < fin.date() else -5


def a_utc(fecha, tipo):
    dia = datetime.strptime(fecha, "%Y-%m-%d")
    h, m = HORA_NY[tipo]
    return (dia.replace(hour=h, minute=m) - timedelta(hours=desfase_ny(dia))).replace(tzinfo=timezone.utc).timestamp()


def cargar(ruta=None, programadas=True):
    """[(ts_utc, tipo, fecha)] ordenado. programadas=True deja fuera las reuniones de urgencia (no se conocen antes)."""
    with open(ruta or RUTA, encoding="utf-8") as fh:
        datos = json.load(fh)
    out = []
    for tipo in ("fomc", "cpi"):
        for e in datos[tipo]:
            if programadas and e.get("no_programada"):
                continue
            out.append((a_utc(e["fecha"], tipo), tipo, e["fecha"]))
    return sorted(out)


def en_ventana(ts, eventos, antes_h, despues_h):
    """¿Cae ts entre antes_h horas antes y despues_h horas después de alguna cita? Devuelve el tipo o None."""
    for t, tipo, _ in eventos:
        if t - antes_h * 3600 <= ts <= t + despues_h * 3600:
            return tipo
        if t - antes_h * 3600 > ts:
            break
    return None


def ola_btc(velas_1h, ts, antes_h=12, despues_h=12):
    """Cómo se movió BTC alrededor de una cita, con velas CERRADAS de 1 h [{t (ms), o, h, l, c}].
    Devuelve {serie: [[horas_desde_la_cita, % frente al cierre previo]], mov_4h_pct, rango_4h_pct} o None si faltan
    velas. «Cierre previo» = cierre de la vela que termina justo antes de la cita."""
    por_t = {int(v["t"]) // 1000: v for v in velas_1h}
    base_t = int(ts // 3600 * 3600) - 3600            # vela que contiene el minuto anterior a la cita
    base = por_t.get(base_t)
    if base is None:
        return None
    c0 = float(base["c"])
    serie = []
    for k in range(-antes_h, despues_h + 1):
        v = por_t.get(base_t + k * 3600)
        if v is not None:
            serie.append([round((base_t + k * 3600 + 3600 - ts) / 3600, 2), round((float(v["c"]) / c0 - 1) * 100, 3)])
    tras = [por_t.get(base_t + k * 3600) for k in range(1, 5)]
    if any(v is None for v in tras):
        return None
    alto = max(float(v["h"]) for v in tras)
    bajo = min(float(v["l"]) for v in tras)
    return {"serie": serie, "mov_4h_pct": round((float(tras[-1]["c"]) / c0 - 1) * 100, 3),
            "rango_4h_pct": round((alto - bajo) / c0 * 100, 3)}


def oleaje_normal(velas_1h):
    """Rango mediano de 4 h de BTC (máximo − mínimo de 4 velas seguidas, en % del cierre previo): «un día normal»."""
    vs = sorted(velas_1h, key=lambda v: int(v["t"]))
    rangos = []
    for i in range(1, len(vs) - 4, 4):
        trozo, c0 = vs[i:i + 4], float(vs[i - 1]["c"])
        rangos.append((max(float(v["h"]) for v in trozo) - min(float(v["l"]) for v in trozo)) / c0 * 100)
    if not rangos:
        return None
    rangos.sort()
    return round(rangos[len(rangos) // 2], 3)


def proximas(ahora, eventos, dias=14):
    """Citas de los próximos días (para mostrarlas; no decide nada)."""
    return [{"ts": t, "tipo": tipo, "fecha": f} for t, tipo, f in eventos if ahora <= t <= ahora + dias * 86400]
