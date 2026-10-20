// File handles are structured-cloned in extension-private IndexedDB, never
// placed in chrome.storage, backups, source control or a server.
export async function fileLink(action,value){
  const db=await new Promise((resolve,reject)=>{const request=indexedDB.open('bpower-excel-link',1);request.onupgradeneeded=()=>request.result.createObjectStore('handles');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
  try{return await new Promise((resolve,reject)=>{const tx=db.transaction('handles',action==='get'?'readonly':'readwrite'),store=tx.objectStore('handles');const request=action==='get'?store.get('excel'):store.put(value,'excel');let result;request.onsuccess=()=>{result=request.result;};tx.oncomplete=()=>resolve(result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('No se pudo recordar el archivo.'));});}finally{db.close();}
}
