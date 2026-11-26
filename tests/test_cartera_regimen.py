"""Cambios del 13/11/2026: estrategias de 1 h retiradas, filtro de régimen de BTC, recorte ±3 del cerebro y cartera
del factor de funding. Todo contra la cuenta simulada (papel.py) y módulos falsos: sin red ni órdenes reales."""

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest import mock

import cartera_funding as cartera
import cerebro
import configuracion as conf
from tests.comunes import ConCarpeta, aislar_bot, config, nuevo_papel
from tests.test_bot import CerebroFalso, InfoFalsa, modulos_falsos, preparar_rutas

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUNES = datetime(2026, 11, 16, 0, 30, tzinfo=timezone.utc).timestamp()
MONEDAS = ["BTC", "ETH", "SOL", "AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ", "KKK", "LLL", "MMM"]


class SerieFalsa:
    def __init__(self, valor, ahora, n=168):
        self.t = [ahora - 3600 * k for k in range(n, 0, -1)]
        self.valor = valor

    def media(self, t, horas):
        return self.valor


class CtxFalso:
    def __init__(self, px, ahora, n=201):
        self.c = [px * (1.01 if k % 2 else 1.0) for k in range(n)]
        self.t = [ahora - 14400 * (n - k) for k in range(n)]

    def __len__(self):
        return len(self.c)

    def ema(self, n):
        return [sum(self.c) / len(self.c)] * len(self.c)


class Estrategias1hRetiradas(unittest.TestCase):
    def test_config_real_sin_estrategias_de_1h_y_con_los_tres_cambios(self):
        with open(os.path.join(AQUI, "config.json"), encoding="utf-8") as f:
            c = json.load(f)
        # Las técnicas de 1 h siguen retiradas (solo sombra). ballenas_1h sí opera en simulado desde el 19/11/2026 y
        # retroceso_1h desde el 21/11/2026 (Roberto: «la de 1 h que iba en positivo», +0,22 R en sombra).
        activas_1h = [k for k, v in c.get("estrategias", {}).items() if k.endswith("_1h") and v.get("activa", True)
                      and k not in ("ballenas_1h", "retroceso_1h")]
        self.assertEqual(activas_1h, [])
        self.assertTrue(c["filtros_entrada"]["regimen_btc"]["activo"])
        self.assertTrue(c["cartera_funding"]["activa"])
        self.assertEqual(c["modo"], "simulado")

    def test_defectos_no_activan_nada_nuevo_y_validan_rangos(self):
        c = config()
        self.assertFalse(c["filtros_entrada"]["regimen_btc"]["activo"])
        self.assertFalse(c["cartera_funding"]["activa"])
        for ruta, malo in (("cartera_funding__riesgo_por_operacion_pct", 9), ("cartera_funding__max_por_lado", 0),
                           ("cartera_funding__universo_max", 3)):
            with self.assertRaises(conf.ErrorConfig, msg=ruta):
                config(**{ruta: malo})


class RecorteCerebro(unittest.TestCase):
    def test_recorte_a_tres_desviaciones(self):
        self.assertEqual(cerebro.RECORTE_Z, 3.0)
        m = cerebro.Modelo(["x"], [])
        m.media, m.desv = {"x": 0.0}, {"x": 1.0}
        self.assertEqual(m._vector({"x": 50.0}, None)[1], 3.0)
        self.assertEqual(m._vector({"x": -50.0}, None)[1], -3.0)
        self.assertEqual(m._vector({"x": 2.0}, None)[1], 2.0)
        self.assertEqual(m.a_dict()["recorte"], 3.0)


