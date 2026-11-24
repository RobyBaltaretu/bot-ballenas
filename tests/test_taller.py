"""Taller (18/11/2026): la revisión del sistema dice la verdad, no inventa «ok» y solo ofrece arreglos seguros."""

import json
import os
import tempfile
import time
import unittest

import taller

AHORA = 1_800_000_000.0
SEGUROS = {"/reanudar", "/aplicarconfig", "/laboratorio", "/investigacion"}


def sano():
    sis = {"latido_ts": AHORA - 5, "ciclos": 1000, "ciclos_fallidos": 0, "ciclo_mediana_seg": 5.5, "ciclo_p95_seg": 6.5,
           "incidentes_activos": 0, "disco": {"libre_gb": 300}, "componentes": {"websocket": {"estado": "correcto", "detalle": "ok"}}}
    bot = {"precios_ts": AHORA - 4, "datos_frescos": True, "conciliacion_ok": True, "conciliacion_ts": AHORA - 20,
           "posiciones": [{"moneda": "ENA", "stop_verificado": True}], "sin_stop": {}, "riesgo_liquidacion": {}, "bloqueos": [],
           "exposicion": {"riesgo_desconocido": []}, "cobertura_ballenas": {"elegidas": 10, "frescas": 9}, "modo": "simulado",
           "contexto_externo": {"activo": True, "fuentes": {"binance": {"estado": "correcto"}, "bybit": {"estado": "correcto"}}},
           "cerebro": {"version": "cerebro-lab-1"}, "margen": {"fraccion_mantenimiento": 0.02}}
    return sis, bot


