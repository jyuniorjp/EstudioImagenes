# -*- coding: utf-8 -*-
"""Motor de miniaturas (YouTube) por capas. Solo PIL: lo usan el editor y las pruebas.

Un proyecto es un dict guardable en JSON. Todas las posiciones y tamaños son relativos (0..1) al lienzo, así el
mismo diseño se dibuja nítido a cualquier tamaño (vista previa chica, PNG final grande).

    proyecto = {"size": [1280, 720], "fx": {...}, "layers": [capa, capa, ...]}   (la primera capa queda al fondo)
    capa imagen: {"kind": "image", "path": ..., "cover": True|False, "x": .5, "y": .5, "h": 1.0, "flip": False,
                  "glow": "#22d3ee"|"", "glow_size": .5, "frame": ""|"#22d3ee", "badge": ""|"#1", "opacity": 1}
    capa texto:  {"kind": "text", "text": "DIOS *DRAGÓN*", "style": "Impacto", "x": .04, "y": .05, "size": .17,
                  "align": "left"|"center"|"right", "max_w": .9}
                  (lo que va entre *asteriscos* sale con el color de acento del estilo)
"""
import os
import random
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


def _res(*p):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), *p)


FONTS = {
    "anton": ("fuentes/Anton-Regular.ttf", None, r"C:\Windows\Fonts\impact.ttf"),
    "bebas": ("fuentes/BebasNeue-Regular.ttf", None, r"C:\Windows\Fonts\impact.ttf"),
    "cinzel_deco": ("fuentes/CinzelDecorative-Black.ttf", None, r"C:\Windows\Fonts\georgiab.ttf"),
    "cinzel": ("fuentes/Cinzel[wght].ttf", b"Bold", r"C:\Windows\Fonts\georgiab.ttf"),
    "montserrat": ("fuentes/Montserrat[wght].ttf", b"Black", r"C:\Windows\Fonts\arialbd.ttf"),
    "bangers": ("fuentes/Bangers-Regular.ttf", None, r"C:\Windows\Fonts\impact.ttf"),
}
_font_cache = {}


def font(key, px):
    k = (key, int(px))
    if k in _font_cache:
        return _font_cache[k]
    path, var, fallback = FONTS.get(key, FONTS["anton"])
    try:
        f = ImageFont.truetype(_res(*path.split("/")), int(px))
        if var:
            try:
                f.set_variation_by_name(var)
            except Exception:
                pass
    except Exception:
        f = ImageFont.truetype(fallback, int(px))
    _font_cache[k] = f
    return f


