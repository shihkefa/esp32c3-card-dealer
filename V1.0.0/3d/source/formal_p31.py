"""Plain U cover, retained by the original adjuster head, with closed shaft stops.

Both rear faces are straight planes. There are no hooks or spring-fit parts.
Remove the adjuster before lifting/lowering the cover; do not clamp it down.
"""
from types import SimpleNamespace


def build(c,parts):
    top=c.box(20.4,12.6,1.5,61,-36.4,87.15)
    rear=c.box(20.4,1.2,14.7,61,-42.1,72.45)
    front=c.box(20.4,1.2,8.65,61,-30.7,78.5)
    head_clearance=c.cyl(3.4,4,61,-35,86)
    head_clearance+=c.cyl(6.4,1.5,d2=3.4).rot(x=180).move(61,-35,88.65)
    head_clearance+=c.cyl(6.4,.15,61,-35,88.65)
    bearing_clearance=c.cyly(11,4,61,-32,75.55)
    unlabelled=top+rear+front-head_clearance-bearing_clearance
    glyph=c.U(c.box(cell+.03,cell+.03,.34,s,t,-.22)
              for s,t,cell in c.letter_pixels('P31',1.8))
    glyph=glyph.basis((1,0,0),(0,0,1),(0,-1,0),(61,-42.7,80.1))
    shape=unlabelled-glyph
    # P15 is regenerated with exactly its already-released dimensions/glyph.
    p15_unlabelled=c.LABEL_BASE_SHAPES['P15']+c.box(13.3,2.8,12,61,-39.6,68.75)
    p15_unlabelled-=c.cyly(3.5,14,61,-42,74.75)
    p15_glyph=(c.LABEL_BASE_SHAPES['P15']-parts['P15'].shape).move(y=-2.75)
    p15=p15_unlabelled-p15_glyph
    removed=float((unlabelled-shape).m.volume())
    expected=sum((cell+.03)**2*.22 for _,_,cell in c.letter_pixels('P31',1.8))
    engraving={'text':'P31','type':'planar','height_mm':1.8,'depth_mm':.22,
        'origin_mm':[61,-42.7,80.1],'normal':[0,-1,0],'u':[1,0,0],'v':[0,0,1],
        'removed_mm3':round(removed,4),'coverage_ratio':round(removed/expected,4),
        'location':'罩內隱藏外背面；避開內側軸端止擋、頂梁承壓及滑塊限位面'}
    return SimpleNamespace(SHAPE=shape,UNLABELED=unlabelled,OPENED=shape,
        REAR_PANEL=rear,SHAFT_END_PLATE=rear,GLYPH=glyph,
        P15_SHAPE=p15,P15_UNLABELED=p15_unlabelled,P15_GLYPH=p15_glyph,engraving=engraving,
        metadata={'cap_dimensions_native_mm':[20.4,12.6,16.2],'qty':2,
            'second_instance_rotation_Z_deg':180,'second_instance_translation_X_mm':122,
            'P15_rear_extension_mm':2.75,'P15_new_back_Y_mm':-41,
            'P15_bore_diameter_mm':3.5,'P15_original_bearing_seat_and_front_unchanged':True,
            'top_adjustment_shaft_hole_mm':3.4,'top_adjustment_countersink_mouth_mm':6.4,
            'top_adjustment_countersink_angle_deg':90,'adjuster_head_normal_lift_gap_mm':.3,
            'adjuster_low_end_contact_at_vertical_offset_mm':-.3,'top_panel_bottom_Z_mm':87.15,
            'cap_bottom_Z_mm':72.45,'hooks_present':False,'front_and_rear_hooks_present':False,
            'outer_wall_planar':True,'rear_wall_inner_Y_mm':-41.5,'rear_wall_outer_Y_mm':-42.7,
            'straight_installation_without_spreading':True,'retention_mode':'original height-adjuster screw head',
            'shaft_stop_inner_Y_mm':[-41.5,41.5],'reference_upper_shaft_length_mm':82,
            'upper_shaft_before_Y_mm':[-40,42],'upper_shaft_new_Y_mm':[-41,41],
            'upper_shaft_centering_translation_Y_mm':-1,'nominal_axial_gap_each_mm':.5,
            'nominal_total_axial_endplay_mm':1,'shaft_end_face_not_radially_clamped':True,
            'nominal_slider_play_mm':{'toward_roller':.45,'outward':.5},
            'slider_native_vertical_travel_mm':[-.3,.8],
            'cap_float_min_relative_Z_mm':-.15,'cap_float_max_relative_Z_mm_formula':'.3 + slider_dz',
            'cap_float_normal_relative_Z_mm':[-.15,.3],
            'manual_leg_opening_for_installation_mm_each':0,
            'assembly_direction':'Seat pedestals, sliders and bearings first; center the82mm upper shaft. Remove original adjuster, lower cover straight down, reinstall and adjust screw without clamping cover.',
            'removal_direction':'Remove original adjuster screw first and lift cover straight up; no spreading is required.',
            'only_upper_shaft_actor_centered_in_this_revision':True,'all_fastener_positions_unchanged':True,
            'new_hardware_qty':0,'recommended_material':'PETG',
            'physical_plain_fit_and_shaft_end_thrust_friction_tested':False})
