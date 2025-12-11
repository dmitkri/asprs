from flask import Blueprint, request, jsonify, session, redirect, render_template
from datetime import datetime, timezone
from database import get_db
from utils.auth import require_permission, has_permission, get_admin_role
from config import MOSCOW_TZ
from services.telegram_service import TelegramService
import sqlite3

maintenance_bp = Blueprint('maintenance', __name__)


def convert_timestamp_to_moscow(value):
    if not value:
        return ''
    try:
        if isinstance(value, (int, float)):
            dt_obj = datetime.fromtimestamp(value, tz=timezone.utc)
        else:
            dt_obj = datetime.fromisoformat(value)
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=MOSCOW_TZ)
        dt_moscow = dt_obj.astimezone(MOSCOW_TZ)
        return dt_moscow.strftime('%d.%m.%Y, %H:%M:%S')
    except Exception:
        return ''


@maintenance_bp.route('/admin/maintenance_requests')
def admin_maintenance_requests():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    if not has_permission(admin_id, 'manage_rooms'):
        return render_template('no_access.html', message='У вас нет доступа к управлению заявками'), 403
    
    role = get_admin_role(admin_id)
    return render_template('admin_maintenance_requests.html', admin_role=role)


@maintenance_bp.route('/api/maintenance_requests', methods=['GET'])
@require_permission('manage_rooms')
def api_get_maintenance_requests():
        admin_id = session.get('admin_id')
        if not admin_id:
            return jsonify({'error': 'Unauthorized'}), 401
        status_filter = request.args.get('status', '').strip()
        request_number_filter = request.args.get('request_number', '').strip()
        with get_db() as conn:
            query = '''
                SELECT mr.*, 
                       COALESCE(e.fio, mr.student_fio) as student_fio_display,
                       COALESCE(e.building, mr.building) as building_display,
                       COALESCE(e.entrance, mr.entrance) as entrance_display,
                       COALESCE(e.room_number, mr.room_number) as room_number_display,
                       tg.tg_username
                FROM maintenance_requests mr
                LEFT JOIN employees e ON mr.employee_id = e.id
                LEFT JOIN tg_users tg ON mr.tg_user_id = tg.tg_user_id
                WHERE 1=1
            '''
            params = []
            if status_filter:
                query += ' AND mr.status = ?'
                params.append(status_filter)
            if request_number_filter:
                like_value = f'%{request_number_filter}%'
                query += ' AND (mr.request_number LIKE ? OR CAST(mr.id AS TEXT) LIKE ?)'
                params.extend([like_value, like_value])
            query += ' ORDER BY mr.created_at DESC'
            requests = conn.execute(query, params).fetchall()
            cursor = conn.execute('PRAGMA table_info(maintenance_requests)')
            columns = [col[1] for col in cursor.fetchall()]
            has_assigned_admin_id = 'assigned_admin_id' in columns
            has_assigned_at = 'assigned_at' in columns
            result = []
            for req in requests:
                admin_id_field = 'assigned_admin_id' if has_assigned_admin_id else 'admin_id'
                admin_fio_field = 'assigned_admin_fio' if has_assigned_admin_id else 'admin_fio'
                assigned_at_field = 'assigned_at' if has_assigned_at else 'taken_at'
                def get_field(field_name, default=''):
                        if field_name in req.keys():
                            value = req[field_name]
                            return value if value is not None else default
                        return default
                created_at_raw = get_field('created_at') or ''
                assigned_at_raw = get_field(assigned_at_field) or ''
                closed_at_raw = get_field('closed_at') or ''
                result.append({
                    'id': get_field('id', 0),
                    'employee_id': get_field('employee_id', 0),
                    'tg_user_id': get_field('tg_user_id'),
                    'tg_username': get_field('tg_username') or '',
                    'student_fio': get_field('student_fio_display') or get_field('student_fio') or '',
                    'building': get_field('building_display') or get_field('building') or '',
                    'entrance': get_field('entrance_display') or get_field('entrance') or '',
                    'room_number': get_field('room_number_display') or get_field('room_number') or '',
                    'message': get_field('message') or '',
                    'status': get_field('status') or 'new',
                    'request_number': get_field('request_number') or '',
                    'assigned_admin_id': get_field(admin_id_field),
                    'assigned_admin_fio': get_field(admin_fio_field) or '',
                    'admin_comment': get_field('admin_comment') or '',
                    'created_at': created_at_raw,
                    'assigned_at': assigned_at_raw,
                    'closed_at': closed_at_raw,
                    'created_at_msk': convert_timestamp_to_moscow(created_at_raw),
                    'assigned_at_msk': convert_timestamp_to_moscow(assigned_at_raw),
                    'closed_at_msk': convert_timestamp_to_moscow(closed_at_raw)
                })
        
        return jsonify({'success': True, 'requests': result})


