"""Роуты для управления постельным бельем"""
from flask import Blueprint, request, jsonify, session, render_template, redirect, send_file, url_for
from datetime import datetime, timedelta
from database import get_db
from utils.auth import require_permission, has_permission, get_admin_role
from config import MOSCOW_TZ
import secrets
import io
import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

bed_linen_bp = Blueprint('bed_linen', __name__)

# TTL токена в секундах (24 часа)
TOKEN_TTL_SECONDS = 24 * 60 * 60

# Проверка доступности библиотек
try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


@bed_linen_bp.route('/api/bed_linen/add_date_for_all', methods=['POST'])
@require_permission('manage_bed_linen')
def api_add_date_for_all():
    """Админ создает период выдачи белья (дата начала и дата окончания)"""
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Необходима авторизация'}), 401
    
    data = request.get_json() or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({
            'success': False,
            'message': 'Необходимо указать дату начала и дату окончания'
        }), 400

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start_dt > end_dt:
            return jsonify({
                'success': False,
                'message': 'Дата начала не может быть позже даты окончания'
            }), 400
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Неверный формат даты. Используйте YYYY-MM-DD'
        }), 400
    
    with get_db() as conn:
        existing = conn.execute("""
            SELECT id FROM bed_linen_dates 
            WHERE is_active = 1 AND (
                (start_date <= ? AND end_date >= ?) OR
                (start_date <= ? AND end_date >= ?) OR
                (start_date >= ? AND end_date <= ?)
            )
        """, (start_date, start_date, end_date, end_date, start_date, end_date)).fetchone()
        
        if existing:
            return jsonify({
                'success': False,
                'message': 'Период пересекается с существующим активным периодом'
            }), 400

        conn.execute("""
            INSERT INTO bed_linen_dates (start_date, end_date, is_active)
            VALUES (?, ?, 1)
        """, (start_date, end_date))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Период выдачи белья с {start_date} по {end_date} успешно создан.'
        })


@bed_linen_bp.route('/api/bed_linen/list_dates', methods=['GET'])
@require_permission('manage_bed_linen')
def api_list_bed_linen_dates():
    """Получить список всех созданных периодов выдачи белья"""
    if not session.get('admin'):
        return jsonify({'error': 'Необходима авторизация'}), 401
    
    today = datetime.now(MOSCOW_TZ).date()
    
    with get_db() as conn:
        periods = conn.execute("""
            SELECT id, start_date, end_date, created_at, is_active
            FROM bed_linen_dates
            ORDER BY start_date DESC
        """).fetchall()
        
        result = []
        for p in periods:
            try:
                start_date = datetime.strptime(p['start_date'], "%Y-%m-%d").date()
                end_date = datetime.strptime(p['end_date'], "%Y-%m-%d").date()
            except:
                start_date = None
                end_date = None
            
            status = 'Неактивен'
            status_class = 'bg-secondary'
            if p['is_active']:
                if start_date and end_date:
                    if today < start_date:
                        status = 'Запланирован'
                        status_class = 'bg-info'
                    elif today > end_date:
                        status = 'Завершен'
                        status_class = 'bg-dark'
                    else:
                        status = 'Активен'
                        status_class = 'bg-success'
                else:
                    status = 'Активен'
                    status_class = 'bg-success'
            else:
                status = 'Неактивен'
                status_class = 'bg-secondary'
            
            result.append({
                'id': p['id'],
                'start_date': p['start_date'],
                'end_date': p['end_date'],
                'created_at': p['created_at'],
                'is_active': bool(p['is_active']),
                'status': status,
                'status_class': status_class
            })
        
        return jsonify({
            'success': True,
            'dates': result
        })


@bed_linen_bp.route('/api/bed_linen/delete_date/<int:date_id>', methods=['DELETE'])
@require_permission('manage_bed_linen')
def api_delete_bed_linen_date(date_id):
    """Удалить дату выдачи белья"""
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Необходима авторизация'}), 401
    
    with get_db() as conn:
        conn.execute("DELETE FROM bed_linen_dates WHERE id = ?", (date_id,))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Дата успешно удалена'
        })


@bed_linen_bp.route('/bed_linen/token', methods=['GET'])
@require_permission('manage_bed_linen')
def api_bed_linen_token():
    """Генерация токена для QR-кода выдачи белья (только для админов)"""
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, token, created_at FROM bed_linen_tokens ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        should_generate = True
        
        if row:
            created_at_str = row[2]
            try:
                created_at = datetime.fromisoformat(created_at_str.replace(' ', 'T'))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=MOSCOW_TZ)
                else:
                    created_at = created_at.astimezone(MOSCOW_TZ)
                
                delta = datetime.now(MOSCOW_TZ) - created_at
                if delta.total_seconds() < TOKEN_TTL_SECONDS:
                    should_generate = False
                    token = row[1]
            except:
                pass
        
        if should_generate:
            token = secrets.token_urlsafe(16)
            cursor.execute("DELETE FROM bed_linen_tokens")
            cursor.execute(
                "INSERT INTO bed_linen_tokens (token, created_at) VALUES (?, ?)",
                (token, datetime.now(MOSCOW_TZ).isoformat())
            )
            conn.commit()
        
        return jsonify({'token': token})


