"""PARIDAD simulado ↔ laboratorio. SOLO LECTURA del ledger y de las velas archivadas por el bot; no opera ni modifica nada.

Responde a «¿el laboratorio y el simulado miden lo mismo?» operación a operación, con dos reproducciones de cada operación
cerrada del ledger usando `estrategia.SimSalida` (el mismo simulador que usa el laboratorio):

  A) PARIDAD DE SALIDA: entra al precio REAL del fill, con el stop REAL, y gestiona la salida vela a vela de 1 h.
     Si A se parece al resultado vivo, la gestión de salida (stop, parcial, sin pérdidas, trailing, tiempo) es la misma.
  B) PARIDAD DE ENTRADA: entra como lo hace el laboratorio (apertura de la vela siguiente a la señal, a mercado, con el
     deslizamiento mínimo) con el stop de la señal. La diferencia B − vivo mide lo que cuesta/gana la entrada maker real
     frente a la supuesta por el laboratorio.

Criterio fijado de antemano: la paridad solo se da por buena con ≥ 30 operaciones comparables y una diferencia media de
la reproducción A frente al resultado vivo < 0,10 R en valor absoluto. Con menos operaciones el informe lo dice y no concluye.

Resultados en R y SIN funding (SimSalida no lo incluye): el vivo se compara como (pnl_neto − funding) / riesgo inicial.
Las velas de 1 h son más gruesas que el seguimiento por precio del bot: una diferencia pequeña en la salida es esperable."""

import argparse
import datetime
import json
import os

import archivo
from estrategia import SimSalida
from senales import INTERVALOS, MODULOS

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(AQUI, "registro", "estudio_paridad.json")
DESLIZAMIENTO_LAB = 0.0002
MIN_OPS = 30
DIFERENCIA_MAX_R = 0.10


def _ts(texto):
    return datetime.datetime.fromisoformat(texto.replace("Z", "+00:00")).timestamp()


def leer_ledger(ruta):
    out = []
    try:
        with open(ruta, encoding="utf-8") as fh:
            for linea in fh:
                try:
                    out.append(json.loads(linea))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def operaciones(eventos):
    """Agrupa el ledger por trade_id y devuelve las operaciones CERRADAS con lo necesario para reproducirlas."""
    por = {}
    for e in eventos:
        if e.get("trade_id"):
            por.setdefault(e["trade_id"], []).append(e)
    out = []
    for tid, evs in por.items():
        cierre = next((e for e in evs if e["tipo"] == "cierre"), None)
        fill = next((e for e in evs if e["tipo"] == "fill" and e.get("rol") == "entrada"), None)
        senal = next((e for e in evs if e["tipo"] == "senal"), None)
        stop = next((e for e in evs if e["tipo"] == "proteccion" and e.get("clase") == "stop"), None)
        decisiones = [e for e in evs if e["tipo"] == "decision" and e.get("aprobada")]
        if not (cierre and fill and senal and stop):
            continue
        px = float(fill["px"])
        out.append({"trade_id": tid, "moneda": cierre["moneda"], "lado": cierre["lado"], "estrategia": cierre["estrategia"],
                    "t_entrada": (fill.get("ts_exchange") or 0) / 1000 or _ts(fill["ts"]), "px_entrada": px,
                    "maker": bool(fill.get("maker")), "sl_pct_real": abs(px - float(stop["trigger"])) / px * 100,
                    "sl_pct_senal": float(senal["sl_pct"]), "vela_ts": (senal.get("contexto") or {}).get("vela_ts"),
                    "causa_vivo": cierre.get("causa"), "t_cierre": _ts(cierre["ts"]),
                    "r_vivo": cierre["r_neto"], "riesgo_usd": cierre.get("riesgo_inicial_usd"),
                    "r_vivo_sin_funding": ((cierre["pnl_neto"] - (cierre.get("funding") or 0.0)) / cierre["riesgo_inicial_usd"]
                                           if cierre.get("riesgo_inicial_usd") else None),
                    "exploracion_amplia": any((d.get("plan") or {}).get("exploracion_amplia") for d in decisiones)})
    return sorted(out, key=lambda x: x["t_entrada"])


def _cfg_salida(cfg, modulo):
    return dict(cfg["salida"], **MODULOS[modulo]["salida"])


def _velas(carpeta, moneda, iv):
    return [v for v in archivo.leer_velas(carpeta, moneda, iv)]


