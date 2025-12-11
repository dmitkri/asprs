from flask import Blueprint, request, jsonify, session, redirect, render_template, send_file
from datetime import datetime, date
from database import get_db
from utils.auth import require_permission, get_admin_role
from config import MOSCOW_TZ, PAYMENT_DETAILS
from services.payment_service import PaymentService
from services.telegram_service import TelegramService
from werkzeug.utils import secure_filename
import calendar
import sqlite3
import os
import io
import base64

import qrcode
QRCODE_AVAILABLE = True

payment_bp = Blueprint('payment', __name__)

def calculate_payment_amount(room_occupancy):
    return PaymentService.calculate_payment_amount(room_occupancy)

@payment_bp.route('/admin/payments')
def admin_payments():
    admin_id = session.get('admin_id')
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_payments'):
        return render_template('no_access.html', message='У вас нет доступа к этому разделу. Необходимо право "Управление оплатами".')
    return render_template('admin_payments.html')

@payment_bp.route('/api/employee/<int:emp_id>/payment_from_scholarship', methods=['POST'])
@require_permission('manage_payments')
def api_set_payment_from_scholarship(emp_id):
    """
    Установить флаг оплаты из стипендии для студента.
    
    Если флаг установлен, автоматически создается принятый платеж за текущий месяц.
    
    Args:
        emp_id (int): ID студента
    
    Request Body:
        JSON объект:
            - payment_from_scholarship (bool): Флаг оплаты из стипендии
    
    Returns:
        JSON объект:
            - success (bool): Успешность операции
            - message (str): Сообщение о результате
    
    Requires:
        Право доступа: 'manage_payments'
    
    Raises:
        401: Если пользователь не авторизован
        403: Если нет прав доступа
        404: Если студент не найден
    
    Example:
        POST /api/employee/1/payment_from_scholarship
        Body: {"payment_from_scholarship": true}
        
        Response:
        {
            "success": true,
            "message": "Настройка сохранена и оплата проставлена"
        }
    """
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    payment_from_scholarship = data.get('payment_from_scholarship', False)
    
    with get_db() as conn:
        student = conn.execute('SELECT id, fio, building, entrance, room_number, room_occupancy FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        conn.execute('''
            UPDATE employees
            SET payment_from_scholarship = ?
            WHERE id = ?
        ''', (1 if payment_from_scholarship else 0, emp_id))
        
        if payment_from_scholarship:
            now = datetime.now(MOSCOW_TZ)
            if now.month == 1:
                payment_month = f"{now.year - 1}-12"
            else:
                payment_month = f"{now.year}-{now.month - 1:02d}"
            payment_date = now.isoformat()
            
            tg_user = conn.execute('SELECT tg_user_id FROM tg_users WHERE employee_id = ?', (emp_id,)).fetchone()
            tg_user_id = tg_user['tg_user_id'] if tg_user else None
            
            room_occupancy = student['room_occupancy'] if student['room_occupancy'] else 1
            
            if student['building'] and student['entrance'] and student['room_number']:
                room = conn.execute('''
                    SELECT capacity FROM rooms
                    WHERE building = ? AND entrance = ? AND room_number = ?
                ''', (student['building'], student['entrance'], student['room_number'])).fetchone()
                if room and room['capacity']:
                    room_occupancy = room['capacity']
            
            payment_amount = calculate_payment_amount(room_occupancy)
            
            existing_payment = conn.execute('''
                SELECT id FROM dormitory_payments
                WHERE employee_id = ? AND payment_month = ? AND status = 'accepted'
            ''', (emp_id, payment_month)).fetchone()
            
            if not existing_payment:
                conn.execute('''
                    INSERT INTO dormitory_payments 
                    (employee_id, tg_user_id, amount, payment_date, payment_month, status, audit_admin_id, audit_comment, audited_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (emp_id, tg_user_id, payment_amount, payment_date, payment_month, 'accepted', admin_id, 'Оплата со стипендии (автоматически)', payment_date, payment_date))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Настройка сохранена' + (' и оплата проставлена' if payment_from_scholarship else '')
        })

def send_telegram_notification(tg_user_id, message, parse_mode='HTML'):
    return TelegramService.send_notification(tg_user_id, message, parse_mode)