@bed_linen_bp.route('/bed_linen/qr')
@require_permission('manage_bed_linen')
def generate_qr_bed_linen():
    """Генерация QR-кода для выдачи белья"""
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not QRCODE_AVAILABLE:
        return jsonify({'error': 'QR code library not available'}), 500
    
    data = request.args.get('data', '')
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


@bed_linen_bp.route('/bed_linen/scan')
def bed_linen_scan():
    """Страница сканирования QR-кода для выдачи белья"""
    return render_template('bed_linen_scan.html')


@bed_linen_bp.route('/bed_linen/manage')
@require_permission('manage_bed_linen')
def bed_linen_manage():
    """Страница управления постельным бельем"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    role = get_admin_role(admin_id)
    return render_template('bed_linen_manage.html', admin_role=role)


@bed_linen_bp.route('/bed_linen/report')
@require_permission('manage_bed_linen')
def bed_linen_report():
    """Страница отчетов по выдаче белья"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    # Получаем месяц из параметров запроса
    month_param = request.args.get('month', '')
    if month_param:
        try:
            year, month = map(int, month_param.split('-'))
            start_date = f"{year}-{month:02d}-01"
            # Последний день месяца
            if month == 12:
                end_date = f"{year}-12-31"
            else:
                next_month = datetime(year, month + 1, 1)
                last_day = (next_month - timedelta(days=1)).day
                end_date = f"{year}-{month:02d}-{last_day:02d}"
        except:
            # Если ошибка парсинга, используем текущий месяц
            now = datetime.now(MOSCOW_TZ)
            year, month = now.year, now.month
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year}-12-31"
            else:
                next_month = datetime(year, month + 1, 1)
                last_day = (next_month - timedelta(days=1)).day
                end_date = f"{year}-{month:02d}-{last_day:02d}"
            month_param = f"{year}-{month:02d}"
    else:
        # Если месяц не указан, используем текущий
        now = datetime.now(MOSCOW_TZ)
        year, month = now.year, now.month
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year}-12-31"
        else:
            next_month = datetime(year, month + 1, 1)
            last_day = (next_month - timedelta(days=1)).day
            end_date = f"{year}-{month:02d}-{last_day:02d}"
        month_param = f"{year}-{month:02d}"
    
    with get_db() as conn:
        # Получаем все периоды для выбранного месяца
        periods_rows = conn.execute("""
            SELECT id, start_date, end_date, is_active
            FROM bed_linen_dates
            WHERE (start_date >= ? AND start_date <= ?) 
               OR (end_date >= ? AND end_date <= ?)
               OR (start_date <= ? AND end_date >= ?)
            ORDER BY start_date ASC
        """, (start_date, end_date, start_date, end_date, start_date, end_date)).fetchall()
        
        periods = []
        today_str = datetime.now(MOSCOW_TZ).date().isoformat()
        
        # Ищем последний прошедший период среди ВСЕХ периодов в базе
        # Период считается прошедшим, если его дата окончания строго меньше сегодняшней
        # (период, который заканчивается сегодня, еще не считается прошедшим)
        all_periods_for_last = conn.execute("""
            SELECT id, start_date, end_date, is_active
            FROM bed_linen_dates
            WHERE end_date < ?
            ORDER BY end_date DESC
            LIMIT 1
        """, (today_str,)).fetchone()
        
        last_passed_period = None
        if all_periods_for_last:
            last_passed_period = dict(all_periods_for_last)
            # Убеждаемся, что ID это число (не строка) для правильной работы в шаблоне
            if 'id' in last_passed_period:
                last_passed_period['id'] = int(last_passed_period['id'])
        
        for period_row in periods_rows:
            period_dict = dict(period_row)
            # Определяем статус периода на основе дат и флага is_active
            start_date = period_dict['start_date']
            end_date = period_dict['end_date']
            is_active_flag = period_dict['is_active']
            
            # Период активен, если:
            # 1. is_active = 1
            # 2. Текущая дата находится между start_date и end_date
            is_currently_active = (
                is_active_flag and 
                start_date <= today_str <= end_date
            )
            
            if is_currently_active:
                period_dict['status'] = 'Активен'
                period_dict['status_class'] = 'bg-success'
            elif today_str > end_date:
                period_dict['status'] = 'Завершен'
                period_dict['status_class'] = 'bg-secondary'
            elif today_str < start_date:
                period_dict['status'] = 'Запланирован'
                period_dict['status_class'] = 'bg-info'
            else:
                period_dict['status'] = 'Завершен'
                period_dict['status_class'] = 'bg-secondary'
            
            periods.append(period_dict)
        
        # Получаем все периоды для определения доступных месяцев/лет
        all_periods_rows = conn.execute("""
            SELECT DISTINCT start_date, end_date
            FROM bed_linen_dates
            ORDER BY start_date ASC
        """).fetchall()
        
        # Извлекаем уникальные месяцы и годы из всех периодов
        available_months = set()
        for period_row in all_periods_rows:
            period_dict = dict(period_row)
            start_date_str = period_dict['start_date']
            end_date_str = period_dict['end_date']
            
            # Парсим даты и добавляем все месяцы между start_date и end_date
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
                
                # Добавляем все месяцы в диапазоне
                current = start_dt.replace(day=1)
                while current <= end_dt:
                    month_key = f"{current.year}-{current.month:02d}"
                    available_months.add(month_key)
                    # Переходим к следующему месяцу
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)
            except:
                pass
        
        # Получаем всех студентов
        employees_rows = conn.execute("""
            SELECT id, fio, room_number, building, entrance
            FROM employees
            ORDER BY fio
        """).fetchall()
        
        employees = []
        for emp_row in employees_rows:
            emp_dict = dict(emp_row)
            # Формируем кортеж как ожидает шаблон: (id, fio, room_number, building, entrance)
            employees.append((
                emp_dict['id'],
                emp_dict['fio'] or '',
                emp_dict['room_number'] or '',
                emp_dict['building'] or '',
                emp_dict['entrance'] or ''
            ))
        
        # Получаем информацию о том, кто получил белье в каких периодах
        student_periods = {}
        if periods:
            period_ids = [p['id'] for p in periods]
            placeholders = ','.join(['?'] * len(period_ids))
            scans_rows = conn.execute(f"""
                SELECT employee_id, period_id
                FROM scans
                WHERE period_id IN ({placeholders})
            """, period_ids).fetchall()
            
            for scan_row in scans_rows:
                scan_dict = dict(scan_row)
                emp_id = scan_dict['employee_id']
                period_id = scan_dict['period_id']
                if emp_id not in student_periods:
                    student_periods[emp_id] = []
                student_periods[emp_id].append(period_id)
        
        # Подсчитываем статистику только для последнего прошедшего периода
        total_students = len(employees)
        period_stats = {}
        
        if last_passed_period:
            period_id = last_passed_period['id']
            # Дополнительная проверка: убеждаемся, что период действительно прошедший
            period_end_date = datetime.strptime(last_passed_period['end_date'], '%Y-%m-%d').date()
            today_date = datetime.now(MOSCOW_TZ).date()
            if period_end_date < today_date:  # Период должен быть строго в прошлом
                # Получаем информацию о том, кто получил белье в последнем прошедшем периоде
                scans_for_last_period = conn.execute("""
                    SELECT employee_id
                    FROM scans
                    WHERE period_id = ?
                """, (period_id,)).fetchall()
                
                # Правильно извлекаем employee_id из Row объектов
                received_employee_ids = {dict(row)['employee_id'] for row in scans_for_last_period}
                received_count = len(received_employee_ids)
                not_received_count = total_students - received_count
                percentage = (received_count / total_students * 100) if total_students > 0 else 0
                
                period_stats[period_id] = {
                    'received': received_count,
                    'not_received': not_received_count,
                    'percentage': round(percentage, 1)
                }
            else:
                # Если период еще не прошел, не показываем статистику
                last_passed_period = None
    
    role = get_admin_role(admin_id)
    # Сортируем доступные месяцы
    available_months_list = sorted(list(available_months))
    
    # Если выбранный месяц не в списке доступных, добавляем его
    if month_param and month_param not in available_months_list:
        available_months_list.append(month_param)
        available_months_list = sorted(available_months_list)
    
    return render_template('bed_linen_report.html', 
                         admin_role=role,
                         selected_month=month_param,
                         periods=periods,
                         employees=employees,
                         student_periods=student_periods,
                         available_months=available_months_list,
                         total_students=total_students,
                         period_stats=period_stats,
                         last_passed_period=last_passed_period)


