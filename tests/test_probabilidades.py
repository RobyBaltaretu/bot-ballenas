"""Ficha «qué cabe esperar» de una estrategia (18/11/2026): reparto de salidas, IC y lectura honesta."""

import unittest

import validacion as vd


def ops(rs, salida="tiempo máximo"):
    return [{"t": 86400 * k, "r": r, "salida": salida} for k, r in enumerate(rs)]


class Probabilidades(unittest.TestCase):
    def test_tipos_de_salida(self):
        self.assertEqual(vd.tipo_salida("stop-loss"), "stop")
        self.assertEqual(vd.tipo_salida("stop sin pérdidas"), "protegido")
        self.assertEqual(vd.tipo_salida("stop dinámico"), "protegido")
        self.assertEqual(vd.tipo_salida("objetivo final"), "objetivo")
        self.assertEqual(vd.tipo_salida("tiempo máximo"), "tiempo")
        self.assertEqual(vd.tipo_salida(None), "otra")

    def test_reparto_suma_el_total(self):
        trades = ops([-1.0] * 10, "stop-loss") + ops([2.0] * 5, "objetivo final") + ops([0.3] * 25)
        p = vd.probabilidades(trades)
        self.assertEqual(p["n"], 40)
        self.assertEqual(sum(v["n"] for v in p["salidas"].values()), 40)
        self.assertEqual(p["salidas"]["stop"]["pct"], 25.0)
        self.assertEqual(p["salidas"]["objetivo"]["r_medio"], 2.0)

    def test_lecturas(self):
        self.assertEqual(vd.probabilidades(ops([0.5 + (0.1 if k % 2 else -0.1) for k in range(60)]))["lectura"], "a_favor")
        self.assertEqual(vd.probabilidades(ops([-0.5 + (0.1 if k % 2 else -0.1) for k in range(60)]))["lectura"], "en_contra")
        self.assertEqual(vd.probabilidades(ops([1.0 if k % 2 else -1.0 for k in range(60)]))["lectura"], "azar")
        self.assertEqual(vd.probabilidades(ops([1.0] * 10))["lectura"], "muestra_pequena")
        self.assertEqual(vd.probabilidades([])["lectura"], "sin_datos")

    def test_wilson(self):
        ic = vd.wilson(30, 100)
        self.assertLess(ic["inferior"], 30)
        self.assertGreater(ic["superior"], 30)
        self.assertIsNone(vd.wilson(0, 0))
        self.assertEqual(vd.wilson(0, 10)["inferior"], 0.0)


class Curva(unittest.TestCase):
    def test_curva_caida_y_meses(self):
        rs = [1.0, -0.5, -0.5, 2.0, -1.0]
        trades = [{"t": 86400 * 40 * k, "cierre_ts": 86400 * 40 * k + 3600, "r": r} for k, r in enumerate(rs)]
        c = vd.curva_estrategia(trades)
        self.assertEqual(c["n"], 5)
        self.assertEqual([p[1] for p in c["puntos"]], [1.0, 0.5, 0.0, 2.0, 1.0])
        self.assertEqual(c["caida_max_r"], 1.0)
        self.assertEqual(c["acierto_pct"], 40.0)
        self.assertEqual(c["rr"], 1.5 / (2.0 / 3))
        self.assertEqual(c["meses_total"], 5)
        self.assertEqual(c["r_total"], 1.0)

    def test_submuestreo_conserva_el_final(self):
        trades = [{"t": k * 3600, "r": 0.1} for k in range(1000)]
        c = vd.curva_estrategia(trades, max_puntos=50)
        self.assertEqual(len(c["puntos"]), 50)
        self.assertAlmostEqual(c["puntos"][-1][1], 100.0, places=2)

    def test_sin_operaciones(self):
        self.assertEqual(vd.curva_estrategia([]), {"n": 0})


if __name__ == "__main__":
    unittest.main()
