"""Build one offline HTML assembly guide from verified project data and images."""
from pathlib import Path
from collections import Counter
import base64,hashlib,io,json,re
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(__file__).resolve().parent
OUT=ROOT/'manual'
OUT.mkdir(exist_ok=True)
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def image_data(path,limit=1800):
    path=Path(path)
    if not path.is_absolute():
        path=(OUT/path) if str(path).replace('\\','/').startswith('assets/') else ROOT/path
    im=Image.open(path).convert('RGB')
    im.thumbnail((limit,limit))
    stream=io.BytesIO();im.save(stream,'JPEG',quality=88,optimize=True)
    return 'data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode('ascii')

raw=load(SOURCE/'assembly_steps.json')
steps=raw['steps'] if isinstance(raw,dict) else raw
assert len(steps)==22
assert [s['id'] for s in steps]==[f'step-{i:02}' for i in range(1,23)]
manifest=load(ROOT/'3d/parts_manifest.json')
parts=manifest['parts']
for p in parts:p['category']='optional' if p['id'] in {'P10','P11','P12'} else 'test' if p['id']=='P30' else 'standard'
assert len(parts)>0 and len(parts)==len({p['id'] for p in parts})
catalog=load(ROOT/'3d/fastener_catalog.json')
counts={'printTypes':len(parts),'standardTypes':sum(p['category']=='standard' for p in parts),
        'standardPrintQty':sum(p['qty'] for p in parts if p['category']=='standard'),
        'extraPrintQty':sum(p['qty'] for p in parts if p['category']!='standard'),
        'shortScrews':next(x['qty'] for x in catalog['screw_skus'] if x['length_mm']==8),
        'longScrews':next(x['qty'] for x in catalog['screw_skus'] if x['length_mm']==25),
        'nuts':catalog['nut_qty']}
