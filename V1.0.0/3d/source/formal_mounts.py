"""Companion mounts for the integrated P04A/P31 revision.

The four pillow and two RF-clamp bolts enter from below. Their nuts now
bear DOWN onto the corresponding upper mount; the bolt heads bear UP
onto the integrated frame. All coordinates here precede incline/head lift.
This module is pure geometry and does not import the integrating builder.
"""

PILLOW_X=(52.5,69.5)
PILLOW_Y=(-35.0,35.0)
PILLOW_HEAD_Z=43.5
PILLOW_NUT_BOTTOM=48.9
PILLOW_POCKET_BOTTOM=48.9
PILLOW_POCKET_HEIGHT=2.7
RF_X=(46.5,75.5)
RF_Y=-74.3
RF_HEAD_Z=43.9
RF_NUT_BOTTOM=66.4
RF_PAD_BOTTOM=65.2
RF_PAD_TOP=69.2
PILLOW_BACK_PAD_MM=2.5
PILLOW_OUTER_HALF_Y_MM=6.0
PILLOW_ADJUST_CSINK_TOP_Z=87.0
PILLOW_ADJUST_CSINK_DIAMETER=6.4
PILLOW_ADJUST_CSINK_PILOT=2.7
PILLOW_ADJUST_CSINK_DEPTH=1.85


def _label_cut(c,parts,pid):
    """Retain the original hidden identifier without copying its old holes."""
    return c.LABEL_BASE_SHAPES[pid]-parts[pid].shape


def _pillow(c,side):
    y=side*35
    a=c.rr(25,12,3,4,61,y,45.4)
    a=a+c.box(20,7,19,61,y,49.3)
    a=a+c.box(3.0,7,19,52.5,y,67)+c.box(3.0,7,19,69.5,y,67)
    a=a+c.box(20,7,4,61,y,83)
    # Keep the full existing guide window open. Extend only the outer back
    # of the core, two guide rails and top bridge to the base's existing
    # +/-6mm outer plane, making one broad flat printable U-shaped face.
    back_y=y+side*4.75
    a+=c.box(20,PILLOW_BACK_PAD_MM,19,61,back_y,49.3)
    for x in PILLOW_X:
        a+=c.box(3,PILLOW_BACK_PAD_MM,19,x,back_y,67)
        # Support the complete outward projection of each 8mm foot boss.
        # Their nut seats and loading throats are recut below.
        a+=c.box(8,6,2.1,x,y+side*3,49.3)
    a+=c.box(20,PILLOW_BACK_PAD_MM,4,61,back_y,83)
    a=a-c.cyly(3.5,15,61,y-7.5,54.2)
    a=a-c.cyly(10.3,7.5,61,-35.8 if side<0 else 28.3,54.2)
    a=a-c.hole(61,y,81,9,2.7)
    # Proper90-degree M3 head clearance, while keeping the2.7mm adjustment
    # pilot and all screw/slider positions. The overcut ensures a true6.4mm
    # opening at the physical Z87 face rather than a smaller hidden chamfer.
    a-=c.cyl(PILLOW_ADJUST_CSINK_DIAMETER,PILLOW_ADJUST_CSINK_DEPTH,
             d2=PILLOW_ADJUST_CSINK_PILOT).rot(x=180).move(61,y,PILLOW_ADJUST_CSINK_TOP_Z)
    a-=c.cyl(PILLOW_ADJUST_CSINK_DIAMETER,.15,61,y,PILLOW_ADJUST_CSINK_TOP_Z)
    a=a-c.cylx(2.7,9,63,y,60)
    for x in PILLOW_X:
        # Original exterior bosses remain. The old underside shallow nut
        # recess and top countersink are intentionally NOT recreated.
        a=a+c.cyl(8,2.1,x,y,49.3)
        a=a-c.hole(x,y,44,10)
        a=a-c.cyl(6.7,PILLOW_POCKET_HEIGHT,x,y,PILLOW_POCKET_BOTTOM,n=6)
        # Six-corner cavity6.7 and the5.9mm side throat fit the standard
        #6.3mm reference nut with flats parallel to the +/-Y walls.
        # The left mount loads from-X; the right mount loads from+X.
        a=a-c.box(14,5.9,PILLOW_POCKET_HEIGHT,
                      x-7 if x<61 else x+7,y,PILLOW_POCKET_BOTTOM)
    return a


def _rf_clamp(c):
    # Work in the original unshifted cradle coordinates first.
    s=c.rr(35,8,3,3,61,-60,65.2)
    for x in RF_X:
        s=s+c.cyl(9.5,RF_PAD_TOP-RF_PAD_BOTTOM,x,-60,RF_PAD_BOTTOM)
    s=s-c.cyly(24.8,12,61,-66,54.2)
    for x in RF_X:
        s=s-c.hole(x,-60,64,10)
        # Top-loading nuts, positively supported on1.2mm of clamp material.
        s=s-c.cyl(6.7,4.1,x,-60,RF_NUT_BOTTOM,n=6)
    return s.move(y=-14.3)


