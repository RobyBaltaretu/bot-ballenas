"""
Detalles para que el bot funcione igual en Windows, macOS y Linux.
"""

import os
import subprocess
import sys
import time


def reemplazar(origen, destino, intentos=20):
    """os.replace con reintentos: en Windows falla si otro programa (p. ej. el panel)
    tiene el archivo abierto en ese mismo instante."""
    for i in range(intentos):
        try:
            os.replace(origen, destino)
            return
        except PermissionError:
            if i == intentos - 1:
                raise
            time.sleep(0.1)


def consola_utf8():
    """Evita errores al mostrar acentos, emojis o símbolos en la consola de Windows."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def consola_sin_seleccion(log=None):
    """Desactiva la «edición rápida» de la consola de Windows. Con ella, un clic en la ventana la pone en modo
    «Seleccionar»: toda escritura en la consola se bloquea y el bot entero se queda parado sin dar ningún error."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.GetStdHandle.restype = ctypes.c_void_p
        entrada = k32.GetStdHandle(-10)
        modo = ctypes.c_uint32()
        if not k32.GetConsoleMode(ctypes.c_void_p(entrada), ctypes.byref(modo)):
            return False               # sin consola (servicio, pythonw, entrada redirigida): nada que proteger
        nuevo = (modo.value & ~0x0040) | 0x0080      # sin ENABLE_QUICK_EDIT_MODE, con ENABLE_EXTENDED_FLAGS
        return bool(k32.SetConsoleMode(ctypes.c_void_p(entrada), nuevo))
    except Exception as e:  # noqa: BLE001
        if log:
            log.debug("No pude ajustar la consola: %s", e)
        return False


def evitar_suspension(log=None):
    """Impide que el ordenador se duerma por inactividad mientras el bot está en marcha.
    No evita que se duerma si cierras la tapa del portátil o se queda sin batería."""
    try:
        if sys.platform == "win32":
            import ctypes
            ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        elif sys.platform == "darwin":
            subprocess.Popen(["caffeinate", "-is", "-w", str(os.getpid())])
        else:
            return
        if log:
            log.info("El ordenador no se dormirá mientras el bot esté en marcha.")
    except Exception as e:  # noqa: BLE001
        if log:
            log.warning("No pude evitar que el ordenador se duerma (%s).", e)
