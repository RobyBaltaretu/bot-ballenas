"""Prueba con historia de la cuenta agresiva: las MISMAS reglas y la misma cuenta (logica.py, cuenta.py) sobre velas de
15 min de Binance (datos públicos de futuros, solo lectura, sin cuenta ni claves), y después miles de secuencias al azar
de sus resultados por DÍAS para estimar la probabilidad de quebrar.

    python -m agresiva.historia [--dias 120] [--monedas 20]

Universo por fecha (auditoría del 25/11/2026, F9): cada día se operan las --monedas de más volumen en Binance de los 7 días
anteriores, elegidas entre todas las monedas que cotizan a la vez en Hyperliquid (también las ya retiradas) y en Binance.
Así no se elige con el volumen de HOY lo que habría que haber elegido hace meses.

Diferencias con el vivo (para no engañarnos):
  - precios de Binance, no de Hyperliquid (muy parecidos en monedas grandes, no idénticos); stop y liquidación con esa
    misma vela (en vivo, vela combinada Hyperliquid + Binance tipo precio de marca);
  - el recorrido dentro de cada vela se supone (alcista o→l→h→c, bajista o→h→l→c) con velas de 15 min, no de 1 min;
  - entrada a la apertura de la vela siguiente con deslizamiento fijo (desliz_pct), sin libro real;
  - funding de Binance (cada 8 h, mismo total aproximado que el horario de Hyperliquid), no el de Hyperliquid;
  - el apalancamiento máximo y los tramos de cada moneda son los de HOY en Hyperliquid;
  - el universo diario se ordena por el volumen de Binance (en vivo, por el de Hyperliquid con un mínimo de 20 M$);
  - tras una quiebra la cuenta vuelve a empezar sola (en vivo solo a mano) para poder contar cuántas veces quiebra.
Escribe agresiva_historia.json (lo muestra el panel). Nada de esto opera.
"""

import argparse
import json
import os
import random
import sys
import time

import requests

from agresiva import logica
from agresiva.cuenta import Cuenta, estado_nuevo
from agresiva.motor import AQUI, _escribir_json, _info, _stats, simbolo_binance, tramos_margen

DIR = os.path.join(AQUI, "datos_backtest", "agresiva_15m")
DIR_DIA = os.path.join(AQUI, "datos_backtest", "agresiva_1d")
DIR_FUNDING = os.path.join(AQUI, "datos_backtest", "agresiva_funding")
BINANCE = "https://fapi.binance.com/fapi/v1/klines"
BINANCE_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"
BINANCE_FUNDING = "https://fapi.binance.com/fapi/v1/fundingRate"
Q = logica.QUINCE_MIN_MS
DIA = 86_400_000
_simbolo = simbolo_binance                      # nombre antiguo (scripts de la auditoría)


def _pedir(get, url, params):
    """GET público a Binance con espera si limita. None si el símbolo no existe o falla."""
    for _ in range(6):
        r = get(url, params)
        if r.status_code in (418, 429):
            time.sleep(20)
            continue
        return r.json() if r.status_code == 200 else None
    return None


def velas_binance(simbolo, desde_ms, hasta_ms, get=None, carpeta=DIR, intervalo="15m"):
    """Velas con caché en disco (solo se pide lo que falta)."""
    paso = {"15m": Q, "1d": DIA}[intervalo]
    get = get or (lambda url, p: requests.get(url, params=p, timeout=30))
    ruta = os.path.join(carpeta, f"{simbolo}.json")
    try:
        with open(ruta, encoding="utf-8") as fh:
            guardadas = {v["t"]: v for v in json.load(fh)}
    except (OSError, ValueError):
        guardadas = {}
    t = max([desde_ms] + [k + paso for k in guardadas if k >= desde_ms])
    while t < hasta_ms:
        lote = _pedir(get, BINANCE, {"symbol": simbolo, "interval": intervalo, "startTime": t, "endTime": hasta_ms, "limit": 1500})
        if not lote:
            break
        for k in lote:
            guardadas[int(k[0])] = {"t": int(k[0]), "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]),
                                    "v": float(k[7])}            # volumen en USDT
        nuevo = int(lote[-1][0]) + paso
        if nuevo <= t:
            break
        t = nuevo
        time.sleep(0.25)
    velas = [guardadas[k] for k in sorted(guardadas) if desde_ms <= k and k + paso <= hasta_ms]
    if guardadas:
        os.makedirs(carpeta, exist_ok=True)
        _escribir_json(ruta, [guardadas[k] for k in sorted(guardadas)])
    return velas


