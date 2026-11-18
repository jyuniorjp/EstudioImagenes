# Estudio de páginas de generación de imágenes (17/11/2026)

Objetivo: ver qué ofrecen las páginas de generación de imágenes con IA y llevar a nuestro **Estudio de Imágenes** (local, sin internet) lo que tu PC puede hacer.

## Cómo se hizo
- **REA (navegador automático)**: se abrió cada página en un Chrome aislado y se leyó su árbol de accesibilidad (nombres de botones, menús, opciones) y la captura de pantalla. Solo se observó: no se inició sesión ni se copió código.
  - **Krea** (krea.ai): leída completa (Evidencia REA `ev_945cede932fb…`).
  - **OpenArt** (openart.ai/home): página de inspiración (Evidencia `ev_a7e014ad4023…`); el resto pide registro.
  - **Ideogram, Leonardo**: protegidas por Cloudflare («verificando que no eres un robot»). No se intentó saltar la protección.
  - **Adobe Firefly**: «Access Denied» al navegador automático.
- **Búsqueda web** (reseñas y guías públicas) para los sitios bloqueados y para generadores de miniaturas (Pikzels, Canva, Thumbnail.AI).

## Lo que ofrecen (y qué pasa en nuestra app)

| Función que vimos | Dónde | En nuestra app |
|---|---|---|
| Agente: «descríbelo y el agente lo hace» | Krea Agent | ✔ Modo Automático + miniatura automática por capas |
| Barra simple: proporción (3:4…), Estilo, resolución (1K), «Image prompt», Generar | Krea | ✔ Medidas, estilos, «Más detalle»; **nuevo: imagen de referencia** |
| Imagen de referencia / estilo / personaje (Image Guidance, Omni Reference, Character) | Leonardo, Midjourney, Ideogram | **Nuevo: «📎 Imagen de referencia» + «Cuánto cambiar»** (parte de tu imagen). Referencia de personaje consistente: pendiente (necesita IP-Adapter) |
| Ampliador hasta 22K | Krea Upscaler | **Nuevo: «Ampliar 2x / 4x» con Real-ESRGAN** (anime y fotos, 3-4 s) |
| Quitar fondo | Krea Background Remover | **Nuevo: «✂ Quitar el fondo» en ⋯ Más** (ya existía en el editor) |
| 1000+ estilos, presets en un clic | Krea | Parcial: 8 estilos + 10 ejemplos con «Crear ahora» |
| Inspiración por categorías (Marketing, Film, Anime, Música…) | OpenArt | **Nuevo: categorías en Inspiración** (Anime, Fotos, Portadas y texto, Arte, Fondos) |
| Editar con palabras (Kontext, Nano Banana, Qwen Edit) | Krea Image Editor | Pendiente: los modelos de edición no caben bien en 6 GB |
| Tiempo real (dibujas y renderiza al instante) | Krea Realtime | Pendiente (necesita ControlNet/modelos turbo) |
| Entrenar tu estilo o personaje (LoRA) | Krea Train, Leonardo | Pendiente (entrenar en 6 GB es muy lento) |
| Miniaturas: texto editable, personas guardadas, revisar CTR, variantes A/B | Pikzels, Canva | ✔ Editor por capas + textos perfectos; **nuevo: «🔎 Revisar con IA» (nota 1-10 y qué mejorar)**. Variantes A/B y «personajes guardados»: siguiente paso |

## Mejoras hechas a partir del estudio
1. **Imagen de referencia** (izquierda): eliges una imagen y la nueva parte de ella. «Cuánto cambiar» va de «se parece» a «solo inspiración». Probado: el castillo nevado pasó a otro estilo manteniendo la composición (60 s).
2. **Menú «⋯ Más»** sobre tus imágenes: Ampliar 2x / 4x (Real-ESRGAN, anime o foto según la imagen), Quitar el fondo (PNG transparente), Usar como referencia, Revisar como miniatura.
3. **Revisar con IA**: Gemma 4 mira la miniatura como un diseñador (legibilidad, contraste, foco, lo cortado) y da nota y consejos. Probado con la miniatura del dragón: 7/10 en 27 s.
4. **Categorías en Inspiración**: filtra los ejemplos por tipo.
5. El instalador para otras PC ahora también baja los ampliadores (85 MB).

## Siguientes pasos posibles (por valor)
- Variantes A/B de miniaturas (2-3 versiones y la IA dice cuál funciona mejor).
- «Personajes guardados»: guardar un personaje recortado y reusarlo en otras miniaturas.
- Referencia de personaje consistente (IP-Adapter para SDXL/Animagine, ~1 GB).
- Biblioteca de estilos con vista previa (como los presets de Krea).

## Fuentes
- Krea: https://www.krea.ai/ (REA) · OpenArt: https://openart.ai/home (REA)
- https://www.neolemon.com/blog/ai-image-generators-that-support-image-reference/
- https://www.layer3labs.io/comparisons/leonardo-ai-alternatives
- https://selfielabstudio.com/blog/leonardo-ai-character-reference-mastery-2026-20260306
- https://theaipicker.com/midjourney-review/
- https://nesyona.com/articles/ideogram-vs-leonardo-ai-2026
- https://magichour.ai/blog/ai-youtube-thumbnail-generators
- https://subscribed.fyi/blog/pikzels-ai-transform-ideas-into-stunning-youtube-thumbnails-in-seconds/
- https://www.unkoa.com/canva-vs-pikzels-2025-which-thumbnail-maker-drives-more-views-for-solo-youtubers/
- https://1of10.com/blog/best-ai-thumbnail-generator/
