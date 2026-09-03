from datetime import datetime, time, date
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.schedule import MedicineSchedule
from app.models.medicine import Medicine
from app.models.elder import Elder
from app.models.user import User

schedule_bp = Blueprint('schedule', __name__)


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


@schedule_bp.route('', methods=['GET'])
@jwt_required()
def get_schedules():
    """Get all schedules."""
    user = get_current_user()
    elder_id = request.args.get('elder_id', type=int)

    if user.role == 'admin':
        query = MedicineSchedule.query.filter_by(is_active=True)
    else:
        elder_ids = [e.id for e in Elder.query.filter_by(caretaker_id=user.id, is_active=True).all()]
        query = MedicineSchedule.query.filter(
            MedicineSchedule.elder_id.in_(elder_ids),
            MedicineSchedule.is_active == True
        )

    if elder_id:
        query = query.filter_by(elder_id=elder_id)

    schedules = query.order_by(MedicineSchedule.scheduled_time).all()
    return jsonify({'schedules': [s.to_dict() for s in schedules]}), 200


@schedule_bp.route('/today/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_today_schedules(elder_id):
    """Get today's medication schedule for an elder."""
    user = get_current_user()
    allowed, _ = can_access_elder(user, elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    today = date.today()
    day_name = today.strftime('%A').lower()

    schedules = MedicineSchedule.query.filter(
        MedicineSchedule.elder_id == elder_id,
        MedicineSchedule.is_active == True,
        (MedicineSchedule.day_of_week == 'all') |
        (MedicineSchedule.day_of_week == day_name) |
        (MedicineSchedule.day_of_week == None)
    ).order_by(MedicineSchedule.scheduled_time).all()

    from app.models.adherence import AdherenceRecord
    schedule_list = []
    for s in schedules:
        s_dict = s.to_dict()
        scheduled_dt = datetime.combine(today, s.scheduled_time)
        adherence = AdherenceRecord.query.filter_by(
            schedule_id=s.id,
            elder_id=elder_id
        ).filter(
            AdherenceRecord.scheduled_datetime >= datetime.combine(today, time.min),
            AdherenceRecord.scheduled_datetime <= datetime.combine(today, time.max)
        ).first()
        s_dict['adherence_status'] = adherence.status if adherence else 'pending'
        s_dict['adherence_id'] = adherence.id if adherence else None
        schedule_list.append(s_dict)

    return jsonify({'schedules': schedule_list, 'date': today.isoformat()}), 200


@schedule_bp.route('', methods=['POST'])
@jwt_required()
def create_schedule():
    """Create a new medicine schedule."""
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    medicine_id = data.get('medicine_id')
    elder_id = data.get('elder_id')
    scheduled_time_str = data.get('scheduled_time')

    if not medicine_id or not elder_id or not scheduled_time_str:
        return jsonify({'error': 'medicine_id, elder_id, and scheduled_time are required'}), 400

    allowed, _ = can_access_elder(user, elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    medicine = Medicine.query.get(medicine_id)
    if not medicine or medicine.elder_id != elder_id:
        return jsonify({'error': 'Medicine not found for this elder'}), 404

    try:
        parsed_time = datetime.strptime(scheduled_time_str, '%H:%M').time()
    except ValueError:
        return jsonify({'error': 'scheduled_time must be in HH:MM format'}), 400

    recurrence = data.get('recurrence', 'daily')
    if recurrence not in ['daily', 'weekly', 'monthly', 'as_needed']:
        return jsonify({'error': 'Invalid recurrence'}), 400

    meal_timing = data.get('meal_timing', 'anytime')
    if meal_timing not in ['before_meal', 'after_meal', 'with_meal', 'anytime']:
        return jsonify({'error': 'Invalid meal_timing'}), 400

    schedule = MedicineSchedule(
        medicine_id=medicine_id,
        elder_id=elder_id,
        scheduled_time=parsed_time,
        day_of_week=data.get('day_of_week', 'all'),
        recurrence=recurrence,
        meal_timing=meal_timing,
        notes=data.get('notes')
    )

    db.session.add(schedule)
    db.session.commit()

    # Schedule today's reminder immediately if the schedule is due today.
    try:
        from app.services.adaptive_reminder_engine import schedule_day_reminders
        today = date.today().isoformat()
        from app.models.schedule import MedicineSchedule as ScheduleModel
        eligible = [schedule]
        schedule_day_reminders(current_app._get_current_object(), eligible, today)
    except Exception as exc:
        current_app.logger.warning('Failed to register new schedule with scheduler: %s', exc)

    return jsonify({'message': 'Schedule created', 'schedule': schedule.to_dict()}), 201


@schedule_bp.route('/<int:schedule_id>', methods=['PUT'])
@jwt_required()
def update_schedule(schedule_id):
    """Update a schedule."""
    user = get_current_user()
    schedule = MedicineSchedule.query.get_or_404(schedule_id)
    allowed, _ = can_access_elder(user, schedule.elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    if 'scheduled_time' in data:
        try:
            schedule.scheduled_time = datetime.strptime(data['scheduled_time'], '%H:%M').time()
        except ValueError:
            return jsonify({'error': 'scheduled_time must be in HH:MM format'}), 400

    updatable = ['day_of_week', 'recurrence', 'meal_timing', 'notes', 'is_active']
    for field in updatable:
        if field in data:
            setattr(schedule, field, data[field])

    db.session.commit()

    # Re-register updated schedule with today’s scheduler if applicable.
    try:
        from app.services.adaptive_reminder_engine import schedule_day_reminders
        today = date.today().isoformat()
        schedule_day_reminders(current_app._get_current_object(), [schedule], today)
    except Exception as exc:
        current_app.logger.warning('Failed to re-register updated schedule with scheduler: %s', exc)

    return jsonify({'message': 'Schedule updated', 'schedule': schedule.to_dict()}), 200


@schedule_bp.route('/<int:schedule_id>', methods=['DELETE'])
@jwt_required()
def delete_schedule(schedule_id):
    """Delete a schedule."""
    user = get_current_user()
    schedule = MedicineSchedule.query.get_or_404(schedule_id)
    allowed, _ = can_access_elder(user, schedule.elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    schedule.is_active = False
    db.session.commit()
    return jsonify({'message': 'Schedule deactivated'}), 200
