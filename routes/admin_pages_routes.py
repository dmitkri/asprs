from flask import Blueprint, render_template, redirect, url_for, request, session
from utils.auth import get_admin_role, has_permission
from database import get_db

admin_pages_bp = Blueprint('admin_pages', __name__)

@admin_pages_bp.route('/admin_panel')
def admin_panel():
    admin_id = session.get('admin_id')
    role = session.get('admin_role', '')
    admin_fio = session.get('admin_fio', '')
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
    with get_db() as conn:
        admin = conn.execute(
            'SELECT password_changed FROM admins WHERE id = ?',
            (admin_id,)
        ).fetchone()
        password_changed = admin['password_changed'] if admin['password_changed'] else 0
        session['password_changed'] = password_changed
    change_password = request.args.get('change_password', '0') == '1'
    return render_template('admin.html', admin_role=role, admin_fio=admin_fio, 
                         password_changed=password_changed, change_password=change_password,
                         admin_permissions=admin_permissions)

@admin_pages_bp.route('/admin/tg_users')
def admin_tg_users():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'manage_tg_users'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_tg_users.html', admin_role=role)

@admin_pages_bp.route('/admin/manage_admins')
def admin_manage_admins():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'manage_admins'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_manage_admins.html', admin_role=role)

@admin_pages_bp.route('/admin/manage_roles')
def admin_manage_roles():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'manage_admins'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_manage_roles.html', admin_role=role)

@admin_pages_bp.route('/admin/user_bot_settings')
def admin_user_bot_settings():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'manage_admins'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_user_bot_settings.html', admin_role=role)

@admin_pages_bp.route('/admin/manage_accommodation')
def admin_manage_accommodation():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'manage_rooms'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_manage_accommodation.html', admin_role=role)

@admin_pages_bp.route('/admin/manage_rooms')
def admin_manage_rooms():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'manage_rooms'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_manage_rooms.html', admin_role=role)

@admin_pages_bp.route('/admin/payments')
def admin_payments():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'manage_payments'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_payments.html', admin_role=role)

@admin_pages_bp.route('/admin/profile')
def admin_profile():
    admin_id = session.get('admin_id')
    role = get_admin_role(admin_id)
    can_manage_telegram = has_permission(admin_id, 'manage_minors') or has_permission(admin_id, 'manage_admins')
    return render_template('admin_profile.html', admin_role=role, can_manage_telegram=can_manage_telegram)

@admin_pages_bp.route('/admin/export')
def admin_export():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'view'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_export.html', admin_role=role)

@admin_pages_bp.route('/admin/manage_groups')
def admin_manage_groups():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'edit'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_manage_groups.html', admin_role=role)

@admin_pages_bp.route('/admin/duty_schedules')
def admin_duty_schedules():
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('auth.admin_login'))
    if not has_permission(admin_id, 'manage_rooms'):
        return render_template('no_access.html', message='У вас нет доступа к этой странице'), 403
    role = get_admin_role(admin_id)
    return render_template('admin_duty_schedules.html', admin_role=role)


