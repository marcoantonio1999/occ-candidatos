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
function captureFixture({challenge=false,plates=1,hidden=false,phone='05512345678',sections=false,ambiguousSections=false,ariaBackground=false,callFor='',callLines='+52 55 0000 0000',callCount=1,href=url()+'&secret=not-exported',raw=false}={}){
  const contact={innerText:phone,getClientRects:()=>[{}],closest:()=>null};
  const header={innerText:'Persona de prueba',getClientRects:()=>[{}],closest:()=>null,querySelectorAll:selector=>selector.startsWith('a[href^="tel:')?[contact]:[]};
  const heading={innerText:'Persona de prueba',getClientRects:()=>[{}],closest:selector=>ariaBackground&&selector==='[aria-hidden="true"]'?{}:null};
  const paragraph={innerText:'Experiencia sintética en atención',getClientRects:()=>[{}],closest:()=>null,matches:()=>false,querySelector:()=>null,nextElementSibling:null};
  const sectionHeading={innerText:'Experiencia laboral',getClientRects:()=>[{}],closest:()=>null,nextElementSibling:paragraph};
  const main={querySelectorAll:()=>ambiguousSections?[sectionHeading,sectionHeading]:[sectionHeading]};
  const plate={innerText:'Persona de prueba',getClientRects:()=>hidden?[]:[{}],closest:selector=>ariaBackground&&selector==='[aria-hidden="true"]'?{}:selector==='header,section'?header:selector==='main,[role="main"]'&&sections?main:null,querySelector:()=>heading,parentElement:header};
  const call={innerText:`Llamar a ${callFor}\n${callLines}`,getClientRects:()=>[{}],closest:()=>null,querySelectorAll:()=>[]};
  const document={title:'Perfil de candidato',body:{innerText:challenge?'Verificación adicional requerida':'Persona de prueba'},querySelector:()=>null,querySelectorAll:selector=>selector.includes('name-plate')?Array(plates).fill(plate):callFor&&selector.includes('call-modal-body')?Array(callCount).fill(call):[]};
  const result=runInNewContext(`(${captureOpenCandidate.toString()})()`,{URL,location:{href},document,getComputedStyle:()=>({visibility:'visible'})});
  if(result.error&&!raw)throw Error(result.error);
  return result;
}

test('new Indeed URL without legacyJobId captures and removes opaque list state',()=>{
  const href='https://employers.indeed.com/candidates/view?id=77cab3bc62d5&l=4FAg&listQuery=PRIVATE-DO-NOT-EXPORT';
  const result=captureFixture({href,ariaBackground:true,callFor:'Persona de prueba',phone:''});
  assert.equal(result.name,'Persona de prueba');assert.equal(result.phone,'+52 55 0000 0000');
  assert.equal(result.url,'https://employers.indeed.com/candidates/view?id=77cab3bc62d5');
  assert(!JSON.stringify(result).includes('PRIVATE-DO-NOT-EXPORT'));
  const identity=profileIdentity(result.url,'Auxiliar administrativo');
  const stored=saveRecord(null,{...result,...identity,vacancy:'Auxiliar administrativo'}).row;
  assert.equal(stored.name,'Persona de prueba');assert.equal(profileIdentity(stored.url).id,stored.id);
  assert.equal(profileIdentity(stored.url,'Vacante renombrada').id,stored.id);
  const backup={format:'bpower-candidatos-manual',version:1,records:[stored]};
  assert.equal(validateBackup(backup)[0].id,stored.id);
});

test('new-link identity distinguishes vacancies and rejects malformed IDs rather than falling back',()=>{
  const source='https://employers.indeed.com/candidates/view?id=77cab3bc62d5';
  assert.equal(profileIdentity(source,' Auxiliar  administrativo ').id,profileIdentity(source,'AUXILIAR ADMINISTRATIVO').id);
  assert.notEqual(profileIdentity(source,'Auxiliar administrativo').id,profileIdentity(source,'Entrenador de futbol').id);
  for(const bad of [source+'&legacyJobId=',source+'&legacyJobId=invalid',source+'&legacyJobId=aaaaaaaaaaaa&legacyJobId=bbbbbbbbbbbb',source+'&id=77cab3bc62d5']){
    assert.equal(profileIdentity(bad),null);assert.match(captureFixture({href:bad,raw:true}).error,/Abre primero/);
  }
});

