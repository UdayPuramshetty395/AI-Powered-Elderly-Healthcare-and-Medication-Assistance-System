from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
import threading
from app import db
from app.models.adherence import AdherenceRecord
from app.models.schedule import MedicineSchedule
from app.models.elder import Elder
from app.models.user import User
from app.models.medicine import Medicine

adherence_bp = Blueprint('adherence', __name__)


def get_current_user():
    user_id = get_jwt_identity()
    return User.query.get(int(user_id))


def can_access_elder(user, elder_id):
    elder = Elder.query.get(elder_id)
    if not elder:
        return False, None
    if user.role != 'admin' and elder.caretaker_id != user.id:
        return False, elder
    return True, elder


def _send_adherence_email(app, elder_id, medicine_id, schedule_id, status, user):
    """Send email to caretaker when dose is marked taken/missed. Non-blocking."""
    import logging
    log = logging.getLogger(__name__)
    try:
        _app = current_app._get_current_object()
        elder    = Elder.query.get(elder_id)
        med      = Medicine.query.get(medicine_id)
        caretaker = User.query.get(elder.caretaker_id) if elder else None

        log.info(f"Email trigger: status={status}, elder={elder.name if elder else 'None'}, "
                 f"caretaker={caretaker.email if caretaker else 'None'}")

        if not elder:
            log.warning("Email skipped: elder not found")
            return
        if not med:
            log.warning("Email skipped: medicine not found")
            return
        if not caretaker:
            log.warning("Email skipped: caretaker not found")
            return
        if not caretaker.email:
            log.warning(f"Email skipped: caretaker {caretaker.username} has no email")
            return

        sched      = MedicineSchedule.query.get(schedule_id)
        sched_time = sched.scheduled_time.strftime('%I:%M %p') if sched else '—'
        taken_at   = datetime.now()

        # Determine if taken late
        is_late = False
        if status in ('taken', 'taken_late') and sched:
            delay = (datetime.utcnow() - datetime.combine(date.today(),
                      sched.scheduled_time)).total_seconds()
            is_late = delay > 1800 or status == 'taken_late'

        ct_name  = caretaker.full_name or caretaker.username
        ct_email = caretaker.email

        # Capture values for thread (avoid SQLAlchemy DetachedInstanceError)
        elder_name   = elder.name
        med_name     = med.name
        med_dosage   = med.dosage

        if status in ('taken', 'taken_late'):
            log.info(f"Sending dose-taken email to {ct_email}")
            def _send(a=_app, e=ct_email, n=ct_name, en=elder_name,
                       mn=med_name, d=med_dosage, t=taken_at, st=sched_time, late=is_late):
                with a.app_context():
                    from app.services.email_service import send_dose_taken_email
                    result = send_dose_taken_email(
                        caretaker_email=e, caretaker_name=n,
                        elder_name=en, medicine_name=mn,
                        dosage=d, taken_at=t,
                        scheduled_time=st, is_late=late
                    )
                    log.info(f"Email result: {result}")
            threading.Thread(target=_send, daemon=True).start()

        elif status == 'missed':
            from app.services.reminder_service import get_consecutive_missed_count
            missed_count = get_consecutive_missed_count(elder_id, medicine_id)
            log.info(f"Sending missed-dose email to {ct_email}, missed_count={missed_count}")
            def _send_m(a=_app, e=ct_email, n=ct_name, en=elder_name,
                         mn=med_name, d=med_dosage, st=sched_time, mc=missed_count):
                with a.app_context():
                    from app.services.email_service import send_missed_dose_email
                    result = send_missed_dose_email(
                        caretaker_email=e, caretaker_name=n,
                        elder_name=en, medicine_name=mn,
                        dosage=d, scheduled_time=st, missed_count=mc
                    )
                    log.info(f"Missed email result: {result}")
            threading.Thread(target=_send_m, daemon=True).start()

    except Exception as e:
        import logging as _lg
        _lg.getLogger(__name__).warning(f'Email trigger error: {e}', exc_info=True)


