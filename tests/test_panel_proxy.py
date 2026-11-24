"""El panel detrás de un túnel o proxy: sin PANEL_PASSWORD solo se admite este equipo SIN cabeceras de reenvío.
Tener túnel no implica Cloudflare Access; las cabeceras de proxy las puede falsificar cualquiera."""

import base64

import panel
from tests.test_panel_observabilidad import Panel


class PanelTrasProxy(Panel):
    CABECERAS = ({"X-Forwarded-For": "8.8.8.8"}, {"Cf-Connecting-Ip": "1.2.3.4"}, {"X-Real-Ip": "1.2.3.4"},
                 {"Forwarded": "for=1.2.3.4;proto=https"})

    def test_local_sin_cabeceras_y_sin_clave_entra(self):
        self.assertEqual(self.get("/api/datos")[0], 200)

    def test_cabeceras_de_tunel_sin_clave_se_rechazan(self):
        for cab in self.CABECERAS:
            st, cuerpo, _ = self.get("/api/datos", cab)
            self.assertEqual(st, 403, cab)
            self.assertIn("PANEL_PASSWORD", cuerpo)
            self.assertEqual(self.post({"cmd": "/pausa"}, cab)[0], 403, cab)

    def test_tunel_con_clave_exige_la_clave(self):
        panel.Manejador.clave = "secreta"
        ok = base64.b64encode(b"x:secreta").decode()
        for cab in self.CABECERAS:
            self.assertEqual(self.get("/api/datos", cab)[0], 401, cab)
            self.assertEqual(self.get("/api/datos", dict(cab, Authorization="Basic " + ok))[0], 200, cab)
            # Remoto con clave: sigue siendo solo lectura (los comandos remotos están desactivados por defecto).
            self.assertEqual(self.post({"cmd": "/pausa"}, dict(cab, Authorization="Basic " + ok))[0], 403, cab)

    def test_tunel_sin_clave_explicito_entra_solo_lectura(self):
        # panel.tunel_sin_clave (temporal, a petición de Roberto): se ve por el túnel, pero nunca se manda nada,
        # ni siquiera con comandos_remotos activado.
        panel.Manejador.tunel_sin_clave = True
        panel.Manejador.comandos_remotos = True
        try:
            for cab in self.CABECERAS:
                self.assertEqual(self.get("/api/datos", cab)[0], 200, cab)
                self.assertEqual(self.post({"cmd": "/pausa"}, cab)[0], 403, cab)
        finally:
            panel.Manejador.tunel_sin_clave = False
            panel.Manejador.comandos_remotos = False

    def test_fuerza_bruta_se_frena(self):
        panel.Manejador.clave = "secreta"
        panel.Manejador.fallos_auth = {}
        mal = base64.b64encode(b"x:otra").decode()
        codigos = [self.get("/api/datos", {"Authorization": "Basic " + mal})[0] for _ in range(11)]
        self.assertEqual(codigos[:10], [401] * 10)
        self.assertEqual(codigos[10], 429)
        panel.Manejador.fallos_auth = {}


del Panel           # la base ya se ejecuta en su propio módulo: aquí solo las pruebas nuevas
