// App UI with fully intercepted local API. No OCC sessions or real candidates.
import assert from 'node:assert/strict';
import {readFile,mkdir} from 'node:fs/promises';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)('C:/Users/daniel/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const html=(await readFile(new URL('./pantalla.html',import.meta.url),'utf8')).replace('__TOKEN__','fictional');
const output='C:/Users/daniel/Documents/marco/mexprod/tmp/outputs/occ-diagnostics';await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
try{for(const width of [320,390,1440]){
 const page=await browser.newPage({viewport:{width,height:950}}),errors=[];let statusReads=0,downloads=0,resumes=0,skips=0,approveSkip=false;
 page.on('dialog',async d=>approveSkip?d.accept():d.dismiss());
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('http://127.0.0.1:5031/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/')return route.fulfill({contentType:'text/html',body:html});
  assert.equal(route.request().headers()['x-occ-key'],'fictional');
  if(path==='/diagnostico'){downloads++;return route.fulfill({contentType:'text/plain',body:'{"version":"1.2.4","event":"worker_error","code":"profile_incomplete"}\n'});}
  if(path==='/continuar'){assert.equal(route.request().method(),'POST');resumes++;return route.fulfill({json:{ok:true}});}
  if(path==='/omitir-perfil'){assert.equal(route.request().method(),'POST');assert.deepEqual(route.request().postDataJSON(),{token:'fictional-skip-token'});skips++;resumes++;return route.fulfill({json:{ok:true}});}
  assert.equal(path,'/estado');statusReads++;
  return route.fulfill({json:{version:'1.2.4',can_skip:!resumes,skip_token:resumes?null:'fictional-skip-token',omitted:skips,stage:resumes?'waiting_ready':'reading_profile',issue:resumes?'':'profile_incomplete',diagnostic_available:true,message:resumes?'Selecciona tu vacante y confirma.':'Perfil incompleto. Avance guardado.',busy:resumes>0,saved:true,count:0,total:5,reviewed:2,pages:1,complete:false,waiting:resumes>0,pending:[],platform:'occ',mode:'all',vacancy:'Ficticia',action:'new'}});
 });
 await page.goto('http://127.0.0.1:5031/');
 await page.getByText(/Versión activa: 1.2.4/).waitFor();
 assert(await page.getByRole('button',{name:'Continuar descarga',exact:true}).isVisible());
 assert(await page.getByText(/Referencia del problema: profile_incomplete/).isVisible());
 const button=page.getByRole('button',{name:'Descargar diagnóstico',exact:true});assert((await button.boundingBox()).height>=44);
 const event=page.waitForEvent('download');await button.click();const download=await event;
 assert.equal(download.suggestedFilename(),'Diagnostico-Candidatos.txt');assert.equal(downloads,1);
 assert.equal(await page.getByRole('button',{name:'Descargar Excel',exact:true}).isVisible(),false);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:`${output}/diagnostic-${width}.png`,fullPage:true});
 await page.waitForTimeout(1700);assert.equal(statusReads,1,'No idle polling or automatic retry');
 await page.getByRole('button',{name:'Continuar descarga',exact:true}).click();
 await page.getByRole('button',{name:'Ya estoy en la vacante',exact:true}).waitFor();
 assert.equal(resumes,1);assert.equal(await page.getByRole('button',{name:'Continuar descarga',exact:true}).isVisible(),false);
 assert(await page.getByRole('button',{name:'Pausar y guardar',exact:true}).isVisible());
 resumes=0;await page.reload();
 const skip=page.getByRole('button',{name:'Omitir este perfil y continuar',exact:true});await skip.waitFor();
 assert((await skip.boundingBox()).height>=44);
 await skip.click();assert.equal(skips,0,'Cancel does not omit');
 approveSkip=true;await skip.click();await page.getByText(/1 omitidos por ti/).waitFor();
 assert.equal(skips,1);assert.equal(await skip.isVisible(),false);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);console.log(JSON.stringify({width,version:true,zeroCandidatesDownload:true,manualResume:true,manualSkip:true,idlePolling:false,overflow:false}));await page.close();
}}finally{await browser.close();}
