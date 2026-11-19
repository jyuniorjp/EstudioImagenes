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


def thumb_plan(text, model=None, saved_names=(), review=True):
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
        "You plan a YouTube thumbnail made of separate layers. Read the user's request (often Spanish). " +
        "Translate FAITHFULLY: keep every noun, adjective, emotion, action and detail the user wrote for each "
        "layer (nothing omitted), never replace an object with a different one, and never add places, objects "
        "or creatures the user did not mention. Spanish weapon words: hoz = sickle, guadaña = scythe, hacha = "
        "axe, espada = sword, lanza = spear, arco = bow, martillo = hammer, daga = dagger. "
        "Answer "
        "ONLY with JSON: {"
        "\"background\": English prompt for the BACKGROUND ONLY (setting, sky, weather, light, colors, big creatures or "
        "objects the user places in the scenery; if the user says a creature is gigantic or "
        "huge, describe it as enormous and filling a big part of the frame; keep every creature's MATERIAL, SHAPE "
        "and COLORS exactly as the user wrote and say they keep those colors under the scene light; a creature made "
        "of a material is one solid sculpted body, not a mosaic of pieces), NO people, NO main characters, keep the "
        "area where the title goes simple, max 120 words; "
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
        # ¿lo dijiste tú? («a la izquierda», «on the left»): entonces Gemma no lo mueve
        c["_user_pos"] = bool(re.search(r"\b(izquierda|derecha|centro|left|right|center)\b", text.lower()))
    if review and ia.vision_model():           # revisión PREVIA: Gemma compara tu texto con las capas de Qwen
        draft = {"background": out["background"], "background_must": [],
                 "characters": [{"desc": str(c.get("desc") or ""), "tags": str(c.get("tags") or ""), "must": []}
                                for c in out["characters"]]}
        if not out["characters"]:
            draft.pop("characters")
        if out["title"]:                       # composición: Gemma decide dónde queda mejor cada cosa
            draft["title_position"] = ""
            if out["subtitle"]:
                draft["subtitle_position"] = ""
        if out["characters"]:
            draft["character_layout"] = [{"position": str(c.get("position") or ""), "size": str(c.get("size") or "")}
                                         for c in out["characters"]]
        fixed, rep = ia.review_draft(text, draft)
        tpos = str(fixed.get("title_position") or "").lower().strip()
        if tpos in _PLACES:
            # lo que TÚ escribiste manda: Gemma solo precisa (p. ej. «derecha» -> «arriba a la derecha»)
            side = spec["position"]
            if not side or side in tpos or (side == "top" and tpos.startswith("top")) or \
                    (side == "bottom" and tpos.startswith("bottom")):
                out["title_place"] = tpos
        spos = str(fixed.get("subtitle_position") or "").lower().strip()
        if spos in ("below_title", "above_title", "bottom"):
            out["subtitle_place"] = spos
        for c, lay in zip(out["characters"], fixed.get("character_layout") or []):
            if isinstance(lay, dict):
                if str(lay.get("position")).lower() in ("left", "center", "right") and not c.get("_user_pos"):
                    c["position"] = str(lay["position"]).lower()
                if str(lay.get("size")).lower() in ("large", "medium", "small"):
                    c["size"] = str(lay["size"]).lower()
        out["background"] = fixed.get("background") or out["background"]
        if fixed.get("background_must"):
            out["background_must"] = ia.relevant_checks(fixed["background_must"], out["background"], text)
        for c, fc in zip(out["characters"], fixed.get("characters") or []):
            for k in ("desc", "tags"):
                if fc.get(k):
                    c[k] = fc[k]
            if fc.get("must"):
                c["must"] = ia.relevant_checks(fc["must"], c.get("desc", ""), c.get("tags", ""), text)
        for c in out["characters"]:               # el género que TÚ escribiste se revisa siempre, primero
            g = str(c.get("gender") or "")
            if g in ("male", "female"):
                want = "a woman" if g == "female" else "a man"
                c["must"] = [want] + [m for m in c.get("must", []) if m != want][:4]
        out["review"] = rep
        out["review_note"] = ia.review_note(rep)
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


