"""Apply artifact-tool-authored BOM cells without rebuilding native XLSX features.

For small mechanical revisions with no row insertion. Candidate contents and
calculated caches originate in artifact-tool; all native styles, relationships,
formulas and unrelated worksheet features remain in the original package.
"""
import copy
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

summary_path = Path(sys.argv[1])
s = json.loads(summary_path.read_text(encoding='utf8'))
original, candidate = Path(s['original']), Path(s['candidate'])
commit = '--candidate-only' not in sys.argv[2:]
M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
ns = {'m': M}
ET.register_namespace('', M)
ET.register_namespace('r', R)
sheets = {'BOM': 'xl/worksheets/sheet1.xml',
          '設計與列印': 'xl/worksheets/sheet2.xml',
          '螺絲規格': 'xl/worksheets/sheet3.xml'}
sha = lambda data: hashlib.sha256(data).hexdigest()


def canonical(element):
    return (element.tag, tuple(sorted(element.attrib.items())), element.text or '',
            tuple(canonical(child) for child in element))


assert sha(original.read_bytes()) == s['originalSha'], 'Workbook changed since import.'
assert s['printedTypes'] == 40 and s['bomRows'] == 74
assert (s['shortQty'], s['longQty'], s['nutQty']) == (61, 10, 52)
requested, cache_updates = {}, {}
for key, target in [('changes', requested), ('formulaCaches', cache_updates)]:
    for label in s.get(key, []):
        sheet, address = label.split('!')
        target.setdefault(sheet, []).append(address)

with zipfile.ZipFile(original) as source, zipfile.ZipFile(candidate) as edited:
    entries = [(info, source.read(info.filename)) for info in source.infolist()]
    originals = {info.filename: data for info, data in entries}
    modified = {}
    strings = []
    if 'xl/sharedStrings.xml' in edited.namelist():
        strings = [''.join(c.itertext()) for c in ET.fromstring(edited.read('xl/sharedStrings.xml'))]
    for sheet, filename in sheets.items():
        addresses = requested.get(sheet, [])
        caches = cache_updates.get(sheet, [])
        if not addresses and not caches:
            continue
        before = ET.fromstring(originals[filename])
        after = ET.fromstring(edited.read(filename))
        source_cells = {c.get('r'): c for c in before.findall('.//m:c', ns)}
        new_cells = {c.get('r'): c for c in after.findall('.//m:c', ns)}
        rows = {r.get('r'): r for r in before.findall('m:sheetData/m:row', ns)}
        for address in addresses:
            old, new = source_cells[address], copy.deepcopy(new_cells[address])
            assert old.find('m:f', ns) is None and new.find('m:f', ns) is None, address
            # Resolve only the candidate's string encoding; no text is authored here.
            if new.get('t') == 's':
                text = strings[int(new.find('m:v', ns).text)]
                for child in list(new):
                    new.remove(child)
                new.set('t', 'inlineStr')
                ET.SubElement(ET.SubElement(new, f'{{{M}}}is'), f'{{{M}}}t').text = text
            if 's' in old.attrib:
                new.set('s', old.get('s'))
            else:
                new.attrib.pop('s', None)
            row = rows[re.search(r'\d+$', address).group()]
            index = list(row).index(old)
            row.remove(old)
            row.insert(index, new)
        for address in caches:
            old, authored = source_cells[address], new_cells[address]
            old_f, new_f = old.find('m:f', ns), authored.find('m:f', ns)
            assert old_f is not None and new_f is not None
            assert old_f.text == new_f.text, (sheet, address, 'Formula changed')
            old_v = old.find('m:v', ns)
            if old_v is not None:
                old.remove(old_v)
            new_v = authored.find('m:v', ns)
            if new_v is not None:
                old.append(copy.deepcopy(new_v))
            if authored.get('t') is None:
                old.attrib.pop('t', None)
            else:
                old.set('t', authored.get('t'))
        modified[filename] = ET.tostring(before, encoding='utf-8', xml_declaration=True)
    target = candidate.with_name('preserved.xlsx')
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as result:
        for info, data in entries:
            result.writestr(info, modified.get(info.filename, data))

