"""Card dealer V1.0.0: two screw SKUs throughout the complete assembly.

Regenerate with Python 3.12, numpy, manifold3d, trimesh and Pillow.
All dimensions in mm. Tilt parameters are in design_params.json;
individual part dimensions are defined in this file.
"""
from __future__ import annotations
import json, math, sys, struct, zipfile, shutil, os
from dataclasses import dataclass
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if (ROOT / "dependencies" / "cad").exists():
    sys.path.insert(0, str(ROOT / "dependencies" / "cad"))
import numpy as np
import manifold3d as mf
import trimesh
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "design_params.json").read_text(encoding="utf-8"))
DEFAULT_OUT = ROOT / "3d"
OUT = Path(os.environ.get("CARD_DEALER_OUTPUT", str(DEFAULT_OUT)))
OUT.mkdir(parents=True, exist_ok=True)
EPS = 0.05
N = 64
UPPER_LIFT = float(P.get('turntable_raise_mm', 0))
P04_MATE_Z = 42.0 + UPPER_LIFT
P04_GEAR_BOTTOM_Z = 36.0
P04_GEAR_HEIGHT = 6.0 + UPPER_LIFT
RAISED_PRINT_PARTS = {f'P{i:02}' for i in range(7,25)} | {
    'P04A','P26','P27','P28','P31','P32A','P32B','P33','P34','P35'}

def head_pose(shape):
    """Place an upper-head solid after its native/inclined construction."""
    return shape.move(z=UPPER_LIFT)

def inclined_head_pose(shape):
    return head_pose(incline(shape))

def assembly_pose(pid, shape):
    if pid in TILTED:
        shape = incline(shape)
    return head_pose(shape) if pid in RAISED_PRINT_PARTS else shape

def fmt(v):
    if isinstance(v, (tuple, list, np.ndarray)):
        return "[" + ",".join(fmt(x) for x in v) + "]"
    return f"{float(v):.5f}".rstrip("0").rstrip(".") or "0"

@dataclass
class S:
    m: object
    code: str
    def move(self, x=0, y=0, z=0):
        return S(self.m.translate((x,y,z)), f"translate({fmt([x,y,z])}){{{self.code}}}")
    def rot(self, x=0, y=0, z=0):
        return S(self.m.rotate((x,y,z)), f"rotate({fmt([x,y,z])}){{{self.code}}}")
    def basis(self,u,v,n,origin):
        matrix=np.column_stack([u,v,n,origin])
        full=np.vstack([matrix,[0,0,0,1]])
        return S(self.m.transform(matrix),f"multmatrix({fmt(full.tolist())}){{{self.code}}}")
    def __add__(self, b):
        return S(self.m + b.m, f"union(){{{self.code}{b.code}}}")
    def __sub__(self, b):
        return S(self.m - b.m, f"difference(){{{self.code}{b.code}}}")
    def __and__(self, b):
        return S(self.m ^ b.m, f"intersection(){{{self.code}{b.code}}}")

def U(items):
    items = list(items)
    if not items:
        return S(mf.Manifold(), "")
    acc = items[0]
    for item in items[1:]:
        acc = acc + item
    return acc

def box(x,y,z, cx=0,cy=0,z0=0):
    return S(mf.Manifold.cube((x,y,z)),f"cube({fmt([x,y,z])});").move(cx-x/2,cy-y/2,z0)

def cyl(d,h,cx=0,cy=0,z0=0,n=N,d2=None):
    d2 = d if d2 is None else d2
    return S(mf.Manifold.cylinder(h,d/2,d2/2,n),
             f"cylinder(h={fmt(h)},d1={fmt(d)},d2={fmt(d2)},$fn={n});").move(cx,cy,z0)

def cyly(d,h,x=0,y0=0,z=0,n=N):
    return cyl(d,h,n=n).rot(x=-90).move(x,y0,z)

def cylx(d,h,x0=0,y=0,z=0,n=N):
    return cyl(d,h,n=n).rot(y=90).move(x0,y,z)

def poly(points,h,z0=0):
    return S(mf.CrossSection([points]).extrude(h),
             f"linear_extrude(height={fmt(h)})polygon({fmt(points)});").move(z=z0)

def rr(x,y,r,h,cx=0,cy=0,z0=0):
    points=[]
    for a,b,start in [(x/2-r,y/2-r,0),(-x/2+r,y/2-r,90),(-x/2+r,-y/2+r,180),(x/2-r,-y/2+r,270)]:
        for deg in np.linspace(start,start+90,9):
            points.append([a+r*math.cos(math.radians(deg)),b+r*math.sin(math.radians(deg))])
    return poly(points,h,z0).move(cx,cy)

def hole(x,y,z0,h,d=3.4): return cyl(d,h,x,y,z0)
def nut(x,y,z0,h=2.6): return cyl(6.55,h,x,y,z0,n=6)
def slotz(x,y,z0,w,l,h): return rr(w,l,min(w,l)/2-.01,h,x,y,z0)

def annular_sector(ri,ro,a1,a2,h,z0):
    points=[]
    for a in np.linspace(a1,a2,16): points.append([ro*math.cos(math.radians(a)),ro*math.sin(math.radians(a))])
    for a in np.linspace(a2,a1,16): points.append([ri*math.cos(math.radians(a)),ri*math.sin(math.radians(a))])
    return poly(points,h,z0)

def gear(teeth,module,h,z0=0,backlash=.18):
    rp=teeth*module/2; rb=rp*math.cos(math.radians(20)); ra=rp+module; rf=rp-1.25*module
    ip=math.tan(math.radians(20))-math.radians(20)
    half=math.pi/(2*teeth)-backlash/(2*rp)
    def inv(r):
        if r <= rb: return 0
        q=math.sqrt((r/rb)**2-1)
        return q-math.atan(q)
    pts=[]
    def p(r,a): return [r*math.cos(a),r*math.sin(a)]
    for k in range(teeth):
        c=2*math.pi*k/teeth
        ar=half+ip-inv(rf)
        pts.append(p(rf,c-ar))
        radii=np.linspace(max(rf,rb),ra,6)
        for r in radii: pts.append(p(r,c-(half+ip-inv(r))))
        at=half+ip-inv(ra)
        for a in np.linspace(c-at,c+at,4)[1:]: pts.append(p(ra,a))
        for r in radii[-2::-1]: pts.append(p(r,c+(half+ip-inv(r))))
        pts.append(p(rf,c+ar))
        nxt=2*math.pi*(k+1)/teeth-ar
        for a in np.linspace(c+ar,nxt,4)[1:]: pts.append(p(rf,a))
    return poly(pts,h,z0)

@dataclass
class Part:
    id: str
    name: str
    shape: S
    qty: int=1
    material: str="PLA / PETG"
    color: tuple=(218,220,214)
    print_rot: tuple=(0,0,0)
    support: str="不需要"
    note: str=""
    engraving: dict|None=None

parts=[]
def add(id,name,shape,qty=1,color=(218,220,214),rot=(0,0,0),support="建議無支撐；待切片",note=""):
    p=Part(id,name,shape,qty,color=color,print_rot=rot,support=support,note=note)
    parts.append(p)
    return p

DARK=(40,57,66); COVER=(55,75,83); PLATE=(67,89,94); LIGHT=(221,223,215); ORANGE=(223,105,62)
METAL=(160,170,178); RUBBER=(34,39,42); PCB=(40,104,89)

# P01 mostly closed base; all electronics and battery remain stationary.
base=rr(164,148,16,2.2,z0=0)+(rr(164,148,16,27.8,z0=2.1)-rr(159.6,143.6,13.8,29,z0=2.0))
for x in [-45,0,45]: base=base-box(18,7,1.6,x,-74,23)
for x in [-68,68]:
    for y in [-58,58]:
        base=base+cyl(8,27,x,y,2)
        base=base-hole(x,y,1,30)-nut(x,y,8.1,2.7)
        base=base-box(10,5.8,2.7,x-5 if x>0 else x+5,y,8.1)
# Adjustable flange supports: the 12-way slip ring is fixed by its flange.
SLIP_MOUNTS=[]
for a in [0,120,240]:
    support=annular_sector(11.8,19.5,a-15,a+15,5.6,2.2)
    support=support-hole(19*math.cos(math.radians(a)),19*math.sin(math.radians(a)),2,8,2.6)
    boss=(cyl(9,7.6,26.5,0,2.2)-hole(26.5,0,1,12))
    # Recessed underside access: no M2 fastener through the purchased flange.
    boss=boss-cyl(6.4,6,26.5,0,-.5)-cyl(6.4,1.7,26.5,0,5.4,d2=3.4)
    base=base+support+boss.rot(z=a)
    base=base-cyl(6.4,6,26.5,0,-.5).rot(z=a)
    SLIP_MOUNTS.append((19*math.cos(math.radians(a)),19*math.sin(math.radians(a))))
base=base-cyl(45.5,2.2,z0=7.8)
# USB-C at rear left; rocker power switch at the front.
base=base-box(8,11,5,-81,-36.5,8.7)
base=base-box(8,10.5,15.5,81,-1,7)
# Motor mounting ledges below 28BYJ body.
for y in [-17.5,17.5]:
    base=base+rr(12,6,2.4,26.5,47,y,2)
    base=base-slotz(47,y,1,3.8,4.5,30)-nut(47,y,24.8,2.7)
    base=base-box(12,5.8,2.7,50,y,24.8)
# Internal tie bridges leave the bottom skin intact.
for x,y in [(-58,-2),(-26,-38),(22,-42),(-68,-36),(-20,55),(25,55)]:
    for dy in ([-13.4,13.4] if y==55 else [-7,7]):
        bridge=rr(10,4,1,3.8,x,y+dy,2.2)-box(6,6,1.8,x,y+dy,3.2)
        base=base+bridge
for yy in [17,27]:
    base=base+(rr(10,4,1,3.8,-30,yy,2.2)-box(6,6,1.8,-30,yy,3.2))
add("P01","封閉式固定底座",base,color=DARK,note="底板封閉；後側三條18×1.6mm通風縫。內部橋座穿束帶；接口依實物核對。")

# P02 is split into a flat-bottom cover and a separately printable bearing cup.
# The original 3 x M3x8 screws clamp P03 / P02A / P02B together; no extra SKU.
BEARING_MOUNTS=[(28.5*math.cos(math.radians(a)),28.5*math.sin(math.radians(a)))
                for a in (30,150,270)]
cover=rr(164,148,16,3,z0=30)+cyl(164,3,z0=30)
cover=cover+(cyl(164,8.6,z0=32.9)-cyl(159.6,9,z0=32.8))
cover=cover-cyl(58.4,5,z0=29)
# Clear motor mounting bosses and pinion shaft; panel lives on front right.
cover=cover-hole(54,0,29,7,24)
for yy in [-17.5,17.5]:
    cover=cover-hole(47,yy,29,8,3.8)-cyl(6.4,1.7,d2=3.8).rot(x=180).move(47,yy,32.8)
    cover=cover-cyl(6.4,.6,47,yy,32.7)
for x in [-68,68]:
    for y in [-58,58]:
        cover=cover-hole(x,y,29,6)-cyl(6.4,1.7,d2=3.4).rot(x=180).move(x,y,33.1)
for x,y in BEARING_MOUNTS:
    cover=cover-hole(x,y,29,6,10.4)
cover=cover+box(18,14,3,-70.5,10,30)
cover=cover-box(13.6,3.6,12,-74.5,14.9,29)-hole(-63.5,10,28,9,2.7)
cover=cover-box(14,8,10,-74.5,10,33.1)
for xx in [-79.5,-69.5]:
    for yy in [8.73,11.27]: cover=cover-hole(xx,yy,26,9,1.2)
