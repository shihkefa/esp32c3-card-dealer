"""Render assembly-manual figures from the delivered CAD, without changing it.

The views are nominal CAD illustrations. Exploded offsets are for identification;
they do not constitute additional fit, preload or physical-assembly validation.
"""
from pathlib import Path
import json, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'3d/source'))
import build_cad as c

OUT=ROOT/'manual/assets'
OUT.mkdir(parents=True,exist_ok=True)
W,H=1440,920
BG=(247,248,246)
GRAY=(184,194,198)
ORANGE=(229,140,70)
BLUE=(68,119,143)
STEEL=(151,163,172)
PCB=(48,127,112)
DARK=(52,65,72)
FONT=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',24)
SMALL=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',19)
parts={p.id:p for p in c.parts}
hw={}
for name,s,color in c.hardware:hw.setdefault(name,[]).append(s)
ap={}
for pid,_,s,color in c.assembly_printables():ap.setdefault(pid,[]).append(s)

def p(pid,color=ORANGE,offset=(0,0,0)):
    return [(s.move(*offset),color) for s in ap.get(pid,[parts[pid].shape])]

def h(names,color=STEEL,offset=(0,0,0)):
    if isinstance(names,str):names=[names]
    return [(s.move(*offset),color) for name in names for s in hw.get(name,[])]

def raw(pid):return parts[pid].shape
def pt(v):return tuple(float(q) for q in v)
def center(shape):
    b=shape.m.bounding_box()
    return tuple(float((b[i]+b[i+3])/2) for i in range(3))

def point_shape(x,y,z):return c.box(.01,.01,.01,x,y,z-.005)
def wp(pid,x,y,z):return center(c.assembly_pose(pid,point_shape(x,y,z)))
def ip(x,y,z):return center(c.inclined_head_pose(point_shape(x,y,z)))
HEAD_RAISE=wp('P04A',0,0,0)[2]

