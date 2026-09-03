from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.alert import Alert
from app.models.elder import Elder
from app.models.user import User

alerts_bp = Blueprint('alerts', __name__)


def get_current_user():
    user_id = get_jwt_identity()
    return User.query.get(int(user_id))


@alerts_bp.route('', methods=['GET'])
@jwt_required()
def get_alerts():
    """Get alerts for current user."""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    elder_id = request.args.get('elder_id', type=int)
    alert_type = request.args.get('alert_type')
    is_read = request.args.get('is_read')

    if user.role == 'admin':
        query = Alert.query
    else:
        query = Alert.query.filter_by(caretaker_id=user.id)

    if elder_id:
        query = query.filter_by(elder_id=elder_id)
    if alert_type:
        query = query.filter_by(alert_type=alert_type)
    if is_read is not None:
        query = query.filter_by(is_read=(is_read.lower() == 'true'))

    alerts = query.order_by(Alert.sent_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'alerts': [a.to_dict() for a in alerts.items],
        'total': alerts.total,
        'pages': alerts.pages,
        'current_page': alerts.page
    }), 200


@alerts_bp.route('/unread', methods=['GET'])
@jwt_required()
def get_unread_alerts():
    """Get unread alerts count and list."""
    user = get_current_user()

    if user.role == 'admin':
        alerts = Alert.query.filter_by(is_read=False).order_by(Alert.sent_at.desc()).limit(10).all()
    else:
        alerts = Alert.query.filter_by(caretaker_id=user.id, is_read=False)\
            .order_by(Alert.sent_at.desc()).limit(10).all()

    return jsonify({
        'count': len(alerts),
        'alerts': [a.to_dict() for a in alerts]
    }), 200


@alerts_bp.route('', methods=['POST'])
@jwt_required()
def create_alert():
    """Create a new alert."""
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    elder_id = data.get('elder_id')
    message = data.get('message', '').strip()
    alert_type = data.get('alert_type', 'general')
    severity = data.get('severity', 'medium')

    if not elder_id or not message:
        return jsonify({'error': 'elder_id and message are required'}), 400

    elder = Elder.query.get(elder_id)
    if not elder:
        return jsonify({'error': 'Elder not found'}), 404

    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    if alert_type not in ['missed_dose', 'low_adherence', 'emergency', 'appointment', 'refill_needed', 'general']:
        return jsonify({'error': 'Invalid alert_type'}), 400
    if severity not in ['low', 'medium', 'high', 'critical']:
        return jsonify({'error': 'Invalid severity'}), 400

    alert = Alert(
        elder_id=elder_id,
        caretaker_id=elder.caretaker_id,
        alert_type=alert_type,
        message=message,
        severity=severity,
        related_medicine_id=data.get('related_medicine_id'),
        related_schedule_id=data.get('related_schedule_id')
    )

    db.session.add(alert)
    db.session.commit()

    return jsonify({'message': 'Alert created', 'alert': alert.to_dict()}), 201


@alerts_bp.route('/<int:alert_id>/read', methods=['PUT'])
@jwt_required()
def mark_alert_read(alert_id):
    """Mark alert as read."""
    user = get_current_user()
    alert = Alert.query.get_or_404(alert_id)

    if user.role != 'admin' and alert.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    alert.is_read = True
    alert.read_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Alert marked as read', 'alert': alert.to_dict()}), 200


@alerts_bp.route('/mark-all-read', methods=['PUT'])
@jwt_required()
def mark_all_read():
    """Mark all unread alerts as read."""
    user = get_current_user()

    if user.role == 'admin':
        Alert.query.filter_by(is_read=False).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
    else:
        Alert.query.filter_by(caretaker_id=user.id, is_read=False).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })

    db.session.commit()
    return jsonify({'message': 'All alerts marked as read'}), 200


@alerts_bp.route('/<int:alert_id>', methods=['DELETE'])
@jwt_required()
def delete_alert(alert_id):
    """Delete an alert."""
    user = get_current_user()
    alert = Alert.query.get_or_404(alert_id)

    if user.role != 'admin' and alert.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(alert)
    db.session.commit()
    return jsonify({'message': 'Alert deleted'}), 200
