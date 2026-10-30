from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
import random
import string
import os
import json
import threading
from functools import wraps

# ── MQTT ──────────────────────────────────────────────────────────────
import paho.mqtt.client as mqtt_lib

app = Flask(__name__)
app.secret_key = 'checkinplus_secret_key_2024'

# ════════════════════════════════════════════════════════════════════
#  KONFIGURASI
# ════════════════════════════════════════════════════════════════════

# ─── PostgreSQL ───────────────────────────────────────────────────────
DB_CONFIG = {
    'dbname'  : os.getenv('DB_NAME',     'checkin_hotels'),
    'user'    : os.getenv('DB_USER',     'hoteluser'),
    'password': os.getenv('DB_PASSWORD', 'hotelpassword123'),
    'host'    : os.getenv('DB_HOST',     'localhost'),
    'port'    : int(os.getenv('DB_PORT', 5432)),
}

# ─── MQTT ─────────────────────────────────────────────────────────────
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT   = int(os.getenv('MQTT_PORT', 1883))

# Topic convention:
#   hotel/kamar/{nomor}/status   → ESP32 → Server  (telemetri sensor)
#   hotel/kamar/{nomor}/command  → Server → ESP32  (perintah)
#   hotel/alert                  → ESP32 → Server  (alarm asap / darurat)

# ─── Kredensial ───────────────────────────────────────────────────────
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'gacorbismillah'
ESP32_API_KEY  = 'esp32-hotel-secret-2024'

# ─── Data Kamar ───────────────────────────────────────────────────────
ROOMS = {
    'Standard': {
        'rooms'      : ['101', '102', '103', '104', '105'],
        'price'      : 500000,
        'description': 'Standard rooms consist of 5 units, equipped with a comfortable bed, '
                       'air conditioning, Wi-Fi, Smart TV, and a private bathroom.'
    },
    'Suite': {
        'rooms'      : ['201', '202', '203', '204', '205'],
        'price'      : 1500000,
        'description': 'Suite rooms consist of 5 units, featuring a spacious layout, premium '
                       'bedding, high-speed Wi-Fi, Smart TV, minibar, and exclusive bathroom amenities.'
    }
}
ALL_ROOMS = ['101','102','103','104','105','201','202','203','204','205']


# ════════════════════════════════════════════════════════════════════
#  DATABASE — PostgreSQL
# ════════════════════════════════════════════════════════════════════

def get_db():
    """Buka koneksi PostgreSQL baru. Gunakan di dalam konteks request."""
    conn = psycopg2.connect(**DB_CONFIG)
    # RealDictCursor → hasil query berupa dict (seperti sqlite3.Row)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


def init_db():
    """Buat tabel jika belum ada dan seed data awal."""
    conn = get_db()
    c    = conn.cursor()

    # ── Tabel bookings ──────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id                SERIAL PRIMARY KEY,
            booking_code      TEXT UNIQUE NOT NULL,
            nama              TEXT NOT NULL,
            email             TEXT NOT NULL,
            checkin_date      TEXT NOT NULL,
            checkin_time      TEXT NOT NULL,
            checkout_time     TEXT NOT NULL,
            lama_menginap     INTEGER NOT NULL,
            tipe_kamar        TEXT NOT NULL,
            nomor_kamar       TEXT NOT NULL,
            metode_pembayaran TEXT DEFAULT \'QRIS\',
            total_pembayaran  INTEGER NOT NULL,
            otp_locker        TEXT,
            status            TEXT DEFAULT \'Menunggu Pembayaran\',
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Tabel room_status ───────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS room_status (
            nomor_kamar  TEXT PRIMARY KEY,
            tipe_kamar   TEXT NOT NULL,
            status_kamar TEXT DEFAULT \'Available\',
            updated_at   TEXT DEFAULT to_char(NOW(),\'YYYY-MM-DD HH24:MI\'),
            updated_by   TEXT DEFAULT \'system\'
        )
    ''')

    # ── Tabel esp32_status (telemetri real-time dari ESP32) ─────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS esp32_status (
            nomor_kamar   TEXT PRIMARY KEY,
            lampu_kipas   INTEGER DEFAULT 0,
            rfid_aktif    INTEGER DEFAULT 0,
            pintu_terbuka INTEGER DEFAULT 0,
            loker_terbuka INTEGER DEFAULT 0,
            nilai_gas     INTEGER DEFAULT 0,
            ambang_gas    INTEGER DEFAULT 800,
            ada_asap      INTEGER DEFAULT 0,
            pir_loker     INTEGER DEFAULT 0,
            pir_slot      INTEGER DEFAULT 0,
            mode          TEXT    DEFAULT \'standby\',
            rfid_sisa_dtk INTEGER DEFAULT 0,
            wifi_rssi     INTEGER DEFAULT 0,
            updated_at    TEXT    DEFAULT to_char(NOW(),\'YYYY-MM-DD HH24:MI:SS\')
        )
    ''')

    # ── Seed room_status jika kosong ────────────────────────────────
    c.execute('SELECT COUNT(*) AS cnt FROM room_status')
    if c.fetchone()['cnt'] == 0:
        rooms_data = [
            ('101','Standard'),('102','Standard'),('103','Standard'),
            ('104','Standard'),('105','Standard'),
            ('201','Suite'),('202','Suite'),('203','Suite'),
            ('204','Suite'),('205','Suite'),
        ]
        c.executemany(
            "INSERT INTO room_status (nomor_kamar, tipe_kamar, status_kamar) "
            "VALUES (%s, %s, 'Available')",
            rooms_data
        )

    conn.commit()
    conn.close()
    print('[DB] PostgreSQL: tabel siap.')


