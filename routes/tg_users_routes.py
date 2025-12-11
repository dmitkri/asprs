from flask import Blueprint, request, jsonify, session, send_file
from database import get_db
from utils.auth import require_permission, has_permission, get_admin_role
from utils.security import allowed_file_excel, secure_filename
from datetime import datetime
import os
import pandas as pd
import io

tg_users_bp = Blueprint('tg_users', __name__)

@tg_users_bp.route('/api/admin/tg_users', methods=['GET'])
@require_permission('manage_tg_users')
def api_admin_tg_users():
    admin_id = session.get('admin_id')
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                e.id as employee_id,
                e.fio,
                e.phone,
                e.group_name,
                e.building,
                e.entrance,
                e.room_number,
                e.tg_username as student_tg_username,
                tg.tg_user_id,
                tg.tg_username as tg_username
            FROM employees e
            LEFT JOIN tg_users tg ON e.id = tg.employee_id
            ORDER BY e.fio
        """)
        students = cursor.fetchall()
        
        result = []
        for student in students:
            is_registered = student['tg_user_id'] is not None
            tg_username = student['tg_username'] or 'Не указан'
            student_tg_username = student['student_tg_username'] or '-'
            
            username_match = False
            if is_registered and student_tg_username != '-':
                tg_normalized = tg_username.lstrip('@').lower() if tg_username != 'Не указан' else ''
                student_normalized = student_tg_username.lstrip('@').lower()
                username_match = tg_normalized == student_normalized
            
            result.append({
                'employee_id': student['employee_id'],
                'fio': student['fio'] or '-',
                'phone': student['phone'] or '-',
                'group_name': student['group_name'] or '-',
                'building': student['building'] or '-',
                'entrance': student['entrance'] or '-',
                'room_number': student['room_number'] or '-',
                'room': f"{student['building'] or ''}-{student['entrance'] or ''}-{student['room_number'] or ''}" if student['building'] else '-',
                'student_tg_username': student_tg_username,
                'tg_user_id': student['tg_user_id'],
                'tg_username': tg_username,
                'is_registered': is_registered,
                'username_match': username_match
            })
        
        return jsonify({
            'success': True,
            'users': result
        })


@tg_users_bp.route('/api/admin/tg_users/export', methods=['GET'])
@require_permission('manage_tg_users')
def api_admin_tg_users_export():
    admin_id = session.get('admin_id')
    with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    e.id as employee_id,
                    e.fio,
                    e.phone,
                    e.group_name,
                    e.building,
                    e.entrance,
                    e.room_number,
                    e.tg_username as student_tg_username,
                    tg.tg_user_id,
                    tg.tg_username as tg_username
                FROM employees e
                LEFT JOIN tg_users tg ON e.id = tg.employee_id
                ORDER BY e.fio
            """)
            students = cursor.fetchall()
            
            data = []
            for student in students:
                is_registered = student['tg_user_id'] is not None
                tg_username = student['tg_username'] or 'Не указан'
                student_tg_username = student['student_tg_username'] or '-'
                
                username_match = False
                if is_registered and student_tg_username != '-':
                    tg_normalized = tg_username.lstrip('@').lower() if tg_username != 'Не указан' else ''
                    student_normalized = student_tg_username.lstrip('@').lower()
                    username_match = tg_normalized == student_normalized
                
                if not is_registered:
                    status = 'Не зарегистрирован'
                elif username_match:
                    status = 'Зарегистрирован'
                else:
                    status = '⚠ Несоответствие username'
                
                data.append({
                    'ID Студента': student['employee_id'],
                    'ФИО': student['fio'] or '-',
                    'Телефон': student['phone'] or '-',
                    'Группа': student['group_name'] or '-',
                    'Корпус': student['building'] or '-',
                    'Подъезд': student['entrance'] or '-',
                    'Комната': student['room_number'] or '-',
                    'Комната (полная)': f"{student['building'] or ''}-{student['entrance'] or ''}-{student['room_number'] or ''}" if student['building'] else '-',
                    'Username в базе': student_tg_username,
                    'ID Telegram': student['tg_user_id'] or '-',
                    'Username Telegram': tg_username if is_registered else '-',
                    'Статус': status
                })
            
            df = pd.DataFrame(data)
            
            buf = io.BytesIO()
            df.to_excel(buf, index=False, engine='openpyxl')
            buf.seek(0)
            
            filename = f'telegram_users_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
            return send_file(
                buf,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )

