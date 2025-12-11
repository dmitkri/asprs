from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from database import get_db
from utils.auth import require_permission
from utils.room_utils import get_entrance_by_number, delete_all_rooms
from utils.room_parser import parse_room_code_alternative
from utils.security import allowed_file_excel
from werkzeug.utils import secure_filename
from services.payment_service import PaymentService
from services.telegram_service import TelegramService
import os
import pandas as pd
from collections import Counter

room_bp = Blueprint('room', __name__)


@room_bp.route('/api/admin/rooms', methods=['GET'])
@require_permission('manage_rooms')
def api_list_rooms():
    now = datetime.now()
    if now.month == 1:
        payment_month = f"{now.year - 1}-12"
    else:
        payment_month = f"{now.year}-{now.month - 1:02d}"
    month = request.args.get('month', payment_month)
    with get_db() as conn:
        rooms = conn.execute('''
            SELECT r.id, r.building, r.entrance, r.floor, r.room_number, 
                   COALESCE(r.excluded_from_duty, 0) as excluded_from_duty,
                   r.category_id,
                   rc.name as category_name,
                   COALESCE(rc.max_occupants, 1) as max_occupants,
                   r.created_at
            FROM rooms r
            LEFT JOIN room_categories rc ON r.category_id = rc.id
            ORDER BY r.building, r.entrance, r.floor, r.room_number
        ''').fetchall()
        
        result = []
        for room in rooms:
            room_building = (room['building'] or '').strip()
            room_entrance = (room['entrance'] or '').strip()
            room_number = (room['room_number'] or '').strip()
            
            students = conn.execute('''
                SELECT e.id, e.fio, tg.tg_user_id, tg.tg_username
                FROM employees e
                LEFT JOIN tg_users tg ON e.id = tg.employee_id
                WHERE TRIM(COALESCE(e.building, '')) = TRIM(COALESCE(?, ''))
                AND TRIM(COALESCE(e.entrance, '')) = TRIM(COALESCE(?, ''))
                AND TRIM(COALESCE(e.room_number, '')) = TRIM(COALESCE(?, ''))
                ORDER BY e.fio
            ''', (room_building, room_entrance, room_number)).fetchall()
            
            students_list = []
            for student in students:
                payment = conn.execute('''
                    SELECT id, status, amount, payment_date
                    FROM dormitory_payments
                    WHERE employee_id = ? AND payment_month = ? AND status = 'accepted'
                ''', (student['id'], month)).fetchone()
                
                paid = payment is not None
                students_list.append({
                    'id': student['id'],
                    'fio': student['fio'],
                    'tg_user_id': student['tg_user_id'],
                    'tg_username': student['tg_username'],
                    'paid': paid,
                    'payment_date': payment['payment_date'] if payment else None
                })
            
            result.append({
                'id': room['id'],
                'building': room['building'],
                'entrance': room['entrance'],
                'floor': room['floor'],
                'room_number': room['room_number'],
                'capacity': room['max_occupants'],
                'max_occupants': room['max_occupants'],
                'excluded_from_duty': room['excluded_from_duty'] or 0,
                'category_id': room['category_id'],
                'category_name': room['category_name'] or '',
                'students_count': len(students_list),
                'students': students_list,
                'created_at': room['created_at']
            })
        
        return jsonify({'success': True, 'rooms': result, 'month': month})

