"""Render the closed hopper, level roof interface and blind underside reliefs."""
import numpy as np
import build_cad as c

parts={p.id:p for p in c.parts}
BLUE=(91,143,162)
ORANGE=(226,143,76)
GRAY=(191,198,195)
hopper=c.assembly_pose('P08',parts['P08'].shape)
roof=[(c.assembly_pose(pid,parts[pid].shape)
       &c.box(240,240,3,z0=c.UPPER_ROOF_TOP_Z+c.UPPER_LIFT-2.2),GRAY)
      for pid in ('P32A','P32B')]

def wp(x,y,z):
    shape=c.assembly_pose('P08',c.box(.01,.01,.01,x,y,z-.005))
    b=shape.m.bounding_box()
    return tuple((b[i]+b[i+3])/2 for i in range(3))

c.render('P08_封底高側板與上蓋齊平.png',
         items=[(hopper,BLUE)]+roof,camvec=(1.25,-1.7,2.35),
         origin_mm=(8,0,106),scale_px_mm=5.5,
         headline='P08 封底高側板牌倉',
         subline='藍色：實際P08　灰色：上蓋屋頂參考；其餘外殼隱藏以顯示配合',
         notes=['內寬61mm · 前後開放不限長 · 底板厚2.4mm · 取牌輪開口23×12mm',
                '側板頂緣按6°傾角補償，組裝後與上蓋頂面Z130.2mm齊平；前上角削邊避讓。',
                '圖依目前CAD生成；裝配間隙、平整度與送牌仍需實印試配。'],
         annotations=[('側板頂緣與上蓋齊平',wp(-30,-31.7,c.hopper_roof_local_z(-30)),(90,260)),
                      ('連續底板，保留滾輪開口',wp(-22,7,64),(1060,1110)),
                      ('前後不設長度擋板',wp(-54,0,64),(90,1120))])

c.render('P08_底面盲槽與滾輪開口.png',
         items=[(parts['P08'].shape,BLUE)],camvec=(1.2,-1.65,-2.5),
         origin_mm=(-2,0,87),scale_px_mm=7,
         headline='P08 底面：牌路封實，螺絲由背面避讓',
         subline='背面視角；兩個盲槽不穿透牌面，四個沉頭固定孔與原位置相同',
         notes=['兩個Ø9.2mm盲槽只避讓P19凸臺與螺絲頭；上方保留1.4mm實心層。',
                '先安裝並調整P19，再放上P08；底板平面貼床，盲槽頂部需核對橋接設定。',
                '只有取牌滾輪開口與四個固定孔貫穿牌倉底板；底面凹刻P08編號。'],
         annotations=[('原23×12mm取牌輪開口',(-22,7,61.6),(90,300)),
                      ('P19盲避讓槽 ×2',(-30.4,-11,62.1),(1100,350)),
                      ('四個原位沉頭固定孔',(31,26,61.6),(1050,1120))])

first=parts['P12'].shape
second=first.rot(z=180).move(x=-8)
c.render('P08_P12中央掛架配合.png',
         items=[(hopper,BLUE),(c.assembly_pose('P12',first),ORANGE),
                (c.assembly_pose('P12',second),ORANGE)],
         camvec=(1.2,-1.7,2.2),origin_mm=(1,0,105),scale_px_mm=7,
         headline='P12 中央掛架配合高側板P08',
         subline='兩片使用同一STL；另一片繞Z軸轉180°並移至相對側',
         notes=['57mm牌：左右各一片，淨寬約58mm；60mm牌取下，回復61mm淨寬。',
                '44.1mm導牌本體落底，中央15mm對稱掛架跨住高側板；掛架約高出上蓋3mm。',
                '掛架位於裝牌開口內；此版P08若使用57mm牌，須配新版P12。'])
