from datetime import datetime
from app import db


class Elder(db.Model):
    """Elder/patient profile model."""
    __tablename__ = 'elders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(
        db.Enum(
            'male',
            'female',
            'other',
            name='gender_enum'
        ),
        nullable=False
    )
    blood_group = db.Column(db.String(10), nullable=True)
    medical_conditions = db.Column(db.Text, nullable=True)
    allergies = db.Column(db.Text, nullable=True)
    caretaker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    emergency_contact = db.Column(db.String(20), nullable=True)
    emergency_contact_name = db.Column(db.String(150), nullable=True)
    address = db.Column(db.Text, nullable=True)
    photo_url = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    medicines = db.relationship('Medicine', backref='elder', lazy=True,
                                foreign_keys='Medicine.elder_id')
    schedules = db.relationship('MedicineSchedule', backref='elder', lazy=True,
                                foreign_keys='MedicineSchedule.elder_id')
    adherence_records = db.relationship('AdherenceRecord', backref='elder', lazy=True,
                                        foreign_keys='AdherenceRecord.elder_id')
    alerts = db.relationship('Alert', backref='elder', lazy=True,
                             foreign_keys='Alert.elder_id')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'age': self.age,
            'gender': self.gender,
            'blood_group': self.blood_group,
            'medical_conditions': self.medical_conditions,
            'allergies': self.allergies,
            'caretaker_id': self.caretaker_id,
            'caretaker_name': self.caretaker.full_name if self.caretaker else None,
            'emergency_contact': self.emergency_contact,
            'emergency_contact_name': self.emergency_contact_name,
            'address': self.address,
            'photo_url': self.photo_url,
            'notes': self.notes,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Elder {self.name}>'
