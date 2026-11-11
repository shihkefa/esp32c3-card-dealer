"""Export exact CAD component triangles for the offline assembly guide.

No source solids or printable STLs are changed. Positions are millimetres in
the existing assembly frame; each local geometry is recentered for the viewer.
Explode vectors are visual separation only, never a claimed insertion path.
"""
from pathlib import Path
from collections import Counter,defaultdict
import base64,csv,hashlib,json,math,sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'3d/source'))
import build_cad as c

OUT=ROOT/'manual/assets/assembly_3d.json'
OUT.parent.mkdir(parents=True,exist_ok=True)
COLORS={'context':'#b6c1bf','print':'#df8748','screw':'#668595','nut':'#c29a55','hardware':'#54818b'}
SHELLS={'P01','P02A','P32A','P32B','P33','P34'}
part_defs={p.id:p for p in c.parts}
fastener_defs={r['name']:r for r in c.fastener_registry}
with (ROOT/'3d/五金數量表.csv').open(encoding='utf-8-sig',newline='') as f:
    fastener_usage={r['模型名稱']:r['位置/用途'] for r in csv.DictReader(f)}

hardware_labels={
 '6005ZZ':'6005ZZ 主轉盤軸承','28BYJ-48':'28BYJ-48 步進馬達','stepper_output':'28BYJ-48 輸出D軸',
 'lower623':'下滾輪 623ZZ 軸承','upper623':'上滾輪 623ZZ 軸承',
 'lower3mmshaft':'下滾輪 3mm 鋼軸','upper3mmshaft':'上滾輪 3mm 鋼軸',
 'N20':'N20 減速取牌馬達','RF300':'RF300 長軸出牌馬達',
 'slipring_rotor':'12路滑環旋轉段','slipring_flange':'滑環固定法蘭',
 'silicone':'出牌輪 O 型圈','feedrubber':'取牌輪 O 型圈','batteryholder':'18650 電池盒',
 '18650':'18650 電芯','ESP32C3':'ESP32-C3 SuperMini','PCF8574':'PCF8574 I/O 模組',
 'charger':'TP4056 Type-C 充電板','TypeC':'充電板 Type-C 插座','booster':'5V 升壓板',
 'protection1S':'單節鋰電池保護板','ULN2003':'ULN2003 步進驅動板',
 'screenpcb':'SSD1306 OLED 電路板','OLEDglass':'OLED 顯示面','screenheader':'OLED 焊孔接腳參考',
 'keypcb':'四鍵電路板','keybody':'輕觸按鍵本體','keyplunger':'輕觸按鍵推桿',
 'powerrocker':'總電源開關','home_opto':'旋轉參考槽型光電','exit_opto':'出口計數槽型光電',
 'DRV8833':'DRV8833 雙馬達驅動板','separatorpad':'分牌摩擦墊',
}

def rgb(color):
    return '#'+''.join(f'{int(v):02x}' for v in color)

def tilted_point(point):
    x,y,z=point; a=math.radians(c.P['hopper_tilt_deg'])
    z-=c.P['card_floor_z_mm']
    return [x*math.cos(a)+z*math.sin(a),y,-x*math.sin(a)+z*math.cos(a)+c.P['card_floor_z_mm']+c.P['hopper_lift_mm']]

def tilted_axis(axis):
    x,y,z=axis;a=math.radians(c.P['hopper_tilt_deg'])
    return [x*math.cos(a)+z*math.sin(a),y,-x*math.sin(a)+z*math.cos(a)]

# Explicit head origins and rotations follow the shw calls in build_cad.py.
# A flat_screw is authored from its head plane towards +Z. No bbox/PCA axis
# guessing is used; verification below compares both projected end planes.
screw_poses={}
def poses(name,points,axis=(0,0,-1),tilt=False):
    origins=[tilted_point(p) if tilt else list(p) for p in points]
    # CAD applies the global head translation after inclination. Keep these
    # explicit screw head origins in the same frame as the exported triangles.
    if name in c.RAISED_HARDWARE:
        for point in origins:point[2]+=c.UPPER_LIFT
    screw_poses[name]=[{'axis':tilted_axis(axis) if tilt else list(axis),
                        'axisOrigin':origin} for origin in origins]

