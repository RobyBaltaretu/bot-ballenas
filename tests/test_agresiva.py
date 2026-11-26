"""Cuenta agresiva simulada: reglas, tamaño, liquidación, recorrido de velas, frenos, motor con API falsa (sin red) y que
sigue aislada del bot y sin ningún camino a órdenes reales."""

import json
import os
import tempfile
import unittest

from agresiva import logica as L
from agresiva.cuenta import Cuenta, estado_nuevo, migrar_estado
from agresiva.historia import monte_carlo, rendimientos_diarios, simular, universo_por_dia
from agresiva.motor import MotorAgresiva, barrer, simbolo_binance, tramos_margen

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q = L.QUINCE_MIN_MS


def vela(t, o, h, l, c, v=100.0):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


def serie_ruptura(n=80, base=100.0):
    """Subida suave y, al final, una vela que rompe el máximo de las 20 previas con mucho volumen."""
    velas = []
    for i in range(n - 1):
        p = base + i * 0.05
        velas.append(vela(i * Q, p, p + 0.2, p - 0.2, p + 0.02))
    p = base + (n - 1) * 0.05
    velas.append(vela((n - 1) * Q, p, p + 2.0, p - 0.1, p + 1.9, v=500.0))
    return velas


class Reglas(unittest.TestCase):
    def setUp(self):
        self.c = L.cfg()

    def test_ruptura_con_volumen_da_largo(self):
        det = L.detectar(serie_ruptura(), self.c)
        self.assertIsNotNone(det)
        self.assertEqual((det["regla"], det["lado"]), ("ruptura_15m", 1))

    def test_sin_volumen_no_hay_ruptura(self):
        velas = serie_ruptura()
        velas[-1]["v"] = 100.0
        det = L.detectar(velas, L.cfg(reglas=["ruptura_15m"]))
        self.assertIsNone(det)

    def test_pocas_velas_no_dan_senal(self):
        self.assertIsNone(L.detectar(serie_ruptura()[-30:], self.c))

    def test_detectar_en_la_serie_coincide_con_la_ventana(self):
        velas = serie_ruptura(120)
        ind = L.indicadores(velas)
        self.assertEqual(L.detectar_en(velas, len(velas) - 1, ind, self.c)["regla"], L.detectar(velas, self.c)["regla"])

    def test_plan_stop_recortado_y_objetivos_en_r(self):
        pl = L.plan(1, 100.0, 0.1, self.c)                 # ATR diminuto: el stop sube al mínimo (0,8 %)
        self.assertAlmostEqual(pl["stop_pct"], 0.8)
        self.assertAlmostEqual(pl["stop"], 99.2)
        self.assertAlmostEqual(pl["objetivos"][0], 100.4)  # 0,5 R
        pl = L.plan(-1, 100.0, 10.0, self.c)               # ATR enorme: el stop baja al máximo (3 %)
        self.assertAlmostEqual(pl["stop"], 103.0)
        self.assertAlmostEqual(pl["objetivos"][-1], 91.0)  # 3 R en corto

    def test_configuracion_incoherente_se_rechaza(self):
        with self.assertRaises(ValueError):
            L.cfg(reparto_objetivos=[0.5, 0.5])
        with self.assertRaises(ValueError):
            L.cfg(stop_min_pct=5, stop_max_pct=1)


