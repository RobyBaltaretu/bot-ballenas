"""
TALLER (18/11/2026): revisión completa del sistema en un solo paso, en lenguaje llano.

Cada comprobación devuelve un estado (ok / aviso / mal / pendiente / desconocido), una frase corta, una explicación
para el botón ⓘ y, si procede, un ARREGLO SEGURO. Los arreglos son siempre cosas que el bot ya sabe hacer y que no
tocan dinero, límites ni el modo: reanudar entradas, reiniciar de forma ordenada, lanzar el laboratorio o la
investigación. Lo demás (poner una clave en .env, abrir INICIAR.bat) se explica paso a paso, porque debe hacerlo una
persona. Nada de aquí cambia la configuración, aprueba estrategias ni pasa a real.

Solo LEE archivos de la carpeta del bot y no hace peticiones de red. De .env solo se mira si una variable tiene valor
(sí/no): nunca se lee ni se devuelve su contenido.

Un dato que no se puede comprobar es «desconocido», nunca «ok».
"""

import json
import os
import shutil
import time

AQUI = os.path.dirname(os.path.abspath(__file__))

ORDEN = {"mal": 0, "aviso": 1, "desconocido": 2, "pendiente": 3, "ok": 4}
GRUPOS = (
    ("motor", "Motor", "El bot: que esté vivo y trabajando a buen ritmo"),
    ("datos", "Datos", "Lo que el bot mira: precios, ballenas y fuentes externas"),
    ("proteccion", "Protección", "Que cada posición tenga su stop y la cuenta cuadre"),
    ("cerebro", "Cerebro", "Laboratorio, investigación y hipótesis en curso"),
    ("almacen", "Almacén", "Disco, registros, configuración y avisos"),
)

REINICIAR = {"tipo": "comando", "cmd": "/aplicarconfig", "etiqueta": "Reiniciar el bot de forma ordenada",
             "confirma": "El bot valida su configuración y se reinicia en unos segundos. Las posiciones abiertas "
                         "conservan su stop en el exchange."}


