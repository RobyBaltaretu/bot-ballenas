"""Un riesgo desconocido no cuenta como 0 (18/11/2026; defecto #55 de day-trader-skill trasladado al bot)."""

import unittest

import riesgo
from tests.comunes import config


def pos(moneda="BTC", lado="L", notional=50.0, **kw):
    return dict({"moneda": moneda, "lado": lado, "notional": notional}, **kw)


class RiesgoPosicion(unittest.TestCase):
    def test_usa_riesgo_usd_si_es_valido(self):
        self.assertEqual(riesgo.riesgo_posicion({"riesgo_usd": 6.5}), 6.5)
        self.assertEqual(riesgo.riesgo_posicion({"riesgo_usd": 0}), 0.0)        # sin pérdidas posible: 0 real

    def test_estima_con_tamano_entrada_y_stop(self):
        self.assertAlmostEqual(riesgo.riesgo_posicion({"tam": 400, "entrada": 0.144, "sl": 0.150}), 2.4)
        self.assertAlmostEqual(riesgo.riesgo_posicion({"riesgo_usd": None, "tam": -2, "entrada": 10, "sl": 9}), 2.0)

    def test_desconocido_es_none(self):
        for p in ({}, {"riesgo_usd": None}, {"riesgo_usd": float("nan")}, {"riesgo_usd": -1},
                  {"riesgo_usd": True}, {"tam": 1, "entrada": 10}, {"tam": 1, "entrada": 10, "sl": 0}):
            self.assertIsNone(riesgo.riesgo_posicion(p), p)


class Agregados(unittest.TestCase):
    def setUp(self):
        self.c = config()

    def test_posicion_sin_riesgo_conocido_bloquea_entradas(self):
        motivos = riesgo.comprobar_agregados(pos("ETH", riesgo_usd=1.0), [pos("BTC")], [], 1000.0, self.c)
        self.assertTrue(any("riesgo desconocido" in m and "BTC" in m for m in motivos), motivos)

    def test_con_riesgo_conocido_no_bloquea_por_ese_motivo(self):
        motivos = riesgo.comprobar_agregados(pos("ETH", riesgo_usd=1.0), [pos("BTC", riesgo_usd=2.0)], [], 1000.0, self.c)
        self.assertFalse(any("riesgo desconocido" in m for m in motivos), motivos)

    def test_el_estimado_cuenta_para_el_limite(self):
        lim = self.c["riesgo"]["riesgo_abierto_max_pct"]
        # Una abierta sin riesgo_usd pero con stop: su riesgo estimado llena el cupo y bloquea la nueva.
        grande = pos("BTC", tam=1.0, entrada=100.0, sl=100.0 - 1000 * lim / 100)
        motivos = riesgo.comprobar_agregados(pos("ETH", riesgo_usd=1.0), [grande], [], 1000.0, self.c)
        self.assertTrue(any("riesgo abierto total" in m for m in motivos), motivos)

    def test_exposicion_informa_de_lo_desconocido(self):
        e = riesgo.exposicion([pos("BTC", riesgo_usd=3.0), pos("SOL")], [], 100.0)
        self.assertEqual(e["riesgo_abierto_usd"], 3.0)
        self.assertEqual(e["riesgo_desconocido"], ["SOL"])


if __name__ == "__main__":
    unittest.main()
