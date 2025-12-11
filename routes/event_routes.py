from flask import Blueprint, request, jsonify, session, redirect, render_template, url_for
from datetime import datetime
from database import get_db
from utils.auth import require_permission, has_permission, get_admin_role
import sqlite3

event_bp = Blueprint('event', __name__)


@event_bp.route('/events/calendar')
def events_calendar():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    if not has_permission(admin_id, 'manage_events'):
        return render_template('no_access.html', message='У вас нет доступа к календарю мероприятий'), 403
    
    role = get_admin_role(admin_id)
    
    all_permissions = [
        'view', 'edit', 'delete', 'import', 'manage_columns', 
        'manage_health', 'manage_vacation', 'manage_admins', 
        'manage_bed_linen', 'manage_send_messages', 'view_reports', 'manage_tg_users', 
        'scan_qr', 'manage_rooms', 'manage_minors', 
        'manage_round_assignments', 'manage_payments', 'manage_events',
        'access_college', 'all'
    ]
    admin_permissions = {}
    for perm in all_permissions:
        admin_permissions[perm] = has_permission(admin_id, perm)
    
    return render_template('events_calendar.html', admin_role=role, admin_permissions=admin_permissions)


@event_bp.route('/events/<int:event_id>/scan')
def event_scan(event_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    if not has_permission(admin_id, 'manage_events'):
        return render_template('no_access.html', message='У вас нет доступа к сканированию QR-кодов'), 403
    
    with get_db() as conn:
        event = conn.execute('''
            SELECT id, description, event_date, event_time, location, admin_fio, coauthor_fio, organizers
            FROM events WHERE id = ?
        ''', (event_id,)).fetchone()
        
        if not event:
            return render_template('no_access.html', message='Мероприятие не найдено'), 404
        admin = conn.execute('SELECT id, username FROM admins WHERE id = ?', (admin_id,)).fetchone()
        admin_username = admin['username'] if admin else ''
        is_global_org = conn.execute('SELECT id FROM event_organizers WHERE tg_username = ?', (admin_username,)).fetchone()
        event_organizers = event['organizers'] or ''
        organizer_list = [o.strip() for o in event_organizers.split(',') if o.strip()] if event_organizers else []
        
        if not is_global_org and admin_username not in organizer_list:
            return render_template('no_access.html', message='Вы не являетесь организатором этого мероприятия'), 403
    
    role = get_admin_role(admin_id)
    return render_template('event_scan.html', event=dict(event), admin_role=role, admin_username=admin_username)


@event_bp.route('/events/<int:event_id>/attendance')
def event_attendance(event_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    if not has_permission(admin_id, 'manage_events'):
        return render_template('no_access.html', message='У вас нет доступа к просмотру посещаемости'), 403
    
    with get_db() as conn:
        event = conn.execute('''
            SELECT id, description, event_date, event_time, location, admin_fio, coauthor_fio
            FROM events WHERE id = ?
        ''', (event_id,)).fetchone()
        
        if not event:
            return render_template('no_access.html', message='Мероприятие не найдено'), 404
    
    role = get_admin_role(admin_id)
    return render_template('event_attendance.html', event=dict(event), admin_role=role)


@event_bp.route('/events/attendance/rating')
def attendance_rating():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    if not has_permission(admin_id, 'manage_events'):
        return render_template('no_access.html', message='У вас нет доступа к рейтингу посещаемости'), 403
    
    role = get_admin_role(admin_id)
    return render_template('attendance_rating.html', admin_role=role)


@event_bp.route('/admin/event_organizers')
def admin_event_organizers():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    if not has_permission(admin_id, 'manage_events'):
        return render_template('no_access.html', message='У вас нет доступа к управлению организаторами'), 403
    
    role = get_admin_role(admin_id)
    return render_template('admin_event_organizers.html', admin_role=role)


@event_bp.route('/api/events/organizers', methods=['GET'])
@require_permission('manage_events')
def api_get_event_organizers():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        organizers = conn.execute('''
            SELECT id, tg_username, fio, tg_user_id, created_at
            FROM event_organizers
            ORDER BY tg_username
        ''').fetchall()
        
        result = []
        for org in organizers:
            result.append({
                'id': org['id'],
                'tg_username': org['tg_username'],
                'fio': org['fio'] or '',
                'tg_user_id': org['tg_user_id'],
                'created_at': org['created_at']
            })
        
        return jsonify({'success': True, 'organizers': result})


@event_bp.route('/api/events/organizers', methods=['POST'])
@require_permission('manage_events')
def api_add_event_organizer():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    tg_username = data.get('tg_username', '').strip().replace('@', '')
    
    if not tg_username:
        return jsonify({'error': 'Укажите Telegram username'}), 400
    
    with get_db() as conn:
        tg_user = conn.execute('''
            SELECT tg_user_id, employee_id FROM tg_users WHERE tg_username = ?
        ''', (tg_username,)).fetchone()
        
        tg_user_id = None
        fio = None
        
        if tg_user:
            tg_user_id = tg_user['tg_user_id']
            if tg_user['employee_id']:
                employee = conn.execute('SELECT fio FROM employees WHERE id = ?', (tg_user['employee_id'],)).fetchone()
                if employee:
                    fio = employee['fio']
        
        conn.execute('''
            INSERT INTO event_organizers (tg_username, fio, tg_user_id)
            VALUES (?, ?, ?)
        ''', (tg_username, fio, tg_user_id))
        conn.commit()
        return jsonify({'success': True})


@event_bp.route('/api/events/organizers/<int:org_id>', methods=['DELETE'])
@require_permission('manage_events')
def api_delete_event_organizer(org_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        conn.execute('DELETE FROM event_organizers WHERE id = ?', (org_id,))
        conn.commit()
        return jsonify({'success': True})


@event_bp.route('/api/events', methods=['GET'])
@require_permission('manage_events')
def api_get_events():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    with get_db() as conn:
        query = 'SELECT id, admin_id, admin_fio, location, description, event_date, event_time, created_at, coauthor_id, coauthor_fio, organizers FROM events WHERE 1=1'
        params = []
        
        if start_date:
            query += ' AND event_date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND event_date <= ?'
            params.append(end_date)
        
        query += ' ORDER BY event_date, event_time'
        
        events = conn.execute(query, params).fetchall()
        
        result = []
        for event in events:
            coauthor_id = event['coauthor_id'] if event['coauthor_id'] else None
            coauthor_fio = event['coauthor_fio'] if event['coauthor_fio'] else None
            organizers = event.get('organizers', '') if hasattr(event, 'get') else (event['organizers'] if 'organizers' in event.keys() else '')
            
            attendance_count = conn.execute(
                'SELECT COUNT(*) as count FROM event_attendance WHERE event_id = ?',
                (event['id'],)
            ).fetchone()['count']
            
            result.append({
                'id': event['id'],
                'admin_id': event['admin_id'],
                'admin_fio': event['admin_fio'],
                'location': event['location'],
                'description': event['description'],
                'event_date': event['event_date'],
                'event_time': event['event_time'],
                'created_at': event['created_at'],
                'coauthor_id': coauthor_id,
                'coauthor_fio': coauthor_fio,
                'organizers': organizers,
                'attendance_count': attendance_count
            })
        
        return jsonify({'success': True, 'events': result})


@event_bp.route('/api/events', methods=['POST'])
@require_permission('manage_events')
def api_create_event():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    location = data.get('location', '').strip()
    description = data.get('description', '').strip()
    event_date = data.get('event_date', '').strip()
    event_time = data.get('event_time', '').strip()
    coauthor_id = data.get('coauthor_id')
    organizers = data.get('organizers', '')
    
    if not location or not description or not event_date or not event_time:
        return jsonify({'error': 'Все поля обязательны для заполнения'}), 400
    
    admin_fio = session.get('admin_fio', '')
    if not admin_fio:
        with get_db() as conn:
            admin = conn.execute('SELECT fio FROM admins WHERE id = ?', (admin_id,)).fetchone()
            if admin:
                admin_fio = admin['fio'] if admin['fio'] else ''
            else:
                admin_fio = ''
    
    if not admin_fio:
        return jsonify({'error': 'ФИО воспитателя не указано. Обратитесь к администратору для добавления ФИО.'}), 400
    
    coauthor_fio = None
    if coauthor_id:
        with get_db() as conn:
            coauthor = conn.execute('SELECT fio FROM admins WHERE id = ? AND role IN ("vospitatel", "admin", "super_admin")', (coauthor_id,)).fetchone()
            if coauthor:
                coauthor_fio = coauthor['fio'] if coauthor['fio'] else None
            else:
                coauthor_id = None
    
    with get_db() as conn:
        conn.execute('''
            INSERT INTO events (admin_id, admin_fio, location, description, event_date, event_time, coauthor_id, coauthor_fio, organizers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (admin_id, admin_fio, location, description, event_date, event_time, coauthor_id, coauthor_fio, organizers))
        conn.commit()
        
        return jsonify({'success': True})


@event_bp.route('/api/events/<int:event_id>', methods=['DELETE'])
@require_permission('manage_events')
def api_delete_event(event_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        event = conn.execute('SELECT admin_id FROM events WHERE id = ?', (event_id,)).fetchone()
        if not event:
            return jsonify({'error': 'Мероприятие не найдено'}), 404
        
        if not has_permission(admin_id, 'manage_admins') and event['admin_id'] != admin_id:
            return jsonify({'error': 'Вы можете удалить только свои мероприятия'}), 403
        
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()
        
        return jsonify({'success': True})


@event_bp.route('/api/events/locations', methods=['GET'])
def api_get_locations():
    """Получить список активных мест проведения мероприятий"""
    try:
        with get_db() as conn:
            # Проверяем существование таблицы
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='event_locations'
            """)
            if not cursor.fetchone():
                # Таблица не существует, возвращаем пустой список или дефолтные значения
                default_locations = [
                    'Коворкинг "Псоу"',
                    'Коворкинг "Мзымта"',
                    'Кинозал',
                    'Коворкинг "Сабаль"',
                    'Коворкинг "Фаргезия"',
                    'Коворкинг "Магнолия"',
                    'Мастер-кухня'
                ]
                return jsonify({'success': True, 'locations': default_locations})
            
            locations = conn.execute('''
                SELECT name FROM event_locations 
                WHERE is_active = 1 
                ORDER BY name
            ''').fetchall()
            location_list = [loc['name'] for loc in locations]
            # Если нет активных мест, возвращаем пустой список
            if not location_list:
                return jsonify({'success': True, 'locations': []})
        return jsonify({'success': True, 'locations': location_list})
    except Exception as e:
        # В случае ошибки возвращаем дефолтные значения
        default_locations = [
            'Коворкинг "Псоу"',
            'Коворкинг "Мзымта"',
            'Кинозал',
            'Коворкинг "Сабаль"',
            'Коворкинг "Фаргезия"',
            'Коворкинг "Магнолия"',
            'Мастер-кухня'
        ]
        return jsonify({'success': True, 'locations': default_locations})


@event_bp.route('/events/locations/manage')
@require_permission('manage_events')
def manage_event_locations():
    """Страница управления местами проведения мероприятий"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    role = get_admin_role(admin_id)
    all_permissions = [
        'view', 'edit', 'delete', 'import', 'manage_columns', 
        'manage_health', 'manage_vacation', 'manage_admins', 
        'manage_bed_linen', 'manage_send_messages', 'view_reports', 'manage_tg_users', 
        'scan_qr', 'manage_rooms', 'manage_minors', 
        'manage_round_assignments', 'manage_payments', 'manage_events',
        'access_college', 'all'
    ]
    admin_permissions = {}
    for perm in all_permissions:
        admin_permissions[perm] = has_permission(admin_id, perm)
    
    return render_template('admin_event_locations.html', admin_role=role, admin_permissions=admin_permissions)


@event_bp.route('/api/events/locations/all', methods=['GET'])
@require_permission('manage_events')
def api_get_all_locations():
    """Получить все места (включая неактивные) для управления"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db() as conn:
            # Проверяем существование таблицы
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='event_locations'
            """)
            if not cursor.fetchone():
                # Таблица не существует, возвращаем пустой список
                return jsonify({'success': True, 'locations': []})
            
            locations = conn.execute('''
                SELECT id, name, description, is_active, created_at
                FROM event_locations 
                ORDER BY is_active DESC, name
            ''').fetchall()
            result = [dict(loc) for loc in locations]
        return jsonify({'success': True, 'locations': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@event_bp.route('/api/events/locations', methods=['POST'])
@require_permission('manage_events')
def api_create_location():
    """Создать новое место проведения мероприятия"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Нет данных в запросе'}), 400
        
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'error': 'Название места обязательно'}), 400
        
        with get_db() as conn:
            # Проверяем существование таблицы
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='event_locations'
            """)
            if not cursor.fetchone():
                return jsonify({'error': 'Таблица мест проведения не создана. Обратитесь к администратору.'}), 500
            
            try:
                conn.execute('''
                    INSERT INTO event_locations (name, description, created_by, is_active)
                    VALUES (?, ?, ?, 1)
                ''', (name, description if description else None, admin_id))
                conn.commit()
                return jsonify({'success': True})
            except sqlite3.IntegrityError:
                return jsonify({'error': 'Место с таким названием уже существует'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@event_bp.route('/api/events/locations/<int:location_id>', methods=['PUT'])
@require_permission('manage_events')
def api_update_location(location_id):
    """Обновить место проведения мероприятия"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    is_active = data.get('is_active', True)
    
    with get_db() as conn:
        # Получаем текущее место
        current_location = conn.execute('''
            SELECT name, description FROM event_locations WHERE id = ?
        ''', (location_id,)).fetchone()
        
        if not current_location:
            return jsonify({'error': 'Место не найдено'}), 404
        
        # Если name не передан, используем текущее
        if not name:
            name = current_location['name']
        if description is None:
            description = current_location['description'] or ''
        
        try:
            conn.execute('''
                UPDATE event_locations 
                SET name = ?, description = ?, is_active = ?
                WHERE id = ?
            ''', (name, description if description else None, 1 if is_active else 0, location_id))
            conn.commit()
            return jsonify({'success': True})
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Место с таким названием уже существует'}), 400


@event_bp.route('/api/events/locations/<int:location_id>', methods=['DELETE'])
@require_permission('manage_events')
def api_delete_location(location_id):
    """Удалить место проведения мероприятия"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        # Проверяем, используется ли место в мероприятиях
        events_count = conn.execute('''
            SELECT COUNT(*) as count FROM events WHERE location = (
                SELECT name FROM event_locations WHERE id = ?
            )
        ''', (location_id,)).fetchone()['count']
        
        if events_count > 0:
            # Деактивируем вместо удаления
            conn.execute('''
                UPDATE event_locations SET is_active = 0 WHERE id = ?
            ''', (location_id,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Место деактивировано, так как используется в мероприятиях'})
        else:
            # Удаляем, если не используется
            conn.execute('DELETE FROM event_locations WHERE id = ?', (location_id,))
            conn.commit()
            return jsonify({'success': True})


@event_bp.route('/api/events/<int:event_id>/attendance', methods=['GET'])
@require_permission('manage_events')
def api_get_event_attendance(event_id):
    admin_id = session.get('admin_id')
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='event_attendance'
        """)
        table_exists = cursor.fetchone() is not None
        if not table_exists:
            return jsonify({'success': True, 'attendance': []})
        cursor.execute("PRAGMA table_info(event_attendance)")
        columns_info = cursor.fetchall()
        columns = [row[1] for row in columns_info]
        has_employee_id = 'employee_id' in columns
        has_student_fio = 'student_fio' in columns
        has_scanned_at = 'scanned_at' in columns
        has_scanned_by_username = 'scanned_by_username' in columns
        select_cols = ['ea.id']
        if has_employee_id:
            select_cols.append('ea.employee_id')
        if has_student_fio:
            select_cols.append('ea.student_fio')
        if has_scanned_at:
            select_cols.append('ea.scanned_at')
        if has_scanned_by_username:
            select_cols.append('ea.scanned_by_username')
        if has_employee_id:
            select_cols.extend([
                'e.fio', 'e.group_name', 'e.building', 'e.entrance', 'e.room_number'
            ])
            query = f'''
                SELECT {', '.join(select_cols)}
                FROM event_attendance ea
                LEFT JOIN employees e ON ea.employee_id = e.id
                WHERE ea.event_id = ?
                ORDER BY ea.scanned_at DESC
            '''
        else:
            query = f'''
                SELECT {', '.join(select_cols)}
                FROM event_attendance ea
                WHERE ea.event_id = ?
                ORDER BY ea.scanned_at DESC
            '''
        attendance = conn.execute(query, (event_id,)).fetchall()
        result = []
        for row in attendance:
            row_dict = dict(row) if hasattr(row, 'keys') else row
            student_fio = ''
            if has_student_fio and 'student_fio' in row_dict:
                student_fio = row_dict.get('student_fio', '')
            elif 'fio' in row_dict:
                student_fio = row_dict.get('fio', '')
            emp_id = None
            if has_employee_id and 'employee_id' in row_dict:
                emp_id = row_dict.get('employee_id')
            result_item = {
                'id': row_dict.get('id'),
                'employee_id': emp_id,
                'student_fio': student_fio,
                'scanned_at': row_dict.get('scanned_at', '') if has_scanned_at else '',
                'scanned_by_username': row_dict.get('scanned_by_username') if has_scanned_by_username else None,
                'fio': row_dict.get('fio') or student_fio,
                'group_name': row_dict.get('group_name'),
                'building': row_dict.get('building'),
                'entrance': row_dict.get('entrance'),
                'room_number': row_dict.get('room_number')
            }
            result.append(result_item)
        return jsonify({'success': True, 'attendance': result})


@event_bp.route('/api/events/attendance/rating', methods=['GET'])
@require_permission('manage_events')
def api_get_attendance_rating():
    admin_id = session.get('admin_id')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    limit = int(request.args.get('limit', 50))
    with get_db() as conn:
        if start_date or end_date:
            query = '''
                SELECT 
                    e.id,
                    e.fio,
                    e.group_name,
                    e.building,
                    e.entrance,
                    e.room_number,
                    COUNT(ea.id) as attendance_count
                FROM employees e
                INNER JOIN event_attendance ea ON e.id = ea.employee_id
                INNER JOIN events ev ON ea.event_id = ev.id
                WHERE 1=1
            '''
            params = []
            if start_date:
                query += ' AND ev.event_date >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND ev.event_date <= ?'
                params.append(end_date)
            query += '''
                GROUP BY e.id, e.fio, e.group_name, e.building, e.entrance, e.room_number
                HAVING attendance_count > 0
                ORDER BY attendance_count DESC, e.fio
                LIMIT ?
            '''
            params.append(limit)
        else:
            query = '''
                SELECT 
                    e.id,
                    e.fio,
                    e.group_name,
                    e.building,
                    e.entrance,
                    e.room_number,
                    COUNT(ea.id) as attendance_count
                FROM employees e
                INNER JOIN event_attendance ea ON e.id = ea.employee_id
                GROUP BY e.id, e.fio, e.group_name, e.building, e.entrance, e.room_number
                HAVING attendance_count > 0
                ORDER BY attendance_count DESC, e.fio
                LIMIT ?
            '''
            params = [limit]
            
            rating = conn.execute(query, params).fetchall()
            
            result = []
            for row in rating:
                result.append({
                    'employee_id': row['id'],
                    'fio': row['fio'] or '',
                    'group_name': row['group_name'] or '',
                    'building': row['building'] or '',
                    'entrance': row['entrance'] or '',
                    'room_number': row['room_number'] or '',
                    'attendance_count': row['attendance_count']
                })
            
            return jsonify({'success': True, 'rating': result})


@event_bp.route('/api/events/<int:event_id>/scan_qr', methods=['POST'])
@require_permission('manage_events')
def api_scan_qr_web(event_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    data = request.json
    qr_code = data.get('qr_code', '').strip()
    
    if not qr_code:
        return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
    
    with get_db() as conn:
        admin = conn.execute('SELECT id, username FROM admins WHERE id = ?', (admin_id,)).fetchone()
        admin_username = admin['username']
        event = conn.execute('SELECT id, organizers FROM events WHERE id = ?', (event_id,)).fetchone()
        if not event:
            return jsonify({'success': False, 'error': 'Мероприятие не найдено'}), 404
        is_global_org = conn.execute('SELECT id FROM event_organizers WHERE tg_username = ?', (admin_username,)).fetchone()
        
        if not is_global_org:
            event_organizers = event['organizers'] or ''
            if event_organizers:
                organizer_list = [o.strip() for o in event_organizers.split(',') if o.strip()]
                if admin_username not in organizer_list:
                    return jsonify({'success': False, 'error': 'Вы не являетесь организатором этого мероприятия'}), 403
            else:
                return jsonify({'success': False, 'error': 'Вы не являетесь организатором этого мероприятия'}), 403
        
        # Обрабатываем QR-код
        if not qr_code.startswith('STUDENT_QR_'):
            return jsonify({'success': False, 'error': 'Неверный формат QR-кода'}), 400
        employee_id = int(qr_code.replace('STUDENT_QR_', ''))
        
        student = conn.execute('SELECT id, fio FROM employees WHERE id = ?', (employee_id,)).fetchone()
        if not student:
            return jsonify({'success': False, 'error': 'Студент не найден'}), 404
        
        existing = conn.execute(
            'SELECT id FROM event_attendance WHERE event_id = ? AND employee_id = ?',
            (event_id, employee_id)
        ).fetchone()
        
        if existing:
            return jsonify({'success': False, 'error': 'Студент уже отмечен на этом мероприятии'}), 400
        
        scanned_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn.execute('''
            INSERT INTO event_attendance (event_id, employee_id, student_fio, scanned_by_tg_id, scanned_by_username, scanned_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (event_id, employee_id, student['fio'], None, admin_username, scanned_at))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Студент {student["fio"]} успешно отмечен',
            'student_fio': student['fio']
        })


@event_bp.route('/api/events/scan_qr', methods=['POST'])
def api_scan_qr():
    data = request.json
    qr_code = data.get('qr_code', '').strip()
    event_id = data.get('event_id')
    scanner_tg_id = data.get('scanner_tg_id')
    scanner_username = data.get('scanner_username', '')
    
    if not qr_code or not event_id or not scanner_tg_id:
        return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
    
    with get_db() as conn:
        event = conn.execute('SELECT id, organizers FROM events WHERE id = ?', (event_id,)).fetchone()
        if not event:
            return jsonify({'success': False, 'error': 'Мероприятие не найдено'}), 404
        
        is_global_org = conn.execute('SELECT id FROM event_organizers WHERE tg_username = ?', (scanner_username,)).fetchone()
        
        if not is_global_org:
            organizers = event.get('organizers', '') if hasattr(event, 'get') else (event['organizers'] if 'organizers' in event.keys() else '')
            if organizers:
                organizer_list = [o.strip() for o in organizers.split(',') if o.strip()]
                if scanner_username not in organizer_list:
                    return jsonify({'success': False, 'error': 'Вы не являетесь организатором этого мероприятия'}), 403
            else:
                return jsonify({'success': False, 'error': 'Вы не являетесь организатором этого мероприятия'}), 403
        
        if not qr_code.startswith('STUDENT_QR_'):
            return jsonify({'success': False, 'error': 'Неверный формат QR-кода'}), 400
        employee_id = int(qr_code.replace('STUDENT_QR_', ''))
        
        student = conn.execute('SELECT id, fio FROM employees WHERE id = ?', (employee_id,)).fetchone()
        if not student:
            return jsonify({'success': False, 'error': 'Студент не найден'}), 404
        
        existing = conn.execute(
            'SELECT id FROM event_attendance WHERE event_id = ? AND employee_id = ?',
            (event_id, employee_id)
        ).fetchone()
        
        if existing:
            return jsonify({'success': False, 'error': 'Студент уже отмечен на этом мероприятии'}), 400
        
        scanned_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn.execute('''
            INSERT INTO event_attendance (event_id, employee_id, student_fio, scanned_by_tg_id, scanned_by_username, scanned_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (event_id, employee_id, student['fio'], scanner_tg_id, scanner_username, scanned_at))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Студент {student["fio"]} успешно отмечен',
            'student_fio': student['fio']
        })


@event_bp.route('/api/events/tg_users', methods=['GET'])
@require_permission('manage_events')
def api_get_tg_users():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    search = request.args.get('search', '').strip()
    
    with get_db() as conn:
        query = '''
            SELECT DISTINCT tu.tg_user_id, tu.tg_username, e.id as employee_id, e.fio
            FROM tg_users tu
            LEFT JOIN employees e ON tu.employee_id = e.id
            WHERE tu.tg_username IS NOT NULL AND tu.tg_username != ''
        '''
        params = []
        
        if search:
            query += ' AND (tu.tg_username LIKE ? OR e.fio LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%'])
        
        query += ' ORDER BY tu.tg_username'
        
        users = conn.execute(query, params).fetchall()
        
        result = []
        for user in users:
            result.append({
                'tg_user_id': user['tg_user_id'],
                'tg_username': user['tg_username'],
                'employee_id': user['employee_id'],
                'fio': user['fio'] or ''
            })
        
        return jsonify({'success': True, 'users': result})


@event_bp.route('/api/events/vospitatels', methods=['GET'])
@require_permission('manage_events')
def api_get_vospitatels():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        vospitatels = conn.execute('''
            SELECT id, fio, username
            FROM admins
            WHERE role IN ('vospitatel', 'admin', 'super_admin') AND is_active = 1
            ORDER BY fio, username
        ''').fetchall()
        
        result = []
        for v in vospitatels:
            fio = v['fio'] if v['fio'] else ''
            username = v['username'] or ''
            if fio:
                result.append({
                    'id': v['id'],
                    'fio': fio,
                    'username': username
                })
        
        return jsonify({'success': True, 'vospitatels': result})


@event_bp.route('/api/students/generate_qr/<int:employee_id>', methods=['POST'])
@require_permission('edit')
def api_generate_student_qr(employee_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        student = conn.execute('SELECT id, fio FROM employees WHERE id = ?', (employee_id,)).fetchone()
        if not student:
            return jsonify({'error': 'Студент не найден'}), 404
        
        qr_code = f'STUDENT_QR_{employee_id}'
        
        conn.execute('UPDATE employees SET student_qr_code = ? WHERE id = ?', (qr_code, employee_id))
        conn.commit()
        
        import qrcode
        import io
        import base64
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_code)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)
        qr_base64 = base64.b64encode(qr_buf.read()).decode('utf-8')
        
        return jsonify({
            'success': True,
            'qr_code': qr_code,
            'qr_image': f'data:image/png;base64,{qr_base64}',
            'student_fio': student['fio']
        })