# estilos de texto: fill/accent = color "#rrggbb" o degradado [(pos, "#color"), ...] de arriba a abajo
GOLD = [(0, "#fff7c2"), (0.45, "#f6c445"), (0.62, "#d18f1c"), (1, "#7a4b0c")]
RED_METAL = [(0, "#ff8a7a"), (0.45, "#e0261f"), (1, "#6a0708")]
CHROME = [(0, "#ffffff"), (0.38, "#d7dae0"), (0.5, "#7c818c"), (0.56, "#f2f3f6"), (1, "#8d939e")]
STYLES = {
    "Impacto": dict(font="anton", fill="#ffffff", accent="#ef1b1b", stroke="#000000", stroke_w=.075,
                    glow="#ff8c1a", glow_r=.16, glow_a=1.0, upper=True),
    "Aura roja": dict(font="anton", fill="#ffffff", accent="#ff3030", stroke="#000000", stroke_w=.06,
                      glow="#ff1010", glow_r=.22, glow_a=1.6, upper=True),
    "Oro y rojo": dict(font="anton", fill=GOLD, accent=RED_METAL, stroke="#2a1306", stroke_w=.07,
                       stroke2="#f3c35a", stroke2_w=.022, shadow="#000000", shadow_off=.05, upper=True),
    "Cromo épico": dict(font="cinzel_deco", fill=CHROME, accent=RED_METAL, stroke="#4a0606", stroke_w=.045,
                        glow="#ff1a1a", glow_r=.12, glow_a=.9, bevel=True, shadow="#000000", shadow_off=.03),
    "Neón": dict(font="bebas", fill="#f4fdff", accent="#ff4fd8", stroke="#22d3ee", stroke_w=.025,
                 glow="#22d3ee", glow_r=.2, glow_a=1.8, upper=True),
    "Elegante": dict(font="cinzel", fill="#ffffff", accent="#f6c445", stroke="", stroke_w=0, shadow="#000000",
                     shadow_off=.04, shadow_blur=.08, tracking=.08, upper=True),
    "Cómic": dict(font="bangers", fill="#ffe14d", accent="#ff4d4d", stroke="#000000", stroke_w=.07,
                  shadow="#000000", shadow_off=.07, shadow_blur=0.0, upper=True),
}


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _paint(fill, size):
    """Capa RGB del relleno: color liso o degradado vertical."""
    w, h = size
    if isinstance(fill, str):
        return Image.new("RGB", size, _rgb(fill))
    col = Image.new("RGB", (1, 256))
    stops = [(p, _rgb(c)) for p, c in fill]
    for y in range(256):
        t = y / 255
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= t <= p1:
                k = (t - p0) / max(1e-6, p1 - p0)
                col.putpixel((0, y), tuple(int(a + (b - a) * k) for a, b in zip(c0, c1)))
                break
    return col.resize((w, h), Image.Resampling.BILINEAR)


def _segments(text):
    """«DIOS *DRAGÓN*» -> [("DIOS ", False), ("DRAGÓN", True)]"""
    out = []
    for i, part in enumerate(re.split(r"\*", text)):
        if part:
            out.append((part, i % 2 == 1))
    return out or [("", False)]


def _render_lines(layer, W, H):
    """Título en varias líneas (texto con saltos de línea): cada línea con sus efectos, apiladas."""
    parts = []
    for line in [x for x in layer.get("text", "").split("\n") if x.strip()]:
        im, _x, _y = render_text(dict(layer, text=line, x=0, y=0, align="left"), W, H)
        bb = im.getchannel("A").getbbox()
        parts.append(im.crop(bb) if bb else im)
    if not parts:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), 0, 0
    gap = -int(min(p.height for p in parts) * .22)           # un poco encimadas, como en las miniaturas
    w = max(p.width for p in parts)
    h = sum(p.height for p in parts) + gap * (len(parts) - 1)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    align = layer.get("align", "left")
    y = 0
    for p in parts:
        x = (w - p.width) // 2 if align == "center" else (w - p.width if align == "right" else 0)
        out.alpha_composite(p, (x, max(0, y)))
        y += p.height + gap
    ax = layer.get("x", .05) * W - (w / 2 if align == "center" else w if align == "right" else 0)
    return out, int(ax), int(layer.get("y", .05) * H)


