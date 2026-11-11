"""Check nominal split P04 assembly and P06 captive-nut access.

This is geometric validation, not print, strength or tightening validation.
The P06 adjustment test deliberately excludes the rigid slip-ring rotor:
travel after nominal contact is NOT an allowed rigid-body interference.
"""
import json
import hashlib
from pathlib import Path
import numpy as np
import build_cad as c

parts = {p.id: p for p in c.parts}
assert 'P04' not in parts and {'P04A', 'P04B', 'P06'} <= parts.keys()
native_a = parts['P04A'].shape
a = c.assembly_pose('P04A', native_a)
b, collar = (parts[k].shape for k in ('P04B', 'P06'))
lift = c.UPPER_LIFT
mate_z = c.P04_MATE_Z
nut_bottom = 38.2 + lift
deck_head_z = 45.4 + lift
hardware = {}
for name, shape, _ in c.hardware:
    hardware.setdefault(name, []).append(shape)
checks = []


def volume(shape):
    return float(shape.m.volume())


def hit(first, second):
    return volume(first & second)


def record(name, passed, **details):
    checks.append({'test': name, 'passed': bool(passed), **details})


bed = []
for pid, minimum in [('P04A', 3500), ('P04B', 1500), ('P06', 250)]:
    p = parts[pid]
    printed = p.shape.rot(*p.print_rot)
    bounds = np.asarray(printed.m.bounding_box())
    cx, cy = (bounds[:2] + bounds[3:5]) / 2
    slab = c.box(bounds[3] - bounds[0] + 2, bounds[4] - bounds[1] + 2,
                 .02, float(cx), float(cy), float(bounds[2]))
    area = hit(printed, slab) / .02
    expected_plane = {'P04A': -45.4, 'P04B': -mate_z, 'P06': -19.}[pid]
    good = area >= minimum and abs(bounds[2] - expected_plane) < 1e-5
    bed.append({'part': pid, 'flat_contact_mm2': round(area, 2),
                'checked_layer_mm': .02, 'minimum_mm2': minimum,
                'bed_z_before_translation_mm': round(float(bounds[2]), 4),
                'passed': bool(good)})
    record(pid + ' actual flat bed contact', good,
           **{k: v for k, v in bed[-1].items() if k != 'passed'})

assembly_samples = 61
assembly_max = max(hit(a.move(z=float(dz)), b) for dz in np.linspace(30, 0, assembly_samples))
record('P04A vertical insertion onto P04B', assembly_max < .02,
       samples=assembly_samples, maximum_overlap_mm3=round(assembly_max, 6))

# Isolate the actual tongue below the mating plane, then check the intended
# 0.2mm side clearances geometrically rather than just reading dimensions.
key = a & c.box(8, 10, 1.2, 31, 0, 40.8 + lift)
record('Asymmetric locating tongue exists', volume(key) > 57.5,
       volume_mm3=round(volume(key), 4))
clearance_samples = []
for axis in ('x', 'y'):
    for sign in (-1, 1):
        free = hit(key.move(**{axis: sign * .199}), b)
        stopped = hit(key.move(**{axis: sign * .25}), b)
        good = free < .001 and stopped > .05
        clearance_samples.append({'axis': axis, 'sign': sign,
                                  'overlap_at_0_199_mm_mm3': round(free, 6),
                                  'overlap_at_0_25_mm_mm3': round(stopped, 6),
                                  'passed': good})
record('Locating tongue 0.2mm nominal side clearance',
       all(x['passed'] for x in clearance_samples), samples=clearance_samples,
       top_clearance_mm=.2)

nut_samples = 0
nut_worst = 0.
driver_checks = []
coverage_checks = []
for x, y in c.P04_MOUNTS:
    for bottom in np.linspace(33.5, nut_bottom, 64):
        nut = c.hex_nut3(x, y, float(bottom))
        nut_worst = max(nut_worst, hit(nut, b), hit(nut, a))
        nut_samples += 1
    screw = c.flat_screw(8).rot(x=180).move(x, y, deck_head_z)
    filled_bore = c.cyl(3, 2.4, x, y, nut_bottom)
    ratio = hit(screw, filled_bore) / volume(filled_bore)
    coverage_checks.append({'position_mm': [x, y], 'coverage_ratio': round(ratio, 6),
                            'nominal_nut_thickness_mm': 2.4, 'passed': ratio >= .995})
    # Hex bit enters the modeled 2mm socket. Round shaft/holder are above it.
    bit = c.cyl(2.25, 15, x, y, 44.2 + lift, n=6)
    shaft = c.cyl(2.6, 20, x, y, 45.45 + lift)
    holder = c.cyl(8, 15, x, y, 60.4 + lift)
    bodies = [a, b] + hardware['deckM3nut'] + hardware['deckM3x8']
    maximum = max(hit(tool, body) for tool in (bit, shaft, holder) for body in bodies)
    driver_checks.append({'position_mm': [x, y], 'maximum_overlap_mm3': round(maximum, 6),
                          'passed': maximum < .02})
