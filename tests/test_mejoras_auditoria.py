"""Mejoras de la auditoría hechas el 21/11/2026: vía de decisión separada (R-07), bloque del cerebro en el resumen del
ledger (R-10), caché de funding para arrancar sin saturar el limitador (R-09) y stops simulados que se aplican también
por lo ocurrido mientras el bot estaba parado (R-14)."""

import json
import logging
import os
import time
import unittest

from ledger import Ledger, nuevo_trade_id, via_decision
from tests.comunes import ConCarpeta, MercadoFalso, config, mover, nuevo_papel


class ViaDeDecision(unittest.TestCase):
    def test_cada_camino_tiene_su_via(self):
        self.assertIsNone(via_decision({"aprobada": False, "plan": {"exploracion_amplia": True}}))
        self.assertEqual(via_decision({"aprobada": True, "plan": {"cartera_funding": True, "explorando": True}}),
                         "cartera_funding")
        self.assertEqual(via_decision({"aprobada": True, "plan": {"exploracion_amplia": True, "explorando": True},
                                       "cerebro": {"exploracion": True, "prediccion": -0.1}}), "exploracion_amplia")
        self.assertEqual(via_decision({"aprobada": True, "plan": {"explorando": True},
                                       "cerebro": {"exploracion": True, "prediccion": 0.2}}), "cerebro_exploracion")
        self.assertEqual(via_decision({"aprobada": True, "plan": {}, "cerebro": {"prediccion": 0.2}}), "cerebro")
        self.assertEqual(via_decision({"aprobada": True, "plan": {}, "cerebro": {"prediccion": None, "abstencion": True}}),
                         "memoria")
        # registro antiguo sin bloque del cerebro
        self.assertEqual(via_decision({"aprobada": True, "plan": {"explorando": True}}), "cerebro_exploracion")


class DecisionEnElLedger(ConCarpeta):
    def test_guarda_cerebro_y_via_y_la_ampliacion_no_pisa_la_entrada(self):
        lg = Ledger(os.path.join(self.dir, "registro"))
        tid = nuevo_trade_id()
        lg.registrar("decision", tid, "simulado", moneda="ETH", lado="L", estrategia="momentum_4h", aprobada=True,
                     motivos=[], plan={"apalancamiento": 2, "explorando": True},
                     cerebro={"prediccion": 0.31, "exploracion": True, "hash_modelo": "abc"})
        lg.registrar("fill", tid, "simulado", moneda="ETH", lado="L", rol="entrada", px=100.0, sz=1.0, comision=0.0,
                     fill_id="f1", estimado=False)
        # una ampliación descartada más tarde (antes sobrescribía la decisión y la operación perdía su plan)
        lg.registrar("decision", tid, "simulado", moneda="ETH", lado="L", estrategia="momentum_4h", aprobada=False,
                     motivos=["ampliación demasiado pequeña (0.01)"], ampliacion=True)
        o = lg.operaciones()[0][tid]
        self.assertTrue(o["decision"]["aprobada"])
        self.assertEqual(o["decision"]["plan"]["apalancamiento"], 2)
        self.assertEqual(o["decision"]["cerebro"]["prediccion"], 0.31)
        self.assertEqual(o["via"], "cerebro_exploracion")
        self.assertEqual(len(o["decisiones_ampliacion"]), 1)
        self.assertNotEqual(o["estado"], "rechazada")