_PLACES = ("top-left", "top", "top-right", "left", "center", "right", "bottom-left", "bottom", "bottom-right")


_SCENERY = re.compile(r"\b(battlefield|sky|skies|landscape|city|cityscape|forest|clouds?|storm|stormy|mountains?|"
                      r"ruins|outdoors|indoors|field|ocean|sea|street|castle|room|valley|desert|night|sunset|"
                      r"scenery|background|horizon|space|cosmos|cosmic|galaxy)\b", re.I)


_CHAR_NEG = ("cropped, out of frame, cut off, scenery, detailed background, sky, clouds, landscape, abstract background, gradient background, "
             "wind effects, floating particles, frame, border")


# ------------------------------------------------------------------ ¿una sola imagen o por capas?
MODE_CFG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioNovelaStudio", "forma.json")
MODES = {"Una imagen": "single", "Por capas": "layers", "Automática": "auto"}
_INTERACT = re.compile(
    r"\b(montad[oa]s?|monta|cabalga\w*|riding|rides?|abraz\w*|hug\w*|en (sus )?brazos|in (his|her|their) arms|"
    r"carg(a|ando|ada|ado)|sostenid[oa] por|en la mano del?|in the hand of|sobre el lomo|on the back of|"
    r"bes(a|an|ando)\b|kiss\w*|pelea\w* contra|luch\w* contra|fight(s|ing) (with|against)|"
    r"sentad[oa]s? (en|sobre)|sitting on|de la mano|hand in hand|espalda con espalda|back to back)\b", re.I)


def mode_choice():
    try:
        with open(MODE_CFG, encoding="utf-8") as f:
            v = json.load(f).get("forma")
        return v if v in MODES else "Una imagen"
    except Exception:
        return "Una imagen"


def set_mode(name):
    try:
        os.makedirs(os.path.dirname(MODE_CFG), exist_ok=True)
        with open(MODE_CFG, "w", encoding="utf-8") as f:
            json.dump({"forma": name if name in MODES else "Una imagen"}, f)
    except OSError:
        pass


def mode_wish():
    return MODES.get(mode_choice(), "single")


def decide_mode(text, tp, saved=None, ref_chars=(), wish="auto"):
    """('single' | 'layers', motivo en español). Por capas cuando hace falta control o personajes tuyos; una sola
    imagen cuando todo convive en la escena (más natural y unas 5 veces más rápida). El título siempre lo pone
    la app con letras perfectas."""
    if wish == "single":
        return "single", "Elegiste «Una imagen»: escena completa y el título encima con letras perfectas."
    if wish == "layers":
        return "layers", "Elegiste «Por capas»: fondo, personajes recortados y título por separado."
    chars = tp.get("characters") or []
    low = text.lower()
    if saved or ref_chars:
        return "layers", "Usas un personaje tuyo (guardado o PNG): va por capas, tal cual, sin redibujarlo."
    if _INTERACT.search(low):
        return "single", ("Los personajes interactúan entre sí o con la escena: una sola imagen, para que el contacto "
                          "y la luz sean naturales.")
    if not chars:
        return "single", "No hay personaje principal: una sola imagen, más rápida."
    if len(chars) >= 2:
        return "layers", "Hay varios personajes en lugares concretos: por capas, para colocar a cada uno."
    c = chars[0]
    if c.get("name") and c.get("series") and len(str(tp.get("background", "")).split()) > 25:
        return "layers", ("Personaje conocido con un fondo complejo: Animagine dibuja al personaje (lo conoce) y "
                          "Z-Image el fondo.")
    if c.get("_user_pos") and re.search(r"\b(grande|mediano|mediana|pequeñ[oa]|large|big|medium|small)\b", low):
        return "layers", "Pediste el lugar y el tamaño exactos del personaje: por capas, para respetarlos."
    return "single", "Un personaje integrado en la escena: una sola imagen, más natural y rápida."


