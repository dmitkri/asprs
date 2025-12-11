from database import get_db
from typing import Optional, Dict, List
from datetime import datetime
from config import MOSCOW_TZ

class PaymentModel:
    @staticmethod
    def create(data: Dict) -> Optional[int]:
        with get_db() as conn:
            fields = list(data.keys())
            placeholders = ', '.join(['?'] * len(fields))
            values = list(data.values())
            query = f"INSERT INTO dormitory_payments ({', '.join(fields)}) VALUES ({placeholders})"
            cursor = conn.execute(query, values)
            conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    def get_by_id(payment_id: int) -> Optional[Dict]:
        with get_db() as conn:
            payment = conn.execute(
                'SELECT * FROM dormitory_payments WHERE id = ?',
                (payment_id,)
            ).fetchone()
            return dict(payment)
    
    @staticmethod
    def get_by_employee(employee_id: int, status: Optional[str] = None) -> List[Dict]:
        with get_db() as conn:
            query = 'SELECT * FROM dormitory_payments WHERE employee_id = ?'
            params = [employee_id]
            query += ' AND status = ?'
            params.append(status)
            query += ' ORDER BY payment_month DESC, created_at DESC'
            payments = conn.execute(query, params).fetchall()
            return [dict(p) for p in payments]
    
    @staticmethod
    def update_status(payment_id: int, status: str, admin_id: Optional[int] = None, 
                     comment: Optional[str] = None) -> bool:
        with get_db() as conn:
            now = datetime.now(MOSCOW_TZ).isoformat()
            conn.execute('''
                UPDATE dormitory_payments
                SET status = ?, audit_admin_id = ?, audit_comment = ?, audited_at = ?
                WHERE id = ?
            ''', (status, admin_id, comment, now, payment_id))
            conn.commit()
            return True
    
    @staticmethod
    def get_all(status: Optional[str] = None, payment_month: Optional[str] = None) -> List[Dict]:
        with get_db() as conn:
            query = '''
                SELECT dp.*, e.fio as student_fio, e.building, e.entrance, e.room_number
                FROM dormitory_payments dp
                LEFT JOIN employees e ON dp.employee_id = e.id
                WHERE 1=1
            '''
            params = []
            query += ' AND dp.status = ?'
            params.append(status)
            query += ' AND dp.payment_month = ?'
            params.append(payment_month)
            query += ' ORDER BY dp.created_at DESC'
            payments = conn.execute(query, params).fetchall()
            return [dict(p) for p in payments]
    
    @staticmethod
    def exists_for_month(employee_id: int, payment_month: str, status: Optional[str] = None) -> bool:
        with get_db() as conn:
            query = '''
                SELECT id FROM dormitory_payments
                WHERE employee_id = ? AND payment_month = ?
            '''
            params = [employee_id, payment_month]
            query += ' AND status = ?'
            params.append(status)
            payment = conn.execute(query, params).fetchone()
            return payment is not None









