from datetime import datetime
from config import MOSCOW_TZ

def parse_vacation_end(vacation_str):
    end_part = vacation_str.split('-', 1)[1].strip()
    parts = end_part.split()
    time_str = parts[0]
    date_str = parts[1]
    date_obj = datetime.strptime(date_str, '%d.%m.%Y')
    time_parts = time_str.split(':')
    hour = int(time_parts[0])
    minute = int(time_parts[1])
    date_obj = date_obj.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return date_obj

def clean_expired_vacations():
    today = datetime.now(MOSCOW_TZ)
    from database import get_db
    import json
    with get_db() as conn:
        rows = conn.execute('SELECT id, vacation, vacation_history FROM employees WHERE vacation != ""').fetchall()
        for row in rows:
            try:
                end_date = parse_vacation_end(row['vacation'])
                # Перемещаем в историю только если дата окончания прошла
                # Сравниваем datetime объекты
                if end_date and today > end_date:
                    history = json.loads(row['vacation_history'] or '[]')
                    history.append(row['vacation'])
                    conn.execute('UPDATE employees SET vacation = ?, vacation_history = ? WHERE id = ?', 
                               ("", json.dumps(history), row['id']))
            except (ValueError, AttributeError, IndexError, TypeError) as e:
                # Если не удалось распарсить дату, пропускаем это заявление
                continue
        conn.commit()

def parse_birth_date(date_value):
    import pandas as pd
    if isinstance(date_value, datetime):
        return date_value.strftime('%Y-%m-%d')
    if isinstance(date_value, pd.Timestamp):
        return date_value.strftime('%Y-%m-%d')
    date_str = str(date_value).strip()
    dt = datetime.strptime(date_str, '%d.%m.%Y')
    return dt.strftime('%Y-%m-%d')

def normalize_header(header):
    header = str(header).lower().strip()
    mapping = {
        'ф и о': 'fio', 'фамилия': 'fio', 'имя': 'fio', 'отчество': 'fio', 'фио': 'fio',
        'телефон': 'phone', 'номер': 'phone', 'номер телефона': 'phone',
        'группа': 'group_name', 'отдел': 'group_name',
        'дата рождения': 'birth_date', 'др': 'birth_date', 'рождение': 'birth_date',
        'примечания': 'notes', 'комментарии': 'notes',
        'прогулы': 'absences', 'пропуски': 'absences', 'акты': 'absences',
        'выговоры': 'reprimands', 'замечания': 'reprimands',
        'заявление': 'vacation', 'отпуск': 'vacation', 'командировка': 'vacation',
        'история заявлений': 'vacation_history',
    }
    return mapping.get(header, header.replace(' ', '_'))

