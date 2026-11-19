# -*- coding: utf-8 -*-
"""El Estudio se diseña a sí mismo: genera los iconos de la interfaz con su propio motor (Z-Image), sobre pantalla
verde, los recorta (BiRefNet + llave de color) y los deja en ui_iconos\\<nombre>.png (64 px, fondo transparente).

Uso:  .venv\\Scripts\\python.exe herramientas\\generar_iconos.py [nombre ...]   (sin nombres: todos)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import imagen_ia as ia                 # noqa: E402
from PIL import Image                  # noqa: E402

OUT = os.path.join(ROOT, "ui_iconos")
RAW = os.path.join(ROOT, "herramientas", "_crudos")
STYLE = ("A single minimalist glossy 3D app icon of {what}, bold simple rounded shapes, smooth gradient from bright "
         "cyan to violet with soft white highlights, centered with generous margin, perfectly isolated on a flat "
         "solid pure chroma key green background (#00ff00), no shadow on the background, no text, no letters, "
         "no frame, high quality UI icon.")
ICONS = {
    "crear": "a magic wand with three bright sparkles",
    "ejemplos": "a glowing light bulb",
    "editor": "a movie clapperboard",
    "atajos": "a computer keyboard key with a small lightning bolt",
    "referencia": "a paperclip attached to a small picture frame",
    "internet": "a glowing globe with orbit rings",
    "carpeta": "an open folder",
    "guardar": "a downward arrow into a tray, save symbol",
    "parecida": "two overlapping picture cards with a circular refresh arrow",
    "inspiracion": "four sparkling stars of different sizes",
    "galeria": "a stack of three picture frames with a small mountain and sun",
    "mas": "a rounded square with three dots",
}


def make(name, what, seed=11):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RAW, exist_ok=True)
    raw = os.path.join(RAW, name + ".png")
    cut = os.path.join(RAW, name + "_recorte.png")
    ia.generate(STYLE.format(what=what), raw, "Alta calidad (Z-Image Turbo)", (768, 768), "", seed=seed,
                negative="text, letters, watermark, frame, border, shadow, blurry")
    ia.cutout(raw, cut, "foto", screen="green")
    with Image.open(cut) as im:
        im = im.convert("RGBA")
    bb = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if bb:
        im = im.crop(bb)
    side = int(max(im.size) * 1.08)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(im, ((side - im.width) // 2, (side - im.height) // 2))
    sq.resize((128, 128), Image.Resampling.LANCZOS).save(os.path.join(OUT, name + ".png"))
    print("listo", name, flush=True)


if __name__ == "__main__":
    names = sys.argv[1:] or list(ICONS)
    ia.free_ollama_gpu()
    ia.start()
    for n in names:
        make(n, ICONS[n])
    # hoja de muestra sobre el fondo oscuro de la app, a tamaño real (22 px) y grande
    sheet = Image.new("RGB", (len(names) * 140, 200), (11, 15, 28))
    for i, n in enumerate(names):
        with Image.open(os.path.join(OUT, n + ".png")) as im:
            sheet.paste(im, (i * 140 + 6, 6), im)
            small = im.resize((22, 22), Image.Resampling.LANCZOS)
            sheet.paste(small, (i * 140 + 59, 160), small)
    sheet.save(os.path.join(RAW, "muestra.png"))
    print("MUESTRA", os.path.join(RAW, "muestra.png"))
