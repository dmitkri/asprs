"""Роуты для системы обхода несовершеннолетних"""
import sqlite3
from flask import Blueprint, request, jsonify, session, redirect, render_template
from database import get_db
from utils.auth import require_permission, get_admin_role, require_admin
from utils.rounds import get_minors_by_entrance, get_minors_for_round, can_do_rounds, is_round_time
from config import MOSCOW_TZ
from datetime import datetime

rounds_bp = Blueprint('rounds_bp', __name__)

def generate_round_schedule(building, entrance):
    """Генерация графика дежурств для подъезда"""
    try:
        with get_db() as conn:
            # Получаем всех студентов, назначенных на обходы для этого подъезда
            students = conn.execute('''
                SELECT e.id, e.fio, e.room_number, ra.student_id
                FROM round_assignments ra
                JOIN employees e ON ra.student_id = e.id
                WHERE ra.building = ? AND ra.entrance = ?
                ORDER BY e.fio
            ''', (building, entrance)).fetchall()
            
            if not students:
                print(f"Нет студентов для генерации графика дежурств для {building}-{entrance}")
                return
            
            # Получаем старосту подъезда
            elder = conn.execute('''
                SELECT e.id, e.fio, tg.tg_user_id
                FROM employees e
                JOIN elder_assignments ea ON e.id = ea.employee_id
                LEFT JOIN tg_users tg ON e.id = tg.employee_id
                WHERE ea.building = ? AND ea.entrance = ? AND e.is_entrance_elder = 1
                LIMIT 1
            ''', (building, entrance)).fetchone()
            
            if not elder:
                print(f"Староста не найден для {building}-{entrance}")
                return
            
            # Формируем график дежурств
            schedule_text = f"📅 График дежурств\n\n"
            schedule_text += f"🏠 Корпус: {building}\n"
            schedule_text += f"🚪 Подъезд: {entrance}\n\n"
            schedule_text += f"👤 Староста: {elder['fio']}\n\n"
            schedule_text += "📋 Список студентов для дежурств:\n\n"
            
            for idx, student in enumerate(students, 1):
                schedule_text += f"{idx}. {student['fio']}"
                if student['room_number']:
                    schedule_text += f" (комната {student['room_number']})"
                schedule_text += "\n"
            
            # Отправляем график старосте в Telegram
            if elder['tg_user_id']:
                try:
                    from services.user_bot_service import send_message_as_user_sync
                    send_message_as_user_sync(elder['tg_user_id'], schedule_text)
                    print(f"График дежурств отправлен старосте {elder['fio']} (ID: {elder['tg_user_id']})")
                except Exception as e:
                    print(f"Ошибка отправки графика старосте: {e}")
            
    except Exception as e:
        print(f"Ошибка генерации графика дежурств: {e}")
        import traceback
        traceback.print_exc()
        raise

@rounds_bp.route('/admin/minors')
def admin_minors():
    """Страница со списками несовершеннолетних по подъездам"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect('/admin')
    
    # Проверяем права доступа - нужен доступ к управлению несовершеннолетними
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_minors'):
        return render_template('no_access.html', message='У вас нет доступа к этому разделу. Необходимо право "Управление несовершеннолетними".')
    
    return render_template('admin_minors.html')

@rounds_bp.route('/api/minors/list', methods=['GET'])
def api_minors_list():
    """Получить список несовершеннолетних студентов по подъездам с результатами обхода"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    building = request.args.get('building', '').strip()
    entrance = request.args.get('entrance', '').strip()
    date = request.args.get('date', '')
    
    # Если дата не указана, используем сегодняшнюю
    if not date:
        date = datetime.now(MOSCOW_TZ).date().isoformat()
    
    minors = get_minors_by_entrance(
        building=building if building else None,
        entrance=entrance if entrance else None
    )
    
    # Получаем результаты обхода за указанную дату
    with get_db() as conn:
        # Получаем список всех корпусов
        buildings = conn.execute('''
            SELECT DISTINCT building FROM employees 
            WHERE building IS NOT NULL AND building != ''
            ORDER BY building
        ''').fetchall()
        buildings_list = [row['building'] for row in buildings]
        
        # Получаем результаты обхода за дату
        rounds = conn.execute('''
            SELECT student_id, status, round_time, inspector_id
            FROM rounds
            WHERE round_date = ?
        ''', (date,)).fetchall()
        
        # Создаем словарь: student_id -> status
        rounds_dict = {}
        for round_row in rounds:
            rounds_dict[round_row['student_id']] = {
                'status': round_row['status'],
                'time': round_row['round_time']
            }
        
        # Добавляем результаты обхода к каждому студенту
        for building_key in minors:
            for entrance_key in minors[building_key]:
                for student in minors[building_key][entrance_key]:
                    student_id = student['id']
                    if student_id in rounds_dict:
                        student['round_status'] = rounds_dict[student_id]['status']
                        student['round_time'] = rounds_dict[student_id]['time']
                    else:
                        student['round_status'] = None
                        student['round_time'] = None
    
    return jsonify({
        'success': True,
        'minors': minors,
        'buildings': buildings_list,
        'date': date
    })

