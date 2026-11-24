"""SimSalida con OHLC: el orden dentro de la vela es desconocido. La base cuenta el peor orden plausible, marca la
ambigüedad y permite medir la sensibilidad (sin usarla para decidir)."""

import unittest

from estrategia import SimSalida

CS = {"parcial_activo": True, "tp1_r": 1.0, "parcial_pct": 50, "tp_final_r": 3.0, "trailing_r": 1.0,
      "breakeven_tras_r": 1.0, "mover_stop_min_r": 0.25}


def sim(lado="L", politica="peor", cs=CS):
    return SimSalida(lado, 100.0, 2.0, cs, 10**12, 0.00015, 0.00045, 0.00015, politica_intrabar=politica)


class Intrabar(unittest.TestCase):
    def test_stop_inicial_y_objetivo_en_la_misma_vela_cuenta_el_stop(self):
        for lado, alto, bajo in (("L", 102.5, 97.5), ("S", 102.5, 97.5)):
            s = sim(lado)
            self.assertTrue(s.paso(alto, bajo, 100, 1))
            self.assertEqual(s.motivo, "stop-loss", lado)
            self.assertEqual(s.ambiguas, 1)

    def test_tp1_y_nuevo_sin_perdidas_en_la_misma_vela(self):
        base, fav = sim(), sim(politica="favorable")
        for s in (base, fav):
            s.paso(102.2, 99.9, 101, 1)          # toca TP1 (102) y vuelve por debajo del sin pérdidas
        self.assertTrue(base.cerrada)
        self.assertEqual(base.motivo, "stop sin pérdidas")
        self.assertEqual(base.ambiguas, 1)
        self.assertFalse(fav.cerrada)             # sensibilidad: con el orden favorable seguiría abierta
        self.assertEqual(fav.ambiguas, 1)

    def test_corto_simetrico(self):
        s = sim("S")
        s.paso(100.1, 97.8, 99, 1)
        self.assertTrue(s.cerrada)
        self.assertEqual(s.ambiguas, 1)

    def test_breakeven_tras_r_sin_parcial(self):
        cs = dict(CS, parcial_activo=False)
        s = sim(cs=cs)
        s.paso(102.1, 99.95, 101, 1)              # avanza 1 R y en la misma vela toca el sin pérdidas
        self.assertTrue(s.cerrada)
        self.assertEqual(s.ambiguas, 1)

    def test_hueco_de_apertura_ejecuta_peor_que_el_stop(self):
        s = sim()
        s.paso(97.0, 96.0, 96.5, 1, apertura=96.5)
        self.assertLess(s.resultado_r(), -1.0)

    def test_sin_ambiguedad_no_cuenta(self):
        s = sim()
        s.paso(101.0, 99.0, 100.5, 1)
        self.assertEqual(s.ambiguas, 0)
        self.assertFalse(s.cerrada)

    def test_tiempo_maximo(self):
        s = SimSalida("L", 100.0, 2.0, CS, 5, 0.00015, 0.00045, 0.00015)
        self.assertTrue(s.paso(100.5, 99.5, 100.2, 5))
        self.assertEqual(s.motivo, "tiempo máximo")

    def test_simulacion_guardada_antigua_sigue_funcionando(self):
        d = sim().a_dict()
        d.pop("ambiguas")
        d.pop("politica_intrabar")                # formato anterior (aprendizaje.json ya guardado)
        s = SimSalida.desde_dict(d)
        self.assertFalse(s.paso(100.5, 100.5, 100.5, 1))
        self.assertTrue(s.paso(97.0, 97.0, 97.0, 2))

    def test_politica_desconocida_no_se_admite(self):
        with self.assertRaises(ValueError):
            sim(politica="optimista")
