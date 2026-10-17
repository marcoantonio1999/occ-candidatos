// Small, dependency-free OOXML writer for a local browser export. All supplied
// strings are inline strings, never Excel formulas or executable hyperlinks.
const enc=new TextEncoder();
export const COLUMNS=[['name','Nombre',30],['phone','Teléfono',21],['email','Correo',32],['vacancy','Vacante',32],['reviewState','Estado en Indeed',24],['experience','Experiencia',50],['education','Educación',42],['skills','Habilidades',38],['languages','Idiomas',24],['notes','Notas',50],['url','Perfil de origen',65],['createdAt','Agregado',23],['updatedAt','Actualizado',23]];
const xml=value=>String(value??'').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/g,'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const crcTable=Array.from({length:256},(_,i)=>{for(let b=0;b<8;b++)i=(i&1)?0xedb88320^(i>>>1):i>>>1;return i>>>0;});
function crc(bytes){let c=0xffffffff;for(const b of bytes)c=crcTable[(c^b)&255]^(c>>>8);return(c^0xffffffff)>>>0;}
function join(parts){const result=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));let pos=0;for(const p of parts){result.set(p,pos);pos+=p.length;}return result;}
function header(size,entries){const bytes=new Uint8Array(size),d=new DataView(bytes.buffer);for(const[offset,value,width]of entries)width===2?d.setUint16(offset,value,true):d.setUint32(offset,value,true);return bytes;}
function zip(files){let offset=0;const local=[],central=[];for(const[name,text]of Object.entries(files)){
  const n=enc.encode(name),b=enc.encode(text),c=crc(b);
  const h=header(30,[[0,0x04034b50,4],[4,20,2],[6,0x800,2],[12,33,2],[14,c,4],[18,b.length,4],[22,b.length,4],[26,n.length,2]]);
  local.push(h,n,b);
  central.push(header(46,[[0,0x02014b50,4],[4,20,2],[6,20,2],[8,0x800,2],[14,33,2],[16,c,4],[20,b.length,4],[24,b.length,4],[28,n.length,2],[42,offset,4]]),n);
  offset+=h.length+n.length+b.length;
}const cd=join(central);return join([...local,cd,header(22,[[0,0x06054b50,4],[8,Object.keys(files).length,2],[10,Object.keys(files).length,2],[12,cd.length,4],[16,offset,4]])]);}
export function exportXlsx(records){
  if(!Array.isArray(records)||!records.length)throw Error('Todavía no hay candidatos guardados.');
  const cell=(value,col,row,style=0)=>`<c r="${String.fromCharCode(65+col)}${row}" s="${style}" t="inlineStr"><is><t xml:space="preserve">${xml(value)}</t></is></c>`;
  let rows=`<row r="1" ht="30" customHeight="1">${COLUMNS.map(([,label],i)=>cell(label,i,1,1)).join('')}</row>`;
  records.forEach((record,index)=>{const row=index+2;rows+=`<row r="${row}">${COLUMNS.map(([key],col)=>{
    if(['createdAt','updatedAt'].includes(key)&&Number.isFinite(Date.parse(record[key])))return `<c r="${String.fromCharCode(65+col)}${row}" s="2"><v>${Date.parse(record[key])/86400000+25569}</v></c>`;
    return cell(record[key],col,row);
  }).join('')}</row>`;});
  const ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
  return zip({
    '[Content_Types].xml':'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
    '_rels/.rels':'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    'xl/workbook.xml':`<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="${ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Candidatos" sheetId="1" r:id="rId1"/></sheets></workbook>`,
    'xl/_rels/workbook.xml.rels':'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
    'xl/styles.xml':`<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="${ns}"><numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy hh:mm"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Arial"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Arial"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF285840"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="49" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`,
    'xl/worksheets/sheet1.xml':`<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="${ns}"><dimension ref="A1:M${records.length+1}"/><sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="22"/><cols>${COLUMNS.map(([, ,width],i)=>`<col min="${i+1}" max="${i+1}" width="${width}" customWidth="1"/>`).join('')}</cols><sheetData>${rows}</sheetData><autoFilter ref="A1:M${records.length+1}"/></worksheet>`
  });
}
