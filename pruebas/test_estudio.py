# -*- coding: utf-8 -*-
"""Pruebas rápidas del Estudio de Imágenes (sin IA ni motor de imágenes: solo la lógica).

Ejecutar:  .venv\\Scripts\\python.exe -m unittest discover -s pruebas -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import imagen_ia as ia            # noqa: E402
import miniatura_auto as A        # noqa: E402
import miniaturas as M            # noqa: E402


def _write(path, data):
    with open(path, "wb") as f:
        f.write(data)


class Titulo(unittest.TestCase):
    TITAN = ('Fondo: titán con barba gris y una guadaña de energía verde en la mano derecha. '
             'Título arriba a la derecha: "ESCAPÉ DE CRONOS" con letras blancas, borde negro grueso y brillo verde. '
             'Debajo del título, más chico: "CAP 1-5" en letras doradas con borde negro.')

    def test_titulo_lee_solo_su_frase(self):
        s = ia.title_spec(self.TITAN)
        self.assertEqual(s["position"], "right")
        self.assertEqual(s["fill"], "#ffffff")          # no el verde de la guadaña de la frase anterior
        self.assertEqual(s["stroke"], "#000000")
        self.assertEqual(s["glow"], "#19c37d")
        self.assertTrue(s["thick"])

    def test_subtitulo_con_sus_colores(self):
        s = ia.title_spec(self.TITAN, "CAP 1-5")
        self.assertEqual(s["fill"], "#ffc83d")
        self.assertEqual(s["stroke"], "#000000")

    def test_ingles_y_pelo_plateado(self):
        t = ('swordswoman with long silver hair, big text on the right side reading "EL ÚLTIMO DRAGÓN" in huge '
             'bold white capital letters with a thick orange outline')
        s = ia.title_spec(t)
        self.assertEqual(s["style"], "Impacto")          # «silver hair» ya no vuelve las letras cromadas
        self.assertEqual((s["position"], s["fill"], s["stroke"]), ("right", "#ffffff", "#ff7a00"))

    def test_borde_en_espanol(self):
        s = ia.title_spec('letras blancas con borde naranja "HOLA" a la derecha')
        self.assertEqual((s["fill"], s["stroke"]), ("#ffffff", "#ff7a00"))


class Genero(unittest.TestCase):
    def test_palabras_completas(self):
        self.assertEqual(ia.gender_of("a young swordswoman"), "female")     # antes contaba «man»
        self.assertEqual(ia.gender_of("un chico con espada"), "male")
        self.assertEqual(ia.gender_of("una chica y un chico"), "")
        self.assertEqual(ia.gender_of("Mega Rayquaza over the clouds"), "")


class Revisiones(unittest.TestCase):
    def test_no_se_cuelan_cosas_inventadas(self):
        bg = ("A cosmic sky with golden cracks of light; an ancient titan face, gray beard, bright golden eyes, "
              "holding a giant axe")
        ok = ia.relevant_checks(["a dragon made of blue crystal", "glowing blue eyes", "an ancient titan face",
                                 "a giant axe", "bright golden eyes"], bg)
        self.assertNotIn("a dragon made of blue crystal", ok)
        self.assertNotIn("glowing blue eyes", ok)
        self.assertIn("a giant axe", ok)

    def test_genero_solo_para_personas(self):
        self.assertEqual(ia._must_list(["a male character", "a giant serpent"], ""), ["a giant serpent"])
        self.assertEqual(ia._must_list(["a girl", "red cape"], "female")[0], "a woman")


class LecturaDelTitulo(unittest.TestCase):
    def test_comparacion_letra_por_letra(self):
        self.assertNotEqual(ia._plain("NACRO DEL OLVIDO"), ia._plain("NACIDO DEL OLVIDO"))
        self.assertIn(ia._plain("ESCAPÉ DE CRONOS"), ia._plain("ESCAPE DE CRONOS CAP 1-5"))


class PromptEnProsa(unittest.TestCase):
    P = ("YouTube thumbnail, 16:9, anime style.\n\nSKIN RULE (TOP PRIORITY):\n- EXACTLY the same skin.\n\n"
         "LEFT CHARACTER — HADES:\n- Long black hair.\n\nBACKGROUND:\n- A throne room.\n\n"
         'TEXT (custom):\n- Top: "SU PROPIA MADRE" in forged letters.\n\nNo other text or watermark.')

    def test_sin_encabezados_en_mayusculas(self):
        d = ia.drawable(self.P)
        self.assertNotIn("SKIN RULE", d)
        self.assertNotIn("SU PROPIA MADRE", d)           # en el video no va texto
        self.assertIn("Hades", d)
        self.assertIn("On the left side", d)

    def test_miniatura_conserva_el_titulo_exacto(self):
        d = ia.drawable(self.P, keep_text=True)
        self.assertIn('"SU PROPIA MADRE"', d)


class Miniaturas(unittest.TestCase):
    def test_etiqueta_del_capitulo(self):
        self.assertEqual(A.chapter_label(["Capítulo 6: Su propia madre"]), "CAP 6")
        self.assertEqual(A.chapter_label(["Capítulo 1", "Capítulo 5"]), "CAP 1-5")

    def test_encuadre(self):
        self.assertEqual(A.framing_of("una chica, medio cuerpo")[0], "cowboy")
        self.assertEqual(A.framing_of("close-up portrait of a man")[0], "upper")
        self.assertEqual(A.framing_of("swordswoman standing")[0], "full")

    def test_forma_capas_o_una_imagen(self):
        c = {"desc": "x"}
        self.assertEqual(A.decide_mode("una chica montada en un dragón", {"characters": [c]}, {})[0], "single")
        self.assertEqual(A.decide_mode("Hades a la izquierda", {"characters": [c]}, {"Hades": "x.png"})[0], "layers")
        self.assertEqual(A.decide_mode("Hades y Hestia", {"characters": [c, c]}, {})[0], "layers")

    def test_titulo_en_dos_lineas(self):
        self.assertEqual(A._split_title("EL ÚLTIMO DRAGÓN"), "EL ÚLTIMO\nDRAGÓN")

    def test_texto_con_colores_propios(self):
        img, _x, _y = M.render_text({"text": "HOLA\nMUNDO", "style": "Impacto", "fill": "#ffffff", "stroke": "#ff7a00",
                                     "stroke_w": .11, "size": .15, "x": .5, "y": .1, "align": "center"}, 1280, 720)
        self.assertGreater(img.height, 150)              # dos líneas apiladas
        self.assertIsNotNone(img.getchannel("A").getbbox())


class Galeria(unittest.TestCase):
    def test_miniatura_en_cache(self):
        from PIL import Image
        import imagenes_app as app
        d = tempfile.mkdtemp()
        app.THUMB_CACHE = os.path.join(d, "cache")
        p = os.path.join(d, "foto.png")
        Image.new("RGB", (1344, 768), (200, 40, 40)).save(p)
        t1 = app._thumb_image(p)
        self.assertEqual(max(t1.size), 150)
        self.assertEqual(len(os.listdir(app.THUMB_CACHE)), 1)      # la segunda vez sale de la caché
        t2 = app._thumb_image(p)
        self.assertEqual(t1.size, t2.size)


class Rueda(unittest.TestCase):
    def test_al_final_pasa_a_lo_de_fuera(self):
        import ui_scroll
        self.assertTrue(ui_scroll._at_end((0.0, 1.0), -120))       # cabe entero: no se desliza
        self.assertTrue(ui_scroll._at_end((0.5, 1.0), -120))       # abajo del todo y bajando
        self.assertFalse(ui_scroll._at_end((0.5, 1.0), 120))       # pero puede subir
        self.assertFalse(ui_scroll._at_end((0.0, 0.4), -120))


class Limpieza(unittest.TestCase):
    def test_borra_solo_intentos_viejos_y_no_lo_que_usan_tus_proyectos(self):
        import json
        import time
        d = tempfile.mkdtemp()
        work, mine = os.path.join(d, "tmp"), os.path.join(d, "mis_imagenes")
        os.makedirs(work)
        os.makedirs(mine)
        old = time.time() - 5 * 86400
        names = {"auto_pers_20261101_120000_0_capa.png": "queda",          # capa final
                 "auto_fondo_20261101_120000.png": "queda",               # fondo final
                 "auto_fondo_20261101_120000_v2.png": "queda",            # fondo de la versión B
                 "auto_pers_20261101_120000_0_1.png": "se borra",         # intento descartado
                 "auto_pers_20261101_120000_0_1_recorte.png": "se borra",
                 "auto_fondo_20261101_120000_1.png": "se borra",          # redibujo descartado
                 "auto_pers_20261101_120000_0_0.png": "queda",            # lo usa un proyecto guardado
                 "pulir.png": "se borra"}
        for n in names:
            p = os.path.join(work, n)
            _write(p, b"x")
            os.utime(p, (old, old))
        nuevo = os.path.join(work, "auto_pers_20261119_120000_0_1.png")   # intento de hoy: aún no se borra
        _write(nuevo, b"x")
        _write(os.path.join(mine, "miniatura_x.miniatura.json"),
               json.dumps({"layers": [{"path": os.path.join(work, "auto_pers_20261101_120000_0_0.png")}]}).encode())
        A.WORK = work
        n, _size = A.cleanup_work([mine])
        left = set(os.listdir(work))
        for name, fate in names.items():
            self.assertEqual(name in left, fate == "queda", name)
        self.assertIn(os.path.basename(nuevo), left)
        self.assertEqual(n, 4)


class Registro(unittest.TestCase):
    def test_registro_de_errores_con_limite(self):
        import imagenes_app as app
        d = tempfile.mkdtemp()
        old_cfg = app.CFG
        app.CFG = os.path.join(d, "estudio.json")
        try:
            log = os.path.join(d, "error.log")
            _write(log, b"x" * 1_100_000)
            app.log_error("prueba", "detalle")
            self.assertTrue(os.path.isfile(log + ".anterior"))
            self.assertLess(os.path.getsize(log), 1000)
        finally:
            app.CFG = old_cfg


if __name__ == "__main__":
    unittest.main()
