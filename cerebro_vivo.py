"""
El cerebro en vivo: ÚNICO que decide si una candidata se opera (en simulado y shadow; en real, además, sigue
haciendo falta la aprobación humana de siempre y los límites del piloto).

Garantías (cada una tiene su prueba):
  - Decide con el modelo que entrenó el laboratorio (cerebro_modelo.json), validado al cargarlo. Modelo ausente,
    corrupto o de otra versión de rasgos -> NO entra nadie (se abstiene) y lo dice.
  - Calcula los rasgos con la MISMA función que el laboratorio (mercado_unificado.rasgos) y solo con velas cerradas.
  - Datos de Binance/Bybit viejos o ausentes -> esos rasgos valen «sin dato» (nunca se inventan) y queda anotado.
  - Jamás salta la protección: límites, stops, bloqueos y piloto real se aplican después, igual que antes.
  - Cualquier error interno -> se abstiene (no entra) y se registra; el bot sigue funcionando.
  - Identidad reproducible de cada modelo (identidad_modelo): hash del modelo canónico + versión de rasgos. Entra en
    la huella de aprobación (promocion.py): cambiar un coeficiente invalida cualquier aprobación para real.
  - En REAL solo decide un modelo con estado de laboratorio «supera» (la configuración no puede relajarlo).
"""

import hashlib
import json
import math
import time

import cerebro as cb
import mercado_unificado as mu


def _rechazar_no_finito(valor):
    raise ValueError(f"valor no numérico en el modelo ({valor})")


def identidad_modelo(doc, intervalo):
    """Identidad del modelo de un intervalo: sha256 del modelo canónico (claves ordenadas) + versión de rasgos +
    versión del documento. None si no hay modelo para ese intervalo. La usan el bot, la CLI de promoción y el
    laboratorio: los tres llegan al mismo valor para el mismo archivo."""
    d = ((doc or {}).get("modelos") or {}).get(intervalo)
    if not isinstance(d, dict):
        return None
    base = {"modelo": d, "version_rasgos": mu.VERSION_RASGOS, "doc": (doc or {}).get("version")}
    return hashlib.sha256(json.dumps(base, sort_keys=True, allow_nan=False).encode()).hexdigest()[:20]

DEFECTOS = {"decide": True, "umbral_r": cb.UMBRAL_R, "max_antiguedad_externos_min": 20,
            # Solo decide con un modelo que el laboratorio no ha suspendido; si no, se abstiene en ese intervalo.
            "estados_validos": ["supera", "exploratorio"],
            # Exploración: SOLO en simulado/shadow, en estos intervalos el cerebro decide aunque su modelo no haya
            # aprobado, para acumular evidencia en vivo. En real nunca (allí además hace falta promoción humana).
            "exploracion_simulado": []}


