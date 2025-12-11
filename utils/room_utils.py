from database import get_db

def load_rooms_structure():
    structure = {}
    
    with get_db() as conn:
        rooms = conn.execute('''
            SELECT building, entrance, floor, room_number 
            FROM rooms 
            WHERE building IS NOT NULL AND entrance IS NOT NULL AND room_number IS NOT NULL
            ORDER BY building, entrance, floor, room_number
        ''').fetchall()
        
        for room in rooms:
            building = str(room['building']).strip()
            entrance = str(room['entrance']).strip()
            floor = room['floor']
            room_number = str(room['room_number']).strip()
            
            entrance_key = f"entrance_{entrance}" if not entrance.startswith('entrance_') else entrance
            floor_key = f"floor_{floor}" if floor is not None else "floor_unknown"
            
            if building not in structure:
                structure[building] = {}
            if entrance_key not in structure[building]:
                structure[building][entrance_key] = {}
            if floor_key not in structure[building][entrance_key]:
                structure[building][entrance_key][floor_key] = []
            
            if room_number not in structure[building][entrance_key][floor_key]:
                structure[building][entrance_key][floor_key].append(room_number)
    
    return structure


def delete_all_rooms():
    with get_db() as conn:
        cursor = conn.execute('DELETE FROM rooms')
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count


def get_entrance_by_number(building, number):
    building = str(building).strip()
    number = str(number).strip()
    
    if number.startswith('00'):
        number_normalized = number.lstrip('0')
        if not number_normalized:
            number_normalized = number
    else:
        number_normalized = number
    
    with get_db() as conn:
        room = conn.execute('''
            SELECT entrance FROM rooms 
            WHERE building = ? AND (room_number = ? OR room_number = ?)
            LIMIT 1
        ''', (building, number, number_normalized)).fetchone()
        
        return str(room['entrance'])
    
    return ""


def get_room_max_occupants(building, entrance, room_number):
    with get_db() as conn:
        room = conn.execute('''
            SELECT COALESCE(rc.max_occupants, 1) as max_occupants
            FROM rooms r
            LEFT JOIN room_categories rc ON r.category_id = rc.id
            WHERE r.building = ? AND r.entrance = ? AND r.room_number = ?
            LIMIT 1
        ''', (building, entrance, room_number)).fetchone()
        
        if room:
            return int(room['max_occupants'])
    
    return 1


def get_room_current_occupants(building, entrance, room_number, exclude_employee_id=None):
    with get_db() as conn:
        query = '''
            SELECT COUNT(*) as count
            FROM employees
            WHERE TRIM(COALESCE(building, '')) = TRIM(COALESCE(?, ''))
            AND TRIM(COALESCE(entrance, '')) = TRIM(COALESCE(?, ''))
            AND TRIM(COALESCE(room_number, '')) = TRIM(COALESCE(?, ''))
        '''
        params = [building, entrance, room_number]
        
        if exclude_employee_id:
            query += ' AND id != ?'
            params.append(exclude_employee_id)
        
        result = conn.execute(query, params).fetchone()
        return result['count'] if result else 0









