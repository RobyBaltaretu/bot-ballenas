"""
Exporta un DIAGNÓSTICO redactado del bot (para revisar o compartir sin exponer nada):

  python diagnostico.py            -> registro/diagnostico_<fecha>.json (y lo resume por pantalla)

Contiene: versiones y huellas (código, configuración, modelo del cerebro, rasgos), integridad de los archivos de
estado (¿existen?, ¿son JSON válidos?, tamaño, fecha, sha256), qué datos FALTAN, modo y límites efectivos, estado
de las fuentes opcionales y la promoción vigente por estrategia. NUNCA incluye .env, claves, tokens, contraseñas
ni direcciones completas (todo pasa por sin_secretos + ocultar_secretos). «Sin datos» no es «funciona»: lo que no
se puede comprobar se marca como desconocido.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
ESTADO = ("config.json", "estado.json", "papel.json", "promociones.json", "cerebro_modelo.json",
          "estrategia_elegida.json", "laboratorio_variantes.json", "laboratorio_holdout.json", "panel_datos.json",
          "estado_sistema.json", "incidentes.json", "aprendizaje.json")
PROHIBIDOS = (".env",)          # nunca se leen ni se listan con contenido


def _archivo(ruta):
    out = {"existe": os.path.exists(ruta)}
    if not out["existe"]:
        return out
    try:
        with open(ruta, "rb") as fh:
            crudo = fh.read()
        out.update(bytes=len(crudo), sha256=hashlib.sha256(crudo).hexdigest()[:16],
                   modificado=datetime.fromtimestamp(os.path.getmtime(ruta), timezone.utc).isoformat(timespec="seconds"))
        try:
            json.loads(crudo.decode("utf-8"))
            out["json_valido"] = True
        except ValueError:
            out["json_valido"] = False
    except OSError as e:
        out["error"] = type(e).__name__
    return out


def generar(carpeta=AQUI):
    """'carpeta' = dónde están los ARCHIVOS a revisar; el código que se usa es siempre el de este proyecto."""
    from configuracion import VERSION_CONFIG, sin_secretos
    from observabilidad import ocultar_secretos
    d = {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "version_config": VERSION_CONFIG,
         "archivos": {n: _archivo(os.path.join(carpeta, n)) for n in ESTADO}, "faltan": [], "desconocido": []}
    d["faltan"] = [n for n, a in d["archivos"].items() if not a["existe"]]
    d["corruptos"] = [n for n, a in d["archivos"].items() if a.get("json_valido") is False]
    try:
        import promocion as pr
        d["huella_codigo"] = pr.hash_codigo(carpeta)
        d["version_huella"] = pr.VERSION_HUELLA
        d["modelo_cerebro"] = pr.identidades_archivo(os.path.join(carpeta, "cerebro_modelo.json")) or None
        if not d["modelo_cerebro"]:
            d["desconocido"].append("modelo del cerebro: ninguno válido (nada puede estar autorizado)")
    except Exception as e:  # noqa: BLE001
        d["desconocido"].append(f"huella: {type(e).__name__}")
    try:
        from mercado_unificado import VERSION_RASGOS
        d["version_rasgos"] = VERSION_RASGOS
    except Exception:  # noqa: BLE001
        pass
    try:
        from configuracion import cargar, hash_config, migrar
        from riesgo import limites_efectivos
        cfg, _ = migrar(cargar(os.path.join(carpeta, "config.json")))
        d["modo"] = cfg.get("modo")
        d["hash_config"] = hash_config(cfg)
        d["limites_efectivos"] = limites_efectivos(dict(cfg, modo=cfg.get("modo", "simulado")) if "riesgo" in cfg else
                                                   {"modo": "simulado", "riesgo": {}})
        d["piloto_real_config"] = cfg.get("piloto_real")
        d["nota_capital"] = ("capital configurado ≠ saldo reconciliado: este diagnóstico NO lee la cuenta; el saldo "
                             "real/simulado vigente está en el panel con su hora de lectura")
    except Exception as e:  # noqa: BLE001
        d["desconocido"].append(f"configuración: {type(e).__name__} (¿config.json incompleto? se usan defaults de código)")
    try:
        from promocion import Registro
        reg = Registro(os.path.join(carpeta, "promociones.json"))
        d["promociones"] = {"corrupto": reg.corrupto,
                            "etapas": {k: v.get("etapa") for k, v in reg.d.get("estrategias", {}).items()},
                            "pendientes_revision": [k for k, v in reg.d.get("estrategias", {}).items()
                                                    if v.get("pendiente_revision")]}
    except Exception as e:  # noqa: BLE001
        d["desconocido"].append(f"promociones: {type(e).__name__}")
    try:
        import coinglass
        d["fuentes_opcionales"] = {"coinglass": coinglass.CoinGlass(entorno={k: v for k, v in os.environ.items()
                                                                                if k == "COINGLASS_API_KEY"}).resumen()}
    except Exception as e:  # noqa: BLE001
        d["desconocido"].append(f"coinglass: {type(e).__name__}")
    texto = ocultar_secretos(json.dumps(sin_secretos(d), ensure_ascii=False, default=str))
    return json.loads(texto)


def main():
    d = generar()
    os.makedirs(os.path.join(AQUI, "registro"), exist_ok=True)
    ruta = os.path.join(AQUI, "registro", f"diagnostico_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json")
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, ensure_ascii=False)
    print(f"Diagnóstico en {ruta}")
    print(f"  modo: {d.get('modo')} · huella de código: {d.get('huella_codigo')} · modelo: {d.get('modelo_cerebro')}")
    for k in ("faltan", "corruptos", "desconocido"):
        if d.get(k):
            print(f"  {k}: {', '.join(d[k])}")


if __name__ == "__main__":
    main()
