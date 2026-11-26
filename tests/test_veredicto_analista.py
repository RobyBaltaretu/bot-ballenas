"""Veredicto de la prueba de dos semanas y analista (Groq siempre simulado: ninguna prueba llega a la red)."""

import json
import os
import tempfile
import unittest

import analista_ia
import investigacion
import veredicto as vd

DENTRO = vd.INICIO_TS + 86400                       # jueves 05/11/2026
LUNES = vd.INICIO_TS + 5 * 86400 + 12 * 3600        # lunes 09/11/2026 12:00 UTC
GENERADO = "2026-11-08T08:00:00+00:00"
IDEA = {"disparador": {"tipo": "ruptura", "n": 20}, "filtros": [{"tipo": "a_favor_btc"}], "salida": "media", "sl_atr": 2.0, "intervalo": "4h"}


def lab(estado="no_supera", carry=None, generado=GENERADO):
    return {"generado": generado, "investigacion": {"carry_realista": {"holdout": carry or {}}},
            "resultados": {"a_4h": {"estado_evaluacion": estado, "holdout": {"r_medio": 0.2}, "fuera_de_muestra": {"r_medio": 0.3}}}}


def op(r, estrategia="a_4h", ts=DENTRO):
    return {"estrategia": estrategia, "cerrada_ts": ts, "pnl_neto": r, "r_neto": r, "moneda": "ETH"}


class Veredicto(unittest.TestCase):
    def test_sin_nada_no_vale(self):
        self.assertEqual(vd.evaluar(lab(), [], ahora=DENTRO)["resultado"], "no_vale")

    def test_supera_el_laboratorio_va_adelante(self):
        self.assertEqual(vd.evaluar(lab("supera"), [], ahora=DENTRO)["resultado"], "adelante")

    def test_un_laboratorio_anterior_a_la_prueba_no_cuenta(self):
        v = vd.evaluar(lab("supera", generado="2026-11-01T07:00:00+00:00"), [], ahora=DENTRO)
        self.assertEqual(v["resultado"], "pendiente")
        self.assertEqual(v["criterios"][0]["estado"], "pendiente")
        # Si la prueba acaba sin un laboratorio válido, no hay nada que avale seguir.
        self.assertEqual(vd.evaluar(lab("supera", generado="2026-11-01T07:00:00+00:00"), [], ahora=vd.FIN_TS)["resultado"], "no_vale")

    def test_en_vivo_claramente_peor_lo_contradice(self):
        self.assertEqual(vd.evaluar(lab("supera"), [op(-1.0)] * 20, ahora=DENTRO)["resultado"], "no_vale")

    def test_pocas_operaciones_no_contradicen(self):
        self.assertEqual(vd.evaluar(lab("supera"), [op(-1.0)] * 5, ahora=DENTRO)["resultado"], "adelante")

    def test_carry_que_aguanta_cambia_de_rumbo(self):
        carry = {"rentab_anual_capital_pct": 7.4, "t": 8.9, "n": 98}
        v = vd.evaluar(lab(carry=carry), [], ahora=DENTRO)
        self.assertEqual(v["resultado"], "cambiar_de_rumbo")
        self.assertEqual(v["objetivo"]["capital_eur_con_carry"], [48649, 64865])

    def test_provisional_hasta_el_final(self):
        self.assertTrue(vd.evaluar(lab(), [], ahora=DENTRO)["provisional"])
        self.assertFalse(vd.evaluar(lab(), [], ahora=vd.FIN_TS)["provisional"])

    def test_semanas_y_objetivo(self):
        s = vd.evaluar(lab(), [op(30.0)], latente=-5.0, saldo=230, ahora=DENTRO)["semanas"]
        self.assertEqual((s[0]["cerradas_usd"], s[0]["total_usd"]), (30.0, 25.0))     # la semana en curso suma las abiertas
        self.assertTrue(s[0]["en_positivo"])
        self.assertTrue(s[0]["llega_al_objetivo"])
        self.assertFalse(s[1]["empezada"])

    def test_operaciones_de_antes_no_cuentan(self):
        v = vd.evaluar(lab(), [op(5.0, ts=vd.INICIO_TS - 1)], ahora=DENTRO)
        self.assertEqual(v["en_vivo"], {})


