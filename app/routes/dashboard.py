from datetime import datetime, date, timedelta, time
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from app import db
from app.models.user import User
from app.models.elder import Elder
from app.models.medicine import Medicine
from app.models.schedule import MedicineSchedule
from app.models.adherence import AdherenceRecord
from app.models.alert import Alert

dashboard_bp = Blueprint('dashboard', __name__)


def get_current_user():
    user_id = get_jwt_identity()
    return User.query.get(int(user_id))


def _get_elder_ids(user):
    if user.role == 'admin':
        return [e.id for e in Elder.query.filter_by(is_active=True).all()]
    return [e.id for e in Elder.query.filter_by(caretaker_id=user.id, is_active=True).all()]


@dashboard_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    user = get_current_user()
    today = date.today()
    elder_ids = _get_elder_ids(user)

    total_elders = len(elder_ids)
    total_active_medicines = Medicine.query.filter(
        Medicine.elder_id.in_(elder_ids), Medicine.is_active == True
    ).count() if elder_ids else 0

    today_schedules = MedicineSchedule.query.filter(
        MedicineSchedule.elder_id.in_(elder_ids),
        MedicineSchedule.is_active == True
    ).count() if elder_ids else 0

    today_taken = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id.in_(elder_ids),
        AdherenceRecord.status.in_(['taken', 'taken_late']),
        func.date(AdherenceRecord.scheduled_datetime) == today
    ).count() if elder_ids else 0

    today_missed = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id.in_(elder_ids),
        AdherenceRecord.status == 'missed',
        func.date(AdherenceRecord.scheduled_datetime) == today
    ).count() if elder_ids else 0

    today_taken_late = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id.in_(elder_ids),
        AdherenceRecord.status == 'taken_late',
        func.date(AdherenceRecord.scheduled_datetime) == today
    ).count() if elder_ids else 0

    today_total = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id.in_(elder_ids),
        func.date(AdherenceRecord.scheduled_datetime) == today
    ).count() if elder_ids else 0

    today_adherence = round(today_taken / today_total * 100, 1) if today_total > 0 else 0

    unread_alerts = Alert.query.filter(
        Alert.is_read == False,
        Alert.caretaker_id == user.id if user.role != 'admin' else True
    ).count()

    since_30 = datetime.utcnow() - timedelta(days=30)
    monthly_total = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id.in_(elder_ids),
        AdherenceRecord.scheduled_datetime >= since_30
    ).count() if elder_ids else 0
    monthly_taken = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id.in_(elder_ids),
        AdherenceRecord.status.in_(['taken', 'taken_late']),
        AdherenceRecord.scheduled_datetime >= since_30
    ).count() if elder_ids else 0
    monthly_missed = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id.in_(elder_ids),
        AdherenceRecord.status == 'missed',
        AdherenceRecord.scheduled_datetime >= since_30
    ).count() if elder_ids else 0
    monthly_rate = round(monthly_taken / monthly_total * 100, 1) if monthly_total > 0 else 0

    try:
        from app.models.reminder_log import ReminderLog
        today_reminders = ReminderLog.query.filter(
            ReminderLog.elder_id.in_(elder_ids),
            func.date(ReminderLog.fired_at) == today
        ).count() if elder_ids else 0
    except Exception:
        today_reminders = 0

    return jsonify({
        'total_elders':           total_elders,
        'total_active_medicines': total_active_medicines,
        'today_schedules':        today_schedules,
        'today_taken':            today_taken,
        'today_taken_late':       today_taken_late,
        'today_missed':           today_missed,
        'today_adherence_rate':   today_adherence,
        'today_reminders':        today_reminders,
        'unread_alerts':          unread_alerts,
        'monthly_adherence_rate': monthly_rate,
        'monthly_taken':          monthly_taken,
        'monthly_missed':         monthly_missed,
        'monthly_total':          monthly_total,
    }), 200


@dashboard_bp.route('/today-schedule', methods=['GET'])
@jwt_required()
def get_today_schedule():
    user = get_current_user()
    today = date.today()
    elder_ids = _get_elder_ids(user)
    if not elder_ids:
        return jsonify({'schedules': []}), 200

    schedules = MedicineSchedule.query.filter(
        MedicineSchedule.elder_id.in_(elder_ids),
        MedicineSchedule.is_active == True
    ).order_by(MedicineSchedule.scheduled_time).all()

    schedule_list = []
    for s in schedules:
        s_dict = s.to_dict()
        adherence = AdherenceRecord.query.filter_by(
            schedule_id=s.id, elder_id=s.elder_id
        ).filter(
            AdherenceRecord.scheduled_datetime >= datetime.combine(today, time.min),
            AdherenceRecord.scheduled_datetime <= datetime.combine(today, time.max)
        ).first()
        s_dict['adherence_status'] = adherence.status if adherence else 'pending'
        s_dict['adherence_id'] = adherence.id if adherence else None
        schedule_list.append(s_dict)

    return jsonify({'schedules': schedule_list, 'date': today.isoformat()}), 200


