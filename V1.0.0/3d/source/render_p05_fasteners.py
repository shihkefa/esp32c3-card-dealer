"""Render actual separate P05 gear/hub, closed bearing seat and installation."""
import build_cad as c
import math
import numpy as np

parts = {p.id: p for p in c.parts}
gear, hub = parts['P05A'].shape, parts['P05B'].shape
gear_top = float(gear.m.bounding_box()[5])
hub_top = float(hub.m.bounding_box()[5])
hw = {}
for name, shape, _ in c.hardware:
    hw.setdefault(name, []).append(shape)
orange, blue, steel, gold = (222, 137, 80), (96, 119, 133), (174, 184, 191), (190, 156, 75)
screw, nut = hw['pinionM3x8'][0], hw['pinionM3nut'][0]
y, z = c.P05_CLAMP_Y, c.P05_CLAMP_Z


def placed_pose(shape, rotation, cx, cy, bed_z):
    rotated = shape.rot(*rotation)
    bounds = np.asarray(rotated.m.bounding_box())
    shift = np.array([cx - (bounds[0] + bounds[3]) / 2,
                       cy - (bounds[1] + bounds[4]) / 2, bed_z - bounds[2]])
    ax, ay, az = np.radians(rotation)
    rx = np.array([[1, 0, 0], [0, np.cos(ax), -np.sin(ax)], [0, np.sin(ax), np.cos(ax)]])
    ry = np.array([[np.cos(ay), 0, np.sin(ay)], [0, 1, 0], [-np.sin(ay), 0, np.cos(ay)]])
    rz = np.array([[np.cos(az), -np.sin(az), 0], [np.sin(az), np.cos(az), 0], [0, 0, 1]])
    matrix = rz @ ry @ rx
    def point(world):
        return tuple(matrix @ np.asarray(world) + shift)
    return rotated.move(*shift), point

items = [(hub, blue), (gear.move(z=30), orange),
         (screw.move(x=17), steel), (nut.move(y=18), steel)]
items += [(shape.move(z=50), steel) for shape in hw['pinionJoinM3x8']]
for (x, _), shape in zip(c.P05_JOIN_MOUNTS, hw['pinionJoinM3nut']):
    items.append((shape.move(x=-15 if x < 54 else 15), steel))
c.render('P05_分件組裝與閉合夾座.png', items=items, origin_mm=(54, 0, 51), scale_px_mm=13,
         camvec=(1.25, 1.7, 1.5), headline='P05 分件：先鎖夾座，再裝齒輪',
         subline='實際 CAD 爆炸圖；三組 M3×8 ＋標準 M3 螺母，維持30T與2:1傳動',
         notes=['先裝P02A與馬達；P05B側放橫向螺母、裝螺絲並套D軸，用匹配的2mm L扳手鎖緊。',
                '放入兩顆垂直固定螺母，再套 P05A；兩顆M3×8由上方固定齒輪與夾座。',
                '齒輪裙邊封住側入口；要重新調整夾座，請先拆下齒輪。尚待實物試配。'],
         annotations=[('垂直 M3×8 ×2', (c.P05_JOIN_MOUNTS[1][0], -1, gear_top + 50), (90, 220)),
                      ('P05A 完整30齒輪\n下伸止退裙邊', (65, -3, 65), (1310, 340)),
                      ('P05B 閉合D軸夾座', (54, -5, 35), (90, 850)),
                      ('垂直固定螺母 ×2', (c.P05_JOIN_MOUNTS[1][0] + 15, -1, 35.3), (90, 670)),
                      ('橫向M3螺母\n由正Y側放入', (51, 25.5, 35.4), (1320, 1060)),
                      ('橫向M3×8\n2mm L扳手鎖付', (74.6, 7.5, 35.4), (90, 1100))])

