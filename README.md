# Candidatos de OCC, Computrabajo e Indeed

Descarga los candidatos de una vacante en Excel desde una pantalla sencilla, con avance guardado para continuar después de una interrupción.

## Descargar e instalar

### App de Indeed: JSON a Excel

[![Descargar app de Indeed para Windows](.github/assets/descargar-indeed.svg)](https://github.com/marcoantonio1999/occ-candidatos/releases/download/indeed-json-v1.0.0/Indeed-JSON-BPower-Instalador.exe)

**Vero: usa este botón azul para la nueva app de Indeed.** Selecciona una carpeta con los JSON descargados de las postulaciones y genera automáticamente el Excel con los datos y los CV PDF adjuntos. No necesita Python ni abrir un navegador automatizado.

Es un instalador independiente de OCC/Computrabajo y de la extensión. [Ver instrucciones de uso](indeed-json-app/README.md).

### Extensión manual para Indeed (nueva)

[Descargar extensión actualizada v1.2.0 para Vero](https://github.com/marcoantonio1999/occ-candidatos/releases/download/extension-v1.2.0/Extension-Candidatos-Manual-1.2.0.zip)

Descomprime el ZIP y sigue **LEEME.md**: en Chrome de escritorio abre `chrome://extensions`, activa Modo de desarrollador y usa **Cargar descomprimida** sobre la carpeta con `manifest.json`. Si las políticas de tu equipo no lo permiten, solicita autorización; no las desactives.

Vero abre cada perfil manualmente y pulsa **Agregar este candidato**. Se conserva el avance local, no se duplican postulaciones y se puede exportar a Excel o respaldar/restaurar en JSON. No usa Selenium, no navega automáticamente ni intenta resolver verificaciones. No lee CV en PDF ni descarga archivos; los datos no visibles se pueden completar a mano. Consulta [las instrucciones completas](extension/LEEME.md).

La versión **1.2.0** reconoce también los enlaces nuevos de Indeed sin `legacyJobId`, corrige la lectura del teléfono mostrado en **Llamar** y permite seleccionar/actualizar un mismo Excel desde el panel amplio. Agrega solo postulaciones nuevas y conserva filas, anotaciones y otras hojas. No realiza llamadas ni navega entre candidatos.

**Para actualizar sin perder el avance:** guarda primero un respaldo JSON desde la extensión antigua, reemplaza sus archivos en **la misma carpeta** y pulsa **Recargar** en `chrome://extensions`. Debe mostrar **v1.2.0**. No quites la extensión anterior antes de respaldar. [Instrucciones completas de actualización y límites](extension/LEEME.md).

La extensión no está publicada en Chrome Web Store ni es oficial de Indeed. Las pruebas automáticas usan datos ficticios y la captura básica también se contrastó con un perfil real autorizado, sin descargar CV ni modificar su estado. El instalador anterior de abajo se conserva para OCC/Computrabajo: la prueba de acceso automático a Indeed mostró una verificación de Cloudflare, por lo que no se garantiza ese flujo.

### Instalador de escritorio anterior

**Versión 1.2.2 (27/10/2026):** corrige la carga incompleta de perfiles de OCC. Espera los datos antes de leerlos y evita cerrar un panel de contacto que ya está abierto. Si no puede leer el perfil, conserva el candidato pendiente y deja Chrome abierto para revisión, sin recargar ni reintentar automáticamente. Incluye OCC, Computrabajo e Indeed y conserva el avance anterior. Es autocontenido: no requiere Python.

[![Descargar instalador para Windows](https://img.shields.io/badge/⬇_Descargar_instalador_para_Windows-367454?style=for-the-badge)](https://github.com/marcoantonio1999/occ-candidatos/releases/latest/download/OCC-Candidatos-Instalador.exe)

1. Pulsa el botón de descarga y abre **OCC-Candidatos-Instalador.exe**.
2. Confirma la instalación. Se abrirá la pantalla de **Candidatos de OCC, Computrabajo e Indeed**.
3. Para usarlo otro día, abre **Candidatos de OCC** desde el escritorio.

**No necesitas instalar Python ni escribir comandos.** Necesitas Windows 10/11 de 64 bits, Google Chrome y conexión a internet. La primera apertura de OCC puede tardar mientras se prepara el navegador.

El instalador no tiene firma digital. Si tu computadora lo bloquea, solicita ayuda a la persona responsable; no desactives las protecciones de Windows.

La herramienta incluye componentes de código abierto y sus avisos de licencia en la carpeta `licenses`.

## Descargar candidatos

1. Elige **OCC**, **Computrabajo** o **Indeed** y escribe el **nombre de la vacante**.
2. En OCC elige **Todos**, **Solo vistos** o **Solo no vistos**. En Computrabajo e Indeed elige **Descargar todos en un Excel nuevo** o **Actualizar mi Excel anterior**.
3. Pulsa **Comenzar descarga**.
4. En la ventana que se abra, inicia sesión y abre los candidatos de esa misma vacante.
5. Vuelve a la pantalla y pulsa **Ya estoy en la vacante**.
6. Al terminar, pulsa **Descargar Excel**.

El nombre escrito identifica la vacante en el Excel; no cambia por sí solo la vacante seleccionada en OCC. No navegues a otras páginas de OCC mientras la herramienta trabaja.

### Actualizar el Excel de Computrabajo

Después de tu primera descarga, elige **Actualizar mi Excel anterior** y abre la misma vacante. La herramienta recorre sus páginas y las listas de recibidos, seleccionados, finalistas y descartados disponibles; no incluye candidatos sugeridos que no se postularon. Agrega candidatos nuevos y actualiza los ya recopilados por su identificador del portal, conservando los anteriores aunque ya no aparezcan en la lista.

La actualización utiliza el historial guardado en esta computadora y genera una copia nueva del Excel. No sobrescribe archivos ni importa modificaciones hechas manualmente en Excel. Si necesitas actualizar desde otra computadora, conserva la carpeta de datos y solicita ayuda antes de trasladarla.

Computrabajo no mostró un indicador inequívoco de visto/no visto en la lista revisada: su columna se exporta como **No identificado**, sin inventar el estado. Abrir perfiles puede marcarlos como vistos. El nombre, teléfono cuando está disponible, experiencia, formación, habilidades e idiomas se leen del perfil visible; no se envían mensajes ni se consumen créditos.

### Indeed

Abre **Administrar a los candidatos → Todas las postulaciones** de una sola vacante y pulsa **Ya estoy en la vacante**. La herramienta recorre las páginas y comprueba su total antes de abrir los perfiles. Guarda el estado original que muestra Indeed (por ejemplo, Nuevos o En evaluación), sin deducir visto/no visto. Abrir perfiles puede registrarlos como revisados; se pide aceptar ese aviso antes de comenzar.

Lee únicamente lo accesible con tu sesión: nombre, teléfono mostrado por el panel **Llamar** (no inicia ninguna llamada) y el enlace individual **Descargar CV**. No usa endpoints privados, no extrae cookies, no fuerza el botón de exportación masiva deshabilitado, no evade verificaciones ni consume desbloqueos. Ante un problema de sesión/conexión se guarda el avance y se espera una continuación manual.

Los CV quedan en `resultados/cvs-indeed/<vacante>/<postulación>/`. Excel agrega su ubicación, el resultado de lectura y el texto extraído. Los PDF escaneados, protegidos o sin texto se conservan y se señalan para revisión; no se inventan secciones ni se envían a OCR/IA de terceros. Los documentos no PDF también quedan guardados, sin afirmar que se leyó su contenido.

Las postulaciones retiradas se incluyen con el nombre y el estado visible, sin inventar teléfono, CV o enlace de perfil. Indeed no expone un ID de postulante en esas filas: se identifican como observaciones de esa descarga, no como identidades confirmadas. Al actualizar, esas observaciones se refrescan con la lista actual; las anteriores permanecen en el avance archivado y el Excel anterior. Los perfiles con ID sí conservan su historial y se actualizan por ID, nunca por nombre o teléfono.

Cada plataforma usa su propia sesión local de Chrome. Iniciar sesión en el navegador de Codex no inicia automáticamente la sesión de Chrome de esta herramienta. No se copian credenciales entre navegadores. Mantén privados tanto el Excel como la carpeta de CV.

## Si se interrumpe

Si una descarga pendiente bloquea la selección de Indeed, pulsa **Guardar pendiente y elegir otra plataforma**. El avance se conserva sin iniciar otra descarga; después puedes seleccionarlo en **Pendientes guardados → Recuperar pendiente** y continuar. Si acabas de actualizar y aún aparece la pantalla anterior, cierra la aplicación anterior (no solo la pestaña) y vuelve a abrir el acceso del escritorio. La versión nueva muestra **1.2.2** arriba.

En OCC, «CV: 0» no se considera prueba de que el candidato no tenga información: también puede ser una carga incompleta. Si después de la espera no hay datos legibles, la descarga se pausa sin marcarlo como terminado. Chrome queda abierto para revisar lo que muestra OCC. **Continuar descarga** cierra esa ventana antes de abrir otra sesión; solo continúa por acción manual y no vuelve a recopilar los perfiles ya guardados. Una verificación humana o sesión vencida también detiene la lectura, sin intentar evadirlas.

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

Extensión: `node --test extension-tests/extension.test.mjs`; el ZIP se genera con `build-extension.ps1`. El directorio `extension-tests/` es solo de desarrollo, nunca forma parte del ZIP ni se instala con la extensión.

</details>