add("P02A","平底上蓋主板",cover,color=COVER,support="大平面朝下；局部小孔與避讓槽待切片",note="大平面朝下列印，軸承座改由底面裝入。中央58.4孔及三個10.4定位孔與P02B配合，名義單邊0.2間隙。共用三顆M3×8及P02B螺母，外圈和底盒孔位保留。")

# Cup print bed: the annular Z18 face. Bearing support remains at Z19 and its
# bore stays 47.3. Three 45-degree expanding pads form the lower clamp flange.
# Upper bosses stop at Z32.8: 0.2 below P02A, so P03 clamps the cover rather
# than bottoming on the bosses. Nut wells open at the original underside holes.
seat=cyl(58,14.8,z0=18)-cyl(43,2.1,z0=17)
for x,y in BEARING_MOUNTS:
    seat=seat+cyl(10,14.8,x,y,18)
    seat=seat+cyl(10,2,x,y,23,d2=14)+cyl(14,5,x,y,25)
    seat=seat-hole(x,y,17.8,17,3.4)-cyl(6.7,12.7,x,y,17.9,n=6)
seat=seat-cyl(47.3,17,z0=19)
add("P02B","分離式軸承座與捕捉螺母槽",seat,color=COVER,support="環形底面朝下；六角槽頂部局部橋接待切片",note="底部環形平面朝下。三處原小孔改5.8對邊六角深槽，先放M3螺母並推至上止擋；螺絲孔3.4。可暫用既有M3×25拉入螺母，再換M3×8。三個下凸緣夾在P02A底面；不在轉軸或軸承工作面刻號。")

retainer=(cyl(70,2,z0=33)+cyl(46.8,2.2,z0=31))-cyl(37,7,z0=30)
# Full pinion motion reaches X34.8; keep the cap's motor side at X34.0.
retainer=retainer-box(10,100,10,39,0,29)
for a in [30,150,270]:
        x,y=28.5*math.cos(math.radians(a)),28.5*math.sin(math.radians(a))
        retainer=retainer-hole(x,y,30,7)-cyl(6.4,1.7,d2=3.4).rot(x=180).move(x,y,35.1)
add("P03","轉盤軸承壓環",retainer,color=DARK,rot=(180,0,0),support="大平面朝下；沉頭孔局部橋接待切片",note="配合P02A/P02B，最大外徑70，馬達側削平避讓；內孔與三孔位置不變，大平面朝下列印。三顆M3×8同時固定壓環、主板與軸承座，分次均勻鎖緊。")

# P04A/P04B: bed-flat carrier and separate gear/journal. Keep every original
# assembly datum, mounting hole and bearing surface; add a keyed bolted joint.
deckplate=(cyl(124,3.4,z0=42)-cyl(112,5,z0=41))
deckplate=deckplate+(rr(38,116,6,3.4,61,-14,42)-rr(28,106,3,5,61,-14,41))
deckplate=deckplate+box(110,8,3.4,-4,-26,42)+box(110,8,3.4,-4,26,42)
deckplate=deckplate+box(8,105,3.4,-45,0,42)+box(8,105,3.4,31,0,42)
for yy in [-60,-35,35]: deckplate=deckplate+box(38,8,3.4,61,yy,42)
main=gear(60,1.2,6,36)+cyl(24.8,29,z0=13)+cyl(31,3,z0=31,d2=24.8)+deckplate
main=main-cyl(22.5,40,z0=10)
main=main-cyly(24.8,17,61,-69.2,54.2)
for a in range(0,360,60): main=main-annular_sector(18,30,a+10,a+50,9,35)
for x in [-45,31]:
    for y in [-26,26]: main=main-hole(x,y,40,8)-nut(x,y,41,2.6)
    for y in [-44,44]: main=main-hole(x,y,40,8)-nut(x,y,41,2.7)
for x,y in [(-33,-19),(-12,-19),(49,-60),(72,-60),(55,-35),(67,-35),(55,35),(67,35)]:
    main=main-hole(x,y,41,6)-nut(x,y,41,2.7)
main=main+cyl(9,3.4,-58,10,42)
main=main-hole(-58,10,40,12)
main=main-cylx(3.4,5,-14.5,0,15.5)
HOUSING_MOUNTS=[(-59,0),(0,57),(72,49)]
main=main+box(12,12,3.4,72,45,42)
for x,y in HOUSING_MOUNTS:
    main=main+cyl(10,3.4,x,y,42)
    main=main-hole(x,y,40,9)-cyl(6.4,1.5,x,y,41.9,d2=3.4)
P04_MOUNTS=[(x,y) for x in (-15,15) for y in (-26,26)]
carrier=main & box(220,220,5,0,0,42)
gear_journal=main & box(220,220,30,0,0,12)
# Retain the bearing shoulder, lower journal and original tooth-bottom height.
# Add only above the old mating plane: P04A's printable solid stays unchanged.
if UPPER_LIFT:
    extension=gear(60,1.2,UPPER_LIFT,42)+cyl(24.8,UPPER_LIFT,z0=42)
    extension=extension-cyl(22.5,UPPER_LIFT+.2,z0=41.9)
    for angle in range(0,360,60):
        extension=extension-annular_sector(18,30,angle+10,angle+50,9+UPPER_LIFT,35)
    gear_journal=gear_journal+extension
for x,y in P04_MOUNTS:
    # Boss material remains inside the original tooth-root circle. Nut wells
    # open at Z36, with a 1.4mm roof and full M3 nut engagement on M3x8.
    boss=cyl(12,P04_GEAR_HEIGHT,x,y,36) & cyl(68.8,P04_GEAR_HEIGHT,z0=36)
    gear_journal=gear_journal+boss
    carrier=carrier+cyl(10,3.4,x,y,42)
    carrier=carrier-hole(x,y,41.8,4)-cyl(6.4,1.7,d2=3.4).rot(x=180).move(x,y,45.5)
    gear_journal=gear_journal-hole(x,y,35.8,7+UPPER_LIFT)-cyl(6.7,4.7+UPPER_LIFT,x,y,35.9,n=6)
# Asymmetric tongue provides XY/yaw location. Put the male feature on A so
# neither B nor A needs to stand on small locating pegs during printing.
carrier=carrier+box(6,8,1.2,31,0,40.8)
gear_journal=gear_journal-box(6.4,8.4,1.5,31,0,40.6+UPPER_LIFT)
add("P04A","分離式旋轉承載盤",carrier,color=PLATE,rot=(180,0,0),support="上方大平面朝下；局部孔槽待切片",note="與P04B配套。上方大平面貼床，底面偏心矩形榫定位防轉；四顆M3×8從上方鎖入P04B捕捉螺母。先組成轉盤，再裝P31與牌倉。")
add("P04B","加厚60齒齒輪與空心轉軸",gear_journal,color=ORANGE,rot=(180,0,0),support=f"Z{P04_MATE_Z:g}齒輪大平面朝下、空心軸朝上；6.4mm定位槽局部橋接待切片",note=f"齒寬{P04_GEAR_HEIGHT:g}mm，齒底Z36及軸承肩臺Z31保持；上接合面由Z42提高{UPPER_LIFT:g}mm至Z{P04_MATE_Z:g}。原P04A沿用，上部裝配整體抬升，使P04A下平面與P02A圓環頂的名義間隙0.5增至{.5+UPPER_LIFT:g}mm。四個螺母與定位槽同步上移，原M3×8沿用。需配延長遮光片P26；P05、P06、滑環位置不變。")

# P05: separate closed clamp hub and gear with a mechanical retaining skirt.
P05_CLAMP_Z=35.4
P05_CLAMP_Y=7.5
P05_HEAD_X=57.6
P05_NUT_X=49.8
P05_JOIN_MOUNTS=[(44,-1),(64,-1)]
P05B_FLAT_Y=-10.5
P05A_CAVITY_FLAT_Y=P05B_FLAT_Y-.2
dshaft=cyl(5.2,15,54,0,29)-box(8,5,17,54,4.15,28)-box(8,5,17,54,-4.15,28)
P05_PROFILE=cyl(12.4,12,54,0,32)+box(11.4,10.4,12,54,7.5,32)
pinion_gear=gear(30,1.2,6,34).rot(z=6).move(54,0)+cyl(32.8,4.5,54,0,33.3)
P05A_ROUND_CAVITY=cyl(30.8,5.6,54,0,32.2)
P05A_D_CAVITY=P05A_ROUND_CAVITY & box(80,80,12,54,P05A_CAVITY_FLAT_Y+40,31)
P05A_ROUND_CAVITY_BASE=pinion_gear-P05A_ROUND_CAVITY-P05_PROFILE
pinion_gear=pinion_gear-P05A_D_CAVITY-P05_PROFILE
for x,y in P05_JOIN_MOUNTS:
    pinion_gear=pinion_gear-hole(x,y,33,9,3.4)
    pinion_gear=pinion_gear-cyl(6.4,1.5,d2=3.4).rot(x=180).move(x,y,40.2)
    P05A_ROUND_CAVITY_BASE=P05A_ROUND_CAVITY_BASE-hole(x,y,33,9,3.4)
    P05A_ROUND_CAVITY_BASE=P05A_ROUND_CAVITY_BASE-cyl(6.4,1.5,d2=3.4).rot(x=180).move(x,y,40.2)
add("P05A","平口內腔30齒輪與止退裙邊",pinion_gear,color=ORANGE,rot=(180,0,0),support="上方大平面朝下；沉孔與裙邊局部橋接待切片",note="配平面版P05B。內腔改D形，內側平口Y−10.7對B的Y−10.5，預留0.2mm名義側隙；僅A需重印，平面版B可沿用。保留完整30齒、模數1.2、6mm齒寬與中心，頂面40。異形孔防轉、兩顆M3×8垂直固定；外裙封住三處側載螺母入口及橫螺絲外退路徑。先鎖夾座再套齒輪，不能硬鎖緊配平口；實印公差待試配。")

pinion_hub=cyl(12,9.5,54,0,30.5)+box(11,10,9.5,54,7.5,30.5)+cyl(30.4,4.6,54,0,33.2)
pinion_hub=pinion_hub-(box(50,50,3,54,0,30.2)-cyl(23.6,3.2,54,0,30.1))
pinion_hub=pinion_hub-dshaft-box(.6,18,11,54,9.5,30.4)
pinion_hub=pinion_hub-cylx(3.4,35,47,7.5,35.4)
# A full 90-degree cone, never opened from above. The +X entry is accessible
# while the gear is absent, and is blocked by the gear after assembly.
P05_CLOSED_SEAT=cyl(6.4,1.5,d2=3.4).rot(y=-90).move(57.8,7.5,35.4)
pinion_hub=pinion_hub-P05_CLOSED_SEAT-cylx(7.2,23,57.8,7.5,35.4)
# The cage opens toward +Y, perpendicular to the horizontal screw axis.
# Continuous roof and floor guide the nut; the gear skirt closes the exit.
P05_CLAMP_NUT_SLOT=cyl(6.7,2.9,n=6).rot(z=30).rot(y=90).move(49.55,7.5,35.4)
P05_CLAMP_NUT_SLOT=(P05_CLAMP_NUT_SLOT+box(2.9,18,5.8,51,16.5,32.5)) & box(4,30,7,51,12,32.5)
pinion_hub=pinion_hub-P05_CLAMP_NUT_SLOT
for x,y in P05_JOIN_MOUNTS:
    pinion_hub=pinion_hub-hole(x,y,33.1,6,3.6)-cyl(6.7,2.6,x,y,34,n=6)
    direction=-1 if x<54 else 1
    pinion_hub=pinion_hub-box(12,6,2.6,x+direction*6,y,34)
