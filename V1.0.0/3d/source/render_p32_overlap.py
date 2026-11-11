"""Actual shell exterior and magnified A-over-B lap, not a new print model."""
import numpy as np
import build_cad as c

parts={p.id:p for p in c.parts}
cam=np.array([1.3,-1.6,1.25]);cam/=np.linalg.norm(cam)
right=np.cross([0,0,1.],cam);right/=np.linalg.norm(right)
blue=(96,119,133);orange=(222,137,80);gray=(179,188,186);steel=(156,172,179)

def pose(shape,origin,offset,magnification=1):
    q=shape.move(*(-np.asarray(origin)))
    if magnification!=1:q=c.S(q.m.scale((magnification,)*3),f'scale({magnification}){{{q.code}}}')
    return q.move(*(right*offset))

def point(world,origin,offset,magnification=1):
    return tuple((np.asarray(world)-np.asarray(origin))*magnification+right*offset)

origin=(14,1.1,86)
items=[]
for pid,col in [('P32A',blue),('P32B',orange),('P33',gray),('P34',gray)]:
    items.append((pose(parts[pid].shape,origin,-137),col))
for pid,_,s,col in c.assembly_printables():
    if pid=='P27':items.append((pose(s.move(z=-c.UPPER_LIFT),origin,-137),orange))
for name,s,col in c.hardware:
    if name in {'OLEDglass','screenpcb'}:items.append((pose(s.move(z=-c.UPPER_LIFT),origin,-137),col))

zoom_origin=(94,-59,120)
crop=c.box(23,31,28,94.5,-59,104)
for pid,col in [('P32A',blue),('P32B',orange)]:
    items.append((pose(parts[pid].shape&crop,zoom_origin,145,4),col))

c.render('P32_台階包覆與接縫.png',items=items,origin_mm=(0,0,0),scale_px_mm=3.0,
         camvec=tuple(cam),headline='P32A 包住 P32B，接縫改成刻意的台階',
         subline='左：上殼組合外觀　右：同一接縫局部放大4倍；顏色用於區分A與B，不是額外零件',
         notes=['A外側包覆邊約6.1mm、厚1.2mm；B屋頂與兩側退1.5mm，配合面名義留0.3mm間隙。',
                'A外屋頂維持原高度，B屋頂維持2.2mm厚；兩件仍有大平面可貼床，原四組內側螺絲不變。',
                'B從負Y方向滑入A包邊再鎖緊；此圖只說明外觀與名義配合，實印公差及局部支撐仍需試配。'],
         annotations=[('A 主片與包覆邊',point((100,-60,120),origin,-137),(90,270)),
                      ('B 接合片\n形成1.5mm階差',point((99.5,-68,115),origin,-137),(90,1010)),
                      ('A向外跨過接縫\n遮住內部對接邊',point((101,-59,121),zoom_origin,145,4),(1250,270)),
                      ('B退台\n名義間隙0.3mm',point((99.5,-63,121),zoom_origin,145,4),(1250,1030))])
