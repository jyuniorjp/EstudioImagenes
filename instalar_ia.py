# -*- coding: utf-8 -*-
"""Instalador de «Imágenes con IA» para cualquier PC con Windows y tarjeta NVIDIA.

Descarga ComfyUI portable (motor que dibuja con la tarjeta), su extensión GGUF y los modelos que el usuario elija;
deja la configuración lista y hace una imagen de prueba. Todo se puede reanudar: si se corta internet o se cancela,
al volver a pulsar «Instalar» sigue donde quedó (archivos .part) y no vuelve a bajar lo que ya está completo.
"""
import ctypes
import json
import os
import shutil
import subprocess
import time
import urllib.request
import zipfile

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioNovelaStudio")
CFG = os.path.join(CFG_DIR, "imagenes_ia.json")
HF = "https://huggingface.co"
GB = 1024 ** 3
MIN_DRIVER = 580          # el ComfyUI portable usa CUDA 13 (controlador NVIDIA 580 o más nuevo)
GGUF_COMMIT = "6ea2651e7df66d7585f6ffee804b20e92fb38b8a"

# archivo: (url, carpeta relativa a la base, nombre, bytes)
F = {
    "7zr": ("https://www.7-zip.org/a/7zr.exe", "descargas", "7zr.exe", 602624),
    "comfy": ("https://github.com/Comfy-Org/ComfyUI/releases/download/v0.45.0/ComfyUI_windows_portable_nvidia.7z",
              "descargas", "ComfyUI_windows_portable_nvidia.7z", 2071479423),
    "gguf": (f"https://github.com/city96/ComfyUI-GGUF/archive/{GGUF_COMMIT}.zip", "descargas", "ComfyUI-GGUF.zip", 0),
    "ae": (HF + "/Comfy-Org/Z-Image-Turbo/resolve/main/split_files/vae/ae.safetensors", "modelos/vae",
           "ae.safetensors", 335304388),
    "zimage": (HF + "/jayn7/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q5_K_M.gguf", "modelos/unet",
               "z_image_turbo-Q5_K_M.gguf", 5522742336),
    "qwen": (HF + "/unsloth/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q6_K.gguf", "modelos/text_encoders",
             "Qwen3-4B-Q6_K.gguf", 3306261792),
    "anime": (HF + "/cagliostrolab/animagine-xl-4.0/resolve/main/animagine-xl-4.0-opt.safetensors",
              "modelos/checkpoints", "animagine-xl-4.0-opt.safetensors", 6938350040),
    "jugg": (HF + "/RunDiffusion/Juggernaut-XL-Lightning/resolve/main/Juggernaut_RunDiffusionPhoto2_Lightning_4Steps"
                  ".safetensors", "modelos/checkpoints", "Juggernaut_XL_Lightning_4Steps.safetensors", 7105348284),
    "clip_l": (HF + "/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors", "modelos/text_encoders",
               "clip_l.safetensors", 246144152),
    "t5": (HF + "/city96/t5-v1_1-xxl-encoder-gguf/resolve/main/t5-v1_1-xxl-encoder-Q4_K_M.gguf",
           "modelos/text_encoders", "t5-v1_1-xxl-encoder-Q4_K_M.gguf", 2896123072),
    "schnell": (HF + "/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q4_K_S.gguf", "modelos/unet",
                "flux1-schnell-Q4_K_S.gguf", 6783943712),
    "dev": (HF + "/city96/FLUX.1-dev-gguf/resolve/main/flux1-dev-Q4_K_S.gguf", "modelos/unet",
            "flux1-dev-Q4_K_S.gguf", 6805988640),
    "ollama_setup": ("https://ollama.com/download/OllamaSetup.exe", "descargas", "OllamaSetup.exe", 0),
    "up_anime": ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
                 "modelos/upscale_models", "RealESRGAN_x4plus_anime_6B.pth", 17938799),
    "up_foto": ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
                "modelos/upscale_models", "RealESRGAN_x4plus.pth", 67040989),
    "cut_anime": ("https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx",
                  "modelos/quitar_fondo", "isnet-anime.onnx", 176069933),
    "cut_foto": ("https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
                 "modelos/quitar_fondo", "isnet-general-use.onnx", 178648008),
    "cut_pro": ("https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-epoch_244.onnx",
                "modelos/quitar_fondo", "BiRefNet-general-epoch_244.onnx", 972666916),
    "vcredist": ("https://aka.ms/vc14/vc_redist.x64.exe", "descargas", "vc_redist.x64.exe", 0),
}
VCREDIST_BYTES = 19_000_000
OLLAMA_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
OLLAMA_MODEL_BYTES = 2_500_000_000
VISION_MODEL = "gemma4:e4b-it-qat"            # la IA que ve: revisa las imágenes, juzga miniaturas, mira referencias
VISION_MODEL_BYTES = 6_150_000_000
OLLAMA_SETUP_BYTES = 1_860_000_000

