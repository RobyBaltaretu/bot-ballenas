"""Arreglos de la auditoría del 19/11/2026: límite conjunto de desplome (R-05) y cierre en el ledger de operaciones
huérfanas (R-08, caso kPEPE del 23/10). La ampliación con los mismos controles que una entrada (R-01) está en test_bot."""

import os
import time
import unittest

from ledger import Ledger, nuevo_trade_id
from riesgo import comprobar_salto, riesgo_salto
from tests.comunes import ConCarpeta, config
from tests.test_gestor import Base


class DesplomeConjunto(unittest.TestCase):
    def setUp(self):
        self.c = config()
        self.c["riesgo"]["riesgo_salto_max_pct"] = 20

    def pos(self, lado="L", tam=1.0, entrada=100.0, sl=92.0, moneda="X"):
        return {"moneda": moneda, "lado": lado, "tam": tam, "entrada": entrada, "sl": sl}

    def test_salto_al_limite_del_stop(self):
        taker = self.c["comisiones"]["taker_pct"] / 100
        # largo: stop 92, orden hija al 10 % peor -> 82,8; pierde 17,2 + comisión de salida
        self.assertAlmostEqual(riesgo_salto(self.pos(), self.c), 17.2 + 82.8 * taker, places=6)
        corto = riesgo_salto(self.pos("S", entrada=100.0, sl=108.0), self.c)
        self.assertAlmostEqual(corto, 18.8 + 118.8 * taker, places=6)
        # stop ya en ganancia de sobra: no pierde nada
        self.assertEqual(riesgo_salto(self.pos(entrada=100.0, sl=130.0), self.c), 0.0)
        self.assertIsNone(riesgo_salto({"lado": "L", "tam": 1.0, "entrada": 100.0}, self.c))

    def test_suma_solo_el_mismo_lado(self):
        largas = [self.pos(moneda=m) for m in ("A", "B")]          # ~17,3 cada una
        cortas = [self.pos("S", sl=108.0, moneda=m) for m in ("C", "D", "E")]
        # equity 200 -> tope 40. Dos largas (34,6) + una nueva de 17,3 = 51,9 > 40: bloquea
        self.assertTrue(comprobar_salto({"lado": "L", "riesgo_salto_usd": 17.3}, largas + cortas, 200, self.c))
        # una corta nueva pequeña: las largas no cuentan; 3 cortas (~57) ya pasan de 40 -> bloquea igualmente
        self.assertTrue(comprobar_salto({"lado": "S", "riesgo_salto_usd": 1.0}, largas + cortas, 200, self.c))
        # con solo una larga abierta y una nueva pequeña, cabe
        self.assertEqual(comprobar_salto({"lado": "L", "riesgo_salto_usd": 5.0}, largas[:1], 200, self.c), [])

    def test_desconocido_bloquea_y_cero_desactiva(self):
        raro = {"moneda": "Z", "lado": "L", "tam": 1.0, "entrada": 100.0}      # sin stop
        self.assertTrue(comprobar_salto({"lado": "L", "riesgo_salto_usd": 1.0}, [raro], 1000, self.c))
        self.assertTrue(comprobar_salto({"lado": "L", "riesgo_salto_usd": None}, [], 1000, self.c))
        self.c["riesgo"]["riesgo_salto_max_pct"] = 0
        self.assertEqual(comprobar_salto({"lado": "L", "riesgo_salto_usd": 999.0}, [raro], 1000, self.c), [])


class HuerfanasDelLedger(Base):
    def huerfana(self, moneda="ETH", hace_s=3600):
        """Una operación que el ledger ve abierta (con entrada) pero que el gestor no tiene: como kPEPE el 23/10."""
        tid = nuevo_trade_id()
        ev = self.ledger.registrar("fill", tid, "simulado", moneda=moneda, lado="L", estrategia="prueba_4h", rol="entrada",
                                   px=100.0, sz=1.0, comision=0.01, fill_id=f"{tid}:f", estimado=False)
        return tid, ev

    def test_se_cierra_como_resultado_desconocido(self):
        tid, _ = self.huerfana()
        cerradas = self.gestor.cerrar_huerfanas_ledger(min_edad_s=600, ahora=time.time() + 3600)
        self.assertEqual(cerradas, [tid])
        ops, _ = self.ledger.operaciones()
        o = ops[tid]
        self.assertEqual(o["estado"], "cerrada")
        self.assertIsNone(o["pnl_neto"])                                # nunca se inventa un resultado
        self.assertEqual(o["contabilidad"], "incompleta")
        # idempotente: ya cerrada, no se vuelve a tocar
        self.assertEqual(self.gestor.cerrar_huerfanas_ledger(min_edad_s=600, ahora=time.time() + 7200), [])

    def test_no_toca_las_recientes_ni_las_vivas(self):
        tid, _ = self.huerfana()
        self.assertEqual(self.gestor.cerrar_huerfanas_ledger(min_edad_s=600), [])        # demasiado reciente
        op = self.gestor.abrir(self.plan())                                             # una operación viva
        self.assertEqual(self.gestor.cerrar_huerfanas_ledger(min_edad_s=600, ahora=time.time() + 3600), [tid])
        ops, _ = self.ledger.operaciones()
        self.assertNotEqual(ops[op["trade_id"]]["estado"], "cerrada")

    def test_posicion_sin_dueno_en_esa_moneda_se_deja_a_la_conciliacion(self):
        tid, _ = self.huerfana("BTC")
        self.papel.order("BTC", True, 0.001, self.m.precios["BTC"] * 1.02, {"limit": {"tif": "Ioc"}})   # ajena
        self.assertIn("BTC", self.papel.d["posiciones"])
        self.assertEqual(self.gestor.cerrar_huerfanas_ledger(min_edad_s=600, ahora=time.time() + 3600), [])


class ResumenConContabilidadIncompleta(ConCarpeta):
    def test_no_recalcula_un_resultado_con_fills_parciales(self):
        ledger = Ledger(os.path.join(self.dir, "registro"))
        tid = nuevo_trade_id()
        ledger.registrar("fill", tid, "simulado", moneda="ETH", lado="L", rol="entrada", px=100.0, sz=1.0, comision=0.0,
                         fill_id="a", estimado=False)
        ledger.registrar("fill", tid, "simulado", moneda="ETH", lado="L", rol="salida", px=110.0, sz=0.4, comision=0.0,
                         pnl_cerrado=4.0, fill_id="b", estimado=False)
        ledger.registrar("cierre", tid, "simulado", moneda="ETH", lado="L", pnl_bruto=None, pnl_neto=None,
                         datos_fills="incompletos", cierre_id=f"{tid}:cierre")
        ops, _ = ledger.operaciones()
        self.assertIsNone(ops[tid]["pnl_neto"])
        self.assertIsNone(ops[tid]["r_neto"])


if __name__ == "__main__":
    unittest.main()
