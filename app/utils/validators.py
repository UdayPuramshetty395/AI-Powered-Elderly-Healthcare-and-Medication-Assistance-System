import re
from datetime import date


def validate_email(email: str) -> bool:
    """Validate email address format."""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password(password: str) -> bool:
    """
    Validate password strength.
    Must be at least 8 characters with uppercase, lowercase, and digit.
    """
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True


def validate_phone(phone: str) -> bool:
    """Validate phone number (10-15 digits, optional + prefix)."""
    pattern = r'^\+?[0-9]{10,15}$'
    return bool(re.match(pattern, phone.replace(' ', '').replace('-', '')))


def validate_blood_group(blood_group: str) -> bool:
    """Validate blood group format."""
    valid = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    return blood_group.upper() in valid


def validate_date_string(date_str: str) -> bool:
    """Validate date string in YYYY-MM-DD format."""
    try:
        date.fromisoformat(date_str)
        return True
    except (ValueError, TypeError):
        return False


def validate_time_string(time_str: str) -> bool:
    """Validate time string in HH:MM format."""
    pattern = r'^([01]\d|2[0-3]):([0-5]\d)$'
    return bool(re.match(pattern, time_str))


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Sanitize and truncate a string."""
    if not value:
        return ''
    return str(value).strip()[:max_length]


def validate_age(age) -> bool:
    """Validate age value."""
    try:
        age_int = int(age)
        return 1 <= age_int <= 150
    except (ValueError, TypeError):
        return False


def validate_gender(gender: str) -> bool:
    """Validate gender value."""
    return gender in ['male', 'female', 'other']


def validate_required_fields(data: dict, required: list) -> tuple:
    """
    Check that all required fields are present and non-empty.
    Returns (is_valid, missing_fields).
    """
    missing = [field for field in required if not data.get(field)]
    return (len(missing) == 0, missing)
