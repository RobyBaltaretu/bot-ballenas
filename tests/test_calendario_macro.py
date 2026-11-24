import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

import calendario_macro as cal


class Calendario(unittest.TestCase):
    def test_horas_de_nueva_york_con_y_sin_horario_de_verano(self):
        h = lambda f, t: datetime.fromtimestamp(cal.a_utc(f, t), timezone.utc).strftime("%H:%M")
        self.assertEqual(h("2026-10-28", "fomc"), "18:00")       # verano en Nueva York
        self.assertEqual(h("2026-12-09", "fomc"), "19:00")
        self.assertEqual(h("2026-11-10", "cpi"), "13:30")        # ya en horario de invierno (1 nov 2026)
        self.assertEqual(h("2026-03-11", "cpi"), "12:30")        # verano desde el 8 mar 2026

    def test_archivo_real_y_ventana(self):
        ev = cal.cargar()
        self.assertGreater(len(ev), 150)
        self.assertNotIn("2020-03-15", [f for _, _, f in ev])     # urgencia: no se sabía antes
        self.assertIn("2020-03-15", [f for _, _, f in cal.cargar(programadas=False)])
        t = cal.a_utc("2026-10-28", "fomc")
        self.assertEqual(cal.en_ventana(t - 11 * 3600, ev, 12, 2), "fomc")
        self.assertEqual(cal.en_ventana(t + 1.5 * 3600, ev, 12, 2), "fomc")
        self.assertIsNone(cal.en_ventana(t + 3 * 3600, ev, 12, 2))
        self.assertEqual([p["fecha"] for p in cal.proximas(t - 86400, ev, 2)], ["2026-10-28"])

    def test_ola_btc_y_oleaje_normal(self):
        t = cal.a_utc("2026-10-28", "fomc")                     # 18:00 UTC
        base = int(t // 3600 * 3600) - 3600                     # vela de 17:00
        velas = [{"t": (base + k * 3600) * 1000, "o": 100, "h": 101 + (k > 0) * 2, "l": 99, "c": 100 + max(0, k)}
                 for k in range(-12, 13)]
        o = cal.ola_btc(velas, t)
        self.assertEqual(o["mov_4h_pct"], 4.0)                  # cierre de la 4.ª vela tras la cita: 104
        self.assertAlmostEqual(o["rango_4h_pct"], 4.0)          # máximo 103 − mínimo 99, sobre 100
        self.assertEqual(o["serie"][12], [0.0, 0.0])            # la vela previa termina justo en la cita
        self.assertIsNone(cal.ola_btc(velas[:14], t))           # faltan velas después: no se inventa
        self.assertIsNotNone(cal.oleaje_normal(velas))
        self.assertIsNone(cal.oleaje_normal([]))

    def test_ventana_igual_que_el_estudio(self):
        import investigacion
        self.assertEqual(tuple(investigacion.ESTUDIO_MACRO_VENTANA), cal.VENTANA_H)

    def test_fechas_validas_y_ordenadas(self):
        with open(cal.RUTA, encoding="utf-8") as fh:
            d = json.load(fh)
        for tipo in ("fomc", "cpi"):
            fechas = [e["fecha"] for e in d[tipo]]
            self.assertEqual(fechas, sorted(fechas))
            for f in fechas:
                datetime.strptime(f, "%Y-%m-%d")


if __name__ == "__main__":
    unittest.main()
