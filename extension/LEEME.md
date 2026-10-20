# Candidatos BPower: extensión de captura manual 1.2.0

Esta extensión es independiente del instalador de OCC/Computrabajo. No necesita Python ni Selenium. Funciona en Chrome de escritorio; no es una aplicación para Chrome de Android o iPhone. La interfaz se adapta a ventanas pequeñas.

## Instalar en Chrome

1. Descarga `Extension-Candidatos-Manual-1.2.0.zip` desde el repositorio personal `marcoantonio1999/occ-candidatos` y descomprímelo en una carpeta permanente y privada.
2. Abre `chrome://extensions` en Chrome de escritorio.
3. Activa **Modo de desarrollador**, pulsa **Cargar descomprimida** y selecciona la carpeta que contiene `manifest.json`.
4. En el menú de extensiones (pieza de rompecabezas), fija **Candidatos BPower · Captura manual**.

No está publicada ni revisada en Chrome Web Store ni es una extensión oficial de Indeed. Si el equipo de tu empresa no permite cargar extensiones, solicita autorización a su responsable; no desactives sus políticas ni protecciones. No carga scripts remotos ni pide acceso a cookies, contraseñas, historial o todos los sitios.

### Si ya tienes la versión 1.0.0 o 1.1.x

Primero pulsa **Guardar respaldo** en la extensión antigua. Cierra su panel, copia el contenido del nuevo ZIP **dentro de la misma carpeta desde la que cargaste la extensión**, reemplazando sus archivos, y pulsa **Recargar** en su tarjeta de `chrome://extensions`. Comprueba que aparezca **1.2.0** y vuelve a abrir el icono. No pulses Quitar ni borres datos de Chrome. Una carpeta nueva puede generar otra instalación independiente sin tu avance; conserva la anterior y el respaldo. Si instalas en otra carpeta, usa **Recuperar un respaldo** en la nueva para trasladarlo.

## Agregar cada candidato

1. En el Chrome habitual, inicia sesión manualmente en Indeed y abre una postulación individual. La extensión no abre ni recorre perfiles.
2. Pulsa el icono de la extensión y escribe la **vacante** (se recuerda para los siguientes candidatos).
3. Pulsa **Agregar este candidato**. Si se identifica un único perfil, queda guardado inmediatamente y aparece su ficha para revisar o completar.
4. Vero abre manualmente el siguiente perfil y repite el clic. No hay cambio automático de página ni ejecución periódica.

Se identifica cada postulación por sus IDs de vacante y candidatura cuando Indeed los proporciona, no por nombre ni teléfono. Los enlaces nuevos sin `legacyJobId` usan el ID del perfil y la vacante escrita: indica siempre el mismo nombre completo, incluida ubicación si distingue puestos. Ese contexto se conserva como fragmento local `#bpower-vacancy=…` del enlace guardado; no se adivina un ID oculto ni se exportan `listQuery`, `l` u otros parámetros del navegador. Una persona en otra vacante queda en otra fila. Volver a agregar la misma postulación no duplica ni sobrescribe sus correcciones. Si ya existe con otro formato de enlace en esa misma vacante, se pide abrir **Revisar** en lugar de duplicar o fusionar registros sin certeza. La recaptura normal solo completa campos vacíos de contacto y secciones visibles.

Para leer el teléfono, pulsa primero el icono **Llamar** de Indeed para mostrar el cuadro con el nombre y número, y después abre la extensión y pulsa **Agregar este candidato**. La extensión no pulsa el icono por ti ni realiza llamadas. Reconoce el cuadro del candidato actual aunque Indeed marque el fondo como oculto para accesibilidad. No usa números de otros candidatos ni de cuadros ambiguos. Si el teléfono guardado estaba vacío, la recaptura lo completa; si ya tenía un valor, se conserva.

La lectura es conservadora: nombre del perfil y contacto solo cuando esté visible y vinculado a esa ficha. Experiencia, educación, habilidades e idiomas se capturan solo si aparecen como secciones HTML visibles con encabezados inequívocos. **No pulsa Llamar, no abre datos ocultos, no lee PDF incrustados ni imágenes de CV, no descarga CV y no inventa información.** Puedes completar esos campos en **Revisar → Experiencia, educación y notas**, copiando únicamente información que puedas consultar legítimamente. El estado de visto/no visto no se deduce de abrir la ficha; se completa manualmente si el portal lo indica.

