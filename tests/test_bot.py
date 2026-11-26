"""Arranque seguro, barrera shadow, aislamiento de las ballenas, datos obsoletos y apagado.
Usa módulos FALSOS de hyperliquid/eth_account: ninguna prueba puede llegar a la red ni firmar nada."""

import json
import os
import sys
import time
import types
import unittest
from unittest import mock

from tests.comunes import ConCarpeta, MercadoFalso, config

SUB = "0x" + "ab" * 20
MAESTRA = "0x" + "cd" * 20
AGENTE = "0x" + "ef" * 20


class ExchangeProhibido:
    creados = 0

    def __init__(self, *a, **k):
        ExchangeProhibido.creados += 1
        raise AssertionError("se intentó crear un cliente de órdenes")


def modulos_falsos(info_cls):
    hl = types.ModuleType("hyperliquid")
    info = types.ModuleType("hyperliquid.info")
    info.Info = info_cls
    ex = types.ModuleType("hyperliquid.exchange")
    ex.Exchange = ExchangeProhibido
    utils = types.ModuleType("hyperliquid.utils")
    const = types.ModuleType("hyperliquid.utils.constants")
    const.MAINNET_API_URL, const.TESTNET_API_URL = "https://falso.invalid", "https://falso-test.invalid"
    utils.constants = const
    eth = types.ModuleType("eth_account")
    eth.Account = types.SimpleNamespace(from_key=lambda k: types.SimpleNamespace(address=AGENTE))
    return {"hyperliquid": hl, "hyperliquid.info": info, "hyperliquid.exchange": ex, "hyperliquid.utils": utils,
            "hyperliquid.utils.constants": const, "eth_account": eth}


class InfoFalsa(MercadoFalso):
    roles = {}
    posiciones = []

    def __init__(self, *a, **k):
        super().__init__()

    def post(self, ruta, cuerpo=None):
        return {}

    def user_role(self, direccion):
        r = self.roles.get(direccion.lower())
        if isinstance(r, Exception):
            raise r
        return r

    def user_state(self, direccion):
        return {"assetPositions": self.posiciones, "marginSummary": {"accountValue": "50"}, "withdrawable": "50"}

    def frontend_open_orders(self, direccion):
        return []


def preparar_rutas(bot, carpeta):
    for nombre in ("RUTA_ESTADO", "RUTA_MEMORIA", "RUTA_PANEL", "RUTA_COMANDOS_PANEL", "RUTA_RESULTADOS_COMANDOS",
                   "RUTA_PAPEL", "RUTA_BALLENAS", "RUTA_ELEGIDA", "RUTA_CONFIG"):
        setattr(bot, nombre, os.path.join(carpeta, os.path.basename(getattr(bot, nombre))))
    bot.DIR_MERCADO = os.path.join(carpeta, "datos_mercado")
    bot.DIR_REGISTRO = os.path.join(carpeta, "registro")
    bot.DIR_ARCHIVO = os.path.join(carpeta, "datos_archivo")
    bot.DIR_REINICIOS = os.path.join(carpeta, "archivo_reinicios")
    bot.AQUI = carpeta          # el archivo de estados de otro modo (estado-<modo>-*.json) iba a la carpeta del bot


class CerebroFalso:
    decide = True
    error = None

    def __init__(self, abre):
        self.abre = abre
        self.identidades = {"1h": "a" * 20, "4h": "b" * 20}

    def recargar(self):
        pass

    def decidir(self, cand, motor, ctx_externo=None, ahora=None):
        return {"abrir": self.abre, "prediccion": 0.3 if self.abre else -0.1, "version": "prueba", "rasgos": {},
                "motivo": "cerebro: prueba (" + ("entra" if self.abre else "no entra") + ")"}

    def resumen(self):
        return {"decide": True}


