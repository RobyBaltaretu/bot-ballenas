"""CP-M19 (auditoría 26/11/2026, T-09): la barrera de red de tests/__init__.py funciona."""
import socket
import threading
import unittest

import requests

import tests
from tests import RedProhibida


class BarreraDeRed(unittest.TestCase):
    def setUp(self):
        self.n = len(tests.intentos)

    def tearDown(self):
        del tests.intentos[self.n:]          # los intentos de ESTA prueba son a propósito: no cuentan como fuga

    def test_conexion_externa_prohibida_aunque_se_capture_exception(self):
        with self.assertRaises(RedProhibida):
            try:
                socket.create_connection(("api.hyperliquid.xyz", 443), timeout=1)
            except Exception:  # noqa: BLE001  (como hace el código del bot: aun así, no se esconde)
                self.fail("RedProhibida no debe ser una Exception")
        with self.assertRaises(RedProhibida):
            requests.post("https://api.hyperliquid.xyz/info", json={"type": "allMids"}, timeout=1)
        with self.assertRaises(RedProhibida):
            socket.getaddrinfo("fapi.binance.com", 443)
        self.assertTrue(issubclass(RedProhibida, BaseException) and not issubclass(RedProhibida, Exception))
        self.assertGreater(len(tests.intentos), self.n)

    def test_la_propia_maquina_si(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        hilo = threading.Thread(target=lambda: srv.accept()[0].close(), daemon=True)
        hilo.start()
        try:
            cli = socket.create_connection(("127.0.0.1", srv.getsockname()[1]), timeout=2)
            cli.close()
        finally:
            hilo.join(2)
            srv.close()
        self.assertEqual(len(tests.intentos), self.n)


if __name__ == "__main__":
    unittest.main()
