from flask import Blueprint, request, jsonify, session
import re
import sqlite3
from database import get_db
from utils.auth import require_permission
from config import FIXED_COLS

column_bp = Blueprint('column', __name__)

@column_bp.route('/api/admin/add_column', methods=['POST'])
@require_permission('manage_columns')
def api_add_column():
    admin_id = session.get('admin_id')
    data = request.json
    name = data.get('name', '').strip()
    col_type = data.get('type', 'text')
    name = re.sub(r'[^a-zA-Zа-яА-Я0-9_\s]', '', name)
    name = name.replace(' ', '_').lower()
    name = re.sub(r'_+', '_', name).strip('_')
    with get_db() as conn:
        existing = conn.execute('SELECT name FROM custom_columns WHERE LOWER(name) = LOWER(?)', (name,)).fetchone()
        conn.execute('INSERT INTO custom_columns (name, col_type) VALUES (?, ?)', (name, col_type))
        conn.commit()
        return jsonify({'success': True, 'name': name})

@column_bp.route('/api/admin/delete_column', methods=['POST'])
@require_permission('manage_columns')
def api_delete_column():
    admin_id = session.get('admin_id')
    data = request.json
    name = data.get('name', '').strip()
    with get_db() as conn:
        conn.execute('DELETE FROM custom_columns WHERE name = ?', (name,))
        conn.commit()
        return jsonify({'success': True})

