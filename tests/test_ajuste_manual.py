"""Ajuste manual de stop y objetivo desde el panel (14/11/2026, pedido por Roberto): solo simulado, solo del bot, sin
ampliar el riesgo aprobado. Con la cuenta simulada, sin red."""

import unittest
from types import SimpleNamespace

import bot
from tests.test_gestor import Base


def tps_vivos(papel, moneda):
    return [o for o in papel.d["ordenes"] if o["coin"] == moneda and o["tipo"] == "limite" and o["reduce_only"]]


class Stop(Base):
    def test_acerca_el_stop_y_deja_uno_solo(self):
        op = self.gestor.abrir(self.plan())
        px = self.m.precios["ETH"]
        nuevo = round((op["sl"] + px) / 2, 2)
        ok, msg = self.gestor.ajustar_manual(op, "stop", nuevo)
        self.assertTrue(ok, msg)
        self.assertAlmostEqual(op["sl"], nuevo, places=1)
        self.assertEqual(len(self.stops("ETH")), 1)                     # el viejo se cancela tras verificar el nuevo
        self.assertEqual(op["ajustes_manuales"][-1]["tipo"], "stop")

    def test_no_amplia_el_riesgo_mas_alla_del_stop_inicial(self):
        op = self.gestor.abrir(self.plan())
        viejo = op["sl"]
        ok, msg = self.gestor.ajustar_manual(op, "stop", op["sl_inicial"] * 0.99)
        self.assertFalse(ok)
        self.assertIn("inicial", msg)
        self.assertEqual(op["sl"], viejo)

    def test_stop_al_otro_lado_del_precio_se_rechaza_y_el_anterior_sigue(self):
        op = self.gestor.abrir(self.plan())
        viejo, n = op["stop_cloid"], len(self.papel.d["ordenes"])
        ok, _ = self.gestor.ajustar_manual(op, "stop", self.m.precios["ETH"] * 1.01)
        self.assertFalse(ok)
        self.assertEqual((op["stop_cloid"], len(self.papel.d["ordenes"])), (viejo, n))

    def test_corto_sube_el_stop_hacia_ganancia_sin_pasar_al_otro_lado(self):
        op = self.gestor.abrir(self.plan(lado="S"))
        px = self.m.precios["ETH"]
        ok, msg = self.gestor.ajustar_manual(op, "stop", px * 1.005)    # un poco por encima del precio: válido
        self.assertTrue(ok, msg)
        ok, _ = self.gestor.ajustar_manual(op, "stop", px * 0.99)       # por debajo de un corto: saltaría al instante
        self.assertFalse(ok)

    def test_operacion_cerrada_o_congelada_no_se_toca(self):
        op = self.gestor.abrir(self.plan())
        self.gestor.ej.congelar("ETH", "prueba", "ambigua", op["trade_id"])
        self.assertFalse(self.gestor.ajustar_manual(op, "stop", self.m.precios["ETH"] * 0.99)[0])
        op["estado"] = "cerrada"
        self.assertFalse(self.gestor.ajustar_manual(op, "tp", self.m.precios["ETH"] * 1.05)[0])