# paquetes que ve el usuario
PACKS = {
    "base": dict(title="Motor de imágenes (ComfyUI)", required=True, default=True,
                 files=["7zr", "comfy", "gguf", "cut_anime", "cut_foto", "up_anime", "up_foto"],
                 extra_gb=4.5,      # lo que ocupa al descomprimir
                 what="El programa que dibuja usando tu tarjeta NVIDIA, sin internet, y el recortador que quita "
                      "fondos para las miniaturas. Obligatorio."),
    "recorte": dict(title="Recortador profesional: BiRefNet", default=True, files=["cut_pro"],
                    what="Saca la silueta completa de los personajes (pelo, capas, espadas) sin el fondo, para "
                         "miniaturas por capas. Mucho más limpio que el recortador básico."),
    "zimage": dict(title="Alta calidad: Z-Image Turbo", default=True, files=["zimage", "qwen", "ae"],
                   what="Fotos realistas, arte, portadas y texto escrito dentro de la imagen. El más recomendado "
                        "(~55 s por imagen)."),
    "anime": dict(title="Anime: Animagine XL 4", default=True, files=["anime"],
                  what="Personajes y escenas estilo anime/manga (~30 s por imagen). Ideal para fondos de "
                       "audionovelas de anime."),
    "jugg": dict(title="Rápida: Juggernaut XL Lightning", default=False, files=["jugg"],
                 what="Fotos realistas en ~15 s. Útil si quieres muchas imágenes rápido."),
    "flux": dict(title="FLUX schnell + dev (extra)", default=False, files=["schnell", "dev", "t5", "clip_l", "ae"],
                 what="Otros dos estilos de ilustración; dev da mucho detalle pero tarda ~2 min por imagen."),
    "ollama": dict(title="Asistente de descripciones (Ollama + Qwen3 4B)", default=True, files=[],
                   what="Entiende lo que escribes en español, elige el mejor modelo y le escribe la descripción. "
                        "Sin él, escribe en inglés y elige el modelo a mano."),
    "vision": dict(title="Revisor de imágenes: Gemma 4 (la IA que ve)", default=True, files=[],
                   what="Mira cada imagen y revisa que tenga lo que pediste (si falta algo, la repite), califica "
                        "las miniaturas y entiende tus imágenes de referencia. Sin él todo funciona, pero sin "
                        "revisión."),
}


def _rmtree(path):
    """Borra una carpeta aunque tenga archivos de solo lectura (los de .git lo son)."""
    import stat

    def onexc(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    if os.path.isdir(path):
        try:
            shutil.rmtree(path, onexc=onexc)
        except TypeError:                       # Python < 3.12
            shutil.rmtree(path, onerror=onexc)


# ------------------------------------------------------------------ estado de la PC
def _run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW,
                           encoding="utf-8", errors="replace")
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def gpu_info():
    """[(nombre, MB de memoria, versión del controlador)] de las tarjetas NVIDIA (vacío si no hay)."""
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            try:
                gpus.append((parts[0], int(float(parts[1])), parts[2]))
            except ValueError:
                pass
    return gpus


def ram_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    try:
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullTotalPhys / GB
    except Exception:
        return 0.0


def free_gb(path):
    try:
        d = os.path.splitdrive(os.path.abspath(path))[0] + "\\"
        return shutil.disk_usage(d).free / GB
    except Exception:
        return 0.0


