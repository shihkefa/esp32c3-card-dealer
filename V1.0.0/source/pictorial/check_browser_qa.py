from pathlib import Path
import json,re,html
root=Path(__file__).resolve().parents[2]
p=root/'.build/pictorial/browser-qa-dom.txt'
s=p.read_text(encoding='utf8',errors='replace')
m=re.search(r'data-qa-result="([^"]+)"',s)
if not m:
    print(json.dumps({'qa_marker_missing':True,'tail':s[-1500:]},ensure_ascii=True,indent=2))
    raise SystemExit(1)
checks=json.loads(html.unescape(m[1]))
assert all(item['passed'] for item in checks),checks
report={'browser':'Chrome headless','checks':checks,'passed':True}
(root/'.build/pictorial/browser-qa-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=True,indent=2))
