import os
from datetime import timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

class ConfigurationError(Exception):
    pass

def get_required_env(key, description=None):
    value = os.getenv(key)
    if not value:
        desc = description or key
        raise ConfigurationError(
            f"Обязательная переменная окружения {key} не установлена. "
            f"Установите её в .env файле или переменных окружения системы. "
            f"Описание: {desc}"
        )
    return value

def get_optional_env(key, default=None):
    return os.getenv(key, default)

SECRET_KEY = get_required_env('SECRET_KEY', 'Секретный ключ для Flask сессий')
DEBUG = get_optional_env('FLASK_DEBUG', 'False').lower() == 'true'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'aspirs.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'avatars')
UPLOAD_FOLDER_EXCEL = os.path.join(BASE_DIR, 'uploads')
RECEIPTS_FOLDER = os.path.join(BASE_DIR, 'static', 'receipts')
STUDENT_FILES_FOLDER = os.path.join(BASE_DIR, 'static', 'student_files')

for folder in [BACKUP_DIR, UPLOAD_FOLDER, UPLOAD_FOLDER_EXCEL, RECEIPTS_FOLDER, STUDENT_FILES_FOLDER]:
    os.makedirs(folder, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_EXCEL = {'xlsx', 'xls'}
ALLOWED_STUDENT_FILE_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'gif', 'txt', 'zip', 'rar'}
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_STUDENT_FILE_SIZE = 50 * 1024 * 1024

BACKUP_RETENTION_DAYS = 30
BACKUP_AUTO_ENABLED = True

MOSCOW_TZ = timezone(timedelta(hours=3))

TELEGRAM_BOT_TOKEN = get_required_env('TELEGRAM_BOT_TOKEN', 'Токен Telegram бота')
ADMIN_TELEGRAM_IDS_STR = get_optional_env('ADMIN_TELEGRAM_IDS', '')
ADMIN_TELEGRAM_IDS = []
ADMIN_TELEGRAM_IDS = [int(uid.strip()) for uid in ADMIN_TELEGRAM_IDS_STR.split(',') if uid.strip().isdigit()]

TELEGRAM_API_ID_STR = get_optional_env('TELEGRAM_API_ID', '')
TELEGRAM_API_ID = int(TELEGRAM_API_ID_STR) if TELEGRAM_API_ID_STR and TELEGRAM_API_ID_STR.isdigit() else None
TELEGRAM_API_HASH = get_optional_env('TELEGRAM_API_HASH', '')
TELEGRAM_PHONE_NUMBER = get_optional_env('TELEGRAM_PHONE_NUMBER', '')
TELEGRAM_SESSION_PATH = os.path.join(BASE_DIR, 'telegram_user_session')

PAYMENT_DETAILS = {
    'bank_name': 'Сбербанк',
    'recipient_name': 'АНОО ВО "Университет "Сириус"',
    'inn': '2367010021',
    'bic': '046015602',
    'account': '40703810530060000441',
    'bank_account': '30101810100000000602',
}

PAYMENT_RATES = {
    1: 5800,
    2: 2900,
    3: 1500,
    4: 900,
}

FIXED_COLS = ['fio', 'phone', 'group_name', 'birth_date']

MAIN_APP_PORT = int(get_optional_env('MAIN_APP_PORT', '5003'))

LOG_LEVEL = get_optional_env('LOG_LEVEL', 'INFO')
LOG_DIR = get_optional_env('LOG_DIR', 'logs')

