// Integration smoke test for the deployed, self-contained GitHub Pages manual.
// Uses a fresh headless profile; never attaches to a personal browser.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('../',import.meta.url));
const target=new URL(process.env.CARD_DEALER_PAGES_URL||'https://shihkefa.github.io/esp32c3-card-dealer/');
assert.equal(target.protocol,'https:','The Pages endpoint must use HTTPS');
const packages=process.env.CARD_DEALER_NODE_MODULES||'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules';
const require=createRequire(path.join(packages,'__verify_pages__.cjs'));
const {chromium}=require('playwright');
const digest=buffer=>createHash('sha256').update(buffer).digest('hex');
const distance=(a,b)=>Math.hypot(...a.map((x,i)=>x-b[i]));
const expectedSha=digest(await fs.readFile(path.join(root,'docs/index.html')));
const output=path.join(root,'.build/pages-qa');
const reportPath=path.join(output,'report.json');
await fs.mkdir(output,{recursive:true});await fs.mkdir(path.dirname(reportPath),{recursive:true});
const checks=[],pageErrors=[],externalRequests=[];
const observations={url:target.href,expected_html_sha256:expectedSha};
let browser;
const pass=(name,details={})=>checks.push({name,passed:true,...details});
const viewer=page=>page.locator('.manual3d');
const canvas=page=>page.locator('.manual3d-viewport canvas');
const state=page=>page.evaluate(()=>window.manual3D.getState());
async function settled(page,key){await page.waitForFunction(key=>{const s=window.manual3D?.getState?.();return s?.ready&&s.sceneKey===key&&s.renderCount>0},key,{timeout:30000})}
async function step(page,index){
 if(await page.locator('#open-sidebar').isVisible())await page.locator('#open-sidebar').click();
 await page.locator(`#step-nav [data-step="${index}"]`).click();
 assert.equal(await page.locator('#step-number').textContent(),String(index+1).padStart(2,'0'));
 if(index!==20)await settled(page,`step-${String(index+1).padStart(2,'0')}`);
}
async function context(options={}){
 const ctx=await browser.newContext({viewport:{width:1440,height:1050},extraHTTPHeaders:{'Cache-Control':'no-cache'},...options});
 const page=await ctx.newPage();
 page.on('pageerror',e=>pageErrors.push(e.message));
 page.on('request',r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==target.origin)externalRequests.push({url:r.url(),type:r.resourceType()})});
 return {ctx,page};
}

