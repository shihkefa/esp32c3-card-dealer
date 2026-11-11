"""Verify screw SKUs and full nut coverage in current assembled world poses."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
import build_cad as c
from virtual_assembly_check import actors, Actor, overlap

aa = actors()
byname = {}
for actor in aa:
    byname.setdefault(actor.kind, []).append(actor)
reg = c.fastener_registry
screw_names = {r['name'] for r in reg if r['kind'] == 'screw'}
nut_names = {r['name'] for r in reg if r['kind'] == 'nut'}
screws = [a for a in aa if a.kind in screw_names]
nuts = [a for a in aa if a.kind in nut_names]
assert len(screws) + len(nuts) == len(reg)
assert {r['sku'] for r in reg if r['kind'] == 'screw'} == {'DIN7991 M3x8', 'DIN7991 M3x25'}
assert len({r['sku'] for r in reg if r['kind'] == 'nut'}) == 1
expected = float(c.cyl(3, 2.4).m.volume())
specific_mates = {'deckM3nut': 'deckM3x8', 'flagM3nut': 'flagM3x8',
                  'hopperM3nut': 'hopperM3x25', 'hoodJoinM3nut': 'hoodJoinM3x8'}
checks = []
for n in nuts:
    vertices = np.asarray(n.shape.m.to_mesh().vert_properties)[:, :3]
    filled = c.mf.Manifold.hull_points(vertices) - n.shape.m
    probe = Actor(n.key + '.bore', 'bore', c.S(filled, ''), n.group)
    hits = [(overlap(probe, s)[0], s.key, s.kind) for s in screws]
    volume, mate, mate_kind = max(hits)
    ratio = volume / expected
    kind_matches = n.kind not in specific_mates or mate_kind == specific_mates[n.kind]
    checks.append({'nut': n.key, 'screw': mate, 'nominal_nut_thickness_mm': 2.4,
                    'major_diameter_shank_coverage_mm': round(ratio * 2.4, 4),
                    'coverage_ratio': round(ratio, 6),
                    'required_mate_kind': specific_mates.get(n.kind),
                    'passed': ratio >= .995 and kind_matches})

# actors() already consumes c.assembly_printables() and c.hardware, which are
# world-posed by the CAD builder. Do not apply head_pose a second time here.
# Explicit datum guards prevent old native heights from silently passing.
pose_checks = []
for kind, measure, target in [
        ('deckM3x8', 'max_z', 45.4 + c.UPPER_LIFT),
        ('deckM3nut', 'min_z', 38.2 + c.UPPER_LIFT),
        ('flagM3x8', 'min_z', 40.6 + c.UPPER_LIFT),
        ('flagM3nut', 'min_z', 45.4 + c.UPPER_LIFT),
        ('retainerM3x8', 'max_z', 35), ('retainerM3nut', 'min_z', 28.1),
        ('rotorM3x8', 'centre_z', 15.5), ('rotorM3nut', 'centre_z', 15.5),
        ('pinionM3x8', 'centre_z', c.P05_CLAMP_Z),
        ('pinionJoinM3x8', 'max_z', 40), ('pinionJoinM3nut', 'min_z', 34.1)]:
    instances = byname.get(kind, [])
    values = []
    for actor in instances:
        bounds = np.asarray(actor.shape.m.bounding_box())
        value = float(bounds[5] if measure == 'max_z' else bounds[2] if measure == 'min_z'
                      else (bounds[2] + bounds[5]) / 2)
        values.append({'instance': actor.key, 'actual_z_mm': round(value, 6),
                        'passed': abs(value - target) < .001})
    pose_checks.append({'kind': kind, 'datum': measure, 'expected_z_mm': target,
                         'instances': values,
                         'passed': bool(instances) and all(x['passed'] for x in values)})
parts = {p.id: p for p in c.parts}
for pid in ('P04A', 'P04B', 'P06', 'P26'):
    actual = byname[pid][0].shape.m
    expected_shape = c.assembly_pose(pid, parts[pid].shape).m
    difference = float(((actual - expected_shape) + (expected_shape - actual)).volume())
    pose_checks.append({'part': pid, 'assembly_pose_difference_mm3': round(difference, 8),
                         'passed': difference < .001})

counts = Counter(r['sku'] for r in reg)
report = {'revision': c.P['revision'], 'upper_head_lift_mm': c.UPPER_LIFT,
          'coordinate_frame': 'Current assembled world geometry from actors(); no repeated lift transform.',
          'source_hashes': {
              'build_cad_py_sha256': hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),
              'design_params_json_sha256': hashlib.sha256((c.HERE / 'design_params.json').read_bytes()).hexdigest(),
              'check_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
          'screw_skus': {k: v for k, v in counts.items() if k.startswith('DIN7991')},
          'nut_skus': {k: v for k, v in counts.items() if not k.startswith('DIN7991')},
          'total_screw_qty': len(screws), 'total_nut_qty': len(nuts),
          'all_passed': all(x['passed'] for x in checks + pose_checks),
          'checks': checks, 'world_pose_checks': pose_checks,
          'scope': 'Nominal smooth major-diameter envelopes through full 2.4mm nut thickness and selected assembled datums. Physical threads, preload, strength, friction, screw tolerances, deflection and loosening are not validated.'}
(c.OUT / 'fastener_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({k: v for k, v in report.items() if k not in {'checks', 'world_pose_checks'}}, ensure_ascii=False, indent=2))
if not report['all_passed']:
    print(json.dumps([x for x in checks + pose_checks if not x['passed']], indent=2))
    raise SystemExit(1)