def reproducir(op, cfg, carpeta_archivo):
    """Devuelve las dos reproducciones (o el motivo por el que no se pudo)."""
    modulo, _, iv = op["estrategia"].rpartition("_")
    if modulo not in MODULOS or iv not in INTERVALOS:
        return {"motivo": f"estrategia {op['estrategia']} sin módulo reproducible"}
    salida = _cfg_salida(cfg, modulo)
    tf = INTERVALOS[iv] * 60
    barras = MODULOS[modulo]["barras_max"]
    tope_global = (cfg.get("riesgo") or {}).get("duracion_max_global_h")
    if tope_global:
        barras = min(barras, int(tope_global * 3600 // tf))
    taker, maker = cfg["comisiones"]["taker_pct"] / 100, cfg["comisiones"]["maker_pct"] / 100
    s = 1 if op["lado"] == "L" else -1
    res = {}

    def correr(sim, velas, desde_t, paso_s):
        for v in velas:
            t = int(v["t"]) / 1000
            if t < desde_t:
                continue
            if sim.paso(float(v["h"]), float(v["l"]), float(v["c"]), t + paso_s, float(v["o"]) if t > desde_t else None):
                break
        return sim

    # A) salida: entra al precio real, vela de 1 h a partir de la hora siguiente al fill.
    v1 = _velas(carpeta_archivo, op["moneda"], "1h")
    if v1:
        desde = (op["t_entrada"] // 3600 + 1) * 3600
        simA = SimSalida(op["lado"], op["px_entrada"], op["sl_pct_real"], salida, op["t_entrada"] + barras * tf,
                         maker if op["maker"] else taker, taker, maker, desl_mercado=DESLIZAMIENTO_LAB)
        correr(simA, v1, desde, 3600)
        res["A"] = {"cerrada": simA.cerrada, "r": simA.resultado_r() if simA.cerrada else None, "causa": simA.motivo,
                    "t_cierre": simA.cierre_ts}
    # B) entrada del laboratorio: apertura de la vela siguiente a la señal, a mercado, en el intervalo de la estrategia.
    vi = _velas(carpeta_archivo, op["moneda"], iv)
    if vi and op.get("vela_ts"):
        j0 = float(op["vela_ts"]) + tf
        vela = next((v for v in vi if int(v["t"]) / 1000 == j0), None)
        if vela:
            entrada = float(vela["o"]) * (1 + s * DESLIZAMIENTO_LAB)
            simB = SimSalida(op["lado"], entrada, op["sl_pct_senal"], salida, j0 + barras * tf, taker, taker, maker,
                             desl_mercado=DESLIZAMIENTO_LAB)
            correr(simB, vi, j0, tf)
            res["B"] = {"cerrada": simB.cerrada, "r": simB.resultado_r() if simB.cerrada else None, "causa": simB.motivo,
                        "entrada": round(entrada, 8)}
    return res


def _media(xs):
    return round(sum(xs) / len(xs), 3) if xs else None


def informe(ledger, config, carpeta_archivo):
    ops = operaciones(leer_ledger(ledger))
    filas, difA, difB, mismas = [], [], [], []
    for op in ops:
        rep = reproducir(op, config, carpeta_archivo)
        a, b = rep.get("A") or {}, rep.get("B") or {}
        fila = {k: op[k] for k in ("trade_id", "moneda", "lado", "estrategia", "causa_vivo", "r_vivo", "r_vivo_sin_funding",
                                   "exploracion_amplia")}
        fila.update(r_A=a.get("r"), causa_A=a.get("causa"), r_B=b.get("r"), causa_B=b.get("causa"),
                    motivo=rep.get("motivo"))
        base = op["r_vivo_sin_funding"]
        if base is not None and a.get("r") is not None:
            difA.append(a["r"] - base)
            mismas.append(1 if (a.get("causa") == op["causa_vivo"]) else 0)
        if base is not None and b.get("r") is not None:
            difB.append(b["r"] - base)
        filas.append(fila)
    n = len(difA)
    suficiente = n >= MIN_OPS
    media_a = _media(difA)
    res = {"estudio": "paridad_simulado_laboratorio", "operaciones_cerradas": len(ops), "comparables_A": n,
           "comparables_B": len(difB),
           "A_salida": {"diferencia_media_r": media_a, "diferencia_abs_media_r": _media([abs(x) for x in difA]),
                        "misma_causa_de_cierre_pct": round(100 * sum(mismas) / len(mismas), 1) if mismas else None},
           "B_entrada_laboratorio": {"diferencia_media_r": _media(difB), "diferencia_abs_media_r": _media([abs(x) for x in difB])},
           "criterio": f"≥ {MIN_OPS} comparables y |diferencia media A| < {DIFERENCIA_MAX_R} R",
           "veredicto": ("sin muestra suficiente para concluir" if not suficiente else
                         ("paridad aceptable" if abs(media_a) < DIFERENCIA_MAX_R else "NO hay paridad: revisar salidas")),
           "filas": filas}
    return res


def main():
    ap = argparse.ArgumentParser(description="Paridad simulado↔laboratorio (solo lectura)")
    ap.add_argument("--salida", default=SALIDA)
    args = ap.parse_args()
    with open(os.path.join(AQUI, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    from configuracion import DEFECTOS
    base = json.loads(json.dumps(DEFECTOS))
    for k in ("salida", "comisiones", "riesgo"):
        base[k] = dict(base.get(k) or {}, **(cfg.get(k) or {}))
    res = informe(os.path.join(AQUI, "registro", "ledger.jsonl"), base, os.path.join(AQUI, "datos_archivo"))
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "filas"}, ensure_ascii=False, indent=1))
    print("Guardado en", args.salida)


if __name__ == "__main__":
    main()
