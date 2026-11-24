"""Suscripción de operaciones del mercado: si la conexión está cerrada, el fallo sube al bot, que reconecta."""

import logging
import tempfile
import unittest

from compat import consola_sin_seleccion
from mercado import Mercado
from tests.comunes import config


class WsCerrado:
    def subscribe(self, *a):
        raise RuntimeError("Connection is already closed")


class Suscribir(unittest.TestCase):
    def test_el_fallo_sube_para_que_el_bot_reconecte(self):
        with tempfile.TemporaryDirectory() as carpeta:
            m = Mercado(config(), logging.getLogger("prueba"), carpeta)
            with self.assertRaises(RuntimeError):
                m.suscribir(WsCerrado(), ["BTC"])
            self.assertEqual(m.subs, {})


class Consola(unittest.TestCase):
    def test_sin_consola_no_falla(self):
        self.assertIn(consola_sin_seleccion(), (True, False))
