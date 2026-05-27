from flask import Flask, render_template, request, jsonify, session, redirect, send_from_directory
from datetime import datetime, date, timedelta
import sqlite3, os, re, random, string, json

app = Flask(__name__)
app.secret_key = "braincheckers_secret_2026"

DB = "braincheckers.db"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "brain@2026"

FRANCHISES = [
    {"id": 1, "name": "Pune - Kothrud Centre",      "address": "Office 302, ABC Tower, Kothrud, Pune – 411038",          "phone": "+91-7234567890"},
    {"id": 2, "name": "Pune - Hadapsar Centre",      "address": "Shop 14, Magarpatta Road, Hadapsar, Pune – 411028",       "phone": "+91-7234567891"},
    {"id": 3, "name": "Mumbai - Andheri Centre",     "address": "2nd Floor, Infinity Mall, Andheri West, Mumbai – 400058", "phone": "+91-7234567892"},
    {"id": 4, "name": "Mumbai - Thane Centre",       "address": "Office 5, Viviana Complex, Thane West – 400601",          "phone": "+91-7234567893"},
    {"id": 5, "name": "Jalgaon Jamod - Durga chok",  "address": "1st Floor, Saraf Complex, Jalgaon Jamod – 443403",  "phone": "+91-7234567894"},
    {"id": 6, "name": "Delhi - Connaught Place",     "address": "Block A, Connaught Place, New Delhi – 110001",            "phone": "+91-7234567895"},
]

TESTS_BY_CATEGORY = {
    "Student":   ["DMIT", "GET", "MET"],
    "Parent":    ["DMIT", "GET", "MET"],
    "Corporate": ["SAT", "MAT", "GAT"],
}

# ── DB ──────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, city TEXT, phone TEXT,
        category TEXT DEFAULT NULL,
        service TEXT, mode TEXT,
        franchise_id INTEGER DEFAULT NULL,
        franchise_name TEXT DEFAULT NULL,
        franchise_address TEXT DEFAULT NULL,
        slot_id INTEGER, time TEXT, booking_date TEXT,
        amount INTEGER, status TEXT DEFAULT 'Confirmed',
        meet_link TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_time TEXT NOT NULL,
        slot_date TEXT NOT NULL,
        is_booked INTEGER DEFAULT 0,
        booking_id INTEGER DEFAULT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        step INTEGER DEFAULT 0,
        name TEXT, phone TEXT,
        category TEXT,
        service TEXT, mode TEXT, amount INTEGER,
        franchise_id INTEGER, franchise_name TEXT, franchise_address TEXT,
        selected_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    seed_slots_for_date(conn, date.today().isoformat())
    seed_slots_for_date(conn, (date.today()+timedelta(days=1)).isoformat())
    seed_slots_for_date(conn, (date.today()+timedelta(days=2)).isoformat())
    conn.close()

def seed_slots_for_date(conn, date_str):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM slots WHERE slot_date=?", (date_str,))
    if c.fetchone()[0] == 0:
        times = ["09:00 AM","10:00 AM","11:00 AM","12:00 PM",
                 "02:00 PM","03:00 PM","04:00 PM","05:00 PM","06:00 PM"]
        for t in times:
            c.execute("INSERT INTO slots (slot_time,slot_date) VALUES (?,?)", (t, date_str))
        conn.commit()

def gen_meet():
    def s(n): return ''.join(random.choices(string.ascii_lowercase, k=n))
    return f"https://meet.google.com/{s(3)}-{s(4)}-{s(3)}"

def validate_name(n):
    n = n.strip()
    if len(n) < 2: return False, "Name must be at least 2 characters."
    if not re.match(r"^[A-Za-z\s]+$", n): return False, "Only letters and spaces allowed."
    return True, ""

def validate_phone(p):
    p = p.strip().replace(" ","").replace("-","")
    if not re.match(r"^[6-9]\d{9}$", p): return False, "Enter a valid 10-digit Indian mobile number (starts with 6–9)."
    return True, p

