"""Render the actual shell centering change and hidden split-shell fasteners."""
from pathlib import Path
import base64,json,zipfile
import numpy as np
import build_cad as c

parts={p.id:p for p in c.parts}
hw={}
for name,s,_ in c.hardware:
    native=s.move(z=-c.UPPER_LIFT) if name in c.RAISED_HARDWARE else s
    hw.setdefault(name,[]).append(native)
blue=(96,119,133); orange=(222,137,80); gray=(177,187,187); steel=(159,174,183)
archive=c.ROOT.parent/'發牌機_完整專案_V1.0.0.zip'
with zipfile.ZipFile(archive) as z:
    old=json.loads(z.read('V1.0.0/manual/assets/assembly_3d.json'))
has_old_shell=any(m['partId']=='P32' for m in old['scenes']['overview']['meshes'])

def old_shape(pid):
    desc=next(m for m in old['scenes']['overview']['meshes'] if m['partId']==pid)
    g=old['geometries'][desc['geometryKey']]
    vs=np.frombuffer(base64.b64decode(g['positionsB64']),dtype='<f4').reshape(-1,3)
    fs=np.frombuffer(base64.b64decode(g['indicesB64']),dtype='<u4').reshape(-1,3)
    m=c.mf.Manifold(c.mf.Mesh(vs.copy(),fs.copy()))
    return c.S(m,'').move(*desc['position'])

def body(pid):return parts[pid].shape
def shifted(shape,y):return shape.move(y=y)

left,right=-123,123
common=['P01','P02A','P04A','P33','P34']
items=[(shifted(body(pid),dy),gray if pid in {'P01','P02A','P04A'} else blue)
       for dy in [left,right] for pid in common]
items += [(shifted(old_shape('P32') if has_old_shell else body('P32A')+body('P32B'),left),gray),
          (shifted(body('P32A'),right),orange),(shifted(body('P32B'),right),orange)]
for dy in [left,right]:
    items += [(s.move(y=dy),steel) for s in hw.get('powerrocker',[])]
if not has_old_shell:
    assert (c.OUT/'P32_居中與分件組裝.png').exists(), 'Historical comparison needs the retained comparison image or the previous archive.'
if has_old_shell:
 c.render('P32_居中與分件組裝.png',items=items,origin_mm=(0,0,70),
         scale_px_mm=3.3,camvec=(1,0,.015),
         headline='只改上殼，讓正面左右中心對齊',
         subline='左：原版　右：P32A＋P32B；底盒、轉盤、馬達、螢幕、按鍵及原孔位保留',
         notes=['含原P33側蓋，左右外緣為Y=-98.2與+98.2mm，總寬196.4mm；相對底盒每側伸出24.2mm。',
                '這是正面左右居中；前後出牌配置維持原位，外殼並非與底盒同寬。',
                '上殼拆成兩件以符合A1 mini；內側新增四組M3×8與標準M3螺母，其餘38種列印件沿用。'],
         annotations=[('原上殼偏向一側',(101,left+65,95),(90,270)),
                      ('新版兩側伸出量一致',(101,right+98.2,95),(1250,270)),
                      ('原底盒沿用',(82,right+74,16),(1260,1060))])

# Exact local crop through the joint, exploded only for clarity.
crop=c.box(170,26,20,14,-53,112)
a=body('P32A')&crop;b=body('P32B')&crop
items=[(a.move(y=15),blue),(b.move(y=-15),orange)]
items += [(s.move(y=-15,z=-14),steel) for s in hw['hoodJoinM3x8']]
items += [(s.move(y=15,z=9),steel) for s in hw['hoodJoinM3nut']]
first=c.HOOD_JOIN_MOUNTS[0];last=c.HOOD_JOIN_MOUNTS[-1]
c.render('P32_內側接合與列印方向.png',items=items,origin_mm=(6,-50,121),
         scale_px_mm=7.2,camvec=(.8,-1.6,-1.5),
         headline='上殼內側四組接合，外觀面不開螺絲孔',
         subline='實際屋頂內側局部爆炸圖；只為看清五金，分解間距不是組裝間隙',
         notes=['P32A主片先從側槽預放四顆M3螺母，再與P32B搭接、對準四個孔。',
                '四支M3×8由內側向上鎖，先全部咬合再交替輕鎖；兩件預組完成後再裝OLED與按鍵。',
                'P32A與P32B都以屋頂大平面貼床，依各自STL姿態列印；螺母槽局部橋接仍需切片確認。'],
         annotations=[('P32A 主片\n四個捕捉螺母座',(last[0],last[1]+15,125),(1240,260)),
                      ('P32B 側片\n下方搭接片',(first[0],first[1]-15,120),(90,270)),
                      ('M3×8 ×4\n由內側向上鎖',(last[0],last[1]-15,c.HOOD_JOIN_HEAD_Z-14),(1250,1050))])
