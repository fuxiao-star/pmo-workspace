"""Build public assets; optionally export a consistent private migration snapshot."""
import argparse
import datetime
import hashlib
import json
import secrets
import shutil
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--export', action='store_true')
args = parser.parse_args()
public = root / 'cloud' / 'public'
public.mkdir(exist_ok=True)
for source in (root / 'frontend').iterdir():
    if source.is_file() and source.name not in ('receiver.json', 'receiver.example.json'):
        text = source.read_text(encoding='utf-8')
        if source.name == 'submit.js':
            text = text.replace('PMO-Rechner', 'PMO-Cloud').replace('PMO computer', 'PMO cloud database').replace('PMO 电脑', 'PMO 云端数据库').replace('该电脑的数据库', '云端数据库')
        (public / source.name).write_text(text, encoding='utf-8')
(public / 'receiver.json').write_text('{"endpoint":""}', encoding='utf-8')
print('Prepared cloud form assets (no credentials or private data).')
if args.export:
    private = root / 'data' / 'cloud-migration'
    private.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    snapshot = private / ('snapshot-' + stamp + '.sqlite3')
    live = sqlite3.connect(root / 'data' / 'pmo.sqlite3')
    copy = sqlite3.connect(snapshot)
    live.backup(copy)
    live.close()
    copy.row_factory = sqlite3.Row
    def literal(v):
        return 'NULL' if v is None else str(v) if isinstance(v, (int, float)) else "'" + str(v).replace("'", "''") + "'"
    statements = []
    counts = {}
    for table in ('groups', 'reports', 'team_members'):
        rows = copy.execute('SELECT * FROM ' + table).fetchall()
        counts[table] = len(rows)
        for row in rows:
            columns = list(row.keys())
            statements.append('INSERT INTO ' + table + '(' + ','.join(columns) + ') VALUES(' + ','.join(literal(row[k]) for k in columns) + ');')
    copy.close()
    # Never copy live sessions. A separate owner credential does not broaden a member's role.
    owner_code = secrets.token_hex(32)
    owner_hash = hashlib.sha256(owner_code.encode()).hexdigest()
    statements.append("INSERT INTO team_members(name,code_hash,created_at,role) VALUES('项目负责人'," + literal(owner_hash) + ',' + literal(datetime.datetime.now(datetime.timezone.utc).isoformat()) + ",'owner');")
    (private / 'import.sql').write_text('\n'.join(statements), encoding='utf-8')
    (private / 'owner-access.txt').write_text('PMO 云端负责人访问码（请勿上传 GitHub 或公开分享）\n' + owner_code + '\n', encoding='utf-8')
    (private / 'manifest.json').write_text(json.dumps({'snapshot': str(snapshot), 'counts': counts, 'ownerCodeFile': 'owner-access.txt'}, ensure_ascii=False), encoding='utf-8')
    print('Private consistent snapshot and import prepared under data/cloud-migration; counts:', counts)
