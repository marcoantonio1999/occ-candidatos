# Indeed JSON a Excel BPower

Aplicación independiente para Windows 10/11 x64. Convierte las postulaciones que tú descargas de Indeed, sin Selenium, extensiones, APIs ni servicios en la nube.

1. Instala `Indeed-JSON-BPower-Instalador.exe`. No necesitas Python ni permisos de administrador.
2. En Indeed, descarga el JSON de la postulación desde su menú de tres puntos. Guarda todos los JSON en una carpeta.
3. Abre **Indeed JSON a Excel BPower** y pulsa **Seleccionar carpeta y generar Excel**.
4. La aplicación crea una carpeta nueva `Indeed-Excel-fecha-...` dentro de la seleccionada: `Postulaciones.xlsx`, los PDF/textos recuperados en `CV` y `LEEME-resultado.txt`.

El Excel contiene nombre, correo original, teléfono, vacante, empresa, ubicación, fecha UTC, secciones detectadas del CV y sus rutas relativas. Mantén el Excel y su carpeta CV juntos. No sustituye el correo original por el alias de Indeed. No puede obtener información que no venga en los archivos.

Los duplicados se omiten por ID de postulación y vacante dentro de cada ejecución. No se combinan personas por nombre/teléfono. Cada ejecución regenera todos los JSON de la carpeta, sin leer subcarpetas, sin modificar originales ni sobrescribir un Excel existente. No hay vigilancia de carpetas ni tareas en segundo plano cuando no se está convirtiendo.

Los CV PDF se recuperan byte por byte. La extracción de secciones depende del formato y puede requerir revisión; el TXT conserva el texto leído. No incluye OCR para escaneos. Adjuntos no PDF, Base64 inválido y CV superiores a 30 MB quedan señalados. JSON máximo 45 MB, lectura PDF máximo 50 páginas/25 segundos por archivo. Un JSON inválido se documenta y se continúa con los demás. Pausar termina el archivo actual y guarda lo obtenido.

Los resultados contienen datos personales. Se guardan únicamente en la carpeta seleccionada; compártelos sólo con personal autorizado. Esta aplicación no tiene conexiones de red, telemetría ni actualización automática. El instalador no está firmado digitalmente: no desactives protecciones de Windows si te muestra una alerta.

Si el diseño del CV no permite identificar secciones, el Excel conserva el texto sin clasificar en su última columna y señala la limitación. El PDF original y el TXT permiten revisarlo sin inventar experiencia o estudios.

## Desarrollo

Python 3.12+, Tkinter y pypdf. Para empaquetar: PyInstaller.

```powershell
python -m pip install -r indeed-json-app/requirements.txt
python -m unittest discover -s indeed-json-app -v
powershell -File indeed-json-app/build.ps1
```

Salida: `dist/Indeed-JSON-BPower.exe` (portable) y `dist/Indeed-JSON-BPower-Instalador.exe` (instalador por usuario). Es independiente del instalador OCC y no lo reemplaza. Licencias de Python, Tcl/Tk y pypdf se incluyen con la instalación.