def render_text(layer, W, H):
    """Devuelve (imagen RGBA, x, y) de una capa de texto ya con efectos. La capa puede cambiar los colores del
    estilo con fill / stroke / stroke_w / accent / glow (p. ej. «letras blancas con borde naranja grueso»)."""
    if "\n" in layer.get("text", ""):
        return _render_lines(layer, W, H)
    st = dict(STYLES.get(layer.get("style"), STYLES["Impacto"]))
    for k in ("fill", "stroke", "accent", "glow"):
        if layer.get(k):
            st[k] = layer[k]
    if layer.get("stroke_w") is not None:
        st["stroke_w"] = float(layer["stroke_w"])
        if layer.get("stroke"):
            st.pop("stroke2", None)
            st.pop("stroke2_w", None)
    text = layer.get("text", "")
    if st.get("upper"):
        text = text.upper()
    px = max(8, layer.get("size", .15) * H)
    max_w = layer.get("max_w", .92) * W
    for _ in range(12):                                       # se achica sola si no cabe
        f = font(st["font"], px)
        track = st.get("tracking", 0) * px
        segs = _segments(text)
        widths = [sum(f.getlength(ch) + track for ch in s) if track else f.getlength(s) for s, _a in segs]
        tw = sum(widths)
        if tw <= max_w or px < 12:
            break
        px *= max(0.6, max_w / tw * 0.98)
    sw = int(round(st.get("stroke_w", 0) * px))
    sw2 = int(round(st.get("stroke2_w", 0) * px))
    glow_r = st.get("glow_r", 0) * px
    pad = int(sw + sw2 + glow_r * 2.2 + st.get("shadow_off", 0) * px + st.get("shadow_blur", .02) * px * 2 + 6)
    asc, desc = f.getmetrics()
    w, h = int(tw + pad * 2 + sw * 2), int(asc + desc + pad * 2)
    m_norm, m_acc, m_stroke = (Image.new("L", (w, h), 0) for _ in range(3))
    d_n, d_a, d_s = ImageDraw.Draw(m_norm), ImageDraw.Draw(m_acc), ImageDraw.Draw(m_stroke)
    x = pad + sw
    for (s, acc), sw_w in zip(segs, widths):
        chars = list(s) if track else [s]
        cx = x
        for ch in chars:
            (d_a if acc else d_n).text((cx, pad), ch, font=f, fill=255)
            if sw or sw2:
                d_s.text((cx, pad), ch, font=f, fill=255, stroke_width=sw + sw2, stroke_fill=255)
            cx += f.getlength(ch) + track if track else 0
        x += sw_w
    m_fill = ImageChops.lighter(m_norm, m_acc)
    if not (sw or sw2):
        m_stroke = m_fill
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if st.get("glow"):                                          # resplandor exterior en dos capas
        g = Image.new("RGBA", (w, h), _rgb(st["glow"]) + (0,))
        a1 = m_stroke.filter(ImageFilter.GaussianBlur(glow_r))
        a2 = m_stroke.filter(ImageFilter.GaussianBlur(glow_r / 3.5))
        a = ImageChops.add(a1, a2).point(lambda v: min(255, int(v * st.get("glow_a", 1))))
        g.putalpha(a)
        out.alpha_composite(g)
    if st.get("shadow"):
        off = int(st.get("shadow_off", .04) * px)
        sh = Image.new("RGBA", (w, h), _rgb(st["shadow"]) + (0,))
        a = ImageChops.offset(m_stroke, off, off)
        blur = st.get("shadow_blur", .02) * px
        if blur:
            a = a.filter(ImageFilter.GaussianBlur(blur))
        sh.putalpha(a.point(lambda v: int(v * .85)))
        out.alpha_composite(sh)
    if sw2:                                                      # borde exterior (dorado en «Oro y rojo»)
        o2 = Image.new("RGBA", (w, h), _rgb(st.get("stroke2", "#000000")) + (0,))
        o2.putalpha(m_stroke)
        out.alpha_composite(o2)
        inner = Image.new("L", (w, h), 0)
        di = ImageDraw.Draw(inner)
        x = pad + sw
        for (s, acc), sw_w in zip(segs, widths):
            di.text((x, pad), s, font=f, fill=255, stroke_width=sw, stroke_fill=255)
            x += sw_w
        o1 = Image.new("RGBA", (w, h), _rgb(st["stroke"]) + (0,))
        o1.putalpha(inner)
        out.alpha_composite(o1)
    elif sw:
        o1 = Image.new("RGBA", (w, h), _rgb(st["stroke"]) + (0,))
        o1.putalpha(m_stroke)
        out.alpha_composite(o1)
    for mask, fill in ((m_norm, st["fill"]), (m_acc, st.get("accent", st["fill"]))):
        if mask.getbbox():
            bb = m_fill.getbbox() or (0, 0, w, h)
            paint = Image.new("RGB", (w, h))
            paint.paste(_paint(fill, (w, max(1, bb[3] - bb[1]))), (0, bb[1]))
            lay = paint.convert("RGBA")
            lay.putalpha(mask)
            out.alpha_composite(lay)
    if st.get("bevel"):                                          # brillo en el borde de arriba (metal)
        k = max(1, int(px * .025))
        edge = ImageChops.subtract(m_fill, ImageChops.offset(m_fill, 0, k)).filter(ImageFilter.GaussianBlur(k / 2))
        hi = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        hi.putalpha(edge.point(lambda v: int(v * .8)))
        out.alpha_composite(hi)
    align = layer.get("align", "left")
    ax = layer.get("x", .05) * W
    if align == "center":
        ax -= w / 2
    elif align == "right":
        ax -= w
    else:
        ax -= pad + sw
    ay = layer.get("y", .05) * H - pad
    return out, int(ax), int(ay)


