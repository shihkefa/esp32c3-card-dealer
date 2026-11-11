"""Annotated split-P04/P06 views rendered directly from delivered CAD solids."""
import numpy as np
import build_cad as c

parts = {p.id: p for p in c.parts}
steel = (174, 184, 191)
blue = (96, 119, 133)
orange = (222, 137, 80)
dark = (66, 92, 105)
hardware = {}
for name, shape, _ in c.hardware:
    hardware.setdefault(name, []).append(shape)

items = [(c.head_pose(parts['P04A'].shape).move(z=36), blue), (parts['P04B'].shape, orange)]
for shape in hardware['deckM3x8']:
    items.append((shape.move(z=66), steel))
for shape in hardware['deckM3nut']:
    items.append((shape.move(z=-43), steel))
c.render('P04_分件組裝說明.png', items=items, origin_mm=(5, 0, 48), scale_px_mm=6.3,
         camvec=(1.1, -1.7, 1.2), headline='P04 拆分：承載盤與齒輪軸',
         subline='V1.0.0  加厚P04B將上部抬高1.5mm；P04A沿用，原四組M3五金不變',
         notes=['先從 P04B 齒輪軸側裝入四顆螺母，再將 P04A 定位榫對準凹槽。',
                '四顆螺絲由上方分次鎖緊；組好轉盤後，再裝 P31 轉接框及牌倉。',
                '展開距離僅供辨識；幾何原型尚待實體列印、試配與鎖緊測試。'],
         annotations=[('M3×8 沉頭螺絲 ×4', (-15, -26, 111.4+c.UPPER_LIFT), (90, 225)),
                      ('P04A 旋轉承載盤', (-45, -26, 79.4+c.UPPER_LIFT), (90, 505)),
                      ('偏心矩形定位榫', (31, 0, 77.4+c.UPPER_LIFT), (1370, 510)),
                      ('P04B 60齒齒輪＋空心軸', (24, 7, 37), (1330, 850)),
                      ('M3 捕捉螺母 ×4\n由齒輪軸側向上放入', (-15, -26, -3.6+c.UPPER_LIFT), (90, 1100))])

printed = []
for pid, dx, color, lift in [('P04A', -66, blue, 45.4), ('P04B', 87, orange, c.P04_MATE_Z)]:
    shape = parts[pid].shape.rot(*parts[pid].print_rot).move(x=dx, z=lift)
    printed.append((shape, color))
    bounds = np.asarray(shape.m.bounding_box())
    printed.append((c.box(float(bounds[3] - bounds[0] + 14),
                          float(bounds[4] - bounds[1] + 14), .7,
                          float((bounds[0] + bounds[3]) / 2),
                          float((bounds[1] + bounds[4]) / 2), -.75), (185, 203, 208)))
c.render('P04_列印方向.png', items=printed, origin_mm=(0, 0, 4), scale_px_mm=4.8,
         camvec=(.6, -1.8, 1.8), headline='P04A／P04B 建議列印方向',
         subline='兩件均有實際大平面貼床；圖中淺藍板代表熱床',
         notes=['P04A：原上方平面貼床，定位榫朝上；不要將定位榫壓在熱床上。',
                f'P04B：Z{c.P04_MATE_Z:g}上平面貼床、空心軸朝上；齒厚{c.P04_GEAR_HEIGHT:g}mm，承載盤對底座環間隙2mm。',
                '螺母槽及定位槽有局部橋接；請先切片確認，不宣稱完全免支撐。'],
         annotations=[('P04A 大平面向下', (-90, 25, 1), (90, 300)),
                      ('定位榫朝上', (-35, 0, 4.6), (90, 1070)),
                      ('P04B 空心軸朝上', (87, 0, 29), (1320, 360)),
                      ('齒輪平面貼床', (110, -14, 0), (1310, 1050))])

flipped = parts['P04B'].shape.rot(x=180).move(z=c.P04_MATE_Z)
detail = [(flipped, orange)]
for shape in hardware['deckM3nut']:
    detail.append((shape.rot(x=180).move(z=62), steel))
