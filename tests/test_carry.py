"""Carry de funding (fases 0-2): terreno, lógica y simulación de las dos patas. Todo con datos sintéticos y adaptadores
falsos: ninguna prueba sale a la red ni toca un exchange."""

import json
import math
import os
import tempfile
import unittest

from carry import ejecucion as ej
from carry import logica as lg
from carry import terreno as tr
from carry.papel_spot import ErrorSpot, PapelSpot

C = lg.cfg()


# ------------------------------------------------------------------ fase 0
def spot_meta():
    return {"tokens": [{"index": 0, "name": "USDC", "szDecimals": 8}, {"index": 5, "name": "UBTC", "szDecimals": 5},
                       {"index": 6, "name": "HYPE", "szDecimals": 2}, {"index": 7, "name": "ZZZ", "szDecimals": 2}],
            "universe": [{"name": "@1", "tokens": [5, 0]}, {"name": "@2", "tokens": [6, 0]}, {"name": "@3", "tokens": [7, 0]}]}


def ctxs(desordenados=True):
    c = [{"coin": "@1", "midPx": "70000", "dayNtlVlm": "50000000"}, {"coin": "@2", "midPx": "70", "dayNtlVlm": "900000"},
         {"coin": "@3", "midPx": "1", "dayNtlVlm": "5"}]
    return list(reversed(c)) if desordenados else c


def libro(mid, prof_usd=100_000, horquilla=0.01):
    m = mid * horquilla / 100 / 2
    n = prof_usd / mid
    return {"levels": [[{"px": str(mid - m), "sz": str(n), "n": 3}], [{"px": str(mid + m), "sz": str(n), "n": 3}]]}


class Terreno(unittest.TestCase):
    def test_se_empareja_por_nombre_no_por_posicion(self):
        # ctx en orden distinto al universo: por posición BTC habría salido con el precio de ZZZ.
        out = tr.emparejar(spot_meta(), ctxs(True), {"BTC": 70020.0, "HYPE": 70.0})
        self.assertEqual(out["BTC"]["mid"], 70000.0)
        self.assertEqual(out["BTC"]["par"], "@1")
        self.assertNotIn("ZZZ", out)

    def test_criterios(self):
        cand = tr.emparejar(spot_meta(), ctxs(), {"BTC": 70020.0, "HYPE": 70.0})
        res = tr.evaluar(cand, {"BTC": 70020.0, "HYPE": 70.0}, {"@1": libro(70000), "@2": libro(70)})
        self.assertEqual(list(res["aptas"]), ["BTC"])
        self.assertIn("volumen", res["excluidas"]["HYPE"])
        malo = tr.evaluar(cand, {"BTC": 70020.0, "HYPE": 70.0}, {"@1": libro(70000, prof_usd=1000, horquilla=0.2)})
        self.assertIn("profundidad", malo["excluidas"]["BTC"])
        self.assertIn("horquilla", malo["excluidas"]["BTC"])

    def test_base_grande_se_excluye(self):
        cand = tr.emparejar(spot_meta(), ctxs(), {"BTC": 72000.0})
        res = tr.evaluar(cand, {"BTC": 72000.0}, {"@1": libro(70000)})
        self.assertIn("base", res["excluidas"]["BTC"])

    def test_solo_consultas_publicas_de_lectura(self):
        with self.assertRaises(tr.ErrorTerreno):
            tr._info({"type": "order"}, post=lambda *a, **k: None)
        with self.assertRaises(tr.ErrorTerreno):
            tr._info({"type": "userState"}, post=lambda *a, **k: None)

    def test_generar_y_guardar(self):
        class R:
            status_code = 200

            def __init__(self, v):
                self.v = v

            def json(self):
                return self.v

        def post(url, json=None, timeout=None):
            self.assertTrue(url.endswith("/info"))
            t = json["type"]
            if t == "spotMetaAndAssetCtxs":
                return R([spot_meta(), ctxs()])
            if t == "metaAndAssetCtxs":
                return R([{"universe": [{"name": "BTC"}, {"name": "HYPE"}]}, [{"markPx": "70020"}, {"markPx": "70"}]])
            return R(libro(70000))
        orig = tr.time.sleep
        tr.time.sleep = lambda s: None
        self.addCleanup(setattr, tr.time, "sleep", orig)
        d = tr.generar(post, ahora=0)
        self.assertEqual(d["monedas_aptas"], ["BTC"])
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "datos_mercado", "spot_hl.json")
            tr.guardar(d, ruta)
            self.assertEqual(list(tr.cargar(ruta)), ["BTC"])
            self.assertEqual(tr.cargar(os.path.join(tmp, "no_existe.json")), {})