poses('hatchM3x8',[(x,-98.2,z) for x,z in [(-32,46.5),(72,46.5),(-32,120),(72,120)]],(0,1,0))
poses('frontM3x8',[(103.2,y,51.2) for y in [-44,44]],(-1,0,0))
poses('hoodJoinM3x8',[(x,y,getattr(c,'HOOD_JOIN_HEAD_Z',118.5)) for x,y in getattr(c,'HOOD_JOIN_MOUNTS',[(-56,-50.5),(-18,-50.5),(20,-50.5),(64,-50.5)])],(0,0,1))
poses('hoodM3x8',[(x,y,42) for x,y in c.HOUSING_MOUNTS],(0,0,1))
poses('oledM3x8',[(x,y,119.5) for x,y in c.OLED_MOUNTS],(0,0,1))
poses('keysM3x8',[(x,y,113.4) for x,y in c.KEY_MOUNTS],(0,0,1))
poses('slipM3x8',[(26.5*math.cos(math.radians(a)),26.5*math.sin(math.radians(a)),5.5) for a in [0,120,240]],(0,0,1))
poses('rotorM3x8',[(-19,0,15.5)],(1,0,0))
poses('deckM3x8',[(x,y,45.4) for x,y in c.P04_MOUNTS])
poses('pinionM3x8',[(c.P05_HEAD_X,c.P05_CLAMP_Y,c.P05_CLAMP_Z)],(-1,0,0))
poses('pinionJoinM3x8',[(x,y,40) for x,y in c.P05_JOIN_MOUNTS])
poses('stepperM3x8',[(47,y,32.7) for y in [-17.5,17.5]])
poses('baseM3x25',[(x,y,33) for x in [-68,68] for y in [-58,58]])
poses('retainerM3x8',[(28.5*math.cos(math.radians(a)),28.5*math.sin(math.radians(a)),35) for a in [30,150,270]])
poses('hopperM3x25',[(x,y,64) for x in [-45,31] for y in [-26,26]],tilt=True)
poses('adapterM3x8',[(x,y,48.9) for x in [-45,31] for y in [-44,44]])
poses('pillowM3x8',[(x,y,51.4) for y in [-35,35] for x in [52.5,69.5]],tilt=True)
poses('adjustM3x8',[(61,y,88.75) for y in [-35,35]],tilt=True)
poses('guideM3x8',[(76,y,60) for y in [-35,35]],(-1,0,0),tilt=True)
poses('n20baseM3x8',[(x,-19,48.4) for x in [-33,-12]],tilt=True)
poses('rfclampM3x25',[(x,-74.3,68.2) for x in [46.5,75.5]],tilt=True)
poses('n20clampM3x8',[(x,-11,62.2) for x in [-30.4,-13.6]],tilt=True)
poses('photoM3x8',[(81,27,63.7)],tilt=True)
poses('flagM3x8',[(-58,10,40.6)],(0,0,1))
poses('homeM3x8',[(-63.5,10,27)],(0,0,1))
poses('gateM3x8',[(39.5,y,72) for y in [-37.5,37.5]],(1,0,0),tilt=True)
poses('wheelM3x8',[(66,0,z+3.2) for z in [54.2,74.75]],tilt=True)
poses('feedM3x8',[(-17,8,57.2)],tilt=True)
poses('couplerM3x8',[(66,y,57.4) for y in [-55.3,-44.8]],tilt=True)

geometries={}; records={}; grouped=defaultdict(list); source_shapes={}; geometry_signatures={}; axis_checks=[]

