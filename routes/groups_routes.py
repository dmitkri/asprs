from flask import Blueprint, jsonify, request, session
import sqlite3
from database import get_db
from utils.auth import require_permission

groups_bp = Blueprint('groups', __name__)

@groups_bp.route('/api/groups', methods=['GET'])
def api_groups():
    """Получить список всех групп (для обратной совместимости)"""
    try:
        with get_db() as conn:
            groups = conn.execute('''
                SELECT name FROM groups ORDER BY name
            ''').fetchall()
            result = [row['name'] for row in groups]
            return jsonify(result)
    except Exception:
        # Если таблицы нет, пытаемся прочитать из файла
        try:
            with open('ofgroups.txt', 'r', encoding='utf-8') as f:
                groups = [line.strip() for line in f if line.strip()]
            return jsonify(groups)
        except FileNotFoundError:
            return jsonify([])

@groups_bp.route('/api/admin/groups', methods=['GET'])
@require_permission('edit')
def api_admin_groups():
    """Получить список всех групп с ID для управления"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db() as conn:
            # Проверяем существование таблицы
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='groups'
            """)
            if not cursor.fetchone():
                # Таблица не существует, создаем её
                from database import init_db
                init_db()
            
            groups = conn.execute('''
                SELECT id, name, created_at, updated_at 
                FROM groups 
                ORDER BY name
            ''').fetchall()
            result = [{
                'id': row['id'],
                'name': row['name'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            } for row in groups]
            return jsonify({'success': True, 'groups': result})
    except sqlite3.OperationalError as e:
        # Если таблица не существует, возвращаем пустой список
        if 'no such table' in str(e).lower():
            return jsonify({'success': True, 'groups': []})
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@groups_bp.route('/api/admin/groups', methods=['POST'])
@require_permission('edit')
def api_admin_groups_create():
    """Создать новую группу"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Название группы не может быть пустым'}), 400
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO groups (name, updated_at)
                VALUES (?, datetime('now'))
            ''', (name,))
            conn.commit()
            group_id = cursor.lastrowid
            return jsonify({
                'success': True,
                'group': {
                    'id': group_id,
                    'name': name
                }
            })
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Группа с таким названием уже существует'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@groups_bp.route('/api/admin/groups/<int:group_id>', methods=['PUT'])
@require_permission('edit')
def api_admin_groups_update(group_id):
    """Обновить группу"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Название группы не может быть пустым'}), 400
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE groups 
                SET name = ?, updated_at = datetime('now')
                WHERE id = ?
            ''', (name, group_id))
            conn.commit()
            
            if cursor.rowcount == 0:
                return jsonify({'error': 'Группа не найдена'}), 404
            
            return jsonify({
                'success': True,
                'group': {
                    'id': group_id,
                    'name': name
                }
            })
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Группа с таким названием уже существует'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@groups_bp.route('/api/admin/groups/<int:group_id>', methods=['DELETE'])
@require_permission('delete')
def api_admin_groups_delete(group_id):
    """Удалить группу"""
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Проверяем, используется ли группа студентами
            students_count = cursor.execute('''
                SELECT COUNT(*) as count 
                FROM employees 
                WHERE group_name = (SELECT name FROM groups WHERE id = ?)
            ''', (group_id,)).fetchone()['count']
            
            if students_count > 0:
                return jsonify({
                    'error': f'Невозможно удалить группу: она используется {students_count} студентом(ами)'
                }), 400
            
            cursor.execute('DELETE FROM groups WHERE id = ?', (group_id,))
            conn.commit()
            
            if cursor.rowcount == 0:
                return jsonify({'error': 'Группа не найдена'}), 404
            
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500









