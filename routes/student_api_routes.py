from flask import Blueprint, request, jsonify, send_file
from functools import wraps
import hmac
import hashlib
import time
import os
import io
from datetime import datetime
from database import get_db
from config import SECRET_KEY, MOSCOW_TZ, PAYMENT_DETAILS, PAYMENT_RATES

student_api_bp = Blueprint('student_api', __name__)

ALLOWED_ORIGINS_STR = os.getenv('STUDENT_CABINET_ORIGINS', 'http://localhost:5002')
ALLOWED_ORIGINS = ALLOWED_ORIGINS_STR.split(',') if ALLOWED_ORIGINS_STR else ['http://localhost:5002']
MAIN_APP_PORT = int(os.getenv('MAIN_APP_PORT', 5003))
ALLOW_LOCALHOST_ANY_PORT = any('localhost' in o for o in ALLOWED_ORIGINS)

@student_api_bp.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    if origin:
        if origin in ALLOWED_ORIGINS:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Token, X-Timestamp'
            response.headers['Access-Control-Max-Age'] = '3600'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        elif ALLOW_LOCALHOST_ANY_PORT and origin.startswith('http://localhost:'):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Token, X-Timestamp'
            response.headers['Access-Control-Max-Age'] = '3600'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@student_api_bp.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        response = jsonify({})
        origin = request.headers.get('Origin')
        if origin:
            if origin in ALLOWED_ORIGINS:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Token, X-Timestamp'
                response.headers['Access-Control-Allow-Credentials'] = 'true'
            elif ALLOW_LOCALHOST_ANY_PORT and origin.startswith('http://localhost:'):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Token, X-Timestamp'
                response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

API_SECRET_KEY = os.getenv('STUDENT_API_SECRET_KEY', 'student_cabinet_api_secret_key_2024')

def verify_api_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        api_token = request.headers.get('X-API-Token')
        timestamp = request.headers.get('X-Timestamp')
        if not api_token or not timestamp:
            return jsonify({'error': 'Missing authentication headers'}), 401
        request_time = int(timestamp)
        current_time = int(time.time())
        time_diff = abs(current_time - request_time)
        if time_diff > 300:
            return jsonify({'error': 'Request timestamp expired'}), 401
        method_upper = request.method.upper()
        message = f"{timestamp}{request.path}{method_upper}"
        expected_token = hmac.new(
            API_SECRET_KEY.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(api_token, expected_token):
            return jsonify({'error': 'Invalid API token'}), 401
        return f(*args, **kwargs)
    return decorated_function

@student_api_bp.route('/api/student/auth', methods=['POST'])
@verify_api_token
def api_student_auth():
    data = request.get_json()
    username = data.get('username', '').strip().lstrip('@')
    password = data.get('password', '').strip()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.id, e.fio, e.phone, e.group_name, e.building, e.entrance, 
                   e.room_number, e.birth_date, e.photo, tg.tg_user_id
            FROM employees e
            JOIN tg_users tg ON e.id = tg.employee_id
            WHERE LOWER(REPLACE(tg.tg_username, '@', '')) = LOWER(?)
        """, (username,))
        student = cursor.fetchone()
        cursor.execute("""
            SELECT password_hash FROM student_passwords 
            WHERE employee_id = ? AND is_active = 1
            ORDER BY created_at DESC LIMIT 1
        """, (student['id'],))
        password_record = cursor.fetchone()
        from werkzeug.security import check_password_hash
        if not check_password_hash(password_record['password_hash'], password):
            return jsonify({'error': 'Invalid password', 'message': 'Неверный пароль'}), 401
        tg_user_id = student['tg_user_id']
        employee_id = student['id']
        import sys
        import importlib.util
        spec = importlib.util.spec_from_file_location("telegram_bot", "telegram_bot.py")
        telegram_bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(telegram_bot)
        code = telegram_bot.send_2fa_code_to_student(tg_user_id, employee_id)
        if not code:
            return jsonify({'error': 'Failed to send 2FA code'}), 500
        return jsonify({
            'success': True,
            '2fa_sent': True,
            'tg_user_id': tg_user_id,
            'student': {
                'id': student['id'],
                'fio': student['fio'],
                'phone': student['phone'],
                'group_name': student['group_name'],
                'building': student['building'],
                'entrance': student['entrance'],
                'room_number': student['room_number'],
                'birth_date': student['birth_date'],
                'photo': student['photo']
            }
        })


@student_api_bp.route('/api/student/verify-2fa', methods=['POST'])
@verify_api_token
def api_verify_2fa():
    data = request.get_json()
    student_id = data.get('student_id')
    code = data.get('code', '').strip()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, employee_id, tg_user_id, expires_at, used
            FROM student_2fa_codes
            WHERE employee_id = ? AND code = ? AND used = 0
            ORDER BY created_at DESC LIMIT 1
        """, (student_id, code))
        code_record = cursor.fetchone()
        expires_at = datetime.fromisoformat(code_record['expires_at'])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=MOSCOW_TZ)
        else:
            expires_at = expires_at.astimezone(MOSCOW_TZ)
        now = datetime.now(MOSCOW_TZ)
        if now > expires_at:
            return jsonify({'error': 'Code expired'}), 401
        cursor.execute("""
            UPDATE student_2fa_codes SET used = 1 WHERE id = ?
        """, (code_record['id'],))
        conn.commit()
        cursor.execute("""
            SELECT id, fio, phone, group_name, building, entrance, room_number, birth_date, photo
            FROM employees WHERE id = ?
        """, (student_id,))
        student = cursor.fetchone()
        return jsonify({
            'success': True,
            'student': dict(student)
        })