try{
 browser=await chromium.launch({headless:true,
  executablePath:process.env.CARD_DEALER_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe',
  args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const desktop=await context(),page=desktop.page;
 const opening=new URL(target);opening.hash='step-08';
 const response=await page.goto(opening.href,{waitUntil:'domcontentloaded',timeout:60000});
 assert(response,'The navigation must return an HTTP response');assert.equal(response.status(),200);
 assert.equal(new URL(page.url()).protocol,'https:');assert.equal(new URL(page.url()).origin,target.origin);
 const liveSha=digest(await response.body());assert.equal(liveSha,expectedSha,'Published HTML differs from the current docs/index.html');
 observations.live_html_sha256=liveSha;observations.http_status=response.status();
 pass('HTTPS responds with HTTP 200 and the exact deployed HTML bytes');

 await page.locator('#step-title').waitFor();await settled(page,'step-08');
 assert.equal(await page.locator('#step-nav [data-step]').count(),22);
 const rendering=await page.evaluate(()=>{const r=window.manual3D.renderer,gl=r.getContext();return {context:gl.constructor.name,triangles:r.info.render.triangles,scene:window.manual3D.getState().sceneKey}});
 assert.match(rendering.context,/WebGL/);assert(rendering.triangles>0);observations.rendering=rendering;
 await page.screenshot({path:path.join(output,'pages-desktop-step08.png'),fullPage:true});
 pass('The live manual shows 22 steps and renders actual WebGL geometry');

 await canvas(page).scrollIntoViewIfNeeded();const box=await canvas(page).boundingBox();
 const beforeRotate=(await state(page)).cameraPosition;
 await page.mouse.move(box.x+box.width*.4,box.y+box.height*.5);await page.mouse.down();
 await page.mouse.move(box.x+box.width*.6,box.y+box.height*.6,{steps:10});await page.mouse.up();
 assert(distance((await state(page)).cameraPosition,beforeRotate)>.1);
 const zoomState=await state(page),beforeZoom=distance(zoomState.cameraPosition,zoomState.target);
 await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.wheel(0,-300);
 await page.waitForFunction(before=>{const s=window.manual3D.getState();return Math.hypot(...s.cameraPosition.map((x,i)=>x-s.target[i]))<before*.98},beforeZoom);
 pass('Dragging rotates the model view and the mouse wheel zooms');

 await step(page,4);const beforeExplode=await state(page);
 const range=viewer(page).getByRole('slider',{name:'爆炸分解幅度'});assert(!await range.isDisabled());await range.focus();await range.press('End');
 const exploded=await state(page);assert.equal(exploded.explodeAmount,1);
 assert(exploded.meshPositions.some((m,i)=>distance(m.position,beforeExplode.meshPositions[i].position)>1));
 const beforeHide=exploded.visibleCount;const hardware=viewer(page).getByRole('checkbox',{name:'顯示螺絲與螺母'});
 await hardware.uncheck();assert((await state(page)).visibleCount<beforeHide);await hardware.check();
 const screw=(await state(page)).meshPositions.find(m=>m.kind==='screw');assert(screw);
 await viewer(page).getByRole('combobox',{name:'選取3D零件或螺絲'}).selectOption(screw.id);
 assert.equal((await state(page)).selectedId,screw.id);
 await viewer(page).getByRole('button',{name:'只看選取',exact:true}).click();assert.equal((await state(page)).visibleCount,1);
 await viewer(page).getByRole('button',{name:'恢復全部',exact:true}).click();assert.equal((await state(page)).visibleCount,beforeHide);
 await page.screenshot({path:path.join(output,'pages-desktop-step05-exploded.png'),fullPage:true});
 pass('Step changes, explosion, hardware filtering and screw inspection work online');

 await page.locator('#show-2d').click();assert(await page.locator('#diagram-open').isVisible());assert(!await canvas(page).isVisible());
 await page.locator('#show-3d').click();assert(await canvas(page).isVisible());
 pass('The reference illustration and the interactive model can be switched');

 await page.locator('[data-view="wiring"]').click();await page.locator('#open-wiring').click();
 const frame=page.frameLocator('#wire-container iframe');await frame.locator('#board svg').waitFor();
 assert.equal(await frame.locator('.trace').count(),97);await frame.locator('#group').selectOption('motor');assert(await frame.locator('.trace.dim').count()>0);
 await page.locator('#close-wiring').click();
 pass('The embedded wiring viewer loads and filters its 97 wire routes');
 await desktop.ctx.close();

 const mobile=await context({viewport:{width:390,height:844},deviceScaleFactor:1,isMobile:true,hasTouch:true});
 await mobile.page.goto(opening.href,{waitUntil:'domcontentloaded',timeout:60000});await settled(mobile.page,'step-08');
 assert.equal(await mobile.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await canvas(mobile.page).scrollIntoViewIfNeeded();const mb=await canvas(mobile.page).boundingBox();const cx=mb.x+mb.width/2,cy=mb.y+mb.height/2;
 const touchBefore=(await state(mobile.page)).cameraPosition,cdp=await mobile.ctx.newCDPSession(mobile.page);
 const point=(x,y)=>({x,y,id:1,radiusX:2,radiusY:2,force:1});
 await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point(cx-35,cy)]});
 for(let i=1;i<=7;i++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[point(cx-35+10*i,cy+4*i)]});
 await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
 assert(distance((await state(mobile.page)).cameraPosition,touchBefore)>.1);
 await mobile.page.screenshot({path:path.join(output,'pages-mobile-step08.png'),fullPage:true});await mobile.ctx.close();
 pass('The 390px mobile layout fits and touch rotation changes the live view');

 assert.deepEqual(pageErrors,[]);assert.deepEqual(externalRequests,[]);
 pass('No uncaught script errors or off-origin runtime requests occur');
 const report={passed:true,url:target.href,html_sha256:liveSha,expected_html_sha256:expectedSha,
  checks,pageErrors,externalRequests,observations,browser:await browser.version(),
  scope:'Published Pages smoke/integration test; the full offline 3D suite remains in V1.0.0/verification.'};
 await fs.writeFile(reportPath,JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({passed:true,url:target.href,checks:checks.length,html_sha256:liveSha},null,2));
}catch(error){
 await fs.writeFile(reportPath,JSON.stringify({passed:false,url:target.href,expected_html_sha256:expectedSha,checks,
  failure:String(error.stack||error),pageErrors,externalRequests,observations},null,2)+'\n');
 throw error;
}finally{if(browser)await browser.close()}