class Respuesta:
    def __init__(self, contenido, codigo=200):
        self.status_code, self.contenido = codigo, contenido

    def json(self):
        return {"choices": [{"message": {"content": self.contenido}}]}


class Analista(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.bot = {"ts": DENTRO, "modo": "simulado", "saldo": 230, "posiciones": []}
        self.ver = vd.evaluar(lab(), [], ahora=DENTRO)

    def clave(self, valor="clave-secreta-prueba"):
        with open(os.path.join(self.dir, ".env"), "w", encoding="utf-8") as fh:
            fh.write(f"GROQ_API_KEY={valor}\n")

    def correr(self, post=None, ahora=DENTRO, extra=None):
        def prohibido(*a, **k):
            raise AssertionError("no debe llamar a la red")
        return analista_ia.ejecutar(self.dir, self.bot, [], self.ver, ahora=ahora, post=post or prohibido, extra=extra)

    def test_sin_clave_hay_informe_y_no_llama_a_nadie(self):
        inf = self.correr()
        self.assertEqual(inf["ia"]["estado"], "sin_clave")
        self.assertTrue(inf["hallazgos"])
        self.assertEqual(analista_ia.ultimo_informe(self.dir)["dia"], inf["dia"])

    def test_al_poner_la_clave_vuelve_a_tocar_sin_reiniciar(self):
        self.correr()
        self.assertFalse(analista_ia.toca(self.dir, DENTRO))
        self.clave()
        self.assertTrue(analista_ia.toca(self.dir, DENTRO))

    def test_con_clave_filtra_la_respuesta_y_guarda_ideas_validas(self):
        self.clave()
        vistos = {}

        def post(url, **k):
            vistos.update(k, url=url)
            return Respuesta(json.dumps({"resumen": "ok", "hallazgos": ["a", 3], "correcciones": ["x"],
                                         "estrategias": [{"clave": "a_4h", "recomendacion": "retirar", "motivo": "m"},
                                                         {"clave": "b", "recomendacion": "subir riesgo"}],
                                         "ideas": [IDEA, {"disparador": {"tipo": "inventado"}}], "orden": "/cerrarbot"}))
        inf = self.correr(post, ahora=LUNES)
        self.assertEqual(inf["ia"]["estado"], "ok")
        self.assertEqual(inf["ia"]["hallazgos"], [{"texto": "a", "verificacion": "no_verificado"}])
        self.assertEqual([e["clave"] for e in inf["ia"]["estrategias"]], ["a_4h"])
        self.assertEqual(inf["ia"]["ideas"], [IDEA])
        self.assertNotIn("orden", inf["ia"])
        self.assertIn("groq.com", vistos["url"])
        self.assertNotIn("clave-secreta-prueba", json.dumps(vistos["json"]))
        ruta = os.path.join(analista_ia.ruta_informes(self.dir), analista_ia.ARCHIVO_IDEAS)
        self.assertEqual(len(investigacion.ideas_del_analista(set(), ruta)), 1)
        self.assertFalse(os.path.exists(ruta))

    def test_las_ideas_solo_se_guardan_los_lunes(self):
        self.clave()
        post = lambda u, **k: Respuesta(json.dumps({"resumen": "ok", "ideas": [IDEA]}))   # noqa: E731
        self.assertEqual(analista_ia.datos_para_ia(self.bot, [], self.ver, DENTRO)["ideas_esta_semana"], False)
        self.assertEqual(self.correr(post)["ia"]["ideas"], [])                              # DENTRO es jueves
        self.assertFalse(os.path.exists(os.path.join(analista_ia.ruta_informes(self.dir), analista_ia.ARCHIVO_IDEAS)))
        self.assertTrue(analista_ia.datos_para_ia(self.bot, [], self.ver, LUNES)["ideas_esta_semana"])

    def test_retirar_se_rebaja_sin_base_y_se_respeta_con_ella(self):
        self.clave()
        self.ver["en_vivo"] = {"a_4h": {"n": 4, "r_medio": 0.8}, "b_4h": {"n": 6, "r_medio": -0.5}, "d_1h": {"n": 0, "r_medio": None}}
        recs = [{"clave": c, "recomendacion": "retirar", "motivo": "m"} for c in ("a_4h", "b_4h", "c_1h", "d_1h")]
        post = lambda u, **k: Respuesta(json.dumps({"estrategias": recs}))                  # noqa: E731
        lab_filas = [{"clave": "c_1h", "oos_t": -3.1}, {"clave": "d_1h", "oos_t": -0.5}]
        r = {e["clave"]: e["recomendacion"] for e in self.correr(post, extra={"laboratorio": lab_filas})["ia"]["estrategias"]}
        self.assertEqual(r, {"a_4h": "vigilar", "b_4h": "retirar", "c_1h": "retirar", "d_1h": "vigilar"})

    def test_un_error_no_filtra_la_clave_y_el_informe_sale(self):
        self.clave()

        def post(url, **k):
            raise RuntimeError("fallo con clave-secreta-prueba")
        inf = self.correr(post)
        self.assertEqual(inf["ia"]["estado"], "error")
        self.assertTrue(inf["hallazgos"])
        with open(os.path.join(analista_ia.ruta_informes(self.dir), f"{inf['dia']}.json"), encoding="utf-8") as fh:
            self.assertNotIn("clave-secreta-prueba", fh.read())

    def test_tras_un_error_reintenta_al_cabo_de_una_hora(self):
        self.clave()
        self.correr(lambda u, **k: Respuesta("{}", 404))
        self.assertFalse(analista_ia.toca(self.dir, DENTRO + 60))
        self.assertTrue(analista_ia.toca(self.dir, DENTRO + analista_ia.REINTENTO_TRAS_ERROR))

    def test_error_http_y_json_malo(self):
        self.clave()
        self.assertEqual(self.correr(lambda u, **k: Respuesta("{}", 401))["ia"]["estado"], "error")
        self.assertEqual(self.correr(lambda u, **k: Respuesta("no es json"))["ia"]["estado"], "error")

    def test_a_groq_no_van_ni_config_ni_ballenas(self):
        self.bot.update(config={"secreto": "x"}, ballenas=[{"direccion": "0xabc"}])
        datos = analista_ia.datos_para_ia(self.bot, [], self.ver, DENTRO)
        self.assertNotIn("config", datos)
        self.assertNotIn("ballenas", datos)


def op_cerrada(tid="op-1", r=-1.0, estrategia="a_4h", **extra):
    return dict({"trade_id": tid, "moneda": "ETH", "lado": "L", "estrategia": estrategia, "pnl_neto": r, "r_neto": r, "alertas": [],
                 "eventos": [{"tipo": "decision", "cerebro": {"prediccion": 0.2, "faltan": []}}]}, **extra)


class Ampliado(unittest.TestCase):
    """Revisor, vigilante y marcador. Nunca sale a la red: sin clave o con respuestas simuladas."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.avisos = []

    def clave(self):
        with open(os.path.join(self.dir, ".env"), "w", encoding="utf-8") as fh:
            fh.write("GROQ_API_KEY=clave-secreta-prueba\n")

    @staticmethod
    def prohibido(*a, **k):
        raise AssertionError("no debe llamar a la red")

    def test_dato_citado_se_coteja(self):
        bot = {"posiciones": [{"moneda": "UNI", "sl": 7.49}]}
        cerradas = [{"moneda": "ETH", "r_neto": -1.0}]
        v = analista_ia.verificar_dato
        self.assertEqual(v({"moneda": "UNI", "campo": "sl", "valor": 7.49}, bot, cerradas), "verificado")
        self.assertEqual(v({"moneda": "UNI", "campo": "sl", "valor": 9.0}, bot, cerradas), "contradicho")
        self.assertEqual(v({"moneda": "BTC", "campo": "sl", "valor": 1.0}, bot, cerradas), "contradicho")   # no existe
        self.assertEqual(v({"moneda": "ETH", "campo": "r_neto", "valor": -1.0}, bot, cerradas), "verificado")
        self.assertEqual(v({"texto": "opinión"}, bot, cerradas), "no_verificado")
        self.assertEqual(v({"moneda": "UNI", "campo": "clave_rara", "valor": 1}, bot, cerradas), "no_verificado")

    def test_revisor_sin_clave_hace_lo_que_no_es_ia_y_no_repite(self):
        op = op_cerrada(r=-1.39, alertas=[{"mensaje": "salida por stop 1.671% peor que el trigger"}])
        r = analista_ia.revisar_operaciones(self.dir, [op], DENTRO, self.prohibido)[0]
        self.assertEqual(r["ia"]["estado"], "sin_clave")
        self.assertEqual(r["comprobaciones"]["deslizamiento_stop_pct"], 1.671)
        self.assertEqual(len(r["comprobaciones"]["anomalias"]), 2)
        self.assertEqual(analista_ia.revisar_operaciones(self.dir, [op], DENTRO, self.prohibido), [])

    def test_revisor_filtra_la_respuesta_y_limita_por_pasada(self):
        self.clave()
        vistos = []

        def post(url, **k):
            vistos.append(k["json"])
            return Respuesta(json.dumps({"causa_probable": "inventada", "explicacion": "x", "anomalias": ["a", 1], "orden": "/cerrarbot"}))
        ops = [op_cerrada(f"op-{i}") for i in range(5)]
        rs = analista_ia.revisar_operaciones(self.dir, ops, DENTRO, post)
        self.assertEqual(len(rs), analista_ia.MAX_REVISIONES_PASADA)
        self.assertEqual(rs[0]["ia"]["causa_probable"], "desconocida")
        self.assertEqual(rs[0]["ia"]["anomalias"], ["a"])
        self.assertNotIn("orden", rs[0]["ia"])
        self.assertNotIn("clave-secreta-prueba", json.dumps(vistos))

    def test_tope_diario_de_consultas(self):
        self.clave()
        analista_ia._guardar_json(self.dir, analista_ia.ARCHIVO_CONSUMO,
                                  {"dia": analista_ia._dia(DENTRO), "consultas": analista_ia.MAX_CONSULTAS_DIA, "tokens": 0})
        r = analista_ia.revisar_operaciones(self.dir, [op_cerrada()], DENTRO, self.prohibido)[0]
        self.assertEqual(r["ia"]["estado"], "limite")

    def test_alarmas_las_decide_el_codigo(self):
        bot = {"ts": DENTRO - 900, "conciliacion_ok": True, "bloqueos": ["vieja"]}
        claves = [a["clave"] for a in analista_ia.detectar_alarmas(bot, {}, [], [], DENTRO)]
        self.assertEqual(claves, ["bot_parado"])                  # con el bot parado, no cuenta la foto vieja de bloqueos
        bot = {"ts": DENTRO, "conciliacion_ok": False, "sin_stop": {"ETH": "x"}, "bloqueos": ["datos viejos", "pausa manual"]}
        ws = [{"componente": "websocket", "primer_ts": DENTRO}] * 15
        rev = [{"comprobaciones": {"deslizamiento_stop_pct": 1.0}}] * 3
        claves = {a["clave"] for a in analista_ia.detectar_alarmas(bot, {"componentes": {"api_rest": {"estado": "fallido"}}}, ws, rev, DENTRO)}
        self.assertEqual(claves, {"conciliacion", "sin_stop:ETH", "bloqueo:datos viejos", "componente:api_rest", "websocket", "deslizamiento"})

    def test_vigilante_avisa_una_vez_y_resuelve(self):
        a = {"clave": "bot_parado", "gravedad": "grave", "texto": "parado"}
        n = analista_ia.vigilar(self.dir, [a], DENTRO, self.prohibido, self.avisos.append)
        self.assertEqual((len(n), len(self.avisos)), (1, 1))
        self.assertEqual(analista_ia.vigilar(self.dir, [a], DENTRO + 600, self.prohibido, self.avisos.append), [])
        self.assertEqual(len(self.avisos), 1)
        self.assertEqual(analista_ia.resumen_panel(self.dir, [], DENTRO)["alarmas_activas"][0]["clave"], "bot_parado")
        analista_ia.vigilar(self.dir, [], DENTRO + 1200, self.prohibido, self.avisos.append)
        self.assertEqual(analista_ia.resumen_panel(self.dir, [], DENTRO)["alarmas_activas"], [])
        analista_ia.vigilar(self.dir, [a], DENTRO + 1800, self.prohibido, self.avisos.append)
        self.assertEqual(len(self.avisos), 2)                     # si vuelve a pasar, vuelve a avisar

    def test_marcador_puntua_y_se_compara_con_decir_siempre_retirar(self):
        analista_ia.registrar_recomendaciones(self.dir, [{"clave": "a_4h", "recomendacion": "retirar"}, {"clave": "b_4h", "recomendacion": "mantener"},
                                                         {"clave": "c_4h", "recomendacion": "vigilar"}], DENTRO)
        analista_ia.registrar_recomendaciones(self.dir, [{"clave": "a_4h", "recomendacion": "retirar"}], DENTRO + 86400)   # repetir no cuenta
        cerradas = [{"estrategia": "a_4h", "cerrada_ts": DENTRO + 100 + i, "r_neto": -1.0} for i in range(5)]
        cerradas += [{"estrategia": "b_4h", "cerrada_ts": DENTRO + 100 + i, "r_neto": -0.5} for i in range(5)]
        cerradas += [{"estrategia": "a_4h", "cerrada_ts": DENTRO - 100, "r_neto": 9.0}]                                    # anterior: no cuenta
        m = analista_ia.marcador(self.dir, cerradas)
        self.assertEqual((m["puntuadas"], m["aciertos"], m["siempre_retirar"], m["pendientes"]), (2, 1, 2, 0))
        self.assertEqual(len(m["recomendaciones"]), 2)
        self.assertEqual(analista_ia.marcador(self.dir, cerradas[:4])["pendientes"], 2)

    def test_pasada_sin_clave_no_sale_a_la_red_y_un_fallo_no_para_el_resto(self):
        bot = {"ts": DENTRO, "modo": "simulado", "saldo": 230, "posiciones": []}
        ver = vd.evaluar(lab(), [], ahora=DENTRO)
        self.assertEqual(analista_ia.pasada(self.dir, bot, [], ver, [op_cerrada()], {}, [], None, DENTRO, self.prohibido, self.avisos.append), [])
        self.assertEqual(analista_ia.resumen_panel(self.dir, [], DENTRO)["marcador"]["revisiones"], 1)
        self.assertIsNotNone(analista_ia.ultimo_informe(self.dir))
        errores = analista_ia.pasada(self.dir, None, [], ver, [op_cerrada("op-2")], {}, [], None, DENTRO, self.prohibido, self.avisos.append)
        self.assertEqual(errores, ["vigilante: AttributeError"])
        self.assertEqual(analista_ia.resumen_panel(self.dir, [], DENTRO)["marcador"]["revisiones"], 2)


class SeriesExternas(unittest.TestCase):
    """Se decide al cerrar la vela: nunca con una vela leída antes de que cerrara."""
    H = 3600

    def contexto(self, lector):
        import contexto_externo as ce
        c = ce.ContextoExterno.__new__(ce.ContextoExterno)
        c.bloqueo, c.lectores, c.recientes = __import__("threading").Lock(), [lector], {}
        c.datos = {"ETH": {"fuentes": {"binance": {"simbolo": "ETHUSDT"}}}}
        return c

    def lector(self, fallo=False):
        H, prueba = self.H, self

        class Lector:
            nombre = "binance"
            lecturas = 0

            def recientes(self, simbolo):
                Lector.lecturas += 1
                if fallo:
                    raise OSError("sin red")
                return {"1h": [{"t": k * H * 1000, "c": 1.0, "v": 1.0, "tb": 1.0} for k in range(prueba.CIERRE - 3, prueba.CIERRE)],
                        "funding": []}
        return Lector()

    CIERRE = 500000

    def test_lectura_anterior_al_cierre_se_repite(self):
        lec = self.lector()
        c = self.contexto(lec)
        ahora = self.CIERRE * self.H + 30
        c.recientes["ETH"] = {"ts": ahora - 60, "1h": [{"t": (self.CIERRE - 1) * self.H * 1000, "c": 9.0, "v": 1.0}], "funding": []}
        velas, _ = c.series_cerebro("ETH", "1h", 1200, ahora)
        self.assertEqual(lec.lecturas, 1)
        self.assertEqual(velas[-1]["t"], (self.CIERRE - 1) * self.H * 1000)
        self.assertEqual(velas[-1]["c"], 1.0)                  # la buena, no la parcial

    def test_si_no_se_puede_releer_la_vela_parcial_no_se_usa(self):
        c = self.contexto(self.lector(fallo=True))
        ahora = self.CIERRE * self.H + 30
        c.recientes["ETH"] = {"ts": ahora - 60, "1h": [{"t": (self.CIERRE - 1) * self.H * 1000, "c": 9.0, "v": 1.0}], "funding": []}
        self.assertIsNone(c.series_cerebro("ETH", "1h", 1200, ahora)[0])


class Limites(unittest.TestCase):
    def test_el_apalancamiento_de_simulado_no_llega_al_piloto_real(self):
        from riesgo import APALANCAMIENTO_MAX_PILOTO, limites_efectivos
        from tests.comunes import config
        c = config()
        c["riesgo"]["apalancamiento_max"] = 5
        self.assertEqual(limites_efectivos(c)["apalancamiento_max"], 5)
        c["modo"] = "real"
        self.assertEqual(limites_efectivos(c)["apalancamiento_max"], APALANCAMIENTO_MAX_PILOTO)
        c["piloto_real"]["apalancamiento_max"] = 5                 # solo si el piloto lo permite expresamente
        self.assertEqual(limites_efectivos(c)["apalancamiento_max"], 5)
        c["piloto_real"]["apalancamiento_max"] = 10                # y nunca más que el general
        self.assertEqual(limites_efectivos(c)["apalancamiento_max"], 5)

    def test_mercados_del_piloto_admite_todo_el_universo(self):
        from bot import mercado_en_piloto
        from tests.comunes import config
        c = config()
        self.assertEqual(c["piloto_real"]["mercados"], ["BTC", "ETH"])        # por defecto, prudente
        self.assertEqual(c["piloto_real"]["apalancamiento_max"], 3)
        self.assertTrue(mercado_en_piloto(c, "BTC"))
        self.assertFalse(mercado_en_piloto(c, "kPEPE"))
        c["piloto_real"]["mercados"] = ["*"]
        self.assertTrue(mercado_en_piloto(c, "kPEPE"))


class ListonPorFamilias(unittest.TestCase):
    def test_variantes_de_una_familia_no_suben_el_liston(self):
        import tempfile
        import validacion as vd
        with tempfile.TemporaryDirectory() as d:
            rv = vd.RegistroVariantes(os.path.join(d, "v.json"))
            ideas = {f"inv:{k}": {"disparador": {"tipo": "rsi", "n": k}, "intervalo": "1h"} for k in range(200)}
            rv.añadir(list(ideas), familias={i: vd.familia_idea(x) for i, x in ideas.items()})
            self.assertEqual((rv.total(), rv.efectivas()), (200, 1))
            nueva = {"disparador": {"tipo": "banda"}, "intervalo": "4h"}           # un TIPO nuevo sí cuenta
            rv.añadir(["inv:nueva"], familias={"inv:nueva": vd.familia_idea(nueva)})
            self.assertEqual(rv.efectivas(), 2)
            rv.añadir(["lab:abc", "lab:def", "cerebro:v1:x"])                 # sin familia: antiguas + cerebro
            self.assertEqual(rv.efectivas(), 4)
            rv.guardar()
            self.assertEqual(vd.RegistroVariantes(os.path.join(d, "v.json")).efectivas(), 4)
            self.assertLess(vd.t_requerido(rv.efectivas(), n_ops=60), vd.t_requerido(rv.total(), n_ops=60))


class PresupuestoGroq(unittest.TestCase):
    """El 19/11/2026 Groq respondió 413: petición 9485 tokens frente a un límite de 8000 por minuto."""

    def datos(self, n):
        return {"modo": "simulado", "posiciones": [], "gramatica_ideas": {"x": 1},
                "cerradas_recientes": [{"trade_id": f"t{i}", "moneda": "BTC", "pnl_neto": 1.2345 + i, "r_neto": 0.123456, "texto": "x" * 150, "cerrada_ts": i}
                                       for i in range(n)],
                "laboratorio": [{"clave": f"e{i}", "oos_r": 0.1234567} for i in range(30)]}

    def test_recorta_hasta_caber_y_lo_avisa(self):
        d = self.datos(90)
        self.assertGreater(analista_ia.tokens_estimados(d, analista_ia.INSTRUCCIONES), 8000)
        out = analista_ia.ajustar_a_presupuesto(d, analista_ia.INSTRUCCIONES, 2000)
        self.assertLessEqual(analista_ia.tokens_estimados(out, analista_ia.INSTRUCCIONES), analista_ia.TPM_GROQ - 2000 - analista_ia.MARGEN_TPM)
        self.assertIn("nota_recorte", out)
        self.assertEqual(out["cerradas_recientes"][-1]["trade_id"], "t89")        # se conservan las más recientes
        self.assertEqual(len(d["cerradas_recientes"]), 90)                       # no muta el original

    def test_si_ya_cabe_no_toca_nada(self):
        d = self.datos(3)
        d["laboratorio"] = d["laboratorio"][:3]
        self.assertEqual(analista_ia.ajustar_a_presupuesto(d, analista_ia.INSTRUCCIONES, 2000), d)


class EstudioSalidas(unittest.TestCase):
    def test_resumen(self):
        filas = [{"disparo": "a", "salida": "corta", "n": 10, "r_senal": -0.2, "r_aleatoria": -0.1},
                 {"disparo": "a", "salida": "larga", "n": 30, "r_senal": 0.2, "r_aleatoria": 0.1},
                 {"disparo": "b", "salida": "corta", "n": 10, "r_senal": 0.0, "r_aleatoria": -0.1},
                 {"disparo": "b", "salida": "larga", "n": 30, "r_senal": 0.0, "r_aleatoria": 0.1}]
        r = investigacion.resumir_estudio(filas)
        self.assertEqual(r["por_salida"]["larga"]["ops"], 60)
        self.assertEqual(r["por_salida"]["larga"]["r_senal"], 0.1)
        self.assertEqual(r["rango_entre_salidas_aleatoria"], 0.2)
        self.assertEqual(r["rango_entre_disparos_senal"], 0.0)
        self.assertEqual(investigacion.resumir_estudio([])["rango_entre_salidas_senal"], None)

    def test_las_entradas_del_estudio_son_de_la_gramatica(self):
        for d in investigacion.ESTUDIO_DISPAROS:
            self.assertTrue(investigacion.idea_valida({"disparador": d, "filtros": [], "salida": "media", "sl_atr": 2.0, "intervalo": "4h"}), d)


class EstudioRegimen(unittest.TestCase):
    def par(self, iv, sin, con):
        return {"intervalo": iv, "disparo": "x", "n_sin": 50, "n_con": 40, "r_sin": sin, "r_con": con}

    def test_mejora_consistente(self):
        r = investigacion.resumir_regimen([self.par("4h", -0.1, 0.1)] * 10)
        self.assertEqual((r["pares"], r["mejora_en"]), (10, 10))
        self.assertLess(r["p_signos"], 0.01)
        self.assertIn("pista, no una estrategia", r["lectura"])

    def test_mezcla_no_se_lleva_a_investigacion(self):
        filas = [self.par("1h", -0.1, 0.1), self.par("1h", 0.1, -0.1)] * 3
        r = investigacion.resumir_regimen(filas)
        self.assertEqual(r["mejora_en"], 3)
        self.assertGreater(r["p_signos"], 0.5)
        self.assertIn("no se lleva a investigación", r["lectura"])
        self.assertEqual(r["por_intervalo"]["1h"]["pares"], 6)

    def test_sin_pares(self):
        self.assertEqual(investigacion.resumir_regimen([])["pares"], 0)


class ContraMercado(unittest.TestCase):
    @staticmethod
    def f(lado, bruto, com=0.1):
        return {"lado": lado, "pnl_bruto": bruto, "comisiones": com, "pnl_neto": bruto - com}

    def test_ganar_en_cortos_con_mercado_a_la_baja_es_mercado(self):
        # Cuatro cortos que ganan y un largo que pierde: todo corto habría ganado más.
        r = vd.contra_mercado([self.f("S", 2), self.f("S", 2), self.f("S", 2), self.f("S", 2), self.f("L", -3)])
        self.assertEqual((r["cortos"], r["largos"]), (4, 1))
        self.assertAlmostEqual(r["bot_usd"], 4.5)
        self.assertAlmostEqual(r["todo_corto_usd"], 10.5)
        self.assertFalse(r["mejor_que_todo_corto"])
        self.assertIn("caída del mercado", r["lectura"])

    def test_elegir_bien_la_direccion_suma(self):
        r = vd.contra_mercado([self.f("S", 2), self.f("L", 2)])        # el largo gana: el mercado subió en esa
        self.assertTrue(r["mejor_que_todo_corto"])
        self.assertIn("sumó", r["lectura"])

    def test_sin_datos_y_en_evaluar(self):
        self.assertEqual(vd.contra_mercado([])["n"], 0)
        v = vd.evaluar(lab(), [dict(op(1.0), lado="S", pnl_bruto=1.1, comisiones=0.1)], ahora=DENTRO)
        self.assertEqual(v["contra_mercado"]["n"], 1)
        # No cambia el veredicto ni los criterios de la prueba.
        self.assertEqual([c["clave"] for c in v["criterios"]], ["laboratorio", "vivo", "carry"])


class Gramatica(unittest.TestCase):
    def test_idea_valida(self):
        self.assertTrue(investigacion.idea_valida(IDEA))
        for mala in ({}, dict(IDEA, sl_atr=9), dict(IDEA, extra=1), dict(IDEA, filtros=[{"tipo": "x"}]),
                     dict(IDEA, disparador={"tipo": "ruptura", "n": 7}), dict(IDEA, disparador={"tipo": "ruptura"}),
                     dict(IDEA, disparador={"tipo": "cruce_medias", "rapida": 20, "lenta": 30, "x": 1})):
            self.assertFalse(investigacion.idea_valida(mala), mala)


class PromptEsceptico(unittest.TestCase):
    """CP-M06 (auditoría 26/11, IA-01): funding_contra = lado × funding (motor.py, bot.py). Con funding positivo el
    largo PAGA, así que funding_contra > 0 es funding EN CONTRA. El prompt decía lo contrario."""

    def test_funding_contra_en_contra(self):
        txt = analista_ia.INSTRUCCIONES_ESCEPTICO
        self.assertIn("funding_contra > 0 = el funding juega EN CONTRA del lado (lo paga)", txt)
        self.assertNotIn("juega a favor del lado", txt)

