"""Pruebas del bot.

CP-M19 (auditoría 26/11/2026, T-09): las pruebas son HERMÉTICAS. Al importar este paquete se corta la red: cualquier
conexión o resolución de nombres fuera de la propia máquina (127.0.0.1 / ::1 / localhost) lanza RedProhibida, que deriva
de BaseException para que ningún «except Exception» del código la esconda y la prueba falle. Así una prueba no puede
llamar sin querer a api.hyperliquid.xyz, Binance o Bybit (ni pasar «igual» cuando no hay red).
"""
import socket

LOCALES = {"127.0.0.1", "::1", "localhost", "0.0.0.0", ""}
intentos = []                       # (destino) de cada intento bloqueado, para diagnosticar


class RedProhibida(BaseException):
    """Una prueba ha intentado salir a la red."""


def _host(direccion):
    if isinstance(direccion, (tuple, list)) and direccion:
        return str(direccion[0])
    return str(direccion)


def _bloquear(destino):
    intentos.append(destino)
    raise RedProhibida(f"prueba con red: intento de conexión a {destino!r} (usa un Info falso o un mock)")


_connect, _connect_ex = socket.socket.connect, socket.socket.connect_ex
_getaddrinfo, _create_connection = socket.getaddrinfo, socket.create_connection


def _connect_local(self, direccion):
    if self.family in (socket.AF_INET, socket.AF_INET6) and _host(direccion) not in LOCALES:
        _bloquear(direccion)
    return _connect(self, direccion)


def _connect_ex_local(self, direccion):
    if self.family in (socket.AF_INET, socket.AF_INET6) and _host(direccion) not in LOCALES:
        _bloquear(direccion)
    return _connect_ex(self, direccion)


def _getaddrinfo_local(host, *a, **k):
    if host is not None and str(host if not isinstance(host, bytes) else host.decode()) not in LOCALES:
        _bloquear(host)
    return _getaddrinfo(host, *a, **k)


def _create_connection_local(direccion, *a, **k):
    if _host(direccion) not in LOCALES:
        _bloquear(direccion)
    return _create_connection(direccion, *a, **k)


socket.socket.connect = _connect_local
socket.socket.connect_ex = _connect_ex_local
socket.getaddrinfo = _getaddrinfo_local
socket.create_connection = _create_connection_local


# Los intentos desde hilos de fondo no hacen fallar la prueba por sí solos (la excepción muere en el hilo): por eso,
# al terminar cada prueba, si hubo algún intento nuevo se anota como ERROR de esa prueba.
import sys       # noqa: E402
import unittest  # noqa: E402

_run = unittest.TestCase.run


def _run_hermetico(self, result=None):
    antes = len(intentos)
    salida = _run(self, result)
    nuevos = intentos[antes:]
    if nuevos and result is not None:
        try:
            raise RedProhibida(f"la prueba (o un hilo suyo) intentó salir a la red: {sorted(set(map(str, nuevos)))}")
        except RedProhibida:
            result.addError(self, sys.exc_info())
    return salida


unittest.TestCase.run = _run_hermetico
