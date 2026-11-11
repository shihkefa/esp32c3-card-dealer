"""Check the closed-floor, roof-height hopper and its two optional side shims.

These are nominal solid and reference-envelope checks, not print, support,
strength, friction, card-feeding or flexible-wire validation.
"""
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np
import build_cad as c

parts = {p.id: p for p in c.parts}
tray = parts['P08'].shape
shims = [parts['P12'].shape, parts['P12'].shape.rot(z=180).move(x=-8)]
world_tray = c.assembly_pose('P08', tray)
world_shims = [c.assembly_pose('P12', s) for s in shims]
checks = []
tol = .002


def vol(s):
    return float(s.m.volume())


def hit(a, b):
    return vol(a & b)


def record(name, passed, **details):
    checks.append({'test': name, 'passed': bool(passed), **details})


def filled(s, reference):
    return max(0., vol(reference - s))


def roof_local_z(x):
    # Independent conversion from the unchanged inclined deck and level roof.
    theta = math.radians(c.P['hopper_tilt_deg'])
    return 64 + (128.7 - 64 - 10 + x * math.sin(theta)) / math.cos(theta)


def world_x_at_roof(x):
    theta = math.radians(c.P['hopper_tilt_deg'])
    return x * math.cos(theta) + (roof_local_z(x) - 64) * math.sin(theta)


mesh_results = []
bed_results = []
for pid, minimum in [('P08', 6000), ('P12', 3000)]:
    p = parts[pid]
    printed = p.shape.rot(*p.print_rot)
    bounds = np.asarray(printed.m.bounding_box())
    dims = bounds[3:] - bounds[:3]
    source = c.tm(printed)
    exported = c.trimesh.load_mesh(io.BytesIO(source.export(file_type='stl')), file_type='stl')
    source_good = exported.is_watertight and len(p.shape.m.decompose()) == 1
    source_good = source_good and np.all(dims <= [175, 175, 180])
    saved = c.trimesh.load_mesh(c.OUT / 'STL' / (pid + '.stl'))
    expected_bytes = c.tm(printed.move(*(-source.bounds[0]))).export(file_type='stl')
    expected_sha = hashlib.sha256(expected_bytes).hexdigest()
    actual_sha = hashlib.sha256((c.OUT/'STL'/(pid+'.stl')).read_bytes()).hexdigest()
    exported_good = (saved.is_watertight and np.allclose(saved.extents, source.extents, atol=.001)
                     and abs(saved.volume - source.volume) < max(.005, source.volume * .00001)
                     and expected_sha == actual_sha)
    mesh_results.append({'part': pid, 'dimensions_mm': dims.round(5).tolist(),
                         'single_closed_body': bool(source_good),
                         'actual_STL_sha256': actual_sha,
                         'reexport_from_current_source_sha256': expected_sha,
                         'actual_STL_matches_current_source': bool(exported_good)})
    layer = c.box(float(dims[0]+2), float(dims[1]+2), .02,
                  float((bounds[0]+bounds[3])/2), float((bounds[1]+bounds[4])/2), float(bounds[2]))
    area = hit(layer, printed) / .02
    bed_results.append({'part': pid, 'contact_area_mm2': round(area, 3),
                        'minimum_mm2': minimum, 'passed': area >= minimum})
record('P08 and P12 are single closed bodies and their delivered STL files match',
       all(r['single_closed_body'] and r['actual_STL_matches_current_source'] for r in mesh_results),
       parts=mesh_results, safe_build_bounds_mm=[175, 175, 180])
record('Both revised parts have a substantial planar print-bed face',
       all(r['passed'] for r in bed_results), parts=bed_results, layer_mm=.02,
       limitation='Blind-pocket and hook bridging/support still require slicing.')

# A complete upper millimetre of floor must remain. Only the roller opening
# and the four pre-existing countersinks are removed from this reference.
floor = c.box(106, 61, 1, -2, 0, 63)
floor = floor - c.slotz(-22, 7, 60, 23, 12, 6)
for x in (-45, 31):
    for y in (-26, 26):
        floor = floor - c.hole(x, y, 60, 7) - c.cyl(3.4, 2, x, y, 62, d2=6.4)
floor_loss = filled(tray, floor)
record('The floor top is continuous except the roller aperture and original four countersinks',
       floor_loss < tol, missing_volume_mm3=round(floor_loss, 8),
       floor_native_interval_mm=[61.6, 64], checked_top_skin_mm=[63, 64],
       roller_window_mm={'center': [-22, 7], 'size': [23, 12]})

blind_results = []
for x in (-30.4, -13.6):
    # Boss diameter 8.4 and top62.2 expanded by0.3mm are clearance references.
    free = c.cyl(9, 3.8, x, -11, 58.7)
    top_skin = c.cyl(8.4, 1.3, x, -11, 62.7)
    overlap = hit(tray, free)
    skin_loss = filled(tray, top_skin)
    blind_results.append({'center_xy_mm': [x, -11], 'expanded_boss_overlap_mm3': round(overlap, 8),
                           'missing_top_skin_mm3': round(skin_loss, 8),
                           'passed': overlap < tol and skin_loss < tol})
