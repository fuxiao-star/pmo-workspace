"""Prepare an existing authorized Sites staging checkout; does not deploy."""
import argparse
import json
import shutil
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--destination',required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
destination=Path(args.destination).resolve()
manifest=destination/'.openai'/'hosting.json'
if not manifest.is_file() or not json.loads(manifest.read_text(encoding='utf-8')).get('project_id'):
    raise SystemExit('An existing authorized Sites checkout is required. No Site was created.')
try:url=json.loads((root/'data'/'connection.json').read_text())['url']
except (OSError,KeyError,ValueError):raise SystemExit('No active receiver URL; no files changed.')
if not url.startswith('https://'):raise SystemExit('HTTPS receiver required.')
dist=destination/'dist';dist.mkdir(exist_ok=True)
for source in (root/'frontend').iterdir():
    if source.is_file() and source.name not in ('receiver.json','receiver.example.json'):shutil.copy2(source,dist/source.name)
(dist/'receiver.json').write_text(json.dumps({'endpoint':url}),encoding='utf-8')
print('Prepared frontend files. Follow Sites source/save/deploy workflow to publish.')