@rounds_bp.route('/api/minors/can_do_rounds', methods=['GET'])
def api_can_do_rounds_list():
    """Получить список студентов, которые могут делать обходы"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        students = conn.execute('''
            SELECT id, fio, building, entrance, room_number
            FROM employees
            WHERE can_do_rounds = 1
            ORDER BY fio
        ''').fetchall()
        
        result = [dict(row) for row in students]
    
    return jsonify({
        'success': True,
        'students': result
    })

@rounds_bp.route('/api/minors/set_minor', methods=['POST'])
def api_set_minor():
    """Установить/снять ручную отметку обхода для студента"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем права доступа
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_minors'):
        return jsonify({'error': 'Доступ запрещен. Необходимо право "Управление несовершеннолетними".'}), 403
    
    data = request.get_json(silent=True) or {}
    student_id = data.get('student_id')
    is_present = data.get('is_minor')  # True = был на обходе (present), False = не был (absent)
    date = data.get('date', '')
    
    if not student_id:
        return jsonify({'error': 'student_id обязателен'}), 400
    
    if not date:
        # Используем сегодняшнюю дату по умолчанию
        date = datetime.now(MOSCOW_TZ).date().isoformat()
    
    with get_db() as conn:
        # Проверяем, что студент существует
        student = conn.execute('''
            SELECT id, fio, building, entrance, room_number FROM employees WHERE id = ?
        ''', (student_id,)).fetchone()
        
        if not student:
            return jsonify({'error': 'Студент не найден'}), 404
        
        # Получаем информацию об администраторе
        admin = conn.execute('''
            SELECT id, fio FROM admins WHERE id = ?
        ''', (admin_id,)).fetchone()
        
        admin_fio = admin['fio'] if admin else 'Администратор'
        
        # Получаем текущее время
        now = datetime.now(MOSCOW_TZ)
        round_time = now.time().isoformat()
        
        # Определяем статус обхода
        status = 'present' if is_present else 'absent'
        
        # Проверяем, есть ли уже запись об обходе за эту дату
        existing_round = conn.execute('''
            SELECT id FROM rounds 
            WHERE student_id = ? AND round_date = ?
        ''', (student_id, date)).fetchone()
        
        if existing_round:
            # Обновляем существующую запись
            conn.execute('''
                UPDATE rounds 
                SET status = ?, round_time = ?, inspector_id = ?, inspector_tg_id = 0
                WHERE id = ?
            ''', (status, round_time, admin_id, existing_round['id']))
        else:
            # Создаем новую запись об обходе
            conn.execute('''
                INSERT INTO rounds 
                (round_date, round_time, inspector_id, inspector_tg_id, building, entrance, 
                 student_id, student_fio, room_number, status, vacation_info, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date, round_time, admin_id, 0,  # inspector_tg_id = 0 для ручной отметки
                student['building'] or '', student['entrance'] or '',
                student_id, student['fio'], student['room_number'] or '',
                status, '', now.isoformat()
            ))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Статус обхода обновлен'
    })

@rounds_bp.route('/api/minors/send_location_question', methods=['POST'])
def api_send_location_question():
    """Отправить сообщение несовершеннолетним, которых не было во время обхода"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем права доступа
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_minors'):
        return jsonify({'error': 'Доступ запрещен. Необходимо право "Управление несовершеннолетними".'}), 403
    
    data = request.get_json(silent=True) or {}
    date = data.get('date', '')
    
    if not date:
        # Используем сегодняшнюю дату по умолчанию
        date = datetime.now(MOSCOW_TZ).date().isoformat()
    
    try:
        # Получаем список несовершеннолетних, которых не было во время обхода
        with get_db() as conn:
            # Проверяем, существует ли колонка is_minor
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(employees)")
            columns = [col[1] for col in cursor.fetchall()]
            has_is_minor = 'is_minor' in columns
            
            # Получаем всех несовершеннолетних с Telegram ID
            from utils.rounds import is_minor
            query = '''
                SELECT e.id, e.fio, e.birth_date, tg.tg_user_id, tg.tg_username
            '''
            if has_is_minor:
                query = query.replace('e.birth_date, tg.tg_user_id', 'e.birth_date, e.is_minor, tg.tg_user_id')
            
            query += '''
                FROM employees e
                JOIN tg_users tg ON e.id = tg.employee_id
                WHERE e.birth_date IS NOT NULL AND e.birth_date != ''
            '''
            
            all_minors = conn.execute(query).fetchall()
            
            # Получаем результаты обхода за указанную дату
            rounds = conn.execute('''
                SELECT student_id, status
                FROM rounds
                WHERE round_date = ?
            ''', (date,)).fetchall()
            
            # Создаем множество ID студентов, которые были на обходе (present)
            present_student_ids = {row['student_id'] for row in rounds if row['status'] == 'present'}
            
            # Фильтруем несовершеннолетних, которых не было (absent или нет записи)
            absent_minors = []
            for row in all_minors:
                # Определяем несовершеннолетних только по дате рождения
                # Поле is_minor теперь используется для отметки обхода, а не для возраста
                if not is_minor(row['birth_date']):
                    continue
                
                student_id = row['id']
                # Если студент был present, пропускаем
                if student_id in present_student_ids:
                    continue
                
                # Если есть запись об обходе со статусом absent, или нет записи вообще - добавляем
                has_round_record = any(r['student_id'] == student_id for r in rounds)
                if not has_round_record or any(r['student_id'] == student_id and r['status'] == 'absent' for r in rounds):
                    absent_minors.append({
                        'employee_id': row['id'],
                        'fio': row['fio'],
                        'tg_user_id': row['tg_user_id'],
                        'tg_username': row['tg_username']
                    })
        
        # Отправляем сообщения через User Bot (от имени аккаунта)
        message = "Где вы находитесь?"
        
        sent_count = 0
        failed_count = 0
        failure_reasons = []
        
        # Пытаемся использовать User Bot
        try:
            from services.user_bot_service import send_message_as_user_sync, _import_pyrogram
            if not _import_pyrogram():
                return jsonify({
                    'success': False,
                    'error': 'User Bot не подключен или не авторизован. Настройте User Bot и повторите попытку.'
                }), 400
            send_message_fn = send_message_as_user_sync
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'Модуль User Bot (pyrogram/tgcrypto) не установлен. Отправка возможна только после настройки личного аккаунта.'
            }), 400
        
        # Сохраняем запросы в базу данных
        for minor in absent_minors:
            try:
                with get_db() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO minor_location_requests 
                        (tg_user_id, employee_id, fio, sent_at)
                        VALUES (?, ?, ?, ?)
                    """, (minor['tg_user_id'], minor['employee_id'], minor['fio'],
                          datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
            except Exception as e:
                print(f"Ошибка сохранения запроса для {minor.get('fio', 'Unknown')}: {e}")
        
        # Подготавливаем список сообщений для отправки
        messages_to_send = []
        for minor in absent_minors:
            try:
                try:
                    chat_id = int(minor['tg_user_id'])
                except Exception:
                    chat_id = minor['tg_user_id']
                
                messages_to_send.append({
                    'chat_id': chat_id,
                    'message': message,
                    'minor': minor
                })
            except Exception as e:
                print(f"Ошибка подготовки сообщения для {minor.get('fio', 'Unknown')}: {e}")
        
        # Если сообщений больше 29, используем пакетную отправку
        if len(messages_to_send) > 29:
            try:
                from services.user_bot_service import send_messages_batch_sync
                # Подготавливаем данные для пакетной отправки
                batch_messages = []
                for msg_data in messages_to_send:
                    batch_messages.append({
                        'chat_id': msg_data['chat_id'],
                        'message': msg_data['message'],
                        'student_info': msg_data['minor']['fio']
                    })
                
                # Отправляем через пакетную функцию
                batch_result = send_messages_batch_sync(batch_messages, batch_size=29, delay_between_batches=60)
                sent_count = batch_result['sent']
                failed_count = batch_result['failed']
                failure_reasons = batch_result['errors']
            except Exception as batch_err:
                print(f"Ошибка при пакетной отправке, переходим на обычную отправку: {batch_err}")
                # Fallback на обычную отправку
                for msg_data in messages_to_send:
                    try:
                        success = False
                        try:
                            success = send_message_fn(msg_data['chat_id'], msg_data['message'])
                        except ValueError as err:
                            failure_reasons.append(f"{msg_data['minor']['fio']} ({msg_data['chat_id']}): {str(err)}")
                        except Exception as err:
                            failure_reasons.append(f"{msg_data['minor']['fio']} ({msg_data['chat_id']}): {str(err)}")
                        
                        if success:
                            sent_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        print(f"Ошибка отправки сообщения несовершеннолетнему {msg_data['minor']['fio']}: {e}")
                        failed_count += 1
                        failure_reasons.append(f"{msg_data['minor']['fio']} ({msg_data['chat_id']}): {str(e)}")
        else:
            # Обычная отправка для <= 29 сообщений
            for msg_data in messages_to_send:
                try:
                    success = False
                    try:
                        success = send_message_fn(msg_data['chat_id'], msg_data['message'])
                    except ValueError as err:
                        failure_reasons.append(f"{msg_data['minor']['fio']} ({msg_data['chat_id']}): {str(err)}")
                    except Exception as err:
                        failure_reasons.append(f"{msg_data['minor']['fio']} ({msg_data['chat_id']}): {str(err)}")
                    
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    print(f"Ошибка отправки сообщения несовершеннолетнему {msg_data['minor']['fio']} (ID: {msg_data['chat_id']}): {e}")
                    failed_count += 1
                    failure_reasons.append(f"{msg_data['minor']['fio']} ({msg_data['chat_id']}): {str(e)}")
        
        response_data = {
            'success': True,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total': len(absent_minors),
            'errors': failure_reasons
        }
        return jsonify(response_data)
    except Exception as e:
        print(f"Ошибка в api_send_location_question: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@rounds_bp.route('/api/minors/set_can_do_rounds', methods=['POST'])
@require_permission('edit')
def api_set_can_do_rounds():
    """Установить/снять право на обход для студента"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    student_id = data.get('student_id')
    can_do = data.get('can_do_rounds', False)
    
    if not student_id:
        return jsonify({'error': 'student_id required'}), 400
    
    with get_db() as conn:
        conn.execute('''
            UPDATE employees
            SET can_do_rounds = ?
            WHERE id = ?
        ''', (1 if can_do else 0, student_id))
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Право на обход обновлено'
    })

@rounds_bp.route('/api/rounds/start', methods=['POST'])
def api_rounds_start():
    """Начать обход (для Telegram бота)"""
    data = request.json
    tg_user_id = data.get('tg_user_id')
    
    if not tg_user_id:
        return jsonify({'error': 'tg_user_id required'}), 400
    
    # Проверяем время (только с 22:00)
    if not is_round_time():
        return jsonify({
            'error': 'Обход можно начать только с 22:00 по Москве'
        }), 403
    
    with get_db() as conn:
        # Проверяем, может ли пользователь делать обходы
        inspector = conn.execute('''
            SELECT e.id, e.fio, e.building, e.entrance, e.can_do_rounds
            FROM employees e
            JOIN tg_users tg ON e.id = tg.employee_id
            WHERE tg.tg_user_id = ?
        ''', (tg_user_id,)).fetchone()
        
        if not inspector:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        if not inspector['can_do_rounds']:
            return jsonify({'error': 'У вас нет права на обход'}), 403
        
        # Проверяем, не идет ли уже обход
        today = datetime.now(MOSCOW_TZ).date().isoformat()
        active_round = conn.execute('''
            SELECT id FROM rounds
            WHERE inspector_tg_id = ? AND round_date = ?
            LIMIT 1
        ''', (tg_user_id, today)).fetchone()
        
        if active_round:
            return jsonify({'error': 'Обход уже начат сегодня'}), 400
        
        # Получаем список несовершеннолетних для подъезда инспектора
        if not inspector['building'] or not inspector['entrance']:
            return jsonify({'error': 'У вас не указан корпус или подъезд'}), 400
        
        minors = get_minors_for_round(inspector['building'], inspector['entrance'])
        
        if not minors:
            return jsonify({'error': 'Нет несовершеннолетних студентов в вашем подъезде'}), 404
        
        # Группируем по комнатам
        rooms = {}
        for minor in minors:
            room = minor['room_number']
            if room not in rooms:
                rooms[room] = []
            rooms[room].append(minor)
        
        return jsonify({
            'success': True,
            'building': inspector['building'],
            'entrance': inspector['entrance'],
            'rooms': rooms
        })

@rounds_bp.route('/api/rounds/record', methods=['POST'])
def api_rounds_record():
    """Записать результат обхода (для Telegram бота)"""
    data = request.json
    tg_user_id = data.get('tg_user_id')
    student_id = data.get('student_id')
    status = data.get('status')  # 'present' или 'absent'
    
    if not tg_user_id or not student_id or not status:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if status not in ['present', 'absent']:
        return jsonify({'error': 'Invalid status'}), 400
    
    now = datetime.now(MOSCOW_TZ)
    round_date = now.date().isoformat()
    round_time = now.time().isoformat()
    
    with get_db() as conn:
        # Получаем информацию об инспекторе и студенте
        inspector = conn.execute('''
            SELECT e.id, e.fio
            FROM employees e
            JOIN tg_users tg ON e.id = tg.employee_id
            WHERE tg.tg_user_id = ?
        ''', (tg_user_id,)).fetchone()
        
        if not inspector:
            return jsonify({'error': 'Inspector not found'}), 404
        
        student = conn.execute('''
            SELECT id, fio, building, entrance, room_number, vacation
            FROM employees
            WHERE id = ?
        ''', (student_id,)).fetchone()
        
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Записываем результат
        conn.execute('''
            INSERT INTO rounds 
            (round_date, round_time, inspector_id, inspector_tg_id, building, entrance, 
             student_id, student_fio, room_number, status, vacation_info, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            round_date, round_time, inspector['id'], tg_user_id,
            student['building'], student['entrance'], student['id'],
            student['fio'], student['room_number'], status,
            student['vacation'] or '', now.isoformat()
        ))
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Результат обхода записан'
    })

