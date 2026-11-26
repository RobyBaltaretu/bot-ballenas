"""Cuenta agresiva: reglas de entrada, plan de la señal, tamaño, liquidación y recorrido de una vela. Funciones puras
(sin red ni disco), las mismas en vivo (motor.py, velas de 1 min) y en la prueba con historia (historia.py, velas de
15 min): así lo que se mide atrás es lo mismo que se opera delante.

Estilo de las señales (como los canales que publican «entrada, stop, objetivos 1–5, apalancamiento»):
  - una regla de entrada da dirección al cierre de una vela de 15 min;
  - el stop va a stop_atr × ATR(14) del precio de entrada, recortado entre stop_min_pct y stop_max_pct;
  - cinco objetivos a 0,5 / 1 / 1,5 / 2 / 3 veces la distancia del stop; en cada uno se cierra un 20 % y al tocar el
    primero el stop pasa al precio de entrada;
  - cierre por tiempo a las horas_max horas.

Dos «piernas» por señal, con la misma entrada, stop y objetivos (cada una se abre aunque la otra no pueda):
  - agresiva (desde el 25/11/2026, tras la auditoría): RIESGO FIJO de riesgo_pct % de la cuenta hasta el stop; el
    apalancamiento pedido (recortado al máximo de la moneda y a sus tramos) solo decide cuánto margen aislado se
    inmoviliza, con un tope de margen_max_pct % por operación y margen_total_max_pct % en total. Antes el margen era fijo
    y, con monedas de 3–10×, arriesgaba menos que la gemela. Si el precio llega antes a la liquidación que al stop, se
    liquida como en Hyperliquid (ver liquidación).
  - gemela: tamaño normal del bot (riesgo gemela_riesgo_pct % hasta el stop, apalancamiento ≤ gemela_apal_max). Sirve
    para separar si las señales ganan algo de lo que pone o quita el apalancamiento.

Como en Hyperliquid: ninguna orden por debajo de min_orden_usd (10 $); los cierres parciales se redondean a los
decimales de la moneda y, si un 20 % no llega a 10 $, se junta con el objetivo siguiente.

Liquidación (margen aislado, documentación de Hyperliquid): al llegar al precio de liquidación se cierra todo contra el
libro y el usuario CONSERVA el margen que sobre. Solo si el precio salta tanto que el valor de la posición queda por
debajo de 2/3 del margen de mantenimiento (rescate del exchange) se pierde todo el margen. El funding entra y sale del
margen aislado de la pierna y mueve el precio de liquidación.

Recorrido de una vela (sin ver ticks): alcista o→l→h→c, bajista o→h→l→c. Un stop se activa al tocarlo y se llena
peor (deslizamiento); un objetivo solo se llena si el precio lo cruza (no basta tocarlo) y siempre a su precio (es una
orden límite en reposo: si la vela ya abre más allá, se llenó al cruzarlo); si la vela ya abre más allá del stop, se
llena al precio de apertura. Es una aproximación: con velas de 1 min (en vivo) apenas importa; con velas de 15 min
(historia) solo el 0,16 % de las velas toca stop y objetivo a la vez (auditoría del 25/11/2026).

Stops y liquidación se disparan en Hyperliquid con el PRECIO DE MARCA (mediana de oráculo, libro y otros exchanges),
no con la última operación: en vivo el motor combina la vela de 1 min de Hyperliquid con la de Binance (vela_disparo) y
solo da por tocado un nivel si lo tocan las dos.
"""

import math

QUINCE_MIN_MS = 900_000
MIN_VELAS = 60