@maintenance_bp.route('/api/maintenance_requests', methods=['POST'])
def api_create_maintenance_request():
    data = request.json
    if not data:
        return jsonify({'error': 'Отсутствуют данные'}), 400
    tg_user_id = data.get('tg_user_id')
    message = data.get('message', '').strip()
    if not tg_user_id or not message:
        return jsonify({'error': 'Недостаточно данных'}), 400
    with get_db() as conn:
        tg_user = conn.execute('SELECT employee_id FROM tg_users WHERE tg_user_id = ?', (tg_user_id,)).fetchone()
        if not tg_user or not tg_user['employee_id']:
            return jsonify({'error': 'Студент не найден'}), 404
        
        employee = conn.execute('''
            SELECT id, fio, building, entrance, room_number 
            FROM employees WHERE id = ?
        ''', (tg_user['employee_id'],)).fetchone()
        
        if not employee:
            return jsonify({'error': 'Студент не найден'}), 404
        
        cursor = conn.execute('PRAGMA table_info(maintenance_requests)')
        columns = [col[1] for col in cursor.fetchall()]
        created_at = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            INSERT INTO maintenance_requests 
            (employee_id, tg_user_id, student_fio, building, entrance, room_number, message, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?)
        ''', (
            employee['id'],
            tg_user_id,
            employee['fio'] or '',
            employee['building'] or '',
            employee['entrance'] or '',
            employee['room_number'] or '',
            message,
            created_at
        ))
        conn.commit()
        return jsonify({'success': True})


@maintenance_bp.route('/api/maintenance_requests/<int:request_id>/assign', methods=['POST'])
@require_permission('manage_rooms')
def api_assign_maintenance_request(request_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    comment = data.get('comment', '').strip()
    request_number = data.get('request_number', '').strip()
    
    with get_db() as conn:
        req = conn.execute('SELECT * FROM maintenance_requests WHERE id = ?', (request_id,)).fetchone()
        if not req:
            return jsonify({'error': 'Заявка не найдена'}), 404
        req_status = req.get('status') if isinstance(req, dict) else (req['status'] if 'status' in req.keys() else None)
        if req_status and req_status != 'new':
            return jsonify({'error': f'Заявка уже обработана (статус: {req_status})'}), 400
        
        admin = conn.execute('SELECT id, fio FROM admins WHERE id = ?', (admin_id,)).fetchone()
        admin_fio = admin['fio'] if admin and admin['fio'] else ''
        
        if not request_number:
            date_prefix = datetime.now().strftime('%Y%m%d')
            last_req = conn.execute('''
                SELECT request_number FROM maintenance_requests 
                WHERE request_number LIKE ? 
                ORDER BY id DESC LIMIT 1
            ''', (f'REQ-{date_prefix}-%',)).fetchone()
            
            if last_req and 'request_number' in last_req.keys() and last_req['request_number']:
                    last_num = int(last_req['request_number'].split('-')[-1])
                    request_number = f'REQ-{date_prefix}-{last_num + 1:03d}'
            else:
                request_number = f'REQ-{date_prefix}-001'
        
        cursor = conn.execute('PRAGMA table_info(maintenance_requests)')
        columns = [col[1] for col in cursor.fetchall()]
        has_assigned_admin_id = 'assigned_admin_id' in columns
        has_assigned_at = 'assigned_at' in columns
        
        assigned_at = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')
        
        if has_assigned_admin_id and has_assigned_at:
            conn.execute('''
                UPDATE maintenance_requests 
                SET status = 'in_progress',
                    request_number = ?,
                    assigned_admin_id = ?,
                    assigned_admin_fio = ?,
                    admin_comment = ?,
                    assigned_at = ?
                WHERE id = ?
            ''', (request_number, admin_id, admin_fio, comment, assigned_at, request_id))
        else:
            conn.execute('''
                UPDATE maintenance_requests 
                SET status = 'in_progress',
                    request_number = ?,
                    admin_id = ?,
                    admin_fio = ?,
                    admin_comment = ?,
                    taken_at = ?
                WHERE id = ?
            ''', (request_number, admin_id, admin_fio, comment, assigned_at, request_id))
        conn.commit()
        
        tg_user_id = req['tg_user_id'] if 'tg_user_id' in req.keys() and req['tg_user_id'] else None
        if tg_user_id:
                message_text = f"✅ <b>Ваша заявка в работе</b>\n\n"
                message_text += f"Номер заявки: <code>{request_number}</code>\n"
                if comment:
                    message_text += f"\nКомментарий: {comment}"
                TelegramService.send_notification(tg_user_id, message_text, parse_mode='HTML')
        
        return jsonify({'success': True, 'request_number': request_number})


@maintenance_bp.route('/api/maintenance_requests/<int:request_id>/comment', methods=['POST'])
@require_permission('manage_rooms')
def api_add_comment_to_request(request_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    comment = data.get('comment', '').strip()
    
    if not comment:
        return jsonify({'error': 'Комментарий не может быть пустым'}), 400
    
    with get_db() as conn:
        req = conn.execute('SELECT * FROM maintenance_requests WHERE id = ?', (request_id,)).fetchone()
        if not req:
            return jsonify({'error': 'Заявка не найдена'}), 404
        
        current_comment = req['admin_comment'] if 'admin_comment' in req.keys() and req['admin_comment'] else ''
        new_comment = f"{current_comment}\n{comment}" if current_comment else comment
        
        conn.execute('''
            UPDATE maintenance_requests 
            SET admin_comment = ?
            WHERE id = ?
        ''', (new_comment, request_id))
        conn.commit()
        
        tg_user_id = req['tg_user_id'] if 'tg_user_id' in req.keys() and req['tg_user_id'] else None
        request_num = req['request_number'] if 'request_number' in req.keys() and req['request_number'] else f'#{request_id}'
        if tg_user_id:
                TelegramService.send_notification(
                    tg_user_id,
                    f"💬 <b>Новый комментарий к заявке {request_num}</b>\n\n{comment}",
                    parse_mode='HTML'
                )
        
        return jsonify({'success': True})


@maintenance_bp.route('/api/maintenance_requests/<int:request_id>/close', methods=['POST'])
@require_permission('manage_rooms')
def api_close_maintenance_request(request_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        req = conn.execute('SELECT * FROM maintenance_requests WHERE id = ?', (request_id,)).fetchone()
        if not req:
            return jsonify({'error': 'Заявка не найдена'}), 404
        
        req_status = req['status'] if 'status' in req.keys() else None
        if req_status == 'closed':
            return jsonify({'error': 'Заявка уже закрыта'}), 400
        
        closed_at = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')
        
        conn.execute('''
            UPDATE maintenance_requests 
            SET status = 'closed',
                closed_at = ?
            WHERE id = ?
        ''', (closed_at, request_id))
        conn.commit()
        
        tg_user_id = req['tg_user_id'] if 'tg_user_id' in req.keys() and req['tg_user_id'] else None
        request_num = req['request_number'] if 'request_number' in req.keys() and req['request_number'] else f'#{request_id}'
        if tg_user_id:
                TelegramService.send_notification(
                    tg_user_id,
                    f"✅ <b>Заявка {request_num} закрыта</b>\n\n"
                    f"Ваша заявка была выполнена и закрыта администратором.",
                    parse_mode='HTML'
                )
        
        return jsonify({'success': True})


@maintenance_bp.route('/api/maintenance_requests/<int:request_id>/complete', methods=['POST'])
def api_complete_maintenance_request(request_id):
    data = request.json
    tg_user_id = data.get('tg_user_id')
    
    if not tg_user_id:
        return jsonify({'error': 'Недостаточно данных'}), 400
    
    with get_db() as conn:
        req = conn.execute('SELECT * FROM maintenance_requests WHERE id = ? AND tg_user_id = ?', 
                          (request_id, tg_user_id)).fetchone()
        if not req:
            return jsonify({'error': 'Заявка не найдена'}), 404
        
        req_status = req['status'] if 'status' in req.keys() else None
        if req_status != 'in_progress':
            return jsonify({'error': 'Заявка не в работе'}), 400
        
        closed_at = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')
        
        conn.execute('''
            UPDATE maintenance_requests 
            SET status = 'closed',
                closed_at = ?
            WHERE id = ?
        ''', (closed_at, request_id))
        conn.commit()
        
        return jsonify({'success': True})


@maintenance_bp.route('/api/maintenance_requests/my', methods=['GET'])
def api_get_my_maintenance_requests():
        data = request.json if request.is_json else {}
        tg_user_id = request.args.get('tg_user_id') or data.get('tg_user_id')
        if not tg_user_id:
            return jsonify({'error': 'Недостаточно данных'}), 400
        with get_db() as conn:
            tg_user = conn.execute('SELECT employee_id FROM tg_users WHERE tg_user_id = ?', (tg_user_id,)).fetchone()
            if not tg_user or not tg_user['employee_id']:
                return jsonify({'error': 'Студент не найден'}), 404
            
            requests = conn.execute('''
                SELECT * FROM maintenance_requests 
                WHERE employee_id = ?
                ORDER BY created_at DESC
                LIMIT 20
            ''', (tg_user['employee_id'],)).fetchall()
            
            cursor = conn.execute('PRAGMA table_info(maintenance_requests)')
            columns = [col[1] for col in cursor.fetchall()]
            has_assigned_admin_id = 'assigned_admin_id' in columns
            
            result = []
            for req in requests:
                admin_id_field = 'assigned_admin_id' if has_assigned_admin_id else 'admin_id'
                
                def get_field(field_name, default=''):
                    try:
                        if field_name in req.keys():
                            value = req[field_name]
                            return value if value is not None else default
                        return default
                    except (KeyError, TypeError):
                        return default
                
                result.append({
                    'id': get_field('id', 0),
                    'message': get_field('message') or '',
                    'status': get_field('status') or 'new',
                    'request_number': get_field('request_number') or '',
                    'admin_comment': get_field('admin_comment') or '',
                    'created_at': get_field('created_at') or '',
                    'created_at_msk': convert_timestamp_to_moscow(get_field('created_at') or ''),
                    'assigned_at': get_field('assigned_at') or get_field('taken_at') or '',
                    'assigned_at_msk': convert_timestamp_to_moscow(get_field('assigned_at') or get_field('taken_at') or ''),
                    'closed_at': get_field('closed_at') or '',
                    'closed_at_msk': convert_timestamp_to_moscow(get_field('closed_at') or '')
                })
            
            return jsonify({'success': True, 'requests': result})

