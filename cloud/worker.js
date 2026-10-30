import adminTemplate from '../admin.html';
import loginTemplate from '../team-login.html';

const SITE='https://pmo-team-report-template.palevenus33.chatgpt.site';
const fields='group project contact email date period phase status results milestone deadline milestoneStatus budget cost plannedHours hours deviations risks support next notes'.split(' ');
const required='group project contact email date period phase status'.split(' ');
const now=()=>Math.floor(Date.now()/1000);
const code=()=>Array.from(crypto.getRandomValues(new Uint8Array(32)),b=>b.toString(16).padStart(2,'0')).join('');
export async function digest(s){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s))),b=>b.toString(16).padStart(2,'0')).join('');}
class Failure extends Error {constructor(status,message){super(message);this.status=status;}}
const fail=(status,message)=>{throw new Failure(status,message)};
function dateValid(s){return /^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s))&&new Date(s).toISOString().slice(0,10)===s;}
export function validate(d){
  if(!d||typeof d!=='object'||Array.isArray(d)||Object.keys(d).some(k=>!fields.includes(k))||Object.values(d).some(v=>typeof v!=='string'||v.length>10000))fail(400,'invalid_data');
  if(required.some(k=>!d[k]?.trim()||d[k].length>300))fail(400,'required_fields');
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email)||!dateValid(d.date)||(d.deadline&&!dateValid(d.deadline)))fail(400,'invalid_data');
  if(!['green','yellow','red'].includes(d.status)||!['Idee','Planung','Konzept','Prototyp','Abschluss'].includes(d.phase)||!['','Offen','In Bearbeitung','Erreicht','Verschoben'].includes(d.milestoneStatus||''))fail(400,'invalid_status');
  for(const k of ['budget','cost','plannedHours','hours'])if(d[k]&&(!Number.isFinite(Number(d[k]))||Number(d[k])<0||Number(d[k])>1e12))fail(400,'invalid_number');
  return Object.fromEntries(fields.map(k=>[k,d[k]||'']));
}
async function body(r){
  if(r.headers.get('Content-Type')?.split(';')[0]!=='application/json')fail(400,'content_type');
  if(Number(r.headers.get('Content-Length'))>131072)fail(413,'payload_size');
  const reader=r.body?.getReader();if(!reader)fail(400,'invalid_data');let n=0,parts=[];
  for(;;){const {done,value}=await reader.read();if(done)break;n+=value.length;if(n>131072){await reader.cancel();fail(413,'payload_size');}parts.push(value);}
  try{const bytes=new Uint8Array(n);let i=0;for(const p of parts){bytes.set(p,i);i+=p.length;}const d=JSON.parse(new TextDecoder().decode(bytes));if(!d||typeof d!=='object'||Array.isArray(d))fail(400,'invalid_data');return d;}catch{fail(400,'invalid_data');}
}
function send(r,status,value,type='application/json; charset=utf-8',extra={}){
  const headers={'Content-Type':type,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',...extra};
  if(r.headers.get('Origin')===SITE){headers['Access-Control-Allow-Origin']=SITE;headers.Vary='Origin';}
  return new Response(status===204?null:type.startsWith('application/json')?JSON.stringify(value):value,{status,headers});
}
const json=(r,value,status=200,extra={})=>send(r,status,value,'application/json; charset=utf-8',extra);
function origin(r,publicRoute=false){const o=r.headers.get('Origin');if(o&&o!==new URL(r.url).origin&&!(publicRoute&&o===SITE))fail(403,'origin');}
const cookie=value=>'pmo_team='+value+'; Path=/team; HttpOnly; Secure; SameSite=Strict; Max-Age='+(value?'28800':'0');
const run=(env,sql,...params)=>env.DB.prepare(sql).bind(...params).run();
const first=(env,sql,...params)=>env.DB.prepare(sql).bind(...params).first();
const all=async(env,sql,...params)=>(await env.DB.prepare(sql).bind(...params).all()).results;
async function session(r,env){
  const raw=r.headers.get('Cookie')?.match(/(?:^|;\s*)pmo_team=([a-f0-9]{64})(?:;|$)/)?.[1];if(!raw)return null;
  return first(env,'SELECT s.csrf,s.member_id,m.name,m.role FROM team_sessions s JOIN team_members m ON m.id=s.member_id WHERE s.token_hash=? AND s.expires_at>? AND m.active=1',await digest(raw),now());
}
async function guard(r,env){const s=await session(r,env);if(!s)fail(401,'team_login_required');if(r.headers.get('X-PMO-Admin')!==s.csrf)fail(403,'forbidden');origin(r);return s;}
async function rateKey(r,scope){return digest(scope+':'+(r.headers.get('CF-Connecting-IP')||'local'));}
async function checkRate(env,key,limit){const row=await first(env,'SELECT attempts FROM auth_failures WHERE key=? AND started_at>?',key,now()-600);if(row?.attempts>=limit)fail(429,'rate_limit');}
async function failed(env,key){await run(env,'INSERT INTO auth_failures(key,started_at,attempts) VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET started_at=CASE WHEN started_at<? THEN excluded.started_at ELSE started_at END, attempts=CASE WHEN started_at<? THEN 1 ELSE attempts+1 END',key,now(),now()-600,now()-600);await run(env,'DELETE FROM auth_failures WHERE started_at<?',now()-600);}
function cloudAdmin(csrf,owner){
  return adminTemplate.replace('__ADMIN_TOKEN__',csrf).replace('__API_PREFIX__','/team').replace('__TEAM_MODE__',owner?'false':'true')
    .replaceAll('管理页仅供本机使用。','管理页仅供已登录的团队成员使用。')
    .replaceAll('临时隧道重启后地址会变化。电脑、网络和接收服务需要保持运行。','云端固定入口，不依赖个人电脑开机。')
    .replaceAll('本机数据','云端数据').replaceAll('本机 SQLite 数据库','云端 D1 数据库')
    .replaceAll('备份前请先关闭接收程序，再复制完整的 data 文件夹。','正式数据保存在云端 D1；负责人可使用部署工具导出备份。')
    .replaceAll('这台电脑上的周报','云端的周报').replaceAll('电脑与接收服务需要在线。','电脑关机后仍可提交和查看。')
    .replaceAll('本机负责人','项目负责人').replaceAll('本机接收服务正在运行','云端服务可访问')
    .replace('/^https:\\/\\/[a-z0-9-]+\\.trycloudflare\\.com$/','/^https:\\/\\/[a-z0-9.-]+$/')
    .replace('</body>',owner?'<button style="position:fixed;right:20px;bottom:12px" id="cloudLogout">退出登录</button><script>document.querySelector("#cloudLogout").onclick=async()=>{await api("/logout",{});location.href="/team"};</script></body>':'</body>');
}
async function submit(r,env){
  origin(r,true);const key=await rateKey(r,'submit');await checkRate(env,key,20);
  const c=r.headers.get('X-PMO-Code')||'';
  const g=c.length>=10&&c.length<=100?await first(env,'SELECT id FROM groups WHERE code_hash=? AND active=1',await digest(c)):null;
  if(!g){await failed(env,key);fail(401,'invalid_code');}
  const b=await body(r),d=validate(b.data),id=b.submissionId;
  if(typeof id!=='string'||!/^[a-zA-Z0-9_-]{16,100}$/.test(id))fail(400,'invalid_data');
  const reportId=crypto.randomUUID(),created=new Date().toISOString();
  const inserted=await run(env,'INSERT INTO reports(id,group_id,submission_key,report_date,period,project,status,payload,created_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(group_id,submission_key) DO NOTHING',reportId,g.id,id,d.date,d.period,d.project,d.status,JSON.stringify(d),created);
  const row=await first(env,'SELECT id,created_at FROM reports WHERE group_id=? AND submission_key=?',g.id,id);
  return json(r,{ok:true,id:row.id,receivedAt:row.created_at,duplicate:inserted.meta.changes===0},inserted.meta.changes?201:200);
}
async function admin(r,env,path){
  const s=await guard(r,env);
  if(r.method==='GET'&&path==='/api/overview'){
    const [groups,reports,count,members]=await Promise.all([
      all(env,'SELECT id,name,active,created_at,project_kind FROM groups ORDER BY id'),
      all(env,'SELECT r.id,g.name AS registered_group,r.created_at,r.payload FROM reports r JOIN groups g ON g.id=r.group_id ORDER BY r.created_at DESC LIMIT 500'),
      first(env,'SELECT COUNT(*) AS total FROM reports'),
      s.role==='owner'?all(env,'SELECT id,name,active,created_at FROM team_members ORDER BY id'):Promise.resolve([])]);
    for(const r of reports){r.data=JSON.parse(r.payload);delete r.payload;}
    return json(r,{groups,reports,total:count.total,teamMembers:members,database:'云端 Cloudflare D1 数据库',connection:{url:new URL(r.url).origin,mode:'cloud'}});
  }
  if(r.method!=='POST')fail(404,'not_found');const b=await body(r);
  if(path==='/api/groups/category'){
    if(!['service','pmo'].includes(b.kind))fail(400,'invalid_data');
    const res=await run(env,'UPDATE groups SET project_kind=? WHERE id=?',b.kind,Number(b.id));if(!res.meta.changes)fail(404,'group_not_found');return json(r,{ok:true});
  }
  if(path==='/api/groups'){
    const name=typeof b.name==='string'?b.name.trim():'';if(!name||name.length>100)fail(400,'invalid_data');
    const c=code();await run(env,'INSERT INTO groups(name,code_hash,created_at) VALUES(?,?,?)',name,await digest(c),new Date().toISOString());return json(r,{name,code:c},201);
  }
  if(['/api/groups/disable','/api/groups/enable','/api/groups/reset-code'].includes(path)){
    const g=await first(env,'SELECT id,name,active FROM groups WHERE id=?',Number(b.id));if(!g)fail(404,'group_not_found');
    if(path.endsWith('reset-code')){const c=code();await run(env,'UPDATE groups SET code_hash=? WHERE id=?',await digest(c),g.id);return json(r,{ok:true,name:g.name,active:g.active,code:c});}
    await run(env,'UPDATE groups SET active=? WHERE id=?',path.endsWith('/enable')?1:0,g.id);return json(r,{ok:true});
  }
  if(['/api/team/members','/api/team/members/disable','/api/team/members/enable','/api/team/members/reset-code'].includes(path)){
    if(s.role!=='owner')fail(403,'owner_only');const c=code();
    if(path==='/api/team/members'){
      const name=typeof b.name==='string'?b.name.trim():'';if(!name||name.length>100)fail(400,'invalid_data');
      await run(env,'INSERT INTO team_members(name,code_hash,created_at) VALUES(?,?,?)',name,await digest(c),new Date().toISOString());return json(r,{ok:true,name,code:c});
    }
    const m=await first(env,'SELECT id,name,role FROM team_members WHERE id=?',Number(b.id));if(!m)fail(404,'member_not_found');if(m.role==='owner')fail(403,'owner_protected');
    const update=path.endsWith('reset-code')?env.DB.prepare('UPDATE team_members SET code_hash=? WHERE id=?').bind(await digest(c),m.id):env.DB.prepare('UPDATE team_members SET active=? WHERE id=?').bind(path.endsWith('/enable')?1:0,m.id);
    await env.DB.batch([update,env.DB.prepare('DELETE FROM team_sessions WHERE member_id=?').bind(m.id)]);
    return json(r,path.endsWith('reset-code')?{ok:true,name:m.name,code:c}:{ok:true});
  }
  fail(404,'not_found');
}
export default {async fetch(r,env){try{
  const path=new URL(r.url).pathname;
  if(r.method==='OPTIONS'){
    if(path!=='/api/reports'||r.headers.get('Origin')!==SITE)fail(403,'origin');
    return send(r,204,null,'application/json',{'Access-Control-Allow-Methods':'POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type, X-PMO-Code'});
  }
  if(r.method==='GET'&&path==='/health')return json(r,{ok:true,service:'pmo-cloud'});
  if(r.method==='GET'&&path==='/receiver.json')return json(r,{endpoint:''});
  if(r.method==='POST'&&path==='/api/reports')return await submit(r,env);
  if(r.method==='GET'&&(path==='/team'||path==='/team/')){
    const s=await session(r,env);return send(r,200,s?cloudAdmin(s.csrf,s.role==='owner'):loginTemplate.replaceAll('本机负责人','项目负责人').replaceAll('负责人电脑和接收服务在线','网络与云端服务可访问'),'text/html; charset=utf-8');
  }
  if(r.method==='POST'&&path==='/team/login'){
    origin(r);const key=await rateKey(r,'team');await checkRate(env,key,10);const b=await body(r),c=b.code;
    const m=typeof c==='string'&&c.length>=20&&c.length<=100?await first(env,'SELECT id FROM team_members WHERE code_hash=? AND active=1',await digest(c)):null;
    if(!m){await failed(env,key);fail(401,'invalid_team_code');}
    const token=code(),csrf=code();await env.DB.batch([env.DB.prepare('DELETE FROM team_sessions WHERE expires_at<?').bind(now()),env.DB.prepare('INSERT INTO team_sessions VALUES(?,?,?,?)').bind(await digest(token),m.id,csrf,now()+28800)]);
    return json(r,{ok:true},200,{'Set-Cookie':cookie(token)});
  }
  if(r.method==='POST'&&path==='/team/logout'){
    await guard(r,env);const token=r.headers.get('Cookie').match(/pmo_team=([a-f0-9]{64})/)[1];await run(env,'DELETE FROM team_sessions WHERE token_hash=?',await digest(token));return json(r,{ok:true},200,{'Set-Cookie':cookie('')});
  }
  if(path.startsWith('/team/api/'))return await admin(r,env,path.slice(5));
  if(r.method==='GET'&&['/','/index.html','/app.js','/i18n.js','/submit.js','/style.css'].includes(path))return env.ASSETS.fetch(r);
  fail(404,'not_found');
}catch(e){
  if(e instanceof Failure)return json(r,{error:e.message},e.status);
  if(/UNIQUE constraint failed/.test(String(e)))return json(r,{error:'duplicate_group'},409);
  // Never expose SQL, report contents, credentials or stack traces to clients/logs.
  return json(r,{error:'storage_unavailable'},503);
}}};
