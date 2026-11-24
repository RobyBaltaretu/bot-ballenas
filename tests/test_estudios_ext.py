"""Paquete estudios_ext (13/11/2026): estudios de investigación con datos sintéticos. Ninguna prueba sale a la red."""

import json
import math
import os
import random
import shutil
import tempfile
import unittest

from tests import comunes  # noqa: F401

from estudios_ext import carry2026 as c26
from estudios_ext import datos as dt
from estudios_ext import factor_funding as ff
from estudios_ext import metricas as mt
from estudios_ext import paridad as pa
from estudios_ext import rasgos as rg
from estudios_ext import tendencia as td

D0 = 18000          # día 0 de las series sintéticas (≈ 2019)


def panel_sintetico(deriva, dias=900, semilla=1, ruido=0.01, funding=0.0, usd=5e7):
    """{moneda: {"dias": {...}, "funding": {...}}}. `deriva`: {moneda: retorno diario medio}."""
    azar = random.Random(semilla)
    panel = {}
    for m, mu in deriva.items():
        c, d = 100.0, {}
        for k in range(dias):
            o = c
            c = o * (1 + mu + ruido * azar.gauss(0, 1))
            d[D0 + k] = {"o": o, "h": max(o, c) * 1.002, "l": min(o, c) * 0.998, "c": c, "usd": usd}
        fnd = funding[m] if isinstance(funding, dict) else funding
        panel[m] = {"dias": d, "funding": {D0 + k: fnd for k in range(dias)}}
    return panel


class Metricas(unittest.TestCase):
    def test_caida_maxima_y_sharpe(self):
        self.assertAlmostEqual(mt.caida_max([0.1, -0.5, 0.2]), 0.5, places=6)
        self.assertEqual(mt.caida_max([0.01, 0.01]), 0.0)
        self.assertEqual(mt.sharpe([0.0, 0.0, 0.0]), 0.0)
        xs = [0.01, -0.005] * 200
        self.assertGreater(mt.sharpe(xs), 0)
        self.assertGreater(mt.t_dias(xs), 2)

    def test_sharpe_deflactado_entre_0_y_1_y_baja_con_mas_pruebas(self):
        azar = random.Random(3)
        xs = [0.001 + 0.01 * azar.gauss(0, 1) for _ in range(500)]
        a, b = mt.sharpe_deflactado(xs, 1), mt.sharpe_deflactado(xs, 50)
        self.assertTrue(0 <= b < a <= 1)

    def test_pbo_con_una_sola_configuracion_no_existe_y_con_ruido_ronda_la_mitad(self):
        self.assertIsNone(mt.pbo_cscv({"a": [0.01] * 400}))
        azar = random.Random(5)
        series = {str(k): [0.01 * azar.gauss(0, 1) for _ in range(640)] for k in range(8)}
        pbo = mt.pbo_cscv(series)["pbo"]
        self.assertTrue(0.25 <= pbo <= 0.75, pbo)

    def test_maximos_moviles_igual_que_el_calculo_directo(self):
        azar = random.Random(7)
        s = [azar.random() for _ in range(300)]
        for n in (1, 5, 20):
            mx, mn = dt.maximos_moviles(s, n), dt.minimos_moviles(s, n)
            for i in range(len(s)):
                if i < n:
                    self.assertIsNone(mx[i])
                else:
                    self.assertEqual(mx[i], max(s[i - n:i]))
                    self.assertEqual(mn[i], min(s[i - n:i]))

    def test_dias_incompletos_se_descartan(self):
        velas = [{"t": (D0 * 6 + k) * 4 * 3600_000, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 1} for k in range(6)]
        velas += [{"t": ((D0 + 1) * 6 + k) * 4 * 3600_000, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 1} for k in range(5)]
        self.assertEqual(list(dt.diarias(velas)), [D0])


