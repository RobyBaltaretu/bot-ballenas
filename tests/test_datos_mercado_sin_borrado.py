"""CP-E13 (auditoría 26/11/2026, W-03): datos_mercado/ es la única historia propia de OI, flujo y operaciones grandes
(Hyperliquid no la ofrece). El bot ya no la borra: antes, lo de más de 120 días se eliminaba cada día."""
import ast
import logging
import os
import tempfile
import time
import unittest

from mercado import Mercado
from tests.comunes import MercadoFalso, config

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BORRAR = {"remove", "unlink", "rmtree", "rmdir", "removedirs"}


def llamadas_de_borrado(ruta):
    with open(ruta, encoding="utf-8") as fh:
        arbol = ast.parse(fh.read())
    return [n.lineno for n in ast.walk(arbol)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in BORRAR]


class SinBorrado(unittest.TestCase):
    def test_los_que_escriben_datos_mercado_no_borran(self):
        # mercado.py (ctx, flujo, grandes) y contexto_externo.py (externo) son los que escriben en datos_mercado/.
        for nombre in ("mercado.py", "contexto_externo.py"):
            self.assertEqual(llamadas_de_borrado(os.path.join(RAIZ, nombre)), [], nombre)

    def test_un_archivo_muy_antiguo_sigue_ahi(self):
        with tempfile.TemporaryDirectory() as carpeta:
            viejo = os.path.join(carpeta, "ctx_2020-01-01.jsonl")
            with open(viejo, "w", encoding="utf-8") as fh:
                fh.write('{"t": 1577836800, "d": {}}\n')
            c = config()
            m = Mercado(c, logging.getLogger("prueba"), carpeta)
            m.foto(MercadoFalso(), ["BTC", "ETH"])                     # graba la foto del minuto (antes: y limpiaba)
            self.assertTrue(os.path.exists(viejo))
            hoy = time.strftime("%Y-%m-%d", time.gmtime())
            self.assertTrue(os.path.exists(os.path.join(carpeta, f"ctx_{hoy}.jsonl")))

    def test_la_clave_dias_guardar_ya_no_existe(self):
        self.assertNotIn("dias_guardar", config()["mercado"])


if __name__ == "__main__":
    unittest.main()
