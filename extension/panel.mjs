import {captureOpenCandidate} from './capture.mjs';
import {FIELDS,profileIdentity} from './model.mjs';
import {exportXlsx} from './xlsx.mjs';
import {appendCandidates,updateExcelHandle} from './excel-file.mjs';
import {fileLink} from './file-link.mjs';
const $=id=>document.getElementById(id);
let records=[],active=null,busy=false;
let excelHandle=null;
const popup=new URLSearchParams(location.search).has('popup');
const pickerSupported=typeof window.showOpenFilePicker==='function'&&typeof window.showSaveFilePicker==='function';
const excelType={description:'Excel de Candidatos BPower',accept:{'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':['.xlsx']}};
function renderFile(){
  $('linkedFile').textContent=excelHandle?`Archivo vinculado: ${excelHandle.name}`:'Ningún Excel vinculado.';
  $('selectExcel').disabled=$('createExcel').disabled=busy||popup||!pickerSupported;
  $('updateExcel').disabled=busy||popup||!pickerSupported||!excelHandle||!records.length;
  $('fileHelp').textContent=popup?'Abre el panel amplio para seleccionar y actualizar un archivo.':!pickerSupported?'Este navegador no permite vincular archivos. Puedes descargar una copia de Excel.':'Selecciona un Excel exportado por esta extensión. Solo se agregan postulaciones nuevas: las filas existentes, sus notas y otras hojas no se sobrescriben. Cierra Excel antes de actualizar. No se escribe automáticamente al capturar.';
}
async function request(type,values={}){const response=await chrome.runtime.sendMessage({type,...values});if(!response||response.error)throw Error(response?.error||'La extensión no respondió. Cierra y abre el panel; el avance guardado se conserva.');return response.result;}
function message(text,error=false){$('message').textContent=text;$('message').classList.toggle('error',error);}
function draft(){return {...Object.fromEntries(FIELDS.map(k=>[k,$(k==='vacancy'?'recordVacancy':k).value])),url:$('sourceUrl').value,id:active?.id||'',revision:active?.revision||0};}
function edit(row,notice=''){active=row;$('editor').hidden=false;for(const key of FIELDS)$(key==='vacancy'?'recordVacancy':key).value=row[key]||'';$('sourceUrl').value=row.url||'';$('captureNotice').textContent=notice;$('editorTitle').textContent=row.revision?'Revisar candidato guardado':'Agregar datos manualmente';$('save').textContent=row.revision?'Guardar corrección':'Guardar candidato';$('draftState').textContent='Los cambios del formulario se guardan como borrador local.';}
function render(){
  renderFile();
  $('count').textContent=`${records.length} candidato${records.length===1?'':'s'}`;
  $('excel').disabled=$('backup').disabled=!records.length||busy;
  const filter=$('search').value.toLocaleLowerCase('es');
  const visible=records.filter(row=>(row.name+' '+row.vacancy).toLocaleLowerCase('es').includes(filter));
  $('empty').hidden=visible.length>0;$('empty').textContent=records.length?'No hay coincidencias con ese filtro.':'Aún no agregas candidatos. Tu avance aparecerá aquí.';
  $('records').replaceChildren(...visible.map(row=>{
    const li=document.createElement('li'),info=document.createElement('div'),name=document.createElement('strong'),vacancy=document.createElement('span'),button=document.createElement('button');
    info.className='record-text';name.textContent=row.name;vacancy.textContent=row.vacancy;info.append(name,vacancy);button.textContent='Revisar';button.disabled=busy;
    button.addEventListener('click',()=>run(async()=>{edit(row);await request('draft',{row});$('editor').scrollIntoView({block:'start',behavior:'smooth'});}));
    li.append(info,button);return li;
  }));
}
async function refresh(){const data=await request('list');records=data.records;render();return data;}
async function run(operation){if(busy)return;busy=true;for(const b of document.querySelectorAll('button'))b.disabled=true;try{await operation();}catch(error){if(error.name==='AbortError')message('Operación cancelada. El archivo y el avance no se modificaron.');else message(error.name==='NotAllowedError'?'No se autorizó el acceso al archivo. El avance local se conserva.':error.message,true);}finally{busy=false;for(const b of document.querySelectorAll('button'))b.disabled=false;$('restore').disabled=!$('backupFile').files.length;render();}}
function download(bytes,type,name){const url=URL.createObjectURL(new Blob([bytes],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
const stamp=()=>new Date().toISOString().replace(/[:.]/g,'-');
$('vacancy').addEventListener('input',()=>request('settings',{vacancy:$('vacancy').value}).catch(e=>message(e.message,true)));
$('capture').addEventListener('click',()=>run(async()=>{
  const vacancy=$('vacancy').value.trim();$('vacancy').setAttribute('aria-invalid',String(!vacancy));if(!vacancy){$('vacancy').focus();throw Error('Escribe primero el nombre de la vacante.');}
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!profileIdentity(tab?.url))throw Error('Abre el perfil individual de un candidato en Indeed. La extensión no navega por ti.');
  let results;
  try{results=await chrome.scripting.executeScript({target:{tabId:tab.id},func:captureOpenCandidate});}catch{throw Error('No se pudo leer un perfil visible. Si Indeed pide una verificación, complétala manualmente; no se reintenta. El avance se conserva.');}
  if(results?.[0]?.result?.error)throw Error(results[0].result.error);
  if(results?.length!==1||results[0].error||!results[0].result)throw Error('No se agregó el candidato. La página no mostró un perfil único o solicitó una verificación.');
  const captured=results[0].result;
  if(profileIdentity(captured.url)?.url.split('#')[0]!==profileIdentity(tab.url)?.url.split('#')[0])throw Error('El perfil cambió mientras se leía. No se agregó nada; vuelve a abrir la extensión sobre el perfil correcto.');
  const result=await request('capture',{row:{...captured,...profileIdentity(tab.url,vacancy),vacancy}});
  edit(result.row,captured.notice);await refresh();
  await request('draft',{row:result.row});
  message(result.enriched?.length?`${result.row.name}: se completaron campos vacíos, sin duplicar ni reemplazar tus correcciones.`:result.duplicate?'Este candidato ya estaba guardado para esta postulación. No se duplicó ni se sobrescribió.':`${result.row.name}: agregado y guardado localmente.`);
}));
$('manual').addEventListener('click',()=>run(async()=>{edit({vacancy:$('vacancy').value});await request('draft',{row:draft()});$('name').focus();}));
$('openPanel').addEventListener('click',()=>run(async()=>{await chrome.runtime.openOptionsPage();}));
for(const input of $('candidateForm').querySelectorAll('input,textarea'))input.addEventListener('input',()=>{
  input.removeAttribute('aria-invalid');
  request('draft',{row:draft()}).then(()=>{$('draftState').textContent='Borrador guardado en este Chrome.';},e=>{$('draftState').textContent='No se pudo guardar el borrador.';message(e.message,true);});
});
$('candidateForm').addEventListener('submit',event=>{event.preventDefault();run(async()=>{
  let valid=true;for(const id of ['name','recordVacancy','sourceUrl']){const field=$(id),ok=!!field.value.trim();field.setAttribute('aria-invalid',String(!ok));if(!ok)valid=false;}
  if(!valid)throw Error('Completa los campos marcados en rojo.');
  const row=draft(),identity=profileIdentity(row.url,row.vacancy);
  if(!identity){$('sourceUrl').setAttribute('aria-invalid','true');throw Error('Pega el enlace del perfil individual de Indeed, no el de la lista ni el de inicio de sesión.');}
  if(active?.revision&&identity.id!==active.id)throw Error('No cambies el enlace de un registro guardado. Usa Completar datos manualmente para otra postulación.');
  const result=await request(active?.revision?'edit':'add',{row:{...row,...identity}});
  edit(result.row);await request('draft',{row:result.row});await refresh();message(result.duplicate?'La postulación ya estaba guardada. Se conservaron sus datos; puedes corregirlos aquí.':'Cambios guardados localmente.');
});});
$('closeEditor').addEventListener('click',()=>run(async()=>{await request('draft',{row:draft()});$('editor').hidden=true;message('Formulario cerrado. El borrador se conserva para la próxima apertura.');}));
$('search').addEventListener('input',render);
$('excel').addEventListener('click',()=>run(async()=>{await refresh();download(exportXlsx(records),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',`Candidatos-Manual-${stamp()}.xlsx`);message('Excel generado con todos los candidatos guardados. El avance local no se borra.');}));
$('selectExcel').addEventListener('click',()=>run(async()=>{
  const [handle]=await window.showOpenFilePicker({types:[excelType],multiple:false,excludeAcceptAllOption:true});
  const file=await handle.getFile();if(file.size>20*1024*1024)throw Error('Selecciona un Excel de hasta 20 MB. No se modificó ningún archivo.');
  await appendCandidates(new Uint8Array(await file.arrayBuffer()),[]);
  excelHandle=handle;
  try{await fileLink('set',handle);message(`Excel vinculado: ${handle.name}. Pulsa Actualizar este Excel para agregar las postulaciones que falten.`);}catch{message(`Excel vinculado solo durante esta apertura: ${handle.name}. No se pudo recordar su ubicación.`,true);}
  renderFile();
}));
$('createExcel').addEventListener('click',()=>run(async()=>{
  if(!records.length)throw Error('Agrega primero un candidato.');
  const handle=await window.showSaveFilePicker({suggestedName:'Candidatos-BPower.xlsx',types:[excelType],excludeAcceptAllOption:true});
  const file=await handle.getFile();
  if(file.size)throw Error('Ese archivo ya contiene datos. No se sobrescribió. Usa Seleccionar Excel existente para conservarlos.');
  await refresh();
  const result=await updateExcelHandle(handle,records,{merge:async(before,rows)=>{
    if(before.length)throw Error('El archivo dejó de estar vacío. No se sobrescribió.');
    return {bytes:exportXlsx(rows),added:rows.length,kept:0};
  }});
  excelHandle=handle;
  try{await fileLink('set',handle);}catch{message('El Excel se guardó, pero no se pudo recordar su ubicación. Vuelve a seleccionarlo en la próxima apertura.',true);return;}
  message(`Excel creado y vinculado: ${handle.name}. ${result.added} postulaciones guardadas.`);
}));
$('updateExcel').addEventListener('click',()=>run(async()=>{
  const handle=excelHandle;if(!handle)throw Error('Selecciona primero un Excel.');
  // Request access in the user's click, before refreshing/processing the data.
  if(await handle.requestPermission({mode:'readwrite'})!=='granted')throw new DOMException('Permiso denegado','NotAllowedError');
  const update=async lock=>{
    if(!lock)throw Error('Hay otra actualización de Excel en curso. Espera a que termine.');
    await refresh();const result=await updateExcelHandle(handle,records);
    message(result.added?`${handle.name}: ${result.added} postulaciones nuevas agregadas; ${result.kept} existentes conservadas sin cambios.`:`${handle.name}: no hay postulaciones nuevas. El archivo no se modificó.`);
  };
  await navigator.locks.request('bpower-excel-update',{ifAvailable:true},update);
}));
$('backup').addEventListener('click',()=>run(async()=>{await refresh();download(JSON.stringify({format:'bpower-candidatos-manual',version:1,records},null,2),'application/json',`Candidatos-Respaldo-${stamp()}.json`);message('Respaldo generado. Contiene datos personales; guárdalo en una ubicación privada.');}));
$('backupFile').addEventListener('change',()=>{$('restore').disabled=!$('backupFile').files.length;});
$('restore').addEventListener('click',()=>run(async()=>{const file=$('backupFile').files[0];if(!file||file.size>10*1024*1024)throw Error('Selecciona un respaldo JSON de hasta 10 MB.');let backup;try{backup=JSON.parse(await file.text());}catch{throw Error('El archivo no contiene un respaldo JSON válido.');}if(!confirm('¿Agregar los registros de este respaldo? No se sobrescribirán los existentes.'))return;const result=await request('import',{backup});await refresh();message(`${result.added} agregados; ${result.kept} existentes conservados.`);}));
try{const data=await refresh();$('vacancy').value=data.settings.vacancy||'';if(data.draft)edit(data.draft);message('Listo. Abre un perfil en Indeed y agrégalo cuando quieras. Tu avance está guardado en este Chrome.');}catch(error){message(error.message,true);}
if(!popup&&pickerSupported){try{excelHandle=await fileLink('get')||null;renderFile();}catch{message('No se pudo recuperar el Excel vinculado. Puedes seleccionarlo nuevamente; los candidatos siguen guardados.',true);}}
window.addEventListener('focus',()=>{if(!busy)refresh().catch(e=>message(e.message,true));});
