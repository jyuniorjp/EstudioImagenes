# -*- coding: utf-8 -*-
"""Miniatura automática por capas a partir de un solo prompt.

1. Tu IA (Qwen) divide el pedido: fondo (sin personas), personajes (cada uno con su lugar), título y estilo.
2. Se dibuja el fondo en horizontal y cada personaje aparte, de cuerpo entero sobre fondo blanco.
3. A cada personaje se le quita el fondo (PNG transparente), se le ajusta el color a la luz del fondo y se le
   pone luz de borde: así no parece una imagen pegada encima de otra.
4. Se arma el proyecto por capas (editable en el editor de miniaturas) con el título en letras perfectas.
"""
import datetime
import json
import os
import re

from PIL import Image, ImageStat

import imagen_ia as ia
import miniaturas as M

WORK = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioNovelaStudio", "miniaturas_tmp")
_THUMB_W = ("miniatura", "thumbnail", "portada de youtube", "miniatura de youtube")


def is_thumbnail_request(text):
    t = (text or "").lower()
    return any(w in t for w in _THUMB_W)


def thumb_plan(text, model=None, saved_names=()):
    """Divide el pedido en capas. Devuelve dict: background, characters[], title, subtitle, title_style, glow,
    embers. Sin Ollama hace un plan simple (todo al fondo y el texto entre comillas como título)."""
    model = model if model is not None else ia.ollama_model()
    title = ia._quoted(text)
    spec = ia.title_spec(text)             # lo que pediste del título: lado, color de letras y de borde
    base = {"background": "", "characters": [], "title": title, "subtitle": "", "title_style": spec["style"],
            "title_spec": spec, "glow": "", "embers": False,
            "anime": "anime" in text.lower() or "manhwa" in text.lower()}
    if not model:
        base["background"] = ia.to_english(text, "") + ", no people"
        return base
    sys_p = (
        "You plan a YouTube thumbnail made of separate layers. Read the user's request (often Spanish) and answer "
        "ONLY with JSON: {"
        "\"background\": English prompt for the BACKGROUND ONLY (setting, sky, weather, light, colors, big creatures or "
        "objects that are part of the scenery like a dragon in the sky; if the user says a creature is gigantic or "
        "huge, describe it as enormous and filling a big part of the frame; keep every creature's MATERIAL, SHAPE "
        "and COLORS exactly as the user wrote and say they keep those colors under the scene light, e.g. a crystal "
        "dragon = one solid dragon sculpted from translucent icy-blue crystal glowing from inside, not a mosaic, not "
        "stained glass), NO people, NO main characters, keep the area where the title goes simple, max 120 words; "
        "\"background_must\": 2-5 very short English checks a viewer can verify in the background picture "
        "taken ONLY from this user's request (never invent or copy anything else); "
        "\"characters\": list (max 3) of the MAIN foreground figures, each {\"desc\": English description of the "
        "figure (gender, age, hair, eyes, clothes, armor, weapon, pose, expression, effects like aura), max 70 "
        "words, \"tags\": Danbooru tags for an anime model starting with 1girl or 1boy, solo, \"gender\": \"male\" or "
        "\"female\" or \"\", \"name\": famous character name or \"\", \"series\": its anime/game or \"\", "
        "\"position\": \"left\" or \"right\" or \"center\" (exactly where the user put it), \"size\": \"large\" or \"medium\", "
        "\"must\": 2-5 very short English checks for this figure, gender first, taken ONLY from what the user "
        "wrote about this figure}; [] if there is no "
        "main figure; "
        "\"title\": the title text the user wants written (exact words) or \"\"; \"subtitle\": second smaller text or "
        "\"\"; \"style\": one of \"Impacto\", \"Aura roja\", \"Oro y rojo\", \"Cromo épico\", \"Neón\", \"Elegante\", "
        "\"Cómic\" that best matches the requested lettering; \"glow\": hex color of the main light of the scene "
        "(for rim light), e.g. \"#ff5a1a\"; \"embers\": true if there is fire, sparks or embers; \"anime\": true if "
        "anime/manga/manhwa style}. Do not invent characters the user did not ask for.")
    try:
        extra = ("\nSaved characters available (if the user mentions one, list it in characters with \"name\" exactly "
                 "as written here): " + ", ".join(saved_names)) if saved_names else ""
        raw = ia._ollama(sys_p, text + extra, model, timeout=120, fmt="json")
        d = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    except Exception:
        d = {}
    out = dict(base)
    if d.get("background"):
        out["background"] = str(d["background"])
    else:
        out["background"] = ia.to_english(text, model) + ", no people"
    out["background_must"] = ia.relevant_checks(
        [str(x) for x in d.get("background_must") or [] if str(x).strip()][:5]
        if isinstance(d.get("background_must"), list) else [], out["background"], text)
    chars = d.get("characters") if isinstance(d.get("characters"), list) else []
    out["characters"] = [c for c in chars if isinstance(c, dict) and (c.get("desc") or c.get("tags"))][:3]
    for c in out["characters"]:
        c["must"] = ia.relevant_checks([str(x) for x in c.get("must") or [] if str(x).strip()][:5]
                                       if isinstance(c.get("must"), list) else [],
                                       c.get("desc", ""), c.get("tags", ""), text)
        for k in ("desc", "tags", "name", "series", "gender", "position", "size"):
            if isinstance(c.get(k), list):
                c[k] = ", ".join(str(x) for x in c[k])
            elif c.get(k) is not None and not isinstance(c.get(k), str):
                c[k] = str(c[k])
    low = text.lower()
    saved_low = {x.lower() for x in saved_names}
    for c in out["characters"]:                 # nombres inventados por la IA no se buscan en internet
        if c.get("name") and str(c["name"]).lower() not in low and str(c["name"]).lower() not in saved_low:
            c["name"], c["series"] = "", ""
    if d.get("title") and not title:
        out["title"] = str(d["title"])[:60]
    out["subtitle"] = str(d.get("subtitle") or "")[:60]
    if d.get("style") in M.STYLES and spec["style"] == "Impacto" and not (spec["fill"] or spec["stroke"]):
        out["title_style"] = d["style"]          # si dijiste cómo son las letras, manda lo tuyo
    for c in out["characters"]:                 # el género lo fija lo que TÚ escribiste, no la IA
        g = ia.gender_of(c.get("desc", "")) or (ia.gender_of(text) if len(out["characters"]) == 1 else "")
        if g:
            c["gender"] = g
            want = "a woman" if g == "female" else "a man"          # el género siempre se revisa
            c["must"] = [want] + [m for m in c.get("must", []) if not re.search(
                r"\b(woman|man|girl|boy|female|male)\b", m.lower())][:4]
        if not c.get("position") or str(c["position"]).lower() not in ("left", "right", "center"):
            c["position"] = {"right": "left", "left": "right"}.get(spec["position"], "")
    g = str(d.get("glow") or "")
    out["glow"] = g if re.fullmatch(r"#[0-9a-fA-F]{6}", g) else ""
    out["embers"] = bool(d.get("embers"))
    out["anime"] = bool(d.get("anime", out["anime"]))
    return out


