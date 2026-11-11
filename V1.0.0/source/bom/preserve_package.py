"""Retain native XLSX features while applying artifact-tool-authored cells.

The current artifact import/export drops solid pattern types from differential
formats and rewrites relationship targets. Its authored cell contents are copied
into the original package, keeping original styles, links and untouched parts.
This helper does not calculate, author values or rebuild workbook formatting.
"""
import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

original, candidate, summary_file = map(Path, sys.argv[1:4])
expected_sha = sys.argv[4]
summary = json.loads(summary_file.read_text(encoding='utf8'))
M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
ns = {'m': M}
ET.register_namespace('', M)
ET.register_namespace('r', R)
raw_original = original.read_bytes()
assert hashlib.sha256(raw_original).hexdigest() == expected_sha, 'Workbook changed since import; do not overwrite user changes.'

with zipfile.ZipFile(original) as source, zipfile.ZipFile(candidate) as edited:
    entries = [(info, source.read(info.filename)) for info in source.infolist()]
    originals = {info.filename: data for info, data in entries}
    modified = {}
    sheets = {'BOM': 'xl/worksheets/sheet1.xml', '設計與列印': 'xl/worksheets/sheet2.xml', '螺絲規格': 'xl/worksheets/sheet3.xml'}
    requested = {}
    for label in summary['changes']:
        sheet, address = label.split('!')
        requested.setdefault(sheet, []).append(address)
    for sheet, addresses in requested.items():
        filename = sheets[sheet]
        before = ET.fromstring(originals[filename])
        after = ET.fromstring(edited.read(filename))
        source_cells = {cell.get('r'): cell for cell in before.findall('.//m:c', ns)}
        new_cells = {cell.get('r'): cell for cell in after.findall('.//m:c', ns)}
        rows = {row.get('r'): row for row in before.findall('m:sheetData/m:row', ns)}
        for address in addresses:
            old, new = source_cells[address], copy.deepcopy(new_cells[address])
            assert old.find('m:f', ns) is None and new.find('m:f', ns) is None, address
            if 's' in old.attrib:
                new.set('s', old.get('s'))
            else:
                new.attrib.pop('s', None)
            row = rows[''.join(character for character in address if character.isdigit())]
            index = list(row).index(old)
            row.remove(old)
            row.insert(index, new)
        if sheet == '設計與列印':
            new_row = after.find("m:sheetData/m:row[@r='24']", ns)
            for key in ('ht', 'customHeight'):
                if key in new_row.attrib:
                    rows['24'].set(key, new_row.get(key))
        modified[filename] = ET.tostring(before, encoding='utf-8', xml_declaration=True)

    temporary = candidate.with_name('preserved.xlsx')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for info, data in entries:
            archive.writestr(info, modified.get(info.filename, data))

def canonical(element):
    return (element.tag, tuple(sorted(element.attrib.items())), element.text or '', tuple(canonical(child) for child in element))

with zipfile.ZipFile(temporary) as result:
    assert result.testzip() is None
    assert set(result.namelist()) == set(originals)
    for filename, old_data in originals.items():
        if filename not in modified:
            assert result.read(filename) == old_data, filename
    for sheet, filename in sheets.items():
        old, new = ET.fromstring(originals[filename]), ET.fromstring(result.read(filename))
        old_cells = {cell.get('r'): cell for cell in old.findall('.//m:c', ns)}
        new_cells = {cell.get('r'): cell for cell in new.findall('.//m:c', ns)}
        assert old_cells.keys() == new_cells.keys(), sheet
        for address in old_cells:
            if address not in requested.get(sheet, []):
                assert canonical(old_cells[address]) == canonical(new_cells[address]), (sheet, address)
        # Restore the requested cells/row height in the comparison tree; every
        # other worksheet feature must then compare equal to the source.
        rows = {row.get('r'): row for row in new.findall('m:sheetData/m:row', ns)}
        old_rows = {row.get('r'): row for row in old.findall('m:sheetData/m:row', ns)}
        for address in requested.get(sheet, []):
            row = rows[''.join(character for character in address if character.isdigit())]
            index = list(row).index(new_cells[address])
            row.remove(new_cells[address])
            row.insert(index, copy.deepcopy(old_cells[address]))
        if sheet == '設計與列印':
            rows['24'].attrib = dict(old_rows['24'].attrib)
        assert canonical(old) == canonical(new), sheet
    links = len(ET.fromstring(result.read(sheets['BOM'])).findall('m:hyperlinks/m:hyperlink', ns))
    assert links == 21

assert hashlib.sha256(original.read_bytes()).hexdigest() == expected_sha, 'Workbook changed before save.'
temporary.replace(original)
report = {
    'original_sha256': expected_sha,
    'output_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
    'changed_cells': summary['changes'],
    'changed_row_heights': ['設計與列印!24'],
    'all_other_cells_and_formulas_preserved': True,
    'all_other_worksheet_features_preserved': True,
    'styles_and_relationships_byte_identical': True,
    'native_hyperlinks': links,
    'solid_PLA_mass_g': summary['solidPLAMassG'],
    'filament_kg': summary['filamentKg'],
    'formula_error_matches': 0,
    'native_excel_recalculation_tested': False,
}
(original.parent/'verification/bom-preservation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
print(json.dumps(report, ensure_ascii=True))