def add_record(name,shape,color,kind='hardware',label=None,part_id=None,pose=None):
    number=len(grouped[name])+1
    rid=f'{name}.{number}'
    mesh=c.tm(shape)
    vertices=np.asarray(mesh.vertices,dtype=np.float64)
    faces=np.asarray(mesh.faces,dtype=np.uint32)
    center=(vertices.min(axis=0)+vertices.max(axis=0))/2
    local=np.asarray(vertices-center,dtype='<f4')
    indices=np.asarray(faces.reshape(-1),dtype='<u4')
    assert len(indices)%3==0 and indices.max()<len(local)
    assert np.isfinite(local).all()
    signature=hashlib.sha256(local.tobytes()+indices.tobytes()).hexdigest()
    key=geometry_signatures.get(signature)
    if key is None:
        key=f'g{len(geometries)+1:03}'
        geometry_signatures[signature]=key
        geometries[key]={'positionsB64':base64.b64encode(local.tobytes()).decode('ascii'),
                         'indicesB64':base64.b64encode(indices.tobytes()).decode('ascii'),
                         'vertexCount':len(local),'indexCount':len(indices)}
    entry={'id':rid,'label':label or name,'partId':part_id or name,'kind':kind,
           'geometryKey':key,'color':rgb(color) if not isinstance(color,str) else color,
           'position':center.round(7).tolist(),'explode':[0,0,0],'highlight':False,
           'isShell':(part_id or name) in SHELLS,'isFastener':kind in {'screw','nut'},'instance':number,
           'triangleCount':len(faces)}
    if pose:
        entry.update(pose)
        entry['axisSource']='Explicit CAD head origin and head-to-tip rotation including 6deg deck tilt'
        projections=(vertices-np.asarray(pose['axisOrigin']))@np.asarray(pose['axis'])
        length=fastener_defs[name]['length_mm']
        entry['screwLengthMm']=length
        max_error=max(abs(float(projections.min())),abs(float(projections.max())-length))
        assert max_error<.0001,(rid,max_error)
        axis_checks.append({'id':rid,'axis':pose['axis'],'head_to_tip_mm':length,'maximum_end_plane_error_mm':round(max_error,9)})
    records[rid]=entry;grouped[name].append(rid);source_shapes[rid]=shape
    return rid

for pid,name,shape,color in c.assembly_printables():
    add_record(pid,shape,color,'print',f'{pid} {name}',pid)
for name,shape,color in c.hardware:
    if name in {'cards','cardedge'}:continue
    spec=fastener_defs.get(name)
    if spec:
        kind=spec['kind']
        label=(f"M3×{spec['length_mm']} 螺絲" if kind=='screw' else '標準M3螺母')+' · '+fastener_usage.get(name,name)
    else:
        kind='hardware';label=hardware_labels.get(name,name)
    index=len(grouped[name])
    pose=screw_poses[name][index] if kind=='screw' else None
    add_record(name,shape,color,kind,label,pose=pose)

standard_ids=list(records)
standard_print_count=sum(records[r]['kind']=='print' for r in standard_ids)
standard_hardware_count=len(standard_ids)-standard_print_count
formal_screw_count=sum(records[r]['kind']=='screw' for r in standard_ids)
formal_nut_count=sum(records[r]['kind']=='nut' for r in standard_ids)
assert len(axis_checks)==formal_screw_count

# Optional/test component shapes retain the exact orientation in their proper
# assembly coordinate system, apart from the explicitly arranged trial coupon.
for pid in ['P10','P11','P12','P30']:
    for idx in range(part_defs[pid].qty):
        shape=part_defs[pid].shape
        if pid=='P12' and idx==1:shape=shape.rot(z=180).move(x=-8)
        shape=c.assembly_pose(pid,shape)
        add_record(pid,shape,part_defs[pid].color,'print',f'{pid} {part_defs[pid].name}',pid)