_img_cache = {}


def _load(path):
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    k = (path, mt)
    if k not in _img_cache:
        if len(_img_cache) > 24:
            _img_cache.clear()
        try:
            with Image.open(path) as im:
                _img_cache[k] = im.convert("RGBA")
        except Exception:
            return None
    return _img_cache[k]


def _adjust(im, layer, H):
    """Ajustes de la capa: brillo, contraste, saturación y desenfoque (el fondo desenfocado da profundidad)."""
    from PIL import ImageEnhance
    b, c, s, bl = (layer.get(k) for k in ("bright", "contrast", "sat", "blur"))
    if not any(v not in (None, 0, 1, 1.0) for v in (b, c, s)) and not bl:
        return im
    rgba = im.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")
    if bl:
        rgb = rgb.filter(ImageFilter.GaussianBlur(float(bl) * H / 720))
    for val, enh in ((b, ImageEnhance.Brightness), (c, ImageEnhance.Contrast), (s, ImageEnhance.Color)):
        if val not in (None, 0, 1, 1.0):
            rgb = enh(rgb).enhance(float(val))
    rgb.putalpha(alpha)
    return rgb


def render_image(layer, W, H):
    src = _load(layer.get("path", ""))
    if src is None:
        return None, 0, 0
    if layer.get("cover"):                                      # fondo: llena el lienzo sin deformar
        k = max(W / src.width, H / src.height)
        im = src.resize((max(1, int(src.width * k)), max(1, int(src.height * k))), Image.Resampling.LANCZOS)
        ox = int((im.width - W) * layer.get("x", .5))
        oy = int((im.height - H) * layer.get("y", .5))
        im = im.crop((ox, oy, ox + W, oy + H))
        if layer.get("flip"):
            im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        return _adjust(im, layer, H), 0, 0
    th = max(4, int(layer.get("h", .9) * H))
    tw = max(4, int(src.width * th / src.height))
    im = src.resize((tw, th), Image.Resampling.LANCZOS)
    if layer.get("flip"):
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    im = _adjust(im, layer, H)
    if layer.get("frame"):                                      # tarjeta con borde de neón y número
        r = int(min(tw, th) * .06)
        mask = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw - 1, th - 1), r, fill=255)
        im.putalpha(ImageChops.multiply(im.split()[3], mask))
        bw = max(2, int(H * .006))
        border = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(border).rounded_rectangle((0, 0, tw - 1, th - 1), r, outline=_rgb(layer["frame"]) + (255,),
                                                 width=bw)
        im.alpha_composite(border)
        if layer.get("badge"):
            bf = font("anton", th * .2)
            t = layer["badge"]
            bwid = int(bf.getlength(t) + th * .12)
            bh = int(th * .26)
            badge = Image.new("RGBA", (bwid, bh), (120, 14, 18, 235))
            ImageDraw.Draw(badge).text((th * .06, bh * .02), t, font=bf, fill=(255, 255, 255, 255))
            im.alpha_composite(badge, (tw - bwid - int(th * .03), int(th * .03)))
    pad = 0
    glow = layer.get("glow") or layer.get("frame")
    if glow:                                                    # borde de luz alrededor de la silueta
        rad = max(2, layer.get("glow_size", .5) * H * .03)
        pad = int(rad * 3)
        big = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        a = Image.new("L", big.size, 0)
        a.paste(im.split()[3], (pad, pad))
        g1 = a.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(rad))
        g2 = a.filter(ImageFilter.GaussianBlur(rad / 3))
        gl = Image.new("RGBA", big.size, _rgb(glow) + (0,))
        gl.putalpha(ImageChops.add(g1, g2).point(lambda v: min(255, int(v * 1.3))))
        big.alpha_composite(gl)
        big.alpha_composite(im, (pad, pad))
        im = big
    op = layer.get("opacity", 1.0)
    if op < 1:
        im.putalpha(im.split()[3].point(lambda v: int(v * op)))
    cx, cy = layer.get("x", .5) * W, layer.get("y", .5) * H
    return im, int(cx - im.width / 2), int(cy - im.height / 2)