def send_payment_notification_with_qr(tg_user_id, student_fio, amount, comment=None, start_date=None, end_date=None):
    if not tg_user_id:
        return False
    from models.employee_model import EmployeeModel
    employee = EmployeeModel.get_by_tg_user_id(tg_user_id)
    room_info = "не указана"
    if employee:
        room_parts = []
        if employee.get('building'):
            room_parts.append(str(employee['building']))
        if employee.get('entrance'):
            room_parts.append(str(employee['entrance']))
        if employee.get('room_number'):
            room_parts.append(str(employee['room_number']))
        if room_parts:
            room_info = "-".join(room_parts)
    qr_buf, qr_string = PaymentService.generate_payment_qr_code(
        amount, student_fio, room_info, comment, start_date, end_date
    )
    payment_text = PaymentService.format_payment_message(
        student_fio, amount, room_info, comment, start_date, end_date
    )
    payment_text += f"\n📸 Отсканируйте QR-код для оплаты или используйте реквизиты выше.\n\nПосле оплаты отправьте фото чека в этот чат."
    return TelegramService.send_payment_notification_with_qr(
        tg_user_id, student_fio, amount, room_info, qr_buf, comment, start_date, end_date
    )

@payment_bp.route('/api/payment/send_reminders_to_all', methods=['POST'])
@require_permission('manage_payments')
def api_send_reminders_to_all():
    admin_id = session.get('admin_id')
    now = datetime.now(MOSCOW_TZ)
    if now.month == 1:
        payment_month = f"{now.year - 1}-12"
    else:
        payment_month = f"{now.year}-{now.month - 1:02d}"
    month_names = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    month_name = month_names.get(payment_month.split('-')[1], payment_month)
    year = payment_month.split('-')[0]
    sent_count = 0
    failed_count = 0
    errors = []
    with get_db() as conn:
        students = conn.execute('''
            SELECT e.id, e.fio, e.building, e.entrance, e.room_number, tg.tg_user_id, r.capacity
            FROM employees e
            LEFT JOIN tg_users tg ON e.id = tg.employee_id
            LEFT JOIN rooms r ON e.building = r.building AND e.entrance = r.entrance AND e.room_number = r.room_number
            WHERE tg.tg_user_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM dormitory_payments dp
                WHERE dp.employee_id = e.id 
                AND dp.payment_month = ?
                AND dp.status = 'accepted'
            )
        ''', (payment_month,)).fetchall()
        if not students:
            return jsonify({
                'success': True,
                'sent': 0,
                'failed': 0,
                'message': 'Нет студентов без оплаты'
            })
        for student in students:
            if not student['tg_user_id']:
                failed_count += 1
                errors.append(f"Студент {student['fio']}: нет Telegram ID")
                continue
            capacity = student['capacity'] if student['capacity'] else 1
            payment_amount = calculate_payment_amount(capacity)
            room_str = f"{student['building']}-{student['entrance']}-{student['room_number']}" if student['building'] else "не указана"
            message = (
                f"🔔 <b>Напоминание об оплате</b>\n\n"
                f"Добрый день, {student['fio']}!\n\n"
                f"Напоминаем, что необходимо оплатить проживание за <b>{month_name} {year}</b>\n\n"
                f"🏠 Комната: {room_str}\n"
                f"💰 Сумма к оплате: {payment_amount} руб.\n\n"
                f"Для оплаты используйте кнопку 💳 Оплатить проживание в главном меню бота.\n"
                f"После оплаты отправьте фото чека."
            )
            if send_telegram_notification(student['tg_user_id'], message):
                sent_count += 1
            else:
                failed_count += 1
                errors.append(f"Студент {student['fio']}: ошибка отправки")
    return jsonify({
        'success': True,
        'sent': sent_count,
        'failed': failed_count,
        'total': len(students) if 'students' in locals() else 0,
        'errors': errors[:20] if errors else []
    })

def calculate_period_payment(start_date_str, end_date_str, monthly_amount):
    start_date = datetime.strptime(start_date_str, '%d.%m.%Y').date()
    end_date = datetime.strptime(end_date_str, '%d.%m.%Y').date()
    if start_date > end_date:
        return {
            'success': False,
            'error': 'Дата начала не может быть позже даты окончания'
        }
    month_calculations = []
    total_amount = 0
    current_date = start_date
    while current_date <= end_date:
        month_start = date(current_date.year, current_date.month, 1)
        last_day = calendar.monthrange(current_date.year, current_date.month)[1]
        month_end = date(current_date.year, current_date.month, last_day)
        period_start = max(current_date, month_start)
        period_end = min(end_date, month_end)
        
        days_in_period = (period_end - period_start).days + 1
        days_in_month = (month_end - month_start).days + 1
        month_amount = (monthly_amount / days_in_month) * days_in_period
        total_amount += month_amount
        month_names = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        month_name = month_names[current_date.month]
        
        month_calculations.append({
            'month': f"{month_name} {current_date.year}",
            'period': f"{period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}",
            'days_in_period': days_in_period,
            'days_in_month': days_in_month,
            'amount': round(month_amount, 2),
            'full_month_amount': monthly_amount
        })
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)
        
        return {
            'success': True,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'monthly_amount': monthly_amount,
            'total_days': (end_date - start_date).days + 1,
            'total_amount': round(total_amount, 2),
            'month_calculations': month_calculations
        }

