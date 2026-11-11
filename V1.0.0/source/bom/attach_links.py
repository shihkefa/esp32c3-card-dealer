"""Add native hyperlinks, a missing feature of this artifact export runtime.

All cells, formulas, style and layout are authored by artifact-tool. This helper
only attaches relationship targets to its source-label cells.
"""
import json, sys, zipfile, os
from pathlib import Path
from xml.etree import ElementTree as ET

book=Path(sys.argv[1]); links=json.loads(Path(sys.argv[2]).read_text(encoding='utf8'))
sheet_name='xl/worksheets/sheet1.xml'
rels_name='xl/worksheets/_rels/sheet1.xml.rels'
M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
with zipfile.ZipFile(book) as z:
    entries=[(item,z.read(item.filename)) for item in z.infolist()]
data={info.filename:b for info,b in entries}
sheet=ET.fromstring(data[sheet_name])
existing=sheet.find(f'{{{M}}}hyperlinks')
if existing is not None:sheet.remove(existing)
rels=ET.fromstring(data[rels_name]) if rels_name in data else ET.Element(f'{{{PKG}}}Relationships')
used={e.get('Id') for e in rels}
hyperlinks=ET.Element(f'{{{M}}}hyperlinks')
for i,link in enumerate(links,1):
    rid=f'rIdSource{i}'
    assert rid not in used
    assert link['url'].startswith('https://')
    ET.SubElement(rels,f'{{{PKG}}}Relationship',{'Id':rid,'Type':R+'/hyperlink','Target':link['url'],'TargetMode':'External'})
    ET.SubElement(hyperlinks,f'{{{M}}}hyperlink',{'ref':link['ref'],f'{{{R}}}id':rid,'display':link['label']})
after={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','drawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
index=next((i for i,e in enumerate(sheet) if e.tag.split('}')[-1] in after),len(sheet))
sheet.insert(index,hyperlinks)
ET.register_namespace('',M);ET.register_namespace('r',R)
sheet_bytes=ET.tostring(sheet,encoding='utf-8',xml_declaration=True)
ET.register_namespace('',PKG)
rels_bytes=ET.tostring(rels,encoding='utf-8',xml_declaration=True)
new=book.with_suffix('.links.xlsx')
with zipfile.ZipFile(new,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for info,b in entries:
        if info.filename==sheet_name:b=sheet_bytes
        elif info.filename==rels_name:b=rels_bytes
        z.writestr(info,b)
    if rels_name not in data:z.writestr(rels_name,rels_bytes)
os.replace(new,book)
print(f'Native source links attached: {len(links)}')
