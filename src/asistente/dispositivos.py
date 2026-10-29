"""Consulta del micrófono predeterminado de macOS directamente a CoreAudio."""

import ctypes

_core = ctypes.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")


class _Direccion(ctypes.Structure):
    _fields_ = [
        ("selector", ctypes.c_uint32),
        ("ambito", ctypes.c_uint32),
        ("elemento", ctypes.c_uint32),
    ]


def _codigo(texto: str) -> int:
    return int.from_bytes(texto.encode("ascii"), "big")


_OBJETO_SISTEMA = 1
_ENTRADA_POR_DEFECTO = _codigo("dIn ")
_AMBITO_GLOBAL = _codigo("glob")

_core.AudioObjectGetPropertyData.argtypes = [
    ctypes.c_uint32,
    ctypes.POINTER(_Direccion),
    ctypes.c_uint32,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_void_p,
]
_core.AudioObjectGetPropertyData.restype = ctypes.c_int32


def entrada_por_defecto() -> int:
    """Identificador del micrófono predeterminado; cambia al conectar o quitar AirPods."""
    direccion = _Direccion(_ENTRADA_POR_DEFECTO, _AMBITO_GLOBAL, 0)
    dispositivo = ctypes.c_uint32(0)
    tamano = ctypes.c_uint32(ctypes.sizeof(dispositivo))
    error = _core.AudioObjectGetPropertyData(
        _OBJETO_SISTEMA, ctypes.byref(direccion), 0, None, ctypes.byref(tamano), ctypes.byref(dispositivo)
    )
    if error != 0:
        raise OSError(f"CoreAudio devolvió el error {error}")
    return dispositivo.value
