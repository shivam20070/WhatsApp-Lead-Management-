from flask import Flask, render_template, request, jsonify, session, redirect, send_from_directory
from datetime import datetime, date, timedelta
import sqlite3, re, random, string, os

app = Flask(__name__)
app.secret_key = "bc_secret_v5_2026"
DB = os.path.join(os.path.dirname(__file__), "bc.db")
ADMIN_USER, ADMIN_PASS = "admin", "brain@2026"

def get_db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT, phone TEXT, city TEXT,
        category TEXT, test_name TEXT,
        mode TEXT, franchise_id INTEGER, franchise_name TEXT, franchise_address TEXT,
        slot_id INTEGER, slot_time TEXT, booking_date TEXT,
        amount INTEGER DEFAULT 0, payment_method TEXT,
        status TEXT DEFAULT 'Confirmed', meet_link TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS slots(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_time TEXT, slot_date TEXT,
        is_booked INTEGER DEFAULT 0, booking_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS franchises(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, area TEXT, address TEXT NOT NULL,
        city TEXT, phone TEXT,
        lat REAL DEFAULT 0, lng REAL DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        icon TEXT DEFAULT '📋',
        is_active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS services(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER, category_name TEXT,
        name TEXT NOT NULL, code TEXT,
        description TEXT, icon TEXT DEFAULT '📋',
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY(category_id) REFERENCES categories(id))""")
    conn.commit()
    # Seed default data if empty
    c.execute("SELECT COUNT(*) FROM franchises"); 
    if c.fetchone()[0]==0:
        frs=[("Pune – Kothrud","Kothrud, Pune","302 ABC Tower, Kothrud, Pune 411038","Pune","+91-7234567890",18.5074,73.8077),
             ("Pune – Hadapsar","Hadapsar, Pune","14 Magarpatta Rd, Hadapsar, Pune 411028","Pune","+91-7234567891",18.5090,73.9259),
             ("Mumbai – Andheri","Andheri West, Mumbai","2F Infinity Mall, Andheri W, Mumbai 400058","Mumbai","+91-7234567892",19.1360,72.8296),
             ("Mumbai – Thane","Thane West","Office 5, Viviana Complex, Thane 400601","Mumbai","+91-7234567893",19.2183,72.9781),
             ("Nagpur – Dharampeth","Dharampeth, Nagpur","Saraf Complex, Dharampeth, Nagpur 440010","Nagpur","+91-7234567894",21.1458,79.0882),
             ("Delhi – CP","Connaught Place","Block A, Connaught Place, New Delhi 110001","Delhi","+91-7234567895",28.6315,77.2167)]
        for f in frs:
            c.execute("INSERT INTO franchises(name,area,address,city,phone,lat,lng) VALUES(?,?,?,?,?,?,?)",f)
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0]==0:
        for cat,icon in [("Student","🎓"),("Parent","👨‍👩‍👧"),("Corporate","💼")]:
            c.execute("INSERT INTO categories(name,icon) VALUES(?,?)",(cat,icon))
    c.execute("SELECT COUNT(*) FROM services")
    if c.fetchone()[0]==0:
        svcs=[
            ("Student",1,"DMIT – Dermatoglyphics Multiple Intelligence Test","DMIT","Fingerprint-based intelligence mapping","🧬"),
            ("Student",1,"Psychometric Assessment – "),
            ("Student",1,"METTycoon (Standalone) – 🎯   "),
            ("Parent",2,"DMIT – Dermatoglyphics Multiple Intelligence Test","DMIT","Understand your child's potential","🧬"),
            ("Parent",2,"Career Planning (Combo) "),
            ("Parent",2,"Tycoon Combo","🎯"),
            ("Corporate",3,"Hiring Assessment","⚙️"),
            ("Corporate",3,"Polaris (Corporate)","📈"),
            ("Corporate",3,"Hiring Assessment (Comparison)","🔬"),
        ]
        for s in svcs:
            c.execute("INSERT INTO services(category_name,category_id,name,code,description,icon) VALUES(?,?,?,?,?,?)",s)
    conn.commit()
    for i in range(7): seed_slots(conn,(date.today()+timedelta(days=i)).isoformat())
    conn.close()

def seed_slots(conn,ds):
    c=conn.cursor(); c.execute("SELECT COUNT(*) FROM slots WHERE slot_date=?",(ds,))
    if c.fetchone()[0]==0:
        for t in ["09:00 AM","10:00 AM","11:00 AM","12:00 PM","02:00 PM","03:00 PM","04:00 PM","05:00 PM","06:00 PM"]:
            c.execute("INSERT INTO slots(slot_time,slot_date) VALUES(?,?)",(t,ds))
        conn.commit()

def gen_meet():
    s=lambda n:''.join(random.choices(string.ascii_lowercase,k=n))
    return f"https://meet.google.com/{s(3)}-{s(4)}-{s(3)}"

def vname(n):
    n=n.strip()
    if len(n)<2: return False,"Min 2 characters."
    if not re.match(r"^[A-Za-z\s]+$",n): return False,"Letters and spaces only."
    return True,""
def vphone(p):
    p=p.strip().replace(" ","").replace("-","")
    if not re.match(r"^[6-9]\d{9}$",p): return False,"Enter valid 10-digit Indian number."
    return True,p
def vemail(e):
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",e.strip()): return False,"Enter valid email."
    return True,""

def avail_slots(ds):
    conn=get_db(); seed_slots(conn,ds); c=conn.cursor()
    c.execute("SELECT * FROM slots WHERE slot_date=? AND is_booked=0 ORDER BY slot_time",(ds,))
    rows=[dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_franchises():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM franchises WHERE is_active=1 ORDER BY id")
    rows=[dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_categories():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM categories WHERE is_active=1 ORDER BY id")
    rows=[dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_services(cat_name=None):
    conn=get_db(); c=conn.cursor()
    if cat_name:
        c.execute("SELECT * FROM services WHERE category_name=? AND is_active=1",(cat_name,))
    else:
        c.execute("SELECT * FROM services WHERE is_active=1 ORDER BY category_name")
    rows=[dict(r) for r in c.fetchall()]; conn.close(); return rows

@app.route('/static/<path:f>')
def sf(f): return send_from_directory('static',f)

@app.route('/')
def index(): return render_template('chatbot.html')

@app.route('/api/categories')
def api_cats():
    cats=get_categories()
    return jsonify({"categories":[{"name":c["name"],"icon":c["icon"]} for c in cats]})

@app.route('/api/tests/<category>')
def api_tests(category):
    svcs=get_services(category)
    return jsonify({"tests":[{"name":s["name"],"code":s["code"],"description":s["description"],"icon":s["icon"]} for s in svcs]})

@app.route('/api/franchises')
def api_fr(): return jsonify({"franchises":get_franchises()})

@app.route('/api/slots')
def api_slots():
    ds=request.args.get("date",date.today().isoformat())
    return jsonify({"slots":avail_slots(ds),"date":ds})

@app.route('/api/book',methods=['POST'])
def api_book():
    d=request.json; errors={}
    ok,err=vname(d.get("name",""));
    if not ok: errors["name"]=err
    ok,err=vphone(d.get("phone",""));
    if not ok: errors["phone"]=err
    ok,err=vemail(d.get("email",""));
    if not ok: errors["email"]=err
    if not d.get("category"): errors["category"]="Select a category."
    if not d.get("test_name"): errors["test_name"]="Select a test."
    if not d.get("mode"): errors["mode"]="Select a mode."
    if not d.get("slot_id"): errors["slot_id"]="Select a time slot."
    if not d.get("booking_date"): errors["booking_date"]="Select a date."
    if d.get("mode")=="Offline" and not d.get("franchise_id"): errors["franchise_id"]="Select a franchise."
    if errors: return jsonify({"ok":False,"errors":errors}),400
    conn=get_db(); c=conn.cursor()
    sid=int(d["slot_id"])
    c.execute("SELECT is_booked FROM slots WHERE id=?",(sid,))
    row=c.fetchone()
    if not row or row["is_booked"]: conn.close(); return jsonify({"ok":False,"errors":{"slot_id":"Slot just booked. Pick another."}}),409
    meet_link=gen_meet() if d.get("mode")=="Online" else None
    frs=get_franchises()
    fr=next((f for f in frs if f["id"]==int(d.get("franchise_id",0))),None) if d.get("franchise_id") else None
    c.execute("""INSERT INTO bookings(name,email,phone,city,category,test_name,mode,
        franchise_id,franchise_name,franchise_address,slot_id,slot_time,booking_date,
        amount,payment_method,status,meet_link) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d["name"].strip().title(),d["email"].strip().lower(),d["phone"].strip(),
         d.get("city","").strip().title(),d["category"],d["test_name"],d["mode"],
         fr["id"] if fr else None,fr["name"] if fr else None,fr["address"] if fr else None,
         sid,d.get("slot_time",""),d["booking_date"],
         100 if d["mode"]=="Online" else 0,
         d.get("payment_method","UPI") if d["mode"]=="Online" else "Free","Confirmed",meet_link))
    bid=c.lastrowid
    c.execute("UPDATE slots SET is_booked=1,booking_id=? WHERE id=?",(bid,sid))
    conn.commit(); conn.close()
    bdate=datetime.strptime(d["booking_date"],"%Y-%m-%d").strftime("%d %b %Y")
    import urllib.parse as up
    msg=f"Hi {d['name'].strip().title()}! Brain Checker session confirmed.\nTest: {d['test_name']}\nDate: {bdate} at {d.get('slot_time','')}\n"+(f"Meet: {meet_link}" if meet_link else f"Venue: {fr['address'] if fr else ''}")
    return jsonify({"ok":True,"booking_id":bid,"name":d["name"].strip().title(),"email":d["email"].strip().lower(),
        "phone":d["phone"].strip(),"category":d["category"],"test_name":d["test_name"],"mode":d["mode"],
        "slot_time":d.get("slot_time",""),"booking_date":bdate,"amount":100 if d["mode"]=="Online" else 0,
        "meet_link":meet_link,"franchise_name":fr["name"] if fr else None,"franchise_address":fr["address"] if fr else None,
        "whatsapp_url":f"https://wa.me/{d['phone'].strip()}?text="+up.quote(msg),
        "mailto_url":f"mailto:{d['email'].strip().lower()}?subject=Brain+Checkers+Booking+Confirmed&body="+up.quote(f"Dear {d['name'].strip().title()},\n\n{msg}\n\nThank you,\nBrain Checker Team")})