CFG_DEFECTO = {
    "cuenta_inicial_usd": 232.0,
    "riesgo_pct": 5.0,               # agresiva: pérdida hasta el stop (con comisiones), % de la cuenta
    "apalancamiento": 20,            # pedido; se recorta al máximo de cada moneda y a sus tramos (solo decide el margen)
    "margen_max_pct": 30.0,          # margen aislado de una operación como máximo, % de la cuenta
    "max_abiertas": 3,               # señales abiertas a la vez
    "margen_total_max_pct": 90.0,    # margen agresivo comprometido como máximo, % de la cuenta
    "min_orden_usd": 10.0,           # orden mínima de Hyperliquid
    "freno_caida_pct": 50.0,         # perder esto desde el inicio de la etapa: pausa de pausa_freno_h (una vez por etapa)
    "pausa_freno_h": 24,
    "freno_diario_pct": 15.0,        # perder esto en el día (UTC): sin entradas hasta el día siguiente
    "quiebra_pct": 10.0,             # bajar de este % del saldo inicial: quebrada, se cierra todo y se para
    "gemela_riesgo_pct": 2.0,
    "gemela_apal_max": 5,
    "comision_taker_pct": 0.045,
    "comision_maker_pct": 0.015,
    "desliz_pct": 0.05,              # deslizamiento de stops, cierres a mercado y entradas sin libro
    "stop_atr": 1.5,
    "stop_min_pct": 0.8,
    "stop_max_pct": 3.0,
    "objetivos_r": [0.5, 1.0, 1.5, 2.0, 3.0],
    "reparto_objetivos": [0.2, 0.2, 0.2, 0.2, 0.2],
    "horas_max": 48,
    "reglas": ["ruptura_15m", "retroceso_15m", "giro_15m"],
    "universo_n": 25,
    "volumen_min_usd": 20_000_000.0,
}


def cfg(**cambios):
    c = dict(CFG_DEFECTO)
    c.update({k: v for k, v in cambios.items() if k in CFG_DEFECTO})
    if len(c["objetivos_r"]) != len(c["reparto_objetivos"]) or not c["objetivos_r"]:
        raise ValueError("objetivos_r y reparto_objetivos deben tener la misma longitud")
    if abs(sum(c["reparto_objetivos"]) - 1) > 1e-6:
        raise ValueError("reparto_objetivos debe sumar 1")
    if sorted(c["objetivos_r"]) != list(c["objetivos_r"]) or min(c["objetivos_r"]) <= 0:
        raise ValueError("objetivos_r deben ser positivos y crecientes")
    for k in ("riesgo_pct", "margen_max_pct", "margen_total_max_pct", "stop_min_pct", "stop_max_pct", "apalancamiento"):
        if not c[k] > 0:
            raise ValueError(f"{k} debe ser positivo")
    if c["stop_min_pct"] > c["stop_max_pct"]:
        raise ValueError("stop_min_pct > stop_max_pct")
    c["reglas"] = [r for r in c["reglas"] if r in REGLAS]
    return c


# ================================================================ indicadores
def ema(xs, n):
    k, e, out = 2 / (n + 1), None, []
    for x in xs:
        e = x if e is None else e + k * (x - e)
        out.append(e)
    return out


def atr(velas, n=14):
    trs, previo = [], None
    for v in velas:
        trs.append(v["h"] - v["l"] if previo is None else max(v["h"] - v["l"], abs(v["h"] - previo), abs(v["l"] - previo)))
        previo = v["c"]
    out, a = [], 0.0
    for i, tr in enumerate(trs):
        a = (a * i + tr) / (i + 1) if i < n else (a * (n - 1) + tr) / n
        out.append(a)
    return out


def rsi(cierres, n=14):
    out, g, p = [50.0], 0.0, 0.0
    for i in range(1, len(cierres)):
        d = cierres[i] - cierres[i - 1]
        sube, baja = max(d, 0.0), max(-d, 0.0)
        if i <= n:
            g, p = (g * (i - 1) + sube) / i, (p * (i - 1) + baja) / i
        else:
            g, p = (g * (n - 1) + sube) / n, (p * (n - 1) + baja) / n
        out.append(50.0 if g == p == 0 else 100.0 if p == 0 else 100 - 100 / (1 + g / p))
    return out