# ------------------------------------------------------------------ fase 1
def serie(h_pct, n=72):
    return [h_pct] * n


class Logica(unittest.TestCase):
    def test_coste_de_las_cuatro_operaciones(self):
        self.assertAlmostEqual(lg.coste_ida_vuelta_pct(C), 2 * (0.045 + 0.07) + 4 * 0.02)

    def test_funding_esperado_pondera_lo_reciente(self):
        antiguo_alto = [0.01] * 48 + [0.0] * 24
        f = lg.funding_esperado(antiguo_alto, C)
        self.assertLess(f["h_pct"], 0.005)             # lo reciente (cero) pesa más que lo antiguo
        self.assertIsNone(lg.funding_esperado([0.01] * 10, C))
        self.assertIsNone(lg.funding_esperado([None] * 40, C))

    def test_horas_de_amortizacion(self):
        self.assertTrue(math.isinf(lg.horas_amortizacion(0.0, C)))
        self.assertTrue(math.isinf(lg.horas_amortizacion(-0.01, C)))
        self.assertAlmostEqual(lg.horas_amortizacion(0.01, C), lg.coste_ida_vuelta_pct(C) / 0.01)

    def test_oportunidades(self):
        terreno = {"BTC": {}, "ETH": {}, "SOL": {}, "HYPE": {}}
        hist = {"BTC": serie(0.005),        # 43,8 %/año, 62 h para amortizar las comisiones
                "ETH": serie(0.0005),       # 4,4 %/año: poco
                "SOL": [0.004, -0.001] * 36,                  # negativo la mitad del tiempo
                "HYPE": serie(0.005)}
        r = lg.oportunidades(hist, {"BTC": 0.05, "ETH": 0.0, "SOL": 0.0, "HYPE": 0.9}, terreno, C, abiertas=())
        self.assertEqual([x["coin"] for x in r["entrar"]], ["BTC"])
        self.assertIn("funding", r["descartadas"]["ETH"])
        self.assertIn("base", r["descartadas"]["HYPE"])
        self.assertIn("SOL", r["descartadas"])
        self.assertIn("ya hay carry", lg.oportunidades(hist, {"BTC": 0.0}, {"BTC": {}}, C, abiertas=("BTC",))["descartadas"]["BTC"])

    def test_amortizacion_larga_descarta(self):
        c = lg.cfg(funding_min_anual_pct=1.0, horas_amortizacion_max=24)
        r = lg.oportunidades({"BTC": serie(0.002)}, {"BTC": 0.0}, {"BTC": {}}, c)     # 17,5 %/año, 155 h para amortizar
        self.assertIn("recuperarse", r["descartadas"]["BTC"])

    def test_tamano_respeta_los_limites(self):
        t = lg.tamano(200.0, [], "BTC", C)
        self.assertTrue(t["ok"])
        self.assertLessEqual(t["capital_usd"], 200 * 0.20 + 0.01)                  # tope por moneda 20 %
        self.assertAlmostEqual(t["capital_usd"], t["notional_usd"] * 1.5, places=1)   # contado + margen con 2x
        lleno = [{"coin": "A", "capital_usd": 40}, {"coin": "B", "capital_usd": 40}, {"coin": "C", "capital_usd": 40}]
        self.assertIn("máximo", lg.tamano(200.0, lleno, "D", C)["motivo"])
        mitad = lg.tamano(200.0, [{"coin": "A", "capital_usd": 99}], "B", C)                # queda 1 $ del 50 % de la cuenta
        self.assertFalse(mitad["ok"])
        self.assertFalse(lg.tamano(30.0, [], "BTC", C)["ok"])                      # 6 $ de capital: menos de 10 $ por pata

    def test_distancia_de_liquidacion(self):
        self.assertAlmostEqual(lg.distancia_liquidacion_pct(2, C), 47.5)
        self.assertAlmostEqual(lg.distancia_liquidacion_pct(5, C), 17.5)

    def test_salidas(self):
        pos = {"coin": "BTC", "abierta_ts": 0, "entrada_perp": 100.0, "apalancamiento": 5}
        ok = {"precio_perp": 100.0, "base_pct": 0.1, "funding_hist": serie(0.0035, 12), "horquilla_spot_pct": 0.01}
        self.assertEqual(lg.evaluar_salida(pos, ok, C, ahora=3600), (False, None))
        salir, m = lg.evaluar_salida(pos, dict(ok, precio_perp=112.0), C, ahora=3600)        # liquidación a 117,5
        self.assertTrue(salir)
        self.assertIn("liquidación", m)
        self.assertIn("base", lg.evaluar_salida(pos, dict(ok, base_pct=1.4), C, ahora=1)[1])
        self.assertIn("funding", lg.evaluar_salida(pos, dict(ok, funding_hist=serie(0.0001, 12)), C, ahora=1)[1])
        self.assertIn("tiempo máximo", lg.evaluar_salida(pos, ok, C, ahora=3600 * 24 * 15)[1])
        self.assertIn("liquidez", lg.evaluar_salida(pos, dict(ok, horquilla_spot_pct=0.5), C, ahora=1)[1])

    def test_sin_stop_de_precio_con_cobertura(self):
        pos = {"coin": "BTC", "abierta_ts": 0, "entrada_perp": 100.0, "apalancamiento": 2}
        ok = {"precio_perp": 70.0, "base_pct": 0.0, "funding_hist": serie(0.0035, 12)}      # cae un 30 %: no es motivo de salida
        self.assertFalse(lg.evaluar_salida(pos, ok, C, ahora=1)[0])