# Print on a purpose-made back flat rather than suspend the large flange.
# The two end chamfers grow at 45 degrees in the new print direction; they
# stay outside the D bore and outside every closed fastener support region.
P05B_PRINT_BASE=pinion_hub
P05B_LOWER_CHAMFER=poly([(-20,30.4),(-3.2,30.4),(-5.98,33.18),(-20,33.18)],40).basis((0,1,0),(0,0,1),(1,0,0),(34,0,0))
P05B_UPPER_CHAMFER=poly([(-20,37.82),(-5.98,37.82),(-3.7,40.1),(-20,40.1)],40).basis((0,1,0),(0,0,1),(1,0,0),(34,0,0))
pinion_hub=pinion_hub-box(80,40,30,54,-30.5,20)-P05B_LOWER_CHAMFER-P05B_UPPER_CHAMFER
add("P05B","平面貼床式閉合D軸夾座",pinion_hub,color=LIGHT,rot=(90,0,0),support="負Y側平面貼床；建議3至5mm brim，孔頂與螺母槽局部橋接待切片",note="背側削成約22×4.6mm平面，配兩處45度外形削角，依STL側放列印，減少法蘭懸空；仍須檢查孔頂橋接。先從正Y側放橫向M3螺母，再沿X側裝M3×8；保留完整360度沉頭座、閉合3.4mm導向孔與D軸配合面。馬達與P02A先就位，再套D軸，用符合工具圖尺寸的2mm L型扳手鎖緊，最後裝P05A。兩顆垂直固定螺母從左右側裝入，由齒輪裙邊封住入口；螺絲與螺母仍需保持咬合，夾持力與實印公差待試配。")

collar=cyl(33,6,z0=13)+box(6,8,7.5,-16,0,11.5)+box(2,8,4,16,0,13.5)
collar=collar-cyl(25.2,9,z0=11.3)-cylx(3.4,9,-19.1,0,15.5)
# Head floats in a cylindrical counterbore: it is used as a light-pressure
# radial screw, not tightened against a countersink. Nut loads the 1.2mm inner
# wall. The top-loading nut channel is closed by the bearing after assembly.
collar=collar-cylx(6.6,2.5,-19.2,0,15.5)
nut_slot=cyl(6.7,2.7,n=6).rot(z=30).rot(y=90).move(-16.5,0,15.5)
nut_slot=(nut_slot+box(2.7,6.7,7,-15.15,0,15.5)) & box(4,9,10,-15.15,0,12.75)
collar=collar-nut_slot
add("P06","捕捉螺母式空心轉軸止退環",collar,color=ORANGE,rot=(180,0,0),support="軸承側環形平面朝下；小孔槽局部橋接待切片",note="先由上方裝M3螺母，再從軸底端套入P04B並對齊徑向孔。M3×8穿通孔後僅輕壓滑環轉子；圓柱沉孔留微調行程，不要求螺絲頭到底。實物滑環殼體可承受壓力與抗轉能力待試裝。")

spacer=cyl(9,16.2,z0=45.4)-cyl(3.4,18,z0=44.5)
add("P07","牌倉支柱",spacer,qty=4,color=LIGHT,note="四支位於(-45/31, ±26)，使用M3沉頭長螺絲。")

# P08 open-ended width-only hopper. No rear wall, no longitudinal stop.
tray=box(106,4.5,2.4,-2,-32.25,61.6)+box(106,4.5,2.4,-2,32.25,61.6)+box(106,4,2.4,-2,0,61.6)
for xx in [-45,-22,31]: tray=tray+box(8,77,2.4,xx,0,61.6)
tray=tray-slotz(-22,7,60,23,12,6)
for side in [-1,1]:
    y=side*(61/2+1.2)
    tray=tray+box(94,2.4,7,-4,y,63.9)
    for x in [-44,26,38]: tray=tray+box(6,2.4,P["hopper_rail_height_mm"],x,y,64)
    # Gate slide attachment ears, outside the card channel.
    tray=tray+box(6,9,16,40,side*37,63.9)
    tray=tray-cylx(3.4,18,35,side*37.5,72)
    tray=tray-cylx(6.4,4.6,35,side*37.5,72)
    tray=tray-cyl(6.4,1.7,d2=3.4).rot(y=90).move(39.4,side*37.5,72)
for x in [-45,31]:
    for y in [-26,26]:
        tray=tray-hole(x,y,60,7)
        tray=tray-cyl(3.4,2,x,y,62,d2=6.4)
add("P08","61mm前後開放牌倉",tray,color=LIGHT,note="內寬61mm。前後無擋板，87/96mm長牌可用，其他長度需試送。")

# Separation gate moves vertically. Its lower edge is shimmed from the deck floor.
gate=box(6,66,11,47.5,0,64.45)+box(7.5,10,14,46.75,-37.5,64.45)+box(7.5,10,14,46.75,37.5,64.45)
gate=gate-box(9,55,6,48,0,70.5)
gate=gate-box(1.1,55.2,4.1,45,0,64.4)
for side in [-1,1]:
    # Vertical slot for M3 bolt, through X direction.
    cut=rr(7.5,3.6,1.7,18,0,0,0).rot(y=90).move(39,side*37.5,70.2)
    gate=gate-cut
    gate=gate-box(6,5.8,11.5,47.8,side*37.5,66.25)
add("P09","可調單張分牌閘",gate,color=ORANGE,rot=(0,90,0),support="固定耳局部支撐",note="起始間隙0.45mm；以實際牌厚調整。下緣貼小片橡膠分牌墊。")

follower=rr(51,55,4,3,-22,0,97)
follower=follower-rr(35.5,39.5,2.5,1.5,-22,0,98.6)
follower=follower-box(6,12,.3,-22,8,96.95)
add("P10","選配重力壓牌滑板",follower,color=ORANGE,note="選配；直接放在牌疊上，自由下落。底面磨平，35.5×39.5mm淺槽供P11定位。無導桿、無彈簧。")
weight=rr(35,39,2,20,-22,0,98.6)
add("P11","選配列印配重塊",weight,color=ORANGE,note="選配；壓力不足才放在P10上。可改列印高度或填充率調重量；100%實心約33g。需實秤。")

# Narrow-card spacers only occupy the width, leaving both ends open.
shim=box(82,1.5,44.1,-4,29.75,64)
for xx in [-44,36]:
    shim=shim+box(5,5.9,2,xx,31.95,108)+box(5,1.5,7,xx,34.15,103)
add("P12","57mm窄牌側墊",shim,qty=2,color=ORANGE,rot=(90,0,0),support="卡鉤需要局部支撐",note="57mm牌左右各一片，內寬約58mm；卡鉤跨在側柱頂，60mm牌取下。左右件以Z軸轉180度裝配。")

# Roller bearing pedestals. Two 623ZZ lower and two 623ZZ upper.
def pillow(side):
    y=side*35
    a=rr(25,12,3,4,61,y,45.4)
    a=a+box(20,7,19,61,y,49.3)
    a=a+box(3.0,7,19,52.5,y,67)+box(3.0,7,19,69.5,y,67)
    a=a+box(20,7,4,61,y,83)
    a=a-cyly(3.5,15,61,y-7.5,54.2)
    # Seat opens towards the roller.
    a=a-cyly(10.3,7.5,61,-35.8 if side<0 else 28.3,54.2)
    a=a-hole(61,y,81,9,2.7)
    a=a-cyl(3.8,.6,d2=2.7).rot(x=180).move(61,y,87.1)
    a=a-cylx(2.7,9,63,y,60)
    for x in [52.5,69.5]:
        a=a+cyl(8,2.1,x,y,49.3)
        a=a-hole(x,y,44,10)-nut(x,y,45.3,.9)
        a=a-cyl(6.4,1.7,d2=3.4).rot(x=180).move(x,y,51.5)
    return a
add("P13","左出牌滾輪座",pillow(-1),color=LIGHT,support="軸承孔局部支撐")
add("P14","右出牌滾輪座",pillow(1),color=LIGHT,support="軸承孔局部支撐")
carrier=box(13.3,6.5,12,61,-35,68.75)
carrier=carrier-cyly(3.5,10,61,-40,74.75)-cyly(10.3,4.3,61,-35.8,74.75)
add("P15","上滾輪調整滑塊",carrier,qty=2,color=ORANGE,rot=(90,0,0),note="左右對稱裝入導槽，以頂部M3螺絲調整夾持間隙。")

def roller(width,bore):
    # Local axis Z; two silicone O-rings 16mm ID x 2mm cross-section.
    s=cyl(18.4,width)
    for zc in ([2,width-2] if width<=10 else [3,width-3]):
        s=s-(cyl(22,2.3,z0=zc-1.15)-cyl(16.8,2.6,z0=zc-1.3))
    s=s-cyl(bore,width+2,z0=-1)
    if width>20:
        # Lightening cavities do not reach shaft clamp hub.
        s=s-(cyl(13,width-12,z0=6)-cyl(7,width-10,z0=5))
    return s

def shaft_clamp(s,x,y,z,width):
    """Split hub, one M3x8 flat socket screw + standard M3 nut.

    Head and nut remain below the hard OD19mm envelope. The feed-wheel
    band stays BETWEEN its two O-ring grooves; no shaft filing required.
    """
    s=s+cyly(19,3.6,x,y-1.8,z)
    s=s-cyly(3.15,width+.4,x,y-width/2-.2,z)
    s=s-box(13,width+.2,.6,x+7.7,y,z-.3)
    s=s-hole(x+5,y,z-10,21)
    s=s-cyl(6.4,1.7,d2=3.4).rot(x=180).move(x+5,y,z+3.3)
    s=s-cyl(6.4,8,x+5,y,z+3.2)
    s=s-nut(x+5,y,z-10,8)
    return s

drive=roller(54,3.15).rot(x=-90).move(61,-27,54.2)
drive=shaft_clamp(drive,61,0,54.2,54)
add("P16","出牌滾輪輪芯",drive,qty=2,color=PLATE,rot=(90,0,0),note="兩件相同；開縫輪轂用M3×8沉頭及M3螺母夾緊，取消止付。硬輪轂外徑19mm，O圈維持原規格。")
feed=roller(10,3.15).rot(x=-90).move(-22,3,54)
feed=shaft_clamp(feed,-22,8,54,10)
add("P17","取牌輪輪芯",feed,color=PLATE,rot=(90,0,0),note="N20的3mm D軸；M3×8沉頭＋M3螺母夾緊，O型圈×2，取消止付。")

# N20 cradle and clamp sit fully under the hopper floor.
n20=rr(28,34,3,3,-22,-11,45.4)
n20=n20+box(4.8,30,10.7,-30.4,-11,48.3)+box(4.8,30,10.7,-13.6,-11,48.3)
n20=n20+box(16,30,.7,-22,-11,48.3)
for x in [-33,-12]: n20=n20-hole(x,-19,44,9)-cyl(6.4,1.6,d2=3.4).rot(x=180).move(x,-19,48.5)
for x in [-30.4,-13.6]: n20=n20-hole(x,-11,47,16,2.7)
n20=n20-box(50,15,30,-22,10,43)
add("P18","N20取牌馬達底座",n20,color=LIGHT)
n20strap=rr(25,8,2,2.2,-22,-11,59.0)
for x in [-30.4,-13.6]:
    n20strap=n20strap+cyl(8.4,3.2,x,-11,59)
    n20strap=n20strap-hole(x,-11,58,6)-cyl(6.4,1.7,d2=3.4).rot(x=180).move(x,-11,62.3)
add("P19","N20馬達壓片",n20strap,color=ORANGE)

