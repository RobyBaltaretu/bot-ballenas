"""Fase 0 del carry: verificar el terreno. SOLO LECTURA de la API pública de Hyperliquid (sin firmar, sin cuenta).

Responde: ¿qué monedas de nuestro universo tienen contado (spot) en Hyperliquid, cuánto se aleja su precio del
perpetuo (la «base»), y hay libro suficiente para entrar y salir sin mover el precio? Guarda el resultado en
datos_mercado/spot_hl.json.

Aviso que costó encontrarlo: en spotMetaAndAssetCtxs la lista de pares y la de contextos NO van en el mismo orden.
Hay que emparejarlas por NOMBRE del par (ctx["coin"] == universe[i]["name"]); emparejarlas por posición da precios de
otra moneda (BTC aparecía como «NEKO»).

Uso:  python -m carry.terreno        (o python carry/terreno.py)
"""

import json
import os
import sys
import time

import requests

from compat import reemplazar

AQUI =os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL_INFO = "https://api.hyperliquid.xyz/info"
RUTA_SALIDA = os.path.join(AQUI, "datos_mercado", "spot_hl.json")
PERMITIDOS = ("spotMetaAndAssetCtxs", "metaAndAssetCtxs", "l2Book", "fundingHistory")        # solo consultas públicas de lectura

BASE_MAX_PCT = 0.5            # |spot / perpetuo - 1| máximo
VOL_MIN_USD = 1_000_000       # volumen de 24 h mínimo del par
SPREAD_MAX_PCT = 0.05         # horquilla máxima
PROF_MIN_USD = 20_000         # profundidad mínima a ±0,25 % del precio medio, en el lado más flojo
VENTANA_PROF_PCT = 0.25


class ErrorTerreno(RuntimeError):
    pass


def _info(carga, post=requests.post):
    """Única puerta de salida a la red: solo /info y solo consultas de la lista blanca."""
    if carga.get("type") not in PERMITIDOS:
        raise ErrorTerreno(f"consulta no permitida: {carga.get('type')}")
    r = post(URL_INFO, json=carga, timeout=30)
    if r.status_code != 200:
        raise ErrorTerreno(f"HTTP {r.status_code} en {carga.get('type')}")
    return r.json()


