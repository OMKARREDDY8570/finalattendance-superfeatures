from flask import Flask, request, render_template, jsonify, session, redirect, url_for
import ast
import re
import requests
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
import json
import os
import time
import random
import threading
from datetime import datetime, timezone
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "mits_secret_key_2024_xK9pL3")
app.config["SESSION_PERMANENT"] = False
ADMIN_SESSION_TIMEOUT = 7200

ADMIN_USER = "admin"
ADMIN_PASS = "Apac/ptp1cob"

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1495123304564920410/5MsyIRVI35vjE97abjdeK0CfYQRDsHbsCesmsHu9I7eWnYORnZSMecjbYXyduCzjtD1t"

_live_clients_lock = threading.Lock()
_live_clients: dict = {}
_LOGIN_ACTIVITY: list = []
MAX_ACTIVITY = 50

_otp_store: dict = {}
_otp_lock = threading.Lock()

def _prune_clients(max_age=60):
    now = time.time()
    with _live_clients_lock:
        for ip in list(_live_clients.keys()):
            if now - _live_clients[ip] > max_age:
                del _live_clients[ip]

@app.before_request
def track_client():
    ip = request.remote_addr or "unknown"
    with _live_clients_lock:
        _live_clients[ip] = time.time()

def live_client_count():
    _prune_clients(60)
    with _live_clients_lock:
        return len(_live_clients)

