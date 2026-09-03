from datetime import datetime, date
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.wellness import WellnessCheck
from app.models.elder import Elder
from app.models.user import User

wellness_bp = Blueprint('wellness', __name__)


def get_current_user():
    user_id = get_jwt_identity()
    return User.query.get(int(user_id))


@wellness_bp.route('/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_wellness(elder_id):
    """Get wellness checks for an elder."""
    user = get_current_user()
    elder = Elder.query.get_or_404(elder_id)
    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    days = request.args.get('days', 7, type=int)
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)

    checks = WellnessCheck.query.filter(
        WellnessCheck.elder_id == elder_id,
        WellnessCheck.checked_at >= since
    ).order_by(WellnessCheck.checked_at.desc()).all()

    return jsonify({'wellness_checks': [c.to_dict() for c in checks]}), 200


@wellness_bp.route('/today/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_today_wellness(elder_id):
    """Get today's wellness check for an elder."""
    user = get_current_user()
    elder = Elder.query.get_or_404(elder_id)
    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    today = date.today()
    from datetime import time as time_obj
    check = WellnessCheck.query.filter(
        WellnessCheck.elder_id == elder_id,
        WellnessCheck.checked_at >= datetime.combine(today, time_obj.min)
    ).first()

    return jsonify({'wellness': check.to_dict() if check else None}), 200


@wellness_bp.route('', methods=['POST'])
@jwt_required()
def submit_wellness():
    """Submit a wellness check."""
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    elder_id = data.get('elder_id')
    if not elder_id:
        return jsonify({'error': 'elder_id is required'}), 400

    elder = Elder.query.get_or_404(elder_id)
    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    check = WellnessCheck(
        elder_id=elder_id,
        recorded_by=user.id,
        mood_score=data.get('mood_score'),
        mood_label=data.get('mood_label'),
        pain_level=data.get('pain_level'),
        sleep_quality=data.get('sleep_quality'),
        appetite=data.get('appetite'),
        notes=data.get('notes', '').strip(),
        companion_message=data.get('companion_message', '').strip()
    )

    db.session.add(check)
    db.session.commit()

    # Generate companion AI response to the mood
    response_msg = _get_wellness_ai_response(check)

    return jsonify({
        'message': 'Wellness check recorded',
        'wellness': check.to_dict(),
        'ai_response': response_msg
    }), 201


def _get_wellness_ai_response(check):
    """Generate an AI companion response to wellness data."""
    score = check.mood_score or 3
    pain = check.pain_level or 0

    if pain >= 7:
        return ("⚠️ Your pain level is high. Please inform your caretaker or doctor immediately. "
                "Don't ignore severe pain.")
    elif pain >= 4:
        return ("I notice you're experiencing some pain. Please mention this to your caretaker today. "
                "Rest and stay comfortable.")

    if score == 5:
        return "Wonderful! You're feeling great today! Keep up your medications and stay happy! 😊"
    elif score == 4:
        return "Great to know you're feeling good today! Remember your medicines and enjoy the day!"
    elif score == 3:
        return ("You're doing okay. A walk, some music, or a call with family can brighten the day. "
                "Don't forget your medications!")
    elif score == 2:
        return ("I'm sorry you're not feeling your best. Please talk to your caretaker about how you feel. "
                "You're not alone.")
    else:
        return ("I'm concerned about you. Please reach out to your caretaker or family right away. "
                "You deserve care and support. 💙")


@wellness_bp.route('/summary/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_wellness_summary(elder_id):
    """Get wellness trend summary for an elder."""
    user = get_current_user()
    elder = Elder.query.get_or_404(elder_id)
    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    from datetime import timedelta
    checks = WellnessCheck.query.filter(
        WellnessCheck.elder_id == elder_id,
        WellnessCheck.checked_at >= datetime.utcnow() - timedelta(days=7)
    ).order_by(WellnessCheck.checked_at.asc()).all()

    if not checks:
        return jsonify({'summary': None, 'checks': []}), 200

    avg_mood = sum(c.mood_score for c in checks if c.mood_score) / max(1, sum(1 for c in checks if c.mood_score))
    avg_pain = sum(c.pain_level for c in checks if c.pain_level) / max(1, sum(1 for c in checks if c.pain_level))

    return jsonify({
        'summary': {
            'avg_mood': round(avg_mood, 1),
            'avg_pain': round(avg_pain, 1),
            'total_checks': len(checks),
            'trend': 'improving' if len(checks) >= 2 and checks[-1].mood_score >= checks[0].mood_score else 'stable'
        },
        'checks': [c.to_dict() for c in checks]
    }), 200