record('Four P04B nuts insert from gear underside', nut_worst < .02,
       samples=nut_samples, final_bottom_z_mm=nut_bottom,
       maximum_overlap_mm3=round(nut_worst, 6), roof_mm=1.4)
record('Four M3x8 screws cover full 2.4mm nut thickness',
       all(x['passed'] for x in coverage_checks), instances=coverage_checks)
record('Driver access from above before P31 installation',
       all(x['passed'] for x in driver_checks), instances=driver_checks,
       socket_bit_AF_mm=round(2.25 * np.cos(np.pi / 6), 3),
       shaft_diameter_mm=2.6, holder_diameter_mm=8,
       scope='P04A/P04B and their four installed nuts/screws only; assemble before P31 and hopper.')

# The requested clearance concerns the carrier's main underside where its
# rails sweep over the fixed outer rim. The deeper locating tongue is at R31
# and must not be mistaken for the rim-facing underside.
cover = parts['P02A'].shape
rim = cover & (c.cyl(164, 12, z0=30) - c.cyl(159.6, 14, z0=29))
rim_top = float(rim.m.bounding_box()[5])
carrier_underside = 42. + lift
gap = carrier_underside - rim_top
nominal_worst, clear_worst, contact_min = 0., 0., float('inf')
for angle in range(360):
    turning = a.rot(z=angle)
    nominal_worst = max(nominal_worst, hit(turning, rim))
    clear_worst = max(clear_worst, hit(turning.move(z=-(gap - .01)), rim))
    contact_min = min(contact_min, hit(turning.move(z=-(gap + .02)), rim))
target_gap = float(c.P['turntable_to_base_ring_gap_mm'])
record('Raised carrier has requested 2mm rim clearance throughout 360deg',
       abs(gap - target_gap) < .001 and abs(target_gap - 2.) < .001
       and nominal_worst < .001 and clear_worst < .001 and contact_min > .01,
       poses=360, angular_step_deg=1, nominal_gap_mm=round(gap, 4),
       requested_gap_mm=target_gap, carrier_main_underside_z_mm=carrier_underside,
       fixed_rim_top_z_mm=rim_top, maximum_nominal_overlap_mm3=round(nominal_worst, 6),
       maximum_overlap_with_0_01mm_remaining_gap_mm3=round(clear_worst, 6),
       minimum_contact_when_lowered_0_02mm_beyond_gap_mm3=round(contact_min, 6),
       scope='Nominal main carrier underside over actual circular rim; no load, sag, warp or physical clearance measurement.')

large_teeth = b & (c.cyl(80, 14, z0=35) - c.cyl(69.2, 16, z0=34))
small_teeth = parts['P05A'].shape & (c.cyl(42, 14, 54, 0, 33) - c.cyl(33.2, 16, 54, 0, 32))
large_bounds, small_bounds = np.asarray(large_teeth.m.bounding_box()), np.asarray(small_teeth.m.bounding_box())
engagement = min(large_bounds[5], small_bounds[5]) - max(large_bounds[2], small_bounds[2])
record('Gear faces retain original 4mm axial engagement', abs(engagement - 4) < .001,
       large_tooth_z_band_mm=[round(float(large_bounds[2]), 4), round(float(large_bounds[5]), 4)],
       small_tooth_z_band_mm=[round(float(small_bounds[2]), 4), round(float(small_bounds[5]), 4)],
       axial_face_overlap_mm=round(float(engagement), 4),
       scope='Axial overlap only; complete conjugate meshing/rotation belongs to the full assembly audit.')

lower_reference = c.cyl(24.8, 22.9, z0=13) + c.cyl(31, 3, z0=31, d2=24.8)
lower_reference = lower_reference - c.cyl(22.5, 40, z0=10) - c.cylx(3.4, 5, -14.5, 0, 15.5)
actual_lower = b & c.box(80, 80, 22.9, 0, 0, 13)
lower_difference = volume((lower_reference - actual_lower) + (actual_lower - lower_reference))
bearing = next(shape for name, shape, _ in c.hardware if name == '6005ZZ')
bearing_interference = hit(b, bearing)
down_stop = hit(b.move(z=-.02), bearing)
record('Bearing shoulder lower journal and P06 hole remain at original datums',
       lower_difference < .001 and bearing_interference < .001 and down_stop > .1,
       reference_difference_mm3=round(lower_difference, 8), shoulder_contact_z_mm=31,
       journal_start_z_mm=13, P06_radial_hole_z_mm=15.5,
       nominal_bearing_overlap_mm3=round(bearing_interference, 6),
       bearing_overlap_on_0_02mm_downward_challenge_mm3=round(down_stop, 6),
       nominal_journal_to_bearing_diameter_clearance_mm=.2,
       warning='Simplified bearing envelope; no race contact pressure, preload or fit tolerance qualification.')

