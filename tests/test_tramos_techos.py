import unittest

import riesgo
from tests.comunes import config


class TramosYTechos(unittest.TestCase):
    def test_tramos_desde_meta(self):
        meta = {"universe": [{"name": "BTC", "marginTableId": 56}, {"name": "X", "marginTableId": 3}],
                "marginTables": [[56, {"marginTiers": [{"lowerBound": "0.0", "maxLeverage": 40},
                                                       {"lowerBound": "150000000.0", "maxLeverage": 20}]}], ["mal"]]}
        self.assertEqual(riesgo.tramos_margen(meta), {"BTC": [(0.0, 40), (150000000.0, 20)]})
        self.assertEqual(riesgo.tramos_margen({}), {})
        self.assertEqual(riesgo.apal_max_tramo([(0.0, 40), (1000.0, 5)], 999, 40), 40)
        self.assertEqual(riesgo.apal_max_tramo([(0.0, 40), (1000.0, 5)], 1000, 40), 5)

    def test_dimensionar_respeta_el_tramo(self):
        c = config()
        c["riesgo"]["apalancamiento_max"] = 40
        sin = riesgo.dimensionar(100000, 100000, 100.0, 1.0, 3, 40, c)
        con = riesgo.dimensionar_con_tramos([(0.0, 40), (1000.0, 1)], 100000, 100000, 100.0, 1.0, 3, 40, c)
        self.assertTrue(sin["ok"])
        if con["ok"]:
            self.assertLessEqual(con["apalancamiento"], 1)
            self.assertEqual(con["apal_max_tramo"], 1)
        igual = riesgo.dimensionar_con_tramos(None, 100000, 100000, 100.0, 1.0, 3, 40, c)
        self.assertEqual(igual["notional"], sin["notional"])

    def test_techos_del_real_no_se_pasan_con_config(self):
        c = config()
        c["modo"] = "real"
        c["riesgo"].update(riesgo_por_operacion_pct=50, riesgo_abierto_max_pct=90, apalancamiento_max=50)
        c["piloto_real"] = dict(c.get("piloto_real") or {}, riesgo_por_operacion_pct=50, riesgo_abierto_max_pct=90,
                                max_posiciones_abiertas=60, apalancamiento_max=50)
        r = riesgo.limites_efectivos(c)
        for k, techo in riesgo.TECHOS_REAL.items():
            if k in r:
                self.assertLessEqual(r[k], techo, k)
        c["modo"] = "simulado"
        self.assertEqual(riesgo.limites_efectivos(c)["riesgo_por_operacion_pct"], 50)   # en simulado no aplica


if __name__ == "__main__":
    unittest.main()
