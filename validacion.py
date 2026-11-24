"""
Herramientas de validación del laboratorio (funciones puras, sin red, probadas en tests/).

Objetivo: que un resultado del laboratorio sea difícil de engañar.
  - Sin fugas: los parámetros se eligen solo con datos ANTERIORES al tramo que se evalúa, y se PURGAN las
    operaciones de entrenamiento que seguían abiertas cuando empieza el tramo de prueba (más un EMBARGO).
  - Walk-forward: varios tramos de prueba consecutivos, cada uno con parámetros elegidos antes.
  - Holdout final: el último tramo no se usa para nada hasta el final y se cuenta cuántas veces se ha mirado.
  - Pruebas múltiples: el umbral de t es el valor crítico de una t de Student de UNA cola con n−1 grados de
    libertad al nivel α/k (Bonferroni), donde k es el número EFECTIVO de variantes probadas desde siempre
    (laboratorio + investigación, registro en laboratorio_variantes.json), no solo las de esta ejecución.
  - Purga en TODAS las particiones: una operación solo cuenta en un tramo si abre Y cierra dentro de él (con un
    embargo antes del final): ningún resultado usa precios de la partición siguiente (ni del holdout).
  - Holdout de UN SOLO USO por experimento: laboratorio_holdout.json guarda hasta dónde se ha mirado ya. Solo
    los datos posteriores cuentan como confirmación independiente; si no hay bastantes, el resultado se degrada
    a 'exploratorio' (nunca 'supera').
  - Muestra insuficiente, línea base vacía o insuficiente, holdout corto o datos que faltan -> 'no_evaluable'.
  - Bootstrap por bloques: intervalo de confianza de la media respetando que las operaciones seguidas se parecen.
  - Líneas base: entrada aleatoria con la misma gestión y "siempre largo".
  - Estrés de costes en ESCENARIOS explícitos y reproducibles (costes ×2, deslizamiento ×3, huecos en stops,
    combinado), no un multiplicador opaco.
  - Universo en el momento: solo cuentan operaciones en monedas que ERAN líquidas entonces.
  - Meseta de parámetros (17/11/2026, idea de tick-stock-panel): los parámetros elegidos no pueden ser un PICO
    aislado; sus vecinos en la rejilla (un parámetro movido un paso) deben rendir parecido fuera de muestra.

Nada de aquí autoriza dinero real: el resultado es evidencia para promocion.py.
"""

import hashlib
import json
import math
import random
from statistics import NormalDist


# ============================================================ particiones
def particionar(t0, t1, pliegues=5, fraccion_holdout=0.15, fraccion_inicial=0.4):
    """Tramos walk-forward sobre [t0, t1).
    - holdout: el último 'fraccion_holdout' del periodo.
    - Antes del holdout: un primer bloque solo de entrenamiento ('fraccion_inicial') y luego 'pliegues' tramos
      de prueba consecutivos. Cada tramo se entrena con TODO lo anterior (ventana creciente).
    Devuelve {"pliegues": [(inicio_prueba, fin_prueba)], "holdout": (inicio, fin)}."""
    if not t1 > t0 or pliegues < 1 or not 0 < fraccion_holdout < 0.5:
        raise ValueError("partición imposible")
    inicio_holdout = t1 - (t1 - t0) * fraccion_holdout
    inicio_pruebas = t0 + (inicio_holdout - t0) * fraccion_inicial
    paso = (inicio_holdout - inicio_pruebas) / pliegues
    tramos = [(inicio_pruebas + k * paso, inicio_pruebas + (k + 1) * paso) for k in range(pliegues)]
    return {"pliegues": tramos, "holdout": (inicio_holdout, t1)}


def entrenamiento_purgado(trades, inicio_prueba, embargo_seg):
    """Operaciones utilizables para elegir parámetros antes de 'inicio_prueba': abrieron antes y ya estaban
    CERRADAS (con margen de embargo) cuando empieza la prueba. Así ninguna mira datos del tramo de prueba."""
    limite = inicio_prueba - embargo_seg
    return [t for t in trades if t["t"] < limite and t.get("cierre_ts", t["t"]) <= limite]


def en_tramo_purgado(trades, inicio, fin, embargo_seg=0):
    """Operaciones que ABREN en [inicio, fin) y CIERRAN antes de fin − embargo. Una operación que cruza el
    límite usaría precios de la partición siguiente: se purga (no se cuenta en ninguna de las dos)."""
    limite = fin - embargo_seg
    return [t for t in trades if inicio <= t["t"] < fin and t.get("cierre_ts", t["t"]) <= limite]


# ============================================================ estadística
def media(xs):
    return sum(xs) / len(xs) if xs else None


def estadistico_t(xs):
    if len(xs) < 2:
        return 0.0
    m = media(xs)
    d = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    return m / (d / math.sqrt(len(xs))) if d else 0.0