class TamanoYLiquidacion(unittest.TestCase):
    def setUp(self):
        self.c = L.cfg()

    def test_riesgo_fijo_y_el_apalancamiento_solo_decide_el_margen(self):
        """Auditoría F8: la agresiva arriesga riesgo_pct (5 %) hasta el stop, sea cual sea el máximo de la moneda."""
        for apal_max in (20, 40):
            t = L.tamano_agresiva(232, 232, 0, 10.0, 1.5, 2, apal_max, [], self.c)
            self.assertTrue(t["ok"])
            self.assertAlmostEqual(t["riesgo_pct"], 5.0, delta=0.05)
            self.assertAlmostEqual(t["notional_usd"] * (0.015 + 2 * 0.00045), 11.6, delta=0.1)
            self.assertEqual(t["apal"], min(20, apal_max))
            self.assertAlmostEqual(t["margen_usd"], t["notional_usd"] / t["apal"])
            self.assertFalse(t["recortado"])

    def test_si_el_margen_no_cabe_se_arriesga_menos(self):
        t = L.tamano_agresiva(232, 232, 0, 10.0, 0.8, 2, 3, [], self.c)       # 3× y stop corto: el margen pasaría del 30 %
        self.assertTrue(t["recortado"])
        self.assertAlmostEqual(t["margen_usd"], 232 * 0.30, delta=0.1)
        self.assertLess(t["riesgo_pct"], 5.0)

    def test_tramos_de_margen_bajan_el_apalancamiento(self):
        t = L.tamano_agresiva(10_000, 10_000, 0, 10.0, 1.5, 2, 40, [(0, 40), (5_000, 10)], self.c)
        self.assertEqual(t["apal"], 10)

    def test_margen_total_maximo(self):
        t = L.tamano_agresiva(232, 232, 232 * 0.9, 10.0, 1.5, 2, 20, [], self.c)
        self.assertFalse(t["ok"])
        self.assertIn("margen", t["motivo"])

    def test_minimo_de_diez_dolares(self):
        """Auditoría F2: Hyperliquid no admite órdenes de menos de 10 $."""
        self.assertIn("10 $", L.tamano_agresiva(5, 5, 0, 10.0, 3.0, 2, 20, [], self.c)["motivo"])
        self.assertIn("10 $", L.tamano_gemela(10, 10, 10.0, 3.0, 2, 20, self.c)["motivo"])

    def test_parciales_redondeados_y_juntados_si_no_llegan_a_diez(self):
        """Auditoría F2 y F6: cada objetivo cierra una cantidad válida para la moneda y de al menos 10 $."""
        objetivos = [100.5, 101, 101.5, 102, 103]
        tam = L.tamanos_objetivos(1.23, objetivos, [0.2] * 5, 2, 10.0)
        self.assertEqual(tam, [0.24, 0.25, 0.24, 0.25, 0.25])
        self.assertAlmostEqual(sum(tam), 1.23)
        tam = L.tamanos_objetivos(0.3, objetivos, [0.2] * 5, 3, 10.0)          # 30 $ en total: 6 $ por objetivo no llega
        self.assertTrue(all(q == 0 or q * 100 >= 10 for q in tam))
        self.assertAlmostEqual(sum(tam), 0.3)
        self.assertGreater(tam[-1], 0)

    def test_gemela_arriesga_el_dos_por_ciento(self):
        t = L.tamano_gemela(232, 232, 100.0, 1.0, 4, 20, self.c)
        perdida = t["sz"] * 100.0 * (0.01 + 2 * 0.00045)
        self.assertAlmostEqual(perdida, 4.64, delta=0.05)
        self.assertLessEqual(t["apal"], 5)

    def test_liquidacion_como_hyperliquid(self):
        self.assertAlmostEqual(L.precio_liquidacion(1, 100, 3, 3), 80.0)
        self.assertAlmostEqual(L.precio_liquidacion(1, 100, 20, 20), 97.4359, places=3)
        self.assertGreater(L.precio_liquidacion(-1, 100, 20, 40), 100)