# ================================================================ reglas de entrada (vela i = la última CERRADA)
def _ruptura(velas, i, cl, e20, e50, a, r):
    """Cierre por encima del máximo (o por debajo del mínimo) de las 20 velas previas, con volumen ≥ 1,5× la media y la
    media de 50 a favor."""
    previas = velas[i - 20:i]
    media_vol = sum(x["v"] for x in previas) / len(previas)
    if media_vol <= 0 or velas[i]["v"] < 1.5 * media_vol:
        return 0
    if cl[i] > max(x["h"] for x in previas) and e50[i] > e50[i - 4]:
        return 1
    if cl[i] < min(x["l"] for x in previas) and e50[i] < e50[i - 4]:
        return -1
    return 0


def _retroceso(velas, i, cl, e20, e50, a, r):
    """Tendencia (media 20 sobre la 50 y la 50 subiendo): la vela baja hasta la media de 20 y cierra por encima, alcista.
    Al revés para cortos."""
    v = velas[i]
    if e20[i] > e50[i] and e50[i] > e50[i - 4] and v["l"] <= e20[i] < cl[i] and cl[i] > v["o"] and cl[i - 1] > e20[i - 1]:
        return 1
    if e20[i] < e50[i] and e50[i] < e50[i - 4] and v["h"] >= e20[i] > cl[i] and cl[i] < v["o"] and cl[i - 1] < e20[i - 1]:
        return -1
    return 0


def _giro(velas, i, cl, e20, e50, a, r):
    """Giro tras exceso: RSI(14) bajo 25 en alguna de las 3 velas previas y ahora de vuelta ≥ 30, con el precio aún a más de
    un ATR por debajo de la media de 50 (largo). Al revés con 75 / 70 para cortos."""
    if min(r[i - 3:i]) < 25 and r[i] >= 30 and cl[i] < e50[i] - a[i]:
        return 1
    if max(r[i - 3:i]) > 75 and r[i] <= 70 and cl[i] > e50[i] + a[i]:
        return -1
    return 0


REGLAS = {"ruptura_15m": _ruptura, "retroceso_15m": _retroceso, "giro_15m": _giro}
NOMBRES = {"ruptura_15m": "Ruptura con volumen", "retroceso_15m": "Retroceso a la media", "giro_15m": "Giro tras exceso"}


def indicadores(velas):
    cl = [v["c"] for v in velas]
    return {"cl": cl, "e20": ema(cl, 20), "e50": ema(cl, 50), "atr": atr(velas, 14), "rsi": rsi(cl, 14)}


def detectar_en(velas, i, ind, c):
    """Señal al cierre de la vela i (todas las velas hasta i, incluida, están cerradas) o None."""
    if i < MIN_VELAS - 1:
        return None
    cl, a = ind["cl"], ind["atr"]
    if a[i] <= 0 or cl[i] <= 0:
        return None
    for regla in c["reglas"]:
        lado = REGLAS[regla](velas, i, cl, ind["e20"], ind["e50"], a, ind["rsi"])
        if lado:
            return {"regla": regla, "lado": lado, "precio": cl[i], "atr": a[i], "t": velas[i]["t"]}
    return None


def detectar(velas, c):
    """velas: lista de velas CERRADAS {t, o, h, l, c, v} en orden. Devuelve la señal de la última vela o None."""
    if len(velas) < MIN_VELAS:
        return None
    return detectar_en(velas, len(velas) - 1, indicadores(velas), c)


# ================================================================ plan, tamaño y liquidación
def plan(lado, entrada, atr_v, c):
    stop_pct = min(max(c["stop_atr"] * atr_v / entrada * 100, c["stop_min_pct"]), c["stop_max_pct"])
    d = entrada * stop_pct / 100
    return {"stop": entrada - lado * d, "stop_pct": round(stop_pct, 4), "objetivos": [entrada + lado * k * d for k in c["objetivos_r"]]}


def bajar(x, decimales):
    f = 10 ** int(decimales)
    return math.floor(x * f + 1e-9) / f


