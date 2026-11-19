# -*- coding: utf-8 -*-
"""Iconos e ilustraciones de la interfaz, dibujados por el propio Estudio (herramientas\\generar_iconos.py).

install(): TEMA para todos los botones de la app, en el momento de crearlos (y cuando cambia su texto):
icono según el texto, esquinas redondeadas, borde suave en los botones secundarios y altura cómoda.
apply(widget): recorre la ventana y, según el texto de cada botón, le pone su icono y le quita el emoji.
Si un icono falta, el botón se queda con su emoji de siempre: nunca queda un botón vacío.
"""
import os
import sys

import customtkinter as ctk
from PIL import Image

# texto del botón (sin espacios a los lados) -> (icono, texto nuevo)
BY_TEXT = {
    "💡 Ejemplos y consejos": ("ejemplos", "Ejemplos"),
    "💡 Consejos para describir mejor y cómo trabajan los modelos":
        ("ejemplos", "Consejos para describir mejor y cómo trabajan los modelos"),
    "🎬 Editor de miniaturas": ("editor", "Editor de miniaturas"),
    "⌨": ("atajos", ""),
    "📎 Subir imágenes de referencia": ("referencia", "Subir imágenes de referencia"),
    "📁 Cambiar carpeta…": ("carpeta", "Cambiar carpeta…"),
    "Crear imagen": ("crear", "Crear imagen"),
    "⋯ Más": ("mas", "Más"),
    "🎬 Usar en miniatura": ("editor", "Usar en miniatura"),
    "Otra parecida": ("parecida", "Otra parecida"),
    "Guardar como…": ("guardar", "Guardar como…"),
    "Abrir carpeta": ("carpeta", "Abrir carpeta"),
    "✨ Crear ahora": ("crear", "Crear ahora"),
    "🎬 Miniatura para YouTube": ("editor", "Miniatura para YouTube"),
    "🎬 Abrir las capas en el editor": ("editor", "Abrir las capas en el editor"),
    "✨ Armar la miniatura por capas": ("crear", "Armar la miniatura por capas"),
    "✨ Pulir con IA": ("crear", "Pulir con IA"),
    "Usar la idea": ("inspiracion", "Usar la idea"),
    "Usar este ejemplo": ("crear", "Usar este ejemplo"),
    "Cambiar…": ("carpeta", "Cambiar…"),
}
# cualquier otro botón que empiece con uno de estos emojis también recibe su icono (y pierde el emoji)
BY_EMOJI = {"🎨": "crear", "✨": "crear", "📁": "carpeta", "📂": "carpeta", "🖼": "galeria", "💾": "guardar",
            "🔎": "inspiracion", "🔍": "inspiracion", "👁": "inspiracion", "💡": "ejemplos", "🎬": "editor",
            "📎": "referencia", "🌐": "internet", "⌨": "atajos"}
_cache = {}


def res(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


# colores del tema (los mismos de la app)
SURF3 = "#18233c"
EDGE = "#2b3d66"            # borde suave de los botones secundarios
ICON = 20                   # tamaño de los iconos en los botones
BIG = {"Crear imagen": 24, "Crear ahora": 22}


def icon(name, size=18):
    """CTkImage del icono (o None si no está). En tamaños pequeños usa la versión «_s»: solo el dibujo blanco,
    sin la baldosa de color (a 20 px la baldosa entera se veía como una mancha)."""
    key = (name, size)
    if key in _cache:
        return _cache[key]
    p = res("ui_iconos", name + ".png")
    small = res("ui_iconos", name + "_s.png")
    if size <= 40 and os.path.isfile(small):
        p = small
    img = None
    if os.path.isfile(p):
        try:
            with Image.open(p) as im:
                pil = im.convert("RGBA")
            img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(size, size))
        except Exception:
            img = None
    _cache[key] = img
    return img


