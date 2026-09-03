from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from app import db
from app.models.user import User
from app.utils.validators import validate_email, validate_password, validate_phone

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'caretaker')
    phone = data.get('phone', '').strip()
    full_name = data.get('full_name', '').strip()

    # Validations
    if not username or len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    if not validate_email(email):
        return jsonify({'error': 'Invalid email address'}), 400
    if not validate_password(password):
        return jsonify({'error': 'Password must be at least 8 characters with uppercase, lowercase, and number'}), 400
    if role not in ['admin', 'caretaker', 'family']:
        return jsonify({'error': 'Invalid role'}), 400
    if phone and not validate_phone(phone):
        return jsonify({'error': 'Invalid phone number'}), 400

    # Check duplicates
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(
        username=username,
        email=email,
        role=role,
        phone=phone or None,
        full_name=full_name or username
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    # Send welcome email to caretaker in background
    if user.email:
        import threading
        from flask import current_app
        _app = current_app._get_current_object()
        def _welcome():
            with _app.app_context():
                try:
                    from app.services.email_service import _send
                    subject = 'Welcome to AI-Powered Elderly Healthcare System'
                    body = f"""Dear {user.full_name or user.username},

Welcome to AI-Powered Elderly Healthcare and Medication Assistance System!

Your account has been created successfully.

You will automatically receive:
  - Email alerts when a patient misses their medicine
  - Daily medication summary every evening at 9 PM
  - Urgent alerts for repeated missed doses

Your login:
  Username : {user.username}
  Role     : {user.role.title()}

To get started:
  1. Add elder/patient profiles
  2. Add their medicines
  3. Create medicine schedules
  4. The system will automatically send reminders

Login at: http://localhost:5000

---
AI-Powered Elderly Healthcare System
"""
                    _send(user.email, subject, body)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f'Welcome email failed: {e}')
        threading.Thread(target=_welcome, daemon=True).start()

    return jsonify({
        'message': 'Registration successful',
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login with username/email and password."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    identifier = data.get('username') or data.get('email', '')
    password = data.get('password', '')

    if not identifier or not password:
        return jsonify({'error': 'Username/email and password required'}), 400

    # Find by username or email
    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier.lower())
    ).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 403

    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user or not user.is_active:
        return jsonify({'error': 'User not found or inactive'}), 401
    access_token = create_access_token(identity=str(user.id))
    return jsonify({'access_token': access_token}), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout (client should discard the token)."""
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    """Get current user profile."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200


@auth_bp.route('/change-password', methods=['PUT'])
@jwt_required()
def change_password():
    """Change user password."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True)
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400
    if not validate_password(new_password):
        return jsonify({'error': 'New password must be at least 8 characters with uppercase, lowercase, and number'}), 400

    user.set_password(new_password)
    db.session.commit()

    return jsonify({'message': 'Password changed successfully'}), 200


@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True)
    if 'full_name' in data:
        user.full_name = data['full_name'].strip()
    if 'phone' in data:
        phone = data['phone'].strip()
        if phone and not validate_phone(phone):
            return jsonify({'error': 'Invalid phone number'}), 400
        user.phone = phone or None

    db.session.commit()
    return jsonify({'message': 'Profile updated', 'user': user.to_dict()}), 200