# Cut only the near half of the actual solids to expose their genuine inner
# surfaces. This section is a visualization, not a new printable part.
front_cut = c.box(70, 35, 50, 54, 25, 20)
section_hub = hub - front_cut
section_gear = gear - front_cut
items = [(section_hub, blue), (section_gear, orange), (screw, steel), (nut, steel)]
items += [(shape, steel) for shape in hw['pinionJoinM3nut']]
c.render('P05_完整承壓與防脫剖示.png', items=items, origin_mm=(54, 0, 36), scale_px_mm=24,
         camvec=(1.2, 1.8, 1.5), headline='完整沉頭承壓座與側入口防脫',
         subline='實際組裝模型局部剖示；圖中切面僅用於看清內部，不是列印開口',
         notes=['P05B保留完整周向錐面與閉合導向孔，頂部有連續屋頂，不再使用上開U槽。',
                'P05A的裙邊及上腹板封住側載出口；三顆螺母都須維持螺紋咬合。',
                '幾何接觸、擋位與退出路徑已檢查；夾緊力、磨損與實印公差仍需測試。'],
         annotations=[('P05A 下伸裙邊', (69.6, 2, 35.5), (90, 270)),
                      ('完整360°沉頭座\n剖示僅展示一半', (56.9, 7.5, 33.1), (1310, 340)),
                      ('閉合螺桿導向', (55, 7.5, 35.4), (90, 1050)),
                      ('橫螺母側載槽\n裝齒輪後封住出口', (51, 9, 35.4), (1310, 1060))])

printed_gear, gear_point = placed_pose(gear, parts['P05A'].print_rot, 88, 0, 30.5)
printed_hub, hub_point = placed_pose(hub, parts['P05B'].print_rot, 20, 0, 30.5)
items = [(printed_gear, orange), (printed_hub, blue),
         (c.box(44, 44, .7, 88, 0, 29.75), (185, 203, 208)),
         (c.box(38, 38, .7, 20, 0, 29.75), (185, 203, 208))]
c.render('P05_列印方向.png', items=items, origin_mm=(54, 0, 38), scale_px_mm=13,
         camvec=(.5, 1.8, 1.9), headline='P05A／P05B 建議列印方向',
         subline='兩件實際大平面貼床；淺藍板代表熱床，並非額外列印零件',
         notes=['左：P05A齒輪上方大平面貼床，裙邊朝上；30T齒形與軸心不變。',
                '右：P05B新增側平面貼床；兩端45°削角減少懸伸，建議3～5mm brim。',
                '局部D孔與圓孔頂仍須切片確認橋接；不宣稱完全免支撐，配合面請先試印。'],
         annotations=[('P05A 齒輪平面貼床', gear_point((61, 10, 40)), (90, 250)),
                      ('下伸裙邊朝上', gear_point((69, -2, 33.3)), (90, 1060)),
                      ('P05B 新增削角\n減少軸座懸伸', hub_point((54, -4.5, 31.7)), (1310, 250)),
                      ('新增平面貼床\n建議3～5mm brim', hub_point((54, -10.5, 35.5)), (1310, 1060))])

flat_print, flat_point = placed_pose(hub, parts['P05B'].print_rot, 27, 0, 0)
flat_view, view_point = placed_pose(hub, (0, 0, 180), -27, 0, 0)
items = [(flat_print, blue), (flat_view, blue),
         (c.box(42, 20, .6, 27, 0, -.65), (185, 203, 208))]
c.render('P05B_平面貼床與削角.png', items=items, origin_mm=(0, 0, 9), scale_px_mm=18,
         camvec=(1.1, 1.6, 1.7), headline='P05B 平面貼床與兩端45°削角',
         subline='左：建議列印姿態　右：同一零件的平面與削角近照，並非要印兩份',
         notes=['新增平面約22×4.6mm；建議3～5mm brim，法蘭可沿側面逐層長高。',
                'D孔頂約4.0mm橋接，其他水平孔也要切片確認；不要直接承諾免支撐。',
                '削角保留D孔支承與完整螺絲座；局部端壁數值不代表整件最小壁厚，仍須試配。'],
         annotations=[('下端45°外形削角', flat_point((54, -4.5, 31.7)), (90, 250)),
                      ('D孔局部橋接\n先切片確認', flat_point((54, 1.65, 30.5)), (90, 1050)),
                      ('上端45°外形削角', view_point((54, -4.8, 39)), (1300, 250)),
                      ('新增平面與零件編號', view_point((54, -10.5, 35.5)), (1300, 1050))])

