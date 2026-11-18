# -*- coding: utf-8 -*-
"""Ayuda de internet para las IA locales (fase 1): AniList y Wikipedia.

- Solo se usa si el usuario activa «Permitir internet» (apagado por defecto). Sin internet todo sigue igual.
- Se envían solo palabras de búsqueda (nombres de anime o personajes), nunca los textos del usuario.
- Lo que llega de internet se trata como DATOS: se limpia, se recorta y se entrega a la IA marcado como
  «datos de referencia» (no instrucciones).
- Caché local (%APPDATA%\\AudioNovelaStudio\\web_cache.json): lo buscado una vez funciona después sin conexión.
"""
import html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioNovelaStudio")
SETTINGS = os.path.join(CFG_DIR, "internet.json")
CACHE = os.path.join(CFG_DIR, "web_cache.json")
UA = "AudioNovelaStudio/1.1 (aplicacion de escritorio)"
TTL = 30 * 24 * 3600                 # un mes
_lock = threading.Lock()
_cache = None


# ------------------------------------------------------------------ interruptor
def enabled():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return bool(json.load(f).get("enabled", False))
    except Exception:
        return False


def set_enabled(on):
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump({"enabled": bool(on)}, f)
    except OSError:
        pass


# ------------------------------------------------------------------ caché
def _load():
    global _cache
    if _cache is None:
        try:
            with open(CACHE, encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    return _cache


def _get(key):
    with _lock:
        v = _load().get(key)
    if v and time.time() - v.get("t", 0) < TTL:
        return v.get("d")
    return None


def _put(key, data):
    with _lock:
        c = _load()
        c[key] = {"t": time.time(), "d": data}
        if len(c) > 600:                       # se quedan las más recientes
            for k in sorted(c, key=lambda k: c[k].get("t", 0))[:100]:
                c.pop(k, None)
        try:
            os.makedirs(CFG_DIR, exist_ok=True)
            with open(CACHE + ".part", "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False)
            os.replace(CACHE + ".part", CACHE)
        except OSError:
            pass


def _clean(text, limit=600):
    """Quita HTML, markdown y spoilers; deja texto plano corto."""
    t = html.unescape(text or "")
    t = re.sub(r"~!.*?!~", "", t, flags=re.S)                      # spoilers de AniList
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"[_*#>`]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit].rsplit(" ", 1)[0] + "…" if len(t) > limit else t


def _http_json(url, data=None, timeout=12):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"User-Agent": UA, "Accept": "application/json",
                                          **({"Content-Type": "application/json"} if data is not None else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(2_000_000).decode("utf-8", "replace"))


# ------------------------------------------------------------------ AniList (gratis, sin cuenta)
ANILIST = "https://graphql.anilist.co"
_Q_MEDIA = """query ($s: String) { Page(perPage: 2) { media(search: $s, type: ANIME, sort: SEARCH_MATCH) {
  title { romaji english native } siteUrl
  characters(perPage: 40, sort: [ROLE, RELEVANCE]) { nodes { name { full native alternative } } } } } }"""
_Q_CHAR = """query ($s: String) { Page(perPage: 10) { characters(search: $s, sort: SEARCH_MATCH) {
  name { full native } gender description(asHtml: false) siteUrl
  media(perPage: 2, sort: POPULARITY_DESC) { nodes { title { romaji english } } } } } }"""


def anime_characters(title):
    """Nombres de personajes de un anime. Devuelve {"anime": título, "names": [...], "url": ...} o None."""
    title = title.strip()
    if not title:
        return None
    key = "anime:" + title.lower()
    hit = _get(key)
    if hit is not None:
        return hit or None
    try:
        d = _http_json(ANILIST, {"query": _Q_MEDIA, "variables": {"s": title}})
        media = (d.get("data", {}).get("Page", {}).get("media") or [])
    except Exception:
        return None                                       # sin conexión: no se guarda nada
    if not media:
        _put(key, {})
        return None
    # a veces el primer resultado es una entrada sin personajes (especial, recopilación): se toma la más completa
    m = max(media, key=lambda x: len(x.get("characters", {}).get("nodes", [])))
    names = []
    for n in m.get("characters", {}).get("nodes", []):
        nm = n.get("name", {})
        if nm.get("full"):
            names.append(nm["full"].strip())
    t = m.get("title", {})
    out = {"anime": t.get("english") or t.get("romaji") or title, "names": names[:40], "url": m.get("siteUrl", "")}
    _put(key, out)
    return out


def character(name, series=""):
    """Datos de un personaje de anime: nombre, serie, género y descripción corta. None si no se encuentra.
    Con «series» se elige el personaje de esa obra (hay muchos «Hades»)."""
    name, series = name.strip(), (series or "").strip()
    if len(name) < 2:
        return None
    key = "char:" + name.lower() + "|" + series.lower()
    hit = _get(key)
    if hit is not None:
        return hit or None
    try:
        d = _http_json(ANILIST, {"query": _Q_CHAR, "variables": {"s": name}})
        chars = d.get("data", {}).get("Page", {}).get("characters") or []
    except Exception:
        return None
    if not chars:
        _put(key, {})
        return None
    def titles(c):
        return [x.get("title", {}).get("english") or x.get("title", {}).get("romaji") or "" for x in
                c.get("media", {}).get("nodes", [])]
    if series:
        words = [w for w in re.findall(r"\w+", series.lower()) if len(w) > 2]
        chars = [c for c in chars if any(all(w in t.lower() for w in words) for t in titles(c))]
        if not chars:
            _put(key, {})
            return None
    c = chars[0]
    media = titles(c)
    out = {"name": c.get("name", {}).get("full", name), "series": ", ".join(m for m in media if m),
           "gender": c.get("gender") or "", "description": _clean(c.get("description"), 700),
           "url": c.get("siteUrl", ""), "source": "AniList"}
    _put(key, out)
    return out


# ------------------------------------------------------------------ Wikipedia (resumen)
def wikipedia(term, lang="es"):
    """Resumen corto del artículo más parecido. None si no hay."""
    term = term.strip()
    if len(term) < 2:
        return None
    key = f"wiki:{lang}:{term.lower()}"
    hit = _get(key)
    if hit is not None:
        return hit or None
    try:
        q = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": term, "srlimit": 1,
                                    "format": "json", "utf8": 1})
        s = _http_json(f"https://{lang}.wikipedia.org/w/api.php?{q}")
        hits = s.get("query", {}).get("search", [])
        if not hits:
            _put(key, {})
            return None
        title = hits[0]["title"]
        p = _http_json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/" +
                       urllib.parse.quote(title.replace(" ", "_")))
    except Exception:
        return None
    out = {"name": p.get("title", title), "description": _clean(p.get("extract"), 700),
           "url": p.get("content_urls", {}).get("desktop", {}).get("page", ""), "source": f"Wikipedia ({lang})"}
    _put(key, out)
    return out