class VerificarSubcuenta(unittest.TestCase):
    def setUp(self):
        import bot
        self.bot = bot
        self.c = config()
        self.c["real"] = {"habilitado": True, "subcuenta": SUB}

    def info(self, roles):
        i = InfoFalsa()
        i.roles = roles
        return i

    def test_correcto(self):
        i = self.info({SUB: {"role": "subAccount", "data": {"master": MAESTRA}}, AGENTE: {"role": "agent", "data": {"user": MAESTRA}}})
        self.assertEqual(self.bot.verificar_subcuenta(i, self.c, SUB, AGENTE), MAESTRA)

    def test_cuenta_principal_bloquea(self):
        i = self.info({SUB: {"role": "user"}, AGENTE: {"role": "agent", "data": {"user": MAESTRA}}})
        with self.assertRaises(self.bot.ErrorArranque):
            self.bot.verificar_subcuenta(i, self.c, SUB, AGENTE)

    def test_clave_principal_en_vez_de_api_wallet_bloquea(self):
        i = self.info({SUB: {"role": "subAccount", "data": {"master": MAESTRA}}, AGENTE: {"role": "user"}})
        with self.assertRaises(self.bot.ErrorArranque):
            self.bot.verificar_subcuenta(i, self.c, SUB, AGENTE)

    def test_agente_de_otra_cuenta_bloquea(self):
        i = self.info({SUB: {"role": "subAccount", "data": {"master": MAESTRA}}, AGENTE: {"role": "agent", "data": {"user": "0x" + "11" * 20}}})
        with self.assertRaises(self.bot.ErrorArranque):
            self.bot.verificar_subcuenta(i, self.c, SUB, AGENTE)

    def test_respuesta_rara_o_error_falla_cerrado(self):
        for rol in (None, "subAccount", {"role": "subAccount"}, ConnectionError("x")):
            i = self.info({SUB: rol, AGENTE: {"role": "agent", "data": {"user": MAESTRA}}})
            with self.assertRaises(self.bot.ErrorArranque):
                self.bot.verificar_subcuenta(i, self.c, SUB, AGENTE)


class CrearCliente(ConCarpeta):
    def setUp(self):
        super().setUp()
        ExchangeProhibido.creados = 0
        self.mods = mock.patch.dict(sys.modules, modulos_falsos(InfoFalsa))
        self.mods.start()
        import bot
        self.bot = bot
        self.rutas = {k: getattr(bot, k) for k in dir(bot) if k.startswith(("RUTA_", "DIR_")) or k == "AQUI"}
        preparar_rutas(bot, self.dir)

    def tearDown(self):
        for k, v in self.rutas.items():
            setattr(self.bot, k, v)
        self.mods.stop()
        super().tearDown()

    def test_shadow_no_crea_cliente_de_ordenes(self):
        c = config()
        c["modo"] = "shadow"
        info, ej, cuenta, url = self.bot.crear_cliente(c, {}, {})
        self.assertFalse(ej.puede_operar)
        self.assertIsNone(cuenta)
        self.assertEqual(ExchangeProhibido.creados, 0)

    def test_real_que_falla_comprobaciones_no_crea_cliente(self):
        c = config()
        c["modo"], c["real"] = "real", {"habilitado": True, "subcuenta": SUB}
        InfoFalsa.roles = {SUB: {"role": "user"}}
        with self.assertRaises(self.bot.ErrorArranque):
            self.bot.crear_cliente(c, {"HL_DIRECCION_CUENTA": SUB, "HL_API_WALLET_KEY": "0x" + "00" * 31 + "01"}, {})
        self.assertEqual(ExchangeProhibido.creados, 0)

    def test_real_con_posiciones_no_atribuibles_no_crea_cliente(self):
        c = config()
        c["modo"], c["real"] = "real", {"habilitado": True, "subcuenta": SUB}
        InfoFalsa.roles = {SUB: {"role": "subAccount", "data": {"master": MAESTRA}},
                           AGENTE: {"role": "agent", "data": {"user": MAESTRA}}}
        InfoFalsa.posiciones = [{"position": {"coin": "BTC", "szi": "0.01", "entryPx": "100000", "positionValue": "1000"}}]
        try:
            with self.assertRaises(self.bot.ErrorArranque):
                self.bot.crear_cliente(c, {"HL_DIRECCION_CUENTA": SUB, "HL_API_WALLET_KEY": "k"}, {})
        finally:
            InfoFalsa.posiciones = []
        self.assertEqual(ExchangeProhibido.creados, 0)


