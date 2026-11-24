"""Hipótesis prerregistradas (17/11/2026): solo datos posteriores, muestra fija, veredicto único e inmutable."""

import copy
import os
import tempfile
import unittest

import configuracion as conf
import preregistro as pr
from tests.comunes import config

DIA = 86400


def ops(n, r=0.5, desde=pr.REGISTRO_TS, por_dia=1, alterna=True):
    out = []
    for i in range(n):
        t = desde + (i // por_dia) * DIA + 3600
        rr = r + (0.3 if (alterna and i % 2) else -0.3 if alterna else 0)
        out.append({"t": t, "cierre_ts": t + 4 * 3600, "moneda": "BTC", "r": rr, "sl_pct": 2.0})
    return out


def sin_estres(muestra):
    return [t["r"] for t in muestra]


class Preregistro(unittest.TestCase):
    def setUp(self):
        self.estado = {"hipotesis": {}}
        self.fin = pr.REGISTRO_TS + 400 * DIA

    def test_datos_anteriores_al_registro_no_cuentan(self):
        antes = ops(60, desde=pr.REGISTRO_TS - 100 * DIA)
        r = pr.evaluar("fuerza_4h", antes, self.fin, sin_estres, self.estado)
        self.assertEqual(r["estado"], "acumulando")
        self.assertEqual(r["progreso"]["operaciones"], 0)

    def test_acumulando_no_muestra_resultado(self):
        r = pr.evaluar("fuerza_4h", ops(10), self.fin, sin_estres, self.estado)
        self.assertEqual(r["estado"], "acumulando")
        self.assertNotIn("r_medio", r)
        self.assertNotIn("veredicto", self.estado["hipotesis"]["fuerza_4h"])

    def test_muestra_fija_exige_operaciones_y_dias(self):
        # 30 operaciones en solo 10 días: hay que esperar a cubrir 20 días distintos
        self.assertIsNone(pr.muestra_fija(ops(30, por_dia=3), self.fin))
        m = pr.muestra_fija(ops(60, por_dia=3), self.fin)
        self.assertEqual(len({int(t["t"] // DIA) for t in m}), pr.MIN_DIAS)
        self.assertEqual(len(pr.muestra_fija(ops(45), self.fin)), pr.MIN_OPS)    # se corta en la muestra fijada

    def test_operaciones_abiertas_al_final_no_cuentan(self):
        o = ops(30)
        fin = o[-1]["cierre_ts"]                       # la última aún no ha cerrado antes del final
        self.assertIsNone(pr.muestra_fija(o, fin))

    def test_confirma_con_ventaja_clara_y_rechaza_sin_ella(self):
        bueno = pr.evaluar("fuerza_4h", ops(30, r=0.5), self.fin, sin_estres, self.estado)
        self.assertEqual(bueno["estado"], "confirmada")
        self.assertLess(bueno["t_requerido"], 2.5)     # corrige por 2 hipótesis, no por mil variantes
        malo = pr.evaluar("carry_realista", ops(30, r=-0.1), self.fin, sin_estres, self.estado)
        self.assertEqual(malo["estado"], "rechazada")

    def test_estres_negativo_rechaza(self):
        r = pr.evaluar("fuerza_4h", ops(30, r=0.5), self.fin, lambda m: [t["r"] - 1 for t in m], self.estado)
        self.assertEqual(r["estado"], "rechazada")

    def test_veredicto_definitivo_no_se_recalcula(self):
        pr.evaluar("fuerza_4h", ops(30, r=0.5), self.fin, sin_estres, self.estado)
        otra = pr.evaluar("fuerza_4h", ops(80, r=-1.0), self.fin, sin_estres, self.estado)
        self.assertEqual(otra["estado"], "confirmada")
        self.assertTrue(otra["definitivo"])

    def test_cambiar_la_definicion_invalida(self):
        pr.evaluar("fuerza_4h", ops(5), self.fin, sin_estres, self.estado)
        original = copy.deepcopy(pr.HIPOTESIS["fuerza_4h"])
        try:
            pr.HIPOTESIS["fuerza_4h"]["params"]["lookback"] = 84
            r = pr.evaluar("fuerza_4h", ops(30, r=0.5), self.fin, sin_estres, self.estado)
            self.assertEqual(r["estado"], "invalidada")
        finally:
            pr.HIPOTESIS["fuerza_4h"] = original

    def test_estado_se_guarda_y_se_lee(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "pre.json")
            pr.evaluar("fuerza_4h", ops(30, r=0.5), self.fin, sin_estres, self.estado)
            pr.guardar_estado(self.estado, ruta)
            self.assertEqual(pr.cargar_estado(ruta)["hipotesis"]["fuerza_4h"]["veredicto"]["estado"], "confirmada")

    def test_cambiar_ruta_no_toca_el_archivo_real(self):
        """Regresión 17/11: con la ruta fijada al definir la función, cambiar RUTA_ESTADO seguía escribiendo el real."""
        real = pr.RUTA_ESTADO
        try:
            with tempfile.TemporaryDirectory() as d:
                pr.RUTA_ESTADO = os.path.join(d, "pre.json")
                pr.guardar_estado({"hipotesis": {"x": {}}})
                self.assertTrue(os.path.exists(pr.RUTA_ESTADO))
                self.assertIn("x", pr.cargar_estado()["hipotesis"])
        finally:
            pr.RUTA_ESTADO = real

    def test_definiciones_cerradas(self):
        from senales import MODULOS, combinaciones
        f = pr.HIPOTESIS["fuerza_4h"]
        self.assertEqual(str(MODULOS["fuerza"]["version"]), f["version"])
        self.assertIn(f["params"], combinaciones(MODULOS["fuerza"]["rejilla"]))
        self.assertEqual(len(pr.HIPOTESIS), 2)


class ConfigLaboratorio(unittest.TestCase):
    def test_por_defecto_solo_4h_y_busqueda_congelada(self):
        lab = conf.DEFECTOS["laboratorio"]
        self.assertEqual(lab["intervalos_estrategias"], ["4h"])
        self.assertIs(lab["busqueda_congelada"], True)

    def test_valores_invalidos_se_rechazan(self):
        for k, v in (("intervalos_estrategias", ["2h"]), ("intervalos_estrategias", []),
                     ("busqueda_congelada", "si")):
            c = config()
            c["laboratorio"][k] = v
            with self.assertRaises(Exception, msg=f"{k}={v}"):
                conf.validar(c, entorno={})


if __name__ == "__main__":
    unittest.main()
