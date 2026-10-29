"""Proceso de la esfera: ventana sin bordes, transparente y que no recibe clics.

Se lanza como `python -m asistente.esfera_ventana` y lee estados por stdin, uno por línea.
AppKit exige el hilo principal, por eso vive en un proceso aparte del bucle de voz.
"""

import math
import signal
import sys
import threading
import time

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSCompositingOperationClear,
    NSGradient,
    NSLineCapStyleRound,
    NSLineJoinStyleRound,
    NSRectFillUsingOperation,
    NSScreen,
    NSStatusWindowLevel,
    NSView,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
)
from Foundation import NSMakePoint, NSMakeRect, NSOperationQueue, NSTimer

from . import config
from .esfera_forma import (
    ESTADOS,
    Parametros,
    arco,
    centros_de_destello,
    contorno,
    mezclar,
)

FPS = 30
SUAVIZADO = 6.0  # qué tan rápido se acercan los parámetros al estado pedido (1/s)
APARICION = 3.5  # velocidad del fundido de entrada y salida (1/s)
LIGERO_BAJO_PRESENCIA = 0.6  # por debajo, la esfera está en espera: menos capas y menos cuadros

# (semiancho, grosor, opacidad, claridad) de cada capa de un destello, de la más ancha a la más brillante
_DESTELLOS = ((0.62, 5.0, 0.18, 0.2), (0.46, 4.0, 0.35, 0.4), (0.30, 3.0, 0.60, 0.7), (0.14, 2.2, 1.0, 1.0))
_DESTELLOS_LIGEROS = (_DESTELLOS[1], _DESTELLOS[3])


def _cian(alfa: float, claridad: float = 0.0) -> NSColor:
    return NSColor.colorWithSRGBRed_green_blue_alpha_(0.08 + 0.62 * claridad, 0.60 + 0.35 * claridad, 1.0, max(0.0, min(1.0, alfa)))


def _ruta(puntos, cx: float, cy: float, radio: float, cerrada: bool) -> NSBezierPath:
    ruta = NSBezierPath.bezierPath()
    for i, (x, y) in enumerate(puntos):
        punto = NSMakePoint(cx + x * radio, cy + y * radio)
        ruta.moveToPoint_(punto) if i == 0 else ruta.lineToPoint_(punto)
    if cerrada:
        ruta.closePath()
    ruta.setLineJoinStyle_(NSLineJoinStyleRound)
    ruta.setLineCapStyle_(NSLineCapStyleRound)
    return ruta


def _trazar(ruta: NSBezierPath, ancho: float, color: NSColor) -> None:
    color.setStroke()
    ruta.setLineWidth_(ancho)
    ruta.stroke()