def render(name,items,labels=(),cam=(1.2,-1.65,1.5),arrows=()):
    """Opaque z-buffer rendering, auto-fit model area with exterior callouts."""
    if len(sys.argv)>1 and name not in sys.argv[1:]:return
    camera=np.asarray(cam,float);camera/=np.linalg.norm(camera)
    right=np.cross([0,0,1.],camera);right/=np.linalg.norm(right)
    up=np.cross(camera,right)
    meshes=[(c.tm(s),col) for s,col in items]
    allv=np.vstack([m.vertices for m,_ in meshes])
    proj=np.column_stack((allv@right,allv@up))
    low,high=proj.min(axis=0),proj.max(axis=0)
    scale=min(1000/max(high[0]-low[0],1),650/max(high[1]-low[1],1))
    mid=(high+low)/2
    def project(v):
        q=np.asarray(v)
        return (float(W/2+(q@right-mid[0])*scale),float(H/2-(q@up-mid[1])*scale))
    pix=np.full((H,W,3),BG,dtype=np.uint8)
    zbuf=np.full((H,W),-np.inf,dtype=np.float32)
    light=np.asarray([-.45,-.75,1.5]);light/=np.linalg.norm(light)
    for mesh,color in meshes:
        tri=np.asarray(mesh.vertices)[np.asarray(mesh.faces)]
        normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-10)
        for t,n in zip(tri,normals):
            if np.dot(n,camera)<-.001:continue
            xy=np.array([project(v) for v in t]);depth=t@camera
            xmin=max(0,int(math.floor(xy[:,0].min())));xmax=min(W-1,int(math.ceil(xy[:,0].max())))
            ymin=max(0,int(math.floor(xy[:,1].min())));ymax=min(H-1,int(math.ceil(xy[:,1].max())))
            if xmax<xmin or ymax<ymin:continue
            x0,y0=xy[0];x1,y1=xy[1];x2,y2=xy[2]
            den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
            if abs(den)<1e-9:continue
            yy,xx=np.mgrid[ymin:ymax+1,xmin:xmax+1]
            aa=((y1-y2)*(xx+.5-x2)+(x2-x1)*(yy+.5-y2))/den
            bb=((y2-y0)*(xx+.5-x2)+(x0-x2)*(yy+.5-y2))/den
            cc=1-aa-bb;zz=aa*depth[0]+bb*depth[1]+cc*depth[2]
            window=zbuf[ymin:ymax+1,xmin:xmax+1]
            mask=(aa>=-1e-5)&(bb>=-1e-5)&(cc>=-1e-5)&(zz>window)
            shade=.66+.34*max(0,float(np.dot(n,light)))
            rgb=tuple(int(ch*shade) for ch in color)
            pix[ymin:ymax+1,xmin:xmax+1][mask]=rgb;window[mask]=zz[mask]
    image=Image.fromarray(pix)
    draw=ImageDraw.Draw(image)
    for start,end in arrows:
        a=np.asarray(project(start));b=np.asarray(project(end));v=b-a
        if np.linalg.norm(v)<1:continue
        v/=np.linalg.norm(v);side=np.asarray([-v[1],v[0]])
        draw.line([tuple(a),tuple(b)],fill=(61,119,143),width=4)
        draw.polygon([tuple(b),tuple(b-v*17+side*8),tuple(b-v*17-side*8)],fill=(61,119,143))
    for text,target,pos in labels:
        pos=tuple(pos);box=draw.multiline_textbbox(pos,text,font=FONT,spacing=5)
        draw.rectangle((box[0]-9,box[1]-6,box[2]+9,box[3]+6),fill=BG)
        anchor=(box[2]+11 if pos[0]<W/2 else box[0]-11,(box[1]+box[3])/2)
        xy=project(target)
        draw.line([anchor,xy],fill=(72,105,118),width=2)
        draw.ellipse((xy[0]-4,xy[1]-4,xy[0]+4,xy[1]+4),fill=(220,116,66))
        draw.multiline_text(pos,text,font=FONT,spacing=5,fill=(37,64,75))
    draw.text((22,H-34),'實際 CAD 示意  ·  爆炸間距供辨識  ·  非實物照片',font=SMALL,fill=(117,132,136))
    image.save(OUT/name,quality=91,subsampling=0)
    print(name,flush=True)

def reuse(source,name):
    if len(sys.argv)>1 and name not in sys.argv[1:]:return
    image=Image.open(ROOT/source).convert('RGB')
    image.thumbnail((1440,1280))
    image.save(OUT/name,quality=91,subsampling=0)