class CerebroVivo:
    def __init__(self, cfg, ruta, log=None, modo="simulado"):
        self.cfg = dict(DEFECTOS, **(cfg or {}))
        self.modo = modo
        self.ruta, self.log = ruta, log
        self.modelos, self.version, self.huella, self.error = {}, None, None, None
        self.identidades = {}
        self._hash_archivo = None
        self.contadores = {"entra": 0, "no_entra": 0, "abstiene": 0}
        self.ultimas = []
        self.recargar()

    # ------------------------------------------------------------ modelo
    def _vaciar(self, error):
        self.modelos, self.identidades, self.error = {}, {}, error

    def recargar(self):
        """Relee el modelo si cambió su CONTENIDO (no se fía de la fecha del archivo). Ante archivo ausente, JSON
        roto, pesos NaN/inf, rasgos o versión de rasgos desconocidos: sin modelo (falla cerrado)."""
        try:
            with open(self.ruta, "rb") as fh:
                crudo = fh.read()
        except OSError:
            if self._hash_archivo is not None or not self.error:
                self._hash_archivo = None
                self._vaciar("no hay modelo del cerebro: pasa el laboratorio")
            return
        h = hashlib.sha256(crudo).hexdigest()
        if h == self._hash_archivo:
            return
        self._hash_archivo = h
        try:
            doc = json.loads(crudo.decode("utf-8"), parse_constant=_rechazar_no_finito)
            if "version_rasgos" in doc and doc["version_rasgos"] != mu.VERSION_RASGOS:
                raise ValueError(f"versión de rasgos desconocida ({doc['version_rasgos']}; esperada {mu.VERSION_RASGOS})")
            modelos, ids = {}, {}
            for iv, d in (doc.get("modelos") or {}).items():
                if list(d.get("rasgos") or []) not in (list(mu.RASGOS), list(mu.RASGOS_HL)):
                    raise ValueError(f"el modelo de {iv} usa otros rasgos (versión antigua)")
                m = cb.Modelo.desde_dict(d)
                if m is None or not all(math.isfinite(x) for x in m.w):
                    raise ValueError(f"el modelo de {iv} no supera la validación")
                modelos[iv] = (m, d)
                ids[iv] = identidad_modelo(doc, iv)
            self.modelos, self.identidades = modelos, ids
            self.version, self.huella, self.error = doc.get("version"), doc.get("huella"), None
            if self.log:
                self.log.info("Cerebro cargado: %s (huella %s) · %s", self.version, self.huella, ", ".join(modelos))
        except Exception as e:  # noqa: BLE001
            self._vaciar(f"modelo del cerebro inválido: {e}")
            if self.log:
                self.log.error("Cerebro: %s. No entra ninguna operación hasta tener un modelo válido.", self.error)

    def identidad(self, intervalo):
        """Identidad del modelo CARGADO para ese intervalo (None si no hay modelo válido)."""
        return self.identidades.get(intervalo) if not self.error else None

    @property
    def decide(self):
        return bool(self.cfg["decide"])

    # ------------------------------------------------------------ decisión
    def decidir(self, cand, motor, ctx_externo=None, ahora=None):
        """{'abrir', 'prediccion', 'motivo', 'rasgos', 'version', 'faltan'} para una candidata del motor."""
        out = {"abrir": False, "prediccion": None, "version": self.version, "rasgos": None, "faltan": [], "exploracion": False,
               "hash_modelo": None, "version_rasgos": mu.VERSION_RASGOS, "abstencion": False}
        try:
            iv, moneda = cand.get("intervalo"), cand["moneda"]
            par = self.modelos.get(iv)
            if par is None:
                return self._fin(out, "abstiene", self.error or f"sin modelo del cerebro para {iv}: no entra")
            modelo, info = par
            out["hash_modelo"] = self.identidades.get(iv)
            estado = info.get("estado_laboratorio")
            if self.modo == "real" and estado != "supera":
                # En real no hay configuración que valga: solo un modelo que SUPERA el laboratorio (y además la
                # aprobación humana con la misma identidad de modelo, que comprueba el bot).
                return self._fin(out, "abstiene", f"modo real: el modelo de {iv} no supera el laboratorio "
                                                  f"({estado or 'sin veredicto'}): no entra")
            if self.cfg.get("estados_validos") and estado not in self.cfg["estados_validos"]:
                if self.modo != "real" and iv in (self.cfg.get("exploracion_simulado") or []):
                    out["exploracion"] = True
                else:
                    return self._fin(out, "abstiene", f"el modelo de {iv} no supera el laboratorio ({estado or 'sin veredicto'}): no entra")
            ctx = (motor.contextos.get((moneda, iv)) or (None, None))[1]
            if ctx is None or len(ctx) < 60:
                return self._fin(out, "abstiene", "sin velas suficientes para calcular los rasgos")
            fh = (motor.funding_hist.get(moneda) or (None, None, None))[1]
            velas_ext, regs_ext = (ctx_externo.series_cerebro(moneda, iv, self.cfg["max_antiguedad_externos_min"] * 60,
                                                             ahora) if ctx_externo else (None, None))
            ra = mu.rasgos(ctx, len(ctx) - 1, cand["lado"], fh,
                           mu.SerieExterna(velas_ext) if velas_ext else None,
                           mu.FundingHorario(regs_ext) if regs_ext else None)
            out["rasgos"] = ra
            out["faltan"] = [k for k, v in ra.items() if v is None]
            p = modelo.predecir(ra, cand.get("estrategia"))
            out["prediccion"] = round(p, 4)
            pre = "cerebro en exploración (simulado, modelo sin aprobar)" if out["exploracion"] else "cerebro"
            # En el laboratorio casi nunca faltan (16 de 1945) y el modelo aprendió de esos pocos casos que «sin dato»
            # suma: en vivo un dato viejo inflaba la predicción hasta abrir (ENA, 04/11). Sin ellos no se decide.
            sin_externos = [k for k in mu.RASGOS_EXT if k in modelo.rasgos and ra.get(k) is None]
            if sin_externos:
                return self._fin(out, "abstiene", f"{pre}: faltan datos externos, no entra")
            if p > self.cfg["umbral_r"]:
                out["abrir"] = True
                return self._fin(out, "entra", f"{pre}: resultado esperado {p:+.3f} R (> {self.cfg['umbral_r']} R)")
            return self._fin(out, "no_entra", f"{pre}: resultado esperado {p:+.3f} R (≤ {self.cfg['umbral_r']} R)")
        except Exception as e:  # noqa: BLE001
            return self._fin(out, "abstiene", f"error del cerebro ({type(e).__name__}): no entra")

    def _fin(self, out, tipo, motivo):
        out["motivo"] = motivo + (f" · sin dato: {', '.join(out['faltan'])}" if out.get("faltan") else "")
        # Abstenerse (sin modelo, sin datos, error) NO es rechazar: el probador no debe contarlo como «rechazada».
        out["abstencion"] = tipo == "abstiene"
        self.contadores[tipo] += 1
        self.ultimas = (self.ultimas + [{"ts": time.time(), "tipo": tipo, "motivo": out["motivo"],
                                          "prediccion": out["prediccion"]}])[-20:]
        return out

    def resumen(self):
        return {"decide": self.decide, "version": self.version, "huella": self.huella, "error": self.error,
                "identidades": dict(self.identidades), "version_rasgos": mu.VERSION_RASGOS,
                "estados_validos": list(self.cfg.get("estados_validos") or []), "modo": self.modo,
                "exploracion": [] if self.modo == "real" else list(self.cfg.get("exploracion_simulado") or []),
                "modelos": {iv: {"n": d.get("n"), "entrenado_hasta": d.get("entrenado_hasta"), "variante": d.get("variante"),
                                 "estrategias": list(d.get("estrategias") or []),
                                 "estado_laboratorio": d.get("estado_laboratorio"),
                                 "pesos": m.pesos()} for iv, (m, d) in self.modelos.items()},
                "contadores": dict(self.contadores), "ultimas": list(self.ultimas)}
