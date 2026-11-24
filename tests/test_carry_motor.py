"""Carry fase 3: el motor simulado de dos patas, con una API falsa (sin red) y carpeta temporal."""

import json
import os
import tempfile
import time
import unittest

from carry.motor import MotorCarry, libro_simple


class Respuesta:
    status_code = 200

    def __init__(self, datos):
        self._d = datos

    def json(self):
        return self._d


class ApiFalsa:
    """Responde como /info de Hyperliquid. tasa = fundingRate por hora (fracción)."""

    def __init__(self, ahora, tasa=0.00005, marca=100000.0, spot=100020.0):
        self.ahora, self.tasa, self.marca, self.spot = ahora, tasa, marca, spot
        self.llamadas = []

    def __call__(self, url, json=None, timeout=0):
        t = json["type"]
        self.llamadas.append(t)
        if t == "metaAndAssetCtxs":
            return Respuesta([{"universe": [{"name": "BTC", "szDecimals": 5}]}, [{"markPx": str(self.marca)}]])
        if t == "fundingHistory":
            base = int(self.ahora // 3600) * 3600
            return Respuesta([{"coin": "BTC", "fundingRate": str(self.tasa), "premium": "0", "time": (base - h * 3600) * 1000}
                              for h in range(79, -1, -1)])
        if t == "l2Book":
            mid = self.marca if json["coin"] == "BTC" else self.spot
            niv = lambda lado: [{"px": str(mid * (1 + lado * (0.00005 + 0.00005 * i))), "sz": "5", "n": 3} for i in range(8)]
            return Respuesta({"levels": [niv(-1), niv(1)]})
        raise AssertionError(f"consulta inesperada: {t}")


class CarryMotor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = self.tmp.name
        self.ahora = 1_800_000_000.0
        os.makedirs(os.path.join(self.raiz, "datos_mercado"))
        self.escribir("config.json", {"modo": "simulado"})
        self.escribir("datos_mercado/spot_hl.json", {
            "generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.ahora)),
            "aptas": {"BTC": {"par": "UBTC/USDC", "token": "UBTC", "sz_decimals": 5, "mid": 100020.0, "vol_24h_usd": 5e7}}})

    def escribir(self, nombre, datos):
        with open(os.path.join(self.raiz, nombre), "w", encoding="utf-8") as fh:
            json.dump(datos, fh)

    def motor(self, **api):
        self.api = ApiFalsa(self.ahora, **api)
        self.reloj = [self.ahora]
        return MotorCarry(self.raiz, post=self.api, reloj=lambda: self.reloj[0], esperar=lambda s: None)

    def test_libro_simple(self):
        self.assertEqual(libro_simple({"levels": [[{"px": "9", "sz": "2"}], [{"px": "10", "sz": "1"}]]}), {"compras": [(9.0, 2.0)], "ventas": [(10.0, 1.0)]})
        self.assertEqual(libro_simple({}), {"compras": [], "ventas": []})

    def test_abre_las_dos_patas_con_funding_alto(self):
        m = self.motor()
        r = m.pasada()
        self.assertEqual(r["estado"], "activo")
        self.assertEqual(len(r["posiciones"]), 1, r["descartadas"])
        p = r["posiciones"][0]
        self.assertEqual(p["coin"], "BTC")
        self.assertAlmostEqual(p["notional_usd"], 26.67, delta=1.0)           # 40 $ por moneda -> 26,67 por pata con apalancamiento 2
        self.assertIn("BTC", m.cartera["perp"])
        self.assertGreater(m.spot.cantidad("BTC"), 0)
        self.assertAlmostEqual(m.spot.cantidad("BTC"), m.cartera["perp"]["BTC"]["sz"], places=4)
        # equity ≈ cuenta menos los costes de entrada (nunca de más)
        self.assertLess(r["cuenta"]["equity_usd"], 200.0)
        self.assertGreater(r["cuenta"]["equity_usd"], 199.0)

    def test_estado_a_disco_y_cartera_persisten(self):
        m = self.motor()
        m.pasada()
        self.assertTrue(os.path.exists(os.path.join(self.raiz, "carry_estado.json")))
        otro = MotorCarry(self.raiz, post=self.api, reloj=lambda: self.reloj[0], esperar=lambda s: None)
        self.assertIn("BTC", otro.cartera["posiciones"])
        self.assertIn("BTC", otro.cartera["perp"])

    def test_sin_funding_suficiente_no_abre(self):
        m = self.motor(tasa=0.000001)
        r = m.pasada()
        self.assertEqual(r["posiciones"], [])
        self.assertIn("BTC", r["descartadas"])

    def test_cobra_funding_real_y_no_dos_veces(self):
        m = self.motor()
        m.pasada()
        self.reloj[0] += 3 * 3600
        self.api.ahora = self.reloj[0]
        m._cache_funding.clear()
        r = m.pasada()
        cobrado = r["posiciones"][0]["funding_usd"]
        self.assertGreater(cobrado, 0)
        r2 = m.pasada()                                           # misma hora: no se vuelve a cobrar
        self.assertAlmostEqual(r2["posiciones"][0]["funding_usd"], cobrado, places=6)

    def test_cierra_cuando_el_funding_se_hunde(self):
        m = self.motor()
        m.pasada()
        self.reloj[0] += 20 * 3600
        self.api.ahora, self.api.tasa = self.reloj[0], 0.0
        m._cache_funding.clear()
        r = m.pasada()
        self.assertEqual(r["posiciones"], [])
        self.assertEqual(r["resumen"]["n_cerradas"], 1)
        self.assertEqual(m.cartera["perp"], {})
        self.assertEqual(m.spot.d["monedas"], {})
        self.assertLess(abs(r["cuenta"]["equity_usd"] - 200.0), 3.0)          # solo costes y base: no se pierde la cuenta
        tipos = [e["tipo"] for e in m.registro.leer()]
        self.assertIn("carry_apertura", tipos)
        self.assertIn("carry_cierre", tipos)

    def test_se_niega_si_el_bot_no_esta_en_simulado(self):
        for modo in ("real", "shadow", None):
            self.escribir("config.json", {"modo": modo})
            r = self.motor().pasada()
            self.assertEqual(r["estado"], "parado")
            self.assertEqual(self.api.llamadas, [])                 # ni siquiera lee la red
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "papel_carry.json")))

    def test_apagado_por_config(self):
        self.escribir("carry_config.json", {"activo": False})
        self.assertEqual(self.motor().pasada()["estado"], "apagado")

    def test_una_posicion_por_moneda(self):
        m = self.motor()
        m.pasada()
        r = m.pasada()
        self.assertEqual(len(r["posiciones"]), 1)
        self.assertEqual(len(m.registro.leer()), 1)


if __name__ == "__main__":
    unittest.main()
