"""One controlled internet round-trip, followed by cleanup of this test's own rows."""
import json
import re
import sqlite3
import urllib.request
import uuid
from pathlib import Path

root=Path(__file__).resolve().parent
connection=json.loads((root/'data'/'connection.json').read_text())
endpoint=connection['url']
admin='http://127.0.0.1:8766'
with urllib.request.urlopen(admin) as r: html=r.read().decode()
token=re.search("const token='([^']+)'",html).group(1)
def request(url,body=None,headers=None,method=None):
    hdr=headers or {}
    if body is not None: hdr={**hdr,'Content-Type':'application/json'}
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=hdr,method=method)
    with urllib.request.urlopen(req,timeout=30) as r: return r.status,dict(r.headers),json.loads(r.read())
name='Connection test '+str(uuid.uuid4())
created=None
try:
    status,_,health=request(endpoint+'/health')
    assert status==200 and health['ok']
    _,_,created=request(admin+'/api/groups',{'name':name},{'X-PMO-Admin':token})
    data={'group':name,'project':'Connection test only','contact':'PMO Test','email':'test@example.com','date':'2026-10-29','period':'TEST','phase':'Konzept','status':'green'}
    headers={'X-PMO-Code':created['code'],'Origin':'https://pmo-team-report-template.palevenus33.chatgpt.site'}
    body={'submissionId':str(uuid.uuid4()),'data':data}
    status,response_headers,receipt=request(endpoint+'/api/reports',body,headers)
    assert status==201 and receipt['ok']
    assert response_headers.get('Access-Control-Allow-Origin')==headers['Origin']
    _,_,again=request(endpoint+'/api/reports',body,headers)
    assert again['id']==receipt['id']
    with sqlite3.connect(root/'data'/'pmo.sqlite3') as db:
        row=db.execute('SELECT payload FROM reports WHERE id=?',(receipt['id'],)).fetchone()
        assert json.loads(row[0])['project']=='Connection test only'
    print('PASS: public HTTPS -> authenticated submission -> local SQLite; retry returned the same receipt; CORS verified.')
finally:
    if created:
        with sqlite3.connect(root/'data'/'pmo.sqlite3') as db:
            row=db.execute('SELECT id FROM groups WHERE name=?',(name,)).fetchone()
            if row:
                db.execute('DELETE FROM reports WHERE group_id=?',(row[0],))
                db.execute('DELETE FROM groups WHERE id=?',(row[0],))
        print('Removed only this run’s generated test group and reports.')