@rounds_bp.route('/api/rounds/history', methods=['GET'])
def api_rounds_history():
    """Получить историю обходов"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    date = request.args.get('date', '')
    if not date:
        date = datetime.now(MOSCOW_TZ).date().isoformat()
    
    with get_db() as conn:
        rounds = conn.execute('''
            SELECT r.*, e.fio as inspector_fio
            FROM rounds r
            JOIN employees e ON r.inspector_id = e.id
            WHERE r.round_date = ?
            ORDER BY r.round_time DESC
        ''', (date,)).fetchall()
        
        result = [dict(row) for row in rounds]
    
    return jsonify({
        'success': True,
        'rounds': result
    })

@rounds_bp.route('/admin/round_assignments')
def admin_round_assignments():
    """Страница управления назначениями студентов на подъезды"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect('/admin')
    
    # Проверяем права доступа
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_round_assignments'):
        return render_template('no_access.html', message='У вас нет доступа к этому разделу. Необходимо право "Управление назначениями на обход".')
    
    role = get_admin_role(admin_id)
    return render_template('admin_round_assignments.html', admin_role=role)

@rounds_bp.route('/api/round_assignments/chiefs', methods=['GET'])
def api_get_round_chiefs():
    """Получить список старших студентов (is_round_chief = 1)"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        chiefs = conn.execute('''
            SELECT id, fio, building, entrance, room_number, is_round_chief
            FROM employees
            WHERE is_round_chief = 1
            ORDER BY fio
        ''').fetchall()
        
        result = [dict(row) for row in chiefs]
    
    return jsonify({
        'success': True,
        'chiefs': result
    })

@rounds_bp.route('/api/round_assignments/set_chief', methods=['POST'])
def api_set_round_chief():
    """Установить/снять статус старшего студента"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Только суперадмин может назначать старшего студента (проверка через manage_admins)
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_admins'):
        return jsonify({'error': 'Доступ запрещен. Только суперадмин может назначать старшего студента'}), 403
    
    data = request.json
    student_id = data.get('student_id')
    is_chief = data.get('is_chief', False)
    
    if not student_id:
        return jsonify({'error': 'student_id обязателен'}), 400
    
    with get_db() as conn:
        conn.execute('''
            UPDATE employees
            SET is_round_chief = ?
            WHERE id = ?
        ''', (1 if is_chief else 0, student_id))
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Статус главного обновлен'
    })