class Tendencia(unittest.TestCase):
    def mundo(self, panel):
        m = td.Mundo(panel)
        pert, primero = m.universo_mensual(n=5)
        vols = {x: m.vol_anual(x) for x in m.monedas}
        return m, pert, primero, vols

    def test_no_mira_el_futuro(self):
        panel = panel_sintetico({"BTC": 0.002, "ETH": 0.001, "SOL": 0.0}, 900)
        m, pert, _, vols = self.mundo(panel)
        completo = {x: {n: td.estados_ventana(m, x, n, pert[x], vols[x]) for n in (5, 30)} for x in m.monedas}
        corte = 700
        recortado = {x: {"dias": {d: v for d, v in p["dias"].items() if d < D0 + corte}, "funding": p["funding"]}
                     for x, p in panel.items()}
        m2, pert2, _, vols2 = self.mundo(recortado)
        for x in m2.monedas:
            for n in (5, 30):
                corto = td.estados_ventana(m2, x, n, pert2[x], vols2[x])
                self.assertEqual(corto[:corte - 1], completo[x][n][:corte - 1], (x, n))

    def test_en_una_subida_sostenida_compra_y_gana_en_una_caida_se_queda_fuera(self):
        arriba = td.informe(panel_sintetico({"BTC": 0.004, "ETH": 0.003, "SOL": 0.003}, 900, ruido=0.01))
        self.assertGreater(arriba["exposicion_media"], 0.01)
        self.assertGreater(arriba["neto_costes"]["cagr_pct"], 0)
        abajo = td.informe(panel_sintetico({"BTC": -0.004, "ETH": -0.004, "SOL": -0.004}, 900, ruido=0.01))
        # Solo largos: nunca vende en corto, así que en una caída no gana, y está menos expuesto que en la subida.
        self.assertLess(abajo["exposicion_media"], arriba["exposicion_media"] / 2)
        self.assertLessEqual(abajo["neto_costes"]["cagr_pct"], 0)
        self.assertFalse(abajo["veredicto"]["supera"])

    def test_el_funding_de_los_largos_se_resta(self):
        base = {"BTC": 0.004, "ETH": 0.003, "SOL": 0.003}
        sin = td.informe(panel_sintetico(base, 900, funding=0.0))
        con = td.informe(panel_sintetico(base, 900, funding=0.001))
        self.assertLess(con["neto_costes_y_funding"]["cagr_pct"], sin["neto_costes_y_funding"]["cagr_pct"])

    def test_universo_exige_historia_y_volumen(self):
        panel = panel_sintetico({"BTC": 0.001, "POCO": 0.001}, 600)
        for d in panel["POCO"]["dias"].values():
            d["usd"] = 1000.0
        m = td.Mundo(panel)
        pert, primero = m.universo_mensual(n=5)
        self.assertTrue(any(pert["BTC"]))
        self.assertFalse(any(pert["POCO"]))
        self.assertGreaterEqual(primero, 365)


class FactorFunding(unittest.TestCase):
    def panel(self, a_favor):
        n = 12
        deriva = {f"M{i}": (-0.0008 if a_favor else 0.0008) * (i - 5.5) / 5.5 for i in range(n)}
        funding = {f"M{i}": 0.0003 * (i - 5.5) / 5.5 for i in range(n)}          # M11 el más caro, M0 el más barato
        return panel_sintetico(deriva, 700, funding=funding, ruido=0.015)

    def correr(self, panel, modo="normal"):
        m = td.Mundo(panel)
        pert, primero = m.universo_mensual(n=ff.N_UNIVERSO, hist=ff.HISTORIA_MIN)
        vols = {x: m.vol_anual(x, ff.VENT_VOL) for x in m.monedas}
        W = ff.construir_pesos(m, pert, vols, primero, modo)
        return m, W, ff.rendimientos(m, W, primero)[2]

    def test_la_regla_gana_si_el_funding_alto_precede_a_las_caidas_y_la_invertida_pierde(self):
        _, _, normal = self.correr(self.panel(True))
        _, _, inv = self.correr(self.panel(True), "invertida")
        self.assertGreater(mt.sharpe(normal), 1.0)
        self.assertLess(mt.sharpe(inv), 0)

    def test_neutral_en_dolares_y_cada_pata_suma_media(self):
        m, W, _ = self.correr(self.panel(True))
        j = max(i for i in range(m.T) if any(W[x][i] for x in W))
        largos = sum(w[j] for w in W.values() if w[j] > 0)
        cortos = -sum(w[j] for w in W.values() if w[j] < 0)
        self.assertAlmostEqual(largos, ff.PATA, places=6)
        self.assertAlmostEqual(cortos, ff.PATA, places=6)

    def test_solo_se_rebalancea_los_domingos(self):
        m, W, _ = self.correr(self.panel(True))
        cambios = [j for j in range(1, m.T) if any(abs(W[x][j] - W[x][j - 1]) > 1e-12 for x in W)]
        self.assertTrue(cambios)
        self.assertTrue(all(td.fecha(m.d0 + j).weekday() == 6 for j in cambios))

    def test_la_senal_aleatoria_no_gana(self):
        _, _, azar = self.correr(self.panel(True), "aleatoria")
        _, _, real = self.correr(self.panel(True))
        self.assertLess(mt.sharpe(azar), mt.sharpe(real))


