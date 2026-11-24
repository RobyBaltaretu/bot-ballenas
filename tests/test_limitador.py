"""Presupuesto de peso de Hyperliquid: pesos documentados, peso extra por elementos devueltos, reintentos que
cuentan y un único presupuesto compartido dentro del proceso del bot."""

import unittest
from unittest import mock

import limitador as lm


class Pesos(unittest.TestCase):
    def test_pesos_base_documentados(self):
        self.assertEqual(lm.peso({"type": "l2Book"}), 2)
        self.assertEqual(lm.peso({"type": "userRole"}), 60)
        self.assertEqual(lm.peso({"type": "userFills"}), 20)
        self.assertEqual(lm.peso({"type": "candleSnapshot"}), 20)
        self.assertEqual(lm.peso({"type": "desconocido"}), 20)

    def test_peso_extra_por_elementos(self):
        self.assertEqual(lm.peso_extra({"type": "userFills"}, [{}] * 2000), 100)
        self.assertEqual(lm.peso_extra({"type": "userFillsByTime"}, [{}] * 39), 1)
        self.assertEqual(lm.peso_extra({"type": "candleSnapshot"}, [{}] * 300), 5)
        self.assertEqual(lm.peso_extra({"type": "l2Book"}, [{}] * 300), 0)
        self.assertEqual(lm.peso_extra({"type": "userFills"}, {"no": "lista"}), 0)

    def test_envolver_anota_el_extra_y_cada_reintento_cuenta(self):
        lim = lm.Limitador(presupuesto=10_000)
        llamadas = []

        class Info:
            def post(self, ruta, cuerpo=None):
                llamadas.append(1)
                if len(llamadas) == 1:
                    raise RuntimeError("429 Too Many Requests")
                return [{}] * 200
        info = lim.envolver(Info())
        with mock.patch("limitador.time.sleep"):
            info.post("/info", {"type": "userFills", "user": "x"})
        self.assertEqual(lim.reintentos_429, 1)
        self.assertEqual(lim.usado(), 20 + 20 + 10)              # dos intentos + extra por 200 fills

    def test_api_del_proceso_del_bot_usa_el_limitador_compartido(self):
        import datos
        lim = lm.Limitador(presupuesto=10_000)
        with mock.patch.object(lm, "COMPARTIDO", lim), mock.patch.object(datos.Api, "limpiar_cache"), \
                mock.patch("datos.os.makedirs"):
            api = datos.Api(usar_cache=False)          # sin tocar la caché real de datos_backtest/
            self.assertIs(api.compartido, lim)
            resp = mock.Mock(status_code=200, json=lambda: [{}] * 40)
            resp.raise_for_status = lambda: None
            with mock.patch("datos.requests.post", return_value=resp):
                api.post({"type": "fundingHistory", "coin": "ETH"}, peso=20, cache=False)
        self.assertEqual(lim.usado(), 22)

    def test_otro_proceso_con_el_bot_en_marcha_usa_solo_lo_que_queda(self):
        import datos
        with mock.patch("datos.os.path.exists", return_value=True):
            self.assertLessEqual(datos.presupuesto_por_defecto() + lm.PRESUPUESTO_MINUTO, lm.LIMITE_IP)
        with mock.patch("datos.os.path.exists", return_value=False):
            self.assertEqual(datos.presupuesto_por_defecto(), 1000)
