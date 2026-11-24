"""Una vela solo se da por estudiada cuando de verdad se leyó: fallo transitorio, respuesta vacía o vela aún sin
publicar se reintentan en el ciclo siguiente (mientras la vela siga siendo reciente) y nunca se procesa dos veces."""

import os
from unittest import mock

from motor import MARGEN_CIERRE_SEG, Motor
from tests.comunes import LOG, ConCarpeta, config

H = 3600


class InfoVelas:
    """candles_snapshot controlado: 'modo' = ok | error | vacio | atrasada."""

    def __init__(self):
        self.modo, self.llamadas = "ok", 0

    def candles_snapshot(self, moneda, iv, ini, fin):
        self.llamadas += 1
        if self.modo == "error":
            raise ConnectionError("timeout")
        if self.modo == "vacio":
            return []
        ultima = (fin // 1000 // H - 1) * H - (H if self.modo == "atrasada" else 0)
        return [{"t": (ultima - k * H) * 1000, "T": (ultima - k * H + H) * 1000 - 1, "o": 100, "h": 101, "l": 99,
                 "c": 100 + (k % 3), "v": 10, "n": 1} for k in range(200)][::-1]


class MarcarProcesado(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.m = Motor(config(), LOG, os.path.join(self.dir, "estrategia_elegida.json"))
        self.m.estrategias = [e for e in self.m.estrategias if e["intervalo"] == "1h"][:1]
        self.m.monedas = ["ETH"]
        self.info = InfoVelas()
        self.t0 = 1_800_000_000 // H * H + MARGEN_CIERRE_SEG + 30      # 50 s después de un cierre de 1 h

    def ciclo(self, dt=0):
        with mock.patch("motor.time.time", return_value=self.t0 + dt), mock.patch("motor.time.sleep"):
            self.m.nuevas_senales(self.info)
        return self.m.procesado.get(("ETH", "1h"))

    def test_fallo_transitorio_se_reintenta_y_recupera(self):
        self.info.modo = "error"
        self.assertIsNone(self.ciclo())
        self.assertEqual(self.m.estado_velas["1h"]["reintentos"]["ETH"], 1)
        self.info.modo = "ok"
        self.assertEqual(self.ciclo(60), (self.t0 // H - 1) * H)        # recuperada en el siguiente ciclo
        self.assertNotIn("ETH", self.m.estado_velas["1h"]["reintentos"])
        self.assertEqual(self.m.velas_estudiadas, 1)

    def test_contexto_vacio_o_vela_atrasada_no_se_marca(self):
        for modo in ("vacio", "atrasada"):
            self.m.procesado.clear()
            self.m.contextos.clear()
            self.info.modo = modo
            self.assertIsNone(self.ciclo(), modo)
        self.info.modo = "ok"
        self.m.contextos.clear()
        self.assertIsNotNone(self.ciclo(30))

    def test_no_se_reprocesa_una_vela_ya_estudiada(self):
        self.ciclo()
        llamadas = self.info.llamadas
        self.ciclo(60)
        self.ciclo(120)
        self.assertEqual(self.info.llamadas, llamadas)
        self.assertEqual(self.m.velas_estudiadas, 1)

    def test_estrategia_apagada_se_sigue_en_sombra_y_nunca_opera(self):
        e = self.m.estrategias[0]
        señal = {"lado": "L", "sl_pct": 1.0, "fuerza": 1.0, "motivo": "prueba"}
        for activa in (True, False):
            self.m.procesado.clear()
            self.m.contextos.clear()
            e["activa"] = activa
            with mock.patch("motor.detectar", return_value=señal), mock.patch("motor.time.time", return_value=self.t0), \
                    mock.patch("motor.time.sleep"):
                cands = [c for c in self.m.nuevas_senales(self.info) if c["estrategia"] == e["clave"]]
            self.assertEqual(len(cands), 1, activa)
            self.assertEqual(bool(cands[0].get("solo_investigacion")), not activa)
            self.assertEqual(bool(cands[0].get("apagada")), not activa)

    def test_fuera_de_la_ventana_se_abandona_y_queda_registrado(self):
        self.info.modo = "error"
        self.ciclo()
        self.ciclo(16 * 60)                    # > 15 min tras el cierre: ya no es reciente
        self.assertEqual(self.m.procesado[("ETH", "1h")], (self.t0 // H - 1) * H)
        self.assertEqual(self.m.estado_velas["1h"]["perdidas_tras_reintentos"], 1)
        self.assertIn("duracion_lectura_s", self.m.estado_velas["1h"])