def apal_tramos(apal, apal_max_mercado, tramos, notional):
    """Apalancamiento permitido: el pedido, sin pasar del máximo de la moneda ni del de su tramo de margen."""
    a = min(apal, apal_max_mercado)
    for desde, maximo in tramos or ():
        if notional >= desde:
            a = min(a, maximo)
    return max(1, int(a))


def tamano_agresiva(equity, libre, margen_abierto, px, stop_pct, sz_dec, apal_max_mercado, tramos, c):
    """Riesgo fijo: el tamaño sale de riesgo_pct % de la cuenta hasta el stop (con comisión de ida y vuelta); el
    apalancamiento (pedido, recortado al de la moneda y a sus tramos) solo decide el margen aislado. Si el margen no cabe
    en los topes (por operación y total), se recorta el tamaño: el riesgo real queda por debajo del pedido."""
    riesgo = equity * c["riesgo_pct"] / 100
    if riesgo <= 0 or stop_pct <= 0:
        return {"ok": False, "motivo": "cuenta sin saldo"}
    notional = riesgo / (stop_pct / 100 + 2 * c["comision_taker_pct"] / 100)
    apal = apal_tramos(c["apalancamiento"], apal_max_mercado, tramos, notional)
    tope = min(equity * c["margen_max_pct"] / 100, equity * c["margen_total_max_pct"] / 100 - margen_abierto)
    if tope <= 0:
        return {"ok": False, "motivo": f"margen comprometido al máximo ({c['margen_total_max_pct']:g} % de la cuenta)"}
    recortado = notional / apal > tope + 1e-9
    if recortado:
        notional = tope * apal
    sz = bajar(notional / px, sz_dec)
    notional = sz * px
    if notional < c["min_orden_usd"]:
        return {"ok": False, "motivo": f"orden de menos de {c['min_orden_usd']:g} $ (mínimo de Hyperliquid)"}
    margen_real = notional / apal
    if libre < margen_real + notional * c["comision_taker_pct"] / 100 - 1e-9:
        return {"ok": False, "motivo": "no hay saldo libre para el margen"}
    return {"ok": True, "sz": sz, "apal": apal, "margen_usd": margen_real, "notional_usd": notional, "recortado": recortado,
            "riesgo_pct": notional * (stop_pct / 100 + 2 * c["comision_taker_pct"] / 100) / equity * 100}


def tamano_gemela(equity, libre, px, stop_pct, sz_dec, apal_max_mercado, c):
    riesgo = equity * c["gemela_riesgo_pct"] / 100
    if riesgo <= 0:
        return {"ok": False, "motivo": "cuenta sin saldo"}
    apal = max(1, int(min(c["gemela_apal_max"], apal_max_mercado)))
    notional = riesgo / (stop_pct / 100 + 2 * c["comision_taker_pct"] / 100)
    notional = min(notional, libre * apal * 0.95)
    sz = bajar(notional / px, sz_dec)
    if sz <= 0 or sz * px < c["min_orden_usd"]:
        return {"ok": False, "motivo": f"orden de menos de {c['min_orden_usd']:g} $ (mínimo de Hyperliquid)"}
    return {"ok": True, "sz": sz, "apal": apal, "margen_usd": sz * px / apal, "notional_usd": sz * px}


def mmr_de(apal_max_mercado):
    """Margen de mantenimiento de Hyperliquid: la mitad del margen inicial al apalancamiento MÁXIMO de la moneda."""
    return 1 / (2 * max(apal_max_mercado, 1))


def precio_liquidacion(lado, entrada, apal, apal_max_mercado):
    """Margen aislado con la fórmula de Hyperliquid (la misma que papel.py): mantenimiento = mitad del margen inicial al
    apalancamiento MÁXIMO de la moneda. Estimación: en real manda el liquidationPx del exchange."""
    mmr = mmr_de(apal_max_mercado)
    disponible = 1 / max(apal, 1e-9) - mmr
    if disponible <= 0:
        return entrada
    px = entrada - lado * entrada * disponible / (1 - mmr * lado)
    return px if px > 0 else None