Si Indeed solicita una verificación o no se identifica el perfil, no se agrega nada, no se insiste y se conserva todo el avance anterior. El modo **Completar datos manualmente** permite introducir datos y el enlace individual, sin leer la página. Abrir perfiles manualmente puede marcarlos como revisados en Indeed.

## Avance y exportación

- Los registros y el borrador del formulario se guardan en `chrome.storage.local` del perfil de Chrome que uses, no en sincronización, Supabase, Render ni otro servidor.
- Cerrar la ventana, el popup o reiniciar Chrome no borra los registros confirmados. Reabre el icono para verlos. Un error al guardar muestra un aviso; no se afirma que quedó guardado si falló la escritura.
- **Descargar una copia de Excel** genera un `.xlsx` real con todos los registros guardados, aunque uses el buscador. Teléfonos e identificadores se conservan como texto; no se ejecutan fórmulas que pudiera contener un campo.
- En **Abrir panel amplio → Actualizar el mismo Excel**, usa **Seleccionar Excel existente** para vincular un Excel exportado por esta extensión, o **Crear Excel vinculado** para elegir uno nuevo vacío. **Actualizar este Excel** escribe en ese mismo archivo, no descarga otra copia. Chrome puede solicitar permiso y conserva el vínculo en este perfil cuando sea posible. No hay escritura automática ni sondeo: se actualiza al pulsar el botón.
- La actualización de un archivo existente agrega solo postulaciones que no estén en su columna **Perfil de origen**. Conserva todas las filas existentes sin modificarlas, incluidas sus notas y correcciones, columnas extra y otras hojas. Por tanto, las correcciones posteriores de una ficha en la extensión **no** reemplazan esa fila en el Excel: puedes corregirla directamente en Excel o descargar una copia nueva. No borres la columna de origen ni cambies las 13 columnas originales de la hoja **Candidatos**.
- Cierra Excel antes de actualizar. Se vuelve a leer el archivo, se detectan cambios concurrentes antes de escribir y solo se confirma el guardado al terminar. Un archivo inválido, protegido, cifrado, con macros, tablas estructuradas o más de 20 MB se rechaza sin sobrescribirlo. Para tablas estructuradas, conviértelas a rango antes de actualizar. Si no hay postulaciones nuevas, no se escribe nada. El vínculo no importa registros del Excel al almacenamiento de la extensión; para trasladar el avance usa JSON.
- **Guardar respaldo** exporta un JSON. **Recuperar un respaldo** agrega los que falten sin sobrescribir registros existentes. Sirve para trasladar el avance a otro Chrome autorizado.
- Exporta respaldos regularmente. **Quitar la extensión, borrar sus datos o eliminar el perfil de Chrome sí puede borrar el avance.** Guarda el JSON antes de hacerlo. Conserva la misma carpeta al actualizarla con Cargar descomprimida.
- Excel y JSON contienen datos personales: no los subas a Git ni los compartas con personas no autorizadas. El almacenamiento local de Chrome no sustituye el cifrado ni la protección de acceso del equipo.

## Límites conocidos y validación

La interfaz de Indeed puede cambiar. Esta versión reconoce `/candidates/view?id=…` con o sin `legacyJobId`, incluidos enlaces con parámetros de lista como el reportado por Vero. IDs inválidos o repetidos, varios perfiles visibles y verificaciones detienen la captura, sin reintentos ni pérdida del avance. No tiene acceso a candidatos retirados sin enlace de perfil. Los errores de validación indican el problema concreto; un perfil no reconocido no se presenta automáticamente como bloqueo de Cloudflare.

Las pruebas de esta actualización usan datos sintéticos y cubren enlaces con y sin vacante en la URL, almacenamiento, duplicados, enriquecimiento de campos vacíos, lectura del diálogo de teléfono y preservación de Excel. La captura básica de la versión local anterior se había probado con un perfil real autorizado; no equivale a validar esta actualización instalada en el equipo de Vero. No se garantiza acceso si Indeed o las políticas de Chrome bloquean el sitio o la extensión.