# ------------------------------------------------------------------ fase 2
def libro_spot(px=100.0, prof=1000.0, paso=0.01):
    return {"compras": [(px - paso, prof), (px - 5 * paso, prof)], "ventas": [(px + paso, prof), (px + 5 * paso, prof)]}


class PerpFalso:
    """Adaptador del perpetuo de prueba. fallo='abrir'|'cerrar'; relleno<1 = se llena solo esa fracción."""

    def __init__(self, fallo=None, relleno=1.0, px=100.0, funding=0.5, px_cierre=None):
        self.fallo, self.relleno, self.px, self.funding, self.px_cierre = fallo, relleno, px, funding, px_cierre
        self.abierto = {}

    def abrir_corto(self, coin, notional_usd, precio_ref):
        if self.fallo == "abrir":
            raise ej.ErrorPata("rechazada")
        sz = notional_usd / precio_ref * self.relleno
        self.abierto[coin] = sz
        return {"px": self.px, "sz": sz, "comision": sz * self.px * 0.00045}

    def cerrar_corto(self, coin, sz):
        if self.fallo == "cerrar":
            raise ej.ErrorPata("sin respuesta")
        px = self.px_cierre or self.px
        self.abierto.pop(coin, None)
        return {"px": px, "sz": sz, "comision": sz * px * 0.00045, "pnl": (self.px - px) * sz}

    def funding_cobrado(self, coin, desde_ts):
        return self.funding


