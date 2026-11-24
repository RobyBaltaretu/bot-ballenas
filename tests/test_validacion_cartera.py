"""A-03 / A-04 / A-12: la cartera aplica (y declara) los límites; el veredicto compara de forma EMPAREJADA por día y
no declara ventaja si la cartera con límites no la confirma; los registros dañados fallan cerrado."""

import json
import os
import unittest

import validacion as vd
from tests.comunes import ConCarpeta, config
from tests.test_laboratorio_validez import DIA, LAB, ops


class Cartera(unittest.TestCase):
    def test_declara_limites_y_censura_las_abiertas_al_final(self):
        c = config()
        ts = ops(30, 0.5) + [{"t": 29 * DIA + 10, "cierre_ts": 40 * DIA, "r": 50.0, "moneda": "SOL", "lado": "L"}]
        res = vd.cartera_produccion(ts, c["riesgo"])
        self.assertGreaterEqual(res["abiertas_al_final_censuradas"], 1)
        self.assertIn("correlación entre posiciones", res["limites_no_modelados"])
        self.assertEqual(res["candidatas"], 31)
        self.assertEqual(res["operaciones"] + res["rechazadas"], res["candidatas"])
        # La operación de +50 R que sigue abierta NO se compone como si hubiera cerrado.
        sin = vd.cartera_produccion(ts[:-1], c["riesgo"])
        self.assertLess(res["resultado_pct"], sin["resultado_pct"] + 50)

    def test_bloqueo_por_caida_maxima(self):
        c = config()
        r = dict(c["riesgo"], drawdown_max_pct=3, riesgo_por_operacion_pct=1, max_posiciones_abiertas=1)
        malas = [{"t": i * DIA, "cierre_ts": i * DIA + 3600, "r": -1.0, "moneda": "ETH", "lado": "L"} for i in range(20)]
        res = vd.cartera_produccion(malas, r)
        self.assertIn("caída máxima", res["descartadas"])
        self.assertLessEqual(res["operaciones"], 4)

    def test_orden_determinista(self):
        c = config()
        ts = ops(60, 0.2)
        self.assertEqual(vd.cartera_produccion(ts, c["riesgo"]), vd.cartera_produccion(list(reversed(ts)), c["riesgo"]))


class VeredictoEmparejado(unittest.TestCase):
    def test_pasa_por_operaciones_pero_falla_por_cartera(self):
        oos, ho, bases = ops(120, 0.6), ops(40, 0.6, t0=200 * DIA, semilla=2), {"aleatoria": ops(120, 0.0, semilla=3)}
        self.assertEqual(vd.veredicto(oos, ho, 10, LAB, bases)["estado"], "supera")
        mala = {"resultado_pct": -3.0, "operaciones": 40, "descartadas": {"máximo de posiciones": 80},
                "limites_no_modelados": list(vd.LIMITES_NO_MODELADOS)}
        v = vd.veredicto(oos, ho, 10, LAB, bases, cartera=mala)
        self.assertEqual(v["estado"], "no_supera")
        self.assertTrue(any("cartera" in c["regla"] and not c["cumple"] for c in v["comprobaciones"]))

    def test_media_bruta_positiva_pero_emparejada_no_supera(self):
        # El candidato gana de media, pero la base gana MÁS los mismos días: la comparación emparejada lo detecta.
        oos = ops(120, 0.3)
        base = [dict(t, r=t["r"] + 0.5) for t in oos]
        v = vd.veredicto(oos, ops(40, 0.6, t0=200 * DIA, semilla=2), 1, LAB, {"igual pero mejor": base})
        self.assertNotEqual(v["estado"], "supera")
        regla = next(c for c in v["comprobaciones"] if "emparejada" in c["regla"])
        self.assertFalse(regla["cumple"])

    def test_sin_dias_comunes_suficientes_no_evaluable(self):
        oos = ops(40, 0.6, paso=600)                         # todo en menos de un día
        v = vd.veredicto(oos, ops(40, 0.6, t0=200 * DIA), 1, LAB, {"b": ops(40, 0.0, paso=600, semilla=4)})
        self.assertEqual(v["estado"], "no_evaluable")


class RegistrosFallanCerrado(ConCarpeta):
    def test_variantes_corrupto_no_empieza_de_cero(self):
        ruta = os.path.join(self.dir, "laboratorio_variantes.json")
        r = vd.RegistroVariantes(ruta)
        r.añadir(["a", "b", "c"])
        r.guardar()
        r.añadir(["d"])
        r.guardar()                                          # .bak = versión con 3
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write('{"variantes": {"a"')                   # escritura interrumpida
        self.assertEqual(vd.RegistroVariantes(ruta).total(), 3)          # se recupera la última copia buena
        with open(ruta + ".bak", "w", encoding="utf-8") as fh:
            fh.write("{roto")
        with self.assertRaises(vd.ErrorRegistro):
            vd.RegistroVariantes(ruta)

    def test_holdout_corrupto_no_se_vuelve_fresco(self):
        ruta = os.path.join(self.dir, "laboratorio_holdout.json")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("{roto")
        with self.assertRaises(vd.ErrorRegistro):
            vd.RegistroHoldout(ruta)

    def test_ausente_empieza_vacio(self):
        self.assertEqual(vd.RegistroVariantes(os.path.join(self.dir, "nuevo.json")).total(), 0)
        h = vd.RegistroHoldout(os.path.join(self.dir, "h.json"))
        h.marcar("x", 10)
        h.guardar()
        with open(os.path.join(self.dir, "h.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["experimentos"]["x"]["visto_hasta"], 10)