counts['reserveShort']=((counts['shortScrews']+11)//10)*10
counts['reserveLong']=counts['longScrews']+2
counts['reserveNuts']=((counts['nuts']+11)//10)*10
fasteners={x['name']:x for x in catalog['instances']}
expected=Counter(x['name'] for x in catalog['instances'])
allocated=Counter()
for s in steps:
    for key in ('title','summary','parts','hardware','actions','checks','notes','stage'):assert key in s,(s['id'],key)
    for e in s.get('fastenerEntries',[]):
        assert e['code'] in fasteners,e
        allocated[e['code']]+=e['qty']
assert allocated==expected,{'missing':expected-allocated,'extra':allocated-expected}
covered={p['id'] for p in parts if any(any(x==p['id'] or x.startswith(p['id']+' ') or x.startswith(p['id']+'×') or x.startswith(p['id']+' ×') for x in s['parts']) for s in steps)}
assert len(covered)==len(parts),sorted(set(p['id'] for p in parts)-covered)
rawfig=load(OUT/'assets/figure_index.json')
figures=rawfig.get('steps',rawfig.get('figures',rawfig))
if isinstance(figures,list):figures={x.get('step',x.get('id')):x for x in figures}
normalized={}
detail_map={
    'step-01':[('成品總覽',rawfig['overview']),('內部結構',rawfig['cutaway']),('P05列印方向',rawfig['details']['p05Print'])],
    'step-02':[('P02螺母裝入詳圖',rawfig['details']['p02Nuts'])],
    'step-04':[('P05分件爆炸圖',rawfig['details']['p05Exploded']),('螺絲承壓與防脫',rawfig['details']['p05Seat'])],
    'step-05':[('P05分件組裝',rawfig['details']['p05Exploded'])],
    'step-06':[('P04螺母裝入詳圖',rawfig['details']['p04Nuts'])],
    'step-07':[('P04B抬高與2mm間隙','3d/P04B_抬高與2mm間隙.png'),('P06捕捉螺母詳圖',rawfig['details']['p06'])],
    'step-08':[('P06輕調接觸位置',rawfig['details']['p06'])],
    'step-17':[('上殼台階包覆詳圖','3d/P32_台階包覆與接縫.png'),('上殼內側連接詳圖','3d/P32_內側接合與列印方向.png'),('前階段居中比較','3d/P32_居中與分件組裝.png'),('頂部操作位置',rawfig['controls'])],
    'step-22':[('成品總覽',rawfig['overview']),('內部結構',rawfig['cutaway'])],
}
for s in steps:
    f=figures[s['id']]
    f=dict(f)
    path=f.get('path',f.get('image',f.get('file')))
    assert path,(s['id'],f)
    f['src']=image_data(path)
    f.setdefault('alt',s['title'])
    f.setdefault('caption','實際 CAD 示意；零件依圖中方向裝配，爆炸間距不是實際間隙。')
    details=[]
    for d in f.get('details',[])+[{'label':label,'path':path} for label,path in detail_map.get(s['id'],[])]:
        d=dict(d);d['src']=image_data(d.get('path',d.get('image',d.get('file'))));details.append(d)
    f['details']=details;normalized[s['id']]=f
wire=ROOT/'wiring/開啟我_互動實物接線圖.html'
models=load(OUT/'assets/assembly_3d.json')
assert len([key for key in models['scenes'] if key.startswith('step-')])>=21
assert models['validation']['standardPrintInstances']==counts['standardPrintQty']
assert len(models['scenes']['overview']['meshes'])==models['validation']['standardComponents']
for scene in models['scenes'].values():
    assert all(m['geometryKey'] in models['geometries'] for m in scene['meshes'])
preview=ROOT/'wiring/發牌機_實物逐腳接線圖.png'
if not preview.exists():
    preview=next((ROOT/'wiring').glob('*.png'))
data={'version':'V1.0.0','date':'2026-11-11','steps':steps,'parts':parts,'counts':counts,'model3d':models,
      'figures':normalized,'fasteners':fasteners,
      'wiring':base64.b64encode(wire.read_bytes()).decode('ascii'),
      'wiringPreview':image_data(preview,1600)}
template=(SOURCE/'template.html').read_text(encoding='utf8')
payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
html=template.replace('__MANUAL_DATA__',payload)
for key,value in counts.items():
    html=html.replace('__COUNT_'+key+'__',str(value))
def inline_js(path):
    return Path(path).read_text(encoding='utf8').replace('</script','<\\/script')
html=html.replace('__THREE_BUNDLE__',inline_js(OUT/'vendor/three-orbit.min.js'))
html=html.replace('__VIEWER3D_JS__',inline_js(SOURCE/'viewer3d.js'))
html=html.replace('__VIEWER3D_CSS__',(SOURCE/'viewer3d.css').read_text(encoding='utf8'))
html=html.replace('__INTEGRATE3D_JS__',inline_js(SOURCE/'integrate3d.js'))
assert '__MANUAL_DATA__' not in html
assert '__COUNT_' not in html
assert not re.search(r'__(?:VIEWER3D|THREE_BUNDLE|INTEGRATE3D)_?[A-Z_]*__',html)
assert not re.search(r'<(?:script|img|link)\b[^>]*(?:src|href)=["\']https?://',html,re.I)
target=OUT/'發牌機_組裝說明書_V1.0.0.html'
target.write_text(html,encoding='utf8')
report={'version':'V1.0.0','steps':22,'print_part_types':len(parts),'all_part_ids_covered':True,
    'fastener_allocation_matches_current_catalog':True,'screws_M3x8':counts['shortScrews'],'screws_M3x25':counts['longScrews'],'nuts_M3':counts['nuts'],
    'embedded_step_figures':len(normalized),'embedded_wiring_viewer':True,'external_runtime_dependencies':0,
    'interactive_3d_steps':21,'interactive_3d_overview_instances':models['validation']['standardComponents'],
    'interactive_3d_geometry_count':len(models['geometries']),
    'interactive_3d_data_sha256':sha(OUT/'assets/assembly_3d.json'),
    'viewer3d_source_sha256':sha(SOURCE/'viewer3d.js'),
    'three_vendor_sha256':sha(OUT/'vendor/three-orbit.min.js'),
    'cad_source_sha256':sha(ROOT/'3d/source/build_cad.py'),'source_data_sha256':sha(SOURCE/'assembly_steps.json'),
    'html_sha256':sha(target),'bytes':target.stat().st_size,'physical_assembly_tested':False}
(ROOT/'verification/manual_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(report,ensure_ascii=True,indent=2))
