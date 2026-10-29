"""Local-only SQLite storage. Public listener accepts authenticated submissions only.
The separate admin listener is never exposed by the tunnel.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from http.cookies import SimpleCookie

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('PMO_DATA_DIR', ROOT / 'data'))
ASSETS = ROOT / 'frontend'
if not ASSETS.is_dir(): ASSETS = ROOT.parent / 'sites' / 'pmo-report-template' / 'dist'
SITE = 'https://pmo-team-report-template.palevenus33.chatgpt.site'
PUBLIC_PORT = int(os.environ.get('PMO_PORT', '8765'))
ADMIN_PORT = int(os.environ.get('PMO_ADMIN_PORT', '8766'))
FIELDS = ('group project contact email date period phase status results milestone deadline milestoneStatus budget cost plannedHours hours deviations risks support next notes').split()
REQUIRED = ('group project contact email date period phase status').split()
ADMIN_TOKEN = secrets.token_urlsafe(32)
FAILED = {}
LOCK = threading.Lock()

@contextmanager
def connect():
    db = sqlite3.connect(DATA / 'pmo.sqlite3', timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()

def initialize():
    DATA.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS groups (
          id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, code_hash TEXT UNIQUE NOT NULL,
          active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES groups(id),
          submission_key TEXT NOT NULL, report_date TEXT NOT NULL, period TEXT NOT NULL,
          project TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL,
          created_at TEXT NOT NULL, UNIQUE(group_id, submission_key));
        CREATE TABLE IF NOT EXISTS team_members (
          id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, code_hash TEXT UNIQUE NOT NULL,
          active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS team_sessions (
          token_hash TEXT PRIMARY KEY, member_id INTEGER NOT NULL REFERENCES team_members(id),
          csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
        ''')
        if 'project_kind' not in {r['name'] for r in db.execute('PRAGMA table_info(groups)')}:
            db.execute("ALTER TABLE groups ADD COLUMN project_kind TEXT NOT NULL DEFAULT 'service'")

def digest(code):
    return hashlib.sha256(code.encode('utf-8')).hexdigest()

def create_group(name):
    code = secrets.token_urlsafe(18)
    with connect() as db:
        db.execute('INSERT INTO groups(name,code_hash,created_at) VALUES(?,?,?)', (name,digest(code),datetime.now(timezone.utc).isoformat()))
    return code

def validate(data):
    if not isinstance(data, dict) or any(k not in FIELDS for k in data):
        raise ValueError('invalid_data')
    if any(not isinstance(v,str) or len(v)>10000 for v in data.values()):
        raise ValueError('invalid_data')
    if any(not data.get(k,'').strip() for k in REQUIRED):
        raise ValueError('required_fields')
    if any(len(data.get(k,''))>300 for k in REQUIRED):
        raise ValueError('invalid_data')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', data['email']):
        raise ValueError('invalid_email')
    date.fromisoformat(data['date'])
    if data.get('deadline'): date.fromisoformat(data['deadline'])
    if data['status'] not in ('green','yellow','red') or data['phase'] not in ('Idee','Planung','Konzept','Prototyp','Abschluss'):
        raise ValueError('invalid_status')
    if data.get('milestoneStatus','') not in ('','Offen','In Bearbeitung','Erreicht','Verschoben'):
        raise ValueError('invalid_status')
    import math
    for field in ('budget','cost','plannedHours','hours'):
        if data.get(field):
            n=float(data[field])
            if not math.isfinite(n) or n<0 or n>1e12: raise ValueError('invalid_number')
    return {k:data.get(k,'') for k in FIELDS}

class Server(ThreadingHTTPServer):
    daemon_threads = True

class Handler(BaseHTTPRequestHandler):
    server_version = 'PMO'
    def log_message(self, fmt, *args):
        # Avoid storing names, access codes, report bodies, or admin session tokens in logs.
        pass
    def setup(self):
        super().setup()
        self.connection.settimeout(20)
    def send(self, status, value, content_type='application/json; charset=utf-8', extra_headers=()):
        body = json.dumps(value, ensure_ascii=False).encode() if content_type.startswith('application/json') else value.encode('utf-8') if isinstance(value,str) else value
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY')
        for name,value in extra_headers: self.send_header(name,value)
        origin=self.headers.get('Origin','')
        if origin==SITE:
            self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Vary','Origin')
        self.end_headers()
        self.wfile.write(body)
    def read_json(self):
        if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError('content_type')
        n=int(self.headers.get('Content-Length','0'))
        if n<1 or n>131072: raise ValueError('payload_size')
        return json.loads(self.rfile.read(n))
    def do_OPTIONS(self):
        if self.headers.get('Origin')!=SITE: return self.send(403,{'error':'origin'})
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin',SITE)
        self.send_header('Access-Control-Allow-Methods','POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type, X-PMO-Code')
        self.send_header('Vary','Origin')
        self.end_headers()
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/health': return self.send(200,{'ok':True,'service':'pmo-local'})
        if path=='/receiver.json': return self.send(200,{'endpoint':''})
        files={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/i18n.js':'i18n.js','/style.css':'style.css','/submit.js':'submit.js'}
        if path not in files: return self.send(404,{'error':'not_found'})
        target=ASSETS/files[path]
        if not target.is_file(): return self.send(404,{'error':'not_found'})
        mime={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8'}[target.suffix]
        self.send(200,target.read_bytes(),mime)
    def do_POST(self):
        if urlparse(self.path).path!='/api/reports': return self.send(404,{'error':'not_found'})
        origin=self.headers.get('Origin','')
        host=self.headers.get('Host','')
        if origin and origin not in (SITE,'https://'+host,'http://'+host): return self.send(403,{'error':'origin'})
        code=self.headers.get('X-PMO-Code','')
        ip=self.headers.get('CF-Connecting-IP',self.client_address[0])[:100]
        now=time.monotonic()
        with LOCK:
            # Bounded, per-address failed-auth tracking; successful submissions do not consume it.
            if len(FAILED)>2000:
                for k in list(FAILED):
                    if now-FAILED[k][0]>600: del FAILED[k]
            start,count=FAILED.get(ip,(now,0))
            if now-start>600: start,count=now,0
            if count>=20: return self.send(429,{'error':'rate_limit'})
        with connect() as db:
            group=db.execute('SELECT * FROM groups WHERE code_hash=? AND active=1',(digest(code),)).fetchone() if 10<=len(code)<=100 else None
        if not group:
            with LOCK: FAILED[ip]=(start,count+1)
            return self.send(401,{'error':'invalid_code'})
        try:
            body=self.read_json()
            if not isinstance(body,dict): raise ValueError()
            data=validate(body.get('data'))
            request_id=body.get('submissionId','')
            if not isinstance(request_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}',request_id): raise ValueError()
            report_id=str(uuid.uuid4())
            created=datetime.now(timezone.utc).isoformat()
            with connect() as db:
                existing=db.execute('SELECT id,created_at FROM reports WHERE group_id=? AND submission_key=?',(group['id'],request_id)).fetchone()
                if existing: return self.send(200,{'ok':True,'id':existing['id'],'receivedAt':existing['created_at'],'duplicate':True})
                db.execute('INSERT INTO reports VALUES(?,?,?,?,?,?,?,?,?)',(report_id,group['id'],request_id,data['date'],data['period'],data['project'],data['status'],json.dumps(data,ensure_ascii=False),created))
            self.send(201,{'ok':True,'id':report_id,'receivedAt':created})
        except (ValueError,TypeError,OverflowError): self.send(400,{'error':'invalid_data'})
        except sqlite3.IntegrityError:
            with connect() as db:
                row=db.execute('SELECT id,created_at FROM reports WHERE group_id=? AND submission_key=?',(group['id'],request_id)).fetchone()
            if row: self.send(200,{'ok':True,'id':row['id'],'receivedAt':row['created_at'],'duplicate':True})
            else: self.send(409,{'error':'conflict'})
        except (sqlite3.Error,OSError): self.send(503,{'error':'storage_unavailable'})

class Admin(Handler):
    def local_host(self):
        return self.headers.get('Host','') in (f'127.0.0.1:{ADMIN_PORT}',f'localhost:{ADMIN_PORT}')
    def authenticated(self):
        # Browser CSRF protection and a secret held only in the local page.
        return self.local_host() and hmac.compare_digest(self.headers.get('X-PMO-Admin',''),ADMIN_TOKEN)
    def do_OPTIONS(self): self.send(403,{'error':'forbidden'})
    def do_GET(self):
        if not self.local_host(): return self.send(403,{'error':'forbidden'})
        path=urlparse(self.path).path
        if path=='/':
            html=admin_page(ADMIN_TOKEN)
            return self.send(200,html,'text/html; charset=utf-8')
        if not self.authenticated(): return self.send(403,{'error':'forbidden'})
        if path=='/api/overview':
            with connect() as db:
                groups=[dict(r) for r in db.execute('SELECT id,name,active,created_at,project_kind FROM groups ORDER BY id')]
                reports=[dict(r) for r in db.execute('SELECT r.id,g.name as registered_group,r.created_at,r.payload FROM reports r JOIN groups g ON g.id=r.group_id ORDER BY r.created_at DESC LIMIT 500')]
                count=db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
                members=[dict(r) for r in db.execute('SELECT id,name,active,created_at FROM team_members ORDER BY id')]
            for r in reports: r['data']=json.loads(r.pop('payload'))
            state={}
            try: state=json.loads((DATA/'connection.json').read_text())
            except (OSError,ValueError): pass
            return self.send(200,{'groups':groups,'reports':reports,'total':count,'teamMembers':members,'database':'服务端共享 SQLite 数据库' if getattr(self,'remote_team',False) else str(DATA/'pmo.sqlite3'),'connection':state})
        self.send(404,{'error':'not_found'})
    def do_POST(self):
        if not self.authenticated(): return self.send(403,{'error':'forbidden'})
        try:
            body=self.read_json()
            if not isinstance(body,dict): raise ValueError()
            if urlparse(self.path).path=='/api/groups/category':
                if body.get('kind') not in ('service','pmo'): raise ValueError()
                with connect() as db:
                    result=db.execute('UPDATE groups SET project_kind=? WHERE id=?',(body['kind'],int(body['id'])))
                    if result.rowcount!=1: return self.send(404,{'error':'group_not_found'})
                return self.send(200,{'ok':True})
            if urlparse(self.path).path in ('/api/team/members','/api/team/members/disable','/api/team/members/enable','/api/team/members/reset-code'):
                if getattr(self,'remote_team',False): return self.send(403,{'error':'local_owner_only'})
                action=urlparse(self.path).path
                code=secrets.token_urlsafe(32)
                with connect() as db:
                    if action=='/api/team/members':
                        name=body.get('name','').strip()
                        if not name or len(name)>100: raise ValueError()
                        db.execute('INSERT INTO team_members(name,code_hash,created_at) VALUES(?,?,?)',(name,digest(code),datetime.now(timezone.utc).isoformat()))
                    else:
                        member=db.execute('SELECT id,name FROM team_members WHERE id=?',(int(body['id']),)).fetchone()
                        if not member: return self.send(404,{'error':'member_not_found'})
                        name=member['name']
                        if action.endswith('/reset-code'):
                            db.execute('UPDATE team_members SET code_hash=? WHERE id=?',(digest(code),member['id']))
                        else:
                            db.execute('UPDATE team_members SET active=? WHERE id=?',(int(action.endswith('/enable')),member['id']))
                        db.execute('DELETE FROM team_sessions WHERE member_id=?',(member['id'],))
                if action in ('/api/team/members','/api/team/members/reset-code'):
                    return self.send(200,{'ok':True,'name':name,'code':code})
                return self.send(200,{'ok':True})
            if urlparse(self.path).path=='/api/groups':
                name=body.get('name','').strip()
                if not name or len(name)>100: raise ValueError()
                code=create_group(name)
                return self.send(201,{'name':name,'code':code})
            action=urlparse(self.path).path
            if action in ('/api/groups/disable','/api/groups/enable','/api/groups/reset-code'):
                group_id=int(body['id'])
                with connect() as db:
                    group=db.execute('SELECT id,name,active FROM groups WHERE id=?',(group_id,)).fetchone()
                    if not group: return self.send(404,{'error':'group_not_found'})
                    if action=='/api/groups/reset-code':
                        code=secrets.token_urlsafe(18)
                        db.execute('UPDATE groups SET code_hash=? WHERE id=?',(digest(code),group_id))
                    else:
                        db.execute('UPDATE groups SET active=? WHERE id=?',(1 if action.endswith('/enable') else 0,group_id))
                if action=='/api/groups/reset-code':
                    return self.send(200,{'ok':True,'name':group['name'],'code':code,'active':group['active']})
                return self.send(200,{'ok':True})
            self.send(404,{'error':'not_found'})
        except (ValueError,TypeError,KeyError): self.send(400,{'error':'invalid_data'})
        except sqlite3.IntegrityError: self.send(409,{'error':'duplicate_group'})

def admin_page(csrf,prefix='',remote=False):
    return (ROOT/'admin.html').read_text(encoding='utf-8').replace('__ADMIN_TOKEN__',csrf).replace('__API_PREFIX__',prefix).replace('__TEAM_MODE__','true' if remote else 'false')

class Public(Handler):
    remote_team=True
    def team_session(self):
        cookie=SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: return None
        raw=cookie.get('pmo_team')
        if not raw or len(raw.value)>100:return None
        with connect() as db:
            row=db.execute('SELECT s.csrf,s.member_id,m.name FROM team_sessions s JOIN team_members m ON m.id=s.member_id WHERE s.token_hash=? AND s.expires_at>? AND m.active=1',(digest(raw.value),int(time.time()))).fetchone()
        return dict(row) if row else None
    def local_host(self): return self.team_session() is not None
    def authenticated(self):
        session=self.team_session()
        return session is not None and hmac.compare_digest(self.headers.get('X-PMO-Admin',''),session['csrf'])
    def origin_allowed(self):
        origin=self.headers.get('Origin','')
        host=self.headers.get('Host','')
        return not origin or origin in ('https://'+host,'http://'+host)
    def do_GET(self):
        path=urlparse(self.path).path
        if path in ('/team','/team/'):
            session=self.team_session()
            if session:return self.send(200,admin_page(session['csrf'],'/team',True),'text/html; charset=utf-8')
            return self.send(200,(ROOT/'team-login.html').read_text(encoding='utf-8'),'text/html; charset=utf-8')
        if path.startswith('/team/api/'):
            if not self.authenticated():return self.send(401,{'error':'team_login_required'})
            self.path=path.removeprefix('/team')
            return Admin.do_GET(self)
        return super().do_GET()
    def do_POST(self):
        path=urlparse(self.path).path
        if path=='/team/login':
            if not self.origin_allowed():return self.send(403,{'error':'origin'})
            ip='team:'+self.headers.get('CF-Connecting-IP',self.client_address[0])[:100]
            now=time.monotonic()
            with LOCK:
                start,count=FAILED.get(ip,(now,0))
                if now-start>600:start,count=now,0
                if count>=10:return self.send(429,{'error':'rate_limit'})
            try:
                body=self.read_json();code=body.get('code','')
                if not isinstance(code,str) or not 20<=len(code)<=100:raise ValueError()
                with connect() as db:
                    member=db.execute('SELECT id FROM team_members WHERE code_hash=? AND active=1',(digest(code),)).fetchone()
                    if member:
                        session=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
                        db.execute('DELETE FROM team_sessions WHERE expires_at<?',(int(time.time()),))
                        db.execute('INSERT INTO team_sessions VALUES(?,?,?,?)',(digest(session),member['id'],csrf,int(time.time())+28800))
                if member:
                    return self.send(200,{'ok':True},extra_headers=[('Set-Cookie','pmo_team='+session+'; Path=/team; HttpOnly; Secure; SameSite=Strict; Max-Age=28800')])
            except (ValueError,TypeError,AttributeError):pass
            with LOCK:FAILED[ip]=(start,count+1)
            return self.send(401,{'error':'invalid_team_code'})
        if path=='/team/logout':
            if not self.authenticated() or not self.origin_allowed():return self.send(403,{'error':'forbidden'})
            cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
            with connect() as db:db.execute('DELETE FROM team_sessions WHERE token_hash=?',(digest(cookie['pmo_team'].value),))
            return self.send(200,{'ok':True},extra_headers=[('Set-Cookie','pmo_team=; Path=/team; HttpOnly; Secure; SameSite=Strict; Max-Age=0')])
        if path.startswith('/team/api/'):
            if not self.authenticated() or not self.origin_allowed():return self.send(403,{'error':'forbidden'})
            self.path=path.removeprefix('/team')
            return Admin.do_POST(self)
        return super().do_POST()

def start():
    initialize()
    public=Server(('127.0.0.1',PUBLIC_PORT),Public)
    admin=Server(('127.0.0.1',ADMIN_PORT),Admin)
    threading.Thread(target=public.serve_forever,daemon=True).start()
    threading.Thread(target=admin.serve_forever,daemon=True).start()
    return public,admin

if __name__=='__main__':
    start()
    print(f'PMO receiver: http://127.0.0.1:{PUBLIC_PORT}; admin: http://127.0.0.1:{ADMIN_PORT}',flush=True)
    try: threading.Event().wait()
    except KeyboardInterrupt: pass
