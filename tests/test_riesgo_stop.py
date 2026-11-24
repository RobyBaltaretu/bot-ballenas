"""A-02: el tamaño respeta el presupuesto de pérdida en TRES escenarios de stop (base, severo y límite de la orden
hija) y nunca presenta una cifra como pérdida máxima garantizada."""

import copy
import os

from ejecucion import Ejecutor
from gestor import Gestor
from ledger import Ledger, nuevo_trade_id
from riesgo import SIN_TOPE, analisis_salida_stop, comparar_con_plan, dimensionar, escenarios_stop
from tests.comunes import LOG, ConCarpeta, MercadoFalso, config, nuevo_papel


def perdida_en_stop(lado, tam, entrada, sl_pct, fill_extra_pct, costes_frac):
    """Cálculo independiente: pérdida si el stop llena fill_extra_pct peor que el trigger (largo o corto)."""
    s = 1 if lado == "L" else -1
    trigger = entrada * (1 - s * sl_pct / 100)
    fill = trigger * (1 - s * fill_extra_pct / 100)
    return tam * s * (entrada - fill) + tam * entrada * costes_frac


class Escenarios(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.c = config()
        self.eq = 1000.0

    def dim(self, sl_pct, precio=100.0, cfg=None, eq=None, dec=4, spread=0.02, funding=0.0):
        return dimensionar(eq or self.eq, eq or self.eq, precio, sl_pct, dec, 20, cfg or self.c, spread, 1.0,
                           funding_frac=funding)

    def test_respeta_los_tres_presupuestos_largo_y_corto(self):
        r = self.c["riesgo"]
        for sl in (0.3, 0.5, 1.0, 2.0, 5.0, 10.0):
            d = self.dim(sl)
            self.assertTrue(d["ok"], (sl, d))
            esc, pres = d["escenarios_usd"], d["presupuestos_usd"]
            self.assertLessEqual(esc["base"], self.eq * r["riesgo_por_operacion_pct"] / 100 + 1e-9, sl)
            self.assertLessEqual(esc["severo"], pres["base"] * r["riesgo_severo_max_multiplo"] + 1e-9, sl)
            self.assertLessEqual(esc["limite"], self.eq * r["perdida_limite_stop_max_pct"] / 100 + 1e-9, sl)
            # Comprobación matemática independiente, largo y corto (simétrico): severo y límite.
            sup = d["supuestos"]
            coms = (d["partes_usd"]["comision_entrada"] + d["partes_usd"]["comision_salida"] +
                    d["partes_usd"]["media_horquilla"]) / d["notional"]
            for lado in ("L", "S"):
                sev = perdida_en_stop(lado, d["tam"], 100.0, sl, sup["stop_deslizamiento_severo_pct"] * 100 /
                                      (100 - (sl if lado == "L" else -sl)), coms)
                self.assertAlmostEqual(sev, esc["severo"], delta=1e-6 * max(1, sev), msg=(sl, lado))
                lim = perdida_en_stop(lado, d["tam"], 100.0, sl, sup["tolerancia_stop_pct"] * 100 /
                                      (100 - (sl if lado == "L" else -sl)), coms)
                self.assertAlmostEqual(lim, esc["limite"], delta=1e-6 * max(1, lim), msg=(sl, lado))

    def test_stop_corto_lo_limita_el_escenario_severo(self):
        d = self.dim(0.3)
        self.assertEqual(d["limitado_por"], "severo")
        self.assertLess(d["escenarios_usd"]["base"], d["presupuestos_usd"]["base"])

    def test_nunca_se_presenta_como_maximo_garantizado(self):
        d = self.dim(2.0)
        self.assertEqual(d["nota"], SIN_TOPE)
        self.assertIn("sin tope", d["nota"])

    def test_tolerancia_que_excede_el_presupuesto_no_abre(self):
        c = copy.deepcopy(self.c)
        c["riesgo"]["perdida_limite_stop_max_pct"] = 1.0        # presupuesto de 2 USD si llena en el límite
        d = self.dim(2.0, cfg=c, eq=200.0, dec=2)               # orden mínima 10 USD × 12 % ≈ 1,2 USD: cabe
        self.assertTrue(d["ok"])
        c["riesgo"]["perdida_limite_stop_max_pct"] = 0.05       # 0,1 USD: ni la orden mínima cabe
        d = self.dim(2.0, cfg=c, eq=200.0, dec=2)
        self.assertFalse(d["ok"])
        self.assertEqual(d["escenario"], "limite")
        self.assertIn("precio límite", d["motivo"])

    def test_minimo_de_10_usd_y_redondeo(self):
        d = self.dim(5.0, eq=20.0, dec=0, precio=7.0)           # 1 % de 20 = 0,2 USD; la mínima (2 u = 14 USD) arriesga más
        self.assertFalse(d["ok"])
        self.assertIn("tamaño mínimo excede riesgo", d["motivo"])
        ok = self.dim(2.0, precio=3.3, dec=1)
        self.assertTrue(ok["ok"])
        self.assertAlmostEqual(ok["tam"] * 10, round(ok["tam"] * 10))                 # redondeado hacia abajo
        self.assertGreaterEqual(ok["notional"], 10.0)

    def test_funding_previsto_entra_en_todos_los_escenarios(self):
        sin = escenarios_stop(self.c, 2.0)
        con = escenarios_stop(self.c, 2.0, funding_frac=0.002)
        for k in ("base", "severo", "limite"):
            self.assertAlmostEqual(con[k] - sin[k], 0.002)
        self.assertLess(self.dim(2.0, funding=0.002)["tam"], self.dim(2.0)["tam"])

    def test_unidades_pct_y_fracciones(self):
        e = escenarios_stop(self.c, 2.0)
        self.assertAlmostEqual(e["partes"]["trigger"], 0.02)                  # fracción del notional
        self.assertEqual(e["supuestos"]["tolerancia_stop_pct"], 10.0)         # en %
        self.assertAlmostEqual(e["limite"] - e["partes"]["trigger"] - e["partes"]["comision_entrada"]
                               - e["partes"]["comision_salida"] - e["partes"]["media_horquilla"], 0.10)

    def test_comparacion_con_plan_y_cola_del_stop(self):
        self.assertEqual(comparar_con_plan(4.0, 5.0)["ratio"], 1.25)
        self.assertIsNone(comparar_con_plan(None, 5.0))
        largo = analisis_salida_stop("L", 98.0, 97.0, 4.0, -6.0)            # salió 1 % por debajo del trigger
        self.assertAlmostEqual(largo["peor_que_trigger_pct"], 1.0204, places=3)
        self.assertEqual(largo["ratio_perdida_riesgo"], 1.5)
        corto = analisis_salida_stop("S", 102.0, 103.0, 4.0, -5.0)
        self.assertAlmostEqual(corto["peor_que_trigger_pct"], 0.9804, places=3)
        self.assertEqual(analisis_salida_stop("L", 98.0, 98.5, 4.0, -3.0)["peor_que_trigger_pct"], 0.0)


class StopConTolerancia(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.c = config(ordenes__entrada_limite=False, ordenes__tolerancia_stop_pct=5.0)
        self.m = MercadoFalso()
        self.papel, self.info = nuevo_papel(self.dir, self.m)
        ledger = Ledger(os.path.join(self.dir, "registro"))
        ej = Ejecutor(self.papel, self.info, "simulado", ledger, "simulado", LOG, self.c["ordenes"], esperar=lambda s: None)
        meta = {a["name"]: a for a in self.m.meta()["universe"]}
        self.g = Gestor(self.c, ej, self.info, "simulado", ledger, {"posiciones": {}}, meta, LOG, "simulado",
                        lambda *a, **k: None, lambda: None, None, esperar=lambda s: None)
        self.ledger = ledger

    def test_limite_del_stop_usa_la_tolerancia_configurada_reduce_only(self):
        for lado in ("L", "S"):
            moneda = "ETH" if lado == "L" else "SOL"
            plan = {"trade_id": nuevo_trade_id(), "moneda": moneda, "lado": lado, "tam": 0.05 if lado == "L" else 1.0,
                    "apalancamiento": 2, "sl_pct": 2.0, "salida": dict(self.c["salida"]), "duracion_min": 600,
                    "estrategia": "prueba_1h", "version": "1", "precio_ref": self.m.precios[moneda], "riesgo_usd": 4.0,
                    "motivo": "prueba"}
            op = self.g.abrir(plan)
            self.assertIsNotNone(op, lado)
            st = [o for o in self.papel.d["ordenes"] if o["coin"] == moneda and o["tipo"] == "stop"]
            self.assertEqual(len(st), 1)
            esperado = st[0]["trigger"] * (0.95 if lado == "L" else 1.05)
            self.assertAlmostEqual(st[0]["limite"], esperado, delta=esperado * 1e-4)
            self.assertTrue(st[0]["reduce_only"])
            self.assertIn("riesgo_post_fill", op)
        tipos = [e["tipo"] for e in self.ledger.leer()[0]]
        self.assertIn("riesgo_post_fill", tipos)

    def test_tolerancia_fuera_de_rango_no_valida(self):
        from configuracion import ErrorConfig
        for malo in (0.5, 11):
            with self.assertRaises(ErrorConfig):
                config(ordenes__tolerancia_stop_pct=malo)