class Recorrido(unittest.TestCase):
    def setUp(self):
        self.c = L.cfg()
        self.pl = L.plan(1, 100.0, 1.0, self.c)            # stop 98,5; objetivos 100,75 101,5 102,25 103 104,5

    def pierna(self, apal=20, apal_max=40, pl=None):
        return L.nueva_pierna("agresiva", 1, 100.0, 2.0, apal, apal_max, pl or self.pl, 0.09, 0, 232)

    def test_objetivo_1_cierra_un_quinto_y_sube_el_stop_a_la_entrada(self):
        p = self.pierna()
        delta, ev = L.avanzar(p, vela(60_000, 100, 100.9, 99.9, 100.8), self.c)
        self.assertEqual([e["tipo"] for e in ev], ["objetivo_1"])
        self.assertAlmostEqual(p["sz"], 1.6)
        self.assertEqual(p["stop"], 100.0)
        self.assertGreater(delta, 0)

    def test_tocar_el_objetivo_sin_cruzarlo_no_llena(self):
        p = self.pierna()
        L.avanzar(p, vela(60_000, 100, 100.75, 99.9, 100.5), self.c)
        self.assertEqual(p["toc"], 0)

    def test_todos_los_objetivos(self):
        p = self.pierna()
        L.avanzar(p, vela(60_000, 100, 105, 99.9, 104.8), self.c)
        self.assertEqual(p["salida"], "objetivo_5")
        self.assertEqual(p["sz"], 0)
        self.assertGreater(L.resultado_r(p), 1.5)

    def test_stop_con_deslizamiento(self):
        p = self.pierna()
        L.avanzar(p, vela(60_000, 100, 100.2, 98.0, 98.3), self.c)
        self.assertEqual(p["salida"], "stop")
        self.assertLess(p["salida_px"], 98.5)
        self.assertLess(L.resultado_r(p), -1)

    def test_vela_bajista_baja_antes_de_subir(self):
        p = self.pierna()                                  # o→h→l→c: toca el objetivo 1 antes y el stop pasa a la entrada
        L.avanzar(p, vela(60_000, 100, 100.9, 98.0, 99.0), self.c)
        self.assertEqual(p["salida"], "stop_entrada")
        p = self.pierna()                                  # o→l→h→c: el stop salta primero
        L.avanzar(p, vela(60_000, 100, 100.9, 98.0, 100.5), self.c)
        self.assertEqual(p["salida"], "stop")

    def test_liquidacion_por_el_libro_conserva_el_margen_que_sobra(self):
        """Auditoría F3: como en Hyperliquid, una liquidación por el libro devuelve lo que sobre del margen aislado."""
        pl = L.plan(1, 100.0, 2.0, self.c)                 # stop a 3 %; a 20× con máximo 20× la liquidación está a ~2,56 %
        p = self.pierna(apal=20, apal_max=20, pl=pl)
        self.assertGreater(p["liq"], p["stop"])
        margen = p["margen0"]
        delta, ev = L.avanzar(p, vela(60_000, 100, 100.1, 96.0, 96.5), self.c)
        self.assertEqual(ev[0]["tipo"], "liquidacion")
        self.assertNotIn("rescate", ev[0])
        self.assertGreater(delta, 0.0)                     # vuelve algo: ~el mantenimiento menos deslizamiento y comisión
        self.assertLess(delta, margen * 0.6)
        self.assertGreater(p["pnl_usd"], -0.09 - margen)

    def test_hueco_mas_alla_de_la_liquidacion_es_un_rescate_y_pierde_todo(self):
        pl = L.plan(1, 100.0, 2.0, self.c)
        p = self.pierna(apal=20, apal_max=20, pl=pl)
        delta, ev = L.avanzar(p, vela(60_000, 90.0, 90.5, 89.0, 89.5), self.c)
        self.assertTrue(ev[0].get("rescate"))
        self.assertEqual(delta, 0.0)
        self.assertAlmostEqual(p["pnl_usd"], -0.09 - p["margen0"])

    def test_objetivos_saltados_en_un_hueco_se_llenan_a_su_precio(self):
        """Auditoría F5: si la vela ya abre más allá de un objetivo, la orden límite se llenó al cruzarlo, a su precio."""
        p = self.pierna()
        delta, ev = L.avanzar(p, vela(60_000, 101.6, 101.9, 101.55, 101.8), self.c)
        self.assertEqual([e["tipo"] for e in ev], ["objetivo_1", "objetivo_2"])
        self.assertEqual([e["px"] for e in ev], [100.75, 101.5])
        self.assertEqual(p["stop"], 100.0)
        L.avanzar(p, vela(120_000, 101.8, 101.8, 99.0, 99.2), self.c)
        self.assertEqual(p["salida"], "stop_entrada")
        self.assertGreater(p["pnl_usd"], 0)

    def test_disparo_tipo_precio_de_marca(self):
        """Auditoría F4: una mecha que solo se imprime en Hyperliquid no salta el stop; si Binance también llega, sí."""
        v = vela(60_000, 100, 100.2, 98.0, 99.9)
        p = self.pierna()
        L.avanzar(p, L.vela_disparo(v, vela(60_000, 100, 100.2, 99.4, 99.9), 1), self.c)
        self.assertEqual(p["sz"], 2.0)
        p = self.pierna()
        L.avanzar(p, L.vela_disparo(v, vela(60_000, 100, 100.2, 98.2, 99.9), 1), self.c)
        self.assertEqual(p["salida"], "stop")
        self.assertIs(L.vela_disparo(v, None, 1), v)
        corto = L.vela_disparo(vela(0, 100, 103, 99.8, 100.1), vela(0, 100, 100.5, 99.8, 100.1), -1)
        self.assertEqual(corto["h"], 100.5)

    def test_hueco_de_apertura_llena_a_la_apertura(self):
        p = self.pierna(apal=5, apal_max=40)
        L.avanzar(p, vela(60_000, 97.0, 97.5, 96.5, 97.2), self.c)
        self.assertEqual(p["salida"], "stop")
        self.assertLess(p["salida_px"], 97.0)

    def test_funding(self):
        p = self.pierna()
        self.assertAlmostEqual(L.aplicar_funding(p, 100.0, 0.0001), -0.02)     # un largo paga con tasa positiva

    def test_funding_va_al_margen_aislado_y_mueve_la_liquidacion(self):
        """Auditoría F7: el funding entra y sale del margen de la pierna, como en Hyperliquid."""
        p = self.pierna(apal=20, apal_max=20)
        liq0, margen0 = p["liq"], L.margen_restante(p)
        L.aplicar_funding(p, 100.0, 0.001)
        self.assertAlmostEqual(L.margen_restante(p), margen0 - 0.2)
        self.assertGreater(p["liq"], liq0)                                   # con menos margen, liquida antes
        delta, _ = L.cerrar_mercado(p, 100.0, self.c, 60_000, "tiempo")
        self.assertAlmostEqual(delta, margen0 - 0.2 - 2 * 100.0 * (1 - 0.0005) * 0.00045 - 2 * 100.0 * 0.0005, places=6)

    def test_pierna_antigua_sin_mantenimiento_sigue_funcionando(self):
        p = self.pierna()
        del p["mmr"], p["margen_extra"]
        L.avanzar(p, vela(60_000, 100, 100.9, 99.9, 100.8), self.c)
        self.assertEqual(p["toc"], 1)


