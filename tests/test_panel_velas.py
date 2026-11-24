"""/api/velas: el gráfico de precio de una operación solo lee las velas que el bot ya archiva (sin pedir nada al
exchange) y valida moneda e intervalo para no salir de datos_archivo/velas/."""

import json
import os

import panel
from tests.test_panel_observabilidad import Panel


class PanelVelas(Panel):
    def setUp(self):
        super().setUp()
        carpeta = os.path.join(self.dir, "datos_archivo", "velas", "1h")
        os.makedirs(carpeta)
        with open(os.path.join(carpeta, "ETH.jsonl"), "w", encoding="utf-8") as fh:
            for i in range(5):
                t = (1_000_000 + i * 3600) * 1000
                fh.write(json.dumps({"t": t, "T": t + 3599999, "o": "10", "h": "12", "l": "9", "c": str(10 + i)}) + "\n")
            fh.write('{"t": 1')                                   # línea cortada: se ignora

    def test_devuelve_velas_cerradas_del_archivo(self):
        st, cuerpo, _ = self.get("/api/velas?moneda=ETH&iv=1h&desde=1003600&hasta=1010800")
        self.assertEqual(st, 200)
        d = json.loads(cuerpo)
        self.assertEqual([v[0] for v in d["velas"]], [1003600, 1007200, 1010800])
        self.assertEqual(d["velas"][0][1:], [10.0, 12.0, 9.0, 11.0])
        self.assertIsNone(d["marca"])                             # la posición de prueba no trae precio de marca

    def test_moneda_sin_archivo_da_lista_vacia(self):
        st, cuerpo, _ = self.get("/api/velas?moneda=BTC&iv=1h")
        self.assertEqual((st, json.loads(cuerpo)["velas"]), (200, []))

    def test_parametros_raros_se_rechazan(self):
        for q in ("moneda=..%2F..%2Fconfig&iv=1h", "moneda=ETH&iv=1d", "moneda=&iv=1h", "moneda=ETH&iv=1h&desde=x"):
            self.assertEqual(self.get(f"/api/velas?{q}")[0], 400, q)

    def test_resumen_de_cerradas_por_periodo(self):
        r = panel.resumen_cerradas("simulado")
        self.assertEqual([r[p]["n"] for p in ("1D", "1S", "Todo")], [1, 1, 1])
        self.assertEqual(panel.resumen_cerradas("real")["Todo"]["n"], 0)      # otro origen no se mezcla
        # Lo anterior a la puesta a cero no está en el saldo actual: no cuenta.
        os.makedirs(os.path.join(self.dir, "archivo_reinicios", "20991231T000000Z"))
        self.assertEqual(panel.resumen_cerradas("simulado")["Todo"]["n"], 0)

    def test_maximo_de_velas(self):
        self.assertGreater(panel.MAX_VELAS, 24 * 7)              # una semana de 1 h cabe entera


del Panel           # la base ya se ejecuta en su propio módulo: aquí solo las pruebas nuevas