class Taller(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = self.t.name
        self.addCleanup(self.t.cleanup)
        os.makedirs(os.path.join(self.d, "registro"))

    def escribir(self, sis=None, bot=None):
        s, b = sano()
        for nombre, datos in (("estado_sistema.json", s if sis is None else sis), ("panel_datos.json", b if bot is None else bot)):
            with open(os.path.join(self.d, nombre), "w", encoding="utf-8") as fh:
                json.dump(datos, fh)
        for nombre in ("estrategia_elegida.json", "registro/investigacion_informe.json"):
            ruta = os.path.join(self.d, nombre)
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write("{}")
            os.utime(ruta, (AHORA - 3600, AHORA - 3600))

    def rev(self, **kw):
        r = taller.revisar(self.d, AHORA, kw.get("validar", lambda: (True, "ok")))
        return r, {x["id"]: x for g in r["grupos"] for x in g["checks"]}

    def test_sistema_sano_sale_en_orden(self):
        self.escribir()
        r, c = self.rev()
        self.assertEqual(r["estado"], "ok", [(k, v["estado"]) for k, v in c.items() if v["estado"] not in ("ok", "pendiente")])
        self.assertEqual(r["trabajos"], [])
        self.assertEqual(r["total"], sum(len(g["checks"]) for g in r["grupos"]))

    def test_bot_parado_es_mal_y_sin_arreglo_automatico(self):
        s, _ = sano()
        s["latido_ts"] = AHORA - 3600
        self.escribir(sis=s)
        r, c = self.rev()
        self.assertEqual(c["latido"]["estado"], "mal")
        self.assertIsNone(c["latido"]["arreglo"])               # un bot parado no puede reiniciarse a sí mismo
        self.assertTrue(any("INICIAR.bat" in p for p in c["latido"]["pasos"]))
        self.assertEqual(r["estado"], "mal")

    def test_sin_datos_es_desconocido_nunca_ok(self):
        self.escribir(sis={}, bot={})
        _, c = self.rev()
        for k in ("latido", "ciclo", "precios", "conciliacion"):
            self.assertEqual(c[k]["estado"], "desconocido", k)

    def test_precios_viejos_y_stop_sin_confirmar(self):
        s, b = sano()
        b["precios_ts"] = AHORA - 900
        b["sin_stop"] = {"ENA": "no se pudo verificar"}
        self.escribir(sis=s, bot=b)
        _, c = self.rev()
        self.assertEqual(c["precios"]["estado"], "mal")
        self.assertEqual(c["stops"]["estado"], "mal")
        self.assertIn("ENA", c["stops"]["resumen"])

    def test_pausa_manual_ofrece_reanudar(self):
        _, b = sano()
        b["bloqueos"] = ["pausa manual"]
        self.escribir(bot=b)
        _, c = self.rev()
        self.assertEqual(c["bloqueos"]["arreglo"]["cmd"], "/reanudar")

    def test_riesgo_desconocido_es_mal(self):
        _, b = sano()
        b["exposicion"] = {"riesgo_desconocido": ["SOL"]}
        self.escribir(bot=b)
        self.assertEqual(self.rev()[1]["riesgo_conocido"]["estado"], "mal")

    def test_laboratorio_viejo_ofrece_lanzarlo_salvo_que_ya_corra(self):
        self.escribir()
        ruta = os.path.join(self.d, "estrategia_elegida.json")
        os.utime(ruta, (AHORA - 12 * 86400, AHORA - 12 * 86400))
        _, c = self.rev()
        self.assertEqual(c["laboratorio"]["estado"], "aviso")
        self.assertEqual(c["laboratorio"]["arreglo"]["cmd"], "/laboratorio")
        bloqueo = os.path.join(self.d, "laboratorio_semanal.lock")
        with open(bloqueo, "w") as fh:
            fh.write("x")
        os.utime(bloqueo, (AHORA - 600, AHORA - 600))
        _, c = self.rev()
        self.assertEqual(c["laboratorio"]["estado"], "ok")
        self.assertIn("En marcha", c["laboratorio"]["resumen"])
        self.assertIsNone(c["laboratorio"]["arreglo"])

    def test_todos_los_arreglos_son_comandos_seguros(self):
        s, b = sano()
        s.update(latido_ts=AHORA - 400, ciclo_p95_seg=60.0)
        b.update(precios_ts=AHORA - 100, bloqueos=["pausa manual"], conciliacion_ts=AHORA - 1000)
        self.escribir(sis=s, bot=b)
        os.utime(os.path.join(self.d, "estrategia_elegida.json"), (AHORA - 20 * 86400,) * 2)
        os.utime(os.path.join(self.d, "registro/investigacion_informe.json"), (AHORA - 5 * 86400,) * 2)
        _, c = self.rev()
        cmds = {x["arreglo"]["cmd"] for x in c.values() if x["arreglo"]}
        self.assertTrue(cmds)
        self.assertTrue(cmds <= SEGUROS, cmds)
        for x in c.values():
            if x["arreglo"]:
                self.assertEqual(x["arreglo"]["tipo"], "comando")
                self.assertTrue(x["arreglo"]["confirma"])

    def test_env_solo_dice_si_tiene_valor_nunca_el_valor(self):
        with open(os.path.join(self.d, ".env"), "w", encoding="utf-8") as fh:
            fh.write("# comentario\nTELEGRAM_TOKEN=SECRETO-123\nTELEGRAM_CHAT_ID=\nPANEL_PASSWORD='zq9x-pw'\nGROQ_API_KEY=gk_7731\n")
        self.assertEqual(taller._env_con_valor(self.d), {"TELEGRAM_TOKEN", "PANEL_PASSWORD", "GROQ_API_KEY"})
        self.escribir()
        r, c = self.rev()
        texto = json.dumps(r, ensure_ascii=False)
        for secreto in ("SECRETO-123", "zq9x-pw", "gk_7731"):
            self.assertNotIn(secreto, texto)
        self.assertEqual(c["telegram"]["estado"], "pendiente")            # falta el chat_id
        self.assertEqual(c["panel_clave"]["estado"], "ok")

    def test_pendiente_no_cuenta_como_fallo(self):
        self.escribir()
        r, c = self.rev()
        self.assertEqual(c["telegram"]["estado"], "pendiente")
        self.assertEqual(r["estado"], "ok")
        self.assertIn("telegram", r["pendientes"])

    def test_config_invalida_es_mal(self):
        self.escribir()
        _, c = self.rev(validar=lambda: (False, "riesgo fuera de rango"))
        self.assertEqual(c["config"]["estado"], "mal")

    def test_humano(self):
        self.assertEqual(taller.humano(5), "5 s")
        self.assertEqual(taller.humano(600), "10 min")
        self.assertEqual(taller.humano(7200), "2.0 h")
        self.assertEqual(taller.humano(None), "—")


if __name__ == "__main__":
    unittest.main()