# ── ADMIN AUTH ──
@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    err=None
    if request.method=='POST':
        if request.form.get('u')==ADMIN_USER and request.form.get('p')==ADMIN_PASS:
            session['adm']=True; return redirect('/admin')
        err="Invalid credentials."
    return render_template('login.html',error=err)

@app.route('/admin/logout')
def admin_logout(): session.pop('adm',None); return redirect('/admin/login')

def adm(f):
    from functools import wraps
    @wraps(f)
    def d(*a,**k):
        if not session.get('adm'): return redirect('/admin/login')
        return f(*a,**k)
    return d

@app.route('/admin')
@adm
def admin(): return render_template('admin.html')

# ── ADMIN BOOKINGS ──
@app.route('/api/admin/bookings')
@adm
def adm_bookings():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM bookings ORDER BY id DESC")
    rows=[dict(r) for r in c.fetchall()]; conn.close()
    return jsonify({"bookings":rows,"total":len(rows),
        "online":sum(1 for r in rows if r["mode"]=="Online"),
        "offline":sum(1 for r in rows if r["mode"]=="Offline"),
        "revenue":sum(r["amount"] for r in rows)})

@app.route('/api/admin/bookings/<int:bid>',methods=['DELETE'])
@adm
def adm_del(bid):
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT slot_id FROM bookings WHERE id=?",(bid,))
    row=c.fetchone()
    if row and row["slot_id"]: c.execute("UPDATE slots SET is_booked=0,booking_id=NULL WHERE id=?",(row["slot_id"],))
    c.execute("DELETE FROM bookings WHERE id=?",(bid,)); conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route('/api/admin/bookings/<int:bid>/status',methods=['PATCH'])