class CuentaYFrenos(unittest.TestCase):
    def setUp(self):
        self.c = L.cfg()
        self.cu = Cuenta(estado_nuevo(1_000_000.0, 232.0), self.c)
        self.mercado = {"sz_dec": 4, "apal_max": 20, "tramos": []}

    def abrir(self, coin="BTC", precio=100.0, ahora=1_000_000.0):
        det = {"regla": "ruptura_15m", "lado": 1, "precio": precio, "atr": 1.0, "t": 0}
        return self.cu.abrir(coin, det, self.mercado, {}, lambda compra, sz: precio, ahora)

    def test_abrir_crea_las_dos_piernas_y_descuenta_margen(self):
        s = self.abrir()
        self.assertEqual(s["agresiva"]["apal"], 20)
        self.assertEqual(s["gemela"]["apal"], 5)
        self.assertAlmostEqual(self.cu.d["agresiva"]["libre_usd"], 232 - s["agresiva"]["margen0"] - s["agresiva"]["comisiones_usd"])
        self.assertAlmostEqual(self.cu.equity_agresiva({"BTC": 100.0}), 232 - s["agresiva"]["comisiones_usd"])

    def test_la_agresiva_abre_aunque_la_gemela_no_pueda(self):
        """Auditoría F1: antes, si la gemela no podía abrir (sin saldo), tampoco abría la agresiva."""
        self.cu.d["gemela"]["libre_usd"] = 0.0
        s = self.abrir()
        self.assertIsNone(s["gemela"])
        self.assertTrue(s["sin_gemela"])
        self.assertIsNotNone(s["agresiva"])
        self.assertEqual(self.cu.d["contadores"]["solo_agresiva"], 1)
        self.cu.avanzar("BTC", vela(60_000_000, 100, 105, 99.9, 104.9))
        f = self.cu.d["cerradas"][-1]
        self.assertIsNone(f["gemela"])
        self.assertEqual(f["agresiva"]["salida"], "objetivo_5")

    def test_sin_ninguna_pierna_es_un_error(self):
        self.cu.d["gemela"]["libre_usd"] = 0.0
        self.cu.d["agresiva"]["estado"] = "quebrada"
        self.assertIn("ni gemela", self.abrir()["error"])

    def test_tres_abiertas_como_maximo(self):
        for coin in ("A", "B", "C"):
            self.assertNotIn("error", self.abrir(coin))
        self.assertIn("sin hueco", self.abrir("D")["error"])

    def test_cerrar_archiva_con_r_y_porcentaje(self):
        self.abrir()
        self.cu.avanzar("BTC", vela(60_000_000, 100, 105, 99.9, 104.9))
        self.assertEqual(self.cu.d["abiertas"], {})
        f = self.cu.d["cerradas"][-1]
        self.assertEqual(f["agresiva"]["salida"], "objetivo_5")
        self.assertGreater(f["agresiva"]["pct_cuenta"], f["gemela"]["pct_cuenta"])

    def test_cierre_por_tiempo(self):
        self.abrir(ahora=0.0)
        self.cu.avanzar("BTC", vela(48 * 3_600_000, 100, 100.2, 99.8, 100.1))
        self.assertEqual(self.cu.d["cerradas"][-1]["gemela"]["salida"], "tiempo")

    def test_quiebra_cierra_y_para_pero_la_gemela_sigue(self):
        self.abrir()
        self.cu.d["agresiva"]["libre_usd"] = 1.0                       # forzamos la cuenta casi a cero
        ev = self.cu.frenos(1_000_100.0, {"BTC": 96.5})
        self.assertEqual(ev[0]["tipo"], "quiebra")
        self.assertEqual(self.cu.d["agresiva"]["estado"], "quebrada")
        self.assertIn("BTC", self.cu.d["abiertas"])                    # la gemela sigue abierta
        self.assertEqual(self.cu.d["abiertas"]["BTC"]["agresiva"]["salida"], "quiebra")
        s = self.abrir("ETH")
        self.assertIsNone(s["agresiva"])
        self.assertIn("quebrada", s["sin_agresiva"])

    def test_freno_de_caida_pausa_una_vez(self):
        self.cu.d["agresiva"]["libre_usd"] = 110.0
        ev = self.cu.frenos(1_000_000.0, {})
        self.assertEqual(ev[0]["tipo"], "freno_caida")
        self.assertFalse(self.cu.puede_abrir_agresiva(1_000_100.0)[0])
        self.assertTrue(self.cu.puede_abrir_agresiva(1_000_000.0 + 25 * 3600)[0])
        self.assertEqual([e["tipo"] for e in self.cu.frenos(1_000_000.0 + 25 * 3600, {})], [])

    def test_freno_diario(self):
        self.cu.frenos(1_000_000.0, {})
        self.cu.d["agresiva"]["libre_usd"] = 190.0
        ev = self.cu.frenos(1_000_500.0, {})
        self.assertEqual(ev[0]["tipo"], "freno_diario")
        self.assertEqual(self.cu.d["agresiva"]["pausa_hasta"] % 86400, 0)

    def test_cuenta_antigua_se_migra_y_anota_el_cambio(self):
        d = estado_nuevo(0, 232.0)
        d["version"] = 1
        d["contadores"].pop("solo_agresiva")
        cambios = migrar_estado(d, 5.0)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(d["version"], 2)
        self.assertIn("riesgo fijo", d["cambios_reglas"][0]["texto"])
        self.assertEqual(migrar_estado(d, 6.0), [])

    def test_reinicio_cuenta_la_etapa_y_conserva_historial(self):
        self.abrir()
        self.cu.avanzar("BTC", vela(60_000_000, 100, 105, 99.9, 104.9))
        antes, _ = self.cu.reiniciar({}, 2_000_000.0)
        self.assertEqual(antes["etapa"], 1)
        self.assertEqual(self.cu.d["etapa"]["n"], 2)
        self.assertEqual(self.cu.d["agresiva"]["libre_usd"], 232.0)
        self.assertEqual(len(self.cu.d["cerradas"]), 1)