class VistaEsfera(NSView):
    def initWithFrame_(self, marco):
        instancia = objc.super(VistaEsfera, self).initWithFrame_(marco)
        if instancia is None:
            return None
        self = instancia  # noqa: PLW0642 - patrón de PyObjC: init devuelve la instancia ya inicializada
        self.ventana_esfera = None
        self.parametros = ESTADOS["reposo"]
        self.objetivo = ESTADOS["reposo"]
        self.fase = 0.0  # se acumula: así un cambio de velocidad no da saltos
        self.reloj = 0.0
        self.opacidad = 0.0
        self.cuadros = 0
        self.ultimo = time.monotonic()
        return self

    def fijar_estado(self, nombre: str) -> None:
        self.objetivo = ESTADOS[nombre]
        if self.objetivo.presencia > 0 and self.ventana_esfera is not None and not self.ventana_esfera.isVisible():
            self.ventana_esfera.orderFrontRegardless()  # sin activar la app: el foco no se mueve

    def paso(self) -> None:
        ahora = time.monotonic()
        dt = min(ahora - self.ultimo, 0.25)
        self.ultimo = ahora
        meta = self.objetivo.presencia
        self.opacidad += max(-APARICION * dt, min(APARICION * dt, meta - self.opacidad))
        if self.opacidad <= 0.0 and meta == 0.0:
            if self.ventana_esfera is not None and self.ventana_esfera.isVisible():
                self.ventana_esfera.orderOut_(None)
            return  # oculta: no se dibuja ni se gasta CPU
        self.parametros = mezclar(self.parametros, self.objetivo, min(1.0, SUAVIZADO * dt))
        self.fase += dt * self.parametros.velocidad
        self.reloj += dt
        if self.ventana_esfera is not None:
            self.ventana_esfera.setAlphaValue_(self.opacidad)
        self.cuadros += 1
        # En espera, con movimiento lento, bastan 10 cuadros por segundo: gasta poco aunque esté siempre encendida.
        if self.parametros.presencia >= LIGERO_BAJO_PRESENCIA or self.cuadros % 3 == 0:
            self.setNeedsDisplay_(True)

    def drawRect_(self, _rect):
        NSRectFillUsingOperation(self.bounds(), NSCompositingOperationClear)
        if self.opacidad <= 0.0:
            return
        p: Parametros = self.parametros
        lado = self.bounds().size.width
        flotar_x = 0.012 * lado * math.sin(0.7 * self.reloj)
        flotar_y = 0.016 * lado * math.sin(0.5 * self.reloj + 1.0)
        cx, cy = lado / 2 + flotar_x, lado / 2 + flotar_y
        radio = lado * 0.31 * (0.88 + 0.12 * self.opacidad)
        respiro = 0.85 + 0.15 * math.sin(self.reloj * 1.6)  # el resplandor late despacio
        brillo = p.brillo * respiro

        ligero = p.presencia < LIGERO_BAJO_PRESENCIA  # en espera se dibujan menos capas
        silueta = _ruta(contorno(self.fase, p.amplitud, p.pulso), cx, cy, radio, cerrada=True)
        segunda = _ruta(contorno(self.fase, p.amplitud * 1.15, p.pulso, desfase=1.3), cx, cy, radio * 0.965, cerrada=True)

        # Interior casi transparente: solo un velo de cristal que se intensifica hacia el borde.
        NSGradient.alloc().initWithStartingColor_endingColor_(_cian(0.0), _cian(0.08 * brillo)).drawInBezierPath_relativeCenterPosition_(
            silueta, NSMakePoint(0, 0)
        )

        # Resplandor: capas anchas y tenues bajo una línea fina y clara.
        for ancho, alfa in ((15, 0.09), (8, 0.16)) if ligero else ((24, 0.05), (15, 0.09), (8, 0.16)):
            _trazar(silueta, ancho, _cian(alfa * brillo))
            if not ligero:
                _trazar(segunda, ancho * 0.6, _cian(alfa * 0.6 * brillo))
        _trazar(segunda, 1.1, _cian(0.60 * brillo, 0.4))
        _trazar(silueta, 1.9, _cian(0.95 * brillo, 0.55))

        # Destellos que recorren el borde, más intensos hacia su centro.
        capas = _DESTELLOS_LIGEROS if ligero else _DESTELLOS
        for centro in centros_de_destello(self.fase):
            for semiancho, ancho, alfa, claridad in capas:
                tramo = arco(centro, semiancho, self.fase, p.amplitud, p.pulso)
                _trazar(_ruta(tramo, cx, cy, radio, False), ancho, _cian(alfa * brillo, claridad))


def _crear_ventana() -> tuple[NSWindow, VistaEsfera]:
    lado = config.ESFERA_LADO
    pantalla = NSScreen.screens()[0].visibleFrame()  # debajo de la barra de menús
    x = pantalla.origin.x + pantalla.size.width - lado - config.ESFERA_MARGEN
    y = pantalla.origin.y + pantalla.size.height - lado - config.ESFERA_MARGEN
    ventana = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(x, y, lado, lado), NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False
    )
    ventana.setOpaque_(False)
    ventana.setBackgroundColor_(NSColor.clearColor())
    ventana.setHasShadow_(False)
    ventana.setIgnoresMouseEvents_(True)  # los clics la atraviesan
    ventana.setLevel_(NSStatusWindowLevel)
    ventana.setReleasedWhenClosed_(False)
    ventana.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorStationary
        | NSWindowCollectionBehaviorIgnoresCycle
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    vista = VistaEsfera.alloc().initWithFrame_(NSMakeRect(0, 0, lado, lado))
    vista.ventana_esfera = ventana
    ventana.setContentView_(vista)
    return ventana, vista


def _leer_estados(vista: VistaEsfera, app) -> None:
    """Hilo lector: aplica los estados en el hilo principal y cierra al llegar EOF (el padre murió o terminó)."""
    cola = NSOperationQueue.mainQueue()
    for linea in sys.stdin:
        nombre = linea.strip()
        if nombre in ESTADOS:
            cola.addOperationWithBlock_(lambda nombre=nombre: vista.fijar_estado(nombre))
    cola.addOperationWithBlock_(lambda: app.terminate_(None))


def principal() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ctrl+C va al asistente; la esfera cierra con él
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # sin icono en el Dock
    _ventana, vista = _crear_ventana()
    threading.Thread(target=_leer_estados, args=(vista, app), daemon=True).start()
    NSTimer.scheduledTimerWithTimeInterval_repeats_block_(1.0 / FPS, True, lambda _temporizador: vista.paso())
    app.run()


if __name__ == "__main__":
    principal()
