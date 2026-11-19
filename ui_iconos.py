# -*- coding: utf-8 -*-
"""Iconos e ilustraciones de la interfaz, dibujados por el propio Estudio (herramientas\\generar_iconos.py).

apply(widget): recorre la ventana y, según el texto de cada botón, le pone su icono y le quita el emoji.
Si un icono falta, el botón se queda con su emoji de siempre: nunca queda un botón vacío.
"""
import os
import sys

import customtkinter as ctk
from PIL import Image

# texto del botón (sin espacios a los lados) -> (icono, texto nuevo)
BY_TEXT = {
    "💡 Ejemplos y consejos": ("ejemplos", "Ejemplos y consejos"),
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
}
# cualquier otro botón que empiece con uno de estos emojis también recibe su icono (y pierde el emoji)
BY_EMOJI = {"🎨": "crear", "✨": "crear", "📁": "carpeta", "📂": "carpeta", "🖼": "galeria", "💾": "guardar",
            "🔎": "inspiracion", "🔍": "inspiracion", "👁": "inspiracion", "💡": "ejemplos", "🎬": "editor",
            "📎": "referencia", "🌐": "internet", "⌨": "atajos"}
_cache = {}


def res(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def icon(name, size=18):
    """CTkImage del icono (o None si no está)."""
    key = (name, size)
    if key in _cache:
        return _cache[key]
    p = res("ui_iconos", name + ".png")
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
        hit = BY_TEXT.get(text)
        if not hit:
            for emo, name in BY_EMOJI.items():
                if text.startswith(emo + " ") or text.startswith(emo + "️ "):
                    hit = (name, text[len(emo):].lstrip("️ ").strip())
                    break
        if not hit:
            continue
        img = icon(hit[0], size + (2 if text == "Crear imagen" else 0))
        if img is None:
            continue
        try:
            w.configure(image=img, text=hit[1], compound="left")
        except Exception:
            pass