# Show the real underside cavity and the mating flat without cutting any teeth.
flat_gear, cavity_point = placed_pose(gear,(180,0,0),-25,0,0)
flat_hub, mating_point = placed_pose(hub,(0,0,0),25,0,0)
backing = c.LABEL_BASE_SHAPES['P05A']-c.P05A_ROUND_CAVITY_BASE
# Apply precisely the gear's placement to the highlighted crescent, not the
# crescent's own bounding-box centering.
gear_rotated=gear.rot(180,0,0)
gear_bounds=np.asarray(gear_rotated.m.bounding_box())
gear_shift=(-25-(gear_bounds[0]+gear_bounds[3])/2,
            -(gear_bounds[1]+gear_bounds[4])/2,-gear_bounds[2])
flat_backing=backing.rot(180,0,0).move(*gear_shift)
flat_gear_base=(gear-backing).rot(180,0,0).move(*gear_shift)
c.render('P05A_P05B_平口配合.png',
         items=[(flat_gear_base,orange),(flat_backing,(230,177,61)),(flat_hub,blue)],
         origin_mm=(0,0,4),scale_px_mm=17,camvec=(-.2,-1.3,2.2),
         headline='P05A 內腔平口，配合新版 P05B',
         subline='左：P05A翻面看內腔　右：沿用現有平面版P05B；黃色為A內側新增材料',
         notes=['A內側平口Y=-10.7，對B外側平口Y=-10.5；名義留0.2mm側隙，不能硬鎖成緊配。',
                '只補回內腔負Y側的新月形區域；外圈30齒、6mm齒寬、固定孔及螺母擋邊保留。',
                '本次僅需重印P05A；P05B可沿用。A仍以齒輪頂部大平面貼床，實印公差待試配。'],
         annotations=[('P05A 新增內側平口',cavity_point((54,-10.7,35.5)),(90,240)),
                      ('完整30齒圈',cavity_point((38,0,37)),(90,1050)),
                      ('P05B 原有切齊平面',mating_point((54,-10.5,35.5)),(1300,1040)),
                      ('兩件平口名義間隙\n0.2mm',mating_point((54,-10.5,36.8)),(1300,240))])

pivot, bend_radius = 72.6, 2.
pieces = [c.cylx(2.30, 2.1, 56.6, y, z, n=6),
          c.cylx(3, pivot - 2 - 57.8, 57.8, y, z),
          c.cyl(3, 68, pivot, y, z + 2)]
points = [np.array([pivot - 2 + 2 * math.cos(theta), y, z + 2 + 2 * math.sin(theta)])
          for theta in np.linspace(-np.pi / 2, 0, 7)]
sphere = c.S(c.mf.Manifold.sphere(1.5, 16), '')
pieces += [sphere.move(*point) for point in points]
for first, second in zip(points, points[1:]):
    delta = second - first
    pieces.append(c.cyl(3, float(np.linalg.norm(delta)), n=16)
                  .rot(y=math.degrees(math.atan2(float(delta[0]), float(delta[2])))).move(*first))
l_key = c.U(pieces)
cover_context = parts['P02A'].shape & c.box(70, 60, 30, 54, 5, 20)
items = [(cover_context, (183, 192, 197)), (hub, blue), (screw, steel), (nut, steel), (l_key, gold),
         (hw['28BYJ-48'][0], steel), (hw['stepper_output'][0], steel)]
items += [(n, steel) for n in hw['pinionJoinM3nut']]
c.render('P05_L工具鎖付順序.png', items=items, origin_mm=(54, 2, 48), scale_px_mm=10,
         camvec=(1, 1.8, 1.8), headline='裝上蓋與馬達後，用2mm L扳手鎖付',
         subline='示範短臂尖端至長臂中心16mm；商品標示外長不可直接等同',
         notes=['① 先裝P02A與馬達，再將P05B套D軸；齒輪P05A與P04此時尚未裝上。',
                '② 扳手先退3.2mm從上方放入，再沿軸咬合；轉60°後退1.1mm、換位重入。',
                '③ 鎖好後裝固定螺母、P05A與兩螺絲，最後裝P04；工具須匹配14／16mm中心距參考。'],
         annotations=[('2mm L扳手參考\n中心距16mm／外桿Ø3', (pivot, y, 83), (90, 250)),
                      ('P02A外圈高邊\n直螺絲起子會被擋住', (80.5, 7.5, 39), (1310, 300)),
                      ('閉合夾座內的鎖付位置', (57.6, y, z), (90, 1060)),
                      ('上蓋與馬達已裝好\n圖中上蓋僅局部展示', (47, -14, 31), (1310, 1060))])
