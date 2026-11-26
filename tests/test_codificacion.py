"""CP-M24 (auditoría 26/11/2026, T-10): codificación única. Ningún .py del proyecto lleva BOM ni finales CRLF, y la
documentación de referencia no arrastra «`n» (saltos de línea de PowerShell escritos como texto)."""
import os
import re
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUERA = {".venv", "__pycache__", ".git", "datos_backtest", "datos_mercado", "datos_archivo", "registro", "logs"}


def archivos_py():
    for base, dirs, nombres in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in FUERA and not d.startswith(".")]
        for n in nombres:
            if n.endswith(".py"):
                yield os.path.join(base, n)


class Codificacion(unittest.TestCase):
    def test_py_sin_bom_ni_crlf(self):
        malos = []
        revisados = 0
        for ruta in archivos_py():
            with open(ruta, "rb") as fh:
                b = fh.read()
            revisados += 1
            rel = os.path.relpath(ruta, RAIZ)
            if b.startswith(b"\xef\xbb\xbf"):
                malos.append(f"{rel}: BOM")
            if b"\r" in b:
                malos.append(f"{rel}: CR/CRLF")
            try:
                b.decode("utf-8")
            except UnicodeDecodeError:
                malos.append(f"{rel}: no es UTF-8")
        self.assertGreater(revisados, 100)
        self.assertEqual(malos, [])

    def test_documentacion_sin_restos_de_powershell(self):
        for nombre in ("CLAUDE.md", "LEEME.md"):
            ruta = os.path.join(RAIZ, nombre)
            if not os.path.exists(ruta):
                continue
            with open(ruta, encoding="utf-8") as fh:
                txt = fh.read()
            restos = [m.start() for m in re.finditer(r"`n(?=  |- )", txt)]
            self.assertEqual(restos, [], f"{nombre}: «`n» literal en las posiciones {restos[:5]}")

    def test_editorconfig(self):
        with open(os.path.join(RAIZ, ".editorconfig"), encoding="utf-8") as fh:
            ec = fh.read()
        self.assertIn("charset = utf-8", ec)
        self.assertRegex(ec, r"\[\*\.\{py[^\]]*\}\]\s*\nend_of_line = lf")


if __name__ == "__main__":
    unittest.main()
