from flask import Blueprint, request, jsonify, session, current_app, send_file
import json
import os
import uuid
import re
from datetime import datetime, date
from database import get_db
from utils.validators import clean_expired_vacations
from utils.auth import require_permission, require_admin, get_admin_role, has_education_level_access
from utils.room_utils import get_entrance_by_number, get_room_max_occupants, get_room_current_occupants
from config import FIXED_COLS, MOSCOW_TZ, STUDENT_FILES_FOLDER, MAX_STUDENT_FILE_SIZE
from utils.security import allowed_file, allowed_student_file, validate_student_file_size, sanitize_filename
from werkzeug.utils import secure_filename

from utils.logging_config import get_logger
logger = get_logger(__name__)

employee_bp = Blueprint('employee', __name__)

@employee_bp.route('/api/columns')
def api_columns():
    """
    Получить список колонок.
    
    Возвращает список фиксированных и пользовательских колонок для отображения данных студентов.
    
    Returns:
        JSON объект с полями:
            - fixed (list[str]): Список фиксированных колонок (fio, phone, group_name, birth_date)
            - custom (list[dict]): Список пользовательских колонок с полями name и col_type
    
    Example:
        Response:
        {
            "fixed": ["fio", "phone", "group_name", "birth_date"],
            "custom": [
                {"name": "custom_field", "col_type": "text"}
            ]
        }
    """
    with get_db() as conn:
        custom = [dict(row) for row in conn.execute('SELECT name, col_type FROM custom_columns ORDER BY id').fetchall()]
    return jsonify({'fixed': FIXED_COLS, 'custom': custom})

