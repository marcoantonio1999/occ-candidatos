// Synthetic development harness only. Not included in the extension ZIP.
const local={
  async get(key){const values=JSON.parse(localStorage.getItem('extension-synthetic')||'{}');return key===null?values:{[key]:values[key]};},
  async set(input){const values=JSON.parse(localStorage.getItem('extension-synthetic')||'{}');localStorage.setItem('extension-synthetic',JSON.stringify({...values,...input}));},
  async setAccessLevel(){}
};
globalThis.chrome={
  storage:{local},runtime:{id:'synthetic-extension',getURL:p=>'chrome-extension://synthetic-extension/'+p,onMessage:{addListener(){}},openOptionsPage:async()=>{}},
  tabs:{query:async()=>[{id:123,url:'https://employers.indeed.com/candidates/view?id=bbbbbbbbbbbb&legacyJobId=aaaaaaaaaaaa'}]},
  scripting:{executeScript:async()=>[{result:{id:'indeed:aaaaaaaaaaaa:bbbbbbbbbbbb',url:'https://employers.indeed.com/candidates/view?id=bbbbbbbbbbbb&legacyJobId=aaaaaaaaaaaa',name:'Persona de prueba',phone:'05512345678',notice:'Perfil sintético para validar la interfaz. No son datos reales.'}}]}
};
const {handle}=await import('../extension/worker.mjs');
let queue=Promise.resolve();
chrome.runtime.sendMessage=message=>{
  const task=queue.then(()=>handle(message));queue=task.catch(()=>{});
  return task.then(result=>({result}),error=>({error:error.message}));
};
await import('../extension/panel.mjs');
