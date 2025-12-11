import sqlite3
import json
import os
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from config import DATABASE_PATH, MOSCOW_TZ

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
                room_number TEXT DEFAULT '',
                building TEXT DEFAULT '',
                entrance TEXT DEFAULT '',
                tg_username TEXT DEFAULT '',
                room_occupancy INTEGER DEFAULT 1,
                payment_from_scholarship INTEGER DEFAULT 0
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
                is_active INTEGER DEFAULT 1,
                fio TEXT DEFAULT '',
                password_changed INTEGER DEFAULT 0
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

            CREATE TABLE IF NOT EXISTS event_organizers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_username TEXT UNIQUE NOT NULL,
                fio TEXT,
                tg_user_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS maintenance_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                tg_user_id INTEGER,
                student_fio TEXT NOT NULL,
                building TEXT,
                entrance TEXT,
                room_number TEXT,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                request_number TEXT,
                assigned_admin_id INTEGER,
                assigned_admin_fio TEXT,
                admin_comment TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                assigned_at TEXT,
                closed_at TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (assigned_admin_id) REFERENCES admins(id)
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
                coauthor_id INTEGER,
                coauthor_fio TEXT,
                organizers TEXT DEFAULT '',
                FOREIGN KEY (admin_id) REFERENCES admins(id)
            );

            CREATE TABLE IF NOT EXISTS event_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES admins(id)
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

            CREATE TABLE IF NOT EXISTS room_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                max_occupants INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                room_number TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 1,
                excluded_from_duty INTEGER DEFAULT 0,
                category_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(building, entrance, room_number),
                FOREIGN KEY (category_id) REFERENCES room_categories(id)
            );

            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_date TEXT NOT NULL,
                round_time TEXT NOT NULL,
                inspector_id INTEGER NOT NULL,
                inspector_tg_id INTEGER NOT NULL,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                student_fio TEXT NOT NULL,
                room_number TEXT NOT NULL,
                status TEXT NOT NULL,
                vacation_info TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (inspector_id) REFERENCES employees(id),
                FOREIGN KEY (student_id) REFERENCES employees(id)
            );

            CREATE TABLE IF NOT EXISTS round_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                assigned_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES employees(id),
                FOREIGN KEY (assigned_by) REFERENCES employees(id),
                UNIQUE(student_id, building, entrance)
            );

            CREATE TABLE IF NOT EXISTS educator_round_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                educator_id INTEGER NOT NULL,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                assigned_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (educator_id) REFERENCES admins(id),
                FOREIGN KEY (assigned_by) REFERENCES admins(id),
                UNIQUE(educator_id, building, entrance)
            );

            CREATE TABLE IF NOT EXISTS column_order (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_name TEXT UNIQUE NOT NULL,
                display_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS block_order (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                block_name TEXT UNIQUE NOT NULL,
                display_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS duty_schedule_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                last_room_index INTEGER NOT NULL,
                last_room_number TEXT,
                last_month INTEGER NOT NULL,
                last_year INTEGER NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(building, entrance)
            );

            CREATE TABLE IF NOT EXISTS elder_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                assigned_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (assigned_by) REFERENCES admins(id),
                UNIQUE(employee_id, building, entrance)
            );

            CREATE TABLE IF NOT EXISTS event_attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                student_fio TEXT NOT NULL,
                scanned_by_tg_id INTEGER,
                scanned_by_username TEXT,
                scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                UNIQUE(event_id, employee_id)
            );

            CREATE TABLE IF NOT EXISTS student_passwords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                tg_user_id INTEGER,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                FOREIGN KEY (tg_user_id) REFERENCES tg_users(tg_user_id),
                UNIQUE(employee_id)
            );

            CREATE TABLE IF NOT EXISTS student_2fa_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                tg_user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                FOREIGN KEY (tg_user_id) REFERENCES tg_users(tg_user_id)
            );

            CREATE TABLE IF NOT EXISTS employee_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                file_type TEXT,
                description TEXT,
                uploaded_by INTEGER,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                FOREIGN KEY (uploaded_by) REFERENCES admins(id)
            );

            CREATE TABLE IF NOT EXISTS minor_location_requests (
                tg_user_id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                fio TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                responded_at TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS message_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message_text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES admins(id)
            );

            CREATE TABLE IF NOT EXISTS duty_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                schedule_month INTEGER NOT NULL,
                schedule_year INTEGER NOT NULL,
                schedule_data TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES employees(id),
                UNIQUE(building, entrance, schedule_month, schedule_year)
            );
        ''')

        _apply_migrations(conn)
        init_roles(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM admins")
        count = cursor.fetchone()['count']
        if count == 0:
            password_hash = generate_password_hash('admin123')
            cursor.execute('''
                INSERT INTO admins (username, password_hash, role, permissions, is_active, password_changed)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', ('admin', password_hash, 'super_admin', '{"all": true}', 1))
            conn.commit()