def main():
    # Existing detailed figures remain authoritative for the recently revised
    # split components and the explicitly tested L-key path.
    existing={
      'figure02.jpg':'3d/P02_分件組裝說明.png',
      'figure04.jpg':'3d/P05_L工具鎖付順序.png',
      'figure05.jpg':'3d/P05A_P05B_平口配合.png',
      'figure06.jpg':'3d/P04_分件組裝說明.png',
      'detail-p02-nuts.jpg':'3d/P02B_螺母槽近照.png',
      'detail-p04-nuts.jpg':'3d/P04B_螺母槽近照.png',
      'detail-p06.jpg':'3d/P06_捕捉螺母與調整螺絲.png',
      'detail-p05-exploded.jpg':'3d/P05_分件組裝與閉合夾座.png',
      'detail-p05-seat.jpg':'3d/P05_完整承壓與防脫剖示.png',
      'detail-p05-print.jpg':'3d/P05_列印方向.png',
      'overview.jpg':'3d/assembly_preview.png',
      'cutaway.jpg':'3d/assembly_cutaway.png',
      'controls.jpg':'3d/top_controls_view.png',
    }
    for name,source in existing.items():reuse(source,name)

    # 01: trial coupon and actual fastener envelopes, arranged for inspection.
    trial=raw('P30')
    render('figure01.jpg',[(trial,ORANGE),(c.flat_screw(8).move(42,0,0),STEEL),
          (c.flat_screw(25).move(58,0,0),BLUE),(c.hex_nut3(42,18,0),STEEL)],
          [('P30 孔徑試配片',(-8,0,4),(30,120)),
           ('M3x8 / M3x25',(58,0,13),(1120,140)),
           ('標準 M3 螺母',(42,18,1.2),(1120,700))],cam=(.6,-1.8,1.8))

    cover_context=raw('P02A')&c.box(90,90,60,47,0,0)
    render('figure03.jpg',[(cover_context,GRAY)]+h(['28BYJ-48','stepper_output'],BLUE,(0,0,-20))
        +h('stepperM3x8',STEEL,(0,0,18))+h('stepperM3nut',STEEL,(0,0,-20)),
        [('P02A 局部',(76,-12,32),(30,140)),
         ('28BYJ-48 馬達',(47,0,-1),(1060,590)),
         ('M3x8 x2',(47,-17.5,50.7),(1060,150))],
        cam=(1.2,-1.8,1.3),arrows=[((54,0,23),(54,0,31))])

    central=(raw('P02A')&c.cyl(98,60,z0=0))+raw('P02B')+raw('P03')
    render('figure07.jpg',[(central,GRAY)]+h('6005ZZ')+p('P04A',BLUE,(0,0,26))+p('P04B',ORANGE,(0,0,26))
        +p('P06',BLUE,(0,0,-20)),
        [(f'P04A / P04B 子組\n上半部抬高 {HEAD_RAISE:g} mm',wp('P04A',0,20,68),(28,130)),
         ('穿入 6005ZZ',(20,0,24),(1080,420)),
         ('P06 先放螺母\n由軸底端套入',(-15,0,-4),(28,710))],
        cam=(1.1,-1.7,.95),arrows=[(wp('P04A',0,0,62),wp('P04A',0,0,42)),((0,0,-3),(0,0,13))])

    render('figure08.jpg',p('P04B',GRAY)+p('P06',ORANGE)+h('6005ZZ')
        +h(['slipring_rotor','slipring_flange'],BLUE,(0,0,-27))
        +h('rotorM3x8',STEEL,(-14,0,0)),
        [('P04B 空心軸',(10,0,30),(30,130)),
         ('滑環由下方穿入',(0,0,-9),(1080,650)),
         ('P06 徑向螺絲\n接觸轉子後輕調',(-25,0,15.5),(30,690))],
        cam=(-1.3,-1.8,.9),arrows=[((0,0,-5),(0,0,8))])

    sensor_context=(raw('P02A')&c.box(50,50,40,-65,10,10))
    sensor_context=sensor_context+c.assembly_pose('P04A',raw('P04A')&c.box(50,50,15,-55,10,38))
    render('figure09.jpg',[(sensor_context,GRAY)]+p('P25',ORANGE)+p('P26',BLUE)+h('home_opto',DARK)
        +h(['homeM3x8','flagM3x8','flagM3nut']),
        [('P25 固定光電座',(-66,10,30),(30,680)),
         (f'P26 支臂隨轉盤抬高\n遮光薄片向下延長 {HEAD_RAISE:g} mm',wp('P26',-58,10,40.6),(1040,140)),
         ('遮光片仍穿過槽中央',(-74.5,10,37),(30,130))],cam=(-1.2,-1.8,1.6))

    render('figure10.jpg',p('P04A',GRAY)+p('P31',ORANGE,(0,0,20))
        +h('adapterM3x8',STEEL,(0,0,36))+h('adapterM3nut',STEEL,(0,0,-10)),
        [('P31 6 度轉接框',wp('P31',20,25,69),(1050,150)),
         ('P04A 旋轉承載盤',wp('P04A',-50,-30,44),(30,650)),
         ('四處 M3x8 + M3 螺母',wp('P04A',-45,-44,84.9),(30,150))],cam=(1.15,-1.65,1.4),
        arrows=[(wp('P31',5,0,71),wp('P31',5,0,51))])

    # Work in the non-inclined local roller coordinates for a clear common axis.
    def unincline(s):
        return s.move(z=-(c.P['card_floor_z_mm']+c.P['hopper_lift_mm']+HEAD_RAISE)).rot(y=-c.P['hopper_tilt_deg']).move(z=c.P['card_floor_z_mm'])
    rollers=p('P16',ORANGE)
    roller_hw=h(['lower3mmshaft','upper3mmshaft','silicone','wheelM3x8','wheelM3nut'])
    roller_items=[(unincline(s),col) for s,col in rollers+roller_hw]
    # Show both outside bearing pairs offset along their insertion axes.
    for name in ['lower623','upper623']:
        for i,s in enumerate(hw[name]):
            side=-1 if i==0 else 1
            roller_items.append((unincline(s).move(y=side*18),BLUE))
    render('figure11.jpg',roller_items,
        [('P16 輪芯 x2',(61,0,74.75),(30,140)),
         ('O 型圈 x4',(61,-24,54.2),(30,690)),
         ('623ZZ 軸承 x4\n沿鋼軸由外側套入',(61,52,74.75),(1080,150)),
         ('3 mm 鋼軸',(61,-45,54.2),(1080,690))],cam=(1.5,-1.3,1.3),
         arrows=[((61,-52,74.75),(61,-36,74.75)),((61,52,54.2),(61,36,54.2))])

    roller_base=p('P31',GRAY)+p('P16',GRAY)+h(['lower3mmshaft','upper3mmshaft','silicone'])
    roller_seats=[]
    for pid in ['P13','P14','P15']:
        for s in ap[pid]:
            b=s.m.bounding_box();side=-1 if (b[1]+b[4])/2<0 else 1
            roller_seats.append((s.move(y=side*17),ORANGE if pid!='P15' else BLUE))
    render('figure12.jpg',roller_base+roller_seats+h('pillowM3x8',STEEL,(0,0,16))
        +h('adjustM3x8',STEEL,(0,0,14)),
        [('P13 / P14 兩側滾輪座',ip(61,-52,61),(30,690)),
         ('P15 上滑塊 x2',ip(61,52,75),(1080,140)),
         ('頂部螺絲調整上輪高度',ip(61,-35,98),(30,140))],cam=(1.5,-1.6,1.4))

    render('figure13.jpg',p('P31',GRAY)+p('P18',BLUE)+p('P19',ORANGE,(0,0,15))+p('P17',ORANGE,(0,12,0))
        +h('N20',STEEL,(0,0,6))+h('feedrubber',DARK,(0,12,0))+h('n20clampM3x8',STEEL,(0,0,28)),
        [('P18 馬達底座',ip(-30,-19,48),(30,690)),
         ('N20 減速馬達',ip(-22,-11,61),(30,140)),
         ('P19 上壓片',ip(-22,-11,75),(1070,140)),
         ('P17 取牌輪\n套 3 mm D 軸',ip(-22,20,54),(1070,690))],cam=(-1.0,-1.7,1.6))

    render('figure14.jpg',p('P31',GRAY)+p('P16',GRAY)+h('lower3mmshaft')
        +p('P20',BLUE)+p('P21',ORANGE,(0,0,15))+p('P22',ORANGE,(0,0,4))
        +h('RF300',STEEL,(0,-13,0))+h('rfclampM3x25',STEEL,(0,0,30)),
        [('RF300 馬達',ip(61,-92,54),(30,650)),
         ('P20 / P21\n兩顆 M3x25 共用固定',ip(75.5,-74.3,79),(30,140)),
         ('P22 聯軸器\n2 mm 端接馬達',ip(61,-49,58),(1080,150)),
         ('3 mm 端接鋼軸',ip(61,-38,54),(1080,680))],cam=(1.4,-1.7,1.4))

    render('figure15.jpg',p('P31',GRAY)+p('P07',BLUE)+p('P08',ORANGE,(0,0,20))
        +p('P09',BLUE,(14,0,20))+h('separatorpad',DARK,(14,0,20))+h('hopperM3x25',STEEL,(0,0,42)),
        [('P08 61 mm 牌倉',ip(-15,-30,84),(30,140)),
         ('P07 支柱 x4',ip(-45,-26,57),(30,690)),
         ('P09 分牌閘\n後方穿入兩顆 M3x8',ip(59,25,87),(1080,140)),
         ('前緣朝出牌口',ip(50,0,84),(1080,680))],cam=(1.2,-1.7,1.5))

    render('figure16.jpg',p('P13',GRAY)+p('P14',GRAY)+p('P16',GRAY)+h(['silicone','lower3mmshaft','upper3mmshaft'])
        +p('P23',ORANGE,(12,0,0))+p('P24',BLUE,(12,9,0))+h('exit_opto',DARK,(12,9,0))
        +h('guideM3x8',STEEL,(27,0,0)),
        [('P23 出牌導槽',ip(91,0,62),(30,140)),
         ('P24 出口感測座',ip(103,41,64),(1070,150)),
         ('槽型光電元件',ip(103,42,65),(1070,650)),
         ('57 mm 牌時向內移 1.5 mm',ip(93,27,64),(30,690))],cam=(1.8,-1.5,1.5))

    # Show inside of roof with holders below it, keeping caps above as reference.
    roof=c.assembly_pose('P32A',raw('P32A')&c.box(58,114,18,77,4,118))
    ui=[(roof,GRAY)]+p('P28',BLUE,(0,0,-18))+p('P35',ORANGE,(0,0,-25))
    ui+=h(['screenpcb','OLEDglass','screenheader'],PCB,(0,0,-18))
    ui+=h(['keypcb','keybody','keyplunger','PCF8574'],PCB,(0,0,-25))+p('P27',ORANGE,(0,0,12))
    render('figure17.jpg',ui,
        [('P28 與 OLED 固定框',wp('P28',75,-24,103),(30,690)),
         ('P35 按鍵及 PCF 支架',wp('P35',88,23,78),(1080,680)),
         ('P27 按鍵帽 x4',wp('P27',75,17,142),(1080,150)),
         ('P32A 屋頂局部',wp('P32A',65,0,129),(30,140))],cam=(1.2,-1.8,.9),
         arrows=[(wp('P27',75,4,141),wp('P27',75,4,132))])

    body_ids=['P04A','P31','P07','P08','P09','P13','P14','P15','P16','P17','P18','P19','P20','P21','P22','P23','P24']
    assembled=[item for pid in body_ids for item in p(pid,GRAY)]
    render('figure18.jpg',assembled+p('P32A',BLUE,(0,0,60))+p('P32B',BLUE,(0,0,60))
        +p('P27',ORANGE,(0,0,60))+p('P28',GRAY,(0,0,60))+p('P35',GRAY,(0,0,60)),
        [('A包覆B 台階上殼\n預裝 UI 後垂直罩入',wp('P32A',20,0,182),(30,130)),
         ('P33 / P34 先不封蓋',wp('P32A',60,-60,80),(1080,680))],cam=(1.2,-1.65,1.35),
        arrows=[(wp('P32A',0,0,153),wp('P32A',0,0,118))])

    electronics=['batteryholder','18650','ESP32C3','charger','TypeC','booster','protection1S','ULN2003','powerrocker']
    render('figure19.jpg',p('P01',GRAY)+p('P29',ORANGE)+h(electronics,PCB),
        [('ESP32 C3 SuperMini',(-58,-1,14),(30,130)),
         ('TP4056 與 Type C',(-67,-36.5,10),(30,690)),
         ('18650 電池盒與 P29',(0,55,17),(1060,130)),
         ('升壓板 / 保護板 / ULN2003',(-20,-35,10),(1060,690))],cam=(1.1,-1.7,2.8))

    base_disc=raw('P01')&c.cyl(88,30,z0=0)
    clips=p('P36',ORANGE,(0,0,17))
    render('figure20.jpg',[(base_disc,GRAY)]+h('slipring_flange',BLUE,(0,0,17))+clips
        +h('slipM3nut',STEEL,(0,0,17))+h('slipM3x8',STEEL,(0,0,-20)),
        [('P36 壓片 x3\n螺母先預放',(26.5,0,28),(30,130)),
         ('滑環固定法蘭',(15,0,25.8),(1060,130)),
         ('P01 底部局部',(0,-35,2),(30,690)),
         ('三顆 M3x8\n由底部凹孔向上鎖',(26.5,0,-14.5),(1060,690))],cam=(1.2,-1.7,-1.35),
        arrows=[((26.5,0,-10),(26.5,0,3)),((-13.25,22.95,-10),(-13.25,22.95,3))])

    reuse('3d/top_controls_view.png','figure22.jpg')
    # A browser-scaled overview is navigational only; the original interactive
    # wiring diagram remains the readable pin-level reference.
    wiring=ROOT/'wiring/發牌機_實物逐腳接線圖.png'
    if wiring.exists():reuse('wiring/發牌機_實物逐腳接線圖.png','figure21.jpg')
    else:reuse('3d/assembly_cutaway.png','figure21.jpg')
    index={
      'revision':'V1.0.0','source':'Actual current CAD solids and delivered wiring reference',
      'scope':'Exploded offsets and context cuts are illustration only; purchased hardware is a reference envelope.',
      'steps':{f'step-{i:02}':{'file':f'assets/figure{i:02}.jpg','alt':alt}
        for i,alt in enumerate([
          'P30試配片與兩種M3沉頭螺絲','P02A P02B P03與6005軸承爆炸圖',
          '28BYJ馬達由P02A下側安裝','P05B與L型扳手鎖付順序','P05A內腔平口與P05B平口配合',
          f'P04A承載盤與加高{HEAD_RAISE:g}mm的P04B齒輪軸子組',f'轉盤子組穿入原高度軸承並從下方套P06，承載盤與P02A頂圈名義間隙{.5+HEAD_RAISE:g}mm','滑環轉子由空心軸下方穿入',
          f'固定高度P25光電與向下延長{HEAD_RAISE:g}mm的P26遮光片','P31下傾轉接框固定到P04A',
          '兩組輪芯 O圈 鋼軸及623軸承','兩側滾輪座與上滑塊從軸外側裝入',
          'N20減速馬達 底座 壓片與取牌輪','RF300長軸馬達 聯軸器與共用長螺絲',
          '牌倉 四支柱與分牌閘爆炸示意','出牌導槽與可調出口光電座',
          'P32A屋頂局部 OLED 按鍵帽與內側支架','台階包覆P32A P32B及預裝頂部UI後整組罩入',
          '底盒內電子模組與電池盒固定位置','P36壓片 預置螺母與底部向上固定螺絲',
          '完整逐腳接線總覽 詳細接線另開原圖','頂部按鍵操作與最終封蓋成品'],1)},
      'details':{'p02Nuts':'assets/detail-p02-nuts.jpg','p04Nuts':'assets/detail-p04-nuts.jpg',
                 'p06':'assets/detail-p06.jpg','p05Exploded':'assets/detail-p05-exploded.jpg',
                 'p05Seat':'assets/detail-p05-seat.jpg','p05Print':'assets/detail-p05-print.jpg'},
      'overview':'assets/overview.jpg','cutaway':'assets/cutaway.jpg','controls':'assets/controls.jpg'
    }
    (OUT/'figure_index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf8')
    print('figure_index.json',flush=True)

if __name__=='__main__':main()
