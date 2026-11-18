"""Apply the completed V1.0.0 geometry in the ordinary formal part IDs.

The native stock in build_cad is retained for audit comparisons. This module
replaces fourteen completed shapes, adds P31, removes two retired print types, and constructs the
single authoritative assembly frame. No adaptation directory is required.
"""
from collections import Counter
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import formal_wx22
import formal_carrier
import formal_p06
import formal_p08_screws
import formal_p23
import formal_p22
import formal_p31
import formal_p16
import formal_home_radial
import formal_p10
import formal_p24
import formal_oled
import formal_p09

LOWER_STACK_LIFT_MM=20.1
HEAD_EXTRA_LIFT_MM=3.7
LEGACY_HEAD_LIFT_MM=1.5
HEAD_LIFT_MM=LEGACY_HEAD_LIFT_MM+HEAD_EXTRA_LIFT_MM
HEAD_TOTAL_LIFT_MM=LOWER_STACK_LIFT_MM+HEAD_LIFT_MM
RETIRED_PRINT_IDS={'P10','P11','P36'}
LEGACY_OMITTED_IDS={'P10','P11','P31','P36'}
CHANGED_PRINT_IDS={'P01','P02A','P06','P04A','P04B','P08','P09','P13','P14','P15','P16','P18','P21','P22','P23','P24','P26','P28','P32A','P31','P10A','P10B','P10C','P10D'}
P10_PRINT_IDS={'P10A','P10B','P10C','P10D'}
BOTTOM_PRINT_IDS={'P01','P29'}
BOTTOM_HARDWARE={'batteryholder','18650','ESP32C3','charger','TypeC','booster',
                 'protection1S','ULN2003','powerrocker'}