def _shade(W, H, side, amount):
    """Degradado oscuro detrás del texto (izquierda, derecha, arriba o abajo) para que siempre se lea."""
    g = Image.linear_gradient("L")                                 # 0 arriba -> 255 abajo
    if side == "left":
        g = g.rotate(270)                                          # 255 a la izquierda (antes quedaba al revés)
    elif side == "right":
        g = g.rotate(90)                                           # 255 a la derecha
    elif side == "top":
        g = g.rotate(180)
    g = g.resize((W, H)).point(lambda v: int(v * amount) if v > 40 else 0)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.putalpha(g)
    return sh


def _vignette(W, H, amount):
    m = Image.radial_gradient("L").resize((W, H)).point(lambda v: int(max(0, v - 90) * amount * 1.6))
    v = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    v.putalpha(m.filter(ImageFilter.GaussianBlur(W / 40)))
    return v


def _embers(W, H, color, amount, seed=7):
    rnd = random.Random(seed)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    c = _rgb(color)
    for _ in range(int(140 * amount)):
        x, y = rnd.random() * W, rnd.random() * H
        r = (0.6 + rnd.random() * 2.2) * H / 720
        if rnd.random() < .25:                                       # algunas alargadas, como chispas
            ang = rnd.uniform(-.9, -.3)
            L = r * rnd.uniform(4, 9)
            d.line((x, y, x + L, y + L * ang), fill=c + (230,), width=max(1, int(r)))
        else:
            d.ellipse((x - r, y - r, x + r, y + r), fill=c + (235,))
    glow = lay.filter(ImageFilter.GaussianBlur(3 * H / 720))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(glow)
    out.alpha_composite(lay)
    return out