def default_base():
    """La unidad con más espacio libre (sin contar la de Windows si otra tiene de sobra) + \\IA."""
    best, best_free = "C:", -1.0
    for d in "CDEFGHIJ":
        root = d + ":\\"
        try:
            if ctypes.windll.kernel32.GetDriveTypeW(root) != 3:       # 3 = disco fijo
                continue
            fr = shutil.disk_usage(root).free / GB
        except Exception:
            continue
        if d == "C":
            fr -= 20                    # deja aire a Windows
        if fr > best_free:
            best, best_free = d + ":", fr
    return best + "\\IA"


def vcredist_ok():
    """Librerías de Visual C++ que necesita PyTorch (si faltan, ComfyUI falla con «c10.dll»)."""
    sysdir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    return all(os.path.isfile(os.path.join(sysdir, f)) for f in ("vcruntime140.dll", "vcruntime140_1.dll",
                                                                  "msvcp140.dll"))


def install_vcredist(base, say, cancel):
    if vcredist_ok():
        return
    url, sub, name, size = F["vcredist"]
    dest = os.path.join(base, sub, name)
    say("Descargando componentes de Windows (Visual C++)…", None)
    download(url, dest, size, None, cancel)
    say("Instalando Visual C++ (Windows te pedirá permiso: pulsa «Sí»)…", None)
    ps = (f"$p = Start-Process -FilePath '{dest}' -ArgumentList '/install','/quiet','/norestart' -Verb RunAs "
          "-Wait -PassThru; exit $p.ExitCode")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                       timeout=900, creationflags=NO_WINDOW)
    if not vcredist_ok():                      # 3010 = instalado, pide reiniciar (igual sirve)
        raise RuntimeError("No se pudo instalar Visual C++ (¿se pulsó «No» en el permiso de Windows?). Vuelve a "
                           f"pulsar «Descargar e instalar». Código {r.returncode}.")


def check_pc(base=None):
    """Revisa la PC. Devuelve dict con gpu, vram_gb, driver, ram_gb, free_gb, ok (bool) y avisos (lista)."""
    base = base or default_base()
    gpus = gpu_info()
    g = max(gpus, key=lambda x: x[1]) if gpus else None
    info = dict(gpu=g[0] if g else "", vram_gb=round(g[1] / 1024, 1) if g else 0.0, driver=g[2] if g else "",
                ram_gb=round(ram_gb(), 1), free_gb=round(free_gb(base), 1), base=base, avisos=[], ok=True,
                vcredist=vcredist_ok(), driver_old=False)
    if not g:
        info["ok"] = False
        info["avisos"].append("No encontré una tarjeta NVIDIA. Sin ella, crear imágenes tardaría muchísimo "
                              "(varios minutos por imagen) y no se puede instalar este motor.")
        return info
    try:
        drv = float(g[2].split(".")[0])
    except ValueError:
        drv = 0
    if drv and drv < MIN_DRIVER:
        info["ok"] = False
        info["driver_old"] = True
        info["avisos"].append(f"Tu controlador NVIDIA es {g[2]}; hace falta {MIN_DRIVER} o más nuevo. Actualízalo "
                              "con la app NVIDIA (o nvidia.com/drivers) y vuelve a abrir esta ventana.")
    if info["vram_gb"] < 4:
        info["ok"] = False
        info["avisos"].append(f"Tu tarjeta tiene {info['vram_gb']} GB; hacen falta al menos 4 GB (mejor 6 GB).")
    elif info["vram_gb"] < 6:
        info["avisos"].append(f"Tu tarjeta tiene {info['vram_gb']} GB: funcionará, pero más lento que con 6 GB o más.")
    if info["ram_gb"] and info["ram_gb"] < 12:
        info["avisos"].append(f"Tienes {info['ram_gb']} GB de RAM; con menos de 16 GB los modelos grandes van lentos.")
    return info