# ════════════════════════════════════════════════════════════════════
#  MQTT CLIENT
# ════════════════════════════════════════════════════════════════════

mqtt_client = mqtt_lib.Client(mqtt_lib.CallbackAPIVersion.VERSION2, client_id='flask-smart-hotel')

def _on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f'[MQTT] Terhubung ke broker {MQTT_BROKER}:{MQTT_PORT}')
        # Subscribe semua topik status dari semua kamar
        client.subscribe('hotel/kamar/+/status')
        client.subscribe('hotel/alert')
        print('[MQTT] Subscribe: hotel/kamar/+/status | hotel/alert')
    else:
        print(f'[MQTT] Gagal connect, rc={rc}')

def _on_mqtt_message(client, userdata, msg):
    """
    Terima pesan dari ESP32 via MQTT.
    Topic: hotel/kamar/{nomor}/status
    Payload JSON: {lampu_kipas, rfid_aktif, pintu_terbuka, loker_terbuka,
                   nilai_gas, ambang_gas, ada_asap, pir_loker, pir_slot,
                   mode, rfid_sisa_dtk, wifi_rssi}
    """
    topic   = msg.topic
    payload = msg.payload.decode('utf-8', errors='replace')

    try:
        data = json.loads(payload)
    except Exception:
        print(f'[MQTT] Payload bukan JSON: {payload}')
        return

    # ── Alert (alarm asap darurat) ──────────────────────────────────
    if topic == 'hotel/alert':
        nomor_kamar = data.get('nomor_kamar', '')
        print(f'[MQTT ALERT] Kamar {nomor_kamar}: {data}')
        if nomor_kamar:
            _update_esp32_status_db(nomor_kamar, data)
        return

    # ── Status sensor periodik ──────────────────────────────────────
    # topic format: hotel/kamar/101/status
    parts = topic.split('/')
    if len(parts) == 4 and parts[0] == 'hotel' and parts[1] == 'kamar':
        nomor_kamar = parts[2]
        print(f'[MQTT] Status kamar {nomor_kamar}: {data}')
        _update_esp32_status_db(nomor_kamar, data)

def _update_esp32_status_db(nomor_kamar: str, data: dict):
    """Update tabel esp32_status dari data MQTT (thread-safe)."""
    try:
        conn    = get_db()
        c       = conn.cursor()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        fields = (
            int(bool(data.get('lampu_kipas',   False))),
            int(bool(data.get('rfid_aktif',    False))),
            int(bool(data.get('pintu_terbuka', False))),
            int(bool(data.get('loker_terbuka', False))),
            int(data.get('nilai_gas',  0)),
            int(data.get('ambang_gas', 800)),
            int(bool(data.get('ada_asap',  False))),
            int(bool(data.get('pir_loker', False))),
            int(bool(data.get('pir_slot',  False))),
            data.get('mode', 'standby'),
            int(data.get('rfid_sisa_dtk', 0)),
            int(data.get('wifi_rssi',     0)),
            now_str,
        )

        c.execute('SELECT nomor_kamar FROM esp32_status WHERE nomor_kamar = %s', (nomor_kamar,))
        if c.fetchone():
            c.execute('''
                UPDATE esp32_status SET
                    lampu_kipas=%s, rfid_aktif=%s, pintu_terbuka=%s, loker_terbuka=%s,
                    nilai_gas=%s, ambang_gas=%s, ada_asap=%s, pir_loker=%s, pir_slot=%s,
                    mode=%s, rfid_sisa_dtk=%s, wifi_rssi=%s, updated_at=%s
                WHERE nomor_kamar = %s
            ''', fields + (nomor_kamar,))
        else:
            c.execute('''
                INSERT INTO esp32_status (
                    lampu_kipas, rfid_aktif, pintu_terbuka, loker_terbuka,
                    nilai_gas, ambang_gas, ada_asap, pir_loker, pir_slot,
                    mode, rfid_sisa_dtk, wifi_rssi, updated_at, nomor_kamar)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ''', fields + (nomor_kamar,))

        # Jika ada asap → update room_status juga
        if data.get('ada_asap'):
            c.execute(
                "UPDATE room_status SET status_kamar='ALARM ASAP', "
                "updated_at=%s, updated_by='ESP32' WHERE nomor_kamar=%s",
                (now_str, nomor_kamar)
            )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[MQTT DB ERROR] {e}')

