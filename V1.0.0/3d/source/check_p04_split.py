"""Check nominal split P04 assembly and P06 captive-nut access.

This is geometric validation, not print, strength or tightening validation.
The P06 adjustment test deliberately excludes the rigid slip-ring rotor:
travel after nominal contact is NOT an allowed rigid-body interference.
"""
import json
import hashlib
import math
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

# A complete 60T working band must be checked for missing material, not only
# collision-free assembly. Carrier-only mounting holes once cut the 210deg
# tooth between Z41 and Z42; a collision audit cannot detect that material loss.
pristine_gear = c.gear(60, 1.2, mate_z - 36, 36)
working_band = c.cyl(78, mate_z - 36, z0=36, n=720) - c.cyl(69, mate_z - 36 + .2, z0=35.9, n=720)
expected_teeth = pristine_gear & working_band
tooth_sectors = []
for index in range(60):
    low, high = math.radians(index * 6 - 3), math.radians(index * 6 + 3)
    sector = c.poly([(0, 0), (60 * math.cos(low), 60 * math.sin(low)),
                     (60 * math.cos(high), 60 * math.sin(high))], mate_z - 36, 36)
    expected_sector = expected_teeth & sector
    tooth_sectors.append((sector, volume(expected_sector), float(c.tm(expected_sector).area)))


def tooth_scan(shape, exported_float32_ulp_mm=0.):
    actual = shape & working_band
    missing, extra = expected_teeth - actual, actual - expected_teeth
    missing_volume, extra_volume = volume(missing), volume(extra)
    # STL vertex quantisation is bounded before recovery into native CAD.
    # Four exported-coordinate float32 ULPs cover serialisation, rigid recovery
    # and boolean numeric noise. Area*distance is a conservative first-order
    # volume budget; per-tooth checks keep a local defect from hiding in it.
    recovery_bound = 4 * exported_float32_ulp_mm
    samples = []
    for index, (sector, expected_volume, area) in enumerate(tooth_sectors):
        tolerance = max(.002, area * recovery_bound) if exported_float32_ulp_mm else .0001
        lost = hit(missing, sector) if missing_volume > 1e-10 else 0.
        added = hit(extra, sector) if extra_volume > 1e-10 else 0.
        samples.append({'tooth_index_0based': index, 'tooth_number_1based': index + 1,
                        'centre_angle_deg': index * 6, 'expected_volume_mm3': round(expected_volume, 6),
                        'missing_volume_mm3': round(lost, 8), 'extra_volume_mm3': round(added, 8),
                        'tolerance_mm3': round(tolerance, 8),
                        'passed': expected_volume > 1 and max(lost, added) <= tolerance})
    total_tolerance = sum(x['tolerance_mm3'] for x in samples)
    result = {'all_60_teeth_passed': all(x['passed'] for x in samples)
              and max(missing_volume, extra_volume) <= total_tolerance,
              'working_radius_lower_bound_mm': 34.5, 'full_height_z_band_mm': [36, mate_z],
              'missing_total_mm3': round(missing_volume, 8), 'extra_total_mm3': round(extra_volume, 8),
              'total_tolerance_mm3': round(total_tolerance, 8),
              'export_float32_ulp_mm': exported_float32_ulp_mm,
              'conservative_vertex_recovery_bound_mm': recovery_bound,
              'failed_tooth_indices_0based': [x['tooth_index_0based'] for x in samples if not x['passed']],
              'teeth': samples}
    return result, missing


cad_scan, _ = tooth_scan(b)
record('All 60 CAD teeth retain the complete pristine profile over full height',
       cad_scan['all_60_teeth_passed'], scan=cad_scan)

# Independently build only the intended B geometry, with no carrier-derived
# N20, hopper, hood or flag mounting cuts. This also catches unwanted holes in
# the inner spokes that a working-tooth-band comparison alone would miss.
spec_mounts = [(x, y) for x in (-15, 15) for y in (-26, 26)]
reference = c.gear(60, 1.2, mate_z - 36, 36) + c.cyl(24.8, mate_z - 13, z0=13)
reference = reference + c.cyl(31, 3, z0=31, d2=24.8) - c.cyl(22.5, mate_z, z0=10)
reference = reference - c.cylx(3.4, 5, -14.5, 0, 15.5)
for angle in range(0, 360, 60):
    reference = reference - c.annular_sector(18, 30, angle + 10, angle + 50, 9 + lift, 35)
for x, y in spec_mounts:
    boss = c.cyl(12, mate_z - 36, x, y, 36) & c.cyl(68.8, mate_z - 36, z0=36)
    reference = reference + boss
    reference = reference - c.cyl(3.4, 7 + lift, x, y, 35.8) - c.cyl(6.7, 4.7 + lift, x, y, 35.9, n=6)
reference = reference - c.box(6.4, 8.4, 1.5, 31, 0, 40.6 + lift) - mark_cut
reference_difference = volume((reference - b) + (b - reference))
record('Complete P04B matches independent gear journal and own-interface reference',
       reference_difference < .001 and set(c.P04_MOUNTS) == set(spec_mounts),
       symmetric_difference_mm3=round(reference_difference, 8),
       scope='Independent intended B body including bore, shoulder, six internal slots, four own fasteners/key and identifier; no P04A mounting holes.')


