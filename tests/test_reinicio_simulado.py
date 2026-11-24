"""Puesta a cero de la cuenta SIMULADA: solo en simulado, con archivo de lo anterior, sin tocar el ledger, y nunca
con posiciones u órdenes abiertas."""

import json
import os
from unittest import mock

from tests.comunes import ConCarpeta, config


class ReinicioSimulado(ConCarpeta):
    def setUp(self):
        super().setUp()
        import bot
        self.bot = bot
        self.rutas = {k: os.path.join(self.dir, os.path.basename(getattr(bot, k)))
                      for k in ("RUTA_PAPEL", "RUTA_ESTADO", "RUTA_REINICIO_SIMULADO")}
        self.parches = [mock.patch.object(bot, k, v) for k, v in self.rutas.items()] + \
            [mock.patch.object(bot, "AQUI", self.dir),
             mock.patch.object(bot, "DIR_REINICIOS", os.path.join(self.dir, "archivo_reinicios"))]
        for p in self.parches:
            p.start()
        self.escribir("RUTA_PAPEL", {"efectivo": 221.9, "saldo_inicial": 232, "posiciones": {}, "ordenes": [],
                                     "fills": [{"px": "1"}]})
        self.escribir("RUTA_ESTADO", {"modo": "simulado", "saldo_inicial": 232, "saldo_maximo": 232.3,
                                      "saldo_inicio_dia": 222.7, "perdidas_seguidas": 3, "pausa_hasta": 9e9,
                                      "agenda": {"lab": 1}, "cloids_propios": {"0x1": {}}, "historial_saldo": [[1, 230]]})
        self.escribir("RUTA_REINICIO_SIMULADO", {"pedido": "prueba"})

    def tearDown(self):
        for p in self.parches:
            p.stop()
        super().tearDown()

    def escribir(self, k, d):
        with open(self.rutas[k], "w", encoding="utf-8") as fh:
            json.dump(d, fh)

    def test_pone_a_cero_y_archiva(self):
        self.assertTrue(self.bot.reiniciar_simulado(config(saldo_simulado_usd=232)))
        self.assertFalse(os.path.exists(self.rutas["RUTA_PAPEL"]))          # se crea de nuevo con el saldo inicial
        self.assertFalse(os.path.exists(self.rutas["RUTA_REINICIO_SIMULADO"]))
        with open(self.rutas["RUTA_ESTADO"], encoding="utf-8") as fh:
            e = json.load(fh)
        self.assertEqual(e, {"agenda": {"lab": 1}, "cloids_propios": {"0x1": {}}, "modo": "simulado"})
        archivo = os.path.join(self.dir, "archivo_reinicios")
        copia = os.path.join(archivo, os.listdir(archivo)[0])
        self.assertEqual(sorted(os.listdir(copia)), ["estado.json", "papel.json", "reiniciar_simulado.json"])
        from papel import CuentaPapel
        from tests.comunes import MercadoFalso
        cta = CuentaPapel(MercadoFalso(), self.rutas["RUTA_PAPEL"], 232, 0.00015, 0.00045)
        self.assertEqual((cta.d["efectivo"], cta.d["posiciones"]), (232, {}))

    def test_nunca_en_real_ni_shadow(self):
        for modo in ("real", "shadow"):
            c = config()
            c["modo"] = modo
            self.assertFalse(self.bot.reiniciar_simulado(c))
        self.assertTrue(os.path.exists(self.rutas["RUTA_PAPEL"]))

    def test_con_posiciones_abiertas_no_se_aplica(self):
        self.escribir("RUTA_PAPEL", {"efectivo": 200, "posiciones": {"ETH": {"szi": 0.1}}, "ordenes": []})
        self.assertFalse(self.bot.reiniciar_simulado(config()))
        self.assertTrue(os.path.exists(self.rutas["RUTA_REINICIO_SIMULADO"]))  # la petición queda pendiente

    def test_sin_peticion_no_hace_nada(self):
        os.remove(self.rutas["RUTA_REINICIO_SIMULADO"])
        self.assertFalse(self.bot.reiniciar_simulado(config()))