class ResumenPorVia(ConCarpeta):
    def test_separa_vias_y_estrategias(self):
        import panel
        lg = Ledger(os.path.join(self.dir, "registro"))

        def op(estr, plan, cer, pnl, r):
            tid = nuevo_trade_id()
            lg.registrar("decision", tid, "simulado", moneda="ETH", lado="L", estrategia=estr, aprobada=True,
                         motivos=[], plan=plan, cerebro=cer)
            lg.registrar("fill", tid, "simulado", moneda="ETH", lado="L", rol="entrada", px=100.0, sz=1.0,
                         comision=0.0, fill_id=tid + "a", estimado=False)
            lg.registrar("fill", tid, "simulado", moneda="ETH", lado="L", rol="salida", px=100.0 + pnl, sz=1.0,
                         comision=0.0, pnl_cerrado=pnl, fill_id=tid + "b", estimado=False)
            lg.registrar("cierre", tid, "simulado", moneda="ETH", lado="L", pnl_bruto=pnl, pnl_neto=pnl, r_neto=r,
                         cierre_id=tid + ":c")
        op("momentum_4h", {"explorando": True}, {"exploracion": True, "prediccion": 0.2}, 5.0, 1.0)
        op("momentum_4h", {"explorando": True}, {"exploracion": True, "prediccion": 0.2}, -2.0, -0.4)
        op("ballenas_1h", {"exploracion_amplia": True, "explorando": True}, {"prediccion": None}, 1.0, 0.5)
        viejo_aqui, viejo_cache = panel.AQUI, panel.CACHE
        try:
            panel.AQUI = self.dir
            panel.CACHE = panel.CacheLedger()
            d = panel.resumen_vias("simulado")
        finally:
            panel.AQUI, panel.CACHE = viejo_aqui, viejo_cache
        vias = {v["via"]: v for v in d["vias"]}
        self.assertEqual(vias["cerebro_exploracion"]["n"], 2)
        self.assertAlmostEqual(vias["cerebro_exploracion"]["pnl"], 3.0)
        self.assertEqual(vias["exploracion_amplia"]["estrategias"][0]["estrategia"], "ballenas_1h")
        self.assertEqual(d["total"]["n"], 3)


class FundingEnDisco(ConCarpeta):
    def motor(self):
        from motor import Motor
        c = config()
        return Motor(c, logging.getLogger("pruebas"), os.path.join(self.dir, "estrategia_elegida.json"))

    def test_sobrevive_al_reinicio_y_descarta_lo_viejo(self):
        from senales import SerieFunding
        m = self.motor()
        ahora = int(time.time() * 1000)
        regs = [{"time": ahora - k * 3600_000, "fundingRate": "0.0001"} for k in range(48, 0, -1)]
        viejo = [{"time": ahora - 200 * 86400_000, "fundingRate": "0.01"}]
        m.funding_hist["ETH"] = (time.time() - 100, SerieFunding(viejo + regs), viejo + regs)
        m._guardar_funding_disco()
        m2 = self.motor()
        self.assertIn("ETH", m2.funding_hist)
        self.assertEqual(len(m2.funding_hist["ETH"][2]), 48)        # el registro de hace 200 días se descarta
        self.assertEqual(m2.funding_hist["ETH"][2][-1]["time"], regs[-1]["time"])   # se sigue desde aquí

    def test_cache_rota_no_impide_arrancar(self):
        with open(os.path.join(self.dir, "funding_vivo_cache.json"), "w", encoding="utf-8") as fh:
            fh.write("{roto")
        self.assertEqual(self.motor().funding_hist, {})
        with open(os.path.join(self.dir, "funding_vivo_cache.json"), "w", encoding="utf-8") as fh:
            json.dump({"monedas": {"ETH": {"ts": 1, "regs": [{"time": "x"}]}, "SOL": {"ts": 1, "regs": [
                {"time": int(time.time() * 1000), "fundingRate": "0.0001"}]}}}, fh)
        self.assertEqual(list(self.motor().funding_hist), ["SOL"])


class ConVelas(MercadoFalso):
    def __init__(self):
        super().__init__()
        self.velas = []

    def candles_snapshot(self, moneda, intervalo, desde, hasta):
        return [v for v in self.velas if v["t"] >= desde]