def publish_command(nomor_kamar: str, command: dict):
    """
    Kirim perintah ke ESP32 via MQTT.
    Contoh: publish_command('101', {'cmd': 'buka_loker'})
    """
    topic   = f'hotel/kamar/{nomor_kamar}/command'
    payload = json.dumps(command)
    mqtt_client.publish(topic, payload, qos=1)
    print(f'[MQTT] Publish → {topic}: {payload}')

def start_mqtt():
    """Jalankan MQTT client di background thread."""
    mqtt_client.on_connect = _on_mqtt_connect
    mqtt_client.on_message = _on_mqtt_message
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        t = threading.Thread(target=mqtt_client.loop_forever, daemon=True)
        t.start()
        print('[MQTT] Background thread dimulai.')
    except Exception as e:
        print(f'[MQTT] Gagal connect ke broker: {e} — lanjut tanpa MQTT.')


# ════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def cek_api_key(data):
    return data.get('api_key', '') == ESP32_API_KEY

def auto_update_booking_statuses():
    conn    = get_db()
    c       = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Pembayaran Berhasil → Check In jika waktu check-in sudah tiba
    c.execute('''
        UPDATE bookings SET status = \'Check In\'
        WHERE status = \'Pembayaran Berhasil\'
          AND (checkin_date || \' \' || checkin_time) <= %s
    ''', (now_str,))

    # Check In → Check Out jika checkout_time sudah lewat
    c.execute('''
        SELECT nomor_kamar FROM bookings
        WHERE status = \'Check In\' AND checkout_time <= %s
    ''', (now_str,))
    checked_out = [r['nomor_kamar'] for r in c.fetchall()]

    if checked_out:
        c.execute('''
            UPDATE bookings SET status = \'Check Out\'
            WHERE status = \'Check In\' AND checkout_time <= %s
        ''', (now_str,))
        c.execute(f'''
            UPDATE room_status SET status_kamar = \'Menunggu Dibersihkan\',
            updated_at = %s, updated_by = \'system\'
            WHERE nomor_kamar = ANY(%s)
        ''', (now_str, checked_out))

    # Pastikan room_status sync dengan booking aktif
    c.execute('''
        UPDATE room_status SET status_kamar = \'Check In\',
        updated_at = %s, updated_by = \'system\'
        WHERE nomor_kamar IN (
            SELECT nomor_kamar FROM bookings WHERE status = \'Check In\'
        )
    ''', (now_str,))

    conn.commit()
    conn.close()

def generate_booking_code():
    return 'BK' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def get_room_availability(nomor_kamar, checkin_date, checkin_time, lama_menginap,
                           exclude_booking_code=None):
    conn = get_db()
    c    = conn.cursor()

    c.execute('SELECT status_kamar FROM room_status WHERE nomor_kamar = %s', (nomor_kamar,))
    room_stat = c.fetchone()
    if room_stat and room_stat['status_kamar'] == 'Menunggu Dibersihkan':
        conn.close()
        return False

    checkin_dt  = datetime.strptime(f'{checkin_date} {checkin_time}', '%Y-%m-%d %H:%M')
    checkout_dt = checkin_dt + timedelta(minutes=lama_menginap * 5)

    query  = "SELECT * FROM bookings WHERE nomor_kamar = %s AND status NOT IN ('Check Out')"
    params = [nomor_kamar]
    if exclude_booking_code:
        query  += ' AND booking_code != %s'
        params.append(exclude_booking_code)

    c.execute(query, params)
    existing = c.fetchall()
    conn.close()

    for b in existing:
        b_in  = datetime.strptime(f"{b['checkin_date']} {b['checkin_time']}", '%Y-%m-%d %H:%M')
        b_out = datetime.strptime(b['checkout_time'], '%Y-%m-%d %H:%M')
        if not (checkout_dt <= b_in or checkin_dt >= b_out):
            return False
    return True