@adherence_bp.route('', methods=['GET'])
@jwt_required()
def get_adherence():
    """Get adherence records with filters."""
    user = get_current_user()
    elder_id = request.args.get('elder_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    if user.role == 'admin':
        query = AdherenceRecord.query
    else:
        elder_ids = [e.id for e in Elder.query.filter_by(caretaker_id=user.id, is_active=True).all()]
        query = AdherenceRecord.query.filter(AdherenceRecord.elder_id.in_(elder_ids))

    if elder_id:
        query = query.filter_by(elder_id=elder_id)
    if status:
        query = query.filter_by(status=status)
    if start_date:
        query = query.filter(AdherenceRecord.scheduled_datetime >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(AdherenceRecord.scheduled_datetime <= datetime.fromisoformat(end_date))

    records = query.order_by(AdherenceRecord.scheduled_datetime.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'records': [r.to_dict() for r in records.items],
        'total': records.total,
        'pages': records.pages,
        'current_page': records.page
    }), 200


@adherence_bp.route('/mark', methods=['POST'])
@jwt_required()
def mark_adherence():
    """Mark a dose as taken, missed, or skipped."""
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    schedule_id = data.get('schedule_id')
    elder_id = data.get('elder_id')
    medicine_id = data.get('medicine_id')
    status = data.get('status', 'taken')
    scheduled_datetime_str = data.get('scheduled_datetime')

    if not all([schedule_id, elder_id, medicine_id, scheduled_datetime_str]):
        return jsonify({'error': 'schedule_id, elder_id, medicine_id, scheduled_datetime are required'}), 400

    if status not in ['taken', 'missed', 'skipped']:
        return jsonify({'error': 'Status must be taken, missed, or skipped'}), 400

    allowed, _ = can_access_elder(user, elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    try:
        scheduled_datetime = datetime.fromisoformat(scheduled_datetime_str)
    except ValueError:
        return jsonify({'error': 'Invalid scheduled_datetime format'}), 400

    # Check if record already exists
    existing = AdherenceRecord.query.filter_by(
        schedule_id=schedule_id,
        elder_id=elder_id,
        scheduled_datetime=scheduled_datetime
    ).first()

    if existing:
        existing.status = status
        existing.taken_datetime = datetime.utcnow() if status in ('taken', 'taken_late') else None
        existing.notes = data.get('notes', existing.notes)
        existing.recorded_by = user.id
        _sync_reminder_state(schedule_id, elder_id, status)
        db.session.commit()
        # Send email for updated record too
        _send_adherence_email(app=None, elder_id=elder_id, medicine_id=medicine_id,
                              schedule_id=schedule_id, status=status, user=user)
        return jsonify({'message': f'Adherence updated to {status}', 'record': existing.to_dict()}), 200

    record = AdherenceRecord(
        schedule_id=schedule_id,
        elder_id=elder_id,
        medicine_id=medicine_id,
        scheduled_datetime=scheduled_datetime,
        taken_datetime=datetime.utcnow() if status == 'taken' else None,
        status=status,
        notes=data.get('notes'),
        recorded_by=user.id
    )

    # Auto-detect taken_late (confirmed > 30 min after scheduled time)
    if status == 'taken':
        delay = (datetime.utcnow() - scheduled_datetime).total_seconds()
        if delay > 1800:  # 30 minutes
            record.status = 'taken_late'
            record.taken_datetime = datetime.utcnow()

    db.session.add(record)

    # Auto-dismiss related alert if taken
    if status == 'taken':
        from app.models.alert import Alert
        Alert.query.filter_by(
            elder_id=elder_id,
            related_schedule_id=schedule_id,
            is_read=False
        ).update({'is_read': True, 'read_at': datetime.utcnow()})

    _sync_reminder_state(schedule_id, elder_id, status)
    db.session.commit()

    # ── Real-time WebSocket update ──────────────────────────────────────────
    try:
        from app.sockets.events import emit_adherence_update, emit_dashboard_refresh
        elder = Elder.query.get(elder_id)
        med = Medicine.query.get(medicine_id)
        if elder and med:
            emit_adherence_update(
                caretaker_id=elder.caretaker_id,
                elder_id=elder_id,
                elder_name=elder.name,
                medicine_name=med.name,
                status=status
            )
            emit_dashboard_refresh(elder.caretaker_id)
    except Exception:
        pass

    # ── Email caretaker ─────────────────────────────────────────────────────
    _send_adherence_email(None, elder_id, medicine_id, schedule_id, status, user)

    return jsonify({'message': f'Dose marked as {status}', 'record': record.to_dict()}), 201


def _sync_reminder_state(schedule_id, elder_id, status):
    """Resolve active reminder state when a dose gets confirmed or closed."""
    if status not in ['taken', 'missed', 'skipped']:
        return
    from app.models.reminder_state import ReminderState
    state = ReminderState.query.filter_by(
        schedule_id=schedule_id,
        elder_id=elder_id,
        dose_date=date.today()
    ).first()
    if state:
        state.status = 'resolved'


@adherence_bp.route('/stats/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_adherence_stats(elder_id):
    """Get adherence statistics for an elder."""
    user = get_current_user()
    allowed, _ = can_access_elder(user, elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    days = request.args.get('days', 30, type=int)
    since = datetime.utcnow() - timedelta(days=days)

    records = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id == elder_id,
        AdherenceRecord.scheduled_datetime >= since
    ).all()

    total = len(records)
    taken = sum(1 for r in records if r.status == 'taken')
    missed = sum(1 for r in records if r.status == 'missed')
    skipped = sum(1 for r in records if r.status == 'skipped')
    pending = sum(1 for r in records if r.status == 'pending')
    rate = round((taken / total * 100), 1) if total > 0 else 0

    # Daily breakdown for chart (last 7 days)
    daily_data = []
    for i in range(6, -1, -1):
        day = date.today() - timedelta(days=i)
        day_records = [r for r in records if r.scheduled_datetime.date() == day]
        day_taken = sum(1 for r in day_records if r.status == 'taken')
        day_total = len(day_records)
        daily_data.append({
            'date': day.isoformat(),
            'day': day.strftime('%a'),
            'taken': day_taken,
            'total': day_total,
            'rate': round((day_taken / day_total * 100), 1) if day_total > 0 else 0
        })

    return jsonify({
        'elder_id': elder_id,
        'period_days': days,
        'total': total,
        'taken': taken,
        'missed': missed,
        'skipped': skipped,
        'pending': pending,
        'adherence_rate': rate,
        'daily_breakdown': daily_data
    }), 200


@adherence_bp.route('/history/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_adherence_history(elder_id):
    """Get adherence history for an elder."""
    user = get_current_user()
    allowed, _ = can_access_elder(user, elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    records = AdherenceRecord.query.filter_by(elder_id=elder_id)\
        .order_by(AdherenceRecord.scheduled_datetime.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'records': [r.to_dict() for r in records.items],
        'total': records.total,
        'pages': records.pages,
        'current_page': records.page
    }), 200