@room_bp.route('/api/admin/rooms', methods=['POST'])
@require_permission('manage_rooms')
def api_create_room():
    data = request.json
    building = data.get('building', '').strip()
    entrance = data.get('entrance', '').strip()
    room_number = data.get('room_number', '').strip()
    floor = data.get('floor')
    excluded_from_duty = data.get('excluded_from_duty', False)
    category_id = data.get('category_id')
    
    if not entrance and building and room_number:
        entrance = get_entrance_by_number(building, room_number)
        if entrance:
            print(f"DEBUG: Подъезд автоматически определен при создании комнаты: {entrance} для корпуса {building}, комната {room_number}")
    
    if not building or not entrance or not room_number:
        return jsonify({'error': 'Корпус, подъезд и номер комнаты обязательны'}), 400
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT id FROM rooms WHERE building = ? AND entrance = ? AND room_number = ?',
            (building, entrance, room_number)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Комната с такими параметрами уже существует'}), 400
        
        # Если указана категория, получаем количество мест из категории
        capacity = 1  # Значение по умолчанию
        if category_id:
            category = conn.execute(
                'SELECT max_occupants FROM room_categories WHERE id = ?',
                (category_id,)
            ).fetchone()
            if category:
                capacity = category['max_occupants']
        
        conn.execute('''
            INSERT INTO rooms (building, entrance, floor, room_number, excluded_from_duty, category_id, capacity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (building, entrance, floor, room_number, 1 if excluded_from_duty else 0, category_id, capacity))
        conn.commit()
        
        return jsonify({'success': True})


@room_bp.route('/api/admin/rooms/<int:room_id>', methods=['POST'])
@require_permission('manage_rooms')
def api_update_room(room_id):
    data = request.json
    building = data.get('building', '').strip()
    entrance = data.get('entrance', '').strip()
    room_number = data.get('room_number', '').strip()
    floor = data.get('floor')
    excluded_from_duty = data.get('excluded_from_duty', False)
    category_id = data.get('category_id')
    
    if not entrance and building and room_number:
        entrance = get_entrance_by_number(building, room_number)
        if entrance:
            print(f"DEBUG: Подъезд автоматически определен при обновлении комнаты: {entrance} для корпуса {building}, комната {room_number}")
    
    if not building or not entrance or not room_number:
        return jsonify({'error': 'Корпус, подъезд и номер комнаты обязательны'}), 400
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT id FROM rooms WHERE id = ?',
            (room_id,)
        ).fetchone()
        
        if not existing:
            return jsonify({'error': 'Комната не найдена'}), 404
        
        duplicate = conn.execute(
            'SELECT id FROM rooms WHERE building = ? AND entrance = ? AND room_number = ? AND id != ?',
            (building, entrance, room_number, room_id)
        ).fetchone()
        
        if duplicate:
            return jsonify({'error': 'Комната с такими параметрами уже существует'}), 400
        
        # Если указана категория, получаем количество мест из категории
        capacity = None
        if category_id:
            category = conn.execute(
                'SELECT max_occupants FROM room_categories WHERE id = ?',
                (category_id,)
            ).fetchone()
            if category:
                capacity = category['max_occupants']
        
        # Если категория не указана или не найдена, используем текущее значение capacity из базы
        if capacity is None:
            current_room = conn.execute(
                'SELECT capacity FROM rooms WHERE id = ?',
                (room_id,)
            ).fetchone()
            if current_room:
                capacity = current_room['capacity'] or 1
        
        conn.execute('''
            UPDATE rooms 
            SET building = ?, entrance = ?, floor = ?, room_number = ?, excluded_from_duty = ?, category_id = ?, capacity = ?
            WHERE id = ?
        ''', (building, entrance, floor, room_number, 1 if excluded_from_duty else 0, category_id, capacity, room_id))
        conn.commit()
        
        return jsonify({'success': True})


@room_bp.route('/api/rooms/list', methods=['GET'])
@require_permission('edit')
def api_rooms_list_for_validation():
    with get_db() as conn:
        rooms = conn.execute('''
            SELECT DISTINCT building, entrance, room_number
            FROM rooms 
            ORDER BY building, entrance, room_number
        ''').fetchall()
        result = []
        for room in rooms:
            result.append({
                'building': room['building'],
                'entrance': room['entrance'],
                'room_number': room['room_number'],
                'display': f"{room['building']}-{room['entrance']}-{room['room_number']}"
            })
        return jsonify({'success': True, 'rooms': result})

@room_bp.route('/api/admin/rooms/<int:room_id>', methods=['DELETE'])
@require_permission('manage_rooms')
def api_delete_room(room_id):
    with get_db() as conn:
        room = conn.execute(
            'SELECT building, entrance, room_number FROM rooms WHERE id = ?',
            (room_id,)
        ).fetchone()
        
        if not room:
            return jsonify({'error': 'Комната не найдена'}), 404
        
        students_count = conn.execute(
            'SELECT COUNT(*) as count FROM employees WHERE building = ? AND entrance = ? AND room_number = ?',
            (room['building'], room['entrance'], room['room_number'])
        ).fetchone()['count']
        
        if students_count > 0:
            return jsonify({'error': f'В комнате проживает {students_count} студент(ов). Сначала переместите их в другие комнаты.'}), 400
        
        conn.execute('DELETE FROM rooms WHERE id = ?', (room_id,))
        conn.commit()
        
        return jsonify({'success': True})


@room_bp.route('/api/admin/room_categories', methods=['GET'])
@require_permission('manage_rooms')
def api_list_categories():
    with get_db() as conn:
        categories = conn.execute('''
            SELECT id, name, max_occupants, created_at
            FROM room_categories
            ORDER BY name
        ''').fetchall()
        result = []
        for cat in categories:
            result.append({
                'id': cat['id'],
                'name': cat['name'],
                'max_occupants': cat['max_occupants'] or 1,
                'created_at': cat['created_at']
            })
        return jsonify({'success': True, 'categories': result})
        print(f"Ошибка в api_list_categories: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500


@room_bp.route('/api/admin/room_categories', methods=['POST'])
@require_permission('manage_rooms')
def api_create_category():
    data = request.json
    name = data.get('name', '').strip()
    max_occupants = data.get('max_occupants', 1)
    max_occupants = int(max_occupants)
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT id FROM room_categories WHERE name = ?',
            (name,)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Категория с таким названием уже существует'}), 400
        
        cursor = conn.execute('''
            INSERT INTO room_categories (name, max_occupants)
            VALUES (?, ?)
        ''', (name, max_occupants))
        conn.commit()
        
        return jsonify({'success': True, 'id': cursor.lastrowid})


@room_bp.route('/api/admin/room_categories/<int:category_id>', methods=['POST'])
@require_permission('manage_rooms')
def api_update_category(category_id):
    data = request.json
    name = data.get('name', '').strip()
    max_occupants = data.get('max_occupants', 1)
    max_occupants = int(max_occupants)
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT id FROM room_categories WHERE id = ?',
            (category_id,)
        ).fetchone()
        
        if not existing:
            return jsonify({'error': 'Категория не найдена'}), 404
        
        duplicate = conn.execute(
            'SELECT id FROM room_categories WHERE name = ? AND id != ?',
            (name, category_id)
        ).fetchone()
        
        if duplicate:
            return jsonify({'error': 'Категория с таким названием уже существует'}), 400
        
        conn.execute('''
            UPDATE room_categories 
            SET name = ?, max_occupants = ?
            WHERE id = ?
        ''', (name, max_occupants, category_id))
        conn.commit()
        
        return jsonify({'success': True})


@room_bp.route('/api/admin/room_categories/<int:category_id>', methods=['DELETE'])
@require_permission('manage_rooms')
def api_delete_category(category_id):
    with get_db() as conn:
        category = conn.execute(
            'SELECT id, name FROM room_categories WHERE id = ?',
            (category_id,)
        ).fetchone()
        
        if not category:
            return jsonify({'error': 'Категория не найдена'}), 404
        
        rooms_count = conn.execute(
            'SELECT COUNT(*) as count FROM rooms WHERE category_id = ?',
            (category_id,)
        ).fetchone()['count']
        
        if rooms_count > 0:
            return jsonify({'error': f'Категория используется в {rooms_count} комнате(ах). Сначала удалите или измените категорию в этих комнатах.'}), 400
        
        conn.execute('DELETE FROM room_categories WHERE id = ?', (category_id,))
        conn.commit()
        
        return jsonify({'success': True})


@room_bp.route('/api/admin/rooms/import_excel', methods=['POST'])
@require_permission('manage_rooms')
def api_import_rooms_excel():
    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config.get('UPLOAD_FOLDER_EXCEL', 'uploads'), filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'xlsx'
    if file_ext == 'xls':
        import xlrd
        engine = 'xlrd'
    else:
        engine = 'openpyxl'
    df = pd.read_excel(filepath, engine=engine, header=0)
    if df.empty:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Файл пуст'}), 400
    room_col = None
    category_col = None
    entrance_col = None
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if 'комната' in col_lower or 'room' in col_lower:
            room_col = col
        elif 'категория' in col_lower or 'category' in col_lower or 'кат' in col_lower:
            category_col = col
        elif 'подъезд' in col_lower or 'entrance' in col_lower or 'под' in col_lower:
            entrance_col = col
    if room_col is None:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Не найден столбец "комната" в файле'}), 400
    if category_col is None:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Не найден столбец "категория проживания" в файле'}), 400
    if entrance_col is None:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Не найден столбец "подъезд" в файле'}), 400
    rooms_data = {}
    errors = []
    for idx, row in df.iterrows():
        room_value = row[room_col]
        if pd.isna(room_value):
            continue
        if pd.api.types.is_number(room_value):
            if pd.api.types.is_integer(room_value):
                room_code = str(int(room_value))
            else:
                room_code = str(int(float(room_value)))
        else:
            room_code = str(room_value).strip()
        if not room_code or len(room_code) < 2:
            continue
        parsed = parse_room_code(room_code)
        if not parsed or not parsed.get('building') or not parsed.get('room_number'):
            errors.append(f'Строка {idx + 2}: не удалось распарсить комнату "{room_code}". Комната должна быть в формате "81059" (корпус-комната).')
            continue
        building = parsed['building']
        room_number = parsed['room_number']
        entrance = None
        if entrance_col and not pd.isna(row.get(entrance_col, None)):
            entrance_value = str(row[entrance_col]).strip()
            if entrance_value:
                entrance = entrance_value
        if not entrance:
            errors.append(f'Строка {idx + 2}: не указан подъезд для комнаты "{room_code}". Подъезд должен быть указан в отдельном столбце.')
            continue
        category_name = None
        if not pd.isna(row[category_col]):
            category_name = str(row[category_col]).strip()
            if not category_name:
                category_name = None
        key = (building, entrance, room_number)
        if key not in rooms_data:
            rooms_data[key] = {
                'category_name': category_name
            }
        if category_name and not rooms_data[key].get('category_name'):
            rooms_data[key]['category_name'] = category_name
    
    created = 0
    updated = 0
    with get_db() as conn:
        for (building, entrance, room_number), room_info in rooms_data.items():
            category_name = room_info.get('category_name')
            category_id = None
            if category_name:
                category = conn.execute(
                    'SELECT id, max_occupants FROM room_categories WHERE name = ?',
                    (category_name,)
                ).fetchone()
                if category:
                    category_id = category['id']
                else:
                    cursor = conn.execute(
                        'INSERT INTO room_categories (name, max_occupants) VALUES (?, 1)',
                        (category_name,)
                    )
                    category_id = cursor.lastrowid
            existing = conn.execute('''
                SELECT id FROM rooms 
                WHERE building = ? AND entrance = ? AND room_number = ?
            ''', (building, entrance, room_number)).fetchone()
            if existing:
                conn.execute('''
                    UPDATE rooms 
                    SET category_id = ?
                    WHERE id = ?
                ''', (category_id, existing['id']))
                updated += 1
            else:
                conn.execute('''
                    INSERT INTO rooms (building, entrance, room_number, category_id)
                    VALUES (?, ?, ?, ?)
                ''', (building, entrance, room_number, category_id))
                created += 1
        conn.commit()
    if os.path.exists(filepath):
        os.remove(filepath)
    result = {
        'success': True,
        'created': created,
        'updated': updated,
        'errors': errors[:20] if errors else []
    }
    if len(errors) > 20:
        result['errors_count'] = len(errors)
    return jsonify(result)


@room_bp.route('/api/admin/rooms/import_excel_with_fio', methods=['POST'])
@require_permission('manage_rooms')
def api_import_rooms_excel_with_fio():
    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config.get('UPLOAD_FOLDER_EXCEL', 'uploads'), filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'xlsx'
    if file_ext == 'xls':
        import xlrd
        engine = 'xlrd'
    else:
        engine = 'openpyxl'
    df = pd.read_excel(filepath, engine=engine, header=0)
    if df.empty:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Файл пуст'}), 400
    room_col = None
    entrance_col = None
    fio_col = None
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if 'комната' in col_lower or 'room' in col_lower or 'номер' in col_lower:
            room_col = col
        elif 'подъезд' in col_lower or 'entrance' in col_lower or 'под' in col_lower:
            entrance_col = col
        elif 'фио' in col_lower or 'fio' in col_lower or 'ф.и.о' in col_lower or 'фи' in col_lower:
            fio_col = col
    if room_col is None:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Не найден столбец "комната" в файле'}), 400
    if entrance_col is None:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Не найден столбец "подъезд" в файле'}), 400
    if fio_col is None:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Не найден столбец с ФИО в файле. Ищите столбцы: "ФИО", "fio", "Ф.И.О", "ФИ"'}), 400
    rooms_created = 0
    rooms_updated = 0
    students_updated = 0
    students_not_found = []
    errors = []
    with get_db() as conn:
        rooms_data = {}
        for idx, row in df.iterrows():
            room_value = row[room_col]
            if pd.isna(room_value):
                continue
            if pd.api.types.is_number(room_value):
                if pd.api.types.is_integer(room_value):
                    room_code = str(int(room_value))
                else:
                    room_code = str(int(float(room_value)))
            else:
                room_code = str(room_value).strip()
            if not room_code or len(room_code) < 2:
                continue
            fio_value = row[fio_col]
            if pd.isna(fio_value):
                continue
            fio = str(fio_value).strip()
            if not fio:
                continue
            parsed = parse_room_code(room_code)
            if not parsed or not parsed.get('building') or not parsed.get('room_number'):
                errors.append(f'Строка {idx + 2}: не удалось распарсить комнату "{room_code}". Комната должна быть в формате "81059" (корпус-комната).')
                continue
            building = parsed['building']
            room_number = parsed['room_number']
            entrance = None
            if entrance_col and not pd.isna(row.get(entrance_col, None)):
                entrance_value = str(row[entrance_col]).strip()
                if entrance_value:
                    entrance = entrance_value
            if not entrance:
                errors.append(f'Строка {idx + 2}: не указан подъезд для комнаты "{room_code}". Подъезд должен быть указан в отдельном столбце.')
                continue
            key = (building, entrance, room_number)
            if key not in rooms_data:
                rooms_data[key] = []
            rooms_data[key].append(fio)
        for (building, entrance, room_number), fios in rooms_data.items():
            capacity = min(len(fios), 4)
            existing_room = conn.execute('''
                SELECT id FROM rooms 
                WHERE building = ? AND entrance = ? AND room_number = ?
            ''', (building, entrance, room_number)).fetchone()
            if existing_room:
                conn.execute('''
                    UPDATE rooms 
                    SET capacity = ?
                    WHERE id = ?
                ''', (capacity, existing_room['id']))
                rooms_updated += 1
            else:
                conn.execute('''
                    INSERT INTO rooms (building, entrance, room_number, capacity, excluded_from_duty, category_id)
                    VALUES (?, ?, ?, ?, 0, NULL)
                ''', (building, entrance, room_number, capacity))
                rooms_created += 1
            for fio in fios:
                student = conn.execute('''
                    SELECT id FROM employees 
                    WHERE LOWER(TRIM(fio)) = LOWER(TRIM(?))
                    LIMIT 1
                ''', (fio,)).fetchone()
                if student:
                    conn.execute('''
                        UPDATE employees 
                        SET building = ?, entrance = ?, room_number = ?
                        WHERE id = ?
                    ''', (building, entrance, room_number, student['id']))
                    students_updated += 1
                else:
                    students_not_found.append(fio)
        
        conn.commit()
    
    if os.path.exists(filepath):
        os.remove(filepath)
    result = {
        'success': True,
        'rooms_created': rooms_created,
        'rooms_updated': rooms_updated,
        'students_updated': students_updated,
        'students_not_found_count': len(students_not_found),
        'errors': errors[:20] if errors else []
    }
    if len(students_not_found) > 0:
        result['students_not_found'] = students_not_found[:20]
        if len(students_not_found) > 20:
            result['students_not_found_count'] = len(students_not_found)
    if len(errors) > 20:
        result['errors_count'] = len(errors)
    return jsonify(result)

@room_bp.route('/api/admin/rooms/delete-all', methods=['POST'])
@require_permission('manage_rooms')
def api_delete_all_rooms():
    deleted_count = delete_all_rooms()
    return jsonify({
        'success': True,
        'deleted': deleted_count,
        'message': f'Удалено комнат: {deleted_count}'
    })