class BotShadowYSimulado(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.mods = mock.patch.dict(sys.modules, modulos_falsos(InfoFalsa))
        self.mods.start()
        import bot
        from ejecucion import Ejecutor, EjecutorShadow
        from ledger import Ledger
        from notificaciones import Telegram
        from observabilidad import Sistema
        from promocion import Registro
        self.bot = bot
        self.rutas = {k: getattr(bot, k) for k in dir(bot) if k.startswith(("RUTA_", "DIR_")) or k == "AQUI"}
        preparar_rutas(bot, self.dir)
        self.Ejecutor, self.EjecutorShadow, self.Ledger = Ejecutor, EjecutorShadow, Ledger
        self.Telegram, self.Sistema, self.Registro = Telegram, Sistema, Registro

    def tearDown(self):
        for k, v in self.rutas.items():
            setattr(self.bot, k, v)
        self.mods.stop()
        super().tearDown()

    def nuevo(self, modo):
        c = config(tiempo_real__websocket=False)
        c["modo"] = modo
        info = InfoFalsa()
        ledger = self.Ledger(os.path.join(self.dir, "registro"))
        if modo == "shadow":
            ej, cuenta = self.EjecutorShadow(), None
        else:
            from tests.comunes import nuevo_papel
            papel, info = nuevo_papel(self.dir, info)
            ej, cuenta = self.Ejecutor(papel, info, "simulado", ledger, "simulado", self.bot.log_op, c["ordenes"],
                                       esperar=lambda s: None), "simulado"
        b = self.bot.Bot(c, info, ej, cuenta, None, self.Telegram(None, None), ledger, self.Sistema(self.dir),
                         self.Registro(os.path.join(self.dir, "promociones.json")))
        b.cerebro = CerebroFalso(abre=True)          # el cerebro real se prueba en test_cerebro_vivo.py
        return b, ledger

    def test_si_el_cerebro_dice_no_no_entra(self):
        b, ledger = self.nuevo("simulado")
        b.cerebro = CerebroFalso(abre=False)
        b.leer_precios()
        b.procesar_candidatas([self.candidata()])
        tipos = [e["tipo"] for e in ledger.leer()[0]]
        self.assertNotIn("orden_enviada", tipos)
        dec = [e for e in ledger.leer()[0] if e["tipo"] == "decision"]
        self.assertFalse(dec[-1]["aprobada"])
        self.assertIn("cerebro", dec[-1]["motivos"][0])

    def test_modo_defensa_ignora_lo_anterior_a_la_puesta_a_cero(self):
        b, _ = self.nuevo("simulado")
        malos = [{"tipo": "real", "resultado_r": -1.0, "cierre_ts": 1000.0 + i} for i in range(8)]
        b.memoria.cerrados = lambda con_lab=False: malos
        self.assertTrue(any("defensa" in m for m in b.factor_capital(230)[1]))
        os.makedirs(os.path.join(self.bot.DIR_REINICIOS, "20261028T224456Z"))
        del b._inicio_simulada
        self.assertFalse(any("defensa" in m for m in b.factor_capital(230)[1]))

    def test_exploracion_amplia_opera_con_riesgo_reducido_lo_que_el_cerebro_rechaza(self):
        b, ledger = self.nuevo("simulado")
        b.c["exploracion_amplia"] = {"activa": True, "riesgo_por_operacion_pct": 0.25, "max_abiertas": 2}
        b.cerebro = CerebroFalso(abre=False)
        b.leer_precios()
        b.conciliacion_ok = b.conciliacion_inicial()
        b.c["ordenes"]["entrada_limite"] = False
        b.procesar_candidatas([self.candidata()])
        op = b.estado["posiciones"].get("ETH")
        self.assertIsNotNone(op, b.bloqueos)
        self.assertTrue(op["exploracion_amplia"])
        saldo = b.ej.ex.d["saldo_inicial"]
        self.assertLessEqual(op.get("riesgo_plan_usd") or 0, saldo * 0.0025 * 1.01)   # 0,25 % como mucho
        # cupo propio: con el máximo de exploración abierto, no abre más
        b.c["exploracion_amplia"]["max_abiertas"] = 1
        self.assertFalse(b._puede_explorar(self.candidata("BTC"), "BTC"))

    def _con_memoria(self, abrir, factor):
        b, ledger = self.nuevo("simulado")
        llamadas = []

        def valorar(moneda, rasgos, modulo=None, medir=False, relajado=False):
            llamadas.append(medir)
            return {"abrir": abrir, "factor": factor, "texto": "la memoria opina", "r_esperado": 0.3 if abrir else -0.5,
                    "n": 40, "juzgada": True}
        b.memoria.valorar = valorar
        b.leer_precios()
        b.conciliacion_ok = b.conciliacion_inicial()
        b.c["ordenes"]["entrada_limite"] = False
        b.procesar_candidatas([self.candidata()])
        self.assertEqual(llamadas, [True, False])                # medición + valoración que aplica
        return [e for e in ledger.leer()[0] if e["tipo"] == "decision"][-1]

    def test_ampliar_ganadoras_solo_en_simulado_y_activada(self):
        b, _ = self.nuevo("simulado")
        b.leer_precios()
        b.conciliacion_ok = b.conciliacion_inicial()
        b.c["ordenes"]["entrada_limite"] = False
        b.procesar_candidatas([self.candidata()])
        op = b.estado["posiciones"]["ETH"]
        op.update(en_breakeven=True, sl=op["entrada"])                # stop ya en la entrada
        llamadas = []
        b.gestor.ampliar = lambda op, tam, motivo: llamadas.append(tam) or 0.0
        b.c["piramide"] = {"activa": False, "fraccion": 0.5, "riesgo_max_frac_original": 1.0}
        b._ampliar_ganadoras()
        self.assertEqual(llamadas, [])
        b.c["piramide"]["activa"] = True
        b.modo = "real"
        b._ampliar_ganadoras()
        self.assertEqual(llamadas, [])                                # en real no existe
        b.modo = "simulado"
        b._ampliar_ganadoras()
        self.assertEqual(len(llamadas), 1)
        self.assertLessEqual(llamadas[0], op["tam_inicial"] * 0.5 + 1e-12)

    def _bot_con_op_en_breakeven(self):
        b, _ = self.nuevo("simulado")
        b.leer_precios()
        b.conciliacion_ok = b.conciliacion_inicial()
        b.c["ordenes"]["entrada_limite"] = False
        b.procesar_candidatas([self.candidata()])
        op = b.estado["posiciones"]["ETH"]
        op.update(en_breakeven=True, sl=op["entrada"])
        llamadas = []
        b.gestor.ampliar = lambda op, tam, motivo: llamadas.append(tam) or 0.0
        b.c["piramide"] = {"activa": True, "fraccion": 0.5, "riesgo_max_frac_original": 1.0}
        return b, op, llamadas

    def test_curva_de_valor_diaria(self):
        # CP-M17 (auditoría 26/11, T-13): un punto por día UTC en registro/curva_valor.jsonl, sin recortar.
        import curva_valor
        b, _ = self.nuevo("simulado")
        b.leer_precios()
        b.conciliacion_ok = b.conciliacion_inicial()                    # sin cuenta leída no hay valor que guardar
        b.escribir_panel()
        b.escribir_panel()                                              # mismo día: no se repite
        ruta = os.path.join(self.bot.DIR_REGISTRO, curva_valor.ARCHIVO)
        puntos = curva_valor.leer(ruta)
        self.assertEqual(len(puntos), 1)
        self.assertEqual(puntos[0]["fuente"], "equity")
        self.assertEqual(puntos[0]["dia"], curva_valor.dia_utc(time.time()))
        self.assertGreater(puntos[0]["equity"], 0)

    def test_ampliar_tras_cobrar_el_tp1_espera_1r_mas(self):
        # CP-E06 (auditoría 26/11): con el TP1 cobrado no se recompra hasta que el precio pase el TP1 en 1 R.
        b, op, llamadas = self._bot_con_op_en_breakeven()
        b.c["piramide"]["avance_tras_tp1_r"] = 1.0
        px, r = b.mids["ETH"], op["r_dist"]
        s = 1 if op["lado"] == "L" else -1
        op.update(parcial=True, tp1_hecho=True, tp1=px - s * 0.5 * r)       # solo 0,5 R más allá del TP1
        b._ampliar_ganadoras()
        self.assertEqual(llamadas, [])
        op["tp1"] = px - s * 1.2 * r                                        # ya 1,2 R más allá
        b._ampliar_ganadoras()
        self.assertEqual(len(llamadas), 1)

    def test_ampliar_respeta_los_bloqueos_de_entrada(self):
        # Auditoría 19/11 (R-01): antes ampliaba con pausa manual, límites de pérdida o datos viejos.
        b, _, llamadas = self._bot_con_op_en_breakeven()
        b.estado["pausa_manual"] = True
        b._ampliar_ganadoras()
        self.assertEqual(llamadas, [])
        self.assertIn("pausa manual", b.ampliacion_bloqueada)
        b.estado["pausa_manual"] = False
        b._ampliar_ganadoras()
        self.assertEqual(len(llamadas), 1)

    def test_ampliar_respeta_la_exposicion_y_el_desplome(self):
        b, op, llamadas = self._bot_con_op_en_breakeven()
        b.c["riesgo"]["exposicion_max_mercado_pct"] = 0.001             # la moneda ya está «llena»
        b._ampliar_ganadoras()
        self.assertEqual(llamadas, [])
        self.assertIn("exposición", op["ampliacion_esperando"])
        b.c["riesgo"]["exposicion_max_mercado_pct"] = 100
        b.c["riesgo"]["riesgo_salto_max_pct"] = 0.0001                  # cualquier salto supera el tope
        b._ampliar_ganadoras()
        self.assertEqual(llamadas, [])
        self.assertIn("desplome", op["ampliacion_esperando"])

    def test_entrada_bloqueada_por_desplome_conjunto(self):
        b, ledger = self.nuevo("simulado")
        b.leer_precios()
        b.conciliacion_ok = b.conciliacion_inicial()
        b.c["ordenes"]["entrada_limite"] = False
        b.c["riesgo"]["riesgo_salto_max_pct"] = 0.0001
        b.procesar_candidatas([self.candidata()])
        self.assertNotIn("ETH", b.estado["posiciones"])
        dec = [e for e in ledger.leer()[0] if e["tipo"] == "decision"][-1]
        self.assertTrue(any("desplome" in m for m in dec["motivos"]), dec["motivos"])

    def test_con_el_cerebro_aceptando_la_memoria_en_contra_reduce_el_tamano(self):
        # 19/11/2026 (Roberto): la memoria vuelve a juzgar lo que acepta el cerebro. En simulado, si los casos
        # parecidos salieron mal, entra con tamaño reducido (factor_exploracion); en real se vetaría.
        dec = self._con_memoria(False, 0.0)
        self.assertTrue(dec["aprobada"], dec["motivos"])
        self.assertLessEqual(dec["plan"]["factor"], 0.5 + 1e-9)

    def test_con_el_cerebro_aceptando_la_memoria_a_favor_no_reduce(self):
        dec = self._con_memoria(True, 1.0)
        self.assertTrue(dec["aprobada"], dec["motivos"])
        self.assertGreater(dec["plan"]["factor"], 0.5)

    def test_sin_cerebro_decidiendo_la_memoria_sigue_valorando(self):
        b, _ = self.nuevo("simulado")
        b.cerebro.decide = False
        llamadas = []

        def valorar(moneda, rasgos, modulo=None, medir=False, relajado=False):
            llamadas.append(medir)
            return {"abrir": True, "factor": 1.0, "texto": "ok", "r_esperado": 0.1, "n": 40, "juzgada": True}
        b.memoria.valorar = valorar
        b.leer_precios()
        b.procesar_candidatas([self.candidata()])
        self.assertEqual(llamadas, [True, False])

    def test_el_ledger_guarda_si_fue_exploracion_amplia_y_si_el_cerebro_se_abstuvo(self):
        b, ledger = self.nuevo("simulado")
        b.c["exploracion_amplia"] = {"activa": True, "riesgo_por_operacion_pct": 0.25, "max_abiertas": 2}
        b.cerebro = CerebroFalso(abre=False)
        b.leer_precios()
        b.conciliacion_ok = b.conciliacion_inicial()
        b.c["ordenes"]["entrada_limite"] = False
        b.procesar_candidatas([self.candidata()])
        dec = [e for e in ledger.leer()[0] if e["tipo"] == "decision"][-1]
        self.assertTrue(dec["aprobada"], dec["motivos"])
        self.assertTrue(dec["plan"]["exploracion_amplia"])
        self.assertIn("abstencion", dec["cerebro"])

    def test_un_ciclo_colgado_hace_salir_para_reiniciar(self):
        b, _ = self.nuevo("simulado")
        b.ultimo_ciclo_ts = 1000.0
        with mock.patch.object(self.bot, "_salir") as salir:
            self.assertFalse(b.comprobar_cuelgue(1000.0 + self.bot.CICLO_COLGADO_SEG))
            self.assertTrue(b.comprobar_cuelgue(1001.0 + self.bot.CICLO_COLGADO_SEG))
            salir.assert_called_once_with(1)
            b.parar.set()                               # en un apagado ordenado, nunca
            self.assertFalse(b.comprobar_cuelgue(99999.0))

    def test_panel_muerto_se_relanza_como_mucho_cada_10_min(self):
        b, _ = self.nuevo("simulado")
        with mock.patch("subprocess.Popen") as popen, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INVOCATION_ID", None)
            self.assertTrue(b.relanzar_panel(1000.0))
            self.assertFalse(b.relanzar_panel(1300.0))
            self.assertTrue(b.relanzar_panel(1700.0))
            self.assertEqual(popen.call_count, 2)
            self.assertTrue(popen.call_args[0][0][-1].endswith("panel.py"))
        with mock.patch("subprocess.Popen") as popen, mock.patch.dict(os.environ, {"INVOCATION_ID": "x"}):
            self.assertFalse(b.relanzar_panel(9000.0))  # en el servidor lo hace systemd
            popen.assert_not_called()

    def test_senales_tras_descarga_lenta_se_deciden_con_datos_de_ahora(self):
        b, _ = self.nuevo("simulado")
        b.leer_precios()
        b.conciliacion_ok = b.conciliacion_inicial()
        vistos = {}

        def senales(*a, **k):                      # la descarga tarda: lo leído al principio del ciclo ya es viejo
            b.mids_ts = 1.0
            b.gestor.ultima_cuenta = dict(b.gestor.ultima_cuenta, ts=1.0)
            return [self.candidata()]
        b.motor.nuevas_senales = senales
        b.procesar_candidatas = lambda c: vistos.update(bloqueos=b.bloqueos_entrada(b.equity()[0]))
        b.ciclo()
        self.assertNotIn("datos de precios obsoletos o no disponibles", vistos["bloqueos"])
        self.assertFalse([x for x in vistos["bloqueos"] if "lectura de la cuenta" in x])
        # Sin señales, el aviso del panel también se actualiza
        b.motor.nuevas_senales = lambda *a, **k: []
        b.bloqueos = ["aviso viejo"]
        b.ciclo()
        self.assertNotIn("aviso viejo", b.bloqueos)

    def test_exploracion_opera_todo_salvo_umbral_explicito(self):
        b, _ = self.nuevo("simulado")
        b.c["exploracion_amplia"] = {"activa": True, "riesgo_por_operacion_pct": 0.25, "max_abiertas": 2}
        for t in (-3.2, -2.0, -1.0, None):                          # por defecto: también lo negativo (igual que el cerebro)
            b.motor.definicion = lambda clave, t=t: {"validacion": {"t": t}}
            self.assertTrue(b._puede_explorar(self.candidata("BTC"), "BTC"), t)
        b.c["exploracion_amplia"]["t_min_laboratorio"] = -2.0       # con umbral explícito, se filtra
        for t, puede in ((-2.4, False), (-2.0, False), (-1.0, True), (None, True)):
            b.motor.definicion = lambda clave, t=t: {"validacion": {"t": t}}
            self.assertEqual(b._puede_explorar(self.candidata("BTC"), "BTC"), puede, t)

    def test_dos_estrategias_misma_moneda_mismo_ciclo_solo_una_entra(self):
        for modo in ("simulado", "shadow"):
            b, ledger = self.nuevo(modo)
            b.leer_precios()
            if modo == "simulado":
                b.conciliacion_ok = b.conciliacion_inicial()
                b.c["ordenes"]["entrada_limite"] = False
            otra = dict(self.candidata(), estrategia="ruptura_4h", intervalo="4h")
            b.procesar_candidatas([self.candidata(), otra])
            dec = [e for e in ledger.leer()[0] if e["tipo"] == "decision"][-2:]   # las de este ciclo
            self.assertEqual(sum(1 for d in dec if d["aprobada"]), 1, modo)
            self.assertTrue(any("ya hay una posición" in m for d in dec for m in d.get("motivos") or []), modo)

    @staticmethod
    def candidata(moneda="ETH", px=4000.0):
        return {"moneda": moneda, "lado": "L", "estrategia": "ruptura_1h", "modulo": "ruptura", "version": "1",
                "motivo": "prueba", "precio_senal": px, "sl_pct": 2.0, "duracion_min": 1800, "fuerza": 1.0,
                "salida": dict(config()["salida"]), "rasgos": {"fuerza": 1.0}, "parametros": {}, "vela_ts": 0,
                "intervalo": "1h"}

    def test_shadow_registra_intencion_sin_ninguna_orden(self):
        b, ledger = self.nuevo("shadow")
        b.leer_precios()
        b.procesar_candidatas([self.candidata()])
        tipos = [e["tipo"] for e in ledger.leer()[0]]
        self.assertIn("shadow_intencion", tipos, b.bloqueos)
        self.assertNotIn("orden_enviada", tipos)
        self.assertEqual(b.ej.intentos, [])
        ev = next(e for e in ledger.leer()[0] if e["tipo"] == "shadow_intencion")
        self.assertTrue(ev["modelado"]["estimado"])          # lo modelado está separado de lo observado
        self.assertIn("mid", ev["observado"])

    def test_shadow_rechaza_cerrar(self):
        b, _ = self.nuevo("shadow")
        ok, msg = b.ejecutar_comando({"cmd": "/cerrarbot", "args": ["CONFIRMAR"]})
        self.assertFalse(ok)
        self.assertIn("SHADOW", msg)

    def test_investigacion_no_opera(self):
        b, ledger = self.nuevo("shadow")
        b.leer_precios()
        cand = dict(self.candidata(), estrategia="ballenas_1h", modulo="ballenas", solo_investigacion=True)
        b.procesar_candidatas([cand])
        dec = [e for e in ledger.leer()[0] if e["tipo"] == "decision"]
        self.assertFalse(dec[-1]["aprobada"])
        self.assertIn("solo investigación", dec[-1]["motivos"][0])

    def test_aspirante_solo_se_observa(self):
        for modo in ("simulado", "shadow"):
            b, ledger = self.nuevo(modo)
            b.leer_precios()
            cand = dict(self.candidata(), estrategia="inv:abc", modulo="aspirante", aspirante="abc", solo_investigacion=True)
            b.procesar_candidatas([cand])
            tipos = [e["tipo"] for e in ledger.leer()[0]]
            self.assertIn("shadow_intencion", tipos, modo)
            self.assertNotIn("orden_enviada", tipos)
            self.assertNotIn("decision", tipos)                 # ni siquiera pasa por el gestor de riesgo
            self.assertEqual(b.estado.get("posiciones", {}), {})
            self.assertEqual(len(b.estado.get("shadow_abiertas", {})), 0)   # no ocupa huecos de shadow
            self.assertEqual(b.ej.intentos if modo == "shadow" else [], [])
            self.assertEqual(b.metricas["senales"], 0)          # no cuenta como señal del bot

    def test_vigilancia_solo_reduce_y_retira_real(self):
        b, _ = self.nuevo("simulado")
        clave = "ruptura_1h"
        d = b.motor.definicion(clave)
        h = b._huella(d)
        from tests.comunes import evidencia_para_apta
        evidencia_para_apta(b.promociones, clave, h)
        for etapa in ("apta_revision", "real_habilitado"):
            b.promociones.aprobar(clave, etapa, "test", h)
        self.assertTrue(b.promociones.autorizada_real(clave, h))
        ahora = time.time()
        b.memoria.datos["registros"] += [{"tipo": "real", "modulo": clave, "resultado_r": -0.6 + (0.2 if i % 2 else -0.2),
                                          "cierre_ts": ahora} for i in range(35)]
        b.vigilar_estrategias(cada_seg=0)
        self.assertEqual(b.vigilancia[clave]["estado"], "degradada")
        self.assertEqual(b.estado["factor_estrategia"][clave], 0.5)
        self.assertFalse(b.promociones.autorizada_real(clave, h))
        # se recupera: NO vuelve de golpe al tamaño normal y la autorización tampoco vuelve
        b.memoria.datos["registros"] = [{"tipo": "real", "modulo": clave, "resultado_r": 0.5 + (0.2 if i % 2 else -0.2),
                                         "cierre_ts": ahora} for i in range(35)]
        b.vigilar_estrategias(cada_seg=0)
        self.assertEqual(b.estado["factor_estrategia"][clave], 0.5)
        self.assertEqual(b.estado["vigilancia_fases"][clave]["fase"], "recuperacion")
        self.assertFalse(b.promociones.autorizada_real(clave, h))
        # tras 7 días sanos -> ×0,75; tras otros 7 -> normal (nunca > 1)
        b.estado["vigilancia_fases"][clave]["desde"] -= 8 * 86400
        b.vigilar_estrategias(cada_seg=0)
        self.assertEqual(b.estado["factor_estrategia"][clave], 0.75)
        b.estado["vigilancia_fases"][clave]["desde"] -= 8 * 86400
        b.vigilar_estrategias(cada_seg=0)
        self.assertNotIn(clave, b.estado["factor_estrategia"])
        self.assertTrue(all(f <= 1 for f in b.estado["factor_estrategia"].values()))

    def test_aplicar_config_valida_reinicia_y_no_cambia_modo(self):
        import configuracion as conf
        b, _ = self.nuevo("simulado")
        ruta = self.bot.RUTA_CONFIG
        nueva = dict(b.c, universo=dict(b.c["universo"], max_monedas=7))
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(dict(nueva, modo="shadow"), fh)
        ok, msg = b.ejecutar_comando({"cmd": "/aplicarconfig"})
        self.assertFalse(ok)                       # cambia el modo: no se aplica desde el panel
        self.assertFalse(getattr(b, "reinicio_pedido", False))
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("{roto")
        ok, _ = b.ejecutar_comando({"cmd": "/aplicarconfig"})
        self.assertFalse(ok)
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(nueva, fh)
        ok, msg = b.ejecutar_comando({"cmd": "/aplicarconfig"})
        self.assertTrue(ok, msg)
        self.assertTrue(b.reinicio_pedido and b.parar.is_set())
        self.assertEqual(conf.VERSION_CONFIG, nueva["version_config"])

    def test_websocket_con_trades_no_se_da_por_muerto(self):
        b, _ = self.nuevo("shadow")
        b.c["tiempo_real"]["websocket"] = True
        b.url = "http://falso"
        b.ws_info = object()
        b.ws_subs = {"0xb": 1}
        b.mercado.subs = {"ETH": 2}
        b.ws_ultimo_msg = time.time() - 1000            # las ballenas llevan rato sin operar...
        b.mercado.al_recibir_trades({"data": [{"px": "100", "sz": "1", "side": "B", "coin": "ETH"}]})   # ...pero hay trades
        antes = b.sistema.contadores["reconexiones_ws"]
        b.vigilar_ws()
        self.assertEqual(b.sistema.contadores["reconexiones_ws"], antes)
        b.mercado.ultimo_mensaje = time.time() - 1000    # silencio real en todo
        b.vigilar_ws()
        self.assertEqual(b.sistema.contadores["reconexiones_ws"], antes + 1)

    def test_datos_obsoletos_bloquean_entradas(self):
        b, _ = self.nuevo("shadow")
        b.leer_precios()
        b.mids_ts = time.time() - 10_000
        self.assertTrue(any("obsoletos" in m for m in b.bloqueos_entrada(58)))

    def test_fallo_de_ballenas_no_tumba_el_bot(self):
        b, _ = self.nuevo("shadow")
        b._seleccionar = mock.Mock(side_effect=ConnectionError("leaderboard caído"))
        b.actualizar_ballenas()
        b._hilo_seleccion.join(5)
        self.assertTrue(any(i["componente"] == "ballenas" for i in b.sistema.incidentes))
        b.leer_precios()
        b.procesar_candidatas([self.candidata()])            # sigue funcionando sin ballenas

    def test_websocket_reconecta_con_espera_creciente(self):
        b, _ = self.nuevo("shadow")
        b.c["tiempo_real"]["websocket"], b.url = True, "https://falso.invalid"
        e1 = b.ws_espera
        b._reconectar_ws("prueba")
        self.assertGreater(b.ws_espera, e1)
        self.assertGreater(b.ws_reintento, time.time())
        self.assertEqual(b.sistema.comp["websocket"]["estado"], "degradado")

    def test_simulado_abre_y_apagado_conserva_stops(self):
        b, ledger = self.nuevo("simulado")
        b.leer_precios()
        b.conciliacion_ok = b.conciliacion_inicial()
        b.c["ordenes"]["entrada_limite"] = False
        b.procesar_candidatas([self.candidata()])
        self.assertIn("ETH", b.estado["posiciones"], b.bloqueos)
        papel = b.ej.ex
        stops = [o for o in papel.d["ordenes"] if o["tipo"] == "stop"]
        self.assertEqual(len(stops), 1)
        b.apagar()
        self.assertEqual([o["oid"] for o in papel.d["ordenes"] if o["tipo"] == "stop"], [s["oid"] for s in stops])
        self.assertIn("ETH", papel.d["posiciones"])


class LatidoExterno(BotShadowYSimulado):
    def test_envia_y_respeta_intervalo(self):
        b, _ = self.nuevo("shadow")
        b.latido_url = "https://hc-ping.com/1234abcd-0000"
        with mock.patch.object(self.bot.requests, "get") as get:
            b.latido_externo()
            b.latido_hilo.join(2)
            b.latido_externo()          # antes de 5 minutos: no repite
        self.assertEqual(get.call_count, 1)
        self.assertEqual(b.sistema.comp["latido_externo"]["estado"], "correcto")

    def test_sin_url_queda_desactivado(self):
        b, _ = self.nuevo("shadow")
        b.latido_externo()
        self.assertEqual(b.sistema.comp["latido_externo"]["estado"], "desactivado")

    def test_url_oculta_en_logs(self):
        from observabilidad import ocultar_secretos
        self.assertNotIn("1234abcd", ocultar_secretos("fallo https://hc-ping.com/1234abcd-0000-1111"))


class Agenda(ConCarpeta):
    def test_agenda_lanza_lo_que_toca_y_nunca_dos_a_la_vez(self):
        import time as _t
        import bot as B
        b = B.Bot.__new__(B.Bot)
        b.c, b.estado = {"agenda": {"activa": True}}, {}
        lanzados = []
        b.lanzar_laboratorio = lambda: lanzados.append("lab") or (True, "")
        b.lanzar_investigacion = lambda: lanzados.append("inv") or (True, "")
        b._en_marcha = lambda: None
        aqui = B.AQUI
        B.AQUI = self.dir
        try:
            # domingo 05:00 local, sin laboratorio reciente -> laboratorio
            dom = _t.mktime((2026, 10, 25, 5, 0, 0, 0, 0, -1))
            b.agenda(dom)
            # lunes 03:00 con laboratorio hecho y sin investigación -> investigación
            b.estado["agenda"] = {"laboratorio": dom}
            b._agenda_ts = 0
            b.agenda(_t.mktime((2026, 10, 26, 3, 0, 0, 0, 0, -1)))
            # algo ya en marcha -> nada
            b._agenda_ts, b._en_marcha = 0, (lambda: "un laboratorio")
            b.agenda(_t.mktime((2026, 10, 27, 3, 0, 0, 0, 0, -1)))
        finally:
            B.AQUI = aqui
        self.assertEqual(lanzados, ["lab", "inv"])
