import concurrent.futures
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import server

class TestReceiver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        server.DATA=Path(cls.tmp.name)
        server.initialize()
        cls.code=server.create_group('Testgruppe')
        cls.http=server.Server(('127.0.0.1',0),server.Public)
        cls.url='http://127.0.0.1:'+str(cls.http.server_port)
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()
        cls.admin=server.Server(('127.0.0.1',0),server.Admin)
        server.ADMIN_PORT=cls.admin.server_port
        cls.admin_url='http://127.0.0.1:'+str(cls.admin.server_port)
        threading.Thread(target=cls.admin.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.admin.shutdown();cls.admin.server_close();cls.tmp.cleanup()
    def request(self,path,body=None,code=None,url=None,headers=None):
        hdr={'Content-Type':'application/json',**(headers or {})}
        if code is not None: hdr['X-PMO-Code']=code
        req=urllib.request.Request((url or self.url)+path,data=json.dumps(body).encode() if body is not None else None,headers=hdr)
        try:
            with urllib.request.urlopen(req) as r: return r.status,json.loads(r.read())
        except urllib.error.HTTPError as e: return e.code,json.loads(e.read())
    def report(self,id='test-submission-00001'):
        return {'submissionId':id,'data':{'group':'Testgruppe','project':'测试项目','contact':'Test','email':'test@example.com','date':'2026-10-29','period':'KW 44','phase':'Konzept','status':'green','budget':'1000','cost':'850','results':'<script>example</script>'}}
    def test_submit_and_retry(self):
        body=self.report()
        status,d=self.request('/api/reports',body,self.code)
        self.assertEqual(status,201)
        status,second=self.request('/api/reports',body,self.code)
        self.assertEqual(status,200);self.assertEqual(d['id'],second['id'])
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM reports WHERE submission_key=?',(body['submissionId'],)).fetchone()[0],1)
            data=json.loads(db.execute('SELECT payload FROM reports WHERE id=?',(d['id'],)).fetchone()[0])
            self.assertEqual(data['project'],'测试项目')
    def test_wrong_code(self): self.assertEqual(self.request('/api/reports',self.report(),'incorrect-code')[0],401)
    def test_code_lifecycle(self):
        auth={'X-PMO-Admin':server.ADMIN_TOKEN}
        _,created=self.request('/api/groups',{'name':'Lifecycle test'},url=self.admin_url,headers=auth)
        old_code=created['code']
        with server.connect() as db:
            group_id=db.execute('SELECT id FROM groups WHERE name=?',('Lifecycle test',)).fetchone()[0]
        body=self.report('lifecycle-report-0001')
        self.assertEqual(self.request('/api/reports',body,old_code)[0],201)
        self.assertEqual(self.request('/api/groups/disable',{'id':group_id},url=self.admin_url,headers=auth)[0],200)
        self.assertEqual(self.request('/api/reports',body,old_code)[0],401)
        self.assertEqual(self.request('/api/groups/enable',{'id':group_id},url=self.admin_url,headers=auth)[0],200)
        self.assertEqual(self.request('/api/reports',body,old_code)[0],200)
        self.request('/api/groups/disable',{'id':group_id},url=self.admin_url,headers=auth)
        status,reset=self.request('/api/groups/reset-code',{'id':group_id},url=self.admin_url,headers=auth)
        self.assertEqual(status,200);self.assertEqual(reset['active'],0)
        self.assertEqual(self.request('/api/reports',body,reset['code'])[0],401)
        self.request('/api/groups/enable',{'id':group_id},url=self.admin_url,headers=auth)
        self.assertEqual(self.request('/api/reports',body,old_code)[0],401)
        self.assertEqual(self.request('/api/reports',body,reset['code'])[0],200)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM reports WHERE group_id=?',(group_id,)).fetchone()[0],1)
        self.assertEqual(self.request('/api/groups/enable',{'id':group_id},url=self.admin_url)[0],403)
        self.assertEqual(self.request('/api/groups/enable',{'id':999999},url=self.admin_url,headers=auth)[0],404)
    def test_validation(self):
        body=self.report();body['data']['cost']='NaN'
        self.assertEqual(self.request('/api/reports',body,self.code)[0],400)
        body=self.report();body['data']['date']='2026-99-99'
        self.assertEqual(self.request('/api/reports',body,self.code)[0],400)
    def test_cors_and_no_public_read(self):
        self.assertEqual(self.request('/api/reports',self.report(),self.code,headers={'Origin':'https://attacker.example'})[0],403)
        self.assertEqual(self.request('/api/reports')[0],404)
        self.assertEqual(self.request('/api/overview')[0],404)
        self.assertEqual(self.request('/data/pmo.sqlite3')[0],404)
    def test_admin_authorization(self):
        self.assertEqual(self.request('/api/overview',url=self.admin_url)[0],403)
        self.assertEqual(self.request('/api/overview',url=self.admin_url,headers={'X-PMO-Admin':server.ADMIN_TOKEN})[0],200)
        self.assertEqual(self.request('/api/overview',url=self.admin_url,headers={'X-PMO-Admin':server.ADMIN_TOKEN,'Host':'evil.example'})[0],403)
    def test_concurrent_retry(self):
        body=self.report('concurrent-report-0001')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda _:self.request('/api/reports',body,self.code),range(4)))
        self.assertTrue(all(status in (200,201) for status,_ in responses))
        self.assertEqual(len({r['id'] for _,r in responses}),1)
    def test_shared_team_access(self):
        owner={'X-PMO-Admin':server.ADMIN_TOKEN}
        _,member=self.request('/api/team/members',{'name':'Team integration test'},url=self.admin_url,headers=owner)
        code=member['code']
        self.assertEqual(self.request('/team/api/overview')[0],401)
        self.assertEqual(self.request('/team/api/overview',headers=owner)[0],401)
        self.assertEqual(self.request('/team/login',{'code':code},headers={'Origin':'https://evil.example'})[0],403)
        req=urllib.request.Request(self.url+'/team/login',data=json.dumps({'code':code}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req) as r:
            self.assertTrue(json.load(r)['ok']);cookie_header=r.headers['Set-Cookie']
        self.assertIn('HttpOnly',cookie_header);self.assertIn('Secure',cookie_header);self.assertIn('SameSite=Strict',cookie_header)
        cookie=cookie_header.split(';',1)[0]
        with server.connect() as db:
            session=db.execute('SELECT csrf,member_id FROM team_sessions WHERE token_hash=?',(server.digest(cookie.split('=',1)[1]),)).fetchone()
        auth={'Cookie':cookie,'X-PMO-Admin':session['csrf']}
        self.assertEqual(self.request('/team/api/overview',headers=auth)[0],200)
        self.assertEqual(self.request('/team/api/overview',headers={'Cookie':cookie})[0],401)
        self.assertEqual(self.request('/team/api/groups/enable',{'id':1},headers={'Cookie':cookie})[0],403)
        self.assertEqual(self.request('/team/api/groups/enable',{'id':1},headers={**auth,'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/team/api/team/members',{'name':'Unauthorized invite'},headers=auth)[0],403)
        self.assertEqual(self.request('/team/api/groups/category',{'id':1,'kind':'pmo'},headers=auth)[0],200)
        _,overview=self.request('/api/overview',url=self.admin_url,headers=owner)
        self.assertEqual(next(g for g in overview['groups'] if g['id']==1)['project_kind'],'pmo')
        self.request('/api/team/members/disable',{'id':session['member_id']},url=self.admin_url,headers=owner)
        self.assertEqual(self.request('/team/api/overview',headers=auth)[0],401)
        self.assertEqual(self.request('/team/login',{'code':code})[0],401)

if __name__=='__main__': unittest.main()