def _beta_incompleta(a, b, x):
    """Beta incompleta regularizada I_x(a, b) (fracción continua de Lentz; Numerical Recipes)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _beta_incompleta(b, a, 1 - x)
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    f = d
    for m in range(1, 400):
        m2 = 2 * m
        num = m * (b - m) * x / ((a + m2 - 1) * (a + m2))
        d = 1.0 + num * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + num / c if abs(c) > tiny else tiny
        f *= d * c
        num = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1))
        d = 1.0 + num * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + num / c if abs(c) > tiny else tiny
        delta = d * c
        f *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return math.exp(ln_beta) * f / a


def t_cdf(t, gl):
    """Función de distribución de una t de Student con 'gl' grados de libertad."""
    x = gl / (gl + t * t)
    p = 0.5 * _beta_incompleta(gl / 2, 0.5, x)
    return 1 - p if t > 0 else p


def t_critico(gl, alfa_una_cola):
    """Valor t tal que P(T > t) = alfa (una cola). gl infinito o enorme -> normal."""
    if gl is None or gl > 1e6:
        return NormalDist().inv_cdf(1 - alfa_una_cola)
    gl = max(1, int(gl))
    lo, hi = 0.0, 1.0
    while 1 - t_cdf(hi, gl) > alfa_una_cola and hi < 1e7:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if 1 - t_cdf(mid, gl) > alfa_una_cola:
            lo = mid
        else:
            hi = mid
    return hi


def t_requerido(n_variantes, alfa=0.05, n_ops=None):
    """Umbral de t de UNA cola: Student-t con n_ops − 1 grados de libertad al nivel alfa / n_variantes
    (Bonferroni). Sin n_ops se usa la normal (equivale a muestra muy grande; menos exigente)."""
    n = max(1, int(n_variantes))
    gl = (n_ops - 1) if n_ops and n_ops > 1 else None
    return t_critico(gl, alfa / n)


def bootstrap_bloques(xs, bloque=10, iteraciones=1000, semilla=12345, nivel=0.90):
    """IC de la media con bootstrap de bloques móviles (respeta la dependencia entre operaciones seguidas)."""
    n = len(xs)
    if n < max(10, bloque):
        return None
    rng = random.Random(semilla)
    b = max(1, min(bloque, n))
    medias = []
    for _ in range(iteraciones):
        muestra = []
        while len(muestra) < n:
            i = rng.randrange(0, n - b + 1)
            muestra.extend(xs[i:i + b])
        medias.append(sum(muestra[:n]) / n)
    medias.sort()
    lo = medias[int((1 - nivel) / 2 * iteraciones)]
    hi = medias[min(iteraciones - 1, int((1 + nivel) / 2 * iteraciones))]
    return {"nivel": nivel, "inferior": round(lo, 4), "superior": round(hi, 4)}


def escenarios_estres(trades, taker_pct, deslizamiento_pct, hueco_stop_r=0.15):
    """Escenarios ADVERSOS explícitos y reproducibles (cada uno resta su coste en R a cada operación):
      costes_x2         otra vez las comisiones taker y el deslizamiento de ida y vuelta (costes al doble)
      deslizamiento_x3  deslizamiento de ida y vuelta tres veces mayor
      huecos_en_stops   las salidas por stop se ejecutan 'hueco_stop_r' R peor (gaps, mark ≠ mid)
      combinado         costes ×2 + huecos en stops
    Devuelve {nombre: {"descripcion", "trades"}}."""
    def coste_desl(t):        # deslizamiento de ida y vuelta de ESA operación (variable) o el fijo
        return 2 * (t.get("deslizamiento_pct") if t.get("deslizamiento_pct") is not None else deslizamiento_pct)

    def stop(t):
        return str(t.get("salida", "")).startswith("stop")
    out = {
        "costes_x2": ("comisiones y deslizamiento de ida y vuelta al doble",
                      [dict(t, r=t["r"] - (2 * taker_pct + coste_desl(t)) / t["sl_pct"]) for t in trades if t.get("sl_pct")]),
        "deslizamiento_x3": ("deslizamiento ×3",
                             [dict(t, r=t["r"] - 2 * coste_desl(t) / t["sl_pct"]) for t in trades if t.get("sl_pct")]),
        "huecos_en_stops": (f"salidas por stop {hueco_stop_r} R peor",
                            [dict(t, r=t["r"] - (hueco_stop_r if stop(t) else 0.0)) for t in trades]),
    }
    if any("funding_r" in t for t in trades):
        out["funding_x3"] = ("funding pagado ×3 (y sin cobrar el favorable)",
                             [dict(t, r=t["r"] - 2 * abs(t.get("funding_r") or 0.0)) for t in trades])
    out["combinado"] = ("costes ×2 y huecos en stops",
                        [dict(t, r=t["r"] - (hueco_stop_r if stop(t) else 0.0)) for t in out["costes_x2"][1]])
    return {k: {"descripcion": d, "trades": v} for k, (d, v) in out.items()}


def desglose(trades, clave):
    grupos = {}
    for t in trades:
        grupos.setdefault(clave(t), []).append(t["r"])
    return {str(k): {"n": len(v), "r_medio": round(media(v), 3), "r_total": round(sum(v), 2)}
            for k, v in sorted(grupos.items(), key=lambda x: str(x[0]))}


def trimestre(t):
    from datetime import datetime, timezone
    d = datetime.fromtimestamp(t, timezone.utc)
    return f"{d.year}-T{(d.month - 1) // 3 + 1}"


def estabilidad(trades):
    """Estabilidad temporal: resultado por trimestre y fracción de trimestres con media > 0."""
    por = desglose(trades, lambda t: trimestre(t["t"]))
    con_datos = [v for v in por.values() if v["n"] >= 5]
    return {"por_trimestre": por, "trimestres_positivos": sum(1 for v in con_datos if v["r_medio"] > 0),
            "trimestres_evaluables": len(con_datos)}


def exposicion_lados(trades):
    n = len(trades)
    largos = sum(1 for t in trades if t.get("lado") == "L")
    return {"largos_pct": round(largos / n * 100, 1) if n else None,
            "cortos_pct": round((n - largos) / n * 100, 1) if n else None}


# ============================================================ universo en el momento
def universo_en_el_tiempo(volumenes, n_monedas, ventana_seg=30 * 86400, paso_seg=86400, vol_min_ventana=0.0):
    """volumenes: {moneda: [(t, volumen_usd_de_la_vela), ...]} ordenados.
    Devuelve una función f(moneda, t) -> bool: ¿estaba la moneda entre las 'n_monedas' de más volumen en los
    'ventana_seg' anteriores a t? (Se calcula por días para que sea rápido.) Evita elegir el universo con
    el volumen de HOY (sesgo de supervivencia). Con vol_min_ventana > 0 además exige ese volumen acumulado en la
    ventana (el mismo mínimo diario que aplica el bot en vivo, × días de la ventana)."""
    if not volumenes:
        return lambda moneda, t: True
    t_min = min(v[0][0] for v in volumenes.values() if v)
    t_max = max(v[-1][0] for v in volumenes.values() if v)
    acumulados = {}
    for m, serie in volumenes.items():
        ts, acc, s = [], [], 0.0
        for t, vol in serie:
            s += vol
            ts.append(t)
            acc.append(s)
        acumulados[m] = (ts, acc)

    def vol_ventana(m, t):
        import bisect
        ts, acc = acumulados[m]
        i = bisect.bisect_left(ts, t) - 1
        j = bisect.bisect_left(ts, t - ventana_seg) - 1
        if i < 0:
            return 0.0
        return acc[i] - (acc[j] if j >= 0 else 0.0)

    miembros = {}
    dia = t_min
    while dia <= t_max + paso_seg:
        orden = sorted(volumenes, key=lambda m: vol_ventana(m, dia), reverse=True)
        miembros[int(dia // paso_seg)] = {m for m in orden[:n_monedas]
                                          if vol_ventana(m, dia) > 0 and vol_ventana(m, dia) >= vol_min_ventana}
        dia += paso_seg

    def esta(moneda, t):
        return moneda in miembros.get(int(t // paso_seg), set())
    return esta


# ============================================================ líneas base
def _r_de(res):
    """simular_en puede devolver un número (R) o {"r", "cierre_ts"}."""
    if res is None:
        return None, None
    if isinstance(res, dict):
        return res.get("r"), res.get("cierre_ts")
    return res, None


def linea_base_aleatoria(trades, simular_en, semilla=12345, t_min=None, t_max=None):
    """Misma cantidad de operaciones, en las mismas monedas y semanas, con el MISMO stop, la misma salida, la
    misma duración y los mismos costes, pero con lado y vela de entrada al azar. Solo dentro de [t_min, t_max]:
    la línea base tampoco puede usar precios de otra partición (si cierra después de t_max, se descarta).
    'simular_en(moneda, t, lado, sl_pct)' devuelve el R (o {"r", "cierre_ts"}) con la gestión real, o None."""
    rng = random.Random(semilla)
    out = []
    for t in trades:
        lado = rng.choice(("L", "S"))
        desplazamiento = rng.uniform(-3.5, 3.5) * 86400
        te = t["t"] + desplazamiento
        if (t_min is not None and te < t_min) or (t_max is not None and te >= t_max):
            te = t["t"]                      # se queda dentro de la partición
        r, cierre = _r_de(simular_en(t["moneda"], te, lado, t["sl_pct"]))
        if r is None or (t_max is not None and cierre is not None and cierre > t_max):
            continue
        out.append({"t": te, "r": r, "moneda": t["moneda"], "lado": lado, "sl_pct": t["sl_pct"], "cierre_ts": cierre})
    return out


def linea_base_largo(trades, simular_en, t_max=None):
    out = []
    for t in trades:
        r, cierre = _r_de(simular_en(t["moneda"], t["t"], "L", t["sl_pct"]))
        if r is None or (t_max is not None and cierre is not None and cierre > t_max):
            continue
        out.append({"t": t["t"], "r": r, "moneda": t["moneda"], "lado": "L", "sl_pct": t["sl_pct"], "cierre_ts": cierre})
    return out


def base_comparable(base, oos, min_fraccion=0.5, min_ops=15):
    """Una línea base solo sirve si tiene una muestra comparable a la de la estrategia."""
    return base is not None and len(base) >= max(min_ops, int(len(oos) * min_fraccion))


# ============================================================ cartera con las restricciones del bot
LIMITES_CARTERA = ("máximo de posiciones", "una por moneda", "máximo del mismo lado", "riesgo por operación (fijo)",
                   "riesgo abierto máximo", "operaciones por día", "pérdida diaria (realizada)",
                   "pérdida semanal (realizada)", "caída máxima desde el pico (realizada)")
# Lo que el bot aplica en vivo y esta cartera NO reproduce: su resultado no equivale a la curva real del bot.
LIMITES_NO_MODELADOS = ("exposición por moneda, bruta, neta y ponderada por beta", "correlación entre posiciones",
                        "margen libre y apalancamiento", "impacto en el libro y liquidez", "tamaño por precio/stop real "
                        "(se supone riesgo fijo por operación)", "suelo de emergencia", "gestión de capital (reducciones)",
                        "valoración diaria a mercado (solo resultados realizados)")


def cartera_produccion(trades, riesgo_cfg, equity=1.0):
    """Recorre las operaciones en orden temporal aplicando los límites de producción: máximo de posiciones,
    una por moneda, máximo del mismo lado, riesgo por operación, riesgo abierto máximo, operaciones por día y
    los bloqueos por pérdida diaria/semanal y caída desde el pico (con lo REALIZADO). Los cierres se aplican por
    orden de cierre (determinista). Las operaciones que siguen abiertas al final se CENSURAN (no se componen
    como si hubieran cerrado). Devuelve el resultado compuesto, qué se descartó por cada límite y qué límites del
    bot NO se modelan (LIMITES_NO_MODELADOS)."""
    abiertas, saldo, maximo, caida = [], equity, equity, 0.0
    hechas, descartes, por_dia = [], {}, {}
    inicio_dia, inicio_semana = {}, {}
    r_total, dias_invertidos = 0.0, set()
    rpo = riesgo_cfg["riesgo_por_operacion_pct"] / 100
    orden = sorted(trades, key=lambda x: (x["t"], -x.get("fuerza", 0), str(x.get("moneda")), x.get("lado", "")))
    ultimo_t = orden[-1]["t"] if orden else 0
    for t in orden:
        for a in sorted((a for a in abiertas if a["cierre_ts"] <= t["t"]), key=lambda a: (a["cierre_ts"], a["t"])):
            abiertas.remove(a)
            saldo *= 1 + rpo * a["r"]
            r_total += a["r"]
            maximo = max(maximo, saldo)
            caida = max(caida, (maximo - saldo) / maximo)
        dia = int(t["t"] // 86400)
        semana = int((t["t"] // 86400 + 3) // 7)            # semanas lunes-domingo (UTC)
        inicio_dia.setdefault(dia, saldo)
        inicio_semana.setdefault(semana, saldo)
        motivo = None
        if (saldo / inicio_dia[dia] - 1) * 100 <= -riesgo_cfg.get("perdida_diaria_max_pct", 1e9):
            motivo = "pérdida diaria"
        elif (saldo / inicio_semana[semana] - 1) * 100 <= -riesgo_cfg.get("perdida_semanal_max_pct", 1e9):
            motivo = "pérdida semanal"
        elif (1 - saldo / maximo) * 100 >= riesgo_cfg.get("drawdown_max_pct", 1e9):
            motivo = "caída máxima"
        elif len(abiertas) >= riesgo_cfg["max_posiciones_abiertas"]:
            motivo = "máximo de posiciones"
        elif any(a["moneda"] == t["moneda"] for a in abiertas):
            motivo = "ya hay posición en la moneda"
        elif sum(1 for a in abiertas if a["lado"] == t["lado"]) >= riesgo_cfg["max_mismo_lado"]:
            motivo = "máximo del mismo lado"
        elif (len(abiertas) + 1) * riesgo_cfg["riesgo_por_operacion_pct"] > riesgo_cfg["riesgo_abierto_max_pct"]:
            motivo = "riesgo abierto máximo"
        elif por_dia.get(dia, 0) >= riesgo_cfg["max_operaciones_dia"]:
            motivo = "operaciones por día"
        if motivo:
            descartes[motivo] = descartes.get(motivo, 0) + 1
            continue
        abiertas.append(t)
        por_dia[dia] = por_dia.get(dia, 0) + 1
        hechas.append(t)
        for d in range(int(t["t"] // 86400), int(t["cierre_ts"] // 86400) + 1):
            dias_invertidos.add(d)
    # Las que siguen abiertas tras la última entrada de la muestra se CENSURAN: no se componen (su cierre cae
    # fuera de lo evaluado y componerlas en un orden arbitrario falsearía la curva). Se informan aparte.
    censuradas = list(abiertas)
    return {"operaciones": len(hechas), "candidatas": len(orden), "rechazadas": len(orden) - len(hechas),
            "resultado_pct": round((saldo / equity - 1) * 100, 2), "resultado_r": round(r_total, 3),
            "caida_max_pct": round(caida * 100, 2), "descartadas": descartes, "dias_invertidos": len(dias_invertidos),
            "abiertas_al_final_censuradas": len(censuradas),
            "limites_aplicados": list(LIMITES_CARTERA), "limites_no_modelados": list(LIMITES_NO_MODELADOS),
            "nota": "riesgo fijo por operación y solo resultados realizados: aproximación, no la curva real del bot"}


def diferencia_emparejada(oos, base, cfg_lab):
    """Candidato − línea base, sumando R por DÍA de calendario en el MISMO periodo (días sin operaciones = 0,
    es decir, en efectivo). Bootstrap por bloques de días contiguos (conserva la dependencia temporal y, al
    agregar por día, la correlación entre monedas del mismo día). None si no hay días comunes suficientes."""
    if not oos or not base:
        return None
    d0 = int(min(min(t["t"] for t in oos), min(t["t"] for t in base)) // 86400)
    d1 = int(max(max(t["t"] for t in oos), max(t["t"] for t in base)) // 86400)
    if d1 - d0 + 1 < 10:
        return None
    cand, bas = [0.0] * (d1 - d0 + 1), [0.0] * (d1 - d0 + 1)
    for serie, ts in ((cand, oos), (bas, base)):
        for t in ts:
            serie[int(t["t"] // 86400) - d0] += t["r"]
    dif = [a - b for a, b in zip(cand, bas)]
    ic = bootstrap_bloques(dif, max(5, cfg_lab.get("bloque_bootstrap", 10)), cfg_lab.get("bootstrap_iteraciones", 1000),
                           cfg_lab.get("semilla", 12345))
    return {"dias": len(dif), "media_dia": round(media(dif), 5), "ic": ic}


def meseta(combos, elegidos, rejilla, desde, hasta, min_ops=10, fraccion_meseta=0.6):
    """¿Los parámetros elegidos están en una MESETA o son un PICO aislado (sobreajuste)?
    combos: [(params, trades)] con TODA la rejilla; se mide el R medio de cada combinación FIJA en el periodo fuera
    de muestra [desde, hasta). Vecinos: el mismo juego con un solo parámetro movido un paso en su lista de valores.
    Tolerancia: 5 % de max(|R elegido|, rango de R de la rejilla). Fracción de vecinos dentro de la tolerancia (o
    mejores): ≥ fraccion_meseta -> 'meseta'; > 0 -> 'pendiente'; 0 -> 'pico'; sin vecinos medibles -> 'aislado'."""
    def clave(p):
        return json.dumps(p, sort_keys=True)

    def r_medio(trades):
        rs = [t["r"] for t in trades if desde <= t["t"] < hasta]
        return media(rs) if len(rs) >= min_ops else None
    por = {clave(p): r_medio(ts) for p, ts in combos}
    mejor = por.get(clave(elegidos))
    if mejor is None:
        return {"estado": "no_evaluable", "motivo": f"los parámetros elegidos tienen menos de {min_ops} operaciones "
                                                    f"en el periodo fuera de muestra", "vecinos": []}
    vecinos = []
    for k, valores in rejilla.items():
        if elegidos.get(k) not in valores:
            continue
        j = valores.index(elegidos[k])
        for jj in (j - 1, j + 1):
            if 0 <= jj < len(valores):
                v = por.get(clave(dict(elegidos, **{k: valores[jj]})))
                vecinos.append({"cambia": {k: valores[jj]}, "r_medio": None if v is None else round(v, 4)})
    medibles = [v for v in vecinos if v["r_medio"] is not None]
    todos = [x for x in por.values() if x is not None]
    tol = 0.05 * max(abs(mejor), max(todos) - min(todos))
    base = {"r_elegido": round(mejor, 4), "tolerancia": round(tol, 4), "vecinos": vecinos}
    if not medibles:
        return dict(base, estado="aislado", fraccion=None)
    cerca = sum(1 for v in medibles if v["r_medio"] >= mejor - tol)
    frac = cerca / len(medibles)
    estado = "meseta" if frac >= fraccion_meseta else ("pendiente" if frac > 0 else "pico")
    return dict(base, estado=estado, fraccion=round(frac, 2))


# ============================================================ ficha de probabilidades (qué cabe esperar)
SALIDAS = {"stop": "stop inicial", "protegido": "stop movido (sin pérdidas o dinámico)", "objetivo": "objetivo final",
           "tiempo": "tiempo máximo", "otra": "otra salida"}


def tipo_salida(motivo):
    m = str(motivo or "").lower()
    if m == "stop-loss":
        return "stop"
    if m.startswith("stop"):
        return "protegido"
    if m.startswith("objetivo"):
        return "objetivo"
    if m.startswith("tiempo"):
        return "tiempo"
    return "otra"


def wilson(k, n, z=1.96):
    """Intervalo de Wilson al 95 % de una proporción (en %). None si n = 0."""
    if not n:
        return None
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"inferior": round(max(0.0, centro - margen) * 100, 1), "superior": round(min(1.0, centro + margen) * 100, 1)}


def probabilidades(trades, cfg_lab=None, min_n=30):
    """«Qué cabe esperar» de una estrategia con sus operaciones FUERA DE MUESTRA (idea de la «Time Machine» de
    day-trader-skill, pero con los datos del laboratorio: años de velas, costes y sin elegir a posteriori).
    Reparto por tipo de salida, % de ganadoras con IC de Wilson, R medio con IC bootstrap por bloques (95 %) y una
    lectura honesta: 'a_favor' / 'en_contra' solo si el IC del R medio excluye 0; si no, 'azar'."""
    cfg_lab = cfg_lab or {}
    rs = [t["r"] for t in trades]
    n = len(rs)
    if not n:
        return {"n": 0, "lectura": "sin_datos"}
    por = {}
    for clave in SALIDAS:
        xs = [t["r"] for t in trades if tipo_salida(t.get("salida")) == clave]
        por[clave] = {"n": len(xs), "pct": round(len(xs) / n * 100, 1), "r_medio": round(media(xs), 3) if xs else None}
    gan = sum(1 for x in rs if x > 0)
    ic = bootstrap_bloques(rs, cfg_lab.get("bloque_bootstrap", 10), cfg_lab.get("bootstrap_iteraciones", 1000),
                           cfg_lab.get("semilla", 12345), nivel=0.95)
    if n < min_n or ic is None:
        lectura = "muestra_pequena"
    elif ic["inferior"] > 0:
        lectura = "a_favor"
    elif ic["superior"] < 0:
        lectura = "en_contra"
    else:
        lectura = "azar"
    return {"n": n, "salidas": por, "ganadoras_pct": round(gan / n * 100, 1), "ganadoras_ic": wilson(gan, n),
            "r_medio": round(media(rs), 4), "r_ic": ic, "lectura": lectura,
            "nota": "fuera de muestra del laboratorio, con costes; describe el pasado, no garantiza el futuro"}


def curva_estrategia(trades, max_puntos=160):
    """Curva de capital FUERA DE MUESTRA en R (para el panel, 18/11/2026): R acumulado por fecha de cierre, caída
    desde el máximo, resultado por mes y métricas de la ficha (acierto, R:R, esperanza, operaciones, caída máxima).
    Solo describe el pasado; no entra en ningún veredicto."""
    ts = sorted((t for t in trades if t.get("r") is not None), key=lambda t: (t.get("cierre_ts") or t["t"], t["t"]))
    if not ts:
        return {"n": 0}
    acum, maximo, puntos, peor = 0.0, 0.0, [], 0.0
    for t in ts:
        acum += t["r"]
        maximo = max(maximo, acum)
        peor = min(peor, acum - maximo)
        puntos.append([int(t.get("cierre_ts") or t["t"]), round(acum, 3), round(acum - maximo, 3)])
    if len(puntos) > max_puntos:                     # se submuestrea conservando el último punto
        paso = len(puntos) / max_puntos
        puntos = [puntos[int(k * paso)] for k in range(max_puntos - 1)] + [puntos[-1]]
    from datetime import datetime, timezone
    meses = {}
    for t in ts:
        m = datetime.fromtimestamp(t.get("cierre_ts") or t["t"], timezone.utc).strftime("%Y-%m")
        x = meses.setdefault(m, {"n": 0, "r": 0.0})
        x["n"] += 1
        x["r"] = round(x["r"] + t["r"], 3)
    ganan = [t["r"] for t in ts if t["r"] > 0]
    pierden = [-t["r"] for t in ts if t["r"] < 0]
    rr = media(ganan) / media(pierden) if ganan and pierden else None
    return {"n": len(ts), "puntos": puntos, "meses": meses, "acierto_pct": round(len(ganan) / len(ts) * 100, 1),
            "rr": round(rr, 2) if rr else None, "esperanza_r": round(media([t["r"] for t in ts]), 4),
            "caida_max_r": round(-peor, 2), "r_total": round(acum, 2),
            "meses_positivos": sum(1 for x in meses.values() if x["r"] > 0), "meses_total": len(meses)}


# ============================================================ veredicto
def veredicto(oos, holdout, n_variantes, cfg_lab, baselines=None, estres=None, veteranas=None, min_ops=30,
              holdout_fresco=None, escenarios=None, cartera=None, meseta_params=None):
    """Aplica las reglas para poder decir 'hay ventaja' (sin prometer nada). Devuelve dict con 'estado':
      'supera'        cumple TODO, incluido un holdout de un solo uso (no consultado antes)
      'exploratorio'  cumple todo pero el holdout independiente no basta (ya se había mirado): NO es evidencia
                      para promoción; hace falta esperar a tener datos nuevos
      'no_supera'     falla alguna regla
      'no_evaluable'  muestra insuficiente, línea base vacía/insuficiente u holdout corto: no se puede juzgar
    holdout: operaciones del holdout completo (ya purgadas). holdout_fresco: solo las que no se habían mirado
    antes (None = no se lleva registro: se trata TODO el holdout como fresco)."""
    r_oos = [t["r"] for t in oos]
    r_ho = [t["r"] for t in holdout]
    if len(r_oos) < min_ops:
        return {"estado": "no_evaluable", "motivo": f"solo {len(r_oos)} operaciones fuera de muestra (mínimo {min_ops})",
                "comprobaciones": []}
    min_ho = max(10, min_ops // 3)
    if len(r_ho) < min_ho:
        return {"estado": "no_evaluable", "motivo": f"holdout con {len(r_ho)} operaciones (mínimo {min_ho})",
                "comprobaciones": []}
    for nombre, base in (baselines or {}).items():
        if not base_comparable(base, oos):
            return {"estado": "no_evaluable", "motivo": f"línea base '{nombre}' vacía o insuficiente "
                                                        f"({len(base or [])} operaciones para {len(oos)})",
                    "comprobaciones": []}
    ic = bootstrap_bloques(r_oos, cfg_lab["bloque_bootstrap"], cfg_lab["bootstrap_iteraciones"], cfg_lab["semilla"])
    t_oos = estadistico_t(r_oos)
    req = t_requerido(n_variantes, n_ops=len(r_oos))
    # Las operaciones del mismo día (y de monedas correlacionadas) NO son independientes: se repite la prueba
    # sumando el resultado por día, que es la unidad que de verdad aporta información nueva.
    por_dia = {}
    for t in oos:
        por_dia[int(t["t"] // 86400)] = por_dia.get(int(t["t"] // 86400), 0.0) + t["r"]
    t_dias = estadistico_t(list(por_dia.values())) if len(por_dia) >= 2 else 0.0
    req_dias = t_requerido(n_variantes, n_ops=max(2, len(por_dia)))
    comp = [
        ("media fuera de muestra > 0", media(r_oos) > 0, round(media(r_oos), 4)),
        (f"t por días ≥ {req_dias:.2f} (resultado sumado por día: {len(por_dia)} días, no supone operaciones "
         f"independientes)", t_dias >= req_dias, round(t_dias, 2)),
        (f"t ≥ {req:.2f} (Student, una cola, {len(r_oos) - 1} gl, corrigiendo por {n_variantes} variantes)",
         t_oos >= req, round(t_oos, 2)),
        ("límite inferior del IC bootstrap > 0", bool(ic and ic["inferior"] > 0), ic),
        ("holdout final con media > 0", media(r_ho) > 0, round(media(r_ho), 4)),
    ]
    for nombre, base in (baselines or {}).items():
        mb = media([t["r"] for t in base])
        comp.append((f"mejor que la línea base '{nombre}' ({len(base)} operaciones comparables)", media(r_oos) > mb,
                     round(mb, 4)))
        # Comparar medias de muestras distintas no basta: diferencia EMPAREJADA por día, mismo periodo.
        de = diferencia_emparejada(oos, base, cfg_lab)
        if de is None:
            return {"estado": "no_evaluable", "motivo": f"no hay días comunes suficientes para comparar con '{nombre}'",
                    "comprobaciones": []}
        comp.append((f"diferencia emparejada por día frente a '{nombre}': IC bootstrap inferior > 0 ({de['dias']} días)",
                     bool(de["ic"] and de["ic"]["inferior"] > 0), de))
    if cartera is not None:
        # Solo se declara ventaja si sobrevive a los límites de producción que la cartera SÍ aplica (y se dice
        # cuáles no modela).
        comp.append(("cartera con los límites del bot con resultado > 0", cartera.get("resultado_pct", 0) > 0,
                     {k: cartera.get(k) for k in ("operaciones", "resultado_pct", "caida_max_pct", "descartadas",
                                                  "abiertas_al_final_censuradas", "limites_no_modelados")}))
    if estres is not None:
        me = media([t["r"] for t in estres]) if estres else None
        comp.append(("sigue > 0 con costes al doble", bool(me and me > 0), None if me is None else round(me, 4)))
    for nombre, esc in (escenarios or {}).items():
        if nombre == "combinado":
            continue                         # se informa, pero no decide (sería exigir dos peores casos a la vez)
        me = media([t["r"] for t in esc["trades"]]) if esc["trades"] else None
        comp.append((f"sigue > 0 en el escenario '{esc['descripcion']}'", bool(me and me > 0),
                     None if me is None else round(me, 4)))
    if veteranas is not None and len(veteranas) >= 10:
        mv = media([t["r"] for t in veteranas])
        comp.append(("positiva en monedas con historia completa", mv > 0, round(mv, 4)))
    if meseta_params is not None and meseta_params.get("estado") in ("meseta", "pendiente", "pico"):
        # Un pico aislado (ningún vecino de la rejilla rinde parecido) es la firma del sobreajuste.
        comp.append(("parámetros en meseta, no un pico aislado (vecinos de la rejilla parecidos fuera de muestra)",
                     meseta_params["estado"] != "pico",
                     {k: meseta_params.get(k) for k in ("estado", "fraccion", "r_elegido", "tolerancia")}))
    ok = all(c[1] for c in comp)
    fresco = holdout if holdout_fresco is None else holdout_fresco
    independiente = len(fresco) >= min_ho
    if ok and independiente:
        mf = media([t["r"] for t in fresco])
        comp.append((f"holdout NO consultado antes ({len(fresco)} operaciones) con media > 0", mf > 0, round(mf, 4)))
        ok = mf > 0
    estado = "supera" if ok and independiente else ("exploratorio" if ok else "no_supera")
    out = {"estado": estado, "t": round(t_oos, 2), "t_requerido": round(req, 2), "t_dias": round(t_dias, 2),
           "ic_bootstrap": ic,
           "holdout_independiente": independiente, "n_holdout_fresco": len(fresco),
           "comprobaciones": [{"regla": c[0], "cumple": c[1], "valor": c[2]} for c in comp]}
    if estado == "exploratorio":
        out["motivo"] = (f"el holdout ya se había consultado: solo {len(fresco)} operaciones nuevas (mínimo {min_ho}). "
                         f"Resultado exploratorio; no cuenta como evidencia hasta tener datos nuevos.")
    return out


# ============================================================ registros: variantes y holdout de un solo uso
class ErrorRegistro(RuntimeError):
    """Registro de variantes u holdout ilegible: empezar vacío haría la validación MÁS permisiva."""


def leer_registro(ruta, vacio):
    """Lee un registro JSON. Archivo ausente -> 'vacio'. Corrupto -> se intenta la copia .bak (la última buena);
    si tampoco vale, ErrorRegistro (falla cerrado: no se sigue como si no hubiera historia)."""
    import os
    if not os.path.exists(ruta) and not os.path.exists(ruta + ".bak"):
        return vacio
    for r in (ruta, ruta + ".bak"):
        try:
            with open(r, encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, dict):
                return d
        except (OSError, ValueError):
            continue
    raise ErrorRegistro(f"{os.path.basename(ruta)} está dañado y no hay copia válida: revísalo antes de seguir "
                        f"(empezar de cero rebajaría los umbrales del laboratorio)")


def guardar_registro(ruta, d, **kw):
    """Escritura atómica y durable; antes, la versión anterior VÁLIDA pasa a .bak."""
    import os
    import shutil
    if os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as fh:
                json.load(fh)
            shutil.copy2(ruta, ruta + ".bak")
        except (OSError, ValueError):
            pass                                  # no se respalda un archivo roto encima de la copia buena
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, **kw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, ruta)


def familia_idea(definicion):
    """Familia de una idea de investigación: disparador × intervalo (p. ej. «inv:rsi@1h»). Las variantes de una misma
    familia (otros umbrales, filtros o salidas) están muy correlacionadas: no son pruebas independientes."""
    try:
        return f"inv:{definicion['disparador']['tipo']}@{definicion.get('intervalo', '?')}"
    except (KeyError, TypeError):
        return "inv:?"


class RegistroVariantes:
    """Todas las variantes probadas DESDE SIEMPRE (laboratorio e investigación), cada una con su FAMILIA.

    Desde el 19/11/2026 (decisión de Roberto) el umbral de t se corrige por el número de FAMILIAS (pruebas
    aproximadamente independientes), no por el de variantes: Bonferroni sobre ~1 100 variantes casi todas vecinas de la
    misma rejilla trataba como independientes pruebas que no lo son y exigía t ≥ ~4,2. Repetir pruebas o ampliar una
    rejilla sigue sin «regalar» nada (no añade familias), pero una idea de un TIPO nuevo sí sube el listón.
    Familias: laboratorio = módulo × intervalo; investigación = disparador × intervalo; cerebro = una."""

    def __init__(self, ruta):
        self.ruta = ruta
        self.d = leer_registro(ruta, {"version": 1, "variantes": {}})
        self.d.setdefault("variantes", {})
        self.d.setdefault("familias", {})

    @staticmethod
    def id_variante(origen, definicion):
        return origen + ":" + hashlib.sha256(json.dumps(definicion, sort_keys=True, default=str).encode()).hexdigest()[:16]

    def añadir(self, ids, ts=None, familias=None):
        """familias: {id: familia} opcional (también rellena la familia de ids ya registrados que no la tenían)."""
        import time
        for i in ids:
            self.d["variantes"].setdefault(i, int(ts or time.time()))
        for i, f in (familias or {}).items():
            if i in self.d["variantes"] and f:
                self.d["familias"].setdefault(i, f)
        return self.total()

    def familia(self, i):
        f = self.d["familias"].get(i)
        if f:
            return f
        if i.startswith("cerebro:"):
            return "cerebro"
        # Sin familia conocida (registros antiguos): se agrupan por origen. Las del laboratorio antiguas son versiones
        # o rejillas anteriores de los mismos módulos; cuentan como UNA familia más (prudente).
        return i.split(":", 1)[0] + ":antiguas"

    def total(self, extra=0):
        return len(self.d["variantes"]) + extra

    def efectivas(self, extra=0):
        """Número de familias distintas: es el que corrige el umbral de t."""
        return max(1, len({self.familia(i) for i in self.d["variantes"]}) + extra)

    def guardar(self):
        guardar_registro(self.ruta, self.d)


def min_holdout(min_ops=30):
    """Operaciones mínimas del holdout (las mismas que exige veredicto con ese min_ops)."""
    return max(10, min_ops // 3)


def sellar_holdout(holdout, fresco, minimo):
    """Holdout ACUMULATIVO. 'fresco' = operaciones del holdout que nadie ha mirado aún.
    - Si ya son >= 'minimo': se ABRE. Devuelve (holdout completo, fresco, sello) y el llamador lo marca como visto.
    - Si no: queda SELLADO. Devuelve (holdout sin las frescas, [], sello): su resultado no se calcula ni se
      muestra y el llamador NO lo marca, así se acumula semana a semana en vez de gastarse cada vez.
    Contar cuántas hay no revela su resultado."""
    abierto = len(fresco) >= minimo
    sello = {"abierto": abierto, "n_reservado": len(fresco), "minimo": minimo}
    if abierto:
        return list(holdout), list(fresco), sello
    ids = {id(t) for t in fresco}
    return [t for t in holdout if id(t) not in ids], [], sello


class RegistroHoldout:
    """Hasta dónde se ha MIRADO ya el holdout de cada experimento. Formato v2:
    {"version": 2, "experimentos": {clave: {"visto_hasta": ts, "consultas": n}}, "usos": {...formato v1...}}.
    La migración desde v1 conserva 'usos' (reversible) y, como no se sabe qué estrategia miró qué, marca como
    vistos los holdouts de cada intervalo hasta la última modificación del archivo (conservador)."""

    def __init__(self, ruta):
        import os
        self.ruta = ruta
        d = leer_registro(ruta, {})
        if d.get("version") != 2:
            visto = os.path.getmtime(ruta) if d and os.path.exists(ruta) else None
            usos = {k: v for k, v in d.items() if isinstance(v, int)}
            exp = {}
            for k in usos:
                iv = k.split(":", 1)[0]
                if visto:
                    exp[f"intervalo:{iv}"] = {"visto_hasta": visto, "consultas": usos[k]}
            d = {"version": 2, "experimentos": exp, "usos": usos}
        self.d = d

    def visto_hasta(self, clave, intervalo=None):
        e = self.d["experimentos"].get(clave) or (self.d["experimentos"].get(f"intervalo:{intervalo}") if intervalo else None)
        return (e or {}).get("visto_hasta")

    def fresco(self, trades, clave, intervalo=None):
        """Solo las operaciones del holdout que ABREN después de lo ya mirado."""
        v = self.visto_hasta(clave, intervalo)
        return list(trades) if v is None else [t for t in trades if t["t"] >= v]

    def marcar(self, clave, hasta):
        e = self.d["experimentos"].setdefault(clave, {"visto_hasta": None, "consultas": 0})
        e["visto_hasta"] = max(e["visto_hasta"] or 0, hasta)
        e["consultas"] += 1

    def guardar(self):
        guardar_registro(self.ruta, self.d, indent=1)


# ============================================================ reproducibilidad
def hash_datos(mercados):
    """Hash del conjunto de datos usado (moneda, intervalo, primera/última vela, nº de velas, último cierre)."""
    h = hashlib.sha256()
    for m in sorted(mercados, key=lambda x: (x.moneda, x.intervalo)):
        ctx = m.ctx
        h.update(json.dumps([m.moneda, m.intervalo, len(ctx), ctx.t[0], ctx.t[-1], ctx.c[-1]]).encode())
    return h.hexdigest()[:16]