class DosPatas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spot = PapelSpot(os.path.join(self.tmp.name, "papel_spot.json"), usdc=500.0)
        self.reg = ej.RegistroCarry(os.path.join(self.tmp.name, "registro", "carry.jsonl"))

    def abrir(self, perp, libro=None, notional=100.0):
        return ej.abrir_par("BTC", notional, perp, self.spot, libro or libro_spot(), 100.0, C, self.reg, sz_decimales=3, ahora=1000.0)

    def test_apertura_completa_deja_las_dos_patas_iguales(self):
        perp = PerpFalso()
        r = self.abrir(perp)
        self.assertEqual(r["estado"], "abierto")
        self.assertAlmostEqual(self.spot.cantidad("BTC"), perp.abierto["BTC"], places=3)
        self.assertEqual([e["tipo"] for e in self.reg.leer()], ["carry_apertura"])

    def test_falla_el_contado_no_se_abre_nada(self):
        r = self.abrir(PerpFalso(), libro={"compras": [], "ventas": [(100.01, 0.1)]})           # sin profundidad
        self.assertEqual((r["estado"], r["patas_abiertas"]), ("deshecho", 0))
        self.assertEqual(self.spot.cantidad("BTC"), 0.0)
        self.assertEqual(self.spot.d["usdc"], 500.0)

    def test_falla_el_corto_se_deshace_el_contado(self):
        perp = PerpFalso(fallo="abrir")
        r = self.abrir(perp)
        self.assertEqual((r["estado"], r["patas_abiertas"]), ("deshecho", 0))
        self.assertEqual(self.spot.cantidad("BTC"), 0.0)
        self.assertLess(self.spot.d["usdc"], 500.0)                  # el deshacer cuesta comisiones y horquilla
        self.assertGreater(self.spot.d["usdc"], 498.0)
        self.assertIn("deshecho", self.reg.leer()[0]["mensaje"])

    def test_falla_el_corto_y_no_se_puede_deshacer_hay_desequilibrio(self):
        perp = PerpFalso(fallo="abrir")
        original = self.spot.ejecutar

        def ejecutar(coin, lado, *a, **k):
            if lado == "venta":
                raise ErrorSpot("libro vacío")
            return original(coin, lado, *a, **k)
        self.spot.ejecutar = ejecutar
        r = self.abrir(perp)
        self.assertEqual((r["estado"], r["congelar"]), ("desequilibrio", "BTC"))
        self.assertTrue(self.reg.leer()[-1]["grave"])

    def test_llenado_parcial_del_corto_iguala_el_contado(self):
        perp = PerpFalso(relleno=0.5)
        r = self.abrir(perp)
        self.assertEqual(r["estado"], "abierto")
        self.assertAlmostEqual(self.spot.cantidad("BTC"), perp.abierto["BTC"], places=3)
        self.assertAlmostEqual(self.spot.cantidad("BTC"), 0.5, places=2)

    def test_cierre_con_resultado_separado(self):
        perp = PerpFalso(funding=0.8)
        pos = self.abrir(perp)["posicion"]
        r = ej.cerrar_par(pos, perp, self.spot, libro_spot(), C, self.reg, "funding bajo", sz_decimales=3, ahora=1000.0 + 7200)
        self.assertEqual(r["estado"], "cerrado")
        res = r["resultado"]
        self.assertEqual(res["funding_cobrado_usd"], 0.8)
        self.assertEqual(res["horas"], 2.0)
        self.assertGreater(res["comisiones_usd"], 0)
        self.assertLess(abs(res["base_usd"]), 0.5)                    # precios iguales: la base solo es la horquilla
        self.assertAlmostEqual(res["pnl_neto_usd"], res["funding_cobrado_usd"] + res["base_usd"] - res["comisiones_usd"], places=3)
        self.assertEqual(self.spot.cantidad("BTC"), 0.0)

    def test_funding_negativo_se_ve_en_el_resultado(self):
        perp = PerpFalso(funding=-0.3)
        pos = self.abrir(perp)["posicion"]
        res = ej.cerrar_par(pos, perp, self.spot, libro_spot(), C, self.reg, "prueba", sz_decimales=3)["resultado"]
        self.assertLess(res["pnl_neto_usd"], -0.3)

    def test_base_que_se_dispara_aparece_en_el_resultado(self):
        perp = PerpFalso(px_cierre=101.0)                          # el perpetuo sube un 1 % y el contado no: la base pierde
        pos = self.abrir(perp)["posicion"]
        res = ej.cerrar_par(pos, perp, self.spot, libro_spot(), C, self.reg, "base", sz_decimales=3)["resultado"]
        self.assertLess(res["base_usd"], -0.5)

    def test_cierre_si_falla_el_corto_sigue_abierto(self):
        perp = PerpFalso()
        pos = self.abrir(perp)["posicion"]
        perp.fallo = "cerrar"
        r = ej.cerrar_par(pos, perp, self.spot, libro_spot(), C, self.reg, "x", sz_decimales=3)
        self.assertEqual(r["estado"], "abierto")
        self.assertGreater(self.spot.cantidad("BTC"), 0)            # no se vendió el contado: seguiría cubierto

    def test_cierre_si_falla_el_contado_hay_desequilibrio(self):
        perp = PerpFalso()
        pos = self.abrir(perp)["posicion"]
        r = ej.cerrar_par(pos, perp, self.spot, {"compras": [], "ventas": []}, C, self.reg, "x", sz_decimales=3)
        self.assertEqual((r["estado"], r["congelar"]), ("desequilibrio", "BTC"))

    def test_reinicio_a_mitad_conserva_el_estado(self):
        perp = PerpFalso()
        self.abrir(perp)
        otra = PapelSpot(os.path.join(self.tmp.name, "papel_spot.json"))          # el bot se reinicia
        self.assertGreater(otra.cantidad("BTC"), 0)
        self.assertEqual(otra.d["usdc"], self.spot.d["usdc"])


