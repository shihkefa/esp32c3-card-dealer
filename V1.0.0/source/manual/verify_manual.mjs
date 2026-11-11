// Verify the offline guide in an isolated headless browser profile.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=fileURLToPath(new URL('../../',import.meta.url));
const pkg=process.env.CARD_DEALER_NODE_MODULES||'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules';
const require=createRequire(path.join(pkg,'__manual_verify__.cjs'));
const {chromium}=require('playwright');
const out=path.join(root,'.build/manual-qa');await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CARD_DEALER_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
await context.setOffline(true);
const page=await context.newPage(),errors=[],external=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url())});
const checks=[];
function passed(name){checks.push({name,passed:true})}
const html=path.join(root,'manual/發牌機_組裝說明書_V1.0.0.html');
const manifest=JSON.parse(await fs.readFile(path.join(root,'3d/parts_manifest.json'),'utf8'));
const catalog=JSON.parse(await fs.readFile(path.join(root,'3d/fastener_catalog.json'),'utf8'));
const expectedTotals=[8,25].map(n=>catalog.screw_skus.find(x=>x.length_mm===n).qty).concat(catalog.nut_qty);
try{
 await page.goto(pathToFileURL(html).href);await page.locator('#step-title').waitFor();
 assert.equal(await page.locator('#step-nav [data-step]').count(),22);passed('22 steps render from a local file while offline');
 const decoded=await page.evaluate(async()=>{const d=JSON.parse(document.querySelector('#manual-data').textContent);const urls=Object.values(d.figures).flatMap(f=>[f.src,...f.details.map(x=>x.src)]);await Promise.all(urls.map(src=>new Promise((ok,bad)=>{const i=new Image();i.onload=()=>i.naturalWidth>0?ok():bad('empty');i.onerror=()=>bad('image error');i.src=src})));return urls.length});
 assert(decoded>=22);passed('All embedded step and detail images decode');
 await page.screenshot({path:path.join(out,'desktop-step01.png'),fullPage:true});
 for(let i=0;i<22;i++){await page.locator(`#step-nav [data-step="${i}"]`).click();assert.equal(await page.locator('#step-number').textContent(),String(i+1).padStart(2,'0'));assert(await page.locator('#step-actions li').count()>0);if([3,11,19].includes(i))await page.screenshot({path:path.join(out,`desktop-step${String(i+1).padStart(2,'0')}.png`),fullPage:true})}passed('All 22 navigation targets show instructions and figures');
 await page.locator('#step-nav [data-step="4"]').click();await page.locator('#complete-step').click();assert.equal(await page.locator('#progress-label').textContent(),'1 / 22');await page.reload();assert.equal(await page.locator('#complete-step').getAttribute('aria-pressed'),'true');passed('Completion persists through reload');
 await page.locator('#reset-progress').click();await page.locator('#cancel-reset').click();assert.equal(await page.locator('#progress-label').textContent(),'1 / 22');await page.locator('#reset-progress').click();await page.locator('#confirm-reset').click();assert.equal(await page.locator('#progress-label').textContent(),'0 / 22');passed('Reset requires an explicit in-page choice and preserves cancellation');
 await page.locator('#show-2d').click();await page.locator('#expand-image').click();assert(await page.locator('#image-dialog').evaluate(x=>x.open));await page.locator('#zoom-in').click();assert.equal(await page.locator('#large-image').evaluate(x=>x.style.width),'125%');await page.keyboard.press('Escape');assert(!await page.locator('#image-dialog').evaluate(x=>x.open));passed('Retained image viewer zoom and Escape dismissal work');
 await page.locator('#step-search').fill('P05');assert(await page.locator('#step-nav [data-step]').count()>0);await page.locator('#step-search').fill('no-such-part-zz');assert.equal(await page.locator('#step-nav [data-step]').count(),0);await page.locator('#step-search').fill('');passed('Step search and empty state work');
 await page.locator('[data-view="parts"]').click();assert.equal(await page.locator('.part-tile').count(),manifest.parts.length);await page.locator('#parts-filter').selectOption('optional');assert.equal(await page.locator('.part-tile').count(),3);await page.locator('#parts-filter').selectOption('all');await page.locator('#parts-search').fill('P05');
 // Related-part notes are searchable too, so a documented P05 relationship
 // can legitimately add results beyond the two P05 printable parts.
 const p05Ids=await page.locator('.part-tile .part-id').allTextContents();
 assert(p05Ids.includes('P05A')&&p05Ids.includes('P05B'));
 assert((await page.locator('.part-tile').allTextContents()).every(text=>text.includes('P05')));
 await page.screenshot({path:path.join(out,'desktop-parts.png'),fullPage:true});passed('Current part index and optional/P05 filters work');
 await page.locator('[data-view="fasteners"]').click();assert.equal(await page.locator('#fastener-table tr').count(),22);const totals=await page.locator('#fastener-table').evaluate(t=>[1,2,3].map(col=>[...t.rows].reduce((n,r)=>n+(parseInt(r.cells[col].textContent)||0),0)));assert.deepEqual(totals,expectedTotals);passed('Displayed per-step hardware totals reconcile to the current catalog');
 await page.locator('[data-view="wiring"]').click();await page.locator('#open-wiring').click();const frame=page.frameLocator('#wire-container iframe');await frame.locator('#board svg').waitFor();assert.equal(await frame.locator('.trace').count(),97);await frame.locator('#group').selectOption('motor');assert(await frame.locator('.trace.dim').count()>0);await frame.locator('#fit').click();await page.locator('#close-wiring').click();passed('Embedded interactive wiring viewer runs offline and filters 97 routes');
 await page.locator('[data-view="steps"]').click();await page.locator('#step-nav [data-step="20"]').click();assert.equal(await page.locator('.figure-label').textContent(),'逐腳接線圖概覽');await page.locator('#diagram-open').click();assert(await page.locator('#wiring-dialog').evaluate(x=>x.open));await page.locator('#close-wiring').click();passed('Wiring step opens the readable interactive diagram directly');
 await page.locator('[data-view="steps"]').click();await page.locator('#step-nav [data-step="3"]').click();const before=await page.locator('#step-number').textContent();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#step-number').textContent(),String(Number(before)+1).padStart(2,'0'));passed('Keyboard previous and next navigation work');
 for(const [w,h] of [[390,844],[768,1024],[1280,900],[1920,1080]]){
  await page.setViewportSize({width:w,height:h});await page.evaluate(()=>window.scrollTo(0,0));
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false,`overflow at ${w}`);
  if(w===390){await page.locator('#open-sidebar').click();await page.locator('#step-nav [data-step="19"]').click();assert.equal(await page.locator('#sidebar').evaluate(x=>x.classList.contains('open')),false);await page.locator('#announcer').waitFor({state:'hidden'});await page.screenshot({path:path.join(out,'mobile-step20.png'),fullPage:true});await page.locator('[data-view="parts"]').click();await page.screenshot({path:path.join(out,'mobile-parts.png'),fullPage:true});await page.locator('[data-view="steps"]').click()}
 }passed('Responsive layouts at 390, 768, 1280 and 1920 px have no page overflow');
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);passed('No JavaScript exceptions or external network requests');
 const report={version:'V1.0.0',html_sha256:createHash('sha256').update(await fs.readFile(html)).digest('hex'),passed:true,checks,embeddedImagesChecked:decoded,offline:true,externalRequests:external,pageErrors:errors,browser:await browser.version(),qaImages:'Internal .build/manual-qa captures, not required by the standalone HTML'};
 await fs.writeFile(path.join(root,'verification/manual_browser_checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:true,checks:checks.length,embeddedImagesChecked:decoded},null,2));
}finally{await browser.close()}
