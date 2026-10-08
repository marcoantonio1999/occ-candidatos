# Candidatos de OCC y Computrabajo

Descarga los candidatos de una vacante en Excel desde una pantalla sencilla, con avance guardado para continuar después de una interrupción.

## Descargar e instalar

[![Descargar instalador para Windows](https://img.shields.io/badge/⬇_Descargar_instalador_para_Windows-367454?style=for-the-badge)](https://github.com/marcoantonio1999/occ-candidatos/releases/latest/download/OCC-Candidatos-Instalador.exe)

1. Pulsa el botón de descarga y abre **OCC-Candidatos-Instalador.exe**.
2. Confirma la instalación. Se abrirá la pantalla de **Candidatos de OCC**.
3. Para usarlo otro día, abre **Candidatos de OCC** desde el escritorio.

**No necesitas instalar Python ni escribir comandos.** Necesitas Windows 10/11 de 64 bits, Google Chrome y conexión a internet. La primera apertura de OCC puede tardar mientras se prepara el navegador.

El instalador no tiene firma digital. Si tu computadora lo bloquea, solicita ayuda a la persona responsable; no desactives las protecciones de Windows.

La herramienta incluye componentes de código abierto y sus avisos de licencia en la carpeta `licenses`.

## Descargar candidatos

1. Elige **OCC** o **Computrabajo** y escribe el **nombre de la vacante**.
2. En OCC elige **Todos**, **Solo vistos** o **Solo no vistos**. En Computrabajo elige **Descargar todos en un Excel nuevo** o **Actualizar mi Excel anterior**.
3. Pulsa **Comenzar descarga**.
4. En la ventana que se abra, inicia sesión y abre los candidatos de esa misma vacante.
5. Vuelve a la pantalla y pulsa **Ya estoy en la vacante**.
6. Al terminar, pulsa **Descargar Excel**.

El nombre escrito identifica la vacante en el Excel; no cambia por sí solo la vacante seleccionada en OCC. No navegues a otras páginas de OCC mientras la herramienta trabaja.

### Actualizar el Excel de Computrabajo

Después de tu primera descarga, elige **Actualizar mi Excel anterior** y abre la misma vacante. La herramienta recorre sus páginas y las listas de recibidos, seleccionados, finalistas y descartados disponibles; no incluye candidatos sugeridos que no se postularon. Agrega candidatos nuevos y actualiza los ya recopilados por su identificador del portal, conservando los anteriores aunque ya no aparezcan en la lista.

La actualización utiliza el historial guardado en esta computadora y genera una copia nueva del Excel. No sobrescribe archivos ni importa modificaciones hechas manualmente en Excel. Si necesitas actualizar desde otra computadora, conserva la carpeta de datos y solicita ayuda antes de trasladarla.

Computrabajo no mostró un indicador inequívoco de visto/no visto en la lista revisada: su columna se exporta como **No identificado**, sin inventar el estado. Abrir perfiles puede marcarlos como vistos. El nombre, teléfono cuando está disponible, experiencia, formación, habilidades e idiomas se leen del perfil visible; no se envían mensajes ni se consumen créditos.

## Si se interrumpe

Abre **Candidatos de OCC** de nuevo y pulsa **Continuar descarga**. Lo que ya se guardó no se vuelve a recopilar. Si estabas revisando páginas, la herramienta puede volver a recorrer la lista para completar lo pendiente.

También puedes usar **Pausar y guardar** o **Descargar Excel** para obtener lo recopilado hasta ese momento.

El avance permanece en la misma computadora. No borres la carpeta de datos de la herramienta. Una interrupción puede requerir iniciar sesión o seleccionar la vacante otra vez; no borra los candidatos ya guardados.

## Qué incluye el Excel

Nombre, teléfono, vacante, plataforma, estado original de revisión, experiencia laboral, educación, idiomas, puesto deseado, área de especialidad, habilidades, certificaciones, cursos y enlace del perfil. Los campos que OCC no muestra no se inventan.

**Importante:** leer perfiles no vistos puede marcarlos como vistos en OCC. El Excel conserva el estado original registrado antes de abrirlos. Los perfiles que requieren créditos o desbloqueo se omiten. No se envían mensajes ni se guardan datos en Google Sheets.

Los resultados son datos personales: compártelos únicamente con las personas autorizadas. Ningún candidato, sesión de OCC o archivo de progreso forma parte de este repositorio o del instalador.

<details>
<summary>Información para mantenimiento</summary>

El instalador guarda la aplicación, su sesión y su progreso en `%LOCALAPPDATA%\OCC-Candidatos`, sin requerir permisos de administrador. La pantalla escucha únicamente en `127.0.0.1`, valida el host y utiliza una clave temporal para sus operaciones. El avance JSON se guarda mediante reemplazo atómico, sincronización a disco y copia anterior de recuperación.

Para desarrollar: instala `requirements-build.txt`, ejecuta `python -m unittest discover -p "test*.py"` y usa `build-installer.ps1` en Windows. La aplicación y su instalador autocontenido se construyen con PyInstaller. El instalador conserva los datos existentes, crea accesos en el escritorio y en Inicio, y abre la pantalla. No hay descarga de candidatos durante las pruebas automatizadas.

</details>