record('P19 clamp bosses have blind underside clearance with a closed upper floor',
       all(r['passed'] for r in blind_results), pockets=blind_results,
       pocket_diameter_mm=9.2, pocket_top_z_mm=62.6, nominal_remaining_skin_mm=1.4)

side_results = []
for side in (-1, 1):
    missing = 0.
    for x in np.linspace(-50, 42, 47):
        high = roof_local_z(float(x)) - .5
        probe = c.box(.2, 2.2, high-64.1, float(x), side*31.7, 64.1)
        missing += filled(tray, probe)
    side_results.append({'side': side, 'missing_sampled_solid_mm3': round(missing, 8)})
record('Both lateral walls are filled from the deck to the raised rim',
       all(r['missing_sampled_solid_mm3'] < tol for r in side_results), sides=side_results,
       longitudinal_probe_columns_per_side=47, wall_thickness_mm=2.4)
channel = c.box(98, 60.8, 48, -4, 0, 64.1)
channel_overlap = hit(tray, channel)
record('The card channel retains 61mm nominal clear width', channel_overlap < tol,
       interior_probe_width_mm=60.8, obstruction_mm3=round(channel_overlap, 8))
end_results = []
for x in (-54.8, 50.8):
    q = c.box(.2, 60.8, 48, x, 0, 64.1)
    end_results.append({'x_mm': x, 'obstruction_mm3': round(hit(tray, q), 8)})
record('Front and rear ends remain open without a longitudinal stop',
       all(r['obstruction_mm3'] < tol for r in end_results), ends=end_results)

roof_top = 128.7 + c.UPPER_LIFT
above = hit(world_tray, c.box(400, 400, 50, 0, 0, roof_top+.0001))
top_results = []
for x in (-50, -25, 0, 25, 42):
    for side in (-1, 1):
        probe = c.box(.1, 1, .1, world_x_at_roof(x), side*31.7, roof_top-.1)
        top_results.append({'native_x_mm': x, 'side': side,
                            'missing_rim_mm3': round(filled(world_tray, probe), 8)})
record('Both installed wall rims are level and flush with the exterior roof',
       above < tol and all(r['missing_rim_mm3'] < 1e-6 for r in top_results),
       assembled_roof_top_z_mm=roof_top, material_above_roof_mm3=round(above, 8), probes=top_results)


def opening_clearance(s):
    # The rounded-rectangle loading aperture is a convex vertical extrusion.
    # All vertices of the material reaching the roof band must lie inside it.
    high = s & c.box(400, 200, 100, 0, 0, 126.5+c.UPPER_LIFT-.001)
    vertices = c.tm(high).vertices
    q = np.abs(vertices[:, :2] - [-15, 0]) - [59, 30]
    signed = np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(np.max(q, axis=1), 0) - 6
    return float(np.min(-signed)), int(len(vertices))


opening_results = []
for name, s in [('P08', world_tray), ('P12.1', world_shims[0]), ('P12.2', world_shims[1])]:
    gap, vertex_count = opening_clearance(s)
    opening_results.append({'part': name, 'minimum_XY_clearance_mm': round(gap, 6),
                             'roof_band_vertices_checked': vertex_count})
record('Raised walls and both central hangers fit the unchanged loading aperture',
       all(r['minimum_XY_clearance_mm'] >= .5-1e-5 for r in opening_results),
       opening_mm={'center_xy': [-15, 0], 'size': [130, 72], 'corner_radius': 6},
       components=opening_results, minimum_required_mm=.5)

# Complete rotational envelopes for the wheel core/clamp and two rubber rings.
envelope = (c.cyly(18.4, 10, -22, 3, 54) + c.cyly(19, 7, -22, 4.5, 54)
            + c.cyly(20.7, 2, -22, 4, 54) + c.cyly(20.7, 2, -22, 10, 54))
envelope_hit = hit(tray, envelope)
record('The complete feed-wheel rotational envelope clears the closed floor', envelope_hit < tol,
       overlap_mm3=round(envelope_hit, 8),
       reference='OD18.4 core plus OD19 clamp/fastener radial envelope and two OD20.7 rubber rings')

native_group = [parts['P17'].shape]
for name, s, _ in c.hardware:
    if name in {'feedM3x8', 'feedM3nut', 'feedrubber'}:
        raw = s.move(z=-(64+10+c.UPPER_LIFT)).rot(y=-c.P['hopper_tilt_deg']).move(z=64)
        native_group.append(raw)
spinning_max = 0.
for deg in range(360):
    for s in native_group:
        spun = s.move(x=22, z=-54).rot(y=deg).move(x=-22, z=54)
        spinning_max = max(spinning_max, hit(spun, tray))
record('Actual feed wheel and its screws nuts and rings clear P08 over a sampled full turn',
       spinning_max < tol, angles=360, increment_deg=1, members=len(native_group),
       maximum_overlap_mm3=round(spinning_max, 8), scope='Sampled source geometry; continuous envelope checked separately.')