def liquidacion_pierna(p):
    """Precio de liquidación con el margen aislado que la pierna tiene AHORA (cambia con el funding)."""
    if p["sz"] <= 0:
        return p.get("liq")
    mmr, lado, e = p["mmr"], p["lado"], p["entrada"]
    disponible = margen_restante(p) / p["sz"] - e * mmr          # por unidad
    px = e - lado * disponible / (1 - mmr * lado)
    return px if px > 0 else None


def tamanos_objetivos(sz, objetivos, reparto, sz_dec, min_usd):
    """Cantidad que cierra cada objetivo, redondeada a los decimales de la moneda. Un parcial que (o cuyo resto) no llega a
    min_usd se junta con el siguiente; el último cierra lo que quede."""
    n = len(objetivos)
    out, usado, acum = [0.0] * n, 0.0, 0.0
    for k in range(n - 1):
        acum += sz * reparto[k]
        q = bajar(acum, sz_dec) if sz_dec is not None else acum
        resto = sz - usado - q
        if q > 0 and q * objetivos[k] >= min_usd - 1e-9 and resto * objetivos[k] >= min_usd - 1e-9:
            out[k] = q
            usado += q
            acum -= q
    out[-1] = round(sz - usado, int(sz_dec)) if sz_dec is not None else sz - usado
    return out


def vela_disparo(v, ref, lado):
    """Vela con la que se disparan stop y liquidación: Hyperliquid usa el precio de MARCA (mediana de oráculo, libro y
    precios de otros exchanges), así que una mecha que solo se imprime en su libro no lo mueve. Aproximación: el extremo
    en contra es el MENOS extremo de la vela de Hyperliquid (v) y la de Binance del mismo minuto (ref). Los objetivos son
    órdenes límite en el libro de Hyperliquid: el lado a favor no cambia. Sin ref, la vela de Hyperliquid tal cual."""
    if not ref:
        return v
    w = dict(v)
    if lado > 0:
        w["l"] = min(max(v["l"], ref["l"]), v["o"], v["c"])
    else:
        w["h"] = max(min(v["h"], ref["h"]), v["o"], v["c"])
    return w


# ================================================================ piernas
def nueva_pierna(tipo, lado, entrada, sz, apal, apal_max_mercado, pl, comision_usd, t_ms, equity_entrada, sz_dec=None,
                 min_usd=0.0, reparto=None):
    """sz_dec: decimales de la moneda; si se da, cada objetivo cierra una cantidad redondeada (tamanos_objetivos)."""
    p = {"tipo": tipo, "lado": lado, "entrada": entrada, "sz0": sz, "sz": sz, "apal": apal,
         "margen0": sz * entrada / apal, "margen_extra": 0.0, "mmr": mmr_de(apal_max_mercado),
         "liq": precio_liquidacion(lado, entrada, apal, apal_max_mercado),
         "stop": pl["stop"], "stop0": pl["stop"], "objetivos": list(pl["objetivos"]), "toc": 0,
         "pnl_usd": -comision_usd, "comisiones_usd": comision_usd, "funding_usd": 0.0,
         "abierta_ms": int(t_ms), "cerrada_ms": None, "salida": None, "salida_px": None,
         "equity_entrada": equity_entrada}
    if sz_dec is not None:
        n = len(pl["objetivos"])
        p["tamanos"] = tamanos_objetivos(sz, pl["objetivos"], reparto or [1 / n] * n, sz_dec, min_usd)
    return p


def riesgo_inicial(p):
    return p["sz0"] * abs(p["entrada"] - p["stop0"])


def resultado_r(p):
    r0 = riesgo_inicial(p)
    return p["pnl_usd"] / r0 if r0 > 0 else 0.0


def margen_restante(p):
    """Margen aislado que queda en la pierna: la parte del inicial de lo que sigue abierto más el funding acumulado."""
    if not p["sz0"] or p["sz"] <= 0:
        return 0.0
    return p["margen0"] * p["sz"] / p["sz0"] + p.get("margen_extra", 0.0)


