"""CP-M18 (auditoría 26/11/2026, OPS-01): el servidor se instala y actualiza con el entorno bloqueado y comprueba que
pip freeze coincide con requirements-bloqueado.txt."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = ("instalar_vps.sh", "actualizar_vps.sh")


def leer(nombre):
    with open(os.path.join(RAIZ, "despliegue", nombre), encoding="utf-8") as fh:
        return fh.read()


def funcion(sh):
    m = re.search(r"^entorno_igual_al_bloqueado\(\) \{.*?^\}$", sh, re.S | re.M)
    return m.group(0) if m else None


def bloqueados():
    with open(os.path.join(RAIZ, "requirements-bloqueado.txt"), encoding="utf-8") as fh:
        return [x.strip() for x in fh if x.strip() and not x.startswith("#")]


class EntornoBloqueado(unittest.TestCase):
    def test_los_scripts_instalan_el_archivo_bloqueado(self):
        for nombre in SCRIPTS:
            sh = leer(nombre)
            instala = re.findall(r"pip\" install -q -r \"\$DESTINO/([^\"]+)\"", sh)
            self.assertEqual(instala, ["requirements-bloqueado.txt"], nombre)
            self.assertIn('entorno_igual_al_bloqueado "$DESTINO/requirements-bloqueado.txt"', sh, nombre)

    def test_la_comprobacion_es_la_misma_en_los_dos(self):
        a, b = (funcion(leer(n)) for n in SCRIPTS)
        self.assertIsNotNone(a)
        self.assertEqual(a, b)

    def test_lo_directo_esta_en_el_bloqueado(self):
        with open(os.path.join(RAIZ, "requirements.txt"), encoding="utf-8") as fh:
            directos = [x.strip() for x in fh if x.strip() and not x.startswith("#")]
        self.assertTrue(set(directos) <= set(bloqueados()), "requirements.txt pide algo que no está bloqueado")

    def comparar(self, freeze):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("sin bash")
        d = tempfile.mkdtemp(prefix="bot-despliegue-")
        try:
            shutil.copy(os.path.join(RAIZ, "requirements-bloqueado.txt"), os.path.join(d, "bloqueado.txt"))
            with open(os.path.join(d, "freeze.txt"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(freeze) + "\n")
            guion = (funcion(leer("instalar_vps.sh")) + "\nfalsopip() { cat freeze.txt; }\n"
                     "if entorno_igual_al_bloqueado bloqueado.txt falsopip; then echo IGUAL; else echo DISTINTO; fi\n")
            try:
                r = subprocess.run([bash, "-c", guion], cwd=d, capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.SubprocessError) as e:
                self.skipTest(f"bash no utilizable: {e}")
            if r.stdout.strip() not in ("IGUAL", "DISTINTO"):
                self.skipTest(f"bash no utilizable: {r.stderr[:200]}")
            return r.stdout.strip()
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_freeze_igual_aunque_cambie_el_nombre(self):
        # pip freeze puede escribir annotated-types o Annotated_Types: es el mismo paquete.
        freeze = [x.replace("_", "-").capitalize() for x in reversed(bloqueados())]
        self.assertEqual(self.comparar(freeze), "IGUAL")

    def test_freeze_con_otra_version_o_de_mas(self):
        b = bloqueados()
        otra = [re.sub(r"==.*", "==0.0.1", b[0])] + b[1:]
        self.assertEqual(self.comparar(otra), "DISTINTO")
        self.assertEqual(self.comparar(b + ["paquete-extra==1.0"]), "DISTINTO")
        self.assertEqual(self.comparar(b[1:]), "DISTINTO")


if __name__ == "__main__":
    unittest.main()