@payment_bp.route('/api/payment/calculate_period', methods=['POST'])
@require_permission('manage_payments')
def api_calculate_period_payment():
    admin_id = session.get('admin_id')
    data = request.json
    start_date = data.get('start_date', '').strip()
    end_date = data.get('end_date', '').strip()
    monthly_amount = data.get('monthly_amount')
    monthly_amount = float(monthly_amount)
    
    result = calculate_period_payment(start_date, end_date, monthly_amount)
    
    if not result.get('success'):
        return jsonify(result), 400
    
    return jsonify(result)

@payment_bp.route('/api/payment/assign_to_student', methods=['POST'])
@require_permission('manage_payments')
def api_assign_payment_to_student():
    admin_id = session.get('admin_id')
    data = request.json
    employee_id = data.get('employee_id')
    amount = data.get('amount')
    start_date = data.get('start_date', '').strip()
    end_date = data.get('end_date', '').strip()
    comment = data.get('comment', '').strip()
    amount = float(amount)
    with get_db() as conn:
        student = conn.execute(
            'SELECT id, fio FROM employees WHERE id = ?',
            (employee_id,)
        ).fetchone()
        if not student:
            return jsonify({
                'success': False,
                'error': 'Студент не найден'
            }), 404
        tg_user = conn.execute(
            'SELECT tg_user_id FROM tg_users WHERE employee_id = ?',
            (employee_id,)
        ).fetchone()
        tg_user_id = tg_user['tg_user_id'] if tg_user else None
        now = datetime.now(MOSCOW_TZ)
        payment_month = f"{now.year}-{now.month:02d}"
        if start_date:
            start_dt = datetime.strptime(start_date, '%d.%m.%Y')
            payment_month = f"{start_dt.year}-{start_dt.month:02d}"
        elif end_date:
            end_dt = datetime.strptime(end_date, '%d.%m.%Y')
            payment_month = f"{end_dt.year}-{end_dt.month:02d}"
        if start_date and end_date:
            payment_comment = f"Назначено аудитом. Период: {start_date} - {end_date}. {comment}".strip()
        else:
            payment_comment = f"Назначено аудитом. {comment}".strip() if comment else "Назначено аудитом"
        conn.execute('''
            INSERT INTO dormitory_payments 
            (employee_id, tg_user_id, amount, payment_month, status, audit_admin_id, audit_comment, created_at)
            VALUES (?, ?, ?, ?, 'assigned', ?, ?, ?)
        ''', (
            employee_id,
            tg_user_id,
            amount,
            payment_month,
            admin_id,
            payment_comment,
            now.isoformat()
        ))
        conn.commit()
        notification_sent = False
        if tg_user_id:
            notification_sent = send_payment_notification_with_qr(
                tg_user_id=tg_user_id,
                student_fio=student['fio'],
                amount=amount,
                comment=comment if comment else None,
                start_date=start_date if start_date else None,
                end_date=end_date if end_date else None
            )
        message = f'Платеж на сумму {amount} руб. назначен студенту {student["fio"]}'
        if notification_sent:
            message += '. Уведомление с QR-кодом отправлено студенту в Telegram'
        elif tg_user_id:
            message += '. Не удалось отправить уведомление в Telegram'
        else:
            message += '. У студента нет Telegram ID, уведомление не отправлено'
        return jsonify({
            'success': True,
            'message': message,
            'notification_sent': notification_sent
        })

