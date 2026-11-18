"""Radial home-sensor layout; reuses P25 and the P04A flag mounting hole.

The measured outer body matches13x6x10mm. Slot/floor/optical-axis dimensions
are conditional ITR9608-F data-sheet references and need physical checking.
"""
from types import SimpleNamespace
import math


def build(c,parts):
    radius=float(c.P.get('home_radial_layout',{}).get('radius_mm',77.5))
    phi=float(c.P.get('home_radial_layout',{}).get('azimuth_deg',155.0))
    angle=math.radians(phi);hx=radius*math.cos(angle);hy=radius*math.sin(angle)
    theta=phi-180
    def repose(s):return s.move(x=74.5,y=-10).rot(z=theta).move(hx,hy)
    a=c.rr(164,148,16,3,z0=30)+c.cyl(164,3,z0=30)
    a+=c.cyl(164,8.6,z0=32.9)-c.cyl(159.6,9,z0=32.8)
    a-=c.cyl(58.4,5,z0=29)+c.hole(54,0,29,7,24)
    for yy in (-17.5,17.5):
        a-=c.hole(47,yy,29,8,3.8)+c.cyl(6.4,1.7,d2=3.8).rot(x=180).move(47,yy,32.8)
        a-=c.cyl(6.4,.6,47,yy,32.7)
    for x in (-68,68):
        for y in (-58,58):a-=c.hole(x,y,29,6)+c.cyl(6.4,1.7,d2=3.4).rot(x=180).move(x,y,33.1)
    for x,y in c.BEARING_MOUNTS:a-=c.hole(x,y,29,6,10.4)
    # Rebuild clean original stock: old home holes/windows are filled, and only
    # their transformed counterparts are cut. Bearing/motor/cover holes stay put.
    a+=repose(c.box(18,14,3,-70.5,10,30))
    a-=repose(c.box(13.6,3.6,12,-74.5,14.9,29)+c.hole(-63.5,10,28,9,2.7))
    a-=repose(c.box(14,8,10,-74.5,10,33.1))
    for x in (-79.5,-69.5):
        for y in (8.73,11.27):a-=repose(c.hole(x,y,26,9,1.2))
    p02_unlabelled=a
    p02_glyph=c.LABEL_BASE_SHAPES['P02A']-parts['P02A'].shape
    p02=a-p02_glyph
    a_end=c.cyl(10,1.4,-58,10,40.6);b_end=c.cyl(10,1.4,hx,hy,40.6)
    arm=c.S((a_end+b_end).m.hull(),'hull(){'+a_end.code+b_end.code+'}')
    arc=c.P.get('P26_arc_revision',{})
    inner=float(arc.get('inner_radius_mm',77.0));outer=float(arc.get('outer_radius_mm',78.0))
    mid=(inner+outer)/2;arc_length=float(arc.get('midline_arc_length_mm',7.0))
    segments=64;span=arc_length/mid
    assert abs(mid-radius)<1e-8,'The shutter arc must remain concentric with its radial home layout'
    angles=[angle-span/2+span*i/segments for i in range(segments+1)]
    points=[(outer*math.cos(a),outer*math.sin(a)) for a in angles]
    points += [(inner*math.cos(a),inner*math.sin(a)) for a in reversed(angles)]
    blade=c.poly(points,8.9,33.1)
    p26_unlabelled=arm+blade-c.hole(-58,10,39,7)-c.cyl(6.4,1.7,-58,10,40.5,d2=3.4)
    # Complete ID on the new hidden arm underside, away from the optical fin
    # and both the bolt cone and the P04A contact face. No buried old ID void.
    length=math.hypot(hx+58,hy-10);u=((hx+58)/length,(hy-10)/length,0)
    v=(u[1],-u[0],0);n=(0,0,-1);origin=((hx-58)/2,(hy+10)/2,40.6)
    glyph=c.U(c.box(cell+.03,cell+.03,.37,s,t,-.25) for s,t,cell in c.letter_pixels('P26',2.5))
    glyph=glyph.basis(u,v,n,origin);p26=p26_unlabelled-glyph
    removed=float((p26_unlabelled-p26).m.volume())
    expected=sum((cell+.03)**2*.25 for _,_,cell in c.letter_pixels('P26',2.5))
    engraving=dict(text='P26',type='planar',height_mm=2.5,depth_mm=.25,
        origin_mm=list(origin),u=list(u),v=list(v),normal=list(n),
        removed_mm3=round(removed,4),coverage_ratio=round(removed/expected,4),
        location='新斜臂隱藏底面；避開光電遮光片、螺絲座及P04A接觸面')
    sensor=c.box(13,6,10)-c.box(5,8,6.2,0,0,4.1)
    for x in (-5,5):
        for y in (-1.27,1.27):sensor+=c.cyl(.4,6,x,y,-6)
    sensor=repose(sensor.move(-74.5,10,33.3))
    bolt=repose(c.cyl(.01,.01,-63.5,10,0)).m.bounding_box()
    bx=(bolt[0]+bolt[3])/2;by=(bolt[1]+bolt[4])/2
    inward=(math.cos(math.radians(theta)),math.sin(math.radians(theta)))
    return SimpleNamespace(P02A_SHAPE=p02,P02A_UNLABELED=p02_unlabelled,
        P26_SHAPE=p26,P26_UNLABELED=p26_unlabelled,P26_GLYPH=glyph,
        P26_ENGRAVING=engraving,BLADE=blade,ARM=arm,SENSOR_NATIVE=sensor,repose=repose,
        metadata=dict(home_center_XY_mm=[hx,hy],azimuth_deg=phi,radius_mm=radius,
            radial_inward_angle_deg=theta%360,radial_inward_unit_XY=list(inward),
            radial_axis_cross_origin_error_mm=abs(hx*inward[1]-hy*inward[0]),
            old_home_center_XY_mm=[-74.5,10],old_to_new_rotation_Z_deg=theta,
            home_mount_bolt_XY_mm=[bx,by],P25_STL_reused=True,
            blade_center_native_XY_mm=[hx,hy],blade_thickness_radial_mm=1,
            blade_width_tangential_mm=2*outer*math.sin(span/2),blade_native_Z_mm=[33.1,42],
            blade_shape='concentric_arc',blade_inner_radius_mm=inner,blade_outer_radius_mm=outer,
            blade_mid_radius_mm=mid,blade_midline_arc_length_mm=arc_length,
            blade_arc_span_rad=span,blade_arc_span_deg=math.degrees(span),
            blade_arc_segment_count=segments,blade_arc_angular_center_deg=phi,
            blade_arc_chord_error_bound_mm=outer*(1-math.cos(span/(2*segments))),
            P04A_flag_anchor_native_XY_mm=[-58,10],arm_native_Z_mm=[40.6,42],
            blade_minimum_rotation_radius_mm=inner,
            blade_maximum_rotation_radius_mm=outer,
            blade_faceted_minimum_radius_bound_mm=inner*math.cos(span/(2*segments)),
            P05_conservative_maximum_radius_mm=76,
            minimum_P05_radial_clearance_mm=radius-.5-76,
            sensor_body_dimensions_XYZ_mm=[13,6,10],sensor_body_bottom_world_Z_mm=53.4,
            conditional_ITR9608_F_slot_width_mm=5,conditional_slot_floor_height_mm=4.1,
            conditional_optical_axis_height_mm=6.8,conditional_slot_floor_world_Z_mm=57.5,
            conditional_optical_axis_world_Z_mm=60.2,sensor_body_top_world_Z_mm=63.4,
            datasheet_reference='source/references/wiring/itr9608-f-p2.png',
            actual_sensor_model_confirmed=False,physical_fit_and_homing_detection_tested=False))
