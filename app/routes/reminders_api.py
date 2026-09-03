"""
Reminder Engine API
POST /api/reminders/snooze          — snooze current reminder
POST /api/reminders/taken           — mark dose taken from reminder popup
GET  /api/reminders/active/<elder>  — get active reminder states
GET  /api/reminders/texts/<level>   — get reminder text for a level
"""
from datetime import date
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.elder import Elder

reminders_api_bp = Blueprint('reminders_api', __name__)


def _get_user():
    return User.query.get(int(get_jwt_identity()))


def _can_access_elder(user, elder_id):
    elder = Elder.query.get(elder_id)
    if not elder:
        return False, None
    if user.role != 'admin' and elder.caretaker_id != user.id:
        return False, elder
    return True, elder


@reminders_api_bp.route('/snooze', methods=['POST'])
@jwt_required()
def snooze():
    user = _get_user()
    data = request.get_json() or {}
    schedule_id = data.get('schedule_id')
    elder_id = data.get('elder_id')
    if not schedule_id or not elder_id:
        return jsonify({'error': 'schedule_id and elder_id required'}), 400
    allowed, _ = _can_access_elder(user, int(elder_id))
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    from app.services.adaptive_reminder_engine import snooze_reminder
    result = snooze_reminder(schedule_id, elder_id, date.today(), current_app._get_current_object())
    return jsonify(result), 200


@reminders_api_bp.route('/taken', methods=['POST'])
@jwt_required()
def mark_taken_from_reminder():
    """Quick-mark a dose as taken from the reminder popup."""
    user = _get_user()
    data = request.get_json() or {}
    schedule_id = data.get('schedule_id')
    elder_id = data.get('elder_id')
    medicine_id = data.get('medicine_id')

    if not schedule_id or not elder_id or not medicine_id:
        return jsonify({'error': 'schedule_id, elder_id, medicine_id required'}), 400
    allowed, _ = _can_access_elder(user, int(elder_id))
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    from app import db
    from app.models.adherence import AdherenceRecord
    from app.models.alert import Alert
    from app.models.reminder_state import ReminderState
    from app.models.schedule import MedicineSchedule
    from datetime import datetime

    today = date.today()
    schedule = MedicineSchedule.query.get(schedule_id)
    if not schedule:
        return jsonify({'error': 'Schedule not found'}), 404

    scheduled_dt = datetime.combine(today, schedule.scheduled_time)

    existing = AdherenceRecord.query.filter_by(
        schedule_id=schedule_id, elder_id=elder_id
    ).filter(
        AdherenceRecord.scheduled_datetime >= datetime.combine(today, __import__('datetime').time.min),
        AdherenceRecord.scheduled_datetime <= datetime.combine(today, __import__('datetime').time.max)
    ).first()

    if existing:
        existing.status = 'taken'
        existing.taken_datetime = datetime.utcnow()
        existing.recorded_by = user.id
    else:
        db.session.add(AdherenceRecord(
            schedule_id=schedule_id, elder_id=elder_id,
            medicine_id=medicine_id,
            scheduled_datetime=scheduled_dt,
            taken_datetime=datetime.utcnow(),
            status='taken', recorded_by=user.id
        ))

    # Resolve reminder state
    state = ReminderState.query.filter_by(
        schedule_id=schedule_id, elder_id=elder_id, dose_date=today
    ).first()
    if state:
        state.status = 'resolved'

    # Dismiss related alerts
    Alert.query.filter_by(
        elder_id=elder_id, related_schedule_id=schedule_id, is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})

    db.session.commit()

    # Send caretaker notification email for the taken dose.
    try:
        from app.routes.adherence import _send_adherence_email
        _send_adherence_email(None, elder_id, medicine_id, schedule_id, 'taken', user)
    except Exception:
        pass

    return jsonify({'message': 'Dose marked as taken', 'status': 'taken'}), 200


@reminders_api_bp.route('/active/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_active_reminders(elder_id):
    """Return active reminder states for the elder today."""
    """Return active reminder states for the elder today."""
    user = _get_user()
    allowed, elder = _can_access_elder(user, elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    from app.services.adaptive_reminder_engine import get_active_reminders_for_elder
    states = get_active_reminders_for_elder(elder_id)
    result = []
    for s in states:
        sdict = s.to_dict()
        sdict['elder_name'] = elder.name if elder else None
        if s.schedule and s.schedule.medicine:
            sdict['medicine_id'] = s.schedule.medicine_id
            sdict['medicine_name'] = s.schedule.medicine.name
            sdict['medicine_dosage'] = s.schedule.medicine.dosage
            sdict['scheduled_time'] = s.schedule.scheduled_time.strftime('%H:%M')
        result.append(sdict)
    return jsonify({'reminders': result}), 200


@reminders_api_bp.route('/texts/<int:level>', methods=['GET'])
@jwt_required()
def get_reminder_texts(level):
    """Return the reminder texts for a given level (1/2/3)."""
    from app.services.adaptive_reminder_engine import REMINDER_TEXTS
    if level not in REMINDER_TEXTS:
        return jsonify({'error': 'Invalid level (1-3)'}), 400
    return jsonify({'level': level, 'texts': REMINDER_TEXTS[level]}), 200


@reminders_api_bp.route('/active-all', methods=['GET'])
@jwt_required()
def get_all_active_reminders():
    """
    Return ALL active reminders across all elders for this caretaker.
    Used by the local reminder_agent.py (polls this every 60 seconds).
    """
    import datetime as _dt
    from app.models.reminder_state import ReminderState
    from app.models.elder import Elder
    from app.models.adherence import AdherenceRecord

    user     = _get_user()
    today    = _dt.date.today()
    dt_min   = _dt.datetime.combine(today, _dt.time.min)
    dt_max   = _dt.datetime.combine(today, _dt.time.max)

    if user.role == 'admin':
        elder_ids = [e.id for e in Elder.query.filter_by(is_active=True).all()]
    else:
        elder_ids = [e.id for e in Elder.query.filter_by(
            caretaker_id=user.id, is_active=True).all()]

    if not elder_ids:
        return jsonify({'reminders': [], 'count': 0}), 200

    active = ReminderState.query.filter(
        ReminderState.elder_id.in_(elder_ids),
        ReminderState.dose_date == today,
        ReminderState.status != 'resolved'
    ).all()

    result = []
    for s in active:
        adherence = AdherenceRecord.query.filter_by(
            schedule_id=s.schedule_id, elder_id=s.elder_id
        ).filter(
            AdherenceRecord.scheduled_datetime >= dt_min,
            AdherenceRecord.scheduled_datetime <= dt_max
        ).first()

        item = s.to_dict()
        item['adherence_status'] = adherence.status if adherence else 'pending'
        if s.schedule and s.schedule.medicine:
            item['medicine_name']   = s.schedule.medicine.name
            item['medicine_dosage'] = s.schedule.medicine.dosage
            item['scheduled_time']  = s.schedule.scheduled_time.strftime('%H:%M')
        if s.elder:
            item['elder_name'] = s.elder.name
        result.append(item)

    return jsonify({'reminders': result, 'count': len(result)}), 200


@reminders_api_bp.route('/agent-health', methods=['GET'])
def agent_health():
    """Check if the local reminder agent is running (no auth needed)."""
    try:
        import requests as req
        resp = req.get('http://localhost:5001/health', timeout=3)
        if resp.ok:
            return jsonify({'agent_running': True, 'details': resp.json()}), 200
    except Exception:
        pass
    return jsonify({'agent_running': False,
                    'message': 'Run: python reminder_agent.py'}), 200