class Objetivo(Base):
    def test_cambia_el_objetivo_final_y_no_duplica(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        antes = len(tps_vivos(self.papel, "ETH"))
        nuevo = round(self.m.precios["ETH"] * 1.08, 2)
        ok, msg = self.gestor.ajustar_manual(op, "tp", nuevo)
        self.assertTrue(ok, msg)
        self.assertEqual(op["tpf"], nuevo)
        self.assertEqual(len(tps_vivos(self.papel, "ETH")), antes)       # cancela el final anterior y pone el nuevo
        self.gestor.conciliar(self.m.precios)
        self.assertEqual(len(tps_vivos(self.papel, "ETH")), antes)       # la conciliación no lo duplica

    def test_objetivo_del_lado_de_la_perdida_se_rechaza(self):
        op = self.gestor.abrir(self.plan())
        antes = len(tps_vivos(self.papel, "ETH"))
        ok, _ = self.gestor.ajustar_manual(op, "tp", self.m.precios["ETH"] * 0.99)
        self.assertFalse(ok)
        self.assertEqual(len(tps_vivos(self.papel, "ETH")), antes)

    def test_quitar_el_objetivo(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        ok, _ = self.gestor.ajustar_manual(op, "tp", None)
        self.assertTrue(ok)
        self.assertIsNone(op["tpf"])
        self.gestor.conciliar(self.m.precios)
        self.assertFalse([o for o in tps_vivos(self.papel, "ETH") if o["px"] > self.m.precios["ETH"] * 1.0001 and
                          o["sz"] >= op["tam"] - 1e-9])                  # no se repone solo

    def test_operacion_sin_objetivo_admite_uno_manual(self):
        plan = self.plan(tam=0.05)
        plan["salida"] = dict(plan["salida"], parcial_activo=False, sin_objetivo=True, tp1_r=98, tp_final_r=99)
        op = self.gestor.abrir(plan)
        self.assertIsNone(op["tpf"])
        self.assertEqual(len(tps_vivos(self.papel, "ETH")), 0)
        ok, msg = self.gestor.ajustar_manual(op, "tp", round(self.m.precios["ETH"] * 1.06, 2))
        self.assertTrue(ok, msg)
        self.assertEqual(len(tps_vivos(self.papel, "ETH")), 1)
        self.assertFalse(op["salida"]["sin_objetivo"])
        self.gestor.conciliar(self.m.precios)
        self.assertEqual(len(tps_vivos(self.papel, "ETH")), 1)


class ComandoDelBot(unittest.TestCase):
    """bot.Bot.ajuste_manual con un Bot de pega: solo importan el origen, el modo y el precio."""

    class Gestor:
        def __init__(self):
            self.llamadas = []

        def ajustar_manual(self, op, tipo, precio):
            self.llamadas.append((tipo, precio))
            return True, "hecho"

    def bot(self, modo="simulado", con_op=True):
        g = self.Gestor()
        return SimpleNamespace(modo=modo, gestor=g, estado={"posiciones": {"ETH": {"moneda": "ETH"}} if con_op else {}},
                               guardar=lambda: None), g

    def pedir(self, falso, **c):
        return bot.Bot.ajuste_manual(falso, {"cmd": "/stopmanual", "moneda": "ETH", "precio": 1.0, "origen": "panel", **c})

    def test_solo_desde_el_panel(self):
        falso, g = self.bot()
        ok, _ = self.pedir(falso, origen="telegram")
        self.assertFalse(ok)
        self.assertEqual(g.llamadas, [])

    def test_solo_en_simulado(self):
        for modo in ("shadow", "real"):
            falso, g = self.bot(modo)
            self.assertFalse(self.pedir(falso)[0], modo)
            self.assertEqual(g.llamadas, [])

    def test_solo_posiciones_del_bot(self):
        falso, g = self.bot(con_op=False)
        self.assertFalse(self.pedir(falso)[0])
        self.assertEqual(g.llamadas, [])

    def test_precios_no_validos(self):
        for malo in ("abc", float("nan"), float("inf"), -3, 0, True):
            falso, g = self.bot()
            self.assertFalse(self.pedir(falso, precio=malo)[0], repr(malo))
            self.assertEqual(g.llamadas, [])

    def test_pasa_lo_valido_y_distingue_stop_de_objetivo(self):
        falso, g = self.bot()
        self.assertTrue(self.pedir(falso, precio=5.5)[0])
        self.assertTrue(self.pedir(falso, cmd="/tpmanual", precio=None)[0])
        self.assertEqual(g.llamadas, [("stop", 5.5), ("tp", None)])


if __name__ == "__main__":
    unittest.main()
