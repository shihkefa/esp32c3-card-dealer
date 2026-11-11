"""Copy a verified standalone assembly manual to the GitHub Pages folder."""
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
destination = root / 'docs'
destination.mkdir(exist_ok=True)
shutil.copyfile(source, destination / 'index.html')
shutil.copyfile(release / 'manual/vendor/THREE_LICENSE.txt', destination / 'THREE_LICENSE.txt')
(destination / '.nojekyll').write_bytes(b'')
assert (destination / 'index.html').read_bytes() == html
print(json.dumps({'version': args.version, 'bytes': len(html),
                  'sha256': hashlib.sha256(html).hexdigest(),
                  'pages_source': 'main:/docs'}, ensure_ascii=False, indent=2))