@payment_bp.route('/api/employees/search', methods=['GET'])
def api_search_employees():
    admin_id = session.get('admin_id')
    import sqlite3
    search = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 1000))
    if not search or len(search) < 2:
        if limit >= 1000:
            with get_db() as conn:
                query = '''
                    SELECT id, fio, room_number, photo, building, entrance, group_name
                    FROM employees
                    ORDER BY fio
                    LIMIT ?
                '''
                employees = conn.execute(query, (limit,)).fetchall()
                result = []
                for row in employees:
                    result.append({
                        'id': row['id'],
                        'fio': row['fio'] if row['fio'] else '',
                        'room_number': row['room_number'] if row['room_number'] else '',
                        'photo': row['photo'] if row['photo'] else None,
                        'building': row['building'] if row['building'] else None,
                        'entrance': row['entrance'] if row['entrance'] else None,
                        'group_name': row['group_name'] if row['group_name'] else None
                    })
                return jsonify({
                    'success': True,
                    'employees': result
                })
        else:
            return jsonify({
                'success': True,
                'employees': []
            })
    with get_db() as conn:
        if not hasattr(conn, 'row_factory') or conn.row_factory != sqlite3.Row:
            conn.row_factory = sqlite3.Row
        query = '''
            SELECT id, fio, room_number, photo, building, entrance, group_name
            FROM employees
            ORDER BY fio
        '''
        employees = conn.execute(query).fetchall()
        result = []
        search_lower = search.lower()
        for row in employees:
            fio = str(row['fio'] or '').lower()
            group_name = str(row['group_name'] if row['group_name'] else '').lower()
            building = str(row['building'] if row['building'] else '').lower()
            room_number = str(row['room_number'] if row['room_number'] else '').lower()
            if (search_lower in fio or 
                (group_name and search_lower in group_name) or
                (building and search_lower in building) or
                (room_number and search_lower in room_number)):
                result.append({
                    'id': row['id'],
                    'fio': row['fio'] if row['fio'] else '',
                    'room_number': row['room_number'] if row['room_number'] else '',
                    'photo': row['photo'] if row['photo'] else None,
                    'building': row['building'] if row['building'] else None,
                    'entrance': row['entrance'] if row['entrance'] else None,
                    'group_name': row['group_name'] if row['group_name'] else None
                })
                if len(result) >= limit:
                    break
    return jsonify({
        'success': True,
        'employees': result
    })

@payment_bp.route('/api/payment/generate_qr', methods=['POST'])
def api_generate_payment_qr():
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()
    if 'admin_id' not in session:
        tg_user_id = data.get('tg_user_id')
        if not tg_user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        with get_db() as conn:
            tg_user = conn.execute(
                'SELECT employee_id FROM tg_users WHERE tg_user_id = ?',
                (tg_user_id,)
            ).fetchone()
            if not tg_user or not tg_user['employee_id']:
                return jsonify({'error': 'User not registered'}), 401
            employee_id = tg_user['employee_id']
    else:
        employee_id = data.get('employee_id')
        if not employee_id:
            return jsonify({'error': 'Employee ID required'}), 400
    with get_db() as conn:
        student = conn.execute(
            'SELECT id, fio, building, entrance, room_number, room_occupancy FROM employees WHERE id = ?',
            (employee_id,)
        ).fetchone()
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    fio = student['fio'] if student['fio'] else ''
    if not fio:
        return jsonify({'error': 'Student FIO not found'}), 404
    building = (student['building'] or '').strip() if 'building' in student and student['building'] else ''
    entrance = (student['entrance'] or '').strip() if 'entrance' in student and student['entrance'] else ''
    room_number = (student['room_number'] or '').strip() if 'room_number' in student and student['room_number'] else ''
    room_occupancy = None
    with get_db() as conn:
        if building and entrance and room_number:
            room = conn.execute(
                'SELECT capacity FROM rooms WHERE building = ? AND entrance = ? AND room_number = ?',
                (building, entrance, room_number)
            ).fetchone()
            if room and 'capacity' in room and room['capacity']:
                room_occupancy = room['capacity']
            else:
                room = conn.execute('''
                    SELECT capacity FROM rooms 
                    WHERE TRIM(building) = ? 
                    AND TRIM(entrance) = ? 
                    AND TRIM(room_number) = ?
                ''', (building.strip(), entrance.strip(), room_number.strip())).fetchone()
                if room and 'capacity' in room and room['capacity']:
                    room_occupancy = room['capacity']
        if not room_occupancy:
            employee_id = student['id'] if 'id' in student else None
            if employee_id:
                room = conn.execute('''
                    SELECT DISTINCT r.capacity 
                    FROM rooms r
                    INNER JOIN employees e ON TRIM(e.building) = TRIM(r.building) 
                        AND TRIM(e.entrance) = TRIM(r.entrance) 
                        AND TRIM(e.room_number) = TRIM(r.room_number)
                    WHERE e.id = ?
                ''', (employee_id,)).fetchone()
                if room and 'capacity' in room and room['capacity']:
                    room_occupancy = room['capacity']
        if not room_occupancy and (building or entrance or room_number):
            all_rooms = conn.execute('SELECT building, entrance, room_number, capacity FROM rooms').fetchall()
            for room in all_rooms:
                room_b = (room['building'] or '').strip().lower()
                room_e = (room['entrance'] or '').strip().lower()
                room_r = (room['room_number'] or '').strip().lower()
                student_b = building.strip().lower() if building else ''
                student_e = entrance.strip().lower() if entrance else ''
                student_r = room_number.strip().lower() if room_number else ''
                if (not student_b or room_b == student_b) and \
                   (not student_e or room_e == student_e) and \
                   (not student_r or room_r == student_r):
                    room_occupancy = room['capacity']
                    break
        if not room_occupancy:
            room_occupancy = student['room_occupancy'] if 'room_occupancy' in student and student['room_occupancy'] else None
    payment_amount = PaymentService.calculate_payment_amount(room_occupancy)
    payment_purpose = f'Оплата за проживание в общежитии Сигма студента {fio}. Сумма: {payment_amount} руб.'
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
    img_buffer = io.BytesIO()
    qr_img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
    return jsonify({
        'success': True,
        'qr_code': img_base64,
        'payment_details': {
            'recipient': PAYMENT_DETAILS['recipient_name'],
            'account': PAYMENT_DETAILS['account'],
            'bic': PAYMENT_DETAILS['bic'],
            'bank': PAYMENT_DETAILS['bank_name'],
            'purpose': payment_purpose,
            'inn': PAYMENT_DETAILS['inn'],
            'amount': payment_amount
        },
        'room_occupancy': room_occupancy,
        'amount': payment_amount
    })