def get_available_slots(date_str):
    conn = get_db()
    seed_slots_for_date(conn, date_str)
    c = conn.cursor()
    c.execute("SELECT * FROM slots WHERE slot_date=? AND is_booked=0 ORDER BY slot_time", (date_str,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_chat_state(sid):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM chat_sessions WHERE session_id=? ORDER BY id DESC LIMIT 1", (sid,))
    row = c.fetchone(); conn.close()
    if row: return dict(row)
    return {"step": 0, "session_id": sid}

def save_chat_state(state):
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM chat_sessions WHERE session_id=?", (state.get("session_id",""),))
    c.execute("""INSERT INTO chat_sessions
        (session_id,step,name,phone,category,service,mode,amount,
         franchise_id,franchise_name,franchise_address,selected_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (state.get("session_id"), state.get("step", 0),
         state.get("name"), state.get("phone"),
         state.get("category"), state.get("service"),
         state.get("mode"), state.get("amount"),
         state.get("franchise_id"), state.get("franchise_name"),
         state.get("franchise_address"), state.get("selected_date")))
    conn.commit(); conn.close()

# ── STATIC ──────────────────────────────────────────────────────────────────

@app.route('/static/<path:f>')
def static_files(f): return send_from_directory('static', f)

# ── PUBLIC APIs ──────────────────────────────────────────────────────────────

@app.route("/api/franchises")
def api_franchises():
    return jsonify({"franchises": FRANCHISES})

@app.route("/api/slots")
def api_slots_public():
    d = request.args.get("date", date.today().isoformat())
    return jsonify({"slots": get_available_slots(d), "date": d})

# ── CHATBOT PAGE ──────────────────────────────────────────────────────────────

@app.route("/")
def chatbot_page():
    if "chat_sid" not in session:
        session["chat_sid"] = ''.join(random.choices(string.ascii_letters+string.digits, k=16))
    return render_template("chatbot.html")

@app.route("/api/reset", methods=["POST"])
def reset():
    sid = session.get("chat_sid", "anon")
    conn = get_db(); conn.execute("DELETE FROM chat_sessions WHERE session_id=?", (sid,)); conn.commit(); conn.close()
    state = {"step": 0, "session_id": sid}; save_chat_state(state)
    return jsonify({"ok": True})

# ── CHAT API ──────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    sid      = session.get("chat_sid", "anon")
    user_msg = request.json.get("message", "").strip()
    state    = get_chat_state(sid)
    step     = state.get("step", 0)
    responses, options = [], []

    # ── STEP 0: Greet ──────────────────────────────────────────────────────
    if step == 0:
        responses.append(("bot", "Welcome to <strong>Brain Checkers</strong>! 🧠<br>I'll help you book your assessment in a few easy steps."))
        responses.append(("bot", "Let's start — what is your <strong>full name</strong>?"))
        state["step"] = 1

    # ── STEP 1: Name ───────────────────────────────────────────────────────
    elif step == 1:
        ok, err = validate_name(user_msg)
        if not ok:
            responses.append(("error", f"⚠️ {err} Please try again."))
        else:
            state["name"] = user_msg.strip().title()
            responses.append(("bot", f"Great to meet you, <strong>{state['name']}</strong>! 👋"))
            responses.append(("bot", "Please share your <strong>10-digit mobile number</strong>:"))
            state["step"] = 2

    # ── STEP 2: Phone ──────────────────────────────────────────────────────
    elif step == 2:
        ok, result = validate_phone(user_msg)
        if not ok:
            responses.append(("error", f"⚠️ {result}"))
        else:
            state["phone"] = result
            responses.append(("bot", f"✅ Got it! Now, <strong>who is this session for?</strong>"))
            responses.append(("category_select", ""))
            state["step"] = 3

    # ── STEP 3: Category ───────────────────────────────────────────────────
    elif step == 3:
        if user_msg.startswith("category|"):
            cat = user_msg.split("|")[1]
            if cat not in TESTS_BY_CATEGORY:
                responses.append(("error", "⚠️ Please select a valid category."))
                responses.append(("category_select", ""))
            else:
                state["category"] = cat
                tests = TESTS_BY_CATEGORY[cat]
                responses.append(("bot", f"Perfect! For <strong>{cat}</strong>, here are the available assessments:"))
                responses.append(("test_select", json.dumps(tests)))
                state["step"] = 4
        else:
            responses.append(("error", "⚠️ Please select a category."))
            responses.append(("category_select", ""))

    # ── STEP 4: Test ───────────────────────────────────────────────────────
    elif step == 4:
        valid_tests = TESTS_BY_CATEGORY.get(state.get("category",""), [])
        if user_msg.startswith("test|"):
            test = user_msg.split("|")[1]
        else:
            test = user_msg
        if test not in valid_tests:
            responses.append(("error", "⚠️ Please select a test from the options."))
            responses.append(("test_select", json.dumps(valid_tests)))
        else:
            state["service"] = test
            responses.append(("bot", f"Excellent choice — <strong>{test}</strong>! 🎯"))
            responses.append(("bot", "How would you prefer to attend your session?"))
            responses.append(("mode_select", ""))
            state["step"] = 5

    # ── STEP 5: Mode ───────────────────────────────────────────────────────
    elif step == 5:
        if user_msg == "Online":
            state["mode"] = "Online"
            state["amount"] = 100
            state["franchise_id"] = None
            state["franchise_name"] = None
            state["franchise_address"] = None
            responses.append(("bot", "💻 <strong>Online Session</strong> selected — ₹100"))
            responses.append(("bot", "Please complete payment to confirm your slot:"))
            responses.append(("qr", "100"))
            state["step"] = 6
        elif user_msg == "Offline":
            state["mode"] = "Offline"
            state["amount"] = 0
            responses.append(("bot", "🏢 <strong>Offline Session</strong> — completely <strong>FREE</strong>!"))
            responses.append(("bot", "Let's find your nearest Brain Checkers centre:"))
            responses.append(("franchise_select", ""))
            state["step"] = 51
        else:
            responses.append(("error", "⚠️ Please select Online or Offline."))
            responses.append(("mode_select", ""))

    # ── STEP 51: Franchise ─────────────────────────────────────────────────
    elif step == 51:
        if user_msg.startswith("franchise|"):
            fid = int(user_msg.split("|")[1])
            fr  = next((f for f in FRANCHISES if f["id"] == fid), None)
            if fr:
                state["franchise_id"]      = fr["id"]
                state["franchise_name"]    = fr["name"]
                state["franchise_address"] = fr["address"]
                responses.append(("bot", f"✅ Centre confirmed: <strong>{fr['name']}</strong>"))
                responses.append(("bot", "Now pick your preferred <strong>date</strong>:"))
                responses.append(("date_select", ""))
                state["step"] = 7
            else:
                responses.append(("error", "⚠️ Invalid selection. Please pick a centre."))
                responses.append(("franchise_select", ""))
        else:
            responses.append(("error", "⚠️ Please select a centre from the list."))
            responses.append(("franchise_select", ""))

    # ── STEP 6: Online — wait for payment, then show date ─────────────────
    elif step == 6:
        if user_msg == "✅ Payment Done":
            responses.append(("bot", "🎉 Payment received! Please select your preferred <strong>date</strong>:"))
            responses.append(("date_select", ""))
            state["step"] = 7
        else:
            responses.append(("error", "⚠️ Please complete the payment and tap 'Payment Done'."))
            responses.append(("qr", "100"))

    # ── STEP 7: Date ───────────────────────────────────────────────────────
    elif step == 7:
        if user_msg.startswith("date|"):
            chosen_date = user_msg.split("|")[1]
            state["selected_date"] = chosen_date
            avail = get_available_slots(chosen_date)
            if not avail:
                responses.append(("error", f"⚠️ No slots available on {chosen_date}. Please choose another date."))
                responses.append(("date_select", ""))
            else:
                d_fmt = datetime.strptime(chosen_date, "%Y-%m-%d").strftime("%d %b %Y")
                responses.append(("bot", f"📅 <strong>{d_fmt}</strong> — choose your <strong>time slot</strong>:"))
                slot_opts = [f"{s['slot_time']}|{s['id']}" for s in avail]
                responses.append(("slot_select", json.dumps(slot_opts)))
                state["step"] = 8
        else:
            responses.append(("error", "⚠️ Please select a date from the calendar."))
            responses.append(("date_select", ""))

    # ── STEP 8: Slot + Confirm ─────────────────────────────────────────────
    elif step == 8:
        if "|" in user_msg:
            parts     = user_msg.split("|")
            slot_time = parts[0].strip()
            try:
                slot_id = int(parts[1])
            except (IndexError, ValueError):
                responses.append(("error", "⚠️ Invalid slot. Please pick a time slot."))
                avail = get_available_slots(state.get("selected_date", date.today().isoformat()))
                responses.append(("slot_select", json.dumps([f"{s['slot_time']}|{s['id']}" for s in avail])))
                save_chat_state(state)
                return jsonify({"responses": responses, "options": options, "step": state.get("step")})

            conn = get_db(); c = conn.cursor()
            c.execute("SELECT is_booked FROM slots WHERE id=?", (slot_id,))
            row = c.fetchone()
            if not row or row["is_booked"]:
                conn.close()
                responses.append(("error", "⚠️ That slot was just taken! Please choose another."))
                avail = get_available_slots(state.get("selected_date", date.today().isoformat()))
                responses.append(("slot_select", json.dumps([f"{s['slot_time']}|{s['id']}" for s in avail])))
            else:
                meet_link  = gen_meet() if state.get("mode") == "Online" else None
                bdate      = state.get("selected_date", date.today().isoformat())
                c.execute("""INSERT INTO bookings
                    (name,phone,category,service,mode,
                     franchise_id,franchise_name,franchise_address,
                     slot_id,time,booking_date,amount,status,meet_link)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (state.get("name"), state.get("phone"),
                     state.get("category"), state.get("service"), state.get("mode"),
                     state.get("franchise_id"), state.get("franchise_name"), state.get("franchise_address"),
                     slot_id, slot_time, bdate, state.get("amount", 0), "Confirmed", meet_link))
                bid = c.lastrowid
                c.execute("UPDATE slots SET is_booked=1, booking_id=? WHERE id=?", (bid, slot_id))
                conn.commit(); conn.close()

                d_fmt = datetime.strptime(bdate, "%Y-%m-%d").strftime("%d %b %Y")
                confirm_data = {
                    "name":    state.get("name"),
                    "phone":   state.get("phone"),
                    "date":    d_fmt,
                    "time":    slot_time,
                    "service": state.get("service"),
                    "mode":    state.get("mode"),
                    "amount":  state.get("amount", 0),
                }
                responses.append(("confirmation", json.dumps(confirm_data)))

                if state.get("mode") == "Online":
                    responses.append(("meet", meet_link))
                else:
                    fr_addr = f"{state.get('franchise_name')}|{state.get('franchise_address')}|Phone: {next((f['phone'] for f in FRANCHISES if f['id']==state.get('franchise_id')),'')}"
                    responses.append(("address", fr_addr))

                options = ["🔄 Book Another Session"]
                state["step"] = 9
        else:
            responses.append(("error", "⚠️ Please select a time slot."))
            avail = get_available_slots(state.get("selected_date", date.today().isoformat()))
            responses.append(("slot_select", json.dumps([f"{s['slot_time']}|{s['id']}" for s in avail])))

    # ── STEP 9: Restart ────────────────────────────────────────────────────
    elif step == 9:
        state = {"step": 1, "session_id": sid}
        responses.append(("bot", "Sure! Let's book another session. What is your <strong>full name</strong>?"))

    save_chat_state(state)
    return jsonify({"responses": responses, "options": options, "step": state.get("step")})

# ── ADMIN AUTH ────────────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True; return redirect("/admin")
        error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None); return redirect("/admin/login")

def admin_req(f):
    from functools import wraps
    @wraps(f)
    def dec(*a, **kw):
        if not session.get("admin"): return redirect("/admin/login")
        return f(*a, **kw)
    return dec

@app.route("/admin")
@admin_req
def admin_page(): return render_template("admin.html")

# ── ADMIN APIs ────────────────────────────────────────────────────────────────

@app.route("/api/admin/bookings")
@admin_req
def api_bookings():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM bookings ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]; conn.close()
    online  = sum(1 for r in rows if r["mode"] == "Online")
    offline = sum(1 for r in rows if r["mode"] == "Offline")
    revenue = sum(r["amount"] for r in rows)
    return jsonify({"bookings": rows, "total": len(rows), "online": online, "offline": offline, "revenue": revenue})

