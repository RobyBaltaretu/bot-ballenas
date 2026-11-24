"""Plantilla para la evaluación externa: todas las propuestas (propuestas.json) y todos los hallazgos
(INDICE_HALLAZGOS.md) con los campos vacíos. Uso: python3 -I generar_plantilla_evaluacion.py <carpeta_auditoria>"""
import json
import os
import re
import sys

D = sys.argv[1]
props = json.load(open(os.path.join(D, "propuestas.json"), encoding="utf-8"))["propuestas"]
ids_h = [m.group(1) for l in open(os.path.join(D, "INDICE_HALLAZGOS.md"), encoding="utf-8")
         if (m := re.match(r"\| ([A-Z]+-\d{2}) \|", l))]
plantilla = {
    "evaluador": "", "commit_fase_a": "",
    "propuestas": [{"id": p["id"], "titulo": p["titulo"], "veredicto": "", "diagnostico_correcto": "",
                    "referencias_correctas": "", "evidencia": "", "prioridad_claude": p["prioridad"],
                    "prioridad_codex": "", "efectos_secundarios": "", "cambios_sugeridos": "", "alternativa_mejor": "",
                    "coincide_con_fase_a": "", "confianza": ""} for p in props],
    "hallazgos": [{"id": h, "veredicto": "", "severidad_codex": "", "evidencia": "", "coincide_con_fase_a": ""}
                  for h in ids_h],
    "reproduccion_experimentos": [{"script": s, "reproduce": "", "diferencias": "", "problemas_del_script": ""}
                                  for s in ("forense_ledger.py", "sesgo_sombras.py", "backtest_independiente.py")],
    "omisiones_de_claude": [],
    "veredicto_global": {"coincide_en_no_go_real": "", "comentario": ""},
}
json.dump(plantilla, open(os.path.join(D, "plantilla_evaluacion_propuestas.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(len(plantilla["propuestas"]), "propuestas,", len(plantilla["hallazgos"]), "hallazgos")
