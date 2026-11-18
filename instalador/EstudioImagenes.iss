; Instalador de Estudio de Imágenes (Inno Setup 6.7+). Lo compila COMPILAR_IMAGENES.bat.
; Iconos y arte del asistente hechos con el propio Estudio (Z-Image Turbo) y convertidos a .ico/.bmp.

#ifndef AppVer
  #define AppVer "1.0.0"
#endif
#define AppName "Estudio de Imágenes"
#define AppExe "EstudioImagenes.exe"

[Setup]
; No cambiar nunca el AppId: así una versión nueva reemplaza a la anterior
AppId={{6B3E2F0A-58C4-4E1F-9C27-0E5D1A6B7C01}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=Kuon Studio
AppComments=Crea imágenes con IA en tu PC, sin internet
DefaultDirName={autopf}\Estudio de Imagenes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
InfoBeforeFile=info_estudio.txt
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..
OutputBaseFilename=Instalar_EstudioImagenes_{#AppVer}
SetupIconFile=..\iconos_imagenes\neon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
; diseño: estilo moderno oscuro (como la app), barra de título también oscura, arte propio a los lados
WizardStyle=modern dark includetitlebar
WizardImageFile=estudio_lateral.bmp,estudio_lateral_150.bmp,estudio_lateral_200.bmp,estudio_lateral_250.bmp
WizardSmallImageFile=estudio_pequena.bmp,estudio_pequena_150.bmp,estudio_pequena_200.bmp,estudio_pequena_250.bmp
WizardImageStretch=yes
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
es.WelcomeLabel1=Bienvenido a Estudio de Imágenes
es.WelcomeLabel2=Crea portadas, fondos para tus videos e imágenes de lo que describas, en tu PC y sin internet.%n%nLa IA entiende lo que escribes en español, elige el mejor modelo (anime, fotos, arte o texto) y dibuja con tu tarjeta NVIDIA.%n%nAl abrirla por primera vez, si esta PC no tiene el motor, la app revisa tu tarjeta y te explica qué descargar, cuánto pesa y lo instala con un botón.
es.FinishedHeadingLabel=¡Listo para crear!
es.FinishedLabel=Estudio de Imágenes quedó instalado.%n%nConsejo: abre «💡 Ejemplos y consejos» para ver qué se puede hacer y cómo describir mejor.

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"
Name: "icono_neon"; Description: "Neón (cian y violeta)"; GroupDescription: "Tema del icono (puedes cambiarlo luego en la app):"; Flags: exclusive
Name: "icono_atardecer"; Description: "Atardecer (naranja y rosa)"; GroupDescription: "Tema del icono (puedes cambiarlo luego en la app):"; Flags: exclusive unchecked
Name: "icono_sakura"; Description: "Sakura (anime, rosa)"; GroupDescription: "Tema del icono (puedes cambiarlo luego en la app):"; Flags: exclusive unchecked
Name: "icono_galaxia"; Description: "Galaxia (morado y estrellas)"; GroupDescription: "Tema del icono (puedes cambiarlo luego en la app):"; Flags: exclusive unchecked
Name: "icono_minimal"; Description: "Minimal (claro)"; GroupDescription: "Tema del icono (puedes cambiarlo luego en la app):"; Flags: exclusive unchecked

[Files]
Source: "..\dist_imagenes\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\iconos_imagenes\*.ico"; DestDir: "{app}\iconos"; Flags: ignoreversion
Source: "..\LEEME_IMAGENES.txt"; DestDir: "{app}"; DestName: "LEEME.txt"; Flags: ignoreversion

[INI]
Filename: "{userappdata}\AudioNovelaStudio\estudio_icono.ini"; Section: "icono"; Key: "tema"; String: "neon"; Tasks: icono_neon
Filename: "{userappdata}\AudioNovelaStudio\estudio_icono.ini"; Section: "icono"; Key: "tema"; String: "atardecer"; Tasks: icono_atardecer
Filename: "{userappdata}\AudioNovelaStudio\estudio_icono.ini"; Section: "icono"; Key: "tema"; String: "sakura"; Tasks: icono_sakura
Filename: "{userappdata}\AudioNovelaStudio\estudio_icono.ini"; Section: "icono"; Key: "tema"; String: "galaxia"; Tasks: icono_galaxia
Filename: "{userappdata}\AudioNovelaStudio\estudio_icono.ini"; Section: "icono"; Key: "tema"; String: "minimal"; Tasks: icono_minimal

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\neon.ico"; Tasks: icono_neon
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\neon.ico"; Tasks: escritorio and icono_neon
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\atardecer.ico"; Tasks: icono_atardecer
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\atardecer.ico"; Tasks: escritorio and icono_atardecer
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\sakura.ico"; Tasks: icono_sakura
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\sakura.ico"; Tasks: escritorio and icono_sakura
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\galaxia.ico"; Tasks: icono_galaxia
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\galaxia.ico"; Tasks: escritorio and icono_galaxia
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\minimal.ico"; Tasks: icono_minimal
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\iconos\minimal.ico"; Tasks: escritorio and icono_minimal

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName} ahora"; Flags: nowait postinstall skipifsilent

; Al desinstalar no se borran tus imágenes (Imágenes\Imagenes IA) ni el motor y modelos (la carpeta IA que elegiste).
