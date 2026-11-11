from pathlib import Path
import re,json
root=Path(__file__).resolve().parents[2]
output=root/'wiring'
source=(output/'開啟我_互動實物接線圖.html').read_text(encoding='utf8')
test=r'''<script>
const checks=[];function check(name,ok){checks.push({name,passed:!!ok});if(!ok)throw Error(name)}
check('97 complete selectable paths',traces.length===97);
let index=wires.findIndex(w=>w.a==='ESP.GPIO21');choose(index);
check('SDA selection reaches OLED through slipring',document.querySelector('#info').textContent.includes('OLED.SDA'));
check('SDA selection reaches PCF through slipring',document.querySelector('#info').textContent.includes('PCF.SDA'));
check('selected path includes slipring internal conductor',document.querySelector('#info').textContent.includes('滑環內部'));
let select=document.querySelector('#group');select.value='sensor';select.dispatchEvent(new Event('change'));
check('group filter',traces.every(t=>t.classList.contains('dim')===(t.dataset.group!=='sensor')));
select.value='all';select.dispatchEvent(new Event('change'));
traces[index].dispatchEvent(new MouseEvent('click',{bubbles:true}));
check('wire click activates selection',document.querySelectorAll('.trace.selected').length>0);
document.querySelector('#clear').click();check('clear selection',document.querySelectorAll('.trace.selected').length===0);
document.querySelector('#plus').click();check('zoom',+svg.getAttribute('viewBox').split(' ')[2]<4400);
document.querySelector('#fit').click();check('fit reset',svg.getAttribute('viewBox')==='0 0 4400 3400');
document.querySelector('#search').value='PCF.P4';document.querySelector('#search').dispatchEvent(new Event('input'));
check('endpoint search',document.querySelectorAll('#list button').length===1);
document.querySelector('#search').value='';document.querySelector('#search').dispatchEvent(new Event('input'));
document.documentElement.setAttribute('data-qa-result',JSON.stringify(checks));
</script>'''
target=root/'.build/pictorial/browser-qa.html'
target.write_text(source.replace('</html>',test+'</html>'),encoding='utf8')
(root/'.build/pictorial/browser-qa-url.txt').write_text(target.as_uri(),encoding='ascii')
print('Prepared offline browser QA')
