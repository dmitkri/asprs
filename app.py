from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_from_directory, send_file
import sqlite3
import os
import json
import uuid
import pandas as pd
import re
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta, timezone
import logging

# Импорт конфигурации
from config import (
    SECRET_KEY, UPLOAD_FOLDER, UPLOAD_FOLDER_EXCEL, 
    ALLOWED_EXTENSIONS, ALLOWED_EXCEL, MOSCOW_TZ
)
from utils.validators import parse_vacation_end

import calendar
import secrets
import io
import base64
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)
try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_FOLDER_EXCEL'] = UPLOAD_FOLDER_EXCEL

fixedCols = ['fio', 'phone', 'group_name', 'birth_date']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_file_excel(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXCEL

def get_db():
    conn = sqlite3.connect('aspirs.db')
    conn.row_factory = sqlite3.Row
    return conn

def clean_expired_vacations():
    """Очистка истекших заявлений на отпуск"""
    today = datetime.now(MOSCOW_TZ)
    with get_db() as conn:
        try:
            rows = conn.execute('SELECT id, vacation, vacation_history FROM employees WHERE vacation != ""').fetchall()
            for row in rows:
                try:
                    end_date = parse_vacation_end(row['vacation'])
                    if end_date and today > end_date:
                        history = json.loads(row['vacation_history'] or '[]')
                        history.append(row['vacation'])
                        conn.execute('UPDATE employees SET vacation = ?, vacation_history = ? WHERE id = ?', 
                                   ("", json.dumps(history), row['id']))
                except (ValueError, AttributeError, IndexError, TypeError) as e:
                    logger.warning(f'Ошибка при обработке заявления на отпуск для employee_id={row["id"]}: {e}')
                    continue
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f'Ошибка при очистке истекших заявлений: {e}', exc_info=True)
            conn.rollback()

def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fio TEXT NOT NULL,
                phone TEXT,
                group_name TEXT,
                birth_date TEXT,
                photo TEXT,
                notes TEXT DEFAULT '',
                absences TEXT DEFAULT '',
                reprimands TEXT DEFAULT '',
                vacation TEXT DEFAULT '',
                vacation_history TEXT DEFAULT '[]',
                extra_data TEXT DEFAULT '{}',
                room_number TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS custom_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                col_type TEXT DEFAULT 'text'
            );

            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                token TEXT,
                scanned_at TEXT,
                period_id INTEGER,
                FOREIGN KEY(employee_id) REFERENCES employees(id),
                FOREIGN KEY(period_id) REFERENCES bed_linen_dates(id),
                UNIQUE(employee_id, token)
            );

            CREATE TABLE IF NOT EXISTS bed_linen_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tg_users (
                tg_user_id INTEGER PRIMARY KEY,
                tg_username TEXT,
                employee_id INTEGER,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            );

            CREATE TABLE IF NOT EXISTS bed_linen_qr_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                qr_code TEXT UNIQUE NOT NULL,
                employee_id INTEGER NOT NULL,
                tg_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used BOOLEAN DEFAULT 0,
                FOREIGN KEY(employee_id) REFERENCES employees(id),
                FOREIGN KEY(tg_user_id) REFERENCES tg_users(tg_user_id)
            );

            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT,
                permissions TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS roles (
                name TEXT PRIMARY KEY,
                permissions TEXT NOT NULL,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS bed_linen_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS employee_changes_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                admin_id INTEGER,
                admin_username TEXT,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                admin_fio TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES admins(id)
            );

            CREATE TABLE IF NOT EXISTS dormitory_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                tg_user_id INTEGER,
                amount REAL,
                payment_date TEXT,
                payment_month TEXT,
                receipt_file TEXT,
                status TEXT DEFAULT 'pending',
                audit_admin_id INTEGER,
                audit_comment TEXT,
                audited_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (tg_user_id) REFERENCES tg_users(tg_user_id),
                FOREIGN KEY (audit_admin_id) REFERENCES admins(id)
            );

            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                room_number TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(building, entrance, room_number)
            );
        ''')

        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(events)")
            existing_cols = [row[1] for row in cursor.fetchall()]
            if 'coauthor_id' not in existing_cols:
                cursor.execute("ALTER TABLE events ADD COLUMN coauthor_id INTEGER")
                cursor.execute("ALTER TABLE events ADD COLUMN coauthor_fio TEXT")
                conn.commit()
        except sqlite3.OperationalError as e:
            pass
        try:
            cursor.execute("PRAGMA table_info(bed_linen_dates)")
            existing_cols = [row[1] for row in cursor.fetchall()]
            
            if existing_cols and 'date' in existing_cols and 'start_date' not in existing_cols:
                cursor.execute("DROP TABLE IF EXISTS bed_linen_dates_old")
                cursor.execute("ALTER TABLE bed_linen_dates RENAME TO bed_linen_dates_old")
                cursor.execute("""
                    CREATE TABLE bed_linen_dates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        is_active INTEGER DEFAULT 1
                    )
                """)
                cursor.execute("""
                    INSERT INTO bed_linen_dates (id, start_date, end_date, created_at, is_active)
                    SELECT id, date, date, created_at, is_active
                    FROM bed_linen_dates_old
                """)
                cursor.execute("DROP TABLE bed_linen_dates_old")
                conn.commit()
        except sqlite3.OperationalError as e:
            pass
        try:
            cursor.execute("PRAGMA table_info(scans)")
            scan_cols = [row[1] for row in cursor.fetchall()]
            if scan_cols and 'period_id' not in scan_cols:
                cursor.execute("ALTER TABLE scans ADD COLUMN period_id INTEGER")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_period_id ON scans(period_id)")
                conn.commit()
        except sqlite3.OperationalError:
            pass
        cursor.execute("PRAGMA table_info(custom_columns)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        if 'type' in existing_cols and 'col_type' not in existing_cols:
            cursor.execute('''
                CREATE TABLE custom_columns_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    col_type TEXT DEFAULT 'text'
                )
            ''')
            cursor.execute('INSERT INTO custom_columns_new (id, name, col_type) SELECT id, name, type FROM custom_columns')
            cursor.execute('DROP TABLE custom_columns')
            cursor.execute('ALTER TABLE custom_columns_new RENAME TO custom_columns')
        
        cursor.execute("PRAGMA table_info(employees)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        for col in ['notes', 'absences', 'reprimands', 'vacation', 'vacation_history']:
            if col not in existing_cols:
                default_val = "''" if col != 'vacation_history' else "'[]'"
                cursor.execute(f"ALTER TABLE employees ADD COLUMN {col} TEXT DEFAULT {default_val}")
        
        if 'room_number' not in existing_cols:
            cursor.execute("ALTER TABLE employees ADD COLUMN room_number TEXT DEFAULT ''")
        
        if 'building' not in existing_cols:
            cursor.execute("ALTER TABLE employees ADD COLUMN building TEXT DEFAULT ''")
        if 'entrance' not in existing_cols:
            cursor.execute("ALTER TABLE employees ADD COLUMN entrance TEXT DEFAULT ''")
        
        if 'tg_username' not in existing_cols:
            cursor.execute("ALTER TABLE employees ADD COLUMN tg_username TEXT DEFAULT ''")
        
        if 'room_occupancy' not in existing_cols:
            cursor.execute("ALTER TABLE employees ADD COLUMN room_occupancy INTEGER DEFAULT 1")
        
        cursor.execute("PRAGMA table_info(admins)")
        admin_cols = [row[1] for row in cursor.fetchall()]
        if 'fio' not in admin_cols:
            cursor.execute("ALTER TABLE admins ADD COLUMN fio TEXT DEFAULT ''")
        
        if 'password_changed' not in admin_cols:
            cursor.execute("ALTER TABLE admins ADD COLUMN password_changed INTEGER DEFAULT 0")
            cursor.execute("UPDATE admins SET password_changed = 0 WHERE password_changed IS NULL")
        
        try:
            cursor.execute("PRAGMA table_info(employee_changes_history)")
            history_cols = [row[1] for row in cursor.fetchall()]
            if 'admin_id' not in history_cols:
                cursor.execute("ALTER TABLE employee_changes_history ADD COLUMN admin_id INTEGER")
            if 'admin_username' not in history_cols:
                cursor.execute("ALTER TABLE employee_changes_history ADD COLUMN admin_username TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rooms_lookup ON rooms(building, entrance, room_number)")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("PRAGMA table_info(dormitory_payments)")
            existing_cols = [row[1] for row in cursor.fetchall()]
            if 'payment_month' not in existing_cols:
                cursor.execute("ALTER TABLE dormitory_payments ADD COLUMN payment_month TEXT")
                conn.commit()
        except sqlite3.OperationalError:
            pass
        conn.commit()
        
        init_roles(conn)
        
        cursor.execute("SELECT COUNT(*) as count FROM admins")
        if cursor.fetchone()['count'] == 0:
            password_hash = generate_password_hash('admin123')
            cursor.execute("PRAGMA table_info(admins)")
            admin_cols = [row[1] for row in cursor.fetchall()]
            if 'password_changed' in admin_cols:
                cursor.execute('''
                    INSERT INTO admins (username, password_hash, role, permissions, is_active, password_changed)
                    VALUES (?, ?, ?, ?, ?, 0)
                ''', ('admin', password_hash, 'super_admin', '{"all": true}', 1))
            else:
                cursor.execute('''
                    INSERT INTO admins (username, password_hash, role, permissions, is_active)
                    VALUES (?, ?, ?, ?, ?)
                ''', ('admin', password_hash, 'super_admin', '{"all": true}', 1))
            conn.commit()

def init_roles(conn):
    
    roles = [
        ('super_admin', json.dumps({'all': True}), 'Супер администратор - полный доступ ко всем функциям'),
        ('admin', json.dumps({
            'view': True,
            'edit': True,
            'delete': True,
            'import': True,
            'manage_columns': True,
            'manage_health': True,
            'manage_vacation': True,
            'manage_admins': False,
            'manage_bed_linen': True,
            'manage_send_messages': True,
            'view_reports': True,
            'manage_tg_users': True,
            'scan_qr': True,
            'manage_rooms': True,
            'manage_minors': True,
            'manage_round_assignments': True,
            'manage_payments': True,
            'manage_events': True
        }), 'Администратор - доступ ко всем функциям кроме управления админами'),
        ('vospitatel', json.dumps({
            'view': True,
            'edit': True,
            'delete': True,
            'import': False,
            'manage_columns': False,
            'manage_health': True,
            'manage_vacation': True,
            'manage_admins': False,
            'manage_bed_linen': True,
            'manage_send_messages': True,
            'view_reports': True,
            'manage_tg_users': True,
            'scan_qr': True,
            'manage_rooms': True,
            'manage_minors': True,
            'manage_round_assignments': True,
            'manage_payments': False,
            'manage_events': True
        }), 'Воспитатель - может редактировать карточки, добавлять, удалять студентов, управлять бельем, смотреть отчеты, управлять комнатами и несовершеннолетними'),
        ('razmeshenie', json.dumps({
            'view': True,
            'edit': False,
            'delete': False,
            'import': False,
            'manage_columns': False,
            'manage_health': False,
            'manage_vacation': False,
            'manage_admins': False,
            'manage_bed_linen': False,
            'manage_send_messages': False,
            'view_reports': True,
            'manage_tg_users': False,
            'scan_qr': False,
            'manage_rooms': False,
            'manage_minors': False,
            'manage_round_assignments': False,
            'manage_payments': False,
            'manage_events': False
        }), 'Администратор средства размещения - просмотр студентов и отчетов по белью'),
        ('audit', json.dumps({
            'view': False,
            'edit': False,
            'delete': False,
            'import': False,
            'manage_columns': False,
            'manage_health': False,
            'manage_vacation': False,
            'manage_admins': False,
            'manage_bed_linen': False,
            'view_reports': False,
            'manage_tg_users': False,
            'scan_qr': False,
            'manage_rooms': False,
            'manage_minors': False,
            'manage_round_assignments': False,
            'manage_payments': True,
            'manage_events': False
        }), 'Аудит - доступ только к разделу оплаты проживания')
    ]
    
    cursor = conn.cursor()
    for role_name, permissions, description in roles:
        cursor.execute('''
            INSERT OR REPLACE INTO roles (name, permissions, description)
            VALUES (?, ?, ?)
        ''', (role_name, permissions, description))
    conn.commit()

def get_admin_role(admin_id):
    
    if not admin_id:
        return None
    
    with get_db() as conn:
        admin = conn.execute(
            'SELECT role, is_active FROM admins WHERE id = ?',
            (admin_id,)
        ).fetchone()
        
        if not admin or not admin['is_active']:
            return None
        
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
        
        if role_obj:
            role_perms = json.loads(role_obj['permissions'])
            if role_perms.get('all'):
                return True
            
            if permission == 'manage_health' or permission == 'manage_vacation':
                if role_perms.get('edit'):
                    return True
            
            return role_perms.get(permission, False)
        
        if role == 'vospitatel':
            allowed_permissions = [
                'view', 'edit', 'delete', 'manage_bed_linen', 'manage_send_messages',
                'view_reports', 'manage_tg_users', 'scan_qr'
            ]
            if permission == 'manage_health' or permission == 'manage_vacation':
                return 'edit' in allowed_permissions
            return permission in allowed_permissions
        
        if role == 'razmeshenie':
            allowed_permissions = ['view', 'view_reports']
            return permission in allowed_permissions
        
        if role == 'audit':
            allowed_permissions = ['manage_payments']
            return permission in allowed_permissions
        
        admin = conn.execute(
            'SELECT permissions FROM admins WHERE id = ?',
            (admin_id,)
        ).fetchone()
        
        if admin and admin['permissions']:
            perms = json.loads(admin['permissions'])
            if perms.get('all'):
                return True
            if permission == 'manage_health' or permission == 'manage_vacation':
                if perms.get('edit'):
                    return True
            return perms.get(permission, False)
        
        return False

def require_permission(permission):
    
    def decorator(f):
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

def require_role(*allowed_roles):
    
    def decorator(f):
        def wrapper(*args, **kwargs):
            admin_id = session.get('admin_id')
            if not admin_id:
                return redirect(url_for('admin_login'))
            
            role = get_admin_role(admin_id)
            if not role or role not in allowed_roles:
                return render_template('no_access.html', 
                    message='У вас нет доступа к этой странице'), 403
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

def require_admin():
    
    return require_role('admin', 'super_admin')

init_db()
clean_expired_vacations()

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

def parse_birth_date(date_value):
    
    try:
        if date_value is None:
            return None
        
        try:
            if pd.isna(date_value):
                return None
        except:
            pass
        
        if isinstance(date_value, (datetime, pd.Timestamp)):
            return date_value.strftime('%Y-%m-%d')
        
        date_str = str(date_value).strip()
        if not date_str or date_str.lower() in ['nan', 'none', '']:
            return None
        
        try:
            dt = datetime.strptime(date_str, '%d.%m.%Y')
            return dt.strftime('%Y-%m-%d')
        except:
            pass
            return None
    except Exception as e:
        pass
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        with get_db() as conn:
            admin = conn.execute(
                'SELECT id, username, password_hash, role, is_active, fio, password_changed FROM admins WHERE username = ?',
                (username,)
            ).fetchone()
            
            if admin and admin['is_active'] and check_password_hash(admin['password_hash'], password):
                try:
                    admin_fio = admin['fio'] if admin['fio'] else ''
                except (KeyError, TypeError):
                    admin_fio = ''
                
                try:
                    password_changed = admin['password_changed'] if admin['password_changed'] else 0
                except (KeyError, TypeError):
                    password_changed = 0
                
                session['admin_id'] = admin['id']
                session['admin_username'] = admin['username']
                session['admin_role'] = admin['role']
                session['admin_fio'] = admin_fio
                session['admin'] = True  # Для обратной совместимости
                session['password_changed'] = password_changed
                
                if not password_changed:
                    return redirect(url_for('admin_panel', change_password=1))
                
                return redirect(url_for('admin_panel'))
        
        flash('Неверный логин или пароль!')
    
    if session.get('admin_id'):
        admin_id = session.get('admin_id')
        role = session.get('admin_role', '')
        admin_fio = session.get('admin_fio', '')
        password_changed = session.get('password_changed', 1) or 1
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
    return render_template('login.html')

@app.route('/admin_panel')
def admin_panel():
    if not session.get('admin_id'):
        return redirect(url_for('admin_login'))
    
    admin_id = session.get('admin_id')
    role = session.get('admin_role', '')
    admin_fio = session.get('admin_fio', '')
    
    with get_db() as conn:
        admin = conn.execute(
            'SELECT password_changed FROM admins WHERE id = ?',
            (admin_id,)
        ).fetchone()
        
        if admin:
            try:
                password_changed = admin['password_changed'] if admin['password_changed'] else 0
            except (KeyError, TypeError):
                password_changed = 0
            session['password_changed'] = password_changed
        else:
            password_changed = session.get('password_changed', 1) or 1
    
    change_password = request.args.get('change_password', '0') == '1'
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
                         password_changed=password_changed, change_password=change_password,
                         admin_permissions=admin_permissions)

@app.route('/admin/tg_users')
def admin_tg_users():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('admin_login'))
    
    role = get_admin_role(admin_id)
    if role not in ['admin', 'super_admin', 'vospitatel']:
        return render_template('no_access.html', 
            message='У вас нет доступа к этой странице. Только администраторы и воспитатели могут управлять Telegram пользователями.'), 403
    
    return render_template('admin_tg_users.html', admin_role=role)

@app.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('admin_role', None)
    session.pop('admin_fio', None)
    session.pop('admin', None)
    return redirect('/')

@app.route('/api/user')
def api_user():
    admin_id = session.get('admin_id')
    return jsonify({
        'is_admin': bool(admin_id),
        'admin_id': admin_id,
        'admin_username': session.get('admin_username'),
        'admin_role': session.get('admin_role'),
        'admin_fio': session.get('admin_fio', '')
    })

@app.route('/api/admin/permissions')
def api_admin_permissions():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    permissions = {}
    for perm in ['view', 'edit', 'delete', 'import', 'manage_columns', 'manage_health', 'manage_vacation', 'manage_admins', 'manage_bed_linen', 'manage_send_messages']:
        permissions[perm] = has_permission(admin_id, perm)
    
    return jsonify({
        'permissions': permissions,
        'role': session.get('admin_role')
    })

@app.route('/api/columns')
def api_columns():
    with get_db() as conn:
        custom = [dict(row) for row in conn.execute('SELECT name, col_type FROM custom_columns ORDER BY id').fetchall()]
    return jsonify({'fixed': fixedCols, 'custom': custom})

# Старый роут /api/employees удален - теперь используется роут из routes/employee_routes.py
# который поддерживает фильтры по статусу (проживание, здоровье)

@app.route('/api/employee/<int:emp_id>')
def api_employee(emp_id):
    clean_expired_vacations()
    with get_db() as conn:
        row = conn.execute('SELECT * FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        d = dict(row)
        d['vacation'] = d.get('vacation') or ''
        d['vacation_history'] = json.loads(d.get('vacation_history', '[]'))
        extra = json.loads(d.get('extra_data', '{}'))
        d['extra_data'] = extra
        d['representatives'] = extra.get('representatives', [])
        return jsonify(d)

@app.route('/api/employee/<int:emp_id>/changes_history')
@require_admin()
def api_employee_changes_history(emp_id):
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Доступ запрещен. Только администраторы могут просматривать историю изменений.'}), 403
    
    with get_db() as conn:
        student = conn.execute('SELECT id, fio FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        try:
            history = conn.execute('''
                SELECT 
                    ech.id, 
                    ech.admin_id, 
                    ech.admin_username, 
                    ech.field_name, 
                    ech.old_value, 
                    ech.new_value, 
                    ech.changed_at,
                    a.role as admin_role,
                    a.fio as admin_fio
                FROM employee_changes_history ech
                LEFT JOIN admins a ON ech.admin_id = a.id
                WHERE ech.employee_id = ?
                ORDER BY ech.changed_at DESC
                LIMIT 100
            ''', (emp_id,)).fetchall()
            
            
            result = []
            for row in history:
                admin_username = row['admin_username'] or 'Система'
                admin_role = row['admin_role'] or 'неизвестно'
                admin_fio = row['admin_fio'] or ''
                
                if admin_fio:
                    display_name = f"{admin_fio} ({admin_role})"
                else:
                    display_name = f"{admin_username} ({admin_role})"
                
                result.append({
                    'id': row['id'],
                    'admin_id': row['admin_id'],
                    'admin_username': display_name,
                    'admin_role': admin_role,
                    'field_name': row['field_name'],
                    'old_value': row['old_value'] or '',
                    'new_value': row['new_value'] or '',
                    'changed_at': row['changed_at']
                })
            
            return jsonify({'success': True, 'history': result})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Ошибка получения истории: {str(e)}'}), 500

@app.route('/api/employee/<int:emp_id>/roommates')
def api_roommates(emp_id):
    
    clean_expired_vacations()
    with get_db() as conn:
        row = conn.execute('SELECT building, entrance, room_number FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Student not found'}), 404
        
        building = row['building']
        entrance = row['entrance']
        room_number = row['room_number']
        
        if not building or not entrance or not room_number:
            return jsonify([])
        
        rows = conn.execute(
            'SELECT id, fio, phone, group_name FROM employees WHERE building = ? AND entrance = ? AND room_number = ? AND id != ? ORDER BY fio',
            (building, entrance, room_number, emp_id)
        ).fetchall()
        
        result = []
        for r in rows:
            result.append({
                'id': r['id'],
                'fio': r['fio'],
                'phone': r['phone'] or '',
                'group_name': r['group_name'] or ''
            })
        
        return jsonify(result)

@app.route('/api/admin/add_column', methods=['POST'])
@require_permission('manage_columns')
def api_add_column():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    name = data.get('name', '').strip()
    col_type = data.get('type', 'text')
    if not name:
        return jsonify({'error': 'Введите название столбца'}), 400
    
    name = re.sub(r'[^a-zA-Zа-яА-Я0-9_\s]', '', name)  # Только буквы, цифры, пробелы и подчеркивания
    name = name.replace(' ', '_').lower()
    
    name = re.sub(r'_+', '_', name).strip('_')
    
    if not name:
        return jsonify({'error': 'Название столбца после нормализации пустое'}), 400
    
    if name in fixedCols:
        return jsonify({'error': f'Столбец "{name}" уже существует (фиксированный столбец)'}), 400
    
    with get_db() as conn:
        existing = conn.execute('SELECT name FROM custom_columns WHERE LOWER(name) = LOWER(?)', (name,)).fetchone()
        if existing:
            return jsonify({'error': f'Столбец "{name}" уже существует'}), 400
        
        try:
            conn.execute('INSERT INTO custom_columns (name, col_type) VALUES (?, ?)', (name, col_type))
            conn.commit()
            return jsonify({'success': True, 'name': name})
        except sqlite3.IntegrityError as e:
            return jsonify({'error': f'Столбец "{name}" уже существует'}), 400
        except Exception as e:
            return jsonify({'error': f'Ошибка при добавлении столбца: {str(e)}'}), 500

@app.route('/api/admin/employee', methods=['POST'])
@require_permission('edit')
def api_add_employee():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    if not data.get('fio'):
        return jsonify({'error': 'FIO required'}), 400

    extra = data.get('extra', {})
    if not isinstance(extra, dict):
        extra = {}
    extra['representatives'] = data.get('representatives', [])
    
    
    extra_json = json.dumps(extra, ensure_ascii=False)
    
    # Обработка даты рождения: пустая строка преобразуется в None
    birth_date = data.get('birth_date', '') or None
    if birth_date:
        birth_date = birth_date.strip()
        if not birth_date:
            birth_date = None

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO employees (fio, phone, group_name, birth_date, building, room_number, entrance, notes, absences, reprimands, vacation, vacation_history, extra_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?)
        ''', (
            data['fio'], data.get('phone', ''), data.get('group_name', ''),
            birth_date, data.get('building', ''), data.get('room_number', ''),
            data.get('entrance', ''), data.get('notes', ''), data.get('absences', ''),
            data.get('reprimands', ''), data.get('vacation', ''), extra_json
        ))
        new_id = cur.lastrowid
        conn.commit()
        return jsonify({'success': True, 'id': new_id})