@adm
def adm_st(bid):
    conn=get_db(); conn.execute("UPDATE bookings SET status=? WHERE id=?",(request.json.get("status"),bid)); conn.commit(); conn.close()
    return jsonify({"ok":True})

# ── ADMIN SLOTS ──
@app.route('/api/admin/slots')
@adm
def adm_slots():
    ds=request.args.get("date",date.today().isoformat())
    conn=get_db(); seed_slots(conn,ds); c=conn.cursor()
    c.execute("""SELECT s.*,b.name bname,b.phone bphone,b.mode bmode,b.category bcat
                 FROM slots s LEFT JOIN bookings b ON s.booking_id=b.id
                 WHERE s.slot_date=? ORDER BY s.slot_time""",(ds,))
    rows=[dict(r) for r in c.fetchall()]; conn.close()
    return jsonify({"slots":rows})

@app.route('/api/admin/slots',methods=['POST'])
@adm
def adm_add_slot():
    d=request.json; t=d.get("time",""); ds=d.get("date",date.today().isoformat())
    if not t: return jsonify({"ok":False,"error":"Time required"}),400
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT id FROM slots WHERE slot_time=? AND slot_date=?",(t,ds))
    if c.fetchone(): conn.close(); return jsonify({"ok":False,"error":"Already exists"}),409
    c.execute("INSERT INTO slots(slot_time,slot_date) VALUES(?,?)",(t,ds)); conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route('/api/admin/slots/<int:sid>',methods=['DELETE'])
@adm
def adm_del_slot(sid):
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT is_booked FROM slots WHERE id=?",(sid,))
    row=c.fetchone()
    if row and row["is_booked"]: conn.close(); return jsonify({"ok":False,"error":"Slot is booked"}),400
    conn.execute("DELETE FROM slots WHERE id=?",(sid,)); conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route('/api/admin/slots/seed',methods=['POST'])
@adm
def adm_seed():
    ds=request.json.get("date",(date.today()+timedelta(days=1)).isoformat())
    conn=get_db(); seed_slots(conn,ds); conn.close()
    return jsonify({"ok":True})

