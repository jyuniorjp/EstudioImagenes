# Estudio de Imágenes

App de escritorio para Windows que crea imágenes con IA **en tu PC, sin internet**, usando una tarjeta NVIDIA.
ComfyUI corre escondido como motor; tu IA local (Ollama) prepara los pedidos y revisa los resultados.

## Qué hace
- **Modelo automático:** Qwen lee lo que pides (en español) y elige el modelo: Animagine XL 4 para anime y
  personajes conocidos (Pokémon, Genshin…), Z-Image Turbo para fotos, arte y texto, FLUX opcional.
  También puedes elegirlo a mano.
- **Revisión:** Gemma 4 mira cada imagen y comprueba que tenga lo pedido (género, objetos, colores); si falta
  algo, la dibuja otra vez reforzando eso.
- **Miniaturas de YouTube por capas:** fondo, personajes recortados (pantalla de color + BiRefNet), título con
  letras perfectas donde y como lo pidas, versiones A/B/C, juez de miniaturas y pulido automático.
- **Editor de miniaturas** con capas, plantillas, personajes guardados y atajos (Ctrl+Z, flechas, Supr…).
- Imágenes de referencia (hasta 3, o Ctrl+V), ampliar 2x/4x, quitar fondo, guardar en PNG/JPG/WEBP/BMP/TIFF.
- 11 medidas (1:1, 3:4, 16:9, 9:16, 21:9…) y personalizada. Ayuda opcional de internet (AniList y Wikipedia).

## Requisitos
Windows 10/11 de 64 bits, tarjeta NVIDIA de 4 GB o más (mejor 6 GB) con controlador 580+, 16 GB de RAM y
unos 20 GB libres. La primera vez la app explica qué descarga, cuánto pesa y lo instala con un botón.

## Compilar
Doble clic en `COMPILAR_IMAGENES.bat`: crea el entorno de Python, compila `EstudioImagenes.exe` con
PyInstaller y arma el instalador con Inno Setup 6.7+.

Más detalles de uso en [LEEME_IMAGENES.txt](LEEME_IMAGENES.txt).

Este Estudio también viene integrado en [Audio Novela Studio](https://github.com/jyuniorjp/AudioNovelaStudio),
donde crea los fondos de los videos.