# RF300 long-shaft motor and printed 2mm-to-3mm coupling.
rf=rr(36,27,4,3,61,-59,45.4)
rf=rf+box(6,24,16.9,46.5,-60,48.3)+box(6,24,16.9,75.5,-60,48.3)
rf=rf-cyly(24.8,24,61,-72,54.2)
for x in [46.5,75.5]: rf=rf-hole(x,-60,43,27)-nut(x,-60,43.4,2.6)
add("P20","RF300出牌馬達底座",rf.move(y=-14.3),color=LIGHT,note="RF300約24.4mm、長軸約18mm。兩顆M3×25同時固定壓片、馬達座及P31，取消另外兩顆底座螺絲。")
rfstrap=rr(35,8,3,3,61,-60,65.2)
rfstrap=rfstrap-cyly(24.8,12,61,-66,54.2)
for x in [46.5,75.5]: rfstrap=rfstrap-hole(x,-60,64,7)-cyl(6.4,1.7,d2=3.4).rot(x=180).move(x,-60,68.3)
add("P21","RF300馬達壓片",rfstrap.move(y=-14.3),color=ORANGE,rot=(180,0,0))
coupler=cyly(19,18,61,-59.3,54.2)-cyly(2.15,9.5,61,-59.8,54.2)-cyly(3.15,10.8,61,-50.5,54.2)
for yy in [-55.3,-44.8]:
    coupler=coupler-box(13,8,.6,68.7,yy,53.9)
    coupler=coupler-hole(66,yy,44,21)-nut(66,yy,44.2,8)
    coupler=coupler-cyl(6.4,1.7,d2=3.4).rot(x=180).move(66,yy,57.5)-cyl(6.4,8,66,yy,57.4)
add("P22","2mm至3mm軸聯軸器",coupler,color=ORANGE,rot=(90,0,0),note="兩端獨立開縫，各M3×8沉頭＋M3螺母夾緊；取消止付。外徑19，需用新版P31避讓。")

guide=box(22,61,1.8,63,0,61.9)+box(22,.8,6,63,-30.9,61.9)+box(22,.8,6,63,30.9,61.9)
guide=guide+box(12,9,3,79.5,27,60.7)
guide=guide-box(14,57,4,61,0,61)
for y in [-35,35]:
    guide=guide+box(5,10,9,73.5,y,55)
    guide=guide-cylx(3.4,9,69,y,60)
    guide=guide-cyl(6.4,1.6,d2=3.4).rot(y=-90).move(76.1,y,60)
guide=guide-box(12,8,8,77,21,61.8)
guide=guide-hole(81,27,59,10)
guide=guide-cyl(6.4,1.7,d2=3.4).rot(x=180).move(81,27,63.8)
add("P23","出牌導向槽",guide,color=LIGHT,support="需要局部支撐",note="兩側M3水平鎖入滾輪座，出口留光電避讓缺口。滾輪接觸面以O型圈為準。")

sensor=rr(19,11,2,3,77,27,57.5)
sensor=sensor+box(15,3,3.7,79,21,60)
sensor=sensor+box(8,9,1.5,72,27,59.2)
for x in [72,81]: sensor=sensor-slotz(x,27,56,3.5,8,6)
sensor=sensor.move(x=9)-box(8,8,15,91,30.5,57.5)
sensor=sensor+box(12,3,18.4,91,34.5,55.1)+box(3,6,5.4,85,31,55.1)+box(15,5,2.2,90.5,33.5,55.1)
for xx in [89.73,92.27]:
    for zz in [59.3,69.3]: sensor=sensor-cyly(1.2,10,xx,30,zz)
for xx in [87.5,94.5]: sensor=sensor-box(1.4,10,3.5,xx,34.5,62.55)
sensor=sensor-box(7,12,4,81,27,54.4)
add("P24","出口光電感測器可調座",sensor,color=ORANGE,note="按13×6.8×6mm、5mm槽寬ITR9608-F包絡；57mm牌時連同感測器向內移1.5mm，8mm長孔調整。")

home=rr(18,13,2,3,-70.5,10,27)+box(13,3,11,-74.5,14.9,29)
home=home-box(8,5,6,-74.5,14.9,35.3)
home=home+cyl(10,3,-63.5,10,27)
home=home-hole(-63.5,10,26,6)
home=home-cyl(6.4,1.7,-63.5,10,26.9,d2=3.4)
home=home-box(4,30,3.1,-81.4,10,26.9)
for xx in [-79.5,-69.5]:
    for yy in [8.73,11.27]: home=home-hole(xx,yy,26,8,1.2)
for xx in [-79.5,-69.5]: home=home-box(1.4,8,3,xx,14.9,32.8)
add("P25","旋轉參考光電座",home,color=ORANGE,note="用於每圈參考標記。螺絲長孔可校正位置。")
flag=box(1,7,6.4+UPPER_LIFT,-74.5,10,35.6-UPPER_LIFT)+rr(25,10,2,1.4,-65.5,10,40.6)
flag=flag-hole(-58,10,39,7)-cyl(6.4,1.7,-58,10,40.5,d2=3.4)
add("P26","延長式轉盤光電遮光片",flag,color=ORANGE,rot=(180,0,0),note=f"配P04B抬升{UPPER_LIFT:g}mm：薄片向下延長{UPPER_LIFT:g}mm，組裝後下緣仍為Z35.6，保留原參考感測器遮光區及槽底0.3mm名義間隙；安裝孔及支臂沿用。")

# Top buttons: the flange sits 0.6mm above the roof, with a modeled 0.35mm stroke.
cap=cyl(9,2,75,4,129.3)+cyl(5.6,4.85,75,4,124.95)
cap=cap-cyl(3.2,2.8,75,4,124.75)
add("P27","頂按式按鍵帽",cap,qty=4,color=ORANGE,rot=(180,0,0),note="自上方按壓；6×6×9.5mm輕觸鍵。帽底至屋頂0.6mm，檢查0至0.35mm行程。")

screen=rr(31,32,3,2,75,-24,121)-box(23,23.5,4,75,-24,120)
screen=screen-box(8,9,5,75,-39.5,120)
for x in [57,93]:
    screen=screen+cyl(8,3.5,x,-24,119.5)
    screen=screen-hole(x,-24,118,7)-cyl(6.4,1.7,x,-24,119.4,d2=3.4)
for x in [62,88]: screen=screen-box(1.4,3.5,5,x,-24,120)
add("P28","頂部OLED固定框",screen,color=LIGHT,note="27.3×27.8mm板件基準；兩顆M3×8沉頭由下方固定，加厚耳座避免螺絲頂穿外罩。")
clip=box(6,28,3.6,-20,55,22)+box(6,3,7.6,-20,41,17)+box(6,3,7.6,-20,69,17)
clip=clip-cylx(19.6,8,-24,55,14)
add("P29","18650電池盒束帶壓扣",clip,qty=2,color=ORANGE,rot=(180,0,0),note="弧形避讓電芯，側翼壓在電池盒邊緣；束帶穿內部橋座固定，不壓電芯凸起處。")

# Print these small samples before the main model.
coupon=rr(58,23,3,4)
for x,d in [(-20,3.0),(-10,3.2),(0,3.4),(10,5.0),(20,5.2)]: coupon=coupon-hole(x,0,-1,7,d)
coupon=coupon+box(5,15,3,-20,0,3.9)
coupon=coupon-hole(-20,0,-1,9,3.0)
add("P30","孔徑試配片",coupon,color=ORANGE,note="3.0／3.2／3.4／5.0／5.2mm，先調整擠出量及孔補償。此件不裝入成品。")

# Assembly placements for repeated printable items.
placements={
 "P07":[(-45,-26,0),(-45,26,0),(31,-26,0),(31,26,0)],
 "P12":[(0,0,0),(0,0,0)],
 "P15":[(0,0,0),(0,0,0)],
 "P16":[(0,0,0),(0,0,20.55)],
 "P27":[(0,y,0) for y in [0,13,26,39]],
 "P29":[(0,0,0),(45,0,0)],
 "P36":[(0,0,0)]*3,
}

def assembly_printables():
    for p in parts:
        if p.id in {"P10","P11","P12","P30"}: continue
        for idx,pose in enumerate(placements.get(p.id,[(0,0,0)])):
            shape=p.shape
            if p.id=="P12" and idx==1: shape=shape.rot(z=180).move(x=-8)
            if p.id=="P15" and idx==1: shape=shape.rot(z=180).move(x=122)
            if p.id=="P36": shape=shape.rot(z=idx*120)
            shape=shape.move(*pose)
            shape=assembly_pose(p.id,shape)
            yield p.id,p.name,shape,p.color

# Reference purchased hardware; omitted from print files.
hardware=[]
def hw(name,shape,color=METAL): hardware.append((name,shape,color))
hw("6005ZZ",cyl(47,12,z0=19)-cyl(25,14,z0=18))
step_shaft=cyl(5,9,54,0,30)-box(8,5,11,54,4,29)-box(8,5,11,54,-4,29)
stepper=cyl(28,19,47,0,11)
for sy in [-1,1]: stepper=stepper+box(12,8,1.5,47,sy*16.5,28.5)-hole(47,sy*17.5,28,3)
hw("28BYJ-48",stepper,METAL)
hw("stepper_output",step_shaft,METAL)
for side in [-1,1]:
    hw("lower623",cyly(10,4,61,side*33-2,54.2)-cyly(3,6,61,side*33-3,54.2))
    hw("upper623",cyly(10,4,61,side*33-2,74.75)-cyly(3,6,61,side*33-3,74.75))
hw("lower3mmshaft",cyly(3,92,61,-50,54.2))
hw("upper3mmshaft",cyly(3,82,61,-40,74.75))
hw("N20",box(12,26,10,-22,-11,49)+cyly(3,10,-22,2,54),METAL)
hw("RF300",(cyly(24.4,13.5,61,-67.5,54.2)+cyly(2,18,61,-54,54.2)).move(y=-14.3),METAL)
hw("slipring_rotor",cyl(22,24.5,z0=9.8),RUBBER)
flange=cyl(44.5,2,z0=7.8)-cyl(22.4,4,z0=6.8)
for x,y in SLIP_MOUNTS: flange=flange-hole(x,y,7,4,2.4)
hw("slipring_flange",flange,METAL)
for z in [54.2,74.75]:
    for y in [-24,24]:
        # Simple solid-ring reference silhouette, actual O-ring is circular section.
        hw("silicone",cyly(P["roller_rubber_od_mm"],2,61,y-1,z)-cyly(16.8,4,61,y-2,z),RUBBER)
for y in [5,11]: hw("feedrubber",cyly(P["roller_rubber_od_mm"],2,-22,y-1,54)-cyly(16.8,4,-22,y-2,54),RUBBER)
hw("batteryholder",rr(78,22,3,19,0,55,3)-cylx(18.8,68,-34,55,14),RUBBER)
hw("18650",cyl(18.4,65,n=48).rot(y=90).move(-32.5,55,14),(84,126,130))
hw("ESP32C3",box(23,32,2,-58,-1,8)+box(19,28,8,-58,-1,9.9),PCB)
hw("PCF8574",box(2,29,20,88,23.5,92)+box(7,25,16,92.4,23.5,94),PCB)
hw("charger",box(25,17,1.6,-67,-36.5,8)+box(18,13,4.1,-65,-36.5,9.5),PCB)
hw("TypeC",box(8,9.5,3.4,-79,-36.5,9.6),METAL)
hw("booster",box(32,20,2,-27,-38,6)+box(28,16,10,-27,-38,7.9),PCB)
hw("protection1S",box(12,15,2,-30,22,6)+box(10,13,3,-30,22,7.9),PCB)
hw("ULN2003",box(34,34,2,23,-42,6)+box(30,30,10,23,-42,7.9),PCB)
hw("screenpcb",box(27.3,27.8,1.6,75,-24,123)+box(21,20,2.1,75,-24,121),PCB)
hw("OLEDglass",box(19.3,26.7,1.3,75,-24,126.7),(12,25,30))
hw("screenheader",box(8,2.5,12,75,-37.9,111),METAL)
hw("keypcb",box(14,51,1.6,75,23.5,116.4),PCB)
for yy in [4,17,30,43]:
    hw("keybody",box(6,6,3.5,75,yy,118),RUBBER)
    hw("keyplunger",cyl(2.8,6,75,yy,121.5),METAL)
