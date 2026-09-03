from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models.user import User

debug_bp = Blueprint('debug_bp', __name__)


def _get_user():
    return User.query.get(int(get_jwt_identity()))


@debug_bp.route('/trigger_reminder', methods=['POST'])
@jwt_required()
def trigger_reminder():
    """Trigger a reminder immediately for testing.
    Body: { schedule_id, elder_id }
    """
    data = request.get_json() or {}
    schedule_id = data.get('schedule_id')
    elder_id = data.get('elder_id')
    if not schedule_id or not elder_id:
        return jsonify({'error': 'schedule_id and elder_id required'}), 400

    try:
        from app.services.adaptive_reminder_engine import fire_reminder
        from datetime import date
        dose_date_str = date.today().isoformat()
        app = current_app._get_current_object()
        fire_reminder(app, int(schedule_id), int(elder_id), dose_date_str, 1)
        return jsonify({'success': True, 'message': 'Reminder triggered'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/scheduler_diagnostics', methods=['GET'])
@jwt_required()
def scheduler_diagnostics():
    """Return scheduler and audio diagnostics for debugging voice reminders."""
    try:
        from app.services.voice_scheduler import print_diagnostics
        app = current_app._get_current_object()
        perform_playback_test = request.args.get('playback_test', 'false').lower() in ['1', 'true', 'yes']
        diagnostics = print_diagnostics(app=app, perform_playback_test=perform_playback_test)
        return jsonify({'success': True, 'diagnostics': diagnostics}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
