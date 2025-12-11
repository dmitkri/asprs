from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from database import get_db
from utils.auth import require_permission, has_permission
from config import MOSCOW_TZ
from datetime import datetime
import json

admin_api_bp = Blueprint('admin_api', __name__)

ALL_SYSTEM_PERMISSIONS = [
    'view', 'edit', 'delete', 'import', 'manage_columns', 
    'manage_health', 'manage_vacation', 'manage_admins', 
    'manage_bed_linen', 'manage_send_messages', 'view_reports', 'manage_tg_users', 
    'scan_qr', 'manage_payments', 'manage_rooms', 
    'manage_minors', 'manage_round_assignments', 'manage_events',
    'access_college', 'all'
]


@admin_api_bp.route('/api/admin/admins', methods=['GET'])
@require_permission('manage_admins')
def api_list_admins():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        admins = conn.execute('''
            SELECT id, username, role, is_active, created_at, fio
            FROM admins 
            ORDER BY created_at DESC
        ''').fetchall()
        
        result = []
        for admin in admins:
            fio = admin['fio'] if admin['fio'] else ''
            
            result.append({
                'id': admin['id'],
                'username': admin['username'],
                'role': admin['role'],
                'is_active': bool(admin['is_active']),
                'created_at': admin['created_at'],
                'fio': fio
            })
        
        return jsonify(result)


