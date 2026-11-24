"""Prueba de «mirar el futuro» (lookahead), al estilo del lookahead-analysis de Freqtrade (17/11/2026).

Idea: una señal o un rasgo decididos al cierre de la vela i solo pueden depender de las velas 0..i. Se calculan
dos veces, con TODA la historia y con la historia CORTADA en i; si alguno cambia, la definición está usando datos
que en vivo aún no existen y todos los veredictos del laboratorio estarían inflados.
Cubre: todos los módulos de senales.MODULOS con toda su rejilla, Contexto.rasgos (aprendizaje), los rasgos del
cerebro (mercado_unificado.rasgos, con funding y datos externos), el ranking de fuerza y el régimen de BTC.
"""

import math
import random
import unittest

import mercado_unificado as mu
from senales import (MODULOS, Contexto, btc_alcista_en, combinaciones, detectar, rangos_fuerza)

H4 = 4 * 3600
T0 = 1_700_000_000 // H4 * H4


def velas(n=520, semilla=1, precio=100.0):
    rng = random.Random(semilla)
    out, p = [], precio
    for k in range(n):
        o = p
        p = max(0.01, p * math.exp(rng.gauss(0.0004, 0.02)))
        h, lo = max(o, p) * (1 + abs(rng.gauss(0, 0.006))), min(o, p) * (1 - abs(rng.gauss(0, 0.006)))
        out.append({"t": (T0 + k * H4) * 1000, "o": o, "h": h, "l": lo, "c": p, "v": 1000 + rng.random() * 500,
                    "tb": 500 + rng.random() * 400})
    return out


def iguales(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(iguales(a[k], b[k]) for k in a)
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


PUNTOS = range(230, 519, 11)


class SinMirarElFuturo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = velas()
        cls.full = Contexto(cls.v)

    def cortado(self, i, v=None):
        return Contexto((v or self.v)[:i + 1])

    def test_senales_de_todos_los_modulos(self):
        extra_funding = {"funding_medio": 0.01, "umbral_alto": 0.005, "umbral_bajo": -0.005}
        for nombre, mod in MODULOS.items():
            if nombre == "fuerza":
                continue                                # su 'extra' depende de todas las monedas: prueba aparte
            extra = extra_funding if nombre == "funding" else None
            for p in combinaciones(mod["rejilla"]):
                for i in PUNTOS:
                    a, b = detectar(nombre, self.full, i, p, extra), detectar(nombre, self.cortado(i), i, p, extra)
                    self.assertTrue(iguales(a, b), f"{nombre} {p} vela {i}: {a} != {b}")

    def test_rasgos_del_aprendizaje(self):
        for i in PUNTOS:
            for lado in ("L", "S"):
                self.assertTrue(iguales(self.full.rasgos(lado, i), self.cortado(i).rasgos(lado, i)), f"vela {i}")

    def test_rasgos_del_cerebro_con_funding_y_externos(self):
        rng = random.Random(5)
        regs = [{"time": (T0 + h * 3600) * 1000, "fundingRate": rng.gauss(0.00001, 0.00003)} for h in range(520 * 4)]
        regs_ext = [{"time": x["time"], "fundingRate": x["fundingRate"] * 0.8} for x in regs]
        ext = velas(semilla=9, precio=100.2)
        for i in PUNTOS:
            t_fin = T0 + (i + 1) * H4                   # cierre de la vela i: lo que existe en vivo en ese momento
            completo = mu.rasgos(self.full, i, "L", mu.FundingHorario(regs), mu.SerieExterna(ext),
                                 mu.FundingHorario(regs_ext))
            corto = mu.rasgos(self.cortado(i), i, "L",
                              mu.FundingHorario([x for x in regs if x["time"] / 1000 <= t_fin]),
                              mu.SerieExterna(ext[:i + 1]),
                              mu.FundingHorario([x for x in regs_ext if x["time"] / 1000 <= t_fin]))
            self.assertTrue(iguales(completo, corto), f"vela {i}: {completo} != {corto}")
            self.assertTrue(any(v is not None for v in completo.values()))

    def test_ranking_de_fuerza(self):
        monedas = {f"M{k}": velas(semilla=20 + k, precio=50 + k) for k in range(7)}
        for lookback in MODULOS["fuerza"]["rejilla"]["lookback"]:
            full = rangos_fuerza([(m, Contexto(v)) for m, v in monedas.items()], lookback)
            for i in PUNTOS:
                corto = rangos_fuerza([(m, Contexto(v[:i + 1])) for m, v in monedas.items()], lookback)
                for m in monedas:
                    self.assertTrue(iguales(full[m].get(i), corto[m].get(i)), f"{m} lookback {lookback} vela {i}")

    def test_fuerza_con_su_ranking(self):
        monedas = {f"M{k}": velas(semilla=40 + k) for k in range(7)}
        for p in combinaciones(MODULOS["fuerza"]["rejilla"]):
            full = {m: Contexto(v) for m, v in monedas.items()}
            rf = rangos_fuerza(list(full.items()), p["lookback"])
            for i in PUNTOS:
                cortos = {m: Contexto(v[:i + 1]) for m, v in monedas.items()}
                rc = rangos_fuerza(list(cortos.items()), p["lookback"])
                for m in monedas:
                    a = detectar("fuerza", full[m], i, p, rf[m].get(i))
                    b = detectar("fuerza", cortos[m], i, p, rc[m].get(i))
                    self.assertTrue(iguales(a, b), f"fuerza {p} {m} vela {i}")

    def test_la_prueba_detecta_una_fuga(self):
        """Control: una señal que mira la vela siguiente (como haría un shift(-1)) debe cazarse."""
        def con_fuga(ctx, i):
            return {"lado": "L"} if i + 1 < len(ctx) and ctx.c[i + 1] > ctx.c[i] else None
        cazadas = sum(not iguales(con_fuga(self.full, i), con_fuga(self.cortado(i), i)) for i in PUNTOS)
        self.assertGreater(cazadas, 0)

    def test_regimen_de_btc(self):
        for i in range(210, 519, 13):
            t = T0 + i * H4 + 1
            self.assertEqual(btc_alcista_en(self.full, t), btc_alcista_en(self.cortado(i), t), f"vela {i}")


if __name__ == "__main__":
    unittest.main()
