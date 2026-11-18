"""P06 revision for the user's WX22 slip ring; dimensions are assembly mm.

The outer collar engages P04B's existing radial hole with a seated M3x8
pin screw.  A separate split collet grips the rotor's 7.8mm neck.  A rear
bridge joins these features through P04B's negative-Y bottom relief.
Clamp deformation, printed fit and the slip-ring casing strength require
physical verification.  Neither wire bundle transfers mechanical torque.
"""
from math import sqrt

BOTTOM_Z = 11.0
TOP_Z = 19.0
OUTER_OD = 33.0
OUTER_ID = 25.2
INNER_MAX_OD = 22.1
NECK_BORE = 8.0
COLLET_OD = 12.0
SLIT = 1.2
INNER_RAISE_MM = 2.1
INNER_BOTTOM_Z = BOTTOM_Z + INNER_RAISE_MM
INNER_TOP_Z = TOP_Z + INNER_RAISE_MM
BRIDGE_BOTTOM_Z = INNER_BOTTOM_Z
BRIDGE_TOP_Z = 12.8 + INNER_RAISE_MM
PIN_Z = 15.5
PIN_HEAD_X = -19.0
PIN_NUT_X = -16.35
CLAMP_Y = 6.3
CLAMP_Z = 14.9 + INNER_RAISE_MM
# The asymmetry keeps the nut and its pocket outside the neck passage.
# The screw loads from +X, away from the outer pin's -X captive nut.
CLAMP_HEAD_X = 2.9
CLAMP_NUT_X = -4.95
LABEL = {'text': 'P06', 'origin_mm': [17, 0, 15.5],
         'normal': [1, 0, 0], 'height_mm': 2.4, 'depth_mm': .25,
         'location': 'Outer positive-X hidden platform; not a bearing/shaft contact face'}


def _side_nut(c, x, y, z):
    # No initial Z rotation: the flats face +/-Y.  This also reduces the
    # tangential envelope beside the 7.8mm rotor neck.
    return c.hex_nut3(0, 0, 0).rot(y=90).move(x, y, z)


def screws(c):
    """Outer positive-drive pin first, then the preassembled neck clamp."""
    return [c.flat_screw(8).rot(y=90).move(PIN_HEAD_X, 0, PIN_Z),
            c.flat_screw(8).rot(y=-90).move(CLAMP_HEAD_X, CLAMP_Y, CLAMP_Z)]


def nuts(c):
    return [_side_nut(c, PIN_NUT_X, 0, PIN_Z),
            _side_nut(c, CLAMP_NUT_X, CLAMP_Y, CLAMP_Z)]


def build(c, engrave=True):
    # The outer annulus retains its Z11 bed plane. The inner collet and
    # bridge are raised2.1mm to retain the fixed WX22 neck/shoulder datum.
    assert abs((22.2-float(c.P['lower_stack_assembly_lift_mm']))-INNER_RAISE_MM)<1e-8
    outer = c.cyl(OUTER_OD, TOP_Z-BOTTOM_Z, z0=BOTTOM_Z)
    outer += c.box(7.5, 8, TOP_Z-BOTTOM_Z, -16, 0, BOTTOM_Z)
    outer += c.box(2, 8, 4, 16, 0, 13.5)
    outer -= c.cyl(OUTER_ID, 8.4, z0=10.8)

    # Full countersunk seat and closed guide for the original-axis pin.
    # The 0.2mm axial offset makes the reference 6mm head meet the 6.4mm
    # seat rather than floating in a cylindrical counterbore.
    outer -= c.cylx(3.4, 13, -22, 0, PIN_Z)
    outer -= c.cyl(6.4, 1.5, d2=3.4).rot(y=90).move(-19.2, 0, PIN_Z)
    outer -= c.cylx(6.4, 2.8, -22, 0, PIN_Z)
    outer -= c.cyl(6.7, 2.7, n=6).rot(y=90).move(-16.5, 0, PIN_Z)
    outer -= c.box(2.7, 5.9, 5, -15.15, 0, PIN_Z)

    # This is also the installation path for the complete 6mm screw head,
    # not merely an Allen-key aperture.  P04B subsequently covers the
    # radial access from the outer ring to the inner clamp.
    # Extend to the centerline, since the curved inner annulus reaches
    # inward of X10 near the upper-Y side of a6mm screw head.
    outer -= c.cylx(6.4, 25, 0, CLAMP_Y, CLAMP_Z)

    inner = c.cyl(COLLET_OD, INNER_TOP_Z-INNER_BOTTOM_Z, z0=INNER_BOTTOM_Z)
    inner += c.box(12.2, 5.5, INNER_TOP_Z-INNER_BOTTOM_Z, 0, 6.75, INNER_BOTTOM_Z)
    inner &= c.cyl(INNER_MAX_OD, 8.4, z0=INNER_BOTTOM_Z-.2)
    inner -= c.cyl(NECK_BORE, 8.6, z0=INNER_BOTTOM_Z-.3)
    inner -= c.box(SLIT, 10, 8.4, 0, 8.9, INNER_BOTTOM_Z-.2)

    # Inner M3x8: head at +2.9, tip at -5.1.  Captive nut occupies
    # -4.95..-2.55.  The left pocket retains a1.8mm wall to the slit.
    inner -= c.cylx(3.4, 15, -7.5, CLAMP_Y, CLAMP_Z)
    inner -= c.cyl(6.4, 1.5, d2=3.4).rot(y=-90).move(3.1, CLAMP_Y, CLAMP_Z)
    inner -= c.cylx(6.4, 9, 3.1, CLAMP_Y, CLAMP_Z)
    inner -= c.cyl(6.7, 2.7, n=6).rot(y=90).move(-5.1, CLAMP_Y, CLAMP_Z)
    inner -= c.box(2.7, 5.9, 5.5, -3.75, CLAMP_Y, CLAMP_Z)

    # Only the rear, negative-Y bridge links the collet to the collar;
    # the front split can close without a complete floor disk resisting it.
    bridge = c.box(8, 11.5, BRIDGE_TOP_Z-BRIDGE_BOTTOM_Z, 0, -8.75, BRIDGE_BOTTOM_Z)
    result = outer + inner + bridge
    result -= c.cyl(NECK_BORE, 8.6, z0=INNER_BOTTOM_Z-.3)

    # Reuse the project's geometric pixel font without touching c.parts.
    label = c.U(c.box(cell+.03, cell+.03, .37, s, t, -.25)
                for s, t, cell in c.letter_pixels('P06', 2.4))
    label = label.basis((0, 1, 0), (0, 0, 1), (1, 0, 0), (17, 0, 15.5))
    return result-label if engrave else result