@admin_api_bp.route('/api/admin/admins', methods=['POST'])
@require_permission('manage_admins')
def api_create_admin():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'vospitatel')
    fio = data.get('fio', '').strip()
    
    system_roles = ['admin', 'super_admin', 'vospitatel', 'razmeshenie', 'audit']
    if role not in system_roles:
        with get_db() as conn:
            role_exists = conn.execute(
                'SELECT name FROM roles WHERE name = ?',
                (role,)
            ).fetchone()
            if not role_exists:
                return jsonify({'error': f'Роль "{role}" не найдена'}), 400
    
    if not username or not password:
        return jsonify({'error': 'Логин и пароль обязательны'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Пароль должен содержать минимум 6 символов'}), 400
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT id FROM admins WHERE username = ?',
            (username,)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Пользователь с таким логином уже существует'}), 400
        
        password_hash = generate_password_hash(password)
        conn.execute('''
            INSERT INTO admins (username, password_hash, role, is_active, fio, password_changed)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (username, password_hash, role, 1, fio))
        conn.commit()
        
        return jsonify({'success': True})


@admin_api_bp.route('/api/admin/admins/<int:admin_id>', methods=['POST'])
@require_permission('manage_admins')
def api_update_admin(admin_id):
    current_admin_id = session.get('admin_id')
    if not current_admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    role = data.get('role')
    is_active = data.get('is_active')
    password = data.get('password', '').strip()
    
    with get_db() as conn:
        if admin_id == current_admin_id and is_active == False:
            return jsonify({'error': 'Нельзя деактивировать самого себя'}), 400
        
        updates = []
        params = []
        
        if role is not None:
            system_roles = ['admin', 'super_admin', 'vospitatel', 'razmeshenie', 'audit']
            if role not in system_roles:
                role_exists = conn.execute(
                    'SELECT name FROM roles WHERE name = ?',
                    (role,)
                ).fetchone()
                if not role_exists:
                    return jsonify({'error': f'Роль "{role}" не найдена'}), 400
            updates.append('role = ?')
            params.append(role)
        
        if is_active is not None:
            updates.append('is_active = ?')
            params.append(1 if is_active else 0)
        
        if password:
            if len(password) < 6:
                return jsonify({'error': 'Пароль должен содержать минимум 6 символов'}), 400
            password_hash = generate_password_hash(password)
            updates.append('password_hash = ?')
            params.append(password_hash)
        
        fio = data.get('fio', '').strip()
        if fio is not None:
            updates.append('fio = ?')
            params.append(fio)
        
        if not updates:
            return jsonify({'error': 'Нет данных для обновления'}), 400
        
        params.append(admin_id)
        query = f'UPDATE admins SET {", ".join(updates)} WHERE id = ?'
        conn.execute(query, params)
        conn.commit()
        
        return jsonify({'success': True})


@admin_api_bp.route('/api/admin/admins/<int:admin_id>', methods=['DELETE'])
@require_permission('manage_admins')
def api_delete_admin(admin_id):
    current_admin_id = session.get('admin_id')
    if not current_admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if admin_id == current_admin_id:
        return jsonify({'error': 'Нельзя удалить самого себя'}), 400
    
    with get_db() as conn:
        conn.execute('DELETE FROM admins WHERE id = ?', (admin_id,))
        conn.commit()
        
        return jsonify({'success': True})


@admin_api_bp.route('/api/admin/roles', methods=['GET'])
@require_permission('manage_admins')
def api_list_roles():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not has_permission(admin_id, 'manage_admins'):
        return jsonify({'error': 'Доступ запрещен. Необходимо право "Управление администраторами".'}), 403
    
    with get_db() as conn:
        roles = conn.execute('''
            SELECT name, permissions, description
            FROM roles 
            ORDER BY name
        ''').fetchall()
        
        result = []
        for role_row in roles:
            perms = json.loads(role_row['permissions'])
            
            result.append({
                'name': role_row['name'],
                'permissions': perms,
                'description': role_row['description'] or ''
            })
        
        return jsonify({'success': True, 'roles': result})


@admin_api_bp.route('/api/admin/roles', methods=['POST'])
@require_permission('manage_admins')
def api_create_role():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    role_name = data.get('name', '').strip()
    permissions = data.get('permissions', {})
    description = data.get('description', '').strip()
    
    if not role_name:
        return jsonify({'error': 'Название роли обязательно'}), 400
    
    system_roles = ['super_admin', 'admin']
    if role_name in system_roles:
        return jsonify({'error': f'Роль "{role_name}" является системной и не может быть изменена'}), 400
    
    all_permissions = ALL_SYSTEM_PERMISSIONS
    
    for perm in permissions.keys():
        if perm not in all_permissions:
            return jsonify({'error': f'Неизвестное право: {perm}'}), 400
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT name FROM roles WHERE name = ?',
            (role_name,)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Роль с таким названием уже существует'}), 400
        
        conn.execute('''
            INSERT INTO roles (name, permissions, description)
            VALUES (?, ?, ?)
        ''', (role_name, json.dumps(permissions), description))
        conn.commit()
        
        return jsonify({'success': True})


@admin_api_bp.route('/api/admin/roles/<role_name>', methods=['POST'])
@require_permission('manage_admins')
def api_update_role(role_name):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    system_roles = ['super_admin', 'admin']
    if role_name in system_roles:
        return jsonify({'error': f'Роль "{role_name}" является системной и не может быть изменена'}), 400
    
    data = request.json
    permissions = data.get('permissions')
    description = data.get('description', '').strip()
    
    if permissions is None:
        return jsonify({'error': 'Права обязательны'}), 400
    
    all_permissions = ALL_SYSTEM_PERMISSIONS
    
    for perm in permissions.keys():
        if perm not in all_permissions:
            return jsonify({'error': f'Неизвестное право: {perm}'}), 400
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT name FROM roles WHERE name = ?',
            (role_name,)
        ).fetchone()
        
        if not existing:
            return jsonify({'error': 'Роль не найдена'}), 404
        
        conn.execute('''
            UPDATE roles 
            SET permissions = ?, description = ?
            WHERE name = ?
        ''', (json.dumps(permissions), description, role_name))
        conn.commit()
        
        return jsonify({'success': True})


@admin_api_bp.route('/api/admin/roles/<role_name>', methods=['DELETE'])
@require_permission('manage_admins')
def api_delete_role(role_name):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    system_roles = ['super_admin', 'admin']
    if role_name in system_roles:
        return jsonify({'error': f'Роль "{role_name}" является системной и не может быть удалена'}), 400
    
    with get_db() as conn:
        admins_with_role = conn.execute(
            'SELECT COUNT(*) as count FROM admins WHERE role = ?',
            (role_name,)
        ).fetchone()
        
        if admins_with_role['count'] > 0:
            return jsonify({'error': f'Роль используется {admins_with_role["count"]} администратором(ами). Сначала измените их роли.'}), 400
        
        conn.execute('DELETE FROM roles WHERE name = ?', (role_name,))
        conn.commit()
        
        return jsonify({'success': True})


@admin_api_bp.route('/api/admin/change_password', methods=['POST'])
@require_permission('manage_admins')
def api_change_password():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not old_password or not new_password:
        return jsonify({'error': 'Старый и новый пароль обязательны'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'Пароль должен содержать минимум 6 символов'}), 400
    
    with get_db() as conn:
        admin = conn.execute(
            'SELECT password_hash FROM admins WHERE id = ?',
            (admin_id,)
        ).fetchone()
        
        if not admin:
            return jsonify({'error': 'Администратор не найден'}), 404
        
        from werkzeug.security import check_password_hash
        if not check_password_hash(admin['password_hash'], old_password):
            return jsonify({'error': 'Неверный старый пароль'}), 400
        
        new_password_hash = generate_password_hash(new_password)
        conn.execute('''
            UPDATE admins 
            SET password_hash = ?, password_changed = 1
            WHERE id = ?
        ''', (new_password_hash, admin_id))
        conn.commit()
        
        session['password_changed'] = 1
        
        return jsonify({'success': True})


@admin_api_bp.route('/api/admin/settings/telegram_ids', methods=['GET'])
def api_get_telegram_ids():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    if not (has_permission(admin_id, 'manage_minors') or has_permission(admin_id, 'manage_admins')):
        return jsonify({'error': 'Доступ запрещен'}), 403
    with get_db() as conn:
        setting = conn.execute('''
            SELECT value FROM system_settings WHERE key = 'admin_telegram_ids'
        ''').fetchone()
        if setting:
            ids = json.loads(setting['value'])
            return jsonify({'success': True, 'telegram_ids': ids})
        else:
            return jsonify({'success': True, 'telegram_ids': []})


@admin_api_bp.route('/api/admin/settings/telegram_ids', methods=['POST'])
def api_save_telegram_ids():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    if not (has_permission(admin_id, 'manage_minors') or has_permission(admin_id, 'manage_admins')):
        return jsonify({'error': 'Доступ запрещен'}), 403
    data = request.json
    telegram_ids = data.get('telegram_ids', [])
    validated_ids = []
    for tg_id in telegram_ids:
        if isinstance(tg_id, (int, str)):
            validated_id = int(str(tg_id).strip())
            if validated_id > 0:
                validated_ids.append(validated_id)
    
    from datetime import datetime
    from config import MOSCOW_TZ
    
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (
            'admin_telegram_ids',
            json.dumps(validated_ids),
            'Telegram ID администраторов для пересылки ответов несовершеннолетних',
            datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Telegram ID администраторов успешно сохранены',
        'telegram_ids': validated_ids
    })


@admin_api_bp.route('/api/admin/settings/user_bot', methods=['GET'])
@require_permission('manage_admins')
def api_get_user_bot_settings():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        settings = {}
        for key in ['telegram_api_id', 'telegram_api_hash', 'telegram_phone_number']:
            setting = conn.execute(
                'SELECT value FROM system_settings WHERE key = ?',
                (key,)
            ).fetchone()
            if setting:
                settings[key] = setting['value']
            else:
                settings[key] = ''
        
        is_configured = bool(settings.get('telegram_api_id') and 
                           settings.get('telegram_api_hash') and 
                           settings.get('telegram_phone_number'))
        import os
        from config import BASE_DIR, TELEGRAM_SESSION_PATH
        session_file = TELEGRAM_SESSION_PATH + '.session'
        has_session = os.path.exists(session_file)
        
        return jsonify({
            'success': True,
            'settings': settings,
            'is_configured': is_configured,
            'has_session': has_session
        })


@admin_api_bp.route('/api/admin/settings/user_bot', methods=['POST'])
@require_permission('manage_admins')
def api_save_user_bot_settings():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    api_id = data.get('api_id', '').strip()
    api_hash = data.get('api_hash', '').strip()
    phone_number = data.get('phone_number', '').strip()
    if not api_id or not api_hash or not phone_number:
        return jsonify({'error': 'Все поля обязательны для заполнения'}), 400
    api_id_int = int(api_id)
    
    if not phone_number.startswith('+'):
        return jsonify({'error': 'Номер телефона должен начинаться с + (например, +79991234567)'}), 400
    
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
            VALUES (?, ?, ?, ?)
        ''', ('telegram_api_id', str(api_id_int), 'Telegram API ID для User Bot', 
              datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.execute('''
            INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
            VALUES (?, ?, ?, ?)
        ''', ('telegram_api_hash', api_hash, 'Telegram API Hash для User Bot', 
              datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.execute('''
            INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
            VALUES (?, ?, ?, ?)
        ''', ('telegram_phone_number', phone_number, 'Номер телефона для User Bot', 
              datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
    import os
    os.environ['TELEGRAM_API_ID'] = str(api_id_int)
    os.environ['TELEGRAM_API_HASH'] = api_hash
    os.environ['TELEGRAM_PHONE_NUMBER'] = phone_number
    
    return jsonify({
        'success': True,
        'message': 'Настройки User Bot успешно сохранены. При следующем использовании User Bot потребуется авторизация.'
    })


@admin_api_bp.route('/api/admin/settings/user_bot/test', methods=['POST'])
@require_permission('manage_admins')
def api_test_user_bot():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from services.user_bot_service import get_user_bot_client, _import_pyrogram
        if not _import_pyrogram():
            return jsonify({
                'success': False,
                'error': 'Pyrogram не установлен. Установите: pip install pyrogram tgcrypto'
            }), 400
        from services.user_bot_service import get_user_bot_settings_from_db
        settings = get_user_bot_settings_from_db()
        if not settings:
            return jsonify({
                'success': False,
                'error': 'Настройки User Bot не заполнены. Заполните форму и сохраните настройки.'
            }), 400
        import os
        from config import TELEGRAM_SESSION_PATH
        session_file = TELEGRAM_SESSION_PATH + '.session'
        has_session = os.path.exists(session_file)
        if not has_session:
            return jsonify({
                'success': False,
                'error': 'Требуется первичная авторизация. Код подтверждения будет отправлен в Telegram. Запустите проверку подключения из консоли сервера для ввода кода: python3 -c "from services.user_bot_service import get_user_bot_client; import asyncio; asyncio.run(get_user_bot_client())"'
            }), 400
        import inspect
        def run_async(coro_or_callable):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Loop is closed")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if callable(coro_or_callable):
                result = coro_or_callable()
                if asyncio.isfuture(result) or inspect.iscoroutine(result):
                    coro = result
                else:
                    return result
            else:
                coro = coro_or_callable
            if not asyncio.isfuture(coro) and not inspect.iscoroutine(coro):
                raise RuntimeError("Передан объект, который нельзя ожидать (await)")
            return loop.run_until_complete(coro)
        client = run_async(get_user_bot_client)
        if client and client.is_connected:
            me = run_async(client.get_me)
            return jsonify({
                'success': True,
                'message': f'User Bot успешно подключен! Аккаунт: {me.first_name} (@{me.username or "без username"})',
                'user_info': {
                    'id': me.id,
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'username': me.username
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Не удалось подключиться к User Bot'
            }), 400


@admin_api_bp.route('/api/admin/settings/user_bot/disconnect', methods=['POST'])
@require_permission('manage_admins')
def api_disconnect_user_bot():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    from services.user_bot_service import disconnect_user_bot
    import asyncio
    import inspect
    def run_async_disconnect(coro_or_callable):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if callable(coro_or_callable):
            result = coro_or_callable()
            if asyncio.isfuture(result) or inspect.iscoroutine(result):
                coro = result
            else:
                return result
        else:
            coro = coro_or_callable
        if not asyncio.isfuture(coro) and not inspect.iscoroutine(coro):
            raise RuntimeError("Передан объект, который нельзя ожидать (await)")
        return loop.run_until_complete(coro)
    run_async_disconnect(disconnect_user_bot)
    return jsonify({
        'success': True,
        'message': 'User Bot отключен'
    })

@admin_api_bp.route('/api/admin/duty_schedules', methods=['GET'])
def api_get_duty_schedules():
    """Получение списка графиков дежурств"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    building = request.args.get('building', '').strip()
    entrance = request.args.get('entrance', '').strip()
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    
    with get_db() as conn:
        query = '''
            SELECT ds.id, ds.building, ds.entrance, ds.schedule_month, ds.schedule_year,
                   ds.schedule_data, ds.created_at, e.fio as created_by_fio
            FROM duty_schedules ds
            LEFT JOIN employees e ON ds.created_by = e.id
            WHERE 1=1
        '''
        params = []
        
        if building:
            query += ' AND ds.building = ?'
            params.append(building)
        if entrance:
            query += ' AND ds.entrance = ?'
            params.append(entrance)
        if month:
            query += ' AND ds.schedule_month = ?'
            params.append(month)
        if year:
            query += ' AND ds.schedule_year = ?'
            params.append(year)
        
        query += ' ORDER BY ds.schedule_year DESC, ds.schedule_month DESC, ds.building, ds.entrance'
        
        schedules = conn.execute(query, params).fetchall()
        
        result = []
        for schedule in schedules:
            try:
                schedule_data = json.loads(schedule['schedule_data']) if schedule['schedule_data'] else {}
            except:
                schedule_data = {}
            
            result.append({
                'id': schedule['id'],
                'building': schedule['building'],
                'entrance': schedule['entrance'],
                'month': schedule['schedule_month'],
                'year': schedule['schedule_year'],
                'schedule_data': schedule_data,
                'created_at': schedule['created_at'],
                'created_by_fio': schedule['created_by_fio'] or 'Неизвестно'
            })
        
        return jsonify({'success': True, 'schedules': result})