# ------------------------------------------------------------------ una sola imagen con un prompt «estilo ChatGPT»
_CHAT_SYS = (
    "You are an expert prompt writer for top image generators (like the ones ChatGPT uses). Turn the user's request "
    "(often Spanish) into ONE rich English paragraph of 140-260 words that describes the FINAL YouTube thumbnail as a "
    "single finished picture: art style and mood first; then every subject with ALL the details the user wrote "
    "(gender, age, looks, hair, eyes, expression, clothes and armor with colors, weapons and which hand, effects, "
    "actions and how subjects interact); the composition (what is on the left, right, foreground, background, how big); "
    "lighting, color palette and camera framing. Then the text: every text the user wants written goes in double "
    "quotes EXACTLY as written (same accents and capitals), with its font look, color, outline, glow, size and "
    "position, and say that no other text appears. Translate faithfully (hoz = sickle, guadaña = scythe, hacha = axe, "
    "espada = sword, lanza = spear, daga = dagger); never omit anything the user wrote and never add objects, places "
    "or creatures the user did not mention. Answer ONLY with JSON: {\"prompt\": the paragraph, \"must\": 3-6 very short "
    "English checks a viewer can verify (gender of each person first), \"anime\": true if anime/manga/manhwa style}.")


def chatgpt_prompt(text, model=None):
    """Qwen escribe el pedido como un prompt de ChatGPT; Gemma lo revisa contra TU texto. -> (prompt, must, nota)."""
    model = model if model is not None else ia.ensure_ollama()
    prompt, must, anime = "", [], "anime" in text.lower() or "manhwa" in text.lower()
    if model:
        try:
            raw = ia._ollama(_CHAT_SYS, text, model, timeout=150, fmt="json")
            d = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
            prompt = str(d.get("prompt") or "").strip()
            must = [str(x) for x in (d.get("must") or []) if str(x).strip()] if isinstance(d.get("must"), list) else []
            anime = bool(d.get("anime", anime))
        except Exception:
            pass
    if not prompt:
        prompt = ia.to_english(text, model)
    note = ""
    if ia.vision_model():                          # revisión PREVIA: Gemma compara con tu texto original
        fixed, rep = ia.review_draft(text, {"prompt": prompt, "must": []})
        prompt = fixed.get("prompt") or prompt
        if fixed.get("must"):
            must = fixed["must"]
        note = ia.review_note(rep)
    must = ia.relevant_checks(must, prompt, text)[:5]
    return prompt, must, anime, note