def pack_bytes(keys, base=None):
    """Bytes que faltan por bajar para esos paquetes (sin repetir archivos compartidos ni contar los que ya están)."""
    seen, total = set(), 0
    for k in keys:
        for f in PACKS[k]["files"]:
            if f in seen:
                continue
            seen.add(f)
            url, sub, name, size = F[f]
            size = size or 2_000_000
            if base and os.path.isfile(os.path.join(base, sub, name)) and os.path.getsize(
                    os.path.join(base, sub, name)) == size:
                continue
            if f in ("7zr", "comfy", "gguf") and base and is_comfy(os.path.join(base, "ComfyUI_windows_portable")):
                continue
            total += size
        if k == "base" and not vcredist_ok():
            total += VCREDIST_BYTES
        if k == "ollama" and not ollama_has_model():
            total += OLLAMA_MODEL_BYTES
        if k == "vision" and not ollama_has_model(VISION_MODEL):
            total += VISION_MODEL_BYTES
    if ("ollama" in keys or "vision" in keys) and not ollama_installed():
        total += OLLAMA_SETUP_BYTES                 # el programa Ollama se baja una sola vez
    return total


def need_gb(keys, base=None):
    """Espacio en disco necesario (descargas + lo descomprimido)."""
    b = pack_bytes(keys, base) / GB
    if "base" in keys and not (base and is_comfy(os.path.join(base, "ComfyUI_windows_portable"))):
        b += PACKS["base"]["extra_gb"]
    return round(b, 1)


# ------------------------------------------------------------------ dónde quedó instalado
def is_comfy(d):
    return bool(d) and os.path.isfile(os.path.join(d, "python_embeded", "python.exe")) and \
        os.path.isfile(os.path.join(d, "ComfyUI", "main.py"))


def saved_comfy():
    try:
        with open(CFG, encoding="utf-8") as f:
            d = json.load(f).get("comfy_dir", "")
        return d if is_comfy(d) else ""
    except Exception:
        return ""


