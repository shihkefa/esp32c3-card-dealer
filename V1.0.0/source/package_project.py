"""Check and package the current release without build caches or older releases."""
from pathlib import Path
from datetime import datetime
import csv
import hashlib
import json
import re
import struct
import zipfile
import xml.etree.ElementTree as ET
from pypdf import PdfReader

root=Path(__file__).resolve().parents[1]
version=(root/'VERSION.txt').read_text(encoding='ascii').strip()
assert re.fullmatch(r'V\d+\.\d+\.\d+',version)
def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()
def load(file):return json.loads(file.read_text(encoding='utf-8-sig'))
def save(file,data):file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

migration=load(root/'verification/migration_checks.json')
assert migration['version']==version and migration['visual_review_passed']
meshes=list((root/'3d/STL').glob('*.stl'))
assert len(meshes)==40
assert not (root/'3d/STL/P32.stl').exists()
assert not (root/'3d/OpenSCAD/P32.scad').exists()
assert {'P32A.stl','P32B.stl'}<={p.name for p in meshes}
assert not (root/'3d/STL/P02.stl').exists()
assert not (root/'3d/STL/P04.stl').exists()
assert not (root/'3d/OpenSCAD/P04.scad').exists()
assert not (root/'3d/STL/P05.stl').exists()
assert not (root/'3d/OpenSCAD/P05.scad').exists()
assert {'P02A.stl','P02B.stl','P03.stl','P04A.stl','P04B.stl','P05A.stl','P05B.stl','P06.stl'}<={p.name for p in meshes}
for obsolete_p05 in ('P05_入口尺寸與列印方向.png','P05_工具入口參考.png',
                     'P05_短臂工具換位步驟.png','P05_螺絲螺母裝入圖.png','P05_直工具鎖付順序.png',
                     'P05_螺絲螺母裝配.txt'):
    assert not (root/'3d'/obsolete_p05).exists(),obsolete_p05
assert (root/'3d/P05_分件與閉合夾座裝配.txt').is_file()
for expected_p05 in ('P05_分件組裝與閉合夾座.png','P05_L工具鎖付順序.png',
                     'P05_完整承壓與防脫剖示.png','P05_列印方向.png','P05B_平面貼床與削角.png',
                     'P05A_P05B_平口配合.png'):
    assert (root/'3d'/expected_p05).is_file(),expected_p05
for file in meshes:
    assert sha(file)==migration['print_mesh_sha256'][file.name]
    raw=file.read_bytes();assert len(raw)==84+50*struct.unpack_from('<I',raw,80)[0]
assert sha(root/f'發牌機_整機組裝_{version}.stl')==migration['assembly_sha256']
assert len(list((root/'3d/OpenSCAD').glob('*.scad')))==40
assert len(load(root/'3d/parts_manifest.json')['parts'])==40
assert load(root/'3d/fastener_validation.json')['all_passed']
assert load(root/'3d/fastener_validation.json')['total_nut_qty']==52
assert load(root/'3d/fastener_validation.json')['screw_skus']=={'DIN7991 M3x8':61,'DIN7991 M3x25':10}
assert load(root/'3d/virtual_assembly_report.json')['summary']['all_passed']
p08=load(root/'3d/p08_hopper_validation.json')
assert p08['all_passed'] and len(p08['checks'])>=16 and all(c['passed'] for c in p08['checks'])
for image in ('P08_封底高側板與上蓋齊平.png','P08_底面盲槽與滾輪開口.png','P08_P12中央掛架配合.png'):
    assert (root/'3d'/image).is_file()
