import unittest

import ledger
import revision_proceso as rp


def _op(eventos):
    op = ledger.nueva_operacion("t1")
    for ev in eventos:
        ev.setdefault("trade_id", "t1")
        ledger.aplicar(op, ev)
    op.pop("_ids", None)
    return ledger.cerrar_resumen(op)


def _base(retraso_stop="2026-11-21T04:00:02Z", px_salida=95.0, peor=0.0, cierre=True):
    evs = [
        {"tipo": "senal", "ts": "2026-11-21T04:00:00Z", "moneda": "BTC", "lado": "L", "estrategia": "x", "precio": 100.0},
        {"tipo": "decision", "ts": "2026-11-21T04:00:00.5Z", "aprobada": True, "plan": {}},
        {"tipo": "orden_enviada", "ts": "2026-11-21T04:00:01Z", "rol": "entrada", "cloid": "c1", "sz": 1,
         "tipo_orden": {"limit": {"tif": "Alo"}}},
        {"tipo": "fill", "ts": "2026-11-21T04:00:01Z", "rol": "entrada", "px": 100.1, "sz": 1, "comision": 0.01,
         "cloid": "c1", "fill_id": "f1"},
        {"tipo": "riesgo_post_fill", "ts": "2026-11-21T04:00:01Z", "ratio": 1.02},
        {"tipo": "proteccion", "ts": retraso_stop, "clase": "stop", "accion": "verificado", "trigger": 95.0, "riesgo_usd": 5.0},
    ]
    if cierre:
        evs += [{"tipo": "fill", "ts": "2026-11-21T06:00:00Z", "rol": "stop", "px": px_salida, "sz": 1, "comision": 0.01,
                 "fill_id": "f2"},
                {"tipo": "cierre", "ts": "2026-11-21T06:00:00Z", "causa": "stop-loss", "peor_que_trigger_pct": peor}]
    return evs


class TestRevisionProceso(unittest.TestCase):
    def test_sin_entrada_no_hay_nota(self):
        self.assertIsNone(rp.nota(_op([{"tipo": "senal", "ts": "2026-11-21T04:00:00Z", "precio": 1}])))

    def test_buen_proceso_y_mal_resultado_no_es_un_error(self):
        n = rp.nota(_op(_base()))
        self.assertEqual(n["nota"], "A")
        self.assertTrue(n["proceso_bueno"])
        self.assertIn("buen proceso, mal resultado", n["cuadrante"])
        self.assertEqual(n["medidas"]["entrada"], "creadora")
        self.assertAlmostEqual(n["medidas"]["segundos_sin_stop"], 1.0)

    def test_stop_tardio_y_deslizado_baja_la_nota(self):
        n = rp.nota(_op(_base(retraso_stop="2026-11-21T04:10:00Z", px_salida=93.0, peor=0.6)))
        claves = {c["clave"]: c["nivel"] for c in n["comprobaciones"]}
        self.assertEqual(claves["stop_puesto"], "fallo")
        self.assertEqual(claves["deslizamiento_stop"], "fallo")
        self.assertFalse(n["proceso_bueno"])

    def test_sin_stop_es_fallo(self):
        evs = [e for e in _base(cierre=False) if e["tipo"] != "proteccion"]
        n = rp.nota(_op(evs))
        self.assertEqual({c["clave"]: c["nivel"] for c in n["comprobaciones"]}["stop_puesto"], "fallo")
        self.assertTrue(n["provisional"])
        self.assertIsNone(n["cuadrante"])

    def test_fill_antes_de_la_decision_es_fallo(self):
        evs = _base()
        evs[1]["ts"] = "2026-11-21T04:00:05Z"
        n = rp.nota(_op(evs))
        self.assertEqual({c["clave"]: c["nivel"] for c in n["comprobaciones"]}["orden_pasos"], "fallo")

    def test_resumen_cuenta_y_calibra(self):
        a = _op(_base())
        b = _op(_base(retraso_stop="2026-11-21T04:10:00Z", peor=0.6))
        b["trade_id"] = "t2"
        r = rp.resumen([a, b])
        self.assertEqual(r["n"], 2)
        self.assertEqual(r["calibracion_entrada"]["creadora"]["n"], 2)
        self.assertEqual(r["peores"][0]["trade_id"], "t2")
        self.assertEqual(rp.resumen([a, b], desde=2e9)["n"], 0)


if __name__ == "__main__":
    unittest.main()