@payment_bp.route('/api/payment/upload_receipt', methods=['POST'])
def api_upload_receipt():
    tg_user_id = request.form.get('tg_user_id')
    with get_db() as conn:
        tg_user = conn.execute(
            'SELECT employee_id FROM tg_users WHERE tg_user_id = ?',
            (tg_user_id,)
        ).fetchone()
        employee_id = tg_user['employee_id']
        file = request.files['receipt']
        receipt_folder = 'static/receipts'
        os.makedirs(receipt_folder, exist_ok=True)
        filename = secure_filename(file.filename)
        if not filename:
            filename = 'receipt.jpg'
        filepath = os.path.join(receipt_folder, f"{employee_id}_{datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')}_{filename}")
        file.save(filepath)
        receipt_file_path = filepath
        payment_date = datetime.now(MOSCOW_TZ).isoformat()
        now = datetime.now(MOSCOW_TZ)
        if now.month == 1:
            payment_month = f"{now.year - 1}-12"
        else:
            payment_month = f"{now.year}-{now.month - 1:02d}"
        conn.execute('''
            INSERT INTO dormitory_payments (employee_id, tg_user_id, receipt_file, status, payment_date, payment_month, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, tg_user_id, receipt_file_path, 'pending', payment_date, payment_month, payment_date))
        conn.commit()
        return jsonify({
            'success': True,
            'message': 'Чек успешно загружен и ожидает проверки'
        })

@payment_bp.route('/api/payment/list', methods=['GET'])
@require_permission('manage_payments')
def api_payment_list():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    status = request.args.get('status', 'all')  # all, pending, accepted, rejected, assigned
    status_aliases = {
        'approved': 'accepted'
    }
    if status in status_aliases:
        status = status_aliases[status]
    
    valid_statuses = {'pending', 'accepted', 'rejected', 'assigned'}
    
    with get_db() as conn:
        if status == 'all':
            payments = conn.execute('''
                SELECT dp.id, dp.employee_id, dp.tg_user_id, dp.amount, dp.payment_date,
                       dp.receipt_file, dp.status, dp.audit_admin_id, dp.audit_comment,
                       dp.audited_at, dp.created_at,
                       e.fio, e.room_number, e.building, e.entrance,
                       a.fio as audit_admin_fio
                FROM dormitory_payments dp
                JOIN employees e ON dp.employee_id = e.id
                LEFT JOIN admins a ON dp.audit_admin_id = a.id
                ORDER BY dp.created_at DESC
            ''').fetchall()
        elif status in valid_statuses:
            payments = conn.execute('''
                SELECT dp.id, dp.employee_id, dp.tg_user_id, dp.amount, dp.payment_date,
                       dp.receipt_file, dp.status, dp.audit_admin_id, dp.audit_comment,
                       dp.audited_at, dp.created_at,
                       e.fio, e.room_number, e.building, e.entrance,
                       a.fio as audit_admin_fio
                FROM dormitory_payments dp
                JOIN employees e ON dp.employee_id = e.id
                LEFT JOIN admins a ON dp.audit_admin_id = a.id
                WHERE dp.status = ?
                ORDER BY dp.created_at DESC
            ''', (status,)).fetchall()
        else:
            payments = []
        
        result = []
        for payment in payments:
            result.append({
                'id': payment['id'],
                'employee_id': payment['employee_id'],
                'tg_user_id': payment['tg_user_id'],
                'fio': payment['fio'],
                'room_number': payment['room_number'],
                'building': payment['building'],
                'entrance': payment['entrance'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'receipt_file': payment['receipt_file'],
                'status': payment['status'],
                'audit_admin_fio': payment['audit_admin_fio'],
                'audit_comment': payment['audit_comment'],
                'audited_at': payment['audited_at'],
                'created_at': payment['created_at']
            })
        
        return jsonify({
            'success': True,
            'payments': result
        })

@payment_bp.route('/api/payment/approve', methods=['POST'])
@require_permission('manage_payments')
def api_payment_approve():
    admin_id = session.get('admin_id')
    data = request.json
    payment_id = data.get('payment_id')
    comment = data.get('comment', '')
    with get_db() as conn:
        audited_at = datetime.now(MOSCOW_TZ).isoformat()
        conn.execute('''
            UPDATE dormitory_payments
            SET status = ?, audit_admin_id = ?, audit_comment = ?, audited_at = ?
            WHERE id = ?
        ''', ('accepted', admin_id, comment, audited_at, payment_id))
        payment = conn.execute('''
            SELECT dp.tg_user_id, e.fio
            FROM dormitory_payments dp
            JOIN employees e ON dp.employee_id = e.id
            WHERE dp.id = ?
        ''', (payment_id,)).fetchone()
        conn.commit()
        if payment and payment['tg_user_id']:
            message = f"✅ <b>Оплата принята</b>\n\nВаш чек об оплате проживания был одобрен аудитом."
            if comment:
                message += f"\n\nКомментарий: {comment}"
            TelegramService.send_notification(payment['tg_user_id'], message, parse_mode='HTML')
        return jsonify({
            'success': True,
            'message': 'Оплата одобрена'
        })

@payment_bp.route('/api/payment/reject', methods=['POST'])
@require_permission('manage_payments')
def api_payment_reject():
    admin_id = session.get('admin_id')
    data = request.json
    payment_id = data.get('payment_id')
    comment = data.get('comment', '')
    with get_db() as conn:
        audited_at = datetime.now(MOSCOW_TZ).isoformat()
        conn.execute('''
            UPDATE dormitory_payments
            SET status = ?, audit_admin_id = ?, audit_comment = ?, audited_at = ?
            WHERE id = ?
        ''', ('rejected', admin_id, comment, audited_at, payment_id))
        payment = conn.execute('''
            SELECT dp.tg_user_id, e.fio
            FROM dormitory_payments dp
            JOIN employees e ON dp.employee_id = e.id
            WHERE dp.id = ?
        ''', (payment_id,)).fetchone()
        conn.commit()
        if payment and payment['tg_user_id']:
            message = f"❌ <b>Оплата не принята</b>\n\nВаш чек об оплате проживания был отклонен аудитом."
            if comment:
                message += f"\n\nПричина: {comment}"
            TelegramService.send_notification(payment['tg_user_id'], message, parse_mode='HTML')
        return jsonify({
            'success': True,
            'message': 'Оплата отклонена'
        })

@payment_bp.route('/api/payment/receipt/<int:payment_id>', methods=['GET'])
@require_permission('manage_payments')
def api_payment_receipt(payment_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        payment = conn.execute('''
            SELECT receipt_file FROM dormitory_payments WHERE id = ?
        ''', (payment_id,)).fetchone()
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        receipt_file = payment['receipt_file']
        if not receipt_file or not os.path.exists(receipt_file):
            return jsonify({'error': 'Receipt file not found'}), 404
        
        return send_file(receipt_file)
