/* Connect the reusable 3D viewer to the existing illustrated step guide. */
let preferredFigureMode='3d',modelFailed=false,loadedScene=null;
window.manual3D=null;
function currentHas3D(){return state.step!==20&&Boolean(DATA.model3d?.scenes?.[DATA.steps[state.step].id])}
function sync3DLabel(){
 const wire=state.step===20,active3D=!document.getElementById('model-host').hidden;
 document.querySelector('.figure-label').textContent=wire?'逐腳接線圖概覽':active3D?'可互動 3D 組裝模型':'實際 CAD 組裝示意';
 $('expand-image').textContent=wire?'開啟互動接線圖':active3D?'⛶ 放大 3D':'⛶ 放大圖面';
 $('diagram-open').setAttribute('aria-label',wire?'開啟完整互動接線圖':'放大目前步驟示意圖');
}
function ensure3D(){
 if(window.manual3D||modelFailed)return;
 try{
  window.manual3D=window.Manual3D.create($('model-viewer'),{data:DATA.model3d});
  if(!window.manual3D.ready)modelFailed=true;
 }catch(e){modelFailed=true;window.manual3D=null;}
}
function sync3D(loadScene=false){
 const available=currentHas3D();
 if(available&&preferredFigureMode==='3d')ensure3D();
 const active=available&&!modelFailed&&preferredFigureMode==='3d';
 $('model-host').hidden=!active;
 $('diagram-open').hidden=active;
 $('figure-modes').hidden=state.step===20;
 $('show-3d').disabled=!available||modelFailed;
 $('show-3d').setAttribute('aria-pressed',active);
 $('show-2d').setAttribute('aria-pressed',!active);
 $('model-unavailable').hidden=!modelFailed||!available;
 document.querySelector('.legend').style.display=state.step===20?'none':'flex';
 if(active){
  const key=DATA.steps[state.step].id;
  if(loadedScene!==key){window.manual3D.setScene(key);loadedScene=key;}
  requestAnimationFrame(()=>window.manual3D?.resize());
  $('figure-caption').textContent=DATA.model3d.scenes[key].caption||'拖曳旋轉、滾輪縮放；點選零件或用清單找到螺絲。爆炸間距只供辨識。';
 }
 sync3DLabel();
}
const before3DRender=renderStep;
renderStep=function(){before3DRender();sync3D(true)};
const before3DProgress=progress;
progress=function(){before3DProgress();sync3DLabel()};
const before3DView=setView;
setView=function(view,scroll=true){before3DView(view,scroll);if(view==='steps')requestAnimationFrame(()=>window.manual3D?.resize())};
$('show-3d').onclick=()=>{preferredFigureMode='3d';sync3D()};
$('show-2d').onclick=()=>{preferredFigureMode='2d';before3DRender();sync3D()};
$('expand-image').onclick=()=>{
 if(state.step===20){openWiring();return}
 if($('model-host').hidden){const f=DATA.figures[DATA.steps[state.step].id];openImage(f.src,f.alt||DATA.steps[state.step].title);return}
 $('model-dialog-host').appendChild($('model-viewer'));
 $('model-dialog-title').textContent=DATA.steps[state.step].title+' 3D 模型';
 $('model-dialog').showModal();requestAnimationFrame(()=>window.manual3D?.resize());
};
$('close-model').onclick=()=>$('model-dialog').close();
$('model-dialog').addEventListener('close',()=>{$('model-host').appendChild($('model-viewer'));requestAnimationFrame(()=>window.manual3D?.resize())});
sync3D(true);
