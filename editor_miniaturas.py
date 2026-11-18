# -*- coding: utf-8 -*-
"""Editor de miniaturas para YouTube (por capas): fondo, personajes o tu foto sin fondo, textos con estilo y efectos.

La IA hace el arte (fondo y personajes) y quita fondos; los textos los dibuja la app (letras perfectas, con tildes).
Se exporta en PNG sin pérdida. Lo abren el Estudio de Imágenes y Audio Novela Studio.
"""
import copy
import datetime
import json
import os
import threading
import traceback

import customtkinter as ctk
from PIL import Image, ImageDraw

import imagen_ia as ia
import miniaturas as M

BG, SURF, SURF2, SURF3, LINE = "#070a12", "#0c1221", "#111a2e", "#18233c", "#1f2d4d"
TXT, MUTED, CYAN, CYAN_D, VIOLET, RED, GREEN, AMBER = ("#e7edff", "#7f8db3", "#22d3ee", "#0b7285", "#a78bfa",
                                                       "#f87171", "#34d399", "#f5a524")
OUT_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "Imagenes IA", "Miniaturas")
WORK = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioNovelaStudio", "miniaturas_tmp")
GLOWS = {"Sin borde": "", "Cian": "#22d3ee", "Rojo": "#ff2a2a", "Dorado": "#f6c445", "Blanco": "#ffffff",
         "Verde": "#39ff88", "Morado": "#b05cff", "Naranja": "#ff8c1a"}
FRAMINGS = {"Medio cuerpo": ("cowboy shot", "medium shot from the thighs up"),
            "Primer plano": ("upper body, portrait", "close-up portrait, head and shoulders"),
            "Cuerpo entero": ("full body", "full body shot")}
SIZES = {"1280×720 (YouTube)": (1280, 720), "1920×1080 (Full HD)": (1920, 1080), "2560×1440 (2K)": (2560, 1440)}
TEMPLATES = {
    "Épico (cromo)": dict(fx={"shade": .55, "shade_side": "top", "vignette": .8, "embers": .8,
                              "embers_color": "#ff5a1a"},
                          texts=[("Nacido del Olvido", "Cromo épico", .5, .05, .16, "center"),
                                 ("Cap 1", "Cromo épico", .5, .74, .15, "center")]),
    "Impacto (blanco y rojo)": dict(fx={"shade": .8, "shade_side": "left", "vignette": .5, "embers": .6,
                                        "embers_color": "#ff8c1a"},
                                    texts=[("Dios Dragón", "Impacto", .04, .05, .19, "left"),
                                           ("*Traicionado*", "Impacto", .045, .26, .14, "left")]),
    "Reacción (oro y rojo)": dict(fx={"shade": .5, "shade_side": "top", "vignette": .6, "embers": .5,
                                      "embers_color": "#ff7a1a"},
                                  texts=[("¿Los *recuerdas?*", "Oro y rojo", .04, .03, .17, "left")]),
    "Película (aura roja)": dict(fx={"shade": .75, "shade_side": "left", "vignette": .55, "embers": .3,
                                     "embers_color": "#ff3030"},
                                 texts=[("Issei traicionado", "Aura roja", .03, .04, .16, "left"),
                                        ("La película", "Elegante", .035, .25, .065, "left")]),
}