def build_chatgpt(text, say, cancel, have, ref_bg, versions, stamp, model=None, on_plan=None, why=""):
    """Una sola imagen, como ChatGPT: un prompt muy descriptivo y la IA dibuja todo, título incluido. Gemma revisa
    la imagen (también que el título esté bien escrito) y se repite reforzando lo que falte. Si la IA no logra
    escribir bien el título, la app lo pone encima con letras perfectas."""
    say("Tu IA escribe el prompt como para ChatGPT y Gemma lo revisa contra tu texto (~1 min)…", .02)
    prompt, must, anime, note = chatgpt_prompt(text, model)
    quotes = [q.strip() for q in re.findall(r'[«"“]([^»"”]{1,60})[»"”]', text) if q.strip()]
    title = max(quotes, key=len) if quotes else ""
    subtitle = next((q for q in quotes if q != title), "")
    text_checks = [f'the text "{q}" is written correctly, letter by letter' for q in (title, subtitle) if q]
    spec = ia.title_spec(text)
    tp = {"mode": "single", "mode_reason": why, "background": prompt, "prompt_full": prompt, "characters": [],
          "title": title, "subtitle": subtitle, "title_style": spec["style"], "title_spec": spec,
          "review_note": note, "anime": anime, "embers": False, "glow": ""}
    if on_plan:
        try:
            on_plan(tp)
        except Exception:
            pass
    eng = "Alta calidad (Z-Image Turbo)" if "Alta calidad (Z-Image Turbo)" in have else have[0]
    neg = "blurry, low quality, deformed, bad anatomy, watermark, signature, misspelled text, extra text"
    full = prompt + (" Modern anime manhwa digital illustration, sharp clean linework." if anime else "") + \
        " Professional YouTube thumbnail, ultra detailed, sharp focus."
    checks = (must + text_checks)[:7]
    ia.free_ollama_gpu()
    ia.start(say=lambda m, f: say(m, .05), cancel=cancel)
    img = os.path.join(WORK, f"auto_unica_{stamp}.png")
    best, best_miss, best_text_ok = None, None, False
    tries = 3 if text_checks else 2
    for attempt in range(tries):
        if cancel is not None and cancel.is_set():
            raise RuntimeError("CANCELLED")
        out = img if attempt == 0 else img.replace(".png", f"_{attempt}.png")
        ia.generate(ia.emphasize(full, best_miss or []), out, eng, (1344, 768), "", cancel=cancel, negative=neg,
                    init_image=ref_bg, strength=.6,
                    say=lambda m, f, a=attempt: say(("Imagen: " if not a else f"Intento {a + 1}: ") + m, .08 + .8 * f))
        if not checks or not ia.vision_model():
            best, best_text_ok = out, True
            break
        say("Tu IA revisa la imagen y lee el título letra por letra…", None)
        miss = [m for m in ia.verify_image(out, must) if m] if must else []
        text_ok = True
        if text_checks:
            r = ia.text_ok(out, [q for q in (title, subtitle) if q])
            text_ok = r if r is not None else not ia.verify_image(out, text_checks)
            if not text_ok:
                miss = miss + text_checks
        if best_miss is None or (text_ok, -len(miss)) > (best_text_ok, -len(best_miss)):
            best, best_miss, best_text_ok = out, miss, text_ok
        if not miss:
            break
        say("A la imagen le falta: " + "; ".join(miss) + ". La dibujo otra vez reforzando eso…", None)
    ia.release_vision()
    if best != img:
        Image.open(best).save(img)
    tp["background_missing"] = [m for m in (best_miss or []) if m not in text_checks]
    alts = []
    for j in range(max(0, int(versions) - 1)):   # versiones B y C: otra imagen con el mismo prompt
        if cancel is not None and cancel.is_set():
            raise RuntimeError("CANCELLED")
        p = img.replace(".png", f"_v{j + 2}.png")
        ia.generate(ia.emphasize(full, best_miss or []), p, eng, (1344, 768), "", cancel=cancel, negative=neg,
                    init_image=ref_bg, strength=.6, say=lambda m, f, j=j: say(f"Versión {'BC'[j]}: " + m, None))
        alts.append(p)
    layers = [{"kind": "image", "path": img, "cover": True, "x": .5, "y": .5}]
    shade_side = "top"
    if title and not best_text_ok:               # el seguro: la IA no logró escribirlo bien -> letras perfectas
        # esa imagen ya tiene el título mal escrito: se dibuja la escena SIN texto y la app pone las letras
        say("La IA no logró escribir bien el título: dibujo la escena sin texto y lo pongo yo con letras "
            "perfectas…", None)
        notext = re.sub(r'[«"“][^»"”]{1,60}[»"”]', "", full)
        notext = re.sub(r"\s{2,}", " ", notext) + " Absolutely no text, no letters, no title, no words anywhere."
        ia.start(say=lambda m, f: say(m, None), cancel=cancel)
        ia.generate(notext, img, eng, (1344, 768), "", cancel=cancel, negative=neg + ", text, letters, words",
                    init_image=ref_bg, strength=.6, say=lambda m, f: say("Escena sin texto: " + m, None))
        tp["title_place"] = ""
        shade_side = _add_texts(text, tp, spec, layers)
        tp["mode_reason"] = (why + " La IA no escribió bien el título, así que lo puso la app con letras perfectas.")
    proj = {"size": [1280, 720], "layers": layers, "alt_backgrounds": alts, "mode": "single",
            "lock": {"layout": True, "style": True},
            "fx": {"shade": .45 if len(layers) > 1 else 0, "shade_side": shade_side, "vignette": .25,
                   "embers": 0, "embers_color": dominant_light(img)}}
    say("Miniatura lista.", 1.0)
    return proj, tp



