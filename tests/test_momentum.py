import json
import os
import unittest

from estrategia import SimSalida
from motor import Motor
from senales import MODULOS, Contexto, barras_max, detectar, usa_intervalo
from tests.comunes import LOG, ConCarpeta, config

H4 = 4 * 3600 * 1000


def velas(n, paso):
    out, px = [], 100.0
    for i in range(n):
        px *= 1 + paso + (0.002 if i % 2 else -0.002)
        out.append({"t": i * H4, "o": str(px), "h": str(px * 1.004), "l": str(px * 0.996), "c": str(px), "v": "1"})
    return out


class Momentum(unittest.TestCase):
    P = {"lookback": 63, "rebalanceo": 21, "umbral_atr": 3.0, "eficiencia_min": 0.1, "sl_atr": 3.0}

    def senal_en_rebalanceo(self, ctx):
        i = max(k for k in range(len(ctx)) if int(ctx.t[k] // 14400) % 21 == 0)
        return detectar("momentum", ctx, i, self.P)

    def test_tendencia_clara_da_senal_a_favor(self):
        self.assertEqual(self.senal_en_rebalanceo(Contexto(velas(300, 0.004)))["lado"], "L")
        self.assertEqual(self.senal_en_rebalanceo(Contexto(velas(300, -0.004)))["lado"], "S")

    def test_lateral_no_da_senal(self):
        self.assertIsNone(self.senal_en_rebalanceo(Contexto(velas(300, 0.0))))

    def test_solo_fuera_del_rebalanceo_no_hay_senal(self):
        ctx = Contexto(velas(300, 0.004))
        i = max(k for k in range(len(ctx)) if int(ctx.t[k] // 14400) % 21 == 5)
        self.assertIsNone(detectar("momentum", ctx, i, self.P))

    def test_solo_4h_y_dura_hasta_el_rebalanceo(self):
        self.assertTrue(usa_intervalo("momentum", "4h"))
        self.assertFalse(usa_intervalo("momentum", "1h"))
        self.assertEqual(barras_max("momentum", self.P), 20)
        self.assertTrue(MODULOS["momentum"]["salida"]["sin_objetivo"])


class SalidaV2(ConCarpeta):
    """14/11/2026: momentum v2 protege ganancias (breakeven y trailing a 1,5 R) sin añadir objetivo."""

    def salida(self):
        return dict(config()["salida"], **MODULOS["momentum"]["salida"])

    def test_salida_v2_declarada(self):
        s = MODULOS["momentum"]["salida"]
        self.assertEqual(MODULOS["momentum"]["version"], "2")
        self.assertEqual((s["breakeven_tras_r"], s["trailing_r"]), (1.5, 1.5))
        self.assertTrue(s["trailing_sin_parcial"] and s["sin_objetivo"] and not s["parcial_activo"])

    def test_el_corto_sube_el_stop_y_cierra_con_ganancia_al_rebotar(self):
        # entrada 100, stop 10 % (1 R = 10): a 85 (+1,5 R) el stop pasa a sin pérdidas y a 80 (+2 R) a 95 (+0,5 R).
        s = SimSalida("S", 100.0, 10.0, self.salida(), 10**12, 0.00015, 0.00045, 0.00015)
        self.assertFalse(s.paso(99.0, 85.0, 85.0, 1))
        self.assertTrue(s.en_breakeven)
        self.assertFalse(s.paso(85.0, 80.0, 80.0, 2))
        self.assertLess(s.sl, 100.0)                     # el stop ya está en beneficio, no en 110
        self.assertTrue(s.paso(96.0, 80.0, 95.5, 3))     # rebote: salta el stop dinámico
        self.assertGreater(s.resultado_r(), 0.3)

    def test_v1_no_movia_el_stop(self):
        v1 = dict(self.salida(), breakeven_tras_r=99, trailing_r=99, trailing_sin_parcial=False)
        s = SimSalida("S", 100.0, 10.0, v1, 10**12, 0.00015, 0.00045, 0.00015)
        s.paso(100.5, 80.0, 80.0, 1)
        self.assertEqual(s.sl, 110.0)

    def test_un_veredicto_de_la_version_anterior_no_manda_sobre_la_salida(self):
        vieja = dict(self.salida(), breakeven_tras_r=99, trailing_r=99, trailing_sin_parcial=False)
        ruta = os.path.join(self.dir, "estrategia_elegida.json")
        for version, esperado in (("1", 1.5), ("2", 99)):
            with open(ruta, "w", encoding="utf-8") as fh:
                json.dump({"resultados": {"momentum_4h": {"version": version, "params": dict(MODULOS["momentum"]["defecto"]),
                                                          "salida": vieja, "barras_max": 20, "supera": False}}}, fh)
            m = Motor(config(), LOG, ruta)
            e = next(x for x in m.estrategias if x["clave"] == "momentum_4h")
            self.assertEqual(e["salida"]["breakeven_tras_r"], esperado, version)
