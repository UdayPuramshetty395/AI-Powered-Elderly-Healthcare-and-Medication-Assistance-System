from datetime import datetime, date
from app import db


class Medicine(db.Model):
    """Medicine/prescription model."""
    __tablename__ = 'medicines'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    generic_name = db.Column(db.String(200), nullable=True)
    dosage = db.Column(db.String(100), nullable=False)
    frequency = db.Column(db.String(100), nullable=False)  # e.g. "Once daily", "Twice daily"
    route = db.Column(
        db.Enum(
            'oral',
            'injection',
            'topical',
            'inhalation',
            'sublingual',
            'other',
            name='medicine_route_enum'
        ),
        nullable=False,
        default='oral'
    )
    elder_id = db.Column(db.Integer, db.ForeignKey('elders.id'), nullable=False, index=True)
    prescribed_by = db.Column(db.String(150), nullable=True)
    start_date = db.Column(db.Date, nullable=True, default=date.today)
    end_date = db.Column(db.Date, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    side_effects = db.Column(db.Text, nullable=True)
    purpose = db.Column(db.String(300), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    schedules = db.relationship('MedicineSchedule', backref='medicine', lazy=True,
                                foreign_keys='MedicineSchedule.medicine_id')
    adherence_records = db.relationship('AdherenceRecord', backref='medicine', lazy=True,
                                        foreign_keys='AdherenceRecord.medicine_id')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'generic_name': self.generic_name,
            'dosage': self.dosage,
            'frequency': self.frequency,
            'route': self.route,
            'elder_id': self.elder_id,
            'elder_name': self.elder.name if self.elder else None,
            'prescribed_by': self.prescribed_by,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'instructions': self.instructions,
            'side_effects': self.side_effects,
            'purpose': self.purpose,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Medicine {self.name}>'
