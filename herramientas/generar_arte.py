# -*- coding: utf-8 -*-
"""Ilustraciones de la interfaz (portada de Inspiración y zona vacía de «Mis imágenes»), dibujadas por el Estudio.
Uso:  .venv\\Scripts\\python.exe herramientas\\generar_arte.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import imagen_ia as ia                 # noqa: E402
from PIL import Image, ImageDraw, ImageFilter      # noqa: E402

OUT = os.path.join(ROOT, "ui_iconos")
BG = (21, 28, 46)                      # SURF2 de la app: la ilustración se funde con su recuadro

ART = {
    "portada": ((1344, 576), "Dreamy digital illustration of a magical artist studio floating among the stars: a glowing "
                "canvas on a wooden easel with streams of cyan and violet light and paint swirling out of it into "
                "the shape of small creatures, mountains and a castle, floating sparkles, deep dark navy blue "
                "background, soft volumetric glow, modern anime illustration, rich detail. No text, no letters."),
    "vacio": ((768, 768), "Minimalist digital illustration of an empty glowing picture frame floating in the center, "
              "soft cyan and violet light coming from inside the frame, a few small sparkles around it, plain dark "
              "navy blue background, clean and calm, modern UI empty state art. No text, no letters."),
}


def dark_to_alpha(im, lo=None, hi=None):
    """El fondo oscuro de la ilustración se vuelve transparente (los brillos y estrellas quedan): así se ve el
    fondo de la app detrás y no queda ningún recuadro. El nivel del fondo se MIDE en los bordes de la imagen."""
    import numpy as np
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    lum = a.max(axis=2)
    if lo is None:
        border = np.concatenate([lum[:12].ravel(), lum[-12:].ravel(), lum[:, :12].ravel(), lum[:, -12:].ravel()])
        bg = float(np.percentile(border, 90))
        lo, hi = bg + 10, bg + 70
    alpha = ((lum - lo) / (hi - lo)).clip(0, 1) * 255
    # bordes de la imagen siempre transparentes (sin línea recta)
    h, w = alpha.shape
    edge = min(h, w) * .06
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy]).astype(np.float32)
    alpha *= (dist / edge).clip(0, 1)
    out = np.dstack([a, alpha]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def fade_edges(im, frac=.12):
    """Bordes que se funden con el color del recuadro de la app (sin cortes rectos)."""
    w, h = im.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((int(w * frac), int(h * frac), int(w * (1 - frac)), int(h * (1 - frac))),
                                        int(min(w, h) * .12), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(min(w, h) * frac * .6))
    base = Image.new("RGB", (w, h), BG)
    base.paste(im.convert("RGB"), (0, 0), m)
    return base


def finish(name):
    raw = os.path.join(ROOT, "herramientas", "_crudos", name + ".png")
    with Image.open(raw) as im:
        out = dark_to_alpha(im)
    w = 900 if name == "portada" else 480          # se muestra pequeña: no hace falta guardarla enorme
    out = out.resize((w, int(out.height * w / out.width)), Image.Resampling.LANCZOS)
    out.save(os.path.join(OUT, name + ".png"), optimize=True)
    old = os.path.join(OUT, name + ".jpg")
    if os.path.isfile(old):
        os.remove(old)
    print("listo", name, flush=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if "--solo-acabado" in sys.argv:           # sin volver a dibujar: solo el fondo transparente
        for name in ART:
            finish(name)
        sys.exit(0)
    ia.free_ollama_gpu()
    ia.start()
    for name, (size, prompt) in ART.items():
        raw = os.path.join(ROOT, "herramientas", "_crudos", name + ".png")
        ia.generate(prompt, raw, "Alta calidad (Z-Image Turbo)", size, "", seed=21,
                    negative="text, letters, watermark, signature, frame border, blurry")
        finish(name)
