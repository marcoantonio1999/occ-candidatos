// Own synthetic pages only: Indeed requests are intercepted, never transmitted.
// Chrome extension APIs in the UI harness are mocked; not an installed/live-site test.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,mkdir} from 'node:fs/promises';
import {captureOpenCandidate} from '../extension/capture.mjs';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,channel:'chrome'});
const out='C:/Users/daniel/Documents/marco/mexprod/outputs/indeed-extension-v1.2.0';
await mkdir(out,{recursive:true});
const href='https://employers.indeed.com/candidates/view?id=bbbbbbbbbbbb&l=4FAg&listQuery=PRIVATE-SYNTHETIC';
try{
 const profile=await browser.newPage();
 let unexpected=0;
 await profile.route('**/*',route=>{
  if(route.request().url()!==href){unexpected++;return route.abort();}
  return route.fulfill({contentType:'text/html',body:'<!doctype html><title>Perfil QA sintético</title><main aria-hidden="true"><header><div data-testid="name-plate-name-item"><h2>Persona QA Sintetica</h2></div><p>Auxiliar administrativo</p></header></main><div role="tooltip" data-testid="call-modal-body"><h3>Llamar a Persona QA Sintetica</h3><p>+52 55 0000 0000</p></div>'});
 });
 await profile.goto(href);const capture=await profile.evaluate(captureOpenCandidate);
 assert.equal(capture.name,'Persona QA Sintetica');assert.equal(capture.phone,'+52 55 0000 0000');
 assert(!capture.url.includes('PRIVATE-SYNTHETIC'));assert(!capture.error);assert.equal(unexpected,0);
 await profile.setContent('<title>Verificación adicional requerida</title><h1>Verificación adicional requerida</h1>');
 assert.match((await profile.evaluate(captureOpenCandidate)).error,/verificación/);
 await profile.close();
 const excel=await browser.newPage();await excel.goto('http://127.0.0.1:8947/extension-tests/excel-browser.html');
 await excel.waitForFunction(()=>Array.isArray(globalThis.excelTestResults));
 const checks=await excel.evaluate(()=>globalThis.excelTestResults);assert.equal(checks.length,5);assert(checks.every(r=>r.pass),JSON.stringify(checks));
 console.log(JSON.stringify({browserExcelChecks:checks,externalRequests:0}));await excel.close();
 for(const width of [320,390,1440]){
  const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(({capture,href})=>{globalThis.__qaCandidate=capture;globalThis.__qaTabUrl=href;},{capture,href});
  await page.goto('http://127.0.0.1:8947/extension-tests/panel-preview.html');
  await page.locator('#vacancy').fill('Auxiliar administrativo');
  await page.getByRole('button',{name:'Agregar este candidato',exact:true}).click();
  await page.locator('#message').filter({hasText:'agregado y guardado localmente'}).waitFor();
  assert.equal(await page.locator('#count').innerText(),'1 candidato');
  assert.equal(await page.getByLabel('Teléfono',{exact:true}).inputValue(),'+52 55 0000 0000');
  assert((await page.locator('#sourceUrl').inputValue()).includes('#bpower-vacancy=auxiliar%20administrativo'));
  await page.getByRole('button',{name:'Agregar este candidato',exact:true}).click();
  await page.locator('#message').filter({hasText:'ya estaba guardado'}).waitFor();assert.equal(await page.locator('#count').innerText(),'1 candidato');
  await page.getByLabel('Teléfono',{exact:true}).fill('5500000099');
  await page.getByRole('button',{name:'Guardar corrección',exact:true}).click();
  await page.locator('#message').filter({hasText:'Cambios guardados localmente'}).waitFor();
  await page.reload();await page.getByRole('button',{name:'Agregar este candidato',exact:true}).click();
  await page.locator('#message').filter({hasText:'ya estaba guardado'}).waitFor();
  assert.equal(await page.getByLabel('Teléfono',{exact:true}).inputValue(),'5500000099');
  assert.equal(await page.locator('#count').innerText(),'1 candidato');
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Descargar una copia de Excel',exact:true}).click();
  const file=await download;const saved=`${out}/candidatos-sinteticos-${width}.xlsx`;await file.saveAs(saved);
  const bytes=await readFile(saved);assert.equal(bytes.subarray(0,2).toString(),'PK');assert(bytes.includes(Buffer.from('5500000099')));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert((await page.locator('.sub').innerText()).includes('v1.2.0'));
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:`${out}/panel-${width}.png`});
  assert.deepEqual(errors,[]);console.log(JSON.stringify({width,newLinkCapture:true,phone:true,duplicatePreserved:true,correctionPreserved:true,persistence:true,xlsx:true,overflow:false}));
  await context.close();
 }
}finally{await browser.close();}