for length,x in [(8,42),(25,58)]:
    rid=add_record(f'trialM3x{length}',c.flat_screw(length).move(x,0,0),COLORS['screw'],
                   'screw',f'M3×{length} 螺絲 · 備料試配')
    records[rid].update({'axis':[0,0,1],'axisOrigin':[x,0,0],'screwLengthMm':length,
                        'axisSource':'Explicit CAD trial screw translation, head towards +Z'})
add_record('trialM3nut',c.hex_nut3(42,18,0),COLORS['nut'],'nut','標準M3螺母 · 備料試配')

scenes={}
def members(names):
    if isinstance(names,str):names=[names]
    return [rid for name in names for rid in grouped[name]]

def scene(sid,names,new=(),explode=None,camera=(1.2,-1.7,1.4),focus=None,view_radius=None,caption=None):
    ids=[]
    for name in names:
        ids.extend(grouped[name] if name in grouped else [name])
    assert len(ids)==len(set(ids)),(sid,'duplicate mesh')
    additions=set(new);explode=explode or {};meshes=[]
    for rid in ids:
        src=records[rid]
        name=rid.rsplit('.',1)[0]
        e=dict(src)
        e['highlight']=name in additions or rid in additions
        if not e['highlight']:
            e['color']=COLORS['context'] if e['kind']=='print' else src['color']
        else:
            e['color']=COLORS[e['kind']]
        vector=explode.get(rid,explode.get(name,[0,0,0]))
        if callable(vector):vector=vector(e)
        e['explode']=[round(float(x),7) for x in vector]
        meshes.append(e)
    result={'meshes':meshes,'camera':list(camera),
            'caption':caption or '實際CAD元件；爆炸位移只供辨識，不表示實際組裝間隙或允許行程。'}
    if focus is not None:result['focus']=list(focus)
    if view_radius is not None:result['viewRadius']=view_radius
    scenes[sid]=result

def along_axis(e,magnitude=18):return np.asarray(e.get('axis',[0,0,1]))*-magnitude
def radial(e,magnitude=16,z=0):
    v=np.asarray(e['position'][:2]);norm=np.linalg.norm(v)
    return [*(v/max(norm,.01)*magnitude),z]
def side_y(e,magnitude=18):return [0,magnitude*(-1 if e['position'][1]<0 else 1),0]

scene('step-01',['P30','trialM3x8','trialM3x25','trialM3nut'],
      new=['P30','trialM3x8','trialM3x25','trialM3nut'],camera=(.5,-1.8,1.8),focus=(15,0,7),view_radius=55,
      caption='P30試配片與兩種螺絲為實際CAD幾何，為方便備料而排列；試配五金稍後重用於正式位置。')
scene('step-02',['P02A','P02B','P03','6005ZZ','retainerM3x8','retainerM3nut'],
      new=['P02B','P03','6005ZZ','retainerM3x8','retainerM3nut'],
      explode={'P02B':[0,0,-24],'P03':[0,0,22],'6005ZZ':[0,0,-7],'retainerM3x8':[0,0,38],'retainerM3nut':[0,0,-24]},
      focus=(0,0,30),view_radius=55)
scene('step-03',['P02A','28BYJ-48','stepper_output','stepperM3x8','stepperM3nut'],
      new=['28BYJ-48','stepper_output','stepperM3x8','stepperM3nut'],
      explode={'28BYJ-48':[0,0,-22],'stepper_output':[0,0,-22],'stepperM3x8':[0,0,22],'stepperM3nut':[0,0,-22]},
      camera=(1.1,-1.65,-1.1),focus=(52,0,26),view_radius=45)
scene('step-04',['P02A','28BYJ-48','stepper_output','stepperM3x8','stepperM3nut','P05B','pinionM3x8','pinionM3nut'],
      new=['P05B','pinionM3x8','pinionM3nut'],
      explode={'P05B':[0,0,15],'pinionM3x8':[20,0,15],'pinionM3nut':[0,20,15]},
      camera=(1.1,1.5,1.2),focus=(54,4,34),view_radius=28,
      caption='先完成P02A及馬達，再鎖P05B；此步沒有P05A和P04，以保留L型工具操作空間。工具實際路徑請對照2D詳圖。')
