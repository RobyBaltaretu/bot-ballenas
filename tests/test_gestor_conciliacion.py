"""Conciliación de objetivos, stop dinámico y cierres parciales (P0 del suplemento): con la cuenta simulada, sin red.
Nunca se supone que un objetivo tocado se llenó ni se inventa PnL cuando la atribución de fills no es única."""

import copy

from contabilidad import atribuir_funding
from gestor import intervalos_funding, trailing_activo
from tests.comunes import config, mover
from tests.test_gestor import Base


def tps(papel, moneda):
    return [o for o in papel.d["ordenes"] if o["coin"] == moneda and o["tipo"] == "limite" and o["reduce_only"]]


class Objetivos(Base):
    def test_tp1_fallido_no_impide_el_objetivo_final(self):
        original = self.papel.order
        rechazos = []

        def falla_primer_tp(name, is_buy, sz, px, tipo, reduce_only=False, cloid=None, builder=None):
            if reduce_only and "limit" in tipo and not rechazos:
                rechazos.append(px)
                return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"error": "rechazado"}]}}}
            return original(name, is_buy, sz, px, tipo, reduce_only, cloid)
        self.papel.order = falla_primer_tp
        op = self.gestor.abrir(self.plan(tam=0.05))
        self.assertTrue(op["parcial"])
        self.assertEqual(len(rechazos), 1)
        roles = {o["rol"]: o["estado"] for o in op["ordenes"].values() if o["rol"] in ("tp1", "tpf")}
        self.assertEqual(roles["tp1"], "rechazada")
        self.assertEqual(roles["tpf"], "abierta")                 # se intentó (y se puso) de forma independiente
        self.assertEqual(len(tps(self.papel, "ETH")), 1)
        self.assertTrue(any("primer objetivo" in t for _, t in self.alertas))

    def test_objetivo_final_que_desaparece_se_repone_con_el_tamano_correcto(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        cl_tpf = next(cl for cl, o in op["ordenes"].items() if o["rol"] == "tpf")
        self.papel.cancel_by_cloid("ETH", cl_tpf)                 # desaparece (p. ej. cancelada por el exchange)
        self.gestor.conciliar(self.m.precios)
        vivos = tps(self.papel, "ETH")
        self.assertEqual(len(vivos), 2)                           # TP1 + TP final repuesto
        suma = sum(o["sz"] for o in vivos)
        self.assertLessEqual(suma, self.estado["posiciones"]["ETH"]["tam"] + 1e-9)
        self.gestor.conciliar(self.m.precios)                     # idempotente: no lo duplica
        self.assertEqual(len(tps(self.papel, "ETH")), 2)

    def test_objetivo_con_estado_incierto_no_se_repone_a_ciegas(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        cl_tpf = next(cl for cl, o in op["ordenes"].items() if o["rol"] == "tpf")
        self.papel.cancel_by_cloid("ETH", cl_tpf)
        self.gestor.ej.consultar = lambda **k: None               # el exchange no responde
        self.gestor.conciliar(self.m.precios)
        self.assertEqual(len(tps(self.papel, "ETH")), 1)          # solo el TP1: el final NO se reenvía

    def test_parcial_con_estado_de_orden_atrasado_se_explica_por_fills(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        mover(self.papel, self.m, "ETH", op["tp1"] * 1.001)       # se llena el TP1
        consultar = self.gestor.ej.consultar
        self.gestor.ej.consultar = lambda **k: None               # su estado aún no llega
        self.gestor.conciliar(self.m.precios)
        self.gestor.ej.consultar = consultar
        o = self.estado["posiciones"]["ETH"]
        self.assertTrue(o["tp1_hecho"])
        self.assertFalse(o.get("contabilidad_incompleta"))
        self.assertEqual(len(o["tramos_tam"][-1]), 2)             # hora del FILL del exchange, no «incierto»
        self.assertNotIn("reducción no explicada", (self.gestor.ej.congelados.get("ETH") or {}).get("motivo", ""))

    def test_reduccion_sin_atribucion_unica_congela_y_queda_desconocida(self):
        self.gestor.abrir(self.plan(tam=0.05))
        self.papel.order("ETH", False, 0.01, 3000.0, {"limit": {"tif": "Ioc"}})   # alguien reduce a mano
        self.gestor.conciliar(self.m.precios)
        o = self.estado["posiciones"]["ETH"]
        self.assertTrue(o["contabilidad_incompleta"])
        self.assertIn("ETH", self.gestor.ej.congelados)
        self.assertEqual(o["tramos_tam"][-1][2], "incierto")


class StopDinamico(Base):
    def test_trailing_sin_parcial_es_un_estado_explicito(self):
        cs = {"trailing_sin_parcial": False}
        self.assertFalse(trailing_activo({"en_breakeven": True, "parcial": False}, cs))
        self.assertTrue(trailing_activo({"en_breakeven": True, "parcial": False}, {"trailing_sin_parcial": True}))
        self.assertTrue(trailing_activo({"en_breakeven": True, "tp1_hecho": True}, cs))
        self.assertFalse(trailing_activo({"en_breakeven": False, "tp1_hecho": True}, cs))

    def _sin_parcial(self, trailing):
        self.c = config(ordenes__entrada_limite=False, salida__parcial_activo=False,
                        salida__trailing_sin_parcial=trailing)
        self.gestor = self.nuevo_gestor()
        plan = self.plan(tam=0.05)
        plan["salida"] = dict(self.c["salida"])
        op = self.gestor.abrir(plan)
        self.assertFalse(op["parcial"])
        for r in (1.2, 2.5):
            px = op["entrada"] + r * op["r_dist"]
            mover(self.papel, self.m, "ETH", px)
            self.gestor.gestionar(op, px)
        return op

    def test_sin_parcial_y_sin_trailing_se_queda_en_sin_perdidas(self):
        op = self._sin_parcial(False)
        self.assertTrue(op["en_breakeven"])
        self.assertAlmostEqual(op["sl"], self.gestor.precio_breakeven(op), delta=op["entrada"] * 1e-4)
        self.assertFalse(op.get("tp1_hecho"))                     # nunca se finge un TP1

    def test_sin_parcial_con_trailing_persigue_el_precio(self):
        op = self._sin_parcial(True)
        self.assertTrue(op["trailing_activo"])
        self.assertGreater(op["sl"], self.gestor.precio_breakeven(op))
        self.assertFalse(op.get("tp1_hecho"))

    def test_trigger_al_otro_lado_del_precio_no_se_envia_y_el_anterior_sigue(self):
        op = self.gestor.abrir(self.plan())
        viejo = op["stop_cloid"]
        n = len(self.papel.d["ordenes"])
        self.assertFalse(self.gestor.reemplazar_stop(op, self.m.precios["ETH"] * 1.01, op["tam"], "prueba"))
        self.assertEqual(len(self.papel.d["ordenes"]), n)          # nada enviado
        self.assertEqual(op["stop_cloid"], viejo)
        self.assertEqual(self.gestor.sin_stop, {})                 # el anterior sigue vivo
        self.papel.cancel_by_cloid("ETH", viejo)                   # y si el anterior no estuviera...
        self.assertFalse(self.gestor.reemplazar_stop(op, self.m.precios["ETH"] * 1.01, op["tam"], "prueba"))
        self.assertIn("ETH", self.gestor.sin_stop)
        self.assertIn("ETH", self.gestor.ej.congelados)


class Cierres(Base):
    def _stop_con_otro_oid(self, op):
        mover(self.papel, self.m, "ETH", op["sl"] * 0.995)
        self.gestor.leer()                                        # la cuenta simulada procesa el disparo
        ult = self.papel.d["fills"][-1]
        self.assertEqual(ult["oid"], op["stop_oid"])
        ult["oid"], ult["cloid"] = 987654321, None                # la orden hija del stop: otro oid, sin cloid

    def test_tp1_y_despues_stop_con_otro_oid_se_contabiliza_entero(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        mover(self.papel, self.m, "ETH", op["tp1"] * 1.001)
        self.gestor.conciliar(self.m.precios)
        op = self.estado["posiciones"]["ETH"]
        self.assertTrue(op["tp1_hecho"])
        self._stop_con_otro_oid(op)
        self.gestor.conciliar(self.m.precios)
        self.assertNotIn("ETH", self.estado["posiciones"])
        ops, _ = self.ledger.operaciones()
        o = ops[op["trade_id"]]
        self.assertIsNotNone(o["pnl_neto"])
        cierre = [e for e in self.ledger.leer()[0] if e["tipo"] == "cierre"][-1]
        self.assertNotEqual(cierre["datos_fills"], "incompletos")
        fills_salida = [e for e in self.ledger.leer()[0] if e["tipo"] == "fill" and e.get("rol") != "entrada"]
        self.assertAlmostEqual(sum(e["sz"] for e in fills_salida), op["tam_inicial"], places=6)

    def test_actividad_externa_concurrente_da_resultado_desconocido(self):
        op = self.gestor.abrir(self.plan(tam=0.05))
        self.gestor.externas_vistas.add("ETH")                    # hubo actividad ajena en esa moneda
        self._stop_con_otro_oid(op)
        self.gestor.conciliar(self.m.precios)
        cierre = [e for e in self.ledger.leer()[0] if e["tipo"] == "cierre"][-1]
        self.assertIsNone(cierre["pnl_neto"])                     # sin PnL inventado
        self.assertEqual(cierre["datos_fills"], "incompletos")
        self.assertIn("ETH", self.gestor.ej.congelados)


class FundingEnElLimite(Base):
    def test_cambio_de_tamano_con_hora_incierta_no_asigna_el_funding_cercano(self):
        h = 3_600_000
        base = {"trade_id": "t", "moneda": "ETH", "lado": "L", "abierta_ts": 0, "tam_inicial": 1.0}
        regs = [{"time": 2 * h, "delta": {"coin": "ETH", "usdc": "-0.1", "szi": "0.5", "fundingRate": "0.0001"}}]
        # El TP1 se llenó a las 1:59:30 (fill del exchange): el pago de las 2:00 es del tamaño 0,5.
        cierto = dict(base, tramos_tam=[[0, 1.0], [2 * h - 30_000, 0.5]])
        por, sin = atribuir_funding(regs, intervalos_funding(cierto, 3 * h, 120_000))
        self.assertEqual(len(por["t"]), 1)
        # Detectado localmente a las 2:00:30 sin fill: pudo ser antes o después del pago -> sin asignar.
        incierto = dict(base, tramos_tam=[[0, 1.0], [2 * h + 30_000, 0.5, "incierto"]])
        por, sin = atribuir_funding(regs, intervalos_funding(incierto, 3 * h, 120_000))
        self.assertEqual(por, {})
        self.assertEqual(len(sin), 1)
        self.assertEqual(copy.deepcopy(incierto["tramos_tam"][1][2]), "incierto")


del Base            # sus pruebas ya se ejecutan en test_gestor