@employee_bp.route('/api/employees')
def api_employees():
    """
    Получить список студентов с возможностью фильтрации.
    
    Поддерживает фильтрацию по поисковому запросу, группе и статусу.
    Автоматически применяет ограничения доступа на основе уровня образования администратора.
    
    Query Parameters:
        q (str, optional): Поисковый запрос. Ищет по ФИО, телефону, группе, заметкам, отпускам и т.д.
        group (str, optional): Фильтр по группе. Можно указать несколько групп через запятую.
        status (str, optional): Фильтр по статусу. Возможные значения:
            - 'ill' - только болеющие студенты
            - 'residents' - только проживающие в общежитии
            - 'non_residents' или 'no_residence' - только не проживающие
    
    Returns:
        JSON массив объектов Employee. Каждый объект содержит:
            - id (int): ID студента
            - fio (str): ФИО
            - phone (str): Телефон
            - group_name (str): Группа
            - birth_date (str): Дата рождения
            - building (str): Корпус
            - entrance (str): Подъезд
            - room_number (str): Номер комнаты
            - vacation (str): Текущий отпуск
            - vacation_history (list): История отпусков
            - extra_data (dict): Дополнительные данные
            - и другие поля
    
    Example:
        GET /api/employees?q=Иванов&group=Группа-1&status=residents
        
        Response:
        [
            {
                "id": 1,
                "fio": "Иванов Иван Иванович",
                "phone": "+7 (999) 123-45-67",
                "group_name": "Группа-1",
                ...
            }
        ]
    """
    clean_expired_vacations()
    search = request.args.get('q', '').strip().lower()
    group_filter = request.args.get('group', '').strip()
    status_filter = request.args.get('status', '').strip().lower()
    admin_id = session.get('admin_id')
    with get_db() as conn:
        query = 'SELECT * FROM employees'
        conditions = []
        params = []
        if group_filter:
            groups = [g.strip() for g in group_filter.split(',') if g.strip()]
            if len(groups) == 1:
                conditions.append('group_name = ?')
                params.append(groups[0])
            elif len(groups) > 1:
                placeholders = ','.join(['?' for _ in groups])
                conditions.append(f'group_name IN ({placeholders})')
                params.extend(groups)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY fio'
        rows = conn.execute(query, params).fetchall()
        data = []
        total_before_filter = len(rows)
        filtered_count = 0
        passed_count = 0
        
        for row in rows:
            d = dict(row)
            d['vacation'] = d.get('vacation') or ''
            d['vacation_history'] = json.loads(d.get('vacation_history', '[]'))
            extra = json.loads(d.get('extra_data', '{}'))
            d['extra_data'] = extra
            d['representatives'] = extra.get('representatives', [])

            # Получаем информацию о здоровье
            health = extra.get('health_info', {}) if isinstance(extra, dict) else {}
            current_health = health.get('current') if isinstance(health, dict) else None
            # Проверяем is_ill (может быть True, "true", или 1)
            is_ill_value = current_health.get('is_ill') if isinstance(current_health, dict) else None
            is_ill = bool(is_ill_value and (is_ill_value == True or str(is_ill_value).lower() == 'true' or is_ill_value == 1))
            
            # Получаем информацию о проживании
            building_value = str(d.get('building') or '').strip()
            entrance_value = str(d.get('entrance') or '').strip()
            room_value = str(d.get('room_number') or '').strip()
            # Считаем, что есть проживание, если указаны building и room_number (entrance может быть пустым)
            has_residence = bool(building_value and room_value)
            
            # Применяем фильтр по статусу ПЕРЕД другими фильтрами
            if status_filter:
                should_skip = False
                if status_filter == 'ill':
                    if not is_ill:
                        should_skip = True
                        filtered_count += 1
                elif status_filter == 'residents':
                    if not has_residence:
                        should_skip = True
                        filtered_count += 1
                    else:
                        passed_count += 1
                elif status_filter in ('non_residents', 'no_residence'):
                    if has_residence:
                        should_skip = True
                        filtered_count += 1
                    else:
                        passed_count += 1
                else:
                    # Для фильтра 'ill' считаем прошедшими только если is_ill=True
                    if status_filter == 'ill' and is_ill:
                        passed_count += 1
                
                if should_skip:
                    continue
                    
            # Применяем фильтр по образованию (может отфильтровать записи)
            education_level = d.get('education_level', '').strip()
            if education_level and admin_id:
                if not has_education_level_access(admin_id, education_level):
                    continue
                    
            if search:
                health_info_str = ''
                if is_ill:
                    health_info_str = 'здоровье болеет болен заболевание болезнь'
                    if current_health and current_health.get('comment'):
                        health_info_str += ' ' + str(current_health['comment']).lower()
                
                searchable = ' '.join([
                    str(d.get('fio', '')),
                    str(d.get('phone', '')),
                    str(d.get('group_name', '')),
                    str(d.get('birth_date', '')),
                    str(d.get('notes', '')),
                    str(d.get('absences', '')),
                    str(d.get('reprimands', '')),
                    str(d.get('vacation', '')),
                    health_info_str,
                ] + [str(v) for v in extra.values()] + d['vacation_history']).lower()
                words = [w.strip() for w in search.split() if w.strip()]
                if words and not all(word in searchable for word in words):
                    continue
            education_level = d.get('education_level', '').strip()
            if education_level and admin_id:
                if not has_education_level_access(admin_id, education_level):
                    continue
            data.append(d)

        logger.info(f"Returned {len(data)} employees for admin {admin_id} (filters: search='{search}', group='{group_filter}', status='{status_filter}')")
        return jsonify(data)

@employee_bp.route('/api/employee/<int:emp_id>')
def api_employee(emp_id):
    """
    Получить подробную информацию о конкретном студенте.
    
    Args:
        emp_id (int): ID студента в базе данных
    
    Returns:
        JSON объект Employee с полной информацией о студенте:
            - id (int): ID студента
            - fio (str): ФИО
            - phone (str): Телефон
            - group_name (str): Группа
            - birth_date (str): Дата рождения (пустая строка если не указана)
            - building (str): Корпус
            - entrance (str): Подъезд
            - room_number (str): Номер комнаты
            - vacation (str): Текущий отпуск
            - vacation_history (list): История отпусков
            - extra_data (dict): Дополнительные данные
            - representatives (list): Представители (для несовершеннолетних)
            - и другие поля
    
    Raises:
        404: Если студент не найден или у администратора нет доступа к уровню образования студента
    
    Example:
        GET /api/employee/1
        
        Response:
        {
            "id": 1,
            "fio": "Иванов Иван Иванович",
            "phone": "+7 (999) 123-45-67",
            ...
        }
    """
    clean_expired_vacations()
    admin_id = session.get('admin_id')
    with get_db() as conn:
        row = conn.execute('SELECT * FROM employees WHERE id = ?', (emp_id,)).fetchone()
        d = dict(row)
        education_level = d.get('education_level', '').strip()
        d['vacation'] = d.get('vacation') or ''
        d['vacation_history'] = json.loads(d.get('vacation_history', '[]'))
        # Нормализация birth_date: None или пустая строка должны быть пустой строкой
        birth_date = d.get('birth_date')
        if not birth_date or birth_date.strip() == '':
            d['birth_date'] = ''
        else:
            d['birth_date'] = birth_date.strip()
        extra = json.loads(d.get('extra_data', '{}'))
        d['extra_data'] = extra
        d['representatives'] = extra.get('representatives', [])
        return jsonify(d)

