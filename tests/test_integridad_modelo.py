"""A-01: la aprobación para real queda ligada a la identidad EXACTA del modelo del cerebro, al lector de fuentes
externas y a su configuración. Cualquier cambio (o un modelo que no carga) invalida la aprobación: falla cerrado."""

import copy
import json
import os
import shutil

from tests.comunes import ConCarpeta, config, evidencia_para_apta

import cerebro as cb
import cerebro_vivo as cv
import mercado_unificado as mu
import promocion as pr


def modelo_valido():
    filas = [({**dict.fromkeys(mu.RASGOS), "flujo1": f / 10, "tendencia": 0.0}, "ruptura_1h", f / 10)
             for f in range(-10, 11)] * 5
    return cb.Modelo(mu.RASGOS, {"ruptura_1h"}).entrenar(filas)


ESTRATEGIA = {"clave": "ruptura_1h", "modulo": "ruptura", "intervalo": "1h", "version": "1", "params": {"n": 20},
              "salida": {}, "barras_max": 30}


class IntegridadModelo(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.ruta = os.path.join(self.dir, "cerebro_modelo.json")
        self.c = config()
        self.doc = {"version": "cerebro-x", "version_rasgos": mu.VERSION_RASGOS,
                    "modelos": {"1h": dict(modelo_valido().a_dict(), estado_laboratorio="supera")}}
        self.escribir(self.doc)
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for f in pr.ARCHIVOS_CODIGO:
            shutil.copy(os.path.join(raiz, f), os.path.join(self.dir, f))

    def escribir(self, doc, crudo=None):
        with open(self.ruta, "w", encoding="utf-8") as fh:
            fh.write(crudo if crudo is not None else json.dumps(doc))

    def huella(self, cerebro, cfg=None, carpeta=None):
        cfg = cfg or self.c
        try:
            modelo = pr.modelo_decisivo(cfg, "1h", {} if cerebro.error else cerebro.identidades)
        except pr.ErrorHuella:
            return None
        return pr.huella_segura(ESTRATEGIA, cfg, codigo=pr.hash_codigo(carpeta or self.dir), modelo=modelo)

    def aprobar_real(self, reg, h):
        evidencia_para_apta(reg, "ruptura_1h", h)
        reg.aprobar("ruptura_1h", "apta_revision", "test", h)
        reg.aprobar("ruptura_1h", "real_habilitado", "test", h)
        self.assertTrue(reg.autorizada_real("ruptura_1h", h))

    # ------------------------------------------------------------ regresión de aceptación
    def test_cambiar_un_coeficiente_impide_operar_en_real_hasta_nueva_aprobacion(self):
        reg = pr.Registro(os.path.join(self.dir, "promociones.json"))
        c = cv.CerebroVivo({}, self.ruta, modo="real")
        h = self.huella(c)
        self.assertIsNotNone(h)
        self.aprobar_real(reg, h)
        doc = copy.deepcopy(self.doc)
        doc["modelos"]["1h"]["w"][3] += 0.001                 # un solo coeficiente
        self.escribir(doc)
        c.recargar()
        h2 = self.huella(c)
        self.assertIsNotNone(h2)
        self.assertNotEqual(h, h2)
        self.assertFalse(reg.autorizada_real("ruptura_1h", h2))
        self.assertTrue(reg.vigente("ruptura_1h", h2)["invalidada"])

    def test_cambiar_regla_de_contexto_externo_invalida(self):
        reg = pr.Registro(os.path.join(self.dir, "promociones.json"))
        c = cv.CerebroVivo({}, self.ruta, modo="real")
        h = self.huella(c)
        self.aprobar_real(reg, h)
        self.assertIn("contexto_externo.py", pr.ARCHIVOS_CODIGO)
        with open(os.path.join(self.dir, "contexto_externo.py"), "a", encoding="utf-8") as fh:
            fh.write("\n# regla nueva\n")
        self.assertFalse(reg.autorizada_real("ruptura_1h", self.huella(c)))
        c2 = copy.deepcopy(self.c)
        c2["contexto_externo"]["desviacion_max_pct"] = 5.0     # configuración de la fuente
        self.assertNotEqual(self.huella(c, c2, carpeta=self.dir), self.huella(c, carpeta=self.dir))

    def test_identidad_es_la_misma_para_bot_cli_y_laboratorio(self):
        c = cv.CerebroVivo({}, self.ruta)
        self.assertEqual(c.identidad("1h"), cv.identidad_modelo(self.doc, "1h"))
        self.assertEqual(pr.identidades_archivo(self.ruta), {"1h": cv.identidad_modelo(self.doc, "1h")})

    # ------------------------------------------------------------ fallos que bloquean
    def bloquea(self, motivo):
        c = cv.CerebroVivo({}, self.ruta, modo="real")
        self.assertEqual(c.identidades, {}, motivo)
        self.assertIsNone(c.identidad("1h"), motivo)
        self.assertIsNone(self.huella(c), motivo)
        return c

    def test_archivo_ausente_bloquea(self):
        os.remove(self.ruta)
        self.bloquea("ausente")

    def test_json_corrupto_bloquea(self):
        self.escribir(None, crudo='{"modelos": {"1h": ')
        self.assertIn("inválido", self.bloquea("corrupto").error)

    def test_pesos_nan_o_inf_bloquean(self):
        for malo in ("NaN", "Infinity", "-Infinity"):
            crudo = json.dumps(self.doc).replace(str(self.doc["modelos"]["1h"]["w"][1]), malo, 1)
            self.assertIn(malo, crudo)
            self.escribir(None, crudo=crudo)
            self.bloquea(malo)

    def test_version_de_rasgos_desconocida_bloquea(self):
        self.escribir(dict(self.doc, version_rasgos=mu.VERSION_RASGOS + 1))
        self.assertIn("versión de rasgos", self.bloquea("version").error)

    def test_modelo_que_desaparece_tras_cargarse_bloquea(self):
        c = cv.CerebroVivo({}, self.ruta)
        self.assertIsNotNone(c.identidad("1h"))
        os.remove(self.ruta)
        c.recargar()
        self.assertIsNone(c.identidad("1h"))

    def test_huella_truncada_bloquea(self):
        reg = pr.Registro(os.path.join(self.dir, "promociones.json"))
        h = self.huella(cv.CerebroVivo({}, self.ruta))
        self.aprobar_real(reg, h)
        self.assertFalse(reg.autorizada_real("ruptura_1h", h[:12]))
        reg.d["estrategias"]["ruptura_1h"]["huella"] = h[:12]  # registro manipulado/truncado
        self.assertFalse(reg.autorizada_real("ruptura_1h", h))
        self.assertFalse(reg.autorizada_real("ruptura_1h", None))

    def test_sin_modelo_para_el_intervalo_no_hay_huella(self):
        with self.assertRaises(pr.ErrorHuella):
            pr.modelo_decisivo(self.c, "4h", {"1h": "x" * 20})
        c2 = copy.deepcopy(self.c)
        c2["cerebro"]["decide"] = False
        self.assertEqual(pr.modelo_decisivo(c2, "4h", {}), pr.SIN_CEREBRO)

    # ------------------------------------------------------------ real exige «supera»
    def test_en_real_un_modelo_no_supera_nunca_decide(self):
        doc = copy.deepcopy(self.doc)
        doc["modelos"]["1h"]["estado_laboratorio"] = "no_supera"
        self.escribir(doc)
        cand = {"moneda": "ETH", "lado": "L", "intervalo": "1h", "estrategia": "ruptura_1h"}
        for cfg in ({}, {"estados_validos": ["supera", "no_supera"]}, {"estados_validos": []},
                    {"exploracion_simulado": ["1h"]}):
            d = cv.CerebroVivo(cfg, self.ruta, modo="real").decidir(cand, None)
            self.assertFalse(d["abrir"], cfg)
            self.assertIn("modo real", d["motivo"])

    def test_cuatro_estados_en_simulado_y_real(self):
        cand = {"moneda": "ETH", "lado": "L", "intervalo": "1h", "estrategia": "ruptura_1h"}
        for estado in ("supera", "no_supera", None, "corrupto"):
            if estado == "corrupto":
                self.escribir(None, crudo="{roto")
            else:
                doc = copy.deepcopy(self.doc)
                if estado is None:
                    doc["modelos"]["1h"].pop("estado_laboratorio", None)
                else:
                    doc["modelos"]["1h"]["estado_laboratorio"] = estado
                self.escribir(doc)
            real = cv.CerebroVivo({}, self.ruta, modo="real").decidir(cand, None)
            if estado != "supera":
                self.assertFalse(real["abrir"], estado)
            sim = cv.CerebroVivo({"exploracion_simulado": ["1h"]}, self.ruta, modo="simulado")
            if estado in ("supera", "no_supera", None):
                self.assertIsNone(sim.error, estado)          # en simulado se carga (etiquetado como exploración)
            else:
                self.assertIsNotNone(sim.error)


class RegistroPromociones(ConCarpeta):
    def test_migracion_pasa_aprobaciones_viejas_a_pendiente_de_revision(self):
        ruta = os.path.join(self.dir, "promociones.json")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "estrategias": {"ruptura_1h": {"etapa": "real_habilitado", "huella": "a" * 20,
                                                                    "evidencias": [], "historial": []}}}, fh)
        reg = pr.Registro(ruta)
        self.assertEqual(reg.migrado, ["ruptura_1h"])
        e = reg.d["estrategias"]["ruptura_1h"]
        self.assertEqual(e["etapa"], "investigacion")
        self.assertTrue(e["pendiente_revision"])
        self.assertFalse(reg.autorizada_real("ruptura_1h", "a" * 20))     # ni con la huella antigua
        self.assertTrue(os.path.exists(ruta + ".v1.bak"))
        reg.guardar()
        self.assertEqual(pr.Registro(ruta).migrado, [])                   # idempotente

    def test_registro_corrupto_falla_cerrado_y_conserva_el_original(self):
        ruta = os.path.join(self.dir, "promociones.json")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write('{"version": 2, "estrategias": {"ruptura_1h": {"etapa": "real_hab')
        reg = pr.Registro(ruta)
        self.assertIsNotNone(reg.corrupto)
        self.assertFalse(reg.autorizada_real("ruptura_1h", "a" * 20))
        self.assertTrue(reg.vigente("ruptura_1h", "a" * 20)["invalidada"])
        with self.assertRaises(ValueError):
            reg.aprobar("ruptura_1h", "laboratorio", "test", "a" * 20)
        reg.guardar()
        copias = [f for f in os.listdir(self.dir) if ".corrupto-" in f]
        self.assertEqual(len(copias), 1)
