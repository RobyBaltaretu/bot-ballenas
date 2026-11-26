"""CP-M17 (auditoría 26/11/2026, T-13): curva de valor diaria completa desde la puesta a cero."""
import os
import unittest
from datetime import datetime, timezone

import curva_valor as cv
from tests.comunes import ConCarpeta


def ts(txt):
    return datetime.strptime(txt, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()


def iso(txt):
    return datetime.fromtimestamp(ts(txt), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Reconstruir(unittest.TestCase):
    def test_un_punto_por_dia_desde_la_puesta_a_cero(self):
        inicio = ts("2026-10-28 22:44")
        cierres = [(ts("2026-10-29 10:00"), 5.0), (ts("2026-10-30 12:00"), -2.0), (ts("2026-10-27 09:00"), 99.0)]
        historial = [[ts("2026-11-01 00:03"), 240.0], [ts("2026-11-01 08:00"), 241.0]]
        puntos = cv.reconstruir(inicio, 232.0, cierres, historial, ts("2026-11-02 05:00"))
        self.assertEqual([p["dia"] for p in puntos],
                         ["2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"])
        valores = [p["equity"] for p in puntos]
        self.assertEqual(valores[:4], [232.0, 232.0, 237.0, 235.0])     # el cierre de antes de la puesta a cero no cuenta
        self.assertEqual(puntos[4]["equity"], 240.0)                      # primer punto real de ese día
        self.assertEqual([p["fuente"] for p in puntos], ["ledger_realizado"] * 4 + ["historial_saldo"])
        self.assertTrue(all(p["cuenta_desde"] == "2026-10-28T22:44:00Z" for p in puntos))

    def test_cierres_del_ledger(self):
        eventos = [{"tipo": "cierre", "ts": iso("2026-10-29 10:00"), "pnl_neto": 1.5},
                   {"tipo": "cierre", "ts": iso("2026-10-29 11:00"), "pnl_neto": None},   # contabilidad incompleta
                   {"tipo": "fill", "ts": iso("2026-10-29 12:00"), "pnl_neto": 7}]
        self.assertEqual(cv.cierres_del_ledger(eventos), [(ts("2026-10-29 10:00"), 1.5)])


class Registrar(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.ruta = os.path.join(self.dir, "registro", cv.ARCHIVO)

    def test_rellena_al_crear_y_luego_un_punto_al_dia(self):
        inicio = ts("2026-11-20 10:00")
        eventos = [{"tipo": "cierre", "ts": iso("2026-11-21 10:00"), "pnl_neto": 3.0}]
        nuevos = cv.registrar(self.ruta, ts("2026-11-23 01:00"), 236.5, inicio, 232.0, lambda: eventos, [])
        self.assertEqual([p["dia"] for p in nuevos], ["2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23"])
        self.assertEqual(nuevos[-1]["fuente"], "equity")
        self.assertEqual(cv.registrar(self.ruta, ts("2026-11-23 20:00"), 240.0, inicio, 232.0, lambda: 1 / 0, []), [])
        leidos = cv.registrar(self.ruta, ts("2026-11-25 00:10"), 241.0, inicio, 232.0, lambda: 1 / 0, [])
        self.assertEqual([p["dia"] for p in leidos], ["2026-11-25"])       # el día sin bot queda como hueco
        self.assertEqual(len(cv.leer(self.ruta)), 5)

    def test_una_puesta_a_cero_nueva_no_borra_la_anterior(self):
        cv.registrar(self.ruta, ts("2026-11-23 01:00"), 236.5, ts("2026-11-22 10:00"), 232.0, [], [])
        cv.registrar(self.ruta, ts("2026-11-25 01:00"), 500.0, ts("2026-11-25 00:30"), 500.0, [], [])
        puntos = cv.leer(self.ruta)
        self.assertEqual(len({p["cuenta_desde"] for p in puntos}), 2)
        self.assertEqual(puntos[0]["dia"], "2026-11-22")                  # lo anterior sigue ahí
        self.assertEqual(puntos[-1]["equity"], 500.0)

    def test_sin_valor_no_escribe(self):
        self.assertEqual(cv.registrar(self.ruta, ts("2026-11-23 01:00"), None, 0, None, [], []), [])
        self.assertFalse(os.path.exists(self.ruta))


if __name__ == "__main__":
    unittest.main()
