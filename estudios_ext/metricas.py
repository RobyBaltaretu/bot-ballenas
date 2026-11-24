"""Métricas de una cartera diaria (solo estadística, sin datos de mercado) más Sharpe deflactado y PBO por CSCV.

Los retornos son FRACCIONES DIARIAS del capital (0,01 = +1 %). Se anualiza con 365 días: el mercado no cierra."""

import itertools
import math
from statistics import NormalDist

ANIO = 365.0
_N = NormalDist()


def media_desv(xs):
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def sharpe(xs):
    m, s = media_desv(xs)
    return m / s * math.sqrt(ANIO) if s > 0 else 0.0


def t_dias(xs):
    """Estadístico t de la media diaria (ya es «t por días»: cada día cuenta una vez)."""
    m, s = media_desv(xs)
    return m / (s / math.sqrt(len(xs))) if s > 0 and len(xs) > 1 else 0.0


def caida_max(xs):
    """Peor caída desde un máximo, como fracción positiva del capital (curva compuesta)."""
    eq = pico = 1.0
    peor = 0.0
    for r in xs:
        eq *= 1 + r
        pico = max(pico, eq)
        peor = max(peor, 1 - eq / pico)
    return peor


def cagr(xs):
    if not xs:
        return 0.0
    eq = 1.0
    for r in xs:
        eq *= 1 + r
    if eq <= 0:
        return -1.0
    return eq ** (ANIO / len(xs)) - 1


def resumen(xs):
    m, s = media_desv(xs)
    return {"dias": len(xs), "sharpe": round(sharpe(xs), 3), "cagr_pct": round(cagr(xs) * 100, 2),
            "volatilidad_anual_pct": round(s * math.sqrt(ANIO) * 100, 2), "caida_max_pct": round(caida_max(xs) * 100, 2),
            "t_dias": round(t_dias(xs), 2), "media_diaria_pct": round(m * 100, 4)}


def por_anio(dias, xs, dia_a_anio):
    """{año: resumen} con los días agrupados por año natural UTC. `dia_a_anio(dia)` -> int."""
    g = {}
    for d, r in zip(dias, xs):
        g.setdefault(dia_a_anio(d), []).append(r)
    return {a: resumen(v) for a, v in sorted(g.items())}


def asimetria_curtosis(xs):
    n = len(xs)
    m, s = media_desv(xs)
    if n < 4 or s == 0:
        return 0.0, 3.0
    z = [(x - m) / s for x in xs]
    return sum(v ** 3 for v in z) / n, sum(v ** 4 for v in z) / n


def sharpe_deflactado(xs, n_pruebas=1):
    """Probabilidad de que el Sharpe verdadero supere el que cabría esperar por azar tras `n_pruebas` intentos
    (Bailey y López de Prado). Con n_pruebas=1 es la probabilidad de que el Sharpe sea > 0. Entre 0 y 1; > 0,95 es sólido."""
    n = len(xs)
    if n < 30:
        return 0.0
    m, s = media_desv(xs)
    if s == 0:
        return 0.0
    sr = m / s                                   # Sharpe diario (sin anualizar)
    asim, curt = asimetria_curtosis(xs)
    var_sr = max(1e-12, (1 - asim * sr + (curt - 1) / 4 * sr * sr) / (n - 1))
    sr0 = 0.0
    if n_pruebas > 1:
        g = 0.5772156649
        sr0 = math.sqrt(var_sr) * ((1 - g) * _N.inv_cdf(1 - 1 / n_pruebas) + g * _N.inv_cdf(1 - 1 / (n_pruebas * math.e)))
    return _N.cdf((sr - sr0) / math.sqrt(var_sr))


def pbo_cscv(series, bloques=8):
    """Probabilidad de sobreajuste por selección (CSCV). `series`: {configuración: [retornos diarios]} de IGUAL longitud.
    Para cada reparto de los bloques en mitad entrenamiento / mitad prueba se elige la mejor configuración del
    entrenamiento y se mira su puesto en la prueba. PBO = parte de repartos donde queda por debajo de la mediana.
    Devuelve None si hay menos de 2 configuraciones o pocos datos."""
    nombres = list(series)
    if len(nombres) < 2:
        return None
    T = min(len(v) for v in series.values())
    tam = T // bloques
    if tam < 20:
        return None
    est = {}
    for k in nombres:
        v = series[k][-tam * bloques:]
        est[k] = [(tam, sum(v[b * tam:(b + 1) * tam]), sum(x * x for x in v[b * tam:(b + 1) * tam])) for b in range(bloques)]

    def sr_de(k, idx):
        n = sum(est[k][b][0] for b in idx)
        s1 = sum(est[k][b][1] for b in idx)
        s2 = sum(est[k][b][2] for b in idx)
        m = s1 / n
        var = max(0.0, (s2 - n * m * m) / (n - 1))
        return m / math.sqrt(var) if var > 0 else 0.0

    logits, peor = [], 0
    for ent in itertools.combinations(range(bloques), bloques // 2):
        pru = [b for b in range(bloques) if b not in ent]
        mejor = max(nombres, key=lambda k: sr_de(k, ent))
        srs = sorted(sr_de(k, pru) for k in nombres)
        rango = (srs.index(sr_de(mejor, pru)) + 1) / (len(nombres) + 1)
        logits.append(math.log(rango / (1 - rango)))
        peor += rango <= 0.5
    return {"pbo": round(peor / len(logits), 3), "repartos": len(logits), "configuraciones": len(nombres),
            "logit_medio": round(sum(logits) / len(logits), 3)}


def escalar_a_volatilidad(xs, vol_anual_objetivo, vol_anual_actual):
    """Escala una serie para igualar la volatilidad anual de otra (comparar 'mantener BTC con la misma volatilidad')."""
    f = vol_anual_objetivo / vol_anual_actual if vol_anual_actual > 0 else 0.0
    return [x * f for x in xs]
