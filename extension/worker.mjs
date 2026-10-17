import {saveRecord,validateBackup,cleanFields} from './model.mjs';
const prefix='candidate:';
let queue=Promise.resolve();
const ready=chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
export async function handle(message, store=chrome.storage.local) {
  if (!message || typeof message!=='object') throw Error('Solicitud no válida.');
  if (message.type==='list') {
    const data=await store.get(null);
    return {records:Object.entries(data).filter(([k])=>k.startsWith(prefix)).map(([,v])=>v).sort((a,b)=>b.createdAt.localeCompare(a.createdAt)),settings:data.settings || {},draft:data.draft || null};
  }
  if (message.type==='settings') {
    const vacancy=cleanFields({vacancy:message.vacancy}).vacancy;
    await store.set({settings:{vacancy}}); return {ok:true};
  }
  if (message.type==='draft') {
    const draft=message.row===null?null:{...cleanFields(message.row),id:message.row.id || '',url:message.row.url || '',revision:message.row.revision || 0};
    await store.set({draft}); return {ok:true};
  }
  if (message.type==='add' || message.type==='edit') {
    const key=prefix+message.row?.id;
    const current=(await store.get(key))[key];
    const result=saveRecord(current,message.row,{edit:message.type==='edit'});
    if (!result.duplicate) await store.set({[key]:result.row});
    return result;
  }
  if (message.type==='import') {
    const rows=validateBackup(message.backup), saved=await store.get(null), added={};
    for (const row of rows) if (!saved[prefix+row.id]) added[prefix+row.id]=row;
    // One atomic storage operation, and never overwrite a saved record on import.
    if (Object.keys(added).length) await store.set(added);
    return {added:Object.keys(added).length,kept:rows.length-Object.keys(added).length};
  }
  throw Error('Acción no disponible.');
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if (sender.id!==chrome.runtime.id || sender.url!==chrome.runtime.getURL('panel.html')) {reply({error:'Acceso no permitido.'});return false;}
  const task=queue.then(()=>ready).then(()=>handle(message));
  queue=task.catch(()=>{});
  task.then(result=>reply({result}),error=>reply({error:/^(Completa |Abre |Un campo |El campo |Registro |Este registro |Respaldo |El respaldo |Acción |Solicitud )/.test(error.message)?error.message:'No se pudo guardar o recuperar el avance. Puede faltar espacio local. Exporta un respaldo antes de quitar la extensión.'}));
  // Validation errors stay useful, without leaking Chrome internals or page contents.
  task.catch(()=>{});
  return true;
});
