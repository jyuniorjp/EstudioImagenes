# -*- coding: utf-8 -*-
"""Quita el fondo de una imagen (deja PNG con transparencia). Lo ejecuta el Python de ComfyUI:

    python_embeded\\python.exe -s quitar_fondo.py entrada.png salida.png modelo.onnx [blanco]

Modelos IS-Net (rembg): isnet-anime (personajes de anime) e isnet-general-use (fotos reales).
«verde» / «azul» / «magenta»: se dibujó sobre pantalla de ese color: se borra el color que toca los bordes y
su reflejo en el contorno (como la pantalla verde del cine).
«blanco»: la imagen se dibujó sobre fondo blanco (personajes de la IA): además se borra todo el blanco que toca los
bordes, como un bote de pintura desde afuera.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter


def _white_from_edges(im):
    """Máscara (255 = fondo) del blanco o casi blanco conectado con los bordes."""
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    near = ((a.min(axis=2) > 222) & ((a.max(axis=2) - a.min(axis=2)) < 28)).astype(np.uint8) * 255
    return _flood_edges(Image.fromarray(near))


SCREENS = ("verde", "azul", "magenta")


def screen_mask(a, screen):
    """Dónde está la pantalla de color (True), midiendo su color REAL en los bordes de la imagen: la IA no pinta un
    verde puro (a veces sale verde menta). a: arreglo RGB int16."""
    import numpy as np
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    if screen == "blue":
        fam = b - np.maximum(r, g) > 12
    elif screen == "magenta":
        fam = np.minimum(r, b) - g > 15
    elif screen == "green":
        fam = g - np.maximum(r, b) > 12
    else:
        fam = (a.min(axis=2) > 200) & ((a.max(axis=2) - a.min(axis=2)) < 35)
    border = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3),
                             a[:, -4:].reshape(-1, 3)])
    bfam = np.concatenate([fam[:4].ravel(), fam[-4:].ravel(), fam[:, :4].ravel(), fam[:, -4:].ravel()])
    if bfam.mean() < .2:                       # casi no hay pantalla en los bordes: solo la regla de color
        return fam
    ref = np.median(border[bfam], axis=0)
    dist = np.sqrt(((a - ref) ** 2).sum(axis=2))
    return fam & (dist < 60) | (dist < 28)


def _screen_from_edges(im, screen):
    """Máscara (255 = fondo) del color de la pantalla (verde, azul o magenta) conectado con los bordes."""
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    near = screen_mask(a, {"azul": "blue", "magenta": "magenta"}.get(screen, "green"))
    return _flood_edges(Image.fromarray(near.astype(np.uint8) * 255))


def _despill(out, mask, screen="verde"):
    """Quita el reflejo del color de la pantalla en el borde del personaje (sin tocar lo de adentro)."""
    edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask.filter(ImageFilter.MinFilter(9)))
    a = np.asarray(out).astype(np.int16).copy()
    e = np.asarray(edge) > 0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    if screen == "azul":
        lim = np.maximum(r, g)
        a[..., 2] = np.where(e & (b > lim), lim, b)
    elif screen == "magenta":
        cap = g + 20
        a[..., 0] = np.where(e & (np.minimum(r, b) > cap), np.maximum(cap, r - (np.minimum(r, b) - cap)), r)
        a[..., 2] = np.where(e & (np.minimum(r, b) > cap), np.maximum(cap, b - (np.minimum(r, b) - cap)), b)
    else:
        lim = np.maximum(r, b)
        a[..., 1] = np.where(e & (g > lim), lim, g)
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), out.mode)


def _flood_edges(m):
    w, h = m.size
    step = max(4, min(w, h) // 120)
    for x in range(0, w, step):
        for y in (0, h - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    for y in range(0, h, step):
        for x in (0, w - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    return m.point(lambda v: 255 if v == 128 else 0).filter(ImageFilter.MaxFilter(3))


def _edge_fade(w, h, frac=0.16):
    """Atenúa suavemente los lados y el borde de arriba (abajo no: ahí suele cortarse el cuerpo)."""
    fx, fy = max(2, int(w * frac)), max(2, int(h * frac))
    col = np.minimum(np.arange(w) / fx, (w - 1 - np.arange(w)) / fx).clip(0, 1)
    row = (np.arange(h) / fy).clip(0, 1)
    return Image.fromarray((np.outer(row, col) * 255).astype(np.uint8))


def cut(src, dst, model, white=False, size=1024, screen=""):
    import onnxruntime as ort
    im = Image.open(src).convert("RGB")
    birefnet = "birefnet" in os.path.basename(model).lower()
    x = np.asarray(im.resize((size, size), Image.Resampling.LANCZOS), dtype=np.float32) / 255.0
    if birefnet:            # BiRefNet: normalización de ImageNet y salida en «logits»
        x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
    else:
        x = (x - 0.5) / 1.0
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])
    pred = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    if birefnet:
        pred = 1.0 / (1.0 + np.exp(-pred))
    else:
        mi, ma = float(pred.min()), float(pred.max())
        pred = (pred - mi) / max(1e-6, ma - mi)
    mask = Image.fromarray((pred * 255).clip(0, 255).astype(np.uint8)).resize(im.size, Image.Resampling.LANCZOS)
    # sin «neblina»: lo casi transparente se borra (si no, el borde de luz ilumina un rectángulo)
    mask = mask.point(lambda v: 0 if v < 48 else (255 if v > 200 else int((v - 48) * 255 / 152)))
    if screen in SCREENS:     # pantalla de color: lo que toca los bordes con ese color es fondo seguro
        mask = ImageChops.subtract(mask, _screen_from_edges(im, screen))
    elif white:
        mask = ImageChops.subtract(mask, _white_from_edges(im))
    # BiRefNet ya separa bien: solo un borde finito (antes se atenuaba un 16 % de cada lado y se comía espadas)
    mask = ImageChops.multiply(mask, _edge_fade(*im.size, frac=0.03 if birefnet else 0.16))
    mask = mask.filter(ImageFilter.GaussianBlur(0.6))
    out = im.convert("RGBA")
    out.putalpha(mask)
    if screen in SCREENS:
        out = _despill(out, mask, screen)
    bbox = mask.point(lambda v: 255 if v > 10 else 0).getbbox()
    if bbox:                                   # sin bordes vacíos: más fácil de colocar
        out = out.crop(bbox)
    out.save(dst)


if __name__ == "__main__":
    mode = sys.argv[4] if len(sys.argv) > 4 else ""
    cut(sys.argv[1], sys.argv[2], sys.argv[3], white=mode == "blanco", screen=mode)
    print("OK")
