from datetime import date
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.medicine import Medicine
from app.models.elder import Elder
from app.models.user import User

medicine_bp = Blueprint('medicine', __name__)


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


@medicine_bp.route('', methods=['GET'])
@jwt_required()
def get_medicines():
    """Get all medicines."""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    is_active = request.args.get('is_active', None)

    if user.role == 'admin':
        query = Medicine.query
    else:
        elder_ids = [e.id for e in Elder.query.filter_by(caretaker_id=user.id, is_active=True).all()]
        query = Medicine.query.filter(Medicine.elder_id.in_(elder_ids))

    if is_active is not None:
        query = query.filter_by(is_active=(is_active.lower() == 'true'))

    medicines = query.order_by(Medicine.name).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'medicines': [m.to_dict() for m in medicines.items],
        'total': medicines.total,
        'pages': medicines.pages,
        'current_page': medicines.page
    }), 200


@medicine_bp.route('/elder/<int:elder_id>', methods=['GET'])
@jwt_required()
def get_medicines_by_elder(elder_id):
    """Get all medicines for a specific elder."""
    user = get_current_user()
    allowed, elder = can_access_elder(user, elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    medicines = Medicine.query.filter_by(elder_id=elder_id, is_active=True).order_by(Medicine.name).all()
    return jsonify({'medicines': [m.to_dict() for m in medicines]}), 200


@medicine_bp.route('', methods=['POST'])
@jwt_required()
def create_medicine():
    """Create a new medicine prescription."""
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    elder_id = data.get('elder_id')
    if not elder_id:
        return jsonify({'error': 'elder_id is required'}), 400

    allowed, elder = can_access_elder(user, elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    name = data.get('name', '').strip()
    dosage = data.get('dosage', '').strip()
    frequency = data.get('frequency', '').strip()

    if not name:
        return jsonify({'error': 'Medicine name is required'}), 400
    if not dosage:
        return jsonify({'error': 'Dosage is required'}), 400
    if not frequency:
        return jsonify({'error': 'Frequency is required'}), 400

    route = data.get('route', 'oral')
    if route not in ['oral', 'injection', 'topical', 'inhalation', 'sublingual', 'other']:
        return jsonify({'error': 'Invalid route'}), 400

    start_date = None
    if data.get('start_date'):
        try:
            start_date = date.fromisoformat(data['start_date'])
        except ValueError:
            return jsonify({'error': 'Invalid start_date format (YYYY-MM-DD)'}), 400

    end_date = None
    if data.get('end_date'):
        try:
            end_date = date.fromisoformat(data['end_date'])
        except ValueError:
            return jsonify({'error': 'Invalid end_date format (YYYY-MM-DD)'}), 400

    medicine = Medicine(
        name=name,
        generic_name=data.get('generic_name'),
        dosage=dosage,
        frequency=frequency,
        route=route,
        elder_id=elder_id,
        prescribed_by=data.get('prescribed_by'),
        start_date=start_date or date.today(),
        end_date=end_date,
        instructions=data.get('instructions'),
        side_effects=data.get('side_effects'),
        purpose=data.get('purpose')
    )

    db.session.add(medicine)
    db.session.commit()

    return jsonify({'message': 'Medicine added', 'medicine': medicine.to_dict()}), 201


@medicine_bp.route('/<int:medicine_id>', methods=['GET'])
@jwt_required()
def get_medicine(medicine_id):
    """Get medicine by ID."""
    user = get_current_user()
    medicine = Medicine.query.get_or_404(medicine_id)
    allowed, _ = can_access_elder(user, medicine.elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403
    return jsonify({'medicine': medicine.to_dict()}), 200


@medicine_bp.route('/<int:medicine_id>', methods=['PUT'])
@jwt_required()
def update_medicine(medicine_id):
    """Update medicine."""
    user = get_current_user()
    medicine = Medicine.query.get_or_404(medicine_id)
    allowed, _ = can_access_elder(user, medicine.elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    updatable = ['name', 'generic_name', 'dosage', 'frequency', 'route',
                 'prescribed_by', 'instructions', 'side_effects', 'purpose', 'is_active']
    for field in updatable:
        if field in data:
            setattr(medicine, field, data[field])

    if 'start_date' in data and data['start_date']:
        medicine.start_date = date.fromisoformat(data['start_date'])
    if 'end_date' in data and data['end_date']:
        medicine.end_date = date.fromisoformat(data['end_date'])

    db.session.commit()
    return jsonify({'message': 'Medicine updated', 'medicine': medicine.to_dict()}), 200


@medicine_bp.route('/<int:medicine_id>', methods=['DELETE'])
@jwt_required()
def delete_medicine(medicine_id):
    """Soft delete medicine."""
    user = get_current_user()
    medicine = Medicine.query.get_or_404(medicine_id)
    allowed, _ = can_access_elder(user, medicine.elder_id)
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    medicine.is_active = False
    db.session.commit()
    return jsonify({'message': 'Medicine deactivated'}), 200