c.render('P04B_螺母槽近照.png', items=detail, origin_mm=(0, 0, 12), scale_px_mm=15,
         camvec=(1.1, -1.7, 2.3), headline='P04B 四處捕捉式螺母槽',
         subline='由齒輪軸側查看；六角槽阻止螺母跟著螺絲旋轉',
         notes=['四顆標準 M3 螺母從圖示方向裝入，推到槽內止擋。',
                '再合上 P04A；M3×8 從承載盤上方鎖入，不需要在塑膠孔攻牙。',
                '螺母對邊 5.5mm、厚 2.4mm；實際列印公差仍需試配。'],
         annotations=[('M3 螺母 ×4', (-15, 26, 22.6-c.UPPER_LIFT), (90, 260)),
                      ('六角深槽入口', (-15, -26, 6), (1320, 460)),
                      ('齒形保留，齒厚7.5mm', (35, -8, 3), (90, 1090)),
                      ('空心轉軸', (0, 0, 28), (1320, 1060))])

detail = [(parts['P06'].shape, orange),
          (hardware['rotorM3nut'][0].move(z=17), steel),
          (hardware['rotorM3x8'][0].move(x=-14), steel)]
c.render('P06_捕捉螺母與調整螺絲.png', items=detail, origin_mm=(-4, 0, 19), scale_px_mm=22,
         camvec=(-1.6, -1.4, 1.6), headline='P06 改為金屬螺母鎖付',
         subline='實際 CAD 展開圖；先放螺母，再將止退環套入 P04B 軸底端',
         notes=['M3 螺母由上方裝入六角槽；M3×8 經 Ø3.4 通孔穿過 P04B 定位孔。',
                '圓柱沉孔保留調整行程；接觸滑環後只輕鎖，不要求螺絲頭到底。',
                '滑環外殼容許壓力與固定扭矩尚待實物確認，圖示未施加壓入量。'],
         annotations=[('標準 M3 螺母\n由上方放入', (-15.15, 0, 32.5), (90, 240)),
                      ('上方開口螺母槽', (-15.15, 0, 18.9), (1310, 390)),
                      ('M3×8 調整螺絲', (-31, 0, 15.5), (90, 1060)),
                      ('圓柱沉孔\n螺絲頭可微調', (-18.5, 0, 15.5), (1320, 1050))])

# Show the actual rim crossing on the long roller-side arm, not the central
# circular carrier (which lies radially inside the stationary rim).
camera=np.asarray((1.2,-1.6,1.15));camera/=np.linalg.norm(camera)
right=np.cross([0,0,1.],camera);right/=np.linalg.norm(right)
def panel(s,origin,offset,factor=1):
    q=s.move(*(-np.asarray(origin)))
    if factor!=1:q=c.S(q.m.scale((factor,)*3),f'scale({factor}){{{q.code}}}')
    return q.move(*(right*offset))
def location(point,origin,offset,factor=1):
    return tuple((np.asarray(point)-np.asarray(origin))*factor+right*offset)
origin=(4,0,30);items=[]
for pid in ('P02A','P02B','P03','P04A','P04B'):
    shape=c.assembly_pose(pid,parts[pid].shape)
    items.append((panel(shape,origin,-126),blue if pid=='P04A' else orange if pid=='P04B' else (169,183,185)))
section_origin=(59,-60,41)
crop=c.box(40,10,22,59,-60,28)
for pid,col in [('P02A',(169,183,185)),('P04A',blue)]:
    shape=c.assembly_pose(pid,parts[pid].shape)&crop
    items.append((panel(shape,section_origin,142,3),col))
c.render('P04B_抬高與2mm間隙.png',items=items,origin_mm=(0,0,0),scale_px_mm=3.8,
         camvec=tuple(camera),headline='P04B 上側加厚1.5mm，承載盤對底座環間隙改為2mm',
         subline='左：實際轉盤與軸承座子組　右：長支臂跨越P02A圓環處，實體局部放大3倍',
         notes=['P04B齒輪厚度6→7.5mm；齒輪底面、軸承肩臺及P06位置保留，P04A原列印件沿用。',
                '承載盤下平面Z43.5，固定圓環頂面Z41.5，名義高度差2.0mm；原間隙0.5mm。',
                '同時更換向下延長1.5mm的P26，保留原光電遮擋區；承重後的撓曲仍需實物試裝確認。'],
         annotations=[('P04A 原件沿用',location((62,-14,46.9),origin,-126),(90,270)),
                      ('P04B 上側加厚\n原四組M3×8沿用',location((25,-15,42.7),origin,-126),(90,1030)),
                      ('P04A 下平面 Z43.5',location((60,-60,43.5),section_origin,142,3),(1200,270)),
                      ('P02A 圓環頂 Z41.5\n兩面名義間隙2mm',location((54,-60,41.5),section_origin,142,3),(1200,1030))])
