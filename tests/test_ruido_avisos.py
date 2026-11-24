"""Control de ruido de los avisos de Telegram (17/11/2026): menos repeticiones, nunca callar lo importante."""

import unittest
from datetime import datetime

import configuracion as conf
from notificaciones import ControlRuido, Telegram
from tests.comunes import config


def ts(hora, minuto=0):
    return datetime(2026, 11, 17, hora, minuto).timestamp()     # hora local del equipo (sin zona)


class Ruido(unittest.TestCase):
    def test_no_repite_el_mismo_texto(self):
        r = ControlRuido(dedup_min=10)
        self.assertTrue(r.permitir("abre BTC", "info", ts(12)))
        self.assertFalse(r.permitir("abre BTC", "info", ts(12, 5)))
        self.assertTrue(r.permitir("abre ETH", "info", ts(12, 5)))
        self.assertTrue(r.permitir("abre BTC", "info", ts(12, 11)))       # pasado el plazo, vuelve a avisar

    def test_respuestas_a_comandos_siempre_pasan(self):
        r = ControlRuido(dedup_min=10, silencio="00:00-23:59")
        for _ in range(3):
            self.assertTrue(r.permitir("Pausado.", "respuesta", ts(3)))

    def test_silencio_solo_calla_lo_informativo(self):
        r = ControlRuido(dedup_min=0, silencio="23:30-07:30")
        self.assertFalse(r.permitir("info", "info", ts(2)))
        self.assertTrue(r.permitir("stop sin confirmar", "aviso", ts(2)))
        self.assertTrue(r.permitir("error de conexión", "error", ts(2)))
        self.assertTrue(r.permitir("info", "info", ts(12)))
        self.assertFalse(r.permitir("info", "info", ts(23, 45)))           # cruza medianoche

    def test_silencio_vacio_o_invalido_no_calla(self):
        for s in ("", "08:00-08:00", "25:00-01:00"):
            self.assertFalse(ControlRuido(silencio=s).en_silencio(ts(3)), s)

    def test_telegram_sin_token_no_envia_ni_falla(self):
        tg = Telegram(None, None)
        tg.enviar("hola", "aviso")
        self.assertTrue(tg.cola.empty())

    def test_validacion_de_config(self):
        self.assertEqual(conf.DEFECTOS["avisos"]["silencio"], "")
        c = config()
        c["avisos"]["silencio"] = "23-7"
        with self.assertRaises(Exception):
            conf.validar(c, entorno={})


if __name__ == "__main__":
    unittest.main()
