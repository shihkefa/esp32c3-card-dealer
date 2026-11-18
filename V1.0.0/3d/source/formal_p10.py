"""Optional gravity-only P10 free-wheel assembly.

Coordinates are the native card plane.  The paired wall clamps are the same
print rotated180deg aboutZ; their flat wall-slot roof accommodates both signs
of the6deg hopper-rim slope. The side clips and headed pivot pins are wholly
printed. There is no lower stop. Only the central free-wheel axle uses metal.
"""
from types import SimpleNamespace
import math


def build(c,parts):
    H=(-48.,120.); R=6.; E=(-3.65,70.)
    L=math.hypot(E[0]-H[0],E[1]-H[1])
    theta0=math.atan2(E[0]-H[0],H[1]-E[1])
    def pose(s,t,slide=0):
        return s.rot(y=-math.degrees(t)).move(H[0]+slide,0,H[1]+slide*math.tan(math.radians(6)))
    def mirror(s):return s.rot(z=180).move(x=-96)
    def pixels(text,height):
        alphabet=dict(c.GLYPHS,C=['111','100','100','100','111'],D=['110','101','101','101','110'])
        cell=height/5;width=(len(text)*4-1)*cell
        for k,ch in enumerate(text):
            for row,values in enumerate(alphabet[ch]):
                for col,value in enumerate(values):
                    if value=='1':yield ((k*4+col+.5)*cell-width/2,(2-row)*cell,cell)
    def glyph(text,height,origin,u,v,n,depth=.2):
        return c.U(c.box(cell+.03,cell+.03,depth+.12,s,t,-depth)
                   for s,t,cell in pixels(text,height)).basis(u,v,n,origin)
    def engraving(unlabelled,label,text,height,origin,u,v,n,where):
        removed=float((unlabelled&label).m.volume())
        expected=float(label.m.volume())*.2/(.2+.12)
        return dict(text=text,type='planar',height_mm=height,depth_mm=.2,
                    origin_mm=list(origin),u=list(u),v=list(v),normal=list(n),
                    removed_mm3=round(removed,5),coverage_ratio=round(removed/expected,5),location=where)

    #2mm moving ears,0.2mm axial clearance at each fixed shoulder end.
    def arm(y):
        a=c.cyly(11.2,2,0,y,0);b=c.cyly(8,2,0,y,-L+12)
        return c.S((a+b).m.hull(),'hull(){'+a.code+b.code+'}')
    frame=c.U(arm(y) for y in (-27.3,25.3))
    for y in (-27.3,25.3):frame+=c.box(1,2,L-12,-3.5,y+1,-L+12)
    frame+=c.box(6,54.6,4,-1,0,-L+10)
    for y,h in [(-3.1,2.8),(16.3,5.6)]:
        frame+=c.cyly(10,h,0,y,-L)+c.box(6,h,12,-1,y+h/2,-L)
    # Full, broad back plane; no change is added below the original wheel fork.
    frame=frame&c.box(30,90,L+30,11,0,-L-10) # X>=-4
    frame-=c.cyly(3.4,30,0,-5,-L)
    frame-=c.cyl(6.4,1.5,d2=3.4).rot(x=-90).move(0,-3.1,-L)
    frame-=c.cyl(6.7,2.6,n=6).rot(x=-90).move(0,19.1,-L)
    frame-=c.box(6.5,2.6,22,0,20.4,-L)
    # The static axle spacer's flag sits in a keyed recess, with its ID beyond
    # the rotating wheel radius and away from the loaded spacer end faces.
    axle_key=c.cyly(5.4,.85,0,-1.1,-L)+c.box(10.2,.9,3.4,5.9,-.7,-L-1.7)
    frame-=axle_key
    for y in (-27.3,25.3):
        frame-=c.cyly(5.6,2.4,0,y-.2,0)
        # The entire headed pin enters from the side; its large head never has
        # to be forced through the bearing hole. The opening faces local-X,
        # hence downward throughout the normal and manual-lift range.
        frame-=c.box(8,2.4,5.6,-4,y+1,-2.8)
    # A continuous opposite/front plane keeps the open-hook horns off the
    # first layer. It adds material on the side rising away from the cards.
    for y in (-27.3,25.3):
        frame+=c.box(1.8,2,L-12,4.7,y+1,-L+12)
        frame+=c.box(1.8,2,10,4.7,y+1,-5)
    frame+=c.box(3.6,54.6,4,3.8,0,-L+10)
    for y,h in [(-3.1,2.8),(16.3,5.6)]:
        frame+=c.box(3.6,h,12,3.8,y+h/2,-L)
        frame+=c.box(1.6,h,5,4.8,y+h/2,-L-5)
    # Re-open the full wheel-nut loading channel through the widened crossbar.
    frame-=axle_key
    frame-=c.cyly(3.4,30,0,-5,-L)
    frame-=c.cyl(6.4,1.5,d2=3.4).rot(x=-90).move(0,-3.1,-L)
    frame-=c.cyl(6.7,2.6,n=6).rot(x=-90).move(0,19.1,-L)
    frame-=c.box(6.5,2.6,22,0,20.4,-L)
    frame_unlabelled=frame
    ga=glyph('P10A',1.8,(-4,0.,-L+12),(0,1,0),(0,0,1),(-1,0,0))
    frame-=ga

    wheel_unlabelled=c.cyly(12,16,0,0,-L)-c.cyly(5.4,18,0,-1,-L)
    # An end-face recess keeps this tiny ID below the running/end-bearing faces.
    gb=glyph('P10B',1.8,(0.,0.,-L+4.0),(1,0,0),(0,0,1),(0,-1,0))
    wheel=wheel_unlabelled-gb
    spacer_unlabelled=c.cyly(5,17.4,0,-1.1,-L)-c.cyly(3.4,19.4,0,-2.1,-L)
    spacer_unlabelled+=c.box(9.5,.8,3,6.25,-.7,-L-1.5)
    gc=glyph('P10C',1.8,(8.,-1.1,-L),(1,0,0),(0,0,1),(0,-1,0))
    spacer=spacer_unlabelled-gc

    walltop=c.hopper_roof_local_z(-45)
    holder=c.box(6,5.6,5.8,-48,31.7,walltop-4)
    holder+=c.cyly(11.2,4.8,-48,27.5,120)+c.cyly(5.2,2.44,-48,25.08,120)
    holder+=c.cyly(8.2,1.2,-48,23.9,120)
    holder=holder&c.box(30,60,40,-36,20,100) # broad plane X=-51
    wallgroove=c.box(8,2.6,30,-48,31.7,walltop-30)
    holder-=wallgroove
    # Tapered PETG contact ribs: a2.2mm relaxed throat on a2.4mm P08 wall.
    # This is an intentional0.1mm preload per jaw, not a rigid fit claim.
    def rib(points):return c.poly(points,6).basis((0,1,0),(0,0,1),(1,0,0),(-51,0,0))
    ribs=rib([(30.38,walltop-3),(30.6,walltop-2.25),(30.6,walltop-1.5),(30.38,walltop-.75)])
    ribs+=rib([(33.02,walltop-.75),(32.8,walltop-1.5),(32.8,walltop-2.25),(33.02,walltop-3)])
    holder+=ribs
    holder_unlabelled=holder
    gd=glyph('P10D',1.8,(-48,32.3,121.8),(1,0,0),(0,0,1),(0,1,0))
    holder-=gd

    axle_screw=c.flat_screw(25).rot(x=-90).move(0,-3.1,-L)
    axle_nut=c.hex_nut3(0,0,0).rot(x=-90).move(0,19.3,-L)
    fixed_hw=[]
    moving_hw=[('wheel_screw',axle_screw),('wheel_nut',axle_nut)]
    specs={
      'P10A':dict(name='重力擺輪架',shape=frame,unlabelled=frame_unlabelled,qty=1,print_rot=(0,90,0),
                   support='原生X+5.6完整平面貼床，C鉤開口在上層；輪軸橫孔/螺母槽局部支撐待切片',
                   engraving=engraving(frame_unlabelled,ga,'P10A',1.8,(-4,0,-L+12),(0,1,0),(0,0,1),(-1,0,0),'內側橫梁反面，避開貼床平面及接觸面')),
      'P10B':dict(name='自由壓牌輪',shape=wheel,unlabelled=wheel_unlabelled,qty=1,print_rot=(90,0,0),
                   support='輪軸垂直列印；小底面可加brim',
                   engraving=engraving(wheel_unlabelled,gb,'P10B',1.8,(0,0,-L+4),(1,0,0),(0,0,1),(0,-1,0),'端面凹字區，避開外圓壓牌與內孔')),
      'P10C':dict(name='輪軸隔套含編號耳',shape=spacer,unlabelled=spacer_unlabelled,qty=1,print_rot=(90,0,0),
                   support='軸向垂直列印，編號耳朝床；建議brim',
                   engraving=engraving(spacer_unlabelled,gc,'P10C',1.8,(8,-1.1,-L),(1,0,0),(0,0,1),(0,-1,0),'外延標記耳，避開轉動外圓/軸孔/端面承壓')),
      'P10D':dict(name='純打印邊牆夾與帶頭樞軸',shape=holder,unlabelled=holder_unlabelled,qty=2,print_rot=(0,-90,0),
                   support='X背面貼床，U夾彎曲在層內；肩軸局部橋接待切片；用PETG試印',
                   engraving=engraving(holder_unlabelled,gd,'P10D',1.8,(-48,32.3,121.8),(1,0,0),(0,0,1),(0,1,0),'肩座外端隱藏面，避開壁槽/承軸/滑動面'))}
    return SimpleNamespace(PARTS=specs,FRAME=frame,WHEEL=wheel,SPACER=spacer,HOLDER=holder,
        MIRROR=mirror,shape_pose=pose,FIXED_HARDWARE=fixed_hw,MOVING_HARDWARE=moving_hw,
        PRELOAD_RIBS=ribs,theta_empty=theta0,arm_length=L,pivot_XZ=H,
        metadata=dict(roller_diameter_mm=12,roller_width_mm=16,roller_Y_mm=[0,16],
            empty_roller_center_XZ_mm=list(E),empty_floor_normal_gap_mm=0,
            pivot_XZ_mm=list(H),arm_length_mm=L,empty_rear_edge_X_mm=-9.65,
            nominal_projected_P17_outer_edge_gap_mm=2,lower_swing_stop_present=False,
            wheel_axial_clearance_each_mm=.3,pivot_radial_clearance_mm=.2,
            pivot_axial_clearance_each_mm=.2,pivot_head_diameter_mm=8.2,pivot_retaining_overlap_mm=1.3,
            pivot_frame_thickness_mm=2,pivot_shoulder_length_mm=2.4,
            pivot_shoulder_diameter_mm=5.2,pivot_frame_bore_mm=5.6,
            clamp_mirror_common_part=True,clamp_clear_slot_width_mm=2.6,clamp_relaxed_throat_mm=2.2,
            P08_wall_thickness_mm=2.4,nominal_PETG_preload_each_side_mm=.1,clip_leg_depth_mm=4,
            clamp_slot_ceiling_native_Z_mm=walltop,side_hardware_qty=0,
            nominal_pivot_X_mm=-48,safe_forward_adjustment_range_mm=[0,6],safe_pivot_X_range_mm=[-48,-42],
            both_clips_must_be_aligned_same_X=True,adjustment_follows_rim_slope=True,
            pivot_hook_opening_direction_frame_local=[-1,0,0],pivot_slot_opening_mm=5.6,
            pin_insertion_method='Slide headed shoulder pin through local-X open bearing mouth; do not force its head through the bore.',
            wall_clip_installation='Preassemble frame on both headed pins, lower PETG clips over walls. Slide both equally along wall; no screw or lower stop.',
            radial_hook_is_gravity_seated_not_a_pull_lock=True,
            minimum_label_nominal_stroke_mm=.39,
            roller_offset_aligns_existing_P17_rubber_Y5_Y11=True,
            new_hardware={'DIN7991 M3x25':1,'M3 nut':1},
            P11_compatible=False,physical_fit_force_grip_and_feed_tested=False))