test('script returns actionable error without conflating an unrecognized profile with Cloudflare',()=>{
  const missing=captureFixture({plates:0,raw:true});assert.match(missing.error,/perfil único/);assert.equal(missing.name,undefined);
  const challenge=captureFixture({challenge:true,raw:true});assert.match(challenge.error,/verificación/);assert.equal(challenge.name,undefined);
});

test('new links deduplicate per vacancy and block ambiguous cross-format duplicates',async()=>{
  const source='https://employers.indeed.com/candidates/view?id=bbbbbbbbbbbb';
  const make=vacancy=>({...profileIdentity(source,vacancy),name:'Persona de prueba',vacancy});
  const store=storeMock();await handle({type:'capture',row:make('Auxiliar')},store);
  assert.equal((await handle({type:'capture',row:make('Auxiliar')},store)).duplicate,true);
  await handle({type:'capture',row:make('Entrenador')},store);
  assert.equal((await handle({type:'list'},store)).records.length,2);
  await assert.rejects(handle({type:'capture',row:{...row(),vacancy:'Auxiliar'}},store),/otro formato/);
  assert.equal((await handle({type:'list'},store)).records.length,2);
});

test('worker accepts both actual popup and full-panel messages after updating from v1.0.0',async()=>{
  for(const path of ['panel.html','panel.html?popup=1']){
    await new Promise(resolve=>{const keep=messageListener({type:'list'},{id:chrome.runtime.id,url:chrome.runtime.getURL(path)},response=>{assert(response.result);resolve();});assert.equal(keep,true);});
  }
});
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
test('Indeed call dialog can bind the one painted name while background is aria-hidden',()=>{
  const result=captureFixture({ariaBackground:true,callFor:'Persona de prueba',phone:''});
  assert.equal(result.name,'Persona de prueba');assert.equal(result.phone,'+52 55 0000 0000');
  assert.throws(()=>captureFixture({ariaBackground:true,callFor:'Otra persona'}),/perfil único/);
  assert.throws(()=>captureFixture({ariaBackground:true,callFor:'Persona de prueba',callCount:2}),/perfil único/);
  assert.throws(()=>captureFixture({ariaBackground:true}),/perfil único/);
});
test('phone formatting duplicates collapse but distinct numbers remain ambiguous',()=>{
  assert.equal(captureFixture({callFor:'Persona de prueba',phone:'',callLines:'+52 55 0000 0000\n+525500000000'}).phone,'+52 55 0000 0000');
  assert.equal(captureFixture({callFor:'Persona de prueba',phone:'',callLines:'+52 55 0000 0000\n+52 55 1111 1111'}).phone,'');
});
test('recapture completes only empty fields without replacing corrections or duplicating',async()=>{
  const store=storeMock();const first=await handle({type:'add',row:{...row(),phone:'',email:'manual@example.invalid'}},store);
  const captured=await handle({type:'capture',row:{...row(),name:'Nombre nuevo',phone:'0001234567',email:'new@example.invalid',experience:'Experiencia visible'}},store);
  assert.deepEqual(captured.enriched,['phone','experience']);assert.equal(captured.row.name,first.row.name);assert.equal(captured.row.email,'manual@example.invalid');assert.equal(captured.row.phone,'0001234567');assert.equal(captured.row.createdAt,first.row.createdAt);assert.equal(captured.row.revision,2);
  const repeated=await handle({type:'capture',row:{...row(),phone:'9999999999'}},store);assert.equal(repeated.row.phone,'0001234567');assert.equal(repeated.row.revision,2);assert.equal((await handle({type:'list'},store)).records.length,1);
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