# Endpoint /api/admin/employee/<int:emp_id> POST перенесен в routes/employee_routes.py
# для правильной обработки vacation_history и других полей

@app.route('/api/admin/employee/<int:emp_id>', methods=['DELETE'])
@require_permission('delete')
def api_delete_employee(emp_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    with get_db() as conn:
        photo = conn.execute('SELECT photo FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if photo and photo['photo']:
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo['photo'])
            if os.path.exists(photo_path):
                os.remove(photo_path)
        conn.execute('DELETE FROM employees WHERE id = ?', (emp_id,))
        conn.commit()
        return jsonify({'success': True})

@app.route('/api/admin/photo/<int:emp_id>', methods=['POST'])
@require_permission('edit')
def api_update_photo(emp_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    if 'photo' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['photo']
    if file and allowed_file(file.filename):
        with get_db() as conn:
            old_photo = conn.execute('SELECT photo FROM employees WHERE id = ?', (emp_id,)).fetchone()
            if old_photo and old_photo['photo']:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_photo['photo'])
                if os.path.exists(old_path):
                    os.remove(old_path)
        _, ext = os.path.splitext(file.filename)
        filename = str(uuid.uuid4()) + ext
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        with get_db() as conn:
            conn.execute('UPDATE employees SET photo = ? WHERE id = ?', (filename, emp_id))
            conn.commit()
        return jsonify({'success': True, 'photo': filename})
    return jsonify({'error': 'Invalid file'}), 400

@app.route('/api/admin/import_excel/check', methods=['POST'])
@require_permission('import')
def api_import_excel_check():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not file or not allowed_file_excel(file.filename):
        return jsonify({'error': 'Invalid file: only .xlsx or .xls'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER_EXCEL'], filename)
    file.save(filepath)

    try:
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'xlsx'
        engine = None
        if file_ext == 'xls':
            try:
                import xlrd
                engine = 'xlrd'
            except ImportError:
                return jsonify({'error': 'Для чтения .xls файлов требуется библиотека xlrd. Установите: pip install xlrd'}), 400
        else:
            engine = 'openpyxl'
        
        try:
            df = pd.read_excel(filepath, engine=engine)
        except Exception as read_error:
            os.remove(filepath)
            return jsonify({'error': f'Ошибка чтения файла: {str(read_error)}'}), 400
        
        if df.empty:
            os.remove(filepath)
            return jsonify({'error': 'Empty file'}), 400

        df.columns = [normalize_header(str(col)) for col in df.columns]

        required_cols = ['fio']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            os.remove(filepath)
            available_cols = ', '.join(df.columns.tolist())
            return jsonify({'error': f'Отсутствуют обязательные колонки: {", ".join(missing_cols)}. Доступные колонки: {available_cols}'}), 400

        matches = []  # Список совпадений по ФИО
        new_students = []  # Список новых студентов
        errors = []
        
        with get_db() as conn:
            for idx, row in df.iterrows():
                try:
                    fio_value = row.get('fio', '') if 'fio' in row.index else ''
                    if pd.isna(fio_value) or fio_value == '':
                        fio = ''
                    else:
                        fio = str(fio_value).strip()
                    
                    if not fio:
                        errors.append(f'Строка {idx + 2}: ФИО не указано')
                        continue
                    
                    phone = ''
                    if 'phone' in row.index:
                        phone_value = row.get('phone', '')
                        if pd.notna(phone_value) and phone_value != '':
                            phone = str(phone_value).strip()
                            phone = ''.join(c for c in phone if c.isdigit())
                            if phone and not phone.startswith('8'):
                                if phone.startswith('7') and len(phone) == 11:
                                    phone = '8' + phone[1:]
                                elif len(phone) == 10:
                                    phone = '8' + phone
                            if phone and (not phone.startswith('8') or len(phone) != 11):
                                errors.append(f'Строка {idx + 2}: Неверный формат телефона. Требуется формат 8---------- (11 цифр)')
                                continue
                    
                    birth_date = None
                    if 'birth_date' in row.index:
                        birth_date_value = row.get('birth_date', '')
                        if pd.notna(birth_date_value) and birth_date_value != '':
                            parsed_date = parse_birth_date(birth_date_value)
                            if parsed_date:
                                birth_date = parsed_date
                            else:
                                date_str = str(birth_date_value).strip()
                                if date_str and date_str.lower() not in ['nan', 'none', '']:
                                    errors.append(f'Строка {idx + 2}: Неверный формат даты рождения. Требуется формат ДД.ММ.ГГГГ')
                                    continue
                    
                    existing = conn.execute(
                        'SELECT id, fio, phone, birth_date FROM employees WHERE LOWER(fio) = LOWER(?)',
                        (fio,)
                    ).fetchone()
                    
                    if existing:
                        matches.append({
                            'row': idx + 2,
                            'fio': fio,
                            'new_phone': phone,
                            'new_birth_date': birth_date,
                            'existing_id': existing['id'],
                            'existing_fio': existing['fio'],
                            'existing_phone': existing['phone'] or '',
                            'existing_birth_date': existing['birth_date'] or ''
                        })
                    else:
                        new_students.append({
                            'row': idx + 2,
                            'fio': fio,
                            'phone': phone,
                            'birth_date': birth_date
                        })
                        
                except Exception as e:
                    errors.append(f'Строка {idx + 2}: {str(e)}')
                    continue

        import json
        temp_data = {
            'matches': matches,
            'new_students': new_students,
            'filepath': filepath
        }
        temp_file = filepath + '.temp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(temp_data, f, ensure_ascii=False, default=str)
        
        return jsonify({
            'success': True,
            'matches': matches,
            'new_students': new_students,
            'errors': errors[:20],
            'temp_file': filename + '.temp'
        })

    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/import_excel', methods=['POST'])
@require_permission('import')
def api_import_excel():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    temp_file = data.get('temp_file')
    update_ids = set(data.get('update_ids', []))  # ID студентов, которых нужно обновить
    
    if not temp_file:
        return jsonify({'error': 'No temp file'}), 400
    
    temp_filepath = os.path.join(app.config['UPLOAD_FOLDER_EXCEL'], temp_file)
    if not os.path.exists(temp_filepath):
        return jsonify({'error': 'Temp file not found'}), 404
    
    try:
        import json
        with open(temp_filepath, 'r', encoding='utf-8') as f:
            temp_data = json.load(f)
        
        matches = temp_data.get('matches', [])
        new_students = temp_data.get('new_students', [])
        original_filepath = temp_data.get('filepath')
        
        imported = 0
        updated = 0
        skipped = 0
        
        with get_db() as conn:
            for match in matches:
                if match['existing_id'] in update_ids:
                    conn.execute('''
                        UPDATE employees 
                        SET phone = ?, birth_date = ?
                        WHERE id = ?
                    ''', (match['new_phone'], match['new_birth_date'], match['existing_id']))
                    updated += 1
                else:
                    skipped += 1
            
            for student in new_students:
                conn.execute('''
                    INSERT INTO employees (fio, phone, birth_date, notes, absences, reprimands, vacation, vacation_history, extra_data)
                    VALUES (?, ?, ?, '', '', '', '', '[]', '{}')
                ''', (student['fio'], student['phone'], student['birth_date']))
                imported += 1
            
            conn.commit()
        
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        if os.path.exists(original_filepath):
            os.remove(original_filepath)
        
        return jsonify({
            'success': True,
            'imported': imported,
            'updated': updated,
            'skipped': skipped
        })

    except Exception as e:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/x-icon')

@app.route('/api/admin/delete_column', methods=['POST'])
@require_permission('manage_columns')
def api_delete_column():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Empty name'}), 400
    with get_db() as conn:
        result = conn.execute('DELETE FROM custom_columns WHERE name = ?', (name,)).rowcount
        if result == 0:
            return jsonify({'error': 'Column not found'}), 404
        conn.execute("UPDATE employees SET extra_data = json_remove(extra_data, '$.' || ?)", (name,))
        conn.commit()
    return jsonify({'success': True})

@app.route('/api/import_excel', methods=['POST'])
def api_import_excel_user():
    
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    if not file or not allowed_file_excel(file.filename):
        return jsonify({'error': 'Недопустимый файл: только .xlsx или .xls'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER_EXCEL'], filename)
    file.save(filepath)

    try:
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'xlsx'
        engine = None
        if file_ext == 'xls':
            try:
                import xlrd
                engine = 'xlrd'
            except ImportError:
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'error': 'Для чтения .xls файлов требуется библиотека xlrd. Установите: pip install xlrd'}), 400
        else:
            engine = 'openpyxl'
        
        try:
            df = pd.read_excel(filepath, engine=engine)
        except Exception as read_error:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'Ошибка чтения файла: {str(read_error)}'}), 400
        
        if df.empty:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': 'Файл пуст'}), 400

        df.columns = [normalize_header(str(col)) for col in df.columns]

        imported = 0
        errors = []
        
        with get_db() as conn:
            for idx, row in df.iterrows():
                try:
                    fio_value = row.get('fio', '') if 'fio' in row.index else ''
                    if pd.isna(fio_value) or fio_value == '':
                        fio = ''
                    else:
                        fio = str(fio_value).strip()
                    
                    if not fio:
                        errors.append(f'Строка {idx + 2}: ФИО не указано')
                        continue
                    
                    phone = ''
                    if 'phone' in row.index:
                        phone_value = row.get('phone', '')
                        if pd.notna(phone_value) and phone_value != '':
                            phone = str(phone_value).strip()
                    
                    birth_date = None
                    if 'birth_date' in row.index:
                        birth_date_value = row.get('birth_date', '')
                        if pd.notna(birth_date_value) and birth_date_value != '':
                            birth_date = parse_birth_date(birth_date_value)
                    
                    existing = conn.execute('SELECT id FROM employees WHERE LOWER(fio) = LOWER(?)', (fio,)).fetchone()
                    
                    if existing:
                        conn.execute('''
                            UPDATE employees 
                            SET phone = ?, birth_date = ?
                            WHERE id = ?
                        ''', (phone, birth_date, existing['id']))
                        imported += 1
                    else:
                        conn.execute('''
                            INSERT INTO employees (fio, phone, birth_date, notes, absences, reprimands, vacation, vacation_history, extra_data)
                            VALUES (?, ?, ?, '', '', '', '', '[]', '{}')
                        ''', (fio, phone, birth_date))
                        imported += 1
                except Exception as e:
                    errors.append(f'Строка {idx + 2}: {str(e)}')
                    continue

            conn.commit()

        os.remove(filepath)
        
        result = {
            'success': True,
            'imported': imported,
            'errors': errors[:10] if errors else []
        }
        
        if len(errors) > 10:
            result['errors_count'] = len(errors)
        
        return jsonify(result)

    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'Ошибка обработки файла: {str(e)}'}), 500

