#!/usr/bin/env python3
"""Malaeb MVP: SQLite booking and venue-owner service; Python standard library only."""
import hashlib, hmac, json, os, secrets, sqlite3, time
from datetime import date as Date, datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('MALAEb_DB',ROOT/'malaeb.sqlite3'))
HOST=os.environ.get('MALAEb_HOST','127.0.0.1'); PORT=int(os.environ.get('MALAEb_PORT','8000'))
PLANS={'monthly':15000,'yearly':150000}; DAYS=14
COOKIE_SECURE='; Secure' if os.environ.get('MALAEb_SECURE_COOKIE')=='1' else ''

def connect():
 d=sqlite3.connect(DB); d.row_factory=sqlite3.Row; d.execute('PRAGMA foreign_keys=ON'); return d

def init_db():
 with connect() as d:
  d.executescript('''CREATE TABLE IF NOT EXISTS owners(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,phone TEXT NOT NULL,password TEXT NOT NULL,created_at INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS venues(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL REFERENCES owners(id) ON DELETE CASCADE,name TEXT NOT NULL,city TEXT NOT NULL,area TEXT NOT NULL,address TEXT NOT NULL DEFAULT '',phone TEXT NOT NULL,pitch_types TEXT NOT NULL,price INTEGER NOT NULL DEFAULT 0,description TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1,created_at INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY,venue_id INTEGER NOT NULL REFERENCES venues(id),customer_name TEXT NOT NULL,customer_phone TEXT NOT NULL,pitch_type TEXT NOT NULL,date TEXT NOT NULL,time TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,owner_id INTEGER NOT NULL REFERENCES owners(id) ON DELETE CASCADE,expires_at INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL REFERENCES owners(id) ON DELETE CASCADE,plan TEXT NOT NULL,amount INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',reference TEXT NOT NULL UNIQUE,created_at INTEGER NOT NULL,paid_at INTEGER,expires_at INTEGER);
  CREATE INDEX IF NOT EXISTS booking_slot ON bookings(venue_id,date,time);''')
  columns={row['name'] for row in d.execute('PRAGMA table_info(subscriptions)')}
  if 'expires_at' not in columns: d.execute('ALTER TABLE subscriptions ADD COLUMN expires_at INTEGER')
def clean(v,n=160): return ' '.join(str(v or '').strip().split())[:n]
def password_hash(p,salt=None):
 salt=salt or secrets.token_bytes(16); return salt.hex()+'$'+hashlib.pbkdf2_hmac('sha256',p.encode(),salt,240000).hex()
def password_ok(p,s):
 try:
  salt,digest=s.split('$',1); return hmac.compare_digest(password_hash(p,bytes.fromhex(salt)).split('$',1)[1],digest)
 except (ValueError,TypeError): return False
