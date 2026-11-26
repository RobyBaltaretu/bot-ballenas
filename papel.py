"""
Modo SIMULADO (paper): una cuenta ficticia propia que se comporta como Hyperliquid pero sin dinero.

  - Precios, libro de órdenes, velas, funding y ballenas: REALES, en directo desde Hyperliquid.
  - Saldo, posiciones, órdenes, comisiones, funding y resultados: ficticios, guardados en papel.json.
  - No necesita claves y NO puede enviar nada a ninguna cuenta: no tiene cliente firmante.

Ofrece el mismo contrato que usa el bot con Hyperliquid, para que el modo simulado ejercite el mismo código:
  order(..., cloid=), cancel(oid), cancel_by_cloid(cloid), update_leverage(),
  y por el lado de consulta: user_state, frontend_open_orders (con cloid), user_fills (con oid y cloid),
  query_order_by_oid / query_order_by_cloid (estados open/filled/canceled/triggered/rejected),
  user_funding_history (funding SIMULADO cada hora con la tasa real del momento), user_fees.

Cómo se ejecutan las órdenes (se comprueba en cada ciclo del bot, ~15 s). Modelo conservador (MODELO = 2):
  - IOC ("a mercado" con precio límite): recorre los niveles REALES del libro (impacto según tamaño) sin pasar
    del límite; lo que no cabe se cancela (fill PARCIAL, como en Hyperliquid); comisión taker.
  - Límite post-only (ALO): se rechaza si cruzaría; si no, espera y se llena (MODELO 3) solo si hay contrapartida
    real a su precio en el libro o si una operación real se imprimió PEOR que su precio (velas de 1 min): así la
    cola entera se consumió. Que el precio medio la cruce ya no basta. Tocarla no llena; comisión maker.
  - Límite GTC reduce-only (objetivos): igual; maker.
  - IOC y stops recorren los 20 niveles visibles y, si no bastan, el libro AGREGADO (más alcance en precio).
  - Stop (trigger, de mercado): se ACTIVA con el precio de MARCA (mark), como en Hyperliquid, y se ejecuta
    contra el libro real (bid para vender, ask para comprar, recorriendo niveles) con la tolerancia del 10 % de
    las órdenes de mercado: el precio de salida puede ser bastante peor que el del stop; taker.
  - Liquidación (ESTIMADA): margen aislado con la fórmula de Hyperliquid (margen de mantenimiento = mitad del
    margen inicial al apalancamiento máximo del mercado). Si la marca la cruza, la posición se cierra a ese
    precio y queda registrado. Es una estimación: en real manda el liquidationPx del exchange.
  - Funding: cada hora en punto con la tasa real vigente, sobre el nocional al precio del ORÁCULO (como en
    Hyperliquid; si no hay oráculo, la marca).
Limitaciones (explícitas): mira el precio cada pocos segundos (no cada tick); no simula la cola ni la
prioridad de las órdenes límite; el libro es una foto (no reacciona a nuestra orden); la marca se lee como
mucho cada pocos segundos; la liquidación es estimada.
"""

import json
import threading
import time

from compat import reemplazar

MODELO = 4                     # versión del modelo de ejecución (entra en la huella vía promocion.MODELO_SIMULACION)
                               # 4 (26/11/2026): funding de las horas perdidas tras un parón (CP-M15)
HUECO_MIN_S = 180              # sin procesar más de 3 min = el bot estuvo parado: se repasan las velas del hueco
TOLERANCIA_MERCADO = 0.10     # las órdenes trigger de mercado de Hyperliquid admiten un 10 % de deslizamiento
MAX_HORAS_FUNDING_PERDIDAS = 24 * 7   # tras un parón, se recupera el funding de hasta 7 días (CP-M15)


def _cloid_txt(cloid):
    if cloid is None:
        return None
    if hasattr(cloid, "to_raw"):
        return cloid.to_raw()
    return str(cloid)


