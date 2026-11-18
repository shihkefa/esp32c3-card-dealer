"""Tall separation gate and full-width30degree rubber seat.

This factory does not install itself into the assembly or alter reference-card
actors. The original outer ears, slots, nut channels and identifier survive.
The rubber's lowest outer edge retains the0.45mm nominal separation throat.
"""
from types import SimpleNamespace
import math

def build(c,parts):
    old=parts['P09'].shape
    bottom=64.45
    spec=c.P['P09_tall_full_width_sloped_gate']
    angle=math.radians(spec['slant_angle_from_vertical_deg'])
    pad_height=spec['rubber_along_surface_dimensions_mm'][1]
    top_front_x=spec['ear_aligned_incoming_plane_native_X_mm']
    toe_x=top_front_x+pad_height*math.sin(angle)
    top_rear_x=top_front_x+spec['upper_panel_thickness_mm']
    native_drop=spec['drop_below_hopper_rim_mm']/math.cos(math.radians(c.P['hopper_tilt_deg']))
    top_front_z=c.hopper_roof_local_z(top_front_x)-native_drop
    top_rear_z=c.hopper_roof_local_z(top_rear_x)-native_drop
    upper_front=lambda z:top_front_x
    pad_width,_,pad_thickness=spec['rubber_along_surface_dimensions_mm']
    adhesive=spec['backing_adhesive_thickness_normal_mm']
    backing_offset=pad_thickness+adhesive
    # Extend the backing plane from the horizontal sole to the ear-aligned wall.
    backing_toe_x=toe_x+backing_offset/math.cos(angle)
    backing_length=(backing_toe_x-top_front_x)/math.sin(angle)
    slant_upper_z=bottom+backing_length*math.cos(angle)
    transition_z=slant_upper_z+1.95
    rear_x=spec['rear_base_native_X_mm']
    shoulder_z=spec['rear_shoulder_native_Z_mm']
    profile=[(backing_toe_x,bottom),(rear_x,bottom),(rear_x,shoulder_z),
        (top_rear_x,shoulder_z),
        (top_rear_x,top_rear_z),(top_front_x,top_front_z),
        (top_front_x,slant_upper_z)]
    # Extrude relative to the exact box-bottom datum. Clipper's absolute2D
    # coordinate rounding would otherwise make a nanometre bottom step against
    # the retained ears, which collapses into degenerate float32STL triangles.
    main=c.poly([(x,z-bottom) for x,z in profile],61).basis(
        (1,0,0),(0,0,1),(0,-1,0),(0,30.5,bottom))
    width_profile=[(-30.5,-1),(30.5,-1),(30.5,slant_upper_z-bottom),
        (30.2,transition_z-bottom),(30.2,top_rear_z-bottom+1),
        (-30.2,top_rear_z-bottom+1),(-30.2,transition_z-bottom),
        (-30.5,slant_upper_z-bottom)]
    width_mask=c.poly(width_profile,120).basis((0,1,0),(0,0,1),(1,0,0),(0,0,bottom))
    main&=width_mask
    central_cut=c.box(120,61,120,47.5,0,40)
    outer=old-central_cut
    unlabelled_outer=c.LABEL_BASE_SHAPES['P09']-central_cut
    # Rear bridges give positive-volume joins on both sides of the exact
    # channel boundary. They introduce no square edge on the incoming face.
    join_start_x=backing_toe_x+.1
    joins=c.U(c.box(rear_x-join_start_x,.4,3.8,(rear_x+join_start_x)/2,side*30.5,bottom) for side in (-1,1))
    main+=joins
    # Connect the ear fronts to the broad wall at the bed datum. The lower
    # webs stay outside the lane; the upper webs meet the vertical wall above
    # the backing plane and blend into the existing solid mounting ears.
    ear_bridges=[]
    for side in (-1,1):
        ear_bridges.append(c.box(2,2.2,11,top_front_x+1,side*31.6,bottom))
        ear_bridges.append(c.box(2,2.7,bottom+11-slant_upper_z,top_front_x+1,side*31.35,slant_upper_z))
    main+=c.U(ear_bridges)
    # u follows card width, v rises upstream, n points into the printed body.
    u=(0,1,0);v=(-math.sin(angle),0,math.cos(angle));n=(math.cos(angle),0,math.sin(angle))
    origin=(toe_x,0,bottom)
    pose=lambda s:s.basis(u,v,n,origin)
    pad=pose(c.box(pad_width,pad_height,pad_thickness,0,pad_height/2,0))
    shape=outer+main
    unlabelled=unlabelled_outer+main
    glyph=c.LABEL_BASE_SHAPES['P09']-old
    print_y=-90
    metadata=dict(changed_print_ids=['P09'],unchanged_outer_ears_slots_nut_channels_ID=True,
        original_main_width_Y_mm=66,new_main_width_Y_mm=61,
        full_width_slanted_face_Y_mm=61,rubber_surface_width_Y_mm=55,
        same_slope_plastic_width_each_side_mm=3,
        upper_main_width_Y_mm=60.4,
        width_transition_native_Z_mm=[slant_upper_z,transition_z],
        retained_outer_stubs_start_abs_Y_mm=30.5,lower_main_half_width_Y_mm=30.5,
        upper_main_half_width_Y_mm=30.2,
        rear_join_overlap_each_side_Y_mm=.2,card_channel_width_mm=61,
        nominal_upper_wall_to_P08_each_side_mm=.3,
        native_profile_XZ_mm=[list(p) for p in profile],
        top_front_native_XZ_mm=[top_front_x,top_front_z],
        top_rear_native_XZ_mm=[top_rear_x,top_rear_z],
        world_top_target_mm=spec['nominal_top_world_Z_mm'],
        drop_below_hopper_rim_mm=spec['drop_below_hopper_rim_mm'],
        original_card_face_native_X_mm=spec['original_incoming_plane_native_X_mm'],
        ear_aligned_card_face_native_X_mm=top_front_x,
        central_wall_to_original_face_shift_native_X_mm=top_front_x-spec['original_incoming_plane_native_X_mm'],
        recess_into_ear_aligned_face_mm=toe_x-top_front_x,
        connected_ear_front_bridges=True,
        original_gate_bottom_native_Z_mm=bottom,floor_native_Z_mm=64,
        nominal_separation_throat_mm=.45,
        pad_dimensions_surface_width_height_thickness_mm=[55,4,1],
        pad_incoming_angle_from_vertical_deg=30,
        pad_lowest_outer_native_XYZ_mm=list(origin),pad_basis_u=list(u),pad_basis_v=list(v),pad_basis_n=list(n),
        direct_centered_pad_on_open_backing=True,retained_pocket_or_side_rails=False,
        bare_backing_single_plane_width_mm=61,bare_backing_length_mm=backing_length,
        bare_backing_toe_native_XZ_mm=[backing_toe_x,bottom],
        bare_backing_vertical_height_mm=slant_upper_z-bottom,
        rubber_face_vertical_height_mm=pad_height*math.cos(angle),
        bare_backing_setback_normal_to_rubber_outer_face_mm=backing_offset,
        adhesive_thickness_normal_mm=adhesive,
        rubber_cut_and_adhesive_thickness_physically_tested=False,
        upper_incoming_plane_slope_dx_dz=0.0,upper_plane_anchor_XZ_mm=[top_front_x,slant_upper_z],
        upper_panel_flat_and_normal_to_hopper_floor=True,upper_panel_thickness_mm=top_rear_x-top_front_x,
        rear_shoulder_shelf_depth_mm=rear_x-top_rear_x,
        rear_shoulder_side_height_mm=shoulder_z-bottom,
        sloped_band_vertical_height_mm=slant_upper_z-bottom,sloped_band_ends_native_Z_mm=slant_upper_z,
        print_rotation_deg=[0,print_y,0],
        reference_cards_translated_by_factory=False,
        suggested_unfed_96mm_load_reference_shift_native_X_mm=-4,
        actual_feed_performance_validated=False,full_assembly_clearance_qualified=False)
    return SimpleNamespace(SHAPE=shape,UNLABELLED=unlabelled,GLYPH=glyph,
        OUTER_RETAINED=outer,CENTRAL_CUT=central_cut,MAIN=main,REAR_JOINS=joins,
        PAD_NATIVE=pad,ENGRAVING=dict(parts['P09'].engraving),
        PRINT_ROT=(0,print_y,0),UPPER_FRONT_X=upper_front,metadata=metadata)