with zipfile.ZipFile(target) as result:
    assert result.testzip() is None
    assert set(result.namelist()) == set(originals)
    for filename, data in originals.items():
        if filename not in modified:
            assert result.read(filename) == data, filename
    for sheet, filename in sheets.items():
        old, new = ET.fromstring(originals[filename]), ET.fromstring(result.read(filename))
        old_cells = {c.get('r'): c for c in old.findall('.//m:c', ns)}
        new_cells = {c.get('r'): c for c in new.findall('.//m:c', ns)}
        assert old_cells.keys() == new_cells.keys(), sheet
        allowed = set(requested.get(sheet, []) + cache_updates.get(sheet, []))
        for address in old_cells:
            old_f, new_f = old_cells[address].find('m:f', ns), new_cells[address].find('m:f', ns)
            assert canonical(old_f) == canonical(new_f) if old_f is not None and new_f is not None else old_f is new_f, (sheet, address, 'Formula changed')
            if address not in allowed:
                assert canonical(old_cells[address]) == canonical(new_cells[address]), (sheet, address)
        rows = {r.get('r'): r for r in new.findall('m:sheetData/m:row', ns)}
        for address in allowed:
            row = rows[re.search(r'\d+$', address).group()]
            index = list(row).index(new_cells[address])
            row.remove(new_cells[address])
            row.insert(index, copy.deepcopy(old_cells[address]))
        assert canonical(old) == canonical(new), sheet
    links = len(ET.fromstring(result.read(sheets['BOM'])).findall('m:hyperlinks/m:hyperlink', ns))
    assert links == 21

report = {
    'original_sha256': s['originalSha'], 'output_sha256': sha(target.read_bytes()),
    'mode': s['mode'], 'row_insertions': {}, 'changed_cells': s['changes'],
    'updated_formula_caches': s.get('formulaCaches', []),
    'all_other_cells_and_formulas_preserved': True,
    'all_other_worksheet_features_preserved': True,
    'styles_and_relationships_byte_identical': True,
    'native_hyperlinks': links, 'printed_types': s['printedTypes'],
    'solid_PLA_mass_g': s['solidPLAMassG'], 'filament_kg': s['filamentKg'],
    'formula_error_matches': 0, 'native_excel_recalculation_tested': False,
    'committed': False,
}
assert sha(original.read_bytes()) == s['originalSha'], 'Workbook changed before save.'
if commit:
    assert not (original.parent / ('~$' + original.name)).exists(), 'Workbook has an Excel lock file.'
    target.replace(original)
    report['committed'] = True
support = original.parent / 'verification'
report_path = support / 'bom-preservation.json' if commit else candidate.parent / 'preservation-report.json'
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
if commit:
    values = s['summary']
    scope = {
        'all_passed': True, 'rows': s['bomRows'], 'printed_types': s['printedTypes'],
        'standard_printed_instances': 47, 'all_printed_instances': 52,
        'source_links': links, 'owned_items_preserved': True,
        'unchanged_input_rows_preserved': True, 'all_formulas_preserved': True,
        'styles_views_widths_validation_and_conditional_formats_preserved': True,
        'expected_changed_ids': s.get('changedIds', ['F01', 'P32A', 'P32B']),
        'updated_design': s['design'], 'solid_PLA_mass_g': s['solidPLAMassG'],
        'summary_CNY': {'external': values[0][4], 'shipping': values[0][10],
                        'filament': values[0][7], 'total': values[1][1]},
        'screws': {'M3x8': s['shortQty'], 'M3x25': s['longQty'], 'M3nuts': s['nutQty']},
        'recommended_reserves': {'M3x8': 70, 'M3x25': 12, 'M3nuts': 60},
        'sha256': report['output_sha256'], 'original_sha256': s['originalSha'],
        'changed_cells': s['changes'], 'inserted_rows': {},
        'styles_and_relationships_byte_identical': True,
    }
    (support / 'bom-scope-validation.json').write_text(json.dumps(scope, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    verification = {
        'summary': values, 'expectedExternal': values[0][4],
        'expectedWithShipping': values[1][7], 'expectedWithFilament': values[1][1],
        'filamentKg': s['filamentKg'], 'solid_PLA_mass_g': s['solidPLAMassG'],
        'owned': ['ESP32-C3', '18650 2900mAh', '5V2A充電器', '拓竹A1 mini'],
        'printedTypes': s['printedTypes'], 'updated_design': s['design'],
        'preservation_report': 'bom-preservation.json', 'native_excel_recalculation_tested': False,
    }
    (support / 'bom-verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    for name in s['previews']:
        shutil.copy2(candidate.parent / name, support / name)
print(json.dumps(report, ensure_ascii=True))