@employee_bp.route('/api/employee/<int:emp_id>/changes_history')
@require_admin()
def api_employee_changes_history(emp_id):
    admin_id = session.get('admin_id')
    from utils.auth import has_permission
    with get_db() as conn:
        student = conn.execute('SELECT id, fio FROM employees WHERE id = ?', (emp_id,)).fetchone()
        history = conn.execute('''
            SELECT 
                ech.id, 
                ech.admin_id, 
                ech.admin_username, 
                ech.field_name, 
                ech.old_value, 
                ech.new_value, 
                ech.changed_at,
                a.role as admin_role,
                a.fio as admin_fio
            FROM employee_changes_history ech
            LEFT JOIN admins a ON ech.admin_id = a.id
            WHERE ech.employee_id = ?
            ORDER BY ech.changed_at DESC
            LIMIT 100
        ''', (emp_id,)).fetchall()
        result = []
        for row in history:
            admin_username = row['admin_username'] or 'Система'
            admin_role = row['admin_role'] or 'неизвестно'
            admin_fio = row['admin_fio'] or ''
            if admin_fio:
                display_name = f"{admin_fio} ({admin_role})"
            else:
                display_name = f"{admin_username} ({admin_role})"
            result.append({
                'id': row['id'],
                'admin_id': row['admin_id'],
                'admin_username': display_name,
                'admin_role': admin_role,
                'field_name': row['field_name'],
                'old_value': row['old_value'] or '',
                'new_value': row['new_value'] or '',
                'changed_at': row['changed_at']
            })
        return jsonify({'success': True, 'history': result})

