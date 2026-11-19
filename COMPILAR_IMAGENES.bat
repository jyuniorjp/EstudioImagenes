@echo off
setlocal
chcp 65001 >nul
title Estudio de Imagenes - Compilando
cd /d "%~dp0"
set "LOG=%~dp0build_imagenes_log.txt"
set "APPVER=1.1.0"
echo === Compilacion Estudio de Imagenes %APPVER% - %date% %time% === > "%LOG%"
set "VPY=%~dp0.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo Creando el entorno de Python .venv la primera vez...
  py -3 -m venv "%~dp0.venv" >> "%LOG%" 2>&1 || python -m venv "%~dp0.venv" >> "%LOG%" 2>&1
  "%VPY%" -m pip install -r "%~dp0requirements.txt" >> "%LOG%" 2>&1
)
if not exist "%VPY%" (
  echo Falta Python 3.12 o mas nuevo: python.org/downloads
  echo BUILD_FAIL >> "%LOG%"
  exit /b 1
)

echo [1/3] Probando los modulos y las pruebas automaticas...
"%VPY%" -c "import numpy, imagen_ia, imagenes_app, instalar_ia, editor_miniaturas, miniaturas, miniatura_auto, web_ayuda, ui_scroll, customtkinter, websockets.sync.client; print('IMPORT_OK')" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo ERROR en los modulos: revisa build_imagenes_log.txt
  echo BUILD_FAIL >> "%LOG%"
  exit /b 1
)
"%VPY%" -m unittest discover -s "%~dp0pruebas" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: alguna prueba automatica fallo. Revisa build_imagenes_log.txt
  echo TESTS_FAIL >> "%LOG%"
  exit /b 1
)

echo [2/3] Compilando EstudioImagenes.exe...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile --windowed --name EstudioImagenes --icon "%~dp0iconos_imagenes\neon.ico" --add-data "%~dp0iconos_imagenes;iconos_imagenes" --add-data "%~dp0ejemplos_ia;ejemplos_ia" --add-data "%~dp0estudio_imagenes.ico;." --add-data "%~dp0fuentes;fuentes" --add-data "%~dp0quitar_fondo.py;." --collect-all customtkinter --hidden-import websockets.sync.client --hidden-import instalar_ia --hidden-import editor_miniaturas --hidden-import miniaturas --hidden-import web_ayuda --hidden-import miniatura_auto --exclude-module pygame --exclude-module matplotlib --distpath dist_imagenes --workpath build_imagenes --specpath build_imagenes imagenes_app.py >> "%LOG%" 2>&1
if not exist "dist_imagenes\EstudioImagenes.exe" (
  echo ERROR al compilar: revisa build_imagenes_log.txt
  echo BUILD_FAIL >> "%LOG%"
  exit /b 1
)

echo [3/3] Creando el instalador...
set "ISCC="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo Falta Inno Setup 6.7 o mas nuevo: jrsoftware.org/isdl.php
  echo INSTALLER_SKIP >> "%LOG%"
  exit /b 1
)
if exist "Instalar_EstudioImagenes_%APPVER%.exe" del /q "Instalar_EstudioImagenes_%APPVER%.exe"
"%ISCC%" /Q "/DAppVer=%APPVER%" "instalador\EstudioImagenes.iss" >> "%LOG%" 2>&1
if not exist "Instalar_EstudioImagenes_%APPVER%.exe" (
  echo No se pudo crear el instalador: revisa build_imagenes_log.txt
  echo INSTALLER_FAIL >> "%LOG%"
  exit /b 1
)
echo INSTALLER_OK >> "%LOG%"
echo BUILD_OK >> "%LOG%"
echo    Listo: Instalar_EstudioImagenes_%APPVER%.exe