def funding_binance(simbolo, desde_ms, hasta_ms, get=None, carpeta=DIR_FUNDING):
    """{t (redondeado a la vela de 15 min): tasa} con los pagos de funding de Binance, con caché."""
    get = get or (lambda url, p: requests.get(url, params=p, timeout=30))
    ruta = os.path.join(carpeta, f"{simbolo}.json")
    try:
        with open(ruta, encoding="utf-8") as fh:
            guardados = {int(k): v for k, v in json.load(fh).items()}
    except (OSError, ValueError):
        guardados = {}
    t = max([desde_ms] + [k + 1 for k in guardados if k >= desde_ms])
    while t < hasta_ms:
        lote = _pedir(get, BINANCE_FUNDING, {"symbol": simbolo, "startTime": t, "endTime": hasta_ms, "limit": 1000})
        if not lote:
            break
        for f in lote:
            guardados[int(f["fundingTime"])] = float(f["fundingRate"])
        nuevo = int(lote[-1]["fundingTime"]) + 1
        if nuevo <= t or len(lote) < 1000:
            break
        t = nuevo
        time.sleep(0.5)
    if guardados:
        os.makedirs(carpeta, exist_ok=True)
        _escribir_json(ruta, {str(k): v for k, v in sorted(guardados.items())})
    return {k // Q * Q: v for k, v in guardados.items() if desde_ms <= k <= hasta_ms}


def universo_por_dia(diarias, n, dias_vol=7):
    """diarias: {coin: [velas de 1 día con v en USDT]}. Devuelve {inicio_del_día_ms: set(monedas)}: las n de más volumen en
    los dias_vol días ANTERIORES (nunca el propio día: sería mirar el futuro). Una moneda necesita esos dias_vol días."""
    vol = {coin: {v["t"]: v["v"] for v in vs} for coin, vs in diarias.items()}
    dias = sorted({t for vs in vol.values() for t in vs})
    out = {}
    for d in dias:
        previos = [d - k * DIA for k in range(1, dias_vol + 1)]
        filas = [(sum(vol[c][p] for p in previos), c) for c in vol if all(p in vol[c] for p in previos)]
        out[d] = {c for _, c in sorted(filas, reverse=True)[:n]}
    return out


def simular(series, mercado, c, inicial=None, funding=None, universo=None):
    """series: {coin: [velas 15 min]}; mercado: {coin: {"sz_dec", "apal_max", "tramos"}}; funding: {coin: {t: tasa}};
    universo: {inicio_día_ms: set(monedas)} (sin él, todas). Recorre el tiempo vela a vela con la misma cuenta que el vivo.
    Devuelve la cuenta y las quiebras."""
    inicial = float(inicial or c["cuenta_inicial_usd"])
    funding = funding or {}
    indic = {k: logica.indicadores(v) for k, v in series.items()}
    pos = {k: {v["t"]: i for i, v in enumerate(vs)} for k, vs in series.items()}
    tiempos = sorted({v["t"] for vs in series.values() for v in vs})
    cuenta = Cuenta(estado_nuevo(tiempos[0] / 1000 if tiempos else 0, inicial), c, max_cerradas=None)
    ultimo = {}
    pendientes = []                                        # señales detectadas al cierre de la vela anterior
    quiebras = []
    for t in tiempos:
        ahora = t / 1000
        velas_t = {k: series[k][pos[k][t]] for k in series if t in pos[k]}
        for coin, det in pendientes:                       # entrada a la apertura de esta vela
            v = velas_t.get(coin)
            if not v or coin in cuenta.d["abiertas"]:
                continue
            marcas = dict(ultimo)
            o = v["o"]
            llenar = lambda compra, sz, o=o: o * (1 + (1 if compra else -1) * c["desliz_pct"] / 100)
            s = cuenta.abrir(coin, dict(det, precio=o), mercado[coin], marcas, llenar, ahora)
            if "error" not in s:
                for cual in ("agresiva", "gemela"):
                    if s.get(cual):
                        s[cual]["abierta_ms"] = t
                s["abierta_ms"] = t
        pendientes = []
        for coin, v in velas_t.items():
            if coin in cuenta.d["abiertas"]:
                tasa = funding.get(coin, {}).get(t)
                if tasa is not None and t > cuenta.d["abiertas"][coin]["abierta_ms"]:
                    cuenta.funding(coin, v["o"], tasa)
                cuenta.avanzar(coin, v)
            ultimo[coin] = v["c"]
        evs = cuenta.frenos(ahora + Q / 1000, ultimo)
        if any(e["tipo"] == "quiebra" for e in evs):
            quiebras.append({"t": t, "etapa": cuenta.d["etapa"]["n"]})
            cuenta.reiniciar(ultimo, ahora + Q / 1000)
        cuenta.anotar_curva(ahora, ultimo)
        hoy = universo.get(t // DIA * DIA, set()) if universo is not None else None
        for coin in velas_t:
            if coin not in cuenta.d["abiertas"] and (hoy is None or coin in hoy):
                det = logica.detectar_en(series[coin], pos[coin][t], indic[coin], c)
                if det:
                    cuenta.d["contadores"]["senales"] += 1
                    pendientes.append((coin, det))
    return cuenta, quiebras


def monte_carlo(rendimientos_pct, pasos, corridas=5000, quiebra_pct=10.0, semilla=7, unidad="días"):
    """Sorteo con reposición de los rendimientos (% de la cuenta en cada paso: un día entero, con todas sus operaciones,
    para respetar que suelen ir juntas), compuestos uno tras otro."""
    if not rendimientos_pct:
        return None
    azar = random.Random(semilla)
    finales, caidas, ruinas, hasta_ruina = [], [], 0, []
    for _ in range(corridas):
        eq, pico, caida = 1.0, 1.0, 0.0
        for k in range(pasos):
            eq *= max(0.0, 1 + azar.choice(rendimientos_pct) / 100)
            pico = max(pico, eq)
            caida = max(caida, 1 - eq / pico) if pico else 1.0
            if eq < quiebra_pct / 100:
                ruinas += 1
                hasta_ruina.append(k + 1)
                break
        finales.append(eq)
        caidas.append(caida)
    finales.sort()
    caidas.sort()
    pct = lambda xs, q: xs[min(len(xs) - 1, int(q * len(xs)))]
    return {"corridas": corridas, "pasos_por_corrida": pasos, "unidad": unidad,
            "prob_quiebra_pct": round(ruinas / corridas * 100, 2),
            "mediana_pasos_hasta_quiebra": sorted(hasta_ruina)[len(hasta_ruina) // 2] if hasta_ruina else None,
            "final_mediana_x": round(pct(finales, 0.5), 4), "final_p10_x": round(pct(finales, 0.1), 4),
            "final_p90_x": round(pct(finales, 0.9), 4), "caida_max_mediana_pct": round(pct(caidas, 0.5) * 100, 1),
            "prob_acabar_perdiendo_pct": round(sum(1 for x in finales if x < 1) / corridas * 100, 1)}


def rendimientos_diarios(cerradas, cual, desde_ms, hasta_ms):
    """% de la cuenta ganado o perdido cada día (suma de las operaciones cerradas ese día; 0 los días sin operaciones)."""
    por_dia = {d: 0.0 for d in range(desde_ms // DIA * DIA, hasta_ms, DIA)}
    for f in cerradas:
        p = f.get(cual)
        if p and p.get("pct_cuenta") is not None and p.get("cerrada_ms"):
            d = p["cerrada_ms"] // DIA * DIA
            por_dia[d] = por_dia.get(d, 0.0) + p["pct_cuenta"]
    return [por_dia[d] for d in sorted(por_dia)]


def informe(cuenta, quiebras, series, c, dias, desde_ms, hasta_ms, universo=None, funding=None):
    cer = cuenta.d["cerradas"]
    por_regla = {r: {"nombre": logica.NOMBRES[r], "agresiva": _stats([f for f in cer if f["regla"] == r], "agresiva"),
                     "gemela": _stats([f for f in cer if f["regla"] == r], "gemela")} for r in c["reglas"]}
    rend_a = rendimientos_diarios(cer, "agresiva", desde_ms, hasta_ms)
    rend_g = rendimientos_diarios(cer, "gemela", desde_ms, hasta_ms)
    etapas = cuenta.d["reinicios"] + [{"etapa": cuenta.d["etapa"]["n"], "inicio": cuenta.d["etapa"]["inicio"], "fin": None,
                                       "inicial_usd": cuenta.d["etapa"]["inicial_usd"],
                                       "final_usd": round(cuenta.equity_agresiva({}), 2), "estado_final": "en curso"}]
    duraciones = [round((e["fin"] - e["inicio"]) / 86400, 1) for e in cuenta.d["reinicios"] if e.get("fin")]
    distintas = sorted({x for s in (universo or {}).values() for x in s}) if universo else sorted(series)
    return {"generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "fuente": "Binance futuros (velas de 15 min, públicas)",
            "dias": dias, "desde": time.strftime("%Y-%m-%d", time.gmtime(desde_ms / 1000)),
            "hasta": time.strftime("%Y-%m-%d", time.gmtime(hasta_ms / 1000)), "monedas": distintas,
            "universo_diario": max((len(s) for s in (universo or {}).values()), default=len(series)),
            "velas": sum(len(v) for v in series.values()), "senales": cuenta.d["contadores"]["senales"],
            "operaciones": len(cer), "sin_hueco": cuenta.d["contadores"]["sin_hueco"],
            "solo_gemela": cuenta.d["contadores"].get("solo_gemela", 0), "solo_agresiva": cuenta.d["contadores"].get("solo_agresiva", 0),
            "total": {"agresiva": _stats(cer, "agresiva"), "gemela": _stats(cer, "gemela")}, "por_regla": por_regla,
            "quiebras": len(quiebras), "dias_por_etapa_quebrada": duraciones, "etapas": etapas,
            "gemela_final_usd": round(cuenta.equity_gemela({}), 2), "gemela_caida_max_pct": round(cuenta.d["gemela"]["caida_max_pct"], 2),
            "monte_carlo": {"agresiva": monte_carlo(rend_a, len(rend_a), quiebra_pct=c["quiebra_pct"]),
                            "gemela": monte_carlo(rend_g, len(rend_g), quiebra_pct=c["quiebra_pct"])},
            "parametros": {k: c[k] for k in ("riesgo_pct", "apalancamiento", "margen_max_pct", "max_abiertas", "margen_total_max_pct",
                                             "min_orden_usd", "stop_atr", "stop_min_pct", "stop_max_pct", "objetivos_r", "horas_max",
                                             "desliz_pct", "comision_taker_pct", "comision_maker_pct", "quiebra_pct")},
            "limitaciones": ["precios de Binance, no de Hyperliquid (también para stop y liquidación)",
                             "recorrido supuesto dentro de cada vela de 15 min", "entrada a la apertura siguiente con deslizamiento fijo",
                             "funding de Binance (cada 8 h), no el horario de Hyperliquid" if funding else "sin funding",
                             "apalancamiento máximo de hoy",
                             "universo diario por volumen de Binance de los 7 días previos" if universo else "monedas elegidas con el volumen de hoy",
                             "tras quebrar vuelve a empezar sola para contar quiebras"]}


def _simbolos_binance(get):
    info = _pedir(get, BINANCE_INFO, {}) or {}
    return {s["symbol"] for s in info.get("symbols", [])
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT"}


def principal(argv=None):
    ap = argparse.ArgumentParser(description="Prueba con historia de 15 min de la cuenta agresiva (solo lectura de datos públicos)")
    ap.add_argument("--dias", type=int, default=120)
    ap.add_argument("--monedas", type=int, default=20, help="monedas operables cada día (las de más volumen de los 7 días previos)")
    args = ap.parse_args(argv)
    c = logica.cfg(**(json.load(open(os.path.join(AQUI, "agresiva_config.json"), encoding="utf-8"))
                      if os.path.exists(os.path.join(AQUI, "agresiva_config.json")) else {}))
    get = lambda url, p: requests.get(url, params=p, timeout=30)
    meta, _ = _info({"type": "metaAndAssetCtxs"}, requests.post)
    tramos = tramos_margen(meta)
    hl = {a["name"]: a for a in meta["universe"]}               # también las retiradas: menos sesgo de supervivencia
    en_binance = _simbolos_binance(get)
    candidatas = {coin: simbolo_binance(coin) for coin in hl if simbolo_binance(coin) in en_binance}
    hasta = (int(time.time() * 1000) // Q) * Q
    desde = hasta - args.dias * DIA
    print(f"{len(candidatas)} monedas en Hyperliquid y en Binance: volumen diario para elegir el universo de cada día…", flush=True)
    diarias = {}
    for coin, sim in sorted(candidatas.items()):
        vs = velas_binance(sim, desde - 8 * DIA, hasta, get=get, carpeta=DIR_DIA, intervalo="1d")
        if vs:
            diarias[coin] = vs
    universo = {d: s for d, s in universo_por_dia(diarias, args.monedas).items() if desde <= d < hasta}
    elegidas = sorted({x for s in universo.values() for x in s})
    print(f"{len(elegidas)} monedas entran algún día en el universo: velas de 15 min y funding…", flush=True)
    series, mercado, funding = {}, {}, {}
    for coin in elegidas:
        sim = candidatas[coin]
        velas = velas_binance(sim, desde - 2 * DIA, hasta, get=get)          # 2 días antes para calentar los indicadores
        if len(velas) < logica.MIN_VELAS:
            continue
        a = hl[coin]
        series[coin] = velas
        mercado[coin] = {"sz_dec": int(a.get("szDecimals", 0)), "apal_max": int(a.get("maxLeverage", 1)), "tramos": tramos.get(coin, [])}
        funding[coin] = funding_binance(sim, desde - 2 * DIA, hasta, get=get)
        print(f"  {coin}: {len(velas)} velas · {sum(1 for s in universo.values() if coin in s)} días en el universo · "
              f"máx. {mercado[coin]['apal_max']}×", flush=True)
    cuenta, quiebras = simular(series, mercado, c, funding=funding, universo=universo)
    out = informe(cuenta, quiebras, series, c, args.dias, desde, hasta, universo=universo, funding=funding)
    _escribir_json(os.path.join(AQUI, "agresiva_historia.json"), out)
    t, g = out["total"]["agresiva"], out["total"]["gemela"]
    print(f"\n{out['operaciones']} operaciones en {args.dias} días · {out['quiebras']} quiebras de la cuenta agresiva")
    print(f"gemela: R medio {g.get('r_media')} · acierto {g.get('acierto_pct')} % · {g.get('pnl_usd')} $")
    print(f"agresiva: {t.get('pnl_usd')} $ · riesgo medio {t.get('riesgo_pct_media')} % · liquidaciones {t.get('liquidaciones')} · "
          f"stops {t.get('stops')}")
    print("Monte Carlo agresiva (por días):", out["monte_carlo"]["agresiva"])
    return 0


if __name__ == "__main__":
    sys.exit(principal())