class FuncionesCartera(unittest.TestCase):
    def test_semana_y_ventana_de_rebalanceo(self):
        semana = cartera.inicio_semana(LUNES)
        self.assertEqual(datetime.fromtimestamp(semana, timezone.utc).isoformat(), "2026-11-16T00:00:00+00:00")
        self.assertEqual(cartera.toca_rebalanceo(LUNES, None, 12), semana)
        self.assertIsNone(cartera.toca_rebalanceo(LUNES, semana, 12))               # ya hecho esta semana
        self.assertIsNone(cartera.toca_rebalanceo(semana + 13 * 3600, None, 12))    # tarde: esa semana no entra
        viernes = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc).timestamp()
        self.assertIsNone(cartera.toca_rebalanceo(viernes, None, 12))               # un reinicio en viernes no abre nada

    def test_seleccion_extremos_y_universo_minimo(self):
        filas = [{"moneda": f"M{k}", "volumen": 100 - k, "funding": k * 0.001, "vol": 3.0} for k in range(12)]
        largos, cortos, n = cartera.seleccionar(filas, 2, 30)
        self.assertEqual(([x["moneda"] for x in largos], [x["moneda"] for x in cortos], n), (["M0", "M1"], ["M11", "M10"], 12))
        self.assertEqual(cartera.seleccionar(filas[:8], 2, 30)[:2], ([], []))
        self.assertEqual(len(cartera.seleccionar(filas, 9, 30)[0]), 4)              # nunca más de un tercio

    def test_fila_exige_historia(self):
        ctx = CtxFalso(100.0, LUNES)
        self.assertIsNone(cartera.fila("X", 1e6, SerieFalsa(0.001, LUNES, n=50), ctx.c, LUNES))
        self.assertIsNone(cartera.fila("X", 1e6, SerieFalsa(0.001, LUNES), ctx.c[:20], LUNES))
        self.assertIsNone(cartera.fila("X", 1e6, None, ctx.c, LUNES))
        f = cartera.fila("X", 1e6, SerieFalsa(0.001, LUNES), ctx.c, LUNES)
        self.assertAlmostEqual(f["vol"], 2.44, delta=0.1)

    def test_las_dos_patas_o_ninguna(self):
        self.assertEqual(cartera.patas_nuevas(0, 0, 2, 4, 4, 6, 9), (2, 2))
        self.assertEqual(cartera.patas_nuevas(0, 0, 2, 4, 0, 6, 9), (0, 0))         # sin hueco de cortos: nada
        self.assertEqual(cartera.patas_nuevas(0, 0, 2, 4, 4, 2, 9), (1, 1))         # solo caben dos posiciones
        self.assertEqual(cartera.patas_nuevas(0, 0, 2, 4, 4, 6, 1), (0, 0))         # riesgo para una sola: nada
        self.assertEqual(cartera.patas_nuevas(1, 1, 2, 4, 4, 6, 9), (1, 1))
        self.assertEqual(cartera.equilibrar(2, 1, 0, 0), (1, 1))
        self.assertEqual(cartera.equilibrar(2, 0, 0, 0), (0, 0))
        self.assertEqual(cartera.equilibrar(1, 1, 1, 1), (1, 1))
        self.assertEqual(cartera.stop_pct(1.0, 3.0, 0.25, 12), 3.0)
        self.assertEqual(cartera.stop_pct(9.0, 3.0, 0.25, 12), 12)


