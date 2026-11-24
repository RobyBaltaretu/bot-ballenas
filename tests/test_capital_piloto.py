"""A-11: un cambio de capital nunca eleva límites; los topes del piloto son absolutos y auditables; un saldo de
~200 € no activa ningún piloto ni evita que el mínimo de Hyperliquid o los costes excedan lo aprobado."""

import copy
import types
import unittest

import riesgo as rg
from tests.comunes import config


class Capital(unittest.TestCase):
    def test_deposito_desplaza_referencias_sin_tocar_limites(self):
        c = config()
        antes = (copy.deepcopy(rg.limites_efectivos(c)), copy.deepcopy(c["piloto_real"]))
        estado = {"saldo_inicial": 58.0, "saldo_inicio_dia": 58.0, "saldo_inicio_semana": 58.0, "saldo_maximo": 60.0,
                  "dia": "2026-10-28", "semana": "2026-W44", "historial_saldo": [[1, 58.0]]}
        delta = rg.rebasar_capital(estado, 232.0, ts_cambio=2)
        self.assertEqual(delta, 174.0)
        self.assertEqual((rg.limites_efectivos(c), c["piloto_real"]), antes)
        aj = estado["ajustes_capital"][-1]
        self.assertEqual((aj["anterior"], aj["nuevo"], aj["tipo"], aj["limites_modificados"]),
                         (58.0, 232.0, "deposito", False))
        # Un depósito no es beneficio: no dispara «objetivo diario» ni desbloquea pérdidas.
        self.assertEqual(rg.bloqueos_duros(estado, 232.0, c), [])

    def test_retirada_y_valores_raros(self):
        estado = {"saldo_inicial": 232.0, "saldo_maximo": 240.0}
        self.assertLess(rg.rebasar_capital(estado, 100.0), 0)
        self.assertEqual(estado["ajustes_capital"][-1]["tipo"], "retirada")
        self.assertEqual(rg.rebasar_capital({"saldo_inicial": None}, 100.0), 0.0)
        self.assertEqual(rg.rebasar_capital({"saldo_inicial": 50.0}, None), 0.0)
        c = config()
        for eq in (None, 0, -10):
            self.assertFalse(rg.dimensionar(eq, 10, 100.0, 2.0, 3, 20, c)["ok"])
            self.assertEqual(rg.bloqueos_duros({}, eq, c), ["valor de la cuenta desconocido"])

    def test_en_real_el_capital_usado_nunca_supera_el_tope_del_piloto(self):
        import bot
        c = config()
        c["modo"] = "real"
        for saldo in (40.0, 232.0, 10_000.0):
            falso = types.SimpleNamespace(modo="real", c=c, gestor=types.SimpleNamespace(
                ultima_cuenta={"equity": saldo, "libre": saldo}))
            eq, libre = bot.Bot.equity(falso)
            self.assertLessEqual(eq, c["piloto_real"]["capital_max_usd"])
            self.assertLessEqual(libre, c["piloto_real"]["capital_max_usd"])
        self.assertEqual(bot.Bot.equity(types.SimpleNamespace(modo="real", c=c, gestor=types.SimpleNamespace(
            ultima_cuenta=None))), (None, None))            # sin lectura reconciliada: desconocido

    def test_saldo_de_200_euros_no_activa_nada(self):
        c = config(saldo_simulado_usd=232)
        self.assertEqual(c["modo"], "simulado")
        self.assertFalse(c["real"]["habilitado"])
        self.assertEqual(rg.limites_efectivos(c)["riesgo_por_operacion_pct"], c["riesgo"]["riesgo_por_operacion_pct"])

    def test_minimo_de_hyperliquid_y_costes_con_poco_capital(self):
        c = config()
        c["modo"] = "real"
        lim = rg.limites_efectivos(c)                        # piloto: 0,5 % por operación
        self.assertEqual(lim["riesgo_por_operacion_pct"], min(c["riesgo"]["riesgo_por_operacion_pct"], 0.5))
        d = rg.dimensionar(50.0, 50.0, 100.0, 5.0, 2, 20, c, limites=lim)
        self.assertFalse(d["ok"])                             # la orden mínima de 10 USD arriesgaría más de 0,25 USD
        self.assertIn("tamaño mínimo excede riesgo", d["motivo"])
