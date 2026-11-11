// Exercise the assembled offline 3D manual through browser controls.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';

const root=fileURLToPath(new URL('../../',import.meta.url));
const packages=process.env.CARD_DEALER_NODE_MODULES||'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules';
const require=createRequire(path.join(packages,'__manual_3d_verify__.cjs'));
const {chromium}=require('playwright');
const html=path.join(root,'manual/發牌機_組裝說明書_V1.0.0.html');
const modelData=JSON.parse(await fs.readFile(path.join(root,'manual/assets/assembly_3d.json'),'utf8'));
const expectedComponents=modelData.validation.standardComponents;
const expectedOverviewMoved=modelData.scenes.overview.meshes.filter(m=>m.explode.some(v=>Math.abs(v)>1e-6)).length;
const output=path.join(root,'.build/manual-3d-qa');
await fs.mkdir(output,{recursive:true});
const checks=[];
const failures=[];
const observations={};
const digest=buffer=>createHash('sha256').update(buffer).digest('hex');
const distance=(a,b)=>Math.sqrt(a.reduce((n,x,i)=>n+(x-b[i])**2,0));
const checksPass=(name,details={})=>checks.push({name,passed:true,...details});
const browser=await chromium.launch({headless:true,
 executablePath:process.env.CARD_DEALER_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe',
 args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});

async function makeContext(options={}){
 const context=await browser.newContext({viewport:{width:1440,height:1050},...options});
 await context.setOffline(true);
 const page=await context.newPage();
 const errors=[],external=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url())});
 return {context,page,errors,external};
}
async function readState(page){return page.evaluate(()=>window.manual3D?.getState?.()||null)}
async function openManual(page,hash='step-08'){
 await page.goto(pathToFileURL(html).href+'#'+hash);
 await page.locator('#step-title').waitFor();
 await page.waitForFunction(()=>window.manual3D?.ready===true);
}
async function navigate(page,index){
 if(await page.locator('#open-sidebar').isVisible())await page.locator('#open-sidebar').click();
 await page.locator(`#step-nav [data-step="${index}"]`).click();
 assert.equal(await page.locator('#step-number').textContent(),String(index+1).padStart(2,'0'));
}
async function screenshot(page,name){await page.screenshot({path:path.join(output,name),fullPage:true})}
const viewer=page=>page.locator('.manual3d');
const canvas=page=>page.locator('.manual3d-viewport canvas');
async function sceneReady(page,key){
 await page.waitForFunction(key=>{const s=window.manual3D?.getState?.();return s?.ready&&s.sceneKey===key&&s.renderCount>0},key);
}
async function step(page,index){await navigate(page,index);if(index!==20)await sceneReady(page,`step-${String(index+1).padStart(2,'0')}`)}
async function button(page,name){return viewer(page).getByRole('button',{name,exact:true})}
async function resetView(page){await (await button(page,'復位')).click()}
async function camera(page){return (await readState(page)).cameraPosition}
function normalize(a){const n=Math.hypot(...a);return a.map(x=>x/n)}
async function direction(page){const s=await readState(page);return normalize(s.cameraPosition.map((x,i)=>x-s.target[i]))}
async function cameraDistance(page){const s=await readState(page);return distance(s.cameraPosition,s.target)}
async function touchDrag(page,session,start,end){
 const point=(p,id=1)=>({x:p[0],y:p[1],id,radiusX:2,radiusY:2,force:1});
 await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point(start)]});
 for(let i=1;i<=8;i++){const p=start.map((x,k)=>x+(end[k]-x)*i/8);await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[point(p)]})}
 await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
}
async function touchPinch(session,cx,cy){
 const points=half=>[{x:cx-half,y:cy,id:1,radiusX:2,radiusY:2,force:1},{x:cx+half,y:cy,id:2,radiusX:2,radiusY:2,force:1}];
 await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:points(35)});
 for(let half=40;half<=90;half+=5)await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:points(half)});
 await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
}