def apply(namespace):
    """Install formal parts/hardware/pose APIs on the build_cad namespace."""
    c=SimpleNamespace(**namespace)
    LOWER_STACK_LIFT_MM=float(c.P['lower_stack_assembly_lift_mm'])
    GEAR_RISE_MM=float(c.P.get('P04B_gear_rise_mm',0.0))
    HEAD_EXTRA_LIFT_MM=1.0+GEAR_RISE_MM
    HEAD_LIFT_MM=LEGACY_HEAD_LIFT_MM+HEAD_EXTRA_LIFT_MM
    HEAD_TOTAL_LIFT_MM=LOWER_STACK_LIFT_MM+HEAD_LIFT_MM
    # Bind the legacy pose helpers to this immutable construction facade.
    # Original Python functions otherwise resolve the later formal helpers
    # through build_cad globals and would apply the final translation twice.
    c.head_pose=lambda shape:shape.move(z=LEGACY_HEAD_LIFT_MM)
    c.inclined_head_pose=lambda shape:c.head_pose(c.incline(shape))
    def legacy_assembly_pose(pid,shape):
        if pid in {'P05A','P05B'}: shape=shape.move(x=c.P05_REFERENCE_SHIFT_X)
        if pid in c.TILTED: shape=c.incline(shape)
        return c.head_pose(shape) if pid in c.RAISED_PRINT_PARTS else shape
    c.assembly_pose=legacy_assembly_pose
    w=formal_wx22.build(c)
    carrier=formal_carrier.build(c,w)
    p08_screws=formal_p08_screws.build(c,{p.id:p for p in c.parts})
    p22=formal_p22.build(c,{p.id:p for p in c.parts})
    p31=formal_p31.build(c,{p.id:p for p in c.parts})
    p16=formal_p16.build(c,{p.id:p for p in c.parts})
    home=formal_home_radial.build(c,{p.id:p for p in c.parts})
    p10=formal_p10.build(c,{p.id:p for p in c.parts})
    p24=formal_p24.build(c,{p.id:p for p in c.parts})
    oled=formal_oled.build(c,{p.id:p for p in c.parts})
    p09=formal_p09.build(c,{p.id:p for p in c.parts})
    p09.metadata['reference_cards_assembly_shifted_native_X_mm']=-4.
    p09.metadata['reference_card_sizes_unchanged']=True
    natives={**w.PRINT_SHAPES,**carrier.SHAPES,'P08':p08_screws.SHAPE,
             'P22':p22.SHAPE,
             'P15':p31.P15_SHAPE,
             'P16':p16.SHAPE,
             'P02A':home.P02A_SHAPE,'P26':home.P26_SHAPE,
             'P23':formal_p23.build(c,next(p.shape for p in c.parts if p.id=='P23')),
             'P24':p24.SHAPE,'P09':p09.SHAPE,**oled.SHAPES}

    notes={
      'P09':('固定耳齊平與滿寬直貼膠分牌閘','中央迎牌面與兩固定耳的共平面朝下躺印，清除局部支撐後試裝',
        '中央大面補至固定耳前緣，並補實接耳窄帶。寬61mm的30°背襯沿面長6.425mm，中央直貼55×4×1mm橡膠，左右各露3mm塑膠。膠下緣比新迎牌面內退2mm，與底板間隙0.45mm起調。上端比P08外緣低3mm，距上蓋內面0.8mm。'),
      'P28':('90度固定式OLED邊緣彈性壓板','底部原生Z119.5完整平面貼床；PETG；四個45度壓舌及局部孔槽依切片檢查',
        '兩固定耳繞OLED中心轉90度至(75,-42)/(75,-6)，仍用兩支原M3×8由下方鎖入P32A。基座及螺絲頭Z119.5、耳頂Z123保持；四個PETG壓舌頂125.4，對PCB背面125.3名義預壓0.1mm，較舊接觸面提高2.4mm。只壓PCB兩端非玻璃邊緣，中央避讓背面元件，+X留低矮焊線出口；實購元件腳位、壓力、蠕變與固定效果待試裝，不可硬壓玻璃。'),
      'P32A':('OLED修正式台階包覆居中上殼主片','原屋頂Z128.7大平面貼床；OLED凹槽上方保留0.4mm外皮，局部支撐依切片檢查',
        '只修改OLED局部：原兩柱移除，兩新柱轉90度至(75,-42)/(75,-6)，沿用兩M3×8與Ø2.7預孔。依使用者尺寸圖及安裝照片，PCB27.8X×27.3Y×1.2、排針朝+X，中心(75,-24)不動；顯示區10.86X×21.74Y朝排針偏2.1mm，視窗14×24中心(77.1,-24)。玻璃凹槽19.86×27.3、頂Z128.3，+X另留低矮焊點空間。PCB正面邊緣貼屋頂內面126.5，玻璃不作壓合止擋；參考總厚上限2.9mm時玻璃頂128.2尚留0.1mm名義隙。原上殼外形、搭接、按鍵、其它孔位及隱藏P32A編號沿用，實印與點亮顯示待試裝。'),
      'P02A':('平底上蓋主板・徑向光電位置','原生Z30大平面貼床；新光電孔槽逐層檢查',
        '保留軸承、馬達及底盒安裝介面。舊光電孔槽填回，歸零光電中心改至R77.5/155°，光軸沿335°徑向指向P02A圓心；P25及原M3×8旋轉平移到新孔位，P25原STL沿用。光電外殼13×6×10mm，內部槽形與光束使用條件式ITR9608-F參考，實物歸零仍待驗證。'),
      'P01':('單件高底盒與WX22固定柱','原底面朝下；開關/Type-C局部橋接待切片',
        '164×148×50.1mm中空底盒，原2.2mm底板、三根23mm滑環柱、螺母止擋及R4下線路保持。開關孔9×14.8mm、中心Y−1/Z14.75；Type-C孔11×5mm底Z6.7。原孔實購小板僅露插口上半部，CAD模組/插頭高度未校準，新孔待實測。P02底面以柱頂Z50.1定位，上部組件整體降低2.1mm；本件STL與前版完全相同。'),
      'P06':('WX22轉子夾持與空心軸連接環','外環原生Z11貼床；內夾套與後橋高2.1mm，需檢查局部支撐',
        '外環原生11..19及外側pin15.5保持；內夾套、夾緊螺絲及後橋抬高2.1mm，保留固定滑環頸部位置。P04B負Y底槽對齊後橋、外pin先退2mm再由上套入。仍用兩組M3×8及M3螺母；內套/後橋底部懸空需局部支撐，夾持力待實測。'),
      'P04A':('平底一體式旋轉承載架','原生Z42大平底貼床；六個底入螺母井採局部支撐屏蔽，剩餘孔槽逐層檢查',
        'P31已併入；原底部方形定位榫刪除，連續斜面梁銜接原6°牌路，四組原M3接合軸保持。四顆牌倉及兩顆N20底座螺母從底部放入；N20底座孔Y−17.5，馬達/軸心不移動。'),
      'P04B':(f'{8.5+GEAR_RISE_MM:.1f}mm完整60齒齒輪與空心轉軸',f'上側Z{44.5+GEAR_RISE_MM:.1f}齒輪平面貼床；局部徑向孔待切片',
        f'齒厚由8.5增加{GEAR_RISE_MM:g}mm至{8.5+GEAR_RISE_MM:.1f}，只向上加厚；原生齒底Z36、接合面Z{44.5+GEAR_RISE_MM:.1f}。60齒、軸承肩臺Z31、−X徑向pin孔及管底負Y寬9mm/Z13..15.4後橋槽保持。四組M3×8接合螺母上止擋隨頂面上移{GEAR_RISE_MM:g}mm以保留完整咬合。前次徑向及圓弧P26改版已使用本件並將上部裝配抬高{GEAR_RISE_MM:g}mm；本次重力擺輪改版沿用本件及P02A/P25/P04A，歸零功能待實物驗證。'),
      'P08':('61mm封底高側板牌倉・恢復原螺絲孔','底板大平面貼床；原側耳螺絲頭孔、底部盲槽及滾輪孔逐層檢查',
        '只將兩處分牌閘孔恢復原螺絲頭圓孔及錐孔；軸Y±37.5/Z72、Ø3.4通孔、Ø6.4螺絲頭入口、原固定耳外形、61mm牌道、底板、側板、滾輪開口及支柱孔全部保持。螺絲由原−X方向放入，P09原螺母槽及所有組裝五金位置不動；先前P08六角螺母孔已撤回。'),
      'P13':('平背出牌軸承座A・反向螺絲','原生負Y外側大平背貼床（X轉+90°）；軸承口朝上，局部螺母槽/橫孔逐層檢查',
        '主體、導軌、頂梁及兩個腳座向外補平至Y−41；完整上滑塊窗口保持開放。列印底面25×41.6、高12mm；軸承孔、通軸孔、調整及導向位置不動。兩支M3×8由P04A下方向上鎖，M3螺母仍由X外側放入、承壓底層3.5mm。頂部調整孔新增實口Ø6.4、90°沉頭，接Ø2.7預孔；保留原調整螺絲姿態，螺絲頭高度仍取決於調整位置。'),
      'P14':('平背出牌軸承座B・反向螺絲','原生正Y外側大平背貼床（X轉−90°）；軸承口朝上，局部螺母槽/橫孔逐層檢查',
        '主體、導軌、頂梁及兩個腳座向外補平至Y+41；完整上滑塊窗口保持開放。列印底面25×41.6、高12mm；軸承孔、通軸孔、調整及導向位置不動。兩支M3×8由P04A下方向上鎖，M3螺母仍由X外側放入、承壓底層3.5mm。頂部調整孔新增實口Ø6.4、90°沉頭，接Ø2.7預孔；保留原調整螺絲姿態，螺絲頭高度仍取決於調整位置。'),
      'P15':('上滾輪調整滑塊','新背面貼床（原X轉90°）；Ø3.5軸孔朝上，局部字槽待切片',
        '僅背面向外補2.75mm至原生Y−41，Ø3.5通軸孔延長；原軸承座、正面、主軸與調整頂面不動。配P31 U罩限制向滾輪及外側滑出，保留原−0.3..+0.8mm上下調整。兩顆同件鏡像裝入；原隱藏編號移至新背面，舊內部字洞已填平。上鋼軸及軸承仍自由轉，不得點膠或鎖死內圈。'),
      'P16':('出牌滾輪輪芯','新端面貼床（原X轉90°）；O圈槽及夾縫逐層檢查',
        '沿鋼軸總長54→53mm，兩端各裁0.5mm至原生Y±26.5；中心、Ø3.15軸孔、中央輪轂夾縫及原M3×8螺絲螺母不動。兩槽及四個O圈由原Y±24各向中間移3mm至±21；槽寬2.3、根徑16.8、外端平料4.35mm。原±21環形減重腔保持，槽底外殼名義徑向壁1.9mm。原隱藏字移至新Y−26.5，舊字洞已填平。上下輪同STL各一件；所有緊固件與其它硬體不動，實印偏擺及摩擦待試。'),
      'P18':('N20底座・底入螺母配套','依既有平面貼床；兩個開放工具通道待切片',
        '安裝孔由Y−19移至Y−17.5以對齊P04A封閉承壓螺母井；孔周Ø6.8工具通道向內開放。N20本體、軸心及上夾座定位均不移動。'),
      'P21':('RF300上夾板・反向長螺絲','依既有平面貼床；頂入螺母槽待切片',
        '兩支M3×25由P04A下方向上鎖，上部兩個Ø9.5承壓耳座頂入M3螺母、底層1.2mm；原P20、馬達避讓及隱藏編號保持。'),
      'P22':('2mm至3mm軸聯軸器','原軸向端面貼床；夾縫、頭部孔及螺母槽局部檢查',
        '外徑19→18mm、軸向長18→17mm，兩端各縮0.5mm。主軸X61/Z54.2及Ø2.15/Ø3.15軸孔位置、深度保持。兩組夾孔X66→65.5，滾輪側Y−44.8→−45.3，馬達側Y−55.3保持；原兩組M3×8及螺母隨孔移，頭部及螺母座規格不變。隱藏編號移至新馬達端面Y−58.8。其它37印件及其它五金不移；夾持及實物間隙待試裝。'),
      'P23':('出牌導向槽','需要局部支撐',
        '原生X81/Y27垂直沉頭孔實際上口改為Ø7.0mm、90°，接Ø3.4mm通孔；頂面Z63.7、錐底Z61.9，原3mm固定耳底層仍1.2mm。原開邊缺口、兩側水平孔、牌路及隱藏編號保持。實購螺絲頭尺寸仍需試放確認。'),
      'P24':('出口光電感測器開放式可調座','原生底面貼床；主長孔懸空耳底需局部支撐，原四孔及束帶槽架接待切片',
        '配使用者確認本體13×6×10mm（寬13、厚6、高10，不含腳）。只刪除第二長孔側及前方突出bar；保留(81,27)主M3長孔、完整承壓邊、原M3×8及螺母介面。原背板、四個Ø1.2接腳孔及孔位、原束帶槽與隱藏P24編號全部保持原幾何。60mm牌整座與光電向外移Y+1.5mm，57mm牌回Y0；固定螺絲軸不移。U槽寬5、槽底高4.1及光軸高6.8mm仍為條件式ITR9608-F參考。實際腳位對孔、固定、實印、觸發與出牌待試裝。'),
      'P26':('同心圓弧歸零光電遮光片','原上方完整平面貼床；圓弧薄片、螺絲孔及字槽逐層檢查',
        f'本件為前次完成的圓弧P26；本次重力擺輪改版沿用。薄片以P02A圓心為中心：內R77、外R78、中線R77.5弧長7mm，中心155°、夾角約5.1751°。原斜臂、固定孔(-58,10)、下緣原生Z33.1及隱藏編號保持，世界下緣Z{33.1+HEAD_TOTAL_LIFT_MM:.1f}；所有裝配及五金位置不移動。55.0 mm 軸距的 P05A 最外徑向包絡 R75，名義間隙 2 mm；外側掃掠較直片減少約0.0785mm，並非大幅增加間隙。條件式ITR9608-F槽底57.5/光軸60.2、名義底隙0.9及上臂距2.5mm保持，實際槽形與歸零觸發待試。'),
    }
    parts=[]
    for p in c.parts:
        if p.id in LEGACY_OMITTED_IDS: continue
        if p.id not in natives:
            note=p.note
            if p.id=='P07':
                note=note.replace('使用M3沉頭長螺絲。','四支M3×25由牌倉上方往下鎖入P04A的底入螺母井；先放入四顆M3螺母。')
            elif p.id=='P25':
                note+=' 本件STL沿用；與原M3×8及光電一起移到R77.5/155°，光軸沿335°指向P02A圓心。'
            elif p.id=='P20':
                note=note.replace('兩顆M3×25同時固定壓片、馬達座及P31，取消另外兩顆底座螺絲。',
                    '兩支M3×25由P04A一體承載架下方向上穿過馬達座，鎖入P21頂入螺母；同時固定承載架、馬達座及上夾板。')
            elif p.id=='P22':
                note=note.replace('需用新版P31避讓','由P04A一體承載架保留對應避讓')
            elif p.id=='P08':
                note=note.replace('上蓋Z130.2齊平','上蓋組裝Z153.4齊平')
            parts.append(replace(p,note=note) if note!=p.note else p);continue
        name,support,note=notes[p.id]
        rot=(0,0,0) if p.id in {'P01','P06','P04A'} else p.print_rot
        if p.id in {'P13','P14'}:rot=(90 if p.id=='P13' else -90,0,0)
        if p.id=='P09':rot=p09.PRINT_ROT
        engraving=p.engraving
        if p.id in oled.ENGRAVINGS:engraving=oled.ENGRAVINGS[p.id]
        if p.id=='P24':engraving=p24.ENGRAVING
        if p.id=='P09':engraving=p09.ENGRAVING
        if p.id=='P06':
            unlabeled=formal_p06.build(c,engrave=False)
            removed=float((unlabeled-natives[p.id]).m.volume())
            expected=sum((cell+.03)**2*.25 for _,_,cell in c.letter_pixels('P06',2.4))
            engraving={'text':'P06','height_mm':2.4,'depth_mm':.25,
                       'location':'正X外側隱藏平台；避開軸承及軸配合面',
                       'type':'planar','origin_mm':[17,0,15.5],
                       'normal':[1,0,0],'u':[0,1,0],'v':[0,0,1],
                       'removed_mm3':round(removed,4),
                       'coverage_ratio':round(removed/expected,4)}
        elif p.id=='P04A':
            engraving={**p.engraving,'location':'旋轉承載架原底部支臂隱藏面；避開四組M3接合孔'}
        elif p.id=='P22':
            engraving={**p.engraving,'origin_mm':[61,-58.8,57.8],
                       'location':'縮短後馬達側端面環帶；避開軸孔及夾孔',
                       'removed_mm3':round(float(p22.GLYPH.m.volume()),4)}
        elif p.id=='P15':
            engraving={**p.engraving,'origin_mm':[61,-41,78.5],
                       'location':'加背後滑塊外背隱藏面；避開軸孔、軸承座及調整頂面',
                       'removed_mm3':round(float(p31.P15_GLYPH.m.volume()),4)}
        elif p.id=='P16':
            engraving={**p.engraving,'origin_mm':[61,-26.5,59.7],
                       'location':'縮短後輪芯負Y隱藏端面；避開O圈槽及軸孔',
                       'removed_mm3':round(float(p16.GLYPH.m.volume()),4)}
        elif p.id=='P26':
            engraving=home.P26_ENGRAVING
        parts.append(replace(p,shape=natives[p.id],name=name,print_rot=rot,material='PETG' if p.id=='P28' else p.material,
                             support=support,note=note,engraving=engraving))
    parts.append(c.Part('P31','上滾輪滑塊U型防脫罩',p31.SHAPE,qty=2,material='PETG',color=c.ORANGE,
        print_rot=(180,0,0),support='上方完整大平面貼床；平直背板及字槽逐層檢查',
        note='配加背P15，P13/P14及P15本體沿用。外背內外均為整片平直板（原生內Y−41.5、外Y−42.7、底Z72.45），兩端扣勾已取消。82mm上軸保持居中±41，閉面止擋±41.5，各端0.5mm、總1mm名義游隙。先鬆上輪夾螺絲居中鋼軸但保持輪芯位置，再鎖回。裝卸先卸原調整螺絲，罩子直接上下套入或取出，不需張腿；回裝原Ø3.4/Ø6.4沉頭調整螺絲作高度調整及頭部防脫，不得鎖到底夾罩。P15前後名義隙0.45/0.5mm，上下−0.3..+0.8mm調整保持；罩可在框頂與螺絲頭之間浮動。軸端平常不碰止擋，推到邊界才端面限位，不夾鋼軸或軸承內圈；實物配合、偏擺與端推摩擦待試，不新增五金。',engraving=p31.engraving))
    p10_notes={
      'P10A':'選配重力擺架，空倉Ø12輪直接貼底板，單張起便抬升。正X+5.6完整平面貼床，C鉤口在上層；活動耳2mm、純打印固定肩長2.4mm，每端0.2mm名義軸向隙。帶頭肩軸由local−X開口側滑入，不硬擠軸頭穿孔；正常重力使其坐向封閉弧，不是抗拉鎖扣。無下擺限位，不可拉擺架搬整機；舊P11配重不適用。',
      'P10B':'Ø12×16mm自由輪，Y0..16對準P17膠環區；Ø5.4孔套在Ø5隔套上。空倉後緣X−9.65，與P17橡膠前緣投影間隙2mm；最低點Z64接底板。端面凹字避開外圓及孔，摩擦/壓力與取牌效果待試。',
      'P10C':'隔套穿輪與M3×25螺絲；兩耳之間有效距16.6mm、輪寬16mm，每端0.3mm軸向隙。近端伸入鍵槽0.8mm，整個套身17.4mm；編號外延耳避開轉動圓周及承壓端面。螺絲鎖到底壓住隔套，不壓自由輪。',
      'P10D':'PETG純打印U夾與一體帶頭肩軸；兩側完全不用螺絲、螺母或墊圈。相同件×2，第二件Z轉180°/移X−96。6mm夾腳在名義樞軸X−48時，後緣對齊P08後緣X−51；可兩側等量向前移0..6mm並沿牆頂6°斜率定位，不得單邊歪斜。名義位置新輪對P17投影隙2mm，移動後不再固定2mm。U夾深4mm、槽淨寬2.6，局部接觸肋鬆態2.2mm夾2.4mm牆，每側名義彈開0.1mm；實際夾力、蠕變與公差未驗。先預裝兩肩軸到C鉤，再從上方夾牆；下擺無限位，輪靠底板停止。X背面側躺印，夾臂彎曲盡量在層內。'}
    for pid,d in p10.PARTS.items():
        parts.append(c.Part(pid,d['name'],d['shape'],qty=d['qty'],material='PETG',
            color=c.ORANGE if pid=='P10A' else c.DARK if pid=='P10B' else (93,140,158),
            print_rot=d['print_rot'],support=d['support'],note=p10_notes[pid],engraving=d['engraving']))

    # Original hardware already contains the legacy 1.5mm head placement.
    # Shift each retained actor exactly once, then add replacement declarations
    # directly in the completed global frame.
    omitted={'slipring_rotor','slipring_flange','slipM3x8','slipM3nut',
      'rotorM3x8','rotorM3nut','stepperM3x8','stepperM3nut','baseM3nut','powerrocker',
      'adapterM3x8','adapterM3nut','hopperM3nut','motorbaseM3nut','pillowM3nut',
      'pillowM3x8','rfclampM3x25','hopperM3x25','n20baseM3x8','deckM3x8','deckM3nut'}
    hardware=[];p22_counts=Counter();oled_screw_index=0
    for name,shape,color in c.hardware:
        if name in omitted: continue
        if name in oled.HARDWARE_NATIVE:
            shape=oled.HARDWARE_NATIVE[name].move(z=LEGACY_HEAD_LIFT_MM)
        elif name=='oledM3x8':
            shape=oled.SCREWS[oled_screw_index].move(z=LEGACY_HEAD_LIFT_MM)
            oled_screw_index+=1
        if name=='separatorpad':
            shape=c.inclined_head_pose(p09.PAD_NATIVE)
        if name in {'cards','cardedge'}:
            angle=np.radians(c.P['hopper_tilt_deg'])
            shape=shape.move(x=-4.*np.cos(angle),z=4.*np.sin(angle))
        if name in {'couplerM3x8','couplerM3nut'}:
            index=p22_counts[name];p22_counts[name]+=1
            local=(p22.SCREWS if name=='couplerM3x8' else p22.NUTS)[index]
            hardware.append((name,c.incline(local).move(z=HEAD_TOTAL_LIFT_MM),color))
            continue
        if name=='silicone':
            bounds=shape.m.bounding_box()
            center_y=(bounds[1]+bounds[4])/2
            shape=shape.move(y=3 if center_y<0 else -3)
        if name=='upper3mmshaft':
            shape=shape.move(y=-1)
        if name=='home_opto':
            shape=home.SENSOR_NATIVE
        if name=='exit_opto':
            shape=c.inclined_head_pose(p24.SENSOR_NATIVE)
        if name=='homeM3x8':
            shape=home.repose(shape)
        shift=(0. if name in BOTTOM_HARDWARE else LOWER_STACK_LIFT_MM)
        if name in c.RAISED_HARDWARE: shift+=HEAD_EXTRA_LIFT_MM
        hardware.append((name,shape.move(z=shift),color))
    def add(name,shapes,color):
        hardware.extend((name,s,color) for s in shapes)
    add('WX22_stator',[w.STATOR],c.DARK)
    add('WX22_rotor',[w.ROTOR],c.METAL)
    add('WX22_upper_bundle',[carrier.UPPER_BUNDLE],c.ORANGE)
    add('WX22_lower_bundle',w.LOWER_BUNDLES,c.ORANGE)
    add('WX22_slip_screw',w.SLIP_SCREWS,c.METAL)
    add('WX22_slip_washer',w.SLIP_WASHERS,c.METAL)
    add('WX22_slip_nut',w.SLIP_NUTS,c.METAL)
    add('WX22_P06_screw',w.P06_SCREWS,c.METAL)
    add('WX22_P06_nut',w.P06_NUTS,c.METAL)
    add('baseM3nut',w.COVER_NUTS,c.METAL)
    add('deckM3x8',carrier.DECK_SCREWS,c.METAL)
    add('deckM3nut',carrier.DECK_NUTS,c.METAL)
    for rec,screw,nut in zip(carrier.FASTENERS,carrier.LOCAL_SCREWS,carrier.LOCAL_NUTS):
        add(rec['screw_kind'],[carrier.pose_local(screw)],c.METAL)
        add(rec['nut_kind'],[carrier.pose_local(nut)],c.METAL)

    byname={r['name']:r for r in c.fastener_registry}
    byname['WX22_slip_screw']={**byname['rotorM3x8'],'name':'WX22_slip_screw'}
    byname['WX22_P06_screw']={**byname['rotorM3x8'],'name':'WX22_P06_screw'}
    for name in ('WX22_slip_nut','WX22_P06_nut'):
        byname[name]={'name':name,'sku':'M3 nut 5.5AF x 2.4','kind':'nut'}
    byname['WX22_slip_washer']={'name':'WX22_slip_washer','sku':'M3 washer OD7 x ID3.2 x 0.5',
                               'kind':'washer','OD_mm':7,'ID_mm':3.2,'thickness_mm':.5}
    registry=[];poses=[];counts=Counter()
    for name,s,color in hardware:
        if name not in byname: continue
        record=dict(byname[name]);counts[name]+=1
        if record['kind']=='screw':
            assert s.screw_pose is not None,name
            head,tip=np.asarray(s.screw_pose,dtype=float)
            axis=(tip-head)/float(record['length_mm'])
            pose={'name':name,'key':f'{name}.{counts[name]}',
                  'length_mm':record['length_mm'],'head_mm':head.tolist(),
                  'tip_mm':tip.tolist(),'axis':axis.tolist()}
            record.update({k:v for k,v in pose.items() if k not in {'name','length_mm'}})
            poses.append(pose)
        registry.append(record)
    totals=Counter((r['kind'],r.get('length_mm')) for r in registry)
    assert totals==Counter({('screw',8):56,('screw',25):10,('nut',None):47,('washer',None):3}),totals
    assert len(parts)==41
    tilted=set(c.TILTED)|{'P31'}|P10_PRINT_IDS
    raised=set(c.RAISED_PRINT_PARTS)-RETIRED_PRINT_IDS|{'P31'}|P10_PRINT_IDS

    def head_pose(shape):
        return shape.move(z=HEAD_TOTAL_LIFT_MM)
    def inclined_head_pose(shape):
        return head_pose(c.incline(shape))
    def assembly_pose(pid,shape):
        if pid in {'P10A','P10B','P10C'}:shape=p10.shape_pose(shape,p10.theta_empty)
        if pid=='P25':shape=home.repose(shape)
        if pid in {'P05A','P05B'}: shape=shape.move(x=c.P05_REFERENCE_SHIFT_X)
        if pid in tilted: shape=c.incline(shape)
        dz=0 if pid in BOTTOM_PRINT_IDS else LOWER_STACK_LIFT_MM
        if pid in raised: dz+=HEAD_LIFT_MM
        return shape.move(z=dz)
    placements={**c.placements,'P24':[(0,p24.STANDARD_Y_SHIFT_MM,0)],'P31':[(0,0,0),(0,0,0)],'P10D':[(0,0,0),(0,0,0)]}
    def assembly_printables():
        for p in parts:
            if p.id in {'P10','P11','P12','P30'}|P10_PRINT_IDS:continue
            for index,pose in enumerate(placements.get(p.id,[(0,0,0)])):
                shape=p.shape
                if p.id=='P12' and index==1:shape=shape.rot(z=180).move(x=-8)
                if p.id in {'P15','P31'} and index==1:shape=shape.rot(z=180).move(x=122)
                yield p.id,p.name,assembly_pose(p.id,shape.move(*pose)),p.color

    def optional_assembly_printables(theta=None,slide_mm=0):
        if theta is None:theta=np.arccos((120+slide_mm*np.tan(np.radians(6))-70)/p10.arm_length)
        for p in parts:
            if p.id not in P10_PRINT_IDS:continue
            native=p10.shape_pose(p.shape,theta,slide_mm) if p.id!='P10D' else p.shape.move(slide_mm,0,slide_mm*np.tan(np.radians(6)))
            yield p.id,p.name,inclined_head_pose(native),p.color
            if p.id=='P10D':yield p.id,p.name,inclined_head_pose(p10.MIRROR(p.shape).move(slide_mm,0,slide_mm*np.tan(np.radians(6)))),p.color
    def optional_hardware(theta=None,slide_mm=0):
        if theta is None:theta=np.arccos((120+slide_mm*np.tan(np.radians(6))-70)/p10.arm_length)
        names={'pivot_screw':'P10pivotM3x8','pivot_nut':'P10pivotM3nut','pivot_washer':'P10pivotM3washer',
               'clamp_screw':'P10clampM3x8','clamp_nut':'P10clampM3nut',
               'wheel_screw':'P10wheelM3x25','wheel_nut':'P10wheelM3nut'}
        for key,s in p10.FIXED_HARDWARE:
            yield names[key.split('.')[0]],inclined_head_pose(s),c.METAL
        for key,s in p10.MOVING_HARDWARE:
            yield names[key],inclined_head_pose(p10.shape_pose(s,theta,slide_mm)),c.METAL
    p10.optional_assembly_printables=optional_assembly_printables
    p10.optional_hardware=optional_hardware
    p10.OPTIONAL_HARDWARE=list(optional_hardware())

    namespace.update(parts=parts,hardware=hardware,fastener_registry=registry,P24_EXIT=p24,OLED_FIX=oled,P09_GATE=p09,
        final_fastener_poses=poses,head_pose=head_pose,assembly_printables=assembly_printables,placements=placements,TILTED=tilted,
        inclined_head_pose=inclined_head_pose,assembly_pose=assembly_pose,
        LOWER_STACK_LIFT_MM=LOWER_STACK_LIFT_MM,HEAD_EXTRA_LIFT_MM=HEAD_EXTRA_LIFT_MM,
        HEAD_LIFT_MM=HEAD_LIFT_MM,HEAD_TOTAL_LIFT_MM=HEAD_TOTAL_LIFT_MM,
        FORMAL_BASE_LIFT=LOWER_STACK_LIFT_MM,FORMAL_HEAD_LIFT=HEAD_TOTAL_LIFT_MM,
        P04_MATE_Z=44.5+GEAR_RISE_MM,P04_GEAR_HEIGHT=8.5+GEAR_RISE_MM,P04B_GEAR_RISE_MM=GEAR_RISE_MM,
        RETIRED_PRINT_IDS=RETIRED_PRINT_IDS,LEGACY_OMITTED_IDS=LEGACY_OMITTED_IDS,CHANGED_PRINT_IDS=CHANGED_PRINT_IDS,
        WX22=w,INTEGRATED_CARRIER=carrier,P08_GATE_SCREW_HOLES=p08_screws,P22_SIZE=p22,P31_RETAINER=p31,P16_WIDTH=p16,HOME_RADIAL=home,P10_GRAVITY=p10,
        optional_assembly_printables=optional_assembly_printables,
        RAISED_PRINT_PARTS=raised)