# ── ADMIN FRANCHISES ──
@app.route('/api/admin/franchises')
@adm
def adm_frs(): return jsonify({"franchises":get_franchises()})

@app.route('/api/admin/franchises',methods=['POST'])
@adm
def adm_add_fr():
    d=request.json
    if not d.get("name") or not d.get("address"): return jsonify({"ok":False,"error":"Name and address required"}),400
    conn=get_db()
    conn.execute("INSERT INTO franchises(name,area,address,city,phone,lat,lng) VALUES(?,?,?,?,?,?,?)",
        (d["name"],d.get("area",""),d["address"],d.get("city",""),d.get("phone",""),
         float(d.get("lat",0)),float(d.get("lng",0))))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route('/api/admin/franchises/<int:fid>',methods=['PUT'])
@adm
def adm_edit_fr(fid):
    d=request.json
    conn=get_db()
    conn.execute("UPDATE franchises SET name=?,area=?,address=?,city=?,phone=?,lat=?,lng=?,is_active=? WHERE id=?",
        (d["name"],d.get("area",""),d["address"],d.get("city",""),d.get("phone",""),
         float(d.get("lat",0)),float(d.get("lng",0)),int(d.get("is_active",1)),fid))
    conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route('/api/admin/franchises/<int:fid>',methods=['DELETE'])
@adm
def adm_del_fr(fid):
    conn=get_db(); conn.execute("UPDATE franchises SET is_active=0 WHERE id=?",(fid,)); conn.commit(); conn.close()
    return jsonify({"ok":True})

# ── ADMIN CATEGORIES ──
@app.route('/api/admin/categories')
@adm
def adm_cats():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM categories ORDER BY id")
    rows=[dict(r) for r in c.fetchall()]; conn.close()
    return jsonify({"categories":rows})

@app.route('/api/admin/categories',methods=['POST'])
@adm
def adm_add_cat():
    d=request.json
    if not d.get("name"): return jsonify({"ok":False,"error":"Name required"}),400
    conn=get_db()
    try:
        conn.execute("INSERT INTO categories(name,icon) VALUES(?,?)",(d["name"],d.get("icon","📋")))
        conn.commit()
    except: conn.close(); return jsonify({"ok":False,"error":"Category already exists"}),409
    conn.close(); return jsonify({"ok":True})

@app.route('/api/admin/categories/<int:cid>',methods=['PUT'])
@adm
def adm_edit_cat(cid):
    d=request.json
    conn=get_db(); conn.execute("UPDATE categories SET name=?,icon=?,is_active=? WHERE id=?",(d["name"],d.get("icon","📋"),int(d.get("is_active",1)),cid)); conn.commit(); conn.close()
    return jsonify({"ok":True})

@app.route('/api/admin/categories/<int:cid>',methods=['DELETE'])
@adm
def adm_del_cat(cid):
    conn=get_db(); conn.execute("UPDATE categories SET is_active=0 WHERE id=?",(cid,)); conn.commit(); conn.close()
    return jsonify({"ok":True})

# ── ADMIN SERVICES ──
@app.route('/api/admin/services')
@adm
def adm_svcs():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM services ORDER BY category_name,id")
    rows=[dict(r) for r in c.fetchall()]; conn.close()
    return jsonify({"services":rows})

@app.route('/api/admin/services',methods=['POST'])
@adm
def adm_add_svc():
    d=request.json
    if not d.get("name") or not d.get("category_name"): return jsonify({"ok":False,"error":"Name and category required"}),400
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT id FROM categories WHERE name=?",(d["category_name"],))
    cat=c.fetchone()
    cid=cat["id"] if cat else None
    conn.execute("INSERT INTO services(category_name,category_id,name,code,description,icon) VALUES(?,?,?,?,?,?)",
        (d["category_name"],cid,d["name"],d.get("code",""),d.get("description",""),d.get("icon","📋")))
    conn.commit(); conn.close(); return jsonify({"ok":True})

@app.route('/api/admin/services/<int:sid>',methods=['PUT'])
@adm
def adm_edit_svc(sid):
    d=request.json
    conn=get_db(); conn.execute("UPDATE services SET name=?,code=?,description=?,icon=?,is_active=?,category_name=? WHERE id=?",
        (d["name"],d.get("code",""),d.get("description",""),d.get("icon","📋"),int(d.get("is_active",1)),d.get("category_name",""),sid))
    conn.commit(); conn.close(); return jsonify({"ok":True})

@app.route('/api/admin/services/<int:sid>',methods=['DELETE'])
@adm
def adm_del_svc(sid):
    conn=get_db(); conn.execute("UPDATE services SET is_active=0 WHERE id=?",(sid,)); conn.commit(); conn.close()
    return jsonify({"ok":True})

if __name__=='__main__':
    init_db(); app.run(debug=True,port=5000)