hw("powerrocker",box(5,10,15,82,-1,7),(22,27,29))
# Card pile, 108 cards of reference 60x96mm stock. Both ends remain open.
hw("cards",box(96,60,32.4,-3.5,0,64),(234,231,220))
for k in range(1,108,3): hw("cardedge",box(96.05,60.05,.08,-3.5,0,64+k*.3),(166,169,162))

# Feed components share one inclined coordinate system; the yaw bearing stays level.
TILTED={f"P{i:02}" for i in range(7,25)}
def incline(s):
    return s.move(z=-P["card_floor_z_mm"]).rot(y=P["hopper_tilt_deg"]).move(z=P["card_floor_z_mm"]+P["hopper_lift_mm"])

# P31 is a connected wedge frame with a horizontal bottom and a 6-degree top.
frame=box(130,8,25,14,-26,20.4)+box(130,8,25,14,26,20.4)
for x in [-45,31]: frame=frame+box(8,105,25,x,0,20.4)
frame=frame+(rr(38,116,6,25,61,-14,20.4)-rr(28,106,3,27,61,-14,19.4))
for y in [-60,-35,35]: frame=frame+box(38,8,25,61,y,20.4)
frame=frame+rr(28,34,3,25,-22,-11,20.4)
frame=frame+rr(40,29.2,4,25,61,-73.3,20.4)
frame=incline(frame)-box(400,400,100,z0=-54.6)
for x,y in [(-45,-26),(-45,26),(31,-26),(31,26),(-33,-19),(-12,-19),(46.5,-74.3),(75.5,-74.3),(52.5,-35),(69.5,-35),(52.5,35),(69.5,35)]:
    nz=43.4 if (x in [52.5,69.5] and abs(y)==35) or y==-74.3 else 42.8
    frame=frame-incline(hole(x,y,30,22))-incline(nut(x,y,nz,4))
frame=frame-incline(cyly(24.8,25,61,-86.3,54.2))
frame=frame-incline(cyly(21.3,54.6,61,-27.3,54.2))-incline(cyly(21.3,10.6,-22,2.7,54))
frame=frame-incline(cyly(19.6,19.5,61,-59.8,54.2))
frame=frame-box(19,17,45,-47,11,30)
for x in [-45,31]:
    for y in [-44,44]:
        frame=frame-hole(x,y,44,30)-cyl(6.4,30,x,y,48.9)
        frame=frame-cyl(6.4,1.7,d2=3.4).rot(x=180).move(x,y,49.0)
add("P31","6度下傾轉接框",frame,color=ORANGE,note="平底鎖在旋轉盤，上斜面承接整組牌路；下傾6度、抬高10mm以避讓馬達。支撐建議待切片核對。")
tilted_hardware={"lower623","upper623","lower3mmshaft","upper3mmshaft","N20","RF300","silicone","feedrubber","cards","cardedge"}
hardware=[(name,incline(shape) if name in tilted_hardware else shape,color) for name,shape,color in hardware]

# Datasheet envelope of ITR9608-F, excluding details below 0.5mm.
def itr9608():
    sensor=box(13,6.8,6)-box(5,8,5,0,0,2)
    for x in [-5,5]:
        for y in [-1.27,1.27]: sensor=sensor+cyl(.4,6,x,y,-6)
    return sensor
hw('home_opto',itr9608().move(-74.5,10,33.3),RUBBER)
hw('exit_opto',incline(itr9608().basis((0,0,1),(-1,0,0),(0,-1,0),(91,33,64.3))),RUBBER)
hw('DRV8833',box(18,2,20,-30,-88,58)+box(14,6,16,-30,-84.1,60),PCB)

# P32 rotates with the head. Large service openings reach its lower edge so
# the upside-down print does not need to bridge across an entire access window.
P32_Y_MIN=P['upper_housing_body_min_y_mm']
P32_Y_MAX=P['upper_housing_body_max_y_mm']
P32_SEAM_Y=P['upper_housing_seam_y_mm']
P32_SEAM_GAP=P['upper_housing_seam_gap_mm']
P32_BODY_WIDTH=P32_Y_MAX-P32_Y_MIN
P32_BODY_CENTER_Y=(P32_Y_MAX+P32_Y_MIN)/2
HOOD_JOIN_MOUNTS=[(x,-50.5) for x in (-56,-18,20,64)]
HOOD_JOIN_HEAD_Z=118.5
HOOD_JOIN_NUT_Z=123.1
HOOD_JOIN_INTERFACE_Z=122.5
P32_LAP_END_Y=P['upper_housing_lap_end_y_mm']
P32_LAP_SKIN=P['upper_housing_lap_skin_mm']
P32_B_SETBACK=P['upper_housing_b_setback_mm']
P32_LAP_CLEARANCE=P['upper_housing_lap_clearance_mm']
P32_A_ROOF_TOP_Z=128.7
P32_A_LAP_ROOF_BOTTOM_Z=P32_A_ROOF_TOP_Z-P32_LAP_SKIN
P32_B_ROOF_TOP_Z=P32_A_ROOF_TOP_Z-P32_B_SETBACK
P32_B_ROOF_INNER_Z=P32_B_ROOF_TOP_Z-2.2
P32_B_OUTER_X=(-73+P32_B_SETBACK,101-P32_B_SETBACK)
P32_B_INNER_X=(-70.8+P32_B_SETBACK,98.8-P32_B_SETBACK)
hood=(rr(174,P32_BODY_WIDTH,14,94.2,14,P32_BODY_CENTER_Y,34.5)
      -rr(169.6,P32_BODY_WIDTH-4.4,11.8,94.4,14,P32_BODY_CENTER_Y,32.1))
P32_BASE_SHELL=hood
hood=hood-rr(130,72,6,70,-15,0,70)
hood=hood-box(96,18,82.1,20,-96,34.4)
exit_cut=rr(74,44.1,4,18,0,52.45,0).basis((0,1,0),(0,0,1),(1,0,0),(92,0,0))
hood=hood-exit_cut
# The top controls share the front roof band; no controls remain on the base wall.
hood=hood-rr(15,25,.5,6,75,-24,125)
hood=hood-rr(20.3,27.7,.5,1.8,75,-24,126.3)
for yy in [4,17,30,43]: hood=hood-hole(75,yy,125,8,6.2)
OLED_MOUNTS=[(57,-24),(93,-24)]
KEY_MOUNTS=[(x,y) for x in [62.5,87.5] for y in [0,47]]
for x,y in OLED_MOUNTS:
    hood=hood+cyl(7,3.6,x,y,123)
    hood=hood-hole(x,y,119,8.6,2.7)
for x,y in KEY_MOUNTS:
    hood=hood+cyl(7,10.2,x,y,116.4)
    hood=hood-hole(x,y,112,15,2.7)
for zz in [58,74]:
    anchor=box(12,5.4,4,-30,-91.7,zz)-box(6,6,1.5,-30,-91.4,zz+1.25)
    hood=hood+anchor
for x,z in [(-32,46.5),(72,46.5),(-32,120),(72,120)]:
    hood=hood+cyly(8,7.2,x,-95.9,z)
    hood=hood-cyly(2.7,13,x,-100,z)
for y in [-44,44]:
    hood=hood+cylx(8,7.2,92,y,51.2)
    hood=hood-cylx(2.7,15,90,y,51.2)
for x,y in HOUSING_MOUNTS:
    hood=hood+cyl(10,8,x,y,45.4)
hood=hood+box(14,10,8,-66,0,45.4)+box(10,16,8,72,57,45.4)+box(10,8,8,0,61,45.4)
# Sloping webs support the mounting feet when printed roof-down.
hood=hood+poly([[-73,53.3],[-59,53.3],[-73,67.4]],10).basis((1,0,0),(0,0,1),(0,-1,0),(0,5,0))
hood=hood+poly([[49,53.3],[96,53.3],[96,100.4]],10).basis((0,1,0),(0,0,1),(1,0,0),(67,0,0))
hood=hood+poly([[52,53.3],[96,53.3],[96,97.4]],10).basis((0,1,0),(0,0,1),(1,0,0),(-5,0,0))
for x,y in HOUSING_MOUNTS:
    hood=hood-hole(x,y,43,14)-nut(x,y,47.3,7.5)
chin=poly([[80,25],[110,25],[110,46.5],[80,34.5]],230).basis((1,0,0),(0,0,1),(0,-1,0),(0,115,0))
hood=hood-chin
hood=hood-box(500,500,143,z0=-100)
hood=hood-box(8,14,12,-51.8,0,44)
P32_UNSPLIT_ENVELOPE=hood
# The rear wall and every existing mounting position stay fixed. The new
# positive-Y side balances the unchanged P33 outer face at Y=-98.2. A seam
# behind the controls keeps both roof-down print footprints below 175mm.
hood_a=hood & box(500,400,200,0,P32_SEAM_Y+P32_SEAM_GAP/2+200,0)
# Thin outer roof/side skin covers B without rising above the existing large
# print-bed plane. Its visible edge is an intentional shoulder, not a butt seam.
lap_band=box(500,P32_SEAM_Y+P32_SEAM_GAP/2+.1-P32_LAP_END_Y,200,
             0,(P32_LAP_END_Y+P32_SEAM_Y+P32_SEAM_GAP/2+.1)/2,0)
lap_skin=(box(500,500,20,0,0,P32_A_LAP_ROOF_BOTTOM_Z)
          +box(20,500,200,-73+P32_LAP_SKIN-10,0,0)
          +box(20,500,200,101-P32_LAP_SKIN+10,0,0))
P32_A_EXTERNAL_LAP=hood & lap_band & lap_skin
hood_a=hood_a+P32_A_EXTERNAL_LAP
# Move B's outer and inner roof/side surfaces inward together, retaining the
# full 2.2mm wall rather than thinning the original side walls to 0.7mm.
# Preserve the original cuts and mounting details at their existing world poses.
b_shell=(rr(174-2*P32_B_SETBACK,P32_BODY_WIDTH,14,
             P32_B_ROOF_TOP_Z-34.5,14,P32_BODY_CENTER_Y,34.5)
         -rr(169.6-2*P32_B_SETBACK,P32_BODY_WIDTH-4.4,11.8,
             P32_B_ROOF_INNER_Z-32.1,14,P32_BODY_CENTER_Y,32.1))
P32_B_RECESSED_ENVELOPE=(b_shell-(P32_BASE_SHELL-hood))+(hood-P32_BASE_SHELL)
P32_B_RECESSED_ENVELOPE=(P32_B_RECESSED_ENVELOPE-chin
                         -box(500,500,143,z0=-100)-box(8,14,12,-51.8,0,44))
hood_b=P32_B_RECESSED_ENVELOPE & box(500,400,200,0,P32_SEAM_Y-P32_SEAM_GAP/2-200,0)
for x,y in HOOD_JOIN_MOUNTS:
    # B's L-tab carries the full closed countersink. It slides underneath A's
    # nut boss; their intended clamped contact is the plane Z=122.5.
    b_root=box(14,5.9,8.02,x,-58.05,118.5)
    # A 0.04mm root overlap avoids an isolated face-touch-only tab in STL.
    b_tab=box(14,9.64,4,x,-50.32,118.5)
    a_boss=box(14,9.4,4.02,x,-50.2,122.5)
    hood_b=hood_b+b_root+b_tab
    hood_a=hood_a+a_boss
    hood_b=hood_b-hole(x,y,118.3,4.4)-cyl(6.4,1.5,x,y,118.3,d2=3.4)
    # The axial hole stops at the inner roof plane. The 2.2mm cosmetic roof
    # remains unpierced; the standard nut has a positive-Y side-loading door.
    hood_a=hood_a-hole(x,y,122.3,4.2)
    hood_a=hood_a-cyl(6.7,2.6,x,y,123,n=6)-box(6.7,16,2.6,x,-42.5,123)
