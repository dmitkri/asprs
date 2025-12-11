from flask import Blueprint, request, jsonify, session, send_file
from database import get_db
from utils.auth import require_permission, get_admin_role
from utils.rounds import is_minor
from datetime import datetime, date
import pandas as pd
import io
from config import FIXED_COLS

export_bp = Blueprint('export', __name__)

# Маппинг столбцов базы данных на названия для экспорта
COLUMN_MAPPING = {
    'id': 'ID',
    'fio': 'ФИО',
    'phone': 'Телефон',
    'group_name': 'Группа',
    'birth_date': 'Дата рождения',
    'building': 'Корпус',
    'entrance': 'Подъезд',
    'room_number': 'Комната',
    'notes': 'Примечания',
    'absences': 'Отсутствия',
    'reprimands': 'Замечания',
    'vacation': 'Отпуск',
    'tg_username': 'Telegram username'
}


@export_bp.route('/api/admin/export/buildings_entrances', methods=['GET'])
@require_permission('view')
def api_get_buildings_entrances():
    """Получить список зданий и подъездов"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        # Получаем уникальные комбинации building и entrance
        buildings_entrances = conn.execute('''
            SELECT DISTINCT building, entrance
            FROM employees
            WHERE building IS NOT NULL AND building != ''
            AND entrance IS NOT NULL AND entrance != ''
            ORDER BY building, entrance
        ''').fetchall()
        
        result = {}
        for row in buildings_entrances:
            building = row['building']
            entrance = row['entrance']
            if building not in result:
                result[building] = []
            if entrance not in result[building]:
                result[building].append(entrance)
        
        return jsonify({
            'success': True,
            'buildings_entrances': result
        })


@export_bp.route('/api/admin/export/groups', methods=['GET'])
@require_permission('view')
def api_get_groups():
    """Получить список всех групп"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        groups = conn.execute('''
            SELECT DISTINCT group_name
            FROM employees
            WHERE group_name IS NOT NULL AND group_name != ''
            ORDER BY group_name
        ''').fetchall()
        
        result = [row['group_name'] for row in groups]
        
        return jsonify({
            'success': True,
            'groups': result
        })


@export_bp.route('/api/admin/export/columns', methods=['GET'])
@require_permission('view')
def api_get_export_columns():
    """Получить список доступных столбцов для экспорта"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Базовые столбцы
    columns = []
    for db_col, display_name in COLUMN_MAPPING.items():
        columns.append({
            'key': db_col,
            'label': display_name,
            'default': True
        })
    
    # Добавляем "Комната (полная)" как отдельный столбец
    columns.append({
        'key': 'room_full',
        'label': 'Комната (полная)',
        'default': True
    })
    
    # Получаем кастомные столбцы
    with get_db() as conn:
        custom_columns = conn.execute('''
            SELECT name, col_type FROM custom_columns ORDER BY id
        ''').fetchall()
        
        for col in custom_columns:
            columns.append({
                'key': f"extra_data_{col['name']}",
                'label': col['name'],
                'default': False
            })
    
    return jsonify({
        'success': True,
        'columns': columns
    })


@export_bp.route('/api/admin/export/export', methods=['POST'])
@require_permission('view')
def api_export_data():
    """Экспорт данных в Excel"""
    try:
        admin_id = session.get('admin_id')
        if not admin_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных в запросе'}), 400
        
        export_type = data.get('export_type')  # 'entrance', 'group', 'adults', 'minors'
        if not export_type:
            return jsonify({'error': 'Не указан тип экспорта'}), 400
        
        building = data.get('building', '').strip()
        entrance = data.get('entrance', '').strip()
        group_name = data.get('group_name', '').strip()
        selected_columns = data.get('columns', [])  # Список выбранных столбцов
        
        with get_db() as conn:
            query = '''
                SELECT 
                    id, fio, phone, group_name, birth_date,
                    building, entrance, room_number, notes,
                    absences, reprimands, vacation, tg_username, extra_data
                FROM employees
                WHERE 1=1
            '''
            params = []
            
            if export_type == 'entrance':
                if not building or not entrance:
                    return jsonify({'error': 'Необходимо указать здание и подъезд'}), 400
                query += ' AND building = ? AND entrance = ?'
                params.extend([building, entrance])
            elif export_type == 'group':
                if not group_name:
                    return jsonify({'error': 'Необходимо указать группу'}), 400
                query += ' AND group_name = ?'
                params.append(group_name)
            elif export_type == 'adults':
                query += ' AND birth_date IS NOT NULL AND birth_date != ""'
            elif export_type == 'minors':
                query += ' AND birth_date IS NOT NULL AND birth_date != ""'
            
            query += ' ORDER BY fio'
            
            students = conn.execute(query, params).fetchall()
            
            # Фильтруем по возрасту для adults/minors
            if export_type in ['adults', 'minors']:
                filtered_students = []
                for student in students:
                    birth_date_str = student['birth_date'] if 'birth_date' in student.keys() else None
                    if birth_date_str:
                        try:
                            is_student_minor = is_minor(birth_date_str)
                            if export_type == 'adults' and not is_student_minor:
                                filtered_students.append(student)
                            elif export_type == 'minors' and is_student_minor:
                                filtered_students.append(student)
                        except (ValueError, TypeError, AttributeError) as e:
                            # Пропускаем студентов с некорректной датой рождения
                            student_id = student['id'] if 'id' in student.keys() else 'unknown'
                            print(f"Skipping student {student_id} due to birth_date error: {e}")
                            continue
                students = filtered_students
            
            # Если столбцы не выбраны, используем все по умолчанию (только те, что помечены default: true)
            if not selected_columns:
                # Получаем столбцы по умолчанию из API
                default_columns = []
                for db_col in COLUMN_MAPPING.keys():
                    default_columns.append(db_col)
                default_columns.append('room_full')
                selected_columns = default_columns
            
            # Формируем данные для Excel
            excel_data = []
            for student in students:
                row = {}
                
                # Обрабатываем выбранные столбцы
                for col_key in selected_columns:
                    if col_key == 'room_full':
                        row['Комната (полная)'] = (
                            f"{student['building'] or ''}-{student['entrance'] or ''}-{student['room_number'] or ''}" 
                            if student['building'] else '-'
                        )
                    elif col_key.startswith('extra_data_'):
                        # Кастомный столбец из extra_data
                        import json
                        extra_data_str = student['extra_data'] if 'extra_data' in student.keys() else '{}'
                        extra_data_str = extra_data_str or '{}'
                        try:
                            extra_data = json.loads(extra_data_str) if isinstance(extra_data_str, str) else extra_data_str
                        except:
                            extra_data = {}
                        custom_col_name = col_key.replace('extra_data_', '')
                        row[custom_col_name] = extra_data.get(custom_col_name, '-')
                    elif col_key in COLUMN_MAPPING:
                        db_value = student[col_key] if col_key in student.keys() else ''
                        # Форматируем дату рождения в формат дд.мм.гггг
                        if col_key == 'birth_date' and db_value:
                            try:
                                # Парсим дату из формата гггг-мм-дд
                                date_obj = datetime.strptime(db_value, '%Y-%m-%d')
                                # Форматируем в дд.мм.гггг
                                db_value = date_obj.strftime('%d.%m.%Y')
                            except (ValueError, TypeError):
                                # Если не удалось распарсить, оставляем как есть
                                pass
                        row[COLUMN_MAPPING[col_key]] = db_value if db_value else '-'
                
                excel_data.append(row)
            
            if not excel_data:
                return jsonify({'error': 'Нет данных для экспорта'}), 400
            
            df = pd.DataFrame(excel_data)
            
            buf = io.BytesIO()
            df.to_excel(buf, index=False, engine='openpyxl')
            buf.seek(0)
            
            # Формируем имя файла
            today = datetime.now().strftime("%Y%m%d_%H%M%S")
            if export_type == 'entrance':
                filename = f'export_entrance_{building}_{entrance}_{today}.xlsx'
            elif export_type == 'group':
                filename = f'export_group_{group_name}_{today}.xlsx'
            elif export_type == 'adults':
                filename = f'export_adults_{today}.xlsx'
            elif export_type == 'minors':
                filename = f'export_minors_{today}.xlsx'
            else:
                filename = f'export_{today}.xlsx'
            
            from flask import Response
            from urllib.parse import quote
            
            # Правильно кодируем имя файла для заголовка Content-Disposition
            # Используем RFC 2231 формат для поддержки кириллицы
            encoded_filename = quote(filename.encode('utf-8'))
            content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
            
            response = Response(
                buf.getvalue(),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={
                    'Content-Disposition': content_disposition
                }
            )
            return response
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"Export error: {error_msg}")
        print(traceback_str)
        return jsonify({'error': f'Ошибка при экспорте: {error_msg}'}), 500

