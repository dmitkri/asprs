import os
import shutil
import gzip
from datetime import datetime
from pathlib import Path
from config import DATABASE_PATH, BACKUP_DIR, BACKUP_RETENTION_DAYS

def create_backup(compress=True):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"aspirs_backup_{timestamp}.db"
    if compress:
        backup_filename += '.gz'
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    if compress:
        with open(DATABASE_PATH, 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    else:
        shutil.copy2(DATABASE_PATH, backup_path)
    os.chmod(backup_path, 0o600)
    return backup_path

def restore_backup(backup_path):
    if os.path.exists(DATABASE_PATH):
        pre_restore_backup = f"{DATABASE_PATH}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(DATABASE_PATH, pre_restore_backup)
    if backup_path.endswith('.gz'):
        with gzip.open(backup_path, 'rb') as f_in:
            with open(DATABASE_PATH, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    else:
        shutil.copy2(backup_path, DATABASE_PATH)
    os.chmod(DATABASE_PATH, 0o600)
    return True

def cleanup_old_backups():
    cutoff_time = datetime.now().timestamp() - (BACKUP_RETENTION_DAYS * 24 * 60 * 60)
    deleted_count = 0
    for filename in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, filename)
        # Удаляем как старые бэкапы (phonebook_backup_), так и новые (aspirs_backup_)
        if os.path.isfile(filepath) and (filename.startswith('aspirs_backup_') or filename.startswith('phonebook_backup_')):
            file_time = os.path.getmtime(filepath)
            if file_time < cutoff_time:
                os.remove(filepath)
                deleted_count += 1
    return deleted_count

def list_backups():
    backups = []
    for filename in os.listdir(BACKUP_DIR):
        # Поддерживаем как старые бэкапы (phonebook_backup_), так и новые (aspirs_backup_)
        if filename.startswith('aspirs_backup_') or filename.startswith('phonebook_backup_'):
            filepath = os.path.join(BACKUP_DIR, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                backups.append({
                    'filename': filename,
                    'path': filepath,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'compressed': filename.endswith('.gz')
                })
    backups.sort(key=lambda x: x['created'], reverse=True)
    return backups

def get_backup_size():
    total_size = 0
    for filename in os.listdir(BACKUP_DIR):
        # Поддерживаем как старые бэкапы (phonebook_backup_), так и новые (aspirs_backup_)
        if filename.startswith('aspirs_backup_') or filename.startswith('phonebook_backup_'):
            filepath = os.path.join(BACKUP_DIR, filename)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
    return total_size