@bed_linen_bp.route('/api/bed_linen/send_reminders', methods=['POST'])
@require_permission('manage_bed_linen')
def api_send_bed_linen_reminders():
    """Отправить сообщения студентам, которые не поменяли белье за выбранный период"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json(silent=True) or {}
    period_id = data.get('period_id')
    
    if not period_id:
        return jsonify({'success': False, 'error': 'Необходимо выбрать период'}), 400
    
    try:
        # Получаем информацию о периоде
        with get_db() as conn:
            period = conn.execute("""
                SELECT id, start_date, end_date
                FROM bed_linen_dates
                WHERE id = ?
            """, (period_id,)).fetchone()
            
            if not period:
                return jsonify({
                    'success': False,
                    'error': 'Период не найден'
                }), 404
            
            period_ids = [period_id]
            
            # Получаем студентов, которые НЕ получили белье ни в одном из периодов
            placeholders = ','.join(['?'] * len(period_ids))
            
            # Получаем всех студентов с Telegram ID (исключаем местных)
            all_students = conn.execute("""
                SELECT DISTINCT e.id, e.fio, tg.tg_user_id
                FROM employees e
                JOIN tg_users tg ON e.id = tg.employee_id
                WHERE tg.tg_user_id IS NOT NULL
                AND COALESCE(e.is_local, 0) = 0
            """).fetchall()
            
            # Получаем студентов, которые получили белье хотя бы в одном периоде
            students_with_linen = conn.execute(f"""
                SELECT DISTINCT employee_id
                FROM scans
                WHERE period_id IN ({placeholders})
            """, period_ids).fetchall()
            
            students_with_linen_ids = {row['employee_id'] for row in students_with_linen}
            
            # Фильтруем студентов, которые НЕ получили белье
            students_without_linen = []
            for student in all_students:
                student_id = student['id']
                if student_id not in students_with_linen_ids:
                    students_without_linen.append({
                        'employee_id': student_id,
                        'fio': student['fio'],
                        'tg_user_id': student['tg_user_id']
                    })
        
            # Получаем информацию о периоде для сообщения
            period_start = period['start_date']
            period_end = period['end_date']
            
            # Форматируем даты для отображения
            if period_start:
                start_parts = period_start.split('-')
                if len(start_parts) >= 3:
                    period_start_formatted = f"{start_parts[2]}.{start_parts[1]}.{start_parts[0]}"
                else:
                    period_start_formatted = period_start
            else:
                period_start_formatted = '—'
            
            if period_end:
                end_parts = period_end.split('-')
                if len(end_parts) >= 3:
                    period_end_formatted = f"{end_parts[2]}.{end_parts[1]}.{end_parts[0]}"
                else:
                    period_end_formatted = period_end
            else:
                period_end_formatted = '—'
        
        if not students_without_linen:
            return jsonify({
                'success': True,
                'sent_count': 0,
                'failed_count': 0,
                'total': 0,
                'message': f'Все студенты получили белье за период {period_start_formatted} - {period_end_formatted}'
            })
        
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
        
        from services.telegram_service import TelegramService
        telegram_service = TelegramService
        
        # Подготавливаем список сообщений для отправки
        messages_to_send = []
        for student in students_without_linen:
            try:
                # Формируем сообщение
                # Получаем имя (второе слово в ФИО, или первое если только одно слово)
                fio_parts = student['fio'].split() if student['fio'] else []
                if len(fio_parts) >= 2:
                    # Если есть несколько слов, берем второе (имя)
                    name = fio_parts[1]
                elif len(fio_parts) == 1:
                    # Если только одно слово, используем его
                    name = fio_parts[0]
                else:
                    name = 'Студент'
                message = f"{name}, добрый день!\n\nПочему вы не поменяли постельное белье?"
                
                # Преобразуем chat_id
                try:
                    chat_id = int(student['tg_user_id'])
                except Exception:
                    chat_id = student['tg_user_id']
                
                messages_to_send.append({
                    'chat_id': chat_id,
                    'message': message,
                    'student': student
                })
            except Exception as e:
                logger.warning(f"Ошибка подготовки сообщения для студента {student.get('fio', 'Unknown')}: {e}", exc_info=True)
        
        sent_count = 0
        failed_count = 0
        failure_reasons = []
        
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
                        'student_info': msg_data['student']['fio']
                    })
                
                # Отправляем через пакетную функцию
                batch_result = send_messages_batch_sync(batch_messages, batch_size=29, delay_between_batches=60)
                sent_count = batch_result['sent']
                failed_count = batch_result['failed']
                failure_reasons = batch_result['errors']
                
                # Для неудачных отправок пробуем через Bot API
                failed_indices = []
                for i, msg_data in enumerate(messages_to_send):
                    # Проверяем, есть ли эта ошибка в списке
                    student_fio = msg_data['student']['fio']
                    chat_id = msg_data['chat_id']
                    found_in_errors = any(f"{student_fio} ({chat_id})" in err for err in failure_reasons)
                    
                    if found_in_errors:
                        # Пробуем отправить через Bot API
                        try:
                            success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                            if success:
                                # Удаляем из ошибок и обновляем счетчики
                                failure_reasons = [err for err in failure_reasons if not f"{student_fio} ({chat_id})" in err]
                                sent_count += 1
                                failed_count -= 1
                        except Exception as fallback_err:
                            logger.warning(f"Ошибка при отправке через Bot API для {student_fio}: {fallback_err}", exc_info=True)
            except Exception as batch_err:
                logger.warning(f"Ошибка при пакетной отправке, переходим на обычную отправку: {batch_err}", exc_info=True)
                # Fallback на обычную отправку
                for msg_data in messages_to_send:
                    try:
                        success = False
                        try:
                            success = send_message_fn(msg_data['chat_id'], msg_data['message'])
                        except ValueError as err:
                            if str(err) == "PEER_ID_INVALID":
                                success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                            else:
                                failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(err)}")
                        except Exception as err:
                            logger.warning(f"Ошибка при отправке через User Bot: {err}", exc_info=True)
                            try:
                                success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                                if not success:
                                    failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): Не удалось отправить")
                            except Exception as fallback_err:
                                failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(fallback_err)}")
                        
                        if success:
                            sent_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка отправки сообщения студенту {msg_data['student']['fio']}: {e}", exc_info=True)
                        failed_count += 1
                        failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(e)}")
        else:
            # Обычная отправка для <= 29 сообщений
            for msg_data in messages_to_send:
                try:
                    success = False
                    try:
                        success = send_message_fn(msg_data['chat_id'], msg_data['message'])
                    except ValueError as err:
                        if str(err) == "PEER_ID_INVALID":
                            # Пробуем через Bot API
                            print(f"PEER_ID_INVALID для пользователя {msg_data['chat_id']}, отправляем через Bot API")
                            success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                        else:
                            failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(err)}")
                    except Exception as err:
                        print(f"Непредвиденная ошибка при отправке через User Bot: {err}")
                        failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(err)}")
                        # В случае любой другой ошибки User Bot, пробуем отправить через Bot API
                        try:
                            success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                            if not success:
                                failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): Не удалось отправить через Bot API после ошибки User Bot")
                        except Exception as fallback_err:
                            logger.warning(f"Ошибка при отправке через Bot API после ошибки User Bot: {fallback_err}", exc_info=True)
                            failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(fallback_err)}")
                    
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения студенту {msg_data['student']['fio']} (ID: {msg_data['chat_id']}): {e}", exc_info=True)
                    failed_count += 1
                    failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(e)}")
        
        response_data = {
            'success': True,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total': len(students_without_linen),
            'errors': failure_reasons
        }
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Ошибка в api_send_bed_linen_reminders: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'}), 500


@bed_linen_bp.route('/bed_linen/verify', methods=['POST'])
def api_bed_linen_verify():
    """Верификация токена при сканировании QR-кода"""
    data = request.get_json(force=True)
    employee_id = data.get('employee_id')
    token = data.get('token')
    
    if not employee_id or not token:
        return jsonify({'status': 'error', 'message': 'Неверные данные.'}), 400
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bed_linen_tokens WHERE token=?", (token,))
        t = cursor.fetchone()
        if not t:
            return jsonify({'status': 'error', 'message': 'Код недействителен.'}), 403
        
        # Проверяем, не использован ли уже токен для этого студента
        cursor.execute("SELECT id FROM scans WHERE employee_id=? AND token=?", (employee_id, token))
        existing_scan = cursor.fetchone()
        if existing_scan:
            return jsonify({'status': 'error', 'message': 'Код уже использован.'}), 403
        
        # Получаем активный период
        cursor.execute("SELECT id FROM bed_linen_dates WHERE is_active=1 ORDER BY start_date DESC LIMIT 1")
        period = cursor.fetchone()
        if not period:
            return jsonify({'status': 'error', 'message': 'Нет активного периода выдачи белья.'}), 400
        
        period_id = period[0]
        
        # Регистрируем получение белья
        cursor.execute("""
            INSERT INTO scans (employee_id, token, scanned_at, period_id)
            VALUES (?, ?, ?, ?)
        """, (employee_id, token, datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S'), period_id))
        conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Белье успешно получено.'
        })


@bed_linen_bp.route('/admin/send_messages')
@require_permission('manage_send_messages')
def admin_send_messages():
    """Страница для отправки сообщений студентам"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    
    # Получаем список периодов для выбора
    with get_db() as conn:
        periods = conn.execute("""
            SELECT id, start_date, end_date
            FROM bed_linen_dates
            ORDER BY start_date DESC
            LIMIT 20
        """).fetchall()
        
        # Получаем список шаблонов
        templates = conn.execute("""
            SELECT id, name, message_text, created_at, updated_at
            FROM message_templates
            ORDER BY updated_at DESC
        """).fetchall()
    
    role = get_admin_role(admin_id)
    return render_template('admin_send_messages.html', 
                         admin_role=role,
                         periods=periods,
                         templates=templates)