def record_login(roll, ip):
    _LOGIN_ACTIVITY.insert(0, {
        "roll": roll, "ip": ip,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    if len(_LOGIN_ACTIVITY) > MAX_ACTIVITY:
        _LOGIN_ACTIVITY.pop()

# ── Discord Webhook ─────────────────────────────────────────────────────────────
def send_discord_message(content: str):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": content}, timeout=5)
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")

# ── OTP Management ──────────────────────────────────────────────────────────────
def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def store_otp(otp: str):
    with _otp_lock:
        _otp_store["otp"] = otp
        _otp_store["expires"] = time.time() + 300

def verify_otp(entered: str) -> bool:
    with _otp_lock:
        if not _otp_store.get("otp"):
            return False
        if time.time() > _otp_store.get("expires", 0):
            _otp_store.clear()
            return False
        if _otp_store["otp"] == entered.strip():
            _otp_store.clear()
            return True
        return False

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        login_time = session.get("admin_login_time", 0)
        if time.time() - login_time > ADMIN_SESSION_TIMEOUT:
            session.clear()
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ── Telegram Config ───────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = "https://api.telegram.org"
APP_PORT = int(os.getenv("PORT", "5000"))
APP_HOST = os.getenv("HOST", "0.0.0.0")

def send_telegram_message(chat_id, text, reply_markup=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return False
    try:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        r = requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json=payload,
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False

def setup_telegram_webhook():
    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; webhook not configured")
        return False
    webhook_base = os.getenv("REPLIT_DEV_DOMAIN") or os.getenv("REPLIT_DOMAINS", "").split(",")[0].strip()
    if not webhook_base:
        logger.warning("REPLIT domain not available; webhook not configured")
        return False
    webhook_url = f"https://{webhook_base}/telegram/webhook"
    try:
        r = requests.post(
            f"{TELEGRAM_API}/bot{token}/setWebhook",
            json={"url": webhook_url},
            timeout=10
        )
        result = r.json()
        if result.get("ok"):
            logger.info(f"Telegram webhook set to {webhook_url}")
            return True
        logger.error(f"Failed to set Telegram webhook: {result}")
        return False
    except Exception as e:
        logger.error(f"Telegram webhook setup error: {e}")
        return False

def answer_callback_query(callback_query_id, text=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        return
    try:
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        requests.post(
            f"{TELEGRAM_API}/bot{token}/answerCallbackQuery",
            json=payload,
            timeout=10
        )
    except Exception as e:
        logger.error(f"Telegram answerCallbackQuery error: {e}")

def edit_telegram_message(chat_id, message_id, text, reply_markup=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        return False
    try:
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        r = requests.post(
            f"{TELEGRAM_API}/bot{token}/editMessageText",
            json=payload,
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram editMessageText error: {e}")
        return False

def main_menu_keyboard(is_linked=False):
    if is_linked:
        return {
            "inline_keyboard": [
                [{"text": "📊 Check Attendance", "callback_data": "status"}],
                [{"text": "🔓 Unlink Account", "callback_data": "unlink"},
                 {"text": "♻️ Forget / Re-link", "callback_data": "forget"},
                 {"text": "❓ Help", "callback_data": "help"}]
            ]
        }
    else:
        return {
            "inline_keyboard": [
                [{"text": "🔗 Link My Account", "callback_data": "link_prompt"}],
                [{"text": "♻️ Forget / Re-link", "callback_data": "forget"}],
                [{"text": "📊 Check Attendance", "callback_data": "status"},
                 {"text": "❓ Help", "callback_data": "help"}]
            ]
        }

def attendance_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🔄 Refresh Attendance", "callback_data": "status"}],
            [{"text": "🏠 Main Menu", "callback_data": "menu"}]
        ]
    }

def build_attendance_text(roll, data):
    if not data:
        return (
            f"⚠️ <b>Attendance Data Error</b>\n\n"
            f"Roll: <b>{roll}</b>\n"
            f"Could not fetch attendance.\n"
            f"Try again later or re-link your account."
            f"IS GEMS WORKING...!!!"
        )

    if "overall" not in data:
        return "⚠️ Invalid attendance data received."
    overall = data["overall"]
    pct = overall["percentage"]
    if pct >= 80:
        status = "🟢 SAFE"
    elif pct >= 75:
        status = "🟡 WARNING"
    else:
        status = "🔴 DANGER"

    if overall["max_skip"] > 0:
        skip_or_need = f"✅ You can safely skip <b>{overall['max_skip']}</b> more class(es)."
    else:
        skip_or_need = f"⚠️ You must attend <b>{overall['need_to_attend']}</b> more class(es) to reach 75%."

    lines = [
        f"📊 <b>Daily Attendance Report — {roll}</b>",
        f"",
        f"<b>Overall:</b> {pct:.2f}% — {status}",
        f"<b>Classes Attended:</b> {overall['attended']} / {overall['total']}",
        f"{skip_or_need}",
        f"",
        f"<b>Subject-wise:</b>",
    ]

    for s in data["subjects"]:
        icon = "✅" if s["percentage"] >= 75 else "⚠️"
        lines.append(f"{icon} <b>{s['name'][:35]}</b>: {s['percentage']}% ({s['attended']}/{s['total']}) — {s['action']}")

    lines.append(f"\n🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p')} IST")
    return "\n".join(lines)

# ── Database Connection Pool ───────────────────────────────────────────────────
_db_pool = None
_pool_lock = threading.Lock()

def _build_dsn():
    supabase_password = os.getenv("SUPABASE_DB_PASSWORD", "")
    if supabase_password:
        return {
            "host": os.getenv("SUPABASE_DB_HOST", "db.ujvhwnqjynscbcgpaiju.supabase.co"),
            "port": int(os.getenv("SUPABASE_DB_PORT", "5432")),
            "dbname": os.getenv("SUPABASE_DB_NAME", "postgres"),
            "user": os.getenv("SUPABASE_DB_USER", "postgres"),
            "password": supabase_password,
            "connect_timeout": 10,
            "sslmode": "require",
        }
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("PGDATABASE", "postgres"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", ""),
        "connect_timeout": 10,
    }

def get_pool():
    global _db_pool
    if _db_pool is not None:
        return _db_pool
    with _pool_lock:
        if _db_pool is not None:
            return _db_pool
        dsn = _build_dsn()
        try:
            if isinstance(dsn, str):
                pool = psycopg2.pool.ThreadedConnectionPool(2, 10, dsn)
            else:
                pool = psycopg2.pool.ThreadedConnectionPool(2, 10, **dsn)
            _db_pool = pool
            logger.info("Database connection pool created (min=2, max=10)")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise
    return _db_pool

def get_db_conn():
    return get_pool().getconn()

def release_conn(conn):
    try:
        get_pool().putconn(conn)
    except Exception:
        pass

def init_db():
    conn = get_db_conn()
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS students (
                roll               TEXT PRIMARY KEY,
                password           TEXT NOT NULL,
                telegram_chat_id   TEXT,
                telegram_enabled   INTEGER DEFAULT 0,
                created_at         TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS subject_settings (
                subject_name TEXT PRIMARY KEY,
                enabled      INTEGER DEFAULT 1
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
        logger.info("Database initialised")
    finally:
        release_conn(conn)

init_db()

def upsert_student(roll, password):
    conn = get_db_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO students (roll, password, created_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (roll) DO UPDATE SET password = EXCLUDED.password
        """, (roll, password, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    finally:
        release_conn(conn)

def get_student(roll):
    conn = get_db_conn()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM students WHERE roll = %s", (roll,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        release_conn(conn)

def get_student_by_chat_id(chat_id):
    conn = get_db_conn()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM students WHERE telegram_chat_id = %s", (str(chat_id),))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        release_conn(conn)

def update_student_telegram(roll, **kwargs):
    conn = get_db_conn()
    try:
        c = conn.cursor()
        fields = ", ".join(f"{k} = %s" for k in kwargs)
        values = list(kwargs.values()) + [roll]
        c.execute(f"UPDATE students SET {fields} WHERE roll = %s", values)
        conn.commit()
    finally:
        release_conn(conn)

def get_all_telegram_subscribed():
    conn = get_db_conn()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("""
            SELECT * FROM students
            WHERE telegram_enabled = 1
              AND telegram_chat_id IS NOT NULL
              AND telegram_chat_id != ''
        """)
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        release_conn(conn)

def get_all_students():
    conn = get_db_conn()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM students ORDER BY created_at DESC")
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        release_conn(conn)

# ── App Settings (notice board, etc.) ────────────────────────────────────────
def get_setting(key, default=None):
    conn = get_db_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
        row = c.fetchone()
        return row[0] if row else default
    finally:
        release_conn(conn)

def set_setting(key, value):
    conn = get_db_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO app_settings (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (key, value))
        conn.commit()
    finally:
        release_conn(conn)

# ── Subject Settings ──────────────────────────────────────────────────────────
def upsert_subjects(subject_names):
    conn = get_db_conn()
    try:
        c = conn.cursor()
        for name in subject_names:
            c.execute("""
                INSERT INTO subject_settings (subject_name, enabled)
                VALUES (%s, 1)
                ON CONFLICT (subject_name) DO NOTHING
            """, (name,))
        conn.commit()
    finally:
        release_conn(conn)

def get_disabled_subjects():
    conn = get_db_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT subject_name FROM subject_settings WHERE enabled = 0")
        rows = c.fetchall()
        return {r[0] for r in rows}
    finally:
        release_conn(conn)

def get_all_subject_settings():
    conn = get_db_conn()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT subject_name, enabled FROM subject_settings ORDER BY subject_name")
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        release_conn(conn)

def set_subject_enabled(subject_name, enabled):
    conn = get_db_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE subject_settings SET enabled = %s WHERE subject_name = %s",
                  (1 if enabled else 0, subject_name))
        conn.commit()
    finally:
        release_conn(conn)

# ── Core Attendance Logic ─────────────────────────────────────────────────────
def calculate(username, password):
    sess = requests.Session()
    login_url = "http://mitsims.in/studentAppLogin/studentLogin.action"
    login_params = {
        "actionType": "studentAppLogin",
        "personType": "student",
        "userId": username,
        "password": password
    }
    try:
        login_response = sess.get(login_url, params=login_params, timeout=15)
        login_data = ast.literal_eval(login_response.text)
        if login_data["status"] == "success":
            student_id = login_data["studentLoginDetails"][0]["id"]
            token      = login_data["studentLoginDetails"][0]["authToken"]
        else:
            return None
    except Exception:
        return None

    attendance_url = "http://mitsims.in/studentApp/getAttendanceDetails.action"
    attendance_params = {
        "tkn": token,
        "stdnt.id": student_id,
        "studentId": student_id,
        "actionType": "attendanceDetails",
        "studentType": "student"
    }
    try:
        attendance_response = sess.get(attendance_url, params=attendance_params, timeout=15)
        js_text = attendance_response.text
        subject_blocks = re.findall(r'\{(.*?)\}', js_text, re.DOTALL)
        cleaned_attendance = {}
        for block in subject_blocks:
            try:
                subject    = re.search(r"subjectName\s*:\s*'([^']+)'", block).group(1).strip()
                attended   = int(re.search(r"attended\s*:\s*'([^']+)'", block).group(1).strip())
                total      = int(re.search(r"conducted\s*:\s*'([^']+)'", block).group(1).strip())
                percentage = float(re.search(r"percentage\s*:\s*'([^']+)'", block).group(1).strip())
                cleaned_attendance[subject] = {
                    'attended': attended,
                    'total_classes': total,
                    'percentage': percentage
                }
            except AttributeError:
                continue
        return cleaned_attendance
    except Exception:
        return None


def process_attendance_data(data, threshold=75):
    if not data:
        return None
    subjects = []
    overall_attended = 0
    overall_total    = 0
    for subject, details in data.items():
        attended = details['attended']
        total    = details['total_classes']
        percent  = details['percentage']
        overall_attended += attended
        overall_total    += total
        if percent >= threshold:
            max_skip     = int(attended / (threshold / 100) - total)
            action       = f"Can skip {max_skip} class(es)" if max_skip > 0 else "No skip"
            need_to_attend = 0
        else:
            need_to_attend = int(((threshold / 100) * total - attended) / (1 - threshold / 100) + 0.9999)
            action         = f"Need to attend {need_to_attend} class(es)"
            max_skip       = 0
        subjects.append({
            'name': subject, 'attended': attended, 'total': total,
            'percentage': percent, 'action': action,
            'max_skip': max_skip, 'need_to_attend': need_to_attend,
            'status': 'safe' if percent >= threshold else 'danger'
        })
    overall_percent = (overall_attended / overall_total * 100) if overall_total > 0 else 0
    if overall_percent >= threshold:
        overall_skip = int(overall_attended / (threshold / 100) - overall_total)
        overall_need = 0
    else:
        overall_skip = 0
        overall_need = int(((threshold / 100) * overall_total - overall_attended) / (1 - threshold / 100) + 0.9999)
    return {
        'subjects': subjects,
        'overall': {
            'attended': overall_attended,
            'total': overall_total,
            'percentage': round(overall_percent, 2),
            'max_skip': overall_skip,
            'need_to_attend': overall_need
        }
    }

# ── Scheduled Daily-Update Job ─────────────────────────────────────────────────
def daily_update_job():
    logger.info("Running daily attendance update job via Telegram…")
    disabled = get_disabled_subjects()
    students = get_all_telegram_subscribed()
    for student in students:
        try:
            raw = calculate(student['roll'], student['password'])
            if not raw:
                continue
            filtered = {k: v for k, v in raw.items() if k not in disabled}
            data = process_attendance_data(filtered)
            if not data:
                continue
            text = build_attendance_text(student['roll'], data)
            send_telegram_message(student['telegram_chat_id'], text)
            logger.info(f"Sent Telegram update for {student['roll']}")
        except Exception as e:
            logger.error(f"Error sending update for {student['roll']}: {e}")

scheduler = BackgroundScheduler(daemon=True, timezone='Asia/Kolkata')
scheduler.add_job(daily_update_job, 'cron', hour=8, minute=30,
                  id='daily_update', replace_existing=True,
                  timezone='Asia/Kolkata')
scheduler.start()
logger.info("Scheduler started — daily job at 08:30 IST (Asia/Kolkata)")
setup_telegram_webhook()

# ── Flask Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/attendance", methods=["POST"])
def get_attendance():
    data = request.get_json()
    roll = data.get("roll")
    password = data.get("password")
    raw_data = calculate(roll, password)
    if raw_data:
        upsert_student(roll, password)
        upsert_subjects(raw_data.keys())
        record_login(roll, request.remote_addr or "unknown")
        disabled  = get_disabled_subjects()
        filtered  = {k: v for k, v in raw_data.items() if k not in disabled}
        processed = process_attendance_data(filtered)
        student   = get_student(roll)
        return jsonify({
            "status": "success",
            "data": processed,
            "subscription": {
                "telegram_enabled": bool(student.get("telegram_enabled")) if student else False,
                "has_telegram": bool(student.get("telegram_chat_id")) if student else False,
            }
        })
    else:
        return jsonify({"status": "error", "message": "Login failed or data unavailable"}), 401


@app.route("/api/telegram-subscribe", methods=["POST"])
def telegram_subscribe():
    data = request.get_json()
    roll     = data.get("roll")
    password = data.get("password")
    chat_id  = str(data.get("chat_id", "")).strip()

    if not roll or not password or not chat_id:
        return jsonify({"status": "error", "message": "Missing roll, password or chat_id"}), 400

    student = get_student(roll)
    if not student:
        return jsonify({"status": "error", "message": "Student not found — please log in first"}), 404

    if not os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN):
        return jsonify({"status": "error", "message": "Telegram bot not configured yet. Please contact admin."}), 503

    update_student_telegram(roll, telegram_chat_id=chat_id, telegram_enabled=1)

    try:
        raw = calculate(roll, password)
        if raw:
            disabled  = get_disabled_subjects()
            filtered  = {k: v for k, v in raw.items() if k not in disabled}
            processed = process_attendance_data(filtered)
            welcome = (
                "🎉 <b>Daily attendance alerts are now active!</b>\n"
                "You'll receive your report every morning at 8:30 AM IST.\n\n"
                + build_attendance_text(roll, processed)
            )
            send_telegram_message(chat_id, welcome)
    except Exception as e:
        logger.error(f"Welcome message error: {e}")

    return jsonify({"status": "success", "message": "Telegram alerts enabled! Check your Telegram for a welcome message."})


@app.route("/api/telegram-unsubscribe", methods=["POST"])
def telegram_unsubscribe():
    data = request.get_json()
    roll = data.get("roll")
    if not roll:
        return jsonify({"status": "error", "message": "Missing roll"}), 400
    update_student_telegram(roll, telegram_enabled=0)
    return jsonify({"status": "success", "message": "Daily Telegram updates disabled."})


@app.route("/api/subscription-status", methods=["POST"])
def subscription_status():
    data = request.get_json()
    roll = data.get("roll")
    student = get_student(roll)
    if not student:
        return jsonify({"telegram_enabled": False, "has_telegram": False})
    return jsonify({
        "telegram_enabled": bool(student.get("telegram_enabled")),
        "has_telegram":     bool(student.get("telegram_chat_id")),
    })


@app.route("/api/notice", methods=["GET"])
def public_notice():
    enabled = get_setting("notice_enabled", "0")
    if enabled != "1":
        return jsonify({"active": False, "text": ""})
    text = get_setting("notice_text", "")
    return jsonify({"active": bool(text), "text": text})


@app.route("/api/send-now", methods=["POST"])
def send_now():
    data     = request.get_json()
    roll     = data.get("roll")
    password = data.get("password")
    student  = get_student(roll)
    if not student or not student.get("telegram_chat_id"):
        return jsonify({"status": "error", "message": "Not subscribed to Telegram alerts"}), 400
    raw = calculate(roll, password)
    if not raw:
        return jsonify({"status": "error", "message": "Could not fetch attendance"}), 500
    disabled  = get_disabled_subjects()
    filtered  = {k: v for k, v in raw.items() if k not in disabled}
    processed = process_attendance_data(filtered)
    text = build_attendance_text(student['telegram_chat_id'], processed)
    ok   = send_telegram_message(student['telegram_chat_id'], text)
    return jsonify({"status": "success" if ok else "error"})


# ── Telegram Bot Webhook ──────────────────────────────────────────────────────

def _handle_status(chat_id):
    student = get_student_by_chat_id(chat_id)
    if student:
        raw = calculate(student['roll'], student['password'])
        if raw:
            disabled  = get_disabled_subjects()
            filtered  = {k: v for k, v in raw.items() if k not in disabled}
            processed = process_attendance_data(filtered)
            send_telegram_message(chat_id, build_attendance_text(student['roll'], processed), attendance_keyboard())
        else:
            send_telegram_message(chat_id, "❌ Could not fetch attendance. Please try again later.", main_menu_keyboard(is_linked=True))
    else:
        send_telegram_message(
            chat_id,
            "⚠️ No linked account found.\n\nSend:\n<code>/link ROLLNUMBER PASSWORD</code>\n\nExample:\n<code>/link 21691A0501 mypassword</code>",
            main_menu_keyboard(is_linked=False)
        )

def _handle_unlink(chat_id):
    student = get_student_by_chat_id(chat_id)
    if student:
        roll = student['roll']
        update_student_telegram(roll, telegram_enabled=0, telegram_chat_id="")
        send_telegram_message(chat_id, f"✅ <b>Unlinked successfully.</b>\nDaily updates stopped for roll <b>{roll}</b>.", main_menu_keyboard(is_linked=False))
    else:
        send_telegram_message(chat_id, "No linked account found for this chat.", main_menu_keyboard(is_linked=False))

def _handle_reset(chat_id):
    student = get_student_by_chat_id(chat_id)
    if student:
        roll = student['roll']
        update_student_telegram(roll, telegram_enabled=0, telegram_chat_id="")
        send_telegram_message(
            chat_id,
            "🔄 <b>Reset complete.</b>\nYour saved link has been cleared.\n\nSend:\n<code>/link ROLLNUMBER PASSWORD</code>",
            main_menu_keyboard(is_linked=False)
        )
    else:
        send_telegram_message(
            chat_id,
            "No linked account found.\n\nSend:\n<code>/link ROLLNUMBER PASSWORD</code>",
            main_menu_keyboard(is_linked=False)
        )

def _handle_forget(chat_id):
    student = get_student_by_chat_id(chat_id)
    if student:
        roll = student["roll"]
        update_student_telegram(roll, telegram_enabled=0, telegram_chat_id="")
        send_telegram_message(
            chat_id,
            "✅ <b>Forgot this chat.</b>\nSend <code>/start</code> again to get your Chat ID, then use <code>/link ROLLNUMBER PASSWORD</code>.",
            main_menu_keyboard(is_linked=False)
        )
    else:
        send_telegram_message(
            chat_id,
            "Send <code>/start</code> to get your Chat ID, then use <code>/link ROLLNUMBER PASSWORD</code>.",
            main_menu_keyboard(is_linked=False)
        )

def _handle_help(chat_id, is_linked=False):
    send_telegram_message(chat_id, (
        "📚 <b>MITS Attendance Bot — Help</b>\n\n"
        "Use the buttons below, or type commands:\n\n"
        "<code>/link ROLL PASS</code> — Link your MITS account\n"
        "<code>/unlink</code> — Stop daily updates\n"
        "<code>/reset</code> — Clear saved link and start over\n"
        "<code>/forget</code> — Remove this chat and get a fresh start\n"
        "<code>/status</code> — Check attendance now\n"
        "<code>/start</code> — Show welcome & Chat ID\n\n"
        "📅 Daily reports are sent at <b>8:30 AM IST</b>."
    ), main_menu_keyboard(is_linked=is_linked))


@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        return '', 200

    update = request.get_json(silent=True) or {}

    callback = update.get("callback_query", {})
    if callback:
        cb_id      = callback.get("id")
        cb_data    = callback.get("data", "")
        cb_chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))
        answer_callback_query(cb_id)

        if not cb_chat_id:
            return '', 200

        student = get_student_by_chat_id(cb_chat_id)
        is_linked = bool(student)

        if cb_data == "status":
            _handle_status(cb_chat_id)
        elif cb_data == "unlink":
            _handle_unlink(cb_chat_id)
        elif cb_data == "help":
            _handle_help(cb_chat_id, is_linked=is_linked)
        elif cb_data == "menu":
            send_telegram_message(
                cb_chat_id,
                f"🏠 <b>Main Menu</b>\n{'Roll: <b>' + student['roll'] + '</b> — linked ✅' if is_linked else 'No account linked yet.'}",
                main_menu_keyboard(is_linked=is_linked)
            )
        elif cb_data == "link_prompt":
            send_telegram_message(
                cb_chat_id,
                "To link your account, send a message in this format:\n\n"
                "<code>/link ROLLNUMBER PASSWORD</code>\n\n"
                "Example:\n<code>/link 21691A0501 mypassword</code>"
            )
        elif cb_data == "forget":
            _handle_forget(cb_chat_id)

        return '', 200

    message = update.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    text    = message.get("text", "").strip()

    if not chat_id or not text:
        return '', 200

    student   = get_student_by_chat_id(chat_id)
    is_linked = bool(student)

    if text.startswith("/start"):
        reply = (
            f"👋 <b>Welcome to MITS Attendance Bot!</b>\n\n"
            f"🆔 Your Chat ID: <code>{chat_id}</code>\n\n"
            f"Bot: <b>@mitsattendancebot</b>\n\n"
        )
        if is_linked:
            reply += f"✅ Linked to roll <b>{student['roll']}</b>. Use the buttons below:"
        else:
            reply += (
                f"To get started, link your MITS account:\n"
                f"<code>/link ROLLNUMBER PASSWORD</code>\n\n"
                f"Or tap <b>Link My Account</b> below for instructions.\n\n"
                f"If you were linked before, send <code>/reset</code> first."
            )
        send_telegram_message(chat_id, reply, main_menu_keyboard(is_linked=is_linked))

    elif text.startswith("/link "):
        parts = text.split(maxsplit=2)
        if len(parts) >= 3:
            roll, password = parts[1].upper(), parts[2]
            raw = calculate(roll, password)
            if raw:
                upsert_student(roll, password)
                upsert_subjects(raw.keys())
                update_student_telegram(roll, telegram_chat_id=chat_id, telegram_enabled=1)
                disabled  = get_disabled_subjects()
                filtered  = {k: v for k, v in raw.items() if k not in disabled}
                processed = process_attendance_data(filtered)
                welcome = (
                    f"✅ <b>Linked successfully!</b> Roll: <b>{roll}</b>\n"
                    f"You'll get daily reports at 8:30 AM IST.\n\n"
                    + build_attendance_text(roll, processed)
                )
                send_telegram_message(chat_id, welcome, attendance_keyboard())
            else:
                send_telegram_message(chat_id, "❌ Invalid credentials. Check your roll number and password.", main_menu_keyboard(is_linked=False))
        else:
            send_telegram_message(chat_id, "Usage:\n<code>/link ROLLNUMBER PASSWORD</code>\n\nExample:\n<code>/link 21691A0501 mypassword</code>")

    elif text == "/unlink":
        _handle_unlink(chat_id)
    elif text == "/reset":
        _handle_reset(chat_id)
    elif text == "/forget":
        _handle_forget(chat_id)
    elif text == "/status":
        _handle_status(chat_id)
    elif text == "/help":
        _handle_help(chat_id, is_linked=is_linked)
    else:
        send_telegram_message(
            chat_id,
            "Use the buttons below or type a command.",
            main_menu_keyboard(is_linked=is_linked)
        )

    return '', 200


# ── Admin Panel Routes ────────────────────────────────────────────────────────

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    error = None
    page_mode = request.args.get("step", "login")

    if request.method == "POST":
        step = request.form.get("step", "login")

        if step == "login":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            if username == ADMIN_USER and password == ADMIN_PASS:
                otp = generate_otp()
                store_otp(otp)
                ip = request.remote_addr or "unknown"
                send_discord_message(
                    f"🔐 **Admin OTP Request**\n"
                    f"Someone is trying to log in to the admin panel.\n"
                    f"**IP:** `{ip}`\n"
                    f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"**OTP:** `{otp}` (valid for 5 minutes)"
                )
                return render_template("admin.html", page="otp", error=None)
            else:
                error = "Invalid credentials"
                return render_template("admin.html", page="login", error=error)

        elif step == "otp":
            entered = request.form.get("otp", "")
            if verify_otp(entered):
                ip = request.remote_addr or "unknown"
                send_discord_message(
                    f"✅ **Admin Login Successful**\n"
                    f"**IP:** `{ip}`\n"
                    f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )
                session["admin_logged_in"] = True
                session["admin_login_time"] = time.time()
                return redirect(url_for("admin_dashboard"))
            else:
                error = "Invalid or expired OTP. Please try again from the beginning."
                return render_template("admin.html", page="login", error=error)

    logged_in  = session.get("admin_logged_in")
    login_time = session.get("admin_login_time", 0)
    if logged_in and (time.time() - login_time <= ADMIN_SESSION_TIMEOUT):
        return redirect(url_for("admin_dashboard"))
    session.clear()
    return render_template("admin.html", page="login", error=error)


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    students   = get_all_students()
    total      = len(students)
    subscribed = sum(1 for s in students if s.get("telegram_enabled"))
    live       = live_client_count()
    subjects   = get_all_subject_settings()
    return render_template("admin.html", page="dashboard",
                           students=students, total=total,
                           subscribed=subscribed, live=live,
                           activity=_LOGIN_ACTIVITY[:20],
                           subjects=subjects)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/api/admin/stats")
@admin_required
def admin_stats():
    students   = get_all_students()
    total      = len(students)
    subscribed = sum(1 for s in students if s.get("telegram_enabled"))
    live       = live_client_count()
    return jsonify({
        "total":      total,
        "subscribed": subscribed,
        "live":       live,
        "activity":   _LOGIN_ACTIVITY[:20],
        "students": [
            {
                "roll":               s["roll"],
                "telegram_chat_id":   s.get("telegram_chat_id") or "",
                "telegram_enabled":   bool(s.get("telegram_enabled")),
                "created_at":         s.get("created_at")
            } for s in students
        ]
    })


@app.route("/api/admin/subjects", methods=["GET"])
@admin_required
def admin_subjects():
    subjects = get_all_subject_settings()
    return jsonify({"subjects": subjects})


@app.route("/api/admin/toggle-subject", methods=["POST"])
@admin_required
def admin_toggle_subject():
    data    = request.get_json()
    name    = data.get("subject_name")
    enabled = data.get("enabled")
    if name is None or enabled is None:
        return jsonify({"status": "error", "message": "Missing subject_name or enabled"}), 400
    set_subject_enabled(name, enabled)
    return jsonify({"status": "success"})


@app.route("/api/admin/notice", methods=["GET", "POST"])
@admin_required
def admin_notice():
    if request.method == "GET":
        return jsonify({
            "text":    get_setting("notice_text", ""),
            "enabled": get_setting("notice_enabled", "0") == "1"
        })
    data = request.get_json()
    text    = data.get("text", "").strip()
    enabled = bool(data.get("enabled", False))
    set_setting("notice_text", text)
    set_setting("notice_enabled", "1" if enabled else "0")
    return jsonify({"status": "success"})


@app.route("/api/admin/set-telegram-webhook", methods=["POST"])
@admin_required
def set_telegram_webhook():
    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        return jsonify({"status": "error", "message": "TELEGRAM_BOT_TOKEN not configured"}), 503
    host = request.host_url.rstrip("/")
    webhook_url = f"{host}/telegram/webhook"
    r = requests.post(
        f"{TELEGRAM_API}/bot{token}/setWebhook",
        json={"url": webhook_url},
        timeout=10
    )
    result = r.json()
    if result.get("ok"):
        return jsonify({"status": "success", "message": f"Webhook set to: {webhook_url}"})
    return jsonify({"status": "error", "message": result.get("description", "Failed")}), 500


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT)
