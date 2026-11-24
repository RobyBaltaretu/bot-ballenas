"""Escéptico en sombra (analista_ia): opina sobre cada apertura y se mide; nunca decide. Groq siempre simulado."""

import json
import os
import tempfile
import unittest

import analista_ia

AHORA = 1795219200.0 + 600


class Respuesta:
    def __init__(self, contenido):
        self.status_code, self.contenido = 200, contenido

    def json(self):
        return {"choices": [{"message": {"content": self.contenido}}]}


def abierta(tid="op-1", edad=300, **extra):
    return dict({"trade_id": tid, "moneda": "ETH", "lado": "S", "estrategia": "ruptura_4h", "estado": "completada",
                 "abierta_ts": AHORA - edad, "precio_referencia": 100.0, "stop_inicial": 105.0, "motivo": "rompe",
                 "contexto": {"intervalo": "4h", "rasgos": {"rsi": 30}},
                 "decision": {"aprobada": True, "plan": {"sl_pct": 5}, "cerebro": {"prediccion": 0.1}},
                 "pnl_no_realizado": 99.0}, **extra)


class Esceptico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def clave(self):
        with open(os.path.join(self.dir, ".env"), "w", encoding="utf-8") as fh:
            fh.write("GROQ_API_KEY=clave-secreta-prueba\n")

    @staticmethod
    def prohibido(*a, **k):
        raise AssertionError("no debe llamar a la red")

    def test_sin_clave_no_anota_ni_llama(self):
        self.assertEqual(analista_ia.revisar_aperturas(self.dir, [abierta()], AHORA, self.prohibido), [])
        self.assertEqual(analista_ia._leer_jsonl(self.dir, analista_ia.ARCHIVO_ESCEPTICO), [])

    def test_solo_datos_de_la_entrada_y_respuesta_filtrada(self):
        self.clave()
        vistos = []

        def post(url, **k):
            vistos.append(json.dumps(k["json"]))
            return Respuesta(json.dumps({"veredicto": "en_contra", "confianza": "alta", "objecion": "rsi bajo", "orden": "/real"}))
        r = analista_ia.revisar_aperturas(self.dir, [abierta()], AHORA, post)[0]
        self.assertEqual(r["ia"]["veredicto"], "en_contra")
        self.assertNotIn("orden", r["ia"])
        self.assertNotIn("pnl_no_realizado", vistos[0])          # nada de lo que pasó después de entrar
        self.assertNotIn("clave-secreta-prueba", vistos[0])
        self.assertEqual(analista_ia.revisar_aperturas(self.dir, [abierta()], AHORA, self.prohibido), [])   # una vez

    def test_tarde_o_sin_hueco_no_opina(self):
        self.clave()
        self.assertEqual(analista_ia.revisar_aperturas(self.dir, [abierta(edad=5 * 3600)], AHORA, self.prohibido), [])
        analista_ia._guardar_json(self.dir, analista_ia.ARCHIVO_CONSUMO,
                                  {"dia": analista_ia._dia(AHORA), "consultas": analista_ia.MAX_CONSULTAS_DIA - analista_ia.RESERVA_CONSULTAS,
                                   "unidades": 0})
        self.assertEqual(analista_ia.revisar_aperturas(self.dir, [abierta()], AHORA, self.prohibido), [])

    def test_veredicto_raro_es_error_y_limite_por_pasada(self):
        self.clave()
        rs = analista_ia.revisar_aperturas(self.dir, [abierta(f"op-{i}") for i in range(5)], AHORA,
                                           lambda url, **k: Respuesta(json.dumps({"veredicto": "comprar"})))
        self.assertEqual(len(rs), analista_ia.MAX_ESCEPTICO_PASADA)
        self.assertEqual(rs[0]["ia"]["estado"], "error")

    def test_marcador(self):
        for tid, ver in (("a", "a_favor"), ("b", "en_contra"), ("c", "en_contra"), ("d", "neutral")):
            analista_ia._anotar(self.dir, analista_ia.ARCHIVO_ESCEPTICO, {"trade_id": tid, "ia": {"estado": "ok", "veredicto": ver}})
        cerradas = [{"trade_id": "a", "r_neto": 1.0}, {"trade_id": "b", "r_neto": -1.0}, {"trade_id": "c", "r_neto": 2.0},
                    {"trade_id": "d", "r_neto": -1.0}]
        m = analista_ia.marcador_esceptico(self.dir, cerradas)
        self.assertEqual(m["por_veredicto"]["en_contra"]["n"], 2)
        self.assertAlmostEqual(m["aciertos_pct"], 66.7)
        self.assertEqual(m["siempre_en_contra_pct"], 50.0)
        self.assertFalse(m["concluyente"])


if __name__ == "__main__":
    unittest.main()