# ------------------------------------------------------------------ que no parezca pegado
def harmonize(char_png, bg_png, out_png, strength=0.16):
    """Acerca el color del personaje a la luz del fondo (leve tinte) sin tocar la transparencia."""
    with Image.open(bg_png) as bg:
        mean = ImageStat.Stat(bg.convert("RGB").resize((64, 36))).mean
    with Image.open(char_png) as im:
        im = im.convert("RGBA")
    r, g, b, a = im.split()
    avg = sum(mean) / 3 or 1
    tint = [min(1.35, max(0.7, m / avg)) for m in mean]           # dirección del color del fondo
    bright = min(1.0, max(0.82, avg / 128))                         # fondo oscuro -> personaje un poco más oscuro
    chans = []
    for ch, k in zip((r, g, b), tint):
        f = (1 - strength) + strength * k
        chans.append(ch.point(lambda v, f=f: min(255, int(v * f * bright))))
    Image.merge("RGBA", (*chans, a)).save(out_png)
    return out_png


def dominant_light(bg_png):
    """Color brillante dominante del fondo (para la luz de borde)."""
    with Image.open(bg_png) as bg:
        small = bg.convert("RGB").resize((96, 54))
    px = sorted(small.getdata(), key=lambda p: max(p) * 2 - min(p), reverse=True)[:200]   # brillantes y saturados
    r, g, b = (sum(p[i] for p in px) // len(px) for i in range(3))
    m = max(r, g, b, 1)
    r, g, b = (int(v * 255 / m) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


# ------------------------------------------------------------------ armar
POS = {1: [.27, .5, .73], 2: [.24, .5, .76], 3: [.18, .5, .82]}      # izquierda, centro, derecha
SIZE = {"large": 1.0, "medium": .82, "small": .62}


def _has_alpha(path):
    try:
        with Image.open(path) as im:
            if im.mode not in ("RGBA", "LA", "PA") and "transparency" not in im.info:
                return False
            a = im.convert("RGBA").getchannel("A")
            return a.getextrema()[0] < 200
    except Exception:
        return False


def cut_quality(png):
    """Qué parte del recuadro del recorte es personaje (0-1). Una figura suelta da 0,35-0,7; si da más de
    0,8 es que se quedó con el fondo pintado detrás (un «cuadro» pegado encima)."""
    try:
        with Image.open(png) as im:
            a = im.convert("RGBA").getchannel("A")
        bb = a.point(lambda v: 255 if v > 10 else 0).getbbox()
        if not bb:
            return 0.0
        a = a.crop(bb)
        hist = a.histogram()
        return sum(hist[11:]) / max(1, a.width * a.height)
    except Exception:
        return 0.0


def harden_cut(png):
    """Último recurso: borra lo semitransparente (el fondo pintado que quedó como neblina)."""
    with Image.open(png) as im:
        im = im.convert("RGBA")
    a = im.getchannel("A").point(lambda v: 0 if v < 170 else min(255, int((v - 170) * 255 / 60)))
    im.putalpha(a)
    bb = a.point(lambda v: 255 if v > 10 else 0).getbbox()
    (im.crop(bb) if bb else im).save(png)


def _split_title(t):
    """«EL ÚLTIMO DRAGÓN» -> «EL ÚLTIMO\nDRAGÓN» (para un título al costado: dos líneas grandes)."""
    w = t.split()
    if len(t) <= 10 or len(w) < 2:
        return t
    best = min(range(1, len(w)), key=lambda i: abs(len(" ".join(w[:i])) - len(" ".join(w[i:]))))
    return " ".join(w[:best]) + "\n" + " ".join(w[best:])


# encuadre del personaje según lo que pidas (por defecto, cuerpo entero)
_FRAMES = (("upper", r"\b(close[- ]?up|primer plano|retrato|portrait|head and shoulders|busto|bust)\b",
            "upper body, portrait", "close-up portrait, head and shoulders"),
           ("cowboy", r"\b(upper body|half body|medio cuerpo|de la cintura para arriba|waist up|cowboy shot|"
                      r"hasta las rodillas|thighs up|medium shot)\b",
            "cowboy shot", "medium shot from the thighs up"))


def framing_of(text):
    """(clave, etiquetas, frase) del encuadre pedido: «upper», «cowboy» o «full» (cuerpo entero)."""
    low = (text or "").lower()
    for key, rx, tags, phrase in _FRAMES:
        if re.search(rx, low):
            return key, tags, phrase
    return "full", "(full body:1.2), standing", "full body shot from head to feet, standing"


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


def touching(raw, screen):
    """Qué bordes de la imagen toca el personaje (arriba, izquierda, derecha, abajo), viendo dónde NO está el color
    de la pantalla. Si toca arriba o los lados, salió cortado (capa, pelo, espada fuera del cuadro)."""
    import numpy as np
    try:
        with Image.open(raw) as im:
            a = np.asarray(im.convert("RGB")).astype(np.int16)
    except Exception:
        return {}
    bgm = screen_mask(a, screen)
    k = 3
    strips = {"top": bgm[:k, :], "bottom": bgm[-k:, :], "left": bgm[:, :k], "right": bgm[:, -k:]}
    return {side: float(1 - m.mean()) for side, m in strips.items()}


def subject_height(cut_png, raw_png):
    """Qué tan alto es el personaje recortado comparado con el dibujo (1 = ocupa todo el alto). Si es muy bajo, la
    IA lo dibujó lejos y pequeño (con paisaje alrededor) y no sirve como capa principal."""
    try:
        with Image.open(cut_png) as c, Image.open(raw_png) as r:
            return c.height / max(1, r.height)
    except Exception:
        return 1.0


def soften_cut_edges(png, sides, frac=.09):
    """El personaje quedó tocando un borde: ese lado se difumina para que no se vea una línea recta ni la esquina
    de un cuadrado (la luz de borde la marcaba)."""
    import numpy as np
    with Image.open(png) as im:
        im = im.convert("RGBA")
    w, h = im.size
    a = np.asarray(im.getchannel("A")).astype(np.float32)
    fx, fy = max(2, int(w * frac)), max(2, int(h * frac))
    if "top" in sides:
        a *= (np.arange(h) / fy).clip(0, 1)[:, None]
    if "bottom" in sides:
        a *= ((h - 1 - np.arange(h)) / fy).clip(0, 1)[:, None]
    if "left" in sides:
        a *= (np.arange(w) / fx).clip(0, 1)[None, :]
    if "right" in sides:
        a *= ((w - 1 - np.arange(w)) / fx).clip(0, 1)[None, :]
    im.putalpha(Image.fromarray(a.clip(0, 255).astype(np.uint8)))
    im.save(png)


_CHAR_NEG = ("cropped, out of frame, cut off, scenery, detailed background, sky, clouds, landscape, abstract background, gradient background, "
             "wind effects, floating particles, frame, border")


def build(text, say=None, cancel=None, have=None, refs=(), screen=None, versions=1, on_plan=None):
    """Hace todo. Devuelve (proyecto, plan). say(mensaje, fracción).
    refs: tus imágenes de referencia. Las PNG con fondo transparente se usan como personajes tal cual; la primera
    imagen normal es la base del fondo (se redibuja a partir de ella)."""
    say = say or (lambda *_: None)
    os.makedirs(WORK, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    have = have if have is not None else ia.available_engines()
    if not have:
        raise RuntimeError("Falta el motor de imágenes.")
    refs = [r for r in (refs or ()) if r and os.path.isfile(r)]
    screen = screen or ia.screen_wish()          # color de la «pantalla» para recortar (elegible en la app)
    ref_chars = [r for r in refs if _has_alpha(r)]
    ref_bg = next((r for r in refs if r not in ref_chars), None)
    model = ia.ensure_ollama()
    say("Tu IA separa el pedido en capas (fondo, personajes, título)…", .02)
    saved = find_saved(text)
    tp = thumb_plan(text, model, tuple(saved))
    if on_plan:                                   # la app muestra al instante lo que se va a dibujar (en inglés)
        try:
            on_plan(tp)
        except Exception:
            pass
    spec = tp.get("title_spec") or ia.title_spec(text)
    if ref_chars and len(tp["characters"]) < len(ref_chars):      # tus PNG transparentes son personajes
        tp["characters"] += [{"desc": "", "position": ""} for _ in range(len(ref_chars) - len(tp["characters"]))]
    tp["characters"] = tp["characters"][:3]
    n = len(tp["characters"])
    steps = 1 + n
    # prompts de los personajes (con internet, plan() busca cómo son los personajes famosos)
    char_jobs = []
    used_saved = set()
    free_refs = list(ref_chars)
    for i, c in enumerate(tp["characters"]):
        hay = (str(c.get("name", "")) + " " + str(c.get("desc", ""))).lower()
        match = next((nm for nm in saved if nm.lower() in hay and nm not in used_saved), None)
        if match:                              # personaje guardado: no se dibuja, se usa su PNG
            used_saved.add(match)
            char_jobs.append((c, None, saved[match], None, "guardado", ""))
            continue
        if free_refs:                          # tu imagen transparente: se usa tal cual
            char_jobs.append((c, None, free_refs.pop(0), None, "guardado", ""))
            continue
        if cancel is not None and cancel.is_set():
            raise RuntimeError("CANCELLED")
        say(f"Preparando al personaje {i + 1} de {n}…", .04)
        anime = tp["anime"]
        who = c.get("desc") or c.get("tags", "")
        if c.get("name"):
            who = f"{c['name']} from {c.get('series', '')}: {who}"
        gender = {"male": " (a man)", "female": " (a woman)"}.get(str(c.get("gender", "")).lower(), "")
        eng = "Anime (Animagine XL 4)" if anime and "Anime (Animagine XL 4)" in have else ia.AUTO
        pl = ia.plan(who + gender + (", anime style" if anime else ""), "Anime" if anime else "Automático", eng,
                     model=model, have=have, already_english=True)
        # pantalla verde (como en el cine): el verde liso se separa sin dudas del personaje. Si el personaje lleva
        # algo verde, sobre blanco (si no, se borraría su pelo o su ropa verde)
        scr = ia.pick_screen(who + " " + str(c.get("tags", "")), screen)
        frame, f_tags, f_phrase = framing_of(str(c.get("desc", "")) + " " + text)
        c["_frame"] = frame
        if ia.ENGINES[pl["engine"]].get("words") == "tags":
            prompt = pl["prompt"].replace(", masterpiece", f", {f_tags}, official art, " +
                                          ia.screen_prompt(scr, True) + ", masterpiece")
        else:
            prompt = (pl["prompt"] + f", {f_phrase}, the whole character inside the picture with empty space around "
                      "it, official character render, isolated on a " + ia.screen_prompt(scr) +
                      ", no scenery, no shadows on the background")
        char_jobs.append((c, pl["engine"], prompt, _CHAR_NEG + ", " + pl["negative"], "anime" if anime else "foto",
                          scr))
    ia.free_ollama_gpu()
    ia.start(say=lambda m, f: say(m, .05), cancel=cancel)
    # 1) fondo (si diste una imagen normal de referencia, se redibuja a partir de ella)
    bg = os.path.join(WORK, f"auto_fondo_{stamp}.png")
    eng_bg = "Alta calidad (Z-Image Turbo)" if "Alta calidad (Z-Image Turbo)" in have else have[0]
    style = (", modern anime manhwa digital illustration, cinematic lighting" if tp["anime"] else
             ", cinematic, dramatic lighting")
    spot = {"right": "the right side", "left": "the left side", "bottom": "the lower part"}.get(
        spec.get("position"), "the upper part")
    bg_prompt = (tp["background"] + style + f". No people, no characters. The scene fills the whole frame edge to "
                 f"edge; {spot} is calmer (open sky or soft light) so a title can go there, but it is still part "
                 "of the same painting: no panels, no blank boxes, no borders, no frames. "
                 "No text, no letters, no logos.")
    bg_neg = ia.ENGINES[eng_bg].get("negative", ia.NEGATIVE) + ", people, person, character"
    must_bg = tp.get("background_must") or []
    best_bg, best_miss = None, None
    for attempt in range(2 if must_bg else 1):     # tu IA que ve revisa el fondo; si falta algo, otra vez
        out_bg = bg if attempt == 0 else bg.replace(".png", f"_{attempt}.png")
        ia.generate(ia.emphasize(bg_prompt, best_miss or []), out_bg, eng_bg, (1344, 768), "", cancel=cancel,
                    negative=bg_neg, init_image=ref_bg, strength=.6,
                    say=lambda m, f: say("Fondo: " + m, .06 + .3 * f / steps))
        if not must_bg or not ia.vision_model():
            best_bg = out_bg
            break
        say("Tu IA revisa que el fondo tenga lo que pediste…", None)
        miss = ia.verify_image(out_bg, must_bg)
        if best_miss is None or len(miss) < len(best_miss):
            best_bg, best_miss = out_bg, miss
        if not miss:
            break
        say("Al fondo le falta: " + "; ".join(miss) + ". Lo dibujo otra vez reforzando eso…", None)
    if best_bg != bg:
        Image.open(best_bg).save(bg)
    tp["background_missing"] = best_miss or []
    alt_bgs = []
    for j in range(max(0, int(versions) - 1)):     # versiones B y C: el mismo pedido, otro dibujo de fondo
        if cancel is not None and cancel.is_set():
            raise RuntimeError("CANCELLED")
        p = bg.replace(".png", f"_v{j + 2}.png")
        ia.generate(ia.emphasize(bg_prompt, best_miss or []), p, eng_bg, (1344, 768), "", cancel=cancel,
                    negative=bg_neg, init_image=ref_bg, strength=.6,
                    say=lambda m, f, j=j: say(f"Fondo de la versión {'BC'[j]}: " + m, None))
        alt_bgs.append(p)
    glow = dominant_light(bg)                     # la luz real del fondo dibujado
    # 2) personajes (cada uno sobre pantalla verde o blanco, recortado y armonizado)
    layers = [{"kind": "image", "path": bg, "cover": True, "x": .5, "y": .5}]
    order = sorted(range(n), key=lambda i: 0 if tp["characters"][i].get("size") == "large" else 1, reverse=True)
    side_title = spec.get("position") in ("left", "right")
    xs = POS.get(n, POS[3])
    if side_title:                                # el título ocupa un costado: los personajes van en el otro
        xs = {"right": [.2, .36, .5], "left": [.5, .64, .8]}[spec["position"]]
        if n == 1:
            xs = [.27, .27, .27] if spec["position"] == "right" else [.73, .73, .73]
    sides = {"left": 0, "center": 1, "right": 2}
    used = set()
    top = .2 if tp["title"] and spec.get("position") in ("", "top") else .05   # la cabeza bajo el título
    for k, i in enumerate(order):
        if cancel is not None and cancel.is_set():
            raise RuntimeError("CANCELLED")
        c, eng, prompt, neg, kind, scr = char_jobs[i]
        raw = os.path.join(WORK, f"auto_pers_{stamp}_{i}.png")
        if kind == "guardado":
            say(f"Uso tu personaje «{os.path.splitext(os.path.basename(prompt))[0]}».", None)
            cut = prompt
        else:
            cut = raw.replace(".png", "_recorte.png")
            tries = []                           # (puntos, dibujo, recorte, bordes que toca)
            for attempt in range(2):             # si sale cortado o con fondo detrás, se dibuja otra vez
                raw_a = raw.replace(".png", f"_{attempt}.png")
                cut_a = raw.replace(".png", f"_{attempt}_recorte.png")
                ia.generate(prompt, raw_a, eng, (832, 1216), "", negative=neg, cancel=cancel,
                            say=lambda m, f, i=i: say(f"Personaje {i + 1} de {n}: {m}",
                                                      .06 + .9 * (1 + k + f) / (steps + 1)))
                ia.cutout(raw_a, cut_a, kind, white=scr == "white", screen=scr if scr != "white" else "",
                          say=lambda m, f=None: say(m, None))
                q, big = cut_quality(cut_a), subject_height(cut_a, raw_a)
                miss = []
                if c.get("must") and ia.vision_model():
                    say(f"Tu IA revisa al personaje {i + 1} (que sea lo que pediste)…", None)
                    miss = ia.verify_image(raw_a, c["must"])
                tch = touching(raw_a, scr)
                allowed = ("bottom",) if c.get("_frame") in ("upper", "cowboy") else ()
                cut_off = [sd for sd, v in tch.items() if v > .04 and sd not in allowed]
                # puntos: sin bordes cortados, sin fondo detrás y que el personaje ocupe casi todo el alto
                pts = (0 if cut_off else 2) + (0 if q > .8 else 2) + (1 if big >= .6 else -3) - 1.5 * len(miss)
                if c.get("must") and c["must"][0] in miss:
                    pts -= 4                       # género equivocado: lo peor que puede pasar
                tries.append((pts, raw_a, cut_a, tch))
                if not cut_off and q <= .8 and big >= .6 and not miss:
                    break
                if attempt == 0:
                    why = ("no tiene: " + "; ".join(miss) if miss else
                           "salió cortado por el borde" if cut_off else
                           "se quedó con fondo detrás" if q > .8 else "salió muy pequeño")
                    if miss:
                        prompt = ia.emphasize(prompt, miss, ia.ENGINES[eng].get("words") == "tags")
                    say(f"El personaje {i + 1} {why}: lo dibujo otra vez…", None)
                    if q > .8:
                        prompt = prompt.replace("background:1.5)", "background:1.7)")
                        neg = "(detailed background:1.3), (scenery:1.3), " + neg
                    if cut_off:          # cuerpo entero dentro del cuadro, pero GRANDE (no un muñequito lejos)
                        prompt = prompt.replace(", official", ", (entire body visible:1.2), head and feet inside "
                                                              "the frame, official", 1)
                        neg = "(cropped:1.3), (out of frame:1.3), (cut off:1.2), " + neg
                    if big < .6:
                        neg = "(scenery:1.3), (landscape:1.3), (rock:1.2), (crystal:1.1), (small figure:1.3), " + neg
            pts, raw_b, cut_b, tch = max(tries, key=lambda t: t[0])       # el mejor intento
            ia.release_vision()
            Image.open(raw_b).save(raw)
            Image.open(cut_b).save(cut)
            if cut_quality(cut) > .8:
                harden_cut(cut)
            soft = [sd for sd, v in tch.items() if v > .01 and not (sd == "bottom" and c.get("_frame") != "full")]
            if soft:                               # lo que siga tocando el borde se difumina (sin esquinas rectas)
                soften_cut_edges(cut, soft)
        fin = raw.replace(".png", "_capa.png")
        harmonize(cut, bg, fin)
        slot = sides.get(str(c.get("position", "")).lower())
        if slot is None or slot in used:
            pref = [2, 0, 1] if n == 1 and not side_title else [0, 2, 1]
            slot = next((j for j in pref if j not in used), k % 3)
        used.add(slot)
        h = SIZE.get(str(c.get("size", "")).lower(), .95 if n == 1 else .85)
        y = top + h / 2
        if c.get("_frame") in ("upper", "cowboy"):
            y = 1.0 - h / 2 + .01                 # pegado al borde de abajo: no se nota dónde termina
        layers.insert(1 + k, {"kind": "image", "path": fin, "x": xs[slot], "y": y, "h": h,
                              "glow": glow, "glow_size": .32})
    # 3) textos (dónde y cómo los pediste)
    shade_side = "top"
    if tp["title"]:
        pos = spec.get("position") or "top"
        lay = {"kind": "text", "style": tp["title_style"]}
        if pos in ("left", "right"):
            lay.update(text=_split_title(tp["title"]), align=pos, x=.965 if pos == "right" else .035, y=.1,
                       size=.19, max_w=.5)
            shade_side = pos
        elif pos == "bottom":
            lay.update(text=tp["title"], align="center", x=.5, y=.72, size=.15 if len(tp["title"]) < 22 else .12)
            shade_side = "bottom"
        else:
            lay.update(text=tp["title"], align="center", x=.5, y=.035 if pos == "top" else .4,
                       size=.15 if len(tp["title"]) < 22 else .12)
        if spec.get("fill"):
            lay["fill"] = spec["fill"]
        if spec.get("stroke"):
            lay["stroke"] = spec["stroke"]
            lay["stroke_w"] = .11 if spec.get("thick") else .075
            lay["glow"] = "#000000"             # sombra oscura: el borde de color resalta más
        layers.append(lay)
    if tp["subtitle"]:
        sub_y = .22 if shade_side == "top" else (.62 if shade_side in ("left", "right") else .62)
        layers.append({"kind": "text", "text": tp["subtitle"], "style": "Elegante", "x": layers[-1].get("x", .5),
                       "y": sub_y, "size": .065, "align": layers[-1].get("align", "center")})
    explicit_pos = bool(re.search(r"\b(left|right|izquierda|derecha|center|centro)\b", text.lower()))
    proj = {"size": [1280, 720], "layers": layers, "alt_backgrounds": alt_bgs,
            "lock": {"layout": bool(spec.get("position")) or explicit_pos,
                     "style": bool(spec.get("fill") or spec.get("stroke") or spec.get("style") != "Impacto")},
            "fx": {"shade": .55 if tp["title"] else 0, "shade_side": shade_side, "vignette": .55,
                   "embers": .6 if tp["embers"] else 0, "embers_color": glow}}
    say("Miniatura lista.", 1.0)
    return proj, tp


def save(proj, path, W=1920, H=1080):
    """Guarda la miniatura (formato según la extensión) y el proyecto .json al lado."""
    img = M.render(proj, W, H)
    ext = os.path.splitext(path)[1].lower()
    M.save_image(img if ext in (".png", ".webp", ".tif", ".tiff") else img.convert("RGB"), path)
    with open(project_path(path), "w", encoding="utf-8") as f:
        json.dump(proj, f, ensure_ascii=False, indent=1)
    return path


def project_path(image_path):
    return os.path.splitext(image_path)[0] + ".miniatura.json"


def load_project(image_path):
    try:
        with open(project_path(image_path), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ------------------------------------------------------------------ personajes guardados (para reusarlos)
CHAR_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioNovelaStudio", "personajes")


def _safe(name):
    return re.sub(r"[^\w\- ]+", "", name, flags=re.U).strip()[:40] or "personaje"


def list_saved():
    """[(nombre, ruta PNG)] de los personajes guardados, el más nuevo primero."""
    try:
        files = [f for f in os.listdir(CHAR_DIR) if f.lower().endswith(".png") and ".part" not in f]
    except OSError:
        return []
    files.sort(key=lambda f: os.path.getmtime(os.path.join(CHAR_DIR, f)), reverse=True)
    return [(os.path.splitext(f)[0], os.path.join(CHAR_DIR, f)) for f in files]


def save_character(png_path, name):
    """Guarda una capa con fondo transparente como personaje reutilizable. Devuelve la ruta guardada."""
    os.makedirs(CHAR_DIR, exist_ok=True)
    dst = os.path.join(CHAR_DIR, _safe(name) + ".png")
    with Image.open(png_path) as im:
        im = im.convert("RGBA")
        bbox = im.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
        (im.crop(bbox) if bbox else im).save(dst + ".part.png")
    os.replace(dst + ".part.png", dst)
    return dst


def delete_character(name):
    try:
        os.remove(os.path.join(CHAR_DIR, _safe(name) + ".png"))
    except OSError:
        pass


def find_saved(text):
    """Personajes guardados que se nombran en el texto: {nombre: ruta}."""
    t = (text or "").lower()
    return {n: p for n, p in list_saved() if len(n) >= 2 and n.lower() in t}


# ------------------------------------------------------------------ versiones A/B/C
_ALT_STYLE = {"Impacto": "Aura roja", "Aura roja": "Impacto", "Oro y rojo": "Impacto", "Cromo épico": "Oro y rojo",
              "Neón": "Impacto", "Elegante": "Cromo épico", "Cómic": "Impacto"}


def make_variants(proj, n=3):
    """Versiones del mismo trabajo, sin volver a dibujar: A tal cual; B en espejo y con otro estilo de título;
    C con el título a la izquierda y los personajes a la derecha.
    Si TÚ dijiste dónde va cada cosa o cómo son las letras, eso no se toca: B resalta la última palabra en amarillo
    y C acerca la cámara (personaje y título más grandes)."""
    import copy
    out = _variants(proj, n)
    alts = proj.get("alt_backgrounds") or []
    for j, v in enumerate(out[1:]):              # B y C con su propio dibujo de fondo (no el mismo dragón)
        if j < len(alts) and os.path.isfile(alts[j]):
            bgl = _bg(v)
            if bgl:
                bgl["path"] = alts[j]
    return out


def _variants(proj, n):
    import copy
    lock = proj.get("lock") or {}
    if lock.get("layout") or lock.get("style"):
        out = [copy.deepcopy(proj)]
        if n >= 2:
            b = copy.deepcopy(proj)
            for l in _titles(b)[:1]:
                lines = l["text"].split("\n")
                last = lines[-1].split(" ")
                last[-1] = "*" + last[-1] + "*"
                lines[-1] = " ".join(last)
                l["text"] = "\n".join(lines)
                l["accent"] = "#ffd400"
                l["size"] = l.get("size", .15) * 1.08
            if not lock.get("layout"):
                for l in _chars(b):
                    l["x"] = 1 - l.get("x", .5)
            out.append(b)
        if n >= 3:
            c = copy.deepcopy(proj)
            for l in _chars(c):
                l["h"] = min(1.3, l.get("h", .9) * 1.18)
                l["y"] = l.get("y", .6) + .08
            for l in _titles(c)[:1]:
                l["size"] = l.get("size", .15) * 1.12
            c.setdefault("fx", {})["vignette"] = .7
            out.append(c)
        return out[:max(1, n)]
    out = [copy.deepcopy(proj)]
    if n >= 2:
        b = copy.deepcopy(proj)
        for l in b["layers"]:
            if l["kind"] == "image" and not l.get("cover"):
                l["x"] = 1 - l.get("x", .5)
            elif l["kind"] == "text" and l.get("y", 0) < .15:
                l["style"] = _ALT_STYLE.get(l.get("style"), "Impacto")
        out.append(b)
    if n >= 3:
        c = copy.deepcopy(proj)
        imgs = sorted([l for l in c["layers"] if l["kind"] == "image" and not l.get("cover")],
                      key=lambda l: l.get("x", .5))
        for j, l in enumerate(imgs):
            l["x"] = .66 + (.24 * j / (len(imgs) - 1) if len(imgs) > 1 else .08)
        texts = [l for l in c["layers"] if l["kind"] == "text"]
        for j, l in enumerate(texts):
            l.update(align="left", x=.04, max_w=.56)
            l["y"] = .06 if j == 0 else .06 + .26 * j
            l["size"] = .17 if j == 0 else .07
        c["fx"] = dict(c.get("fx", {}), shade=.85, shade_side="left")
        out.append(c)
    return out[:max(1, n)]


# ------------------------------------------------------------------ pulir hasta la nota pedida
def _chars(proj):
    return [l for l in proj["layers"] if l["kind"] == "image" and not l.get("cover")]


def _bg(proj):
    return next((l for l in proj["layers"] if l.get("cover")), None)


def _titles(proj):
    return [l for l in proj["layers"] if l["kind"] == "text"]


def pro_defaults(proj):
    """Lo que hacen los diseñadores de miniaturas: fondo un poco más oscuro y desenfocado (profundidad), personajes
    más vivos con luz de borde, título grande y un «pop» final de contraste y color."""
    bg = _bg(proj)
    if bg:
        bg.setdefault("bright", .96)
        bg.setdefault("blur", 1.0)
        bg.setdefault("sat", 1.12)
    for l in _chars(proj):
        l.setdefault("bright", 1.08)
        l.setdefault("contrast", 1.06)
        l.setdefault("sat", 1.1)
        l["glow_size"] = max(.4, l.get("glow_size", .3))
    t = _titles(proj)
    if t:
        t[0]["size"] = max(t[0].get("size", .15), .16)
    fx = proj.setdefault("fx", {})
    fx.setdefault("pop_contrast", .06)
    fx.setdefault("pop_sat", .1)
    fx.setdefault("autolevel", .7)
    fx["vignette"] = max(fx.get("vignette", 0), .4)
    return proj


_KEYS = {"titulo": ("título", "titulo", "texto", "letra", "legib", "tipograf"),
         "contraste": ("contraste", "oscur", "apagad", "brillo"),
         "personaje": ("personaje", "chica", "chico", "rostro", "cara", "destac", "figura"),
         "limpieza": ("fondo", "elementos", "ruido", "recarg", "cortad", "distrac"),
         "color": ("color", "satura", "vibran", "paleta"),
         "foco": ("foco", "punto focal", "atención", "centro")}


def _fix(proj, crit, tips):
    """Aplica los arreglos de los criterios más bajos. Devuelve la lista de cambios hechos (en español)."""
    import copy
    proj = copy.deepcopy(proj)
    weak = sorted((v, k) for k, v in crit.items() if v < 9.5)
    low = " ".join(tips).lower()
    for k, words in _KEYS.items():                       # si la nota no vino por criterio, se lee el consejo
        if not crit and any(w in low for w in words):
            weak.append((5, k))
    done = []
    fx = proj.setdefault("fx", {})
    bg, chars, titles = _bg(proj), _chars(proj), _titles(proj)
    for _v, k in weak[:3]:
        if k == "titulo" and titles:
            t = titles[0]
            t["size"] = min(.24, t.get("size", .15) * 1.12)
            t["max_w"] = .95
            if t.get("style") in ("Elegante", "Neón", "Cómic") and not (proj.get("lock") or {}).get("style"):
                t["style"] = "Impacto"
            fx["shade"] = min(.95, fx.get("shade", 0) + .2)
            fx.setdefault("shade_side", "top")
            done.append("título más grande y con más sombra detrás")
        elif k == "contraste":
            # antes se oscurecía todo el fondo y la miniatura quedaba «sucia»: ahora se estiran los niveles
            fx["autolevel"] = min(1.0, fx.get("autolevel", 0) + .3)
            fx["pop_contrast"] = min(.25, fx.get("pop_contrast", 0) + .05)
            for l in chars:
                l["bright"] = min(1.35, l.get("bright", 1) * 1.08)
                l["contrast"] = min(1.3, l.get("contrast", 1) * 1.05)
            done.append("más contraste (niveles automáticos, personajes más claros)")
        elif k in ("personaje", "foco") and chars:
            main = max(chars, key=lambda l: l.get("h", .8))
            main["h"] = min(1.25, main.get("h", .9) * 1.1)
            main["glow_size"] = min(.8, main.get("glow_size", .3) + .15)
            main["bright"] = min(1.35, main.get("bright", 1) * 1.06)
            if bg:
                bg["blur"] = min(5, (bg.get("blur") or 0) + 1.2)
            done.append("personaje más grande y con más luz; fondo más desenfocado")
        elif k in ("limpieza", "foco"):
            if bg:
                bg["blur"] = min(5, (bg.get("blur") or 0) + 1.5)
            fx["vignette"] = min(.9, fx.get("vignette", 0) + .1)
            fx["embers"] = round(fx.get("embers", 0) * .5, 2)
            done.append("fondo más simple (desenfoque y viñeta, menos chispas)")
        elif k == "color":
            fx["pop_sat"] = min(.4, fx.get("pop_sat", 0) + .1)
            if bg:
                bg["sat"] = min(1.6, bg.get("sat", 1) * 1.1)
            done.append("colores más vivos")
    return proj, done


JUDGE_SCALE = "Escala de este juez (Gemma 4 en tu PC): tus miniaturas profesionales sacan 6,8 a 8,1; por encima de 8 ya es muy buena."
POLISH_TARGET = 8.5          # supera a las mejores miniaturas del usuario con este mismo juez (8,1)


def improve(proj, target=POLISH_TARGET, rounds=4, say=None, cancel=None, work_png=None):
    """Revisa con la IA y corrige hasta llegar a la nota pedida (o agotar las rondas).
    Devuelve (mejor proyecto, mejor nota, historial [(ronda, nota, criterios, cambios)])."""
    say = say or (lambda *_: None)
    work_png = work_png or os.path.join(WORK, "pulir.png")
    os.makedirs(WORK, exist_ok=True)
    cur = pro_defaults(__import__("copy").deepcopy(proj))
    judge = ia.fast_judge()                    # pulir necesita muchas rondas: siempre el juez rápido
    best, best_score, history = cur, -1.0, []
    for r in range(rounds):
        if cancel is not None and cancel.is_set():
            break
        M.render(cur, 1280, 720).convert("RGB").save(work_png)
        say(f"Tu IA califica la miniatura (ronda {r + 1} de {rounds})…", (r + .5) / rounds)
        d = ia.critique_thumbnail(work_png, model=judge, keep_alive="5m")
        score = float(d.get("nota") or 0)
        crit = d.get("criterios") or {}
        if score > best_score:
            best, best_score = cur, score
        if score >= target:
            history.append((r + 1, score, crit, []))
            break
        cur, changes = _fix(cur, crit, d.get("mejorar", []))
        history.append((r + 1, score, crit, changes))
        say(f"Ronda {r + 1}: {score}/10 → {', '.join(changes) or 'sin cambios'}", (r + 1) / rounds)
        if not changes:
            break
    try:                                                  # libera la tarjeta (Gemma)
        req = __import__("urllib.request", fromlist=["x"]).Request(
            ia.OLLAMA + "/api/generate", json.dumps({"model": judge, "keep_alive": 0}).encode(),
            {"Content-Type": "application/json"})
        __import__("urllib.request", fromlist=["x"]).urlopen(req, timeout=20).read()
    except Exception:
        pass
    return best, best_score, history
