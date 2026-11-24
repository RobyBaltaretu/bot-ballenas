"""Índice único de hallazgos (ID, título, severidad, fuente). Uso: python3 -I generar_indice_hallazgos.py <carpeta>"""
import glob
import os
import re
import sys

D = sys.argv[1]
PAT = r"\b(T-\d{2}|Q-\d{2}|B-\d{2}|IA-\d{2}|W-\d{2}|C-\d{2}|A-\d{2}|S-\d{2}|SEG-\d{2}|OPS-\d{2}|V-\d{2})\b"
citados = {}
for f in sorted(glob.glob(os.path.join(D, "*.md"))) + [os.path.join(D, "experimentos", "hallazgos_borrador.md")]:
    for m in re.finditer(PAT, open(f, encoding="utf-8").read()):
        citados.setdefault(m.group(1), set()).add(os.path.basename(f))
defin = {}
for l in open(os.path.join(D, "03_auditoria_tecnica.md"), encoding="utf-8"):
    m = re.match(r"### (\S+) · (.+?) · (P\d)", l)
    if m:
        defin[m.group(1)] = (m.group(2), m.group(3), "03_auditoria_tecnica.md")
for l in open(os.path.join(D, "experimentos", "hallazgos_borrador.md"), encoding="utf-8"):
    m = re.match(r"- ([A-Z]+-\d{2}) (.*)", l)
    if m and m.group(1) not in defin:
        sev = re.search(r"· (P\d) ·", l)
        defin[m.group(1)] = (m.group(2).strip()[:140], sev.group(1) if sev else "—", "experimentos/hallazgos_borrador.md")
faltan = sorted(set(citados) - set(defin))
assert not faltan, f"IDs citados sin definición: {faltan}"
filas = ["# Índice de hallazgos", "",
         "Cada ID está definido en la fuente indicada (detalle completo en 03 o en `experimentos/hallazgos_borrador.md`).",
         "Una revisión externa debe marcar cada uno como CONFIRMADO, PARCIAL, REFUTADO o NO VERIFICABLE.", "",
         "| ID | Severidad | Hallazgo (resumen) | Definido en | Citado en |", "|---|---|---|---|---|"]
orden = lambda k: (re.sub(r"\d", "", k), int(re.sub(r"\D", "", k)))
for k in sorted(defin, key=orden):
    t, s, f = defin[k]
    filas.append(f"| {k} | {s} | {t.replace('|', '/')} | {f} | {', '.join(sorted(citados.get(k, [])))} |")
open(os.path.join(D, "INDICE_HALLAZGOS.md"), "w", encoding="utf-8").write("\n".join(filas) + "\n")
print(len(defin), "hallazgos")