@rounds_bp.route('/api/round_assignments/set_elder', methods=['POST'])
@require_admin()
def api_set_entrance_elder():
    """Установка/снятие статуса старосты подъезда"""
    try:
        admin_id = session.get('admin_id')
        if not admin_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
        # Только суперадмин может назначать старост подъездов (проверка через manage_admins)
        from utils.auth import has_permission
        if not has_permission(admin_id, 'manage_admins'):
            return jsonify({'success': False, 'error': 'Доступ запрещен. Только суперадмин может назначать старост подъездов'}), 403
        
        data = request.get_json()
        employee_id = data.get('employee_id')
        is_elder = data.get('is_elder', False)
        building = data.get('building', '').strip()
        entrance = data.get('entrance', '').strip()
        
        if not employee_id:
            return jsonify({'success': False, 'error': 'Не указан ID студента'}), 400
        
        with get_db() as conn:
            if is_elder:
                # Устанавливаем статус старосты
                if not building or not entrance:
                    return jsonify({'success': False, 'error': 'Не указаны корпус и подъезд'}), 400
                
                # Устанавливаем флаг is_entrance_elder
                conn.execute('''
                    UPDATE employees 
                    SET is_entrance_elder = 1
                    WHERE id = ?
                ''', (employee_id,))
                
                # Добавляем или обновляем назначение в elder_assignments
                conn.execute('''
                    INSERT OR REPLACE INTO elder_assignments (employee_id, building, entrance, assigned_by)
                    VALUES (?, ?, ?, ?)
                ''', (employee_id, building, entrance, admin_id))
            else:
                # Снимаем статус старосты
                conn.execute('''
                    UPDATE employees 
                    SET is_entrance_elder = 0
                    WHERE id = ?
                ''', (employee_id,))
                
                # Удаляем все назначения этого студента
                conn.execute('''
                    DELETE FROM elder_assignments
                    WHERE employee_id = ?
                ''', (employee_id,))
            
            conn.commit()
            
            # Получаем обновленную информацию о студенте
            employee = conn.execute('''
                SELECT id, fio, is_entrance_elder, building, entrance
                FROM employees
                WHERE id = ?
            ''', (employee_id,)).fetchone()
            
            # Получаем назначения старосты
            assignments = conn.execute('''
                SELECT building, entrance
                FROM elder_assignments
                WHERE employee_id = ?
            ''', (employee_id,)).fetchall()
            
            # Если староста назначен, отправляем уведомление в Telegram
            if is_elder:
                # Получаем Telegram ID старосты
                tg_user = conn.execute('''
                    SELECT tg_user_id FROM tg_users WHERE employee_id = ?
                ''', (employee_id,)).fetchone()
                
                if tg_user and tg_user['tg_user_id']:
                    try:
                        from services.user_bot_service import send_message_as_user_sync
                        message = (
                            f"✅ Вы назначены старостой подъезда!\n\n"
                            f"🏠 Корпус: {building}\n"
                            f"🚪 Подъезд: {entrance}\n\n"
                            f"Используйте кнопку '📅 График дежурств' в меню бота для генерации графика."
                        )
                        send_message_as_user_sync(tg_user['tg_user_id'], message)
                    except Exception as e:
                        print(f"Ошибка отправки уведомления старосте: {e}")
            
            return jsonify({
                'success': True,
                'employee': {
                    'id': employee['id'],
                    'fio': employee['fio'],
                    'is_entrance_elder': employee['is_entrance_elder'],
                    'building': employee['building'],
                    'entrance': employee['entrance'],
                    'assignments': [{'building': a['building'], 'entrance': a['entrance']} for a in assignments]
                }
            })
    except Exception as e:
        print(f"Ошибка в api_set_entrance_elder: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@rounds_bp.route('/api/round_assignments/elders', methods=['GET'])
@require_admin()
def api_get_entrance_elders():
    """Получение списка старост подъездов"""
    try:
        with get_db() as conn:
            # Получаем старост с их назначениями
            elders = conn.execute('''
                SELECT e.id, e.fio, e.is_entrance_elder,
                       ea.building, ea.entrance
                FROM employees e
                LEFT JOIN elder_assignments ea ON e.id = ea.employee_id
                WHERE e.is_entrance_elder = 1
                ORDER BY COALESCE(ea.building, ''), COALESCE(ea.entrance, ''), e.fio
            ''').fetchall()
            
            # Группируем по студентам
            elders_dict = {}
            for elder in elders:
                elder_id = elder['id']
                if elder_id not in elders_dict:
                    elders_dict[elder_id] = {
                        'id': elder['id'],
                        'fio': elder['fio'],
                        'is_entrance_elder': elder['is_entrance_elder'],
                        'assignments': []
                    }
                
                # Добавляем назначение, если оно есть
                if elder['building'] and elder['entrance']:
                    assignment = {
                        'building': elder['building'],
                        'entrance': elder['entrance']
                    }
                    if assignment not in elders_dict[elder_id]['assignments']:
                        elders_dict[elder_id]['assignments'].append(assignment)
            
            result = list(elders_dict.values())
            
            return jsonify({'success': True, 'elders': result})
    except Exception as e:
        print(f"Ошибка в api_get_entrance_elders: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@rounds_bp.route('/api/round_assignments/list', methods=['GET'])
def api_get_round_assignments():
    """Получить список назначений студентов на подъезды"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    building = request.args.get('building', '').strip()
    entrance = request.args.get('entrance', '').strip()
    
    with get_db() as conn:
        query = '''
            SELECT ra.*, e.fio as student_fio, e.building as student_building, 
                   e.entrance as student_entrance, e.room_number,
                   assigner.fio as assigned_by_fio
            FROM round_assignments ra
            JOIN employees e ON ra.student_id = e.id
            LEFT JOIN employees assigner ON ra.assigned_by = assigner.id
            WHERE 1=1
        '''
        params = []
        
        if building:
            query += ' AND ra.building = ?'
            params.append(building)
        
        if entrance:
            query += ' AND ra.entrance = ?'
            params.append(entrance)
        
        query += ' ORDER BY ra.building, ra.entrance, e.fio'
        
        assignments = conn.execute(query, params).fetchall()
        result = [dict(row) for row in assignments]
    
    return jsonify({
        'success': True,
        'assignments': result
    })

@rounds_bp.route('/api/round_assignments/assign', methods=['POST'])
def api_assign_round():
    """Назначить студента на обход подъезда"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем права доступа
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_round_assignments'):
        return jsonify({'error': 'Доступ запрещен. Необходимо право "Управление назначениями на обход".'}), 403
    
    data = request.json
    student_id = data.get('student_id')
    building = data.get('building', '').strip()
    entrance = data.get('entrance', '').strip()
    
    if not student_id or not building or not entrance:
        return jsonify({'error': 'student_id, building и entrance обязательны'}), 400
    
    with get_db() as conn:
        # Проверяем, что студент существует и имеет право обхода
        student = conn.execute('''
            SELECT id, fio, can_do_rounds 
            FROM employees 
            WHERE id = ?
        ''', (student_id,)).fetchone()
        if not student:
            return jsonify({'error': 'Студент не найден'}), 404
        
        if not student['can_do_rounds']:
            return jsonify({'error': 'У этого студента нет права обхода. Сначала предоставьте право обхода на странице "Управление правом обхода".'}), 400
        
        # Добавляем или обновляем назначение
        conn.execute('''
            INSERT OR REPLACE INTO round_assignments 
            (student_id, building, entrance, assigned_by)
            VALUES (?, ?, ?, ?)
        ''', (student_id, building, entrance, admin_id))
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Студент назначен на обход подъезда'
    })

