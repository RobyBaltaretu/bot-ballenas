"""Panel nuevo (panel_web/): se sirve desde el mismo origen sin compilar, con CSP estricta, sin salir de su carpeta,
sin dependencias externas y sin construir HTML con datos (nada de innerHTML). El panel clásico sigue en /clasico."""

import json
import os
import re
import shutil

import panel
from tests.test_panel_observabilidad import Panel

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, "panel_web")


def archivos_web(ext):
    for base, _, nombres in os.walk(WEB):
        for n in nombres:
            if n.endswith(ext):
                yield os.path.join(base, n)


class PanelWeb(Panel):
    def setUp(self):
        super().setUp()
        shutil.copytree(WEB, os.path.join(self.dir, "panel_web"))

    def test_raiz_sirve_el_panel_nuevo_con_token_y_csp_estricta(self):
        st, html, cab = self.get("/")
        self.assertEqual(st, 200)
        self.assertIn(panel.Manejador.token, html)
        self.assertNotIn("{{TOKEN}}", html)
        # Los assets llevan la versión en la ruta (ninguna caché sirve un JS viejo) y esa ruta se sirve.
        version = panel.version_web()
        self.assertIn(f'"/assets/v-{version}/js/app.js"', html)
        self.assertNotIn('"/assets/js/', html)
        self.assertEqual(self.get(f"/assets/v-{version}/js/vistas/operaciones.js")[0], 200)
        self.assertEqual(self.get("/assets/v-zz/js/app.js")[0], 404)
        csp = cab.get("Content-Security-Policy", "")
        self.assertIn("script-src 'self';", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertEqual(cab.get("Cache-Control"), "no-store")

    def test_clasico_sigue_disponible_como_vuelta_atras(self):
        st, html, cab = self.get("/clasico")
        self.assertEqual(st, 200)
        self.assertIn(panel.Manejador.token, html)
        self.assertIn("unsafe-inline", cab.get("Content-Security-Policy", ""))

    def test_assets_con_su_tipo_y_cache_revalidable(self):
        for ruta, tipo in (("/assets/app.css", "text/css"), ("/assets/js/app.js", "text/javascript"),
                           ("/assets/js/vistas/inicio.js", "text/javascript"), ("/assets/icono.svg", "image/svg+xml")):
            st, _, cab = self.get(ruta)
            self.assertEqual(st, 200, ruta)
            self.assertTrue(cab.get("Content-Type", "").startswith(tipo), ruta)
            self.assertEqual(cab.get("Cache-Control"), "no-cache", ruta)
            self.assertEqual(cab.get("X-Content-Type-Options"), "nosniff", ruta)

    def test_no_se_sale_de_la_carpeta_ni_sirve_otros_tipos(self):
        with open(os.path.join(self.dir, "config.json"), "w", encoding="utf-8") as fh:
            fh.write('{"secreto": "no"}')
        for ruta in ("/assets/../config.json", "/assets/%2e%2e/config.json", "/assets/js/../../config.json",
                     "/assets/..%2fconfig.json", "/assets/index.html", "/assets/app.py", "/assets/.env", "/assets/",
                     "/assets/JS/APP.JS", "/panel_web/index.html", "/assets/js/app.js.map"):
            st, cuerpo, _ = self.get(ruta)
            self.assertEqual(st, 404, ruta)
            self.assertNotIn("secreto", cuerpo, ruta)
        self.assertIsNone(panel.asset_web("/assets/../../panel.py"))

    def test_sin_carpeta_nueva_se_usa_el_clasico(self):
        shutil.rmtree(os.path.join(self.dir, "panel_web"))
        st, _, cab = self.get("/")
        self.assertEqual(st, 200)
        self.assertIn("unsafe-inline", cab.get("Content-Security-Policy", ""))

    def test_todos_los_endpoints_existentes_siguen_respondiendo(self):
        for ruta in ("/api/datos", "/api/operaciones", "/api/operaciones?formato=csv", "/api/operacion?id=op-1",
                     "/api/observabilidad", "/api/diagnostico", "/api/feed", "/api/feed/tipos", "/api/config",
                     "/api/config/historial", "/api/laboratorio", "/api/glosario", "/api/resultado?id=x", "/api/taller"):
            self.assertEqual(self.get(ruta)[0], 200, ruta)
        self.assertEqual(self.get("/api/estrategia?clave=nada")[0], 404)
        self.assertEqual(self.get("/api/caso?id=nada")[0], 404)


del Panel           # sus pruebas ya se ejecutan en su módulo


class CodigoDelNavegador(PanelWeb.__mro__[2]):         # unittest.TestCase (sin servidor)
    def test_sin_innerhtml_ni_eval(self):
        for ruta in archivos_web(".js"):
            with open(ruta, encoding="utf-8") as fh:
                codigo = re.sub(r"/\*.*?\*/|//[^\n]*", "", fh.read(), flags=re.S)     # sin comentarios
            for prohibido in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
                self.assertNotIn(prohibido, codigo, f"{prohibido} en {os.path.basename(ruta)}")

    def test_sin_recursos_externos(self):
        for ext in (".js", ".css", ".html"):
            for ruta in archivos_web(ext):
                with open(ruta, encoding="utf-8") as fh:
                    codigo = fh.read()
                self.assertIsNone(re.search(r"(src|href)=\"https?://|url\(\s*['\"]?https?://|import .* from ['\"]https?://", codigo),
                                  os.path.basename(ruta))

    def test_html_sin_scripts_ni_estilos_en_linea(self):
        with open(os.path.join(WEB, "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)[^>]*>")
        self.assertNotRegex(html, r"\sstyle=|\son[a-z]+=")

    def test_todos_los_imports_resuelven(self):
        for ruta in archivos_web(".js"):
            with open(ruta, encoding="utf-8") as fh:
                codigo = fh.read()
            for destino in re.findall(r"(?:from\s+|import\()\s*['\"](\.[^'\"]+)['\"]", codigo):
                self.assertTrue(os.path.isfile(os.path.normpath(os.path.join(os.path.dirname(ruta), destino))),
                                f"{os.path.basename(ruta)} importa {destino}, que no existe")
            for nombre in re.findall(r"import\s*\{([^}]+)\}\s*from\s*['\"](\.[^'\"]+)['\"]", codigo):
                nombres, origen = nombre
                with open(os.path.normpath(os.path.join(os.path.dirname(ruta), origen)), encoding="utf-8") as fh:
                    exportado = fh.read()
                for n in (x.strip() for x in nombres.split(",") if x.strip()):
                    self.assertRegex(exportado, rf"export\s+(?:const|function|class|let|async function)\s+{re.escape(n)}(?![\w$])",
                                     f"{os.path.basename(ruta)} importa {n} de {origen}, que no lo exporta")

    def test_el_token_no_se_guarda_ni_va_en_urls(self):
        for ruta in archivos_web(".js"):
            with open(ruta, encoding="utf-8") as fh:
                codigo = fh.read()
            for m in re.finditer(r"localStorage\.(?:setItem|getItem)\(\s*['\"]([^'\"]+)", codigo):
                # Solo comodidades visuales locales (modo experto y tema); nunca el token ni datos del bot.
                self.assertIn(m.group(1), ("panel.experto", "panel.tema"), os.path.basename(ruta))
            self.assertNotRegex(codigo, r"[?&]token=", os.path.basename(ruta))
            if "TOKEN" in codigo:
                self.assertEqual(os.path.basename(ruta), "api.js")

    def test_el_despliegue_incluye_los_archivos_del_panel(self):
        import fnmatch
        with open(os.path.join(RAIZ, "despliegue", "actualizar_vps.sh"), encoding="utf-8") as fh:
            sh = fh.read()
        for ext in ("*.js", "*.css", "*.svg", "*.html"):
            self.assertIn(f"--include '{ext}'", sh, f"actualizar_vps.sh no copia {ext}")
        with open(os.path.join(RAIZ, "despliegue", "preparar_actualizacion.ps1"), encoding="utf-8") as fh:
            excluidos = re.findall(r'--exclude="([^"]+)"', fh.read())
        for base, _, nombres in os.walk(WEB):
            for n in nombres:
                self.assertFalse(any(fnmatch.fnmatch(n, e) for e in excluidos), f"el paquete excluiría {n}")

    def test_ninguna_ruta_nueva_de_escritura(self):
        rutas = set()
        for ruta in archivos_web(".js"):
            with open(ruta, encoding="utf-8") as fh:
                rutas |= set(re.findall(r"enviar\(\s*['\"]([^'\"]+)['\"]", fh.read()))
        self.assertTrue(rutas <= {"/api/comando", "/api/incidente", "/api/config", "/api/config/restaurar"}, rutas)
        codigo = ""
        for vista in ("inicio.js", "operaciones.js"):
            with open(os.path.join(WEB, "assets", "js", "vistas", vista), encoding="utf-8") as fh:
                codigo += fh.read()
        # Comandos literales ({cmd: "/pausa"}) y los de ajuste manual del stop/objetivo de UNA operación (14/11/2026,
        # pedido por Roberto; viven en operaciones.js, solo simulado; el servidor y el bot lo vuelven a validar).
        comandos = set(re.findall(r"cmd:\s*['\"](/[a-z]+)['\"]", codigo)) | set(re.findall(r"pedir\(\s*['\"](/[a-z]+)['\"]", codigo))
        self.assertNotIn("/stopmanual", open(os.path.join(WEB, "assets", "js", "vistas", "inicio.js"), encoding="utf-8").read(),
                         "el ajuste es por operación: no debe haber un control general en la portada")
        # Arreglos del Taller (18/11/2026): una lista cerrada en taller.js; el servidor los vuelve a filtrar y solo
        # los acepta desde este equipo (panel.COMANDOS_TALLER).
        with open(os.path.join(WEB, "assets", "js", "vistas", "taller.js"), encoding="utf-8") as fh:
            m = re.search(r"const PERMITIDOS = \[([^\]]*)\]", fh.read())
        taller = set(re.findall(r"/[a-z]+", m.group(1)))
        self.assertTrue(taller <= set(panel.COMANDOS_TALLER) | {"/reanudar"}, taller)
        self.assertEqual(comandos | taller, {"/pausa", "/reanudar", "/cerrarbot", "/stopmanual", "/tpmanual",
                                             "/aplicarconfig", "/laboratorio", "/investigacion"})
        self.assertEqual(json.loads(json.dumps(sorted(panel.COMANDOS))), sorted(comandos | taller))