def art(name, size):
    """Ilustración (ui_iconos\\<name>.png/.jpg) como CTkImage del tamaño dado, recortada sin deformar."""
    for ext in (".png", ".jpg"):
        p = res("ui_iconos", name + ext)
        if os.path.isfile(p):
            try:
                with Image.open(p) as im:
                    pil = im.convert("RGBA")
                w, h = size
                r = max(w / pil.width, h / pil.height)
                pil = pil.resize((max(1, int(pil.width * r)), max(1, int(pil.height * r))), Image.Resampling.LANCZOS)
                x, y = (pil.width - w) // 2, (pil.height - h) // 2
                pil = pil.crop((x, y, x + w, y + h))
                return ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
            except Exception:
                return None
    return None


def match(text):
    """(icono, texto sin emoji) para el texto de un botón, o None."""
    text = (text or "").strip()
    hit = BY_TEXT.get(text)
    if hit:
        return hit
    for emo, name in BY_EMOJI.items():
        if text.startswith(emo + " ") or text.startswith(emo + "\ufe0f "):
            return name, text[len(emo):].lstrip("\ufe0f ").strip()
    return None


_installed = False


def _in_scope(w):
    """El tema solo se aplica dentro de las ventanas del Estudio (marcadas con _tema_iconos). Dentro de Audio
    Novela, los botones del resto de la app se quedan como estaban."""
    while w is not None:
        if getattr(w, "_tema_iconos", False):
            return True
        w = getattr(w, "master", None)
    return False


def install():
    """Tema de botones para toda la app. Se llama una vez al arrancar, antes de crear la ventana."""
    global _installed
    if _installed:
        return
    _installed = True
    init0, conf0 = ctk.CTkButton.__init__, ctk.CTkButton.configure

    def init(self, master, *a, **kw):
        if not _in_scope(master):
            return init0(self, master, *a, **kw)
        text = kw.get("text", "")
        auto = False
        if kw.get("image") is None and isinstance(text, str):
            hit = match(text)
            img = icon(hit[0], BIG.get(hit[1], ICON)) if hit else None
            if img is not None:
                kw.update(image=img, text=hit[1], compound=kw.get("compound", "left"))
                auto = True
        kw.setdefault("corner_radius", 10)
        if kw.get("fg_color") == SURF3 and "border_width" not in kw:
            kw.update(border_width=1, border_color=EDGE)
        if kw.get("height") in (28, 30):
            kw["height"] = 32
        init0(self, master, *a, **kw)
        self._auto_icon = auto or kw.get("image") is None

    def configure(self, require_redraw=False, **kw):
        if "text" in kw and "image" not in kw and getattr(self, "_auto_icon", False):
            hit = match(str(kw["text"]))
            img = icon(hit[0], BIG.get(hit[1], ICON)) if hit else None
            kw["image"] = img
            if img is not None:
                kw["text"] = hit[1]
            require_redraw = True
        return conf0(self, require_redraw, **kw)

    ctk.CTkButton.__init__ = init
    ctk.CTkButton.configure = configure

    seg0 = ctk.CTkSegmentedButton.__init__

    def seg(self, master, *a, **kw):
        """Barras de opciones (1-2-3-4, Rápido/Exigente, categorías): más altas y redondeadas."""
        if not _in_scope(master):
            return seg0(self, master, *a, **kw)
        kw.setdefault("corner_radius", 10)
        kw["height"] = max(kw.get("height") or 0, 32)
        kw.setdefault("border_width", 3)
        seg0(self, master, *a, **kw)

    ctk.CTkSegmentedButton.__init__ = seg


def apply(widget, size=18):
    """Pone los iconos a todos los botones conocidos dentro de widget (y sus hijos)."""
    stack = [widget]
    while stack:
        w = stack.pop()
        try:
            stack.extend(w.winfo_children())
        except Exception:
            continue
        if not isinstance(w, ctk.CTkButton):
            continue
        try:
            text = str(w.cget("text")).strip()
        except Exception:
            continue
        hit = match(text)
        if not hit:
            continue
        img = icon(hit[0], BIG.get(hit[1], max(size, ICON)))
        if img is None:
            continue
        try:
            w.configure(image=img, text=hit[1], compound="left")
        except Exception:
            pass
