"""
CoinGlass API v4: fuente OPCIONAL de SOLO LECTURA para investigación y observación (research_only).

  - Nunca opera ni usa endpoints privados: solo GET a los endpoints de lectura de LECTURAS (lista cerrada).
  - Desactivada salvo coinglass.activo = true en config.json Y la variable de entorno COINGLASS_API_KEY. La clave
    nunca se guarda en el repositorio, informes, panel, logs ni pruebas (se enmascara en cualquier error).
  - Sus datos NO cambian entradas, tamaños, stops ni promoción: no hay ninguna ruta del bot que los use para
    decidir. Pasar a usarlos exige validación fuera de muestra y prospectiva, con costes y ablación.
  - Los agregados multi-exchange NO son liquidez ejecutable en Hyperliquid.
  - Cada resultado lleva procedencia: fuente, endpoint, símbolo, intervalo, unidad, hora del evento y de recepción,
    antigüedad y estado explícito (ok | desactivado | sin_clave | timeout | limite_api | error_http | formato_desconocido
    | sin_datos | obsoleto). Lo ausente es None, nunca 0.

Documentación consultada el 28/10/2026: base https://open-api-v4.coinglass.com, cabecera CG-API-KEY, límites por
minuto en las cabeceras API-KEY-MAX-LIMIT / API-KEY-USE-LIMIT. El formato exacto de respuesta y la cobertura
dependen del plan contratado: hay que confirmarlos con una clave real antes de activar nada.
"""

import os
import time

URL_BASE = "https://open-api-v4.coinglass.com"
# Endpoints de lectura permitidos -> (unidad declarada, significado). Cualquier otro se rechaza.
LECTURAS = {
    "/api/futures/open-interest/aggregated-history": ("USD", "interés abierto agregado (OHLC) multi-exchange"),
    "/api/futures/funding-rate/history": ("fracción por intervalo", "funding por exchange y par"),
    "/api/futures/liquidation/aggregated-history": ("USD", "liquidaciones agregadas largo/corto por moneda"),
    "/api/futures/aggregated-taker-buy-sell-volume/history": ("USD", "volumen agresor comprador/vendedor agregado"),
    "/api/hyperliquid/whale-alert": ("USD", "alertas de posiciones grandes en Hyperliquid"),
    "/api/hyperliquid/whale-position": ("USD", "posiciones grandes en Hyperliquid"),
}
DEFECTOS = {"activo": False, "timeout_seg": 10, "max_antiguedad_seg": 3600}


def _enmascarar(texto, clave):
    return str(texto).replace(clave, "***") if clave else str(texto)