neighbour_results = []
for pid in ('P07', 'P09', 'P13', 'P14', 'P18', 'P19', 'P23', 'P31', 'P32A', 'P32B'):
    for pid2, name, s, _ in c.assembly_printables():
        if pid2 == pid:
            neighbour_results.append({'instance': name, 'part': pid, 'overlap_mm3': round(hit(world_tray, s), 8)})
for name, s, _ in c.hardware:
    if name in {'n20clampM3x8', 'N20', 'hopperM3x25', 'gateM3x8', 'gateM3nut'}:
        neighbour_results.append({'instance': name, 'overlap_mm3': round(hit(world_tray, s), 8)})
record('Revised P08 clears its installed surrounding components and retained fasteners',
       all(r['overlap_mm3'] < tol for r in neighbour_results), components=neighbour_results)

shim_results = []
for index, s in enumerate(shims, 1):
    # Same-STL opposite-side placement must retain the centered hanger.
    assembly = c.assembly_pose('P12', s)
    overlap = hit(s, tray)
    # Sample strictly inside the wall thickness: including the exact Y30.5
    # contact plane can retain zero-volume stem facets in a boolean mesh.
    bridge = s & c.box(15, 2.2, 3, -4, (1 if index == 1 else -1)*31.7, 118)
    vertices = c.tm(c.assembly_pose('P12', bridge)).vertices
    rim_gap = float(np.min(vertices[:, 2]) - roof_top)
    path_max = max(hit(assembly.move(z=float(d)), world_tray) for d in np.linspace(60, 0, 61))
    shim_results.append({'instance': index, 'seated_overlap_mm3': round(overlap, 8),
                         'minimum_vertical_bridge_clearance_mm': round(rim_gap, 6),
                         'vertical_drop_samples': 61, 'insertion_overlap_mm3': round(path_max, 8)})
record('The same centered-hanger P12 fits and drops in from above on both sides',
       all(r['seated_overlap_mm3'] < tol and r['insertion_overlap_mm3'] < tol
           and r['minimum_vertical_bridge_clearance_mm'] >= .298 for r in shim_results),
       shims=shim_results, nominal_local_wall_to_hanger_clearance_mm=.3)
shim_inner = c.U(shims)
narrow_probe = c.box(81, 57.8, 43.8, -4, 0, 64.1)
shim_obstruction = hit(shim_inner, narrow_probe)
record('Installed narrow-card shims retain 58mm nominal card width', shim_obstruction < tol,
       interior_probe_width_mm=57.8, obstruction_mm3=round(shim_obstruction, 8))

card_results = []
for width, length in ((57, 87), (60, 96)):
    surroundings = [tray] + (shims if width == 57 else [])
    worst = 0.
    for count in (1, 13, 54, 108):
        card = c.box(length, width, count*.3, 44.5-length/2, 0, 64)
        weights = [parts[pid].shape.move(z=64+count*.3-97) for pid in ('P10', 'P11')]
        worst = max(worst, *(hit(item, obstacle) for item in [card]+weights for obstacle in surroundings))
    card_results.append({'card_mm': [width, length], 'maximum_overlap_mm3': round(worst, 8)})
record('Both card sizes and descending gravity weights clear the new walls and shims',
       all(r['maximum_overlap_mm3'] < tol for r in card_results), card_cases=card_results,
       deck_counts=[1, 13, 54, 108], card_reference_thickness_mm=.3)

housing = c.U([c.assembly_pose(pid, parts[pid].shape) for pid in ('P32A', 'P32B')])
cover_max = max(hit(housing.move(z=float(d)), world_tray+c.U(world_shims)) for d in np.linspace(80, 0, 81))
record('The upper cover can be lowered over the raised hopper and optional shims',
       cover_max < tol, vertical_samples=81, maximum_overlap_mm3=round(cover_max, 8),
       scope='Housing halves and revised hopper/shims only; full UI/hardware path checked in global assembly report.')

report = {'revision': c.P['revision'], 'all_passed': all(r['passed'] for r in checks),
          'source_hashes': {
              'build_cad_py_sha256': hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),
              'design_params_json_sha256': hashlib.sha256((c.HERE/'design_params.json').read_bytes()).hexdigest(),
              'check_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
          'checks': checks,
          'scope': 'Nominal source solids, delivered P08/P12 meshes, continuous wheel references and sampled assembly paths.',
          'limitations': ['No physical printing, slicer/support, impact, friction, card feeding or deflection test.',
                          'Small clearances and hanger retention require actual print-fit confirmation.',
                          'P19 is installed before the closed-floor P08; underside screw access is not a through hole.']}
(c.OUT/'p08_hopper_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
print(json.dumps({'all_passed': report['all_passed'], 'checks': len(checks),
                  'failed': [r for r in checks if not r['passed']]}, ensure_ascii=False, indent=2))
if not report['all_passed']:
    raise SystemExit(1)