add("P32A","台階包覆式居中上殼主片",hood_a,color=LIGHT,rot=(180,0,0),support="原屋頂大平面貼床；1.2mm外蓋邊隨屋頂起印，孔槽局部橋接待切片",note="只改上殼，保留原UI、P33/P34、牌路及安裝孔。原Y=-55分件線藏在A的U形外蓋邊下；A往負Y包至-61，屋頂與兩側蓋邊厚1.2mm，外觀明確形成1.5mm階差。B退台與A留0.3mm名義間隙。含原P33前視總寬196.4，X外形174保持。原四顆M3×8與M3螺母從內側連接，先滑合兩片再裝UI，屋頂外觀面無螺絲孔；實印公差待試配。")
add("P32B","退台式上殼背側接合片",hood_b,color=LIGHT,rot=(180,0,0),support="退台後127.2mm屋頂大平面貼床；封閉沉頭孔與接合凸臺局部橋接待切片",note="B屋頂外面降1.5mm至Z127.2、內面Z125.0；兩側X外緣收至-71.5及99.5，內面同步內移，壁厚保留2.2mm。由負Y滑入A屋頂與側邊罩檐下，名義間隙0.3mm；負Y的P33側蓋、原孔與DRV固定區保持位置。原四處L搭接及螺絲承壓座沿用，先接合兩片再預裝UI。")

hatch=rr(114,92,6,2.2,20,80.5,0).rot(x=90).move(y=-96)
for x,z in [(-32,46.5),(72,46.5),(-32,120),(72,120)]:
    hatch=hatch-cyly(3.4,6,x,-100,z)
    hatch=hatch-cyl(6.2,1.4,d2=3.4).rot(x=-90).move(x,-98.3,z)
hatch=hatch-box(500,500,143,z0=-100)
add("P33","上罩側維修蓋",hatch,color=COVER,rot=(90,0,0),note="四顆M3×8沉頭螺絲固定；下緣43mm。可拆後調整馬達、分牌閘及清除卡牌。")

lip=rr(98,16.5,4,2.2,0,51.25,0).basis((0,1,0),(0,0,1),(1,0,0),(101,0,0))
for y in [-44,44]:
    lip=lip-cylx(3.4,7,99,y,51.2)
    lip=lip-cyl(6.2,1.4,d2=3.4).rot(y=-90).move(103.3,y,51.2)
add("P34","出牌口下飾蓋",lip,color=COVER,rot=(0,90,0),note="兩顆M3×8沉頭螺絲固定；安裝後保留約74×15mm出牌口。內面刻號，正面保持平整。")

keyboard=rr(20,55,3,3,75,23.5,113.4)-box(8,47,5,75,23.5,112.4)
for x,y in KEY_MOUNTS:
    keyboard=keyboard+cyl(8,3,x,y,113.4)
    keyboard=keyboard-hole(x,y,112,6)
    keyboard=keyboard-cyl(6.4,1.7,x,y,113.3,d2=3.4)
for x in [66.5,83.5]:
    for y in [10.5,36.5]: keyboard=keyboard-box(1.4,3.5,5,x,y,112.4)
spine=box(3,35,22,85.5,23.5,92)-box(5,23,15,85.5,23.5,95.5)
keyboard=keyboard+spine+box(6,35,3,85.5,23.5,113.4)
for y in [7.5,39.5]:
    for z in [98,108]: keyboard=keyboard-box(6,1.4,3.5,85.5,y,z-1.75)
add('P35','頂部按鍵與PCF支架',keyboard,color=ORANGE,rot=(180,0,0),note='14×51mm按鍵板；四顆M3×8沉頭由內側鎖上罩，PCF板焊線低矮裝配。')

# Three identical slip-ring clips. Nuts are captive in the clips; M3x8 screws
# enter recessed wells from the UNDERSIDE after lowering the whole upper unit.
# The 2.2mm peg merely locates in the reference flange's original 2.4mm hole;
# no M2 screw or enlargement of the purchased flange is required.
clip36=rr(12,8,1,4.2,26.5,0,9.8)+box(5,4,.8,20.5,0,9.8)+cyl(2.2,2.3,19,0,7.6)
clip36=clip36-hole(26.5,0,9,6)-nut(26.5,0,10.7,2.7)-box(9,5.8,2.7,31,0,10.7)
add('P36','滑環法蘭壓片',clip36,qty=3,color=ORANGE,rot=(180,0,0),note='M3×8由底座底部凹孔往上鎖入壓片M3螺母。三片相同轉120°。定位小柱適用參考孔圓Ø38；法蘭不同可移位或剪除小柱後暫時定位。')

def flat_screw(length):
    assert length in (8,25), 'V1.0.0 permits exactly two screw lengths'
    s=cyl(6,1.5,d2=3)+cyl(3,length-1.4,z0=1.4)
    return s-cyl(2.31,1.25,z0=-.05,n=6)

fastener_registry=[]
def shw(name,length,shape):
    fastener_registry.append({'name':name,'sku':f'DIN7991 M3x{length}','kind':'screw','diameter_mm':3,'length_mm':length,'head':'socket countersunk','hex_key_mm':2})
    hw(name,shape,METAL)
def hex_nut3(x,y,z):return cyl(6.3,2.4,x,y,z,n=6)-hole(x,y,z-.1,2.6,3.2)
def nhw(name,shape):
    fastener_registry.append({'name':name,'sku':'M3 nut 5.5AF x 2.4','kind':'nut'})
    hw(name,shape,METAL)
for x,z in [(-32,46.5),(72,46.5),(-32,120),(72,120)]:
    shw('hatchM3x8',8,flat_screw(8).rot(x=-90).move(x,-98.2,z))
for y in [-44,44]:shw('frontM3x8',8,flat_screw(8).rot(y=-90).move(103.2,y,51.2))
for x,y in HOUSING_MOUNTS:
    shw('hoodM3x8',8,flat_screw(8).move(x,y,42))
    nhw('hoodM3nut',hex_nut3(x,y,47.3))
for x,y in OLED_MOUNTS:shw('oledM3x8',8,flat_screw(8).move(x,y,119.5))
for x,y in KEY_MOUNTS:shw('keysM3x8',8,flat_screw(8).move(x,y,113.4))
for x,y in HOOD_JOIN_MOUNTS:
    shw('hoodJoinM3x8',8,flat_screw(8).move(x,y,HOOD_JOIN_HEAD_Z))
    nhw('hoodJoinM3nut',hex_nut3(x,y,HOOD_JOIN_NUT_Z))
for a in [0,120,240]:
    shw('slipM3x8',8,flat_screw(8).move(26.5,0,5.5).rot(z=a))
    nhw('slipM3nut',hex_nut3(26.5,0,10.8).rot(z=a))
shw('rotorM3x8',8,flat_screw(8).rot(y=90).move(-19,0,15.5))
nhw('rotorM3nut',hex_nut3(0,0,0).rot(z=30).rot(y=90).move(-16.35,0,15.5))
for x,y in P04_MOUNTS:
    shw('deckM3x8',8,flat_screw(8).rot(x=180).move(x,y,45.4))
    nhw('deckM3nut',hex_nut3(x,y,38.2))
shw('pinionM3x8',8,flat_screw(8).rot(y=-90).move(P05_HEAD_X,P05_CLAMP_Y,P05_CLAMP_Z))
nhw('pinionM3nut',hex_nut3(0,0,0).rot(z=30).rot(y=90).move(P05_NUT_X,P05_CLAMP_Y,P05_CLAMP_Z))
for x,y in P05_JOIN_MOUNTS:
    shw('pinionJoinM3x8',8,flat_screw(8).rot(x=180).move(x,y,40))
    nhw('pinionJoinM3nut',hex_nut3(x,y,34.1))
for yy in [-17.5,17.5]:
    shw('stepperM3x8',8,flat_screw(8).rot(x=180).move(47,yy,32.7))
    nhw('stepperM3nut',hex_nut3(47,yy,24.9))
for x in [-68,68]:
    for y in [-58,58]:
        shw('baseM3x25',25,flat_screw(25).rot(x=180).move(x,y,33))
        nhw('baseM3nut',hex_nut3(x,y,8.2))
for a in [30,150,270]:
    x,y=28.5*math.cos(math.radians(a)),28.5*math.sin(math.radians(a))
    shw('retainerM3x8',8,flat_screw(8).rot(x=180).move(x,y,35))
    nhw('retainerM3nut',hex_nut3(x,y,28.1))
for x in [-45,31]:
    for y in [-26,26]:
        shw('hopperM3x25',25,incline(flat_screw(25).rot(x=180).move(x,y,64)))
        nhw('hopperM3nut',incline(hex_nut3(x,y,42.8)))
    for y in [-44,44]:
        shw('adapterM3x8',8,flat_screw(8).rot(x=180).move(x,y,48.9))
        nhw('adapterM3nut',hex_nut3(x,y,41.3))
for y in [-35,35]:
    for x in [52.5,69.5]:
        shw('pillowM3x8',8,incline(flat_screw(8).rot(x=180).move(x,y,51.4)))
        nhw('pillowM3nut',incline(hex_nut3(x,y,43.4)))
    shw('adjustM3x8',8,incline(flat_screw(8).rot(x=180).move(61,y,88.75)))
    shw('guideM3x8',8,incline(flat_screw(8).rot(y=-90).move(76,y,60)))
for x,y in [(-33,-19),(-12,-19)]:
    shw('n20baseM3x8',8,incline(flat_screw(8).rot(x=180).move(x,y,48.4)))
    nhw('motorbaseM3nut',incline(hex_nut3(x,y,42.8)))
for x in [46.5,75.5]:
    shw('rfclampM3x25',25,incline(flat_screw(25).rot(x=180).move(x,-74.3,68.2)))
    nhw('motorbaseM3nut',incline(hex_nut3(x,-74.3,43.4)))
for x in [-30.4,-13.6]:shw('n20clampM3x8',8,incline(flat_screw(8).rot(x=180).move(x,-11,62.2)))
shw('photoM3x8',8,incline(flat_screw(8).rot(x=180).move(81,27,63.7)))
nhw('photoM3nut',incline(hex_nut3(81,27,55.9)))
shw('flagM3x8',8,flat_screw(8).move(-58,10,40.6))
nhw('flagM3nut',hex_nut3(-58,10,45.4))
shw('homeM3x8',8,flat_screw(8).move(-63.5,10,27))
for y in [-37.5,37.5]:
    shw('gateM3x8',8,incline(flat_screw(8).rot(y=90).move(39.5,y,72)))
    nhw('gateM3nut',incline(hex_nut3(0,0,0).rot(y=90).move(44.8,y,72)))
for z in [54.2,74.75]:
    shw('wheelM3x8',8,incline(flat_screw(8).rot(x=180).move(66,0,z+3.2)))
    nhw('wheelM3nut',incline(hex_nut3(66,0,z-4.5)))
shw('feedM3x8',8,incline(flat_screw(8).rot(x=180).move(-17,8,57.2)))
nhw('feedM3nut',incline(hex_nut3(-17,8,49.5)))
hw('separatorpad',incline(box(1,55,4,45,0,64.45)),RUBBER)
for y in [-55.3,-44.8]:
    shw('couplerM3x8',8,incline(flat_screw(8).rot(x=180).move(66,y,57.4)))
    nhw('couplerM3nut',incline(hex_nut3(66,y,49.7)))

# Keep the bearing, drive pinion and lower slip-ring/collar assembly fixed.
# Every other hardware item belongs to the lifted head; transform once, after
# its complete native or inclined construction and before consumer scripts.
UNRAISED_HARDWARE = {
    '6005ZZ','28BYJ-48','stepper_output','slipring_rotor','slipring_flange',
    'batteryholder','18650','ESP32C3','charger','TypeC','booster','protection1S',
    'ULN2003','powerrocker','home_opto','slipM3x8','slipM3nut','rotorM3x8','rotorM3nut',
    'pinionM3x8','pinionM3nut','pinionJoinM3x8','pinionJoinM3nut',
    'stepperM3x8','stepperM3nut','baseM3x25','baseM3nut','retainerM3x8','retainerM3nut','homeM3x8'}