class CoinGlass:
    def __init__(self, cfg=None, entorno=None, sesion=None, reloj=time.time):
        self.cfg = dict(DEFECTOS, **(cfg or {}))
        entorno = os.environ if entorno is None else entorno
        self._clave = (entorno.get("COINGLASS_API_KEY") or "").strip()
        self.sesion, self.reloj = sesion, reloj
        self.metricas = {"peticiones": 0, "errores": 0, "limite_api": 0, "timeouts": 0, "ultima_latencia_s": None,
                         "limite_minuto": None, "usado_minuto": None}

    @property
    def estado(self):
        if not self.cfg["activo"]:
            return {"estado": "desactivado", "motivo": "coinglass.activo = false (por defecto)"}
        if not self._clave:
            return {"estado": "sin_clave", "motivo": "falta COINGLASS_API_KEY en el entorno"}
        return {"estado": "activo", "motivo": None}

    def _resultado(self, estado, endpoint, simbolo, intervalo, datos=None, motivo=None, ts_evento=None):
        recibido = self.reloj()
        unidad, significado = LECTURAS.get(endpoint, (None, None))
        antig = (recibido - ts_evento) if ts_evento else None
        if estado == "ok" and antig is not None and antig > self.cfg["max_antiguedad_seg"]:
            estado, motivo = "obsoleto", f"último dato de hace {antig:.0f} s"
        return {"estado": estado, "motivo": motivo, "datos": datos if estado in ("ok", "obsoleto") else None,
                "procedencia": {"fuente": "coinglass", "endpoint": endpoint, "simbolo": simbolo, "intervalo": intervalo,
                                "unidad": unidad, "significado": significado, "cobertura": "agregada multi-exchange"
                                if not endpoint.startswith("/api/hyperliquid") else "hyperliquid",
                                "ts_evento": ts_evento, "ts_recepcion": recibido, "antiguedad_seg": antig},
                "uso_permitido": "research_only"}

    def leer(self, endpoint, simbolo=None, intervalo=None, **params):
        """GET a un endpoint de LECTURAS. Nunca lanza: devuelve un resultado con estado explícito."""
        if endpoint not in LECTURAS:
            raise ValueError(f"endpoint no permitido (solo lectura de la lista cerrada): {endpoint}")
        est = self.estado
        if est["estado"] != "activo":
            return self._resultado(est["estado"], endpoint, simbolo, intervalo, motivo=est["motivo"])
        if self.sesion is None:
            import requests
            self.sesion = requests.Session()
        q = dict(params)
        if simbolo:
            q.setdefault("symbol", simbolo)
        if intervalo:
            q.setdefault("interval", intervalo)
        self.metricas["peticiones"] += 1
        t0 = self.reloj()
        try:
            r = self.sesion.get(URL_BASE + endpoint, params=q, headers={"CG-API-KEY": self._clave, "accept": "application/json"},
                                timeout=self.cfg["timeout_seg"])
        except Exception as e:  # noqa: BLE001
            nombre = type(e).__name__
            self.metricas["errores"] += 1
            if "Timeout" in nombre:
                self.metricas["timeouts"] += 1
                return self._resultado("timeout", endpoint, simbolo, intervalo, motivo="sin respuesta a tiempo")
            return self._resultado("error_http", endpoint, simbolo, intervalo, motivo=_enmascarar(nombre, self._clave))
        self.metricas["ultima_latencia_s"] = round(self.reloj() - t0, 3)
        cab = getattr(r, "headers", {}) or {}
        self.metricas["limite_minuto"] = cab.get("API-KEY-MAX-LIMIT")
        self.metricas["usado_minuto"] = cab.get("API-KEY-USE-LIMIT")
        if r.status_code == 429:
            self.metricas["limite_api"] += 1
            return self._resultado("limite_api", endpoint, simbolo, intervalo, motivo="límite de la API alcanzado")
        if r.status_code != 200:
            self.metricas["errores"] += 1
            return self._resultado("error_http", endpoint, simbolo, intervalo, motivo=f"HTTP {r.status_code}")
        try:
            cuerpo = r.json()
        except ValueError:
            return self._resultado("formato_desconocido", endpoint, simbolo, intervalo, motivo="respuesta no JSON")
        if not isinstance(cuerpo, dict) or "data" not in cuerpo:
            return self._resultado("formato_desconocido", endpoint, simbolo, intervalo, motivo="sin campo 'data'")
        if str(cuerpo.get("code", "0")) not in ("0", "200"):
            return self._resultado("error_http", endpoint, simbolo, intervalo,
                                   motivo=_enmascarar(f"código {cuerpo.get('code')}: {cuerpo.get('msg')}", self._clave)[:200])
        datos = cuerpo["data"]
        if not datos:
            return self._resultado("sin_datos", endpoint, simbolo, intervalo, motivo="respuesta vacía")
        filas = datos if isinstance(datos, list) else [datos]
        # Duplicados por hora: se conserva el último. Hora del evento en s (CoinGlass suele dar ms).
        por_t, sin_t = {}, []
        for f in filas:
            t = f.get("time") if isinstance(f, dict) else None
            if isinstance(t, (int, float)):
                por_t[t / 1000 if t > 1e11 else t] = f
            else:
                sin_t.append(f)
        ordenadas = [por_t[k] for k in sorted(por_t)] + sin_t
        ts_evento = max(por_t) if por_t else None
        return self._resultado("ok", endpoint, simbolo, intervalo, datos=ordenadas, ts_evento=ts_evento)

    def resumen(self):
        """Para el panel/diagnóstico: estado y métricas, SIN la clave."""
        return {"estado": self.estado, "metricas": dict(self.metricas), "uso_permitido": "research_only",
                "endpoints": sorted(LECTURAS)}
