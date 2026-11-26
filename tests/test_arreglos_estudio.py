"""Arreglos del estudio del 19/11/2026: funding con su hora real, stop disparado sin llenar del todo, entradas límite
del simulador (MODELO 3) y libro agregado para stops en monedas poco líquidas."""

import os
import time
import unittest

from ledger import Ledger, iso_ms
from tests.comunes import ConCarpeta, MercadoFalso, mover, nuevo_papel
from tests.test_gestor import Base


class DiferencialAbierto(MercadoFalso):
    """Libro con el diferencial muy abierto: el precio medio puede cruzar nuestra orden sin que nadie opere a ese
    precio. Velas de 1 min configurables."""

    def __init__(self):
        super().__init__()
        self.bid_ask = {}
        self.velas = []

    def l2_snapshot(self, moneda):
        if moneda in self.bid_ask:
            b, a = self.bid_ask[moneda]
            return {"levels": [[{"px": str(b), "sz": "1000"}], [{"px": str(a), "sz": "1000"}]]}
        return super().l2_snapshot(moneda)

    def candles_snapshot(self, moneda, intervalo, desde, hasta):
        return [v for v in self.velas if v["t"] >= desde]


class EntradasLimite(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.m = DiferencialAbierto()
        self.papel, _ = nuevo_papel(self.dir, self.m)

    def test_medio_que_cruza_sin_contrapartida_no_llena(self):
        self.papel.order("ETH", True, 0.01, 3990.0, {"limit": {"tif": "Alo"}})
        mover(self.papel, self.m, "ETH", 3985.0)                   # el medio pasa por debajo de 3990...
        self.m.bid_ask["ETH"] = (3970.0, 4000.0)                   # ...pero nadie vende a 3990 o menos
        self.papel.procesar()
        self.assertNotIn("ETH", self.papel.d["posiciones"])

    def test_contrapartida_en_el_libro_llena_como_maker(self):
        self.papel.order("ETH", True, 0.01, 3990.0, {"limit": {"tif": "Alo"}})
        mover(self.papel, self.m, "ETH", 3989.0)
        self.m.bid_ask["ETH"] = (3988.0, 3989.5)                   # hay vendedores por debajo de nuestro precio
        self.papel.procesar()
        self.assertIn("ETH", self.papel.d["posiciones"])
        self.assertFalse(self.papel.d["fills"][-1]["crossed"])

    def test_mecha_entre_comprobaciones_llena_por_las_velas(self):
        self.papel.order("ETH", True, 0.01, 3990.0, {"limit": {"tif": "Alo"}})
        siguiente = (int(time.time() * 1000) // 60_000 + 1) * 60_000
        self.m.velas = [{"t": siguiente, "l": "3985.0", "h": "4001.0"}]   # se operó por debajo de 3990
        self.papel.procesar()
        self.assertIn("ETH", self.papel.d["posiciones"])

    def test_vela_que_empezo_antes_de_la_orden_no_cuenta(self):
        self.papel.order("ETH", True, 0.01, 3990.0, {"limit": {"tif": "Alo"}})
        actual = (int(time.time() * 1000) // 60_000) * 60_000
        self.m.velas = [{"t": actual, "l": "3900.0", "h": "4001.0"}]      # su mínimo pudo ser antes de la orden
        self.papel.procesar()
        self.assertNotIn("ETH", self.papel.d["posiciones"])


class LibroProfundo(MercadoFalso):
    """20 niveles visibles muy finos; el libro agregado llega más lejos con liquidez."""

    def l2_snapshot(self, moneda):
        px = self.precios[moneda]
        bids = [{"px": str(px * (1 - 0.0001 * (k + 1))), "sz": "0.001"} for k in range(20)]
        asks = [{"px": str(px * (1 + 0.0001 * (k + 1))), "sz": "0.001"} for k in range(20)]
        return {"levels": [bids, asks]}

    def post(self, ruta, datos):
        px = self.precios[datos["coin"]]
        bids = [{"px": str(px * (1 - 0.005 * (k + 1))), "sz": "1"} for k in range(5)]
        asks = [{"px": str(px * (1 + 0.005 * (k + 1))), "sz": "1"} for k in range(5)]
        return {"levels": [bids, asks]}


class StopProfundo(ConCarpeta):
    def test_stop_usa_el_libro_agregado_si_el_visible_no_basta(self):
        m = LibroProfundo()
        papel, _ = nuevo_papel(self.dir, m)
        papel.order("ETH", True, 0.5, 4100.0, {"limit": {"tif": "Ioc"}})
        self.assertAlmostEqual(papel.d["posiciones"]["ETH"]["szi"], 0.5)      # la entrada también llega al agregado
        papel.order("ETH", False, 0.5, 3500.0, {"trigger": {"triggerPx": 3900.0, "isMarket": True, "tpsl": "sl"}},
                    reduce_only=True)
        mover(papel, m, "ETH", 3880.0)
        papel.procesar()
        self.assertNotIn("ETH", papel.d["posiciones"])                      # cerrado entero, no solo 0,02


class StopDisparadoParcial(Base):
    def test_el_resto_se_cierra_en_vez_de_quedar_sin_stop(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        original = self.papel._barrer
        veces = []

        def barrer_medio(moneda, compra, sz, limite, profundo=False):
            if not veces:                                          # el stop: el libro solo cubre la mitad
                veces.append(1)
                hecho, px = original(moneda, compra, sz / 2, limite, profundo)
                return hecho, px
            return original(moneda, compra, sz, limite, profundo)
        self.papel._barrer = barrer_medio
        mover(self.papel, self.m, "ETH", op["sl"] * 0.995)
        self.gestor.conciliar(self.m.precios)
        self.assertNotIn("ETH", self.papel.d["posiciones"])                 # no queda nada sin protección
        self.assertNotIn("ETH", self.estado["posiciones"])
        eventos = self.ledger.leer()[0]
        self.assertTrue(any(e["tipo"] == "proteccion" and e.get("accion") == "disparado_parcial" for e in eventos))
        cierre = [e for e in eventos if e["tipo"] == "cierre"][-1]
        self.assertIsNotNone(cierre["pnl_neto"])                            # contabilidad completa


class AmpliarGanadoras(Base):
    """Piramidar (19/11/2026, solo simulado): una vez, con el stop ya en la entrada; R contra el riesgo original."""

    def a_breakeven(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        self.assertIsNotNone(self.gestor.ampliable(op))                # recién abierta: todavía no
        mover(self.papel, self.m, "ETH", op["tp1"] * 1.001)          # cobra el objetivo 1 y pasa 1 R
        self.gestor.conciliar(self.m.precios)
        op = self.estado["posiciones"]["ETH"]
        self.gestor.gestionar(op, self.m.precios["ETH"])
        self.assertTrue(op["en_breakeven"])
        # CP-E06: tras el TP1 solo se amplía cuando el precio pasa el TP1 en 1 R más, en otro ciclo.
        mover(self.papel, self.m, "ETH", op["tp1"] + 1.05 * op["r_dist"])
        self.gestor.conciliar(self.m.precios)
        op = self.estado["posiciones"]["ETH"]
        self.gestor.gestionar(op, self.m.precios["ETH"])
        return op

    def test_amplia_una_vez_y_protege_el_tamano_nuevo(self):
        op = self.a_breakeven()
        self.assertIsNone(self.gestor.ampliable(op, self.m.precios["ETH"]))
        antes = op["tam"]
        añadido = self.gestor.ampliar(op, 0.025, "prueba")
        self.assertAlmostEqual(añadido, 0.025)
        self.assertAlmostEqual(op["tam"], antes + 0.025)
        self.assertAlmostEqual(self.papel.d["posiciones"]["ETH"]["szi"], antes + 0.025)
        st = self.stops("ETH")
        self.assertEqual(len(st), 1)
        self.assertAlmostEqual(st[0]["sz"], op["tam"])                  # el stop cubre TODO
        self.assertIn("ya ampliada", self.gestor.ampliable(op))         # nunca dos veces
        self.gestor.conciliar(self.m.precios)                          # la cuenta cuadra: sin congelar
        self.assertNotIn("ETH", self.gestor.ej.congelados)
        fills = [e for e in self.ledger.leer()[0] if e["tipo"] == "fill" and e.get("rol") == "ampliacion"]
        self.assertEqual(len(fills), 1)

    def test_al_cerrar_guarda_con_y_sin_ampliacion(self):
        op = self.a_breakeven()
        riesgo_original = op["riesgo_plan_usd"]
        self.gestor.ampliar(op, 0.025, "prueba")
        mover(self.papel, self.m, "ETH", op["sl"] * 0.995)            # vuelve al stop (en la entrada)
        self.gestor.conciliar(self.m.precios)
        self.assertNotIn("ETH", self.estado["posiciones"])
        cierre = [e for e in self.ledger.leer()[0] if e["tipo"] == "cierre"][-1]
        a = cierre["ampliacion"]
        self.assertTrue(a["estimado"])
        self.assertLess(a["pnl_ampliacion"], 0)                        # comprar arriba y salir en el stop pierde
        self.assertAlmostEqual(a["pnl_sin_ampliacion"] + a["pnl_ampliacion"], cierre["pnl_neto"], places=6)
        self.assertGreater(a["pnl_sin_ampliacion"], cierre["pnl_neto"])
        # 1 R = el riesgo de la entrada ORIGINAL (no se infla con la parte añadida)
        self.assertLess(cierre["riesgo_inicial_usd"], riesgo_original * 1.5)
        ops, _ = self.ledger.operaciones()
        o = ops[op["trade_id"]]
        self.assertEqual(o["ampliacion"]["tam"], a["tam"])
        self.assertTrue(o["fills_ampliacion"])

    def test_la_cartera_y_lo_no_protegido_no_se_amplian(self):
        op = self.a_breakeven()
        op["cartera_funding"] = True
        self.assertIn("cartera", self.gestor.ampliable(op))
        op["cartera_funding"] = False
        self.gestor.sin_stop["ETH"] = "prueba"
        self.assertIn("congelado", self.gestor.ampliable(op))


class NoRecompraElTP1(Base):
    """CP-E06 (auditoría 26/11, Q-05): cobrar el TP1 ponía el stop en la entrada y en el ciclo siguiente se recompraba
    el 50 % recién vendido (SKY: +0,29 R -> -0,38 R). La piramidación sigue activa, pero espera al menos 1 R más."""

    def cobrar_tp1(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        self.assertTrue(op["parcial"])
        mover(self.papel, self.m, "ETH", op["tp1"] * 1.001)
        self.gestor.conciliar(self.m.precios)
        op = self.estado["posiciones"]["ETH"]
        self.gestor.gestionar(op, self.m.precios["ETH"])
        self.assertTrue(op["tp1_hecho"] and op["en_breakeven"])
        return op

    def test_no_amplia_en_el_ciclo_del_cobro(self):
        op = self.cobrar_tp1()
        motivo = self.gestor.ampliable(op, op["tp1"] + 2 * op["r_dist"])    # ni con el precio muy lejos
        self.assertIn("mismo ciclo", motivo)

    def test_sin_avanzar_1r_no_amplia_y_tras_1r_si(self):
        op = self.cobrar_tp1()
        self.gestor.conciliar(self.m.precios)                                # otro ciclo, precio igual
        op = self.estado["posiciones"]["ETH"]
        self.assertIn("no ha avanzado", self.gestor.ampliable(op, self.m.precios["ETH"]))
        self.assertIn("no ha avanzado", self.gestor.ampliable(op, op["tp1"] + 0.9 * op["r_dist"]))
        self.assertIn("sin precio", self.gestor.ampliable(op, None))
        self.assertIsNone(self.gestor.ampliable(op, op["tp1"] + 1.0 * op["r_dist"]))
        self.assertIsNone(self.gestor.ampliable(op, op["tp1"] + 1.5 * op["r_dist"]))

    def test_el_avance_exigido_es_configurable(self):
        op = self.cobrar_tp1()
        self.gestor.conciliar(self.m.precios)
        op = self.estado["posiciones"]["ETH"]
        self.gestor.c["piramide"]["avance_tras_tp1_r"] = 0.5
        self.assertIsNone(self.gestor.ampliable(op, op["tp1"] + 0.6 * op["r_dist"]))

    def test_sin_objetivo_parcial_no_cambia(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        op["tp1_hecho"], op["en_breakeven"], op["sl"] = False, True, op["entrada"]
        self.assertIsNone(self.gestor.ampliable(op, op["entrada"]))         # sin TP1 cobrado: como antes


class FundingConSuHora(ConCarpeta):
    def test_cada_pago_conserva_la_hora_del_cobro(self):
        ledger = Ledger(os.path.join(self.dir, "registro"))
        h = 3_600_000
        for k in (1, 2):
            ledger.registrar("funding", "t1", "simulado", moneda="ETH", lado="L", usd=-0.01, tasa=0.0001,
                             ts_pago=iso_ms(k * h))
        ops, _ = ledger.operaciones()
        horas = [p["ts"] for p in ops["t1"]["funding"]]
        self.assertEqual(horas, [iso_ms(h), iso_ms(2 * h)])
        self.assertEqual(iso_ms(0), "1970-01-01T00:00:00.000Z")
        self.assertIsNone(iso_ms(None))


if __name__ == "__main__":
    unittest.main()