@student_api_bp.route('/api/student/profile', methods=['GET'])
@verify_api_token
def api_student_profile():
    student_id = request.args.get('student_id')
    student_id = int(student_id)
    
    with get_db() as conn:
        student = conn.execute('''
            SELECT id, fio, phone, group_name, building, entrance, room_number, 
                   birth_date, photo, notes, room_occupancy, payment_from_scholarship
            FROM employees 
            WHERE id = ?
        ''', (student_id,)).fetchone()
        
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        return jsonify({
            'success': True,
            'student': dict(student)
        })


@student_api_bp.route('/api/student/payments', methods=['GET'])
@verify_api_token
def api_student_payments():
    student_id = request.args.get('student_id')
    student_id = int(student_id)
    
    with get_db() as conn:
        payments = conn.execute('''
            SELECT id, amount, payment_date, payment_month, receipt_file, 
                   status, audit_comment, audited_at, created_at
            FROM dormitory_payments
            WHERE employee_id = ?
            ORDER BY created_at DESC
        ''', (student_id,)).fetchall()
        
        return jsonify({
            'success': True,
            'payments': [dict(p) for p in payments]
        })


@student_api_bp.route('/api/student/payment/submit', methods=['POST'])
@verify_api_token
def api_student_payment_submit():
    data = request.get_json()
    student_id = data.get('student_id')
    amount = data.get('amount')
    payment_date = data.get('payment_date')
    payment_month = data.get('payment_month')
    receipt_file = data.get('receipt_file')
    with get_db() as conn:
        student = conn.execute('SELECT id FROM employees WHERE id = ?', (student_id,)).fetchone()
        tg_user = conn.execute(
            'SELECT tg_user_id FROM tg_users WHERE employee_id = ?',
            (student_id,)
        ).fetchone()
        tg_user_id = tg_user['tg_user_id'] if tg_user else None
        receipt_path = None
        if receipt_file:
            import base64
            import os
            from config import RECEIPTS_FOLDER
            image_data = base64.b64decode(receipt_file.split(',')[1] if ',' in receipt_file else receipt_file)
            filename = f"{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            receipt_path = os.path.join(RECEIPTS_FOLDER, filename)
            with open(receipt_path, 'wb') as f:
                f.write(image_data)
            receipt_path = f"receipts/{filename}"
        assigned_payment = conn.execute('''
            SELECT id FROM dormitory_payments
            WHERE employee_id = ? AND payment_month = ? AND status = 'assigned'
            ORDER BY created_at DESC
        ''', (student_id, payment_month)).fetchone()
        if assigned_payment:
            conn.execute('''
                UPDATE dormitory_payments
                SET amount = ?, payment_date = ?, payment_month = ?, receipt_file = ?, status = 'pending'
                WHERE id = ?
            ''', (amount, payment_date, payment_month, receipt_path, assigned_payment['id']))
        else:
            conn.execute('''
                INSERT INTO dormitory_payments 
                (employee_id, tg_user_id, amount, payment_date, payment_month, receipt_file, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ''', (student_id, tg_user_id, amount, payment_date, payment_month, receipt_path))
        conn.commit()
        return jsonify({
            'success': True,
            'message': 'Payment submitted successfully'
        })


