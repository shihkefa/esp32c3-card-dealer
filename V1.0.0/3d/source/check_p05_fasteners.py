"""Validate closed P05B seating, assembled retention and removable P05A.

All results concern nominal undeformed CAD. Contact/support and blocked escape
paths are geometric constraints, not measured preload, friction or strength.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import build_cad as c

source_hashes = {'build_cad_py_sha256': hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),
                 'check_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
parts = {p.id: p for p in c.parts}
assert 'P05' not in parts
gear, hub = (parts[k].shape for k in ('P05A', 'P05B'))
gear_top = float(gear.m.bounding_box()[5])
hardware = {}
for name, shape, _ in c.hardware:
    hardware.setdefault(name, []).append(shape)
screw = hardware['pinionM3x8'][0]
nut = hardware['pinionM3nut'][0]
join_screws, join_nuts = hardware['pinionJoinM3x8'], hardware['pinionJoinM3nut']
pair = screw + nut
axis_y, axis_z = c.P05_CLAMP_Y, c.P05_CLAMP_Z
shaft, motor = hardware['stepper_output'][0], hardware['28BYJ-48'][0]
cover_full = parts['P02A'].shape
cover = cover_full & c.box(54, 54, 25, 54, 0, 20)
checks = []
diagnostics = []


def vol(shape):
    return float(shape.m.volume())


def hit(a, b):
    return vol(a & b)


def record(name, passed, **details):
    checks.append({'test': name, 'passed': bool(passed), **details})


def path(moving, bodies, axis, distances):
    first = None
    worst = 0.
    samples = 0
    for distance in distances:
        shifted = moving.move(**{axis: float(distance)})
        overlap = max(hit(shifted, body) for body in bodies)
        if overlap > .001 and first is None:
            first = float(distance)
        worst = max(worst, overlap)
        samples += 1
    return {'samples': samples, 'maximum_overlap_mm3': round(worst, 6),
            'first_blocked_offset_mm': None if first is None else round(first, 4)}


def rotate_x(shape, angle):
    return shape.move(y=-axis_y, z=-axis_z).rot(x=float(angle)).move(y=axis_y, z=axis_z)


# Assemble bare hub using perpendicular nut entry and an ordinary axial screw.
nut_entry = path(nut, [hub], 'y', np.linspace(20, 0, 81))
screw_entry = path(screw, [hub, nut], 'x', np.linspace(20, 0, 81))
record('Bare P05B permits clamp nut side loading from positive Y',
       nut_entry['maximum_overlap_mm3'] < .001, **nut_entry)
record('Bare P05B permits M3x8 axial loading from positive X',
       screw_entry['maximum_overlap_mm3'] < .001, **screw_entry)

join_entries = []
for (x, y), n in zip(c.P05_JOIN_MOUNTS, join_nuts):
    direction = -1 if x < 54 else 1
    result = path(n, [hub], 'x', np.linspace(direction * 16, 0, 65))
    join_entries.append({'position_mm': [x, y], **result})
record('Both joining nuts side-load normally with P05A removed',
       all(x['maximum_overlap_mm3'] < .001 for x in join_entries), instances=join_entries)

bare = hub + pair + c.U(join_nuts)
shaft_max = max(max(hit(bare.move(z=float(dz)), body) for body in (shaft, motor, cover))
                for dz in np.linspace(20, 0, 81))
record('Bare hub and loaded nuts lower onto D shaft before gear installation',
       shaft_max < .001, samples=81, maximum_overlap_mm3=round(shaft_max, 6),
       scope='Undeformed reference fit; actual D-clamp deformation and holding torque require testing.')
gear_entry = path(gear, [hub, pair] + join_nuts, 'z', np.linspace(20, 0, 81))
record('P05A descends over clamped nominal hub and both joining nuts',
       gear_entry['maximum_overlap_mm3'] < .001, **gear_entry,
       warning='The hub is undeformed in this check. Print fit after physical clamp tightening must be verified.')

coverage = []
fill = c.cyl(3, 2.4).rot(y=90).move(c.P05_NUT_X, axis_y, axis_z)
coverage.append({'name': 'clamp nut', 'ratio': hit(screw, fill) / vol(fill)})
for (x, y), s in zip(c.P05_JOIN_MOUNTS, join_screws):
    fill = c.cyl(3, 2.4, x, y, 34.1)
    coverage.append({'name': 'join nut', 'position_mm': [x, y], 'ratio': hit(s, fill) / vol(fill)})
record('All three M3 nuts have full 2.4mm nominal shank coverage',
       all(x['ratio'] > .995 for x in coverage), instances=coverage)

# Ordinary straight driver: socket bit, slim shank, then handle outside cover.
driver = (c.cylx(2.25, 2.1, c.P05_HEAD_X - 1, axis_y, axis_z, n=6)
          + c.cylx(3, 28, c.P05_HEAD_X + .2, axis_y, axis_z)
          + c.cylx(10, 15, 86, axis_y, axis_z))
driver_entry = path(driver, [hub, screw, nut, cover_full, shaft, motor], 'x', np.linspace(22, 0, 89))
driver_turn_max = 0.
for angle in range(0, 360, 5):
    turning = rotate_x(driver, angle)
    turning_screw = rotate_x(screw, angle)
    driver_turn_max = max(driver_turn_max,
                          *(hit(turning, body) for body in (hub, turning_screw, nut, cover_full, motor, shaft)))
diagnostics.append({'method': 'Straight axial screwdriver after P02A installation',
                    'supported': False, 'entry': driver_entry,
                    'maximum_turn_overlap_mm3': round(driver_turn_max, 6),
                    'reason': 'The fixed cover outer rim obstructs a straight axial approach. Use the tested L-key procedure; do not postpone cover installation around the already clamped flange.'})


def make_l_key(short_centre_mm):
    """Conservative 3mm steel envelope with a 2mm centreline bend radius."""
    tip = c.P05_HEAD_X - 1
    pivot = tip + short_centre_mm
    radius, bend_radius = 1.5, 2.
    pieces = [c.cylx(2.30, 2.1, tip, axis_y, axis_z, n=6),
              c.cylx(3, pivot - bend_radius - (c.P05_HEAD_X + .2),
                      c.P05_HEAD_X + .2, axis_y, axis_z),
              c.cyl(3, 70 - bend_radius, pivot, axis_y, axis_z + bend_radius)]
    points = []
    for theta in np.linspace(-np.pi / 2, 0, 7):
        points.append(np.array([pivot - bend_radius + bend_radius * math.cos(theta),
                                axis_y, axis_z + bend_radius + bend_radius * math.sin(theta)]))
    sphere = c.S(c.mf.Manifold.sphere(radius, 16), '')
    pieces += [sphere.move(*point) for point in points]
    for first, second in zip(points, points[1:]):
        delta = second - first
        length = float(np.linalg.norm(delta))
        angle = math.degrees(math.atan2(float(delta[0]), float(delta[2])))
        pieces.append(c.cyl(3, length, n=16).rot(y=angle).move(*first))
    return c.U(pieces)


l_key_families = []
for short_length in (14., 16., 20.):
    l_key = make_l_key(short_length)
    phases = []

    def l_phase(name, poses):
        maximum, count = 0., 0
        for angle, dx, dz, screw_angle in poses:
            moving = rotate_x(l_key, angle).move(x=dx, z=dz)
            moving_screw = rotate_x(screw, screw_angle)
            maximum = max(maximum, *(hit(moving, body) for body in
                                      (hub, nut, moving_screw, cover_full, motor, shaft)))
            count += 1
        phases.append({'phase': name, 'poses': count,
                        'maximum_overlap_mm3': round(maximum, 6), 'passed': maximum < .001})

    l_phase('Descend from above while axially retracted',
            ((0., 3.2, float(dz), 0.) for dz in np.linspace(22, 0, 61)))
    l_phase('Set starting angle 60deg outside screw socket',
            ((float(angle), 3.2, 0., 0.) for angle in np.linspace(0, 60, 31)))
    l_phase('Engage at 60deg using hex symmetry',
            ((60., float(dx), 0., 0.) for dx in np.linspace(3.2, 0, 33)))
    l_phase('Tightening stroke 60deg to 0deg, screw co-rotates',
            ((float(angle), 0., 0., float(angle) - 60.) for angle in np.linspace(60, 0, 61)))
    l_phase('Withdraw axially while screw stays at -60deg',
            ((0., float(dx), 0., -60.) for dx in np.linspace(0, 1.1, 23)))
    l_phase('Reset to 60deg after disengagement',
            ((float(angle), 1.1, 0., -60.) for angle in np.linspace(0, 60, 31)))
    l_phase('Re-engage for the next tightening stroke',
            ((60., float(dx), 0., -60.) for dx in np.linspace(1.1, 0, 23)))
    l_phase('Opposite-side -60deg sweep with screw co-rotating',
            ((float(angle), float(dx), 0., float(angle))
             for angle in np.linspace(-60, 0, 13) for dx in (0., 1.1)))
    l_key_families.append({'short_arm_tip_to_stem_centre_mm': short_length,
                           'supported': all(phase['passed'] for phase in phases),
                           'poses': sum(phase['poses'] for phase in phases), 'phases': phases})
supported_lengths = [f['short_arm_tip_to_stem_centre_mm'] for f in l_key_families if f['supported']]
record('Common-size 2mm L-key references enter, tighten and reindex with cover installed',
       bool(supported_lengths), tested_families=l_key_families,
       supported_tip_to_stem_centres_mm=supported_lengths,
       shaft_envelope_diameter_mm=3, centreline_bend_radius_mm=2,
       long_arm_reference_mm=70, initial_retraction_before_descent_mm=3.2,
       axial_disengagement_for_reindex_mm=1.1,
       permitted_stroke='60deg toward 0deg, long arm remains above cover; reset only while disengaged.',
       assembly_order='Install P02A and motor first, fit P05B and clamp with L key, then fit P05A and finally P04.',
       warning='Only the stated tool envelopes are validated. Catalog outside length differs from tip-to-stem centre distance; real bend radius, longer-arm obstruction and commercial dimensions require trial fitting. No screw preload/torque result.')

join_driver_checks = []
for (x, y), target_screw in zip(c.P05_JOIN_MOUNTS, join_screws):
    tool = c.cyl(2.25, 16, x, y, gear_top - 1, n=6) + c.cyl(3, 25, x, y, gear_top + .25)
    overlap = max(hit(tool, body) for body in [gear, hub, pair, target_screw] + join_nuts + join_screws)
    join_driver_checks.append({'position_mm': [x, y], 'maximum_overlap_mm3': round(overlap, 6)})
record('Joining screws have ordinary vertical tool access before P04',
       all(x['maximum_overlap_mm3'] < .001 for x in join_driver_checks), instances=join_driver_checks)

# Inspect actual material immediately outside and inside the 45deg seating
# surface. Four axial stations and 72 circumferential probes each; no averaging
# can hide a missing upper half. The original head and seat share r=X-54.6.
cone_samples = []
for x in (56.55, 56.85, 57.15, 57.45):
    radius = x - 54.6
    for deg in range(0, 360, 5):
        theta = math.radians(deg)
        outward = c.box(.025, .025, .025, x,
                         axis_y + (radius + .04) * math.cos(theta),
                         axis_z + (radius + .04) * math.sin(theta) - .0125)
        inward = c.box(.025, .025, .025, x,
                        axis_y + (radius - .04) * math.cos(theta),
                        axis_z + (radius - .04) * math.sin(theta) - .0125)
        support = hit(outward, hub) / vol(outward)
        head_fill = hit(inward, screw) / vol(inward)
        inward_hub = hit(inward, hub) / vol(inward)
        cone_samples.append({'x_mm': x, 'angle_deg': deg,
                             'support_ratio': round(support, 6),
                             'head_ratio': round(head_fill, 6),
                             'inward_hub_ratio': round(inward_hub, 6)})
record('Closed cone supports all 360deg at four axial stations',
       all(x['support_ratio'] > .995 and x['head_ratio'] > .995 and x['inward_hub_ratio'] < .005
           for x in cone_samples), axial_stations=4, angles_per_station=72,
       probe_side_mm=.025, radial_offset_mm=.04, samples=cone_samples,
       scope='Complete geometric bearing-seat material adjacent to nominal cone; no contact pressure/preload result.')

guide_samples = []
for x in (53.0, 55.0, 55.5):
    for deg in range(0, 360, 5):
        theta = math.radians(deg)
        probe = c.box(.025, .025, .025, x,
                       axis_y + 1.75 * math.cos(theta),
                       axis_z + 1.75 * math.sin(theta) - .0125)
        ratio = hit(probe, hub) / vol(probe)
        guide_samples.append({'x_mm': x, 'angle_deg': deg, 'solid_ratio': round(ratio, 6)})
record('Closed 3.4mm guide rings remain around the clamp screw',
       all(x['solid_ratio'] > .995 for x in guide_samples), rings=3, angles_per_ring=72,
       diameter_clearance_mm=.4, nominal_radial_play_mm=.2, samples=guide_samples,
       warning='A closed guide still has 0.2mm nominal radial clearance; this is not a zero-play claim.')

# Prove the removable gear is the positive barrier at each original side exit.
retention = []
for name, moving, axis, distances in [
        ('clamp screw +X side exit', screw, 'x', np.linspace(0, 22, 111)),
        ('clamp nut +Y side exit', nut, 'y', np.linspace(0, 20, 101))]:
    assembled_path = path(moving, [gear], axis, distances)
    bare_path = path(moving, [hub], axis, distances)
    retention.append({'name': name, 'assembled_gear_barrier': assembled_path,
                      'gear_removed_path': bare_path,
                      'passed': assembled_path['maximum_overlap_mm3'] > .05 and bare_path['maximum_overlap_mm3'] < .001})
for (x, y), n in zip(c.P05_JOIN_MOUNTS, join_nuts):
    direction = -1 if x < 54 else 1
    distances = np.linspace(0, direction * 16, 81)
    assembled_path = path(n, [gear], 'x', distances)
    bare_path = path(n, [hub], 'x', distances)
    retention.append({'name': 'join nut side exit', 'position_mm': [x, y],
                      'assembled_gear_barrier': assembled_path,
                      'gear_removed_path': bare_path,
                      'passed': assembled_path['maximum_overlap_mm3'] > .05 and bare_path['maximum_overlap_mm3'] < .001})
record('Gear skirt positively blocks side exits; removing gear restores access',
       all(x['passed'] for x in retention), exits=retention)

pair_escape = []
for axis in ('x', 'y', 'z'):
    for sign in (-1, 1):
        result = path(pair, [gear, hub], axis, np.linspace(0, sign * 8, 81))
        pair_escape.append({'axis': axis, 'sign': sign, **result,
                            'passed': result['maximum_overlap_mm3'] > .05})
record('Thread-engaged clamp screw/nut pair cannot translate out axially sideways or vertically',
       all(x['passed'] for x in pair_escape), paths=pair_escape,
       scope='Rigid pair represents maintained thread engagement; six straight escape paths, not exhaustive arbitrary configuration-space search.')

tilts = []
for axis in ('y', 'z'):
    for angle in (-3, -2, -1, -.5, .5, 1, 2, 3):
        tilted = pair.move(x=-51, y=-axis_y, z=-axis_z).rot(**{axis: angle}).move(x=51, y=axis_y, z=axis_z)
        overlap = max(hit(tilted, hub), hit(tilted, gear))
        tilts.append({'axis': axis, 'angle_deg': angle,
                      'overlap_mm3': round(overlap, 6), 'blocked': overlap > .001})
record('Seated bolt pitch and yaw meet solid support rather than an open U slot',
       all(x['blocked'] for x in tilts if abs(x['angle_deg']) >= 1), samples=tilts,
       tested_pivot_mm=[51, axis_y, axis_z],
       warning='Tests start from the nominal seated cone; does not eliminate guide clearances or simulate elastic deflection and clamp force.')

slit_probe = c.box(.5, 14.1, 1, 54, 8.55, 36)
slit_overlap = hit(slit_probe, hub)
record('D-clamp slit remains open through positive-Y flange perimeter',
       slit_overlap < .001, probe_y_interval_mm=[1.5, 15.6],
       overlap_mm3=round(slit_overlap, 6), slit_width_mm=.6,
       warning='Closing deformation and whether gear attachment changes shaft grip require physical testing.')

turning_unit = gear + hub + pair + c.U(join_screws + join_nuts)
turn_max = 0.
for angle in range(360):
    moving = turning_unit.move(x=-54).rot(z=angle).move(x=54)
    turn_max = max(turn_max, hit(moving, cover), hit(moving, motor))
record('Complete undeformed P05 unit clears cover and motor throughout rotation',
       turn_max < .001, poses=360, angular_step_deg=1,
       maximum_overlap_mm3=round(turn_max, 6),
       nominal_lower_hub_radial_clearance_mm=.2, nominal_skirt_to_cover_z_clearance_mm=.3,
       warning='Discrete undeformed geometry; not a continuous sweep or measured manufactured clearance.')

old_teeth = c.gear(30, 1.2, 6, 34).rot(z=6).move(54, 0)
outside_root = c.box(80, 80, 12, 54, 0, 32) - c.cyl(33, 14, 54, 0, 31)
old_height = c.box(80, 80, 6, 54, 0, 34)
actual_old_band = gear & old_height
removed = hit(old_teeth - actual_old_band, outside_root)
added = hit(actual_old_band - old_teeth, outside_root)
extra_difference = 0.
if gear_top > 40.00001:
    extra_teeth = c.gear(30, 1.2, gear_top - 40, 40).rot(z=6).move(54, 0)
    new_band = gear & c.box(80, 80, gear_top - 40, 54, 0, 40)
    extra_difference = hit((new_band - extra_teeth) + (extra_teeth - new_band), outside_root)
record('Original 30T tooth profile and 2:1 transmission remain unchanged',
       max(removed, added, extra_difference) < .0001,
       original_height_band_mm=[34, 40], actual_height_band_mm=[34, gear_top],
       original_removed_mm3=round(removed, 8), original_added_mm3=round(added, 8),
       added_height_profile_difference_mm3=round(extra_difference, 8),
       tooth_count=30, module_mm=1.2, axis_mm=[54, 0], gear_ratio='30:60 = 1:2')

# Side-printing change: compare to the actual pre-cut hub retained by the CAD
# builder. Exterior cuts must not alter either the D fit or screw bearing cage.
added_backing = c.LABEL_BASE_SHAPES['P05A'] - c.P05A_ROUND_CAVITY_BASE
expected_backing = (c.cyl(30.8,4.5,54,0,33.3)
                    & c.box(80,40,4.5,54,c.P05A_CAVITY_FLAT_Y-20,33.3))
backing_removed = vol(c.P05A_ROUND_CAVITY_BASE - c.LABEL_BASE_SHAPES['P05A'])
backing_difference = vol((added_backing-expected_backing)+(expected_backing-added_backing))
record('P05A change only fills the intended negative-Y crescent inside the old cavity',
       backing_removed < .001 and backing_difference < .001 and vol(added_backing) > 1,
       removed_from_original_gear_mm3=round(backing_removed,8),
       added_material_mm3=round(vol(added_backing),6),
       expected_region_difference_mm3=round(backing_difference,8),
       material_z_interval_mm=[33.3,37.8], radial_limit_mm=15.4,
       scope='Unengraved CAD comparison; outer teeth, skirt, fixing bores and seats are unchanged.')

flat_samples=[]
for xx in (50,54,58):
    for zz in (33.5,35.4,37.5):
        a_wall=c.box(.04,.04,.04,xx,c.P05A_CAVITY_FLAT_Y-.04,zz)
        b_wall=c.box(.04,.04,.04,xx,c.P05B_FLAT_Y+.04,zz)
        gap=c.box(.04,.16,.04,xx,(c.P05A_CAVITY_FLAT_Y+c.P05B_FLAT_Y)/2,zz)
        flat_samples.append({'x_mm':xx,'z_mm':zz,
            'A_wall_solid_ratio':round(hit(a_wall,gear)/vol(a_wall),6),
            'B_wall_solid_ratio':round(hit(b_wall,hub)/vol(b_wall),6),
            'gap_overlap_mm3':round(max(hit(gap,gear),hit(gap,hub)),8)})
record('P05A D-cavity flat follows the unchanged P05B flat with 0.2mm nominal clearance',
       abs(c.P05B_FLAT_Y-c.P05A_CAVITY_FLAT_Y-.2)<1e-8
       and all(s['A_wall_solid_ratio']>.995 and s['B_wall_solid_ratio']>.995
               and s['gap_overlap_mm3']<.000001 for s in flat_samples),
       A_inner_flat_y_mm=c.P05A_CAVITY_FLAT_Y,B_outer_flat_y_mm=c.P05B_FLAT_Y,
       nominal_gap_mm=round(c.P05B_FLAT_Y-c.P05A_CAVITY_FLAT_Y,6),samples=flat_samples,
       warning='Nominal clearance, not an interference fit. Printed first-layer expansion and clamp deformation still need fitting.')

base_hub = c.P05B_PRINT_BASE
flat_removed = c.box(70, 20, 25, 54, -20.5, 20)
lower_wedge = c.poly([(-20, 30.5), (-3.3, 30.5), (-5.98, 33.18), (-20, 33.18)], 50)
lower_wedge = lower_wedge.basis((0, 1, 0), (0, 0, 1), (1, 0, 0), (29, 0, 0))
upper_wedge = c.poly([(-20, 37.82), (-5.98, 37.82), (-3.8, 40), (-20, 40)], 50)
upper_wedge = upper_wedge.basis((0, 1, 0), (0, 0, 1), (1, 0, 0), (29, 0, 0))
cut_residuals = {'flat_outside_mm3': hit(flat_removed, hub),
                 'lower_chamfer_outside_mm3': hit(lower_wedge, hub),
                 'upper_chamfer_outside_mm3': hit(upper_wedge, hub),
                 'material_added_to_base_mm3': vol(hub - base_hub)}
record('New side flat and both 45deg external chamfers are present',
       max(cut_residuals.values()) < .001,
       residuals_mm3={k: round(v, 8) for k, v in cut_residuals.items()},
       flat_source_y_mm=-10.5, lower_chamfer_z_band_mm=[30.5, 33.18],
       upper_chamfer_z_band_mm=[37.82, 40], junction_ledge_mm=.02,
       scope='Only exterior material removal plus recessed identifier; tiny 0.02mm junction ledges are intentional.')

d_fit_crop = c.box(5.7, 3.8, 9.5, 54, 0, 30.5)
seat_crop = c.box(5, 9, 9, 56.5, 7.5, 30.8)
d_change = hit((base_hub - hub) + (hub - base_hub), d_fit_crop)
seat_change = hit((base_hub - hub) + (hub - base_hub), seat_crop)
wall_samples = []
for height in (30.6, 31.5, 33.0, 35.4, 37.8, 39.9):
    for dx, yy in [(-1.8, -1.75), (0, -1.75), (1.8, -1.75),
                   (-1.8, 1.75), (1.8, 1.75), (-2.7, 0), (2.7, 0)]:
        probe = c.box(.05, .05, .05, 54 + dx, yy, height)
        ratio = hit(probe, hub) / vol(probe)
        wall_samples.append({'source_z_mm': height, 'source_xy_mm': [54 + dx, yy],
                             'solid_ratio': round(ratio, 6)})
local_walls = []
for name, probe, thickness in [
        ('lower axial-end back wall', c.box(1.6, 1.5, .05, 54, -2.475, 30.55), 1.65),
        ('upper axial-end back wall', c.box(1.6, 2, .05, 54, -2.75, 39.9), 2.15)]:
    ratio = hit(probe, hub) / vol(probe)
    local_walls.append({'location': name, 'local_nominal_wall_mm': thickness,
                        'sampled_solid_ratio': round(ratio, 6)})
chamfer_face_support = []
for label, zs, boundary in [('lower', (30.6, 31.5, 32.5, 33.1), lambda zz: 27.2 - zz),
                             ('upper', (37.9, 38.5, 39.3, 39.9), lambda zz: zz - 43.8)]:
    for height in zs:
        probe = c.box(.05, .05, .05, 54, boundary(height) + .08, height - .025)
        ratio = hit(probe, hub) / vol(probe)
        chamfer_face_support.append({'chamfer': label, 'source_z_mm': height,
                                      'sampled_solid_ratio': round(ratio, 6)})
d_bridge_span = 2 * math.sqrt(2.6 ** 2 - 1.65 ** 2)
record('Exterior printing cuts preserve D-bore fit and closed bearing support',
       max(d_change, seat_change) < .001
       and all(x['solid_ratio'] > .995 for x in wall_samples)
       and all(x['sampled_solid_ratio'] > .995 for x in local_walls + chamfer_face_support),
       d_fit_region_changed_mm3=round(d_change, 8), bearing_region_changed_mm3=round(seat_change, 8),
       d_wall_samples=wall_samples, axial_end_wall_samples=local_walls,
       chamfer_face_samples=chamfer_face_support,
       horizontal_D_flat_roof_span_mm=round(d_bridge_span, 3),
       warning='1.65/2.15mm values are local axial-end back walls, not whole-part minimum thickness. Horizontal D/round holes still need slicer bridging/fit checks. The full cone/guide tests above are independently re-executed.')

bed = []
for pid, minimum, expected in [('P05A', 450, -gear_top), ('P05B', 80, -10.5)]:
    p = parts[pid]
    printed = p.shape.rot(*p.print_rot)
    bounds = np.asarray(printed.m.bounding_box())
    slab = c.box(float(bounds[3] - bounds[0] + 2), float(bounds[4] - bounds[1] + 2), .02,
                 float((bounds[0] + bounds[3]) / 2), float((bounds[1] + bounds[4]) / 2), float(bounds[2]))
    area = hit(printed, slab) / .02
    bed.append({'part': pid, 'contact_area_mm2': round(area, 2),
                'passed': bool(area > minimum and abs(bounds[2] - expected) < 1e-5)})
record('Both P05 parts have real planar print-bed contact',
       all(x['passed'] for x in bed), sampled_layer_mm=.02, parts=bed,
       recommended_P05B_brim_mm=[3, 5], P05B_nominal_flat_face_mm=[21.98, 4.6],
       warning='P05B lies on the new side flat, not its original bottom. Hole roofs need local bridging/support checks; no support-free claim.')

report = {'revision': c.P['revision'], 'design': 'Independent closed D-clamp hub plus removable positively retaining gear',
          'all_passed': all(x['passed'] for x in checks), 'source_hashes': source_hashes,
          'scope': 'Nominal CAD contact, material support and sampled insertion/escape constraints, not physical qualification.',
          'checks': checks, 'diagnostics': diagnostics,
          'limitations': ['No measured preload, clamping force, friction, thread lead, durability or vibration test.',
                          'Hub deformation after tightening and fit after gear attachment are not modeled.',
                          'Blocked sampled straight/tilt paths do not prove all possible arbitrary escape configurations.',
                          'Maintain screw/nut thread engagement; completely disassembling fasteners changes their constraints.',
                          'Print tolerance, cone seating, commercial tool dimensions and local support need trial fitting.']}
(c.OUT / 'p05_fastener_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({'all_passed': report['all_passed'], 'source_hashes': source_hashes,
                  'checks': [{k: v for k, v in x.items() if k not in {'samples'}} for x in checks]}, ensure_ascii=True, indent=2))
if not report['all_passed']:
    raise SystemExit(1)
