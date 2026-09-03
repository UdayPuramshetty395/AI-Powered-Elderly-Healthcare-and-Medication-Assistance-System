from datetime import datetime, time
from app import db


class MedicineSchedule(db.Model):
    """Medicine schedule/timing model."""
    __tablename__ = 'medicine_schedules'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=False, index=True)
    elder_id = db.Column(db.Integer, db.ForeignKey('elders.id'), nullable=False, index=True)
    scheduled_time = db.Column(db.Time, nullable=False)
    day_of_week = db.Column(db.String(20), nullable=True)  # 'all', 'monday', 'tuesday', etc.
    recurrence = db.Column(db.Enum('daily', 'weekly', 'monthly', 'as_needed'), 
                          nullable=False, default='daily')
    meal_timing = db.Column(db.Enum('before_meal', 'after_meal', 'with_meal', 'anytime'),
                           nullable=True, default='anytime')
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    adherence_records = db.relationship('AdherenceRecord', backref='schedule', lazy=True,
                                        foreign_keys='AdherenceRecord.schedule_id')

    def to_dict(self):
        return {
            'id': self.id,
            'medicine_id': self.medicine_id,
            'medicine_name': self.medicine.name if self.medicine else None,
            'medicine_dosage': self.medicine.dosage if self.medicine else None,
            'elder_id': self.elder_id,
            'elder_name': self.elder.name if self.elder else None,
            'scheduled_time': self.scheduled_time.strftime('%H:%M:%S') if self.scheduled_time else None,
            'day_of_week': self.day_of_week,
            'recurrence': self.recurrence,
            'meal_timing': self.meal_timing,
            'notes': self.notes,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<MedicineSchedule {self.medicine_id} at {self.scheduled_time}>'