scene('step-05',['P02A','28BYJ-48','stepper_output','P05B','P05A','pinionM3x8','pinionM3nut','pinionJoinM3x8','pinionJoinM3nut'],
      new=['P05A','pinionJoinM3x8','pinionJoinM3nut'],
      explode={'P05A':[0,0,26],'pinionJoinM3x8':[0,0,42],
               'pinionJoinM3nut':lambda e:[-18 if e['position'][0]<54 else 18,0,0]},
      camera=(1.2,1.6,1.3),focus=(54,0,36),view_radius=32,
      caption='P05A內腔平口對應P05B；可隱藏P05A或旋到底面查看0.2mm名義側隙與防脫裙邊。')
scene('step-06',['P04A','P04B','deckM3x8','deckM3nut'],new=['P04A','deckM3x8','deckM3nut'],
      explode={'P04A':[0,0,24],'deckM3x8':[0,0,40],'deckM3nut':[0,0,-16]},
      camera=(1.0,-1.6,1.3),focus=(0,0,37),view_radius=75,
      caption='P04B齒輪上側加厚1.5mm至7.5mm，原P04A承載盤沿用；四支M3×8及四顆螺母仍由原方向裝入。')
scene('step-07',['P02A','P02B','P03','6005ZZ','P04A','P04B','deckM3x8','deckM3nut','P06','rotorM3nut'],
      new=['P04A','P04B','deckM3x8','deckM3nut','P06','rotorM3nut'],
      explode={'P04A':[0,0,26],'P04B':[0,0,26],'deckM3x8':[0,0,26],'deckM3nut':[0,0,26],
               'P06':[0,0,-24],'rotorM3nut':[0,0,-24]},
      camera=(-1.3,-1.7,.8),focus=(0,0,25),view_radius=63,
      caption='P04A與P02A圓環名義間隙改為2mm；軸承肩臺及P06高度保留。P06螺母先預放，再由空心軸底部套入，暫不突出徑向螺絲。')
scene('step-08',['P04B','P06','6005ZZ','slipring_rotor','slipring_flange','rotorM3x8','rotorM3nut'],
      new=['slipring_rotor','slipring_flange','rotorM3x8'],
      explode={'slipring_rotor':[0,0,-30],'slipring_flange':[0,0,-30],'rotorM3x8':[-20,0,0]},
      camera=(-1.4,-1.6,.6),focus=(0,0,19),view_radius=45,
      caption='滑環由下方穿入。P06螺絲只輕調至接觸轉子，不能把爆炸距離或0.6mm頭部避讓當成允許壓入量。')
scene('step-09',['P02A','P04A','P25','P26','home_opto','homeM3x8','flagM3x8','flagM3nut'],
      new=['P25','P26','home_opto','homeM3x8','flagM3x8','flagM3nut'],
      explode={'P25':[-12,0,-5],'home_opto':[-12,0,8],'P26':[0,0,15],
               'homeM3x8':[-12,0,-15],'flagM3x8':[0,0,-12],'flagM3nut':[0,0,27]},
      camera=(-1.3,-1.8,1.3),focus=(-66,10,34),view_radius=30,
      caption='使用向下延長1.5mm的P26；支臂隨轉盤抬升，但遮光薄片下緣仍為Z35.6，P25與光電感測器維持原高度。')
scene('step-10',['P04A','P31','adapterM3x8','adapterM3nut'],new=['P31','adapterM3x8','adapterM3nut'],
      explode={'P31':[0,0,22],'adapterM3x8':[0,0,40],'adapterM3nut':[0,0,-12]},
      focus=(15,-5,55),view_radius=90)
