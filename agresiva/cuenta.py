"""Cuenta agresiva simulada y su gemela conservadora. Dinero ficticio; sin red ni disco (quien la posee la guarda).

Una «señal» abre dos piernas con la misma entrada, stop y objetivos (logica.py): la agresiva (riesgo fijo alto,
apalancamiento alto) y la gemela (tamaño normal del bot). Cada pierna se abre por su cuenta: la gemela sigue con la
agresiva en pausa o quebrada (así se sigue midiendo la calidad de las señales) y la agresiva abre aunque la gemela no
pueda (sin saldo, menos de 10 $…).

Frenos de la agresiva (en cada pasada, con el valor de la cuenta a precio de marca):
  - quiebra: por debajo de quiebra_pct % del saldo inicial de la etapa se cierra todo a mercado y se para. Volver a
    empezar solo a mano (`python -m agresiva.motor --reiniciar`), y cada reinicio queda contado.
  - caída: perder freno_caida_pct % desde el inicio de la etapa = pausa de pausa_freno_h horas (una vez por etapa).
  - diario: perder freno_diario_pct % en el día UTC = sin entradas nuevas hasta las 00:00 UTC.
Una pausa solo impide entradas nuevas: lo abierto se sigue gestionando con sus stops y objetivos.
"""

import time

from agresiva import logica

MAX_CERRADAS = 5000
MAX_CURVA = 3000
VERSION = 2
CAMBIOS_V2 = ("Auditoría del 25/11/2026: la agresiva pasa a riesgo fijo (riesgo_pct % hasta el stop; antes margen fijo del 10 %); "
              "cada pierna se abre aunque la otra no pueda; mínimo de 10 $ por orden y parciales redondeados; liquidación por el "
              "libro conservando el margen sobrante; stops y liquidación con vela tipo precio de marca (Hyperliquid + Binance); "
              "funding pagado de verdad (fundingHistory) dentro del margen aislado; objetivos saltados en un hueco se llenan a su precio.")


