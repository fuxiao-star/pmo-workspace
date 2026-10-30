"""Integration checks against an isolated local Workers/D1 database, never production."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

root = Path(__file__).resolve().parent
node = os.environ.get('PMO_NODE', 'node')
tool = [node, str(root / 'node_modules/wrangler/bin/wrangler.js')]
testdir = root / '.wrangler' / ('test-' + uuid.uuid4().hex)
testdir.mkdir(parents=True)
persist = str(testdir / 'persist')
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
base = 'http://127.0.0.1:' + str(port)
def command(*args):
    p = subprocess.run(tool + list(args), cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError(p.stdout + p.stderr)
command('d1','execute','DB','--local','--persist-to',persist,'--file',str(root/'migrations/0001_initial.sql'))
owner, member = 'test-owner-' + uuid.uuid4().hex, 'test-member-' + uuid.uuid4().hex
seed = testdir/'seed.sql'
seed.write_text("INSERT INTO team_members(name,code_hash,created_at,role) VALUES('owner','" + hashlib.sha256(owner.encode()).hexdigest() + "','2026-10-30','owner'),('member','" + hashlib.sha256(member.encode()).hexdigest() + "','2026-10-30','member');")
command('d1','execute','DB','--local','--persist-to',persist,'--file',str(seed))
log = open(testdir/'dev.log','w',encoding='utf-8')
process = subprocess.Popen(tool+['dev','--ip','127.0.0.1','--port',str(port),'--persist-to',persist],cwd=root,stdout=log,stderr=log)
def request(path, data=None, headers=None, method=None):
    h = dict(headers or {})
    if data is not None:h['Content-Type']='application/json'
    req=urllib.request.Request(base+path,json.dumps(data).encode() if data is not None else None,h,method=method)
    try:r=urllib.request.urlopen(req,timeout=20)
    except urllib.error.HTTPError as e:r=e
    raw=r.read().decode()
    return r.status,dict(r.headers),json.loads(raw) if raw and r.headers.get('Content-Type','').startswith('application/json') else raw
def login(c):
    status,h,_=request('/team/login',{'code':c},{'Origin':base});assert status==200
    cookie=h['Set-Cookie'].split(';')[0]
    assert 'HttpOnly' in h['Set-Cookie'] and 'Secure' in h['Set-Cookie'] and 'SameSite=Strict' in h['Set-Cookie']
    status,_,html=request('/team',headers={'Cookie':cookie});assert status==200
    csrf=re.search("const token='([^']+)'",html).group(1)
    return {'Cookie':cookie,'X-PMO-Admin':csrf,'Origin':base},html
try:
    for _ in range(80):
        if process.poll() is not None:raise RuntimeError((testdir/'dev.log').read_text())
        try:
            if request('/health')[0]==200:break
        except OSError:pass
        time.sleep(.25)
    else:raise RuntimeError('Local Worker did not start')
    assert request('/team/api/overview')[0]==401
    assert request('/admin.html')[0]==404
    assert request('/team/login',{'code':'wrong'})[0]==401
    own,html=login(owner);other,memberhtml=login(member)
    assert 'const teamMode=false' in html and 'const teamMode=true' in memberhtml
    assert 'trycloudflare\\.com$' not in html
    assert request('/team/api/overview',headers={'Cookie':own['Cookie']})[0]==403
    assert request('/team/api/groups',{'name':'x'},{**own,'Origin':'https://evil.example'})[0]==403
    status,_,g=request('/team/api/groups',{'name':'Integration group'},own);assert status==201
    groupcode=g['code']
    overview=request('/team/api/overview',headers=own)[2];gid=overview['groups'][0]['id']
    payload={'submissionId':uuid.uuid4().hex,'data':{'group':'Integration group','project':'Cloud test','contact':'Tester','email':'test@example.com','date':'2026-10-30','period':'W44','phase':'Konzept','status':'green'}}
    public={'X-PMO-Code':groupcode,'Origin':'https://pmo-team-report-template.palevenus33.chatgpt.site'}
    status,headers,receipt=request('/api/reports',payload,public);assert status==201 and receipt['ok']
    assert headers['Access-Control-Allow-Origin']==public['Origin']
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        retries=list(pool.map(lambda _:request('/api/reports',payload,public),range(4)))
    assert all(r[0]==200 and r[2]['id']==receipt['id'] for r in retries)
    assert request('/team/api/overview',headers=other)[2]['total']==1
    bad=json.loads(json.dumps(payload));bad['data']['date']='2026-02-30'
    assert request('/api/reports',bad,public)[0]==400
    bad['data']['date']='2026-10-30';bad['data']['hours']='NaN'
    assert request('/api/reports',bad,public)[0]==400
    assert request('/api/reports',payload,{**public,'Origin':'https://evil.example'})[0]==403
    assert request('/api/reports',payload,{'X-PMO-Code':'wrong'})[0]==401
    assert request('/api/reports',headers={'Origin':public['Origin']},method='OPTIONS')[0]==204
    assert request('/api/reports',headers={'Origin':'https://evil.example'},method='OPTIONS')[0]==403
    assert request('/team/api/groups/category',{'id':gid,'kind':'pmo'},other)[0]==200
    assert request('/team/api/overview',headers=own)[2]['groups'][0]['project_kind']=='pmo'
    assert request('/team/api/groups/disable',{'id':gid},own)[0]==200
    assert request('/api/reports',payload,public)[0]==401
    reset=request('/team/api/groups/reset-code',{'id':gid},own)[2]
    assert reset['active']==0
    assert request('/api/reports',payload,{**public,'X-PMO-Code':reset['code']})[0]==401
    assert request('/team/api/groups/enable',{'id':gid},own)[0]==200
    assert request('/api/reports',payload,public)[0]==401
    assert request('/api/reports',payload,{**public,'X-PMO-Code':reset['code']})[2]['id']==receipt['id']
    assert request('/team/api/team/members',{'name':'unauthorized'},other)[0]==403
    assert request('/team/api/team/members/disable',{'id':1},own)[0]==403
    assert request('/team/api/team/members/disable',{'id':2},own)[0]==200
    assert request('/team/api/overview',headers=other)[0]==401
    assert request('/team/login',{'code':member})[0]==401
    assert request('/team/api/overview',headers=own)[2]['total']==1
    assert request('/team/logout',{},own)[0]==200
    assert request('/team/api/overview',headers=own)[0]==401
    for _ in range(10):request('/team/login',{'code':'wrong'})
    assert request('/team/login',{'code':'wrong'})[0]==429
    print('PASS: isolated Worker/D1 authentication, CSRF, CORS, validation, concurrent idempotency, shared data, code lifecycle, owner protection, session revocation and rate limiting.')
finally:
    process.terminate()
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.kill()
    log.close()
