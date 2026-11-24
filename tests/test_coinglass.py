"""CoinGlass: solo lectura, desactivado por defecto, estados explícitos y la clave nunca aparece. Sin red."""

import json
import os
import unittest

import coinglass as cgl

CLAVE = "clave-de-prueba-" + "x" * 16
EP = "/api/futures/open-interest/aggregated-history"


class Resp:
    def __init__(self, codigo=200, cuerpo=None, cab=None, no_json=False):
        self.status_code, self._c, self.headers, self._nj = codigo, cuerpo, cab or {}, no_json

    def json(self):
        if self._nj:
            raise ValueError("no json")
        return self._c


class Sesion:
    def __init__(self, resp=None, excepcion=None):
        self.resp, self.excepcion, self.llamadas = resp, excepcion, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.llamadas.append((url, params, headers, timeout))
        if self.excepcion:
            raise self.excepcion
        return self.resp


def cg(resp=None, excepcion=None, activo=True, clave=CLAVE, ahora=1_800_000_000):
    s = Sesion(resp, excepcion)
    return cgl.CoinGlass({"activo": activo}, {"COINGLASS_API_KEY": clave} if clave else {}, s, lambda: ahora), s


class Conector(unittest.TestCase):
    def test_desactivado_por_defecto_y_sin_clave(self):
        c = cgl.CoinGlass(entorno={"COINGLASS_API_KEY": CLAVE}, sesion=Sesion())
        self.assertEqual(c.leer(EP, "BTC", "1h")["estado"], "desactivado")
        c, s = cg(clave="")
        r = c.leer(EP, "BTC", "1h")
        self.assertEqual(r["estado"], "sin_clave")
        self.assertIsNone(r["datos"])
        self.assertEqual(s.llamadas, [])

    def test_datos_validos_con_procedencia_y_duplicados(self):
        filas = [{"time": 1_799_996_400_000, "close": "1"}, {"time": 1_799_996_400_000, "close": "2"},
                 {"time": 1_799_992_800_000, "close": "0.5"}]
        c, s = cg(Resp(200, {"code": "0", "msg": "success", "data": filas}, {"API-KEY-MAX-LIMIT": "30"}))
        r = c.leer(EP, "BTC", "1h")
        self.assertEqual(r["estado"], "ok")
        self.assertEqual([f["close"] for f in r["datos"]], ["0.5", "2"])          # ordenado y sin duplicados
        self.assertEqual(r["procedencia"]["fuente"], "coinglass")
        self.assertEqual(r["procedencia"]["antiguedad_seg"], 3600)
        self.assertEqual(r["uso_permitido"], "research_only")
        self.assertEqual(s.llamadas[0][2]["CG-API-KEY"], CLAVE)
        self.assertEqual(c.metricas["limite_minuto"], "30")

    def test_estados_explicitos(self):
        import requests
        casos = [(Resp(429, {}), None, "limite_api"), (Resp(500, {}), None, "error_http"),
                 (Resp(200, no_json=True), None, "formato_desconocido"), (Resp(200, {"sin": "data"}), None, "formato_desconocido"),
                 (Resp(200, {"code": "0", "data": []}), None, "sin_datos"),
                 (Resp(200, {"code": "40001", "msg": f"clave {CLAVE} inválida", "data": None}), None, "error_http"),
                 (None, requests.exceptions.ReadTimeout(), "timeout"), (None, ConnectionError(), "error_http")]
        for resp, exc, esperado in casos:
            c, _ = cg(resp, exc)
            r = c.leer(EP, "BTC", "1h")
            self.assertEqual(r["estado"], esperado, esperado)
            self.assertIsNone(r["datos"])
            self.assertNotIn(CLAVE, json.dumps(r, default=str))                 # la clave nunca sale

    def test_dato_viejo_es_obsoleto(self):
        c, _ = cg(Resp(200, {"code": "0", "data": [{"time": 1_790_000_000_000}]}))
        self.assertEqual(c.leer(EP, "BTC", "1h")["estado"], "obsoleto")

    def test_solo_endpoints_de_lectura_de_la_lista(self):
        c, _ = cg(Resp(200, {}))
        with self.assertRaises(ValueError):
            c.leer("/api/user/account", "BTC")

    def test_resumen_sin_clave_y_sin_uso_en_decisiones(self):
        c, _ = cg(Resp(200, {}))
        self.assertNotIn(CLAVE, json.dumps(c.resumen()))
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        import promocion
        for f in promocion.ARCHIVOS_CODIGO:                    # ningún módulo que decide lo importa
            with open(os.path.join(raiz, f), encoding="utf-8") as fh:
                self.assertNotIn("import coinglass", fh.read(), f)
