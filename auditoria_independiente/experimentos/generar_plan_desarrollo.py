"""Plan de desarrollo para el programador a partir de las propuestas de la auditoría (generar_propuestas.py), con la
condición del propietario (26/11/2026): NADA que impida o reduzca que el bot opere. Las propuestas que lo harían se
excluyen (con su motivo, a la vista) o se transforman en una versión que no bloquea (p. ej. aviso en vez de pausa).
Genera PLAN_DESARROLLO.md y plan_desarrollo.json. Uso: python3 -I generar_plan_desarrollo.py <carpeta_auditoria>
"""
import importlib.util
import json
import os
import sys

D = sys.argv[1]
spec = importlib.util.spec_from_file_location("gp", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                 "generar_propuestas.py"))
gp = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0], D]
spec.loader.exec_module(gp)
P = {p["id"]: dict(p) for p in gp.P}

EXCLUIDAS = {
    "CP-E01": "apagaría momentum_4h (deja de operar una estrategia)",
    "CP-E02": "quitaría la exploración amplia (deja de operar esa vía)",
    "CP-E03": "con el modelo actual el cerebro dejaría de aprobar operaciones",
    "CP-E07": "ballenas_1h dejaría de operar (se mejora su señal con CP-A15 en su lugar)",
    "CP-E08": "quitaría las ballenas del bot",
    "CP-E10": "las sombras de las estrategias apagadas alimentan el aprendizaje; se mantienen",
    "CP-E11": "se corrige el prompt (CP-M06) en lugar de quitarlo",
    "CP-E15": "la cartera de funding dejaría de operar",
    "CP-E16": "no afecta al trading; queda a gusto del propietario",
    "CP-M01": "impediría operar estrategias que el laboratorio no aprueba (hoy, todas)",
    "CP-M07": "reduciría el tamaño de las operaciones (3 % confirmado por el propietario)",
    "CP-M10": "un suelo de −20 % también apagaría el simulado; el tope del real ya lo cubre CP-M08 (perdida_max_usd)",
    "CP-M11": "límites de exposición más estrictos bloquearían entradas",
}

CAMBIOS = {
    "CP-E06": dict(tipo="MODIFICAR", titulo="Piramidación: no recomprar lo recién cobrado en el TP1",
                   propuesta="Mantener la piramidación activa, pero que gestor.ampliable() devuelva motivo si la "
                             "operación tenía objetivo parcial y ya lo cobró (tp1_hecho) hasta que el precio avance "
                             "al menos 1 R más allá del TP1; y nunca en el mismo ciclo del cobro.",
                   riesgo_del_cambio="Menos ampliaciones justo después del TP1 (las que deshacían la toma de beneficios).",
                   aceptacion="Prueba: TP1 cobrado y precio sin avanzar 1 R → no amplía; tras +1 R → amplía.",
                   decide="auditor", huella="sí (código)"),
    "CP-A07": dict(titulo="Aviso por desviación del laboratorio (sin pausa)",
                   propuesta="Si el R medio de las últimas 30 operaciones de una estrategia queda bajo el límite "
                             "inferior del IC del laboratorio: incidente y aviso en el panel/Telegram. No pausa ni reduce.",
                   riesgo_del_cambio="Ninguno.", aceptacion="Prueba con serie degradada → incidente, sin bloqueo de entradas."),
    "CP-A14": dict(titulo="Conciliación PnL de fills frente al valor de la cuenta (aviso)",
                   propuesta="Si la suma de PnL atribuido difiere del cambio de accountValue (sin depósitos) más de X "
                             "en 24 h: incidente y aviso. Sin pausa.",
                   riesgo_del_cambio="Ninguno.", aceptacion="Prueba con diferencia sintética → incidente."),
    "CP-A09": dict(propuesta="Solo en modo real: leer userRateLimit cada hora y avisar cuando quede poco margen; no "
                             "afecta al simulado."),
    "CP-M08": dict(propuesta="Solo afecta a modo real (hoy no activo): 1 % / 3 % / 3 posiciones / 2× / "
                             "perdida_max_usd 46 / mercados [BTC, ETH, SOL]. El simulado sigue igual.",
                   decide="propietario (preaprobado al encargar el plan; aplicar con arranque manual)"),
    "CP-M09": dict(propuesta="Solo modo real: TECHOS_REAL 1 % / 3 % / 2× / −3 % día / 3 posiciones. El simulado no "
                             "cambia.", decide="propietario (preaprobado al encargar el plan)"),
    "CP-M13": dict(propuesta="Rechazo por margen en papel.order() como en Hyperliquid y releer la cuenta tras cada "
                             "apertura. Solo rechaza lo que en real sería imposible; si el margen libre no alcanza, "
                             "redimensionar al margen disponible en vez de descartar."),
    "CP-V02": dict(depende=[]),
}