# ------------------------------------------------------------------ usos concretos
def split_topics(topic):
    """«anime: Gamers!, Golden Time, Seitokai Yakuindomo» -> ["Gamers!", "Golden Time", "Seitokai Yakuindomo"]"""
    t = re.sub(r"^\s*(anime|animes|serie|series|tema|manga)\s*:\s*", "", topic or "", flags=re.I)
    parts = [p.strip(" .") for p in re.split(r"[,;/\n]| y ", t) if p.strip(" .")]
    return [p for p in parts if 2 <= len(p) <= 60][:6]


def names_for_topic(topic, say=None):
    """Nombres de personajes de los animes del tema. Devuelve (nombres, fuentes)."""
    names, sources = [], []
    for t in split_topics(topic):
        (say or (lambda *_: None))(f"Buscando personajes de «{t}» en AniList…")
        a = anime_characters(t)
        if a and a.get("names"):
            names += [n for n in a["names"] if n not in names]
            sources.append(f"AniList: {a['anime']} ({len(a['names'])} nombres)")
    return names[:120], sources


def reference_facts(refs, say=None):
    """Datos de referencia para personajes o cosas conocidas pedidas en un dibujo. Devuelve (texto, fuentes)."""
    facts, sources = [], []
    for r in refs[:3]:
        if isinstance(r, dict):
            r, series = str(r.get("name", "")).strip(), str(r.get("series", "")).strip()
        else:
            r, series = str(r).strip(), ""
        if not r:
            continue
        (say or (lambda *_: None))(f"Buscando «{r}»…")
        c = character(r, series)
        if c and c.get("description"):
            facts.append(f"- {c['name']} ({c['series']}): {c['description']}")
            sources.append(f"AniList: {c['name']}")
            continue
        q = f"{r} {series}".strip()
        w = wikipedia(q, "es") or wikipedia(q, "en")
        if w and w.get("description"):
            facts.append(f"- {w['name']}: {w['description']}")
            sources.append(f"{w['source']}: {w['name']}")
    return "\n".join(facts), sources