scene('step-11',['P16','P15','lower3mmshaft','upper3mmshaft','silicone','lower623','upper623','wheelM3x8','wheelM3nut'],
      new=['P16','P15','lower623','upper623','wheelM3x8','wheelM3nut'],
      explode={'lower623':lambda e:side_y(e,22),'upper623':lambda e:side_y(e,22),
               'wheelM3x8':lambda e:along_axis(e,16),'wheelM3nut':[0,0,-14],
               'P15':lambda e:side_y(e,22)},
      camera=(1.6,-1.3,1.2),focus=(60,-2,68),view_radius=65)
scene('step-12',['P31','P13','P14','P15','P16','lower3mmshaft','upper3mmshaft','silicone','lower623','upper623','wheelM3x8','wheelM3nut','pillowM3x8','pillowM3nut','adjustM3x8'],
      new=['P13','P14','P15','pillowM3x8','pillowM3nut','adjustM3x8'],
      explode={'P13':lambda e:side_y(e,20),'P14':lambda e:side_y(e,20),'P15':lambda e:side_y(e,20),
               'pillowM3x8':[0,0,22],'pillowM3nut':[0,0,-12],'adjustM3x8':[0,0,24]},
      camera=(1.5,-1.6,1.25),focus=(60,0,64),view_radius=80)
scene('step-13',['P31','P17','P18','P19','N20','feedrubber','feedM3x8','feedM3nut','n20baseM3x8','n20clampM3x8']+grouped['motorbaseM3nut'][:2],
      new=['P17','P18','P19','N20','feedrubber','feedM3x8','feedM3nut','n20baseM3x8','n20clampM3x8']+grouped['motorbaseM3nut'][:2],
      explode={'P19':[0,0,18],'N20':[0,0,7],'P17':[0,17,0],'feedrubber':[0,17,0],
               'feedM3x8':[0,17,13],'feedM3nut':[0,17,-10],'n20baseM3x8':[0,0,11],'n20clampM3x8':[0,0,32]},
      camera=(-1.2,-1.7,1.5),focus=(-20,-8,64),view_radius=45)
scene('step-14',['P31','P16','lower3mmshaft','P20','P21','P22','RF300','couplerM3x8','couplerM3nut','rfclampM3x25']+grouped['motorbaseM3nut'][2:],
      new=['P20','P21','P22','RF300','couplerM3x8','couplerM3nut','rfclampM3x25']+grouped['motorbaseM3nut'][2:],
      explode={'P21':[0,0,20],'P22':[0,0,12],'RF300':[0,-22,0],'rfclampM3x25':[0,0,38],
               'couplerM3x8':lambda e:along_axis(e,22),'couplerM3nut':[0,0,-14]},
      camera=(1.4,-1.7,1.4),focus=(62,-51,61),view_radius=70,
      caption='P20與P21共用兩顆M3×25。P22的2mm端接馬達、3mm端接鋼軸；螺絲與螺母均可獨立選取。')
scene('step-15',['P31','P07','P08','P09','separatorpad','hopperM3x25','hopperM3nut','gateM3x8','gateM3nut'],
      new=['P07','P08','P09','separatorpad','hopperM3x25','hopperM3nut','gateM3x8','gateM3nut'],
      explode={'P08':[0,0,23],'P09':[15,0,23],'separatorpad':[15,0,23],
               'hopperM3x25':[0,0,44],'hopperM3nut':[0,0,-13],
               'gateM3x8':[-12,0,23],'gateM3nut':[30,0,23]},
      focus=(0,0,87),view_radius=95,
      caption='P08底板與兩側擋板封實，保留61mm內寬、前後開放及約23×12mm取牌輪開口。側板頂緣組裝後水平並切齊上殼屋頂外表面，上殼開口邊留至少0.5mm設計間隙。')
scene('step-16',['P13','P14','P15','P16','silicone','lower3mmshaft','upper3mmshaft','P23','P24','exit_opto','guideM3x8','photoM3x8','photoM3nut'],
      new=['P23','P24','exit_opto','guideM3x8','photoM3x8','photoM3nut'],
      explode={'P23':[15,0,0],'P24':[15,12,0],'exit_opto':[15,12,8],
               'guideM3x8':[34,0,0],'photoM3x8':[15,12,20],'photoM3nut':[15,12,-12]},
      camera=(1.8,-1.5,1.3),focus=(82,0,62),view_radius=63)