RAISED_HARDWARE = {name for name,_,_ in hardware} - UNRAISED_HARDWARE
hardware=[(name,head_pose(shape) if name in RAISED_HARDWARE else shape,color)
          for name,shape,color in hardware]


# Closed, block-stroke lettering is generated as real CSG recesses. No font
# installation or text texture is required to preserve the marks in STL.
GLYPHS={
 'A':['010','101','111','101','101'], 'B':['110','101','110','101','110'],
 'P':['110','101','110','100','100'],
 '0':['111','101','101','101','111'], '1':['010','110','010','010','111'],
 '2':['111','001','111','100','111'], '3':['111','001','111','001','111'],
 '4':['101','101','111','001','001'], '5':['111','100','111','001','111'],
 '6':['111','100','111','101','111'], '7':['111','001','010','010','010'],
 '8':['111','101','111','101','111'], '9':['111','101','111','001','111'],
 'S':['111','100','111','001','111'],'E':['111','100','110','100','111'],
 'T':['111','010','010','010','010'],'R':['110','101','110','101','101'],
 'U':['101','101','101','101','111'],'N':['101','111','111','111','101'],
 '-':['000','000','111','000','000'],'+':['000','010','111','010','000'],
}
LABEL_BASE_SHAPES={}
def letter_pixels(text,height):
    cell=height/5; width=(len(text)*4-1)*cell
    for k,ch in enumerate(text):
        for row,values in enumerate(GLYPHS[ch]):
            for col,value in enumerate(values):
                if value=='1': yield ((k*4+col+.5)*cell-width/2,(2-row)*cell,cell)

def mark_part(part,text,cutter,height,depth,location,kind,details):
    before=part.shape
    LABEL_BASE_SHAPES[part.id]=before
    removed=float((before.m^cutter.m).volume())
    expected=float(cutter.m.volume())*depth/(depth+.12)
    ratio=removed/expected if expected>0 else 0
    if ratio<.88: raise RuntimeError(f"{part.id} label only {ratio:.3f} covered at {location}")
    part.shape=before-cutter
    part.engraving={'text':text,'type':kind,'location':location,'height_mm':height,'depth_mm':depth,'removed_mm3':round(removed,4),'coverage_ratio':round(ratio,4),**details}
    part.note+=f" 編號{text}：{location}，凹刻{depth}mm。"

def mark_flat(pid,origin,u,v,n,height=3,depth=.3,location="內側隱藏面",text=None):
    part=next(p for p in parts if p.id==pid);text=text or pid
    cutter=U(box(cell+.03,cell+.03,depth+.12,s,t,-depth) for s,t,cell in letter_pixels(text,height)).basis(u,v,n,origin)
    mark_part(part,text,cutter,height,depth,location,'planar',{'origin_mm':origin,'normal':n,'u':u,'v':v})

def mark_cylinder(pid,center,radius,height=2.5,depth=.3):
    part=next(p for p in parts if p.id==pid);cuts=[]
    for s,t,cell in letter_pixels(pid,height):
        a=s/radius;ca,sa=math.cos(a),math.sin(a)
        o=(center[0]+radius*ca,center[1]+radius*sa,center[2]+t)
        cuts.append(box(cell+.04,cell+.04,depth+.12,z0=-depth).basis((-sa,ca,0),(0,0,1),(ca,sa,0),o))
    mark_part(part,pid,U(cuts),height,depth,'支柱外側中央；避開端面與螺絲孔','cylindrical',{'center_mm':center,'radius_mm':radius})

TOP=((1,0,0),(0,1,0),(0,0,1));BOTTOM=((1,0,0),(0,-1,0),(0,0,-1))
BACK=((1,0,0),(0,0,1),(0,-1,0));LEFT=((0,-1,0),(0,0,1),(-1,0,0));RIGHT=((0,1,0),(0,0,1),(1,0,0))
SIDEWAYS_BOTTOM=((0,1,0),(1,0,0),(0,0,-1))
# These are operating legends, not part identifiers on the cosmetic face.
for yy,text in [(4,'SET'),(17,'-'),(30,'+'),(43,'RUN')]:
    label=U(box(cell+.03,cell+.03,.37,s,t,-.25) for s,t,cell in letter_pixels(text,2.5)).basis((0,1,0),(-1,0,0),(0,0,1),(88,yy,128.7))
    part=next(p for p in parts if p.id=='P32A');part.shape=part.shape-label
mark_flat('P01',(-30,14,2.2),*TOP,3.5,.35,'盒內底板空白區')
mark_flat('P02A',(-54,-26,30),*BOTTOM,3.5,.35,'上蓋內面；避開軸承座與定位孔')
mark_cylinder('P02B',(0,0,22),29,2.5,.3)
next(p for p in parts if p.id=='P02B').engraving['location']='軸承座外側空白弧面；避開軸承孔與螺母槽'
next(p for p in parts if p.id=='P02B').note=next(p for p in parts if p.id=='P02B').note.replace('支柱外側中央；避開端面與螺絲孔','軸承座外側空白弧面；避開軸承孔與螺母槽')
mark_flat('P03',(0,24,35),*TOP,3,.3,'壓環上方空白環帶；避開孔與軸承接觸面')
mark_flat('P04A',(-45,-36,42),*SIDEWAYS_BOTTOM,3,.3,'轉盤背面支臂；避開定位榫與固定孔')
mark_flat('P04B',(-14,0,36),*SIDEWAYS_BOTTOM,2.4,.25,'齒輪軸側內圈背面；避開齒面、軸承配合面與螺母槽')
mark_flat('P05A',(54,-10.5,40),*TOP,2.5,.3,'齒輪內部平坦腹板；避開齒面、異形孔與沉頭座')
mark_flat('P05B',(54,-10.5,35.5),*BACK,2.4,.25,'背側新增貼床平面；避開D軸孔、側載槽與承壓面')
mark_flat('P06',(17,0,15.5),*RIGHT,2.4,.25,'止退環隱藏小平臺；避開徑向固定孔及軸承接觸面')
mark_cylinder('P07',(0,0,53.5),4.5)
mark_flat('P08',(31,-8,61.6),*SIDEWAYS_BOTTOM,3,.3,'牌倉底面橫肋；避開牌路與支柱')
mark_flat('P09',(46.75,42.5,74.5),(-1,0,0),(0,0,1),(0,1,0),2.5,.3,'分牌閘固定耳外側；不接觸牌面')
mark_flat('P10',(-47.5,0,98.5),*LEFT,2,.25,'壓牌滑板後側薄邊；避開牌面與配重槽')
mark_flat('P11',(-22,0,98.6),*BOTTOM,3.5,.35,'配重塊底面中央隱藏區')
mark_flat('P12',(36,34.9,106.5),(-1,0,0),(0,0,1),(0,1,0),2,.25,'卡鉤外側；避開牌面與側柱卡合區')
for pid,y in [('P13',-35),('P14',35)]: mark_flat(pid,(51,y,64),*LEFT,2.5,.3,'滾輪座後側實心區；避開軸承孔和導槽')
mark_flat('P15',(61,-38.25,78.5),*BACK,2.5,.3,'滑塊背面；避開軸孔、軸承座和上方調整接觸點')
mark_flat('P16',(61,-27,59.7),*BACK,2.5,.3,'輪芯端面空白區；避開輪槽、軸孔及摩擦圓周')
mark_flat('P17',(-22,3,59.5),*BACK,2.5,.25,'取牌輪端面；避開O圈槽、軸孔與接觸圓周')
mark_flat('P18',(-22,-8,45.4),*BOTTOM,3,.3,'馬達座底面空白區')
mark_flat('P19',(-22,-11,61.2),*TOP,2.5,.25,'壓片上面中央；位於牌倉下方')
mark_flat('P20',(46.5,-68,45.4),*BOTTOM,2.5,.25,'底座下方側翼；避開馬達弧座及螺絲孔')
mark_flat('P21',(61,-74.3,68.2),*TOP,2.5,.25,'壓片上方中央；避開馬達弧面')
mark_flat('P22',(61,-59.3,57.8),*BACK,2,.25,'聯軸器端面環帶；避開軸孔及止付孔')
mark_flat('P23',(71.5,0,61.9),*SIDEWAYS_BOTTOM,2.5,.25,'出牌導槽下方前緣；不在牌路表面')
mark_flat('P24',(91,36,64.3),(-1,0,0),(0,0,1),(0,1,0),2.2,.25,'出口座背板外側；避開接腳與束帶孔')
mark_flat('P25',(-69.5,6.5,27),*BOTTOM,2,.25,'參考感測座底面；避開固定孔與接腳孔')
mark_flat('P26',(-66,10,40.6),*BOTTOM,2.5,.25,'遮光片支臂底面；避開光路薄片及螺絲孔')
# Tiny cap: two-digit 27 follows the hidden annular underside of its flange.
cap_part=next(p for p in parts if p.id=='P27');cap_cuts=[]
for s,t,cell in letter_pixels('27',1.4):
    a=s/3.65;ca,sa=math.cos(a),math.sin(a);r=3.65+t
    cap_cuts.append(box(cell+.03,cell+.03,.34,z0=-.22).basis((-ca,-sa,0),(-sa,ca,0),(0,0,-1),(75-r*sa,4+r*ca,129.3)))
mark_part(cap_part,'27',U(cap_cuts),1.4,.22,'頂按鍵帽凸緣背面環帶；按壓面無編號','annular',{'canonical_id':'P27','origin_mm':(75,7.65,129.3),'normal':(0,0,-1),'u':(-1,0,0),'v':(0,1,0)})
mark_flat('P28',(75,-10.1,121),*BOTTOM,2.5,.25,'頂部螢幕框底面前側橫條')
mark_flat('P29',(-23,41,20.2),(0,0,1),(0,1,0),(-1,0,0),2,.25,'束帶壓扣支腳外側；避開電芯避讓弧面')
mark_flat('P30',(8,-8,4),*TOP,2.5,.3,'試配片孔列旁的工具標示區')
mark_flat('P31',(-10,22,50.5),*BACK,3,.3,'轉接框內側直立肋面；避開安裝斜面')
mark_flat('P32A',(-30,96,55),*BACK,4,.35,'新正側內壁下方；避開裝牌口、固定孔與接合面')
mark_flat('P32B',(-50,-93.8,60),(-1,0,0),(0,0,1),(0,1,0),3,.35,'原背側內壁空白區；避開P33開口、柱位與接合面')
mark_flat('P33',(20,-96,80.5),(-1,0,0),(0,0,1),(0,1,0),4,.35,'側維修蓋內面；外觀面無字')
mark_flat('P34',(101,0,51),*LEFT,3.5,.35,'出牌口下飾蓋內面；外觀面無字')
mark_flat('P35',(84,10,103),(0,0,1),(0,1,0),(-1,0,0),2.5,.3,'按鍵支架後側直立框；避開電路板及束帶孔')
mark_flat('P36',(22,0,14),(0,1,0),(-1,0,0),(0,0,1),2,.25,'滑環壓片內端上面；避開螺母槽、定位柱與法蘭接觸面')

def tm(shape):
    mesh=shape.m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:,:3],faces=np.asarray(mesh.tri_verts),process=False)

