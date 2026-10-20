import {exportXlsx,zip} from '../extension/xlsx.mjs';
import {unzip,appendCandidates} from '../extension/excel-file.mjs';
import {profileIdentity,saveRecord} from '../extension/model.mjs';
const assert=(value,message)=>{if(!value)throw Error(message);};
const decode=bytes=>new TextDecoder().decode(bytes);
const encode=text=>new TextEncoder().encode(text);
const fixture=(job='aaaaaaaaaaaa',app='bbbbbbbbbbbb')=>saveRecord(null,{...profileIdentity(`https://employers.indeed.com/candidates/view?id=${app}&legacyJobId=${job}`),name:'Persona de prueba',phone:'000123',vacancy:'Vacante QA',notes:'Nota local'}).row;
const results=[];
async function check(name,fn){try{await fn();results.push({name,pass:true});}catch(error){results.push({name,pass:false,error:error.message});}}
const first=fixture(),next=fixture('cccccccccccc');
await check('Append preserves manual notes, extra columns, formulas, other sheets and binary parts',async()=>{
  const files=await unzip(exportXlsx([first]));
  files['xl/worksheets/sheet1.xml']=encode(decode(files['xl/worksheets/sheet1.xml']).replace('Nota local','Nota corregida en Excel').replace('</row></sheetData>','<c r="N2" t="inlineStr"><is><t>Anotación adicional</t></is></c><c r="O2"><f>1+1</f><v>2</v></c></row></sheetData>'));
  files['xl/worksheets/sheet2.xml']=encode('<otraHoja>Conservar</otraHoja>');files['xl/media/image.png']=new Uint8Array([0,1,255]);
  const bytes=zip(files),result=await appendCandidates(bytes,[{...first,notes:'NO sobrescribir'},next,next]);
  assert(result.added===1&&result.kept===1,'counts');
  const output=await unzip(result.bytes),sheet=decode(output['xl/worksheets/sheet1.xml']);
  assert(sheet.includes('Nota corregida en Excel')&&!sheet.includes('NO sobrescribir'),'manual note overwritten');assert(sheet.includes('Anotación adicional')&&sheet.includes('<f>1+1</f>'),'extra cells changed');
  assert(decode(output['xl/worksheets/sheet2.xml'])===decode(files['xl/worksheets/sheet2.xml']),'other sheet changed');assert(output['xl/media/image.png'].join()===files['xl/media/image.png'].join(),'binary part changed');assert(sheet.includes('A1:O3'),'dimension not extended');
  const twice=await appendCandidates(result.bytes,[first,next]);assert(twice.added===0&&twice.bytes===result.bytes,'second update changed file');
});
await check('Excel shared strings and non-first worksheet relationship resolve correctly',async()=>{
  const files=await unzip(exportXlsx([first]));
  let sheet=decode(files['xl/worksheets/sheet1.xml']);const strings=[];
  sheet=sheet.replace(/<c ([^>]+) t="inlineStr"><is><t xml:space="preserve">(.*?)<\/t><\/is><\/c>/g,(_,attrs,value)=>{const index=strings.push(`<si><t>${value}</t></si>`)-1;return `<c ${attrs} t="s"><v>${index}</v></c>`;});
  files['xl/sharedStrings.xml']=encode(`<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">${strings.join('')}</sst>`);
  files['xl/worksheets/another.xml']=encode(sheet);delete files['xl/worksheets/sheet1.xml'];files['xl/_rels/workbook.xml.rels']=encode(decode(files['xl/_rels/workbook.xml.rels']).replace('worksheets/sheet1.xml','worksheets/another.xml'));
  const result=await appendCandidates(zip(files),[next]);assert(result.added===1,'shared strings import failed');assert(decode((await unzip(result.bytes))['xl/worksheets/another.xml']).includes('r="K3"'),'wrong worksheet modified');
});
await check('Malformed, wrong-format, protected and structured-table workbooks fail without mutation',async()=>{
  for(const transform of [s=>s.replace('Nombre','Otro encabezado'),s=>s.replace('</worksheet>','<sheetProtection sheet="1"/></worksheet>'),s=>s.replace('</worksheet>','<tableParts><tablePart r:id="rId3" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></tableParts></worksheet>'),s=>s.replace('</worksheet>',''),s=>s.replace('https://employers.indeed.com/candidates/view','https://evil.invalid')]){
    const files=await unzip(exportXlsx([first]));files['xl/worksheets/sheet1.xml']=encode(transform(decode(files['xl/worksheets/sheet1.xml'])));const input=zip(files),before=input.join();let failed=false;try{await appendCandidates(input,[next]);}catch{failed=true;}assert(failed,'unsafe workbook accepted');assert(input.join()===before,'input mutated');
  }
});
await check('Candidate in another vacancy remains distinct and formulas in imported fields remain text',async()=>{
  const result=await appendCandidates(exportXlsx([first]),[{...next,name:'=HYPERLINK("invalid")',notes:'<b>& texto'}]);
  const text=decode((await unzip(result.bytes))['xl/worksheets/sheet1.xml']);assert(result.added===1,'job identity ignored');assert(!text.includes('<f>'),'formula injection');assert(text.includes('&lt;b&gt;&amp; texto'),'XML escaping');
});
await check('New Indeed links keep vacancy identity across Excel edits and do not append duplicates',async()=>{
  const source='https://employers.indeed.com/candidates/view?id=77cab3bc62d5';
  const make=vacancy=>saveRecord(null,{...profileIdentity(source,vacancy),name:'Persona QA nueva',vacancy,phone:'5500000000'}).row;
  const original=make('Auxiliar administrativo'),other=make('Entrenador');
  const files=await unzip(exportXlsx([original]));
  files['xl/worksheets/sheet1.xml']=encode(decode(files['xl/worksheets/sheet1.xml']).replace('Auxiliar administrativo','Etiqueta editada en Excel'));
  const result=await appendCandidates(zip(files),[original,other]);
  assert(result.added===1&&result.kept===1,'vacancy names merged or existing row duplicated');
  const sheet=decode((await unzip(result.bytes))['xl/worksheets/sheet1.xml']);
  assert(sheet.includes('Etiqueta editada en Excel'),'manual vacancy label overwritten');
  assert((await appendCandidates(result.bytes,[original,other])).added===0,'second update appended duplicate');
});

globalThis.excelTestResults=results;
document.body.textContent=JSON.stringify(results,null,2);