@student_api_bp.route('/api/student/rounds', methods=['GET'])
@verify_api_token
def api_student_rounds():
    student_id = request.args.get('student_id')
    student_id = int(student_id)
    with get_db() as conn:
        rounds = conn.execute('''
            SELECT id, round_date, round_time, inspector_id, inspector_tg_id,
                   building, entrance, room_number, status, vacation_info, created_at
            FROM rounds
            WHERE student_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        ''', (student_id,)).fetchall()
        assignments = conn.execute('''
            SELECT id, building, entrance, created_at
            FROM round_assignments
            WHERE student_id = ?
        ''', (student_id,)).fetchall()
        return jsonify({
            'success': True,
            'rounds': [dict(r) for r in rounds],
            'assignments': [dict(a) for a in assignments]
        })


@student_api_bp.route('/api/student/maintenance', methods=['GET'])
@verify_api_token
def api_student_maintenance():
    student_id = request.args.get('student_id')
    student_id = int(student_id)
    with get_db() as conn:
        requests = conn.execute('''
            SELECT id, building, entrance, room_number, message, status,
                   request_number, assigned_admin_fio, admin_comment,
                   created_at, assigned_at, closed_at
            FROM maintenance_requests
            WHERE employee_id = ?
            ORDER BY created_at DESC
        ''', (student_id,)).fetchall()
        requests_list = [dict(r) for r in requests]
        return jsonify({
            'success': True,
            'requests': requests_list
        })


@student_api_bp.route('/api/student/maintenance/submit', methods=['POST'])
@verify_api_token
def api_student_maintenance_submit():
    data = request.get_json()
    student_id = data.get('student_id')
    message = data.get('message')
    
    with get_db() as conn:
        student = conn.execute('''
            SELECT id, fio, building, entrance, room_number
            FROM employees WHERE id = ?
        ''', (student_id,)).fetchone()
        tg_user = conn.execute(
            'SELECT tg_user_id FROM tg_users WHERE employee_id = ?',
            (student_id,)
        ).fetchone()
        tg_user_id = tg_user['tg_user_id'] if tg_user else None
        import secrets
        request_number = f"MR-{secrets.token_hex(4).upper()}"
        conn.execute('''
            INSERT INTO maintenance_requests 
            (employee_id, tg_user_id, student_fio, building, entrance, room_number, message, status, request_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?)
        ''', (
            student_id, tg_user_id, student['fio'],
            student['building'], student['entrance'], student['room_number'],
            message, request_number
        ))
        conn.commit()
        return jsonify({
            'success': True,
            'message': 'Maintenance request submitted successfully',
            'request_number': request_number
        })


@student_api_bp.route('/api/student/events', methods=['GET'])
@verify_api_token
def api_student_events():
    student_id = request.args.get('student_id')
    student_id = int(student_id)
    with get_db() as conn:
        attendance = conn.execute('''
            SELECT ea.id, ea.event_id, ea.scanned_at,
                   e.location, e.description, e.event_date, e.event_time
            FROM event_attendance ea
            JOIN events e ON ea.event_id = e.id
            WHERE ea.employee_id = ?
            ORDER BY ea.scanned_at DESC
        ''', (student_id,)).fetchall()
        from datetime import datetime
        upcoming_events = conn.execute('''
            SELECT id, location, description, event_date, event_time, organizers
            FROM events
            WHERE event_date >= date('now')
            ORDER BY event_date, event_time
            LIMIT 20
        ''').fetchall()
        return jsonify({
            'success': True,
            'attendance': [dict(a) for a in attendance],
            'upcoming_events': [dict(e) for e in upcoming_events]
        })

@student_api_bp.route('/api/student/roommates', methods=['GET'])
@verify_api_token
def api_student_roommates():
    student_id = request.args.get('student_id')
    student_id = int(student_id)
    with get_db() as conn:
        student = conn.execute('''
            SELECT building, entrance, room_number
            FROM employees WHERE id = ?
        ''', (student_id,)).fetchone()
        if not student or not all([student['building'], student['entrance'], student['room_number']]):
            return jsonify({
                'success': True,
                'roommates': []
            })
        roommates = conn.execute('''
            SELECT id, fio, phone, group_name, photo
            FROM employees
            WHERE building = ? AND entrance = ? AND room_number = ? AND id != ?
        ''', (student['building'], student['entrance'], student['room_number'], student_id)).fetchall()
        return jsonify({
            'success': True,
            'roommates': [dict(r) for r in roommates]
        })