# ════════════════════════════════════════════════════════════════════
#  ROUTE WEBSITE TAMU
# ════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/daftar-kamar')
def daftar_kamar():
    return render_template('daftar_kamar.html', rooms=ROOMS)

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'GET':
        selected_room = request.args.get('room', '')
        selected_type = request.args.get('type', '')
        return render_template('booking.html', rooms=ROOMS,
                               selected_room=selected_room, selected_type=selected_type)

    data          = request.json
    nama          = data.get('nama')
    email         = data.get('email')
    checkin_date  = data.get('checkin_date')
    checkin_time  = data.get('checkin_time')
    lama_menginap = int(data.get('lama_menginap', 1))
    tipe_kamar    = data.get('tipe_kamar')
    nomor_kamar   = data.get('nomor_kamar')

    if not all([nama, email, checkin_date, checkin_time, tipe_kamar, nomor_kamar]):
        return jsonify({'success': False, 'message': 'Semua field harus diisi!'})
    if not get_room_availability(nomor_kamar, checkin_date, checkin_time, lama_menginap):
        return jsonify({'success': False, 'message': f'Kamar {nomor_kamar} tidak tersedia!'})

    checkin_dt   = datetime.strptime(f'{checkin_date} {checkin_time}', '%Y-%m-%d %H:%M')
    checkout_dt  = checkin_dt + timedelta(minutes=lama_menginap * 5)
    checkout_str = checkout_dt.strftime('%Y-%m-%d %H:%M')
    price        = ROOMS[tipe_kamar]['price']
    total        = price * lama_menginap
    booking_code = generate_booking_code()
    otp          = generate_otp()

    conn = get_db()
    c    = conn.cursor()
    c.execute('''
        INSERT INTO bookings (booking_code, nama, email, checkin_date, checkin_time,
            checkout_time, lama_menginap, tipe_kamar, nomor_kamar, total_pembayaran,
            otp_locker, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,\'Menunggu Pembayaran\')
    ''', (booking_code, nama, email, checkin_date, checkin_time, checkout_str,
          lama_menginap, tipe_kamar, nomor_kamar, total, otp))
    conn.commit()
    conn.close()

    session['booking_code'] = booking_code
    session['email']        = email
    return jsonify({'success': True, 'booking_code': booking_code, 'total': total})

@app.route('/payment/<booking_code>')
def payment(booking_code):
    conn    = get_db()
    c       = conn.cursor()
    c.execute('SELECT * FROM bookings WHERE booking_code = %s', (booking_code,))
    booking = c.fetchone()
    conn.close()
    if not booking:
        return redirect(url_for('home'))
    return render_template('payment.html', booking=dict(booking))

@app.route('/confirm-payment', methods=['POST'])
def confirm_payment():
    data         = request.json
    booking_code = data.get('booking_code')
    conn         = get_db()
    c            = conn.cursor()
    c.execute("UPDATE bookings SET status = 'Pembayaran Berhasil' WHERE booking_code = %s",
              (booking_code,))
    conn.commit()
    c.execute('SELECT * FROM bookings WHERE booking_code = %s', (booking_code,))
    booking = c.fetchone()
    conn.close()
    session['booking_code'] = booking_code
    session['email']        = booking['email']
    return jsonify({'success': True})

@app.route('/booking-success/<booking_code>')
def booking_success(booking_code):
    conn = get_db()
    c    = conn.cursor()
    c.execute('SELECT * FROM bookings WHERE booking_code = %s', (booking_code,))
    booking = c.fetchone()
    conn.close()
    if not booking:
        return redirect(url_for('home'))
    return render_template('booking_success.html', booking=dict(booking))

@app.route('/data-booking')
def data_booking():
    email = request.args.get('email', session.get('email', ''))
    return render_template('data_booking.html', email=email)

@app.route('/api/bookings')
def api_bookings():
    email = request.args.get('email', '')
    if not email:
        return jsonify([])
    auto_update_booking_statuses()
    conn = get_db()
    c    = conn.cursor()
    c.execute('SELECT * FROM bookings WHERE email = %s ORDER BY created_at DESC', (email,))
    bookings = [dict(r) for r in c.fetchall()]
    conn.close()
    now = datetime.now()
    for b in bookings:
        co            = datetime.strptime(b['checkout_time'], '%Y-%m-%d %H:%M')
        b['sisa_waktu'] = max(0, int((co - now).total_seconds()))
    return jsonify(bookings)

@app.route('/api/check-room-availability')
def check_room_availability():
    nomor_kamar   = request.args.get('nomor_kamar')
    checkin_date  = request.args.get('checkin_date')
    checkin_time  = request.args.get('checkin_time')
    lama_menginap = int(request.args.get('lama_menginap', 1))
    available     = get_room_availability(nomor_kamar, checkin_date, checkin_time, lama_menginap)
    return jsonify({'available': available})