assert load(root/'3d/p02_split_validation.json')['all_passed']
assert load(root/'3d/p04_split_validation.json')['all_passed']
assert (root/'3d/P04B_抬高與2mm間隙.png').is_file()
assert (root/'3d/P04B_完整60齒檢查.png').is_file()
p04_checks={check['test']:check for check in load(root/'3d/p04_split_validation.json')['checks']}
for required_tooth_check in (
    'All 60 CAD teeth retain the complete pristine profile over full height',
    'Complete P04B matches independent gear journal and own-interface reference',
    'Exported P04B STL roundtrip retains all 60 full-height tooth profiles',
    'Negative control rejects the legacy N20 pocket at tooth index35 angle210deg'):
    assert p04_checks[required_tooth_check]['passed']
for report_name,script_name in [('p04_split_validation.json','check_p04_split.py'),
                                ('p08_hopper_validation.json','check_p08_hopper.py'),
                                ('fastener_validation.json','check_fasteners.py')]:
    checked_sources=load(root/'3d'/report_name)['source_hashes']
    assert checked_sources['build_cad_py_sha256']==sha(root/'3d/source/build_cad.py')
    assert checked_sources['design_params_json_sha256']==sha(root/'3d/source/design_params.json')
    assert checked_sources['check_script_sha256']==sha(root/'3d/source'/script_name)
assert load(root/'3d/p05_fastener_validation.json')['all_passed']
assert load(root/'3d/p32_split_validation.json')['all_passed']
p32_sources=load(root/'3d/p32_split_validation.json')['source_hashes']
assert p32_sources['build_cad_py_sha256']==sha(root/'3d/source/build_cad.py')
assert p32_sources['check_script_sha256']==sha(root/'3d/source/check_p32_split.py')
assert (root/'3d/P32_居中與分件組裝.png').is_file()
assert (root/'3d/P32_台階包覆與接縫.png').is_file()
p05_sources=load(root/'3d/p05_fastener_validation.json')['source_hashes']
assert p05_sources['build_cad_py_sha256']==sha(root/'3d/source/build_cad.py')
assert p05_sources['check_script_sha256']==sha(root/'3d/source/check_p05_fasteners.py')

manual=root/'manual/發牌機_組裝說明書_V1.0.0.html'
manual_data=load(root/'verification/manual_validation.json')
manual_browser=load(root/'verification/manual_browser_checks.json')
assert manual_data['steps']==22 and manual_data['print_part_types']==40
assert manual_data['fastener_allocation_matches_current_catalog']
assert manual_data['html_sha256']==sha(manual)==manual_browser['html_sha256']
assert manual_data['cad_source_sha256']==sha(root/'3d/source/build_cad.py')
assert manual_data['source_data_sha256']==sha(root/'source/manual/assembly_steps.json')
assert manual_browser['passed'] and not manual_browser['externalRequests'] and not manual_browser['pageErrors']
manual_3d=load(root/'verification/manual_3d_browser_checks.json')
assert manual_data['interactive_3d_steps']==21 and manual_data['interactive_3d_overview_instances']==215
assert manual_data['interactive_3d_data_sha256']==sha(root/'manual/assets/assembly_3d.json')
manual_3d_sources=load(root/'manual/assets/assembly_3d.json')['sourceHashes']
assert manual_3d_sources['buildCad']==sha(root/'3d/source/build_cad.py')
assert manual_3d_sources['exportScript']==sha(root/'source/manual/export_manual_3d.py')
assert manual_data['viewer3d_source_sha256']==sha(root/'source/manual/viewer3d.js')
assert manual_data['three_vendor_sha256']==sha(root/'manual/vendor/three-orbit.min.js')
assert manual_3d['passed'] and manual_3d['html_sha256']==sha(manual)
assert (root/'manual/vendor/THREE_LICENSE.txt').is_file()

firmware=load(root/'firmware/verification.json')
assert firmware['version']==version and firmware['target_compile']['passed']
assert all(sha(root/'firmware/CardDealer'/name)==digest
           for name,digest in firmware['core_tests']['unchanged_source_sha256'].items())