try{
 const desktop=await makeContext();
 await openManual(desktop.page);
 await sceneReady(desktop.page,'step-08');
 const page=desktop.page;
 const initial=await readState(desktop.page);
 assert(initial,'Viewer must expose its current observation state');
 observations.initial={...initial,meshPositions:undefined};
 const rendering=await page.evaluate(()=>{const r=window.manual3D.renderer,gl=r.getContext();return {type:gl.constructor.name,triangles:r.info.render.triangles,width:gl.drawingBufferWidth,height:gl.drawingBufferHeight}});
 assert.match(rendering.type,/WebGL/);assert(rendering.triangles>0);assert(rendering.width>100&&rendering.height>100);observations.rendering=rendering;
 checksPass('Offline local HTML initializes an actual 3D viewer');
 await screenshot(page,'desktop-step08.png');
 for(let i=0;i<22;i++){
  await step(page,i);
  if(i===20){assert(await page.locator('#diagram-open').isVisible());assert.equal(await canvas(page).isVisible(),false);continue}
  const s=await readState(page);assert(s.meshCount>0);assert(await canvas(page).isVisible());
  if(i===0){assert(await viewer(page).getByRole('slider',{name:'爆炸分解幅度'}).isDisabled());checksPass('Trial-layout step disables the unnecessary exploded-view slider')}
  const tris=await page.evaluate(()=>window.manual3D.renderer.info.render.triangles);assert(tris>0,`No triangles at step ${i+1}`);
 }
 checksPass('Every mechanical step has rendered triangle meshes; wiring step remains a readable diagram',{mechanicalSteps:21});
 await step(page,7);await canvas(page).scrollIntoViewIfNeeded();
 const box=await canvas(page).boundingBox(),start=[box.x+box.width*.42,box.y+box.height*.48];
 let picked=null;
 for(const [u,v] of [[.5,.5],[.5,.65],[.35,.5],[.65,.5],[.45,.4]]){
  await page.mouse.click(box.x+box.width*u,box.y+box.height*v);picked=(await readState(page)).selectedId;if(picked)break;
 }
 assert(picked,'Clicking visible geometry must select a real mesh');
 await viewer(page).getByRole('combobox',{name:'選取3D零件或螺絲'}).selectOption('');checksPass('Pointer picking identifies visible model geometry');
 const cameraBefore=await camera(page);const pixelsBefore=digest(await canvas(page).screenshot());
 await page.mouse.move(...start);await page.mouse.down();await page.mouse.move(start[0]+100,start[1]+50,{steps:12});await page.mouse.up();
 await page.waitForFunction(before=>{const p=window.manual3D.getState().cameraPosition;return p.some((x,i)=>Math.abs(x-before[i])>.1)},cameraBefore);
 assert.notEqual(digest(await canvas(page).screenshot()),pixelsBefore);checksPass('Mouse drag rotates the actual camera and changes rendered pixels');
 const zoomBefore=await cameraDistance(page);await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.wheel(0,-400);
 await page.waitForFunction(before=>{const s=window.manual3D.getState();return Math.hypot(...s.cameraPosition.map((x,i)=>x-s.target[i]))<before*.98},zoomBefore);
 checksPass('Mouse wheel zoom changes viewing distance');
 await step(page,4);await resetView(page);
 const explosionBefore=await readState(page);const range=viewer(page).getByRole('slider',{name:'爆炸分解幅度'});await range.focus();await range.press('End');
 const explosionAfter=await readState(page);assert.equal(explosionAfter.explodeAmount,1);
 assert(explosionAfter.meshPositions.some((m,i)=>distance(m.position,explosionBefore.meshPositions[i].position)>1),'Slider must move real mesh positions');
 await screenshot(page,'desktop-step05-exploded.png');checksPass('Exploded view moves individual parts and fasteners rather than only the percentage label');
 const originalCount=explosionAfter.visibleCount;const hardware=viewer(page).getByRole('checkbox',{name:'顯示螺絲與螺母'});await hardware.uncheck();const withoutHardware=await readState(page);assert(withoutHardware.visibleCount<originalCount);assert(withoutHardware.meshPositions.filter(x=>x.kind==='screw'||x.kind==='nut').every(x=>!x.visible));await hardware.check();checksPass('Hardware filter hides actual screw and nut meshes');
 const source=JSON.parse(await fs.readFile(path.join(root,'manual/assets/assembly_3d.json'),'utf8'));
 const chosen=source.scenes['step-05'].meshes.find(x=>x.kind==='screw');assert(chosen);
 await viewer(page).getByRole('combobox',{name:'選取3D零件或螺絲'}).selectOption(chosen.id);
 assert.equal((await readState(page)).selectedId,chosen.id);assert((await viewer(page).locator('.manual3d-selected-label').textContent()).includes(chosen.label));
 await (await button(page,'只看選取')).click();assert.equal((await readState(page)).visibleCount,1);await (await button(page,'聚焦')).click();await (await button(page,'恢復全部')).click();assert.equal((await readState(page)).visibleCount,originalCount);checksPass('Small screws can be selected, identified, isolated, focused and restored');
 await (await button(page,'上視')).click();assert((await direction(page))[2]>.999);await (await button(page,'底視')).click();assert((await direction(page))[2]<-.999);await (await button(page,'等角')).click();assert(Math.abs((await direction(page))[2])<.99);checksPass('Top, bottom and isometric camera controls point in their stated directions');
 await step(page,19);await (await button(page,'底視')).click();await screenshot(page,'desktop-step20-bottom.png');
 await step(page,21);assert.equal((await readState(page)).meshCount,expectedComponents);const shell=viewer(page).getByRole('checkbox',{name:'顯示外殼與底板'});await shell.uncheck();const withoutShell=await readState(page);assert(withoutShell.visibleCount<expectedComponents);assert(withoutShell.meshPositions.filter(x=>x.isShell).every(x=>!x.visible));await screenshot(page,'desktop-step22-shell-hidden.png');checksPass('Complete assembly matches the current independently visible component count and shell filtering reveals internals');
 const sceneSelector=viewer(page).getByRole('combobox',{name:'3D模型範圍'});await sceneSelector.selectOption('overview');await sceneReady(page,'overview');const overviewBefore=await readState(page);const overviewRange=viewer(page).getByRole('slider',{name:'爆炸分解幅度'});assert(!await overviewRange.isDisabled());await overviewRange.focus();await overviewRange.press('End');const overviewAfter=await readState(page);const movedOverview=overviewAfter.meshPositions.filter((m,i)=>distance(m.position,overviewBefore.meshPositions[i].position)>1e-6).length;assert.equal(movedOverview,expectedOverviewMoved);await sceneSelector.selectOption('step');await sceneReady(page,'step-22');assert.equal((await readState(page)).explodeAmount,0);checksPass('Overview explosion moves the intended components and returning to the step resets its view',{movedComponents:movedOverview});
 // The root integration supplies stable IDs for the existing diagram/3D switch.
 const diagramSwitch=page.locator('#show-2d');const modelSwitch=page.locator('#show-3d');
 await diagramSwitch.click();assert(await page.locator('#diagram-open').isVisible());assert.equal(await canvas(page).isVisible(),false);await modelSwitch.click();assert(await canvas(page).isVisible());checksPass('Step illustration and interactive 3D modes can be switched without losing the step');
 await page.locator('#expand-image').click();assert(await page.locator('#model-dialog').evaluate(x=>x.open));assert(await page.locator('#model-dialog .manual3d-viewport canvas').isVisible());await page.locator('#close-model').click();assert(!await page.locator('#model-dialog').evaluate(x=>x.open));await page.locator('#model-host .manual3d-viewport canvas').waitFor({state:'visible'});assert((await readState(page)).ready);checksPass('Enlarged model dialog restores the live 3D view to the step on closing');
 assert.deepEqual(desktop.errors,[]);
 assert.deepEqual(desktop.external,[]);
 await desktop.context.close();

 const mobile=await makeContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:1});
 await openManual(mobile.page);await sceneReady(mobile.page,'step-08');await canvas(mobile.page).scrollIntoViewIfNeeded();
 assert.equal(await mobile.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await screenshot(mobile.page,'mobile-step08-initial.png');
 const mobileBox=await canvas(mobile.page).boundingBox();const cx=mobileBox.x+mobileBox.width/2,cy=mobileBox.y+mobileBox.height/2;
 const session=await mobile.context.newCDPSession(mobile.page);const touchCameraBefore=await camera(mobile.page);
 await touchDrag(mobile.page,session,[cx-45,cy],[cx+40,cy+35]);
 assert(distance(touchCameraBefore,await camera(mobile.page))>.1);checksPass('Mobile one-finger gesture rotates the 3D view');
 const pinchBefore=await cameraDistance(mobile.page);await touchPinch(session,cx,cy);const pinchAfter=await cameraDistance(mobile.page);assert(pinchAfter<pinchBefore*.98);checksPass('Mobile two-finger pinch zoom changes camera distance');
 await mobile.page.getByRole('combobox',{name:'選取3D零件或螺絲'}).selectOption(source.scenes['step-08'].meshes.find(x=>x.kind==='screw').id);assert((await readState(mobile.page)).selectedId);await screenshot(mobile.page,'mobile-step08.png');
 assert.equal(await mobile.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);assert.deepEqual(mobile.errors,[]);assert.deepEqual(mobile.external,[]);checksPass('Mobile controls and part selector fit within a 390px viewport');await mobile.context.close();

 const fallback=await makeContext();await fallback.context.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){if(/^(webgl2?|experimental-webgl)$/i.test(type))return null;return original.call(this,type,...args)}});
 await fallback.page.goto(pathToFileURL(html).href+'#step-08');await fallback.page.locator('#step-title').waitFor();await fallback.page.locator('#diagram-open').waitFor({state:'visible'});await fallback.page.locator('#next-step').click();assert.equal(await fallback.page.locator('#step-number').textContent(),'09');assert.deepEqual(fallback.errors,[]);assert.deepEqual(fallback.external,[]);await screenshot(fallback.page,'webgl-unavailable-fallback.png');checksPass('Unavailable WebGL automatically retains the diagram and functioning assembly navigation');await fallback.context.close();

 checksPass('All tested contexts run offline without external requests or uncaught script exceptions');
 const report={version:'V1.0.0',html_sha256:digest(await fs.readFile(html)),passed:!failures.length,
  checks,failures,observations,browser:await browser.version(),offline:true,
  scope:'Interactive 3D viewing and responsive/offline behavior; not physical assembly validation.'};
 await fs.writeFile(path.join(root,'verification/manual_3d_browser_checks.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({passed:report.passed,checks:checks.length},null,2));
}finally{await browser.close()}
