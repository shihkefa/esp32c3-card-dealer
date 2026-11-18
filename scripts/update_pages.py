"""Sync the current assembly steps, offline manual and P35 guide to GitHub Pages."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--version', default='V1.0.0')
args = parser.parse_args()
if not re.fullmatch(r'V\d+\.\d+\.\d+', args.version):
    parser.error('Version must use V1.0.0 format.')
root = Path(__file__).resolve().parents[1]
release = root / args.version
source = release / 'manual' / f'發牌機_組裝說明書_{args.version}.html'
html = source.read_bytes()
text = html.decode('utf8')
assert 'manual-data' in text and 'Manual3D' in text, 'Build the complete 3D manual first.'
assert '__MANUAL_DATA__' not in text, 'The manual still contains a build placeholder.'
assert not re.search(r'<(?:script|img|link)\b[^>]*(?:src|href)=["\']https?://', text, re.I)
steps_file = release / 'source/manual/assembly_steps.json'
steps = json.loads(steps_file.read_text(encoding='utf-8'))['steps']
block = re.search(r'<script id="manual-data" type="application/json">(.*?)</script>', text, re.S)
data = json.loads(block[1])
assert [s['id'] for s in steps] == [s['id'] for s in data['steps']]
if data['steps'] != steps:
    data['steps'] = steps
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', r'\u003c')
    html = (text[:block.start(1)] + encoded + text[block.end(1):]).encode('utf-8')
    source.write_bytes(html)
destination = root / 'docs'
destination.mkdir(exist_ok=True)
shutil.copyfile(source, destination / 'index.html')
guide = release / 'manual' / 'P35_按鍵洞洞板裝配說明.html'
shutil.copyfile(guide, destination / guide.name)
image_dir = destination / 'assets'
image_dir.mkdir(exist_ok=True)
for image in (release / 'manual/assets').glob('p35-*.png'):
    shutil.copyfile(image, image_dir / image.name)
shutil.copyfile(release / 'manual/vendor/THREE_LICENSE.txt', destination / 'THREE_LICENSE.txt')
(destination / '.nojekyll').write_bytes(b'')
assert (destination / 'index.html').read_bytes() == html
print(json.dumps({'version': args.version, 'bytes': len(html),
                  'sha256': hashlib.sha256(html).hexdigest(),
                  'pages_source': 'main:/docs'}, ensure_ascii=False, indent=2))