def font(size=13, weight="normal"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


def _cfg(**kw):
    """Ajustes del editor (última carpeta y formato). Con argumentos los guarda."""
    p = os.path.join(os.path.dirname(WORK), "editor_miniaturas.json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    if kw:
        d.update(kw)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
        except OSError:
            pass
    return d


def _has_transparency(path):
    """True si la imagen ya trae fondo transparente (PNG/WEBP de personajes o logos)."""
    try:
        with Image.open(path) as im:
            if im.mode == "P" and "transparency" in im.info:
                im = im.convert("RGBA")
            if im.mode not in ("RGBA", "LA"):
                return False
            a = im.getchannel("A")
            w, h = a.size
            border = [a.getpixel((x, y)) for x in range(0, w, max(1, w // 40)) for y in (0, h - 1)]
            border += [a.getpixel((x, y)) for y in range(0, h, max(1, h // 40)) for x in (0, w - 1)]
            return sum(1 for v in border if v < 20) > len(border) * 0.5
    except Exception:
        return False


def _log(where):
    try:
        os.makedirs(os.path.dirname(WORK), exist_ok=True)
        with open(os.path.join(os.path.dirname(WORK), "error.log"), "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] Miniaturas - {where}\n{traceback.format_exc()}\n")
    except OSError:
        pass


class ThumbEditor(ctk.CTkToplevel):
    def __init__(self, master, start_image=None, title=None, title_style=None, project=None):
        super().__init__(master)
        self.title("Editor de miniaturas")
        self.geometry("1400x860")
        self.minsize(1100, 700)
        self.configure(fg_color=BG)
        os.makedirs(WORK, exist_ok=True)
        self.proj = {"size": [1280, 720], "fx": {}, "layers": []}
        self.sel = None
        self.busy = False
        self.cancel = threading.Event()
        self.started = False
        self._boxes, self._prev_job, self._prev_img, self._drag = [], None, None, None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(self, width=380, fg_color=SURF, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsw", padx=(12, 6), pady=12)
        right = ctk.CTkFrame(self, fg_color=SURF, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        self._build_left(left)
        self._build_right(right)
        self.apply_template("Impacto (blanco y rojo)", keep_images=False)
        if start_image and os.path.isfile(start_image):
            self.add_image(start_image, background=True)
        if title:
            self.set_title(title, title_style or "Impacto")
        if project:
            self.load_project(project)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._undo, self._redo, self._last_state = [], [], None
        self._bind_keys()
        self.after(200, self.lift)

    # ------------------------------------------------------------------ interfaz
    def _h(self, p, t, top=14):
        ctk.CTkLabel(p, text=t, font=font(14, "bold"), text_color=CYAN).pack(anchor="w", padx=8, pady=(top, 4))

    def _b(self, p, t, cmd, color=SURF3, **kw):
        return ctk.CTkButton(p, text=t, command=cmd, fg_color=color, hover_color=CYAN_D, height=32, font=font(12),
                             **kw)

    def _menu(self, p, values, var, cmd=None, w=170):
        return ctk.CTkOptionMenu(p, values=values, variable=var, width=w, fg_color=SURF3, button_color=SURF3,
                                 button_hover_color=CYAN_D, dropdown_fg_color=SURF2,
                                 command=(lambda _v: cmd()) if cmd else None)

    def _build_left(self, L):
        ctk.CTkLabel(L, text="🎬  Miniatura para YouTube", font=font(18, "bold"), text_color=TXT).pack(
            anchor="w", padx=8, pady=(6, 0))
        ctk.CTkLabel(L, text="Arrastra las capas en la vista para moverlas. Los textos los dibuja la app: salen "
                             "perfectos, con tildes y ñ.", font=font(11), text_color=MUTED, justify="left",
                     wraplength=350).pack(anchor="w", padx=8)
        self._h(L, "✨ Automática (un solo prompt)")
        self.t_auto = ctk.CTkTextbox(L, height=90, fg_color=SURF2, border_color=LINE, border_width=1, wrap="word",
                                     font=font(12))
        self.t_auto.pack(fill="x", padx=8)
        self._b(L, "✨ Armar la miniatura por capas", self.auto_build, CYAN_D).pack(fill="x", padx=8, pady=(4, 0))
        ctk.CTkLabel(L, text="Describe fondo, personajes y el título entre comillas. Tarda 2-4 min.", font=font(11),
                     text_color=MUTED).pack(anchor="w", padx=8)
        self._h(L, "1 · Plantilla")
        tr = ctk.CTkFrame(L, fg_color="transparent")
        tr.pack(fill="x", padx=6)
        for i, name in enumerate(TEMPLATES):
            self._b(tr, name, lambda n=name: self.apply_template(n), width=170).grid(row=i // 2, column=i % 2,
                                                                                   padx=2, pady=2, sticky="ew")
        self._h(L, "2 · Fondo")
        self.e_bg = ctk.CTkEntry(L, placeholder_text="Ej.: campo de batalla en llamas, cielo rojo, dragón a lo lejos",
                                 fg_color=SURF2, border_color=LINE)
        self.e_bg.pack(fill="x", padx=8)
        r = ctk.CTkFrame(L, fg_color="transparent")
        r.pack(fill="x", padx=6, pady=4)
        self._b(r, "🎨 Crear con IA", self.gen_background, CYAN_D).pack(side="left", padx=2)
        self._b(r, "📁 Subir", lambda: self.pick_image(background=True)).pack(side="left", padx=2)
        self._b(r, "🖼 Mías", lambda: self.pick_image(background=True, mine=True)).pack(side="left", padx=2)
        self._h(L, "3 · Personajes y tu foto")
        self.e_ch = ctk.CTkEntry(L, placeholder_text="Ej.: chico de pelo blanco, alas negras, halo de fuego",
                                 fg_color=SURF2, border_color=LINE)
        self.e_ch.pack(fill="x", padx=8)
        r = ctk.CTkFrame(L, fg_color="transparent")
        r.pack(fill="x", padx=6, pady=4)
        self.v_frame = ctk.StringVar(value="Medio cuerpo")
        self._menu(r, list(FRAMINGS), self.v_frame, w=130).pack(side="left", padx=2)
        self.v_anime = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(r, text="Anime", variable=self.v_anime, fg_color=CYAN_D, font=font(12)).pack(side="left",
                                                                                                    padx=6)
        r2 = ctk.CTkFrame(L, fg_color="transparent")
        r2.pack(fill="x", padx=6)
        self._b(r2, "🎨 Crear personaje (4 opciones)", self.gen_character, CYAN_D).pack(side="left", padx=2)
        self._b(r2, "📁 Subir foto", lambda: self.pick_image(background=False)).pack(side="left", padx=2)
        ctk.CTkLabel(L, text="Al subir una foto o crear un personaje se le quita el fondo solo.", font=font(11),
                     text_color=MUTED).pack(anchor="w", padx=8)
        self._h(L, "Mis personajes guardados")
        self.saved_box = ctk.CTkFrame(L, fg_color="transparent")
        self.saved_box.pack(fill="x", padx=6)
        ctk.CTkLabel(L, text="Toca uno para ponerlo. Guarda uno nuevo desde «Capa elegida». Si lo nombras en la "
                             "miniatura automática, se usa tal cual.", font=font(11), text_color=MUTED,
                     justify="left", wraplength=350).pack(anchor="w", padx=8)
        self._saved_imgs = []
        self._load_saved()
        self._h(L, "4 · Textos")
        self.txt_box = ctk.CTkFrame(L, fg_color="transparent")
        self.txt_box.pack(fill="x", padx=4)
        self._b(L, "+ Agregar texto", self.add_text).pack(anchor="w", padx=8, pady=4)
        ctk.CTkLabel(L, text="Truco: lo que va entre *asteriscos* sale en el color de acento. Ej.: DIOS *DRAGÓN*",
                     font=font(11), text_color=MUTED, justify="left", wraplength=350).pack(anchor="w", padx=8)
        self._h(L, "5 · Capa elegida")
        self.sel_box = ctk.CTkFrame(L, fg_color=SURF2, corner_radius=10)
        self.sel_box.pack(fill="x", padx=8)
        self.lbl_sel = ctk.CTkLabel(self.sel_box, text="Toca una capa en la vista", font=font(12), text_color=MUTED)
        self.lbl_sel.pack(anchor="w", padx=10, pady=6)
        self.s_size = ctk.CTkSlider(self.sel_box, from_=0.05, to=1.6, command=lambda v: self._set_sel("size", v),
                                    progress_color=CYAN_D, button_color=CYAN)
        self.s_size.pack(fill="x", padx=10)
        row = ctk.CTkFrame(self.sel_box, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=6)
        self.v_glow = ctk.StringVar(value="Sin borde")
        ctk.CTkLabel(row, text="Borde de luz", font=font(12)).pack(side="left", padx=2)
        self._menu(row, list(GLOWS), self.v_glow, lambda: self._set_sel("glow", GLOWS[self.v_glow.get()]),
                   w=110).pack(side="left", padx=4)
        self.v_style = ctk.StringVar(value="Impacto")
        self.m_style = self._menu(row, list(M.STYLES), self.v_style, lambda: self._set_sel("style", self.v_style.get()),
                                  w=120)
        row2 = ctk.CTkFrame(self.sel_box, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=(0, 8))
        for t, f in (("↔ Espejo", lambda: self._set_sel("flip", None)), ("⬆ Adelante", lambda: self._order(1)),
                     ("⬇ Atrás", lambda: self._order(-1)), ("🗑", self._delete)):
            self._b(row2, t, f, width=10).pack(side="left", padx=2)
        row3 = ctk.CTkFrame(self.sel_box, fg_color="transparent")
        row3.pack(fill="x", padx=8, pady=(0, 8))
        self._b(row3, "▣ Tarjeta con número", self._card, width=10).pack(side="left", padx=2)
        self._b(row3, "💾 Guardar personaje", self.save_selected_character, width=10).pack(side="left", padx=2)
        self._h(L, "6 · Efectos")
        self.v_fx = {}
        for key, label, mx in (("embers", "Brasas / chispas", 1.5), ("vignette", "Viñeta (bordes oscuros)", 1.2),
                               ("shade", "Sombra detrás del texto", 1.0)):
            ctk.CTkLabel(L, text=label, font=font(12), text_color=TXT).pack(anchor="w", padx=8)
            s = ctk.CTkSlider(L, from_=0, to=mx, progress_color=CYAN_D, button_color=CYAN,
                              command=lambda v, k=key: self._set_fx(k, v))
            s.pack(fill="x", padx=8)
            self.v_fx[key] = s
        r = ctk.CTkFrame(L, fg_color="transparent")
        r.pack(fill="x", padx=6, pady=4)
        self.v_emb = ctk.StringVar(value="Naranja")
        ctk.CTkLabel(r, text="Color chispas", font=font(12)).pack(side="left", padx=2)
        self._menu(r, [k for k in GLOWS if GLOWS[k]], self.v_emb, lambda: self._set_fx("embers_color",
                                                                                    GLOWS[self.v_emb.get()]),
                   w=100).pack(side="left", padx=4)
        self.v_side = ctk.StringVar(value="left")
        self._menu(r, ["left", "right", "top", "bottom"], self.v_side, lambda: self._set_fx("shade_side", self.v_side.get()),
                   w=80).pack(side="left", padx=4)
        self._h(L, "7 · Inspirarse en una imagen")
        ctk.CTkLabel(L, text="Sube una miniatura que te guste: tu IA (Gemma 4) la mira y propone fondo, personaje y "
                             "texto parecidos.", font=font(11), text_color=MUTED, justify="left",
                     wraplength=350).pack(anchor="w", padx=8)
        self._b(L, "👁 Analizar imagen…", self.inspire).pack(anchor="w", padx=8, pady=4)
        self.lbl_insp = ctk.CTkLabel(L, text="", font=font(11), text_color=VIOLET, justify="left", wraplength=350)
        self.lbl_insp.pack(anchor="w", padx=8)
        self._h(L, "8 · Guardar")
        r = ctk.CTkFrame(L, fg_color="transparent")
        r.pack(fill="x", padx=6)
        self.v_out = ctk.StringVar(value="1280×720 (YouTube)")
        self._menu(r, list(SIZES), self.v_out, w=170).pack(side="left", padx=2)
        self._b(r, "💾 Guardar…", self.export, GREEN, text_color="#04121a").pack(side="left", padx=4)
        self._b(r, "🔎 Revisar con IA", self.review).pack(side="left", padx=4)
        self._b(L, "✨ Pulir con IA (rondas hasta superar 8,5)", self.polish).pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkLabel(L, text="Eliges carpeta, nombre y formato: PNG (sin pérdida), JPG, WEBP, BMP o TIFF.",
                     font=font(11), text_color=MUTED, justify="left", wraplength=350).pack(anchor="w", padx=8)
        r = ctk.CTkFrame(L, fg_color="transparent")
        r.pack(fill="x", padx=6, pady=(4, 12))
        self._b(r, "Guardar proyecto", self.save_project).pack(side="left", padx=2)
        self._b(r, "Abrir proyecto", self.open_project).pack(side="left", padx=2)

    def _build_right(self, R):
        R.grid_columnconfigure(0, weight=1)
        R.grid_rowconfigure(0, weight=1)
        self.box = ctk.CTkFrame(R, fg_color="#000000", corner_radius=10)
        self.box.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))
        self.box.grid_propagate(False)
        self.view = ctk.CTkLabel(self.box, text="", fg_color="transparent")
        self.view.place(relx=.5, rely=.5, anchor="center")
        self.view.bind("<ButtonPress-1>", self._press)
        self.view.bind("<B1-Motion>", self._move)
        self.view.bind("<ButtonRelease-1>", lambda _e: (setattr(self, "_drag", None), self.refresh()))
        self.box.bind("<Configure>", lambda _e: self.refresh())
        bot = ctk.CTkFrame(R, fg_color="transparent")
        bot.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.pb = ctk.CTkProgressBar(bot, progress_color=CYAN, fg_color=SURF2)
        self.pb.set(0)
        self.pb.pack(fill="x")
        self.lbl = ctk.CTkLabel(bot, text="Elige una plantilla, pon un fondo y un personaje o tu foto.", font=font(12),
                                text_color=MUTED, anchor="w", justify="left", wraplength=900)
        self.lbl.pack(fill="x", pady=(4, 0))

    def status(self, t, color=MUTED, f=None):
        try:
            self.lbl.configure(text=t, text_color=color)
            if f is not None:
                self.pb.set(max(0.0, min(1.0, f)))
        except Exception:
            pass

    def ui(self, fn):
        try:
            self.after(0, fn)
        except Exception:
            pass

    # ------------------------------------------------------------------ vista previa
    def refresh(self, now=False):
        if self._prev_job is not None:
            try:
                self.after_cancel(self._prev_job)
            except Exception:
                pass
        self._prev_job = self.after(1 if now else 40, self._draw)

    # ------------------------------------------------------------------ atajos de teclado y deshacer
    KEYS_HELP = ("Ctrl+Z deshacer · Ctrl+Y rehacer · Supr borrar capa · Flechas mover (Shift: más) · + / − tamaño · "
                 "Tab siguiente capa · Ctrl+D duplicar · Ctrl+H espejo · RePág/AvPág adelante/atrás · Esc soltar · "
                 "Ctrl+S guardar imagen · Ctrl+Shift+S guardar proyecto · Ctrl+O abrir proyecto")

    def _bind_keys(self):
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

        def k(seq, fn, when_typing=False):
            def h(e):
                if typing(e) and not when_typing:
                    return None
                try:
                    fn(e)
                except Exception:
                    pass
                return "break"
            self.bind(seq, h)
        k("<Control-z>", lambda e: self.undo(), True)
        k("<Control-Z>", lambda e: self.redo(), True)
        k("<Control-y>", lambda e: self.redo(), True)
        k("<Delete>", lambda e: self._delete())
        k("<Escape>", lambda e: self.select(None), True)
        k("<Tab>", lambda e: self._next_layer())
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            k(f"<{key}>", lambda e, dx=dx, dy=dy: self._nudge(dx * .005, dy * .005))
            k(f"<Shift-{key}>", lambda e, dx=dx, dy=dy: self._nudge(dx * .03, dy * .03))
        for key in ("plus", "KP_Add", "equal"):
            k(f"<{key}>", lambda e: self._grow(1.06))
        for key in ("minus", "KP_Subtract"):
            k(f"<{key}>", lambda e: self._grow(1 / 1.06))
        k("<Control-d>", lambda e: self._duplicate())
        k("<Control-h>", lambda e: self._set_sel("flip", None))
        k("<Prior>", lambda e: self._order(1))
        k("<Next>", lambda e: self._order(-1))
        k("<Control-s>", lambda e: self.export(), True)
        k("<Control-S>", lambda e: self.save_project(), True)
        k("<Control-o>", lambda e: self.open_project(), True)

    def _snapshot(self):
        """Guarda el estado anterior para Ctrl+Z (se llama al dibujar, si algo cambió y no estás arrastrando)."""
        import copy
        try:
            cur = json.dumps(self.proj, sort_keys=True, ensure_ascii=False)
        except Exception:
            return
        if self._last_state is None:
            self._last_state = cur
            return
        if cur != self._last_state and self._drag is None:
            self._undo.append(self._last_state)
            del self._undo[:-60]
            self._redo.clear()
            self._last_state = cur

    def _restore(self, state):
        self.proj = json.loads(state)
        self._last_state = state
        self.sel = None
        for key, sl in self.v_fx.items():
            sl.set(self.proj.get("fx", {}).get(key, 0))
        self._rebuild_texts()
        self.select(None)

    def undo(self):
        if not self._undo:
            self.status("No hay nada que deshacer.", MUTED)
            return
        self._redo.append(self._last_state)
        self._restore(self._undo.pop())
        self.status("Deshecho (Ctrl+Y para rehacer).", MUTED)

    def redo(self):
        if not self._redo:
            return
        self._undo.append(self._last_state)
        self._restore(self._redo.pop())

    def _next_layer(self):
        L = self.proj["layers"]
        if L:
            self.select(0 if self.sel is None else (self.sel + 1) % len(L))

    def _nudge(self, dx, dy):
        if self.sel is None:
            return
        lay = self.proj["layers"][self.sel]
        lay["x"] = round(lay.get("x", .5) + dx, 4)
        lay["y"] = round(lay.get("y", .5) + dy, 4)
        self.refresh()

    def _grow(self, f):
        if self.sel is None:
            return
        lay = self.proj["layers"][self.sel]
        key = "size" if lay["kind"] == "text" else "h"
        lay[key] = max(.02, min(1.6, lay.get(key, .15 if key == "size" else .9) * f))
        try:
            self.s_size.set(lay[key])
        except Exception:
            pass
        self.refresh()

    def _duplicate(self):
        import copy
        if self.sel is None or self.proj["layers"][self.sel].get("cover"):
            return
        lay = copy.deepcopy(self.proj["layers"][self.sel])
        lay["x"] = lay.get("x", .5) + .03
        lay["y"] = lay.get("y", .5) + .03
        self.proj["layers"].insert(self.sel + 1, lay)
        self._rebuild_texts()
        self.select(self.sel + 1)

    def _draw(self):
        self._snapshot()
        self._prev_job = None
        try:
            scale = ctk.ScalingTracker.get_widget_scaling(self)
            bw, bh = self.box.winfo_width() - 20, self.box.winfo_height() - 20
            if bw < 50 or bh < 50:
                return
            W, H = self.proj["size"]
            k = min(bw / W, bh / H)
            pw, ph = max(16, int(W * k)), max(9, int(H * k))
            boxes = []
            img = M.render(self.proj, pw, ph, boxes)
            self._boxes = boxes
            if self.sel is not None:
                b = next((b for b in boxes if b[0] == self.sel), None)
                if b:
                    d = ImageDraw.Draw(img)
                    d.rectangle((b[1] * pw, b[2] * ph, b[3] * pw - 1, b[4] * ph - 1), outline=(34, 211, 238, 255),
                                width=2)
            self._pw, self._ph = pw, ph
            self._prev_img = ctk.CTkImage(img.convert("RGB"), size=(pw / scale, ph / scale))
            self.view.configure(image=self._prev_img)
        except Exception:
            _log("vista previa")

    def _hit(self, e):
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        x, y = e.x * scale / max(1, self._pw), e.y * scale / max(1, self._ph)
        for i, x0, y0, x1, y1 in reversed(self._boxes):
            lay = self.proj["layers"][i]
            if lay.get("cover"):
                continue
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i, x, y
        bg = next((i for i, l in enumerate(self.proj["layers"]) if l.get("cover")), None)
        return bg, x, y

    def _press(self, e):
        try:
            i, x, y = self._hit(e)
            self.select(i)
            if i is not None:
                lay = self.proj["layers"][i]
                self._drag = (x, y, lay.get("x", .5), lay.get("y", .5))
        except Exception:
            _log("tocar")

    def _move(self, e):
        if self._drag is None or self.sel is None:
            return
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        x, y = e.x * scale / max(1, self._pw), e.y * scale / max(1, self._ph)
        x0, y0, lx, ly = self._drag
        lay = self.proj["layers"][self.sel]
        if lay.get("cover"):                          # el fondo se encuadra (qué parte se ve)
            lay["x"] = min(1, max(0, lx - (x - x0) * 2))
            lay["y"] = min(1, max(0, ly - (y - y0) * 2))
        else:
            lay["x"], lay["y"] = lx + (x - x0), ly + (y - y0)
        self.refresh()

    # ------------------------------------------------------------------ capas
    def select(self, i):
        self.sel = i
        if i is None:
            self.lbl_sel.configure(text="Toca una capa en la vista")
        else:
            lay = self.proj["layers"][i]
            if lay["kind"] == "text":
                self.lbl_sel.configure(text=f"Texto: «{lay['text']}»")
                self.s_size.configure(from_=0.03, to=0.35)
                self.s_size.set(lay.get("size", .15))
                self.v_style.set(lay.get("style", "Impacto"))
                self.m_style.pack(side="left", padx=4)
            else:
                self.lbl_sel.configure(text="Fondo (arrastra para encuadrar)" if lay.get("cover") else
                                       "Imagen: " + os.path.basename(lay.get("path", "")))
                self.s_size.configure(from_=0.1, to=1.6)
                self.s_size.set(lay.get("h", .9))
                self.m_style.pack_forget()
                inv = {v: k for k, v in GLOWS.items()}
                self.v_glow.set(inv.get(lay.get("glow", ""), "Sin borde"))
        self.refresh()

    def _set_sel(self, key, v):
        if self.sel is None:
            return
        lay = self.proj["layers"][self.sel]
        if key == "size":
            lay["size" if lay["kind"] == "text" else "h"] = float(v)
        elif key == "flip":
            lay["flip"] = not lay.get("flip")
        elif key == "style" and lay["kind"] == "text":
            lay["style"] = v
            for k in ("fill", "stroke", "stroke_w", "accent", "glow"):   # al elegir estilo, sus colores mandan
                lay.pop(k, None)
            self._rebuild_texts()
        elif key == "glow" and lay["kind"] == "image":
            lay["glow"] = v
        self.refresh()

    def _order(self, d):
        if self.sel is None:
            return
        L = self.proj["layers"]
        j = self.sel + d
        if 0 <= j < len(L) and not L[j].get("cover") and not L[self.sel].get("cover"):
            L[self.sel], L[j] = L[j], L[self.sel]
            self.sel = j
            self._rebuild_texts()
            self.refresh()

    def _delete(self):
        if self.sel is None:
            return
        del self.proj["layers"][self.sel]
        self.sel = None
        self._rebuild_texts()
        self.select(None)

    def _card(self):
        if self.sel is None:
            return
        lay = self.proj["layers"][self.sel]
        if lay["kind"] != "image" or lay.get("cover"):
            return
        if lay.get("frame"):
            lay["frame"], lay["badge"] = "", ""
        else:
            n = sum(1 for l in self.proj["layers"] if l.get("frame")) + 1
            lay["frame"], lay["badge"] = "#22d3ee", f"#{n}"
        self.refresh()

    def add_text(self, text="Nuevo texto", style="Impacto", x=.05, y=.4, size=.12, align="left"):
        self.proj["layers"].append({"kind": "text", "text": text, "style": style, "x": x, "y": y, "size": size,
                                    "align": align})
        self._rebuild_texts()
        self.select(len(self.proj["layers"]) - 1)

    def _rebuild_texts(self):
        for w in self.txt_box.winfo_children():
            w.destroy()
        for i, lay in enumerate(self.proj["layers"]):
            if lay["kind"] != "text":
                continue
            row = ctk.CTkFrame(self.txt_box, fg_color=SURF2, corner_radius=8)
            row.pack(fill="x", pady=2)
            # un título en varias líneas se muestra con « / » (la casilla es de una línea) y se vuelve a partir igual
            v = ctk.StringVar(value=lay["text"].replace("\n", " / "))
            e = ctk.CTkEntry(row, textvariable=v, fg_color=SURF3, border_width=0, font=font(13, "bold"))
            e.pack(side="left", fill="x", expand=True, padx=6, pady=6)

            def changed(*_a, lay=lay, v=v):
                lay["text"] = "\n".join(p.strip() for p in v.get().split(" / ")) if " / " in v.get() else v.get()
                self.refresh()
            v.trace_add("write", changed)
            e.bind("<FocusIn>", lambda _e, i=i: (setattr(self, "sel", i), self.refresh()))
            ctk.CTkLabel(row, text=lay["style"], font=font(10), text_color=VIOLET).pack(side="left", padx=4)

    def add_image(self, path, background=False, glow=""):
        L = self.proj["layers"]
        if background:
            L[:] = [l for l in L if not l.get("cover")]
            L.insert(0, {"kind": "image", "path": path, "cover": True, "x": .5, "y": .5})
            idx = 0
        else:
            first_text = next((i for i, l in enumerate(L) if l["kind"] == "text"), len(L))
            n_img = sum(1 for l in L if l["kind"] == "image" and not l.get("cover"))
            L.insert(first_text, {"kind": "image", "path": path, "x": .74 - .22 * (n_img % 3), "y": .58, "h": 1.0,
                                  "glow": glow})
            idx = first_text
        self._rebuild_texts()
        self.select(idx)

    def apply_template(self, name, keep_images=True):
        t = TEMPLATES[name]
        imgs = [l for l in self.proj["layers"] if l["kind"] == "image"] if keep_images else []
        self.proj["fx"] = dict(t["fx"])
        texts = [{"kind": "text", "text": tx, "style": st, "x": x, "y": y, "size": s, "align": al}
                 for tx, st, x, y, s, al in t["texts"]]
        self.proj["layers"] = imgs + texts
        for k, s in self.v_fx.items():
            s.set(self.proj["fx"].get(k, 0))
        self.v_side.set(self.proj["fx"].get("shade_side", "left"))
        self.sel = None
        self._rebuild_texts()
        self.status(f"Plantilla «{name}». Cambia los textos y agrega fondo y personajes.")
        self.refresh()

    def set_title(self, text, style="Impacto"):
        """Pone un solo título arriba al centro (lo que pediste entre comillas)."""
        self.proj["layers"] = [l for l in self.proj["layers"] if l["kind"] != "text"]
        self.proj["fx"].update(shade=.55, shade_side="top")
        self.v_fx["shade"].set(.55)
        self.v_side.set("top")
        self.add_text(text, style, x=.5, y=.04, size=.15, align="center")
        self.status(f"Título «{text}» en estilo {style}: arrástralo, cambia el estilo o agrega más textos.", GREEN)

    def auto_build(self):
        text = self.t_auto.get("1.0", "end").strip()
        if not text:
            self.status("Escribe qué miniatura quieres (fondo, personajes y título entre comillas).", AMBER)
            return

        def work():
            import miniatura_auto
            proj, tp = miniatura_auto.build(text, lambda m, f: self.ui(lambda: self.status(m, MUTED, f)), self.cancel)
            self.started = True
            self.ui(lambda: (self.load_project(proj),
                             self.status(f"Lista: {len(tp['characters'])} personaje(s) y título «{tp['title']}». "
                                         "Ajusta lo que quieras y pulsa «Guardar…».", GREEN, 1)))
        self._task(work)

    def _load_saved(self):
        import miniatura_auto
        for w in self.saved_box.winfo_children():
            w.destroy()
        self._saved_imgs = []
        items = miniatura_auto.list_saved()[:12]
        if not items:
            ctk.CTkLabel(self.saved_box, text="(todavía no guardaste ninguno)", font=font(11),
                         text_color=MUTED).pack(anchor="w", padx=2)
            return
        for k, (name, path) in enumerate(items):
            try:
                with Image.open(path) as im:
                    im = im.convert("RGBA")
                    im.thumbnail((64, 80))
                    img = ctk.CTkImage(im.copy(), size=im.size)
            except Exception:
                continue
            self._saved_imgs.append(img)
            cell = ctk.CTkFrame(self.saved_box, fg_color=SURF2, corner_radius=8)
            cell.grid(row=k // 4, column=k % 4, padx=3, pady=3)
            ctk.CTkButton(cell, image=img, text="", width=70, height=84, fg_color="transparent", hover_color=SURF3,
                          command=lambda p=path: self.add_image(p, glow="")).pack()
            ctk.CTkLabel(cell, text=name[:10], font=font(10), text_color=MUTED).pack()

    def save_selected_character(self):
        if self.sel is None:
            self.status("Toca primero un personaje en la vista.", AMBER)
            return
        lay = self.proj["layers"][self.sel]
        if lay["kind"] != "image" or lay.get("cover"):
            self.status("Elige un personaje (una imagen sin fondo), no el fondo ni un texto.", AMBER)
            return
        d = ctk.CTkInputDialog(text="Nombre del personaje (para reusarlo y nombrarlo en tus prompts):",
                               title="Guardar personaje")
        name = (d.get_input() or "").strip()
        if not name:
            return
        import miniatura_auto
        try:
            p = miniatura_auto.save_character(lay["path"], name)
            self._load_saved()
            self.status(f"Guardado «{name}». Escribe «{name}» en una miniatura automática y se usará tal cual.",
                        GREEN)
            lay["path"] = lay["path"] if os.path.isfile(lay["path"]) else p
        except Exception as e:
            self.status(f"No se pudo guardar: {e}", RED)

    def polish(self):
        """Tu IA califica y corrige la miniatura en varias rondas; se queda con la mejor."""
        if not any(l["kind"] == "image" for l in self.proj["layers"]):
            self.status("Agrega primero un fondo o una imagen.", AMBER)
            return
        import copy
        import miniatura_auto
        proj = copy.deepcopy(self.proj)

        def work():
            best, score, hist = miniatura_auto.improve(proj, cancel=self.cancel,
                                                       say=lambda m, f: self.ui(lambda: self.status(m, MUTED, f)))
            start = hist[0][1] if hist else 0
            msg = (f"Pulida: {start} → {score}/10 en {len(hist)} ronda(s). " + miniatura_auto.JUDGE_SCALE)
            self.ui(lambda: (self.load_project(best), self.status(msg, GREEN, 1)))
        self._task(work)

    def review(self):
        """Tu IA (Gemma 4) mira la miniatura como un diseñador: nota y qué mejorar."""
        if not any(l["kind"] == "image" for l in self.proj["layers"]):
            self.status("Agrega primero un fondo o una imagen.", AMBER)
            return
        tmp = os.path.join(WORK, "revisar.png")
        os.makedirs(WORK, exist_ok=True)
        M.render(self.proj, 1280, 720).convert("RGB").save(tmp)

        def work():
            slow = ia.judge_choice() == "Exigente"
            self.ui(lambda: self.status("Tu IA está mirando la miniatura (" + ("juez exigente, ~3 min" if slow
                                                                                else "~30 s") + ")…", MUTED, None))
            d = ia.critique_thumbnail(tmp)
            txt = (f"Nota {d.get('nota', '?')}/10 · Bien: " + "; ".join(d.get("bien", [])) +
                   " · Mejorar: " + "; ".join(d.get("mejorar", [])))
            self.ui(lambda: self.status(txt, GREEN))
        self._task(work)

    def load_project(self, proj):
        self.proj = proj
        self.sel = None
        for k, s in self.v_fx.items():
            s.set(self.proj.get("fx", {}).get(k, 0))
        self.v_side.set(self.proj.get("fx", {}).get("shade_side", "left"))
        self._rebuild_texts()
        self.status("Capas cargadas: mueve, cambia tamaños o textos, o reemplaza un personaje.", GREEN)
        self.refresh()

    def _set_fx(self, k, v):
        self.proj["fx"][k] = float(v) if isinstance(v, float) else v
        self.refresh()

    # ------------------------------------------------------------------ imágenes
    def pick_image(self, background, mine=False):
        from tkinter import filedialog
        init = os.path.join(os.path.expanduser("~"), "Pictures", "Imagenes IA") if mine else None
        p = filedialog.askopenfilename(parent=self, title="Elige una imagen", initialdir=init,
                                       filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff")])
        if not p:
            return
        if background:
            self.add_image(p, background=True)
            return
        if _has_transparency(p):
            self.add_image(p, glow="")
            self.status("Tu imagen ya tiene fondo transparente: la puse tal cual.", GREEN)
            return
        self._task(self._cut_task, p, "foto", "#22d3ee")

    def _cut_task(self, src, kind, glow, white=False, screen=""):
        os.makedirs(WORK, exist_ok=True)
        dst = os.path.join(WORK, f"recorte_{datetime.datetime.now():%Y%m%d_%H%M%S}.png")
        ia.cutout(src, dst, kind, say=lambda m, f=None: self.ui(lambda: self.status(m, MUTED, f)),
                  white=white and not screen, screen=screen)
        if white or screen:                       # personaje de la IA: si toca un borde, sin esquinas rectas
            try:
                import miniatura_auto
                tch = miniatura_auto.touching(src, screen or "white")
                soft = [sd for sd, v in tch.items() if v > .01 and sd != "bottom"]
                if soft:
                    miniatura_auto.soften_cut_edges(dst, soft)
            except Exception:
                pass
        self.ui(lambda: (self.add_image(dst, glow=glow), self.status("Listo: arrástrala a donde quieras.", GREEN)))

    def _task(self, fn, *a):
        if self.busy:
            self.status("Espera a que termine lo que está haciendo.", AMBER)
            return
        self.busy = True
        self.cancel.clear()

        def run():
            try:
                fn(*a)
            except RuntimeError as e:
                self.ui(lambda e=e: self.status("Cancelado." if str(e) == "CANCELLED" else f"⚠ {e}", RED))
            except Exception as e:
                _log("tarea")
                self.ui(lambda e=e: self.status(f"⚠ Algo falló: {e}", RED))
            finally:
                self.busy = False
        threading.Thread(target=run, daemon=True).start()

    def _start_engine(self):
        ia.free_ollama_gpu()
        if ia.start(say=lambda m, f: self.ui(lambda: self.status(m, MUTED, f)), cancel=self.cancel):
            self.started = True

    def gen_background(self):
        text = self.e_bg.get().strip()
        if not text:
            self.status("Escribe cómo quieres el fondo (o súbelo).", AMBER)
            return

        def work():
            self.ui(lambda: self.status("Tu IA prepara el fondo…", MUTED, .02))
            pl = ia.plan(text + ", wide background scene, no people, sin personas", "Automático", ia.AUTO)
            self._start_engine()
            dst = os.path.join(WORK, f"fondo_{datetime.datetime.now():%Y%m%d_%H%M%S}.png")
            ia.generate(pl["prompt"], dst, pl["engine"], (1344, 768), "", negative=pl["negative"], cancel=self.cancel,
                        say=lambda m, f: self.ui(lambda: self.status("Fondo: " + m, MUTED, f)))
            self.ui(lambda: (self.add_image(dst, background=True),
                             self.status(f"Fondo listo ({pl['engine'].split(' (')[0]}).", GREEN)))
        self._task(work)

    def gen_character(self):
        text = self.e_ch.get().strip()
        if not text:
            self.status("Describe el personaje (o sube tu foto).", AMBER)
            return
        anime = self.v_anime.get()
        tag, phrase = FRAMINGS[self.v_frame.get()]

        def work():
            self.ui(lambda: self.status("Tu IA prepara el personaje…", MUTED, .02))
            have = ia.available_engines()
            eng = "Anime (Animagine XL 4)" if anime and "Anime (Animagine XL 4)" in have else ia.AUTO
            pl = ia.plan(text + (", estilo anime" if anime else ""), "Anime" if anime else "Automático", eng,
                         have=have)
            scr = ia.pick_screen(text, ia.screen_wish())      # pantalla verde/azul/magenta/blanca
            self._screen = scr
            if ia.ENGINES[pl["engine"]].get("words") == "tags":
                prompt = pl["prompt"].replace(", masterpiece", f", {tag}, " + ia.screen_prompt(scr, True) +
                                              ", masterpiece")
            else:
                prompt = pl["prompt"] + f", {phrase}, isolated on a " + ia.screen_prompt(scr) + ", studio lighting"
            self._start_engine()
            outs = []
            for k in range(4):
                if self.cancel.is_set():
                    raise RuntimeError("CANCELLED")
                dst = os.path.join(WORK, f"pers_{datetime.datetime.now():%Y%m%d_%H%M%S}_{k}.png")
                ia.generate(prompt, dst, pl["engine"], (832, 1216), "", negative=pl["negative"], cancel=self.cancel,
                            say=lambda m, f, k=k: self.ui(lambda: self.status(f"Personaje {k + 1} de 4: {m}", MUTED,
                                                                              (k + f) / 4)))
                outs.append(dst)
            self.ui(lambda: self._choose(outs, "anime" if anime else "foto"))
        self._task(work)

    def _choose(self, paths, kind):
        """Muestra las 4 opciones; la elegida se recorta y entra como capa."""
        w = ctk.CTkToplevel(self)
        w.title("Elige tu personaje")
        w.configure(fg_color=BG)
        w.after(150, w.lift)
        ctk.CTkLabel(w, text="Elige el que más te guste: se le quita el fondo y entra a la miniatura.",
                     font=font(13, "bold"), text_color=TXT).pack(padx=12, pady=(12, 6))
        row = ctk.CTkFrame(w, fg_color="transparent")
        row.pack(padx=12, pady=(0, 12))
        w._imgs = []
        for p in paths:
            try:
                with Image.open(p) as im:
                    im = im.convert("RGB")
                    im.thumbnail((260, 380))
                    img = ctk.CTkImage(im.copy(), size=im.size)
            except Exception:
                continue
            w._imgs.append(img)
            ctk.CTkButton(row, image=img, text="", fg_color=SURF2, hover_color=CYAN_D, width=im.width + 10,
                          command=lambda p=p: (w.destroy(), self._task(
                              self._cut_task, p, kind, "#ff8c1a", True,
                              "" if getattr(self, "_screen", "white") == "white" else self._screen))).pack(
                side="left", padx=6)
        self.status("Elige uno de los 4 personajes.", CYAN, 1)

    def inspire(self):
        from tkinter import filedialog
        p = filedialog.askopenfilename(parent=self, title="Imagen para inspirarse",
                                       filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if not p:
            return

        def work():
            self.ui(lambda: self.status("Tu IA está mirando la imagen (~30 s la primera vez)…", MUTED, None))
            d = ia.describe_image(p)
            cols = d.get("colores", "")
            cols = ", ".join(cols) if isinstance(cols, list) else str(cols)

            def show():
                self.lbl_insp.configure(text=f"{d.get('descripcion', '')}\nColores: {cols}")
                if d.get("fondo"):
                    self.e_bg.delete(0, "end")
                    self.e_bg.insert(0, d["fondo"])
                if d.get("personaje"):
                    self.e_ch.delete(0, "end")
                    self.e_ch.insert(0, d["personaje"])
                if d.get("texto"):
                    t = next((l for l in self.proj["layers"] if l["kind"] == "text"), None)
                    if t:
                        t["text"] = str(d["texto"]).title()
                        self._rebuild_texts()
                self.status("Listo: puse sus ideas en Fondo y Personaje. Revísalas y pulsa «Crear».", GREEN)
                self.refresh()
            self.ui(show)
        self._task(work)

    # ------------------------------------------------------------------ guardar
    def export(self):
        if not any(l["kind"] == "image" for l in self.proj["layers"]):
            self.status("Agrega al menos un fondo o una imagen.", AMBER)
            return
        W, H = SIZES[self.v_out.get()]
        from tkinter import filedialog
        last = _cfg().get("last_dir") or OUT_DIR
        os.makedirs(last, exist_ok=True)
        ext = _cfg().get("last_ext", ".png")
        types = sorted(M.SAVE_TYPES, key=lambda t: t[1] != "*" + ext)
        path = filedialog.asksaveasfilename(parent=self, title="Guardar miniatura", initialdir=last,
                                            initialfile=datetime.datetime.now().strftime("miniatura_%Y%m%d_%H%M%S") + ext,
                                            defaultextension=ext, filetypes=types)
        if not path:
            return
        ext = os.path.splitext(path)[1].lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"):
            path, ext = path + ".png", ".png"
        _cfg(last_dir=os.path.dirname(path), last_ext=ext)
        proj = copy.deepcopy(self.proj)

        def work():
            self.ui(lambda: self.status("Guardando en alta calidad…", MUTED, .5))
            img = M.render(proj, W, H)
            M.save_image(img if ext in (".png", ".webp", ".tif", ".tiff") else img.convert("RGB"), path)
            size = os.path.getsize(path)
            with open(os.path.splitext(path)[0] + ".json", "w", encoding="utf-8") as f:
                json.dump(proj, f, ensure_ascii=False, indent=1)
            kind = "sin pérdida" if ext in (".png", ".bmp", ".tif", ".tiff") else "calidad alta"
            msg = f"✔ Guardada: {path} ({W}×{H}, {size / 2**20:.1f} MB, {ext[1:].upper()} {kind})."
            if size > 2 * 1024 * 1024:
                yt = os.path.splitext(path)[0] + "_youtube.jpg"
                M.save_image(img.convert("RGB"), yt)
                msg += f" YouTube acepta hasta 2 MB: también guardé {os.path.basename(yt)} para subirla."
            self.ui(lambda: (self.status(msg, GREEN, 1), self._open_folder(path)))
        self._task(work)

    def _open_folder(self, p):
        try:
            import subprocess
            subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
        except Exception:
            pass

    def save_project(self):
        from tkinter import filedialog
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".json", initialdir=OUT_DIR,
                                         filetypes=[("Proyecto de miniatura", "*.json")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.proj, f, ensure_ascii=False, indent=1)
            self.status("Proyecto guardado.", GREEN)

    def open_project(self):
        from tkinter import filedialog
        p = filedialog.askopenfilename(parent=self, initialdir=OUT_DIR, filetypes=[("Proyecto de miniatura", "*.json")])
        if not p:
            return
        try:
            with open(p, encoding="utf-8") as f:
                self.proj = json.load(f)
            self.sel = None
            for k, s in self.v_fx.items():
                s.set(self.proj.get("fx", {}).get(k, 0))
            self._rebuild_texts()
            self.refresh()
            self.status("Proyecto abierto.", GREEN)
        except Exception as e:
            self.status(f"No se pudo abrir: {e}", RED)

    def _close(self):
        self.cancel.set()
        if self.busy:
            ia.interrupt()
        if self.started:
            threading.Thread(target=ia.stop, daemon=True).start()
        self.destroy()


def open_editor(master, start_image=None, title=None, title_style=None, project=None):
    try:
        return ThumbEditor(master, start_image, title, title_style, project)
    except Exception:
        _log("abrir")
        return None