@rounds_bp.route('/api/round_assignments/remove', methods=['POST'])
def api_remove_round_assignment():
    """Удалить назначение студента на обход подъезда"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем права доступа
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_round_assignments'):
        return jsonify({'error': 'Доступ запрещен. Необходимо право "Управление назначениями на обход".'}), 403
    
    data = request.json
    assignment_id = data.get('assignment_id')
    
    if not assignment_id:
        return jsonify({'error': 'assignment_id обязателен'}), 400
    
    with get_db() as conn:
        conn.execute('DELETE FROM round_assignments WHERE id = ?', (assignment_id,))
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Назначение удалено'
    })

@rounds_bp.route('/api/round_assignments/students', methods=['GET'])
def api_get_students_for_assignment():
    """Получить список студентов для назначения (с can_do_rounds = 1)"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        students = conn.execute('''
            SELECT id, fio, building, entrance, room_number, can_do_rounds
            FROM employees
            WHERE can_do_rounds = 1
            ORDER BY fio
        ''').fetchall()
        
        result = [dict(row) for row in students]
    
    return jsonify({
        'success': True,
        'students': result
    })

@rounds_bp.route('/api/round_assignments/educators_list', methods=['GET'])
@require_permission('manage_round_assignments')
def api_educators_list():
    """Получить список воспитателей (администраторов с ролью vospitatel)"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        educators = conn.execute('''
            SELECT id, username, fio, COALESCE(max_entrances, 0) as max_entrances
            FROM admins
            WHERE role = 'vospitatel' AND is_active = 1
            ORDER BY fio, username
        ''').fetchall()
        
        result = []
        for e in educators:
            result.append({
                'id': e['id'],
                'fio': e['fio'] or e['username'] or '',
                'username': e['username'] or '',
                'max_entrances': e['max_entrances'] or 0
            })
        
        return jsonify({'success': True, 'educators': result})

@rounds_bp.route('/api/round_assignments/all_students', methods=['GET'])
def api_get_all_students():
    """Получить список всех студентов для выбора главного"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем права доступа
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_round_assignments'):
        return jsonify({'error': 'Доступ запрещен. Необходимо право "Управление назначениями на обход".'}), 403
    
    search = request.args.get('search', '').strip()
    can_do_rounds_only = request.args.get('can_do_rounds', '').strip() == '1'
    
    with get_db() as conn:
        query = '''
            SELECT id, fio, building, entrance, room_number, can_do_rounds, is_round_chief, 
                   photo, group_name, is_entrance_elder
            FROM employees
            WHERE 1=1
        '''
        params = []
        
        if can_do_rounds_only:
            query += ' AND can_do_rounds = 1'
        
        query += ' ORDER BY fio'
        
        students = conn.execute(query, params).fetchall()
        
        # Фильтрация через Python для корректной работы с кириллицей
        result = []
        search_lower = search.lower() if search else ''
        
        for row in students:
            student_dict = dict(row)
            
            # Если есть поисковый запрос, фильтруем через Python
            if search_lower:
                fio = str(student_dict.get('fio') or '').lower()
                group_name = str(student_dict.get('group_name') or '').lower()
                building = str(student_dict.get('building') or '').lower()
                room_number = str(student_dict.get('room_number') or '').lower()
                
                # Проверяем, содержит ли хотя бы одно поле поисковый запрос
                if (search_lower in fio or 
                    search_lower in group_name or
                    search_lower in building or
                    search_lower in room_number):
                    result.append(student_dict)
            else:
                # Если поиска нет, добавляем всех
                result.append(student_dict)
    
    return jsonify({
        'success': True,
        'students': result
    })

@rounds_bp.route('/api/round_assignments/students_for_rounds', methods=['GET'])
def api_get_students_for_rounds():
    """Получить список студентов с правом обхода для назначения на обходы (формат для UserSelect)"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем права доступа
    from utils.auth import has_permission
    if not has_permission(admin_id, 'manage_round_assignments'):
        return jsonify({'error': 'Доступ запрещен. Необходимо право "Управление назначениями на обход".'}), 403
    
    search = request.args.get('q', '').strip().lower()
    limit = int(request.args.get('limit', 1000))
    
    with get_db() as conn:
        query = '''
            SELECT id, fio, building, entrance, room_number, photo, group_name
            FROM employees
            WHERE can_do_rounds = 1
        '''
        
        if search:
            # Используем поиск, который работает с кириллицей
            employees = conn.execute(query + ' ORDER BY fio').fetchall()
            result = []
            for row in employees:
                fio = str(row['fio'] or '').lower()
                group_name = str(row['group_name'] if row['group_name'] else '').lower()
                building = str(row['building'] if row['building'] else '').lower()
                room_number = str(row['room_number'] if row['room_number'] else '').lower()
                
                # Поиск по ФИО, группе, корпусу или номеру комнаты
                if (search in fio or 
                    (group_name and search in group_name) or
                    (building and search in building) or
                    (room_number and search in room_number)):
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
        else:
            query += ' ORDER BY fio LIMIT ?'
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

@rounds_bp.route('/api/round_assignments/students_for_rounds_chief', methods=['GET'])
def api_get_students_for_rounds_chief():
    """Получить список студентов с правом обхода для назначения старшим студентом"""
    tg_user_id = request.args.get('tg_user_id')
    
    if not tg_user_id:
        return jsonify({'error': 'tg_user_id обязателен'}), 400
    
    with get_db() as conn:
        # Проверяем, является ли пользователь старшим студентом
        tg_user = conn.execute('''
            SELECT employee_id FROM tg_users WHERE tg_user_id = ?
        ''', (tg_user_id,)).fetchone()
        
        if not tg_user or not tg_user['employee_id']:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        chief = conn.execute('''
            SELECT id, is_round_chief
            FROM employees
            WHERE id = ?
        ''', (tg_user['employee_id'],)).fetchone()
        
        if not chief or not chief['is_round_chief']:
            return jsonify({'error': 'Вы не являетесь старшим студентом'}), 403
        
        # Получаем список студентов с правом обхода
        students = conn.execute('''
            SELECT id, fio, building, entrance, room_number, photo, group_name
            FROM employees
            WHERE can_do_rounds = 1
            ORDER BY fio
            LIMIT 100
        ''').fetchall()
        
        result = []
        for row in students:
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
        'students': result
    })

@rounds_bp.route('/api/round_assignments/assign_by_chief', methods=['POST'])
def api_assign_round_by_chief():
    """Назначить студента на обход подъезда от имени старшего студента"""
    data = request.json
    student_id = data.get('student_id')
    building = data.get('building', '').strip()
    entrance = data.get('entrance', '').strip()
    tg_user_id = data.get('tg_user_id')
    
    if not student_id or not building or not entrance or not tg_user_id:
        return jsonify({'error': 'student_id, building, entrance и tg_user_id обязательны'}), 400
    
    with get_db() as conn:
        # Проверяем, является ли пользователь старшим студентом
        tg_user = conn.execute('''
            SELECT employee_id FROM tg_users WHERE tg_user_id = ?
        ''', (tg_user_id,)).fetchone()
        
        if not tg_user or not tg_user['employee_id']:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        chief = conn.execute('''
            SELECT id, is_round_chief, fio
            FROM employees
            WHERE id = ?
        ''', (tg_user['employee_id'],)).fetchone()
        
        if not chief or not chief['is_round_chief']:
            return jsonify({'error': 'Вы не являетесь старшим студентом'}), 403
        
        # Проверяем, что студент существует и имеет право обхода
        student = conn.execute('''
            SELECT id, fio, can_do_rounds 
            FROM employees 
            WHERE id = ?
        ''', (student_id,)).fetchone()
        if not student:
            return jsonify({'error': 'Студент не найден'}), 404
        
        if not student['can_do_rounds']:
            return jsonify({'error': 'У этого студента нет права обхода'}), 400
        
        # Добавляем или обновляем назначение
        try:
            conn.execute('''
                INSERT OR REPLACE INTO round_assignments 
                (student_id, building, entrance, assigned_by)
                VALUES (?, ?, ?, ?)
            ''', (student_id, building, entrance, chief['id']))
            conn.commit()
        except sqlite3.IntegrityError:
            # Назначение уже существует, это нормально
            pass
    
    return jsonify({
        'success': True,
        'message': 'Студент назначен на обход подъезда'
    })

@rounds_bp.route('/api/round_assignments/restrictions', methods=['GET'])
@require_permission('manage_round_assignments')
def api_get_round_restrictions():
    """Получить список ограничений на обходы"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    student_id = request.args.get('student_id', type=int)
    
    with get_db() as conn:
        # Получаем ограничения для студентов
        query_students = '''
            SELECT rr.*, e.fio as person_fio, 'student' as person_type
            FROM round_restrictions rr
            JOIN employees e ON rr.student_id = e.id
            WHERE rr.student_id > 0
        '''
        params_students = []
        
        if student_id and student_id > 0:
            query_students += ' AND rr.student_id = ?'
            params_students.append(student_id)
        
        query_students += ' ORDER BY e.fio, rr.building, rr.entrance'
        
        # Получаем ограничения для воспитателей
        query_educators = '''
            SELECT rr.*, a.fio as person_fio, 'educator' as person_type
            FROM round_restrictions rr
            JOIN admins a ON ABS(rr.student_id) = a.id
            WHERE rr.student_id < 0 AND a.role = 'vospitatel'
        '''
        params_educators = []
        
        if student_id and student_id < 0:
            query_educators += ' AND ABS(rr.student_id) = ?'
            params_educators.append(abs(student_id))
        
        query_educators += ' ORDER BY a.fio, rr.building, rr.entrance'
        
        restrictions_students = conn.execute(query_students, params_students).fetchall()
        restrictions_educators = conn.execute(query_educators, params_educators).fetchall()
        
        result = []
        for r in restrictions_students:
            result.append({
                'id': r['id'],
                'student_id': r['student_id'],
                'person_fio': r['person_fio'],
                'person_type': 'student',
                'building': r['building'],
                'entrance': r['entrance'],
                'reason': r.get('reason', ''),
                'created_at': r['created_at']
            })
        for r in restrictions_educators:
            result.append({
                'id': r['id'],
                'student_id': r['student_id'],  # Отрицательный ID для воспитателя
                'person_fio': r['person_fio'],
                'person_type': 'educator',
                'building': r['building'],
                'entrance': r['entrance'],
                'reason': r.get('reason', ''),
                'created_at': r['created_at']
            })
    
    return jsonify({
        'success': True,
        'restrictions': result
    })

@rounds_bp.route('/api/round_assignments/restrictions', methods=['POST'])
@require_permission('manage_round_assignments')
def api_add_round_restriction():
    """Добавить ограничение на обход"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    student_id = data.get('student_id')  # Может быть отрицательным для воспитателей
    educator_id = data.get('educator_id')  # ID воспитателя (если указан)
    building = data.get('building', '').strip()
    entrance = data.get('entrance', '').strip()
    reason = data.get('reason', '').strip()
    
    # Определяем, это студент или воспитатель
    is_educator = educator_id is not None
    if is_educator:
        student_id = -abs(educator_id)  # Отрицательный ID для воспитателя
    elif not student_id:
        return jsonify({'error': 'student_id или educator_id обязателен'}), 400
    
    if not building or not entrance:
        return jsonify({'error': 'Корпус и подъезд обязательны'}), 400
    
    with get_db() as conn:
        if is_educator:
            # Проверяем, что воспитатель существует
            educator = conn.execute('''
                SELECT id FROM admins WHERE id = ? AND role = 'vospitatel'
            ''', (abs(student_id),)).fetchone()
            
            if not educator:
                return jsonify({'error': 'Воспитатель не найден'}), 404
        else:
            # Проверяем, что студент существует
            student = conn.execute('''
                SELECT id, fio FROM employees WHERE id = ?
            ''', (student_id,)).fetchone()
            
            if not student:
                return jsonify({'error': 'Студент не найден'}), 404
        
        # Добавляем ограничение
        try:
            conn.execute('''
                INSERT INTO round_restrictions (student_id, building, entrance, reason)
                VALUES (?, ?, ?, ?)
            ''', (student_id, building, entrance, reason))
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Ограничение уже существует'}), 400
    
    return jsonify({
        'success': True,
        'message': 'Ограничение добавлено'
    })

@rounds_bp.route('/api/round_assignments/restrictions/<int:restriction_id>', methods=['DELETE'])
@require_permission('manage_round_assignments')
def api_delete_round_restriction(restriction_id):
    """Удалить ограничение на обход"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM round_restrictions WHERE id = ?', (restriction_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Ограничение не найдено'}), 404
    
    return jsonify({
        'success': True,
        'message': 'Ограничение удалено'
    })

@rounds_bp.route('/api/round_assignments/set_max_entrances', methods=['POST'])
@require_permission('manage_round_assignments')
def api_set_max_entrances():
    """Установить максимальное количество подъездов для воспитателя (администратора с ролью vospitatel)"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    educator_id = data.get('educator_id')  # ID администратора-воспитателя
    max_entrances = data.get('max_entrances', 0)
    
    if not educator_id:
        return jsonify({'error': 'educator_id обязателен'}), 400
    
    try:
        max_entrances = int(max_entrances)
        if max_entrances < 0:
            return jsonify({'error': 'Количество подъездов не может быть отрицательным'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Некорректное значение количества подъездов'}), 400
    
    with get_db() as conn:
        # Проверяем, что администратор существует и является воспитателем
        educator = conn.execute('''
            SELECT id, username, fio, role FROM admins WHERE id = ? AND role = 'vospitatel'
        ''', (educator_id,)).fetchone()
        
        if not educator:
            return jsonify({'error': 'Воспитатель не найден или не имеет роль vospitatel'}), 404
        
        # Обновляем max_entrances
        conn.execute('''
            UPDATE admins
            SET max_entrances = ?
            WHERE id = ?
        ''', (max_entrances, educator_id))
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Количество подъездов обновлено'
    })

@rounds_bp.route('/api/round_assignments/generate_schedule', methods=['POST'])
@require_permission('manage_round_assignments')
def api_generate_round_schedule():
    """Генерация графика назначений на обход с учетом ограничений"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    replace_existing = data.get('replace_existing', False)
    
    with get_db() as conn:
        # Получаем всех студентов с правом обхода
        students = conn.execute('''
            SELECT id, fio, building, entrance
            FROM employees
            WHERE can_do_rounds = 1
            ORDER BY fio
        ''').fetchall()
        
        # Получаем всех воспитателей (администраторов с ролью vospitatel)
        educators = conn.execute('''
            SELECT id, username, fio, COALESCE(max_entrances, 0) as max_entrances
            FROM admins
            WHERE role = 'vospitatel' AND is_active = 1
            ORDER BY fio, username
        ''').fetchall()
        
        if not students and not educators:
            return jsonify({'error': 'Нет студентов с правом обхода и воспитателей'}), 400
        
        # Получаем все корпуса и подъезды
        buildings_entrances = conn.execute('''
            SELECT DISTINCT building, entrance
            FROM employees
            WHERE building IS NOT NULL AND building != ''
            AND entrance IS NOT NULL AND entrance != ''
            ORDER BY building, entrance
        ''').fetchall()
        
        if not buildings_entrances:
            return jsonify({'error': 'Нет доступных корпусов и подъездов'}), 400
        
        # Получаем все ограничения
        restrictions = conn.execute('''
            SELECT student_id, building, entrance
            FROM round_restrictions
        ''').fetchall()
        
        # Создаем словарь ограничений: (type, id, building, entrance) -> True
        # Для студентов: ('student', student_id, building, entrance)
        # Для воспитателей: ('educator', educator_id, building, entrance)
        restrictions_dict = {}
        for r in restrictions:
            # Ограничения могут быть для студентов (student_id > 0) или воспитателей (student_id < 0, где |student_id| = educator_id)
            student_id = r['student_id']
            if student_id < 0:
                # Это ограничение для воспитателя
                key = ('educator', abs(student_id), r['building'], r['entrance'])
            else:
                # Это ограничение для студента
                key = ('student', student_id, r['building'], r['entrance'])
            restrictions_dict[key] = True
        
        # Получаем существующие назначения
        existing_assignments = {}
        if not replace_existing:
            existing = conn.execute('''
                SELECT student_id, building, entrance
                FROM round_assignments
            ''').fetchall()
            for e in existing:
                key = (e['student_id'], e['building'], e['entrance'])
                existing_assignments[key] = True
        
        # Воспитатели уже получены из admins, студенты - обычные
        educators_list = [e for e in educators if e['max_entrances'] and e['max_entrances'] > 0]
        regular_students = list(students)
        
        # Создаем список подъездов для распределения
        entrances_to_assign = []
        for be in buildings_entrances:
            entrances_to_assign.append((be['building'], be['entrance']))
        
        # Распределяем воспитателей
        assignments = []
        educator_assignments = {}  # Счетчик назначений для каждого воспитателя
        
        # Сортируем воспитателей по убыванию max_entrances (сначала те, кому нужно больше подъездов)
        educators_sorted = sorted(educators_list, key=lambda x: x['max_entrances'] or 0, reverse=True)
        
        for educator in educators_sorted:
            max_ent = educator['max_entrances']
            educator_assignments[educator['id']] = 0
            
            # Получаем список доступных подъездов для этого воспитателя
            available_entrances = []
            for building, entrance in entrances_to_assign:
                restriction_key = ('educator', educator['id'], building, entrance)
                assignment_key = ('educator', educator['id'], building, entrance)
                
                # Пропускаем, если есть ограничение или уже назначен
                if restriction_key in restrictions_dict or assignment_key in existing_assignments:
                    continue
                
                available_entrances.append((building, entrance))
            
            # Назначаем воспитателя на доступные подъезды (до max_ent)
            for building, entrance in available_entrances[:max_ent]:
                # Для воспитателей сохраняем в round_assignments с отрицательным student_id
                # или создаем отдельную таблицу. Пока используем отрицательный ID
                assignments.append({
                    'is_educator': True,
                    'educator_id': educator['id'],
                    'building': building,
                    'entrance': entrance
                })
                assignment_key = ('educator', educator['id'], building, entrance)
                existing_assignments[assignment_key] = True
                educator_assignments[educator['id']] += 1
        
        # Распределяем обычных студентов на оставшиеся подъезды
        # Создаем список подъездов, которые еще не назначены
        assigned_entrances = set()
        for a in assignments:
            assigned_entrances.add((a['building'], a['entrance']))
        
        remaining_entrances = [e for e in entrances_to_assign if e not in assigned_entrances]
        
        if not regular_students and remaining_entrances:
            # Если нет обычных студентов, но есть незанятые подъезды
            # Пытаемся назначить воспитателей на дополнительные подъезды (если у них еще есть лимит)
            for educator in educators_sorted:
                max_ent = educator['max_entrances']
                current_count = educator_assignments.get(educator['id'], 0)
                
                if current_count >= max_ent:
                    continue
                
                # Ищем доступные подъезды для дополнительного назначения
                for building, entrance in remaining_entrances[:]:
                    if current_count >= max_ent:
                        break
                    
                    restriction_key = ('educator', educator['id'], building, entrance)
                    assignment_key = ('educator', educator['id'], building, entrance)
                    
                    if restriction_key in restrictions_dict or assignment_key in existing_assignments:
                        continue
                    
                    assignments.append({
                        'is_educator': True,
                        'educator_id': educator['id'],
                        'building': building,
                        'entrance': entrance
                    })
                    existing_assignments[assignment_key] = True
                    educator_assignments[educator['id']] += 1
                    remaining_entrances.remove((building, entrance))
        
        # Распределяем студентов по оставшимся подъездам (равномерно)
        if regular_students and remaining_entrances:
            # Создаем счетчик назначений для каждого студента
            student_assignments_count = {s['id']: 0 for s in regular_students}
            
            # Распределяем по кругу, чтобы нагрузка была равномерной
            for building, entrance in remaining_entrances:
                # Находим студента с минимальным количеством назначений
                best_student = None
                min_assignments = float('inf')
                
                for student in regular_students:
                    # Проверяем ограничения
                    restriction_key = ('student', student['id'], building, entrance)
                    if restriction_key in restrictions_dict:
                        continue
                    
                    # Проверяем, не назначен ли уже
                    assignment_key = ('student', student['id'], building, entrance)
                    if assignment_key in existing_assignments:
                        continue
                    
                    # Выбираем студента с минимальным количеством назначений
                    count = student_assignments_count.get(student['id'], 0)
                    if count < min_assignments:
                        min_assignments = count
                        best_student = student
                
                if best_student:
                    assignments.append({
                        'is_educator': False,
                        'student_id': best_student['id'],
                        'building': building,
                        'entrance': entrance
                    })
                    assignment_key = ('student', best_student['id'], building, entrance)
                    existing_assignments[assignment_key] = True
                    student_assignments_count[best_student['id']] = student_assignments_count.get(best_student['id'], 0) + 1
        
        # Сохраняем назначения в базу данных
        if replace_existing:
            conn.execute('DELETE FROM round_assignments')
            conn.execute('DELETE FROM educator_round_assignments')
        
        created = 0
        updated = 0
        for assignment in assignments:
            try:
                if assignment.get('is_educator'):
                    # Назначение воспитателя
                    conn.execute('''
                        INSERT INTO educator_round_assignments (educator_id, building, entrance, assigned_by)
                        VALUES (?, ?, ?, ?)
                    ''', (assignment['educator_id'], assignment['building'], assignment['entrance'], admin_id))
                    created += 1
                else:
                    # Назначение студента
                    conn.execute('''
                        INSERT INTO round_assignments (student_id, building, entrance, assigned_by)
                        VALUES (?, ?, ?, ?)
                    ''', (assignment['student_id'], assignment['building'], assignment['entrance'], admin_id))
                    created += 1
            except sqlite3.IntegrityError:
                # Назначение уже существует, обновляем
                if assignment.get('is_educator'):
                    conn.execute('''
                        UPDATE educator_round_assignments
                        SET assigned_by = ?
                        WHERE educator_id = ? AND building = ? AND entrance = ?
                    ''', (admin_id, assignment['educator_id'], assignment['building'], assignment['entrance']))
                else:
                    conn.execute('''
                        UPDATE round_assignments
                        SET assigned_by = ?
                        WHERE student_id = ? AND building = ? AND entrance = ?
                    ''', (admin_id, assignment['student_id'], assignment['building'], assignment['entrance']))
                updated += 1
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': f'График сгенерирован: создано {created}, обновлено {updated} назначений',
        'created': created,
        'updated': updated,
        'total': len(assignments)
    })

