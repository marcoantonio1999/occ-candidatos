# Candidatos BPower: extensión de captura manual 1.0.0

Esta extensión es independiente del instalador de OCC/Computrabajo. No necesita Python ni Selenium. Funciona en Chrome de escritorio; no es una aplicación para Chrome de Android o iPhone. La interfaz se adapta a ventanas pequeñas.

## Instalar en Chrome

1. Descarga `Extension-Candidatos-Manual-1.0.0.zip` desde el repositorio personal `marcoantonio1999/occ-candidatos` y descomprímelo en una carpeta permanente y privada.
2. Abre `chrome://extensions` en Chrome de escritorio.
3. Activa **Modo de desarrollador**, pulsa **Cargar descomprimida** y selecciona la carpeta que contiene `manifest.json`.
4. En el menú de extensiones (pieza de rompecabezas), fija **Candidatos BPower · Captura manual**.

No está publicada ni revisada en Chrome Web Store ni es una extensión oficial de Indeed. Si el equipo de tu empresa no permite cargar extensiones, solicita autorización a su responsable; no desactives sus políticas ni protecciones. No carga scripts remotos ni pide acceso a cookies, contraseñas, historial o todos los sitios.

## Agregar cada candidato

1. En el Chrome habitual, inicia sesión manualmente en Indeed y abre una postulación individual. La extensión no abre ni recorre perfiles.
2. Pulsa el icono de la extensión y escribe la **vacante** (se recuerda para los siguientes candidatos).
3. Pulsa **Agregar este candidato**. Si se identifica un único perfil, queda guardado inmediatamente y aparece su ficha para revisar o completar.
4. Vero abre manualmente el siguiente perfil y repite el clic. No hay cambio automático de página ni ejecución periódica.

Se identifica cada postulación por sus IDs de vacante y candidatura, no por nombre ni teléfono. Una persona en otra vacante queda en otra fila. Volver a agregar la misma postulación no duplica ni sobrescribe sus correcciones.

La lectura es conservadora: nombre del perfil y contacto solo cuando esté visible y vinculado a esa ficha. Experiencia, educación, habilidades e idiomas se capturan solo si aparecen como secciones HTML visibles con encabezados inequívocos. **No pulsa Llamar, no abre datos ocultos, no lee PDF incrustados ni imágenes de CV, no descarga CV y no inventa información.** Puedes completar esos campos en **Revisar → Experiencia, educación y notas**, copiando únicamente información que puedas consultar legítimamente. El estado de visto/no visto no se deduce de abrir la ficha; se completa manualmente si el portal lo indica.

Si Indeed solicita una verificación o no se identifica el perfil, no se agrega nada, no se insiste y se conserva todo el avance anterior. El modo **Completar datos manualmente** permite introducir datos y el enlace individual, sin leer la página. Abrir perfiles manualmente puede marcarlos como revisados en Indeed.

## Avance y exportación

- Los registros y el borrador del formulario se guardan en `chrome.storage.local` del perfil de Chrome que uses, no en sincronización, Supabase, Render ni otro servidor.
- Cerrar la ventana, el popup o reiniciar Chrome no borra los registros confirmados. Reabre el icono para verlos. Un error al guardar muestra un aviso; no se afirma que quedó guardado si falló la escritura.
- **Exportar a Excel** genera un `.xlsx` real con todos los registros guardados, aunque uses el buscador. Teléfonos e identificadores se conservan como texto; no se ejecutan fórmulas que pudiera contener un campo.
- **Guardar respaldo** exporta un JSON. **Recuperar un respaldo** agrega los que falten sin sobrescribir registros existentes. Sirve para trasladar el avance a otro Chrome autorizado.
- Exporta respaldos regularmente. **Quitar la extensión, borrar sus datos o eliminar el perfil de Chrome sí puede borrar el avance.** Guarda el JSON antes de hacerlo. Conserva la misma carpeta al actualizarla con Cargar descomprimida.
- Excel y JSON contienen datos personales: no los subas a Git ni los compartas con personas no autorizadas. El almacenamiento local de Chrome no sustituye el cifrado ni la protección de acceso del equipo.

## Límites conocidos y validación

La interfaz de Indeed puede cambiar. Esta versión reconoce el formato de perfil `/candidates/view?id=…&legacyJobId=…`; si cambia o el candidato aparece solo en la lista, falla de forma conservadora y ofrece captura manual. No tiene acceso a candidatos retirados sin enlace de perfil.

Pruebas con perfiles y contactos sintéticos, almacenamiento simulado, lectura DOM y exportación XML/ZIP. No se instalará en la cuenta de Vero ni se descargarán postulaciones reales como parte de la validación. No se garantiza acceso si Indeed o las políticas de Chrome bloquean el sitio o la extensión.
