import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const root = fileURLToPath(new URL('../../', import.meta.url));
const out = process.env.CARD_DEALER_BOM_OUTPUT || root;
const support = path.join(out,'verification');
await fs.mkdir(support,{recursive:true});
const manifest = JSON.parse(await fs.readFile(path.join(out, '3d/parts_manifest.json'), 'utf8'));
const fasteners=JSON.parse(await fs.readFile(path.join(out,'3d/fastener_catalog.json'),'utf8'));
assert.equal(fasteners.screw_sku_count,2);
const shortQty=fasteners.screw_skus.find(s=>s.length_mm===8).qty;
const longQty=fasteners.screw_skus.find(s=>s.length_mm===25).qty;
const coupon=manifest.parts.find(p=>p.id==='P30');
const filamentKg=Number((Math.ceil((manifest.solid_PLA_mass_g+coupon.volume_cm3*1.24+25)/50)*0.05).toFixed(2));
const expectedExternal=80.5,expectedShipping=9.5;
const expectedCash=expectedExternal+expectedShipping;
const expectedTotal=Math.round((expectedCash+filamentKg*40)*100)/100;
await fs.mkdir(out, { recursive: true });
const file = path.join(out, '發牌機_BOM_V1.0.0.xlsx');
if (['--refresh-turntable-gap','--inspect-turntable-gap','--refresh-tooth-fix','--inspect-tooth-fix','--refresh-hopper','--inspect-hopper'].some(flag=>process.argv.includes(flag))) {
  const toothFix=['--refresh-tooth-fix','--inspect-tooth-fix'].some(flag=>process.argv.includes(flag));
  const hopper=['--refresh-hopper','--inspect-hopper'].some(flag=>process.argv.includes(flag));
  const mode=hopper?'hopper':toothFix?'tooth-fix':'turntable-gap';
  const original=path.join(root,'發牌機_BOM_V1.0.0.xlsx');
  const originalSha=crypto.createHash('sha256').update(await fs.readFile(original)).digest('hex');
  const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(original));
  const bom=workbook.worksheets.getItem('BOM'),printing=workbook.worksheets.getItem('設計與列印'),screws=workbook.worksheets.getItem('螺絲規格');
  const before=[bom,printing,screws].map(sheet=>({name:sheet.name,values:sheet.getRange('A1:S100').values,formulas:sheet.getRange('A1:S100').formulas}));
  const parts=(hopper?['P08','P12']:toothFix?['P04B']:['P04B','P26']).map(id=>manifest.parts.find(p=>p.id===id));
  assert(parts.every(Boolean)&&manifest.parts.length===40,'Export the current mechanical manifest first');
  assert.deepEqual([shortQty,longQty,fasteners.nut_qty],[61,10,52]);
  if(hopper){
    assert(parts[0].dimensions_mm[0]===106&&parts[0].dimensions_mm[1]===83&&parts[0].dimensions_mm[2]>50,'Export the raised solid-wall P08 first');
    assert(parts[1].dimensions_mm.some(n=>n>45),'Export the taller-wall P12 spacers first');
  }else assert.deepEqual(parts.map(p=>p.dimensions_mm),toothFix?[[74.4,74.4,30.5]]:[[74.4,74.4,30.5],[25,10,7.9]]);
  if(toothFix)assert.equal(parts[0].name,'完整齒形60齒齒輪與空心轉軸','Export the independent full-tooth P04B manifest first');
  const findRow=(sheet,id,start,end)=>{
    const index=sheet.getRange(`A${start}:A${end}`).values.findIndex(r=>r[0]===id);
    assert(index>=0,`${sheet.name}: missing ${id}`);return start+index;
  };
  const rows=parts.map(p=>({p,bom:findRow(bom,p.id,11,100),printing:findRow(printing,p.id,18,70)}));
  const filamentRow=findRow(bom,'F01',11,100),lastBomRow=findRow(bom,'F02',11,100);
  assert.equal(lastBomRow-10,74);
  const originalFilamentKg=Number(bom.getRange(`D${filamentRow}`).values[0][0]);
  assert(Number.isFinite(originalFilamentKg)&&originalFilamentKg>=0,'Keep a valid existing filament allocation');
  const retainedFilamentKg=hopper?Math.max(originalFilamentKg,filamentKg):originalFilamentKg;
  const dir=path.join(root,`.build/bom-${mode}`);await fs.mkdir(dir,{recursive:true});
  for(const item of rows){
    const image=await workbook.render({sheetName:'設計與列印',range:`A${item.printing-1}:K${item.printing+1}`,scale:1.25,format:'png'});
    await fs.writeFile(path.join(dir,`before-${item.p.id}.png`),new Uint8Array(await image.arrayBuffer()));
    console.log((await workbook.inspect({kind:'region',sheetId:'設計與列印',range:`A${item.printing}:K${item.printing}`,maxChars:1700})).ndjson);
  }
  if(process.argv.includes('--inspect-turntable-gap')||process.argv.includes('--inspect-tooth-fix')||process.argv.includes('--inspect-hopper'))process.exit(0);
  const allowed=new Map([['BOM',new Set()],['設計與列印',new Set()],['螺絲規格',new Set()]]);
  const set=(sheet,address,value)=>{sheet.getRange(address).values=[[value]];allowed.get(sheet.name).add(address);};
  const notes={
    P04B:toothFix?'修復承載盤螺母槽誤切齒面，B獨立建模，完整60齒貫穿7.5mm厚度。接合面Z43.5、對P02A名義間隙2mm及原M3×8沿用。本次只需重印P04B，P04A、已延長P26及其他零件沿用。齒輪大平面朝下、空心軸朝上。':'齒寬7.5mm，上接合面Z43.5；齒底與軸承肩臺不變。原P04A及其上機構抬升1.5mm，對P02A名義間隙由0.5增至2mm。原M3×8沿用，配延長P26。齒輪大平面朝下、空心軸朝上。',
    P26:'配P04B抬升1.5mm，遮光薄片向下延長1.5mm；組裝後下緣仍為Z35.6，原感測器光路與槽底0.3mm名義間隙保留。安裝孔及支臂沿用，依STL平面貼床。',
    P08:parts.find(p=>p.id==='P08')?.note,
    P12:parts.find(p=>p.id==='P12')?.note,
  };
  const bomNotes={
    P08:'2.4mm連續底板，兩側板加高至上蓋齊平。內寬61mm、前後開放。保留23×12mm滾輪孔及固定孔；底面盲槽避讓P19。57mm牌配新版P12。',
    P12:'配新版高側板P08，57mm牌左右各一片、內寬約58mm；60mm牌取下。底邊坐底板，中央掛鉤約高出上蓋3mm。另一片轉180°後X移-8mm。',
  };
  if(hopper){
    set(bom,'A3','V1.0.0　封底加高牌倉　P32台階上殼　兩規格螺絲　Type-C');
    set(bom,'A4','2026-11-11更新。P08底板與側板封實，側板上緣與上蓋齊平；P12配合新高度。其他38種STL及五金數量沿用。');
  }else if(!toothFix){
    set(bom,'A3','V1.0.0　轉盤間隙2mm　P32A覆蓋P32B台階上殼　兩規格螺絲　Type-C');
    set(bom,'A4','2026-11-11更新。P04B齒寬增至7.5mm，上部抬升1.5mm，配P26延長遮光片。其他38種STL及五金用量沿用。');
  }
  for(const item of rows){
    const {p}=item,mass=(p.volume_cm3*1.24).toFixed(1);
    set(bom,`B${item.bom}`,p.name);
    set(bom,`C${item.bom}`,`${p.dimensions_mm.join(' × ')} mm；${p.material}；PLA實心換算約${mass}g`);
    set(bom,`P${item.bom}`,(hopper?bomNotes[p.id]:notes[p.id])+' 成本併入耗材。');
    set(printing,`B${item.printing}`,p.name);
    if(!toothFix)for(let i=0;i<3;i++)set(printing,`${'DEF'[i]}${item.printing}`,p.dimensions_mm[i]);
    set(printing,`G${item.printing}`,p.supports);
    set(printing,`I${item.printing}`,notes[p.id]+` PLA實心換算約${mass}g${toothFix?`（模型體積${p.volume_cm3}cm³）`:''}；實際依切片。`);
  }
  set(bom,`C${filamentRow}`,`暫留${retainedFilamentKg.toFixed(2)}kg；全部模型實心換算約${manifest.solid_PLA_mass_g}g（含上罩與選配）。`);
  if(hopper){
    set(bom,`D${filamentRow}`,retainedFilamentKg);
    set(printing,'A5','P08連續底板與兩側板加高至上蓋開口，保留61mm內寬與前後開放；P12卡扣配套修改。上蓋、原孔位及五金沿用。');
  }else if(!toothFix)set(printing,'A5','P04B使上部抬升1.5mm，P04A對P02A名義間隙2mm；P26向下延長1.5mm以沿用原參考感測器。P32A／B台階上殼沿用。');
  workbook.recalculate();
  const changes=[],formulaCaches=[];
  const cacheAllowed=new Set(['E6','H6','K6','M6','B7','E7','H7','K7',`F${filamentRow}`,`I${filamentRow}`,`K${filamentRow}`]);
  function columnName(n){let v='';for(n++;n;n=Math.floor((n-1)/26))v=String.fromCharCode(65+(n-1)%26)+v;return v;}
  for(const snapshot of before){
    const current=workbook.worksheets.getItem(snapshot.name).getRange('A1:S100'),values=current.values,formulas=current.formulas;
    for(let r=0;r<snapshot.values.length;r++)for(let c=0;c<snapshot.values[r].length;c++){
      const address=columnName(c)+(r+1),oldFormula=snapshot.formulas[r]?.[c]??null;
      assert.deepEqual(formulas[r]?.[c]??null,oldFormula,`${snapshot.name}!${address}: formula changed`);
      if(JSON.stringify(values[r]?.[c]??null)===JSON.stringify(snapshot.values[r][c]??null))continue;
      if(oldFormula&&[null,''].includes(snapshot.values[r][c]??null)&&[null,''].includes(values[r]?.[c]??null))continue;
      if(oldFormula){assert(hopper&&snapshot.name==='BOM'&&cacheAllowed.has(address),`${snapshot.name}!${address}: unexpected formula result change`);formulaCaches.push(`${snapshot.name}!${address}`);}
      else{assert(allowed.get(snapshot.name).has(address),`${snapshot.name}!${address}: unexpected input change`);changes.push(`${snapshot.name}!${address}`);}
    }
  }
  const errors=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:1800});
  for(const sheet of [bom,printing,screws])for(const row of sheet.getRange('A1:S100').values)for(const value of row)assert(!(typeof value==='string'&&/^#(REF!|DIV\/0!|VALUE!|NAME\?|N\/A|NUM!|NULL!|SPILL!|CALC!)/.test(value)),`${sheet.name}: ${value}`);
  const previews=hopper
    ?[['BOM','A1:M9','bom-summary-preview.png'],['BOM','A1:M26','bom-preview.png'],['BOM',`A41:M${lastBomRow}`,'bom-lower-preview.png'],['設計與列印','A1:K35','printing-preview.png'],['設計與列印','A27:K33','hopper-printing-preview.png']]
    :toothFix
    ?[['BOM',`A41:M${lastBomRow}`,'bom-lower-preview.png'],['設計與列印','A1:K30','printing-preview.png'],['設計與列印','A23:K25','p05-printing-preview.png'],['BOM',`A${rows[0].bom-1}:M${rows[0].bom+1}`,'tooth-P04B-bom-preview.png']]
    :[['BOM','A1:M9','bom-summary-preview.png'],['BOM','A1:M26','bom-preview.png'],['BOM',`A41:M${lastBomRow}`,'bom-lower-preview.png'],['設計與列印','A1:K30','printing-preview.png']];
  for(const item of rows){previews.push(['設計與列印',`A${item.printing-1}:K${item.printing+1}`,`${hopper?'hopper':'turntable'}-${item.p.id}-printing-preview.png`],['BOM',`O${item.bom}:P${item.bom}`,`${hopper?'hopper':'turntable'}-${item.p.id}-note-preview.png`]);}
  for(const [sheetName,range,name] of previews){const image=await workbook.render({sheetName,range,scale:1.25,format:'png'});await fs.writeFile(path.join(dir,name),new Uint8Array(await image.arrayBuffer()));}
  const candidate=path.join(dir,'candidate.xlsx');await(await SpreadsheetFile.exportXlsx(workbook)).save(candidate);
  const summary={mode,original,candidate,originalSha,changes,formulaCaches,
    solidPLAMassG:manifest.solid_PLA_mass_g,filamentKg:retainedFilamentKg,suggestedFilamentKg:filamentKg,
    shortQty,longQty,nutQty:fasteners.nut_qty,summary:bom.getRange('A6:M7').values,formulaErrors:errors.ndjson,
    printedTypes:manifest.parts.length,bomRows:lastBomRow-10,changedIds:hopper?['F01','P08','P12']:toothFix?(changes.includes(`BOM!C${filamentRow}`)?['P04B','F01']:['P04B']):['F01','P04B','P26'],
    design:hopper?'P08 has a continuous floor with only the pickup-roller window and mounting holes, solid raised sidewalls level with the upper loading opening, 61mm clear width and open ends. P12 spacers are adapted to the taller walls. Other 38 STL types, the upper shell, mounting positions and hardware quantities retained.':toothFix?'P04B independently rebuilt to remove legacy carrier-nut cuts from all 60 teeth across the full 7.5mm thickness. Original 2mm nominal turntable gap, mating dimensions and fasteners retained. Only P04B needs reprinting; extended P26 and all other 39 STL types retained.':'P04B gear thickness 7.5mm raises the original upper assembly by 1.5mm for a 2mm nominal P04A-to-P02A clearance; P26 flag extends downward 1.5mm to retain the original home sensor beam. Other 38 STL types, P32 shell and all hardware quantities unchanged.',
    previews:previews.map(r=>r[2])};
  await fs.writeFile(path.join(dir,'edit-summary.json'),JSON.stringify(summary,null,2));
  const python=process.env.CARD_DEALER_PYTHON||'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe';
  execFileSync(python,[path.join(root,'source/bom/preserve_mechanical_package.py'),path.join(dir,'edit-summary.json'),...(process.argv.includes('--candidate-only')?['--candidate-only']:[])],{stdio:'inherit'});
  console.log(JSON.stringify({changes,filamentKg:retainedFilamentKg,solidPLAMassG:manifest.solid_PLA_mass_g,summary:summary.summary}));
  process.exit(0);
}
if (process.argv.includes('--refresh-shell-step')) {
  // A mechanical appearance revision: import the user's current workbook and
  // edit existing P32A/P32B cells only. No row insertion or new stock is needed.
  const original=path.join(root,'發牌機_BOM_V1.0.0.xlsx');
  const originalSha=crypto.createHash('sha256').update(await fs.readFile(original)).digest('hex');
  const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(original));
  const bom=workbook.worksheets.getItem('BOM'),printing=workbook.worksheets.getItem('設計與列印'),screws=workbook.worksheets.getItem('螺絲規格');
  const before=[bom,printing,screws].map(sheet=>({name:sheet.name,values:sheet.getRange('A1:S100').values,formulas:sheet.getRange('A1:S100').formulas}));
  const a=manifest.parts.find(p=>p.id==='P32A'),b=manifest.parts.find(p=>p.id==='P32B');
  assert(a&&b&&manifest.parts.length===40,'Export the new step-shell manifest first');
  assert(a.dimensions_mm[1]>159&&b.dimensions_mm[0]<172,'Manifest must contain the A-over-B lap revision');
  assert.deepEqual([shortQty,longQty,fasteners.nut_qty],[61,10,52]);
  const findRow=(sheet,id,start,end)=>{
    const index=sheet.getRange(`A${start}:A${end}`).values.findIndex(r=>r[0]===id);
    assert(index>=0,`${sheet.name}: missing ${id}`);return start+index;
  };
  const rows=[a,b].map(p=>({p,bom:findRow(bom,p.id,11,100),printing:findRow(printing,p.id,18,70)}));
  const filamentRow=findRow(bom,'F01',11,100),lastBomRow=findRow(bom,'F02',11,100);
  assert.equal(lastBomRow-10,74);
  const dir=path.join(root,'.build/bom-step');await fs.mkdir(dir,{recursive:true});
  const beforePreview=await workbook.render({sheetName:'設計與列印',range:`A${rows[0].printing-1}:K${rows[1].printing+1}`,scale:1.25,format:'png'});
  await fs.writeFile(path.join(dir,'before.png'),new Uint8Array(await beforePreview.arrayBuffer()));
  const allowed=new Map([['BOM',new Set()],['設計與列印',new Set()],['螺絲規格',new Set()]]);
  const set=(sheet,address,value)=>{sheet.getRange(address).values=[[value]];allowed.get(sheet.name).add(address);};
  const note=p=>p.id==='P32A'
    ?'A外側1.2mm包覆邊向B延伸6.1mm，形成明顯台階；與B名義間隙0.3mm。屋頂大平面貼床。先與B在機外用原四組M3×8及螺母從內側連接，其他零件與孔位不變。'
    :'B屋頂與側牆內退1.5mm，屋頂厚2.2mm，配A包覆邊留0.3mm名義間隙；屋頂大平面貼床。與A仍用原四組M3×8及螺母，局部橋接與配合公差待切片試印。';
  set(bom,'A3','V1.0.0　P32A覆蓋P32B台階上殼　兩規格螺絲　頂部操作　Type-C');
  set(bom,'A4','2026-11-11更新。只修訂P32A／P32B台階搭接，其他38種列印件及五金數量沿用；已有量、單價與採購狀態保留。');
  for(const item of rows){
    const {p}=item,mass=(p.volume_cm3*1.24).toFixed(1);
    set(bom,`B${item.bom}`,p.name);
    set(bom,`C${item.bom}`,`${p.dimensions_mm.join(' × ')} mm；${p.material}；PLA實心換算約${mass}g`);
    set(bom,`P${item.bom}`,note(p)+' 成本併入耗材。');
    set(printing,`B${item.printing}`,p.name);
    for(let i=0;i<3;i++)set(printing,`${'DEF'[i]}${item.printing}`,p.dimensions_mm[i]);
    set(printing,`G${item.printing}`,p.supports);
    set(printing,`I${item.printing}`,note(p)+` PLA實心換算約${mass}g；實際依切片。`);
  }
  set(bom,`C${filamentRow}`,`暫留${filamentKg.toFixed(2)}kg；全部模型實心換算約${manifest.solid_PLA_mass_g}g（含上罩與選配）。`);
  set(bom,`D${filamentRow}`,filamentKg);
  set(printing,'A5','P32A包覆P32B形成台階，名義搭接間隙0.3mm；A／B屋頂大平面貼床。四組內側M3接合沿用，其他38種STL與既有孔位不變。');
  workbook.recalculate();
  const cacheAllowed=new Set(['E6','H6','K6','M6','B7','E7','H7','K7',`F${filamentRow}`,`I${filamentRow}`,`K${filamentRow}`]);
  const changes=[],formulaCaches=[];
  function columnName(n){let v='';for(n++;n;n=Math.floor((n-1)/26))v=String.fromCharCode(65+(n-1)%26)+v;return v;}
  for(const snapshot of before){
    const current=workbook.worksheets.getItem(snapshot.name).getRange('A1:S100'),values=current.values,formulas=current.formulas;
    for(let r=0;r<snapshot.values.length;r++)for(let c=0;c<snapshot.values[r].length;c++){
      const address=columnName(c)+(r+1),oldFormula=snapshot.formulas[r]?.[c]??null;
      assert.deepEqual(formulas[r]?.[c]??null,oldFormula,`${snapshot.name}!${address}: formula changed`);
      if(JSON.stringify(values[r]?.[c]??null)===JSON.stringify(snapshot.values[r][c]??null))continue;
      if(oldFormula&&[null,''].includes(snapshot.values[r][c]??null)&&[null,''].includes(values[r]?.[c]??null))continue;
      if(oldFormula){assert(snapshot.name==='BOM'&&cacheAllowed.has(address),`${snapshot.name}!${address}: unexpected formula result change`);formulaCaches.push(`${snapshot.name}!${address}`);}
      else{assert(allowed.get(snapshot.name).has(address),`${snapshot.name}!${address}: unexpected input change`);changes.push(`${snapshot.name}!${address}`);}
    }
  }
  const errors=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:1800});
  for(const sheet of [bom,printing,screws])for(const row of sheet.getRange('A1:S100').values)for(const v of row)assert(!(typeof v==='string'&&/^#(REF!|DIV\/0!|VALUE!|NAME\?|N\/A|NUM!|NULL!|SPILL!|CALC!)/.test(v)),`${sheet.name}: ${v}`);
  const previews=[['BOM','A1:M9','bom-summary-preview.png'],['BOM','A1:M26','bom-preview.png'],['BOM',`A41:M${lastBomRow}`,'bom-lower-preview.png'],['BOM',`A${rows[0].bom-1}:M${lastBomRow}`,'shell-bom-preview.png'],['BOM',`O${rows[0].bom}:P${rows[1].bom}`,'shell-note-preview.png'],['設計與列印',`A${rows[0].printing-1}:K${rows[1].printing+1}`,'shell-printing-preview.png'],['設計與列印','A1:K30','printing-preview.png'],['螺絲規格','A1:G16','screws-preview.png']];
  for(const [sheetName,range,name] of previews){
    const image=await workbook.render({sheetName,range,scale:1.25,format:'png'});
    await fs.writeFile(path.join(dir,name),new Uint8Array(await image.arrayBuffer()));
  }
  const candidate=path.join(dir,'candidate.xlsx');await(await SpreadsheetFile.exportXlsx(workbook)).save(candidate);
  const summary={mode:'shell-step',original,candidate,originalSha,changes,formulaCaches,
    solidPLAMassG:manifest.solid_PLA_mass_g,filamentKg,shortQty,longQty,nutQty:fasteners.nut_qty,
    summary:bom.getRange('A6:M7').values,formulaErrors:errors.ndjson,printedTypes:manifest.parts.length,bomRows:lastBomRow-10,
    design:'P32A 1.2mm outer lap covers recessed P32B with an intentional step; 0.3mm nominal fit gap; original four internal M3 joints and all other 38 STL types unchanged.',
    previews:previews.map(r=>r[2])};
  await fs.writeFile(path.join(dir,'edit-summary.json'),JSON.stringify(summary,null,2));
  const python=process.env.CARD_DEALER_PYTHON||'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe';
  execFileSync(python,[path.join(root,'source/bom/preserve_mechanical_package.py'),path.join(dir,'edit-summary.json'),...(process.argv.includes('--candidate-only')?['--candidate-only']:[])],{stdio:'inherit'});
  console.log(JSON.stringify({changes,formulaCaches,summary:summary.summary,filamentKg,solidPLAMassG:manifest.solid_PLA_mass_g}));
  process.exit(0);
}
if (process.argv.includes('--render-shell-final') || process.argv.includes('--inspect-final')) {
  const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'發牌機_BOM_V1.0.0.xlsx')));
  const renderFinal=process.argv.includes('--render-shell-final');
  if(renderFinal){
    for(const [sheetName,range,name] of [['BOM','A1:M26','bom-preview'],['BOM','A41:M84','bom-lower-preview'],['設計與列印','A1:K30','printing-preview'],['螺絲規格','A1:G16','screws-preview']]) {
      const image=await workbook.render({sheetName,range,scale:1.25,format:'png'});
      await fs.writeFile(path.join(support,name+'.png'),new Uint8Array(await image.arrayBuffer()));
    }
  }
  const inspection=await workbook.inspect({kind:'workbook,sheet,table',maxChars:4000,tableMaxRows:3,tableMaxCols:7});
  await fs.writeFile(path.join(support,'發牌機_BOM_V1.0.0.xlsx.inspect.ndjson'),inspection.ndjson+'\n');
  console.log(JSON.stringify({finalWorkbookInspected:true,finalWorkbookRendered:renderFinal,files:renderFinal?4:0}));process.exit(0);
}
if (process.argv.includes('--refresh-shell')) {
  const original=path.join(root,'發牌機_BOM_V1.0.0.xlsx');
  const originalSha=crypto.createHash('sha256').update(await fs.readFile(original)).digest('hex');
  const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(original));
  const bom=workbook.worksheets.getItem('BOM'),printing=workbook.worksheets.getItem('設計與列印'),screws=workbook.worksheets.getItem('螺絲規格');
  const dir=path.join(root,'.build/bom-shell');await fs.mkdir(dir,{recursive:true});
  const a=manifest.parts.find(p=>p.id==='P32A'),b=manifest.parts.find(p=>p.id==='P32B');
  assert(a&&b&&manifest.parts.length===40,'Export the new shell manifest first');
  const oldBomRow=11+bom.getRange('A11:A110').values.findIndex(r=>r[0]==='P32');
  const oldPrintRow=18+printing.getRange('A18:A80').values.findIndex(r=>r[0]==='P32');
  assert(oldBomRow>=11&&oldPrintRow>=18,'Original P32 row must exist');
  const bomInsert=oldBomRow+1,printInsert=oldPrintRow+1;
  const oldBomEnd=11+bom.getRange('A11:A110').values.findIndex(r=>r[0]==='F02');
  const oldFilament=11+bom.getRange('A11:A110').values.findIndex(r=>r[0]==='F01');
  const filamentRow=oldFilament+1,newBomEnd=oldBomEnd+1;
  const shiftFormula=(formula,at)=>formula.split(/("(?:[^"]|"")*")/g).map((s,i)=>i%2?s:s.replace(/(?<![A-Za-z0-9_])(\$?[A-Z]{1,3}\$?)(\d+)\b/g,(_,c,n)=>c+(Number(n)>=at?Number(n)+1:n))).join('');
  // The runtime has no range.insert surface. Copy existing rows from bottom
  // to top, then author the new row; the native-preservation helper performs
  // the corresponding structural row insert in the original XLSX package.
  for(let r=oldBomEnd;r>=bomInsert;r--)bom.getRange(`A${r+1}:S${r+1}`).copyFrom(bom.getRange(`A${r}:S${r}`),'all');
  for(let r=60;r>=printInsert;r--)printing.getRange(`A${r+1}:K${r+1}`).copyFrom(printing.getRange(`A${r}:K${r}`),'all');
  bom.getRange(`A${bomInsert}:S${bomInsert}`).copyFrom(bom.getRange(`A${oldBomRow}:S${oldBomRow}`),'all');
  printing.getRange(`A${printInsert}:K${printInsert}`).copyFrom(printing.getRange(`A${oldPrintRow}:K${oldPrintRow}`),'all');
  const originalSummary=bom.getRange('A6:M7').formulas;
  for(let r=0;r<2;r++)for(let c=0;c<13;c++)if(originalSummary[r][c])bom.getRangeByIndexes(5+r,c,1,1).formulas=[[shiftFormula(originalSummary[r][c],bomInsert)]];
  const changes=[];
  function set(sheet,address,value){sheet.getRange(address).values=[[value]];changes.push(`${sheet.name}!${address}`)}
  const shellNote=p=>`${p.id}與${p.id==='P32A'?'P32B':'P32A'}配套，先在機外用四組M3×8與M3螺母從內側連接，再裝原OLED與按鍵。含P33後左右總寬196.4mm、前視中心對齊；其他零件與原安裝孔不移動。依STL屋頂大平面貼床，局部孔槽橋接待切片。`;
  set(bom,'A3','V1.0.0　P32A與P32B上殼居中分件版　兩規格螺絲　頂部操作　Type-C');
  set(bom,'A4','2026-11-11更新。上殼分件，其他38種列印件沿用；已有量、單價與採購狀態按原表保留。');
  const c07=11+bom.getRange('A11:A110').values.findIndex(r=>r[0]==='C07');
  set(bom,`C${c07}`,`M3×8內六角沉頭×${shortQty}、M3×25×${longQty}；M3螺母×${fasteners.nut_qty}。`);
  for(const [p,row] of [[a,oldBomRow],[b,bomInsert]]){
    set(bom,`A${row}`,p.id);set(bom,`B${row}`,p.name);set(bom,`C${row}`,`${p.dimensions_mm.join(' × ')} mm；${p.material}`);set(bom,`D${row}`,p.qty);set(bom,`P${row}`,shellNote(p)+' 成本併入耗材。');
    bom.getRange(`A${row}:S${row}`).format.rowHeight=94;
  }
  // New printed item starts with no assumed stock or purchase history.
  for(const [col,value] of Object.entries({E:0,G:'件',H:null,J:null,L:'自行列印',M:'待列印',O:'',Q:'',R:'',S:null}))set(bom,`${col}${bomInsert}`,value);
  bom.getRange(`F${bomInsert}`).formulas=[[`=MAX(D${bomInsert}-E${bomInsert},0)`]];
  bom.getRange(`I${bomInsert}`).formulas=[[`=IF(OR(L${bomInsert}="自行列印",L${bomInsert}="既有設備"),0,IF(F${bomInsert}=0,0,IF(ISNUMBER(H${bomInsert}),ROUND(F${bomInsert}*H${bomInsert},2),"待填單價")))`]];
  bom.getRange(`K${bomInsert}`).formulas=[[`=IF(OR(L${bomInsert}="自行列印",L${bomInsert}="既有設備"),0,IF(F${bomInsert}=0,0,IF(ISNUMBER(J${bomInsert}),ROUND(F${bomInsert}*J${bomInsert},2),"")))`]];
  set(bom,`D${filamentRow}`,filamentKg);
  set(bom,`C${filamentRow}`,`暫留${filamentKg.toFixed(2)}kg；全部模型實心換算約${manifest.solid_PLA_mass_g}g（含上罩與選配）。`);
  set(printing,'A5','P32A主罩與P32B側罩先在機外連接，四組M3×8及M3螺母由內側固定；含P33後左右總寬196.4mm，正面中心對齊。');
  set(printing,'A6',`${manifest.parts.length}種STL，基本36種47件，全選含選配及試配片52件。列印方向與局部橋接依各件備註，實物公差待試配。`);
  for(const [p,row] of [[a,oldPrintRow],[b,printInsert]]){
    printing.getRange(`A${row}:K${row}`).values=[[p.id,p.name,p.qty,...p.dimensions_mm,p.supports,p.file,shellNote(p),'組裝件',p.material]];
    for(const col of 'ABCDEFGHIJK')changes.push(`${printing.name}!${col}${row}`);
    printing.getRange(`A${row}:K${row}`).format.rowHeight=104;
  }
  for(const [cell,value] of [['B7',shortQty],['C7',Math.ceil((shortQty+2)/10)*10],['B9',fasteners.nut_qty],['C9',Math.ceil((fasteners.nut_qty+2)/10)*10],['A15','P32A／P32B新增四組M3×8與M3螺母，從上殼內側連接；兩片先組合再裝頂部UI與罩入機構。']])set(screws,cell,value);
  workbook.recalculate();
  const errors=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:1800});
  console.log(errors.ndjson);
  for(const [sheetName,range,name] of [['BOM','A1:M9','bom-summary-preview'],['BOM',`A${oldBomRow-1}:M${newBomEnd}`,'shell-bom-preview'],['BOM',`O${oldBomRow}:P${bomInsert}`,'shell-note-preview'],['設計與列印',`A${oldPrintRow-1}:K${printInsert+1}`,'shell-printing-preview'],['螺絲規格','A6:G15','screws-preview']]){
    const image=await workbook.render({sheetName,range,scale:1.25,format:'png'});await fs.writeFile(path.join(dir,name+'.png'),new Uint8Array(await image.arrayBuffer()));
  }
  const candidate=path.join(dir,'candidate.xlsx');await(await SpreadsheetFile.exportXlsx(workbook)).save(candidate);
  const authored=[...new Set(changes)];
  // Include affected formula caches from the artifact calculation, keeping
  // every unrelated native cell and feature in the preservation pass.
  for(const address of ['E6','H6','K6','M6','B7','E7','H7','K7',`F${filamentRow}`,`I${filamentRow}`,`K${filamentRow}`])authored.push(`BOM!${address}`);
  for(const col of 'ABCDEFGHIJKLMNOPQRS')authored.push(`BOM!${col}${bomInsert}`);
  const summary={mode:'shell',original,candidate,originalSha,changes:[...new Set(authored)],
    rowInsertions:{BOM:{at:bomInsert,styleRow:oldBomRow},'設計與列印':{at:printInsert,styleRow:oldPrintRow}},
    rowHeights:{BOM:{[oldBomRow]:94,[bomInsert]:94},'設計與列印':{[oldPrintRow]:104,[printInsert]:104}},
    solidPLAMassG:manifest.solid_PLA_mass_g,filamentKg,shortQty,longQty,nutQty:fasteners.nut_qty,
    summary:bom.getRange('A6:M7').values,formulaErrors:errors.ndjson,printedTypes:manifest.parts.length};
  await fs.writeFile(path.join(dir,'edit-summary.json'),JSON.stringify(summary,null,2));
  const python=process.env.CARD_DEALER_PYTHON||'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe';
  execFileSync(python,[path.join(root,'source/bom/preserve_shell_package.py'),path.join(dir,'edit-summary.json')],{stdio:'inherit'});
  console.log(JSON.stringify({candidate,originalSha,filamentKg,summary:summary.summary}));
  process.exit(0);
}
if (process.argv.includes('--inspect-shell')) {
  const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'發牌機_BOM_V1.0.0.xlsx')));
  console.log(workbook.help('range.insert',{include:'index,examples,notes',maxChars:2500}).ndjson);
  const dir=path.join(root,'.build/bom-shell');await fs.mkdir(dir,{recursive:true});
  for (const [sheetName,range,name] of [['BOM','A75:M83','before-bom'],['設計與列印','A50:K56','before-printing'],['螺絲規格','A6:G14','before-screws']]) {
    const preview=await workbook.render({sheetName,range,scale:1.2,format:'png'});
    await fs.writeFile(path.join(dir,name+'.png'),new Uint8Array(await preview.arrayBuffer()));
  }
  console.log((await workbook.inspect({kind:'region',sheetId:'BOM',range:'A75:M83',maxChars:1100})).ndjson);
  process.exit(0);
}
if (process.argv.includes('--inspect-p05') || process.argv.includes('--refresh-p05')) {
  const inspectOnly = process.argv.includes('--inspect-p05');
  const original = path.join(root, '發牌機_BOM_V1.0.0.xlsx');
  const originalSha = crypto.createHash('sha256').update(await fs.readFile(original)).digest('hex');
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(original));
  const bom = workbook.worksheets.getItem('BOM');
  const printing = workbook.worksheets.getItem('設計與列印');
  const screws = workbook.worksheets.getItem('螺絲規格');
  const before = [bom, printing, screws].map(sheet => ({
    name: sheet.name, values: sheet.getRange('A1:S100').values, formulas: sheet.getRange('A1:S100').formulas,
  }));
  const bomRow = 11 + bom.getRange('A11:A100').values.findIndex(row => row[0] === 'P05A');
  const printRow = 18 + printing.getRange('A18:A70').values.findIndex(row => row[0] === 'P05A');
  const filamentRow = 11 + bom.getRange('A11:A100').values.findIndex(row => row[0] === 'F01');
  assert(bomRow >= 11 && printRow >= 18 && filamentRow >= 11);
  console.log((await workbook.inspect({ kind:'region', sheetId:'設計與列印', range:`A${printRow}:K${printRow}`, maxChars:2200 })).ndjson);
  const previewDir = path.join(root, '.build', 'bom-p05');
  await fs.mkdir(previewDir, { recursive:true });
  const beforePreview = await workbook.render({ sheetName:'設計與列印', range:`A${printRow-1}:K${printRow+1}`, scale:1.35, format:'png' });
  await fs.writeFile(path.join(previewDir,'before.png'),new Uint8Array(await beforePreview.arrayBuffer()));
  if (inspectOnly) process.exit(0);
  const p = manifest.parts.find(part => part.id === 'P05A');
  assert(p);
  const note = '內腔平口Y−10.7配P05B平口Y−10.5，名義側隙0.2mm。保留完整30齒、6mm齒寬與防脫裙邊。先鎖B再裝A，以兩組M3×8與M3螺母固定。既有平面版B可沿用，配合公差待試印。';
  bom.getRange('A3').values = [['V1.0.0　P05A內側平口配合版／P05B平面貼床／M3×8及M3×25／頂部操作　Type-C']];
  bom.getRange(`B${bomRow}`).values = [[p.name]];
  bom.getRange(`C${bomRow}`).values = [[`${p.dimensions_mm.join(' × ')} mm；${p.material}`]];
  bom.getRange(`P${bomRow}`).values = [[note+' 頂部大平面貼床；成本併入耗材。']];
  bom.getRange(`C${filamentRow}`).values = [[`暫留${Number(bom.getRange(`D${filamentRow}`).values[0][0]).toFixed(2)}kg；全部模型實心換算約${manifest.solid_PLA_mass_g}g（含上罩與選配）。`]];
  printing.getRange('A5').values = [['P05A內側平口配合P05B，名義側隙0.2mm。A頂面貼床，B平面側放並建議3–5mm brim，孔槽橋接待切片。']];
  printing.getRange(`B${printRow}`).values = [[p.name]];
  printing.getRange(`D${printRow}:F${printRow}`).values = [p.dimensions_mm];
  printing.getRange(`G${printRow}`).values = [[p.supports]];
  printing.getRange(`I${printRow}`).values = [[note]];
  printing.getRange(`A${printRow}:K${printRow}`).format.rowHeight = 100;
  workbook.recalculate();
  const allowed = new Map([
    ['BOM',new Set(['A3',`B${bomRow}`,`C${bomRow}`,`P${bomRow}`,`C${filamentRow}`])],
    ['設計與列印',new Set(['A5',`B${printRow}`,`D${printRow}`,`E${printRow}`,`F${printRow}`,`G${printRow}`,`I${printRow}`])],
    ['螺絲規格',new Set()],
  ]);
  const changes=[];
  function columnName(n) { let s=''; for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s; return s; }
  for(const snapshot of before) {
    const current=workbook.worksheets.getItem(snapshot.name).getRange('A1:S100');
    const values=current.values, formulas=current.formulas;
    for(let r=0;r<snapshot.values.length;r++)for(let col=0;col<snapshot.values[r].length;col++) {
      const address=columnName(col)+(r+1);
      assert.deepEqual(formulas[r]?.[col]??null,snapshot.formulas[r]?.[col]??null,`${snapshot.name}!${address} formula changed`);
      if (snapshot.formulas[r]?.[col] && [null,''].includes(snapshot.values[r][col]??null) && [null,''].includes(values[r]?.[col]??null)) continue;
      if(JSON.stringify(values[r]?.[col]??null)!==JSON.stringify(snapshot.values[r][col]??null)) {
        assert(allowed.get(snapshot.name).has(address),`${snapshot.name}!${address} unexpected value change ${JSON.stringify(snapshot.values[r][col])} -> ${JSON.stringify(values[r]?.[col])}`);
        changes.push(`${snapshot.name}!${address}`);
      }
    }
  }
  const errors = await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:2000});
  console.log(errors.ndjson);
  for(const [sheetName,range,filename] of [
    ['設計與列印',`A${printRow-1}:K${printRow+1}`,'p05-printing-preview.png'],
    ['BOM',`O${bomRow}:P${bomRow}`,'p05-bom-note-preview.png'],
    ['BOM','A1:M9','bom-summary-preview.png'],
    ['BOM','A1:M26','bom-preview.png'],
    ['BOM','A41:M83','bom-lower-preview.png'],
    ['設計與列印','A1:K30','printing-preview.png'],
  ]) {
    const preview=await workbook.render({sheetName,range,scale:1.35,format:'png'});
    await fs.writeFile(path.join(support,filename),new Uint8Array(await preview.arrayBuffer()));
  }
  const candidate=path.join(previewDir,'candidate.xlsx');
  await (await SpreadsheetFile.exportXlsx(workbook)).save(candidate);
  await fs.writeFile(path.join(previewDir,'edit-summary.json'),JSON.stringify({changes,formulaErrors:errors.ndjson,filamentKg:Number(bom.getRange(`D${filamentRow}`).values[0][0]),solidPLAMassG:manifest.solid_PLA_mass_g,original,candidate},null,2));
  const python = process.env.CARD_DEALER_PYTHON || 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe';
  execFileSync(python,[path.join(root,'source/bom/preserve_package.py'),original,candidate,path.join(previewDir,'edit-summary.json'),originalSha],{stdio:'inherit'});
  console.log(JSON.stringify({candidate,changes,summary:bom.getRange('A6:M7').values}));
  process.exit(0);
}
const wb = Workbook.create();
const sheet = wb.worksheets.add('BOM');
const printSheet = wb.worksheets.add('設計與列印');
const screwSheet = wb.worksheets.add('螺絲規格');