def export_models():
    stldir=OUT/"STL"; srcdir=OUT/"OpenSCAD"; stldir.mkdir(exist_ok=True);srcdir.mkdir(exist_ok=True)
    manifest=[]; scad=[f"// Card dealer {P['revision']}. Units: mm. Generated from design_params.json and build_cad.py.\n$fn=64;\npart=\"assembly\";\n"]
    totalvol=0
    for p in parts:
        t=tm(p.shape)
        if not t.is_watertight or t.volume<=0:
            raise RuntimeError(f"{p.id} not a watertight positive solid")
        decomposed=p.shape.m.decompose()
        if len(decomposed)!=1:
            raise RuntimeError(f"{p.id} has {len(decomposed)} disconnected bodies")
        printed=p.shape.rot(*p.print_rot)
        pt=tm(printed); shift=-pt.bounds[0]; printed=printed.move(*shift); pt=tm(printed)
        dims=pt.extents
        if np.any(dims>np.array([175,175,180])): raise RuntimeError(f"{p.id} exceeds A1 mini safe build area: {dims}")
        fn=f"{p.id}.stl"; pt.export(stldir/fn)
        reloaded=trimesh.load_mesh(stldir/fn)
        if not reloaded.is_watertight or reloaded.volume<=0:
            raise RuntimeError(f"{p.id} STL roundtrip is not watertight")
        (srcdir/f"{p.id}.scad").write_text("// "+p.name+"\n$fn=64;\n"+printed.code,encoding="utf-8")
        volume=float(t.volume)/1000
        if p.id!="P30": totalvol+=volume*p.qty
        manifest.append({"id":p.id,"name":p.name,"qty":p.qty,"file":f"STL/{fn}","dimensions_mm":[round(float(v),2) for v in dims],"volume_cm3":round(volume,3),"watertight":bool(pt.is_watertight),"connected_components":len(decomposed),"print_rotation":p.print_rot,"supports":p.support,"material":p.material,"note":p.note,"engraving":p.engraving})
        scad.append(f"module {p.id}(){{{p.shape.code}}}\n")
        scad.append(f"if(part==\"{p.id}\"){{{printed.code}}}\n")
    scad.append('if(part=="assembly"){\n')
    for pid,name,shape,color in assembly_printables():
        scad.append(f"color({fmt([x/255 for x in color])}){{{shape.code}}}\n")
    scad.append("}\n")
    (OUT/"card_dealer.scad").write_text("".join(scad),encoding="utf-8")
    optional_ids={"P10","P11","P12"}
    optional_g=sum(x["volume_cm3"]*x["qty"] for x in manifest if x["id"] in optional_ids)*P["pla_density_g_cm3"]
    manifest_doc={"revision":P["revision"],"units":"mm","parts":manifest,"solid_volume_total_cm3":round(totalvol,2),"solid_PLA_mass_g":round(totalvol*P["pla_density_g_cm3"],1),"optional_solid_mass_g":round(optional_g,1),"status":"幾何原型，未經實物試裝","parameters":P}
    (OUT/"parts_manifest.json").write_text(json.dumps(manifest_doc,ensure_ascii=False,indent=2),encoding="utf-8")
    labels=[f"{P['revision']}：{len(manifest)}種列印件凹刻編號，P27刻27；尺寸單位mm。",""]
    for item in manifest:
        e=item['engraving']
        labels.extend([f"{item['id']} {item['name']} ×{item['qty']}",
                       f"字高{e['height_mm']:g}、深{e['depth_mm']:g}，{e['location']}",""])
    (OUT/'零件編號位置表.txt').write_text('\n'.join(labels),encoding='utf8')
    screws=[f for f in fastener_registry if f['kind']=='screw']
    assert {f['sku'] for f in screws}=={'DIN7991 M3x8','DIN7991 M3x25'}
    catalog={'revision':P['revision'],'screw_sku_count':2,'screw_skus':[{**next(f for f in screws if f['length_mm']==l),'qty':sum(f['length_mm']==l for f in screws)} for l in [8,25]],'nut_qty':sum(f['kind']=='nut' for f in fastener_registry),'instances':fastener_registry}
    (OUT/'fastener_catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({"parts":len(manifest),"assembled_print_count":sum(x["qty"] for x in manifest if x["id"] not in {"P10","P11","P12","P30"}),"solid_mass_g":manifest_doc["solid_PLA_mass_g"]},ensure_ascii=False),flush=True)
    return manifest_doc

def render(filename,cutaway=False,camvec=(1.2,-1.55,1.6),items=None,
           origin_mm=None,scale_px_mm=5.0,headline=None,subline=None,notes=None,annotations=()):
    W,H=1800,1500
    image=Image.new("RGB",(W,H),(243,242,237))
    cam=np.array(camvec);cam=cam/np.linalg.norm(cam)
    right=np.cross(np.array([0,0,1.]),cam);right/=np.linalg.norm(right)
    up=np.cross(cam,right)
    origin=np.array([0,0,62.] if origin_mm is None else origin_mm)
    scale=scale_px_mm
    entries=[]
    for pid,name,shape,color in assembly_printables():
        if cutaway and pid in {"P02A","P02B","P08","P09","P10","P11","P12","P27","P28","P32A","P32B","P33","P34","P35"}: continue
        if cutaway and pid=='P01': shape=shape-box(40,240,40,90,0,2.2)-box(200,40,40,0,-85,2.2)
        entries.append((shape,color))
    for name,shape,color in hardware:
        if cutaway and name in {"cards","cardedge","spring","M3guide","OLEDglass","screenpcb","screenheader","PCF8574","keypcb","keybody","keyplunger","oledM3x8","keysM3x8","hatchM3x8","frontM3x8","hoodM3x8","hoodM3nut","hoodJoinM3x8","hoodJoinM3nut"}: continue
        entries.append((shape,color))
    if items is not None:entries=items
    triangles=[]
    light=np.array([-.6,-.7,1.5]);light/=np.linalg.norm(light)
    for shape,color in entries:
        mesh=tm(shape); v=np.asarray(mesh.vertices); f=np.asarray(mesh.faces)
        tri=v[f]; normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-10)
        for t,n in zip(tri,normals):
            if np.dot(n,cam)<-.001: continue
            p=t-origin
            xy=np.column_stack([W/2+(p@right)*scale,H*.49-(p@up)*scale])
            depth=p@cam
            intensity=.58+.42*max(0,float(np.dot(n,light)))
            c=tuple(int(max(0,min(255,ch*intensity))) for ch in color)
            triangles.append((depth,xy,c))
    shadow=Image.new("RGBA",(W,H));sd=ImageDraw.Draw(shadow)
    sd.ellipse((270,970,1540,1265),fill=(50,65,70,35));shadow=shadow.filter(ImageFilter.GaussianBlur(40))
    image=Image.alpha_composite(image.convert("RGBA"),shadow).convert("RGB")
    pixels=np.array(image)
    zbuf=np.full((H,W),-np.inf,dtype=np.float32)
    for depth,xy,color in triangles:
        xmin=max(0,int(math.floor(xy[:,0].min()))); xmax=min(W-1,int(math.ceil(xy[:,0].max())))
        ymin=max(0,int(math.floor(xy[:,1].min()))); ymax=min(H-1,int(math.ceil(xy[:,1].max())))
        if xmax<xmin or ymax<ymin: continue
        x0,y0=xy[0];x1,y1=xy[1];x2,y2=xy[2]
        den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(den)<1e-8: continue
        yy,xx=np.mgrid[ymin:ymax+1,xmin:xmax+1]
        aa=((y1-y2)*(xx+.5-x2)+(x2-x1)*(yy+.5-y2))/den
        bb=((y2-y0)*(xx+.5-x2)+(x0-x2)*(yy+.5-y2))/den
        cc=1-aa-bb
        zz=aa*depth[0]+bb*depth[1]+cc*depth[2]
        window=zbuf[ymin:ymax+1,xmin:xmax+1]
        mask=(aa>=-1e-5)&(bb>=-1e-5)&(cc>=-1e-5)&(zz>window)
        window[mask]=zz[mask]
        pixels[ymin:ymax+1,xmin:xmax+1][mask]=color
    image=Image.fromarray(pixels)
    draw=ImageDraw.Draw(image)
    fontpath="C:/Windows/Fonts/msjh.ttc"
    title=ImageFont.truetype(fontpath,48);body=ImageFont.truetype(fontpath,25);small=ImageFont.truetype(fontpath,22)
    if not cutaway and items is None:
        # Orthographic projection of a real 128x64 display layout onto its glass.
        texture=Image.new("RGBA",(256,128),(10,25,32,255)); td=ImageDraw.Draw(texture)
        tf=ImageFont.truetype(fontpath,27)
        for i,line in enumerate(["每人張數 17","玩家人數  3","餘牌張數  3"]): td.text((6,2+i*40),line,font=tf,fill=(141,230,226,255))
        world0=np.array([68.6,-36,128.02+UPPER_LIFT]); worldu=np.array([0,24/256,0]);worldv=np.array([12.8/128,0,0])
        def project(v):
            q=v-origin
            return np.array([W/2+q@right*scale,H*.49-q@up*scale])
        p0=project(world0);u=project(world0+worldu)-p0;v=project(world0+worldv)-p0
        matrix=np.column_stack([u,v]);inv=np.linalg.inv(matrix); off=-inv@p0
        transformed=texture.transform((W,H),Image.Transform.AFFINE,(inv[0,0],inv[0,1],off[0],inv[1,0],inv[1,1],off[1]),resample=Image.Resampling.BICUBIC)
        # The screen texture must respect the housing's true occlusion.
        yy,xx=np.mgrid[0:H,0:W]
        du=float(worldu@cam);dv=float(worldv@cam);d0=float((world0-origin)@cam)
        glass_depth=d0+du*(inv[0,0]*(xx+.5)+inv[0,1]*(yy+.5)+off[0])+dv*(inv[1,0]*(xx+.5)+inv[1,1]*(yy+.5)+off[1])
        rgba=np.array(transformed);rgba[:,:,3][glass_depth<zbuf-.06]=0
        transformed=Image.fromarray(rgba)
        image=Image.alpha_composite(image.convert("RGBA"),transformed).convert("RGB");draw=ImageDraw.Draw(image)
    draw.text((90,60),headline or "充電式撲克牌發牌機",font=title,fill=(29,47,54))
    draw.text((94,128),subline or f"{P['revision']}  頂部螢幕與按鍵 · 旋轉上罩 · 隱藏式零件編號"+("  /  剖示" if cutaway else ""),font=body,fill=(82,97,102))
    foot=notes or ["61 mm 內寬 · 前後開放牌倉 · 57×87 / 60×96 mm 參考牌型",
        "28BYJ-48 · 單顆 18650 · USB Type-C · 螢幕與四顆設定按鍵",
        "依模型生成；未經實物試裝，板件尺寸與送牌性能仍需驗證。"]
    for i,line in enumerate(foot):draw.text((90,H-144+i*48),line,font=body if i==0 else small,fill=(70,86,92))
    for label,world,xy in annotations:
        q=np.asarray(world)-origin
        target=(float(W/2+q@right*scale),float(H*.49-q@up*scale))
        label_box=draw.multiline_textbbox(xy,label,font=body,spacing=6)
        draw.rectangle((label_box[0]-10,label_box[1]-7,label_box[2]+10,label_box[3]+7),fill=(250,250,247))
        anchor=(label_box[2]+12 if xy[0]<W/2 else label_box[0]-12,(label_box[1]+label_box[3])/2)
        draw.line([anchor,target],fill=(64,94,110),width=3)
        draw.ellipse((target[0]-5,target[1]-5,target[0]+5,target[1]+5),fill=(223,105,62))
        draw.multiline_text(xy,label,font=body,fill=(29,55,67),spacing=6)
    image.save(OUT/filename)
    print(str(OUT/filename),flush=True)

if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else "all"
    if mode in {"all","export"}: export_models()
    if mode in {"all","render"}:
        render("assembly_preview.png")
        render("assembly_cutaway.png",True)
        render("top_controls_view.png",camvec=(1.5,-.25,3.5))