def valor_en_cuenta(p, marca):
    """Lo que la pierna abierta suma a la cuenta: su margen más el resultado no realizado (nunca menos de 0: margen aislado)."""
    if p["sz"] <= 0:
        return 0.0
    return max(0.0, margen_restante(p) + p["lado"] * (marca - p["entrada"]) * p["sz"])


def _cerrar_parte(p, q, px, comision_pct, t_ms, motivo):
    q = min(q, p["sz"])
    todo = p["sz"] - q <= p["sz0"] * 1e-9
    pnl = p["lado"] * (px - p["entrada"]) * q
    com = q * px * comision_pct / 100
    extra = p.get("margen_extra", 0.0)
    extra_q = extra if todo else extra * q / p["sz"]
    liberado = p["margen0"] * q / p["sz0"] + extra_q
    if liberado + pnl - com < 0:                       # margen aislado: nunca se pierde más que el margen de la pierna
        pnl = com - liberado
    p["margen_extra"] = extra - extra_q
    p["sz"] = 0.0 if todo else p["sz"] - q
    p["pnl_usd"] += pnl - com
    p["comisiones_usd"] += com
    ev = {"tipo": motivo, "px": px, "sz": q, "pnl_usd": pnl - com, "t": int(t_ms)}
    if p["sz"] == 0:
        p["cerrada_ms"], p["salida"], p["salida_px"] = int(t_ms), motivo, px
    return liberado + pnl - com, ev


def _rescate(p, t_ms, px):
    """Liquidación de rescate (el precio saltó tanto que la posición vale menos de 2/3 del mantenimiento): se pierde todo
    el margen aislado de la pierna."""
    perdido = margen_restante(p)
    q = p["sz"]
    p["pnl_usd"] -= perdido
    p["sz"], p["margen_extra"] = 0.0, 0.0
    p["cerrada_ms"], p["salida"], p["salida_px"] = int(t_ms), "liquidacion", px
    return 0.0, {"tipo": "liquidacion", "px": px, "sz": q, "pnl_usd": -perdido, "t": int(t_ms), "rescate": True}


def _liquidar(p, px, c, t_ms):
    """Liquidación por el libro (lo normal en Hyperliquid): se cierra todo a mercado al precio px con deslizamiento y
    comisión de tomador, y el usuario CONSERVA el margen que sobre. Si en px la posición ya vale menos de 2/3 del margen de
    mantenimiento (hueco grande), es un rescate y se pierde todo el margen."""
    valor = margen_restante(p) + p["lado"] * (px - p["entrada"]) * p["sz"]
    if valor < 2 / 3 * p.get("mmr", 0.0) * p["sz"] * px:
        return _rescate(p, t_ms, px)
    return _cerrar_parte(p, p["sz"], px * (1 - p["lado"] * c["desliz_pct"] / 100), c["comision_taker_pct"], t_ms, "liquidacion")


def cerrar_mercado(p, px, c, t_ms, motivo):
    """Cierre de todo lo que queda a mercado (tiempo, quiebra, reinicio): taker y deslizamiento en contra."""
    if p["sz"] <= 0:
        return 0.0, None
    return _cerrar_parte(p, p["sz"], px * (1 - p["lado"] * c["desliz_pct"] / 100), c["comision_taker_pct"], t_ms, motivo)


def _objetivo(p, c, t, eventos):
    """Llena el siguiente objetivo a SU precio (orden límite en reposo, comisión de creador). Devuelve el saldo liberado."""
    k = p["toc"]
    ultimo = k == len(p["objetivos"]) - 1
    if ultimo:
        q = p["sz"]
    elif p.get("tamanos"):
        q = min(p["sz"], p["tamanos"][k])
    else:                                                          # piernas abiertas antes del 25/11/2026
        q = min(p["sz"], p["sz0"] * c["reparto_objetivos"][k])
    d = 0.0
    if q > 0:
        d, ev = _cerrar_parte(p, q, p["objetivos"][k], c["comision_maker_pct"], t, f"objetivo_{k + 1}")
        ev["objetivo"] = k + 1
        eventos.append(ev)
    p["toc"] = k + 1
    if k == 0 and p["sz"] > 0:
        p["stop"] = p["entrada"]                                   # al tocar el objetivo 1 el stop pasa a la entrada
    return d