def build(c,PARTS):
    """Return uninclined native P13/P14/P21 shapes with original IDs."""
    result={'P13':_pillow(c,-1),'P14':_pillow(c,1),'P21':_rf_clamp(c)}
    return {pid:shape-_label_cut(c,PARTS,pid) for pid,shape in result.items()}


def records():
    """Serializable fastener declarations in the same native coordinate frame."""
    result=[]
    i=0
    for y in PILLOW_Y:
        for x in PILLOW_X:
            i+=1
            result.append({'key':f'pillow.{i}','screw_kind':'pillowM3x8',
                           'nut_kind':'pillowM3nut','part':'P13' if y<0 else 'P14',
                           'x':x,'y':y,'head_z':PILLOW_HEAD_Z,
                           'length_mm':8,'nut_bottom_z':PILLOW_NUT_BOTTOM,
                           'nut_thickness_mm':2.4,'axis':[0,0,1]})
    for i,x in enumerate(RF_X,1):
        result.append({'key':f'rfclamp.{i}','screw_kind':'rfclampM3x25',
                       'nut_kind':'motorbaseM3nut','part':'P21',
                       'x':x,'y':RF_Y,'head_z':RF_HEAD_Z,
                       'length_mm':25,'nut_bottom_z':RF_NUT_BOTTOM,
                       'nut_thickness_mm':2.4,'axis':[0,0,1]})
    return result


def screws(c):
    return [c.flat_screw(r['length_mm']).move(r['x'],r['y'],r['head_z']) for r in records()]


def nuts(c):
    return [c.hex_nut3(r['x'],r['y'],r['nut_bottom_z']) for r in records()]


def hardware(c):
    return {'coordinate_frame':'Native before incline, head lift or WX22 scene translation',
            'records':records(),'screws':screws(c),'nuts':nuts(c)}


def metadata():
    return {'companion_parts':['P13','P14','P21'],
            'P13_P14':{'native_base_Z_mm':[45.4,49.4],
                       'top_adjustment_countersink':{
                         'axes_XY_mm':[[61,-35],[61,35]],'top_Z_mm':87,
                         'mouth_diameter_mm':6.4,'pilot_diameter_mm':2.7,
                         'included_angle_deg':90,'depth_mm':1.85,
                         'bottom_Z_mm':85.15,'remaining_cylindrical_pilot_mm':2.15,
                         'minimum_inboard_top_lip_mm':.3,
                         'adjustment_hardware_moved':False},
                       'flat_outboard_face_Y_offset_mm':PILLOW_OUTER_HALF_Y_MM,
                       'back_extension_mm':PILLOW_BACK_PAD_MM,
                       'print_rotation_X_deg':{'P13':90,'P14':-90},
                       'print_envelope_mm':[25,41.6,12],
                       'guide_window_open_through_Y':True,
                       'screw':'DIN7991 M3x8 from below',
                       'head_Z_mm':PILLOW_HEAD_Z,'tip_Z_mm':51.5,
                       'modeled_nut_Z_mm':[48.9,51.3],
                       'pocket_Z_mm':[48.9,51.6],
                       'hex_circumdiameter_mm':6.7,
                       'tightened_nut_Z_mm':[48.9,51.3],
                       'pocket_floor_material_mm':3.5,
                       'nut_loading':{'x52.5':'From-X','x69.5':'From+X'},
                       'side_throat_width_mm':5.9,
                       'outer_shape_bearing_guide_adjuster_interfaces_preserved':True},
            'P21':{'screw':'DIN7991 M3x25 from below',
                    'head_Z_mm':RF_HEAD_Z,'tip_Z_mm':68.9,
                    'nut_Z_mm':[66.4,68.8],'pad_OD_mm':9.5,
                    'hex_circumdiameter_mm':6.7,
                    'pad_Z_mm':[65.2,69.2],'nut_floor_material_mm':1.2,
                    'nut_loading':'From+Z',
                    'P20_geometry_changed':False,
                    'original_motor_clearance_and_hidden_label_preserved':True},
            'assembly':['Preload P13/P14 nuts from their outerX sides before fitting the roller shafts.',
                        'Load P21 nuts from above before installing any obstructing upper housing.',
                        'Install the six reverse screws from the integrated frame underside before closing P02 or the outer housing.',
                        'Tighten gradually; physical printed fit, preload and material strength require testing.'],
            'limitations':['Nominal reference screws have smooth envelopes, not physical threads.',
                           'Pillow nuts may fall from side mouths before thread engagement; hold them during preassembly.',
                           'No physical print, torque, pullout, support-cleaning or fatigue test.']}