def resumen_libro(libro, mid):
    """(horquilla %, profundidad USD en el lado más flojo a ±0,25 %) de una respuesta l2Book."""
    try:
        compras, ventas = libro["levels"]
        mejor_c, mejor_v = float(compras[0]["px"]), float(ventas[0]["px"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None, 0.0
    if not mid:
        return None, 0.0
    lim = VENTANA_PROF_PCT / 100
    prof_c = sum(float(x["px"]) * float(x["sz"]) for x in compras if float(x["px"]) >= mid * (1 - lim))
    prof_v = sum(float(x["px"]) * float(x["sz"]) for x in ventas if float(x["px"]) <= mid * (1 + lim))
    return round((mejor_v - mejor_c) / mid * 100, 4), round(min(prof_c, prof_v), 2)


def emparejar(spot_meta, ctxs, marcas_perp):
    """Pares de contado /USDC cuya base es una moneda con perpetuo (BTC <- UBTC, HYPE <- HYPE...).
    Devuelve {coin: {par, token, ...}} de los candidatos (sin libro todavía)."""
    ctx_por_par = {c["coin"]: c for c in ctxs if isinstance(c, dict) and "coin" in c}        # por NOMBRE, nunca por posición
    tokens = {t["index"]: t for t in spot_meta["tokens"]}
    out = {}
    for par in spot_meta["universe"]:
        base_i, quote_i = par["tokens"]
        c = ctx_por_par.get(par["name"])
        if quote_i != 0 or not c:                 # solo contra USDC
            continue
        nombre = tokens[base_i]["name"]
        coin = nombre if nombre in marcas_perp else (nombre[1:] if nombre.startswith("U") and nombre[1:] in marcas_perp else None)
        mid = float(c.get("midPx") or 0)
        if not coin or not mid:
            continue
        out.setdefault(coin, []).append({"par": par["name"], "token": nombre, "sz_decimals": tokens[base_i]["szDecimals"],
                                         "mid": mid, "vol_24h_usd": round(float(c.get("dayNtlVlm") or 0), 2)})
    # Si una moneda tiene varios pares (token y derivados), se queda el más líquido.
    return {coin: max(v, key=lambda x: x["vol_24h_usd"]) for coin, v in out.items()}


def evaluar(candidatos, marcas_perp, libros):
    """Aplica los criterios. Devuelve {"aptas": {coin: datos}, "excluidas": {coin: motivo}}."""
    aptas, excluidas = {}, {}
    for coin, c in sorted(candidatos.items()):
        base = (c["mid"] / marcas_perp[coin] - 1) * 100
        horquilla, prof = resumen_libro(libros.get(c["par"]) or {}, c["mid"])
        fila = dict(c, perp_mark=marcas_perp[coin], base_pct=round(base, 4), horquilla_pct=horquilla, profundidad_usd=prof)
        motivos = []
        if abs(base) > BASE_MAX_PCT:
            motivos.append(f"base {base:+.2f} % (máx. {BASE_MAX_PCT} %)")
        if c["vol_24h_usd"] < VOL_MIN_USD:
            motivos.append(f"volumen {c['vol_24h_usd']:,.0f} $ < {VOL_MIN_USD:,} $")
        if horquilla is None or horquilla > SPREAD_MAX_PCT:
            motivos.append(f"horquilla {horquilla} % (máx. {SPREAD_MAX_PCT} %)")
        if prof < PROF_MIN_USD:
            motivos.append(f"profundidad {prof:,.0f} $ < {PROF_MIN_USD:,} $")
        if motivos:
            excluidas[coin] = "; ".join(motivos)
        else:
            aptas[coin] = fila
    return {"aptas": aptas, "excluidas": excluidas}


def generar(post=requests.post, ahora=None):
    sm, ctxs = _info({"type": "spotMetaAndAssetCtxs"}, post)
    meta, pctx = _info({"type": "metaAndAssetCtxs"}, post)
    marcas = {m["name"]: float(c["markPx"]) for m, c in zip(meta["universe"], pctx)}     # aquí SÍ van alineadas con meta
    candidatos = emparejar(sm, ctxs, marcas)
    # Solo se pide el libro de los que pasan lo barato (volumen y base): evita ~decenas de llamadas inútiles.
    previos = {k: v for k, v in candidatos.items()
               if v["vol_24h_usd"] >= VOL_MIN_USD and abs((v["mid"] / marcas[k] - 1) * 100) <= BASE_MAX_PCT}
    libros = {}
    for coin, c in previos.items():
        libros[c["par"]] = _info({"type": "l2Book", "coin": c["par"]}, post)
        time.sleep(0.2)
    res = evaluar(candidatos, marcas, libros)
    return {"generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ahora or time.time())),
            "criterios": {"base_max_pct": BASE_MAX_PCT, "vol_min_usd": VOL_MIN_USD, "spread_max_pct": SPREAD_MAX_PCT,
                          "prof_min_usd": PROF_MIN_USD, "ventana_prof_pct": VENTANA_PROF_PCT},
            "monedas_aptas": sorted(res["aptas"]), "aptas": res["aptas"], "excluidas": res["excluidas"]}


def cargar(ruta=RUTA_SALIDA):
    """Monedas aptas guardadas por la última verificación ({} si no hay archivo)."""
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh).get("aptas") or {}
    except (OSError, ValueError):
        return {}


def guardar(datos, ruta=RUTA_SALIDA):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    reemplazar(tmp, ruta)


def main():
    datos = generar()
    guardar(datos)
    print(f"Contado verificado en Hyperliquid: {', '.join(datos['monedas_aptas']) or 'ninguna'}")
    for coin, motivo in datos["excluidas"].items():
        print(f"  excluida {coin}: {motivo}")
    print(f"Guardado en {RUTA_SALIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

