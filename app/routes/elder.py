from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.elder import Elder
from app.models.user import User

elder_bp = Blueprint('elder', __name__)


def get_current_user():
    user_id = get_jwt_identity()
    return User.query.get(int(user_id))


@elder_bp.route('', methods=['GET'])
@jwt_required()
def get_elders():
    """Get all elders for current caretaker."""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()

    query = Elder.query.filter_by(is_active=True)
    if user.role != 'admin':
        query = query.filter_by(caretaker_id=user.id)
    if search:
        query = query.filter(Elder.name.ilike(f'%{search}%'))

    elders = query.order_by(Elder.name).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'elders': [e.to_dict() for e in elders.items],
        'total': elders.total,
        'pages': elders.pages,
        'current_page': elders.page
    }), 200


@elder_bp.route('', methods=['POST'])
@jwt_required()
def create_elder():
    """Create a new elder profile."""
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    name = data.get('name', '').strip()
    age = data.get('age')
    gender = data.get('gender', '').strip()

    if not name:
        return jsonify({'error': 'Name is required'}), 400
    if not age or not isinstance(age, int) or age < 1 or age > 150:
        return jsonify({'error': 'Valid age is required'}), 400
    if gender not in ['male', 'female', 'other']:
        return jsonify({'error': 'Gender must be male, female, or other'}), 400

    elder = Elder(
        name=name,
        age=age,
        gender=gender,
        blood_group=data.get('blood_group'),
        medical_conditions=data.get('medical_conditions'),
        allergies=data.get('allergies'),
        caretaker_id=user.id,
        emergency_contact=data.get('emergency_contact'),
        emergency_contact_name=data.get('emergency_contact_name'),
        address=data.get('address'),
        photo_url=data.get('photo_url'),
        notes=data.get('notes')
    )

    db.session.add(elder)
    db.session.commit()

    return jsonify({'message': 'Elder profile created', 'elder': elder.to_dict()}), 201


@elder_bp.route('/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_elder(elder_id):
    """Get elder by ID."""
    user = get_current_user()
    elder = Elder.query.get_or_404(elder_id)

    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({'elder': elder.to_dict()}), 200


@elder_bp.route('/<int:elder_id>', methods=['PUT'])
@jwt_required()
def update_elder(elder_id):
    """Update elder profile."""
    user = get_current_user()
    elder = Elder.query.get_or_404(elder_id)

    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    updatable = ['name', 'age', 'gender', 'blood_group', 'medical_conditions',
                 'allergies', 'emergency_contact', 'emergency_contact_name',
                 'address', 'photo_url', 'notes']
    for field in updatable:
        if field in data:
            setattr(elder, field, data[field])

    db.session.commit()
    return jsonify({'message': 'Elder profile updated', 'elder': elder.to_dict()}), 200


@elder_bp.route('/<int:elder_id>', methods=['DELETE'])
@jwt_required()
def delete_elder(elder_id):
    """Soft delete elder profile."""
    user = get_current_user()
    elder = Elder.query.get_or_404(elder_id)

    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    elder.is_active = False
    db.session.commit()
    return jsonify({'message': 'Elder profile deactivated'}), 200


@elder_bp.route('/<int:elder_id>/summary', methods=['GET'])
@jwt_required()
def get_elder_summary(elder_id):
    """Get elder summary with medicine and adherence stats."""
    user = get_current_user()
    elder = Elder.query.get_or_404(elder_id)

    if user.role != 'admin' and elder.caretaker_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    from app.models.medicine import Medicine
    from app.models.adherence import AdherenceRecord
    from sqlalchemy import func

    active_medicines = Medicine.query.filter_by(elder_id=elder_id, is_active=True).count()
    total_records = AdherenceRecord.query.filter_by(elder_id=elder_id).count()
    taken_records = AdherenceRecord.query.filter_by(elder_id=elder_id, status='taken').count()
    adherence_rate = round((taken_records / total_records * 100), 1) if total_records > 0 else 0

    return jsonify({
        'elder': elder.to_dict(),
        'stats': {
            'active_medicines': active_medicines,
            'total_doses_scheduled': total_records,
            'doses_taken': taken_records,
            'adherence_rate': adherence_rate
        }
    }), 200