@app.route("/api/admin/bookings/<int:bid>", methods=["DELETE"])
@admin_req
def del_booking(bid):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT slot_id FROM bookings WHERE id=?", (bid,))
    row = c.fetchone()
    if row and row["slot_id"]:
        c.execute("UPDATE slots SET is_booked=0, booking_id=NULL WHERE id=?", (row["slot_id"],))
    c.execute("DELETE FROM bookings WHERE id=?", (bid,)); conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/admin/bookings/<int:bid>/status", methods=["PATCH"])
@admin_req
def upd_status(bid):
    st = request.json.get("status")
    conn = get_db(); conn.execute("UPDATE bookings SET status=? WHERE id=?", (st, bid)); conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/admin/slots")
@admin_req
def api_slots():
    target = request.args.get("date", date.today().isoformat())
    conn = get_db(); seed_slots_for_date(conn, target); c = conn.cursor()
    c.execute("""SELECT s.*, b.name as booked_by, b.phone as booked_phone, b.mode as booked_mode
                 FROM slots s LEFT JOIN bookings b ON s.booking_id=b.id
                 WHERE s.slot_date=? ORDER BY s.slot_time""", (target,))
    rows = [dict(r) for r in c.fetchall()]; conn.close()
    return jsonify({"slots": rows, "date": target})

