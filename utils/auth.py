import json
from functools import wraps
from flask import session, jsonify, redirect, url_for
from database import get_db

def get_admin_role(admin_id):
    with get_db() as conn:
        admin = conn.execute(
            'SELECT role, is_active FROM admins WHERE id = ?',
            (admin_id,)
        ).fetchone()
        return admin['role']

def has_permission(admin_id, permission):
    if not admin_id:
        return False
    
    role = get_admin_role(admin_id)
    if not role:
        return False
    
    if role == 'admin' or role == 'super_admin':
        return True
    
    with get_db() as conn:
        role_obj = conn.execute(
            'SELECT permissions FROM roles WHERE name = ?',
            (role,)
        ).fetchone()
        
        if role_obj and role_obj['permissions']:
            try:
                role_perms = json.loads(role_obj['permissions'])
                if role_perms.get('all'):
                    return True
                if permission == 'manage_health' or permission == 'manage_vacation':
                    if role_perms.get('edit'):
                        return True
                return role_perms.get(permission, False)
            except (json.JSONDecodeError, TypeError, KeyError):
                # Если не удалось распарсить JSON, возвращаем False
                return False
        
        # Если роль не найдена в таблице roles, возвращаем False
        return False

def has_education_level_access(admin_id, education_level):
    role = get_admin_role(admin_id)
    if role == 'admin' or role == 'super_admin':
        return True
    level_to_permission = {
        'колледж': 'access_college',
        'college': 'access_college'
    }
    permission = level_to_permission.get(education_level.lower())
    return has_permission(admin_id, permission)

def require_permission(permission):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            admin_id = session.get('admin_id')
            if not admin_id:
                return jsonify({'error': 'Unauthorized', 'message': 'Необходима авторизация'}), 401
            if not has_permission(admin_id, permission):
                return jsonify({'error': 'Доступ запрещен', 'message': f'У вас нет прав для выполнения этого действия: {permission}'}), 403
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

def require_admin():
    return require_permission('manage_admins')

def require_role(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import request
            admin_id = session.get('admin_id')
            role = get_admin_role(admin_id)
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