assert sha(root/'firmware/tests/core_tests.cpp')==firmware['core_tests']['test_source_sha256']
merged=(root/'firmware/bin/CardDealer.ino.merged.bin').read_bytes()
app=(root/'firmware/bin/CardDealer.ino.bin').read_bytes()
assert len(merged)==4*1024*1024 and merged[0x10000:0x10000+len(app)]==app
assert b'CARD DEALER '+version.encode() in app
assert sha(root/f'發牌機_{version}_整合燒錄.bin')==hashlib.sha256(merged).hexdigest()
assert set(merged[0x9000:0xe000])=={255}  # Explicitly documented NVS reset.

board=(root/'firmware/CardDealer/BoardConfig.h').read_text(encoding='utf8')
for name,pin in {'kFeedIn1':5,'kFeedIn2':6,'kEjectIn1':7,'kExitPin':10,'kSda':21,'kScl':20,'kHomePcfBit':4}.items():
    assert re.search(r'\b'+name+r'\s*=\s*'+str(pin)+r'\s*;',board)
with (root/'firmware/docs/滑環12路接線.csv').open(encoding='utf-8-sig',newline='') as f:slip=list(csv.DictReader(f))
assert len(slip)==12 and slip[9]['旋轉端']=='PCF8574 P4'

wiring=root/'wiring'
wires=load(wiring/'逐線端點與路徑.json');parts=load(wiring/'板型與焊孔位置.json')
assert len(wires)==97
pins={name+'.'+pin:xy[:2] for name,part in parts.items() for pin,xy in part['pins'].items()}
for i in range(12):
    pins[f'SR{i+1:02}.F']=[1960,1050+i*95];pins[f'SR{i+1:02}.R']=[2270,1050+i*95]
for wire in wires:
    assert wire['points'][0]==pins[wire['a']] and wire['points'][-1]==pins[wire['b']]
svg=ET.parse(wiring/'發牌機_實物逐腳接線圖.svg')
assert sum(e.attrib.get('class')=='trace' for e in svg.iter())==97
pdfs={'發牌機_實物逐腳接線圖_A1.pdf':1,'指定板型與觀看方向_A4.pdf':4}
for name,count in pdfs.items():
    reader=PdfReader(wiring/name)
    assert len(reader.pages)==count
    assert version in '\n'.join(page.extract_text() for page in reader.pages)
browser=load(wiring/'互動圖_瀏覽器驗證.json')
assert browser['passed'] and len(browser['checks'])==10
scripts=re.findall(r'<script\b[^>]*>(.*?)</script>',(wiring/'開啟我_互動實物接線圖.html').read_text(encoding='utf8'),re.S)
assert hashlib.sha256('\n'.join(scripts).encode()).hexdigest()==browser['viewer_javascript_sha256']
wire_report=load(wiring/'verification.json')
wire_report['pdf_page_counts']=pdfs
wire_report['browser_tests']={'passed':True,'checks':10,'previous_result_reused_for_identical_javascript':True}
wire_report['hashes']={p.name:sha(p) for p in sorted(wiring.iterdir()) if p.is_file() and p.name!='verification.json'}
save(wiring/'verification.json',wire_report)

book=root/f'發牌機_BOM_{version}.xlsx'
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(book) as z:
    assert z.testzip() is None
    sheets=[name for name in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name)]
    assert len(sheets)==3
    formula_count=0;summary={}
    for name in sheets:
        tree=ET.fromstring(z.read(name))
        for cell in tree.findall('.//m:sheetData/m:row/m:c',ns):
            assert cell.get('t')!='e',(name,cell.get('r'))
            formula_count+=cell.find('m:f',ns) is not None
            if name.endswith('sheet1.xml') and cell.get('r') in {'B7','E6','H7'}:
                summary[cell.get('r')]=float(cell.find('m:v',ns).text)
    bom_scope=load(root/'verification/bom-scope-validation.json')
    assert bom_scope['all_passed'] and bom_scope['printed_types']==40
    assert summary=={'E6':bom_scope['summary_CNY']['external'],
                     'B7':bom_scope['summary_CNY']['total'],
                     'H7':bom_scope['summary_CNY']['external']+bom_scope['summary_CNY']['shipping']}
    assert formula_count>=200
    assert len(ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('m:hyperlinks/m:hyperlink',ns))==21