@app.route("/api/admin/slots", methods=["POST"])
@admin_req
def add_slot():
    data = request.json; t = data.get("time","").strip(); d = data.get("date", date.today().isoformat())
    if not t: return jsonify({"ok": False, "error": "Time required"}), 400
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM slots WHERE slot_time=? AND slot_date=?", (t, d))
    if c.fetchone(): conn.close(); return jsonify({"ok": False, "error": "Slot already exists"}), 409
    c.execute("INSERT INTO slots (slot_time,slot_date) VALUES (?,?)", (t, d)); conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/admin/slots/<int:sid>", methods=["DELETE"])
@admin_req
def del_slot(sid):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT is_booked FROM slots WHERE id=?", (sid,))
    row = c.fetchone()
    if row and row["is_booked"]: conn.close(); return jsonify({"ok": False, "error": "Cannot delete a booked slot"}), 400
    conn.execute("DELETE FROM slots WHERE id=?", (sid,)); conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/admin/slots/seed", methods=["POST"])
@admin_req
def seed_day():
    target = request.json.get("date", (date.today()+timedelta(days=1)).isoformat())
    conn = get_db(); seed_slots_for_date(conn, target); conn.close()
    return jsonify({"ok": True})

@app.route("/api/admin/franchises")
@admin_req
def api_franchises_admin(): return jsonify({"franchises": FRANCHISES})

if __name__ == "__main__":
    init_db(); app.run(debug=True, port=5000)