class Historia(unittest.TestCase):
    def test_simular_y_monte_carlo(self):
        series = {"BTC": serie_ruptura(200)}
        for i in range(200, 260):                                     # tras la ruptura, sigue subiendo
            p = series["BTC"][-1]["c"]
            series["BTC"].append(vela(i * Q, p, p + 1.0, p - 0.1, p + 0.9))
        cuenta, quiebras = simular(series, {"BTC": {"sz_dec": 4, "apal_max": 40, "tramos": []}}, L.cfg())
        self.assertGreaterEqual(len(cuenta.d["cerradas"]), 1)
        self.assertEqual(quiebras, [])
        mc = monte_carlo([5.0, -3.0, 2.0], 50, corridas=200)
        self.assertEqual(mc["corridas"], 200)
        self.assertEqual(mc["unidad"], "días")
        self.assertEqual(monte_carlo([-60.0], 10, corridas=10)["prob_quiebra_pct"], 100.0)

    def test_rendimientos_por_dia_juntan_las_operaciones_del_dia(self):
        """Auditoría F10: la ruina se sortea por días (las operaciones de un mismo día suelen ir juntas)."""
        dia = 86_400_000
        cer = [{"agresiva": {"pct_cuenta": -2.0, "cerrada_ms": dia + 10}}, {"agresiva": {"pct_cuenta": -3.0, "cerrada_ms": dia + 20}},
               {"agresiva": {"pct_cuenta": 1.0, "cerrada_ms": 3 * dia}}, {"agresiva": None}]
        self.assertEqual(rendimientos_diarios(cer, "agresiva", 0, 4 * dia), [0.0, -5.0, 0.0, 1.0])

    def test_universo_por_dia_solo_mira_dias_anteriores(self):
        """Auditoría F9: el universo de cada día sale del volumen de los 7 días ANTERIORES, nunca del propio día."""
        dia = 86_400_000
        diarias = {"A": [{"t": k * dia, "v": 100.0} for k in range(10)],
                   "B": [{"t": k * dia, "v": 50.0 if k < 9 else 1e9} for k in range(10)]}
        u = universo_por_dia(diarias, 1)
        self.assertEqual(u[9 * dia], {"A"})                    # B explota el día 9: no cuenta hasta el día 10
        self.assertNotIn(3 * dia, [k for k, v in u.items() if v])

    def test_simular_respeta_el_universo_y_cobra_funding(self):
        series = {"BTC": serie_ruptura(200)}
        for i in range(200, 260):
            p = series["BTC"][-1]["c"]
            series["BTC"].append(vela(i * Q, p, p + 1.0, p - 0.1, p + 0.9))
        mercado = {"BTC": {"sz_dec": 4, "apal_max": 40, "tramos": []}}
        cuenta, _ = simular(series, mercado, L.cfg(), universo={})
        self.assertEqual(cuenta.d["contadores"]["senales"], 0)
        funding = {"BTC": {series["BTC"][k]["t"]: 0.01 for k in range(150, 260)}}
        cuenta, _ = simular(series, mercado, L.cfg(), funding=funding)
        self.assertLess(sum(f["gemela"]["funding_usd"] for f in cuenta.d["cerradas"] if f.get("gemela")), 0)