def build_single(text, tp, spec, say, cancel, have, ref_bg, versions, stamp):
    """Una sola imagen (escena con sus personajes) + título y subtítulo encima con letras perfectas.
    Gemma revisa la imagen contra tu pedido y se redibuja reforzando lo que falte."""
    chars = tp.get("characters") or []
    where = {"left": "on the left side", "right": "on the right side", "center": "in the center"}
    size = {"large": "large in the foreground", "medium": "medium size", "small": "small, further back"}
    parts = []
    for c in chars:
        frame = framing_of(str(c.get("desc", "")) + " " + text)[2]
        extra = ", ".join(x for x in (where.get(str(c.get("position", "")).lower(), ""),
                                     size.get(str(c.get("size", "")).lower(), ""), frame) if x)
        who = (f"{c['name']} from {c.get('series', '')}, " if c.get("name") else "") + str(c.get("desc", ""))
        parts.append(f"{who} ({extra})" if extra else who)
    place0 = tp.get("title_place") or {"right": "top-right", "left": "top-left"}.get(spec.get("position"),
                                                                                    spec.get("position") or "top")
    spot = {"top-right": "the upper right corner", "top-left": "the upper left corner", "right": "the right side",
            "left": "the left side", "bottom": "the lower part", "bottom-right": "the lower right corner",
            "bottom-left": "the lower left corner", "center": "the center"}.get(place0, "the upper part")
    style = (" Modern anime manhwa digital illustration, sharp clean linework, cinematic lighting." if tp["anime"]
             else " Cinematic, dramatic lighting.")
    scene = ((" ".join(p.rstrip(".") + "." for p in parts) + " ") if parts else "") + \
        "Setting: " + str(tp.get("background", "")).rstrip(".") + "." + style + \
        f" Keep {spot} calmer (sky or soft light) for a title, as part of the same painting. No text, no letters, " \
        "no logos, no watermark."
    eng = "Alta calidad (Z-Image Turbo)" if "Alta calidad (Z-Image Turbo)" in have else have[0]
    neg = ia.ENGINES[eng].get("negative", ia.NEGATIVE)
    fandom = any(c.get("name") and c.get("series") for c in chars)
    if fandom and tp["anime"] and "Anime (Animagine XL 4)" in have:
        # personaje conocido: Animagine lo dibuja con su etiqueta (la escena se le pide en etiquetas)
        pl = ia.plan(scene, "Anime", "Anime (Animagine XL 4)", model=ia.ollama_model(), have=have, already_english=True)
        eng, scene, neg = pl["engine"], pl["prompt"], pl["negative"]
    must = list(tp.get("background_must") or [])
    for c in chars:
        must += [m for m in (c.get("must") or []) if m not in must]
    must = must[:6]
    tags = ia.ENGINES[eng].get("words") == "tags"
    ia.free_ollama_gpu()
    ia.start(say=lambda m, f: say(m, .05), cancel=cancel)
    img = os.path.join(WORK, f"auto_escena_{stamp}.png")
    best, best_miss = None, None
    for attempt in range(2 if must else 1):     # Gemma revisa la escena; si falta algo, otra vez reforzándolo
        if cancel is not None and cancel.is_set():
            raise RuntimeError("CANCELLED")
        out = img if attempt == 0 else img.replace(".png", f"_{attempt}.png")
        ia.generate(ia.emphasize(scene, best_miss or [], tags), out, eng, (1344, 768), "", cancel=cancel,
                    negative=neg, init_image=ref_bg, strength=.6,
                    say=lambda m, f: say("Escena: " + m, .06 + .7 * f))
        if not must or not ia.vision_model():
            best = out
            break
        say("Tu IA revisa que la escena tenga lo que pediste…", None)
        miss = ia.verify_image(out, must)
        if best_miss is None or len(miss) < len(best_miss):
            best, best_miss = out, miss
        if not miss:
            break
        say("A la escena le falta: " + "; ".join(miss) + ". La dibujo otra vez reforzando eso…", None)
    ia.release_vision()
    if best != img:
        Image.open(best).save(img)
    tp["background_missing"] = best_miss or []
    alts = []
    for j in range(max(0, int(versions) - 1)):   # versiones B y C: el mismo pedido, otra escena
        if cancel is not None and cancel.is_set():
            raise RuntimeError("CANCELLED")
        p = img.replace(".png", f"_v{j + 2}.png")
        ia.generate(ia.emphasize(scene, best_miss or [], tags), p, eng, (1344, 768), "", cancel=cancel,
                    negative=neg, init_image=ref_bg, strength=.6,
                    say=lambda m, f, j=j: say(f"Escena de la versión {'BC'[j]}: " + m, None))
        alts.append(p)
    glow = dominant_light(img)
    layers = [{"kind": "image", "path": img, "cover": True, "x": .5, "y": .5}]
    shade_side = _add_texts(text, tp, spec, layers)
    proj = {"size": [1280, 720], "layers": layers, "alt_backgrounds": alts, "mode": "single",
            "lock": {"layout": True,
                     "style": bool(spec.get("fill") or spec.get("stroke") or spec.get("style") != "Impacto")},
            "fx": {"shade": .45 if tp["title"] else 0, "shade_side": shade_side, "vignette": .45,
                   "embers": .5 if tp["embers"] else 0, "embers_color": glow}}
    say("Miniatura lista.", 1.0)
    return proj, tp