class CuentaSpot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = PapelSpot(os.path.join(self.tmp.name, "s.json"), usdc=1000.0)

    def test_compra_come_niveles_y_cobra_comision(self):
        libro = {"compras": [], "ventas": [(100.0, 1.0), (101.0, 5.0)]}
        f = self.s.ejecutar("BTC", "compra", 2.0, libro, 0.07, 3)
        self.assertAlmostEqual(f["px"], 100.5)
        self.assertAlmostEqual(f["comision"], 201.0 * 0.0007)
        self.assertAlmostEqual(self.s.d["usdc"], 1000 - 201.0 - 201.0 * 0.0007)

    def test_sin_profundidad_o_con_mucho_deslizamiento_se_rechaza_entera(self):
        with self.assertRaises(ErrorSpot):
            self.s.ejecutar("BTC", "compra", 10.0, {"compras": [], "ventas": [(100.0, 1.0)]}, 0.07, 3)
        with self.assertRaises(ErrorSpot):
            self.s.ejecutar("BTC", "compra", 2.0, {"compras": [], "ventas": [(100.0, 1.0), (110.0, 5.0)]}, 0.07, 3)
        self.assertEqual((self.s.d["usdc"], self.s.cantidad("BTC")), (1000.0, 0.0))

    def test_no_se_vende_lo_que_no_hay_ni_se_compra_sin_saldo(self):
        libro = {"compras": [(100.0, 50.0)], "ventas": [(100.0, 50.0)]}
        with self.assertRaises(ErrorSpot):
            self.s.ejecutar("BTC", "venta", 1.0, libro, 0.07, 3)
        with self.assertRaises(ErrorSpot):
            self.s.ejecutar("BTC", "compra", 20.0, libro, 0.07, 3)          # 2.000 $ con 1.000

    def test_redondeo_a_los_decimales_de_la_moneda(self):
        f = self.s.ejecutar("BTC", "compra", 0.12399, {"compras": [], "ventas": [(10.0, 5.0)]}, 0.0, 2)
        self.assertEqual(f["sz"], 0.12)
        with self.assertRaises(ErrorSpot):
            self.s.ejecutar("BTC", "compra", 0.001, {"compras": [], "ventas": [(10.0, 5.0)]}, 0.0, 2)

    def test_traspaso_simulado(self):
        self.s.traspasar(50.0)
        self.assertEqual(self.s.d["usdc"], 1050.0)
        with self.assertRaises(ErrorSpot):
            self.s.traspasar(-5000.0)

    def test_valor_de_la_cuenta(self):
        self.s.ejecutar("BTC", "compra", 1.0, {"compras": [], "ventas": [(100.0, 5.0)]}, 0.0, 3)
        self.assertAlmostEqual(self.s.valor({"BTC": 110.0}), 1000 - 100 + 110)


class NoEstaConectado(unittest.TestCase):
    def test_ningun_archivo_del_bot_importa_carry(self):
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for f in sorted(os.listdir(raiz)):
            if f.endswith(".py"):
                with open(os.path.join(raiz, f), encoding="utf-8") as fh:
                    txt = fh.read()
                self.assertNotRegex(txt, r"(?m)^\s*(from|import) carry\b", f)

    def test_el_paquete_no_tiene_llamadas_de_orden_reales(self):
        raiz = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "carry")
        for f in os.listdir(raiz):
            if f.endswith(".py"):
                with open(os.path.join(raiz, f), encoding="utf-8") as fh:
                    txt = fh.read()
                for prohibido in ("exchange.order", "Exchange(", "private_key", "HL_API_WALLET", "market_open", "usd_class_transfer"):
                    self.assertNotIn(prohibido, txt, f"{f}: {prohibido}")


if __name__ == "__main__":
    unittest.main()