@app.route('/api/available-rooms')
def available_rooms():
    checkin_date  = request.args.get('checkin_date')
    checkin_time  = request.args.get('checkin_time')
    lama_menginap = int(request.args.get('lama_menginap', 1))
    tipe_kamar    = request.args.get('tipe_kamar', '')
    result        = {}
    for tipe, info in ROOMS.items():
        if tipe_kamar and tipe != tipe_kamar:
            continue
        result[tipe] = [
            {'room': r, 'available': get_room_availability(r, checkin_date, checkin_time, lama_menginap)}
            for r in info['rooms']
        ]
    return jsonify(result)

@app.route('/api/extend-booking', methods=['POST'])
def extend_booking():
    data         = request.json
    booking_code = data.get('booking_code')
    extra_days   = int(data.get('extra_days', 1))
    conn         = get_db()
    c            = conn.cursor()
    c.execute('SELECT * FROM bookings WHERE booking_code = %s', (booking_code,))
    booking = c.fetchone()
    conn.close()
    if not booking:
        return jsonify({'success': False, 'message': 'Booking tidak ditemukan'})
    booking  = dict(booking)
    old_co   = datetime.strptime(booking['checkout_time'], '%Y-%m-%d %H:%M')
    new_co   = (old_co + timedelta(minutes=extra_days * 5)).strftime('%Y-%m-%d %H:%M')
    if not get_room_availability(booking['nomor_kamar'], old_co.strftime('%Y-%m-%d'),
                                  old_co.strftime('%H:%M'), extra_days, booking_code):
        return jsonify({'success': False, 'message': 'Kamar tidak tersedia untuk diperpanjang'})
    extra_cost = ROOMS[booking['tipe_kamar']]['price'] * extra_days
    conn = get_db()
    c    = conn.cursor()
    c.execute('''
        UPDATE bookings SET checkout_time=%s, lama_menginap=%s,
        total_pembayaran=%s, status=\'Menunggu Pembayaran\' WHERE booking_code=%s
    ''', (new_co, booking['lama_menginap'] + extra_days, extra_cost, booking_code))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'extra_cost': extra_cost, 'booking_code': booking_code})

@app.route('/api/check-near-checkout')
def check_near_checkout():
    email = request.args.get('email', '')
    if not email:
        return jsonify([])
    conn = get_db()
    c    = conn.cursor()
    c.execute(
        "SELECT * FROM bookings WHERE email=%s AND status IN ('Check In','Pembayaran Berhasil')",
        (email,)
    )
    bookings = [dict(r) for r in c.fetchall()]
    conn.close()
    now      = datetime.now()
    warnings = []
    for b in bookings:
        co   = datetime.strptime(b['checkout_time'], '%Y-%m-%d %H:%M')
        sisa = (co - now).total_seconds()
        if 0 < sisa <= 120:
            warnings.append({
                'booking_code': b['booking_code'],
                'nomor_kamar' : b['nomor_kamar'],
                'sisa_waktu'  : int(sisa),
                'checkout_time': b['checkout_time'],
                'can_extend'  : get_room_availability(
                    b['nomor_kamar'], co.strftime('%Y-%m-%d'),
                    co.strftime('%H:%M'), 1, b['booking_code']
                )
            })
    return jsonify(warnings)

@app.route('/notifikasi')
def notifikasi():
    return render_template('notifikasi.html')


# ════════════════════════════════════════════════════════════════════
#  ROUTE ADMIN
# ════════════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if (request.form.get('username') == ADMIN_USERNAME and
                request.form.get('password') == ADMIN_PASSWORD):
            session['admin_logged_in'] = True
            session['admin_username']  = request.form['username']
            return redirect(url_for('admin_dashboard'))
        return render_template('admin/login.html', error='Username atau password salah!')
    return render_template('admin/login.html', error=None)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    auto_update_booking_statuses()
    conn = get_db()
    c    = conn.cursor()

    c.execute("SELECT COUNT(*) AS cnt FROM bookings")
    total_bookings = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) AS cnt FROM bookings WHERE status='Check In'")
    active_checkin = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) AS cnt FROM bookings WHERE status='Menunggu Pembayaran'")
    pending_payment = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) AS cnt FROM room_status WHERE status_kamar='Menunggu Dibersihkan'")
    need_cleaning = c.fetchone()['cnt']

    c.execute("SELECT COALESCE(SUM(total_pembayaran),0) AS total FROM bookings "
              "WHERE status NOT IN ('Menunggu Pembayaran')")
    total_revenue = c.fetchone()['total']

    c.execute("SELECT * FROM bookings ORDER BY created_at DESC LIMIT 5")
    recent = [dict(r) for r in c.fetchall()]

    c.execute("SELECT * FROM room_status ORDER BY nomor_kamar")
    room_statuses = [dict(r) for r in c.fetchall()]

    c.execute("SELECT * FROM esp32_status")
    iot_data = {r['nomor_kamar']: dict(r) for r in c.fetchall()}

    conn.close()
    return render_template('admin/dashboard.html',
        total_bookings=total_bookings, active_checkin=active_checkin,
        pending_payment=pending_payment, need_cleaning=need_cleaning,
        total_revenue=total_revenue, recent=recent,
        room_statuses=room_statuses, iot_data=iot_data)