def _apply_migrations(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(events)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    
    # Добавляем колонки только если их нет
    if 'coauthor_id' not in existing_cols:
        cursor.execute("ALTER TABLE events ADD COLUMN coauthor_id INTEGER")
    if 'coauthor_fio' not in existing_cols:
        cursor.execute("ALTER TABLE events ADD COLUMN coauthor_fio TEXT")
    conn.commit()

    cursor.execute("PRAGMA table_info(bed_linen_dates)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    # Проверяем, нужно ли выполнять миграцию
    if 'date' in existing_cols and 'start_date' not in existing_cols:
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
    
    cursor.execute("PRAGMA table_info(scans)")
    scan_cols = [row[1] for row in cursor.fetchall()]
    if 'period_id' not in scan_cols:
        cursor.execute("ALTER TABLE scans ADD COLUMN period_id INTEGER")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_period_id ON scans(period_id)")
    conn.commit()
    
    cursor.execute("PRAGMA table_info(event_attendance)")
    attendance_cols = [row[1] for row in cursor.fetchall()]
    if 'employee_id' not in attendance_cols:
        cursor.execute("SELECT COUNT(*) as cnt FROM event_attendance")
        count = cursor.fetchone()['cnt']
        if count > 0:
            cursor.execute("DROP TABLE IF EXISTS event_attendance_old")
            cursor.execute("""
                CREATE TABLE event_attendance_old AS 
                SELECT * FROM event_attendance
            """)
            cursor.execute("DROP TABLE IF EXISTS event_attendance")
            cursor.execute("""
                CREATE TABLE event_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    employee_id INTEGER NOT NULL,
                    student_fio TEXT NOT NULL,
                    scanned_by_tg_id INTEGER,
                    scanned_by_username TEXT,
                    scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                    FOREIGN KEY (employee_id) REFERENCES employees(id),
                    UNIQUE(event_id, employee_id)
                )
            """)
            # Проверяем, есть ли колонка student_fio в старой таблице
            cursor.execute("PRAGMA table_info(event_attendance_old)")
            old_cols = [row[1] for row in cursor.fetchall()]
            if 'student_fio' in old_cols:
                cursor.execute("""
                    INSERT INTO event_attendance 
                    (id, event_id, employee_id, student_fio, scanned_by_tg_id, scanned_by_username, scanned_at)
                    SELECT 
                        old.id, 
                        old.event_id,
                        COALESCE((SELECT id FROM employees WHERE fio = old.student_fio LIMIT 1), 0) as employee_id,
                        old.student_fio,
                        old.scanned_by_tg_id,
                        old.scanned_by_username,
                        old.scanned_at
                    FROM event_attendance_old old
                    WHERE (SELECT id FROM employees WHERE fio = old.student_fio LIMIT 1) IS NOT NULL
                """)
            cursor.execute("DROP TABLE IF EXISTS event_attendance_old")
            conn.commit()
    
    cursor.execute("PRAGMA table_info(custom_columns)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if 'col_type' not in existing_cols:
        cursor.execute('''
            CREATE TABLE custom_columns_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                col_type TEXT DEFAULT 'text'
            )
        ''')
        # Проверяем, какая колонка есть в старой таблице: type или col_type
        if 'type' in existing_cols:
            cursor.execute('INSERT INTO custom_columns_new (id, name, col_type) SELECT id, name, type FROM custom_columns')
        elif 'col_type' in existing_cols:
            cursor.execute('INSERT INTO custom_columns_new (id, name, col_type) SELECT id, name, col_type FROM custom_columns')
        else:
            cursor.execute('INSERT INTO custom_columns_new (id, name) SELECT id, name FROM custom_columns')
        cursor.execute('DROP TABLE custom_columns')
        cursor.execute('ALTER TABLE custom_columns_new RENAME TO custom_columns')
        conn.commit()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            max_occupants INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.execute("PRAGMA table_info(room_categories)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if 'max_occupants' not in existing_cols:
        cursor.execute("ALTER TABLE room_categories ADD COLUMN max_occupants INTEGER DEFAULT 1")
        conn.commit()
    
    cursor.execute("PRAGMA table_info(rooms)")
    room_cols = [row[1] for row in cursor.fetchall()]
    if 'excluded_from_duty' not in room_cols:
        cursor.execute("ALTER TABLE rooms ADD COLUMN excluded_from_duty INTEGER DEFAULT 0")
        conn.commit()
    
    cursor.execute("PRAGMA table_info(rooms)")
    room_cols = [row[1] for row in cursor.fetchall()]
    if 'category_id' not in room_cols:
        cursor.execute("ALTER TABLE rooms ADD COLUMN category_id INTEGER")
        conn.commit()
    
    # Создаем таблицу groups, если её нет
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='groups'
    """)
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Импортируем группы из файла ofgroups.txt, если он существует
        try:
            import os
            if os.path.exists('ofgroups.txt'):
                with open('ofgroups.txt', 'r', encoding='utf-8') as f:
                    groups = [line.strip() for line in f if line.strip()]
                    for group in groups:
                        try:
                            cursor.execute("INSERT INTO groups (name) VALUES (?)", (group,))
                        except sqlite3.IntegrityError:
                            # Группа уже существует, пропускаем
                            pass
                conn.commit()
        except Exception:
            # Если не удалось импортировать, продолжаем без ошибок
            pass
    
    cursor.execute("PRAGMA table_info(rooms)")
    room_cols = [row[1] for row in cursor.fetchall()]
    if 'floor' not in room_cols:
        cursor.execute("ALTER TABLE rooms ADD COLUMN floor INTEGER")
        conn.commit()
    
    # Создаем таблицу мест проведения мероприятий, если её нет
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='event_locations'
    """)
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE event_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES admins(id)
            )
        """)
        # Добавляем начальные места из хардкода
        initial_locations = [
            'Коворкинг "Псоу"',
            'Коворкинг "Мзымта"',
            'Кинозал',
            'Коворкинг "Сабаль"',
            'Коворкинг "Фаргезия"',
            'Коворкинг "Магнолия"',
            'Мастер-кухня'
        ]
        for location_name in initial_locations:
            try:
                cursor.execute("""
                    INSERT INTO event_locations (name, is_active)
                    VALUES (?, 1)
                """, (location_name,))
            except sqlite3.IntegrityError:
                pass  # Место уже существует
        conn.commit()
    
    cursor.execute("PRAGMA table_info(employees)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    for col in ['notes', 'absences', 'reprimands', 'vacation', 'vacation_history']:
        if col not in existing_cols:
            default_val = "''" if col != 'vacation_history' else "'[]'"
            cursor.execute(f"ALTER TABLE employees ADD COLUMN {col} TEXT DEFAULT {default_val}")
    for col, default in [
        ('room_number', "''"),
        ('building', "''"),
        ('entrance', "''"),
        ('tg_username', "''"),
        ('room_occupancy', '1'),
        ('payment_from_scholarship', '0'),
        ('can_do_rounds', '0'),
        ('is_round_chief', '0'),
        ('is_entrance_elder', '0'),
        ('education_level', "''"),
        ('has_own_bed_linen', '0'),
        ('max_entrances', '0'),  # Максимальное количество подъездов для воспитателей
        ('is_local', '0')  # Местный студент (не в списках на смену белья)
    ]:
        if col not in existing_cols:
            if col in ['room_occupancy', 'payment_from_scholarship', 'can_do_rounds', 'is_round_chief', 'is_entrance_elder', 'has_own_bed_linen', 'max_entrances', 'is_local']:
                cursor.execute(f"ALTER TABLE employees ADD COLUMN {col} INTEGER DEFAULT {default}")
            else:
                cursor.execute(f"ALTER TABLE employees ADD COLUMN {col} TEXT DEFAULT {default}")
    
    # Создаем таблицу ограничений на обходы
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='round_restrictions'
    """)
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE round_restrictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES employees(id) ON DELETE CASCADE,
                UNIQUE(student_id, building, entrance)
            )
        """)
        conn.commit()
    if 'is_minor' not in existing_cols:
        cursor.execute("ALTER TABLE employees ADD COLUMN is_minor INTEGER")
    cursor.execute("PRAGMA table_info(admins)")
    admin_cols = [row[1] for row in cursor.fetchall()]
    if 'fio' not in admin_cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN fio TEXT DEFAULT ''")
    if 'password_changed' not in admin_cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN password_changed INTEGER DEFAULT 0")
        cursor.execute("UPDATE admins SET password_changed = 0 WHERE password_changed IS NULL")
    if 'max_entrances' not in admin_cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN max_entrances INTEGER DEFAULT 0")
        cursor.execute("UPDATE admins SET max_entrances = 0 WHERE max_entrances IS NULL")
    cursor.execute("PRAGMA table_info(employee_changes_history)")
    history_cols = [row[1] for row in cursor.fetchall()]
    if 'admin_id' not in history_cols:
        cursor.execute("ALTER TABLE employee_changes_history ADD COLUMN admin_id INTEGER")
    if 'admin_username' not in history_cols:
        cursor.execute("ALTER TABLE employee_changes_history ADD COLUMN admin_username TEXT")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rooms_lookup ON rooms(building, entrance, room_number)")
    conn.commit()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS elder_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            building TEXT NOT NULL,
            entrance TEXT NOT NULL,
            assigned_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (assigned_by) REFERENCES admins(id),
            UNIQUE(employee_id, building, entrance)
        )
    ''')
    conn.commit()
    cursor.execute("PRAGMA table_info(dormitory_payments)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    cursor.execute("PRAGMA table_info(dormitory_payments)")
    payment_cols = [row[1] for row in cursor.fetchall()]
    if 'payment_month' not in payment_cols:
        cursor.execute("ALTER TABLE dormitory_payments ADD COLUMN payment_month TEXT")
    conn.commit()
    
    # Создаем таблицу duty_schedules, если её нет
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='duty_schedules'
    """)
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE duty_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                schedule_month INTEGER NOT NULL,
                schedule_year INTEGER NOT NULL,
                schedule_data TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES employees(id),
                UNIQUE(building, entrance, schedule_month, schedule_year)
            )
        ''')
        conn.commit()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employee_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            file_type TEXT,
            description TEXT,
            uploaded_by INTEGER,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by) REFERENCES admins(id)
        )
    ''')
    conn.commit()
    
    # Создаем таблицу duty_schedules, если её нет
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='duty_schedules'
    """)
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE duty_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building TEXT NOT NULL,
                entrance TEXT NOT NULL,
                schedule_month INTEGER NOT NULL,
                schedule_year INTEGER NOT NULL,
                schedule_data TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES employees(id),
                UNIQUE(building, entrance, schedule_month, schedule_year)
            )
        ''')
        conn.commit()
    
    conn.commit()

def init_roles(conn):
    system_roles = [
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
    ]
    
    # Предустановленные роли (не системные) - создаются только если их еще нет
    preset_roles = [
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
            'manage_send_messages': False,
            'view_reports': False,
            'manage_tg_users': False,
            'scan_qr': False,
            'manage_rooms': False,
            'manage_minors': False,
            'manage_round_assignments': False,
            'manage_payments': True,
            'manage_events': False
        }), 'Аудит - доступ только к разделу оплаты проживания'),
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
            'view_reports': True,
            'manage_tg_users': False,
            'scan_qr': False,
            'manage_rooms': False,
            'manage_minors': False,
            'manage_round_assignments': False,
            'manage_payments': False,
            'manage_events': False
        }), 'Администратор средства размещения - просмотр студентов и отчетов по белью')
    ]
    cursor = conn.cursor()
    for role_name, permissions, description in system_roles:
        cursor.execute('''
            INSERT OR REPLACE INTO roles (name, permissions, description)
            VALUES (?, ?, ?)
        ''', (role_name, permissions, description))
    for role_name, permissions, description in preset_roles:
        cursor.execute('''
            INSERT OR IGNORE INTO roles (name, permissions, description)
            VALUES (?, ?, ?)
        ''', (role_name, permissions, description))
    conn.commit()