ui=['P27','P28','P35','screenpcb','OLEDglass','screenheader','keypcb','keybody','keyplunger','PCF8574','oledM3x8','keysM3x8']
shells=['P32A','P32B'];shell_join=['hoodJoinM3x8','hoodJoinM3nut']
scene('step-17',shells+shell_join+ui,new=shells+shell_join+ui,
      explode={'P32B':[0,-30,0],'hoodJoinM3x8':[0,0,-28],'hoodJoinM3nut':[0,18,0],'P27':[0,0,18],'P28':[0,0,-20],'screenpcb':[0,0,-20],'OLEDglass':[0,0,-20],
               'screenheader':[0,0,-20],'P35':[0,0,-28],'keypcb':[0,0,-28],
               'keybody':[0,0,-28],'keyplunger':[0,0,-28],'PCF8574':[0,0,-28],
               'oledM3x8':[0,0,-35],'keysM3x8':[0,0,-44]},
      camera=(1.2,-1.7,-.8),focus=(14,-35,119),view_radius=125,
      caption='先讓P32B由負Y滑入P32A約6.1mm包覆邊下，以原四組M3×8及螺母內鎖，再裝原UI。旋轉可看屋頂及兩側1.5mm台階；0.3mm為名義配合間隙。P27由屋頂上方裝入。')
body=['P04A','P31','P07','P08','P09','P13','P14','P15','P16','P17','P18','P19','P20','P21','P22','P23','P24']
scene('step-18',body+shells+shell_join+['hoodM3x8','hoodM3nut']+ui,
      new=shells+shell_join+['hoodM3x8','hoodM3nut']+ui,
      explode={name:[0,0,60] for name in shells+shell_join+ui}|{'hoodM3x8':[0,0,-20],'hoodM3nut':[0,0,60]},
      focus=(14,-8,84),view_radius=130,
      caption='台階包覆的P32A/P32B連好並預裝UI後整組由上方罩入；四組內連接、原安裝孔與機構位置保留。此步不含P33/P34，保留接線開口。')
electronics=['batteryholder','18650','ESP32C3','charger','TypeC','booster','protection1S','ULN2003','powerrocker']
scene('step-19',['P01','P29']+electronics+['baseM3nut'],new=['P29']+electronics+['baseM3nut'],
      explode={'P29':[0,0,18],'batteryholder':[0,0,10],'18650':[0,0,28],
               'ESP32C3':[0,0,16],'charger':[0,0,16],'TypeC':[0,0,16],
               'booster':[0,0,16],'protection1S':[0,0,16],'ULN2003':[0,0,16],'powerrocker':[15,0,0]},
      camera=(1.1,-1.7,2.4),focus=(0,0,13),view_radius=110,
      caption='外購板件為指定參考包絡；長條PCF與部分ULN2003固定座仍須依實物試配。電池須在斷電接線核對後安裝。')
scene('step-20',['P01','P02A','P04B','P06','slipring_rotor','slipring_flange','P36','slipM3x8','slipM3nut'],
      new=['P36','slipM3x8','slipM3nut'],
      explode={'P02A':[0,0,24],'P04B':[0,0,24],'P06':[0,0,24],
               'slipring_rotor':[0,0,24],'slipring_flange':[0,0,24],'P36':[0,0,24],
               'slipM3nut':[0,0,24],'slipM3x8':[0,0,-22]},
      camera=(1.2,-1.7,-1.3),focus=(0,0,10),view_radius=72,
      caption='三顆滑環M3×8由P01底部向上鎖入預放螺母的P36；可切到底視圖查看三個操作孔。')
