"""Meseta de parámetros (17/11/2026): un resultado que solo existe en un punto de la rejilla es sobreajuste."""

import unittest

import validacion as vd
from senales import combinaciones

REJILLA = {"a": [1, 2, 3], "b": [10, 20]}


def combos(r_de):
    out = []
    for p in combinaciones(REJILLA):
        r = r_de(p)
        out.append((p, [{"t": 1000 + k, "r": r + (0.01 if k % 2 else -0.01)} for k in range(20)]))
    return out


class Meseta(unittest.TestCase):
    def test_meseta_cuando_los_vecinos_rinden_parecido(self):
        m = vd.meseta(combos(lambda p: 0.30), {"a": 2, "b": 10}, REJILLA, 0, 10_000)
        self.assertEqual(m["estado"], "meseta")
        self.assertEqual(len(m["vecinos"]), 3)               # a=1, a=3, b=20

    def test_pico_aislado(self):
        m = vd.meseta(combos(lambda p: 0.5 if p == {"a": 2, "b": 10} else -0.3), {"a": 2, "b": 10}, REJILLA, 0, 10_000)
        self.assertEqual(m["estado"], "pico")

    def test_pendiente(self):
        m = vd.meseta(combos(lambda p: 0.5 if p["a"] >= 2 and p["b"] == 10 else -0.3), {"a": 2, "b": 10}, REJILLA, 0, 10_000)
        self.assertEqual(m["estado"], "pendiente")

    def test_vecino_mejor_cuenta_como_cercano(self):
        m = vd.meseta(combos(lambda p: 0.2 if p == {"a": 2, "b": 10} else 0.6), {"a": 2, "b": 10}, REJILLA, 0, 10_000)
        self.assertEqual(m["estado"], "meseta")

    def test_solo_cuenta_el_periodo_fuera_de_muestra(self):
        m = vd.meseta(combos(lambda p: 0.3), {"a": 2, "b": 10}, REJILLA, 5000, 10_000)
        self.assertEqual(m["estado"], "no_evaluable")

    def test_sin_vecinos_medibles(self):
        cs = [(p, ts if p == {"a": 2, "b": 10} else ts[:3]) for p, ts in combos(lambda p: 0.3)]
        self.assertEqual(vd.meseta(cs, {"a": 2, "b": 10}, REJILLA, 0, 10_000)["estado"], "aislado")

    def test_un_pico_impide_superar_el_veredicto(self):
        oos = [{"t": 86400 * k, "r": 0.5 + (0.05 if k % 2 else -0.05), "moneda": "BTC"} for k in range(60)]
        ho = [{"t": 86400 * (100 + k), "r": 0.5, "moneda": "BTC"} for k in range(20)]
        cfg = {"bloque_bootstrap": 5, "bootstrap_iteraciones": 200, "semilla": 1}
        ver = vd.veredicto(oos, ho, 1, cfg, meseta_params={"estado": "pico", "fraccion": 0.0})
        regla = [c for c in ver["comprobaciones"] if "meseta" in c["regla"]]
        self.assertEqual(len(regla), 1)
        self.assertFalse(regla[0]["cumple"])
        self.assertNotEqual(ver["estado"], "supera")
        ok = vd.veredicto(oos, ho, 1, cfg, meseta_params={"estado": "meseta", "fraccion": 1.0})
        self.assertTrue([c for c in ok["comprobaciones"] if "meseta" in c["regla"]][0]["cumple"])
        # Sin datos de meseta (no evaluable) no se añade la regla
        sin = vd.veredicto(oos, ho, 1, cfg, meseta_params={"estado": "no_evaluable"})
        self.assertFalse([c for c in sin["comprobaciones"] if "meseta" in c["regla"]])


if __name__ == "__main__":
    unittest.main()