def _save_cfg(**kw):
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        try:
            with open(CFG, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data.update(kw)
        with open(CFG + ".part", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(CFG + ".part", CFG)
    except OSError:
        pass


# ------------------------------------------------------------------ descarga que se reanuda
class Cancelled(Exception):
    pass


def download(url, dest, size=0, progress=None, cancel=None, tries=6):
    """Baja url a dest (con .part y reanudación). progress(bytes_hechos). Comprueba el tamaño final."""
    if size and os.path.isfile(dest) and os.path.getsize(dest) == size:
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    last_err = None
    for attempt in range(tries):
        have = os.path.getsize(part) if os.path.isfile(part) else 0
        if size and have > size:
            os.remove(part)
            have = 0
        req = urllib.request.Request(url, headers={"User-Agent": "AudioNovelaStudio-instalador/1.0",
                                                   **({"Range": f"bytes={have}-"} if have else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status != 206:            # el servidor no reanuda: empezar de cero
                    have = 0
                total = size or (have + int(r.headers.get("Content-Length") or 0))
                with open(part, "ab" if have else "wb") as f:
                    while True:
                        if cancel is not None and cancel.is_set():
                            raise Cancelled()
                        b = r.read(1 << 20)
                        if not b:
                            break
                        f.write(b)
                        have += len(b)
                        if progress:
                            progress(have)
            if total and have < total:
                raise OSError(f"descarga incompleta ({have} de {total})")
            if size and have != size:
                raise OSError(f"tamaño distinto al esperado ({have} en vez de {size})")
            os.replace(part, dest)
            return dest
        except Cancelled:
            raise
        except Exception as e:
            last_err = e
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            time.sleep(min(30, 3 * (attempt + 1)))
    raise RuntimeError(f"No se pudo descargar {os.path.basename(dest)}: {last_err}")


# ------------------------------------------------------------------ Ollama
def ollama_running():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2).read()
        return True
    except Exception:
        return False


def ollama_installed():
    if ollama_running():
        return True
    for p in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
              r"C:\Program Files\Ollama\ollama.exe"):
        if os.path.isfile(p):
            return True
    return bool(shutil.which("ollama"))


def ollama_has_model(name=OLLAMA_MODEL):
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            return any(m.get("name") == name for m in json.load(r).get("models", []))
    except Exception:
        return False


def _ollama_start():
    for p in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama app.exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")):
        if os.path.isfile(p):
            try:
                args = [p] if p.endswith("app.exe") else [p, "serve"]
                subprocess.Popen(args, creationflags=NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0))
                return
            except Exception:
                pass


def install_ollama(base, say, cancel, models=(OLLAMA_MODEL,)):
    if not ollama_installed():
        url, sub, name, size = F["ollama_setup"]
        dest = os.path.join(base, sub, name)
        say("Descargando Ollama (asistente)…", None)
        download(url, dest, size, lambda b: say(f"Descargando Ollama… {b / GB:.2f} GB", None), cancel)
        say("Instalando Ollama (puede pedir permiso a Windows)…", None)
        r = subprocess.run([dest, "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"], timeout=900)
        if r.returncode != 0 and not ollama_installed():
            raise RuntimeError("No se pudo instalar Ollama.")
    if not ollama_running():
        _ollama_start()
        for _ in range(60):
            if ollama_running():
                break
            time.sleep(1)
    if not ollama_running():
        raise RuntimeError("Ollama quedó instalado pero no arrancó. Ábrelo desde el menú Inicio y vuelve a intentar.")
    names = {OLLAMA_MODEL: "el asistente Qwen3 4B", VISION_MODEL: "el revisor Gemma 4"}
    for model in models:
        if ollama_has_model(model):
            continue
        req = urllib.request.Request("http://127.0.0.1:11434/api/pull",
                                     json.dumps({"model": model, "stream": True}).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3600) as r:
            for line in r:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("error"):
                    raise RuntimeError("Ollama: " + d["error"])
                if d.get("total"):
                    say(f"Bajando {names.get(model, model)}… {d.get('completed', 0) / GB:.2f} de "
                        f"{d['total'] / GB:.2f} GB", d.get("completed", 0) / d["total"])
        if not ollama_has_model(model):
            raise RuntimeError(f"No terminó de bajarse {names.get(model, model)}.")


# ------------------------------------------------------------------ instalación completa
def install(base, keys, say=None, cancel=None):
    """Instala los paquetes elegidos en base (p. ej. D:\\IA). say(texto, fracción 0..1 o None).
    Devuelve la carpeta de ComfyUI. Lanza Cancelled o RuntimeError (con texto en español)."""
    say = say or (lambda *_: None)
    keys = ["base"] + [k for k in keys if k != "base"]
    base = os.path.abspath(base)
    os.makedirs(base, exist_ok=True)
    comfy = os.path.join(base, "ComfyUI_windows_portable")
    need = need_gb(keys, base)
    if free_gb(base) < need + 1:
        raise RuntimeError(f"Falta espacio en {base[:2]}: hacen falta {need} GB y hay {free_gb(base):.1f} GB libres.")
    total = max(1, pack_bytes(keys, base))
    done = [0]

    def grab(fkey):
        url, sub, name, size = F[fkey]
        dest = os.path.join(base, *sub.split("/"), name)
        if size and os.path.isfile(dest) and os.path.getsize(dest) == size:
            return dest
        start = done[0]
        part = dest + ".part"
        already = os.path.getsize(part) if os.path.isfile(part) else 0

        def prog(b):
            say(f"Descargando {name}… {b / GB:.2f} / {(size or b) / GB:.2f} GB",
                min(0.99, (start + b - already) / total))
        download(url, dest, size, prog, cancel)
        done[0] = start + (size or os.path.getsize(dest)) - already
        return dest

    # 0) componentes de Windows que necesita el motor
    install_vcredist(base, say, cancel)
    # 1) motor
    if not is_comfy(comfy):
        z = grab("7zr")
        arc = grab("comfy")
        say("Descomprimiendo el motor (unos minutos)…", None)
        tmp = os.path.join(base, "_extrayendo")
        _rmtree(tmp)
        r = subprocess.run([z, "x", arc, f"-o{tmp}", "-y"], capture_output=True, timeout=3600, creationflags=NO_WINDOW)
        src = os.path.join(tmp, "ComfyUI_windows_portable")
        if r.returncode != 0 or not is_comfy(src):
            _rmtree(tmp)
            try:
                os.remove(arc)          # el archivo podría estar dañado: se vuelve a bajar la próxima vez
            except OSError:
                pass
            raise RuntimeError("No se pudo descomprimir ComfyUI. Vuelve a pulsar «Instalar».")
        if os.path.isdir(comfy):
            _rmtree(comfy)
        os.replace(src, comfy)
        _rmtree(tmp)
        try:
            os.remove(arc)              # 2 GB que ya no hacen falta
        except OSError:
            pass
    # 2) extensión GGUF (modelos comprimidos que caben en tarjetas de 6 GB)
    node = os.path.join(comfy, "ComfyUI", "custom_nodes", "ComfyUI-GGUF")
    if not os.path.isfile(os.path.join(node, "nodes.py")):
        zp = grab("gguf")
        say("Instalando la extensión GGUF…", None)
        with zipfile.ZipFile(zp) as zf:
            root = zf.namelist()[0].split("/")[0]
            tmp = node + "_tmp"
            _rmtree(tmp)
            zf.extractall(tmp)
        _rmtree(node)
        os.replace(os.path.join(tmp, root), node)
        _rmtree(tmp)
    py = os.path.join(comfy, "python_embeded", "python.exe")
    chk = subprocess.run([py, "-s", "-c", "import gguf, sentencepiece, onnxruntime"], capture_output=True,
                         creationflags=NO_WINDOW)
    if chk.returncode != 0:
        say("Instalando librerías de la extensión…", None)
        r = subprocess.run([py, "-s", "-m", "pip", "install", "--no-warn-script-location", "gguf>=0.13.0",
                            "sentencepiece", "protobuf", "onnxruntime"], capture_output=True, text=True, timeout=1800,
                           creationflags=NO_WINDOW, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError("No se pudieron instalar las librerías de GGUF:\n" + (r.stderr or r.stdout)[-400:])
    # 3) dónde están los modelos
    mdir = os.path.join(base, "modelos")
    for sub in ("checkpoints", "unet", "text_encoders", "vae", "loras", "upscale_models"):
        os.makedirs(os.path.join(mdir, sub), exist_ok=True)
    yaml = ("ia_local:\n    base_path: " + mdir.replace("\\", "/") + "/\n    checkpoints: checkpoints/\n"
            "    unet: unet/\n    diffusion_models: unet/\n    text_encoders: text_encoders/\n    clip: text_encoders/\n"
            "    vae: vae/\n    loras: loras/\n    upscale_models: upscale_models/\n")
    with open(os.path.join(comfy, "ComfyUI", "extra_model_paths.yaml"), "w", encoding="utf-8") as f:
        f.write(yaml)
    _save_cfg(comfy_dir=comfy, base=base, installed=keys)
    # 4) modelos
    seen = set()
    for k in keys:
        for fk in PACKS[k]["files"]:
            if fk in seen or fk in ("7zr", "comfy", "gguf"):
                continue
            seen.add(fk)
            grab(fk)
    # 5) asistente
    models = [m for k, m in (("ollama", OLLAMA_MODEL), ("vision", VISION_MODEL)) if k in keys]
    if models:
        install_ollama(base, say, cancel, models)
    say("Instalación completa.", 1.0)
    return comfy


def self_test(say=None, cancel=None):
    """Enciende el motor y hace una imagen pequeña con el modelo más liviano instalado. Devuelve la ruta."""
    import tempfile
    import imagen_ia as ia
    say = say or (lambda *_: None)
    have = ia.available_engines()
    if not have:
        raise RuntimeError("No hay modelos instalados.")
    order = ["Rápida (fotos realistas)", "Anime (Animagine XL 4)", "Alta calidad (Z-Image Turbo)"]
    eng = next((e for e in order if e in have), have[0])
    started = ia.start(say=say, cancel=cancel)
    try:
        out = os.path.join(tempfile.gettempdir(), "prueba_imagen_ia.png")
        say("Haciendo una imagen de prueba…", None)
        ia.generate("a small red house in a green field, blue sky", out, eng, (512, 512), cancel=cancel)
        return out
    finally:
        if started:
            ia.stop()
