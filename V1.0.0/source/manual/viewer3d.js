/* Offline CAD assembly viewer. THREE and OrbitControls are embedded by the
 * manual builder. No model fetch, CDN, texture download or continuous loop. */
(function(global){
 'use strict';
 const kindLabel={print:'列印件',screw:'螺絲',nut:'螺母',hardware:'外購件',tool:'工具'};
 const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
 let nextId=0;
 function create(container,options){
  options=options||{};const data=options.data||{},T=global.THREE,Orbit=global.OrbitControls;
  const prefix='manual3d-'+(++nextId)+'-';let disposed=false,usable=false,frame=0,renderCount=0,sceneKey='',activeStepKey='';
  const root=document.createElement('div');root.className='manual3d';container.appendChild(root);
  function fail(message,error){usable=false;root.replaceChildren();const p=document.createElement('div');p.className='manual3d-error';p.textContent=message;root.appendChild(p);if(options.onError)options.onError(error||new Error(message));}
  const api={get ready(){return usable},get renderer(){return renderer},get controls(){return controls},
   setScene,resize,dispose,getState,select:selectById,fit:()=>fitView(),
   setExplode:value=>{if(explodeInput){explodeInput.value=String(clamp(Number(value)||0,0,1));changeExplode()}},
   clearSelection:()=>selectObject(null),element:root};
  let renderer=null,controls=null,camera=null,scene=null,content=null,axisGroup=null,selectionBox=null;
  let geometryCache=new Map(),objects=[],selected=null,isolated=false,explosion=0,currentScene=null,defaultDirection=null;
  let viewport=null,explodeInput=null,explodeOutput=null,showHardware=null,showShell=null,partsSelect=null,modeSelect=null,selectedLabel=null,countLabel=null,isolateButton=null,focusButton=null,allButton=null,status=null,resizeObserver=null;
  let pointerStart=null,clickBlocked=false,lastW=0,lastH=0;
  const listeners=[];
  function listen(target,event,handler,opts){target.addEventListener(event,handler,opts);listeners.push(()=>target.removeEventListener(event,handler,opts))}
  function button(label,title,action){const b=document.createElement('button');b.type='button';b.textContent=label;if(title)b.title=title;if(action)listen(b,'click',action);return b}
  function makeCheck(text,checked,onChange){const label=document.createElement('label');label.className='manual3d-check';const input=document.createElement('input');input.type='checkbox';input.checked=checked;label.append(input,document.createTextNode(text));listen(input,'change',onChange);return {label,input}}
  function announce(text){if(!status)return;status.hidden=!text;status.textContent=text||''}
  function requestRender(){if(disposed||!usable||frame)return;frame=requestAnimationFrame(()=>{frame=0;if(disposed||!usable||!lastW||!lastH)return;renderer.render(scene,camera);renderCount++})}
  if(!T||!Orbit){fail('3D 檢視器無法載入。請切換到原有示意圖繼續組裝。');return api}
  try{
   renderer=new T.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});
   renderer.setPixelRatio(Math.min(global.devicePixelRatio||1,2));
   renderer.setClearColor(0xf3f2ed,1);renderer.outputColorSpace=T.SRGBColorSpace;
   renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.2;
   scene=new T.Scene();scene.background=new T.Color(0xf3f2ed);
   camera=new T.PerspectiveCamera(36,1,.01,20000);camera.up.set(0,0,1);
   content=new T.Group();scene.add(content);
   scene.add(new T.HemisphereLight(0xffffff,0xb6c4c0,1.5));
   const key=new T.DirectionalLight(0xffffff,2.4);key.position.set(160,-160,250);scene.add(key);
   const fill=new T.DirectionalLight(0xe3f0f1,1.1);fill.position.set(-180,100,100);scene.add(fill);
   axisGroup=new T.Group();scene.add(axisGroup);
   selectionBox=new T.Box3Helper(new T.Box3(),0xd9813f);selectionBox.visible=false;scene.add(selectionBox);
   usable=true;
  }catch(error){if(renderer)renderer.dispose();fail('這個瀏覽器目前無法顯示 WebGL 3D。請切換到示意圖；組裝步驟與接線圖仍可閱讀。',error);return api}
  const toolbar=document.createElement('div');toolbar.className='manual3d-toolbar';root.appendChild(toolbar);
  modeSelect=document.createElement('select');modeSelect.className='manual3d-mode';modeSelect.setAttribute('aria-label','3D模型範圍');toolbar.appendChild(modeSelect);
  listen(modeSelect,'change',()=>{const key=modeSelect.value==='step'?activeStepKey:modeSelect.value;loadScene(key)});
  toolbar.append(button('等角','回到本步等角視角',()=>fitView(defaultDirection,null,true)),button('上視','從上方查看',()=>fitView([0,-.001,1],selected?[selected]:null,true)),button('底視','從底部查看螺母與螺絲',()=>fitView([0,.001,-1],selected?[selected]:null,true)));
  const spacer=document.createElement('span');spacer.className='manual3d-spacer';toolbar.appendChild(spacer);
  toolbar.append(button('復位','重設顯示、分解與選取',resetView),button('⛶','切換3D全螢幕',async()=>{try{if(document.fullscreenElement===root)await document.exitFullscreen();else if(root.requestFullscreen)await root.requestFullscreen();else announce('此瀏覽器不支援全螢幕；可用滾輪或雙指縮放模型。')}catch{announce('無法開啟全螢幕；仍可旋轉與縮放模型。')}}));
  viewport=document.createElement('div');viewport.className='manual3d-viewport';viewport.setAttribute('aria-label','可旋轉縮放的3D組裝模型');viewport.appendChild(renderer.domElement);root.appendChild(viewport);
  renderer.domElement.setAttribute('aria-label','3D模型，拖曳旋轉，滾輪或雙指縮放，點選零件查看名稱');renderer.domElement.tabIndex=0;
  const gestures=document.createElement('div');gestures.className='manual3d-gesture';gestures.innerHTML='<span class="manual3d-help">拖曳旋轉 · 滾輪／雙指縮放<span class="desktop-help"> · 右鍵平移</span></span>';
  countLabel=document.createElement('span');countLabel.className='manual3d-count';gestures.appendChild(countLabel);viewport.appendChild(gestures);
  status=document.createElement('p');status.className='manual3d-status';status.setAttribute('role','status');status.hidden=true;root.appendChild(status);
  const opts=document.createElement('div');opts.className='manual3d-options';root.appendChild(opts);
  const explosionLabel=document.createElement('label');explosionLabel.className='manual3d-explode';explosionLabel.textContent='組合';explodeInput=document.createElement('input');explodeInput.type='range';explodeInput.min='0';explodeInput.max='1';explodeInput.step='.01';explodeInput.value='0';explodeInput.id=prefix+'explode';explodeInput.setAttribute('aria-label','爆炸分解幅度');explosionLabel.htmlFor=explodeInput.id;explodeOutput=document.createElement('output');explodeOutput.textContent='0%';explosionLabel.append(explodeInput,document.createTextNode('分解'),explodeOutput);opts.appendChild(explosionLabel);listen(explodeInput,'input',changeExplode);
  const hardwareCheck=makeCheck('五金',true,()=>{applyVisibility();requestRender()});showHardware=hardwareCheck.input;showHardware.setAttribute('aria-label','顯示螺絲與螺母');opts.appendChild(hardwareCheck.label);
  const shellCheck=makeCheck('外殼／底板',true,()=>{applyVisibility();requestRender()});showShell=shellCheck.input;showShell.setAttribute('aria-label','顯示外殼與底板');opts.appendChild(shellCheck.label);
  opts.appendChild(button('只看五金','隱藏列印件與外購件，只看本步螺絲和螺母',()=>{
   isolated=false;objects.forEach(o=>o.visible=!!o.userData.desc.isFastener||['screw','nut'].includes(o.userData.desc.kind));selected=null;partsSelect.value='';updateSelection();countVisible();fitView();
  }));
  const inspect=document.createElement('div');inspect.className='manual3d-inspect';root.appendChild(inspect);
  const selectRow=document.createElement('div');selectRow.className='manual3d-select-row';const selectLabel=document.createElement('label');selectLabel.textContent='選取零件';selectLabel.htmlFor=prefix+'part';partsSelect=document.createElement('select');partsSelect.id=prefix+'part';partsSelect.setAttribute('aria-label','選取3D零件或螺絲');selectRow.append(selectLabel,partsSelect);inspect.appendChild(selectRow);listen(partsSelect,'change',()=>selectById(partsSelect.value));
  const selectionRow=document.createElement('div');selectionRow.className='manual3d-selection';selectedLabel=document.createElement('div');selectedLabel.className='manual3d-selected-label';selectedLabel.setAttribute('aria-live','polite');selectionRow.appendChild(selectedLabel);const selectionActions=document.createElement('div');selectionActions.className='manual3d-inspect-actions';focusButton=button('聚焦','將選取零件放大到適合畫面',()=>{if(selected)fitView(null,[selected])});isolateButton=button('只看選取','只顯示選取零件，以便查看孔與螺母槽',()=>{if(!selected)return;isolated=!isolated;applyVisibility();updateSelection();fitView()});allButton=button('恢復全部','恢復顯示本步所有零件與五金',()=>{isolated=false;showHardware.checked=true;showShell.checked=true;applyVisibility();updateSelection();fitView()});selectionActions.append(focusButton,isolateButton,allButton);selectionRow.appendChild(selectionActions);inspect.appendChild(selectionRow);
  const info=document.createElement('p');info.className='manual3d-info';info.textContent='點選模型或用清單找小螺絲；虛線顯示選取螺絲的安裝軸向。分解位移供辨識，並非實際鎖付或拆裝路徑。';inspect.appendChild(info);
  controls=new Orbit(camera,renderer.domElement);controls.target.set(0,0,0);controls.enableDamping=false;controls.rotateSpeed=.8;controls.zoomSpeed=.9;controls.panSpeed=.75;controls.screenSpacePanning=true;controls.minPolarAngle=.0001;controls.maxPolarAngle=Math.PI-.0001;
  listen(controls,'change',requestRender);
  listen(renderer.domElement,'pointerdown',e=>{pointerStart={x:e.clientX,y:e.clientY,pointer:e.pointerId};clickBlocked=false});
  listen(renderer.domElement,'pointermove',e=>{if(pointerStart&&Math.hypot(e.clientX-pointerStart.x,e.clientY-pointerStart.y)>6)clickBlocked=true});
  listen(renderer.domElement,'pointerup',e=>{
   if(!pointerStart||clickBlocked||e.button>0){pointerStart=null;return}pointerStart=null;
   const rect=renderer.domElement.getBoundingClientRect(),mouse=new T.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),ray=new T.Raycaster();ray.setFromCamera(mouse,camera);content.updateMatrixWorld(true);const hits=ray.intersectObjects(objects.filter(x=>x.visible),false);selectObject(hits[0]?hits[0].object:null);
  });
  listen(renderer.domElement,'pointercancel',()=>{pointerStart=null;clickBlocked=true});
  listen(renderer.domElement,'webglcontextlost',e=>{e.preventDefault();usable=false;announce('3D繪圖暫停，請切換到示意圖繼續閱讀，或重新整理頁面。');if(options.onError)options.onError(new Error('WebGL context lost'))});
  listen(document,'fullscreenchange',resize);
  if(global.ResizeObserver){resizeObserver=new ResizeObserver(resize);resizeObserver.observe(viewport)}else listen(global,'resize',resize);
  updateSelection();resize();return api;

  function decode(base64,Type){const s=atob(base64),bytes=new Uint8Array(s.length);for(let i=0;i<s.length;i++)bytes[i]=s.charCodeAt(i);return new Type(bytes.buffer)}
  function geometry(key){if(geometryCache.has(key))return geometryCache.get(key);const raw=data.geometries&&data.geometries[key];if(!raw)throw new Error('Missing geometry '+key);const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(decode(raw.positionsB64,Float32Array),3));g.setIndex(new T.BufferAttribute(decode(raw.indicesB64,Uint32Array),1));g.computeVertexNormals();g.computeBoundingBox();g.computeBoundingSphere();geometryCache.set(key,g);return g}
  function disposeAxes(){while(axisGroup&&axisGroup.children.length){const a=axisGroup.children[0];axisGroup.remove(a);if(a.geometry)a.geometry.dispose();if(a.material)a.material.dispose()}}
  function clearMeshes(){selectObject(null,false);for(const o of objects){content.remove(o);o.material.dispose()}objects=[];disposeAxes();if(selectionBox)selectionBox.visible=false;}
  function setScene(key){if(disposed||!usable)return false;if(String(key).startsWith('step-'))activeStepKey=key;return loadScene(key)}
  function loadScene(key){
   if(disposed||!usable)return false;const definition=data.scenes&&data.scenes[key];if(!definition){announce('此步沒有可用的3D模型，請切換到示意圖。');return false}
   clearMeshes();sceneKey=key;currentScene=definition;selected=null;isolated=false;explosion=0;explodeInput.value='0';const canExplode=definition.meshes.some(d=>(d.explode||[]).some(v=>Math.abs(Number(v)||0)>1e-8));explodeInput.disabled=!canExplode;explodeInput.title=canExplode?'調整本步零件的示意分解幅度':'本步無需分解';explodeOutput.textContent=canExplode?'0%':'本步無需分解';showHardware.checked=true;showShell.checked=true;defaultDirection=new T.Vector3(...(definition.camera||[1.2,-1.65,1.25])).normalize();announce('');
   try{for(const desc of definition.meshes){const mat=new T.MeshStandardMaterial({color:desc.color||'#93a5a1',metalness:['screw','nut'].includes(desc.kind)?.28:.02,roughness:.62,flatShading:true,side:T.DoubleSide});const o=new T.Mesh(geometry(desc.geometryKey),mat);o.userData.desc=desc;o.userData.baseColor=mat.color.clone();o.position.set(...(desc.position||[0,0,0]));o.name=desc.id;content.add(o);objects.push(o)}}catch(error){clearMeshes();announce('本步3D資料無法顯示，請切換到示意圖。');if(options.onError)options.onError(error);return false}
   modeSelect.replaceChildren();if(activeStepKey&&data.scenes[activeStepKey]){const option=document.createElement('option');option.value='step';option.textContent='本步組裝';modeSelect.appendChild(option)}for(const [id,label] of [['overview','整機總覽'],['optional','選配零件']])if(data.scenes[id]){const option=document.createElement('option');option.value=id;option.textContent=label;modeSelect.appendChild(option)}modeSelect.value=String(key).startsWith('step-')?'step':key;
   partsSelect.replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent='點選模型，或在這裡選取零件';partsSelect.appendChild(blank);const groups=new Map();for(const o of objects){const d=o.userData.desc,k=d.isFastener||['screw','nut'].includes(d.kind)?'螺絲與螺母':d.highlight?'本步重點零件':'配合件與已裝結構';if(!groups.has(k)){const group=document.createElement('optgroup');group.label=k;groups.set(k,group);partsSelect.appendChild(group)}const option=document.createElement('option');option.value=d.id;option.textContent=d.label||d.partId||d.id;groups.get(k).appendChild(option)}
   updateSelection();applyVisibility();resize();fitView(defaultDirection,null,true);requestRender();return true;
  }
  function isFastener(o){const d=o.userData.desc;return !!d.isFastener||['screw','nut'].includes(d.kind)}
  function isShell(o){const d=o.userData.desc;return !!d.isShell||['P01','P02A','P32A','P32B','P33','P34'].includes(d.partId)}
  function applyVisibility(){for(const o of objects)o.visible=isolated?o===selected:(!isFastener(o)||showHardware.checked)&&(!isShell(o)||showShell.checked);if(selected&&!selected.visible){selected=null;partsSelect.value='';updateSelection()}updateSelectionBox();countVisible();requestRender()}
  function countVisible(){countLabel.textContent=objects.filter(x=>x.visible).length+' / '+objects.length+' 件'}
  function changeExplode(){explosion=explodeInput.disabled?0:clamp(Number(explodeInput.value)||0,0,1);explodeOutput.textContent=explodeInput.disabled?'本步無需分解':Math.round(explosion*100)+'%';for(const o of objects){const d=o.userData.desc,b=d.position||[0,0,0],v=d.explode||[0,0,0];o.position.set(b[0]+v[0]*explosion,b[1]+v[1]*explosion,b[2]+v[2]*explosion)}content.updateMatrixWorld(true);updateSelectionBox();updateAxis();fitView(null,null,true);requestRender()}
  function visibleBounds(list){content.updateMatrixWorld(true);const box=new T.Box3();box.makeEmpty();for(const o of (list||objects.filter(x=>x.visible))){if(o.geometry.boundingBox)box.union(o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld))}return box}
  function fitView(direction,list,useStepFocus){if(!usable||!objects.length)return;const box=visibleBounds(list);if(box.isEmpty()){announce('目前沒有顯示的零件，請按「恢復全部」。');requestRender();return}announce('');let center=box.getCenter(new T.Vector3()),size=box.getSize(new T.Vector3()),radius=Math.max(size.length()/2,1);if(useStepFocus&&!list&&!isolated&&currentScene&&Array.isArray(currentScene.focus)&&Number(currentScene.viewRadius)>0){center=new T.Vector3(...currentScene.focus);radius=Number(currentScene.viewRadius)*(1+explosion*.8)}let dir=direction?new T.Vector3(...(direction.isVector3?direction.toArray():direction)):camera.position.clone().sub(controls.target);if(dir.lengthSq()<.001)dir=defaultDirection.clone();dir.normalize();const vFov=T.MathUtils.degToRad(camera.fov),hFov=2*Math.atan(Math.tan(vFov/2)*Math.max(camera.aspect,.15)),distance=radius/Math.sin(Math.min(vFov,hFov)/2)*1.12;controls.target.copy(center);camera.position.copy(center).addScaledVector(dir,distance);camera.near=Math.max(.01,distance/2000);camera.far=Math.max(2000,distance*40);camera.updateProjectionMatrix();controls.minDistance=Math.max(.2,radius*.08);controls.maxDistance=radius*80;controls.update();requestRender()}
  function resetView(){isolated=false;selected=null;partsSelect.value='';explodeInput.value='0';showHardware.checked=true;showShell.checked=true;changeExplode();applyVisibility();updateSelection();fitView(defaultDirection,null,true)}
  function selectById(id){selectObject(objects.find(o=>o.userData.desc.id===id)||null)}
  function selectObject(o,notify=true){selected=o;if(o){if(isFastener(o))showHardware.checked=true;if(isShell(o))showShell.checked=true;partsSelect.value=o.userData.desc.id}else{isolated=false;if(partsSelect)partsSelect.value=''}if(partsSelect){applyVisibility();updateSelection()}if(notify&&options.onSelect)options.onSelect(o?{...o.userData.desc}:null);requestRender()}
  function updateSelection(){if(!selectedLabel)return;for(const o of objects){o.material.color.copy(o.userData.baseColor);o.material.emissive.setHex(o===selected?0x2b6549:0);o.material.emissiveIntensity=o===selected?.42:0}selectedLabel.replaceChildren();if(selected){const d=selected.userData.desc,strong=document.createElement('strong');strong.textContent=d.label||d.partId||d.id;selectedLabel.append(strong,document.createTextNode(' · '+(kindLabel[d.kind]||'零件')+(d.partId?' · '+d.partId:'')));if(d.spec)selectedLabel.append(document.createTextNode(' · '+d.spec))}else selectedLabel.textContent='尚未選取。可從底視查看螺母，或把外殼隱藏。';focusButton.disabled=!selected;isolateButton.disabled=!selected;isolateButton.textContent=isolated?'離開單件':'只看選取';allButton.disabled=!objects.length;updateSelectionBox();updateAxis()}
  function updateSelectionBox(){if(!selectionBox)return;selectionBox.visible=!!selected&&selected.visible;if(selected&&selected.visible){selected.updateMatrixWorld(true);selectionBox.box.copy(selected.geometry.boundingBox).applyMatrix4(selected.matrixWorld)}}
  function updateAxis(){if(!axisGroup)return;disposeAxes();if(!selected||!selected.visible||selected.userData.desc.kind!=='screw')return;const d=selected.userData.desc,size=selected.geometry.boundingBox.getSize(new T.Vector3());let axis;if(d.axis&&d.axis.length===3)axis=new T.Vector3(...d.axis).normalize();else{const dims=[size.x,size.y,size.z],index=dims.indexOf(Math.max(...dims));axis=new T.Vector3(index===0?1:0,index===1?1:0,index===2?1:0)}const center=Array.isArray(d.axisOrigin)?new T.Vector3(...d.axisOrigin).add(selected.position.clone().sub(new T.Vector3(...(d.position||[0,0,0])))):selected.geometry.boundingBox.getCenter(new T.Vector3()).add(selected.position);const half=Math.max(size.length()*.8,8),a=center.clone().addScaledVector(axis,-half),b=center.clone().addScaledVector(axis,half),geometry=new T.BufferGeometry().setFromPoints([a,b]),material=new T.LineDashedMaterial({color:0x226e62,dashSize:1.5,gapSize:.7,transparent:true,opacity:.95,depthTest:false});const line=new T.Line(geometry,material);line.computeLineDistances();line.renderOrder=9;axisGroup.add(line)}
  function resize(){if(disposed||!usable||!viewport)return;const rect=viewport.getBoundingClientRect();if(rect.width<1||rect.height<1)return;lastW=Math.round(rect.width);lastH=Math.round(rect.height);renderer.setSize(lastW,lastH,false);camera.aspect=lastW/lastH;camera.updateProjectionMatrix();requestRender()}
  function getState(){return {ready:usable,sceneKey,meshCount:objects.length,visibleCount:objects.filter(x=>x.visible).length,selectedId:selected?selected.userData.desc.id:null,isolated,explodeAmount:explosion,explode:explosion,renderCount,renderedTriangles:renderer?renderer.info.render.triangles:0,cameraPosition:camera?camera.position.toArray():null,target:controls?controls.target.toArray():null,distance:camera&&controls?camera.position.distanceTo(controls.target):0,geometryCacheSize:geometryCache.size,meshPositions:objects.map(o=>({id:o.userData.desc.id,kind:o.userData.desc.kind,partId:o.userData.desc.partId,position:o.position.toArray(),visible:o.visible,isShell:isShell(o),isFastener:isFastener(o)}))}}
  function dispose(){if(disposed)return;disposed=true;if(frame)cancelAnimationFrame(frame);frame=0;if(resizeObserver)resizeObserver.disconnect();for(const remove of listeners)remove();listeners.length=0;if(controls)controls.dispose();if(content){for(const o of objects){content.remove(o);o.material.dispose()}objects=[]}disposeAxes();if(selectionBox){selectionBox.geometry.dispose();selectionBox.material.dispose()}for(const g of geometryCache.values())g.dispose();geometryCache.clear();if(renderer){renderer.dispose();renderer.forceContextLoss()}root.remove();usable=false}
 }
 global.Manual3D={create};
})(window);