// Goal prices are planning inputs, not verified quotations. Only the four
// user-confirmed assets are marked owned. Initial inventory stays separate
// from purchasing status and actual prices.
const rows = [];
function row(id, name, spec, qty, owned, unit, price, acquisition, status, search, note, product='', official='') {
  rows.push({ id, name, spec, qty, owned, unit, price, acquisition, status, search, note, product, official });
}
row('A01','ESP32-C3 開發板','ESP32-C3 SuperMini，原生USB，4MB Flash。',1,1,'片',null,'採購','已有','','使用者確認已有此板型；USB接電腦前拔除JP-ESP5V，GND共地。Wi-Fi與BLE保持關閉。', '', 'https://documentation.espressif.com/esp32-c3_datasheet_en.html');
row('A02','18650 鋰離子電池','2900mAh。設計前提：單節 3.6/3.7V，充滿 4.2V。',1,1,'顆',null,'採購','已有','','使用者確認已有；型號、保護情況及允許充放電電流待核對。');
row('A03','USB 充電器','5V / 2A，沿用已有充電器。',1,1,'個',null,'採購','已有','','只作充電輸入，充電電流由充電板設定。');
row('A04','拓竹 A1 mini 3D 印表機','列印空間 180 × 180 × 180mm。',1,1,'台',null,'既有設備','已有','','製作設備，非裝入發牌機的零件。', '', 'https://bambulab.cn/zh-cn/a1-mini/tech-specs');
row('B01','旋轉馬達與驅動板','28BYJ-48 5V + ULN2003 X113647/ZC-A0591。',1,0,'組',6,'採購','待購','28BYJ-48 5V ULN2003 套装','選含馬達與七輸入驅動板的整組；42×30mm板與固定座須試配。外加60:30齒輪，2:1減速。', 'https://tao.hooos.com/goods_pW3w974Uxt6Zk53qJkseeaTptm-Gn755MIjNKqprqHo.html','https://www.electrokit.com/upload/product/41014/41014801/28byj48-5v.pdf');
row('B02','取牌減速馬達','N20含金屬減速箱，5V約500rpm；可選6V/500rpm款以5V供電。',1,0,'顆',5,'採購','待購','N20 6V 500转 3mm D轴 金属减速箱 低功率','3mm D軸、出軸約10mm、無編碼器，本體含減速箱按12×10×26mm。6V/500rpm款在5V全速空載粗估420rpm，非實測；負載及PWM會更低。核對尺寸及堵轉電流，選低功率型；升壓仍設5V。');
row('B03','出牌直流馬達','RF-300FA-12350，約24.4mm外徑，約18mm長軸。',1,0,'顆',2,'採購','待購','RF-300FA-12350 5.9V 长轴18mm','使用5V；模型馬達夾座與聯軸器按長軸版規劃，採購前核對軸長。','https://tao.hooos.com/goods_NxoJyO0F5tzwBn3fxZGhRtB-RWRNNzu2zdvGaYwi6.html','https://product.mabuchi-motor.co.jp/detail.html?id=74');
row('B04','雙路直流馬達驅動板','DRV8833 HW-627十二腳黑板，5V供電、3.3V控制。',1,0,'片',3,'採購','待購','DRV8833 双路 直流电机 驱动模块','依指定板型焊接面腳序接線；EEP接本板VCC 5V，IN4接GND。持續電流須配合馬達及散熱。','https://tao.k7dj.com/goods-9zNMqODRIBtODY84Pg6h22GsQt6-qKZqqrSnnmd8yywuo.html','https://www.ti.com/product/DRV8833');
row('B05','OLED 螢幕','0.96吋、128×64、SSD1306、4針 IIC。',1,0,'片',7,'採購','待購','0.96 OLED 12864 SSD1306 4针 IIC','上罩水平固定。參考PCB27.3×27.8、玻璃19.3×26.7，背面元件與接腳須量測；顯示每人張數/玩家/餘牌。','https://item.taobao.com/item.htm?id=40809409804','https://wiki.lckfb.com/zh-hans/coloreasyduino/module/screen/0-96-iic-single-screen.html');
row('B06','按鍵 IO 擴展板','PCF8574T長條9孔IO板，3.3V，I2C地址0x20。',1,0,'片',2,'採購','待購','PCF8574T 8路 IO扩展模块 I2C','指定Waveshare式長條板；P0–P3四按鍵、P4旋轉參考，A0–A2接GND。P35固定座需按實物重新試配。', '', 'https://www.ti.com/product/PCF8574');
row('B07','輕觸按鍵','6×6mm，高度9.5mm，兩腳／四腳常開型。',4,0,'顆',0.25,'採購','待購','轻触开关 6x6x9.5','設定、減、加、開始/暫停各一顆；按鍵帽與板位置可微調。');
row('B08','導電滑環','12路，每路至少2A，外徑≤22mm；參考總長26.5mm。',1,0,'個',20,'採購','待購','12路 2A 帽式 导电滑环 22mm','頂部UI使6路不足。使用5V/GND/3.3V/SDA/SCL/取牌2路/出牌1路/出口計數/旋轉參考共10路，餘2路。法蘭參考Ø44.5、孔圓Ø38，實物需核對；20元為配置目標，非12路SKU報價。','https://tao.k7dj.com/goods-D08verAhDt5Xge3OB2sQQYsjtn-QAnppRSjj98rz9SK4.html','https://www.panlinkslipring.com/sale-40975477-compact-customized-capsule-slip-rings-for-robotics-mechanical.html');
row('B09','槽型光電感測器','ITR9608-F 裸件，13×6.8×6mm、槽寬5mm。',2,0,'顆',1,'採購','待購','ITR9608-F 槽型 光电开关','出口計數及旋轉參考。57mm牌時P24與出口感測器向內移1.5mm；本版已建接腳包絡。','','https://media.digikey.com/pdf/data%20sheets/everlight%20pdfs/itr9608-f.pdf');
row('C01','轉盤軸承','6005ZZ，25×47×12mm。',1,0,'個',2,'採購','待購','6005ZZ 25 47 12 轴承','承載轉盤。模型軸承座47.3mm、空心轉軸24.8mm，先試配。', '', 'https://www.skf.com/group/products/rolling-bearings/ball-bearings/deep-groove-ball-bearings/productid-6005-2Z');
row('C02','出牌滾輪軸承','623ZZ，3×10×4mm。',4,0,'個',0.5,'採購','待購','623ZZ 3 10 4 微型轴承','上、下滾輪各兩顆。模型軸承孔10.3mm。');
row('C03','滾輪鋼軸','直徑3mm，上軸82mm、下軸92mm，各一支。',2,0,'支',1,'採購','待購','3mm 光轴 100mm','可買100mm各裁至82/92mm；下軸較長以連接外側聯軸器。依實購軸及馬達長度核對。');
row('C04','矽膠 O型圈','內徑16mm、線徑2mm。',6,0,'個',0.25,'採購','待購','硅胶 O型圈 16x2','取牌輪2個，上、下出牌輪各2個；輪槽底徑16.8mm，拉伸後接觸外徑估約20.7mm，依實物調夾持量。');
row('C05','橡膠分牌墊','裁約55×4×1mm，嵌入P09前面凹袋。',1,0,'片',0.5,'採購','待購','橡胶片 1mm 分页 摩擦垫','工作面與閘面對齊，底緣間隙起始0.45mm；固定後依實際牌厚調整。');
row('C07','兩規格螺絲及M3螺母',`M3×8內六角沉頭×${shortQty}、M3×25×${longQty}；M3螺母×${fasteners.nut_qty}。`,1,0,'組',6,'採購','待購','DIN7991 M3x8 M3x25 沉头 内六角 全牙 M3螺母','整機只有兩種螺絲；同用2mm內六角。頭徑≤6、頭高≤1.7，長度含頭。取消M2、止付與盤頭。詳見螺絲規格頁及五金數量表。6元為配置目標，包裝最低購量與備品另核。','','https://www.aanddfasteners.co.uk/uploads/media/gbMcC5-media-Din7991Socketcountersunkspecification.pdf');
row('D01','Type-C 充電板','TP4056 HW-387 Type-C無保護版，單節4.2V。',1,0,'片',1.2,'採購','待購','TP4056 Type-C 充电板 无保护 C to C','與獨立保護板搭配。先設0.5A；確認電芯型號後再考慮1A。選支援C-to-C充電的板款。','https://item.taobao.com/item.htm?id=624056967771','https://www.toppwr.com/eproduct/view.php?id=478');
row('D02','單節鋰電池保護板','1S 5A長條35×7.4mm，DW01及三顆8205A。',1,0,'片',1.3,'採購','待購','1S 3.7V 5A 锂电池 保护板','充電板與升壓板都接保護板P端，不旁路保護。額定電流及截止電壓待確認。');
row('D03','5V 升壓模組','TPS61088型，設定輸出5V，常開，目標持續2A。',1,0,'片',7.5,'採購','待購','TPS61088 3.7V 转5V 升压模块','選完整模組。確認低電池電壓及馬達啟動下仍能供電；初次上電先量輸出5V。','https://tao.hooos.com/goods_WZ042NGCot25YXXngGHaa6SQta-oMZ778FAdjp9wK4T4.html','https://www.ti.com/lit/ds/symlink/tps61088.pdf');
row('D04','18650 電池盒','單節帶線，約78×22×20mm，接點足夠供應馬達。',1,0,'個',1.5,'採購','待購','18650 单节 带线 电池盒','電池盒長度與保護電芯相容性待量測；模型固定扣間距可調。','https://tao.hvcis.com/goods-nzX7QomCMt3YQeVxyVhkkzs0tP-YA3ppxSdQMg6J36IB.html');
row('D05','總電源開關','小船型開關，直流額定至少5A。',1,0,'個',1,'採購','待購','小船型 电源开关 DC 5A','放在保護板至升壓板的供電路徑。第一版關機充電。');
row('D06','USB Type-C 充電線','設備端Type-C，依現有充電器選另一端。',1,0,'條',2,'採購','待確認','USB Type-C 充电线 2A','充電器已有；線材是否已有未確認。先列入採購，若已有可填已有量1。');
row('E01','洞洞板','裁成約14×51mm，四按鍵中心距13mm。',1,0,'片',0.8,'採購','待購','洞洞板 2.54mm 小块','固定於上罩P35支架；腳距依實物調整，PCF板及螢幕採低矮焊線，未包容高直立杜邦接頭。');
row('E02','連接導線','訊號線與較粗的馬達／電池供電線。',1,0,'組',0.8,'採購','待購','硅胶线 22AWG 28AWG','電池及馬達主電源不用細訊號線代替。線長待實際組裝裁切。');
row('E03','排針／杜邦接頭','2.54mm，足夠連接控制器、螢幕及驅動板。',1,0,'組',0.5,'採購','待購','2.54 排针 杜邦 接头','若模組已焊排針，可降低此項新增用量。');
row('E04','電阻組','150Ω/¼W×2、10kΩ×4、47kΩ×1；充電設定另核。',1,0,'組',0.3,'採購','待購','电阻 10K 150R 220R 2.4K 5.1K','PCF板已有I2C上拉，不另重複加裝。TP4056先設0.5A；PROG與Type-C CC電阻依實板核對。');
row('E05','去耦／濾波電容','100nF陶瓷×2、470–1000µF/10V電解約2顆。',1,0,'組',0.6,'採購','待購','100nF 104 1000uF 10V 电容','馬達端去耦及5V電源緩衝，與PCB內建電容配合。');
row('E06','可拆電源接頭','JST-XH等兩芯接頭，約2組。',1,0,'組',0.5,'採購','待購','XH2.54 2P 公母 接线','確認極性，方便拆裝電池與旋轉頭。');
row('E07','熱縮管／小束帶','絕緣與線材固定。',1,0,'組',0.5,'採購','待購','热缩管 小扎带','包括光電座及板件的束帶固定。');

