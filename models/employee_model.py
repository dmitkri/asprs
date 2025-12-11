from database import get_db
from typing import Optional, Dict, List

class EmployeeModel:
    @staticmethod
    def get_by_id(employee_id: int) -> Optional[Dict]:
        with get_db() as conn:
            employee = conn.execute(
                'SELECT * FROM employees WHERE id = ?',
                (employee_id,)
            ).fetchone()
            return dict(employee)
    
    @staticmethod
    def get_by_tg_user_id(tg_user_id: int) -> Optional[Dict]:
        with get_db() as conn:
            tg_user = conn.execute(
                'SELECT employee_id FROM tg_users WHERE tg_user_id = ?',
                (tg_user_id,)
            ).fetchone()
            return EmployeeModel.get_by_id(tg_user['employee_id'])
    
    @staticmethod
    def get_roommates(employee_id: int) -> List[Dict]:
        with get_db() as conn:
            employee = conn.execute(
                'SELECT building, entrance, room_number FROM employees WHERE id = ?',
                (employee_id,)
            ).fetchone()
            roommates = conn.execute('''
                SELECT id, fio, phone, group_name, photo
                FROM employees
                WHERE building = ? AND entrance = ? AND room_number = ?
                  AND id != ?
                ORDER BY fio
            ''', (
                employee['building'],
                employee['entrance'],
                employee['room_number'],
                employee_id
            )).fetchall()
            return [dict(rm) for rm in roommates]
    
    @staticmethod
    def get_room_occupancy(building: str, entrance: str, room_number: str) -> Optional[int]:
        with get_db() as conn:
            room = conn.execute('''
                SELECT capacity FROM rooms
                WHERE building = ? AND entrance = ? AND room_number = ?
            ''', (building, entrance, room_number)).fetchone()
            return room['capacity']
    
    @staticmethod
    def update(employee_id: int, data: Dict) -> bool:
        with get_db() as conn:
            fields = []
            values = []
            for key, value in data.items():
                if key != 'id':
                    fields.append(f"{key} = ?")
                    values.append(value)
            values.append(employee_id)
            query = f"UPDATE employees SET {', '.join(fields)} WHERE id = ?"
            conn.execute(query, values)
            conn.commit()
            return True
    
    @staticmethod
    def create(data: Dict) -> Optional[int]:
        with get_db() as conn:
            fields = list(data.keys())
            placeholders = ', '.join(['?'] * len(fields))
            values = list(data.values())
            query = f"INSERT INTO employees ({', '.join(fields)}) VALUES ({placeholders})"
            cursor = conn.execute(query, values)
            conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    def delete(employee_id: int) -> bool:
        with get_db() as conn:
            conn.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
            conn.commit()
            return True
    
    @staticmethod
    def search(query: str = '', group: str = '', education_level: str = '') -> List[Dict]:
        with get_db() as conn:
            sql = 'SELECT * FROM employees WHERE 1=1'
            params = []
            sql += ' AND (fio LIKE ? OR phone LIKE ?)'
            params.extend([f'%{query}%', f'%{query}%'])
            sql += ' AND group_name = ?'
            params.append(group)
            sql += ' AND education_level = ?'
            params.append(education_level)
            sql += ' ORDER BY fio'
            employees = conn.execute(sql, params).fetchall()
            return [dict(emp) for emp in employees]