class CuentaPapel:
    def __init__(self, info_real, ruta, saldo_inicial, comision_maker, comision_taker, log=None):
        self.info = info_real
        self.ruta = ruta
        self.maker, self.taker = comision_maker, comision_taker
        self.log = log
        self.bloqueo = threading.RLock()
        self._mids_cache = (0.0, {})
        self._ctx_cache = (0.0, {})          # moneda -> {"mark", "oraculo", "apal_max"}
        try:
            with open(ruta, encoding="utf-8") as f:
                self.d = json.load(f)
        except FileNotFoundError:
            self.d = {"efectivo": saldo_inicial, "saldo_inicial": saldo_inicial, "posiciones": {},
                      "ordenes": [], "fills": [], "oid": 1, "apalancamiento": {}}
        # Saldo inicial cambiado en la configuración: solo se adopta si la cuenta simulada está SIN ESTRENAR
        # (sin operaciones, posiciones ni órdenes y con el efectivo intacto). Con historia, se respeta la cuenta.
        if (saldo_inicial and float(self.d.get("saldo_inicial") or 0) != float(saldo_inicial)
                and not self.d.get("fills") and not self.d.get("posiciones") and not self.d.get("ordenes")
                and float(self.d.get("efectivo") or 0) == float(self.d.get("saldo_inicial") or 0)):
            if self.log:
                self.log.info(f"Cuenta simulada sin estrenar: saldo inicial {self.d.get('saldo_inicial')} → "
                              f"{saldo_inicial} USD (config.saldo_simulado_usd)")
            # Evento EXPLÍCITO de capital (depósito/retirada): el bot ajusta sus referencias con esta hora exacta.
            self.d.setdefault("ajustes_capital", []).append({"ts": time.time(), "de": self.d.get("saldo_inicial"),
                                                             "a": saldo_inicial})
            self.d["efectivo"] = self.d["saldo_inicial"] = saldo_inicial
        # Campos añadidos en versiones nuevas (compatibles con papel.json antiguos)
        self.d.setdefault("historial_ordenes", {})     # oid -> {estado, coin, cloid, origSz, sz, ...}
        self.d.setdefault("funding", [])
        self.d.setdefault("ultima_hora_funding", int(time.time() // 3600))
        self._guardar()

    # ---------------------------------------------------------------- base
    def _guardar(self):
        self.d["fills"] = self.d["fills"][-3000:]
        self.d["funding"] = self.d["funding"][-5000:]
        if len(self.d["historial_ordenes"]) > 5000:
            for k in sorted(self.d["historial_ordenes"], key=int)[:-5000]:
                self.d["historial_ordenes"].pop(k, None)
        tmp = self.ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.d, f, indent=1)
        reemplazar(tmp, self.ruta)

    def _mids(self):
        t, mids = self._mids_cache
        if time.time() - t > 2:
            mids = {k: float(v) for k, v in self.info.all_mids().items()}
            self._mids_cache = (time.time(), mids)
        return mids

    def _ctx(self):
        """Marca, oráculo y apalancamiento máximo de cada moneda (cacheado 10 s: pesa 20 en el límite de Hyperliquid y
        el bot la pedía en cada procesar(); cada 3 s gastaba ~400 de los 900 de peso por minuto. El ciclo es de 15 s)."""
        t, ctx = self._ctx_cache
        if time.time() - t > 10:
            try:
                meta, ctxs = self.info.meta_and_asset_ctxs()
                ctx = {a["name"]: {"mark": float(x.get("markPx") or 0) or None,
                                   "oraculo": float(x.get("oraclePx") or 0) or None,
                                   "funding": float(x.get("funding") or 0),
                                   "apal_max": a.get("maxLeverage")}
                       for a, x in zip(meta["universe"], ctxs)}
                self._ctx_cache = (time.time(), ctx)
            except Exception:  # noqa: BLE001  (sin contexto: se usa el mid y se marca como aproximado)
                pass
        return self._ctx_cache[1]

    def _marca(self, moneda):
        return (self._ctx().get(moneda) or {}).get("mark") or self._mids().get(moneda)

    def _libro(self, moneda, cifras=None):
        """Libro real. Hyperliquid solo da 20 niveles por lado; con 'cifras' (nSigFigs) pide el libro AGREGADO, que
        llega más lejos en precio (para ver la liquidez que hay detrás de los 20 primeros niveles)."""
        if cifras:
            niveles = self.info.post("/info", {"type": "l2Book", "coin": moneda, "nSigFigs": cifras})["levels"]
        else:
            # El bot pregunta muchas veces por ciclo: la foto del libro dura lo mismo que la de los mids (se renueva
            # en cuanto se renuevan ellos).
            cache = self.__dict__.setdefault("_libro_cache", {})
            ref, niveles = cache.get(moneda, (None, None))
            if niveles is None or ref is not self._mids_cache:
                niveles = self.info.l2_snapshot(moneda)["levels"]
                cache[moneda] = (self._mids_cache, niveles)
        bids = [(float(x["px"]), float(x["sz"])) for x in niveles[0]]
        asks = [(float(x["px"]), float(x["sz"])) for x in niveles[1]]
        return bids, asks

    def _mejores(self, moneda):
        bids, asks = self._libro(moneda)
        mid = self._mids().get(moneda)
        return (bids[0][0] if bids else mid), (asks[0][0] if asks else mid)

    @staticmethod
    def _recorrer(lado, compra, sz, limite, desde_px=None):
        """Toma liquidez de 'lado' hasta 'limite'. Con 'desde_px' solo usa niveles PEORES que ese precio (los ya
        consumidos del libro fino no se cuentan dos veces). Devuelve (ejecutado, coste)."""
        resto, coste = sz, 0.0
        for px, cant in lado:
            if (compra and px > limite) or (not compra and px < limite):
                break
            if desde_px is not None and ((compra and px <= desde_px) or (not compra and px >= desde_px)):
                continue
            toma = min(resto, cant)
            coste += toma * px
            resto -= toma
            if resto <= 1e-12:
                break
        return sz - max(resto, 0.0), coste

    def _barrer(self, moneda, compra, sz, limite, profundo=False):
        """Recorre el libro real del lado contrario sin pasar de 'limite'. Devuelve (ejecutado, precio_medio).
        Con 'profundo' (stops y cierres), si los 20 niveles visibles no bastan y el límite está más lejos, sigue con
        el libro agregado de Hyperliquid (más alcance en precio, precio de cada tramo = el de su nivel agregado)."""
        bids, asks = self._libro(moneda)
        lado = asks if compra else bids
        hecho, coste = self._recorrer(lado, compra, sz, limite)
        if profundo and sz - hecho > 1e-12 and lado:
            ultimo = lado[-1][0]
            for cifras in (3, 2):
                try:
                    b2, a2 = self._libro(moneda, cifras)
                except Exception:  # noqa: BLE001  (sin libro agregado: se queda lo que había en el visible)
                    break
                mas, c2 = self._recorrer(a2 if compra else b2, compra, sz - hecho, limite, desde_px=ultimo)
                if mas > 1e-12:
                    hecho, coste = hecho + mas, coste + c2
                    lado2 = a2 if compra else b2
                    ultimo = lado2[-1][0] if lado2 else ultimo
                if sz - hecho <= 1e-12:
                    break
        return (hecho, coste / hecho) if hecho > 1e-12 else (0.0, None)

    def _liquidacion(self, moneda, pos):
        """Precio de liquidación ESTIMADO (margen aislado, fórmula de Hyperliquid)."""
        apal = self.d["apalancamiento"].get(moneda, 1)
        apal_max = (self._ctx().get(moneda) or {}).get("apal_max") or apal
        szi = pos["szi"]
        lado = 1 if szi > 0 else -1
        tam = abs(szi)
        margen = tam * pos["entrada"] / max(apal, 1e-9)
        mmr = 1 / (2 * max(apal_max, 1))               # mantenimiento = mitad del inicial al apalancamiento máximo
        disponible = margen - tam * pos["entrada"] * mmr
        px = pos["entrada"] - lado * disponible / tam / (1 - mmr * lado)
        return px if px > 0 else None

    def _nuevo_oid(self):
        self.d["oid"] += 1
        return self.d["oid"]

    @staticmethod
    def _ok(estado):
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [estado]}}}

    def _historial(self, oid, **campos):
        h = self.d["historial_ordenes"].setdefault(str(oid), {"oid": oid})
        h.update(campos)
        h["statusTimestamp"] = int(time.time() * 1000)
        return h

    # ------------------------------------------------------------ ejecución
    def _ejecutar(self, moneda, compra, sz, px, comision, oid=None, cloid=None, nota=None):
        """Aplica un fill a la cuenta ficticia. Devuelve el tamaño ejecutado."""
        pos = self.d["posiciones"].get(moneda, {"szi": 0.0, "entrada": 0.0})
        szi, entrada = pos["szi"], pos["entrada"]
        delta = sz if compra else -sz
        pnl = 0.0
        if szi == 0 or (szi > 0) == (delta > 0):
            nuevo = szi + delta
            entrada = (entrada * abs(szi) + px * sz) / abs(nuevo)
        else:
            cerrado = min(abs(szi), sz)
            pnl = cerrado * (px - entrada) * (1 if szi > 0 else -1)
            nuevo = szi + delta
            if nuevo != 0 and (nuevo > 0) != (szi > 0):
                entrada = px  # se dio la vuelta
        fee = px * sz * comision
        self.d["efectivo"] += pnl - fee
        if abs(nuevo) < 1e-12:
            self.d["posiciones"].pop(moneda, None)
        else:
            self.d["posiciones"][moneda] = {"szi": nuevo, "entrada": entrada}
        self.d["fills"].append({"coin": moneda, "time": int(time.time() * 1000), "px": str(px), "sz": str(sz),
                                "side": "B" if compra else "A", "closedPnl": str(round(pnl, 6)),
                                "fee": str(round(fee, 6)), "startPosition": str(szi), "oid": oid,
                                "cloid": cloid, "crossed": comision == self.taker,
                                "tid": f"papel-{self.d.get('n_fill', 0) + 1}", "nota": nota})
        self.d["n_fill"] = self.d.get("n_fill", 0) + 1
        return sz

    def _funding(self):
        """Cada hora en punto: paga/cobra funding con la tasa REAL vigente (positiva = los largos pagan)."""
        hora = int(time.time() // 3600)
        if hora <= self.d["ultima_hora_funding"] or not self.d["posiciones"]:
            self.d["ultima_hora_funding"] = max(self.d["ultima_hora_funding"], hora)
            return False
        try:
            meta, ctxs = self.info.meta_and_asset_ctxs()
            tasas = {a["name"]: (float(x.get("funding") or 0), float(x.get("oraclePx") or 0) or float(x.get("markPx") or 0))
                     for a, x in zip(meta["universe"], ctxs)}
        except Exception:  # noqa: BLE001  (sin datos: no se inventa el funding; se reintenta en el siguiente ciclo)
            return False
        # CP-M15 (auditoría 26/11, T-08): las horas en que el bot estuvo parado también se pagan/cobran, cada una con
        # su tasa REAL (fundingHistory). Antes solo se aplicaba la hora de la vuelta.
        perdidas = list(range(max(self.d["ultima_hora_funding"] + 1, hora - MAX_HORAS_FUNDING_PERDIDAS), hora))
        if perdidas:
            self._funding_perdido(perdidas, tasas)
        for m, p in self.d["posiciones"].items():
            if m not in tasas:
                continue
            tasa, oraculo = tasas[m]
            oraculo = oraculo or self._mids().get(m, p["entrada"])
            pago = -p["szi"] * oraculo * tasa          # Hyperliquid usa el precio del oráculo para el nocional
            self.d["efectivo"] += pago
            self.d["funding"].append({"time": hora * 3600_000, "hash": None, "simulado": True,
                                      "delta": {"type": "funding", "coin": m, "usdc": str(round(pago, 8)),
                                                "szi": str(p["szi"]), "fundingRate": str(tasa)}})
        self.d["ultima_hora_funding"] = hora
        return True

    def _funding_perdido(self, horas, tasas):
        """Funding de las 'horas' (enteros, hora UTC desde epoch) en que el bot no estuvo: tasa real de cada hora
        (fundingHistory) y precio de apertura de su vela de 1 h (si falta, el oráculo actual). Supone el tamaño que
        hay ahora durante todo el hueco (las órdenes del hueco se repasan después). Sin historia de una moneda no se
        inventa nada: queda en el log."""
        desde, hasta = horas[0] * 3600_000, (horas[-1] + 1) * 3600_000 - 1
        for m, p in self.d["posiciones"].items():
            try:
                hist = self.info.funding_history(m, desde, hasta) or []
            except Exception as e:  # noqa: BLE001
                if self.log:
                    self.log.warning(f"Funding simulado: no pude leer la historia de {m} para {len(horas)} h perdidas "
                                     f"({e}); esas horas quedan sin aplicar")
                continue
            por_hora = {}
            for x in hist:
                try:
                    por_hora[int(x["time"]) // 3600_000] = float(x["fundingRate"])
                except (KeyError, TypeError, ValueError):
                    continue
            try:
                velas = self.info.candles_snapshot(m, "1h", desde, hasta) or []
                precios = {int(v["t"]) // 3600_000: float(v["o"]) for v in velas}
            except Exception:  # noqa: BLE001
                precios = {}
            reserva = (tasas.get(m) or (0.0, 0.0))[1] or self._mids().get(m, p["entrada"])
            aplicadas = 0
            for h in horas:
                if h not in por_hora:
                    continue
                tasa = por_hora[h]
                pago = -p["szi"] * (precios.get(h) or reserva) * tasa
                self.d["efectivo"] += pago
                self.d["funding"].append({"time": h * 3600_000, "hash": None, "simulado": True, "recuperado": True,
                                          "delta": {"type": "funding", "coin": m, "usdc": str(round(pago, 8)),
                                                    "szi": str(p["szi"]), "fundingRate": str(tasa)}})
                aplicadas += 1
            if self.log and aplicadas < len(horas):
                self.log.warning(f"Funding simulado: {m} sin tasa para {len(horas) - aplicadas} de {len(horas)} h "
                                 f"perdidas; no se inventan")

    def _velas_1m(self, moneda, desde_ms):
        """Velas REALES de 1 minuto desde 'desde_ms' (cacheadas 30 s). Sirven para saber si hubo operaciones a un
        precio peor que nuestra orden entre dos comprobaciones (mechas que el muestreo cada pocos segundos no ve)."""
        cache = self.__dict__.setdefault("_velas_cache", {})
        t, desde, lista = cache.get(moneda, (0.0, None, []))
        if time.time() - t > 30 or desde is None or desde > desde_ms:
            try:
                lista = self.info.candles_snapshot(moneda, "1m", int(desde_ms), int(time.time() * 1000)) or []
            except Exception:  # noqa: BLE001  (sin velas: solo cuenta la contrapartida en el libro)
                lista = []
            cache[moneda] = (time.time(), desde_ms, lista)
        return lista

    def _limite_llena(self, o):
        """¿Se habría llenado ENTERA esta orden límite en reposo? (MODELO 3). Nuestra orden no está en el libro real,
        así que se mira lo que la habría ejecutado de verdad:
          a) contrapartida en el libro AL precio o mejor (compra: hay asks ≤ px; venta: bids ≥ px). Esos vendedores
             (compradores) habrían cruzado con nosotros;
          b) una operación real impresa ESTRICTAMENTE peor que nuestro precio desde que la orden está puesta (mínimo
             de vela de 1 min < px en compra; máximo > px en venta): todo el nivel, cola incluida, se consumió.
        Ya NO basta con que el precio MEDIO la cruce (antes: con el diferencial abierto el medio cruzaba sin que nadie
        operase a nuestro precio, y se llenaba de más). Tocar el precio exacto no llena (la cola no se conoce)."""
        # Foto propia de 15 s por moneda: el bot llama a procesar() muchas veces por ciclo y pedir el libro en cada una
        # saturaba el limitador de peticiones (las mechas entre fotos las recogen las velas).
        cache = self.__dict__.setdefault("_libro_reposo", {})
        t, libro = cache.get(o["coin"], (0.0, None))
        if libro is None or time.time() - t > 15:
            try:
                libro = self._libro(o["coin"])
            except Exception:  # noqa: BLE001
                libro = ([], [])
            cache[o["coin"]] = (time.time(), libro)
        bids, asks = libro
        if o["compra"] and asks and asks[0][0] <= o["px"]:
            return True
        if not o["compra"] and bids and bids[0][0] >= o["px"]:
            return True
        desde = (int(o.get("ts") or time.time() * 1000) // 60_000 + 1) * 60_000   # velas que empiezan DESPUÉS
        for v in self._velas_1m(o["coin"], desde):
            try:
                if int(v["t"]) < desde:
                    continue
                if o["compra"] and float(v["l"]) < o["px"]:
                    return True
                if not o["compra"] and float(v["h"]) > o["px"]:
                    return True
            except (KeyError, TypeError, ValueError):
                continue
        return False

    def _primer_toque(self, o, velas, desde_ms):
        """(t, precio) de la primera vela de 1 min desde 'desde_ms' en que esta orden reduce-only se habría ejecutado,
        o None. Stop: el precio negociado llega al disparo (las velas son de operaciones, no de marca: aproximación);
        se llena al disparo o, si la vela ya abrió peor (hueco), a su apertura, nunca peor que la tolerancia del 10 %.
        Límite: como en _limite_llena, una operación impresa ESTRICTAMENTE peor que su precio; se llena a su precio."""
        for v in velas:
            try:
                t, ap, lo, hi = int(v["t"]), float(v["o"]), float(v["l"]), float(v["h"])
            except (KeyError, TypeError, ValueError):
                continue
            if t < desde_ms:
                continue
            if o["tipo"] == "stop":
                trig = o["trigger"]
                if o["compra"] and hi >= trig:
                    return t, min(max(trig, ap), trig * (1 + TOLERANCIA_MERCADO))
                if not o["compra"] and lo <= trig:
                    return t, max(min(trig, ap), trig * (1 - TOLERANCIA_MERCADO))
            elif (o["compra"] and lo < o["px"]) or (not o["compra"] and hi > o["px"]):
                return t, o["px"]
        return None

    def _recuperar_hueco(self, desde_ms):
        """El bot estuvo parado (R-14 de la auditoría): mientras tanto nadie miraba los stops ni los objetivos y, al
        volver, una posición cuyo stop se cruzó y el precio regresó seguía abierta (optimista). Aquí se repasan las velas
        reales de 1 min del hueco y se ejecutan, EN ORDEN CRONOLÓGICO por moneda, las órdenes reduce-only que se habrían
        disparado. Es una estimación (sin el libro de aquel momento): el fill va marcado como tal."""
        cambio = False
        for m in list(self.d["posiciones"]):
            cursor = desde_ms
            velas = None
            while m in self.d["posiciones"]:
                pos = self.d["posiciones"][m]
                ordenes = [o for o in self.d["ordenes"] if o["coin"] == m and o["reduce_only"]
                           and (pos["szi"] > 0) != o["compra"]]
                if not ordenes:
                    break
                if velas is None:
                    velas = sorted(self._velas_1m(m, cursor), key=lambda v: int(v.get("t", 0)))
                toques = []
                for o in ordenes:
                    r = self._primer_toque(o, velas, max(cursor, (int(o.get("ts") or 0) // 60_000 + 1) * 60_000))
                    if r:
                        toques.append((r[0], 0 if o["tipo"] == "stop" else 1, r[1], o))   # misma vela: el stop primero
                if not toques:
                    break
                t, _, px, o = min(toques, key=lambda x: x[:2])
                sz = min(o["sz"], abs(pos["szi"]))
                es_stop = o["tipo"] == "stop"
                self._ejecutar(m, o["compra"], sz, px, self.taker if es_stop else self.maker, o["oid"], o.get("cloid"),
                               f"{'stop' if es_stop else 'objetivo'} alcanzado mientras el bot estaba parado "
                               f"(vela de 1 min {t}, ESTIMADO)")
                self._historial(o["oid"], status="filled", sz="0.0", avgPx=str(px))
                self.d["ordenes"] = [x for x in self.d["ordenes"] if x is not o]
                self.d.setdefault("huecos_recuperados", []).append({"moneda": m, "oid": o["oid"], "tipo": o["tipo"],
                                                                   "vela_ms": t, "px": px, "sz": sz})
                self.d["huecos_recuperados"] = self.d["huecos_recuperados"][-200:]
                cursor, cambio = t, True
        return cambio

    def procesar(self):
        """Comprueba las órdenes pendientes contra el precio real actual, la liquidación estimada y el funding."""
        with self.bloqueo:
            mids = self._mids()
            quedan, cambio = [], self._funding()
            ahora_ms = int(time.time() * 1000)
            previo = self.d.get("ultimo_proceso_ms")
            if previo and ahora_ms - previo > HUECO_MIN_S * 1000:
                cambio = self._recuperar_hueco(previo) or cambio
            if not previo or ahora_ms - previo > 60_000:
                self.d["ultimo_proceso_ms"] = ahora_ms
                cambio = True              # se guarda como mucho una vez por minuto
            # Liquidación estimada (antes que los stops: si la marca cruza la liquidación, el exchange liquida)
            for m, pos in list(self.d["posiciones"].items()):
                marca, liq = self._marca(m), self._liquidacion(m, pos)
                if marca and liq and ((pos["szi"] > 0 and marca <= liq) or (pos["szi"] < 0 and marca >= liq)):
                    self._ejecutar(m, pos["szi"] < 0, abs(pos["szi"]), liq, self.taker, None, None,
                                   "liquidación ESTIMADA (simulado)")
                    self.d.setdefault("liquidaciones", []).append({"moneda": m, "px": liq, "time": int(time.time() * 1000)})
                    cambio = True
            for o in self.d["ordenes"]:
                m = o["coin"]
                px = mids.get(m)
                pos = self.d["posiciones"].get(m)
                if px is None:
                    quedan.append(o)
                    continue
                if o["reduce_only"]:
                    if not pos or (pos["szi"] > 0) == o["compra"]:
                        cambio = True  # ya no hay nada que reducir: la orden desaparece (como en Hyperliquid)
                        self._historial(o["oid"], status="reduceOnlyCanceled")
                        continue
                    sz = min(o["sz"], abs(pos["szi"]))
                else:
                    sz = o["sz"]
                if o["tipo"] == "stop":
                    marca = self._marca(m) or px          # Hyperliquid activa los TP/SL con el precio de MARCA
                    disparada = marca >= o["trigger"] if o["compra"] else marca <= o["trigger"]
                    if disparada:
                        lim = o["trigger"] * (1 + TOLERANCIA_MERCADO) if o["compra"] else o["trigger"] * (1 - TOLERANCIA_MERCADO)
                        hecho, pmedio = self._barrer(m, o["compra"], sz, lim, profundo=True)
                        if hecho > 0:
                            self._ejecutar(m, o["compra"], hecho, pmedio, self.taker, o["oid"], o.get("cloid"),
                                           f"stop activado por la marca {marca}")
                        resto = sz - hecho
                        self._historial(o["oid"], status="filled" if resto <= 1e-12 else "canceled",
                                        sz=str(max(resto, 0.0)), avgPx=str(pmedio) if pmedio else None)
                        cambio = True
                        continue
                else:
                    llena = self._limite_llena(o)
                    if llena:
                        self._ejecutar(m, o["compra"], sz, o["px"], self.maker, o["oid"], o.get("cloid"))
                        self._historial(o["oid"], status="filled", sz="0.0", avgPx=str(o["px"]))
                        cambio = True
                        continue
                quedan.append(o)
            self.d["ordenes"] = quedan
            if cambio:
                self._guardar()

    # --------------------------------------------------- lo que pide el bot (Info)
    def user_state(self):
        self.procesar()
        mids = self._mids()
        posiciones, no_realizado, margen, mantenimiento = [], 0.0, 0.0, 0.0
        for m, p in self.d["posiciones"].items():
            px = mids.get(m, p["entrada"])
            upnl = p["szi"] * (px - p["entrada"])
            apal = self.d["apalancamiento"].get(m, 1)
            no_realizado += upnl
            margen_pos = abs(p["szi"]) * p["entrada"] / apal
            margen += margen_pos
            apal_max = (self._ctx().get(m) or {}).get("apal_max") or apal
            mantenimiento += abs(p["szi"]) * px / (2 * max(apal_max, 1))
            liq = self._liquidacion(m, p)
            posiciones.append({"position": {"coin": m, "szi": str(p["szi"]), "entryPx": str(p["entrada"]),
                                            "positionValue": str(abs(p["szi"]) * px), "unrealizedPnl": str(upnl),
                                            "marginUsed": str(margen_pos),
                                            "liquidationPx": str(liq) if liq else None, "liquidacion_estimada": True,
                                            "leverage": {"type": "isolated", "value": apal}}})
        valor = self.d["efectivo"] + no_realizado
        return {"assetPositions": posiciones, "withdrawable": str(max(0.0, valor - margen)),
                "marginSummary": {"accountValue": str(valor), "totalMarginUsed": str(margen),
                                  "totalNtlPos": str(sum(float(x["position"]["positionValue"]) for x in posiciones))},
                "crossMaintenanceMarginUsed": str(mantenimiento), "time": int(time.time() * 1000), "simulado": True}

    def frontend_open_orders(self):
        return [{"coin": o["coin"], "oid": o["oid"], "cloid": o.get("cloid"), "isTrigger": o["tipo"] == "stop",
                 "triggerPx": str(o.get("trigger", 0)), "limitPx": str(o.get("px", o.get("limite", 0))),
                 "sz": str(o["sz"]), "origSz": str(o["sz"]), "side": "B" if o["compra"] else "A",
                 "reduceOnly": o["reduce_only"], "timestamp": o.get("ts"),
                 "orderType": "Stop Market" if o["tipo"] == "stop" else "Limit"} for o in self.d["ordenes"]]

    def user_fills(self):
        return list(reversed(self.d["fills"]))

    def user_funding_history(self, start_ms, end_ms=None):
        return [f for f in self.d["funding"] if f["time"] >= start_ms and (end_ms is None or f["time"] <= end_ms)]

    def user_fees(self):
        return {"userAddRate": str(self.maker), "userCrossRate": str(self.taker), "simulado": True}

    def query_order(self, oid=None, cloid=None):
        """Mismo formato que orderStatus de Hyperliquid."""
        cloid = _cloid_txt(cloid)
        with self.bloqueo:
            self.procesar()
            for o in self.d["ordenes"]:
                if (oid is not None and o["oid"] == oid) or (cloid and o.get("cloid") == cloid):
                    return {"status": "order", "order": {"status": "open", "statusTimestamp": int(time.time() * 1000),
                                                         "order": {"coin": o["coin"], "oid": o["oid"], "cloid": o.get("cloid"),
                                                                   "sz": str(o["sz"]), "origSz": str(o["sz"]),
                                                                   "side": "B" if o["compra"] else "A",
                                                                   "limitPx": str(o.get("px", o.get("limite", 0))),
                                                                   "isTrigger": o["tipo"] == "stop",
                                                                   "triggerPx": str(o.get("trigger", 0)),
                                                                   "reduceOnly": o["reduce_only"]}}}
            for h in self.d["historial_ordenes"].values():
                if (oid is not None and h["oid"] == oid) or (cloid and h.get("cloid") == cloid):
                    return {"status": "order", "order": {"status": h.get("status", "unknown"),
                                                         "statusTimestamp": h.get("statusTimestamp"),
                                                         "order": {"coin": h.get("coin"), "oid": h["oid"],
                                                                   "cloid": h.get("cloid"), "sz": h.get("sz", "0"),
                                                                   "origSz": h.get("origSz"), "avgPx": h.get("avgPx")}}}
        return {"status": "unknownOid"}

    # ------------------------------------------------ lo que pide el bot (Exchange)
    def update_leverage(self, leverage, name, is_cross=True):
        with self.bloqueo:
            self.d["apalancamiento"][name] = leverage
            self._guardar()
        return {"status": "ok", "response": {"type": "default"}}

    def _duplicado(self, cloid):
        if not cloid:
            return False
        return any(o.get("cloid") == cloid for o in self.d["ordenes"]) or \
            any(h.get("cloid") == cloid for h in self.d["historial_ordenes"].values())

    def order(self, name, is_buy, sz, limit_px, order_type, reduce_only=False, cloid=None, builder=None):
        cloid = _cloid_txt(cloid)
        with self.bloqueo:
            if self._duplicado(cloid):
                # Hyperliquid rechaza un cloid repetido: así una orden reenviada por error no se duplica.
                return self._ok({"error": "Duplicate cloid"})
            px, sz = float(limit_px), float(sz)
            if "trigger" in order_type:
                trig = float(order_type["trigger"]["triggerPx"])
                oid = self._nuevo_oid()
                self.d["ordenes"].append({"oid": oid, "coin": name, "compra": is_buy, "sz": sz, "tipo": "stop",
                                          "trigger": trig, "limite": px, "reduce_only": reduce_only, "cloid": cloid,
                                          "ts": int(time.time() * 1000)})
                self._historial(oid, coin=name, cloid=cloid, origSz=str(sz), sz=str(sz), status="open")
                self._guardar()
                return self._ok({"resting": {"oid": oid, "cloid": cloid}})
            if px * sz < 10 and not reduce_only:
                return self._ok({"error": "Order must have minimum value of $10."})
            bid, ask = self._mejores(name)
            cruza = px >= ask if is_buy else px <= bid
            tif = order_type["limit"]["tif"]
            oid = self._nuevo_oid()
            if tif == "Alo" and cruza:
                self._historial(oid, coin=name, cloid=cloid, origSz=str(sz), sz=str(sz), status="rejected")
                self._guardar()
                return self._ok({"error": "Post only order would have immediately matched"})
            if cruza:
                if reduce_only:
                    pos = self.d["posiciones"].get(name)
                    if not pos or (pos["szi"] > 0) == is_buy:
                        self._historial(oid, coin=name, cloid=cloid, origSz=str(sz), sz=str(sz), status="rejected")
                        self._guardar()
                        return self._ok({"error": "Reduce only order would increase position."})
                    sz = min(sz, abs(pos["szi"]))
                # Recorre los niveles reales del libro hasta el límite: impacto por tamaño y posible fill parcial.
                hecho, precio = self._barrer(name, is_buy, sz, px, profundo=True)
                if hecho <= 0:
                    self._historial(oid, coin=name, cloid=cloid, origSz=str(sz), sz=str(sz), status="canceled")
                    self._guardar()
                    return self._ok({"error": "Order could not immediately match against any resting orders."})
                self._ejecutar(name, is_buy, hecho, precio, self.taker, oid, cloid)
                resto = sz - hecho
                if resto > 1e-12 and tif == "Gtc":
                    self.d["ordenes"].append({"oid": oid, "coin": name, "compra": is_buy, "sz": resto, "tipo": "limite",
                                              "px": px, "reduce_only": reduce_only, "cloid": cloid,
                                              "ts": int(time.time() * 1000)})
                    self._historial(oid, coin=name, cloid=cloid, origSz=str(sz), sz=str(resto), avgPx=str(precio),
                                    status="open")
                    self._guardar()
                    return self._ok({"resting": {"oid": oid, "cloid": cloid}})
                self._historial(oid, coin=name, cloid=cloid, origSz=str(sz), sz=str(max(resto, 0.0)), avgPx=str(precio),
                                status="filled" if resto <= 1e-12 else "canceled")
                self._guardar()
                return self._ok({"filled": {"totalSz": str(hecho), "avgPx": str(precio), "oid": oid, "cloid": cloid}})
            if tif == "Ioc":
                self._historial(oid, coin=name, cloid=cloid, origSz=str(sz), sz=str(sz), status="canceled")
                self._guardar()
                return self._ok({"error": "Order could not immediately match against any resting orders."})
            self.d["ordenes"].append({"oid": oid, "coin": name, "compra": is_buy, "sz": sz, "tipo": "limite",
                                      "px": px, "reduce_only": reduce_only, "cloid": cloid, "ts": int(time.time() * 1000)})
            self._historial(oid, coin=name, cloid=cloid, origSz=str(sz), sz=str(sz), status="open")
            self._guardar()
            return self._ok({"resting": {"oid": oid, "cloid": cloid}})

    def market_open(self, name, is_buy, sz, px=None, slippage=0.05, cloid=None, builder=None):
        bid, ask = self._mejores(name)
        lim = (ask * (1 + slippage)) if is_buy else (bid * (1 - slippage))
        return self.order(name, is_buy, sz, lim, {"limit": {"tif": "Ioc"}}, False, cloid)

    def _cancelar(self, filtro):
        with self.bloqueo:
            antes = len(self.d["ordenes"])
            quedan = []
            for o in self.d["ordenes"]:
                if filtro(o):
                    self._historial(o["oid"], status="canceled")
                else:
                    quedan.append(o)
            self.d["ordenes"] = quedan
            self._guardar()
            if len(quedan) == antes:
                return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": [
                    {"error": "Order was never placed, already canceled, or filled."}]}}}
            return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}

    def cancel(self, name, oid):
        return self._cancelar(lambda o: o["oid"] == oid)

    def cancel_by_cloid(self, name, cloid):
        cloid = _cloid_txt(cloid)
        return self._cancelar(lambda o: o.get("cloid") == cloid)


class InfoConPapel:
    """Usa la API real de Hyperliquid para todo, salvo para TU cuenta, que es la ficticia."""

    def __init__(self, info_real, cuenta, direccion):
        self._info, self._cuenta, self._dir = info_real, cuenta, direccion

    def __getattr__(self, nombre):
        return getattr(self._info, nombre)

    def user_state(self, address, *a, **k):
        return self._cuenta.user_state() if address == self._dir else self._info.user_state(address, *a, **k)

    def frontend_open_orders(self, address, *a, **k):
        return self._cuenta.frontend_open_orders() if address == self._dir else self._info.frontend_open_orders(address)

    def open_orders(self, address, *a, **k):
        # Nadie lo llama hoy, pero se conserva a propósito: sin él, __getattr__ mandaría la consulta de la cuenta
        # simulada a la API real.
        return self.frontend_open_orders(address)

    def user_fills(self, address):
        return self._cuenta.user_fills() if address == self._dir else self._info.user_fills(address)

    def user_funding_history(self, user, startTime, endTime=None):
        if user == self._dir:
            return self._cuenta.user_funding_history(startTime, endTime)
        return self._info.user_funding_history(user, startTime, endTime)

    def user_fees(self, address):
        return self._cuenta.user_fees() if address == self._dir else self._info.user_fees(address)

    def query_order_by_oid(self, user, oid):
        return self._cuenta.query_order(oid=oid) if user == self._dir else self._info.query_order_by_oid(user, oid)

    def query_order_by_cloid(self, user, cloid):
        return self._cuenta.query_order(cloid=cloid) if user == self._dir else self._info.query_order_by_cloid(user, cloid)

    def user_role(self, user):
        return {"role": "simulado"} if user == self._dir else self._info.user_role(user)
