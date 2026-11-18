"""PCB-edge OLED clamp and corrected rotated SSD1306 module reference.

Only P28 and the local OLED area of P32A change.  Four short PETG tongues
have 0.1mm nominal PCB preload; glass is clear of the roof, not a clamp stop.
The user's drawing and underside photograph establish different facts: board
dimensions come from the drawing; header toward +X is the photo interpretation.
Component heights, solder and actual flexure force still require a trial fit.
"""
from types import SimpleNamespace

CENTER=(75.,-24.)
OLD_MOUNTS=((57.,-24.),(93.,-24.))
MOUNTS=((75.,-42.),(75.,-6.))
PCB_BOTTOM=125.3
PCB_TOP=126.5
PRELOAD=.1

def build(c,parts):
    # The old square-ish PCB was combined with a rotated glass/header model.
    # Refill only the old local cuts, keeping all other housing surfaces/IDs.
    roof=parts['P32A'].shape
    for x,y in OLD_MOUNTS:
        roof-=c.cyl(7.1,3.55,x,y,122.95) # stop at the inner roof plane126.5
        roof+=c.cyl(2.8,1.1,x,y,126.5)   # repair the old blind pilot in roof
    roof+=c.rr(20.3,27.7,.5,2.2,*CENTER,126.5)
    # AA centre is2.1mm toward the header at +X; no PCB translation.
    window=c.rr(14,24,.5,4,77.1,-24,126.0)
    recess=c.rr(19.86,27.3,.3,2,75,-24,126.3)
    roof-=window+recess
    # A low-profile front-side solder allowance, not a universal pin-header fit.
    header_relief=c.rr(3.2,11,.4,1.1,87.4,-24,126.3)
    roof-=header_relief
    for x,y in MOUNTS:
        roof+=c.cyl(7,3.6,x,y,123)
        roof-=c.hole(x,y,119,8.6,2.7)

    # Flat-backed base, accessible central opening and +X wire exit.
    base=c.rr(31,32,3,3.5,*CENTER,119.5)-c.rr(25.4,26,1,5,*CENTER,119.3)
    base-=c.box(8,12,5,89.2,-24,119.3)
    for x,y in MOUNTS:
        base+=c.cyl(8,3.5,x,y,119.5)
        base-=c.hole(x,y,119.3,4)
        base-=c.cyl(6.4,1.7,x,y,119.4,d2=3.4)

    # 45-degree ramp tongues print from the same flat base. The0.6mm vertical
    # web is intentionally compliant, not a solid2.4mm compression spacer.
    frame=base
    tongues=[];pad_shapes=[];preload_regions=[];contact_regions=[]
    for side in (-1,1):
        root=75+side*13.5
        tip=75+side*11.1
        for dy in (-8.8,8.8):
            y=-24+dy
            # Keep the beam top0.05mm below the pad top. Coincident decimal
            # faces would create sliver triangles on float32 STL export.
            profile=[[root,122.35],[root,122.95],[tip,125.35],[tip,124.75]]
            if side<0:profile.reverse()
            tongue=c.poly(profile,1.6).basis((1,0,0),(0,0,1),(0,-1,0),(0,y+.8,0))
            # Begin the full-width contact root before the tapered beam tip
            # narrows below a0.4mm-nozzle extrusion. The first actual slice
            # otherwise lost model layerZ5.6 before the old0.3mm cap began.
            # Top/contact footprint/preload stay unchanged.
            pad=c.box(1.4,1.6,.7,tip,y,124.7)
            tongues.append(tongue);pad_shapes.append(pad)
            base+=tongue+pad
            # Bound only the top0.1mm of each contact. No whole-part overlap
            # exemption is granted to the clamp or the circuit board.
            region=c.box(1.4,1.6,.10001,tip,y,125.3)
            preload_regions.append(region)
            contact_regions.append(dict(center_XY_mm=[tip,y],
                rectangular_pad_XY_mm=[1.4,1.6],free_top_native_Z_mm=125.4,
                PCB_contact_native_Z_mm=125.3,nominal_preload_mm=.1,
                maximum_allowed_nominal_overlap_mm3=.2241,
                pad_AABB_native_mm=[tip-.7,y-.8,125.3,tip+.7,y+.8,125.40001]))
    unlabelled=base
    origin=(60.9,-24,119.5);height=2.2;depth=.25
    glyph=c.U(c.box(cell+.03,cell+.03,depth+.12,s,t,-depth)
              for s,t,cell in c.letter_pixels('P28',height))
    glyph=glyph.basis((0,1,0),(1,0,0),(0,0,-1),origin)
    removed=float((base&glyph).m.volume())
    expected=float(glyph.m.volume())*depth/(depth+.12)
    assert removed/expected>.99,(removed,expected,removed/expected,glyph.m.bounding_box(),base.m.bounding_box())
    clamp=base-glyph
    engraving=dict(text='P28',type='planar',height_mm=height,depth_mm=depth,
        location='固定框負X側底面隱藏實心邊；避開PCB接觸、彈舌及螺絲孔',
        origin_mm=list(origin),normal=[0,0,-1],u=[0,1,0],v=[1,0,0],
        removed_mm3=round(removed,4),coverage_ratio=round(removed/expected,4))

    # Module reference: +X is the header edge; its long display dimension isY.
    pcb=c.box(27.8,27.3,1.2,*CENTER,PCB_BOTTOM)
    for x in (63.1,86.9):
        for y in (-35.65,-12.35):pcb-=c.hole(x,y,125.2,1.5,2)
    # The drawing's nominal2.7mm total is0.1mm more than1.2+1.4.
    # Keep that0.1 as an explicitly conditional adhesive/reference layer.
    glass=c.box(19.26,26.7,1.4,*CENTER,126.6)
    glass_max=c.box(19.26,26.7,1.7,*CENTER,126.5)
    aa=c.box(10.86,21.74,.02,77.1,-24,128.0)
    # Back-side parts are a conservative central envelope based on the photo;
    # footprints and height are not claimed to be measured.
    components=c.box(18,21,2.0,*CENTER,123.3)
    solder=c.U(c.cyl(1.5,.3,87.4,y,126.5)+c.cyl(.65,1.0,87.4,y,124.3)
               for y in (-27.81,-25.27,-22.73,-20.19))
    wires=c.U(c.cylx(.85,5,87.4,y,124.4) for y in (-27.81,-25.27,-22.73,-20.19))
    header=solder+wires
    screws=[c.flat_screw(8).move(x,y,119.5) for x,y in MOUNTS]
    metadata=dict(
        changed_print_ids=['P28','P32A'],OLED_center_native_XY_mm=list(CENTER),
        old_mounts_native_XY_mm=[list(p) for p in OLD_MOUNTS],
        mounts_native_XY_mm=[list(p) for p in MOUNTS],mounts_rotated_about_center_deg=90,
        header_direction='+X',header_direction_inferred_from_user_photo=True,
        PCB_dimensions_XYZ_mm=[27.8,27.3,1.2],PCB_native_Z_mm=[125.3,126.5],
        glass_dimensions_XYZ_mm=[19.26,26.7,1.4],glass_native_Z_mm=[126.6,128.0],
        adhesive_or_drawing_stack_difference_mm=.1,adhesive_layer_measured=False,
        user_drawing_overall_thickness_nominal_mm=2.7,user_drawing_overall_thickness_max_mm=2.9,
        maximum_glass_reference_native_Z_mm=[126.5,128.2],
        AA_dimensions_XY_mm=[10.86,21.74],AA_center_native_XY_mm=[77.1,-24.],
        AA_offset_toward_header_mm=2.1,window_dimensions_XY_mm=[14.,24.],
        window_center_native_XY_mm=[77.1,-24.],
        glass_recess_dimensions_XY_mm=[19.86,27.3],glass_recess_top_native_Z_mm=128.3,
        cosmetic_roof_top_native_Z_mm=128.7,minimum_local_roof_skin_mm=.4,
        nominal_maximum_glass_to_roof_clearance_mm=.1,
        clamp_base_native_Z_mm=[119.5,123.],screw_head_native_Z_mm=119.5,
        screw_length_mm=8,screw_count=2,new_screw_SKUs_added=False,
        clamp_material='PETG',printed_compliant_tongue_count=4,
        tongue_vertical_thickness_mm=.6,tongue_ramp_deg=45,
        contact_free_native_Z_mm=125.4,nominal_PCB_preload_mm=.1,
        contact_pad_native_Z_mm=[124.7,125.4],contact_pad_root_height_mm=.7,
        PCB_contact_regions=contact_regions,
        rigid_clamp_does_not_use_glass_as_stop=True,
        component_envelope_dimensions_mm=[18,21,2.0],component_positions_physically_measured=False,
        pin_and_wire_reference_conditional=True,full_pin_header_fit_claimed=False,
        physical_fit_clamp_force_and_display_visibility_tested=False)
    return SimpleNamespace(SHAPES={'P28':clamp,'P32A':roof},
        ENGRAVINGS={'P28':engraving,'P32A':dict(parts['P32A'].engraving)},
        UNLABELLED=unlabelled,GLYPH=glyph,TONGUES=tongues,CONTACT_PADS=pad_shapes,
        PRELOAD_GAUGE_NATIVE=c.U(preload_regions),
        P28_RIGID=clamp-c.U(tongues+pad_shapes),BASE_FRAME=frame-glyph,
        PRELOAD_REGIONS=preload_regions,PCB=pcb,COMPONENTS=components,
        GLASS=glass,MAXIMUM_GLASS=glass_max,HEADER=header,AA=aa,
        HARDWARE_NATIVE={'screenpcb':pcb+components,'OLEDglass':glass,'screenheader':header},
        SCREWS=screws,WINDOW=window,RECESS=recess,HEADER_RELIEF=header_relief,
        metadata=metadata)