def _json(carpeta, nombre, defecto=None):
    try:
        with open(os.path.join(carpeta, nombre), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return defecto


def _edad_archivo(carpeta, nombre, ahora):
    try:
        return ahora - os.path.getmtime(os.path.join(carpeta, nombre))
    except OSError:
        return None


def _env_con_valor(carpeta):
    """Nombres de variables de .env que tienen valor. NUNCA devuelve los valores."""
    out = set()
    try:
        with open(os.path.join(carpeta, ".env"), encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                k, v = linea.split("=", 1)
                if v.strip().strip("'\""):
                    out.add(k.strip())
    except OSError:
        pass
    return out


def humano(seg):
    if seg is None:
        return "—"
    seg = max(0, seg)
    if seg < 90:
        return f"{round(seg)} s"
    if seg < 5400:
        return f"{round(seg / 60)} min"
    if seg < 172800:
        return f"{seg / 3600:.1f} h"
    return f"{seg / 86400:.1f} días"


def c(id_, grupo, titulo, estado, resumen, detalle, arreglo=None, pasos=None):
    """Una comprobación. pasos: instrucciones para quien tiene que arreglarlo a mano."""
    return {"id": id_, "grupo": grupo, "titulo": titulo, "estado": estado, "resumen": resumen, "detalle": detalle,
            "arreglo": arreglo, "pasos": pasos or []}


# ------------------------------------------------------------------------------------------------ motor
def _motor(sis, ahora):
    out = []
    lat = sis.get("latido_ts")
    edad = ahora - lat if lat else None
    det = ("El bot escribe un «latido» en cada ciclo (cada ~6 segundos). Si el último es muy viejo, el bot está parado, "
           "bloqueado o el PC se durmió.")
    if edad is None:
        out.append(c("latido", "motor", "El bot está vivo", "desconocido", "Sin latido registrado.", det,
                     pasos=["Abre INICIAR.bat para arrancar el bot.", "Si ya está abierto, espera un minuto y vuelve a revisar."]))
    elif edad <= 180:
        out.append(c("latido", "motor", "El bot está vivo", "ok", f"Último latido hace {humano(edad)}.", det))
    elif edad <= 600:
        out.append(c("latido", "motor", "El bot está vivo", "aviso", f"Último latido hace {humano(edad)}: va con retraso.", det,
                     arreglo=REINICIAR))
    else:
        out.append(c("latido", "motor", "El bot está vivo", "mal", f"Sin latido desde hace {humano(edad)}: parece parado.", det,
                     pasos=["Abre INICIAR.bat (o reinicia el lanzador) para arrancar el bot.",
                            "Sus posiciones abiertas conservan su stop en el exchange mientras tanto.",
                            "Cuando arranque, pulsa «Revisar de nuevo»."]))
    ciclos, fall = sis.get("ciclos") or 0, sis.get("ciclos_fallidos") or 0
    med, p95 = sis.get("ciclo_mediana_seg"), sis.get("ciclo_p95_seg")
    det = "Cada ciclo es una vuelta del bot: leer precios, vigilar posiciones y decidir. Un ciclo lento retrasa sus reacciones."
    if med is None:
        out.append(c("ciclo", "motor", "Ritmo de trabajo", "desconocido", "Aún sin medidas de ciclo.", det))
    else:
        mal = fall / ciclos > 0.05 if ciclos else False
        lento = p95 is not None and p95 > 30
        est = "mal" if mal else "aviso" if lento or med > 15 else "ok"
        out.append(c("ciclo", "motor", "Ritmo de trabajo", est,
                     f"Ciclo típico {med:.1f} s (peor 5 %: {p95:.1f} s) · {fall} fallidos de {ciclos}.", det,
                     arreglo=REINICIAR if est != "ok" else None))
    return out


# ------------------------------------------------------------------------------------------------ datos
def _datos(sis, bot, ahora):
    out = []
    ts = bot.get("precios_ts")
    edad = ahora - ts if ts else None
    det = "Sin precios frescos el bot no abre operaciones nuevas. Los precios llegan de Hyperliquid cada pocos segundos."
    if edad is None:
        out.append(c("precios", "datos", "Precios al día", "desconocido", "Sin hora del último precio.", det))
    elif edad <= 60 and bot.get("datos_frescos") is not False:
        out.append(c("precios", "datos", "Precios al día", "ok", f"Último precio hace {humano(edad)}.", det))
    else:
        out.append(c("precios", "datos", "Precios al día", "mal" if edad > 300 else "aviso",
                     f"Último precio hace {humano(edad)}: el bot no abre nada nuevo hasta que se recupere.", det, arreglo=REINICIAR))
    comp = sis.get("componentes") or {}
    ws = comp.get("websocket") or {}
    out.append(c("websocket", "datos", "Conexión en tiempo real",
                 "ok" if ws.get("estado") == "correcto" else "aviso" if ws else "desconocido",
                 ws.get("detalle") or "Sin información.",
                 "Conexión continua con Hyperliquid para seguir a las ballenas y recibir precios al instante. Si cae, el bot "
                 "usa sondeos más lentos y se reconecta solo.", arreglo=REINICIAR if ws.get("estado") not in (None, "correcto", "desactivado") else None))
    cob = bot.get("cobertura_ballenas") or {}
    el, fr = cob.get("elegidas"), cob.get("frescas")
    det = "El bot sigue a cuentas grandes de Hyperliquid. «Frescas» son las que se han leído hace poco."
    if not el:
        out.append(c("ballenas", "datos", "Ballenas seguidas", "aviso", "No sigue ninguna cuenta ahora mismo.", det))
    else:
        out.append(c("ballenas", "datos", "Ballenas seguidas", "ok" if fr is not None and fr / el >= 0.5 else "aviso",
                     f"{fr if fr is not None else '?'} de {el} con datos frescos.", det))
    ext = (bot.get("contexto_externo") or {}).get("fuentes") or {}
    det = "Binance y Bybit se usan solo para leer datos públicos de mercado. El bot nunca opera allí."
    if (bot.get("contexto_externo") or {}).get("activo") is False:
        out.append(c("externas", "datos", "Binance y Bybit (solo lectura)", "pendiente", "Desactivado en la configuración.", det))
    elif not ext:
        out.append(c("externas", "datos", "Binance y Bybit (solo lectura)", "desconocido", "Sin información de las fuentes.", det))
    else:
        malas = [k for k, v in ext.items() if v.get("estado") != "correcto"]
        out.append(c("externas", "datos", "Binance y Bybit (solo lectura)", "ok" if not malas else "aviso",
                     "Las dos fuentes responden." if not malas else f"Con problemas: {', '.join(malas)}.", det))
    return out


# ------------------------------------------------------------------------------------------------ protección
def _proteccion(sis, bot, ahora):
    out = []
    conc = bot.get("conciliacion_ts")
    det = "Cada pocos segundos el bot compara lo que cree tener con lo que dice la cuenta. Si no cuadra, algo falla."
    if bot.get("conciliacion_ok") is False:
        out.append(c("conciliacion", "proteccion", "La cuenta cuadra con el registro", "mal", "NO cuadra: revisa el sistema.", det,
                     arreglo=REINICIAR, pasos=["Mira la pestaña «Registros» por errores recientes.", "Si persiste, descarga el diagnóstico."]))
    elif not conc or ahora - conc > 300:
        out.append(c("conciliacion", "proteccion", "La cuenta cuadra con el registro", "desconocido",
                     f"Última comprobación hace {humano(ahora - conc) if conc else '—'}.", det, arreglo=REINICIAR))
    else:
        out.append(c("conciliacion", "proteccion", "La cuenta cuadra con el registro", "ok", f"Comprobado hace {humano(ahora - conc)}.", det))
    pos = bot.get("posiciones") or []
    sin = bot.get("sin_stop") or {}
    det = "Cada posición debe tener su stop colocado y verificado en el exchange: es lo que limita la pérdida si algo falla."
    sin_ok = [p.get("moneda") for p in pos if not p.get("stop_verificado")]
    if sin:
        out.append(c("stops", "proteccion", "Todas las posiciones tienen su stop", "mal", f"Stop NO confirmado: {', '.join(sin)}.", det,
                     pasos=["El bot lo está reintentando solo. Si dura más de unos minutos, cierra esa posición desde Control."]))
    elif not pos:
        out.append(c("stops", "proteccion", "Todas las posiciones tienen su stop", "ok", "No hay posiciones abiertas.", det))
    elif sin_ok:
        out.append(c("stops", "proteccion", "Todas las posiciones tienen su stop", "aviso", f"Sin verificar aún: {', '.join(sin_ok)}.", det))
    else:
        out.append(c("stops", "proteccion", "Todas las posiciones tienen su stop", "ok", f"{len(pos)} de {len(pos)} verificados.", det))
    liq = bot.get("riesgo_liquidacion") or {}
    frac = (bot.get("margen") or {}).get("fraccion_mantenimiento")
    det = "Si el precio llegara a la liquidación antes que al stop, se perdería la posición entera. El bot exige que quede lejos."
    if liq:
        out.append(c("liquidacion", "proteccion", "Lejos de la liquidación", "mal", "; ".join(f"{m}: {x}" for m, x in liq.items())[:160], det))
    else:
        out.append(c("liquidacion", "proteccion", "Lejos de la liquidación", "ok" if frac is None or frac < 0.5 else "aviso",
                     "Ninguna posición cerca." if frac is None else f"Margen de mantenimiento al {frac * 100:.1f} % del valor.", det))
    bloq = bot.get("bloqueos") or []
    pausa = "pausa manual" in bloq
    det = "Un bloqueo impide abrir operaciones nuevas (pérdida diaria, caída máxima, datos viejos, pausa…). Las abiertas siguen protegidas."
    if pausa:
        out.append(c("bloqueos", "proteccion", "Entradas permitidas", "aviso", "Pausaste las entradas nuevas.", det,
                     arreglo={"tipo": "comando", "cmd": "/reanudar", "etiqueta": "Reanudar entradas",
                              "confirma": "El bot vuelve a abrir operaciones si se cumplen sus reglas."}))
    elif bloq:
        out.append(c("bloqueos", "proteccion", "Entradas permitidas", "aviso", "; ".join(bloq)[:200], det,
                     pasos=["Es una protección del bot, no un fallo: se levanta sola cuando la causa desaparece."]))
    else:
        out.append(c("bloqueos", "proteccion", "Entradas permitidas", "ok", "Sin bloqueos.", det))
    desc = (bot.get("exposicion") or {}).get("riesgo_desconocido") or []
    out.append(c("riesgo_conocido", "proteccion", "Riesgo de cada posición conocido", "ok" if not desc else "mal",
                 "Todo el riesgo está contado." if not desc else f"No se sabe cuánto arriesga: {', '.join(desc)}.",
                 "Un riesgo desconocido nunca cuenta como cero: si falta, el bot no abre nada nuevo hasta saberlo."))
    return out


# ------------------------------------------------------------------------------------------------ cerebro
def _cerebro(carpeta, bot, ahora):
    out = []
    lock_lab = _edad_archivo(carpeta, "laboratorio_semanal.lock", ahora)
    lock_inv = _edad_archivo(carpeta, "investigacion.lock", ahora)
    en_marcha = (lock_lab is not None and lock_lab < 12 * 3600) or (lock_inv is not None and lock_inv < 12 * 3600)
    edad = _edad_archivo(carpeta, "estrategia_elegida.json", ahora)
    det = "El laboratorio prueba las estrategias con años de datos cada domingo. Sin laboratorio reciente, el veredicto de cada una envejece."
    if lock_lab is not None and lock_lab < 12 * 3600:
        out.append(c("laboratorio", "cerebro", "Laboratorio semanal", "ok", f"En marcha desde hace {humano(lock_lab)}.", det))
    elif edad is None:
        out.append(c("laboratorio", "cerebro", "Laboratorio semanal", "desconocido", "Sin resultados guardados.", det,
                     arreglo={"tipo": "comando", "cmd": "/laboratorio", "etiqueta": "Lanzar el laboratorio ahora",
                              "confirma": "Tarda varias horas y trabaja en segundo plano. El bot sigue operando con normalidad."}))
    elif edad <= 9 * 86400:
        out.append(c("laboratorio", "cerebro", "Laboratorio semanal", "ok", f"Último resultado hace {humano(edad)}.", det))
    else:
        out.append(c("laboratorio", "cerebro", "Laboratorio semanal", "aviso" if edad <= 15 * 86400 else "mal",
                     f"Último resultado hace {humano(edad)}: toca uno nuevo.", det,
                     arreglo=None if en_marcha else {"tipo": "comando", "cmd": "/laboratorio", "etiqueta": "Lanzar el laboratorio ahora",
                                                    "confirma": "Tarda varias horas y trabaja en segundo plano. El bot sigue operando con normalidad."}))
    edad = _edad_archivo(carpeta, "registro/investigacion_informe.json", ahora)
    det = "Cada noche el departamento de investigación examina ideas nuevas (hoy congelado) y vigila las que están en seguimiento."
    if lock_inv is not None and lock_inv < 12 * 3600:
        out.append(c("investigacion", "cerebro", "Investigación nocturna", "ok", f"En marcha desde hace {humano(lock_inv)}.", det))
    elif edad is None:
        out.append(c("investigacion", "cerebro", "Investigación nocturna", "desconocido", "Sin informe guardado.", det))
    elif edad <= 2 * 86400:
        out.append(c("investigacion", "cerebro", "Investigación nocturna", "ok", f"Último informe hace {humano(edad)}.", det))
    else:
        out.append(c("investigacion", "cerebro", "Investigación nocturna", "aviso", f"Último informe hace {humano(edad)}.", det,
                     arreglo=None if en_marcha else {"tipo": "comando", "cmd": "/investigacion", "etiqueta": "Lanzar la investigación ahora",
                                                    "confirma": "Dura hasta 90 minutos en segundo plano."}))
    cer = bot.get("cerebro") or {}
    det = "El cerebro es el modelo que decide qué propuestas se operan. Sin modelo válido, el bot se abstiene."
    if cer.get("error"):
        out.append(c("cerebro", "cerebro", "Modelo del cerebro", "mal", str(cer["error"])[:160], det))
    elif cer.get("version"):
        out.append(c("cerebro", "cerebro", "Modelo del cerebro", "ok", f"Cargado: {str(cer['version']).replace('cerebro-lab-', '')}.", det))
    else:
        out.append(c("cerebro", "cerebro", "Modelo del cerebro", "aviso", "Sin modelo cargado.", det))
    pre = _json(carpeta, "preregistro_estado.json")
    det = "Las hipótesis prerregistradas se juzgan una sola vez con datos nuevos. Este archivo guarda su veredicto definitivo."
    out.append(c("preregistro", "cerebro", "Hipótesis prerregistradas", "ok" if pre is not None else "pendiente",
                 "Estado guardado." if pre is not None else "Se crea tras el primer laboratorio con datos posteriores al 17/11.", det))
    return out


# ------------------------------------------------------------------------------------------------ almacén
def _almacen(carpeta, sis, bot, env, ahora, validar_config):
    out = []
    disco = sis.get("disco") or {}
    try:
        libre = shutil.disk_usage(carpeta).free / 1e9
    except OSError:
        libre = disco.get("libre_gb")
    det = "El bot guarda velas, el libro de órdenes y registros. Con el disco lleno dejaría de guardar y podría fallar."
    if libre is None:
        out.append(c("disco", "almacen", "Espacio en disco", "desconocido", "No se pudo medir.", det))
    else:
        out.append(c("disco", "almacen", "Espacio en disco", "ok" if libre >= 10 else "aviso" if libre >= 3 else "mal",
                     f"{libre:.0f} GB libres.", det,
                     pasos=[] if libre >= 10 else ["Libera espacio en el disco (no borres datos_mercado ni datos_archivo)."]))
    inc = sis.get("incidentes_activos")
    det = "Los incidentes son fallos técnicos que el bot ha detectado y registra. «Reconocer» no los arregla: solo dice que los has visto."
    out.append(c("incidentes", "almacen", "Incidentes técnicos", "ok" if inc == 0 else "desconocido" if inc is None else "aviso",
                 "Ninguno activo." if inc == 0 else "Sin datos." if inc is None else f"{inc} activo(s).", det,
                 pasos=[] if inc in (0, None) else ["Abre la pestaña «Incidentes» para verlos y reconocerlos."]))
    if validar_config is not None:
        ok, msg = validar_config()
        out.append(c("config", "almacen", "Configuración válida", "ok" if ok else "mal", msg[:200],
                     "config.json se valida con las mismas reglas que al arrancar. Si no es válida, el bot se niega a reiniciar.",
                     pasos=[] if ok else ["Restaura la configuración anterior en Configuración → Historial y restaurar."]))
    tg = {"TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"} <= env
    out.append(c("telegram", "almacen", "Avisos por Telegram", "ok" if tg else "pendiente",
                 "Configurado." if tg else "Sin configurar: no recibes avisos en el móvil.",
                 "Con Telegram el bot te avisa de stops, errores y cierres, y puedes pausarlo desde el móvil.",
                 pasos=[] if tg else ["En Telegram, habla con @BotFather → /newbot y copia el token.",
                                      "Escribe algo a tu bot y ejecuta «python notificaciones.py» para ver tu chat_id.",
                                      "Pon TELEGRAM_TOKEN y TELEGRAM_CHAT_ID en el archivo .env (lo haces tú; nunca me los pases).",
                                      "Después usa «Reiniciar el bot de forma ordenada»."]))
    cfg = _json(carpeta, "config.json", {}).get("panel", {})
    clave = "PANEL_PASSWORD" in env
    sin_clave = bool(cfg.get("tunel_sin_clave")) and not clave
    out.append(c("panel_clave", "almacen", "Contraseña del panel", "ok" if clave else "aviso" if sin_clave else "pendiente",
                 "Puesta." if clave else "El túnel entra SIN contraseña (solo lectura)." if sin_clave else "Sin contraseña (solo se usa en este equipo).",
                 "La contraseña protege el panel si lo abres desde fuera. Sin ella, el acceso remoto es solo de lectura.",
                 pasos=[] if clave else ["Pon PANEL_PASSWORD en .env (lo haces tú) y quita «tunel_sin_clave» de config.json."]))
    ap = (bot.get("modo") == "real")
    out.append(c("modo", "almacen", "Modo de funcionamiento", "aviso" if ap else "ok",
                 "REAL: dinero real." if ap else f"{(bot.get('modo') or '?').capitalize()}: dinero ficticio.",
                 "El panel nunca cambia el modo. Pasar a real exige promocion.py y tu aprobación expresa."))
    return out


def revisar(carpeta=AQUI, ahora=None, validar_config=None, extras=None):
    """Revisión completa. validar_config: función sin argumentos -> (ok, mensaje), o None para omitirla.
    extras: comprobaciones adicionales que aporta quien llama (p. ej. el panel, que conoce el registro contable)."""
    ahora = time.time() if ahora is None else ahora
    sis = _json(carpeta, "estado_sistema.json", {}) or {}
    bot = _json(carpeta, "panel_datos.json", {}) or {}
    env = _env_con_valor(carpeta)
    checks = (_motor(sis, ahora) + _datos(sis, bot, ahora) + _proteccion(sis, bot, ahora) + _cerebro(carpeta, bot, ahora)
              + _almacen(carpeta, sis, bot, env, ahora, validar_config) + list(extras or []))
    cuenta = {k: sum(1 for x in checks if x["estado"] == k) for k in ORDEN}
    peor = min(checks, key=lambda x: ORDEN[x["estado"]])["estado"] if checks else "desconocido"
    # El estado global ignora lo «pendiente» (cosas tuyas por hacer): no es un fallo.
    global_ = "ok" if peor in ("ok", "pendiente") else peor
    trabajos = sorted((x for x in checks if x["estado"] in ("mal", "aviso", "desconocido")), key=lambda x: ORDEN[x["estado"]])
    return {"ts": ahora, "estado": global_, "cuenta": cuenta, "total": len(checks),
            "grupos": [{"id": g, "titulo": t, "texto": tx, "checks": [x for x in checks if x["grupo"] == g]} for g, t, tx in GRUPOS],
            "trabajos": [x["id"] for x in trabajos], "pendientes": [x["id"] for x in checks if x["estado"] == "pendiente"]}