@app.route('/admin/data-booking')
@admin_required
def admin_data_booking():
    auto_update_booking_statuses()
    conn          = get_db()
    c             = conn.cursor()
    status_filter = request.args.get('status', '')
    tipe_filter   = request.args.get('tipe', '')
    search        = request.args.get('search', '')
    query         = "SELECT * FROM bookings WHERE 1=1"
    params        = []
    if status_filter:
        query += " AND status=%s";     params.append(status_filter)
    if tipe_filter:
        query += " AND tipe_kamar=%s"; params.append(tipe_filter)
    if search:
        query  += " AND (nama ILIKE %s OR email ILIKE %s OR booking_code ILIKE %s OR nomor_kamar ILIKE %s)"
        params += [f'%{search}%'] * 4
    query += " ORDER BY created_at DESC"
    c.execute(query, params)
    bookings = [dict(r) for r in c.fetchall()]
    conn.close()
    now = datetime.now()
    for b in bookings:
        b['sisa_waktu'] = max(0, int(
            (datetime.strptime(b['checkout_time'], '%Y-%m-%d %H:%M') - now).total_seconds()
        ))
    return render_template('admin/data_booking.html', bookings=bookings,
        status_filter=status_filter, tipe_filter=tipe_filter, search=search)

@app.route('/admin/room-status')
@admin_required
def admin_room_status():
    auto_update_booking_statuses()
    conn = get_db()
    c    = conn.cursor()
    c.execute('''
        SELECT rs.*, b.nama, b.checkout_time, b.booking_code
        FROM room_status rs
        LEFT JOIN bookings b
          ON rs.nomor_kamar = b.nomor_kamar AND b.status = \'Check In\'
        ORDER BY rs.nomor_kamar
    ''')
    room_statuses = [dict(r) for r in c.fetchall()]
    conn.close()
    return render_template('admin/room_status.html', room_statuses=room_statuses)

@app.route('/admin/iot-monitor')
@admin_required
def admin_iot_monitor():
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM room_status ORDER BY nomor_kamar")
    room_statuses = [dict(r) for r in c.fetchall()]
    c.execute("SELECT * FROM esp32_status ORDER BY nomor_kamar")
    iot_data = {r['nomor_kamar']: dict(r) for r in c.fetchall()}
    conn.close()
    return render_template('admin/iot_monitor.html',
                           room_statuses=room_statuses, iot_data=iot_data)

