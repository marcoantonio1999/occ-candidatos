import {test} from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {deflateRawSync} from 'node:zlib';
import {zip,crc} from '../extension/xlsx.mjs';
import {unzip,updateExcelHandle} from '../extension/excel-file.mjs';
globalThis.crypto??=webcrypto;
test('ZIP parser round-trips binary parts and rejects corruption, duplicate paths and oversized input',async()=>{
  const bytes=zip({'xl/workbook.xml':'<book/>','media/image.png':new Uint8Array([0,255,1])});
  assert.deepEqual((await unzip(bytes))['media/image.png'],new Uint8Array([0,255,1]));
  const bad=bytes.slice();bad[50]^=1;await assert.rejects(unzip(bad));
  await assert.rejects(unzip(new Uint8Array(21*1024*1024)));
  await assert.rejects(unzip(zip({'../escape':'invalid'})));
});
test('ZIP parser accepts normal deflate compressed entries with CRC checking',async()=>{
  const name=new TextEncoder().encode('test.xml'),data=new TextEncoder().encode('<root>compressed data</root>'),packed=deflateRawSync(data);
  const local=new Uint8Array(30+name.length+packed.length),central=new Uint8Array(46+name.length),end=new Uint8Array(22);
  const l=new DataView(local.buffer),c=new DataView(central.buffer),e=new DataView(end.buffer);
  l.setUint32(0,0x04034b50,true);l.setUint16(8,8,true);l.setUint32(14,crc(data),true);l.setUint32(18,packed.length,true);l.setUint32(22,data.length,true);l.setUint16(26,name.length,true);local.set(name,30);local.set(packed,30+name.length);
  c.setUint32(0,0x02014b50,true);c.setUint16(10,8,true);c.setUint32(16,crc(data),true);c.setUint32(20,packed.length,true);c.setUint32(24,data.length,true);c.setUint16(28,name.length,true);central.set(name,46);
  e.setUint32(0,0x06054b50,true);e.setUint16(8,1,true);e.setUint16(10,1,true);e.setUint32(12,central.length,true);e.setUint32(16,local.length,true);
  const all=new Uint8Array(local.length+central.length+end.length);all.set(local);all.set(central,local.length);all.set(end,local.length+central.length);
  assert.deepEqual((await unzip(all))['test.xml'],data);
});
function fakeHandle(){let disk=new Uint8Array([1,2,3]),writes=0,aborts=0;return {get disk(){return disk;},get writes(){return writes;},get aborts(){return aborts;},getFile:async()=>new Blob([disk]),createWritable:async()=>{let staged;return {write:async bytes=>{staged=bytes;writes++;},close:async()=>{disk=staged;},abort:async()=>{aborts++;}};}};}
test('no-new-records and invalid workbook do not open a writable file',async()=>{
  const handle=fakeHandle();handle.createWritable=()=>{throw Error('Must not write');};
  const result=await updateExcelHandle(handle,[],{merge:async bytes=>({bytes,added:0})});assert.equal(result.added,0);
  await assert.rejects(updateExcelHandle(handle,[]));assert.deepEqual(handle.disk,new Uint8Array([1,2,3]));
});
test('successful file update commits only after validation, failed write aborts',async()=>{
  const handle=fakeHandle();await updateExcelHandle(handle,[],{merge:async()=>({bytes:new Uint8Array([4,5]),added:1})});assert.deepEqual(handle.disk,new Uint8Array([4,5]));
  const broken=fakeHandle();broken.createWritable=async()=>({write:async()=>{throw Error('disk full');},close:async()=>{throw Error('must not close');},abort:async()=>{broken.aborted=true;}});
  await assert.rejects(updateExcelHandle(broken,[],{merge:async()=>({bytes:new Uint8Array([4]),added:1})}),/disk full/);assert.equal(broken.aborted,true);assert.deepEqual(broken.disk,new Uint8Array([1,2,3]));
});
test('concurrent external change is detected before write and original is not overwritten',async()=>{
  const handle=fakeHandle();let read=0;handle.getFile=async()=>new Blob([++read===1?new Uint8Array([1,2,3]):new Uint8Array([9])]);
  await assert.rejects(updateExcelHandle(handle,[],{merge:async()=>({bytes:new Uint8Array([4]),added:1})}),/cambió/);assert.equal(handle.writes,0);assert.equal(handle.aborts,1);
});