FASES = {
    1: ("Corregir errores (no cambia la operativa)",
        ["CP-E06", "CP-M05", "CP-M06", "CP-M15", "CP-M16", "CP-M17", "CP-M18", "CP-M19", "CP-M23", "CP-M24", "CP-E13"]),
    2: ("Simulación y medición fieles",
        ["CP-M02", "CP-M03", "CP-M04", "CP-M12", "CP-M13", "CP-M14", "CP-M22", "CP-A01", "CP-A02", "CP-A04", "CP-A03",
         "CP-M20", "CP-M21"]),
    3: ("Mejoras de la operativa (sin bloquear entradas)",
        ["CP-E04", "CP-E05", "CP-E12", "CP-A08", "CP-A15", "CP-A07", "CP-A14", "CP-E09"]),
    4: ("Operación segura y preparación del real (parte la hace Roberto)",
        ["CP-A16", "CP-E14", "CP-A11", "CP-A12", "CP-A10", "CP-A09", "CP-M08", "CP-M09", "CP-A13"]),
    5: ("Investigación (no toca la operativa)", ["CP-A05", "CP-A06", "CP-V01", "CP-V02", "CP-V03", "CP-V04", "CP-V05"]),
}
ACCION_ROBERTO = {"CP-A16": "poner PANEL_PASSWORD en .env y la política de Cloudflare Access",
                  "CP-E14": "hacerlo después de CP-A16", "CP-A11": "poner TELEGRAM_TOKEN, TELEGRAM_CHAT_ID y HEALTHCHECK_URL",
                  "CP-A12": "crear la máquina del VPS", "CP-A10": "crear la cuenta/API wallet de testnet",
                  "CP-M08": "arranque manual con INICIAR.bat", "CP-M09": "arranque manual con INICIAR.bat"}


def main():
    for i, c in CAMBIOS.items():
        P[i].update(c)
    incluidas = [i for _, (_, ids) in sorted(FASES.items()) for i in ids]
    assert not set(incluidas) & set(EXCLUIDAS), "una propuesta está incluida y excluida a la vez"
    assert set(incluidas) | set(EXCLUIDAS) == set(P), f"sin clasificar: {set(P) - set(incluidas) - set(EXCLUIDAS)}"
    plan = []
    for f, (nombre, ids) in sorted(FASES.items()):
        for i in ids:
            p = dict(P[i], fase=f, nombre_fase=nombre, accion_roberto=ACCION_ROBERTO.get(i, ""),
                     depende=[d for d in P[i]["depende"] if d not in EXCLUIDAS])
            plan.append(p)
    json.dump({"version": 1, "fecha": "2026-11-26", "commit_codigo": "b8a9f8d",
               "condicion": "Nada que impida o reduzca que el bot opere.", "tareas": plan,
               "excluidas": [{"id": i, "titulo": P[i]["titulo"], "motivo": m} for i, m in EXCLUIDAS.items()]},
              open(os.path.join(D, "plan_desarrollo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    o = ["# Plan de desarrollo", "",
         "Generado desde `experimentos/generar_plan_desarrollo.py` (no editar a mano). Parte de las propuestas de la auditoría",
         "(`CAMBIOS_PROPUESTOS.md`) con la condición del propietario del 26/11/2026: **nada que impida o reduzca que el bot",
         "opere**. Lo que lo haría está excluido al final, con su motivo; algunas propuestas se han transformado (aviso en",
         "lugar de pausa, piramidación corregida en lugar de eliminada, límites solo para el modo real).", "",
         f"**{len(plan)} tareas en 5 fases · {len(EXCLUIDAS)} excluidas.**", ""]
    for f, (nombre, ids) in sorted(FASES.items()):
        o += [f"## Fase {f}: {nombre}", "", "| ID | Tarea | Prioridad | Esfuerzo | Acción de Roberto |", "|---|---|---|---|---|"]
        o += [f"| {i} | {P[i]['titulo']} | {P[i]['prioridad']} | {P[i]['esfuerzo']} | {ACCION_ROBERTO.get(i, '—')} |" for i in ids]
        o.append("")
        for i in ids:
            p = P[i]
            o += [f"### {i} · {p['titulo']}", "", f"- **Dónde:** {p['donde']}", f"- **Ahora:** {p['actual']}",
                  f"- **Qué hacer:** {p['propuesta']}", f"- **Por qué:** {p['evidencia']}",
                  f"- **Riesgo:** {p['riesgo_del_cambio']} · **Huella:** {p['huella']}",
                  f"- **Hecho cuando:** {p['aceptacion']}",
                  f"- **Depende de:** {', '.join(d for d in p['depende'] if d not in EXCLUIDAS) or '—'}", ""]
    o += ["## Excluidas (impedirían o reducirían la operativa)", "", "| ID | Propuesta | Motivo |", "|---|---|---|"]
    o += [f"| {i} | {P[i]['titulo']} | {m} |" for i, m in EXCLUIDAS.items()]
    open(os.path.join(D, "PLAN_DESARROLLO.md"), "w", encoding="utf-8").write("\n".join(o) + "\n")
    print(len(plan), "tareas,", len(EXCLUIDAS), "excluidas")


if __name__ == "__main__":
    main()
