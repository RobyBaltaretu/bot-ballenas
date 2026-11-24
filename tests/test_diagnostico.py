"""El diagnóstico exportado marca lo que falta o está roto y nunca contiene secretos."""

import json
import os
import shutil

import diagnostico
import promocion
from tests.comunes import ConCarpeta

CLAVE = "0x" + "7a" * 32


class Diagnostico(ConCarpeta):
    def setUp(self):
        super().setUp()
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for f in promocion.ARCHIVOS_CODIGO:
            shutil.copy(os.path.join(raiz, f), os.path.join(self.dir, f))
        with open(os.path.join(self.dir, "config.json"), "w", encoding="utf-8") as fh:
            json.dump({"version_config": 2, "modo": "simulado", "real": {"subcuenta": "0x" + "ab" * 20},
                       "telegram_token": "123456789:" + "A" * 35, "nota": f"clave {CLAVE}"}, fh)
        with open(os.path.join(self.dir, "promociones.json"), "w", encoding="utf-8") as fh:
            fh.write("{roto")
        with open(os.path.join(self.dir, ".env"), "w", encoding="utf-8") as fh:
            fh.write(f"HL_API_WALLET_KEY={CLAVE}\n")

    def test_marca_faltantes_y_corruptos_sin_secretos(self):
        d = diagnostico.generar(self.dir)
        texto = json.dumps(d)
        self.assertNotIn(CLAVE, texto)
        self.assertNotIn("A" * 35, texto)
        self.assertNotIn("ab" * 20, texto)
        self.assertNotIn(".env", list(d["archivos"]))
        self.assertIn("papel.json", d["faltan"])
        self.assertIn("promociones.json", d["corruptos"])
        self.assertTrue(d["promociones"]["corrupto"])
        self.assertTrue(any("modelo del cerebro" in x for x in d["desconocido"]))
        self.assertEqual(len(d["huella_codigo"]), 16)