def _add_texts(text, tp, spec, layers):
    """Título y subtítulo con letras perfectas, donde y como los pediste. Devuelve el lado de la sombra."""
    shade_side = "top"
    if tp["title"]:
        place = tp.get("title_place") or {"right": "top-right", "left": "top-left"}.get(spec.get("position"),
                                                                                      spec.get("position") or "top")
        lay = {"kind": "text", "style": tp["title_style"]}
        side = "right" if place.endswith("right") else "left" if place.endswith("left") else ""
        if side:                                     # a un costado: dos líneas grandes
            y0 = {"top": .05, "bottom": .52}.get(place.split("-")[0], .22)
            lay.update(text=_split_title(tp["title"]), align=side, x=.965 if side == "right" else .035, y=y0,
                       size=.17 if place.startswith(("top", "bottom")) else .19, max_w=.5)
            shade_side = side
        elif place == "bottom":
            lay.update(text=tp["title"], align="center", x=.5, y=.72, size=.15 if len(tp["title"]) < 22 else .12)
            shade_side = "bottom"
        else:
            lay.update(text=tp["title"], align="center", x=.5, y=.035 if place == "top" else .4,
                       size=.15 if len(tp["title"]) < 22 else .12)
        if spec.get("fill"):
            lay["fill"] = spec["fill"]
        if spec.get("stroke"):
            lay["stroke"] = spec["stroke"]
            lay["stroke_w"] = .11 if spec.get("thick") else .075
            lay["glow"] = "#000000"             # sombra oscura: el borde de color resalta más
        if spec.get("glow"):                     # «brillo verde»: lo pediste tú
            lay["glow"] = spec["glow"]
        layers.append(lay)
    if tp["subtitle"]:
        tl = next((l for l in layers if l.get("kind") == "text"), None)
        if tl:                                       # junto al título: debajo (o encima si lo pediste)
            # se MIDE el título ya dibujado (antes se calculaba a ojo y «CAP 1-5» quedaba encima de «CRONOS»)
            try:
                timg, _tx, ty = M.render_text(tl, 1280, 720)
                bb = timg.getchannel("A").point(lambda v: 255 if v > 90 else 0).getbbox()
                below = (ty + (bb[3] if bb else timg.height)) / 720 + .01
            except Exception:
                below = tl["y"] + tl["size"] * ((tl["text"].count("\n") + 1) * 1.25 + .3)
            sub_y = max(.02, tl["y"] - .1) if tp.get("subtitle_place") == "above_title" else \
                (.86 if tp.get("subtitle_place") == "bottom" else min(.88, below))
            if tp.get("subtitle_place") == "above_title":
                tl["y"] = min(.8, tl["y"] + .09)
        else:
            sub_y = .22
        sl = {"kind": "text", "text": tp["subtitle"], "style": "Elegante", "x": tl.get("x", .5) if tl else .5,
              "y": sub_y, "size": .065, "align": tl.get("align", "center") if tl else "center"}
        ss = ia.title_spec(text, tp["subtitle"])          # «"CAP 1-5" en letras doradas con borde negro»
        if ss.get("fill") or ss.get("stroke"):
            sl.update(style="Impacto", size=.08)
            for k in ("fill", "stroke", "glow"):
                if ss.get(k):
                    sl[k] = ss[k]
            if ss.get("stroke"):
                sl["stroke_w"] = .1 if ss.get("thick") else .07
        layers.append(sl)
    return shade_side