@tg_users_bp.route('/api/admin/tg_users/import', methods=['POST'])
@require_permission('manage_tg_users')
def api_admin_tg_users_import():
    file = request.files['file']
    filename = secure_filename(file.filename)
    from flask import current_app
    filepath = os.path.join(current_app.config.get('UPLOAD_FOLDER_EXCEL', 'uploads'), filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'xlsx'
    if file_ext == 'xls':
        import xlrd
        engine = 'xlrd'
    else:
        engine = 'openpyxl'
    df = pd.read_excel(filepath, engine=engine)
        
    from utils.validators import normalize_header
    df.columns = [normalize_header(str(col)) for col in df.columns]
    not_found = 0
    skipped = 0
    to_replace = []
    inserted = 0
    errors = []
    with get_db() as conn:
        cursor = conn.cursor()
        for idx, row in df.iterrows():
            fio = str(row.get('fio', '')).strip() if pd.notna(row.get('fio')) else ''
            employee_id = int(row.get('id')) if pd.notna(row.get('id')) and str(row.get('id')).strip() else None
            tg_username = ''
            if 'tg_username' in df.columns:
                tg_username = str(row.get('tg_username', '')).strip() if pd.notna(row.get('tg_username')) else ''
            elif 'username' in df.columns:
                tg_username = str(row.get('username', '')).strip() if pd.notna(row.get('username')) else ''
            tg_username = tg_username.lstrip('@').strip()
            if employee_id:
                cursor.execute("SELECT id, fio, tg_username FROM employees WHERE id = ?", (employee_id,))
                student = cursor.fetchone()
            elif fio:
                cursor.execute("SELECT id, fio, tg_username FROM employees WHERE LOWER(fio) = LOWER(?)", (fio,))
                student = cursor.fetchone()
            current_username = student['tg_username'] if student['tg_username'] else ''
            current_username = current_username.strip() if current_username else ''
            current_normalized = current_username.lstrip('@').lower()
            new_normalized = tg_username.lstrip('@').lower()
            if current_normalized == new_normalized:
                skipped += 1
            elif current_username:
                to_replace.append({
                    'employee_id': student['id'],
                    'fio': student['fio'],
                    'current_username': current_username,
                    'new_username': tg_username,
                    'row_number': idx + 2
                })
            else:
                cursor.execute("UPDATE employees SET tg_username = ? WHERE id = ?", (tg_username, student['id']))
                inserted += 1
        conn.commit()
    os.remove(filepath)
    return jsonify({
        'success': True,
        'inserted': inserted,
        'skipped': skipped,
        'to_replace': to_replace,
        'not_found': not_found,
        'errors': errors[:20]
    })

@tg_users_bp.route('/api/admin/tg_users/confirm_replace', methods=['POST'])
@require_permission('manage_tg_users')
def api_admin_tg_users_confirm_replace():
    data = request.get_json()
    replacements = data.get('replacements', [])
    updated = 0
    not_found = 0
    errors = []
    with get_db() as conn:
        cursor = conn.cursor()
        for replacement in replacements:
            employee_id = replacement.get('employee_id')
            new_username = replacement.get('new_username', '').strip().lstrip('@')
            cursor.execute("SELECT id, fio FROM employees WHERE id = ?", (employee_id,))
            student = cursor.fetchone()
            cursor.execute("UPDATE employees SET tg_username = ? WHERE id = ?", (new_username, employee_id))
            updated += 1
        conn.commit()
    return jsonify({
        'success': True,
        'updated': updated,
        'not_found': not_found,
        'errors': errors
    })

