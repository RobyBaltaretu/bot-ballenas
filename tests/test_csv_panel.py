"""Exportación CSV del panel: ningún texto se abre en Excel como fórmula (17/11/2026)."""

import unittest

import panel


class CeldaCSV(unittest.TestCase):
    def test_textos_peligrosos_quedan_como_texto(self):
        for v in ("=HYPERLINK(\"x\")", "+1+1", "-2+3", "@SUMA(A1)", "\tx", "\rx"):
            self.assertTrue(panel.celda_csv(v).startswith("'"), v)

    def test_numeros_y_textos_normales_no_cambian(self):
        for v in (-1.5, 0, 3, None, "ruptura_4h", "BTC"):
            self.assertEqual(panel.celda_csv(v), v)

    def test_listas_como_json_y_neutralizadas(self):
        self.assertEqual(panel.celda_csv(["a", "b"]), '["a", "b"]')
        self.assertEqual(panel.celda_csv([]), "[]")


if __name__ == "__main__":
    unittest.main()