class StopsConElBotParado(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.m = ConVelas()
        self.papel, _ = nuevo_papel(self.dir, self.m)
        self.papel.order("ETH", True, 1.0, 4100.0, {"limit": {"tif": "Ioc"}})
        self.papel.order("ETH", False, 1.0, 3500.0, {"trigger": {"triggerPx": 3900.0, "isMarket": True, "tpsl": "sl"}},
                         reduce_only=True)
        self.papel.order("ETH", False, 1.0, 4300.0, {"limit": {"tif": "Gtc"}}, reduce_only=True)
        self.papel.procesar()
        self.minuto = (int(time.time() * 1000) // 60_000 + 1) * 60_000

    def vela(self, k, o, h, lo):
        self.m.velas.append({"t": self.minuto + k * 60_000, "o": str(o), "h": str(h), "l": str(lo), "c": str(o)})

    def parado(self, minutos=30):
        self.papel.d["ultimo_proceso_ms"] -= minutos * 60_000
        for o in self.papel.d["ordenes"]:
            o["ts"] -= (minutos + 5) * 60_000
        self.minuto -= minutos * 60_000

    def test_stop_cruzado_y_vuelto_se_ejecuta_al_volver(self):
        self.parado()
        self.vela(1, 4000, 4010, 3880)          # cruza el stop (3900) y vuelve
        self.vela(2, 3990, 4000, 3980)
        mover(self.papel, self.m, "ETH", 4000.0)
        self.papel.procesar()
        self.assertNotIn("ETH", self.papel.d["posiciones"])
        rec = self.papel.d["huecos_recuperados"][-1]
        self.assertEqual(rec["tipo"], "stop")
        self.assertAlmostEqual(rec["px"], 3900.0)
        self.assertEqual([o for o in self.papel.d["ordenes"] if o["coin"] == "ETH"], [])

    def test_hueco_de_apertura_llena_a_la_apertura(self):
        self.parado()
        self.vela(1, 3800, 3820, 3790)          # abre ya por debajo del stop
        mover(self.papel, self.m, "ETH", 3810.0)
        self.papel.procesar()
        self.assertAlmostEqual(self.papel.d["huecos_recuperados"][-1]["px"], 3800.0)

    def test_gana_lo_que_ocurrio_primero(self):
        self.parado()
        self.vela(1, 4200, 4350, 4190)          # primero el objetivo (4300)...
        self.vela(2, 4000, 4010, 3850)          # ...luego el stop: ya no hay posición
        mover(self.papel, self.m, "ETH", 4000.0)
        self.papel.procesar()
        rec = self.papel.d["huecos_recuperados"]
        self.assertEqual([r["tipo"] for r in rec], ["limite"])
        self.assertNotIn("ETH", self.papel.d["posiciones"])

    def test_sin_hueco_no_se_repasa_nada(self):
        self.vela(1, 4000, 4010, 3880)          # una mecha con el bot en marcha la sigue viendo la marca, no esto
        mover(self.papel, self.m, "ETH", 4000.0)
        self.papel.procesar()
        self.assertIn("ETH", self.papel.d["posiciones"])
        self.assertNotIn("huecos_recuperados", self.papel.d)


class RelojDeBajaResolucion(ConCarpeta):
    """Fallos que solo salían con un reloj que avanza a saltos (Python 3.12 en Windows, ~16 ms): dos cosas en el mismo
    instante. En el servidor también hay que estar a salvo."""

    def test_rotar_dos_veces_en_el_mismo_instante_no_pierde_nada(self):
        from unittest import mock
        import ledger as mod
        fijo = mod.datetime(2026, 11, 21, 12, 0, 0, tzinfo=mod.timezone.utc)
        with mock.patch.object(mod, "datetime", mock.Mock(now=mock.Mock(return_value=fijo))):
            lg = Ledger(os.path.join(self.dir, "r"), max_bytes=300)
            for i in range(20):
                lg.registrar("senal", f"t{i}", "simulado", moneda="ETH", motivo="x" * 20)
        self.assertEqual(len(lg.leer()[0]), 20)

    def test_ultimo_objetivo_con_la_misma_hora_es_el_nuevo(self):
        from gestor import Gestor
        op = {"ordenes": {"viejo": {"rol": "tpf", "ts": 100.0, "estado": "cancelada"},
                          "nuevo": {"rol": "tpf", "ts": 100.0, "estado": "abierta"}}}
        self.assertEqual(Gestor._ultima_tp(None, op, "tpf")[0], "nuevo")


if __name__ == "__main__":
    unittest.main()
