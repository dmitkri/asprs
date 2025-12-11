from flask import Blueprint, jsonify, request, send_file, session
from utils.backup import create_backup, restore_backup, list_backups, cleanup_old_backups, get_backup_size
from utils.auth import require_permission, require_admin
import os

backup_bp = Blueprint('backup', __name__)

@backup_bp.route('/api/backup/create', methods=['POST'])
@require_admin()
def api_create_backup():
    compress = request.json.get('compress', True) if request.is_json else True
    backup_path = create_backup(compress=compress)
    deleted_count = cleanup_old_backups()
    return jsonify({
        'success': True,
        'message': 'Бэкап успешно создан',
        'backup_path': backup_path,
        'backup_filename': os.path.basename(backup_path),
        'deleted_old_backups': deleted_count
    })

@backup_bp.route('/api/backup/list', methods=['GET'])
@require_admin()
def api_list_backups():
    backups = list_backups()
    total_size = get_backup_size()
    return jsonify({
        'success': True,
        'backups': backups,
        'total_size': total_size,
        'count': len(backups)
    })

@backup_bp.route('/api/backup/restore', methods=['POST'])
@require_admin()
def api_restore_backup():
    data = request.json
    backup_filename = data.get('backup_filename')
    from config import BACKUP_DIR
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    restore_backup(backup_path)
    return jsonify({
        'success': True,
        'message': 'База данных успешно восстановлена'
    })

@backup_bp.route('/api/backup/download/<path:filename>', methods=['GET'])
@require_admin()
def api_download_backup(filename):
    from config import BACKUP_DIR
    backup_path = os.path.join(BACKUP_DIR, filename)
    from flask import send_file
    return send_file(backup_path, as_attachment=True)

@backup_bp.route('/api/backup/cleanup', methods=['POST'])
@require_admin()
def api_cleanup_backups():
    deleted_count = cleanup_old_backups()
    return jsonify({
        'success': True,
        'message': f'Удалено {deleted_count} старых бэкапов',
        'deleted_count': deleted_count
    })

@backup_bp.route('/api/backup/stats', methods=['GET'])
@require_admin()
def api_backup_stats():
    backups = list_backups()
    total_size = get_backup_size()
    return jsonify({
        'success': True,
        'total_backups': len(backups),
        'total_size': total_size,
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'oldest_backup': backups[-1]['created'] if backups else None,
        'newest_backup': backups[0]['created'] if backups else None
    })