excluded={'.build','.build-temp','.build-tests','__pycache__','node_modules'}
files=[p for p in sorted(root.rglob('*')) if p.is_file() and not p.name.startswith('~$')
       and not excluded.intersection(p.relative_to(root).parts)]
obsolete=re.compile(r'(?<![A-Za-z0-9])(?:FW[0-9]+\.[0-9]+|W[0-9]+\.[0-9]+|V0\.[0-9]+)')
text_ext={'.txt','.csv','.json','.py','.mjs','.ino','.h','.cpp','.scad','.ps1','.html','.svg','.md','.ndjson','.log'}
for file in files:
    assert not obsolete.search(file.relative_to(root).as_posix()),file
    # Manufacturer documents are retained verbatim, including their own versions.
    if file.is_relative_to(root/'source/references'):
        continue
    if file.suffix in text_ext:
        assert not obsolete.search(file.read_text(encoding='utf-8-sig')),file
    elif file.suffix=='.xlsx':
        with zipfile.ZipFile(file) as z:
            assert all(not obsolete.search(z.read(n).decode('utf8')) for n in z.namelist() if n.endswith('.xml'))
    elif file.suffix=='.pdf':
        assert all(not obsolete.search(p.extract_text()) for p in PdfReader(file).pages)

hashes={p.relative_to(root).as_posix():sha(p) for p in files if p.name not in {'SHA256SUMS.txt'} and p!=root/'verification.json'}
summary_report={'version':version,'generated_at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'firmware':firmware,'cad':{'print_types':40,'assembly_mesh_unchanged':False,'hardware_reference_only':True,
        'design_change':migration['design_change'],'p02_split_checks':migration['p02_split_checks'],
        'p04_split_checks':load(root/'3d/p04_split_validation.json'),
        'p05_fastener_checks':load(root/'3d/p05_fastener_validation.json'),
        'p32_split_checks':load(root/'3d/p32_split_validation.json'),
        'p08_hopper_checks':load(root/'3d/p08_hopper_validation.json'),
        'mechanical_refit_required':migration['mechanical_refit_required']},
    'wiring':{'complete_paths':97,'pdf_pages':pdfs,'viewer_javascript_unchanged':True},
    'bom':{'sheets':3,'formulas':formula_count,'native_links':21,'external_materials':summary['E6'],'with_shipping':summary['H7'],'with_filament':summary['B7']},
    'manual':{'validation':manual_data,'browser_checks':manual_browser,'interactive_3d_checks':manual_3d},
    'visual_review_passed':True,'older_project_version_tokens':0,'sha256':hashes}
save(root/'verification.json',summary_report)
hashes['verification.json']=sha(root/'verification.json')
(root/'SHA256SUMS.txt').write_text(''.join(f'{digest}  {name}\n' for name,digest in sorted(hashes.items())),encoding='utf8')
archive=root.parent/f'發牌機_完整專案_{version}.zip'
temporary_archive=archive.with_suffix('.tmp.zip')
with zipfile.ZipFile(temporary_archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for file in sorted(root.rglob('*')):
        if file.is_file() and not file.name.startswith('~$') and not excluded.intersection(file.relative_to(root).parts):
            z.write(file,Path(version)/file.relative_to(root))
with zipfile.ZipFile(temporary_archive) as z:
    assert z.testzip() is None
    for name,digest in hashes.items():assert hashlib.sha256(z.read(version+'/'+name)).hexdigest()==digest
    entries=len(z.namelist())
temporary_archive.replace(archive)
print(json.dumps({'archive':str(archive),'entries':entries,'bytes':archive.stat().st_size,
    'sha256':sha(archive),'version':version,'all_checks_passed':True},ensure_ascii=True,indent=2))
