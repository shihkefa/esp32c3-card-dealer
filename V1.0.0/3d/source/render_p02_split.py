"""Render the actual split parts and the accessible nut wells, with labels."""
import math
import numpy as np
import build_cad as c

parts={p.id:p for p in c.parts}
steel=(174,184,191)
items=[(parts['P02A'].shape,(96,119,133)),(parts['P02B'].shape.move(z=-45),(222,137,80)),
       (parts['P03'].shape.move(z=35),(66,92,105))]
bearing=next(shape for name,shape,_ in c.hardware if name=='6005ZZ')
items.append((bearing.move(z=15),steel))
for x,y in c.BEARING_MOUNTS:
    items.append((c.flat_screw(8).rot(x=180).move(x,y,95),steel))
    items.append((c.hex_nut3(x,y,28.1).move(z=-70),steel))
c.render('P02_分件組裝說明.png',items=items,origin_mm=(0,0,24),scale_px_mm=6.2,
    camvec=(1.1,-1.7,1.1),headline='P02 分件與捕捉式螺母',
    subline='V1.0.0  依實際模型展開；裝配方向不變，三顆 M3×8 共用鎖固',
    notes=['P02A 主板與 P02B 軸承座分開列印；P03 請使用本次配套檔。',
           '先裝螺母與軸承，再由上方穿過 P03 鎖緊；圖中間距僅為看清零件。',
           '已做名義幾何檢查，尚未實體列印；配合、橋接與鎖緊力仍需試裝。'],
    annotations=[('M3×8 沉頭螺絲 ×3',(24.68,14.25,94),(90,225)),
        ('P03 軸承壓環',(24,0,69),(1390,385)),
        ('6005ZZ 軸承',(20,0,40),(1390,540)),
        ('P02A 平底主板',(-45,-42,33),(90,660)),
        ('P02B 軸承座',(24,0,-23),(90,1050)),
        ('M3 螺母 ×3\n由底部開口放入',(24.68,14.25,-40.7),(1370,1120))])

# View the bearing seat upside down, matching the user's underside screenshot.
flipped=parts['P02B'].shape.rot(x=180).move(z=32.8)
detail=[(flipped,(222,137,80))]
for x,y in c.BEARING_MOUNTS:
    detail.append((c.hex_nut3(x,y,28.1).rot(x=180).move(z=56.8),steel))
c.render('P02B_螺母槽近照.png',items=detail,origin_mm=(0,0,8),scale_px_mm=15,
    camvec=(1.2,-1.7,2.2),headline='P02B 原小開口改為六角螺母槽',
    subline='倒置查看：三個開口放入標準 M3 螺母，六角槽防止螺母跟轉',
    notes=['六角槽對邊約 5.8 mm，適用對邊 5.5 mm、厚 2.4 mm 的標準 M3 螺母。',
           '螺母需推到深槽止擋；可暫用既有 M3×25 拉入，再換回 M3×8 鎖固。',
           '螺絲通孔改 Ø3.4 mm，不再依靠塑膠預孔攻牙；列印誤差需先試配。'],
    annotations=[('六角防轉槽',(24.68,-14.25,14.8),(90,440)),
                 ('M3 螺母',(24.68,-14.25,27.5),(1370,380)),
                 ('平面定位凸緣',(-24.68,-14.25,2.8),(90,1040))])