def build(text, say=None, cancel=None, have=None, refs=(), screen=None, versions=1, on_plan=None, mode=None):
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
    saved = find_saved(text)
    wish = mode or mode_wish()
    if not (saved or ref_chars) and wish != "layers":
        why = ("Una sola imagen, como ChatGPT: tu IA escribe un prompt muy descriptivo y dibuja todo junto, título "
               "incluido." if wish == "single" else "Automática: una sola imagen, como ChatGPT.")
        return build_chatgpt(text, say, cancel, have, ref_bg, versions, stamp, model, on_plan, why)
    say("Tu IA separa el pedido en capas (fondo, personajes, título)…", .02)
    tp = thumb_plan(text, model, tuple(saved))
    spec = tp.get("title_spec") or ia.title_spec(text)
    form, why = decide_mode(text, tp, saved, ref_chars, wish)
    tp["mode"], tp["mode_reason"] = form, why
    if on_plan:                                   # la app muestra al instante lo que se va a dibujar (en inglés)
        try:
            on_plan(tp)
        except Exception:
            pass
    if form == "single":
        return build_single(text, tp, spec, say, cancel, have, ref_bg, versions, stamp)
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
            # el personaje va sobre una pantalla lisa: fuera los paisajes que la IA añade por su cuenta
            # («dark battlefield, stormy sky» estorban al recorte y no los pediste para el personaje)
            pl["prompt"] = ", ".join(t for t in pl["prompt"].split(", ") if not _SCENERY.search(t))
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
    place0 = tp.get("title_place") or {"right": "top-right", "left": "top-left"}.get(spec.get("position"),
                                                                                    spec.get("position") or "")
    tside = "right" if place0.endswith("right") else "left" if place0.endswith("left") else ""
    if tside and spec.get("position") not in ("left", "right"):
        spec = dict(spec, position=tside)           # el título va a un costado: los personajes al otro
    side_title = spec.get("position") in ("left", "right")
    xs = POS.get(n, POS[3])
    if side_title:                                # el título ocupa un costado: los personajes van en el otro
        xs = {"right": [.2, .36, .5], "left": [.5, .64, .8]}[spec["position"]]
        if n == 1:
            xs = [.27, .27, .27] if spec["position"] == "right" else [.73, .73, .73]
    sides = {"left": 0, "center": 1, "right": 2}
    used = set()
    top = .2 if tp["title"] and (place0 or "top") in ("", "top") else .05   # la cabeza bajo el título
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
    shade_side = _add_texts(text, tp, spec, layers)
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


def chapter_label(names):
    """«Capítulo 6: …» -> «CAP 6»; varios -> «CAP 1-5»; sin números -> el nombre corto en mayúsculas."""
    nums = []
    for n in names:
        m = re.search(r"\b(?:cap[íi]tulo|cap\.?|chapter|ch\.?)\s*(\d+)", str(n), re.I) or re.search(r"\b(\d+)\b", str(n))
        if m:
            nums.append(int(m.group(1)))
    if nums:
        a, b = min(nums), max(nums)
        return f"CAP {a}" if a == b else f"CAP {a}-{b}"
    return (str(names[0]) if names else "")[:24].upper()


