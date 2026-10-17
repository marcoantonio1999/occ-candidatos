import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';
import {profileIdentity,saveRecord,validateBackup} from '../extension/model.mjs';
import {captureOpenCandidate} from '../extension/capture.mjs';
import {exportXlsx} from '../extension/xlsx.mjs';
const url=(job='a'.repeat(12),app='b'.repeat(12))=>`https://employers.indeed.com/candidates/view?id=${app}&legacyJobId=${job}`;
const row=(job,app)=>({...profileIdentity(url(job,app)),name:'Persona de prueba',vacancy:'Vacante de prueba',phone:'05512345678',notes:'=SUM(1,2)'});
function storeMock(initial={}){let values=structuredClone(initial);return {get:async key=>structuredClone(key===null?values:{[key]:values[key]}),set:async input=>{values={...values,...structuredClone(input)};},setAccessLevel:async()=>{}};}
globalThis.chrome={storage:{local:storeMock()},runtime:{id:'test-extension',getURL:p=>`chrome-extension://test-extension/${p}`,onMessage:{addListener:fn=>{globalThis.messageListener=fn;}}}};
const {handle}=await import('../extension/worker.mjs');
test('manifest permissions are minimal and no automatic site scripts',async()=>{
  const m=JSON.parse(await readFile(new URL('../extension/manifest.json',import.meta.url),'utf8'));
  assert.deepEqual(m.permissions,['activeTab','scripting','storage']);assert.equal(m.manifest_version,3);
  assert.equal(m.host_permissions,undefined);assert.equal(m.content_scripts,undefined);assert.equal(m.externally_connectable,undefined);
  assert.match(m.content_security_policy.extension_pages,/connect-src 'none'/);
});
test('identities strip tokens and reject outside, ambiguous and list URLs',()=>{
  assert.equal(profileIdentity(url()+'&token=private#other').url,url());
  for(const value of [url().replace('.com/','.com.evil/'),url().replace('https:','http:'),url().replace('employers.','user@employers.'),url()+'&id='+ 'c'.repeat(12),url().replace('/view','')])assert.equal(profileIdentity(value),null);
});
test('same person in another vacancy remains distinct, repeated capture preserves corrections',()=>{
  const first=saveRecord(null,row()).row;
  assert.equal(saveRecord(first,{...row(),name:'Nombre diferente'}).row.name,first.name);
  assert.equal(saveRecord(first,row()).duplicate,true);
  assert.notEqual(row('c'.repeat(12)).id,row().id);
  const edited=saveRecord(first,{...first,name:'Nombre corregido'},{edit:true}).row;
  assert.equal(edited.revision,2);assert.equal(edited.createdAt,first.createdAt);
  assert.throws(()=>saveRecord(edited,first,{edit:true}),/otra ventana/);
});
test('missing fields and identity mismatches do not become saved records',()=>{
  assert.throws(()=>saveRecord(null,{...row(),name:''}),/Completa/);
  assert.throws(()=>saveRecord(null,{...row(),id:'other'}),/perfil individual/);
  assert.throws(()=>saveRecord(null,{...row(),notes:'a'.repeat(12001)}),/demasiado largo/);
});
test('records and draft persist through a new worker context and backup import is non-destructive',async()=>{
  const store=storeMock();const saved=await handle({type:'add',row:row()},store);
  await handle({type:'draft',row:{...saved.row,notes:'Borrador privado'}},store);
  const data=await handle({type:'list'},store);
  assert.equal(data.records.length,1);assert.equal(data.draft.notes,'Borrador privado');
  const backup={format:'bpower-candidatos-manual',version:1,records:[{...saved.row,name:'No sobrescribir'}]};
  assert.deepEqual(await handle({type:'import',backup},store),{added:0,kept:1});
  assert.equal((await handle({type:'list'},store)).records[0].name,'Persona de prueba');
  const target=storeMock();assert.equal((await handle({type:'import',backup},target)).added,1);
  assert.equal((await handle({type:'list'},target)).records.length,1);
});
test('storage failure is propagated, never falsely reported saved',async()=>{
  const store=storeMock();store.set=async()=>{throw Error('Synthetic storage full');};
  await assert.rejects(handle({type:'add',row:row()},store),/storage full/);
  assert.equal((await handle({type:'list'},store)).records.length,0);
});
test('invalid backups fail before saving',()=>{
  const record=saveRecord(null,row()).row;
  assert.throws(()=>validateBackup({format:'bpower-candidatos-manual',version:1,records:[record,record]}),/repetidas/);
  assert.throws(()=>validateBackup({format:'bpower-candidatos-manual',version:1,records:[{...record,url:'https://evil.invalid'}]}),/perfil individual/);
});
test('content scripts or outside senders cannot save arbitrary data',()=>{
  let result;const allowed=messageListener({type:'list'},{id:chrome.runtime.id,url:'https://employers.indeed.com/'},r=>result=r);
  assert.equal(allowed,false);assert.match(result.error,/Acceso/);
});
function captureFixture({challenge=false,plates=1,hidden=false,phone='05512345678',sections=false,ambiguousSections=false}={}){
  const contact={innerText:phone,getClientRects:()=>[{}],closest:()=>null};
  const header={innerText:'Persona de prueba',getClientRects:()=>[{}],closest:()=>null,querySelectorAll:selector=>selector.startsWith('a[href^="tel:')?[contact]:[]};
  const heading={innerText:'Persona de prueba',getClientRects:()=>[{}],closest:()=>null};
  const paragraph={innerText:'Experiencia sintética en atención',getClientRects:()=>[{}],closest:()=>null,matches:()=>false,querySelector:()=>null,nextElementSibling:null};
  const sectionHeading={innerText:'Experiencia laboral',getClientRects:()=>[{}],closest:()=>null,nextElementSibling:paragraph};
  const main={querySelectorAll:()=>ambiguousSections?[sectionHeading,sectionHeading]:[sectionHeading]};
  const plate={innerText:'Persona de prueba',getClientRects:()=>hidden?[]:[{}],closest:selector=>selector==='header,section'?header:selector==='main,[role="main"]'&&sections?main:null,querySelector:()=>heading,parentElement:header};
  const document={title:'Perfil de candidato',body:{innerText:challenge?'Verificación adicional requerida':'Persona de prueba'},querySelector:()=>null,querySelectorAll:selector=>selector.includes('name-plate')?Array(plates).fill(plate):[]};
  return runInNewContext(`(${captureOpenCandidate.toString()})()`,{URL,location:{href:url()+'&secret=not-exported'},document,getComputedStyle:()=>({visibility:'visible'})});
}
test('capture only reads the one visible profile and strips secrets',()=>{
  const result=captureFixture();assert.equal(result.name,'Persona de prueba');assert.equal(result.phone,'05512345678');assert.equal(result.url,url());assert.equal(result.experience,'');
});
test('challenge, hidden or multiple candidates produce no capture',()=>{
  assert.throws(()=>captureFixture({challenge:true}),/verificación/);
  assert.throws(()=>captureFixture({plates:2}),/perfil único/);
  assert.throws(()=>captureFixture({hidden:true}),/perfil único/);
});
test('visible HTML sections are captured only under an unambiguous heading',()=>{
  assert.equal(captureFixture({sections:true}).experience,'Experiencia sintética en atención');
  assert.equal(captureFixture({sections:true,ambiguousSections:true}).experience,'');
});
test('no navigation, requests, cookie access or automated actions in capture module',async()=>{
  const code=await readFile(new URL('../extension/capture.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(code,/fetch\(|XMLHttpRequest|\.click\(|setInterval|setTimeout|document\.cookie|location\s*=|location\.(?:assign|replace)\(/);
});
test('real XLSX ZIP uses text for phones and formula-like notes and UTC numeric dates',async()=>{
  const data=exportXlsx([saveRecord(null,{...row(),name:'Persona <prueba> & ejemplo'}).row]);
  const text=new TextDecoder().decode(data);
  assert.deepEqual([...data.slice(0,4)],[80,75,3,4]);
  assert.match(text,/05512345678/);assert.match(text,/&lt;prueba&gt; &amp; ejemplo/);assert.match(text,/t="inlineStr"/);assert.doesNotMatch(text,/<f[ >]/);assert.match(text,/=SUM\(1,2\)/);assert.match(text,/ySplit="1"/);
  const output=new URL('../../outputs/indeed-extension-tests/',import.meta.url);await mkdir(output,{recursive:true});await writeFile(new URL('export-synthetic.xlsx',output),data);
});
