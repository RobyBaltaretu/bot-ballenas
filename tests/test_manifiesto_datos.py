import unittest

import laboratorio as lab
import manifiesto_datos as md

T0 = 1735689600  # 01/01/2025 00:00 UTC


def velas(n, quitar=(), cambiar=None):
    out = []
    for i in range(n):
        if i in quitar:
            continue
        c = 100.0 + i
        if cambiar is not None and i == cambiar:
            c += 1
        out.append({"t": (T0 + i * 4 * 3600) * 1000, "o": c, "h": c + 1, "l": c - 1, "c": c, "v": 1})
    return out


class Manifiesto(unittest.TestCase):
    def test_huecos_y_funding(self):
        m = lab.Mercado("BTC", "4h", velas(400, quitar=range(100, 110)), None)
        s = md.serie(m)
        self.assertEqual(s["faltan"], 10)
        self.assertAlmostEqual(s["mayor_hueco_h"], 40.0)
        self.assertEqual(s["funding_cobertura_pct"], 0.0)
        man = md.construir({"4h": [m]})
        self.assertEqual(man["resumen"]["con_huecos"][0]["serie"], "BTC|4h")

    def test_historia_reescrita_se_detecta_y_el_mes_en_curso_no(self):
        antes = md.construir({"4h": [lab.Mercado("BTC", "4h", velas(400), None)]})
        igual = md.construir({"4h": [lab.Mercado("BTC", "4h", velas(400), None)]}, antes)
        self.assertEqual(igual["resumen"]["historia_cambiada"], [])
        self.assertEqual(igual["hash"], antes["hash"])
        otra = md.construir({"4h": [lab.Mercado("BTC", "4h", velas(400, cambiar=5), None)]}, antes)
        self.assertEqual(otra["resumen"]["historia_cambiada"], [{"serie": "BTC|4h", "meses": ["2025-01"]}])
        ultima = md.construir({"4h": [lab.Mercado("BTC", "4h", velas(400, cambiar=399), None)]}, antes)
        self.assertEqual(ultima["resumen"]["historia_cambiada"], [])      # el último mes aún puede cambiar
        self.assertTrue(md.texto(otra["resumen"])[1].startswith("  HISTORIA CAMBIADA"))


if __name__ == "__main__":
    unittest.main()