@bed_linen_bp.route('/api/bed_linen/send_custom_messages', methods=['POST'])
@require_permission('manage_send_messages')
def api_send_custom_messages():
    """Отправить кастомные сообщения студентам"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json(silent=True) or {}
    message_text = data.get('message', '').strip()
    recipient_type = data.get('recipient_type', '')  # 'period', 'all', 'custom'
    period_id = data.get('period_id')
    custom_student_ids = data.get('student_ids', [])
    
    if not message_text:
        return jsonify({'success': False, 'error': 'Текст сообщения не может быть пустым'}), 400
    
    try:
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
        
        from services.telegram_service import TelegramService
        telegram_service = TelegramService
        
        # Определяем получателей
        students_to_send = []
        
        with get_db() as conn:
            if recipient_type == 'period' and period_id:
                # Студенты, которые не получили белье за период
                students_with_linen = conn.execute("""
                    SELECT DISTINCT employee_id
                    FROM scans
                    WHERE period_id = ?
                """, (period_id,)).fetchall()
                students_with_linen_ids = {row['employee_id'] for row in students_with_linen}
                
                all_students = conn.execute("""
                    SELECT DISTINCT e.id, e.fio, tg.tg_user_id
                    FROM employees e
                    JOIN tg_users tg ON e.id = tg.employee_id
                    WHERE tg.tg_user_id IS NOT NULL
                    AND COALESCE(e.is_local, 0) = 0
                """).fetchall()
                
                for student in all_students:
                    if student['id'] not in students_with_linen_ids:
                        students_to_send.append({
                            'employee_id': student['id'],
                            'fio': student['fio'],
                            'tg_user_id': student['tg_user_id']
                        })
            elif recipient_type == 'all':
                # Все студенты с Telegram
                all_students = conn.execute("""
                    SELECT DISTINCT e.id, e.fio, tg.tg_user_id
                    FROM employees e
                    JOIN tg_users tg ON e.id = tg.employee_id
                    WHERE tg.tg_user_id IS NOT NULL
                    AND COALESCE(e.is_local, 0) = 0
                """).fetchall()
                
                for student in all_students:
                    students_to_send.append({
                        'employee_id': student['id'],
                        'fio': student['fio'],
                        'tg_user_id': student['tg_user_id']
                    })
            elif recipient_type == 'custom' and custom_student_ids:
                # Кастомный список студентов
                placeholders = ','.join(['?'] * len(custom_student_ids))
                students = conn.execute(f"""
                    SELECT DISTINCT e.id, e.fio, tg.tg_user_id
                    FROM employees e
                    JOIN tg_users tg ON e.id = tg.employee_id
                    WHERE tg.tg_user_id IS NOT NULL 
                    AND COALESCE(e.is_local, 0) = 0
                    AND e.id IN ({placeholders})
                """, custom_student_ids).fetchall()
                
                for student in students:
                    students_to_send.append({
                        'employee_id': student['id'],
                        'fio': student['fio'],
                        'tg_user_id': student['tg_user_id']
                    })
            else:
                return jsonify({'success': False, 'error': 'Неверный тип получателей'}), 400
        
        if not students_to_send:
            return jsonify({
                'success': False,
                'error': 'Не найдено студентов для отправки'
            }), 400
        
        # Подготавливаем список сообщений для отправки
        messages_to_send = []
        for student in students_to_send:
            try:
                # Формируем сообщение с подстановкой имени
                fio_parts = student['fio'].split() if student['fio'] else []
                if len(fio_parts) >= 2:
                    name = fio_parts[1]
                elif len(fio_parts) == 1:
                    name = fio_parts[0]
                else:
                    name = 'Студент'
                
                # Заменяем {name} на имя студента, если есть такой плейсхолдер
                personalized_message = message_text.replace('{name}', name)
                
                # Преобразуем chat_id
                try:
                    chat_id = int(student['tg_user_id'])
                except Exception:
                    chat_id = student['tg_user_id']
                
                messages_to_send.append({
                    'chat_id': chat_id,
                    'message': personalized_message,
                    'student': student
                })
            except Exception as e:
                logger.warning(f"Ошибка подготовки сообщения для студента {student.get('fio', 'Unknown')}: {e}", exc_info=True)
        
        sent_count = 0
        failed_count = 0
        failure_reasons = []
        
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
                        'student_info': msg_data['student']['fio']
                    })
                
                # Отправляем через пакетную функцию
                batch_result = send_messages_batch_sync(batch_messages, batch_size=29, delay_between_batches=60)
                sent_count = batch_result['sent']
                failed_count = batch_result['failed']
                failure_reasons = batch_result['errors']
                
                # Для неудачных отправок пробуем через Bot API
                for msg_data in messages_to_send:
                    student_fio = msg_data['student']['fio']
                    chat_id = msg_data['chat_id']
                    found_in_errors = any(f"{student_fio} ({chat_id})" in err for err in failure_reasons)
                    
                    if found_in_errors:
                        # Пробуем отправить через Bot API
                        try:
                            success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                            if success:
                                # Удаляем из ошибок и обновляем счетчики
                                failure_reasons = [err for err in failure_reasons if not f"{student_fio} ({chat_id})" in err]
                                sent_count += 1
                                failed_count -= 1
                        except Exception as fallback_err:
                            logger.warning(f"Ошибка при отправке через Bot API для {student_fio}: {fallback_err}", exc_info=True)
            except Exception as batch_err:
                logger.warning(f"Ошибка при пакетной отправке, переходим на обычную отправку: {batch_err}", exc_info=True)
                # Fallback на обычную отправку
                for msg_data in messages_to_send:
                    try:
                        success = False
                        try:
                            success = send_message_fn(msg_data['chat_id'], msg_data['message'])
                        except ValueError as err:
                            if str(err) == "PEER_ID_INVALID":
                                success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                            else:
                                failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(err)}")
                        except Exception as err:
                            logger.warning(f"Ошибка при отправке через User Bot: {err}", exc_info=True)
                            try:
                                success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                                if not success:
                                    failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): Не удалось отправить")
                            except Exception as fallback_err:
                                failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(fallback_err)}")
                        
                        if success:
                            sent_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка отправки сообщения студенту {msg_data['student']['fio']}: {e}", exc_info=True)
                        failed_count += 1
                        failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(e)}")
        else:
            # Обычная отправка для <= 29 сообщений
            for msg_data in messages_to_send:
                try:
                    success = False
                    try:
                        success = send_message_fn(msg_data['chat_id'], msg_data['message'])
                    except ValueError as err:
                        if str(err) == "PEER_ID_INVALID":
                            # Пробуем через Bot API
                            print(f"PEER_ID_INVALID для пользователя {msg_data['chat_id']}, отправляем через Bot API")
                            success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                        else:
                            failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(err)}")
                    except Exception as err:
                        print(f"Непредвиденная ошибка при отправке через User Bot: {err}")
                        failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(err)}")
                        # В случае любой другой ошибки User Bot, пробуем отправить через Bot API
                        try:
                            success = telegram_service.send_notification(msg_data['chat_id'], msg_data['message'])
                            if not success:
                                failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): Не удалось отправить через Bot API после ошибки User Bot")
                        except Exception as fallback_err:
                            logger.warning(f"Ошибка при отправке через Bot API после ошибки User Bot: {fallback_err}", exc_info=True)
                            failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(fallback_err)}")
                    
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения студенту {msg_data['student']['fio']} (ID: {msg_data['chat_id']}): {e}", exc_info=True)
                    failed_count += 1
                    failure_reasons.append(f"{msg_data['student']['fio']} ({msg_data['chat_id']}): {str(e)}")
        
        response_data = {
            'success': True,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total': len(students_to_send),
            'errors': failure_reasons
        }
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Ошибка в api_send_custom_messages: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bed_linen_tokens WHERE token=?", (token,))
        t = cursor.fetchone()
        if not t:
            return jsonify({'status': 'error', 'message': 'Код недействителен.'}), 403
        
        now = datetime.now(MOSCOW_TZ)
        today_str = now.date().isoformat()
        
        period = cursor.execute("""
            SELECT id FROM bed_linen_dates
            WHERE is_active = 1 AND start_date <= ? AND end_date >= ?
            ORDER BY start_date DESC
            LIMIT 1
        """, (today_str, today_str)).fetchone()
        
        if not period:
            return jsonify({
                'status': 'error',
                'message': 'Нет активного периода выдачи белья на сегодня.'
            }), 403
        
        period_id = period['id']
        
        student = cursor.execute("""
            SELECT fio FROM employees 
            WHERE id = ?
        """, (employee_id,)).fetchone()
        
        student_fio = student['fio'] if student else 'Студент'
        
        # Проверяем, не получал ли уже студент белье в этом периоде
        existing = cursor.execute("""
            SELECT id FROM scans 
            WHERE employee_id = ? AND period_id = ?
        """, (employee_id, period_id)).fetchone()
        
        if existing:
            return jsonify({
                'status': 'error',
                'message': f'{student_fio} уже получил(а) белье в этом периоде.'
            }), 403
        
        # Записываем факт получения белья
        scanned_at = now.isoformat()
        cursor.execute("""
            INSERT INTO scans (employee_id, period_id, scanned_at)
            VALUES (?, ?, ?)
        """, (employee_id, period_id, scanned_at))
        conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'{student_fio} успешно получил(а) белье.',
            'student_fio': student_fio
        })


@bed_linen_bp.route('/bed_linen/verify_qr', methods=['POST'])
def api_bed_linen_verify_qr():
    """Верификация QR-кода при сканировании"""
    try:
        data = request.get_json(silent=True) or {}
        # Поддерживаем оба варианта: qr_code и qr_data
        qr_data = data.get('qr_code', '') or data.get('qr_data', '')
        if isinstance(qr_data, str):
            qr_data = qr_data.strip()
        else:
            qr_data = str(qr_data).strip() if qr_data else ''
        
        if not qr_data:
            return jsonify({'status': 'error', 'message': 'QR-код не предоставлен.'}), 400
        
        # Парсим QR-код: формат должен быть токен
        token = qr_data
        employee_id = data.get('employee_id')
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Сначала проверяем таблицу bed_linen_qr_codes (QR-коды от Telegram бота)
            qr_code_row = cursor.execute("""
                SELECT qr_code, employee_id, tg_user_id, created_at, expires_at, used
                FROM bed_linen_qr_codes 
                WHERE qr_code = ?
            """, (token,)).fetchone()
            
            if qr_code_row:
                # Это QR-код от бота
                qr_employee_id = qr_code_row['employee_id']
                qr_tg_user_id = qr_code_row['tg_user_id']
                expires_at_str = qr_code_row['expires_at']
                is_used = bool(qr_code_row['used'])
                
                # Проверяем, использован ли уже
                if is_used:
                    return jsonify({'status': 'error', 'message': 'Этот QR-код уже использован.'}), 403
                
                # Проверяем срок действия
                try:
                    expires_at = datetime.fromisoformat(expires_at_str.replace(' ', 'T'))
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=MOSCOW_TZ)
                    else:
                        expires_at = expires_at.astimezone(MOSCOW_TZ)
                    
                    if datetime.now(MOSCOW_TZ) > expires_at:
                        return jsonify({'status': 'error', 'message': 'QR-код истек.'}), 403
                except:
                    pass
                
                # Если передан employee_id, проверяем, что он совпадает
                if employee_id and int(employee_id) != qr_employee_id:
                    return jsonify({'status': 'error', 'message': 'QR-код принадлежит другому студенту.'}), 403
                
                # Используем employee_id из QR-кода
                employee_id = qr_employee_id
                
                # Получаем активный период
                cursor.execute("SELECT id FROM bed_linen_dates WHERE is_active=1 ORDER BY start_date DESC LIMIT 1")
                period = cursor.fetchone()
                if not period:
                    return jsonify({'status': 'error', 'message': 'Нет активного периода выдачи белья.'}), 400
                
                period_id = period[0]
                
                # Проверяем, не получил ли уже студент белье за этот период
                cursor.execute("SELECT id FROM scans WHERE employee_id=? AND period_id=?", (employee_id, period_id))
                existing_scan = cursor.fetchone()
                if existing_scan:
                    return jsonify({'status': 'error', 'message': 'Студент уже получил белье за этот период.'}), 403
                
                # Регистрируем получение белья
                cursor.execute("""
                    INSERT INTO scans (employee_id, token, scanned_at, period_id)
                    VALUES (?, ?, ?, ?)
                """, (employee_id, token, datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S'), period_id))
                
                # Помечаем QR-код как использованный
                cursor.execute("UPDATE bed_linen_qr_codes SET used = 1 WHERE qr_code = ?", (token,))
                
                # Получаем информацию о студенте
                student = conn.execute("SELECT fio FROM employees WHERE id=?", (employee_id,)).fetchone()
                conn.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': 'Белье успешно получено.',
                    'token': token,
                    'student': {'fio': student['fio'] if student else '', 'id': employee_id}
                })
            
            # Если не найден в bed_linen_qr_codes, проверяем bed_linen_tokens (старая система)
            token_row = cursor.execute("SELECT id FROM bed_linen_tokens WHERE token=?", (token,)).fetchone()
            if not token_row:
                return jsonify({'status': 'error', 'message': 'QR-код недействителен.'}), 403
            
            # Проверяем срок действия токена
            created_at_row = cursor.execute("SELECT created_at FROM bed_linen_tokens WHERE token=?", (token,)).fetchone()
            if created_at_row:
                try:
                    created_at = datetime.fromisoformat(created_at_row[0].replace(' ', 'T'))
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=MOSCOW_TZ)
                    else:
                        created_at = created_at.astimezone(MOSCOW_TZ)
                    
                    delta = datetime.now(MOSCOW_TZ) - created_at
                    if delta.total_seconds() > TOKEN_TTL_SECONDS:
                        return jsonify({'status': 'error', 'message': 'Код истек.'}), 403
                except:
                    pass
            
            # Если передан employee_id, сразу регистрируем получение белья
            if employee_id:
                # Получаем активный период
                cursor.execute("SELECT id FROM bed_linen_dates WHERE is_active=1 ORDER BY start_date DESC LIMIT 1")
                period = cursor.fetchone()
                if not period:
                    return jsonify({'status': 'error', 'message': 'Нет активного периода выдачи белья.'}), 400
                
                period_id = period[0]
                
                # Проверяем, не использован ли уже токен для этого студента
                cursor.execute("SELECT id FROM scans WHERE employee_id=? AND token=?", (employee_id, token))
                existing_scan = cursor.fetchone()
                if existing_scan:
                    return jsonify({'status': 'error', 'message': 'Код уже использован для этого студента.'}), 403
                
                # Регистрируем получение белья
                cursor.execute("""
                    INSERT INTO scans (employee_id, token, scanned_at, period_id)
                    VALUES (?, ?, ?, ?)
                """, (employee_id, token, datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S'), period_id))
                
                # Получаем информацию о студенте
                student = conn.execute("SELECT fio FROM employees WHERE id=?", (employee_id,)).fetchone()
                conn.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': 'Белье успешно получено.',
                    'token': token,
                    'student': {'fio': student['fio'] if student else ''}
                })
        
        return jsonify({
            'status': 'success',
            'message': 'Код действителен. Введите ID студента для получения белья.',
            'token': token
        })
    except Exception as e:
        logger.error(f"Ошибка в api_bed_linen_verify_qr: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Ошибка сервера: {str(e)}'}), 500


@bed_linen_bp.route('/api/message_templates', methods=['GET'])
@require_permission('manage_bed_linen')
def api_get_message_templates():
    """Получить список шаблонов сообщений"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db() as conn:
            templates = conn.execute("""
                SELECT id, name, message_text, created_at, updated_at
                FROM message_templates
                ORDER BY updated_at DESC
            """).fetchall()
            
            result = []
            for template in templates:
                result.append({
                    'id': template['id'],
                    'name': template['name'],
                    'message_text': template['message_text'],
                    'created_at': template['created_at'],
                    'updated_at': template['updated_at']
                })
            
            return jsonify({'success': True, 'templates': result})
    except Exception as e:
        logger.error(f"Ошибка в api_get_message_templates: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bed_linen_bp.route('/api/message_templates', methods=['POST'])
@require_permission('manage_bed_linen')
def api_create_message_template():
    """Создать шаблон сообщения"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    message_text = data.get('message_text', '').strip()
    
    if not name or not message_text:
        return jsonify({'success': False, 'error': 'Название и текст шаблона обязательны'}), 400
    
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO message_templates (name, message_text, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (name, message_text, admin_id, 
                  datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Шаблон успешно создан'})
    except Exception as e:
        logger.error(f"Ошибка в api_create_message_template: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bed_linen_bp.route('/api/message_templates/<int:template_id>', methods=['PUT'])
@require_permission('manage_bed_linen')
def api_update_message_template(template_id):
    """Обновить шаблон сообщения"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    message_text = data.get('message_text', '').strip()
    
    if not name or not message_text:
        return jsonify({'success': False, 'error': 'Название и текст шаблона обязательны'}), 400
    
    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE message_templates
                SET name = ?, message_text = ?, updated_at = ?
                WHERE id = ?
            """, (name, message_text, 
                  datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                  template_id))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Шаблон успешно обновлен'})
    except Exception as e:
        logger.error(f"Ошибка в api_update_message_template: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bed_linen_bp.route('/api/message_templates/<int:template_id>', methods=['DELETE'])
@require_permission('manage_bed_linen')
def api_delete_message_template(template_id):
    """Удалить шаблон сообщения"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM message_templates WHERE id = ?", (template_id,))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Шаблон успешно удален'})
    except Exception as e:
        logger.error(f"Ошибка в api_delete_message_template: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