def avanzar(p, vela, c):
    """Pasa una vela {t, o, h, l, c} por la pierna. Devuelve (cambio del saldo libre, [eventos]). El cambio del saldo es lo
    que vuelve a la cuenta: margen liberado + resultado − comisiones (un rescate no devuelve nada)."""
    if p["sz"] <= 0:
        return 0.0, []
    lado, entrada = p["lado"], p["entrada"]
    t = vela["t"]
    f = lambda px: lado * (px - entrada)                           # beneficio por unidad: >0 a favor
    camino = [vela["o"], vela["l"], vela["h"], vela["c"]] if vela["c"] >= vela["o"] else [vela["o"], vela["h"], vela["l"], vela["c"]]
    delta, eventos = 0.0, []

    def adverso(desde_px, hasta_px, hueco):
        """El precio va en contra de desde_px a hasta_px: el primer nivel que toca (stop o liquidación) cierra todo."""
        niveles = [("stop", p["stop"])]
        if p["liq"] is not None:
            niveles.append(("liquidacion", p["liq"]))
        tocados = [(n, px) for n, px in niveles if f(hasta_px) <= f(px) and (hueco or f(px) < f(desde_px) + 1e-15)]
        if not tocados:
            return None
        nombre, nivel = max(tocados, key=lambda x: f(x[1]))         # el más cercano al precio de partida
        if nombre == "liquidacion" or (hueco and any(n == "liquidacion" for n, _ in tocados)):
            return _liquidar(p, desde_px if hueco else p["liq"], c, t)
        px = desde_px if hueco else nivel                             # vela que abre más allá del stop: se llena a la apertura
        motivo = "stop_entrada" if p["toc"] > 0 and abs(p["stop"] - entrada) < 1e-12 else "stop"
        return _cerrar_parte(p, p["sz"], px * (1 - lado * c["desliz_pct"] / 100), c["comision_taker_pct"], t, motivo)

    # apertura de la vela: ¿ya está más allá del stop o de la liquidación?
    r = adverso(camino[0], camino[0], True)
    if r:
        return r[0], [r[1]]
    # ¿o ya más allá de algún objetivo? Las órdenes límite en reposo se llenaron al cruzarlas, a su precio.
    while p["sz"] > 0 and p["toc"] < len(p["objetivos"]) and f(camino[0]) > f(p["objetivos"][p["toc"]]):
        delta += _objetivo(p, c, t, eventos)
    for a, b in zip(camino, camino[1:]):
        if p["sz"] <= 0:
            break
        if f(b) < f(a):
            r = adverso(a, b, False)
            if r:
                delta += r[0]
                eventos.append(r[1])
        elif f(b) > f(a):
            while p["sz"] > 0 and p["toc"] < len(p["objetivos"]) and f(a) < f(p["objetivos"][p["toc"]]) < f(b):
                delta += _objetivo(p, c, t, eventos)
    return delta, eventos


def aplicar_funding(p, marca, tasa):
    """Un pago de funding: un largo paga con tasa positiva y cobra con negativa; un corto, al revés. Entra o sale del
    margen aislado de la pierna (como en Hyperliquid), así que mueve su precio de liquidación."""
    if p["sz"] <= 0:
        return 0.0
    pago = -p["lado"] * p["sz"] * marca * tasa
    p["margen_extra"] = p.get("margen_extra", 0.0) + pago
    p["funding_usd"] += pago
    p["pnl_usd"] += pago
    if "mmr" in p:
        p["liq"] = liquidacion_pierna(p)
    return pago
