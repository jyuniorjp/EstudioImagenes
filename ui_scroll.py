# -*- coding: utf-8 -*-
"""Rueda del ratón cómoda en toda la app.

CustomTkinter hace que CADA zona deslizable escuche la rueda en toda la aplicación y solo compruebe que el ratón
esté «en algún lugar dentro» de ella. Por eso, con un cuadro de texto largo dentro del panel (tu prompt, «Lo que se
envía»), se movían el cuadro Y el panel a la vez, y con zonas anidadas se movía la de fuera.

Regla nueva: se desliza SOLO lo que está bajo el ratón, empezando por lo más interno (un cuadro de texto, luego su
zona deslizable, luego la de fuera). Si lo de dentro ya llegó al final (o no tiene más contenido), la rueda pasa a lo
de fuera, como en los navegadores. Llamar install() una vez, antes de crear las ventanas.
"""
import sys

import customtkinter as ctk

_installed = False


def _at_end(view, delta):
    """¿Ya no puede moverse más en esa dirección? (delta > 0: hacia arriba)."""
    first, last = view
    if last - first >= 0.999:                    # cabe entero: no hay nada que deslizar
        return True
    return first <= 0.0001 if delta > 0 else last >= 0.9999


def target_for(widget, delta):
    """Lo que debe moverse con la rueda: un widget de texto (se mueve solo), una zona deslizable, o None."""
    w = widget
    while w is not None:
        try:
            cls = w.winfo_class()
        except Exception:
            return None
        if cls == "Text":
            try:
                if not _at_end(w.yview(), delta):
                    return w
            except Exception:
                pass
        owner = getattr(w, "_wheel_owner", None)
        if owner is not None:
            try:
                if not _at_end(owner._parent_canvas.yview(), delta):
                    return owner
            except Exception:
                pass
        w = getattr(w, "master", None)
    return None


def install():
    global _installed
    if _installed:
        return
    _installed = True
    SF = ctk.CTkScrollableFrame
    orig_init, orig_wheel = SF.__init__, SF._mouse_wheel_all

    def __init__(self, *a, **k):
        orig_init(self, *a, **k)
        try:
            self._parent_canvas._wheel_owner = self      # para saber a qué zona pertenece cada lienzo
            # 1 «unidad» = 1 píxel: el paso es parejo en todas las zonas
            self._parent_canvas.configure(yscrollincrement=1)
        except Exception:
            pass

    def _mouse_wheel_all(self, event):
        if getattr(self, "_shift_pressed", False):     # horizontal: lo de siempre
            return orig_wheel(self, event)
        try:
            w = event.widget
            if isinstance(w, str):
                w = self.nametowidget(w)
        except Exception:
            return
        delta = event.delta if event.delta else (120 if getattr(event, "num", 0) == 4 else -120)
        if target_for(w, delta) is not self:
            return
        try:
            step = -int(delta / 3) if sys.platform.startswith("win") else -int(delta) * 20   # ~40 px por vuelta
            self._parent_canvas.yview("scroll", step, "units")
        except Exception:
            pass

    SF.__init__ = __init__
    SF._mouse_wheel_all = _mouse_wheel_all