@app.route('/api/admin/admins', methods=['GET'])
@require_admin()
def api_list_admins():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        admins = conn.execute('''
            SELECT id, username, role, is_active, created_at, fio
            FROM admins 
            ORDER BY created_at DESC
        ''').fetchall()
        
        result = []
        for admin in admins:
            try:
                fio = admin['fio'] if admin['fio'] else ''
            except (KeyError, TypeError):
                fio = ''
            
            result.append({
                'id': admin['id'],
                'username': admin['username'],
                'role': admin['role'],
                'is_active': bool(admin['is_active']),
                'created_at': admin['created_at'],
                'fio': fio
            })
        
        return jsonify(result)

@app.route('/api/admin/admins', methods=['POST'])
@require_admin()
def api_create_admin():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'vospitatel')
    fio = data.get('fio', '').strip()
    
    system_roles = ['admin', 'super_admin', 'vospitatel', 'razmeshenie', 'audit']
    if role not in system_roles:
        with get_db() as conn:
            role_exists = conn.execute(
                'SELECT name FROM roles WHERE name = ?',
                (role,)
            ).fetchone()
            if not role_exists:
                return jsonify({'error': f'Роль "{role}" не найдена'}), 400
    
    if not username or not password:
        return jsonify({'error': 'Логин и пароль обязательны'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Пароль должен содержать минимум 6 символов'}), 400
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT id FROM admins WHERE username = ?',
            (username,)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Пользователь с таким логином уже существует'}), 400
        
        password_hash = generate_password_hash(password)
        conn.execute('''
            INSERT INTO admins (username, password_hash, role, is_active, fio, password_changed)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (username, password_hash, role, 1, fio))
        conn.commit()
        
        return jsonify({'success': True})

@app.route('/api/admin/admins/<int:admin_id>', methods=['POST'])
@require_admin()
def api_update_admin(admin_id):
    current_admin_id = session.get('admin_id')
    if not current_admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    role = data.get('role')
    is_active = data.get('is_active')
    password = data.get('password', '').strip()
    
    with get_db() as conn:
        if admin_id == current_admin_id and is_active == False:
            return jsonify({'error': 'Нельзя деактивировать самого себя'}), 400
        
        updates = []
        params = []
        
        if role is not None:
            system_roles = ['admin', 'super_admin', 'vospitatel', 'razmeshenie', 'audit']
            if role not in system_roles:
                role_exists = conn.execute(
                    'SELECT name FROM roles WHERE name = ?',
                    (role,)
                ).fetchone()
                if not role_exists:
                    return jsonify({'error': f'Роль "{role}" не найдена'}), 400
            updates.append('role = ?')
            params.append(role)
        
        if is_active is not None:
            updates.append('is_active = ?')
            params.append(1 if is_active else 0)
        
        if password:
            if len(password) < 6:
                return jsonify({'error': 'Пароль должен содержать минимум 6 символов'}), 400
            password_hash = generate_password_hash(password)
            updates.append('password_hash = ?')
            params.append(password_hash)
        
        fio = data.get('fio', '').strip()
        if fio is not None:
            updates.append('fio = ?')
            params.append(fio)
        
        if not updates:
            return jsonify({'error': 'Нет данных для обновления'}), 400
        
        params.append(admin_id)
        query = f'UPDATE admins SET {", ".join(updates)} WHERE id = ?'
        conn.execute(query, params)
        conn.commit()
        
        return jsonify({'success': True})

@app.route('/api/admin/admins/<int:admin_id>', methods=['DELETE'])
@require_admin()
def api_delete_admin(admin_id):
    current_admin_id = session.get('admin_id')
    if not current_admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if admin_id == current_admin_id:
        return jsonify({'error': 'Нельзя удалить самого себя'}), 400
    
    with get_db() as conn:
        conn.execute('DELETE FROM admins WHERE id = ?', (admin_id,))
        conn.commit()
        
        return jsonify({'success': True})

@app.route('/admin/manage_admins')
@require_admin()
def admin_manage_admins():
    
    return render_template('admin_manage_admins.html')

@app.route('/admin/manage_roles')
@require_admin()
def admin_manage_roles():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('admin_login'))
    
    role = get_admin_role(admin_id)
    if role not in ['super_admin', 'admin']:
        return render_template('no_access.html', 
            message='У вас нет доступа к этой странице. Только администраторы могут управлять ролями.')
    
    return render_template('admin_manage_roles.html')

@app.route('/api/admin/roles', methods=['GET'])
@require_admin()
def api_list_roles():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['super_admin', 'admin']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    with get_db() as conn:
        roles = conn.execute('''
            SELECT name, permissions, description
            FROM roles 
            ORDER BY name
        ''').fetchall()
        
        result = []
        for role_row in roles:
            try:
                perms = json.loads(role_row['permissions'])
            except:
                perms = {}
            
            result.append({
                'name': role_row['name'],
                'permissions': perms,
                'description': role_row['description'] or ''
            })
        
        return jsonify({'success': True, 'roles': result})

@app.route('/api/admin/roles', methods=['POST'])
@require_admin()
def api_create_role():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['super_admin', 'admin']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    data = request.json
    role_name = data.get('name', '').strip()
    permissions = data.get('permissions', {})
    description = data.get('description', '').strip()
    
    if not role_name:
        return jsonify({'error': 'Название роли обязательно'}), 400
    
    system_roles = ['super_admin', 'admin']
    if role_name in system_roles:
        return jsonify({'error': f'Роль "{role_name}" является системной и не может быть изменена'}), 400
    
    all_permissions = [
        'view', 'edit', 'delete', 'import', 'manage_columns', 
        'manage_health', 'manage_vacation', 'manage_admins', 
        'manage_bed_linen', 'manage_send_messages', 'view_reports', 'manage_tg_users', 
        'scan_qr', 'manage_rooms', 'manage_minors', 
        'manage_round_assignments', 'manage_payments', 'manage_events',
        'access_college', 'all'
        'access_college', 'all'
    ]
    
    for perm in permissions.keys():
        if perm not in all_permissions:
            return jsonify({'error': f'Неизвестное право: {perm}'}), 400
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT name FROM roles WHERE name = ?',
            (role_name,)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Роль с таким названием уже существует'}), 400
        
        conn.execute('''
            INSERT INTO roles (name, permissions, description)
            VALUES (?, ?, ?)
        ''', (role_name, json.dumps(permissions), description))
        conn.commit()
        
        return jsonify({'success': True})

@app.route('/api/admin/roles/<role_name>', methods=['POST'])
@require_admin()
def api_update_role(role_name):
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['super_admin', 'admin']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    system_roles = ['super_admin', 'admin']
    if role_name in system_roles:
        return jsonify({'error': f'Роль "{role_name}" является системной и не может быть изменена'}), 400
    
    data = request.json
    permissions = data.get('permissions')
    description = data.get('description', '').strip()
    
    if permissions is None:
        return jsonify({'error': 'Права обязательны'}), 400
    
    all_permissions = [
        'view', 'edit', 'delete', 'import', 'manage_columns', 
        'manage_health', 'manage_vacation', 'manage_admins', 
        'manage_bed_linen', 'manage_send_messages', 'view_reports', 'manage_tg_users', 
        'scan_qr', 'manage_rooms', 'manage_minors', 
        'manage_round_assignments', 'manage_payments', 'manage_events',
        'access_college', 'all'
        'access_college', 'all'
    ]
    
    for perm in permissions.keys():
        if perm not in all_permissions:
            return jsonify({'error': f'Неизвестное право: {perm}'}), 400
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT name FROM roles WHERE name = ?',
            (role_name,)
        ).fetchone()
        
        if not existing:
            return jsonify({'error': 'Роль не найдена'}), 404
        
        conn.execute('''
            UPDATE roles 
            SET permissions = ?, description = ?
            WHERE name = ?
        ''', (json.dumps(permissions), description, role_name))
        conn.commit()
        
        return jsonify({'success': True})

@app.route('/api/admin/roles/<role_name>', methods=['DELETE'])
@require_admin()
def api_delete_role(role_name):
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['super_admin', 'admin']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    system_roles = ['super_admin', 'admin']
    if role_name in system_roles:
        return jsonify({'error': f'Роль "{role_name}" является системной и не может быть удалена'}), 400
    
    with get_db() as conn:
        admins_with_role = conn.execute(
            'SELECT COUNT(*) as count FROM admins WHERE role = ?',
            (role_name,)
        ).fetchone()
        
        if admins_with_role['count'] > 0:
            return jsonify({'error': f'Роль используется {admins_with_role["count"]} администратором(ами). Сначала измените их роли.'}), 400
        
        conn.execute('DELETE FROM roles WHERE name = ?', (role_name,))
        conn.commit()
        
        return jsonify({'success': True})

# Маршрут /admin/manage_rooms перенесен в routes/admin_pages_routes.py

@app.route('/api/admin/rooms', methods=['GET'])
@require_admin()
def api_list_rooms():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['super_admin', 'admin', 'vospitatel']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    from datetime import datetime
    now = datetime.now()
    if now.month == 1:
        payment_month = f"{now.year - 1}-12"
    else:
        payment_month = f"{now.year}-{now.month - 1:02d}"
    
    month = request.args.get('month', payment_month)
    
    with get_db() as conn:
        rooms = conn.execute('''
            SELECT id, building, entrance, room_number, capacity, created_at
            FROM rooms 
            ORDER BY building, entrance, room_number
        ''').fetchall()
        
        result = []
        for room in rooms:
            room_building = (room['building'] or '').strip()
            room_entrance = (room['entrance'] or '').strip()
            room_number = (room['room_number'] or '').strip()
            
            students = conn.execute('''
                SELECT e.id, e.fio, tg.tg_user_id, tg.tg_username
                FROM employees e
                LEFT JOIN tg_users tg ON e.id = tg.employee_id
                WHERE TRIM(COALESCE(e.building, '')) = TRIM(COALESCE(?, ''))
                AND TRIM(COALESCE(e.entrance, '')) = TRIM(COALESCE(?, ''))
                AND TRIM(COALESCE(e.room_number, '')) = TRIM(COALESCE(?, ''))
                ORDER BY e.fio
            ''', (room_building, room_entrance, room_number)).fetchall()
            
            students_list = []
            for student in students:
                payment = conn.execute('''
                    SELECT id, status, amount, payment_date
                    FROM dormitory_payments
                    WHERE employee_id = ? AND payment_month = ? AND status = 'accepted'
                ''', (student['id'], month)).fetchone()
                
                paid = payment is not None
                students_list.append({
                    'id': student['id'],
                    'fio': student['fio'],
                    'tg_user_id': student['tg_user_id'],
                    'tg_username': student['tg_username'],
                    'paid': paid,
                    'payment_date': payment['payment_date'] if payment else None
                })
            
            result.append({
                'id': room['id'],
                'building': room['building'],
                'entrance': room['entrance'],
                'room_number': room['room_number'],
                'capacity': room['capacity'],
                'students_count': len(students_list),
                'students': students_list,
                'created_at': room['created_at']
            })
        
        return jsonify({'success': True, 'rooms': result, 'month': month})

@app.route('/api/admin/rooms', methods=['POST'])
@require_admin()
def api_create_room():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['super_admin', 'admin', 'vospitatel']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    data = request.json
    building = data.get('building', '').strip()
    entrance = data.get('entrance', '').strip()
    room_number = data.get('room_number', '').strip()
    capacity = data.get('capacity', 1)
    
    if not building or not entrance or not room_number:
        return jsonify({'error': 'Корпус, подъезд и номер комнаты обязательны'}), 400
    
    try:
        capacity = int(capacity)
        if capacity < 1 or capacity > 4:
            return jsonify({'error': 'Количество мест должно быть от 1 до 4 (максимум 4 проживающих)'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Некорректное количество мест'}), 400
    
    with get_db() as conn:
        existing = conn.execute(
            'SELECT id FROM rooms WHERE building = ? AND entrance = ? AND room_number = ?',
            (building, entrance, room_number)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Комната с такими параметрами уже существует'}), 400
        
        conn.execute('''
            INSERT INTO rooms (building, entrance, room_number, capacity)
            VALUES (?, ?, ?, ?)
        ''', (building, entrance, room_number, capacity))
        conn.commit()
        
        return jsonify({'success': True})

# Маршрут /api/admin/rooms/<int:room_id> перенесен в routes/room_routes.py
# Количество мест теперь определяется через категорию проживания

@app.route('/api/admin/rooms/<int:room_id>', methods=['DELETE'])
@require_admin()
def api_delete_room(room_id):
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['super_admin', 'admin', 'vospitatel']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    with get_db() as conn:
        room = conn.execute(
            'SELECT building, entrance, room_number FROM rooms WHERE id = ?',
            (room_id,)
        ).fetchone()
        
        if not room:
            return jsonify({'error': 'Комната не найдена'}), 404
        
        students_count = conn.execute(
            'SELECT COUNT(*) as count FROM employees WHERE building = ? AND entrance = ? AND room_number = ?',
            (room['building'], room['entrance'], room['room_number'])
        ).fetchone()['count']
        
        if students_count > 0:
            return jsonify({'error': f'В комнате проживает {students_count} студент(ов). Сначала переместите их в другие комнаты.'}), 400
        
        conn.execute('DELETE FROM rooms WHERE id = ?', (room_id,))
        conn.commit()
        
        return jsonify({'success': True})

@app.route('/api/admin/rooms/send_payment_reminders', methods=['POST'])
@require_admin()
def api_send_payment_reminders():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['super_admin', 'admin', 'vospitatel']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    data = request.json
    room_id = data.get('room_id')
    student_ids = data.get('student_ids', [])
    
    from datetime import datetime
    now = datetime.now()
    if now.month == 1:
        payment_month = f"{now.year - 1}-12"
    else:
        payment_month = f"{now.year}-{now.month - 1:02d}"
    
    month_names = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    month_name = month_names.get(payment_month.split('-')[1], payment_month)
    year = payment_month.split('-')[0]
    
    sent_count = 0
    failed_count = 0
    errors = []
    
    with get_db() as conn:
        if room_id:
            room = conn.execute(
                'SELECT building, entrance, room_number, capacity FROM rooms WHERE id = ?',
                (room_id,)
            ).fetchone()
            
            if not room:
                return jsonify({'error': 'Комната не найдена'}), 404
            
            students = conn.execute('''
                SELECT e.id, e.fio, tg.tg_user_id
                FROM employees e
                LEFT JOIN tg_users tg ON e.id = tg.employee_id
                WHERE e.building = ? AND e.entrance = ? AND e.room_number = ?
                AND NOT EXISTS (
                    SELECT 1 FROM dormitory_payments dp
                    WHERE dp.employee_id = e.id 
                    AND dp.payment_month = ?
                    AND dp.status = 'accepted'
                )
            ''', (room['building'], room['entrance'], room['room_number'], payment_month)).fetchall()
            
            student_ids = [s['id'] for s in students]
        
        for student_id in student_ids:
            student = conn.execute('''
                SELECT e.id, e.fio, e.building, e.entrance, e.room_number, tg.tg_user_id, r.capacity
                FROM employees e
                LEFT JOIN tg_users tg ON e.id = tg.employee_id
                LEFT JOIN rooms r ON e.building = r.building AND e.entrance = r.entrance AND e.room_number = r.room_number
                WHERE e.id = ?
            ''', (student_id,)).fetchone()
            
            if not student or not student['tg_user_id']:
                failed_count += 1
                errors.append(f"Студент {student['fio'] if student else student_id}: нет Telegram ID")
                continue
            
            capacity = student['capacity'] if student['capacity'] else 1
            payment_amount = calculate_payment_amount(capacity)
            
            room_str = f"{student['building']}-{student['entrance']}-{student['room_number']}" if student['building'] else "не указана"
            message = (
                f"🔔 *Напоминание об оплате*\n\n"
                f"Добрый день, {student['fio']}!\n\n"
                f"Напоминаем, что необходимо оплатить проживание за *{month_name} {year}*\n\n"
                f"🏠 Комната: {room_str}\n"
                f"💰 Сумма к оплате: {payment_amount} руб.\n\n"
                f"Для оплаты используйте кнопку 💳 Оплатить проживание в главном меню бота.\n"
                f"После оплаты отправьте фото чека."
            )
            
            try:
                send_telegram_notification(student['tg_user_id'], message)
                sent_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Студент {student['fio']}: {str(e)}")
    
    return jsonify({
        'success': True,
        'sent': sent_count,
        'failed': failed_count,
        'errors': errors
    })

@app.route('/api/admin/delete_vacation/<int:emp_id>', methods=['POST'])
@require_permission('manage_vacation')
def api_delete_vacation(emp_id):
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    with get_db() as conn:
        row = conn.execute('SELECT vacation, vacation_history FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Employee not found'}), 404
        
        vacation_text = row['vacation'] or ''
        if not vacation_text:
            return jsonify({'error': 'No vacation to delete'}), 400
        
        history = json.loads(row['vacation_history'] or '[]')
        history.append(vacation_text)
        
        conn.execute('UPDATE employees SET vacation = ?, vacation_history = ? WHERE id = ?', 
                    ('', json.dumps(history), emp_id))
        conn.commit()
    return jsonify({'success': True})

allowed_days_for_week = {
    1: {7, 8},
    2: {14, 15},
    3: {21, 22},
    4: {28, 29}
}

TOKEN_TTL_SECONDS = 10

buildings_entrances_floors_apartments = {
    "8": {
        "entrance_1": {
            "floor_2": ["2355","2356","2357","2358","2359","2360"],
            "floor_3": ["3357","3358","3359","3360","3361","3362"],
            "floor_4": ["4355","4356","4357","4358","4359","4360"],
            "floor_5": ["5357","5358","5359","5360","5361","5362"]
        },
        "entrance_2": {
            "floor_1": ["1057","1058"],
            "floor_2": ["2361","2362","2363","2364","2365","2366","2367"],
            "floor_3": ["3363","3364","3365","3366","3367","3368","3369"],
            "floor_4": ["4361","4362","4363","4364","4365","4366","4367"],
            "floor_5": ["5363","5364","5365","5366","5367","5368","5369"]
        },
        "entrance_3": {
            "floor_1": ["1059"],
            "floor_2": ["2368","2369","2370","2371","2372","2373"],
            "floor_3": ["3370","3371","3372","3373","3374","3375"],
            "floor_4": ["4368","4369","4370","4371","4372","4373"],
            "floor_5": ["5370","5371","5372","5373","5374","5375"]
        },
        "entrance_4": {
            "floor_2": ["2375","2376","2377","2378","2379","2380","2381","2382"],
            "floor_3": ["3377","3378","3379","3380","3381","3382","3383","3384"],
            "floor_4": ["4375","4376","4377","4378","4379","4380","4381","4382"],
            "floor_5": ["5377","5378","5379","5380","5381","5382","5383","5384"]
        }
    },
    "9": {
        "entrance_1": {
            "floor_1": ["1060","1061","1062"],
            "floor_2": ["2382","2383","2384","2385","2386","2387","2388","2389"],
            "floor_3": ["3384","3385","3386","3387","3388","3389","3390","3391"],
            "floor_4": ["4382","4383","4384","4385","4386","4387","4388","4389"],
            "floor_5": ["5384","5385","5386","5387","5388","5389","5390","5391"]
        },
        "entrance_2": {
            "floor_1": ["1063"],
            "floor_2": ["2390","2391","2392","2393","2394","2395"],
            "floor_3": ["3392","3393","3394","3395","3396","3397"],
            "floor_4": ["4390","4391","4392","4393","4394","4395"],
            "floor_5": ["5392","5393","5394","5395","5396","5397"]
        },
        "entrance_3": {
            "floor_2": ["2396","2397","2398","2399","2400","2401"],
            "floor_3": ["3398","3399","3400","3401","3402","3403"],
            "floor_4": ["4396","4397","4398","4399","4400","4401"],
            "floor_5": ["5398","5399","5400","5401","5402","5403"]
        },
        "entrance_4": {
            "floor_1": ["1064"],
            "floor_2": ["2403","2404","2405","2406","2407","2408"],
            "floor_3": ["3405","3406","3407","3408","3409","3410"],
            "floor_4": ["4403","4404","4405","4406","4407","4408"],
            "floor_5": ["5405","5406","5407","5408","5409","5410"]
        }
    }
}

def get_entrance_by_number(building, number):
    
    if not building or not number:
        return ""
    possible_entrances = []
    building_data = buildings_entrances_floors_apartments.get(building, {})
    for entrance_key, floors in building_data.items():
        for floor_numbers in floors.values():
            if number in floor_numbers:
                entrance_num = entrance_key.split("_")[-1]
                possible_entrances.append(entrance_num)
    if len(possible_entrances) == 1:
        return possible_entrances[0]
    return ""

@app.route('/api/get_entrance')
def api_get_entrance():
    
    building = request.args.get('building', '').strip()
    number = request.args.get('number', '').strip()
    if not building or not number:
        return jsonify({'entrance': ''})
    
    entrance = get_entrance_by_number(building, number)
    return jsonify({'entrance': entrance})

@app.route('/api/employee/<int:emp_id>/reports')
def api_employee_reports(emp_id):
    
    month_str = request.args.get('month', '')
    
    if month_str:
        try:
            start_date = datetime.strptime(month_str, "%Y-%m").date()
            start_date = start_date.replace(day=1)
        except:
            pass
            today = date.today()
            start_date = today.replace(day=1)
    else:
        today = date.today()
        start_date = today.replace(day=1)
    
    end_day = calendar.monthrange(start_date.year, start_date.month)[1]
    end_date = start_date.replace(day=end_day)
    
    month_start = start_date.isoformat()
    month_end = end_date.isoformat()
    
    with get_db() as conn:
        scans = conn.execute("""
            SELECT scanned_at 
            FROM scans 
            WHERE employee_id = ? AND scanned_at >= ? AND scanned_at <= ?
            ORDER BY scanned_at DESC
        """, (emp_id, month_start, month_end)).fetchall()
        
        dates_received = []
        for scan in scans:
            try:
                scanned_at_str = scan['scanned_at']
                if 'T' in scanned_at_str or ' ' in scanned_at_str:
                    scanned_at = datetime.fromisoformat(scanned_at_str.replace(' ', 'T'))
                else:
                    scanned_at = datetime.strptime(scanned_at_str, '%Y-%m-%d')
                
                if scanned_at.tzinfo is None:
                    scanned_at = scanned_at.replace(tzinfo=MOSCOW_TZ)
                else:
                    scanned_at = scanned_at.astimezone(MOSCOW_TZ)
                
                dates_received.append({
                    'date': scanned_at.strftime("%d.%m.%Y"),
                    'time': scanned_at.strftime("%H:%M"),
                    'datetime': scanned_at.isoformat(),
                    'full': scanned_at.strftime("%d.%m.%Y %H:%M")
                })
            except Exception as e:
                continue
        
        return jsonify({
            'month': month_str or start_date.strftime("%Y-%m"),
            'period': start_date.strftime("%B %Y"),
            'dates': dates_received,
            'received_count': len(dates_received)
        })

@app.route('/api/bed_linen/add_date_for_all', methods=['POST'])
def api_add_date_for_all():
    
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Необходима авторизация'}), 401
    
    data = request.get_json() or {}
    start_date = data.get('start_date')  # Дата начала в формате "YYYY-MM-DD"
    end_date = data.get('end_date')  # Дата окончания в формате "YYYY-MM-DD"
    
    if not start_date or not end_date:
        return jsonify({
            'success': False,
            'message': 'Необходимо указать дату начала и дату окончания'
        }), 400
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start_dt > end_dt:
            return jsonify({
                'success': False,
                'message': 'Дата начала не может быть позже даты окончания'
            }), 400
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Неверный формат даты. Используйте YYYY-MM-DD'
        }), 400
    
    with get_db() as conn:
        existing = conn.execute("""
            SELECT id FROM bed_linen_dates 
            WHERE is_active = 1 AND (
                (start_date <= ? AND end_date >= ?) OR
                (start_date <= ? AND end_date >= ?) OR
                (start_date >= ? AND end_date <= ?)
            )
        """, (start_date, start_date, end_date, end_date, start_date, end_date)).fetchone()
        
        if existing:
            return jsonify({
                'success': False,
                'message': 'Период пересекается с существующим активным периодом'
            }), 400
        
        conn.execute("""
            INSERT INTO bed_linen_dates (start_date, end_date, is_active)
            VALUES (?, ?, 1)
        """, (start_date, end_date))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Период выдачи белья с {start_date} по {end_date} успешно создан.'
        })

@app.route('/api/bed_linen/list_dates', methods=['GET'])
def api_list_bed_linen_dates():
    
    if not session.get('admin'):
        return jsonify({'error': 'Необходима авторизация'}), 401
    
    today = datetime.now(MOSCOW_TZ).date()
    
    with get_db() as conn:
        periods = conn.execute("""
            SELECT id, start_date, end_date, created_at, is_active
            FROM bed_linen_dates
            ORDER BY start_date DESC
        """).fetchall()
        
        result = []
        for p in periods:
            try:
                start_date = datetime.strptime(p['start_date'], "%Y-%m-%d").date()
                end_date = datetime.strptime(p['end_date'], "%Y-%m-%d").date()
            except:
                start_date = None
                end_date = None
            
            status = 'Неактивен'
            status_class = 'bg-secondary'
            if p['is_active']:
                if start_date and end_date:
                    if today < start_date:
                        status = 'Запланирован'
                        status_class = 'bg-info'
                    elif today > end_date:
                        status = 'Завершен'
                        status_class = 'bg-secondary'
                    else:
                        status = 'Активен'
                        status_class = 'bg-success'
                else:
                    status = 'Активен'
                    status_class = 'bg-success'
            else:
                status = 'Неактивен'
                status_class = 'bg-secondary'
            
            result.append({
                'id': p['id'],
                'start_date': p['start_date'],
                'end_date': p['end_date'],
                'created_at': p['created_at'],
                'is_active': bool(p['is_active']),
                'status': status,
                'status_class': status_class
            })
        
        return jsonify({
            'success': True,
            'dates': result
        })

@app.route('/api/bed_linen/delete_date/<int:date_id>', methods=['DELETE'])
def api_delete_bed_linen_date(date_id):
    
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Необходима авторизация'}), 401
    
    with get_db() as conn:
        conn.execute("DELETE FROM bed_linen_dates WHERE id = ?", (date_id,))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Дата успешно удалена'
        })


@app.route('/bed_linen/token', methods=['GET'])
def api_bed_linen_token():
    
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, token, created_at FROM bed_linen_tokens ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        should_generate = True
        
        if row:
            created_at_str = row[2]
            try:
                created_at = datetime.fromisoformat(created_at_str.replace(' ', 'T'))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=MOSCOW_TZ)
                else:
                    created_at = created_at.astimezone(MOSCOW_TZ)
                
                delta = datetime.now(MOSCOW_TZ) - created_at
                if delta.total_seconds() < TOKEN_TTL_SECONDS:
                    should_generate = False
                    token = row[1]
            except:
                pass
        
        if should_generate:
            token = secrets.token_urlsafe(16)
            cursor.execute("DELETE FROM bed_linen_tokens")
            cursor.execute(
                "INSERT INTO bed_linen_tokens (token, created_at) VALUES (?, ?)",
                (token, datetime.now(MOSCOW_TZ).isoformat())
            )
            conn.commit()
        
        return jsonify({'token': token})

@app.route('/bed_linen/qr')
def generate_qr_bed_linen():
    
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not QRCODE_AVAILABLE:
        return jsonify({'error': 'QR code library not available'}), 500
    
    data = request.args.get('data', '')
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/bed_linen/generate_pdf')
def generate_pdf_bed_linen():
    
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not QRCODE_AVAILABLE:
        return jsonify({'error': 'QR code library not available'}), 500
    
    if not REPORTLAB_AVAILABLE:
        return jsonify({
            'error': 'PDF library not available',
            'message': 'Для работы генерации PDF необходимо установить библиотеку reportlab',
            'instructions': [
                '1. Откройте терминал в папке проекта',
                '2. Выполните команду: pip3 install reportlab',
                '3. Если не работает, попробуйте: python3 -m pip install reportlab',
                '4. После установки ПЕРЕЗАПУСТИТЕ Flask приложение',
                '5. Попробуйте снова сгенерировать PDF'
            ]
        }), 500
    
    token = request.args.get('token', '')
    if not token:
        return jsonify({'error': 'Токен не предоставлен'}), 400
    
    qr_img = qrcode.make(token)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format='PNG')
    qr_buf.seek(0)
    
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=A4)
    width, height = A4
    
    now = datetime.now(MOSCOW_TZ)
    
    cyrillic_font = "Helvetica"
    cyrillic_font_bold = "Helvetica-Bold"
    font_loaded = False
    
    import platform
    system = platform.system()
    
    inter_paths = [
        os.path.join(app.static_folder, 'fonts', 'Inter-Regular.ttf'),
        os.path.join(app.static_folder, 'fonts', 'Inter-Bold.ttf'),
        os.path.join(app.root_path, 'static', 'fonts', 'Inter-Regular.ttf'),
        os.path.join(app.root_path, 'static', 'fonts', 'Inter-Bold.ttf'),
        'static/fonts/Inter-Regular.ttf',
        'static/fonts/Inter-Bold.ttf',
    ]
    
    if system == 'Darwin':  # macOS
        inter_paths.extend([
            '/Library/Fonts/Inter-Regular.ttf',
            '/Library/Fonts/Inter-Bold.ttf',
            os.path.expanduser('~/Library/Fonts/Inter-Regular.ttf'),
            os.path.expanduser('~/Library/Fonts/Inter-Bold.ttf'),
        ])
    elif system == 'Linux':
        inter_paths.extend([
            '/usr/share/fonts/truetype/inter/Inter-Regular.ttf',
            '/usr/share/fonts/truetype/inter/Inter-Bold.ttf',
            '/usr/share/fonts/opentype/inter/Inter-Regular.otf',
            '/usr/share/fonts/opentype/inter/Inter-Bold.otf',
        ])
    else:  # Windows
        inter_paths.extend([
            'C:/Windows/Fonts/inter.ttf',
            'C:/Windows/Fonts/INTER.TTF',
        ])
    
    inter_regular_path = None
    inter_bold_path = None
    
    for font_path in inter_paths:
        if os.path.exists(font_path):
            is_bold = 'bold' in font_path.lower() and 'regular' not in font_path.lower()
            is_regular = 'regular' in font_path.lower() or (not is_bold and 'bold' not in font_path.lower())
            
            if is_regular and not is_bold:
                try:
                    pdfmetrics.registerFont(TTFont('Inter', font_path))
                    cyrillic_font = 'Inter'
                    inter_regular_path = font_path
                    font_loaded = True
                    break
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    continue
    
    for font_path in inter_paths:
        if os.path.exists(font_path):
            is_bold = 'bold' in font_path.lower()
            if is_bold:
                try:
                    pdfmetrics.registerFont(TTFont('InterBold', font_path))
                    cyrillic_font_bold = 'InterBold'
                    inter_bold_path = font_path
                    break
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    continue
    
    if font_loaded and inter_regular_path and not inter_bold_path:
        try:
            pdfmetrics.registerFont(TTFont('InterBold', inter_regular_path))
            cyrillic_font_bold = 'InterBold'
        except:
            pass
            cyrillic_font_bold = 'Inter'
    
    if not font_loaded:
        if system == 'Darwin':  # macOS
            arial_paths = [
                '/System/Library/Fonts/Supplemental/Arial.ttf',
                '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                '/Library/Fonts/Arial.ttf',
                '/System/Library/Fonts/Arial.ttf'
            ]
            for arial_path in arial_paths:
                if os.path.exists(arial_path):
                    try:
                        pdfmetrics.registerFont(TTFont('CyrillicFont', arial_path))
                        pdfmetrics.registerFont(TTFont('CyrillicFontBold', arial_path))
                        cyrillic_font = 'CyrillicFont'
                        cyrillic_font_bold = 'CyrillicFontBold'
                        font_loaded = True
                        break
                    except Exception as e:
                        continue
            
            if font_loaded:
                bold_paths = [p for p in arial_paths if 'Bold' in p]
                for bold_path in bold_paths:
                    if os.path.exists(bold_path):
                        try:
                            pdfmetrics.registerFont(TTFont('CyrillicFontBold', bold_path))
                            break
                        except:
                            pass
    
    elif system == 'Linux':
        linux_fonts = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
        ]
        for font_path in linux_fonts:
            if os.path.exists(font_path):
                try:
                    if 'Bold' in font_path:
                        pdfmetrics.registerFont(TTFont('CyrillicFontBold', font_path))
                        cyrillic_font_bold = 'CyrillicFontBold'
                        if not font_loaded:
                            pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
                            cyrillic_font = 'CyrillicFont'
                            font_loaded = True
                    else:
                        pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
                        cyrillic_font = 'CyrillicFont'
                        font_loaded = True
                        pdfmetrics.registerFont(TTFont('CyrillicFontBold', font_path))
                        cyrillic_font_bold = 'CyrillicFontBold'
                    if font_loaded:
                        break
                except Exception:
                    continue
    
    else:  # Windows
        windows_fonts = [
            'C:/Windows/Fonts/arial.ttf',
            'C:/Windows/Fonts/ARIAL.TTF',
            'C:/Windows/Fonts/arialbd.ttf'  # Arial Bold
        ]
        for font_path in windows_fonts:
            if os.path.exists(font_path):
                try:
                    if 'bd' in font_path.lower() or 'bold' in font_path.lower():
                        pdfmetrics.registerFont(TTFont('CyrillicFontBold', font_path))
                        cyrillic_font_bold = 'CyrillicFontBold'
                    else:
                        pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
                        cyrillic_font = 'CyrillicFont'
                        pdfmetrics.registerFont(TTFont('CyrillicFontBold', font_path))
                        cyrillic_font_bold = 'CyrillicFontBold'
                        font_loaded = True
                except Exception:
                    continue
    
    if not font_loaded:
        montserrat_paths = [
            os.path.join(app.static_folder, 'fonts', 'Montserrat-Regular.ttf'),
            os.path.join(app.static_folder, 'fonts', 'Montserrat.ttf'),
            'static/fonts/Montserrat-Regular.ttf',
            'static/fonts/Montserrat.ttf'
        ]
        for font_path in montserrat_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
                    pdfmetrics.registerFont(TTFont('CyrillicFontBold', font_path))
                    cyrillic_font = 'CyrillicFont'
                    cyrillic_font_bold = 'CyrillicFontBold'
                    font_loaded = True
                    break
                except Exception:
                    continue
    
    if not font_loaded:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
            cyrillic_font = 'HeiseiMin-W3'
            cyrillic_font_bold = 'HeiseiMin-W3'
            font_loaded = True
        except Exception:
            try:
                pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
                cyrillic_font = 'HeiseiKakuGo-W5'
                cyrillic_font_bold = 'HeiseiKakuGo-W5'
                font_loaded = True
            except Exception:
                pass
    use_cyrillic = (cyrillic_font not in ["Helvetica", "Helvetica-Bold"])
    
    c.setFillColorRGB(0, 0, 0)
    
    c.setStrokeColorRGB(0, 0, 0)
    
    logo_paths = [
        os.path.abspath(os.path.join(app.root_path, 'static', 'logo.png')),
        os.path.abspath(os.path.join(app.static_folder, 'logo.png')),
        os.path.join(app.root_path, 'static', 'logo.png'),
        os.path.join(app.static_folder, 'logo.png'),
        'static/logo.png',
        os.path.abspath(os.path.join(app.root_path, 'static', 'logo.PNG')),
        os.path.join(app.root_path, 'static', 'logo.PNG'),
    ]
    
    logo_height = 0
    logo_loaded = False
    logo_top_y = height - 30  # 30px отступ от верха
    
    for logo_path in logo_paths:
        if os.path.exists(logo_path):
            try:
                try:
                    from PIL import Image
                    img = Image.open(logo_path)
                    img_width, img_height = img.size
                except ImportError:
                    img_width, img_height = 200, 100
                except Exception as e:
                    continue
                
                max_logo_width = 200
                if img_width > max_logo_width:
                    logo_width = max_logo_width
                    logo_height = int(img_height * (max_logo_width / img_width))
                else:
                    logo_width = img_width
                    logo_height = img_height
                
                logo_x = (width - logo_width) / 2
                
                logo_bottom_y = logo_top_y - logo_height
                
                
                try:
                    from PIL import Image
                    img_file = Image.open(logo_path)
                    
                    if img_file.mode in ('RGBA', 'LA', 'P'):
                        rgb_img = Image.new('RGB', img_file.size, (255, 255, 255))
                        if img_file.mode == 'P':
                            img_file = img_file.convert('RGBA')
                        rgb_img.paste(img_file, mask=img_file.split()[-1] if img_file.mode in ('RGBA', 'LA') else None)
                        img_file = rgb_img
                    elif img_file.mode != 'RGB':
                        img_file = img_file.convert('RGB')
                    
                    img_reader = ImageReader(img_file)
                    c.drawImage(img_reader, logo_x, logo_bottom_y, width=logo_width, height=logo_height)
                except Exception as e1:
                    try:
                        c.drawImage(logo_path, logo_x, logo_bottom_y, width=logo_width, height=logo_height)
                    except Exception as e2:
                        try:
                            c.drawImage(ImageReader(logo_path), logo_x, logo_bottom_y, width=logo_width, height=logo_height)
                        except Exception as e3:
                            import traceback
                            traceback.print_exc()
                            continue
                
                logo_y = logo_bottom_y - 40  # 40px отступ между логотипом и заголовком
                logo_loaded = True
                break
            except Exception as e:
                import traceback
                traceback.print_exc()
                continue
    
    if not logo_loaded:
        logo_y = height - 140  # Смещаем ниже
    
    if use_cyrillic:
        try:
            c.setFont(cyrillic_font_bold, 40)
            title = "Выдача постельного белья"
            title_width = c.stringWidth(title, cyrillic_font_bold, 40)
        except:
            pass
            c.setFont("Helvetica-Bold", 40)
            title = "BED LINEN ISSUANCE"
            title_width = c.stringWidth(title, "Helvetica-Bold", 40)
    else:
        c.setFont("Helvetica-Bold", 40)
        title = "BED LINEN ISSUANCE"
        title_width = c.stringWidth(title, "Helvetica-Bold", 40)
    c.drawString((width - title_width) / 2, logo_y - 30, title)
    
    if use_cyrillic:
        try:
            c.setFont(cyrillic_font_bold, 22)
            date_str = f"Дата: {now.strftime('%d.%m.%Y %H:%M')}"
            date_width = c.stringWidth(date_str, cyrillic_font_bold, 22)
        except:
            pass
            c.setFont("Helvetica-Bold", 22)
            date_str = f"Date: {now.strftime('%d.%m.%Y %H:%M')}"
            date_width = c.stringWidth(date_str, "Helvetica-Bold", 22)
    else:
        c.setFont("Helvetica-Bold", 22)
        date_str = f"Date: {now.strftime('%d.%m.%Y %H:%M')}"
        date_width = c.stringWidth(date_str, "Helvetica-Bold", 22)
    
    date_y = logo_y - 70 if logo_loaded else height - 190  # Увеличенный отступ от заголовка
    c.drawString((width - date_width) / 2, date_y, date_str)
    
    qr_size = 300
    qr_x = (width - qr_size) / 2
    qr_y = date_y - 320 if logo_loaded else height - 480
    
    qr_buf.seek(0)
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size)
    
    code_y = qr_y - 100
    if use_cyrillic:
        try:
            c.setFont(cyrillic_font_bold, 26)
            code_label = "Код для получения:"
            code_label_width = c.stringWidth(code_label, cyrillic_font_bold, 26)
        except:
            pass
            c.setFont("Helvetica-Bold", 26)
            code_label = "CODE FOR RECEIVING:"
            code_label_width = c.stringWidth(code_label, "Helvetica-Bold", 26)
    else:
        c.setFont("Helvetica-Bold", 26)
        code_label = "CODE FOR RECEIVING:"
        code_label_width = c.stringWidth(code_label, "Helvetica-Bold", 26)
    c.drawString((width - code_label_width) / 2, code_y, code_label)
    
    c.setFont("Courier-Bold", 30)
    token_width = c.stringWidth(token, "Courier-Bold", 30)
    c.drawString((width - token_width) / 2, code_y - 50, token)
    
    instruction_y = code_y - 120
    if use_cyrillic:
        try:
            c.setFont(cyrillic_font, 20)
            instruction1 = "Для получения белья отсканируйте QR-код"
            instruction1_width = c.stringWidth(instruction1, cyrillic_font, 20)
            c.drawString((width - instruction1_width) / 2, instruction_y, instruction1)
            
            instruction2 = "или введите код вручную"
            instruction2_width = c.stringWidth(instruction2, cyrillic_font, 20)
            c.drawString((width - instruction2_width) / 2, instruction_y - 40, instruction2)
        except:
            pass
            c.setFont("Helvetica", 20)
            instruction1 = "Scan QR code to receive bed linen"
            instruction1_width = c.stringWidth(instruction1, "Helvetica", 20)
            c.drawString((width - instruction1_width) / 2, instruction_y, instruction1)
            
            instruction2 = "or enter code manually"
            instruction2_width = c.stringWidth(instruction2, "Helvetica", 20)
            c.drawString((width - instruction2_width) / 2, instruction_y - 40, instruction2)
    else:
        c.setFont("Helvetica", 20)
        instruction1 = "Scan QR code to receive bed linen"
        instruction1_width = c.stringWidth(instruction1, "Helvetica", 20)
        c.drawString((width - instruction1_width) / 2, instruction_y, instruction1)
        
        instruction2 = "or enter code manually"
        instruction2_width = c.stringWidth(instruction2, "Helvetica", 20)
        c.drawString((width - instruction2_width) / 2, instruction_y - 40, instruction2)
    
    c.setFillColorRGB(0.5, 0.5, 0.5)  # Серый цвет для полупрозрачности
    if use_cyrillic:
        try:
            c.setFont(cyrillic_font, 12)  # Уменьшенный шрифт
            footer = "Создано в АСПиРС"
            footer_width = c.stringWidth(footer, cyrillic_font, 12)
            c.drawString((width - footer_width) / 2, 40, footer)  # Ниже на странице
        except:
            pass
            c.setFont("Helvetica", 12)
            footer = "Created in ASPIRS"
            footer_width = c.stringWidth(footer, "Helvetica", 12)
            c.drawString((width - footer_width) / 2, 40, footer)
    else:
        c.setFont("Helvetica", 12)
        footer = "Created in ASPIRS"
        footer_width = c.stringWidth(footer, "Helvetica", 12)
        c.drawString((width - footer_width) / 2, 40, footer)
    
    c.setFillColorRGB(0, 0, 0)
    
    c.save()
    pdf_buf.seek(0)
    
    from flask import Response
    from urllib.parse import quote
    
    filename = f'Выдача_постельного_белья_{now.strftime("%Y%m%d_%H%M%S")}.pdf'
    # Правильно кодируем имя файла для заголовка Content-Disposition
    # Используем RFC 2231 формат для поддержки кириллицы
    encoded_filename = quote(filename.encode('utf-8'))
    content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
    
    return Response(
        pdf_buf.getvalue(),
        mimetype='application/pdf',
        headers={
            'Content-Disposition': content_disposition
        }
    )

@app.route('/bed_linen/verify', methods=['POST'])
def api_bed_linen_verify():
    
    data = request.get_json(force=True)
    employee_id = data.get('employee_id')
    token = data.get('token')
    
    if not employee_id or not token:
        return jsonify({'status': 'error', 'message': 'Неверные данные.'}), 400
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bed_linen_tokens WHERE token=?", (token,))
        t = cursor.fetchone()
        if not t:
            return jsonify({'status': 'error', 'message': 'Код недействителен.'}), 403
        
        now = datetime.now(MOSCOW_TZ)
        today_str = now.date().isoformat()
        
        period = cursor.execute("""
            SELECT id FROM bed_linen_dates
            WHERE is_active = 1 AND start_date <= ? AND end_date >= ?
            ORDER BY start_date DESC
            LIMIT 1
        """, (today_str, today_str)).fetchone()
        
        if not period:
            return jsonify({
                'status': 'error',
                'message': 'Нет активного периода выдачи белья на сегодня.'
            }), 403
        
        period_id = period['id']
        
        student = cursor.execute("SELECT fio FROM employees WHERE id = ?", (employee_id,)).fetchone()
        
        student_fio = student['fio'] if student else 'Студент'
        
        existing_scan = cursor.execute("SELECT id FROM scans WHERE employee_id = ? AND period_id = ?", (employee_id, period_id)).fetchone()
        
        if existing_scan:
            return jsonify({
                'status': 'error',
                'message': f'{student_fio} уже получал белье в этот период.'
            }), 403
        
        scanned_at = now.isoformat(sep=' ', timespec='seconds')
        cursor.execute(
            "INSERT INTO scans (employee_id, token, scanned_at, period_id) VALUES (?, ?, ?, ?)",
            (employee_id, token, scanned_at, period_id)
        )
        
        cursor.execute("DELETE FROM bed_linen_tokens WHERE token=?", (token,))
        
        conn.commit()
        
        scanned_at_formatted = now.strftime("%d.%m.%Y %H:%M:%S")
        return jsonify({
            'status': 'success',
            'message': f'Получение зарегистрировано в {scanned_at_formatted}'
        })



@app.route('/bed_linen/scan')
def bed_linen_scan():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('admin_login'))
    
    if not has_permission(admin_id, 'scan_qr'):
        return render_template('no_access.html', 
            message='У вас нет доступа к сканеру QR-кодов.')
    
    return render_template('bed_linen_scan.html')

@app.route('/bed_linen/manage')
def bed_linen_manage():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('admin_login'))
    
    role = get_admin_role(admin_id)
    if role not in ['admin', 'super_admin', 'vospitatel']:
        return render_template('no_access.html', 
            message='У вас нет доступа к этой странице'), 403
    
    return render_template('bed_linen_manage.html')

@app.route('/bed_linen/report')
def bed_linen_report():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('admin_login'))
    
    role = get_admin_role(admin_id)
    if role not in ['admin', 'super_admin', 'vospitatel', 'razmeshenie']:
        return render_template('no_access.html', 
            message='У вас нет доступа к этой странице'), 403
    
    month_str = request.args.get('month', '')
    
    if month_str:
        try:
            start_date = datetime.strptime(month_str, "%Y-%m").date()
            start_date = start_date.replace(day=1)
        except:
            pass
            today = date.today()
            start_date = today.replace(day=1)
    else:
        today = date.today()
        start_date = today.replace(day=1)
    
    end_day = calendar.monthrange(start_date.year, start_date.month)[1]
    end_date = start_date.replace(day=end_day)
    
    selected_month = start_date.strftime("%Y-%m")
    month_start = start_date.isoformat()
    month_end = end_date.isoformat()
    
    with get_db() as conn:
        first_scan = conn.execute("SELECT MIN(scanned_at) AS first_scan FROM scans").fetchone()
        if first_scan and first_scan[0]:
            try:
                scan_date = first_scan[0]
                if 'T' in scan_date or ' ' in scan_date:
                    first_scan_date = scan_date.split('T')[0].split(' ')[0]
                else:
                    first_scan_date = scan_date[:10]
            except:
                first_scan_date = date.today().isoformat()
        else:
            first_scan_date = date.today().isoformat()
        
        periods_raw = conn.execute("""
            SELECT id, start_date, end_date, is_active
            FROM bed_linen_dates
            WHERE (start_date >= ? AND start_date <= ?) 
               OR (end_date >= ? AND end_date <= ?)
               OR (start_date <= ? AND end_date >= ?)
            ORDER BY start_date ASC
        """, (month_start, month_end, month_start, month_end, month_start, month_end)).fetchall()
        
        today = datetime.now(MOSCOW_TZ).date()
        periods = []
        for period in periods_raw:
            period_id = period['id']
            start_date_str = period['start_date']
            end_date_str = period['end_date']
            
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                start_formatted = start_date.strftime("%d.%m.%Y")
            except:
                start_formatted = start_date_str
                start_date = None
            
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                end_formatted = end_date.strftime("%d.%m.%Y")
            except:
                end_formatted = end_date_str
                end_date = None
            
            status = 'Активен'
            status_class = 'bg-success'
            if start_date and end_date:
                if today < start_date:
                    status = 'Запланирован'
                    status_class = 'bg-info'
                elif today > end_date:
                    status = 'Завершен'
                    status_class = 'bg-secondary'
            
            periods.append({
                'id': period_id,
                'start_date': start_formatted,
                'end_date': end_formatted,
                'status': status,
                'status_class': status_class
            })
        
        # Ищем последний прошедший период среди ВСЕХ периодов в базе
        # Период считается прошедшим, если его дата окончания строго меньше сегодняшней
        # (период, который заканчивается сегодня, еще не считается прошедшим)
        today_str = today.isoformat()
        all_periods_for_last = conn.execute("""
            SELECT id, start_date, end_date, is_active
            FROM bed_linen_dates
            WHERE end_date < ?
            ORDER BY end_date DESC
            LIMIT 1
        """, (today_str,)).fetchone()
        
        last_passed_period = None
        if all_periods_for_last:
            last_passed_period = dict(all_periods_for_last)
            if 'id' in last_passed_period:
                last_passed_period['id'] = int(last_passed_period['id'])
        
        # Получаем всех студентов (исключаем местных)
        employees_raw = conn.execute("""
            SELECT id, fio, room_number, building, entrance
            FROM employees
            WHERE COALESCE(is_local, 0) = 0
            ORDER BY fio
        """).fetchall()
        
        # Получаем информацию о том, кто получил белье в каких периодах
        period_ids = [p['id'] for p in periods]
        scans = []
        if period_ids:
            placeholders = ','.join(['?'] * len(period_ids))
            scans = conn.execute(f"""
                SELECT employee_id, period_id
                FROM scans
                WHERE period_id IN ({placeholders})
            """, period_ids).fetchall()
        
        student_periods = {}
        for scan in scans:
            emp_id = scan['employee_id']
            period_id = scan['period_id']
            if emp_id not in student_periods:
                student_periods[emp_id] = []
            if period_id not in student_periods[emp_id]:
                student_periods[emp_id].append(period_id)
        
        period_ids = [p['id'] for p in periods]
        
        employees_with_missing = []
        employees_with_all = []
        
        for emp in employees_raw:
            emp_id = emp['id']
            emp_periods = student_periods.get(emp_id, [])
            
            missing_periods = [pid for pid in period_ids if pid not in emp_periods]
            
            if missing_periods:
                employees_with_missing.append(emp)
            else:
                employees_with_all.append(emp)
        
        employees = employees_with_missing + employees_with_all
        
        # Подсчитываем статистику только для последнего прошедшего периода
        total_students = len(employees)
        period_stats = {}
        
        if last_passed_period:
            period_id = last_passed_period['id']
            # Дополнительная проверка: убеждаемся, что период действительно прошедший
            period_end_date = datetime.strptime(last_passed_period['end_date'], '%Y-%m-%d').date()
            if period_end_date < today:  # Период должен быть строго в прошлом
                # Получаем информацию о том, кто получил белье в последнем прошедшем периоде
                scans_for_last_period = conn.execute("""
                    SELECT employee_id
                    FROM scans
                    WHERE period_id = ?
                """, (period_id,)).fetchall()
                
                received_employee_ids = {dict(row)['employee_id'] for row in scans_for_last_period}
                received_count = len(received_employee_ids)
                not_received_count = total_students - received_count
                percentage = (received_count / total_students * 100) if total_students > 0 else 0
                
                period_stats[period_id] = {
                    'received': received_count,
                    'not_received': not_received_count,
                    'percentage': round(percentage, 1)
                }
            else:
                # Если период еще не прошел, не показываем статистику
                last_passed_period = None
        
        # Получаем все периоды для определения доступных месяцев/лет
        all_periods_rows = conn.execute("""
            SELECT DISTINCT start_date, end_date
            FROM bed_linen_dates
            ORDER BY start_date ASC
        """).fetchall()
        
        # Извлекаем уникальные месяцы и годы из всех периодов
        available_months = set()
        for period_row in all_periods_rows:
            period_dict = dict(period_row)
            start_date_str = period_dict['start_date']
            end_date_str = period_dict['end_date']
            
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
                
                current = start_dt.replace(day=1)
                while current <= end_dt:
                    month_key = f"{current.year}-{current.month:02d}"
                    available_months.add(month_key)
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)
            except:
                pass
        
        available_months_list = sorted(list(available_months))
        if selected_month and selected_month not in available_months_list:
            available_months_list.append(selected_month)
            available_months_list = sorted(available_months_list)
        
        return render_template(
            'bed_linen_report.html',
            admin_role=role,
            employees=employees,
            periods=periods,
            student_periods=student_periods,
            selected_month=selected_month,
            available_months=available_months_list,
            total_students=total_students,
            period_stats=period_stats,
            last_passed_period=last_passed_period
        )



@app.route('/api/admin/tg_users', methods=['GET'])
def api_admin_tg_users():
    
    if not session.get('admin_id'):
        return jsonify({'error': 'Необходима авторизация'}), 401
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                e.id as employee_id,
                e.fio,
                e.phone,
                e.group_name,
                e.building,
                e.entrance,
                e.room_number,
                e.tg_username as student_tg_username,
                tg.tg_user_id,
                tg.tg_username as tg_username
            FROM employees e
            LEFT JOIN tg_users tg ON e.id = tg.employee_id
            ORDER BY e.fio
        """)
        students = cursor.fetchall()
        
        result = []
        for student in students:
            is_registered = student['tg_user_id'] is not None
            tg_username = student['tg_username'] or 'Не указан'
            student_tg_username = student['student_tg_username'] or '-'
            
            username_match = False
            if is_registered and student_tg_username != '-':
                tg_normalized = tg_username.lstrip('@').lower() if tg_username != 'Не указан' else ''
                student_normalized = student_tg_username.lstrip('@').lower()
                username_match = tg_normalized == student_normalized
            
            result.append({
                'employee_id': student['employee_id'],
                'fio': student['fio'] or '-',
                'phone': student['phone'] or '-',
                'group_name': student['group_name'] or '-',
                'building': student['building'] or '-',
                'entrance': student['entrance'] or '-',
                'room_number': student['room_number'] or '-',
                'room': f"{student['building'] or ''}-{student['entrance'] or ''}-{student['room_number'] or ''}" if student['building'] else '-',
                'student_tg_username': student_tg_username,
                'tg_user_id': student['tg_user_id'],
                'tg_username': tg_username,
                'is_registered': is_registered,
                'username_match': username_match
            })
        
        return jsonify({
            'success': True,
            'users': result
        })

@app.route('/api/admin/tg_users/export', methods=['GET'])
def api_admin_tg_users_export():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Необходима авторизация'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['admin', 'super_admin']:
        return jsonify({'error': 'У вас нет прав для экспорта данных'}), 403
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    e.id as employee_id,
                    e.fio,
                    e.phone,
                    e.group_name,
                    e.building,
                    e.entrance,
                    e.room_number,
                    e.tg_username as student_tg_username,
                    tg.tg_user_id,
                    tg.tg_username as tg_username
                FROM employees e
                LEFT JOIN tg_users tg ON e.id = tg.employee_id
                ORDER BY e.fio
            """)
            students = cursor.fetchall()
            
            data = []
            for student in students:
                is_registered = student['tg_user_id'] is not None
                tg_username = student['tg_username'] or 'Не указан'
                student_tg_username = student['student_tg_username'] or '-'
                
                username_match = False
                if is_registered and student_tg_username != '-':
                    tg_normalized = tg_username.lstrip('@').lower() if tg_username != 'Не указан' else ''
                    student_normalized = student_tg_username.lstrip('@').lower()
                    username_match = tg_normalized == student_normalized
                
                if not is_registered:
                    status = 'Не зарегистрирован'
                elif username_match:
                    status = 'Зарегистрирован'
                else:
                    status = '⚠ Несоответствие username'
                
                data.append({
                    'ID Студента': student['employee_id'],
                    'ФИО': student['fio'] or '-',
                    'Телефон': student['phone'] or '-',
                    'Группа': student['group_name'] or '-',
                    'Корпус': student['building'] or '-',
                    'Подъезд': student['entrance'] or '-',
                    'Комната': student['room_number'] or '-',
                    'Комната (полная)': f"{student['building'] or ''}-{student['entrance'] or ''}-{student['room_number'] or ''}" if student['building'] else '-',
                    'Username в базе': student_tg_username,
                    'ID Telegram': student['tg_user_id'] or '-',
                    'Username Telegram': tg_username if is_registered else '-',
                    'Статус': status
                })
            
            df = pd.DataFrame(data)
            
            buf = io.BytesIO()
            df.to_excel(buf, index=False, engine='openpyxl')
            buf.seek(0)
            
            filename = f'telegram_users_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
            return send_file(
                buf,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
    except Exception as e:
        return jsonify({'error': f'Ошибка экспорта: {str(e)}'}), 500

@app.route('/api/admin/tg_users/import', methods=['POST'])
def api_admin_tg_users_import():
    
    if not session.get('admin_id'):
        return jsonify({'error': 'Необходима авторизация'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не предоставлен'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    def allowed_file_excel(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['xlsx', 'xls']
    
    if not allowed_file_excel(file.filename):
        return jsonify({'error': 'Неверный формат файла. Используйте .xlsx или .xls'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config.get('UPLOAD_FOLDER_EXCEL', 'uploads'), filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)
    
    try:
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'xlsx'
        engine = None
        if file_ext == 'xls':
            try:
                import xlrd
                engine = 'xlrd'
            except ImportError:
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'error': 'Для чтения .xls файлов требуется библиотека xlrd. Установите: pip install xlrd'}), 400
        else:
            engine = 'openpyxl'
        
        try:
            df = pd.read_excel(filepath, engine=engine)
        except Exception as read_error:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'Ошибка чтения файла: {str(read_error)}'}), 400
        
        if df.empty:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': 'Файл пуст'}), 400
        
        def normalize_header(header):
            if pd.isna(header):
                return ''
            header_str = str(header).strip().lower()
            mapping = {
                'фио': 'fio',
                'fio': 'fio',
                'username': 'tg_username',
                'tg_username': 'tg_username',
                'telegram username': 'tg_username',
                'telegram_username': 'tg_username',
                'тг username': 'tg_username',
                'тг_username': 'tg_username',
                'id': 'id',
                'employee_id': 'id'
            }
            return mapping.get(header_str, header_str)
        
        df.columns = [normalize_header(str(col)) for col in df.columns]
        
        if 'fio' not in df.columns and 'id' not in df.columns:
            return jsonify({'error': 'Файл должен содержать колонку "ФИО" или "ID"'}), 400
        
        if 'tg_username' not in df.columns:
            return jsonify({'error': 'Файл должен содержать колонку "tg_username" или "Username"'}), 400
        
        not_found = 0
        skipped = 0  # Пропущено (username уже идентичен)
        to_replace = []  # Записи, требующие подтверждения замены
        inserted = 0  # Вставлено (username не было)
        errors = []
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            for idx, row in df.iterrows():
                try:
                    fio = str(row.get('fio', '')).strip() if pd.notna(row.get('fio')) else ''
                    employee_id = int(row.get('id')) if pd.notna(row.get('id')) and str(row.get('id')).strip() else None
                    tg_username = str(row.get('tg_username', '')).strip() if pd.notna(row.get('tg_username')) else ''
                    
                    if not tg_username:
                        continue
                    
                    tg_username = tg_username.lstrip('@').strip()
                    
                    if employee_id:
                        cursor.execute("SELECT id, fio, tg_username FROM employees WHERE id = ?", (employee_id,))
                        student = cursor.fetchone()
                    elif fio:
                        cursor.execute("SELECT id, fio, tg_username FROM employees WHERE LOWER(fio) = LOWER(?)", (fio,))
                        student = cursor.fetchone()
                    else:
                        errors.append(f"Строка {idx + 2}: не указан ID или ФИО")
                        continue
                    
                    if not student:
                        not_found += 1
                        errors.append(f"Строка {idx + 2}: студент не найден (ФИО: {fio}, ID: {employee_id})")
                        continue
                    
                    try:
                        current_username = student['tg_username'] if student['tg_username'] else ''
                    except (KeyError, TypeError):
                        current_username = ''
                    current_username = current_username.strip() if current_username else ''
                    
                    current_normalized = current_username.lstrip('@').lower()
                    new_normalized = tg_username.lstrip('@').lower()
                    
                    if current_normalized == new_normalized:
                        skipped += 1
                    elif current_username:
                        to_replace.append({
                            'employee_id': student['id'],
                            'fio': student['fio'],
                            'current_username': current_username,
                            'new_username': tg_username,
                            'row_number': idx + 2
                        })
                    else:
                        cursor.execute("UPDATE employees SET tg_username = ? WHERE id = ?", (tg_username, student['id']))
                        inserted += 1
                    
                except Exception as e:
                    errors.append(f"Строка {idx + 2}: ошибка обработки - {str(e)}")
                    continue
            
            conn.commit()
        
        os.remove(filepath)
        
        result = {
            'success': True,
            'inserted': inserted,
            'skipped': skipped,
            'to_replace': to_replace,  # Список записей, требующих подтверждения замены
            'not_found': not_found,
            'errors': errors[:20]  # Ограничиваем количество ошибок
        }
        
        return jsonify(result)
        
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'Ошибка импорта: {str(e)}'}), 500

@app.route('/api/admin/tg_users/confirm_replace', methods=['POST'])
def api_admin_tg_users_confirm_replace():
    
    if not session.get('admin_id'):
        return jsonify({'error': 'Необходима авторизация'}), 401
    
    data = request.get_json()
    replacements = data.get('replacements', [])  # Список {employee_id, new_username}
    
    if not replacements:
        return jsonify({'error': 'Не предоставлен список для замены'}), 400
    
    updated = 0
    not_found = 0
    errors = []
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        for replacement in replacements:
            try:
                employee_id = replacement.get('employee_id')
                new_username = replacement.get('new_username', '').strip().lstrip('@')
                
                if not employee_id or not new_username:
                    errors.append(f"Неверные данные для замены: employee_id={employee_id}, username={new_username}")
                    continue
                
                cursor.execute("SELECT id, fio FROM employees WHERE id = ?", (employee_id,))
                student = cursor.fetchone()
                
                if not student:
                    not_found += 1
                    errors.append(f"Студент с ID {employee_id} не найден")
                    continue
                
                cursor.execute("UPDATE employees SET tg_username = ? WHERE id = ?", (new_username, employee_id))
                updated += 1
                
            except Exception as e:
                errors.append(f"Ошибка при замене для employee_id {replacement.get('employee_id')}: {str(e)}")
                continue
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'updated': updated,
        'not_found': not_found,
        'errors': errors
    })

@app.route('/events/calendar')
def events_calendar():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('admin_login'))
    
    if not has_permission(admin_id, 'manage_events'):
        return render_template('no_access.html', message='У вас нет доступа к календарю мероприятий'), 403
    
    role = get_admin_role(admin_id)
    
    all_permissions = [
        'view', 'edit', 'delete', 'import', 'manage_columns', 
        'manage_health', 'manage_vacation', 'manage_admins', 
        'manage_bed_linen', 'manage_send_messages', 'view_reports', 'manage_tg_users', 
        'scan_qr', 'manage_rooms', 'manage_minors', 
        'manage_round_assignments', 'manage_payments', 'manage_events',
        'access_college', 'all'
        'access_college', 'all'
    ]
    admin_permissions = {}
    for perm in all_permissions:
        admin_permissions[perm] = has_permission(admin_id, perm)
    
    return render_template('events_calendar.html', admin_role=role, admin_permissions=admin_permissions)

@app.route('/api/events', methods=['GET'])
def api_get_events():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    with get_db() as conn:
        query = 'SELECT id, admin_id, admin_fio, location, description, event_date, event_time, created_at, coauthor_id, coauthor_fio FROM events WHERE 1=1'
        params = []
        
        if start_date:
            query += ' AND event_date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND event_date <= ?'
            params.append(end_date)
        
        query += ' ORDER BY event_date, event_time'
        
        events = conn.execute(query, params).fetchall()
        
        result = []
        for event in events:
            try:
                coauthor_id = event['coauthor_id'] if event['coauthor_id'] else None
                coauthor_fio = event['coauthor_fio'] if event['coauthor_fio'] else None
            except (KeyError, TypeError):
                coauthor_id = None
                coauthor_fio = None
            
            result.append({
                'id': event['id'],
                'admin_id': event['admin_id'],
                'admin_fio': event['admin_fio'],
                'location': event['location'],
                'description': event['description'],
                'event_date': event['event_date'],
                'event_time': event['event_time'],
                'created_at': event['created_at'],
                'coauthor_id': coauthor_id,
                'coauthor_fio': coauthor_fio
            })
        
        return jsonify({'success': True, 'events': result})

@app.route('/api/events', methods=['POST'])
def api_create_event():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['vospitatel', 'admin', 'super_admin']:
        return jsonify({'error': 'Только воспитатели могут добавлять мероприятия'}), 403
    
    data = request.json
    location = data.get('location', '').strip()
    description = data.get('description', '').strip()
    event_date = data.get('event_date', '').strip()
    event_time = data.get('event_time', '').strip()
    coauthor_id = data.get('coauthor_id')
    
    
    if not location or not description or not event_date or not event_time:
        return jsonify({'error': 'Все поля обязательны для заполнения'}), 400
    
    admin_fio = session.get('admin_fio', '')
    if not admin_fio:
        with get_db() as conn:
            admin = conn.execute('SELECT fio FROM admins WHERE id = ?', (admin_id,)).fetchone()
            if admin:
                try:
                    admin_fio = admin['fio'] if admin['fio'] else ''
                except (KeyError, TypeError):
                    admin_fio = ''
            else:
                admin_fio = ''
    
    if not admin_fio:
        return jsonify({'error': 'ФИО воспитателя не указано. Обратитесь к администратору для добавления ФИО.'}), 400
    
    coauthor_fio = None
    if coauthor_id:
        with get_db() as conn:
            coauthor = conn.execute('SELECT fio FROM admins WHERE id = ? AND role IN ("vospitatel", "admin", "super_admin")', (coauthor_id,)).fetchone()
            if coauthor:
                try:
                    coauthor_fio = coauthor['fio'] if coauthor['fio'] else None
                except (KeyError, TypeError):
                    coauthor_fio = None
            else:
                coauthor_id = None
    
    with get_db() as conn:
        
        conn.execute('''
            INSERT INTO events (admin_id, admin_fio, location, description, event_date, event_time, coauthor_id, coauthor_fio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (admin_id, admin_fio, location, description, event_date, event_time, coauthor_id, coauthor_fio))
        conn.commit()
        
        saved_event = conn.execute('SELECT location FROM events WHERE admin_id = ? AND event_date = ? AND event_time = ? ORDER BY id DESC LIMIT 1', 
                                   (admin_id, event_date, event_time)).fetchone()
        if saved_event:
            pass
        
        return jsonify({'success': True})

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def api_delete_event(event_id):
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = get_admin_role(admin_id)
    if role not in ['vospitatel', 'admin', 'super_admin']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    with get_db() as conn:
        event = conn.execute('SELECT admin_id FROM events WHERE id = ?', (event_id,)).fetchone()
        if not event:
            return jsonify({'error': 'Мероприятие не найдено'}), 404
        
        if role == 'vospitatel' and event['admin_id'] != admin_id:
            return jsonify({'error': 'Вы можете удалить только свои мероприятия'}), 403
        
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()
        
        return jsonify({'success': True})

@app.route('/api/events/locations', methods=['GET'])
def api_get_locations():
    """Получить список активных мест проведения мероприятий"""
    with get_db() as conn:
        locations = conn.execute('''
            SELECT name FROM event_locations 
            WHERE is_active = 1 
            ORDER BY name
        ''').fetchall()
        location_list = [loc['name'] for loc in locations]
    return jsonify({'success': True, 'locations': location_list})

@app.route('/api/events/vospitatels', methods=['GET'])
def api_get_vospitatels():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        vospitatels = conn.execute('''
            SELECT id, fio, username
            FROM admins
            WHERE role IN ('vospitatel', 'admin', 'super_admin') AND is_active = 1
            ORDER BY fio, username
        ''').fetchall()
        
        result = []
        for v in vospitatels:
            try:
                fio = v['fio'] if v['fio'] else ''
                username = v['username'] or ''
                if fio:
                    result.append({
                        'id': v['id'],
                        'fio': fio,
                        'username': username
                    })
            except (KeyError, TypeError):
                continue
        
        return jsonify({'success': True, 'vospitatels': result})


PAYMENT_DETAILS = {
    'bank_name': 'Сбербанк',
    'recipient_name': 'АНОО ВО "Университет "Сириус"',
    'inn': '2367010021',
    'bic': '046015602',
    'account': '40703810530060000441',
    'bank_account': '30101810100000000602',  # Корреспондентский счет (обычно для Сбербанка)
}

PAYMENT_RATES = {
    1: 5800,  # 1 проживающий - 5800
    2: 2900,  # 2 - 2900
    3: 1500,  # 3 - 1500
    4: 900,   # 4 - 900
}

def calculate_payment_amount(room_occupancy):
    
    if not room_occupancy or room_occupancy <= 0:
        room_occupancy = 1
    
    if room_occupancy > 4:
        room_occupancy = 4
    
    return PAYMENT_RATES.get(room_occupancy, PAYMENT_RATES[1])

try:
    from config import TELEGRAM_BOT_TOKEN
except ImportError:
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

def send_telegram_notification(tg_user_id, message, parse_mode='Markdown'):
    
    try:
        import requests
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        data = {
            'chat_id': tg_user_id,
            'text': message,
            'parse_mode': parse_mode
        }
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        return False

@app.route('/api/payment/generate_qr', methods=['POST'])
def api_generate_payment_qr():
    
    try:
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()
        
        if 'admin_id' not in session:
            tg_user_id = data.get('tg_user_id')
            if not tg_user_id:
                return jsonify({'error': 'Unauthorized'}), 401
            
            with get_db() as conn:
                tg_user = conn.execute(
                    'SELECT employee_id FROM tg_users WHERE tg_user_id = ?',
                    (tg_user_id,)
                ).fetchone()
                
                if not tg_user or not tg_user['employee_id']:
                    return jsonify({'error': 'User not registered'}), 401
                
                employee_id = tg_user['employee_id']
        else:
            employee_id = data.get('employee_id')
            if not employee_id:
                return jsonify({'error': 'Employee ID required'}), 400
        
        with get_db() as conn:
            student = conn.execute(
                'SELECT id, fio, building, entrance, room_number, room_occupancy FROM employees WHERE id = ?',
                (employee_id,)
            ).fetchone()
        
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        fio = student['fio'] if student['fio'] else ''
        if not fio:
            return jsonify({'error': 'Student FIO not found'}), 404
        
        try:
            building = (student['building'] or '').strip() if 'building' in student and student['building'] else ''
            entrance = (student['entrance'] or '').strip() if 'entrance' in student and student['entrance'] else ''
            room_number = (student['room_number'] or '').strip() if 'room_number' in student and student['room_number'] else ''
        except (KeyError, TypeError):
            building = ''
            entrance = ''
            room_number = ''
        
        
        room_occupancy = None
        
        if building and entrance and room_number:
            room = conn.execute(
                'SELECT capacity FROM rooms WHERE building = ? AND entrance = ? AND room_number = ?',
                (building, entrance, room_number)
            ).fetchone()
            
            
            if room and 'capacity' in room and room['capacity']:
                room_occupancy = room['capacity']
            else:
                room = conn.execute('''
                    SELECT capacity FROM rooms 
                    WHERE TRIM(building) = ? 
                    AND TRIM(entrance) = ? 
                    AND TRIM(room_number) = ?
                ''', (building.strip(), entrance.strip(), room_number.strip())).fetchone()
                
                if room and 'capacity' in room and room['capacity']:
                    room_occupancy = room['capacity']
        
        if not room_occupancy:
            try:
                employee_id = student['id'] if 'id' in student else None
                if employee_id:
                    room = conn.execute('''
                        SELECT DISTINCT r.capacity 
                        FROM rooms r
                        INNER JOIN employees e ON TRIM(e.building) = TRIM(r.building) 
                            AND TRIM(e.entrance) = TRIM(r.entrance) 
                            AND TRIM(e.room_number) = TRIM(r.room_number)
                        WHERE e.id = ?
                    ''', (employee_id,)).fetchone()
                    
                    if room and 'capacity' in room and room['capacity']:
                        room_occupancy = room['capacity']
            except Exception as e:
                import traceback
                traceback.print_exc()
        
        if not room_occupancy and (building or entrance or room_number):
            try:
                all_rooms = conn.execute('SELECT building, entrance, room_number, capacity FROM rooms').fetchall()
                
                for room in all_rooms:
                    room_b = (room['building'] or '').strip().lower()
                    room_e = (room['entrance'] or '').strip().lower()
                    room_r = (room['room_number'] or '').strip().lower()
                    
                    student_b = building.strip().lower() if building else ''
                    student_e = entrance.strip().lower() if entrance else ''
                    student_r = room_number.strip().lower() if room_number else ''
                    
                    if (not student_b or room_b == student_b) and \
                       (not student_e or room_e == student_e) and \
                       (not student_r or room_r == student_r):
                        room_occupancy = room['capacity']
                        break
            except Exception as e:
                import traceback
                traceback.print_exc()
        
        if not room_occupancy:
            try:
                room_occupancy = student['room_occupancy'] if 'room_occupancy' in student and student['room_occupancy'] else None
            except (KeyError, TypeError):
                room_occupancy = None
        
        payment_amount = calculate_payment_amount(room_occupancy, building, entrance, room_number)
        
        payment_purpose = f'Оплата за проживание в общежитии Сигма студента {fio}. Сумма: {payment_amount} руб.'
        
        qr_string = (
            f"ST00012|Name={PAYMENT_DETAILS['recipient_name']}|"
            f"PersonalAcc={PAYMENT_DETAILS['account']}|"
            f"BankName={PAYMENT_DETAILS['bank_name']}|"
            f"BIC={PAYMENT_DETAILS['bic']}|"
            f"CorrespAcc={PAYMENT_DETAILS['bank_account']}|"
            f"Purpose={payment_purpose}|"
            f"Sum={payment_amount * 100}"  # Сумма в копейках
        )
        
        if not QRCODE_AVAILABLE:
            return jsonify({'error': 'QR code library not available'}), 500
        
        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_string)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            img_buffer = io.BytesIO()
            qr_img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            return jsonify({
                'success': True,
                'qr_code': img_base64,
                'payment_details': {
                    'recipient': PAYMENT_DETAILS['recipient_name'],
                    'account': PAYMENT_DETAILS['account'],
                    'bic': PAYMENT_DETAILS['bic'],
                    'bank': PAYMENT_DETAILS['bank_name'],
                    'purpose': payment_purpose,
                    'inn': PAYMENT_DETAILS['inn'],
                    'amount': payment_amount
                },
                'room_occupancy': room_occupancy,
                'amount': payment_amount
            })
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return jsonify({'error': f'Failed to generate QR code: {str(e)}'}), 500
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/api/payment/upload_receipt', methods=['POST'])
def api_upload_receipt():
    
    tg_user_id = request.form.get('tg_user_id')
    if not tg_user_id:
        return jsonify({'error': 'tg_user_id required'}), 400
    
    with get_db() as conn:
        tg_user = conn.execute(
            'SELECT employee_id FROM tg_users WHERE tg_user_id = ?',
            (tg_user_id,)
        ).fetchone()
        
        if not tg_user or not tg_user['employee_id']:
            return jsonify({'error': 'User not registered'}), 401
        
        employee_id = tg_user['employee_id']
        
        if 'receipt' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['receipt']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        receipt_folder = 'static/receipts'
        os.makedirs(receipt_folder, exist_ok=True)
        
        filename = secure_filename(file.filename)
        if not filename:
            filename = 'receipt.jpg'
        filepath = os.path.join(receipt_folder, f"{employee_id}_{datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')}_{filename}")
        file.save(filepath)
        
        receipt_file_path = filepath
        
        payment_date = datetime.now(MOSCOW_TZ).isoformat()
        now = datetime.now(MOSCOW_TZ)
        if now.month == 1:
            payment_month = f"{now.year - 1}-12"
        else:
            payment_month = f"{now.year}-{now.month - 1:02d}"
        
        conn.execute('''
            INSERT INTO dormitory_payments (employee_id, tg_user_id, receipt_file, status, payment_date, payment_month, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, tg_user_id, receipt_file_path, 'pending', payment_date, payment_month, payment_date))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Чек успешно загружен и ожидает проверки'
        })

@app.route('/api/payment/list', methods=['GET'])
@require_permission('manage_payments')
def api_payment_list():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    status = request.args.get('status', 'all')  # all, pending, approved, rejected
    
    with get_db() as conn:
        if status == 'all':
            payments = conn.execute('''
                SELECT dp.id, dp.employee_id, dp.tg_user_id, dp.amount, dp.payment_date,
                       dp.receipt_file, dp.status, dp.audit_admin_id, dp.audit_comment,
                       dp.audited_at, dp.created_at,
                       e.fio, e.room_number, e.building, e.entrance,
                       a.fio as audit_admin_fio
                FROM dormitory_payments dp
                JOIN employees e ON dp.employee_id = e.id
                LEFT JOIN admins a ON dp.audit_admin_id = a.id
                ORDER BY dp.created_at DESC
            ''').fetchall()
        else:
            payments = conn.execute('''
                SELECT dp.id, dp.employee_id, dp.tg_user_id, dp.amount, dp.payment_date,
                       dp.receipt_file, dp.status, dp.audit_admin_id, dp.audit_comment,
                       dp.audited_at, dp.created_at,
                       e.fio, e.room_number, e.building, e.entrance,
                       a.fio as audit_admin_fio
                FROM dormitory_payments dp
                JOIN employees e ON dp.employee_id = e.id
                LEFT JOIN admins a ON dp.audit_admin_id = a.id
                WHERE dp.status = ?
                ORDER BY dp.created_at DESC
            ''', (status,)).fetchall()
        
        result = []
        for payment in payments:
            result.append({
                'id': payment['id'],
                'employee_id': payment['employee_id'],
                'tg_user_id': payment['tg_user_id'],
                'fio': payment['fio'],
                'room_number': payment['room_number'],
                'building': payment['building'],
                'entrance': payment['entrance'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'receipt_file': payment['receipt_file'],
                'status': payment['status'],
                'audit_admin_fio': payment['audit_admin_fio'],
                'audit_comment': payment['audit_comment'],
                'audited_at': payment['audited_at'],
                'created_at': payment['created_at']
            })
        
        return jsonify({
            'success': True,
            'payments': result
        })

@app.route('/api/payment/approve', methods=['POST'])
@require_permission('manage_payments')
def api_payment_approve():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    payment_id = data.get('payment_id')
    comment = data.get('comment', '')
    
    if not payment_id:
        return jsonify({'error': 'payment_id required'}), 400
    
    with get_db() as conn:
        audited_at = datetime.now(MOSCOW_TZ).isoformat()
        conn.execute('''
            UPDATE dormitory_payments
            SET status = ?, audit_admin_id = ?, audit_comment = ?, audited_at = ?
            WHERE id = ?
        ''', ('accepted', admin_id, comment, audited_at, payment_id))
        
        payment = conn.execute('''
            SELECT dp.tg_user_id, e.fio
            FROM dormitory_payments dp
            JOIN employees e ON dp.employee_id = e.id
            WHERE dp.id = ?
        ''', (payment_id,)).fetchone()
        
        conn.commit()
        
        if payment and payment['tg_user_id']:
            message = f"✅ <b>Оплата принята</b>\n\nВаш чек об оплате проживания был одобрен аудитом."
            if comment:
                message += f"\n\nКомментарий: {comment}"
            send_telegram_notification(payment['tg_user_id'], message)
        
        return jsonify({
            'success': True,
            'message': 'Оплата одобрена'
        })

@app.route('/api/payment/reject', methods=['POST'])
@require_permission('manage_payments')
def api_payment_reject():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    payment_id = data.get('payment_id')
    comment = data.get('comment', '')
    
    if not payment_id:
        return jsonify({'error': 'payment_id required'}), 400
    
    with get_db() as conn:
        audited_at = datetime.now(MOSCOW_TZ).isoformat()
        conn.execute('''
            UPDATE dormitory_payments
            SET status = ?, audit_admin_id = ?, audit_comment = ?, audited_at = ?
            WHERE id = ?
        ''', ('rejected', admin_id, comment, audited_at, payment_id))
        
        payment = conn.execute('''
            SELECT dp.tg_user_id, e.fio
            FROM dormitory_payments dp
            JOIN employees e ON dp.employee_id = e.id
            WHERE dp.id = ?
        ''', (payment_id,)).fetchone()
        
        conn.commit()
        
        if payment and payment['tg_user_id']:
            message = f"❌ <b>Оплата не принята</b>\n\nВаш чек об оплате проживания был отклонен аудитом."
            if comment:
                message += f"\n\nПричина: {comment}"
            send_telegram_notification(payment['tg_user_id'], message)
        
        return jsonify({
            'success': True,
            'message': 'Оплата отклонена'
        })

@app.route('/api/payment/receipt/<int:payment_id>', methods=['GET'])
@require_permission('manage_payments')
def api_payment_receipt(payment_id):
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with get_db() as conn:
        payment = conn.execute('''
            SELECT receipt_file FROM dormitory_payments WHERE id = ?
        ''', (payment_id,)).fetchone()
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        receipt_file = payment['receipt_file']
        if not receipt_file or not os.path.exists(receipt_file):
            return jsonify({'error': 'Receipt file not found'}), 404
        
        return send_file(receipt_file)

@app.route('/admin/payments')
def admin_payments():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('admin_login'))
    
    role = get_admin_role(admin_id)
    if role not in ['audit', 'super_admin', 'admin']:
        return render_template('no_access.html', message='У вас нет доступа к этому разделу')
    
    return render_template('admin_payments.html')


@app.route('/admin/profile')
def admin_profile():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return redirect(url_for('admin_login'))
    
    with get_db() as conn:
        admin = conn.execute(
            'SELECT id, username, fio, role, password_changed FROM admins WHERE id = ?',
            (admin_id,)
        ).fetchone()
        
        if not admin:
            return redirect(url_for('admin_login'))
        
        try:
            password_changed = admin['password_changed'] if admin['password_changed'] else 0
        except (KeyError, TypeError):
            password_changed = 0
        role = session.get('admin_role', '')
        admin_fio = session.get('admin_fio', '')
        
        return render_template('admin_profile.html', 
                             admin_role=role, 
                             admin_fio=admin_fio,
                             admin_username=admin['username'],
                             password_changed=password_changed)

@app.route('/api/admin/change_password', methods=['POST'])
def api_change_password():
    
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    if not current_password or not new_password or not confirm_password:
        return jsonify({'error': 'Все поля обязательны для заполнения'}), 400
    
    if new_password != confirm_password:
        return jsonify({'error': 'Новый пароль и подтверждение не совпадают'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'Пароль должен содержать минимум 6 символов'}), 400
    
    with get_db() as conn:
        admin = conn.execute(
            'SELECT password_hash FROM admins WHERE id = ?',
            (admin_id,)
        ).fetchone()
        
        if not admin:
            return jsonify({'error': 'Администратор не найден'}), 404
        
        if not check_password_hash(admin['password_hash'], current_password):
            return jsonify({'error': 'Неверный текущий пароль'}), 400
        
        new_password_hash = generate_password_hash(new_password)
        conn.execute(
            'UPDATE admins SET password_hash = ?, password_changed = 1 WHERE id = ?',
            (new_password_hash, admin_id)
        )
        conn.commit()
        
        session['password_changed'] = 1
        
        return jsonify({
            'success': True, 
            'message': 'Пароль успешно изменен',
            'password_changed': True
        })


@app.errorhandler(404)
def not_found_error(error):
    
    return render_template('error.html', 
                         error_code=404,
                         error_message='Страница не найдена'), 404

@app.errorhandler(500)
def internal_error(error):
    
    import traceback
    error_details = traceback.format_exc() if app.debug else None
    return render_template('error.html',
                         error_code=500,
                         error_message='Внутренняя ошибка сервера',
                         error_details=error_details), 500

@app.errorhandler(403)
def forbidden_error(error):
    
    return render_template('error.html',
                         error_code=403,
                         error_message='Доступ запрещен'), 403

@app.errorhandler(400)
def bad_request_error(error):
    
    return render_template('error.html',
                         error_code=400,
                         error_message='Неверный запрос'), 400

@app.errorhandler(405)
def method_not_allowed_error(error):
    
    return render_template('error.html',
                         error_code=405,
                         error_message='Метод не разрешен'), 405

from routes.room_routes import room_bp
from routes.employee_routes import employee_bp
from routes.utility_routes import utility_bp
from routes.admin_pages_routes import admin_pages_bp
from routes.admin_api_routes import admin_api_bp
from routes.bed_linen_routes import bed_linen_bp
from routes.event_routes import event_bp
from routes.rounds_routes import rounds_bp
from routes.payment_routes import payment_bp
from routes.maintenance_routes import maintenance_bp
from routes.export_routes import export_bp
from routes.groups_routes import groups_bp

app.register_blueprint(room_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(utility_bp)
app.register_blueprint(admin_pages_bp)
app.register_blueprint(admin_api_bp)
app.register_blueprint(bed_linen_bp)
app.register_blueprint(event_bp)
app.register_blueprint(rounds_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(maintenance_bp)
app.register_blueprint(export_bp)
app.register_blueprint(groups_bp)

if __name__ == '__main__':
    app.run(debug=True)