scene('step-22',list(standard_ids),new=['P33','P34','baseM3x25','hatchM3x8','frontM3x8'],
      explode={'P32A':[0,0,42],'P32B':[0,-25,42],'hoodJoinM3x8':[0,0,20],'hoodJoinM3nut':[0,18,42],**{name:[0,0,42] for name in ui},
               'P33':[0,-32,0],'P34':[32,0,0],'baseM3x25':[0,0,30],
               'hatchM3x8':[0,-50,0],'frontM3x8':[50,0,0]},
      camera=(1.2,-1.6,1.4),focus=(10,-8,62),view_radius=145,
      caption=f'標準空機{len(standard_ids)}個獨立元件。試牌及校正完成後才裝P33/P34與底盒四顆長螺絲；可隱藏外殼查看內部。')
overview_explode={m['id']:m['explode'] for m in scenes['step-22']['meshes']}
scene('overview',list(standard_ids),new=[],explode=overview_explode,camera=(1.2,-1.6,1.4),focus=(10,-8,62),view_radius=145,
      caption=f'標準空機{standard_print_count}個列印件及{standard_hardware_count}個外購/五金參考件，共{len(standard_ids)}個元件；沒有隱藏簡化孔、齒輪或螺母槽。')
scene('optional',['P31','P07','P08','P09','P10','P11','P12'],new=['P10','P11','P12'],
      explode={'P10':[0,0,25],'P11':[0,0,45],'P12':lambda e:[0,-14 if e['position'][1]<0 else 14,8]},
      focus=(0,0,90),view_radius=95,
      caption=f'P10/P11僅在少牌壓力不足時加；57mm牌左右各用一片配套P12，第二片轉180度。44.1mm導牌本體仍落在底板，中央15mm對稱掛架跨過高側板並約高出3mm；原低側板版本不可直接混用。選配件不計入標準空機{len(standard_ids)}件。')

assert len(scenes['overview']['meshes'])==len(standard_ids)
assert len(scenes['step-22']['meshes'])==len(standard_ids)
assert set(scenes)=={f'step-{i:02}' for i in range(1,23) if i!=21}|{'overview','optional'}
assert all(len(s['meshes'])>0 for s in scenes.values())
assert all(len(e['axis'])==3 for e in records.values() if e['kind']=='screw')

# Exact source triangles, with only a Float32 local recentering round trip.
max_roundtrip=0.0
for rid,src in records.items():
    g=geometries[src['geometryKey']]
    local=np.frombuffer(base64.b64decode(g['positionsB64']),dtype='<f4').reshape(-1,3)
    original=np.asarray(c.tm(source_shapes[rid]).vertices)
    restored=local.astype(float)+src['position']
    max_roundtrip=max(max_roundtrip,float(np.abs(original-restored).max()))
assert max_roundtrip<.00002,max_roundtrip

payload={'version':'V1.0.0','units':'mm','up':[0,0,1],
    'schema':'Exact indexed CAD geometry, Float32 positions and Uint32 indices in little endian base64; positions are world mm centers; explode is a visual vector at slider=1.',
    'geometries':geometries,'scenes':scenes,
    'sourceHashes':{'buildCad':hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),
                    'exportScript':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
    'validation':{'standardComponents':len(standard_ids),'standardPrintInstances':standard_print_count,'standardHardwareInstances':standard_hardware_count,
        'upperHeadRaiseMm':c.UPPER_LIFT,
        'allGeometriesUnsimplified':True,'uniqueGeometries':len(geometries),
        'independentScrews':formal_screw_count,'independentNuts':formal_nut_count,'explicitScrewAxesVerified':len(axis_checks),
        'maximumFloat32WorldRoundtripErrorMm':round(max_roundtrip,9),'physicalAssemblyTested':False,
        'nominalSceneCount':len(scenes),'axisChecks':axis_checks}}
OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf8')
print(json.dumps({'file':str(OUT),'bytes':OUT.stat().st_size,
    **{k:v for k,v in payload['validation'].items() if k!='axisChecks'}},ensure_ascii=True,indent=2))
