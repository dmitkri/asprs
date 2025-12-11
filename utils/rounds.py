from datetime import datetime, date
from database import get_db
from config import MOSCOW_TZ
from utils.validators import parse_birth_date

def is_minor(birth_date_str):
    birth_date = None
    if isinstance(birth_date_str, str):
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age < 18

def get_minors_by_entrance(building=None, entrance=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        columns = [col[1] for col in cursor.fetchall()]
        has_is_minor = 'is_minor' in columns
        query = '''
            SELECT id, fio, birth_date, building, entrance, room_number, vacation
        '''
        if has_is_minor:
            query += ', is_minor'
        query += '''
            FROM employees
            WHERE birth_date IS NOT NULL AND birth_date != ''
        '''
        params = []
        if building:
            query += ' AND building = ?'
            params.append(building)
        if entrance:
            query += ' AND entrance = ?'
            params.append(entrance)
        query += ' ORDER BY COALESCE(building, ""), COALESCE(entrance, ""), COALESCE(room_number, ""), fio'
        rows = conn.execute(query, params).fetchall()
        result = {}
        for row in rows:
            bld = row['building'] or 'Не указан'
            ent = row['entrance'] or 'Не указан'
            if bld not in result:
                result[bld] = {}
            if ent not in result[bld]:
                result[bld][ent] = []
            result[bld][ent].append({
                'id': row['id'],
                'fio': row['fio'],
                'birth_date': row['birth_date'],
                'room_number': row['room_number'] or 'Не указана',
                'vacation': row['vacation'] or ''
            })
        return result

def get_minors_for_round(building, entrance):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        columns = [col[1] for col in cursor.fetchall()]
        has_is_minor = 'is_minor' in columns
        query = '''
            SELECT id, fio, birth_date, room_number, vacation
        '''
        if has_is_minor:
            query += ', is_minor'
        query += '''
            FROM employees
            WHERE building = ? AND entrance = ?
            AND room_number IS NOT NULL AND room_number != ''
            ORDER BY CAST(room_number AS INTEGER), fio
        '''
        rows = conn.execute(query, (building, entrance)).fetchall()
        minors = []
        for row in rows:
            minors.append({
                'id': row['id'],
                'fio': row['fio'],
                'room_number': row['room_number'],
                'vacation': row['vacation'] or ''
            })
        return minors

def can_do_rounds(employee_id):
    with get_db() as conn:
        row = conn.execute(
            'SELECT can_do_rounds FROM employees WHERE id = ?',
            (employee_id,)
        ).fetchone()
        return row['can_do_rounds'] == 1

def is_round_time():
    now = datetime.now(MOSCOW_TZ)
    return now.hour >= 22

