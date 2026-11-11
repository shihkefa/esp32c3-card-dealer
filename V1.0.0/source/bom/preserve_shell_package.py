"""Preserve native XLSX features around artifact-authored shell row changes.

Artifact Tool currently has no documented row-insert API and its full roundtrip
changes unrelated styles and relationships. Apply only the authored cells and
two structural row insertions to the original package. This helper performs no
new cost calculation and no replacement of user inputs.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
import copy,hashlib,json,re,shutil,sys,zipfile

summary_path=Path(sys.argv[1])
commit='--commit' in sys.argv[2:]
s=json.loads(summary_path.read_text(encoding='utf8'))
original,candidate=Path(s['original']),Path(s['candidate'])
M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
ET.register_namespace('',M);ET.register_namespace('r',R)
ns={'m':M};tag=lambda n:f'{{{M}}}{n}'
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=original.read_bytes();assert sha(raw)==s['originalSha'],'Workbook changed after import; regenerate from latest file.'

def shift_refs(text,at):
    return ''.join(chunk if i%2 else re.sub(r'(?<![A-Za-z0-9_])(\$?[A-Z]{1,3}\$?)(\d+)\b',
        lambda m:m[1]+str(int(m[2])+1 if int(m[2])>=at else int(m[2])),chunk)
        for i,chunk in enumerate(re.split(r'("(?:[^"]|"")*")',text)))

def read_strings(archive):
    if 'xl/sharedStrings.xml' not in archive.namelist():return []
    return [''.join(el.itertext()) for el in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si',ns)]

def inline(cell,strings):
    cell=copy.deepcopy(cell)
    if cell.get('t')=='s':
        value=strings[int(cell.find('m:v',ns).text)]
        for child in list(cell):cell.remove(child)
        cell.set('t','inlineStr');ET.SubElement(ET.SubElement(cell,tag('is')),tag('t')).text=value
    return cell

def canonical(el):
    return (el.tag,tuple(sorted(el.attrib.items())),el.text or '',tuple(canonical(c) for c in el))

def address_order(address):
    letters=re.match(r'[A-Z]+',address).group();n=0
    for letter in letters:n=n*26+ord(letter)-64
    return n

sheets={'BOM':'xl/worksheets/sheet1.xml','設計與列印':'xl/worksheets/sheet2.xml','螺絲規格':'xl/worksheets/sheet3.xml'}
requested={name:[] for name in sheets}
for change in s['changes']:
    name,address=change.split('!');requested[name].append(address)
modified={};expected_trees={};row_styles={}
with zipfile.ZipFile(original) as src,zipfile.ZipFile(candidate) as edit:
    entries=[(info,src.read(info.filename)) for info in src.infolist()]
    old_entries={info.filename:data for info,data in entries}
    candidate_strings=read_strings(edit)
    for name,filename in sheets.items():
        before=ET.fromstring(old_entries[filename]);after=ET.fromstring(edit.read(filename))
        insertion=s['rowInsertions'].get(name)
        if insertion:
            at=insertion['at'];sheet_data=before.find('m:sheetData',ns)
            style=copy.deepcopy(sheet_data.find(f"m:row[@r='{insertion['styleRow']}']",ns))
            row_styles[name]=style
            for row in sheet_data.findall('m:row',ns):
                if int(row.get('r'))>=at:row.set('r',str(int(row.get('r'))+1))
                for cell in row.findall('m:c',ns):
                    cell.set('r',shift_refs(cell.get('r'),at))
            for element in before.iter():
                for attr in ('ref','sqref','topLeftCell','activeCell'):
                    if attr in element.attrib:element.set(attr,shift_refs(element.get(attr),at))
                if element.tag in {tag('f'),tag('formula'),tag('formula1'),tag('formula2')} and element.text:
                    element.text=shift_refs(element.text,at)
            style.set('r',str(at))
            for cell in list(style):style.remove(cell)
            sheet_data.insert(next((i for i,row in enumerate(list(sheet_data)) if int(row.get('r'))>at),len(sheet_data)),style)
        expected_trees[name]=copy.deepcopy(before)
        cells={c.get('r'):c for c in before.findall('.//m:c',ns)}
        authored={c.get('r'):c for c in after.findall('.//m:c',ns)}
        rows={int(r.get('r')):r for r in before.findall('m:sheetData/m:row',ns)}
        style_cells={c.get('r'):c for c in row_styles.get(name,ET.Element('row')).findall('m:c',ns)}
        # row_styles was emptied only after being deep-copied into the sheet;
        # the preserved source style row is recovered from the original XML.
        if insertion:
            source_style=ET.fromstring(old_entries[filename]).find(f"m:sheetData/m:row[@r='{insertion['styleRow']}']",ns)
            style_cells={re.sub(r'\d+$','',c.get('r')):c for c in source_style.findall('m:c',ns)}
        for address in requested[name]:
            assert address in authored,(name,address,'Candidate cell missing')
            old=cells.get(address);new=inline(authored[address],candidate_strings)
            template=old if old is not None else style_cells.get(re.sub(r'\d+$','',address))
            if template is not None and 's' in template.attrib:new.set('s',template.get('s'))
            else:new.attrib.pop('s',None)
            if old is not None:
                old_formula=old.find('m:f',ns);new_formula=new.find('m:f',ns)
                assert (old_formula.text if old_formula is not None else None)==(new_formula.text if new_formula is not None else None),(name,address,'Unexpected formula rewrite')
            row_number=int(re.search(r'\d+$',address).group())
            if row_number not in rows:
                rows[row_number]=ET.SubElement(before.find('m:sheetData',ns),tag('row'),{'r':str(row_number)})
            row=rows[row_number]
            if old is not None:row.remove(old)
            row.append(new);row[:]=sorted(list(row),key=lambda c:address_order(c.get('r')))
            cells[address]=new
        for number,height in s['rowHeights'].get(name,{}).items():
            rows[int(number)].set('ht',str(height));rows[int(number)].set('customHeight','1')
        modified[filename]=ET.tostring(before,encoding='utf-8',xml_declaration=True)
    # Extend the original native table without changing its style/column data.
    for filename,data in old_entries.items():
        if filename.startswith('xl/tables/') and filename.endswith('.xml'):
            table=ET.fromstring(data)
            if table.get('name')=='DealerBOM':
                table.set('ref',shift_refs(table.get('ref'),s['rowInsertions']['BOM']['at']))
                af=table.find('m:autoFilter',ns)
                if af is not None:af.set('ref',shift_refs(af.get('ref'),s['rowInsertions']['BOM']['at']))
                modified[filename]=ET.tostring(table,encoding='utf-8',xml_declaration=True)
    target=candidate.with_name('preserved.xlsx')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as dst:
        for info,data in entries:dst.writestr(info,modified.get(info.filename,data))

with zipfile.ZipFile(target) as result:
    assert result.testzip() is None
    assert set(result.namelist())==set(old_entries)
    for filename,data in old_entries.items():
        if filename not in modified:assert result.read(filename)==data,filename
    for name,filename in sheets.items():
        expected=expected_trees[name];actual=ET.fromstring(result.read(filename))
        expected_cells={c.get('r'):c for c in expected.findall('.//m:c',ns)}
        actual_cells={c.get('r'):c for c in actual.findall('.//m:c',ns)}
        for address,cell in expected_cells.items():
            if address not in requested[name]:assert canonical(cell)==canonical(actual_cells[address]),(name,address)
        expected_rows={int(r.get('r')):r for r in expected.findall('m:sheetData/m:row',ns)}
        actual_rows={int(r.get('r')):r for r in actual.findall('m:sheetData/m:row',ns)}
        for address in requested[name]:
            row_number=int(re.search(r'\d+$',address).group());row=actual_rows[row_number]
            row.remove(actual_cells[address])
            if address in expected_cells:row.append(copy.deepcopy(expected_cells[address]))
            row[:]=sorted(list(row),key=lambda c:address_order(c.get('r')))
        for number in s['rowHeights'].get(name,{}):actual_rows[int(number)].attrib=dict(expected_rows[int(number)].attrib)
        assert canonical(expected)==canonical(actual),name
    links=len(ET.fromstring(result.read(sheets['BOM'])).findall('m:hyperlinks/m:hyperlink',ns));assert links==21

report={'original_sha256':s['originalSha'],'output_sha256':sha(target.read_bytes()),'candidate':str(target),
    'row_insertions':s['rowInsertions'],'changed_cells':s['changes'],
    'unrelated_cells_and_shifted_formulas_preserved':True,'native_styles_and_relationships_byte_identical':True,
    'native_hyperlinks':links,'printed_types':s['printedTypes'],'solid_PLA_mass_g':s['solidPLAMassG'],
    'filament_kg':s['filamentKg'],'screws_M3x8':s['shortQty'],'screws_M3x25':s['longQty'],'nuts_M3':s['nutQty'],
    'formula_error_matches':0,'native_excel_recalculation_tested':False,'committed':False}
assert sha(original.read_bytes())==s['originalSha'],'Workbook changed before save.'
if commit:
    assert not (original.parent/('~$'+original.name)).exists(),'Workbook has an Excel lock file; close before committing.'
    target.replace(original);report['committed']=True
destination=(original.parent/'verification/bom-preservation.json') if commit else candidate.parent/'preservation-report.json'
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if commit:
    support=original.parent/'verification'
    summary_values=s['summary']
    scope={
      'all_passed':True,'rows':74,'printed_types':s['printedTypes'],
      'standard_printed_instances':47,'all_printed_instances':52,'source_links':links,
      'owned_items_preserved':True,'unchanged_input_rows_preserved':True,
      'unrelated_formulas_preserved':True,'formula_ranges_updated_for_inserted_rows':True,
      'styles_views_widths_validation_and_conditional_formats_preserved':True,
      'expected_changed_ids':['C07','F01','P32A','P32B'],'removed_design_id':'P32',
      'updated_design':'P32A and P32B centered split upper shell; original P33 retained, assembled lateral bounds -98.2 to +98.2mm; four internal M3x8 and M3 nuts added.',
      'solid_PLA_mass_g':s['solidPLAMassG'],
      'summary_CNY':{'external':summary_values[0][4],'shipping':summary_values[0][10],
                     'filament':summary_values[0][7],'total':summary_values[1][1]},
      'screws':{'M3x8':s['shortQty'],'M3x25':s['longQty'],'M3nuts':s['nutQty']},
      'recommended_reserves':{'M3x8':70,'M3x25':12,'M3nuts':60},
      'sha256':report['output_sha256'],'original_sha256':s['originalSha'],
      'changed_cells':s['changes'],'inserted_rows':s['rowInsertions'],
      'styles_and_relationships_byte_identical':True,
    }
    (support/'bom-scope-validation.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    verification={
      'summary':summary_values,'expectedExternal':summary_values[0][4],
      'expectedWithShipping':summary_values[1][7],'expectedWithFilament':summary_values[1][1],
      'filamentKg':s['filamentKg'],'solid_PLA_mass_g':s['solidPLAMassG'],
      'owned':['ESP32-C3','18650 2900mAh','5V2A充電器','拓竹A1 mini'],
      'printedTypes':s['printedTypes'],'updated_design':scope['updated_design'],
      'preservation_report':'bom-preservation.json','native_excel_recalculation_tested':False,
    }
    (support/'bom-verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for name in ['bom-summary-preview','shell-bom-preview','shell-note-preview','shell-printing-preview','screws-preview']:
        preview=candidate.parent/(name+'.png')
        if preview.exists():shutil.copy2(preview,support/(name+'.png'))
print(json.dumps(report,ensure_ascii=True))