def auto_cover(chapter_text, story, label, write, bible, out_png, say=None, cancel=None, vertical=False):
    """Miniatura automática de un capítulo (título de la obra + «CAP 6»), como tus ejemplos: un prompt estilo
    ChatGPT con el texto dibujado por la IA; Gemma revisa que esté bien escrito y, si no lo logra, la app pone
    las letras perfectas sobre la escena sin texto. Devuelve la ruta."""
    say = say or (lambda *_: None)
    title = (story or "").strip().upper()[:40]
    texts = [(title, "Top")] + ([(label, "Bottom center, smaller, on an ornamental plaque")] if label else [])
    pp = ia.poster_prompt(chapter_text, story, bible, write, vertical, texts=[t for t in texts if t[0]])
    if not pp:
        raise RuntimeError("no se pudo escribir el prompt de la miniatura")
    full = ia.drawable(pp, keep_text=True)
    size = (768, 1344) if vertical else (1344, 768)
    eng = "Alta calidad (Z-Image Turbo)"
    neg = "blurry, low quality, deformed, bad anatomy, misspelled text, extra text, watermark, signature"
    checks = [f'the text "{t}" is written correctly, letter by letter' for t, _w in texts if t]
    ia.free_ollama_gpu()
    ia.start(say=lambda m, f: say(m, None), cancel=cancel)
    best, ok = None, False
    for attempt in range(3):
        if cancel is not None and cancel.is_set():
            raise RuntimeError("CANCELLED")
        p = out_png if attempt == 0 else out_png.replace(".png", f"_{attempt}.png")
        ia.generate(full, p, eng, size, "", negative=neg, cancel=cancel,
                    say=lambda m, f: say("Miniatura: " + m, f))
        best = best or p
        if not ia.vision_model():
            ok = True
            break
        say("Tu IA lee el título letra por letra…", None)
        good = ia.text_ok(p, [t for t, _w in texts if t])
        if good is None:                            # no se pudo leer: la revisión de siempre
            good = not ia.verify_image(p, checks)
        if good:
            best, ok = p, True
            break
    ia.release_vision()
    for k in range(1, 3):                           # limpiar intentos
        q = out_png.replace(".png", f"_{k}.png")
        if q != best and os.path.isfile(q):
            try:
                os.remove(q)
            except OSError:
                pass
    if ok:
        if best != out_png:
            os.replace(best, out_png)
        return out_png
    # el seguro: escena sin texto y letras perfectas encima
    say("La IA no escribió bien el título: lo pongo yo con letras perfectas…", None)
    ia.start(say=lambda m, f: say(m, None), cancel=cancel)
    scene = os.path.join(WORK, "portada_sin_texto.png")
    os.makedirs(WORK, exist_ok=True)
    ia.generate(ia.drawable(pp), scene, eng, size, "", negative=neg + ", text, letters", cancel=cancel)
    tp = {"title": title, "subtitle": label, "title_style": "Cromo épico", "title_place": "top",
          "subtitle_place": "bottom"}
    layers = [{"kind": "image", "path": scene, "cover": True, "x": .5, "y": .5}]
    side = _add_texts("", tp, {"position": "top", "style": "Cromo épico"}, layers)
    proj = {"size": [size[0], size[1]], "layers": layers,
            "fx": {"shade": .5, "shade_side": side, "vignette": .4}}
    img = M.render(proj, size[0] * 1920 // 1344, size[1] * 1920 // 1344 if not vertical else size[1] * 1080 // 768)
    M.save_image(img.convert("RGB"), out_png)
    for q in (best,):
        if q and q != out_png and os.path.isfile(q):
            try:
                os.remove(q)
            except OSError:
                pass
    return out_png