@student_api_bp.route('/api/student/payment-qr', methods=['GET'])
@verify_api_token
def api_student_payment_qr():
    student_id = request.args.get('student_id')
    student_id = int(student_id)
    import qrcode
    with get_db() as conn:
            student = conn.execute('''
                SELECT id, fio, building, entrance, room_number, room_occupancy
                FROM employees 
                WHERE id = ?
            ''', (student_id,)).fetchone()
            student_fio = student['fio'] or 'Неизвестно'
            student_building = (student['building'] or '').strip() if student['building'] else ''
            student_entrance = (student['entrance'] or '').strip() if student['entrance'] else ''
            student_room = (student['room_number'] or '').strip() if student['room_number'] else ''
            room_occupancy = student['room_occupancy'] if student['room_occupancy'] else None
            if student_building and student_entrance and student_room:
                room = conn.execute('''
                    SELECT r.building, r.entrance, r.room_number, 
                           COALESCE(rc.max_occupants, 1) as max_occupants
                    FROM rooms r
                    LEFT JOIN room_categories rc ON r.category_id = rc.id
                    WHERE r.building = ? AND r.entrance = ? AND r.room_number = ?
                ''', (student_building, student_entrance, student_room)).fetchone()
                if room and room['max_occupants']:
                    room_occupancy = room['max_occupants']
            if not room_occupancy or room_occupancy <= 0:
                room_occupancy = 1
            if room_occupancy > 4:
                room_occupancy = 4
            payment_amount = PAYMENT_RATES.get(room_occupancy, PAYMENT_RATES[1])
            payment_purpose = f'Оплата за проживание в общежитии Сигма студента {student_fio}. Сумма: {payment_amount} руб.'
            qr_string = (
                f"ST00012|Name={PAYMENT_DETAILS['recipient_name']}|"
                f"PersonalAcc={PAYMENT_DETAILS['account']}|"
                f"BankName={PAYMENT_DETAILS['bank_name']}|"
                f"BIC={PAYMENT_DETAILS['bic']}|"
                f"CorrespAcc={PAYMENT_DETAILS['bank_account']}|"
                f"Purpose={payment_purpose}|"
                f"Sum={payment_amount * 100}"
            )
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_string)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_buf = io.BytesIO()
            qr_img.save(qr_buf, format='PNG')
            qr_buf.seek(0)
            return send_file(
                qr_buf,
                mimetype='image/png',
                as_attachment=False
            )


@student_api_bp.route('/api/student/payment-info', methods=['GET'])
@verify_api_token
def api_student_payment_info():
    student_id = request.args.get('student_id')
    student_id = int(student_id)
    with get_db() as conn:
        student = conn.execute('''
            SELECT id, fio, building, entrance, room_number, room_occupancy
            FROM employees 
            WHERE id = ?
        ''', (student_id,)).fetchone()
        student_fio = student['fio'] or 'Неизвестно'
        student_building = (student['building'] or '').strip() if student['building'] else ''
        student_entrance = (student['entrance'] or '').strip() if student['entrance'] else ''
        student_room = (student['room_number'] or '').strip() if student['room_number'] else ''
        room_occupancy = student['room_occupancy'] if student['room_occupancy'] else None
        if student_building and student_entrance and student_room:
            room = conn.execute('''
                SELECT r.building, r.entrance, r.room_number, 
                       COALESCE(rc.max_occupants, 1) as max_occupants
                FROM rooms r
                LEFT JOIN room_categories rc ON r.category_id = rc.id
                WHERE r.building = ? AND r.entrance = ? AND r.room_number = ?
            ''', (student_building, student_entrance, student_room)).fetchone()
            if room and room['max_occupants']:
                room_occupancy = room['max_occupants']
        if not room_occupancy or room_occupancy <= 0:
            room_occupancy = 1
        if room_occupancy > 4:
            room_occupancy = 4
        payment_amount = PAYMENT_RATES.get(room_occupancy, PAYMENT_RATES[1])
        payment_purpose = f'Оплата за проживание в общежитии Сигма студента {student_fio}. Сумма: {payment_amount} руб.'
        room_info = f"{student_building}-{student_entrance}-{student_room}" if (student_building and student_entrance and student_room) else "не указана"
        return jsonify({
            'success': True,
            'student_fio': student_fio,
            'room_info': room_info,
            'room_occupancy': room_occupancy,
            'payment_amount': payment_amount,
            'payment_purpose': payment_purpose,
            'payment_details': PAYMENT_DETAILS
        })

