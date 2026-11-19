# -*- coding: utf-8 -*-
"""Estudio de Imágenes: ventana sencilla para crear imágenes con IA en tu PC (usa imagen_ia / ComfyUI).

Funciona sola (EstudioImagenes.exe) o dentro de Audio Novela Studio (botón «Crear con IA» de la portada).
"""
import datetime
import json
import os
import subprocess
import sys
import threading
import time
import traceback

import customtkinter as ctk

import ui_scroll

ui_scroll.install()             # la rueda mueve solo lo que está bajo el ratón (ver ui_scroll.py)

import ui_iconos                # iconos e ilustraciones dibujados por el propio Estudio
ui_iconos.install()             # tema de botones: iconos propios, esquinas y bordes (ver ui_iconos.py)
from PIL import Image

import imagen_ia as ia
import miniaturas as M

APP = "Estudio de Imágenes"
BG, SURF, SURF2, SURF3, LINE = "#070a12", "#0c1221", "#111a2e", "#18233c", "#1f2d4d"
TXT, MUTED, CYAN, CYAN_D, VIOLET, RED, GREEN = "#e7edff", "#7f8db3", "#22d3ee", "#0b7285", "#a78bfa", "#f87171", "#34d399"
AMBER = "#f5a524"
OUT_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "Imagenes IA")
CFG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioNovelaStudio", "estudio_imagenes.json")
ICON_THEMES = {"Neón": "neon", "Atardecer": "atardecer", "Sakura": "sakura", "Galaxia": "galaxia",
               "Minimal": "minimal"}
ICON_INI = os.path.join(os.path.dirname(CFG), "estudio_icono.ini")      # lo escribe el instalador
MAX_THUMBS = 60
CATEGORIES = {"Todo": None, "Anime": ["anime"], "Fotos": ["foto"], "Portadas y texto": ["texto"],
              "Arte": ["arte"], "Fondos": ["fondo"]}


def _example_cats(e):
    """Categorías de un ejemplo según su título y modelo (si el .json no las trae)."""
    t = (e.get("title", "") + " " + e.get("engine", "")).lower()
    c = []
    if "anime" in t or "animagine" in t:
        c.append("anime")
    if "foto" in t or "paisaje" in t:
        c.append("foto")
    if "texto" in t or "portada" in t or "título" in t:
        c.append("texto")
    if "fondo" in t or "paisaje" in t or "short" in t:
        c.append("fondo")
    if "arte" in t or "acuarela" in t or "avatar" in t or "fantás" in t:
        c.append("arte")
    return c or ["arte"]


PAGE_INSP, PAGE_MINE = "✨  Inspiración", "🖼  Mis imágenes"
QUICK = [("🌸 Anime", 0), ("🏯 Fondo para video", 1), ("📷 Foto realista", 2), ("🔤 Letrero con texto", 4),
         ("📚 Portada de libro", 5), ("🐉 Fantasía", 6), ("🎨 Acuarela", 7), ("🦊 Avatar", 9)]          # miniaturas en pantalla (más no hace falta y cuidan los recursos de Windows)


def font(size=13, weight="normal"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


def res_dir(*parts):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), *parts)


def icon_file(key, ext="ico"):
    p = res_dir("iconos_imagenes", f"{key}.{ext}")
    return p if os.path.isfile(p) else ""


def current_icon_theme():
    """Tema guardado en la app; si no hay, el que eligió el instalador; si no, Neón."""
    try:
        with open(CFG, encoding="utf-8") as f:
            k = json.load(f).get("icon_theme", "")
        if k in ICON_THEMES.values():
            return k
    except Exception:
        pass
    try:
        with open(ICON_INI, encoding="utf-8-sig") as f:
            for line in f:
                if line.strip().lower().startswith("tema="):
                    k = line.split("=", 1)[1].strip()
                    if k in ICON_THEMES.values():
                        return k
    except Exception:
        pass
    return "neon"


def update_shortcut_icons(key):
    """Cambia el icono de los accesos directos «Estudio de Imágenes» (escritorio y menú Inicio)."""
    src = icon_file(key)
    if not src:
        return
    try:
        dst_dir = os.path.join(os.path.dirname(CFG), "iconos")
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, f"estudio_{key}.ico")
        import shutil
        shutil.copyfile(src, dst)
        ps = ("$ws = New-Object -ComObject WScript.Shell; "
              "$dirs = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'), "
              "[Environment]::GetFolderPath('CommonDesktopDirectory'), [Environment]::GetFolderPath('CommonPrograms')); "
              "foreach ($d in $dirs) { if ($d) { Get-ChildItem -LiteralPath $d -Filter '*.lnk' -ErrorAction "
              "SilentlyContinue | Where-Object { $_.BaseName -like 'Estudio de Im*genes' } | ForEach-Object { "
              "try { $l = $ws.CreateShortcut($_.FullName); $l.IconLocation = '" + dst.replace("'", "''") + ",0'; "
              "$l.Save() } catch {} } } }")
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                       timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def log_error(where, exc_text):
    try:
        os.makedirs(os.path.dirname(CFG), exist_ok=True)
        path = os.path.join(os.path.dirname(CFG), "error.log")
        try:                                   # con límite: pasado 1 MB se guarda una copia y empieza uno nuevo
            if os.path.getsize(path) > 1_000_000:
                os.replace(path, path + ".anterior")
        except OSError:
            pass
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {APP} - {where}\n{exc_text}\n")
    except OSError:
        pass


