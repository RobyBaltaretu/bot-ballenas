import unittest

import sombras


def reg(tipo="sombra", r=None, modulo="ruptura_1h", motivo="estrategia apagada: se sigue en sombra", ts=1000.0,
        origen="simulado", **extra):
    d = {"id": f"x{ts}", "tipo": tipo, "moneda": "BTC", "lado": "L", "modulo": modulo, "origen": origen, "ts": ts,
         "resultado_r": r, "cierre_ts": ts + 3600 if r is not None else None, "motivos_descarte": [motivo],
         "trade_id": "op-1"}
    d.update(extra)
    return d


class Sombras(unittest.TestCase):
    def test_categorias_de_los_motivos_reales(self):
        casos = {
            "solo investigación: hipótesis sin validar (no opera)": "investigacion",
            "estrategia apagada: se sigue en sombra para seguir aprendiendo (no opera)": "apagada",
            "el modelo de 1h no supera el laboratorio (no_supera): no entra": "cerebro",
            "cerebro en exploración (simulado, modelo sin aprobar): resultado esperado 0.01 R (≤ 0.05 R)": "cerebro",
            "contra el régimen de BTC (bajista frente a su media de 200 velas)": "regimen",
            "tamaño mínimo excede riesgo: la orden mínima (10 USD) arriesgaría 2 USD": "riesgo",
            "correlada 0.85 con BNB ya abierta": "riesgo",
            "máximo de posiciones en la misma dirección (3)": "riesgo",
            "volatilidad extrema: la última vela midió 4.2 ATR": "mercado",
            "funding 0.01%/h en contra": "mercado",
            "stop 12.11% fuera de límites (0.25–12%)": "mercado",
            "entradas bloqueadas: pausa por racha de pérdidas": "pausa",
            "algo nuevo": "otro",
        }
        for motivo, esperado in casos.items():
            self.assertEqual(sombras.categoria(motivo), esperado, motivo)

    def test_estadisticas_y_lectura_del_filtro(self):
        st = sombras.estadisticas([1.0, -1.0, 2.0, None])
        self.assertEqual((st["n"], st["r_medio"], st["suma"]), (3, 0.667, 2.0))
        self.assertEqual(sombras.lectura_filtro(sombras.estadisticas([-1.0, -0.5] * 3))[0], "pocos")
        self.assertEqual(sombras.lectura_filtro(sombras.estadisticas([-1.0, -0.8] * 20))[0], "acierta")
        self.assertEqual(sombras.lectura_filtro(sombras.estadisticas([1.0, 0.8] * 20))[0], "falla")
        self.assertEqual(sombras.lectura_filtro(sombras.estadisticas([1.0, -1.0] * 20))[0], "neutro")

    def test_resumen_filtra_origen_y_puesta_a_cero(self):
        regs = [reg(r=1.0, ts=2000), reg(r=-1.0, ts=2100), reg(r=5.0, ts=10),          # esta, antes de la puesta a cero
                reg(r=3.0, ts=2200, origen="real"), reg(tipo="real", r=0.5, ts=2300), reg(ts=2400)]
        d = sombras.resumen(regs, 9999, desde=1000, origen="simulado", estado_estrategia=lambda c: "apagada")
        self.assertEqual(d["total"]["n"], 2)
        self.assertEqual(d["operadas"]["n"], 1)
        self.assertEqual(d["balanza"], {"ahorrado": 1.0, "dejado": 1.0, "neto": 0.0, "n_pierden": 1, "n_ganan": 1})
        self.assertEqual(len(d["abiertas"]), 1)
        self.assertEqual([p["ts"] for p in d["puntos"]], [2100, 2000])       # lo más reciente primero
        e = d["estrategias"][0]
        self.assertEqual((e["clave"], e["estado"], e["n"], e["abiertas"]), ("ruptura_1h", "apagada", 2, 1))
        self.assertEqual(e["curva"][-1][1], 0.0)

    def test_abierta_con_parcial_cobrado(self):
        sim = {"s": 1, "entrada": 100.0, "r_dist": 2.0, "sl": 100.5, "tp1": 102.0, "tpf": 106.0, "mejor": 103.0,
               "realizado_r": 0.5, "restante": 0.5, "tp1_hecho": True, "en_breakeven": True, "limite_ts": 5000}
        a = sombras.abierta(reg(sim=sim), px=101.0, px_ts=3000)
        self.assertEqual((a["r_ahora"], a["r_mejor"], a["r_stop"], a["r_tp1"], a["r_tpf"]), (0.75, 1.5, 0.25, 1.0, 3.0))
        corto = sombras.abierta(reg(sim=dict(sim, s=-1, realizado_r=0, restante=1)), px=98.0)
        self.assertEqual(corto["r_ahora"], 1.0)
        self.assertIsNone(sombras.abierta(reg(sim=sim))["r_ahora"])          # sin precio no se inventa

    def test_aviso_de_estrategia(self):
        gana = sombras.estadisticas([1.0, 0.5] * 30)
        self.assertIsNotNone(sombras.aviso_estrategia("apagada", gana))
        self.assertIsNone(sombras.aviso_estrategia("activa", gana))
        self.assertIsNotNone(sombras.aviso_estrategia("activa", sombras.estadisticas([-1.0, -0.5] * 20)))

    def test_curva_reducida_conserva_el_final(self):
        regs = [reg(r=1.0, ts=1000 + i) for i in range(300)]
        e = sombras.resumen(regs, 9e9)["estrategias"][0]
        self.assertLessEqual(len(e["curva"]), sombras.MAX_CURVA)
        self.assertEqual(e["curva"][-1][1], 300.0)


if __name__ == "__main__":
    unittest.main()
