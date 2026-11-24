"""Cartera del factor de funding (estudio B de la auditoría del 13/11/2026). SOLO SIMULADO.

Idea: cada semana, largo en las monedas con el funding medio más bajo y corto en las que lo tienen más alto, con
el mismo número de patas a cada lado. No predice la dirección del mercado: apuesta a que la diferencia de funding
entre monedas se cobra y a que el exceso de apalancamiento de un lado se corrige.

Aquí solo hay funciones puras (sin red, sin estado, sin órdenes). El bot (`bot.py`) las usa para proponer las patas
como candidatas normales: pasan por los mismos filtros de ejecución, los mismos límites de riesgo y la cuenta
simulada (`papel.py`). En shadow y en real este módulo no propone nada, y aunque lo hiciera no hay promoción
posible para «cartera_funding_4h» (no es una estrategia del laboratorio).

DIFERENCIAS CON EL ESTUDIO (no ocultarlas: lo que opera aquí NO es exactamente lo que se midió):
  - funding de Hyperliquid (el estudio usó el de Binance);
  - universo por volumen de 24 h (el estudio, por volumen medio de 30 días);
  - como mucho `max_por_lado` patas por lado (el estudio operaba un tercio entero del universo);
  - cada pata lleva stop (múltiplo de su volatilidad diaria) porque el gestor no abre sin stop; el estudio no tenía;
  - el tamaño sale del riesgo por pata y del stop (≈ inverso a la volatilidad, como en el estudio).
Nada de esto está validado como rentable: se marca «explorando» y no cuenta como evidencia de ventaja.
"""

import math
from datetime import datetime, timedelta, timezone

VERSION = 1
CLAVE = "cartera_funding_4h"
MODULO = "cartera_funding"
INTERVALO = "4h"
VENTANA_SENAL_H = 7 * 24          # funding medio de los últimos 7 días (como el estudio)
MIN_REGISTROS_FUNDING = 120       # de las 168 horas de la ventana: con menos, la moneda no entra
BARRAS_VOL = 180                  # 30 días de velas de 4 h para la volatilidad
BARRAS_DIA = 6
MIN_UNIVERSO = 9                  # con menos monedas con datos no hay terciles que valgan
GRACIA_CIERRE_MIN = 60            # las patas duran hasta el siguiente rebalanceo y un poco más (para renovarlas)
# Sin objetivos ni stop dinámico: la pata se mantiene hasta el rebalanceo (o hasta su stop de protección).
SALIDA = {"parcial_activo": False, "tp1_r": 98, "tp_final_r": 99, "trailing_r": 99, "breakeven_tras_r": 99,
          "sin_objetivo": True}


def inicio_semana(ts):
    """Instante (epoch, s) del lunes 00:00 UTC de la semana de 'ts'."""
    d = datetime.fromtimestamp(ts, timezone.utc)
    lunes = (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return lunes.timestamp()


def toca_rebalanceo(ahora, semana_hecha, retraso_max_h):
    """Devuelve el inicio de la semana si toca rebalancear ahora, o None.
    Solo se rebalancea en las primeras 'retraso_max_h' horas tras el lunes 00:00 UTC: si el bot estuvo parado y se
    pasó la ventana, esa semana no se entra tarde (no sería la regla estudiada)."""
    semana = inicio_semana(ahora)
    if semana_hecha is not None and semana_hecha >= semana:
        return None
    if ahora - semana > retraso_max_h * 3600:
        return None
    return semana


def vol_diaria_pct(cierres):
    """Volatilidad diaria (%) con los rendimientos logarítmicos de las últimas BARRAS_VOL velas de 4 h."""
    c = [x for x in cierres[-(BARRAS_VOL + 1):] if x and x > 0]
    if len(c) < BARRAS_VOL // 2:
        return None
    r = [math.log(c[k] / c[k - 1]) for k in range(1, len(c))]
    media = sum(r) / len(r)
    var = sum((x - media) ** 2 for x in r) / (len(r) - 1)
    return math.sqrt(var * BARRAS_DIA) * 100


def fila(moneda, volumen, serie_funding, cierres, ahora):
    """Datos de una moneda para la selección, o None si le falta historia (funding de la ventana o velas)."""
    import bisect
    if serie_funding is None:
        return None
    n = bisect.bisect_right(serie_funding.t, ahora) - bisect.bisect_right(serie_funding.t, ahora - VENTANA_SENAL_H * 3600)
    if n < MIN_REGISTROS_FUNDING:
        return None
    f = serie_funding.media(ahora, VENTANA_SENAL_H)
    vol = vol_diaria_pct(cierres)
    if f is None or not vol:
        return None
    return {"moneda": moneda, "volumen": float(volumen or 0), "funding": f, "vol": vol}


def seleccionar(filas, max_por_lado, universo_max=30):
    """(largos, cortos, n): del universo (las 'universo_max' de más volumen), el tercio de funding más bajo es
    candidato a largo y el más alto a corto; de cada tercio se toman las 'max_por_lado' más extremas.
    Las listas van de la más extrema a la menos."""
    universo = sorted(filas, key=lambda x: -x["volumen"])[:universo_max]
    n = len(universo)
    k = n // 3
    if n < MIN_UNIVERSO or k < 1 or max_por_lado < 1:
        return [], [], n
    orden = sorted(universo, key=lambda x: (x["funding"], x["moneda"]))
    por_lado = min(max_por_lado, k)
    return orden[:por_lado], orden[::-1][:por_lado], n


def stop_pct(vol, multiplo, sl_min, sl_max):
    """Stop de protección: 'multiplo' volatilidades diarias, dentro de los límites de stop del bot."""
    return round(max(sl_min, min(sl_max, vol * multiplo)), 3)


def patas_nuevas(mantenidas_l, mantenidas_s, objetivo_por_lado, libres_l, libres_s, libres_total, libres_riesgo):
    """Cuántas patas NUEVAS caben por lado (nl, ns) dejando el mismo número de largos que de cortos en la cartera.
    Las dos patas o ninguna: si no hay hueco para igualar los lados, no se abre nada nuevo.
    libres_l/libres_s: huecos del límite «mismo lado»; libres_total: huecos de posiciones; libres_riesgo: cuántas
    patas caben en el riesgo abierto que queda."""
    for p in range(objetivo_por_lado, max(mantenidas_l, mantenidas_s) - 1, -1):
        nl, ns = p - mantenidas_l, p - mantenidas_s
        if nl < 0 or ns < 0:
            continue
        if nl <= libres_l and ns <= libres_s and nl + ns <= min(libres_total, libres_riesgo):
            return nl, ns
    return 0, 0


def equilibrar(aprobadas_l, aprobadas_s, mantenidas_l, mantenidas_s):
    """Tras los filtros de ejecución puede haber caído una pata: devuelve cuántas aprobadas se conservan por lado
    para que largos y cortos queden iguales (se descartan las menos extremas del lado que sobra)."""
    total = min(mantenidas_l + aprobadas_l, mantenidas_s + aprobadas_s)
    return max(0, total - mantenidas_l), max(0, total - mantenidas_s)