class BotCarteraYRegimen(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.mods = mock.patch.dict(sys.modules, modulos_falsos(InfoFalsa))
        self.mods.start()
        import bot
        self.bot = bot
        self.rutas = {k: getattr(bot, k) for k in dir(bot) if k.startswith(("RUTA_", "DIR_")) or k == "AQUI"}
        preparar_rutas(bot, self.dir)

    def tearDown(self):
        for k, v in self.rutas.items():
            setattr(self.bot, k, v)
        self.mods.stop()
        super().tearDown()

    def nuevo(self, modo="simulado", **cambios):
        from ejecucion import Ejecutor, EjecutorShadow
        from ledger import Ledger
        from notificaciones import Telegram
        from observabilidad import Sistema
        from promocion import Registro
        c = config(tiempo_real__websocket=False, riesgo__riesgo_abierto_max_pct=9.0, riesgo__max_posiciones_abiertas=6,
                   riesgo__max_mismo_lado=4, **cambios)       # los límites de la operativa actual
        c["modo"] = modo
        info = InfoFalsa()
        info.precios = {m: 100.0 for m in MONEDAS}
        ledger = Ledger(os.path.join(self.dir, "registro"))
        if modo == "shadow":
            ej, cuenta = EjecutorShadow(), None
        else:
            papel, info = nuevo_papel(self.dir, info)
            ej, cuenta = Ejecutor(papel, info, "simulado", ledger, "simulado", self.bot.log_op, c["ordenes"],
                                  esperar=lambda s: None), "simulado"
        b = self.bot.Bot(c, info, ej, cuenta, None, Telegram(None, None), ledger, Sistema(self.dir),
                         Registro(os.path.join(self.dir, "promociones.json")))
        b.cerebro = CerebroFalso(abre=True)
        aislar_bot(b)                                # CP-M19: sin red
        b.leer_precios()
        if modo == "simulado":
            b.conciliacion_ok = b.conciliacion_inicial()
            b.c["ordenes"]["entrada_limite"] = False
        return b, ledger

    @staticmethod
    def candidata(moneda="ETH", lado="L", **extra):
        return dict({"moneda": moneda, "lado": lado, "estrategia": "ruptura_4h", "modulo": "ruptura", "version": "1",
                     "motivo": "prueba", "precio_senal": 100.0, "sl_pct": 2.0, "duracion_min": 1800, "fuerza": 1.0,
                     "salida": dict(config()["salida"]), "rasgos": {"fuerza": 1.0}, "parametros": {}, "vela_ts": 0,
                     "intervalo": "4h"}, **extra)

    def ultima(self, ledger):
        return [e for e in ledger.leer()[0] if e["tipo"] == "decision"][-1]

    # ------------------------------------------------------------ régimen de BTC
    def test_regimen_contra_no_entra_y_a_favor_si(self):
        b, ledger = self.nuevo()
        b.f["regimen_btc"] = {"activo": True, "media": 200}
        b.procesar_candidatas([self.candidata("ETH", "L", btc_alcista=False)])
        dec = self.ultima(ledger)
        self.assertFalse(dec["aprobada"])
        self.assertIn("contra el régimen de BTC", dec["motivos"][0])
        self.assertNotIn("ETH", b.estado["posiciones"])
        b.procesar_candidatas([self.candidata("SOL", "S", btc_alcista=False)])
        self.assertTrue(self.ultima(ledger)["aprobada"], self.ultima(ledger)["motivos"])
        self.assertIn("SOL", b.estado["posiciones"])

    def test_regimen_desconocido_falla_cerrado(self):
        b, ledger = self.nuevo()
        b.f["regimen_btc"] = {"activo": True, "media": 200}
        for cand in (self.candidata(btc_alcista=None), self.candidata()):      # sin dato y sin contexto de BTC
            b.procesar_candidatas([cand])
            dec = self.ultima(ledger)
            self.assertFalse(dec["aprobada"])
            self.assertIn("régimen de BTC desconocido", dec["motivos"][0])
        self.assertEqual(b.estado["posiciones"], {})

    def test_la_exploracion_amplia_no_se_salta_el_regimen(self):
        b, ledger = self.nuevo()
        b.f["regimen_btc"] = {"activo": True, "media": 200}
        b.c["exploracion_amplia"] = {"activa": True, "riesgo_por_operacion_pct": 0.25, "max_abiertas": 2}
        b.cerebro = CerebroFalso(abre=False)
        b.procesar_candidatas([self.candidata("ETH", "L", btc_alcista=False)])
        self.assertFalse(self.ultima(ledger)["aprobada"])
        self.assertEqual(b.estado["posiciones"], {})

    def test_filtro_apagado_no_cambia_nada(self):
        b, ledger = self.nuevo()
        b.procesar_candidatas([self.candidata("ETH", "L", btc_alcista=False)])
        self.assertTrue(self.ultima(ledger)["aprobada"], self.ultima(ledger)["motivos"])

    # ------------------------------------------------------------ cartera de funding
    def preparar_cartera(self, b, fundings=None):
        b.c["cartera_funding"] = dict(b.c["cartera_funding"], activa=True)
        fundings = fundings or {m: 0.001 * k for k, m in enumerate(MONEDAS)}
        b.motor.monedas = list(MONEDAS)
        b.motor.volumen = {m: 1e7 for m in MONEDAS}
        b.motor.funding_hist = {m: (LUNES, SerieFalsa(fundings[m], LUNES), []) for m in MONEDAS}
        ctxs = {m: CtxFalso(100.0, LUNES) for m in MONEDAS}
        b.motor.contexto = lambda info, m, iv: ctxs[m]
        b.motor.rasgos = lambda *a, **k: {"fuerza": 1.0}

    def test_cartera_abre_patas_equilibradas_en_simulado(self):
        b, ledger = self.nuevo()
        self.preparar_cartera(b)
        cands = b._candidatas_cartera_funding(LUNES)
        self.assertEqual(sorted((c["moneda"], c["lado"]) for c in cands),
                         [("BTC", "L"), ("ETH", "L"), ("LLL", "S"), ("MMM", "S")])
        self.assertTrue(all(c["cabe"] and c["cartera_funding"] and not c["validada"] for c in cands))
        self.assertEqual(b._candidatas_cartera_funding(LUNES + 600), [])        # una vez por semana
        b.cerebro = CerebroFalso(abre=False)                                    # no pasa por el cerebro
        b.procesar_candidatas(cands)
        pos = b.estado["posiciones"]
        self.assertEqual(sorted(pos), ["BTC", "ETH", "LLL", "MMM"], b.bloqueos)
        self.assertTrue(all(d["cartera_funding"] and d["explorando"] for d in pos.values()))
        saldo = b.ej.ex.d["saldo_inicial"]
        for d in pos.values():                                                  # 1 % por pata como mucho
            self.assertLessEqual(d.get("riesgo_plan_usd") or 0, saldo * 0.01 * 1.01)
        self.assertEqual(sum(1 for d in pos.values() if d["lado"] == "L"), 2)

    def test_cartera_no_propone_fuera_de_simulado_ni_apagada(self):
        b, _ = self.nuevo("shadow")
        self.preparar_cartera(b)
        self.assertEqual(b._candidatas_cartera_funding(LUNES), [])
        b, _ = self.nuevo()
        self.preparar_cartera(b)
        b.c["cartera_funding"]["activa"] = False
        self.assertEqual(b._candidatas_cartera_funding(LUNES), [])
        b.c["cartera_funding"]["activa"] = True
        b.modo = "real"                                                         # aunque llegara una candidata, no opera
        b.procesar_candidatas([self.candidata("ETH", "L", cartera_funding=True, cabe=True,
                                              estrategia=cartera.CLAVE, modulo=cartera.MODULO)])
        self.assertEqual(b.estado["posiciones"], {})

    def test_sin_hueco_para_las_dos_patas_no_abre_ninguna(self):
        b, ledger = self.nuevo()
        self.preparar_cartera(b)
        b.c["riesgo"]["max_mismo_lado"] = 4
        for m in ("AAA", "BBB", "CCC", "DDD"):                                  # cuatro cortos ajenos: no caben más cortos
            b.procesar_candidatas([self.candidata(m, "S", sl_pct=10.0)])
        antes = json.loads(json.dumps(b.estado["posiciones"]))
        self.assertEqual(len(antes), 4, b.bloqueos)
        cands = b._candidatas_cartera_funding(LUNES)
        self.assertTrue(cands and not any(c["cabe"] for c in cands))
        b.procesar_candidatas(cands)
        self.assertEqual(json.loads(json.dumps(b.estado["posiciones"])), antes)  # las ajenas, intactas; nada nuevo
        self.assertIn("sin hueco para las dos patas", self.ultima(ledger)["motivos"][0])

    def test_rebalanceo_solo_toca_las_patas_de_la_cartera(self):
        b, _ = self.nuevo()
        self.preparar_cartera(b)
        b.procesar_candidatas([self.candidata("DDD", "L")])                     # posición ajena a la cartera
        ajena = json.loads(json.dumps(b.estado["posiciones"]["DDD"]))
        b.procesar_candidatas(b._candidatas_cartera_funding(LUNES))
        self.assertEqual(len(b._patas_cartera()), 4, b.bloqueos)
        # Semana siguiente: BTC deja de estar en el extremo bajo y ETH sigue.
        fundings = {m: 0.001 * k for k, m in enumerate(MONEDAS)}
        fundings["BTC"] = 0.0055
        sig = LUNES + 7 * 86400
        b.motor.funding_hist = {m: (sig, SerieFalsa(fundings[m], sig), []) for m in MONEDAS}
        ctxs = {m: CtxFalso(100.0, sig) for m in MONEDAS}
        b.motor.contexto = lambda info, m, iv: ctxs[m]
        self.assertEqual(b._candidatas_cartera_funding(sig), [])                # primero salen las que sobran
        pos = b.estado["posiciones"]
        self.assertTrue(pos["BTC"].get("cartera_salir"))
        self.assertFalse(pos["ETH"].get("cartera_salir"))
        self.assertGreater(pos["ETH"]["duracion_min"], pos["BTC"]["duracion_min"])
        self.assertEqual(json.loads(json.dumps(pos["DDD"])), ajena)             # la ajena no cambia en nada

    def test_equilibrar_descarta_la_pata_sin_pareja(self):
        b, ledger = self.nuevo()
        self.preparar_cartera(b)
        cands = b._candidatas_cartera_funding(LUNES)
        b.ej.congelados["MMM"] = {"motivo": "prueba"}                           # una pata corta cae en los filtros
        b.procesar_candidatas(cands)
        pos = b.estado["posiciones"]
        self.assertEqual(sum(1 for d in pos.values() if d["lado"] == "L"),
                         sum(1 for d in pos.values() if d["lado"] == "S"), sorted(pos))
        self.assertEqual(len(pos), 2)


if __name__ == "__main__":
    unittest.main()