@dashboard_bp.route('/adherence-chart', methods=['GET'])
@jwt_required()
def get_adherence_chart():
    """Supports ?days=7 (weekly) or ?days=30 (monthly)."""
    user = get_current_user()
    days = request.args.get('days', 7, type=int)
    elder_id = request.args.get('elder_id', type=int)
    elder_ids = _get_elder_ids(user)

    if elder_id and elder_id in elder_ids:
        elder_ids = [elder_id]
    if not elder_ids:
        return jsonify({'chart_data': []}), 200

    since = datetime.utcnow() - timedelta(days=days)
    records = AdherenceRecord.query.filter(
        AdherenceRecord.elder_id.in_(elder_ids),
        AdherenceRecord.scheduled_datetime >= since
    ).all()

    chart_data = []
    for i in range(days - 1, -1, -1):
        day = date.today() - timedelta(days=i)
        day_recs    = [r for r in records if r.scheduled_datetime.date() == day]
        day_taken   = sum(1 for r in day_recs if r.status in ('taken', 'taken_late'))
        day_late    = sum(1 for r in day_recs if r.status == 'taken_late')
        day_missed  = sum(1 for r in day_recs if r.status == 'missed')
        day_total   = len(day_recs)
        label = day.strftime('%d %b') if days > 7 else day.strftime('%a')
        chart_data.append({
            'date':       day.isoformat(),
            'day':        label,
            'taken':      day_taken,
            'taken_late': day_late,
            'missed':     day_missed,
            'total':      day_total,
            'rate':       round(day_taken / day_total * 100, 1) if day_total > 0 else 0
        })

    return jsonify({'chart_data': chart_data, 'days': days}), 200


@dashboard_bp.route('/elder-summary', methods=['GET'])
@jwt_required()
def get_elder_summary():
    user = get_current_user()
    elders = Elder.query.filter_by(is_active=True).all() if user.role == 'admin' \
        else Elder.query.filter_by(caretaker_id=user.id, is_active=True).all()

    since = datetime.utcnow() - timedelta(days=30)
    summary = []
    for elder in elders:
        records = AdherenceRecord.query.filter(
            AdherenceRecord.elder_id == elder.id,
            AdherenceRecord.scheduled_datetime >= since
        ).all()
        total  = len(records)
        taken  = sum(1 for r in records if r.status in ('taken', 'taken_late'))
        missed = sum(1 for r in records if r.status == 'missed')
        rate   = round(taken / total * 100, 1) if total > 0 else 0
        summary.append({
            'elder_id':       elder.id,
            'elder_name':     elder.name,
            'age':            elder.age,
            'adherence_rate': rate,
            'missed':         missed,
            'active_medicines': Medicine.query.filter_by(elder_id=elder.id, is_active=True).count(),
            'unread_alerts':  Alert.query.filter_by(elder_id=elder.id, is_read=False).count(),
            'status': 'good' if rate >= 80 else ('warning' if rate >= 60 else 'critical')
        })

    return jsonify({'summary': summary}), 200


@dashboard_bp.route('/next-dose', methods=['GET'])
@jwt_required()
def get_next_dose():
    user = get_current_user()
    now = datetime.now()
    today = date.today()
    elder_ids = _get_elder_ids(user)
    if not elder_ids:
        return jsonify({'next_dose': None}), 200

    current_time = now.time().replace(second=0, microsecond=0)
    schedules = MedicineSchedule.query.filter(
        MedicineSchedule.elder_id.in_(elder_ids),
        MedicineSchedule.is_active == True,
        MedicineSchedule.scheduled_time >= current_time
    ).order_by(MedicineSchedule.scheduled_time).all()

    for s in schedules:
        adherence = AdherenceRecord.query.filter_by(
            schedule_id=s.id, elder_id=s.elder_id
        ).filter(
            AdherenceRecord.scheduled_datetime >= datetime.combine(today, time.min),
            AdherenceRecord.scheduled_datetime <= datetime.combine(today, time.max)
        ).first()
        if adherence and adherence.status in ('taken', 'taken_late'):
            continue
        return jsonify({'next_dose': s.to_dict()}), 200

    return jsonify({'next_dose': None}), 200


@dashboard_bp.route('/upcoming-doses', methods=['GET'])
@jwt_required()
def get_upcoming_doses():
    user = get_current_user()
    minutes = request.args.get('minutes', 5, type=int)
    now = datetime.now()
    today = date.today()
    elder_ids = _get_elder_ids(user)
    if not elder_ids:
        return jsonify({'doses': []}), 200

    current_time = now.time()
    future_time  = (now + timedelta(minutes=minutes)).time()

    schedules = MedicineSchedule.query.filter(
        MedicineSchedule.elder_id.in_(elder_ids),
        MedicineSchedule.is_active == True,
        MedicineSchedule.scheduled_time >= current_time,
        MedicineSchedule.scheduled_time <= future_time
    ).all()

    doses = []
    for s in schedules:
        adherence = AdherenceRecord.query.filter_by(
            schedule_id=s.id, elder_id=s.elder_id
        ).filter(
            AdherenceRecord.scheduled_datetime >= datetime.combine(today, time.min),
            AdherenceRecord.scheduled_datetime <= datetime.combine(today, time.max)
        ).first()
        if not adherence or adherence.status == 'pending':
            doses.append(s.to_dict())

    return jsonify({'doses': doses}), 200
