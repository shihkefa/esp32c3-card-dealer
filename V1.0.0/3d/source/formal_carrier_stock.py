"""Clean P04A/P31 continuous stock before functional holes and engraving.

Native frame: P04A undersideZ42, old P31 top is the original inclined
localZ45.4 plane. The ordinary head lift and WX22 lift are assembly poses,
not included in this stock. No labelled/cut old part is unioned here.
"""
from math import cos,tan,radians

BOTTOM_Z=42.0
TOP_LOCAL_Z=45.4
SECTION_THICKNESS=.05
P04B_MOUNTS=[(x,y) for x in (-15,15) for y in (-26,26)]
HOUSING_MOUNTS=[(-59,0),(0,57),(72,49)]
FLAG_MOUNT=(-58,10)


def top_z(x,angle_deg=6):
    angle=radians(angle_deg)
    return 74.0-18.6/cos(angle)-x*tan(angle)


def _hull(c,first,second):
    return c.S((first+second).m.hull(),
               'hull(){'+first.code+second.code+'}')


def _box_loft(c,lower_width,lower_length,lower_x,lower_y,
              upper_width,upper_length,upper_x,upper_y):
    lower=c.box(lower_width,lower_length,SECTION_THICKNESS,
                lower_x,lower_y,BOTTOM_Z)
    upper=c.incline(c.box(upper_width,upper_length,SECTION_THICKNESS,
                         upper_x,upper_y,TOP_LOCAL_Z-SECTION_THICKNESS))
    return _hull(c,lower,upper)


def _rr_loft(c,width,length,radius,x,y,inner=False):
    # The inner cutter extends beyond both stock planes, avoiding a thin
    # closed skin. Its loft is subtracted before transverse rails are added.
    lo=BOTTOM_Z-.12 if inner else BOTTOM_Z
    hi=TOP_LOCAL_Z+.12 if inner else TOP_LOCAL_Z-SECTION_THICKNESS
    thickness=.24 if inner else SECTION_THICKNESS
    return _hull(c,c.rr(width,length,radius,thickness,x,y,lo),
                 c.incline(c.rr(width,length,radius,thickness,x,y,hi)))


def _under_top_plane(c,angle_deg=6):
    # XZ polygon extruded alongY, used for the tool-well reinforcement tops.
    # X+200 would put this sloping ceiling below the floor and create a
    # self-crossing polygon. +/-100 encloses the part and stays aboveZ42.
    profile=[(-100,BOTTOM_Z-.1),(100,BOTTOM_Z-.1),
             (100,top_z(100,angle_deg)),(-100,top_z(-100,angle_deg))]
    return c.poly(profile,400).rot(x=90).move(y=200)


def build(c):
    if abs(float(c.P['hopper_tilt_deg'])-6)>1e-8:
        raise ValueError('This preserved interface stock is defined for the6deg head.')

    # Original thin load-distribution rim and functional mounting pads.
    # Every old nut cutter and intermediate adapter cutter is deliberately
    # absent. The caller makes only the current functional holes afterwards.
    stock=c.cyl(124,3.4,z0=BOTTOM_Z)-c.cyl(112,3.6,z0=BOTTOM_Z-.1)

    # Continuous side rails replace two offset, stacked plate/frame rails.
    for y in (-26,26):
        stock+=_box_loft(c,139,8,10.5,y,130,8,14,y)
    for x in (-45,31):
        stock+=_box_loft(c,8,105,x,0,8,105,x,0)

    # Right-hand open motor/roller frame. Its interior is a matching open
    # loft, not a rectangular pocket whose ends would leave horizontal lips.
    outer=_rr_loft(c,38,116,6,61,-14)
    inner=_rr_loft(c,28,106,3,61,-14,inner=True)
    stock+=outer-inner
    for y in (-60,-35,35):
        stock+=_box_loft(c,38,8,61,y,38,8,61,y)

    # Local closed mounting islands preserve the two motor seating planes.
    # The RF island now reaches the common underside for its bolt access.
    # Extend only the left edge2mm to carry the complete left N20 nut roof.
    # The original seating plane and the opposite motor-frame edge stay put.
    stock+=_rr_loft(c,30,34,3,-23,-11)
    stock+=_rr_loft(c,40,29.2,4,61,-73.3)

    # These pads are functional faces; do not raise them to the tilted deck.
    stock+=c.box(12,12,3.4,72,45,BOTTOM_Z)
    for x,y in HOUSING_MOUNTS:
        stock+=c.cyl(10,3.4,x,y,BOTTOM_Z)
    stock+=c.cyl(9,3.4,*FLAG_MOUNT,BOTTOM_Z)

    # Four original P04B axes get reinforced vertical wells. The caller
    # preserves the old countersunk seats and cuts the full head/tool path.
    top_clip=_under_top_plane(c,float(c.P['hopper_tilt_deg']))
    for x,y in P04B_MOUNTS:
        stock+=c.cyl(12,30,x,y,BOTTOM_Z)&top_clip

    # The former6x8x1.2mm key is omitted. The whole carrier now sharesZ42
    # as its print bed plane; alignment/clamping uses the four M3 joints.
    return stock


def metadata():
    return {
        'coordinate_frame':'Native pre-head-lift P04A frame',
        'base_plane_Z_mm':BOTTOM_Z,
        'top_plane_equation':'z=74-18.6/cos(6deg)-x*tan(6deg)',
        'legacy_adapter_fasteners_removed':{'M3x8':4,'M3_nut':4},
        'legacy_unused_nut_pockets_removed':True,
        'N20_nut_roof_left_edge_extension_mm':2,
        'construction':'Clean section hulls/lofts; no union of old cut/labelled parts',
        'P04B_original_mount_centers_mm':P04B_MOUNTS,
        'P04B_tool_well_reinforcement_OD_mm':12,
        'P04B_key':{'removed':True,'former_center_XY_mm':[31,0],
                     'former_size_mm':[6,8,1.2],'alignment':'Four M3 mounting holes'},
        'housing_mount_centers_mm':HOUSING_MOUNTS,
        'flag_mount_center_mm':FLAG_MOUNT,
        'functional_pad_Z_mm':[42,45.4],
        'print_note':'NativeZ42 is the flat bed plane. The former underside key is removed; local cavities still require slice inspection.',
        'caller_must_cut':['P04B four screw bores/countersinks/deep access',
                           'motor/roller/coupler clearances',
                           'new load-bearing nut seats and entry paths',
                           'housing and flag holes','hidden part ID'],
    }
