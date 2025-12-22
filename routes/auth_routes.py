from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import check_password_hash
from database import get_db
from utils.auth import get_admin_role, has_permission
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Неверный логин или пароль!')
            return redirect(url_for('auth.admin_login'))
        
        with get_db() as conn:
            admin = conn.execute(
                'SELECT id, username, password_hash, role, is_active, fio, password_changed FROM admins WHERE username = ?',
                (username,)
            ).fetchone()
            
            # Проверка на None перед обращением к полям
            if admin is None:
                logger.warning(f'Попытка входа с несуществующим логином: {username}')
                flash('Неверный логин или пароль!')
                return redirect(url_for('auth.admin_login'))
            
            # Проверка активности пользователя
            if not admin['is_active']:
                logger.warning(f'Попытка входа неактивного пользователя: {username}')
                flash('Ваш аккаунт деактивирован!')
                return redirect(url_for('auth.admin_login'))
            
            # Проверка пароля ПЕРЕД созданием сессии
            if not check_password_hash(admin['password_hash'], password):
                logger.warning(f'Неверный пароль для пользователя: {username}')
                flash('Неверный логин или пароль!')
                return redirect(url_for('auth.admin_login'))
            
            # Создание сессии только после успешной проверки пароля
            admin_fio = admin['fio'] if admin['fio'] else ''
            password_changed = admin['password_changed'] if admin['password_changed'] else 0
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            session['admin_role'] = admin['role']
            session['admin_fio'] = admin_fio
            session['admin'] = True
            session['password_changed'] = password_changed
            
            logger.info(f'Успешный вход пользователя: {username} (ID: {admin["id"]})')
            return redirect(url_for('admin_pages.admin_panel', change_password=1))
    role = session.get('admin_role', '')
    admin_fio = session.get('admin_fio', '')
    password_changed = session.get('password_changed', 1) or 1
    from utils.auth import has_permission
    admin_id = session.get('admin_id')
    all_permissions = [
        'view', 'edit', 'delete', 'import', 'manage_columns', 
        'manage_health', 'manage_vacation', 'manage_admins', 
        'manage_bed_linen', 'manage_send_messages', 'view_reports', 'manage_tg_users', 
        'scan_qr', 'manage_rooms', 'manage_minors', 
        'manage_round_assignments', 'manage_payments', 'manage_events',
        'access_college', 'all'
    ]
    admin_permissions = {}
    for perm in all_permissions:
        admin_permissions[perm] = has_permission(admin_id, perm)
    return render_template('admin.html', admin_role=role, admin_fio=admin_fio, 
                         password_changed=password_changed, change_password=False,
                         admin_permissions=admin_permissions)

@auth_bp.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('admin_role', None)
    session.pop('admin_fio', None)
    session.pop('admin', None)
    return redirect('/')

@auth_bp.route('/api/user')
def api_user():
    admin_id = session.get('admin_id')
    return jsonify({
        'is_admin': bool(admin_id),
        'admin_id': admin_id,
        'admin_username': session.get('admin_username'),
        'admin_role': session.get('admin_role'),
        'admin_fio': session.get('admin_fio', '')
    })

@auth_bp.route('/api/admin/permissions')
def api_admin_permissions():
    admin_id = session.get('admin_id')
    permissions = {}
    all_permissions = [
        'view', 'edit', 'delete', 'import', 'manage_columns', 
        'manage_health', 'manage_vacation', 'manage_admins', 
        'manage_bed_linen', 'manage_send_messages', 'view_reports', 'manage_tg_users', 
        'scan_qr', 'manage_payments', 'manage_rooms', 
        'manage_minors', 'manage_round_assignments', 'manage_events',
        'access_college', 'all'
    ]
    for perm in all_permissions:
        permissions[perm] = has_permission(admin_id, perm)
    return jsonify({
        'permissions': permissions,
        'role': session.get('admin_role')
    })

