"""Lectura de las cachés locales de Binance (velas de 4 h, funding de 8 h) y paso a velas diarias UTC.
No sale a la red: si falta un archivo, esa moneda no entra en el estudio."""

import glob
import json
import os
from collections import deque

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_EXTERNO = os.path.join(AQUI, "datos_backtest", "externo")
DIA_MS = 86_400_000
BARRAS_POR_DIA = 6
# No son monedas de riesgo cripto (oro tokenizado): fuera de todos los estudios.
EXCLUIDAS = {"PAXGUSDT", "XAUTUSDT", "USDCUSDT", "TUSDUSDT", "FDUSDUSDT"}


def _leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def simbolos(carpeta=DIR_EXTERNO):
    """Símbolos de Binance con velas de 4 h en la caché, sin las excluidas."""
    out = []
    for f in sorted(glob.glob(os.path.join(carpeta, "binance_*_4h_v2.json"))):
        s = os.path.basename(f)[len("binance_"):-len("_4h_v2.json")]
        if not s.startswith("spot_") and s not in EXCLUIDAS:
            out.append(s)
    return out


def velas_4h(simbolo, carpeta=DIR_EXTERNO):
    return _leer(os.path.join(carpeta, f"binance_{simbolo}_4h_v2.json"))


def funding_binance(simbolo, carpeta=DIR_EXTERNO):
    return _leer(os.path.join(carpeta, f"binance_{simbolo}_funding.json"))


def diarias(velas):
    """Velas de 4 h -> {dia: {"o","h","l","c","usd"}} solo con días COMPLETOS (6 velas). dia = t_ms // 86 400 000.
    La vela diaria de `dia` cierra a las 00:00 UTC del día siguiente: solo se usa cuando ya está cerrada."""
    por_dia = {}
    for v in sorted(velas, key=lambda x: x["t"]):
        por_dia.setdefault(int(v["t"]) // DIA_MS, []).append(v)
    out = {}
    for d, vs in por_dia.items():
        if len(vs) != BARRAS_POR_DIA:
            continue
        out[d] = {"o": float(vs[0]["o"]), "h": max(float(x["h"]) for x in vs), "l": min(float(x["l"]) for x in vs),
                  "c": float(vs[-1]["c"]), "usd": sum(float(x.get("v") or 0) * float(x["c"]) for x in vs)}
    return out


def funding_por_dia(regs, defecto_dia=None):
    """Registros de funding -> {dia: suma de la tasa cobrada ese día} (fracción del nocional, positiva = largos pagan).
    Cada registro cubre el periodo ANTERIOR a su hora de pago: el de las 00:00 pertenece al día que termina."""
    out = {}
    for r in regs:
        d = (int(r["time"]) - 1) // DIA_MS
        out[d] = out.get(d, 0.0) + float(r["fundingRate"])
    return out


def cargar_panel(lista=None, carpeta=DIR_EXTERNO):
    """{moneda: {"dias": {dia: vela}, "funding": {dia: tasa}}} con el nombre sin 'USDT'."""
    panel = {}
    for s in (lista if lista is not None else simbolos(carpeta)):
        d = diarias(velas_4h(s, carpeta))
        if len(d) < 60:
            continue
        panel[s[:-4] if s.endswith("USDT") else s] = {"dias": d, "funding": funding_por_dia(funding_binance(s, carpeta))}
    return panel


def rango_dias(panel):
    todos = [d for p in panel.values() for d in p["dias"]]
    return (min(todos), max(todos)) if todos else (0, -1)


def maximos_moviles(serie, n):
    """Para cada posición i, máximo de serie[i-n:i] (excluye i). None si no hay n datos. O(len)."""
    return _movil(serie, n, mayor=True)


def minimos_moviles(serie, n):
    return _movil(serie, n, mayor=False)


def _movil(serie, n, mayor):
    out, dq = [None] * len(serie), deque()
    for i, x in enumerate(serie):
        if i >= n:
            while dq and dq[0] < i - n:
                dq.popleft()
            out[i] = serie[dq[0]]
        while dq and ((serie[dq[-1]] <= x) if mayor else (serie[dq[-1]] >= x)):
            dq.pop()
        dq.append(i)
    return out