class Carry(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.dir, "datos_backtest", "externo"))
        t0 = (1_700_000_000 // 28800) * 28800
        self.t0 = t0
        fr = [{"coin": "BTC", "fundingRate": "0.0001" if k < 10 * 24 else "0.0", "premium": "0", "time": (t0 + k * 3600) * 1000}
              for k in range(30 * 24)]
        perp = [{"t": (t0 + k * 14400) * 1000, "o": 100, "h": 100, "l": 100, "c": 100, "v": 1} for k in range(30 * 6)]
        spot = [{"t": (t0 + k * 28800) * 1000, "o": 100, "h": 100, "l": 100, "c": 100, "v": 1} for k in range(30 * 3)]
        for ruta, datos in ((os.path.join("datos_backtest", "funding_BTC.json"), fr),
                            (os.path.join("datos_backtest", "externo", "binance_BTCUSDT_4h_v2.json"), perp),
                            (os.path.join("datos_backtest", "externo", "binance_spot_BTCUSDT_8h_v2.json"), spot)):
            with open(os.path.join(self.dir, ruta), "w", encoding="utf-8") as fh:
                json.dump(datos, fh)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_una_operacion_cobra_el_funding_menos_las_cuatro_comisiones(self):
        datos = c26.cargar("BTC", self.dir)
        trades = c26.operaciones("BTC", datos, 20)
        self.assertEqual(len(trades), 1)
        r = trades[0]
        self.assertAlmostEqual(r["base_pct"], 0.0, places=6)
        self.assertGreater(r["funding_pct"], 2.0)                       # ≈ 9-10 días × 24 h × 0,01 %
        self.assertAlmostEqual(r["r"], r["funding_pct"] - c26.COSTE_PCT, places=3)

    def test_periodo_rentabilidad_sobre_capital_reservado(self):
        trades = c26.operaciones("BTC", c26.cargar("BTC", self.dir), 20)
        p = c26.periodo(trades, self.t0, self.t0 + 365 * 86400, 1)
        self.assertEqual(p["n"], 1)
        esperado = trades[0]["r"] / 2
        self.assertAlmostEqual(p["rentab_neta_capital_reservado_pct"], esperado, places=1)
        vacio = c26.periodo(trades, self.t0 + 400 * 86400, self.t0 + 500 * 86400, 1)
        self.assertEqual(vacio["n"], 0)

    def test_informe_sin_datos_de_otras_monedas_no_falla(self):
        res = c26.informe(self.dir, ahora=self.t0 + 31 * 86400, monedas=("BTC", "ETH"))
        self.assertEqual(res["monedas_usadas"], ["BTC"])
        self.assertEqual(res["monedas_sin_datos"], ["ETH"])
        self.assertIn("veredicto", res)


def evento(tipo, tid, ts, **kw):
    return dict({"v": 1, "id": tipo + tid, "ts": ts, "tipo": tipo, "trade_id": tid, "origen": "simulado"}, **kw)


class Paridad(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.t_fill = 1_792_756_876                 # 2026-10-23T12:01:16Z
        self.ledger = os.path.join(self.dir, "ledger.jsonl")
        base = {"moneda": "ETH", "lado": "L", "estrategia": "ruptura_4h"}
        evs = [evento("senal", "t1", "2026-10-23T12:00:56.000Z", sl_pct=1.0, contexto={"vela_ts": 1_792_742_400.0}, **base),
               evento("fill", "t1", "2026-10-23T12:01:16.723Z", rol="entrada", px=100.0, maker=True,
                      ts_exchange=self.t_fill * 1000, **base),
               evento("proteccion", "t1", "2026-10-23T12:01:17.000Z", clase="stop", trigger=99.0, **base),
               evento("decision", "t1", "2026-10-23T12:00:57.000Z", aprobada=True, plan={"exploracion_amplia": True}, **base),
               evento("cierre", "t1", "2026-10-23T14:49:37.906Z", causa="stop-loss", pnl_neto=-1.05, funding=-0.01,
                      riesgo_inicial_usd=1.0, r_neto=-1.05, **base)]
        with open(self.ledger, "w", encoding="utf-8") as fh:
            for e in evs:
                fh.write(json.dumps(e) + "\n")
        for iv, paso, filas in (("1h", 3600, [(self.t_fill // 3600 + 1) * 3600 + k * 3600 for k in range(5)]),
                                ("4h", 14400, [1_792_742_400 + 14400 + k * 14400 for k in range(3)])):
            carpeta = os.path.join(self.dir, "velas", iv)
            os.makedirs(carpeta)
            with open(os.path.join(carpeta, "ETH.jsonl"), "w", encoding="utf-8") as fh:
                for k, t in enumerate(filas):
                    baja = 98.0 if k == 1 else 100.0           # la segunda vela rompe el stop (99)
                    fh.write(json.dumps({"t": t * 1000, "o": "100", "h": "100.5", "l": str(baja), "c": "100", "v": "1"}) + "\n")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_agrupa_las_operaciones_cerradas_y_lee_la_marca_de_exploracion(self):
        ops = pa.operaciones(pa.leer_ledger(self.ledger))
        self.assertEqual(len(ops), 1)
        self.assertTrue(ops[0]["exploracion_amplia"])
        self.assertAlmostEqual(ops[0]["sl_pct_real"], 1.0)
        self.assertAlmostEqual(ops[0]["r_vivo_sin_funding"], -1.04)

    def test_reproduce_la_salida_y_no_concluye_con_una_sola_operacion(self):
        res = pa.informe(self.ledger, comunes.config(), self.dir)
        self.assertEqual(res["comparables_A"], 1)
        self.assertEqual(res["veredicto"], "sin muestra suficiente para concluir")
        fila = res["filas"][0]
        self.assertEqual(fila["causa_A"], "stop-loss")
        self.assertLess(fila["r_A"], -0.9)
        self.assertEqual(fila["causa_B"], "stop-loss")

    def test_estrategia_desconocida_no_rompe(self):
        ops = pa.operaciones(pa.leer_ledger(self.ledger))
        ops[0]["estrategia"] = "rara_4h"
        self.assertIn("motivo", pa.reproducir(ops[0], comunes.config(), self.dir))


class Rasgos(unittest.TestCase):
    def modelo(self):
        r = ["tendencia", "funding8h"]
        return {"modelos": {"4h": {"rasgos": r, "media": {"tendencia": 2.0, "funding8h": 0.0},
                                   "desv": {"tendencia": 1.0, "funding8h": 0.004}, "n": 100, "umbral_r": 0.05,
                                   "estado_laboratorio": "no_supera"}}}

    def ledger(self, n, f8):
        ruta = os.path.join(self.dir, "l.jsonl")
        with open(ruta, "w", encoding="utf-8") as fh:
            for k in range(n):
                fh.write(json.dumps({"tipo": "decision", "estrategia": "ruptura_4h", "aprobada": False,
                                     "cerebro": {"prediccion": 0.0, "faltan": [],
                                                 "rasgos": {"tendencia": 2.0 + (k % 3 - 1), "funding8h": f8 * (k % 3 - 1)}}}) + "\n")
        return ruta

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_marca_el_rasgo_con_dispersion_distinta(self):
        res = rg.informe(self.ledger(40, 0.05), self.modelo())["intervalos"]["4h"]
        self.assertEqual(res["desplazados"], ["funding8h"])
        self.assertIn("funding8h", res["veredicto"])

    def test_sin_desplazamiento_y_con_poca_muestra(self):
        ok = rg.informe(self.ledger(40, 0.004), self.modelo())["intervalos"]["4h"]
        self.assertEqual(ok["desplazados"], [])
        poco = rg.informe(self.ledger(5, 0.004), self.modelo())["intervalos"]["4h"]
        self.assertEqual(poco["veredicto"], "sin muestra suficiente para concluir")
        self.assertEqual(rg.informe(self.ledger(5, 0.004), self.modelo())["intervalos"]["1h"], {"motivo": "sin modelo"})


class NoEstaConectado(unittest.TestCase):
    RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_ningun_archivo_del_bot_importa_estudios_ext(self):
        for f in sorted(os.listdir(self.RAIZ)):
            if f.endswith(".py"):
                with open(os.path.join(self.RAIZ, f), encoding="utf-8") as fh:
                    txt = fh.read()
                self.assertNotRegex(txt, r"(?m)^\s*(from|import) estudios_ext\b", f)

    def test_el_paquete_no_opera_ni_sale_a_la_red(self):
        carpeta = os.path.join(self.RAIZ, "estudios_ext")
        for f in os.listdir(carpeta):
            if f.endswith(".py"):
                with open(os.path.join(carpeta, f), encoding="utf-8") as fh:
                    txt = fh.read()
                for prohibido in ("exchange.order", "Exchange(", "private_key", "HL_API_WALLET", "market_open",
                                  "usd_class_transfer", "import requests", "urllib", "socket", "hyperliquid", ".env"):
                    self.assertNotIn(prohibido, txt, f"{f}: {prohibido}")


if __name__ == "__main__":
    unittest.main()