class Respuesta:
    def __init__(self, datos, status=200):
        self._d, self.status_code = datos, status

    def json(self):
        return self._d


class ApiFalsa:
    """Responde como /info de Hyperliquid con una moneda (BTC) que rompe al alza en la última vela de 15 min."""

    def __init__(self, ahora_ms, binance=("BTCUSDT",)):
        self.ahora_ms = ahora_ms
        self.llamadas = []
        self.binance = set(binance)

    def __call__(self, url, json=None, timeout=0):
        t = json["type"]
        self.llamadas.append(t)
        if t == "metaAndAssetCtxs":
            return Respuesta([{"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 40, "marginTableId": 7}],
                               "marginTables": [[7, {"marginTiers": [{"lowerBound": "0", "maxLeverage": 40}]}]]},
                              [{"markPx": "104", "funding": "0.0000125", "dayNtlVlm": "5e9"}]])
        if t == "candleSnapshot":
            req = json["req"]
            bloque = self.ahora_ms // Q
            if req["interval"] == "15m":
                velas = serie_ruptura(130)
                desplaz = (bloque - 130) * Q
                return Respuesta([{"t": v["t"] + desplaz, "o": str(v["o"]), "h": str(v["h"]), "l": str(v["l"]), "c": str(v["c"]),
                                   "v": str(v["v"])} for v in velas])
            return Respuesta([])
        if t == "l2Book":
            return Respuesta({"levels": [[{"px": "103.9", "sz": "50", "n": 1}], [{"px": "104.0", "sz": "50", "n": 1}]]})
        if t == "fundingHistory":
            return Respuesta([{"coin": json["coin"], "fundingRate": "0.0001", "premium": "0", "time": h}
                              for h in range(json["startTime"] // 3_600_000 * 3_600_000 + 3_600_000, json["endTime"] + 1, 3_600_000)])
        raise AssertionError(f"consulta inesperada: {t}")

    def get(self, url, params=None, timeout=0):
        """Velas de 1 min de Binance (referencia para el disparo tipo precio de marca)."""
        self.llamadas.append("binance")
        assert url.startswith("https://fapi.binance.com/fapi/v1/klines"), url
        if params["symbol"] not in self.binance:
            return Respuesta({"code": -1121}, status=400)
        return Respuesta([[t, "104", "104.5", "103.5", "104", "1", t + 59_999, "1"] for t in
                          range(params["startTime"] // 60_000 * 60_000, min(params["endTime"], self.ahora_ms), 60_000)][:1500])


class Motor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = self.tmp.name
        with open(os.path.join(self.raiz, "config.json"), "w", encoding="utf-8") as fh:
            json.dump({"modo": "simulado"}, fh)
        self.ahora = 1_800_000_000.0 + 30                              # 30 s después de cerrar una vela de 15 min

    def motor(self):
        self.api = ApiFalsa(int(self.ahora * 1000))
        return MotorAgresiva(self.raiz, post=self.api, reloj=lambda: self.ahora, esperar=lambda s: None, get=self.api.get)

    def test_abre_la_senal_y_escribe_el_estado(self):
        m = self.motor()
        r = m.pasada()
        self.assertEqual(r["estado"], "activo")
        self.assertEqual(len(r["abiertas"]), 1, r["descartadas"])
        s = r["abiertas"][0]
        self.assertEqual((s["coin"], s["regla"], s["lado"]), ("BTC", "ruptura_15m", 1))
        self.assertEqual(s["agresiva"]["apal"], 20)
        self.assertAlmostEqual(s["agresiva"]["entrada"], 104.0)
        self.assertGreater(len(s["velas"]["15m"]), 10)                  # velas para el gráfico de la señal
        self.assertEqual(s["velas"]["15m"][-1][0] % Q, 0)
        for f in ("agresiva_estado.json", "papel_agresiva.json", os.path.join("registro", "agresiva.jsonl")):
            self.assertTrue(os.path.exists(os.path.join(self.raiz, f)), f)
        self.assertEqual(MotorAgresiva(self.raiz, post=self.api, reloj=lambda: self.ahora, get=self.api.get).cuenta.d["abiertas"].keys(),
                         {"BTC"})
        self.assertTrue(4.0 < s["agresiva"]["riesgo_pct"] <= 5.0)          # 5 % con comisiones; sin ellas, algo menos

    def test_funding_pagado_una_sola_vez_por_hora(self):
        """Auditoría F7: el funding sale de fundingHistory (lo pagado de verdad) y no se cobra dos veces."""
        m = self.motor()
        m.pasada()
        self.ahora += 3600 + 60
        self.api.ahora_ms = int(self.ahora * 1000)
        m.pasada()
        s = m.cuenta.d["abiertas"].get("BTC")
        self.assertIsNotNone(s)
        pagado = s["gemela"]["funding_usd"]
        self.assertLess(pagado, 0)                                            # largo con tasa positiva: paga
        self.ahora += 120
        self.api.ahora_ms = int(self.ahora * 1000)
        m.pasada()
        self.assertEqual(m.cuenta.d["abiertas"]["BTC"]["gemela"]["funding_usd"], pagado)
        self.assertIn("fundingHistory", self.api.llamadas)

    def test_sin_binance_usa_solo_hyperliquid_y_avisa_una_vez(self):
        self.api = ApiFalsa(int(self.ahora * 1000), binance=())
        m = MotorAgresiva(self.raiz, post=self.api, reloj=lambda: self.ahora, esperar=lambda s: None, get=self.api.get)
        m.pasada()
        self.ahora += 120
        self.api.ahora_ms = int(self.ahora * 1000)
        r = m.pasada()
        self.assertEqual(r["sin_binance"], ["BTC"])
        self.assertEqual(self.api.llamadas.count("binance"), 1)

    def test_misma_vela_no_se_mira_dos_veces(self):
        m = self.motor()
        m.pasada()
        n = self.api.llamadas.count("candleSnapshot")
        self.ahora += 120                                               # dos minutos después, dentro del mismo cuarto de hora
        self.api.ahora_ms = int(self.ahora * 1000)
        m.pasada()
        self.assertEqual(self.api.llamadas.count("candleSnapshot"), n + 1)       # solo las velas de 1 min de la abierta

    def test_fuera_de_simulado_no_hace_nada(self):
        with open(os.path.join(self.raiz, "config.json"), "w", encoding="utf-8") as fh:
            json.dump({"modo": "real"}, fh)
        m = self.motor()
        r = m.pasada()
        self.assertEqual(r["estado"], "parado")
        self.assertEqual(self.api.llamadas, [])

    def test_reinicio_pedido_por_archivo(self):
        m = self.motor()
        m.pasada()
        with open(os.path.join(self.raiz, "agresiva_reinicio.json"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        r = m.pasada()
        self.assertEqual(r["etapa"]["n"], 2)
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "agresiva_reinicio.json")))

    def test_utilidades(self):
        self.assertAlmostEqual(barrer([(10, 1), (11, 1)], 1.5), (10 + 5.5) / 1.5)
        self.assertIsNone(barrer([(10, 1)], 2))
        self.assertEqual(tramos_margen({"universe": [{"name": "X", "marginTableId": 1}],
                                        "marginTables": [[1, {"marginTiers": [{"lowerBound": "0", "maxLeverage": 10}]}]]}), {"X": [(0.0, 10)]})
        self.assertEqual((simbolo_binance("BTC"), simbolo_binance("kPEPE")), ("BTCUSDT", "1000PEPEUSDT"))


class Aislada(unittest.TestCase):
    def test_ningun_archivo_del_bot_importa_agresiva(self):
        for f in sorted(os.listdir(RAIZ)):
            if f.endswith(".py"):
                with open(os.path.join(RAIZ, f), encoding="utf-8") as fh:
                    self.assertNotRegex(fh.read(), r"(?m)^\s*(from|import) agresiva\b", f)
        with open(os.path.join(RAIZ, "carry", "motor.py"), encoding="utf-8") as fh:
            self.assertNotIn("agresiva", fh.read())

    def test_el_paquete_no_tiene_llamadas_de_orden_reales(self):
        carpeta = os.path.join(RAIZ, "agresiva")
        for f in os.listdir(carpeta):
            if f.endswith(".py"):
                with open(os.path.join(carpeta, f), encoding="utf-8") as fh:
                    txt = fh.read()
                for prohibido in ("exchange.order", "Exchange(", "private_key", "HL_API_WALLET", "market_open", "usd_class_transfer",
                                  "hyperliquid.xyz/exchange", '"/exchange"', "/fapi/v1/order", "/api/v3/order", "X-MBX-APIKEY",
                                  "import papel", "from papel", "import ledger", "from ledger"):
                    self.assertNotIn(prohibido, txt, f"{f}: {prohibido}")

    def test_solo_consultas_publicas(self):
        from agresiva.motor import ErrorApi, _info
        with self.assertRaises(ErrorApi):
            _info({"type": "order"}, post=lambda *a, **k: None)
        with self.assertRaises(ErrorApi):
            _info({"type": "clearinghouseState"}, post=lambda *a, **k: None)


if __name__ == "__main__":
    unittest.main()
