from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.utils import secure_filename
from database import get_db
from utils.auth import require_permission
from utils.security import allowed_file_excel
from utils.validators import normalize_header, parse_birth_date
from datetime import datetime
from config import MOSCOW_TZ
import os
import pandas as pd
import json

import_bp = Blueprint('import', __name__)


@import_bp.route('/api/admin/import_excel/check', methods=['POST'])
@require_permission('import')
def api_import_excel_check():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file or not allowed_file_excel(file.filename):
        return jsonify({'error': 'Invalid file: only .xlsx or .xls'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER_EXCEL'], filename)
    file.save(filepath)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'xlsx'
    engine = None
    if file_ext == 'xls':
        import xlrd
        engine = 'xlrd'
    else:
        engine = 'openpyxl'
    df = pd.read_excel(filepath, engine=engine)
    if df.empty:
        os.remove(filepath)
        return jsonify({'error': 'Empty file'}), 400
    df.columns = [normalize_header(str(col)) for col in df.columns]
    required_cols = ['fio']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        os.remove(filepath)
        available_cols = ', '.join(df.columns.tolist())
        return jsonify({'error': f'Отсутствуют обязательные колонки: {", ".join(missing_cols)}. Доступные колонки: {available_cols}'}), 400
    matches = []
    new_students = []
    errors = []
    with get_db() as conn:
            for idx, row in df.iterrows():
                fio_value = row.get('fio', '') if 'fio' in row.index else ''
                if pd.isna(fio_value) or fio_value == '':
                    fio = ''
                else:
                    fio = str(fio_value).strip()
                if not fio:
                    errors.append(f'Строка {idx + 2}: ФИО не указано')
                    continue
                phone = ''
                if 'phone' in row.index:
                    phone_value = row.get('phone', '')
                    if pd.notna(phone_value) and phone_value != '':
                        phone = str(phone_value).strip()
                        phone = ''.join(c for c in phone if c.isdigit())
                        if phone and not phone.startswith('8'):
                            if phone.startswith('7') and len(phone) == 11:
                                phone = '8' + phone[1:]
                            elif len(phone) == 10:
                                phone = '8' + phone
                        if phone and (not phone.startswith('8') or len(phone) != 11):
                            errors.append(f'Строка {idx + 2}: Неверный формат телефона. Требуется формат 8---------- (11 цифр)')
                            continue
                birth_date = None
                if 'birth_date' in row.index:
                    birth_date_value = row.get('birth_date', '')
                    if pd.notna(birth_date_value) and birth_date_value != '':
                        parsed_date = parse_birth_date(birth_date_value)
                        if parsed_date:
                            birth_date = parsed_date
                        else:
                            date_str = str(birth_date_value).strip()
                            if date_str and date_str.lower() not in ['nan', 'none', '']:
                                errors.append(f'Строка {idx + 2}: Неверный формат даты рождения. Требуется формат ДД.ММ.ГГГГ')
                                continue
                existing = conn.execute(
                    'SELECT id, fio, phone, birth_date FROM employees WHERE LOWER(fio) = LOWER(?)',
                    (fio,)
                ).fetchone()
                if existing:
                    matches.append({
                        'row': idx + 2,
                        'fio': fio,
                        'new_phone': phone,
                        'new_birth_date': birth_date,
                        'existing_id': existing['id'],
                        'existing_fio': existing['fio'],
                        'existing_phone': existing['phone'] or '',
                        'existing_birth_date': existing['birth_date'] or ''
                    })
                else:
                    new_students.append({
                        'row': idx + 2,
                        'fio': fio,
                        'phone': phone,
                        'birth_date': birth_date
                    })
    temp_data = {
        'matches': matches,
        'new_students': new_students,
        'filepath': filepath
    }
    temp_file = filepath + '.temp'
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(temp_data, f, ensure_ascii=False, default=str)
    return jsonify({
        'success': True,
        'matches': matches,
        'new_students': new_students,
        'errors': errors[:20],
        'temp_file': filename + '.temp'
    })


@import_bp.route('/api/admin/import_excel', methods=['POST'])
@require_permission('import')
def api_import_excel():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    temp_file = data.get('temp_file')
    update_ids = set(data.get('update_ids', []))
    
    if not temp_file:
        return jsonify({'error': 'No temp file'}), 400
    
    temp_filepath = os.path.join(current_app.config['UPLOAD_FOLDER_EXCEL'], temp_file)
    with open(temp_filepath, 'r', encoding='utf-8') as f:
        temp_data = json.load(f)
        
        matches = temp_data.get('matches', [])
        new_students = temp_data.get('new_students', [])
        original_filepath = temp_data.get('filepath')
        
        imported = 0
        updated = 0
        skipped = 0
        
        with get_db() as conn:
            for match in matches:
                if match['existing_id'] in update_ids:
                    conn.execute('''
                        UPDATE employees 
                        SET phone = ?, birth_date = ?
                        WHERE id = ?
                    ''', (match['new_phone'], match['new_birth_date'], match['existing_id']))
                    updated += 1
                else:
                    skipped += 1
            
            admin_username = session.get('admin_username', 'Unknown')
            now = datetime.now(MOSCOW_TZ).isoformat()
            
            for student in new_students:
                cur = conn.execute('''
                    INSERT INTO employees (fio, phone, birth_date, notes, absences, reprimands, vacation, vacation_history, extra_data)
                    VALUES (?, ?, ?, '', '', '', '', '[]', '{}')
                ''', (student['fio'], student['phone'], student['birth_date']))
                new_id = cur.lastrowid
                
                conn.execute('''
                    INSERT INTO employee_changes_history 
                    (employee_id, admin_id, admin_username, field_name, old_value, new_value, changed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_id, admin_id, admin_username, 
                    'Карточка создана (импорт Excel)', 
                    None, 
                    f"Создана карточка студента: {student['fio']}",
                    now
                ))
                imported += 1
            
            conn.commit()
        
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        if os.path.exists(original_filepath):
            os.remove(original_filepath)
        
        return jsonify({
            'success': True,
            'imported': imported,
            'updated': updated,
            'skipped': skipped
        })


@import_bp.route('/api/import_excel', methods=['POST'])
def api_import_excel_user():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    if not file or not allowed_file_excel(file.filename):
        return jsonify({'error': 'Недопустимый файл: только .xlsx или .xls'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER_EXCEL'], filename)
    file.save(filepath)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'xlsx'
    engine = None
    if file_ext == 'xls':
        import xlrd
        engine = 'xlrd'
    else:
        engine = 'openpyxl'
    df = pd.read_excel(filepath, engine=engine)
    if df.empty:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Файл пуст'}), 400
    df.columns = [normalize_header(str(col)) for col in df.columns]
    imported = 0
    errors = []
    with get_db() as conn:
            for idx, row in df.iterrows():
                fio_value = row.get('fio', '') if 'fio' in row.index else ''
                if pd.isna(fio_value) or fio_value == '':
                    fio = ''
                else:
                    fio = str(fio_value).strip()
                if not fio:
                    errors.append(f'Строка {idx + 2}: ФИО не указано')
                    continue
                phone = ''
                if 'phone' in row.index:
                    phone_value = row.get('phone', '')
                    if pd.notna(phone_value) and phone_value != '':
                        phone = str(phone_value).strip()
                birth_date = None
                if 'birth_date' in row.index:
                    birth_date_value = row.get('birth_date', '')
                    if pd.notna(birth_date_value) and birth_date_value != '':
                        birth_date = parse_birth_date(birth_date_value)
                existing = conn.execute('SELECT id FROM employees WHERE LOWER(fio) = LOWER(?)', (fio,)).fetchone()
                if existing:
                    conn.execute('''
                        UPDATE employees 
                        SET phone = ?, birth_date = ?
                        WHERE id = ?
                    ''', (phone, birth_date, existing['id']))
                    imported += 1
                else:
                    admin_id = session.get('admin_id')
                    admin_username = session.get('admin_username', 'Unknown')
                    now = datetime.now(MOSCOW_TZ).isoformat()
                    cur = conn.execute('''
                        INSERT INTO employees (fio, phone, birth_date, notes, absences, reprimands, vacation, vacation_history, extra_data)
                        VALUES (?, ?, ?, '', '', '', '', '[]', '{}')
                    ''', (fio, phone, birth_date))
                    new_id = cur.lastrowid
                    conn.execute('''
                        INSERT INTO employee_changes_history 
                        (employee_id, admin_id, admin_username, field_name, old_value, new_value, changed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        new_id, admin_id, admin_username, 
                        'Карточка создана (импорт Excel)', 
                        None, 
                        f"Создана карточка студента: {fio}",
                        now
                    ))
                    imported += 1
            conn.commit()
    os.remove(filepath)
    result = {
        'success': True,
        'imported': imported,
        'errors': errors[:10] if errors else []
    }
    if len(errors) > 10:
        result['errors_count'] = len(errors)
    return jsonify(result)