class ImageStudio(ctk.CTkFrame):
    """Panel completo. on_use(ruta) añade el botón «Usar en Audio Novela»."""

    def __init__(self, master, on_use=None, use_label="Usar como portada", standalone=False):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._tema_iconos = True          # tema de botones (ui_iconos) dentro del Estudio
        self.on_use, self.cancel, self.busy = on_use, threading.Event(), False
        self.started_server = False
        self.current = None
        self._thumbs = {}          # ruta -> (botón, CTkImage)
        self._big = None
        cfg = self._load_cfg()
        self.out_dir = cfg.get("out_dir") if cfg.get("out_dir") and os.path.isdir(cfg.get("out_dir")) else OUT_DIR
        self.v_sfmt = ctk.StringVar(value=cfg.get("save_fmt") if cfg.get("save_fmt") in M.EXT_BY_NAME else "PNG")
        engines = ia.available_engines()
        self.has_engine = bool(engines)
        self.avail = engines
        self.engines = [ia.AUTO] + (engines or list(ia.ENGINES))
        self.ollama = ""

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(self, width=330, fg_color=SURF, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsw", padx=(12, 6), pady=12)
        right = ctk.CTkFrame(self, fg_color=SURF, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)

        # ---- controles
        logo = ui_iconos.art("crear", (36, 36))          # logo dibujado por el propio Estudio
        ctk.CTkLabel(left, text=("  " if logo else "🎨  ") + APP, image=logo, compound="left", font=font(19, "bold"),
                     text_color=TXT).pack(anchor="w", padx=8, pady=(6, 2))
        ctk.CTkLabel(left, text="Todo se hace en tu PC, sin internet.", font=font(12), text_color=MUTED).pack(anchor="w", padx=8)
        self._label(left, "Describe la imagen (puede ser en español)")
        self.txt = ctk.CTkTextbox(left, height=120, fg_color=SURF2, border_color=LINE, border_width=1, wrap="word",
                                  font=font(13))
        self.txt.pack(fill="x", padx=8)
        if cfg.get("last_prompt"):
            self.txt.insert("1.0", cfg["last_prompt"])
        brow = ctk.CTkFrame(left, fg_color="transparent")
        brow.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkButton(brow, text="💡 Ejemplos y consejos", height=28, width=10, font=font(12), fg_color=SURF3,
                      hover_color=CYAN_D, command=self.open_examples).pack(side="left")
        ctk.CTkButton(brow, text="🎬 Editor de miniaturas", height=28, width=10, font=font(12, "bold"),
                      fg_color="#7c2d12", hover_color="#c2410c", command=self.open_thumb).pack(side="left", padx=6)

        rrow = ctk.CTkFrame(left, fg_color="transparent")
        rrow.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkButton(rrow, text="📎 Subir imágenes de referencia", height=32, width=10, font=font(12, "bold"),
                      fg_color="#1e3a5f", hover_color=CYAN_D, border_color=CYAN_D, border_width=1,
                      command=self.pick_reference).pack(side="left")
        ctk.CTkButton(rrow, text="⌨", height=32, width=34, font=font(13), fg_color=SURF3, hover_color=CYAN_D,
                      command=self.show_keys).pack(side="right")
        self.lbl_ref = ctk.CTkLabel(rrow, text="", font=font(11), text_color=MUTED)
        self.lbl_ref.pack(side="left", padx=6)
        ctk.CTkLabel(left, text="Para editar una imagen tuya o inspirarse en ella (hasta 3; también Ctrl+V para "
                                "pegar). Escribe arriba qué cambiar: «ponle el pelo rojo», «de noche», «estilo "
                                "anime»… En miniaturas, los PNG transparentes se usan como personajes.",
                     font=font(11), text_color=MUTED, justify="left", wraplength=300).pack(anchor="w", padx=8)
        self.ref_box = ctk.CTkFrame(left, fg_color="transparent")
        self.ref_path = None             # la primera (la base); se mantiene por compatibilidad
        self.refs = []
        self.ref_thumbs = ctk.CTkFrame(self.ref_box, fg_color="transparent")
        self.ref_thumbs.pack(fill="x", pady=(2, 2))
        self.v_strength = ctk.DoubleVar(value=0.6)
        self.v_auto_str = ctk.BooleanVar(value=True)
        arow = ctk.CTkFrame(self.ref_box, fg_color="transparent")
        arow.pack(fill="x")
        ctk.CTkSwitch(arow, text="Mi IA decide cuánto cambiar", variable=self.v_auto_str, font=font(11),
                      progress_color=CYAN_D, command=self._auto_str_changed).pack(side="left")
        ctk.CTkButton(arow, text="✕ Quitar", width=60, height=24, fg_color=SURF3, hover_color=RED, font=font(11),
                      command=self.clear_reference).pack(side="right")
        self.str_box = ctk.CTkFrame(self.ref_box, fg_color="transparent")
        ctk.CTkLabel(self.str_box, text="Cuánto cambiar:  ← se parece  ·  solo inspiración →", font=font(11),
                     text_color=MUTED, justify="left", wraplength=300).pack(anchor="w", padx=(2, 0))
        ctk.CTkSlider(self.str_box, from_=0.25, to=0.95, variable=self.v_strength, progress_color=CYAN_D,
                      button_color=CYAN, width=260).pack(anchor="w")
        self.v_tr = ctk.BooleanVar(value=cfg.get("translate", True))
        self.sw_tr = ctk.CTkSwitch(left, text="Mi IA prepara la descripción", variable=self.v_tr,
                                   progress_color=CYAN_D, font=font(12))
        self.sw_tr.pack(anchor="w", padx=8, pady=(8, 0))
        self.lbl_tr = ctk.CTkLabel(left, text="Buscando Ollama…", font=font(11), text_color=MUTED, justify="left",
                                   wraplength=300)
        self.lbl_tr.pack(anchor="w", padx=8)
        import web_ayuda
        self.v_web = ctk.BooleanVar(value=web_ayuda.enabled())
        ctk.CTkSwitch(left, text="🌐 Permitir internet (AniList y Wikipedia)", variable=self.v_web,
                      progress_color=CYAN_D, font=font(12),
                      command=lambda: web_ayuda.set_enabled(self.v_web.get())).pack(anchor="w", padx=8, pady=(6, 0))
        ctk.CTkLabel(left, text="Si nombras un personaje o lugar conocido, busca cómo es de verdad. Solo envía esos "
                                "nombres.", font=font(11), text_color=MUTED, justify="left", wraplength=300).pack(
            anchor="w", padx=8)

        self._label(left, "Modelo")
        self.v_eng = ctk.StringVar(value=cfg.get("engine") if cfg.get("engine") in self.engines else ia.AUTO)
        self.m_eng = self._menu(left, self.engines, self.v_eng)
        self.v_eng.trace_add("write", lambda *_: self._eng_hint())
        self.lbl_eng = ctk.CTkLabel(left, text="", font=font(11), text_color=MUTED, justify="left", wraplength=300)
        self.lbl_eng.pack(anchor="w", padx=8)
        self._label(left, "Estilo")
        self.v_sty = ctk.StringVar(value=cfg.get("style") if cfg.get("style") in ia.STYLES else "Automático")
        self._menu(left, list(ia.STYLES), self.v_sty)
        self._label(left, "Formato")
        self.v_fmt = ctk.StringVar(value=cfg.get("format") if cfg.get("format") in ia.FORMATS else
                                   "Horizontal 16:9 (video, YouTube)")
        self._menu(left, list(ia.FORMATS) + [ia.CUSTOM], self.v_fmt)
        self.custom_row = ctk.CTkFrame(left, fg_color="transparent")
        self.v_cw = ctk.StringVar(value=str(cfg.get("custom_w", 1280)))
        self.v_ch = ctk.StringVar(value=str(cfg.get("custom_h", 720)))
        for txt, var in (("Ancho", self.v_cw), ("Alto", self.v_ch)):
            ctk.CTkLabel(self.custom_row, text=txt, font=font(12), text_color=MUTED).pack(side="left", padx=(0, 4))
            ctk.CTkEntry(self.custom_row, textvariable=var, width=70, fg_color=SURF2,
                         border_color=LINE).pack(side="left", padx=(0, 10))
        self.lbl_cs = ctk.CTkLabel(self.custom_row, text="", font=font(11), text_color=MUTED)
        self.lbl_cs.pack(side="left")
        self.fmt_anchor = ctk.CTkFrame(left, fg_color="transparent", height=1)
        self.fmt_anchor.pack(fill="x")
        self.v_fmt.trace_add("write", lambda *_: self._fmt_changed())
        for v in (self.v_cw, self.v_ch):
            v.trace_add("write", lambda *_: self._fmt_changed())
        self._label(left, "Cuántas")
        self.v_n = ctk.StringVar(value=str(cfg.get("count", 1)) if str(cfg.get("count", 1)) in "1234" else "1")
        ctk.CTkSegmentedButton(left, values=["1", "2", "3", "4"], variable=self.v_n, selected_color=CYAN_D,
                               unselected_color=SURF2, font=font(12)).pack(anchor="w", padx=8)
        jrow = ctk.CTkFrame(left, fg_color="transparent")
        jrow.pack(fill="x", padx=8, pady=(12, 0))
        ctk.CTkLabel(jrow, text="Juez de miniaturas", font=font(12, "bold"), text_color=TXT).pack(side="left")
        self.v_judge = ctk.StringVar(value=ia.judge_choice())
        self.seg_judge = ctk.CTkSegmentedButton(jrow, values=list(ia.JUDGES), variable=self.v_judge, font=font(12),
                                                selected_color=CYAN_D, unselected_color=SURF2,
                                                command=lambda v: ia.set_judge(v))
        self.seg_judge.pack(side="left", padx=8)
        ctk.CTkLabel(left, text="Rápido: ~30 s, cabe en tu tarjeta. Exigente (Gemma 4 12B): ~3 min, más estricto. "
                                "El pulido usa siempre el rápido.", font=font(11), text_color=MUTED, justify="left",
                     wraplength=300).pack(anchor="w", padx=8)
        import miniatura_auto as _ma
        frow = ctk.CTkFrame(left, fg_color="transparent")
        frow.pack(fill="x", padx=8, pady=(12, 0))
        ctk.CTkLabel(frow, text="Forma de la miniatura", font=font(12, "bold"), text_color=TXT).pack(side="left")
        self.v_form = ctk.StringVar(value=_ma.mode_choice())
        ctk.CTkOptionMenu(frow, values=list(_ma.MODES), variable=self.v_form, width=130, font=font(12),
                          fg_color=SURF3, button_color=SURF3, button_hover_color=CYAN_D,
                          command=lambda v: _ma.set_mode(v)).pack(side="left", padx=8)
        ctk.CTkLabel(left, text="«Una imagen» (recomendado, 2-4 min): como ChatGPT, tu IA escribe un prompt muy "
                                "descriptivo y dibuja todo junto, título incluido (si lo escribe mal, la app lo pone "
                                "con letras perfectas). «Por capas» (5-12 min): cada cosa aparte; se usa sola si nombras "
                                "un personaje guardado o subes su PNG.",
                     font=font(11), text_color=MUTED, justify="left", wraplength=300).pack(anchor="w", padx=8)
        srow = ctk.CTkFrame(left, fg_color="transparent")
        srow.pack(fill="x", padx=8, pady=(12, 0))
        ctk.CTkLabel(srow, text="Fondo para recortar personajes", font=font(12, "bold"), text_color=TXT).pack(
            side="left")
        self.v_screen = ctk.StringVar(value=ia.screen_choice())
        ctk.CTkOptionMenu(srow, values=list(ia.SCREEN_NAMES), variable=self.v_screen, width=120, font=font(12),
                          fg_color=SURF3, button_color=SURF3, button_hover_color=CYAN_D,
                          command=lambda v: ia.set_screen(v)).pack(side="left", padx=8)
        ctk.CTkLabel(left, text="Los personajes de las miniaturas se dibujan sobre una «pantalla» de color (como la "
                                "verde del cine) y se recorta. Automático: verde; si el personaje lleva verde, azul; "
                                "si lleva verde y azul, magenta.", font=font(11), text_color=MUTED, justify="left",
                     wraplength=300).pack(anchor="w", padx=8)
        self.v_det = ctk.BooleanVar(value=cfg.get("detail", True))
        ctk.CTkSwitch(left, text="Más detalle (2.ª pasada, 1,5x más grande)", variable=self.v_det,
                      progress_color=CYAN_D, font=font(12)).pack(anchor="w", padx=8, pady=(12, 0))
        ctk.CTkLabel(left, text="El mismo modelo agranda y repasa los detalles finos. Tarda ~2x.", font=font(11),
                     text_color=MUTED, justify="left", wraplength=300).pack(anchor="w", padx=8)

        self.btn = ctk.CTkButton(left, text="Crear imagen", height=50, corner_radius=14, font=font(16, "bold"),
                                 fg_color=CYAN_D, hover_color="#0e94a8", border_width=2, border_color="#3fd5ec",
                                 text_color="#ffffff", command=self.toggle)
        self.btn.pack(fill="x", padx=8, pady=(16, 6))
        self.pb = ctk.CTkProgressBar(left, progress_color=CYAN, fg_color=SURF2)
        self.pb.set(0)
        self.pb.pack(fill="x", padx=8)
        self.lbl = ctk.CTkLabel(left, text="", font=font(12), text_color=MUTED, justify="left", wraplength=300)
        self.lbl.pack(anchor="w", padx=8, pady=(4, 0))
        self.lbl_why = ctk.CTkLabel(left, text="", font=font(11), text_color=VIOLET, justify="left", wraplength=300)
        self.lbl_why.pack(anchor="w", padx=8, pady=(2, 0))
        self.btn_title = ctk.CTkButton(left, text="", height=34, font=font(12, "bold"), fg_color="#c2410c",
                                       hover_color="#ea580c", command=self._title_to_editor)
        self._pending_title = None
        self._label(left, "Lo que se envía al dibujo (inglés)")
        self.en = ctk.CTkTextbox(left, height=90, fg_color=SURF2, border_color=LINE, border_width=1, wrap="word",
                                 font=font(11), text_color=MUTED)
        self.en.pack(fill="x", padx=8, pady=(0, 8))
        self._label(left, "Dónde y en qué formato se guardan")
        srow = ctk.CTkFrame(left, fg_color="transparent")
        srow.pack(fill="x", padx=8)
        self._menu_small = ctk.CTkOptionMenu(srow, values=list(M.EXT_BY_NAME), variable=self.v_sfmt, width=90,
                                             fg_color=SURF3, button_color=SURF3, button_hover_color=CYAN_D,
                                             dropdown_fg_color=SURF2, command=lambda _v: self._save_cfg())
        self._menu_small.pack(side="left")
        ctk.CTkButton(srow, text="📁 Cambiar carpeta…", height=28, width=10, font=font(12), fg_color=SURF3,
                      hover_color=CYAN_D, command=self.pick_out_dir).pack(side="left", padx=6)
        self.lbl_out = ctk.CTkLabel(left, text="", font=font(11), text_color=MUTED, justify="left", wraplength=300)
        self.lbl_out.pack(anchor="w", padx=8, pady=(2, 8))
        self._show_out()
        self._icon_imgs = {}
        if standalone:                 # tema del icono (solo en la app aparte; dentro de Audio Novela no aplica)
            self._label(left, "Tema del icono de la app")
            irow = ctk.CTkFrame(left, fg_color="transparent")
            irow.pack(anchor="w", padx=8, pady=(0, 10))
            self.icon_theme = current_icon_theme()
            self._icon_btns = {}
            for name, key in ICON_THEMES.items():
                png = icon_file(key, "png")
                img = None
                if png:
                    try:
                        with Image.open(png) as im:
                            img = ctk.CTkImage(im.convert("RGBA").resize((34, 34), Image.Resampling.LANCZOS),
                                               size=(34, 34))
                    except Exception:
                        img = None
                self._icon_imgs[key] = img
                b = ctk.CTkButton(irow, image=img, text="" if img else name[:3], width=46, height=46,
                                  fg_color=CYAN_D if key == self.icon_theme else "transparent", hover_color=SURF3,
                                  border_width=0, command=lambda k=key: self.set_icon_theme(k))
                b.pack(side="left", padx=(0, 3))
                self._icon_btns[key] = b
            self.lbl_icon = ctk.CTkLabel(left, text="", font=font(11), text_color=MUTED)
            self.lbl_icon.pack(anchor="w", padx=8)
            self._icon_name()

        # ---- arriba: Inspiración (lo primero que se ve) | Mis imágenes
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(right, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
        self.v_page = ctk.StringVar(value=PAGE_INSP)
        tabs = ctk.CTkFrame(top, fg_color=SURF2, corner_radius=14, border_width=1, border_color=LINE)
        tabs.pack(side="left")
        self._tabs = {}
        for name, ico, label in ((PAGE_INSP, "inspiracion", "Inspiración"), (PAGE_MINE, "galeria", "Mis imágenes")):
            b = ctk.CTkButton(tabs, text=label, image=ui_iconos.icon(ico, 22), compound="left", height=38, width=160,
                              corner_radius=11, font=font(14, "bold"), fg_color="transparent", hover_color=SURF3,
                              text_color=MUTED, command=lambda n=name: self.show_page(n))
            b.pack(side="left", padx=4, pady=4)
            self._tabs[name] = b
        self.lbl_count = ctk.CTkLabel(top, text="", font=font(12), text_color=MUTED)
        self.lbl_count.pack(side="right")
        self.page_insp = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.page_insp.grid(row=1, column=0, sticky="nsew", padx=4, pady=(6, 6))
        self.page_mine = mine = ctk.CTkFrame(right, fg_color="transparent")
        mine.grid(row=1, column=0, sticky="nsew")
        mine.grid_columnconfigure(0, weight=1)
        mine.grid_rowconfigure(0, weight=5)
        mine.grid_rowconfigure(2, weight=2)
        right = mine            # la vista grande y la galería van dentro de «Mis imágenes»
        # la vista grande va en un marco de tamaño fijo y la imagen se centra con place(): así la imagen nunca
        # empuja el diseño (antes crecía, volvía a medirse y se dibujaba encima, como un «glitch»)
        self.view_box = ctk.CTkFrame(right, fg_color=SURF2, corner_radius=10)
        self.view_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))
        self.view_box.grid_propagate(False)
        self._empty_art = ui_iconos.art("vacio", (220, 220))
        self.view = ctk.CTkLabel(self.view_box, text="Aquí aparecerá tu imagen", font=font(14), text_color=MUTED,
                                 image=self._empty_art, compound="top",
                                 fg_color="transparent")
        self.view.place(relx=0.5, rely=0.5, anchor="center")
        self._big_job, self._big_key, self._pil = None, None, None
        self.view_box.bind("<Configure>", lambda _e: self._big_later())
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=10)
        self.act_btns = []
        if on_use:
            self.act_btns.append(self._small(bar, "✔ " + use_label, self._use, CYAN_D))
        for t, f in (("⋯ Más", self.more_menu), ("🎬 Usar en miniatura", lambda: self.open_thumb(self.current)),
                     ("Otra parecida", self.variation), ("Guardar como…", self.save_as),
                     ("Abrir carpeta", self.open_folder)):
            self.act_btns.append(self._small(bar, t, f))
        for b in self.act_btns:
            b.pack(side="right", padx=(6, 0))
        # el texto va después: así los botones nunca se cortan (el texto se acorta si no cabe)
        self.info = ctk.CTkLabel(bar, text="", font=font(11), text_color=MUTED, anchor="w")
        self.info.pack(side="left", fill="x", expand=True)
        self.gal = ctk.CTkScrollableFrame(right, fg_color=SURF2, corner_radius=10, label_text="Tus imágenes",
                                          label_font=font(12), label_fg_color=SURF3)
        self.gal.grid(row=2, column=0, sticky="nsew", padx=10, pady=(6, 10))
        self._eng_hint()
        self._fmt_changed()
        self._load_gallery()
        self._build_inspiration(self.page_insp)
        self.show_page(PAGE_INSP)
        if not self.has_engine:
            self._status("Esta PC todavía no tiene el motor de imágenes. Pulsa el botón: te explico qué se descarga, "
                         "cuánto pesa, y lo instalo y dejo funcionando.", AMBER)
            self.btn.configure(text="Instalar imágenes con IA…", command=self.open_setup)
            if standalone:
                self.after(900, self.open_setup)
        threading.Thread(target=self._find_ollama, daemon=True).start()
        self.after(300, self._bind_keys)
        self.after(60, lambda: ui_iconos.apply(self))
        self.after(8000, self._cleanup_later)

    def _cleanup_later(self):
        """Limpieza silenciosa por detrás: intentos descartados de miniaturas con más de 2 días."""
        import miniatura_auto

        def work():
            try:
                miniatura_auto.cleanup_work([self.out_dir])
            except Exception:
                log_error("limpieza", traceback.format_exc())
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- atajos de teclado
    KEYS = (("Ctrl+Enter", "Crear imagen"), ("Esc", "Cancelar lo que se está creando"),
            ("Ctrl+V", "Pegar una imagen copiada como referencia"), ("Ctrl+O", "Subir imágenes de referencia"),
            ("Ctrl+S", "Guardar como… (cualquier formato)"), ("Ctrl+D", "Otra parecida"),
            ("Ctrl+E", "Abrir en el editor de miniaturas"), ("Ctrl+U", "Ampliar 2x"),
            ("Ctrl+B", "Quitar el fondo"), ("Ctrl+R", "Revisar como miniatura"),
            ("Ctrl+1 / Ctrl+2", "Inspiración / Mis imágenes"), ("← →", "Imagen anterior / siguiente"),
            ("Ctrl+Shift+O", "Abrir la carpeta"), ("F1", "Ejemplos y consejos"), ("F11", "Pantalla completa"),
            ("Ctrl+K", "Ver estos atajos"))

    def _bind_keys(self):
        top = self.winfo_toplevel()
        # el cuadro de texto de Tk trae atajos de Linux (Ctrl+K borra la línea, Ctrl+O mete una línea, Ctrl+D y
        # Ctrl+H borran letras): en Windows nadie los espera y chocaban con los atajos de la app
        for cls in ("Text", "Entry"):
            for seq in ("<Control-Key-k>", "<Control-Key-o>", "<Control-Key-d>", "<Control-Key-h>"):
                try:
                    self.bind_class(cls, seq, "")
                except Exception:
                    pass

        def typing(e):
            try:
                return e.widget.winfo_class() in ("Entry", "Text", "TEntry")
            except Exception:
                return False

        def k(seq, fn, when_typing=True):
            def h(e):
                if typing(e) and not when_typing:
                    return None
                try:
                    r = fn(e)
                except Exception:
                    log_error("atajo " + seq, traceback.format_exc())
                    return "break"
                return None if r is False else "break"
            top.bind(seq, h, add="+")
        k("<Control-Return>", lambda e: None if self.busy else self.toggle())
        k("<Control-KP_Enter>", lambda e: None if self.busy else self.toggle())
        k("<Escape>", lambda e: self.toggle() if self.busy else False)
        k("<Control-v>", lambda e: self.paste_reference())      # si no es imagen, se pega el texto normal
        k("<Control-o>", lambda e: self.pick_reference())
        k("<Control-s>", lambda e: self.save_as())
        k("<Control-d>", lambda e: self.variation())
        k("<Control-e>", lambda e: self.open_thumb(self.current))
        k("<Control-u>", lambda e: self._tool("upscale", 2))
        k("<Control-b>", lambda e: self._tool("cut"))
        k("<Control-r>", lambda e: self._tool("review"))
        k("<Control-Key-1>", lambda e: self.show_page(PAGE_INSP))
        k("<Control-Key-2>", lambda e: self.show_page(PAGE_MINE))
        k("<Control-O>", lambda e: self.open_folder())
        k("<F1>", lambda e: self.open_examples())
        k("<Control-k>", lambda e: self.show_keys())
        k("<Left>", lambda e: self._step(-1), when_typing=False)
        k("<Right>", lambda e: self._step(1), when_typing=False)
        k("<F11>", lambda e: top.attributes("-fullscreen", not top.attributes("-fullscreen")))

    def _step(self, d):
        order = list(self._thumbs)
        if not order:
            return
        i = order.index(self.current) if self.current in order else -1
        self.select(order[max(0, min(len(order) - 1, i + d))])
        self.show_page(PAGE_MINE)

    def show_keys(self):
        w = ctk.CTkToplevel(self)
        w.title("Atajos de teclado")
        w.configure(fg_color=BG)
        w.resizable(False, False)
        ctk.CTkLabel(w, text="⌨  Atajos de teclado", font=font(17, "bold"), text_color=TXT).pack(padx=18, pady=(14, 8),
                                                                                              anchor="w")
        box = ctk.CTkFrame(w, fg_color=SURF, corner_radius=10)
        box.pack(fill="both", padx=14, pady=(0, 8))
        for i, (key, what) in enumerate(self.KEYS):
            ctk.CTkLabel(box, text=key, font=font(12, "bold"), text_color=CYAN, anchor="w", width=130).grid(
                row=i, column=0, sticky="w", padx=(12, 6), pady=2)
            ctk.CTkLabel(box, text=what, font=font(12), text_color=TXT, anchor="w").grid(row=i, column=1, sticky="w",
                                                                                         padx=(0, 12), pady=2)
        ctk.CTkLabel(w, text="En el editor de miniaturas: Ctrl+Z deshacer, Supr borrar capa, flechas mover, + / − "
                             "tamaño, Tab siguiente capa.", font=font(11), text_color=MUTED, wraplength=380,
                     justify="left").pack(padx=16, pady=(0, 12), anchor="w")
        w.after(100, lambda: (w.lift(), w.focus_force()))
        w.bind("<Escape>", lambda e: w.destroy())

    # ---------------------------------------------------------------- portada de inspiración
    def show_page(self, name=None):
        name = name or self.v_page.get()
        self.v_page.set(name)
        for tab_name, b in getattr(self, "_tabs", {}).items():
            on = tab_name == name
            b.configure(fg_color=CYAN_D if on else "transparent", hover_color=CYAN_D if on else SURF3,
                        text_color="#ffffff" if on else MUTED)
        if name == PAGE_MINE:
            self.page_insp.grid_remove()
            self.page_mine.grid()
        else:
            self.page_mine.grid_remove()
            self.page_insp.grid()
        n = len(self._thumbs)
        self.lbl_count.configure(text=f"{n} imagen{'es' if n != 1 else ''} tuya{'s' if n != 1 else ''}" if n else "")

    def _build_inspiration(self, page):
        self._ex = load_examples()
        self._insp_imgs, self._cards, self._insp_cols = [], [], 0
        hero = ctk.CTkFrame(page, fg_color=SURF2, corner_radius=16)
        hero.pack(fill="x", padx=8, pady=(4, 10))
        top = ctk.CTkFrame(hero, fg_color="transparent")
        top.pack(fill="x")
        himg = ui_iconos.art("portada", (300, 132))      # ilustración dibujada por el propio Estudio
        if himg is not None:
            ctk.CTkLabel(top, image=himg, text="", corner_radius=12).pack(side="right", padx=(8, 16), pady=(14, 4))
        ctk.CTkLabel(top, text="¿Qué quieres crear hoy?", font=font(28, "bold"), text_color=TXT).pack(
            anchor="w", padx=22, pady=(18, 0))
        ctk.CTkLabel(top, text="Escribe tu idea en español a la izquierda, o empieza con una de estas. Tu IA elige el "
                               "mejor modelo y dibuja en tu PC, sin internet.", font=font(13), text_color=MUTED,
                     justify="left", wraplength=560 if himg is not None else 900).pack(anchor="w", padx=22,
                                                                                      pady=(2, 10))
        chips = ctk.CTkFrame(hero, fg_color="transparent")
        chips.pack(fill="x", padx=18, pady=(0, 16))
        self._chips = [ctk.CTkButton(chips, text="🎬 Miniatura para YouTube", height=30, width=10, corner_radius=15,
                                     font=font(12, "bold"), fg_color="#c2410c", hover_color="#ea580c",
                                     command=self.open_thumb)]
        for label, idx in QUICK:
            if idx < len(self._ex):
                self._chips.append(ctk.CTkButton(chips, text=label, height=30, width=10, corner_radius=15,
                                                 font=font(12), fg_color=SURF3, hover_color=CYAN_D, border_width=1,
                                                 border_color=LINE,
                                                 command=lambda e=self._ex[idx]: self._use_example(e)))
        # las sugerencias pasan a otra fila si no caben (antes la última salía cortada: «Acuarel…»)
        chips.bind("<Configure>", lambda e: self._flow_chips(e.width), add="+")
        self._flow_chips(900)
        cats = ctk.CTkFrame(page, fg_color="transparent")
        cats.pack(fill="x", padx=10, pady=(0, 4))
        self.v_cat = ctk.StringVar(value="Todo")
        ctk.CTkSegmentedButton(cats, values=list(CATEGORIES), variable=self.v_cat, font=font(12),
                               selected_color=CYAN_D, unselected_color=SURF2,
                               command=lambda _v: self._layout_cards(force=True)).pack(side="left")
        self.grid_insp = ctk.CTkFrame(page, fg_color="transparent")
        self.grid_insp.pack(fill="both", expand=True, padx=4)
        for e in self._ex:
            self._cards.append(self._card(self.grid_insp, e))
        if not self._ex:
            ctk.CTkLabel(self.grid_insp, text="(No se encontraron los ejemplos)", text_color=MUTED).pack(pady=30)
        foot = ctk.CTkFrame(page, fg_color="transparent")
        foot.pack(fill="x", padx=8, pady=(6, 12))
        ctk.CTkButton(foot, text="💡 Consejos para describir mejor y cómo trabajan los modelos", height=34,
                      font=font(12), fg_color=SURF3, hover_color=CYAN_D, command=self.open_examples).pack(side="left")
        # add="+": sin él se borraba el aviso con el que el deslizador sabe hasta dónde llega la página, y
        # Inspiración no se deslizaba aunque tenía tarjetas más abajo
        page.bind("<Configure>", lambda _e: self.after_idle(self._layout_cards), add="+")
        self.after(300, self._layout_cards)

    def _flow_chips(self, width):
        """Coloca las sugerencias rápidas una tras otra y pasa a otra fila cuando no caben (sin cortar ninguna)."""
        if width < 50 or getattr(self, "_chips_w", None) == width or not self._chips:
            return
        self._chips_w = width
        x = y = 0
        rowh = 0
        for b in self._chips:
            w, h = b.winfo_reqwidth(), b.winfo_reqheight()
            if x and x + w > width:
                x, y = 0, y + rowh + 6
            b.place(x=x, y=y)
            x += w + 8
            rowh = max(rowh, h)
        self._chips[0].master.configure(height=y + rowh + 2)

    def _card(self, parent, e):
        card = ctk.CTkFrame(parent, fg_color=SURF2, corner_radius=14, border_width=1, border_color=LINE)
        img_lbl = None
        try:
            with Image.open(os.path.join(examples_dir(), e["file"])) as im:
                im = im.convert("RGB")
                k = min(330 / im.width, 230 / im.height)
                size = (int(im.width * k), int(im.height * k))
                img = ctk.CTkImage(im.resize(size, Image.Resampling.LANCZOS), size=size)
            self._insp_imgs.append(img)
            img_lbl = ctk.CTkLabel(card, image=img, text="", cursor="hand2")
            img_lbl.pack(padx=10, pady=(10, 6))
            img_lbl.bind("<Button-1>", lambda _ev, e=e: self._use_example(e))
        except Exception:
            pass
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12)
        ctk.CTkLabel(row, text=e["title"], font=font(14, "bold"), text_color=TXT).pack(side="left")
        model = e["engine"].split("(")[-1].rstrip(")")
        ctk.CTkLabel(row, text=f" {model} ", font=font(11, "bold"), text_color="#0b0f1a", fg_color=VIOLET,
                     corner_radius=8).pack(side="right")
        txt = e["prompt_es"] if len(e["prompt_es"]) <= 120 else e["prompt_es"][:117].rsplit(" ", 1)[0] + "…"
        ctk.CTkLabel(card, text="«" + txt + "»", font=font(11), text_color=MUTED, justify="left",
                     wraplength=320).pack(anchor="w", padx=12, pady=(4, 6))
        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(btns, text="✨ Crear ahora", height=30, width=10, font=font(12, "bold"), fg_color=CYAN_D,
                      hover_color=CYAN, command=lambda e=e: self._create_example(e)).pack(side="left")
        ctk.CTkButton(btns, text="Usar la idea", height=30, width=10, font=font(12), fg_color=SURF3,
                      hover_color=LINE, command=lambda e=e: self._use_example(e)).pack(side="left", padx=6)
        ctk.CTkLabel(btns, text=f"~{e.get('seconds', '?')} s", font=font(11), text_color=MUTED).pack(side="right")
        return card

    def _layout_cards(self, force=False):
        try:
            w = self.page_insp.winfo_width()
            scale = ctk.ScalingTracker.get_widget_scaling(self)
            cols = max(1, min(4, int(w / scale) // 365))
            if cols == self._insp_cols and not force:
                return
            self._insp_cols = cols
            for c in range(4):
                self.grid_insp.grid_columnconfigure(c, weight=1 if c < cols else 0, uniform="cards" if c < cols else "")
            want = CATEGORIES.get(getattr(self, "v_cat", None) and self.v_cat.get() or "Todo")
            k = 0
            for card, e in zip(self._cards, self._ex):
                if want and not (set(want) & set(e.get("cats") or _example_cats(e))):
                    card.grid_remove()
                    continue
                card.grid(row=k // cols, column=k % cols, sticky="nsew", padx=6, pady=6)
                k += 1
        except Exception:
            pass

    def _create_example(self, e):
        self._use_example(e)
        if self.has_engine and not self.busy:
            self.toggle()

    # ---------------------------------------------------------------- tema del icono
    def _icon_name(self):
        name = next((n for n, k in ICON_THEMES.items() if k == self.icon_theme), "")
        self.lbl_icon.configure(text=f"Tema: {name} (también cambia los accesos directos)")

    def set_icon_theme(self, key):
        self.icon_theme = key
        for k, b in self._icon_btns.items():
            b.configure(fg_color=CYAN_D if k == key else "transparent")
        self._icon_name()
        ico = icon_file(key)
        if ico:
            try:
                self.winfo_toplevel().iconbitmap(default=ico)
                self.winfo_toplevel().iconbitmap(ico)
            except Exception:
                pass
        self._save_cfg()
        threading.Thread(target=update_shortcut_icons, args=(key,), daemon=True).start()

    # ---------------------------------------------------------------- miniatura automática
    def _work_thumb(self, prompt, say, opts=None):
        """Miniatura por capas: fondo + personajes sin fondo + título. Se guarda y se puede abrir en el editor."""
        import miniatura_auto
        try:
            self._ui(lambda: self.lbl_why.configure(text="Pediste una miniatura: la armo por capas (fondo, personajes "
                                                         "con fondo transparente y título con letras perfectas)."))
            def show_plan(tp):
                gen_es = {"female": "mujer", "male": "hombre"}
                if tp.get("prompt_full"):                   # una imagen: el prompt completo que recibe la IA
                    txt = ("FORMA: una imagen — " + tp.get("mode_reason", "") + "\n\nPROMPT:\n" + tp["prompt_full"] +
                           ("\n\n" + tp["review_note"] if tp.get("review_note") else ""))
                    why = " ".join(x for x in (tp.get("mode_reason"), tp.get("review_note")) if x)
                    self._ui(lambda: (self.en.delete("1.0", "end"), self.en.insert("1.0", txt),
                                      self.lbl_why.configure(text=why)))
                    return
                txt = (("FORMA: " + ("una imagen" if tp.get("mode") == "single" else "por capas") + " — " +
                        tp.get("mode_reason", "") + "\n\n" if tp.get("mode_reason") else "") +
                       "FONDO: " + tp.get("background", "") + "\n\nPERSONAJES:\n" +
                       ("\n".join("• " + (f"[{gen_es[c['gender']]}] " if c.get("gender") in gen_es else "") +
                                  str(c.get("desc") or "") for c in tp.get("characters", [])) or "sin personajes") +
                       (f"\n\nTÍTULO: «{tp['title']}»" if tp.get("title") else "") +
                       ("\n\n" + tp["review_note"] if tp.get("review_note") else ""))
                why = " ".join(x for x in (tp.get("mode_reason"), tp.get("review_note")) if x)
                self._ui(lambda: (self.en.delete("1.0", "end"), self.en.insert("1.0", txt),
                                  self.lbl_why.configure(text=why)))
            say("Tu IA lee el pedido, decide la forma y Gemma revisa que no falte nada (~1 min)…", .02)
            proj, tp = miniatura_auto.build(prompt, say, self.cancel, have=self.avail,
                                            refs=list(getattr(self, "refs", []) or []),
                                            versions=(opts or {}).get("versions", 1), on_plan=show_plan)
            self.started_server = True
            out_dir, ext = self.out_dir, (opts or {}).get("ext", ".png")
            os.makedirs(out_dir, exist_ok=True)
            stamp = datetime.datetime.now().strftime("miniatura_%Y%m%d_%H%M%S")
            versions = (opts or {}).get("versions", 1)          # «Cuántas» = cuántas versiones (A, B, C)
            variants = miniatura_auto.make_variants(proj, versions)
            paths, notes = [], {}
            for j, pv in enumerate(variants):
                say(f"Guardando la versión {'ABC'[j]} en alta calidad…", .96)
                pth = os.path.join(out_dir, stamp + (f"_{'ABC'[j]}" if versions > 1 else "") + ext)
                miniatura_auto.save(pv, pth, 1920, 1080)
                paths.append(pth)
            best, verdict = paths[0], ""
            if versions > 1 and ia.vision_model():            # la IA mira cada versión y recomienda una
                ia.stop() if self.started_server else None
                self.started_server = False
                for j, pth in enumerate(paths):
                    if self.cancel.is_set():
                        break
                    say(f"Tu IA revisa la versión {'ABC'[j]} de {versions} (~30 s cada una)…", .97)
                    try:
                        notes[pth] = ia.critique_thumbnail(pth, model=ia.fast_judge())
                    except Exception:
                        pass
                if notes:
                    best = max(notes, key=lambda p: notes[p].get("nota", 0))
                    bj = paths.index(best)
                    tips = "; ".join(notes[best].get("mejorar", [])[:2])
                    verdict = (f"La IA recomienda la versión {'ABC'[bj]} ({notes[best].get('nota')}/10). " +
                               " · ".join(f"{'ABC'[j]}: {notes[p].get('nota', '?')}" for j, p in enumerate(paths)
                                          if p in notes) + (f". Para mejorarla: {tips}" if tips else ""))
            if ia.vision_model() and not self.cancel.is_set():      # pulir la elegida hasta superar tu nivel
                bj = paths.index(best)
                say("Tu IA pule la miniatura elegida (varias rondas, ~1-2 min)…", .975)
                pol, score, hist = miniatura_auto.improve(variants[bj], cancel=self.cancel,
                                                          say=lambda m, f: say(m, .975))
                start = hist[0][1] if hist else 0
                if score >= start:
                    miniatura_auto.save(pol, best, 1920, 1080)
                    notes[best] = dict(notes.get(best, {}), nota=score)
                verdict = (verdict + " " if verdict else "") + \
                    f"Pulida: {start} → {score}/10 en {len(hist)} ronda(s). " + miniatura_auto.JUDGE_SCALE
            for j, pth in enumerate(paths):
                meta = dict(prompt=prompt, kind="miniatura", engine="Miniatura por capas",
                            style=tp.get("title_style", ""), size=[1920, 1080], seed="",
                            reason=(f"Versión {'ABC'[j]} · " if versions > 1 else "") +
                            f"{len(tp['characters'])} personaje(s), título «{tp['title']}»" +
                            (f" · nota IA {notes[pth].get('nota')}/10" if pth in notes else ""),
                            created=datetime.datetime.now().isoformat(timespec="seconds"))
                with open(os.path.splitext(pth)[0] + ".json", "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=1)
            path = best
            gen_es = {"female": "mujer", "male": "hombre"}
            names = "\n".join("• " + (f"[{gen_es[c['gender']]}] " if c.get("gender") in gen_es else "") +
                              (c.get("desc") or "")[:90] for c in tp["characters"]) or "sin personajes"
            msg = verdict or f"Miniatura lista: {path}"
            if tp.get("background_missing"):
                msg += " Ojo: al fondo aún le falta " + "; ".join(tp["background_missing"]) + \
                    " (prueba «Otra parecida» o cámbialo en el editor)."
            self._ui(lambda: ([self._add_thumb(p, first=True) for p in paths], self.select(path),
                              self.show_page(PAGE_MINE), self._status(msg, GREEN),
                              self.en.delete("1.0", "end"),
                              self.en.insert("1.0", "FONDO: " + tp["background"] + "\n\nPERSONAJES: " + names),
                              self._offer_layers(path)))
        except RuntimeError as e:
            msg = "Cancelado." if str(e) == "CANCELLED" else str(e)
            self._ui(lambda: self._status(msg, MUTED if msg == "Cancelado." else RED))
        except Exception as e:
            log_error("miniatura automática", traceback.format_exc())
            self._ui(lambda e=e: self._status(f"Algo falló: {e}", RED))
        finally:
            def done():
                self.busy = False
                self.btn.configure(text="Crear imagen", fg_color=CYAN_D, hover_color=CYAN)
            self._ui(done)

    def _offer_layers(self, path):
        self._pending_title = None
        self._layers_path = path
        self.btn_title.configure(text="🎬 Abrir las capas en el editor", command=self._layers_to_editor)
        if not self.btn_title.winfo_ismapped():
            self.btn_title.pack(fill="x", padx=8, pady=(6, 0), after=self.lbl_why)

    def _layers_to_editor(self):
        import editor_miniaturas
        import miniatura_auto
        path = getattr(self, "_layers_path", None) or self.current
        proj = miniatura_auto.load_project(path) if path else None
        self._thumb_win = editor_miniaturas.open_editor(self.winfo_toplevel(), project=proj) if proj else \
            editor_miniaturas.open_editor(self.winfo_toplevel(), path)

    # ---------------------------------------------------------------- imagen de referencia
    MAX_REFS = 3

    def pick_reference(self, path=None):
        if path is None:
            from tkinter import filedialog
            paths = filedialog.askopenfilenames(parent=self.winfo_toplevel(), title="Imágenes de referencia (hasta 3)",
                                                filetypes=[("Imágenes",
                                                            "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff")])
            paths = list(paths or ())
        else:
            paths = [path]
        paths = [p for p in paths if p and os.path.isfile(p)]
        if not paths:
            return
        for p in paths:
            if p not in self.refs:
                self.refs.append(p)
        if len(self.refs) > self.MAX_REFS:
            self._status(f"Uso solo las {self.MAX_REFS} primeras referencias.", AMBER)
            self.refs = self.refs[:self.MAX_REFS]
        self._show_refs()
        self._status("Con referencia: tu IA la mira, y la nueva imagen parte de la primera con los cambios que "
                     "escribas. Las otras sirven de inspiración.", CYAN)

    def paste_reference(self):
        """Ctrl+V con una imagen copiada (captura, navegador…): se guarda y se usa como referencia."""
        try:
            from PIL import ImageGrab
            data = ImageGrab.grabclipboard()
        except Exception:
            data = None
        if isinstance(data, list):                 # archivos copiados en el explorador
            for p in data:
                if str(p).lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")):
                    self.pick_reference(p)
            return bool(data)
        if data is None or not hasattr(data, "save"):
            return False
        folder = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioNovelaStudio", "referencias")
        os.makedirs(folder, exist_ok=True)
        p = os.path.join(folder, datetime.datetime.now().strftime("pegada_%Y%m%d_%H%M%S.png"))
        data.save(p)
        self.pick_reference(p)
        return True

    def _show_refs(self):
        for w in self.ref_thumbs.winfo_children():
            w.destroy()
        self._ref_imgs = []
        self.ref_path = self.refs[0] if self.refs else None
        if not self.refs:
            self.lbl_ref.configure(text="")
            self.ref_box.pack_forget()
            return
        for i, p in enumerate(self.refs):
            try:
                with Image.open(p) as im:
                    im.thumbnail((84, 84))
                    th = im.convert("RGBA")
            except Exception:
                continue
            img = ctk.CTkImage(th, size=th.size)
            self._ref_imgs.append(img)
            cell = ctk.CTkFrame(self.ref_thumbs, fg_color=SURF2, corner_radius=6)
            cell.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(cell, image=img, text="").pack(padx=3, pady=(3, 0))
            ctk.CTkButton(cell, text=("base" if i == 0 else "inspira") + "  ✕", width=10, height=18, font=font(10),
                          fg_color="transparent", hover_color=RED,
                          command=lambda p=p: self._drop_ref(p)).pack(pady=(0, 2))
        self.lbl_ref.configure(text=f"{len(self.refs)} de {self.MAX_REFS}", text_color=CYAN)
        if not self.ref_box.winfo_ismapped():
            self.ref_box.pack(fill="x", padx=8, pady=(2, 0), after=self.lbl_ref.master)
        self._auto_str_changed()

    def _drop_ref(self, p):
        self.refs = [x for x in self.refs if x != p]
        self._show_refs()

    def _auto_str_changed(self):
        if self.v_auto_str.get():
            self.str_box.pack_forget()
        elif not self.str_box.winfo_ismapped():
            self.str_box.pack(fill="x", pady=(2, 0))

    def clear_reference(self):
        self.refs = []
        self._show_refs()

    # ---------------------------------------------------------------- menú «⋯ Más»
    def more_menu(self):
        import tkinter as tk
        if not self.current:
            self._status("Elige primero una de tus imágenes.", AMBER)
            return
        m = tk.Menu(self, tearoff=0, bg=SURF2, fg=TXT, activebackground=CYAN_D, activeforeground="#ffffff",
                    font=("Segoe UI", 11))
        m.add_command(label="🔍 Ampliar 2x (más nitidez)", command=lambda: self._tool("upscale", 2))
        m.add_command(label="🔍 Ampliar 4x", command=lambda: self._tool("upscale", 4))
        m.add_command(label="✂ Quitar el fondo (PNG transparente)", command=lambda: self._tool("cut"))
        m.add_command(label="📎 Usar como imagen de referencia", command=lambda: self.pick_reference(self.current))
        m.add_command(label="🔎 Revisar como miniatura (nota y consejos)", command=lambda: self._tool("review"))
        try:
            m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            m.grab_release()

    def _tool(self, what, factor=4):
        if self.busy or not self.current:
            return
        src = self.current
        meta = self._meta(src) or {}
        kind = "anime" if "Anime" in str(meta.get("engine", "")) or "anime" in str(meta.get("prompt", "")).lower() \
            else "foto"
        self.busy = True
        self.cancel.clear()
        save_ext = M.EXT_BY_NAME.get(self.v_sfmt.get(), ".png")    # se lee aquí: el hilo no toca la ventana

        def say(msg, f=None):
            self._ui(lambda: (self._status(msg), self.pb.set(f) if f is not None else None))

        def work():
            try:
                stem = os.path.splitext(src)[0]
                if what == "upscale":
                    if not ia.upscalers_installed():
                        raise RuntimeError("Falta el modelo para ampliar (Real-ESRGAN). Vuelve a abrir el instalador "
                                           "de imágenes con IA.")
                    if ia.start(say=say, cancel=self.cancel):
                        self.started_server = True
                    out = f"{stem}_x{factor}.png"
                    ia.upscale(src, out, factor, kind, say=lambda m, f: say(f"Ampliando {factor}x… {m}", f),
                               cancel=self.cancel)
                    ext = save_ext
                    if ext != ".png":
                        with Image.open(out) as im:
                            M.save_image(im.copy(), f"{stem}_x{factor}{ext}")
                        os.remove(out)
                        out = f"{stem}_x{factor}{ext}"
                    self._ui(lambda: (self._add_thumb(out, first=True), self.select(out),
                                      self._status(f"Ampliada {factor}x: {out}", GREEN)))
                elif what == "cut":
                    out = f"{stem}_sinfondo.png"
                    ia.cutout(src, out, kind, say=lambda m, f=None: say(m, f))
                    self._ui(lambda: (self._add_thumb(out, first=True), self.select(out),
                                      self._status(f"Sin fondo (PNG transparente): {out}", GREEN)))
                elif what == "review":
                    slow = ia.judge_choice() == "Exigente"
                    say("Tu IA está mirando la miniatura como un diseñador (" +
                        ("juez exigente, ~3 min" if slow else "~30 s") + ")…", None)
                    d = ia.critique_thumbnail(src)
                    self._ui(lambda: self._show_review(d))
            except RuntimeError as e:
                msg = "Cancelado." if str(e) == "CANCELLED" else str(e)
                self._ui(lambda: self._status(msg, RED))
            except Exception as e:
                log_error("herramienta " + what, traceback.format_exc())
                self._ui(lambda e=e: self._status(f"Algo falló: {e}", RED))
            finally:
                self.busy = False
        threading.Thread(target=work, daemon=True).start()

    def _show_review(self, d):
        from tkinter import messagebox
        txt = (f"Nota: {d.get('nota', '?')}/10\n\nLo bueno:\n" + "\n".join("• " + x for x in d.get("bien", [])) +
               "\n\nPara mejorar:\n" + "\n".join("• " + x for x in d.get("mejorar", [])))
        self._status(f"Revisión: {d.get('nota', '?')}/10", GREEN)
        messagebox.showinfo("Revisión de la miniatura", txt, parent=self.winfo_toplevel())

    # ---------------------------------------------------------------- dónde se guardan
    def _show_out(self):
        self.lbl_out.configure(text="Carpeta: " + self.out_dir)

    def pick_out_dir(self):
        from tkinter import filedialog
        d = filedialog.askdirectory(parent=self.winfo_toplevel(), initialdir=self.out_dir,
                                    title="Carpeta donde se guardan tus imágenes")
        if not d:
            return
        self.out_dir = os.path.normpath(d)
        self._show_out()
        self._save_cfg()
        for b, _i in list(self._thumbs.values()):         # la galería muestra la carpeta nueva
            try:
                b.destroy()
            except Exception:
                pass
        self._thumbs = {}
        self.current, self._pil = None, None
        self._load_gallery()
        self.show_page(self.v_page.get())
        self._status(f"Tus imágenes se guardarán en {self.out_dir} como {self.v_sfmt.get()}.", GREEN)

    # ---------------------------------------------------------------- miniaturas
    def _offer_title(self, path, title, style):
        self._pending_title = (path, title, style)
        self.btn_title.configure(text=f"🎬 Poner el título «{title[:28]}» ({style})", command=self._title_to_editor)
        if not self.btn_title.winfo_ismapped():
            self.btn_title.pack(fill="x", padx=8, pady=(6, 0), after=self.lbl_why)

    def _title_to_editor(self):
        if not self._pending_title:
            return
        path, title, style = self._pending_title
        if path != self.current and self.current:
            path = self.current
        import editor_miniaturas
        self._thumb_win = editor_miniaturas.open_editor(self.winfo_toplevel(), path, title, style)

    def open_thumb(self, image=None):
        import editor_miniaturas
        import miniatura_auto
        if image and miniatura_auto.load_project(image):
            self._layers_path = image
            return self._layers_to_editor()
        w = getattr(self, "_thumb_win", None)
        if w is not None and w.winfo_exists():
            if image:
                w.add_image(image, background=True)
            w.lift()
            return
        self._thumb_win = editor_miniaturas.open_editor(self.winfo_toplevel(), image)

    # ---------------------------------------------------------------- ejemplos
    def open_examples(self):
        if getattr(self, "_ex_win", None) is not None and self._ex_win.winfo_exists():
            self._ex_win.lift()
            return
        self._ex_win = ExamplesWindow(self.winfo_toplevel(), on_pick=self._use_example)

    def _use_example(self, e):
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", e.get("prompt_es", ""))
        if e.get("style") in ia.STYLES:
            self.v_sty.set(e["style"])
        if e.get("format") in ia.FORMATS:
            self.v_fmt.set(e["format"])
        self.v_eng.set(ia.AUTO)
        self._status("Idea cargada a la izquierda: cámbiala a tu gusto y pulsa «Crear imagen».", CYAN)

    # ---------------------------------------------------------------- instalación en esta PC
    def open_setup(self):
        open_setup(self.winfo_toplevel(), on_done=self._installed)

    def _installed(self):
        engines = ia.available_engines()
        self.avail, self.has_engine = engines, bool(engines)
        self.engines = [ia.AUTO] + (engines or list(ia.ENGINES))
        try:
            self.m_eng.configure(values=self.engines)
            self.v_eng.set(ia.AUTO)
            self.btn.configure(text="Crear imagen", command=self.toggle, state="normal")
            self._status("¡Listo! Ya puedes crear imágenes.", GREEN)
        except Exception:
            pass
        threading.Thread(target=self._find_ollama, daemon=True).start()

    # ---------------------------------------------------------------- piezas de interfaz
    def _label(self, parent, text):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w", fill="x", padx=8, pady=(14, 4))
        ctk.CTkFrame(row, width=4, height=16, corner_radius=2, fg_color=CYAN).pack(side="left", padx=(0, 7))
        ctk.CTkLabel(row, text=text, font=font(12, "bold"), text_color=TXT).pack(side="left")

    def _menu(self, parent, values, var, cmd=None):
        m = ctk.CTkOptionMenu(parent, values=values, variable=var, fg_color=SURF3, button_color=SURF3,
                              button_hover_color=CYAN_D, dropdown_fg_color=SURF2, width=300,
                              command=(lambda _v: cmd()) if cmd else None)
        m.pack(anchor="w", padx=8)
        return m

    def _small(self, parent, text, cmd, color=SURF3):
        return ctk.CTkButton(parent, text=text, command=cmd, height=30, width=10, font=font(12), fg_color=color,
                             hover_color=CYAN_D)

    def _status(self, text, color=MUTED):
        try:
            self.lbl.configure(text=text, text_color=color)
        except Exception:
            pass

    def _ui(self, fn):
        """Ejecuta fn en el hilo de la ventana (si la ventana ya se cerró, no hace nada)."""
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _eng_hint(self):
        if self.v_eng.get() == ia.AUTO:
            self.lbl_eng.configure(text="Según lo que pidas: anime → Animagine, fotos y arte → Z-Image…")
            return
        e = ia.ENGINES.get(self.v_eng.get(), {})
        self.lbl_eng.configure(text=f"≈ {e.get('seg', '?')} s por imagen en tu tarjeta (la 1.ª tarda más)")

    def _size(self):
        if self.v_fmt.get() == ia.CUSTOM:
            return ia.fit_size(self.v_cw.get(), self.v_ch.get())
        return ia.FORMATS.get(self.v_fmt.get(), (1024, 1024))

    def _fmt_changed(self):
        try:
            if self.v_fmt.get() == ia.CUSTOM:
                if not self.custom_row.winfo_ismapped():
                    self.custom_row.pack(anchor="w", padx=8, pady=(6, 0), before=self.fmt_anchor)
                w, h = self._size()
                self.lbl_cs.configure(text=f"→ {w}×{h}")
            elif self.custom_row.winfo_ismapped():
                self.custom_row.pack_forget()
        except Exception:
            pass

    def _find_ollama(self):
        self._ui(lambda: self.lbl_tr.configure(text="Abriendo tu IA (Ollama)…"))
        m = ia.ensure_ollama()          # si está instalado pero cerrado, se abre solo
        self.ollama = m

        def show():
            if m:
                self.lbl_tr.configure(text=f"Con {m} (Ollama). Apágalo si escribes directo en inglés.")
            else:
                self.v_tr.set(False)
                self.sw_tr.configure(state="disabled")
                self.lbl_tr.configure(text="Ollama no está abierto: escribe la descripción en inglés para mejores "
                                           "resultados.")
        self._ui(show)

    # ---------------------------------------------------------------- ajustes
    def _load_cfg(self):
        try:
            with open(CFG, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cfg(self):
        try:
            os.makedirs(os.path.dirname(CFG), exist_ok=True)
            data = dict(last_prompt=self.txt.get("1.0", "end").strip()[:2000], translate=self.v_tr.get(),
                        engine=self.v_eng.get(), style=self.v_sty.get(), format=self.v_fmt.get(),
                        count=int(self.v_n.get()), detail=self.v_det.get(), custom_w=self.v_cw.get(),
                        custom_h=self.v_ch.get(), out_dir=self.out_dir, save_fmt=self.v_sfmt.get())
            if getattr(self, "icon_theme", None):
                data["icon_theme"] = self.icon_theme
            with open(CFG + ".part", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(CFG + ".part", CFG)
        except Exception:
            pass

    # ---------------------------------------------------------------- crear
    def toggle(self):
        if self.busy:
            self.cancel.set()
            self._status("Cancelando…")
            return
        prompt = self.txt.get("1.0", "end").strip()
        if not prompt:
            self._status("Escribe primero qué quieres dibujar.", RED)
            return
        self._run(prompt, translate=self.v_tr.get() and bool(self.ollama), seed=None)

    def variation(self):
        meta = self._meta(self.current) if self.current else None
        if not meta or self.busy:
            return
        self._run(meta.get("prompt", ""), translate=False, seed=None, english=meta.get("final") or meta.get("english"),
                  meta=meta)

    def _run(self, prompt, translate, seed, english=None, meta=None):
        self._save_cfg()
        m = meta or {}
        opts = dict(engine=m.get("engine") or self.v_eng.get(), style=m.get("style") or self.v_sty.get(),
                    size=tuple(m.get("size") or self._size()), n=1 if meta else int(self.v_n.get()),
                    detail=m.get("detail", self.v_det.get()), negative=m.get("negative"), reason=m.get("reason", ""),
                    init_image=self.ref_path if not meta else None, strength=float(self.v_strength.get()),
                    refs=list(self.refs) if not meta else [], auto_strength=bool(self.v_auto_str.get()))
        opts["must"] = list(m.get("checks") or [])        # «Otra parecida»: se revisa con la misma lista
        import miniatura_auto
        # «miniatura de YouTube…» con el modelo en Automático: se arma sola por capas (fondo, personajes, título)
        # lo que el trabajo necesita de la ventana se lee AQUÍ (en el hilo, leer controles de Tk puede cerrar la app)
        opts["ext"] = M.EXT_BY_NAME.get(self.v_sfmt.get(), ".png")
        opts["versions"] = max(1, min(3, int(self.v_n.get())))
        opts["auto_thumb"] = (m.get("kind") == "miniatura" or
                              (not meta and opts["engine"] == ia.AUTO and miniatura_auto.is_thumbnail_request(prompt)))
        self.busy = True
        self.cancel.clear()
        self.btn.configure(text="Cancelar", fg_color="#7f1d1d", hover_color=RED)
        self.pb.set(0)
        threading.Thread(target=self._work, args=(prompt, translate, english, opts), daemon=True).start()

    def _work(self, prompt, translate, english, opts):
        def say(msg, f):
            # f=None: aviso sin porcentaje («Tu IA revisa…»): la barra se queda donde estaba
            self._ui(lambda: (self.pb.set(max(0.0, min(1.0, f))) if f is not None else None, self._status(msg)))
        try:
            if opts.get("auto_thumb"):
                return self._work_thumb(prompt, say, opts)
            if english is None:
                if translate and not self.ollama:          # se cerró Ollama: se vuelve a abrir
                    say("Abriendo tu IA (Ollama)…", 0.01)
                    self.ollama = ia.ensure_ollama(20)
                ref_desc = None
                if opts.get("refs") and translate and ia.vision_model():
                    # sin esto la IA solo leía tu texto («ponle el pelo rojo») y no sabía qué había en la imagen
                    say("Tu IA mira tu imagen de referencia para entender qué cambiar (~30 s)…", 0.02)
                    ia.free_ollama_gpu()
                    ref_desc = ia.describe_for_edit(opts["refs"]) or None
                say("Tu IA analiza lo que pediste y elige el modelo…" if translate else "Preparando…", 0.04)
                if translate and ia.vision_model():
                    say("Tu IA traduce y Gemma revisa que no falte nada de lo que pediste…", 0.04)
                pl = ia.plan(prompt, opts["style"], opts["engine"], model=self.ollama if translate else "",
                             have=self.avail, ref_desc=ref_desc, review=bool(translate))
                english, final = pl["prompt"], pl["prompt"]
                opts["must"] = pl.get("must") or []
                opts.update(engine=pl["engine"], negative=pl["negative"], reason=pl["reason"],
                            title=pl.get("title", ""), title_style=pl.get("title_style", ""))
                if pl.get("strength") and opts.get("auto_strength"):
                    opts["strength"] = pl["strength"]
            else:
                final = english            # «Otra parecida»: mismo texto y mismo motor, otra semilla
            why = opts.get("reason", "")
            self._ui(lambda: (self.en.delete("1.0", "end"), self.en.insert("1.0", final),
                              self.lbl_why.configure(text=why)))
            ia.free_ollama_gpu()
            if ia.start(say=say, cancel=self.cancel):
                self.started_server = True
            out_dir, ext = self.out_dir, opts.get("ext", ".png")
            os.makedirs(out_dir, exist_ok=True)
            n = opts["n"]
            for i in range(n):
                if self.cancel.is_set():
                    raise RuntimeError("CANCELLED")
                name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{i + 1}"
                path = os.path.join(out_dir, name + ext)
                raw = path if ext == ".png" else os.path.join(out_dir, name + ".tmp.png")
                pre = f"Imagen {i + 1} de {n}: " if n > 1 else ""
                _p, s = ia.generate(final, raw, opts["engine"], opts["size"], "", negative=opts.get("negative"),
                                    detail=opts["detail"], cancel=self.cancel, init_image=opts.get("init_image"),
                                    strength=opts.get("strength", 0.6),
                                    say=lambda m, f, i=i: say(pre + m, (i + f) / n))
                missing = []
                if opts.get("must") and ia.vision_model() and not self.cancel.is_set():
                    # Gemma mira el dibujo y revisa que tenga lo que pediste; si falta algo, se dibuja otra vez
                    # reforzando eso y se queda el que tenga menos fallas
                    say(pre + "Tu IA revisa que la imagen tenga lo que pediste…", (i + .9) / n)
                    missing = ia.verify_image(raw, opts["must"])
                    if missing and not self.cancel.is_set():
                        say(pre + "Le falta: " + "; ".join(missing) + ". La dibujo otra vez reforzando eso…",
                            (i + .9) / n)
                        ia.release_vision()
                        alt = raw.replace(".png", "_2.png") if raw.endswith(".png") else raw + "_2.png"
                        fix = ia.emphasize(final, missing, ia.ENGINES.get(opts["engine"], {}).get("words") == "tags")
                        _p2, s2 = ia.generate(fix, alt, opts["engine"], opts["size"], "",
                                              negative=opts.get("negative"), detail=opts["detail"],
                                              cancel=self.cancel, init_image=opts.get("init_image"),
                                              strength=opts.get("strength", 0.6),
                                              say=lambda m, f, i=i: say(pre + "Otra vez: " + m, (i + .9) / n))
                        miss2 = ia.verify_image(alt, opts["must"])
                        if len(miss2) < len(missing):
                            os.replace(alt, raw)
                            s, missing = s2, miss2
                        else:
                            try:
                                os.remove(alt)
                            except OSError:
                                pass
                    ia.release_vision()
                    note = ("Revisada por tu IA: " + ("tiene todo lo pedido." if not missing else
                                                      "aún le falta " + "; ".join(missing) + "."))
                    self._ui(lambda t=note: self.lbl_why.configure(text=(opts.get("reason", "") + " " + t).strip()))
                if raw != path:                         # el formato que elegiste (JPG, WEBP, BMP, TIFF)
                    with Image.open(raw) as im:
                        M.save_image(im.copy(), path)
                    try:
                        os.remove(raw)
                    except OSError:
                        pass
                meta = dict(prompt=prompt, english=english, final=final, engine=opts["engine"], style=opts["style"],
                            size=list(opts["size"]), seed=s, detail=opts["detail"], negative=opts.get("negative"),
                            reason=opts.get("reason", ""), checks=opts.get("must", []), missing=missing,
                            created=datetime.datetime.now().isoformat(timespec="seconds"))
                try:
                    with open(os.path.splitext(path)[0] + ".json", "w", encoding="utf-8") as f:
                        json.dump(meta, f, ensure_ascii=False, indent=1)
                except OSError:
                    pass
                self._ui(lambda p=path: (self._add_thumb(p, first=True), self.select(p), self.show_page(PAGE_MINE)))
            self._ui(lambda: self._status(f"Listo. Guardadas en {out_dir} ({ext[1:].upper()})", GREEN))
            if opts.get("title"):
                self._ui(lambda p=path, t=opts["title"], st=opts.get("title_style") or "Impacto":
                         self._offer_title(p, t, st))
        except RuntimeError as e:
            msg = "Cancelado." if str(e) == "CANCELLED" else str(e)
            self._ui(lambda: self._status(msg, MUTED if msg == "Cancelado." else RED))
        except Exception as e:
            log_error("crear", traceback.format_exc())
            self._ui(lambda e=e: self._status(f"Algo falló: {e}", RED))
        finally:
            def done():
                self.busy = False
                self.btn.configure(text="Crear imagen", fg_color=CYAN_D, hover_color=CYAN)
            self._ui(done)

    # ---------------------------------------------------------------- galería
    def _load_gallery(self):
        """La galería se llena por detrás: la ventana aparece al instante (antes tardaba ~2,5 s con 47 imágenes
        porque cada una se abría entera para hacer su miniatura). Las miniaturas quedan en caché en disco."""
        out_dir = self.out_dir
        try:
            files = sorted((f for f in os.listdir(out_dir) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp",
                                                                                 ".bmp", ".tif", ".tiff"))
                            and ".tmp." not in f and ".part" not in f),
                           key=lambda f: os.path.getmtime(os.path.join(out_dir, f)), reverse=True)[:MAX_THUMBS]
        except OSError:
            files = []
        if not files:
            return
        paths = [os.path.join(out_dir, f) for f in files]

        def work():
            thumbs = []
            for p in reversed(paths):
                th = _thumb_image(p)
                if th is not None:
                    thumbs.append((p, th))

            def show():
                if self.out_dir != out_dir:           # cambiaste de carpeta mientras cargaba
                    return
                for p, th in thumbs:
                    if p not in self._thumbs:
                        self._add_thumb(p, first=True, thumb=th, regrid=False)
                self._regrid()
                if not self.current and paths[0] in self._thumbs:
                    self.select(paths[0])
                n = len(self._thumbs)
                self.lbl_count.configure(text=f"{n} imagen{'es' if n != 1 else ''} tuya{'s' if n != 1 else ''}")
            self._ui(show)
        threading.Thread(target=work, daemon=True).start()

    def _regrid(self):
        for i, p in enumerate(self._thumbs):
            self._thumbs[p][0].grid(row=i // 5, column=i % 5, padx=4, pady=4)

    def _add_thumb(self, path, first=False, thumb=None, regrid=True):
        if thumb is None:
            thumb = _thumb_image(path)
            if thumb is None:
                return
        img = ctk.CTkImage(thumb, size=thumb.size)
        b = ctk.CTkButton(self.gal, image=img, text="", width=thumb.size[0] + 8, height=thumb.size[1] + 8,
                          fg_color="transparent", hover_color=SURF3, command=lambda p=path: self.select(p))
        self._thumbs[path] = (b, img)
        order = [path] + [p for p in self._thumbs if p != path] if first else list(self._thumbs)
        for p in order[MAX_THUMBS:]:          # se quitan las más viejas
            try:
                self._thumbs.pop(p)[0].destroy()
            except Exception:
                pass
        order = order[:MAX_THUMBS]
        self._thumbs = {p: self._thumbs[p] for p in order if p in self._thumbs}
        if regrid:
            self._regrid()

    def _meta(self, path):
        try:
            with open(os.path.splitext(path)[0] + ".json", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def select(self, path):
        if not os.path.isfile(path):
            return
        self.current = path
        for p, (b, _i) in self._thumbs.items():
            b.configure(fg_color=CYAN_D if p == path else "transparent")
        m = self._meta(path) or {}
        bits = [os.path.basename(path)]
        if m:
            bits += [m.get("engine", "").split(" (")[0], m.get("style", ""), f"semilla {m.get('seed', '')}"]
        self.info.configure(text="   ·   ".join(b for b in bits if b))
        try:                                   # se abre una vez; al cambiar el tamaño de la ventana se reusa
            with Image.open(path) as im:
                self._pil = im.convert("RGB")
        except Exception:
            self._pil = None
        self._big_key = None
        self._show_big()

    def _big_later(self):
        """Mientras se arrastra el borde de la ventana llegan cientos de avisos: se redibuja solo al final."""
        if self._big_job is not None:
            try:
                self.after_cancel(self._big_job)
            except Exception:
                pass
        self._big_job = self.after(140, self._show_big)

    def _show_big(self):
        self._big_job = None
        if self._pil is None:
            return
        try:
            scale = ctk.ScalingTracker.get_widget_scaling(self)     # zoom de Windows (125 %, 150 %…)
            W = max(100, self.view_box.winfo_width() - int(16 * scale))
            H = max(80, self.view_box.winfo_height() - int(16 * scale))
            im = self._pil
            k = min(W / im.width, H / im.height)
            px = (max(1, int(im.width * k)), max(1, int(im.height * k)))       # píxeles reales de la pantalla
            key = (self.current, px)
            if key == self._big_key:
                return
            self._big_key = key
            # CTkImage multiplica «size» por el zoom: se le da el tamaño lógico y la imagen ya en píxeles reales
            self._big = ctk.CTkImage(im.resize(px, Image.Resampling.LANCZOS),
                                     size=(px[0] / scale, px[1] / scale))
            self.view.configure(image=self._big, text="")
        except Exception:
            pass

    # ---------------------------------------------------------------- acciones
    def _use(self):
        if self.current and self.on_use:
            self.on_use(self.current)

    def save_as(self):
        if not self.current:
            return
        from tkinter import filedialog
        ext = M.EXT_BY_NAME.get(self.v_sfmt.get(), ".png")
        types = sorted(M.SAVE_TYPES, key=lambda t: t[1] != "*" + ext)       # el formato elegido primero
        dst = filedialog.asksaveasfilename(defaultextension=ext, filetypes=types,
                                           initialfile=os.path.splitext(os.path.basename(self.current))[0] + ext)
        if not dst:
            return
        try:
            with Image.open(self.current) as im:
                M.save_image(im.copy(), dst)
            self._status("Guardada: " + dst, GREEN)
        except Exception as e:
            self._status(f"No se pudo guardar: {e}", RED)

    def open_folder(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            if self.current and os.path.isfile(self.current):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(self.current)])
            else:
                os.startfile(self.out_dir)
        except Exception:
            pass

    def shutdown(self):
        """Al cerrar: detiene lo que esté dibujando y apaga ComfyUI si lo encendimos nosotros."""
        self.cancel.set()
        self._save_cfg()
        if self.busy:
            ia.interrupt()
        if self.started_server:
            ia.stop()


TIPS = [
    ("Cómo describir (la fórmula)",
     "Qué + cómo es + dónde + luz/hora + estilo + encuadre.\n"
     "Ej.: «Una guerrera de armadura plateada (qué), cabello rojo largo (cómo es), en un puente de piedra sobre un "
     "río (dónde), al atardecer con niebla (luz), ilustración fantástica (estilo), plano medio (encuadre)»."),
    ("Sé concreto",
     "Colores, ropa, hora del día, clima, material («de cristal», «de madera»), emoción («mirada triste»). "
     "«Una casa» da cualquier cosa; «una casa de adobe con techo rojo al amanecer» da lo que imaginas."),
    ("Texto dentro de la imagen",
     "Ponlo entre comillas y corto (1 a 4 palabras), mejor en MAYÚSCULAS: que diga \"KUON STUDIO\". "
     "Di dónde va: «arriba, en letras grandes». Lo hace Z-Image (o FLUX dev). Frases largas suelen salir mal."),
    ("Anime",
     "Escribe «estilo anime» o elige el estilo Anime: se usa Animagine XL. Describe pelo, ojos, ropa, pose y fondo. "
     "Tu IA lo convierte en las etiquetas que ese modelo entiende (1girl, silver hair, school uniform…)."),
    ("Fotos realistas",
     "Empieza con «foto realista de…». Añade el plano: primer plano, plano medio, gran angular, vista desde abajo. "
     "Luz: «luz de ventana», «hora dorada», «neón». Se usa Z-Image."),
    ("Fondos para tus videos",
     "Horizontal 16:9. Pide «sin personas» o «personas pequeñas de espaldas» para que no tapen los subtítulos. "
     "En Audio Novela, el fondo «Imágenes con IA» lo hace solo, una imagen por capítulo."),
    ("Portadas y miniaturas",
     "Deja sitio para el título: «espacio vacío arriba» o pon el título entre comillas. Colores fuertes y un solo "
     "protagonista llaman más la atención en YouTube."),
    ("Medidas",
     "1:1 avatar o publicación · 3:4 y 2:3 retrato o póster · 4:5 Instagram · 16:9 YouTube · 9:16 Shorts/TikTok · "
     "21:9 cine/banner · Personalizada si necesitas un tamaño exacto (se ajusta a múltiplos de 64)."),
    ("Cómo mejorar un resultado",
     "1) «Otra parecida»: mismo texto, otra versión. 2) Cambia o añade 1-2 detalles, no todo. 3) Cuando te guste, "
     "activa «Más detalle» para la versión final (1,5x más grande). 4) Prueba otro estilo."),
    ("Qué suele fallar",
     "Manos y dedos, textos largos, muchas personas haciendo cosas distintas, y pedir 10 cosas a la vez. "
     "Mejor una idea clara por imagen."),
]
MODELS_HELP = [
    ("Automático (recomendado)", "Tu IA (Qwen3 en Ollama) lee lo que pides, decide si es anime, foto, texto o arte, "
                                 "elige el modelo y le escribe la descripción en su «idioma»."),
    ("Alta calidad · Z-Image Turbo", "Fotos realistas, arte, portadas y texto dentro de la imagen. ~55 s."),
    ("Anime · Animagine XL 4", "Personajes y escenas de anime/manga. Entiende etiquetas. ~30 s."),
    ("Rápida · Juggernaut XL", "Fotos realistas en ~15 s; entiende peor descripciones largas."),
    ("Ilustración · FLUX schnell", "Ilustraciones variadas ~45 s."),
    ("Máxima calidad · FLUX dev", "Mucho detalle y texto; el más lento (~2 min)."),
]


def examples_dir():
    return res_dir("ejemplos_ia")


def load_examples():
    try:
        with open(os.path.join(examples_dir(), "ejemplos.json"), encoding="utf-8") as f:
            return [e for e in json.load(f) if os.path.isfile(os.path.join(examples_dir(), e["file"]))]
    except Exception:
        return []


class ExamplesWindow(ctk.CTkToplevel):
    _tema_iconos = True
    """Ejemplos reales (imagen + lo que se escribió + qué modelo eligió la IA) y consejos para mejores prompts."""

    def __init__(self, master, on_pick=None):
        super().__init__(master)
        self.on_pick = on_pick
        self.title("Ejemplos y consejos")
        self.geometry("1060x760")
        self.configure(fg_color=BG)
        self._imgs = []
        tv = ctk.CTkTabview(self, fg_color=SURF, segmented_button_selected_color=CYAN_D,
                            segmented_button_unselected_color=SURF2)
        tv.pack(fill="both", expand=True, padx=12, pady=12)
        t1, t2, t3 = tv.add("Ejemplos"), tv.add("Consejos"), tv.add("Modelos")
        # ejemplos
        exs = load_examples()
        sc = ctk.CTkScrollableFrame(t1, fg_color="transparent")
        sc.pack(fill="both", expand=True)
        if not exs:
            ctk.CTkLabel(sc, text="No se encontraron los ejemplos.", text_color=MUTED, font=font(13)).pack(pady=40)
        for c in range(2):
            sc.grid_columnconfigure(c, weight=1)
        for i, e in enumerate(exs):
            card = ctk.CTkFrame(sc, fg_color=SURF2, corner_radius=10)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            try:
                with Image.open(os.path.join(examples_dir(), e["file"])) as im:
                    im = im.convert("RGB")
                    im.thumbnail((440, 250))
                    img = ctk.CTkImage(im.copy(), size=im.size)
                self._imgs.append(img)
                ctk.CTkLabel(card, image=img, text="").pack(padx=8, pady=(8, 4))
            except Exception:
                pass
            ctk.CTkLabel(card, text=e["title"], font=font(13, "bold"), text_color=TXT).pack(anchor="w", padx=10)
            eng = e["engine"].split(" (")[0] + " · " + e["engine"].split("(")[-1].rstrip(")")
            ctk.CTkLabel(card, text=f"{eng} · estilo {e['style']} · {e['format'].split(' (')[0]} · ~{e['seconds']} s",
                         font=font(11), text_color=VIOLET, justify="left", wraplength=440).pack(anchor="w", padx=10)
            ctk.CTkLabel(card, text="Lo que se escribió: «" + e["prompt_es"] + "»", font=font(11), text_color=MUTED,
                         justify="left", wraplength=440).pack(anchor="w", padx=10, pady=(2, 4))
            ctk.CTkButton(card, text="Usar este ejemplo", height=30, font=font(12), fg_color=CYAN_D, hover_color=CYAN,
                          command=lambda e=e: self._use(e)).pack(anchor="w", padx=10, pady=(0, 10))
        # consejos
        sc2 = ctk.CTkScrollableFrame(t2, fg_color="transparent")
        sc2.pack(fill="both", expand=True)
        for title, body in TIPS:
            ctk.CTkLabel(sc2, text=title, font=font(13, "bold"), text_color=CYAN).pack(anchor="w", padx=10, pady=(10, 0))
            ctk.CTkLabel(sc2, text=body, font=font(12), text_color=TXT, justify="left", wraplength=960).pack(
                anchor="w", padx=10)
        # modelos
        sc3 = ctk.CTkScrollableFrame(t3, fg_color="transparent")
        sc3.pack(fill="both", expand=True)
        ctk.CTkLabel(sc3, text="Cómo trabajan juntos", font=font(14, "bold"), text_color=TXT).pack(anchor="w", padx=10,
                                                                                                  pady=(10, 2))
        ctk.CTkLabel(sc3, text="1) Tu IA de texto (Qwen3) entiende tu pedido en español y decide el tipo de imagen. "
                               "2) Elige el modelo que mejor hace ese tipo. 3) Le escribe la descripción como ese "
                               "modelo la entiende: etiquetas para el de anime, frases detalladas para los demás, y "
                               "su lista de cosas a evitar. 4) Con «Más detalle», el mismo modelo agranda la imagen "
                               "1,5x y repasa los detalles finos sin cambiar la composición.",
                     font=font(12), text_color=TXT, justify="left", wraplength=960).pack(anchor="w", padx=10)
        for title, body in MODELS_HELP:
            ctk.CTkLabel(sc3, text=title, font=font(13, "bold"), text_color=CYAN).pack(anchor="w", padx=10, pady=(10, 0))
            ctk.CTkLabel(sc3, text=body, font=font(12), text_color=TXT, justify="left", wraplength=960).pack(
                anchor="w", padx=10)
        self.after(200, self.lift)

    def _use(self, e):
        if self.on_pick:
            try:
                self.on_pick(e)
            except Exception:
                log_error("usar ejemplo", traceback.format_exc())
        self.destroy()


class SetupWindow(ctk.CTkToplevel):
    _tema_iconos = True
    """Explica qué hace falta, cuánto pesa y lo instala todo con un botón (instalar_ia)."""

    def __init__(self, master, on_done=None):
        import instalar_ia as ins
        super().__init__(master)
        self.ins, self.on_done = ins, on_done
        self.title("Activar imágenes con IA")
        self.geometry("760x780")
        self.configure(fg_color=BG)
        self.cancel, self.busy = threading.Event(), False
        sc = ctk.CTkScrollableFrame(self, fg_color=SURF, corner_radius=12)
        sc.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        ctk.CTkLabel(sc, text="🎨  Imágenes con IA en esta PC", font=font(18, "bold"), text_color=TXT).pack(
            anchor="w", padx=10, pady=(8, 2))
        ctk.CTkLabel(sc, text="Crea portadas, fondos de video por capítulo e imágenes de lo que describas, sin "
                              "internet y gratis, usando tu tarjeta NVIDIA. Se descarga una sola vez; después funciona "
                              "sin conexión. Si se corta internet, vuelve a pulsar «Descargar e instalar» y sigue donde "
                              "quedó.", font=font(12), text_color=MUTED, justify="left", wraplength=690).pack(anchor="w",
                                                                                                         padx=10)
        self.lbl_pc = ctk.CTkLabel(sc, text="Revisando tu PC…", font=font(12), text_color=TXT, justify="left",
                                   wraplength=690)
        self.lbl_pc.pack(anchor="w", padx=10, pady=(10, 4))
        row = ctk.CTkFrame(sc, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(6, 0))
        ctk.CTkLabel(row, text="Carpeta", font=font(12, "bold"), text_color=TXT).pack(side="left")
        self.v_base = ctk.StringVar(value=ins.default_base())
        ctk.CTkEntry(row, textvariable=self.v_base, fg_color=SURF2, border_color=LINE).pack(side="left", fill="x",
                                                                                           expand=True, padx=8)
        ctk.CTkButton(row, text="Cambiar…", width=80, fg_color=SURF3, hover_color=CYAN_D,
                      command=self._pick).pack(side="left")
        ctk.CTkLabel(sc, text="Qué se va a instalar", font=font(13, "bold"), text_color=TXT).pack(anchor="w", padx=10,
                                                                                                  pady=(14, 4))
        self.vars = {}
        for k, p in ins.PACKS.items():
            box = ctk.CTkFrame(sc, fg_color=SURF2, corner_radius=8)
            box.pack(fill="x", padx=10, pady=3)
            v = ctk.BooleanVar(value=p.get("default", False))
            self.vars[k] = v
            gb = ins.pack_bytes([k]) / ins.GB + (p.get("extra_gb", 0) if k == "base" else 0)
            size_txt = f"{gb:.1f} GB" if gb >= 0.05 else "ya instalado"
            cb = ctk.CTkCheckBox(box, text=f"{p['title']}   ·   {size_txt}", variable=v, font=font(12, "bold"),
                                 fg_color=CYAN_D, hover_color=CYAN, command=self._update)
            cb.pack(anchor="w", padx=8, pady=(6, 0))
            if p.get("required"):
                cb.configure(state="disabled")
            ctk.CTkLabel(box, text=p["what"], font=font(11), text_color=MUTED, justify="left",
                         wraplength=640).pack(anchor="w", padx=36, pady=(0, 6))
        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.pack(fill="x", padx=12, pady=(0, 12))
        self.lbl_total = ctk.CTkLabel(bot, text="", font=font(12, "bold"), text_color=CYAN, justify="left",
                                      wraplength=720)
        self.lbl_total.pack(anchor="w", pady=(0, 6))
        self.btn = ctk.CTkButton(bot, text="Descargar e instalar", height=42, font=font(15, "bold"), fg_color=CYAN_D,
                                 hover_color=CYAN, command=self.toggle)
        self.btn.pack(fill="x")
        self.pb = ctk.CTkProgressBar(bot, progress_color=CYAN, fg_color=SURF2)
        self.pb.set(0)
        self.pb.pack(fill="x", pady=(6, 0))
        self.lbl = ctk.CTkLabel(bot, text="", font=font(12), text_color=MUTED, justify="left", wraplength=720)
        self.lbl.pack(anchor="w", pady=(4, 0))
        self.v_base.trace_add("write", lambda *_: self._update())
        self.pc = None
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(200, self.lift)
        threading.Thread(target=self._check, daemon=True).start()

    def _ui(self, fn):
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _pick(self):
        from tkinter import filedialog
        d = filedialog.askdirectory(title="Carpeta para el motor y los modelos", parent=self)
        if d:
            d = os.path.normpath(d)
            self.v_base.set(d if os.path.basename(d).upper() == "IA" else os.path.join(d, "IA"))

    def _check(self):
        pc = self.ins.check_pc(self.v_base.get())
        self.pc = pc

        def show():
            lines = []
            if pc["gpu"]:
                lines = [f"✔ Tarjeta: {pc['gpu']} ({pc['vram_gb']} GB) · controlador {pc['driver']}",
                         f"✔ Memoria RAM: {pc['ram_gb']} GB"]
            if pc["gpu"]:
                lines.append("✔ Componentes de Windows (Visual C++) ya instalados" if pc.get("vcredist") else
                             "• Se instalarán los componentes de Windows (Visual C++ 2015-2022, ~19 MB). Windows "
                             "pedirá permiso una vez.")
            lines += ["⚠ " + a for a in pc["avisos"]]
            self.lbl_pc.configure(text="\n".join(lines) or "✔ Tu PC cumple lo necesario.",
                                  text_color=TXT if pc["ok"] else RED)
            if pc.get("driver_old"):
                ctk.CTkButton(self.lbl_pc.master, text="Abrir la página del controlador NVIDIA", fg_color=SURF3,
                              hover_color=CYAN_D, command=lambda: __import__("webbrowser").open(
                                  "https://www.nvidia.com/es-la/drivers/")).pack(anchor="w", padx=10, pady=(0, 6),
                                                                                after=self.lbl_pc)
            if not pc["ok"]:
                self.btn.configure(state="disabled", text="Tu PC no cumple lo necesario")
            self._update()
        self._ui(show)

    def keys(self):
        return [k for k, v in self.vars.items() if v.get()]

    def _update(self):
        try:
            base = self.v_base.get().strip()
            keys = self.keys()
            dl = self.ins.pack_bytes(keys, base) / self.ins.GB
            need = self.ins.need_gb(keys, base)
            free = self.ins.free_gb(base)
            mins = dl * 1024 / 6 / 60          # ~6 MB/s (internet de 50 Mbps)
            t = (f"Descarga: {dl:.1f} GB · ocupará {need:.1f} GB en {base[:2]} (libres: {free:.0f} GB) · "
                 f"≈ {max(1, round(mins))} min con internet de 50 Mbps.")
            enough = free >= need + 1
            if not enough:
                t += "  ⚠ No alcanza el espacio: elige otra carpeta o desmarca algo."
            self.lbl_total.configure(text=t, text_color=CYAN if enough else RED)
            if not self.busy and (self.pc is None or self.pc["ok"]):
                self.btn.configure(state="normal" if enough else "disabled")
        except Exception:
            pass

    def toggle(self):
        if self.busy:
            self.cancel.set()
            self.lbl.configure(text="Cancelando… (lo ya bajado se conserva)")
            return
        self.busy = True
        self.cancel.clear()
        self.btn.configure(text="Cancelar", fg_color="#7f1d1d", hover_color=RED)
        threading.Thread(target=self._work, args=(self.v_base.get().strip(), self.keys()), daemon=True).start()

    def _work(self, base, keys):
        def say(msg, f):
            self._ui(lambda: (self.lbl.configure(text=msg, text_color=MUTED),
                              self.pb.set(f) if f is not None else None))
        ok = False
        try:
            self.ins.install(base, keys, say, self.cancel)
            say("Probando que todo funcione (enciende el motor y hace una imagen de prueba)…", 0.99)
            t = time.time()
            self.ins.self_test(say, self.cancel)
            ok = True
            secs = time.time() - t
            self._ui(lambda: (self.lbl.configure(text=f"✔ ¡Listo! Tu PC ya crea imágenes con IA (prueba en "
                                                      f"{secs:.0f} s). Ya puedes cerrar esta ventana.",
                                                 text_color=GREEN), self.pb.set(1)))
        except self.ins.Cancelled:
            self._ui(lambda: self.lbl.configure(text="Cancelado. Lo descargado se guardó: al volver a pulsar sigue "
                                                     "donde quedó.", text_color=MUTED))
        except RuntimeError as e:
            msg = "Cancelado." if str(e) == "CANCELLED" else str(e)
            self._ui(lambda: self.lbl.configure(text="⚠ " + msg, text_color=RED))
        except Exception as e:
            log_error("instalar", traceback.format_exc())
            self._ui(lambda e=e: self.lbl.configure(text=f"⚠ Algo falló: {e}. Vuelve a pulsar «Descargar e "
                                                         "instalar».", text_color=RED))
        finally:
            def done():
                self.busy = False
                self.btn.configure(text="Listo ✔" if ok else "Descargar e instalar", fg_color=CYAN_D,
                                   hover_color=CYAN, state="disabled" if ok else "normal")
                if not ok:
                    self._update()
                if ok and self.on_done:
                    try:
                        self.on_done()
                    except Exception:
                        log_error("después de instalar", traceback.format_exc())
            self._ui(done)

    def _close(self):
        if self.busy:
            from tkinter import messagebox
            if not messagebox.askyesno("Activar imágenes con IA", "Se está instalando. ¿Cancelar y cerrar? Lo que ya "
                                       "se bajó se guarda.", parent=self):
                return
            self.cancel.set()
        self.destroy()


THUMB_CACHE = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioNovelaStudio", "miniaturas_cache")


def _thumb_image(path):
    """Miniatura de 150 px de una imagen (cualquier hilo). Se guarda en caché según ruta, fecha y tamaño: la
    segunda vez se abre al instante; si la imagen cambia, se rehace sola."""
    import hashlib
    try:
        st = os.stat(path)
        key = hashlib.sha1(f"{path}|{st.st_mtime_ns}|{st.st_size}".encode("utf-8")).hexdigest()[:20]
        cached = os.path.join(THUMB_CACHE, key + ".jpg")
        if os.path.isfile(cached):
            with Image.open(cached) as im:
                return im.convert("RGB")
        with Image.open(path) as im:
            im.draft("RGB", (300, 300))              # JPG: se decodifica ya pequeño
            im.thumbnail((150, 150), Image.Resampling.LANCZOS, reducing_gap=2.0)
            thumb = im.convert("RGB")
        try:
            os.makedirs(THUMB_CACHE, exist_ok=True)
            thumb.save(cached, "JPEG", quality=88)
        except OSError:
            pass
        return thumb
    except Exception:
        return None


def open_setup(master, on_done=None):
    try:
        return SetupWindow(master, on_done)
    except Exception:
        log_error("abrir instalador", traceback.format_exc())
        return None


def open_window(master, on_use=None, use_label="Usar como portada"):
    """Ventana dentro de otra app (Audio Novela Studio)."""
    w = ctk.CTkToplevel(master)
    w.title(APP)
    w.geometry("1180x760")
    w.configure(fg_color=BG)
    st = ImageStudio(w, on_use=on_use, use_label=use_label)
    st.pack(fill="both", expand=True)

    def close():
        try:
            st.shutdown()
        finally:
            w.destroy()
    w.protocol("WM_DELETE_WINDOW", close)
    w.after(200, w.lift)
    return w


def main():
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root._tema_iconos = True           # en la app aparte, el tema de botones va en todas sus ventanas
    root.title(APP)
    root.geometry("1200x780")
    root.minsize(900, 600)
    root.configure(fg_color=BG)
    for ico in (icon_file(current_icon_theme()), res_dir("estudio_imagenes.ico"), res_dir("icon.ico")):
        try:
            if ico and os.path.isfile(ico):
                root.iconbitmap(default=ico)
                root.iconbitmap(ico)
                break
        except Exception:
            pass
    st = ImageStudio(root, standalone=True)
    st.pack(fill="both", expand=True)

    def on_error(exc, val, tb):
        log_error("ventana", "".join(traceback.format_exception(exc, val, tb)))
        st._status(f"Algo falló, pero puedes seguir: {val}", RED)
    root.report_callback_exception = on_error
    threading.excepthook = lambda a: log_error("hilo", "".join(traceback.format_exception(a.exc_type, a.exc_value,
                                                                                          a.exc_traceback)))

    def close():
        try:
            st.shutdown()
        finally:
            root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()


if __name__ == "__main__":
    main()