@app.route('/admin/api/update-room-status', methods=['POST'])
@admin_required
def admin_update_room_status():
    data        = request.json
    nomor_kamar = data.get('nomor_kamar')
    new_status  = data.get('status')
    allowed     = ['Available', 'Menunggu Dibersihkan', 'Check In']
    if new_status not in allowed:
        return jsonify({'success': False, 'message': 'Status tidak valid'})
    conn    = get_db()
    c       = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    c.execute(
        "UPDATE room_status SET status_kamar=%s, updated_at=%s, updated_by='admin' "
        "WHERE nomor_kamar=%s",
        (new_status, now_str, nomor_kamar)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/api/send-command', methods=['POST'])
@admin_required
def admin_send_command():
    """
    Admin kirim perintah ke ESP32 via MQTT.
    Body: {nomor_kamar, cmd}
    cmd contoh: 'buka_loker', 'kunci_loker', 'buka_pintu', 'reset'
    """
    data        = request.json
    nomor_kamar = data.get('nomor_kamar', '')
    cmd         = data.get('cmd', '')
    if not nomor_kamar or not cmd:
        return jsonify({'success': False, 'message': 'nomor_kamar dan cmd wajib diisi'})
    publish_command(nomor_kamar, {'cmd': cmd, 'from': 'admin'})
    return jsonify({'success': True, 'message': f'Perintah "{cmd}" dikirim ke kamar {nomor_kamar}'})

@app.route('/admin/api/all-bookings')
@admin_required
def admin_api_all_bookings():
    auto_update_booking_statuses()
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM bookings ORDER BY created_at DESC")
    bookings = [dict(r) for r in c.fetchall()]
    conn.close()
    now = datetime.now()
    for b in bookings:
        b['sisa_waktu'] = max(0, int(
            (datetime.strptime(b['checkout_time'], '%Y-%m-%d %H:%M') - now).total_seconds()
        ))
    return jsonify(bookings)

@app.route('/admin/api/room-statuses')
@admin_required
def admin_api_room_statuses():
    auto_update_booking_statuses()
    conn = get_db()
    c    = conn.cursor()
    c.execute('''
        SELECT rs.*, b.nama, b.checkout_time, b.booking_code
        FROM room_status rs
        LEFT JOIN bookings b
          ON rs.nomor_kamar = b.nomor_kamar AND b.status = \'Check In\'
        ORDER BY rs.nomor_kamar
    ''')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/admin/api/iot-status')
@admin_required
def admin_api_iot_status():
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM esp32_status ORDER BY nomor_kamar")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)


# ════════════════════════════════════════════════════════════════════
#  ENDPOINT IoT — KHUSUS ESP32 (HTTP, tetap dipertahankan)
#  ESP32 bisa pakai HTTP atau MQTT — keduanya didukung.
# ════════════════════════════════════════════════════════════════════

@app.route('/api/iot/otp')
def iot_get_otp():
    if not cek_api_key(request.args):
        return jsonify({'error': 'Unauthorized'}), 401
    nomor_kamar = request.args.get('nomor_kamar', '')
    if not nomor_kamar:
        return jsonify({'error': 'nomor_kamar diperlukan'}), 400

    auto_update_booking_statuses()
    conn = get_db()
    c    = conn.cursor()
    c.execute('''
        SELECT otp_locker, status, nama, checkout_time FROM bookings
        WHERE nomor_kamar = %s AND status IN (\'Pembayaran Berhasil\', \'Check In\')
        ORDER BY created_at DESC LIMIT 1
    ''', (nomor_kamar,))
    booking = c.fetchone()
    conn.close()

    if booking:
        return jsonify({
            'otp'          : booking['otp_locker'],
            'status'       : booking['status'],
            'nama'         : booking['nama'],
            'checkout_time': booking['checkout_time'],
        })
    return jsonify({'otp': None, 'status': 'Available'})

@app.route('/api/iot/status-kamar')
def iot_status_kamar():
    if not cek_api_key(request.args):
        return jsonify({'error': 'Unauthorized'}), 401
    nomor_kamar = request.args.get('nomor_kamar', '')
    if not nomor_kamar:
        return jsonify({'error': 'nomor_kamar diperlukan'}), 400
    conn = get_db()
    c    = conn.cursor()
    c.execute('SELECT * FROM room_status WHERE nomor_kamar = %s', (nomor_kamar,))
    row  = c.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Kamar tidak ditemukan'}), 404
    return jsonify(dict(row))

@app.route('/api/iot/kamar-status', methods=['POST'])
def iot_post_kamar_status():
    """
    HTTP fallback: ESP32 kirim status sensor tiap 5 detik.
    Jika ESP32 sudah pakai MQTT, endpoint ini tetap berfungsi
    sebagai fallback saat koneksi MQTT terputus.
    """
    data = request.json or {}
    if not cek_api_key(data):
        return jsonify({'error': 'Unauthorized'}), 401
    nomor_kamar = data.get('nomor_kamar', '')
    if not nomor_kamar:
        return jsonify({'error': 'nomor_kamar diperlukan'}), 400

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn    = get_db()
    c       = conn.cursor()

    fields = (
        int(bool(data.get('lampu_kipas',   False))),
        int(bool(data.get('rfid_aktif',    False))),
        int(bool(data.get('pintu_terbuka', False))),
        int(bool(data.get('loker_terbuka', False))),
        int(data.get('nilai_gas',  0)),
        int(data.get('ambang_gas', 800)),
        int(bool(data.get('ada_asap',  False))),
        int(bool(data.get('pir_loker', False))),
        int(bool(data.get('pir_slot',  False))),
        data.get('mode', 'standby'),
        int(data.get('rfid_sisa_dtk', 0)),
        int(data.get('wifi_rssi', 0)),
        now_str,
    )

    c.execute('SELECT nomor_kamar FROM esp32_status WHERE nomor_kamar=%s', (nomor_kamar,))
    if c.fetchone():
        c.execute('''
            UPDATE esp32_status SET
                lampu_kipas=%s, rfid_aktif=%s, pintu_terbuka=%s, loker_terbuka=%s,
                nilai_gas=%s, ambang_gas=%s, ada_asap=%s, pir_loker=%s, pir_slot=%s,
                mode=%s, rfid_sisa_dtk=%s, wifi_rssi=%s, updated_at=%s
            WHERE nomor_kamar=%s
        ''', fields + (nomor_kamar,))
    else:
        c.execute('''
            INSERT INTO esp32_status (
                lampu_kipas, rfid_aktif, pintu_terbuka, loker_terbuka,
                nilai_gas, ambang_gas, ada_asap, pir_loker, pir_slot,
                mode, rfid_sisa_dtk, wifi_rssi, updated_at, nomor_kamar)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', fields + (nomor_kamar,))

    if data.get('ada_asap'):
        c.execute(
            "UPDATE room_status SET status_kamar='ALARM ASAP', "
            "updated_at=%s, updated_by='ESP32' WHERE nomor_kamar=%s",
            (now_str, nomor_kamar)
        )

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'received_at': now_str})

@app.route('/api/iot/update-status-kamar', methods=['POST'])
def iot_update_status_kamar():
    data        = request.json or {}
    if not cek_api_key(data):
        return jsonify({'error': 'Unauthorized'}), 401
    nomor_kamar = data.get('nomor_kamar', '')
    status_baru = data.get('status', '')
    allowed     = ['Menunggu Dibersihkan', 'Check In', 'Available']
    if not nomor_kamar or status_baru not in allowed:
        return jsonify({'error': f'nomor_kamar wajib & status harus salah satu dari {allowed}'}), 400

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    conn    = get_db()
    c       = conn.cursor()
    c.execute(
        "UPDATE room_status SET status_kamar=%s, updated_at=%s, updated_by='ESP32' "
        "WHERE nomor_kamar=%s",
        (status_baru, now_str, nomor_kamar)
    )
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Kamar tidak ditemukan'}), 404

    if status_baru == 'Menunggu Dibersihkan':
        c.execute(
            "UPDATE bookings SET status='Check Out' "
            "WHERE nomor_kamar=%s AND status IN ('Check In','Pembayaran Berhasil')",
            (nomor_kamar,)
        )

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'nomor_kamar': nomor_kamar,
                    'status_baru': status_baru, 'updated_at': now_str})

@app.route('/api/iot/kamar-aktif')
def iot_kamar_aktif():
    if not cek_api_key(request.args):
        return jsonify({'error': 'Unauthorized'}), 401

    auto_update_booking_statuses()
    conn = get_db()
    c    = conn.cursor()
    c.execute('''
        SELECT b.*, rs.status_kamar, rs.tipe_kamar
        FROM bookings b
        JOIN room_status rs ON b.nomor_kamar = rs.nomor_kamar
        WHERE b.status IN (\'Pembayaran Berhasil\', \'Check In\')
        ORDER BY
          CASE b.status
            WHEN \'Check In\'          THEN 1
            WHEN \'Pembayaran Berhasil\' THEN 2
          END ASC,
          b.checkout_time ASC
        LIMIT 1
    ''')
    booking = c.fetchone()
    conn.close()

    if booking:
        return jsonify({
            'ada_booking'  : True,
            'nomor_kamar'  : booking['nomor_kamar'],
            'otp'          : booking['otp_locker'],
            'nama'         : booking['nama'],
            'checkout_time': booking['checkout_time'],
            'status'       : booking['status'],
            'status_kamar' : booking['status_kamar'],
            'tipe_kamar'   : booking['tipe_kamar'],
        })
    return jsonify({'ada_booking': False})

@app.route('/admin/api/kamar-aktif-esp32')
@admin_required
def admin_api_kamar_aktif_esp32():
    auto_update_booking_statuses()
    conn = get_db()
    c    = conn.cursor()
    c.execute('''
        SELECT b.nomor_kamar, b.nama, b.checkout_time, b.status, b.otp_locker,
               rs.tipe_kamar
        FROM bookings b
        JOIN room_status rs ON b.nomor_kamar = rs.nomor_kamar
        WHERE b.status IN (\'Pembayaran Berhasil\', \'Check In\')
        ORDER BY
          CASE b.status WHEN \'Check In\' THEN 1 ELSE 2 END,
          b.checkout_time ASC
        LIMIT 1
    ''')
    booking = c.fetchone()
    conn.close()
    if booking:
        return jsonify({
            'ada_booking'  : True,
            'nomor_kamar'  : booking['nomor_kamar'],
            'nama'         : booking['nama'],
            'checkout_time': booking['checkout_time'],
            'status'       : booking['status'],
            'tipe_kamar'   : booking['tipe_kamar'],
        })
    return jsonify({'ada_booking': False})


# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    init_db()
    start_mqtt()
    # host='0.0.0.0' agar bisa diakses ESP32 di jaringan lokal
    app.run(debug=False, host='0.0.0.0', port=8000)
