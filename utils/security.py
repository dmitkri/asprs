import re
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS, ALLOWED_EXCEL, MAX_FILE_SIZE, ALLOWED_STUDENT_FILE_EXTENSIONS, MAX_STUDENT_FILE_SIZE

def validate_filename(filename):
    dangerous_chars = ['..', '/', '\\', '\x00']
    for char in dangerous_chars:
        if char in filename:
            return False
    return True

def sanitize_filename(filename):
    safe_name = secure_filename(filename)
    return safe_name

def allowed_file(filename, allowed_extensions=None):
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions

def allowed_file_excel(filename):
    return allowed_file(filename, ALLOWED_EXCEL)

def validate_file_size(file):
    current_pos = file.tell()
    file.seek(0, 2)
    size = file.tell()
    file.seek(current_pos)
    return size <= MAX_FILE_SIZE

def allowed_student_file(filename):
    return allowed_file(filename, ALLOWED_STUDENT_FILE_EXTENSIONS)

def validate_student_file_size(file):
    current_pos = file.tell()
    file.seek(0, 2)
    size = file.tell()
    file.seek(current_pos)
    return size <= MAX_STUDENT_FILE_SIZE

def sanitize_input(text, max_length=None):
    text = text.replace('\x00', '')
    if max_length and len(text) > max_length:
        text = text[:max_length]
    return text.strip()

def validate_phone(phone):
    digits = re.sub(r'\D', '', phone)
    return 10 <= len(digits) <= 11

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_date_format(date_str, format='%Y-%m-%d'):
    from datetime import datetime
    datetime.strptime(date_str, format)
    return True

def escape_html(text):
    text = str(text)
    replacements = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text