// These are fabricated parts. Costs are collected once under filament below.
for (const p of manifest.parts) {
  row(p.id, p.name, `${p.dimensions_mm.join(' × ')} mm；${p.material}`,p.qty,0,'件',null,'自行列印','待列印','',p.note+' 列印方向已放入STL；成本併入耗材。');
}
row('F01','PLA 列印耗材',`暫留${filamentKg.toFixed(2)}kg；全部模型實心換算約${manifest.solid_PLA_mass_g}g（含上罩與選配）。`,filamentKg,0,'kg',40,'耗材分攤','待確認','PLA 1.75mm 1kg','保守預留：模型實心質量＋試配片＋25g餘料後向上取50g整數。尚未切片，實際以切片秤重為準；若購整卷按整卷實付核算。');
row('F02','運費及價差預留','依合單、收貨地及實際SKU調整。',1,0,'筆',9.5,'運費預留','待確認','','目標預留，不是已確認運費。');

const start=11,end=start+rows.length-1;
sheet.showGridLines=false; sheet.tabColor='#294556';
sheet.getRange(`A1:S${end}`).format.font={name:'Arial',size:10,color:'#223843'};
sheet.getRange(`A1:S${end}`).format.verticalAlignment='center';
sheet.getRange('A2').values=[['撲克牌發牌機 BOM']];
sheet.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#223843'};
sheet.getRange('A3').values=[['V1.0.0　轉盤間隙2mm　P32A覆蓋P32B台階上殼　兩規格螺絲　Type-C']];
sheet.getRange('A4').values=[['2026-11-11更新。已有項目不計新增採購費；價格為目標預算，實際SKU、庫存與運費待核。']];
sheet.getRange('A8').values=[['淡黃色欄可編輯。已有量按初始庫存填入；實價空白表示尚未報價，並非零元。']];
sheet.getRange('A9').values=[['含耗材總額超出80元時顯示紅色；外購加運費與含耗材總額分別列示。']];
for(const cell of ['A3','A4','A8','A9']) sheet.getRange(cell).format.font={name:'Arial',size:10,color:'#53656F'};
sheet.getRange('A5:M5').format.borders={bottom:{style:'thin',color:'#9AAAB4'}};
sheet.getRange('A6').values=[['預算上限']]; sheet.getRange('B6').values=[[80]];
sheet.getRange('D6').values=[['外購材料']];
sheet.getRange('E6').formulas=[[`=ROUND(SUMIFS(I${start}:I${end},L${start}:L${end},"採購"),2)`]];
sheet.getRange('G6').values=[['耗材']]; sheet.getRange('H6').formulas=[[`=ROUND(SUMIFS(I${start}:I${end},L${start}:L${end},"耗材分攤"),2)`]];
sheet.getRange('J6').values=[['運費預留']]; sheet.getRange('K6').formulas=[[`=SUMIFS(I${start}:I${end},L${start}:L${end},"運費預留")`]];
sheet.getRange('A7').values=[['總計']]; sheet.getRange('B7').formulas=[[`=IF(COUNTIFS(I${start}:I${end},"待填單價")>0,"待填單價",ROUND(SUM(I${start}:I${end}),2))`]];
sheet.getRange('D7').values=[['預算餘額']]; sheet.getRange('E7').formulas=[['=IF(ISNUMBER(B7),B6-B7,"待填單價")']];
sheet.getRange('G7').values=[['外購含運']]; sheet.getRange('H7').formulas=[['=ROUND(E6+K6,2)']];
sheet.getRange('J7').values=[['實價合計']]; sheet.getRange('K7').formulas=[[`=IF(COUNT(J${start}:J${end})=0,"未填實價",ROUND(SUM(K${start}:K${end}),2))`]];
sheet.getRange('M6').formulas=[['=IF(ISNUMBER(B7),IF(B7>B6,"超出預算",IF(B7=B6,"已到上限","目標內")),"待填單價")']];
sheet.getRange('M7').values=[['人民幣 CNY']];
sheet.getRange('B6').format.fill='#FFF2CC';
const money='"¥"#,##0.00;[Red]-"¥"#,##0.00;"¥"0.00';
for(const a of ['B6:B7','E6:E7','H6:H7','K6:K7']) { sheet.getRange(a).setNumberFormat(money);sheet.getRange(a).format.font.bold=true; }
sheet.getRange('E7').conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{fill:'#FCE4D6',font:{color:'#9C2F22',bold:true}}});
sheet.getRange('B7').conditionalFormats.addCustom('AND(ISNUMBER(B7),B7>$B$6)',{fill:'#FCE4D6',font:{color:'#9C2F22',bold:true}});
sheet.getRange('M6').conditionalFormats.add('containsText',{text:'超出',format:{fill:'#FCE4D6',font:{color:'#9C2F22',bold:true}}});