def load_exported_stl(path):
    mesh = c.trimesh.load_mesh(path, process=True)
    info = {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'watertight': bool(mesh.is_watertight), 'positive_volume': bool(mesh.volume > 0)}
    assert tuple(parts['P04B'].print_rot) == (180, 0, 0)
    printed_bounds = np.asarray(b.rot(*parts['P04B'].print_rot).m.bounding_box())
    manifold = c.mf.Manifold(c.mf.Mesh(np.ascontiguousarray(mesh.vertices, dtype=np.float32),
                                      np.ascontiguousarray(mesh.faces, dtype=np.uint32)))
    info['manifold_status'] = str(manifold.status())
    recovered = c.S(manifold, '').move(*printed_bounds[:3]).rot(x=-180)
    largest = float(np.abs(np.asarray(mesh.vertices)).max())
    ulp = float(np.spacing(np.float32(largest)))
    info['export_coordinate_max_mm'] = largest
    return recovered, ulp, info


stl_path = c.OUT / 'STL' / 'P04B.stl'
recovered_stl, stl_ulp, stl_info = load_exported_stl(stl_path)
stl_scan, _ = tooth_scan(recovered_stl, stl_ulp)
record('Exported P04B STL roundtrip retains all 60 full-height tooth profiles',
       stl_info['watertight'] and stl_info['positive_volume'] and stl_scan['all_60_teeth_passed'],
       exported_stl=stl_info, scan=stl_scan,
       tolerance_basis='Per tooth max(0.002mm3, expected surface area * 4 float32 exported-coordinate ULP); global tolerance is the sum, never a substitute for each tooth.')

# Always rerun an analytic negative control, even after temporary old STL files
# are removed from the release workspace. It reproduces the carrier-only N20
# pocket that used to affect the original B band before the upper extension.
legacy_n20 = (c.cyl(3.4, 6, -33, -19, 41) + c.cyl(6.55, 2.7, -33, -19, 41, n=6))
legacy_n20 = legacy_n20 & c.box(90, 90, 1, 0, 0, 41)
seeded_scan, seeded_missing = tooth_scan(pristine_gear - legacy_n20)
record('Negative control rejects the legacy N20 pocket at tooth index35 angle210deg',
       not seeded_scan['all_60_teeth_passed'] and 35 in seeded_scan['failed_tooth_indices_0based'],
       legacy_cutter_xy_mm=[-33, -19], legacy_cutter_z_band_mm=[41, 42], scan=seeded_scan)

baseline_evidence = {'available': False,
                     'note': 'Previous exported STL is a temporary audit artifact; the analytic negative control above is always rerun.'}
baseline_path = Path(c.os.environ.get('CARD_DEALER_P04_BASELINE', str(c.ROOT / '.build' / 'P04B_before.stl')))
if baseline_path.exists():
    previous, previous_ulp, previous_info = load_exported_stl(baseline_path)
    previous_scan, previous_missing = tooth_scan(previous, previous_ulp)
    sector35 = tooth_sectors[35][0]
    defect35 = previous_missing & sector35
    threshold = previous_scan['teeth'][35]['tolerance_mm3']
    bad_height_bins = []
    for bottom in np.arange(36, mate_z, .25):
        top = min(float(bottom + .25), mate_z)
        amount = hit(defect35, c.box(90, 90, top - float(bottom), 0, 0, float(bottom)))
        if amount > threshold:
            bad_height_bins.append({'z_band_mm': [round(float(bottom), 4), round(top, 4)],
                                     'missing_volume_mm3': round(amount, 8)})
    found_band = [bad_height_bins[0]['z_band_mm'][0], bad_height_bins[-1]['z_band_mm'][1]] if bad_height_bins else None
    defect_match = abs(previous_scan['teeth'][35]['missing_volume_mm3'] - seeded_scan['teeth'][35]['missing_volume_mm3'])
    baseline_evidence = {'available': True, 'exported_stl': previous_info, 'scan': previous_scan,
                         'tooth35_missing_height_bins': bad_height_bins,
                         'significant_defect_z_band_mm': found_band,
                         'volume_difference_from_legacy_cutter_mm3': round(defect_match, 8)}
    record('Previous defective exported STL is rejected with the original 210deg Z41..42 loss',
           not previous_scan['all_60_teeth_passed'] and 35 in previous_scan['failed_tooth_indices_0based']
           and found_band == [41., 42.] and defect_match <= max(.01, threshold * 2),
           evidence=baseline_evidence,
           numbering='Zero-based index35 is one-based tooth36, centred at 210deg; not an intended internal key or weight-reduction slot.')

report = {'revision': c.P['revision'], 'all_passed': all(x['passed'] for x in checks),
          'upper_head_lift_mm': lift, 'P04_mating_plane_z_mm': mate_z,
          'source_hashes': {
              'build_cad_py_sha256': hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),
              'design_params_json_sha256': hashlib.sha256((c.HERE / 'design_params.json').read_bytes()).hexdigest(),
              'check_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
          'scope': 'Nominal CAD/reference-envelope geometry; no physical assembly or slicer test.',
          'print_contact': bed, 'checks': checks, 'previous_export_evidence': baseline_evidence,
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
