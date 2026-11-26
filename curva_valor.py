"""Curva de valor diaria de la cuenta (CP-M17, auditoría 26/11/2026, T-13).

estado.json guarda el valor cada 5 min pero solo los últimos 3 000 puntos (~10 días): no sirve para medir la caída o
comparar periodos desde la puesta a cero. Aquí se guarda UN punto por día UTC en registro/curva_valor.jsonl, que nunca
se recorta. Cada punto es el valor de la cuenta AL EMPEZAR el día (el primero que ve el bot ese día).

Al crear el archivo se rellenan los días anteriores desde la puesta a cero, sin inventar nada y diciendo de dónde sale
cada punto («fuente»):
  - "historial_saldo": primer punto de ese día en estado.json (valor real de la cuenta, con lo no realizado);
  - "ledger_realizado": saldo inicial + resultado neto de las operaciones cerradas antes de ese día (registro/ledger);
    no incluye lo no realizado de las abiertas en ese momento;
  - "equity": valor leído en directo por el bot.
Cada línea lleva «cuenta_desde» (la puesta a cero a la que pertenece): una puesta a cero nueva no borra la anterior.

Solo escribe un informe: no decide nada (está en promocion.ARCHIVOS_SIN_EFECTO).
"""
import json
import os
from datetime import datetime, timezone

DIA_S = 86400
ARCHIVO = "curva_valor.jsonl"          # dentro de registro/


def dia_utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_iso(txt):
    return datetime.strptime(txt[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()


def leer(ruta):
    """Puntos guardados (lista de dicts). Una línea ilegible se salta (no se reescribe el archivo)."""
    out = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                try:
                    p = json.loads(linea)
                except ValueError:
                    continue
                if isinstance(p, dict) and p.get("dia"):
                    out.append(p)
    except OSError:
        pass
    return out


def _anadir(ruta, puntos):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "a", encoding="utf-8", newline="\n") as f:
        for p in puntos:
            f.write(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n")


def reconstruir(inicio_ts, saldo_inicial, cierres, historial, hasta_ts):
    """Un punto por cada día UTC desde la puesta a cero ('inicio_ts') hasta el día ANTERIOR a 'hasta_ts'.
    'cierres' = [(ts, pnl_neto)] de operaciones cerradas; 'historial' = [[ts, valor]] de estado.json."""
    if not inicio_ts:
        inicio_ts = min([h[0] for h in historial] or [hasta_ts])
    cuenta_desde = iso(inicio_ts)
    primero_del_dia = {}
    for ts, valor in sorted(historial or []):
        if ts >= inicio_ts and valor is not None:
            primero_del_dia.setdefault(dia_utc(ts), (ts, valor))
    cierres = sorted((ts, pnl) for ts, pnl in cierres if ts >= inicio_ts and pnl is not None)
    out = []
    d0 = int(inicio_ts // DIA_S) * DIA_S
    hoy = int(hasta_ts // DIA_S) * DIA_S
    t = d0
    while t < hoy:
        dia = dia_utc(t)
        if dia in primero_del_dia:
            ts, valor = primero_del_dia[dia]
            out.append({"dia": dia, "ts": iso(ts), "equity": round(valor, 4), "fuente": "historial_saldo",
                        "cuenta_desde": cuenta_desde})
        elif saldo_inicial is not None:
            desde = max(t, inicio_ts)
            realizado = sum(p for ts, p in cierres if ts < desde)
            out.append({"dia": dia, "ts": iso(desde), "equity": round(saldo_inicial + realizado, 4),
                        "fuente": "ledger_realizado", "cuenta_desde": cuenta_desde})
        t += DIA_S
    return out


def cierres_del_ledger(eventos):
    """[(ts, pnl_neto)] de los eventos «cierre» del ledger con resultado conocido."""
    out = []
    for e in eventos or []:
        if e.get("tipo") == "cierre" and e.get("pnl_neto") is not None:
            try:
                out.append((_ts_iso(e["ts"]), float(e["pnl_neto"])))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def registrar(ruta, ahora, equity, inicio_ts, saldo_inicial=None, eventos_ledger=None, historial=None):
    """Añade el punto de hoy si aún no está. Si la cuenta actual (puesta a cero 'inicio_ts') no tiene ningún punto,
    antes rellena los días anteriores. 'eventos_ledger' puede ser una función (solo se lee si hace falta).
    Devuelve la lista de puntos añadidos."""
    if equity is None:
        return []
    puntos = leer(ruta)
    cuenta_desde = iso(inicio_ts) if inicio_ts else (puntos[-1]["cuenta_desde"] if puntos else iso(ahora))
    mios = [p for p in puntos if p.get("cuenta_desde") == cuenta_desde]
    hoy = dia_utc(ahora)
    if any(p["dia"] == hoy for p in mios):
        return []
    nuevos = []
    if not mios:
        eventos = eventos_ledger() if callable(eventos_ledger) else eventos_ledger
        nuevos = reconstruir(inicio_ts or _ts_iso(cuenta_desde), saldo_inicial, cierres_del_ledger(eventos),
                             historial, ahora)
    # Con la cuenta ya empezada, los días sin bot (parado) quedan como hueco: no se rellenan con suposiciones.
    nuevos.append({"dia": hoy, "ts": iso(ahora), "equity": round(equity, 4), "fuente": "equity",
                   "cuenta_desde": cuenta_desde})
    _anadir(ruta, nuevos)
    return nuevos