const headers=['編號','材料／零件','指定規格','需用量','已有量','待備量','單位','目標單價','目標金額','實際單價','實價金額','取得方式','採購狀態'];
sheet.getRange('A10:M10').values=[headers];
const values=rows.map(r=>[r.id,r.name,r.spec,r.qty,r.owned,null,r.unit,r.price,null,null,null,r.acquisition,r.status]);
sheet.getRange(`A${start}:M${end}`).values=values;
const formulaF=rows.map((_,i)=>[`=MAX(D${start+i}-E${start+i},0)`]);
const formulaI=rows.map((_,i)=>{const n=start+i;return [`=IF(OR(L${n}="自行列印",L${n}="既有設備"),0,IF(F${n}=0,0,IF(ISNUMBER(H${n}),ROUND(F${n}*H${n},2),"待填單價")))`];});
const formulaK=rows.map((_,i)=>{const n=start+i;return [`=IF(OR(L${n}="自行列印",L${n}="既有設備"),0,IF(F${n}=0,0,IF(ISNUMBER(J${n}),ROUND(F${n}*J${n},2),"")))`];});
sheet.getRange(`F${start}:F${end}`).formulas=formulaF;
sheet.getRange(`I${start}:I${end}`).formulas=formulaI;
sheet.getRange(`K${start}:K${end}`).formulas=formulaK;
const table=sheet.tables.add(`A10:M${end}`,true,'DealerBOM'); table.style='TableStyleMedium2';table.showFilterButton=true;
sheet.getRange('A10:M10').format={fill:'#294556',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',wrapText:true,rowHeight:34};
sheet.getRange(`A${start}:M${end}`).format.rowHeight=48;
sheet.getRange(`B${start}:C${end}`).format.wrapText=true;
for(const a of [`D${start}:E${end}`,`H${start}:H${end}`,`J${start}:J${end}`,`L${start}:M${end}`]) sheet.getRange(a).format.fill='#FFF6DE';
sheet.getRange(`H${start}:K${end}`).setNumberFormat(money);
sheet.getRange(`D${start}:F${end}`).setNumberFormat('0');
const filamentRow=start+rows.findIndex(r=>r.id==='F01');
sheet.getRange(`D${filamentRow}:F${filamentRow}`).setNumberFormat('0.00');
sheet.getRange(`D${start}:K${end}`).format.horizontalAlignment='right';
sheet.getRange(`G${start}:G${end}`).format.horizontalAlignment='center';
sheet.getRange(`L${start}:L${end}`).dataValidation={rule:{type:'list',values:['採購','既有設備','自行列印','耗材分攤','運費預留']}};
sheet.getRange(`M${start}:M${end}`).dataValidation={rule:{type:'list',values:['已有','待購','待列印','待確認','已採購','已列印']}};
sheet.getRange(`M${start}:M${end}`).conditionalFormats.add('containsText',{text:'已有',format:{fill:'#E7EEE9',font:{color:'#345348'}}});
sheet.getRange(`I${start}:I${end}`).conditionalFormats.add('containsText',{text:'待填',format:{fill:'#FCE4D6',font:{color:'#9C2F22'}}});
sheet.getRange('O10:S10').values=[['淘寶搜尋詞','用途與待確認事項','商品參考','規格來源','選定商品連結（可填）']];
sheet.getRange('O10:S10').format={fill:'#EEF1F3',font:{name:'Arial',size:10,bold:true,color:'#294556'},horizontalAlignment:'center',rowHeight:34};
sheet.getRange(`O${start}:S${end}`).values=rows.map(r=>[r.search,r.note,r.product,r.official,null]);
sheet.getRange(`O${start}:S${end}`).format.wrapText=true;
sheet.getRange(`S${start}:S${end}`).format.fill='#FFF6DE';
// Notes provide compact, correctly identified source provenance beside inputs.
for(let i=0;i<rows.length;i++) {
  const n=start+i, r=rows[i];
  if(r.product) sheet.getRange(`Q${n}`).values=[['商品線索（待核價）']];
  if(r.official) sheet.getRange(`R${n}`).values=[['規格資料']];
}
sheet.getRange(`Q${start}:R${end}`).format.font.color='#245A82';
const widths={A:9,B:23,C:47,D:9,E:9,F:9,G:10,H:12,I:12,J:12,K:12,L:13,M:13,N:3,O:39,P:64,Q:24,R:18,S:32};
for(const [c,w] of Object.entries(widths)) sheet.getRange(`${c}1:${c}${end}`).format.columnWidth=w;
sheet.freezePanes.freezeRows(10); sheet.freezePanes.freezeColumns(2);

// Distinct fabrication view: dimensions, quantities, filenames and fit notes.
printSheet.showGridLines=false;printSheet.tabColor='#6D838B';
printSheet.getRange('A1:K60').format.font={name:'Arial',size:10,color:'#223843'};
printSheet.getRange('A1:K60').format.verticalAlignment='center';
printSheet.getRange('A2').values=[['設計與列印']]; printSheet.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#223843'};
printSheet.getRange('A4').values=[['內寬61mm，不設後擋板與定長槽；前緣對齊分牌閘。參考57×87與60×96mm，108張容量待實測。']];
printSheet.getRange('A5').values=[['P04B使上部抬升1.5mm，P04A對P02A名義間隙2mm；P26向下延長1.5mm以沿用原參考感測器。P32A／B台階上殼沿用。']];
printSheet.getRange('A6').values=[[`${manifest.parts.length}種STL已驗證封閉且符合A1 mini尺寸；含全件配對、1°旋轉、螺母裝入及平面落板核對。未實體試裝。`]];
printSheet.getRange('A7').values=[['28BYJ-48搭配2:1外部減速，整機速度受逐張轉向限制；本版不以每秒2至4張作性能承諾。']];
printSheet.getRange('A8').values=[['單顆18650，Type-C關機充電；先以0.5A選料，核對電池型號後再設定允許電流。']];
for(const a of ['A4','A5','A6','A7','A8']) printSheet.getRange(a).format.font.color='#53656F';
printSheet.getRange('A10:G10').values=[['模式','玩家','每人張數','餘牌','間隔角度','餘牌位置','需放牌數']];
printSheet.getRange('A11:G14').values=[['鬥地主',3,17,3,120,60,54],['摜蛋',4,27,0,90,null,108],['四人13張',4,13,0,90,null,52],['三人13張',3,13,13,120,60,52]];
printSheet.getRange('A15').values=[['第一位為開始時的朝向0°。餘牌集中發在第一與第二位之間。三人13張此表按放入52張計。']];
printSheet.getRange('E11:F14').setNumberFormat('0"°"');
printSheet.getRange('A10:G10').format={fill:'#294556',font:{color:'#FFFFFF',bold:true,name:'Arial',size:10},horizontalAlignment:'center',rowHeight:28};
printSheet.getRange('B11:G14').format.horizontalAlignment='right';
printSheet.getRange('A17:K17').values=[['編號','列印零件','數量','X(mm)','Y(mm)','Z(mm)','支撐','檔名','配合與組裝備註','備料類別','材質']];
const pr=18,pe=pr+manifest.parts.length-1;
printSheet.getRange(`A${pr}:K${pe}`).values=manifest.parts.map(p=>[p.id,p.name,p.qty,...p.dimensions_mm,p.supports,p.file,p.note,['P10','P11'].includes(p.id)?'壓力不足才選配':p.id==='P12'?'57mm牌選配':p.id==='P30'?'先印試配':'組裝件',p.material]);
printSheet.getRange('A17:K17').format={fill:'#294556',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',rowHeight:30};
printSheet.getRange(`A${pr}:K${pe}`).format.rowHeight=68;
printSheet.getRange(`B${pr}:B${pe}`).format.wrapText=true;
printSheet.getRange(`I${pr}:I${pe}`).format.wrapText=true;
printSheet.getRange(`G${pr}:G${pe}`).format.wrapText=true;
printSheet.getRange(`D${pr}:F${pe}`).setNumberFormat('0.00');
printSheet.getRange(`C${pr}:F${pe}`).format.horizontalAlignment='right';
const pw={A:7,B:25,C:7,D:11,E:11,F:11,G:13,H:19,I:70,J:17,K:16};
for(const [c,w] of Object.entries(pw))printSheet.getRange(`${c}1:${c}${pe}`).format.columnWidth=w;
printSheet.freezePanes.freezeRows(17);printSheet.freezePanes.freezeColumns(2);

screwSheet.showGridLines=false;screwSheet.tabColor='#C4784E';
screwSheet.getRange('A1:G18').format={font:{name:'Arial',size:11,color:'#223843'},verticalAlignment:'center'};
screwSheet.getRange('A2').values=[['整機螺絲：僅兩種規格']];
screwSheet.getRange('A2').format.font={name:'Arial',size:17,bold:true,color:'#223843'};
screwSheet.getRange('A4').values=[['DIN7991 M3×0.5；90°沉頭，頭徑≤6.0、頭高≤1.7；同用2mm內六角。長度包含頭部。']];
screwSheet.getRange('A6:G6').values=[['規格','模型需用量','建議備料','頭型／材質','主要用途','淘寶搜尋詞','備註']];
screwSheet.getRange('A7:G9').values=[
 ['M3×8',shortQty,Math.ceil((shortQty+2)/10)*10,'內六角沉頭；鋼或不鏽鋼','外殼、支架、輪轂夾緊等','DIN7991 M3x8 沉头 内六角','同一頭型，勿換盤頭或頭徑較大版本'],
 ['M3×25',longQty,longQty+2,'內六角沉頭；鋼或不鏽鋼','底盒、牌倉、RF300共用固定','DIN7991 M3x25 沉头 内六角 全牙','數量已包含RF300壓片與底座共用螺絲'],
 ['M3螺母',fasteners.nut_qty,Math.ceil((fasteners.nut_qty+2)/10)*10,'標準M3；對邊5.5、厚2.4','所有螺母位置','M3 六角螺母 厚2.4','螺母僅一規格；不使用加厚或防鬆帽型'],
 ];
screwSheet.getRange('A6:G6').format={fill:'#294556',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:32,wrapText:true,horizontalAlignment:'center'};
screwSheet.getRange('A7:G9').format={rowHeight:72,wrapText:true};
screwSheet.getRange('B7:C9').format.horizontalAlignment='center';
screwSheet.getRange('A11').values=[['建議備料含少量備品；Excel主表C07仍以整組6元作目標配置，實付依所選包裝填入。']];
screwSheet.getRange('A12').values=[['固定順序為P02A/馬達、P05B、P05A；B橫向用一組M3×8與螺母，A/B連接另用兩組。']];
screwSheet.getRange('A13').values=[['P06螺絲穿P04B孔，接觸滑環後輕調，不強鎖到底；RF300仍共用兩顆長螺絲。']];
screwSheet.getRange('A14').values=[['P05A未裝時，以常見2mm L型工具鎖緊B，尺寸依新工具圖核對；完整座面與閉孔限制歪斜，夾力仍待實測。']];
screwSheet.getRange('A15').values=[['P32A／P32B新增四組M3×8與M3螺母，從上殼內側連接；兩片先組合再裝頂部UI與罩入機構。']];
screwSheet.getRange('A16').values=[['逐位置模型數量：設計包內3D/五金數量表.csv。模型用量與建議備料數量分列。']];
for(const [col,width] of Object.entries({A:19,B:13,C:13,D:30,E:37,F:43,G:44}))screwSheet.getRange(`${col}1:${col}18`).format.columnWidth=width;
screwSheet.freezePanes.freezeRows(6);

// Check formulas by changing an existing input and a missing-price boundary.
wb.recalculate();
const baseTotal=sheet.getRange('B7').values[0][0];
const external=sheet.getRange('E6').values[0][0];
assert.equal(Math.round(external*100)/100,expectedExternal);
assert.equal(Math.round(baseTotal*100)/100,expectedTotal);
assert.equal(sheet.getRange('H7').values[0][0],expectedCash);
assert.equal(sheet.getRange('E7').values[0][0],80-expectedTotal);
assert.equal(sheet.getRange('K7').values[0][0],'未填實價');
const n20row=start+rows.findIndex(r=>r.id==='B02');
sheet.getRange(`H${n20row}`).values=[[6]];
wb.recalculate();assert.equal(sheet.getRange('B7').values[0][0],expectedTotal+1);
sheet.getRange(`H${n20row}`).values=[[5]];
sheet.getRange(`J${n20row}`).values=[[0]];
wb.recalculate();assert.equal(sheet.getRange(`K${n20row}`).values[0][0],0);
assert.equal(sheet.getRange('K7').values[0][0],0);
sheet.getRange(`J${n20row}`).values=[[null]];
sheet.getRange('E11').values=[[0]];
wb.recalculate();assert.equal(sheet.getRange('B7').values[0][0],'待填單價');
sheet.getRange('E11').values=[[1]];
wb.recalculate();

const inspect=await wb.inspect({kind:'table',range:'BOM!A6:M7',include:'values,formulas',tableMaxRows:3,tableMaxCols:13,maxChars:5000});
await fs.writeFile(path.join(support,'bom-verification.json'),JSON.stringify({summary:inspect.ndjson,expectedExternal,expectedWithShipping:expectedCash,expectedWithFilament:expectedTotal,filamentKg,owned:['ESP32-C3','18650 2900mAh','5V2A充電器','拓竹A1 mini'],printedTypes:manifest.parts.length},null,2));
console.log(inspect.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},summary:'final formula error scan',maxChars:3000});
console.log(errors.ndjson);
for(const [sn,range,fn] of [['BOM','A1:M26','bom-preview.png'],['BOM',`A41:M${end}`,'bom-lower-preview.png'],['BOM','O10:S32','sources-preview.png'],['設計與列印','A1:K30','printing-preview.png'],['螺絲規格','A1:G16','screws-preview.png']]) {
  const preview=await wb.render({sheetName:sn,range,scale:1.35,format:'png'});
  await fs.writeFile(path.join(support,fn),new Uint8Array(await preview.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(file);
// HYPERLINK calculation is unsupported by this artifact runtime. Cells above
// are authored as labels; this missing export feature uses native OOXML links.
const links=rows.flatMap((r,i)=>[
  ...(r.product?[{ref:`Q${start+i}`,url:r.product,label:'商品線索（待核價）'}]:[]),
  ...(r.official?[{ref:`R${start+i}`,url:r.official,label:'規格資料'}]:[]),
]);
const linksFile=path.join(support,'bom-hyperlinks.json');await fs.writeFile(linksFile,JSON.stringify(links));
execFileSync(process.env.CARD_DEALER_PYTHON || 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe',[path.join(root,'source/bom/attach_links.py'),file,linksFile],{stdio:'inherit'});
console.log(JSON.stringify({file,rows:rows.length,expectedBudget:expectedTotal,externalAndShipping:expectedCash,filamentKg},null,2));
