import bcrypt
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.models.user import User


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def get_current_user() -> User:
    """Get the current authenticated user from JWT."""
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return User.query.get(int(user_id))


def admin_required(fn):
    """Decorator: require admin role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = get_current_user()
        if not user or user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


def caretaker_or_admin_required(fn):
    """Decorator: require caretaker or admin role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = get_current_user()
        if not user or user.role not in ['admin', 'caretaker']:
            return jsonify({'error': 'Caretaker or admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


def active_user_required(fn):
    """Decorator: require active user account."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = get_current_user()
        if not user or not user.is_active:
            return jsonify({'error': 'Account is inactive'}), 403
        return fn(*args, **kwargs)
    return wrapper