def render(project, W=None, H=None, boxes=None):
    """Dibuja el proyecto. boxes (lista) recibe (índice de capa, x0, y0, x1, y1) relativos, para tocar y mover."""
    W = int(W or project.get("size", [1280, 720])[0])
    H = int(H or project.get("size", [1280, 720])[1])
    fx = project.get("fx", {})
    canvas = Image.new("RGBA", (W, H), _rgb(fx.get("bg", "#0b0f1a")) + (255,))
    layers = project.get("layers", [])
    first_text = next((i for i, l in enumerate(layers) if l.get("kind") == "text"), len(layers))
    for i, l in enumerate(layers):
        if i == first_text:                                          # efectos entre el arte y el texto
            if fx.get("embers"):
                canvas.alpha_composite(_embers(W, H, fx.get("embers_color", "#ff7a1a"), fx["embers"]))
            if fx.get("vignette"):
                canvas.alpha_composite(_vignette(W, H, fx["vignette"]))
            if fx.get("shade"):
                canvas.alpha_composite(_shade(W, H, fx.get("shade_side", "left"), fx["shade"]))
        try:
            im, x, y = (render_text if l.get("kind") == "text" else render_image)(l, W, H)
        except Exception:
            im = None
        if im is None:
            continue
        canvas.alpha_composite(im, (x, y)) if 0 <= x and 0 <= y and x + im.width <= W and y + im.height <= H \
            else _paste_clip(canvas, im, x, y)
        if boxes is not None:
            a = im.split()[3].getbbox() or (0, 0, im.width, im.height)
            boxes.append((i, (x + a[0]) / W, (y + a[1]) / H, (x + a[2]) / W, (y + a[3]) / H))
    if first_text == len(layers):
        if fx.get("embers"):
            canvas.alpha_composite(_embers(W, H, fx.get("embers_color", "#ff7a1a"), fx["embers"]))
        if fx.get("vignette"):
            canvas.alpha_composite(_vignette(W, H, fx["vignette"]))
    if fx.get("autolevel") or fx.get("pop_contrast") or fx.get("pop_sat"):   # «pop» final, como en YouTube
        from PIL import ImageEnhance, ImageOps
        rgb = canvas.convert("RGB")
        if fx.get("autolevel"):                  # niveles automáticos: estira las sombras y las luces (más punch)
            rgb = Image.blend(rgb, ImageOps.autocontrast(rgb, cutoff=float(fx.get("autolevel_cut", 1.0))),
                              min(1.0, float(fx["autolevel"])))
        if fx.get("pop_contrast"):
            rgb = ImageEnhance.Contrast(rgb).enhance(1 + float(fx["pop_contrast"]))
        if fx.get("pop_sat"):
            rgb = ImageEnhance.Color(rgb).enhance(1 + float(fx["pop_sat"]))
        canvas = rgb.convert("RGBA")
    return canvas


def _paste_clip(canvas, im, x, y):
    """alpha_composite no admite posiciones fuera del lienzo: se recorta lo que sobresale."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.width, x + im.width), min(canvas.height, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    canvas.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def export_png(project, path, W, H):
    """PNG sin pérdida. Devuelve (ruta, bytes). Si pesa más de 2 MB (límite de YouTube), guarda además un JPG."""
    img = render(project, W, H).convert("RGB")
    part = path + ".part.png"
    img.save(part, optimize=True)
    os.replace(part, path)
    size = os.path.getsize(path)
    extra = ""
    if size > 2 * 1024 * 1024:
        extra = os.path.splitext(path)[0] + "_youtube.jpg"
        img.save(extra, quality=95, subsampling=0)
    return path, size, extra


# ------------------------------------------------------------------ guardar en el formato que se elija
SAVE_TYPES = [("PNG (sin pérdida)", "*.png"), ("JPG", "*.jpg"), ("WEBP", "*.webp"), ("BMP", "*.bmp"),
              ("TIFF", "*.tif")]
EXT_BY_NAME = {"PNG": ".png", "JPG": ".jpg", "WEBP": ".webp", "BMP": ".bmp", "TIFF": ".tif"}


def save_image(img, path, quality=95):
    """Guarda según la extensión. PNG/TIFF/BMP sin pérdida; JPG y WEBP con calidad alta (WEBP 100 = sin pérdida)."""
    ext = os.path.splitext(path)[1].lower()
    part = path + ".part" + (ext or ".png")
    if ext in (".jpg", ".jpeg"):
        img.convert("RGB").save(part, "JPEG", quality=quality, subsampling=0, optimize=True)
    elif ext == ".webp":
        img.save(part, "WEBP", lossless=quality >= 100, quality=quality, method=6)
    elif ext == ".bmp":
        img.convert("RGB").save(part, "BMP")
    elif ext in (".tif", ".tiff"):
        img.save(part, "TIFF", compression="tiff_lzw")
    else:
        img.save(part, "PNG", optimize=True)
    os.replace(part, path)
    return path
