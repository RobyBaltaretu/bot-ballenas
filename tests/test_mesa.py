"""Mesa (18/11/2026): «¿por qué no entra nada?» cuenta los motivos reales y no se inventa ninguno."""

import unittest

import mesa

AHORA = 1_800_000_000.0


def f(dt, estado="rechazada", motivos=(), est="ruptura_4h"):
    return {"ts": AHORA - dt, "estado": estado, "motivos": list(motivos), "estrategia": est}


class Etiquetas(unittest.TestCase):
    def test_motivos_reales_del_bot(self):
        casos = {
            "máximo de posiciones en la misma dirección (4)": "Ya hay el máximo del mismo lado",
            "tamaño mínimo excede riesgo (0.75 USD > 0.33 USD)": "Orden mínima mayor que el riesgo permitido",
            "stop 18.44% fuera de límites (0.25–12%)": "Stop demasiado lejos o demasiado cerca",
            "funding en contra": "Funding en contra",
            "volatilidad extrema": "Volatilidad extrema",
            "correlación con ENA": "Muy correlacionada con otra abierta",
            "cerebro en exploración (simulado, modelo sin aprobar): resultado esperado -0.046 R": "El cerebro no ve ventaja",
            "el precio ya avanzó 0.41 R desde la señal": "El precio ya se había ido",
            "enfriamiento tras cerrar en esa moneda": "Enfriamiento tras cerrar en esa moneda",
            "riesgo abierto total 9.4% > 9%": "Riesgo abierto al máximo",
            "algo que nadie previó": "Otros motivos",
        }
        for texto, esperado in casos.items():
            self.assertEqual(mesa.etiqueta(texto), esperado, texto)


class Embudo(unittest.TestCase):
    def test_ultimo_cierre_agrupa_las_propuestas_cercanas(self):
        filas = ([f(9000, motivos=["volatilidad extrema"])]                                   # un cierre anterior
                 + [f(100, motivos=["máximo de posiciones en la misma dirección (4)"]) for _ in range(5)]
                 + [f(110, motivos=["tamaño mínimo excede riesgo"]), f(120, estado="abierta")])
        r = mesa.embudo(filas, AHORA)["ultimo"]
        self.assertEqual((r["propuestas"], r["entran"], r["rechazadas"]), (7, 1, 6))
        self.assertEqual(r["motivos"][0], {"motivo": "Ya hay el máximo del mismo lado", "n": 5})
        self.assertEqual(r["motivos"][1]["motivo"], "Orden mínima mayor que el riesgo permitido")

    def test_una_propuesta_con_varios_motivos_cuenta_en_cada_uno(self):
        r = mesa.embudo([f(10, motivos=["funding en contra", "volatilidad extrema"])], AHORA)["ultimo"]
        self.assertEqual({m["motivo"] for m in r["motivos"]}, {"Funding en contra", "Volatilidad extrema"})
        self.assertEqual(r["rechazadas"], 1)

    def test_solo_investigacion_no_cuenta_como_propuesta_operable(self):
        filas = [f(10, motivos=["solo investigación: hipótesis sin validar (no opera)"]) for _ in range(30)] + [f(20, motivos=["funding en contra"])]
        d = mesa.embudo(filas, AHORA)
        self.assertEqual(d["ultimo"]["propuestas"], 1)
        self.assertEqual(d["solo_investigacion_24h"], 30)

    def test_sin_datos(self):
        self.assertIsNone(mesa.embudo([], AHORA)["ultimo"])
        self.assertEqual(mesa.embudo([{"ts": None, "estado": "rechazada"}], AHORA)["dia"]["propuestas"], 0)

    def test_ventana_de_24_horas(self):
        filas = [f(3600, motivos=["funding en contra"]), f(3 * 86400, motivos=["funding en contra"])]
        self.assertEqual(mesa.embudo(filas, AHORA)["dia"]["propuestas"], 1)

    def test_senal_sin_decision_no_cuenta_como_entrada_ni_rechazo(self):
        r = mesa.embudo([f(10, estado="senal")], AHORA)["ultimo"]
        self.assertEqual((r["entran"], r["rechazadas"], r["sin_decision"]), (0, 0, 1))


if __name__ == "__main__":
    unittest.main()