def metadata():
    return {
        'status': 'Geometric prototype; printed fit, elastic gripping and strength unverified',
        'single_piece': True,
        'print_plane_Z_mm': BOTTOM_Z,
        'inner_raised_above_print_bed_mm':INNER_RAISE_MM,
        'inner_and_bridge_local_support_required':True,
        'outer_stop': {'OD_mm': OUTER_OD, 'ID_mm': OUTER_ID,
                       'bottom_Z_mm': BOTTOM_Z, 'bearing_stop_Z_mm': TOP_Z},
        'rear_bridge': {'X_width_mm': 8, 'Y_range_mm': [-14.5, -3],
                        'Z_range_mm': [BRIDGE_BOTTOM_Z, BRIDGE_TOP_Z],
                        'P04B_rear_slot_top_Z_mm':15.4,
                        'clearance_to_P04B_rear_slot_ceiling_mm': .5,
                        'clearance_to_rotor_shoulder_top_mm': .5},
        'inner_collet': {'bore_mm': NECK_BORE, 'OD_mm': COLLET_OD,
                         'maximum_printed_envelope_OD_mm': INNER_MAX_OD,
                         'Z_range_mm': [INNER_BOTTOM_Z, INNER_TOP_Z],
                         'rotor_neck_reference_mm': {'OD': 7.8, 'Z': [12.6, 21.4]},
                         'nominal_radial_clearance_before_clamping_mm': .1,
                         'slit_width_mm': SLIT, 'slit_direction': '+Y',
                         'required_ideal_circumference_takeup_mm': .2*3.141592653589793,
                         'actual_clamp_deformation_or_force_validated': False},
        'outer_pin': {'screw': 'DIN7991 M3x8', 'head_X_mm': PIN_HEAD_X,
                      'tip_X_mm': -11, 'axis_YZ_mm': [0, PIN_Z],
                      'nut_start_X_mm': PIN_NUT_X, 'nut_length_mm': 2.4,
                      'unchanged_P04B_wall_X_range_mm': [-12.4, -11.25],
                      'purpose': 'Positive-drive pin through existing P04B radial hole; not a rotor set screw'},
        'inner_clamp': {'screw': 'DIN7991 M3x8', 'head_X_mm': CLAMP_HEAD_X,
                        'tip_X_mm': -5.1, 'axis_YZ_mm': [CLAMP_Y, CLAMP_Z],
                        'nut_X_range_mm': [CLAMP_NUT_X, CLAMP_NUT_X+2.4],
                        'nut_pocket_X_range_mm': [-5.1, -2.4],
                        'nut_pocket_to_slit_wall_mm': 1.8,
                        'nut_hex_flats_face': '+/-Y',
                        'head_loading_direction': 'From +X towards -X before inserting P04B',
                        'outer_installation_aperture_mm': 6.4,
                        'outer_aperture_roof_mm':0,
                        'outer_aperture_opens_through_top':True,
                        'opening_above_outer_top_mm':CLAMP_Z+3.2-TOP_Z,
                        'outer_aperture_bottom_wall_mm': CLAMP_Z-3.2-BOTTOM_Z,
                        'nut_loading_direction': 'From +Z before installing its screw',
                        'nuts_retained_against_gravity_before_thread_engagement': False},
        'hardware': {'DIN7991_M3x8': 2, 'M3_nut_5_5AF_x_2_4': 2,
                     'additional_vs_original_P06': {'M3x8': 1, 'M3_nut': 1}},
        'label': LABEL,
        'assembly_sequence': [
            'Temporarily hold the three flange washers and nuts on the stator flange before installing P06; keep temporary tape clear of rotating surfaces.',
            'Preload both P06 nuts from above before installing P04B or its bearing; engage both screws.',
            'Keep the outer pin screw retracted about2mm so its tip stays outside the P04B insertion path.',
            'Slide the raised inner collet over the fixed rotor neck; the flange remains at worldZ25.2..27.7.',
            'Tighten the inner collet gently using a2mm Allen key through the +X aperture; printed grip requires testing.',
            'Align the negative-Y bottom relief of P04B with the rear bridge before lowering the tube/bearing; do not force it around to find the slot.',
            'Align the existing P04B radial hole and install the outer seated M3x8 pin and nut.',
            'Complete this upper/slip-ring subassembly outside P01, then lower it into P01 and fasten the stationary flange from below.',
        ],
        'limitations': [
            'P04B blocks access to the inner collet screw after assembly; remove it to adjust the clamp.',
            'The rotor lead bundle needs a separate free central path and strain relief; the8.8mm neck is not the total wire envelope.',
            'No clamping load, elastic closure, casing strength, fatigue or physical support-removal test is represented by this CAD.',
            'The inner collet and rear bridge begin2.1mm above the outer-ring print bed; inspect local support in the slicer.',
        ],
    }