class App(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
 def log_message(self,fmt,*a): print(self.log_date_time_string(),fmt%a)
 def json_out(self,status,obj,headers=None):
  b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
  for k,v in (headers or {}).items(): self.send_header(k,v)
  self.end_headers(); self.wfile.write(b)
 def body(self):
  try:
   n=int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(n)) if n<=20000 else None
  except (ValueError,json.JSONDecodeError): return None
 def owner(self,d):
  token=next((x.strip().split('=',1)[1] for x in self.headers.get('Cookie','').split(';') if x.strip().startswith('malaeb_session=')),None)
  if not token:return None
  return d.execute('SELECT o.* FROM sessions s JOIN owners o ON o.id=s.owner_id WHERE s.token_hash=? AND s.expires_at>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
 def do_GET(self):
  path=urlparse(self.path).path
  if path.startswith('/api/'):
   with connect() as d:
    if path=='/api/venues':
     rows=d.execute('SELECT id,name,city,area,address,phone,pitch_types,price,description FROM venues WHERE active=1 ORDER BY id DESC').fetchall(); return self.json_out(200,{'venues':[dict(r,pitch_types=json.loads(r['pitch_types'])) for r in rows]})
    if path=='/api/me':
     o=self.owner(d)
     if not o:return self.json_out(200,{'owner':None})
     venues=d.execute('SELECT * FROM venues WHERE owner_id=?',(o['id'],)).fetchall(); sub=d.execute('SELECT * FROM subscriptions WHERE owner_id=? ORDER BY id DESC LIMIT 1',(o['id'],)).fetchone()
     return self.json_out(200,{'owner':{'id':o['id'],'name':o['name'],'email':o['email'],'phone':o['phone']},'venues':[dict(v,pitch_types=json.loads(v['pitch_types'])) for v in venues],'subscription':dict(sub) if sub else None})
    if path=='/api/owner/bookings':
     o=self.owner(d)
     if not o:return self.json_out(401,{'error':'سجل دخولك أولاً.'})
     rows=d.execute('SELECT b.*,v.name venue_name FROM bookings b JOIN venues v ON v.id=b.venue_id WHERE v.owner_id=? ORDER BY b.date DESC,b.time DESC',(o['id'],)).fetchall(); return self.json_out(200,{'bookings':[dict(r) for r in rows]})
   return self.json_out(404,{'error':'المسار غير موجود.'})
  if path=='/': self.path='/index.html'
  return super().do_GET()
 def do_POST(self):
  path=urlparse(self.path).path
  if not path.startswith('/api/'):return self.json_out(404,{'error':'المسار غير موجود.'})
  x=self.body()
  if x is None:return self.json_out(400,{'error':'البيانات غير صالحة.'})
  now=int(time.time())
  with connect() as d:
   if path=='/api/register':
    name,email,phone=clean(x.get('owner_name'),100),clean(x.get('email'),180).lower(),clean(x.get('owner_phone'),30); pw=str(x.get('password') or '')
    keys={'venue_name':120,'city':70,'area':100,'address':200,'venue_phone':30,'description':500}; v={k:clean(x.get(k),n) for k,n in keys.items()}; kinds=x.get('pitch_types',[]); kinds=[k for k in kinds if k in ('5','7')] if isinstance(kinds,list) else []
    try: price=max(0,min(1000000,int(x.get('price') or 0)))
    except (ValueError,TypeError):price=0
    if not name or '@' not in email or len(pw)<8 or not phone or not v['venue_name'] or not v['city'] or not v['area'] or not v['venue_phone'] or not kinds:return self.json_out(400,{'error':'أكمل البيانات المطلوبة. كلمة المرور لازم 8 أحرف على الأقل.'})
    try:
     cur=d.execute('INSERT INTO owners(name,email,phone,password,created_at) VALUES(?,?,?,?,?)',(name,email,phone,password_hash(pw),now)); oid=cur.lastrowid
     d.execute('INSERT INTO venues(owner_id,name,city,area,address,phone,pitch_types,price,description,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(oid,v['venue_name'],v['city'],v['area'],v['address'],v['venue_phone'],json.dumps(kinds),price,v['description'],now))
    except sqlite3.IntegrityError:return self.json_out(409,{'error':'هذا البريد مسجل من قبل.'})
    token=secrets.token_urlsafe(32); d.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),oid,now+DAYS*86400)); return self.json_out(201,{'ok':True},{'Set-Cookie':f'malaeb_session={token}; Path=/; HttpOnly; SameSite=Lax{COOKIE_SECURE}; Max-Age={DAYS*86400}'})
   if path=='/api/login':
    o=d.execute('SELECT * FROM owners WHERE email=?',(clean(x.get('email'),180).lower(),)).fetchone()
    if not o or not password_ok(str(x.get('password') or ''),o['password']):return self.json_out(401,{'error':'البريد أو كلمة المرور غير صحيحة.'})
    token=secrets.token_urlsafe(32); d.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),o['id'],now+DAYS*86400)); return self.json_out(200,{'ok':True},{'Set-Cookie':f'malaeb_session={token}; Path=/; HttpOnly; SameSite=Lax{COOKIE_SECURE}; Max-Age={DAYS*86400}'})
   if path=='/api/logout':
    token=next((z.strip().split('=',1)[1] for z in self.headers.get('Cookie','').split(';') if z.strip().startswith('malaeb_session=')),None)
    if token:d.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    return self.json_out(200,{'ok':True},{'Set-Cookie':f'malaeb_session=; Path=/; HttpOnly; SameSite=Lax{COOKIE_SECURE}; Max-Age=0'})
   if path=='/api/bookings':
    try: venue=d.execute('SELECT * FROM venues WHERE id=? AND active=1',(int(x.get('venue_id')),)).fetchone()
    except (ValueError,TypeError):venue=None
    name,phone,date,clock=clean(x.get('name'),100),clean(x.get('phone'),30),clean(x.get('date'),10),clean(x.get('time'),5); pitch=clean(x.get('pitch_type'),2)
    try:
     match_date=Date.fromisoformat(date); datetime.strptime(clock,'%H:%M')
    except ValueError: return self.json_out(400,{'error':'تاريخ أو وقت الحجز غير صحيح.'})
    if not venue or not name or len(phone)<7 or pitch not in json.loads(venue['pitch_types']) or match_date<Date.today():return self.json_out(400,{'error':'تحقق من بيانات الملعب والاسم والهاتف والموعد.'})
    if d.execute("SELECT 1 FROM bookings WHERE venue_id=? AND date=? AND time=? AND status IN ('pending','confirmed')",(venue['id'],date,clock)).fetchone():return self.json_out(409,{'error':'هذا الموعد عليه طلب. اختار وقتاً آخر.'})
    cur=d.execute('INSERT INTO bookings(venue_id,customer_name,customer_phone,pitch_type,date,time,created_at) VALUES(?,?,?,?,?,?,?)',(venue['id'],name,phone,pitch,date,clock,now)); return self.json_out(201,{'ok':True,'booking_id':cur.lastrowid,'message':'وصل طلبك للملعب. انتظر تأكيده.'})
   if path=='/api/subscriptions':
    o=self.owner(d)
    if not o:return self.json_out(401,{'error':'سجل دخولك أولاً.'})
    plan=x.get('plan')
    if plan not in PLANS:return self.json_out(400,{'error':'الباقة غير متاحة.'})
    active=d.execute("SELECT 1 FROM subscriptions WHERE owner_id=? AND status='active' AND expires_at>?",(o['id'],now)).fetchone()
    if active:return self.json_out(409,{'error':'اشتراكك فعال حالياً.'})
    pending=d.execute("SELECT 1 FROM subscriptions WHERE owner_id=? AND status='pending'",(o['id'],)).fetchone()
    if pending:return self.json_out(409,{'error':'لديك طلب اشتراك بانتظار المراجعة.'})
    ref='MLB-'+secrets.token_hex(5).upper(); d.execute('INSERT INTO subscriptions(owner_id,plan,amount,status,reference,created_at) VALUES(?,?,?,\'pending\',?,?)',(o['id'],plan,PLANS[plan],ref,now)); return self.json_out(201,{'ok':True,'reference':ref,'amount_iqd':PLANS[plan],'message':'سُجل طلب الاشتراك بانتظار مراجعة الدفع من الإدارة.'})
   if path.startswith('/api/owner/bookings/'):
    o=self.owner(d)
    if not o:return self.json_out(401,{'error':'سجل دخولك أولاً.'})
    try:bid=int(path.rsplit('/',1)[1])
    except ValueError:return self.json_out(400,{'error':'رقم الحجز غير صحيح.'})
    status=x.get('status')
    if status not in ('confirmed','rejected','completed'):return self.json_out(400,{'error':'الحالة غير صحيحة.'})
    cur=d.execute('UPDATE bookings SET status=? WHERE id=? AND venue_id IN (SELECT id FROM venues WHERE owner_id=?)',(status,bid,o['id'])); return self.json_out(200 if cur.rowcount else 404,{'ok':bool(cur.rowcount)})
  return self.json_out(404,{'error':'المسار غير موجود.'})
 def do_PUT(self):
  if urlparse(self.path).path!='/api/owner/venue':return self.json_out(404,{'error':'المسار غير موجود.'})
  x=self.body()
  if x is None:return self.json_out(400,{'error':'البيانات غير صالحة.'})
  with connect() as d:
   o=self.owner(d)
   if not o:return self.json_out(401,{'error':'سجل دخولك أولاً.'})
   v=d.execute('SELECT * FROM venues WHERE owner_id=? ORDER BY id LIMIT 1',(o['id'],)).fetchone()
   if not v:return self.json_out(404,{'error':'ماكو ملعب مسجل.'})
   name,city,area,address,phone,desc=[clean(x.get(k),lim) for k,lim in [('name',120),('city',70),('area',100),('address',200),('phone',30),('description',500)]]; kinds=x.get('pitch_types',[]); kinds=[k for k in kinds if k in ('5','7')] if isinstance(kinds,list) else []
   try:price=max(0,min(1000000,int(x.get('price') or 0)))
   except (ValueError,TypeError):price=0
   if not all((name,city,area,phone,kinds)):return self.json_out(400,{'error':'أكمل بيانات الملعب المطلوبة.'})
   d.execute('UPDATE venues SET name=?,city=?,area=?,address=?,phone=?,pitch_types=?,price=?,description=? WHERE id=?',(name,city,area,address,phone,json.dumps(kinds),price,desc,v['id']))
  return self.json_out(200,{'ok':True})
if __name__=='__main__':
 init_db(); print(f'Malaeb MVP: http://{HOST}:{PORT}'); ThreadingHTTPServer((HOST,PORT),App).serve_forever()
