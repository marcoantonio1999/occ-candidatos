import {COLUMNS,crc,zip} from './xlsx.mjs';
import {profileIdentity} from './model.mjs';

const NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
const REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships';
const decode=new TextDecoder('utf-8',{fatal:true});
const invalid=()=>Error('El Excel no tiene un formato compatible. No se modificó. Usa un Excel exportado por esta extensión, con la hoja Candidatos y sus 13 columnas originales.');
export const MAX_FILE=20*1024*1024;

// Read only bounded, unencrypted, single-disk ZIPs. The browser's inflater has
// a capped output reader so an untrusted workbook cannot allocate without limit.
export async function unzip(bytes){
  if(!(bytes instanceof Uint8Array)||bytes.length>MAX_FILE||bytes.length<22)throw invalid();
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  let end=-1;
  for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--){
    if(view.getUint32(i,true)===0x06054b50&&i+22+view.getUint16(i+20,true)===bytes.length){end=i;break;}
  }
  if(end<0||view.getUint16(end+4,true)||view.getUint16(end+6,true))throw invalid();
  const count=view.getUint16(end+10,true),size=view.getUint32(end+12,true),start=view.getUint32(end+16,true);
  if(!count||count>2000||count!==view.getUint16(end+8,true)||start+size!==end)throw invalid();
  const files=Object.create(null);let at=start,total=0;
  for(let i=0;i<count;i++){
    if(at+46>end||view.getUint32(at,true)!==0x02014b50)throw invalid();
    const flags=view.getUint16(at+8,true),method=view.getUint16(at+10,true),expectedCrc=view.getUint32(at+16,true);
    const packed=view.getUint32(at+20,true),length=view.getUint32(at+24,true),nameLen=view.getUint16(at+28,true),extra=view.getUint16(at+30,true),comment=view.getUint16(at+32,true),offset=view.getUint32(at+42,true);
    if(flags&1||![0,8].includes(method)||length>30*1024*1024||(total+=length)>60*1024*1024||view.getUint16(at+34,true)||at+46+nameLen+extra+comment>end)throw invalid();
    const name=decode.decode(bytes.subarray(at+46,at+46+nameLen));
    if(!name||name.startsWith('/')||name.includes('\\')||name.split('/').includes('..')||Object.hasOwn(files,name)||offset+30>start||view.getUint32(offset,true)!==0x04034b50)throw invalid();
    const localNameLen=view.getUint16(offset+26,true),localExtra=view.getUint16(offset+28,true),from=offset+30+localNameLen+localExtra;
    if(view.getUint16(offset+8,true)!==method||view.getUint16(offset+6,true)&1||decode.decode(bytes.subarray(offset+30,offset+30+localNameLen))!==name||from+packed>start)throw invalid();
    let data=bytes.slice(from,from+packed);
    if(method===8){
      const reader=new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader();
      const parts=[];let used=0;
      try{while(true){const part=await reader.read();if(part.done)break;used+=part.value.length;if(used>length){await reader.cancel();throw invalid();}parts.push(part.value);}}finally{reader.releaseLock();}
      data=new Uint8Array(used);let pos=0;for(const part of parts){data.set(part,pos);pos+=part.length;}
    }
    if(data.length!==length||crc(data)!==expectedCrc)throw invalid();
    files[name]=data;at+=46+nameLen+extra+comment;
  }
  if(at!==end)throw invalid();
  return files;
}
function parse(bytes){
  if(!bytes)throw invalid();
  const text=decode.decode(bytes);
  if(/<!DOCTYPE|<!ENTITY/i.test(text))throw invalid();
  const doc=new DOMParser().parseFromString(text,'application/xml');
  if(doc.getElementsByTagName('parsererror').length)throw invalid();
  return doc;
}
const nodes=(parent,name)=>Array.from(parent.getElementsByTagNameNS(NS,name));
const direct=(parent,name)=>Array.from(parent.children).filter(n=>n.localName===name&&n.namespaceURI===NS);
const textOf=node=>nodes(node,'t').filter(t=>!t.closest('rPh')).map(t=>t.textContent).join('');
function resolvePart(base,target){
  if(!target||/[?#\\]/.test(target)||/^[a-z]+:/i.test(target))throw invalid();
  const parts=target.startsWith('/')?[]:base.split('/').slice(0,-1);
  for(const part of target.split('/')){if(part==='..'){if(!parts.length)throw invalid();parts.pop();}else if(part&&part!=='.')parts.push(part);}
  return parts.join('/');
}
function relation(files,base,id,type){
  const at=base.lastIndexOf('/'),path=base.slice(0,at+1)+'_rels/'+base.slice(at+1)+'.rels';
  const matches=Array.from(parse(files[path]).documentElement.children).filter(n=>n.getAttribute('Id')===id&&n.getAttribute('Type')===REL+'/'+type&&!n.getAttribute('TargetMode'));
  if(matches.length!==1)throw invalid();return resolvePart(base,matches[0].getAttribute('Target'));
}
function cellText(cell,shared){
  if(!cell)return '';
  if(direct(cell,'f').length)throw invalid();
  if(cell.getAttribute('t')==='inlineStr')return textOf(cell);
  const value=direct(cell,'v')[0]?.textContent||'';
  if(cell.getAttribute('t')==='s'){if(!/^\d+$/.test(value)||shared[Number(value)]===undefined)throw invalid();return shared[Number(value)];}
  return value;
}
function serialize(doc){return new XMLSerializer().serializeToString(doc);}

export async function appendCandidates(bytes,records){
  if(!Array.isArray(records)||records.length>5000)throw invalid();
  const files=await unzip(bytes),book=parse(files['xl/workbook.xml']);
  if(book.documentElement.namespaceURI!==NS||Object.keys(files).some(p=>/vbaProject|_xmlsignatures/i.test(p)))throw invalid();
  const sheets=nodes(book,'sheet').filter(s=>s.getAttribute('name')==='Candidatos');
  if(sheets.length!==1)throw invalid();
  const path=relation(files,'xl/workbook.xml',sheets[0].getAttributeNS(REL,'id'),'worksheet');
  const doc=parse(files[path]),root=doc.documentElement;
  if(root.namespaceURI!==NS||nodes(doc,'sheetProtection').length||nodes(doc,'mergeCell').length)throw invalid();
  const data=direct(root,'sheetData');if(data.length!==1)throw invalid();
  const shared=files['xl/sharedStrings.xml']?nodes(parse(files['xl/sharedStrings.xml']),'si').map(textOf):[];
  const rows=direct(data[0],'row');if(!rows.length||rows.length>10001||rows[0].getAttribute('r')!=='1')throw invalid();
  const cells=row=>direct(row,'c');
  const header=new Map(cells(rows[0]).map(c=>[c.getAttribute('r'),c]));
  COLUMNS.forEach(([,label],i)=>{if(cellText(header.get(String.fromCharCode(65+i)+'1'),shared)!==label)throw invalid();});
  const ids=new Set();let last=1,maxCol='M';
  for(const row of rows.slice(1)){
    const index=Number(row.getAttribute('r'));if(!Number.isInteger(index)||index<=last||index>10001)throw invalid();last=index;
    const map=new Map();for(const cell of cells(row)){
      const ref=cell.getAttribute('r'),match=/^([A-Z]{1,3})(\d+)$/.exec(ref||'');
      if(!match||Number(match[2])!==index||map.has(match[1]))throw invalid();map.set(match[1],cell);
      if(match[1].length>maxCol.length||(match[1].length===maxCol.length&&match[1]>maxCol))maxCol=match[1];
    }
    const source=cellText(map.get('K'),shared);
    if(!source){if(cells(row).some(c=>direct(c,'f').length||cellText(c,shared)))throw invalid();continue;}
    const identity=profileIdentity(source,cellText(map.get('D'),shared));if(!identity||ids.has(identity.id))throw invalid();ids.add(identity.id);
  }
  const incoming=new Set(),added=[];
  for(const record of records){const identity=profileIdentity(record.url,record.vacancy);if(!identity||identity.id!==record.id)throw invalid();if(incoming.has(identity.id))continue;incoming.add(identity.id);if(!ids.has(identity.id))added.push(record);}
  if(!added.length)return {bytes,added:0,kept:ids.size};
  if(last+added.length>10001)throw Error('Este Excel supera el máximo de 10,000 filas. No se modificó.');
  // Preserve every old cell and all other ZIP parts. Only append new rows;
  // manual corrections, notes, extra columns, formulas and other sheets stay.
  const template=rows[1]?new Map(cells(rows[1]).map(c=>[c.getAttribute('r').replace(/\d+$/,''),c.getAttribute('s')])):new Map();
  for(const record of added){
    const index=++last,row=doc.createElementNS(NS,'row');row.setAttribute('r',String(index));
    COLUMNS.forEach(([key],i)=>{const col=String.fromCharCode(65+i),cell=doc.createElementNS(NS,'c');cell.setAttribute('r',col+index);
      const style=template.get(col);if(style!==null&&style!==undefined)cell.setAttribute('s',style);
      // Dates use the old column's date style when present. Without a template,
      // use literal ISO text rather than an unformatted serial number.
      if(['createdAt','updatedAt'].includes(key)&&style!==null&&style!==undefined&&Number.isFinite(Date.parse(record[key]))){const v=doc.createElementNS(NS,'v');v.textContent=String(Date.parse(record[key])/86400000+25569);cell.append(v);}
      else{cell.setAttribute('t','inlineStr');const is=doc.createElementNS(NS,'is'),t=doc.createElementNS(NS,'t');t.setAttributeNS('http://www.w3.org/XML/1998/namespace','xml:space','preserve');t.textContent=String(record[key]??'').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/g,'');is.append(t);cell.append(is);}row.append(cell);
    });data[0].append(row);
  }
  const dimension=direct(root,'dimension')[0];if(dimension){const old=dimension.getAttribute('ref')?.match(/:([A-Z]+)\d+$/)?.[1];if(old&&(old.length>maxCol.length||old.length===maxCol.length&&old>maxCol))maxCol=old;dimension.setAttribute('ref',`A1:${maxCol}${last}`);}
  const filter=direct(root,'autoFilter')[0];if(filter){const match=/^A1:([A-Z]+)\d+$/.exec(filter.getAttribute('ref')||'');if(!match)throw invalid();filter.setAttribute('ref',`A1:${match[1]}${last}`);}
  // Excel tables with totals/calculated columns need a different insertion
  // workflow. Refuse them instead of silently breaking table semantics.
  if(nodes(doc,'tablePart').length)throw Error('El Excel contiene una tabla estructurada. Convierte esa tabla en rango antes de vincularlo. No se modificó.');
  files[path]=new TextEncoder().encode(serialize(doc));
  const output=zip(files);if(output.length>MAX_FILE)throw Error('El Excel actualizado superaría 20 MB. No se modificó.');
  return {bytes:output,added:added.length,kept:ids.size};
}

export async function updateExcelHandle(handle,records,{merge=appendCandidates}={}){
  const original=await handle.getFile();if(original.size>MAX_FILE)throw invalid();
  const before=new Uint8Array(await original.arrayBuffer()),result=await merge(before,records);
  if(!result.added)return result;
  const hash=async value=>new Uint8Array(await crypto.subtle.digest('SHA-256',value)).join(',');
  const expected=await hash(before);let stream;
  try{
    stream=await handle.createWritable({mode:'exclusive'});
    const current=await handle.getFile();
    if(current.size>MAX_FILE||await hash(await current.arrayBuffer())!==expected)throw Error('El Excel cambió durante la actualización. No se guardó. Cierra Excel y vuelve a pulsar Actualizar.');
    await stream.write(result.bytes);await stream.close();stream=null;return result;
  }catch(error){if(stream)await stream.abort().catch(()=>{});throw error;}
}