def _dia(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _medianoche_siguiente(ts):
    return (int(ts) // 86400 + 1) * 86400


def estado_nuevo(ahora, inicial):
    return {"version": VERSION, "creado": ahora, "cambios_reglas": [],
            "etapa": {"n": 1, "inicio": ahora, "inicial_usd": inicial},
            "agresiva": {"libre_usd": inicial, "estado": "activa", "pausa_hasta": 0, "motivo_pausa": None, "freno50_usado": False,
                         "dia": None, "equity_dia": None, "pico_usd": inicial, "caida_max_pct": 0.0},
            "gemela": {"libre_usd": inicial, "inicial_usd": inicial, "pico_usd": inicial, "caida_max_pct": 0.0},
            "abiertas": {}, "cerradas": [], "reinicios": [], "curva": [],
            "contadores": {"senales": 0, "abiertas": 0, "sin_hueco": 0, "solo_gemela": 0, "solo_agresiva": 0}}


def migrar_estado(d, ahora):
    """Cuentas creadas con reglas anteriores: sube la versión y deja anotado qué cambió y cuándo (para no mezclar etapas
    sin saberlo). Devuelve la lista de cambios aplicados ahora."""
    nuevos = []
    if d.get("version", 1) < 2:
        nuevos.append({"ts": ahora, "version": 2, "texto": CAMBIOS_V2})
    d["version"] = max(d.get("version", 1), VERSION)
    d.setdefault("cambios_reglas", []).extend(nuevos)
    d["contadores"].setdefault("solo_agresiva", 0)
    return nuevos


class Cuenta:
    def __init__(self, d, c, max_cerradas=MAX_CERRADAS):
        self.d, self.c, self.max_cerradas = d, c, max_cerradas

    # ------------------------------------------------------------ valor
    def _equity(self, cual, marcas):
        total = self.d[cual]["libre_usd"]
        for coin, s in self.d["abiertas"].items():
            p = s.get(cual)
            if p and p["sz"] > 0:
                total += logica.valor_en_cuenta(p, marcas.get(coin, p["entrada"]))
        return total

    def equity_agresiva(self, marcas):
        return self._equity("agresiva", marcas)

    def equity_gemela(self, marcas):
        return self._equity("gemela", marcas)

    def margen_agresivo(self):
        return sum(logica.margen_restante(s["agresiva"]) for s in self.d["abiertas"].values() if s.get("agresiva") and s["agresiva"]["sz"] > 0)

    # ------------------------------------------------------------ estado de la agresiva
    def puede_abrir_agresiva(self, ahora):
        a = self.d["agresiva"]
        if a["estado"] == "quebrada":
            return False, "cuenta agresiva quebrada"
        if a["estado"] == "pausa":
            if ahora < a["pausa_hasta"]:
                return False, f"en pausa: {a['motivo_pausa']}"
            a["estado"], a["motivo_pausa"], a["pausa_hasta"] = "activa", None, 0
        return True, None

    def frenos(self, ahora, marcas):
        """Aplica los frenos. Devuelve la lista de eventos (para el registro)."""
        a, c, ev = self.d["agresiva"], self.c, []
        g = self.d["gemela"]
        eqg = self.equity_gemela(marcas)
        g["pico_usd"] = max(g["pico_usd"], eqg)
        if g["pico_usd"] > 0:
            g["caida_max_pct"] = max(g["caida_max_pct"], (1 - eqg / g["pico_usd"]) * 100)
        if a["estado"] == "quebrada":
            return ev
        if a["estado"] == "pausa" and ahora >= a["pausa_hasta"]:
            a["estado"], a["motivo_pausa"], a["pausa_hasta"] = "activa", None, 0
        eq = self.equity_agresiva(marcas)
        a["pico_usd"] = max(a["pico_usd"], eq)
        if a["pico_usd"] > 0:
            a["caida_max_pct"] = max(a["caida_max_pct"], (1 - eq / a["pico_usd"]) * 100)
        inicial = self.d["etapa"]["inicial_usd"]
        if eq < inicial * c["quiebra_pct"] / 100:
            cierres = self.cerrar_agresivas(marcas, ahora, "quiebra")
            a["estado"], a["motivo_pausa"], a["pausa_hasta"] = "quebrada", f"la cuenta bajó de {c['quiebra_pct']:g} % del saldo inicial", 0
            a["quebrada_ts"] = ahora
            ev.append({"tipo": "quiebra", "equity_usd": round(self.equity_agresiva(marcas), 4), "cierres": cierres})
            return ev
        dia = _dia(ahora)
        if a["dia"] != dia:
            a["dia"], a["equity_dia"] = dia, eq
        if not a["freno50_usado"] and eq <= inicial * (1 - c["freno_caida_pct"] / 100):
            a["freno50_usado"] = True
            a["estado"], a["pausa_hasta"] = "pausa", ahora + c["pausa_freno_h"] * 3600
            a["motivo_pausa"] = f"perdido el {c['freno_caida_pct']:g} % desde el inicio: {c['pausa_freno_h']:g} h sin entradas"
            ev.append({"tipo": "freno_caida", "equity_usd": round(eq, 4), "hasta": a["pausa_hasta"]})
        elif a["equity_dia"] and eq <= a["equity_dia"] * (1 - c["freno_diario_pct"] / 100) and \
                not (a["estado"] == "pausa" and a["pausa_hasta"] >= _medianoche_siguiente(ahora)):
            a["estado"], a["pausa_hasta"] = "pausa", _medianoche_siguiente(ahora)
            a["motivo_pausa"] = f"perdido el {c['freno_diario_pct']:g} % hoy: sin entradas hasta las 00:00 UTC"
            ev.append({"tipo": "freno_diario", "equity_usd": round(eq, 4), "hasta": a["pausa_hasta"]})
        return ev

    # ------------------------------------------------------------ abrir
    def hay_hueco(self):
        return len(self.d["abiertas"]) < self.c["max_abiertas"]

    def abrir(self, coin, det, mercado, marcas, llenar, ahora):
        """det: señal de logica.detectar. mercado: {"sz_dec", "apal_max", "tramos"}. llenar(compra, sz) -> precio medio o
        None (sin liquidez). Devuelve la señal abierta o un dict {"error": motivo}."""
        c = self.c
        if coin in self.d["abiertas"]:
            return {"error": "ya hay una señal abierta en esa moneda"}
        if not self.hay_hueco():
            self.d["contadores"]["sin_hueco"] += 1
            return {"error": f"sin hueco ({c['max_abiertas']} abiertas)"}
        lado, px_ref = det["lado"], det["precio"]
        pl_ref = logica.plan(lado, px_ref, det["atr"], c)
        compra = lado > 0
        t_ms = int(ahora * 1000)

        def pierna(tipo, sz, apal, equity):
            """Llena en el libro y crea la pierna con stop y objetivos medidos desde el precio real. None si no hay liquidez."""
            px = llenar(compra, sz)
            if not px:
                return None
            pl = logica.plan(lado, px, det["atr"], c)
            com = sz * px * c["comision_taker_pct"] / 100
            return logica.nueva_pierna(tipo, lado, px, sz, apal, mercado["apal_max"], pl, com, t_ms, equity,
                                       sz_dec=mercado["sz_dec"], min_usd=c["min_orden_usd"], reparto=c["reparto_objetivos"])

        # Cada pierna se abre por su cuenta (auditoría 25/11/2026, F1): antes, si la gemela no podía, tampoco abría la agresiva.
        g = self.d["gemela"]
        eqg = self.equity_gemela(marcas)
        gem, sin_gemela = None, None
        tg = logica.tamano_gemela(eqg, g["libre_usd"], px_ref, pl_ref["stop_pct"], mercado["sz_dec"], mercado["apal_max"], c)
        if tg["ok"]:
            gem = pierna("gemela", tg["sz"], tg["apal"], eqg)
            sin_gemela = None if gem else "sin liquidez para entrar"
        else:
            sin_gemela = tg["motivo"]

        agr = None
        ok, motivo = self.puede_abrir_agresiva(ahora)
        if ok:
            a = self.d["agresiva"]
            eqa = self.equity_agresiva(marcas)
            ta = logica.tamano_agresiva(eqa, a["libre_usd"], self.margen_agresivo(), px_ref, pl_ref["stop_pct"], mercado["sz_dec"],
                                        mercado["apal_max"], mercado.get("tramos"), c)
            if ta["ok"]:
                agr = pierna("agresiva", ta["sz"], ta["apal"], eqa)
                motivo = None if agr else "sin liquidez para el tamaño agresivo"
                if agr and ta.get("recortado"):
                    agr["recortada"] = True                         # el margen no cabía: arriesga menos de riesgo_pct
            else:
                motivo = ta["motivo"]
        if gem is None and agr is None:
            return {"error": f"ni gemela ({sin_gemela}) ni agresiva ({motivo})"}
        if gem:
            g["libre_usd"] -= gem["margen0"] + gem["comisiones_usd"]
        if agr:
            self.d["agresiva"]["libre_usd"] -= agr["margen0"] + agr["comisiones_usd"]
        cont = self.d["contadores"]
        if agr is None:
            cont["solo_gemela"] = cont.get("solo_gemela", 0) + 1
        if gem is None:
            cont["solo_agresiva"] = cont.get("solo_agresiva", 0) + 1
        ref = gem or agr
        s = {"id": f"AGR-{coin}-{det['t']}", "coin": coin, "regla": det["regla"], "lado": lado, "t_senal": det["t"],
             "precio_senal": px_ref, "atr": det["atr"], "stop_pct": logica.plan(lado, ref["entrada"], det["atr"], c)["stop_pct"],
             "apal_max_mercado": mercado["apal_max"], "abierta_ms": t_ms, "ultimo_min_ms": t_ms, "funding_ms": t_ms,
             "agresiva": agr, "sin_agresiva": motivo, "gemela": gem, "sin_gemela": sin_gemela}
        self.d["abiertas"][coin] = s
        cont["abiertas"] += 1
        return s

    # ------------------------------------------------------------ avanzar y cerrar
    def _abono(self, cual, delta):
        self.d[cual]["libre_usd"] += delta

    @staticmethod
    def migrar(s):
        """Piernas abiertas antes de la auditoría del 25/11/2026: añade el mantenimiento y el margen de funding que la
        lógica nueva necesita (su liquidación y su funding siguen las reglas nuevas desde ahora)."""
        for cual in ("agresiva", "gemela"):
            p = s.get(cual)
            if p:
                p.setdefault("mmr", logica.mmr_de(s.get("apal_max_mercado") or 1))
                p.setdefault("margen_extra", 0.0)
        s.setdefault("sin_gemela", None)
        return s

    def avanzar(self, coin, vela, disparo=None):
        """Pasa una vela por las dos piernas de la señal de esa moneda. Devuelve los eventos. disparo: vela con la que se
        miran stop y liquidación (logica.vela_disparo, tipo precio de marca); por defecto, la misma."""
        s = self.d["abiertas"].get(coin)
        if not s:
            return []
        self.migrar(s)
        eventos = []
        for cual in ("agresiva", "gemela"):
            p = s.get(cual)
            if p and p["sz"] > 0:
                delta, evs = logica.avanzar(p, disparo or vela, self.c)
                self._abono(cual, delta)
                eventos += [dict(e, pierna=cual) for e in evs]
        if eventos:                                    # para marcarlos en el gráfico de la señal
            s["eventos"] = (s.get("eventos") or []) + [{"t": e["t"], "tipo": e["tipo"], "px": e["px"], "pierna": e["pierna"]}
                                                       for e in eventos]
            del s["eventos"][:-40]
        s["ultimo_min_ms"] = max(s["ultimo_min_ms"], vela["t"])
        if vela["t"] - s["abierta_ms"] >= self.c["horas_max"] * 3_600_000:
            eventos += self._cerrar_senal_mercado(s, vela["c"], vela["t"], "tiempo")
        self._archivar_si_cerrada(coin)
        return eventos

    def _cerrar_senal_mercado(self, s, px, t_ms, motivo, solo=None):
        evs = []
        for cual in (solo,) if solo else ("agresiva", "gemela"):
            p = s.get(cual)
            if p and p["sz"] > 0:
                delta, ev = logica.cerrar_mercado(p, px, self.c, t_ms, motivo)
                self._abono(cual, delta)
                if ev:
                    evs.append(dict(ev, pierna=cual))
        return evs

    def funding(self, coin, marca, tasa):
        """Un pago de funding a las piernas abiertas de la moneda. Va al margen aislado de cada pierna (no al saldo libre):
        se libera al cerrar y mueve el precio de liquidación."""
        s = self.d["abiertas"].get(coin)
        total = {}
        if s:
            self.migrar(s)
        for cual in ("agresiva", "gemela"):
            p = s.get(cual) if s else None
            if p and p["sz"] > 0:
                total[cual] = logica.aplicar_funding(p, marca, tasa)
        return total

    def cerrar_agresivas(self, marcas, ahora, motivo):
        evs = []
        for coin, s in list(self.d["abiertas"].items()):
            if s.get("agresiva") and s["agresiva"]["sz"] > 0:
                evs += [dict(e, coin=coin) for e in self._cerrar_senal_mercado(s, marcas.get(coin, s["agresiva"]["entrada"]),
                                                                              int(ahora * 1000), motivo, solo="agresiva")]
            self._archivar_si_cerrada(coin)
        return evs

    def _archivar_si_cerrada(self, coin):
        s = self.d["abiertas"].get(coin)
        if not s or any(s.get(k) and s[k]["sz"] > 0 for k in ("agresiva", "gemela")):
            return None
        fila = {"id": s["id"], "coin": coin, "regla": s["regla"], "lado": s["lado"], "abierta_ms": s["abierta_ms"],
                "precio_senal": s["precio_senal"], "stop_pct": s["stop_pct"], "apal_max_mercado": s["apal_max_mercado"],
                "etapa": self.d["etapa"]["n"], "sin_agresiva": s.get("sin_agresiva"), "sin_gemela": s.get("sin_gemela")}
        for cual in ("agresiva", "gemela"):
            p = s.get(cual)
            fila[cual] = None if not p else {
                "entrada": p["entrada"], "salida_px": p["salida_px"], "salida": p["salida"], "cerrada_ms": p["cerrada_ms"],
                "apal": p["apal"], "margen_usd": round(p["margen0"], 4), "liq": p["liq"], "objetivos_tocados": p["toc"],
                "pnl_usd": round(p["pnl_usd"], 4), "r": round(logica.resultado_r(p), 4),
                "comisiones_usd": round(p["comisiones_usd"], 4), "funding_usd": round(p["funding_usd"], 4),
                "riesgo_pct": round(logica.riesgo_inicial(p) / p["equity_entrada"] * 100, 3) if p["equity_entrada"] else None,
                "pct_cuenta": round(p["pnl_usd"] / p["equity_entrada"] * 100, 3) if p["equity_entrada"] else None}
        fila["cerrada_ms"] = max((fila[k]["cerrada_ms"] or 0) for k in ("agresiva", "gemela") if fila[k])
        self.d["cerradas"].append(fila)
        if self.max_cerradas:
            del self.d["cerradas"][:-self.max_cerradas]
        del self.d["abiertas"][coin]
        return fila

    # ------------------------------------------------------------ reinicio y curva
    def reiniciar(self, marcas, ahora):
        """Nueva etapa de la agresiva (solo a mano). Cierra lo agresivo abierto a mercado y vuelve al saldo inicial. La
        gemela y el historial no se tocan; el reinicio queda contado."""
        cierres = self.cerrar_agresivas(marcas, ahora, "reinicio")
        a = self.d["agresiva"]
        antes = {"etapa": self.d["etapa"]["n"], "inicio": self.d["etapa"]["inicio"], "fin": ahora,
                 "inicial_usd": self.d["etapa"]["inicial_usd"], "final_usd": round(a["libre_usd"], 4),
                 "estado_final": a["estado"], "caida_max_pct": round(a["caida_max_pct"], 2)}
        self.d["reinicios"].append(antes)
        inicial = float(self.c["cuenta_inicial_usd"])
        self.d["etapa"] = {"n": antes["etapa"] + 1, "inicio": ahora, "inicial_usd": inicial}
        self.d["agresiva"] = estado_nuevo(ahora, inicial)["agresiva"]
        return antes, cierres

    def anotar_curva(self, ahora, marcas):
        curva = self.d["curva"]
        if curva and ahora - curva[-1][0] < 900:
            return
        curva.append([int(ahora), round(self.equity_agresiva(marcas), 4), round(self.equity_gemela(marcas), 4)])
        del curva[:-MAX_CURVA]
