from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from database import get_db
from utils.room_utils import get_entrance_by_number
from config import MOSCOW_TZ

utility_bp = Blueprint('utility', __name__)

@utility_bp.route('/api/get_entrance')
def api_get_entrance():
    building = request.args.get('building', '').strip()
    number = request.args.get('number', '').strip()
    entrance = get_entrance_by_number(building, number)
    return jsonify({'entrance': entrance})

@utility_bp.route('/api/employee/<emp_id>/reports')
def api_employee_reports(emp_id):
    if emp_id == 'new' or not emp_id:
        return jsonify({
            'month': request.args.get('month', ''),
            'period': '',
            'dates': [],
            'received_count': 0,
            'periods': [],
            'has_own_bed_linen': False
        })
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return jsonify({
            'month': request.args.get('month', ''),
            'period': '',
            'dates': [],
            'received_count': 0,
            'periods': [],
            'has_own_bed_linen': False
        })
    month_str = request.args.get('month', '')
    if not month_str or '-' not in month_str:
        return jsonify({
            'month': month_str or '',
            'period': '',
            'dates': [],
            'received_count': 0,
            'periods': [],
            'has_own_bed_linen': False
        })
    year, month = map(int, month_str.split('-'))
    start_date = datetime(year, month, 1, tzinfo=MOSCOW_TZ)
    if month == 12:
        end_date = datetime(year + 1, 1, 1, tzinfo=MOSCOW_TZ) - timedelta(seconds=1)
    else:
        end_date = datetime(year, month + 1, 1, tzinfo=MOSCOW_TZ) - timedelta(seconds=1)
    month_start = start_date.isoformat()
    month_end = end_date.isoformat()
    with get_db() as conn:
        student = conn.execute("""
            SELECT has_own_bed_linen 
            FROM employees 
            WHERE id = ?
        """, (emp_id,)).fetchone()
        has_own_bed_linen = bool(student['has_own_bed_linen'] if 'has_own_bed_linen' in student.keys() else 0)
        scans = conn.execute("""
            SELECT scanned_at 
            FROM scans 
            WHERE employee_id = ? AND scanned_at >= ? AND scanned_at <= ?
            ORDER BY scanned_at DESC
        """, (emp_id, month_start, month_end)).fetchall()
        dates_received = []
        for scan in scans:
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
        periods = []
        period_rows = conn.execute("""
            SELECT id, start_date, end_date
            FROM bed_linen_dates
            WHERE is_active = 1
            AND (
                (start_date >= ? AND start_date <= ?) OR
                (end_date >= ? AND end_date <= ?) OR
                (start_date <= ? AND end_date >= ?)
            )
            ORDER BY start_date ASC
        """, (month_start[:10], month_end[:10], month_start[:10], month_end[:10], month_start[:10], month_end[:10])).fetchall()
        for period_row in period_rows:
            periods.append({
                'id': period_row['id'],
                'start_date': period_row['start_date'],
                'end_date': period_row['end_date']
            })
        return jsonify({
            'month': month_str or start_date.strftime("%Y-%m"),
            'period': start_date.strftime("%B %Y"),
            'dates': dates_received,
            'received_count': len(dates_received),
            'periods': periods,
            'has_own_bed_linen': has_own_bed_linen
        })

@utility_bp.route('/static/<path:filename>')
def static_files(filename):
    from flask import current_app
    return send_from_directory('static', filename)

