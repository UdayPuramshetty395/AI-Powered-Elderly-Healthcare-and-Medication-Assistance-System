"""
Analytics & ML API routes
GET  /api/analytics/adherence/<elder_id>     — full adherence stats
GET  /api/analytics/risk/<elder_id>          — ML risk + adherence score
GET  /api/analytics/patterns/<elder_id>      — behavior patterns
GET  /api/analytics/dashboard                — multi-elder summary
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.elder import Elder
from app.models.user import User

analytics_bp = Blueprint('analytics', __name__)


def _get_user():
    return User.query.get(int(get_jwt_identity()))


def _can_access(user, elder_id):
    elder = Elder.query.get(elder_id)
    if not elder:
        return False, None
    if user.role != 'admin' and elder.caretaker_id != user.id:
        return False, None
    return True, elder


@analytics_bp.route('/adherence/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_adherence_analytics(elder_id):
    user = _get_user()
    ok, _ = _can_access(user, elder_id)
    if not ok:
        return jsonify({'error': 'Access denied'}), 403
    from app.services.ml_service import get_adherence_analytics
    return jsonify(get_adherence_analytics(elder_id)), 200


@analytics_bp.route('/risk/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_risk(elder_id):
    user = _get_user()
    ok, elder = _can_access(user, elder_id)
    if not ok:
        return jsonify({'error': 'Access denied'}), 403
    from app.services.ml_service import get_risk_score
    data = get_risk_score(elder_id)
    data['elder_name'] = elder.name
    return jsonify(data), 200


@analytics_bp.route('/patterns/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_patterns(elder_id):
    user = _get_user()
    ok, elder = _can_access(user, elder_id)
    if not ok:
        return jsonify({'error': 'Access denied'}), 403
    from app.services.ml_service import get_behavior_patterns
    data = get_behavior_patterns(elder_id)
    data['elder_name'] = elder.name
    return jsonify(data), 200


@analytics_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def analytics_dashboard():
    """Multi-elder analytics summary for the caretaker dashboard."""
    user = _get_user()
    if user.role == 'admin':
        elders = Elder.query.filter_by(is_active=True).all()
    else:
        elders = Elder.query.filter_by(caretaker_id=user.id, is_active=True).all()

    from app.services.ml_service import get_risk_score, get_adherence_analytics
    summary = []
    for elder in elders:
        risk = get_risk_score(elder.id)
        adh = get_adherence_analytics(elder.id)
        summary.append({
            'elder_id': elder.id,
            'elder_name': elder.name,
            'age': elder.age,
            'risk_score': risk.get('risk_score', 50),
            'adherence_score': risk.get('adherence_score', 0),
            'monthly_rate': adh['monthly']['rate'],
            'weekly_rate': adh['weekly']['rate'],
            'daily_rate': adh['daily']['rate'],
            'missed_today': adh['daily']['missed'],
        })

    return jsonify({'elders': summary}), 200