@employee_bp.route('/api/employee/<emp_id>/roommates')
def api_roommates(emp_id):
    if emp_id == 'new' or not emp_id:
        return jsonify([])
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return jsonify([])
    clean_expired_vacations()
    with get_db() as conn:
        row = conn.execute('SELECT building, entrance, room_number FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if not row:
            return jsonify([])
        building = row['building']
        entrance = row['entrance']
        room_number = row['room_number']
        roommates = conn.execute('''
            SELECT id, fio, phone, group_name, birth_date, photo
            FROM employees
            WHERE building = ? AND entrance = ? AND room_number = ? AND id != ?
            ORDER BY fio
        ''', (building, entrance, room_number, emp_id)).fetchall()
        result = [dict(rm) for rm in roommates]
        return jsonify(result)

@employee_bp.route('/api/admin/employee', methods=['POST'])
@require_permission('edit')
def api_add_employee():
    admin_id = session.get('admin_id')
    data = request.json
    education_level = data.get('education_level', '').strip()
    extra = data.get('extra', {})
    extra['representatives'] = data.get('representatives', [])
    extra_json = json.dumps(extra, ensure_ascii=False)
    building = data.get('building', '').strip()
    room_number = data.get('room_number', '').strip()
    entrance = data.get('entrance', '').strip()
    
    # Автоматическое определение подъезда, если не указан
    if not entrance and building and room_number:
        entrance = get_entrance_by_number(building, room_number)
    
    # Проверка комнаты и количества проживающих, если указаны building и room_number
    if building and room_number:
        with get_db() as conn:
            # Проверяем существование комнаты
            room_exists = None
            if entrance:
                room_exists = conn.execute('''
                    SELECT id FROM rooms 
                    WHERE TRIM(COALESCE(building, '')) = TRIM(COALESCE(?, ''))
                    AND TRIM(COALESCE(entrance, '')) = TRIM(COALESCE(?, ''))
                    AND TRIM(COALESCE(room_number, '')) = TRIM(COALESCE(?, ''))
                ''', (building, entrance, room_number)).fetchone()
            
            # Если комната не найдена, но подъезд был определен, возвращаем ошибку
            if not room_exists and entrance:
                return jsonify({
                    'error': f'Комната {building}-{entrance}-{room_number} не найдена в базе данных. Пожалуйста, сначала добавьте комнату в разделе "Управление комнатами".'
                }), 400
            
            # Если комната не найдена и подъезд не определен, возвращаем ошибку
            if not room_exists and not entrance:
                return jsonify({
                    'error': f'Комната {building}-{room_number} не найдена в базе данных. Не удалось определить подъезд. Пожалуйста, сначала добавьте комнату в разделе "Управление комнатами".'
                }), 400
            
            # Проверяем количество проживающих (комната найдена и подъезд определен)
            if entrance and room_exists:
                max_occupants = get_room_max_occupants(building, entrance, room_number)
                current_occupants = get_room_current_occupants(building, entrance, room_number)
                
                if current_occupants >= max_occupants:
                    return jsonify({
                        'error': f'Комната {building}-{entrance}-{room_number} уже заполнена. Максимальное количество проживающих: {max_occupants}, текущее: {current_occupants}. Невозможно разместить еще одного студента.'
                    }), 400
    
    # Обработка даты рождения: пустая строка преобразуется в None
    birth_date = data.get('birth_date', '') or None
    if birth_date:
        birth_date = birth_date.strip()
        if not birth_date:
            birth_date = None
    
    with get_db() as conn:
        cur = conn.cursor()
        has_own_bed_linen = 1 if data.get('has_own_bed_linen') else 0
        is_local = 1 if data.get('is_local') else 0
        
        cur.execute('''
            INSERT INTO employees (fio, phone, group_name, birth_date, building, room_number, entrance, notes, absences, reprimands, vacation, vacation_history, extra_data, education_level, has_own_bed_linen, is_local)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, ?)
        ''', (
            data['fio'], data.get('phone', ''), data.get('group_name', ''),
            birth_date, building, room_number,
            entrance, data.get('notes', ''), data.get('absences', ''),
            data.get('reprimands', ''), data.get('vacation', ''), extra_json,
            education_level, has_own_bed_linen, is_local
        ))
        new_id = cur.lastrowid
        admin_username = session.get('admin_username', 'Unknown')
        admin_fio = session.get('admin_fio', '')
        now = datetime.now(MOSCOW_TZ).isoformat()
        
        cur.execute('''
            INSERT INTO employee_changes_history 
            (employee_id, admin_id, admin_username, field_name, old_value, new_value, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_id, admin_id, admin_username, 
            'Карточка создана', 
            None, 
            f"Создана карточка студента: {data['fio']}",
            now
        ))
        
        conn.commit()
        return jsonify({'success': True, 'id': new_id})

@employee_bp.route('/api/admin/employee/<int:emp_id>', methods=['POST'])
@require_permission('edit')
def api_update_employee(emp_id):
    admin_id = session.get('admin_id')
    data = request.json
    
    # Логирование для отладки
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"api_update_employee called for emp_id={emp_id}, vacation in data: {data.get('vacation', 'NOT FOUND')[:100] if data.get('vacation') else 'EMPTY'}")
    with get_db() as conn:
        current_student = conn.execute('SELECT education_level FROM employees WHERE id = ?', (emp_id,)).fetchone()
        current_level = (current_student['education_level'] or '').strip()
        new_level = data.get('education_level', '').strip() or current_level
    admin_username = session.get('admin_username', 'Unknown')
    with get_db() as conn_check:
        admin_info = conn_check.execute('SELECT username, fio FROM admins WHERE id = ?', (admin_id,)).fetchone()
        admin_fio_value = admin_info['fio'] if admin_info['fio'] else ''
        admin_username = admin_info['username'] or admin_fio_value or 'Unknown'
    extra = data.get('extra', {})
    extra['representatives'] = data.get('representatives', [])
    extra_json = json.dumps(extra, ensure_ascii=False, default=str)
    with get_db() as conn:
        current = conn.execute('SELECT * FROM employees WHERE id = ?', (emp_id,)).fetchone()
        fields_to_track = {
            'fio': 'ФИО',
            'phone': 'Телефон',
            'group_name': 'Группа',
            'birth_date': 'Дата рождения',
            'building': 'Корпус',
            'room_number': 'Номер комнаты',
            'entrance': 'Подъезд',
            'notes': 'Примечания',
            'absences': 'Акты',
            'reprimands': 'Выговоры',
            'vacation': 'Заявление',
            'education_level': 'Уровень образования',
            'has_own_bed_linen': 'Свое постельное белье'
        }
        changes = []
        residence_fields = ['building', 'room_number', 'entrance']
        for field_key, field_name in fields_to_track.items():
            if field_key in current.keys():
                old_value_raw = current[field_key]
                old_value = str(old_value_raw if old_value_raw is not None else '')
            else:
                old_value = ''
            new_value = str(data.get(field_key, '') or '')
            old_value_normalized = old_value.strip() if old_value else ''
            new_value_normalized = new_value.strip() if new_value else ''
            if field_key in residence_fields:
                if old_value_normalized and not new_value_normalized:
                    continue
            if old_value_normalized != new_value_normalized:
                changes.append({
                    'field_name': field_name,
                    'field_key': field_key,
                    'old_value': old_value,
                    'new_value': new_value
                })
        building = data.get('building', '').strip()
        current_building = current['building'] if 'building' in current.keys() else None
        if not building and current_building:
            building = str(current_building or '')
        room_number = data.get('room_number', '').strip()
        current_room_number = current['room_number'] if 'room_number' in current.keys() else None
        if not room_number and current_room_number:
            room_number = str(current_room_number or '')
        entrance = data.get('entrance', '').strip()
        current_entrance = current['entrance'] if 'entrance' in current.keys() else None
        if not entrance and current_entrance:
            entrance = str(current_entrance or '')
        if not entrance and building and room_number:
            auto_entrance = get_entrance_by_number(building, room_number)
            if auto_entrance:
                entrance = auto_entrance
        # Валидация комнаты и проверка количества проживающих
        if building and room_number:
            # Проверяем существование комнаты
            room_exists = None
            if entrance:
                room_exists = conn.execute('''
                    SELECT id FROM rooms 
                    WHERE TRIM(COALESCE(building, '')) = TRIM(COALESCE(?, ''))
                    AND TRIM(COALESCE(entrance, '')) = TRIM(COALESCE(?, ''))
                    AND TRIM(COALESCE(room_number, '')) = TRIM(COALESCE(?, ''))
                ''', (building, entrance, room_number)).fetchone()
            
            # Если комната не найдена, пытаемся найти правильный подъезд
            if not room_exists and building and room_number:
                auto_entrance = get_entrance_by_number(building, room_number)
                if auto_entrance:
                    entrance = auto_entrance
                    room_exists = conn.execute('''
                        SELECT id FROM rooms 
                        WHERE TRIM(COALESCE(building, '')) = TRIM(COALESCE(?, ''))
                        AND TRIM(COALESCE(entrance, '')) = TRIM(COALESCE(?, ''))
                        AND TRIM(COALESCE(room_number, '')) = TRIM(COALESCE(?, ''))
                    ''', (building, entrance, room_number)).fetchone()
            
            # Если комната не найдена, возвращаем ошибку
            if not room_exists:
                return jsonify({
                    'error': f'Комната {building}-{entrance or "?"}-{room_number} не найдена в базе данных. Пожалуйста, сначала добавьте комнату в разделе "Управление комнатами".'
                }), 400
            
            # Проверяем количество проживающих только если комната найдена
            if entrance:
                max_occupants = get_room_max_occupants(building, entrance, room_number)
                current_occupants = get_room_current_occupants(building, entrance, room_number, exclude_employee_id=emp_id)
                
                # Определяем текущую комнату студента
                current_room = None
                current_building = current['building'] if 'building' in current.keys() else None
                current_entrance = current['entrance'] if 'entrance' in current.keys() else None
                current_room_number = current['room_number'] if 'room_number' in current.keys() else None
                if current_building and current_entrance and current_room_number:
                    current_room = (str(current_building).strip(), str(current_entrance).strip(), str(current_room_number).strip())
                
                new_room = (building, entrance, room_number)
                
                # Проверяем, меняется ли комната студента
                if current_room != new_room:
                    # Если студент переезжает в другую комнату или впервые получает комнату
                    if current_occupants >= max_occupants:
                        return jsonify({
                            'error': f'Комната {building}-{entrance}-{room_number} уже заполнена. Максимальное количество проживающих: {max_occupants}, текущее: {current_occupants}. Невозможно разместить еще одного студента.'
                        }), 400
        
        education_level = data.get('education_level', '').strip()
        has_own_bed_linen = 1 if data.get('has_own_bed_linen') else 0
        is_local = 1 if data.get('is_local') else 0
        
        # Обработка даты рождения: пустая строка преобразуется в None
        birth_date = data.get('birth_date', '') or None
        if birth_date:
            birth_date = birth_date.strip()
            if not birth_date:
                birth_date = None
        
        # Обработка vacation_history: если меняется vacation, старое значение добавляем в историю
        new_vacation_raw = data.get('vacation', '')
        new_vacation = new_vacation_raw.strip() if new_vacation_raw else ''
        old_vacation = (current['vacation'] if 'vacation' in current.keys() else None) or ''
        vacation_history = (current['vacation_history'] if 'vacation_history' in current.keys() else None) or '[]'
        
        # Логирование для отладки
        logger.info(f"Processing vacation for emp_id={emp_id}: new_vacation_raw={repr(new_vacation_raw)[:100]}, new_vacation={repr(new_vacation)[:100]}, old_vacation={repr(old_vacation)[:100]}")
        
        try:
            history_list = json.loads(vacation_history) if isinstance(vacation_history, str) else vacation_history
            if not isinstance(history_list, list):
                history_list = []
        except:
            history_list = []
        
        # Если старое заявление существует и отличается от нового, добавляем его в историю
        # Важно: добавляем в историю только если новое заявление не пустое (т.е. это замена, а не удаление)
        if old_vacation and old_vacation.strip() and new_vacation and old_vacation.strip() != new_vacation:
            history_list.append(old_vacation.strip())
        
        vacation_history_json = json.dumps(history_list, ensure_ascii=False)
        
        logger.info(f"Updating employee {emp_id}: vacation='{new_vacation[:50] if new_vacation else ''}...', vacation_history length={len(history_list)}")
        
        conn.execute('''
            UPDATE employees SET
            fio = ?, phone = ?, group_name = ?, birth_date = ?,
            building = ?, room_number = ?, entrance = ?,
            notes = ?, absences = ?, reprimands = ?, vacation = ?, vacation_history = ?, extra_data = ?, education_level = ?, has_own_bed_linen = ?, is_local = ?
            WHERE id = ?
        ''', (
            data['fio'], data.get('phone', ''), data.get('group_name', ''),
            birth_date, building, room_number,
            entrance, data.get('notes', ''), data.get('absences', ''),
            data.get('reprimands', ''), new_vacation, vacation_history_json, extra_json,
            education_level, has_own_bed_linen, is_local, emp_id
        ))
        
        # Проверяем, что данные сохранились
        verify = conn.execute('SELECT vacation, vacation_history FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if verify:
            logger.info(f"Verified employee {emp_id}: vacation='{verify['vacation'][:50] if verify['vacation'] else ''}...', vacation_history length={len(json.loads(verify['vacation_history'] or '[]'))}")
        
        if changes:
            if not admin_username or admin_username == 'Unknown':
                admin_info = conn.execute('SELECT username, fio FROM admins WHERE id = ?', (admin_id,)).fetchone()
                if admin_info:
                    admin_fio_value = admin_info['fio'] if admin_info['fio'] else ''
                    admin_username = admin_info['username'] or admin_fio_value or 'Unknown'
            for change in changes:
                old_val = change['old_value'][:500] if len(change['old_value']) > 500 else change['old_value']
                new_val = change['new_value'][:500] if len(change['new_value']) > 500 else change['new_value']
                final_admin_username = admin_username or 'Unknown'
                conn.execute('''
                    INSERT INTO employee_changes_history 
                    (employee_id, admin_id, admin_username, field_name, old_value, new_value, changed_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    emp_id, admin_id, final_admin_username, 
                    change['field_name'], old_val, new_val
                ))
        conn.commit()
        return jsonify({'success': True, 'changes_count': len(changes)})

@employee_bp.route('/api/admin/employee/<int:emp_id>', methods=['DELETE'])
@require_permission('delete')
def api_delete_employee(emp_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    with get_db() as conn:
        photo = conn.execute('SELECT photo FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if photo and photo['photo']:
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], photo['photo'])
            if os.path.exists(photo_path):
                os.remove(photo_path)
        conn.execute('DELETE FROM employees WHERE id = ?', (emp_id,))
        conn.commit()
        return jsonify({'success': True})

@employee_bp.route('/api/admin/photo/<int:emp_id>', methods=['POST'])
@require_permission('edit')
def api_update_photo(emp_id):
    admin_id = session.get('admin_id')
    file = request.files['photo']
    with get_db() as conn:
        old_photo_row = conn.execute('SELECT photo, fio FROM employees WHERE id = ?', (emp_id,)).fetchone()
        old_photo = old_photo_row['photo']
        student_fio = old_photo_row['fio'] or 'Студент'
        if old_photo:
            old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_photo)
            if os.path.exists(old_path):
                os.remove(old_path)
    _, ext = os.path.splitext(file.filename)
    filename = str(uuid.uuid4()) + ext
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
    with get_db() as conn:
        conn.execute('UPDATE employees SET photo = ? WHERE id = ?', (filename, emp_id))
        admin_row = conn.execute('SELECT username, fio FROM admins WHERE id = ?', (admin_id,)).fetchone()
        admin_username = admin_row['username'] if admin_row else session.get('admin_username', 'Unknown')
        admin_fio = admin_row['fio'] if admin_row and admin_row['fio'] else ''
        final_admin_username = admin_fio if admin_fio else admin_username
        now = datetime.now(MOSCOW_TZ).isoformat()
        old_value = f"Фото: {old_photo}" if old_photo else "Фото отсутствовало"
        new_value = f"Фото: {filename}"
        conn.execute('''
            INSERT INTO employee_changes_history 
            (employee_id, admin_id, admin_username, field_name, old_value, new_value, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            emp_id, admin_id, final_admin_username,
            'photo', old_value, new_value, now
        ))
        conn.commit()
    return jsonify({'success': True, 'photo': filename})

@employee_bp.route('/api/employee/<emp_id>/files', methods=['GET'])
def api_get_employee_files(emp_id):
    if emp_id == 'new' or not emp_id:
        return jsonify({'success': True, 'files': []})
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return jsonify({'success': True, 'files': []})
    admin_id = session.get('admin_id')
    with get_db() as conn:
        student = conn.execute('SELECT id, fio FROM employees WHERE id = ?', (emp_id,)).fetchone()
        
        files = conn.execute('''
            SELECT 
                ef.id,
                ef.filename,
                ef.original_filename,
                ef.file_path,
                ef.file_size,
                ef.file_type,
                ef.description,
                ef.uploaded_at,
                a.username as uploaded_by_username,
                a.fio as uploaded_by_fio
            FROM employee_files ef
            LEFT JOIN admins a ON ef.uploaded_by = a.id
            WHERE ef.employee_id = ?
            ORDER BY ef.uploaded_at DESC
        ''', (emp_id,)).fetchall()
        
        result = []
        for file_row in files:
            result.append({
                'id': file_row['id'],
                'filename': file_row['filename'],
                'original_filename': file_row['original_filename'],
                'file_path': file_row['file_path'],
                'file_size': file_row['file_size'],
                'file_type': file_row['file_type'],
                'description': file_row['description'] or '',
                'uploaded_at': file_row['uploaded_at'],
                'uploaded_by': file_row['uploaded_by_fio'] or file_row['uploaded_by_username'] or 'Неизвестно'
            })
        
        return jsonify({'success': True, 'files': result})

@employee_bp.route('/api/employee/<int:emp_id>/files', methods=['POST'])
@require_permission('edit')
def api_upload_employee_file(emp_id):
    admin_id = session.get('admin_id')
    file = request.files['file']
    current_pos = file.tell()
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(current_pos)
    description = request.form.get('description', '').strip()
    with get_db() as conn:
        student = conn.execute('SELECT id, fio FROM employees WHERE id = ?', (emp_id,)).fetchone()
        original_filename = file.filename
        safe_filename = sanitize_filename(original_filename)
        _, ext = os.path.splitext(safe_filename)
        unique_filename = str(uuid.uuid4()) + ext
        file_path = os.path.join(STUDENT_FILES_FOLDER, unique_filename)
        relative_path = os.path.join('static', 'student_files', unique_filename)
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        file_type = ext[1:].lower() if ext else 'unknown'
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO employee_files 
            (employee_id, filename, original_filename, file_path, file_size, file_type, description, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            emp_id,
            unique_filename,
            original_filename,
            relative_path,
            file_size,
            file_type,
            description,
            admin_id
        ))
        conn.commit()
        file_id = cursor.lastrowid
        return jsonify({
            'success': True,
            'file': {
                'id': file_id,
                'filename': unique_filename,
                'original_filename': original_filename,
                'file_size': file_size,
                'file_type': file_type,
                'description': description
            }
        })

@employee_bp.route('/api/employee/<int:emp_id>/files/<int:file_id>', methods=['DELETE'])
@require_permission('edit')
def api_delete_employee_file(emp_id, file_id):
    admin_id = session.get('admin_id')
    with get_db() as conn:
        file_row = conn.execute('''
            SELECT file_path, filename FROM employee_files 
            WHERE id = ? AND employee_id = ?
        ''', (file_id, emp_id)).fetchone()
        relative_path = file_row['file_path']
        filename = file_row['filename']
        if os.path.isabs(relative_path):
            file_path = relative_path
        else:
            if relative_path.startswith('static/'):
                file_path = os.path.join(current_app.root_path, relative_path)
            else:
                file_path = os.path.join(STUDENT_FILES_FOLDER, filename)
        conn.execute('DELETE FROM employee_files WHERE id = ?', (file_id,))
        conn.commit()
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'success': True})

@employee_bp.route('/api/employee/<int:emp_id>/files/<int:file_id>/download')
def api_download_employee_file(emp_id, file_id):
    admin_id = session.get('admin_id')
    with get_db() as conn:
        file_row = conn.execute('''
            SELECT file_path, original_filename FROM employee_files 
            WHERE id = ? AND employee_id = ?
        ''', (file_id, emp_id)).fetchone()
        relative_path = file_row['file_path']
        if os.path.isabs(relative_path):
            file_path = relative_path
        else:
            if relative_path.startswith('static/'):
                file_path = os.path.join(current_app.root_path, relative_path)
            else:
                file_path = os.path.join(STUDENT_FILES_FOLDER, file_row['filename'])
        original_filename = file_row['original_filename']
        from flask import Response
        from urllib.parse import quote
        
        # Правильно кодируем имя файла для заголовка Content-Disposition
        # Используем RFC 2231 формат для поддержки кириллицы
        encoded_filename = quote(original_filename.encode('utf-8'))
        content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
        
        # Определяем MIME-тип на основе расширения файла
        import mimetypes
        mimetype, _ = mimetypes.guess_type(original_filename)
        if not mimetype:
            mimetype = 'application/octet-stream'
        
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        return Response(
            file_data,
            mimetype=mimetype,
            headers={
                'Content-Disposition': content_disposition
            }
        )