flag = c.assembly_pose('P26', parts['P26'].shape)
flag_bottom = float(flag.m.bounding_box()[2])
home_opto = next(shape for name, shape, _ in c.hardware if name == 'home_opto')
flag_collision = hit(flag, home_opto)
record('Extended P26 preserves original shutter lower edge',
       abs(flag_bottom - 35.6) < .001 and flag_collision < .001,
       assembled_lower_edge_z_mm=round(flag_bottom, 4),
       native_lower_edge_z_mm=round(float(parts['P26'].shape.m.bounding_box()[2]), 4),
       original_reference_lower_edge_z_mm=35.6, nominal_sensor_slot_floor_clearance_mm=.3,
       overlap_with_fixed_sensor_mm3=round(flag_collision, 6),
       warning='Original geometric shutter depth is preserved; actual optical beam height still requires hardware confirmation.')

rotor_nut = hardware['rotorM3nut'][0]
collar_nut_worst = max(hit(rotor_nut.move(z=float(dz)), collar)
                       for dz in np.linspace(15, 0, 61))
record('P06 nut inserts from above before collar installation', collar_nut_worst < .02,
       samples=61, maximum_overlap_mm3=round(collar_nut_worst, 6))
slot_bore_overlap = hit(c.nut_slot, c.cyl(25.2, 9, z0=11.3))
record('P06 nut slot stays outside 25.2mm shaft bore', slot_bore_overlap < .001,
       overlap_mm3=round(slot_bore_overlap, 6),
       nut_pocket_to_shaft_bore_nominal_spacing_mm=1.2,
       scope='The separate 3.4mm radial screw hole intentionally crosses this spacing.')
floor_probe = c.box(2.4, 3, 1.25, -15.15, 0, 11.5)
floor_ratio = hit(floor_probe, collar) / volume(floor_probe)
record('P06 nut-slot floor retains 1.25mm nominal material', floor_ratio > .999,
       thickness_mm=1.25, sampled_solid_ratio=round(floor_ratio, 6),
       scope='Central floor sample under nut well; not a whole-part structural minimum.')

rotor_screw = hardware['rotorM3x8'][0]
rigid_rotor = hardware['slipring_rotor'][0]
travel = []
for dx in np.linspace(0, .6, 13):
    screw = rotor_screw.move(x=float(dx))
    maximum = max(hit(screw, body) for body in (collar, b, rotor_nut))
    travel.append({'inward_shift_mm': round(float(dx), 3),
                   'maximum_fastener_housing_overlap_mm3': round(maximum, 6),
                   'rigid_rotor_overlap_mm3': round(hit(screw, rigid_rotor), 6),
                   'passed_housing_clearance': maximum < .02})
record('P06 screw housing clearance through 0.6mm adjustment',
       all(x['passed_housing_clearance'] for x in travel), samples=travel,
       nominal_rotor_contact_shift_mm=0,
       warning='Positive rigid-rotor overlap after nominal contact is NOT permitted or classified as designed interference. Travel describes housing room only; tighten lightly after contact, not until head bottoms.')

mark = parts['P04B'].engraving
mark_cut = c.U(c.box(cell + .03, cell + .03, mark['depth_mm'] + .12,
                    s, t, -mark['depth_mm'])
               for s, t, cell in c.letter_pixels(mark['text'], mark['height_mm']))
mark_cut = mark_cut.basis(mark['u'], mark['v'], mark['normal'], mark['origin_mm'])
verts = np.asarray(mark_cut.m.to_mesh().vert_properties)[:, :3]
max_radius = float(np.linalg.norm(verts[:, :2], axis=1).max())
record('P04B identifier avoids gear teeth and locating tongue',
       max_radius < 18 and hit(mark_cut, c.box(8, 10, 3, 31, 0, 39.5 + lift)) < .001,
       maximum_identifier_radius_mm=round(max_radius, 3),
       location=mark['location'], tooth_root_radius_mm=34.5)

report = {'revision': c.P['revision'], 'all_passed': all(x['passed'] for x in checks),
          'upper_head_lift_mm': lift, 'P04_mating_plane_z_mm': mate_z,
          'source_hashes': {
              'build_cad_py_sha256': hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),
              'design_params_json_sha256': hashlib.sha256((c.HERE / 'design_params.json').read_bytes()).hexdigest(),
              'check_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
          'scope': 'Nominal CAD/reference-envelope geometry; no physical assembly or slicer test.',
          'print_contact': bed, 'checks': checks,
          'limitations': [
              'Print fit, elephant foot, screw tolerances, friction, preload, strength and loosening require physical testing.',
              'Local nut-well/locating-slot roofs may need bridge settings or local support; no zero-support claim.',
              'P06 housing adjustment clearance does not authorize rigid slip-ring penetration or establish allowable clamping force.',
              'Install P04A/P04B fasteners before P31; load P06 nut before fitting collar beneath bearing.'
          ]}
(c.OUT / 'p04_split_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps(report, ensure_ascii=True, indent=2))
if not report['all_passed']:
    raise SystemExit(1)
